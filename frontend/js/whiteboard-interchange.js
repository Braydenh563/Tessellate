// whiteboard-interchange.js: a board in and out as text (2026-10-05, the
// features audit's W5; WHITEBOARD_PLAN Phase E).
//
// The features audit: a board went out only as pictures (PNG, SVG, PDF), and
// nothing came in but pictures and pasted text, where draw.io reads and
// writes Mermaid and keeps its diagram inside the SVG it exports. Three
// pieces, each local and each a pure function the tests run in node:
//
// - **Mermaid out** (`wbBoardToMermaid`): the board's shapes, text boxes and
//   cards that a connector joins, as a `flowchart` with the connector labels.
// - **Mermaid in** (`wbMermaidParse`, `wbMermaidLayout`): the `graph` and
//   `flowchart` subset people write (rectangles, rounded, diamonds, circles;
//   `-->`, `---`, `-.->`, `==>`, labels as `|yes|` or `-- yes -->`; chains
//   and `;`), laid out in rows by depth, placed as shapes and elbow
//   connectors, one undo step.
// - **An outline of a free board** (`wbBoardOutline`): its frames in
//   presentation order, what lies in each in reading order, then the rest;
//   Markdown a document or another app reads.
// - **A re-editable SVG**: the board's rows ride in the exported SVG's
//   `<metadata>` (`wbBoardSvgMetadata`), and importing that SVG puts them
//   back as new rows, connectors rejoined (`wbImportBoardRows`).
//
// Loaded in the Library bundle after whiteboard-format.js (`LAZY_MODULES`).

const WB_MERMAID_SHAPES = {
  rect: ["[", "]"],
  diamond: ["{", "}"],
  circle: ["((", "))"],
};

//: Words safe inside a Mermaid node or edge label: quotes, brackets and the
//: bar would end it early.
function wbMermaidText(text) {
  return String(text || "").replace(/["[\](){}|<>#;]/g, " ").replace(/\s+/g, " ").trim().slice(0, 120) || " ";
}

//: The board as a Mermaid flowchart: every connector whose two ends are a
//: shape, a text box or a card, and the things it joins. Pure: reads `state`.
//: `frameOf(kind, item)` (the board passes one) names the frame an item lies
//: in, `{id, title}` or null: those items are written inside a `subgraph`
//: of the frame's title, so frames go out and come back as frames.
function wbBoardToMermaid(state, cardTitle = (node) => `Note ${node.entry_id}`, frameOf = null) {
  const ids = new Map();
  const loose = [];
  const framed = new Map();
  const edges = [];
  const declare = (kind, item) => {
    const key = `${kind}:${item.id}`;
    if (ids.has(key)) return ids.get(key);
    const id = `n${ids.size + 1}`;
    ids.set(key, id);
    let words = "";
    let shape = "rect";
    if (kind === "node") words = cardTitle(item);
    else if (kind === "object") words = item.data?.content || "";
    else {
      let data = {};
      try {
        data = JSON.parse(item.data) || {};
      } catch {
        data = {};
      }
      words = data.label || "";
      shape = data.shape === "diamond" ? "diamond" : data.shape === "circle" ? "circle" : "rect";
    }
    const [open, close] = WB_MERMAID_SHAPES[shape];
    const frame = frameOf ? frameOf(kind, item) : null;
    let bucket = loose;
    if (frame) {
      if (!framed.has(frame.id)) framed.set(frame.id, { title: frame.title, lines: [] });
      bucket = framed.get(frame.id).lines;
    }
    bucket.push(`${id}${open}"${wbMermaidText(words)}"${close}`);
    return id;
  };
  const find = (kind, id) => (state[{ node: "nodes", object: "objects", sketch: "sketches" }[kind]] || []).find((i) => i.id === id);
  for (const sketch of state.sketches || []) {
    let data = null;
    try {
      data = JSON.parse(sketch.data);
    } catch {
      continue;
    }
    if (!String(data?.type || "").startsWith("link-") || data.sourceId == null || data.targetId == null) continue;
    const sKind = data.sourceKind || "node", tKind = data.targetKind || "node";
    const s = find(sKind, data.sourceId), t = find(tKind, data.targetId);
    if (!s || !t) continue;
    const a = declare(sKind, s), b = declare(tKind, t);
    const arrow = (data.endCap && data.endCap !== "none") || data.endStyle === "end" || data.endStyle === "both" ? "-->" : "---";
    const label = data.label ? `|${wbMermaidText(data.label)}|` : "";
    edges.push(`  ${a} ${arrow}${label} ${b}`);
  }
  const lines = ["flowchart TD"];
  let f = 0;
  for (const { title, lines: inside } of framed.values()) {
    f += 1;
    lines.push(`  subgraph f${f} ["${wbMermaidText(title)}"]`, ...inside.map((l) => `    ${l}`), "  end");
  }
  lines.push(...loose.map((l) => `  ${l}`), ...edges);
  return lines.join("\n") + "\n";
}

//: The `graph`/`flowchart` subset, to `{ dir, nodes: [{id, text, shape,
//: group}], edges: [{from, to, label, arrow}], subgraphs: [{id, title,
//: parent}] }`. A `subgraph` (nested or not, `subgraph id [Title]`,
//: `subgraph id`, or `subgraph Some title`) up to its `end` holds every node
//: first named inside it, and comes in as a frame (wb-phase2 step 2; it was
//: skipped). An edge may name a subgraph: it joins the frame. Unknown lines
//: (style, classDef, click, direction) are skipped and counted, never fatal.
function wbMermaidParse(source) {
  const out = { dir: "TD", nodes: [], edges: [], subgraphs: [], skipped: 0 };
  const byId = new Map();
  const open = [];
  const node = (id, text = null, shape = null) => {
    let n = byId.get(id);
    if (!n) {
      n = { id, text: id, shape: "rect", group: null };
      byId.set(id, n);
      out.nodes.push(n);
    }
    if (n.group == null && open.length) n.group = open[open.length - 1];
    if (text != null) n.text = text;
    if (shape) n.shape = shape;
    return n;
  };
  //: One node reference: an id with an optional shape and text.
  const NODE = /^\s*([A-Za-z0-9_]\w*)\s*(\(\(([^)]*)\)\)|\(\[([^\]]*)\]\)|\[\[([^\]]*)\]\]|\[([^\]]*)\]|\(([^)]*)\)|\{([^}]*)\}|>([^\]]*)\])?/;
  const unquote = (t) => String(t ?? "").trim().replace(/^"(.*)"$/, "$1").trim();
  const takeNode = (text) => {
    const m = NODE.exec(text);
    if (!m) return null;
    let shape = null, words = null;
    if (m[3] != null) [shape, words] = ["circle", m[3]];
    else if (m[4] != null) [shape, words] = ["rect", m[4]];
    else if (m[5] != null) [shape, words] = ["rect", m[5]];
    else if (m[6] != null) [shape, words] = ["rect", m[6]];
    else if (m[7] != null) [shape, words] = ["rect", m[7]];
    else if (m[8] != null) [shape, words] = ["diamond", m[8]];
    else if (m[9] != null) [shape, words] = ["rect", m[9]];
    node(m[1], words == null ? null : unquote(words), shape);
    return { id: m[1], rest: text.slice(m[0].length) };
  };
  //: An edge between two references: the arrow, then an optional label in
  //: bars, or a label written inside the arrow (`-- yes -->`).
  const EDGE = /^\s*(?:(--|==|-\.)\s*([^-=.>|][^>]*?)\s*(-->|==>|\.->|---|-\.-)|(-->|---|==>|-\.->|-\.-|===|--o|--x))\s*(?:\|([^|]*)\|)?/;
  for (const raw of String(source || "").split(/\n|;/)) {
    const line = raw.replace(/%%.*$/, "").trim();
    if (!line) continue;
    const head = /^(graph|flowchart)\s*(TD|TB|BT|LR|RL)?\s*$/i.exec(line);
    if (head) {
      out.dir = (head[2] || "TD").toUpperCase().replace("TB", "TD");
      continue;
    }
    const sub = /^subgraph\s+(.+)$/.exec(line);
    if (sub) {
      const rest = sub[1].trim();
      const named = /^([A-Za-z0-9_][\w-]*)\s*\[\s*(.*?)\s*\]$/.exec(rest);
      const id = named ? named[1] : rest;
      const title = named ? unquote(named[2]) || id : unquote(rest);
      if (!out.subgraphs.some((g) => g.id === id)) out.subgraphs.push({ id, title, parent: open.length ? open[open.length - 1] : null });
      open.push(id);
      continue;
    }
    if (/^end$/.test(line) && open.length) {
      open.pop();
      continue;
    }
    if (/^(style|classDef|class|click|linkStyle|subgraph|end|direction)\b/.test(line)) {
      out.skipped += 1;
      continue;
    }
    let first = takeNode(line);
    if (!first) {
      out.skipped += 1;
      continue;
    }
    let rest = first.rest;
    while (rest.trim()) {
      const e = EDGE.exec(rest);
      if (!e) {
        out.skipped += 1;
        break;
      }
      const arrowText = e[3] || e[4] || "";
      const label = unquote(e[5] ?? e[2] ?? "");
      const next = takeNode(rest.slice(e[0].length));
      if (!next) {
        out.skipped += 1;
        break;
      }
      out.edges.push({ from: first.id, to: next.id, label, arrow: />|o$|x$/.test(arrowText), dashed: /\./.test(arrowText) });
      first = next;
      rest = next.rest;
    }
  }
  //: A subgraph named in an edge is the frame, not a node of its own.
  const groups = new Set(out.subgraphs.map((g) => g.id));
  out.nodes = out.nodes.filter((n) => !groups.has(n.id));
  return out;
}

