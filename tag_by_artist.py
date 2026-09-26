#!/usr/bin/env python3
"""Retag beats.genre = 'Underground' from artist names in the title.

Layers, first match wins per alias:
  1. Hand overrides for type-beat names public tables miss or get wrong.
  2. KoryJCampbell/dj-crates-tools artist→subgenre tables (local extract).
  3. Wikidata is not used: no local extract, and a fresh download would stall the scan.

No network. No TypeSafe/Jev.

Updates rows still marked Underground, and Hip-Hop rows whose artist maps
to a tighter source style. Never overwrites a tighter genre (Trap, Drill,
R&B, and the rest) with a broader one.
"""

from __future__ import annotations

import json
import re
import sqlite3
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "typebeats.db"
DJCRATES_PATH = ROOT / "data" / "djcrates_artist_genres.json"

BATCH = 4000
READ_BATCH = 8000

# Layer 1. Overrides win over the mined table.
HAND_OVERRIDES: dict[str, str] = {
    # R&B
    "chris brown": "R&B",
    "bryson tiller": "R&B",
    "partynextdoor": "R&B",
    "party next door": "R&B",
    "sza": "R&B",
    "summer walker": "R&B",
    "brent faiyaz": "R&B",
    "6lack": "R&B",
    "the weeknd": "R&B",
    "weeknd": "R&B",
    "tory lanez": "R&B",
    "kehlani": "R&B",
    "giveon": "R&B",
    "jhene aiko": "R&B",
    "ella mai": "R&B",
    "frank ocean": "R&B",
    # Melodic Trap (dataset often files these under generic Trap)
    "gunna": "Melodic Trap",
    "lil baby": "Melodic Trap",
    "don toliver": "Melodic Trap",
    "toosii": "Melodic Trap",
    "rod wave": "Melodic Trap",
    "future": "Melodic Trap",
    "young thug": "Melodic Trap",
    "lil tjay": "Melodic Trap",
    "polo g": "Melodic Trap",
    "a boogie": "Melodic Trap",
    "nav": "Melodic Trap",
    "juice wrld": "Melodic Trap",
    # Rage / plugg names the public tables miss
    "sofaygo": "Rage/Opium",
    "so faygo": "Rage/Opium",
    "che": "Rage/Opium",
    "osamason": "Rage/Opium",
    "osama son": "Rage/Opium",
    "kai angel": "Rage/Opium",
    "destroy lonely": "Rage/Opium",
    "yeat": "Rage/Opium",
    "summrs": "Plugg/Pluggnb",
    "autumn": "Plugg/Pluggnb",
    "autumn!": "Plugg/Pluggnb",
    "xavier sobased": "Plugg/Pluggnb",
    "xaviersobased": "Plugg/Pluggnb",
    "nettspend": "Plugg/Pluggnb",
    # Drill / trap-south / Detroit
    "lil durk": "Drill",
    "fivio foreign": "Drill",
    "fivio": "Drill",
    "pop smoke": "Drill",
    "kodak black": "Trap",
    "kodak": "Trap",
    "dababy": "Trap",
    "da baby": "Trap",
    "key glock": "Trap",
    "g herbo": "Trap",
    "21 savage": "Trap",
    "nardo wick": "Trap",
    "moneybagg yo": "Trap",
    "babytron": "Detroit",
    "baby tron": "Detroit",
    "veeze": "Detroit",
    "baby smoove": "Detroit",
    "kasher quon": "Detroit",
    "babyface ray": "Detroit",
    "icewear vezzo": "Detroit",
    "sada baby": "Detroit",
    "rio da yung og": "Detroit",
    "yn jay": "Detroit",
}

