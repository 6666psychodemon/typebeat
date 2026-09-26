# TypeBeat Radio — Design System

Lean-back underground type-beat radio. One composition per viewport: art is the hero, chrome stays out of the way, CTAs stay crisp.

> **Chat handoff:** start with [`LLM_CONTEXT.md`](./LLM_CONTEXT.md) for external LLMs, then [`HANDOFF.md`](./HANDOFF.md) for current status, cache-bust, and do-not-regress. Skins keys: [`THEMES.md`](./THEMES.md). Auth: [`AUTH.md`](./AUTH.md).

## Philosophy

- **Lean-back, not dashboard.** First viewport = art stage + transport + one filter rail + reactions. No stats strips, no playlist walls, no competing heroes.
- **Skin-specific materials.** Deck leans liquid glass; Signal is brutalist paper/mono; Cassette/Tape use physical shells. Same geometry, different surface grammar.
- **High-contrast CTAs.** Primary actions (Request Invite, Send, accent EXP) use dark ink on sand/accent fill. Elevation is on the *pill*, never a dark text-shadow on dark glyphs (that muddies contrast).
- **Big hit targets.** Orbs ≥ ~52–58px; chips stay tappable; invite pill ≥ 48px tall.
- **No overlays in the stage.** Reserved zones (grid/flex) so filter rail, prev/next, invite, and reactions never stack on each other.

## Key product ideas (from build discussions)

- Square cover art **dead-center** of the viewport; prev / next flanking on the vinyl centre axis (round metallic caps, never overlapping vinyl).
- **Normal panel LEFT:** Views (slider), Track age (slider under Views), Genre, Clearance (**FREE** / **FFP**), Prolific (checkbox). Left rail scrolls when Genre pushes Clearance below the fold — do not clip those blocks with `overflow: hidden`.
- **Experimental panel RIGHT:** Skin + Crossfade (3s/7s). CDJ chip look is locked (no Shape picker). Glass locked to animated `glass`. Neither panel overlays the vinyl.
- Filters: Views (numeric ranges — **slider only**), **Genre** (stations), Clearance (free / FFP) — not “Depth” labels, not “License.”
- Station switch is **deferred while a track is loaded**: first Genre click arms the choice (**NEXT UP** → **CHANGE NOW?** on the pending chip); station does not switch until the user confirms with **Next (`>`)** or clicks the pending chip again. **Prev (`<`)** cancels the pending genre without skipping the track. With no track loaded, Genre applies immediately. In-flight prefetch uses a generation token so the latest click wins.
- Invite gate before Google sign-in; like/dislike prompt invite when unauth. **REQUEST INVITE** (ALL CAPS) sits under the compressor in the player column with clear vertical margin (never overlaps compressor or timeline).
- **Experimental panel (EXP / Shift+E):** right rail — **skin**, **crossfade**, **title transition** (Fade / Wipe / Blur / Tick), **vinyl title placement + scale** (deck only). **No** orb-position Exp tuners — offsets locked in `DEFAULT_REACT_POS` (`skins.js`). Shape Exp removed (CDJ only). Views + Track age = sliders (**same length**, same segment count). Compressor = **amount** meter (drag to compress) + separate spectrum visualizer (`#audio-viz`) above it — never drive the compressor fill from live GR. No Debug log chip. Foldable (`tb_radio_exp_fold`). Prolific checkbox + Track age under Views on the **left**. Panel **scrolls** when Crossfade (etc.) exceeds rail height.
- **CDJ genre pads:** keep tall (`--cdj-pad-h: 3.2rem`). Labels stay **one line** (`white-space: nowrap` + `--chip-fit` shrink); never wrap and never shrink pad height to fit text.
- **Left / Exp panel labels:** no underlines in Vinyl or Tape — panels must look identical across skins.
- Skins: **Deck** + **TAPE** (`tape`). Legacy `as-tape` / `cassette` / `mixtape` / `signal` storage migrates on load.

## Always-on track crossfade (permanent)

Track changes (**prev / next / ended / station commit**) always soft-handoff — not an optional toggle.

