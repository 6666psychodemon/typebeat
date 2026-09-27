"""Genre tree stored in data/genres.db, separate from the catalog.

typebeats.db keeps assignments (beats.genre, beats.parent_genre).
This file is the tree: parents, subgenres, artists, and phrases.
data/genre_taxonomy.json is only the seed input.
"""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "genres.db"
TAXONOMY_PATH = ROOT / "data" / "genre_taxonomy.json"

# Subgenre strings with no radio parent. parent_genre stays NULL.
ORPHANS = (
    "Ambient/Cloud",
    "Experimental/Glitch",
    "Roots Reggae",
    "Ragga",
)

SCHEMA = """
CREATE TABLE parents (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    button_label TEXT NOT NULL,
    show_on_radio INTEGER NOT NULL DEFAULT 1,
    definition TEXT,
    differs TEXT
);
CREATE TABLE subgenres (
    id TEXT PRIMARY KEY,
    parent_id TEXT REFERENCES parents(id),
    name TEXT NOT NULL UNIQUE,
    label TEXT,
    definition TEXT,
    differs TEXT,
    weight INTEGER NOT NULL DEFAULT 50
);
CREATE TABLE artists (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    alias TEXT NOT NULL UNIQUE,
    subgenre_id TEXT NOT NULL REFERENCES subgenres(id)
);
CREATE TABLE phrases (
    id INTEGER PRIMARY KEY,
    subgenre_id TEXT NOT NULL REFERENCES subgenres(id),
    phrase TEXT NOT NULL,
    pattern TEXT,
    scope TEXT NOT NULL DEFAULT 'anywhere'
);
CREATE INDEX idx_artists_alias ON artists(alias);
CREATE INDEX idx_phrases_sub ON phrases(subgenre_id);
"""


def connect(*, readonly: bool = False) -> sqlite3.Connection:
    if readonly:
        uri = f"file:{DB_PATH}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
    else:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "genre"


def read_taxonomy() -> dict | None:
    """Parents and subgenres for /map. Artists are not included."""
    if not DB_PATH.is_file():
        return None
    conn = connect(readonly=True)
    try:
        parents = conn.execute(
            """
            SELECT id, name, button_label, show_on_radio, definition, differs
            FROM parents
            ORDER BY name
            """
        ).fetchall()
        if not parents:
            return None
        subs = conn.execute(
            """
            SELECT id, parent_id, name, label, definition, differs
            FROM subgenres
            WHERE parent_id IS NOT NULL
            ORDER BY name
            """
        ).fetchall()
    finally:
        conn.close()
    by_parent: dict[str, list[dict]] = {}
    for row in subs:
        by_parent.setdefault(row["parent_id"], []).append(
            {
                "id": row["id"],
                "name": row["name"],
                "label": row["label"] or row["name"],
                "definition": row["definition"] or "",
                "differs": row["differs"] or "",
                "parent": "",
            }
        )
    out_parents = []
    for row in parents:
        children = by_parent.get(row["id"], [])
        for child in children:
            child["parent"] = row["name"]
        out_parents.append(
            {
                "id": row["id"],
                "name": row["name"],
                "label": row["button_label"] or row["name"],
                "button": bool(row["show_on_radio"]),
                "definition": row["definition"] or "",
                "differs": row["differs"] or "",
                "subgenres": children,
            }
        )
    return {"parents": out_parents, "borders": []}


def parent_by_subgenre() -> dict[str, str]:
    """Subgenre string → parent name. Orphans are omitted."""
    if not DB_PATH.is_file():
        return {}
    conn = connect(readonly=True)
    try:
        rows = conn.execute(
            """
            SELECT s.name AS sub, p.name AS parent
            FROM subgenres s
            JOIN parents p ON p.id = s.parent_id
            """
        ).fetchall()
    finally:
        conn.close()
    return {row["sub"]: row["parent"] for row in rows}


def alias_rows() -> list[tuple[str, str]]:
    if not DB_PATH.is_file():
        return []
    conn = connect(readonly=True)
    try:
        rows = conn.execute(
            """
            SELECT a.alias AS alias, s.name AS genre
            FROM artists a
            JOIN subgenres s ON s.id = a.subgenre_id
            """
        ).fetchall()
    finally:
        conn.close()
    return [(row["alias"], row["genre"]) for row in rows]


def phrase_rows() -> list[dict]:
    if not DB_PATH.is_file():
        return []
    conn = connect(readonly=True)
    try:
        rows = conn.execute(
            """
            SELECT ph.phrase, ph.pattern, ph.scope, s.name AS genre, s.weight
            FROM phrases ph
            JOIN subgenres s ON s.id = ph.subgenre_id
            """
        ).fetchall()
    finally:
        conn.close()
    return [dict(row) for row in rows]


def subgenre_weights() -> dict[str, int]:
    if not DB_PATH.is_file():
        return {}
    conn = connect(readonly=True)
    try:
        rows = conn.execute("SELECT name, weight FROM subgenres").fetchall()
    finally:
        conn.close()
    return {row["name"]: int(row["weight"]) for row in rows}


