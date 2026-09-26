#!/usr/bin/env python3
"""
Producer harvester v2 — scrape missing type beats for known producers
within a fixed date window (default: 2026-03-27 → 2026-08-05).

Does NOT replace producer_harvester.py.

Workflow vs old tools
---------------------
- scraper.py: style/artist queries from queries.txt (matrix search).
- producer_harvester.py: producers from DB channel_name; marks them done in
  harvested_producers.txt; no date-window filter on search.
- producer_harvester_v2.py (this): producers FROM harvested_producers.txt;
  YouTube after:/before: date bounds; own checkpoint file for resumability;
  INSERT OR IGNORE so existing rows are not overwritten.

Examples
--------
  # Smoke: first 5 producers, no DB writes
  python producer_harvester_v2.py --limit 5 --dry-run

  # Smoke: first 5 producers, write to DB
  python producer_harvester_v2.py --limit 5

  # Full run (resumable via checkpoint)
  python producer_harvester_v2.py

  # Priority pass (same checkpoint — safe resume / switch mid-run):
  #   1. Ctrl-C the current run (finished producers stay checkpointed)
  #   2. python build_producer_priority.py
  #   3. Restart with one of:
  python producer_harvester_v2.py --priority --fast-empty
  python producer_harvester_v2.py --priority-top --fast-empty
  # Optional: --known-only skips cold names never seen as channel_name.

  # Custom window / paths
  python producer_harvester_v2.py \\
      --after 2026-03-27 --before 2026-08-06 \\
      --producers harvested_producers.txt \\
      --checkpoint harvester_v2_checkpoint.txt
"""

from __future__ import annotations

import argparse
import os
import random
import re
import sqlite3
import sys
import time
from datetime import datetime, timedelta
from typing import Iterable, Optional, Set

import scrapetube

# ---------------------------------------------------------------------------
# Defaults (CLI can override)
# ---------------------------------------------------------------------------
DEFAULT_DB = "typebeats.db"
DEFAULT_PRODUCERS = "harvested_producers.txt"
DEFAULT_PRIORITY_PRODUCERS = "harvested_producers_priority.txt"
DEFAULT_PRIORITY_TOP = "harvested_producers_priority_top20k.txt"
DEFAULT_CHECKPOINT = "harvester_v2_checkpoint.txt"
DEFAULT_AFTER = "2026-03-27"
# YouTube `before:` is exclusive → day after inclusive end date
DEFAULT_BEFORE = "2026-08-06"
DEFAULT_SEARCH_LIMIT = 50
DEFAULT_MAX_VIEWS = 100_000
DEFAULT_KNOWN_STREAK = 5
DEFAULT_SLEEP_MIN = 0.4
DEFAULT_SLEEP_MAX = 1.2
DEFAULT_PRODUCER_PAUSE_MIN = 0.8
DEFAULT_PRODUCER_PAUSE_MAX = 2.0
# Used with --fast-empty when a producer yields 0 new inserts
DEFAULT_EMPTY_PAUSE_MIN = 0.15
DEFAULT_EMPTY_PAUSE_MAX = 0.4
DEFAULT_SCRAPETUBE_SLEEP = 1.0
DEFAULT_FAST_SCRAPETUBE_SLEEP = 0.35


def get_absolute_date(relative_text, scrape_date_str: str) -> str:
    """Convert YouTube relative publish text to YYYY-MM-DD."""
    if re.match(r"\d{4}-\d{2}-\d{2}", str(relative_text)):
        return str(relative_text)

    try:
        scrape_date = datetime.strptime(scrape_date_str, "%Y-%m-%d")
    except ValueError:
        scrape_date = datetime.now()

    ts = str(relative_text).lower()
    match = re.search(r"(\d+)\s*(year|yr|month|mo|week|wk|day|hour|min|sec)", ts)
    if not match:
        return scrape_date.strftime("%Y-%m-%d")

    n = int(match.group(1))
    unit = match.group(2)
    days = 0
    if unit in ("year", "yr"):
        days = n * 365
    elif unit in ("month", "mo"):
        days = n * 30
    elif unit in ("week", "wk"):
        days = n * 7
    elif unit == "day":
        days = n

    return (scrape_date - timedelta(days=days)).strftime("%Y-%m-%d")


