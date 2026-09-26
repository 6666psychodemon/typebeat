/* Radio player — queue, transport, polish, view-range chips */

(() => {
  const $ = (sel) => document.querySelector(sel);

  const STORAGE_NOT_FIT = "typebeat.radio.notFit";
  const STORAGE_EVENTS = "typebeat.radio.events";
  const STORAGE_POLISH = "typebeat.radio.polishPreset";
  const STORAGE_POLISH_AMT = "typebeat.radio.polishAmount";
  const STORAGE_TIER = "typebeat.radio.viewTier";
  const STORAGE_LOOP = "typebeat.radio.loopTrack";
  const STORAGE_DEVICE = "typebeat.radio.deviceId";
  const STORAGE_XFADE_MODE = "typebeat.radio.xfadeMode";
  const STORAGE_XFADE_PRELOAD = "typebeat.radio.xfadePreload";
  const STORAGE_XFADE_HANDOFF = "typebeat.radio.xfadeHandoffGate";
  const STORAGE_XFADE_OVERLAP = "typebeat.radio.xfadeOverlapMin";
  const STORAGE_XFADE_DEBUG = "typebeat.radio.xfadeDebug";
  const STORAGE_XFADE_START = "typebeat.radio.xfadeStartAt";
  /** Softened hard ceiling (matches polish.js MAX_P). */
  const POLISH_MAX = 0.82;
  /** Drag distance (px up) mapping 0 → POLISH_MAX. */
  const POLISH_DRAG_PX = 140;
  /** Default compressor amount ≈ 25% of max when localStorage unset. */
  const POLISH_DEFAULT = POLISH_MAX * 0.25;
  /**
   * Crossfade timing — always-on product behavior (not optional).
   * Art / atmosphere / iframe volume fades use FADE_MS (~480ms).
   * True dual-source overlap (hear A+B together) uses CROSSFADE_MS (~7s)
   * via polish graph gains on dual same-origin <audio> hosts.
   */
  const FADE_MS = 480;
  const ART_FADE_MS = FADE_MS;
  /** True overlapping A↔B gain crossfade when local audio is ready. */
  const CROSSFADE_MS = 7000;
  /** Wait for next local cache / element buffer before degrading off dual overlap.
   *  Keep short enough that Next feels responsive; overlap itself is 3s/7s. */
  const XFADE_READY_MS = 4500;
  /** Max wait for local cache during skip handoff before iframe fallback. */
  const LOCAL_HANDOFF_MAX_MS = 5500;
  /** One short retry after primary handoff wait (never loop). */
  const LOCAL_CACHE_RETRY_MS = 1200;
  /** Prep/buffer budget before overlap starts (overlap itself clears this timer). */
  const NAV_HANDOFF_PREP_MS = 14000;
  /** If Next/Prev is clicked while the lock has been held this long, force-release. */
  const NAV_STUCK_MS = 2500;
  const DEAD_COVER_MAX_SKIPS = 8;
  const DEAD_COVER_PLACEHOLDER_MAX_W = 130;
  const DEAD_COVER_PLACEHOLDER_MAX_H = 100;

  const XFADE_MODE_DEF = {
    graph7: { id: "graph7", label: "7s crossfade", ms: 7000, path: "graph" },
    graph3: { id: "graph3", label: "3s crossfade", ms: 3000, path: "graph" },
    volume7: { id: "volume7", label: "Volume 7s", ms: 7000, path: "volume" },
    volume3: { id: "volume3", label: "Volume 3s", ms: 3000, path: "volume" },
    instant: { id: "instant", label: "Instant", ms: 0, path: "instant" },
  };
  const XFADE_PRELOAD_DEF = {
    aggressive: { id: "aggressive", label: "Aggressive" },
    early: { id: "early", label: "Early" },
    on_skip: { id: "on_skip", label: "On skip only" },
    off: { id: "off", label: "Off" },
  };
  const XFADE_HANDOFF_DEF = {
    require_preloaded: { id: "require_preloaded", label: "Require preloaded" },
    allow_buffer_wait: { id: "allow_buffer_wait", label: "Allow buffer wait" },
  };
  const XFADE_OVERLAP_DEF = {
    auto: { id: "auto", label: "Auto" },
    "0": { id: "0", label: "0", ms: 0 },
    "3000": { id: "3000", label: "3s", ms: 3000 },
    "7000": { id: "7000", label: "7s", ms: 7000 },
    "10000": { id: "10000", label: "10s", ms: 10000 },
  };
  const XFADE_START_DEF = {
    "0": { id: "0", label: "0s", sec: 0 },
    "3": { id: "3", label: "3s", sec: 3 },
    "5": { id: "5", label: "5s", sec: 5 },
    "10": { id: "10", label: "10s", sec: 10 },
  };
  const DEFAULT_XFADE_MODE = "graph7";
  /** Aggressive preload keeps Next smooth — on_skip still available in Exp. */
  const DEFAULT_XFADE_PRELOAD = "aggressive";
  const DEFAULT_XFADE_HANDOFF = "allow_buffer_wait";
  const DEFAULT_XFADE_OVERLAP = "auto";
  const DEFAULT_XFADE_START = "0";
  /** Short edge for play/pause so transport never hard-cuts PCM. */
  const TRANSPORT_FADE_MS = 70;
  const VOLUME_DEFAULT = 100;
  const EVENT_SCHEMA = 1;
  /** Reasons that leave the current track → loop toggle resets to off. */
  const LOOP_RESET_REASONS = new Set([
    "next",
    "prev",
    "ended",
    "not_fit",
    "station",
    "error",
    "skip",
    "nav",
  ]);
  const REFILL_WHEN_REMAINING = 12;
  /** Server + client kick depth for /api/audio cache warming. */
  const PREFETCH_AUDIO_AHEAD = 5;
  /** Re-kick inactive slot preload when this many seconds remain (or on track start). */
  const PRELOAD_LEAD_SEC = 30;
  const PRELOAD_KICK_THROTTLE_MS = 1800;
  const DEFAULT_STATION = "all";
  const DEFAULT_TIER = "all";
  /** Pending genre chip evolves from "NEXT UP" → "CHANGE NOW?" */
  const PENDING_EVOLVE_MS = 650;
  /** Abort slow /api/queue so startup never hangs on a locked/scanning DB. */
  const QUEUE_FETCH_TIMEOUT_MS = 8000;
  const QUEUE_INDEX_RETRIES = 8;

  const el = {
    chips: $("#genre-chips"),
    tiers: $("#tier-chips"),
    license: $("#license-chips"),
    artA: $("#art-a"),
    artB: $("#art-b"),
    artBtn: $("#btn-play"),
    playGlyph: $("#play-glyph"),
    prev: $("#btn-prev"),
    next: $("#btn-next"),
    prevThumb: $("#prev-thumb"),
    nextThumb: $("#next-thumb"),
    like: $("#btn-like"),
    dislike: $("#btn-dislike"),
    notFit: $("#btn-not-fit"),
    loop: $("#btn-loop"),
    washA: $("#atmosphere-a"),
    washB: $("#atmosphere-b"),
    coverA: $("#atmosphere-cover-a"),
    coverB: $("#atmosphere-cover-b"),
    atmosphere: $("#atmosphere"),
    level: $("#btn-compress"),
    artTitle: $("#art-title"),
    artTitleText: $("#art-title-text"),
    audioA: $("#audio-host-a"),
    audioB: $("#audio-host-b"),
    authRail: $("#auth-rail"),
    btnRequestInvite: $("#btn-request-invite"),
    btnSignIn: $("#btn-sign-in"),
    btnSignOut: $("#btn-sign-out"),
    authUser: $("#auth-user"),
    inviteOverlay: $("#invite-overlay"),
    inviteBackdrop: $("#invite-backdrop"),
    inviteForm: $("#invite-form"),
    inviteFormWrap: $("#invite-form-wrap"),
    inviteDone: $("#invite-done"),
    inviteSetup: $("#invite-setup"),
    inviteEmail: $("#invite-email"),
    inviteNote: $("#invite-note"),
    inviteError: $("#invite-error"),
    inviteCancel: $("#invite-cancel"),
    inviteSubmit: $("#invite-submit"),
    inviteDoneClose: $("#invite-done-close"),
    inviteDoneCopy: $("#invite-done-copy"),
    inviteDoneSignin: $("#invite-done-signin"),
    inviteSetupClose: $("#invite-setup-close"),
  };

  const state = {
    genres: [],
    viewTiers: [],
    genreId: DEFAULT_STATION,
    tierId: DEFAULT_TIER,
    requireFree: false,
    requireFfp: false,
    requireProlific: false,
    /** @type {number|null} */
    maxAgeMonths: null,
    queue: [],
    index: 0,
    nextCursor: null,
    hasMore: false,
    refilling: false,
    player: null,
    playing: false,
    artFlip: false,
    washFlip: false,
    loadingQueue: false,
    transitioning: false,
    trackStartedAt: 0,
    reducedMotion: window.matchMedia("(prefers-reduced-motion: reduce)").matches,
    polishAmount: POLISH_DEFAULT,
    polishPreset: "medium",
    polish: null,
    polishCanHear: false,
    polishConnected: false,
    /** True when both audio hosts are in the polish graph (A↔B gain xfade). */
    polishDual: false,
    /** @type {'local'|'iframe'|null} */
    audioMode: null,
    /** @type {'a'|'b'} */
    activeSlot: "a",
    localAudioTools: null,
    prepareGen: 0,
    prefetchGen: 0,
    readyCache: Object.create(null),
    /** Inactive-slot preload for seamless xfade (buffered + silent play). */
    slotPreload: {
      slot: null,
      videoId: null,
      url: null,
      buffered: false,
      primed: false,
    },
    /** Pending style station (legacy deferred switch — kept cleared). */
    pendingGenreId: null,
    /** @type {'up_next'|'change_now'|null} */
    pendingPhase: null,
    pendingTimer: 0,
    pendingPrefetch: null,
    /** True while a station switch fetch is applying. */
    pendingCommit: false,
    /** Generation token so a later style click wins over an in-flight fetch. */
    stationGen: 0,
    /** Single-flight skip/next mutex — always cleared in releaseNavLock(). */
    navLock: {
      token: 0,
      busy: false,
      timer: 0,
      startedAt: 0,
    },
    /** Latest nav intent coalesced while handoff is in flight. */
    navQueued: null,
    /** Set by handoff timeout — in-flight work must bail and fallback. */
    navHandoffTimedOut: false,
    /** True while A↔B overlap is actively running — never iframe-cut mid-fade. */
    xfadeInProgress: false,
    loopTrack: false,
    tipEl: null,
    compressDrag: null,
    tipHideTimer: 0,
    /** Accumulated audible listen time for current video_id (excludes paused gaps). */
    listenAccumMs: 0,
    /** When the current play segment started (0 if paused). */
    listenSegmentAt: 0,
    deviceId: null,
    preloadKickAt: 0,
    /** Exp panel crossfade experiments (localStorage-backed). */
    xfadeExp: {
      mode: DEFAULT_XFADE_MODE,
      preload: DEFAULT_XFADE_PRELOAD,
      handoffGate: DEFAULT_XFADE_HANDOFF,
      overlapMin: DEFAULT_XFADE_OVERLAP,
      startAt: DEFAULT_XFADE_START,
      debug: false,
    },
    /** @type {{ authenticated: boolean, user: object|null, google_configured: boolean }} */
    auth: {
      authenticated: false,
      user: null,
      google_configured: false,
    },
  };

  function normalizeXfadeMode(id) {
    const raw = (id == null ? "" : String(id)).trim().toLowerCase();
    if (Object.prototype.hasOwnProperty.call(XFADE_MODE_DEF, raw)) return raw;
    return DEFAULT_XFADE_MODE;
  }

  function normalizeXfadePreload(id) {
    const raw = (id == null ? "" : String(id)).trim().toLowerCase();
    if (Object.prototype.hasOwnProperty.call(XFADE_PRELOAD_DEF, raw)) return raw;
    return DEFAULT_XFADE_PRELOAD;
  }

  function normalizeXfadeHandoff(id) {
    const raw = (id == null ? "" : String(id)).trim().toLowerCase();
    if (Object.prototype.hasOwnProperty.call(XFADE_HANDOFF_DEF, raw)) return raw;
    return DEFAULT_XFADE_HANDOFF;
  }

  function normalizeXfadeOverlap(id) {
    const raw = id == null ? DEFAULT_XFADE_OVERLAP : String(id).trim().toLowerCase();
    if (Object.prototype.hasOwnProperty.call(XFADE_OVERLAP_DEF, raw)) return raw;
    return DEFAULT_XFADE_OVERLAP;
  }

  function normalizeXfadeStart(id) {
    const raw = id == null ? DEFAULT_XFADE_START : String(id).trim().toLowerCase();
    if (Object.prototype.hasOwnProperty.call(XFADE_START_DEF, raw)) return raw;
    return DEFAULT_XFADE_START;
  }

  function readXfadeExp() {
    try {
      state.xfadeExp.mode = normalizeXfadeMode(localStorage.getItem(STORAGE_XFADE_MODE));
      let preload = normalizeXfadePreload(localStorage.getItem(STORAGE_XFADE_PRELOAD));
      /* Smoothness KEY: migrate prior on_skip default → aggressive once. */
      if (
        preload === "on_skip" &&
        localStorage.getItem("typebeat.radio.xfadePreloadMigrated") !== "1"
      ) {
        preload = "aggressive";
        localStorage.setItem(STORAGE_XFADE_PRELOAD, "aggressive");
        localStorage.setItem("typebeat.radio.xfadePreloadMigrated", "1");
      }
      state.xfadeExp.preload = preload;
      state.xfadeExp.handoffGate = normalizeXfadeHandoff(localStorage.getItem(STORAGE_XFADE_HANDOFF));
      state.xfadeExp.overlapMin = normalizeXfadeOverlap(localStorage.getItem(STORAGE_XFADE_OVERLAP));
      let startAt = normalizeXfadeStart(localStorage.getItem(STORAGE_XFADE_START));
      /* Seek-to-5s mid-handoff caused silence gaps — migrate to 0 once. */
      if (
        startAt === "5" &&
        localStorage.getItem("typebeat.radio.xfadeStartMigrated") !== "1"
      ) {
        startAt = "0";
        localStorage.setItem(STORAGE_XFADE_START, "0");
        localStorage.setItem("typebeat.radio.xfadeStartMigrated", "1");
      }
      state.xfadeExp.startAt = startAt;
      state.xfadeExp.debug = localStorage.getItem(STORAGE_XFADE_DEBUG) === "1";
    } catch {
      /* private mode */
    }
  }

  function persistXfadeExp() {
    try {
      localStorage.setItem(STORAGE_XFADE_MODE, state.xfadeExp.mode);
      localStorage.setItem(STORAGE_XFADE_PRELOAD, state.xfadeExp.preload);
      localStorage.setItem(STORAGE_XFADE_HANDOFF, state.xfadeExp.handoffGate);
      localStorage.setItem(STORAGE_XFADE_OVERLAP, state.xfadeExp.overlapMin);
      localStorage.setItem(STORAGE_XFADE_START, state.xfadeExp.startAt);
      if (state.xfadeExp.debug) {
        localStorage.setItem(STORAGE_XFADE_DEBUG, "1");
      } else {
        localStorage.removeItem(STORAGE_XFADE_DEBUG);
      }
    } catch {
      /* private mode */
    }
  }

  function getXfadeModeDef() {
    return XFADE_MODE_DEF[state.xfadeExp.mode] || XFADE_MODE_DEF[DEFAULT_XFADE_MODE];
  }

  function getEffectiveXfadeMs() {
    if (state.reducedMotion) return 0;
    const overlap = state.xfadeExp.overlapMin;
    if (overlap !== DEFAULT_XFADE_OVERLAP) {
      const def = XFADE_OVERLAP_DEF[overlap];
      if (def && Number.isFinite(def.ms)) return Math.max(0, def.ms);
    }
    return getXfadeModeDef().ms;
  }

  function resolveXfadePath() {
    const ms = getEffectiveXfadeMs();
    if (ms <= 0) return "instant";
    return getXfadeModeDef().path;
  }

  function xfadePreloadAllowsBackground() {
    const p = state.xfadeExp.preload;
    return p === "aggressive" || p === "early";
  }

  function xfadePreloadOnSkipOnly() {
    return state.xfadeExp.preload === "on_skip";
  }

  function xfadeRequirePreloaded() {
    return state.xfadeExp.handoffGate === "require_preloaded";
  }

  function xfadeDbg(...args) {
    if (state.xfadeExp.debug) console.info(...args);
  }

  function preloadDbg(...args) {
    if (state.xfadeExp.debug) console.info(...args);
  }

  function logXfadeConfig() {
    const mode = getXfadeModeDef();
    const preload = XFADE_PRELOAD_DEF[state.xfadeExp.preload] || XFADE_PRELOAD_DEF[DEFAULT_XFADE_PRELOAD];
    const handoff = XFADE_HANDOFF_DEF[state.xfadeExp.handoffGate] || XFADE_HANDOFF_DEF[DEFAULT_XFADE_HANDOFF];
    const overlap = XFADE_OVERLAP_DEF[state.xfadeExp.overlapMin] || XFADE_OVERLAP_DEF[DEFAULT_XFADE_OVERLAP];
    const startAt = XFADE_START_DEF[state.xfadeExp.startAt] || XFADE_START_DEF[DEFAULT_XFADE_START];
    console.info(
      `[xfade] mode=${mode.label} preload=${preload.label} handoff=${handoff.label} overlap=${overlap.label} start=${startAt.label} ms=${getEffectiveXfadeMs()}`
    );
  }

  function getXfadeStartSec() {
    const def = XFADE_START_DEF[state.xfadeExp.startAt] || XFADE_START_DEF[DEFAULT_XFADE_START];
    return def.sec || 0;
  }

  /** Skip intro on incoming track during handoff (Exp "Start at").
   *  Never seek while the host is already playing — that causes a silence gap. */
  function applyIncomingStartOffset(audio, { force = false } = {}) {
    const sec = getXfadeStartSec();
    if (sec <= 0 || !audio) return;
    if (!force && !audio.paused) return;
    const apply = () => {
      try {
        const dur = audio.duration;
        const cur = Number.isFinite(audio.currentTime) ? audio.currentTime : 0;
        if (Math.abs(cur - sec) < 0.35) return;
        if (Number.isFinite(dur) && dur > sec + 0.5) {
          audio.currentTime = sec;
        } else if (!Number.isFinite(dur) || dur === 0) {
          audio.currentTime = sec;
        }
      } catch {
        /* ignore seek before metadata */
      }
    };
    if (audio.readyState >= 1) apply();
    else audio.addEventListener("loadedmetadata", apply, { once: true });
  }

  function localHandoffBudgetMs(wantOverlap) {
    return wantOverlap ? LOCAL_HANDOFF_MAX_MS : 800;
  }

  /** Wait for cache + inactive-slot buffer — not the overlap fade itself. */
  function computeNavHandoffTimeoutMs(wantOverlap) {
    if (!wantOverlap) return 5000;
    return LOCAL_HANDOFF_MAX_MS + XFADE_READY_MS + 2000;
  }

  function applyCrossfadeSettings({
    mode,
    preload,
    handoffGate,
    overlapMin,
    startAt,
    debug,
  } = {}) {
    let changed = false;
    if (mode != null && normalizeXfadeMode(mode) !== state.xfadeExp.mode) {
      state.xfadeExp.mode = normalizeXfadeMode(mode);
      changed = true;
    }
    if (preload != null && normalizeXfadePreload(preload) !== state.xfadeExp.preload) {
      state.xfadeExp.preload = normalizeXfadePreload(preload);
      changed = true;
    }
    if (handoffGate != null && normalizeXfadeHandoff(handoffGate) !== state.xfadeExp.handoffGate) {
      state.xfadeExp.handoffGate = normalizeXfadeHandoff(handoffGate);
      changed = true;
    }
    if (overlapMin != null && normalizeXfadeOverlap(overlapMin) !== state.xfadeExp.overlapMin) {
      state.xfadeExp.overlapMin = normalizeXfadeOverlap(overlapMin);
      changed = true;
    }
    if (startAt != null && normalizeXfadeStart(startAt) !== state.xfadeExp.startAt) {
      state.xfadeExp.startAt = normalizeXfadeStart(startAt);
      changed = true;
    }
    if (typeof debug === "boolean" && debug !== state.xfadeExp.debug) {
      state.xfadeExp.debug = debug;
      changed = true;
    }
    if (!changed) return;
    persistXfadeExp();
    logXfadeConfig();
    xfadeDbg("[xfade] settings applied — takes effect on next skip");
  }

  function titleCaseLabel(text) {
    return String(text || "")
      .split(/\s+/)
      .filter(Boolean)
      .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
      .join(" ");
  }

  function capsLabel(text) {
    return String(text || "").toUpperCase();
  }

  /** Two-line tier tick markup (Views + Track age sliders). */
  function tierLinesMarkup(lineA, lineB) {
    if (lineB == null || lineB === "") {
      return `<span class="views-tier-lines tier-lines"><span>${lineA}</span></span>`;
    }
    return `<span class="views-tier-lines tier-lines"><span>${lineA}</span><span>${lineB}</span></span>`;
  }

  /** Views slider ticks: stack unit line (e.g. &lt;1 + K) for narrow columns. */
  function viewsTierLabelMarkup(label) {
    const raw = capsLabel(label);
    if (!raw) return "";
    if (raw === "ALL") {
      return tierLinesMarkup("ALL");
    }
    const lt = raw.match(/^<(\d+)(K)?$/);
    if (lt) {
      return tierLinesMarkup(`&lt;${lt[1]}`, lt[2] || "K");
    }
    const range = raw.match(/^(\d+K)–(\d+K)$/);
    if (range) {
      return tierLinesMarkup(range[1], range[2]);
    }
    const singleK = raw.match(/^(\d+)K$/);
    if (singleK) {
      return tierLinesMarkup(singleK[1], "K");
    }
    return tierLinesMarkup(raw);
  }

  /** Track age slider ticks: &lt;6 + M, &lt;2 + Y, ALL on one line. */
  function ageTierLabelMarkup(label) {
    const raw = capsLabel(label);
    if (!raw) return "";
    if (raw === "ALL") {
      return tierLinesMarkup("ALL");
    }
    const lt = raw.match(/^<(\d+)(M|Y)$/);
    if (lt) {
      return tierLinesMarkup(`&lt;${lt[1]}`, lt[2]);
    }
    return tierLinesMarkup(raw);
  }

  function getDeviceId() {
    if (state.deviceId) return state.deviceId;
    try {
      let id = localStorage.getItem(STORAGE_DEVICE);
      if (!id) {
        id =
          typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
            ? crypto.randomUUID()
            : `tb-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
        localStorage.setItem(STORAGE_DEVICE, id);
      }
      state.deviceId = id;
      return id;
    } catch {
      state.deviceId = state.deviceId || `tb-ephemeral-${Date.now().toString(36)}`;
      return state.deviceId;
    }
  }

  function escapeAttr(s) {
    return String(s || "")
      .replace(/&/g, "&amp;")
      .replace(/"/g, "&quot;")
      .replace(/</g, "&lt;");
  }

  function thumbUrl(videoId) {
    // maxres often 404 on UG uploads; hqdefault is reliable 16:9 — CSS crops square
    return `https://i.ytimg.com/vi/${videoId}/hqdefault.jpg`;
  }

  function currentTrack() {
    return state.queue[state.index] || null;
  }

  function stayMs() {
    if (!state.trackStartedAt) return 0;
    return Math.max(0, Date.now() - state.trackStartedAt);
  }

  function flushListenSegment() {
    if (!state.listenSegmentAt) return;
    state.listenAccumMs += Math.max(0, Date.now() - state.listenSegmentAt);
    state.listenSegmentAt = 0;
  }

  function startListenSegment() {
    if (!state.listenSegmentAt) state.listenSegmentAt = Date.now();
  }

  /** Audible time on current track (pauses excluded). */
  function listenMs() {
    let ms = state.listenAccumMs;
    if (state.listenSegmentAt) ms += Math.max(0, Date.now() - state.listenSegmentAt);
    return Math.max(0, ms);
  }

  function markTrackStart() {
    state.trackStartedAt = Date.now();
    state.listenAccumMs = 0;
    state.listenSegmentAt = state.playing ? Date.now() : 0;
  }

  function resetLoopOnTrackChange(reason) {
    if (!LOOP_RESET_REASONS.has(reason)) return;
    if (!state.loopTrack) {
      syncLoopButton();
      return;
    }
    state.loopTrack = false;
    try {
      localStorage.setItem(STORAGE_LOOP, "0");
    } catch {
      /* ignore */
    }
    syncLoopButton();
  }

  function audioEl(slot) {
    return slot === "b" ? el.audioB : el.audioA;
  }

  function activeAudio() {
    return audioEl(state.activeSlot);
  }

  function otherSlot(slot = state.activeSlot) {
    return slot === "a" ? "b" : "a";
  }

  /* --- not-fit persistence (localStorage, keyed video_id + genre) --- */
  function readNotFitMap() {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_NOT_FIT) || "{}") || {};
    } catch {
      return {};
    }
  }

  function writeNotFitMap(map) {
    localStorage.setItem(STORAGE_NOT_FIT, JSON.stringify(map));
  }

  function notFitKey(videoId, genreId) {
    return `${genreId}::${videoId}`;
  }

  function isNotFit(videoId, genreId = state.genreId) {
    const map = readNotFitMap();
    return Boolean(map[notFitKey(videoId, genreId)]);
  }

  function markNotFit(videoId, genreId = state.genreId) {
    const map = readNotFitMap();
    map[notFitKey(videoId, genreId)] = {
      at: new Date().toISOString(),
      genre: genreId,
      video_id: videoId,
    };
    writeNotFitMap(map);
  }

  function filterNotFit(tracks, genreId) {
    return (tracks || []).filter((t) => t && t.video_id && !isNotFit(t.video_id, genreId));
  }

  /* --- invite / auth --- */
  function isAuthed() {
    return Boolean(state.auth && state.auth.authenticated && state.auth.user);
  }

  function isVinylNameOn() {
    /* Curved vinyl name is Deck-only; Cassette/Signal keep flat titles. */
    return (
      document.documentElement.classList.contains("is-vinyl-name") &&
      document.documentElement.getAttribute("data-skin") === "deck"
    );
  }

  function syncAuthChrome() {
    const authed = isAuthed();
    const googleOk = Boolean(state.auth.google_configured);
    document.documentElement.classList.toggle("is-authed", authed);
    if (el.btnRequestInvite) {
      el.btnRequestInvite.hidden = authed;
    }
    if (el.btnSignIn) {
      /* Poster shell: invite CTA only — Sign In stays in invite modal / OAuth callback. */
      el.btnSignIn.hidden = true;
      el.btnSignIn.dataset.tip = googleOk
        ? "Sign In With Google"
        : "Sign In Setup Required";
    }
    if (el.btnSignOut) {
      el.btnSignOut.hidden = !authed;
    }
    if (el.authUser) {
      el.authUser.hidden = !authed;
      el.authUser.textContent = authed
        ? state.auth.user.name || state.auth.user.email || ""
        : "";
    }
    if (el.like) {
      el.like.dataset.tip = "Like";
      el.like.setAttribute("aria-label", "Like");
    }
    if (el.dislike) {
      el.dislike.dataset.tip = "Dislike";
      el.dislike.setAttribute("aria-label", "Dislike");
    }
    syncArtTitle();
  }

  function trackDisplayTitle(track) {
    if (!track) return "";
    const raw = (track.title || "").trim();
    if (raw) return raw;
    return track.video_id ? `Track ${track.video_id}` : "";
  }

  function syncArtTitle(trackOverride = null) {
    if (!el.artTitle || !el.artTitleText) return;
    const track = trackOverride || currentTrack();
    const title = trackDisplayTitle(track);
    const prev = el.artTitleText.textContent || "";
    /* Vinyl Exp: always feed title text for the curved SVG; hide lower-third. */
    if (isVinylNameOn()) {
      el.artTitleText.textContent = title || "";
      el.artTitle.hidden = true;
      if (window.TypeBeatSkins && typeof window.TypeBeatSkins.syncVinylTitle === "function") {
        window.TypeBeatSkins.syncVinylTitle();
      }
      return;
    }
    /* Product rule: cover lower-third title for unauth only. */
    if (!isAuthed() && title) {
      if (title !== prev) el.artTitleText.textContent = title;
      el.artTitle.hidden = false;
      return;
    }
    el.artTitle.hidden = true;
    if (el.artTitleText.textContent) el.artTitleText.textContent = "";
  }

  function setInviteView(view) {
    const form = el.inviteFormWrap;
    const done = el.inviteDone;
    const setup = el.inviteSetup;
    if (form) form.hidden = view !== "form";
    if (done) done.hidden = view !== "done";
    if (setup) setup.hidden = view !== "setup";
  }

  function openInviteModal(opts = {}) {
    if (!el.inviteOverlay) return;
    const view = opts.view || "form";
    setInviteView(view);
    if (el.inviteError) {
      el.inviteError.hidden = true;
      el.inviteError.textContent = "";
    }
    if (view === "form" && el.inviteForm) {
      el.inviteForm.reset();
    }
    if (el.inviteDone) {
      const title = el.inviteDone.querySelector(".invite-title");
      if (title && view === "done") {
        title.textContent = opts.title || "Request Sent";
      }
    }
    if (view === "done") {
      if (el.inviteDoneCopy && opts.message) {
        el.inviteDoneCopy.textContent = opts.message;
      }
      if (el.inviteDoneSignin) {
        const showSignin =
          opts.status === "invited" || opts.status === "redeemed";
        el.inviteDoneSignin.hidden = !showSignin;
      }
    }
    el.inviteOverlay.hidden = false;
    requestAnimationFrame(() => {
      el.inviteOverlay.classList.add("is-open");
      if (view === "form" && el.inviteEmail) el.inviteEmail.focus();
    });
  }

  function closeInviteModal() {
    if (!el.inviteOverlay) return;
    el.inviteOverlay.classList.remove("is-open");
    const finish = () => {
      el.inviteOverlay.hidden = true;
      setInviteView("form");
    };
    if (state.reducedMotion) finish();
    else setTimeout(finish, 280);
  }

  function openSignIn() {
    if (state.auth.google_configured) {
      window.location.href = "/auth/google";
      return;
    }
    openInviteModal({ view: "setup" });
  }

  async function loadAuthStatus() {
    try {
      const res = await fetch("/api/auth/status", { credentials: "same-origin" });
      const data = await res.json();
      state.auth = {
        authenticated: Boolean(data.authenticated),
        user: data.user || null,
        google_configured: Boolean(data.google_configured),
      };
    } catch {
      state.auth = {
        authenticated: false,
        user: null,
        google_configured: false,
      };
    }
    syncAuthChrome();
  }

  function handleAuthQueryParams() {
    const params = new URLSearchParams(window.location.search);
    const auth = params.get("auth");
    if (!auth) return;
    const msg = params.get("msg") || "";
    if (auth === "ok") {
      /* signed in — chrome refreshes via loadAuthStatus */
    } else if (auth === "setup") {
      openInviteModal({ view: "setup" });
    } else if (auth === "denied" || auth === "error") {
      openInviteModal({
        view: "done",
        status: "denied",
        title: "No Access",
        message: msg || "No invite for this Google account",
      });
      if (el.inviteDoneSignin) el.inviteDoneSignin.hidden = true;
    }
    const url = new URL(window.location.href);
    url.searchParams.delete("auth");
    url.searchParams.delete("msg");
    window.history.replaceState({}, "", url.pathname + url.search + url.hash);
  }

  async function persistReaction(reaction) {
    const track = currentTrack();
    if (!track || !isAuthed()) return;
    try {
      await fetch("/api/reactions", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          video_id: track.video_id,
          reaction,
          genre: state.genreId,
        }),
      });
    } catch {
      /* ignore */
    }
  }

  function onReactionClick(reaction) {
    if (!isAuthed()) {
      openInviteModal({ view: "form" });
      return;
    }
    flashBtn(reaction === "like" ? el.like : el.dislike);
    logEvent(reaction);
    persistReaction(reaction);
  }

  function wireInviteUi() {
    if (el.btnRequestInvite) {
      el.btnRequestInvite.addEventListener("click", () => openInviteModal({ view: "form" }));
    }
    if (el.btnSignIn) {
      el.btnSignIn.addEventListener("click", () => openSignIn());
    }
    if (el.btnSignOut) {
      el.btnSignOut.addEventListener("click", () => {
        window.location.href = "/auth/logout";
      });
    }
    const closers = [
      el.inviteBackdrop,
      el.inviteCancel,
      el.inviteDoneClose,
      el.inviteSetupClose,
    ];
    closers.forEach((node) => {
      if (node) node.addEventListener("click", () => closeInviteModal());
    });
    if (el.inviteDoneSignin) {
      el.inviteDoneSignin.addEventListener("click", () => openSignIn());
    }
    if (el.inviteForm) {
      el.inviteForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const email = (el.inviteEmail && el.inviteEmail.value.trim()) || "";
        const note = (el.inviteNote && el.inviteNote.value.trim()) || "";
        if (!email) {
          if (el.inviteError) {
            el.inviteError.hidden = false;
            el.inviteError.textContent = "Email required";
          }
          return;
        }
        if (el.inviteSubmit) el.inviteSubmit.disabled = true;
        try {
          const res = await fetch("/api/invite-request", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, note: note || undefined }),
          });
          const data = await res.json().catch(() => ({}));
          if (!res.ok || data.ok === false) {
            if (el.inviteError) {
              el.inviteError.hidden = false;
              el.inviteError.textContent = data.error || "Could not send request";
            }
            return;
          }
          openInviteModal({
            view: "done",
            status: data.status,
            title:
              data.status === "invited" || data.status === "redeemed"
                ? "You're Invited"
                : "Request Sent",
            message: data.message || "Request sent — we'll be in touch.",
          });
        } catch {
          if (el.inviteError) {
            el.inviteError.hidden = false;
            el.inviteError.textContent = "Could not send request";
          }
        } finally {
          if (el.inviteSubmit) el.inviteSubmit.disabled = false;
        }
      });
    }
    window.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && el.inviteOverlay && !el.inviteOverlay.hidden) {
        closeInviteModal();
      }
    });
  }

  /* --- lightweight event log (localStorage + optional /api/events) --- */
  function logEvent(type, extra = {}) {
    const track = currentTrack();
    const payload = {
      schema: EVENT_SCHEMA,
      type,
      ts: new Date().toISOString(),
      device_id: getDeviceId(),
      genre: state.genreId,
      tier: state.tierId,
      is_free: state.requireFree,
      free_for_profit: state.requireFfp,
      video_id: track ? track.video_id : null,
      stay_ms: stayMs(),
      listen_ms: listenMs(),
      audio_mode: state.audioMode,
      ...extra,
    };

    try {
      const buf = JSON.parse(localStorage.getItem(STORAGE_EVENTS) || "[]");
      buf.push(payload);
      localStorage.setItem(STORAGE_EVENTS, JSON.stringify(buf.slice(-400)));
    } catch {
      /* ignore quota */
    }

    try {
      fetch("/api/events", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        keepalive: true,
      }).catch(() => {});
    } catch {
      /* offline / no server hook */
    }
  }

  function crossfadeArt(videoId) {
    /* Deck vinyl stays full opacity — atmosphere layers crossfade via --fade-ms. */
    const nextImg = state.artFlip ? el.artA : el.artB;
    const prevImg = state.artFlip ? el.artB : el.artA;
    const url = thumbUrl(videoId);

    const activate = () => {
      nextImg.classList.add("is-active");
      prevImg.classList.remove("is-active");
      state.artFlip = !state.artFlip;
      try {
        document.documentElement.dispatchEvent(new CustomEvent("tb:art-update"));
      } catch (err) {
        /* old browsers */
      }
      window.setTimeout(() => maybeHandleDeadCover(videoId, nextImg), 0);
    };

    if (nextImg.src === url && nextImg.complete) {
      activate();
    } else {
      nextImg.onload = activate;
      nextImg.onerror = activate;
      nextImg.src = url;
    }

    const nextWash = state.washFlip ? el.washA : el.washB;
    const prevWash = state.washFlip ? el.washB : el.washA;
    const coverCss = `url("${url}")`;
    if (el.atmosphere) el.atmosphere.style.setProperty("--cover-url", coverCss);
    nextWash.style.backgroundImage = coverCss;
    nextWash.classList.add("is-visible");
    prevWash.classList.remove("is-visible");
    if (el.coverA && el.coverB) {
      const nextCover = state.washFlip ? el.coverA : el.coverB;
      const prevCover = state.washFlip ? el.coverB : el.coverA;
      nextCover.style.backgroundImage = coverCss;
      nextCover.classList.add("is-visible");
      prevCover.classList.remove("is-visible");
    }
    state.washFlip = !state.washFlip;
  }

  let deadCoverSkipStreak = 0;
  let pendingUnplayableSkip = null;

  function isSilentSkipReason(reason) {
    return reason === "dead_cover" || reason === "dead_track";
  }

  function isDeadCoverImage(img) {
    if (!img) return true;
    if (!img.complete) return false;
    if (!img.naturalWidth || !img.naturalHeight) return true;
    return (
      img.naturalWidth <= DEAD_COVER_PLACEHOLDER_MAX_W &&
      img.naturalHeight <= DEAD_COVER_PLACEHOLDER_MAX_H
    );
  }

  function flagDeadCover(videoId, reason) {
    if (!videoId) return;
    logEvent("dead_cover", {
      video_id: videoId,
      reason: reason || "thumb_unavailable",
      dead_cover: true,
    });
  }

  function drainPendingUnplayableSkip() {
    const pending = pendingUnplayableSkip;
    if (!pending) return;
    if (state.navLock.busy || state.loadingQueue) return;
    const cur = currentTrack();
    if (!cur || cur.video_id !== pending.videoId) {
      pendingUnplayableSkip = null;
      return;
    }
    pendingUnplayableSkip = null;
    requestSkipUnplayable(pending.reason || "dead_cover", pending.videoId);
  }

  function requestSkipUnplayable(reason, videoId) {
    const id = videoId || (currentTrack() && currentTrack().video_id);
    if (!id) return;
    if (deadCoverSkipStreak >= DEAD_COVER_MAX_SKIPS) {
      console.warn("[nav] unplayable skip cap reached");
      return;
    }
    if (state.navLock.busy || state.loadingQueue) {
      pendingUnplayableSkip = { videoId: id, reason: reason || "dead_track" };
      return;
    }
    deadCoverSkipStreak += 1;
    if (reason === "dead_cover") {
      flagDeadCover(id, "placeholder_or_error");
    } else {
      logEvent("dead_track", { video_id: id, reason: reason || "unplayable" });
    }
    advanceTrack(1, reason === "dead_cover" ? "dead_cover" : "dead_track");
  }

  function maybeHandleDeadCover(videoId, img) {
    if (!videoId || !isDeadCoverImage(img)) {
      if (videoId && img && img.complete && img.naturalWidth > DEAD_COVER_PLACEHOLDER_MAX_W) {
        deadCoverSkipStreak = 0;
      }
      return;
    }
    requestSkipUnplayable("dead_cover", videoId);
  }

  function videoIdFromAudioSrc(src) {
    if (!src) return null;
    const s = String(src);
    /* Primary local path: /api/audio/<11-char id> (no file extension). */
    let m = s.match(/\/api\/audio\/([a-zA-Z0-9_-]{11})(?:[/?#]|$)/);
    if (m) return m[1];
    m =
      s.match(/\/([a-zA-Z0-9_-]{11})\.[a-zA-Z0-9]+(?:[?#]|$)/) ||
      s.match(/[?&]video_id=([a-zA-Z0-9_-]{11})(?:[&]|$)/);
    return m ? m[1] : null;
  }

  function heardVideoId() {
    if (state.audioMode === "local") {
      const a = activeAudio();
      return videoIdFromAudioSrc(a && a.src);
    }
    if (state.audioMode === "iframe" && state.player && typeof state.player.getVideoData === "function") {
      try {
        return state.player.getVideoData().video_id || null;
      } catch {
        return null;
      }
    }
    return null;
  }

  async function abortStaleLocalOverlap() {
    state.xfadeInProgress = false;
    const inactiveSlot = otherSlot(state.activeSlot);
    const inactive = audioEl(inactiveSlot);
    if (inactive) {
      try {
        inactive.pause();
        inactive.volume = 0;
      } catch {
        /* ignore */
      }
    }
    const active = activeAudio();
    if (active) {
      try {
        active.volume = 1;
      } catch {
        /* ignore */
      }
    }
    if (state.polish && typeof state.polish.setActiveSlot === "function") {
      state.polish.setActiveSlot(state.activeSlot, 0);
    }
  }

  async function ensureHeardMatchesTrack(track, shouldPlay) {
    if (!track || !track.video_id || !shouldPlay) return true;
    const heard = heardVideoId();
    if (heard === track.video_id) return true;
    /* Either slot already holding this id (parser miss or mid-swap) — do not restart. */
    if (
      state.audioMode === "local" &&
      (hostHasVideoId(el.audioA, track.video_id) || hostHasVideoId(el.audioB, track.video_id))
    ) {
      const a = activeAudio();
      if (a && hostHasVideoId(a, track.video_id) && !a.paused) return true;
      if (a && hostHasVideoId(a, track.video_id)) {
        try {
          await a.play();
          setPlayingUI(true);
          return true;
        } catch {
          /* fall through */
        }
      }
    }
    console.warn("[nav] audio desync — repairing", { heard, want: track.video_id });
    await abortStaleLocalOverlap();
    const url = await prepareLocalAudioRace(track.video_id, 4000, () => true);
    if (url) {
      const ok = await playViaLocalCold(track, url, { autoplay: true, fadeMs: FADE_MS });
      if (ok && heardVideoId() === track.video_id) return true;
    }
    await playViaIframe(track, { autoplay: true, fadeMs: FADE_MS, reason: "desync_repair" });
    return heardVideoId() === track.video_id;
  }

  function setPlayingUI(playing, { force = false } = {}) {
    const next = Boolean(playing);
    // During track handoff keep the pause glyph — never flash "play" mid-crossfade.
    if (!next && state.transitioning && !force) return;
    if (next && !state.playing) startListenSegment();
    if (!next && state.playing) flushListenSegment();
    state.playing = next;
    el.artBtn.classList.toggle("is-playing", next);
    el.artBtn.classList.toggle("is-paused", !next);
    el.artBtn.setAttribute("aria-label", next ? "Pause current track" : "Play current track");
    // Tip only on the central glyph — not the whole vinyl / art button
    const tipHost = el.playGlyph || el.artBtn;
    tipHost.setAttribute("data-tip", next ? "Pause current track" : "Play current track");
    if (next && state.polishCanHear) startCompressMeterLoop();
    else stopCompressMeterLoop();
    el.artBtn.removeAttribute("data-tip");
  }

  function fadeElementVolume(audio, from, to, ms) {
    return new Promise((resolve) => {
      if (!audio || state.reducedMotion || ms <= 0) {
        if (audio) audio.volume = Math.max(0, Math.min(1, to));
        resolve();
        return;
      }
      const start = performance.now();
      const fromV = Math.max(0, Math.min(1, from));
      const toV = Math.max(0, Math.min(1, to));
      const step = (now) => {
        const t = Math.min(1, (now - start) / ms);
        const eased = 1 - Math.pow(1 - t, 2.4);
        audio.volume = fromV + (toV - fromV) * eased;
        if (t < 1) requestAnimationFrame(step);
        else resolve();
      };
      requestAnimationFrame(step);
    });
  }

  /* --- volume (YT 0–100 or <audio> 0–1) --- */
  function setVolumeSafe(vol) {
    const v = Math.max(0, Math.min(100, vol));
    if (state.audioMode === "local") {
      const a = activeAudio();
      if (a) a.volume = v / 100;
      return;
    }
    if (!state.player || typeof state.player.setVolume !== "function") return;
    try {
      state.player.setVolume(v);
    } catch {
      /* embed may not be ready */
    }
  }

  function getVolumeSafe() {
    if (state.audioMode === "local") {
      const a = activeAudio();
      return a ? Math.round((a.volume || 0) * 100) : VOLUME_DEFAULT;
    }
    if (state.player && typeof state.player.getVolume === "function") {
      try {
        return state.player.getVolume();
      } catch {
        return VOLUME_DEFAULT;
      }
    }
    return VOLUME_DEFAULT;
  }

  function fadeVolume(from, to, ms) {
    return new Promise((resolve) => {
      if (state.reducedMotion || ms <= 0) {
        setVolumeSafe(to);
        resolve();
        return;
      }
      const start = performance.now();
      const step = (now) => {
        const t = Math.min(1, (now - start) / ms);
        const eased = 1 - Math.pow(1 - t, 2.4);
        setVolumeSafe(from + (to - from) * eased);
        if (t < 1) {
          requestAnimationFrame(step);
        } else {
          resolve();
        }
      };
      requestAnimationFrame(step);
    });
  }

  function pauseIframe() {
    if (!state.player) return;
    try {
      if (typeof state.player.pauseVideo === "function") state.player.pauseVideo();
      if (typeof state.player.mute === "function") state.player.mute();
      if (typeof state.player.setVolume === "function") state.player.setVolume(0);
    } catch {
      /* ignore */
    }
  }

  function stopLocalSlot(slot) {
    const a = audioEl(slot);
    if (!a) return;
    try {
      a.pause();
      a.removeAttribute("src");
      a.load();
    } catch {
      /* ignore */
    }
  }

  function stopLocalAudio() {
    stopLocalSlot("a");
    stopLocalSlot("b");
    resetSlotPreload();
    state.prefetchGen += 1;
  }

  function ensurePolishConnected() {
    if (!state.polish) return false;
    if (!el.audioA || !el.audioB) return false;

    // Already dual-wired — never re-snap gains (cancels in-flight crossfade ramps).
    if (state.polishConnected && state.polishDual) {
      if (typeof state.polish.setAmount === "function") {
        state.polish.setAmount(state.polishAmount);
      }
      return true;
    }

    // Always prefer dual — single-host cannot do true A↔B graph overlap.
    if (typeof state.polish.connectDualMedia === "function") {
      const dual = state.polish.connectDualMedia(el.audioA, el.audioB);
      if (dual && dual.ok) {
        state.polishConnected = true;
        state.polishDual = true;
        /* Snap only on first successful wire — not during xfade / re-entry. */
        if (
          !state.xfadeInProgress &&
          typeof state.polish.setActiveSlot === "function"
        ) {
          state.polish.setActiveSlot(state.activeSlot, 0);
        }
        if (typeof state.polish.setAmount === "function") {
          state.polish.setAmount(state.polishAmount);
        }
        return true;
      }
      if (dual && dual.reason) {
        console.warn("polish dual connect failed", dual.reason);
      }
    }

    // Legacy single-host fallback (no true graph overlap)
    if (!state.polishConnected) {
      const result = state.polish.connectMediaElement(el.audioA);
      state.polishConnected = Boolean(result && result.ok);
      state.polishDual = false;
      if (!state.polishConnected) {
        console.warn("polish connect failed", result && result.reason);
      }
    }
    if (state.polishConnected && state.polish && typeof state.polish.setAmount === "function") {
      state.polish.setAmount(state.polishAmount);
    }
    return state.polishConnected;
  }

  function setPolishHearable(canHear) {
    state.polishCanHear = Boolean(canHear);
    if (el.level) {
      el.level.classList.toggle("is-unavailable", !state.polishCanHear);
      el.level.setAttribute(
        "data-tip",
        state.polishCanHear
          ? "Hold And Drag Sideways To Compress"
          : "Compressor Needs Local Audio"
      );
    }
    if (state.polishCanHear && state.playing) startCompressMeterLoop();
    else if (!state.polishCanHear) {
      stopCompressMeterLoop();
      syncCompressUI();
    }
  }

  async function restartCurrentTrack(reason = "loop") {
    const track = currentTrack();
    if (!track) return;
    logEvent("loop", { reason });
    if (state.audioMode === "local") {
      const a = activeAudio();
      if (a) {
        try {
          a.currentTime = 0;
          await a.play();
          setPlayingUI(true);
          markTrackStart();
          return;
        } catch {
          /* fall through */
        }
      }
    }
    if (state.audioMode === "iframe" && state.player) {
      try {
        if (typeof state.player.seekTo === "function") state.player.seekTo(0, true);
        if (typeof state.player.playVideo === "function") state.player.playVideo();
        setPlayingUI(true);
        markTrackStart();
        return;
      } catch {
        /* fall through */
      }
    }
    await loadTrack(state.index, { autoplay: true, reason: "loop" });
  }

  function clearStylePending() {
    state.pendingGenreId = null;
    state.pendingPhase = null;
    state.pendingPrefetch = null;
    state.navQueued = null;
    if (state.pendingTimer) {
      window.clearTimeout(state.pendingTimer);
      state.pendingTimer = 0;
    }
  }

  function pendingChipLabel() {
    if (state.pendingPhase === "change_now") return "CHANGE NOW?";
    return "NEXT UP";
  }

  function armStylePending(genreId) {
    clearStylePending();
    state.pendingGenreId = genreId;
    state.pendingPhase = "up_next";
    syncChipActive();
    state.pendingTimer = window.setTimeout(() => {
      if (state.pendingGenreId !== genreId) return;
      state.pendingPhase = "change_now";
      syncChipActive();
    }, PENDING_EVOLVE_MS);

    const gen = genreId;
    requestQueuePage(genreId, null)
      .then((data) => {
        if (state.pendingGenreId === gen) state.pendingPrefetch = data;
      })
      .catch(() => {});
  }

  async function commitStylePending() {
    const genreId = state.pendingGenreId;
    if (!genreId || state.loadingQueue || state.pendingCommit) return;
    const token = ++state.stationGen;
    const keepPlaying = state.playing;
    const cached = state.pendingPrefetch;
    state.pendingCommit = true;
    clearStylePending();
    resetLoopOnTrackChange("station");
    logEvent("station_change", { from: state.genreId, to: genreId, deferred: true });

    state.loadingQueue = true;
    el.artBtn.classList.add("is-loading");
    syncNavControls();
    try {
      let data =
        cached && Array.isArray(cached.tracks)
          ? cached
          : await requestQueuePage(genreId, null, {
              warm:
                genreId === DEFAULT_STATION &&
                state.tierId === DEFAULT_TIER &&
                !hasExperimentalQueueFilters(),
            });
      if (token !== state.stationGen) return;

      state.queue = filterNotFit(data.tracks || [], genreId);
      state.genreId = genreId;
      state.index = 0;
      if (data.warm) {
        state.nextCursor = null;
        state.hasMore = true;
      } else {
        state.nextCursor = data.next_cursor || null;
        state.hasMore = Boolean(data.has_more && state.nextCursor);
      }
      state.readyCache = Object.create(null);
      resetSlotPreload();
      state.prefetchGen += 1;
      syncChipActive();
      syncTierActive();
      syncLicenseActive();

      if (!keepPlaying) {
        stopLocalAudio();
        pauseIframe();
        state.audioMode = null;
        state.activeSlot = "a";
        if (state.polish && typeof state.polish.setActiveSlot === "function") {
          state.polish.setActiveSlot("a");
        }
        setPolishHearable(false);
      }

      if (!state.queue.length) return;

      if (keepPlaying) {
        if (state.navLock.busy) forceReleaseNavLock("station");
        await loadTrack(0, { autoplay: true, reason: "station" });
      } else {
        const track = currentTrack();
        if (track) {
          crossfadeArt(track.video_id);
          syncArtTitle();
          markTrackStart();
          setPlayingUI(false);
          prefetchLocalAudio(track.video_id);
          if (state.player && typeof state.player.cueVideoById === "function") {
            try {
              if (typeof state.player.mute === "function") state.player.mute();
            } catch {
              /* ignore */
            }
            state.player.cueVideoById(track.video_id);
          }
        }
      }
      if (token !== state.stationGen) return;
      prefetchAhead(state.index);
      if (data.warm) refreshLiveQueueInBackground();
    } catch (err) {
      console.error(err);
    } finally {
      if (token !== state.stationGen) return;
      state.loadingQueue = false;
      el.artBtn.classList.remove("is-loading");
      state.pendingCommit = false;
      syncNavControls();
      window.setTimeout(() => drainNavQueue(), 0);
    }
  }

  /** Instant style switch — labels update immediately; queue/crossfade follow. */
  async function applyGenreNow(genreId) {
    if (!genreId) return;
    if (genreId === state.genreId && !state.loadingQueue && !state.pendingCommit) return;
    const token = ++state.stationGen;
    const from = state.genreId;

    const keepPlaying = state.playing;
    clearStylePending();
    state.genreId = genreId;
    syncChipActive();
    syncTierActive();
    syncLicenseActive();
    resetLoopOnTrackChange("station");
    logEvent("station_change", { from, to: genreId, deferred: false });

    state.pendingCommit = true;
    state.loadingQueue = true;
    el.artBtn.classList.add("is-loading");
    syncNavControls();
    try {
      const data = await requestQueuePage(genreId, null, {
        warm:
          genreId === DEFAULT_STATION &&
          state.tierId === DEFAULT_TIER &&
          !hasExperimentalQueueFilters(),
      });
      if (token !== state.stationGen) return;

      state.queue = filterNotFit(data.tracks || [], genreId);
      state.index = 0;
      if (data.warm) {
        state.nextCursor = null;
        state.hasMore = true;
      } else {
        state.nextCursor = data.next_cursor || null;
        state.hasMore = Boolean(data.has_more && state.nextCursor);
      }
      state.readyCache = Object.create(null);
      resetSlotPreload();
      state.prefetchGen += 1;
      syncChipActive();

      if (!keepPlaying) {
        stopLocalAudio();
        pauseIframe();
        state.audioMode = null;
        state.activeSlot = "a";
        if (state.polish && typeof state.polish.setActiveSlot === "function") {
          state.polish.setActiveSlot("a");
        }
        setPolishHearable(false);
      }

      if (!state.queue.length) return;

      if (keepPlaying) {
        if (state.navLock.busy) forceReleaseNavLock("station");
        await loadTrack(0, { autoplay: true, reason: "station" });
      } else {
        const track = currentTrack();
        if (track) {
          crossfadeArt(track.video_id);
          syncArtTitle();
          markTrackStart();
          setPlayingUI(false);
          prefetchLocalAudio(track.video_id);
          if (state.player && typeof state.player.cueVideoById === "function") {
            try {
              if (typeof state.player.mute === "function") state.player.mute();
            } catch {
              /* ignore */
            }
            state.player.cueVideoById(track.video_id);
          }
        }
      }
      if (token !== state.stationGen) return;
      prefetchAhead(state.index);
      if (data.warm) refreshLiveQueueInBackground();
    } catch (err) {
      console.error(err);
    } finally {
      if (token !== state.stationGen) return;
      state.loadingQueue = false;
      el.artBtn.classList.remove("is-loading");
      state.pendingCommit = false;
      syncNavControls();
      window.setTimeout(() => drainNavQueue(), 0);
    }
  }

  /**
   * Rebuild rotation for Views / Clearance without interrupting the current track.
   * Current stays at index 0; new matches fill "up next".
   */
  async function rebuildQueueKeepCurrent() {
    const current = currentTrack();
    state.loadingQueue = true;
    try {
      const data = await requestQueuePage(state.genreId, null);
      const raw = filterNotFit(data.tracks || [], state.genreId);
      let next = raw;
      if (current && current.video_id) {
        next = raw.filter((t) => t.video_id !== current.video_id);
        state.queue = [current, ...next];
        state.index = 0;
      } else {
        state.queue = next;
        state.index = 0;
      }
      state.nextCursor = data.next_cursor || null;
      state.hasMore = Boolean(data.has_more && state.nextCursor);
      prefetchAhead(state.index);
    } catch (err) {
      console.warn("deferred queue rebuild failed", err);
    } finally {
      state.loadingQueue = false;
      window.setTimeout(() => drainNavQueue(), 0);
    }
  }

  async function peekLocalReady(videoId) {
    if (!videoId) return null;
    if (state.localAudioTools && state.localAudioTools.ready === false) return null;
    if (state.readyCache[videoId]) return state.readyCache[videoId];
    try {
      const res = await fetch(`/api/audio/${encodeURIComponent(videoId)}/info`);
      const data = await res.json().catch(() => ({}));
      if (res.ok && data.ready) {
        const url = data.url || `/api/audio/${encodeURIComponent(videoId)}`;
        state.readyCache[videoId] = url;
        if (data.partial) {
          preloadDbg("[preload] partial ready", {
            video_id: videoId,
            bytes: data.bytes,
          });
        }
        return url;
      }
      if (data.error && state.xfadeExp.debug) {
        preloadDbg("[preload] cache pending", { video_id: videoId, error: data.error });
      }
    } catch {
      /* ignore */
    }
    return null;
  }

  function prefetchLocalAudio(videoId) {
    if (!videoId) return;
    if (state.localAudioTools && state.localAudioTools.ready === false) return;
    if (state.readyCache[videoId]) {
      scheduleInactivePreload(videoId);
      return;
    }
    // Non-blocking kick — don't tie up the browser on yt-dlp
    fetch(`/api/audio/${encodeURIComponent(videoId)}?kick=1`)
      .then(async (res) => {
        const data = await res.json().catch(() => ({}));
        if (data.ready) {
          state.readyCache[videoId] =
            data.url || `/api/audio/${encodeURIComponent(videoId)}`;
          scheduleInactivePreload(videoId);
        }
      })
      .catch(() => {});
  }

  /**
   * Prefer a brief wait for prefetch over a silent hard cut.
   * Polls /info after kick; never blocks on full yt-dlp prepare beyond ms.
   */
  async function prepareLocalAudioRace(videoId, ms = XFADE_READY_MS, isCurrent = null) {
    if (!videoId) return null;
    if (state.localAudioTools && state.localAudioTools.ready === false) return null;
    if (state.readyCache[videoId]) {
      scheduleInactivePreload(videoId);
      return state.readyCache[videoId];
    }

    prefetchLocalAudio(videoId);
    const deadline = Date.now() + Math.max(0, Number(ms) || 0);
    while (Date.now() < deadline) {
      if (isCurrent && !isCurrent()) {
        return state.readyCache[videoId] || null;
      }
      const url = state.readyCache[videoId] || (await peekLocalReady(videoId));
      if (url) {
        scheduleInactivePreload(videoId);
        return url;
      }
      await new Promise((r) => window.setTimeout(r, 120));
    }
    const finalUrl = state.readyCache[videoId] || (await peekLocalReady(videoId));
    if (finalUrl) scheduleInactivePreload(videoId);
    return finalUrl;
  }

  /** Absolute media URL for comparisons against audio.src. */
  function absAudioUrl(url) {
    try {
      return new URL(url, window.location.origin).href;
    } catch {
      return url;
    }
  }

  function hostHasVideoId(host, videoId) {
    if (!host || !host.src || !videoId) return false;
    return host.src.includes(videoId);
  }

  function bufferedAheadSec(audio) {
    if (!audio || !Number.isFinite(audio.currentTime)) return 0;
    try {
      const b = audio.buffered;
      if (!b || !b.length) return 0;
      const t = audio.currentTime;
      for (let i = 0; i < b.length; i++) {
        if (t >= b.start(i) && t <= b.end(i)) {
          return Math.max(0, b.end(i) - t);
        }
      }
      return Math.max(0, b.end(b.length - 1) - t);
    } catch {
      return 0;
    }
  }

  /** Enough PCM buffered to start overlap without a stall.
   *  Handoff is looser: a short head of audio + canplay is enough — the ~7s
   *  crossfade keeps downloading while A fades out. */
  function isMediaBuffered(audio, { handoff = false } = {}) {
    if (!audio) return false;
    if (audio.readyState >= 4) return true;
    if (handoff) {
      if (audio.readyState >= 3) return true;
      if (audio.readyState >= 2 && bufferedAheadSec(audio) >= 0.45) return true;
      if (audio.readyState >= 2 && bufferedAheadSec(audio) >= 0.2) return true;
      return false;
    }
    if (audio.readyState >= 3 && bufferedAheadSec(audio) >= 1.5) return true;
    if (audio.readyState >= 2 && bufferedAheadSec(audio) >= 3) return true;
    return false;
  }

  function resetSlotPreload() {
    state.slotPreload = {
      slot: null,
      videoId: null,
      url: null,
      buffered: false,
      primed: false,
    };
  }

  function syncNavControls() {
    const locked =
      state.navLock.busy || state.loadingQueue || state.transitioning || state.xfadeInProgress;
    [el.prev, el.next].forEach((btn) => {
      if (!btn) return;
      btn.classList.toggle("is-busy", locked);
      /* Never use HTML disabled — it blocks clicks needed for stuck recovery. */
      btn.removeAttribute("disabled");
      btn.setAttribute("aria-disabled", locked ? "true" : "false");
      btn.setAttribute("aria-busy", locked ? "true" : "false");
    });
    if (el.prev) {
      el.prev.setAttribute(
        "aria-label",
        locked ? "Skip to previous track, loading" : "Skip to previous track"
      );
    }
    if (el.next) {
      el.next.setAttribute(
        "aria-label",
        locked ? "Skip to next track, loading" : "Skip to next track"
      );
    }
  }

  /** Soft deadline around media.play() — hung play() promises were killing Next. */
  async function playHostWithTimeout(host, ms = 3500) {
    if (!host) return false;
    if (!host.paused) return true;
    try {
      await Promise.race([
        host.play(),
        new Promise((_, reject) => {
          window.setTimeout(() => reject(new Error("play_timeout")), Math.max(400, ms));
        }),
      ]);
    } catch (err) {
      console.warn("[nav] play timeout/blocked", err && err.message ? err.message : err);
    }
    return !host.paused;
  }

  function setVisualFadeMs(ms) {
    const m = state.reducedMotion ? 0 : Math.max(0, Number(ms) || ART_FADE_MS);
    document.documentElement.style.setProperty("--art-fade-ms", `${m}ms`);
    document.documentElement.style.setProperty("--title-fade-ms", `${m}ms`);
  }

  async function resumeAudioContext() {
    if (state.polish && typeof state.polish.resume === "function") {
      try {
        await state.polish.resume();
      } catch {
        /* gesture / policy */
      }
    }
  }

  /** Drop preload + timer state after handoff completes or aborts. */
  function clearHandoffState({ bumpPreload = true } = {}) {
    if (bumpPreload) state.prefetchGen += 1;
    resetSlotPreload();
    if (state.navLock.timer) {
      window.clearTimeout(state.navLock.timer);
      state.navLock.timer = 0;
    }
  }

  function beginNavLock() {
    const token = ++state.navLock.token;
    state.navLock.busy = true;
    state.navLock.startedAt = Date.now();
    state.transitioning = true;
    state.navHandoffTimedOut = false;
    syncNavControls();
    return token;
  }

  function releaseNavLock(token) {
    if (token != null && token !== state.navLock.token) return;
    if (!state.navLock.busy) return;
    if (state.navLock.timer) {
      window.clearTimeout(state.navLock.timer);
      state.navLock.timer = 0;
    }
    state.navLock.busy = false;
    state.transitioning = false;
    syncNavControls();
    window.setTimeout(() => {
      drainNavQueue();
      drainPendingUnplayableSkip();
    }, 0);
  }

  function forceReleaseNavLock(why = "stuck") {
    const token = state.navLock.token;
    console.warn("[nav] force-release", { why, token, held: Date.now() - state.navLock.startedAt });
    state.navHandoffTimedOut = true;
    state.xfadeInProgress = false;
    state.prepareGen += 1;
    /* Invalidate in-flight loadTrack token so a late commit cannot race a new skip. */
    state.navLock.token += 1;
    state.navQueued = null;
    clearHandoffState({ bumpPreload: true });
    abortStaleLocalOverlap().catch(() => {});
    if (state.navLock.timer) {
      window.clearTimeout(state.navLock.timer);
      state.navLock.timer = 0;
    }
    state.navLock.busy = false;
    state.transitioning = false;
    syncNavControls();
    window.setTimeout(() => {
      drainNavQueue();
      drainPendingUnplayableSkip();
    }, 0);
  }

  function navLockHeldMs() {
    if (!state.navLock.busy || !state.navLock.startedAt) return 0;
    return Date.now() - state.navLock.startedAt;
  }

  function requestSkip(direction, reason) {
    resumeAudioContext().catch(() => {});
    if (!state.queue.length || state.loadingQueue) return;
    if (state.navLock.busy) {
      const held = navLockHeldMs();
      /* Stuck recovery: after NAV_STUCK_MS (or mid-xfade overshoot), free the lock
         so Next always works. Coalesce earlier clicks into one queued skip. */
      const xfadeHold = getEffectiveXfadeMs() + 2000;
      if (held >= NAV_STUCK_MS || (state.xfadeInProgress && held >= xfadeHold)) {
        forceReleaseNavLock(state.xfadeInProgress ? "stuck_xfade" : "stuck_click");
      } else {
        queueNavWhileBusy(direction, reason);
        return;
      }
    }
    if (direction > 0) {
      advanceTrack(1, reason || "next");
    } else {
      const nextIdx = nextPlayableIndex(state.index, -1);
      loadTrack(nextIdx, { autoplay: true, reason: reason || "prev" });
    }
  }

  function navReasonQueues(reason) {
    return [
      "next",
      "prev",
      "skip",
      "ended",
      "error",
      "not_fit",
      "nav",
      "dead_cover",
      "dead_track",
    ].includes(reason);
  }

  function queueNavWhileBusy(direction, reason) {
    // Only coalesce explicit skip intent — never chain auto ended/error through handoff.
    if (reason === "ended" || reason === "error") return;
    state.navQueued = { direction, reason };
  }

  function drainNavQueue() {
    const q = state.navQueued;
    if (!q || state.navLock.busy) return;
    state.navQueued = null;
    if (q.direction > 0) {
      advanceTrack(1, q.reason || "next");
    } else if (state.queue.length) {
      const nextIdx = nextPlayableIndex(state.index, -1);
      loadTrack(nextIdx, { autoplay: true, reason: q.reason || "prev" });
    }
  }

  function isHandoffStale(navToken, prepareGen) {
    return navToken !== state.navLock.token || prepareGen !== state.prepareGen;
  }

  function clearNavHandoffTimer() {
    if (state.navLock.timer) {
      window.clearTimeout(state.navLock.timer);
      state.navLock.timer = 0;
    }
  }

  function startNavHandoffTimer(navToken, prepareGen, timeoutMs, onTimeout) {
    clearNavHandoffTimer();
    const ms = Math.max(2000, Number(timeoutMs) || NAV_HANDOFF_PREP_MS);
    state.navLock.timer = window.setTimeout(() => {
      if (navToken !== state.navLock.token || prepareGen !== state.prepareGen) return;
      if (state.xfadeInProgress) {
        /* Overlap already audible — extend once, then force-clear if still stuck. */
        console.info("[nav] handoff timeout deferred — xfade in progress");
        state.navLock.timer = window.setTimeout(() => {
          if (navToken !== state.navLock.token || prepareGen !== state.prepareGen) return;
          if (state.xfadeInProgress) {
            console.warn("[nav] xfade stuck past deferred window — force recovery");
            state.xfadeInProgress = false;
            abortStaleLocalOverlap().catch(() => {});
          }
          state.navHandoffTimedOut = true;
          clearHandoffState({ bumpPreload: true });
          onTimeout();
        }, Math.max(getEffectiveXfadeMs(), 4000) + 800);
        return;
      }
      state.navHandoffTimedOut = true;
      clearHandoffState({ bumpPreload: true });
      console.warn("[nav] handoff timeout — forcing recovery", {
        ms: Date.now() - state.navLock.startedAt,
        index: state.index,
        budget_ms: ms,
      });
      onTimeout();
    }, ms);
  }

  /** Safety net while A↔B overlap runs (prep timer is cleared at overlap start). */
  function armXfadeWatchdog(navToken, fadeMs) {
    const ms = Math.max(800, Number(fadeMs) || getEffectiveXfadeMs()) + 1800;
    window.setTimeout(() => {
      if (navToken != null && navToken !== state.navLock.token) return;
      if (!state.xfadeInProgress) return;
      console.warn("[xfade] watchdog — clearing stuck xfadeInProgress", { ms });
      state.xfadeInProgress = false;
    }, ms);
  }

  /** True when inactive slot holds the intended track and is buffered. */
  function isHotPreloadValid(videoId, slotHint = null) {
    const pre = state.slotPreload;
    if (!videoId || !pre.videoId || pre.videoId !== videoId) return false;
    if (!pre.slot || !pre.buffered) return false;
    if (slotHint && pre.slot !== slotHint) return false;
    const host = audioEl(pre.slot);
    return hostHasVideoId(host, videoId);
  }

  function invalidateStalePreload(forVideoId) {
    if (isHotPreloadValid(forVideoId)) return false;
    if (!state.slotPreload.videoId && !state.slotPreload.slot) return false;
    state.prefetchGen += 1;
    resetSlotPreload();
    return true;
  }

  async function waitMediaReady(audio, ms = 6000, { handoff = false, isCurrent = null } = {}) {
    if (!audio) return false;
    if (isMediaBuffered(audio, { handoff })) return true;
    return new Promise((resolve) => {
      let done = false;
      let iv = 0;
      const finish = (ok) => {
        if (done) return;
        done = true;
        if (iv) window.clearInterval(iv);
        audio.removeEventListener("canplaythrough", onReady);
        audio.removeEventListener("canplay", onProgress);
        audio.removeEventListener("progress", onProgress);
        audio.removeEventListener("error", onErr);
        resolve(ok);
      };
      const check = () => isMediaBuffered(audio, { handoff });
      const onReady = () => finish(check());
      const onProgress = () => {
        if (check()) finish(true);
      };
      const onErr = () => finish(false);
      audio.addEventListener("canplaythrough", onReady);
      audio.addEventListener("canplay", onProgress);
      audio.addEventListener("progress", onProgress);
      audio.addEventListener("error", onErr);
      iv = window.setInterval(() => {
        if (isCurrent && !isCurrent()) {
          finish(check());
          return;
        }
        if (check()) finish(true);
      }, 120);
      window.setTimeout(() => finish(check()), ms);
    });
  }

  /** Start inactive decode at graph gain ε while current track plays. */
  async function primeInactiveSlot(slot) {
    const host = audioEl(slot);
    if (!host || !host.src) return false;
    if (state.audioMode !== "local" || !state.polishConnected || !state.polishDual) {
      return false;
    }
    /* Never prime during an active overlap — would fight the ramp. */
    if (state.xfadeInProgress) return false;
    ensurePolishConnected();
    /* Element volume unity; graph gain on inactive stays at ε until crossfadeTo. */
    host.volume = 1;
    if (!host.paused) {
      state.slotPreload.primed = true;
      return true;
    }
    try {
      await host.play();
      state.slotPreload.primed = true;
      preloadDbg("[preload] primed", {
        slot,
        video_id: state.slotPreload.videoId,
      });
      return true;
    } catch (err) {
      console.warn("[preload] prime blocked", err);
      return false;
    }
  }

  /**
   * Load next queue item into the inactive host, wait for buffer, then silently
   * play (graph gain ε) so crossfade hears PCM immediately — no startup gap.
   */
  async function preloadIntoInactive(videoId, url, gen = null) {
    if (!videoId || !url || !el.audioA || !el.audioB) return false;
    const next = neighborTrack(1);
    if (!next || next.video_id !== videoId) return false;

    const slot = otherSlot(state.activeSlot);
    const host = audioEl(slot);
    if (!host) return false;

    const checkGen = gen != null ? gen : state.prefetchGen;
    const abs = absAudioUrl(url);

    if (state.slotPreload.videoId && state.slotPreload.videoId !== videoId) {
      resetSlotPreload();
    }

    if (isHotPreloadValid(videoId, slot)) {
      if (!state.slotPreload.primed && state.audioMode === "local" && state.playing) {
        await primeInactiveSlot(slot);
      }
      return true;
    }

    try {
      if (!hostHasVideoId(host, videoId) || host.src !== abs) {
        host.preload = "auto";
        host.src = url;
        host.load();
      }
    } catch {
      return false;
    }

    state.slotPreload = {
      slot,
      videoId,
      url,
      buffered: false,
      primed: false,
    };

    applyIncomingStartOffset(host);
    const ready = await waitMediaReady(host, 14000, { handoff: true });
    if (gen != null && checkGen !== state.prefetchGen) return false;
    if (!ready) {
      console.warn("[preload] buffer timeout", videoId);
      return false;
    }

    state.slotPreload.buffered = true;
    preloadDbg("[preload] ready", {
      slot,
      video_id: videoId,
      ahead_sec: Math.round(bufferedAheadSec(host) * 10) / 10,
      start_sec: getXfadeStartSec(),
    });

    if (state.audioMode === "local" && state.playing) {
      await primeInactiveSlot(slot);
    }
    return true;
  }

  /** Kick server cache + buffer/prime next track into inactive host. */
  function scheduleInactivePreload(forVideoId = null, { force = false } = {}) {
    if (!force && !xfadePreloadAllowsBackground()) return;
    const next = neighborTrack(1);
    if (!next || !next.video_id) return;
    const targetId = forVideoId || next.video_id;
    if (next.video_id !== targetId) return;

    if (state.slotPreload.videoId && state.slotPreload.videoId !== targetId) {
      state.prefetchGen += 1;
      resetSlotPreload();
    }

    const gen = ++state.prefetchGen;
    (async () => {
      let url = state.readyCache[targetId];
      if (!url) url = await peekLocalReady(targetId);
      if (!url) {
        prefetchLocalAudio(targetId);
        const deadline = Date.now() + 45000;
        while (Date.now() < deadline && gen === state.prefetchGen) {
          url = state.readyCache[targetId] || (await peekLocalReady(targetId));
          if (url) break;
          await new Promise((r) => window.setTimeout(r, 250));
        }
      }
      if (!url || gen !== state.prefetchGen) return;
      await preloadIntoInactive(targetId, url, gen);
    })();
  }

  /** Ensure slot has url buffered enough for overlap (uses preload cache when hot). */
  async function ensureSlotBuffered(slot, url, ms = 4500) {
    const host = audioEl(slot);
    if (!host || !url) return false;
    const abs = absAudioUrl(url);
    const pre = state.slotPreload;
    const videoId = pre.videoId || (url.match(/\/api\/audio\/([^/?#]+)/) || [])[1];
    if (
      pre.slot === slot &&
      pre.url &&
      absAudioUrl(pre.url) === abs &&
      pre.buffered &&
      isHotPreloadValid(videoId, slot) &&
      isMediaBuffered(host, { handoff: true })
    ) {
      if (!pre.primed && state.audioMode === "local") {
        await primeInactiveSlot(slot);
      }
      return true;
    }
    try {
      if (host.src !== abs) {
        host.preload = "auto";
        host.src = url;
        host.load();
      }
    } catch {
      return false;
    }
    applyIncomingStartOffset(host);
    return waitMediaReady(host, ms, { handoff: true });
  }

  /** Poll until local file ready, then swap iframe → polish local (same track). */
  function promoteToLocalWhenReady(track, prepareGen) {
    if (!track || !track.video_id) return;
    const vid = track.video_id;
    let attempts = 0;
    const maxAttempts = 60; // ~60 * 350ms ≈ 21s

    const tick = async () => {
      if (prepareGen !== state.prepareGen) return;
      const cur = currentTrack();
      if (!cur || cur.video_id !== vid) return;

      attempts += 1;
      let url = state.readyCache[vid] || (await peekLocalReady(vid));
      if (!url && attempts <= 3) {
        fetch(`/api/audio/${encodeURIComponent(vid)}?kick=1`).catch(() => {});
      }
      if (!url) {
        if (attempts < maxAttempts) {
          window.setTimeout(tick, 350);
        }
        return;
      }

      state.readyCache[vid] = url;
      if (state.audioMode === "local") return;

      const wantPlay = state.playing || state.audioMode === "iframe";
      const ok = await playViaLocalCold(track, url, {
        autoplay: wantPlay,
        fadeMs: state.reducedMotion ? 0 : FADE_MS,
      });
      if (ok) logEvent("promote_local", { video_id: vid });
    };

    window.setTimeout(tick, 120);
  }

  function maybeKickInactivePreload(force = false) {
    if (!force && !xfadePreloadAllowsBackground()) return;
    const now = Date.now();
    if (!force && now - state.preloadKickAt < PRELOAD_KICK_THROTTLE_MS) return;
    state.preloadKickAt = now;
    scheduleInactivePreload(null, { force });
  }

  /** Kick /api/audio for queue items ahead of the play head (non-blocking). */
  function kickQueueAudioPrefetch(fromIndex, count = PREFETCH_AUDIO_AHEAD) {
    const n = state.queue.length;
    const base = typeof fromIndex === "number" ? fromIndex : state.index;
    for (let step = 0; step < count; step++) {
      const i = base + step;
      if (i >= n) break;
      const t = state.queue[i];
      if (t && t.video_id && !isNotFit(t.video_id)) {
        prefetchLocalAudio(t.video_id);
        prefetchThumb(t.video_id);
      }
    }
  }

  function prefetchAhead(fromIndex) {
    const base = typeof fromIndex === "number" ? fromIndex : state.index;
    kickQueueAudioPrefetch(base + 1, PREFETCH_AUDIO_AHEAD);
    /* Prev neighbor when known (history in queue). */
    for (let step = 1; step <= 2; step++) {
      const i = base - step;
      if (i < 0) break;
      const t = state.queue[i];
      if (t && t.video_id && !isNotFit(t.video_id)) {
        prefetchThumb(t.video_id);
      }
    }
    syncNeighborThumbs(base);
    maybeKickInactivePreload(true);
  }

  function neighborTrack(direction, fromIndex) {
    if (!state.queue.length) return null;
    const base = typeof fromIndex === "number" ? fromIndex : state.index;
    const idx = nextPlayableIndex(base, direction);
    if (idx === base) return null;
    return state.queue[idx] || null;
  }

  function setCtrlThumb(img, track) {
    if (!img) return;
    const wrap = img.closest(".ctrl__thumb-wrap");
    if (!track || !track.video_id) {
      img.removeAttribute("src");
      if (wrap) wrap.classList.remove("is-ready");
      return;
    }
    const url = thumbUrl(track.video_id);
    if (img.getAttribute("src") === url) {
      if (wrap) wrap.classList.add("is-ready");
      return;
    }
    const onReady = () => {
      if (wrap) wrap.classList.add("is-ready");
    };
    img.onload = onReady;
    img.onerror = () => {
      img.removeAttribute("src");
      if (wrap) wrap.classList.remove("is-ready");
    };
    if (wrap) wrap.classList.remove("is-ready");
    img.src = url;
    if (img.complete && img.naturalWidth) onReady();
  }

  function syncNeighborThumbs(fromIndex) {
    const base = typeof fromIndex === "number" ? fromIndex : state.index;
    const prev = neighborTrack(-1, base);
    const next = neighborTrack(1, base);
    setCtrlThumb(el.prevThumb, prev);
    setCtrlThumb(el.nextThumb, next);
    if (prev && prev.video_id) prefetchThumb(prev.video_id);
    if (next && next.video_id) prefetchThumb(next.video_id);
  }

  function wireLocalAudioEvents() {
    ["a", "b"].forEach((slot) => {
      const host = audioEl(slot);
      if (!host || host.dataset.wired === "1") return;
      host.dataset.wired = "1";
      host.dataset.slot = slot;

      host.addEventListener("ended", () => {
        if (state.audioMode !== "local") return;
        if (slot !== state.activeSlot) return;
        // Outgoing track ended while handoff already in flight — drop stale auto-advance.
        if (state.navLock.busy || state.transitioning || state.loadingQueue) return;
        if (!state.playing) return;
        if (state.loopTrack) {
          restartCurrentTrack("loop");
          return;
        }
        logEvent("ended");
        advanceTrack(1, "ended");
      });

      host.addEventListener("play", () => {
        if (state.audioMode !== "local") return;
        if (slot !== state.activeSlot && !state.transitioning) return;
        setPlayingUI(true);
        if (state.polish && typeof state.polish.resume === "function") {
          state.polish.resume().catch(() => {});
        }
        if (slot === state.activeSlot && state.playing) {
          kickQueueAudioPrefetch(state.index + 1, PREFETCH_AUDIO_AHEAD);
          maybeKickInactivePreload(true);
        }
      });

      host.addEventListener("timeupdate", () => {
        if (state.audioMode !== "local") return;
        if (slot !== state.activeSlot || !state.playing) return;
        const dur = host.duration;
        const cur = host.currentTime;
        if (!Number.isFinite(dur) || dur <= 0) {
          maybeKickInactivePreload();
          return;
        }
        const remaining = dur - cur;
        const leadSec =
          state.xfadeExp.preload === "early" ? dur : PRELOAD_LEAD_SEC;
        if (cur < 10 || remaining <= leadSec) {
          maybeKickInactivePreload();
        }
      });

      host.addEventListener("pause", () => {
        if (state.audioMode !== "local") return;
        if (state.transitioning) return;
        if (slot !== state.activeSlot) return;
        setPlayingUI(false);
      });

      host.addEventListener("error", () => {
        if (state.audioMode !== "local" || state.transitioning) return;
        if (slot !== state.activeSlot) return;
        logEvent("local_audio_error");
        const track = currentTrack();
        if (!track) return;
        const vid = track.video_id;
        playViaIframe(track, { autoplay: true, fadeMs: 0, reason: "local_error" }).then(() => {
          window.setTimeout(() => {
            if (currentTrack()?.video_id !== vid) return;
            if (state.audioMode !== "iframe") return;
            try {
              if (state.player && typeof state.player.getPlayerState === "function") {
                const st = state.player.getPlayerState();
                if (st === YT.PlayerState.UNSTARTED && heardVideoId() !== vid) {
                  requestSkipUnplayable("dead_track", vid);
                }
              }
            } catch {
              /* ignore */
            }
          }, 2200);
        });
      });
    });
  }

  /**
   * True overlapping crossfade: start inactive slot while prev still audible
   * (~CROSSFADE_MS), then park prev. Graph gains when dual connected; else
   * parallel element-volume fades (both tracks audible mid-overlap).
   */
  async function crossfadeToLocal(track, url, { autoplay = true } = {}) {
    if (!track || !track.video_id || !url) return false;
    await resumeAudioContext();
    ensurePolishConnected();
    if (!state.polishConnected) return false;

    // Stay visually "playing" for the whole handoff.
    if (autoplay) setPlayingUI(true);

    pauseIframe();
    setPolishHearable(true);
    state.audioMode = "local";

    const fromSlot = state.activeSlot;
    const toSlot = otherSlot(fromSlot);
    const prev = audioEl(fromSlot);
    const next = audioEl(toSlot);

    if (!prev || !next) return false;

    // Keep prev audible — never pause/replace until after the overlap.
    if (autoplay && prev.paused) {
      const resumed = await playHostWithTimeout(prev, 2800);
      if (!resumed) {
        console.warn("crossfade resume prev blocked");
        return false;
      }
    }
    if (autoplay && prev.paused) return false;

    let preloaded = isHotPreloadValid(track.video_id, toSlot);
    if (preloaded && !hostHasVideoId(next, track.video_id)) {
      console.warn("[xfade] stale preload — host drift", track.video_id);
      invalidateStalePreload(track.video_id);
      preloaded = false;
    }

    if (preloaded) {
      xfadeDbg("[xfade] using preloaded slot", {
        slot: toSlot,
        primed: state.slotPreload.primed,
        video_id: track.video_id,
      });
    }

    const fadePath = resolveXfadePath();
    const fadeMs = state.reducedMotion ? 0 : getEffectiveXfadeMs();

    if (xfadeRequirePreloaded() && !preloaded) {
      console.warn("[xfade] gate blocked — slot not preloaded", track.video_id);
      return false;
    }

    const buffered =
      preloaded ||
      (xfadeRequirePreloaded()
        ? false
        : await ensureSlotBuffered(
            toSlot,
            url,
            /* Start fade as soon as a short head is ready — rest fills during overlap. */
            Math.min(2800, Math.max(900, XFADE_READY_MS * 0.45))
          ));
    if (!buffered) {
      console.warn("[xfade] next slot not buffered", track.video_id);
      return false;
    }

    if (fadePath === "instant" || fadeMs <= 0) {
      const ready =
        preloaded ||
        (await ensureSlotBuffered(toSlot, url, xfadeRequirePreloaded() ? 2000 : 4500));
      if (!ready) {
        console.warn("[xfade] instant cut blocked — not buffered", track.video_id);
        return false;
      }
      if (next.paused) {
        const okPlay = await playHostWithTimeout(next, 2800);
        if (!okPlay) {
          console.warn("instant cut play blocked");
          return false;
        }
      }
      if (state.polish && typeof state.polish.setActiveSlot === "function") {
        state.polish.setActiveSlot(toSlot, 0);
      }
      state.activeSlot = toSlot;
      next.volume = 1;
      try {
        prev.pause();
        prev.currentTime = 0;
      } catch {
        /* ignore */
      }
      resetSlotPreload();
      setPlayingUI(true);
      console.info("[xfade] instant cut", { from: fromSlot, to: toSlot, video_id: track.video_id });
      if (xfadePreloadAllowsBackground()) scheduleInactivePreload();
      return true;
    }

    if (!autoplay) {
      if (state.polish && typeof state.polish.setActiveSlot === "function") {
        state.polish.setActiveSlot(toSlot, 0);
      }
      state.activeSlot = toSlot;
      try {
        prev.pause();
      } catch {
        /* ignore */
      }
      setPlayingUI(false, { force: true });
      return true;
    }

    ensurePolishConnected();
    const useGraphXfade =
      fadePath === "graph" &&
      state.polishDual &&
      state.polish &&
      typeof state.polish.crossfadeTo === "function";

    /* Keep inactive at graph ε until crossfadeTo ramps — stitch-era order.
       Do not re-enter ensurePolishConnected here (would be a no-op now, but
       historically snapped gains and killed the overlap). */
    if (state.polish && typeof state.polish.setActiveSlot === "function") {
      state.polish.setActiveSlot(fromSlot, 0);
    }

    prev.volume = 1;
    next.volume = useGraphXfade ? 1 : 0;

    /* Seek only while paused (never mid-play — silence gap). Primed hosts skip. */
    if (next.paused && getXfadeStartSec() > 0) {
      applyIncomingStartOffset(next, { force: true });
    }

    if (next.paused) {
      const okPlay = await playHostWithTimeout(next, 2800);
      if (!okPlay) {
        console.warn("crossfade play blocked");
        return false;
      }
    }
    if (next.paused) return false;

    setPlayingUI(true);
    if (state.polish && typeof state.polish.resume === "function") {
      await state.polish.resume().catch(() => {});
    }

    // Overlap is underway — prep timer must not iframe-fallback mid-fade.
    clearNavHandoffTimer();
    state.xfadeInProgress = true;
    syncNavControls();
    armXfadeWatchdog(state.navLock.token, fadeMs);

    console.info("[xfade] overlap active", {
      ms: fadeMs,
      from: fromSlot,
      to: toSlot,
      graph: useGraphXfade,
      path: fadePath,
      video_id: track.video_id,
    });
    xfadeDbg("[xfade] overlap detail", {
      mode: getXfadeModeDef().label,
      handoff: state.xfadeExp.handoffGate,
      preloaded,
    });

    try {
      if (useGraphXfade) {
        prev.volume = 1;
        next.volume = 1;
        if (state.polish && typeof state.polish.fadeMaster === "function") {
          state.polish.fadeMaster(1, 1);
        }
        await Promise.race([
          state.polish.crossfadeTo(toSlot, fadeMs),
          new Promise((resolve) => {
            window.setTimeout(() => resolve(false), fadeMs + 1200);
          }),
        ]);
        /* Confirm destination gains after ramp (stitch left this to crossfadeTo). */
        if (state.polish && typeof state.polish.setActiveSlot === "function") {
          state.polish.setActiveSlot(toSlot, 0);
        }
      } else {
        if (
          state.polish &&
          typeof state.polish.setGraphGainsPassthrough === "function"
        ) {
          state.polish.setGraphGainsPassthrough();
        }
        prev.volume = 1;
        next.volume = 0;
        await Promise.all([
          fadeElementVolume(prev, prev.volume || 1, 0, fadeMs),
          fadeElementVolume(next, 0, 1, fadeMs),
        ]);
        if (state.polish && typeof state.polish.setActiveSlot === "function") {
          state.polish.setActiveSlot(toSlot, 0);
        }
      }

      state.activeSlot = toSlot;
      resetSlotPreload();
      try {
        prev.pause();
        prev.currentTime = 0;
      } catch {
        /* ignore */
      }
      next.volume = 1;
      setPlayingUI(true);
      scheduleInactivePreload();
      return true;
    } finally {
      state.xfadeInProgress = false;
      syncNavControls();
    }
  }

  /** Cold start / non-overlap local play (first track, promote, or after iframe). */
  async function playViaLocalCold(
    track,
    url,
    { autoplay = true, fadeMs = FADE_MS, slot = null, keepPrevAlive = false } = {}
  ) {
    ensurePolishConnected();
    if (!state.polishConnected || !url) return false;

    pauseIframe();
    setPolishHearable(true);
    state.audioMode = "local";

    const fromSlot = state.activeSlot;
    const targetSlot = slot || fromSlot || "a";
    const audio = audioEl(targetSlot);
    const otherS = otherSlot(targetSlot);
    const other = audioEl(otherS);
    const abs = absAudioUrl(url);
    const inactiveHandoff = keepPrevAlive && targetSlot !== fromSlot && autoplay;
    const keepOther =
      keepPrevAlive ||
      inactiveHandoff ||
      (state.slotPreload.slot === otherS &&
        state.slotPreload.primed &&
        state.slotPreload.videoId);
    if (other !== audio && !keepOther) {
      try {
        other.pause();
      } catch {
        /* ignore */
      }
    }

    if (state.polish && typeof state.polish.setActiveSlot === "function") {
      state.polish.setActiveSlot(targetSlot, state.reducedMotion ? 0 : 40);
    }

    if (audio.src !== abs) {
      audio.src = url;
    }

    const ready = await waitMediaReady(audio, inactiveHandoff ? 4000 : 2500);
    if (!ready) return false;

    // Inactive-slot handoff: prev stays audible — crossfade instead of hard swap.
    if (inactiveHandoff && fromSlot !== targetSlot) {
      state.slotPreload = {
        slot: targetSlot,
        videoId: track.video_id,
        url,
        buffered: true,
        primed: !audio.paused,
      };
      const ok = await crossfadeToLocal(track, url, { autoplay });
      if (ok) return true;
      console.warn("[xfade] inactive cold handoff failed", track.video_id);
    }

    state.activeSlot = targetSlot;
    resetSlotPreload();
    audio.volume = 0;
    if (autoplay) {
      try {
        await audio.play();
      } catch (err) {
        console.warn("local play blocked", err);
        return false;
      }
      setPlayingUI(true);
      if (state.polish && typeof state.polish.resume === "function") {
        await state.polish.resume().catch(() => {});
      }
      if (state.polish && typeof state.polish.fadeMaster === "function") {
        await state.polish.fadeMaster(1, 1);
      }
      await fadeVolume(0, VOLUME_DEFAULT, fadeMs * 0.65);
      audio.volume = 1;
      scheduleInactivePreload();
    } else {
      audio.volume = 1;
      setPlayingUI(false, { force: true });
    }

    return true;
  }

  /**
   * Primary local path: keep outgoing PCM audible, buffer/prime inactive host,
   * then true A↔B graph overlap (~CROSSFADE_MS). Never pause prev until xfade starts.
   */
  async function playViaLocal(
    track,
    { autoplay = true, fadeMs = FADE_MS, allowCrossfade = true, waitMs = null, isCurrent = null } = {}
  ) {
    const still = () => !isCurrent || isCurrent();
    ensurePolishConnected();

    const budget =
      waitMs != null
        ? waitMs
        : allowCrossfade
          ? XFADE_READY_MS
          : 800;

    const fromSlot = state.activeSlot;
    const toSlot = otherSlot(fromSlot);
    const prev = audioEl(fromSlot);
    const canHandoff =
      allowCrossfade &&
      autoplay &&
      !state.reducedMotion &&
      state.audioMode === "local" &&
      state.playing &&
      state.polishConnected &&
      prev &&
      prev.src &&
      !prev.src.includes(track.video_id);

    if (canHandoff && prev.paused) {
      try {
        await prev.play();
      } catch {
        /* ignore */
      }
    }

    const handoffReady = canHandoff && prev && !prev.paused;

    if (handoffReady) {
      const pre = state.slotPreload;
      const preloaded = isHotPreloadValid(track.video_id, toSlot);

      let url =
        state.readyCache[track.video_id] ||
        (preloaded && pre.url ? pre.url : null);

      if (!url) {
        console.info("[next] keeping prev alive", {
          phase: "cache",
          video_id: track.video_id,
          ms: budget,
        });
        url = await prepareLocalAudioRace(track.video_id, budget, still);
      }

      if (!still()) return false;

      if (url) {
        if (preloaded) {
          console.info("[next] handoff start", {
            preloaded: true,
            slot: toSlot,
            video_id: track.video_id,
          });
        } else if (xfadeRequirePreloaded()) {
          console.warn("[xfade] gate blocked — waiting for preload only", track.video_id);
          return false;
        } else {
          xfadeDbg("[next] keeping prev alive", {
            phase: "buffer",
            slot: toSlot,
            video_id: track.video_id,
          });
          /* Short prime only — crossfadeToLocal starts overlap ASAP; download continues. */
          const buffered = await ensureSlotBuffered(
            toSlot,
            url,
            Math.min(2400, Math.max(800, budget * 0.4))
          );
          if (!buffered) {
            console.warn("[xfade] buffer timeout — still holding prev", track.video_id);
            return false;
          }
          if (!still()) return false;
          console.info("[next] handoff start", {
            preloaded: false,
            slot: toSlot,
            video_id: track.video_id,
          });
        }

        state.xfadeInProgress = true;
        try {
          const ok = await crossfadeToLocal(track, url, { autoplay });
          if (ok) return true;
        } finally {
          /* crossfadeToLocal clears this; keep false if it returned early. */
          state.xfadeInProgress = false;
        }

        console.warn("[xfade] overlap failed — inactive cold", track.video_id);
        return playViaLocalCold(track, url, {
          autoplay,
          fadeMs,
          slot: toSlot,
          keepPrevAlive: true,
        });
      }

      console.warn("[xfade] no local url while holding prev", track.video_id);
      return false;
    }

    if (allowCrossfade && state.audioMode === "local") {
      xfadeDbg("[xfade] no handoff gate", {
        mode: state.audioMode,
        playing: state.playing,
        dual: state.polishDual,
        paused: prev ? prev.paused : null,
        hasPrev: Boolean(prev && prev.src && !prev.src.includes(track.video_id)),
        reduced: state.reducedMotion,
      });
    }

    const url = await prepareLocalAudioRace(track.video_id, budget, still);
    if (!url || !still()) return false;

    if (allowCrossfade && state.audioMode === "local" && !state.xfadeInProgress) {
      await ensureSlotBuffered(toSlot, url, Math.min(2500, XFADE_READY_MS));
    }
    if (!still()) return false;

    return playViaLocalCold(track, url, { autoplay, fadeMs });
  }

  /** Last resort after local handoff timeout — always advances playback. */
  async function advanceViaIframeFallback(
    track,
    { autoplay = true, fadeMs = FADE_MS, reason = "fallback", prepareGen = null, fadePrev = false } = {}
  ) {
    const from = audioEl(state.activeSlot);
    const to = audioEl(otherSlot(state.activeSlot));
    if (
      state.audioMode === "local" &&
      from &&
      to &&
      !from.paused &&
      !to.paused
    ) {
      console.warn("[xfade] aborting dual overlap for fallback", {
        video_id: track.video_id,
        reason,
      });
      await abortStaleLocalOverlap();
    }
    console.info("[next] fallback iframe", { video_id: track.video_id, reason });
    const active = activeAudio();
    if (fadePrev && state.audioMode === "local" && active && state.playing && !active.paused) {
      try {
        await fadeElementVolume(active, active.volume || 1, 0, Math.min(fadeMs * 0.45, 900));
      } catch {
        /* ignore */
      }
    }
    await playViaIframe(track, { autoplay, fadeMs, reason });
    ensurePolishConnected();
    if (prepareGen != null && !(state.localAudioTools && state.localAudioTools.ready === false)) {
      promoteToLocalWhenReady(track, prepareGen);
    }
  }

  /** YouTube iframe: volume fade only — true dual-source overlap needs local audio. */
  async function playViaIframe(track, { autoplay = true, fadeMs = FADE_MS, reason = "fallback" } = {}) {
    stopLocalAudio();
    setPolishHearable(false);
    state.audioMode = "iframe";
    state.polishConnected = false;
    state.polishDual = false;

    if (el.level) {
      el.level.setAttribute("data-tip", "Compressor Needs Local Audio");
    }

    if (!state.player || typeof state.player.loadVideoById !== "function") {
      // YT API not ready yet — retry briefly so first play isn't silent forever
      if (autoplay) {
        setPlayingUI(true);
        const started = Date.now();
        await new Promise((resolve) => {
          const poll = () => {
            if (state.player && typeof state.player.loadVideoById === "function") {
              resolve();
              return;
            }
            if (Date.now() - started > 8000) {
              resolve();
              return;
            }
            window.setTimeout(poll, 120);
          };
          poll();
        });
      }
      if (!state.player || typeof state.player.loadVideoById !== "function") {
        setPlayingUI(Boolean(autoplay));
        return;
      }
    }

    try {
      if (typeof state.player.unMute === "function") state.player.unMute();
    } catch {
      /* ignore */
    }

    state.player.loadVideoById({ videoId: track.video_id });
    setVolumeSafe(0);
    if (autoplay) {
      try {
        state.player.playVideo();
      } catch (err) {
        console.warn("iframe play blocked", err);
      }
      setPlayingUI(true);
      await fadeVolume(0, VOLUME_DEFAULT, fadeMs * 0.65);
    } else {
      setVolumeSafe(VOLUME_DEFAULT);
      setPlayingUI(false, { force: true });
    }
  }

  function nextPlayableIndex(fromIndex, direction) {
    if (!state.queue.length) return fromIndex;
    const n = state.queue.length;
    let i = fromIndex;
    for (let step = 0; step < n; step++) {
      i = ((i + direction) % n + n) % n;
      const t = state.queue[i];
      if (t && !isNotFit(t.video_id)) return i;
    }
    return fromIndex;
  }

  function seenIds() {
    return new Set(state.queue.map((t) => t.video_id).filter(Boolean));
  }

  async function advanceTrack(direction, reason) {
    if (direction > 0) {
      const atEnd = state.index >= state.queue.length - 1;
      if (atEnd && state.hasMore && state.nextCursor) {
        await refillQueueIfNeeded(true);
      }
      if (state.index < state.queue.length - 1) {
        let i = state.index + 1;
        while (i < state.queue.length && isNotFit(state.queue[i].video_id)) i++;
        if (i < state.queue.length) {
          return loadTrack(i, { autoplay: true, reason });
        }
      }
      if (!state.hasMore) {
        const nextIdx = nextPlayableIndex(state.index, 1);
        return loadTrack(nextIdx, { autoplay: true, reason });
      }
      await refillQueueIfNeeded(true);
      if (state.index < state.queue.length - 1) {
        return loadTrack(state.index + 1, { autoplay: true, reason });
      }
    }
    const nextIdx = nextPlayableIndex(state.index, direction);
    return loadTrack(nextIdx, { autoplay: true, reason });
  }

  function queueParams(genreId, cursor, extra = {}) {
    const params = new URLSearchParams({
      genre: genreId,
      tier: state.tierId || DEFAULT_TIER,
    });
    if (cursor) params.set("cursor", cursor);
    if (state.requireFree) params.set("is_free", "1");
    if (state.requireFfp) params.set("free_for_profit", "1");
    if (state.requireProlific) params.set("prolific", "1");
    if (state.maxAgeMonths) params.set("max_age_months", String(state.maxAgeMonths));
    if (extra.warm) params.set("warm", "1");
    if (extra.live) params.set("live", "1");
    return params;
  }

  function hasExperimentalQueueFilters() {
    return Boolean(state.requireProlific || state.maxAgeMonths);
  }

  /** Called by skins.js experimental panel when prolific / age change. */
  function applyExperimentalFilters({ prolific, maxAgeMonths } = {}) {
    let changed = false;
    if (typeof prolific === "boolean" && prolific !== state.requireProlific) {
      state.requireProlific = prolific;
      changed = true;
    }
    if (maxAgeMonths !== undefined) {
      const next =
        maxAgeMonths === null || maxAgeMonths === "" || maxAgeMonths === 0
          ? null
          : Number(maxAgeMonths);
      const normalized = Number.isFinite(next) && next > 0 ? next : null;
      if (normalized !== state.maxAgeMonths) {
        state.maxAgeMonths = normalized;
        changed = true;
      }
    }
    if (!changed) return;
    logEvent("exp_filters", {
      prolific: state.requireProlific,
      max_age_months: state.maxAgeMonths,
    });
    fetchQueue(state.genreId);
  }

  window.TypeBeatRadio = window.TypeBeatRadio || {};
  window.TypeBeatRadio.applyExperimentalFilters = applyExperimentalFilters;
  window.TypeBeatRadio.applyCrossfadeSettings = applyCrossfadeSettings;
  window.TypeBeatRadio.syncArtTitle = syncArtTitle;
  window.TypeBeatRadio.renderTiers = renderTiers;
  window.TypeBeatRadio.applyPolishAmount = applyPolishAmount;
  window.TypeBeatRadio.getPolishPct = polishPct;
  window.TypeBeatRadio.syncCompressUI = syncCompressUI;
  window.TypeBeatRadio.getDisplayTitle = () => trackDisplayTitle(currentTrack());
  window.TypeBeatRadio.viewsTierLabelMarkup = viewsTierLabelMarkup;
  window.TypeBeatRadio.ageTierLabelMarkup = ageTierLabelMarkup;
  window.TypeBeatRadio.getExperimentalFilters = () => ({
    prolific: state.requireProlific,
    maxAgeMonths: state.maxAgeMonths,
  });
  window.TypeBeatRadio.getCrossfadeSettings = () => ({
    mode: state.xfadeExp.mode,
    preload: state.xfadeExp.preload,
    handoffGate: state.xfadeExp.handoffGate,
    overlapMin: state.xfadeExp.overlapMin,
    startAt: state.xfadeExp.startAt,
    debug: state.xfadeExp.debug,
    effectiveMs: getEffectiveXfadeMs(),
    startSec: getXfadeStartSec(),
  });

  async function fetchJsonWithTimeout(url, timeoutMs = QUEUE_FETCH_TIMEOUT_MS) {
    const ctrl = new AbortController();
    const timer = window.setTimeout(() => ctrl.abort(), timeoutMs);
    try {
      const res = await fetch(url, { signal: ctrl.signal });
      const data = await res.json();
      return { res, data };
    } finally {
      window.clearTimeout(timer);
    }
  }

  async function requestQueuePage(genreId, cursor, opts = {}) {
    const { warm = false, live = false, retriesLeft = QUEUE_INDEX_RETRIES } = opts;
    const params = queueParams(genreId, cursor, { warm, live });
    let res;
    let data;
    try {
      ({ res, data } = await fetchJsonWithTimeout(`/api/queue?${params}`));
    } catch (err) {
      // Timeout / network — try explicit warm playlist once before failing.
      if (!warm && !cursor && genreId === DEFAULT_STATION) {
        try {
          return await requestQueuePage(genreId, null, {
            warm: true,
            retriesLeft: 2,
          });
        } catch {
          /* fall through */
        }
      }
      throw err;
    }
    if (res.status === 202 || data.status === "indexing") {
      if (retriesLeft <= 0) {
        if (!warm && !cursor && genreId === DEFAULT_STATION) {
          return requestQueuePage(genreId, null, { warm: true, retriesLeft: 2 });
        }
        throw new Error(data.message || "Catalog still indexing");
      }
      await new Promise((r) => setTimeout(r, 900));
      return requestQueuePage(genreId, cursor, {
        warm,
        live,
        retriesLeft: retriesLeft - 1,
      });
    }
    if (!res.ok) throw new Error(data.error || "Queue failed");
    return data;
  }

  async function refillQueueIfNeeded(force = false) {
    if (state.refilling || state.loadingQueue || !state.hasMore) {
      return;
    }
    const remaining = state.queue.length - state.index - 1;
    if (!force && remaining > REFILL_WHEN_REMAINING) return;

    // Warm first page has no cursor — pull a live DB page once to unlock keyset refill.
    if (!state.nextCursor) {
      state.refilling = true;
      try {
        await refreshLiveQueueInBackground();
      } finally {
        state.refilling = false;
      }
      return;
    }

    state.refilling = true;
    try {
      const data = await requestQueuePage(state.genreId, state.nextCursor);
      const raw = data.tracks || [];
      const known = seenIds();
      const fresh = filterNotFit(raw, state.genreId).filter((t) => !known.has(t.video_id));
      if (fresh.length) {
        state.queue = state.queue.concat(fresh);
      }
      state.nextCursor = data.next_cursor || null;
      state.hasMore = Boolean(data.has_more && state.nextCursor);
      prefetchAhead(state.index);
    } catch (err) {
      console.warn("refill failed", err);
    } finally {
      state.refilling = false;
    }
  }

  function prefetchThumb(videoId) {
    if (!videoId) return;
    try {
      const img = new Image();
      img.decoding = "async";
      img.src = thumbUrl(videoId);
    } catch {
      /* ignore */
    }
  }

  /** After warm first-paint, pull a live DB page in the background and append. */
  async function refreshLiveQueueInBackground() {
    if (state.genreId !== DEFAULT_STATION || state.tierId !== DEFAULT_TIER) return;
    if (hasExperimentalQueueFilters()) return;
    if (state.requireFree || state.requireFfp) return;
    try {
      const data = await requestQueuePage(state.genreId, null, { live: true });
      if (!data || data.warm) return;
      const raw = data.tracks || [];
      const known = seenIds();
      const fresh = filterNotFit(raw, state.genreId).filter((t) => !known.has(t.video_id));
      if (fresh.length) {
        state.queue = state.queue.concat(fresh);
      }
      if (data.next_cursor) {
        state.nextCursor = data.next_cursor;
        state.hasMore = Boolean(data.has_more && state.nextCursor);
      }
      prefetchAhead(state.index);
    } catch (err) {
      console.warn("live queue refresh skipped", err);
    }
  }

  async function loadTrack(index, { autoplay = true, reason = "nav" } = {}) {
    if (!state.queue.length) return;

    if (state.navLock.busy) {
      if (navReasonQueues(reason)) {
        queueNavWhileBusy(reason === "prev" ? -1 : 1, reason);
      }
      return;
    }

    const target =
      typeof index === "number"
        ? ((index % state.queue.length) + state.queue.length) % state.queue.length
        : state.index;

    let resolved = target;
    if (reason !== "init" && state.queue[resolved] && isNotFit(state.queue[resolved].video_id)) {
      resolved = nextPlayableIndex(resolved, 1);
    }

    const track = state.queue[resolved];
    if (!track) return;

    const active = activeAudio();
    const sameLocal =
      resolved === state.index &&
      state.audioMode === "local" &&
      active &&
      active.src &&
      active.src.includes(track.video_id);

    const sameYt =
      resolved === state.index &&
      state.player &&
      typeof state.player.getVideoData === "function" &&
      (state.player.getVideoData().video_id || "") === track.video_id;

    if ((sameLocal || sameYt) && reason === "nav") return;

    const navToken = beginNavLock();
    const prepareGen = ++state.prepareGen;

    const silentSkip = isSilentSkipReason(reason);
    const fadeMs = silentSkip || state.reducedMotion ? 0 : FADE_MS;
    const wasPlaying = autoplay || state.playing;
    // Lock pause glyph for the whole handoff (incl. prepare wait).
    if (wasPlaying && !silentSkip) setPlayingUI(true);
    const prevTrack = currentTrack();
    const prevVideoId = prevTrack ? prevTrack.video_id : null;
    const leavingTrack =
      reason !== "init" &&
      reason !== "loop" &&
      reason !== "play" &&
      (resolved !== state.index || (prevVideoId && prevVideoId !== track.video_id));

    /* Title + cover update immediately on Next — do not wait for audio handoff. */
    if (leavingTrack || reason === "init" || reason === "station") {
      crossfadeArt(track.video_id);
      syncArtTitle(track);
    }

    if (leavingTrack) {
      flushListenSegment();
      resetLoopOnTrackChange(reason);
      if (isHotPreloadValid(track.video_id)) {
        console.info("[next] reusing hot preload", {
          video_id: track.video_id,
          slot: state.slotPreload.slot,
          buffered: state.slotPreload.buffered,
          primed: state.slotPreload.primed,
        });
      } else {
        if (state.slotPreload.videoId) {
          xfadeDbg("[next] stale preload invalidated", {
            wanted: track.video_id,
            had: state.slotPreload.videoId,
            slot: state.slotPreload.slot,
          });
        }
        invalidateStalePreload(track.video_id);
      }
    }

    // True A↔B overlap when already on local — do not pre-fade A out.
    const wantOverlap =
      leavingTrack &&
      wasPlaying &&
      state.audioMode === "local" &&
      !state.reducedMotion;

    let handoffCommitted = false;

    const commitHandoff = async ({
      usedLocal,
      toolsOk,
      shouldPlay,
      wantOverlap,
      stayed,
      listened,
      fallbackReason = null,
    }) => {
      if (handoffCommitted || navToken !== state.navLock.token) return;
      if (prepareGen !== state.prepareGen && !state.navHandoffTimedOut) return;
      handoffCommitted = true;

      state.index = resolved;
      syncArtTitle();

      if (!usedLocal) {
        if (wantOverlap && state.audioMode === "local" && shouldPlay) {
          console.warn("[xfade] local cache timeout — advancing via fallback", track.video_id);
        }
        await advanceViaIframeFallback(track, {
          autoplay: shouldPlay,
          fadeMs,
          reason: fallbackReason || (toolsOk ? "cache_timeout" : "no_ytdlp"),
          prepareGen,
          fadePrev: wantOverlap && shouldPlay,
        });
      }

      /* After a successful local xfade, never "repair" — that caused blip→silence→restart. */
      if (shouldPlay && !usedLocal) {
        await ensureHeardMatchesTrack(track, shouldPlay);
      }

      markTrackStart();
      clearHandoffState({ bumpPreload: false });

      if (
        reason === "skip" ||
        reason === "next" ||
        reason === "prev" ||
        reason === "ended" ||
        reason === "not_fit" ||
        reason === "station" ||
        reason === "error" ||
        reason === "dead_cover" ||
        reason === "dead_track"
      ) {
        logEvent("track_change", {
          reason,
          from: prevVideoId,
          to: track.video_id,
          video_id: prevVideoId,
          stay_ms: stayed,
          listen_ms: listened,
          audio_mode: state.audioMode,
        });
      }

      prefetchAhead(resolved);
      refillQueueIfNeeded();
      if (shouldPlay && state.audioMode === "local") {
        scheduleInactivePreload();
      }
    };

    const handoffTimeoutMs = silentSkip
      ? Math.min(3200, computeNavHandoffTimeoutMs(false))
      : computeNavHandoffTimeoutMs(wantOverlap);
    startNavHandoffTimer(navToken, prepareGen, handoffTimeoutMs, () => {
      if (handoffCommitted) return;
      commitHandoff({
        usedLocal: false,
        toolsOk: true,
        shouldPlay: wasPlaying || autoplay,
        wantOverlap: false,
        stayed: stayMs(),
        listened: listenMs(),
        fallbackReason: "nav_timeout",
      })
        .catch((err) => console.error("[nav] timeout recovery failed", err))
        .finally(() => {
          releaseNavLock(navToken);
        });
    });

    try {
      await resumeAudioContext();
      prefetchAhead(resolved);
      // Kick + warm inactive host for the track we are jumping to.
      if (leavingTrack && track.video_id) {
        prefetchLocalAudio(track.video_id);
      }

      if (leavingTrack && xfadePreloadOnSkipOnly()) {
        scheduleInactivePreload(track.video_id, { force: true });
      }

      if (
        !silentSkip &&
        state.playing &&
        (state.audioMode === "iframe" || (state.audioMode === "local" && !wantOverlap))
      ) {
        await fadeVolume(getVolumeSafe(), 0, fadeMs * 0.55);
      }

      if (isHandoffStale(navToken, prepareGen)) return;

      const stayed = stayMs();
      const listened = listenMs();
      /* Art/title already updated at click time when leavingTrack. */
      if (!leavingTrack && reason !== "init" && reason !== "station") {
        crossfadeArt(track.video_id);
        syncArtTitle(track);
      } else {
        syncArtTitle(track);
      }

      const toolsOk = !(state.localAudioTools && state.localAudioTools.ready === false);
      let usedLocal = false;
      const shouldPlay = wasPlaying || autoplay;

      const localWaitMs = silentSkip
        ? Math.min(900, localHandoffBudgetMs(false))
        : localHandoffBudgetMs(wantOverlap && shouldPlay);

      if (toolsOk && !state.navHandoffTimedOut) {
        usedLocal = await playViaLocal(track, {
          autoplay: shouldPlay,
          fadeMs,
          allowCrossfade: silentSkip ? false : wantOverlap,
          waitMs: localWaitMs,
          isCurrent: () => !isHandoffStale(navToken, prepareGen),
        });
      }

      if (isHandoffStale(navToken, prepareGen)) return;

      const retryBudgetMs = silentSkip ? Math.min(1200, LOCAL_CACHE_RETRY_MS) : LOCAL_CACHE_RETRY_MS;

      if (!usedLocal && toolsOk && shouldPlay && !state.navHandoffTimedOut && !silentSkip) {
        console.info("[next] keeping prev alive", {
          phase: "retry",
          video_id: track.video_id,
          ms: retryBudgetMs,
        });
        const retryUrl = await prepareLocalAudioRace(
          track.video_id,
          retryBudgetMs,
          () => !isHandoffStale(navToken, prepareGen)
        );
        if (retryUrl && !isHandoffStale(navToken, prepareGen)) {
          usedLocal = await playViaLocal(track, {
            autoplay: shouldPlay,
            fadeMs,
            allowCrossfade: wantOverlap,
            waitMs: 800,
            isCurrent: () => !isHandoffStale(navToken, prepareGen),
          });
        }
      }

      if (isHandoffStale(navToken, prepareGen)) return;

      await commitHandoff({
        usedLocal,
        toolsOk,
        shouldPlay,
        wantOverlap,
        stayed,
        listened,
        fallbackReason: state.navHandoffTimedOut ? "nav_timeout" : null,
      });
    } catch (err) {
      console.error("[nav] loadTrack failed", err);
      if (!handoffCommitted && !isHandoffStale(navToken, prepareGen)) {
        await commitHandoff({
          usedLocal: false,
          toolsOk: true,
          shouldPlay: wasPlaying || autoplay,
          wantOverlap: false,
          stayed: stayMs(),
          listened: listenMs(),
          fallbackReason: "nav_error",
        });
      }
    } finally {
      clearHandoffState({ bumpPreload: false });
      releaseNavLock(navToken);
    }
  }

  async function fetchQueue(genreId) {
    state.loadingQueue = true;
    el.artBtn.classList.add("is-loading");
    syncNavControls();
    clearStylePending();
    resetLoopOnTrackChange("station");

    try {
      // Prefer warm first paint for default All (server returns warm unless ?live=1).
      // Experimental prolific / age filters always need live SQL.
      const data = await requestQueuePage(genreId, null, {
        warm:
          genreId === DEFAULT_STATION &&
          state.tierId === DEFAULT_TIER &&
          !hasExperimentalQueueFilters(),
      });
      const raw = data.tracks || [];
      state.queue = filterNotFit(raw, genreId);
      state.genreId = genreId;
      state.index = 0;
      // Warm pages have no cursor; keep hasMore true so we can live-refresh / refill.
      if (data.warm) {
        state.nextCursor = null;
        state.hasMore = true;
      } else {
        state.nextCursor = data.next_cursor || null;
        state.hasMore = Boolean(data.has_more && state.nextCursor);
      }
      state.readyCache = Object.create(null);
      resetSlotPreload();
      state.prefetchGen += 1;
      syncChipActive();
      syncTierActive();
      syncLicenseActive();

      stopLocalAudio();
      pauseIframe();
      state.audioMode = null;
      state.activeSlot = "a";
      if (state.polish && typeof state.polish.setActiveSlot === "function") {
        state.polish.setActiveSlot("a");
      }
      setPolishHearable(false);

      if (!state.queue.length) {
        return;
      }

      const track = currentTrack();
      prefetchThumb(track.video_id);
      crossfadeArt(track.video_id);
      syncArtTitle();
      markTrackStart();

      if (state.player && typeof state.player.cueVideoById === "function") {
        try {
          if (typeof state.player.mute === "function") state.player.mute();
        } catch {
          /* ignore */
        }
        state.player.cueVideoById(track.video_id);
      }
      setPlayingUI(false);

      kickQueueAudioPrefetch(0, PREFETCH_AUDIO_AHEAD);
      prefetchAhead(-1);
      if (track && track.video_id) {
        prefetchLocalAudio(track.video_id);
      }

      if (data.warm) {
        // Don't block UI — extend rotation from live DB when ready.
        refreshLiveQueueInBackground();
      }
    } catch (err) {
      console.error(err);
    } finally {
      state.loadingQueue = false;
      el.artBtn.classList.remove("is-loading");
      syncNavControls();
      window.setTimeout(() => drainNavQueue(), 0);
    }
  }

  function flashBtn(btn) {
    btn.classList.add("is-flash");
    window.setTimeout(() => btn.classList.remove("is-flash"), 280);
  }

  function syncChipActive() {
    if (!el.chips) return;
    el.chips.querySelectorAll(".genre-chip").forEach((btn) => {
      const id = btn.dataset.genre;
      const on = id === state.genreId;
      const pending = id === state.pendingGenreId;
      const label = btn.dataset.label || btn.textContent;
      if (!btn.dataset.label) btn.dataset.label = label;

      btn.classList.toggle("is-active", on && !pending);
      btn.classList.toggle("is-pending", pending);
      btn.classList.toggle("is-confirm", pending && state.pendingPhase === "change_now");
      btn.setAttribute("aria-selected", on || pending ? "true" : "false");

      if (pending) {
        const tip =
          state.pendingPhase === "change_now"
            ? "Press Next Or Click Again To Change Genre Now"
            : "Next Up — Press Next To Confirm";
        btn.textContent = pendingChipLabel();
        btn.setAttribute("data-tip", tip);
        btn.setAttribute("aria-label", `${btn.dataset.label}. ${tip}`);
      } else {
        btn.textContent = capsLabel(btn.dataset.label);
        btn.setAttribute(
          "data-tip",
          on ? `Playing ${btn.dataset.label}` : `Queue ${btn.dataset.label} Next`
        );
        btn.setAttribute("aria-label", btn.dataset.label);
      }
    });
    if (window.TypeBeatSkins && typeof window.TypeBeatSkins.rescanChipFit === "function") {
      window.TypeBeatSkins.rescanChipFit();
    }
  }

  function syncTierActive() {
    if (!el.tiers) return;
    el.tiers.querySelectorAll(".genre-chip").forEach((btn) => {
      const on = btn.dataset.tier === state.tierId;
      btn.classList.toggle("is-active", on);
      btn.setAttribute("aria-selected", on ? "true" : "false");
    });
  }

  function syncLicenseActive() {
    if (!el.license) return;
    el.license.querySelectorAll(".genre-chip").forEach((btn) => {
      const key = btn.dataset.filter;
      const on =
        (key === "free" && state.requireFree) || (key === "ffp" && state.requireFfp);
      btn.classList.toggle("is-active", on);
      btn.setAttribute("aria-pressed", on ? "true" : "false");
    });
  }

  function syncLoopButton() {
    if (!el.loop) return;
    el.loop.classList.toggle("is-active", state.loopTrack);
    el.loop.setAttribute("aria-pressed", state.loopTrack ? "true" : "false");
    el.loop.setAttribute(
      "data-tip",
      state.loopTrack ? "Loop On — Click To Stop" : "Loop This Track"
    );
  }

  function renderChips() {
    el.chips.innerHTML = state.genres
      .map((g) => {
        const isDefault = g.id === "all";
        const active = g.id === state.genreId && !state.pendingGenreId;
        const label = titleCaseLabel(g.label);
        const display = capsLabel(label);
        const tip = active ? `Playing ${label}` : `Queue ${label} Next`;
        return `<button type="button" class="genre-chip${active ? " is-active" : ""}${
          isDefault ? " is-default" : ""
        }" role="option" data-genre="${g.id}" data-label="${escapeAttr(label)}" data-tip="${escapeAttr(
          tip
        )}" aria-label="${escapeAttr(label)}" aria-selected="${
          active ? "true" : "false"
        }">${display}</button>`;
      })
      .join("");
    if (window.TypeBeatSkins && typeof window.TypeBeatSkins.rescanChipFit === "function") {
      window.TypeBeatSkins.rescanChipFit();
    }
  }

  function applyViewTier(tierId) {
    if (!tierId || tierId === state.tierId) return;
    const from = state.tierId;
    state.tierId = tierId;
    try {
      localStorage.setItem(STORAGE_TIER, state.tierId);
    } catch {
      /* ignore */
    }
    syncTierActive();
    renderTiers();
    logEvent("tier_change", { from, to: state.tierId, deferred: Boolean(currentTrack()) });
    if (currentTrack()) {
      rebuildQueueKeepCurrent();
    } else {
      reloadRotation();
    }
  }

  function renderTiers() {
    if (!el.tiers) return;
    const sliderMode =
      document.documentElement.getAttribute("data-views-ui") === "slider" &&
      state.viewTiers.length > 1;
    if (sliderMode) {
      const idx = Math.max(
        0,
        state.viewTiers.findIndex((t) => t.id === state.tierId)
      );
      const tier = state.viewTiers[idx] || state.viewTiers[0];
      const hint = titleCaseLabel(tier.hint || `Views ${tier.label}`);
      const n = state.viewTiers.length;
      el.tiers.innerHTML = `<div class="views-slider" role="group" aria-label="Views tier" style="--views-n:${n}">
        <input type="range" class="views-slider__input" id="views-tier-slider" min="0" max="${
          n - 1
        }" step="1" value="${idx}" aria-valuemin="0" aria-valuemax="${
        n - 1
      }" aria-valuenow="${idx}" aria-valuetext="${escapeAttr(hint)}" />
        <div class="views-slider__track" aria-hidden="true">
          ${state.viewTiers
            .map(
              (t, i) =>
                `<span class="views-slider__tick${i === idx ? " is-active" : ""}" data-tier="${
                  t.id
                }"></span>`
            )
            .join("")}
        </div>
        <div class="views-slider__labels" aria-hidden="true">
          ${state.viewTiers
            .map(
              (t, i) =>
                `<span class="views-slider__label${i === idx ? " is-active" : ""}">${viewsTierLabelMarkup(
                  t.label
                )}</span>`
            )
            .join("")}
        </div>
      </div>`;
      const input = document.getElementById("views-tier-slider");
      if (input) {
        input.addEventListener("input", () => {
          const i = Number(input.value);
          const t = state.viewTiers[i];
          if (!t || t.id === state.tierId) return;
          applyViewTier(t.id);
        });
      }
      return;
    }
    el.tiers.innerHTML = state.viewTiers
      .map((t) => {
        const active = t.id === state.tierId;
        const label = t.label;
        const display = capsLabel(label);
        const hint = titleCaseLabel(t.hint || `Views ${label}`);
        return `<button type="button" class="genre-chip${active ? " is-active" : ""}${
          t.id === "all" ? " is-default" : ""
        }" role="option" data-tier="${t.id}" data-tip="${escapeAttr(hint)}" aria-label="${escapeAttr(
          hint
        )}" aria-selected="${active ? "true" : "false"}">${display}</button>`;
      })
      .join("");
  }

  async function togglePlayPause() {
    const track = currentTrack();
    if (!track) return;

    const edge = state.reducedMotion ? 0 : TRANSPORT_FADE_MS;

    if (state.playing) {
      if (state.audioMode === "local") {
        const a = activeAudio();
        if (a) {
          if (state.polish && typeof state.polish.fadeMaster === "function" && edge > 0) {
            await state.polish.fadeMaster(0, edge);
          } else if (edge > 0) {
            await fadeElementVolume(a, a.volume || 1, 0, edge);
          }
          try {
            a.pause();
          } catch {
            /* ignore */
          }
          a.volume = 1;
        }
      } else if (state.player) {
        if (edge > 0) {
          await fadeVolume(getVolumeSafe(), 0, edge);
        }
        state.player.pauseVideo();
      }
      setPlayingUI(false, { force: true });
      logEvent("pause", { listen_ms: listenMs() });
      return;
    }

    if (state.audioMode === "local") {
      const a = activeAudio();
      if (a && a.src) {
        try {
          if (state.polish && typeof state.polish.fadeMaster === "function") {
            await state.polish.fadeMaster(0, 1);
          } else {
            a.volume = 0;
          }
          await a.play();
          if (state.polish && typeof state.polish.resume === "function") {
            await state.polish.resume().catch(() => {});
          }
          if (state.polish && typeof state.polish.fadeMaster === "function") {
            await state.polish.fadeMaster(1, edge || 1);
          } else if (edge > 0) {
            await fadeElementVolume(a, 0, 1, edge);
          } else {
            a.volume = 1;
          }
          setPlayingUI(true);
          logEvent("play");
          prefetchAhead(state.index);
          scheduleInactivePreload();
          return;
        } catch {
          /* fall through to load */
        }
      }
    }

    await loadTrack(state.index, { autoplay: true, reason: "play" });
    logEvent("play");
  }

  function wireControls() {
    el.prev.addEventListener("click", () => {
      if (state.pendingGenreId) {
        logEvent("station_cancel", { from: state.pendingGenreId, to: state.genreId });
        clearStylePending();
        syncChipActive();
        return;
      }
      logEvent("skip", { direction: "prev" });
      requestSkip(-1, "prev");
    });

    el.next.addEventListener("click", () => {
      if (state.pendingGenreId) {
        logEvent("skip", { direction: "next", pending_commit: true });
        commitStylePending();
        return;
      }
      logEvent("skip", { direction: "next" });
      requestSkip(1, "next");
    });

    el.artBtn.addEventListener("click", () => {
      togglePlayPause();
    });

    el.chips.addEventListener("click", (e) => {
      const btn = e.target.closest(".genre-chip");
      if (!btn || !btn.dataset.genre) return;
      const genreId = btn.dataset.genre;

      if (genreId === state.genreId) {
        if (state.pendingGenreId) {
          clearStylePending();
          syncChipActive();
        }
        return;
      }

      if (state.pendingGenreId && genreId === state.pendingGenreId) {
        commitStylePending();
        return;
      }

      if (currentTrack()) {
        logEvent("station_arm", { from: state.genreId, to: genreId });
        armStylePending(genreId);
        return;
      }

      applyGenreNow(genreId);
    });

    if (el.tiers) {
      el.tiers.addEventListener("click", (e) => {
        const btn = e.target.closest(".genre-chip");
        if (!btn || !btn.dataset.tier) return;
        applyViewTier(btn.dataset.tier);
      });
    }

    if (el.license) {
      el.license.addEventListener("click", (e) => {
        const btn = e.target.closest(".genre-chip");
        if (!btn || !btn.dataset.filter) return;
        if (btn.dataset.filter === "free") {
          state.requireFree = !state.requireFree;
        } else if (btn.dataset.filter === "ffp") {
          state.requireFfp = !state.requireFfp;
        } else {
          return;
        }
        syncLicenseActive();
        logEvent("license_filter", {
          is_free: state.requireFree,
          free_for_profit: state.requireFfp,
          deferred: Boolean(currentTrack()),
        });
        if (currentTrack()) {
          rebuildQueueKeepCurrent();
        } else {
          reloadRotation();
        }
      });
    }

    el.like.addEventListener("click", () => {
      onReactionClick("like");
    });

    el.dislike.addEventListener("click", () => {
      onReactionClick("dislike");
    });

    el.notFit.addEventListener("click", () => {
      const track = currentTrack();
      if (!track || state.transitioning) return;
      flashBtn(el.notFit);
      markNotFit(track.video_id, state.genreId);
      logEvent("not_fit");
      state.queue = state.queue.filter((t) => t.video_id !== track.video_id);
      if (!state.queue.length) {
        if (state.hasMore && state.nextCursor) {
          refillQueueIfNeeded(true).then(() => {
            if (!state.queue.length) return;
            loadTrack(0, { autoplay: true, reason: "not_fit" });
          });
          return;
        }
        return;
      }
      const idx = state.index % state.queue.length;
      loadTrack(idx, { autoplay: true, reason: "not_fit" });
    });

    if (el.loop) {
      el.loop.addEventListener("click", () => {
        state.loopTrack = !state.loopTrack;
        try {
          localStorage.setItem(STORAGE_LOOP, state.loopTrack ? "1" : "0");
        } catch {
          /* ignore */
        }
        syncLoopButton();
        logEvent("loop_toggle", { loop: state.loopTrack });
      });
    }

    if (el.level) {
      wireCompressGesture(el.level);
    }

    window.addEventListener("keydown", (e) => {
      if (el.inviteOverlay && !el.inviteOverlay.hidden && el.inviteOverlay.classList.contains("is-open")) {
        if (e.code === "Space" || e.code === "ArrowLeft" || e.code === "ArrowRight") {
          return;
        }
      }
      const tag = e.target && e.target.tagName;
      const typing =
        tag === "TEXTAREA" ||
        (tag === "INPUT" &&
          (!e.target.type ||
            ["text", "search", "email", "url", "tel", "password", "number"].includes(
              String(e.target.type).toLowerCase()
            ))) ||
        (e.target && e.target.isContentEditable);
      if (typing) return;
      if (tag === "SELECT") return;
      if (e.code === "Space") {
        e.preventDefault();
        if (el.artBtn) {
          el.artBtn.click();
          /* Global space toggles play — drop focus so the platter never keeps an accent ring. */
          el.artBtn.blur();
        }
      } else if (e.code === "ArrowRight") {
        el.next.click();
      } else if (e.code === "ArrowLeft") {
        el.prev.click();
      } else if (e.code === "KeyL") {
        if (el.loop) el.loop.click();
      }
    });
  }

  function hideTip(immediate = false) {
    if (state.tipHideTimer) {
      window.clearTimeout(state.tipHideTimer);
      state.tipHideTimer = 0;
    }
    const tip = state.tipEl;
    if (!tip) return;
    if (immediate) {
      tip.remove();
      state.tipEl = null;
      return;
    }
    tip.classList.remove("is-show");
    tip.classList.add("is-hide");
    state.tipHideTimer = window.setTimeout(() => {
      if (state.tipEl === tip) {
        tip.remove();
        state.tipEl = null;
      }
      state.tipHideTimer = 0;
    }, 280);
  }

  function placeTip(tip, anchor, clientX, clientY) {
    const pad = 10;
    const rect = anchor.getBoundingClientRect();
    let x = Number.isFinite(clientX) ? clientX : rect.left + rect.width / 2;
    let y = Number.isFinite(clientY) ? clientY : rect.top;
    x = Math.min(window.innerWidth - pad, Math.max(pad, x));
    y = Math.min(window.innerHeight - pad, Math.max(pad + 28, y));
    tip.style.left = `${x}px`;
    tip.style.top = `${y}px`;
  }

  function showTip(anchor, text, clientX, clientY) {
    if (!text) return;
    hideTip(true);
    const tip = document.createElement("div");
    tip.className = "radio-tip";
    tip.setAttribute("role", "status");
    tip.setAttribute("aria-live", "polite");
    tip.textContent = text;
    document.body.appendChild(tip);
    state.tipEl = tip;
    placeTip(tip, anchor, clientX, clientY);
    requestAnimationFrame(() => tip.classList.add("is-show"));
  }

  const TIP_SHOW_DELAY_MS = 2000;

  function wireTips() {
    let active = null;
    let consumed = false;
    let showTimer = 0;

    const clearShowTimer = () => {
      if (showTimer) {
        window.clearTimeout(showTimer);
        showTimer = 0;
      }
    };

    document.addEventListener(
      "pointerover",
      (e) => {
        const target = e.target.closest("[data-tip]");
        if (!target || target === active) return;
        active = target;
        consumed = false;
        clearShowTimer();
        hideTip(true);
        const text = target.getAttribute("data-tip");
        if (!text) return;
        const x = e.clientX;
        const y = e.clientY;
        showTimer = window.setTimeout(() => {
          showTimer = 0;
          if (active !== target) return;
          showTip(target, text, x, y);
          consumed = true;
        }, TIP_SHOW_DELAY_MS);
      },
      true
    );

    document.addEventListener(
      "pointermove",
      (e) => {
        if (!active || !state.tipEl || !consumed) return;
        if (!active.contains(e.target) && e.target !== active) return;
        placeTip(state.tipEl, active, e.clientX, e.clientY);
      },
      true
    );

    document.addEventListener(
      "pointerout",
      (e) => {
        if (!active) return;
        const related = e.relatedTarget;
        if (related && active.contains(related)) return;
        if (e.target !== active && !active.contains(e.target)) return;
        active = null;
        consumed = false;
        clearShowTimer();
        hideTip();
      },
      true
    );

    window.addEventListener("scroll", () => hideTip(true), true);
    window.addEventListener("blur", () => hideTip(true));
  }

  function wireListenLifecycle() {
    document.addEventListener("visibilitychange", () => {
      if (document.visibilityState === "hidden") {
        if (!currentTrack()) return;
        flushListenSegment();
        if (state.playing || state.listenAccumMs > 0) {
          logEvent("pause_away", {
            listen_ms: listenMs(),
            stay_ms: stayMs(),
          });
        }
        return;
      }
      if (state.playing) startListenSegment();
    });

    window.addEventListener("pagehide", () => {
      if (!currentTrack()) return;
      flushListenSegment();
      logEvent("session_end", {
        listen_ms: listenMs(),
        stay_ms: stayMs(),
      });
    });
  }

  async function loadGenres() {
    const res = await fetch("/api/genres");
    const data = await res.json();
    state.genres = data.genres || [];
    state.viewTiers = data.view_tiers || [];
    state.genreId = data.default || DEFAULT_STATION;

    let savedTier = DEFAULT_TIER;
    try {
      savedTier = localStorage.getItem(STORAGE_TIER) || data.default_view_tier || DEFAULT_TIER;
    } catch {
      savedTier = data.default_view_tier || DEFAULT_TIER;
    }
    if (!state.viewTiers.some((t) => t.id === savedTier)) {
      savedTier = data.default_view_tier || DEFAULT_TIER;
    }
    state.tierId = savedTier;

    try {
      state.requireProlific = localStorage.getItem("tb_radio_prolific") === "1";
      const ageRaw = localStorage.getItem("tb_radio_max_age_months");
      if (ageRaw) {
        const n = Number(ageRaw);
        const allowed = [6, 18, 24, 60, 120];
        if (Number.isFinite(n) && n > 0) {
          if (allowed.includes(n)) {
            state.maxAgeMonths = n;
          } else {
            let best = allowed[0];
            let bestDist = Math.abs(n - best);
            for (const m of allowed) {
              const d = Math.abs(n - m);
              if (d < bestDist) {
                best = m;
                bestDist = d;
              }
            }
            state.maxAgeMonths = best;
            localStorage.setItem("tb_radio_max_age_months", String(best));
          }
        }
      }
    } catch {
      /* private mode */
    }

    renderChips();
    renderTiers();
    syncLicenseActive();
  }

  async function probeLocalAudioTools() {
    try {
      const res = await fetch("/api/audio/tools");
      const data = await res.json();
      state.localAudioTools = data;
      if (!data.ready) {
        setPolishHearable(false);
        console.info(
          "TypeBeat: yt-dlp missing — Compressor needs: pip install yt-dlp"
        );
      }
      return data;
    } catch {
      state.localAudioTools = { ready: false };
      return state.localAudioTools;
    }
  }

  function clampPolish(amount) {
    const max =
      (state.polish && typeof state.polish.MAX_P === "number" && state.polish.MAX_P) ||
      (window.TypeBeatPolish && typeof window.TypeBeatPolish.MAX_P === "number"
        ? window.TypeBeatPolish.MAX_P
        : POLISH_MAX);
    return Math.min(max, Math.max(0, Number(amount) || 0));
  }

  function polishPct(amount = state.polishAmount) {
    const max =
      (window.TypeBeatPolish && typeof window.TypeBeatPolish.MAX_P === "number"
        ? window.TypeBeatPolish.MAX_P
        : POLISH_MAX) || POLISH_MAX;
    if (max <= 0) return 0;
    return Math.round((clampPolish(amount) / max) * 100);
  }

  function compressTipText() {
    if (!state.polishCanHear) return "Compressor Needs Local Audio";
    const pct = polishPct();
    if (pct <= 0) return "Hold And Drag Sideways To Compress";
    return `Hold And Drag Sideways · ${pct}%`;
  }

  function syncCompressUI() {
    if (!el.level) return;
    const pct = polishPct();
    const amount = clampPolish(state.polishAmount);
    const amountNorm = amount / (POLISH_MAX || 1);
    /* Fill = set amount only. Live GR is audio work — never drive the meter
       like a spectrum/visualizer. Spectrum lives in #audio-viz above. */
    el.level.style.setProperty(
      "--compress",
      String(Math.max(0, Math.min(1, amountNorm)))
    );
    el.level.setAttribute("aria-valuenow", String(pct));
    el.level.setAttribute("aria-label", "Compression amount");
    el.level.setAttribute("aria-valuetext", `Compression amount ${pct} percent`);
    el.level.setAttribute("aria-orientation", "horizontal");
    el.level.classList.toggle("is-active", pct > 0);
    el.level.classList.toggle("is-unavailable", !state.polishCanHear);
    const gr = document.getElementById("compress-gr");
    if (gr) {
      gr.textContent = String(pct);
      gr.dataset.unit = "amt";
    }
    const stepsGr = document.getElementById("compress-steps-gr");
    if (stepsGr) stepsGr.textContent = `${pct}%`;
    document.querySelectorAll(".compress-step").forEach((btn) => {
      const step = btn.dataset.compressStep;
      let on = false;
      if (step === "low") on = pct <= 18;
      else if (step === "mid") on = pct > 18 && pct < 62;
      else if (step === "high") on = pct >= 62;
      btn.setAttribute("aria-pressed", on ? "true" : "false");
    });
    if (!state.compressDrag) {
      el.level.setAttribute("data-tip", compressTipText());
    }
  }

  let compressMeterRaf = 0;
  let audioVizRaf = 0;
  let audioVizBuf = null;

  function drawAudioVisualizer() {
    const canvas = document.getElementById("audio-viz");
    if (!canvas) return;
    const ctx2d = canvas.getContext("2d");
    if (!ctx2d) return;
    const w = canvas.width;
    const h = canvas.height;
    ctx2d.clearRect(0, 0, w, h);

    const polish = state.polish;
    const analyser =
      polish && typeof polish.getVizAnalyser === "function"
        ? polish.getVizAnalyser()
        : null;
    if (
      !analyser ||
      !state.playing ||
      state.audioMode !== "local" ||
      !state.polishCanHear
    ) {
      ctx2d.fillStyle = "rgba(255,250,242,0.12)";
      for (let i = 0; i < 16; i++) {
        const bh = 2;
        ctx2d.fillRect(4 + i * 12, h - bh - 2, 6, bh);
      }
      return;
    }
    if (!audioVizBuf || audioVizBuf.length !== analyser.frequencyBinCount) {
      audioVizBuf = new Uint8Array(analyser.frequencyBinCount);
    }
    analyser.getByteFrequencyData(audioVizBuf);
    const bars = 18;
    const step = Math.max(1, Math.floor(audioVizBuf.length / bars));
    const gap = 2;
    const barW = Math.max(3, (w - gap * (bars + 1)) / bars);
    for (let i = 0; i < bars; i++) {
      let sum = 0;
      for (let j = 0; j < step; j++) sum += audioVizBuf[i * step + j] || 0;
      const v = sum / (step * 255);
      const bh = Math.max(2, v * (h - 4));
      const x = gap + i * (barW + gap);
      ctx2d.fillStyle =
        i < bars * 0.55
          ? "rgba(120, 220, 160, 0.85)"
          : i < bars * 0.8
            ? "rgba(255, 210, 90, 0.88)"
            : "rgba(255, 100, 70, 0.9)";
      ctx2d.fillRect(x, h - bh - 1, barW, bh);
    }
  }

  function startCompressMeterLoop() {
    if (compressMeterRaf) return;
    const tick = () => {
      compressMeterRaf = 0;
      if (!el.level) return;
      syncCompressUI();
      drawAudioVisualizer();
      if (state.playing && state.audioMode === "local" && state.polishCanHear) {
        compressMeterRaf = requestAnimationFrame(tick);
      }
    };
    compressMeterRaf = requestAnimationFrame(tick);
  }

  function stopCompressMeterLoop() {
    if (compressMeterRaf) {
      cancelAnimationFrame(compressMeterRaf);
      compressMeterRaf = 0;
    }
    drawAudioVisualizer();
  }

  function applyPolishAmount(amount, { persist = true, log = false } = {}) {
    const next = clampPolish(amount);
    state.polishAmount = next;
    if (next < 0.12) state.polishPreset = "soft";
    else if (next < 0.62) state.polishPreset = "medium";
    else state.polishPreset = "hard";

    const polish = state.polish;
    if (polish) {
      if (typeof polish.setAmount === "function") polish.setAmount(next);
      else if (typeof polish.applyPolishMacro === "function") polish.applyPolishMacro(next);
    }

    syncCompressUI();

    if (persist) {
      try {
        localStorage.setItem(STORAGE_POLISH_AMT, String(next));
        localStorage.setItem(STORAGE_POLISH, state.polishPreset);
      } catch {
        /* ignore */
      }
    }
    if (log) {
      logEvent("polish_amount", { amount: next, pct: polishPct(next) });
    }
  }

  function readSavedPolishAmount() {
    try {
      const rawAmt = localStorage.getItem(STORAGE_POLISH_AMT);
      if (rawAmt != null && rawAmt !== "") {
        const n = Number(rawAmt);
        if (Number.isFinite(n)) {
          const clamped = clampPolish(n);
          // Stuck near 100% / hard ceiling → hissy; reset to ~25% default
          if (clamped >= POLISH_MAX * 0.9) {
            try {
              localStorage.setItem(STORAGE_POLISH_AMT, String(POLISH_DEFAULT));
              localStorage.setItem(STORAGE_POLISH, "medium");
            } catch {
              /* ignore */
            }
            return POLISH_DEFAULT;
          }
          return clamped;
        }
      }
      const legacy = localStorage.getItem(STORAGE_POLISH);
      if (legacy === "soft") return 0.08;
      if (legacy === "hard") {
        // Do not restore full Hard from legacy preset — that was the noisy default path
        try {
          localStorage.setItem(STORAGE_POLISH_AMT, String(POLISH_DEFAULT));
          localStorage.setItem(STORAGE_POLISH, "medium");
        } catch {
          /* ignore */
        }
        return POLISH_DEFAULT;
      }
      if (legacy === "medium") return POLISH_DEFAULT;
    } catch {
      /* ignore */
    }
    return POLISH_DEFAULT;
  }

  function wireCompressGesture(btn) {
    const endDrag = (e) => {
      const drag = state.compressDrag;
      if (!drag) return;
      state.compressDrag = null;
      btn.classList.remove("is-dragging");
      try {
        if (drag.pointerId != null) btn.releasePointerCapture(drag.pointerId);
      } catch {
        /* ignore */
      }
      applyPolishAmount(state.polishAmount, { persist: true, log: true });
      btn.setAttribute("data-tip", compressTipText());
      if (e) e.preventDefault();
    };

    btn.addEventListener("pointerdown", (e) => {
      if (e.button != null && e.button !== 0) return;
      e.preventDefault();
      hideTip(true);
      state.compressDrag = {
        pointerId: e.pointerId,
        startX: e.clientX,
        startY: e.clientY,
        startAmount: state.polishAmount,
        horizontal: true,
        moved: false,
      };
      btn.classList.add("is-dragging");
      try {
        btn.setPointerCapture(e.pointerId);
      } catch {
        /* ignore */
      }
    });

    btn.addEventListener("pointermove", (e) => {
      const drag = state.compressDrag;
      if (!drag || drag.pointerId !== e.pointerId) return;
      const horizontal = drag.horizontal === true;
      const deltaPx = horizontal ? e.clientX - drag.startX : drag.startY - e.clientY;
      if (Math.abs(deltaPx) > 3) drag.moved = true;
      const delta = deltaPx / POLISH_DRAG_PX;
      const next = clampPolish(drag.startAmount + delta * POLISH_MAX);
      applyPolishAmount(next, { persist: false });
      btn.setAttribute("data-tip", `Compress ${polishPct(next)}%`);
      if (state.tipEl) {
        state.tipEl.textContent = `Compress ${polishPct(next)}%`;
        placeTip(state.tipEl, btn, e.clientX, e.clientY);
      } else {
        showTip(btn, `Compress ${polishPct(next)}%`, e.clientX, e.clientY);
      }
      e.preventDefault();
    });

    btn.addEventListener("pointerup", endDrag);
    btn.addEventListener("pointercancel", endDrag);
    btn.addEventListener("lostpointercapture", () => {
      if (state.compressDrag) endDrag();
    });

    btn.addEventListener("keydown", (e) => {
      let step = 0;
      if (e.code === "ArrowUp" || e.code === "ArrowRight") step = 0.06;
      else if (e.code === "ArrowDown" || e.code === "ArrowLeft") step = -0.06;
      else if (e.code === "Home") {
        applyPolishAmount(0, { persist: true, log: true });
        e.preventDefault();
        return;
      } else if (e.code === "End") {
        applyPolishAmount(POLISH_MAX, { persist: true, log: true });
        e.preventDefault();
        return;
      } else return;
      applyPolishAmount(state.polishAmount + step, { persist: true, log: true });
      e.preventDefault();
    });
  }

  function initPolish() {
    getDeviceId();
    readXfadeExp();
    logXfadeConfig();
    state.polishAmount = readSavedPolishAmount();

    try {
      state.loopTrack = localStorage.getItem(STORAGE_LOOP) === "1";
    } catch {
      state.loopTrack = false;
    }
    syncLoopButton();

    if (!window.TypeBeatPolish || typeof window.TypeBeatPolish.createPolish !== "function") {
      syncCompressUI();
      return;
    }

    state.polish = window.TypeBeatPolish.createPolish();
    applyPolishAmount(state.polishAmount, { persist: false });
    setPolishHearable(false);
    wireLocalAudioEvents();
    // Wire dual graph before first play so crossfade is reachable immediately.
    ensurePolishConnected();
  }

  // YouTube IFrame API — fallback when local extract fails
  window.onYouTubeIframeAPIReady = function onYouTubeIframeAPIReady() {
    const first = currentTrack();
    state.player = new YT.Player("yt-host", {
      height: "0",
      width: "0",
      videoId: first ? first.video_id : undefined,
      playerVars: {
        autoplay: 0,
        controls: 0,
        rel: 0,
        playsinline: 1,
      },
      events: {
        onReady: () => {
          try {
            if (typeof state.player.mute === "function") state.player.mute();
          } catch {
            /* ignore */
          }
          setPlayingUI(false);
          markTrackStart();
        },
        onStateChange: (event) => {
          if (state.audioMode === "local") {
            if (event.data === YT.PlayerState.PLAYING) {
              pauseIframe();
            }
            return;
          }
          if (event.data === YT.PlayerState.ENDED) {
            if (state.loopTrack) {
              restartCurrentTrack("loop");
              return;
            }
            // Ignore ENDED from cue/swap when iframe is not the active playing path.
            if (state.audioMode !== "iframe" || !state.playing) return;
            if (state.navLock.busy || state.transitioning || state.loadingQueue) return;
            logEvent("ended");
            advanceTrack(1, "ended");
          } else if (event.data === YT.PlayerState.PLAYING) {
            setPlayingUI(true);
            if (!state.trackStartedAt) markTrackStart();
          } else if (event.data === YT.PlayerState.PAUSED) {
            // Ignore cue/load pauses during track handoff — keep pause glyph.
            if (state.transitioning) return;
            setPlayingUI(false, { force: true });
          }
        },
        onError: () => {
          if (state.audioMode !== "iframe") return;
          if (state.navLock.busy || state.transitioning || state.loadingQueue) {
            const t = currentTrack();
            if (t && t.video_id) {
              pendingUnplayableSkip = { videoId: t.video_id, reason: "dead_track" };
            }
            return;
          }
          logEvent("embed_error");
          requestSkipUnplayable("dead_track");
        },
      },
    });
  };

  function injectYT() {
    const tag = document.createElement("script");
    tag.src = "https://www.youtube.com/iframe_api";
    document.head.appendChild(tag);
  }

  async function boot() {
    document.documentElement.style.setProperty("--fade-ms", `${ART_FADE_MS}ms`);
    document.documentElement.style.setProperty("--art-fade-ms", `${ART_FADE_MS}ms`);
    document.documentElement.style.setProperty("--title-fade-ms", `${ART_FADE_MS}ms`);
    // Belt-and-suspenders: never allow native image drag on cover / thumbs
    [el.artA, el.artB, el.prevThumb, el.nextThumb].forEach((img) => {
      if (!img) return;
      img.draggable = false;
      img.setAttribute("draggable", "false");
      img.addEventListener("dragstart", (e) => e.preventDefault());
    });
    if (el.playGlyph) {
      el.artBtn.removeAttribute("data-tip");
      if (!el.playGlyph.getAttribute("data-tip")) {
        el.playGlyph.setAttribute("data-tip", "Play Or Pause");
      }
    }
    wireControls();
    syncNavControls();
    wireInviteUi();
    wireTips();
    wireListenLifecycle();
    initPolish();
    el.artBtn.classList.add("is-paused");
    try {
      await loadAuthStatus();
      handleAuthQueryParams();
      await probeLocalAudioTools();
      await loadGenres();
      await fetchQueue(state.genreId);
      injectYT();
    } catch (err) {
      console.error(err);
    }
  }

  boot();
})();
