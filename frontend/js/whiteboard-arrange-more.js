(() => {
  // whiteboard-arrange-more.js: two more Arrange commands from draw.io's layout menu (WHITEBOARD_PLAN, section 10).
  // "Space parallel connectors" fans the connectors that join the same two shapes so none hides another
  // (`mxParallelEdgeLayout`); "Flip the layout" mirrors where the selected shapes sit, left to right or top to
  // bottom, and the bends of the connectors between them, without turning any shape itself (draw.io's layout
  // `direction`). The pure parts take plain data, so a node test runs them without a board.

  //: Between two neighbouring connectors, in board units, measured at the middle of the line.
  const GAP = 28;
  const keyOf = (kind, id) => `${kind || "node"}:${id}`;

  //: The offsets of `n` lines about the middle one: 1 gives [0], 2 gives [-14, 14], 3 gives [-28, 0, 28].
  function offsets(n, gap = GAP) {
    return Array.from({ length: n }, (_, i) => (i - (n - 1) / 2) * gap);
  }

  //: A connector this layout may bend: both ends on a shape, a free route or a straight line, and no bends of the
  //: person's own (their waypoints are theirs, as are the elbow, entity and isometric routes, which are drawn from
  //: the two ends alone).
  function spreadable(data) {
    if (!data || !String(data.type || "").startsWith("link-")) return false;
    if (data.sourceId == null || data.targetId == null) return false;
    if (data.sourceId === data.targetId && (data.sourceKind || "node") === (data.targetKind || "node")) return false;
    if (data.loop || (data.route && data.route !== "straight") || data.points?.length) return false;
    return true;
  }

  const pairOf = (data) => [keyOf(data.sourceKind, data.sourceId), keyOf(data.targetKind, data.targetId)].sort().join("|");

  //: Pure: the bend each connector takes. `links` is [{id, data}], `centers` maps a shape's key to its centre and
  //: `only` is the set of pairs to touch (null for every pair). A pair with fewer than two spreadable lines is left
  //: alone. The bend is the curve's pull away from the chord (it peaks at half of it), so a line sits at `offset`
  //: from the chord when its bend is twice that, along the chord's normal read from the lower key to the higher one:
  //: both ways between the same two shapes then fan to the same sides.
  function plan(links, centers, only = null) {
    const groups = new Map();
    for (const link of links) {
      if (!spreadable(link.data)) continue;
      const pair = pairOf(link.data);
      if (only && !only.has(pair)) continue;
      if (!groups.has(pair)) groups.set(pair, []);
      groups.get(pair).push(link);
    }
    const out = [];
    for (const [pair, group] of groups) {
      if (group.length < 2) continue;
      const [a, b] = pair.split("|").map((k) => centers.get(k));
      const len = a && b ? Math.hypot(b.x - a.x, b.y - a.y) : 0;
      if (!len) continue;
      const nx = -(b.y - a.y) / len, ny = (b.x - a.x) / len;
      const spots = offsets(group.length);
      group.sort((p, q) => p.id - q.id).forEach((link, i) => {
        out.push({ id: link.id, bend: { x: Math.round(nx * spots[i] * 2), y: Math.round(ny * spots[i] * 2) } });
      });
    }
    return out;
  }

  //: The links on this board as {id, sketch, data}, locked and hidden ones left out.
  function boardLinks() {
    const out = [];
    for (const sketch of wbState.sketches || []) {
      if (!wbIsLinkSketch(sketch) || wbIsLocked("sketch", sketch) || wbItemHidden("sketch", sketch)) continue;
      const data = wbSketchData(sketch);
      if (data) out.push({ id: sketch.id, sketch, data });
    }
    return out;
  }

  function centersOf(links) {
    const centers = new Map();
    for (const { data } of links) {
      for (const [kind, id] of [[data.sourceKind || "node", data.sourceId], [data.targetKind || "node", data.targetId]]) {
        const key = keyOf(kind, id);
        if (centers.has(key) || id == null) continue;
        const item = wbFindItem(kind, id);
        const box = item && wbItemBBox(kind, item);
        if (box) centers.set(key, wbBoxCenter(box));
      }
    }
    return centers;
  }

  //: Which pairs the command works on: the pairs of the selected connectors, then of the selected shapes among
  //: themselves, and with nothing selected every pair on the board.
  function pairsWanted(links) {
    const picked = wbSelectedKeys();
    if (!picked.size) return null;
    const out = new Set();
    for (const { id, data } of links) {
      if (picked.has(keyOf("sketch", id)) && data.sourceId != null && data.targetId != null) out.add(pairOf(data));
      else if (picked.has(keyOf(data.sourceKind, data.sourceId)) && picked.has(keyOf(data.targetKind, data.targetId))) out.add(pairOf(data));
    }
    return out;
  }

  function currentPlan() {
    const links = boardLinks();
    return { links, steps: plan(links, centersOf(links), pairsWanted(links)) };
  }

  //: Whether the command has anything to do now (the menus and the palette grey it out otherwise).
  const canSpread = () => currentPlan().steps.length > 0;

  async function spread() {
    const { links, steps } = currentPlan();
    if (!steps.length) {
      toast("No two connectors join the same pair of shapes here, or the ones that do have bends of their own.");
      return 0;
    }
    const byId = new Map(links.map((l) => [l.id, l]));
    //: One request for every connector (test_board_selection_batches); the gesture still reads the change as one Undo.
    await wbRecordGesture(async () => {
      const rows = [];
      for (const step of steps) {
        const { sketch } = byId.get(step.id);
        if (wbSketchSetProps(sketch, { bend: step.bend.x || step.bend.y ? step.bend : undefined })) rows.push({ kind: "sketch", item: sketch });
      }
      await wbSaveMany(rows);
    });
    wbScheduleRender();
    const said = `Spaced ${nounCount(steps.length, "connector")} that share their ends.`;
    wbAnnounce(said);
    toast(said);
    return steps.length;
  }

  //: Pure: a connector's fields after the layout is mirrored about `sum` along `axis` ("h" mirrors x about the
  //: line whose x-sum is `sum`; "v" mirrors y). `moved` holds the keys of the shapes that were carried over.
  //: Anchors on a carried shape flip with it, so a line that left a shape's right side still leaves toward
  //: the other shape; the bends, free ends and the bow are mirrored only when every end the line has is
  //: on a carried shape (or the line is itself picked), so a line to a shape left behind keeps its path.
  function mirrored(data, axis, sum, moved, picked) {
    const h = axis === "h";
    const flip = (p) => (h ? { ...p, x: Math.round((sum - p.x) * 100) / 100 } : { ...p, y: Math.round((sum - p.y) * 100) / 100 });
    const anchor = (a) => (a && Number.isFinite(a.x) && Number.isFinite(a.y)
      ? (h ? { ...a, x: Math.round((1 - a.x) * 1e4) / 1e4, dx: a.dx ? -a.dx : a.dx } : { ...a, y: Math.round((1 - a.y) * 1e4) / 1e4, dy: a.dy ? -a.dy : a.dy })
      : a);
    const ends = [["source", data.sourceKind, data.sourceId], ["target", data.targetKind, data.targetId]];
    const attached = ends.filter((e) => e[2] != null);
    const carried = attached.filter((e) => moved.has(keyOf(e[1], e[2])));
    const patch = {};
    for (const [name] of carried) if (data[`${name}Anchor`]) patch[`${name}Anchor`] = anchor(data[`${name}Anchor`]);
    if (attached.length ? carried.length === attached.length : picked) {
      if (Array.isArray(data.points) && data.points.length) patch.points = data.points.map(flip);
      for (const [name, , id] of ends) if (id == null && data[`${name}Point`]) patch[`${name}Point`] = flip(data[`${name}Point`]);
      if (data.bend && (data.bend.x || data.bend.y)) patch.bend = h ? { x: -data.bend.x, y: data.bend.y } : { x: data.bend.x, y: -data.bend.y };
    }
    //: A loop leaves one side of its shape: left becomes right, or top bottom.
    const opposite = h ? { left: "right", right: "left" } : { top: "bottom", bottom: "top" };
    const sides = wbFmtState.drawMore?.SIDES;
    if (data.loop && opposite[data.loop] && sides && carried.length) {
      patch.loop = opposite[data.loop];
      patch.sourceAnchor = sides[patch.loop].start;
      patch.targetAnchor = sides[patch.loop].end;
    }
    return patch;
  }

  //: The mirror line's sum for a set of boxes: where a box with edges (a, b) lands is sum - b to sum - a.
  function mirrorSum(boxes, axis) {
    const lo = Math.min(...boxes.map((b) => (axis === "h" ? b.minX : b.minY)));
    const hi = Math.max(...boxes.map((b) => (axis === "h" ? b.maxX : b.maxY)));
    return lo + hi;
  }

  function flippable() {
    return wbSelectionEntries().filter((e) => !wbIsLocked(e.kind, e.item) && !wbItemHidden(e.kind, e.item));
  }

  //: Flip the layout: the selected shapes swap places across the middle of the group, one undo step.
  async function flipLayout(axis) {
    const entries = flippable();
    if (entries.length < 2) {
      toast("Select two or more shapes to flip their layout.");
      return 0;
    }
    const sum = mirrorSum(entries.map((e) => e.bbox), axis);
    const moved = new Set(entries.map((e) => keyOf(e.kind, e.id)));
    const picked = wbSelectedKeys();
    await wbRecordGesture(async () => {
      const rows = [];
      for (const e of entries) {
        const dx = axis === "h" ? sum - (e.bbox.minX + e.bbox.maxX) : 0;
        const dy = axis === "v" ? sum - (e.bbox.minY + e.bbox.maxY) : 0;
        if (Math.abs(dx) < 0.5 && Math.abs(dy) < 0.5) continue;
        wbMoveItemBy(e.kind, e.id, e.item, dx, dy, rows);
      }
      await wbSaveMany(rows);
      const links = [];
      for (const { id, sketch, data } of boardLinks()) {
        const patch = mirrored(data, axis, sum, moved, picked.has(keyOf("sketch", id)));
        if (Object.keys(patch).length && wbSketchSetProps(sketch, patch)) links.push({ kind: "sketch", item: sketch });
      }
      await wbSaveMany(links);
    });
    wbScheduleRender();
    const said = axis === "h" ? `Flipped the layout of ${nounCount(entries.length, "shape")} left to right.` : `Flipped the layout of ${nounCount(entries.length, "shape")} top to bottom.`;
    wbAnnounce(said);
    toast(said);
    return entries.length;
  }

  wbFmtState.arrangeMore = { GAP, offsets, spreadable, plan, canSpread, spread, mirrored, mirrorSum, flipLayout };
})();
