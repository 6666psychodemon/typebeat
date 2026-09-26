#!/usr/bin/env python3
"""
Build a priority-ordered producer list for producer_harvester_v2.

Scores producers already present in typebeats.db higher when they have:
  - tracks published in the harvest window (Mar 27 – Aug 5 by default)
  - low-view (≤25k) tracks in that window (radio UG signal)
  - tagged radio genres (Rage/Opium, Drill, Plugg, … — not Underground flood)

Cold names (in harvested_producers.txt but never seen as channel_name) go last.

Outputs (additive; does not touch the running checkpoint):
  harvested_producers_priority.txt          — full reordered list
  harvested_producers_priority_top20k.txt   — top 20k only (recommended first pass)
  harvested_producers_priority_scores.csv   — score breakdown for inspection

Uses a DB snapshot copy when the live DB is locked by a harvester.

Examples
--------
  python build_producer_priority.py
  python build_producer_priority.py --db typebeats.db --top 20000
"""

from __future__ import annotations

import argparse
import collections
import os
import shutil
import sqlite3
import tempfile
import time
from typing import Optional

DEFAULT_DB = "typebeats.db"
DEFAULT_PRODUCERS = "harvested_producers.txt"
DEFAULT_CHECKPOINT = "harvester_v2_checkpoint.txt"
DEFAULT_AFTER = "2026-03-27"
DEFAULT_BEFORE = "2026-08-06"
DEFAULT_OUT = "harvested_producers_priority.txt"
DEFAULT_TOP_OUT = "harvested_producers_priority_top20k.txt"
DEFAULT_CSV = "harvested_producers_priority_scores.csv"
DEFAULT_TOP = 20_000

# Match radio/genres.py station tags (skip Underground — it floods the DB).
RADIO_GENRES = (
    "Rage/Opium",
    "Plugg/Pluggnb",
    "Drill",
    "Dark/Aggressive",
    "Boom Bap/Old School",
    "Ambient/Cloud",
    "Experimental/Glitch",
)


def load_lines(path: str) -> list[str]:
    if not os.path.exists(path):
        return []
    out: list[str] = []
    seen: set[str] = set()
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            name = line.strip()
            if not name or name in seen:
                continue
            seen.add(name)
            out.append(name)
    return out


def open_db(db_path: str) -> tuple[sqlite3.Connection, Optional[str]]:
    """Open DB read-only; fall back to a file snapshot if locked."""
    snap: Optional[str] = None
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5)
        conn.execute("SELECT 1 FROM beats LIMIT 1").fetchone()
        return conn, snap
    except sqlite3.OperationalError:
        pass
    snap = os.path.join(
        tempfile.gettempdir(), f"typebeats_priority_snap_{os.getpid()}.db"
    )
    print(f"⚠️  Live DB busy — copying snapshot to {snap}")
    shutil.copy2(db_path, snap)
    conn = sqlite3.connect(snap)
    return conn, snap


def score_producer(window_n: int, window_ug: int, genre_n: int) -> float:
    """Higher = scrape sooner. Window activity dominates."""
    # Soft-cap genre so mega-tagged catalogs don't drown window signal.
    return (
        window_n * 10.0
        + window_ug * 2.0
        + min(genre_n, 500) * 0.05
        + (5.0 if window_n > 0 else 1.0)
    )


