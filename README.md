# TypeBeat

Underground type-beat discovery and listening. The **active product UI** is **TypeBeat Radio** — a local Python HTTP server with a custom glass-and-vinyl player that reads `typebeats.db` and streams YouTube audio (with optional on-machine extract for Web Audio polish and crossfades).

The repo also contains **data harvesters** (scrape, tag, producer lists), a **Streamlit catalog app** (`app.py`), and an early **Next.js scaffold** (`web/`). Those are separate from the radio experience unless you explicitly work on them.

## Run Radio

```bash
cd /Users/maximrahr/Documents/typebeat
source venv/bin/activate
pip install yt-dlp   # once; ffmpeg recommended
python -m radio
# http://127.0.0.1:8765/?v=ui-polish-95
```

Copy `.env.example` → `.env` if you need Google sign-in for reactions (see `radio/AUTH.md`).

For **GitHub + Turso** (what ships in git vs what stays local), see [`docs/GITHUB_TURSO_WORKFLOW.md`](docs/GITHUB_TURSO_WORKFLOW.md).

## Documentation

| Doc | Audience |
|-----|----------|
| [`radio/LLM_CONTEXT.md`](radio/LLM_CONTEXT.md) | **Start here** when handing work to another LLM — architecture, APIs, file map, persistence |
| [`radio/HANDOFF.md`](radio/HANDOFF.md) | Current status, verify checklist, do-not-regress |
| [`radio/DESIGN_SYSTEM.md`](radio/DESIGN_SYSTEM.md) | Normative UI and audio rules |
| [`PRD_v2.md`](PRD_v2.md) | Product vision and roadmap |

Hard-refresh the player after static changes using the cache version in `radio/static/index.html` (currently `ui-polish-95`).
