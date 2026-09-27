"""SQLite queue builder for TypeBeat radio."""

from __future__ import annotations

import json
import random
import sqlite3
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from .genres import (
    DEFAULT_MAX_VIEWS,
    DEFAULT_MIN_VIEWS,
    DEFAULT_VIEW_TIER_ID,
    HQ_MIX_DB_GENRES,
    QUEUE_BATCH,
    get_genre,
)

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "typebeats.db"
DATA_DIR = Path(__file__).resolve().parent / "data"
WARM_QUEUE_PATH = DATA_DIR / "warm_queue.json"
PROLIFIC_TXT = ROOT / "prolific_producers.txt"
PROLIFIC_DB = DATA_DIR / "prolific_channels.sqlite"
WARM_QUEUE_SIZE = 40
INDEX_GENRE_VIEWS = "idx_beats_genre_views"
INDEX_VIEWS_VID = "idx_beats_views_vid"

_column_cache: dict[str, bool] = {}


def beats_has_column(conn: sqlite3.Connection, name: str) -> bool:
    """True when beats has this column. Cached so a missing parent_genre
    does not break station playback. Existence alone is not a filter."""
    cached = _column_cache.get(name)
    if cached is not None:
        return cached
    found = any(row[1] == name for row in conn.execute("PRAGMA table_info(beats)"))
    _column_cache[name] = found
    return found

_prolific_ready = False
_prolific_count = 0


def _load_prolific_names() -> list[str]:
    if not PROLIFIC_TXT.is_file():
        return []
    names: list[str] = []
    seen: set[str] = set()
    try:
        text = PROLIFIC_TXT.read_text(encoding="utf-8")
    except OSError:
        return []
    for line in text.splitlines():
        name = line.strip()
        if not name or name in seen:
            continue
        seen.add(name)
        names.append(name)
    return names


def ensure_prolific_side_db(*, force: bool = False) -> int:
    """
    Materialize prolific channel names into a tiny side SQLite for JOIN filters.
    Source of truth: prolific_producers.txt (window-tier ≥ p90 / ≥22 tracks).
    """
    global _prolific_ready, _prolific_count
    if _prolific_ready and not force and PROLIFIC_DB.is_file():
        return _prolific_count

    names = _load_prolific_names()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    stale = True
    if PROLIFIC_DB.is_file() and PROLIFIC_TXT.is_file() and not force:
        try:
            stale = PROLIFIC_DB.stat().st_mtime < PROLIFIC_TXT.stat().st_mtime
        except OSError:
            stale = True
    if stale or not PROLIFIC_DB.is_file() or force:
        conn = sqlite3.connect(str(PROLIFIC_DB), timeout=30.0)
        try:
            conn.execute("DROP TABLE IF EXISTS channels")
            conn.execute(
                "CREATE TABLE channels (name TEXT PRIMARY KEY NOT NULL)"
            )
            if names:
                conn.executemany(
                    "INSERT OR IGNORE INTO channels(name) VALUES (?)",
                    [(n,) for n in names],
                )
            conn.commit()
        finally:
            conn.close()

    _prolific_count = len(names)
    _prolific_ready = True
    return _prolific_count


def _attach_prolific(conn: sqlite3.Connection) -> bool:
    """ATTACH side DB for EXISTS join. Returns False if unavailable."""
    try:
        ensure_prolific_side_db()
        if not PROLIFIC_DB.is_file():
            return False
        # Re-attach safely if a prior call left it open on a reused connection.
        try:
            conn.execute("DETACH DATABASE prolific")
        except sqlite3.Error:
            pass
        conn.execute(
            "ATTACH DATABASE ? AS prolific",
            (str(PROLIFIC_DB.resolve()),),
        )
        return True
    except sqlite3.Error:
        return False


def _detach_prolific(conn: sqlite3.Connection) -> None:
    try:
        conn.execute("DETACH DATABASE prolific")
    except sqlite3.Error:
        pass


def connect() -> sqlite3.Connection:
    # Read-friendly while harvester may hold a write lock on the same DB.
    uri = f"file:{DB_PATH}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, check_same_thread=False, timeout=60.0)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA busy_timeout=60000")
    except sqlite3.Error:
        pass
    return conn


