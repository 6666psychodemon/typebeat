"""CI-safe checks: fixture shape matches catalog schema (no Turso, no prod DB)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = ROOT / "sql" / "schema" / "001_catalog.sql"
FIXTURE = ROOT / "tests" / "fixtures" / "tracks.json"

REQUIRED_KEYS = {
    "video_id",
    "title",
    "channel_name",
    "url",
    "views",
}


def _catalog_columns(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("PRAGMA table_info(beats)").fetchall()
    return {str(r[1]) for r in rows}


def test_fixture_loads_and_matches_schema() -> None:
    assert SCHEMA.is_file(), "missing sql/schema/001_catalog.sql"
    assert FIXTURE.is_file(), "missing tests/fixtures/tracks.json"

    tracks = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert isinstance(tracks, list) and len(tracks) >= 1

    conn = sqlite3.connect(":memory:")
    try:
        conn.executescript(SCHEMA.read_text(encoding="utf-8"))
        columns = _catalog_columns(conn)
        for row in tracks:
            missing = REQUIRED_KEYS - set(row.keys())
            assert not missing, f"fixture row missing keys: {missing}"
            extra = set(row.keys()) - columns
            assert not extra, f"fixture keys not in schema: {extra}"
            placeholders = ", ".join(row.keys())
            qs = ", ".join("?" for _ in row)
            conn.execute(
                f"INSERT INTO beats ({placeholders}) VALUES ({qs})",
                tuple(row.values()),
            )
        count = conn.execute("SELECT COUNT(*) FROM beats").fetchone()[0]
        assert count == len(tracks)
    finally:
        conn.close()
