(() => {
  // whiteboard-drag.js: the link index (which connectors follow which item) and dragging a card or object (moved out of whiteboard.js, L634).
  // Wrapped: only what other files call goes on `window`; nothing here runs at load.

  //: Everything `renderWbObjects` reads when it paints one object, as one
  //: string (MINDMAP_PLAN.md §13a). Two renders with the same key for an object
  //: would write the same pixels, so the second one skips it.
  //:
  //: **The map fields are the ones that are not on the object.** A topic's
  //: colour comes from its branch, its chevron from how many children it has,
  //: its badge from how many topics are folded under it, its spine from which
  //: side its parent is on, and everything the strip sets comes from the node's
  //: data with the map's theme merged underneath: all five change without the
  //: row itself changing, so all five are in the key.
  //:
  //: `height` is deliberately left out for a map node, because a map node's
  //: height is its text's: the measure pass at the end of `renderWbObjects`
  //: writes what was drawn back onto the datum, so including it would make
  //: every node's key differ from its own last render, for ever. The one
  //: exception is a topic somebody has resized by hand (`sized`), whose stored
  //: height is written back as a `min-height` and therefore is an input.
  function wbObjectPaintKey(d, ctx) {
    //: No x or y: a position is applied as a transform without a repaint (the
    //: update pass above). The one paint that reads a topic's own x is the
    //: both-sides spine, added below with its parent's.
    const base = `${d.kind}|${d.z}|${d.width}|${d.rotation ?? ""}|${JSON.stringify(d.data ?? null)}`;
    //: The board's sticky-fold default is read by the paint (`wbStickyFolds`).
    if (!WB_MAP_KINDS.has(d.kind)) return `${base}|${d.height}|${ctx.fold}`;
    const index = ctx.index;
    const children = index?.childrenOf.get(d.id)?.length || 0;
    const buried = d.data?.collapsed && index ? wbMapSubtree(index, d.id).length - 1 : 0;
    //: Only where it is read: `wb-map-node-mirrored` is decided from the
    //: parent's own box on a both-sides map, and on every other layout the
    //: side is the layout's, so a parent moving cannot change a child's spine.
    let parentBox = "";
    //: A branch with its own structure draws its topics by that layout (`_bl`).
    if ((d._bl || ctx.layout) === "tree-both" && index) {
      const parent = index.byId.get(d.parent_id);
      if (parent) parentBox = `${parent.x}:${parent.width ?? ""}:${d.x}`;
    }
    return `${base}|${d.data?.sized ? d.height : ""}|${wbMapLabel(d)}|${ctx.colors?.get(d.id) || ""}` +
      `|${children}|${buried}|${d.parent_id ?? ""}|${parentBox}|${ctx.layout}|${d._bl || ""}|${ctx.theme}` +
      `|${ctx.fills?.get(d.id) ?? ""}|${wbMapLevelOf(d) ?? ""}` +
      //: The tasks under it (MINDMAP_PLAN.md decision 15): a child ticked
      //: changes this topic's "1/2" without changing anything of its own.
      `|${(() => { const t = index ? wbMapTaskTally(index).get(d.id) : null; return t ? `${t.done}/${t.total}` : ""; })()}` +
      //: Its number (decision 17): a sibling added above it renumbers it.
      `|${wbMapNumberOf(index, d.id)}`;
  }

  //: **Every link sketch on the board, parsed once and filed under both of its
  //: ends** (MINDMAP_PLAN.md §13a). Built by whoever is about to ask about more
  //: than one item, which is `wbCaptureBulkMoveOrigin`: it is handed the whole
  //: branch under a dragged topic, and the alternative is `wbLinkedSketchesFor`
  //: walking and re-parsing every sketch on the board once per member.
  //:
  //: Keyed `kind:id`, the same pair `wbLinkedSketchesFor` matches on. The keys
  //: are strings, so a link whose stored id is `"12"` rather than `12` now finds
  //: its node where the scan's `===` did not: nothing in this app writes one,
  //: since both come from the same rows, and a link that cannot find its end is
  //: a line left behind by a drag either way.
  //:
  //: A sketch with both ends on one item is filed once, which is what the scan's
  //: `atSource || atTarget` did.
  function wbLinkSketchIndex() {
    const byEnd = new Map();
    for (const sketch of wbState.sketches || []) {
      const parsed = wbParsedLink(sketch);
      if (!parsed) continue;
      const pair = { sketch, parsed };
      const source = `${parsed.sourceKind || "node"}:${parsed.sourceId}`;
      const target = `${parsed.targetKind || "node"}:${parsed.targetId}`;
      for (const end of target === source ? [source] : [source, target]) {
        const list = byEnd.get(end);
        if (list) list.push(pair);
        else byEnd.set(end, [pair]);
      }
    }
    return byEnd;
  }

  function wbParsedLink(sketch) {
    const hit = wbLinkParseCache.get(sketch.id);
    if (hit && hit.data === sketch.data) return hit.link;
    let link = null;
    try {
      const parsed = JSON.parse(sketch.data);
      if (parsed && typeof parsed.type === "string" && parsed.type.startsWith("link-")) link = parsed;
    } catch {
      link = null;
    }
    wbLinkParseCache.set(sketch.id, { data: sketch.data, link });
    return link;
  }

  //: The sketches touching `nodeId`, pre-parsed once. `wbUpdateLinkedSketches`
  //: used to do this same JSON.parse-and-scan of *every* sketch on the board on
  //: every single mousemove frame of a card drag, a board with a few hundred
  //: sketches (strokes plus link lines) turns a drag into dozens of full-board
  //: parses a second, visible as stutter on a busy board. `dragStart` below
  //: builds this list once per drag instead; a card gains or loses a link only
  //: between drags, never mid-drag, so it doesn't need to be live.
  function wbLinkedSketchesFor(nodeId, kind = "node", index = null) {
    //: **One parse of the board, not one parse per item asking**
    //: (MINDMAP_PLAN.md §13a). Given an index (see `wbLinkSketchIndex`), this
    //: is a lookup. Without one it is the scan below, which is right for the
    //: single item a solo drag picks up and quadratic for a bulk move, which
    //: hands this every topic under the one grabbed: a branch of two hundred
    //: topics over a board of a few hundred link sketches was two hundred full
    //: scans with a `JSON.parse` in each of them, before the pointer had moved.
    if (index) return index.get(`${kind}:${nodeId}`) || [];
    const found = [];
    for (const sketch of wbState.sketches) {
      const parsed = wbParsedLink(sketch);
      if (!parsed) continue;
      const atSource = parsed.sourceId === nodeId && (parsed.sourceKind || "node") === kind;
      const atTarget = parsed.targetId === nodeId && (parsed.targetKind || "node") === kind;
      if (!atSource && !atTarget) continue;
      found.push({ sketch, parsed });
    }
    return found;
  }

  //: Recomputes just the link-sketch paths touching `nodeId`, without a full
  //: `wbScheduleRender()`, reported directly as "resizing and drawing shapes
  //: is glitchy and slow to update". `dragging` below used to call the full
  //: render on every single mousemove frame of a card drag, purely to keep a
  //: link line's endpoint following the card, which re-binds *every* card,
  //: sketch and object on the board, dozens of times a second, for one card's
  //: own link. Mirrors the link-path maths in `renderWhiteboard`'s own
  //: `sketchUpdate.each` exactly, so the two can't drift apart.
  //: `precomputed`, when given, skips the board-wide scan, see
  //: `wbLinkedSketchesFor`'s own comment for why `dragging` always passes one.
  function wbUpdateLinkedSketches(nodeId, precomputed) {
    const pairs = precomputed || wbLinkedSketchesFor(nodeId);
    for (const entry of pairs) {
      const { sketch, parsed } = entry;
      const look = wbMapCrossLinkLook(parsed);
      const endpoints = look ? null : wbResolveLinkEndpoints(parsed);
      if (!look && !endpoints) continue;
      const plainD = look
        ? look.d
        : wbLinkPathD(parsed.type, endpoints.source, endpoints.target, wbLinkCaps(parsed), parsed.width, parsed.bend, wbLinkShape(parsed));
      //: A connector shape follows the drag as its outline (the plain line stays the hit band).
      const shaped = !look && parsed.shape ? wbFmtState.shapeMore?.shapedLink(parsed, endpoints) : null;
      const pathData = shaped ? shaped.d : plainD;
      //: **The two paths, found once per gesture rather than once per frame**
      //: (MINDMAP_PLAN.md §13a). Three document-wide queries per link per frame
      //: is thousands of walks of the document a second on a board that mixes a
      //: branch with a few hundred links, for elements that a render keyed by
      //: id does not replace. `isConnected` is the revalidation, the same shape
      //: `wbBulkMoveElement` already uses: a sketch deleted mid-gesture is gone
      //: from the document and has to be looked for again rather than written
      //: to invisibly for ever.
      if (!entry.el || !entry.el.isConnected) {
        entry.el = wbInstances.query(`.sketch-group[data-id="${sketch.id}"]`);
        entry.path = entry.el?.querySelector(".sketch-path") || null;
        entry.hitbox = entry.el?.querySelector(".sketch-hitbox") || null;
      }
      entry.path?.setAttribute("d", pathData);
      entry.hitbox?.setAttribute("d", look ? look.line : shaped ? shaped.centre : pathData);
      //: A connector's label rides on the line (decision 13), looked up once
      //: per gesture like the two paths.
      if (entry.label === undefined || (entry.label && !entry.label.isConnected)) {
        entry.label = entry.el?.querySelector(":scope > .wb-link-label") || null;
      }
      if (entry.label) wbLayoutLinkLabel(entry.el);
      wbFmtState.linkEdge?.follow(sketch.id, wbUpdateLinkedSketches); // the connectors that end on this one
    }
  }

  function dragStart(event, d) {
    // Eraser/delete don't move cards: a swipe meant to erase a run of cards
    // must not also drag the first one it touches out from under the pointer.
    if (window.currentTool === "eraser" || window.currentTool === "delete" || window.currentTool === "bucket") return;
    if (window.currentTool && window.currentTool.startsWith("link-")) {
      // Real anchors: snap the link's own start to whichever of the source
      // card's 8 fixed points the drag actually began near, so a link from a
      // specific corner stays pinned there through a later resize, `null`
      // (nothing near enough) is the free/floating case, resolved fresh every
      // render in `wbLinkEndpoints` instead of frozen at drag-start.
      const [startX, startY] = d3.pointer(event, wbInstances.layer("wb-zoom-group"));
      d.linkSourceAnchor = wbNearestAnchor(d._linkKind || "node", d, startX, startY);
      wbLinkDragActive = true;
      wbShowAnchorHints(d._linkKind || "node", d, d.linkSourceAnchor);
      d.linkingPath = document.createElementNS("http://www.w3.org/2000/svg", "path");
      d.linkingPath.setAttribute("fill", "none");
      d.linkingPath.setAttribute("stroke", window.currentStrokeColor || "#ffffff");
      d.linkingPath.setAttribute("stroke-width", "3");
      wbInstances.layer("wb-zoom-group").appendChild(d.linkingPath);
      //: Escape mid-draw drops the line being drawn and makes nothing.
      d._gesture = wbBeginGesture(() => {
        d.linkingPath?.remove();
        d.linkingPath = null;
        wbLinkDragActive = false;
        wbClearAnchorHints();
        wbMapClearLinkCue();
      });
    } else {
      // `.raise()` deliberately does NOT happen here, see the matching
      // comment in `dragging` below for a real bug this caused.
      // Reported directly: "hard to move notes diagonally when on grid lock".
      // `dragging` below used to re-snap the *already-snapped* `d.x`/`d.y`
      // every frame: each small per-frame delta got rounded straight back to
      // the same grid line it started from, discarding the sub-grid remainder
      // instead of carrying it forward, so many frames of real motion could
      // add up to nothing until one single frame happened to cross a whole
      // grid step by itself. A raw (never-snapped) running position, seeded
      // here and only read through `wbSnap` when applying/saving, fixes it:
      // every pixel of real cursor motion accumulates, and only the *display*
      // rounds to the grid.
      d._rawX = d.x;
      d._rawY = d.y;
      d._dragOriginX = d.x;
      d._dragOriginY = d.y;
      // See wbLinkedSketchesFor's own comment: parsed once here rather than on
      // every frame of the drag that's about to start.
      d._linkedSketches = wbLinkedSketchesFor(d.id);
      d._raised = false;
      // Asked for directly: undo should cover a move, not only create/delete.
      // Snapshotted before anything below can mutate `d`.
      d._moveUndoBefore = WB_KIND_INFO.node.payload(d);
      d._altCopy = Boolean(event.sourceEvent?.altKey);
      d._gesture = wbBeginGesture(() => wbRestoreMove("node", d), true);
      // Bulk-move detection deliberately waits for the first real
      // "drag" frame below, not decided here, see the matching comment on
      // the sketch drag's own "start" for the click-toggle bug that caused.
    }
  }

  async function dragEndNode(event, d) {
    if (window.currentTool && window.currentTool.startsWith("link-")) {
      const cancelledLink = wbEndGesture(d._gesture);
      delete d._gesture;
      // The in-flight cue goes with the gesture, released or taken back.
      wbMapClearLinkCue();
      if (cancelledLink) {
        d.linkingPath?.remove();
        d.linkingPath = null;
        d.linkSourceAnchor = null;
        return;
      }
      if (d.linkingPath) d.linkingPath.remove();
      d.linkingPath = null;
      wbLinkDragActive = false;
      wbClearAnchorHints();

      const [mx, my] = d3.pointer(event, wbInstances.layer("wb-zoom-group"));

      const sourceKind = d._linkKind || "node";
      const hit = wbLinkCandidateAt(mx, my, sourceKind, d.id);
      const targetNode = hit ? hit[1] : null;
      const targetKind = hit ? hit[0] : "node";

      if (targetNode && await wbMapJoinByLink(d, targetNode)) {
        // The map took it as a branch: see `wbMapJoinByLink`. No sketch, and
        // the transplant has already tidied, rendered and said what it did.
        d.linkSourceAnchor = null;
        return;
      }
      if (targetNode) {
         // The release point's own nearest anchor on the target, same as the
         // source got at drag-start, `null` (nothing near enough) persists
         // as a free/floating end, same as the source's own case.
         const targetAnchor = wbNearestAnchor(targetKind, targetNode, mx, my);
         const crossLink = wbIsMap() && WB_MAP_KINDS.has(d.kind) && WB_MAP_KINDS.has(targetNode.kind);
         const tool = crossLink ? wbMapCrossLinkType() : window.currentTool;
         const linkBase = {
              type: tool,
              sourceId: d.id,
              targetId: targetNode.id,
              sourceKind: sourceKind === "node" ? undefined : sourceKind,
              targetKind: targetKind === "node" ? undefined : targetKind,
              color: window.currentStrokeColor || "#ffffff",
              sourceAnchor: d.linkSourceAnchor || undefined,
              targetAnchor: targetAnchor || undefined,
              //: A board link wears the held tool's ends; a map's cross-link
              //: keeps the map's own look.
              ...(crossLink ? {} : wbToolCaps()),
         };
         //: A board's default connector style (Set as default style) starts every new link, a map's cross-link too.
         const sketchData = {
           data: JSON.stringify(wbFmtState.board?.withDefaults("link", linkBase) ?? linkBase),
           x: 0, y: 0, z: wbStackNewZ("sketch"),
           board_id: window.currentBoardId
         };
         try {
           const res = await apiJson("/whiteboard/sketches", { method: "POST", body: JSON.stringify(sketchData) });
           wbState.sketches.push(res);
           wbPushUndo({ action: "create", kind: "sketch", id: res.id });
           //: **A cross-link has to be *told* it is one, before it is drawn**
           //: (MINDMAP_PLAN §13c). What marks a link sketch as a cross-link is
           //: the board tree's `cross_links`, which is fetched with the map's
           //: state, so a link drawn now and rendered now carried none of the
           //: map's treatment: it was drawn as an ordinary board connector, in
           //: the pen's colour and solid, until the board was next opened. That
           //: is the most literal possible form of "there are two types of
           //: connections" and the reason this refresh is awaited before the
           //: render rather than left to the next reload.
           if (wbIsMap()) await wbRefreshMapState();
           wbScheduleRender();
           //: **Say which of the two it made** (MINDMAP_PLAN §13c). One gesture
           //: produces either kind, decided by whether the far end is already in
           //: the tree (`wbMapJoinByLink`), and §13.2's finding was that nothing
           //: on screen says which is about to happen. The branch half has said
           //: so since it was built ("Connected to ... as a branch"); this is
           //: the other half, in the same words the ring and the rail now use.
           if (wbIsMap() && wbMapCrossLinkInfo(res.id)) {
             toast("Cross-link made: it joins two branches without changing the tree.");
           }
         } catch (err) {
           toast(voiceLine("failed", "connect those", err.message), true);
         }
      }
      d.linkSourceAnchor = null;
    } else {
      //: Dropped on the delete target: put back, then deleted (INBOX 660).
      wbTrashTake(d._gesture, "node", d);
      wbClearAlignmentGuides();
      // Sync back to API.
      //
      // `board_id` has to go with it. The server takes the whole node on a PUT,
      // so omitting it read as "move this to the global board", dragging a card
      // on a named board silently moved it off that board.
      //
      // And a 404 here is recoverable rather than fatal: it means this client's
      // copy of the board is stale (the note was purged, or the board was
      // rebuilt). Refetching puts the screen back in step; leaving it, as this
      // did, shows a card sitting where you dropped it that is not saved
      // anywhere: the worst of both answers.
      const moveBefore = d._moveUndoBefore;
      delete d._moveUndoBefore;
      // Reset unconditionally, even when this gesture wasn't a bulk move,
      // see the matching comment in objDrag's own "end" for why leaving a
      // solo drag's `null` in place would break bulk-move detection later.
      const bulkOrigin = d._bulkOrigin;
      delete d._bulkOrigin;
      const altCopy = d._altCopy;
      delete d._altCopy;
      const cancelled = wbEndGesture(d._gesture);
      delete d._gesture;
      if (cancelled) return;
      //: A click is not a drop (see objDrag's own "end"): only a card that
      //: really moved is saved.
      const moved = moveBefore && (moveBefore.x !== d.x || moveBefore.y !== d.y);
      if (moved || !moveBefore) await wbSaveNode(d);
      if (d._unsaved) {
        //: Not saved: back where it was taken from (see objDragEnd's twin).
        delete d._unsaved;
        if (moveBefore) Object.assign(d, { x: moveBefore.x, y: moveBefore.y });
        wbScheduleRender();
        toast(voiceLine("failed", "save the move", "the item went back where it was"), true, { action: ["Reload the board", () => fetchWhiteboardState().then(wbScheduleRender)] });
        return;
      }
      //: The whole drag is one undo step now, carried members and Alt copies
      //: included (`wbFinishDrag`); this used to undo only the card grabbed.
      await wbFinishDrag(moved ? { action: "move", kind: "node", id: d.id, before: moveBefore } : null, bulkOrigin, altCopy);
    }
  }

  //: The file's surface: what other files call (L634).
  Object.assign(window, { wbObjectPaintKey, wbLinkSketchIndex, wbParsedLink, wbLinkedSketchesFor, wbUpdateLinkedSketches, dragStart, dragEndNode });
})();