| Piece | Behavior |
|-------|----------|
| Local audio (primary) | Dual `<audio>` A↔B + polish graph **gain** crossfade — **true overlap** (~**7s** / `CROSSFADE_MS`): both tracks audible mid-cross |
| Verification | DevTools must log **`[xfade] overlap active`** when dual overlap runs; if missing, you are likely on iframe-only |
| Prefetch | Default **Aggressive**: prime next ahead for smooth Next. On skip / Early / Off still in Exp. |
| Art / atmosphere | Opacity crossfade paired with audio handoff (`--art-fade-ms` = effective xfade ms; title uses `--title-fade-ms`) |
| YouTube iframe fallback | Best-effort **volume** fade only (~480ms). Full A+B overlap **requires** local `/api/audio` (iframe PCM is cross-origin — true dual-audio xfade is impossible in the iframe alone) |
| Reduced motion | Fades / overlap collapse to 0 |

Do not reintroduce a user-facing “crossfade on/off” control. Station commits while playing must crossfade into the new queue’s first track (do not hard-stop local audio first).

### Next / nav lock (do not regress)

- Never use HTML `disabled` on Prev/Next — it blocks stuck-recovery clicks.
- `NAV_STUCK_MS` (~2.5s) force-releases a held lock on another click; xfade overshoot also force-releases.
- Clearing the prep timer when overlap starts requires an **xfade watchdog** + deferred timeout that still recovers (never `return` while leaving `navLock.busy`).
- Timeout-wrap `HTMLMediaElement.play()` and graph `crossfadeTo` so hung promises cannot freeze Next.

Hard-refresh cache-bust: `?v=ui-polish-98`.

### Zoom / proportions (~150% / ~175%)

At high browser zoom the CSS viewport shrinks. Keep **vinyl/tape + prev/next + reaction orbs** linked via shared tokens:

| Token | Role |
|-------|------|
| `--art-size` | Platter / tape stage |
| `--side-orb-size` | Prev / Next caps |
| `--orb-size` / `--orb-size-like` | Reaction orbs |
| `--rail-width` | Left / right chrome columns |

Under `max-height: 720px` / `max-width: 1100px` (~150%), rails tighten and `--art-size` / orbs scale down together. Under `max-height: 580px` / `max-width: 920px` (~175%), stage shrinks further and compressor / invite offsets tighten so chrome does not collide with rails.

Locked defaults for reaction orb % offsets (`DEFAULT_REACT_POS` in `skins.js` — not Exp-tunable):

| Skin | Control | X | Y |
|------|---------|---|---|
| Vinyl | loop | 6% | 8% |
| Vinyl | not-fit (X) | 6% | 8% |
| Vinyl | like | 1% | 8% |
| Vinyl | dislike | 1% | 8% |
| Tape | loop | 0% | −3% |
| Tape | not-fit (X) | 0% | −3% |
| Tape | like | −6% | −13% |
| Tape | dislike | −6% | −13% |

Legacy `tb_radio_react_pos` is removed on load.

### Exp → Crossfade experiments (temporary)

Founder-only controls. **Default: 7s crossfade + Aggressive preload.** Duration labels **7s crossfade** / **3s crossfade**. Never iframe-cut mid-overlap (`xfadeInProgress`). Debug log chip removed.

Persisted in `localStorage`:

| Key | Options |
|-----|---------|
| `typebeat.radio.xfadeMode` | `graph7` (default) · `graph3` · `volume7` · `volume3` · `instant` |
| `typebeat.radio.xfadePreload` | `aggressive` (default) · `early` · `on_skip` · `off` |
| `typebeat.radio.xfadeHandoffGate` | `allow_buffer_wait` (default) · `require_preloaded` |
| `typebeat.radio.xfadeOverlapMin` | `auto` (default) · `0` · `3000` · `7000` · `10000` |
| `tb_radio_title_xfade` | `fade` (default) · `wipe` · `blur` · `tick` |
| `tb_radio_vinyl_title_placement` | `inner_rim_top` (default) · `inner_band_wrap` · `lower_inner_arc` |
| `tb_radio_vinyl_title_scale` | 50–400 (default 100) |

| Mode | Behavior |
|------|----------|
| 7s / 3s crossfade | polish `xfadeGainA/B` equal-power ramp (true dual-source overlap) |
| Volume 7s / 3s | `fadeElementVolume` on both `<audio>`; graph gains passthrough at unity |
| Instant | Hard cut after buffer ready — baseline path check |

