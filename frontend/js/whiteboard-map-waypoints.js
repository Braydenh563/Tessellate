(() => {
  // whiteboard-map-waypoints.js: map line waypoints, cross-link handles and their menus.
  // Moved out of whiteboard-map.js whole (L286) and wrapped: only what other files call goes on `window`; nothing here runs at load.
  //: Dragging one waypoint handle (§12.1 item 5's third).
  //:
  //: In client pixels over the zoom scale, the same conversion
  //: `wbMapStartResizeDrag` makes and for the same reason: the pointer's own
  //: delta is the only measurement that does not need the canvas transform
  //: rebuilt per frame, and the waypoint it starts from is already in board
  //: units. Per frame it redraws this one edge (`wbUpdateMapEdges`, which moves
  //: the visible path, the hit twin and the handle together) rather than the
  //: board; the write lands once, on the drop.
  function wbWireMapEdgeHandle(handle, parentId, childId) {
    handle.addEventListener("pointerdown", (event) => {
      //: No `is-shown` check here, deliberately: the stylesheet is the one gate,
      //: and it has two ways of opening (hover on the line, or the topic at
      //: either end selected). A class test would have refused the hover route
      //: silently, which is the half that works when the strip is in the way.
      //: An unshown handle is `pointer-events: none` and so is never the target
      //: of this event in the first place.
      event.preventDefault();
      event.stopPropagation();
      const index = wbMapIndex();
      const parent = index.byId.get(parentId);
      const child = index.byId.get(childId);
      if (!parent || !child) return;
      const layout = wbMapLayout();
      const container = document.getElementById("whiteboard-container");
      const k = container ? d3.zoomTransform(container).k : 1;
      const start = wbMapEdgeWaypoint(wbMapEdgeAnchors(parent, child, layout), child);
      const edges = wbMapEdgesFor(childId).filter((edge) => edge.parent.id === parentId);
      const before = {
        edge_bend: child.data?.edge_bend ?? null,
        edge_slide: child.data?.edge_slide ?? null,
      };
      let next = null;
      //: Held open for the length of the drag. The pointer leaves the line the
      //: instant the bend starts, which ends the `:hover` that revealed the
      //: handle: pointer capture should carry the moves anyway, but a control
      //: that depends on capture outliving `pointer-events: none` is a control
      //: that depends on a detail of one engine.
      handle.classList.add("is-dragging");
      handle.setPointerCapture?.(event.pointerId);
      const move = (moveEvent) => {
        const x = start.x + (moveEvent.clientX - event.clientX) / k;
        const y = start.y + (moveEvent.clientY - event.clientY) / k;
        next = wbMapEdgeFractions(wbMapEdgeAnchors(parent, child, layout), x, y);
        child.data = { ...child.data, ...next };
        wbUpdateMapEdges(edges);
      };
      const done = async () => {
        handle.removeEventListener("pointermove", move);
        handle.removeEventListener("pointerup", done);
        handle.removeEventListener("pointercancel", done);
        handle.classList.remove("is-dragging");
        if (!next) return;
        //: Zero is stored as nothing at all, like every other default this map
        //: writes: a line dragged back to straight and a line nobody has
        //: touched are the same line, and neither should carry a field into an
        //: export.
        const patch = {
          edge_bend: next.edge_bend || null,
          edge_slide: next.edge_slide || null,
        };
        if (patch.edge_bend === before.edge_bend && patch.edge_slide === before.edge_slide) return;
        //: Back to the line as it was before the save: the drag wrote each
        //: frame's bend into `child.data`, so `wbMapSetNodeStyle`'s undo
        //: snapshot read the new curve as the old one, and Ctrl+Z put back the
        //: same curve (INBOX 658, the owner: "I modified dragged the curve of a
        //: mindmap link and I couldnt ctrl z undo it").
        child.data = { ...child.data, ...before };
        await wbMapSetNodeStyle(child, patch);
        renderWhiteboardNow();
      };
      handle.addEventListener("pointermove", move);
      handle.addEventListener("pointerup", done);
      handle.addEventListener("pointercancel", done);
    });
    //: Back to the line it was, without going to a menu for it. The same
    //: gesture a text grip uses to reset a size elsewhere in this file, and the
    //: node's own menu says so in words for anyone who does not try it.
    //: A click on the dot must not reach the canvas: it cleared the selection,
    //: which stood the mid-line `+` back over the dot (zoomed out it covers
    //: it), so the second click of a double-click hit the `+` (L-mindmap-15).
    handle.addEventListener("click", (event) => event.stopPropagation());
    handle.addEventListener("dblclick", (event) => {
      event.preventDefault();
      event.stopPropagation();
      const child = wbMapIndex().byId.get(childId);
      if (child) wbMapStraightenEdge(child);
    });
  }

  //: Drop a line's waypoint. Named rather than inlined because two surfaces ask
  //: for it (the handle's own double-click and the topic's menu) and §12.5's
  //: rule is one action in one place.
  async function wbMapStraightenEdge(node) {
    if (!node) return;
    if (!node.data?.edge_bend && !node.data?.edge_slide) return;
    await wbMapSetNodeStyle(node, { edge_bend: null, edge_slide: null });
    renderWhiteboardNow();
  }

  //: Where a line's two end grips sit: a step out from each end along its
  //: side's normal, so the grip is clear of the topic and of the buttons a
  //: selected topic wears beside it (its add rail reaches 35 units out, its
  //: fold chevron 15; both are HTML above the line layer and took the press
  //: at 12). A third of the line at most, so the two grips never cross.
  const WB_MAP_END_OUT = 42;

  function wbMapEdgeEndPoints(parent, child, layout) {
    const a = wbMapEdgeAnchors(parent, child, layout);
    const s1 = a.s1 || wbMapFacingSide(parent, wbMapNodeSize(parent), a.x1, a.y1);
    const s2 = a.s2 || wbMapFacingSide(child, wbMapNodeSize(child), a.x2, a.y2);
    const step = Math.min(WB_MAP_END_OUT, Math.hypot(a.x2 - a.x1, a.y2 - a.y1) / 3);
    const out = (x, y, side) => {
      const [, , ux, uy] = WB_MAP_SIDES[side];
      return { x: x + ux * step, y: y + uy * step };
    };
    return { from: out(a.x1, a.y1, s1), to: out(a.x2, a.y2, s2) };
  }

  function wbMapPlaceEdgeEnds(path, ends) {
    const [from, to] = path._wbEnds || [];
    if (!from || !to || !ends) return;
    from.setAttribute("cx", String(ends.from.x));
    from.setAttribute("cy", String(ends.from.y));
    to.setAttribute("cx", String(ends.to.x));
    to.setAttribute("cy", String(ends.to.y));
  }

  //: Dragging one end grip round its topic (K31). The side is the one the
  //: pointer faces from the topic's centre, so the end snaps from side to side
  //: as the hand goes round; per frame only this line is redrawn, from the
  //: cached box sizes (no layout read), and the write lands once, on the drop,
  //: as one Undo step through `wbMapSetNodeStyle`.
  function wbWireMapEdgeEnd(grip, parentId, childId, end) {
    const field = end === "from" ? "edge_from" : "edge_to";
    grip.addEventListener("pointerdown", (event) => {
      if (event.button !== 0) return;
      event.preventDefault();
      event.stopPropagation();
      const index = wbMapIndex();
      const parent = index.byId.get(parentId);
      const child = index.byId.get(childId);
      if (!parent || !child) return;
      const node = end === "from" ? parent : child;
      const size = wbMapNodeSize(node);
      const container = document.getElementById("whiteboard-container");
      const k = container ? d3.zoomTransform(container).k : 1;
      const startX = Number(grip.getAttribute("cx"));
      const startY = Number(grip.getAttribute("cy"));
      const edges = wbMapEdgesFor(childId).filter((edge) => edge.parent.id === parentId);
      const before = child.data?.[field] ?? null;
      let side = null;
      grip.classList.add("is-dragging");
      grip.setPointerCapture?.(event.pointerId);
      const move = (moveEvent) => {
        const x = startX + (moveEvent.clientX - event.clientX) / k;
        const y = startY + (moveEvent.clientY - event.clientY) / k;
        const next = wbMapFacingSide(node, size, x, y);
        if (next === side) return;
        side = next;
        child.data = { ...child.data, [field]: side };
        wbUpdateMapEdges(edges);
      };
      const done = async () => {
        grip.removeEventListener("pointermove", move);
        grip.removeEventListener("pointerup", done);
        grip.removeEventListener("pointercancel", done);
        grip.classList.remove("is-dragging");
        if (!side) return;
        //: Back to what it was before the save, so the undo snapshot holds the
        //: old side (the waypoint drag's own INBOX 658 lesson).
        child.data = { ...child.data, [field]: before };
        if (side !== before) await wbMapSetNodeStyle(child, { [field]: side });
        renderWhiteboardNow();
      };
      grip.addEventListener("pointermove", move);
      grip.addEventListener("pointerup", done);
      grip.addEventListener("pointercancel", done);
    });
    //: A press on a grip is not a click on the canvas: without this the
    //: canvas took it as one and dropped the selection the grip was shown for.
    grip.addEventListener("click", (event) => event.stopPropagation());
    grip.addEventListener("dblclick", async (event) => {
      event.preventDefault();
      event.stopPropagation();
      const child = wbMapIndex().byId.get(childId);
      if (!child?.data?.[field]) return;
      await wbMapSetNodeStyle(child, { [field]: null });
      renderWhiteboardNow();
    });
  }

  //: Both ends of the line into a topic back on Auto: the topic menu's row.
  async function wbMapAutoEdgeEnds(node) {
    if (!node || (!node.data?.edge_from && !node.data?.edge_to)) return;
    await wbMapSetNodeStyle(node, { edge_from: null, edge_to: null });
    renderWhiteboardNow();
  }

  //: The gestures on one edge, bound to the group that holds its stroke, its
  //: target twin and its waypoint handle, so all three answer them. Bound at
  //: creation rather than delegated: the edge group is replaced wholesale on
  //: every render (`wbRenderMapEdges`'s own comment says why), so there is
  //: exactly one binding per element per lifetime and nothing to clean up.
  //:
  //: The handle stops its own `pointerdown`, so a hold that starts on the
  //: handle is a drag and not a ring; a hold anywhere else on the line is a
  //: ring, which is what it has always been.
  function wbWireMapEdgeGestures(hit, childId) {
    hit.addEventListener("contextmenu", (event) => {
      event.preventDefault();
      event.stopPropagation();
      wbOpenMapLinkRadial(childId, event.clientX, event.clientY);
    });
    //: Touch has no right-click, so a hold stands in: `wireLongPress` (navigation.js),
    //: which is the same 500ms and the same cancel-on-move this used to write
    //: for itself, plus the one thing the hand-rolled version could not do,
    //: swallowing the click the lift synthesises.
    wireLongPress(hit, (event, point) => wbOpenMapLinkRadial(childId, point.x, point.y));
    //: **Double-click a line to say what it means** (the conventions pass:
    //: Miro, tldraw and XMind all label a connector this way). The label
    //: itself already answered a double-click; a line with no label yet had
    //: only the ring's middle slot, and a double-click on it made a new trunk
    //: on top of it. The bend grip is part of this group and keeps its own
    //: double-click (straighten), which stops here first.
    hit.addEventListener("dblclick", (event) => {
      if (event.target.closest?.(".wb-map-edge-handle, .wb-map-edge-label")) return;
      event.preventDefault();
      event.stopPropagation();
      wbMapLabelEdge(childId);
    });
  }

  function wbOpenMapLinkRadial(childId, clientX, clientY) {
    const ring = document.getElementById("wb-map-link-radial");
    const host = document.getElementById("library-view-whiteboard");
    const index = wbMapIndex();
    const child = index.byId.get(childId);
    if (!ring || !host || !child) return;
    wbCloseContextMenu();
    wbCloseMapRadial();
    // At the pointer, not at the line's middle: a branch edge can be hundreds of
    // pixels long and a ring that jumped to its midpoint would open somewhere
    // you were not looking.
    const hostRect = host.getBoundingClientRect();
    wbMapLinkRadialFor = childId;
    wbMapLinkRadialCross = null;
    wbPlaceMapRadial(ring, host, clientX - hostRect.left, clientY - hostRect.top);
    wbSyncMapLinkRadial(child, index);
  }

  //: The same ring on a cross-link. Returns whether it took the gesture, so the
  //: one door every right-click and hold goes through (`wbOpenContextMenuFor`)
  //: can fall back to the board's flat menu for a link that is not one.
  function wbOpenMapCrossLinkRadial(sketchId, clientX, clientY) {
    const info = wbMapCrossLinkInfo(sketchId);
    const ring = document.getElementById("wb-map-link-radial");
    const host = document.getElementById("library-view-whiteboard");
    if (!info || !ring || !host) return false;
    wbCloseContextMenu();
    wbCloseMapRadial();
    const hostRect = host.getBoundingClientRect();
    wbMapLinkRadialFor = null;
    wbMapLinkRadialCross = sketchId;
    wbPlaceMapRadial(ring, host, clientX - hostRect.left, clientY - hostRect.top);
    wbSyncMapLinkRadial(null, info.index);
    return true;
  }

  //: **The ring says which of the two lines it is on, in words** (§13c). The
  //: three slots are the same three either way, and two of them mean something
  //: different on each: Cut takes a branch off its parent and deletes a
  //: cross-link outright, and the middle slot labels a branch and turns a
  //: cross-link into one. Saying so on the slot, rather than relying on the
  //: person having noticed which line they right-clicked, is the whole point of
  //: this pass: §13.2 found that nothing on screen said which kind was which.
  function wbSyncMapLinkRadial(child, index) {
    const reverse = document.getElementById("wb-link-reverse");
    const middle = document.getElementById("wb-link-label");
    const cut = document.getElementById("wb-link-cut");
    const ring = document.getElementById("wb-map-link-radial");
    const cross = wbMapLinkRadialCross != null;
    const setSlot = (el, word, title, icon) => {
      if (!el) return;
      el.querySelector(".wb-map-radial-name").textContent = word;
      el.title = title;
      el.setAttribute("aria-label", title);
      const glyph = el.querySelector("i");
      if (glyph) glyph.className = icon;
    };
    if (ring) {
      ring.setAttribute("aria-label", cross ? "What you can do with this cross-link" : "What you can do with this branch");
      const caption = ring.querySelector(".wb-map-radial-caption");
      if (caption) {
        caption.dataset.rest = cross
          ? "A cross-link: it joins two branches without changing the tree"
          : "A branch: the line the tree itself is made of";
        //: The drawn text as well as the attribute: `data-rest` is what the
        //: caption goes back to when the pointer leaves a slot, and the ring was
        //: already placed (and the caption already painted from the old value)
        //: by the time this runs.
        caption.textContent = caption.dataset.rest;
      }
    }
    if (cross) {
      setSlot(reverse, "Reverse", "Turn this cross-link around: it points the other way", "ph ph-swap");
      setSlot(middle, "Make branch", "Make this a branch instead: the topic at the far end moves under this one", "ph ph-tree-structure");
      setSlot(cut, "Cut", "Cut this cross-link: the two topics keep their own branches", "ph ph-scissors");
      if (reverse) reverse.disabled = false;
      return;
    }
    setSlot(reverse, "Reverse", "Turn the branch around: the topic below becomes the one above", "ph ph-swap");
    setSlot(middle, "Label", "Label this branch", "ph ph-tag");
    setSlot(cut, "Cut", "Cut this branch: the topic below becomes a trunk of its own", "ph ph-scissors");
    if (reverse && child) {
      // Turning a line around makes the parent a child of the child. If the
      // parent is a trunk that is a clean swap; it is never possible for a line
      // that is not there, which is the only case worth refusing.
      const parent = index.byId.get(child.parent_id);
      reverse.disabled = !parent;
    }
  }

  //: The file's surface: what other files call (L286).
  Object.assign(window, { wbWireMapEdgeHandle, wbMapStraightenEdge, wbMapEdgeEndPoints, wbMapPlaceEdgeEnds, wbWireMapEdgeEnd, wbMapAutoEdgeEnds, wbWireMapEdgeGestures, wbOpenMapLinkRadial, wbOpenMapCrossLinkRadial });
})();
