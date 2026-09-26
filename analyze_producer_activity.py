#!/usr/bin/env python3
"""
Analyze producer activity in a publish-date window and tier channels.

Thresholds (computed from the empirical distribution of window_track_count
among producers with ≥1 track in the window; override via CLI):

  Sparse   : 1–2 tracks in window (not worth attention for priority harvest)
  Active   : 3 … (p90 − 1) inclusive — moderate / worth some attention
  Prolific : ≥ p90 tracks in window (high activity; p75 reported as a warm floor)

Default window: 2026-03-27 → today (inclusive via exclusive --before = tomorrow).
Matches the producer_harvester_v2 search intent (Mar 27 onward), even if the
harvester CLI default `--before` is still pinned to 2026-08-06.

Outputs
-------
  prolific_producers.csv   — prolific tier (≥ p90 by default)
  prolific_producers.txt   — channel_name only (prolific)
  active_producers.csv     — active tier
  sparse_producers.csv     — sparse tier (1–2)
  PRODUCERS_ACTIVITY.md    — summary, thresholds, top examples, how to use

Re-run
------
  source venv/bin/activate
  python analyze_producer_activity.py
  python analyze_producer_activity.py --after 2026-03-27 --before 2026-08-11
  # Safe under live harvester writes (uses sqlite backup API):
  python analyze_producer_activity.py --snapshot
"""

from __future__ import annotations

import argparse
import csv
import math
import os
import sqlite3
import statistics
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import List, Sequence, Tuple


DEFAULT_DB = "typebeats.db"
DEFAULT_AFTER = "2026-03-27"
DEFAULT_SNAPSHOT = "typebeats_activity_snapshot.db"


def tomorrow_iso() -> str:
    return (date.today() + timedelta(days=1)).isoformat()


def percentile_nearest(sorted_vals: Sequence[int], p: float) -> int:
    """Nearest-rank percentile (p in 0..100) on a non-empty sorted list."""
    if not sorted_vals:
        return 0
    if p <= 0:
        return sorted_vals[0]
    if p >= 100:
        return sorted_vals[-1]
    k = max(1, math.ceil(p / 100.0 * len(sorted_vals)))
    return sorted_vals[k - 1]


def backup_db(src: str, dest: str) -> None:
    if os.path.exists(dest):
        os.remove(dest)
    src_conn = sqlite3.connect(src, timeout=120)
    src_conn.execute("PRAGMA busy_timeout=120000")
    try:
        dest_conn = sqlite3.connect(dest)
        with dest_conn:
            src_conn.backup(dest_conn)
        dest_conn.close()
    finally:
        src_conn.close()


def fetch_activity(
    db_path: str, after: str, before: str
) -> Tuple[List[dict], dict]:
    """
    Return per-channel rows for the publish window plus global stats.

    Single full-table GROUP BY (avoids N chunked lookups that deadlock under
    a live harvester writer). window_track_count uses published_time in
    [after, before); total_tracks / last_publish are all-time for the channel.
    """
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=300)
    conn.execute("PRAGMA busy_timeout=300000")
    conn.row_factory = sqlite3.Row
    try:
        print("   … Producer Harvest v2 count", flush=True)
        v2_count = conn.execute(
            "SELECT COUNT(*) FROM beats WHERE artist_style = 'Producer Harvest v2'"
        ).fetchone()[0]

        print("   … per-channel GROUP BY (full scan; may take a few min)", flush=True)
        # One pass over beats: window + lifetime stats together.
        agg = conn.execute(
            """
            SELECT channel_name,
                   SUM(CASE WHEN published_time >= ? AND published_time < ?
                            THEN 1 ELSE 0 END) AS window_track_count,
                   SUM(CASE WHEN published_time >= ? AND published_time < ?
                                 AND artist_style = 'Producer Harvest v2'
                            THEN 1 ELSE 0 END) AS window_v2_count,
                   COUNT(*) AS total_tracks,
                   MAX(published_time) AS last_publish,
                   MAX(CASE WHEN published_time >= ? AND published_time < ?
                            THEN published_time END) AS last_publish_in_window
            FROM beats
            WHERE channel_name IS NOT NULL AND channel_name != ''
            GROUP BY channel_name
            HAVING window_track_count > 0
            """,
            (after, before, after, before, after, before),
        ).fetchall()

        rows: List[dict] = []
        window_tracks = 0
        for r in agg:
            wc = int(r["window_track_count"])
            window_tracks += wc
            rows.append(
                {
                    "channel_name": r["channel_name"],
                    "window_track_count": wc,
                    "window_v2_count": int(r["window_v2_count"] or 0),
                    "total_tracks": int(r["total_tracks"]),
                    "last_publish": r["last_publish"],
                    "last_publish_in_window": r["last_publish_in_window"],
                }
            )
        rows.sort(key=lambda x: (-x["window_track_count"], x["channel_name"].lower()))

        meta = {
            "v2_inserts_total": int(v2_count),
            "window_tracks": window_tracks,
            "window_channels": len(rows),
            "db_path": db_path,
        }
        return rows, meta
    finally:
        conn.close()