### Crossfade root cause (Aggressive path glitch)

Symptom: brief start of next → silence → next starts again.

**Cause:** `ensurePolishConnected()` re-called `connectDualMedia` + `setActiveSlot(state.activeSlot)` on every entry. Mid-overlap that **cancelled the linearRamp** while `polish.activeSlot` had already flipped (or `state.activeSlot` still pointed at the outgoing deck). Pausing the outgoing host then left both sides near ε → silence, then repair/iframe restart. Secondary contributors: seeking incoming while playing (Start-at), and false desync repair after a successful local handoff.

**Restored:** stitch-era dual-audio order — wire dual once, linearRamp A↔B, keep inactive at graph ε until `crossfadeTo`, no mid-fade gain snap, confirm destination slot after ramp, skip post-xfade `ensureHeardMatchesTrack` when `usedLocal`.

### How to verify true crossfade

1. Ensure **yt-dlp** is installed (`/api/audio/tools` → `ready: true`).
2. Hard-refresh with cache-bust (`?v=ui-polish-98`).
3. Press play and wait until **Compressor** is usable (local audio promoted — not “Needs Local Audio”).
4. With Preload = **Aggressive** (default): let ~8–15s pass; console **`[preload] ready`** / **`[preload] primed`**, then Next → **`[xfade] overlap active`** (~3000 or ~7000ms) with both tracks audible continuously (no blip→silence→restart).
5. Compressor meter fill = **set amount** (drag sideways); DynamicsCompressor actually compresses. Spectrum bars live only in **`#audio-viz`** above it — never treat the compressor as a visualizer.

## Click-free audio transitions

Polish + transport must avoid zipper / hard zero-cross clicks:

- Crossfade gains ramp to a tiny epsilon (not an abrupt `0` jump).
- Play / pause uses a short master-bus fade (~70ms) before pause / after play.
- Polish amount changes use longer compressor / limiter / makeup time constants; no-op reapply is skipped.
- Never rebuild or reconnect the polish graph on track change; dual MediaElement sources stay wired at boot.
- Do not re-`setAmount` after every handoff.

## Accessibility (normative)

Apply these in CSS, not only in copy. Low-vision: larger chip labels, stronger focus, no 1px-only affordances.

| Rule | Spec |
|------|------|
| Contrast | Text/icons vs background ≥ **4.5:1**. Large UI chrome (pads, orbs, bars) ≥ **3:1**. Docks sit on a dark glass scrim over cover-art so contrast holds in every glass mode. |
| Hit targets | Interactive controls ≥ **44×44px** where feasible (prev/next, like/dislike, Exp FAB, Exp chips, compressor steps). Filter chips may clamp on short 14" viewports — never below ~32px. |
| Focus | Visible `:focus-visible` ring (`--focus-ring` / `--focus-offset`) on every button, chip, slider, select, and invite control. |
| Not color alone | CDJ / CDJ ink pads: **underline bar** + label color + `aria-pressed`. Like/Dislike: accessible name + outline→fill on hover (fill is not the selected state). |
| Motion | Honor `prefers-reduced-motion`: freeze cover-art glass drift (Soft + Glass animated), vinyl spin, cassette/tape-alt reels, art fades, chip hover lift, and like/dislike/loop/skip hover keyframes (opacity-only remains). Pause also freezes glass drift and Glass morph. |
| Scan | **ALL CAPS** section headings (Views / Genre / Clearance / Experimental / Skin). Left rail and Exp share `--font-chip-label` / `--type-chip-label` with `letter-spacing: 0.08em`. CTA label **REQUEST INVITE**. |
| Names | Like / Dislike keep `aria-label`. Compressor exposes `aria-valuenow` / `aria-valuetext` for the **set amount** percent on the meter. |

## Stage layout (`html[data-layout="classic"]`)

CSS is the source of truth. Default **classic** split:

| Zone | Placement |
|------|-----------|
| Everyday filters | **Left** rail — Views, Track age, Genre, Clearance, Prolific |
| Vinyl / player | **Geometrically centered** in the viewport (equal `--rail-width` columns) |
| Experimental | **Right** rail — foldable to a vertical EXP tab |

**Exp → Split filters** (`html[data-filter-split="on"]`, `tb_radio_filter_split`): splits the *normal* panel, not Exp.

