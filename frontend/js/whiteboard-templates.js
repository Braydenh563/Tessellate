// whiteboard-templates.js: the New board dialog, every template's picture,
// and a new map's offer of a starting shape (INBOX 715).
//
// The owner, with the dialog and three templates on screen: "the pill at the
// top is ugly and I want it to be redesigned to be like the other popups",
// "there are no mindmap templates to choose from", "some of the templates are
// poorly designed and the templates need massive improving and expanding";
// then, of the library's map tiles, "these all look the same".
//
// One source for each kind: `frontend/board-library/templates.json` (boards)
// and `maps.json` (maps), each entry carrying its `purpose` (the picker's
// group), a one-line `hint`, and for a map its `shape` (how its picture is
// drawn) and `layout` (the map layout it starts in). The New board dialog,
// the Library's tiles and the empty map's offer all draw from those files
// through the two picture functions here, so the three agree.
//
// **Loaded in the Library bundle after whiteboard-library.js** (`LAZY_MODULES`,
// app.js); the two picture functions are pure (no DOM), so
// `tests/test_board_templates_715.py` runs them under node.

//: The picker's groups, in order, for both kinds.
const WB_TEMPLATE_PURPOSES = [
  ["plan", "Plan and track"],
  ["decide", "Weigh and decide"],
  ["solve", "Find the cause"],
  ["meet", "Meet and review"],
  ["learn", "Study and create"],
];

// --- pictures ----------------------------------------------------------------
//
// A picture is `{viewBox, parts}`, each part `{tag, cls, a, text}`, and
// `wbThumbSvg` turns it into an `<svg>` with DOM calls (nothing is parsed).
// Colours come from classes (library-lazy.css), never from attributes, so a
// picture follows the theme.

function wbThumbRound(v) {
  return Math.round(v * 10) / 10;
}

