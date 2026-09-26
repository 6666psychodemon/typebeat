"""
Invite / auth SQLite store (separate from the catalog typebeats.db).

Tables: invite_requests, invites, users, reactions.
"""

from __future__ import annotations

import re
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent / "data"
AUTH_DB_PATH = DATA_DIR / "auth.db"

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_lock = threading.Lock()


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def normalize_email(email: str | None) -> str | None:
    if not email:
        return None
    cleaned = str(email).strip().lower()
    if not cleaned or len(cleaned) > 254 or not _EMAIL_RE.match(cleaned):
        return None
    return cleaned


def connect(writable: bool = True) -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(AUTH_DB_PATH), timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    if writable:
        conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db() -> None:
    with _lock:
        conn = connect(True)
        try:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS invite_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT NOT NULL COLLATE NOCASE,
                    note TEXT,
                    status TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'invited', 'denied')),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_invite_requests_email
                    ON invite_requests(email);
                CREATE INDEX IF NOT EXISTS idx_invite_requests_status
                    ON invite_requests(status);

                CREATE TABLE IF NOT EXISTS invites (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT NOT NULL COLLATE NOCASE UNIQUE,
                    status TEXT NOT NULL DEFAULT 'open'
                        CHECK (status IN ('open', 'redeemed')),
                    request_id INTEGER REFERENCES invite_requests(id),
                    created_at TEXT NOT NULL,
                    redeemed_at TEXT,
                    redeemed_by_user_id INTEGER
                );
                CREATE INDEX IF NOT EXISTS idx_invites_status ON invites(status);

                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    google_sub TEXT NOT NULL UNIQUE,
                    email TEXT NOT NULL COLLATE NOCASE UNIQUE,
                    name TEXT,
                    picture TEXT,
                    created_at TEXT NOT NULL,
                    last_login_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS reactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL REFERENCES users(id),
                    video_id TEXT NOT NULL,
                    genre TEXT,
                    reaction TEXT NOT NULL CHECK (reaction IN ('like', 'dislike')),
                    created_at TEXT NOT NULL,
                    UNIQUE (user_id, video_id)
                );
                CREATE INDEX IF NOT EXISTS idx_reactions_user
                    ON reactions(user_id, created_at);
                """
            )
            # Migrate early reactions unique (user_id, video_id, reaction) → (user_id, video_id)
            idx_sql = conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='reactions'"
            ).fetchone()
            create_sql = (idx_sql["sql"] if idx_sql else "") or ""
            if "UNIQUE (user_id, video_id, reaction)" in create_sql.replace("\n", " "):
                conn.executescript(
                    """
                    CREATE TABLE reactions_v2 (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL REFERENCES users(id),
                        video_id TEXT NOT NULL,
                        genre TEXT,
                        reaction TEXT NOT NULL CHECK (reaction IN ('like', 'dislike')),
                        created_at TEXT NOT NULL,
                        UNIQUE (user_id, video_id)
                    );
                    INSERT OR REPLACE INTO reactions_v2
                        (id, user_id, video_id, genre, reaction, created_at)
                    SELECT id, user_id, video_id, genre, reaction, created_at
                    FROM reactions
                    GROUP BY user_id, video_id
                    HAVING id = MAX(id);
                    DROP TABLE reactions;
                    ALTER TABLE reactions_v2 RENAME TO reactions;
                    CREATE INDEX IF NOT EXISTS idx_reactions_user
                        ON reactions(user_id, created_at);
                    """
                )
            conn.commit()
        finally:
            conn.close()


def create_invite_request(email: str, note: str | None = None) -> dict[str, Any]:
    """Insert or refresh a pending invite request. Returns public result."""
    norm = normalize_email(email)
    if not norm:
        return {"ok": False, "error": "valid email required"}

    note_clean = (note or "").strip()[:200] or None
    now = utc_now()

    with _lock:
        conn = connect(True)
        try:
            # Already has an open invite — tell them to sign in.
            inv = conn.execute(
                "SELECT id, status FROM invites WHERE email = ? COLLATE NOCASE",
                (norm,),
            ).fetchone()
            if inv and inv["status"] == "open":
                return {
                    "ok": True,
                    "status": "invited",
                    "message": "You already have an invite — Sign In With Google.",
                }
            if inv and inv["status"] == "redeemed":
                return {
                    "ok": True,
                    "status": "redeemed",
                    "message": "This email already has access — Sign In With Google.",
                }

            existing = conn.execute(
                """
                SELECT id, status FROM invite_requests
                WHERE email = ? COLLATE NOCASE
                ORDER BY id DESC LIMIT 1
                """,
                (norm,),
            ).fetchone()

            if existing and existing["status"] == "pending":
                conn.execute(
                    """
                    UPDATE invite_requests
                    SET note = COALESCE(?, note), updated_at = ?
                    WHERE id = ?
                    """,
                    (note_clean, now, existing["id"]),
                )
                conn.commit()
                return {
                    "ok": True,
                    "status": "pending",
                    "message": "Request sent — we'll be in touch.",
                }

            if existing and existing["status"] == "invited":
                return {
                    "ok": True,
                    "status": "invited",
                    "message": "You already have an invite — Sign In With Google.",
                }

            conn.execute(
                """
                INSERT INTO invite_requests (email, note, status, created_at, updated_at)
                VALUES (?, ?, 'pending', ?, ?)
                """,
                (norm, note_clean, now, now),
            )
            conn.commit()
            return {
                "ok": True,
                "status": "pending",
                "message": "Request sent — we'll be in touch.",
            }
        finally:
            conn.close()


def list_invite_requests(status: str | None = None) -> list[dict[str, Any]]:
    with _lock:
        conn = connect(False)
        try:
            if status:
                rows = conn.execute(
                    """
                    SELECT id, email, note, status, created_at, updated_at
                    FROM invite_requests WHERE status = ?
                    ORDER BY created_at DESC
                    """,
                    (status,),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT id, email, note, status, created_at, updated_at
                    FROM invite_requests
                    ORDER BY
                      CASE status
                        WHEN 'pending' THEN 0
                        WHEN 'invited' THEN 1
                        ELSE 2
                      END,
                      created_at DESC
                    """
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()


