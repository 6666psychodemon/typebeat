"""
Google OAuth + signed session cookies for TypeBeat Radio.

Env (see .env.example / AUTH.md):
  GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, OAUTH_REDIRECT_URI, SESSION_SECRET
  INVITE_ADMIN_TOKEN (local admin page)
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from . import auth_db

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = REPO_ROOT / ".env"

SESSION_COOKIE = "tb_session"
SESSION_MAX_AGE = 60 * 60 * 24 * 30  # 30 days
OAUTH_STATE_COOKIE = "tb_oauth_state"
OAUTH_STATE_MAX_AGE = 600

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"

_env_loaded = False


def load_dotenv(path: Path | None = None) -> None:
    """Minimal .env loader (no python-dotenv dependency)."""
    global _env_loaded
    if _env_loaded:
        return
    env_file = path or ENV_PATH
    if env_file.is_file():
        try:
            text = env_file.read_text(encoding="utf-8")
        except OSError:
            text = ""
        for line in text.splitlines():
            raw = line.strip()
            if not raw or raw.startswith("#") or "=" not in raw:
                continue
            key, _, val = raw.partition("=")
            key = key.strip()
            val = val.strip().strip("'").strip('"')
            if key and key not in os.environ:
                os.environ[key] = val
    _env_loaded = True


def _cfg(name: str, default: str = "") -> str:
    load_dotenv()
    return (os.environ.get(name) or default).strip()


def google_configured() -> bool:
    return bool(_cfg("GOOGLE_CLIENT_ID") and _cfg("GOOGLE_CLIENT_SECRET"))


def oauth_redirect_uri() -> str:
    return _cfg(
        "OAUTH_REDIRECT_URI",
        "http://127.0.0.1:8765/auth/google/callback",
    )


def session_secret() -> str:
    secret = _cfg("SESSION_SECRET")
    if secret:
        return secret
    # Dev fallback — sessions reset across restarts if no secret set.
    # Prefer setting SESSION_SECRET in .env for stable cookies.
    fallback = _cfg("_TB_DEV_SESSION_SECRET")
    if not fallback:
        fallback = secrets.token_urlsafe(32)
        os.environ["_TB_DEV_SESSION_SECRET"] = fallback
    return fallback


def invite_admin_token() -> str:
    return _cfg("INVITE_ADMIN_TOKEN")


def auth_public_status() -> dict[str, Any]:
    return {
        "google_configured": google_configured(),
        "oauth_redirect_uri": oauth_redirect_uri(),
        "admin_configured": bool(invite_admin_token()),
    }


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)


def sign_payload(payload: dict[str, Any], max_age: int = SESSION_MAX_AGE) -> str:
    body = dict(payload)
    body["exp"] = int(time.time()) + max_age
    raw = json.dumps(body, separators=(",", ":"), sort_keys=True).encode("utf-8")
    sig = hmac.new(session_secret().encode("utf-8"), raw, hashlib.sha256).digest()
    return f"{_b64url(raw)}.{_b64url(sig)}"


def verify_payload(token: str | None) -> dict[str, Any] | None:
    if not token or "." not in token:
        return None
    try:
        raw_b64, sig_b64 = token.split(".", 1)
        raw = _b64url_decode(raw_b64)
        expected = hmac.new(
            session_secret().encode("utf-8"), raw, hashlib.sha256
        ).digest()
        if not hmac.compare_digest(expected, _b64url_decode(sig_b64)):
            return None
        payload = json.loads(raw.decode("utf-8"))
        if int(payload.get("exp") or 0) < int(time.time()):
            return None
        return payload
    except (ValueError, json.JSONDecodeError, TypeError):
        return None


def make_session_cookie(user: dict[str, Any]) -> str:
    token = sign_payload(
        {
            "uid": int(user["id"]),
            "email": user["email"],
            "name": user.get("name") or "",
        }
    )
    return _cookie_header(
        SESSION_COOKIE,
        token,
        max_age=SESSION_MAX_AGE,
        http_only=True,
    )


def clear_session_cookie() -> str:
    return _cookie_header(SESSION_COOKIE, "", max_age=0, http_only=True)


def make_oauth_state_cookie(state: str) -> str:
    return _cookie_header(
        OAUTH_STATE_COOKIE,
        state,
        max_age=OAUTH_STATE_MAX_AGE,
        http_only=True,
    )


def clear_oauth_state_cookie() -> str:
    return _cookie_header(OAUTH_STATE_COOKIE, "", max_age=0, http_only=True)


def _cookie_header(
    name: str,
    value: str,
    *,
    max_age: int,
    http_only: bool = True,
) -> str:
    parts = [
        f"{name}={value}",
        "Path=/",
        f"Max-Age={max_age}",
        "SameSite=Lax",
    ]
    if http_only:
        parts.append("HttpOnly")
    # Local http://127.0.0.1 — no Secure flag (would break localhost).
    return "; ".join(parts)


def parse_cookies(header: str | None) -> dict[str, str]:
    out: dict[str, str] = {}
    if not header:
        return out
    for part in header.split(";"):
        if "=" not in part:
            continue
        k, _, v = part.partition("=")
        out[k.strip()] = v.strip()
    return out


def user_from_request(cookie_header: str | None) -> dict[str, Any] | None:
    cookies = parse_cookies(cookie_header)
    payload = verify_payload(cookies.get(SESSION_COOKIE))
    if not payload or "uid" not in payload:
        return None
    user = auth_db.get_user(int(payload["uid"]))
    if not user:
        return None
    return {
        "id": user["id"],
        "email": user["email"],
        "name": user.get("name"),
        "picture": user.get("picture"),
    }


def google_authorize_url(state: str) -> str:
    params = {
        "client_id": _cfg("GOOGLE_CLIENT_ID"),
        "redirect_uri": oauth_redirect_uri(),
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "online",
        "include_granted_scopes": "true",
        "prompt": "select_account",
        "state": state,
    }
    return f"{GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}"


def _http_json(
    url: str,
    *,
    method: str = "GET",
    data: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    body = None
    req_headers = {"Accept": "application/json", **(headers or {})}
    if data is not None:
        body = urllib.parse.urlencode(data).encode("utf-8")
        req_headers["Content-Type"] = "application/x-www-form-urlencoded"
    req = urllib.request.Request(url, data=body, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"Google API {exc.code}: {err_body}") from exc


def exchange_code_for_user(code: str) -> dict[str, Any]:
    token = _http_json(
        GOOGLE_TOKEN_URL,
        method="POST",
        data={
            "code": code,
            "client_id": _cfg("GOOGLE_CLIENT_ID"),
            "client_secret": _cfg("GOOGLE_CLIENT_SECRET"),
            "redirect_uri": oauth_redirect_uri(),
            "grant_type": "authorization_code",
        },
    )
    access = token.get("access_token")
    if not access:
        raise RuntimeError("No access_token from Google")

    info = _http_json(
        GOOGLE_USERINFO_URL,
        headers={"Authorization": f"Bearer {access}"},
    )
    email = auth_db.normalize_email(info.get("email"))
    sub = str(info.get("sub") or "").strip()
    if not email or not sub:
        raise RuntimeError("Google account missing email")
    if info.get("email_verified") is False:
        raise RuntimeError("Google email not verified")
    return {
        "google_sub": sub,
        "email": email,
        "name": (info.get("name") or "")[:120] or None,
        "picture": (info.get("picture") or "")[:500] or None,
    }


def redeem_google_login(google_user: dict[str, Any]) -> dict[str, Any]:
    """
    Allow sign-in only if email has an open invite OR already has a user row
    (returning user whose invite was redeemed).
    """
    email = google_user["email"]
    existing = auth_db.find_user_by_google(email, google_user["google_sub"])
    open_invite = auth_db.find_open_invite(email)
    if not existing and not open_invite:
        return {
            "ok": False,
            "error": "No invite for this Google account",
            "email": email,
        }

    user = auth_db.upsert_user_from_google(
        google_sub=google_user["google_sub"],
        email=email,
        name=google_user.get("name"),
        picture=google_user.get("picture"),
    )
    return {"ok": True, "user": user}


def check_admin_token(provided: str | None) -> bool:
    expected = invite_admin_token()
    if not expected:
        return False
    if not provided:
        return False
    return hmac.compare_digest(expected, provided.strip())