- **Left:** Views + Clearance (discovery + safety — short, scanned once)
- **Right, above Exp:** Style / genres (taste — longer list, lives with look-and-feel experiments)

Why this split: Views/Clearance are status filters; Style is the browsing vocabulary. Keeping taste next to Exp avoids a tall left column and keeps the safety chips in a compact left scan. Vinyl stays visually centered because left and right columns keep equal width even when Exp is folded.

Exp fold persists in `tb_radio_exp_fold`. Shift+E still toggles. Folded = thin vertical tab; unfolded = full Exp panel. Keyboard Exp toggle is unchanged.

### Layout invariants (do not break)

These rules keep the three-column classic stage from collapsing into “left rail + floating orbs”:

1. **`html[data-layout="classic"]`** — `@media (min-width: 860px)` grid is `left | player | right` on `.stage-body`. Do not remove `.chrome-rail--left`, `.player`, or `.chrome-rail--right` from the DOM.
2. **Never `display: none` on `.player` or `.chrome-rail--right` globally** — fold Exp via `html[data-exp-fold="on"] .exp-panel` only; the right rail and EXP tab stay visible.
3. **`skins.js` init order** — build `#exp-dock` (Exp panel) and left-rail extras before optional skin chrome; nothing in `init()` may throw before `buildExpPanel()` completes (removed skin helpers must not be called).
4. **`data-skin`** — only `deck` | `tape`; unknown / legacy values normalize to `deck` in JS before paint and on boot.
5. **Valid CSS** — a syntax error in `skins.css` can drop deck/tape/rearranged rules; run a quick parse check after editing large skin blocks.

### Cover-art glass (`html[data-glass]`)

**Locked to animated `glass`.** Soft / Hard / Stained Exp chips removed. Persist `tb_radio_glass` forced to `glass`.

## Shape (locked — no Exp picker)

`html[data-shape="cdj-ink"]` only. Exp Shape section removed. Legacy ids (pill, cdj, fold, …) normalize to `cdj-ink` on load.

**Locked to CDJ** (`cdj-ink`). Pill and other shapes removed. Persisted `tb_radio_chip_shape` / `?shape=` values for `pill` and deleted ids **map to `cdj-ink`**.

| id | Look |
|----|------|
| `cdj-ink` | Pioneer hot-cue pad (Exp label **CDJ**) — recessed well, raised rubber cap, cycling orange/blue/yellow + underline bar |

Applies to filter chips, Exp chips, and the Request Invite chip. Orbs stay round.

**Overlap:** CDJ ink pads are a grid of fixed pads (`--cdj-pad-w` / `--cdj-pad-h: 3.2rem` / `--cdj-pad-gap`) — no bleed. Long Genre labels stay **one line**: shrink via `--chip-fit` (character count) + `white-space: nowrap`; **never** wrap to 2 lines and **never** shrink pad height to fit text.

**Views + Track age are full-width range sliders**, not CDJ pad banks. `.filter-chips--tiers` and `.filter-chips--age` must `display: block` (escape the CDJ auto-fill grid) so both tracks share the full rail width and the same segment count. Parent `.filter-rail` keeps `overflow-y: auto` (never `overflow: hidden`) so Clearance / Prolific stay reachable on short viewports.

## Buttons carry no border strokes

Chips, pads, orbs, reaction buttons, the compressor, auth / CTA pills and invite buttons render with `border: 0`. Definition comes from **fill + inner shadow (`inset 0 0 0 1px var(--btn-ring)`) + the CDJ underline bar** — never an outline stroke. `--btn-ring` is light on dark skins and `rgba(10,11,12,.3)` on Signal. **Focus-visible outlines are exempt**: every button keeps a 2px accent ring at `outline-offset: 3px` for keyboard nav.

### Layout

**Rearranged** is the default and only player layout — reactions orbit the vinyl in a flat constellation + wide horizontal compressor. Legacy TESTING placements (Offset, Stack, React↑, etc.) removed from Exp.

## Reaction icons

**Line stroke only** — no icon-set toggle in Exp (legacy Solid/Glyph removed).

### Icon tilt (dynamism)

