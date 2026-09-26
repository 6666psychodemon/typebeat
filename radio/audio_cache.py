"""
Local-only YouTube audio extract for TypeBeat Radio Polish.

Uses yt-dlp (+ ffmpeg if needed) to pull an audio-only file into
radio/data/audio_cache/ so the browser can play a same-origin <audio>
element and Web Audio can process it.

Personal / local tooling only — downloading YouTube streams may violate
YouTube ToS. Do not ship this as a production public feature as-is.

Does not touch typebeats.db (safe alongside the harvester).
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path

CACHE_DIR = Path(__file__).resolve().parent / "data" / "audio_cache"
MAX_CACHE_BYTES = 400 * 1024 * 1024  # ~400 MB
MAX_CACHE_FILES = 48
DOWNLOAD_TIMEOUT_S = 120
MAX_CONCURRENT_DOWNLOADS = 3
# Report ready + allow progressive serve while yt-dlp is still writing.
MIN_PARTIAL_BYTES = 384 * 1024
MIN_SERVE_BYTES = 256 * 1024
ERROR_RETRY_S = 45

_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
_SKIP_SUFFIXES = {".part", ".ytdl", ".temp", ".frag", ".tmp"}

_lock = threading.Lock()
_inflight: dict[str, threading.Event] = {}
_errors: dict[str, tuple[str, float]] = {}  # msg, monotonic ts
_download_slots = threading.Semaphore(MAX_CONCURRENT_DOWNLOADS)
_ytdlp_path: str | None | bool = False  # False = unprobed
_ffmpeg_ok: bool | None = None
_node_ok: bool | None = None


def valid_video_id(video_id: str) -> bool:
    return bool(video_id and _VIDEO_ID_RE.match(video_id))


def _probe_ytdlp() -> str | None:
    global _ytdlp_path
    if _ytdlp_path is not False:
        return _ytdlp_path  # type: ignore[return-value]
    path = shutil.which("yt-dlp")
    if not path:
        # Project venv (server often started with system python / odd PATH)
        for candidate in (
            Path(__file__).resolve().parent.parent / "venv" / "bin" / "yt-dlp",
            Path(__file__).resolve().parent.parent / ".venv" / "bin" / "yt-dlp",
        ):
            if candidate.is_file() and os.access(candidate, os.X_OK):
                path = str(candidate)
                break
    if not path:
        try:
            import yt_dlp  # noqa: F401

            path = "python-module"
        except ImportError:
            path = None
    _ytdlp_path = path
    return path


def _probe_ffmpeg() -> bool:
    global _ffmpeg_ok
    if _ffmpeg_ok is not None:
        return _ffmpeg_ok
    _ffmpeg_ok = shutil.which("ffmpeg") is not None
    return _ffmpeg_ok


def _probe_node() -> bool:
    global _node_ok
    if _node_ok is not None:
        return _node_ok
    _node_ok = shutil.which("node") is not None
    return _node_ok


def tools_status() -> dict:
    ytdlp = _probe_ytdlp()
    return {
        "ytdlp": bool(ytdlp),
        "ytdlp_path": None if ytdlp == "python-module" else ytdlp,
        "ytdlp_via": "module" if ytdlp == "python-module" else ("bin" if ytdlp else None),
        "ffmpeg": _probe_ffmpeg(),
        "node": _probe_node(),
        "cache_dir": str(CACHE_DIR),
        "ready": bool(ytdlp),
    }


def _ext_candidates(video_id: str) -> list[Path]:
    # Common yt-dlp audio outputs browsers can decode
    return [
        CACHE_DIR / f"{video_id}.m4a",
        CACHE_DIR / f"{video_id}.webm",
        CACHE_DIR / f"{video_id}.opus",
        CACHE_DIR / f"{video_id}.mp3",
        CACHE_DIR / f"{video_id}.mp4",
        CACHE_DIR / f"{video_id}.ogg",
    ]


def _is_playable_file(path: Path, *, min_bytes: int = 1024) -> bool:
    if not path.is_file():
        return False
    if any(path.name.endswith(suf) for suf in _SKIP_SUFFIXES):
        return False
    try:
        return path.stat().st_size >= min_bytes
    except OSError:
        return False


def find_cached(video_id: str) -> Path | None:
    if not valid_video_id(video_id):
        return None
    for path in _ext_candidates(video_id):
        if _is_playable_file(path):
            return path
    # Any leftover from yt-dlp (e.g. .mp4 audio-only)
    if CACHE_DIR.is_dir():
        for path in CACHE_DIR.glob(f"{video_id}.*"):
            if _is_playable_file(path):
                return path
    return None


def find_partial(video_id: str, *, min_bytes: int = MIN_PARTIAL_BYTES) -> Path | None:
    """Growing .part file while yt-dlp is still extracting."""
    if not valid_video_id(video_id) or not CACHE_DIR.is_dir():
        return None
    best: Path | None = None
    best_size = 0
    for path in CACHE_DIR.glob(f"{video_id}*"):
        if not path.is_file():
            continue
        name = path.name
        is_part = name.endswith(".part") or ".part." in name
        if not is_part:
            continue
        try:
            size = path.stat().st_size
        except OSError:
            continue
        if size >= min_bytes and size > best_size:
            best = path
            best_size = size
    return best


def find_streamable(video_id: str) -> tuple[Path | None, bool]:
    """
    Return (path, partial).
    partial=True when serving an in-progress .part file.
    """
    complete = find_cached(video_id)
    if complete:
        return complete, False
    partial = find_partial(video_id, min_bytes=MIN_SERVE_BYTES)
    if partial:
        return partial, True
    return None, False


def _evict_if_needed() -> None:
    if not CACHE_DIR.is_dir():
        return
    files = [p for p in CACHE_DIR.iterdir() if p.is_file() and not p.name.endswith(".part")]
    files.sort(key=lambda p: p.stat().st_mtime)
    total = sum(p.stat().st_size for p in files)
    while files and (len(files) > MAX_CACHE_FILES or total > MAX_CACHE_BYTES):
        victim = files.pop(0)
        try:
            size = victim.stat().st_size
            victim.unlink(missing_ok=True)
            total -= size
        except OSError:
            break


def _ytdlp_ydl_opts(outtmpl: str) -> dict:
    opts: dict = {
        "format": "bestaudio[ext=m4a]/bestaudio/best",
        "outtmpl": outtmpl,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "noplaylist": True,
        "retries": 2,
        "fragment_retries": 2,
        "socket_timeout": 30,
        "paths": {"home": str(CACHE_DIR)},
        "extractor_args": {"youtube": {"player_client": ["android", "web"]}},
    }
    if _probe_node():
        opts["js_runtimes"] = {"node": {}}
        opts["remote_components"] = ["ejs:github"]
    return opts


def _ytdlp_cli_args(outtmpl: str, url: str) -> list[str]:
    ytdlp = _probe_ytdlp()
    if not ytdlp or ytdlp == "python-module":
        raise RuntimeError("yt-dlp not available")
    cmd = [
        ytdlp,
        "--no-playlist",
        "-f",
        "bestaudio[ext=m4a]/bestaudio/best",
        "-o",
        outtmpl,
        "--quiet",
        "--no-warnings",
        "--retries",
        "2",
        "--extractor-args",
        "youtube:player_client=android,web",
    ]
    if _probe_node():
        cmd.extend(["--js-runtimes", "node", "--remote-components", "ejs:github"])
    cmd.append(url)
    return cmd


def is_inflight(video_id: str) -> bool:
    with _lock:
        return video_id in _inflight


def wait_streamable(video_id: str, *, timeout: float = 18.0) -> Path | None:
    """Poll cache/partial files for up to timeout seconds (for media GET)."""
    deadline = time.monotonic() + max(0.5, timeout)
    while time.monotonic() < deadline:
        path, _partial = find_streamable(video_id)
        if path:
            return path
        time.sleep(0.22)
    path, _partial = find_streamable(video_id)
    return path


def _download(video_id: str) -> Path:
    _download_slots.acquire()
    try:
        return _download_inner(video_id)
    finally:
        _download_slots.release()


def _download_inner(video_id: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _evict_if_needed()

    url = f"https://www.youtube.com/watch?v={video_id}"
    outtmpl = str(CACHE_DIR / f"{video_id}.%(ext)s")

    ytdlp = _probe_ytdlp()
    if not ytdlp:
        raise RuntimeError(
            "yt-dlp not installed — run: source venv/bin/activate && pip install yt-dlp"
        )

    if ytdlp == "python-module":
        import yt_dlp

        with yt_dlp.YoutubeDL(_ytdlp_ydl_opts(outtmpl)) as ydl:
            ydl.download([url])
    else:
        cmd = _ytdlp_cli_args(outtmpl, url)
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=DOWNLOAD_TIMEOUT_S,
            check=False,
        )
        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or "yt-dlp failed").strip()
            raise RuntimeError(err[:500])

    path = find_cached(video_id)
    if not path:
        raise RuntimeError("yt-dlp finished but no playable file found in cache")
    return path


def _store_error(video_id: str, msg: str) -> None:
    with _lock:
        _errors[video_id] = (msg[:500], time.monotonic())


def _peek_error_unlocked(video_id: str) -> str | None:
    entry = _errors.get(video_id)
    if not entry:
        return None
    msg, ts = entry
    if time.monotonic() - ts > ERROR_RETRY_S:
        _errors.pop(video_id, None)
        return None
    return msg


def _get_error(video_id: str) -> str | None:
    with _lock:
        return _peek_error_unlocked(video_id)


def _clear_error(video_id: str) -> None:
    with _lock:
        _errors.pop(video_id, None)


def ensure_audio(video_id: str, *, allow_partial: bool = False) -> dict:
    """
    Ensure audio is cached. Blocks until ready or error.
    Returns {ok, path, video_id, error, cached, partial}.
    """
    if not valid_video_id(video_id):
        return {"ok": False, "video_id": video_id, "error": "invalid video_id", "path": None}

    existing = find_cached(video_id)
    if existing:
        return {
            "ok": True,
            "video_id": video_id,
            "path": str(existing),
            "cached": True,
            "partial": False,
            "error": None,
            "ext": existing.suffix.lstrip("."),
        }

    if allow_partial:
        partial, is_partial = find_streamable(video_id)
        if partial and is_partial:
            return {
                "ok": True,
                "video_id": video_id,
                "path": str(partial),
                "cached": False,
                "partial": True,
                "error": None,
                "ext": partial.suffix.lstrip(".").replace("part", "mp4"),
            }

    with _lock:
        event = _inflight.get(video_id)
        if event is None:
            event = threading.Event()
            _inflight[video_id] = event
            starter = True
        else:
            starter = False

    if not starter:
        # Wait for the in-flight download (other request)
        deadline = time.monotonic() + DOWNLOAD_TIMEOUT_S + 5
        while time.monotonic() < deadline:
            existing = find_cached(video_id)
            if existing:
                return {
                    "ok": True,
                    "video_id": video_id,
                    "path": str(existing),
                    "cached": True,
                    "partial": False,
                    "error": None,
                    "ext": existing.suffix.lstrip("."),
                }
            if allow_partial:
                partial = find_partial(video_id, min_bytes=MIN_SERVE_BYTES)
                if partial:
                    return {
                        "ok": True,
                        "video_id": video_id,
                        "path": str(partial),
                        "cached": False,
                        "partial": True,
                        "error": None,
                        "ext": "mp4",
                    }
            if event.wait(timeout=0.35):
                break
        existing = find_cached(video_id)
        if existing:
            return {
                "ok": True,
                "video_id": video_id,
                "path": str(existing),
                "cached": True,
                "partial": False,
                "error": None,
                "ext": existing.suffix.lstrip("."),
            }
        return {
            "ok": False,
            "video_id": video_id,
            "path": None,
            "cached": False,
            "partial": False,
            "error": _get_error(video_id) or "download failed",
        }

    try:
        path = _download(video_id)
        _clear_error(video_id)
        return {
            "ok": True,
            "video_id": video_id,
            "path": str(path),
            "cached": False,
            "partial": False,
            "error": None,
            "ext": path.suffix.lstrip("."),
        }
    except Exception as exc:  # noqa: BLE001 — surface to API
        msg = str(exc)[:500]
        _store_error(video_id, msg)
        return {
            "ok": False,
            "video_id": video_id,
            "path": None,
            "cached": False,
            "partial": False,
            "error": msg,
        }
    finally:
        with _lock:
            ev = _inflight.pop(video_id, None)
            if ev:
                ev.set()


def kick_prepare(video_id: str) -> dict:
    """
    Start extract in a background thread if needed; never blocks on yt-dlp.
    Returns immediately with ready/pending status.
    """
    if not valid_video_id(video_id):
        return {"ok": False, "ready": False, "pending": False, "error": "invalid video_id", "video_id": video_id}

    existing = find_cached(video_id)
    if existing:
        return {
            "ok": True,
            "ready": True,
            "pending": False,
            "video_id": video_id,
            "url": f"/api/audio/{video_id}",
            "cached": True,
            "partial": False,
            "ext": existing.suffix.lstrip("."),
            "error": None,
        }

    partial = find_partial(video_id, min_bytes=MIN_PARTIAL_BYTES)
    if partial:
        try:
            size = partial.stat().st_size
        except OSError:
            size = 0
        return {
            "ok": True,
            "ready": True,
            "pending": True,
            "partial": True,
            "video_id": video_id,
            "url": f"/api/audio/{video_id}",
            "bytes": size,
            "error": None,
        }

    with _lock:
        already = video_id in _inflight
        err = _peek_error_unlocked(video_id)

    if already:
        return {
            "ok": True,
            "ready": False,
            "pending": True,
            "video_id": video_id,
            "url": f"/api/audio/{video_id}",
            "error": err,
        }

    # Allow retry after a failed extract (e.g. stale 403 before node runtime fix).
    _clear_error(video_id)

    def _run() -> None:
        ensure_audio(video_id)

    threading.Thread(target=_run, name=f"audio-prep-{video_id}", daemon=True).start()
    return {
        "ok": True,
        "ready": False,
        "pending": True,
        "video_id": video_id,
        "url": f"/api/audio/{video_id}",
        "error": None,
    }


def audio_info(video_id: str) -> dict:
    if not valid_video_id(video_id):
        return {"ok": False, "ready": False, "error": "invalid video_id", "video_id": video_id}

    path = find_cached(video_id)
    with _lock:
        inflight = video_id in _inflight
        err = _peek_error_unlocked(video_id)

    if path:
        return {
            "ok": True,
            "ready": True,
            "video_id": video_id,
            "url": f"/api/audio/{video_id}",
            "ext": path.suffix.lstrip("."),
            "bytes": path.stat().st_size,
            "inflight": False,
            "partial": False,
            "error": None,
        }

    partial = find_partial(video_id, min_bytes=MIN_PARTIAL_BYTES)
    if partial:
        try:
            size = partial.stat().st_size
        except OSError:
            size = 0
        return {
            "ok": True,
            "ready": True,
            "video_id": video_id,
            "url": f"/api/audio/{video_id}",
            "ext": "mp4",
            "bytes": size,
            "inflight": inflight,
            "partial": True,
            "error": None,
        }

    return {
        "ok": True,
        "ready": False,
        "video_id": video_id,
        "url": f"/api/audio/{video_id}",
        "inflight": inflight,
        "partial": False,
        "error": err,
    }


def mime_for(path: Path) -> str:
    name = path.name.lower()
    if name.endswith(".part"):
        # yt-dlp .mp4.part → treat as mp4 for the browser
        base = name[:-5]
        ext = Path(base).suffix.lower()
    else:
        ext = path.suffix.lower()
    return {
        ".m4a": "audio/mp4",
        ".mp4": "audio/mp4",
        ".webm": "audio/webm",
        ".opus": "audio/ogg",
        ".ogg": "audio/ogg",
        ".mp3": "audio/mpeg",
    }.get(ext, "application/octet-stream")


def clear_error(video_id: str) -> None:
    _clear_error(video_id)


# Touch mtime helper for LRU
def touch(path: Path) -> None:
    try:
        now = time.time()
        path.touch()
        # some FS ignore empty touch — set explicitly
        import os

        os.utime(path, (now, now))
    except OSError:
        pass