//: Rows by depth from the nodes nothing points at (a cycle's entry is its
//: first node), in the order met; then each node's centre in board units,
//: top-down or left-right as the source said, the whole centred on 0. A
//: subgraph is laid out the same way inside itself and then takes its place
//: in its parent's rows as one block (its edges to the outside count as the
//: block's), so a frame never covers a node that is not in it. The returned
//: Map carries `frames`: `{id, title, depth, x, y, w, h}`, outermost first.
function wbMermaidLayout(graph, { w = 160, h = 70, gapX = 220, gapY = 140, pad = 30, head = 34 } = {}) {
  const across = graph.dir === "LR" || graph.dir === "RL";
  const flip = graph.dir === "BT" || graph.dir === "RL";
  const subs = graph.subgraphs || [];
  const sub = new Map(subs.map((g) => [g.id, g]));
  const groupOf = new Map();
  for (const n of graph.nodes) groupOf.set(n.id, sub.has(n.group) ? n.group : null);
  for (const g of subs) groupOf.set(g.id, sub.has(g.parent) && g.parent !== g.id ? g.parent : null);
  const order = new Map(graph.nodes.map((n, i) => [n.id, i]));
  const first = (id, seen = new Set()) => {
    if (order.has(id)) return order.get(id);
    if (seen.has(id)) return Infinity;
    seen.add(id);
    let best = Infinity;
    for (const [k, g] of groupOf) if (g === id) best = Math.min(best, first(k, seen));
    order.set(id, best);
    return best;
  };
  //: The unit at level `g` that holds `id`: itself, or its ancestor there.
  const unitAt = (id, g) => {
    let cur = id;
    for (let guard = 0; cur != null && guard < 64; guard += 1) {
      if (groupOf.get(cur) === g && groupOf.has(cur)) return cur;
      cur = groupOf.get(cur);
    }
    return null;
  };
  const sepAlong = across ? gapX - w : gapY - h;
  const sepCross = across ? gapY - h : gapX - w;
  const block = (g, depth) => {
    const units = [...groupOf.keys()].filter((id) => groupOf.get(id) === g).sort((a, b) => first(a) - first(b));
    const size = new Map(), inner = new Map();
    for (const u of units) {
      if (sub.has(u)) {
        const b = block(u, depth + 1);
        inner.set(u, b);
        size.set(u, { w: Math.max(b.w, w) + pad * 2, h: Math.max(b.h, 0) + pad * 2 + head });
      } else {
        size.set(u, { w, h: graph.nodes.find((n) => n.id === u)?.h || h });
      }
    }
    const incoming = new Map(units.map((u) => [u, 0]));
    const out = new Map(units.map((u) => [u, []]));
    for (const e of graph.edges) {
      const a = unitAt(e.from, g), b = unitAt(e.to, g);
      if (a == null || b == null || a === b || !incoming.has(a) || !incoming.has(b)) continue;
      incoming.set(b, incoming.get(b) + 1);
      out.get(a).push(b);
    }
    const level = new Map();
    const queue = units.filter((u) => !incoming.get(u));
    if (!queue.length && units.length) queue.push(units[0]);
    for (const u of queue) level.set(u, 0);
    while (queue.length) {
      const u = queue.shift();
      for (const next of out.get(u) || []) {
        if (level.has(next)) continue;
        level.set(next, level.get(u) + 1);
        queue.push(next);
      }
    }
    for (const u of units) if (!level.has(u)) level.set(u, 0);
    const rows = new Map();
    for (const u of units) {
      if (!rows.has(level.get(u))) rows.set(level.get(u), []);
      rows.get(level.get(u)).push(u);
    }
    const rowList = [...rows.keys()].sort((a, b) => a - b).map((k) => rows.get(k));
    if (flip) rowList.reverse();
    const along = (u) => (across ? size.get(u).w : size.get(u).h);
    const cross = (u) => (across ? size.get(u).h : size.get(u).w);
    const extent = (row) => row.reduce((t, u) => t + cross(u), 0) + sepCross * (row.length - 1);
    const crossMax = Math.max(0, ...rowList.map(extent));
    const centres = new Map();
    let a = 0;
    for (const row of rowList) {
      const thick = Math.max(...row.map(along));
      let c = (crossMax - extent(row)) / 2;
      for (const u of row) {
        const ca = a + thick / 2, cc = c + cross(u) / 2;
        centres.set(u, across ? { x: ca, y: cc } : { x: cc, y: ca });
        c += cross(u) + sepCross;
      }
      a += thick + sepAlong;
    }
    const total = Math.max(0, a - sepAlong);
    const res = { w: across ? total : crossMax, h: across ? crossMax : total, at: new Map(), frames: [] };
    for (const u of units) {
      const c = centres.get(u);
      if (!sub.has(u)) {
        res.at.set(u, c);
        continue;
      }
      const sz = size.get(u), b = inner.get(u);
      const fx = c.x - sz.w / 2, fy = c.y - sz.h / 2;
      res.frames.push({ id: u, title: sub.get(u).title, depth, x: fx, y: fy, w: sz.w, h: sz.h });
      const ox = fx + pad + (sz.w - pad * 2 - b.w) / 2, oy = fy + pad + head;
      for (const [id, p] of b.at) res.at.set(id, { x: p.x + ox, y: p.y + oy });
      for (const f of b.frames) res.frames.push({ ...f, x: f.x + ox, y: f.y + oy });
    }
    return res;
  };
  const top = block(null, 0);
  const at = new Map();
  for (const n of graph.nodes) {
    const p = top.at.get(n.id) || { x: 0, y: 0 };
    at.set(n.id, { x: p.x - top.w / 2, y: p.y - top.h / 2 });
  }
  at.frames = top.frames.map((f) => ({ ...f, x: f.x - top.w / 2, y: f.y - top.h / 2 })).sort((p, q) => p.depth - q.depth);
  return at;
}

//: A free board as Markdown: each frame (in presentation order) as a
//: heading over what lies in it in reading order, then what lies in none.
function wbBoardOutline(state, { frames, title = "Board", cardTitle = (node) => `Note ${node.entry_id}` } = {}) {
  const items = [];
  for (const node of state.nodes || []) items.push({ x: node.x || 0, y: node.y || 0, words: cardTitle(node) });
  for (const obj of state.objects || []) {
    if (obj.kind === "text" && obj.data?.content) items.push({ x: obj.x || 0, y: obj.y || 0, words: obj.data.content });
  }
  for (const sketch of state.sketches || []) {
    let data = null;
    try {
      data = JSON.parse(sketch.data);
    } catch {
      continue;
    }
    if (!data?.label || typeof data.d !== "string") continue;
    const nums = (data.d.match(/-?\d*\.?\d+/g) || []).map(Number);
    const xs = nums.filter((_, i) => i % 2 === 0), ys = nums.filter((_, i) => i % 2 === 1);
    items.push({ x: Math.min(...xs), y: Math.min(...ys), words: data.label });
  }
  const inside = (item, f) => item.x >= f.x && item.x <= f.x + (f.width || 0) && item.y >= f.y && item.y <= f.y + (f.height || 0);
  const reading = (a, b) => a.y - b.y || a.x - b.x;
  const lines = [`# ${title}`, ""];
  const used = new Set();
  for (const f of frames || []) {
    lines.push(`## ${String(f.data?.content || "").trim() || "Frame"}`, "");
    const mine = items.filter((it) => !used.has(it) && inside(it, f)).sort(reading);
    for (const it of mine) {
      used.add(it);
      lines.push(`- ${String(it.words).replace(/\s*\n\s*/g, " ").trim()}`);
    }
    if (!mine.length) lines.push("(empty)");
    lines.push("");
  }
  const rest = items.filter((it) => !used.has(it)).sort(reading);
  if (rest.length) {
    if (frames?.length) lines.push("## Elsewhere on the board", "");
    for (const it of rest) lines.push(`- ${String(it.words).replace(/\s*\n\s*/g, " ").trim()}`);
    lines.push("");
  }
  return lines.join("\n");
}

//: The rows an exported SVG carries so it can come back in as a board.
function wbBoardSvgMetadata(rows) {
  const body = JSON.stringify({ app: "memorymap-board", v: 1, rows });
  return `<metadata id="memorymap-board">${body.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")}</metadata>`;
}

//: **Which Mermaid diagram a text is** (INBOX 797, canvasdepth): its first
//: line that is not a comment. `null` for a kind the board does not draw
//: (pie, gantt, journey), so the caller can say so rather than guess.
function wbMermaidKind(source) {
  const first = String(source || "").split("\n").map((l) => l.replace(/%%.*$/, "").trim()).find(Boolean) || "";
  if (/^(graph|flowchart)\b/i.test(first)) return "flowchart";
  if (/^stateDiagram(-v2)?\b/.test(first)) return "state";
  if (/^classDiagram(-v2)?\b/.test(first)) return "class";
  if (/^sequenceDiagram\b/.test(first)) return "sequence";
  return null;
}

//: A Mermaid line with its comment off, or "" for none.
function wbMermaidLines(source) {
  return String(source || "").split("\n").map((raw) => raw.replace(/%%.*$/, "").trim());
}

//: `stateDiagram` to the flowchart's graph shape, so the same layout and the
//: same placing draw it: `[*]` is a start dot where it begins a transition
//: and an end dot where it ends one, `state "Words" as Id` names a state,
//: `state Id {` up to `}` is a frame, `A --> B : label` a labelled arrow.
//: Notes, `direction`, forks and choices are skipped and counted.
function wbMermaidStateParse(source) {
  const out = { dir: "TD", nodes: [], edges: [], subgraphs: [], skipped: 0 };
  const byId = new Map();
  const open = [];
  const node = (id, text = null, shape = "rounded") => {
    let n = byId.get(id);
    if (!n) {
      n = { id, text: id, shape, group: open.length ? open[open.length - 1] : null };
      byId.set(id, n);
      out.nodes.push(n);
    }
    if (text != null) n.text = text;
    return n;
  };
  const end = (ref, starting) => {
    if (ref !== "[*]") return node(ref).id;
    const id = starting ? "__start" : "__end";
    node(id, "", starting ? "start" : "end");
    return id;
  };
  for (const line of wbMermaidLines(source)) {
    if (!line || /^stateDiagram/.test(line)) continue;
    const named = /^state\s+"([^"]*)"\s+as\s+([\w-]+)$/.exec(line);
    if (named) {
      node(named[2], named[1]);
      continue;
    }
    const block = /^state\s+([\w-]+)\s*\{$/.exec(line);
    if (block) {
      if (!out.subgraphs.some((g) => g.id === block[1])) out.subgraphs.push({ id: block[1], title: block[1], parent: open.length ? open[open.length - 1] : null });
      open.push(block[1]);
      continue;
    }
    if (line === "}" && open.length) {
      open.pop();
      continue;
    }
    const edge = /^(\[\*\]|[\w-]+)\s*-->\s*(\[\*\]|[\w-]+)\s*(?::\s*(.*))?$/.exec(line);
    if (edge) {
      out.edges.push({ from: end(edge[1], true), to: end(edge[2], false), label: (edge[3] || "").trim(), arrow: true, dashed: false });
      continue;
    }
    const described = /^([\w-]+)\s*:\s*(.+)$/.exec(line);
    if (described && !/^(note|direction)$/.test(described[1])) {
      node(described[1], described[2].trim());
      continue;
    }
    out.skipped += 1;
  }
  const groups = new Set(out.subgraphs.map((g) => g.id));
  out.nodes = out.nodes.filter((n) => !groups.has(n.id));
  return out;
}

