// documents-board.js: a board embed edited from the document (DOCUMENTS_PLAN 26, gap row 10). `![[board:12]]` draws the board's
// card; its "Edit here" opens the board in a dialog over the document, with the whiteboard's own toolbar; the dialog's X closes it.
// The whiteboard is one page-wide instance (one `wbState`, one `#whiteboard-container`, ids everywhere), so this does not make a
// second one: it lends the Library's `#library-view-whiteboard` to the panel and puts it back on close. Whiteboard side, small
// hooks: `openWhiteboardBoard(id, { stay: true })` does not switch to the Library (`restore: true` puts the board's remembered camera
// back), `wbShowBoardsLanding` first offers a cancelable `wb-leave` event, which this file answers by closing the panel (the board's
// own "Boards" button is hidden, the dialog's X takes its place), and `wbShowBoardsLanding.wantsEscape()` says whether the board
// still has a use for an Escape. Closing leaves the Library as it was: its board open again, or its list.
// **Show live (decision 83, L-documents-11)** is the other half: a window per card, read-only, drawn here from the board's own data
// and zoomed by the diagram view's recipe, which never touches the whiteboard, so any number of them and the Library's board
// cannot cross. The windows are at the foot of this file.
// Lazy: `LAZY_MODULES.docBoard`; documents-embeds.js draws the buttons and asks for this file on the first press. It adds no global name.
(() => {
  let open = null;

  //: Put the whiteboard view back where the Library keeps it, and the Library as it was: the board it had open is loaded again
  //: (with the camera it had), or the board list is shown when it was on the list.
  async function close() {
    const was = open;
    if (!was) return;
    open = null;
    await window.wbCancelBoardTimers?.();
    window.wbLeaveFullscreen?.();
    if (was.libraryBoard != null) {
      //: Loaded while the view is still in the dialog, unseen (a hidden Library has no size to frame by): the camera is restored, not framed.
      was.overlay.classList.add("doc-board-closing");
      await window.openWhiteboardBoard(was.libraryBoard, { stay: true, restore: true });
    } else {
      window.wbShowBoardsLanding?.();
    }
    was.view.classList.toggle("hidden", was.hidden);
    was.home.insertBefore(was.view, was.next);
    was.overlay.remove();
    window.dispatchEvent(new Event("resize"));
    //: The card's picture is from the board index, which the edit has outdated.
    await window.loadMapBoardIndex?.(true);
    document.dispatchEvent(new CustomEvent("board-edited", { detail: { id: was.id } }));
    //: The redraw above may have replaced the button that opened the panel: the same board's button at the same place gets the focus.
    setTimeout(() => {
      const same = [...document.querySelectorAll(`.doc-embed-board-edit[data-board-id="${was.id}"]`)];
      (was.opener?.isConnected ? was.opener : same[was.nth] || same[0])?.focus();
    }, 0);
  }

  async function show(id, title, opener) {
    if (open) return;
    const view = document.getElementById("library-view-whiteboard");
    if (!view) return;
    //: The overlay recipe (`dialogHead`, then `panelMovable` by its head), as the diagram builder's dialog is built.
    const overlay = document.createElement("div");
    overlay.className = "modal-overlay confirm-overlay doc-board-overlay";
    overlay.setAttribute("role", "dialog");
    overlay.setAttribute("aria-modal", "true");
    overlay.setAttribute("aria-label", `Board: ${title || "Untitled"}`);
    const card = document.createElement("div");
    card.className = "card modal-card space-dialog doc-board-card";
    card.append(dialogHead(title || "Untitled board", close));
    overlay.append(card);
    document.body.append(overlay);
    //: What the Library has open now, so closing leaves it so: the board on its canvas, or none (the list).
    const canvas = document.getElementById("wb-canvas-view");
    const libraryBoard = canvas && !canvas.classList.contains("hidden") && window.currentBoardId != null ? window.currentBoardId : null;
    const nth = [...document.querySelectorAll(`.doc-embed-board-edit[data-board-id="${id}"]`)].indexOf(opener);
    open = { id, view, overlay, opener, nth, libraryBoard, home: view.parentElement, next: view.nextSibling, hidden: view.classList.contains("hidden") };
    card.append(view);
    view.classList.remove("hidden");
    await window.openWhiteboardBoard(id, { stay: true });
    card.querySelector('.dialog-head-actions button[aria-label="Close"]')?.focus();
  }

  //: **Escape is the board's first, the panel's next.** A menu, a selection, a tool, a find bar, a text being typed or full screen
  //: each take an Escape; the one that finds none of them closes the panel. The board's state is read before its own handlers run
  //: (capture), because a handler that clears a selection does not say it did.
  let boardTookEscape = false;
  function boardWantsEscape(event) {
    const { view } = open;
    if (view.classList.contains("wb-fullscreen") || view.classList.contains("wb-presenting")) return true;
    if (document.querySelector(".action-menu:not(.hidden), .help-popover:not(.hidden), .wb-ctx-menu:not(.hidden), .wb-map-radial:not(.hidden)")) return true;
    if (event.target?.closest?.('input, textarea, select, [contenteditable]:not([contenteditable="false"])')) return true;
    return Boolean(window.wbShowBoardsLanding?.wantsEscape?.());
  }
  document.addEventListener("keydown", (event) => {
    if (open && event.key === "Escape") boardTookEscape = boardWantsEscape(event);
  }, true);
  //: On `window`, after every `document` handler: one that took the key has stopped it or prevented it.
  window.addEventListener("keydown", (event) => {
    if (!open || event.key !== "Escape" || boardTookEscape || event.defaultPrevented) return;
    if (activeOverlay() !== open.overlay) return;
    event.preventDefault();
    close();
  });

  document.addEventListener("board-edit", (event) => show(event.detail.id, event.detail.title, event.target));
  //: The board's own "Boards" button, the phone shell's back and a space switch all end up here; with the panel open they close it.
  document.addEventListener("wb-leave", (event) => {
    if (!open) return;
    event.preventDefault();
    close();
  });

  //: **A window per board card (decision 83).** Each is `{ id, button, host, fig, nth }`, its own picture and zoom; none reads or
  //: writes the one whiteboard's state, has a selection, an undo or a save, so two windows and the Library's board cannot cross.
  const windows = new Set();
  const NS = "http://www.w3.org/2000/svg";
  const PAD = 24;
  const svgEl = (tag, attrs = {}, cls = "") => {
    const el = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, String(v));
    if (cls) el.setAttribute("class", cls);
    return el;
  };
  //: Words wrapped to the box by an average glyph width: a picture to read, not the board's own layout engine.
  function words(group, text, x, y, w, h, size, colour, centred) {
    const per = Math.max(4, Math.floor((w - 16) / (size * 0.55)));
    const lines = [];
    for (const para of String(text || "").split("\n")) {
      let line = "";
      for (const word of para.split(/\s+/)) {
        if (line && (line + " " + word).length > per) lines.push(line), (line = word);
        else line = line ? `${line} ${word}` : word;
      }
      lines.push(line);
    }
    const fit = lines.slice(0, Math.max(1, Math.floor((h - 8) / (size * 1.3))));
    const t = svgEl("text", { x: centred ? x + w / 2 : x + 8, "font-size": size, "text-anchor": centred ? "middle" : "start" }, "doc-board-words");
    if (colour) t.style.fill = colour;
    const top = centred ? y + h / 2 - ((fit.length - 1) * size * 1.3) / 2 + size * 0.35 : y + 8 + size;
    fit.forEach((line, i) => {
      const span = svgEl("tspan", { x: t.getAttribute("x"), y: top + i * size * 1.3 });
      span.textContent = line;
      t.append(span);
    });
    group.append(t);
  }
  const SHAPES = {
    ellipse: (x, y, w, h) => svgEl("ellipse", { cx: x + w / 2, cy: y + h / 2, rx: w / 2, ry: h / 2 }),
    circle: (x, y, w, h) => SHAPES.ellipse(x, y, w, h),
    pill: (x, y, w, h) => svgEl("rect", { x, y, width: w, height: h, rx: Math.min(w, h) / 2 }),
    diamond: (x, y, w, h) => svgEl("polygon", { points: `${x + w / 2},${y} ${x + w},${y + h / 2} ${x + w / 2},${y + h} ${x},${y + h / 2}` }),
    hexagon: (x, y, w, h) => svgEl("polygon", { points: `${x + w / 4},${y} ${x + (3 * w) / 4},${y} ${x + w},${y + h / 2} ${x + (3 * w) / 4},${y + h} ${x + w / 4},${y + h} ${x},${y + h / 2}` }),
  };
  //: The board as one SVG, from `GET /whiteboard/?board_id=`: frames under everything, then connectors, then items by their z.
  function picture(board) {
    const layersOff = new Set((board.layers || []).filter((l) => l.hidden || l.visible === false).map((l) => l.id ?? l.name));
    const shown = (d) => !d?.hidden && !(d?.layer != null && layersOff.has(d.layer));
    const titles = new Map((typeof allEntries !== "undefined" ? allEntries : []).map((e) => [e.id, e.title]));
    const items = [];
    for (const n of board.nodes || []) if (!n.hidden) items.push({ kind: "node", key: [`node:${n.entry_id}`, `node:${n.id}`], x: n.x, y: n.y, w: n.width || 250, h: n.height || 150, z: n.z || 0, rot: n.rotation, text: titles.get(n.entry_id) || "Note" });
    for (const o of board.objects || []) if (shown(o.data)) items.push({ kind: o.kind, key: [`${o.kind}:${o.id}`, `object:${o.id}`], x: o.x, y: o.y, w: o.width || 160, h: o.height || 80, z: o.z || 0, rot: o.rotation, d: o.data || {}, text: o.data?.content || o.data?.name || o.data?.caption || "" });
    const at = new Map();
    for (const it of items) for (const k of it.key) at.set(k, [it.x + it.w / 2, it.y + it.h / 2]);
    const strokes = [];
    for (const sk of board.sketches || []) {
      let d = null;
      try { d = typeof sk.data === "string" ? JSON.parse(sk.data) : sk.data; } catch { d = null; }
      if (d && shown(d)) strokes.push({ ...d, x: sk.x || 0, y: sk.y || 0 });
    }
    const box = [Infinity, Infinity, -Infinity, -Infinity];
    const grow = (x, y) => ((box[0] = Math.min(box[0], x)), (box[1] = Math.min(box[1], y)), (box[2] = Math.max(box[2], x)), (box[3] = Math.max(box[3], y)));
    for (const it of items) grow(it.x, it.y), grow(it.x + it.w, it.y + it.h);
    const lines = [];
    for (const s of strokes) {
      if (String(s.type || "").startsWith("link-")) {
        const a = s.sourcePoint ? [s.sourcePoint.x, s.sourcePoint.y] : at.get(`${s.sourceKind || "node"}:${s.sourceId}`);
        const b = s.targetPoint ? [s.targetPoint.x, s.targetPoint.y] : at.get(`${s.targetKind || "node"}:${s.targetId}`);
        if (a && b) lines.push({ s, pts: [a, ...(s.points || []).map((p) => [p.x, p.y]), b] }), grow(...a), grow(...b);
      } else if (s.d) {
        //: A pen stroke's box is its path's, which only the browser measures; its origin keeps it inside the frame.
        lines.push({ s, path: true }), grow(s.x, s.y);
      }
    }
    if (!Number.isFinite(box[0])) box.splice(0, 4, 0, 0, 320, 160);
    const vb = [box[0] - PAD, box[1] - PAD, box[2] - box[0] + 2 * PAD, box[3] - box[1] + 2 * PAD].map((v) => Math.round(v));
    const svg = svgEl("svg", { viewBox: vb.join(" "), role: "img" }, "md-mermaid-img doc-board-svg");
    svg.mermaidSvg = `<svg xmlns="${NS}" viewBox="${vb.join(" ")}"></svg>`;
    const order = items.filter((it) => it.kind === "frame").concat(["lines"], items.filter((it) => it.kind !== "frame").sort((p, q) => p.z - q.z));
    for (const it of order) {
      if (it === "lines") {
        for (const { s, pts, path } of lines) {
          const el = path ? svgEl("path", { d: s.d, transform: `translate(${s.x} ${s.y})` }) : svgEl("polyline", { points: pts.map((p) => p.join(",")).join(" ") });
          el.setAttribute("class", "doc-board-line");
          if (s.color) el.style.stroke = s.color;
          el.style.strokeWidth = String(s.width || 2);
          if (path && s.fill) el.style.fill = s.fill;
          svg.append(el);
        }
        continue;
      }
      const g = svgEl("g", {}, `doc-board-item doc-board-${it.kind}${it.d?.sticky ? " doc-board-sticky" : ""}`);
      if (it.rot) g.setAttribute("transform", `rotate(${it.rot} ${it.x + it.w / 2} ${it.y + it.h / 2})`);
      const d = it.d || {};
      const shape = d.shape === "none" || d.shape === "underline" ? null : (SHAPES[d.shape] || ((x, y, w, h) => svgEl("rect", { x, y, width: w, height: h, rx: 8 })))(it.x, it.y, it.w, it.h);
      if (shape) {
        shape.setAttribute("class", "doc-board-shape");
        if (d.bg) shape.style.fill = d.bg;
        if (d.border_color) shape.style.stroke = d.border_color;
        if (d.border_width) shape.style.strokeWidth = String(d.border_width);
        g.append(shape);
      }
      if (it.kind === "image" && d.url) {
        g.append(svgEl("image", { href: d.url, x: it.x, y: it.y, width: it.w, height: it.h, preserveAspectRatio: "xMidYMid slice" }));
      } else if (it.kind === "frame") {
        words(g, it.text, it.x, it.y - 22, it.w, 30, 14, d.color, false);
      } else {
        const size = Number(d.font_size) || (it.kind === "node" ? 16 : 15);
        words(g, it.text || it.kind, it.x, it.y, it.w, it.h, size, d.color, d.align ? d.align === "center" : it.kind !== "text" || Boolean(d.shape));
      }
      svg.append(g);
    }
    svg.setAttribute("aria-label", `A board with ${nounCount(items.length, "item")}`);
    return svg;
  }

  async function fill(win) {
    win.host.setAttribute("aria-busy", "true");
    try {
      const board = await apiJson(`/whiteboard/?board_id=${win.id}`);
      if (!win.host.isConnected && !windows.has(win)) return;
      const pic = picture(board);
      win.fig.querySelector(".md-mermaid-img")?.remove();
      win.fig.append(pic);
      win.count = pic.querySelectorAll(".doc-board-item").length;
      win.host.dataset.items = String(win.count);
      for (const paint of win.fig.onpaint || []) paint();
    } catch (error) {
      toast(voiceLine("failed", { what: "The board", why: error?.message || "it could not be read" }));
    } finally {
      win.host.removeAttribute("aria-busy");
    }
  }

  async function mount(button, id) {
    const host = document.createElement("div");
    host.className = "dgm doc-board-live";
    host.dataset.boardId = String(id);
    const head = document.createElement("div");
    head.className = "doc-board-live-head";
    const fig = document.createElement("div");
    fig.className = "dgm-picture doc-board-picture";
    host.append(head, fig);
    const nth = [...document.querySelectorAll(`.doc-embed-board-live[data-board-id="${id}"]`)].indexOf(button);
    const win = { id, button, host, fig, nth, count: 0 };
    head.append(smallButton("ph:arrow-clockwise Refresh", "Read this board again", () => fill(win)));
    windows.add(win);
    button.after(host);
    button.setAttribute("aria-pressed", "true");
    lazyScript("/css/diagram-lazy.css");
    await fill(win);
    if ((await ensureModule("vf")) && (await ensureModule("diagramView"))) diagramModel.view.wire({ fig });
    else lazyLoadFailed("The board window");
  }

  function unmount(win) {
    windows.delete(win);
    win.host.remove();
    win.button.setAttribute("aria-pressed", "false");
  }

  document.addEventListener("board-live", (event) => {
    const button = event.target;
    const win = [...windows].find((w) => w.button === button);
    if (win) unmount(win);
    else mount(button, event.detail.id);
  });
  //: Edit here closed: the document may have redrawn its cards, so each window goes back after its card's new button (the same
  //: board, the same place), keeping its zoom; then the windows on the edited board read it again. A card that is gone takes its window.
  document.addEventListener("board-edited", (event) => setTimeout(() => {
    for (const win of windows) {
      if (!win.button.isConnected) {
        const same = document.querySelectorAll(`.doc-embed-board-live[data-board-id="${win.id}"]`)[win.nth];
        if (!same) {
          windows.delete(win);
          win.host.remove();
          continue;
        }
        win.button = same;
        same.after(win.host);
        same.setAttribute("aria-pressed", "true");
      }
      if (win.id === event.detail.id) fill(win);
    }
  }, 0));
})();
