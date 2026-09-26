# GitHub + Turso workflow

This repo is split on purpose: **code and schema on GitHub**, **full catalog in Turso**, **secrets only on your machine or in Cursor**.

## What lives where

| Location | Contents |
|----------|----------|
| **GitHub** (`6666psychodemon/typebeat`) | TypeBeat Radio app (`radio/`), SQL schema (`sql/schema/`), migrations notes, tiny test fixture (`tests/fixtures/tracks.json`), `.env.example`, CI |
| **Local only** | `typebeats.db` (~1.8GB catalog), harvest logs, producer lists, `radio/data/audio_cache/`, `.env` |
| **Turso `onthebeat-dev`** | Small dev catalog for integration experiments |
| **Turso `onthebeat`** | Production catalog |

Do not commit `.env`, Turso tokens, or SQLite dumps.

## Environment variables

Copy [`.env.example`](../.env.example) to `.env` locally.

| Variable | Used by | Notes |
|----------|---------|--------|
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `OAUTH_REDIRECT_URI`, `SESSION_SECRET`, `INVITE_ADMIN_TOKEN` | Radio auth | See [`radio/AUTH.md`](../radio/AUTH.md) |
| `TURSO_DATABASE_URL`, `TURSO_AUTH_TOKEN` | Future / optional remote catalog | Set in Cursor **Secrets** or local `.env`; not required for CI |
| `TYPESAFE_API_KEY` | JEV tagging scripts | Optional; never in GitHub Actions unless you add a dedicated dev key for integration tests |

Radio today reads **local** `typebeats.db` at repo root ([`radio/queue.py`](../radio/queue.py)). Turso wiring is documented here so prod/dev databases stay out of git.

## Local dev without the big DB

```bash
python scripts/seed_fixture_db.py
python -m radio
```

That creates a minimal `typebeats.db` from the fixture (gitignored).

## CI (GitHub Actions)

- Runs `pytest` on the fixture + schema only.
- Does **not** need `TURSO_AUTH_TOKEN` or prod Turso URLs.
- Optional: add a separate workflow job with **onthebeat-dev** credentials stored as GitHub **Secrets** (`TURSO_DATABASE_URL_DEV`, `TURSO_AUTH_TOKEN_DEV`) — never use prod tokens in CI.

## First-time GitHub setup (`gh` not on PATH in some environments)

Install GitHub CLI, then:

```bash
cd /Users/maximrahr/Documents/typebeat
gh auth login
gh repo create 6666psychodemon/typebeat --public --source=. --remote=origin --push
```

If the repo already exists:

```bash
git remote add origin https://github.com/6666psychodemon/typebeat.git
git push -u origin main
```

## Turso (manual)

1. Create databases **onthebeat-dev** and **onthebeat** in the Turso dashboard.
2. Apply `sql/schema/001_catalog.sql` (and auth DDL if you host auth remotely later).
3. Load dev data via your harvest/sync pipeline — not via git.

Tokens: Turso → database → **Connect** → copy URL and token into local `.env` or Cursor secrets.