//: A class relation's two ends: the mark on each side of the line, then
//: the line (`--` solid, `..` dashed). `<|` and `|>` are inheritance and
//: realisation (a triangle), `*` composition (a filled diamond), `o`
//: aggregation (a diamond), `<` and `>` an arrow.
const WB_MERMAID_CLASS_MARKS = { "<|": "triangle", "|>": "triangle", "*": "diamond-filled", o: "diamond", "<": "arrow", ">": "arrow" };

//: `classDiagram` to the graph shape: each class a box whose text is its
//: name over its members (from `class X { ... }` or `X : member`), each
//: relation a line with its marks as caps and its label from `: words` or a
//: quoted multiplicity. Annotations, notes, `classDef` and styles are
//: skipped and counted.
function wbMermaidClassParse(source) {
  const out = { dir: "TD", nodes: [], edges: [], subgraphs: [], skipped: 0 };
  const byId = new Map();
  const members = new Map();
  const node = (id) => {
    let n = byId.get(id);
    if (!n) {
      n = { id, text: id, shape: "rect", group: null };
      byId.set(id, n);
      out.nodes.push(n);
      members.set(id, []);
    }
    return n;
  };
  const REL = /^([\w-]+)\s*(?:"([^"]*)")?\s*(<\||\*|o|<)?(--|\.\.)(\|>|\*|o|>)?\s*(?:"([^"]*)")?\s*([\w-]+)\s*(?::\s*(.*))?$/;
  let inside = null;
  for (const line of wbMermaidLines(source)) {
    if (!line || /^classDiagram/.test(line)) continue;
    if (inside) {
      if (line === "}") inside = null;
      else if (!/^<<.*>>$/.test(line)) members.get(inside).push(line);
      continue;
    }
    const cls = /^class\s+([\w-]+)(?:~[^~]*~)?\s*(\{)?\s*(\})?$/.exec(line);
    if (cls) {
      node(cls[1]);
      if (cls[2] && !cls[3]) inside = cls[1];
      continue;
    }
    const rel = REL.exec(line);
    if (rel) {
      node(rel[1]);
      node(rel[7]);
      const startCap = WB_MERMAID_CLASS_MARKS[rel[3]] || null, endCap = WB_MERMAID_CLASS_MARKS[rel[5]] || null;
      const label = [rel[8], rel[2], rel[6]].map((t) => (t || "").trim()).find(Boolean) || "";
      out.edges.push({ from: rel[1], to: rel[7], label, arrow: Boolean(endCap), startCap, endCap, dashed: rel[4] === ".." });
      continue;
    }
    const member = /^([\w-]+)\s*:\s*(.+)$/.exec(line);
    if (member) {
      node(member[1]);
      members.get(member[1]).push(member[2].trim());
      continue;
    }
    out.skipped += 1;
  }
  for (const n of out.nodes) {
    const list = members.get(n.id) || [];
    if (list.length) n.text = [n.id, ...list].join("\n");
    n.h = 50 + 20 * list.length;
  }
  return out;
}

//: `sequenceDiagram` to `{participants: [{id, text, actor}], steps}`: a step
//: is a message (`A->>B: words`; `-->>`, `--)` and `--x` dashed), a note
//: (`Note over A,B: words`, `left of`, `right of`) or a block's opening
//: line (`loop`, `alt`, `opt`, `par`, `critical`, `break`, `rect`) drawn as
//: a label across the lifelines. `end`, `activate` and `else` lines are
//: kept quiet; other lines are skipped and counted.
function wbMermaidSequenceParse(source) {
  const out = { participants: [], steps: [], skipped: 0 };
  const byId = new Map();
  const who = (id, text = null, actor = false) => {
    let p = byId.get(id);
    if (!p) {
      p = { id, text: id, actor };
      byId.set(id, p);
      out.participants.push(p);
    }
    if (text != null) p.text = text;
    if (actor) p.actor = true;
    return p;
  };
  const MSG = /^(\w+)\s*(-->>|->>|-->|->|--x|-x|--\)|-\))\s*[+-]?\s*(\w+)\s*:\s*(.*)$/;
  for (const line of wbMermaidLines(source)) {
    if (!line || /^sequenceDiagram/.test(line)) continue;
    const decl = /^(participant|actor)\s+([\w-]+)(?:\s+as\s+(.+))?$/.exec(line);
    if (decl) {
      who(decl[2], decl[3] ? decl[3].trim() : null, decl[1] === "actor");
      continue;
    }
    const msg = MSG.exec(line);
    if (msg) {
      who(msg[1]);
      who(msg[3]);
      out.steps.push({ kind: "message", from: msg[1], to: msg[3], text: msg[4].trim(), dashed: msg[2].startsWith("--") });
      continue;
    }
    const note = /^note\s+(over|left of|right of)\s+([\w-]+(?:\s*,\s*[\w-]+)?)\s*:\s*(.*)$/i.exec(line);
    if (note) {
      const over = note[2].split(",").map((s) => s.trim());
      over.forEach((id) => who(id));
      out.steps.push({ kind: "note", over, side: note[1].toLowerCase(), text: note[3].trim() });
      continue;
    }
    if (/^(loop|alt|opt|par|critical|break|rect)\b/.test(line)) {
      out.steps.push({ kind: "block", text: line });
      continue;
    }
    if (/^(end|else|and|option|activate|deactivate)\b/.test(line)) continue;
    out.skipped += 1;
  }
  return out;
}

//: **A `.drawio` file, cell by cell** (INBOX 797, canvasdepth; the draw.io
//: programme's decision 3 maps each style key to the board's own). A style
//: string `ellipse;fillColor=#dae8fc;` as keys, its bare first word (the
//: shape: ellipse, rhombus, text, swimlane) as `_kind`.
function wbDrawioStyle(style) {
  const out = {};
  for (const part of String(style || "").split(";")) {
    if (!part) continue;
    const eq = part.indexOf("=");
    if (eq < 0) {
      if (!out._kind) out._kind = part.trim();
      out[part.trim()] = "1";
    } else {
      out[part.slice(0, eq).trim()] = part.slice(eq + 1).trim();
    }
  }
  return out;
}

//: A label as plain text: draw.io keeps HTML in `value` when `html=1`. Read
//: with string rules, not a parser, so nothing in a file can run. A cell
//: whose style says `html=0` holds plain text (this app's own export writes
//: it so), kept as it stands.
function wbDrawioText(value, html = true) {
  if (!html) return String(value || "").trim();
  const named = { amp: "&", lt: "<", gt: ">", quot: '"', apos: "'", nbsp: " " };
  return String(value || "")
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(/<\/(div|p|li)>/gi, "\n")
    .replace(/<[^>]*>/g, "")
    .replace(/&(#x?[0-9a-f]+|[a-z]+);/gi, (m, code) => {
      if (code[0] !== "#") return named[code.toLowerCase()] ?? m;
      const n = code[1] === "x" || code[1] === "X" ? parseInt(code.slice(2), 16) : parseInt(code.slice(1), 10);
      return Number.isFinite(n) && n > 0 && n < 0x110000 ? String.fromCodePoint(n) : m;
    })
    .split("\n").map((l) => l.trim()).filter((l, i, all) => l || (i > 0 && i < all.length - 1)).join("\n").trim();
}

//: draw.io's ends to the board's (decision 3's caps row).
const WB_DRAWIO_CAPS = { classic: "arrow", block: "arrow", open: "arrow", openThin: "arrow", classicThin: "arrow", blockThin: "arrow", oval: "circle", ERone: "er-one-only", ERmandOne: "er-one", ERmany: "er-many", ERoneToMany: "er-one-many", ERzeroToOne: "er-zero-one", ERzeroToMany: "er-zero-many", cross: "cross", openAsync: "half-arrow", async: "half-arrow", doubleBlock: "double-arrow" };
//: Style keys with no counterpart here, counted in the import's report.
const WB_DRAWIO_DROPPED = ["sketch", "glass", "comic", "shadow", "rotation", "image", "gradientColor"];