def extract_views(vid: dict) -> int:
    v_text = vid.get("viewCountText", {}).get("simpleText") or "0"
    raw_text = v_text.lower().replace(",", "").replace(" ", "").replace("\xa0", "")
    multipliers = {"k": 1000, "m": 1_000_000}
    multiplier = 1
    for key, val in multipliers.items():
        if key in raw_text:
            multiplier = val
            break
    nums = re.findall(r"(\d+\.?\d*)", raw_text)
    try:
        return int(float(nums[0]) * multiplier) if nums else 0
    except (ValueError, IndexError):
        return 0


def safe_title(vid: dict) -> str:
    try:
        return vid["title"]["runs"][0]["text"]
    except (KeyError, IndexError, TypeError):
        return ""


def safe_channel(vid: dict) -> str:
    try:
        return vid["longBylineText"]["runs"][0]["text"]
    except (KeyError, IndexError, TypeError):
        return ""


def load_lines(path: str) -> list[str]:
    if not os.path.exists(path):
        return []
    out: list[str] = []
    seen: Set[str] = set()
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            name = line.strip()
            if not name or name in seen:
                continue
            seen.add(name)
            out.append(name)
    return out


def load_checkpoint(path: str) -> Set[str]:
    return set(load_lines(path))


def append_checkpoint(path: str, producer: str) -> None:
    with open(path, "a", encoding="utf-8") as f:
        f.write(producer + "\n")


