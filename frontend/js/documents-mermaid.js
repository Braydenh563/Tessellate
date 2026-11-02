// documents-mermaid.js: Mermaid fences, the in-house flowchart reader and the
// Live figure widget (split out of documents.js, audit 1031 DC13 remainder).
//
// What is here: the pure flowchart reader (`mermaidFlowParse`,
// `mermaidFlowLayout`, bracketed by `DOC-MERMAID-BEGIN`/`END` for
// `tests/test_doc_mermaid.py`), the hand-over of a fence to the lazy `mermaid`
// module (`docRenderMermaidIn`, `docMermaidWhenDrawn`) and the Live state field
// that draws a fence as its figure (`docMermaidField`). What stayed in
// documents.js: `docPhase2State` (shared with the embeds and the print sheet)
// and the editor extension list that calls `docMermaidField`.
//
// **Loaded in the Library bundle, before documents.js**, the way
// documents-props.js is: documents.js and documents-export.js call in here only
// from inside functions, while this file's own top level declares and reads
// nothing from either (`docPhase2State`, `docStr`, `ensureModule` are read when
// a function runs). One closure; what other files call is the `Object.assign`
// at the foot.
(() => {
  // -----------------------------------------------------------------------------
  // Mermaid fences (DOCUMENTS_PLAN decisions 3 and 6, BACKLOG steps 8 and 12b)
  // -----------------------------------------------------------------------------
  //
  //: **Every ```mermaid fence is drawn by Mermaid itself**, in Read (so in a print
  //: and the HTML export) and in Live while the caret is outside the fence. The
  //: library is vendored (`frontend/vendor/mermaid/`) and lives in a hidden
  //: same-origin frame that the lazy `mermaid` module (mermaid-draw.js) creates
  //: on the first fence; nothing of it is in the boot scripts. This file only
  //: hands a fence over (`docRenderMermaidIn`, the Live widget below) and waits
  //: for the picture when a page is printed or saved.
  //:
  //: What stays here is the small in-house flowchart reader, pure and node-tested
  //: (`tests/test_doc_mermaid.py`): `mermaidFlowParse` reads a flowchart fence
  //: into nodes and links (flowchart or graph, TD, TB, BT, LR or RL, seven
  //: shapes, six link kinds, labels, chains, fans) and `mermaidFlowLayout`
  //: places it in layers (ranks by longest path with the cycles' back links
  //: reversed, barycentre sweeps, each layer centred). They no longer draw
  //: anything; the diagram verifier and a board import are what they are kept
  //: for. Anything the reader does not read whole is still handed to Mermaid.
  // DOC-MERMAID-BEGIN
  const MERMAID_SHAPES = [
    ["([", "])", "stadium"], ["((", "))", "circle"], ["{{", "}}", "hexagon"],
    ["[", "]", "rect"], ["(", ")", "round"], ["{", "}", "diamond"],
  ];
  const MERMAID_IGNORED = /^(style|classDef|class|linkStyle|click)\b/;
  //: Longest first, so `-.->` is not read as `-.-` and a stray `>`.
  const MERMAID_LINKS = [
    ["-.->", "dotted", true], ["==>", "thick", true], ["-->", "solid", true],
    ["-.-", "dotted", false], ["===", "thick", false], ["---", "solid", false],
  ];
  const MERMAID_MAX_NODES = 120;

  function mermaidFlowUnquote(text) {
    const t = text.trim();
    return t.length >= 2 && t[0] === '"' && t[t.length - 1] === '"' ? t.slice(1, -1) : t;
  }

  //: One node reference: an id and, optionally, its shape and text. Returns the
  //: node and how many characters it took, or null.
  function mermaidFlowNode(src, at) {
    //: A hyphen only between word characters: `a-->b` is a, a link and b.
    const id = /^[A-Za-z0-9_]+(?:-[A-Za-z0-9_]+)*/.exec(src.slice(at));
    if (!id) return null;
    let i = at + id[0].length;
    for (const [open, close, shape] of MERMAID_SHAPES) {
      if (src.startsWith(open, i)) {
        const end = src.indexOf(close, i + open.length);
        if (end === -1) return null;
        const text = mermaidFlowUnquote(src.slice(i + open.length, end));
        return { id: id[0], shape, text, end: end + close.length };
      }
    }
    return { id: id[0], shape: null, text: null, end: i };
  }

  function mermaidFlowLink(src, at) {
    const rest = src.slice(at);
    //: `-- text -->`, `-. text .->`, `== text ==>`.
    const worded = /^(--|-\.|==)\s*([^-.=|>][^|>]*?)\s*(-->|\.->|==>|---|-\.-|===)/.exec(rest);
    if (worded) {
      const head = MERMAID_LINKS.find(([s]) => s === worded[3] || (worded[3] === ".->" && s === "-.->"));
      const style = worded[1] === "-." ? "dotted" : worded[1] === "==" ? "thick" : "solid";
      return { style, arrow: head ? head[2] : true, label: mermaidFlowUnquote(worded[2]), end: at + worded[0].length };
    }
    for (const [token, style, arrow] of MERMAID_LINKS) {
      if (!rest.startsWith(token)) continue;
      let end = at + token.length;
      let label = "";
      const piped = /^\s*\|([^|]*)\|/.exec(src.slice(end));
      if (piped) {
        label = mermaidFlowUnquote(piped[1]);
        end += piped[0].length;
      }
      return { style, arrow, label, end };
    }
    return null;
  }

  //: The text of a fence as nodes and edges, or null when it is not a flowchart
  //: this reads whole.
  function mermaidFlowParse(source) {
    const lines = String(source || "").replace(/\r/g, "").split(/\n|;/).map((l) => l.replace(/%%.*$/, "").trim()).filter(Boolean);
    if (!lines.length) return null;
    const head = /^(flowchart|graph)(?:\s+(TD|TB|BT|LR|RL))?\s*$/i.exec(lines[0]);
    if (!head) return null;
    const dir = (head[2] || "TD").toUpperCase().replace("TB", "TD");
    const nodes = new Map();
    const edges = [];
    const touch = (n) => {
      const had = nodes.get(n.id);
      if (!had) nodes.set(n.id, { id: n.id, shape: n.shape || "rect", text: n.text ?? n.id, order: nodes.size });
      else if (n.shape) Object.assign(had, { shape: n.shape, text: n.text ?? had.text });
    };
    for (const line of lines.slice(1)) {
      if (MERMAID_IGNORED.test(line)) continue;
      let at = 0;
      let group = [];
      let pending = null;
      const skip = () => {
        while (at < line.length && /\s/.test(line[at])) at++;
      };
      for (;;) {
        skip();
        const node = mermaidFlowNode(line, at);
        if (!node) return null;
        touch(node);
        group.push(node.id);
        at = node.end;
        skip();
        if (line[at] === "&") {
          at++;
          continue;
        }
        if (pending) {
          for (const from of pending.from) for (const to of group) edges.push({ from, to, style: pending.style, arrow: pending.arrow, label: pending.label });
        }
        if (at >= line.length) break;
        const link = mermaidFlowLink(line, at);
        if (!link) return null;
        pending = { from: group, ...link };
        group = [];
        at = link.end;
      }
      if (nodes.size > MERMAID_MAX_NODES) return null;
    }
    if (!nodes.size) return null;
    return { dir, nodes: [...nodes.values()], edges };
  }

  //: Layers, then places. `measure(text)` is a width in px; the default is an
  //: estimate so node can run this.
  function mermaidFlowLayout(graph, measure = (t) => t.length * 7.4) {
    const across = graph.dir === "LR" || graph.dir === "RL";
    const ids = graph.nodes.map((n) => n.id);
    const out = new Map(ids.map((id) => [id, []]));
    const into = new Map(ids.map((id) => [id, []]));
    //: The back links of every cycle, found by a walk in the order the nodes
    //: were written, are ranked as if reversed: a loop still draws, upward.
    const state = new Map();
    const back = new Set();
    const visit = (id) => {
      state.set(id, 1);
      graph.edges.forEach((e, k) => {
        if (e.from !== id || e.from === e.to) return;
        if (state.get(e.to) === 1) back.add(k);
        else if (!state.get(e.to)) visit(e.to);
      });
      state.set(id, 2);
    };
    for (const id of ids) if (!state.get(id)) visit(id);
    graph.edges.forEach((e, k) => {
      if (e.from === e.to) return;
      const [a, b] = back.has(k) ? [e.to, e.from] : [e.from, e.to];
      out.get(a).push(b);
      into.get(b).push(a);
    });
    const rank = new Map();
    const rankOf = (id, seen = new Set()) => {
      if (rank.has(id)) return rank.get(id);
      if (seen.has(id)) return 0;
      seen.add(id);
      const r = into.get(id).length ? Math.max(...into.get(id).map((p) => rankOf(p, seen) + 1)) : 0;
      rank.set(id, r);
      return r;
    };
    ids.forEach((id) => rankOf(id));
    const layers = [];
    for (const id of ids) (layers[rank.get(id)] ||= []).push(id);
    const pos = new Map();
    const reindex = () => layers.forEach((layer) => layer.forEach((id, i) => pos.set(id, i)));
    reindex();
    const bary = (id, side) => {
      const near = side.get(id);
      return near.length ? near.reduce((s, n) => s + pos.get(n), 0) / near.length : pos.get(id);
    };
    for (let sweep = 0; sweep < 4; sweep++) {
      const down = sweep % 2 === 0;
      const order = down ? layers.slice(1) : layers.slice(0, -1).reverse();
      for (const layer of order) {
        layer.sort((a, b) => bary(a, down ? into : out) - bary(b, down ? into : out) || pos.get(a) - pos.get(b));
        layer.forEach((id, i) => pos.set(id, i));
      }
    }
    const byId = new Map(graph.nodes.map((n) => [n.id, n]));
    const size = new Map();
    for (const n of graph.nodes) {
      const w = Math.max(48, Math.ceil(measure(n.text)) + 28);
      const h = 38;
      if (n.shape === "diamond") size.set(n.id, { w: w + 28, h: h + 22 });
      else if (n.shape === "circle") size.set(n.id, { w: Math.max(w, 60), h: Math.max(w, 60) });
      else size.set(n.id, { w, h });
    }
    //: Main axis (down the ranks) and cross axis (along a rank), turned for LR.
    const main = (s) => (across ? s.w : s.h);
    const cross = (s) => (across ? s.h : s.w);
    const gapMain = 56;
    const gapCross = 28;
    const pad = 12;
    const rankSpan = layers.map((layer) => Math.max(...layer.map((id) => main(size.get(id)))));
    const rankWidth = layers.map((layer) => layer.reduce((s, id) => s + cross(size.get(id)), 0) + gapCross * (layer.length - 1));
    const widest = Math.max(...rankWidth);
    const place = new Map();
    let along = pad;
    layers.forEach((layer, r) => {
      let c = pad + (widest - rankWidth[r]) / 2;
      for (const id of layer) {
        const s = size.get(id);
        const mid = along + rankSpan[r] / 2;
        const cmid = c + cross(s) / 2;
        place.set(id, across ? { x: mid, y: cmid } : { x: cmid, y: mid });
        c += cross(s) + gapCross;
      }
      along += rankSpan[r] + gapMain;
    });
    const total = { main: along - gapMain + pad, cross: widest + pad * 2 };
    let width = across ? total.main : total.cross;
    let height = across ? total.cross : total.main;
    //: BT and RL are TD and LR mirrored.
    if (graph.dir === "BT") for (const p of place.values()) p.y = height - p.y;
    if (graph.dir === "RL") for (const p of place.values()) p.x = width - p.x;
    const boxes = graph.nodes.map((n) => ({ ...byId.get(n.id), ...place.get(n.id), ...size.get(n.id) }));
    const at = new Map(boxes.map((b) => [b.id, b]));
    //: Where a line meets a box: its outline on the line toward the other
    //: point (a diamond's and a circle's own, a rectangle's for the rest).
    const edgePoint = (b, toward) => {
      const dx = toward.x - b.x;
      const dy = toward.y - b.y;
      if (!dx && !dy) return { x: b.x, y: b.y };
      let s;
      if (b.shape === "diamond") s = 1 / (Math.abs(dx) / (b.w / 2) + Math.abs(dy) / (b.h / 2));
      else if (b.shape === "circle") s = (b.w / 2) / Math.hypot(dx, dy);
      else s = Math.min(dx ? (b.w / 2) / Math.abs(dx) : Infinity, dy ? (b.h / 2) / Math.abs(dy) : Infinity);
      return { x: b.x + dx * s, y: b.y + dy * s };
    };
    const lines = graph.edges.map((e) => {
      const a = at.get(e.from);
      const b = at.get(e.to);
      if (e.from === e.to) {
        const top = { x: a.x + a.w / 2, y: a.y - a.h / 4 };
        return { ...e, d: `M${top.x} ${top.y} c 30 -20 30 ${a.h / 2 + 20} 0 ${a.h / 2}`, mid: { x: top.x + 26, y: a.y } };
      }
      //: **A line that would lie on another bows aside**: a link back up the
      //: flow (a loop's return), the second of two links between one pair, and
      //: one that skips a rank (it would cross the box between) are curves
      //: whose middle is pushed off the straight line, to the right of the flow
      //: for a return and to alternate sides for the rest.
      const k = graph.edges.indexOf(e);
      const twin = graph.edges.findIndex((o, j) => j < k && ((o.from === e.from && o.to === e.to) || (o.from === e.to && o.to === e.from)));
      const backward = rank.get(e.to) <= rank.get(e.from);
      const skips = Math.abs(rank.get(e.to) - rank.get(e.from)) > 1;
      const bend = backward ? 46 : twin !== -1 ? -46 : skips ? 40 * (k % 2 ? -1 : 1) : 0;
      if (!bend) {
        const p = edgePoint(a, b);
        const q = edgePoint(b, a);
        const mid = { x: (p.x + q.x) / 2, y: (p.y + q.y) / 2 };
        return { ...e, d: `M${p.x.toFixed(1)} ${p.y.toFixed(1)} L${q.x.toFixed(1)} ${q.y.toFixed(1)}`, mid };
      }
      const dx = b.x - a.x;
      const dy = b.y - a.y;
      const len = Math.hypot(dx, dy) || 1;
      const c = { x: (a.x + b.x) / 2 - (dy / len) * bend * 2, y: (a.y + b.y) / 2 + (dx / len) * bend * 2 };
      const p = edgePoint(a, c);
      const q = edgePoint(b, c);
      const mid = { x: 0.25 * p.x + 0.5 * c.x + 0.25 * q.x, y: 0.25 * p.y + 0.5 * c.y + 0.25 * q.y };
      const f = (n) => n.toFixed(1);
      return { ...e, d: `M${f(p.x)} ${f(p.y)} Q${f(c.x)} ${f(c.y)} ${f(q.x)} ${f(q.y)}`, mid };
    });
    //: A curve may bow past an edge: the box grows to hold it, on any side.
    let x0 = 0;
    let y0 = 0;
    for (const line of lines) {
      if (line.from === line.to) continue;
      const nums = line.d.match(/-?[\d.]+/g).map(Number);
      for (let i = 0; i + 1 < nums.length; i += 2) {
        x0 = Math.min(x0, nums[i] - 12);
        y0 = Math.min(y0, nums[i + 1] - 12);
        width = Math.max(width, nums[i] + 12);
        height = Math.max(height, nums[i + 1] + 12);
      }
    }
    return { x0: Math.floor(x0), y0: Math.floor(y0), width: Math.ceil(width - x0), height: Math.ceil(height - y0), boxes, lines };
  }
  // DOC-MERMAID-END

  //: Read (and so the print and the HTML export, which are drawn from it): each
  //: mermaid fence is handed to the lazy `mermaid` module (mermaid-draw.js), which
  //: asks the diagram frame and swaps the fence for its picture; one the parser
  //: refuses stays the code block with the reason under it. The promise is kept
  //: so an export or a print can wait for the pictures before it saves the page.
  function docRenderMermaidIn(container) {
    if (!container.querySelector('.code-block code[data-lang="mermaid"]')) return;
    docPhase2State.mermaidDrawn = ensureModule("mermaid")
      .then((ok) => (ok ? mermaidDrawIn(container) : null))
      .catch(() => null);
  }

  //: Resolves when the pictures of the page being saved or printed are in.
  async function docMermaidWhenDrawn() {
    await docPhase2State.mermaidDrawn;
    //: Only a page that loaded the module has pictures to wait for.
    if (await lazyModuleLoads.get("mermaid")) await mermaidSettled();
  }

  //: Live: a mermaid fence the caret is outside of is its figure, through a
  //: state field for the reason the columns block gives (a replace that spans
  //: line breaks may not come from a plugin). Pressing the figure puts the
  //: caret on the fence's first line, which shows the text to edit.
  function docMermaidBlocks(text) {
    const blocks = [];
    const re = /^```[ \t]*mermaid[^\n]*\n([\s\S]*?)\n```[ \t]*$/gm;
    for (let m = re.exec(text); m; m = re.exec(text)) {
      blocks.push({ from: m.index, to: m.index + m[0].length, source: m[1] });
    }
    return blocks;
  }

  function docMermaidField(CM) {
    if (docPhase2State.mermaidFieldCache) return docPhase2State.mermaidFieldCache;
    const { StateField, StateEffect } = CM.state;
    const { Decoration, EditorView, WidgetType } = CM.view;
    //: Sent when a fence the frame refused is known, so the field draws it as the
    //: code it is (with the reason) instead of leaving a figure that never fills.
    const recheck = StateEffect.define();
    class DocMermaidWidget extends WidgetType {
      constructor(source, from) {
        super();
        this.source = source;
        this.from = from;
      }
      eq(other) {
        return other.source === this.source && other.from === this.from;
      }
      //: What CodeMirror assumes for a widget it has not measured; the figure's
      //: placeholder is about this tall (mermaid-lazy.css), so the page does not jump.
      get estimatedHeight() {
        return 160;
      }
      ignoreEvent(event) {
        return event.type !== "mousedown";
      }
      toDOM(view) {
        const figure = document.createElement("figure");
        figure.className = "md-mermaid cm-md-mermaid md-mermaid-pending";
        figure.title = "Press to edit the diagram's text";
        //: Async: the placeholder holds the room, then the picture replaces it
        //: and the editor measures the widget again.
        ensureModule("mermaid").then((ok) => {
          if (!ok) return;
          docPhase2State.mermaidReady = true;
          mermaidFill(figure, this.source, (result) => {
            if (result.svg) view.requestMeasure();
            else view.dispatch({ effects: recheck.of(this.source) });
          });
        });
        figure.addEventListener("mousedown", (event) => {
          event.preventDefault();
          const at = Math.min(this.from + 4, view.state.doc.length);
          view.dispatch({ selection: { anchor: at } });
          view.focus();
        });
        return figure;
      }
    }
    class DocMermaidReason extends WidgetType {
      constructor(reason, source) {
        super();
        this.reason = reason;
        this.source = source;
      }
      eq(other) {
        return other.reason === this.reason && other.source === this.source;
      }
      toDOM() {
        return mermaidFailure.note(this.reason, this.source);
      }
    }
    const build = (state) => {
      const text = docStr(state.doc);
      if (!text.includes("```mermaid") && !/```[ \t]+mermaid/.test(text)) return Decoration.none;
      const ranges = [];
      for (const block of docMermaidBlocks(text)) {
        //: A reason exists only once the module drew here (the widget above).
        const reason = docPhase2State.mermaidReady ? mermaidFailure(block.source) : "";
        //: A fence the frame refused stays the code it is, with its reason under it.
        if (reason) {
          ranges.push(Decoration.widget({ widget: new DocMermaidReason(reason, block.source), block: true, side: 1 }).range(block.to));
          continue;
        }
        if (docLiveSpanTouched.anchorIn(state.selection.ranges, block.from, block.to)) continue;
        ranges.push(Decoration.replace({ widget: new DocMermaidWidget(block.source, block.from), block: true }).range(block.from, block.to));
      }
      return Decoration.set(ranges, true);
    };
    docPhase2State.mermaidFieldCache = StateField.define({
      create: (state) => build(state),
      update: (value, tr) => (tr.docChanged || tr.selection || tr.effects.some((e) => e.is(recheck)) ? build(tr.state) : value),
      provide: (field) => EditorView.decorations.from(field),
    });
    return docPhase2State.mermaidFieldCache;
  }

  //: The file's whole surface: what documents.js and documents-export.js call.
  Object.assign(window, { docRenderMermaidIn, docMermaidWhenDrawn, docMermaidField });
})();