def build(args: argparse.Namespace) -> int:
    t0 = time.time()
    producers = load_lines(args.producers)
    if not producers:
        print(f"❌ No producers in {args.producers}")
        return 1
    done = set(load_lines(args.checkpoint))
    print(f"📁 producers={len(producers)}  checkpoint done={len(done)}")

    conn, snap = open_db(args.db)
    c = conn.cursor()

    # Helpful indexes on snapshot only (live ro DB can't create).
    if snap:
        print("📇 indexing snapshot…")
        c.execute("CREATE INDEX IF NOT EXISTS idx_ch ON beats(channel_name)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_pub ON beats(published_time)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_genre ON beats(genre)")
        conn.commit()

    print("📊 window aggregates…")
    window_counts: dict[str, int] = {}
    window_ug: dict[str, int] = {}
    for ch, n, ug in c.execute(
        """
        SELECT channel_name, COUNT(*),
               SUM(CASE WHEN views > 0 AND views <= 25000 THEN 1 ELSE 0 END)
        FROM beats
        WHERE published_time >= ? AND published_time < ?
          AND channel_name IS NOT NULL AND channel_name != ''
        GROUP BY channel_name
        """,
        (args.after, args.before),
    ):
        window_counts[ch] = n
        window_ug[ch] = ug
    print(f"   {len(window_counts)} channels with window tracks ({time.time()-t0:.1f}s)")

    print("🎛  radio-genre aggregates…")
    placeholders = ",".join("?" * len(RADIO_GENRES))
    genre_hits = dict(
        c.execute(
            f"""
            SELECT channel_name, COUNT(*) FROM beats
            WHERE genre IN ({placeholders})
              AND channel_name IS NOT NULL AND channel_name != ''
            GROUP BY channel_name
            """,
            RADIO_GENRES,
        )
    )
    print(f"   {len(genre_hits)} channels with radio tags ({time.time()-t0:.1f}s)")

    print("🔗 distinct channel set…")
    chans = {
        r[0]
        for r in c.execute(
            "SELECT DISTINCT channel_name FROM beats "
            "WHERE channel_name IS NOT NULL AND channel_name != ''"
        )
    }
    print(f"   {len(chans)} channels ({time.time()-t0:.1f}s)")

    pending_known = [p for p in producers if p not in done and p in chans]
    pending_cold = [p for p in producers if p not in done and p not in chans]
    in_db = sum(1 for p in producers if p in chans)
    print(
        f"✅ exact DB match {in_db}/{len(producers)} ({100 * in_db / len(producers):.1f}%)"
    )
    print(f"🚀 pending known={len(pending_known)}  cold={len(pending_cold)}")

    scored: list[tuple[float, str, int, int, int]] = []
    bands: collections.Counter[str] = collections.Counter()
    for p in pending_known:
        w = window_counts.get(p, 0)
        ug = window_ug.get(p, 0)
        g = genre_hits.get(p, 0)
        s = score_producer(w, ug, g)
        scored.append((s, p, w, ug, g))
        if s >= 200:
            bands["200+"] += 1
        elif s >= 100:
            bands["100-199"] += 1
        elif s >= 50:
            bands["50-99"] += 1
        elif s >= 20:
            bands["20-49"] += 1
        elif s >= 10:
            bands["10-19"] += 1
        else:
            bands["<10"] += 1
    scored.sort(reverse=True)

    print("📈 score bands:", dict(bands))
    print("🏆 top 15:")
    for row in scored[:15]:
        print("  ", tuple(round(x, 1) if isinstance(x, float) else x for x in row))

    wc = sorted(
        ((window_counts[p], p) for p in producers if p not in done and p in window_counts),
        reverse=True,
    )
    total_w = sum(w for w, _ in wc)
    print(f"📦 window tracks among pending-in-list: {total_w} across {len(wc)} producers")
    for cut in (500, 1000, 2000, 5000, 10_000, 20_000, 50_000):
        if cut > len(wc):
            break
        cum = sum(w for w, _ in wc[:cut])
        print(f"   top {cut}: {cum} ({100 * cum / max(total_w, 1):.1f}%)")

    ordered: list[str] = []
    seen_out: set[str] = set()
    for _, p, *_ in scored:
        if p not in seen_out:
            ordered.append(p)
            seen_out.add(p)
    for p in pending_cold:
        if p not in seen_out:
            ordered.append(p)
            seen_out.add(p)

    with open(args.out, "w", encoding="utf-8") as f:
        for p in ordered:
            f.write(p + "\n")
    top_n = min(args.top, len(ordered))
    with open(args.top_out, "w", encoding="utf-8") as f:
        for p in ordered[:top_n]:
            f.write(p + "\n")
    with open(args.csv, "w", encoding="utf-8") as f:
        f.write("rank,score,producer,window_tracks,window_ug,radio_genre_tracks\n")
        for i, (s, p, w, ug, g) in enumerate(scored[:top_n], 1):
            safe = p.replace(",", " ")
            f.write(f"{i},{s:.1f},{safe},{w},{ug},{g}\n")

    print(f"\n✍️  {args.out} ({len(ordered)} lines)")
    print(f"✍️  {args.top_out} ({top_n} lines)")
    print(f"✍️  {args.csv}")
    print(f"⏱  {time.time() - t0:.1f}s")

    conn.close()
    if snap and os.path.exists(snap):
        try:
            os.remove(snap)
        except OSError:
            pass
    return 0


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build priority producer harvest order.")
    p.add_argument("--db", default=DEFAULT_DB)
    p.add_argument("--producers", default=DEFAULT_PRODUCERS)
    p.add_argument("--checkpoint", default=DEFAULT_CHECKPOINT)
    p.add_argument("--after", default=DEFAULT_AFTER)
    p.add_argument("--before", default=DEFAULT_BEFORE)
    p.add_argument("--out", default=DEFAULT_OUT)
    p.add_argument("--top-out", default=DEFAULT_TOP_OUT)
    p.add_argument("--csv", default=DEFAULT_CSV)
    p.add_argument("--top", type=int, default=DEFAULT_TOP)
    return p.parse_args()


if __name__ == "__main__":
    raise SystemExit(build(parse_args()))