//: A vertex's look in the board's keys: stroke, fill, width (draw.io 1 is
//: the board's 2), dash, label colour, size and weight.
function wbDrawioLook(s) {
  const hex = (v) => (/^#[0-9a-f]{6}$/i.test(v || "") ? v.toLowerCase() : null);
  const look = {};
  if (s.strokeColor === "none") look.noStroke = true;
  else if (hex(s.strokeColor)) look.color = hex(s.strokeColor);
  if (hex(s.fillColor)) Object.assign(look, { fill: hex(s.fillColor), fillOpacity: 1 });
  if (hex(s.fontColor)) look.label_color = hex(s.fontColor);
  if (Number(s.fontStyle) & 1) look.label_bold = true;
  if (Number(s.fontStyle) & 2) look.label_italic = true;
  if (Number(s.fontSize) > 0) look.label_size = Math.round(Number(s.fontSize));
  look.width = Math.max(1, Math.round((Number(s.strokeWidth) || 1) * 2));
  if (s.dashed === "1") look.dash = "dashed";
  return look;
}

//: What a vertex is drawn as, from its style: the kinds the board has a
//: path for, else a box (counted when its shape was something else).
function wbDrawioShape(s) {
  const kind = s.shape || s._kind || "";
  if (kind === "ellipse" || s.ellipse === "1") return "ellipse";
  if (kind === "rhombus") return "diamond";
  if (kind === "triangle") return "triangle";
  if (kind === "hexagon") return "hexagon";
  if (kind === "parallelogram") return "parallelogram";
  if (s.rounded === "1") return "rounded";
  return "rect";
}

//: The cells of one page (`{id, parent, vertex, edge, source, target, style,
//: value, geo: {x, y, width, height, relative}, sourcePoint, targetPoint,
//: points}`) to what the board makes: `items` (shape, text, frame) with
//: absolute boxes, `links` between item ids or free points, and `dropped`
//: (style keys with no counterpart, and shapes drawn as a box).
function wbDrawioPlan(cells) {
  const byId = new Map(cells.map((c) => [c.id, c]));
  const roots = new Set(cells.filter((c) => !c.parent || !byId.has(c.parent) || !byId.get(c.parent).parent).map((c) => c.id));
  const dropped = {};
  const drop = (k) => { dropped[k] = (dropped[k] || 0) + 1; };
  const origin = (id, guard = 0) => {
    const c = byId.get(id);
    if (!c || roots.has(id) || !c.vertex || guard > 32) return { x: 0, y: 0 };
    const up = origin(c.parent, guard + 1);
    return { x: up.x + (Number(c.geo?.x) || 0), y: up.y + (Number(c.geo?.y) || 0) };
  };
  const items = [], links = [], edgeLabels = new Map();
  for (const c of cells) {
    if (!c.vertex || roots.has(c.id)) continue;
    const s = wbDrawioStyle(c.style);
    const parent = byId.get(c.parent);
    if (parent?.edge) {
      edgeLabels.set(parent.id, wbDrawioText(c.value, s.html !== "0"));
      continue;
    }
    for (const k of WB_DRAWIO_DROPPED) if (s[k] && s[k] !== "0") drop(k);
    if (s._kind === "group") continue;
    const at = origin(c.id);
    const box = { x: at.x, y: at.y, w: Math.max(1, Number(c.geo?.width) || 0), h: Math.max(1, Number(c.geo?.height) || 0) };
    const label = wbDrawioText(c.value, s.html !== "0");
    if (s._kind === "swimlane" || s.swimlane === "1") items.push({ id: c.id, kind: "frame", ...box, label });
    else if (s._kind === "text") items.push({ id: c.id, kind: "text", ...box, label, look: { font_size: Math.round(Number(s.fontSize) || 16), ...(wbDrawioLook(s).label_color ? { color: wbDrawioLook(s).label_color } : {}) } });
    else {
      const shape = wbDrawioShape(s);
      if (shape === "rect" && (s.shape || (s._kind && !["rounded", "whiteSpace", "html"].includes(s._kind)))) drop(`shape ${s.shape || s._kind}`);
      items.push({ id: c.id, kind: "shape", ...box, shape, label, look: wbDrawioLook(s) });
    }
  }
  for (const c of cells) {
    if (!c.edge) continue;
    const s = wbDrawioStyle(c.style);
    const data = { width: Math.max(1, Math.round((Number(s.strokeWidth) || 1) * 2)) };
    if (/^#[0-9a-f]{6}$/i.test(s.strokeColor || "")) data.color = s.strokeColor.toLowerCase();
    if (s.edgeStyle === "orthogonalEdgeStyle" || s.edgeStyle === "elbowEdgeStyle") data.route = "elbow";
    if (s.edgeStyle === "entityRelationEdgeStyle") data.route = "elbow";
    const end = s.endArrow ?? "classic";
    if (end !== "none" && end !== "") data.endCap = WB_DRAWIO_CAPS[end] || "arrow";
    if (s.startArrow && s.startArrow !== "none") data.startCap = WB_DRAWIO_CAPS[s.startArrow] || "arrow";
    if (s.dashed === "1") data.dash = "dashed";
    const label = wbDrawioText(c.value, s.html !== "0") || edgeLabels.get(c.id) || "";
    if (label) data.label = label;
    const source = byId.get(c.source)?.vertex ? c.source : null, target = byId.get(c.target)?.vertex ? c.target : null;
    if (!source && c.sourcePoint) data.sourcePoint = { x: Number(c.sourcePoint.x) || 0, y: Number(c.sourcePoint.y) || 0 };
    if (!target && c.targetPoint) data.targetPoint = { x: Number(c.targetPoint.x) || 0, y: Number(c.targetPoint.y) || 0 };
    if ((!source && !data.sourcePoint) || (!target && !data.targetPoint)) {
      drop("loose connector");
      continue;
    }
    if (Array.isArray(c.points) && c.points.length && data.route !== "elbow") data.points = c.points.map((p) => ({ x: Number(p.x) || 0, y: Number(p.y) || 0 }));
    links.push({ id: c.id, type: s.curved === "1" ? "link-curved" : "link-straight", source, target, data });
  }
  return { items, links, dropped };
}

//: The board's end marks to draw.io's (the import's table, turned round).
const WB_DRAWIO_CAPS_OUT = { arrow: "classic", circle: "oval", "er-one-only": "ERone", "er-one": "ERmandOne", "er-many": "ERmany", "er-one-many": "ERoneToMany", "er-zero-one": "ERzeroToOne", "er-zero-many": "ERzeroToMany", cross: "cross", "half-arrow": "openAsync", "double-arrow": "doubleBlock" };
const WB_DRAWIO_SHAPES_OUT = { circle: "ellipse", diamond: "rhombus", triangle: "triangle", rect: "rounded=0" };

//: **A board as a `.drawio` file** (OPEN 807: the import had no way back).
//: Frames are swimlanes, text boxes and stickies are text or filled boxes,
//: closed shapes are vertices in their own shape, and connectors are edges
//: joined to the cells that took their ends. What a draw.io page has no
//: counterpart for (pictures, tables, cards, drawn lines) is counted in
//: `skipped` and named to the person, never dropped silently. One uncompressed
//: page, so any text editor can read it. `box(kind, item)` is a shape's
//: bounds (the board's `wbItemBBox` in the page); `hidden(kind, item)`
//: leaves out what the layers panel hides.
function wbBoardToDrawio(state, { title = "Board", box = null, hidden = null } = {}) {
  const bounds = box || (() => null);
  const esc = (v) => String(v ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/\r?\n/g, "&#xa;");
  const hex = (v) => (/^#[0-9a-f]{6}$/i.test(v || "") ? v.toLowerCase() : null);
  const skipped = {};
  const skip = (what) => { skipped[what] = (skipped[what] || 0) + 1; };
  const ids = new Map();
  const cells = [];
  let n = 1;
  const geo = (b) => `<mxGeometry x="${Math.round(b.x)}" y="${Math.round(b.y)}" width="${Math.max(1, Math.round(b.w))}" height="${Math.max(1, Math.round(b.h))}" as="geometry"/>`;
  const vertex = (key, style, value, b) => {
    const id = `c${++n}`;
    ids.set(key, id);
    cells.push(`<mxCell id="${id}" value="${esc(value)}" style="${style}" vertex="1" parent="1">${geo(b)}</mxCell>`);
  };
  const font = (size, bold, italic, underline, ink) => {
    const bits = (bold ? 1 : 0) | (italic ? 2 : 0) | (underline ? 4 : 0);
    return `${Number(size) > 0 ? `fontSize=${Math.round(size)};` : ""}${bits ? `fontStyle=${bits};` : ""}${hex(ink) ? `fontColor=${hex(ink)};` : ""}`;
  };
  const objects = [...(state.objects || [])].filter((o) => !(hidden && hidden("object", o)));
  //: Frames first, so they sit behind what is on them, then by stacking order.
  objects.sort((a, b) => (b.kind === "frame") - (a.kind === "frame") || (a.z || 0) - (b.z || 0));
  for (const o of objects) {
    const d = o.data || {};
    const b = { x: o.x || 0, y: o.y || 0, w: o.width || 160, h: o.height || 60 };
    if (o.kind === "frame") vertex(`object:${o.id}`, "swimlane;startSize=30;html=0;whiteSpace=wrap;", d.content || "Frame", b);
    else if (o.kind === "text") {
      const filled = hex(d.bg) || hex(d.border_color);
      const look = font(d.font_size, d.bold, d.italic, d.underline, d.color);
      if (filled) vertex(`object:${o.id}`, `rounded=0;whiteSpace=wrap;html=0;${hex(d.bg) ? `fillColor=${hex(d.bg)};` : ""}${hex(d.border_color) ? `strokeColor=${hex(d.border_color)};` : ""}${look}`, d.content || "", b);
      else vertex(`object:${o.id}`, `text;whiteSpace=wrap;html=0;align=left;verticalAlign=top;${look}`, d.content || "", b);
    } else if (o.kind === "image" || o.kind === "table") skip(o.kind === "image" ? "pictures" : "tables");
    else skip("other items");
  }
  if ((state.nodes || []).length) skipped.cards = state.nodes.length;
  const links = [];
  for (const sk of state.sketches || []) {
    if (hidden && hidden("sketch", sk)) continue;
    let d = null;
    try { d = JSON.parse(sk.data); } catch { continue; }
    if (!d) continue;
    if (String(d.type || "").startsWith("link-")) { links.push([sk, d]); continue; }
    const closed = typeof d.d === "string" && /[Zz]\s*$/.test(d.d.trim());
    if (typeof d.d !== "string" || !(WB_DRAWIO_SHAPES_OUT[d.shape] || d.shape === "custom" || closed)) { skip("drawn lines"); continue; }
    const bb = bounds("sketch", sk);
    if (!bb) { skip("drawn lines"); continue; }
    if (d.shape === "custom" || (!WB_DRAWIO_SHAPES_OUT[d.shape] && closed)) skip("shapes drawn as boxes");
    const shape = WB_DRAWIO_SHAPES_OUT[d.shape] || "rounded=0";
    const width = Math.max(1, Math.round((Number(d.width) || 2) / 2));
    vertex(`sketch:${sk.id}`,
      `${shape};whiteSpace=wrap;html=0;${hex(d.color) ? `strokeColor=${hex(d.color)};` : ""}${hex(d.fill) ? `fillColor=${hex(d.fill)};` : "fillColor=none;"}strokeWidth=${width};${d.dash === "dashed" || d.dash === "dotted" ? "dashed=1;" : ""}${font(d.label_size, d.label_bold, d.label_italic, d.label_underline, d.label_color)}`,
      d.label || "", { x: bb.minX, y: bb.minY, w: bb.maxX - bb.minX, h: bb.maxY - bb.minY });
  }
  for (const [sk, d] of links) {
    const ref = (side) => {
      const id = ids.get(`${d[`${side}Kind`] || "node"}:${d[`${side}Id`]}`);
      return id ? ` ${side}="${id}"` : "";
    };
    const point = (side) => {
      const p = d[`${side}Point`];
      return p && !ref(side) ? `<mxPoint x="${Math.round(p.x)}" y="${Math.round(p.y)}" as="${side}Point"/>` : "";
    };
    const joined = (side) => ref(side) || d[`${side}Point`];
    if (!joined("source") || !joined("target")) { skip("loose connectors"); continue; }
    const capOf = (cap, flag) => (cap && cap !== "none" ? WB_DRAWIO_CAPS_OUT[cap] || "classic" : flag ? "classic" : "none");
    const end = capOf(d.endCap, d.endStyle === "end" || d.endStyle === "both");
    const start = capOf(d.startCap, d.endStyle === "both");
    const way = Array.isArray(d.points) && d.route !== "elbow" ? `<Array as="points">${d.points.map((p) => `<mxPoint x="${Math.round(p.x)}" y="${Math.round(p.y)}"/>`).join("")}</Array>` : "";
    const style = `${d.route === "elbow" ? "edgeStyle=orthogonalEdgeStyle;" : ""}${d.type === "link-curved" ? "curved=1;" : ""}html=0;endArrow=${end};startArrow=${start};` +
      `${hex(d.color) ? `strokeColor=${hex(d.color)};` : ""}strokeWidth=${Math.max(1, Math.round((Number(d.width) || 2) / 2))};${d.dash === "dashed" || d.dash === "dotted" ? "dashed=1;" : ""}`;
    cells.push(`<mxCell id="c${++n}" value="${esc(d.label || "")}" style="${style}" edge="1" parent="1"${ref("source")}${ref("target")}>` +
      `<mxGeometry relative="1" as="geometry">${point("source")}${point("target")}${way}</mxGeometry></mxCell>`);
  }
  const shapes = cells.filter((c) => c.includes('vertex="1"')).length;
  const xml = '<?xml version="1.0" encoding="UTF-8"?>\n<mxfile host="Tessellate">' +
    `<diagram name="${esc(String(title).slice(0, 120))}" id="page1"><mxGraphModel grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="0" math="0" shadow="0">` +
    `<root><mxCell id="0"/><mxCell id="1" parent="0"/>${cells.join("")}</root></mxGraphModel></diagram></mxfile>\n`;
  return { xml, shapes, links: cells.length - shapes, skipped };
}

//: A box's outline as a path the board draws (M, L, C and Z only, so the
//: ports and the hit test read it).
function wbDrawioPath(shape, x, y, w, h) {
  const k = 0.5523;
  const rx = w / 2, ry = h / 2, cx = x + rx, cy = y + ry;
  if (shape === "ellipse") return `M ${cx} ${y} C ${cx + rx * k} ${y} ${x + w} ${cy - ry * k} ${x + w} ${cy} C ${x + w} ${cy + ry * k} ${cx + rx * k} ${y + h} ${cx} ${y + h} C ${cx - rx * k} ${y + h} ${x} ${cy + ry * k} ${x} ${cy} C ${x} ${cy - ry * k} ${cx - rx * k} ${y} ${cx} ${y} Z`;
  if (shape === "diamond") return `M ${cx} ${y} L ${x + w} ${cy} L ${cx} ${y + h} L ${x} ${cy} Z`;
  if (shape === "triangle") return `M ${x} ${y} L ${x + w} ${cy} L ${x} ${y + h} Z`;
  if (shape === "hexagon") return `M ${x + w / 4} ${y} L ${x + (w * 3) / 4} ${y} L ${x + w} ${cy} L ${x + (w * 3) / 4} ${y + h} L ${x + w / 4} ${y + h} L ${x} ${cy} Z`;
  if (shape === "parallelogram") return `M ${x + w / 5} ${y} L ${x + w} ${y} L ${x + (w * 4) / 5} ${y + h} L ${x} ${y + h} Z`;
  if (shape === "rounded") {
    const r = Math.min(10, w / 4, h / 4);
    return `M ${x + r} ${y} L ${x + w - r} ${y} C ${x + w} ${y} ${x + w} ${y} ${x + w} ${y + r} L ${x + w} ${y + h - r} C ${x + w} ${y + h} ${x + w} ${y + h} ${x + w - r} ${y + h} L ${x + r} ${y + h} C ${x} ${y + h} ${x} ${y + h} ${x} ${y + h - r} L ${x} ${y + r} C ${x} ${y} ${x} ${y} ${x + r} ${y} Z`;
  }
  return `M ${x} ${y} L ${x + w} ${y} L ${x + w} ${y + h} L ${x} ${y + h} Z`;
}

//: The rows inside an SVG that carries them, or null.
function wbBoardRowsFromSvg(text) {
  //: Read with a pattern, not a DOMParser: parsing the picture in this
  //: document applies its `style` attributes against the app's CSP, which
  //: refuses each one with a console error (measured: six on one import).
  try {
    const m = /<metadata id="memorymap-board">([\s\S]*?)<\/metadata>/.exec(String(text || ""));
    const body = m ? m[1].replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&amp;/g, "&") : null;
    const parsed = body ? JSON.parse(body) : null;
    return parsed?.app === "memorymap-board" && Array.isArray(parsed.rows) ? parsed.rows : null;
  } catch {
    return null;
  }
}

//: The rows of what an export covers, links included, with their old ids so
//: an import can rejoin them.
function wbExportRows(scope) {
  const onlyKeys = scope === "selection" ? wbSelectedKeys() : null;
  const rows = [];
  for (const kind of ["object", "sketch"]) {
    for (const item of wbState[WB_LIST_BY_KIND[kind]] || []) {
      if (wbItemHidden(kind, item)) continue;
      if (kind === "object" && WB_MAP_KINDS.has(item.kind)) continue;
      let link = null;
      if (kind === "sketch") {
        try {
          link = String(JSON.parse(item.data)?.type || "").startsWith("link-") ? JSON.parse(item.data) : null;
        } catch {
          link = null;
        }
      }
      if (onlyKeys && !link && !onlyKeys.has(wbMultiKey(kind, item.id))) continue;
      rows.push({ kind, id: item.id, link: Boolean(link), payload: WB_KIND_INFO[kind].payload(item) });
    }
  }
  if (onlyKeys) {
    const kept = new Set(rows.filter((r) => !r.link).map((r) => `${r.kind}:${r.id}`));
    return rows.filter((r) => {
      if (!r.link) return true;
      const d = JSON.parse(r.payload.data);
      return kept.has(`${d.sourceKind || "node"}:${d.sourceId}`) && kept.has(`${d.targetKind || "node"}:${d.targetId}`);
    });
  }
  return rows;
}

//: Makes `rows` (from an SVG's metadata) on this board, centred at `at`,
//: connectors rejoined to the new ids; one undo step. Cards are left out: a
//: card is a note, and a file cannot carry the note.
async function wbImportBoardRows(rows, at = wbViewCentre()) {
  const shapes = rows.filter((r) => !r.link && (r.kind === "object" || r.kind === "sketch"));
  if (!shapes.length) {
    toast("That file has no shapes or text to bring in.");
    return 0;
  }
  const boxes = shapes.map((r) => (r.kind === "sketch" ? wbPathBBox(wbSketchParsedData({ data: r.payload.data })?.d || "") : { minX: r.payload.x, minY: r.payload.y, maxX: r.payload.x + (r.payload.width || 0), maxY: r.payload.y + (r.payload.height || 0) })).filter(Boolean);
  const minX = Math.min(...boxes.map((b) => b.minX)), minY = Math.min(...boxes.map((b) => b.minY));
  const maxX = Math.max(...boxes.map((b) => b.maxX)), maxY = Math.max(...boxes.map((b) => b.maxY));
  const dx = at[0] - (minX + maxX) / 2, dy = at[1] - (minY + maxY) / 2;
  const remap = new Map();
  let made = 0;
  await wbRecordGesture(async () => {
    for (const row of shapes) {
      const [created] = await wbCreateCopies([{ kind: row.kind, payload: { ...row.payload, group_id: null } }], dx, dy);
      if (!created) continue;
      remap.set(`${row.kind}:${row.id}`, created.id);
      made += 1;
    }
    for (const row of rows.filter((r) => r.link)) {
      const data = JSON.parse(row.payload.data);
      const s = remap.get(`${data.sourceKind || "node"}:${data.sourceId}`), t = remap.get(`${data.targetKind || "node"}:${data.targetId}`);
      if (s == null || t == null) continue;
      data.sourceId = s;
      data.targetId = t;
      if (Array.isArray(data.points)) data.points = data.points.map((p) => ({ x: p.x + dx, y: p.y + dy }));
      const link = await apiJson("/whiteboard/sketches", { method: "POST", body: JSON.stringify({ data: JSON.stringify(data), x: 0, y: 0, z: wbStackNewZ("sketch"), board_id: window.currentBoardId ?? null }) });
      wbState.sketches.push(link);
    }
  });
  renderWhiteboardNow();
  wbAnnounce(`Brought in ${nounCount(made, "item")} from the file.`);
  return made;
}

//: A Mermaid flowchart, state or class diagram onto this board: shapes and
//: elbow connectors laid out by depth, centred in the view, one undo step.
//: A sequence diagram has its own drawing (`wbImportMermaidSequence`).
async function wbImportMermaid(source, at = wbViewCentre()) {
  const kind = wbMermaidKind(source) || "flowchart";
  if (kind === "sequence") return wbImportMermaidSequence(source, at);
  const graph = kind === "state" ? wbMermaidStateParse(source) : kind === "class" ? wbMermaidClassParse(source) : wbMermaidParse(source);
  if (!graph.nodes.length) {
    toast("No diagram found. Start with a line like: flowchart TD, stateDiagram, classDiagram or sequenceDiagram", "info");
    return 0;
  }
  const place = wbMermaidLayout(graph);
  const ink = window.currentStrokeColor && /^#[0-9a-f]{6}$/i.test(window.currentStrokeColor) ? window.currentStrokeColor : "#335599";
  const ids = new Map();
  const frameIds = new Map();
  await wbRecordGesture(async () => {
    //: Innermost first: `wbStackNewZ` puts each new frame under the others,
    //: so the outer frame, made last, is under the inner one.
    for (const f of [...(place.frames || [])].reverse()) {
      const made = await wbCreateObject("frame", { content: f.title || "Frame" }, Math.round(at[0] + f.x), Math.round(at[1] + f.y), Math.round(f.w), Math.round(f.h));
      if (made) frameIds.set(f.id, made.id);
    }
    for (const n of graph.nodes) {
      const c = place.get(n.id);
      const made = await wbMermaidPlaceNode(n, at[0] + c.x, at[1] + c.y, ink);
      wbState.sketches.push(made);
      ids.set(n.id, made.id);
    }
    for (const e of graph.edges) {
      //: An end that names a subgraph joins its frame.
      const s = ids.get(e.from) ?? frameIds.get(e.from), t = ids.get(e.to) ?? frameIds.get(e.to);
      if (s == null || t == null || (s === t && ids.has(e.from) === ids.has(e.to))) continue;
      const sKind = ids.has(e.from) ? "sketch" : "object", tKind = ids.has(e.to) ? "sketch" : "object";
      const data = { type: "link-straight", route: "elbow", sourceId: s, sourceKind: sKind, targetId: t, targetKind: tKind, color: ink, width: 2 };
      if (e.endCap || e.arrow) data.endCap = wbMermaidCap(e.endCap || "arrow");
      if (e.startCap) data.startCap = wbMermaidCap(e.startCap);
      if (e.dashed) data.dash = "dashed";
      if (e.label) data.label = e.label;
      const link = await apiJson("/whiteboard/sketches", { method: "POST", body: JSON.stringify({ data: JSON.stringify(data), x: 0, y: 0, z: wbStackNewZ("sketch"), board_id: window.currentBoardId ?? null }) });
      wbState.sketches.push(link);
    }
  });
  renderWhiteboardNow();
  const frames = frameIds.size ? ` in ${nounCount(frameIds.size, "frame")}` : "";
  const said = `Brought in ${graph.nodes.length} shapes${frames} and ${graph.edges.length} connectors${graph.skipped ? `; ${nounCount(graph.skipped, "line")} left out` : ""}.`;
  wbAnnounce(said);
  toast(said);
  return graph.nodes.length;
}

//: A cap this board draws: a mark it has no drawing for (a board from
//: before the triangle and diamond ends) falls back to the arrow.
function wbMermaidCap(kind) {
  return typeof WB_CAP_KINDS !== "undefined" && WB_CAP_KINDS.includes(kind) ? kind : "arrow";
}

//: One node as a shape centred on (cx, cy): a diamond, a circle, a rounded
//: box (a state), a start or end dot (a state diagram's `[*]`), or a box as
//: tall as its text (a class with its members).
async function wbMermaidPlaceNode(n, cx, cy, ink) {
  const dot = n.shape === "start" || n.shape === "end";
  const w = dot ? 28 : 160, h = dot ? 28 : n.h || 70;
  const x = cx - w / 2, y = cy - h / 2;
  const r = 14;
  const d = n.shape === "diamond"
    ? `M ${x + w / 2} ${y} L ${x + w} ${y + h / 2} L ${x + w / 2} ${y + h} L ${x} ${y + h / 2} Z`
    : n.shape === "circle" || dot
      ? `M ${x} ${y + h / 2} A ${w / 2} ${h / 2} 0 1 0 ${x + w} ${y + h / 2} A ${w / 2} ${h / 2} 0 1 0 ${x} ${y + h / 2} Z`
      : n.shape === "rounded"
        ? `M ${x + r} ${y} L ${x + w - r} ${y} C ${x + w} ${y} ${x + w} ${y} ${x + w} ${y + r} L ${x + w} ${y + h - r} C ${x + w} ${y + h} ${x + w} ${y + h} ${x + w - r} ${y + h} L ${x + r} ${y + h} C ${x} ${y + h} ${x} ${y + h} ${x} ${y + h - r} L ${x} ${y + r} C ${x} ${y} ${x} ${y} ${x + r} ${y} Z`
        : `M ${x} ${y} L ${x + w} ${y} L ${x + w} ${y + h} L ${x} ${y + h} Z`;
  const data = { d, shape: n.shape === "diamond" ? "diamond" : n.shape === "circle" || dot ? "circle" : n.shape === "rounded" ? "custom" : "rect", color: ink, width: 2 };
  if (n.text) data.label = n.text;
  if (dot) Object.assign(data, { fill: ink, fillOpacity: 1 });
  if (n.shape === "end") data.width = 4;
  return apiJson("/whiteboard/sketches", {
    method: "POST",
    body: JSON.stringify({ data: JSON.stringify(data), x: 0, y: 0, z: wbStackNewZ("sketch"), board_id: window.currentBoardId ?? null }),
  });
}

//: A sequence diagram: each participant a box along the top (an actor's
//: box rounded) over a dashed lifeline, each message a labelled arrow
//: between lifelines one row down from the last (a message to itself a
//: loop out to the right), a note a sticky across the lifelines it is
//: over, a block's opening line a text label. One undo step.
async function wbImportMermaidSequence(source, at = wbViewCentre()) {
  const seq = wbMermaidSequenceParse(source);
  if (!seq.participants.length) {
    toast("No participants found. Start with a line like: sequenceDiagram", "info");
    return 0;
  }
  const ink = window.currentStrokeColor && /^#[0-9a-f]{6}$/i.test(window.currentStrokeColor) ? window.currentStrokeColor : "#335599";
  const gapX = 220, boxW = 160, boxH = 56, row = 64;
  const n = seq.participants.length;
  const left = at[0] - ((n - 1) * gapX) / 2;
  const height = boxH + row * (seq.steps.length + 1);
  const top = at[1] - height / 2;
  const xOf = new Map(seq.participants.map((p, i) => [p.id, left + i * gapX]));
  const post = async (data) => {
    const made = await apiJson("/whiteboard/sketches", { method: "POST", body: JSON.stringify({ data: JSON.stringify(data), x: 0, y: 0, z: wbStackNewZ("sketch"), board_id: window.currentBoardId ?? null }) });
    wbState.sketches.push(made);
    return made;
  };
  let messages = 0;
  await wbRecordGesture(async () => {
    for (const p of seq.participants) {
      const cx = xOf.get(p.id);
      await wbMermaidPlaceNode({ shape: p.actor ? "rounded" : "rect", text: p.text, h: boxH }, cx, top + boxH / 2, ink).then((made) => wbState.sketches.push(made));
      await post({ d: `M ${cx} ${top + boxH} L ${cx} ${top + height}`, shape: "line", color: ink, width: 1.5, dash: "dashed" });
    }
    for (const [i, step] of seq.steps.entries()) {
      const y = top + boxH + row * (i + 1);
      if (step.kind === "message") {
        const x1 = xOf.get(step.from), x2 = xOf.get(step.to);
        const data = { type: "link-straight", color: ink, width: 2, endCap: "arrow", label: step.text };
        if (x1 === x2) Object.assign(data, { sourcePoint: { x: x1, y: y - row / 4 }, targetPoint: { x: x1, y: y + row / 4 }, points: [{ x: x1 + 60, y: y - row / 4 }, { x: x1 + 60, y: y + row / 4 }] });
        else Object.assign(data, { sourcePoint: { x: x1, y }, targetPoint: { x: x2, y } });
        if (step.dashed) data.dash = "dashed";
        await post(data);
        messages += 1;
      } else if (step.kind === "note") {
        const xs = step.over.map((id) => xOf.get(id));
        const minX = Math.min(...xs), maxX = Math.max(...xs);
        const shift = step.side === "left of" ? -boxW / 2 - 10 : step.side === "right of" ? boxW / 2 + 10 : 0;
        const w = Math.max(boxW, maxX - minX + boxW / 2);
        await wbCreateObject("text", { content: step.text, bg: "#fff4a3", border_color: "#e8d56a", color: "#2a2a1f" }, Math.round((minX + maxX) / 2 + shift - w / 2), Math.round(y - row / 2 + 6), Math.round(w), row - 12);
      } else {
        await wbCreateObject("text", { content: step.text }, Math.round(left - boxW / 2), Math.round(y - row / 2 + 8), Math.round((n - 1) * gapX + boxW), row - 16);
      }
    }
  });
  renderWhiteboardNow();
  const said = `Brought in ${nounCount(n, "participant")} and ${nounCount(messages, "message")}${seq.skipped ? `; ${nounCount(seq.skipped, "line")} left out` : ""}.`;
  wbAnnounce(said);
  toast(said);
  return n;
}

function wbCardTitleForExport(node) {
  const entry = (typeof allEntries !== "undefined" ? allEntries : []).find((e) => e.id === node.entry_id);
  return entry ? noteNamePlain(entry.content).slice(0, 80) : `Note ${node.entry_id}`;
}

//: The innermost frame an item lies wholly inside, for the Mermaid export's
//: subgraphs (the same "wholly inside" a frame's drag uses).
function wbMermaidFrameOf(kind, item) {
  const box = wbItemBBox(kind, item);
  if (!box) return null;
  let best = null;
  for (const f of wbState.objects || []) {
    if (f.kind !== "frame" || wbItemHidden("object", f)) continue;
    if (box.minX < f.x || box.minY < f.y || box.maxX > f.x + f.width || box.maxY > f.y + f.height) continue;
    if (!best || f.width * f.height < best.width * best.height) best = f;
  }
  return best ? { id: best.id, title: wbFrameTitle(best) } : null;
}

async function wbExportMermaid() {
  const text = wbBoardToMermaid(wbState, wbCardTitleForExport, wbMermaidFrameOf);
  if (text.trim() === "flowchart TD") {
    toast("Nothing on this board is joined by a connector, so there is no flowchart to write.");
    return;
  }
  await saveFile(wbExportFileName("whole", "mmd"), new Blob([text], { type: "text/plain" }));
  toast("Board exported as a Mermaid flowchart.");
}

async function wbExportDrawio() {
  const made = wbBoardToDrawio(wbState, { title: wbBoardTitleForExport(), box: wbItemBBox, hidden: wbItemHidden });
  if (!made.shapes) {
    toast("Nothing on this board has a draw.io counterpart yet: add shapes, text or frames first.", "info");
    return;
  }
  await saveFile(wbExportFileName("whole", "drawio"), new Blob([made.xml], { type: "application/vnd.jgraph.mxfile" }));
  const left = Object.entries(made.skipped).map(([k, c]) => `${k} ${c}`).join(", ");
  toast(`Board exported for draw.io: ${nounCount(made.shapes, "shape")} and ${nounCount(made.links, "connector")}${left ? `; not kept: ${left}` : ""}.`);
}

async function wbExportOutline() {
  const text = wbBoardOutline(wbState, { frames: wbFramesInOrder(), title: wbBoardTitleForExport(), cardTitle: wbCardTitleForExport });
  await saveFile(wbExportFileName("whole", "md"), new Blob([text], { type: "text/markdown" }));
  toast("Board exported as an outline.");
}

//: The Import dialog: paste a Mermaid flowchart, or choose a .mmd file or a
//: board SVG this app exported.
function wbOpenImportDialog() {
  const dialog = document.getElementById("wb-import-dialog");
  if (!dialog) return;
  const field = document.getElementById("wb-import-text");
  if (field) field.value = "";
  dialog.showModal();
  field?.focus();
}

//: Every page of a `.drawio` file as cells, with its name (canvasdepth2;
//: the first page alone before). A page is either its `mxGraphModel` as XML
//: or, from older draw.io, that XML deflated, base64'd and URI-encoded;
//: `DecompressionStream` undoes it. A `.drawio.svg` carries the file in its
//: root's `content` attribute. `cells` and `pages` stay the first page's
//: and the count, for the callers that read only those.
async function wbDrawioCells(text) {
  const xml = (s) => new DOMParser().parseFromString(s, "text/xml");
  let doc = xml(text);
  const svgContent = doc.documentElement?.localName === "svg" ? doc.documentElement.getAttribute("content") : null;
  if (svgContent) doc = xml(svgContent);
  const diagrams = [...doc.getElementsByTagName("diagram")];
  const modelOf = async (diagram) => {
    const own = diagram ? diagram.getElementsByTagName("mxGraphModel")[0] : doc.getElementsByTagName("mxGraphModel")[0];
    if (own || !diagram) return own || null;
    const packed = diagram.textContent.trim();
    if (!packed) return null;
    const bytes = Uint8Array.from(atob(packed), (ch) => ch.charCodeAt(0));
    const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream("deflate-raw"));
    const inflated = await new Response(stream).text();
    return xml(decodeURIComponent(inflated)).getElementsByTagName("mxGraphModel")[0] || null;
  };
  const all = [];
  for (const [i, diagram] of (diagrams.length ? diagrams : [null]).entries()) {
    const model = await modelOf(diagram);
    if (model) all.push({ name: diagram?.getAttribute("name") || `Page ${i + 1}`, cells: wbDrawioModelCells(model) });
  }
  if (!all.length) return null;
  return { cells: all[0].cells, pages: Math.max(1, diagrams.length), all };
}

function wbDrawioModelCells(model) {
  const point = (el, as) => {
    const p = [...el.children].find((n) => n.localName === "mxPoint" && n.getAttribute("as") === as);
    return p ? { x: Number(p.getAttribute("x")) || 0, y: Number(p.getAttribute("y")) || 0 } : null;
  };
  const cells = [];
  for (const el of model.getElementsByTagName("mxCell")) {
    //: `UserObject` and `object` wrap a cell to carry its label and data.
    const wrap = el.parentElement && /^(UserObject|object)$/.test(el.parentElement.localName) ? el.parentElement : null;
    const geo = [...el.children].find((n) => n.localName === "mxGeometry");
    const points = geo ? [...geo.getElementsByTagName("Array")].filter((a) => a.getAttribute("as") === "points").flatMap((a) => [...a.children].map((q) => ({ x: Number(q.getAttribute("x")) || 0, y: Number(q.getAttribute("y")) || 0 }))) : [];
    cells.push({
      id: (wrap || el).getAttribute("id"), parent: el.getAttribute("parent"), vertex: el.getAttribute("vertex") === "1", edge: el.getAttribute("edge") === "1",
      source: el.getAttribute("source"), target: el.getAttribute("target"), style: el.getAttribute("style") || "",
      value: wrap ? wrap.getAttribute("label") || "" : el.getAttribute("value") || "",
      geo: geo ? { x: geo.getAttribute("x"), y: geo.getAttribute("y"), width: geo.getAttribute("width"), height: geo.getAttribute("height"), relative: geo.getAttribute("relative") === "1" } : {},
      sourcePoint: geo ? point(geo, "sourcePoint") : null, targetPoint: geo ? point(geo, "targetPoint") : null, points,
    });
  }
  return cells;
}

//: A page's box: where its items reach.
function wbDrawioBox(plan) {
  const minX = Math.min(...plan.items.map((i) => i.x)), minY = Math.min(...plan.items.map((i) => i.y));
  const maxX = Math.max(...plan.items.map((i) => i.x + i.w)), maxY = Math.max(...plan.items.map((i) => i.y + i.h));
  return { minX, minY, maxX, maxY, w: maxX - minX, h: maxY - minY };
}

//: One page's items and connectors onto the board, moved by `dx, dy`.
async function wbDrawioPlace(plan, dx, dy, ink) {
  const ids = new Map();
  for (const f of plan.items.filter((i) => i.kind === "frame").reverse()) {
    const made = await wbCreateObject("frame", { content: f.label || "Lane" }, Math.round(f.x + dx), Math.round(f.y + dy), Math.round(f.w), Math.round(f.h));
    if (made) ids.set(f.id, ["object", made.id]);
  }
  for (const item of plan.items.filter((i) => i.kind === "text")) {
    const made = await wbCreateObject("text", { content: item.label, ...item.look }, Math.round(item.x + dx), Math.round(item.y + dy), Math.round(Math.max(40, item.w)), Math.round(Math.max(24, item.h)));
    if (made) ids.set(item.id, ["object", made.id]);
  }
  for (const item of plan.items.filter((i) => i.kind === "shape")) {
    const data = { d: wbDrawioPath(item.shape, item.x + dx, item.y + dy, item.w, item.h), shape: item.shape === "ellipse" ? "circle" : item.shape === "diamond" ? "diamond" : item.shape === "rect" ? "rect" : "custom", color: ink, ...item.look };
    if (item.label) data.label = item.label;
    const made = await apiJson("/whiteboard/sketches", { method: "POST", body: JSON.stringify({ data: JSON.stringify(data), x: 0, y: 0, z: wbStackNewZ("sketch"), board_id: window.currentBoardId ?? null }) });
    wbState.sketches.push(made);
    ids.set(item.id, ["sketch", made.id]);
  }
  for (const link of plan.links) {
    const data = { type: link.type, color: ink, ...link.data };
    const s = link.source ? ids.get(link.source) : null, t = link.target ? ids.get(link.target) : null;
    if (link.source && !s) continue;
    if (link.target && !t) continue;
    if (s) Object.assign(data, { sourceKind: s[0], sourceId: s[1] });
    if (t) Object.assign(data, { targetKind: t[0], targetId: t[1] });
    for (const key of ["sourcePoint", "targetPoint"]) if (data[key]) data[key] = { x: data[key].x + dx, y: data[key].y + dy };
    if (data.points) data.points = data.points.map((p) => ({ x: p.x + dx, y: p.y + dy }));
    const made = await apiJson("/whiteboard/sketches", { method: "POST", body: JSON.stringify({ data: JSON.stringify(data), x: 0, y: 0, z: wbStackNewZ("sketch"), board_id: window.currentBoardId ?? null }) });
    wbState.sketches.push(made);
  }
}

//: Room round a page inside its frame, and between two page frames.
const WB_DRAWIO_PAGE_PAD = 48;
const WB_DRAWIO_PAGE_GAP = 160;

//: A `.drawio` file onto this board, centred in the view, one undo step:
//: swimlanes as frames, text as text boxes, the rest as shapes with their
//: labels, edges as connectors joined to what they join. What has no
//: counterpart is named in the report rather than dropped silently.
//:
//: **Every page comes in, each in a frame named after it, side by side**
//: (canvasdepth2). Frames rather than a board per page because a board's
//: pages are its frames (WHITEBOARD_PLAN decision 22): the Pages tab lists
//: them, Present walks them, and the whole file stays one board and one Undo
//: step. A one-page file comes in as before, with no frame round it.
async function wbImportDrawio(text, at = wbViewCentre()) {
  let read = null;
  try {
    read = await wbDrawioCells(text);
  } catch {
    read = null;
  }
  if (!read) {
    toast("That draw.io file could not be read.", "info");
    return 0;
  }
  const pages = read.all.map((page) => ({ ...page, plan: wbDrawioPlan(page.cells) })).filter((page) => page.plan.items.length);
  if (!pages.length) {
    toast("That draw.io file has no shapes to bring in.", "info");
    return 0;
  }
  const framed = pages.length > 1;
  const pad = framed ? WB_DRAWIO_PAGE_PAD : 0;
  for (const page of pages) page.box = wbDrawioBox(page.plan);
  const rowW = pages.reduce((sum, page) => sum + page.box.w + pad * 2, 0) + WB_DRAWIO_PAGE_GAP * (pages.length - 1);
  const rowH = Math.max(...pages.map((page) => page.box.h + pad * 2));
  const ink = window.currentStrokeColor && /^#[0-9a-f]{6}$/i.test(window.currentStrokeColor) ? window.currentStrokeColor : "#335599";
  let left = at[0] - rowW / 2;
  const top = at[1] - rowH / 2;
  await wbRecordGesture(async () => {
    for (const page of pages) {
      if (framed) {
        await wbCreateObject("frame", { content: page.name.slice(0, 120) }, Math.round(left), Math.round(top),
          Math.round(page.box.w + pad * 2), Math.round(page.box.h + pad * 2));
      }
      await wbDrawioPlace(page.plan, left + pad - page.box.minX, top + pad - page.box.minY, ink);
      left += page.box.w + pad * 2 + WB_DRAWIO_PAGE_GAP;
    }
  });
  renderWhiteboardNow();
  const items = pages.reduce((n, page) => n + page.plan.items.length, 0);
  const links = pages.reduce((n, page) => n + page.plan.links.length, 0);
  const dropped = {};
  for (const page of pages) for (const [k, n] of Object.entries(page.plan.dropped)) dropped[k] = (dropped[k] || 0) + n;
  const kept = Object.entries(dropped).map(([k, n]) => `${k} ${n}`).join(", ");
  const said = `Brought in ${items} shapes and ${links} connectors from draw.io`
    + `${framed ? `, ${nounCount(pages.length, "page")} each in a frame of its own` : ""}${kept ? `; not kept: ${kept}` : ""}.`;
  wbAnnounce(said);
  toast(said);
  return items;
}

async function wbImportText(text) {
  if (/<mxfile[\s>]|<mxGraphModel[\s>]|content="&lt;mxfile/i.test(text)) return wbImportDrawio(text);
  const rows = /<svg[\s>]/i.test(text) ? wbBoardRowsFromSvg(text) : null;
  if (/<svg[\s>]/i.test(text) && !rows) {
    toast("That SVG was not exported from a board here, so it has no board inside it. Insert it as a picture instead.", "info");
    return 0;
  }
  return rows ? wbImportBoardRows(rows) : wbImportMermaid(text);
}

onDomReady(() => {
  const dialog = document.getElementById("wb-import-dialog");
  if (!dialog) return;
  const file = document.getElementById("wb-import-file");
  document.getElementById("wb-import-choose")?.addEventListener("click", () => file?.click());
  file?.addEventListener("change", async () => {
    const chosen = file.files?.[0];
    file.value = "";
    if (!chosen) return;
    const text = await chosen.text();
    dialog.close();
    await wbImportText(text);
  });
  document.getElementById("wb-import-go")?.addEventListener("click", async () => {
    const text = document.getElementById("wb-import-text")?.value || "";
    if (!text.trim()) {
      toast("Paste a Mermaid diagram first, or choose a file.");
      return;
    }
    dialog.close();
    await wbImportText(text);
  });
});

//: **Board thumbnails (INBOX 1317).** When edits settle (3 s) or the person
//: clicks away from the board, the board is drawn through the export path to a
//: ~480px WebP (JPEG where WebP cannot be encoded) and PUT to the server, which
//: keeps it as a file and serves it to every card and widget as a cached
//: <img>. The server's fingerprint decides whether a redraw is needed at all,
//: so panning or selecting (which also mutate the DOM) costs one small GET.
//: The SVG is built synchronously, before any await, because the click that
//: leaves the board hides it and the export reads live sizes.
const WB_THUMB = Object.freeze({ width: 480, maxHeight: 960, quality: 0.6, delayMs: 3000, maxBytes: 60 * 1024 });
const wbThumbState = { timer: null, pending: null, busy: false };

//: The default board has no note and no id; the server keeps its thumbnail
//: under 0 (the owner, 2026-10-26: "the default board doesnt get a thumbnail":
//: a falsy id was skipped here, so it only ever drew the schematic fallback).
function wbThumbBoardId() {
  return window.currentBoardId ?? 0;
}

function wbThumbMark() {
  wbThumbState.pending = wbThumbBoardId();
  clearTimeout(wbThumbState.timer);
  wbThumbState.timer = setTimeout(wbThumbFlush, WB_THUMB.delayMs);
}

async function wbThumbFlush() {
  clearTimeout(wbThumbState.timer);
  const id = wbThumbState.pending;
  wbThumbState.pending = null;
  const container = document.getElementById("whiteboard-container");
  if (id === null || wbThumbState.busy || String(wbThumbBoardId()) !== String(id)) return;
  if (!container || container.offsetParent === null) return;
  if (!(wbState.nodes?.length || wbState.sketches?.length || wbState.objects?.length)) return;
  let built;
  try {
    built = wbBuildExportSvg("board");
  } catch {
    return;
  }
  wbThumbState.busy = true;
  try {
    const state = await apiJson(`/whiteboard/boards/${id}/thumbnail/state`);
    if (state.stored === state.fp) return;
    const w = Math.max(1, Math.min(WB_THUMB.width, Math.round(built.width)));
    const h = Math.max(1, Math.min(WB_THUMB.maxHeight, Math.round((built.height * w) / built.width)));
    let blob = null;
    for (const quality of [WB_THUMB.quality, 0.4]) {
      blob = await wbRasterizeSvg(built.svg, w, h, "image/webp", quality);
      if (blob.type !== "image/webp") blob = await wbRasterizeSvg(built.svg, w, h, "image/jpeg", quality);
      if (blob.size <= WB_THUMB.maxBytes) break;
    }
    if (blob.size > WB_THUMB.maxBytes) return;
    await api(`/whiteboard/boards/${id}/thumbnail?fp=${state.fp}`, {
      method: "PUT",
      headers: { "Content-Type": blob.type },
      body: blob,
      silent: true,
    });
  } catch {
    // A thumbnail is a convenience: the SVG preview stays the fallback.
  } finally {
    wbThumbState.busy = false;
  }
}

(function wbThumbWatch() {
  const container = document.getElementById("whiteboard-container");
  if (!container) return;
  new MutationObserver(wbThumbMark).observe(container, { childList: true, subtree: true, attributes: true });
  document.addEventListener(
    "pointerdown",
    (event) => {
      if (wbThumbState.pending !== null && !container.contains(event.target)) wbThumbFlush();
    },
    true
  );
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden" && wbThumbState.pending !== null) wbThumbFlush();
  });
})();