def connect_write(*, timeout: float = 60.0) -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False, timeout=timeout)
    conn.row_factory = sqlite3.Row
    conn.execute(f"PRAGMA busy_timeout={int(timeout * 1000)}")
    return conn


def _index_names(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name IS NOT NULL"
    ).fetchall()
    return {str(r[0] if not isinstance(r, sqlite3.Row) else r["name"]) for r in rows}


def missing_radio_indexes(conn: sqlite3.Connection) -> list[str]:
    have = _index_names(conn)
    missing: list[str] = []
    if INDEX_GENRE_VIEWS not in have:
        missing.append(INDEX_GENRE_VIEWS)
    if INDEX_VIEWS_VID not in have:
        missing.append(INDEX_VIEWS_VID)
    return missing


def ensure_radio_index(conn: sqlite3.Connection) -> None:
    """Speeds genre + view-cap queue pulls (one-time cost on huge DBs)."""
    # Index creation needs a writable connection (see connect_write in server warm).
    conn.execute(
        f"CREATE INDEX IF NOT EXISTS {INDEX_GENRE_VIEWS} ON beats(genre, views)"
    )
    # All station has no genre filter — keyset on views alone.
    # Without this, deep_mix does a full table SCAN + TEMP B-TREE (~tens of seconds).
    conn.execute(
        f"CREATE INDEX IF NOT EXISTS {INDEX_VIEWS_VID} ON beats(views, video_id)"
    )
    conn.commit()


def has_views_index(conn: sqlite3.Connection | None = None) -> bool:
    own = False
    if conn is None:
        conn = connect()
        own = True
    try:
        return INDEX_VIEWS_VID not in missing_radio_indexes(conn)
    finally:
        if own:
            conn.close()


def _rows_to_tracks(rows: list[sqlite3.Row]) -> list[dict]:
    tracks = []
    for r in rows:
        keys = r.keys()
        tracks.append(
            {
                "video_id": r["video_id"],
                "title": r["title"],
                "channel_name": r["channel_name"],
                "views": r["views"],
                "url": r["url"]
                if "url" in keys
                else f"https://youtube.com/watch?v={r['video_id']}",
                "published_time": r["published_time"]
                if "published_time" in keys
                else None,
            }
        )
    return tracks


def _parse_cursor(cursor: str | None) -> tuple[int, str] | None:
    """Cursor is 'views:video_id' from the last track of the previous page."""
    if not cursor or ":" not in cursor or cursor.startswith("u:"):
        return None
    views_s, vid = cursor.split(":", 1)
    try:
        return int(views_s), vid
    except ValueError:
        return None


def _decode_union_cursor(
    cursor: str | None,
) -> tuple[str | None, str | None, bool, bool]:
    """Split a union cursor into genre and keyword keysets.

    Format: ``u:g=<views:video_id>|-|k=<views:video_id>|-``.
    ``-`` means that side is exhausted. Any other cursor starts both sides
    from the beginning so a station keeps walking tagged rows and keywords.
    """
    if not cursor or not cursor.startswith("u:"):
        return None, None, False, False
    genre_tok = ""
    keyword_tok = ""
    for part in cursor[2:].split("|"):
        if part.startswith("g="):
            genre_tok = part[2:]
        elif part.startswith("k="):
            keyword_tok = part[2:]
    genre_done = genre_tok == "-"
    keyword_done = keyword_tok == "-"
    genre_cursor = None if genre_done or not genre_tok else genre_tok
    keyword_cursor = None if keyword_done or not keyword_tok else keyword_tok
    return genre_cursor, keyword_cursor, genre_done, keyword_done


def _encode_union_cursor(
    genre_cursor: str | None,
    keyword_cursor: str | None,
    *,
    genre_done: bool,
    keyword_done: bool,
) -> str | None:
    if genre_done and keyword_done:
        return None
    genre_tok = "-" if genre_done or not genre_cursor else genre_cursor
    keyword_tok = "-" if keyword_done or not keyword_cursor else keyword_cursor
    return f"u:g={genre_tok}|k={keyword_tok}"


def _row_cursor(row: sqlite3.Row) -> str:
    return f"{int(row['views'] or 0)}:{row['video_id']}"


