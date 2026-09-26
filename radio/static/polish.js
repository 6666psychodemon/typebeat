/**
 * TypeBeat Radio — Polish (loudness glue for amateur YT levels).
 *
 * Signal chain (serial):
 *   dual xfade → auto EQ (M/S peaking cuts) → compressor → limiter → out
 *
 * Continuous macro amount p ∈ [0, MAX_P]:
 *   Soft  p≈0.08  — light EQ, gentle glue, polite ceiling
 *   Level p≈0.45  — audible punch + loudness match
 *   Hard  p≈0.82  — strong crush (ceiling slightly softer than old p=1)
 *
 * Limiter sits last for true-peak-ish control across wildly uneven uploads.
 * No parallel crush path — keeps the chain predictable for A/B.
 *
 * Graph needs same-origin MediaElement (local /api/audio). Dual <audio>
 * hosts + xfadeGainA/B do true overlapping crossfades (~7s). YouTube IFrame
 * PCM is cross-origin and cannot be tapped — iframe path is volume-fade only.
 */
(function (global) {
  const EQ_BANDS = 6;
  const EQ_LO_HZ = 1200;
  const EQ_HI_HZ = 15000;
  const EQ_MAX_CUT_DB = 14;
  /** Softened hard ceiling — was 1.0; a notch less limiter aggression. */
  const MAX_P = 0.82;

  /**
   * Measured-ish output/input ratios for makeup after serial compressor
   * (limiter follows; makeup targets pre-limiter level).
   * Points at amount 0 / 0.5 / 1.0 with makeup pinned to 1.
   */
  const COMP_LEVEL = [1.0, 0.72, 0.48];

  const PRESETS = {
    soft: { id: "soft", label: "Soft", p: 0.08 },
    medium: { id: "medium", label: "Level", p: 0.45 },
    hard: { id: "hard", label: "Hard", p: MAX_P },
  };

  function clamp01(x) {
    return Math.min(1, Math.max(0, x));
  }

  function safeHz(f, ctx) {
    const ny = (ctx.sampleRate || 44100) * 0.49;
    return Math.max(20, Math.min(ny, f));
  }

  function lerp3(table, amount) {
    const a = clamp01(amount);
    if (a < 0.5) return table[0] + (table[1] - table[0]) * (a / 0.5);
    return table[1] + (table[2] - table[1]) * ((a - 0.5) / 0.5);
  }

  function createPolish() {
    const conf = {
      polish: 0.45,
      compAmount: 0,
      autoEqAmount: 0,
      autoMakeup: 0,
      limitAmount: 0,
      msAutoEq: true,
    };

    let ctx = null;
    let input = null;
    let mediaSourceA = null;
    let mediaSourceB = null;
    let xfadeGainA = null;
    let xfadeGainB = null;
    let eqIn = null;
    let eqAnalyser = null;
    let eqBuf = null;
    let eqPrefix = null;
    let midBands = [];
    let sideBands = [];
    let masterComp = null;
    let makeupGain = null;
    let limiter = null;
    let outputGain = null;
    let vizAnalyser = null;
    let eqWasActive = false;
    let autoEqLast = 0;
    let makeupLast = -1;
    let raf = 0;
    let active = false;
    let sourceKind = "none"; // none | media | dual | node
    /** @type {'a'|'b'} */
    let activeSlot = "a";
    /** Master fade multiplier (play/pause soft edges). 0…1 */
    let masterFade = 1;
    let masterFadeTimer = 0;

    function ensureContext() {
      if (ctx) return ctx;
      const AC = window.AudioContext || window.webkitAudioContext;
      if (!AC) throw new Error("Web Audio API unavailable");
      ctx = new AC();
      return ctx;
    }

    function buildGraph() {
      ensureContext();
      if (input) return;

      input = ctx.createGain();
      input.gain.value = 1;

      xfadeGainA = ctx.createGain();
      xfadeGainB = ctx.createGain();
      xfadeGainA.gain.value = 1;
      xfadeGainB.gain.value = 0.0001;
      xfadeGainA.connect(input);
      xfadeGainB.connect(input);

      // --- Auto EQ analyser (pre-cut) ---
      eqIn = ctx.createGain();
      eqAnalyser = ctx.createAnalyser();
      eqAnalyser.fftSize = 2048;
      eqAnalyser.smoothingTimeConstant = 0.5;
      eqBuf = new Float32Array(eqAnalyser.frequencyBinCount);
      eqPrefix = new Float32Array(eqAnalyser.frequencyBinCount + 1);
      eqIn.connect(eqAnalyser);

      // --- Mid/side peaking cuts ---
      const msSplit = ctx.createChannelSplitter(2);
      const msMerge = ctx.createChannelMerger(2);
      const midBus = ctx.createGain();
      const sideBus = ctx.createGain();
      eqIn.connect(msSplit);

      const mk = (g) => {
        const n = ctx.createGain();
        n.gain.value = g;
        return n;
      };
      const mL = mk(0.5);
      const mR = mk(0.5);
      const sL = mk(0.5);
      const sR = mk(-0.5);
      msSplit.connect(mL, 0);
      mL.connect(midBus);
      msSplit.connect(mR, 1);
      mR.connect(midBus);
      msSplit.connect(sL, 0);
      sL.connect(sideBus);
      msSplit.connect(sR, 1);
      sR.connect(sideBus);

      const sideHP = ctx.createBiquadFilter();
      sideHP.type = "highpass";
      sideHP.frequency.value = safeHz(120, ctx);

      midBands = [];
      sideBands = [];
      const buildBands = (into) => {
        for (let i = 0; i < EQ_BANDS; i++) {
          const b = ctx.createBiquadFilter();
          b.type = "peaking";
          b.frequency.value = safeHz(1500 + i * 1200, ctx);
          b.Q.value = 6;
          b.gain.value = 0;
          into.push(b);
        }
      };
      buildBands(midBands);
      buildBands(sideBands);

      let mt = midBus;
      midBands.forEach((b) => {
        mt.connect(b);
        mt = b;
      });
      let st = sideBus;
      st.connect(sideHP);
      st = sideHP;
      sideBands.forEach((b) => {
        st.connect(b);
        st = b;
      });

      const outML = mk(1);
      const outMR = mk(1);
      const outSL = mk(1);
      const outSR = mk(-1);
      mt.connect(outML);
      outML.connect(msMerge, 0, 0);
      mt.connect(outMR);
      outMR.connect(msMerge, 0, 1);
      st.connect(outSL);
      outSL.connect(msMerge, 0, 0);
      st.connect(outSR);
      outSR.connect(msMerge, 0, 1);

      // --- Compressor (glue) ---
      masterComp = ctx.createDynamicsCompressor();
      masterComp.attack.value = 0.008;
      masterComp.release.value = 0.18;
      masterComp.knee.value = 10;

      makeupGain = ctx.createGain();
      makeupGain.gain.value = 1;

      // --- Limiter (ceiling) — last stage ---
      limiter = ctx.createDynamicsCompressor();
      limiter.threshold.value = -3;
      limiter.ratio.value = 20;
      limiter.attack.value = 0.001;
      limiter.release.value = 0.08;
      limiter.knee.value = 0.5;

      outputGain = ctx.createGain();
      outputGain.gain.value = 1;

      // Spectrum tap for the UI visualizer (separate from compressor meter).
      vizAnalyser = ctx.createAnalyser();
      vizAnalyser.fftSize = 256;
      vizAnalyser.smoothingTimeConstant = 0.72;

      // Chain: EQ → compressor → makeup → limiter → out (+ viz tap)
      input.connect(eqIn);
      msMerge.connect(masterComp);
      masterComp.connect(makeupGain);
      makeupGain.connect(limiter);
      limiter.connect(outputGain);
      outputGain.connect(ctx.destination);
      outputGain.connect(vizAnalyser);

      applyPolishMacro(conf.polish);
      active = true;
      tick();
    }

    function applyCompressor() {
      if (!masterComp) return;
      const x = clamp01(conf.compAmount);
      const t = ctx.currentTime;
      // Longer τ avoids zipper noise when the amount slider moves
      const tau = 0.12;
      // Audible DynamicsCompressor: deeper threshold / higher ratio as amount rises
      masterComp.threshold.setTargetAtTime(-8 - 26 * x, t, tau);
      masterComp.ratio.setTargetAtTime(1.6 + 8.4 * x, t, tau);
      masterComp.knee.setTargetAtTime(12 - 10 * x, t, tau);
      masterComp.attack.setTargetAtTime(0.01 - 0.007 * x, t, tau);
      masterComp.release.setTargetAtTime(0.2 - 0.09 * x, t, tau);
      applyMakeup();
      applyLimiter();
    }

    function applyLimiter() {
      if (!limiter) return;
      const x = clamp01(conf.limitAmount);
      const t = ctx.currentTime;
      const tau = 0.1;
      limiter.threshold.setTargetAtTime(-1.2 - 4.4 * x, t, tau);
      limiter.ratio.setTargetAtTime(12 + 7.5 * x, t, tau);
      limiter.attack.setTargetAtTime(0.002 - 0.001 * x, t, tau);
      limiter.release.setTargetAtTime(0.12 - 0.04 * x, t, tau);
      if (outputGain) {
        const trim = 1 - 0.09 * x;
        outputGain.gain.setTargetAtTime(trim * masterFade, t, 0.08);
      }
    }

    function applyMakeup() {
      if (!makeupGain) return;
      const x = clamp01(conf.compAmount);
      const amt = clamp01(conf.autoMakeup === undefined ? 0.7 : conf.autoMakeup);
      const loss = lerp3(COMP_LEVEL, x);
      const auto = Math.pow(loss > 0.05 ? 1 / loss : 1, amt);
      const target = Math.max(0.25, Math.min(1.85, auto));
      if (makeupLast > 0 && Math.abs(target - makeupLast) < makeupLast * 0.015) return;
      makeupLast = target;
      makeupGain.gain.setTargetAtTime(target, ctx.currentTime, 0.09);
    }

    function applyPolishMacro(p) {
      conf.polish = Math.min(MAX_P, clamp01(p));
      // Soft barely touches; Hard is unmistakably EQ'd + crushed + limited
      // Softened makeup / EQ curves to avoid hiss at higher amounts
      conf.compAmount = 0.05 + 0.78 * conf.polish;
      conf.autoEqAmount = 0.08 + 0.62 * conf.polish;
      conf.autoMakeup = 0.22 + 0.45 * conf.polish;
      conf.limitAmount = 0.1 + 0.7 * conf.polish;
      if (masterComp) applyCompressor();
    }

    function setAmount(p) {
      const next = Math.min(MAX_P, clamp01(p));
      // Skip no-op reapply — re-scheduling compressor params mid-audio clicks
      if (Math.abs(next - conf.polish) < 0.0008 && masterComp) {
        return conf.polish;
      }
      applyPolishMacro(next);
      return conf.polish;
    }

    function currentOutputTrim() {
      const x = clamp01(conf.limitAmount);
      return 1 - 0.09 * x;
    }

    /**
     * Soft play/pause edge on the polish bus (avoids hard zero-cross clicks).
     * Does not rebuild or reconnect the graph.
     */
    function fadeMaster(to, ms) {
      return new Promise((resolve) => {
        if (!outputGain || !ctx) {
          masterFade = Math.max(0, Math.min(1, to));
          resolve(false);
          return;
        }
        if (masterFadeTimer) {
          window.clearTimeout(masterFadeTimer);
          masterFadeTimer = 0;
        }
        const target = Math.max(0, Math.min(1, to));
        const dur = Math.max(0, Number(ms) || 0) / 1000;
        const t0 = ctx.currentTime;
        const trim = currentOutputTrim();
        const endVal = Math.max(0.0001, trim * target);
        try {
          outputGain.gain.cancelScheduledValues(t0);
          outputGain.gain.setValueAtTime(Math.max(0.0001, outputGain.gain.value), t0);
          if (dur <= 0.001) {
            outputGain.gain.setValueAtTime(target <= 0 ? 0.0001 : endVal, t0);
          } else if (target <= 0.001) {
            outputGain.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
          } else {
            outputGain.gain.linearRampToValueAtTime(endVal, t0 + dur);
          }
        } catch {
          outputGain.gain.value = target <= 0 ? 0.0001 : endVal;
        }
        masterFade = target;
        masterFadeTimer = window.setTimeout(() => {
          masterFadeTimer = 0;
          if (target <= 0.001 && outputGain) {
            try {
              outputGain.gain.setValueAtTime(0.0001, ctx.currentTime);
            } catch {
              /* ignore */
            }
          }
          resolve(true);
        }, Math.ceil(dur * 1000) + 12);
      });
    }

    function getMasterFade() {
      return masterFade;
    }

    function msFactors(f) {
      if (f < 300) return { mid: 1.0, side: 0.0 };
      if (f < 5000) return { mid: 0.72, side: 1.35 };
      if (f < 10000) return { mid: 0.9, side: 1.15 };
      return { mid: 1.0, side: 0.55 };
    }

    function autoEqTick(now) {
      if (!eqAnalyser || !midBands.length) return;
      const amt = conf.autoEqAmount;
      const t = ctx.currentTime;
      if (amt <= 0.001) {
        if (eqWasActive) {
          midBands.concat(sideBands).forEach((b) => b.gain.setTargetAtTime(0, t, 0.08));
          eqWasActive = false;
        }
        return;
      }
      eqWasActive = true;
      if (now - autoEqLast < 40) return;
      autoEqLast = now;

      eqAnalyser.getFloatFrequencyData(eqBuf);
      const n = eqBuf.length;
      const binHz = ctx.sampleRate / 2 / n;
      const lo = Math.max(2, Math.floor(EQ_LO_HZ / binHz));
      const hi = Math.min(n - 2, Math.ceil(safeHz(EQ_HI_HZ, ctx) / binHz));
      if (hi <= lo + 4) return;

      eqPrefix[0] = 0;
      for (let i = 0; i < n; i++) {
        const v = eqBuf[i];
        eqPrefix[i + 1] = eqPrefix[i] + (Number.isFinite(v) ? v : -140);
      }
      const avg = (a, b) => (eqPrefix[b + 1] - eqPrefix[a]) / (b - a + 1);

      const cands = [];
      for (let i = lo; i <= hi; i++) {
        const w = Math.max(5, Math.round(i * 0.16));
        const base = avg(Math.max(0, i - w), Math.min(n - 1, i + w));
        const excess = eqBuf[i] - base;
        if (excess < 4) continue;
        if (eqBuf[i] < eqBuf[i - 1] || eqBuf[i] < eqBuf[i + 1]) continue;
        cands.push({ f: i * binHz, excess, score: excess });
      }
      cands.sort((a, b) => b.score - a.score);

      const picked = [];
      for (const c of cands) {
        if (picked.length >= EQ_BANDS) break;
        if (picked.some((p) => Math.abs(Math.log2(p.f / c.f)) < 0.18)) continue;
        picked.push(c);
      }
      picked.sort((a, b) => a.f - b.f);

      const apply = (b, p, factor) => {
        if (!p || factor <= 0) {
          b.gain.setTargetAtTime(0, t, 0.12);
          return;
        }
        const cut = -Math.min(EQ_MAX_CUT_DB, (p.excess - 3) * amt * 1.25 * factor);
        b.frequency.setTargetAtTime(safeHz(p.f, ctx), t, 0.08);
        const goingDown = cut < b.gain.value;
        b.gain.setTargetAtTime(cut, t, goingDown ? 0.06 : 0.14);
      };

      for (let i = 0; i < EQ_BANDS; i++) {
        const p = picked[i];
        const f = p ? msFactors(p.f) : { mid: 1, side: 1 };
        apply(midBands[i], p, conf.msAutoEq ? f.mid : 1);
        apply(sideBands[i], p, conf.msAutoEq ? f.side : 1);
      }
    }

    function getReductionDb() {
      if (!masterComp) return 0;
      try {
        const r = masterComp.reduction;
        return Number.isFinite(r) ? r : 0;
      } catch {
        return 0;
      }
    }

    /** 0..1 live gain-reduction intensity for the meter UI. */
    function getReductionNorm() {
      const db = getReductionDb();
      /* reduction is negative dB (e.g. -12). Map ~0…-18dB → 0…1 */
      return Math.max(0, Math.min(1, (-db) / 18));
    }

    /** Spectrum analyser for the separate visualizer UI (not the compressor meter). */
    function getVizAnalyser() {
      if (!ctx || !outputGain) return null;
      if (!vizAnalyser) {
        try {
          buildGraph();
        } catch {
          return null;
        }
      }
      return vizAnalyser;
    }

    function tick(now) {
      if (!active) return;
      autoEqTick(now || performance.now());
      raf = requestAnimationFrame(tick);
    }

    async function resume() {
      ensureContext();
      if (ctx.state === "suspended") await ctx.resume();
    }

    function connectMediaElement(el) {
      try {
        buildGraph();
        if (mediaSourceA) {
          try {
            mediaSourceA.disconnect();
          } catch {
            /* already disconnected */
          }
          mediaSourceA = null;
        }
        mediaSourceA = ctx.createMediaElementSource(el);
        mediaSourceA.connect(xfadeGainA);
        const t = ctx.currentTime;
        xfadeGainA.gain.cancelScheduledValues(t);
        xfadeGainA.gain.setValueAtTime(1, t);
        if (xfadeGainB) {
          xfadeGainB.gain.cancelScheduledValues(t);
          xfadeGainB.gain.setValueAtTime(0.0001, t);
        }
        sourceKind = "media";
        activeSlot = "a";
        return { ok: true, reason: null };
      } catch (err) {
        sourceKind = "none";
        return {
          ok: false,
          reason: err && err.message ? err.message : String(err),
        };
      }
    }

    function connectDualMedia(elA, elB) {
      try {
        buildGraph();
        const firstWire = !mediaSourceA || !mediaSourceB;
        if (!mediaSourceA) {
          mediaSourceA = ctx.createMediaElementSource(elA);
          mediaSourceA.connect(xfadeGainA);
        }
        if (!mediaSourceB) {
          mediaSourceB = ctx.createMediaElementSource(elB);
          mediaSourceB.connect(xfadeGainB);
        }
        /* First wire only — re-entry must NOT cancelScheduledValues mid-crossfade
           (that caused blip → silence when ensurePolishConnected ran during ramp). */
        if (firstWire) {
          const t = ctx.currentTime;
          xfadeGainA.gain.cancelScheduledValues(t);
          xfadeGainB.gain.cancelScheduledValues(t);
          xfadeGainA.gain.setValueAtTime(activeSlot === "a" ? 1 : 0.0001, t);
          xfadeGainB.gain.setValueAtTime(activeSlot === "b" ? 1 : 0.0001, t);
        }
        sourceKind = "dual";
        return { ok: true, reason: null };
      } catch (err) {
        sourceKind = "none";
        return {
          ok: false,
          reason: err && err.message ? err.message : String(err),
        };
      }
    }

    function getActiveSlot() {
      return activeSlot;
    }

    function crossfadeTo(toSlot, ms) {
      return new Promise((resolve) => {
        if (!xfadeGainA || !xfadeGainB || !ctx) {
          resolve(false);
          return;
        }
        const to = toSlot === "b" ? "b" : "a";
        const dur = Math.max(0, Number(ms) || 0) / 1000;
        const t0 = ctx.currentTime;
        const outA = to === "a" ? 1 : 0.0001;
        const outB = to === "b" ? 1 : 0.0001;

        const curA = Math.max(0.0001, xfadeGainA.gain.value);
        const curB = Math.max(0.0001, xfadeGainB.gain.value);
        xfadeGainA.gain.cancelScheduledValues(t0);
        xfadeGainB.gain.cancelScheduledValues(t0);
        xfadeGainA.gain.setValueAtTime(curA, t0);
        xfadeGainB.gain.setValueAtTime(curB, t0);

        if (dur <= 0.001) {
          xfadeGainA.gain.setValueAtTime(outA, t0);
          xfadeGainB.gain.setValueAtTime(outB, t0);
          activeSlot = to;
          resolve(true);
          return;
        }

        /* Linear ramps (stitch-era) — continuous A↔B without curve discontinuities.
           Keep activeSlot on the outgoing deck until the ramp finishes so any
           mid-fade setActiveSlot(state.activeSlot) cannot snap the wrong way. */
        xfadeGainA.gain.linearRampToValueAtTime(outA, t0 + dur);
        xfadeGainB.gain.linearRampToValueAtTime(outB, t0 + dur);
        window.setTimeout(() => {
          activeSlot = to;
          resolve(true);
        }, Math.ceil(dur * 1000) + 20);
      });
    }

    /** Both graph gains at unity — element volume drives overlap (Exp volume xfade). */
    function setGraphGainsPassthrough() {
      if (!xfadeGainA || !xfadeGainB || !ctx) return;
      const t = ctx.currentTime;
      xfadeGainA.gain.cancelScheduledValues(t);
      xfadeGainB.gain.cancelScheduledValues(t);
      xfadeGainA.gain.setValueAtTime(1, t);
      xfadeGainB.gain.setValueAtTime(1, t);
    }

    function setActiveSlot(slot, ms) {
      if (!xfadeGainA || !xfadeGainB || !ctx) return;
      const to = slot === "b" ? "b" : "a";
      if (to === activeSlot && (ms == null || ms <= 0)) return;
      const durMs = ms == null ? 32 : Math.max(0, Number(ms) || 0);
      if (durMs > 1) {
        crossfadeTo(to, durMs);
        return;
      }
      const t = ctx.currentTime;
      xfadeGainA.gain.cancelScheduledValues(t);
      xfadeGainB.gain.cancelScheduledValues(t);
      xfadeGainA.gain.setValueAtTime(to === "a" ? 1 : 0.0001, t);
      xfadeGainB.gain.setValueAtTime(to === "b" ? 1 : 0.0001, t);
      activeSlot = to;
    }

    function connectNode(node) {
      buildGraph();
      node.connect(input);
      sourceKind = "node";
      return { ok: true, reason: null };
    }

    function setPreset(id) {
      const preset = PRESETS[id] || PRESETS.medium;
      applyPolishMacro(preset.p);
      return preset;
    }

    function getStatus() {
      return {
        active: Boolean(active && masterComp && limiter),
        sourceKind,
        canProcess: sourceKind === "media" || sourceKind === "dual" || sourceKind === "node",
        polish: conf.polish,
        compAmount: conf.compAmount,
        autoEqAmount: conf.autoEqAmount,
        autoMakeup: conf.autoMakeup,
        limitAmount: conf.limitAmount,
        activeSlot,
        chain: ["autoEQ", "compressor", "limiter"],
        presets: PRESETS,
      };
    }

    function dispose() {
      active = false;
      if (raf) cancelAnimationFrame(raf);
      raf = 0;
      if (masterFadeTimer) {
        window.clearTimeout(masterFadeTimer);
        masterFadeTimer = 0;
      }
      try {
        if (ctx) ctx.close();
      } catch {
        /* ignore */
      }
      ctx = null;
      input = null;
      mediaSourceA = null;
      mediaSourceB = null;
      xfadeGainA = null;
      xfadeGainB = null;
      limiter = null;
      outputGain = null;
      sourceKind = "none";
      masterFade = 1;
    }

    return {
      PRESETS,
      MAX_P,
      resume,
      buildGraph,
      connectMediaElement,
      connectDualMedia,
      crossfadeTo,
      setGraphGainsPassthrough,
      setActiveSlot,
      getActiveSlot,
      fadeMaster,
      getMasterFade,
      connectNode,
      setPreset,
      setAmount,
      applyPolishMacro,
      getReductionDb,
      getReductionNorm,
      getVizAnalyser,
      getStatus,
      dispose,
      get conf() {
        return conf;
      },
    };
  }

  global.TypeBeatPolish = { createPolish, PRESETS, MAX_P };
})(window);