//: **A map template's picture, drawn from its own tree** (the owner: "these
//: all look the same"; every tile was one root and three branches). The
//: branch count, each branch's children and the template's `shape` decide
//: it: a brainstorm radiates, pros and cons go both ways, cause and effect is
//: a fishbone, a decision forks, a project runs in phases left to right, book
//: notes and a meeting are tiers. A saved branch with no shape is a tree.
function wbMapThumbSpec(entry) {
  const R = wbThumbRound;
  const nodes = entry?.payload?.nodes || entry?.payload?.branch?.nodes || [];
  const top = nodes.length === 1 && nodes[0].children?.length ? nodes[0].children : nodes;
  const branches = top.slice(0, 8);
  const kids = branches.map((b) => Math.min(4, (b.children || []).length));
  const n = Math.max(1, branches.length);
  const shape = ["radial", "two-sided", "fishbone", "fork", "phases", "tiers"].includes(entry?.shape) ? entry.shape : "tree";
  const lines = [];
  const boxes = [];
  //: **Each branch wears its own colour** (a map's branches are coloured by
  //: the creation order, `MAP_BRANCH_PALETTE`; the tiles were all one grey).
  //: `hue` is the branch being drawn, set at the top of each branch's turn;
  //: the root, a spine and a label stay neutral. The colours are classes
  //: (library-lazy.css), so a picture still follows the theme.
  let hue = -1;
  const tone = (cls) => (hue < 0 ? cls : `${cls} wb-thumb-b${hue % 10}`);
  const line = (d) => lines.push({ tag: "path", cls: tone("wb-thumb-line"), a: { d } });
  const box = (cx, cy, w, h, cls = "wb-thumb-node") => boxes.push({
    tag: "rect", cls: cls === "wb-thumb-root" ? cls : tone(cls), a: { x: R(cx - w / 2), y: R(cy - h / 2), width: R(w), height: R(h), rx: R(Math.min(2, h / 2)) },
  });
  const leaf = (cx, cy) => boxes.push({ tag: "circle", cls: tone("wb-thumb-leaf"), a: { cx: R(cx), cy: R(cy), r: 1.5 } });
  //: A stroke inside a box where its words would be, so a tier reads as labelled.
  const label = (cx, cy, w) => boxes.push({ tag: "path", cls: "wb-thumb-label", a: { d: `M ${R(cx - w / 2)} ${R(cy)} L ${R(cx + w / 2)} ${R(cy)}` } });
  if (!branches.length) {
    box(32, 20, 18, 9, "wb-thumb-root");
    label(32, 20, 10);
    return { viewBox: "0 0 64 40", parts: boxes };
  }
  if (shape === "radial") {
    branches.forEach((_, i) => {
      hue = i;
      const t = -Math.PI / 2 + (i * 2 * Math.PI) / n;
      const bx = 32 + 20 * Math.cos(t), by = 20 + 12.5 * Math.sin(t);
      line(`M 32 20 L ${R(bx)} ${R(by)}`);
      for (let k = 0; k < kids[i]; k += 1) {
        const u = t + (k - (kids[i] - 1) / 2) * 0.32;
        const kx = 32 + 29 * Math.cos(u), ky = 20 + 18 * Math.sin(u);
        line(`M ${R(bx)} ${R(by)} L ${R(kx)} ${R(ky)}`);
        leaf(kx, ky);
      }
      box(bx, by, 9, 5);
    });
    box(32, 20, 14, 8, "wb-thumb-root");
  } else if (shape === "two-sided") {
    const right = branches.slice(0, Math.ceil(n / 2));
    const left = branches.slice(Math.ceil(n / 2));
    const side = (list, dir, offset) => {
      const m = list.length;
      const gap = Math.min(13, 32 / Math.max(1, m));
      list.forEach((_, j) => {
        const i = offset + j;
        hue = i;
        const by = 20 + (j - (m - 1) / 2) * gap, bx = 32 + dir * 17;
        line(`M ${32 + dir * 7} 20 C ${32 + dir * 12} 20 ${32 + dir * 11} ${R(by)} ${R(bx - dir * 4.5)} ${R(by)}`);
        for (let k = 0; k < kids[i]; k += 1) {
          const ky = by + (k - (kids[i] - 1) / 2) * 4, kx = 32 + dir * 27;
          line(`M ${R(bx + dir * 4.5)} ${R(by)} L ${R(kx - dir * 1.5)} ${R(ky)}`);
          leaf(kx, ky);
        }
        box(bx, by, 9, 5);
      });
    };
    side(right, 1, 0);
    side(left, -1, right.length);
    box(32, 20, 14, 8, "wb-thumb-root");
  } else if (shape === "fishbone") {
    //: The effect is the head on the right; each kind of cause is a rib, top
    //: and bottom in turn, its causes ticks along it.
    line("M 3 20 L 49 20");
    const pairs = Math.ceil(n / 2);
    branches.forEach((_, i) => {
      hue = i;
      const x = 44 - Math.floor(i / 2) * (36 / pairs);
      const up = i % 2 === 0 ? -1 : 1;
      line(`M ${R(x)} 20 L ${R(x - 8)} ${20 + up * 12}`);
      for (let k = 0; k < kids[i]; k += 1) {
        const f = (k + 1) / (kids[i] + 1);
        const px = x - 8 * f, py = 20 + up * 12 * f;
        line(`M ${R(px)} ${R(py)} L ${R(px - 4)} ${R(py)}`);
      }
      box(x - 8, 20 + up * 14.5, 9, 4.5);
    });
    box(56, 20, 13, 10, "wb-thumb-root");
  } else if (shape === "fork") {
    //: One split point, every option curving away from it.
    line("M 16 20 L 20 20");
    const gap = Math.min(10, 34 / n);
    branches.forEach((_, i) => {
      hue = i;
      const by = 20 + (i - (n - 1) / 2) * gap;
      line(`M 20 20 C 25 20 24 ${R(by)} 27.5 ${R(by)}`);
      for (let k = 0; k < kids[i]; k += 1) {
        const kx = 41 + k * 6;
        line(`M ${R(kx - (k ? 4.5 : 9))} ${R(by)} L ${R(kx - 1.5)} ${R(by)}`);
        leaf(kx, by);
      }
      box(32, by, 9, Math.min(5, gap - 1));
    });
    box(9, 20, 14, 8, "wb-thumb-root");
  } else if (shape === "phases") {
    //: The phases are chevrons in a row, left to right, under the goal.
    const w = (60 - (n - 1) * 1.5) / n;
    const centres = branches.map((_, i) => 2 + i * (w + 1.5) + w / 2);
    line(`M 32 9.5 L 32 13 M ${R(centres[0])} 13 L ${R(centres[n - 1])} 13`);
    branches.forEach((_, i) => {
      hue = i;
      const x = 2 + i * (w + 1.5), cx = centres[i];
      line(`M ${R(cx)} 13 L ${R(cx)} 17`);
      const notch = i ? 2.5 : 0;
      boxes.push({ tag: "path", cls: tone("wb-thumb-node"), a: { d: `M ${R(x)} 17 L ${R(x + w - 2.5)} 17 L ${R(x + w)} 21.5 L ${R(x + w - 2.5)} 26 L ${R(x)} 26 L ${R(x + notch)} 21.5 Z` } });
      for (let k = 0; k < kids[i]; k += 1) box(cx, 30 + k * 4, w * 0.6, 2.4, "wb-thumb-leafbox");
    });
    box(32, 6, 16, 7, "wb-thumb-root");
  } else if (shape === "tiers") {
    const w = Math.min(12, (60 - (n - 1) * 2) / n);
    const centres = branches.map((_, i) => 32 + (i - (n - 1) / 2) * (w + 2));
    line(`M 32 9.5 L 32 12 M ${R(centres[0])} 12 L ${R(centres[n - 1])} 12`);
    branches.forEach((_, i) => {
      hue = i;
      const cx = centres[i];
      line(`M ${R(cx)} 12 L ${R(cx)} 15.5`);
      if (kids[i]) line(`M ${R(cx)} 20.5 L ${R(cx)} ${R(26 + (kids[i] - 1) * 5)}`);
      box(cx, 18, w, 5);
      label(cx, 18, w - 4);
      for (let k = 0; k < kids[i]; k += 1) box(cx, 26 + k * 5, w * 0.8, 3.4, "wb-thumb-leafbox");
    });
    box(32, 6, 18, 7, "wb-thumb-root");
    label(32, 6, 10);
  } else {
    //: A tree: a spine from the root, every branch an elbow off it.
    const gap = Math.min(9, 34 / n);
    const ys = branches.map((_, i) => 20 + (i - (n - 1) / 2) * gap);
    line(`M 16 20 L 20 20 M 20 ${R(ys[0])} L 20 ${R(ys[n - 1])}`);
    branches.forEach((_, i) => {
      hue = i;
      const by = ys[i];
      line(`M 20 ${R(by)} L 24.5 ${R(by)}`);
      for (let k = 0; k < kids[i]; k += 1) {
        const ky = by + (k - (kids[i] - 1) / 2) * 3;
        line(`M 33.5 ${R(by)} L 37 ${R(by)} L 37 ${R(ky)} L 40 ${R(ky)}`);
        box(44, ky, 8, 2.2, "wb-thumb-leafbox");
      }
      box(29, by, 9, Math.min(5, gap - 1));
    });
    box(9, 20, 14, 8, "wb-thumb-root");
  }
  return { viewBox: "0 0 64 40", parts: [...lines, ...boxes] };
}