// --- A live Mermaid diagram (INBOX 1451) -----------------------------------
//
// The owner: "allow mermaid diagrams to actually be added as objects like
// with draw.io into the whiteboard". An object of kind `diagram` keeps its
// source (`data.mermaid`) and nothing drawn: the notes' own hidden frame
// (mermaid-draw.js, loaded only when a board has one) draws it, so a theme
// change redraws it and an edit is one Save. Double-click edits it; "Turn
// into shapes" hands the source to `wbImportMermaid` for editable shapes.

const WB_DIAGRAM_SAMPLE = "flowchart TD\n  A[Start] --> B{Ready?}\n  B -->|yes| C[Ship it]";
const wbDiagramDialogState = { target: null, timer: 0 };

//: The drawing already made for this item's source in the theme in force, as
//: an image address, or "": export and the thumbnail are synchronous.
function wbDiagramDataUrl(obj) {
  const known = typeof mermaidKnown === "function" ? mermaidKnown(obj?.data?.mermaid || "") : null;
  return known?.svg ? `data:image/svg+xml;charset=utf-8,${encodeURIComponent(known.svg)}` : "";
}

function wbBuildDiagram(el, d) {
  el.attr("role", "img").on("dblclick", (event) => {
    event.stopPropagation();
    if (!wbIsLocked("object", d)) wbOpenDiagramDialog(d);
  });
}

