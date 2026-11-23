(() => {
  // whiteboard-gesture.js: gestures, the bin target and drag finishing, moved out of whiteboard.js (L634).
  // Wrapped: only what other files call goes on `window`; nothing here runs at load.

  //: `move` marks the three item drags (a card, a box or topic, a shape), the
  //: gestures the delete target answers (`wbTrashTake`).
  function wbBeginGesture(restore, move = false) {
    wbGesture = { restore, cancelled: false, move };
    return wbGesture;
  }

  function wbEndGesture(gesture) {
    if (gesture && wbGesture === gesture) wbGesture = null;
    return Boolean(gesture?.cancelled);
  }

  //: Called by the board's Escape before anything else Escape does: a gesture
  //: in flight is the one thing on screen the key can mean.
  function wbCancelGesture() {
    const gesture = wbGesture;
    if (!gesture || gesture.cancelled) return false;
    gesture.cancelled = true;
    try {
      gesture.restore?.();
    } finally {
      wbClearAlignmentGuides();
      wbTrashHide();
    }
    return true;
  }

  function wbTouchSlopStep(gesture, event, unit = 1, slop = WB_TOUCH_SLOP) {
    const { dx, dy } = event;
    const touch = String(event.sourceEvent?.type || "").startsWith("touch");
    if (!gesture || gesture.slopDone) return { dx, dy };
    gesture.slopX = (gesture.slopX || 0) + dx;
    gesture.slopY = (gesture.slopY || 0) + dy;
    if (Math.hypot(gesture.slopX, gesture.slopY) * unit < (touch ? slop : WB_CLICK_SLOP)) return null;
    gesture.slopDone = true;
    return { dx: gesture.slopX, dy: gesture.slopY };
  }

  //: True for the touch-start of a second finger (or a third). d3-drag's filter
  //: gets the touch-start itself as `event`.
  function wbIsSecondTouch(event) {
    return String(event?.type || "").startsWith("touch") && (event.touches?.length || 0) > 1;
  }

  function wbTrashTarget() {
    if (wbTrash.el?.isConnected) return wbTrash.el;
    const host = document.getElementById("wb-present-bar")?.parentElement;
    if (!host) return null;
    wbTrash.el = document.createElement("div");
    wbTrash.el.className = "whiteboard-floating-panel wb-trash card glass hidden";
    wbTrash.el.setAttribute("aria-hidden", "true");
    const icon = document.createElement("i");
    icon.className = "ph ph-trash";
    const label = document.createElement("span");
    label.className = "wb-trash-label";
    wbTrash.el.append(icon, label);
    //: The sidebar's drags (Library tiles, Layers rows) are the browser's own drag and drop, which sends no pointer
    //: moves, so the target answers dragover, dragleave and drop itself (after INBOX 660, LEDGER L262).
    wbTrash.el.addEventListener("dragover", (e) => {
      if (!wbTrash.drop) return;
      e.preventDefault();
      e.dataTransfer.dropEffect = "move";
      if (!wbTrash.el.classList.contains("wb-trash-hot")) wbTrashSetHot(true);
    });
    wbTrash.el.addEventListener("dragleave", (e) => {
      if (!wbTrash.drop || wbTrash.el.contains(e.relatedTarget)) return;
      //: Crossing from the icon to the label leaves a child with no related target in some engines: only the pointer's place says it left.
      const r = wbTrash.el.getBoundingClientRect();
      const inside = e.clientX > r.left && e.clientX < r.right && e.clientY > r.top && e.clientY < r.bottom;
      if (!inside) wbTrashSetHot(false);
    });
    wbTrash.el.addEventListener("drop", (e) => {
      if (!wbTrash.drop) return;
      e.preventDefault();
      const drop = wbTrash.drop;
      wbTrash.dndEnd();
      drop();
    });
    host.appendChild(wbTrash.el);
    return wbTrash.el;
  }

  function wbTrashSetHot(hot) {
    const el = wbTrashTarget();
    if (!el) return;
    el.classList.toggle("wb-trash-hot", hot);
    el.querySelector(".wb-trash-label").textContent = hot ? "Release to delete" : "Drop here to delete";
  }

  function wbTrashHide() {
    wbTrash.rect = null;
    if (wbTrash.el) wbTrash.el.classList.add("hidden");
  }

  //: Called first thing by each item drag's end, while the drag still holds
  //: what `restore` needs. True when the drop was on the target: the move is
  //: put back, the gesture is marked cancelled (so the end saves nothing) and
  //: the delete is under way.
  function wbTrashTake(gesture, kind, d) {
    const hit = Boolean(gesture && gesture === wbGesture && gesture.move && !gesture.cancelled && gesture.overTrash);
    wbTrashHide();
    if (!hit) return false;
    const keys = wbDragIsBulkMove(kind, d.id) ? [...wbMultiSelection] : [wbMultiKey(kind, d.id)];
    gesture.cancelled = true;
    try {
      gesture.restore?.();
    } finally {
      wbClearAlignmentGuides();
    }
    wbTrashDelete(keys);
    return true;
  }

  async function wbTrashDelete(keys) {
    const rank = { sketch: 0, node: 1, object: 2 };
    const ordered = [...keys].sort((a, b) => rank[a.split(":")[0]] - rank[b.split(":")[0]]);
    const find = (key) => {
      const sep = key.indexOf(":");
      const kind = key.slice(0, sep), id = Number(key.slice(sep + 1));
      return [kind, (wbState[WB_LIST_BY_KIND[kind]] || []).find((i) => i.id === id)];
    };
    const map = wbIsMap();
    const topics = () => (wbState.objects || []).filter((o) => WB_MAP_KINDS.has(o.kind)).length;
    const topicsBefore = map ? topics() : 0;
    wbMultiSelection.clear();
    clearWbSelection();
    await wbRecordGesture(async () => {
      for (const key of ordered) {
        const [kind, item] = find(key);
        if (!item) continue;
        if (kind === "sketch") await wbDeleteSketch(item);
        else if (kind === "node") await wbDeleteNode(item);
        else await wbDeleteObject(item);
      }
    });
    wbApplySelectionHighlight();
    wbScheduleRender();
    const gone = ordered.filter((key) => !find(key)[1]).length;
    if (!gone) return;
    const step = wbStacks.undo[wbStacks.undo.length - 1];
    const topicsGone = map ? topicsBefore - topics() : 0;
    const words = topicsGone
      ? `Deleted ${nounCount(topicsGone, "topic")}.`
      : `Deleted ${gone === 1 ? "1 item" : `${gone} items`}.`;
    wbAnnounce(words);
    toastAction(words, "Undo", async () => {
      //: The toast's Undo is the stack's own step, and only while it is the
      //: last thing done: Ctrl+Z may already have taken it back.
      if (wbStacks.undo[wbStacks.undo.length - 1] === step) await wbUndo();
    });
  }

  //: Put a moved item (and whatever moved with it) back where the drag found
  //: it, on screen only: nothing was saved yet, so nothing needs unsaving.
  function wbRestoreMove(kind, d) {
    if (kind === "sketch") {
      const el = wbInstances.query(`.sketch-group[data-id="${d.id}"]`);
      if (d._dragOriginalD != null) {
        el?.querySelector(".sketch-path")?.setAttribute("d", d._dragOriginalD);
        el?.querySelector(".sketch-hitbox")?.setAttribute("d", d._dragOriginalD);
        wbLayoutShapeLabel(el);
      }
      delete d._dragLiveD;
    } else {
      d.x = d._dragOriginX;
      d.y = d._dragOriginY;
      const el = document.querySelector(WB_SELECTOR_BY_KIND[kind](d.id));
      if (el) el.style.transform = wbItemTransform(d);
    }
    if (d._bulkOrigin) {
      wbApplyBulkMove(d._bulkOrigin, 0, 0);
      for (const entry of d._bulkOrigin.values()) delete entry.item._liveD;
    }
    if (d._linkedSketches?.length) wbUpdateLinkedSketches(d.id, d._linkedSketches);
    if (d._mapEdges?.length) wbUpdateMapEdges(d._mapEdges);
    if (wbIsMap()) wbMapClearDropTarget();
    delete d._dropTarget;
    wbUpdateSelectionBar();
  }

  //: Put a resized or turned card or text box back to the box it had when the
  //: grip was taken, from the undo snapshot the grip already keeps.
  function wbRestoreBox(kind, d, before) {
    if (!before) return;
    for (const key of ["x", "y", "width", "height", "rotation"]) d[key] = before[key];
    const el = document.querySelector(WB_SELECTOR_BY_KIND[kind](d.id));
    if (!el) return;
    el.style.width = d.width ? `${d.width}px` : "";
    el.style.height = d.height ? `${d.height}px` : "";
    el.style.transform = wbItemTransform(d);
  }

  //: **Shift keeps a move on one axis** (Figma, Miro, tldraw, PowerPoint): the
  //: axis the pointer has travelled further along wins, decided afresh every
  //: frame so a drag that turns the corner follows it. `null` means free.
  function wbAxisLock(dx, dy, shiftKey) {
    if (!shiftKey) return null;
    return Math.abs(dx) >= Math.abs(dy) ? "x" : "y";
  }

  //: The undo entries for every member a drag carried besides the item under
  //: the pointer. A group move used to undo only the one item that was grabbed
  //: and leave the rest of the group where it landed ("a real limitation, not
  //: attempted further", the node drag's end said): the origin map already
  //: holds where each member started, so the whole move is one step now.
  function wbBulkUndoEntries(origin) {
    const out = [];
    for (const entry of origin?.values() || []) {
      const before = WB_KIND_INFO[entry.kind].payload(entry.item);
      if (entry.kind === "sketch") {
        let parsed = null;
        try { parsed = JSON.parse(entry.item.data); } catch { parsed = null; }
        if (!parsed) continue;
        parsed.d = entry.d;
        before.data = JSON.stringify(parsed);
      } else {
        if (entry.item.x === entry.x && entry.item.y === entry.y) continue;
        before.x = entry.x;
        before.y = entry.y;
      }
      out.push({ action: "move", kind: entry.kind, id: entry.id, before });
    }
    return out;
  }

  //: **Alt-drag leaves a copy behind** (tldraw, Figma, Miro and Excalidraw all
  //: bind it). Made at the drop, at the place every dragged item was taken
  //: from, rather than at the press: a copy created mid-gesture needs a render
  //: to appear, and a render during a drag is exactly what this file keeps
  //: finding kills the drag. What is left behind and what is carried look the
  //: same, so where the copy is made is invisible except for that.
  //:
  //: Two things are not copied, each for a reason that is not this gesture's:
  //: a note card (one card per note per board, `wbCopySelection`'s own note)
  //: and a map topic (a copy of a topic's row is a topic with no place in
  //: the tree, which is not what anyone dragging a branch means by a copy).
  //: A group copied together is a new group, not new members of the old one.
  async function wbDropCopies(befores) {
    const created = await wbCreateCopies(
      befores
        .filter(({ kind, before }) => kind !== "node" && !(kind === "object" && WB_MAP_KINDS.has(before.kind)))
        .map(({ kind, before }) => ({ kind, payload: before })),
      0, 0
    );
    if (befores.some((b) => b.kind === "node")) {
      toast("A note card can't be copied: drag the note in again from the Library for a second card.");
    }
    return created;
  }

  //: Make copies of `items` ({kind, payload}) moved by (dx, dy), and return
  //: their "create" undo entries. The one maker behind Alt-drag, Ctrl+D and
  //: paste, so a copy is the same thing however it was asked for: a group
  //: copied whole is a new group, and a shape moves by its path, not its x/y
  //: (see `wbTransformPathD`: a sketch's own x/y do not place it).
  async function wbCreateCopies(items, dx, dy, noComments = false) {
    const groups = new Map();
    const wire = items.map(({ kind, payload, key, src, dst }, i) => {
      const body = { ...payload, board_id: window.currentBoardId ?? null };
      if (kind === "sketch") {
        const parsed = JSON.parse(body.data || "{}");
        if (dx || dy) {
          if (typeof parsed.d === "string") parsed.d = wbTransformPathD(parsed.d, { dx, dy });
          else wbShiftLinkGeometry(parsed, dx, dy);
        }
        if (noComments) delete parsed.comments;
        body.data = JSON.stringify(parsed);
      } else {
        body.x = (body.x || 0) + dx;
        body.y = (body.y || 0) + dy;
        if (noComments) wbWithoutComments(body);
      }
      //: Each id in the chain gets its own fresh one, so a pasted group of
      //: groups is still nested and never joins the original.
      if (body.group_id) {
        body.group_id = wbGroupChain(body).map((seg) => {
          if (!groups.has(seg)) groups.set(seg, wbNewGroupId());
          return groups.get(seg);
        }).join(WB_GROUP_SEP);
      }
      const row = { key: key || `i${i}` };
      if (kind === "sketch") Object.assign(row, { sketch: body, src: src || null, dst: dst || null });
      else row.object = body;
      return row;
    });
    //: One request for the whole paste (the server makes the rows in one
    //: transaction and points each copied link at its new ends), where it was
    //: one request per item: measured in WHITEBOARD_PLAN 1355.
    let res;
    try {
      res = await apiJson(`/whiteboard/boards/${window.currentBoardId ?? 0}/paste`, { method: "POST", body: JSON.stringify({ items: wire }) });
    } catch (err) {
      toast(err.message || voiceLine("failed", { what: "make that copy" }), true);
      return [];
    }
    wbState.objects.push(...res.objects);
    wbState.sketches.push(...res.sketches);
    return [
      ...res.objects.map((o) => ({ action: "create", kind: "object", id: o.id })),
      ...res.sketches.map((o) => ({ action: "create", kind: "sketch", id: o.id })),
    ];
  }

  //: A copy without the threads on it: a card's `comments` column, an object's
  //: `data.comments`.
  function wbWithoutComments(body) {
    if ("comments" in body) body.comments = null;
    if (body.data && typeof body.data === "object") {
      const { comments, ...rest } = body.data;
      body.data = rest;
    }
  }

  //: A copied link carries its own free ends and bends in board units, so a
  //: moved copy moves them too (a path's `d` is moved by `wbTransformPathD`).
  function wbShiftLinkGeometry(parsed, dx, dy) {
    for (const name of ["sourcePoint", "targetPoint"]) {
      if (parsed[name]) parsed[name] = { x: parsed[name].x + dx, y: parsed[name].y + dy };
    }
    if (Array.isArray(parsed.points)) parsed.points = parsed.points.map((p) => ({ x: p.x + dx, y: p.y + dy }));
  }

  //: One undo step for a whole drag: the item under the pointer, the members
  //: it carried, and the copies an Alt-drag left behind.
  function wbPushDragUndo(entries) {
    const all = entries.filter(Boolean);
    if (all.length === 0) return;
    wbPushUndo(all.length === 1 ? all[0] : { action: "batch", entries: all });
  }

  //: Everything a drag that ends has to do after its own item is saved: the
  //: carried members saved, the copies made, and one undo step pushed for it.
  async function wbFinishDrag(primary, bulkOrigin, altCopy) {
    wbFmtState.keys?.recordDrag(primary);
    const carried = wbBulkUndoEntries(bulkOrigin);
    if (bulkOrigin) await wbSaveBulkMove(bulkOrigin);
    const bends = await wbCarryWaypoints(primary, bulkOrigin);
    let copies = [];
    if (altCopy && (primary || carried.length)) {
      copies = await wbDropCopies([primary, ...carried].filter(Boolean));
    }
    wbPushDragUndo([primary, ...carried, ...bends, ...copies]);
    if (copies.length || bends.length) wbScheduleRender();
  }

  //: **A connector's bends move with what it joins** (wb-phase2 step 5,
  //: draw.io's rule): when both its ends were carried by one drag, its
  //: waypoints go the same way, so a moved group keeps its lines' shape rather
  //: than leaving their bends behind. Returns the undo entries, which ride in
  //: the drag's one step.
  async function wbCarryWaypoints(primary, origin) {
    if (!origin?.size) return [];
    let dx = 0, dy = 0, found = false;
    for (const entry of origin.values()) {
      if (entry.kind === "sketch") {
        const was = typeof entry.d === "string" ? wbPathBBox(entry.d) : null;
        const now = was && wbItemBBox("sketch", entry.item);
        if (was && now) [dx, dy, found] = [now.minX - was.minX, now.minY - was.minY, true];
      } else if (entry.x !== undefined) {
        [dx, dy, found] = [entry.item.x - entry.x, entry.item.y - entry.y, true];
      }
      if (found) break;
    }
    if (!found || (!dx && !dy)) return [];
    const moved = new Set(origin.keys());
    if (primary) moved.add(wbMultiKey(primary.kind, primary.id));
    const out = [];
    const rows = [];
    for (const sketch of wbState.sketches || []) {
      let data = null;
      try {
        data = JSON.parse(sketch.data);
      } catch {
        continue;
      }
      if (!data || !String(data.type || "").startsWith("link-") || !Array.isArray(data.points) || !data.points.length) continue;
      const ends = [[data.sourceKind || "node", data.sourceId], [data.targetKind || "node", data.targetId]];
      if (!ends.every(([kind, id]) => id != null && moved.has(wbMultiKey(kind, id)))) continue;
      const before = WB_KIND_INFO.sketch.payload(sketch);
      wbSketchSetProps(sketch, { points: data.points.map((p) => ({ x: Math.round(p.x + dx), y: Math.round(p.y + dy) })) });
      rows.push({ kind: "sketch", item: sketch });
      out.push({ action: "move", kind: "sketch", id: sketch.id, before });
    }
    await wbSaveMany(rows);
    return out;
  }

  //: **A map's own nodes go in one request.** A tidy of a two hundred node map
  //: was two hundred PUTs, two hundred transactions and a map half arranged for
  //: as long as they took, with nothing to roll back to when one of them failed
  //: (recorded as "Tidy still persists one node at a time"). `move-many` takes
  //: the whole set, so the batch either lands or does not. Everything that is
  //: not a map node on a map board still goes one at a time: a sketch's `d` and
  //: an image's box are not what that endpoint moves.
  //:
  //: Chunked at 200 against the endpoint's own 400, so a map twice the size of
  //: anything built here still goes in two requests rather than in four hundred.
  //: A failure falls back to the per-object path rather than surfacing: the
  //: caller has already painted the new positions, and the fallback is the code
  //: that was doing this until now.
  const WB_MOVE_MANY_CHUNK = 200;

  async function wbSaveMapBulkMove(origin) {
    const boardId = window.currentBoardId;
    if (!boardId || !wbIsMap()) return null;
    const batched = [];
    for (const entry of origin.values()) {
      if (entry.kind === "object" && WB_MAP_KINDS.has(entry.item?.kind)) batched.push(entry);
    }
    //: One node is not a batch: a single PUT says more in its own event log and
    //: costs the same.
    if (batched.length < 2) return null;
    try {
      for (let at = 0; at < batched.length; at += WB_MOVE_MANY_CHUNK) {
        const slice = batched.slice(at, at + WB_MOVE_MANY_CHUNK);
        await apiJson(`/whiteboard/boards/${boardId}/nodes/move-many`, {
          method: "PUT",
          body: JSON.stringify({
            moves: slice.map((entry) => ({ id: entry.item.id, x: entry.item.x, y: entry.item.y })),
          }),
        });
      }
    } catch (err) {
      return null;
    }
    return new Set(batched);
  }

  async function wbSaveBulkMove(origin) {
    //: A link that travelled by its group's transform (`wbApplyBulkMove`) is
    //: written where it landed, the `d` a full recompute gives, and the
    //: transform cleared, before anything below reads or replaces the paths.
    if (origin.rigidAt) {
      for (const rigid of origin.rigidLinks || []) {
        if (!rigid.path.isConnected) continue;
        rigid.group.removeAttribute("transform");
        if (!rigid.state) origin.compileRigid(rigid);
        if (rigid.state === "bad") { wbUpdateLinkedSketches(null, [rigid.pair]); continue; }
        rigid.path.setAttribute("d", rigid.at(...origin.rigidAt));
        rigid.hit?.setAttribute("d", rigid.hitAt(...origin.rigidAt));
      }
      origin.rigidAt = null;
    }
    //: **And is rebuilt where the items landed, before the save goes out.** The
    //: translate above is a view of the drag, not the truth: the items' own
    //: coordinates have moved, so the outline has to be recomputed from them or
    //: it keeps the offset for as long as the selection lasts. Measured before
    //: the fix: after the drag ended the box was still at the position the
    //: items had started from, not just during the gesture.
    //:
    //: Here rather than in each of the three per-kind drag handlers, because
    //: this is the one function all three end at, and it runs after the drag is
    //: over, so replacing the handle elements can no longer cut a gesture short.
    wbApplySelectionHighlight();
    const done = await wbSaveMapBulkMove(origin);
    const rows = [];
    for (const entry of origin.values()) {
      if (done && done.has(entry)) continue;
      if (entry.kind === "sketch") {
        if (!entry.item._liveD) continue;
        wbSketchSetD(entry.item, entry.item._liveD);
        delete entry.item._liveD;
      }
      rows.push({ kind: entry.kind, item: entry.item });
    }
    await wbSaveMany(rows);
  }

  //: The file's surface: what other files call (L634).
  Object.assign(window, { wbBeginGesture, wbEndGesture, wbCancelGesture, wbTouchSlopStep, wbIsSecondTouch, wbTrashTarget, wbTrashSetHot, wbTrashHide, wbTrashTake, wbTrashDelete, wbRestoreMove, wbRestoreBox, wbAxisLock, wbCreateCopies, wbPushDragUndo, wbFinishDrag, wbCarryWaypoints, wbSaveBulkMove });
})();
