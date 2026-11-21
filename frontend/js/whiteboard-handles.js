(() => {
  // whiteboard-handles.js: path transforms, end caps, selection grips, waypoint and endpoint handles, the group outline (moved out of whiteboard.js, L634).
  // Wrapped: only what other files call goes on `window`; nothing here runs at load.

  // --- Sketch move/resize (ROADMAP.md Tier 2 §11 / user-reported: "can't
  // move objects drawn on the whiteboard", "can't resize... can't shorten
  // lines") -------------------------------------------------------------------
  //
  // Cards and objects have real x/y/width/height columns; a sketch is just an
  // SVG path string (`d`), so "move" and "resize" both mean rewriting the
  // coordinates inside that string rather than moving a positioned element.
  // This is *not* a general SVG path parser, it only has to round-trip
  // exactly the commands this app's own drawing tools ever emit (see the
  // `pointermove` handler above: `M`/`L` for pen and lines, `C` for link
  // curves, `h`/`v`/`Z` for rect, `a` for circle): a path from anywhere else
  // was never a possibility, so there is no reason to handle SVG's full
  // command set.
  //: `rotate` (degrees, about `anchorX`/`anchorY`) is what a sketch didn't
  //: have: cards and objects rotate (a drag handle + a stored `rotation`
  //: column), but a sketch *is* its path data, and rotating a path correctly
  //: needs care `dx`/`sx` alone don't: `h`/`v` (a purely horizontal/vertical
  //: relative line: this app's own rect tool emits them) can't represent a
  //: rotated line at all, since rotating "purely horizontal" by anything
  //: other than a multiple of 90° makes it not horizontal any more, so each
  //: becomes an absolute `L` instead once rotation is non-zero. `a` (the
  //: circle tool's arc pairs) stays relative, a rotation adds straight onto
  //: the arc's own `x-axis-rotation` parameter and rotates its endpoint
  //: delta; `rx`/`ry`/large-arc/sweep are unchanged, which is exact for a
  //: *pure* rotation (no reflection): this app never emits a negative
  //: scale, so that combination doesn't need handling here.
  function wbTransformPathD(d, { dx = 0, dy = 0, sx = 1, sy = 1, rotate = 0, anchorX = 0, anchorY = 0 } = {}) {
    const theta = (rotate * Math.PI) / 180;
    const cos = Math.cos(theta), sin = Math.sin(theta);
    const mapPoint = (x, y) => {
      const scaledX = anchorX + (x - anchorX) * sx;
      const scaledY = anchorY + (y - anchorY) * sy;
      const relX = scaledX - anchorX, relY = scaledY - anchorY;
      return [anchorX + relX * cos - relY * sin + dx, anchorY + relX * sin + relY * cos + dy];
    };
    // A relative delta scales the same way a point's offset from the anchor
    // does, but never translates (dx/dy are a position's own change, not a
    // vector's).
    const mapDelta = (ddx, ddy) => {
      const scaledX = ddx * sx, scaledY = ddy * sy;
      return [scaledX * cos - scaledY * sin, scaledX * sin + scaledY * cos];
    };
    const tokens = d.match(/[MLCHVAZmlchvaz]|-?\d*\.?\d+(?:[eE]-?\d+)?/g);
    if (!tokens) return d;
    let i = 0, px = 0, py = 0; // current point, tracked only for h/v → L under rotation
    const out = [];
    while (i < tokens.length) {
      const cmd = tokens[i++];
      if (cmd === "M" || cmd === "L") {
        const x = parseFloat(tokens[i++]), y = parseFloat(tokens[i++]);
        const [mx, my] = mapPoint(x, y);
        out.push(cmd, mx, my);
        px = x; py = y;
      } else if (cmd === "C") {
        const n = [];
        for (let k = 0; k < 6; k++) n.push(parseFloat(tokens[i++]));
        const [x1, y1] = mapPoint(n[0], n[1]);
        const [x2, y2] = mapPoint(n[2], n[3]);
        const [x3, y3] = mapPoint(n[4], n[5]);
        out.push(cmd, x1, y1, x2, y2, x3, y3);
        px = n[4]; py = n[5];
      } else if (cmd === "h") {
        const ddx = parseFloat(tokens[i++]);
        if (rotate) {
          const [mx, my] = mapPoint(px + ddx, py);
          out.push("L", mx, my);
        } else {
          out.push(cmd, ddx * sx);
        }
        px += ddx;
      } else if (cmd === "v") {
        const ddy = parseFloat(tokens[i++]);
        if (rotate) {
          const [mx, my] = mapPoint(px, py + ddy);
          out.push("L", mx, my);
        } else {
          out.push(cmd, ddy * sy);
        }
        py += ddy;
      } else if (cmd === "a") {
        const rx = parseFloat(tokens[i++]) * sx, ry = parseFloat(tokens[i++]) * sy;
        const rot = parseFloat(tokens[i++]) + rotate, large = tokens[i++], sweep = tokens[i++];
        const edx = parseFloat(tokens[i++]), edy = parseFloat(tokens[i++]);
        const [mdx, mdy] = mapDelta(edx, edy);
        out.push(cmd, rx, ry, rot, large, sweep, mdx, mdy);
        px += edx; py += edy;
      } else if (cmd === "A") {
        //: The circle tool writes absolute arcs (`wbEllipseDrawD`), and this walk
        //: knew only the relative spelling, so it fell into the "unrecognised
        //: token" branch below and handed the path back unchanged: a circle
        //: could be selected and never moved, resized or rotated (the owner,
        //: 2026-09-14: "I still cant drag and select shapes"; measured in
        //: `scratchpad/ui-sweeps/marquee.js`, the pen strokes moved and every
        //: circle stayed). The endpoint is a point, so it maps as one.
        const rx = parseFloat(tokens[i++]) * sx, ry = parseFloat(tokens[i++]) * sy;
        const rot = parseFloat(tokens[i++]) + rotate, large = tokens[i++], sweep = tokens[i++];
        const ex = parseFloat(tokens[i++]), ey = parseFloat(tokens[i++]);
        const [mx, my] = mapPoint(ex, ey);
        out.push(cmd, rx, ry, rot, large, sweep, mx, my);
        px = ex; py = ey;
      } else if (cmd === "H") {
        const x = parseFloat(tokens[i++]);
        const [mx, my] = mapPoint(x, py);
        out.push("L", mx, my);
        px = x;
      } else if (cmd === "V") {
        const y = parseFloat(tokens[i++]);
        const [mx, my] = mapPoint(px, y);
        out.push("L", mx, my);
        py = y;
      } else if (cmd === "Z" || cmd === "z") {
        out.push(cmd);
      } else {
        return d; // an unrecognised token: leave the path untouched rather than corrupt it
      }
    }
    return out.join(" ");
  }

  //: The bounding box of a path this app drew, walked the same way a real SVG
  //: renderer would (tracking the pen's current point through relative
  //: commands) rather than just min/maxing every raw number, `h`/`v`/`a`'s
  //: numbers are deltas and radii, not coordinates, and mixing them into a
  //: coordinate min/max would produce a nonsense box.
  function wbPathBBox(d) {
    const tokens = d.match(/[MLCHVAZmlchvaz]|-?\d*\.?\d+(?:[eE]-?\d+)?/g);
    if (!tokens) return null;
    let i = 0, px = 0, py = 0;
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    const visit = (x, y) => {
      minX = Math.min(minX, x); minY = Math.min(minY, y);
      maxX = Math.max(maxX, x); maxY = Math.max(maxY, y);
    };
    while (i < tokens.length) {
      const cmd = tokens[i++];
      if (cmd === "M" || cmd === "L") {
        px = parseFloat(tokens[i++]); py = parseFloat(tokens[i++]);
        visit(px, py);
      } else if (cmd === "C") {
        const n = [];
        for (let k = 0; k < 6; k++) n.push(parseFloat(tokens[i++]));
        visit(n[0], n[1]); visit(n[2], n[3]); visit(n[4], n[5]);
        px = n[4]; py = n[5];
      } else if (cmd === "h") {
        px += parseFloat(tokens[i++]);
        visit(px, py);
      } else if (cmd === "v") {
        py += parseFloat(tokens[i++]);
        visit(px, py);
      } else if (cmd === "a" || cmd === "A") {
        const rx = parseFloat(tokens[i++]), ry = parseFloat(tokens[i++]);
        i += 3; // x-axis-rotation, large-arc-flag, sweep-flag: unused for a bbox
        let ex = parseFloat(tokens[i++]), ey = parseFloat(tokens[i++]);
        //: The circle tool writes absolute arcs (`A`, `wbEllipseDrawD`), and this
        //: parser only knew the relative spelling: a circle's box collapsed to
        //: its first point, so a marquee dragged over one selected nothing
        //: unless it happened to cover that point (INBOX 252, the owner: "when
        //: I drag over shapes with the select tool, they dont get selected").
        if (cmd === "A") { ex -= px; ey -= py; }
        // Exact for the axis-aligned circle/ellipse this tool ever draws: two
        // half-arcs whose shared chord's midpoint is the ellipse's own centre.
        const midX = px + ex / 2, midY = py + ey / 2;
        visit(midX - rx, midY - ry);
        visit(midX + rx, midY + ry);
        px += ex; py += ey;
      } else if (cmd === "H") {
        px = parseFloat(tokens[i++]);
        visit(px, py);
      } else if (cmd === "V") {
        py = parseFloat(tokens[i++]);
        visit(px, py);
      }
      // Z/z closes back to the last M, doesn't move the pen for bbox purposes.
    }
    return isFinite(minX) ? { minX, minY, maxX, maxY, width: maxX - minX, height: maxY - minY } : null;
  }
  //: A corner resize held to the proportions it started with: whichever axis
  //: the pointer has stretched further (as a fraction of its own start) wins,
  //: and the other follows it, so the corner stays under the pointer along the
  //: axis being pulled hardest.
  function wbKeepAspect(startW, startH, w, h) {
    const scale = Math.max(w / startW, h / startH);
    return { w: startW * scale, h: startH * scale };
  }

  //: **Alt resizes from the centre** (row 1600, the audit's C3; Figma, tldraw
  //: and PowerPoint all hold it): the side opposite the handle moves by as much
  //: the other way, so the box grows about its middle. A box's new frame from
  //: where the gesture began (`start` is `{x, y, w, h}`), for the card and the
  //: object handles; Shift on a corner still keeps the proportions.
  function wbResizeBox(start, handle, dx, dy, shiftKey, altKey, min) {
    const grow = altKey ? 2 : 1;
    let w = start.w, h = start.h;
    if (handle.includes("e")) w = Math.max(min, start.w + grow * dx);
    if (handle.includes("w")) w = Math.max(min, start.w - grow * dx);
    if (handle.includes("s")) h = Math.max(min, start.h + grow * dy);
    if (handle.includes("n")) h = Math.max(min, start.h - grow * dy);
    if (handle.length === 2 && shiftKey) ({ w, h } = wbKeepAspect(start.w, start.h, w, h));
    if (altKey) return { x: start.x + (start.w - w) / 2, y: start.y + (start.h - h) / 2, w, h };
    return {
      x: handle.includes("w") ? start.x + start.w - w : start.x,
      y: handle.includes("n") ? start.y + start.h - h : start.y,
      w,
      h,
    };
  }

  function wbSketchResizeTransform(bbox, handle, dx, dy, shiftKey, altKey = false) {
    const { minX, minY, maxX, maxY } = bbox;
    if (altKey) {
      //: About the middle (see `wbResizeBox`): the same frame maths, read back
      //: as a scale about the centre.
      const box = wbResizeBox({ x: minX, y: minY, w: maxX - minX || 1, h: maxY - minY || 1 },
        handle, dx, dy, shiftKey, true, WB_SKETCH_MIN_SIZE);
      return {
        sx: handle.includes("e") || handle.includes("w") ? box.w / (maxX - minX || 1) : 1,
        sy: handle.includes("n") || handle.includes("s") ? box.h / (maxY - minY || 1) : 1,
        anchorX: (minX + maxX) / 2,
        anchorY: (minY + maxY) / 2,
      };
    }
    let newMinX = minX, newMaxX = maxX, newMinY = minY, newMaxY = maxY;
    if (handle.includes("e")) newMaxX = Math.max(minX + WB_SKETCH_MIN_SIZE, maxX + dx);
    if (handle.includes("w")) newMinX = Math.min(maxX - WB_SKETCH_MIN_SIZE, minX + dx);
    if (handle.includes("s")) newMaxY = Math.max(minY + WB_SKETCH_MIN_SIZE, maxY + dy);
    if (handle.includes("n")) newMinY = Math.min(maxY - WB_SKETCH_MIN_SIZE, minY + dy);
    // Reported directly: shift while resizing didn't snap to a square. Only a
    // corner handle ("nw"/"ne"/"se"/"sw", length 2) has two free axes to lock
    // together; the larger of the two free-form extents wins, and the corner
    // *opposite* the one being dragged stays anchored, matching `anchorX`/
    // `anchorY` below rather than recentring the shape.
    //: Shift keeps the shape's own proportions (see nodeResizeDrag), which is
    //: still a square for a shape that was drawn square.
    const isCorner = handle.length === 2;
    if (isCorner && shiftKey) {
      const { w, h } = wbKeepAspect(maxX - minX || 1, maxY - minY || 1, newMaxX - newMinX, newMaxY - newMinY);
      if (handle.includes("e")) newMaxX = newMinX + w; else newMinX = newMaxX - w;
      if (handle.includes("s")) newMaxY = newMinY + h; else newMinY = newMaxY - h;
    }
    const oldW = maxX - minX || 1, oldH = maxY - minY || 1;
    const sx = handle.includes("e") || handle.includes("w") ? (newMaxX - newMinX) / oldW : 1;
    const sy = handle.includes("n") || handle.includes("s") ? (newMaxY - newMinY) / oldH : 1;
    return { sx, sy, anchorX: handle.includes("w") ? maxX : minX, anchorY: handle.includes("n") ? maxY : minY };
  }

  //: A sketch's own `data` blob, whether it's `{d, color}` or the wider
  //: `{d, color, width, opacity}` a highlighter carries (HISTORY.md): parsed
  //: once so move/resize can rewrite just `d` and leave every other field
  //: (colour, the highlighter's width/opacity) exactly as it was.
  // Detected from the path data itself, not a stored "kind" field (sketches
  // don't have one): rect/triangle/diamond's own preview-drawing code (above,
  // in the pointermove handler) closes its path with Z; circle instead
  // returns to its start point via two arc ("a") commands. Line/arrow/pen/
  // highlighter never do either.
  function wbSketchIsClosedShape(sketch) {
    const d = wbSketchParsedData(sketch)?.d || "";
    const trimmed = d.trim();
    return /[Zz]\s*$/.test(trimmed) || /\ba\s/i.test(trimmed);
  }

  // Paint-bucket tool: recolour whatever's clicked with the main toolbar's
  // stroke colour. Closed shapes (rect/circle/triangle/diamond) get their
  // fill set, since that's the area a bucket click reads as "inside" of;
  // anything else (line/arrow/pen stroke) has no interior, so its stroke is
  // recoloured instead, the same colour the rail's ink swatch shows.
  async function wbBucketFillSketch(sketch) {
    const color = document.getElementById("wb-rail-ink")?.value || "#3355ff";
    let parsed;
    try {
      parsed = JSON.parse(sketch.data);
    } catch {
      return;
    }
    if (parsed && WB_FILLABLE_SHAPES.has(parsed.shape)) {
      await wbSaveSketchProps(sketch, { fill: color });
    } else {
      await wbSaveSketchProps(sketch, { color });
    }
    wbScheduleRender();
  }

  //: True once a sketch's `d` has more than one `M`, every shape this app's
  //: own tools ever draw uses exactly one *except* an arrow (shaft + one or
  //: two head subpaths, `wbArrowHeadPath`'s own `M`s). Good enough to tell
  //: "this is an arrow" apart from a line/rect/circle/triangle/diamond/pen
  //: stroke without a dedicated `kind` field on every sketch.
  function wbSketchIsArrow(d) {
    return (d.match(/M/g) || []).length > 1;
  }

  //: **A straight line takes ends whether or not it has one yet** (the owner,
  //: 2026-10-11: a plain line offered no arrowheads, because the bar showed the
  //: end lists only for a path that already carried one).
  function wbSketchTakesCaps(parsed) {
    if (!parsed || typeof parsed.d !== "string") return false;
    if (!/^M\s*-?[\d.]+(?:e-?\d+)?\s+-?[\d.]+(?:e-?\d+)?\s+L\s*-?[\d.]+(?:e-?\d+)?\s+-?[\d.]+(?:e-?\d+)?(?:\s+M|\s*$)/.test(parsed.d)) return false;
    return parsed.shape === "line" || parsed.shape === "arrow" || wbSketchIsArrow(parsed.d);
  }

  //: What the Line or Arrow tool puts on its two ends: which ends (`End`,
  //: `Start`, `Both`, `Plain`) and the mark (`window.currentArrowHead`).
  function wbToolCaps() {
    const style = (window.currentTool === "line" ? window.currentLineEndStyle : window.currentArrowEndStyle) || "none";
    const head = WB_CAP_KINDS.includes(window.currentArrowHead) ? window.currentArrowHead : "arrow";
    return {
      startCap: style === "start" || style === "both" ? head : "none",
      endCap: style === "end" || style === "both" ? head : "none",
    };
  }

  //: Rebuilds a line/arrow's own two end caps from its shaft, the shaft is
  //: always the sketch's first subpath, `M sx sy L ex ey` (every arrow this
  //: app draws starts that way), so either end's cap can be changed after
  //: the fact without needing to have stored which shape was originally
  //: chosen. Independently per end (`WB_CAP_KINDS` each): asked for
  //: directly ("a full line/arrow end-cap system... circle/square/multi-line
  //: ends"), replacing the single shared arrowhead-only version.
  function wbRegenerateShapeCaps(d, startCap, endCap, headLen, sizes) {
    const m = d.match(/^M\s*(-?[\d.]+(?:e-?\d+)?)\s+(-?[\d.]+(?:e-?\d+)?)\s+L\s*(-?[\d.]+(?:e-?\d+)?)\s+(-?[\d.]+(?:e-?\d+)?)/);
    if (!m) return d;
    const sx = parseFloat(m[1]), sy = parseFloat(m[2]), ex = parseFloat(m[3]), ey = parseFloat(m[4]);
    const angle = Math.atan2(ey - sy, ex - sx);
    let out = `M ${sx} ${sy} L ${ex} ${ey}`;
    if (endCap && endCap !== "none") out += " " + wbCapPath(endCap, ex, ey, angle, headLen, sizes?.endSize);
    if (startCap && startCap !== "none") out += " " + wbCapPath(startCap, sx, sy, angle + Math.PI, headLen, sizes?.startSize);
    return out;
  }

  //: What style a drawn line/arrow's own path is *actually* carrying,
  //: needed because the properties panel used to just show whatever the
  //: active drawing tool's current default was (live-reported bug, same
  //: session as the Line-tool-always-drew-an-arrowhead one above), which
  //: lies the moment a sketch's real style differs from that default.
  //: `wbArrowHeadPath` always starts its own subpath at the tip it's drawn
  //: for, so a head is detected by which of the shaft's two endpoints each
  //: extra `M` lands on: exact, not guessed, since these are the same
  //: coordinates the shaft itself was drawn from.
  function wbDetectArrowStyle(d) {
    const m = d.match(/^M\s*(-?[\d.]+(?:e-?\d+)?)\s+(-?[\d.]+(?:e-?\d+)?)\s+L\s*(-?[\d.]+(?:e-?\d+)?)\s+(-?[\d.]+(?:e-?\d+)?)/);
    if (!m) return "none";
    const sx = parseFloat(m[1]), sy = parseFloat(m[2]), ex = parseFloat(m[3]), ey = parseFloat(m[4]);
    let hasEnd = false, hasStart = false;
    //: **Scanned from *after* the shaft's own `M`, not from the start of `d`.**
    //: Reported: "arrow drawn shows both caps as Arrow in properties" -
    //: reproduced live: an arrow with only an end head stored no `startCap`/
    //: `endCap` fields at all (an older/legacy shape), so this ran, and `m[0]`
    //: (the shaft's own leading `M sx sy L ex ey`, matched above) begins with
    //: exactly the same `M sx sy` a *real* start-cap marker would - the loop
    //: below used to scan the whole string including that leading `M`, so
    //: every plain shaft with no start cap at all still measured a
    //: zero-distance "hit" on its own start point and reported one anyway.
    //: Slicing it off leaves only the head subpaths `wbArrowHeadPath` actually
    //: appended, which is what this function is supposed to be reading.
    for (const extra of d.slice(m[0].length).matchAll(/M\s*(-?[\d.]+(?:e-?\d+)?)\s+(-?[\d.]+(?:e-?\d+)?)/g)) {
      const x = parseFloat(extra[1]), y = parseFloat(extra[2]);
      if (Math.hypot(x - ex, y - ey) < 0.5) hasEnd = true;
      else if (Math.hypot(x - sx, y - sy) < 0.5) hasStart = true;
    }
    if (hasEnd && hasStart) return "both";
    if (hasEnd) return "end";
    if (hasStart) return "start";
    return "none";
  }

  //: A drawn line/arrow's own two cap kinds, the explicit `startCap`/
  //: `endCap` fields (any of `WB_CAP_KINDS`) if this sketch has them, or
  //: `wbDetectArrowStyle`'s older binary read translated to "arrow"/"none"
  //: for one saved before the full end-cap system existed. Explicit fields
  //: rather than shape-sniffing every cap kind out of the raw path: circle
  //: and square are geometrically ambiguous with plenty of things a pen
  //: stroke could also draw, where an arrow's two-line V (`wbDetectArrowStyle`)
  //: is not: so a *new* cap choice is trusted and stored, and only a link
  //: with no stored choice at all falls back to inferring one.
  function wbSketchCaps(parsed) {
    const sizes = { startSize: parsed.startCapSize || null, endSize: parsed.endCapSize || null };
    if (parsed.startCap !== undefined || parsed.endCap !== undefined) {
      return { startCap: parsed.startCap || "none", endCap: parsed.endCap || "none", ...sizes };
    }
    const legacy = wbDetectArrowStyle(parsed.d);
    return {
      startCap: legacy === "start" || legacy === "both" ? "arrow" : "none",
      endCap: legacy === "end" || legacy === "both" ? "arrow" : "none",
      ...sizes,
    };
  }

  //: Two draggable handles at a selected link's own resolved endpoints, 
  //: asked for directly: "I should be able to move the points where lines,
  //: arrows and links connect on objects to other points or even make it a
  //: dangling unattached point not attached to an object." Dragging one
  //: rewrites *that end's* own reference (`sourceId`/`sourceAnchor` or
  //: `targetId`/`targetAnchor`, reattach, snapping to the nearest of the
  //: hovered card's 8 fixed anchors the same way creating a link already
  //: does) or, released over empty canvas, `sourcePoint`/`targetPoint`, a
  //: fixed board-space point with no card at all. `wbResolveLinkEndpoints`
  //: already reads both shapes, so nothing else needs to change to render one.
  // Remove every sketch handle group, from **both** layers it can live in.
  //
  // Reported with a screenshot: "when I change where links are connected on
  // notes or objects on the whiteboard, these weird small circles are left
  // hanging." They are link endpoint handles, and the cause was a layer split
  // that the cleanup never caught up with, handles for a *link* are appended to
  // `#wb-overlay-zoom-group` (they sit on a card's own border, which the base
  // SVG paints underneath the card's HTML, so they had to move up a layer),
  // while both existing clears only ever swept `#wb-zoom-group`. Every
  // re-render appended a fresh group and none of the old ones was ever removed,
  // so the circles accumulated.
  //
  // One helper, used by all three call sites, so a third layer cannot
  // reintroduce the same gap quietly.
  function wbClearSketchHandles() {
    for (const layer of ["#wb-zoom-group", "#wb-overlay-zoom-group"]) {
      d3.select(wbInstances.query(layer)).selectAll(".wb-sketch-handle-group").remove();
    }
  }

  //: **A right-click on a link's own grip is a right-click on the link**
  //: (MINDMAP_PLAN 13c's leftover). The bend grip and the two end grips live in
  //: the overlay layer, not inside the link's `.sketch-group`, so a right-click
  //: on one reached neither the link's menu (the board's, or on a map the
  //: cross-link ring, both wired on the group by `wbWireContextMenu`) nor the
  //: canvas's, and did nothing: on the one spot of the line drawn to be grabbed.
  //: The press is handed to the link's own hit stroke at the same point, which
  //: is exactly the right-click that already works a little way along the line.
  function wbForwardGripContextMenu(event, sketchId) {
    const hit = wbInstances.query(`.sketch-group[data-id="${sketchId}"] .sketch-hitbox`)
      || wbInstances.query(`.sketch-group[data-id="${sketchId}"]`);
    if (!hit) return;
    event.preventDefault();
    event.stopPropagation();
    hit.dispatchEvent(new MouseEvent("contextmenu", {
      bubbles: true,
      cancelable: true,
      clientX: event.clientX,
      clientY: event.clientY,
      screenX: event.screenX,
      screenY: event.screenY,
      button: 2,
      buttons: 2,
    }));
  }

  function wbRenderLinkEndpointHandles(sketch, parsed) {
    const look = wbMapCrossLinkLook(parsed);
    const endpoints = (look && wbPathEnds(look.line)) || wbResolveLinkEndpoints(parsed);
    if (!endpoints) return;
    // The overlay layer (see its own comment in index.html), an endpoint
    // sits *on a card's own border* by definition, which the base SVG layer
    // paints underneath the card's HTML element. A handle there would be
    // both invisible and unclickable exactly where it's needed most.
    // Clear before drawing: this appends rather than data-joining, so without
    // it every call leaves its predecessor behind on the board.
    wbClearSketchHandles();
    const group = d3.select(wbInstances.layer("wb-overlay-zoom-group")).append("g").attr("class", "wb-sketch-handle-group");
    const shape = look ? null : wbLinkShape(parsed);
    const drawnEnds = shape?.route === "elbow" ? wbElbowEnds(endpoints.source, endpoints.target, shape.points) : endpoints;

    // Every connector's bends are waypoint grips (`wbRenderWaypointHandles`).
    // A map's cross-link keeps its one bend handle: drag to curve it,
    // double-click to straighten it, at the control point so the thing you
    // grab is the thing that moves.
    if (!look) wbRenderWaypointHandles(group, sketch, parsed, endpoints);
    else {
      const mid = { x: (endpoints.source.x + endpoints.target.x) / 2, y: (endpoints.source.y + endpoints.target.y) / 2 };
      const bendLive = { x: parsed.bend?.x || 0, y: parsed.bend?.y || 0 };
      const paths = () => [".sketch-path", ".sketch-hitbox"].map((c) => wbInstances.query(`.sketch-group[data-id="${sketch.id}"] ${c}`));
      const repaint = () => {
        const d = wbLinkPathD(parsed.type, endpoints.source, endpoints.target, wbLinkCaps(parsed), parsed.width, bendLive);
        for (const el of paths()) el?.setAttribute("d", d);
        wbLayoutLinkLabel(wbInstances.query(`.sketch-group[data-id="${sketch.id}"]`));
        //: A map's ribbon is a filled outline; mid-bend the path is an open
        //: curve, which a fill would close into a wedge. Stroke it in the same
        //: colour until the render after the gesture redraws it properly.
        const drawn = paths()[0];
        if (look?.ribbon && drawn && drawn.getAttribute("fill") !== "none") {
          drawn.setAttribute("stroke", drawn.getAttribute("fill"));
          drawn.setAttribute("fill", "none");
        }
      };
      const handle = group.append("circle")
        .attr("class", "wb-link-bend-handle")
        .attr("cx", mid.x + bendLive.x).attr("cy", mid.y + bendLive.y)
        .attr("r", 6);
      handle.append("title").text("Drag to bend this link · double-click to straighten");
      handle.on("contextmenu", (event) => wbForwardGripContextMenu(event, sketch.id));
      handle.call(
        d3.drag()
          .on("start", (event) => event.sourceEvent.stopPropagation())
          .on("drag", function (event) {
            bendLive.x += event.dx;
            bendLive.y += event.dy;
            d3.select(this).attr("cx", mid.x + bendLive.x).attr("cy", mid.y + bendLive.y);
            repaint();
          })
          .on("end", async () => {
            const before = WB_KIND_INFO.sketch.payload(sketch);
            await wbSaveSketchProps(sketch, { bend: (bendLive.x || bendLive.y) ? { x: bendLive.x, y: bendLive.y } : undefined });
            wbPushUndo({ action: "move", kind: "sketch", id: sketch.id, before });
            wbScheduleRender();
          })
      ).on("dblclick", async (event) => {
        event.stopPropagation();
        const before = WB_KIND_INFO.sketch.payload(sketch);
        await wbSaveSketchProps(sketch, { bend: undefined });
        wbPushUndo({ action: "move", kind: "sketch", id: sketch.id, before });
        wbScheduleRender();
      });
    }

    //: Dragging a link's end onto something: any card, text box, sticky or
    //: shape, tested in its rotated frame. This was cards on their unrotated
    //: box, so an end dropped on a rotated sticky became a free point that
    //: floated just off it (reported, with a screenshot).
    const hoveredItemAt = (px, py) => wbLinkCandidateAt(px, py);

    for (const end of ["source", "target"]) {
      const other = end === "source" ? "target" : "source";
      const live = { x: drawnEnds[end].x, y: drawnEnds[end].y };
      group.append("circle")
        .attr("class", "wb-link-endpoint-handle")
        .attr("data-end", end)
        .attr("cx", live.x).attr("cy", live.y)
        .attr("r", 7)
        .style("cursor", "crosshair")
        .on("contextmenu", (event) => wbForwardGripContextMenu(event, sketch.id))
        .call(
          d3.drag()
            .on("start", (event) => event.sourceEvent.stopPropagation())
            .on("drag", function (event) {
              // No `/ transform.k` here: unlike the HTML-element card/object
              // drags elsewhere in this file, this circle's drag container
              // (its parent `<g>`, d3-drag's default) sits *inside* the zoomed
              // `#wb-overlay-zoom-group`. d3.pointer() resolves SVG coordinates
              // through the element's `getScreenCTM()`, which already folds in
              // every ancestor transform: so `event.dx`/`dy` arrive pre-divided
              // by the zoom scale. Dividing again here shrank every frame's
              // movement by a second factor of the zoom level: reported
              // directly ("when I drag the whiteboard links, it goes off my
              // cursor"), and confirmed live: at 2x zoom the handle trailed
              // the cursor by exactly half the dragged distance, growing every
              // frame, matching a `1/k` double-division exactly.
              live.x += event.dx;
              live.y += event.dy;
              d3.select(this).attr("cx", live.x).attr("cy", live.y);
              const previewPts = end === "source" ? [live, endpoints[other]] : [endpoints[other], live];
              const previewD = wbLinkPathD(parsed.type, previewPts[0], previewPts[1], wbLinkCaps(parsed), parsed.width, parsed.bend, wbLinkShape(parsed));
              wbInstances.query(`.sketch-group[data-id="${sketch.id}"] .sketch-path`)?.setAttribute("d", previewD);
              wbInstances.query(`.sketch-group[data-id="${sketch.id}"] .sketch-hitbox`)?.setAttribute("d", previewD);
              wbLayoutLinkLabel(wbInstances.query(`.sketch-group[data-id="${sketch.id}"]`));

              const hit = hoveredItemAt(live.x, live.y);
              if (hit) wbShowAnchorHints(hit[0], hit[1], wbNearestAnchor(hit[0], hit[1], live.x, live.y));
              else wbClearAnchorHints();
              wbFmtState.linkEdge?.cue(hit ? null : [live.x, live.y], sketch.id);
            })
            .on("end", async () => {
              wbClearAnchorHints();
              wbFmtState.linkEdge?.cue(null);
              const before = WB_KIND_INFO.sketch.payload(sketch);
              const hit = hoveredItemAt(live.x, live.y);
              const partial = {};
              if (hit) {
                const [kind, item] = hit;
                partial[end + "Id"] = item.id;
                partial[end + "Kind"] = kind === "node" ? undefined : kind;
                partial[end + "Anchor"] = wbNearestAnchor(kind, item, live.x, live.y) || undefined;
                partial[end + "Point"] = undefined;
                partial[end + "Edge"] = undefined;
              } else {
                const edge = wbFmtState.linkEdge?.hitAt(live.x, live.y, sketch.id);
                partial[end + "Id"] = undefined;
                partial[end + "Kind"] = undefined;
                partial[end + "Anchor"] = undefined;
                partial[end + "Point"] = edge ? { x: edge.x, y: edge.y } : { x: live.x, y: live.y };
                partial[end + "Edge"] = edge ? { id: edge.id, t: edge.t } : undefined;
              }
              await wbSaveSketchProps(sketch, partial);
              wbPushUndo({ action: "move", kind: "sketch", id: sketch.id, before });
              wbScheduleRender();
            })
        );
    }
  }

  //: **A connector's bends, as grips** (the features audit W4, then the same
  //: for straight and curved lines, wb-phase2 step 1). Each waypoint the person
  //: placed is a filled grip: drag it to move the bend, double-click it to take
  //: it out. Between them, in the middle of every run of the drawn line, a
  //: small hollow grip adds one: drag it and the line goes through where it is
  //: let go. The waypoints are saved in board units on the link (`points`);
  //: an elbow's route between them is worked out again on every render, a
  //: straight line runs through them in turn, and a curved one is one smooth
  //: curve through all of them. A link from before this with the old single
  //: `bend` shows that as one waypoint, and the first edit writes `points`.
  function wbRenderWaypointHandles(group, sketch, parsed, endpoints) {
    if (["er", "iso", "loop"].includes(wbLinkShape(parsed)?.route)) return;
    const elbow = parsed.route === "elbow";
    const points = wbLinkWaypoints(parsed, endpoints).map((p) => ({ x: p.x, y: p.y }));
    const groupEl = () => wbInstances.query(`.sketch-group[data-id="${sketch.id}"]`);
    const live = () => ({ ...parsed, points, bend: undefined });
    const ends = () => wbResolveLinkEndpoints(live()) || endpoints;
    const repaint = () => {
      const p = live(), e = ends();
      const d = wbLinkPathD(p.type, e.source, e.target, wbLinkCaps(p), p.width, null, wbLinkShape(p));
      for (const c of [".sketch-path", ".sketch-hitbox"]) groupEl()?.querySelector(c)?.setAttribute("d", d);
      wbLayoutLinkLabel(groupEl());
    };
    const save = async (said) => {
      const before = WB_KIND_INFO.sketch.payload(sketch);
      const kept = points.map((p) => ({ x: Math.round(p.x), y: Math.round(p.y) }));
      await wbSaveSketchProps(sketch, { points: kept.length ? kept : undefined, bend: undefined });
      wbPushUndo({ action: "move", kind: "sketch", id: sketch.id, before });
      if (said) wbAnnounce(said);
      wbScheduleRender();
    };
    for (const p of points) {
      const grip = group.append("circle")
        .attr("class", "wb-link-waypoint-handle")
        .attr("cx", p.x).attr("cy", p.y).attr("r", 6);
      grip.append("title").text("Drag to move this bend · double-click to take it out");
      grip.on("contextmenu", (event) => wbForwardGripContextMenu(event, sketch.id));
      //: Saved only when it moved: a save re-renders the grips, and one on the
      //: first click of a double-click took the grip the second click needed
      //: (measured: a double-click on a bend left it where it was).
      let moved = false;
      grip.call(d3.drag()
        .on("start", (event) => event.sourceEvent.stopPropagation())
        .on("drag", function (event) {
          moved = true;
          p.x += event.dx;
          p.y += event.dy;
          d3.select(this).attr("cx", p.x).attr("cy", p.y);
          repaint();
        })
        .on("end", () => {
          if (moved) save();
          moved = false;
        })).on("dblclick", (event) => {
        event.stopPropagation();
        points.splice(points.indexOf(p), 1);
        save("Bend taken out.");
      });
    }
    //: A label is pressed by its words (INBOX 1404), so a ring that would sit
    //: on them waits: the press would otherwise land on the ring.
    let labelBox = null;
    try { labelBox = groupEl()?.querySelector(":scope > .wb-link-label:not(.wb-link-label2)")?.getBBox() || null; } catch { labelBox = null; }
    const underLabel = (a) => Boolean(labelBox && labelBox.width && a.x > labelBox.x - 6 && a.x < labelBox.x + labelBox.width + 6 && a.y > labelBox.y - 6 && a.y < labelBox.y + labelBox.height + 6);
    for (const add of wbWaypointAddSpots(live(), ends(), groupEl()?.querySelector(".sketch-hitbox")?.getAttribute("d")).filter((a) => !underLabel(a))) {
      const grip = group.append("circle")
        .attr("class", "wb-link-waypoint-add")
        .attr("cx", add.x).attr("cy", add.y).attr("r", 4);
      grip.append("title").text("Drag to add a bend here");
      grip.on("contextmenu", (event) => wbForwardGripContextMenu(event, sketch.id));
      //: Added on the first move, not on the press: a click (or the two of a
      //: double-click) on the ring is not a drag, and inserting on press left
      //: one or two bends exactly where the ring was (measured: a double-click
      //: there saved the same point twice).
      const p = { x: add.x, y: add.y };
      let added = false;
      grip.call(
        d3.drag()
          .on("start", (event) => event.sourceEvent.stopPropagation())
          .on("drag", function (event) {
            if (!added) {
              added = true;
              const index = elbow ? wbWaypointInsert(points, add.line, p).findIndex((q) => q === p || (q.x === p.x && q.y === p.y)) : add.index;
              points.splice(index, 0, p);
              d3.select(this).attr("class", "wb-link-waypoint-handle").attr("r", 6);
            }
            p.x += event.dx;
            p.y += event.dy;
            d3.select(this).attr("cx", p.x).attr("cy", p.y);
            repaint();
          })
          .on("end", () => {
            if (added) save("Bend added. Drag it to move it, double-click to take it out.");
          })
      ).on("dblclick", (event) => {
        //: The ring sits on the line, so a double-click there is the line's
        //: own gesture (a bend where you double-click), not swallowed.
        event.stopPropagation();
        if (added) return;
        added = true;
        const index = elbow ? wbWaypointInsert(points, add.line, p).findIndex((q) => q.x === p.x && q.y === p.y) : add.index;
        points.splice(index, 0, p);
        save("Bend added. Drag it to move it, double-click to take it out.");
      });
    }
  }

  //: A link's waypoints as the grips and a double-click read them: its
  //: `points`, or the one point an old link's single `bend` curve passes
  //: through (a quadratic's middle is halfway from the chord to its control).
  function wbLinkWaypoints(parsed, endpoints) {
    if (Array.isArray(parsed?.points) && parsed.points.length) return parsed.points;
    if (parsed?.route === "elbow" || !endpoints || !parsed?.bend || !(parsed.bend.x || parsed.bend.y)) return [];
    return [{
      x: (endpoints.source.x + endpoints.target.x) / 2 + parsed.bend.x / 2,
      y: (endpoints.source.y + endpoints.target.y) / 2 + parsed.bend.y / 2,
    }];
  }

  //: The line a link is drawn along, as points: an elbow's route, or the
  //: stops a straight or curved link runs through. What a new waypoint's place
  //: among the others is measured on.
  function wbLinkDrawnLine(parsed, ends) {
    const shape = wbLinkShape(parsed);
    if (shape?.route === "elbow") {
      const e = wbElbowEnds(ends.source, ends.target, shape.points);
      return wbElbowRoute(e.source, e.target, ends.source.box, ends.target.box, shape.points);
    }
    return [ends.source, ...(shape?.points || []), ends.target].map((p) => ({ x: p.x, y: p.y }));
  }

  //: Where the add-a-bend grips sit: the middle of every run long enough to
  //: aim at, on the line as drawn (a curve's own middle, not its chord's).
  //: `index` is where a bend added there goes among the waypoints; an elbow's
  //: runs are not one per waypoint, so it carries its route instead.
  function wbWaypointAddSpots(parsed, ends, drawnD) {
    const shape = wbLinkShape(parsed);
    const spots = [];
    if (["er", "iso", "loop"].includes(shape?.route)) return spots;
    if (shape?.route === "elbow") {
      const line = wbLinkDrawnLine(parsed, ends);
      for (let i = 0; i < line.length - 1; i++) {
        const a = line[i], b = line[i + 1];
        if (Math.hypot(b.x - a.x, b.y - a.y) < 36) continue;
        spots.push({ x: (a.x + b.x) / 2, y: (a.y + b.y) / 2, line });
      }
      return spots;
    }
    if (!shape) {
      const mid = (drawnD && wbLinkMidpoint(drawnD, 0.5)) || { x: (ends.source.x + ends.target.x) / 2, y: (ends.source.y + ends.target.y) / 2 };
      return [{ x: mid.x, y: mid.y, index: 0 }];
    }
    const stops = [ends.source, ...shape.points, ends.target];
    const segs = shape.route === "curved" ? wbCurveThroughSegs(stops, ends.source.dir, ends.target.dir) : null;
    for (let i = 0; i < stops.length - 1; i++) {
      const a = stops[i], b = stops[i + 1];
      if (Math.hypot(b.x - a.x, b.y - a.y) < 36) continue;
      const mid = segs ? wbCubicAt(segs[i], 0.5) : { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
      spots.push({ x: mid.x, y: mid.y, index: i });
    }
    return spots;
  }

  //: Where a label sits along its line: 0 at the start, 1 at the end, the
  //: middle when it was never moved.
  function wbLinkLabelT(parsed) {
    const t = Number(parsed?.label_t);
    return Number.isFinite(t) && t >= 0 && t <= 1 ? t : 0.5;
  }

  //: The share of the drawn line nearest a point, sampled along the line's own
  //: length so a curve is measured where it is.
  function wbLinkNearestT(d, p) {
    const shaft = String(d || "").split(/\s(?=M)/)[0];
    if (!shaft || !wbLinkMeasurePath) return 0.5;
    wbLinkMeasurePath.setAttribute("d", shaft);
    let length = 0;
    try {
      length = wbLinkMeasurePath.getTotalLength();
    } catch {
      return 0.5;
    }
    if (!length) return 0.5;
    let best = Infinity, bestT = 0.5;
    const steps = 80;
    for (let i = 0; i <= steps; i++) {
      const q = wbLinkMeasurePath.getPointAtLength((length * i) / steps);
      const dist = Math.hypot(q.x - p.x, q.y - p.y);
      if (dist < best) {
        best = dist;
        bestT = i / steps;
      }
    }
    return Math.max(0.05, Math.min(0.95, bestT));
  }

  // The handles themselves: a fresh SVG group per selection, since (unlike a
  // card/object's own always-present handles) a sketch has no fixed element to
  // attach 8 children to; it's rebuilt on every selection change and after
  // every `wbScheduleRender()` re-applies the current selection.
  //: **A sweep that caught several things gets one box round all of them.**
  //: Reported with two screenshots: "the highlight select only highlights the
  //: shapes, it doesnt show the box and enchor points as it should like when I
  //: individually select them". A single selection has had a box and eight
  //: anchors for a long time; a multi-selection had only each item's own
  //: highlight, so a face drawn from four shapes read as four selected things
  //: with no handle between them.
  //:
  //: The anchors work, rather than being drawn for the look of it: they scale
  //: every selected item about the opposite corner, which is the one gesture a
  //: group box is *for*. The maths is `wbSketchResizeTransform`, the same
  //: function a single shape's handles already use, so a group resize and a
  //: shape resize cannot drift apart (shift-to-square included).
  //:
  //: The rotate point sits above the box; how each kind turns about the
  //: group's centre is written at "And a rotate point above the box" below.
  function wbMultiSelectionEntries() {
    const entries = [];
    for (const key of wbMultiSelection) {
      const sep = key.indexOf(":");
      const kind = key.slice(0, sep);
      const id = Number(key.slice(sep + 1));
      if (kind === "node") {
        const node = (wbState.nodes || []).find((n) => n.id === id);
        if (node) entries.push({ kind, item: node });
      } else if (kind === "object") {
        const object = (wbState.objects || []).find((o) => o.id === id);
        if (object) entries.push({ kind, item: object });
      } else if (kind === "sketch") {
        const sketch = (wbState.sketches || []).find((k) => k.id === id);
        const parsed = sketch ? wbSketchParsedData(sketch) : null;
        //: A link has no `d` of its own (it is recomputed from its endpoints
        //: every render), so it cannot be scaled and is not part of the box.
        if (sketch && parsed) entries.push({ kind, item: sketch, parsed });
      }
    }
    return entries;
  }

  //: Every kind measured in board units, which is the one frame the three of
  //: them share: a card's size lives on the element (its height is the text's
  //: until someone drags it), an object carries its own, and a sketch's is its
  //: path's extent.
  function wbEntryBox(entry) {
    if (entry.kind === "sketch") {
      const bbox = wbPathBBox(entry.parsed.d);
      return bbox ? { minX: bbox.minX, minY: bbox.minY, maxX: bbox.maxX, maxY: bbox.maxY } : null;
    }
    const { item } = entry;
    const el = document.querySelector(WB_SELECTOR_BY_KIND[entry.kind](item.id));
    const w = item.width || el?.offsetWidth || WB_CARD_DEFAULT_SIZE.w;
    const h = item.height || el?.offsetHeight || WB_CARD_DEFAULT_SIZE.h;
    return { minX: item.x, minY: item.y, maxX: item.x + w, maxY: item.y + h };
  }

  //: **The box an item actually occupies, rotation included.**
  //:
  //: `wbEntryBox` above returns the item's *layout* box: the `x`, `y`, `width`
  //: and `height` stored on the row, which is what a resize has to write back
  //: and so is the only thing the group-scale maths may use. A rotated card
  //: does not occupy that box. Measured with one card at 0 degrees and one at
  //: 45: the group outline drawn from layout boxes missed the rotated card by
  //: 61px above, 61px below and 21px to the right, so a selection you could
  //: see was drawn inside a card you had selected.
  //:
  //: The corners of the layout box turned about its own centre, which is what
  //: `translate() rotate()` does to the element (`transform-origin` resolves
  //: to 50% 50% in the untouched box), and then the axis-aligned box around
  //: those four points.
  //:
  //: Deliberately a second function rather than a change to `wbEntryBox`: the
  //: two boxes answer different questions, and the group resize needs the
  //: layout one. Giving it this one instead would write a rotated card's
  //: bounding box back as its `width` and `height`, which grows the card every
  //: time the group is scaled.
  function wbEntryOutlineBox(entry) {
    const box = wbEntryBox(entry);
    if (!box) return null;
    const rotation = entry.kind === "sketch" ? 0 : entry.item.rotation || 0;
    if (!rotation) return box;
    const centre = wbBoxCenter(box);
    const corners = [
      { x: box.minX, y: box.minY },
      { x: box.maxX, y: box.minY },
      { x: box.minX, y: box.maxY },
      { x: box.maxX, y: box.maxY },
    ].map((corner) => wbRotatePoint(corner, centre, rotation));
    return {
      minX: Math.min(...corners.map((c) => c.x)),
      minY: Math.min(...corners.map((c) => c.y)),
      maxX: Math.max(...corners.map((c) => c.x)),
      maxY: Math.max(...corners.map((c) => c.y)),
    };
  }

  //: What every frame of a group drag is computed from, taken once at the
  //: start: reading it back off the items each frame compounds the rounding
  //: into a shape that drifts while the pointer is still.
  function wbMultiSnapshot(boxes) {
    return boxes.map((row) => ({
      entry: row.entry,
      box: row.box,
      d: row.entry.kind === "sketch" ? row.entry.parsed.d : null,
      rotation: row.entry.kind === "sketch" ? 0 : (row.entry.item.rotation || 0),
      //: The whole row as it was, for the undo step and for Escape.
      before: WB_KIND_INFO[row.entry.kind].payload(row.entry.item),
    }));
  }

  //: Escape during a group's resize or turn: every member back as the grip
  //: found it, on screen only (nothing was saved yet).
  function wbRestoreMultiSnapshot(rows) {
    for (const row of rows || []) {
      const item = row.entry.item;
      if (row.entry.kind === "sketch") {
        delete item._liveD;
        delete item._dragLiveD;
        const selector = `.sketch-group[data-id="${item.id}"]`;
        document.querySelector(`${selector} .sketch-path`)?.setAttribute("d", row.d);
        document.querySelector(`${selector} .sketch-hitbox`)?.setAttribute("d", row.d);
        wbLayoutShapeLabel(document.querySelector(selector));
        continue;
      }
      wbRestoreBox(row.entry.kind, item, row.before);
    }
  }

  //: **What follows a group's resize or turn live** (the wb ledger, 10-25):
  //: every connector touching a member, once (a link between two members is one
  //: path), and each shape member's own outline, which is drawn in the board
  //: layer apart from the group's box and stayed at the old size until release.
  function wbMultiLiveLinks(rows) {
    const index = wbLinkSketchIndex();
    return [...new Set(rows.flatMap((r) => wbLinkedSketchesFor(r.entry.item.id, r.entry.kind, index)))];
  }

  function wbMultiMemberOutline(id) {
    return wbInstances.query(`#wb-zoom-group .wb-sketch-handle-group[data-sketch-id="${id}"]`);
  }

  function wbFollowMultiOutline(id, liveD) {
    const box = wbMultiMemberOutline(id)?.querySelector(".wb-sketch-selection-box");
    const bb = liveD ? wbPathBBox(liveD) : null;
    if (!box || !bb) return;
    box.setAttribute("x", bb.minX - 2);
    box.setAttribute("y", bb.minY - 2);
    box.setAttribute("width", (bb.maxX - bb.minX) + 4);
    box.setAttribute("height", (bb.maxY - bb.minY) + 4);
  }

  //: Saving a whole group, one write at a time. Each write is the item's whole
  //: row and the board's stale-client recovery reloads everything, which a
  //: burst of simultaneous writes would race.
  async function wbSaveMultiSnapshot(rows) {
    //: One undo step for the whole group (it had none: Ctrl+Z after resizing
    //: or turning a selection put nothing back).
    wbPushDragUndo(rows.map((row) => ({
      action: "move", kind: row.entry.kind, id: row.entry.item.id, before: row.before,
    })));
    for (const row of rows) {
      if (row.entry.kind !== "sketch") continue;
      const live = row.entry.item._liveD;
      delete row.entry.item._liveD;
      delete row.entry.item._dragLiveD;
      if (live) wbSketchSetD(row.entry.item, live);
    }
    await wbSaveMany(rows.map((row) => ({ kind: row.entry.kind, item: row.entry.item })));
    wbScheduleRender();
  }

  function wbRenderMultiSelectionHandles() {
    //: Not round several topics on a map (INBOX 617): the layout owns where a
    //: topic sits, so the box's eight sizes and its turn could only fight it.
    //: Each topic keeps its own outline (`.wb-in-group`).
    if (wbMapMultiTopics()) return;
    const entries = wbMultiSelectionEntries();
    if (entries.length < 2) return;
    const boxes = entries.map((entry) => ({ entry, box: wbEntryBox(entry) })).filter((row) => row.box);
    if (boxes.length < 2) return;
    //: The outline is drawn around what the items occupy (rotation included);
    //: `row.box` stays the layout box, because that is what the resize below
    //: writes back. See `wbEntryOutlineBox` for why the two cannot be one.
    const outlines = boxes.map((row) => wbEntryOutlineBox(row.entry) || row.box);
    const bbox = {
      minX: Math.min(...outlines.map((box) => box.minX)),
      minY: Math.min(...outlines.map((box) => box.minY)),
      maxX: Math.max(...outlines.map((box) => box.maxX)),
      maxY: Math.max(...outlines.map((box) => box.maxY)),
    };
    //: **Each member is outlined, and only the group carries grips** (INBOX
    //: 278's second half). A shape had nothing drawn round it at all in a
    //: marquee selection, which was reported ("when I drag select shapes, the
    //: individual anchor/rotate boxes dont appear... its fine for the notes but
    //: the shapes and lines arent selected visually and individually"), and the
    //: answer then was to give every member its own full set of handles. That
    //: is what the second screenshot in 278 shows: a three-item group drew
    //: **eight** rotate knobs and sixteen resize handles, one set per member
    //: plus the group's, so the stem the eye lands on rises from a member's own
    //: centre or sits below the group's top border, and no one of them reads as
    //: the group's. Both reports are answered by drawing the member's outline
    //: and nothing else: what is selected is still visible one by one, and
    //: there is exactly one thing to grab.
    for (const row of boxes) {
      if (row.entry.kind === "sketch") wbDrawSketchHandles(row.entry.item, { outlineOnly: true });
    }
    //: **The overlay layer, not the base one** (INBOX 262: "not being able to
    //: drag the edges of a group selection"). The base SVG paints *under*
    //: `#wb-html-layer`, which is where a card and its own eight handles live,
    //: so a group handle that landed on a member's corner was both invisible
    //: and unclickable: measured with `elementFromPoint` at each handle's own
    //: centre, 6 of the 8 returned a card's `.wb-resize-handle` instead. The
    //: link endpoint handles moved up here for exactly this reason and their
    //: comment records it; a group box is the same case, since its corners are
    //: the union of the members' corners and so sit on a member by definition.
    //:
    //: The members keep their own handles, visible and usable away from the
    //: group's eight: that was asked for directly ("when I drag select shapes,
    //: the individual anchor/rotate boxes dont appear"), so the fix is which
    //: layer wins the press, not which handles are drawn.
    const group = d3.select(wbInstances.layer("wb-overlay-zoom-group"))
      .append("g")
      .attr("class", "wb-sketch-handle-group wb-multi-handle-group");
    const boxRect = group.append("rect").attr("class", "wb-sketch-selection-box");

    //: **The chrome is laid out from a box rather than drawn at fixed points.**
    //: Reported: "the group selection outline doesnt resize with the objects
    //: selected in side them when resizing or rotating the group selection".
    //: Every part of it was positioned once, from the bbox as it stood when the
    //: selection was made, so a drag moved the items and left the outline and
    //: its eight anchors behind: you were pulling a handle that was no longer on
    //: the corner it belonged to, with the box crossing the middle of what it
    //: was supposed to contain. One function that can be called again with a
    //: new box, from every frame of the drag, is the fix; a redraw is not,
    //: because it would replace the element the gesture is bound to.
    const handleAt = new Map();
    let stem = null, spinDot = null;
    function layoutGroupChrome(box) {
      boxRect
        .attr("x", box.minX - 2).attr("y", box.minY - 2)
        .attr("width", (box.maxX - box.minX) + 4)
        .attr("height", (box.maxY - box.minY) + 4);
      for (const [name, el] of handleAt) {
        const hx = name.includes("w") ? box.minX : name.includes("e") ? box.maxX : (box.minX + box.maxX) / 2;
        const hy = name.includes("n") ? box.minY : name.includes("s") ? box.maxY : (box.minY + box.maxY) / 2;
        el.attr("x", hx - 5).attr("y", hy - 5);
      }
      const cx = (box.minX + box.maxX) / 2;
      //: **The anchor, without which the grip leaves the box** (INBOX 278: "the
      //: rotate line and circle dont sit at the top center of a group
      //: selection... and instead sit off to the top left or right, or below the
      //: top border"). `.wb-sketch-rotate-handle` and `.wb-rotate-handle-stem`
      //: carry `scale(var(--wb-inv-zoom))` so a grip stays one size to the hand,
      //: and that rule keeps `transform-box` at its `view-box` default *because
      //: the code that draws them sets the origin in board units* (the rule says
      //: so in its own comment, and `wbDrawSketchHandles` does it for a single
      //: shape). This group never set one, so the scale resolved about the SVG
      //: view box's origin and multiplied the grip's own coordinates by `1 / k`:
      //: measured on a three-item group, the knob sat at board (680, 1344) at
      //: 0.5x and (170, 336) at 2x for a box whose top centre is (340, 672), so
      //: it flew down and right when you zoomed out and up and left when you
      //: zoomed in, while sitting exactly right at 1x. The foot of the stem is
      //: the point that must not move, the same anchor the single-shape handles
      //: use, and it is re-set here rather than once at creation because a
      //: resize drag calls this again with a new box.
      const anchor = `${cx}px ${box.minY}px`;
      if (stem) {
        stem.attr("x1", cx).attr("y1", box.minY).attr("x2", cx).attr("y2", box.minY - 28)
          .style("transform-origin", anchor);
      }
      if (spinDot) spinDot.attr("cx", cx).attr("cy", box.minY - 28).style("transform-origin", anchor);
    }

    //: The box the items now occupy, given the scale this frame is applying.
    //: The same arithmetic the items themselves get, so the outline cannot
    //: disagree with what it is drawn around.
    function scaledBox(t) {
      return {
        minX: t.anchorX + (bbox.minX - t.anchorX) * t.sx,
        minY: t.anchorY + (bbox.minY - t.anchorY) * t.sy,
        maxX: t.anchorX + (bbox.maxX - t.anchorX) * t.sx,
        maxY: t.anchorY + (bbox.maxY - t.anchorY) * t.sy,
      };
    }

    //: The state every frame of the drag is computed from. Taken once at the
    //: start rather than read back off the items, which would compound each
    //: frame's rounding into a shape that drifts while you hold the mouse
    //: still, the accumulation bug the single-shape handles document.
    let start = null, sizeLinks = [];
    let groupGesture = null;
    for (const handle of ["nw", "n", "ne", "e", "se", "s", "sw", "w"]) {
      const hx = handle.includes("w") ? bbox.minX : handle.includes("e") ? bbox.maxX : (bbox.minX + bbox.maxX) / 2;
      const hy = handle.includes("n") ? bbox.minY : handle.includes("s") ? bbox.maxY : (bbox.minY + bbox.maxY) / 2;
      let rawDX = 0, rawDY = 0;
      const handleEl = group.append("rect")
        .attr("class", "wb-sketch-resize-handle")
        .attr("data-handle", handle)
        .attr("x", hx - 5).attr("y", hy - 5)
        .attr("width", 10).attr("height", 10)
        .style("cursor", `${handle}-resize`)
        .call(
          d3.drag()
            .on("start", (event) => {
              event.sourceEvent.stopPropagation();
              rawDX = 0;
              rawDY = 0;
              start = wbMultiSnapshot(boxes);
              const rows = start;
              sizeLinks = wbMultiLiveLinks(rows);
              const links = sizeLinks;
              groupGesture = wbBeginGesture(() => {
                wbRestoreMultiSnapshot(rows);
                for (const row of rows) if (row.entry.kind === "sketch") wbFollowMultiOutline(row.entry.item.id, row.d);
                if (links.length) wbUpdateLinkedSketches(null, links);
                wbClearAlignmentGuides();
                layoutGroupChrome(bbox);
              });
            })
            .on("drag", (event) => {
              if (!start || groupGesture?.cancelled) return;
              const zoom = d3.zoomTransform(wbInstances.container());
              rawDX += event.dx / zoom.k;
              rawDY += event.dy / zoom.k;
              const raw = wbSketchResizeTransform(bbox, handle, rawDX, rawDY, event.sourceEvent.shiftKey, event.sourceEvent.altKey);
              //: **A corner scales a group proportionally** (the owner: "when I
              //: try to resizr the multiple selected objects with the group box,
              //: the items all go out of proportion and funky"). A single shape
              //: stretching on one axis is a shape being reshaped, which is what
              //: you asked for by grabbing its corner; a *set* of things doing it
              //: is every circle in the set turning into a different ellipse and
              //: every card into a different rectangle, which is never what the
              //: gesture meant. The driving axis wins, so the corner still
              //: follows the pointer in the direction it was pulled, and shift
              //: releases the lock for a deliberate stretch.
              const corner = handle.length === 2;
              const free = event.sourceEvent.shiftKey;
              const k = Math.abs(raw.sx - 1) >= Math.abs(raw.sy - 1) ? raw.sx : raw.sy;
              const t = corner && !free ? { ...raw, sx: k, sy: k } : raw;
              for (const row of start) {
                if (row.entry.kind === "sketch") {
                  row.kind ??= wbSketchParsedData(row.entry.item)?.shapeKind || "";
                  const newD = (wbFmtState.shapeTable?.resized(row.d, t, row.kind, wbTransformPathD, wbPathBBox) ?? wbTransformPathD(row.d, t));
                  const selector = `.sketch-group[data-id="${row.entry.item.id}"]`;
                  document.querySelector(`${selector} .sketch-path`)?.setAttribute("d", newD);
                  document.querySelector(`${selector} .sketch-hitbox`)?.setAttribute("d", newD);
                  wbLayoutShapeLabel(document.querySelector(selector));
                  row.entry.item._liveD = newD;
                  row.entry.item._dragLiveD = newD;
                  wbFollowMultiOutline(row.entry.item.id, newD);
                  continue;
                }
                const item = row.entry.item;
                item.x = t.anchorX + (row.box.minX - t.anchorX) * t.sx;
                item.y = t.anchorY + (row.box.minY - t.anchorY) * t.sy;
                item.width = Math.max(WB_OBJECT_MIN_SIZE, (row.box.maxX - row.box.minX) * t.sx);
                item.height = Math.max(WB_OBJECT_MIN_SIZE, (row.box.maxY - row.box.minY) * t.sy);
                //: The drag accumulator is a running position from the *last*
                //: drag, and anything that moves an item behind its back has to
                //: drop it or the next drag starts from where the item used to
                //: be.
                delete item._rawX;
                delete item._rawY;
                //: Written straight to the element rather than through a
                //: render: a render rebuilds the selection chrome, which
                //: includes the very handle this drag is bound to, and the
                //: gesture dies the moment its element is replaced. The
                //: single-shape handles avoid the same trap the same way.
                const el = document.querySelector(WB_SELECTOR_BY_KIND[row.entry.kind](item.id));
                if (el) {
                  el.style.transform = wbItemTransform(item);
                  el.style.width = `${item.width}px`;
                  el.style.height = `${item.height}px`;
                }
              }
              if (sizeLinks.length) wbUpdateLinkedSketches(null, sizeLinks);
              const live = scaledBox(t);
              layoutGroupChrome(live);
              //: The size beside the box, as a single item's resize shows it.
              wbShowAlignmentGuides([]);
              wbShowSizeReadout({ x: live.minX, y: live.minY, w: live.maxX - live.minX, h: live.maxY - live.minY });
            })
            .on("end", async () => {
              wbClearAlignmentGuides();
              if (!start) return;
              const rows = start;
              start = null;
              const cancelled = wbEndGesture(groupGesture);
              groupGesture = null;
              if (cancelled) return;
              await wbSaveMultiSnapshot(rows);
            })
        );
      handleAt.set(handle, handleEl);
    }

    //: **And a rotate point above the box** (the owner: "the group boxes dont
    //: have a rotate point at the top"). Every item turns about the group's
    //: centre, which for a card or a text box is a move *and* a rotation of its
    //: own: the box travels round the centre and then faces the new direction.
    //: A shape has no rotation column, so its turn is baked into the path the
    //: same way its own rotate handle bakes one.
    //:
    //: The angle is absolute, read straight off the pointer's bearing from the
    //: centre, which is what makes the handle follow the cursor rather than
    //: drift by a per-frame delta. Shift snaps to 15 degrees, the same as
    //: everywhere else on this board.
    const centerX = (bbox.minX + bbox.maxX) / 2;
    const centerY = (bbox.minY + bbox.maxY) / 2;
    const handleY = bbox.minY - 28;
    stem = group.append("line")
      .attr("class", "wb-rotate-handle-stem")
      .attr("x1", centerX).attr("y1", bbox.minY).attr("x2", centerX).attr("y2", handleY);
    let spin = null, spinLinks = [];
    spinDot = group.append("circle")
      .attr("class", "wb-sketch-rotate-handle")
      .attr("cx", centerX).attr("cy", handleY).attr("r", 6)
      .style("cursor", "grab")
      .call(
        d3.drag()
          .on("start", (event) => {
            event.sourceEvent.stopPropagation();
            spin = wbMultiSnapshot(boxes);
            const rows = spin;
            //: Each link touching a turned card or box, once (a link between two
            //: selected items is one path), so its ends follow the turn live.
            //: Shapes too: a turned shape's live path is `_dragLiveD`, which the
            //: link's end reads, so a connector to a shape follows the turn.
            spinLinks = wbMultiLiveLinks(rows);
            const links = spinLinks;
            groupGesture = wbBeginGesture(() => {
              wbRestoreMultiSnapshot(rows);
              for (const row of rows) wbMultiMemberOutline(row.entry.item.id)?.removeAttribute("transform");
              if (links.length) wbUpdateLinkedSketches(null, links);
              group.attr("transform", null);
            });
          })
          .on("drag", (event) => {
            if (!spin || groupGesture?.cancelled) return;
            const angle = wbSketchAngleFromCenterDeg(
              centerX, centerY, event.sourceEvent, event.sourceEvent.shiftKey
            );
            const theta = (angle * Math.PI) / 180;
            const cos = Math.cos(theta), sin = Math.sin(theta);
            for (const row of spin) {
              if (row.entry.kind === "sketch") {
                const newD = wbTransformPathD(row.d, {
                  rotate: angle, anchorX: centerX, anchorY: centerY,
                });
                const selector = `.sketch-group[data-id="${row.entry.item.id}"]`;
                document.querySelector(`${selector} .sketch-path`)?.setAttribute("d", newD);
                document.querySelector(`${selector} .sketch-hitbox`)?.setAttribute("d", newD);
                wbLayoutShapeLabel(document.querySelector(selector));
                row.entry.item._liveD = newD;
                row.entry.item._dragLiveD = newD;
                //: Its outline turns about the same centre as the group's box.
                wbMultiMemberOutline(row.entry.item.id)?.setAttribute("transform", `rotate(${angle} ${centerX} ${centerY})`);
                continue;
              }
              const item = row.entry.item;
              const w = row.box.maxX - row.box.minX, h = row.box.maxY - row.box.minY;
              //: The box turns about its own centre (`wbItemTransform` translates
              //: and then rotates, so the origin is the element's middle), which
              //: is why the point carried round the group's centre is the item's
              //: centre and not its corner.
              const relX = row.box.minX + w / 2 - centerX;
              const relY = row.box.minY + h / 2 - centerY;
              item.x = centerX + relX * cos - relY * sin - w / 2;
              item.y = centerY + relX * sin + relY * cos - h / 2;
              item.rotation = (row.rotation + angle) % 360;
              delete item._rawX;
              delete item._rawY;
              const el = document.querySelector(WB_SELECTOR_BY_KIND[row.entry.kind](item.id));
              if (el) el.style.transform = wbItemTransform(item);
            }
            if (spinLinks.length) wbUpdateLinkedSketches(null, spinLinks);
            //: The outline turns with what it contains rather than being
            //: recomputed as a new upright box: a box that stayed level while
            //: its contents turned is the "doesnt rotate with them" half of the
            //: same report, and an upright box round a turned set is also the
            //: wrong shape, since the set no longer fills it.
            group.attr("transform", `rotate(${angle} ${centerX} ${centerY})`);
          })
          .on("end", async () => {
            if (!spin) return;
            const rows = spin;
            spin = null;
            //: Dropped, not kept: the render that follows the save rebuilds this
            //: whole group from the items' new positions, and a transform left
            //: on it would be applied a second time on top of them.
            group.attr("transform", null);
            const cancelled = wbEndGesture(groupGesture);
            groupGesture = null;
            if (cancelled) return;
            await wbSaveMultiSnapshot(rows);
          })
      );
    layoutGroupChrome(bbox);
  }

  //: **A shape's lines and clone arrows follow it while it is stretched or
  //: turned**, not only when it is moved (INBOX 740, 746). A move already keeps
  //: its live path in `_dragLiveD`, which `wbItemBBox` and the outline a link
  //: meets both read; a resize and a turn now put theirs there too for the
  //: length of the gesture, and `null` takes it away at the end, before the
  //: save writes the path for good.
  function wbFollowLiveShape(sketch, liveD) {
    if (liveD == null) {
      delete sketch._dragLiveD;
      delete sketch._followLinks;
      return;
    }
    sketch._dragLiveD = liveD;
    if (!sketch._followLinks) sketch._followLinks = wbLinkedSketchesFor(sketch.id, "sketch");
    if (sketch._followLinks.length) wbUpdateLinkedSketches(sketch.id, sketch._followLinks);
    wbQueueSelectionBar();
  }

  function wbRenderSketchHandles() {
    wbClearSketchHandles();
    if (!wbSelectedItem || wbSelectedItem.kind !== "sketch") return;
    const sketch = wbState.sketches.find((s) => s.id === wbSelectedItem.id);
    if (!sketch) return;
    wbDrawSketchHandles(sketch);
  }

  //: **One shape's own box and anchors**, split out from the single-selection
  //: renderer above so a sweep can draw them for every shape it caught. The
  //: owner, with a screenshot of a selected face beside a pair of selected
  //: notes: "when I drag select shapes, the individual anchor/rotate boxes dont
  //: appear ... see how its fine for the notes but the shapes and lines arent
  //: selected visually and individually??" A card and a text box carry their
  //: eight handles as children of the element, so `.wb-selected` alone reveals
  //: them; a shape is a path in the SVG layer with nowhere to keep handles, and
  //: this is the only thing that draws them. It ran for the single selection
  //: only, which is exactly the difference the screenshot shows.
  //: `outlineOnly` draws the selection box and stops: a member of a group
  //: selection is shown as selected without being given grips of its own, which
  //: belong to the group (INBOX 278). A link's endpoint handles are grips too,
  //: so that branch takes the same exit.
  function wbDrawSketchHandles(sketch, { outlineOnly = false } = {}) {
    // A link sketch has no `.d` of its own: `wbSketchParsedData` returns
    // null for it, and the 8-point bbox resize handles below make no sense
    // for a path recomputed fresh from its endpoints every render anyway.
    // It gets its own two endpoint handles instead (below).
    let rawParsed;
    try { rawParsed = JSON.parse(sketch.data); } catch { rawParsed = null; }
    if (rawParsed && (rawParsed.type || "").startsWith("link-")) {
      if (!outlineOnly) wbRenderLinkEndpointHandles(sketch, rawParsed);
      return;
    }
    const parsed = wbSketchParsedData(sketch);
    if (!parsed) return;
    const bbox = wbPathBBox(parsed.d);
    if (!bbox) return;

    //: A lone selection's grips go in the overlay, above the HTML objects that
    //: can lie over the shape (3 of 8 grips were under a text box: measured
    //: with `elementFromPoint`); a multi member's bare outline stays under.
    const group = d3.select(wbInstances.query(outlineOnly ? "#wb-zoom-group" : "#wb-overlay-zoom-group"))
      .append("g")
      .attr("class", "wb-sketch-handle-group")
      .attr("data-sketch-id", sketch.id);

    //: **One selection box for every kind** (WHITEBOARD_PLAN.md decision 6). A
    //: card and a text box wear a 1px `--accent` outline; a sketch wore a dashed
    //: 35%-opacity stroke *along its own path* instead, so the same click read
    //: as two different kinds of thing and a thin diagonal line had no box at
    //: all. This is that outline, drawn round the shape's own bbox.
    group.append("rect")
      .attr("class", "wb-sketch-selection-box")
      .attr("x", bbox.minX - 2).attr("y", bbox.minY - 2)
      .attr("width", (bbox.maxX - bbox.minX) + 4)
      .attr("height", (bbox.maxY - bbox.minY) + 4);

    if (outlineOnly) return;

    //: **The box and the grips follow a resize while it happens**, with the
    //: size beside them, as a card's do (the 22-10 bug doc: "Shape anchor
    //: points and selection borders don't resize with the user's" drag). They
    //: were drawn once from the old bbox and only moved on the release render.
    const placeGrips = (bb) => {
      const node = group.node();
      const box = node.querySelector(".wb-sketch-selection-box");
      box.setAttribute("x", bb.minX - 2);
      box.setAttribute("y", bb.minY - 2);
      box.setAttribute("width", (bb.maxX - bb.minX) + 4);
      box.setAttribute("height", (bb.maxY - bb.minY) + 4);
      for (const grip of node.querySelectorAll(".wb-sketch-resize-handle")) {
        const h = grip.dataset.handle;
        grip.setAttribute("x", (h.includes("w") ? bb.minX : h.includes("e") ? bb.maxX : (bb.minX + bb.maxX) / 2) - 5);
        grip.setAttribute("y", (h.includes("n") ? bb.minY : h.includes("s") ? bb.maxY : (bb.minY + bb.maxY) / 2) - 5);
      }
      const midX = (bb.minX + bb.maxX) / 2;
      const origin = `${midX}px ${bb.minY}px`;
      const stem = node.querySelector(".wb-rotate-handle-stem");
      if (stem) {
        stem.setAttribute("x1", midX);
        stem.setAttribute("x2", midX);
        stem.setAttribute("y1", bb.minY);
        stem.setAttribute("y2", bb.minY - 28);
        stem.style.transformOrigin = origin;
      }
      const turn = node.querySelector(".wb-sketch-rotate-handle");
      if (turn) {
        turn.setAttribute("cx", midX);
        turn.setAttribute("cy", bb.minY - 28);
        turn.style.transformOrigin = origin;
      }
    };

    for (const handle of ["nw", "n", "ne", "e", "se", "s", "sw", "w"]) {
      const hx = handle.includes("w") ? bbox.minX : handle.includes("e") ? bbox.maxX : (bbox.minX + bbox.maxX) / 2;
      const hy = handle.includes("n") ? bbox.minY : handle.includes("s") ? bbox.maxY : (bbox.minY + bbox.maxY) / 2;
      let rawDX = 0, rawDY = 0; // this handle's own running total for the drag closure below
      group.append("rect")
        .attr("class", "wb-sketch-resize-handle")
        .attr("data-handle", handle)
        .attr("x", hx - 5).attr("y", hy - 5)
        .attr("width", 10).attr("height", 10)
        .style("cursor", `${handle}-resize`)
        .call(
          d3.drag()
            .on("start", (event) => {
              event.sourceEvent.stopPropagation();
              // event.dx/dy are per-frame deltas (since the *previous* event,
              // not since the drag started), recomputing the transform from
              // the original bbox using only the latest frame's delta each
              // time would apply just that one frame's worth of movement and
              // throw the rest away. Accumulated from the start instead, the
              // same fix as the drag-snap accumulation bug above.
              rawDX = 0;
              rawDY = 0;
              sketch._resizeUndoBefore = WB_KIND_INFO.sketch.payload(sketch);
              sketch._gesture = wbBeginGesture(() => {
                delete sketch._liveD;
                wbInstances.query(`.sketch-group[data-id="${sketch.id}"] .sketch-path`)?.setAttribute("d", parsed.d);
                wbInstances.query(`.sketch-group[data-id="${sketch.id}"] .sketch-hitbox`)?.setAttribute("d", parsed.d);
                wbLayoutShapeLabel(wbInstances.query(`.sketch-group[data-id="${sketch.id}"]`));
              });
            })
            .on("drag", (event) => {
              if (sketch._gesture?.cancelled) return;
              // No `/ transform.k`, for the reason the link endpoint handle
              // above already records: this rect's drag container is its parent
              // `<g>` inside the zoomed `#wb-zoom-group`, and d3.pointer
              // resolves SVG coordinates through `getScreenCTM()`, which has
              // already folded in every ancestor transform. `event.dx` arrives
              // in board units. Dividing again halved the gesture at 2x
              // (measured: a 60px drag on the east grip widened the shape by
              // 30px on screen, where the card's own grip moved the full 60).
              rawDX += event.dx;
              rawDY += event.dy;
              const t = wbSketchResizeTransform(bbox, handle, rawDX, rawDY, event.sourceEvent.shiftKey || wbKeepsRatio("sketch", sketch), event.sourceEvent.altKey);
              const newD = (wbFmtState.shapeTable?.resized(parsed.d, t, parsed.shapeKind, wbTransformPathD, wbPathBBox) ?? wbTransformPathD(parsed.d, t));
              wbInstances.query(`.sketch-group[data-id="${sketch.id}"] .sketch-path`)?.setAttribute("d", newD);
              wbInstances.query(`.sketch-group[data-id="${sketch.id}"] .sketch-hitbox`)?.setAttribute("d", newD);
              wbLayoutShapeLabel(wbInstances.query(`.sketch-group[data-id="${sketch.id}"]`));
              sketch._liveD = newD; // read at drag end, without waiting for a full render
              wbFollowLiveShape(sketch, newD);
              const live = wbPathBBox(newD);
              if (live) {
                placeGrips(live);
                wbShowAlignmentGuides([]);
                wbShowSizeReadout({ x: live.minX, y: live.minY, w: live.maxX - live.minX, h: live.maxY - live.minY });
              }
            })
            .on("end", async () => {
              wbClearAlignmentGuides();
              wbFollowLiveShape(sketch, null);
              const before = sketch._resizeUndoBefore;
              delete sketch._resizeUndoBefore;
              if (wbEndGesture(sketch._gesture)) delete sketch._liveD;
              delete sketch._gesture;
              if (sketch._liveD) {
                const finalD = sketch._liveD;
                delete sketch._liveD;
                //: A stretch of a turned shape is a new shape: turning it back
                //: by the old angle would give a skewed one, not an upright one,
                //: so the kept turn goes with the resize.
                await wbSaveSketchProps(sketch, { d: finalD, turned: 0 });
                if (before) wbPushUndo({ action: "move", kind: "sketch", id: sketch.id, before });
              }
              wbScheduleRender();
            })
        );
    }

    // Rotation: asked for directly, the one thing cards/objects already had
    // (a drag handle above the item, Shift snaps to 15°) that a sketch
    // didn't, since its "shape" is its path data rather than a stored
    // rotation column. Baked into `d` on release via `wbTransformPathD`'s new
    // `rotate` support, the same "commit into the path" convention move and
    // resize already use for a sketch, not a live CSS transform, which
    // would need a rotation to remember and re-apply on every future edit
    // instead of just being the shape's own coordinates.
    const centerX = (bbox.minX + bbox.maxX) / 2, centerY = (bbox.minY + bbox.maxY) / 2;
    const handleY = bbox.minY - 28;
    //: The anchor both halves of this control are scaled about, in board units:
    //: the point where the stem meets the shape. See the grip rules in
    //: 07-whiteboard-misc.css: the circle and the stem are siblings rather than
    //: an element and its pseudo-element, so the shared origin cannot be written
    //: as a percentage of either one and has to come from the bbox here.
    const rotateAnchor = `${centerX}px ${bbox.minY}px`;
    group.append("line")
      .attr("class", "wb-rotate-handle-stem")
      .style("transform-origin", rotateAnchor)
      .attr("x1", centerX).attr("y1", bbox.minY).attr("x2", centerX).attr("y2", handleY);
    // Absolute, not incremental: the handle sits straight above the shape's
    // centre (0°, the same reference `wbAngleFromCenterDeg` uses), so the
    // rotation applied is exactly the pointer's own angle from vertical, the
    // same "the handle follows your cursor" feel `nodeRotateDrag` above
    // already established for cards.
    let rotateOriginalD = null, rotateLiveD = null, rotateLiveAngle = 0, spinEls = null;
    const shapeGrip = group.append("circle")
      .attr("class", "wb-sketch-rotate-handle")
      // r 6, not 7: the card and text-box grip is 12px across
      // (`.wb-rotate-handle`), and 14 against 12 was the one measured difference
      // left between the two recipes.
      .attr("cx", centerX).attr("cy", handleY).attr("r", 6)
      .style("transform-origin", rotateAnchor)
      .style("cursor", "grab")
      .call(
        d3.drag()
          .on("start", (event) => {
            event.sourceEvent.stopPropagation();
            rotateOriginalD = parsed.d;
            sketch._rotateUndoBefore = WB_KIND_INFO.sketch.payload(sketch);
            sketch._gesture = wbBeginGesture(() => {
              rotateLiveD = null;
              group.attr("transform", null);
              wbInstances.query(`.sketch-group[data-id="${sketch.id}"] .sketch-path`)?.setAttribute("d", parsed.d);
              wbInstances.query(`.sketch-group[data-id="${sketch.id}"] .sketch-hitbox`)?.setAttribute("d", parsed.d);
              wbLayoutShapeLabel(wbInstances.query(`.sketch-group[data-id="${sketch.id}"]`));
            });
          })
          .on("drag", (event) => {
            if (sketch._gesture?.cancelled) return;
            const currentAngle = wbSketchAngleFromCenterDeg(centerX, centerY, event.sourceEvent, event.sourceEvent.shiftKey);
            const newD = wbTransformPathD(rotateOriginalD, { rotate: currentAngle, anchorX: centerX, anchorY: centerY });
            rotateLiveD = newD;
            rotateLiveAngle = currentAngle;
            //: **The box turns with the shape** (the wb ledger, 10-25): it was
            //: drawn once round the upright shape and stayed there while the
            //: shape swung out of it. The whole handle group turns about the
            //: same centre, as a card's outline does, and the grip stays under
            //: the pointer; the release render draws the new shape's own box.
            group.attr("transform", `rotate(${currentAngle} ${centerX} ${centerY})`);
            //: Looked up on the first frame, not every frame.
            spinEls ||= wbSketchLiveEls(sketch.id);
            spinEls.path?.setAttribute("d", newD);
            spinEls.hit?.setAttribute("d", newD);
            wbLayoutShapeLabel(spinEls.g);
            wbFollowLiveShape(sketch, newD);
          })
          .on("end", async () => {
            spinEls = null;
            wbFollowLiveShape(sketch, null);
            const before = sketch._rotateUndoBefore;
            delete sketch._rotateUndoBefore;
            if (wbEndGesture(sketch._gesture)) rotateLiveD = null;
            delete sketch._gesture;
            if (rotateLiveD) {
              const finalD = rotateLiveD;
              rotateLiveD = null;
              //: The running total `wbResetRotation` turns the shape back by.
              const turned = ((Number(parsed.turned) || 0) + rotateLiveAngle) % 360;
              await wbSaveSketchProps(sketch, { d: finalD, turned });
              //: Repeat last turns the next selection by what this drag turned by (the turn is baked into the path, so there
              //: is no stored rotation to read it back from).
              wbFmtState.keys?.record({ kind: "turn", deg: rotateLiveAngle });
              if (before) wbPushUndo({ action: "move", kind: "sketch", id: sketch.id, before });
              //: Only after a real turn. A render rebuilds this grip, and a
              //: press that turned nothing (half of a double-click) then left
              //: the second press on a different element, so the browser sent
              //: the double-click to the canvas behind it and the reset never
              //: ran (measured: the event's target was `#wb-svg-layer`).
              wbScheduleRender();
            }
          })
      );
    //: The grip's two gestures, written on it: an SVG shape's tooltip is its
    //: `<title>`, the same way the map's line grip says what it does.
    shapeGrip.append("title").text("Drag to rotate: Shift snaps to 15°, double-click stands it upright");
  }

  //: The file's surface: what other files call (L634).
  //: Private names a sweep drives (scratchpad/ui-sweeps), on an exported name so the shared scope does not grow.
  wbRenderSketchHandles.sweep = { wbDrawSketchHandles, wbSketchIsArrow };
  Object.assign(window, { wbTransformPathD, wbPathBBox, wbResizeBox, wbSketchIsClosedShape, wbBucketFillSketch, wbSketchTakesCaps, wbToolCaps, wbRegenerateShapeCaps, wbSketchCaps, wbClearSketchHandles, wbLinkWaypoints, wbLinkDrawnLine, wbLinkLabelT, wbLinkNearestT, wbRenderMultiSelectionHandles, wbRenderSketchHandles });
})();