//: Draws the source once per source and theme; a mistake shows the parser's
//: one line in the box instead of a broken picture.
function wbPaintDiagram(node, d) {
  const source = d.data?.mermaid || "";
  node.setAttribute("aria-label", `Mermaid ${wbMermaidKind(source) || ""} diagram`.replace("  ", " "));
  ensureModule("mermaid").then(() => {
    const key = `${source}\u0000${mermaidThemeNow().key}`;
    if (node._wbDiagramKey === key) return;
    node._wbDiagramKey = key;
    mermaidRequest(source).then((result) => {
      if (node._wbDiagramKey !== key) return;
      const url = wbDiagramDataUrl(d);
      const img = url ? Object.assign(document.createElement("img"), { src: url, alt: "", draggable: false }) : null;
      const note = img ? null : Object.assign(document.createElement("div"), { className: "wb-diagram-note", textContent: result?.error || "This diagram could not be drawn." });
      node.replaceChildren(img || note);
    });
  });
}

//: The box a drawing fits at its own shape: its longer side 480, neither
//: under 40 (a wide flowchart drew as a strip inside a 320 by 220 box).
async function wbDiagramSize(source) {
  await ensureModule("mermaid");
  const svg = (await mermaidRequest(source))?.svg || "";
  const box = /viewBox="[-\d.]+ [-\d.]+ ([\d.]+) ([\d.]+)"/.exec(svg);
  const ratio = box ? Number(box[1]) / Number(box[2]) || 1.45 : 1.45;
  const w = ratio >= 1 ? 480 : Math.max(40, 480 * ratio);
  return { width: Math.round(w), height: Math.round(Math.max(40, w / ratio)) };
}

