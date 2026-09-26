# TypeBeat Radio — Chat Handoff

**Date:** 2026-09-24  
**Cache-bust:** `?v=ui-polish-95` (bump on every static CSS/JS change; update `index.html` + this file + `DESIGN_SYSTEM.md` / `THEMES.md` / `LLM_CONTEXT.md`)  
**Stack:** Python `python -m radio` on `http://127.0.0.1:8765` (venv + yt-dlp for local audio)  
**Scope note:** This is **typebeat radio only** — ignore Gemini Search+ / other repos unless the user says otherwise.

## Read first

| Doc | Purpose |
|-----|---------|
| **`LLM_CONTEXT.md`** | Self-contained master brief for external LLMs (architecture, APIs, keys, file map) |
| **`HANDOFF.md`** (this file) | Current status, do-not-regress, next-chat checklist |
| **`DESIGN_SYSTEM.md`** | Normative UI / audio / layout rules |
| **`THEMES.md`** | Skins + Exp persistence keys (keep in sync with locked Exp) |
| **`AUTH.md`** | Invite gate + Google OAuth |
| **`static/fonts/README.md`** | Display font licensing (Druk vs Big Shoulders) |

## Key files

| Path | Role |
|------|------|
| `radio/static/index.html` | Shell + `?v=` cache-bust on CSS/JS |
| `radio/static/tokens.css` | Shared tokens (`--art-size`, `--rail-width`, `--cdj-pad-h`, …) |
| `radio/static/radio.css` | Layout, filters, compressor meter, Views/age sliders, Prolific |
| `radio/static/skins.css` | Deck/Tape skins, CDJ pads, rearranged constellation, zoom media |
| `radio/static/skins.js` | Skin/Exp, Track age + Prolific mount, chip-fit, vinyl title placement + scale, locked reaction orb offsets |
| `radio/static/radio.js` | Transport, station deferral, polish UI, nav lock, xfade orchestration |
| `radio/static/polish.js` | Dual MediaElement graph: EQ → **DynamicsCompressor** → makeup → limiter → out; `crossfadeTo` |
| `radio/static/as-tape/` | Tape PNG assets (`cassette.png`, reels, …) |

## Product snapshot (locked)

- **Skins:** `deck` (vinyl) · `tape` only. Legacy ids migrate on load.
- **Shape:** `cdj-ink` only (no Shape Exp picker).
- **Glass:** animated `glass` only.
- **Layout:** classic 3-column; player **rearranged** constellation (reactions on art, compressor under art).
- **Left rail:** Views (**slider**) → Track age (**slider**, same length / 6 segments) → Genre → Clearance → Prolific (**checkbox**).
- **Right Exp:** Skin · Crossfade (7s default, Aggressive preload) · Title transition (Fade / Wipe / Blur / Tick) · **Vinyl title** placement chips + scale slider (deck only). **No** orb-position tuners — offsets locked in `DEFAULT_REACT_POS`. Foldable (`Shift+E` / `tb_radio_exp_fold`).
- **Station change:** deferred while track loaded (pending chip **NEXT UP** → **CHANGE NOW?**; confirm with **Next** or re-click chip; **Prev** cancels).
- **Clearance:** visible chip **FFP** (`aria-label` / tooltip carry “free for profit”; not “FREE FOR PROFIT” as the face label).
- **Crossfade:** always on for local audio (dual A↔B graph gains). Iframe = volume fade only.
- **Compressor:** horizontal **amount** control (drag sideways). Fill = set amount, **not** live GR / spectrum. Spectrum = `#audio-viz` **above** compressor. Audio path must actually compress (`polish.setAmount` → DynamicsCompressor).

## Latest polish batch (`ui-polish-95`) — seven-pillar review

Static assets in `index.html` ship at **`?v=ui-polish-95`**. Impeccable-style seven-pillar pass on `radio/static` (motion, typography, interaction, UX copy). Product rules from **94** (orb lock, FFP, NEXT UP, vinyl Exp, tape window) unchanged.