All reaction icons are slightly tilted **bottom-left → top-right** (~−9° to −15°). **Like / Dislike** use **2×** hit area + glyph size (`--orb-size-like`) with ~−15° CCW tilt. Hover fills the outline icon (solid glyph, same sand color) without using the selected/pressed treatment; selected stays accent color. Tooltips on `data-tip` wait **2000ms** (native `title` is not used — it cannot delay to 2s). Prev/next chevrons stay upright and centred inside the metal transport caps (below).

**Not-fit (close)** uses a grungy distressed X (`#grunge-ink` SVG filter, square caps, jittered paths).

### Loop icon

Single **line-style ring** with anchor dot (~−13° CCW tilt). No Exp toggle — arrows / track variants removed.

### Hover motion (like / dislike / loop / skip)

Idle opacity **0.75**; hover / `:focus-visible` / pressed **0.90** (~180ms). Selected/active (liked, loop on, authed like) **1.0**. Mouse-away **plays the hover motion in reverse** (not a snap): like bounce lands back, dislike dive comes up, loop spin eases to a stop, skip eases from enlarged to idle. `prefers-reduced-motion` keeps opacity + skip scale only. Fill-on-hover for like/dislike is unchanged. 2s tooltip delay unchanged.

| Control | Hover |
|---------|--------|
| Like | Double bounce up (“cool bro”) |
| Dislike | Slow dive down then return (“naaah bro”) |
| Loop | Steady slow spin on the ring with a short ease-in, then constant linear rotation (no speed jitters) |
| Skip (prev/next) | Grow a bit (`scale` ~1.08) while hovered; ease back to idle on mouse-away. Independent `scale` so metal-cap `transform` rules cannot cancel it. |

## Left rail — everyday filters fit on ~14" laptop

Target: **Views + Genre + Clearance** (+ Prolific / Track age) fit in the **left** column on a typical 14" MacBook (~1512×982 CSS) without mandatory scroll when possible. **`--cdj-pad-h` stays 3.2rem** under short viewports — do not squash pad height; if content is tall, `.filter-rail` uses `overflow-y: auto` — never `overflow: hidden` on the filter rail (that clipped Clearance with no scroll).

## Zoom resilience

- **Deck (vinyl):** vector/CSS (`%` of `.art`, SVG textPath). Scales with `--art-size` under browser zoom.
- **Tape:** shell is a **PNG**. Layout (orbs, title, chrome) uses `%` / `clamp`; pixel edges and label registration soft-fail above ~150% zoom — expected limit of bitmap art.

Strategy:

- **No page scroll.** `html`, `body`, `.stage`, `.stage-body` use `overflow: hidden`. Vinyl/cassette + transport + compressor stay in the viewport.
- **Left filter rail:** clamp type/gaps; Genre stays 2-column CDJ grid; Views/age are full-width sliders; rail scrolls if needed.
- **Right Exp panel:** variable-height experimental content **must scroll** (see below) — never clip Crossfade / Mode / etc.
- Style chips: **2-column grid** on desktop (not one long wrapped row).
- Track age + Views: **equal-length range sliders** (never a short CDJ-grid age track; never horizontal scroll for age labels).

### Controls must never overlap (normative)

Stacked player chrome needs clear vertical separation and non-overlapping hit targets:

- **Request Invite** sits **under** the compressor pill with a visible gap (`html[data-testing="rearranged"] .auth-rail--player` is absolutely positioned below the art column — `top: calc(100% + 8.85rem)`). Do not reintroduce a mid-art `translateY` that lands the CTA on the compressor / timeline bar.
- Compressor, invite, like/dislike, and prev/next must not share the same hit rectangle. If two controls collide, move the lower one further down and grow `.player` `padding-bottom` to match.
- When adding stacked chrome under the platter, reserve space in `.player` padding first; never rely on z-index to “hide” an overlap.

### Panels with variable content must scroll (normative)

Any panel whose content height can grow (Exp Crossfade block, future Exp sections) **must**:

- Constrain height via the rail / dock (`min-height: 0`, flex child filling the rail).
- Use `overflow-y: auto` (and `overflow-x: hidden`) on the scrollable panel itself — **never** clip interactive controls without a scrollbar.
- Keep the left everyday filter rail compact (wrap/clamp); the right Exp dock is the scrollable column.

Do not treat Exp overflow as a “fit everything” problem — scroll is required once Crossfade (or similar) makes the panel taller than the viewport rail.