def _with_retry(fn):
    last_err: Exception | None = None
    for attempt in range(4):
        try:
            return fn()
        except sqlite3.OperationalError as exc:
            last_err = exc
            if "locked" not in str(exc).lower() or attempt == 3:
                raise
            time.sleep(0.35 * (attempt + 1))
    if last_err:
        raise last_err
    return None


def _published_after_iso(max_age_months: int | None) -> str | None:
    """ISO cutoff date for age filter, or None when unrestricted."""
    if max_age_months is None:
        return None
    try:
        months = int(max_age_months)
    except (TypeError, ValueError):
        return None
    if months <= 0:
        return None
    # Approximate calendar months as 30-day blocks (experimental filter).
    cutoff = date.today() - timedelta(days=months * 30)
    return cutoff.isoformat()


def _free_clauses(
    *,
    require_free: bool = False,
    require_ffp: bool = False,
    require_prolific: bool = False,
    max_age_months: int | None = None,
) -> tuple[str, list[Any]]:
    """Optional license / prolific / age chips — off means no filter."""
    clauses: list[str] = []
    params: list[Any] = []
    if require_free:
        clauses.append("COALESCE(is_free, 0) = 1")
    if require_ffp:
        clauses.append("COALESCE(free_for_profit, 0) = 1")
    if require_prolific:
        clauses.append(
            "EXISTS (SELECT 1 FROM prolific.channels pc WHERE pc.name = beats.channel_name)"
        )
    published_after = _published_after_iso(max_age_months)
    if published_after:
        # Only ISO YYYY-MM-DD rows (majority of catalog). Relative "N ago"
        # strings must not participate in lexicographic date compares.
        clauses.append(
            "(published_time GLOB '[0-9][0-9][0-9][0-9]-*' AND published_time >= ?)"
        )
        params.append(published_after)
    if not clauses:
        return "", []
    return " AND " + " AND ".join(clauses), params


def _fetch_by_genres_page(
    conn: sqlite3.Connection,
    db_genres: list[str],
    max_views: int,
    fetch_n: int,
    cursor: str | None,
    *,
    min_views: int = 1,
    require_free: bool = False,
    require_ffp: bool = False,
    require_prolific: bool = False,
    max_age_months: int | None = None,
    column: str = "genre",
) -> list[sqlite3.Row]:
    """Keyset page through lowest-view tagged rows.

    ``column`` is ``genre`` (one subgenre, or Underground) or ``parent_genre``
    (a parent button). Callers pass ``parent_genre`` only after that column
    is filled. A missing column stays on ``genre``.
    """
    if column not in ("genre", "parent_genre"):
        column = "genre"
    if column == "parent_genre" and not beats_has_column(conn, "parent_genre"):
        column = "genre"
    min_views = max(1, int(min_views))
    free_sql, free_params = _free_clauses(
        require_free=require_free,
        require_ffp=require_ffp,
        require_prolific=require_prolific,
        max_age_months=max_age_months,
    )
    placeholders = ",".join("?" * len(db_genres))
    parsed = _parse_cursor(cursor)
    if parsed:
        c_views, c_vid = parsed
        sql = f"""
            SELECT video_id, title, channel_name, views, url, published_time
            FROM beats
            WHERE {column} IN ({placeholders})
              AND views >= ?
              AND views <= ?
              AND video_id IS NOT NULL
              AND length(video_id) > 5
              {free_sql}
              AND (views > ? OR (views = ? AND video_id > ?))
            ORDER BY views ASC, video_id ASC
            LIMIT ?
        """
        return conn.execute(
            sql,
            [
                *db_genres,
                min_views,
                max_views,
                *free_params,
                c_views,
                c_views,
                c_vid,
                fetch_n,
            ],
        ).fetchall()

    sql = f"""
        SELECT video_id, title, channel_name, views, url, published_time
        FROM beats
        WHERE {column} IN ({placeholders})
          AND views >= ?
          AND views <= ?
          AND video_id IS NOT NULL
          AND length(video_id) > 5
          {free_sql}
        ORDER BY views ASC, video_id ASC
        LIMIT ?
    """
    return conn.execute(
        sql, [*db_genres, min_views, max_views, *free_params, fetch_n]
    ).fetchall()


