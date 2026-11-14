(() => {
  // whiteboard-layouts-more.js: draw.io's Arrange > Layout menu for a board (WHITEBOARD_PLAN section 16) and the
  // stack layout on lanes (section 12). Flow (a layered layout: rank by longest path, order by the barycentre,
  // then coordinates), a radial tree, an org chart (leaves stacked under their manager), an organic force pass
  // with a fixed seed and step count, and a circle. The vertical and horizontal trees are the older Tidy
  // commands (`wbTidySelection`). The layout functions are pure: they take boxes and pairs of keys and return
  // top-left corners, so a node test runs them without a board.

  //: Between two boxes, in board units; a dummy point on a long edge keeps a thinner berth.
  const GAP = 48;
  const DUMMY_GAP = 12;
  //: Rows of an org chart's stacked leaves sit closer than ranks do, and hang this far right of the manager.
  const STACK_GAP = 16;
  const INDENT = 28;
  const SEED = 20241112;
  const STEPS = 250;

  const lmKeyOf = (kind, id) => `${kind || "node"}:${id}`;

  //: Seeded generator (mulberry32): the same numbers every run, so the organic layout is the same every run.
  function lmSeeded(seed) {
    let a = seed >>> 0;
    return () => {
      a = (a + 0x6d2b79f5) >>> 0;
      let t = a;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  //: Adjacency by index, a pair seen twice or pointing at itself dropped, in input order.
  function lmAdjacency(nodes, edges) {
    const index = new Map(nodes.map((n, i) => [n.key, i]));
    const out = nodes.map(() => []), inn = nodes.map(() => []);
    const seen = new Set();
    for (const [a, b] of edges) {
      const i = index.get(a), j = index.get(b);
      if (i == null || j == null || i === j || seen.has(`${i}>${j}`)) continue;
      seen.add(`${i}>${j}`);
      out[i].push(j);
      inn[j].push(i);
    }
    return { index, out, inn };
  }

  function lmExtent(nodes) {
    return {
      minX: Math.min(...nodes.map((n) => n.x)), minY: Math.min(...nodes.map((n) => n.y)),
      maxX: Math.max(...nodes.map((n) => n.x + n.w)), maxY: Math.max(...nodes.map((n) => n.y + n.h)),
    };
  }

  //: Moves a set of top-left corners (a Map key -> {x, y}) so the group's top-left corner is where the input's was.
  function lmAnchorTopLeft(nodes, pos) {
    const was = lmExtent(nodes);
    const minX = Math.min(...[...pos].map(([, p]) => p.x)), minY = Math.min(...[...pos].map(([, p]) => p.y));
    for (const p of pos.values()) {
      p.x = Math.round(p.x - minX + was.minX);
      p.y = Math.round(p.y - minY + was.minY);
    }
    return pos;
  }

  //: The same for a layout that grows from a middle: the group's centre stays where it was.
  function lmAnchorCentre(nodes, pos) {
    const was = lmExtent(nodes);
    const size = new Map(nodes.map((n) => [n.key, n]));
    const now = lmExtent([...pos].map(([key, p]) => ({ x: p.x, y: p.y, w: size.get(key).w, h: size.get(key).h })));
    const dx = (was.minX + was.maxX) / 2 - (now.minX + now.maxX) / 2, dy = (was.minY + was.maxY) / 2 - (now.minY + now.maxY) / 2;
    for (const p of pos.values()) {
      p.x = Math.round(p.x + dx);
      p.y = Math.round(p.y + dy);
    }
    return pos;
  }

  // --- Flow: a layered layout -------------------------------------------------------------------------------------

  //: The edges with every cycle broken: a depth-first walk from the nodes nothing points into (then the rest, in
  //: input order) turns the edge that closes a loop around. Returns [from, to] index pairs, each once.
  function lmAcyclic(n, out, inn) {
    const state = new Array(n).fill(0);
    const seen = new Set();
    const edges = [];
    const add = (u, v) => {
      if (seen.has(`${u}>${v}`) || seen.has(`${v}>${u}`)) return;
      seen.add(`${u}>${v}`);
      edges.push([u, v]);
    };
    const visit = (u) => {
      state[u] = 1;
      for (const v of out[u]) {
        if (state[v] === 1) add(v, u);
        else {
          add(u, v);
          if (state[v] === 0) visit(v);
        }
      }
      state[u] = 2;
    };
    const order = [...Array(n).keys()];
    for (const u of [...order.filter((i) => !inn[i].length), ...order]) if (state[u] === 0) visit(u);
    return edges;
  }

  //: Crossings between two neighbouring layers: pairs of edges whose ends are in opposite order.
  function lmLayerCrossings(pairs) {
    let count = 0;
    for (let i = 0; i < pairs.length; i++) for (let j = i + 1; j < pairs.length; j++) {
      const [a, b] = pairs[i], [c, d] = pairs[j];
      if ((a - c) * (b - d) < 0) count++;
    }
    return count;
  }

  //: Pure: the flow layout. `dir` is "down" (ranks run top to bottom) or "right". Ranks by the longest path from a
  //: source, long edges carry a dummy point per rank crossed, the order inside a rank is swept by the barycentre
  //: of the neighbours (the best of twenty-four sweeps by crossings, the board's own order breaking ties), and the
  //: coordinates pull each point toward its neighbours' middle without letting two boxes touch.
  function lmFlow(nodes, edges, { dir = "down", gap = GAP } = {}) {
    const n = nodes.length;
    const { out, inn } = lmAdjacency(nodes, edges);
    const dag = lmAcyclic(n, out, inn);
    const down = dir === "down";
    const breadth = (i) => (i < n ? (down ? nodes[i].w : nodes[i].h) : 0);
    const thick = (i) => (i < n ? (down ? nodes[i].h : nodes[i].w) : 0);
    const along = nodes.map((nd) => (down ? nd.x + nd.w / 2 : nd.y + nd.h / 2));
    // Longest path rank, in topological order.
    const into = new Array(n).fill(0);
    const next = nodes.map(() => []);
    for (const [u, v] of dag) { next[u].push(v); into[v]++; }
    const rank = new Array(n).fill(0);
    const queue = [...Array(n).keys()].filter((i) => !into[i]);
    for (let q = 0; q < queue.length; q++) {
      const u = queue[q];
      for (const v of next[u]) {
        rank[v] = Math.max(rank[v], rank[u] + 1);
        if (--into[v] === 0) queue.push(v);
      }
    }
    // Dummy points on edges that span more than one rank.
    const pos0 = along.slice();
    const rankOf = rank.slice();
    const segments = [];
    for (const [u, v] of dag) {
      let prev = u;
      for (let r = rank[u] + 1; r < rank[v]; r++) {
        const id = rankOf.length;
        rankOf.push(r);
        pos0.push(along[u] + ((along[v] - along[u]) * (r - rank[u])) / (rank[v] - rank[u]));
        segments.push([prev, id]);
        prev = id;
      }
      segments.push([prev, v]);
    }
    const total = rankOf.length;
    const layers = [];
    for (let i = 0; i < total; i++) (layers[rankOf[i]] ||= []).push(i);
    for (const layer of layers) layer.sort((a, b) => pos0[a] - pos0[b] || a - b);
    const ups = Array.from({ length: total }, () => []), downs = Array.from({ length: total }, () => []);
    for (const [u, v] of segments) { downs[u].push(v); ups[v].push(u); }
    const place = new Array(total).fill(0);
    const index = () => layers.forEach((layer) => layer.forEach((v, i) => { place[v] = i; }));
    const crossings = () => {
      let sum = 0;
      for (let r = 0; r + 1 < layers.length; r++) sum += lmLayerCrossings(layers[r].flatMap((u) => downs[u].map((v) => [place[u], place[v]])));
      return sum;
    };
    index();
    let best = layers.map((l) => l.slice()), bestCount = crossings();
    for (let sweep = 0; sweep < 24 && bestCount > 0; sweep++) {
      const forward = sweep % 2 === 0;
      const order = forward ? [...layers.keys()].slice(1) : [...layers.keys()].slice(0, -1).reverse();
      for (const r of order) {
        const links = forward ? ups : downs;
        const bary = new Map(layers[r].map((v, i) => [v, links[v].length ? links[v].reduce((s, w) => s + place[w], 0) / links[v].length : i]));
        layers[r].sort((a, b) => bary.get(a) - bary.get(b) || place[a] - place[b]);
        layers[r].forEach((v, i) => { place[v] = i; });
      }
      const count = crossings();
      if (count < bestCount) { bestCount = count; best = layers.map((l) => l.slice()); }
    }
    for (let r = 0; r < layers.length; r++) layers[r] = best[r];
    index();
    // Coordinates: ranks stacked by their thickest box; inside a rank, boxes side by side, then pulled toward
    // the middle of their neighbours (the average of a left-to-right and a right-to-left squeeze stays legal).
    const sep = (a, b) => (breadth(a) + breadth(b)) / 2 + (a < n && b < n ? gap : DUMMY_GAP);
    const centre = new Array(total).fill(0);
    for (const layer of layers) {
      let at = 0;
      layer.forEach((v, i) => {
        if (i) at += sep(layer[i - 1], v);
        centre[v] = at;
      });
      const mid = (centre[layer[0]] + centre[layer[layer.length - 1]]) / 2;
      for (const v of layer) centre[v] -= mid;
    }
    const squeeze = (layer, want) => {
      const lo = [], hi = [];
      layer.forEach((v, i) => { lo[i] = Math.max(want.get(v), i ? lo[i - 1] + sep(layer[i - 1], v) : -Infinity); });
      for (let i = layer.length - 1; i >= 0; i--) hi[i] = Math.min(want.get(layer[i]), i < layer.length - 1 ? hi[i + 1] - sep(layer[i], layer[i + 1]) : Infinity);
      layer.forEach((v, i) => { centre[v] = (lo[i] + hi[i]) / 2; });
    };
    for (let pass = 0; pass < 8; pass++) {
      const forward = pass % 2 === 0;
      const order = forward ? [...layers.keys()].slice(1) : [...layers.keys()].slice(0, -1).reverse();
      for (const r of order) {
        const links = forward ? ups : downs;
        squeeze(layers[r], new Map(layers[r].map((v) => [v, links[v].length ? links[v].reduce((s, w) => s + centre[w], 0) / links[v].length : centre[v]])));
      }
    }
    let start = 0;
    const row = layers.map((layer) => {
      const t = Math.max(0, ...layer.map(thick));
      const at = start;
      start += t + gap * 1.5;
      return { at, t };
    });
    const pos = new Map();
    nodes.forEach((nd, i) => {
      const { at, t } = row[rank[i]];
      const lead = at + (t - thick(i)) / 2;
      pos.set(nd.key, down ? { x: centre[i] - nd.w / 2, y: lead } : { x: lead, y: centre[i] - nd.h / 2 });
    });
    return lmAnchorTopLeft(nodes, pos);
  }

  // --- Trees: radial and org chart ---------------------------------------------------------------------------------

  //: The forest the connectors make: a box nothing points into is a root, children keep their board order along
  //: `axis`, and anything a loop left unreached starts a tree of its own. Returns { roots, kids } by index.
  function lmForest(nodes, edges, axis) {
    const { out, inn } = lmAdjacency(nodes, edges);
    const at = (i) => (axis === "x" ? nodes[i].x : nodes[i].y);
    const order = [...Array(nodes.length).keys()].sort((a, b) => at(a) - at(b) || a - b);
    const seen = new Set();
    const kids = nodes.map(() => []);
    const roots = [];
    const walk = (u) => {
      seen.add(u);
      const mine = out[u].filter((v) => !seen.has(v)).sort((a, b) => at(a) - at(b) || a - b);
      mine.forEach((v) => seen.add(v));
      kids[u] = mine;
      mine.forEach(walk);
    };
    for (const u of [...order.filter((i) => !inn[i].length), ...order]) if (!seen.has(u)) { roots.push(u); walk(u); }
    return { roots, kids };
  }

  //: Pure: a radial tree. The roots sit at the middle (a lone root is the middle itself), each depth is a ring,
  //: and a subtree gets an arc as wide as its leaves are many. A ring is as far out as its closest pair of
  //: neighbours needs so no two boxes touch: every centre is at least one box diagonal from every other.
  function lmRadial(nodes, edges, { gap = GAP } = {}) {
    const n = nodes.length;
    const { roots, kids } = lmForest(nodes, edges, "x");
    const diag = Math.hypot(Math.max(...nodes.map((nd) => nd.w)), Math.max(...nodes.map((nd) => nd.h))) + gap;
    const lone = roots.length === 1;
    const top = lone ? roots[0] : -1;
    const level = (u) => (u === -1 ? roots : kids[u]);
    const leaves = new Map();
    const count = (u) => {
      const c = level(u).reduce((s, v) => s + count(v), 0) || 1;
      leaves.set(u, c);
      return c;
    };
    count(top);
    const angle = new Map(), depth = new Map();
    const rings = [];
    const span = (u, from, to, d) => {
      angle.set(u, (from + to) / 2);
      depth.set(u, d);
      if (u !== -1) (rings[d] ||= []).push(u);
      let a = from;
      for (const v of level(u)) {
        const share = ((to - from) * leaves.get(v)) / leaves.get(u);
        span(v, a, a + share, d + 1);
        a += share;
      }
    };
    span(top, 0, Math.PI * 2, 0);
    const radius = [0];
    for (let d = 1; d < rings.length; d++) {
      const list = rings[d].slice().sort((a, b) => angle.get(a) - angle.get(b));
      let need = radius[d - 1] + diag;
      for (let i = 0; i < (list.length > 1 ? list.length : 0); i++) {
        const a = angle.get(list[i]), b = angle.get(list[(i + 1) % list.length]);
        const step = i === list.length - 1 ? Math.PI * 2 - (a - b) : b - a;
        need = Math.max(need, diag / (2 * Math.sin(Math.min(Math.max(step, 1e-3), Math.PI) / 2)));
      }
      radius[d] = need;
    }
    const pos = new Map();
    for (let i = 0; i < n; i++) {
      const d = depth.get(i), r = radius[d] || 0, a = angle.get(i) - Math.PI / 2;
      pos.set(nodes[i].key, { x: Math.cos(a) * r - nodes[i].w / 2, y: Math.sin(a) * r - nodes[i].h / 2 });
    }
    return lmAnchorCentre(nodes, pos);
  }

  //: Pure: an org chart. A tree top to bottom with a manager centred over the reports that have reports of their
  //: own; reports with none (leaves) are stacked in one column under their manager, hanging a little to the right
  //: of it when they are all it has, and are the first block of the row when it has others. Each subtree takes
  //: the room its widest row needs, so no two boxes touch.
  function lmOrg(nodes, edges, { gap = GAP } = {}) {
    const { roots, kids } = lmForest(nodes, edges, "x");
    const info = new Map();
    const measure = (u) => {
      const leaf = kids[u].filter((v) => !kids[v].length);
      const column = leaf.length >= 2 ? leaf : [];
      const rest = kids[u].filter((v) => !column.includes(v));
      rest.forEach(measure);
      const blocks = [];
      if (column.length) blocks.push({ column, b: Math.max(...column.map((v) => nodes[v].w)), t: column.reduce((s, v) => s + nodes[v].h, 0) + STACK_GAP * (column.length - 1) });
      for (const v of rest) blocks.push({ node: v, b: info.get(v).b, t: info.get(v).t });
      const row = blocks.reduce((s, blk) => s + blk.b, 0) + gap * Math.max(0, blocks.length - 1);
      const hang = blocks.length === 1 && column.length ? INDENT : 0;
      const own = nodes[u].w;
      info.set(u, {
        blocks, hang, rest, b: Math.max(own, row + hang), t: nodes[u].h + (blocks.length ? gap * 1.5 + Math.max(...blocks.map((blk) => blk.t)) : 0), row,
      });
    };
    roots.forEach(measure);
    const pos = new Map();
    const place = (u, left, top) => {
      const m = info.get(u);
      const nd = nodes[u];
      // A manager over a lone column sits at the block's left; otherwise it is centred over its children.
      const x = m.hang ? left : left + (m.b - nd.w) / 2;
      pos.set(nd.key, { x, y: top });
      let at = m.hang ? left + m.hang : left + (m.b - m.row) / 2;
      const y = top + nd.h + gap * 1.5;
      for (const blk of m.blocks) {
        if (blk.column) {
          let row = y;
          for (const v of blk.column) {
            pos.set(nodes[v].key, { x: at, y: row });
            row += nodes[v].h + STACK_GAP;
          }
        } else place(blk.node, at, y);
        at += blk.b + gap;
      }
    };
    let at = 0;
    for (const r of roots) {
      place(r, at, 0);
      at += info.get(r).b + gap;
    }
    return lmAnchorTopLeft(nodes, pos);
  }

  // --- Organic and circle ------------------------------------------------------------------------------------------

  //: Pure: how many pairs of boxes overlap (touching edges do not count).
  function lmOverlapCount(boxes) {
    let c = 0;
    for (let i = 0; i < boxes.length; i++) for (let j = i + 1; j < boxes.length; j++) {
      const a = boxes[i], b = boxes[j];
      if (a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h) c++;
    }
    return c;
  }

  //: Pure: a force pass (Fruchterman and Reingold): every pair pushes apart, every connector pulls together, a
  //: cooling step limits the move. The start is a seeded ring, so the same graph gives the same picture. A last
  //: pass pushes any boxes that still touch apart, and if some still do the whole picture is spread until none do.
  function lmOrganic(nodes, edges, { gap = GAP, steps = STEPS, seed = SEED } = {}) {
    const n = nodes.length;
    const { out } = lmAdjacency(nodes, edges);
    const diag = Math.hypot(Math.max(...nodes.map((nd) => nd.w)), Math.max(...nodes.map((nd) => nd.h))) + gap;
    const k = diag * 1.3;
    const rnd = lmSeeded(seed);
    const p = nodes.map((_, i) => {
      const a = (Math.PI * 2 * i) / n, r = (k * Math.sqrt(n)) / 2;
      return { x: Math.cos(a) * r + (rnd() - 0.5) * k * 0.2, y: Math.sin(a) * r + (rnd() - 0.5) * k * 0.2 };
    });
    let heat = (k * Math.sqrt(n)) / 3;
    for (let s = 0; s < steps; s++) {
      const move = p.map(() => ({ x: 0, y: 0 }));
      for (let i = 0; i < n; i++) for (let j = i + 1; j < n; j++) {
        let dx = p[i].x - p[j].x, dy = p[i].y - p[j].y;
        let d = Math.hypot(dx, dy);
        if (d < 0.01) { dx = rnd() - 0.5; dy = rnd() - 0.5; d = Math.hypot(dx, dy) || 1; }
        const f = (k * k) / d;
        move[i].x += (dx / d) * f; move[i].y += (dy / d) * f;
        move[j].x -= (dx / d) * f; move[j].y -= (dy / d) * f;
      }
      for (let i = 0; i < n; i++) for (const j of out[i]) {
        const dx = p[i].x - p[j].x, dy = p[i].y - p[j].y, d = Math.hypot(dx, dy) || 1;
        const f = (d * d) / k;
        move[i].x -= (dx / d) * f; move[i].y -= (dy / d) * f;
        move[j].x += (dx / d) * f; move[j].y += (dy / d) * f;
      }
      for (let i = 0; i < n; i++) {
        move[i].x -= p[i].x * 0.05; move[i].y -= p[i].y * 0.05;
        const d = Math.hypot(move[i].x, move[i].y) || 1, cap = Math.min(d, heat);
        p[i].x += (move[i].x / d) * cap; p[i].y += (move[i].y / d) * cap;
      }
      heat *= 0.97;
    }
    const boxes = () => nodes.map((nd, i) => ({ x: p[i].x - nd.w / 2 - gap / 2, y: p[i].y - nd.h / 2 - gap / 2, w: nd.w + gap, h: nd.h + gap }));
    for (let pass = 0; pass < 60 && lmOverlapCount(boxes()) > 0; pass++) {
      const b = boxes();
      for (let i = 0; i < n; i++) for (let j = i + 1; j < n; j++) {
        const ox = Math.min(b[i].x + b[i].w, b[j].x + b[j].w) - Math.max(b[i].x, b[j].x), oy = Math.min(b[i].y + b[i].h, b[j].y + b[j].h) - Math.max(b[i].y, b[j].y);
        if (ox <= 0 || oy <= 0) continue;
        if (ox < oy) { const s = (p[i].x <= p[j].x ? -1 : 1) * (ox / 2 + 0.5); p[i].x += s; p[j].x -= s; }
        else { const s = (p[i].y <= p[j].y ? -1 : 1) * (oy / 2 + 0.5); p[i].y += s; p[j].y -= s; }
      }
    }
    for (let grow = 0; grow < 40 && lmOverlapCount(boxes()) > 0; grow++) for (const q of p) { q.x *= 1.15; q.y *= 1.15; }
    const pos = new Map(nodes.map((nd, i) => [nd.key, { x: p[i].x - nd.w / 2, y: p[i].y - nd.h / 2 }]));
    return lmAnchorCentre(nodes, pos);
  }

  //: Pure: a circle. Connected boxes sit next to each other round it (a walk along the connectors, the board's
  //: order choosing where each walk starts), on a radius where neighbours are a box diagonal apart.
  function lmCircle(nodes, edges, { gap = GAP } = {}) {
    const n = nodes.length;
    const { out, inn } = lmAdjacency(nodes, edges);
    const seen = new Set(), order = [];
    const byBoard = [...Array(n).keys()].sort((a, b) => nodes[a].x - nodes[b].x || nodes[a].y - nodes[b].y || a - b);
    for (const s of byBoard) {
      if (seen.has(s)) continue;
      seen.add(s);
      const queue = [s];
      for (let q = 0; q < queue.length; q++) {
        order.push(queue[q]);
        for (const v of [...out[queue[q]], ...inn[queue[q]]]) if (!seen.has(v)) { seen.add(v); queue.push(v); }
      }
    }
    const diag = Math.hypot(Math.max(...nodes.map((nd) => nd.w)), Math.max(...nodes.map((nd) => nd.h))) + gap;
    const r = n < 2 ? 0 : Math.max(diag / (2 * Math.sin(Math.PI / n)), 0);
    const pos = new Map();
    order.forEach((i, at) => {
      const a = -Math.PI / 2 + (Math.PI * 2 * at) / n;
      pos.set(nodes[i].key, { x: Math.cos(a) * r - nodes[i].w / 2, y: Math.sin(a) * r - nodes[i].h / 2 });
    });
    return lmAnchorCentre(nodes, pos);
  }

  //: Pure: how many pairs of connectors cross, drawn as straight lines between box centres. Two that share a box
  //: never count.
  function lmCrossingCount(nodes, pos, edges) {
    const mid = new Map(nodes.map((nd) => [nd.key, { x: (pos.get(nd.key)?.x ?? nd.x) + nd.w / 2, y: (pos.get(nd.key)?.y ?? nd.y) + nd.h / 2 }]));
    const lines = edges.filter(([a, b]) => a !== b && mid.has(a) && mid.has(b));
    const side = (a, b, c) => Math.sign((b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x));
    let count = 0;
    for (let i = 0; i < lines.length; i++) for (let j = i + 1; j < lines.length; j++) {
      const [a, b] = lines[i], [c, d] = lines[j];
      if (a === c || a === d || b === c || b === d) continue;
      const [p1, p2, p3, p4] = [mid.get(a), mid.get(b), mid.get(c), mid.get(d)];
      if (side(p1, p2, p3) * side(p1, p2, p4) < 0 && side(p3, p4, p1) * side(p3, p4, p2) < 0) count++;
    }
    return count;
  }

  //: A rack, like draw.io's `rackLayout`: the boxes in one column as wide as the widest, each in a slot a whole
  //: number of rack units tall (an item taller than a unit takes the next whole number), a gap between slots, each
  //: centred in its slot. Order is top to bottom, then left to right, as they lie now; the column's top left stays
  //: where the group's was. Edges play no part. Pure: boxes in, top-left corners out.
  const RACK_UNIT = 24;
  function lmRack(nodes, edges, { gap = DUMMY_GAP, unit = RACK_UNIT } = {}) {
    const order = [...nodes].sort((a, b) => a.y - b.y || a.x - b.x);
    const width = Math.max(0, ...nodes.map((nd) => nd.w));
    const left = Math.min(...nodes.map((nd) => nd.x));
    const top = Math.min(...nodes.map((nd) => nd.y));
    const pos = new Map();
    let y = top;
    for (const nd of order) {
      const slot = Math.max(1, Math.ceil(nd.h / unit)) * unit;
      pos.set(nd.key, { x: left + (width - nd.w) / 2, y: y + (slot - nd.h) / 2 });
      y += slot + gap;
    }
    return pos;
  }

  const KINDS = {
    rack: lmRack,
    "flow-h": (nodes, edges) => lmFlow(nodes, edges, { dir: "right" }),
    "flow-v": (nodes, edges) => lmFlow(nodes, edges, { dir: "down" }),
    radial: lmRadial,
    org: lmOrg,
    organic: lmOrganic,
    circle: lmCircle,
  };

  //: Pure: the top-left corner each box takes under the named layout (a Map key -> {x, y}).
  function lmArrange(kind, nodes, edges) {
    return KINDS[kind](nodes, edges);
  }

  // --- On a board --------------------------------------------------------------------------------------------------

  const NOUN = { "flow-h": "a flow, left to right", "flow-v": "a flow, top to bottom", radial: "a radial tree", org: "an org chart", organic: "an organic layout", circle: "a circle", rack: "a rack" };

  //: What a layout moves: the selected shapes, or every shape on the board when fewer than two are selected. Frames,
  //: connectors, locked and hidden things stay out.
  function lmLayoutEntries() {
    const ok = (e) => e.bbox && !wbIsLocked(e.kind, e.item) && !wbItemHidden(e.kind, e.item) && !(e.kind === "sketch" && wbIsLinkSketch(e.item)) && !(e.kind === "object" && e.item.kind === "frame");
    let entries = wbSelectionEntries().filter(ok);
    if (entries.length < 2) {
      entries = wbSelectableItems().map(([kind, item]) => ({ kind, id: item.id, item, bbox: wbItemBBox(kind, item) })).filter(ok);
    }
    return entries;
  }

  function lmCanLayout() {
    const entries = lmLayoutEntries();
    return entries.length >= 2 && wbTidyEdges(entries).length > 0;
  }

  //: A rack stacks what is selected (two or more, connectors or none), so a board with nothing selected is never
  //: swept into one by accident.
  function lmRackEntries() {
    return wbSelectionEntries().filter((e) => e.bbox && !wbIsLocked(e.kind, e.item) && !wbItemHidden(e.kind, e.item) && !(e.kind === "sketch" && wbIsLinkSketch(e.item)) && !(e.kind === "object" && e.item.kind === "frame"));
  }

  function lmCanRack() {
    return lmRackEntries().length >= 2;
  }

  //: One Undo step: the boxes move, and the connectors between them drop the bends and pinned ends they had, which
  //: described the old places, so each routes afresh from where its two boxes now are.
  async function lmApply(kind) {
    await ensureModule("boards");
    const rack = kind === "rack";
    const entries = rack ? lmRackEntries() : lmLayoutEntries();
    const edges = rack ? [] : wbTidyEdges(entries);
    if (rack && entries.length < 2) {
      toast("Select two or more things to stack them as a rack.");
      return 0;
    }
    if (!rack && (entries.length < 2 || !edges.length)) {
      toast("Join two or more shapes with connectors to lay them out.");
      return 0;
    }
    const nodes = entries.map((e) => ({ key: lmKeyOf(e.kind, e.id), x: e.bbox.minX, y: e.bbox.minY, w: e.bbox.maxX - e.bbox.minX, h: e.bbox.maxY - e.bbox.minY }));
    const pos = lmArrange(kind, nodes, edges);
    const keys = new Set(nodes.map((nd) => nd.key));
    await wbRecordGesture(async () => {
      const rows = [];
      for (const e of entries) {
        const at = pos.get(lmKeyOf(e.kind, e.id));
        const dx = at.x - e.bbox.minX, dy = at.y - e.bbox.minY;
        if (Math.abs(dx) < 0.5 && Math.abs(dy) < 0.5) continue;
        wbMoveItemBy(e.kind, e.id, e.item, dx, dy, rows);
      }
      for (const sketch of wbState.sketches || []) {
        if (!wbIsLinkSketch(sketch)) continue;
        const data = wbSketchData(sketch);
        if (!keys.has(lmKeyOf(data.sourceKind, data.sourceId)) || !keys.has(lmKeyOf(data.targetKind, data.targetId))) continue;
        if (wbSketchSetProps(sketch, { points: undefined, bend: undefined, sourceAnchor: undefined, targetAnchor: undefined })) rows.push({ kind: "sketch", item: sketch });
      }
      await wbSaveMany(rows);
    });
    wbScheduleRender();
    const said = `Laid out ${nounCount(entries.length, "shape")} as ${NOUN[kind]}.`;
    wbAnnounce(said);
    toast(said);
    return entries.length;
  }

  // --- The stack layout on lanes -----------------------------------------------------------------------------------

  //: Pure: a lane's children in a column. `kids` are {key, minX, minY, maxX, maxY}; they keep the order they have on
  //: the board (top, then left), each takes the lane's padding from its left edge and the gap below the one before.
  //: The lane grows to hold them and never shrinks. Returns { moves: [{key, dx, dy}], width, height }.
  function lmStackColumn(frame, kids, { gap = STACK_GAP, pad = STACK_GAP } = {}) {
    const sorted = kids.slice().sort((a, b) => a.minY - b.minY || a.minX - b.minX || (a.key < b.key ? -1 : 1));
    const moves = [];
    let y = frame.y + pad, widest = 0;
    for (const k of sorted) {
      moves.push({ key: k.key, dx: frame.x + pad - k.minX, dy: y - k.minY });
      y += k.maxY - k.minY + gap;
      widest = Math.max(widest, k.maxX - k.minX);
    }
    return {
      moves,
      width: Math.max(frame.width, widest + pad * 2),
      height: sorted.length ? Math.max(frame.height, y - gap + pad - frame.y) : frame.height,
    };
  }

  let settling = false;

  //: Stacks the children of every lane marked Stack. In memory and synchronous, so it can ride on the change
  //: that caused it; returns the undo entries for what moved and the rows to save, or null when nothing did.
  function lmRestack() {
    if (settling) return null;
    const lanes = (wbState.objects || []).filter((o) => o.kind === "frame" && o.data?.stack && !wbIsLocked("object", o));
    if (!lanes.length) return null;
    const entries = [], rows = [];
    for (const lane of lanes) {
      const kids = [];
      for (const key of wbFrameContents(lane)) {
        const [kind, rawId] = key.split(":");
        const item = wbFindItem(kind, Number(rawId));
        if (!item || (kind === "sketch" && wbIsLinkSketch(item)) || (kind === "object" && item.kind === "frame")) continue;
        const box = wbItemBBox(kind, item);
        if (box) kids.push({ key, kind, item, ...box });
      }
      if (!kids.length) continue;
      const plan = lmStackColumn(lane, kids, { pad: lane.data?.pad ?? STACK_GAP });
      const byKey = new Map(kids.map((k) => [k.key, k]));
      for (const m of plan.moves) {
        if (Math.abs(m.dx) < 0.5 && Math.abs(m.dy) < 0.5) continue;
        const k = byKey.get(m.key);
        entries.push(wbMoveItemBy(k.kind, k.item.id, k.item, m.dx, m.dy, rows));
      }
      if (plan.width !== lane.width || plan.height !== lane.height) {
        entries.push({ action: "move", kind: "object", id: lane.id, before: WB_KIND_INFO.object.payload(lane) });
        lane.width = plan.width;
        lane.height = plan.height;
        rows.push({ kind: "object", item: lane });
      }
    }
    return entries.length ? { entries, rows } : null;
  }

  //: Inside a gesture (`wbRecordGesture` diffs the board, so the moves join its one step on their own).
  async function lmSettleNow() {
    await ensureModule("boards");
    const done = lmRestack();
    if (!done) return false;
    settling = true;
    try {
      await wbSaveMany(done.rows);
    } finally {
      settling = false;
    }
    wbScheduleRender();
    return true;
  }

  async function lmFlush(rows) {
    await ensureModule("boards");
    try {
      await wbSaveMany(rows);
    } catch (err) {
      console.error("stack lane", err);
    }
    wbScheduleRender();
  }

  //: On a change pushed to Undo outside a gesture: the lane moves go ahead of it in one batch, so one Undo takes the
  //: change and the stacking back together. Returns the entry to push in its place, or null.
  function lmSettle(entry) {
    const done = lmRestack();
    if (!done) return null;
    const own = entry.action === "batch" ? entry.entries : [entry];
    lmFlush(done.rows);
    return { action: "batch", entries: [...done.entries, ...own] };
  }

  //: The hook `wbPushUndo` and `wbRecordGesture` (whiteboard.js) call; held on `wbBoardState` so they name nothing from a later file.
  wbBoardState.lane = { settle: lmSettle, settleNow: lmSettleNow };
  wbFmtState.layoutMore = {
    GAP, flow: lmFlow, radial: lmRadial, org: lmOrg, organic: lmOrganic, circle: lmCircle, arrange: lmArrange, overlapCount: lmOverlapCount,
    crossingCount: lmCrossingCount, canLayout: lmCanLayout, canRack: lmCanRack, rack: lmRack, apply: lmApply, stackColumn: lmStackColumn,
  };
})();