def ensure_schema(cursor: sqlite3.Cursor) -> None:
    """Match live typebeats.db columns used by scraper / harvester."""
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS beats (
            video_id TEXT PRIMARY KEY,
            title TEXT,
            artist_style TEXT,
            channel_name TEXT,
            url TEXT,
            views INTEGER,
            published_time TEXT,
            scraped_at TEXT,
            genre TEXT,
            is_free INTEGER,
            free_for_profit INTEGER
        )
        """
    )


def build_query(producer: str, after: str, before: Optional[str]) -> str:
    # Quote producer for phrase-ish search; date ops per PRD / YouTube search.
    q = f'"{producer}" type beat after:{after}'
    if before:
        q += f" before:{before}"
    return q


def in_date_window(pub_date: str, after: str, before: Optional[str]) -> bool:
    """Inclusive after; exclusive before (YouTube-style) when before is set."""
    if not re.match(r"\d{4}-\d{2}-\d{2}", pub_date):
        return True  # keep unknowns; search already date-filtered
    if pub_date < after:
        return False
    if before and pub_date >= before:
        return False
    return True


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Harvest missing type beats for producers in a date window."
    )
    p.add_argument("--db", default=DEFAULT_DB, help="SQLite DB path")
    p.add_argument(
        "--producers",
        default=DEFAULT_PRODUCERS,
        help="Producer list file (one name per line). Default: harvested_producers.txt",
    )
    p.add_argument(
        "--priority",
        action="store_true",
        help=f"Use {DEFAULT_PRIORITY_PRODUCERS} (from build_producer_priority.py)",
    )
    p.add_argument(
        "--priority-top",
        action="store_true",
        help=f"Use {DEFAULT_PRIORITY_TOP} (top ~20k scored producers only)",
    )
    p.add_argument(
        "--checkpoint",
        default=DEFAULT_CHECKPOINT,
        help="Append-only file of completed producers (resumability)",
    )
    p.add_argument("--after", default=DEFAULT_AFTER, help="Inclusive start YYYY-MM-DD")
    p.add_argument(
        "--before",
        default=DEFAULT_BEFORE,
        help="Exclusive end YYYY-MM-DD (default day after Aug 5 → covers through 2026-08-05)",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Process at most N pending producers (0 = all). Use for smoke tests.",
    )
    p.add_argument(
        "--search-limit",
        type=int,
        default=DEFAULT_SEARCH_LIMIT,
        help="Max videos per producer search",
    )
    p.add_argument("--max-views", type=int, default=DEFAULT_MAX_VIEWS)
    p.add_argument(
        "--known-streak",
        type=int,
        default=DEFAULT_KNOWN_STREAK,
        help="Stop a producer early after this many consecutive known video_ids",
    )
    p.add_argument(
        "--known-only",
        action="store_true",
        help="Skip producers never seen as channel_name in the DB (cold names)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Search and log only; no DB writes / no checkpoint",
    )
    p.add_argument(
        "--shuffle",
        action="store_true",
        help="Randomize pending producer order",
    )
    p.add_argument(
        "--no-sleep",
        action="store_true",
        help="Disable stealth sleeps (not recommended)",
    )
    p.add_argument(
        "--fast-empty",
        action="store_true",
        help=(
            "Shorter inter-producer pause when a search yields 0 new inserts, "
            "and slightly lower scrapetube sleep (modest speedup, mild ban risk)"
        ),
    )
    p.add_argument(
        "--producer-pause-min",
        type=float,
        default=DEFAULT_PRODUCER_PAUSE_MIN,
        help="Min sleep between producers (default 0.8s)",
    )
    p.add_argument(
        "--producer-pause-max",
        type=float,
        default=DEFAULT_PRODUCER_PAUSE_MAX,
        help="Max sleep between producers (default 2.0s)",
    )
    p.add_argument(
        "--empty-pause-min",
        type=float,
        default=DEFAULT_EMPTY_PAUSE_MIN,
        help="With --fast-empty: min pause after 0-result producer",
    )
    p.add_argument(
        "--empty-pause-max",
        type=float,
        default=DEFAULT_EMPTY_PAUSE_MAX,
        help="With --fast-empty: max pause after 0-result producer",
    )
    p.add_argument(
        "--scrapetube-sleep",
        type=float,
        default=None,
        help="scrapetube.get_search sleep seconds (default 1.0; 0.35 with --fast-empty)",
    )
    p.add_argument(
        "--offset",
        type=int,
        default=0,
        help="Skip first N pending producers after checkpoint filter",
    )
    args = p.parse_args(list(argv) if argv is not None else None)
    if args.priority and args.priority_top:
        p.error("Use only one of --priority / --priority-top")
    if args.priority_top:
        args.producers = DEFAULT_PRIORITY_TOP
    elif args.priority:
        args.producers = DEFAULT_PRIORITY_PRODUCERS
    if args.scrapetube_sleep is None:
        args.scrapetube_sleep = (
            DEFAULT_FAST_SCRAPETUBE_SLEEP
            if args.fast_empty
            else DEFAULT_SCRAPETUBE_SLEEP
        )
    return args


def stealth_sleep(lo: float, hi: float, disabled: bool) -> None:
    if disabled:
        return
    if hi < lo:
        hi = lo
    time.sleep(random.uniform(lo, hi))


def known_channel_names(db_path: str) -> Set[str]:
    conn = sqlite3.connect(db_path, timeout=60)
    try:
        rows = conn.execute(
            "SELECT DISTINCT channel_name FROM beats "
            "WHERE channel_name IS NOT NULL AND channel_name != ''"
        )
        return {r[0] for r in rows}
    finally:
        conn.close()


def run(args: argparse.Namespace) -> int:
    producers = load_lines(args.producers)
    if not producers:
        print(f"❌ No producers found in {args.producers}")
        if args.priority or args.priority_top:
            print("   Run: python build_producer_priority.py")
        return 1

    done = load_checkpoint(args.checkpoint)
    pending = [p for p in producers if p not in done]

    if args.known_only:
        print("🔍 loading known channel_name set for --known-only…")
        known = known_channel_names(args.db)
        before = len(pending)
        pending = [p for p in pending if p in known]
        print(f"   kept {len(pending)}/{before} (dropped {before - len(pending)} cold)")

    if args.shuffle:
        random.shuffle(pending)
    if args.offset:
        pending = pending[args.offset :]
    if args.limit and args.limit > 0:
        pending = pending[: args.limit]

    print("=== producer_harvester_v2 ===")
    print(f"📁 producers file : {args.producers} ({len(producers)} unique)")
    print(f"✅ checkpoint     : {args.checkpoint} ({len(done)} done)")
    print(f"🚀 pending batch  : {len(pending)}")
    print(f"📅 window         : after:{args.after} before:{args.before}")
    print(f"🗄️  db             : {args.db}")
    print(f"🧪 dry_run        : {args.dry_run}")
    print(f"⚡ fast_empty     : {args.fast_empty} (scrapetube_sleep={args.scrapetube_sleep})")
    print(f"🎯 known_only     : {args.known_only}")
    print()

    if not pending:
        print("Nothing to do — all producers already checkpointed.")
        return 0

    conn = None
    cursor = None
    if not args.dry_run:
        conn = sqlite3.connect(args.db)
        cursor = conn.cursor()
        ensure_schema(cursor)
        conn.commit()

    total_new = 0
    total_seen = 0
    total_skipped_date = 0
    errors = 0
    started = time.time()

    for i, producer in enumerate(pending, 1):
        query = build_query(producer, args.after, args.before)
        print(f"\n[{i}/{len(pending)}] 🚜 {producer}")
        print(f"   🔎 {query}")

        new_for_producer = 0
        consecutive_knowns = 0

        try:
            videos = scrapetube.get_search(
                query,
                limit=args.search_limit,
                sleep=0 if args.no_sleep else args.scrapetube_sleep,
                sort_by="upload_date",
            )

            for vid in videos:
                total_seen += 1
                video_id = vid.get("videoId")
                if not video_id:
                    continue

                title = safe_title(vid)
                if "type beat" not in title.lower():
                    continue

                pub_raw = vid.get("publishedTimeText", {}).get("simpleText") or "Unknown"
                scrape_date_str = datetime.now().strftime("%Y-%m-%d")
                pub_date = get_absolute_date(pub_raw, scrape_date_str)
                if not in_date_window(pub_date, args.after, args.before):
                    total_skipped_date += 1
                    continue

                views = extract_views(vid)
                if not (0 < views <= args.max_views):
                    continue

                if cursor is not None:
                    cursor.execute(
                        "SELECT 1 FROM beats WHERE video_id=?", (video_id,)
                    )
                    if cursor.fetchone():
                        consecutive_knowns += 1
                        # Refresh views lightly (same as v1)
                        cursor.execute(
                            "UPDATE beats SET views=?, scraped_at=? WHERE video_id=?",
                            (views, scrape_date_str, video_id),
                        )
                        if consecutive_knowns >= args.known_streak:
                            print(
                                f"   ⏭️ Known streak ({args.known_streak}) — next producer"
                            )
                            break
                        continue

                consecutive_knowns = 0
                channel = safe_channel(vid) or producer
                is_free = 1 if "free" in title.lower() else 0

                if args.dry_run:
                    print(f"   [dry] would insert {video_id} | {pub_date} | {views} | {title[:80]}")
                    new_for_producer += 1
                    total_new += 1
                    continue

                cursor.execute(
                    """
                    INSERT OR IGNORE INTO beats
                        (video_id, title, artist_style, channel_name, url, views,
                         published_time, scraped_at, is_free)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        video_id,
                        title,
                        "Producer Harvest v2",
                        channel,
                        f"https://youtube.com/watch?v={video_id}",
                        views,
                        pub_date,
                        scrape_date_str,
                        is_free,
                    ),
                )
                if cursor.rowcount:
                    new_for_producer += 1
                    total_new += 1

                stealth_sleep(DEFAULT_SLEEP_MIN, DEFAULT_SLEEP_MAX, args.no_sleep)

            if conn is not None:
                conn.commit()

            if not args.dry_run:
                append_checkpoint(args.checkpoint, producer)
                print(f"   ✅ +{new_for_producer} new | checkpointed")
            else:
                print(f"   ✅ +{new_for_producer} candidates (dry-run, not checkpointed)")

        except KeyboardInterrupt:
            print("\n🛑 Manual stop — progress checkpointed for finished producers.")
            if conn is not None:
                conn.commit()
            break
        except Exception as e:
            errors += 1
            print(f"   ⚠️ Error: {e}")
            # Do not checkpoint on hard failure so producer can be retried
            continue

        # Inter-producer pause: shorter when empty + --fast-empty
        if args.fast_empty and new_for_producer == 0:
            stealth_sleep(args.empty_pause_min, args.empty_pause_max, args.no_sleep)
        else:
            stealth_sleep(
                args.producer_pause_min, args.producer_pause_max, args.no_sleep
            )

        if i % 10 == 0:
            elapsed = time.time() - started
            print(
                f"\n📊 progress: {i}/{len(pending)} producers | "
                f"+{total_new} inserts | {total_seen} videos seen | "
                f"{errors} errors | {elapsed/60:.1f} min"
            )

    if conn is not None:
        conn.close()

    elapsed = time.time() - started
    print("\n=== done ===")
    print(f"New inserts (or dry candidates): {total_new}")
    print(f"Videos inspected: {total_seen}")
    print(f"Skipped outside date window: {total_skipped_date}")
    print(f"Errors: {errors}")
    print(f"Elapsed: {elapsed/60:.1f} min")
    print(f"Resume with same command; checkpoint: {args.checkpoint}")
    return 0


if __name__ == "__main__":
    sys.exit(run(parse_args()))