def _fetch_deep_catalog_page(
    conn: sqlite3.Connection,
    max_views: int,
    fetch_n: int,
    cursor: str | None,
    *,
    min_views: int = 1,
    require_free: bool = False,
    require_ffp: bool = False,
    require_prolific: bool = False,
    max_age_months: int | None = None,
) -> list[sqlite3.Row]:
    """
    All station: no genre filter (includes Underground flood).
    Same keyset (views, video_id) as tagged stations — paginate forever.
    """
    min_views = max(1, int(min_views))
    free_sql, free_params = _free_clauses(
        require_free=require_free,
        require_ffp=require_ffp,
        require_prolific=require_prolific,
        max_age_months=max_age_months,
    )
    parsed = _parse_cursor(cursor)
    if parsed:
        c_views, c_vid = parsed
        sql = f"""
            SELECT video_id, title, channel_name, views, url, published_time
            FROM beats
            WHERE views >= ?
              AND views <= ?
              AND video_id IS NOT NULL
              AND length(video_id) > 5
              {free_sql}
              AND (views > ? OR (views = ? AND video_id > ?))
            ORDER BY views ASC, video_id ASC
            LIMIT ?
        """
        return conn.execute(
            sql,
            [min_views, max_views, *free_params, c_views, c_views, c_vid, fetch_n],
        ).fetchall()

    sql = f"""
        SELECT video_id, title, channel_name, views, url, published_time
        FROM beats
        WHERE views >= ?
          AND views <= ?
          AND video_id IS NOT NULL
          AND length(video_id) > 5
          {free_sql}
        ORDER BY views ASC, video_id ASC
        LIMIT ?
    """
    return conn.execute(
        sql, [min_views, max_views, *free_params, fetch_n]
    ).fetchall()


