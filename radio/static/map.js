(function () {
  "use strict";

  const board = document.getElementById("board");
  const world = document.getElementById("world");
  const boardStatus = document.getElementById("board-status");
  const retry = document.getElementById("retry");
  const input = document.getElementById("q");
  const status = document.getElementById("q-status");
  const sheet = document.getElementById("sheet");
  const sheetTitle = document.getElementById("sheet-title");
  const sheetStored = document.getElementById("sheet-stored");
  const sheetRelation = document.getElementById("sheet-relation");
  const sheetDef = document.getElementById("sheet-def");
  const sheetDiffLabel = document.getElementById("sheet-diff-label");
  const sheetDiff = document.getElementById("sheet-diff");
  const sheetArtistsLabel = document.getElementById("sheet-artists-label");
  const sheetArtists = document.getElementById("sheet-artists");
  const sheetStation = document.getElementById("sheet-station");

  const SEED = {
    Alt: [180, 220],
    Trap: [520, 380],
    Rage: [900, 180],
    Drill: [920, 520],
    "2010s": [480, 760],
    Club: [160, 640],
    "Boom Bap": [1280, 340],
    "West Coast": [1660, 180],
    Southern: [1660, 540],
    Rap: [1280, 740],
    "90s": [1980, 320],
    "2000s": [2280, 150],
    "80s": [2300, 460],
    "R&B": [1980, 680],
    "Lo-fi": [2300, 760],
    Country: [2580, 460],
    Meme: [2580, 760],
    Underground: [2580, 160],
    UK: [980, 1020],
    Afro: [1360, 1060],
    Caribbean: [1760, 1060],
    Latin: [2220, 1100],
  };

  let nodes = [];
  let parents = [];
  let view = { x: 40, y: 80, zoom: 0.45 };
  let selectedKey = "";
  let drag = null;
  let suppressClick = false;
  const pointers = new Map();
  let pinch = null;

  function clamp(n, lo, hi) {
    return Math.max(lo, Math.min(hi, n));
  }

  function norm(value) {
    return String(value || "")
      .toLowerCase()
      .replace(/&/g, " and ")
      .replace(/[^a-z0-9]+/g, " ")
      .replace(/\s+/g, " ")
      .trim();
  }

  function linesFor(label) {
    const raw = String(label || "");
    if (raw.includes("/")) {
      return raw.split(/\s*\/\s*/).map((part) => part.trim()).filter(Boolean);
    }
    if (raw.includes("-") && raw.length > 12) {
      return raw.split("-").map((part) => part.trim()).filter(Boolean);
    }
    const words = raw.split(/\s+/).filter(Boolean);
    if (words.length <= 2) return words.length ? words : [raw];
    const mid = Math.ceil(words.length / 2);
    return [words.slice(0, mid).join(" "), words.slice(mid).join(" ")];
  }

  function subRadius(label) {
    const parts = String(label).split(/[\s/–-]+/).filter(Boolean);
    const longest = Math.max(...parts.map((part) => part.length), 3);
    return clamp(18 + longest * 2.4, 40, 58);
  }

  function matches(node, query) {
    const q = norm(query);
    if (!q) return false;
    const compact = q.replace(/ /g, "");
    const fields = [node.name, node.display, node.parentName];
    return fields.some((value) => {
      const text = norm(value);
      if (!text) return false;
      return text.includes(q) || text.replace(/ /g, "").includes(compact);
    });
  }

  function layout(data) {
    const built = [];
    let spill = 0;
    (data.parents || []).forEach((parent) => {
      if (!parent || !parent.name) return;
      const subs = (parent.subgenres || []).filter((sub) => sub && sub.name).map((sub) => {
        const display = sub.label || sub.name;
        return {
          kind: "sub",
          id: sub.id || sub.name,
          name: sub.name,
          display,
          parentName: parent.name,
          definition: sub.definition || "",
          differs: sub.differs || "",
          parentButton: parent.button !== false,
          r: subRadius(display),
        };
      });
      const n = Math.max(subs.length, 1);
      const maxSub = subs.reduce((m, sub) => Math.max(m, sub.r), 40);
      let radius = 122;
      if (n > 1) {
        const gap = 1.05;
        const step = (Math.PI * 2 - gap) / n;
        const orbit = (maxSub + 6) / Math.sin(step / 2);
        radius = Math.max(132, orbit + maxSub + 12);
      }
      const seed = SEED[parent.name] || [420 + spill * 300, 2200];
      if (!SEED[parent.name]) spill += 1;
      built.push({
        kind: "parent",
        id: parent.id || parent.name,
        name: parent.name,
        display: parent.name,
        parentName: parent.name,
        definition: parent.definition || "",
        differs: parent.differs || "",
        button: parent.button !== false,
        parentButton: parent.button !== false,
        r: radius,
        x: seed[0],
        y: seed[1],
        subs,
      });
    });

    for (let pass = 0; pass < 160; pass += 1) {
      for (let i = 0; i < built.length; i += 1) {
        for (let j = i + 1; j < built.length; j += 1) {
          const a = built[i];
          const b = built[j];
          let dx = b.x - a.x;
          let dy = b.y - a.y;
          let dist = Math.hypot(dx, dy) || 1;
          const need = a.r + b.r + 22;
          if (dist < need) {
            const push = (need - dist) / 2;
            dx /= dist;
            dy /= dist;
            a.x -= dx * push;
            a.y -= dy * push;
            b.x += dx * push;
            b.y += dy * push;
          }
        }
      }
    }

    built.forEach((parent) => {
      const subs = parent.subs;
      const n = subs.length;
      const gap = 1.05;
      const sweep = Math.PI * 2 - gap;
      const start = -Math.PI / 2 + gap / 2;
      subs.forEach((sub, index) => {
        const angle = n === 1 ? Math.PI / 2 : start + sweep * ((index + 0.5) / n);
        const orbit = n === 1 ? parent.r * 0.34 : parent.r - sub.r - 12;
        sub.x = parent.x + Math.cos(angle) * orbit;
        sub.y = parent.y + Math.sin(angle) * orbit;
        sub.key = `sub:${parent.name}:${sub.id}`;
      });
      parent.key = `parent:${parent.name}:${parent.id}`;
    });

    parents = built;
    nodes = [];
    built.forEach((parent) => {
      nodes.push(parent);
      parent.subs.forEach((sub) => nodes.push(sub));
    });
  }

  function bubbleButton(node) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = node.kind === "parent" ? "bubble bubble--parent is-settling" : "bubble bubble--sub is-settling";
    button.style.left = `${node.x - node.r}px`;
    button.style.top = `${node.y - node.r}px`;
    button.style.width = `${node.r * 2}px`;
    button.style.height = `${node.r * 2}px`;
    if (node.kind === "parent") {
      const lines = linesFor(node.display);
      const longest = Math.max(...lines.map((line) => line.length), 1);
      const size = clamp((node.r * 1.42) / longest, 13, 32);
      button.style.fontSize = `${size}px`;
      if (longest > 8) button.style.letterSpacing = "0";
    }
    button.style.animationDelay = `${Math.min(nodes.indexOf(node) * 14, 480)}ms`;
    const who = node.kind === "parent" ? `${node.display} parent` : `${node.display}, under ${node.parentName}`;
    button.setAttribute("aria-label", who);
    button.setAttribute("aria-pressed", "false");
    linesFor(node.display).forEach((line) => {
      const span = document.createElement("span");
      span.className = "bubble__line";
      span.textContent = line;
      button.appendChild(span);
    });
    button.addEventListener("animationend", () => button.classList.remove("is-settling"));
    button.addEventListener("click", (event) => {
      if (suppressClick) {
        suppressClick = false;
        event.preventDefault();
        return;
      }
      select(node);
    });
    node.el = button;
    return button;
  }

  function render() {
    world.replaceChildren();
    nodes.forEach((node) => world.appendChild(bubbleButton(node)));
  }

  function applyView() {
    world.style.transform = `translate(${view.x}px, ${view.y}px) scale(${view.zoom})`;
  }

  function boundsOf(list) {
    let minX = Infinity;
    let minY = Infinity;
    let maxX = -Infinity;
    let maxY = -Infinity;
    list.forEach((node) => {
      minX = Math.min(minX, node.x - node.r);
      minY = Math.min(minY, node.y - node.r);
      maxX = Math.max(maxX, node.x + node.r);
      maxY = Math.max(maxY, node.y + node.r);
    });
    return { x: minX, y: minY, w: Math.max(1, maxX - minX), h: Math.max(1, maxY - minY) };
  }

  function fit(list) {
    if (!list.length) return;
    const rect = board.getBoundingClientRect();
    const box = boundsOf(list);
    const padX = 36;
    const padTop = 92;
    const padBottom = sheet.hidden ? 28 : Math.min(rect.height * 0.42, 280);
    const zoom = clamp(Math.min((rect.width - padX * 2) / box.w, (rect.height - padTop - padBottom) / box.h), 0.2, 1.05);
    view.zoom = zoom;
    view.x = (rect.width - box.w * zoom) / 2 - box.x * zoom;
    view.y = padTop + (rect.height - padTop - padBottom - box.h * zoom) / 2 - box.y * zoom;
    applyView();
  }

  function zoomAt(clientX, clientY, factor) {
    const rect = board.getBoundingClientRect();
    const px = clientX - rect.left;
    const py = clientY - rect.top;
    const next = clamp(view.zoom * factor, 0.12, 2.8);
    const scale = next / view.zoom;
    view.x = px - (px - view.x) * scale;
    view.y = py - (py - view.y) * scale;
    view.zoom = next;
    applyView();
  }

  function clearSheet() {
    selectedKey = "";
    sheet.hidden = true;
    nodes.forEach((node) => {
      node.el.classList.remove("is-selected");
      node.el.setAttribute("aria-pressed", "false");
    });
  }

  function select(node) {
    selectedKey = node.key;
    nodes.forEach((item) => {
      const on = item.key === node.key;
      item.el.classList.toggle("is-selected", on);
      item.el.setAttribute("aria-pressed", on ? "true" : "false");
    });
    sheet.hidden = false;
    sheetTitle.textContent = node.display;
    if (node.display !== node.name) {
      sheetStored.hidden = false;
      sheetStored.textContent = `Stored as ${node.name}.`;
    } else {
      sheetStored.hidden = true;
      sheetStored.textContent = "";
    }
    if (node.kind === "sub") {
      sheetRelation.textContent = `${node.display} is under ${node.parentName}.`;
    } else {
      const count = node.subs.length;
      sheetRelation.textContent = count === 1
        ? "One style sits inside this bubble."
        : `${count} styles sit inside this bubble.`;
    }
    sheetDef.textContent = node.definition;
    const differs = node.differs;
    sheetDiffLabel.hidden = !differs;
    sheetDiff.hidden = !differs;
    sheetDiff.textContent = differs;
    sheetArtists.replaceChildren();
    sheetArtistsLabel.hidden = true;
    const thin = node.parentButton === false;
    sheetStation.hidden = !thin;
    sheetStation.textContent = thin ? "No radio button. It stays on this map." : "";
  }

  function paint(query) {
    const q = String(query || "").trim();
    if (!q) {
      nodes.forEach((node) => node.el.classList.remove("is-hit", "is-dim", "is-kin"));
      status.textContent = "";
      return 0;
    }
    const directParents = new Set();
    const hitSubs = new Set();
    nodes.forEach((node) => {
      if (!matches(node, q)) return;
      if (node.kind === "parent") directParents.add(node.name);
      else hitSubs.add(node.key);
    });
    let hits = 0;
    nodes.forEach((node) => {
      node.el.classList.remove("is-hit", "is-dim", "is-kin");
      const direct = node.kind === "parent"
        ? directParents.has(node.name)
        : hitSubs.has(node.key) || directParents.has(node.parentName);
      if (direct) {
        node.el.classList.add("is-hit");
        hits += 1;
      } else if (node.kind === "parent" && node.subs.some((sub) => hitSubs.has(sub.key))) {
        node.el.classList.add("is-kin");
      } else {
        node.el.classList.add("is-dim");
      }
    });
    status.textContent = hits ? `${hits} ${hits === 1 ? "bubble matches" : "bubbles match"}.` : "No bubble matches that.";
    return hits;
  }

  function matchedNodes() {
    return nodes.filter((node) => node.el.classList.contains("is-hit") || node.el.classList.contains("is-kin"));
  }

  board.addEventListener("pointerdown", (event) => {
    if (event.button !== 0) return;
    if (event.target.closest(".map-retry")) return;
    board.setPointerCapture(event.pointerId);
    pointers.set(event.pointerId, { x: event.clientX, y: event.clientY });
    if (pointers.size === 2) {
      const pts = [...pointers.values()];
      pinch = {
        dist: Math.hypot(pts[0].x - pts[1].x, pts[0].y - pts[1].y) || 1,
        zoom: view.zoom,
        cx: (pts[0].x + pts[1].x) / 2,
        cy: (pts[0].y + pts[1].y) / 2,
      };
      drag = null;
      return;
    }
    drag = {
      id: event.pointerId,
      x: event.clientX,
      y: event.clientY,
      ox: view.x,
      oy: view.y,
      moved: false,
    };
  });

  board.addEventListener("pointermove", (event) => {
    if (!pointers.has(event.pointerId)) return;
    pointers.set(event.pointerId, { x: event.clientX, y: event.clientY });
    if (pointers.size >= 2 && pinch) {
      const pts = [...pointers.values()];
      const dist = Math.hypot(pts[0].x - pts[1].x, pts[0].y - pts[1].y) || 1;
      const cx = (pts[0].x + pts[1].x) / 2;
      const cy = (pts[0].y + pts[1].y) / 2;
      const factor = dist / pinch.dist;
      view.zoom = pinch.zoom;
      zoomAt(cx, cy, factor);
      pinch.zoom = view.zoom;
      pinch.dist = dist;
      return;
    }
    if (!drag || drag.id !== event.pointerId) return;
    const dx = event.clientX - drag.x;
    const dy = event.clientY - drag.y;
    if (Math.hypot(dx, dy) > 5) {
      drag.moved = true;
      board.classList.add("is-panning");
    }
    if (!drag.moved) return;
    view.x = drag.ox + dx;
    view.y = drag.oy + dy;
    applyView();
  });

  function endPointer(event) {
    pointers.delete(event.pointerId);
    if (pointers.size < 2) pinch = null;
    if (drag && drag.id === event.pointerId) {
      const moved = drag.moved;
      drag = null;
      board.classList.remove("is-panning");
      if (moved) {
        suppressClick = true;
        setTimeout(() => {
          suppressClick = false;
        }, 0);
      }
      if (!moved && event.target === board) clearSheet();
    }
  }

  board.addEventListener("pointerup", endPointer);
  board.addEventListener("pointercancel", endPointer);

  board.addEventListener("wheel", (event) => {
    event.preventDefault();
    const factor = event.deltaY < 0 ? 1.08 : 0.92;
    zoomAt(event.clientX, event.clientY, factor);
  }, { passive: false });

  document.getElementById("zoom-in").addEventListener("click", () => {
    const rect = board.getBoundingClientRect();
    zoomAt(rect.left + rect.width / 2, rect.top + rect.height / 2, 1.18);
  });
  document.getElementById("zoom-out").addEventListener("click", () => {
    const rect = board.getBoundingClientRect();
    zoomAt(rect.left + rect.width / 2, rect.top + rect.height / 2, 1 / 1.18);
  });
  document.getElementById("zoom-fit").addEventListener("click", () => fit(parents));
  document.getElementById("sheet-close").addEventListener("click", clearSheet);

  input.addEventListener("input", () => paint(input.value));
  input.addEventListener("keydown", (event) => {
    if (event.key !== "Enter") return;
    event.preventDefault();
    const hits = paint(input.value);
    if (hits) fit(matchedNodes());
  });

  window.addEventListener("keydown", (event) => {
    const typing = event.target === input;
    if (event.key === "Escape") {
      clearSheet();
      if (typing) {
        input.value = "";
        paint("");
      }
      return;
    }
    if (typing) return;
    if (event.key === "+" || event.key === "=") {
      document.getElementById("zoom-in").click();
    } else if (event.key === "-" || event.key === "_") {
      document.getElementById("zoom-out").click();
    } else if (event.key === "0") {
      fit(parents);
    } else if (event.key === "/") {
      event.preventDefault();
      input.focus();
    }
  });

  window.addEventListener("resize", () => fit(parents));

  async function load() {
    boardStatus.hidden = false;
    boardStatus.textContent = "Loading the map.";
    retry.hidden = true;
    try {
      const response = await fetch("/api/taxonomy");
      if (!response.ok) throw new Error(String(response.status));
      const data = await response.json();
      if (!data || !Array.isArray(data.parents) || !data.parents.length) {
        throw new Error("empty");
      }
      layout(data);
      render();
      boardStatus.hidden = true;
      fit(parents);
    } catch (err) {
      boardStatus.hidden = false;
      boardStatus.textContent = "The genre map didn't load.";
      retry.hidden = false;
    }
  }

  retry.addEventListener("click", load);
  load();
})();
