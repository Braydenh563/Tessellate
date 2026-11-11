(() => {
  // whiteboard-shape-more.js: what draw.io does with a shape's ports and points that the first pass left (WHITEBOARD_PLAN,
  // section 10). A table's connection points are the two ends of each row (draw.io's `portConstraint=eastwest` on a
  // table row), and a connector that is joined to a row stays on that row when rows are added or removed. The pure
  // parts take plain data, so a node test runs them without a board.

  //: A row's middle is a fraction of the table's height, rows being of equal height.
  const rowMiddle = (row, rows) => Math.round(((row + 0.5) / rows) * 1e4) / 1e4;
  const held = new Map();

  //: The ports of a table with `rows` rows, as fractions of its box: the left and right ends of every row, then the
  //: middles of the top and the bottom edge, so a connector can still come in from above or below.
  function tableRowPorts(rows) {
    const n = Math.max(1, Math.floor(rows) || 1);
    if (held.has(n)) return held.get(n);
    const out = [];
    for (let r = 0; r < n; r += 1) out.push({ x: 0, y: rowMiddle(r, n) }, { x: 1, y: rowMiddle(r, n) });
    out.push({ x: 0.5, y: 0 }, { x: 0.5, y: 1 });
    held.set(n, out);
    return out;
  }

  //: The row a stored anchor sits on in a table of `rows` rows, or -1 when it is not at a row's end.
  function rowOf(anchor, rows) {
    if (!anchor || !Number.isFinite(anchor.x) || !Number.isFinite(anchor.y)) return -1;
    if (Math.abs(anchor.x) > 0.001 && Math.abs(anchor.x - 1) > 0.001) return -1;
    const at = anchor.y * rows - 0.5;
    const row = Math.round(at);
    return Math.abs(at - row) < 0.02 && row >= 0 && row < rows ? row : -1;
  }

  //: Pure: the row an anchor on row `row` is on after a row is added at `at` (before the row now there) or removed
  //: from `at`; -1 when its row is the one removed.
  function rowAfter(row, at, remove) {
    if (remove) return row === at ? -1 : row > at ? row - 1 : row;
    return row >= at ? row + 1 : row;
  }

  //: Pure: the patch a connector needs so its ends stay on their table rows. `ends` is [[name, kind, id]]; `table`
  //: is the table's id. A removed row's end lets go of the table's side (it floats), the rest move to the row's new
  //: middle. Returns {} when nothing is on a row.
  function carryPatch(data, tableId, rows, at, remove) {
    const patch = {};
    const total = rows + (remove ? -1 : 1);
    for (const name of ["source", "target"]) {
      if (data[`${name}Id`] !== tableId || (data[`${name}Kind`] || "node") !== "object") continue;
      const anchor = data[`${name}Anchor`];
      const row = rowOf(anchor, rows);
      if (row < 0) continue;
      const next = rowAfter(row, at, remove);
      patch[`${name}Anchor`] = next < 0 ? undefined : { ...anchor, y: rowMiddle(next, total) };
    }
    return patch;
  }

  //: For `wbTableReshape`: null when no connector is on a row of this table, else a function that moves the ends
  //: (to run inside the same gesture as the table's own change, so it is one Undo).
  function carryRowPorts(table, at, remove, rows) {
    const jobs = [];
    for (const sketch of wbState.sketches || []) {
      if (!wbIsLinkSketch(sketch)) continue;
      const patch = carryPatch(wbSketchData(sketch) || {}, table.id, rows, at, remove);
      if (Object.keys(patch).length) jobs.push([sketch, patch]);
    }
    if (!jobs.length) return null;
    return async () => {
      for (const [sketch, patch] of jobs) await wbSaveSketchProps(sketch, patch);
    };
  }

  wbFmtState.shapeMore = { tableRowPorts, rowOf, rowAfter, carryPatch, carryRowPorts };
})();