### Compressor UI (locked: meter)

Compressor is always the horizontal **amount meter** under the vinyl (`html[data-compress-ui="meter"]`). Exp Compressor UI picker removed.

- **Fill** = set polish amount (`--compress` from `polishAmount` / drag). Orange amount ramp — **not** a green→yellow→red VU and **not** live gain-reduction.
- **Spectrum** = separate `#audio-viz` canvas **above** the compressor. Never show the bar-graph `.level__icon` inside the compressor control.
- **Audio** = `polish.js` DynamicsCompressor in the local graph must respond to `setAmount` / `applyPolishMacro`. Slider / Steps modes are not offered.

### Vinyl curved title (Deck)

Deck always shows the track name as SVG `textPath` on `.vinyl-title`, curved **on the paper sticker ring** (not black PVC alone, not a strip below the platter).

- **Sticker:** `.art__sticker` — paper disc (~50% of platter) behind the cover.
- **Cover art:** `.art__img` clips inside `.art__sticker` (~50% platter) with `overflow: hidden`, `object-fit: cover`, edge-to-edge circle (no square inset).
- **Title:** Anton / Archivo Black (`--font-title`), curved on the paper sticker via `textPath` (placement preset from Exp — default **top inner rim**; **Upper wrap** uses a full inner ring). Font starts large, then shrinks tracking, then ellipsizes only if still too long. **Title scale** slider (50–400%) applies after auto-fit.
- Hide `.skin-nowplaying` / `.art__title` while the curved title is active.

### Tape reactions

On Tape, like / dislike sit **outside** the beige cassette shell (left-outside / right-outside bottom corners) — never on the label or reels.

### Tape title + reel window

- **Title:** Permanent Marker — smaller type + tighter tracking, one line + ellipsis.
- **Window:** clear reel well — cover art in the window rect, reels visible on pause/play; reel spin uses `animation-play-state` (freeze on pause).
- **Shell:** art/empty clipped to rounded cassette silhouette (no sharp under-corners).

### Cassette frame

Permanent `static/as-tape/cassette.png` — Exp Label chrome toggle removed.

### Crossfade must survive skin / CSS edits (normative)

Local dual-source crossfade (`radio.js` + `polish.js`) is product-critical. Rules:

- Never remove Exp Crossfade controls (Mode / Preload / Overlap / Start). Debug log chip is intentionally gone. `.exp-select` / `.exp-field` / `.exp-section--xfade` must stay visible.
- Skin CSS must not `display:none` / `visibility:hidden` those controls.
- True overlap requires **local audio** (`/api/audio/tools` → `ready: true` via project `venv` yt-dlp). Iframe-only cannot do A↔B graph overlap.
- Console verification: `[xfade] overlap active` with `graph: true` on skip when local audio is hot.
- `radio.js` / `polish.js` last known working audio path: mtimes Sep 19 / Sep 12 (no git commits in repo yet). Do not strip `crossfadeToLocal` / `polish.crossfadeTo` when editing skins.

## Geometry (all skins)

| Zone | Role |
|------|------|
| **Invite / auth** | Under compressor in the player column (clear gap); reserved stage padding so it never overlaps compressor / timeline |
| **Left rail** | Everyday filters (Views / Style / Clearance); fixed `--rail-width` |
| **Art stage** | Center column: prev · art · next on one axis (no overlay into either rail) |
| **Right rail** | Exp dock (skin, crossfade); CDJ locked; foldable; **scrolls** when content exceeds rail height |
| **Reactions** | Constellation on vinyl; on Tape, like/dislike **outside** the cassette shell; compressor meter under art |

Viewport: `100dvh`, `overflow: hidden` on page and left filter rail, safe-area insets, `clamp()` for art / orbs / chips / gaps. Left rail chips wrap; right Exp panel scrolls when content exceeds the rail.

### Core parameters

