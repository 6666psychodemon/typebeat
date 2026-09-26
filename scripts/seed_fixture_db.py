#!/usr/bin/env python3
"""Build a tiny typebeats.db from tests/fixtures/tracks.json (for local smoke tests)."""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = ROOT / "sql" / "schema" / "001_catalog.sql"
FIXTURE = ROOT / "tests" / "fixtures" / "tracks.json"


def main() -> int:
    out = ROOT / "typebeats.db"
    if len(sys.argv) > 1:
        out = Path(sys.argv[1]).expanduser().resolve()

    tracks = json.loads(FIXTURE.read_text(encoding="utf-8"))
    if out.is_file():
        out.unlink()

    conn = sqlite3.connect(str(out))
    try:
        conn.executescript(SCHEMA.read_text(encoding="utf-8"))
        for row in tracks:
            keys = list(row.keys())
            conn.execute(
                f"INSERT INTO beats ({', '.join(keys)}) VALUES ({', '.join('?' for _ in keys)})",
                [row[k] for k in keys],
            )
        conn.commit()
    finally:
        conn.close()

    print(f"Wrote {len(tracks)} rows to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