# dj-crates-tools stored these hip-hop `sub` labels under genre "Hip-Hop".
# Named styles and coasts stay their own genre. Generic Hip-Hop is only
# used when the source sub is missing or is itself just "Hip-Hop".
# Boom Bap, Old School, Cloud Rap, Trap, and Drill already had station strings.
HIPHOP_SUB_GENRE = {
    "East Coast": "East Coast",
    "Southern": "Southern",
    "West Coast": "West Coast",
    "Midwest": "Midwest",
    "Conscious": "Conscious",
    "Crunk": "Crunk",
    "G-Funk": "G-Funk",
    "Pop Rap": "Pop Rap",
    "Boom Bap": "Boom Bap/Old School",
    "Old School": "Boom Bap/Old School",
    "Cloud Rap": "Ambient/Cloud",
    "Trap": "Trap",
    "Drill": "Drill",
}

# Rows we are allowed to retag. Anything else is already a tighter genre.
RETAG_FROM = ("Hip-Hop", "Underground")

# Whole-clause only. Stops "future bass" or "cheesecake" style false hits.
EXACT_ONLY = frozenset({
    "future", "che", "nav", "yeat", "kodak", "fivio", "veeze", "autumn", "sza", "gunna",
})

QUOTE_RES = (
    re.compile(r'"[^"]*"'),
    re.compile(r"“[^”]*”"),
    re.compile(r"«[^»]*»"),
    re.compile(r"''[^']*''"),
)
SKIP_RE = re.compile(r"\bhow to make\b|\btutorials?\b|\bcompilations?\b")
SPLIT_RE = re.compile(
    r"\s*(?:,|\bx\b|feat\.?|ft\.?|vs\.?)\s*|[×+]|(?:\s*[&]\s*)",
    re.IGNORECASE,
)
TOKEN_RE = re.compile(r"[a-z0-9]+")
YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
TYPEBEAT_RE = re.compile(r"\btype\s*beats?\b")
PROD_TAIL_RE = re.compile(
    r"(?:\((?:prod|produced)[^)]*\)|\b(?:prod|produced)\.?\s*by\b.*$|\|\s*(?:prod|produced)\b.*$)",
    re.IGNORECASE,
)
FREE_TAG_RE = re.compile(
    r"[\[\(\{*]+\s*(?:free(?:\s+for\s+profit)?|not\s+free|sold)\s*[\]\)\}*]+",
    re.IGNORECASE,
)
FILLER = frozenset({
    "type", "beat", "beats", "free", "prod", "produced", "instrumental",
    "instrumentals", "for", "profit", "non", "not", "sold", "exclusive",
    "untagged", "tagged", "official", "full", "download", "instru", "inst",
    "with", "hook", "ft", "feat", "vs", "and", "the", "a", "an", "of", "w",
})

_ALIAS: dict[tuple[str, ...], str] = {}
_SQUEEZE: set[str] = set()
MAX_ALIAS_LEN = 1


def _tokens(alias: str) -> tuple[str, ...]:
    text = alias.lower().replace("$", "s").replace("é", "e").replace("!", "")
    return tuple(TOKEN_RE.findall(text))


def _add_alias(alias: str, genre: str) -> None:
    global MAX_ALIAS_LEN
    parts = _tokens(alias)
    if not parts or len(parts) > 6:
        return
    if len(parts) == 1 and (len(parts[0]) < 2 or parts[0] in FILLER):
        return
    _ALIAS[parts] = genre
    squeezed = "".join(parts)
    _SQUEEZE.add(squeezed)
    if len(parts) > 1:
        _ALIAS[(squeezed,)] = genre
    MAX_ALIAS_LEN = max(MAX_ALIAS_LEN, len(parts), 1)


def _source_genre(row: dict) -> str:
    genre = row["genre"]
    sub = (row.get("sub") or "").strip()
    if genre == "Hip-Hop":
        return HIPHOP_SUB_GENRE.get(sub, genre)
    return genre


def _load_aliases() -> None:
    # Layer 2 first, then layer 1 overwrites.
    if DJCRATES_PATH.is_file():
        rows = json.loads(DJCRATES_PATH.read_text(encoding="utf-8"))
        for row in rows:
            _add_alias(row["name"], _source_genre(row))
    for alias, genre in HAND_OVERRIDES.items():
        _add_alias(alias, genre)


