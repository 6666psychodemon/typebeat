"""
TypeBeat Radio — local HTTP server + liquid-glass player.

Approach (PM/UX): Streamlit chrome fights full-bleed glass + centered square art,
so radio runs as a tiny stdlib HTTP server serving custom HTML/CSS/JS that reads
local SQLite. Catalog Streamlit app (`app.py`) stays untouched. Cursor Canvas is
for analytical artifacts, not this product UI.

Local audio (Compressor / polish.js):
  yt-dlp extracts audio into radio/data/audio_cache/ so Web Audio can process a
  same-origin <audio> element. YouTube IFrame alone cannot be tapped (cross-origin).
  Personal use only — may conflict with YouTube ToS; not for production shipping.

Deps (once):
  source venv/bin/activate
  pip install yt-dlp
  # ffmpeg recommended (Homebrew: brew install ffmpeg) — used by yt-dlp when needed

Run from repo root:
  source venv/bin/activate
  python -m radio
  # open http://127.0.0.1:8765

Invite / Google auth: see radio/AUTH.md and .env.example
"""

from __future__ import annotations

import html
import json
import mimetypes
import random
import secrets
import sqlite3
import sys
import threading
import time
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import audio_cache
from . import auth as radio_auth
from . import auth_db
from .genres import (
    DEFAULT_GENRE_ID,
    DEFAULT_MAX_VIEWS,
    DEFAULT_MIN_VIEWS,
    DEFAULT_VIEW_TIER_ID,
    QUEUE_BATCH,
    genre_list_public,
    get_genre,
    get_view_tier,
    taxonomy_public,
    view_tiers_public,
)
from .queue import (
    DB_PATH,
    INDEX_GENRE_VIEWS,
    INDEX_VIEWS_VID,
    WARM_QUEUE_PATH,
    build_queue_page,
    build_warm_queue,
    connect,
    connect_write,
    load_warm_queue,
    missing_radio_indexes,
    warm_queue_response,
)

STATIC_DIR = Path(__file__).resolve().parent / "static"
DATA_DIR = Path(__file__).resolve().parent / "data"
EVENTS_LOG = DATA_DIR / "events.jsonl"
HOST = "127.0.0.1"
PORT = 8765

_index_ready = threading.Event()
_index_error: str | None = None
_views_index_ready = threading.Event()
_warm_lock = threading.Lock()
_warm_payload: dict | None = None
_events_lock = threading.Lock()


def _set_warm_memory(payload: dict | None) -> None:
    global _warm_payload
    with _warm_lock:
        _warm_payload = payload


def _get_warm_memory() -> dict | None:
    with _warm_lock:
        return _warm_payload


def _refresh_warm_memory_from_disk() -> dict | None:
    payload = warm_queue_response(shuffle=True)
    if payload:
        _set_warm_memory(payload)
    return payload


WARM_AUDIO_PREFETCH_N = 5


def _prefetch_warm_audio(tracks: list[dict], n: int = WARM_AUDIO_PREFETCH_N) -> None:
    """Kick yt-dlp cache for the first few warm ids (non-blocking)."""
    for t in (tracks or [])[:n]:
        vid = (t or {}).get("video_id")
        if vid:
            try:
                audio_cache.kick_prepare(vid)
            except Exception:  # noqa: BLE001
                pass


def _warm_playlist() -> None:
    """
    Ensure radio/data/warm_queue.json exists and is loaded into memory.
    Uses genre-indexed pulls when the All-station views index is still missing,
    so cold start never waits on a full beats SCAN.
    """
    try:
        existing = load_warm_queue()
        if existing and existing.get("tracks"):
            payload = warm_queue_response(shuffle=True)
            if payload:
                _set_warm_memory(payload)
                _prefetch_warm_audio(payload.get("tracks") or [])
                print(
                    f"  Warm queue: {len(payload['tracks'])} tracks "
                    f"from {WARM_QUEUE_PATH.name}",
                    flush=True,
                )

        # Rebuild / refresh in background (genre path is fast; deep path after index).
        built = build_warm_queue()
        tracks = built.get("tracks") or []
        if tracks:
            payload = warm_queue_response(shuffle=True)
            if payload:
                _set_warm_memory(payload)
                _prefetch_warm_audio(payload.get("tracks") or [])
                print(
                    f"  Warm queue refreshed ({built.get('source')}): "
                    f"{len(payload['tracks'])} tracks → {WARM_QUEUE_PATH}",
                    flush=True,
                )
        elif not existing:
            print("  ⚠️  Warm queue empty — first /api/queue may hit SQLite", flush=True)
    except Exception as exc:  # noqa: BLE001
        print(f"  ⚠️  Warm queue failed: {exc}", flush=True)


