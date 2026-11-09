// diagram-tree-canvas.js: a mind map and a timeline edited on their picture (INBOX 1661 l). Lazy: fetched by
// diagram-seq-canvas.js's `wire` for those kinds, whose `edit` gives the press, the rename in place and the keys.
// Mermaid tags no part of these drawings with a row, but it numbers every box in the order it read the source (a mind
// map's `<g class="node mindmap-node" id="…-node_N">`, a timeline's `<path id="…-node-N">`), and that is the order the
// model prints. So box N is row N of that walk, and its words are checked against the row's: a drawing a step behind the
// model leaves the box out rather than give it to a neighbour, and two parts with one name still land on their own rows.
// A press on a box starts the blocks list's own drag (diagram-kinds.js `seedBlock`), and `spot` says where it lands.
(() => {
  const num = (tag, name) => Number((new RegExp(`\\s${name}="(-?[\\d.]+)"`).exec(tag) || [])[1]);
  const shift = (tag) => (/translate\((-?[\d.]+)[ ,]+(-?[\d.]+)\)/.exec(tag) || []).slice(1).map(Number);
  const ENT = { amp: "&", lt: "<", gt: ">", quot: '"', apos: "'", nbsp: " " };
  //: The words only: entities read, tags and marks dropped (Mermaid draws `**a**` as a, closes a `<b>`, wraps a long name).
  const words = (t) => String(t ?? "").replace(/&(#\d+|\w+);/g, (all, e) => (e[0] === "#" ? String.fromCodePoint(Number(e.slice(1))) : ENT[e] ?? all))
    .replace(/<[^>]*>/g, "").toLowerCase().replace(/[^\p{L}\p{N}]/gu, "");
  const said = (seg) => [...seg.matchAll(/<tspan\b[^>]*>([^<]*)<\/tspan>/g)].map((m) => m[1]).join(" ");

  //: Every box of a drawn mind map or timeline, in drawing units: `{n, x, y, w, h, text}` (centre-based, n is Mermaid's number).
  function parts(svg) {
    const vb = (/viewBox="([^"]+)"/.exec(svg || "")?.[1] || "").trim().split(/[\s,]+/).map(Number);
    if (vb.length !== 4 || vb.some(Number.isNaN)) return null;
    const out = [];
    const mm = [...svg.matchAll(/<g\b[^>]*class="node mindmap-node[^"]*"[^>]*>/g)];
    mm.forEach((m, i) => {
      const seg = svg.slice(m.index + m[0].length, mm[i + 1]?.index ?? svg.length);
      const [x, y] = shift(m[0]);
      //: The words are centred on the node (the label's own shift is half their size); a box pads them 20 by 5, a circle is its radius.
      const [lx, ly] = shift(/<g\b[^>]*class="label"[^>]*>/.exec(seg)?.[0] || "");
      const r = num(/<circle\b[^>]*>/.exec(seg)?.[0] || "", "r") || 0;
      const n = Number(/-node_(\d+)"/.exec(m[0])?.[1]);
      if (!Number.isNaN(x + y + n)) out.push({ n, x, y, w: Math.max(2 * Math.abs(lx || 0) + 40, 2 * r), h: Math.max(2 * Math.abs(ly || 0) + 10, 2 * r), text: said(seg) });
    });
    const tl = mm.length ? [] : [...svg.matchAll(/<path\b[^>]*id="[^"]*-node-(\d+)"[^>]*>/g)];
    tl.forEach((m, i) => {
      //: A timeline box sits in its wrapper's shift (the last one before it); the line under it is its width and its height.
      const [x, y] = shift(svg.slice(svg.lastIndexOf('transform="translate(', m.index), m.index));
      const seg = svg.slice(m.index, tl[i + 1]?.index ?? svg.length);
      const line = /<line\b[^>]*class="node-line[^"]*"[^>]*>/.exec(seg)?.[0] || "";
      const [w, h] = [num(line, "x2"), num(line, "y1")];
      if (!Number.isNaN(x + y + w + h)) out.push({ n: Number(m[1]), x: x + w / 2, y: y + h / 2, w, h, text: said(seg) });
    });
    return { vb, parts: out };
  }

  //: The rows in the order Mermaid numbers its boxes: a mind map from its centre down, each branch before the next; a
  //: timeline's sections with their periods and events, or (no sections) its periods. Mermaid draws no period that is
  //: outside every section once there is one.
  function order(A, m) {
    const rows = [];
    if (A.name === "mindmap") {
      const walk = (n) => (rows.push(n), n.children.forEach(walk));
      if (m.root) walk(m.root);
    } else {
      const period = (p) => rows.push(p, ...p.events);
      if (m.sections.length) m.sections.forEach((s) => (rows.push(s), s.periods.forEach(period)));
      else m.free.forEach(period);
    }
    return rows;
  }

  //: The overlay's `S.hit`: each box under its row's key, `et` the row's type.
  function boxes(svg, A, m, key) {
    const read = parts(svg);
    if (!read) return null;
    const rows = order(A, m);
    const found = [];
    for (const p of read.parts) {
      const row = rows[p.n];
      const [drawn, own] = [words(p.text), words(row && A.text(row))];
      if (row && (!drawn || !own || drawn === own)) found.push({ id: key(row), et: row.type, x: p.x, y: p.y, w: p.w, h: p.h });
    }
    return found.length ? { vb: read.vb, boxes: found, clusters: [] } : null;
  }

  //: Where a row of `type` (the dragged row `skip`, or a new one) lands dropped at drawing point (vx, vy): before or after
  //: the box under it, along the way its sisters run (an event's down its period, the rest across), or into it in the
  //: middle; the list's own thresholds (diagram-kinds.js `dropAt`). Null off a box, on the dragged row or inside it.
  function spot(A, m, hit, vx, vy, type, skip = null) {
    const ops = diagramModel.kinds.ops;
    const b = hit?.boxes.find((o) => Math.abs(vx - o.x) <= o.w / 2 && Math.abs(vy - o.y) <= o.h / 2);
    const f = b && b.id !== skip && ops.find(A, m, b.id);
    const dragged = skip && ops.find(A, m, skip);
    if (!f) return null;
    let inside = false;
    if (dragged) ops.walk(A, m, (n) => n === f.node && (inside = true), dragged.node);
    if (inside) return null;
    const down = A.name === "timeline" && type === "e";
    const frac = down ? (vy - b.y + b.h / 2) / b.h : (vx - b.x + b.w / 2) / b.w;
    const holds = ops.level(A, m, f.node, type);
    const beside = !f.level.fixed && f.level.types.includes(type);
    //: "After" is before the next sister that is not the dragged row itself (a move before itself is no move).
    const next = f.list.slice(f.list.indexOf(f.node) + 1).find((n) => n !== dragged?.node) || null;
    if (beside && (frac < 0.28 || (!holds && frac < 0.5))) return { op: "before", parent: f.parent, before: f.node, key: b.id };
    if (beside && (frac > 0.72 || !holds)) return { op: "after", parent: f.parent, before: next, key: b.id };
    return holds ? { op: "into", parent: f.node, before: null, key: b.id } : null;
  }

  const imgOf = (S) => S?.fig?.querySelector(".md-mermaid-img");
  const boxEl = (S, key) => S.fig.querySelector(`.dgm-overlay .dgm-box[data-node="${CSS.escape(key)}"]`);
  const pointAt = (S, x, y) => {
    const r = imgOf(S).getBoundingClientRect();
    const [vx, vy, vw, vh] = S.hit.vb;
    return [vx + ((x - r.left) / r.width) * vw, vy + ((y - r.top) / r.height) * vh];
  };

  //: A press on a drawn box (diagram-kinds.js `seedBlock`): the row it is, for the list's drag to carry. The centre is not dragged.
  function node(event, panes) {
    const img = event.target.closest?.(".dgm-stage .md-mermaid-img");
    const S = img && panes.get(img.closest(".dgm"));
    if (!S?.k || S.seq || !S.hit || !S.hitAt || event.shiftKey || event.ctrlKey || event.metaKey || event.altKey) return null;
    const key = S.hitAt(event);
    const f = key && diagramModel.kinds.ops.find(S.k, S.m, key);
    const box = f && !f.level.fixed ? boxEl(S, key) : null;
    return box ? { S, key, box } : null;
  }

  //: A row or a shelf tile over the picture (diagram-kinds.js `dropAt` asks): its place by the box under the pointer, the
  //: box ringed and the caption saying where. Null off every box (a tile then lands after the selection, as a press adds it).
  function over(g) {
    const { S } = g;
    if (!S?.hit || S.seq || !imgOf(S)) return null;
    const type = g.tile ? g.tile.type : diagramModel.kinds.ops.find(S.k, S.m, g.key)?.node.type;
    const s = type && spot(S.k, S.m, S.hit, ...pointAt(S, g.x, g.y), type, g.key || null);
    const card = s && boxEl(S, s.key);
    if (!card) return null;
    const name = diagramModel.kinds.act.name(S, s.key);
    return { canvas: true, op: s.op, parent: s.parent, before: s.before, card, word: `${{ before: "Before", after: "After", into: "Into" }[s.op]} ${name}` };
  }

  function wire(S) {
    const fig = S?.fig;
    if (!fig || !/^(mindmap|timeline)$/.test(S.k?.name) || fig.dataset.tree) return;
    fig.dataset.tree = "1";
    diagramModel.seqCanvas.edit(S, (svg) => boxes(svg, S.k, S.m, diagramModel.kinds.ops.key));
  }

  diagramModel.treeCanvas = { wire, parts, order, boxes, spot, node, over };
})();