async function wbInsertDiagram(source) {
  const [cx, cy] = wbViewCentre();
  const { width, height } = await wbDiagramSize(source);
  const made = await wbCreateObject("diagram", { mermaid: source }, cx - width / 2, cy - height / 2, width, height);
  if (!made) return null;
  clearWbSelection();
  wbHandleItemClick("object", made.id, { shiftKey: false });
  wbAnnounce("Diagram added. Double-click it to change it.");
  return made;
}

//: Insert opens it empty with a sample; double-click opens it on an item.
function wbOpenDiagramDialog(d = null) {
  const dialog = document.getElementById("wb-diagram-dialog");
  const field = document.getElementById("wb-diagram-text");
  if (!dialog || !field) return;
  wbDiagramDialogState.target = d;
  field.value = d?.data?.mermaid || WB_DIAGRAM_SAMPLE;
  document.getElementById("wb-diagram-title").textContent = d ? "Edit diagram" : "Mermaid diagram";
  document.getElementById("wb-diagram-save").textContent = d ? "Save" : "Add to board";
  const shapes = document.getElementById("wb-diagram-shapes");
  shapes.hidden = !d;
  shapes.disabled = !wbMermaidKind(field.value);
  wbDiagramPreview();
  dialog.showModal();
  field.focus();
}