| Pillar | Shipped in 95 |
|--------|----------------|
| **Motion** | Like hover: `react-like-bounce` → **`react-like-lift`** (`--ease-out`); loop `1.6s var(--ease-out)`; compressor fill **`scaleY`** + `transform` (not `height`); `skins.js` `animationend` names updated. |
| **Typography & contrast** | Functional text **≥ ~11px**: `--type-chip-label` min `0.6875rem`; Exp labels `0.6875rem` + higher alpha; `.level__gr` / `.compress-steps__gr` → `0.72rem`; `.auth-user` → `--chrome-fg-muted`. |
| **Interaction** | Play `:focus-visible` on deck **and** tape; prev/next skip **aria** + `aria-busy` when loading (no HTML `disabled`); compress **`role="slider"`** + “Compression amount” aria. |
| **UX copy** | Specific transport/compress/invite strings in `index.html` + `radio.js` (e.g. invite submit **Send request**); FFP / NEXT UP copy from 94 retained. |
| **Assets / detect** | 1×1 GIF `src` on art/thumbs until queue load; `.impeccable/config.json` ignores runtime `broken-image` on `index.html` / `skins.js`. |

**Deferred (not in 95):** decorative `sheen-drift` / `load-shine` marquees; full typeset swap off Space Grotesk (CDJ brief-locked); skip/not-fit hover dark-glow polish.

## Batches `ui-polish-65` → `ui-polish-95` (summary)

Incremental polish landed in static CSS/JS between 64 and 95 (individual batch notes were not always doc’d). Verified through **95**:

1. **Vinyl title Exp** — deck-only **Title placement** chips (`Top rim` default · `Upper wrap` full inner ring · `Bottom arc`) + **Title scale** range slider (50–400%, `tb_radio_vinyl_title_scale`). Auto-fit shrink / tracking / ellipsis unchanged.
2. **Reaction orbs** — Exp **orb position tuners removed**; CSS vars come from locked `DEFAULT_REACT_POS` in `skins.js`. Legacy `tb_radio_react_pos` is cleared on load.
3. **Pending genre UX** — armed chip label **NEXT UP**, then **CHANGE NOW?** after timeout (`radio.js`); confirm with Next or chip; Prev cancels.
4. **Clearance copy** — FFP chip shows **FFP** on the pad; tooltip + `aria-label` spell out free-for-profit.
5. **Tape window** — still **no** frosted overlay (64 rollback stands); reels + cover visible through shell window.
6. **ui-polish-95** — seven-pillar batch above; static cache **95**.

## Batch (`ui-polish-64`) — reference

1. **Tape reel window rollback** — removed ui-polish-63 frosted `.as-tape-chrome__window-glass` overlay, `data-tape-glass`, Exp **Tape window → Frost**, and `tb_radio_tape_glass`. Clear window shows reels + J-card cover again; pause still freezes reel `animation-play-state`.
2. **Vinyl curved title restore** — full **360°** `textPath` ring on sticker (r=22.5); `fitVinylTitleFont` shrink / tracking / ellipsis unchanged. Title updates on track change via `syncArtTitle` + `syncVinylTitleText`.
3. **LLM handoff docs** — added `radio/LLM_CONTEXT.md`, root `README.md`, synced cache lines to `ui-polish-64`.

## Prior batch (`ui-polish-63`) — partially reverted in 64

1. **Track age slider labels** — two-line tier markup (`<18` / `M`, …) — **kept**.
2. ~~**Tape frosted window**~~ — **reverted in ui-polish-64**.
3. **Title transition** — Fade / Wipe / Blur / Tick on tape label — **kept**.

## Prior batch (`ui-polish-62`) — superseded on vinyl title

1. **Vinyl sticker art** — cover in `.art__sticker` — **kept**.
2. ~~**Upper-arc vinyl title**~~ — **reverted to full ring in ui-polish-64**.
3. **Genre chip-fit** — **kept**.

## Prior batch (`ui-polish-61`) — reference

Full-ring vinyl title (restored in 64), genre chip-fit, views two-line labels, Marker-sponge (removed in 63).

## Do not regress