//: **A board template's picture, drawn from its own items.** A frame with a
//: `tint` is a panel, as the board draws it: a tinted ground, its title
//: inside its top with padding and a hint line under it. Every title in one
//: picture is one size (the owner's screenshots had three: the size was
//: worked out per frame from the length of its name), the largest that
//: still fits the narrowest frame's name.
//: **`placed`: the tile draws what placing it makes** (INBOX 794, the owner:
//: the previews "arent visually accurate to what is actually placed and are a
//: bit misleading"). A placed shape takes the pen's ink wherever the library's
//: payload says `ink` (colour and fill) and keeps its own weight, dash and
//: fill opacity (`routes_board_library.py` `_place_element`), but the tile drew
//: every ink as the page's text colour, lifted a faint fill to 18% and gave
//: every line one hairline, so a cyan pen still showed grey shapes. With
//: `placed` set the tile resolves the ink to `opts.ink`, and the fill opacity,
//: width and dash are the payload's own (the width in the tile's board units,
//: the dash the board's own ratios). The New board dialog's pictures are
//: drawings of whole templates at a glance, so they keep the old legibility.
function wbBoardThumbSpec(element, opts = {}) {
  const R = wbThumbRound;
  const placed = opts.placed === true;
  const pen = /^#[0-9a-f]{6}$/i.test(opts.ink || "") ? opts.ink : "currentColor";
  const box = element?.box || { w: 100, h: 100 };
  const span = Math.max(box.w, box.h);
  const pad = span * 0.04;
  const strokeW = span / (span > 400 ? 120 : 40);
  const items = (element?.items || []).slice(0, 80);
  const frames = items.filter((i) => i.kind === "object" && i.type === "frame");
  const words = (d) => (d?.content || "").replace(/[#*_[\]()>`]/g, "").trim();
  //: The panel's padding in board units, as the board's own CSS draws it.
  const inset = 20;
  let title = span / 22;
  for (const f of frames) {
    const len = Math.max(4, words(f.data).length);
    //: 0.7em a letter: a bold title in capitals and wide letters ("Why 1",
    //: "Wednesday") measured past 0.6 in the browser.
    title = Math.min(title, ((f.w || 100) - inset * 2) / (0.7 * len));
  }
  title = R(Math.max(6, title));
  const notes = items.filter((i) => i.kind === "object" && i.type !== "frame" && i.type !== "image" && words(i.data));
  let note = span / 30;
  for (const s of notes) note = Math.min(note, ((s.w || 100) - inset) / (0.6 * Math.max(4, Math.min(16, words(s.data).length))));
  note = R(Math.max(5, note));
  const parts = [];
  for (const item of items) {
    if (item.kind === "sketch") {
      const data = typeof item.data === "string" ? (() => { try { return JSON.parse(item.data); } catch { return {}; } })() : item.data || {};
      if (!data.d) continue;
      const a = { d: data.d, "stroke-linejoin": "round" };
      const inkOf = (v) => (v === "ink" ? (placed ? pen : "currentColor") : v);
      const ink = !data.color ? "currentColor" : inkOf(data.color);
      const fill = inkOf(data.fill);
      a.fill = fill || "none";
      if (fill && data.fillOpacity != null) {
        a["fill-opacity"] = String(placed || !(data.fill === "ink" && data.fillOpacity < 1) ? data.fillOpacity : Math.max(0.18, data.fillOpacity));
      }
      if (data.noStroke) a.stroke = "none";
      else {
        const width = placed && data.width > 0 ? data.width : strokeW;
        a.stroke = ink;
        a["stroke-width"] = R(width);
        //: The board's own ratios (`wbDashArray`, whiteboard.js).
        if (placed && data.dash === "dashed") a["stroke-dasharray"] = `${R(width * 3)} ${R(width * 2)}`;
        else if (placed && data.dash === "dotted") a["stroke-dasharray"] = `${R(width)} ${R(width * 1.6)}`;
      }
      parts.push({ tag: "path", cls: "", a });
      continue;
    }
    if (item.kind !== "object") continue;
    const x = item.x || 0, y = item.y || 0, w = item.w || 100, h = item.h || 60;
    const d = item.data || {};
    if (item.type === "frame") {
      const tint = d.tint || "";
      parts.push({ tag: "rect", cls: tint ? "wb-thumb-frame" : "wb-thumb-frame-plain", tint, a: { x, y, width: w, height: h, rx: R(Math.min(16, span / 60)) } });
      const name = words(d).slice(0, 40);
      if (!name) continue;
      if (tint) {
        parts.push({ tag: "text", cls: "wb-thumb-title", a: { x: x + inset, y: R(y + inset + title * 0.8), "font-size": title }, text: name });
        if (d.hint) parts.push({ tag: "rect", cls: "wb-thumb-hint", a: { x: x + inset, y: R(y + inset + title * 1.3), width: R(Math.min(w - inset * 2, title * 7)), height: R(title * 0.4), rx: R(title * 0.2) } });
      } else {
        parts.push({ tag: "text", cls: "wb-thumb-title", a: { x, y: R(y - title * 0.35), "font-size": title }, text: name });
      }
      continue;
    }
    const a = { x, y, width: w, height: h, rx: R(strokeW * 2) };
    if (d.bg) {
      a.fill = d.bg;
      a.stroke = d.border_color || "none";
    } else {
      a.fill = "none";
      a.stroke = "currentColor";
      a["stroke-opacity"] = "0.4";
    }
    a["stroke-width"] = R(strokeW / 2);
    parts.push({ tag: "rect", cls: "", a });
    const text = words(d).slice(0, 16);
    if (text) {
      parts.push({ tag: "text", cls: "wb-thumb-note", a: { x: R(x + w / 2), y: R(y + h / 2), "text-anchor": "middle", "dominant-baseline": "central", "font-size": note, fill: d.color || "currentColor" }, text });
    }
  }
  //: Room over the drawing only for a plain frame, whose title sits above it.
  const above = frames.some((f) => !f.data?.tint && words(f.data)) ? title : 0;
  return { viewBox: `${R(-pad)} ${R(-pad - above)} ${R(box.w + pad * 2)} ${R(box.h + pad * 2 + above)}`, parts };
}

//: Blank: an empty board, or one central topic.
function wbBlankThumbSpec(kind) {
  if (kind === "map") return wbMapThumbSpec({ payload: { nodes: [] } });
  return { viewBox: "0 0 64 40", parts: [{ tag: "rect", cls: "wb-thumb-blank", a: { x: 4, y: 4, width: 56, height: 32, rx: 3 } }] };
}

function wbThumbSvg(spec) {
  const NS = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("class", "wb-lib-thumb");
  svg.setAttribute("aria-hidden", "true");
  svg.setAttribute("focusable", "false");
  svg.setAttribute("viewBox", spec.viewBox);
  svg.setAttribute("preserveAspectRatio", "xMidYMid meet");
  for (const part of spec.parts) {
    const el = document.createElementNS(NS, part.tag);
    if (part.cls) el.setAttribute("class", part.cls);
    if (part.tint) el.dataset.tint = part.tint;
    for (const [k, v] of Object.entries(part.a)) el.setAttribute(k, String(v));
    if (part.text) el.textContent = part.text;
    svg.appendChild(el);
  }
  return svg;
}

// --- New board from a template (BACKLOG 4b, decision 25; INBOX 715) -------------
//
// DESIGN.md's recipe for "a dialog of choices that each make something":
// quiet radio rows beside a preview of what the chosen row makes; choosing is
// not making (only Create, Enter or a double click makes). The kind is a
// `.tabs-line` under the head (DESIGN.md: a popup chooses a kind with a tab
// strip, never a pill); the rows are grouped by purpose, each with its
// picture, and the preview draws the same picture large over its name and
// hint.

function wbTemplateEntry(set, item) {
  return { ...item, kind: item.kind || "element", ref: `builtin:${set}/${item.key}` };
}

function wbTemplateChoices(kind) {
  const out = [{ ref: null, name: "Blank", hint: kind === "map" ? "One central topic named after the map" : "An empty board", group: null }];
  const set = kind === "map" ? "maps" : "templates";
  for (const item of wbLibSets.get(set)?.items || []) {
    if (item.template !== kind) continue;
    out.push({ ref: `builtin:${set}/${item.key}`, name: item.name, hint: item.hint || "", group: item.purpose || "learn", entry: wbTemplateEntry(set, item) });
  }
  for (const item of wbLibState.lib?.items || []) {
    if (item.kind !== "template") continue;
    const type = item.payload?.board?.type === "map" ? "map" : "board";
    if (type !== kind) continue;
    out.push({ ref: `item:${item.id}`, name: item.name, hint: "Saved from one of your boards", group: "yours", entry: { ...item, ref: `item:${item.id}`, payload: item.payload } });
  }
  return out;
}

function wbTemplatePicture(choice, kind) {
  if (!choice.entry) return wbThumbSvg(wbBlankThumbSpec(kind));
  const entry = choice.entry;
  const branch = entry.kind === "branch" || entry.payload?.branch;
  return branch ? wbThumbSvg(wbMapThumbSpec(entry)) : wbLibThumb(entry);
}

//: **A new board needs no name** (INBOX 739, the owner: "auto naming of the
//: whiteboards, mindmaps ... like "untitled #" so the user isnt forced to
//: name a new object"). The next free number after every "Untitled board N"
//: (or map) there is, counted from the boards themselves, so a deleted one's
//: number is not reused while a higher one exists. Shown as the name field's
//: placeholder, so what Create makes is what the field already says.
async function wbUntitledNames() {
  const rows = await apiJson("/whiteboard/boards", { silent: true }).catch(() => []);
  const next = (base) => {
    const pattern = new RegExp(`^${base} (\\d{1,6})$`, "i");
    let top = 0;
    for (const row of Array.isArray(rows) ? rows : []) {
      const match = pattern.exec(String(row?.title || "").trim());
      if (match) top = Math.max(top, Number(match[1]));
    }
    return `${base} ${top + 1}`;
  };
  return { board: next("Untitled board"), map: next("Untitled map") };
}

//: Resolves `{name, kind, ref}` (ref null for blank) or null when cancelled.
async function wbOpenTemplateGallery(kind = "board") {
  const dialog = document.getElementById("wb-template-dialog");
  const list = document.getElementById("wb-template-list");
  const preview = document.getElementById("wb-template-preview");
  const nameField = document.getElementById("wb-template-name");
  const tabs = document.getElementById("wb-template-kind");
  if (!dialog || !list || !preview || !nameField || !tabs) return null;
  const [, untitled] = await Promise.all([wbLoadLibrary(), wbUntitledNames()]);
  let chosen = null;
  let choices = [];
  const choose = (choice, { focus = false } = {}) => {
    chosen = choice;
    for (const row of list.querySelectorAll(".doc-template-choice")) {
      const on = row.dataset.ref === String(choice.ref);
      row.setAttribute("aria-checked", on ? "true" : "false");
      row.tabIndex = on ? 0 : -1;
      if (on && focus) row.focus();
    }
    const caption = document.createElement("div");
    caption.className = "wb-template-preview-text";
    const title = document.createElement("strong");
    title.textContent = choice.name;
    const hint = document.createElement("p");
    hint.className = "muted";
    hint.textContent = choice.hint;
    caption.append(title, hint);
    const art = document.createElement("div");
    art.className = "wb-template-preview-art";
    art.append(wbTemplatePicture(choice, kind));
    const inner = document.createElement("div");
    inner.className = "wb-template-preview-inner";
    inner.append(caption, art);
    preview.replaceChildren(inner);
    //: A blank one is named for you too (INBOX 904 B17): the default name is
    //: the value, selected when the dialog opens, so typing replaces it.
    if (!nameField.dataset.typed) nameField.value = choice.ref ? choice.name : untitled[kind === "map" ? "map" : "board"];
  };
  const row = (choice) => {
    const li = document.createElement("li");
    li.setAttribute("role", "presentation");
    const button = document.createElement("button");
    button.type = "button";
    button.className = "ghost doc-template-choice wb-template-choice";
    button.setAttribute("role", "radio");
    button.setAttribute("aria-checked", "false");
    button.dataset.ref = String(choice.ref);
    const art = wbTemplatePicture(choice, kind);
    art.classList.add("wb-template-choice-art");
    const words = document.createElement("span");
    words.className = "wb-template-choice-words";
    const name = document.createElement("strong");
    name.textContent = choice.name;
    const hint = document.createElement("span");
    hint.className = "muted text-sm";
    hint.textContent = choice.hint;
    words.append(name, hint);
    const check = document.createElement("i");
    check.className = "ph ph-check doc-template-check";
    check.setAttribute("aria-hidden", "true");
    button.append(art, words, check);
    button.addEventListener("click", () => choose(choice));
    button.addEventListener("dblclick", () => finish(true));
    li.append(button);
    return li;
  };
  const heading = (words) => {
    const li = document.createElement("li");
    li.setAttribute("role", "presentation");
    li.className = "wb-template-group";
    li.textContent = words;
    return li;
  };
  const fill = () => {
    list.replaceChildren();
    for (const tab of tabs.querySelectorAll("[role='tab']")) {
      const on = tab.dataset.value === kind;
      tab.setAttribute("aria-selected", on ? "true" : "false");
      tab.tabIndex = on ? 0 : -1;
    }
    nameField.placeholder = untitled[kind === "map" ? "map" : "board"];
    choices = wbTemplateChoices(kind);
    list.append(row(choices[0]));
    for (const [key, words] of [...WB_TEMPLATE_PURPOSES, ["yours", "Yours"]]) {
      const group = choices.filter((c) => c.group === key);
      if (!group.length) continue;
      list.append(heading(words));
      for (const choice of group) list.append(row(choice));
    }
    list.scrollTop = 0;
    choose(choices[0]);
  };
  let settle;
  const done = new Promise((resolve) => {
    settle = resolve;
  });
  const finish = (make) => {
    const name = nameField.value.trim() || untitled[kind === "map" ? "map" : "board"];
    dialog.close();
    settle(make ? { name, kind, ref: chosen?.ref || null } : null);
  };
  nameField.value = "";
  delete nameField.dataset.typed;
  nameField.oninput = () => {
    nameField.dataset.typed = "1";
  };
  nameField.onkeydown = (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      finish(true);
    }
  };
  list.onkeydown = (e) => {
    const rows = [...list.querySelectorAll(".doc-template-choice")];
    const at = rows.indexOf(document.activeElement);
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      const next = rows[(at + (e.key === "ArrowDown" ? 1 : -1) + rows.length) % rows.length];
      next?.click();
      next?.focus();
    } else if (e.key === "Enter") {
      e.preventDefault();
      finish(true);
    }
  };
  //: A tab strip's keys: the arrows move the choice and the focus together.
  const pick = (value, { focus = false } = {}) => {
    kind = value;
    fill();
    if (focus) tabs.querySelector(`[data-value="${value}"]`)?.focus();
  };
  for (const tab of tabs.querySelectorAll("[role='tab']")) tab.onclick = () => pick(tab.dataset.value);
  tabs.onkeydown = (e) => {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(e.key)) return;
    e.preventDefault();
    const values = [...tabs.querySelectorAll("[role='tab']")].map((t) => t.dataset.value);
    const at = values.indexOf(kind);
    const next = e.key === "Home" ? 0 : e.key === "End" ? values.length - 1 : (at + (e.key === "ArrowRight" ? 1 : -1) + values.length) % values.length;
    pick(values[next], { focus: true });
  };
  document.getElementById("wb-template-create").onclick = () => finish(true);
  for (const btn of dialog.querySelectorAll("[data-close-dialog='wb-template-dialog']")) btn.onclick = () => finish(false);
  dialog.oncancel = (e) => {
    e.preventDefault();
    finish(false);
  };
  fill();
  dialog.showModal();
  nameField.focus();
  nameField.select();
  return done;
}