def _fetch_hq_mix_page(
    conn: sqlite3.Connection,
    max_views: int,
    fetch_n: int,
    cursor: str | None,
    *,
    min_views: int = DEFAULT_MIN_VIEWS,
    require_free: bool = False,
    require_ffp: bool = False,
    require_prolific: bool = False,
    max_age_months: int | None = None,
) -> list[sqlite3.Row]:
    """
    Cross-genre quality mix: tagged radio styles only (no Underground flood),
    views in [min_views, max_views].

    Pulls a small indexed page per genre (fast under harvester write load),
    merges by (views, video_id), then the caller shuffles the batch.
    """
    n_g = max(1, len(HQ_MIX_DB_GENRES))
    # Slight over-fetch so shuffle still has cross-genre variety after trim.
    per = max(6, (fetch_n + n_g - 1) // n_g + 3)
    merged: list[sqlite3.Row] = []
    seen: set[str] = set()
    for g in HQ_MIX_DB_GENRES:
        chunk = _fetch_by_genres_page(
            conn,
            [g],
            max_views,
            per,
            cursor,
            min_views=min_views,
            require_free=require_free,
            require_ffp=require_ffp,
            require_prolific=require_prolific,
            max_age_months=max_age_months,
        )
        for row in chunk:
            vid = row["video_id"]
            if vid in seen:
                continue
            seen.add(vid)
            merged.append(row)
    merged.sort(key=lambda r: (int(r["views"] or 0), r["video_id"] or ""))
    return merged[:fetch_n]


def _fetch_keyword_station_page(
    conn: sqlite3.Connection,
    keywords: list[str],
    max_views: int,
    fetch_n: int,
    cursor: str | None,
    *,
    min_views: int = 1,
    require_free: bool = False,
    require_ffp: bool = False,
    require_prolific: bool = False,
    max_age_months: int | None = None,
    fallback: bool = True,
) -> tuple[list[sqlite3.Row], list[sqlite3.Row]]:
    """
    Walk low-view Underground (indexed) in pages, soft-match keywords in Python
    so we never full-scan 5M rows with LIKE.

    Returns (matched rows, scanned pool). Keyword-only stations pass
    ``fallback=True`` and get an Underground slice when the window has no hits.
    Stations that also have ``db_genres`` pass ``fallback=False`` so only real
    keyword hits are merged in.
    """
    min_views = max(1, int(min_views))
    free_sql, free_params = _free_clauses(
        require_free=require_free,
        require_ffp=require_ffp,
        require_prolific=require_prolific,
        max_age_months=max_age_months,
    )
    parsed = _parse_cursor(cursor)
    sample_n = min(max(fetch_n * 20, 4000), 8000)
    if parsed:
        c_views, c_vid = parsed
        sql = f"""
            SELECT video_id, title, channel_name, views, url, published_time,
                   coalesce(artist_style, '') AS artist_style
            FROM beats
            WHERE genre = 'Underground'
              AND views >= ? AND views <= ?
              AND video_id IS NOT NULL AND length(video_id) > 5
              {free_sql}
              AND (views > ? OR (views = ? AND video_id > ?))
            ORDER BY views ASC, video_id ASC
            LIMIT ?
        """
        pool = conn.execute(
            sql,
            [min_views, max_views, *free_params, c_views, c_views, c_vid, sample_n],
        ).fetchall()
    else:
        sql = f"""
            SELECT video_id, title, channel_name, views, url, published_time,
                   coalesce(artist_style, '') AS artist_style
            FROM beats
            WHERE genre = 'Underground'
              AND views >= ? AND views <= ?
              AND video_id IS NOT NULL AND length(video_id) > 5
              {free_sql}
            ORDER BY views ASC, video_id ASC
            LIMIT ?
        """
        pool = conn.execute(
            sql, [min_views, max_views, *free_params, sample_n]
        ).fetchall()

    keys = [k.lower() for k in keywords]
    matched = []
    for row in pool:
        blob = f"{row['title'] or ''} {row['artist_style'] or ''}".lower()
        if any(k in blob for k in keys):
            matched.append(row)
            if len(matched) >= fetch_n:
                break
    if matched:
        return matched, list(pool)
    if fallback:
        # Keyword-only stations still play when this window has no title hits.
        return list(pool[:fetch_n]), list(pool)
    return [], list(pool)


def _fetch_union_station_page(
    conn: sqlite3.Connection,
    db_genres: list[str],
    keywords: list[str],
    max_views: int,
    fetch_n: int,
    cursor: str | None,
    *,
    match_column: str = "genre",
    **filt: Any,
) -> tuple[list[sqlite3.Row], str | None, bool]:
    """Tagged rows OR Underground keyword hits, one shared page.

    ``match_column`` is ``parent_genre`` for a parent button and ``genre``
    for one subgenre. Keyword hits stay Underground titles.
    Each side keeps its own keyset. A page alternates them so neither catalog
    is dropped, and each cursor advances only through rows that were consumed.
    """
    genre_cursor, keyword_cursor, genre_done, keyword_done = _decode_union_cursor(
        cursor
    )
    tagged: list[sqlite3.Row] = []
    if not genre_done:
        tagged = _fetch_by_genres_page(
            conn,
            db_genres,
            max_views,
            fetch_n,
            genre_cursor,
            column=match_column,
            **filt,
        )
    matched: list[sqlite3.Row] = []
    pool: list[sqlite3.Row] = []
    if not keyword_done and keywords:
        matched, pool = _fetch_keyword_station_page(
            conn,
            keywords,
            max_views,
            fetch_n,
            keyword_cursor,
            fallback=False,
            **filt,
        )

    rows: list[sqlite3.Row] = []
    seen: set[str] = set()
    i = j = 0
    while len(rows) < fetch_n and (i < len(tagged) or j < len(matched)):
        if i < len(tagged):
            row = tagged[i]
            i += 1
            vid = row["video_id"]
            if vid not in seen:
                seen.add(vid)
                rows.append(row)
                if len(rows) >= fetch_n:
                    break
        if j < len(matched) and len(rows) < fetch_n:
            row = matched[j]
            j += 1
            vid = row["video_id"]
            if vid not in seen:
                seen.add(vid)
                rows.append(row)

    if genre_done or not tagged:
        genre_done = True
        next_genre = None
    elif i < len(tagged):
        next_genre = _row_cursor(tagged[i - 1])
    elif len(tagged) >= fetch_n:
        next_genre = _row_cursor(tagged[-1])
    else:
        genre_done = True
        next_genre = None

    sample_cap = min(max(fetch_n * 20, 4000), 8000)
    if keyword_done or not keywords:
        keyword_done = True
        next_keyword = None
    elif j > 0 and (j < len(matched) or len(matched) >= fetch_n):
        # More keyword hits may sit after the last match we kept.
        next_keyword = _row_cursor(matched[j - 1])
    elif pool and len(pool) >= sample_cap:
        next_keyword = _row_cursor(pool[-1])
    else:
        keyword_done = True
        next_keyword = None

    next_cursor = _encode_union_cursor(
        next_genre,
        next_keyword,
        genre_done=genre_done,
        keyword_done=keyword_done,
    )
    return rows, next_cursor, next_cursor is not None


def build_queue_page(
    genre_id: str,
    *,
    max_views: int = DEFAULT_MAX_VIEWS,
    min_views: int | None = None,
    limit: int = QUEUE_BATCH,
    cursor: str | None = None,
    require_free: bool = False,
    require_ffp: bool = False,
    require_prolific: bool = False,
    max_age_months: int | None = None,
    subgenre: str | None = None,
) -> dict[str, Any]:
    """
    One shuffled batch of a station's filtered catalog.

    Uses keyset pagination (views, video_id) so refill can walk the entire
    views band over a session without loading millions of rows at once.
    Each page is shuffled for radio feel; order across pages stays low-view-first.
    """
    genre = get_genre(genre_id)
    if not genre:
        return {
            "tracks": [],
            "cursor": None,
            "next_cursor": None,
            "has_more": False,
            "limit": limit,
        }

    limit = max(1, min(int(limit), 200))
    # Fetch exactly one page — don't over-fetch then discard (that skips tracks
    # when the keyset cursor advances past the scanned window).
    fetch_n = limit
    hq_mix = bool(genre.get("hq_mix"))
    deep_mix = bool(genre.get("deep_mix"))
    floor = max(1, int(min_views if min_views is not None else DEFAULT_MIN_VIEWS))
    ceiling = max(floor, int(max_views))
    published_after = _published_after_iso(max_age_months)

    conn = connect()
    prolific_attached = False
    try:
        if require_prolific:
            prolific_attached = _attach_prolific(conn)
            if not prolific_attached:
                # No side table — return empty rather than silently ignoring filter.
                return {
                    "tracks": [],
                    "cursor": cursor,
                    "next_cursor": None,
                    "has_more": False,
                    "limit": limit,
                    "hq_mix": hq_mix,
                    "deep_mix": deep_mix,
                    "max_views": ceiling,
                    "min_views": floor,
                    "require_free": require_free,
                    "require_ffp": require_ffp,
                    "prolific": True,
                    "max_age_months": max_age_months,
                    "published_after": published_after,
                    "error": "prolific channel list unavailable",
                }

        scanned: list[sqlite3.Row] = []
        union_next: str | None = None
        union_has_more = False
        used_union = False
        filt = dict(
            min_views=floor,
            require_free=require_free,
            require_ffp=require_ffp,
            require_prolific=require_prolific and prolific_attached,
            max_age_months=max_age_months,
        )

        def _pull():
            nonlocal scanned, union_next, union_has_more, used_union
            if hq_mix:
                rows = _fetch_hq_mix_page(
                    conn, ceiling, fetch_n, cursor, **filt
                )
                scanned = list(rows)
                return rows
            if deep_mix:
                # Without idx_beats_views_vid, ORDER BY views ASC scans ~all rows
                # (~30s+ on 5M). Fall back to genre-indexed HQ slices until warmup.
                if INDEX_VIEWS_VID in missing_radio_indexes(conn):
                    rows = _fetch_hq_mix_page(
                        conn, ceiling, fetch_n, cursor, **filt
                    )
                    scanned = list(rows)
                    return rows
                rows = _fetch_deep_catalog_page(
                    conn, ceiling, fetch_n, cursor, **filt
                )
                scanned = list(rows)
                return rows
            db_genres = list(genre.get("db_genres") or [])
            keywords = genre.get("keywords") or []
            parent = genre.get("parent")
            chosen = (subgenre or "").strip()
            # Explore can play one subgenre. Main buttons play the parent.
            if chosen and chosen in db_genres:
                rows = _fetch_by_genres_page(
                    conn,
                    [chosen],
                    ceiling,
                    fetch_n,
                    cursor,
                    column="genre",
                    **filt,
                )
                scanned = list(rows)
                return rows
            # Parent buttons read parent_genre. All is deep_mix (above).
            # UG MIX stays on genre = Underground.
            if parent and parent != "Underground" and db_genres:
                use_parent = beats_has_column(conn, "parent_genre")
                tagged = [parent] if use_parent else db_genres
                column = "parent_genre" if use_parent else "genre"
                if keywords:
                    rows, union_next, union_has_more = _fetch_union_station_page(
                        conn,
                        tagged,
                        keywords,
                        ceiling,
                        fetch_n,
                        cursor,
                        match_column=column,
                        **filt,
                    )
                    used_union = True
                    scanned = list(rows)
                    return rows
                rows = _fetch_by_genres_page(
                    conn,
                    tagged,
                    ceiling,
                    fetch_n,
                    cursor,
                    column=column,
                    **filt,
                )
                scanned = list(rows)
                return rows
            if db_genres and keywords:
                rows, union_next, union_has_more = _fetch_union_station_page(
                    conn,
                    db_genres,
                    keywords,
                    ceiling,
                    fetch_n,
                    cursor,
                    **filt,
                )
                used_union = True
                scanned = list(rows)
                return rows
            if db_genres:
                rows = _fetch_by_genres_page(
                    conn,
                    db_genres,
                    ceiling,
                    fetch_n,
                    cursor,
                    **filt,
                )
                scanned = list(rows)
                return rows
            matched, pool = _fetch_keyword_station_page(
                conn,
                keywords,
                ceiling,
                fetch_n,
                cursor,
                **filt,
            )
            scanned = pool
            return matched

        rows = _with_retry(_pull) or []
        tracks = _rows_to_tracks(rows)

        # Cursor advances past the SQL window actually scanned (before shuffle).
        # Union stations keep a separate keyset per source so keyword pages
        # are not dropped once db_genres is set.
        if used_union:
            next_cursor = union_next
            has_more = union_has_more
        else:
            page_end_row = scanned[-1] if scanned else None
            next_cursor = (
                f"{int(page_end_row['views'])}:{page_end_row['video_id']}"
                if page_end_row
                else None
            )
            if hq_mix or deep_mix or genre.get("db_genres"):
                has_more = len(scanned) >= fetch_n
            else:
                sample_cap = min(max(fetch_n * 20, 4000), 8000)
                has_more = len(scanned) >= sample_cap

        random.shuffle(tracks)
        return {
            "tracks": tracks,
            "cursor": cursor,
            "next_cursor": next_cursor if (has_more and next_cursor) else None,
            "has_more": bool(has_more and next_cursor),
            "limit": limit,
            "hq_mix": hq_mix,
            "deep_mix": deep_mix,
            "max_views": ceiling,
            "min_views": floor,
            "require_free": require_free,
            "require_ffp": require_ffp,
            "prolific": bool(require_prolific),
            "max_age_months": max_age_months,
            "published_after": published_after,
        }
    finally:
        if prolific_attached:
            _detach_prolific(conn)
        conn.close()


def build_queue(
    genre_id: str,
    *,
    max_views: int = DEFAULT_MAX_VIEWS,
    limit: int = QUEUE_BATCH,
) -> list[dict]:
    """Backward-compatible: first page of the station mix."""
    return build_queue_page(genre_id, max_views=max_views, limit=limit)["tracks"]


def _public_track(t: dict) -> dict:
    """Player payload strips exact view counts."""
    return {k: v for k, v in t.items() if k != "views"}


def load_warm_queue() -> dict[str, Any] | None:
    """Read seed playlist from disk (instant even when SQLite is locked/slow)."""
    try:
        if not WARM_QUEUE_PATH.is_file():
            return None
        raw = json.loads(WARM_QUEUE_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict):
        return None
    tracks = raw.get("tracks")
    if not isinstance(tracks, list) or not tracks:
        return None
    cleaned = []
    for t in tracks:
        if not isinstance(t, dict):
            continue
        vid = t.get("video_id")
        if not vid or not isinstance(vid, str) or len(vid) < 6:
            continue
        cleaned.append(
            {
                "video_id": vid,
                "title": t.get("title") or "",
                "channel_name": t.get("channel_name") or "",
                "url": t.get("url") or f"https://youtube.com/watch?v={vid}",
                "published_time": t.get("published_time"),
            }
        )
    if not cleaned:
        return None
    return {
        "genre": raw.get("genre") or "all",
        "tier": raw.get("tier") or DEFAULT_VIEW_TIER_ID,
        "max_views": int(raw.get("max_views") or DEFAULT_MAX_VIEWS),
        "min_views": int(raw.get("min_views") or DEFAULT_MIN_VIEWS),
        "tracks": cleaned,
        "built_at": raw.get("built_at"),
        "source": raw.get("source") or "file",
    }


def save_warm_queue(tracks: list[dict], *, source: str = "db") -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "genre": "all",
        "tier": DEFAULT_VIEW_TIER_ID,
        "min_views": DEFAULT_MIN_VIEWS,
        "max_views": DEFAULT_MAX_VIEWS,
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": source,
        "count": len(tracks),
        "tracks": [_public_track(t) for t in tracks],
    }
    tmp = WARM_QUEUE_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(WARM_QUEUE_PATH)
    return WARM_QUEUE_PATH


