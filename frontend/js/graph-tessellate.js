// The Tessellation view (GRAPH_PLAN Q31). Every note owns one cell of a plane
// tiled with no gaps; neighbours are related notes, a category is a framed
// region. One layout, selection, legend and popup code under both looks:
//
// - Cells: a Voronoi inside each category's rectangle, a note's cell as large
//   as its links make it (the seeds are the centres of a link-weighted
//   treemap, so the tiles share the Map's area rule).
// - Hexes: one hexagon size under every category, a category's notes a compact
//   blob of it, linked notes in neighbouring hexagons.
//
// Lazy: it travels in the graph bundle (LAZY_MODULES.graph), never at boot.
// `layoutTessellation` and `fitHeaderLabel` are pure (run in node by
// tests/test_graph_tessellation.py); the drawing reads the canvas state.

(() => {
  //: What the layouts read of the notebook's links: each note's link count and
  //: its neighbours. Built from the edges the map draws, so a hidden kind or a
  //: pruned similarity line weighs nothing here either.
  //: **A visible gap between categories** (INBOX 1744, the owner's liked mock A):
  //: the frame is drawn 2px inside its rectangle (`gcDrawTreemap`), and the
  //: cells keep 5px clear of the rectangle, so two regions are 4px of frame
  //: apart and each holds its cells 3px off its own frame.
  const TESS_PAD = 5;
  //: Half the space between two cells, and the radius their corners are softened to.
  const TESS_HALF_GAP = 1.5;
  const TESS_RADIUS = 3;

  //: A convex polygon pulled in by `d` on every side (each edge moved inward,
  //: then the polygon clipped to it), so neighbouring cells read as tiles with
  //: a gap between them. Empty when `d` swallows the polygon.
  function tessInset(poly, d) {
    const area = d3.polygonArea(poly);
    if (!area || poly.length < 3) return poly;
    const sign = area > 0 ? -1 : 1;
    let out = poly.map((p) => [p[0], p[1]]);
    for (let i = 0; i < poly.length && out.length; i++) {
      const [ax, ay] = poly[i];
      const [bx, by] = poly[(i + 1) % poly.length];
      const len = Math.hypot(bx - ax, by - ay);
      if (!len) continue;
      //: Inward normal (the winding decides which side that is).
      const nx = (-(by - ay) / len) * sign;
      const ny = ((bx - ax) / len) * sign;
      const inside = (p) => (p[0] - ax) * nx + (p[1] - ay) * ny - d;
      const next = [];
      for (let j = 0; j < out.length; j++) {
        const p = out[j];
        const q = out[(j + 1) % out.length];
        const dp = inside(p);
        const dq = inside(q);
        if (dp >= 0) next.push(p);
        if ((dp >= 0) !== (dq >= 0)) {
          const f = dp / (dp - dq);
          next.push([p[0] + (q[0] - p[0]) * f, p[1] + (q[1] - p[1]) * f]);
        }
      }
      out = next;
    }
    return out.length >= 3 ? out : [];
  }

  function gcTessInfo(edges) {
    const degree = new Map();
    const near = new Map();
    const touch = (a, b) => {
      degree.set(a, (degree.get(a) || 0) + 1);
      if (!near.has(a)) near.set(a, new Set());
      near.get(a).add(b);
    };
    for (const edge of edges) {
      const a = edge.source && edge.source.id != null ? edge.source.id : edge.source;
      const b = edge.target && edge.target.id != null ? edge.target.id : edge.target;
      if (a === b) continue;
      touch(a, b);
      touch(b, a);
    }
    return { degree, near };
  }

  //: A category's notes in the order they take their seats: the best-linked
  //: first, then each one's neighbours, so notes that are linked end up in
  //: neighbouring cells.
  function tessOrder(notes, info) {
    const degreeOf = (note) => (info && info.degree && info.degree.get(note.id)) || 0;
    const byId = new Map(notes.map((note) => [note.id, note]));
    const left = [...notes].sort((a, b) => degreeOf(b) - degreeOf(a));
    const seen = new Set();
    const order = [];
    for (const start of left) {
      if (seen.has(start.id)) continue;
      seen.add(start.id);
      const queue = [start];
      while (queue.length) {
        const note = queue.shift();
        order.push(note);
        const next = [...((info && info.near && info.near.get(note.id)) || [])]
          .map((id) => byId.get(id))
          .filter((other) => other && !seen.has(other.id))
          .sort((a, b) => degreeOf(b) - degreeOf(a));
        for (const other of next) {
          seen.add(other.id);
          queue.push(other);
        }
      }
    }
    return order;
  }

  function layoutTessellation(nodes, width, height, info, look) {
    //: Hexes are one size everywhere, so a category's area follows its note
    //: count (a hex blob cannot fill an area set by links); Cells follow links.
    const hexes = look === "hexes";
    const done = layoutTreemap(nodes, width, height, hexes ? null : info);
    done.tess = { look: hexes ? "hexes" : "cells", cells: [], near: (info && info.near) || null };
    if (!nodes.length) return done;
    const members = new Map();
    for (const node of done.nodes) {
      if (!members.has(node.category)) members.set(node.category, []);
      members.get(node.category).push(node);
    }
    const boxes = done.treemap.map((rect) => ({
      rect,
      notes: tessOrder(members.get(rect.category) || [], info),
      x0: rect.x0 + TESS_PAD,
      y0: rect.y0 + rect.head,
      x1: rect.x1 - TESS_PAD,
      y1: rect.y1 - TESS_PAD,
    }));
    const seat = (note, poly, w, h) => {
      const [x, y] = d3.polygonCentroid(poly);
      note.x = Number.isFinite(x) ? x : poly[0][0];
      note.y = Number.isFinite(y) ? y : poly[0][1];
      note.fx = note.x;
      note.fy = note.y;
      note.cell = { w, h };
      done.tess.cells.push({ id: note.id, category: note.category, poly });
    };
    if (hexes) {
      const R = tessHexRadius(boxes);
      const a = Math.sqrt(3) * R;
      for (const box of boxes) {
        const spots = tessHexSpots(box, R).sort((p, q) => p.d - q.d).slice(0, box.notes.length);
        box.notes.forEach((note, i) => {
          const spot = spots[i];
          if (!spot) return;
          const poly = [];
          for (let c = 0; c < 6; c++) {
            const angle = (Math.PI / 180) * (60 * c + 30);
            poly.push([spot.x + R * Math.cos(angle), spot.y + R * Math.sin(angle)]);
          }
          seat(note, poly, a, 2 * R);
        });
      }
      return done;
    }
    for (const box of boxes) {
      const bw = Math.max(box.x1 - box.x0, 1);
      const bh = Math.max(box.y1 - box.y0, 1);
      const frame = [
        [box.x0, box.y0],
        [box.x1, box.y0],
        [box.x1, box.y1],
        [box.x0, box.y1],
      ];
      if (box.notes.length === 1) {
        seat(box.notes[0], frame, bw, bh);
        continue;
      }
      //: Seeds: the centres of a treemap of the notes in their seating order,
      //: each weighing 1 plus its links, so a well-linked note's seed sits in a
      //: bigger tile and wins a bigger Voronoi cell.
      const leaves = d3
        .hierarchy({ children: box.notes.map((note) => ({ note })) })
        .sum((d) => (d.note ? 1 + Math.min((info && info.degree && info.degree.get(d.note.id)) || 0, 12) : 0));
      d3.treemap().size([bw, bh]).tile(d3.treemapSquarify).paddingInner(0)(leaves);
      const seeds = leaves.children.map((leaf) => [box.x0 + (leaf.x0 + leaf.x1) / 2, box.y0 + (leaf.y0 + leaf.y1) / 2]);
      const voronoi = d3.Delaunay.from(seeds).voronoi([box.x0, box.y0, box.x1, box.y1]);
      box.notes.forEach((note, i) => {
        const ring = voronoi.cellPolygon(i);
        const poly = ring ? ring.slice(0, -1) : frame;
        const xs = poly.map((p) => p[0]);
        const ys = poly.map((p) => p[1]);
        seat(note, poly, Math.max(...xs) - Math.min(...xs), Math.max(...ys) - Math.min(...ys));
      });
    }
    return done;
  }

  //: The largest hexagon (centre to corner) under which every category's notes
  //: fit in its box. Capacity falls as the hexagon grows, so a binary search.
  function tessHexRadius(boxes) {
    const fits = (R) => boxes.every((box) => tessHexSpots(box, R).length >= box.notes.length);
    let lo = 1;
    let hi = 60;
    if (fits(hi)) return hi;
    while (hi - lo > 0.05) {
      const mid = (lo + hi) / 2;
      if (fits(mid)) lo = mid;
      else hi = mid;
    }
    return lo;
  }

  //: Every hexagon (pointy top) that fits whole in a box, centred in it, each
  //: with its distance from the middle so the blob grows outward from there.
  function tessHexSpots(box, R) {
    const a = Math.sqrt(3) * R;
    const bw = box.x1 - box.x0;
    const bh = box.y1 - box.y0;
    const rows = bh >= 2 * R ? Math.floor((bh - 2 * R) / (1.5 * R)) + 1 : 0;
    const cols = bw >= 1.5 * a ? Math.floor((bw - 1.5 * a) / a) + 1 : 0;
    const spots = [];
    if (!rows || !cols) return spots;
    const left = box.x0 + (bw - (cols * a + a / 2)) / 2;
    const top = box.y0 + (bh - (2 * R + 1.5 * R * (rows - 1))) / 2;
    const mx = (box.x0 + box.x1) / 2;
    const my = (box.y0 + box.y1) / 2;
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const x = left + a / 2 + (r % 2 ? a / 2 : 0) + c * a;
        const y = top + R + 1.5 * R * r;
        spots.push({ x, y, d: Math.hypot(x - mx, y - my) });
      }
    }
    return spots;
  }

  //: A category's name fitted to its header, never split inside a word (INBOX
  //: 1744: "Literatur / e"). `measure(text, size)` is a string's width in px at
  //: that font size; `maxW` and `maxH` the room in px. In order, at 12px: the
  //: name and count on one line; the name alone; the name wrapped at spaces
  //: over two lines at most; then the same one size down, to 9px; last, the
  //: name's leading whole words and an ellipsis. Null when even the first word
  //: is wider than the room or no line fits: the label is left out, the title
  //: tooltip and the legend name it.
  function fitHeaderLabel(measure, name, count, maxW, maxH) {
    const label = name || "Unfiled";
    const words = label.split(/\s+/).filter(Boolean);
    for (let size = 12; size >= 9; size--) {
      const rows = Math.min(2, Math.floor(maxH / (size + 3)));
      if (rows < 1) continue;
      const full = `${label} (${count})`;
      if (measure(full, size) <= maxW) return { size, lines: [full] };
      if (measure(label, size) <= maxW) return { size, lines: [label] };
      const lines = rows > 1 ? tessWrap(measure, words, size, maxW) : null;
      if (lines && lines.length <= rows) return { size, lines };
    }
    const size = 9;
    const rows = Math.min(2, Math.floor(maxH / (size + 3)));
    if (rows < 1) return null;
    for (let n = words.length - 1; n >= 1; n--) {
      //: Never stranded on an ampersand or a dash: "Academics &…" says nothing.
      if (/^[^\p{L}\p{N}]+$/u.test(words[n - 1])) continue;
      const lines = tessWrap(measure, [...words.slice(0, n - 1), `${words[n - 1]}\u2026`], size, maxW);
      if (lines && lines.length <= rows) return { size, lines };
    }
    return null;
  }

  //: Greedy wrap at spaces only; null when a single word is wider than the room.
  function tessWrap(measure, words, size, maxW) {
    const lines = [];
    let line = "";
    for (const word of words) {
      if (measure(word, size) > maxW) return null;
      const joined = line ? `${line} ${word}` : word;
      if (measure(joined, size) <= maxW) line = joined;
      else {
        lines.push(line);
        line = word;
      }
    }
    if (line) lines.push(line);
    return lines;
  }

  //: The cells, behind the notes: each filled with its note's colour, a hairline
  //: between them, the lit ones (hovered, selected) filled stronger and ringed.
  //: One Path2D per cell is built once per layout and kept on the cell.
  //: **A new note's cell settles like the logo's third cell** (L-graph-10).
  //: The emblem's `emblem-arrive` (css/03-dashboard-widgets.css) drifts in
  //: from 7% up and right turned -10deg, overshoots to -0.8% and 1.5deg at
  //: 72%, and settles, over 1.4 s; a cell does the same in its own width.
  //: Only a note newer than every cell before (a filter that shows a
  //: category again is not an arrival), never on the first draw, and not at
  //: all under either reduced motion setting.
  const TESS_ARRIVE_MS = 1400;
  function tessArrivals(s, tess, now) {
    if (s.tessLast !== tess) {
      const before = s.tessLast;
      s.tessLast = tess;
      if (before && before.cells.length && !gcStill()) {
        const known = new Set(before.cells.map((c) => c.id));
        const newest = Math.max(...before.cells.map((c) => (typeof c.id === "number" ? c.id : -Infinity)));
        for (const cell of tess.cells) {
          if (!known.has(cell.id) && typeof cell.id === "number" && cell.id > newest) {
            (s.tessArrive || (s.tessArrive = new Map())).set(cell.id, now);
          }
        }
      }
    }
    if (!s.tessArrive || !s.tessArrive.size) return null;
    for (const [id, at] of s.tessArrive) if (now - at >= TESS_ARRIVE_MS) s.tessArrive.delete(id);
    if (!s.tessArrive.size) return null;
    //: The next frame through the canvas's own loop, inside its self-frame
    //: bound (INBOX 1643), like a composed frame still moving.
    if ((s.selfFrames = (s.selfFrames || 0) + 1) <= gcRequestDraw.selfCap) {
      s.drawAsking = true;
      try {
        gcRequestDraw(s);
      } finally {
        s.drawAsking = false;
      }
    }
    return s.tessArrive;
  }

  //: The keyframes as a pose at progress `t` (0 to 1): offsets in cell
  //: widths, the turn in radians, the opacity. Null once settled.
  function tessArrivePose(t) {
    if (!(t >= 0) || t >= 1) return null;
    const out = (u) => 1 - (1 - u) ** 3;
    const inOut = (u) => (u < 0.5 ? 4 * u ** 3 : 1 - (-2 * u + 2) ** 3 / 2);
    const deg = Math.PI / 180;
    let dx;
    let dy;
    let turn;
    if (t < 0.72) {
      const u = out(t / 0.72);
      dx = 0.07 + (-0.008 - 0.07) * u;
      dy = -0.07 + (0.008 + 0.07) * u;
      turn = (-10 + 11.5 * u) * deg;
    } else {
      const u = inOut((t - 0.72) / 0.28);
      dx = -0.008 * (1 - u);
      dy = 0.008 * (1 - u);
      turn = 1.5 * (1 - u) * deg;
    }
    return { dx, dy, turn, alpha: Math.min(1, t / 0.2) };
  }

  function gcDrawTessellation(ctx, s, k) {
    const tess = s.tree && s.tree.tess;
    if (!tess) return;
    ctx.save();
    ctx.lineJoin = "round";
    //: The tile: the cell pulled in by half the gap, its corners rounded with
    //: arcs (one path, so a translucent fill never doubles where a stroke
    //: would overlap it).
    const cellPath = (cell) => {
      if (!cell._path) {
        const path = new Path2D();
        const tile = tessInset(cell.poly, TESS_HALF_GAP);
        const n = tile.length;
        if (n) {
          const mid = (a, b) => [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
          const start = mid(tile[0], tile[1 % n]);
          path.moveTo(start[0], start[1]);
          for (let i = 1; i <= n; i++) {
            const corner = tile[i % n];
            const to = mid(corner, tile[(i + 1) % n]);
            const reach = Math.min(Math.hypot(corner[0] - start[0], corner[1] - start[1]), Math.hypot(to[0] - corner[0], to[1] - corner[1]));
            path.arcTo(corner[0], corner[1], to[0], to[1], Math.min(TESS_RADIUS, reach));
          }
          path.closePath();
        }
        cell._path = path;
      }
      return cell._path;
    };
    const lit = new Set(s.selected ? [...s.selected] : []);
    //: A hovered cell lights the cells of the notes it links to, softer
    //: (mock A; the lines are not drawn here, so this is what shows them).
    const linked = new Set();
    if (s.hoveredId != null) {
      lit.add(s.hoveredId);
      for (const id of (tess.near && tess.near.get(s.hoveredId)) || []) if (!lit.has(id)) linked.add(id);
    }
    const now = performance.now();
    const arriving = tessArrivals(s, tess, now);
    ctx.lineWidth = 1 / k;
    ctx.strokeStyle = gcTokens.ink;
    for (const cell of tess.cells) {
      const node = s.byId.get(cell.id);
      const path = cellPath(cell);
      const at = arriving && arriving.get(cell.id);
      const pose = at != null ? tessArrivePose((now - at) / TESS_ARRIVE_MS) : null;
      if (pose) {
        ctx.save();
        const [cx, cy] = d3.polygonCentroid(cell.poly);
        const [x0, x1] = d3.extent(cell.poly, (p) => p[0]);
        const size = x1 - x0;
        ctx.translate(cx + pose.dx * size, cy + pose.dy * size);
        ctx.rotate(pose.turn);
        ctx.translate(-cx, -cy);
      }
      const fade = pose ? pose.alpha : 1;
      ctx.globalAlpha = fade * (lit.has(cell.id) ? 0.38 : linked.has(cell.id) ? 0.27 : 0.14);
      ctx.fillStyle = (node && node.colour) || s.colourOf({ isGroup: true, category: cell.category });
      ctx.fill(path);
      ctx.globalAlpha = fade * (linked.has(cell.id) ? 0.5 : 0.16);
      ctx.stroke(path);
      if (pose) ctx.restore();
    }
    ctx.lineWidth = 2.2 / k;
    for (const cell of tess.cells) {
      if (!lit.has(cell.id)) continue;
      ctx.globalAlpha = 0.95;
      ctx.strokeStyle = (s.byId.get(cell.id) || {}).colour || gcTokens.ink;
      ctx.stroke(cellPath(cell));
    }
    ctx.restore();
  }

  //: The note whose cell holds a point, for a pointer on a cell's empty part
  //: (a dot is small; the cell is the target). Null off every cell.
  function gcTessNodeAt(x, y, s) {
    const tess = s.tree && s.tree.tess;
    if (!tess) return null;
    for (const cell of tess.cells) {
      if (!cell._box) {
        const xs = cell.poly.map((p) => p[0]);
        const ys = cell.poly.map((p) => p[1]);
        cell._box = [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
      }
      const b = cell._box;
      if (x < b[0] || x > b[2] || y < b[1] || y > b[3] || !d3.polygonContains(cell.poly, [x, y])) continue;
      const node = s.byId.get(cell.id);
      return node && gcVisibleAtTime(node, s) ? node : null;
    }
    return null;
  }

  //: The title tooltip of the category rectangle under a point, in the Map and
  //: the Tessellation view: the whole name and the count, however the header
  //: had to shrink or leave it out.
  function gcCategoryTitleAt(x, y, s) {
    const rects = s.tree && s.tree.treemap;
    if (!rects) return "";
    const rect = rects.find((r) => x >= r.x0 && x <= r.x1 && y >= r.y0 && y <= r.y1);
    return rect ? `${rect.category || "Unfiled"}: ${rect.count} ${rect.count === 1 ? "note" : "notes"}` : "";
  }

  //: The file's whole surface, one name (ranked row 37a): the layout and the
  //: header fit (pure, run in node by the tests), the drawing, the two hit tests
  //: and the link read the canvas and `layoutHierarchy` call.
  Object.assign(window, {
    gcTess: {
      info: gcTessInfo,
      layout: layoutTessellation,
      fit: fitHeaderLabel,
      inset: tessInset,
      paint: gcDrawTessellation,
      nodeAt: gcTessNodeAt,
      titleAt: gcCategoryTitleAt,
      arrivePose: tessArrivePose,
    },
  });
})();