// --- A new map's offer of a starting shape (MINDMAP_PLAN §5 item 21) -----------
//
// "An empty canvas is the main reason mindmap features go unused." Offered on
// a map that is still just its root, and never again once it is used or
// dismissed (`wbSyncMapTemplates`, whiteboard-map.js). It was four outlined
// word buttons from a list of its own; it is now the Library's map templates,
// each a tile with its picture, in one row that scrolls (INBOX 715).

function wbRenderMapTemplates() {
  const row = document.getElementById("wb-map-template-row");
  if (!row || row.childElementCount) return;
  const set = wbLibSets.get("maps");
  if (!set) {
    if (!wbLibState.mapOfferLoading) {
      wbLibState.mapOfferLoading = true;
      wbLoadLibrary().finally(() => {
        wbLibState.mapOfferLoading = false;
        if (wbLibSets.get("maps")) wbRenderMapTemplates();
      });
    }
    return;
  }
  for (const item of set.items || []) {
    const entry = wbTemplateEntry("maps", item);
    const tile = document.createElement("button");
    tile.type = "button";
    tile.className = "ghost wb-map-template-tile";
    tile.dataset.wbTemplate = item.key;
    tile.title = item.hint ? `${item.name}: ${item.hint}` : item.name;
    tile.setAttribute("aria-label", item.name);
    const name = document.createElement("span");
    name.className = "wb-map-template-name";
    name.textContent = item.name;
    tile.append(wbThumbSvg(wbMapThumbSpec(entry)), name);
    tile.addEventListener("click", () => wbApplyMapTemplate(entry));
    row.append(tile);
  }
}

//: Under the map's root, through the Library's own placing (one request, one
//: undo step), then in the layout the template is drawn for.
async function wbApplyMapTemplate(entry) {
  if (!entry || !wbIsMap()) return;
  await wbRecordGesture(async () => {
    await wbLibPlace(entry);
    if (entry.layout && entry.layout !== wbMapLayout()) await wbMapSetLayout(entry.layout);
  });
  wbDismissMapTemplates();
}
