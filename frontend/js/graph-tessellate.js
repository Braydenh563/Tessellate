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
    done.tess = { look: hexes ? "hexes" : "cells", cells: [] };
    if (!nodes.length) return done;
    const members = new Map();
    for (const node of done.nodes) {
      if (!members.has(node.category)) members.set(node.category, []);
      members.get(node.category).push(node);
    }
    const boxes = done.treemap.map((rect) => ({
      rect,
      notes: tessOrder(members.get(rect.category) || [], info),
      x0: rect.x0 + 2,
      y0: rect.y0 + rect.head,
      x1: rect.x1 - 2,
      y1: rect.y1 - 2,
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

  //: A category's name fitted to its header, never cut. `measure(text, size)` is
  //: a string's width in px at that font size; `maxW` and `maxH` the room in px.
  //: Tried at 12px first, then down to 9: the name and count on one line, the
  //: name alone, the name wrapped over as many lines as fit (a word wider than
  //: the room is broken between letters, not shortened). Null when not even 9px
  //: fits: the label is left out, the title tooltip and the legend name it.
  function fitHeaderLabel(measure, name, count, maxW, maxH) {
    const label = name || "Unfiled";
    for (let size = 12; size >= 9; size--) {
      const lineH = size + 3;
      const rows = Math.floor(maxH / lineH);
      if (rows < 1) continue;
      const full = `${label} (${count})`;
      if (measure(full, size) <= maxW) return { size, lines: [full] };
      if (measure(label, size) <= maxW) return { size, lines: [label] };
      const lines = tessWrap(measure, label, size, maxW);
      if (lines.length <= rows) return { size, lines };
    }
    return null;
  }

  function tessWrap(measure, text, size, maxW) {
    const lines = [];
    let line = "";
    const put = (word) => {
      const joined = line ? `${line} ${word}` : word;
      if (measure(joined, size) <= maxW) {
        line = joined;
        return true;
      }
      return false;
    };
    for (const word of text.split(/\s+/).filter(Boolean)) {
      if (put(word)) continue;
      if (line) lines.push(line);
      line = "";
      let rest = word;
      while (measure(rest, size) > maxW && rest.length > 1) {
        let n = rest.length - 1;
        while (n > 1 && measure(rest.slice(0, n), size) > maxW) n--;
        lines.push(rest.slice(0, n));
        rest = rest.slice(n);
      }
      line = rest;
    }
    if (line) lines.push(line);
    return lines;
  }

  //: The cells, behind the notes: each filled with its note's colour, a hairline
  //: between them, the lit ones (hovered, selected) filled stronger and ringed.
  //: One Path2D per cell is built once per layout and kept on the cell.
  function gcDrawTessellation(ctx, s, k) {
    const tess = s.tree && s.tree.tess;
    if (!tess) return;
    ctx.save();
    ctx.lineJoin = "round";
    const cellPath = (cell) => {
      if (!cell._path) {
        cell._path = new Path2D();
        cell.poly.forEach(([x, y], i) => (i ? cell._path.lineTo(x, y) : cell._path.moveTo(x, y)));
        cell._path.closePath();
      }
      return cell._path;
    };
    const lit = new Set(s.selected ? [...s.selected] : []);
    if (s.hoveredId != null) lit.add(s.hoveredId);
    ctx.lineWidth = 1 / k;
    ctx.strokeStyle = gcTokens.ink;
    for (const cell of tess.cells) {
      const node = s.byId.get(cell.id);
      const path = cellPath(cell);
      ctx.globalAlpha = lit.has(cell.id) ? 0.38 : 0.14;
      ctx.fillStyle = (node && node.colour) || s.colourOf({ isGroup: true, category: cell.category });
      ctx.fill(path);
      ctx.globalAlpha = 0.22;
      ctx.stroke(path);
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
      paint: gcDrawTessellation,
      nodeAt: gcTessNodeAt,
      titleAt: gcCategoryTitleAt,
    },
  });
})();