| Token | Intent | Typical |
|-------|--------|---------|
| `--art-size` | Dominant square | `min(…, 620–720px)` via clamp/dvh |
| `--rail-width` | Filter column | ~252–320px (tighter at short height) |
| `--orb-size` | Prev/next + loop / not-fit / compressor orbs | 52–58px |
| `--orb-size-like` | Like / Dislike only | 2× `--orb-size` |
| `--gutter` | Rail ↔ stage gap | 0.65–1rem |
| `--gap-transport` | Prev/art/next grid gap | 0.45–0.85rem |
| `--orb-clearance` | Extra air pushing prev/next clear of the vinyl rim | 0.6–1.15rem |
| `--btn-ring` | Inner ring that replaces button border strokes | light on dark skins, ink on Signal |
| `--radius-panel` | Glass / panels | 18px (0 on Signal) |
| `--radius-chip` / `--radius-cta` | Pills | CDJ overrides to pad radius (`data-shape="cdj-ink"`) |
| `--fade-ms` | Art / atmosphere opacity crossfade | 480ms |
| *(JS)* `CROSSFADE_MS` | Dual-source local audio overlap | **7000ms** |
| *(JS)* `XFADE_READY_MS` | Wait for cache before degrade | **3000ms** |
| `--invite-reserve` | Top clear for CTA | ~3.5rem |

### Z-index layers

`atmosphere (0)` → `stage (1)` → `player (4)` → `chrome (6)` → `exp (8)` → `auth (12)` → `modal (40)` → `tip (10000)`

## Tokens & recipes

**Files:** `static/tokens.css` (`:root` + `.cta-pill`), consumed by `radio.css` / `skins.css`.

### CTA (`.cta-pill`, `#btn-request-invite`)

Matches **panel chips** (CDJ-era): `--font-chip`, `--type-chip`, `--chip-pad-*`, `--radius-chip`, sentence case, min-height ≥ `--hit-min` (44px). Still a filled accent CTA (`--cta-bg` / `--cta-fg`) with layered inner/outer shadow — not the old Anton/uppercase orange pill.

```css
background: var(--cta-bg);
color: var(--cta-fg);
font-family: var(--font-chip);
text-shadow: var(--cta-text-shadow); /* none */
box-shadow: var(--cta-shadow);       /* inner highlight + outer lift */
```

Skins may recolor `--cta-bg` / `--cta-fg`; they must keep `--cta-text-shadow: none` for filled CTAs. Hover/focus-visible matches chips (lift + brightness).

### Chips

Use `--font-chip`, `--type-chip`, `--chip-pad-*`, `--chip-min-h`, `--chip-track`, `--gap-chip`. Section headings use `--font-chip-label` / `--type-chip-label` on **both** rails (`.filter-block__label` and `.exp-section__label`). Prefer slightly smaller type + tighter padding over an internal Genre scrollbar. Long Genre / Clearance names shrink proportionally (`--chip-fit` from character count) and stay **one line** (`nowrap`) — never two-line wrap, never shorter pads. Corner language follows locked CDJ ink (`data-shape`). Views / Clearance short labels stay `--type-chip`. Prolific checkbox box uses **`em`** units so it scales with label type under zoom.

### Panels / orbs

Reuse `--glass-*` for Deck-leaning chrome; Signal zeros blur/radius and inverts to paper; Cassette uses a physical tape shell (reels / label) with quiet frosted side chrome.

### Prev / next transport caps

`#btn-prev` / `#btn-next` are **round brushed-metal CDJ caps** (Pioneer CUE / PLAY-PAUSE reference) in every skin and every Exp shape:

- `border-radius: 50%` + `aspect-ratio: 1/1`, forced past skin and shape overrides (`!important`, plus a `corner-shape: round` guard).
- Dark gunmetal `conic-gradient` + `repeating-conic-gradient` brush striations, top bevel highlight, darker lower edge, inset rim ring, layered outer drop shadow.
- `::before` paints a translucent recessed collar as a **ring only** (transparent over the cap) so it reads the same on paper and dark skins.
- Blurred prev/next track thumbnails (`.ctrl__thumb-wrap`) are hidden — they fought the metal face.
- **Position:** both sit on one horizontal axis through the centre of the artwork (`.art-wrap` is `display: grid`, so no inline baseline gap offsets the centre line) and are pushed outward by `--orb-clearance` (0.6–1.15rem) with `margin-inline`, not `transform` — hover / press transforms stay free. `.transport` reserves the same amount in `padding-inline`, so the caps can never be clipped by the player box or the stage.

## Skins (era via functional UI)

**Shipping skins today:** `deck` + `tape` only (see [`THEMES.md`](./THEMES.md)). Rows below for `cassette` / `tape-alt` are historical references; storage migrates those ids to `tape`.

