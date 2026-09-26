"""Fill Jev judgment columns on beats, without changing the keyword genre.

Scope, in order:
1. Rows the keyword tagger never labeled (genre IS NULL), any view count.
2. Underground rows in the radio rotation (1–50,000 views).
3. Every other keyword genre in that same view range.

Each row is one System One call. subgenre and commercial_use are asked
together. Results land in jev_genre, jev_genre_confidence, and commercial_use.
The existing genre column stays as it is.

The run is resumable: jev_sweep_checkpoint.json is the cursor, and rows with
jev_tagged_at set are skipped.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import signal
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

from typesafe_sdk import (
    AsyncTypeSafeClient,
    Choice,
    Noul,
    RetryPolicy,
    TypeSafeAPIError,
    TypeSafeAuthenticationError,
    TypeSafeError,
)

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "typebeats.db"
CHECKPOINT_PATH = ROOT / "jev_sweep_checkpoint.json"
LOCK_PATH = ROOT / "jev_sweep.pid"
LOG_PATH = ROOT / "jev_sweep.log"

VIEW_MIN = 1
VIEW_MAX = 50_000

RADIO_GENRES = (
    "Plugg/Pluggnb",
    "Rage/Opium",
    "Experimental/Glitch",
    "Drill",
    "Ambient/Cloud",
    "Dark/Aggressive",
    "Boom Bap/Old School",
)

QUESTIONS = {
    "subgenre": Choice(
        instructions=(
            "Which station best fits this YouTube type-beat listing, using `title` and `channel`? "
            "Choose other when it is not a beat in one of these styles, or when the style is unclear."
        ),
        criteria={
            "plugg": "Plugg or pluggnb, including MexikoDro, CashCache, or a dreamy detuned trap bounce.",
            "rage": "Rage or opium trap. Playboi Carti, Yeat, Ken Carson, Destroy Lonely, F1lthy, or an explicit rage beat.",
            "experimental": "Experimental, sigilkore, hexd, glitchcore, drain, or scenecore.",
            "drill": "Drill that is not specifically UK drill: NY drill, Chicago drill, or generic drill.",
            "uk_drill": "UK drill. Sliding 808s or UK rappers such as Central Cee, Headie One, or Digga D.",
            "ambient": "Ambient, cloud rap, ethereal, or spacey, including a Clams Casino style.",
            "dark": "Dark, horror, or aggressive trap, including phonk, when it is not mainly rage or drill.",
            "boom_bap": "Boom bap, 90s, old school, or lo-fi east-coast hip-hop.",
            "melodic": "Melodic or emo trap led by guitar, piano, sad, or heartbreak mood, and not mainly boom bap or plugg.",
            "jersey": "Jersey club or jerk.",
            "grime": "Grime, including Skepta, Stormzy, Wiley, or Dizzee, or an explicit grime beat.",
            "uk_garage": "UK garage, 2-step, or speed garage.",
            "afroswing": "Afroswing, afro trap, or UK afrobeats-adjacent swing.",
            "road_rap": "UK road rap that is not grime or drill.",
            "other": "None of these stations is a clear fit.",
        },
    ),
    "commercial_use": Noul(
        instructions=(
            "Does `title` grant commercial or free-for-profit use of this beat?"
        ),
        criteria={
            "true": "The title allows commercial use, free for profit, or an equivalent license.",
            "false": "The title does not grant commercial use. Non-profit use, or no license mention, is a no.",
        },
    ),
}

COLUMNS = (
    "jev_genre TEXT",
    "jev_genre_confidence REAL",
    "commercial_use REAL",
    "jev_model TEXT",
    "jev_tagged_at TEXT",
    "jev_error TEXT",
)

log = logging.getLogger("jev_sweep")


@dataclass
class Cursor:
    phase: str
    genre: str | None
    views: int
    video_id: str
    tagged: int = 0
    errors: int = 0

    def to_json(self) -> dict:
        return {
            "phase": self.phase,
            "genre": self.genre,
            "views": self.views,
            "video_id": self.video_id,
            "tagged": self.tagged,
            "errors": self.errors,
        }

    @classmethod
    def load(cls) -> Cursor:
        if not CHECKPOINT_PATH.is_file():
            return cls("untagged", None, -1, "")
        raw = json.loads(CHECKPOINT_PATH.read_text())
        return cls(
            phase=raw["phase"],
            genre=raw.get("genre"),
            views=int(raw["views"]),
            video_id=str(raw["video_id"]),
            tagged=int(raw.get("tagged") or 0),
            errors=int(raw.get("errors") or 0),
        )

    def save(self) -> None:
        tmp = CHECKPOINT_PATH.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self.to_json()))
        tmp.replace(CHECKPOINT_PATH)


@dataclass
class Tagged:
    video_id: str
    genre: str
    confidence: float
    commercial: float
    model: str


@dataclass
class RowFailure:
    video_id: str
    message: str
    retryable: bool
    credits: bool = False


def load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip().removeprefix("export ").strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def ensure_schema(conn: sqlite3.Connection) -> None:
    existing = {row[1] for row in conn.execute("PRAGMA table_info(beats)")}
    for column in COLUMNS:
        name = column.split()[0]
        if name in existing:
            continue
        conn.execute(f"ALTER TABLE beats ADD COLUMN {column}")
    conn.commit()


def acquire_lock() -> None:
    if LOCK_PATH.is_file():
        try:
            pid = int(LOCK_PATH.read_text().strip())
        except ValueError:
            pid = None
        if pid is not None:
            try:
                os.kill(pid, 0)
            except OSError:
                pass
            else:
                raise SystemExit(f"jev_sweep is already running (pid {pid})")
    LOCK_PATH.write_text(str(os.getpid()))


def release_lock() -> None:
    if LOCK_PATH.is_file():
        try:
            if int(LOCK_PATH.read_text().strip()) == os.getpid():
                LOCK_PATH.unlink()
        except (ValueError, OSError):
            pass


def fetch_batch(conn: sqlite3.Connection, cursor: Cursor, limit: int) -> list[sqlite3.Row]:
    params: list = []
    if cursor.phase == "untagged":
        where = "genre IS NULL AND views >= ?"
        params.append(VIEW_MIN)
    elif cursor.phase == "underground":
        where = "genre = 'Underground' AND views >= ? AND views <= ?"
        params.extend([VIEW_MIN, VIEW_MAX])
    elif cursor.phase == "radio":
        where = "genre = ? AND views >= ? AND views <= ?"
        params.extend([cursor.genre, VIEW_MIN, VIEW_MAX])
    else:
        raise SystemExit(f"unknown phase {cursor.phase}")
    params.extend([cursor.views, cursor.views, cursor.video_id, limit])
    return list(
        conn.execute(
            f"""
            SELECT video_id, title, channel_name, views
            FROM beats
            WHERE {where}
              AND jev_tagged_at IS NULL
              AND jev_error IS NULL
              AND video_id IS NOT NULL
              AND (views > ? OR (views = ? AND video_id > ?))
            ORDER BY views, video_id
            LIMIT ?
            """,
            params,
        )
    )


def advance(cursor: Cursor) -> Cursor | None:
    if cursor.phase == "untagged":
        return Cursor("underground", None, -1, "", cursor.tagged, cursor.errors)
    if cursor.phase == "underground":
        return Cursor("radio", RADIO_GENRES[0], -1, "", cursor.tagged, cursor.errors)
    if cursor.genre is None:
        return Cursor("radio", RADIO_GENRES[0], -1, "", cursor.tagged, cursor.errors)
    index = RADIO_GENRES.index(cursor.genre)
    if index + 1 >= len(RADIO_GENRES):
        return None
    return Cursor("radio", RADIO_GENRES[index + 1], -1, "", cursor.tagged, cursor.errors)


def phase_label(cursor: Cursor) -> str:
    if cursor.phase == "radio":
        return f"radio:{cursor.genre}"
    return cursor.phase


def commit_rows(
    conn: sqlite3.Connection,
    tagged: list[Tagged],
    failures: list[RowFailure],
    cursor: Cursor,
) -> None:
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with conn:
        for row in tagged:
            conn.execute(
                """
                UPDATE beats
                SET jev_genre = ?,
                    jev_genre_confidence = ?,
                    commercial_use = ?,
                    jev_model = ?,
                    jev_tagged_at = ?,
                    jev_error = NULL
                WHERE video_id = ?
                """,
                (
                    row.genre,
                    row.confidence,
                    row.commercial,
                    row.model,
                    now,
                    row.video_id,
                ),
            )
        for row in failures:
            conn.execute(
                "UPDATE beats SET jev_error = ? WHERE video_id = ?",
                (row.message[:400], row.video_id),
            )
    cursor.tagged += len(tagged)
    cursor.errors += len(failures)
    cursor.save()


async def judge(client: AsyncTypeSafeClient, row: sqlite3.Row) -> Tagged | RowFailure:
    state = {"title": row["title"] or "", "channel": row["channel_name"] or ""}
    try:
        response = await client.system_one(state, QUESTIONS)
    except TypeSafeAuthenticationError:
        raise
    except TypeSafeAPIError as exc:
        retryable = exc.status in {408, 429} or (exc.status is not None and exc.status >= 500)
        return RowFailure(
            row["video_id"],
            f"HTTP {exc.status}: {exc}",
            retryable,
            credits=exc.status == 402,
        )
    except (TypeSafeError, TimeoutError, OSError) as exc:
        return RowFailure(row["video_id"], str(exc), True)
    except Exception as exc:
        return RowFailure(row["video_id"], str(exc), True)
    genre = response.choices["subgenre"]
    return Tagged(
        video_id=row["video_id"],
        genre=genre.choice,
        confidence=float(genre.confidence),
        commercial=float(response.nouls["commercial_use"].noul),
        model=response.model,
    )


async def run(args: argparse.Namespace) -> None:
    load_dotenv(ROOT / ".env")
    conn = connect()
    try:
        ensure_schema(conn)
        cursor = Cursor.load()
        client_retry = RetryPolicy(
            max_retries=5,
            backoff_initial=1.0,
            backoff_max=20.0,
            timeout=180.0,
        )
        started = time.monotonic()
        tagged_this_process = 0
        retry_streak = 0
        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop.set)

        log.info("resume %s cursor views=%s video_id=%s", phase_label(cursor), cursor.views, cursor.video_id)
        async with AsyncTypeSafeClient(timeout=25.0, retry=client_retry) as client:
            while not stop.is_set():
                if args.limit and tagged_this_process >= args.limit:
                    log.info("reached --limit %s", args.limit)
                    return
                room = args.concurrency
                if args.limit:
                    room = min(room, args.limit - tagged_this_process)
                rows = fetch_batch(conn, cursor, room)
                if not rows:
                    if cursor.phase == args.through:
                        log.info("finished through %s tagged=%s errors=%s", args.through, cursor.tagged, cursor.errors)
                        cursor.save()
                        return
                    nxt = advance(cursor)
                    if nxt is None:
                        log.info("sweep finished tagged=%s errors=%s", cursor.tagged, cursor.errors)
                        cursor.save()
                        return
                    log.info("phase done, next %s", phase_label(nxt))
                    cursor = nxt
                    cursor.save()
                    continue

                judged = await asyncio.gather(*(judge(client, row) for row in rows))
                tagged: list[Tagged] = []
                permanent: list[RowFailure] = []
                retryable: RowFailure | None = None
                credits: RowFailure | None = None
                last_done: sqlite3.Row | None = None
                for row, result in zip(rows, judged):
                    if isinstance(result, RowFailure) and result.credits:
                        credits = result
                        break
                    if isinstance(result, RowFailure) and result.retryable:
                        retryable = result
                        break
                    if isinstance(result, RowFailure):
                        permanent.append(result)
                        log.warning("skip %s %s", row["video_id"], result.message)
                    else:
                        tagged.append(result)
                    last_done = row

                if tagged or permanent:
                    if last_done is not None:
                        cursor.views = int(last_done["views"])
                        cursor.video_id = last_done["video_id"]
                    commit_rows(conn, tagged, permanent, cursor)
                    tagged_this_process += len(tagged)
                    elapsed = max(time.monotonic() - started, 0.001)
                    sample = tagged[-1] if tagged else None
                    log.info(
                        "%s +%d this_run=%d total=%d errors=%d rate=%.2f/s %s",
                        phase_label(cursor),
                        len(tagged),
                        tagged_this_process,
                        cursor.tagged,
                        cursor.errors,
                        tagged_this_process / elapsed,
                        (
                            f"genre={sample.genre} commercial={sample.commercial:.3f}"
                            if sample
                            else "no successes"
                        ),
                    )

                if credits is not None:
                    log.error("out of TypeSafe credits on %s; stopping without skipping later rows", credits.video_id)
                    return
                if retryable is None:
                    retry_streak = 0
                    continue
                retry_streak += 1
                log.warning(
                    "retryable failure on %s (%s), streak %s",
                    retryable.video_id,
                    retryable.message,
                    retry_streak,
                )
                if retry_streak >= 8:
                    log.error("stopping after repeated retryable failures; rerun to resume")
                    return
                await asyncio.sleep(min(60.0, 2.0 * retry_streak))

        log.info("stopped after signal; resume with the same command")
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Tag beats with Jev genre and commercial-use judgments.")
    parser.add_argument("--concurrency", type=int, default=6, help="rows evaluated at once")
    parser.add_argument("--limit", type=int, default=0, help="stop after this many successes in this process")
    parser.add_argument(
        "--through",
        choices=("untagged", "underground", "radio"),
        default="radio",
        help="stop after this phase",
    )
    args = parser.parse_args()
    if args.concurrency < 1:
        raise SystemExit("--concurrency must be at least 1")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(LOG_PATH),
            logging.StreamHandler(),
        ],
    )
    logging.getLogger("typesafe_sdk").setLevel(logging.WARNING)
    logging.getLogger("httpx2").setLevel(logging.WARNING)
    acquire_lock()
    try:
        asyncio.run(run(args))
    finally:
        release_lock()


if __name__ == "__main__":
    main()
