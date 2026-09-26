# Display fonts for TypeBeat Radio

Used by the radio player (`radio/static`). After font/CSS changes, hard-refresh with the current cache-bust from [`HANDOFF.md`](../HANDOFF.md) / `index.html` (today: `?v=ui-polish-98`).

## Druk (preferred)

**Druk** is a Commercial Type face and is **not** bundled here (license required).

A system `Druk.ttc` may exist on some macOS installs (Apple Application Support); browsers generally **cannot** load that for web pages — self-host licensed files instead.

If you already have a license:

1. Drop files here:
   - `Druk-Bold.woff2` (preferred) or `.woff` / `.otf`
2. In `radio/static/radio.css`, uncomment the `url(...)` lines inside the `@font-face` for `"Druk"`.
3. Hard-refresh the player.

## Fallback (active now)

Until Druk files are wired, track titles use **Big Shoulders Display** (Google Fonts, OFL) — a bold condensed display face in a similar register. Brand wordmark uses the same family for cohesion.