function wbDiagramPreview() {
  const source = document.getElementById("wb-diagram-text")?.value || "";
  const well = document.getElementById("wb-diagram-preview");
  if (!well) return;
  ensureModule("mermaid").then(() => mermaidRequest(source)).then((result) => {
    if ((document.getElementById("wb-diagram-text")?.value || "") !== source) return;
    const url = wbDiagramDataUrl({ data: { mermaid: source } });
    const img = url ? Object.assign(document.createElement("img"), { src: url, alt: "Preview of the diagram" }) : null;
    well.replaceChildren(img || Object.assign(document.createElement("p"), { className: "muted", textContent: result?.error || "Nothing to draw yet." }));
  });
}

async function wbSaveDiagramDialog() {
  const dialog = document.getElementById("wb-diagram-dialog");
  const source = (document.getElementById("wb-diagram-text")?.value || "").trim();
  if (!source) {
    toast("Write the diagram first, or Cancel.");
    return;
  }
  dialog.close();
  const d = wbDiagramDialogState.target;
  if (!d) return wbInsertDiagram(source);
  if (source === d.data?.mermaid) return;
  wbPushUndo({ action: "move", kind: "object", id: d.id, before: WB_KIND_INFO.object.payload(d) });
  //: The new drawing's own shape, about the box's centre.
  const fit = await wbDiagramSize(source);
  d.data = { ...d.data, mermaid: source };
  Object.assign(d, { x: Math.round(d.x + (d.width - fit.width) / 2), y: Math.round(d.y + (d.height - fit.height) / 2) }, fit);
  await wbSaveObject(d);
  wbScheduleRender();
  wbAnnounce("Diagram saved.");
}

//: Editable shapes where the diagram stood, as one Undo step.
async function wbDiagramToShapes() {
  const d = wbDiagramDialogState.target;
  const source = document.getElementById("wb-diagram-text")?.value || "";
  if (!d || !wbMermaidKind(source)) return;
  document.getElementById("wb-diagram-dialog")?.close();
  await wbRecordGesture(async () => {
    const made = await wbImportMermaid(source, [d.x + d.width / 2, d.y + d.height / 2]);
    if (made) await wbDeleteObject(d);
  });
}

onDomReady(() => {
  const field = document.getElementById("wb-diagram-text");
  if (!field) return;
  field.addEventListener("input", () => {
    clearTimeout(wbDiagramDialogState.timer);
    document.getElementById("wb-diagram-shapes").disabled = !wbMermaidKind(field.value);
    wbDiagramDialogState.timer = setTimeout(wbDiagramPreview, 300);
  });
  document.getElementById("wb-diagram-save")?.addEventListener("click", wbSaveDiagramDialog);
  document.getElementById("wb-diagram-shapes")?.addEventListener("click", wbDiagramToShapes);
});
