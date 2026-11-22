(() => {
  // whiteboard-guides.js: alignment guides, spacing and grid, moved out of whiteboard.js (L634).
  // Wrapped: only what other files call goes on `window`; nothing here runs at load.

  //: **The box the whole selection occupies, for a group drag.**
  //:
  //: A single drag asks the guides about the item under the pointer. A group
  //: drag has no single item to ask about, which is why it used to ask about
  //: nothing: the guide block was written `if (!bypassSnap && !d._bulkOrigin)`,
  //: so selecting several things and moving them turned the alignment guides
  //: off, exactly when lining things up is what you are doing.
  //:
  //: What a group should align is its own outer box, which is what every
  //: drawing app does with a multi-selection. `_bulkOrigin` holds every *other*
  //: member at the position the drag started from (the dragged item is
  //: deliberately not in it, since its own handler moves it), so the group's
  //: starting box is those plus the dragged item's own origin, and its box
  //: this frame is that shifted by how far the dragged item has come.
  //:
  //: Returns null when there is nothing to measure, so the caller falls back
  //: to the plain single-item path rather than guessing.
  //: `self` is for a dragged item that has no x/y/width/height of its own: a
  //: sketch is a path, and its box has to be measured from that path rather
  //: than read off the datum. Pass `{minX, minY, maxX, maxY, dx, dy}` (the
  //: item's box *before* this drag, and how far it has come) and the rest of
  //: the maths is identical, which is the point of threading it through here
  //: instead of writing the union a second time.
  function wbBulkGroupBox(d, kind, self = null) {
    if (!d._bulkOrigin || !d._bulkOrigin.size) return null;
    if (!self && (d._dragOriginX === undefined || d._dragOriginY === undefined)) return null;
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    const add = (box) => {
      if (!box) return;
      minX = Math.min(minX, box.minX);
      minY = Math.min(minY, box.minY);
      maxX = Math.max(maxX, box.maxX);
      maxY = Math.max(maxY, box.maxY);
    };
    add(
      self || {
        minX: d._dragOriginX,
        minY: d._dragOriginY,
        maxX: d._dragOriginX + (d.width || WB_CARD_DEFAULT_SIZE.w),
        maxY: d._dragOriginY + (d.height || WB_CARD_DEFAULT_SIZE.h),
      }
    );
    for (const entry of d._bulkOrigin.values()) {
      if (entry.kind === "sketch") {
        add(wbPathBBox(entry.d));
      } else if (entry.x !== undefined) {
        add({
          minX: entry.x,
          minY: entry.y,
          maxX: entry.x + (entry.item.width || WB_CARD_DEFAULT_SIZE.w),
          maxY: entry.y + (entry.item.height || WB_CARD_DEFAULT_SIZE.h),
        });
      }
    }
    if (!Number.isFinite(minX)) return null;
    const dx = self ? self.dx : d.x - d._dragOriginX;
    const dy = self ? self.dy : d.y - d._dragOriginY;
    return { x: minX + dx, y: minY + dy, w: maxX - minX, h: maxY - minY };
  }

  //: Which keys the guides must ignore: everything moving this frame. The
  //: dragged item alone for a plain drag, the whole selection for a group one,
  //: since `_bulkOrigin` was built from it.
  function wbDragExcludeKeys(d, kind) {
    if (!d._bulkOrigin || !d._bulkOrigin.size) return new Set([wbMultiKey(kind, d.id)]);
    return new Set([wbMultiKey(kind, d.id), ...d._bulkOrigin.keys()]);
  }

  function wbAlignmentGuides(excludeKeys, x, y, w, h, tol = WB_ALIGN_SNAP_PX) {
    const dragged = { left: x, centerX: x + w / 2, right: x + w, top: y, centerY: y + h / 2, bottom: y + h };
    let bestX = null, bestY = null;
    const others = wbGuideBoxes(excludeKeys, { x, y, w, h });
    {
      for (const box of others) {
        const other = {
          left: box.minX, centerX: (box.minX + box.maxX) / 2, right: box.maxX,
          top: box.minY, centerY: (box.minY + box.maxY) / 2, bottom: box.maxY,
        };
        for (const edge of ["left", "centerX", "right"]) {
          if (box.only && box.only !== edge) continue;
          const delta = other[edge] - dragged[edge];
          if (Math.abs(delta) <= tol && (!bestX || Math.abs(delta) < Math.abs(bestX.delta))) {
            bestX = { delta, at: other[edge], y1: Math.min(dragged.top, other.top), y2: Math.max(dragged.bottom, other.bottom), kind: edge === "centerX" ? "center" : "edge" };
          }
        }
        for (const edge of ["top", "centerY", "bottom"]) {
          if (box.only && box.only !== edge) continue;
          const delta = other[edge] - dragged[edge];
          if (Math.abs(delta) <= tol && (!bestY || Math.abs(delta) < Math.abs(bestY.delta))) {
            bestY = { delta, at: other[edge], x1: Math.min(dragged.left, other.left), x2: Math.max(dragged.right, other.right), kind: edge === "centerY" ? "center" : "edge" };
          }
        }
      }
    }
    //: **The line spans every box that shares it** (Figma, Miro), not only the
    //: nearest one: a second pass over the boxes, run only on a frame that
    //: snapped, extends the line across each box whose edge or centre sits on
    //: it and across the dragged box as it lands.
    const guideLines = [];
    const dx0 = bestX ? bestX.delta : 0, dy0 = bestY ? bestY.delta : 0;
    if (bestX) {
      let y1 = Math.min(bestX.y1, dragged.top + dy0), y2 = Math.max(bestX.y2, dragged.bottom + dy0);
      for (const box of others) {
        if (Math.abs(box.minX - bestX.at) < 0.5 || Math.abs(box.maxX - bestX.at) < 0.5 || Math.abs((box.minX + box.maxX) / 2 - bestX.at) < 0.5) {
          y1 = Math.min(y1, box.minY);
          y2 = Math.max(y2, box.maxY);
        }
      }
      guideLines.push({ x1: bestX.at, y1: y1 - 12, x2: bestX.at, y2: y2 + 12, kind: bestX.kind });
    }
    if (bestY) {
      let x1 = Math.min(bestY.x1, dragged.left + dx0), x2 = Math.max(bestY.x2, dragged.right + dx0);
      for (const box of others) {
        if (Math.abs(box.minY - bestY.at) < 0.5 || Math.abs(box.maxY - bestY.at) < 0.5 || Math.abs((box.minY + box.maxY) / 2 - bestY.at) < 0.5) {
          x1 = Math.min(x1, box.minX);
          x2 = Math.max(x2, box.maxX);
        }
      }
      guideLines.push({ x1: x1 - 12, y1: bestY.at, x2: x2 + 12, y2: bestY.at, kind: bestY.kind });
    }
    let dx = dx0, dy = dy0;

    // Equal-spacing guides ("same spacing", asked for directly): only tried on
    // an axis the edge/center snap above didn't already claim, so a card never
    // fights between "line up with this edge" and "match this gap" mid-drag.
    // Scoped to the single nearest neighbour each side, not every possible
    // triple: that is what draw.io and PowerPoint show too, and it keeps this
    // O(n) per drag frame like the alignment pass above it, not O(n^2).
    if (!bestX) {
      const rowMates = others.filter((b) => (!b.only || b.only === "left" || b.only === "right") && b.minY < dragged.bottom && b.maxY > dragged.top);
      const left = rowMates.filter((b) => b.maxX <= dragged.left + tol).sort((a, b) => b.maxX - a.maxX)[0];
      const right = rowMates.filter((b) => b.minX >= dragged.right - tol).sort((a, b) => a.minX - b.minX)[0];
      if (left && right) {
        const gapLeft = dragged.left - left.maxX, gapRight = right.minX - dragged.right;
        if (gapLeft >= 0 && gapRight >= 0 && Math.abs(gapLeft - gapRight) <= tol) {
          const avgGap = (gapLeft + gapRight) / 2;
          dx = left.maxX + avgGap - dragged.left;
          const midY = (Math.max(left.minY, dragged.top) + Math.min(left.maxY, dragged.bottom)) / 2;
          guideLines.push({ x1: left.maxX, y1: midY, x2: dragged.left + dx, y2: midY, kind: "spacing" });
          guideLines.push({ x1: dragged.right + dx, y1: midY, x2: right.minX, y2: midY, kind: "spacing" });
        }
      }
      //: **Continue a row's spacing** (Figma and draw.io): with nothing on the
      //: other side, the gap to the nearest item matches the gap that item
      //: keeps to its own neighbour, so the third box of a row lands where the
      //: first two set the rhythm.
      if (!guideLines.some((l) => l.kind === "spacing" && l.y1 === l.y2)) {
        const series = wbSpacingSeries(rowMates, dragged, "x", tol);
        if (series) {
          dx = series.delta;
          guideLines.push(...series.lines);
        }
      }
    }
    if (!bestY) {
      const colMates = others.filter((b) => (!b.only || b.only === "top" || b.only === "bottom") && b.minX < dragged.right && b.maxX > dragged.left);
      const above = colMates.filter((b) => b.maxY <= dragged.top + tol).sort((a, b) => b.maxY - a.maxY)[0];
      const below = colMates.filter((b) => b.minY >= dragged.bottom - tol).sort((a, b) => a.minY - b.minY)[0];
      if (above && below) {
        const gapAbove = dragged.top - above.maxY, gapBelow = below.minY - dragged.bottom;
        if (gapAbove >= 0 && gapBelow >= 0 && Math.abs(gapAbove - gapBelow) <= tol) {
          const avgGap = (gapAbove + gapBelow) / 2;
          dy = above.maxY + avgGap - dragged.top;
          const midX = (Math.max(above.minX, dragged.left) + Math.min(above.maxX, dragged.right)) / 2;
          guideLines.push({ x1: midX, y1: above.maxY, x2: midX, y2: dragged.top + dy, kind: "spacing" });
          guideLines.push({ x1: midX, y1: dragged.bottom + dy, x2: midX, y2: below.minY, kind: "spacing" });
        }
      }
      if (!guideLines.some((l) => l.kind === "spacing" && l.x1 === l.x2)) {
        const series = wbSpacingSeries(colMates, dragged, "y", tol);
        if (series) {
          dy = series.delta;
          guideLines.push(...series.lines);
        }
      }
    }

    return { dx, dy, guideLines };
  }

  //: A row (`axis` "x") or column ("y") of boxes beside the dragged one: if the
  //: gap from it to its nearest neighbour on one side is within snapping of the
  //: gap that neighbour keeps to the next one out, the move that makes the two
  //: equal and the two spacing marks. Pure (node-tested).
  function wbSpacingSeries(mates, dragged, axis, tol = WB_ALIGN_SNAP_PX) {
    const lo = axis === "x" ? "minX" : "minY", hi = axis === "x" ? "maxX" : "maxY";
    const dLo = axis === "x" ? dragged.left : dragged.top, dHi = axis === "x" ? dragged.right : dragged.bottom;
    const cross = (b) => (axis === "x"
      ? (Math.max(b.minY, dragged.top) + Math.min(b.maxY, dragged.bottom)) / 2
      : (Math.max(b.minX, dragged.left) + Math.min(b.maxX, dragged.right)) / 2);
    const mark = (a, b, at) => (axis === "x"
      ? { x1: a, y1: at, x2: b, y2: at, kind: "spacing" }
      : { x1: at, y1: a, x2: at, y2: b, kind: "spacing" });
    let best = null;
    for (const side of [-1, 1]) {
      const near = side < 0
        ? mates.filter((b) => b[hi] <= dLo + tol).sort((a, b) => b[hi] - a[hi])[0]
        : mates.filter((b) => b[lo] >= dHi - tol).sort((a, b) => a[lo] - b[lo])[0];
      if (!near) continue;
      const far = side < 0
        ? mates.filter((b) => b !== near && b[hi] <= near[lo]).sort((a, b) => b[hi] - a[hi])[0]
        : mates.filter((b) => b !== near && b[lo] >= near[hi]).sort((a, b) => a[lo] - b[lo])[0];
      if (!far) continue;
      const gap = side < 0 ? near[lo] - far[hi] : far[lo] - near[hi];
      const mine = side < 0 ? dLo - near[hi] : near[lo] - dHi;
      if (gap < 0 || mine < 0 || Math.abs(mine - gap) > tol) continue;
      const delta = side < 0 ? gap - mine : mine - gap;
      if (best && Math.abs(delta) >= Math.abs(best.delta)) continue;
      const at = cross(near);
      best = {
        delta,
        lines: side < 0
          ? [mark(far[hi], near[lo], at), mark(near[hi], dLo + delta, at)]
          : [mark(dHi + delta, near[lo], at), mark(near[hi], far[lo], at)],
      };
    }
    return best;
  }

  //: **Guides for an edge being dragged** (INBOX 825 item 2, INBOX 826's E4):
  //: a resize, and a shape or box drawn out, snap the moving edge to another
  //: item's edge or centre and the moving size to a neighbour's width or
  //: height, each shown by a guide line; then the grid when snap is on, and a
  //: card's content height (`fit`) for its bottom edge. `box` is {x, y, w, h},
  //: `edges` the moving sides ("se", "w"). Pure apart from `wbGuideBoxes`
  //: (node-tested in tests/test_wb_resize_guides.py).
  function wbResizeGuides(excludeKeys, box, edges, { fit = null, grid = 0, min = 1, tol = WB_ALIGN_SNAP_PX } = {}) {
    const others = wbGuideBoxes(excludeKeys, box);
    const out = { x: box.x, y: box.y, w: box.w, h: box.h, guideLines: [] };
    const axis = (horizontal) => {
      const hi = horizontal ? edges.includes("e") : edges.includes("s");
      const lo = horizontal ? edges.includes("w") : edges.includes("n");
      if (!hi && !lo) return;
      const start = horizontal ? box.x : box.y, size = horizontal ? box.w : box.h;
      const fixed = hi ? start : start + size;
      const moving = hi ? start + size : start;
      const [minK, maxK, cMin, cMax] = horizontal ? ["minX", "maxX", "minY", "maxY"] : ["minY", "maxY", "minX", "maxX"];
      const crossLo = horizontal ? box.y : box.x, crossHi = crossLo + (horizontal ? box.h : box.w);
      let best = null;
      const offer = (target, line) => {
        const delta = target - moving;
        if (Math.abs(delta) > tol || (best && Math.abs(delta) >= Math.abs(best.delta))) return;
        if (Math.abs(target - fixed) < min) return;
        best = { delta, target, line };
      };
      const across = (at, a, b, kind) => (horizontal
        ? { x1: at, y1: a, x2: at, y2: b, kind }
        : { x1: a, y1: at, x2: b, y2: at, kind });
      for (const other of others) {
        const a = Math.min(crossLo, other[cMin]) - 20, b = Math.max(crossHi, other[cMax]) + 20;
        offer(other[minK], across(other[minK], a, b, "edge"));
        offer(other[maxK], across(other[maxK], a, b, "edge"));
        if (other.only) continue; // a frame's margin line: an edge to land on, not a centre or a size
        offer((other[minK] + other[maxK]) / 2, across((other[minK] + other[maxK]) / 2, a, b, "center"));
        const span = other[maxK] - other[minK];
        offer(hi ? fixed + span : fixed - span, [
          { mark: true, at: other[cMin] - 8, from: other[minK], to: other[maxK] },
        ]);
      }
      if (fit && !horizontal && hi) offer(fixed + fit, across(fixed + fit, crossLo - 20, crossHi + 20, "edge"));
      if (!best && grid) {
        const target = Math.round(moving / grid) * grid;
        if (Math.abs(target - fixed) >= min) best = { delta: target - moving, target, line: null };
      }
      if (!best) return;
      const lowEdge = hi ? fixed : best.target, highEdge = hi ? best.target : fixed;
      if (horizontal) { out.x = lowEdge; out.w = highEdge - lowEdge; } else { out.y = lowEdge; out.h = highEdge - lowEdge; }
      //: A size match marks both measures: the neighbour's and the one it set.
      if (Array.isArray(best.line)) {
        const m = best.line[0];
        const mark = (at, from, to, extra) => ({
          ...(horizontal ? { x1: from, y1: at, x2: to, y2: at } : { x1: at, y1: from, x2: at, y2: to }),
          kind: "spacing", ...extra,
        });
        //: Only the item being resized wears the number, and it stands clear of
        //: the grips on its edge (K19); the neighbour's measure is a bare line.
        out.guideLines.push(mark(m.at, m.from, m.to, { label: false }), mark(crossLo - 8, lowEdge, highEdge, { out: true }));
      } else if (best.line) out.guideLines.push(best.line);
    };
    axis(true);
    axis(false);
    return out;
  }

  //: The size beside what is being drawn or resized ("120 x 80", E4), in the
  //: guides' own group so it goes when they do; a constant screen size.
  function wbShowSizeReadout(box) {
    const group = wbAlignGuideGroup(false);
    const container = wbInstances.container();
    if (!group || !container) return;
    const k = d3.zoomTransform(container).k || 1;
    const words = `${Math.round(box.w)} x ${Math.round(box.h)}`;
    const ns = "http://www.w3.org/2000/svg";
    const g = document.createElementNS(ns, "g");
    g.setAttribute("class", "wb-size-readout");
    g.setAttribute("transform", `translate(${box.x + box.w / 2} ${box.y + box.h}) scale(${1 / k}) translate(0 16)`);
    const width = words.length * 7 + 12;
    const plate = document.createElementNS(ns, "rect");
    plate.setAttribute("x", String(-width / 2));
    plate.setAttribute("y", "-10");
    plate.setAttribute("width", String(width));
    plate.setAttribute("height", "20");
    plate.setAttribute("rx", "4");
    const text = document.createElementNS(ns, "text");
    text.setAttribute("text-anchor", "middle");
    text.setAttribute("dominant-baseline", "central");
    text.textContent = words;
    g.append(plate, text);
    group.appendChild(g);
    wbMeasuring(true);
  }

  //: While a size or gap badge shows, the arrow grips and the turn handle hide:
  //: they sit on the same spots (22 px out, mid-side) and covered the numbers
  //: (the owner 2026-10-26: "sizes still get cut off"). Neither works mid-drag.
  function wbMeasuring(on) {
    wbInstances.container()?.classList.toggle("wb-measuring", on);
  }

  //: One resize frame through the guides: the box the handle has made, snapped
  //: (unless `off`), the lines and the size drawn. Returns the new width and
  //: height; the caller places x and y from them as before.
  function wbGuidedResize(kind, d, handle, start, width, height, { off = false, fit = null } = {}) {
    const box = {
      x: handle.includes("w") ? start.x + start.w - width : start.x,
      y: handle.includes("n") ? start.y + start.h - height : start.y,
      w: width,
      h: height,
    };
    const snapped = off ? { ...box, guideLines: [] } : wbResizeGuides(new Set([wbMultiKey(kind, d.id)]), box, handle, {
      fit, grid: wbSnapOn() ? WB_GRID_SPACING : 0, min: WB_OBJECT_MIN_SIZE, tol: wbAlignTol(),
    });
    wbShowAlignmentGuides(snapped.guideLines);
    wbShowSizeReadout(snapped);
    return { width: snapped.w, height: snapped.h };
  }

  //: **A box drawn out from a press snaps its moving corner** (E4): the
  //: corner under the pointer goes through the edge guides, and the size shows
  //: beside it. Every closed shape is drawn corner to corner, the ellipse
  //: included (dogfood 2026-10-25 item 7: a circle grown from its centre
  //: put its top under the toolbar and felt unlike the rectangle). Alt draws
  //: from the centre without snapping (`wbDragBox`); Shift (a square) is left
  //: alone.
  function wbDrawOutSnap(sx, sy, x, y, event) {
    const dx = x - sx, dy = y - sy;
    const box = { x: Math.min(sx, x), y: Math.min(sy, y), w: Math.abs(dx), h: Math.abs(dy) };
    if (event.shiftKey || event.altKey) {
      //: Shift (a square) and Alt (from the centre, unsnapped) are left to
      //: `wbDragBox`; the readout shows the box it will draw.
      wbShowAlignmentGuides([]);
      wbShowSizeReadout(wbDragBox(sx, sy, x, y, event));
      return [x, y];
    }
    const edges = (dx >= 0 ? "e" : "w") + (dy >= 0 ? "s" : "n");
    const snapped = wbResizeGuides(null, box, edges, {
      grid: wbSnapOn() ? WB_GRID_SPACING : 0, min: 1, tol: wbAlignTol(),
    });
    wbShowAlignmentGuides(snapped.guideLines);
    wbShowSizeReadout(snapped);
    return [edges.includes("e") ? snapped.x + snapped.w : snapped.x, edges.includes("s") ? snapped.y + snapped.h : snapped.y];
  }

  //: Default guide colours, one per `kind` `wbAlignmentGuides` can report: 
  //: "edge" (an outer border lining up with another), "center" (mid-points
  //: lining up, the draw.io/PowerPoint convention of a *different* colour so
  //: the two are never confused at a glance), and "spacing" (equal gaps).
  //: Overridable per the direct ask ("colours should be alterable"); the
  //: picker lives in the whiteboard's own shape-menu dropdown rather than a
  //: new top menu bar, see HISTORY.md for why that redesign was not taken.
  //: The defaults live in CSS (`.wb-align-guide-<kind>`, one ink per theme, so
  //: each passes 3:1 on the canvas in light and dark); only a colour the owner
  //: picked is written here, and it wins over the class.
  function wbAlignGuideColor(kind) {
    return prefs.get(`wb-guide-color-${kind}`, null) || "";
  }
  //: The active board's own guides group, found in its overlay layer and marked by a class, not a document id: an embed's
  //: guides and the page board's are two groups (L-whiteboard-73). `make` draws one when there is none.
  function wbAlignGuideGroup(make) {
    const zoomGroup = wbInstances.layer("wb-overlay-zoom-group") || wbInstances.layer("wb-zoom-group");
    if (!zoomGroup) return null;
    let group = zoomGroup.querySelector(":scope > .wb-align-guides");
    if (!group && make) {
      group = document.createElementNS("http://www.w3.org/2000/svg", "g");
      group.setAttribute("class", "wb-align-guides");
      group.setAttribute("pointer-events", "none");
      zoomGroup.appendChild(group);
    }
    return group;
  }
  function wbShowAlignmentGuides(lines) {
    //: The overlay layer, above the cards in DOM order: in `#wb-zoom-group` (the base SVG) a guide ran
    //: under every note card it lined up with (owner, 2026-11-10, INBOX 1725). Same pan and zoom.
    const zoomGroup = wbInstances.layer("wb-overlay-zoom-group") || wbInstances.layer("wb-zoom-group");
    if (!zoomGroup) return;
    const group = wbAlignGuideGroup(true);
    group.replaceChildren();
    wbMeasuring(false);
    if (!lines.length) return;
    const ns = "http://www.w3.org/2000/svg";
    const container = wbInstances.container();
    const k = (container && d3.zoomTransform(container).k) || 1;
    for (const line of lines) {
      const kind = line.kind || "edge";
      const el = document.createElementNS(ns, "line");
      el.setAttribute("x1", line.x1);
      el.setAttribute("y1", line.y1);
      el.setAttribute("x2", line.x2);
      el.setAttribute("y2", line.y2);
      el.setAttribute("class", `wb-align-guide-line wb-align-guide-${kind}`);
      const picked = wbAlignGuideColor(kind);
      if (picked) el.style.stroke = picked;
      group.appendChild(el);
      if (kind !== "spacing" || line.label === false) continue;
      const length = Math.round(Math.hypot(line.x2 - line.x1, line.y2 - line.y1));
      if (length * k < 22) continue; // a label wider than its gap is noise
      const label = document.createElementNS(ns, "g");
      label.setAttribute("class", "wb-align-guide-label");
      //: A badge on the edge being dragged sits over that edge's own grip (the
      //: "34" under the left handle, K19): it steps off the line, away from the box.
      const clear = line.out ? WB_BADGE_CLEAR_PX / k : 0;
      const bx = (line.x1 + line.x2) / 2 - (line.x1 === line.x2 ? clear : 0);
      const by = (line.y1 + line.y2) / 2 - (line.y1 === line.y2 ? clear : 0);
      label.setAttribute("transform", `translate(${bx} ${by}) scale(${1 / k})`);
      const words = String(length);
      const width = words.length * 7 + 10;
      const plate = document.createElementNS(ns, "rect");
      plate.setAttribute("x", String(-width / 2));
      plate.setAttribute("y", "-9");
      plate.setAttribute("width", String(width));
      plate.setAttribute("height", "18");
      plate.setAttribute("rx", "4");
      if (picked) plate.style.fill = picked;
      const text = document.createElementNS(ns, "text");
      text.setAttribute("text-anchor", "middle");
      text.setAttribute("dominant-baseline", "central");
      text.textContent = words;
      label.append(plate, text);
      group.appendChild(label);
      wbMeasuring(true);
    }
  }

  function wbClearAlignmentGuides() {
    wbAlignGuideGroup(false)?.remove();
    wbMeasuring(false);
  }

  function wbApplyGrid() {
    const el = wbInstances.container();
    if (!el) return;
    el.dataset.wbGrid = wbGridType();
    wbSyncGridToTransform();
  }

  //: **A board's look lives on the board** (WHITEBOARD_PLAN decision 24,
  //: FEAT-06). It used to be one localStorage colour shared by every board and
  //: a per-board localStorage image, so neither synced, neither was in a
  //: backup, the desktop window and a browser tab drew different boards, and
  //: media cleanup deleted the image as an orphan. Now `background {color,
//: image}` is in the board's settings and arrives with its state
  //: (`wbState.background`); grid and snap stay per device.
  function wbBoardBackground() {
    return (wbState && wbState.background) || {};
  }

  //: The file's surface: what other files call (L634).
  Object.assign(window, { wbBulkGroupBox, wbDragExcludeKeys, wbAlignmentGuides, wbShowSizeReadout, wbGuidedResize, wbDrawOutSnap, wbAlignGuideColor, wbShowAlignmentGuides, wbClearAlignmentGuides, wbApplyGrid, wbBoardBackground });
})();