def seed() -> None:
    """Import the taxonomy once, then the alias list the tagger already uses."""
    from tag_underground_pass import (
        ANYWHERE_SRC,
        DJCRATES_PATH,
        HAND,
        SPEC,
        STYLES,
        build_entries,
        entry_genre,
        name_key,
        source_genre,
    )

    taxonomy = json.loads(TAXONOMY_PATH.read_text(encoding="utf-8"))
    if DB_PATH.exists():
        DB_PATH.unlink()
    conn = connect()
    try:
        conn.executescript(SCHEMA)
        sub_ids: dict[str, str] = {}
        for parent in taxonomy.get("parents") or []:
            if not isinstance(parent, dict):
                continue
            pid = str(parent.get("id") or _slug(str(parent.get("name") or "")))
            pname = str(parent.get("name") or "")
            if not pname:
                continue
            show = 0 if parent.get("button") is False else 1
            conn.execute(
                """
                INSERT INTO parents (id, name, button_label, show_on_radio, definition, differs)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    pid,
                    pname,
                    pname,
                    show,
                    parent.get("definition") or "",
                    parent.get("differs") or "",
                ),
            )
            for sub in parent.get("subgenres") or []:
                if not isinstance(sub, dict):
                    continue
                sname = str(sub.get("name") or "")
                if not sname:
                    continue
                sid = str(sub.get("id") or _slug(sname))
                weight = int(SPEC.get(sname) or sub.get("weight") or 50)
                conn.execute(
                    """
                    INSERT INTO subgenres
                        (id, parent_id, name, label, definition, differs, weight)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        sid,
                        pid,
                        sname,
                        sub.get("label") or sname,
                        sub.get("definition") or "",
                        sub.get("differs") or "",
                        weight,
                    ),
                )
                sub_ids[sname] = sid
        for name in ORPHANS:
            if name in sub_ids:
                continue
            sid = _slug(name)
            conn.execute(
                """
                INSERT INTO subgenres (id, parent_id, name, label, weight)
                VALUES (?, NULL, ?, ?, ?)
                """,
                (sid, name, name, int(SPEC.get(name) or 50)),
            )
            sub_ids[name] = sid

        # alias → (display name, subgenre string). Later writes win.
        chosen: dict[str, tuple[str, str]] = {}

        def put(display: str, genre: str, *, overwrite: bool) -> None:
            alias = name_key(display)
            if not alias or genre not in sub_ids:
                return
            if not overwrite and alias in chosen:
                return
            chosen[alias] = (display.strip() or alias, genre)

        if DJCRATES_PATH.is_file():
            rows = json.loads(DJCRATES_PATH.read_text(encoding="utf-8"))
            for row in rows:
                if not isinstance(row, dict):
                    continue
                put(str(row.get("name") or ""), source_genre(row), overwrite=True)

        for parent in taxonomy.get("parents") or []:
            if not isinstance(parent, dict):
                continue
            for sub in parent.get("subgenres") or []:
                if not isinstance(sub, dict):
                    continue
                sname = str(sub.get("name") or "")
                for artist in sub.get("artists") or []:
                    put(str(artist), sname, overwrite=True)

        entries = build_entries()
        for entry in entries.values():
            genre = entry_genre(entry)
            if not genre:
                continue
            # Gaps only. Hand and djcrates already landed via build order below.
            if entry.get("source") in ("llm", "wikidata"):
                put(str(entry.get("name") or ""), genre, overwrite=False)

        for alias, genre in HAND.items():
            put(alias, genre, overwrite=True)

        conn.executemany(
            "INSERT INTO artists (name, alias, subgenre_id) VALUES (?, ?, ?)",
            [
                (display, alias, sub_ids[genre])
                for alias, (display, genre) in sorted(chosen.items())
            ],
        )

        phrase_sql = (
            "INSERT INTO phrases (subgenre_id, phrase, pattern, scope) VALUES (?, ?, ?, ?)"
        )
        phrase_params = []
        for pattern, genre in ANYWHERE_SRC:
            if genre not in sub_ids:
                continue
            phrase_params.append((sub_ids[genre], pattern, pattern, "anywhere"))
        for style, genre in STYLES:
            if not genre or genre not in sub_ids:
                continue
            phrase_params.append((sub_ids[genre], style, None, "typebeat"))
        conn.executemany(phrase_sql, phrase_params)
        conn.commit()
        counts = {
            "parents": conn.execute("SELECT COUNT(*) FROM parents").fetchone()[0],
            "subgenres": conn.execute("SELECT COUNT(*) FROM subgenres").fetchone()[0],
            "artists": conn.execute("SELECT COUNT(*) FROM artists").fetchone()[0],
            "phrases": conn.execute("SELECT COUNT(*) FROM phrases").fetchone()[0],
            "radio_off": conn.execute(
                "SELECT COUNT(*) FROM parents WHERE show_on_radio = 0"
            ).fetchone()[0],
        }
    finally:
        conn.close()
    print(
        f"genres.db {DB_PATH} parents {counts['parents']} "
        f"subgenres {counts['subgenres']} artists {counts['artists']} "
        f"phrases {counts['phrases']} show_on_radio=0 {counts['radio_off']}",
        flush=True,
    )


if __name__ == "__main__":
    seed()
