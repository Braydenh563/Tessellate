// sketch-pad.js: Quick sketch, a small raster paint pad (INBOX 1352, the
// owner 2026-10-26: "prioritise the quick sketch improvements, redesign and
// extension ... I want to copy it to a separate repo"). Loaded on the first
// `openSketch` (media.js) with sketch-pad.css.
//
// **Self-contained on purpose.** Everything the pad needs from the app goes
// through the one `host` object handed to `SketchPad.open` (saving as a note,
// the toast, the confirm dialog, preferences, the menu and help recipes, the
// highlighter's numbers); `SKETCH_HOST_DEFAULTS` below is what it falls back
// to with no app, so `scratchpad/sketch-standalone/` runs it from three files.
// It builds its own markup into the element it is given and reads nothing
// global but `window`, `document` and the host.
//
// The tools are the ones every paint program teaches (the PaintZ and Ongkon
// audit in docs/roadmap/agent-remaining/paint-1026.md; ideas only, neither has
// a licence): a shape is drawn corner to corner, Alt draws it from its centre,
// Shift makes it square or round and snaps a line to 45 degrees; one letter
// picks each tool and every tooltip says which.

(() => {
  "use strict";

  //: What the pad asks of the page it lives in. Each member is optional; a
  //: missing one takes the value here, which is enough to run with no app.
  const SKETCH_HOST_DEFAULTS = {
    title: "Quick sketch",
    //: async (blob, caption) => void. Null hides Save as note.
    save: null,
    toast: null,
    confirm: async (message) => window.confirm(message),
    prefs: {
      get(key, fallback) {
        try {
          const raw = window.localStorage.getItem(`sketch-pad:${key}`);
          return raw === null ? fallback : JSON.parse(raw);
        } catch {
          return fallback;
        }
      },
      set(key, value) {
        try {
          window.localStorage.setItem(`sketch-pad:${key}`, JSON.stringify(value));
        } catch {
          /* private window or blocked storage: the setting lasts the visit */
        }
      },
    },
    //: The app hands over its own table (HIGHLIGHTER_STYLE, media.js), so the
    //: pad and the whiteboard keep one answer to "what is a highlighter".
    highlighter: { alpha: 0.4, widthMultiplier: 4, minWidth: 12, maxWidth: 24, blendOnLight: "multiply" },
    //: (items, label) => element. Null builds the pad's own small menu.
    menu: null,
    //: (button, panel) => void. Null toggles the panel on a press.
    wireHelp: null,
    singleKeys: () => true,
    //: Called once the pad has agreed to close (nothing unsaved, or confirmed).
    close: null,
  };

  const W = 960;
  const H = 600;
  const UNDO_DEPTH = 30;
  const ZOOMS = [0.25, 0.33, 0.5, 0.67, 0.75, 1, 1.25, 1.5, 2, 3, 4];
  const FILL_TOLERANCE = 32;
  const SWATCHES = [
    ["#1f2430", "Ink"], ["#6b7280", "Grey"], ["#ffffff", "White"], ["#ef4444", "Red"],
    ["#f97316", "Orange"], ["#eab308", "Yellow"], ["#22c55e", "Green"], ["#14b8a6", "Teal"],
    ["#3b82f6", "Blue"], ["#6366f1", "Indigo"], ["#a855f7", "Purple"], ["#ec4899", "Pink"],
  ];

  //: One row per tool: its key, its name, its icon, its help line, and
  //: whether a press paints from the pointer (`brush`) or draws a shape.
  const TOOLS = [
    { id: "select", key: "S", label: "Select", icon: "selection", group: "pick", tip: "drag a box, then drag it to move it; Delete clears it" },
    { id: "pencil", key: "P", label: "Pencil", icon: "pencil-simple", group: "draw", brush: true, tip: "hard edge; Shift draws a straight line" },
    { id: "brush", key: "B", label: "Brush", icon: "paint-brush", group: "draw", brush: true, tip: "soft, smoothed stroke; a pen's pressure sets the width" },
    { id: "highlighter", key: "H", label: "Highlighter", icon: "highlighter", group: "draw", brush: true, tip: "one see-through band" },
    { id: "eraser", key: "E", label: "Eraser", icon: "eraser", group: "draw", brush: true, tip: "rubs out ink, never the paper or the picture" },
    { id: "line", key: "L", label: "Line", icon: "line-segment", group: "shape", tip: "Shift snaps to 45 degrees, Alt draws from the middle" },
    { id: "arrow", key: "A", label: "Arrow", icon: "arrow-up-right", group: "shape", tip: "Shift snaps to 45 degrees" },
    { id: "rect", key: "R", label: "Rectangle", icon: "square", group: "shape", tip: "Shift for a square, Alt from the centre" },
    { id: "ellipse", key: "O", label: "Ellipse", icon: "circle", group: "shape", tip: "Shift for a circle, Alt from the centre" },
    { id: "polygon", key: "G", label: "Polygon", icon: "polygon", group: "shape", tip: "click each corner; double-click, Enter or the first corner closes it" },
    { id: "text", key: "T", label: "Text", icon: "text-t", group: "mark", tip: "click and type; Enter places it, Shift+Enter a new line" },
    { id: "fill", key: "F", label: "Fill", icon: "paint-bucket", group: "mark", tip: "fills the area under the pointer with the ink colour" },
    { id: "picker", key: "I", label: "Colour picker", icon: "eyedropper", group: "mark", tip: "takes the colour under the pointer; Alt does it with any tool" },
  ];
  const TOOL_BY_ID = new Map(TOOLS.map((t) => [t.id, t]));
  const SHAPES = new Set(["line", "arrow", "rect", "ellipse"]);

  // --- Pure geometry (tests/test_sketch_pad.py runs these in node) ----------

  //: The box a drag from (x0, y0) to (x, y) draws: corner to corner, or with
  //: Alt the press is the centre; Shift makes the sides equal, keeping the
  //: direction of the drag so the shape grows towards the pointer.
  function spBox(x0, y0, x, y, mods = {}) {
    let dx = x - x0;
    let dy = y - y0;
    if (mods.shift) {
      const side = Math.max(Math.abs(dx), Math.abs(dy));
      dx = Math.sign(dx || 1) * side;
      dy = Math.sign(dy || 1) * side;
    }
    if (mods.alt) return { x: x0 - Math.abs(dx), y: y0 - Math.abs(dy), w: 2 * Math.abs(dx), h: 2 * Math.abs(dy) };
    return { x: Math.min(x0, x0 + dx), y: Math.min(y0, y0 + dy), w: Math.abs(dx), h: Math.abs(dy) };
  }

  //: The point at the same distance from (x0, y0) on the nearest multiple of
  //: 45 degrees.
  function spSnap45(x0, y0, x, y) {
    const step = Math.PI / 4;
    const angle = Math.round(Math.atan2(y - y0, x - x0) / step) * step;
    const d = Math.hypot(x - x0, y - y0);
    return { x: x0 + Math.round(Math.cos(angle) * d * 1000) / 1000, y: y0 + Math.round(Math.sin(angle) * d * 1000) / 1000 };
  }

  //: A line's two ends: Shift snaps the far end, Alt mirrors it through the
  //: press so the press is the middle.
  function spLineEnds(x0, y0, x, y, mods = {}) {
    const end = mods.shift ? spSnap45(x0, y0, x, y) : { x, y };
    const start = mods.alt ? { x: 2 * x0 - end.x, y: 2 * y0 - end.y } : { x: x0, y: y0 };
    return { x1: start.x, y1: start.y, x2: end.x, y2: end.y };
  }

  //: The pixels a fill from (sx, sy) reaches: every 4-connected pixel whose
  //: colour is within `tol` of the seed's on each channel, then one pixel
  //: more, so the fill tucks under an antialiased edge instead of leaving a
  //: pale seam inside it. A scanline walk over typed arrays: a 960x600 sheet
  //: is under 20 ms.
  function spFloodMask(data, w, h, sx, sy, tol = FILL_TOLERANCE) {
    const mask = new Uint8Array(w * h);
    const p0 = (sy * w + sx) * 4;
    const seed = [data[p0], data[p0 + 1], data[p0 + 2], data[p0 + 3]];
    const near = (i) => {
      const p = i * 4;
      return Math.abs(data[p] - seed[0]) <= tol && Math.abs(data[p + 1] - seed[1]) <= tol
        && Math.abs(data[p + 2] - seed[2]) <= tol && Math.abs(data[p + 3] - seed[3]) <= tol;
    };
    const stack = [sx, sy];
    while (stack.length) {
      const y = stack.pop();
      let x = stack.pop();
      let i = y * w + x;
      if (mask[i]) continue;
      while (x > 0 && !mask[i - 1] && near(i - 1)) { x -= 1; i -= 1; }
      spFillRun(mask, near, stack, w, h, x, y);
    }
    return spGrow(mask, w, h);
  }

  //: One run of a scanline fill, rightwards from (x, y), queueing the first
  //: pixel of each run above and below it.
  function spFillRun(mask, near, stack, w, h, x, y) {
    let up = false;
    let down = false;
    for (let i = y * w + x; x < w && !mask[i] && near(i); x += 1, i += 1) {
      mask[i] = 1;
      if (y > 0) {
        const open = !mask[i - w] && near(i - w);
        if (open && !up) stack.push(x, y - 1);
        up = open;
      }
      if (y < h - 1) {
        const open = !mask[i + w] && near(i + w);
        if (open && !down) stack.push(x, y + 1);
        down = open;
      }
    }
  }

  function spGrow(mask, w, h) {
    const out = mask.slice();
    for (let y = 0; y < h; y += 1) {
      for (let x = 0; x < w; x += 1) {
        const i = y * w + x;
        if (mask[i]) continue;
        if ((x > 0 && mask[i - 1]) || (x < w - 1 && mask[i + 1]) || (y > 0 && mask[i - w]) || (y < h - 1 && mask[i + w])) out[i] = 1;
      }
    }
    return out;
  }

  function spHex(r, g, b) {
    return `#${[r, g, b].map((v) => v.toString(16).padStart(2, "0")).join("")}`;
  }

  function spRgb(hex) {
    const n = parseInt(hex.slice(1), 16);
    return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
  }

  // --- State ------------------------------------------------------------------

  const S = {
    host: SKETCH_HOST_DEFAULTS,
    root: null,
    el: {},
    tool: "pencil",
    lastTool: "pencil",
    ink: "#1f2430",
    fill: "#3b82f6",
    well: "ink",
    size: 4,
    mode: "outline",
    zoom: 1,
    fitted: true,
    undo: [],
    redo: [],
    drag: null,
    poly: null,
    sel: null,
    text: null,
    image: null,
    paper: "#ffffff",
    recent: [],
    dirty: false,
    open: false,
    rect: null,
    statusFrame: 0,
    status: { pos: "", size: "" },
  };

  // --- Markup -------------------------------------------------------------------

  //: An element from a tag, its attributes and its children. `on*` keys are
  //: listeners; everything else is an attribute. No innerHTML anywhere: the
  //: pad builds every node, so a caption or a colour cannot become markup.
  function h(tag, attrs = {}, ...children) {
    const el = document.createElement(tag);
    for (const [key, value] of Object.entries(attrs)) {
      if (value === null || value === undefined || value === false) continue;
      if (key.startsWith("on")) el.addEventListener(key.slice(2), value);
      else el.setAttribute(key, value === true ? "" : String(value));
    }
    for (const child of children.flat()) if (child !== null && child !== undefined) el.append(child);
    return el;
  }

  function icon(name) {
    return h("i", { class: `ph ph-${name}`, "aria-hidden": "true" });
  }

  //: A square icon button of the app's ghost recipe, its name and key in the
  //: tooltip as every other tool in the app has them.
  //: A tooltip says the name, the key, and for a tool what its modifiers do,
  //: so nothing has to be learned from the help panel first.
  function iconButton(name, label, onclick, { key = "", tip = "", extra = "", data = {} } = {}) {
    const title = (key ? `${label} (${key})` : label) + (tip ? `: ${tip}` : "");
    const attrs = { type: "button", class: `ghost icon-button sp-btn ${extra}`.trim(), title, "aria-label": label, onclick };
    if (key) attrs["aria-keyshortcuts"] = key;
    for (const [k, v] of Object.entries(data)) attrs[`data-${k}`] = v;
    return h("button", attrs, icon(name));
  }

  function buildHead() {
    const help = buildHelp();
    return h("div", { class: "dialog-head sp-head" },
      h("h2", { class: "dialog-head-title sp-title" }, icon("palette"), ` ${S.host.title}`),
      h("span", { class: "dialog-head-actions sp-head-actions" },
        help.button,
        h("button", { type: "button", class: "icon-only ghost small dialog-head-btn sp-btn", "data-sp": "close", title: "Close (Esc)", "aria-label": "Close", onclick: () => requestClose() }, icon("x"))),
      help.panel);
  }

  function buildHelp() {
    const button = h("button", {
      type: "button", class: "icon-only ghost small graph-help-toggle sp-btn", "data-sp": "help-toggle",
      "data-help-for": "sketch-help", "aria-controls": "sketch-help", "aria-expanded": "false",
      title: "About the sketch pad", "aria-label": "About the sketch pad",
    }, icon("question"));
    const keys = TOOLS.map((t) => h("li", {}, h("kbd", {}, t.key), ` ${t.label}: ${t.tip}`));
    const panel = h("div", { class: "help-body hidden sp-help", id: "sketch-help", role: "dialog", "aria-label": "About the sketch pad" },
      h("p", {}, "Pick a tool on the left or press its letter. Shapes draw corner to corner; Alt draws from the centre and Shift keeps them square, round or at 45 degrees. Esc cancels a shape in progress."),
      h("ul", { class: "sp-help-keys" }, keys),
      h("p", {}, "[ and ] change the size, X swaps the ink and fill colours, + and - zoom, 0 fits the page, Ctrl+Z undoes, Ctrl+Y redoes and Ctrl+A selects the whole page. Clear keeps the paper and any picture under the ink."));
    return { button, panel };
  }

  function buildTools() {
    const rail = h("div", { class: "sp-rail", role: "toolbar", "aria-label": "Tools", "aria-orientation": "vertical", "data-sp": "rail" });
    let group = null;
    let groupName = "";
    for (const tool of TOOLS) {
      if (tool.group !== groupName) {
        groupName = tool.group;
        group = h("div", { class: "sp-rail-group", role: "group" });
        rail.append(group);
      }
      group.append(iconButton(tool.icon, tool.label, () => setTool(tool.id), { key: tool.key, tip: tool.tip, extra: "sp-tool", data: { tool: tool.id } }));
    }
    return rail;
  }

  function buildColours() {
    const wells = h("div", { class: "sp-wells", role: "group", "aria-label": "Colours" },
      h("button", { type: "button", class: "sp-well sp-well-ink active", "data-sp": "well-ink", title: "Ink colour: lines, text, fill and outlines", "aria-label": "Ink colour", "aria-pressed": "true", onclick: () => setWell("ink") }),
      h("button", { type: "button", class: "sp-well sp-well-fill", "data-sp": "well-fill", title: "Fill colour: the inside of shapes", "aria-label": "Fill colour", "aria-pressed": "false", onclick: () => setWell("fill") }),
      iconButton("arrows-left-right", "Swap ink and fill", swapColours, { key: "X", extra: "sp-swap" }));
    const swatches = h("div", { class: "sp-swatches", role: "group", "aria-label": "Palette", "data-sp": "swatches" },
      SWATCHES.map(([hex, name]) => swatch(hex, name)));
    const recent = h("div", { class: "sp-swatches sp-recent", role: "group", "aria-label": "Recent colours", "data-sp": "recent" });
    const custom = h("label", { class: "sp-custom", title: "Any colour" },
      h("span", { class: "sp-visually-hidden" }, "Any colour"),
      h("input", { type: "color", "data-sp": "custom", value: S.ink, oninput: (e) => setColour(e.target.value), onchange: (e) => rememberColour(e.target.value) }),
      icon("plus"));
    return h("div", { class: "sp-group sp-colours" }, wells, swatches, recent, custom);
  }

  function swatch(hex, name) {
    const b = h("button", { type: "button", class: "sp-swatch", title: name, "aria-label": name, "data-colour": hex, onclick: () => setColour(hex) });
    b.style.background = hex;
    return b;
  }

  function buildStroke() {
    const size = h("label", { class: "sp-size", title: "Size ([ and ])" },
      h("span", { class: "sp-visually-hidden" }, "Size"),
      h("input", { type: "range", min: "1", max: "48", value: String(S.size), "data-sp": "size", "aria-keyshortcuts": "[ ]", oninput: (e) => setSize(Number(e.target.value)) }),
      h("output", { class: "sp-size-value", "data-sp": "size-value" }, String(S.size)));
    const modes = h("div", { class: "sp-modes", role: "group", "aria-label": "Shape style" },
      iconButton("square", "Outline only", () => setMode("outline"), { extra: "sp-mode", data: { mode: "outline" } }),
      iconButton("square-half", "Outline and fill", () => setMode("both"), { extra: "sp-mode", data: { mode: "both" } }),
      iconButton("square-fill", "Fill only", () => setMode("fill"), { extra: "sp-mode", data: { mode: "fill" } }));
    return h("div", { class: "sp-group sp-stroke" }, size, modes);
  }

  function buildActions() {
    const items = [
      { label: "Add a picture under the ink", run: () => S.el.image.click() },
      { label: "Paper colour", run: () => S.el.paper.click() },
      { label: "Download as PNG", run: () => downloadPng() },
      { label: "Clear the ink", danger: true, run: () => clearInk() },
    ];
    const menu = S.host.menu ? S.host.menu(items.map((i) => ({ ...i, title: i.label })), "More for this sketch") : fallbackMenu(items);
    return h("div", { class: "dock-actions sp-group sp-actions", role: "group", "aria-label": "The sheet" },
      iconButton("arrow-counter-clockwise", "Undo", undo, { key: "Ctrl+Z", data: { sp: "undo" } }),
      iconButton("arrow-clockwise", "Redo", redo, { key: "Ctrl+Y", data: { sp: "redo" } }),
      iconButton("trash", "Clear the ink", clearInk, { data: { sp: "clear" } }),
      menu,
      h("input", { type: "file", accept: "image/png, image/jpeg, image/gif, image/webp", class: "sp-hidden", "data-sp": "image", "aria-label": "Choose a picture to draw over", onchange: onImagePicked }),
      h("input", { type: "color", class: "sp-hidden", "data-sp": "paper", "aria-label": "Paper colour", value: S.paper, oninput: (e) => setPaper(e.target.value), onchange: (e) => S.host.prefs.set("paper", e.target.value) }));
  }

  //: The menu the pad draws when the page gives it none: a button, a list,
  //: Escape and an outside press close it.
  function fallbackMenu(items) {
    const list = h("div", { class: "sp-menu hidden", role: "menu" },
      items.map((item) => h("button", { type: "button", role: "menuitem", class: `sp-menu-row${item.danger ? " danger" : ""}`, onclick: () => { list.classList.add("hidden"); item.run(); } }, item.label)));
    const opener = iconButton("dots-three", "More for this sketch", () => {
      list.classList.toggle("hidden");
      opener.setAttribute("aria-expanded", String(!list.classList.contains("hidden")));
      if (!list.classList.contains("hidden")) list.querySelector("button")?.focus();
    });
    opener.setAttribute("aria-haspopup", "menu");
    opener.setAttribute("aria-expanded", "false");
    document.addEventListener("pointerdown", (e) => {
      if (!e.target.closest?.(".sp-menu-wrap")) list.classList.add("hidden");
    });
    list.addEventListener("keydown", (e) => {
      if (e.key !== "Escape") return;
      e.stopPropagation();
      list.classList.add("hidden");
      opener.focus();
    });
    return h("span", { class: "sp-menu-wrap" }, opener, list);
  }

  function buildStage() {
    const paper = h("canvas", { class: "sp-layer sp-paper", width: W, height: H, "data-sp": "paper-canvas" });
    const ink = h("canvas", { class: "sp-layer sp-ink", width: W, height: H, "data-sp": "ink-canvas", "aria-label": "Drawing area", role: "img" });
    const preview = h("canvas", { class: "sp-layer sp-preview", width: W, height: H, "data-sp": "preview" });
    const ring = h("div", { class: "sp-ring hidden", "data-sp": "ring", "aria-hidden": "true" });
    const stage = h("div", { class: "sp-stage", "data-sp": "stage" }, paper, ink, preview, ring);
    for (const [type, fn] of [["pointerdown", onDown], ["pointermove", onMove], ["pointerup", onUp], ["pointercancel", onCancelPointer], ["pointerleave", onLeave], ["dblclick", onDouble]]) {
      stage.addEventListener(type, fn);
    }
    const viewport = h("div", { class: "sp-viewport", "data-sp": "viewport", onwheel: onWheel, onscroll: () => { S.rect = null; } }, stage);
    return viewport;
  }

  function buildStatus() {
    return h("div", { class: "sp-status", "data-sp": "status-bar" },
      h("span", { class: "sp-readout", "data-sp": "pos", title: "Pointer position" }),
      h("span", { class: "sp-readout", "data-sp": "box", title: "Size of the shape or selection" }),
      h("span", { class: "sp-readout sp-dim", "data-sp": "dims", title: "Page size" }, `${W} × ${H} px`),
      h("span", { class: "sp-zoom", role: "group", "aria-label": "Zoom" },
        iconButton("magnifying-glass-minus", "Zoom out", () => stepZoom(-1), { key: "-" }),
        h("button", { type: "button", class: "ghost sp-zoom-value", "data-sp": "zoom", title: "Fit the page (0); press again for 100%", onclick: toggleFit }, "100%"),
        iconButton("magnifying-glass-plus", "Zoom in", () => stepZoom(1), { key: "+" })));
  }

  function buildFoot() {
    const saving = typeof S.host.save === "function";
    return h("div", { class: "sp-foot", "data-sp": "foot" },
      saving ? h("input", { type: "text", maxlength: "200", class: "sp-caption", "data-sp": "caption", placeholder: "Caption (becomes the note text)", "aria-label": "Caption for this sketch" }) : null,
      h("span", { class: "status sp-message", role: "status", "data-sp": "message" }),
      h("button", { type: "button", class: `${saving ? "ghost" : ""} sp-download`.trim(), "data-sp": "download", onclick: downloadPng }, icon("download-simple"), " Download PNG"),
      saving ? h("button", { type: "button", class: "sp-save", "data-sp": "save", onclick: saveNote }, "Save as note") : null);
  }

  function build(root) {
    root.replaceChildren();
    root.classList.add("sp-root");
    const bar = h("div", { class: "dock sp-bar", "data-dock-name": "sketch", role: "toolbar", "aria-label": "Colour, size and sheet" },
      buildColours(), buildStroke(), buildActions());
    const body = h("div", { class: "sp-body" }, buildTools(), buildStage());
    root.append(buildHead(), bar, body, buildStatus(), buildFoot());
    S.el = {};
    for (const node of root.querySelectorAll("[data-sp]")) S.el[camel(node.dataset.sp)] = node;
    S.el.inkCtx = S.el.inkCanvas.getContext("2d", { willReadFrequently: true });
    S.el.previewCtx = S.el.preview.getContext("2d");
    S.el.paperCtx = S.el.paperCanvas.getContext("2d");
    S.el.text = null;
    wireHelp();
  }

  function camel(name) {
    return name.replace(/-([a-z])/g, (_, c) => c.toUpperCase());
  }

  function wireHelp() {
    const button = S.el.helpToggle;
    const panel = S.root.querySelector("#sketch-help");
    if (S.host.wireHelp) {
      S.host.wireHelp(button, panel);
      return;
    }
    button.addEventListener("click", () => {
      const open = panel.classList.toggle("hidden") === false;
      button.setAttribute("aria-expanded", String(open));
    });
  }

  // --- Settings -------------------------------------------------------------------

  function setTool(id) {
    if (!TOOL_BY_ID.has(id)) return;
    commitText();
    if (id !== "select") commitSelection();
    cancelPolygon();
    if (id !== "picker") S.lastTool = id;
    S.tool = id;
    for (const b of S.root.querySelectorAll(".sp-tool")) {
      const on = b.dataset.tool === id;
      b.classList.toggle("active", on);
      b.setAttribute("aria-pressed", String(on));
    }
    S.el.stage.dataset.tool = id;
    S.el.ring.classList.add("hidden");
  }

  function setWell(which) {
    S.well = which;
    S.el.wellInk.classList.toggle("active", which === "ink");
    S.el.wellFill.classList.toggle("active", which === "fill");
    S.el.wellInk.setAttribute("aria-pressed", String(which === "ink"));
    S.el.wellFill.setAttribute("aria-pressed", String(which === "fill"));
    S.el.custom.value = which === "ink" ? S.ink : S.fill;
  }

  function setColour(hex) {
    if (S.well === "fill") S.fill = hex;
    else S.ink = hex;
    paintWells();
    if (S.text) S.text.input.style.color = S.ink;
  }

  function paintWells() {
    S.el.wellInk.style.background = S.ink;
    S.el.wellFill.style.background = S.fill;
    S.el.wellInk.title = `Ink colour ${S.ink}: lines, text, fill and outlines`;
    S.el.wellFill.title = `Fill colour ${S.fill}: the inside of shapes`;
    for (const b of S.root.querySelectorAll(".sp-swatch")) {
      b.classList.toggle("active", b.dataset.colour.toLowerCase() === (S.well === "fill" ? S.fill : S.ink).toLowerCase());
    }
    S.host.prefs.set("colours", { ink: S.ink, fill: S.fill });
  }

  function swapColours() {
    [S.ink, S.fill] = [S.fill, S.ink];
    paintWells();
    S.el.custom.value = S.well === "ink" ? S.ink : S.fill;
  }

  //: The last six picked with the colour well, newest first, kept between
  //: visits: a colour matched by eye is the one you come back for.
  function rememberColour(hex) {
    if (SWATCHES.some(([c]) => c === hex)) return;
    S.recent = [hex, ...S.recent.filter((c) => c !== hex)].slice(0, 6);
    S.host.prefs.set("recent", S.recent);
    paintRecent();
  }

  function paintRecent() {
    S.el.recent.replaceChildren(...S.recent.map((hex) => swatch(hex, `Recent ${hex}`)));
    S.el.recent.classList.toggle("sp-hidden", S.recent.length === 0);
  }

  function setSize(n) {
    S.size = Math.max(1, Math.min(48, Math.round(n)));
    S.el.size.value = String(S.size);
    S.el.sizeValue.textContent = String(S.size);
    if (S.text) S.text.input.style.fontSize = `${textPx() * S.zoom}px`;
  }

  function setMode(mode) {
    S.mode = mode;
    for (const b of S.root.querySelectorAll(".sp-mode")) {
      const on = b.dataset.mode === mode;
      b.classList.toggle("active", on);
      b.setAttribute("aria-pressed", String(on));
    }
  }

  function setPaper(hex) {
    S.paper = hex;
    drawPaper();
    S.dirty = true;
  }

  function drawPaper() {
    const ctx = S.el.paperCtx;
    ctx.fillStyle = S.paper;
    ctx.fillRect(0, 0, W, H);
    const img = S.image;
    if (!img) return;
    const scale = Math.min(W / img.width, H / img.height);
    const w = img.width * scale;
    const hh = img.height * scale;
    ctx.drawImage(img, (W - w) / 2, (H - hh) / 2, w, hh);
  }

  async function setImage(file) {
    if (!file) return;
    try {
      S.image = await createImageBitmap(file);
      drawPaper();
      S.dirty = true;
      say("");
    } catch {
      say("Couldn't load that picture.");
    }
  }

  function onImagePicked(e) {
    const file = e.target.files[0];
    e.target.value = "";
    setImage(file);
  }

  // --- Zoom -------------------------------------------------------------------------

  function applyZoom(z, anchor = null) {
    const vp = S.el.viewport;
    const before = anchor ? { x: (vp.scrollLeft + anchor.x) / S.zoom, y: (vp.scrollTop + anchor.y) / S.zoom } : null;
    S.zoom = Math.max(ZOOMS[0], Math.min(ZOOMS[ZOOMS.length - 1], z));
    S.el.stage.style.width = `${Math.round(W * S.zoom)}px`;
    S.el.stage.style.height = `${Math.round(H * S.zoom)}px`;
    S.el.zoom.textContent = `${Math.round(S.zoom * 100)}%`;
    S.rect = null;
    if (before) {
      vp.scrollLeft = before.x * S.zoom - anchor.x;
      vp.scrollTop = before.y * S.zoom - anchor.y;
    }
    placeText();
  }

  function fitZoom() {
    const vp = S.el.viewport;
    const room = Math.min((vp.clientWidth - 16) / W, (vp.clientHeight - 16) / H);
    return Math.max(ZOOMS[0], Math.min(1, room || 1));
  }

  function fit() {
    S.fitted = true;
    applyZoom(fitZoom());
  }

  function toggleFit() {
    if (S.fitted && Math.abs(S.zoom - 1) > 0.01) {
      S.fitted = false;
      applyZoom(1);
    } else fit();
  }

  function stepZoom(dir, anchor = null) {
    S.fitted = false;
    const next = dir > 0 ? ZOOMS.find((z) => z > S.zoom + 0.001) : [...ZOOMS].reverse().find((z) => z < S.zoom - 0.001);
    applyZoom(next ?? S.zoom, anchor);
  }

  function onWheel(e) {
    if (!(e.ctrlKey || e.metaKey)) return;
    e.preventDefault();
    const r = S.el.viewport.getBoundingClientRect();
    stepZoom(e.deltaY < 0 ? 1 : -1, { x: e.clientX - r.left, y: e.clientY - r.top });
  }

  // --- Pointer --------------------------------------------------------------------------

  //: The press in page pixels. The stage's box is read once per gesture and
  //: again only after a zoom or a scroll, so a stroke reads no layout per move.
  function point(e) {
    if (!S.rect) S.rect = S.el.inkCanvas.getBoundingClientRect();
    const r = S.rect;
    return { x: ((e.clientX - r.left) / r.width) * W, y: ((e.clientY - r.top) / r.height) * H };
  }

  function mods(e) {
    return { shift: e.shiftKey, alt: e.altKey };
  }

  function onDown(e) {
    if (e.button !== undefined && e.button !== 0) return;
    if (e.target.closest?.(".sp-text-editor")) return;
    e.preventDefault();
    S.rect = null;
    const p = point(e);
    if (e.altKey && TOOL_BY_ID.get(S.tool).brush) {
      pickColour(p);
      return;
    }
    const start = DOWN[S.tool];
    if (start) start(p, e);
    if (S.drag) S.el.stage.setPointerCapture?.(e.pointerId);
  }

  function onMove(e) {
    const p = point(e);
    showPos(p);
    moveRing(e, p);
    if (S.poly) {
      drawPolygonPreview(p, e);
      return;
    }
    if (!S.drag || S.drag.cancelled) return;
    const step = MOVE[S.drag.kind];
    if (step) {
      const events = e.getCoalescedEvents ? e.getCoalescedEvents() : [];
      if (S.drag.kind === "stroke" && events.length > 1) for (const ce of events) step(point(ce), ce);
      else step(p, e);
    }
  }

  function onUp(e) {
    const drag = S.drag;
    S.drag = null;
    if (!drag || drag.cancelled) return;
    const end = UP[drag.kind];
    if (end) end(point(e), e, drag);
    showBox("");
  }

  function onCancelPointer() {
    if (S.drag) cancelDrag();
  }

  function onLeave() {
    S.el.ring.classList.add("hidden");
    showPos(null);
  }

  function onDouble(e) {
    if (S.tool === "polygon" && S.poly) {
      e.preventDefault();
      closePolygon();
    }
  }

  //: The ring that shows a brush's width under the pointer: a positioned div,
  //: moved by a transform, so hovering paints nothing on the canvases.
  function moveRing(e, p) {
    const tool = TOOL_BY_ID.get(S.tool);
    const ring = S.el.ring;
    if (!tool.brush || e.pointerType === "touch") {
      ring.classList.add("hidden");
      return;
    }
    const d = Math.max(4, brushWidth(e) * S.zoom);
    ring.classList.remove("hidden");
    ring.style.width = `${d}px`;
    ring.style.height = `${d}px`;
    ring.style.transform = `translate(${p.x * S.zoom - d / 2}px, ${p.y * S.zoom - d / 2}px)`;
  }

  function brushWidth(e) {
    if (S.tool === "highlighter") return highlighterWidth();
    if (S.tool === "eraser") return S.size * 3;
    //: A pen's pressure, when the device reports one (0.5 is "no
    //: pressure" for a mouse, so it changes nothing there).
    const pressure = e && e.pointerType === "pen" && e.pressure > 0 ? e.pressure : 0.5;
    const scale = S.tool === "brush" ? 0.4 + pressure * 1.2 : 1;
    return Math.max(1, S.size * scale);
  }

  function highlighterWidth() {
    const hl = S.host.highlighter;
    return Math.min(hl.maxWidth, Math.max(hl.minWidth, S.size * hl.widthMultiplier));
  }

  // --- Brushes ----------------------------------------------------------------------------

  function startStroke(p, e) {
    pushUndo();
    S.drag = { kind: "stroke", x0: p.x, y0: p.y, points: [p], last: p, mid: p, cancelled: false };
    const ctx = strokeCtx();
    styleStroke(ctx, e);
    ctx.beginPath();
    ctx.moveTo(p.x, p.y);
    ctx.lineTo(p.x + 0.01, p.y);
    ctx.stroke();
    showPreviewAlpha();
  }

  //: The pencil, brush and highlighter draw on the preview layer and land on
  //: the ink when the stroke ends: a highlighter is one band at one alpha (the
  //: layer is shown at that alpha while it is drawn, so no frame repaints the
  //: stroke), and Escape can take any stroke back. The eraser works on the
  //: ink itself, since there is nothing to preview a hole on.
  function strokeCtx() {
    return S.tool === "eraser" ? S.el.inkCtx : S.el.previewCtx;
  }

  function styleStroke(ctx, e) {
    ctx.lineCap = S.tool === "highlighter" ? "square" : "round";
    ctx.lineJoin = "round";
    ctx.strokeStyle = S.ink;
    ctx.lineWidth = brushWidth(e);
    ctx.globalCompositeOperation = S.tool === "eraser" ? "destination-out" : "source-over";
    ctx.globalAlpha = 1;
    ctx.shadowBlur = S.tool === "brush" ? Math.min(8, S.size / 2) : 0;
    ctx.shadowColor = S.ink;
  }

  function showPreviewAlpha() {
    S.el.preview.style.opacity = S.tool === "highlighter" ? String(S.host.highlighter.alpha) : "1";
  }

  function moveStroke(p, e) {
    const d = S.drag;
    d.points.push(p);
    const ctx = strokeCtx();
    if (e.shiftKey && S.tool !== "eraser") {
      redrawStraight(d, p, e);
      return;
    }
    styleStroke(ctx, e);
    ctx.beginPath();
    if (S.tool === "brush") {
      const mid = { x: (d.last.x + p.x) / 2, y: (d.last.y + p.y) / 2 };
      ctx.moveTo(d.mid.x, d.mid.y);
      ctx.quadraticCurveTo(d.last.x, d.last.y, mid.x, mid.y);
      d.mid = mid;
    } else {
      ctx.moveTo(d.last.x, d.last.y);
      ctx.lineTo(p.x, p.y);
    }
    ctx.stroke();
    d.last = p;
  }

  //: Shift while drawing makes the stroke a straight line from where it
  //: started (snapped to 45 degrees), as the board's pens do.
  function redrawStraight(d, p, e) {
    const ctx = S.el.previewCtx;
    ctx.clearRect(0, 0, W, H);
    styleStroke(ctx, e);
    const end = spSnap45(d.x0, d.y0, p.x, p.y);
    ctx.beginPath();
    ctx.moveTo(d.x0, d.y0);
    ctx.lineTo(end.x, end.y);
    ctx.stroke();
    d.straight = true;
  }

  function endStroke() {
    if (S.tool !== "eraser") landPreview(S.tool === "highlighter");
    S.dirty = true;
  }

  //: The preview layer onto the ink, once: at the highlighter's alpha and
  //: blend for a highlighter, as it is for everything else.
  function landPreview(highlight) {
    const ctx = S.el.inkCtx;
    ctx.save();
    if (highlight) {
      ctx.globalAlpha = S.host.highlighter.alpha;
      ctx.globalCompositeOperation = S.host.highlighter.blendOnLight || "multiply";
    }
    ctx.drawImage(S.el.preview, 0, 0);
    ctx.restore();
    clearPreview();
  }

  function clearPreview() {
    S.el.previewCtx.clearRect(0, 0, W, H);
    S.el.preview.style.opacity = "1";
  }

  // --- Shapes ------------------------------------------------------------------------------

  function startShape(p) {
    S.drag = { kind: "shape", x0: p.x, y0: p.y, cancelled: false };
  }

  function moveShape(p, e) {
    const d = S.drag;
    const ctx = S.el.previewCtx;
    ctx.clearRect(0, 0, W, H);
    const size = paintShape(ctx, S.tool, d.x0, d.y0, p.x, p.y, mods(e));
    showBox(size);
  }

  function endShape(p, e, d) {
    clearPreview();
    if (Math.hypot(p.x - d.x0, p.y - d.y0) < 2) return;
    pushUndo();
    paintShape(S.el.inkCtx, S.tool, d.x0, d.y0, p.x, p.y, mods(e));
    S.dirty = true;
  }

  //: Draws one shape and returns its size for the status line.
  function paintShape(ctx, kind, x0, y0, x, y, m) {
    ctx.save();
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.lineWidth = S.size;
    ctx.strokeStyle = S.ink;
    ctx.fillStyle = S.fill;
    let label;
    if (kind === "line" || kind === "arrow") {
      const l = spLineEnds(x0, y0, x, y, m);
      ctx.beginPath();
      ctx.moveTo(l.x1, l.y1);
      ctx.lineTo(l.x2, l.y2);
      ctx.stroke();
      if (kind === "arrow") arrowHead(ctx, l);
      const deg = Math.round((Math.atan2(l.y2 - l.y1, l.x2 - l.x1) * 180) / Math.PI);
      label = `${Math.round(Math.hypot(l.x2 - l.x1, l.y2 - l.y1))} px, ${(360 - deg) % 360}°`;
    } else {
      const b = spBox(x0, y0, x, y, m);
      ctx.beginPath();
      if (kind === "ellipse") ctx.ellipse(b.x + b.w / 2, b.y + b.h / 2, Math.max(0.5, b.w / 2), Math.max(0.5, b.h / 2), 0, 0, Math.PI * 2);
      else ctx.rect(b.x, b.y, b.w, b.h);
      finishShape(ctx);
      label = `${Math.round(b.w)} × ${Math.round(b.h)}`;
    }
    ctx.restore();
    return label;
  }

  function finishShape(ctx) {
    if (S.mode !== "outline") ctx.fill();
    if (S.mode !== "fill") ctx.stroke();
  }

  function arrowHead(ctx, l) {
    const angle = Math.atan2(l.y2 - l.y1, l.x2 - l.x1);
    const len = S.size * 3 + 8;
    ctx.beginPath();
    ctx.moveTo(l.x2, l.y2);
    ctx.lineTo(l.x2 - len * Math.cos(angle - Math.PI / 6), l.y2 - len * Math.sin(angle - Math.PI / 6));
    ctx.lineTo(l.x2 - len * Math.cos(angle + Math.PI / 6), l.y2 - len * Math.sin(angle + Math.PI / 6));
    ctx.closePath();
    ctx.fillStyle = S.ink;
    ctx.fill();
  }

  // --- Polygon ----------------------------------------------------------------------------------

  function polygonDown(p, e) {
    if (!S.poly) {
      S.poly = { points: [p] };
      return;
    }
    const first = S.poly.points[0];
    const near = Math.hypot(p.x - first.x, p.y - first.y) * S.zoom < 10;
    if (near && S.poly.points.length > 2) {
      closePolygon();
      return;
    }
    S.poly.points.push(polygonPoint(p, e));
  }

  function polygonPoint(p, e) {
    const last = S.poly.points[S.poly.points.length - 1];
    return e.shiftKey ? spSnap45(last.x, last.y, p.x, p.y) : p;
  }

  function drawPolygonPreview(p, e) {
    const ctx = S.el.previewCtx;
    ctx.clearRect(0, 0, W, H);
    tracePolygon(ctx, [...S.poly.points, polygonPoint(p, e)], false);
  }

  function tracePolygon(ctx, pts, closed) {
    ctx.save();
    ctx.lineWidth = S.size;
    ctx.lineJoin = "round";
    ctx.lineCap = "round";
    ctx.strokeStyle = S.ink;
    ctx.fillStyle = S.fill;
    ctx.beginPath();
    pts.forEach((pt, i) => (i ? ctx.lineTo(pt.x, pt.y) : ctx.moveTo(pt.x, pt.y)));
    if (closed) {
      ctx.closePath();
      finishShape(ctx);
    } else ctx.stroke();
    ctx.restore();
  }

  function closePolygon() {
    const poly = S.poly;
    S.poly = null;
    clearPreview();
    if (!poly || poly.points.length < 3) return;
    pushUndo();
    tracePolygon(S.el.inkCtx, poly.points, true);
    S.dirty = true;
  }

  function cancelPolygon() {
    if (!S.poly) return false;
    S.poly = null;
    clearPreview();
    return true;
  }

  // --- Fill and picker ----------------------------------------------------------------------------

  //: What the page shows (paper, picture and ink) as one image.
  function composite() {
    const c = document.createElement("canvas");
    c.width = W;
    c.height = H;
    const ctx = c.getContext("2d", { willReadFrequently: true });
    ctx.drawImage(S.el.paperCanvas, 0, 0);
    ctx.drawImage(S.el.inkCanvas, 0, 0);
    return c;
  }

  function fillAt(p) {
    const x = Math.floor(p.x);
    const y = Math.floor(p.y);
    if (x < 0 || y < 0 || x >= W || y >= H) return;
    const seen = composite().getContext("2d").getImageData(0, 0, W, H);
    const mask = spFloodMask(seen.data, W, H, x, y);
    pushUndo();
    const ink = S.el.inkCtx.getImageData(0, 0, W, H);
    const [r, g, b] = spRgb(S.ink);
    for (let i = 0; i < mask.length; i += 1) {
      if (!mask[i]) continue;
      const q = i * 4;
      ink.data[q] = r;
      ink.data[q + 1] = g;
      ink.data[q + 2] = b;
      ink.data[q + 3] = 255;
    }
    S.el.inkCtx.putImageData(ink, 0, 0);
    S.dirty = true;
  }

  function pickColour(p) {
    const x = Math.max(0, Math.min(W - 1, Math.floor(p.x)));
    const y = Math.max(0, Math.min(H - 1, Math.floor(p.y)));
    const [r, g, b] = composite().getContext("2d").getImageData(x, y, 1, 1).data;
    setColour(spHex(r, g, b));
    S.el.custom.value = spHex(r, g, b);
    say(`Picked ${spHex(r, g, b)}.`);
    if (S.tool === "picker") setTool(S.lastTool);
  }

  // --- Text --------------------------------------------------------------------------------------------

  function textPx() {
    return Math.max(12, S.size * 4);
  }

  //: Typed in place, on the page, in the ink colour and the size it will be
  //: drawn at: what you see while typing is what lands (it was a browser
  //: `prompt()`, which looked like an error).
  function startText(p) {
    if (S.text) {
      commitText();
      return;
    }
    const input = h("textarea", { class: "sp-text-editor", rows: "1", "aria-label": "Text to place", spellcheck: "true" });
    input.style.color = S.ink;
    input.style.fontSize = `${textPx() * S.zoom}px`;
    S.text = { x: p.x, y: p.y, input };
    S.el.stage.append(input);
    placeText();
    input.addEventListener("keydown", onTextKey);
    input.addEventListener("input", growText);
    input.addEventListener("blur", () => setTimeout(commitText, 0));
    requestAnimationFrame(() => input.focus());
  }

  function placeText() {
    if (!S.text) return;
    const { input, x, y } = S.text;
    input.style.left = `${x * S.zoom}px`;
    input.style.top = `${y * S.zoom}px`;
    input.style.fontSize = `${textPx() * S.zoom}px`;
    growText();
  }

  function growText() {
    const input = S.text?.input;
    if (!input) return;
    const lines = input.value.split("\n");
    input.rows = lines.length;
    input.cols = Math.max(4, ...lines.map((l) => l.length + 1));
  }

  function onTextKey(e) {
    e.stopPropagation();
    if (e.key === "Escape") {
      e.preventDefault();
      dropText();
    } else if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      commitText();
    }
  }

  function commitText() {
    const t = S.text;
    if (!t) return;
    S.text = null;
    const value = t.input.value.replace(/\s+$/, "");
    t.input.remove();
    if (!value) return;
    pushUndo();
    const ctx = S.el.inkCtx;
    const px = textPx();
    ctx.save();
    ctx.fillStyle = S.ink;
    ctx.font = `${px}px ${getComputedStyle(S.root).fontFamily || "sans-serif"}`;
    ctx.textBaseline = "top";
    value.split("\n").forEach((line, i) => ctx.fillText(line, t.x + 2, t.y + 2 + i * px * 1.25));
    ctx.restore();
    S.dirty = true;
  }

  function dropText() {
    if (!S.text) return false;
    S.text.input.remove();
    S.text = null;
    return true;
  }

  // --- Select ---------------------------------------------------------------------------------------------

  function inSelection(p) {
    const s = S.sel;
    return s && p.x >= s.x && p.x <= s.x + s.w && p.y >= s.y && p.y <= s.y + s.h;
  }

  function selectDown(p) {
    if (inSelection(p)) {
      liftSelection();
      S.drag = { kind: "move", x0: p.x, y0: p.y, sx: S.sel.x, sy: S.sel.y, cancelled: false };
      return;
    }
    commitSelection();
    S.drag = { kind: "marquee", x0: p.x, y0: p.y, cancelled: false };
  }

  function moveMarquee(p) {
    const d = S.drag;
    const b = clampBox(spBox(d.x0, d.y0, p.x, p.y));
    S.sel = { ...b, img: null };
    drawSelection();
    showBox(`${Math.round(b.w)} × ${Math.round(b.h)}`);
  }

  function endMarquee() {
    if (!S.sel || S.sel.w < 2 || S.sel.h < 2) {
      S.sel = null;
      clearPreview();
    }
  }

  function clampBox(b) {
    const x = Math.max(0, Math.round(b.x));
    const y = Math.max(0, Math.round(b.y));
    return { x, y, w: Math.min(W, Math.round(b.x + b.w)) - x, h: Math.min(H, Math.round(b.y + b.h)) - y };
  }

  //: The selected pixels come off the ink onto a canvas of their own the
  //: first time they move, so they can float over what is under them and
  //: land with their transparency kept.
  function liftSelection() {
    const s = S.sel;
    if (s.img) return;
    pushUndo();
    const c = document.createElement("canvas");
    c.width = s.w;
    c.height = s.h;
    c.getContext("2d").drawImage(S.el.inkCanvas, s.x, s.y, s.w, s.h, 0, 0, s.w, s.h);
    S.el.inkCtx.clearRect(s.x, s.y, s.w, s.h);
    s.img = c;
  }

  function moveSelection(p) {
    const d = S.drag;
    S.sel.x = Math.round(d.sx + p.x - d.x0);
    S.sel.y = Math.round(d.sy + p.y - d.y0);
    drawSelection();
  }

  function drawSelection() {
    const s = S.sel;
    const ctx = S.el.previewCtx;
    ctx.clearRect(0, 0, W, H);
    if (!s) return;
    if (s.img) ctx.drawImage(s.img, s.x, s.y);
    ctx.save();
    ctx.lineWidth = 1 / S.zoom;
    ctx.setLineDash([6 / S.zoom, 4 / S.zoom]);
    ctx.strokeStyle = "#1f2430";
    ctx.strokeRect(s.x + 0.5, s.y + 0.5, s.w, s.h);
    ctx.lineDashOffset = 6 / S.zoom;
    ctx.strokeStyle = "#ffffff";
    ctx.strokeRect(s.x + 0.5, s.y + 0.5, s.w, s.h);
    ctx.restore();
  }

  function commitSelection() {
    const s = S.sel;
    if (!s) return;
    S.sel = null;
    if (s.img) S.el.inkCtx.drawImage(s.img, s.x, s.y);
    clearPreview();
    S.dirty = true;
  }

  function deleteSelection() {
    const s = S.sel;
    if (!s) return false;
    if (!s.img) {
      pushUndo();
      S.el.inkCtx.clearRect(s.x, s.y, s.w, s.h);
    }
    S.sel = null;
    clearPreview();
    S.dirty = true;
    return true;
  }

  function selectAll() {
    setTool("select");
    commitSelection();
    S.sel = { x: 0, y: 0, w: W, h: H, img: null };
    drawSelection();
  }

  function nudge(dx, dy) {
    liftSelection();
    S.sel.x += dx;
    S.sel.y += dy;
    drawSelection();
  }

  const DOWN = {
    select: selectDown,
    pencil: startStroke,
    brush: startStroke,
    highlighter: startStroke,
    eraser: startStroke,
    line: startShape,
    arrow: startShape,
    rect: startShape,
    ellipse: startShape,
    polygon: polygonDown,
    text: startText,
    fill: (p) => fillAt(p),
    picker: (p) => pickColour(p),
  };
  const MOVE = { stroke: moveStroke, shape: moveShape, marquee: moveMarquee, move: moveSelection };
  const UP = { stroke: endStroke, shape: endShape, marquee: endMarquee, move: () => {} };

  //: Escape in the middle of a stroke or a shape: nothing lands, and the
  //: release that follows does nothing.
  function cancelDrag() {
    const d = S.drag;
    if (!d) return false;
    d.cancelled = true;
    S.drag = null;
    if (d.kind === "stroke") restoreLast();
    if (d.kind === "marquee") S.sel = null;
    if (d.kind !== "move") clearPreview();
    else drawSelection();
    showBox("");
    return true;
  }

  // --- History ----------------------------------------------------------------------------------------------

  function pushUndo() {
    S.undo.push(S.el.inkCtx.getImageData(0, 0, W, H));
    if (S.undo.length > UNDO_DEPTH) S.undo.shift();
    S.redo = [];
  }

  //: Takes back the snapshot a cancelled stroke pushed, so a cancelled
  //: stroke leaves no Undo step behind it.
  function restoreLast() {
    const last = S.undo.pop();
    if (last) S.el.inkCtx.putImageData(last, 0, 0);
  }

  function undo() {
    commitText();
    cancelPolygon();
    commitSelection();
    if (!S.undo.length) return say("Nothing to undo.");
    S.redo.push(S.el.inkCtx.getImageData(0, 0, W, H));
    S.el.inkCtx.putImageData(S.undo.pop(), 0, 0);
    S.dirty = true;
    say("");
  }

  function redo() {
    if (!S.redo.length) return say("Nothing to redo.");
    S.undo.push(S.el.inkCtx.getImageData(0, 0, W, H));
    S.el.inkCtx.putImageData(S.redo.pop(), 0, 0);
    S.dirty = true;
    say("");
  }

  function clearInk() {
    commitText();
    cancelPolygon();
    S.sel = null;
    clearPreview();
    pushUndo();
    S.el.inkCtx.clearRect(0, 0, W, H);
    S.dirty = true;
    say("Cleared. Undo brings it back.");
  }

  // --- Keys ------------------------------------------------------------------------------------------------------

  function onKey(e) {
    if (!S.open) return;
    if (e.key === "Escape") {
      onEscape(e);
      return;
    }
    if (typingIn(e.target)) return;
    if ((e.ctrlKey || e.metaKey) && chordKey(e)) {
      e.preventDefault();
      e.stopPropagation();
      return;
    }
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    if (plainKey(e)) {
      e.preventDefault();
      e.stopPropagation();
    }
  }

  function typingIn(target) {
    return Boolean(target && (target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName)) && target.type !== "range" && target.type !== "color");
  }

  //: Escape takes back what is in hand before it closes anything: a shape
  //: being drawn, a polygon, a selection, an open menu. Only an Escape with
  //: nothing in hand reaches the page, which closes the pad.
  function onEscape(e) {
    if (e.target.closest?.("[role='menu'], .sp-help:not(.hidden)")) return;
    const spent = cancelDrag() || cancelPolygon() || dropText() || clearSelection() || closeOwnHelp();
    if (!spent) return;
    e.preventDefault();
    e.stopImmediatePropagation();
  }

  //: The pad's own '?' (no host help recipe, so the standalone page): the
  //: app's popover takes its Escape in menus.js.
  function closeOwnHelp() {
    const panel = S.root.querySelector(".sp-help:not(.help-popover):not(.hidden)");
    if (S.host.wireHelp || !panel) return false;
    panel.classList.add("hidden");
    S.root.querySelector("[data-sp=help-toggle]").setAttribute("aria-expanded", "false");
    return true;
  }

  function clearSelection() {
    if (!S.sel) return false;
    commitSelection();
    return true;
  }

  function chordKey(e) {
    const k = e.key.toLowerCase();
    if (k === "z") (e.shiftKey ? redo : undo)();
    else if (k === "y") redo();
    else if (k === "a") selectAll();
    else if (k === "0") fit();
    else return false;
    return true;
  }

  const PLAIN = {
    "[": () => setSize(S.size - (S.size > 10 ? 2 : 1)),
    "]": () => setSize(S.size + (S.size >= 10 ? 2 : 1)),
    "+": () => stepZoom(1),
    "=": () => stepZoom(1),
    "-": () => stepZoom(-1),
    "0": () => fit(),
    //: These three act only on a polygon or a selection in hand; otherwise
    //: the key is left alone, so Enter still presses a focused button (it
    //: was swallowed, and the help '?' would not open from the keyboard).
    Enter: () => Boolean(S.poly) && (closePolygon(), true),
    Delete: () => deleteSelection(),
    Backspace: () => (S.poly ? (popPolygonPoint(), true) : deleteSelection()),
  };
  const NUDGE = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] };

  function plainKey(e) {
    if (NUDGE[e.key] && S.sel) {
      const [dx, dy] = NUDGE[e.key];
      const step = e.shiftKey ? 10 : 1;
      nudge(dx * step, dy * step);
      return true;
    }
    if (PLAIN[e.key]) return PLAIN[e.key]() !== false;
    if (!S.host.singleKeys()) return false;
    const k = e.key.toUpperCase();
    if (k === "X") {
      swapColours();
      return true;
    }
    const tool = TOOLS.find((t) => t.key === k);
    if (!tool) return false;
    setTool(tool.id);
    return true;
  }

  function popPolygonPoint() {
    S.poly.points.pop();
    if (!S.poly.points.length) cancelPolygon();
  }

  // --- Status -----------------------------------------------------------------------------------------------------

  //: The readouts are written once a frame at most: a pointer reports far
  //: more often than a screen draws.
  function showPos(p) {
    S.status.pos = p && p.x >= 0 && p.y >= 0 && p.x <= W && p.y <= H ? `${Math.round(p.x)}, ${Math.round(p.y)}` : "";
    queueStatus();
  }

  function showBox(text) {
    S.status.size = text || "";
    queueStatus();
  }

  function queueStatus() {
    if (S.statusFrame) return;
    S.statusFrame = requestAnimationFrame(() => {
      S.statusFrame = 0;
      if (S.el.pos.textContent !== S.status.pos) S.el.pos.textContent = S.status.pos;
      if (S.el.box.textContent !== S.status.size) S.el.box.textContent = S.status.size;
    });
  }

  function say(text) {
    if (S.el.message) S.el.message.textContent = text;
  }

  // --- Output ------------------------------------------------------------------------------------------------------

  function flatten() {
    commitText();
    commitSelection();
    closePolygon();
    return composite();
  }

  function pngBlob() {
    return new Promise((resolve) => flatten().toBlob(resolve, "image/png"));
  }

  async function downloadPng() {
    const blob = await pngBlob();
    const stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-");
    const a = h("a", { href: URL.createObjectURL(blob), download: `sketch-${stamp}.png` });
    document.body.append(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
    say("Downloaded.");
  }

  async function saveNote() {
    const caption = (S.el.caption?.value || "").trim() || `Sketch: ${new Date().toLocaleDateString()}`;
    say("Saving…");
    S.el.save.disabled = true;
    try {
      await S.host.save(await pngBlob(), caption);
      S.dirty = false;
      if (S.el.caption) S.el.caption.value = "";
      say("");
      finishClose();
    } catch (error) {
      say(error?.message || "Couldn't save the sketch.");
    } finally {
      S.el.save.disabled = false;
    }
  }

  // --- Open and close ----------------------------------------------------------------------------------------------

  function restorePrefs() {
    const p = S.host.prefs;
    const colours = p.get("colours", null);
    if (colours?.ink) S.ink = colours.ink;
    if (colours?.fill) S.fill = colours.fill;
    S.recent = (p.get("recent", []) || []).filter((c) => /^#[0-9a-f]{6}$/i.test(c)).slice(0, 6);
    S.paper = p.get("paper", "#ffffff") || "#ffffff";
    S.size = Number(p.get("size", 4)) || 4;
  }

  //: Opens the pad in `root` (built on the first open, and again only if the
  //: host changed), on a clean page. `options.image` puts a picture under the
  //: ink, `options.caption` fills the caption.
  function open(root, host = {}, options = {}) {
    const merged = { ...SKETCH_HOST_DEFAULTS, ...host, prefs: host.prefs || SKETCH_HOST_DEFAULTS.prefs, highlighter: { ...SKETCH_HOST_DEFAULTS.highlighter, ...(host.highlighter || {}) } };
    if (S.root !== root || S.hostRef !== host) {
      S.host = merged;
      S.hostRef = host;
      S.root = root;
      restorePrefs();
      build(root);
      viewportWatch?.observe(S.el.viewport);
    }
    reset();
    S.open = true;
    if (options.caption && S.el.caption) S.el.caption.value = options.caption;
    if (options.image) setImage(options.image);
    requestAnimationFrame(() => {
      fit();
      root.querySelector('.sp-tool[data-tool="pencil"]')?.focus();
    });
  }

  function reset() {
    S.undo = [];
    S.redo = [];
    S.drag = null;
    S.poly = null;
    S.sel = null;
    dropText();
    S.image = null;
    S.dirty = false;
    S.el.inkCtx.clearRect(0, 0, W, H);
    clearPreview();
    drawPaper();
    S.el.paper.value = S.paper;
    setTool("pencil");
    setWell("ink");
    setMode(S.mode);
    setSize(S.size);
    paintWells();
    paintRecent();
    say("");
    S.root.querySelector("#sketch-help")?.classList.add("hidden");
  }

  //: Asks before throwing away a drawing. Resolves true when the pad closed.
  async function requestClose() {
    if (!S.open) return true;
    commitText();
    if (S.dirty && !(await S.host.confirm("Close without saving your sketch?"))) return false;
    finishClose();
    return true;
  }

  function finishClose() {
    S.open = false;
    S.host.prefs.set("size", S.size);
    S.host.close?.();
  }

  document.addEventListener("keydown", onKey, true);
  //: The viewport, not the window: the bar can rewrap after the pad opens
  //: (the icon font arriving, a phone turning), which moves the page without
  //: a window resize, and the fit and the pointer's box then went stale
  //: (measured at 390: a refit read 35% against 34% at open, and the
  //: pointer was 5px off).
  const viewportWatch = typeof ResizeObserver === "function" ? new ResizeObserver(() => {
    S.rect = null;
    if (S.open && S.fitted) fit();
  }) : null;
  window.addEventListener("resize", () => {
    S.rect = null;
    if (!viewportWatch && S.open && S.fitted) fit();
  });

  window.SketchPad = {
    open,
    requestClose,
    setImage,
    isOpen: () => S.open,
    isDirty: () => S.dirty,
    //: For tests and sweeps: the pure helpers and the live state.
    _geometry: { spBox, spSnap45, spLineEnds, spFloodMask },
    _state: S,
  };
})();
