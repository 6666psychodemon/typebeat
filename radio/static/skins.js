/* TypeBeat Radio — experimental skins + exp panel.
 * Skins: deck | tape. Legacy ?skin= values migrate to tape/deck.
 */
(function () {
  "use strict";

  const STORAGE_KEY = "tb_radio_skin";
  const STORAGE_PROLIFIC = "tb_radio_prolific";
  const STORAGE_VINYL_TITLE_SCALE = "tb_radio_vinyl_title_scale";
  const STORAGE_VINYL_TITLE_PLACEMENT = "tb_radio_vinyl_title_placement";
  const STORAGE_AGE = "tb_radio_max_age_months";
  const STORAGE_SHAPE = "tb_radio_chip_shape";
  const STORAGE_GLASS = "tb_radio_glass";
  const STORAGE_TAPE_FONT = "tb_radio_tape_font";
  const STORAGE_EXP_FOLD = "tb_radio_exp_fold";
  const STORAGE_TITLE_XFADE = "tb_radio_title_xfade";
  const DEFAULT_SKIN = "deck";
  const LAYOUT_MODE = "rearranged";
  const DEFAULT_LAYOUT = "classic";
  /** Locked: CDJ pads only (Pill removed). */
  const DEFAULT_SHAPE = "cdj-ink";
  const FALLBACK_SHAPE = "cdj-ink";
  /** Locked: animated Glass only. */
  const DEFAULT_GLASS = "glass";
  /** Locked: meter presentation only. */
  const DEFAULT_COMPRESS_UI = "meter";
  /** Locked sticker/title font — Exp font picker removed. */
  const DEFAULT_TAPE_FONT = "permanent-marker";
  /** Title transition: fade (default) | wipe | blur | tick (tape alt modes). */
  const DEFAULT_TITLE_XFADE = "fade";
  const VINYL_TITLE_SCALE_DEFAULT = 100;
  const VINYL_TITLE_SCALE_MIN = 50;
  const VINYL_TITLE_SCALE_MAX = 400;
  const VINYL_TITLE_PLACEMENT_DEFAULT = "inner_rim_top";

  function normalizeVinylTitlePlacement(id) {
    const raw = String(id || "").trim();
    if (
      raw === "inner_rim_top" ||
      raw === "inner_band_wrap" ||
      raw === "lower_inner_arc"
    ) {
      return raw;
    }
    return VINYL_TITLE_PLACEMENT_DEFAULT;
  }
  const TITLE_XFADE_MODES = ["fade", "wipe", "blur", "tick"];
  /** Permanent cassette frame (Label chrome Exp toggle removed). */
  const AS_TAPE_FRAME = "/static/as-tape/cassette.png";
  const AS_TAPE_ASSET = "/static/as-tape/";

  /** Reaction orb positions (% offsets) — locked defaults (Exp tuners removed). */
  const DEFAULT_REACT_POS = {
    vinyl: {
      loop: { x: 6, y: 8 },
      notFit: { x: 6, y: 8 },
      like: { x: 1, y: 8 },
      dislike: { x: 1, y: 8 },
    },
    tape: {
      loop: { x: 0, y: -3 },
      notFit: { x: 0, y: -3 },
      like: { x: -6, y: -13 },
      dislike: { x: -6, y: -13 },
    },
  };

  const SKINS = [
    { id: "deck", label: "Vinyl", tip: "Turntable / vinyl platter — liquid glass" },
    { id: "tape", label: "TAPE", tip: "Layered reel deck — andrewstephens75/as-tape-player" },
  ];

  const LEGACY_TO_SKIN = {
    "": DEFAULT_SKIN,
    poster: DEFAULT_SKIN,
    glass: DEFAULT_SKIN,
    default: DEFAULT_SKIN,
    baseline: DEFAULT_SKIN,
    mixtape: "tape",
    "retro-cassette": "tape",
    cassette: "tape",
    "tape-alt": "tape",
    "as-tape": "tape",
    signal: DEFAULT_SKIN,
  };

  const SHAPE_OPTIONS = [
    { id: "cdj-ink", label: "CDJ", tip: "Pioneer hot-cue pad — recessed well, bevelled cap, outlined type" },
  ];

  /** Legacy + deleted Exp shapes → CDJ ink (Pill removed). */
  const LEGACY_SHAPE_TO = {
    pill: FALLBACK_SHAPE,
    cdj: FALLBACK_SHAPE,
    squircle: FALLBACK_SHAPE,
    petal: FALLBACK_SHAPE,
    drift: FALLBACK_SHAPE,
    warp: FALLBACK_SHAPE,
    wave: FALLBACK_SHAPE,
    teardrop: FALLBACK_SHAPE,
    scallop: FALLBACK_SHAPE,
    swoop: FALLBACK_SHAPE,
    fold: FALLBACK_SHAPE,
    blob: FALLBACK_SHAPE,
    cue: FALLBACK_SHAPE,
  };

  const GLASS_OPTIONS = [
    { id: "glass", label: "Glass", tip: "Slowly animates between Soft and Hard atmosphere" },
  ];

  /** Locked to meter — Exp compressor picker removed. */
  const COMPRESS_UI_OPTIONS = [
    { id: "meter", label: "Meter", tip: "VU / gain-reduction meter" },
  ];

  const COMPRESS_STEP_AMOUNTS = {
    low: 0.08,
    mid: 0.205,
    high: 0.72,
  };

  const AGE_OPTIONS = [
    { months: null, label: "All" },
    { months: 6, label: "<6m" },
    { months: 18, label: "<18m" },
    { months: 24, label: "<2y" },
    { months: 60, label: "<5y" },
    { months: 120, label: "<10y" },
  ];

  function snapMaxAgeMonths(n) {
    if (!Number.isFinite(n) || n <= 0) return null;
    const allowed = AGE_OPTIONS.map((o) => o.months).filter((m) => m != null);
    if (allowed.includes(n)) return n;
    let best = allowed[0];
    let bestDist = Math.abs(n - best);
    for (const m of allowed) {
      const d = Math.abs(n - m);
      if (d < bestDist) {
        best = m;
        bestDist = d;
      }
    }
    return best;
  }

  const XFADE_MODE_OPTIONS = [
    { id: "graph7", label: "7s crossfade", tip: "True A↔B overlap ~7s (default)" },
    { id: "graph3", label: "3s crossfade", tip: "True A↔B overlap ~3s" },
    { id: "volume7", label: "Volume 7s", tip: "Element volume fade, 7s" },
    { id: "volume3", label: "Volume 3s", tip: "Element volume fade, 3s" },
    { id: "instant", label: "Instant", tip: "Hard cut — no overlap" },
  ];

  const XFADE_PRELOAD_OPTIONS = [
    { id: "aggressive", label: "Aggressive", tip: "Prime next track ahead (smoothest Next — default)" },
    { id: "early", label: "Early", tip: "Preload immediately on track start" },
    { id: "on_skip", label: "On skip", tip: "Fetch only when Next/Prev pressed" },
    { id: "off", label: "Off", tip: "No background preload" },
  ];

  const XFADE_OVERLAP_OPTIONS = [
    { id: "auto", label: "Auto", tip: "Use mode duration (7s / 3s / etc.)" },
    { id: "0", label: "0", tip: "Force instant handoff (0ms overlap)" },
    { id: "3000", label: "3s", tip: "Override overlap to 3 seconds" },
    { id: "7000", label: "7s", tip: "Override overlap to 7 seconds" },
    { id: "10000", label: "10s", tip: "Override overlap to 10 seconds" },
  ];

  const XFADE_START_OPTIONS = [
    { id: "0", label: "0s", tip: "Incoming track starts at 0:00 (smoothest — default)" },
    { id: "3", label: "3s", tip: "Skip first 3s on handoff" },
    { id: "5", label: "5s", tip: "Skip first 5s on handoff" },
    { id: "10", label: "10s", tip: "Skip first 10s on handoff" },
  ];

  const root = document.documentElement;

  let current = DEFAULT_SKIN;
  let prolificOn = false;
  let vinylTitleScale = VINYL_TITLE_SCALE_DEFAULT;
  let vinylTitlePlacement = VINYL_TITLE_PLACEMENT_DEFAULT;
  /** @type {number|null} */
  let maxAgeMonths = null;
  let titleXfadeMode = DEFAULT_TITLE_XFADE;
  let chipShape = DEFAULT_SHAPE;
  let panelOpen = false;
  let glassMode = DEFAULT_GLASS;
  let tapeFont = DEFAULT_TAPE_FONT;
  /** Locked: views slider only. */
  let viewsUiSlider = true;
  let compressUi = DEFAULT_COMPRESS_UI;
  let asTapeLabelEl = null;
  let asTapeFrameEl = null;
  let asTapeCoverEl = null;

  function capsLabel(text) {
    return String(text || "").toUpperCase();
  }

  /** Keep in sync with radio.js ageTierLabelMarkup (skins inits before radio.js). */
  function ageTierLabelMarkup(label) {
    const raw = capsLabel(label);
    if (!raw) return "";
    if (raw === "ALL") {
      return '<span class="views-tier-lines tier-lines"><span>ALL</span></span>';
    }
    const lt = raw.match(/^<(\d+)(M|Y)$/);
    if (lt) {
      return `<span class="views-tier-lines tier-lines"><span>&lt;${lt[1]}</span><span>${lt[2]}</span></span>`;
    }
    return `<span class="views-tier-lines tier-lines"><span>${raw}</span></span>`;
  }

  function normalizeTitleXfadeMode(mode) {
    const id = String(mode || "").trim().toLowerCase();
    if (id === "sponge") return DEFAULT_TITLE_XFADE;
    return TITLE_XFADE_MODES.includes(id) ? id : DEFAULT_TITLE_XFADE;
  }

  function indexOfSkin(id) {
    const i = SKINS.findIndex((s) => s.id === id);
    return i === -1 ? -1 : i;
  }

  function normalizeSkin(id) {
    const raw = (id == null ? "" : String(id)).trim().toLowerCase();
    if (Object.prototype.hasOwnProperty.call(LEGACY_TO_SKIN, raw)) {
      return LEGACY_TO_SKIN[raw];
    }
    if (indexOfSkin(raw) >= 0) return raw;
    return DEFAULT_SKIN;
  }

  function normalizeTapeFont(_id) {
    return DEFAULT_TAPE_FONT;
  }

  function normalizeGlass(_id) {
    return DEFAULT_GLASS;
  }

  function normalizeCompressUi(id) {
    const raw = (id == null ? "" : String(id)).trim().toLowerCase();
    if (COMPRESS_UI_OPTIONS.some((t) => t.id === raw)) return raw;
    return DEFAULT_COMPRESS_UI;
  }

  function normalizeShape(id) {
    const raw = (id == null ? "" : String(id)).trim().toLowerCase();
    if (Object.prototype.hasOwnProperty.call(LEGACY_SHAPE_TO, raw)) {
      return LEGACY_SHAPE_TO[raw];
    }
    if (SHAPE_OPTIONS.some((t) => t.id === raw)) return raw;
    return DEFAULT_SHAPE;
  }

  function readStored(key) {
    try {
      return localStorage.getItem(key);
    } catch (err) {
      return null;
    }
  }

  function store(key, value) {
    try {
      if (value === null || value === undefined || value === "") {
        localStorage.removeItem(key);
      } else {
        localStorage.setItem(key, String(value));
      }
    } catch (err) {
      /* private mode */
    }
  }

  /* Apply skin before first paint so there is no baseline flash. */
  const storedRaw = readStored(STORAGE_KEY);
  current = normalizeSkin(storedRaw);
  const fromUrl = new URLSearchParams(location.search).get("skin");
  if (fromUrl !== null) {
    current = normalizeSkin(fromUrl);
    store(STORAGE_KEY, current);
  } else if (storedRaw !== current) {
    /* Migrate legacy poster / empty / glass → deck */
    store(STORAGE_KEY, current);
  }
  root.setAttribute("data-skin", current);

  prolificOn = readStored(STORAGE_PROLIFIC) === "1";

  function normalizeVinylTitleScale(n) {
    const v = Number(n);
    if (!Number.isFinite(v)) return VINYL_TITLE_SCALE_DEFAULT;
    return Math.min(
      VINYL_TITLE_SCALE_MAX,
      Math.max(VINYL_TITLE_SCALE_MIN, Math.round(v))
    );
  }

  vinylTitleScale = normalizeVinylTitleScale(
    readStored(STORAGE_VINYL_TITLE_SCALE) ?? VINYL_TITLE_SCALE_DEFAULT
  );

  vinylTitlePlacement = normalizeVinylTitlePlacement(
    readStored(STORAGE_VINYL_TITLE_PLACEMENT) ?? VINYL_TITLE_PLACEMENT_DEFAULT
  );

  const storedTitleXfade = readStored(STORAGE_TITLE_XFADE);
  titleXfadeMode = normalizeTitleXfadeMode(storedTitleXfade);
  if (storedTitleXfade === "sponge") {
    store(STORAGE_TITLE_XFADE, titleXfadeMode);
  }
  root.setAttribute("data-title-xfade", titleXfadeMode);

  root.removeAttribute("data-tape-glass");
  try {
    localStorage.removeItem("tb_radio_tape_glass");
  } catch (err) {
    /* private mode */
  }

  applyReactPosVars();
  try {
    localStorage.removeItem("tb_radio_react_pos");
  } catch (err) {
    /* private mode */
  }

  /* Deck vinyl name + spin are always on (legacy Exp toggles removed). */
  root.classList.add("is-vinyl-name", "is-vinyl-spin");
  root.removeAttribute("data-vinyl-font");
  try {
    localStorage.removeItem("tb_radio_vinyl_name");
    localStorage.removeItem("tb_radio_vinyl_spin");
    localStorage.removeItem("tb_radio_vinyl_font");
  } catch (err) {
    /* private mode */
  }
  root.setAttribute("data-testing", LAYOUT_MODE);
  root.setAttribute("data-layout", DEFAULT_LAYOUT);
  try {
    localStorage.removeItem("tb_radio_testing");
    localStorage.removeItem("tb_radio_loop_icon");
    localStorage.removeItem("tb_radio_react_icons");
  } catch (err) {
    /* private mode */
  }


  glassMode = DEFAULT_GLASS;
  root.setAttribute("data-glass", glassMode);
  store(STORAGE_GLASS, glassMode);
  try {
    localStorage.removeItem("tb_radio_tape_chrome");
  } catch (err) {
    /* private mode */
  }
  root.removeAttribute("data-tape-chrome");

  tapeFont = DEFAULT_TAPE_FONT;
  root.setAttribute("data-tape-font", tapeFont);
  store(STORAGE_TAPE_FONT, tapeFont);

  /* Views = slider only; drop chips mode + Exp toggle. */
  viewsUiSlider = true;
  root.setAttribute("data-views-ui", "slider");
  try {
    localStorage.removeItem("tb_radio_views_slider");
  } catch (err) {
    /* private mode */
  }

  /* Compressor = meter only; drop slider/steps Exp picker. */
  compressUi = DEFAULT_COMPRESS_UI;
  root.setAttribute("data-compress-ui", compressUi);
  try {
    localStorage.removeItem("tb_radio_compress_ui");
  } catch (err) {
    /* private mode */
  }

  const storedFold = readStored(STORAGE_EXP_FOLD);
  panelOpen = storedFold !== "1";
  root.setAttribute("data-exp-fold", panelOpen ? "off" : "on");

  /* Shape locked to CDJ ink — Exp Shape picker removed. */
  chipShape = DEFAULT_SHAPE;
  root.setAttribute("data-shape", chipShape);
  root.setAttribute("data-chip-shape", chipShape);
  store(STORAGE_SHAPE, chipShape);
  try {
    /* Drop legacy shape ids from storage so reload stays CDJ. */
    const storedShapeRaw = readStored(STORAGE_SHAPE);
    if (storedShapeRaw && normalizeShape(storedShapeRaw) !== DEFAULT_SHAPE) {
      store(STORAGE_SHAPE, DEFAULT_SHAPE);
    }
  } catch (err) {
    /* private mode */
  }

  const ageRaw = readStored(STORAGE_AGE);
  if (ageRaw) {
    const n = Number(ageRaw);
    maxAgeMonths = snapMaxAgeMonths(n);
    if (maxAgeMonths != null && String(maxAgeMonths) !== ageRaw) {
      store(STORAGE_AGE, String(maxAgeMonths));
    }
  }

  function applySkin(id) {
    current = normalizeSkin(id);
    root.setAttribute("data-skin", current);
    store(STORAGE_KEY, current);
    syncSkinChips();
    syncSkinChrome();
    syncTapeLabels();
    syncVinylPathForSkin();
    syncVinylTitleScaleSection();
    notifyArtTitle();
  }

  function syncSkinChrome() {
    if (current === "tape") {
      ensureAsTapeChrome();
      return;
    }
    ensureVinylSticker();
    const wrap = document.getElementById("art-wrap");
    if (wrap) wrap.querySelectorAll(".title-sponge-canvas").forEach((c) => c.remove());
  }

  function setChipShape(_id) {
    /* Shape picker removed — always CDJ ink. */
    chipShape = DEFAULT_SHAPE;
    root.setAttribute("data-shape", chipShape);
    root.setAttribute("data-chip-shape", chipShape);
    store(STORAGE_SHAPE, chipShape);
  }

  function setGlassMode(_id) {
    glassMode = DEFAULT_GLASS;
    root.setAttribute("data-glass", glassMode);
    store(STORAGE_GLASS, glassMode);
    syncGlassChips();
  }

  function setTapeFont(_id) {
    tapeFont = DEFAULT_TAPE_FONT;
    root.setAttribute("data-tape-font", tapeFont);
    store(STORAGE_TAPE_FONT, tapeFont);
  }

  function setCompressUi(_id) {
    compressUi = DEFAULT_COMPRESS_UI;
    root.setAttribute("data-compress-ui", compressUi);
    syncCompressSteps();
  }

  function syncTapeFrameAsset() {
    const frame =
      asTapeFrameEl || document.querySelector(".as-tape-chrome__frame");
    if (!frame) return;
    asTapeFrameEl = frame;
    if (frame.getAttribute("src") !== AS_TAPE_FRAME) {
      frame.setAttribute("src", AS_TAPE_FRAME);
    }
  }


  function applyCompressStep(step) {
    const amount = COMPRESS_STEP_AMOUNTS[step];
    const api = window.TypeBeatRadio;
    if (typeof amount === "number" && api && typeof api.applyPolishAmount === "function") {
      api.applyPolishAmount(amount, { persist: true, log: true });
    }
    syncCompressSteps();
  }

  function syncCompressSteps() {
    const host = document.getElementById("compress-steps");
    if (!host) return;
    const api = window.TypeBeatRadio;
    const pct = api && typeof api.getPolishPct === "function" ? api.getPolishPct() : 25;
    const gr = document.getElementById("compress-steps-gr");
    if (gr) gr.textContent = `${pct}%`;
    let active = "mid";
    if (pct <= 18) active = "low";
    else if (pct >= 62) active = "high";
    host.querySelectorAll(".compress-step").forEach((btn) => {
      const on = (btn.dataset.compressStep || "") === active;
      btn.setAttribute("aria-pressed", on ? "true" : "false");
    });
  }

  function wireCompressStepButtons() {
    const host = document.getElementById("compress-steps");
    if (!host || host.dataset.wired === "1") return;
    host.dataset.wired = "1";
    host.querySelectorAll(".compress-step").forEach((btn) => {
      btn.addEventListener("click", () => applyCompressStep(btn.dataset.compressStep));
    });
    syncCompressSteps();
  }

  function cycleSkin() {
    applySkin(SKINS[(indexOfSkin(current) + 1) % SKINS.length].id);
  }

  function pushFiltersToRadio() {
    const api = window.TypeBeatRadio;
    if (api && typeof api.applyExperimentalFilters === "function") {
      api.applyExperimentalFilters({
        prolific: prolificOn,
        maxAgeMonths,
      });
    }
  }

  function notifyArtTitle() {
    const api = window.TypeBeatRadio;
    if (api && typeof api.syncArtTitle === "function") {
      api.syncArtTitle();
    }
    syncSkinChrome();
    syncVinylTitleText();
    syncTapeLabels();
  }

  function setProlific(on) {
    prolificOn = Boolean(on);
    store(STORAGE_PROLIFIC, prolificOn ? "1" : null);
    syncProlificChip();
    pushFiltersToRadio();
  }

  function setAge(months) {
    maxAgeMonths = months;
    store(STORAGE_AGE, months == null ? null : String(months));
    syncAgeChips();
    pushFiltersToRadio();
  }

  function vinylTitleActiveLayer() {
    if (!vinylTextEl || !vinylTextElB) return null;
    if (vinylTextEl.classList.contains("is-active")) {
      return { el: vinylTextEl, path: vinylTextPath };
    }
    if (vinylTextElB.classList.contains("is-active")) {
      return { el: vinylTextElB, path: vinylTextPathB };
    }
    return { el: vinylTextEl, path: vinylTextPath };
  }

  function vinylTitleClearInactiveLayer() {
    if (!vinylTextEl || !vinylTextElB) return;
    const inactive = vinylTextEl.classList.contains("is-active") ? vinylTextElB : vinylTextEl;
    const inactivePath =
      inactive === vinylTextEl ? vinylTextPath : vinylTextPathB;
    if (inactivePath) inactivePath.textContent = "";
    inactive.style.fontSize = "";
    inactive.style.letterSpacing = "";
    vinylTitleClearPathFill(inactive, inactivePath);
  }

  function refitVinylTitleLayers() {
    if ((root.getAttribute("data-skin") || DEFAULT_SKIN) !== "deck") return;
    const rim = lastVinylTitle;
    if (!rim) return;
    if (!vinylSvg) buildVinylTitle();
    if (!vinylTextPath || !vinylTextPathB) bindVinylTitleDom(vinylSvg);
    const active = vinylTitleActiveLayer();
    if (!active || !active.el || !active.path) return;
    const text = (active.path.textContent || "").trim() || rim;
    if (!text) return;
    fitVinylTitleFont(text, active.el, active.path);
  }

  function setVinylTitleScale(pct) {
    vinylTitleScale = normalizeVinylTitleScale(pct);
    store(
      STORAGE_VINYL_TITLE_SCALE,
      vinylTitleScale === VINYL_TITLE_SCALE_DEFAULT ? null : String(vinylTitleScale)
    );
    syncVinylTitleScaleControls();
    refitVinylTitleLayers();
  }

  function getVinylTitlePlacement() {
    return vinylTitlePlacement;
  }

  function setVinylTitlePlacement(id) {
    const next = normalizeVinylTitlePlacement(id);
    if (next === vinylTitlePlacement) {
      syncVinylTitlePlacementChips();
      return;
    }
    vinylTitlePlacement = next;
    store(STORAGE_VINYL_TITLE_PLACEMENT, next);
    const preset = getVinylTitlePlacementPreset();
    VINYL_TITLE_RING_R = preset.ringRBase;
    syncVinylTitleRingPath(VINYL_TITLE_RING_R);
    syncVinylTitlePlacementChips();
    refitVinylTitleLayers();
  }

  function syncVinylTitlePlacementChips() {
    if (!vinylTitlePlacementChipsEl) return;
    vinylTitlePlacementChipsEl.querySelectorAll(".exp-chip").forEach((btn) => {
      const on = (btn.dataset.vinylTitlePlacement || "") === vinylTitlePlacement;
      btn.classList.toggle("is-active", on);
      btn.setAttribute("aria-pressed", on ? "true" : "false");
    });
  }

  function syncVinylTitleScaleControls() {
    if (vinylTitleScaleInput) {
      vinylTitleScaleInput.value = String(vinylTitleScale);
      vinylTitleScaleInput.setAttribute("aria-valuenow", String(vinylTitleScale));
      vinylTitleScaleInput.setAttribute("aria-valuetext", `${vinylTitleScale} percent`);
    }
    if (vinylTitleScaleReadout) {
      vinylTitleScaleReadout.textContent = `${vinylTitleScale}%`;
    }
  }

  function syncVinylTitleDeckExpSections() {
    const deck = current === "deck";
    if (vinylTitlePlacementSec) vinylTitlePlacementSec.hidden = !deck;
    if (vinylTitleScaleSec) vinylTitleScaleSec.hidden = !deck;
  }

  function syncVinylTitleScaleSection() {
    syncVinylTitleDeckExpSections();
  }

  function setTitleXfadeMode(mode) {
    titleXfadeMode = normalizeTitleXfadeMode(mode);
    store(STORAGE_TITLE_XFADE, titleXfadeMode);
    root.setAttribute("data-title-xfade", titleXfadeMode);
    if (titleXfadeSelect) titleXfadeSelect.value = titleXfadeMode;
  }

  function applyReactPosVars() {
    const v = DEFAULT_REACT_POS.vinyl;
    const t = DEFAULT_REACT_POS.tape;
    const set = (prefix, cfg) => {
      root.style.setProperty(`--react-${prefix}-loop-x`, `${cfg.loop.x}%`);
      root.style.setProperty(`--react-${prefix}-loop-y`, `${cfg.loop.y}%`);
      root.style.setProperty(`--react-${prefix}-x-x`, `${cfg.notFit.x}%`);
      root.style.setProperty(`--react-${prefix}-x-y`, `${cfg.notFit.y}%`);
      root.style.setProperty(`--react-${prefix}-like-x`, `${cfg.like.x}%`);
      root.style.setProperty(`--react-${prefix}-like-y`, `${cfg.like.y}%`);
      root.style.setProperty(`--react-${prefix}-dislike-x`, `${cfg.dislike.x}%`);
      root.style.setProperty(`--react-${prefix}-dislike-y`, `${cfg.dislike.y}%`);
    };
    set("vinyl", v);
    set("tape", t);
  }

  /* --- Now-playing strip (deck / signal) --- */
  function buildNowPlaying() {
    const player = document.querySelector(".player");
    const source = document.getElementById("art-title-text");
    if (!player || !source || document.querySelector(".skin-nowplaying")) return;

    const strip = document.createElement("div");
    strip.className = "skin-nowplaying";
    strip.setAttribute("aria-hidden", "true");

    const sync = () => {
      strip.textContent = (source.textContent || "").trim();
    };
    sync();
    new MutationObserver(sync).observe(source, {
      childList: true,
      characterData: true,
      subtree: true,
    });

    const controls = player.querySelector(".player-controls");
    player.insertBefore(strip, controls || null);
  }

  /* --- Curved track name (vinyl / arc) — Deck only --- */
  let vinylSvg = null;
  let vinylTextPath = null;
  let vinylTextEl = null;
  let vinylTextPathB = null;
  let vinylTextElB = null;
  let vinylTitleFlip = false;
  let vinylTitleAnim = 0;
  let vinylTitleTickTimer = 0;
  let lastVinylTitle = "";
  let lastTapeTitle = "";
  let tapeTitleAnimTimer = 0;

  function clearTapeTitleAnimClasses(slot) {
    if (!slot) return;
    slot.querySelectorAll(".as-tape-chrome__label-text").forEach((el) => {
      el.classList.remove("is-leaving", "is-entering");
    });
  }

  function finishTapeTitleSwap(nextEl, prevEl) {
    const slot =
      (nextEl && nextEl.closest(".as-tape-chrome__label-slot")) ||
      document.querySelector(".as-tape-chrome__label-slot");
    if (prevEl) prevEl.classList.remove("is-active", "is-leaving", "is-entering");
    if (nextEl) {
      nextEl.classList.add("is-active");
      nextEl.classList.remove("is-leaving", "is-entering");
    }
    clearTapeTitleAnimClasses(slot);
    fitTapeLabels();
  }

  function scrambleTickText(target, progress) {
    const chars = "ABCDEFGHJKLMNPQRSTUVWXYZ0123456789";
    const out = [];
    for (let i = 0; i < target.length; i += 1) {
      if (i / target.length < progress) {
        out.push(target[i]);
      } else if (target[i] === " ") {
        out.push(" ");
      } else {
        out.push(chars[(Math.random() * chars.length) | 0]);
      }
    }
    return out.join("");
  }

  function runTapeAltTitleTransition(prevEl, nextEl, prev, display) {
    const mode = titleXfadeMode;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const ms = Math.max(400, Math.min(2800, titleFadeMs()));
    if (tapeTitleAnimTimer) {
      window.clearTimeout(tapeTitleAnimTimer);
      tapeTitleAnimTimer = 0;
    }
    clearTapeTitleAnimClasses(prevEl && prevEl.closest(".as-tape-chrome__label-slot"));

    if (reduce || !prev || !display) {
      nextEl.textContent = display;
      finishTapeTitleSwap(nextEl, prevEl);
      return;
    }

    nextEl.textContent = display;
    prevEl.textContent = prev;

    if (mode === "wipe") {
      prevEl.classList.add("is-leaving");
      prevEl.classList.remove("is-active");
      nextEl.classList.add("is-entering", "is-active");
      tapeTitleAnimTimer = window.setTimeout(() => {
        tapeTitleAnimTimer = 0;
        finishTapeTitleSwap(nextEl, prevEl);
      }, ms);
      return;
    }

    if (mode === "blur") {
      prevEl.classList.add("is-leaving");
      prevEl.classList.remove("is-active");
      nextEl.classList.add("is-entering");
      nextEl.classList.remove("is-active");
      tapeTitleAnimTimer = window.setTimeout(() => {
        nextEl.classList.add("is-active");
        nextEl.classList.remove("is-entering");
        prevEl.classList.remove("is-leaving");
        tapeTitleAnimTimer = window.setTimeout(() => {
          tapeTitleAnimTimer = 0;
          finishTapeTitleSwap(nextEl, prevEl);
        }, ms);
      }, Math.round(ms * 0.45));
      return;
    }

    if (mode === "tick") {
      prevEl.classList.remove("is-active");
      nextEl.classList.add("is-active", "is-entering");
      nextEl.textContent = scrambleTickText(display, 0);
      const steps = 16;
      let step = 0;
      const tickMs = Math.max(16, Math.round((ms * 0.42) / steps));
      const run = () => {
        step += 1;
        const p = step / steps;
        nextEl.textContent = p >= 1 ? display : scrambleTickText(display, p);
        if (step < steps) {
          tapeTitleAnimTimer = window.setTimeout(run, tickMs);
        } else {
          tapeTitleAnimTimer = 0;
          finishTapeTitleSwap(nextEl, prevEl);
        }
      };
      tapeTitleAnimTimer = window.setTimeout(run, tickMs);
      return;
    }

    nextEl.textContent = display;
    finishTapeTitleSwap(nextEl, prevEl);
  }

  function ensureVinylSticker() {
    const art = document.getElementById("btn-play");
    if (!art) return;
    let sticker = art.querySelector(".art__sticker");
    if (!sticker) {
      sticker = document.createElement("span");
      sticker.className = "art__sticker";
      const firstImg = art.querySelector(".art__img");
      if (firstImg) art.insertBefore(sticker, firstImg);
      else art.prepend(sticker);
    }
    let media = sticker.querySelector(".art__sticker-media");
    if (!media) {
      media = document.createElement("span");
      media.className = "art__sticker-media";
      media.setAttribute("aria-hidden", "true");
      sticker.insertBefore(media, sticker.firstChild);
    }
    art.querySelectorAll(".art__img").forEach((img) => {
      if (img.parentElement !== media) media.appendChild(img);
    });
  }

  function repairVinylTitleClasses(svg) {
    if (!svg) return;
    svg.querySelectorAll("text.vinyl-title__text, text").forEach((textEl) => {
      const cls = textEl.getAttribute("class") || "";
      if (cls.includes("vinyl-title__text--a") && cls.includes("is-active")) {
        textEl.setAttribute("class", "vinyl-title__text vinyl-title__text--a is-active");
      } else if (cls.includes("vinyl-title__text--b")) {
        textEl.setAttribute("class", "vinyl-title__text vinyl-title__text--b");
      } else if (cls.includes("vinyl-title__text--a")) {
        textEl.setAttribute("class", "vinyl-title__text vinyl-title__text--a");
      }
    });
  }

  function bindVinylTitleDom(svg) {
    vinylSvg = svg;
    vinylTextPath =
      svg.querySelector(".vinyl-title__text--a .vinyl-title__path") ||
      svg.querySelector(".vinyl-title__text--a textPath");
    vinylTextEl =
      svg.querySelector("text.vinyl-title__text--a") ||
      svg.querySelector(".vinyl-title__text--a");
    vinylTextPathB =
      svg.querySelector(".vinyl-title__text--b .vinyl-title__path") ||
      svg.querySelector(".vinyl-title__text--b textPath");
    vinylTextElB =
      svg.querySelector("text.vinyl-title__text--b") ||
      svg.querySelector(".vinyl-title__text--b");
  }

  function mountVinylTitleElement(svg) {
    ensureVinylSticker();
    const art = document.getElementById("btn-play");
    const sticker = art && art.querySelector(".art__sticker");
    if (!sticker) return false;
    if (svg.parentElement !== sticker) sticker.appendChild(svg);
    return true;
  }

  /**
   * Curved vinyl title on sticker label (viewBox 0 0 100 100; platter center 50,50).
   * Three EXP presets — paths stay inside label; outer ink ≤ VINYL_TITLE_MAX_OUTER_R.
   * fitVinylTitleFont: natural spacing; tracking capped at VINYL_TITLE_TRACK_OVERFLOW_MAX.
   */
  const VINYL_STICKER_OUTER_R = 50;
  const VINYL_STICKER_CENTER = 50;
  /** Conservative ink limit inside sticker rim (r=50); includes stroke margin. */
  const VINYL_TITLE_MAX_OUTER_R = 49;
  const VINYL_TITLE_PLACEMENT_OPTIONS = [
    {
      id: "inner_rim_top",
      label: "Top rim",
      tip: "Inner rim arc at 12 o'clock above play — default",
      ringRBase: 44.2,
      ringRMax: 44.8,
      ringRMin: 37.5,
      startOffset: "50%",
      side: "left",
      dy: -0.34,
      arcSoftCap: 0.72,
      pathD(rr) {
        const y = VINYL_STICKER_CENTER;
        const x0 = VINYL_STICKER_CENTER - rr;
        const x1 = VINYL_STICKER_CENTER + rr;
        return `M ${x0},${y} A ${rr},${rr} 0 0,1 ${x1},${y}`;
      },
    },
    {
      id: "inner_band_wrap",
      label: "Upper wrap",
      tip: "Full ring inside label — readable upper arc around play",
      ringRBase: 43.2,
      ringRMax: 44,
      ringRMin: 37.5,
      startOffset: "25%",
      side: "left",
      dy: -0.3,
      arcSoftCap: 0.38,
      pathD(rr) {
        const c = VINYL_STICKER_CENTER;
        const xR = c + rr;
        const xL = c - rr;
        return `M ${xR},${c} A ${rr},${rr} 0 1,1 ${xL},${c} A ${rr},${rr} 0 1,1 ${xR},${c}`;
      },
    },
    {
      id: "lower_inner_arc",
      label: "Bottom arc",
      tip: "Inner arc at 6 o'clock below pause — right-side up on label",
      ringRBase: 43.6,
      ringRMax: 44.2,
      ringRMin: 37.5,
      startOffset: "50%",
      side: "left",
      dy: 0.32,
      arcSoftCap: 0.72,
      pathD(rr) {
        const y = VINYL_STICKER_CENTER;
        const x0 = VINYL_STICKER_CENTER + rr;
        const x1 = VINYL_STICKER_CENTER - rr;
        return `M ${x0},${y} A ${rr},${rr} 0 0,1 ${x1},${y}`;
      },
    },
  ];

  function getVinylTitlePlacementPreset(placementId) {
    const id = normalizeVinylTitlePlacement(placementId ?? vinylTitlePlacement);
    return (
      VINYL_TITLE_PLACEMENT_OPTIONS.find((o) => o.id === id) ||
      VINYL_TITLE_PLACEMENT_OPTIONS[0]
    );
  }

  let VINYL_TITLE_RING_R = getVinylTitlePlacementPreset().ringRBase;

  function vinylTitleClampRingR(r, preset) {
    const p = preset || getVinylTitlePlacementPreset();
    const hi = Math.min(p.ringRMax, VINYL_TITLE_MAX_OUTER_R - 0.45);
    return Math.max(p.ringRMin, Math.min(r, hi));
  }

  function vinylTitleRingPathD(r, preset) {
    const p = preset || getVinylTitlePlacementPreset();
    const rr = vinylTitleClampRingR(r, p);
    return p.pathD(rr);
  }

  const VINYL_TITLE_FONT_MIN = 5;
  const VINYL_TITLE_FONT_SEARCH_MAX = 400;
  const VINYL_TITLE_TRACK_MAX = 0.06;
  const VINYL_TITLE_TRACK_MIN = -0.15;
  /** Hard cap on positive tracking from overflow fit (prefer shrink / ellipsis). */
  const VINYL_TITLE_TRACK_OVERFLOW_MAX = 0.06;

  function vinylTitleTrackMinForText(text) {
    const len = String(text || "").trim().length;
    if (len <= 12) return -0.12;
    if (len <= 28) return -0.13;
    return VINYL_TITLE_TRACK_MIN;
  }

  function vinylTitleArcSoftMax(path, preset) {
    const p = preset || getVinylTitlePlacementPreset();
    if (!path || typeof path.getTotalLength !== "function") return 0;
    return path.getTotalLength() * p.arcSoftCap;
  }

  function vinylTitleClearPathFill(textEl, textPathEl) {
    if (textEl) {
      textEl.removeAttribute("textLength");
      textEl.removeAttribute("lengthAdjust");
    }
    if (textPathEl) {
      textPathEl.removeAttribute("textLength");
      textPathEl.removeAttribute("lengthAdjust");
    }
  }

  /** Letter-spacing (em) so getComputedTextLength() ≈ targetLen at fixed font-size. */
  function vinylTitleSpacingForPathLength(textEl, targetLen, trackMin, trackMax) {
    if (!textEl || !(targetLen > 0)) return trackMin;
    let lo = trackMin;
    let hi = Math.min(trackMax, VINYL_TITLE_TRACK_OVERFLOW_MAX);
    let best = lo;
    for (let i = 0; i < 52; i++) {
      const mid = (lo + hi) / 2;
      textEl.style.letterSpacing = `${mid}em`;
      let m = 0;
      try {
        m = textEl.getComputedTextLength();
      } catch (err) {
        m = 0;
      }
      if (m < targetLen * 0.996) {
        lo = mid;
        best = mid;
      } else {
        best = mid;
        hi = mid;
      }
    }
    return best;
  }

  function vinylTitleFontSearchHi(rawText, path) {
    const len = Math.max(1, String(rawText || "").trim().length);
    const pathLen =
      path && typeof path.getTotalLength === "function" ? path.getTotalLength() : 280;
    const est = (pathLen / len) * 3.1;
    const shortBoost = len <= 14 ? 96 : len <= 28 ? 48 : 0;
    return Math.min(VINYL_TITLE_FONT_SEARCH_MAX, Math.max(52, est + shortBoost));
  }

  function syncVinylTitleRingPath(ringR) {
    const preset = getVinylTitlePlacementPreset();
    const r = ringR != null ? ringR : VINYL_TITLE_RING_R;
    const d = vinylTitleRingPathD(r, preset);
    const path =
      (vinylSvg && vinylSvg.querySelector("#vinyl-path-deck")) ||
      document.getElementById("vinyl-path-deck");
    if (path) path.setAttribute("d", d);
    const scope = vinylSvg || document;
    scope.querySelectorAll(".vinyl-title__path, textPath").forEach((tp) => {
      tp.setAttribute("side", preset.side);
      tp.setAttribute("startOffset", preset.startOffset);
      tp.setAttribute("text-anchor", "middle");
      tp.setAttribute("dy", String(preset.dy));
    });
  }

  function vinylTitleInkPad(textEl) {
    let stroke = 0.65;
    try {
      const sw = parseFloat(getComputedStyle(textEl).strokeWidth);
      if (Number.isFinite(sw)) stroke = sw;
    } catch (err) {
      /* deck default */
    }
    return stroke * 0.5 + 0.45;
  }

  function vinylTitleParseFontSizePx(textEl) {
    if (!textEl || !textEl.style || !textEl.style.fontSize) return 18;
    const n = parseFloat(textEl.style.fontSize);
    return Number.isFinite(n) ? n : 18;
  }

  function vinylTitleParseLetterSpacingEm(textEl) {
    if (!textEl || !textEl.style) return 0;
    const m = /^([\d.+-]+)/.exec(textEl.style.letterSpacing || "");
    if (!m) return 0;
    const v = parseFloat(m[1]);
    return Number.isFinite(v) ? v : 0;
  }

  /** Max distance from sticker center to outermost glyph/stroke ink (viewBox units). */
  function vinylTitleMaxOuterRadius(textEl, ringR) {
    const preset = getVinylTitlePlacementPreset();
    const pathDy = preset.dy;
    const pad = textEl ? vinylTitleInkPad(textEl) : 0.55;
    if (!textEl) return VINYL_TITLE_MAX_OUTER_R + pad + 1;

    const cx = VINYL_STICKER_CENTER;
    const cy = VINYL_STICKER_CENTER;
    let measuredMax = 0;
    let validGlyphs = 0;

    const numChars =
      typeof textEl.getNumberOfChars === "function" ? textEl.getNumberOfChars() : 0;
    const fsPx = vinylTitleParseFontSizePx(textEl);
    const maxGlyphSpan = Math.max(fsPx * 1.4, 6);

    if (numChars > 0 && typeof textEl.getExtentOfChar === "function") {
      for (let i = 0; i < numChars; i++) {
        let ext;
        try {
          ext = textEl.getExtentOfChar(i);
        } catch (err) {
          continue;
        }
        if (!ext || !(ext.width > 0) || !(ext.height > 0)) continue;
        if (ext.width > maxGlyphSpan * 2.5 || ext.height > maxGlyphSpan * 2.5) continue;

        const corners = [
          [ext.x, ext.y],
          [ext.x + ext.width, ext.y],
          [ext.x, ext.y + ext.height],
          [ext.x + ext.width, ext.y + ext.height],
        ];
        let glyphMax = 0;
        let glyphOk = false;
        for (const [x, y] of corners) {
          const r = Math.hypot(x - cx, y - cy);
          if (r > VINYL_STICKER_OUTER_R + 1.5) continue;
          glyphMax = Math.max(glyphMax, r);
          glyphOk = true;
        }
        if (glyphOk) {
          measuredMax = Math.max(measuredMax, glyphMax);
          validGlyphs += 1;
        }
      }
    }

    if (validGlyphs > 0 && measuredMax <= VINYL_STICKER_OUTER_R + 0.35) {
      return measuredMax + pad;
    }

    /* textPath getExtentOfChar is unreliable in WebKit/Blink — outer ink hugs the path radius. */
    const ring = ringR != null ? ringR : VINYL_TITLE_RING_R;
    const dyOut = pathDy > 0 ? pathDy : 0;
    const dyIn = pathDy < 0 ? -pathDy : 0;
    const trackEm = vinylTitleParseLetterSpacingEm(textEl);
    const stretchOut = Math.max(0, trackEm) * fsPx * 0.05;
    return ring + pad + dyOut * 0.85 - dyIn * 0.35 + stretchOut + 0.08;
  }

  function buildVinylTitle() {
    const art = document.getElementById("btn-play");
    if (!art) return;

    let existing =
      art.querySelector(".vinyl-title") ||
      document.querySelector(".player-controls .vinyl-title") ||
      document.querySelector(".art-wrap .vinyl-title");
    if (existing) {
      repairVinylTitleClasses(existing);
      mountVinylTitleElement(existing);
      bindVinylTitleDom(existing);
      syncVinylPathForSkin();
      syncVinylTitleText();
      return;
    }

    ensureVinylSticker();

    const svgNS = "http://www.w3.org/2000/svg";
    const xlinkNS = "http://www.w3.org/1999/xlink";
    const svg = document.createElementNS(svgNS, "svg");
    svg.classList.add("vinyl-title");
    svg.setAttribute("viewBox", "0 0 100 100");
    svg.setAttribute("aria-hidden", "true");
    svg.setAttribute("focusable", "false");

    const defs = document.createElementNS(svgNS, "defs");

    const pathDeck = document.createElementNS(svgNS, "path");
    pathDeck.setAttribute("id", "vinyl-path-deck");
    pathDeck.setAttribute("d", vinylTitleRingPathD(VINYL_TITLE_RING_R));
    pathDeck.setAttribute("fill", "none");

    defs.append(pathDeck);

    const preset = getVinylTitlePlacementPreset();

    const mkText = (...classes) => {
      const text = document.createElementNS(svgNS, "text");
      text.classList.add("vinyl-title__text", ...classes);
      const textPath = document.createElementNS(svgNS, "textPath");
      textPath.setAttribute("href", "#vinyl-path-deck");
      textPath.setAttributeNS(xlinkNS, "xlink:href", "#vinyl-path-deck");
      textPath.setAttribute("startOffset", preset.startOffset);
      textPath.setAttribute("text-anchor", "middle");
      textPath.setAttribute("side", preset.side);
      textPath.setAttribute("dy", String(preset.dy));
      textPath.classList.add("vinyl-title__path");
      text.appendChild(textPath);
      return { text, textPath };
    };

    const a = mkText("vinyl-title__text--a", "is-active");
    const b = mkText("vinyl-title__text--b");

    svg.append(defs, a.text, b.text);
    mountVinylTitleElement(svg);

    bindVinylTitleDom(svg);
    repairVinylTitleClasses(svg);
    syncVinylPathForSkin();
    syncVinylTitleText();

    const source = document.getElementById("art-title-text");
    if (source) {
      new MutationObserver(syncVinylTitleText).observe(source, {
        childList: true,
        characterData: true,
        subtree: true,
      });
    }

    new MutationObserver(syncVinylPathForSkin).observe(root, {
      attributes: true,
      attributeFilter: ["data-skin"],
    });
  }

  function syncVinylPathForSkin() {
    if (!vinylSvg) return;
    const skin = root.getAttribute("data-skin") || DEFAULT_SKIN;
    /* Curved textPath is Deck-only; Cassette/Signal stay flat. */
    vinylSvg.hidden = skin !== "deck";
    if (skin === "deck") {
      ensureVinylSticker();
      syncVinylTitleRingPath();
    }
    if (vinylTextPath) {
      vinylTextPath.setAttribute("href", "#vinyl-path-deck");
      vinylTextPath.setAttributeNS("http://www.w3.org/1999/xlink", "xlink:href", "#vinyl-path-deck");
    }
    if (vinylTextPathB) {
      vinylTextPathB.setAttribute("href", "#vinyl-path-deck");
      vinylTextPathB.setAttributeNS("http://www.w3.org/1999/xlink", "xlink:href", "#vinyl-path-deck");
    }
  }

  function formatVinylRimText(cleaned) {
    return cleaned ? String(cleaned).trim() : "";
  }

  /**
   * Apply user scale after auto-fit base size (target = base × scale %).
   * Never uses textLength — font-size changes must be visible on the EXP slider.
   */
  function vinylTitleCommitScaledFit(el, tp, opts) {
    if (!el || !tp || !opts) return;
    vinylTitleClearInactiveLayer();
    const { bestSize, bestTrack, ringR, trackMin } = opts;
    const base = Number.isFinite(bestSize) && bestSize > 0 ? bestSize : VINYL_TITLE_FONT_MIN;
    const scale = vinylTitleScale / 100;
    const targetPx = Math.min(VINYL_TITLE_FONT_SEARCH_MAX, base * scale);
    const preset = getVinylTitlePlacementPreset();
    let ring = ringR != null ? ringR : VINYL_TITLE_RING_R;
    let track =
      bestTrack != null ? bestTrack : trackMin != null ? trackMin : VINYL_TITLE_TRACK_MIN;
    if (track > VINYL_TITLE_TRACK_OVERFLOW_MAX) track = VINYL_TITLE_TRACK_OVERFLOW_MAX;

    el.dataset.vinylFitBasePx = String(base);
    vinylTitleClearPathFill(el, tp);

    const applyAtSize = (sizePx) => {
      el.style.fontSize = `${sizePx}px`;
      el.style.letterSpacing = `${track}em`;
      vinylTitleClearPathFill(el, tp);
    };

    const fitsInk = () => vinylTitleMaxOuterRadius(el, ring) <= VINYL_TITLE_MAX_OUTER_R;

    let ringGuard = 0;
    while (ringGuard++ < 52) {
      syncVinylTitleRingPath(ring);
      VINYL_TITLE_RING_R = ring;
      let lo = VINYL_TITLE_FONT_MIN;
      let hi = targetPx;
      let best = lo;
      for (let i = 0; i < 52; i++) {
        const mid = (lo + hi) / 2;
        applyAtSize(mid);
        if (fitsInk()) {
          best = mid;
          lo = mid;
        } else {
          hi = mid;
        }
      }
      applyAtSize(best);
      if (fitsInk()) break;
      if (ring <= preset.ringRMin) break;
      ring = Math.max(preset.ringRMin, ring - 0.22);
    }
  }

  function fitVinylTitleFont(rawText, textEl, textPathEl) {
    const el = textEl || vinylTextEl;
    const tp = textPathEl || vinylTextPath;
    if (!el || !tp) return;
    if (el.classList.contains("is-active")) vinylTitleClearInactiveLayer();
    const path =
      (vinylSvg && vinylSvg.querySelector("#vinyl-path-deck")) ||
      document.getElementById("vinyl-path-deck");
    if (!path || typeof path.getTotalLength !== "function") {
      const preset = getVinylTitlePlacementPreset();
      tp.textContent = rawText;
      vinylTitleClearPathFill(el, tp);
      vinylTitleCommitScaledFit(el, tp, {
        bestSize: 18,
        bestTrack: VINYL_TITLE_TRACK_MAX,
        ringR: preset.ringRBase,
        trackMin: VINYL_TITLE_TRACK_MIN,
      });
      return;
    }

    const runFitOnText = (displayText) => {
      const preset = getVinylTitlePlacementPreset();
      tp.textContent = displayText;
      vinylTitleClearPathFill(el, tp);
      const trackMin = vinylTitleTrackMinForText(displayText);
      let ringR = preset.ringRBase;
      const applyRing = (r) => {
        ringR = r;
        syncVinylTitleRingPath(ringR);
      };
      applyRing(ringR);

      const arcSoftMax = () => vinylTitleArcSoftMax(path, preset);

      const fitsOuterInk = () =>
        vinylTitleMaxOuterRadius(el, ringR) <= VINYL_TITLE_MAX_OUTER_R;

      const textLengthPx = () => {
        try {
          return el.getComputedTextLength();
        } catch (err) {
          return 0;
        }
      };

      const fitsArcSoft = () => {
        const cap = arcSoftMax();
        if (!(cap > 0)) return true;
        return textLengthPx() <= cap * 1.02;
      };

      const tightenTrackingIfNeeded = () => {
        const cap = arcSoftMax();
        if (!(cap > 0) || textLengthPx() <= cap * 1.02) {
          el.style.letterSpacing = `${trackMin}em`;
          return trackMin;
        }
        const track = vinylTitleSpacingForPathLength(
          el,
          cap,
          trackMin,
          VINYL_TITLE_TRACK_OVERFLOW_MAX
        );
        el.style.letterSpacing = `${track}em`;
        return track;
      };

      const tryFontOnRing = (fontPx) => {
        vinylTitleClearPathFill(el, tp);
        el.style.fontSize = `${fontPx}px`;
        el.style.letterSpacing = `${trackMin}em`;
        if (!fitsOuterInk()) return { ok: false, inkOk: false, track: trackMin };
        let track = tightenTrackingIfNeeded();
        const inkOk = fitsOuterInk();
        const ok = inkOk && fitsArcSoft();
        return { ok, track, inkOk };
      };

      const maxFontForRim = (hiCap) => {
        let lo = VINYL_TITLE_FONT_MIN;
        let hi = hiCap;
        let best = lo;
        let bestTrack = trackMin;
        for (let i = 0; i < 44; i++) {
          const mid = (lo + hi) / 2;
          const trial = tryFontOnRing(mid);
          if (trial.ok) {
            best = mid;
            bestTrack = trial.track;
            lo = mid;
          } else if (trial.inkOk === false) {
            hi = mid;
          } else {
            hi = mid;
          }
        }
        return { best, bestTrack };
      };

      const runFitPass = () => {
        const hiCap = vinylTitleFontSearchHi(displayText, path);
        const fit = maxFontForRim(hiCap);
        let bestSize = fit.best;
        let bestTrack = fit.bestTrack;
        el.style.fontSize = `${bestSize}px`;
        el.style.letterSpacing = `${bestTrack}em`;
        vinylTitleClearPathFill(el, tp);

        const fitsRim = () => fitsOuterInk() && fitsArcSoft();

        let guard = 0;
        while (!fitsRim() && bestSize > VINYL_TITLE_FONT_MIN + 0.12 && guard++ < 96) {
          bestSize -= 0.25;
          el.style.fontSize = `${bestSize}px`;
          bestTrack = tightenTrackingIfNeeded();
        }

        return { bestSize, bestTrack, fitsRim };
      };

      let pass = runFitPass();
      let { bestSize, bestTrack, fitsRim } = pass;

      let ringGuard = 0;
      while (!fitsRim() && ringR > preset.ringRMin && ringGuard++ < 48) {
        applyRing(ringR - 0.22);
        pass = runFitPass();
        ({ bestSize, bestTrack, fitsRim } = pass);
      }

      let outwardGuard = 0;
      while (ringR < preset.ringRMax - 0.02 && outwardGuard++ < 24) {
        const prevRing = ringR;
        applyRing(ringR + 0.1);
        const tryPass = runFitPass();
        if (tryPass.fitsRim() && tryPass.bestSize >= bestSize - 0.12) {
          bestSize = tryPass.bestSize;
          bestTrack = tryPass.bestTrack;
          fitsRim = tryPass.fitsRim;
        } else {
          applyRing(prevRing);
          el.style.fontSize = `${bestSize}px`;
          el.style.letterSpacing = `${bestTrack}em`;
          break;
        }
      }

      return { bestSize, bestTrack, fitsRim, ringR, trackMin };
    };

    let fit = runFitOnText(rawText);
    if (!fit.fitsRim()) {
      let text = String(rawText || "");
      while (text.length > 6 && !fit.fitsRim()) {
        text = text.slice(0, -2);
        fit = runFitOnText(`${text.trimEnd()}…`);
      }
    }

    vinylTitleCommitScaledFit(el, tp, {
      bestSize: fit.bestSize,
      bestTrack: fit.bestTrack,
      ringR: fit.ringR,
      trackMin: fit.trackMin,
    });
  }

  function titleFadeMs() {
    const raw = getComputedStyle(root).getPropertyValue("--title-fade-ms").trim();
    const n = parseFloat(raw);
    return Number.isFinite(n) ? n : 480;
  }

  function syncVinylTitleText() {
    if (!vinylSvg) buildVinylTitle();
    if (!vinylTextPath || !vinylTextPathB) {
      bindVinylTitleDom(vinylSvg);
    }
    if (!vinylTextPath || !vinylTextPathB) return;
    let title = "";
    const source = document.getElementById("art-title-text");
    title = (source && source.textContent) || "";
    if (!title) {
      const api = window.TypeBeatRadio;
      if (api && typeof api.getDisplayTitle === "function") {
        title = api.getDisplayTitle() || "";
      }
    }
    const cleaned = String(title).trim();
    const rim = formatVinylRimText(cleaned).toUpperCase();
    if (vinylSvg) {
      vinylSvg.classList.toggle("is-empty", !cleaned);
      if (cleaned) vinylSvg.hidden = false;
    }
    if (rim === lastVinylTitle) {
      if (cleaned && vinylTextEl && vinylTextElB) {
        const active = vinylTextEl.classList.contains("is-active") ? vinylTextEl : vinylTextElB;
        const activePath = active === vinylTextEl ? vinylTextPath : vinylTextPathB;
        if (activePath && activePath.textContent !== rim) {
          activePath.textContent = rim;
          fitVinylTitleFont(rim, active, activePath);
        }
      }
      return;
    }
    const prev = lastVinylTitle;
    lastVinylTitle = rim;

    const nextPath = vinylTitleFlip ? vinylTextPath : vinylTextPathB;
    const nextEl = vinylTitleFlip ? vinylTextEl : vinylTextElB;
    const prevPath = vinylTitleFlip ? vinylTextPathB : vinylTextPath;
    const prevEl = vinylTitleFlip ? vinylTextElB : vinylTextEl;

    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const useTick =
      titleXfadeMode === "tick" && prev && rim && !reduce && typeof scrambleTickText === "function";

    const commitVinylTitle = () => {
      if (!nextPath || !nextEl) return;
      nextPath.textContent = rim;
      fitVinylTitleFont(rim, nextEl, nextPath);
      if (prevEl) prevEl.classList.remove("is-active");
      nextEl.classList.add("is-active");
      vinylTitleFlip = !vinylTitleFlip;
      if (prevPath) {
        prevPath.textContent = "";
        vinylTitleClearPathFill(prevEl, prevPath);
      }
      if (prevEl) {
        prevEl.style.fontSize = "";
        prevEl.style.letterSpacing = "";
      }
      if (vinylSvg) {
        vinylSvg.classList.remove("is-empty");
        vinylSvg.hidden = false;
      }
    };

    if (vinylTitleAnim) cancelAnimationFrame(vinylTitleAnim);
    if (vinylTitleTickTimer) {
      window.clearTimeout(vinylTitleTickTimer);
      vinylTitleTickTimer = 0;
    }

    if (!useTick) {
      commitVinylTitle();
      return;
    }

    prevEl.classList.remove("is-active");
    nextEl.classList.add("is-active", "is-entering");
    const steps = 16;
    let step = 0;
    const tickMs = Math.max(16, Math.round((titleFadeMs() * 0.42) / steps));
    const runTick = () => {
      step += 1;
      const p = step / steps;
      const partial = p >= 1 ? rim : scrambleTickText(rim, p);
      nextPath.textContent = partial;
      fitVinylTitleFont(partial, nextEl, nextPath);
      if (step < steps) {
        vinylTitleTickTimer = window.setTimeout(runTick, tickMs);
      } else {
        vinylTitleTickTimer = 0;
        nextEl.classList.remove("is-entering");
        commitVinylTitle();
      }
    };
    nextPath.textContent = scrambleTickText(rim, 0);
    fitVinylTitleFont(scrambleTickText(rim, 0), nextEl, nextPath);
    vinylTitleTickTimer = window.setTimeout(runTick, tickMs);
  }


  let asTapeObserversBound = false;

  function buildAsTapeShellHtml() {
    return (
      '<div class="as-tape-chrome__tray">' +
      '<img class="as-tape-chrome__empty" src="' + AS_TAPE_ASSET + 'empty.png" alt="" decoding="async" />' +
      '<div class="as-tape-chrome__tape">' +
      '<img class="as-tape-chrome__reel as-tape-chrome__reel--l" src="' + AS_TAPE_ASSET + 'reel.png" alt="" decoding="async" />' +
      '<img class="as-tape-chrome__reel as-tape-chrome__reel--r" src="' + AS_TAPE_ASSET + 'reel.png" alt="" decoding="async" />' +
      '<img class="as-tape-chrome__cover" alt="" decoding="async" hidden />' +
      '<div class="as-tape-chrome__window" aria-hidden="true"></div>' +
      '<img class="as-tape-chrome__frame" src="' + AS_TAPE_FRAME + '" alt="" decoding="async" />' +
      '<img class="as-tape-chrome__sprocket as-tape-chrome__sprocket--l" src="' + AS_TAPE_ASSET + 'sprocket.png" alt="" decoding="async" />' +
      '<img class="as-tape-chrome__sprocket as-tape-chrome__sprocket--r" src="' + AS_TAPE_ASSET + 'sprocket.png" alt="" decoding="async" />' +
      '<span class="as-tape-chrome__label-slot">' +
      '<span class="as-tape-chrome__label-text as-tape-chrome__label-text--a is-active"></span>' +
      '<span class="as-tape-chrome__label-text as-tape-chrome__label-text--b"></span>' +
      "</span>" +
      "</div>" +
      "</div>"
    );
  }

  /* --- AS Tape shell (andrewstephens75/as-tape-player) --- */
  function ensureAsTapeChrome() {
    const art = document.getElementById("btn-play");
    if (!art) return;

    let chrome = art.querySelector(".as-tape-chrome");
    const needsRebuild =
      chrome &&
      (!chrome.querySelector(".as-tape-chrome__cover") ||
        chrome.querySelector(".as-tape-chrome__window-glass") ||
        !chrome.querySelector(".as-tape-chrome__window") ||
        !chrome.querySelector(".as-tape-chrome__label-text--a") ||
        !chrome.querySelector(".as-tape-chrome__label-slot") ||
        chrome.querySelector(".as-tape-chrome__fluff") ||
        chrome.querySelector(".as-tape-chrome__body"));
    if (!chrome || needsRebuild) {
      if (chrome) chrome.remove();
      chrome = document.createElement("div");
      chrome.className = "as-tape-chrome";
      chrome.setAttribute("aria-hidden", "true");
      chrome.innerHTML = buildAsTapeShellHtml();
      const glyph = art.querySelector(".art__play-glyph");
      if (glyph) art.insertBefore(chrome, glyph);
      else art.appendChild(chrome);
    }

    asTapeLabelEl = chrome.querySelector(".as-tape-chrome__label-text--a");
    if (!asTapeLabelEl) {
      asTapeLabelEl = chrome.querySelector(".as-tape-chrome__label-text");
    }
    asTapeFrameEl = chrome.querySelector(".as-tape-chrome__frame");
    asTapeCoverEl = chrome.querySelector(".as-tape-chrome__cover");
    syncTapeFrameAsset();
    syncTapeLabels();
    syncAsTapeCover();
    bindTapeLabelFit();
    fitTapeLabels();

    if (!asTapeObserversBound) {
      asTapeObserversBound = true;
      const source = document.getElementById("art-title-text");
      if (source) {
        new MutationObserver(syncTapeLabels).observe(source, {
          childList: true,
          characterData: true,
          subtree: true,
        });
      }

      ["art-a", "art-b"].forEach((id) => {
        const img = document.getElementById(id);
        if (!img) return;
        new MutationObserver(syncAsTapeCover).observe(img, {
          attributes: true,
          attributeFilter: ["src", "class"],
        });
      });

      new MutationObserver(() => {
        if (current === "tape") ensureAsTapeChrome();
      }).observe(art, { childList: true });

      new MutationObserver(() => {
        if (root.getAttribute("data-skin") === "tape") ensureAsTapeChrome();
      }).observe(root, { attributes: true, attributeFilter: ["data-skin"] });

      document.documentElement.addEventListener("tb:art-update", () => {
        if (current === "tape") {
          ensureAsTapeChrome();
          syncAsTapeCover();
        }
      });
    }
  }

  function activeArtSrc() {
    const a = document.getElementById("art-a");
    const b = document.getElementById("art-b");
    const active = (a && a.classList.contains("is-active") && a) || (b && b.classList.contains("is-active") && b);
    const src = active && active.getAttribute("src");
    return src && src.trim() ? src.trim() : "";
  }

  function syncAsTapeCover() {
    if (!asTapeFrameEl) {
      asTapeFrameEl = document.querySelector(".as-tape-chrome__frame");
    }
    if (!asTapeCoverEl) {
      asTapeCoverEl = document.querySelector(".as-tape-chrome__cover");
    }
    if (asTapeFrameEl && !asTapeFrameEl.src.includes("cassette.png")) {
      asTapeFrameEl.src = AS_TAPE_FRAME;
    }
    if (!asTapeCoverEl) return;
    const cover = activeArtSrc();
    if (cover) {
      asTapeCoverEl.src = cover;
      asTapeCoverEl.hidden = false;
    } else {
      asTapeCoverEl.removeAttribute("src");
      asTapeCoverEl.hidden = true;
    }
  }

  function getDisplayTitleText() {
    /* Prefer live DOM (updated immediately on Next) over queue index. */
    const source = document.getElementById("art-title-text");
    const dom = String((source && source.textContent) || "").trim();
    if (dom) return dom;
    const api = window.TypeBeatRadio;
    if (api && typeof api.getDisplayTitle === "function") {
      return String(api.getDisplayTitle() || "").trim();
    }
    return "";
  }

  function syncTapeLabels() {
    const title = getDisplayTitleText();
    const display = title || "Side A";
    const chrome =
      document.querySelector(".as-tape-chrome__label-slot") ||
      document.querySelector(".as-tape-chrome__tape") ||
      document.querySelector(".as-tape-chrome");
    let labelA = document.querySelector(".as-tape-chrome__label-text--a");
    let labelB = document.querySelector(".as-tape-chrome__label-text--b");
    if (!labelA) {
      asTapeLabelEl = document.querySelector(".as-tape-chrome__label-text");
      if (asTapeLabelEl) {
        asTapeLabelEl.textContent = display;
      }
      syncAsTapeCover();
      fitTapeLabels();
      return;
    }
    if (!labelB) {
      labelB = document.createElement("span");
      labelB.className = "as-tape-chrome__label-text as-tape-chrome__label-text--b";
      labelA.parentNode.appendChild(labelB);
    }
    asTapeLabelEl = labelA;

    if (display === lastTapeTitle) {
      syncAsTapeCover();
      fitTapeLabels();
      return;
    }
    const prev = lastTapeTitle;
    lastTapeTitle = display;

    const activeIsA = labelA.classList.contains("is-active");
    const next = activeIsA ? labelB : labelA;
    const prevEl = activeIsA ? labelA : labelB;

    if (titleXfadeMode !== "fade" && prev && display) {
      runTapeAltTitleTransition(prevEl, next, prev, display);
      syncAsTapeCover();
      return;
    }

    next.textContent = display;
    prevEl.classList.remove("is-active");
    next.classList.add("is-active");
    syncAsTapeCover();
    fitTapeLabels();
  }

  const TAPE_LABEL_FIT_MIN = 0.22;

  function fitTapeLabelEl(el) {
    if (!(el instanceof HTMLElement)) return;
    if (root.getAttribute("data-skin") !== "tape") return;
    const text = (el.textContent || "").replace(/\s+/g, " ").trim();
    el.style.setProperty("--tape-label-fit", "1");
    if (!text) return;
    const slot = el.closest(".as-tape-chrome__label-slot");
    if (!slot) return;

    const fitToSlot = () => {
      const maxW = slot.clientWidth;
      const maxH = slot.clientHeight;
      if (maxW <= 0 || maxH <= 0) return false;
      const cs = getComputedStyle(el);
      const padX =
        (parseFloat(cs.paddingLeft) || 0) + (parseFloat(cs.paddingRight) || 0);
      const budgetW = Math.max(8, maxW - padX - 4);
      const budgetH = maxH * 0.94;
      let lo = TAPE_LABEL_FIT_MIN;
      let hi = 1;
      let best = lo;
      for (let i = 0; i < 14; i += 1) {
        const fit = (lo + hi) / 2;
        el.style.setProperty("--tape-label-fit", String(fit));
        const sizePx = parseFloat(getComputedStyle(el).fontSize) || 12;
        const w = measureChipTextWidth(text, sizePx, el);
        const lineH = sizePx * (parseFloat(cs.lineHeight) || 1.05);
        if (w <= budgetW && lineH <= budgetH) {
          best = fit;
          lo = fit;
        } else {
          hi = fit;
        }
      }
      el.style.setProperty("--tape-label-fit", String(Number(best.toFixed(3))));
      return true;
    };
    if (!fitToSlot()) {
      requestAnimationFrame(() => fitTapeLabelEl(el));
    }
  }

  function fitTapeLabels() {
    document
      .querySelectorAll(".as-tape-chrome__label-text.is-active")
      .forEach((el) => fitTapeLabelEl(el));
  }

  let tapeLabelFitRo = null;

  function bindTapeLabelFit() {
    if (tapeLabelFitRo || typeof ResizeObserver === "undefined") return;
    tapeLabelFitRo = new ResizeObserver(() => fitTapeLabels());
    const slot = document.querySelector(".as-tape-chrome__label-slot");
    if (slot) tapeLabelFitRo.observe(slot);
  }

  /* --- Experimental panel --- */
  let fab = null;
  let panel = null;
  let skinChipsEl = null;
  let prolificChip = null;
  let ageChipsEl = null;
  let shapeChipsEl = null;
  let glassChipsEl = null;
  let xfadeModeSelect = null;
  let xfadePreloadSelect = null;
  let xfadeHandoffChipsEl = null;
  let xfadeOverlapChipsEl = null;
  let xfadeStartSelect = null;
  let titleXfadeSelect = null;
  let vinylTitleScaleSec = null;
  let vinylTitlePlacementSec = null;
  let vinylTitlePlacementChipsEl = null;
  let vinylTitleScaleInput = null;
  let vinylTitleScaleReadout = null;

  /** @type {{ mode: string, preload: string, handoffGate: string, overlapMin: string, startAt: string, debug: boolean }} */
  let xfadeSettings = {
    mode: "graph7",
    preload: "aggressive",
    handoffGate: "allow_buffer_wait",
    overlapMin: "auto",
    startAt: "0",
    debug: false,
  };

  function syncSkinChips() {
    if (!skinChipsEl) return;
    skinChipsEl.querySelectorAll(".exp-chip").forEach((btn) => {
      const on = (btn.dataset.skin || "") === current;
      btn.classList.toggle("is-active", on);
      btn.setAttribute("aria-pressed", on ? "true" : "false");
    });
  }

  function syncProlificChip() {
    if (!prolificChip) return;
    const on = prolificOn;
    prolificChip.classList.toggle("is-active", on);
    prolificChip.setAttribute("aria-checked", on ? "true" : "false");
    const input = prolificChip.querySelector('input[type="checkbox"]');
    if (input) input.checked = on;
  }

  function syncAgeChips() {
    if (!ageChipsEl) return;
    const n = AGE_OPTIONS.length;
    const idx = Math.max(
      0,
      AGE_OPTIONS.findIndex((o) => o.months === maxAgeMonths)
    );
    const input = ageChipsEl.querySelector(".views-slider__input");
    if (input) {
      input.value = String(idx);
      input.setAttribute("aria-valuenow", String(idx));
      const opt = AGE_OPTIONS[idx];
      input.setAttribute(
        "aria-valuetext",
        opt ? `Track age ${opt.label}` : "Track age"
      );
    }
    ageChipsEl.querySelectorAll(".views-slider__tick").forEach((tick, i) => {
      tick.classList.toggle("is-active", i === idx);
    });
    ageChipsEl.querySelectorAll(".views-slider__label").forEach((lab, i) => {
      lab.classList.toggle("is-active", i === idx);
    });
    ageChipsEl.style.setProperty("--views-n", String(n));
  }

  function syncShapeChips() {
    /* no-op — Shape Exp section removed */
  }

  function syncGlassChips() {
    if (!glassChipsEl) return;
    glassChipsEl.querySelectorAll(".exp-chip").forEach((btn) => {
      const on = (btn.dataset.glass || "") === glassMode;
      btn.classList.toggle("is-active", on);
      btn.setAttribute("aria-pressed", on ? "true" : "false");
    });
  }

  function pullXfadeFromRadio() {
    const api = window.TypeBeatRadio;
    if (api && typeof api.getCrossfadeSettings === "function") {
      const s = api.getCrossfadeSettings();
      xfadeSettings = {
        mode: s.mode || "graph7",
        preload: s.preload || "aggressive",
        handoffGate: s.handoffGate || "allow_buffer_wait",
        overlapMin: s.overlapMin || "auto",
        startAt: s.startAt || "0",
        debug: false,
      };
    }
  }

  function pushXfadeToRadio() {
    const api = window.TypeBeatRadio;
    if (api && typeof api.applyCrossfadeSettings === "function") {
      api.applyCrossfadeSettings(xfadeSettings);
    }
  }

  function setXfadeMode(id) {
    xfadeSettings.mode = id;
    if (xfadeModeSelect) xfadeModeSelect.value = id;
    pushXfadeToRadio();
  }

  function setXfadePreload(id) {
    xfadeSettings.preload = id;
    if (xfadePreloadSelect) xfadePreloadSelect.value = id;
    pushXfadeToRadio();
  }

  function setXfadeHandoff(id) {
    xfadeSettings.handoffGate = id;
    syncXfadeHandoffChips();
    pushXfadeToRadio();
  }

  function setXfadeOverlap(id) {
    xfadeSettings.overlapMin = id;
    syncXfadeOverlapChips();
    pushXfadeToRadio();
  }

  function setXfadeStart(id) {
    xfadeSettings.startAt = id;
    if (xfadeStartSelect) xfadeStartSelect.value = id;
    pushXfadeToRadio();
  }

  function syncXfadeModeSelect() {
    if (!xfadeModeSelect) return;
    xfadeModeSelect.value = xfadeSettings.mode;
  }

  function syncXfadePreloadSelect() {
    if (!xfadePreloadSelect) return;
    xfadePreloadSelect.value = xfadeSettings.preload;
  }

  function syncXfadeHandoffChips() {
    if (!xfadeHandoffChipsEl) return;
    xfadeHandoffChipsEl.querySelectorAll(".exp-chip").forEach((btn) => {
      const on = (btn.dataset.xfadeHandoff || "") === xfadeSettings.handoffGate;
      btn.classList.toggle("is-active", on);
      btn.setAttribute("aria-pressed", on ? "true" : "false");
    });
  }

  function syncXfadeOverlapChips() {
    if (!xfadeOverlapChipsEl) return;
    xfadeOverlapChipsEl.querySelectorAll(".exp-chip").forEach((btn) => {
      const on = (btn.dataset.xfadeOverlap || "") === xfadeSettings.overlapMin;
      btn.classList.toggle("is-active", on);
      btn.setAttribute("aria-pressed", on ? "true" : "false");
    });
  }

  function syncXfadeStartSelect() {
    if (!xfadeStartSelect) return;
    xfadeStartSelect.value = xfadeSettings.startAt;
  }

  function syncXfadeControls() {
    syncXfadeModeSelect();
    syncXfadePreloadSelect();
    syncXfadeHandoffChips();
    syncXfadeOverlapChips();
    syncXfadeStartSelect();
  }

  function buildExpSelect(options, { ariaLabel, value, onChange } = {}) {
    const sel = document.createElement("select");
    sel.className = "exp-select";
    sel.setAttribute("aria-label", ariaLabel || "");
    options.forEach((opt) => {
      const o = document.createElement("option");
      o.value = opt.id;
      o.textContent = opt.label;
      if (opt.tip) o.dataset.tip = opt.tip;
      sel.appendChild(o);
    });
    sel.value = value;
    sel.addEventListener("change", () => onChange(sel.value));
    return sel;
  }

  function setPanelOpen(open) {
    panelOpen = Boolean(open);
    if (panel) panel.classList.toggle("is-open", panelOpen);
    if (fab) fab.setAttribute("aria-expanded", panelOpen ? "true" : "false");
    const rail = document.querySelector(".chrome-rail--right") || document.querySelector(".chrome-rail");
    if (rail) rail.classList.toggle("is-exp-open", panelOpen);
    root.classList.toggle("is-exp-open", panelOpen);
    root.setAttribute("data-exp-fold", panelOpen ? "off" : "on");
    store(STORAGE_EXP_FOLD, panelOpen ? null : "1");
  }

  function buildFilterRailExtras() {
    const left = document.getElementById("filter-rail");
    if (!left || left.dataset.filterExtras === "1") return;
    left.dataset.filterExtras = "1";

    const viewsBlock = left.querySelector(".filter-block--views");

    /* Track age — range slider under Views (same pattern as Views). */
    const ageBlock = document.createElement("div");
    ageBlock.className = "filter-block filter-block--age";
    const ageLabel = document.createElement("span");
    ageLabel.className = "filter-block__label";
    ageLabel.textContent = "Track age";
    ageChipsEl = document.createElement("div");
    ageChipsEl.className = "filter-chips filter-chips--age";
    ageChipsEl.setAttribute("role", "group");
    ageChipsEl.setAttribute("aria-label", "Max track age");
    const ageN = AGE_OPTIONS.length;
    const ageIdx = Math.max(
      0,
      AGE_OPTIONS.findIndex((o) => o.months === maxAgeMonths)
    );
    ageChipsEl.innerHTML = `<div class="views-slider age-slider" role="group" aria-label="Track age" style="--views-n:${ageN}">
      <input type="range" class="views-slider__input" id="age-tier-slider" min="0" max="${
        ageN - 1
      }" step="1" value="${ageIdx}" aria-valuemin="0" aria-valuemax="${
      ageN - 1
    }" aria-valuenow="${ageIdx}" aria-valuetext="Track age ${
      (AGE_OPTIONS[ageIdx] && AGE_OPTIONS[ageIdx].label) || "All"
    }" />
      <div class="views-slider__track" aria-hidden="true">
        ${AGE_OPTIONS.map(
          (o, i) =>
            `<span class="views-slider__tick${i === ageIdx ? " is-active" : ""}" data-age="${
              o.months == null ? "all" : o.months
            }"></span>`
        ).join("")}
      </div>
      <div class="views-slider__labels" aria-hidden="true">
        ${AGE_OPTIONS.map(
          (o, i) =>
            `<span class="views-slider__label${i === ageIdx ? " is-active" : ""}">${ageTierLabelMarkup(
              o.label
            )}</span>`
        ).join("")}
      </div>
    </div>`;
    const ageInput = ageChipsEl.querySelector("#age-tier-slider");
    if (ageInput) {
      ageInput.addEventListener("input", () => {
        const i = Number(ageInput.value);
        const opt = AGE_OPTIONS[i];
        if (!opt) return;
        setAge(opt.months);
      });
    }
    ageBlock.append(ageLabel, ageChipsEl);

    /* Prolific — checkbox (same visual language as pads, not a chip). */
    const prolBlock = document.createElement("div");
    prolBlock.className = "filter-block filter-block--prolific";
    const prolLabel = document.createElement("span");
    prolLabel.className = "filter-block__label";
    prolLabel.textContent = "Prolific";
    const prolRow = document.createElement("div");
    prolRow.className = "filter-chips filter-chips--prolific";
    prolificChip = document.createElement("button");
    prolificChip.type = "button";
    prolificChip.className = "filter-check";
    prolificChip.setAttribute("role", "checkbox");
    prolificChip.setAttribute("aria-checked", "false");
    prolificChip.dataset.tip = "Channels with ≥22 tracks in activity window";
    prolificChip.innerHTML =
      '<span class="filter-check__box" aria-hidden="true"></span>' +
      '<span class="filter-check__text">Prolific only</span>' +
      '<input type="checkbox" class="filter-check__input" tabindex="-1" aria-hidden="true" />';
    prolificChip.addEventListener("click", () => setProlific(!prolificOn));
    prolRow.appendChild(prolificChip);
    prolBlock.append(prolLabel, prolRow);

    if (viewsBlock) {
      viewsBlock.after(ageBlock);
    } else {
      left.prepend(ageBlock);
    }
    left.appendChild(prolBlock);

    syncProlificChip();
    syncAgeChips();
  }

  function buildExpPanel() {
    const existingPanel = document.querySelector(".exp-panel");
    if (existingPanel) {
      existingPanel.classList.add("glass", "glass--panel", "glass--art-match");
      return;
    }
    const mount = document.getElementById("exp-dock") || document.body;
    if (!mount) return;

    fab = document.createElement("button");
    fab.type = "button";
    fab.className = "exp-fab";
    fab.id = "exp-fab";
    fab.setAttribute("aria-expanded", "false");
    fab.setAttribute("aria-controls", "exp-panel");
    fab.setAttribute(
      "aria-label",
      "Experimental controls — skins, crossfade"
    );
    fab.dataset.tip = "EXP — visual experiments (Shift+E)";
    fab.textContent = "EXP";
    fab.addEventListener("click", (event) => {
      event.stopPropagation();
      setPanelOpen(!panelOpen);
    });

    panel = document.createElement("div");
    panel.className = "exp-panel glass glass--panel glass--art-match";
    panel.id = "exp-panel";
    panel.setAttribute("role", "region");
    panel.setAttribute("aria-label", "Experimental controls");

    const title = document.createElement("p");
    title.className = "exp-panel__title";
    title.textContent = "Experimental";

    /* Skin */
    const skinSec = document.createElement("div");
    skinSec.className = "exp-section";
    const skinLabel = document.createElement("span");
    skinLabel.className = "exp-section__label";
    skinLabel.textContent = "Skin";
    skinChipsEl = document.createElement("div");
    skinChipsEl.className = "exp-chips";
    skinChipsEl.setAttribute("role", "group");
    skinChipsEl.setAttribute("aria-label", "Skin");
    SKINS.forEach((s) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "exp-chip";
      btn.dataset.skin = s.id;
      btn.dataset.tip = s.tip;
      btn.textContent = s.label;
      btn.setAttribute("aria-pressed", "false");
      btn.addEventListener("click", () => applySkin(s.id));
      skinChipsEl.appendChild(btn);
    });
    skinSec.append(skinLabel, skinChipsEl);

    /* Crossfade experiments — Duration exposes 3s / 7s clearly */
    const xfadeSec = document.createElement("div");
    xfadeSec.className = "exp-section exp-section--xfade";
    const xfadeLabel = document.createElement("span");
    xfadeLabel.className = "exp-section__label";
    xfadeLabel.textContent = "Crossfade";

    const xfadeModeRow = document.createElement("div");
    xfadeModeRow.className = "exp-field";
    const xfadeModeLbl = document.createElement("span");
    xfadeModeLbl.className = "exp-field__label";
    xfadeModeLbl.textContent = "Duration";
    xfadeModeSelect = buildExpSelect(XFADE_MODE_OPTIONS, {
      ariaLabel: "Crossfade duration",
      value: xfadeSettings.mode,
      onChange: setXfadeMode,
    });
    xfadeModeSelect.dataset.tip = "3s or 7s overlap — applies on next skip";
    xfadeModeRow.append(xfadeModeLbl, xfadeModeSelect);

    const xfadePreloadRow = document.createElement("div");
    xfadePreloadRow.className = "exp-field";
    const xfadePreloadLbl = document.createElement("span");
    xfadePreloadLbl.className = "exp-field__label";
    xfadePreloadLbl.textContent = "Preload";
    xfadePreloadSelect = buildExpSelect(XFADE_PRELOAD_OPTIONS, {
      ariaLabel: "Preload strategy",
      value: xfadeSettings.preload,
      onChange: setXfadePreload,
    });
    xfadePreloadSelect.dataset.tip = "Aggressive = smoothest Next";
    xfadePreloadRow.append(xfadePreloadLbl, xfadePreloadSelect);

    /* Handoff gate stays in JS (default allow_buffer_wait) — not rendered. */

    const xfadeOverlapLbl = document.createElement("span");
    xfadeOverlapLbl.className = "exp-section__label exp-section__label--sub";
    xfadeOverlapLbl.textContent = "Overlap";
    xfadeOverlapChipsEl = document.createElement("div");
    xfadeOverlapChipsEl.className = "exp-chips";
    xfadeOverlapChipsEl.setAttribute("role", "group");
    xfadeOverlapChipsEl.setAttribute("aria-label", "Overlap duration override");
    XFADE_OVERLAP_OPTIONS.forEach((opt) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "exp-chip exp-chip--compact";
      btn.dataset.xfadeOverlap = opt.id;
      btn.dataset.tip = opt.tip;
      btn.textContent = opt.label;
      btn.setAttribute("aria-pressed", "false");
      btn.addEventListener("click", () => setXfadeOverlap(opt.id));
      xfadeOverlapChipsEl.appendChild(btn);
    });

    const xfadeStartRow = document.createElement("div");
    xfadeStartRow.className = "exp-field";
    const xfadeStartLbl = document.createElement("span");
    xfadeStartLbl.className = "exp-field__label";
    xfadeStartLbl.textContent = "Start at";
    xfadeStartSelect = buildExpSelect(XFADE_START_OPTIONS, {
      id: "exp-xfade-start",
      value: xfadeSettings.startAt,
      onChange: setXfadeStart,
    });
    xfadeStartSelect.dataset.tip = "Seek incoming track on handoff (skip intro / buffer headroom)";
    xfadeStartRow.append(xfadeStartLbl, xfadeStartSelect);

    xfadeSec.append(
      xfadeLabel,
      xfadeModeRow,
      xfadePreloadRow,
      xfadeOverlapLbl,
      xfadeOverlapChipsEl,
      xfadeStartRow
    );

    /* Title transition Exp: Fade + tape alt modes (no canvas sponge). */
    const titleSec = document.createElement("div");
    titleSec.className = "exp-section";
    const titleSecLbl = document.createElement("span");
    titleSecLbl.className = "exp-section__label";
    titleSecLbl.textContent = "Title transition";
    const titleRow = document.createElement("div");
    titleRow.className = "exp-field";
    const titleFieldLbl = document.createElement("span");
    titleFieldLbl.className = "exp-field__label";
    titleFieldLbl.textContent = "Mode";
    titleXfadeSelect = buildExpSelect(
      [
        { id: "fade", label: "Fade", tip: "Crossfade between two label layers (default)" },
        { id: "wipe", label: "Wipe horizontal", tip: "Tape: clip old title left→right, new title underneath" },
        { id: "blur", label: "Blur swap", tip: "Tape: blur out old, blur in new — one slot" },
        { id: "tick", label: "Type tick", tip: "Tape: scramble-resolve into new title" },
      ],
      {
        ariaLabel: "Title transition mode",
        value: titleXfadeMode,
        onChange: setTitleXfadeMode,
      }
    );
    titleXfadeSelect.dataset.tip = "Fade on vinyl · Wipe / Blur / Tick on tape label";
    titleRow.append(titleFieldLbl, titleXfadeSelect);
    titleSec.append(titleSecLbl, titleRow);

    vinylTitlePlacementSec = document.createElement("div");
    vinylTitlePlacementSec.className = "exp-section exp-section--vinyl-placement";
    const vinylPlaceLbl = document.createElement("span");
    vinylPlaceLbl.className = "exp-section__label";
    vinylPlaceLbl.textContent = "Vinyl title placement";
    vinylTitlePlacementChipsEl = document.createElement("div");
    vinylTitlePlacementChipsEl.className = "exp-chips";
    vinylTitlePlacementChipsEl.setAttribute("role", "group");
    vinylTitlePlacementChipsEl.setAttribute("aria-label", "Vinyl title placement");
    VINYL_TITLE_PLACEMENT_OPTIONS.forEach((opt) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "exp-chip";
      btn.dataset.vinylTitlePlacement = opt.id;
      btn.dataset.tip = opt.tip;
      btn.textContent = opt.label;
      btn.setAttribute("aria-pressed", "false");
      btn.addEventListener("click", () => setVinylTitlePlacement(opt.id));
      vinylTitlePlacementChipsEl.appendChild(btn);
    });
    vinylTitlePlacementSec.append(vinylPlaceLbl, vinylTitlePlacementChipsEl);

    vinylTitleScaleSec = document.createElement("div");
    vinylTitleScaleSec.className = "exp-section exp-section--vinyl-scale";
    const vinylScaleLbl = document.createElement("span");
    vinylScaleLbl.className = "exp-section__label";
    vinylScaleLbl.textContent = "Vinyl title size";
    const vinylScaleField = document.createElement("div");
    vinylScaleField.className = "exp-field";
    const vinylScaleFieldLbl = document.createElement("span");
    vinylScaleFieldLbl.className = "exp-field__label";
    vinylScaleFieldLbl.textContent = "Sticker title scale";
    const vinylScaleRow = document.createElement("div");
    vinylScaleRow.className = "exp-scale-row";
    vinylTitleScaleInput = document.createElement("input");
    vinylTitleScaleInput.type = "range";
    vinylTitleScaleInput.className = "exp-scale-row__input";
    vinylTitleScaleInput.id = "exp-vinyl-title-scale";
    vinylTitleScaleInput.min = String(VINYL_TITLE_SCALE_MIN);
    vinylTitleScaleInput.max = String(VINYL_TITLE_SCALE_MAX);
    vinylTitleScaleInput.step = "1";
    vinylTitleScaleInput.value = String(vinylTitleScale);
    vinylTitleScaleInput.setAttribute(
      "aria-label",
      "Vinyl sticker title scale percent"
    );
    vinylTitleScaleInput.dataset.tip = "Scales rim title after auto-fit (50–400%)";
    vinylTitleScaleReadout = document.createElement("span");
    vinylTitleScaleReadout.className = "exp-scale-row__value";
    vinylTitleScaleReadout.setAttribute("aria-live", "polite");
    vinylTitleScaleReadout.textContent = `${vinylTitleScale}%`;
    vinylTitleScaleInput.addEventListener("input", () => {
      setVinylTitleScale(vinylTitleScaleInput.value);
    });
    vinylScaleRow.append(vinylTitleScaleInput, vinylTitleScaleReadout);
    const vinylScaleHint = document.createElement("p");
    vinylScaleHint.className = "exp-hint exp-hint--sub";
    vinylScaleHint.textContent =
      "Bigger titles for short names; natural spacing (no full-ring stretch). 50–400%.";
    vinylScaleField.append(vinylScaleFieldLbl, vinylScaleRow);
    vinylTitleScaleSec.append(vinylScaleLbl, vinylScaleField, vinylScaleHint);

    const hint = document.createElement("p");
    hint.className = "exp-hint";
    hint.textContent =
      "CDJ chips · Views+Age sliders · Meter · Glass · Shift+S skin · Shift+E Exp";

    panel.append(title, skinSec, xfadeSec, titleSec, vinylTitlePlacementSec, vinylTitleScaleSec, hint);
    mount.append(panel, fab);

    syncSkinChips();
    syncProlificChip();
    syncAgeChips();
    syncVinylTitleScaleControls();
    syncVinylTitlePlacementChips();
    syncVinylTitleScaleSection();
    pullXfadeFromRadio();
    syncXfadeControls();
    setPanelOpen(panelOpen);
    wireCompressStepButtons();
    /* radio.js may load after this; push once API is ready. */
    pushFiltersToRadio();
    pushXfadeToRadio();
    notifyArtTitle();
    let tries = 0;
    const waitApi = window.setInterval(() => {
      tries += 1;
      pushFiltersToRadio();
      pullXfadeFromRadio();
      syncXfadeControls();
      pushXfadeToRadio();
      notifyArtTitle();
      if (window.TypeBeatRadio && typeof window.TypeBeatRadio.syncCompressUI === "function") {
        window.TypeBeatRadio.syncCompressUI();
      }
      syncCompressSteps();
      if ((window.TypeBeatRadio && window.TypeBeatRadio.applyExperimentalFilters) || tries > 40) {
        window.clearInterval(waitApi);
      }
    }, 50);
  }

  document.addEventListener("keydown", (event) => {
    if (event.defaultPrevented || event.metaKey || event.ctrlKey || event.altKey) return;
    const tag = (event.target && event.target.tagName) || "";
    if (tag === "INPUT" || tag === "TEXTAREA" || (event.target && event.target.isContentEditable)) {
      return;
    }
    const key = event.key.toLowerCase();
    if (event.shiftKey && key === "s") {
      event.preventDefault();
      cycleSkin();
      return;
    }
    if (event.shiftKey && key === "e") {
      event.preventDefault();
      setPanelOpen(!panelOpen);
    }
  });

  let chipMeasureCanvas;

  function measureChipTextWidth(text, fontSizePx, el) {
    if (!chipMeasureCanvas) chipMeasureCanvas = document.createElement("canvas");
    const ctx = chipMeasureCanvas.getContext("2d");
    if (!ctx) return text.length * fontSizePx * 0.55;
    const cs = getComputedStyle(el);
    ctx.font = `${cs.fontWeight || 700} ${fontSizePx}px ${cs.fontFamily || "sans-serif"}`;
    return ctx.measureText(text).width;
  }

  function applyChipFit(el) {
    if (!(el instanceof HTMLElement)) return;
    if (!el.classList.contains("genre-chip") && !el.classList.contains("exp-chip")) return;
    if (el.closest(".filter-chips--tiers")) {
      el.style.removeProperty("--chip-fit");
      el.removeAttribute("data-chip-len");
      return;
    }
    const text = (el.textContent || "").replace(/\s+/g, " ").trim();
    const n = text.length;
    el.style.setProperty("--chip-fit", "1");
    if (!text) {
      el.removeAttribute("data-chip-len");
      return;
    }
    const fitToWidth = () => {
      const maxW = el.clientWidth;
      if (maxW <= 0) return false;
      const cs = getComputedStyle(el);
      const padX =
        (parseFloat(cs.paddingLeft) || 0) + (parseFloat(cs.paddingRight) || 0);
      const budget = Math.max(8, maxW - padX - 4);
      let lo = 0.12;
      let hi = 1;
      let best = lo;
      for (let i = 0; i < 14; i += 1) {
        const fit = (lo + hi) / 2;
        el.style.setProperty("--chip-fit", String(fit));
        const sizePx = parseFloat(getComputedStyle(el).fontSize) || 10;
        const w = measureChipTextWidth(text, sizePx, el);
        if (w <= budget) {
          best = fit;
          lo = fit;
        } else {
          hi = fit;
        }
      }
      el.style.setProperty("--chip-fit", String(Number(best.toFixed(3))));
      return true;
    };
    if (!fitToWidth()) {
      requestAnimationFrame(() => applyChipFit(el));
      return;
    }
    el.setAttribute("data-chip-len", n <= 6 ? "short" : n <= 10 ? "mid" : n <= 13 ? "long" : "xl");
  }

  function scanChipFit(root) {
    if (!root) return;
    if (root.nodeType === 1 && (root.classList.contains("genre-chip") || root.classList.contains("exp-chip"))) {
      applyChipFit(root);
    }
    if (root.querySelectorAll) {
      root.querySelectorAll(".genre-chip, .exp-chip").forEach(applyChipFit);
    }
  }

  function bindChipFit() {
    const chipRo =
      typeof ResizeObserver !== "undefined"
        ? new ResizeObserver((entries) => {
            entries.forEach((e) => applyChipFit(e.target));
          })
        : null;

    const watchChip = (el) => {
      if (!(el instanceof HTMLElement)) return;
      if (!el.classList.contains("genre-chip") && !el.classList.contains("exp-chip")) return;
      if (chipRo) chipRo.observe(el);
    };

    scanChipFit(document);
    document.querySelectorAll(".genre-chip, .exp-chip").forEach(watchChip);

    const rail = document.getElementById("filter-rail");
    if (rail && typeof ResizeObserver !== "undefined") {
      new ResizeObserver(() => scanChipFit(document)).observe(rail);
    }

    const mo = new MutationObserver((recs) => {
      recs.forEach((r) => {
        if (r.type === "characterData" && r.target && r.target.parentElement) {
          applyChipFit(r.target.parentElement);
        }
        r.addedNodes.forEach((n) => {
          if (n.nodeType !== 1) return;
          scanChipFit(n);
          if (n.matches?.(".genre-chip, .exp-chip")) watchChip(n);
          n.querySelectorAll?.(".genre-chip, .exp-chip").forEach(watchChip);
        });
      });
    });
    mo.observe(document.body, { childList: true, subtree: true, characterData: true });
  }

  document.addEventListener("tb:art-update", () => {
    if ((root.getAttribute("data-skin") || DEFAULT_SKIN) === "deck") {
      ensureVinylSticker();
      syncVinylTitleText();
    }
  });

  function rotationDeg(node) {
    try {
      const t = window.getComputedStyle(node).transform;
      if (!t || t === "none") return -13;
      const m = new DOMMatrixReadOnly(t);
      return Math.atan2(m.b, m.a) * (180 / Math.PI);
    } catch {
      return -13;
    }
  }

  function bindHoverMotions() {
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)");
    const bind = (id) => {
      const btn = document.getElementById(id);
      if (!btn || btn.dataset.hoverBound === "1") return;
      btn.dataset.hoverBound = "1";
      const enter = () => {
        btn.classList.remove("is-leave-motion");
        btn.classList.add("is-enter-motion");
        if (id === "btn-loop" && !reduce.matches) {
          btn.classList.add("is-loop-spinning");
        }
      };
      const leave = (ev) => {
        if (ev && btn.contains(ev.relatedTarget)) return;
        btn.classList.remove("is-enter-motion");
        if (id === "btn-loop") {
          btn.classList.remove("is-loop-spinning");
        }
        if (reduce.matches) {
          btn.classList.remove("is-leave-motion");
          return;
        }
        if (id === "btn-loop") {
          const icon = btn.querySelector(".loop-icon");
          if (icon) {
            icon.style.setProperty("--loop-from", `${rotationDeg(icon)}deg`);
          }
        }
        btn.classList.remove("is-leave-motion");
        void btn.offsetWidth;
        btn.classList.add("is-leave-motion");
      };
      btn.addEventListener("pointerenter", enter);
      btn.addEventListener("pointerleave", leave);
      if (id !== "btn-loop") {
        btn.addEventListener("focus", enter);
        btn.addEventListener("blur", leave);
      }
      btn.addEventListener("animationend", (ev) => {
        if (!btn.classList.contains("is-leave-motion")) return;
        const name = ev.animationName || "";
        if (
          name === "react-like-lift" ||
          name === "react-dislike-dive" ||
          name === "react-loop-spin-out" ||
          name === "react-notfit-settle" ||
          name === "react-leave-soft"
        ) {
          btn.classList.remove("is-leave-motion");
        }
      });
    };
    ["btn-like", "btn-dislike", "btn-loop", "btn-not-fit"].forEach(bind);
  }

  function assertLayoutInvariants() {
    const check = () => {
      const expDock = document.getElementById("exp-dock");
      if (expDock && !expDock.querySelector(".exp-panel")) {
        console.error("[radio] exp-dock empty after init — rebuilding Exp panel");
        panel = null;
        fab = null;
        buildExpPanel();
      }

      const rawSkin = root.getAttribute("data-skin");
      const safeSkin = normalizeSkin(rawSkin);
      if (rawSkin !== safeSkin) {
        console.error("[radio] unknown data-skin — falling back to deck");
        applySkin(safeSkin);
      }

      const player = document.querySelector(".player");
      if (player) {
        const { width, height } = player.getBoundingClientRect();
        if (width < 8 || height < 8) {
          console.error("[radio] .player near-zero size — resetting data-layout=classic");
          root.setAttribute("data-layout", DEFAULT_LAYOUT);
        }
      }

      const rightRail = document.querySelector(".chrome-rail--right");
      if (rightRail && window.getComputedStyle(rightRail).display === "none") {
        console.error("[radio] .chrome-rail--right is display:none — layout CSS regression");
      }
    };
    if (typeof requestAnimationFrame === "function") {
      requestAnimationFrame(check);
    } else {
      check();
    }
  }

  function init() {
    wireCompressStepButtons();
    ensureVinylSticker();
    /* Exp + filters before skin DOM — init must not throw before rails are populated. */
    buildFilterRailExtras();
    buildExpPanel();
    buildNowPlaying();
    buildVinylTitle();
    ensureAsTapeChrome();
    syncSkinChrome();
    bindHoverMotions();
    bindChipFit();
    assertLayoutInvariants();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  window.TypeBeatSkins = {
    rescanChipFit: () => scanChipFit(document),
    fitTapeLabels,
    ensureVinylSticker,
    syncVinylTitle: syncVinylTitleText,
    getVinylTitleScale: () => vinylTitleScale,
    setVinylTitleScale,
    getVinylTitlePlacement,
    setVinylTitlePlacement,
    refitVinylTitleLayers,
  };
})();