def list_invites() -> list[dict[str, Any]]:
    with _lock:
        conn = connect(False)
        try:
            rows = conn.execute(
                """
                SELECT id, email, status, request_id, created_at, redeemed_at
                FROM invites ORDER BY created_at DESC
                """
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()


def grant_invite(email: str, request_id: int | None = None) -> dict[str, Any]:
    """Create/open an invite for email; mark matching request invited."""
    norm = normalize_email(email)
    if not norm:
        return {"ok": False, "error": "valid email required"}

    now = utc_now()
    with _lock:
        conn = connect(True)
        try:
            existing = conn.execute(
                "SELECT id, status FROM invites WHERE email = ? COLLATE NOCASE",
                (norm,),
            ).fetchone()

            if existing and existing["status"] == "redeemed":
                return {
                    "ok": True,
                    "status": "redeemed",
                    "message": f"{norm} already redeemed",
                    "invite_id": existing["id"],
                }

            if existing:
                invite_id = existing["id"]
            else:
                # Link to latest pending request if not specified
                rid = request_id
                if rid is None:
                    row = conn.execute(
                        """
                        SELECT id FROM invite_requests
                        WHERE email = ? COLLATE NOCASE AND status = 'pending'
                        ORDER BY id DESC LIMIT 1
                        """,
                        (norm,),
                    ).fetchone()
                    rid = int(row["id"]) if row else None

                cur = conn.execute(
                    """
                    INSERT INTO invites (email, status, request_id, created_at)
                    VALUES (?, 'open', ?, ?)
                    """,
                    (norm, rid, now),
                )
                invite_id = int(cur.lastrowid)

            conn.execute(
                """
                UPDATE invite_requests
                SET status = 'invited', updated_at = ?
                WHERE email = ? COLLATE NOCASE AND status = 'pending'
                """,
                (now, norm),
            )
            conn.commit()
            return {
                "ok": True,
                "status": "open",
                "email": norm,
                "invite_id": invite_id,
                "message": f"Invite granted for {norm}",
            }
        finally:
            conn.close()


def deny_invite_request(email: str) -> dict[str, Any]:
    norm = normalize_email(email)
    if not norm:
        return {"ok": False, "error": "valid email required"}

    now = utc_now()
    with _lock:
        conn = connect(True)
        try:
            cur = conn.execute(
                """
                UPDATE invite_requests
                SET status = 'denied', updated_at = ?
                WHERE email = ? COLLATE NOCASE AND status = 'pending'
                """,
                (now, norm),
            )
            conn.commit()
            if cur.rowcount == 0:
                return {"ok": False, "error": f"no pending request for {norm}"}
            return {"ok": True, "status": "denied", "email": norm}
        finally:
            conn.close()


def find_open_invite(email: str) -> dict[str, Any] | None:
    norm = normalize_email(email)
    if not norm:
        return None
    with _lock:
        conn = connect(False)
        try:
            row = conn.execute(
                """
                SELECT id, email, status, request_id, created_at
                FROM invites
                WHERE email = ? COLLATE NOCASE AND status = 'open'
                """,
                (norm,),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()


def upsert_user_from_google(
    *,
    google_sub: str,
    email: str,
    name: str | None = None,
    picture: str | None = None,
) -> dict[str, Any]:
    norm = normalize_email(email)
    if not norm or not google_sub:
        raise ValueError("google_sub and email required")

    now = utc_now()
    with _lock:
        conn = connect(True)
        try:
            row = conn.execute(
                "SELECT id FROM users WHERE google_sub = ?",
                (google_sub,),
            ).fetchone()
            if row:
                conn.execute(
                    """
                    UPDATE users
                    SET email = ?, name = ?, picture = ?, last_login_at = ?
                    WHERE id = ?
                    """,
                    (norm, name, picture, now, row["id"]),
                )
                user_id = int(row["id"])
            else:
                # Re-bind by email if founder re-granted after revoke (rare)
                by_email = conn.execute(
                    "SELECT id FROM users WHERE email = ? COLLATE NOCASE",
                    (norm,),
                ).fetchone()
                if by_email:
                    conn.execute(
                        """
                        UPDATE users
                        SET google_sub = ?, name = ?, picture = ?, last_login_at = ?
                        WHERE id = ?
                        """,
                        (google_sub, name, picture, now, by_email["id"]),
                    )
                    user_id = int(by_email["id"])
                else:
                    cur = conn.execute(
                        """
                        INSERT INTO users
                            (google_sub, email, name, picture, created_at, last_login_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (google_sub, norm, name, picture, now, now),
                    )
                    user_id = int(cur.lastrowid)

            invite = conn.execute(
                """
                SELECT id FROM invites
                WHERE email = ? COLLATE NOCASE AND status = 'open'
                """,
                (norm,),
            ).fetchone()
            if invite:
                conn.execute(
                    """
                    UPDATE invites
                    SET status = 'redeemed', redeemed_at = ?, redeemed_by_user_id = ?
                    WHERE id = ?
                    """,
                    (now, user_id, invite["id"]),
                )

            conn.commit()
            user = conn.execute(
                "SELECT id, google_sub, email, name, picture, created_at, last_login_at "
                "FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
            return dict(user)
        finally:
            conn.close()


def get_user(user_id: int) -> dict[str, Any] | None:
    with _lock:
        conn = connect(False)
        try:
            row = conn.execute(
                "SELECT id, google_sub, email, name, picture, created_at, last_login_at "
                "FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()


def find_user_by_google(email: str, google_sub: str) -> dict[str, Any] | None:
    norm = normalize_email(email)
    with _lock:
        conn = connect(False)
        try:
            row = conn.execute(
                """
                SELECT id, google_sub, email, name, picture, created_at, last_login_at
                FROM users
                WHERE google_sub = ?
                   OR (? IS NOT NULL AND email = ? COLLATE NOCASE)
                LIMIT 1
                """,
                (google_sub, norm, norm),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()


def save_reaction(
    user_id: int,
    video_id: str,
    reaction: str,
    genre: str | None = None,
) -> dict[str, Any]:
    if reaction not in ("like", "dislike"):
        return {"ok": False, "error": "invalid reaction"}
    vid = (video_id or "").strip()[:32]
    if not vid:
        return {"ok": False, "error": "video_id required"}
    now = utc_now()
    with _lock:
        conn = connect(True)
        try:
            conn.execute(
                """
                INSERT INTO reactions (user_id, video_id, genre, reaction, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id, video_id) DO UPDATE SET
                    reaction = excluded.reaction,
                    genre = excluded.genre,
                    created_at = excluded.created_at
                """,
                (user_id, vid, (genre or "")[:80] or None, reaction, now),
            )
            conn.commit()
            return {"ok": True}
        finally:
            conn.close()