def _build_warm_via_genres(conn: sqlite3.Connection, limit: int) -> list[dict]:
    """
    Fast warm seed using idx_beats_genre_views (works before views-only index exists).
    Pulls a slice from each HQ genre so All startup isn't a 5M-row SCAN.
    """
    n_g = max(1, len(HQ_MIX_DB_GENRES))
    per = max(4, (limit + n_g - 1) // n_g + 2)
    merged: list[sqlite3.Row] = []
    seen: set[str] = set()
    for g in HQ_MIX_DB_GENRES:
        chunk = _fetch_by_genres_page(
            conn,
            [g],
            DEFAULT_MAX_VIEWS,
            per,
            None,
            min_views=DEFAULT_MIN_VIEWS,
        )
        for row in chunk:
            vid = row["video_id"]
            if vid in seen:
                continue
            seen.add(vid)
            merged.append(row)
    random.shuffle(merged)
    return _rows_to_tracks(merged[:limit])


def build_warm_queue(*, limit: int = WARM_QUEUE_SIZE) -> dict[str, Any]:
    """
    Build a small All-station playlist for cold start.

    Prefers deep catalog when idx_beats_views_vid exists; otherwise genre-indexed
    HQ slices (still representative of ≤50k) so we never block on a full SCAN.
    """
    limit = max(10, min(int(limit), 80))
    if not DB_PATH.exists():
        return {"tracks": [], "source": "missing_db"}

    conn = connect()
    try:
        views_idx = INDEX_VIEWS_VID not in missing_radio_indexes(conn)

        def _pull() -> list[dict]:
            if views_idx:
                rows = _fetch_deep_catalog_page(
                    conn,
                    DEFAULT_MAX_VIEWS,
                    limit,
                    None,
                    min_views=DEFAULT_MIN_VIEWS,
                )
                tracks = _rows_to_tracks(rows)
                random.shuffle(tracks)
                return tracks
            return _build_warm_via_genres(conn, limit)

        tracks = _with_retry(_pull) or []
        source = "deep_catalog" if views_idx else "hq_genres"
        if tracks:
            save_warm_queue(tracks, source=source)
        return {"tracks": tracks, "source": source, "path": str(WARM_QUEUE_PATH)}
    finally:
        conn.close()


def warm_queue_response(
    *,
    limit: int | None = None,
    shuffle: bool = True,
) -> dict[str, Any] | None:
    """Shape a /api/queue-compatible payload from the on-disk warm file."""
    warm = load_warm_queue()
    if not warm:
        return None
    tracks = list(warm["tracks"])
    if shuffle:
        random.shuffle(tracks)
    if limit is not None:
        tracks = tracks[: max(1, min(int(limit), 200))]
    return {
        "genre": "all",
        "tier": warm.get("tier") or DEFAULT_VIEW_TIER_ID,
        "max_views": warm.get("max_views", DEFAULT_MAX_VIEWS),
        "min_views": warm.get("min_views", DEFAULT_MIN_VIEWS),
        "is_free": False,
        "free_for_profit": False,
        "hq_mix": False,
        "deep_mix": True,
        "count": len(tracks),
        "limit": len(tracks),
        "cursor": None,
        "next_cursor": None,
        "has_more": True,
        "tracks": tracks,
        "warm": True,
        "warm_source": warm.get("source"),
        "warm_built_at": warm.get("built_at"),
    }
