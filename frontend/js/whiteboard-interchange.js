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
// - **Mermaid in** (`diagramModel.parse` in documents-mermaid.js, 1546 D4: the
//   one flowchart grammar; `wbMermaidLayout` here): the `graph` and `flowchart`
//   subset people write (rectangles, rounded, diamonds, circles; `-->`, `---`,
//   `-.->`, `==>`, labels as `|yes|` or `-- yes -->`; chains and `;`), laid
//   out in rows by depth, placed as shapes and elbow connectors, one undo step.
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

//: The board as a Mermaid flowchart: every connector whose two ends are a
//: shape, a text box or a card, and the things it joins. Pure: reads `state`.
//: `frameOf(kind, item)` (the board passes one) names the frame an item lies
//: in, `{id, title}` or null: those items are written inside a `subgraph`
//: of the frame's title, so frames go out and come back as frames.
function wbBoardToMermaid(state, cardTitle = (node) => `Note ${node.entry_id}`, frameOf = null) {
  //: Words safe inside a node or edge label: quotes, brackets and the bar would end it early.
  const safeWords = (text) => String(text || "").replace(/["[\](){}|<>#;]/g, " ").replace(/\s+/g, " ").trim().slice(0, 120) || " ";
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
    bucket.push(`${id}${open}"${safeWords(words)}"${close}`);
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
    const label = data.label ? `|${safeWords(data.label)}|` : "";
    edges.push(`  ${a} ${arrow}${label} ${b}`);
  }
  const lines = ["flowchart TD"];
  let f = 0;
  for (const { title, lines: inside } of framed.values()) {
    f += 1;
    lines.push(`  subgraph f${f} ["${safeWords(title)}"]`, ...inside.map((l) => `    ${l}`), "  end");
  }
  lines.push(...loose.map((l) => `  ${l}`), ...edges);
  return lines.join("\n") + "\n";
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

//: The colours a Mermaid source asks for, by node id and by connector index (L-documents-17). A `style Id fill:#..,stroke:#..`
//: line (the model keeps it as a line it cannot place) gives a block its fill and its stroke, 3 or 6 hex digits; the builder's
//: own hue (`n.fill`) is the stroke with a light fill; `linkStyle N stroke:#..` colours that connector. A named colour or any
//: other property is ignored: the board draws what it can read exactly and the rest as it always did.
wbMermaidLayout.look = (graph) => {
  const hex = (v) => {
    const m = /^#([0-9a-f]{3}|[0-9a-f]{6})$/i.exec(String(v || "").trim());
    return m ? "#" + (m[1].length === 3 ? [...m[1]].map((c) => c + c).join("") : m[1]).toLowerCase() : "";
  };
  const prop = (text, name) => hex(new RegExp(`(?:^|[,\\s])${name}:([^,\\s]+)`).exec(text)?.[1]);
  const nodes = new Map(), edges = new Map();
  graph.edges.forEach((e, i) => hex(e.colour) && edges.set(String(i), hex(e.colour)));
  for (const n of graph.nodes) if (hex(n.fill)) nodes.set(n.id, { color: hex(n.fill), fill: hex(n.fill), fillOpacity: 0.2 });
  for (const k of graph.kept || []) {
    const style = /^style\s+([\w-]+)\s+(.*)$/.exec(k.line || "");
    if (style) {
      const look = { ...nodes.get(style[1]) };
      const fill = prop(style[2], "fill"), stroke = prop(style[2], "stroke");
      if (fill) Object.assign(look, { fill, fillOpacity: 1 });
      if (stroke) look.color = stroke;
      if (fill || stroke) nodes.set(style[1], look);
      continue;
    }
    const link = /^linkStyle\s+(\d+)\s+(.*)$/.exec(k.line || "");
    if (link && prop(link[2], "stroke")) edges.set(link[1], prop(link[2], "stroke"));
  }
  return { nodes, edges };
};

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
const WB_DRAWIO_DROPPED = ["sketch", "glass", "comic"];

//: A vertex's look in the board's keys: stroke, fill, width (draw.io 1 is
//: the board's 2), dash, label colour, size and weight.
function wbDrawioLook(s) {
  const hex = (v) => (/^#[0-9a-f]{6}$/i.test(v || "") ? v.toLowerCase() : null);
  const look = {};
  if (s.strokeColor === "none") look.noStroke = true;
  else if (hex(s.strokeColor)) look.color = hex(s.strokeColor);
  //: draw.io's fillOpacity and strokeOpacity are percentages, 100 when absent.
  const pct = (v) => (v === undefined || v === "" || !Number.isFinite(Number(v)) ? null : Math.max(0, Math.min(100, Number(v))) / 100);
  if (hex(s.fillColor)) Object.assign(look, { fill: hex(s.fillColor), fillOpacity: pct(s.fillOpacity) ?? 1 });
  if (pct(s.strokeOpacity) !== null && pct(s.strokeOpacity) < 1) look.opacity = pct(s.strokeOpacity);
  if (hex(s.fontColor)) look.label_color = hex(s.fontColor);
  if (Number(s.fontStyle) & 1) look.label_bold = true;
  if (Number(s.fontStyle) & 2) look.label_italic = true;
  if (Number(s.fontSize) > 0) look.label_size = Math.round(Number(s.fontSize));
  look.width = Math.max(1, Math.round((Number(s.strokeWidth) || 1) * 2));
  if (s.dashed === "1") look.dash = "dashed";
  //: A gradient needs the fill it starts from; draw.io's direction is the board's (`gradientDirection` south by default).
  if (look.fill && hex(s.gradientColor)) look.gradient = { to: hex(s.gradientColor), dir: { south: "s", north: "n", east: "e", west: "w", radial: "radial" }[s.gradientDirection] || "s" };
  //: draw.io's shadow is a soft drop two across and three down.
  if (s.shadow === "1") Object.assign(look, { shadow: true, shadow_x: 2, shadow_y: 3, shadow_blur: 4 });
  return look;
}

//: **A shape's own connection points in a draw.io style** (a property of `wbDrawioStyle`, to add no global) (`points=[[x,y,perimeter,dx,dy],...]`, L-whiteboard-13): the two
//: fractions of the box, whether the point slides to the outline, and a pixel offset from there. They are the shape's
//: `ports` (the name is the board's own and has no place in the style). `read` is bounded as the server bounds them.
wbDrawioStyle.points = {
  MAX: 64,
  OFFSET: 2000,
  read(style) {
    let list = null;
    try { list = JSON.parse(style?.points); } catch { return []; }
    if (!Array.isArray(list)) return [];
    const round = (n) => Math.round(n * 1e4) / 1e4;
    const out = [];
    for (const q of list) {
      if (!Array.isArray(q) || !Number.isFinite(q[0]) || !Number.isFinite(q[1]) || Math.abs(q[0]) > 4 || Math.abs(q[1]) > 4) continue;
      const port = { x: round(q[0]), y: round(q[1]) };
      if (Number(q[2]) === 1) port.perimeter = true;
      for (const [key, i] of [["dx", 3], ["dy", 4]]) {
        const n = Number(q[i]);
        if (Number.isFinite(n) && n !== 0) port[key] = round(Math.max(-wbDrawioStyle.points.OFFSET, Math.min(wbDrawioStyle.points.OFFSET, n)));
      }
      out.push(port);
      if (out.length >= wbDrawioStyle.points.MAX) break;
    }
    return out;
  },
  write(ports) {
    const list = (Array.isArray(ports) ? ports : []).filter((q) => Number.isFinite(q?.x) && Number.isFinite(q?.y)).slice(0, wbDrawioStyle.points.MAX);
    if (!list.length) return "";
    return `points=${JSON.stringify(list.map((q) => [q.x, q.y, q.perimeter ? 1 : 0, Number(q.dx) || 0, Number(q.dy) || 0]))};`;
  },
};

//: What a vertex is drawn as, from its style: the kinds the board has a
//: path for, else a box (counted when its shape was something else).
function wbDrawioShape(s) {
  //: cylinder3, cube, step, umlActor...: the JS-drawn kinds of whiteboard-shape-table.js, drawn again at any size.
  //: The shape table loads after this file and is absent where this half runs alone (node tests), so it is looked up, not assumed.
  const drawn = (typeof wbFmtState === "undefined" ? {} : wbFmtState).shapeTable?.fromDrawio(s);
  if (drawn) return drawn;
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
    const ownPicture = s.shape === "image" && /^\/media\/[A-Za-z0-9][A-Za-z0-9._-]*$/.test(s.image || "");
    //: A picture that travels inside the file (`data:image/png,<base64>`, draw.io writes no `;base64`) is uploaded to this notebook on the way in; an outside address never is.
    const inline = s.shape === "image" ? /^data:(image\/(?:png|jpeg|gif|webp|svg\+xml)),([A-Za-z0-9+/=]{1,8000000})$/.exec(s.image || "") : null;
    const turn = wbDrawioStyle.more.rotation(s);
    for (const k of WB_DRAWIO_DROPPED) if (s[k] && s[k] !== "0") drop(k);
    if (s._kind === "group") continue;
    const at = origin(c.id);
    const box = { x: at.x, y: at.y, w: Math.max(1, Number(c.geo?.width) || 0), h: Math.max(1, Number(c.geo?.height) || 0) };
    const label = wbDrawioText(c.value, s.html !== "0");
    if (ownPicture) {
      //: Only a picture already on this notebook comes back; an outside address would make the board call out.
      const border = /^#[0-9a-f]{6}$/i.test(s.imageBorder || "") ? { border_color: s.imageBorder.toLowerCase(), border_width: Math.max(1, Math.min(40, Math.round(Number(s.strokeWidth) || 1))) } : {};
      items.push({ id: c.id, kind: "image", ...box, url: s.image, look: border, ...(turn ? { rotation: turn } : {}) });
    } else if (inline) {
      items.push({ id: c.id, kind: "image", ...box, url: null, inline: { mime: inline[1], base64: inline[2] }, look: {}, ...(turn ? { rotation: turn } : {}) });
    } else if (s._kind === "swimlane" || s.swimlane === "1") items.push({ id: c.id, kind: "frame", ...box, label });
    else if (s._kind === "text") items.push({ id: c.id, kind: "text", ...box, label, look: { font_size: Math.round(Number(s.fontSize) || 16), ...(wbDrawioLook(s).label_color ? { color: wbDrawioLook(s).label_color } : {}) }, ...(turn ? { rotation: turn } : {}) });
    else {
      const shape = wbDrawioShape(s);
      if (shape === "rect" && (s.shape || (s._kind && !["rounded", "whiteSpace", "html"].includes(s._kind)))) drop(`shape ${s.shape || s._kind}`);
      const ports = wbDrawioStyle.points.read(s);
      items.push({ id: c.id, kind: "shape", ...box, shape, label, look: wbDrawioLook(s), ...(ports.length ? { ports } : {}), ...(turn ? { rotation: turn } : {}) });
    }
  }
  for (const c of cells) {
    if (!c.edge) continue;
    const s = wbDrawioStyle(c.style);
    const data = { width: Math.max(1, Math.round((Number(s.strokeWidth) || 1) * 2)) };
    if (/^#[0-9a-f]{6}$/i.test(s.strokeColor || "")) data.color = s.strokeColor.toLowerCase();
    if (s.edgeStyle === "orthogonalEdgeStyle" || s.edgeStyle === "elbowEdgeStyle") data.route = "elbow";
    if (s.edgeStyle === "entityRelationEdgeStyle") data.route = "er";
    if (s.edgeStyle === "isometricEdgeStyle") data.route = "iso";
    //: draw.io's edge shapes (`shape=` on an edge) are the board's connector shapes (`shape` on a link).
    const edgeShape = { link: "double", arrow: "block", flexArrow: "flex", taperedArrow: "tapered", pipe: "pipe", wire: "wire" }[s.shape];
    if (edgeShape) data.shape = edgeShape;
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
    if (Array.isArray(c.points) && c.points.length && !["elbow", "er", "iso"].includes(data.route)) data.points = c.points.map((p) => ({ x: Number(p.x) || 0, y: Number(p.y) || 0 }));
    links.push({ id: c.id, type: s.curved === "1" ? "link-curved" : "link-straight", source, target, data });
  }
  return { items, links, dropped };
}

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
  //: A fill or a line under 100% says so, as draw.io's own percentages.
  const opacityKeys = (d) => `${hex(d.fill) && d.fillOpacity != null && d.fillOpacity < 1 ? `fillOpacity=${Math.round(d.fillOpacity * 100)};` : ""}${d.opacity != null && d.opacity < 1 ? `strokeOpacity=${Math.round(d.opacity * 100)};` : ""}`;
  //: The board's gradient and shadow as draw.io's keys (the reader's table, turned round).
  const paintKeys = (d) => `${hex(d.fill) && hex(d.gradient?.to) ? `gradientColor=${hex(d.gradient.to)};gradientDirection=${{ s: "south", n: "north", e: "east", w: "west", radial: "radial" }[d.gradient.dir] || "south"};` : ""}${d.shadow ? "shadow=1;" : ""}`;
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
    //: A card, text box or picture turns about its centre; a drawn shape has its turn in its path.
    const turn = Number(o.rotation) ? `rotation=${Math.round(Number(o.rotation) * 100) / 100};` : "";
    if (o.kind === "frame") vertex(`object:${o.id}`, "swimlane;startSize=30;html=0;whiteSpace=wrap;", d.content || "Frame", b);
    else if (o.kind === "text") {
      const filled = hex(d.bg) || hex(d.border_color);
      const look = font(d.font_size, d.bold, d.italic, d.underline, d.color);
      if (filled) vertex(`object:${o.id}`, `${turn}rounded=0;whiteSpace=wrap;html=0;${paintKeys({ fill: d.bg, shadow: d.shadow, gradient: d.gradient })}${hex(d.bg) ? `fillColor=${hex(d.bg)};${d.bg_alpha != null && d.bg_alpha < 1 ? `fillOpacity=${Math.round(d.bg_alpha * 100)};` : ""}` : ""}${hex(d.border_color) ? `strokeColor=${hex(d.border_color)};` : ""}${look}`, d.content || "", b);
      else vertex(`object:${o.id}`, `${turn}text;whiteSpace=wrap;html=0;align=left;verticalAlign=top;${look}`, d.content || "", b);
    } else if (o.kind === "table" && Array.isArray(d.cells) && d.cells.length) {
      //: A table is its cells, one vertex each (a merged cell as one spanning its rows and columns), so the file draws it as the board does.
      for (const cell of wbTableRules.wbTableCellBoxes(o, b.w, b.h)) {
        const fill = cell.head ? "#eef1f6" : cell.stripe ? "#f4f6fa" : "#ffffff";
        vertex(`object:${o.id}:${cell.r}:${cell.c}`, `rounded=0;whiteSpace=wrap;html=0;align=left;verticalAlign=top;fillColor=${fill};strokeColor=#9aa3b5;${cell.head ? "fontStyle=1;" : ""}`, cell.text, { x: b.x + cell.x, y: b.y + cell.y, w: cell.w, h: cell.h });
      }
    } else if (o.kind === "image" && /^\/media\/[A-Za-z0-9][A-Za-z0-9._-]*$/.test(d.url || "")) {
      //: A picture of this notebook's: its address and its border (draw.io's `imageBorder` and `strokeWidth`).
      vertex(`object:${o.id}`, `${turn}shape=image;html=0;aspect=fixed;image=${d.url};${hex(d.border_color) && d.border_width > 0 ? `imageBorder=${hex(d.border_color)};strokeWidth=${Math.round(d.border_width)};` : ""}`, "", b);
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
    //: A table shape (cylinder, cube, step...) goes out under its draw.io `shape=` word, open sub-paths and all.
    const drawn = d.shapeKind ? (typeof wbFmtState === "undefined" ? {} : wbFmtState).shapeTable?.toDrawio(d.shapeKind) || "" : "";
    if (typeof d.d !== "string" || !(drawn || WB_DRAWIO_SHAPES_OUT[d.shape] || d.shape === "custom" || closed)) { skip("drawn lines"); continue; }
    const bb = bounds("sketch", sk);
    if (!bb) { skip("drawn lines"); continue; }
    if (!drawn && (d.shape === "custom" || (!WB_DRAWIO_SHAPES_OUT[d.shape] && closed))) skip("shapes drawn as boxes");
    const shape = drawn ? drawn.replace(/;$/, "") : WB_DRAWIO_SHAPES_OUT[d.shape] || "rounded=0";
    const width = Math.max(1, Math.round((Number(d.width) || 2) / 2));
    vertex(`sketch:${sk.id}`,
      `${shape};whiteSpace=wrap;html=0;${hex(d.color) ? `strokeColor=${hex(d.color)};` : ""}${hex(d.fill) ? `fillColor=${hex(d.fill)};` : "fillColor=none;"}${opacityKeys(d)}${paintKeys(d)}strokeWidth=${width};${d.dash === "dashed" || d.dash === "dotted" ? "dashed=1;" : ""}${wbDrawioStyle.points.write(d.ports)}${font(d.label_size, d.label_bold, d.label_italic, d.label_underline, d.label_color)}`,
      d.label || "", { x: bb.minX, y: bb.minY, w: bb.maxX - bb.minX, h: bb.maxY - bb.minY });
  }
  for (const [sk, stored] of links) {
    //: draw.io has no end on an edge's line, so an end on a connector goes out as the free point it resolves to now.
    const d = (typeof wbFmtState === "undefined" ? null : wbFmtState.linkEdge)?.pinned(stored) ?? stored;
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
    //: A .drawio edge carries one value here; the second label (`label2`) has no cell of its own to ride, so the notice names it.
    if (d.label2) skip("second connector labels");
    //: The board's end marks to draw.io's (the import's table, turned round).
    const capsOut = { arrow: "classic", circle: "oval", "er-one-only": "ERone", "er-one": "ERmandOne", "er-many": "ERmany", "er-one-many": "ERoneToMany", "er-zero-one": "ERzeroToOne", "er-zero-many": "ERzeroToMany", cross: "cross", "half-arrow": "openAsync", "double-arrow": "doubleBlock" };
    const capOf = (cap, flag) => (cap && cap !== "none" ? capsOut[cap] || "classic" : flag ? "classic" : "none");
    const end = capOf(d.endCap, d.endStyle === "end" || d.endStyle === "both");
    const start = capOf(d.startCap, d.endStyle === "both");
    const way = Array.isArray(d.points) && !["elbow", "er", "iso"].includes(d.route) ? `<Array as="points">${d.points.map((p) => `<mxPoint x="${Math.round(p.x)}" y="${Math.round(p.y)}"/>`).join("")}</Array>` : "";
    const edgeShape = { double: "link", block: "arrow", flex: "flexArrow", tapered: "taperedArrow", pipe: "pipe", wire: "wire" }[d.shape];
    const style = `${edgeShape ? `shape=${edgeShape};` : ""}${{ elbow: "edgeStyle=orthogonalEdgeStyle;", er: "edgeStyle=entityRelationEdgeStyle;", iso: "edgeStyle=isometricEdgeStyle;" }[d.route] || ""}${d.type === "link-curved" ? "curved=1;" : ""}html=0;endArrow=${end};startArrow=${start};` +
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

//: **draw.io beyond a single file** (a property of `wbDrawioStyle`, to add no global): a turn, a picture inside
//: a file, a library file (`mxlibrary`), the CSV import, and a plan as a library entry. Each is pure but the
//: ones that read XML or upload, which `wbDrawioCells` and the notebook's media route do.
wbDrawioStyle.more = {
  //: A turn in degrees from a style (`rotation=`), clockwise as the board's: 0 when absent or whole turns.
  rotation(s) {
    const deg = Number(s.rotation);
    return Number.isFinite(deg) && deg % 360 !== 0 ? Math.round((((deg % 360) + 360) % 360) * 100) / 100 : 0;
  },
  //: A path of M, L, C and Z turned `deg` clockwise about a centre.
  turn(d, deg, cx, cy) {
    const rad = (deg * Math.PI) / 180, cos = Math.cos(rad), sin = Math.sin(rad);
    const round = (n) => Math.round(n * 100) / 100;
    const nums = String(d).match(/[MLCZ]|-?\d*\.?\d+/g) || [];
    const out = [];
    for (let i = 0; i < nums.length; i++) {
      if (/[MLCZ]/.test(nums[i])) { out.push(nums[i]); continue; }
      const x = Number(nums[i]) - cx, y = Number(nums[++i]) - cy;
      out.push(round(cx + x * cos - y * sin), round(cy + x * sin + y * cos));
    }
    return out.join(" ");
  },
  //: A shape's `sketch` data at `dx, dy`: its path (turned when it has a turn), its look, label and ports.
  shapeData(item, dx, dy, ink) {
    const own = (typeof wbFmtState === "undefined" ? {} : wbFmtState).shapeTable?.shapePathAt(item.shape, item.x + dx, item.y + dy, item.w, item.h);
    const path = own || wbDrawioPath(item.shape, item.x + dx, item.y + dy, item.w, item.h);
    const data = {
      d: item.rotation ? wbDrawioStyle.more.turn(path, item.rotation, item.x + dx + item.w / 2, item.y + dy + item.h / 2) : path,
      shape: item.rotation ? "custom" : item.shape === "ellipse" ? "circle" : item.shape === "diamond" ? "diamond" : item.shape === "rect" ? "rect" : "custom", color: ink, ...item.look,
    };
    if (own) {
      data.shapeKind = item.shape;
      data.label_area = wbFmtState.shapeTable.area(item.shape);
      if (item.rotation) delete data.shapeKind; //: a turned outline is only stretched, never drawn again
    }
    if (item.label) data.label = item.label;
    if (item.ports?.length) data.ports = item.ports;
    return data;
  },
  //: A picture inside a `.drawio` file, uploaded to this notebook as board-only media (as a pasted picture is); its address, or null.
  //: An SVG one is drawn to a PNG first: the upload takes no `.svg` (a script could ride in one), so it would be lost.
  async picture({ mime, base64 }, box = { w: 256, h: 256 }) {
    try {
      let file = new Blob([Uint8Array.from(atob(base64), (ch) => ch.charCodeAt(0))], { type: mime });
      if (mime === "image/svg+xml") file = await wbDrawioStyle.more.svgToPng(file, box);
      if (!file) return null;
      const ext = file.type.slice(6).replace("jpeg", "jpg");
      const form = new FormData();
      form.append("file", new File([file], `drawio-picture.${ext}`, { type: file.type }));
      form.append("board", "true");
      return (await apiJson("/media/upload", { method: "POST", headers: authHeaders(), body: form }))?.url || null;
    } catch {
      return null;
    }
  },
  //: An SVG picture as a PNG at twice its box on the board (the SVG may carry no size of its own), or null.
  async svgToPng(svg, { w, h }) {
    const width = Math.round(Math.max(1, w) * 2), height = Math.round(Math.max(1, h) * 2);
    if (width * height > 64e6) return null;
    const url = URL.createObjectURL(svg);
    try {
      const img = new Image();
      img.src = url;
      await img.decode();
      const canvas = Object.assign(document.createElement("canvas"), { width, height });
      canvas.getContext("2d").drawImage(img, 0, 0, width, height);
      return await new Promise((done) => canvas.toBlob(done, "image/png"));
    } catch {
      return null;
    } finally {
      URL.revokeObjectURL(url);
    }
  },
  //: draw.io's packing of XML: URI-encoded, deflated raw, base64.
  async inflate(packed) {
    const bytes = Uint8Array.from(atob(String(packed).trim()), (ch) => ch.charCodeAt(0));
    const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream("deflate-raw"));
    return decodeURIComponent(await new Response(stream).text());
  },
  async deflate(xml) {
    const stream = new Blob([encodeURIComponent(xml)]).stream().pipeThrough(new CompressionStream("deflate-raw"));
    const bytes = new Uint8Array(await new Response(stream).arrayBuffer());
    let bin = "";
    for (const b of bytes) bin += String.fromCharCode(b);
    return btoa(bin);
  },

  //: A plan as a library entry's payload (the board's own element format): item boxes from the plan's
  //: top-left, shapes as drawings, links between the items they join. A picture inside the file has no
  //: notebook address to keep and a connector with a loose end joins nothing, so both are counted in `skipped`.
  payload(plan) {
    if (!plan.items.length) return null;
    const box = {
      minX: Math.min(...plan.items.map((i) => i.x)), minY: Math.min(...plan.items.map((i) => i.y)),
      maxX: Math.max(...plan.items.map((i) => i.x + i.w)), maxY: Math.max(...plan.items.map((i) => i.y + i.h)),
    };
    box.w = box.maxX - box.minX;
    box.h = box.maxY - box.minY;
    const keys = new Map();
    const items = [];
    let skipped = 0;
    for (const [i, it] of plan.items.entries()) {
      const key = `d${i}`;
      const x = Math.round(it.x - box.minX), y = Math.round(it.y - box.minY);
      const turn = it.rotation ? { rotation: it.rotation } : {};
      if (it.kind === "frame") items.push({ key, kind: "object", type: "frame", data: { content: it.label || "Frame" }, x, y, w: it.w, h: it.h, z: -1 });
      else if (it.kind === "text") items.push({ key, kind: "object", type: "text", data: { content: it.label || "", ...it.look }, x, y, w: it.w, h: it.h, z: i + 1, ...turn });
      else if (it.kind === "image") {
        if (!it.url) { skipped += 1; continue; }
        items.push({ key, kind: "object", type: "image", data: { url: it.url, ...it.look }, x, y, w: it.w, h: it.h, z: i + 1, ...turn });
      } else items.push({ key, kind: "sketch", data: wbDrawioStyle.more.shapeData(it, -box.minX, -box.minY, "ink"), z: i + 1 });
      keys.set(it.id, key);
    }
    const links = [];
    for (const l of plan.links) {
      if (!keys.has(l.source) || !keys.has(l.target)) { skipped += 1; continue; }
      const data = { type: l.type, color: "ink", ...l.data };
      if (data.points) data.points = data.points.map((p) => ({ x: p.x - box.minX, y: p.y - box.minY }));
      links.push({ from: keys.get(l.source), to: keys.get(l.target), data });
    }
    return { payload: { box: { w: Math.max(1, Math.round(box.w)), h: Math.max(1, Math.round(box.h)) }, items, links }, skipped };
  },

  //: **`mxlibrary`** (a draw.io shape library): `<mxlibrary>[{"xml", "w", "h", "title"}]</mxlibrary>`, each `xml`
  //: plain or packed. `read` is the entries (null when the text is not one); `body` is the board library's own
  //: import body, every entry through the same cell reader and planner a `.drawio` file takes.
  mxlibrary: {
    LIMIT: 500,
    read(text) {
      const m = /<mxlibrary[^>]*>([\s\S]*?)<\/mxlibrary>/i.exec(String(text || ""));
      if (!m) return null;
      const body = m[1].replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"').replace(/&apos;/g, "'").replace(/&amp;/g, "&");
      let list = null;
      try { list = JSON.parse(body); } catch { return null; }
      if (!Array.isArray(list)) return null;
      return list.slice(0, wbDrawioStyle.more.mxlibrary.LIMIT).map((e) => ({ xml: typeof e?.xml === "string" ? e.xml : "", title: String(e?.title || "").slice(0, 80) }));
    },
    async body(text, name = "draw.io library") {
      const entries = wbDrawioStyle.more.mxlibrary.read(text);
      if (!entries) return null;
      const items = [];
      let skipped = 0;
      for (const [i, e] of entries.entries()) {
        let made = null;
        try {
          const xml = e.xml.trimStart().startsWith("<") ? e.xml : await wbDrawioStyle.more.inflate(e.xml);
          const read = e.xml ? await wbDrawioCells(xml) : null;
          made = read ? wbDrawioStyle.more.payload(wbDrawioPlan(read.cells)) : null;
        } catch {
          made = null;
        }
        if (!made) { skipped += 1; continue; }
        skipped += made.skipped;
        items.push({ kind: "element", name: e.title || `Shape ${i + 1}`, tags: ["draw.io"], payload: made.payload });
      }
      return { body: { format: "memorymap-library", version: 1, library: { name: String(name).slice(0, 80) }, items }, skipped };
    },
    //: A library's items (the export route's JSON) as an `mxlibrary` file, each through the cell writer. Items
    //: with no shapes in them (styles, palettes, branches) are left out and counted.
    async write(lib) {
      const entries = [];
      let left = 0;
      for (const it of lib.items || []) {
        const p = it.payload;
        if (!["element", "shape", "preset"].includes(it.kind) || !Array.isArray(p?.items) || !p.items.length) { left += 1; continue; }
        const at = new Map();
        const state = { objects: [], sketches: [], nodes: [] };
        const boxes = new Map();
        for (const [i, item] of p.items.entries()) {
          if (item.kind === "object") {
            state.objects.push({ id: i, kind: item.type, x: item.x, y: item.y, width: item.w, height: item.h, z: item.z, rotation: item.rotation, data: item.data || {} });
            at.set(item.key, ["object", i]);
          } else {
            const row = { id: i, data: JSON.stringify(item.data || {}) };
            const nums = /[Aa]/.test(item.data?.d || "") ? [] : (String(item.data?.d || "").match(/-?\d*\.?\d+/g) || []).map(Number);
            const xs = nums.filter((_, n) => n % 2 === 0), ys = nums.filter((_, n) => n % 2 === 1);
            boxes.set(row, xs.length && ys.length ? { minX: Math.min(...xs), minY: Math.min(...ys), maxX: Math.max(...xs), maxY: Math.max(...ys) } : { minX: 0, minY: 0, maxX: p.box.w, maxY: p.box.h });
            state.sketches.push(row);
            at.set(item.key, ["sketch", i]);
          }
        }
        let n = state.sketches.length + state.objects.length;
        for (const l of p.links || []) {
          const a = at.get(l.from), b = at.get(l.to);
          if (a && b) state.sketches.push({ id: ++n + 1000, data: JSON.stringify({ ...l.data, sourceKind: a[0], sourceId: a[1], targetKind: b[0], targetId: b[1] }) });
        }
        const out = wbBoardToDrawio(state, { title: it.name, box: (_, row) => boxes.get(row) || null });
        const model = /<mxGraphModel[\s\S]*<\/mxGraphModel>/.exec(out.xml)?.[0];
        if (!model) { left += 1; continue; }
        entries.push({ xml: await wbDrawioStyle.more.deflate(model), w: Math.round(p.box.w), h: Math.round(p.box.h), aspect: "fixed", title: String(it.name || "Shape").slice(0, 80) });
      }
      const json = JSON.stringify(entries).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
      return { xml: `<mxlibrary>${json}</mxlibrary>\n`, count: entries.length, left };
    },
  },

  //: **draw.io's CSV import** (`# label:`, `# style:`, `# connect:` and the rest above a table with a header
  //: row). Each row is a vertex whose label and style are templates over its columns (`%name%`), each
  //: `connect` line joins rows by a column that holds the other row's value, and `layout` places them with the
  //: board's flow layout (the Mermaid import's) or a grid when it names none. Same cells as a file's, so the
  //: planner and the placer are the `.drawio` ones.
  csv: {
    //: A directive is `# key: value`, or `## key: value`; the file is CSV when one of these comes first.
    DIRECTIVE: /^\s*#{1,2}\s*(label|style|parentstyle|stylename|styles|identity|parent|namespace|connect|width|height|padding|ignore|nodespacing|levelspacing|edgespacing|layout|link|labelname|labels|left|top)\s*:\s*(.*)$/i,
    is(text) {
      const first = String(text || "").slice(0, 4000).split(/\r?\n/).find((l) => l.trim());
      return Boolean(first && wbDrawioStyle.more.csv.DIRECTIVE.test(first));
    },
    //: Directives in order, and the table's records (quotes may hold commas, quotes and line breaks).
    split(text) {
      const directives = [], table = [];
      let row = [], field = "", quoted = false, lineStart = true;
      const src = String(text || "").replace(/^﻿/, "");
      for (let i = 0; i < src.length; i += 1) {
        const ch = src[i];
        if (lineStart && !quoted && ch === "#") {
          let end = src.indexOf("\n", i);
          if (end < 0) end = src.length;
          const m = wbDrawioStyle.more.csv.DIRECTIVE.exec(src.slice(i, end).replace(/\r$/, ""));
          if (m) directives.push([m[1].toLowerCase(), m[2].trim()]);
          i = end;
          continue;
        }
        lineStart = false;
        if (quoted) {
          if (ch === '"' && src[i + 1] === '"') { field += '"'; i += 1; } else if (ch === '"') quoted = false; else field += ch;
        } else if (ch === '"' && !field) quoted = true;
        else if (ch === ",") { row.push(field); field = ""; } else if (ch === "\n" || ch === "\r") {
          if (ch === "\r" && src[i + 1] === "\n") i += 1;
          row.push(field);
          field = "";
          if (row.some((v) => v.trim())) table.push(row);
          row = [];
          lineStart = true;
        } else field += ch;
      }
      row.push(field);
      if (row.some((v) => v.trim())) table.push(row);
      return { directives, table };
    },
    //: The cells (as `wbDrawioModelCells` makes them) for CSV text, `dropped` (what has no counterpart) and the layout used.
    read(text) {
      const { directives, table } = wbDrawioStyle.more.csv.split(text);
      if (table.length < 2) return null;
      const dir = (key) => directives.filter((d) => d[0] === key).map((d) => d[1]);
      const one = (key, otherwise = "") => dir(key)[0] ?? otherwise;
      const head = table[0].map((h) => h.trim());
      const rows = table.slice(1).map((r) => Object.fromEntries(head.map((h, i) => [h, (r[i] ?? "").trim()])));
      const dropped = {};
      const fill = (tpl, row) => String(tpl).replace(/%(\w+)%/g, (m, k) => (k in row ? row[k] : m)).replace(/%%/g, "%");
      const styleMap = (() => { try { return JSON.parse(one("styles", "{}")) || {}; } catch { return {}; } })();
      const styleName = one("stylename");
      const baseStyle = one("style", "whiteSpace=wrap;html=1;");
      const labelTpl = one("label", `%${head[0]}%`);
      for (const k of ["parent", "parentstyle"]) if (one(k)) dropped[`csv ${k}`] = 1;
      const gapX = Math.max(10, Number(one("nodespacing")) || 40), gapY = Math.max(10, Number(one("levelspacing")) || 100);
      const wantW = Number(one("width")), wantH = Number(one("height"));
      const identity = one("identity");
      const nodes = rows.map((row, i) => {
        const id = `csv${i}`;
        const value = fill(labelTpl, row);
        const plain = wbDrawioText(value, true);
        const lines = plain.split("\n");
        const w = wantW > 0 ? wantW : Math.max(90, Math.min(280, Math.max(...lines.map((l) => l.length)) * 8 + 30));
        const h = wantH > 0 ? wantH : Math.max(48, lines.length * 20 + 24);
        const extra = styleName && styleMap[row[styleName]] ? String(styleMap[row[styleName]]) : "";
        return { id, row, value, w, h, style: `${fill(baseStyle, row)}${extra && !/;$/.test(fill(baseStyle, row)) ? ";" : ""}${extra}` };
      });
      //: Edges: a row's `from` column holds values (comma separated) of other rows' `to` column.
      const edges = [];
      for (const raw of dir("connect")) {
        let rule = null;
        try { rule = JSON.parse(raw); } catch { dropped["csv connect not JSON"] = (dropped["csv connect not JSON"] || 0) + 1; continue; }
        const to = rule.to === "id" && identity ? identity : rule.to;
        if (!rule.from || !to) continue;
        for (const n of nodes) {
          for (const ref of String(n.row[rule.from] ?? "").split(",").map((v) => v.trim()).filter(Boolean)) {
            for (const other of nodes) {
              if (other === n || other.row[to] !== ref) continue;
              const [source, target] = rule.invert ? [other, n] : [n, other];
              edges.push({ id: `csve${edges.length}`, source: source.id, target: target.id, value: rule.label ? fill(rule.label, n.row) : "", style: String(rule.style || "endArrow=classic;") });
            }
          }
        }
      }
      //: Placement: the board's flow layout for the flow and tree names, a grid for none.
      const named = one("layout", "auto").toLowerCase();
      const flow = { horizontalflow: "LR", horizontaltree: "LR", verticalflow: "TB", verticaltree: "TB" }[named];
      const pos = new Map();
      if (flow || (!["auto", "none", ""].includes(named) && edges.length)) {
        if (!flow) dropped[`layout ${named}`] = 1;
        const wide = Math.max(...nodes.map((n) => n.w));
        const high = Math.max(...nodes.map((n) => n.h));
        const graph = { dir: flow || "TB", nodes: nodes.map((n) => ({ id: n.id, h: n.h })), edges: edges.map((e) => ({ from: e.source, to: e.target })) };
        const place = wbMermaidLayout(graph, { w: wide, h: high, gapX: flow === "LR" ? wide + gapY : wide + gapX, gapY: flow === "LR" ? high + gapX : high + gapY });
        for (const n of nodes) { const c = place.get(n.id); pos.set(n.id, { x: c.x - n.w / 2, y: c.y - n.h / 2 }); }
      } else {
        if (!["auto", "none", ""].includes(named)) dropped[`layout ${named}`] = 1;
        const across = Math.max(1, Math.ceil(Math.sqrt(nodes.length)));
        const wide = Math.max(...nodes.map((n) => n.w)), high = Math.max(...nodes.map((n) => n.h));
        nodes.forEach((n, i) => pos.set(n.id, { x: (i % across) * (wide + gapX), y: Math.floor(i / across) * (high + gapX) }));
      }
      const cells = [{ id: "0" }, { id: "1", parent: "0" }];
      for (const n of nodes) {
        const p = pos.get(n.id);
        cells.push({ id: n.id, parent: "1", vertex: true, value: n.value, style: n.style, geo: { x: p.x, y: p.y, width: n.w, height: n.h } });
      }
      for (const e of edges) cells.push({ id: e.id, parent: "1", edge: true, source: e.source, target: e.target, value: e.value, style: e.style, geo: {} });
      return { cells, dropped, layout: named, rows: nodes.length };
    },
  },
};

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
    return wbFmtState.linkEdge.keptRows(rows);
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
    //: Connectors rejoin in passes, so one that hangs on another connector (whiteboard-link-edge.js) finds it made.
    let waiting = rows.filter((r) => r.link);
    for (let pass = 0; pass < 5 && waiting.length; pass += 1) {
      const later = [];
      for (const row of waiting) {
        const data = wbFmtState.linkEdge.place(JSON.parse(row.payload.data), remap, dx, dy);
        if (!data) {
          later.push(row);
          continue;
        }
        const link = await apiJson("/whiteboard/sketches", { method: "POST", body: JSON.stringify({ data: JSON.stringify(data), x: 0, y: 0, z: wbStackNewZ("sketch"), board_id: window.currentBoardId ?? null }) });
        wbState.sketches.push(link);
        remap.set(`sketch:${row.id}`, link.id);
      }
      if (later.length === waiting.length) break;
      waiting = later;
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
  const graph = kind === "state" ? wbMermaidStateParse(source) : kind === "class" ? wbMermaidClassParse(source) : diagramModel.parse(source) || { nodes: [], edges: [] };
  if (!graph.nodes.length) {
    toast("No diagram found. Start with a line like: flowchart TD, stateDiagram, classDiagram or sequenceDiagram", "info");
    return 0;
  }
  const place = wbMermaidLayout(graph);
  const look = wbMermaidLayout.look(graph);
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
      const made = await wbMermaidPlaceNode(n, at[0] + c.x, at[1] + c.y, ink, look.nodes.get(n.id));
      wbState.sketches.push(made);
      ids.set(n.id, made.id);
    }
    for (const [index, e] of graph.edges.entries()) {
      //: An end that names a subgraph joins its frame.
      const s = ids.get(e.from) ?? frameIds.get(e.from), t = ids.get(e.to) ?? frameIds.get(e.to);
      if (s == null || t == null || (s === t && ids.has(e.from) === ids.has(e.to))) continue;
      const sKind = ids.has(e.from) ? "sketch" : "object", tKind = ids.has(e.to) ? "sketch" : "object";
      const data = { type: "link-straight", route: "elbow", sourceId: s, sourceKind: sKind, targetId: t, targetKind: tKind, color: look.edges.get(String(index)) || ink, width: 2 };
      if (e.endCap || e.arrow) data.endCap = wbMermaidCap(e.endCap || "arrow");
      if (e.startCap) data.startCap = wbMermaidCap(e.startCap);
      if (e.dashed || e.style === "dotted") data.dash = "dashed";
      if (e.label) data.label = e.label;
      const link = await apiJson("/whiteboard/sketches", { method: "POST", body: JSON.stringify({ data: JSON.stringify(data), x: 0, y: 0, z: wbStackNewZ("sketch"), board_id: window.currentBoardId ?? null }) });
      wbState.sketches.push(link);
    }
  });
  renderWhiteboardNow();
  const frames = frameIds.size ? ` in ${nounCount(frameIds.size, "frame")}` : "";
  //: The model keeps a line it cannot place (`kept`); the other readers count `skipped`.
  const skipped = graph.skipped || graph.kept?.length || 0;
  const said = `Brought in ${graph.nodes.length} shapes${frames} and ${graph.edges.length} connectors${skipped ? `; ${nounCount(skipped, "line")} left out` : ""}.`;
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
async function wbMermaidPlaceNode(n, cx, cy, ink, look = null) {
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
  if (look && !dot) Object.assign(data, look);
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
    return xml(await wbDrawioStyle.more.inflate(packed)).getElementsByTagName("mxGraphModel")[0] || null;
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
  for (const item of plan.items.filter((i) => i.kind === "image")) {
    const url = item.url || (item.inline ? await wbDrawioStyle.more.picture(item.inline, item) : null);
    //: A picture that would not upload is named in the import's report, never dropped silently.
    if (!url) { plan.dropped.pictures = (plan.dropped.pictures || 0) + 1; plan.unplaced = (plan.unplaced || 0) + 1; continue; }
    const made = await wbCreateObject("image", { url, ...item.look }, Math.round(item.x + dx), Math.round(item.y + dy), Math.round(Math.max(20, item.w)), Math.round(Math.max(20, item.h)), undefined, item.rotation ? { rotation: item.rotation } : null);
    if (made) ids.set(item.id, ["object", made.id]);
  }
  for (const item of plan.items.filter((i) => i.kind === "text")) {
    const made = await wbCreateObject("text", { content: item.label, ...item.look }, Math.round(item.x + dx), Math.round(item.y + dy), Math.round(Math.max(40, item.w)), Math.round(Math.max(24, item.h)), undefined, item.rotation ? { rotation: item.rotation } : null);
    if (made) ids.set(item.id, ["object", made.id]);
  }
  for (const item of plan.items.filter((i) => i.kind === "shape")) {
    const data = wbDrawioStyle.more.shapeData(item, dx, dy, ink);
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
const WB_DRAWIO_PAGE = { pad: 48, gap: 160 };

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
async function wbImportDrawio(text, at = wbViewCentre(), csv = null) {
  let read = null;
  try {
    read = csv ? { all: [{ name: "CSV", cells: csv.cells }] } : await wbDrawioCells(text);
  } catch {
    read = null;
  }
  if (!read) {
    toast("That draw.io file could not be read.", "info");
    return 0;
  }
  const pages = read.all.map((page) => ({ ...page, plan: wbDrawioPlan(page.cells) })).filter((page) => page.plan.items.length);
  for (const [k, n] of Object.entries(csv?.dropped || {})) pages[0].plan.dropped[k] = (pages[0].plan.dropped[k] || 0) + n;
  if (!pages.length) {
    toast("That draw.io file has no shapes to bring in.", "info");
    return 0;
  }
  const framed = pages.length > 1;
  const pad = framed ? WB_DRAWIO_PAGE.pad : 0;
  for (const page of pages) page.box = wbDrawioBox(page.plan);
  const rowW = pages.reduce((sum, page) => sum + page.box.w + pad * 2, 0) + WB_DRAWIO_PAGE.gap * (pages.length - 1);
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
      left += page.box.w + pad * 2 + WB_DRAWIO_PAGE.gap;
    }
  });
  renderWhiteboardNow();
  const items = pages.reduce((n, page) => n + page.plan.items.length - (page.plan.unplaced || 0), 0);
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
  if (wbDrawioStyle.more.csv.is(text)) {
    const csv = wbDrawioStyle.more.csv.read(text);
    if (!csv) {
      toast("That draw.io CSV has a header row and no rows under it.", "info");
      return 0;
    }
    return wbImportDrawio(text, wbViewCentre(), csv);
  }
  if (/<mxlibrary[\s>]/i.test(text)) {
    await wbLibImportFile(new File([text], "draw.io library.xml", { type: "text/xml" }));
    return 0;
  }
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
    //: A PNG exported with "Include a copy of the diagram" carries its board in a chunk.
    if (chosen.type === "image/png" || /\.png$/i.test(chosen.name)) {
      const rows = wbFmtState.exporters.rowsOf(new Uint8Array(await chosen.arrayBuffer()));
      dialog.close();
      if (rows) await wbImportBoardRows(rows);
      else toast("That PNG has no board inside it. Export a PNG with Include a copy of the diagram on, or insert it as a picture.", "info");
      return;
    }
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

//: It watches the board canvas, built when a board first opens (row 21).
onSurface("board", function wbThumbWatch() {
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
});

// --- A live Mermaid diagram (INBOX 1451) -----------------------------------
//
// The owner: "allow mermaid diagrams to actually be added as objects like
// with draw.io into the whiteboard". An object of kind `diagram` keeps its
// source (`data.mermaid`) and nothing drawn: the notes' own hidden frame
// (mermaid-draw.js, loaded only when a board has one) draws it, so a theme
// change redraws it and an edit is one Save. Double-click edits it in the block builder; "Turn
// into shapes" (in its menu) hands the source to `wbImportMermaid` for editable shapes.


//: The drawing already made for this item's source in the theme in force, as
//: an image address, or "": export and the thumbnail are synchronous.
//: The look a diagram object stored (INBOX 1486): its fill colour (`bg`), the
//: fill's opacity (`bg_alpha`) and the line's (`line_alpha`); null when it
//: stored none, which draws as every diagram always did.
function wbDiagramLook(obj) {
  const x = obj?.data || {};
  const look = {};
  if (x.bg && x.bg !== "transparent") look.fill = x.bg;
  if (x.bg_alpha != null) look.fillAlpha = x.bg_alpha;
  if (x.line_alpha != null) look.lineAlpha = x.line_alpha;
  return Object.keys(look).length ? look : null;
}

//: The colour and the strength a diagram's fill shows when it stored none,
//: for the Format panel's Fill row and slider: the accent at the default share.
function wbDiagramFillColour(data) {
  if (data?.bg && data.bg !== "transparent") return data.bg;
  const accent = wbHexColour(getComputedStyle(document.documentElement).getPropertyValue("--accent").trim());
  return accent || "#4664f0";
}

function wbDiagramFillShare() {
  const strong = document.documentElement.dataset.contrast === "on";
  //: The same two numbers as mermaid-draw.js `mermaidFillShare`, read here without loading that lazy module.
  return strong ? 0.28 : 0.16;
}

function wbDiagramDataUrl(obj) {
  const known = typeof mermaidKnown === "function" ? mermaidKnown(obj?.data?.mermaid || "", wbDiagramLook(obj)) : null;
  return known?.svg ? `data:image/svg+xml;charset=utf-8,${encodeURIComponent(known.svg)}` : "";
}

function wbBuildDiagram(el, d) {
  el.attr("role", "img").on("dblclick", (event) => {
    event.stopPropagation();
    if (!wbIsLocked("object", d)) wbEditDiagram(d);
  });
}

//: Draws the source once per source and theme; a mistake shows the parser's
//: one line in the box instead of a broken picture.
function wbPaintDiagram(node, d) {
  const source = d.data?.mermaid || "";
  node.setAttribute("aria-label", `Mermaid ${wbMermaidKind(source) || ""} diagram`.replace("  ", " "));
  //: 1621 D3, the snapshot rule: a linked diagram redraws from its Library row and rewrites `data.mermaid`
  //: as an ordinary silent save when they differ; a row that is gone draws the snapshot and says so.
  if (d.data?.diagram_id && !node._wbRow) {
    node._wbRow = apiJson(`/documents/${d.data.diagram_id}`, { silent: true }).then((row) => {
      const text = String(row?.content || "").trim();
      if (row?.file_type !== "mmd" || !text || text === source.trim()) return;
      d.data = { ...d.data, mermaid: text };
      wbSaveObject(d);
      wbPaintDiagram(node, d);
    }, (error) => {
      if (error?.status !== 404) return;
      d._wbGone = true;
      node.setAttribute("title", "The linked diagram was deleted");
      wbAnnounce("The linked diagram was deleted");
    });
  }
  ensureModule("mermaid").then(() => {
    const key = `${source}\u0000${mermaidThemeNow(wbDiagramLook(d)).key}`;
    if (node._wbDiagramKey === key) return;
    node._wbDiagramKey = key;
    mermaidRequest(source, wbDiagramLook(d)).then((result) => {
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

async function wbInsertDiagram(source, diagramId = null) {
  const [cx, cy] = wbViewCentre();
  const { width, height } = await wbDiagramSize(source);
  const made = await wbCreateObject("diagram", { mermaid: source, ...(diagramId ? { diagram_id: diagramId } : {}) }, cx - width / 2, cy - height / 2, width, height);
  if (!made) return null;
  clearWbSelection();
  wbHandleItemClick("object", made.id, { shiftKey: false });
  wbAnnounce("Diagram added. Double-click it to change it.");
  return made;
}

//: Insert opens the builder on a sample; a double-click opens it on an item (1546 D6: the one block
//: editor, in a dialog; the textarea dialog this was is gone). Done saves, Cancel changes nothing.
async function wbEditDiagram(d = null) {
  //: Insert asks first (R12, owner 2026-11-12): a diagram already made lands linked to its document at once, "New diagram" opens the empty builder.
  if (!d) {
    const pick = await chooseDiagram({ verb: "Insert" });
    if (!pick) return;
    if (pick !== true) {
      const row = await apiJson(`/documents/${pick.id}`).catch(() => null);
      return row ? wbInsertDiagram(String(row.content || "").trim(), pick.id) : toast("That diagram did not open. Try again.", "info");
    }
  }
  openDiagramBuilder({
    source: d?.data?.mermaid || "",
    title: d ? "Edit diagram" : "Diagram builder",
    draft: d ? `board:${d.id}` : "board-new",
    shapes: d ? (source) => (wbMermaidKind(source) ? wbDiagramToShapes(d, source) : toast("Shapes cover flowchart, state, class and sequence diagrams.")) : null,
    //: Save to Library (R9c).
    offer: d && { link: d },
    onDone: (source, changed) => wbSaveDiagram(d, source, changed),
  });
}

//: A diagram opened and closed with no change is not saved at all, so its source stays byte for byte.
async function wbSaveDiagram(d, source, changed) {
  const text = String(source).trim();
  if (d && !changed) return;
  if (!text) return toast("Write the diagram first, or Cancel.");
  if (!d) return wbInsertDiagram(text);
  if (text === d.data?.mermaid) return;
  wbPushUndo({ action: "move", kind: "object", id: d.id, before: WB_KIND_INFO.object.payload(d) });
  //: The new drawing's own shape, about the box's centre.
  const fit = await wbDiagramSize(text);
  d.data = { ...d.data, mermaid: text };
  //: A live link writes the row too, or the next redraw would put the old source back.
  if (d._wbGone) delete d.data.diagram_id;
  else if (d.data.diagram_id) await apiJson(`/documents/${d.data.diagram_id}`, { method: "PUT", body: JSON.stringify({ content: text }), silent: true }).catch(() => { d._wbGone = true; delete d.data.diagram_id; });
  Object.assign(d, { x: Math.round(d.x + (d.width - fit.width) / 2), y: Math.round(d.y + (d.height - fit.height) / 2) }, fit);
  await wbSaveObject(d);
  wbScheduleRender();
  wbAnnounce("Diagram saved.");
}

//: Editable shapes where the diagram stood, as one Undo step.
async function wbDiagramToShapes(d, source) {
  await wbRecordGesture(async () => {
    const made = await wbImportMermaid(source, [d.x + d.width / 2, d.y + d.height / 2]);
    if (made) await wbDeleteObject(d);
  });
}

//: **A PDF written here, not by the browser's print window** (LEDGER L270).
//: The old export opened Print and left the page size, the orientation and
//: the page count to whatever the print dialog chose, so a board came out as
//: one shrunken page. This writes the file itself: `wbPdf.plan` decides the
//: pages (fit on one, one per frame, or tiled across several), `wbExportPdf`
//: (whiteboard.js) draws each page from the export SVG as a JPEG, and
//: `wbPdf.build` wraps the JPEGs in a minimal PDF 1.4 (catalog, page tree, and
//: per page a page, a content stream and a DCT image, then an xref table). No
//: library: nothing vendored writes PDF, and a page of one picture is a dozen
//: lines of structure.
const wbPdf = (() => {
  //: Every paper size, in points (short side, long side), A4 the fallback: the one table the PDF export, the board's
  //: paper setting and the page view all read.
  const SIZES = { a4: [595.28, 841.89], a3: [841.89, 1190.55], letter: [612, 792], legal: [612, 1008] };
  const MM = 72 / 25.4;
  //: A paper's short and long side in points: a known size, or a board's custom one (`paper_w`, `paper_h`, millimetres).
  function sideOf(size, custom) {
    if (size === "custom" && custom?.paper_w > 0 && custom?.paper_h > 0) {
      return [custom.paper_w * MM, custom.paper_h * MM].sort((a, b) => a - b);
    }
    return SIZES[size] || SIZES.a4;
  }
  const MARGIN = 28;
  const TILE_SCALE = 0.75;
  const MAX_PAGES = 40;

  //: A board's page in board units (96 to the inch; the table is in points): its paper and orientation, A4 portrait
  //: when it sets none. Page view draws these frames.
  function pagePx(bg = {}) {
    const [short, long] = sideOf(bg.paper, bg);
    const [w, h] = bg.orientation === "landscape" ? [long, short] : [short, long];
    return [Math.round((w * 96) / 72), Math.round((h * 96) / 72)];
  }

  //: The pages for a board: `bounds` is the export's viewBox ({x, y, w, h}),
  //: `frames` the frames to give a page each ({x, y, width, height}). Every page
  //: has its size in points, the part of the board it shows (`crop`, board
  //: units) and where that sits on the page (`place`, points, from the top-left).
  function plan({ bounds, frames = [], size = "a4", orientation = "auto", layout = "fit", custom = null }) {
    const [short, long] = sideOf(size, custom);
    const pageFor = (w, h) => {
      const landscape = orientation === "landscape" || (orientation === "auto" && w > h);
      return landscape ? [long, short] : [short, long];
    };
    const clip = (r) => {
      const x = Math.max(bounds.x, r.x), y = Math.max(bounds.y, r.y);
      const w = Math.min(bounds.x + bounds.w, r.x + r.w) - x, h = Math.min(bounds.y + bounds.h, r.y + r.h) - y;
      return w > 0 && h > 0 ? { x, y, w, h } : null;
    };
    const fitPage = (crop) => {
      const [pw, ph] = pageFor(crop.w, crop.h);
      const cw = pw - 2 * MARGIN, ch = ph - 2 * MARGIN;
      const k = Math.min(cw / crop.w, ch / crop.h);
      const w = crop.w * k, h = crop.h * k;
      return { page: [pw, ph], crop, place: { x: (pw - w) / 2, y: (ph - h) / 2, w, h } };
    };
    if (layout === "frames") {
      //: Reading order: rows of frames top to bottom, each row left to right.
      const crops = frames
        .map((f) => clip({ x: f.x - 12, y: f.y - 28, w: f.width + 24, h: f.height + 40 }))
        .filter(Boolean)
        .sort((a, b) => (Math.abs(a.y - b.y) > 40 ? a.y - b.y : a.x - b.x));
      if (crops.length) return crops.slice(0, MAX_PAGES).map(fitPage);
    }
    if (layout === "tiles") {
      const [pw, ph] = pageFor(bounds.w, bounds.h);
      const cw = pw - 2 * MARGIN, ch = ph - 2 * MARGIN;
      let scale = TILE_SCALE;
      while (Math.ceil((bounds.w * scale) / cw) * Math.ceil((bounds.h * scale) / ch) > MAX_PAGES) scale *= 0.8;
      const tw = cw / scale, th = ch / scale;
      const pages = [];
      for (let y = bounds.y; y < bounds.y + bounds.h - 0.5; y += th) {
        for (let x = bounds.x; x < bounds.x + bounds.w - 0.5; x += tw) {
          const crop = { x, y, w: Math.min(tw, bounds.x + bounds.w - x), h: Math.min(th, bounds.y + bounds.h - y) };
          pages.push({ page: [pw, ph], crop, place: { x: MARGIN, y: MARGIN, w: crop.w * scale, h: crop.h * scale } });
        }
      }
      return pages;
    }
    return [fitPage({ ...bounds })];
  }

  //: The file: `pages` are `{page: [w, h], place: {x, y, w, h}, image: {jpeg: Uint8Array, w, h}}`.
  function build(pages) {
    const enc = new TextEncoder();
    const chunks = [];
    const offsets = [];
    let length = 0;
    const put = (part) => {
      const bytes = typeof part === "string" ? enc.encode(part) : part;
      chunks.push(bytes);
      length += bytes.length;
    };
    const num = (n) => String(Math.round(n * 100) / 100);
    const object = (id, ...parts) => {
      offsets[id] = length;
      put(`${id} 0 obj\n`);
      for (const part of parts) put(part);
      put("\nendobj\n");
    };
    put("%PDF-1.4\n");
    object(1, "<< /Type /Catalog /Pages 2 0 R >>");
    object(2, `<< /Type /Pages /Kids [${pages.map((_, i) => `${3 + 3 * i} 0 R`).join(" ")}] /Count ${pages.length} >>`);
    pages.forEach((p, i) => {
      const id = 3 + 3 * i;
      const [w, h] = p.page;
      const { x, y, w: pw, h: ph } = p.place;
      const draw = `q ${num(pw)} 0 0 ${num(ph)} ${num(x)} ${num(h - y - ph)} cm /Im0 Do Q`;
      object(id, `<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${num(w)} ${num(h)}] /Resources << /XObject << /Im0 ${id + 2} 0 R >> >> /Contents ${id + 1} 0 R >>`);
      object(id + 1, `<< /Length ${draw.length} >>\nstream\n${draw}\nendstream`);
      object(id + 2, `<< /Type /XObject /Subtype /Image /Width ${p.image.w} /Height ${p.image.h} /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length ${p.image.jpeg.length} >>\nstream\n`, p.image.jpeg, "\nendstream");
    });
    const total = 3 + 3 * pages.length;
    const xref = length;
    put(`xref\n0 ${total}\n0000000000 65535 f \n`);
    for (let id = 1; id < total; id++) put(`${String(offsets[id]).padStart(10, "0")} 00000 n \n`);
    put(`trailer\n<< /Size ${total} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`);
    const out = new Uint8Array(length);
    let at = 0;
    for (const chunk of chunks) {
      out.set(chunk, at);
      at += chunk.length;
    }
    return out;
  }

  //: The choices the export dialog offers, and the last ones made.
  const CHOICES = {
    size: [{ value: "a4", label: "A4" }, { value: "a3", label: "A3" }, { value: "letter", label: "Letter" }, { value: "legal", label: "Legal" }],
    orientation: [
      { value: "auto", label: "Auto", title: "Landscape for a wide board, portrait for a tall one" },
      { value: "portrait", label: "Portrait" },
      { value: "landscape", label: "Landscape" },
    ],
    layout: [
      { value: "fit", label: "One page", title: "The whole export scaled onto one page" },
      { value: "frames", label: "Per frame", title: "One page for each frame, in reading order" },
      { value: "tiles", label: "Tiled", title: "Full-size pages side by side across the board" },
    ],
  };
  function savedChoice() {
    const saved = prefs.json("wb-export-pdf", {});
    const pick = (key, fallback) => (CHOICES[key].some((o) => o.value === saved[key]) ? saved[key] : fallback);
    return { size: pick("size", "a4"), orientation: pick("orientation", "auto"), layout: pick("layout", "fit") };
  }

  //: The export dialog's starting point: the board's own paper and direction when it sets them (Format > Board), else
  //: the last choice made here. A custom paper carries its millimetres along for the plan.
  function boardChoice(bg, saved) {
    const out = { ...saved };
    if (bg.paper) {
      out.size = bg.paper;
      if (bg.paper === "custom") out.custom = { paper_w: bg.paper_w, paper_h: bg.paper_h };
    }
    if (bg.orientation) out.orientation = bg.orientation;
    return out;
  }

  function saveChoice(choice) {
    try {
      const { size, orientation, layout } = choice;
      prefs.set("wb-export-pdf", JSON.stringify({ size, orientation, layout }));
    } catch {
      // Private mode: the choice holds for this export.
    }
  }

  //: The frames that get a page in "Per frame": those in the export's scope.
  function framesIn(scope, bounds) {
    const onlyKeys = scope === "selection" ? wbSelectedKeys() : null;
    return (wbState.objects || []).filter((f) =>
      f.kind === "frame" && !wbItemHidden("object", f) &&
      (!onlyKeys || onlyKeys.has(wbMultiKey("object", f.id))) &&
      f.x < bounds.x + bounds.w && f.x + f.width > bounds.x && f.y < bounds.y + bounds.h && f.y + f.height > bounds.y);
  }

  //: The pages of a PDF, drawn from the export SVG: each page is the same
  //: picture with its viewBox moved to that page's part of the board.
  async function pictures(scope, choice) {
    const { svg } = wbBuildExportSvg(scope);
    const box = /viewBox="(-?[\d.]+) (-?[\d.]+) ([\d.]+) ([\d.]+)"/.exec(svg);
    const bounds = { x: Number(box[1]), y: Number(box[2]), w: Number(box[3]), h: Number(box[4]) };
    const pages = [];
    const inlined = await wbInlineSvgImages(svg);
    for (const p of plan({ bounds, frames: framesIn(scope, bounds), ...choice })) {
      //: About 216 dpi on paper, held to what a canvas will hold.
      const w = Math.min(3000, Math.max(1, Math.round(p.place.w * 3)));
      const h = Math.max(1, Math.round((w * p.place.h) / p.place.w));
      const crop = inlined.replace(/viewBox="[^"]*"/, `viewBox="${p.crop.x} ${p.crop.y} ${p.crop.w} ${p.crop.h}"`);
      const blob = await wbRasterizeSvg(crop, w, h, "image/jpeg", 0.92);
      pages.push({ ...p, image: { jpeg: new Uint8Array(await blob.arrayBuffer()), w, h } });
    }
    return pages;
  }

  return { plan, build, pictures, choices: CHOICES, savedChoice, saveChoice, boardChoice, SIZES, pagePx };
})();