def _warm_index() -> None:
    global _index_error
    try:
        if not DB_PATH.exists():
            _index_error = f"Missing database at {DB_PATH}"
            return

        missing: list[str] = []
        try:
            conn = connect()
            try:
                missing = missing_radio_indexes(conn)
            finally:
                conn.close()
        except sqlite3.OperationalError as exc:
            # DB locked on open — proceed; warm file covers first play.
            print(f"  ⚠️  Index probe deferred (DB busy): {exc}", flush=True)
            return

        need_genre = INDEX_GENRE_VIEWS in missing
        need_views = INDEX_VIEWS_VID in missing

        if not missing:
            _views_index_ready.set()
            return

        # Genre index alone unblocks tagged stations + warm seed. Signal ready
        # before the (slow) views-index CREATE so /api/queue isn't stuck on 202.
        if need_genre:
            print("  Building genre/views index (one-time)…", flush=True)
            try:
                conn = connect_write()
                try:
                    conn.execute(
                        f"CREATE INDEX IF NOT EXISTS {INDEX_GENRE_VIEWS} ON beats(genre, views)"
                    )
                    conn.commit()
                finally:
                    conn.close()
            except sqlite3.OperationalError as exc:
                if "locked" not in str(exc).lower():
                    raise
                conn = connect()
                try:
                    still = missing_radio_indexes(conn)
                    if INDEX_GENRE_VIEWS in still:
                        _index_error = str(exc)
                        return
                finally:
                    conn.close()

        # Mark genre-ready before long views-index build.
        _index_ready.set()

        if need_views:
            print(
                "  Building views index for All station "
                "(one-time; warm queue covers cold start)…",
                flush=True,
            )
            # Harvester often holds the write lock — retry instead of one long stall.
            created = False
            last_err: str | None = None
            for attempt in range(1, 13):
                try:
                    # Short busy wait — harvester may hold the write lock for a while.
                    conn = connect_write(timeout=8.0)
                    try:
                        try:
                            conn.execute("PRAGMA journal_mode=WAL")
                            conn.execute("PRAGMA synchronous=NORMAL")
                        except sqlite3.Error:
                            pass
                        conn.execute(
                            f"CREATE INDEX IF NOT EXISTS {INDEX_VIEWS_VID} "
                            "ON beats(views, video_id)"
                        )
                        conn.commit()
                    finally:
                        conn.close()
                    created = True
                    break
                except sqlite3.OperationalError as exc:
                    last_err = str(exc)
                    if "locked" not in last_err.lower():
                        raise
                    wait = min(30.0, 2.0 * attempt)
                    print(
                        f"  ⚠️  Views index deferred (DB locked, try {attempt}/12) "
                        f"— retry in {wait:.0f}s",
                        flush=True,
                    )
                    time.sleep(wait)

            if created:
                _views_index_ready.set()
                print("  Views index ready.", flush=True)
                try:
                    build_warm_queue()
                    _refresh_warm_memory_from_disk()
                except Exception as exc:  # noqa: BLE001
                    print(f"  ⚠️  Post-index warm refresh: {exc}", flush=True)
            else:
                print(
                    "  ⚠️  Views index still missing"
                    + (f" ({last_err})" if last_err else "")
                    + " — serving warm queue for All",
                    flush=True,
                )
                try:
                    conn = connect()
                    try:
                        if INDEX_VIEWS_VID not in missing_radio_indexes(conn):
                            _views_index_ready.set()
                    finally:
                        conn.close()
                except sqlite3.OperationalError:
                    pass
        else:
            _views_index_ready.set()
    except Exception as exc:  # noqa: BLE001 — surface to /api/health
        _index_error = str(exc)
    finally:
        _index_ready.set()


