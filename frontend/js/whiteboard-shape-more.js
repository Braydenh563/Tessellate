(() => {
  // whiteboard-shape-more.js: what draw.io does with a shape's ports and points that the first pass left (WHITEBOARD_PLAN,
  // section 10). A table's connection points are the two ends of each row (draw.io's `portConstraint=eastwest` on a
  // table row), and a connector that is joined to a row stays on that row when rows are added or removed. And Edit shape
  // points (draw.io's `editPolygon`) for a closed shape of straight sides. The pure parts take plain data, so a node test
  // runs them without a board.

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
      const saves = [];
      for (const [sketch, patch] of jobs) if (wbSketchSetProps(sketch, patch)) saves.push({ kind: "sketch", item: sketch });
      await wbSaveMany(saves);
    };
  }

  //: **Edit shape points** (draw.io's `editPolygon`): the corners of a closed shape with straight sides, as handles you
  //: can drag. A press on the outline adds a corner there (and drags it), a press on a corner without moving takes it out
  //: (three stay), and the result is saved as the shape's own path (`shape: "custom"`, the label area dropped, since it was
  //: set for the old outline). One Undo step per move, addition or removal. Escape, or a press anywhere else, ends it.

  //: Pure: the corners of a closed path of straight sides (absolute or relative M, L, H, V, then Z) as [{x, y}], or null
  //: for anything else (a curve, an open line, two outlines).
  function polygonPoints(d) {
    const text = String(d || "").trim();
    if (!/[Zz]$/.test(text) || /[CcQqAaSsTt]/.test(text)) return null;
    const tokens = text.match(/[MmLlHhVvZz]|-?\d*\.?\d+(?:[eE][-+]?\d+)?/g);
    if (!tokens) return null;
    const pts = [];
    let i = 0, cmd = "", px = 0, py = 0, started = false;
    const num = () => parseFloat(tokens[i++]);
    const to = (x, y) => { px = x; py = y; pts.push({ x, y }); };
    while (i < tokens.length) {
      if (/^[A-Za-z]$/.test(tokens[i])) cmd = tokens[i++];
      switch (cmd) {
        case "M": if (started) return null; started = true; to(num(), num()); cmd = "L"; break;
        case "m": if (started) return null; started = true; to(px + num(), py + num()); cmd = "l"; break;
        case "L": to(num(), num()); break;
        case "l": { const x = px + num(); to(x, py + num()); break; }
        case "H": to(num(), py); break;
        case "h": to(px + num(), py); break;
        case "V": to(px, num()); break;
        case "v": to(px, py + num()); break;
        case "Z": case "z": cmd = ""; break;
        default: return null;
      }
    }
    if (pts.some((p) => !Number.isFinite(p.x) || !Number.isFinite(p.y))) return null;
    const same = (a, b) => Math.abs(a.x - b.x) < 0.01 && Math.abs(a.y - b.y) < 0.01;
    const out = pts.filter((p, n) => n === 0 || !same(p, pts[n - 1]));
    if (out.length > 1 && same(out[0], out[out.length - 1])) out.pop();
    return out.length >= 3 ? out : null;
  }

  const round2 = (n) => Math.round(n * 100) / 100;
  const polygonD = (pts) => `M ${pts.map((p) => `${round2(p.x)} ${round2(p.y)}`).join(" L ")} Z`;

  //: Pure: the corner within `grab` of a point, the nearest one, or -1.
  function nearestCorner(pts, x, y, grab) {
    let best = -1, bestDist = grab;
    pts.forEach((p, n) => {
      const dist = Math.hypot(p.x - x, p.y - y);
      if (dist <= bestDist) { bestDist = dist; best = n; }
    });
    return best;
  }

  //: Pure: where a point is nearest the outline: the foot on the closest side, that side's distance, and the index a
  //: corner added there takes (after the side's first corner).
  function nearestOnSide(pts, x, y) {
    let best = null;
    pts.forEach((a, n) => {
      const b = pts[(n + 1) % pts.length];
      const dx = b.x - a.x, dy = b.y - a.y;
      const len2 = dx * dx + dy * dy;
      const t = len2 ? Math.max(0, Math.min(1, ((x - a.x) * dx + (y - a.y) * dy) / len2)) : 0;
      const fx = a.x + dx * t, fy = a.y + dy * t;
      const dist = Math.hypot(x - fx, y - fy);
      if (!best || dist < best.dist) best = { index: n + 1, x: fx, y: fy, dist };
    });
    return best;
  }

  //: The one selected shape the editor can work on, with its parsed data.
  function pointsTarget() {
    const target = wbSwapTarget();
    return target && polygonPoints(target.parsed.d) ? target : null;
  }

  const editing = { id: null, drag: null };
  const GRAB_PX = 8;
  const zoomK = () => d3.zoomTransform(document.getElementById("whiteboard-container")).k || 1;

  //: The handles, in the overlay layer above the cards (as the connection points' dots), at a size that holds at any zoom.
  function drawHandles(item) {
    const group = document.getElementById("wb-overlay-zoom-group");
    if (!group) return;
    let layer = document.getElementById("wb-point-handles");
    if (!layer) {
      layer = document.createElementNS("http://www.w3.org/2000/svg", "g");
      layer.setAttribute("id", "wb-point-handles");
      layer.setAttribute("pointer-events", "none");
      group.appendChild(layer);
    }
    layer.textContent = "";
    const pts = (item && polygonPoints(wbSketchParsedData(item)?.d)) || [];
    const k = zoomK(), size = 10 / k;
    for (const p of pts) {
      const box = document.createElementNS("http://www.w3.org/2000/svg", "rect");
      box.setAttribute("x", String(p.x - size / 2));
      box.setAttribute("y", String(p.y - size / 2));
      box.setAttribute("width", String(size));
      box.setAttribute("height", String(size));
      box.setAttribute("fill", "var(--card)");
      box.setAttribute("stroke", "var(--accent)");
      box.setAttribute("stroke-width", String(2 / k));
      layer.appendChild(box);
    }
  }

  function stopPoints(say) {
    if (editing.id == null) return;
    editing.id = null;
    editing.drag = null;
    document.getElementById("wb-point-handles")?.remove();
    if (say) wbAnnounce("Shape points done.");
  }

  function editPoints() {
    if (editing.id != null) {
      stopPoints(true);
      return;
    }
    const target = pointsTarget();
    if (!target) {
      toast("Select one shape with straight sides first.", "info");
      return;
    }
    editing.id = target.item.id;
    drawHandles(target.item);
    wbAnnounce("Editing shape points: drag a point to move it, press the outline to add one, press a point to take it out, Escape to finish.");
    toast("Drag a point to move it, press the outline to add one, a point to take it out. Escape finishes.", "info");
  }

  //: The shape's path set to `pts`, in memory and on screen (nothing saved yet).
  function showPoints(item, pts) {
    const next = { ...wbSketchParsedData(item), d: polygonD(pts), shape: "custom" };
    delete next.label_area;
    delete next.shapeKind;
    item.data = JSON.stringify(next);
    renderWhiteboardNow();
    drawHandles(item);
  }

  async function commitPoints(drag, said) {
    editing.drag = null;
    await wbSaveSketchProps(drag.item, {});
    wbPushUndo({ action: "move", kind: "sketch", id: drag.item.id, before: drag.before });
    wbScheduleRender();
    wbAnnounce(said);
  }

  function bindPointEditor() {
    const container = document.getElementById("whiteboard-container");
    if (!container) return;
    container.addEventListener("pointerdown", (e) => {
      if (editing.id == null || e.button !== 0) return;
      const target = pointsTarget();
      if (!target || target.item.id !== editing.id) {
        stopPoints(false);
        return;
      }
      const [x, y] = wbClientToBoard(e.clientX, e.clientY);
      const grab = GRAB_PX / zoomK();
      const pts = polygonPoints(target.parsed.d);
      let index = nearestCorner(pts, x, y, grab), added = false;
      if (index < 0) {
        const side = nearestOnSide(pts, x, y);
        if (!side || side.dist > grab * 1.5) {
          stopPoints(true);
          return;
        }
        pts.splice(side.index, 0, { x: side.x, y: side.y });
        index = side.index;
        added = true;
      }
      e.preventDefault();
      e.stopPropagation();
      const drag = { item: target.item, before: WB_KIND_INFO.sketch.payload(target.item), pts, index, added, moved: false, x: e.clientX, y: e.clientY };
      editing.drag = drag;
      if (added) showPoints(drag.item, pts);
      const finish = (keep) => {
        window.removeEventListener("pointermove", move);
        window.removeEventListener("pointerup", up);
        window.removeEventListener("pointercancel", cancel);
        document.removeEventListener("keydown", key, true);
        if (!keep) {
          drag.item.data = drag.before.data;
          editing.drag = null;
          renderWhiteboardNow();
          drawHandles(drag.item);
        }
      };
      const move = (ev) => {
        if (!drag.moved && Math.hypot(ev.clientX - drag.x, ev.clientY - drag.y) < 4) return;
        drag.moved = true;
        const [bx, by] = wbClientToBoard(ev.clientX, ev.clientY);
        const snap = wbSnapOn() ? (v) => Math.round(v / WB_GRID_SPACING) * WB_GRID_SPACING : (v) => v;
        drag.pts[drag.index] = { x: snap(bx), y: snap(by) };
        showPoints(drag.item, drag.pts);
      };
      const up = async () => {
        finish(true);
        if (drag.moved || drag.added) {
          await commitPoints(drag, drag.added && !drag.moved ? `Point added; the shape has ${drag.pts.length}.` : "Point moved.");
        } else if (drag.pts.length > 3) {
          drag.pts.splice(drag.index, 1);
          showPoints(drag.item, drag.pts);
          await commitPoints(drag, `Point taken out; the shape has ${drag.pts.length}.`);
        } else {
          editing.drag = null;
          toast("A shape keeps at least three points.", "info");
        }
      };
      const cancel = () => finish(false);
      const key = (ev) => {
        if (ev.key !== "Escape") return;
        ev.preventDefault();
        ev.stopPropagation();
        finish(false);
      };
      window.addEventListener("pointermove", move);
      window.addEventListener("pointerup", up);
      window.addEventListener("pointercancel", cancel);
      document.addEventListener("keydown", key, true);
    }, true);
    document.addEventListener("keydown", (e) => {
      if (editing.id == null || editing.drag || e.key !== "Escape") return;
      e.preventDefault();
      e.stopPropagation();
      stopPoints(true);
    }, true);
  }

  onSurface("board", bindPointEditor);

  wbFmtState.shapeMore = {
    tableRowPorts, rowOf, rowAfter, carryPatch, carryRowPorts,
    polygonPoints, polygonD, nearestCorner, nearestOnSide, pointsTarget, editPoints,
  };
})();
