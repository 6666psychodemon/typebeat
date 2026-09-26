# TypeBeat Radio — Invite & Google Auth

Invite-gated Google sign-in. Unauthenticated listeners can still play the radio; **Like / Dislike** open a minimal invite request form instead of signing in directly.

> UI / chat handoff: [`LLM_CONTEXT.md`](./LLM_CONTEXT.md) (attach first for new LLMs), [`HANDOFF.md`](./HANDOFF.md). Design norms: [`DESIGN_SYSTEM.md`](./DESIGN_SYSTEM.md).

## Env

Copy `.env.example` → `.env` (never commit `.env`):

| Key | Purpose |
|-----|---------|
| `GOOGLE_CLIENT_ID` | Google OAuth Web client ID |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret |
| `OAUTH_REDIRECT_URI` | Must match Google console (default `http://127.0.0.1:8765/auth/google/callback`) |
| `SESSION_SECRET` | Long random string for HTTP-only session cookies |
| `INVITE_ADMIN_TOKEN` | Optional token for `/admin/invites?token=…` |

Without Google creds, **invite requests + admin grant still work**. “Sign In” shows a short setup message.

## Google Cloud setup

1. [Google Cloud Console](https://console.cloud.google.com/) → APIs & Services → Credentials → **Create OAuth client ID** → Application type **Web application**.
2. Authorized redirect URI: `http://127.0.0.1:8765/auth/google/callback` (and any deployed host you use).
3. Put Client ID + secret in `.env`. Set `SESSION_SECRET` to a long random value.

## Flow

1. Listener hits Like/Dislike → **Request Invite** (email + optional note) → stored in `radio/data/auth.db`.
2. Founder grants invite (CLI or admin page).
3. Listener **Sign In With Google** → OAuth → email must match an open invite (or an existing user) → session cookie; invite marked redeemed.
4. Authed Like/Dislike persist to `reactions` (+ events still log with `user_id`).

## Admin

CLI (preferred):

```bash
source venv/bin/activate
python -m radio.invite_admin list
python -m radio.invite_admin list pending
python -m radio.invite_admin grant someone@example.com
python -m radio.invite_admin deny someone@example.com
python -m radio.invite_admin invites
```

Local page (optional): set `INVITE_ADMIN_TOKEN` then open  
`http://127.0.0.1:8765/admin/invites?token=YOUR_TOKEN`

## Local test

```bash
source venv/bin/activate
# optional: cp .env.example .env  and fill Google + SESSION_SECRET + INVITE_ADMIN_TOKEN
python -m radio
# open http://127.0.0.1:8765
# click Like → submit invite form
python -m radio.invite_admin list
python -m radio.invite_admin grant you@gmail.com
# Sign In (needs Google OAuth configured) with that Gmail
```

SQLite file: `radio/data/auth.db` (`invite_requests`, `invites`, `users`, `reactions`).

## Follow-ups

- Per-genre 100-track cap for unauth / warm queue (not required for invite funnel).
- Hide external YT links for unauth if/when the player exposes them.
