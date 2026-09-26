# Radio UI themes / skins

TypeBeat Radio runs **`deck`** or **`tape`** via `html[data-skin]`. Shared geometry lives in `tokens.css` / `radio.css`; skins change surface grammar. See **`LLM_CONTEXT.md`** (master brief), **`DESIGN_SYSTEM.md`** (norms), and **`HANDOFF.md`** (chat continuity).

## Skins

| id | Label | Notes |
|----|-------|--------|
| `deck` | **Deck** | Default turntable / liquid glass; curved vinyl title on sticker ring |
| `tape` | **TAPE** | [andrewstephens75/as-tape-player](https://github.com/andrewstephens75/as-tape-player) reel deck; assets in `static/as-tape/` |

Legacy `poster` / `glass` / `default` / `signal` → `deck`.  
`as-tape` / `cassette` / `mixtape` / `retro-cassette` → `tape`.

Assets: `static/tokens.css`, `static/skins.css`, `static/skins.js` (sets `data-skin` before paint).

## Locked look (no Exp pickers)

| Attribute | Locked value | Notes |
|-----------|--------------|--------|
| Shape | `cdj-ink` | Pioneer hot-cue pads; Exp Shape section **removed** |
| Glass | `glass` | Animated morph; Soft/Hard/Stained chips **removed** |
| Views UI | `slider` | Always range slider |
| Compressor UI | `meter` | Amount meter under art; Steps/Slider modes **removed** |
| Player layout | rearranged | Reactions orbit art; wide horizontal compressor |

## Experimental panel (current)

**Exp** (right rail) or **Shift+E**:

- **Skin** — Vinyl / Tape  
- **Crossfade** — duration, preload, overlap, start-at (default **7s** + **Aggressive**)  
- **Title transition** — Fade (default) / Wipe horizontal / Blur swap / Type tick  
- **Vinyl title (deck only)** — placement chips (`Top rim` · `Upper wrap` · `Bottom arc`) + scale slider (50–400%)  

**Not in Exp anymore:** Shape, Glass, Views-as-slider toggle, Compressor UI picker, Debug log, Tape-font picker, **orb position tuners** (offsets locked in `DEFAULT_REACT_POS`).

Persists: `tb_radio_skin`, `tb_radio_prolific`, `tb_radio_max_age_months`, `tb_radio_chip_shape` (forced `cdj-ink`), `tb_radio_glass` (forced `glass`), `tb_radio_exp_fold`, `tb_radio_compress_ui` (forced `meter`), `tb_radio_title_xfade`, `tb_radio_vinyl_title_placement`, `tb_radio_vinyl_title_scale`, `typebeat.radio.xfade*`, `typebeat.radio.polishAmount`. Legacy `tb_radio_react_pos` is cleared on load.

| Key | Options |
|-----|---------|
| `tb_radio_title_xfade` | `fade` · `wipe` · `blur` · `tick` (legacy `sponge` migrates to `fade`) |
| `tb_radio_vinyl_title_placement` | `inner_rim_top` · `inner_band_wrap` · `lower_inner_arc` |
| `tb_radio_vinyl_title_scale` | integer percent 50–400 (default 100) |

Hard-refresh: `?v=ui-polish-98`.

## Glass modes (historical)

Only **`glass`** ships. Soft / hard / stained remain documented for archaeology; storage is rewritten to `glass` on load.

| id | Look (legacy) |
|----|----------------|
| `soft` | Large wash + slow cover zoom |
| `hard` | Tighter blur |
| `stained` | Faceted panes |
| `glass` | **Active** — animated morph Hard ↔ Soft |