class RadioHandler(BaseHTTPRequestHandler):
    server_version = "TypeBeatRadio/1.0"

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _send(
        self,
        code: int,
        body: bytes,
        content_type: str,
        *,
        extra_headers: list[tuple[str, str]] | None = None,
        location: str | None = None,
    ) -> None:
        self.send_response(code)
        if location:
            self.send_header("Location", location)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for key, value in extra_headers or []:
            self.send_header(key, value)
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _json(
        self,
        code: int,
        payload: dict | list,
        *,
        extra_headers: list[tuple[str, str]] | None = None,
    ) -> None:
        data = json.dumps(payload).encode("utf-8")
        self._send(
            code,
            data,
            "application/json; charset=utf-8",
            extra_headers=extra_headers,
        )

    def _redirect(
        self,
        location: str,
        *,
        extra_headers: list[tuple[str, str]] | None = None,
    ) -> None:
        self._send(
            302,
            b"",
            "text/plain",
            location=location,
            extra_headers=extra_headers,
        )

    def _read_json_body(self, max_bytes: int = 8_192) -> tuple[dict | None, str | None]:
        try:
            length = int(self.headers.get("Content-Length") or "0")
        except ValueError:
            length = 0
        if length <= 0 or length > max_bytes:
            return None, "invalid body size"
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None, "invalid json"
        if not isinstance(payload, dict):
            return None, "expected object"
        return payload, None

    def _admin_authorized(self, qs: dict) -> bool:
        token = (qs.get("token") or [None])[0]
        if not token:
            token = self.headers.get("X-Invite-Admin-Token")
        return radio_auth.check_admin_token(token)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)

        if path in ("/", "/index.html"):
            return self._serve_file(STATIC_DIR / "index.html")

        if path in ("/map", "/map.html"):
            return self._serve_file(STATIC_DIR / "map.html")

        if path == "/api/taxonomy":
            return self._json(200, taxonomy_public())

        if path.startswith("/static/"):
            rel = path[len("/static/") :]
            return self._serve_file(STATIC_DIR / rel)

        if path == "/api/auth/status":
            user = radio_auth.user_from_request(self.headers.get("Cookie"))
            status = radio_auth.auth_public_status()
            return self._json(
                200,
                {
                    **status,
                    "authenticated": bool(user),
                    "user": user,
                },
            )

        if path == "/api/me":
            user = radio_auth.user_from_request(self.headers.get("Cookie"))
            if not user:
                return self._json(401, {"authenticated": False})
            return self._json(200, {"authenticated": True, "user": user})

        if path == "/auth/google":
            if not radio_auth.google_configured():
                return self._redirect("/?auth=setup")
            state = secrets.token_urlsafe(24)
            return self._redirect(
                radio_auth.google_authorize_url(state),
                extra_headers=[
                    ("Set-Cookie", radio_auth.make_oauth_state_cookie(state)),
                ],
            )

        if path == "/auth/google/callback":
            return self._handle_google_callback(qs)

        if path == "/auth/logout":
            return self._redirect(
                "/",
                extra_headers=[
                    ("Set-Cookie", radio_auth.clear_session_cookie()),
                    ("Set-Cookie", radio_auth.clear_oauth_state_cookie()),
                ],
            )

        if path == "/admin/invites":
            return self._serve_admin_invites(qs)

        if path == "/api/genres":
            return self._json(
                200,
                {
                    "genres": genre_list_public(),
                    "default": DEFAULT_GENRE_ID,
                    "view_tiers": view_tiers_public(),
                    "default_view_tier": DEFAULT_VIEW_TIER_ID,
                },
            )

        if path == "/api/health":
            tools = audio_cache.tools_status()
            warm = _get_warm_memory() or load_warm_queue()
            auth_status = radio_auth.auth_public_status()
            return self._json(
                200,
                {
                    "ok": DB_PATH.exists() and _index_error is None,
                    "db": str(DB_PATH),
                    "db_exists": DB_PATH.exists(),
                    "index_ready": _index_ready.is_set(),
                    "views_index_ready": _views_index_ready.is_set(),
                    "index_error": _index_error,
                    "warm_queue": {
                        "ready": bool(warm and (warm.get("tracks") if isinstance(warm, dict) else True)),
                        "path": str(WARM_QUEUE_PATH),
                        "count": len((warm or {}).get("tracks") or [])
                        if isinstance(warm, dict)
                        else 0,
                    },
                    "local_audio": tools,
                    "auth": auth_status,
                },
            )

        if path == "/api/audio/tools":
            return self._json(200, audio_cache.tools_status())

        # GET /api/audio/<video_id>/info — cache status without downloading
        if path.startswith("/api/audio/") and path.endswith("/info"):
            video_id = path[len("/api/audio/") : -len("/info")]
            return self._json(200, audio_cache.audio_info(video_id))

        # GET /api/audio/<video_id> — ensure extract + stream same-origin audio
        if path.startswith("/api/audio/"):
            video_id = path[len("/api/audio/") :]
            if "/" in video_id or not video_id:
                return self._json(404, {"error": "not found"})
            if not audio_cache.valid_video_id(video_id):
                return self._json(400, {"error": "invalid video_id"})

            # Optional ?prepare=1 returns JSON after ensure (no body stream)
            # Optional ?kick=1 starts extract in background and returns immediately
            prepare_only = (qs.get("prepare") or ["0"])[0] in ("1", "true", "yes")
            kick_only = (qs.get("kick") or ["0"])[0] in ("1", "true", "yes")
            if kick_only:
                kicked = audio_cache.kick_prepare(video_id)
                status = 200 if kicked.get("ready") else 202
                return self._json(status, kicked)

            if prepare_only:
                result = audio_cache.ensure_audio(video_id, allow_partial=True)
                if not result.get("ok"):
                    return self._json(
                        502,
                        {
                            "error": result.get("error") or "audio extract failed",
                            "video_id": video_id,
                            "fallback": "iframe",
                        },
                    )
                return self._json(
                    200,
                    {
                        "ok": True,
                        "video_id": video_id,
                        "url": f"/api/audio/{video_id}",
                        "cached": result.get("cached"),
                        "partial": result.get("partial"),
                        "ext": result.get("ext"),
                    },
                )

            # Media GET — never block the worker pool on a full yt-dlp run.
            stream_path, _is_partial = audio_cache.find_streamable(video_id)
            if stream_path:
                return self._serve_audio_file(Path(stream_path))

            if not audio_cache.is_inflight(video_id):
                audio_cache.kick_prepare(video_id)

            stream_path = audio_cache.wait_streamable(video_id, timeout=20.0)
            if stream_path:
                return self._serve_audio_file(Path(stream_path))

            err = audio_cache.audio_info(video_id).get("error")
            return self._json(
                503,
                {
                    "error": err or "audio not ready — retry shortly",
                    "video_id": video_id,
                    "fallback": "iframe",
                },
            )

        if path == "/api/queue":
            if not DB_PATH.exists() and not (_get_warm_memory() or load_warm_queue()):
                return self._json(503, {"error": "typebeats.db not found — run scraper first"})

            genre = (qs.get("genre") or [DEFAULT_GENRE_ID])[0]
            if not get_genre(genre):
                genre = DEFAULT_GENRE_ID

            tier_id = (qs.get("tier") or qs.get("view_tier") or [DEFAULT_VIEW_TIER_ID])[0]
            tier = get_view_tier(tier_id)
            min_views = int(tier["min_views"])
            max_views = int(tier["max_views"])

            # Explicit min/max override named tier when provided.
            if "min_views" in qs:
                try:
                    min_views = max(1, int(qs["min_views"][0]))
                except ValueError:
                    pass
            if "max_views" in qs:
                try:
                    max_views = max(min_views, int(qs["max_views"][0]))
                except ValueError:
                    pass

            def _flag(name: str) -> bool:
                raw = (qs.get(name) or ["0"])[0].strip().lower()
                return raw in ("1", "true", "yes", "on")

            require_free = _flag("is_free") or _flag("free")
            require_ffp = _flag("free_for_profit") or _flag("ffp")
            require_prolific = _flag("prolific")
            want_warm = _flag("warm")
            force_live = _flag("live")

            max_age_months: int | None = None
            raw_age = (qs.get("max_age_months") or qs.get("age_months") or [None])[0]
            if raw_age not in (None, "", "0", "all", "none"):
                try:
                    max_age_months = max(1, min(int(raw_age), 120))
                except (TypeError, ValueError):
                    max_age_months = None
            # Alternate: published_after=YYYY-MM-DD → approximate months for queue builder.
            raw_after = (qs.get("published_after") or [None])[0]
            if max_age_months is None and raw_after:
                try:
                    from datetime import date as _date

                    after = _date.fromisoformat(str(raw_after)[:10])
                    days = max(0, (_date.today() - after).days)
                    if days > 0:
                        max_age_months = max(1, min(int(round(days / 30)), 120))
                except ValueError:
                    pass

            try:
                limit = int((qs.get("limit") or [str(QUEUE_BATCH)])[0])
            except ValueError:
                limit = QUEUE_BATCH
            cursor = (qs.get("cursor") or [None])[0] or None

            # Default All cold-start: serve warm playlist instantly (memory/file).
            # Avoids 30s+ full scans when idx_beats_views_vid is missing or DB locked.
            # Experimental filters (prolific / age) always hit live SQL.
            warm_eligible = (
                genre == "all"
                and tier["id"] == DEFAULT_VIEW_TIER_ID
                and min_views == DEFAULT_MIN_VIEWS
                and max_views == DEFAULT_MAX_VIEWS
                and not require_free
                and not require_ffp
                and not require_prolific
                and max_age_months is None
                and not cursor
            )
            if warm_eligible and not force_live:
                mem = _get_warm_memory()
                if mem and mem.get("tracks"):
                    tracks = list(mem["tracks"])
                    random.shuffle(tracks)
                    tracks = tracks[: max(1, min(limit, 200))]
                    _prefetch_warm_audio(tracks)
                    return self._json(
                        200,
                        {
                            "genre": "all",
                            "tier": tier["id"],
                            "max_views": max_views,
                            "min_views": min_views,
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
                            "warm_source": mem.get("warm_source") or "memory",
                            "audio_notes": {
                                "compression": "polish",
                                "local_audio": audio_cache.tools_status().get("ready"),
                                "detail": (
                                    "Polish needs same-origin audio via /api/audio/<id> "
                                    "(yt-dlp cache). YouTube IFrame alone is cross-origin "
                                    "and cannot be tapped; client falls back to iframe if "
                                    "extract fails."
                                ),
                            },
                        },
                    )
                disk = warm_queue_response(limit=limit, shuffle=True)
                if disk:
                    _set_warm_memory(disk)
                    disk["audio_notes"] = {
                        "compression": "polish",
                        "local_audio": audio_cache.tools_status().get("ready"),
                        "detail": (
                            "Polish needs same-origin audio via /api/audio/<id> "
                            "(yt-dlp cache). YouTube IFrame alone is cross-origin "
                            "and cannot be tapped; client falls back to iframe if "
                            "extract fails."
                        ),
                    }
                    _prefetch_warm_audio(disk.get("tracks") or [])
                    return self._json(200, disk)
                if want_warm:
                    return self._json(
                        202,
                        {
                            "status": "indexing",
                            "message": "Warm playlist not ready — retry shortly",
                        },
                    )

            if not DB_PATH.exists():
                return self._json(503, {"error": "typebeats.db not found — run scraper first"})

            if not _index_ready.is_set():
                # Still indexing — warm already tried above; ask client to retry.
                return self._json(
                    202,
                    {
                        "status": "indexing",
                        "message": "Building genre index for faster pulls — retry shortly",
                    },
                )
            if _index_error:
                return self._json(500, {"error": _index_error})

            try:
                page = build_queue_page(
                    genre,
                    max_views=max_views,
                    min_views=min_views,
                    limit=limit,
                    cursor=cursor,
                    require_free=require_free,
                    require_ffp=require_ffp,
                    require_prolific=require_prolific,
                    max_age_months=max_age_months,
                )
            except sqlite3.OperationalError as exc:
                # Concurrent harvester write lock — fall back to warm for All.
                if "locked" in str(exc).lower():
                    if warm_eligible:
                        disk = warm_queue_response(limit=limit, shuffle=True)
                        if disk:
                            disk["status"] = "warm_fallback"
                            disk["message"] = "Catalog busy — warm playlist"
                            return self._json(200, disk)
                    return self._json(
                        202,
                        {
                            "status": "indexing",
                            "message": "Catalog busy — retry shortly",
                        },
                    )
                return self._json(500, {"error": str(exc)})
            # Strip exact view counts from the player payload (ranges stay on chips).
            tracks = [
                {k: v for k, v in t.items() if k != "views"} for t in page["tracks"]
            ]
            return self._json(
                200,
                {
                    "genre": genre,
                    "tier": tier["id"],
                    "max_views": page.get("max_views", max_views),
                    "min_views": page.get("min_views", min_views),
                    "is_free": require_free,
                    "free_for_profit": require_ffp,
                    "prolific": require_prolific,
                    "max_age_months": max_age_months,
                    "published_after": page.get("published_after"),
                    "hq_mix": page.get("hq_mix", False),
                    "deep_mix": page.get("deep_mix", False),
                    "count": len(tracks),
                    "limit": page["limit"],
                    "cursor": page["cursor"],
                    "next_cursor": page["next_cursor"],
                    "has_more": page["has_more"],
                    "tracks": tracks,
                    "warm": False,
                    "audio_notes": {
                        "compression": "polish",
                        "local_audio": audio_cache.tools_status().get("ready"),
                        "detail": (
                            "Polish needs same-origin audio via /api/audio/<id> "
                            "(yt-dlp cache). YouTube IFrame alone is cross-origin "
                            "and cannot be tapped; client falls back to iframe if "
                            "extract fails."
                        ),
                    },
                },
            )

        self._json(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)

        if path == "/api/invite-request":
            payload, err = self._read_json_body(4_096)
            if err:
                return self._json(400, {"error": err})
            assert payload is not None
            result = auth_db.create_invite_request(
                str(payload.get("email") or ""),
                str(payload.get("note") or "") if payload.get("note") is not None else None,
            )
            code = 200 if result.get("ok") else 400
            return self._json(code, result)

        if path == "/api/reactions":
            user = radio_auth.user_from_request(self.headers.get("Cookie"))
            if not user:
                return self._json(401, {"error": "sign in required", "invite_required": True})
            payload, err = self._read_json_body(4_096)
            if err:
                return self._json(400, {"error": err})
            assert payload is not None
            result = auth_db.save_reaction(
                int(user["id"]),
                str(payload.get("video_id") or ""),
                str(payload.get("reaction") or ""),
                str(payload.get("genre") or "") or None,
            )
            code = 200 if result.get("ok") else 400
            return self._json(code, result)

        if path == "/admin/invites/grant":
            if not self._admin_authorized(qs):
                return self._json(401, {"error": "unauthorized"})
            payload, err = self._read_json_body(2_048)
            if err:
                return self._json(400, {"error": err})
            assert payload is not None
            email = str(payload.get("email") or "")
            result = auth_db.grant_invite(email)
            return self._json(200 if result.get("ok") else 400, result)

        if path == "/admin/invites/deny":
            if not self._admin_authorized(qs):
                return self._json(401, {"error": "unauthorized"})
            payload, err = self._read_json_body(2_048)
            if err:
                return self._json(400, {"error": err})
            assert payload is not None
            result = auth_db.deny_invite_request(str(payload.get("email") or ""))
            return self._json(200 if result.get("ok") else 400, result)

        if path != "/api/events":
            return self._json(404, {"error": "not found"})

        payload, err = self._read_json_body(8_192)
        if err:
            return self._json(400, {"error": err})
        assert payload is not None

        if "type" not in payload:
            return self._json(400, {"error": "expected object with type"})

        # Normalize preference-training fields (append-only; keep extras).
        record = dict(payload)
        record.setdefault("schema", 1)
        if not record.get("ts"):
            from datetime import datetime, timezone

            record["ts"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        for key in ("stay_ms", "listen_ms"):
            raw = record.get(key)
            try:
                record[key] = max(0, int(raw))
            except (TypeError, ValueError):
                record[key] = 0
        if "listen_ms" not in payload and "stay_ms" in payload:
            record["listen_ms"] = record["stay_ms"]
        if record.get("device_id") is not None:
            record["device_id"] = str(record["device_id"])[:80] or None
        for key in ("video_id", "genre", "tier", "type", "audio_mode", "reason"):
            if key in record and record[key] is not None:
                record[key] = str(record[key])[:120]
        if record.get("type") == "dead_cover" or record.get("dead_cover"):
            record["dead_cover"] = True

        user = radio_auth.user_from_request(self.headers.get("Cookie"))
        if user:
            record["user_id"] = int(user["id"])
            record["user_email"] = user.get("email")

        line = json.dumps(record, ensure_ascii=False) + "\n"
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            with _events_lock:
                with EVENTS_LOG.open("a", encoding="utf-8") as fh:
                    fh.write(line)
        except OSError as exc:
            return self._json(500, {"error": str(exc)})

        return self._send(204, b"", "text/plain")

    def _handle_google_callback(self, qs: dict) -> None:
        err = (qs.get("error") or [None])[0]
        if err:
            return self._redirect(f"/?auth=error&msg={urllib.parse.quote(str(err)[:120])}")

        if not radio_auth.google_configured():
            return self._redirect("/?auth=setup")

        code = (qs.get("code") or [None])[0]
        state = (qs.get("state") or [None])[0]
        cookies = radio_auth.parse_cookies(self.headers.get("Cookie"))
        expected = cookies.get(radio_auth.OAUTH_STATE_COOKIE)
        clear_state = ("Set-Cookie", radio_auth.clear_oauth_state_cookie())

        if not code or not state or not expected or state != expected:
            return self._redirect(
                "/?auth=error&msg=" + urllib.parse.quote("Invalid OAuth state"),
                extra_headers=[clear_state],
            )

        try:
            google_user = radio_auth.exchange_code_for_user(str(code))
            result = radio_auth.redeem_google_login(google_user)
        except Exception as exc:  # noqa: BLE001
            return self._redirect(
                "/?auth=error&msg=" + urllib.parse.quote(str(exc)[:160]),
                extra_headers=[clear_state],
            )

        if not result.get("ok"):
            msg = result.get("error") or "No invite for this Google account"
            return self._redirect(
                "/?auth=denied&msg=" + urllib.parse.quote(str(msg)[:160]),
                extra_headers=[clear_state],
            )

        user = result["user"]
        return self._redirect(
            "/?auth=ok",
            extra_headers=[
                clear_state,
                ("Set-Cookie", radio_auth.make_session_cookie(user)),
            ],
        )

    def _serve_admin_invites(self, qs: dict) -> None:
        if not radio_auth.invite_admin_token():
            body = (
                "<!doctype html><meta charset=utf-8><title>Admin</title>"
                "<body style='font-family:system-ui;background:#0c0d10;color:#e8dcc8;padding:2rem'>"
                "<p>Set <code>INVITE_ADMIN_TOKEN</code> in <code>.env</code> to enable this page.</p>"
                "</body>"
            ).encode("utf-8")
            return self._send(503, body, "text/html; charset=utf-8")

        if not self._admin_authorized(qs):
            body = (
                "<!doctype html><meta charset=utf-8><title>Admin</title>"
                "<body style='font-family:system-ui;background:#0c0d10;color:#e8dcc8;padding:2rem'>"
                "<p>Unauthorized. Pass <code>?token=…</code> or header "
                "<code>X-Invite-Admin-Token</code>.</p>"
                "</body>"
            ).encode("utf-8")
            return self._send(401, body, "text/html; charset=utf-8")

        token = (qs.get("token") or [""])[0]
        wants_json = (qs.get("format") or [""])[0] == "json" or "application/json" in (
            self.headers.get("Accept") or ""
        )
        requests = auth_db.list_invite_requests()
        invites = auth_db.list_invites()
        if wants_json:
            return self._json(200, {"requests": requests, "invites": invites})

        def rows_html(items: list[dict], kind: str) -> str:
            if not items:
                return "<p class='empty'>(none)</p>"
            bits = ["<table><thead><tr><th>ID</th><th>Status</th><th>Email</th><th>Note</th><th></th></tr></thead><tbody>"]
            for r in items:
                email = html.escape(str(r.get("email") or ""))
                note = html.escape(str(r.get("note") or ""))
                status = html.escape(str(r.get("status") or ""))
                rid = html.escape(str(r.get("id") or ""))
                actions = ""
                if kind == "requests" and r.get("status") == "pending":
                    actions = (
                        f"<button type='button' data-act='grant' data-email='{email}'>Grant</button> "
                        f"<button type='button' data-act='deny' data-email='{email}'>Deny</button>"
                    )
                bits.append(
                    f"<tr><td>{rid}</td><td>{status}</td><td>{email}</td>"
                    f"<td>{note}</td><td>{actions}</td></tr>"
                )
            bits.append("</tbody></table>")
            return "".join(bits)

        page = f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Invite Admin</title>
<style>
  body {{ margin:0; font-family: "DM Sans", system-ui, sans-serif; background:#0c0d10; color:#e8dcc8; }}
  main {{ max-width: 920px; margin: 0 auto; padding: 1.5rem 1rem 3rem; }}
  h1 {{ font-size: 1.1rem; letter-spacing: 0.12em; text-transform: uppercase; font-weight: 600; }}
  h2 {{ font-size: 0.75rem; letter-spacing: 0.1em; text-transform: uppercase; color: rgba(232,220,200,0.55); margin-top: 2rem; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.9rem; }}
  th, td {{ text-align: left; padding: 0.45rem 0.35rem; border-bottom: 1px solid rgba(255,255,255,0.08); vertical-align: top; }}
  th {{ font-size: 0.65rem; letter-spacing: 0.08em; text-transform: uppercase; color: rgba(232,220,200,0.45); }}
  button {{ appearance: none; border: 1px solid rgba(196,165,116,0.35); background: rgba(255,255,255,0.06);
    color: #e8dcc8; border-radius: 999px; padding: 0.25rem 0.7rem; cursor: pointer; font-size: 0.75rem;
    letter-spacing: 0.06em; text-transform: uppercase; }}
  button:hover {{ background: rgba(196,165,116,0.2); }}
  .empty {{ color: rgba(232,220,200,0.4); }}
  .grant-row {{ display:flex; gap:0.5rem; margin-top:1rem; flex-wrap:wrap; }}
  input {{ background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.12); color:#e8dcc8;
    border-radius: 10px; padding: 0.45rem 0.7rem; min-width: 220px; }}
  code {{ color: #c4a574; }}
</style>
</head><body><main>
  <h1>Invite Admin</h1>
  <p style="opacity:0.65;font-size:0.9rem">Local founder tool. Prefer CLI: <code>python -m radio.invite_admin list|grant|deny</code></p>
  <div class="grant-row">
    <input id="grant-email" type="email" placeholder="email@example.com" />
    <button type="button" id="grant-btn">Grant Invite</button>
  </div>
  <h2>Requests</h2>
  {rows_html(requests, "requests")}
  <h2>Invites</h2>
  {rows_html(invites, "invites")}
<script>
const TOKEN = {json.dumps(token)};
async function act(kind, email) {{
  const res = await fetch('/admin/invites/' + kind + '?token=' + encodeURIComponent(TOKEN), {{
    method: 'POST',
    headers: {{ 'Content-Type': 'application/json', 'X-Invite-Admin-Token': TOKEN }},
    body: JSON.stringify({{ email }}),
  }});
  const data = await res.json().catch(() => ({{}}));
  if (!res.ok || data.ok === false) {{
    alert(data.error || ('Failed: ' + res.status));
    return;
  }}
  location.reload();
}}
document.querySelectorAll('[data-act]').forEach((btn) => {{
  btn.addEventListener('click', () => act(btn.dataset.act, btn.dataset.email));
}});
document.getElementById('grant-btn').addEventListener('click', () => {{
  const email = document.getElementById('grant-email').value.trim();
  if (email) act('grant', email);
}});
</script>
</main></body></html>
"""
        return self._send(200, page.encode("utf-8"), "text/html; charset=utf-8")

    def _serve_file(self, file_path: Path) -> None:
        # Prevent path escape
        try:
            resolved = file_path.resolve()
            if not str(resolved).startswith(str(STATIC_DIR.resolve())):
                self._json(403, {"error": "forbidden"})
                return
        except OSError:
            self._json(404, {"error": "not found"})
            return

        if not resolved.is_file():
            self._json(404, {"error": "not found"})
            return

        ctype = mimetypes.guess_type(str(resolved))[0] or "application/octet-stream"
        if resolved.suffix == ".js":
            ctype = "application/javascript; charset=utf-8"
        elif resolved.suffix == ".css":
            ctype = "text/css; charset=utf-8"
        elif resolved.suffix == ".html":
            ctype = "text/html; charset=utf-8"
        self._send(200, resolved.read_bytes(), ctype)

    def _serve_audio_file(self, file_path: Path) -> None:
        """Serve cached audio with Range support (HTMLMediaElement seeking)."""
        try:
            resolved = file_path.resolve()
            cache_root = audio_cache.CACHE_DIR.resolve()
            if not str(resolved).startswith(str(cache_root)):
                self._json(403, {"error": "forbidden"})
                return
        except OSError:
            self._json(404, {"error": "not found"})
            return

        if not resolved.is_file():
            self._json(404, {"error": "not found"})
            return

        audio_cache.touch(resolved)
        size = resolved.stat().st_size
        ctype = audio_cache.mime_for(resolved)
        range_header = self.headers.get("Range")

        if range_header and range_header.startswith("bytes="):
            try:
                spec = range_header[6:].split(",")[0].strip()
                start_s, _, end_s = spec.partition("-")
                start = int(start_s) if start_s else 0
                end = int(end_s) if end_s else size - 1
                end = min(end, size - 1)
                if start < 0 or start > end or start >= size:
                    self.send_response(416)
                    self.send_header("Content-Range", f"bytes */{size}")
                    self.end_headers()
                    return
                length = end - start + 1
                self.send_response(206)
                self.send_header("Content-Type", ctype)
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
                self.send_header("Content-Length", str(length))
                self.send_header("Cache-Control", "private, max-age=3600")
                self.end_headers()
                with resolved.open("rb") as fh:
                    fh.seek(start)
                    remaining = length
                    while remaining > 0:
                        chunk = fh.read(min(65536, remaining))
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        remaining -= len(chunk)
                return
            except (ValueError, OSError):
                pass

        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(size))
        self.send_header("Cache-Control", "private, max-age=3600")
        self.end_headers()
        with resolved.open("rb") as fh:
            while True:
                chunk = fh.read(65536)
                if not chunk:
                    break
                self.wfile.write(chunk)


def main() -> None:
    radio_auth.load_dotenv()
    auth_db.init_db()

    if not DB_PATH.exists():
        print(f"⚠️  Database not found at {DB_PATH}")
        print("   Run the scraper / ensure typebeats.db is in the repo root.")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    # Warm playlist first so /api/queue is instant even while indexes build.
    threading.Thread(target=_warm_playlist, daemon=True, name="warm-playlist").start()
    threading.Thread(target=_warm_index, daemon=True, name="warm-index").start()

    ThreadingHTTPServer.allow_reuse_address = True
    server = ThreadingHTTPServer((HOST, PORT), RadioHandler)
    url = f"http://{HOST}:{PORT}"
    tools = audio_cache.tools_status()
    auth_status = radio_auth.auth_public_status()
    print(f"TypeBeat Radio → {url}", flush=True)
    print(
        "  Queue: /api/queue?genre=all&tier=all  "
        f"(views {DEFAULT_MIN_VIEWS}–{DEFAULT_MAX_VIEWS}; optional is_free / free_for_profit)",
        flush=True,
    )
    print(
        f"  Warm: {WARM_QUEUE_PATH} (instant All first page; ?live=1 for DB)",
        flush=True,
    )
    print(
        f"  Local audio: /api/audio/<video_id> (yt-dlp={'yes' if tools.get('ready') else 'MISSING'})",
        flush=True,
    )
    if not tools.get("ready"):
        print("  ⚠️  Install yt-dlp for Level polish: pip install yt-dlp", flush=True)
    if not tools.get("ffmpeg"):
        print("  ⚠️  ffmpeg not on PATH — brew install ffmpeg (recommended)", flush=True)
    print(f"  Events log: POST /api/events → {EVENTS_LOG}", flush=True)
    print(f"  Auth DB: {auth_db.AUTH_DB_PATH}", flush=True)
    if auth_status["google_configured"]:
        print(f"  Google OAuth: configured → {auth_status['oauth_redirect_uri']}", flush=True)
    else:
        print(
            "  Google OAuth: not configured (set GOOGLE_CLIENT_* in .env) — invite request still works",
            flush=True,
        )
    if auth_status["admin_configured"]:
        print("  Admin: /admin/invites?token=…  (INVITE_ADMIN_TOKEN)", flush=True)
    else:
        print("  Admin: CLI python -m radio.invite_admin list|grant|deny", flush=True)
    print("  Catalog (unchanged): streamlit run app.py", flush=True)
    print("  Ctrl+C to stop", flush=True)
    try:
        webbrowser.open(url)
    except Exception:
        pass
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        server.server_close()


if __name__ == "__main__":
    main()