def assign_tiers(
    rows: List[dict], prolific_min: int, sparse_max: int = 2
) -> Tuple[List[dict], List[dict], List[dict]]:
    """Prolific ≥ prolific_min (default p90); sparse ≤2; else active."""
    prolific, active, sparse = [], [], []
    for r in rows:
        n = r["window_track_count"]
        if n <= sparse_max:
            r["tier"] = "sparse"
            sparse.append(r)
        elif n >= prolific_min:
            r["tier"] = "prolific"
            prolific.append(r)
        else:
            r["tier"] = "active"
            active.append(r)
    return prolific, active, sparse


def write_csv(path: Path, rows: List[dict], fieldnames: Sequence[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def write_txt(path: Path, rows: List[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(r["channel_name"] + "\n")


def write_markdown(
    path: Path,
    *,
    after: str,
    before: str,
    meta: dict,
    counts: Counter,
    p50: int,
    p75: int,
    p90: int,
    p95: int,
    mean: float,
    prolific: List[dict],
    active: List[dict],
    sparse: List[dict],
    generated_at: str,
) -> None:
    top_p = prolific[:15]
    top_a = active[:10]
    lines = [
        "# Producer activity (publish window)",
        "",
        f"Generated: `{generated_at}`",
        f"Window: `published_time >= {after}` and `< {before}` (exclusive end).",
        f"DB: `{meta['db_path']}`",
        "",
        "## Thresholds",
        "",
        "Computed from the distribution of `window_track_count` among producers",
        "with ≥1 track in the window (nearest-rank percentiles):",
        "",
        f"| Stat | Value |",
        f"|------|------:|",
        f"| Producers in window | {meta['window_channels']:,} |",
        f"| Tracks in window | {meta['window_tracks']:,} |",
        f"| Producer Harvest v2 inserts (all-time in DB) | {meta['v2_inserts_total']:,} |",
        f"| p50 (median) | {p50} |",
        f"| p75 (warm floor) | {p75} |",
        f"| p90 | **{p90}** ← prolific cutoff |",
        f"| p95 | {p95} |",
        f"| mean | {mean:.2f} |",
        "",
        "### Tier definitions",
        "",
        f"- **Prolific**: `window_track_count ≥ {p90}` (at/above p90; high output)",
        f"- **Active**: `3 … {max(3, p90 - 1)}` tracks in window (moderate)",
        "- **Sparse**: `1–2` tracks in window (usually not worth harvest priority)",
        f"- Note: p75={p75} is a warm floor inside Active — rising toward prolific.",
        "",
        "## Counts per tier",
        "",
        f"| Tier | Producers | Share |",
        f"|------|----------:|------:|",
        f"| Prolific | {len(prolific):,} | {100 * len(prolific) / max(1, meta['window_channels']):.1f}% |",
        f"| Active | {len(active):,} | {100 * len(active) / max(1, meta['window_channels']):.1f}% |",
        f"| Sparse | {len(sparse):,} | {100 * len(sparse) / max(1, meta['window_channels']):.1f}% |",
        "",
        "## Track-count histogram (window)",
        "",
        "| window_track_count | producers |",
        "|-------------------:|----------:|",
    ]
    for k in sorted(counts):
        if k <= 20 or k in (p50, p75, p90, p95) or k % 25 == 0:
            lines.append(f"| {k} | {counts[k]:,} |")
    # Always show a few high buckets collapsed
    high = sum(v for k, v in counts.items() if k > 20)
    lines.append(f"| >20 (sum) | {high:,} |")
    lines += [
        "",
        "## Top prolific examples",
        "",
        "| channel_name | window | total | last_publish |",
        "|--------------|-------:|------:|--------------|",
    ]
    for r in top_p:
        lines.append(
            f"| {r['channel_name']} | {r['window_track_count']} | "
            f"{r['total_tracks']} | {r['last_publish']} |"
        )
    lines += [
        "",
        "## Sample active (highest in tier)",
        "",
        "| channel_name | window | total | last_publish |",
        "|--------------|-------:|------:|--------------|",
    ]
    for r in top_a:
        lines.append(
            f"| {r['channel_name']} | {r['window_track_count']} | "
            f"{r['total_tracks']} | {r['last_publish']} |"
        )
    lines += [
        "",
        "## Artifacts",
        "",
        "- `prolific_producers.txt` — names only (feed into priority harvest)",
        "- `prolific_producers.csv` — channel_name, window_track_count, window_tracks, last_publish, …",
        "- `active_producers.csv` / `sparse_producers.csv`",
        "- Re-run: `python analyze_producer_activity.py` (add `--snapshot` while harvester is writing)",
        "",
        "## How this helps attention / harvest priority",
        "",
        "1. **Attention**: focus curation / radio / tagging on prolific + active; ignore sparse noise.",
        "2. **Harvest order**: put `prolific_producers.txt` ahead of cold / sparse names when",
        "   rebuilding priority lists (`build_producer_priority.py` or a manual prepend).",
        "3. **Skip waste**: sparse (1–2) producers rarely justify another YouTube search pass.",
        "4. **Note**: `producer_harvester_v2` default search window may still end at",
        "   `before:2026-08-06`; extend `--before` if you want harvest to match “through today”.",
        "",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Tier producers by window activity.")
    p.add_argument("--db", default=DEFAULT_DB)
    p.add_argument("--after", default=DEFAULT_AFTER)
    p.add_argument(
        "--before",
        default=None,
        help="Exclusive end YYYY-MM-DD (default: tomorrow → includes today)",
    )
    p.add_argument(
        "--snapshot",
        action="store_true",
        help=f"sqlite backup to {DEFAULT_SNAPSHOT} first (safer under live writes)",
    )
    p.add_argument(
        "--snapshot-path",
        default=DEFAULT_SNAPSHOT,
        help="Path for --snapshot backup",
    )
    p.add_argument(
        "--prolific-min",
        type=int,
        default=None,
        help="Override prolific cutoff (default = empirical p90)",
    )
    p.add_argument("--outdir", default=".", help="Directory for output files")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    after = args.after
    before = args.before or tomorrow_iso()
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    db_path = args.db
    if args.snapshot:
        print(f"📦 snapshot {args.db} → {args.snapshot_path} …")
        backup_db(args.db, args.snapshot_path)
        db_path = args.snapshot_path
        print("   done")

    print(f"📊 querying {db_path} window [{after}, {before}) …")
    rows, meta = fetch_activity(db_path, after, before)
    if not rows:
        print("No producers in window.")
        return 1

    counts_list = sorted(r["window_track_count"] for r in rows)
    p50 = percentile_nearest(counts_list, 50)
    p75 = percentile_nearest(counts_list, 75)
    p90 = percentile_nearest(counts_list, 90)
    p95 = percentile_nearest(counts_list, 95)
    mean = statistics.fmean(counts_list)
    prolific_min = args.prolific_min if args.prolific_min is not None else p90

    prolific, active, sparse = assign_tiers(rows, prolific_min)
    hist = Counter(r["window_track_count"] for r in rows)

    fields = [
        "channel_name",
        "tier",
        "window_track_count",
        "window_v2_count",
        "total_tracks",
        "last_publish",
        "last_publish_in_window",
    ]
    write_csv(outdir / "prolific_producers.csv", prolific, fields)
    write_txt(outdir / "prolific_producers.txt", prolific)
    write_csv(outdir / "active_producers.csv", active, fields)
    write_csv(outdir / "sparse_producers.csv", sparse, fields)
    write_markdown(
        outdir / "PRODUCERS_ACTIVITY.md",
        after=after,
        before=before,
        meta=meta,
        counts=hist,
        p50=p50,
        p75=p75,
        p90=prolific_min if args.prolific_min is not None else p90,
        p95=p95,
        mean=mean,
        prolific=prolific,
        active=active,
        sparse=sparse,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )

    print(
        f"tiers: prolific={len(prolific)} (≥{prolific_min}) "
        f"active={len(active)} sparse={len(sparse)}"
    )
    print(f"percentiles: p50={p50} p75={p75} p90={p90} p95={p95} mean={mean:.2f}")
    print(f"wrote: {outdir / 'prolific_producers.txt'}")
    print(f"wrote: {outdir / 'PRODUCERS_ACTIVITY.md'}")
    print("top 10 prolific:")
    for r in prolific[:10]:
        print(f"  {r['window_track_count']:4d}  {r['channel_name']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