_load_aliases()


def strip_quotes(title: str) -> str:
    s = title
    prev = None
    while prev != s:
        prev = s
        for cre in QUOTE_RES:
            s = cre.sub(" ", s)
    return s


def _clause_genre(clause: str) -> str | None:
    raw = YEAR_RE.sub(" ", clause)
    raw = TYPEBEAT_RE.sub(" ", raw)
    raw = re.sub(r"\binstrumentals?\b", " ", raw)
    tokens = [t for t in TOKEN_RE.findall(raw) if t not in FILLER]
    if not tokens:
        return None
    found: list[str] = []
    i = 0
    while i < len(tokens):
        matched = False
        upper = min(MAX_ALIAS_LEN, len(tokens) - i)
        for length in range(upper, 0, -1):
            window = tuple(tokens[i : i + length])
            genre = _ALIAS.get(window)
            if genre is None:
                continue
            if length == 1 and window[0] in EXACT_ONLY and tuple(tokens) != window:
                continue
            found.append(genre)
            i += length
            matched = True
            break
        if not matched:
            i += 1
    if not found:
        return None
    if len(set(found)) == 1:
        return found[0]
    return ""  # disagree inside the clause


def classify(title: str | None, channel: str | None) -> str | None:
    if not title:
        return None
    text = strip_quotes(title).lower()
    if SKIP_RE.search(text):
        return None
    if channel:
        ch = channel.lower().strip()
        squeezed = "".join(_tokens(ch))
        if ch and squeezed not in _SQUEEZE and len(squeezed) >= 4:
            text = text.replace(ch, " ")
    text = FREE_TAG_RE.sub(" ", text)
    text = PROD_TAIL_RE.sub(" ", text)
    text = TYPEBEAT_RE.sub(" ", text)
    text = re.sub(r"[\[\]\(\)\{\}*_]+", " ", text)
    found: set[str] = set()
    for clause in SPLIT_RE.split(text):
        clause = clause.strip(" -|~:.")
        if not clause:
            continue
        genre = _clause_genre(clause)
        if genre == "":
            return None
        if genre:
            found.add(genre)
    if len(found) == 1:
        return next(iter(found))
    return None


def _self_check() -> None:
    cases = [
        ('[FREE] Lil Baby Type Beat - "No Hope"', "", "Melodic Trap"),
        ('Che Type Beat "Rooms"', "", "Rage/Opium"),
        ("Summrs x Autumn! Type Beat", "", "Plugg/Pluggnb"),
        ("Che x Summrs Type Beat", "", None),
        ("future bass type beat", "", None),
        ('Future Type Beat "Price Tags"', "", "Melodic Trap"),
        ('Kodak Black Type Beat "x"', "", "Trap"),
        ("black type beat", "", None),
        ("Nas Type Beat", "", "Boom Bap/Old School"),
        ("How To Make A Drake Type Beat Tutorial", "", None),
        ('"R&B" Drake Type Beat', "", "Southern"),
        ("Kendrick Lamar Type Beat", "", "West Coast"),
        ("J. Cole Type Beat", "", "Conscious"),
        ("Lil Jon Type Beat", "", "Crunk"),
        ("Wizkid Type Beat", "", "Afropop"),
        ("Burna Boy Type Beat", "", "Afrofusion"),
        ("Sean Paul Type Beat", "", "Ragga"),
        ("Parliament Type Beat", "", "Psychedelic Soul"),
        ("Rick James Type Beat", "", "Funk"),
        ("Veeze Type Beat", "", "Detroit"),
        ("OsamaSon x SoFaygo Type Beat", "", "Rage/Opium"),
        ("Xavier Sobased Type Beat", "", "Plugg/Pluggnb"),
        ("Kai Angel Type Beat", "", "Rage/Opium"),
    ]
    failed = 0
    for title, channel, expected in cases:
        got = classify(title, channel)
        if got != expected:
            failed += 1
            print(f"FAIL {title!r} -> {got!r} expected {expected!r}")
    if failed:
        raise SystemExit(f"{failed} classifier checks failed")
    print(f"classifier checks ok ({len(cases)}) aliases {len(_ALIAS)}", flush=True)


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), timeout=120)
    conn.execute("PRAGMA busy_timeout=120000")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-262144")
    conn.execute("PRAGMA temp_store=MEMORY")
    return conn


