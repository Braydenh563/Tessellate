(() => {
  // whiteboard-connectors.js: connection anchors, link routing and the connector panel.
  // Moved out of whiteboard.js whole (L286) and wrapped: only what other files call goes on `window`; nothing here runs at load.
  //: Real anchor/connection points for links (asked for directly, "take
  //: inspiration from draw.io", named "worth its own session" three sessions
  //: running: HANDOVER.md §53-55). Eight **fixed** points (corners + edge
  //: midpoints), as fractions of the shape's own bounding box so a resize
  //: carries an anchor with it for free, no migration needed, these two
  //: fractions just live as `sourceAnchor`/`targetAnchor` keys in the link
  //: sketch's existing `data` JSON blob. Omitting either key is the **free**
  //: case: that end "floats", auto-following the rectangle border facing
  //: whatever the other end resolves to, every render, draw.io's own
  //: behaviour, not a fixed centre-point offset.
  const WB_FIXED_ANCHORS = [
    { x: 0, y: 0 }, { x: 0.5, y: 0 }, { x: 1, y: 0 },
    { x: 1, y: 0.5 }, { x: 1, y: 1 }, { x: 0.5, y: 1 },
    { x: 0, y: 1 }, { x: 0, y: 0.5 },
  ];

  //: A link only ever connects nodes (cards) today: see `dragEndNode`'s own
  //: hit-test: but takes `kind` rather than assuming "node" so a future
  //: object-to-object link doesn't need this rewritten.
  //: **Endpoints follow rotation.** Reported with a screenshot: "if I rotate
  //: a textbox or shape, the connections no longer fit to the edge and just
  //: float in mid air." Cards and objects store `rotation` (degrees, about
  //: the box centre) and were measured as their *unrotated* box; a drawn
  //: shape bakes its rotation into the path, so its axis-aligned bbox is a
  //: superset of the shape and a ray to the bbox edge stops short of it.
  //: Two plain pieces of geometry fix both: rotate a point about a centre, and
  //: intersect a ray with the shape's own outline.
  function wbItemRotation(kind, item) {
    if (kind === "sketch") return 0;
    const deg = Number(item?.rotation);
    return Number.isFinite(deg) ? deg : 0;
  }

  function wbRotatePoint(pt, center, deg) {
    if (!deg) return pt;
    const rad = (deg * Math.PI) / 180;
    const cos = Math.cos(rad), sin = Math.sin(rad);
    const dx = pt.x - center.x, dy = pt.y - center.y;
    return { x: center.x + dx * cos - dy * sin, y: center.y + dx * sin + dy * cos };
  }

  function wbBoxCenter(box) {
    return { x: (box.minX + box.maxX) / 2, y: (box.minY + box.maxY) / 2 };
  }

  //: The straight segments of a path, for hit-testing a ray against a drawn
  //: shape. Curves (the circle tool's arcs) contribute their endpoints only;
  //: the bbox fallback in `wbEdgePoint` covers a shape with no usable segment.
  function wbPathPolyline(d) {
    const tokens = (d || "").match(/[MLCHVAZmlchvaz]|-?\d*\.?\d+(?:[eE]-?\d+)?/g);
    if (!tokens) return [];
    const segs = [];
    let i = 0, px = 0, py = 0, sx = 0, sy = 0, cmd = "";
    const num = () => parseFloat(tokens[i++]);
    const lineTo = (x, y) => { segs.push([px, py, x, y]); px = x; py = y; };
    while (i < tokens.length) {
      if (/^[A-Za-z]$/.test(tokens[i])) cmd = tokens[i++];
      if (i >= tokens.length && cmd !== "Z" && cmd !== "z") break;
      switch (cmd) {
        case "M": px = num(); py = num(); sx = px; sy = py; cmd = "L"; break;
        case "m": px += num(); py += num(); sx = px; sy = py; cmd = "l"; break;
        case "L": lineTo(num(), num()); break;
        case "l": { const x = px + num(); lineTo(x, py + num()); break; }
        case "H": lineTo(num(), py); break;
        case "h": lineTo(px + num(), py); break;
        case "V": lineTo(px, num()); break;
        case "v": lineTo(px, py + num()); break;
        case "C": i += 4; lineTo(num(), num()); break;
        case "c": { i += 4; const x = px + num(); lineTo(x, py + num()); break; }
        case "A": i += 5; lineTo(num(), num()); break;
        case "a": { i += 5; const x = px + num(); lineTo(x, py + num()); break; }
        case "Z": case "z": lineTo(sx, sy); cmd = ""; break;
        default: i += 1;
      }
    }
    return segs;
  }

  //: Where a line from an item's centre toward (towardX, towardY) leaves the
  //: item: on its rotated border for a card or text box, on its own outline
  //: for a drawn shape.
  function wbEdgePoint(kind, item, towardX, towardY) {
    const box = wbItemBBox(kind, item);
    if (!box) return null;
    const c = wbBoxCenter(box);
    if (kind === "sketch") {
      const parsed = typeof item._dragLiveD === "string" ? { d: item._dragLiveD } : wbSketchParsedData(item);
      const segs = parsed ? wbPathPolyline(parsed.d) : [];
      const dx = towardX - c.x, dy = towardY - c.y;
      if (segs.length && (dx || dy)) {
        // Ray c + t·(dx,dy), t ≥ 0, against each segment; nearest hit wins.
        let best = null;
        for (const [x1, y1, x2, y2] of segs) {
          const ex = x2 - x1, ey = y2 - y1;
          const den = dx * ey - dy * ex;
          if (Math.abs(den) < 1e-9) continue;
          const t = ((x1 - c.x) * ey - (y1 - c.y) * ex) / den;
          const u = ((x1 - c.x) * dy - (y1 - c.y) * dx) / den;
          if (t >= 0 && u >= 0 && u <= 1 && (best === null || t < best)) best = t;
        }
        if (best !== null) return { x: c.x + dx * best, y: c.y + dy * best };
      }
      return wbBoxRayIntersection(box, towardX, towardY);
    }
    const rot = wbItemRotation(kind, item);
    let shape = "rectangle";
    if (kind === "object") shape = item.data?.shape || "rectangle";
    else if (kind === "node") shape = item.shape || "rectangle";
  
    const getIntersection = (bx, tx, ty) => {
      if (shape === "ellipse") return wbEllipseRayIntersection(bx, tx, ty);
      if (shape === "pill") return wbPillRayIntersection(bx, tx, ty);
      return wbBoxRayIntersection(bx, tx, ty);
    };

    if (!rot) return getIntersection(box, towardX, towardY);
    const local = wbRotatePoint({ x: towardX, y: towardY }, c, -rot);
    return wbRotatePoint(getIntersection(box, local.x, local.y), c, rot);
  }

  //: The direction a curved link should leave an endpoint in: the box's face
  //: normal for an upright card, the outward radial for anything rotated or
  //: drawn (whose faces are not axis-aligned).
  function wbItemEdgeDir(kind, item, pt) {
    const box = wbItemBBox(kind, item);
    if (!box || !pt) return null;
    if (kind !== "sketch" && !wbItemRotation(kind, item)) return wbEdgeNormal(box, pt);
    const c = wbBoxCenter(box);
    const len = Math.hypot(pt.x - c.x, pt.y - c.y);
    return len ? { x: (pt.x - c.x) / len, y: (pt.y - c.y) / len } : null;
  }

  //: **An item's connection points, on its own outline** (wb-phase2 step 5;
  //: draw.io's fixed ports). A card, a text box and a rectangle keep the eight
  //: of `WB_FIXED_ANCHORS`. A drawn polygon (a diamond, a triangle, a custom
  //: shape of straight sides) has its corners and the middle of each side, so
  //: a diamond's are its four tips and four side middles rather than the four
  //: corners of its box, which float off it; a curved outline (an ellipse) has
  //: the eight compass points where it actually is. Each is a fraction of the
  //: box, which is how a link stores it (`sourceAnchor`), so a resize carries
  //: it and nothing stored changes shape.
  const wbPortCache = new Map();

  function wbPortFractions(kind, item) {
    //: A table's points are the two ends of each row (draw.io's east-west port on a table row), see whiteboard-shape-more.js.
    if (kind === "object" && item.kind === "table" && wbFmtState.shapeMore) return wbFmtState.shapeMore.tableRowPorts(wbTableRules.wbTableRowWeights(item));
    if (kind !== "sketch") return WB_FIXED_ANCHORS;
    const parsed = wbSketchParsedData(item);
    if (!parsed || typeof parsed.d !== "string") return WB_FIXED_ANCHORS;
    //: A converted draw.io shape carries its stencil's own ports (decision 2
    //: of the draw.io programme): those are where its author put them, so they
    //: come before anything guessed from the path.
    if (Array.isArray(parsed.ports) && parsed.ports.length) {
      const own = parsed.ports.filter((q) => Number.isFinite(q?.x) && Number.isFinite(q?.y));
      //: A port flagged `perimeter` is held on the outline, wherever the box has been resized to (`snapToOutline`).
      if (own.some((q) => q.perimeter)) {
        const held = wbPortCache.get(item.id);
        if (held && held.d === parsed.d && held.own === parsed.ports) return held.ports;
        const ports = own.map((q) => (q.perimeter ? wbFmtState.drawMore?.snapToOutline(q, parsed.d) || q : q));
        wbPortCache.set(item.id, { d: parsed.d, own: parsed.ports, ports });
        return ports;
      }
      if (own.length) return own;
    }
    const cached = wbPortCache.get(item.id);
    if (cached && cached.d === parsed.d) return cached.ports;
    const ports = wbPortsForPath(parsed.d, WB_FILLABLE_SHAPES.has(parsed.shape)) || WB_FIXED_ANCHORS;
    wbPortCache.set(item.id, { d: parsed.d, ports });
    return ports;
  }

  //: Pure (node-tested): the ports of a path as fractions of its box, or null
  //: when it is not a closed outline worth porting (an open stroke).
  function wbPortsForPath(d, shaped = false) {
    const box = wbPathBBox(d);
    if (!box) return null;
    const w = box.maxX - box.minX || 1, h = box.maxY - box.minY || 1;
    const frac = (p) => ({ x: Math.round(((p.x - box.minX) / w) * 1e4) / 1e4, y: Math.round(((p.y - box.minY) / h) * 1e4) / 1e4 });
    const curved = /[CcQqAaSsTt]/.test(d);
    const closed = /[Zz]\s*$/.test(String(d).trim());
    if (!closed && !shaped) return null;
    if (!curved) {
      const segs = wbPathPolyline(d).filter(([x1, y1, x2, y2]) => Math.hypot(x2 - x1, y2 - y1) > 0.5);
      if (segs.length >= 3 && segs.length <= 12) {
        const out = [];
        const add = (p) => {
          const f = frac(p);
          if (!out.some((q) => Math.abs(q.x - f.x) < 0.02 && Math.abs(q.y - f.y) < 0.02)) out.push(f);
        };
        for (const [x1, y1] of segs) add({ x: x1, y: y1 });
        for (const [x1, y1, x2, y2] of segs) add({ x: (x1 + x2) / 2, y: (y1 + y2) / 2 });
        return out;
      }
    }
    //: A curve: where the outline is at the eight compass points of its box's
    //: inscribed ellipse (an ellipse drawn by the tool is exactly that).
    const out = [];
    for (let i = 0; i < 8; i += 1) {
      const t = (i * Math.PI) / 4;
      out.push(frac({ x: box.minX + w * (0.5 + 0.5 * Math.cos(t)), y: box.minY + h * (0.5 + 0.5 * Math.sin(t)) }));
    }
    return out;
  }

  //: An item's connection points, in board space, rotated with it.
  function wbAnchorPositions(kind, item) {
    const box = wbItemBBox(kind, item);
    if (!box) return [];
    const w = box.maxX - box.minX, h = box.maxY - box.minY;
    const c = wbBoxCenter(box);
    const rot = wbItemRotation(kind, item);
    return wbPortFractions(kind, item).map((a) => {
      //: A port may carry a pixel offset from its place in the box (`dx`, `dy`; draw.io's `points` offsets).
      const pt = wbRotatePoint({ x: box.minX + a.x * w + (Number(a.dx) || 0), y: box.minY + a.y * h + (Number(a.dy) || 0) }, c, rot);
      return { anchor: a, x: pt.x, y: pt.y };
    });
  }

  //: Where a stored anchor is: read from its fraction, not looked up among
  //: the item's current ports, so a link anchored before an item's ports
  //: changed (a box corner on an ellipse) keeps its end where it was.
  function wbAnchorPoint(kind, item, anchor) {
    if (!anchor || !Number.isFinite(anchor.x) || !Number.isFinite(anchor.y)) return null;
    const box = wbItemBBox(kind, item);
    if (!box) return null;
    const pt = { x: box.minX + anchor.x * (box.maxX - box.minX) + (Number(anchor.dx) || 0), y: box.minY + anchor.y * (box.maxY - box.minY) + (Number(anchor.dy) || 0) };
    return wbRotatePoint(pt, wbBoxCenter(box), wbItemRotation(kind, item));
  }

  //: The nearest of the 8 fixed points to a board-coordinate click, or `null`
  //: if none is within `thresholdPx`, `null` is the caller's cue to persist
  //: no anchor at all (the free/floating case) rather than a distant one.
  function wbNearestAnchor(kind, item, px, py, thresholdPx = 16) {
    let best = null, bestDist = thresholdPx;
    for (const p of wbAnchorPositions(kind, item)) {
      const d = Math.hypot(px - p.x, py - p.y);
      if (d <= bestDist) { bestDist = d; best = p.anchor; }
    }
    return best;
  }

  //: The standard rectangle/ray intersection: where the line from this box's
  //: centre toward `(towardX, towardY)` crosses the box's own border. This is
  //: what a "floating" end actually resolves to each render, aimed at the
  //: other end's real point, not always the other shape's centre.
  //: **Which edge an endpoint sits on, as an outward unit vector.** This is
  //: what makes a connector leave a card perpendicular to the side it is
  //: attached to, instead of always leaving horizontally.
  //:
  //: Reported directly: "links don't change in their direction based off the
  //: edge they are connected to and where the other end is coming from." Two
  //: separate faults produced that, and this function is the input to both
  //: fixes (see `wbLinkPathD`).
  //:
  //: Snapped to one axis rather than used as a raw radial vector: a connector
  //: that leaves a rectangle at 37 degrees because that is where the anchor
  //: happens to be reads as sloppy, where one that leaves squarely off the top
  //: edge reads as deliberate. The dominant axis is chosen by comparing the
  //: offset from centre against the box's own half-extents, so a wide, short
  //: card still resolves its short edges correctly.
  function wbEdgeNormal(box, pt) {
    if (!box || !pt) return null;
    const halfW = (box.maxX - box.minX) / 2 || 1;
    const halfH = (box.maxY - box.minY) / 2 || 1;
    const dx = (pt.x - (box.minX + box.maxX) / 2) / halfW;
    const dy = (pt.y - (box.minY + box.maxY) / 2) / halfH;
    if (!dx && !dy) return null;
    if (Math.abs(dx) >= Math.abs(dy)) return { x: Math.sign(dx) || 1, y: 0 };
    return { x: 0, y: Math.sign(dy) || 1 };
  }

  //: Attach a direction to an endpoint without changing its shape, so every
  //: existing `wbLinkPathD(type, endpoints.source, …)` call site keeps working
  //: and simply gains the better curve. An endpoint with no direction (a free
  //: dangling point, or the live drag preview) falls back to the old
  //: behaviour.
  function wbWithDir(pt, dir) {
    return dir ? { x: pt.x, y: pt.y, dir } : pt;
  }

  //: A link's resolved end for the path: the point, the side it leaves by,
  //: and for an elbow (`wbElbowRoute`) the box it must go round and whether
  //: the end floats (no fixed anchor), which an elbow settles on the facing
  //: side's middle. A fresh object every time, never the stored free point.
  function wbLinkEnd(pt, dir, box, floating) {
    const end = { x: pt.x, y: pt.y };
    if (dir) end.dir = dir;
    if (box) end.box = box;
    if (floating) end.floating = true;
    return end;
  }

  function wbEllipseRayIntersection(box, towardX, towardY) {
    const cx = (box.minX + box.maxX) / 2, cy = (box.minY + box.maxY) / 2;
    const dx = towardX - cx, dy = towardY - cy;
    if (!dx && !dy) return { x: cx, y: cy };
    const a = (box.maxX - box.minX) / 2, b = (box.maxY - box.minY) / 2;
    if (a === 0 || b === 0) return { x: cx, y: cy };
    const t = 1 / Math.sqrt((dx * dx) / (a * a) + (dy * dy) / (b * b));
    return { x: cx + dx * t, y: cy + dy * t };
  }

  function wbPillRayIntersection(box, towardX, towardY) {
    const cx = (box.minX + box.maxX) / 2, cy = (box.minY + box.maxY) / 2;
    const dx = towardX - cx, dy = towardY - cy;
    if (!dx && !dy) return { x: cx, y: cy };
    const w = box.maxX - box.minX, h = box.maxY - box.minY;
    const r = Math.min(w, h) / 2;
    const pt = wbBoxRayIntersection(box, towardX, towardY);
    if (w > h) {
      if (pt.x > box.minX + r && pt.x < box.maxX - r) return pt;
      const circleCx = pt.x <= box.minX + r ? box.minX + r : box.maxX - r;
      const dcx = cx - circleCx;
      const a = dx * dx + dy * dy;
      const b = 2 * (dcx * dx);
      const c = dcx * dcx - r * r;
      const discriminant = b * b - 4 * a * c;
      if (discriminant >= 0) {
        const t = (-b + Math.sqrt(discriminant)) / (2 * a);
        return { x: cx + dx * t, y: cy + dy * t };
      }
    } else {
      if (pt.y > box.minY + r && pt.y < box.maxY - r) return pt;
      const circleCy = pt.y <= box.minY + r ? box.minY + r : box.maxY - r;
      const dcy = cy - circleCy;
      const a = dx * dx + dy * dy;
      const b = 2 * (dcy * dy);
      const c = dcy * dcy - r * r;
      const discriminant = b * b - 4 * a * c;
      if (discriminant >= 0) {
        const t = (-b + Math.sqrt(discriminant)) / (2 * a);
        return { x: cx + dx * t, y: cy + dy * t };
      }
    }
    return pt;
  }

  function wbBoxRayIntersection(box, towardX, towardY) {
    const cx = (box.minX + box.maxX) / 2, cy = (box.minY + box.maxY) / 2;
    const dx = towardX - cx, dy = towardY - cy;
    if (!dx && !dy) return { x: cx, y: cy };
    const halfW = (box.maxX - box.minX) / 2, halfH = (box.maxY - box.minY) / 2;
    const t = Math.min(dx ? halfW / Math.abs(dx) : Infinity, dy ? halfH / Math.abs(dy) : Infinity);
    return { x: cx + dx * t, y: cy + dy * t };
  }

  //: The two real endpoints of a link, shared by the render path
  //: (`sketchUpdate.each`) and the per-drag-frame follow (`wbUpdateLinkedSketches`)
  //: so the two can't drift apart: same reasoning as that function's own
  //: comment, just extended to real anchors instead of a hardcoded centre.
  //: A fixed end resolves to its own point regardless of the other end; a
  //: floating end resolves toward whatever the *other* end actually is (its
  //: fixed point if it has one, its centre otherwise), not always the centre.
  //: **A link end is a card *or a text object*.** Reported: "I cant even link
  //: connections to text boxes or sticky notes." Every end was hard-wired to
  //: `wbState.nodes`; a link stores `sourceKind`/`targetKind` now ("node" when
  //: absent, so every existing link reads exactly as before) and both ends
  //: resolve through the one lookup below.
  //: Whether this row has anything to draw *now*.
  //:
  //: Reported: a node with "a dangling curved edge to nowhere". Deleting one
  //: end of a cross-link removes the link's row on the server (every delete
  //: route calls `_forget_links_to`) but the client kept its own copy, and the
  //: render then set the path's `d` to `""` and left the `<g>` on the canvas -
  //: measured: three nodes and one cross-link, delete one end, and the group is
  //: still there with an empty path. An empty path draws nothing, but the group
  //: is still a hit target and still carries the link's classes, and the next
  //: thing to give a `.sketch-group` a decoration would have made it visible.
  //:
  //: Filtering the data join instead of blanking the path means d3's own
  //: `exit().remove()` takes the element away, which is the mechanism that
  //: already exists for "this is no longer on the board". The row itself is the
  //: server's business: `_drop_orphan_links` deletes it on the next board load.
  function wbSketchIsDrawable(sketch) {
    let parsed = null;
    try {
      parsed = JSON.parse(sketch.data || "{}");
    } catch {
      return true; // not ours to judge, a stroke, or a row we cannot read
    }
    if (!parsed || !String(parsed.type || "").startsWith("link-")) return true;
    //: Ids only, deliberately, the same rule the server's `_drop_orphan_links`
    //: applies. Asking `wbResolveLinkEndpoints` instead would drag the DOM into
    //: this: it measures an item's box, which is null for anything not painted
    //: yet, so a link would vanish on the first render of a board and reappear
    //: on the second. A free end (`sourcePoint`/`targetPoint`) is a feature and
    //: stays; only an end that names an id which is gone is an orphan.
    for (const [id, kind] of [
      [parsed.sourceId, parsed.sourceKind || "node"],
      [parsed.targetId, parsed.targetKind || "node"],
    ]) {
      if (id == null) continue;
      if (!wbLinkItem(kind, id)) return false;
    }
    return true;
  }

  //: **One lookup table per list, not a scan per link end**
  //: (MINDMAP_PLAN.md §13a). `wbUpdateLinkedSketches` calls this twice for every
  //: link touching a moved item, on every frame of the gesture, so the `.find`
  //: this replaces was the whole object list walked twice per link per frame:
  //: measured on `mapperf.js`'s own link fixture at 500 topics, a branch drag
  //: over 300 link sketches had a 183.3ms worst frame with the list scanned and
  //: 33.3ms with it indexed.
  //:
  //: **Keyed on the array itself, so it cannot go stale by being replaced.**
  //: Every list on `wbState` is either mutated by push or replaced wholesale by
  //: a `filter`, and a replacement is a different array, which is a different
  //: key in this WeakMap and therefore a fresh index. The length guard covers
  //: the push. The one case neither covers is an element replaced in place at
  //: the same length, which happens in exactly one place (a card re-posted onto
  //: its own row), and that place drops the entry by hand.
  const wbLinkItemIndex = new WeakMap();

  function wbForgetLinkItems(list) {
    wbLinkItemIndex.delete(list);
  }

  function wbLinkItem(kind, id) {
    if (id == null) return null;
    const list = kind === "object" ? (wbState.objects || [])
      : kind === "sketch" ? (wbState.sketches || [])
      : wbState.nodes;
    let held = wbLinkItemIndex.get(list);
    if (!held || held.size !== list.length) {
      held = { size: list.length, byId: new Map(list.map((i) => [i.id, i])) };
      wbLinkItemIndex.set(list, held);
    }
    return held.byId.get(id) || null;
  }

  //: Everything a link can start from or land on: cards, text boxes and
  //: stickies, and every drawn shape (a link is a sketch too, and is never a
  //: target). Reported: "only notes light up with edge anchor points... and
  //: nothing else like shapes, sticky notes and text boxes."
  function wbLinkCandidates(excludeKind, excludeId) {
    const out = [];
    for (const n of wbState.nodes) out.push(["node", n]);
    //: Map topics count too (INBOX 177: "one of my mindmap nodes isnt linked to
    //: anything, so I tried to use the link tools like the curbved link tools
    //: and they didnt work"). A topic is an object like a text box is; only
    //: `kind === "text"` was offered, so on a mind map the link tools found
    //: nothing to start from and nothing to land on, which reads as the tool
    //: being broken.
    for (const o of wbState.objects || []) {
      if (o.kind === "text" || WB_MAP_KINDS.has(o.kind)) out.push(["object", o]);
    }
    for (const sk of wbState.sketches || []) {
      const parsed = wbSketchParsedData(sk);
      if (!parsed || (parsed.type || "").startsWith("link-")) continue;
      out.push(["sketch", sk]);
    }
    return out.filter(([kind, item]) => !(kind === excludeKind && item.id === excludeId));
  }

  //: Is a board point inside an item, in the item's own rotated frame, not
  //: its axis-aligned box. Reported: "hard to put connections on objects that
  //: are rotated as the connection points and borders constantly flicker", 
  //: the pointer crossed in and out of the unrotated box while visibly over
  //: (or off) the rotated card, so the hints came and went with every move.
  function wbPointInItem(kind, item, x, y, tol = 0) {
    const box = wbItemBBox(kind, item);
    if (!box) return false;
    const rot = wbItemRotation(kind, item);
    const p = rot ? wbRotatePoint({ x, y }, wbBoxCenter(box), -rot) : { x, y };
    return p.x >= box.minX - tol && p.x <= box.maxX + tol && p.y >= box.minY - tol && p.y <= box.maxY + tol;
  }

  //: **What an Arrow-tool end binds to** (dogfood 2026-10-25 item 6). A
  //: closed shape, a card or a map topic under the point, or within `tol` board
  //: units of its edge: an arrow ended on a shape's border sat a pixel outside
  //: its box and stayed a loose path that did not follow the shape. Pen
  //: strokes and lines are never a target (a scribble is not a thing to join).
  function wbArrowCandidateAt(x, y, tol) {
    const candidates = wbLinkCandidates().reverse();
    for (const [kind, item] of candidates) {
      if (kind === "sketch" && !wbSketchIsClosedShape(item)) continue;
      if (wbPointInItem(kind, item, x, y, tol)) return [kind, item];
    }
    return null;
  }

  //: The Arrow tool's stroke as a bound connector, or null when neither end is
  //: on anything (then it stays the free path it always was). A bound end keeps
  //: the shape id and, near one of its connection points, that point; away from
  //: them it floats and resolves to the shape's edge facing the other end, so
  //: the head meets the border rather than ending inside the shape. A shape
  //: that is moved, resized or turned drags the arrow with it, as a port-drawn
  //: connector does. Both ends on one shape stay a free arrow.
  function wbBoundArrowData(sx, sy, x, y, tol, blob) {
    const from = wbArrowCandidateAt(sx, sy, tol);
    const to = wbArrowCandidateAt(x, y, tol);
    if (!from && !to) return null;
    if (from && to && from[0] === to[0] && from[1].id === to[1].id) return null;
    const data = { type: "link-straight", color: blob.color, width: blob.width };
    for (const key of ["dash", "noStroke", "startCap", "endCap"]) if (blob[key] !== undefined) data[key] = blob[key];
    const end = (hit, px, py, name) => {
      if (!hit) {
        data[`${name}Point`] = { x: Math.round(px), y: Math.round(py) };
        return;
      }
      data[`${name}Id`] = hit[1].id;
      if (hit[0] !== "node") data[`${name}Kind`] = hit[0];
      const anchor = wbNearestAnchor(hit[0], hit[1], px, py, tol * 1.6);
      if (anchor) data[`${name}Anchor`] = anchor;
    };
    end(from, sx, sy, "source");
    end(to, x, y, "target");
    return data;
  }

  function wbLinkCandidateAt(x, y, excludeKind, excludeId) {
    // Topmost first: objects and cards paint above sketches, and a later
    // sibling above an earlier one.
    const candidates = wbLinkCandidates(excludeKind, excludeId).reverse();
    for (const [kind, item] of candidates) {
      if (wbPointInItem(kind, item, x, y)) return [kind, item];
    }
    return null;
  }

  //: `aim` is a straight or curved link's first and last waypoints: a floating
  //: end leaves its shape facing the waypoint it runs to, not the far end.
  function wbLinkEndpoints(sourceItem, sourceAnchor, targetItem, targetAnchor, sourceKind = "node", targetKind = "node", aim = null) {
    const sourceBox = wbItemBBox(sourceKind, sourceItem);
    const targetBox = wbItemBBox(targetKind, targetItem);
    if (!sourceBox || !targetBox) return null;
    const sourceCenter = wbBoxCenter(sourceBox);
    const targetCenter = wbBoxCenter(targetBox);
    const fixedSource = wbAnchorPoint(sourceKind, sourceItem, sourceAnchor);
    const fixedTarget = wbAnchorPoint(targetKind, targetItem, targetAnchor);
    const towardTarget = aim?.source || fixedTarget || targetCenter;
    const towardSource = aim?.target || fixedSource || sourceCenter;
    const source = fixedSource || wbEdgePoint(sourceKind, sourceItem, towardTarget.x, towardTarget.y);
    const target = fixedTarget || wbEdgePoint(targetKind, targetItem, towardSource.x, towardSource.y);
    return {
      source: wbLinkEnd(source, wbItemEdgeDir(sourceKind, sourceItem, source), sourceBox, !fixedSource),
      target: wbLinkEnd(target, wbItemEdgeDir(targetKind, targetItem, target), targetBox, !fixedTarget),
    };
  }

  //: A link end is either attached to a card (`sourceId`/`targetId`, plus an
  //: optional fixed `sourceAnchor`/`targetAnchor` fraction: the existing
  //: shape) or a free "dangling" point in board space with no card at all
  //: (`sourcePoint`/`targetPoint`, `{x, y}`, asked for directly: "even make
  //: it a dangling unattached point not attached to an object"). Both ends
  //: independently resolved here so any combination, node/node (the
  //: original case), node/free, or free/free, renders through one path.
  //: Returns `null` for a stale reference (a card end whose id no longer
  //: exists), same as the two call sites already treated a missing node.
  function wbResolveLinkEndpoints(parsed) {
    const sourceKind = parsed.sourceKind || "node";
    const targetKind = parsed.targetKind || "node";
    const sourceNode = wbLinkItem(sourceKind, parsed.sourceId);
    const targetNode = wbLinkItem(targetKind, parsed.targetId);
    if (parsed.sourceId != null && !sourceNode) return null;
    if (parsed.targetId != null && !targetNode) return null;
    if (!sourceNode && !parsed.sourcePoint) return null;
    if (!targetNode && !parsed.targetPoint) return null;
    const way = !["elbow", "er", "iso"].includes(parsed.route) && Array.isArray(parsed.points) && parsed.points.length ? parsed.points : null;
    const aim = way ? { source: way[0], target: way[way.length - 1] } : null;
    if (sourceNode && targetNode) {
      return wbLinkEndpoints(sourceNode, parsed.sourceAnchor, targetNode, parsed.targetAnchor, sourceKind, targetKind, aim);
    }
    if ((sourceNode && !wbItemBBox(sourceKind, sourceNode)) || (targetNode && !wbItemBBox(targetKind, targetNode))) return null;

    const sourceBox = sourceNode ? wbItemBBox(sourceKind, sourceNode) : null;
    const targetBox = targetNode ? wbItemBBox(targetKind, targetNode) : null;
    // A free point is always fixed, there's no card border for it to "aim
    // toward" the way a floating card-end resolves. A card-end with no fixed
    // anchor of its own still floats toward whatever the other end actually
    // is, same as the node/node case.
    const sourceFixed = sourceNode ? wbAnchorPoint(sourceKind, sourceNode, parsed.sourceAnchor) : parsed.sourcePoint;
    const targetFixed = targetNode ? wbAnchorPoint(targetKind, targetNode, parsed.targetAnchor) : parsed.targetPoint;
    const targetCenter = targetBox && wbBoxCenter(targetBox);
    const sourceCenter = sourceBox && wbBoxCenter(sourceBox);
    const towardTarget = aim?.source || targetFixed || targetCenter;
    const towardSource = aim?.target || sourceFixed || sourceCenter;
    const source = sourceFixed || wbEdgePoint(sourceKind, sourceNode, towardTarget.x, towardTarget.y);
    const target = targetFixed || wbEdgePoint(targetKind, targetNode, towardSource.x, towardSource.y);
    // Only a card end has an edge to leave perpendicular to. A free dangling
    // point has no box, so it keeps the plain chord behaviour.
    return {
      source: wbLinkEnd(source, sourceNode && wbItemEdgeDir(sourceKind, sourceNode, source), sourceBox, sourceNode && !sourceFixed),
      target: wbLinkEnd(target, targetNode && wbItemEdgeDir(targetKind, targetNode, target), targetBox, targetNode && !targetFixed),
    };
  }

  //: Reads a link's own start/end cap kinds, the new independent-per-end
  //: fields (`startCap`/`endCap`, one of `WB_CAP_KINDS`) if it has them, or
  //: translated from the older single `endStyle` (start/end/both/none,
  //: always an arrow) for a link saved before the full end-cap system
  //: existed. No migration needed: this is the only place either shape gets
  //: read, so an old link keeps rendering exactly as it always did until its
  //: caps are actually changed.
  function wbLinkCaps(parsed) {
    const sizes = { startSize: parsed.startCapSize || null, endSize: parsed.endCapSize || null };
    if (parsed.startCap !== undefined || parsed.endCap !== undefined) {
      return { startCap: parsed.startCap || "none", endCap: parsed.endCap || "none", ...sizes };
    }
    const style = parsed.endStyle;
    return {
      startCap: style === "start" || style === "both" ? "arrow" : "none",
      endCap: style === "end" || style === "both" ? "arrow" : "none",
      ...sizes,
    };
  }

  //: One path for a link, shared by the render and the live drag preview.
  //: **A curved link leaves and enters along the edge it is attached to**, and
  //: its caps point along the curve: each end's control point is pushed along
  //: its edge's outward normal (`wbEdgeNormal` via `wbWithDir`), by an offset
  //: proportional to the ends' distance and clamped, and a cap's angle is read
  //: from that control point, so it always agrees with the drawn curve. An end
  //: with no edge (a free point, the preview) keeps the horizontal curve.
  //: `bend` (double-click to add a point): an offset from the chord's midpoint;
  //: when set, the link is one quadratic curve through it. `shape`
  //: (`wbLinkShape`): an elbow, routed round its two boxes through its bends.
  function wbLinkPathD(type, sPt, tPt, caps, width, bend, shape = null) {
    //: A curved connector from a shape back to itself: a loop out of its side (`wbFmtState.drawMore`).
    if (shape?.route === "loop") return wbCurvePathD(wbFmtState.drawMore.loopSegs(shape.side, sPt, tPt), caps, width);
    //: Entity relation and isometric (`wbFmtState.drawMore`): drawn from the two ends alone.
    if (shape?.route === "er" || shape?.route === "iso") {
      const held = wbGapEnds(sPt, tPt, shape.gap);
      return wbElbowPathD(wbFmtState.drawMore.routeStops(shape.route, held.source, held.target), caps, width);
    }
    if (shape?.route === "elbow") {
      //: The gap is taken after a floating end has settled on its side, and
      //: along the way the route leaves it.
      const ends = wbElbowEnds(sPt, tPt, shape.points);
      const held = wbGapEnds(ends.source, ends.target, shape.gap);
      //: With no waypoint the obstacle router (`wbFmtState.router`) goes round every item; it answers null when
      //: there is no path or the grid would be too large, and the classic route below is drawn instead.
      const routed = shape.points?.length ? null : wbFmtState.router?.route(held.source, held.target, sPt.box, tPt.box);
      return wbElbowPathD(routed || wbElbowRoute(held.source, held.target, sPt.box, tPt.box, shape.points), caps, width);
    }
    if (shape?.gap) {
      const way = shape.points || [];
      ({ source: sPt, target: tPt } = wbGapEnds(sPt, tPt, shape.gap, {
        chord: type === "link-straight", via: way.length ? [way[0], way[way.length - 1]] : null,
      }));
    }
    //: A straight or curved connector with waypoints (draw.io's bends on any
    //: edge): straight runs through each in turn, curved is one smooth curve
    //: through all of them. The old single `bend` below is read only when a
    //: link has no waypoints; the first edit of it writes `points` instead.
    if (shape?.points?.length) {
      const stops = [sPt, ...shape.points, tPt];
      if (shape.route === "straight") return wbElbowPathD(stops, caps, width);
      return wbCurvePathD(wbCurveThroughSegs(stops, sPt.dir, tPt.dir), caps, width);
    }
    if (bend && (bend.x || bend.y)) {
      const ctrl = { x: (sPt.x + tPt.x) / 2 + bend.x, y: (sPt.y + tPt.y) / 2 + bend.y };
      const startCap = caps?.startCap || "none", endCap = caps?.endCap || "none";
      const headLen = (width || 3) * 4 + 6;
      const from = wbShaftEnd(sPt, ctrl, startCap, headLen, caps?.startSize), to = wbShaftEnd(tPt, ctrl, endCap, headLen, caps?.endSize);
      let d = `M ${from.x} ${from.y} Q ${ctrl.x} ${ctrl.y}, ${to.x} ${to.y}`;
      if (endCap !== "none") d += " " + wbCapPath(endCap, tPt.x, tPt.y, Math.atan2(tPt.y - ctrl.y, tPt.x - ctrl.x), headLen, caps?.endSize);
      if (startCap !== "none") d += " " + wbCapPath(startCap, sPt.x, sPt.y, Math.atan2(sPt.y - ctrl.y, sPt.x - ctrl.x), headLen, caps?.startSize);
      return d;
    }
    const straight = type === "link-straight";
    const dx = tPt.x - sPt.x;
    const dy = tPt.y - sPt.y;
    const span = Math.hypot(dx, dy);
    // Enough to read as a deliberate curve, never enough to swing wide.
    const reach = Math.max(24, Math.min(span * 0.4, 160));
    const c1 = sPt.dir
      ? { x: sPt.x + sPt.dir.x * reach, y: sPt.y + sPt.dir.y * reach }
      : { x: sPt.x + dx / 2, y: sPt.y };
    const c2 = tPt.dir
      ? { x: tPt.x + tPt.dir.x * reach, y: tPt.y + tPt.dir.y * reach }
      : { x: tPt.x - dx / 2, y: tPt.y };
    const startCap = caps?.startCap || "none", endCap = caps?.endCap || "none";
    const headLen = (width || 3) * 4 + 6;
    const from = wbShaftEnd(sPt, straight ? tPt : c1, startCap, headLen, caps?.startSize);
    const to = wbShaftEnd(tPt, straight ? sPt : c2, endCap, headLen, caps?.endSize);
    const base = straight
      ? `M ${from.x} ${from.y} L ${to.x} ${to.y}`
      : `M ${from.x} ${from.y} C ${c1.x} ${c1.y}, ${c2.x} ${c2.y}, ${to.x} ${to.y}`;
    if (startCap === "none" && endCap === "none") return base;
    // On a straight link the chord *is* the tangent. On a curve, the tangent at
    // an end is the direction to that end's own control point, pointing away
    // from the shape, so the head is rotated by PI to point back into it.
    const endAngle = straight
      ? Math.atan2(dy, dx)
      : Math.atan2(tPt.y - c2.y, tPt.x - c2.x);
    const startAngle = straight
      ? Math.atan2(dy, dx) + Math.PI
      : Math.atan2(sPt.y - c1.y, sPt.x - c1.x);
    let d = base;
    if (endCap !== "none") d += " " + wbCapPath(endCap, tPt.x, tPt.y, endAngle, headLen, caps?.endSize);
    if (startCap !== "none") d += " " + wbCapPath(startCap, sPt.x, sPt.y, startAngle, headLen, caps?.startSize);
    return d;
  }

  // --- Elbow connectors (WHITEBOARD_PLAN Phase B; the features audit W4) ------
  //
  // draw.io's orthogonal edge: a connector that leaves its shape straight out
  // of the side it is anchored to, turns only at right angles, and goes round
  // the two shapes it joins rather than through them. `wbElbowRoute` is the
  // pure part (tested in node, `tests/test_wb_elbow.py`): the two ends with
  // their outward direction (`wbWithDir`), the two boxes, and any waypoints the
  // person dragged in, to a polyline of axis-aligned segments.

  const WB_ELBOW_PAD = 24;

  function wbElbowSide(p) {
    if (!p?.dir) return null;
    return Math.abs(p.dir.x) >= Math.abs(p.dir.y) ? "h" : "v";
  }

  //: Whether the axis-aligned segment a-b passes through a box's inside.
  function wbElbowCrosses(a, b, box) {
    if (!box) return false;
    const lx = Math.min(a.x, b.x), hx = Math.max(a.x, b.x);
    const ly = Math.min(a.y, b.y), hy = Math.max(a.y, b.y);
    return lx < box.maxX - 1 && hx > box.minX + 1 && ly < box.maxY - 1 && hy > box.minY + 1;
  }

  //: One leg, from `a` heading `inDir` to `b`, arriving so that it can leave
  //: towards `outDir` (null: anything): straight when they line up, else one
  //: right-angle corner, the one that does not cut a box, does not double back
  //: and keeps going the way it was going.
  function wbElbowLeg(a, b, inDir, outDir, boxes) {
    if (Math.abs(a.x - b.x) < 0.5 || Math.abs(a.y - b.y) < 0.5) return [];
    const candidates = [{ x: b.x, y: a.y }, { x: a.x, y: b.y }];
    let best = null, bestScore = Infinity;
    for (const c of candidates) {
      const first = { x: Math.sign(c.x - a.x), y: Math.sign(c.y - a.y) };
      const second = { x: Math.sign(b.x - c.x), y: Math.sign(b.y - c.y) };
      let score = 0;
      for (const box of boxes) score += (wbElbowCrosses(a, c, box) ? 100 : 0) + (wbElbowCrosses(c, b, box) ? 100 : 0);
      if (inDir && first.x * inDir.x + first.y * inDir.y < 0) score += 20;
      if (outDir && second.x * outDir.x + second.y * outDir.y < 0) score += 20;
      if (inDir && first.x * inDir.x + first.y * inDir.y > 0) score -= 1;
      if (score < bestScore) {
        bestScore = score;
        best = c;
      }
    }
    return [best];
  }

  function wbElbowRoute(s, t, sBox = null, tBox = null, points = []) {
    const pad = WB_ELBOW_PAD;
    const boxes = [sBox, tBox].filter(Boolean);
    const guess = Math.abs(t.x - s.x) >= Math.abs(t.y - s.y) ? "h" : "v";
    const sSide = wbElbowSide(s) || guess;
    const tSide = wbElbowSide(t) || guess;
    const sDir = sSide === "h" ? { x: Math.sign(s.dir?.x || t.x - s.x) || 1, y: 0 } : { x: 0, y: Math.sign(s.dir?.y || t.y - s.y) || 1 };
    const tDir = tSide === "h" ? { x: Math.sign(t.dir?.x || s.x - t.x) || 1, y: 0 } : { x: 0, y: Math.sign(t.dir?.y || s.y - t.y) || 1 };
    const s1 = { x: s.x + sDir.x * pad, y: s.y + sDir.y * pad };
    const t1 = { x: t.x + tDir.x * pad, y: t.y + tDir.y * pad };
    const into = { x: -tDir.x, y: -tDir.y };
    const out = [{ x: s.x, y: s.y }, s1];
    let cur = s1, inDir = sDir;
    const stops = [...(points || []).map((p) => ({ x: p.x, y: p.y })), t1];
    for (const [i, stop] of stops.entries()) {
      const last = i === stops.length - 1;
      let leg = wbElbowLeg(cur, stop, inDir, last ? into : null, boxes);
      //: Two shapes facing away from each other, or one behind the other, need
      //: two corners: out round the boxes, along, and back in.
      if (last && !points?.length && leg.length && boxes.length && (wbElbowCrosses(cur, leg[0], sBox) || wbElbowCrosses(leg[0], stop, sBox) || wbElbowCrosses(cur, leg[0], tBox) || wbElbowCrosses(leg[0], stop, tBox))) {
        leg = wbElbowDetour(cur, stop, sSide, sBox, tBox, pad);
      } else if (last && !points?.length && !leg.length && sSide === tSide) {
        leg = [];
      }
      if (last && !points?.length && sSide === tSide && leg.length === 1) {
        //: Side to side (or top to bottom) facing each other: the classic
        //: three segments, turning halfway rather than at one end.
        if (sSide === "h") {
          const mx = (cur.x + stop.x) / 2;
          const mid = [{ x: mx, y: cur.y }, { x: mx, y: stop.y }];
          if (!boxes.some((b) => wbElbowCrosses(cur, mid[0], b) || wbElbowCrosses(mid[0], mid[1], b) || wbElbowCrosses(mid[1], stop, b))) leg = mid;
        } else {
          const my = (cur.y + stop.y) / 2;
          const mid = [{ x: cur.x, y: my }, { x: stop.x, y: my }];
          if (!boxes.some((b) => wbElbowCrosses(cur, mid[0], b) || wbElbowCrosses(mid[0], mid[1], b) || wbElbowCrosses(mid[1], stop, b))) leg = mid;
        }
      }
      out.push(...leg, stop);
      const prev = out[out.length - 2];
      inDir = { x: Math.sign(stop.x - prev.x), y: Math.sign(stop.y - prev.y) };
      cur = stop;
    }
    out.push({ x: t.x, y: t.y });
    //: Drop repeated points and the middle of three in a line.
    const clean = [];
    for (const p of out) {
      const last = clean[clean.length - 1];
      if (last && Math.abs(last.x - p.x) < 0.5 && Math.abs(last.y - p.y) < 0.5) continue;
      const prev = clean[clean.length - 2];
      if (prev && last && ((Math.abs(prev.x - last.x) < 0.5 && Math.abs(last.x - p.x) < 0.5) || (Math.abs(prev.y - last.y) < 0.5 && Math.abs(last.y - p.y) < 0.5))) {
        clean[clean.length - 1] = p;
        continue;
      }
      clean.push(p);
    }
    return clean;
  }

  //: Out past both boxes on the nearer side, along, and back: the route for a
  //: target behind the side its source leaves from.
  function wbElbowDetour(a, b, side, sBox, tBox, pad) {
    if (side === "h") {
      const top = Math.min(sBox?.minY ?? a.y, tBox?.minY ?? b.y) - pad;
      const bottom = Math.max(sBox?.maxY ?? a.y, tBox?.maxY ?? b.y) + pad;
      const y = Math.abs(top - a.y) + Math.abs(top - b.y) <= Math.abs(bottom - a.y) + Math.abs(bottom - b.y) ? top : bottom;
      return [{ x: a.x, y }, { x: b.x, y }];
    }
    const left = Math.min(sBox?.minX ?? a.x, tBox?.minX ?? b.x) - pad;
    const right = Math.max(sBox?.maxX ?? a.x, tBox?.maxX ?? b.x) + pad;
    const x = Math.abs(left - a.x) + Math.abs(left - b.x) <= Math.abs(right - a.x) + Math.abs(right - b.x) ? left : right;
    return [{ x, y: a.y }, { x, y: b.y }];
  }

  //: The polyline as a path, with the end caps turned to the last and first
  //: segments.
  function wbElbowPathD(pts, caps, width) {
    const startCap = caps?.startCap || "none", endCap = caps?.endCap || "none";
    const headLen = (width || 3) * 4 + 6;
    const n = pts.length;
    const run = pts.slice();
    if (n > 1) {
      run[0] = wbShaftEnd(pts[0], pts[1], startCap, headLen, caps?.startSize);
      run[n - 1] = wbShaftEnd(pts[n - 1], pts[n - 2], endCap, headLen, caps?.endSize);
    }
    let d = `M ${run[0].x} ${run[0].y}` + run.slice(1).map((p) => ` L ${p.x} ${p.y}`).join("");
    if (endCap !== "none" && n > 1) d += " " + wbCapPath(endCap, pts[n - 1].x, pts[n - 1].y, Math.atan2(pts[n - 1].y - pts[n - 2].y, pts[n - 1].x - pts[n - 2].x), headLen, caps?.endSize);
    if (startCap !== "none" && n > 1) d += " " + wbCapPath(startCap, pts[0].x, pts[0].y, Math.atan2(pts[0].y - pts[1].y, pts[0].x - pts[1].x), headLen, caps?.startSize);
    return d;
  }

  //: **A smooth curve through a connector's waypoints**, as cubic segments: a
  //: Catmull-Rom spline (each inner stop's tangent parallel to the chord of its
  //: two neighbours), whose two ends leave and enter along their shapes' edge
  //: normals the way a curved link without waypoints does. Pure, so the render,
  //: the grips (each segment's middle is where its add grip sits) and the node
  //: tests all read the same curve.
  function wbCurveThroughSegs(pts, sDir = null, tDir = null) {
    const segs = [];
    for (let i = 0; i < pts.length - 1; i++) {
      const p0 = pts[i - 1], p1 = pts[i], p2 = pts[i + 1], p3 = pts[i + 2];
      const reach = Math.max(12, Math.min(Math.hypot(p2.x - p1.x, p2.y - p1.y) / 2, 160));
      let c1, c2;
      if (p0) c1 = { x: p1.x + (p2.x - p0.x) / 6, y: p1.y + (p2.y - p0.y) / 6 };
      else if (sDir) c1 = { x: p1.x + sDir.x * reach, y: p1.y + sDir.y * reach };
      else c1 = { x: p1.x + (p2.x - p1.x) / 3, y: p1.y + (p2.y - p1.y) / 3 };
      if (p3) c2 = { x: p2.x - (p3.x - p1.x) / 6, y: p2.y - (p3.y - p1.y) / 6 };
      else if (tDir) c2 = { x: p2.x + tDir.x * reach, y: p2.y + tDir.y * reach };
      else c2 = { x: p2.x - (p2.x - p1.x) / 3, y: p2.y - (p2.y - p1.y) / 3 };
      segs.push({ a: { x: p1.x, y: p1.y }, c1, c2, b: { x: p2.x, y: p2.y } });
    }
    return segs;
  }

  //: A point along one cubic segment, `u` from 0 to 1.
  function wbCubicAt(seg, u) {
    const v = 1 - u;
    const w = [v * v * v, 3 * v * v * u, 3 * v * u * u, u * u * u];
    return {
      x: w[0] * seg.a.x + w[1] * seg.c1.x + w[2] * seg.c2.x + w[3] * seg.b.x,
      y: w[0] * seg.a.y + w[1] * seg.c1.y + w[2] * seg.c2.y + w[3] * seg.b.y,
    };
  }

  //: The segments as a path, the caps turned along the curve's own ends.
  function wbCurvePathD(segs, caps, width) {
    if (!segs.length) return "";
    const startCap = caps?.startCap || "none", endCap = caps?.endCap || "none";
    const headLen = (width || 3) * 4 + 6;
    const first = segs[0], last = segs[segs.length - 1];
    const from = wbShaftEnd(first.a, first.c1, startCap, headLen, caps?.startSize), to = wbShaftEnd(last.b, last.c2, endCap, headLen, caps?.endSize);
    let d = `M ${from.x} ${from.y}` + segs.map((s) => {
      const end = s === last ? to : s.b;
      return ` C ${s.c1.x} ${s.c1.y}, ${s.c2.x} ${s.c2.y}, ${end.x} ${end.y}`;
    }).join("");
    if (endCap !== "none") d += " " + wbCapPath(endCap, last.b.x, last.b.y, Math.atan2(last.b.y - last.c2.y, last.b.x - last.c2.x), headLen, caps?.endSize);
    if (startCap !== "none") d += " " + wbCapPath(startCap, first.a.x, first.a.y, Math.atan2(first.a.y - first.c1.y, first.a.x - first.c1.x), headLen, caps?.startSize);
    return d;
  }

  //: **Where a new waypoint goes among the others**: by how far along `line`
  //: (the drawn route for an elbow, the stops for a straight or curved line)
  //: it is, so a bend added in the third run lands between the second and
  //: third waypoints rather than at the end.
  function wbWaypointInsert(points, line, p) {
    const at = wbPolylineAt(line, p);
    const index = points.filter((q) => wbPolylineAt(line, q) <= at).length;
    return [...points.slice(0, index), { x: p.x, y: p.y }, ...points.slice(index)];
  }

  // --- Line jumps (draw.io's "line jumps"; wb-phase2 step 1) -----------------
  //
  // Where a connector crosses one drawn before it, it hops over: a small arc,
  // a gap, or a sharp peak, so two crossing lines never read as a junction.
  // Per connector (`jumps` in its data, none when absent), on its straight
  // runs (a straight line or an elbow; a curve has none to break), against
  // every connector under it in paint order, so of two crossing lines only the
  // upper one hops, as in draw.io. `wbLineJumpsD` is the pure part.

  const WB_JUMP_STYLES = ["none", "arc", "gap", "sharp"];

  //: Where segment a-b crosses segment c-d, as a share of a-b's length, or
  //: null: parallel, touching at an end, or apart.
  function wbSegmentCross(a, b, c, d) {
    const rx = b.x - a.x, ry = b.y - a.y, sx = d.x - c.x, sy = d.y - c.y;
    const den = rx * sy - ry * sx;
    if (Math.abs(den) < 1e-9) return null;
    const t = ((c.x - a.x) * sy - (c.y - a.y) * sx) / den;
    const u = ((c.x - a.x) * ry - (c.y - a.y) * rx) / den;
    //: Half-open on the other line, so a crossing exactly at one of its sampled
    //: points counts once rather than falling between two segments.
    return t > 0 && t < 1 && u >= 0 && u < 1 ? t : null;
  }

  //: The shaft of a polyline `pts` with a hop wherever it crosses one of
  //: `others` (polylines). Crossings closer than a hop's width merge into one
  //: wide hop; none within a hop of a corner (it would bend through the turn).
  //: Arcs and peaks rise to the same side of the line whichever way it runs:
  //: up for a level run, left for an upright one.
  function wbLineJumpsD(pts, others, style = "arc", size = 6) {
    if (!pts?.length) return "";
    let d = `M ${pts[0].x} ${pts[0].y}`;
    for (let i = 0; i < pts.length - 1; i++) {
      const a = pts[i], b = pts[i + 1];
      const len = Math.hypot(b.x - a.x, b.y - a.y);
      if (!len) continue;
      const ux = (b.x - a.x) / len, uy = (b.y - a.y) / len;
      const at = [];
      if (style && style !== "none") {
        for (const line of others || []) {
          for (let j = 0; j < line.length - 1; j++) {
            const t = wbSegmentCross(a, b, line[j], line[j + 1]);
            if (t !== null && t * len > size && t * len < len - size) at.push(t * len);
          }
        }
      }
      at.sort((p, q) => p - q);
      const hops = [];
      for (const s of at) {
        const last = hops[hops.length - 1];
        if (last && s - last.to < size * 2) last.to = s;
        else hops.push({ from: s, to: s });
      }
      let nx = uy, ny = -ux;
      const flip = ny > 1e-9 || (Math.abs(ny) <= 1e-9 && nx > 0);
      if (flip) { nx = -nx; ny = -ny; }
      const r2 = (n) => Math.round(n * 100) / 100;
      for (const hop of hops) {
        const p0 = { x: a.x + ux * (hop.from - size), y: a.y + uy * (hop.from - size) };
        const p1 = { x: a.x + ux * (hop.to + size), y: a.y + uy * (hop.to + size) };
        d += ` L ${r2(p0.x)} ${r2(p0.y)}`;
        if (style === "gap") d += ` M ${r2(p1.x)} ${r2(p1.y)}`;
        else if (style === "sharp") {
          const mid = { x: (p0.x + p1.x) / 2 + nx * size, y: (p0.y + p1.y) / 2 + ny * size };
          d += ` L ${r2(mid.x)} ${r2(mid.y)} L ${r2(p1.x)} ${r2(p1.y)}`;
        } else {
          const rad = r2(Math.hypot(p1.x - p0.x, p1.y - p0.y) / 2);
          d += ` A ${rad} ${rad} 0 0 ${flip ? 0 : 1} ${r2(p1.x)} ${r2(p1.y)}`;
        }
      }
      d += ` L ${b.x} ${b.y}`;
    }
    return d;
  }

  //: The points along a drawn shaft (its first subpath): lines as they are,
  //: curves sampled, so a curved line is still something to hop over.
  function wbShaftPoints(d) {
    const shaft = String(d || "").split(/\s(?=M)/)[0];
    const tokens = shaft.match(/[MLCQHV]|-?\d*\.?\d+(?:[eE]-?\d+)?/g);
    if (!tokens) return [];
    const pts = [];
    let i = 0, cmd = "", x = 0, y = 0;
    const num = () => parseFloat(tokens[i++]);
    while (i < tokens.length) {
      if (/^[A-Z]$/.test(tokens[i])) cmd = tokens[i++];
      if (i >= tokens.length) break;
      if (cmd === "M" || cmd === "L") {
        x = num(); y = num();
        pts.push({ x, y });
      } else if (cmd === "H") {
        x = num();
        pts.push({ x, y });
      } else if (cmd === "V") {
        y = num();
        pts.push({ x, y });
      } else if (cmd === "C" || cmd === "Q") {
        const c = cmd === "C" ? [num(), num(), num(), num()] : [num(), num()];
        const ex = num(), ey = num();
        const seg = cmd === "C"
          ? { a: { x, y }, c1: { x: c[0], y: c[1] }, c2: { x: c[2], y: c[3] }, b: { x: ex, y: ey } }
          : { a: { x, y }, c1: { x: x + (2 / 3) * (c[0] - x), y: y + (2 / 3) * (c[1] - y) }, c2: { x: ex + (2 / 3) * (c[0] - ex), y: ey + (2 / 3) * (c[1] - ey) }, b: { x: ex, y: ey } };
        for (let k = 1; k <= 12; k++) pts.push(wbCubicAt(seg, k / 12));
        x = ex; y = ey;
      } else {
        i += 1;
      }
    }
    return pts;
  }

  //: After a render has drawn every line plain: each connector that jumps
  //: hops over the lines painted before it. Reads each line's hitbox (always
  //: the plain line) and rewrites only the drawn path's shaft, its caps kept.
  //: Nothing to do on a board where no connector asks for jumps, which is
  //: almost every board, so the cost there is one pass over the data.
  function wbApplyLineJumps(groups) {
    //: What the paint skip compares the drawn path with (`renderWhiteboard`): a jump rewrites it, so the
    //: pass records the path it left, and writes only when it differs from the one on the page.
    const settle = (el, path, d) => {
      if (path && path.getAttribute("d") !== d) path.setAttribute("d", d);
      if (el._wbStrokeD != null) el._wbStrokeD = d;
    };
    const links = [];
    let wanted = false;
    for (const el of groups) {
      let parsed = null;
      try {
        parsed = JSON.parse(el.__data__?.data || "null");
      } catch {
        parsed = null;
      }
      if (!parsed || !String(parsed.type || "").startsWith("link-") || wbMapCrossLinkLook(parsed) || (parsed.shape && parsed.shape !== "line")) continue;
      links.push({ el, parsed });
      if (parsed.jumps && parsed.jumps !== "none") wanted = true;
    }
    if (!wanted) return;
    const under = [];
    for (const { el, parsed } of links) {
      const plain = el.querySelector(".sketch-hitbox")?.getAttribute("d") || "";
      const pts = wbShaftPoints(plain);
      const straight = ["elbow", "er", "iso"].includes(parsed.route) || (parsed.type === "link-straight" && !(parsed.bend && (parsed.bend.x || parsed.bend.y) && !parsed.points?.length));
      if (straight && parsed.jumps && parsed.jumps !== "none" && under.length && pts.length > 1) {
        const path = el.querySelector(".sketch-path");
        const caps = String(path?.getAttribute("d") || "").split(/\s(?=M)/).slice(1).join(" ");
        const shaft = wbLineJumpsD(pts, under, parsed.jumps, wbJumpSize(parsed));
        settle(el, path, caps ? `${shaft} ${caps}` : shaft);
      } else if (parsed.jumps && parsed.jumps !== "none" && el._wbPlainD != null) {
        //: A skipped connector keeps the path it was last given; with nothing to hop it goes back to the plain one.
        settle(el, el.querySelector(".sketch-path"), el._wbPlainD);
      }
      under.push(pts);
    }
  }

  //: A floating end of an elbow (no fixed anchor) sits in the middle of the
  //: side that faces the other end, the way draw.io's orthogonal edge does,
  //: rather than wherever the ray between the two centres crosses the edge:
  //: that point leaves a jog of a few pixels next to the shape, which reads as
  //: a mistake on a route that is otherwise all right angles.
  function wbElbowFloat(p, toward) {
    if (!p?.floating || !p.box || !toward) return p;
    const b = p.box;
    const cx = (b.minX + b.maxX) / 2, cy = (b.minY + b.maxY) / 2;
    const hw = (b.maxX - b.minX) / 2 || 1, hh = (b.maxY - b.minY) / 2 || 1;
    const dx = (toward.x - cx) / hw, dy = (toward.y - cy) / hh;
    if (Math.abs(dx) >= Math.abs(dy)) {
      const sx = Math.sign(dx) || 1;
      return { x: cx + sx * hw, y: cy, dir: { x: sx, y: 0 }, box: b };
    }
    const sy = Math.sign(dy) || 1;
    return { x: cx, y: cy + sy * hh, dir: { x: 0, y: sy }, box: b };
  }

  //: The two ends an elbow is drawn between, floating ends settled first; the
  //: render and the grips both read this, so a grip sits where the line starts.
  function wbElbowEnds(sPt, tPt, points) {
    const first = points?.[0], last = points?.[points.length - 1];
    return {
      source: wbElbowFloat(sPt, first || (tPt.box ? { x: (tPt.box.minX + tPt.box.maxX) / 2, y: (tPt.box.minY + tPt.box.maxY) / 2 } : tPt)),
      target: wbElbowFloat(tPt, last || (sPt.box ? { x: (sPt.box.minX + sPt.box.maxX) / 2, y: (sPt.box.minY + sPt.box.maxY) / 2 } : sPt)),
    };
  }

  //: How far along a polyline the nearest point to `p` is, in board units:
  //: the order a new waypoint takes among the others.
  function wbPolylineAt(pts, p) {
    let best = Infinity, at = 0, run = 0;
    for (let i = 0; i < pts.length - 1; i++) {
      const a = pts[i], b = pts[i + 1];
      const len = Math.hypot(b.x - a.x, b.y - a.y);
      const u = len ? Math.max(0, Math.min(1, ((p.x - a.x) * (b.x - a.x) + (p.y - a.y) * (b.y - a.y)) / (len * len))) : 0;
      const dist = Math.hypot(p.x - (a.x + (b.x - a.x) * u), p.y - (a.y + (b.y - a.y) * u));
      if (dist < best) {
        best = dist;
        at = run + len * u;
      }
      run += len;
    }
    return at;
  }

  //: A link's line shape for the context bar. An elbow is a straight link with
  //: `route: "elbow"`, so every reader that only knows the two old types (the
  //: assistant's board tools, an older build) still draws it as a link.
  function wbLinkRouteName(parsed) {
    if (["elbow", "er", "iso"].includes(parsed?.route)) return parsed.route;
    return parsed?.type === "link-straight" ? "straight" : "curved";
  }

  //: The waypoints a link is drawn through, and how: every elbow, and a
  //: straight or curved link once it has a waypoint. `null` is the plain line
  //: (or the legacy single `bend`), drawn as it always was.
  function wbLinkShape(parsed) {
    const points = Array.isArray(parsed?.points) ? parsed.points : [];
    const gap = wbLinkGap(parsed);
    if (parsed?.route === "elbow") return { route: "elbow", points, gap };
    if (parsed?.route === "er" || parsed?.route === "iso") return { route: parsed.route, points: [], gap };
    //: A curved connector from a shape back to itself is a loop (`wbFmtState.drawMore`).
    if (parsed?.type === "link-curved" && !parsed.route && parsed.sourceId != null && parsed.sourceId === parsed.targetId && (parsed.sourceKind || "node") === (parsed.targetKind || "node")) return { route: "loop", side: parsed.loop || "top", points: [], gap };
    if (!points.length && !gap) return null;
    return { route: parsed.type === "link-straight" ? "straight" : "curved", points, gap };
  }

  //: A line jump's half-width: the connector's own (`jumpSize`, 2 to 40) or,
  //: when it has none, four more than its width.
  function wbJumpSize(parsed) {
    const size = Number(parsed?.jumpSize);
    if (Number.isFinite(size) && parsed?.jumpSize !== null && parsed?.jumpSize !== "") return Math.max(2, Math.min(40, Math.round(size)));
    return 4 + (Number(parsed?.width) || 3);
  }

  //: draw.io's perimeter spacing: how far a connector stops short of the shape
  //: at each end (`gapStart`, `gapEnd`, 0 to 60), or null when it touches both.
  function wbLinkGap(parsed) {
    const clamp = (n) => (Number.isFinite(Number(n)) ? Math.max(0, Math.min(60, Number(n))) : 0);
    const start = clamp(parsed?.gapStart), end = clamp(parsed?.gapEnd);
    return start || end ? { start, end } : null;
  }

  //: One end held off its shape by `gap`, along the line itself (`chord`, a
  //: straight run) or the way the end leaves its shape (a curve, an elbow).
  //: A free point has no shape to keep off, so it stays put.
  function wbGapEnd(pt, gap, toward, chord) {
    if (!gap || !pt?.box) return pt;
    const len = Math.hypot(toward.x - pt.x, toward.y - pt.y);
    const v = !chord && pt.dir ? pt.dir : (len ? { x: (toward.x - pt.x) / len, y: (toward.y - pt.y) / len } : null);
    return v ? { ...pt, x: pt.x + v.x * gap, y: pt.y + v.y * gap } : pt;
  }

  function wbGapEnds(sPt, tPt, gap, { chord = false, via = null } = {}) {
    if (!gap) return { source: sPt, target: tPt };
    //: Two gaps on a short line never run past each other.
    const room = Math.hypot(tPt.x - sPt.x, tPt.y - sPt.y) * 0.45;
    return {
      source: wbGapEnd(sPt, Math.min(gap.start, room), via?.[0] || tPt, chord),
      target: wbGapEnd(tPt, Math.min(gap.end, room), via?.[1] || sPt, chord),
    };
  }

  //: A small SVG dot at each of a shape's connection points, shown while a link
  //: drag is in progress so the snap targets are actually discoverable rather
  //: than a silent hit-test, draw.io shows the same thing on hover. The
  //: nearest one to the live pointer (if within snapping range) renders larger
  //: and filled, so "this is where it'll land" is visible before release.
  //: **How close a press must be to a connection point to draw from it**, in
  //: screen px, and the same distance at which the point lights up under the
  //: pointer, so the dot that grows is the one a drag leaves from. It was 9
  //: to press and 10 to light: eight points on a shape's outline covered most
  //: of its edge, and grabbing the edge to move the shape drew an arrow instead
  //: (dogfood 2026-10-25). The dot is 4px across in its resting size.
  const WB_PORT_HIT_PX = 6;

  function wbShowAnchorHints(kind, item, nearAnchor) {
    // The overlay layer, not the base SVG's own `#wb-zoom-group`, cards
    // render in an HTML layer *above* that SVG (see `#wb-overlay-layer`'s own
    // comment in index.html), so a hint drawn there for a hovered card would
    // be painted directly underneath it, invisible exactly when it matters.
    const zoomGroup = document.getElementById("wb-overlay-zoom-group");
    if (!zoomGroup) return;
    let hints = document.getElementById("wb-anchor-hints");
    if (!hints) {
      hints = document.createElementNS("http://www.w3.org/2000/svg", "g");
      hints.setAttribute("id", "wb-anchor-hints");
      hints.setAttribute("pointer-events", "none");
      zoomGroup.appendChild(hints);
    }
    hints.innerHTML = "";
    if (!item) return;
    for (const { anchor: a, x, y } of wbAnchorPositions(kind, item)) {
      const near = nearAnchor && nearAnchor.x === a.x && nearAnchor.y === a.y;
      const dot = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      dot.setAttribute("cx", x);
      dot.setAttribute("cy", y);
      dot.setAttribute("r", near ? 6 : 4);
      dot.setAttribute("fill", near ? "var(--accent)" : "var(--card)");
      dot.setAttribute("stroke", "var(--accent)");
      dot.setAttribute("stroke-width", "1.5");
      //: A named port (a stencil's `N`, `S`, `Out`) says so: a title on its dot, and the name beside the lit one.
      if (a.name) {
        const title = document.createElementNS("http://www.w3.org/2000/svg", "title");
        title.textContent = a.name;
        dot.appendChild(title);
      }
      hints.appendChild(dot);
      if (near && a.name) wbFmtState.drawMore?.nameBeside(hints, a.name, x, y);
    }
  }

  function wbClearAnchorHints() {
    document.getElementById("wb-anchor-hints")?.remove();
  }

  //: The file's surface: what other files call (L286).
  Object.assign(window, { wbItemRotation, wbRotatePoint, wbBoxCenter, wbEdgePoint, wbPortFractions, wbAnchorPositions, wbAnchorPoint, wbNearestAnchor, wbSketchIsDrawable, wbForgetLinkItems, wbLinkItem, wbLinkCandidates, wbBoundArrowData, wbLinkCandidateAt, wbResolveLinkEndpoints, wbLinkCaps, wbLinkPathD, wbElbowRoute, wbCurveThroughSegs, wbCubicAt, wbWaypointInsert, WB_JUMP_STYLES, wbShaftPoints, wbApplyLineJumps, wbElbowEnds, wbLinkRouteName, wbLinkShape, wbJumpSize, wbLinkGap, WB_PORT_HIT_PX, wbShowAnchorHints, wbClearAnchorHints });
})();