Each skin evokes an era through **controls and type**, not copylike physical case details.

| id | Era / functional grammar | Type | Accent | Art |
|----|--------------------------|------|--------|-----|
| `deck` | Analog radio / DJ — large type, high-contrast, tactile pads | Space Grotesk chips + Anton titles | Coral/sand | Circular platter: darkest PVC band just outside the paper label, groove contrast, rim specular, spinning glint that pauses with the record |
| `cassette` | Sony-style shell (ManzDev/twitch-cassette) — blue window, paper label, magnetic shield | **Permanent Marker** label (betodealmeida/cassette-tape-player) + Plex Mono UI | Tape green | Wide cassette; title on ruled paper label + Side A; differential reel speeds |
| `tape-alt` | Pure CSS orange cassette (mrtoxas/cassette-tape-css) — cream header, spoked reels | **Rowdies** side badge + **Homemade Apple** title | Sunset coral | Orange body + inset window; reels spin while playing |
| `tape` | Layered reel deck ([andrewstephens75/as-tape-player](https://github.com/andrewstephens75/as-tape-player)) — upstream reel/sprocket positions; cover on insert | Exp **Tape font** (`tb_radio_tape_font`) | Warm grey deck | Label 2-line ellipsis; legacy `?skin=as-tape` / `cassette` / `mixtape` → `tape` |

Default: **`deck`**. Cycle: Shift+S. Force: `?skin=tape|deck`.

### Tape skin attributions

| Source | Adapted |
|--------|---------|
| [ManzDev/twitch-cassette](https://github.com/ManzDev/twitch-cassette) | Cassette shell structure: top brand strip, three-part label (top/mid/bot), blue window gap with notched reels + central tape spools, trapezoid magnetic shield, corner screws. Reel spin animations (6s / 8s reverse). |
| [betodealmeida/cassette-tape-player](https://github.com/betodealmeida/cassette-tape-player) | **Permanent Marker** (Google Fonts) on cassette label text — same family as their SVG `.cassette-label`. |
| [mrtoxas/cassette-tape-css](https://github.com/mrtoxas/cassette-tape-css) | Tape-alt skin: orange gradient body, cream header with ruled lines, inset window + spoolbar reels + radial tape film, footer holes/screw. **Rowdies** + **Homemade Apple** fonts from their demo. |
| [andrewstephens75/as-tape-player](https://github.com/andrewstephens75/as-tape-player) | AS Tape skin: `empty.png` tray, layered `reel.png` (clipped L/R), `sprocket.png`, `cassette.png` body; 6s `spinClockwise` on play. Assets copied to `/static/as-tape/`. |

Prior SoundManager2 / CodeFronts references remain in `THEMES.md` as visual study notes; current Cassette implementation follows ManzDev + betodealmeida fonts.

## Do / Don’t

**Do:** reserve equal left/right columns so vinyl stays centered; keep CDJ pads tall (3.2rem); Genre labels one-line via `--chip-fit`; Views/age equal full-width sliders; high-contrast filled CTAs; skin-specific fonts/materials; hard-refresh after token/CSS deploys (`?v=ui-polish-98`); keep dual-source overlap crossfades always on for local audio; log `[xfade] overlap active` in DevTools when overlap runs; compressor fill = amount + separate `#audio-viz`; tilt line icons for dynamism; 2s tooltip delay.

**Don’t:** border strokes on buttons (fill + inner shadow instead — focus rings excepted); let prev/next overlap the artwork or sit off its centre line; overlay Exp or filters on the vinyl; let Request Invite overlap the compressor or timeline; clip Exp Crossfade controls without `overflow-y: auto`; dark text-shadow on dark CTA text; Genre-section scrollbars as the fit strategy; squash `--cdj-pad-h` to fit more chips; wrap Genre labels to two lines; drive compressor fill from GR / spectrum; put Track age back on a CDJ pad grid; purple-AI / cream-terracotta default looks; hard-cut local audio on station change; optional crossfade toggle; reintroduce Shape/Glass/Compress-UI/**orb-position** Exp pickers; treat ~480ms volume swaps as “true crossfade”; stay on iframe when local cache is reachable within 3s; 1px-only focus or state.