def run() -> None:
    _self_check()
    if not DJCRATES_PATH.is_file():
        raise SystemExit(f"missing {DJCRATES_PATH}")
    conn = _connect()
    counts: Counter[str] = Counter()
    pending: list[tuple[str, str, str]] = []
    scanned = 0
    moved = 0
    started = time.time()
    # One pass per source bucket so a tighter write is not scanned again.
    buckets = list(RETAG_FROM)

    def flush() -> None:
        nonlocal pending
        if not pending:
            return
        conn.executemany(
            "UPDATE beats SET genre = ? WHERE video_id = ? AND genre = ?",
            pending,
        )
        conn.commit()
        # Let the WAL shrink between batches so a long scan cannot fill the disk.
        conn.execute("PRAGMA wal_checkpoint(PASSIVE)")
        pending = []

    try:
        # Short reads. A single open scan pins the WAL and filled the disk.
        for bucket in buckets:
            # Keyset on (views, video_id), which idx_beats_genre_views_vid covers.
            # Ordering by rowid sorts the whole genre and filled a temp b-tree.
            last_views = -1
            last_vid = ""
            while True:
                rows = conn.execute(
                    """
                    SELECT video_id, title, channel_name, views
                    FROM beats
                    WHERE genre = ?
                      AND (views, video_id) > (?, ?)
                    ORDER BY views, video_id
                    LIMIT ?
                    """,
                    (bucket, last_views, last_vid, READ_BATCH),
                ).fetchall()
                if not rows:
                    break
                last_vid = rows[-1][0]
                last_views = rows[-1][3]
                for video_id, title, channel, _views in rows:
                    scanned += 1
                    genre = classify(title, channel)
                    # Leave generic Hip-Hop in place. Never write Underground
                    # or Hip-Hop over a row, and never broaden a tighter tag.
                    if not genre or genre in RETAG_FROM or genre == bucket:
                        continue
                    pending.append((genre, video_id, bucket))
                    counts[genre] += 1
                    moved += 1
                    if len(pending) >= BATCH:
                        flush()
                if scanned % 200000 < READ_BATCH:
                    elapsed = max(time.time() - started, 0.001)
                    print(
                        f"{bucket} scanned {scanned:,} moved {moved:,} ({scanned / elapsed:,.0f} rows/s)",
                        flush=True,
                    )
        flush()
        remaining = conn.execute(
            "SELECT COUNT(*) FROM beats WHERE genre = 'Underground'"
        ).fetchone()[0]
        hiphop_left = conn.execute(
            "SELECT COUNT(*) FROM beats WHERE genre = 'Hip-Hop'"
        ).fetchone()[0]
    finally:
        conn.close()

    elapsed = time.time() - started
    print(f"done in {elapsed:,.0f}s  scanned {scanned:,}  moved {moved:,}")
    print("layers: 1 hand overrides, 2 dj-crates-tools; wikidata skipped (no local extract)")
    print("hip-hop source subs promoted to their own genre:")
    for sub, genre in HIPHOP_SUB_GENRE.items():
        if sub != genre and genre in ("Boom Bap/Old School", "Ambient/Cloud", "Trap", "Drill"):
            continue
        print(f"  {sub} -> {genre}")
    print("moved per genre:")
    for genre, n in counts.most_common():
        print(f"  {genre}: {n:,}")
    print(f"Hip-Hop remaining: {hiphop_left:,}")
    print(f"Underground remaining: {remaining:,}")


if __name__ == "__main__":
    run()