- Crossfade: no mid-fade `ensurePolishConnected` gain snap; watch for blip→silence→restart. Verify `[xfade] overlap active`.
- Next/Prev: never HTML `disabled`; keep `NAV_STUCK_MS` + xfade watchdogs.
- Never `overflow: hidden` on `.filter-rail` (clips Clearance).
- Never reintroduce Shape / Glass / Compress-UI / **Tape frost** / **orb-position** Exp pickers.
- Never drive compressor fill from live gain reduction.
- Never make Track age a CDJ pad grid again.
- Don’t shrink `--cdj-pad-h` for “fit” — scroll the rail.
- Tape window: no frosted glass overlay — reels must stay visible through the shell window.
- Gemini / other products are out of scope unless explicitly requested.

## How to run / verify

```bash
cd /Users/maximrahr/Documents/typebeat
source venv/bin/activate
python -m radio
# open http://127.0.0.1:8765/?v=ui-polish-95
```

| Check | Expect |
|-------|--------|
| `/api/audio/tools` | `ready: true` (yt-dlp) for true xfade + audible compressor |
| Next after preload | Console `[xfade] overlap active`; continuous audio |
| Genre long labels | One line; pads stay ~3.2rem tall |
| Views vs Track age | Equal track widths; age ticks two-line (`<18` / `M`) |
| Tape window | Reels + cover visible; no frost blur layer |
| Vinyl title | Placement + scale from Exp (default top rim); updates on Next |
| Pending genre | Chip shows NEXT UP → CHANGE NOW? while track loaded |
| FFP chip | Face label **FFP**; tooltip/aria describe free for profit |
| Title transition | Wipe / Blur / Tick — single visible title (no sponge overlap) |
| Compressor drag | Louder squash at high %; fill tracks amount; bars only in `#audio-viz` |
| Zoom 150% / 175% | Art + orbs + rails scale; invite not on Views panel |

## Known soft spots / likely next work

- **Reaction orb offsets** are code-locked (`DEFAULT_REACT_POS`) — change in `skins.js`, not Exp.
- **FFP** is three letters on the pad; long-form copy lives in tooltip / aria only.
- **Tape PNG** soft-fails above ~150% zoom (bitmap limit) — layout tokens still scale.
- **Pillar leftovers:** sheen/load-shine marquees, skip hover glow, grotesk stack — see Latest batch **Deferred**.
- Repo may have **no git commits** for radio static yet — don’t assume clean history; prefer careful diffs.
- PRD files at repo root (`PRD.md`, `PRD_v2.md`, …) are product vision, not radio UI runbooks.

## Persistence keys (current)

| Key | Notes |
|-----|--------|
| `tb_radio_skin` | `deck` \| `tape` |
| `tb_radio_chip_shape` | Forced `cdj-ink` |
| `tb_radio_glass` | Forced `glass` |
| `tb_radio_compress_ui` | Forced `meter` |
| `tb_radio_views_slider` / `data-views-ui` | Forced `slider` |
| `tb_radio_prolific` | Prolific-only filter |
| `tb_radio_max_age_months` | Track age |
| `tb_radio_exp_fold` | Exp folded when set |
| `tb_radio_title_xfade` | `fade` (default) · `wipe` · `blur` · `tick` (legacy `sponge` → `fade`) |
| `tb_radio_vinyl_title_placement` | `inner_rim_top` (default) · `inner_band_wrap` · `lower_inner_arc` |
| `tb_radio_vinyl_title_scale` | 50–400 (default 100) |
| `typebeat.radio.xfade*` | Mode / preload / handoff / overlap / start |
| `typebeat.radio.polishAmount` | Compressor amount (default ~25% of max) |

Removed on load: `tb_radio_tape_glass`, `tb_radio_react_pos` (ui-polish-64 frost rollback; orb JSON no longer used).

## Chat continuity

Prior agent transcript (this UI polish arc):  
[`Typebeat UI polish`](7ecbc7f8-39c0-44d2-96cd-1d67fcdd1a65)

When starting a new chat: attach **`radio/LLM_CONTEXT.md`** first, then **`radio/HANDOFF.md`** + **`radio/DESIGN_SYSTEM.md`**, hard-refresh `?v=ui-polish-95`, and confirm local audio tools before touching crossfade/compressor.
