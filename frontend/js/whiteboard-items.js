(() => {
  // whiteboard-items.js: painting the board's items, fitting them to their words, saving and deleting them (moved out of whiteboard.js, L634).
  // Wrapped: only what other files call goes on `window`; nothing here runs at load.

  function wbScheduleRender() {
    if (wbRenderQueued) return;
    wbRenderQueued = true;
    wbRenderFrame = requestAnimationFrame(() => {
      wbRenderFrame = 0;
      wbRenderQueued = false;
      renderWhiteboard();
      wbUpdateSelectionBar();
      wbSyncBoardCount();
      wbMapAfterRender();
      wbFmtState.opts?.afterRender();
    });
  }

  function wbCloseOrphanedPopovers() {
    editorCloseOrphans();
    for (const popover of WB_ITEM_POPOVERS) {
      const ref = popover.ref();
      if (ref && !wbFindItem(ref.kind, ref.id)) popover.close();
    }
  }

  //: Delete a sketch, node or object by item (audit 1028 B7). Plain top-level
  //: functions: nothing here closes over a render, so the Delete key, the
  //: eraser, the menus and the selection bar all call the one function and no
  //: stale closure can be the one that runs. The eraser is a drag: mouseenter
  //: fires for everything the pointer crosses while `wbErasing` is true.
  async function wbDeleteSketch(d) {
    const deletingKey = `sketch:${d.id}`;
    if (wbDeleting.has(deletingKey)) return;
    wbDeleting.add(deletingKey);
    //: With the links that end on it, which the server drops too (INBOX 537),
    //: and taken off the stack by identity, not by `pop`: a second delete in
    //: flight may have pushed after this one.
    const links = wbLinksTouching("sketch", d.id);
    const edgeEnds = wbFmtState.linkEdge?.beforeDelete(d); // connector ends on this one float free (whiteboard-link-edge.js)
    const entry = { action: "delete", kind: "sketch", payload: WB_KIND_INFO.sketch.payload(d), oldId: d.id, links, edgeEnds };
    const redoBefore = wbStacks.redo;
    wbPushUndo(entry);
    try {
      await apiJson(`/whiteboard/sketches/${d.id}`, { method: "DELETE" });
      wbState.sketches = wbState.sketches.filter((s) => s.id !== d.id);
      wbForgetLinks(links);
      await wbFmtState.linkEdge?.afterDelete(edgeEnds);
      wbScheduleRender();
    } catch (e) {
      wbDeleteFailed(entry, redoBefore, e, () => wbDeleteSketch(d)); // the delete never happened, so neither did the undo entry
    } finally {
      wbDeleting.delete(deletingKey);
    }
  }

  async function wbDeleteNode(d) {
    const deletingKey = `node:${d.id}`;
    if (wbDeleting.has(deletingKey)) return;
    wbDeleting.add(deletingKey);
    const links = wbLinksTouching("node", d.id);
    const entry = { action: "delete", kind: "node", payload: WB_KIND_INFO.node.payload(d), oldId: d.id, links };
    const redoBefore = wbStacks.redo;
    wbPushUndo(entry);
    try {
      await apiJson(`/whiteboard/nodes/${d.id}`, { method: "DELETE" });
      wbState.nodes = wbState.nodes.filter((n) => n.id !== d.id);
      wbForgetLinks(links);
      wbScheduleRender();
    } catch (e) {
      wbDeleteFailed(entry, redoBefore, e, () => wbDeleteNode(d));
    } finally {
      wbDeleting.delete(deletingKey);
    }
  }

  async function wbDeleteObject(d) {
    // The same rule as the map's own subtree delete, at the other door: this
    // is what the Delete tool, the context menu's Delete and the selection
    // bar all call, and a rule enforced at one of two doors is not a rule.
    if (WB_MAP_KINDS.has(d.kind) && wbMapDeleteEmptiesMap(d.id)) {
      wbMapRefuseLastTopic();
      return;
    }
    const deletingKey = `object:${d.id}`;
    if (wbDeleting.has(deletingKey)) return;
    wbDeleting.add(deletingKey);
    const entry = { action: "delete", kind: "object", payload: WB_KIND_INFO.object.payload(d), oldId: d.id, parentId: d.parent_id ?? null, links: wbLinksTouching("object", d.id) };
    const redoBefore = wbStacks.redo;
    wbPushUndo(entry);
    try {
      const res = await apiJson(`/whiteboard/objects/${d.id}`, { method: "DELETE" });
      //: **A topic's branch is on the entry too** (INBOX 537): the server took
      //: the whole subtree, and an entry of one row brought back one topic.
      if (Array.isArray(res?.deleted) && res.deleted.length > 1) {
        Object.assign(entry, { action: "subtree", rows: res.deleted, links: Array.isArray(res.links) ? res.links : [] });
      }
      wbForgetLinks(Array.isArray(res?.links) ? res.links : entry.links);
      // **Whatever the server says it deleted, not just the row we asked
      // about.** On a map this endpoint takes the node's whole subtree and
      // returns it as `deleted[]` (§9.1), so dropping only `d.id` here left
      // every descendant on the canvas as a card pointing at a row that no
      // longer exists: visible as nodes that survive a delete and then 404
      // on the next save. Found by deleting a branch with the Delete key and
      // counting: the server removed two rows, the board still drew one of
      // them. An ordinary text box or image has no children, so `deleted`
      // is a single row there and this is exactly what it always was.
      const gone = new Set(
        Array.isArray(res?.deleted) && res.deleted.length
          ? res.deleted.map((row) => row.id)
          : [d.id]
      );
      wbState.objects = wbState.objects.filter((o) => !gone.has(o.id));
      wbScheduleRender();
    } catch (e) {
      wbDeleteFailed(entry, redoBefore, e, () => wbDeleteObject(d));
    } finally {
      wbDeleting.delete(deletingKey);
    }
  }

  //: One PUT body builder for a node, shared by every call site that saves
  //: one (drag-end, resize-end, bulk-move, grouping), three of those used to
  //: each build the body by hand, and it was exactly that duplication that
  //: let a save silently drop `group_id` back to null the first time this
  //: file added it (nothing reminded the third copy to include the new field).
  //: **Double-tap an anchor and the box fits its text.** Asked for directly: "I
  //: want to be able tot double tap anchor edges to auto resize notes,
  //: textboxes, and nstickynotes etc to auto size adjust to the text in them".
  //: The drag already resizes by hand; this is the same handle saying "as
  //: small as it can be and still show everything", which is the size people
  //: are dragging towards most of the time and cannot hit exactly.
  //:
  //: Height only. A text box's width is a line-length decision (the text
  //: rewraps as it changes, so "fit the width" has no fixed point: narrowing
  //: makes it taller, which makes nothing shorter), and its height is the one
  //: dimension with a single right answer for a given width.
  //:
  //: `height: auto` then `scrollHeight`: the element's own layout is the only
  //: thing that knows what the text, at this width, in this font, actually
  //: needs. Measured live rather than estimated from character counts, which is
  //: the version of this that is wrong for every font but the one it was tuned
  //: against.
  //: **Double-click the rotate grip and the item stands up straight again**
  //: (the owner, 2026-09-23: "double clcike the rotate point above the top
  //: centre of an object and reset it to its default rotate"). The same
  //: gesture Figma, Miro and PowerPoint give the grip, and the partner of the
  //: resize handle's double-click-to-fit just below: a handle's double-click
  //: puts back the thing that handle changes.
  //:
  //: A card and a text box store their angle, so this is `rotation: 0`. A
  //: shape bakes its turn into its path (see the sketch rotate grip), so it
  //: keeps a running total of the turns it was given in `turned` and is
  //: rotated back by that much about its own centre. A shape turned before
  //: `turned` existed, or resized since (see the resize grip), has nothing to
  //: go back by, and says so rather than guessing. A group's grip is not here: a group has no angle of its own,
  //: only members that were each turned about its centre.
  async function wbResetRotation(grip, alone = false) {
    const el = grip.closest(".node-card, .wb-object");
    if (el) {
      const kind = el.classList.contains("node-card") ? "node" : "object";
      const item = (wbState[WB_LIST_BY_KIND[kind]] || []).find((i) => i.id === Number(el.dataset.id));
      if (!item || !item.rotation) return;
      const before = WB_KIND_INFO[kind].payload(item);
      //: **A frame stood upright takes what it holds with it** (the 22-10 bug
      //: doc: "if I double click the rotate" node the frame resets and its
      //: contents stay turned). The same turn a drag of its grip makes, by
      //: minus its angle, in one Undo step; Ctrl stands the frame up alone.
      if (kind === "object" && item.kind === "frame") {
        item._turnFrom = item.rotation;
        item._turnOrigin = wbFrameTurnOrigin(item, alone);
      }
      item.rotation = 0;
      el.style.transform = wbItemTransform(item);
      if (item._turnOrigin) {
        wbFrameTurnLive(item);
        await wbSaveObject(item);
        await wbFrameTurnEnd(item, { action: "move", kind, id: item.id, before });
        wbScheduleRender();
        return;
      }
      delete item._turnOrigin;
      if (kind === "node") await wbSaveNode(item);
      else await wbSaveObject(item);
      wbPushUndo({ action: "move", kind, id: item.id, before });
      wbScheduleRender();
      return;
    }
    const sketch = wbSelectedSketchOrNull();
    const parsed = sketch && wbSketchParsedData(sketch);
    if (!parsed) return;
    const turned = Number(parsed.turned) || 0;
    if (!turned) {
      toast("This shape has no turn to take back: it is upright, or was resized or turned before its angle was kept.");
      return;
    }
    const box = wbPathBBox(parsed.d);
    if (!box) return;
    const before = WB_KIND_INFO.sketch.payload(sketch);
    const d = wbTransformPathD(parsed.d, {
      rotate: -turned, anchorX: (box.minX + box.maxX) / 2, anchorY: (box.minY + box.maxY) / 2,
    });
    await wbSaveSketchProps(sketch, { d, turned: 0 });
    wbPushUndo({ action: "move", kind: "sketch", id: sketch.id, before });
    wbScheduleRender();
  }

  //: The height a card's text needs, chrome included (see `wbFitToText`):
  //: the double-click's answer, and the "fit content" snap of a card's resize.
  function wbCardFitHeight(el) {
    const content = el.querySelector(".wb-card-content");
    const previous = el.style.height;
    let fitted = 0;
    if (content) {
      const saved = {
        overflow: content.style.overflow,
        maxHeight: content.style.maxHeight,
        height: content.style.height,
      };
      //: The chrome is measured *before* anything is opened up, while the card
      //: is still in its real layout: afterwards both boxes are growing and
      //: the difference between them is no longer the padding.
      const chrome = Math.max(0, el.offsetHeight - content.offsetHeight);
      content.style.overflow = "visible";
      content.style.maxHeight = "none";
      content.style.height = "auto";
      el.style.height = "auto";
      fitted = Math.ceil(content.scrollHeight) + chrome;
      el.style.height = previous;
      for (const [name, value] of Object.entries(saved)) {
        const prop = name === "maxHeight" ? "max-height" : name;
        if (value) content.style.setProperty(prop, value);
        else content.style.removeProperty(prop);
      }
    } else {
      el.style.height = "auto";
      fitted = Math.ceil(el.scrollHeight);
      el.style.height = previous;
    }
    return fitted;
  }

  //: **Each grip says what its double-click does on this kind** (OPEN.md: the
  //: title said "fits the text" on a picture, which has none). A frame fits
  //: what it holds, a picture has nothing to fit, a table or diagram fits its
  //: content, the rest fit their words.
  function wbResizeHandleTitle(kind) {
    if (kind === "frame") return "Drag to resize, double-click to fit this edge to what is inside";
    if (kind === "image") return "Drag to resize: Shift keeps the proportions, double-click fits the picture";
    //: A table or a diagram has no words to fit: the double-click takes the height its content needs (L261).
    if (kind === "table" || kind === "diagram") return "Drag to resize: Shift keeps the proportions, double-click fits the height to what is inside";
    return "Drag to resize: Shift keeps the proportions, double-click fits the text";
  }

  //: A picture's own proportions at the width it has now (pure, node-tested).
  function wbImageFitHeight(natW, natH, width) {
    if (!(natW > 0 && natH > 0)) return width;
    return Math.max(WB_OBJECT_MIN_SIZE, Math.round((width * natH) / natW));
  }

  //: Double-click on a picture's grip: the box takes the picture's natural
  //: aspect at the current width, one undo step.
  async function wbFitImage(el) {
    const item = (wbState.objects || []).find((o) => o.id === Number(el.dataset.id));
    const img = el.querySelector("img");
    if (!item || !img) return;
    const next = wbImageFitHeight(img.naturalWidth, img.naturalHeight, item.width);
    if (Math.abs(item.height - next) < 2) {
      toast("Already the picture's own shape.");
      return;
    }
    const before = WB_KIND_INFO.object.payload(item);
    item.height = next;
    el.style.height = `${next}px`;
    await wbSaveObject(item);
    wbPushUndo({ action: "move", kind: "object", id: item.id, before });
    wbScheduleRender();
    toast(voiceLine("done", "Fitted to the picture"));
  }

  async function wbFitToText(el) {
    if (!el) return;
    const id = Number(el.dataset.id);
    const isNode = el.classList.contains("node-card");
    const item = isNode
      ? (wbState.nodes || []).find((n) => n.id === id)
      : (wbState.objects || []).find((o) => o.id === id);
    if (!item) return;
    //: A map topic has no stored height at all until someone drags one in
    //: (`sized`), and its own rule is "the text owns the height". Fitting one
    //: is therefore not a new number, it is dropping the number: the same
    //: "Back to the branch" the context menu offers for every other hand-set
    //: property.
    if (WB_MAP_KINDS.has(item.kind)) {
      if (!item.data?.sized) {
        toast("This topic is already sized to its text.");
        return;
      }
      //: **The height is a number the server accepts, never null** (INBOX 716,
      //: the owner's log: `[HTTP 422] PUT /whiteboard/objects/57: Check the
    //: height and try again.`). `height` is not nullable on the object schema,
      //: so dropping it as `null` was refused, `wbSaveObject` took the refusal
      //: for a stale board and reloaded it from the server, and the server still
      //: had the manual size: the next move of the node saved the old box back.
      //: What the topic needs is what its text needs, so it is measured once the
      //: floor is gone and stored as the drawn height, which is also what
      //: `wbMapNodeSize` falls back to before an element exists.
      const before = WB_KIND_INFO.object.payload(item);
      el.style.removeProperty("min-height");
      item.data = { ...item.data, sized: false };
      item.height = Math.max(WB_MAP_HEIGHT_FLOOR, Math.round(el.offsetHeight) || WB_MAP_NODE_H);
      //: The line follows the box in the same frame. The size measured for the
      //: edges is cached per gesture (`wbMapNodeSize`), and nothing here is a
      //: pointer-up, so without this the branch kept ending at the old box until
      //: something else redrew it.
      wbForgetMapNodeSize(item.id);
      wbUpdateMapEdges(wbMapEdgesFor(item.id));
      await wbSaveObject(item);
      wbPushUndo({ action: "move", kind: "object", id: item.id, before });
      wbScheduleRender();
      toast(voiceLine("done", "Sized to its text"));
      return;
    }
    //: **The card's own `scrollHeight` is not the answer for a note card.**
    //: Reported as the gesture not working at all: *"Double tap anchor resize
    //: nodes to auto size adjust"*. Measured, the gesture fires and the toast
    //: says "Sized to its text", and a 100px card holding fourteen wrapped
    //: lines came out 103px and still clipping.
    //:
    //: The reason is one rule further in. `.wb-card-content` carries
    //: `min-height: 0; overflow: hidden` on purpose (INBOX 238: without them a
    //: note's paragraphs were painted over the board), and a capped card also
    //: carries a `max-height`. Both mean the text is already clipped *inside*
    //: the card, so the card's own scroll height with `height: auto` is the
    //: height of a box that is clipping, not the height the text needs.
    //:
    //: So the measurement opens the content up too, reads, and puts every
    //: property back exactly as it found it. Restored with
    //: `removeProperty`/assignment of the saved value rather than by setting
    //: something "sensible": these elements are re-rendered from CSS, and
    //: leaving an inline `overflow` behind would silently disable the clipping
    //: that rule exists to do.
    //: **The text's height, plus the card's chrome.** Not the card's own
    //: `scrollHeight`, which is what this used to read and which cannot answer
    //: the question: `.wb-card-content` carries `min-height: 0` and
    //: `overflow: hidden` on purpose (INBOX 238, without them a note's
    //: paragraphs were painted over the board), so the text is already clipped
    //: *inside* the card and the card's scroll height is the height of a box
    //: that is clipping, not the height the text needs. Measured: a 100px card
    //: holding fourteen wrapped lines fitted to 100px, three times running,
    //: while the toast said it had been sized to its text.
    //:
    //: So the content is opened up and measured on its own, and the difference
    //: between the card and the content (padding, a thumbnail, a Show more
    //: row) is added back. Every property is restored to exactly what it was,
    //: by removal when it was not set inline: these elements are re-rendered
    //: from CSS, and an inline `overflow` left behind would silently disable
    //: the clipping that rule exists to do.
    const fitted = wbCardFitHeight(el);
    if (!fitted) return;
    //: The same floor the resize drag uses, so a fit cannot produce a box that
    //: a drag would refuse to make.
    const next = Math.max(WB_OBJECT_MIN_SIZE, fitted);
    if (Math.abs((item.height || 0) - next) < 2) {
      toast("Already sized to its text.");
      return;
    }
    const before = WB_KIND_INFO[isNode ? "node" : "object"].payload(item);
    item.height = next;
    el.style.height = `${next}px`;
    if (isNode) await wbSaveNode(item);
    else await wbSaveObject(item);
    wbPushUndo({ action: "move", kind: isNode ? "node" : "object", id: item.id, before });
    wbScheduleRender();
    toast(voiceLine("done", "Sized to its text"));
  }

  //: `boardId` is read when the save starts: a caller that awaited first (wbSaveMany) passes the one it began on.
  async function wbSaveNode(node, boardId = window.currentBoardId ?? null) {
    delete node._unsaved;
    try {
      const saved = await apiJson(`/whiteboard/nodes/${node.id}`, {
        method: "PUT",
        body: JSON.stringify({
          entry_id: node.entry_id,
          board_id: node.board_id ?? boardId,
          x: node.x, y: node.y, z: node.z,
          width: node.width ?? null, height: node.height ?? null,
          rotation: node.rotation ?? null,
          group_id: node.group_id ?? null,
          locked: Boolean(node.locked),
          comments: node.comments ?? null,
        }),
      });
      Object.assign(node, saved);
    } catch {
      recordBrowserLog("WARN", [`[Whiteboard] card ${node.id} is stale: reloading the board`]);
      await fetchWhiteboardState();
      wbScheduleRender();
      node._unsaved = true;
    }
  }

  async function wbSaveObject(d) {
    //: A topic still on its way to the server (`wbMapAddChild`'s optimistic
    //: add) is saved once it has its real id.
    if (d._creating) return d._creating.then((ok) => (ok ? wbSaveObject(d) : undefined));
    if (d._undoing) return;
    delete d._unsaved;
    const body = {
      kind: d.kind, data: d.data, board_id: d.board_id,
      x: d.x, y: d.y, z: d.z, width: d.width, height: d.height,
      rotation: d.rotation ?? null,
      group_id: d.group_id ?? null,
    };
    try {
      const saved = await apiJson(`/whiteboard/objects/${d.id}`, {
        method: "PUT",
        body: JSON.stringify(body),
        keepalive: wbCommitOpenEdit.leaving === true,
      });
      //: **What changed here while the save was out stays** (audit FEAT-02):
      //: with the map's add no longer waiting for its saves, a tidy or a
      //: rename can land between this request and its answer, and taking the
      //: answer whole put the topic back where it was when the request left.
      const now = { x: d.x, y: d.y, data: d.data };
      Object.assign(d, saved);
      if (now.x !== body.x || now.y !== body.y) Object.assign(d, { x: now.x, y: now.y });
      if (now.data !== body.data) d.data = now.data;
    } catch {
      // Same recoverable-stale-client shape every other whiteboard write here
      // already follows: a 404 means this object (or its board) is gone.
      recordBrowserLog("WARN", [`[Whiteboard] object ${d.id} is stale: reloading the board`]);
      await fetchWhiteboardState();
      wbScheduleRender();
      d._unsaved = true;
    }
  }

  //: **A selection is saved in one request** (audit 1031 BD2: Ctrl+A on 362
  //: items and two arrow presses sent 167 `PUT`s and three long tasks of 189 to
  //: 274 ms). `rows` is `{ kind, item }`; the server takes each item's own `PUT`
  //: body plus its id (`PUT /whiteboard/items/save-many`, one transaction, all
  //: or nothing). One item, or a topic still being created, goes the old way.
  async function wbSaveMany(rows) {
    //: **The board is the one the save began on** (L-whiteboard-57): a nudge burst is
    //: flushed as another board instance goes live (wbInstances.activate), so after
    //: the first await `currentBoardId` and the reload below are that board's.
    const inst = wbInstances.active;
    const boardId = window.currentBoardId ?? null;
    //: An item twice (width then height on one card) is one row: the server
    //: refuses a batch that names an id twice.
    const seen = new Set();
    const ready = rows.filter((r) => {
      const key = `${r.kind}:${r.item?.id}`;
      if (!r.item || r.item._creating || seen.has(key)) return false;
      seen.add(key);
      return true;
    });
    const waiting = rows.filter((r) => r.item?._creating);
    for (const { kind, item } of waiting) await wbSaveRow(kind, item, boardId);
    if (ready.length < 2) {
      for (const { kind, item } of ready) await wbSaveRow(kind, item, boardId);
      return true;
    }
    //: The route takes at most 5,000 of a kind a request; a larger selection
    //: goes in slices of that size (each slice all or nothing, like move-many).
    for (let at = 0; at < ready.length; at += WB_SAVE_MANY_MAX) {
      if (!(await wbSaveManyBatch(ready.slice(at, at + WB_SAVE_MANY_MAX), inst))) return false;
    }
    return true;
  }

  //: One `save-many` request. False (after reloading the board) when it fails;
  //: a board no longer live is not reloaded in the live one's place.
  async function wbSaveManyBatch(slice, inst = wbInstances.active) {
    const body = { nodes: [], sketches: [], objects: [] };
    for (const { kind, item } of slice) body[WB_KIND_INFO[kind].list].push({ id: item.id, ...WB_KIND_INFO[kind].payload(item) });
    try {
      await apiJson("/whiteboard/items/save-many", { method: "PUT", body: JSON.stringify(body) });
      return true;
    } catch {
      recordBrowserLog("WARN", ["[Whiteboard] a selection is stale: reloading the board"]);
      //: A board not live is read again by itself, not in the live one's place (L-whiteboard-65).
      if (wbInstances.active !== inst) {
        if (!inst.reload) inst.stale = true;
        else if (!inst.destroyed) inst.reload().catch(() => {});
        return false;
      }
      await fetchWhiteboardState();
      wbScheduleRender();
      return false;
    }
  }

  function wbSaveRow(kind, item, boardId) {
    if (kind === "sketch") return wbSaveSketchProps(item, {});
    return kind === "node" ? wbSaveNode(item, boardId) : wbSaveObject(item);
  }

  //: A sketch's `d` written into its data without saving it (a group drag's end).
  function wbSketchSetD(sketch, d) {
    const parsed = wbSketchParsedData(sketch);
    if (!parsed) return;
    wbFmtState.inkMore?.follow(parsed, d, wbPathBBox);
    parsed.d = d;
    sketch.data = JSON.stringify(parsed);
  }

  //: `wbSaveSketchProps`' merge without its save, for a selection saved together
  //: (`wbSaveMany`). False when the sketch holds nothing to merge into.
  function wbSketchSetProps(sketch, partial) {
    let parsed = null;
    try {
      const candidate = JSON.parse(sketch.data);
      if (candidate && (typeof candidate.d === "string" || (candidate.type || "").startsWith("link-"))) parsed = candidate;
    } catch {
      parsed = null;
    }
    if (!parsed) return false;
    wbFmtState.inkMore?.follow(parsed, partial.d, wbPathBBox);
    Object.assign(parsed, partial);
    sketch.data = JSON.stringify(parsed);
    return true;
  }

  //: The leading run of plain moves in a batch of undo steps, taken off it, so the
  //: run is put back with one request (`wbApplyMoveRun`); one move goes its own way.
  function wbTakeMoveRun(pending) {
    let n = 0;
    while (n < pending.length && pending[n].action === "move" && WB_KIND_INFO[pending[n].kind]) n++;
    return n > 1 ? pending.splice(0, n) : [];
  }

  async function wbApplyMoveRun(run) {
    const rows = [];
    const reverse = [];
    for (const entry of run) {
      const item = wbState[WB_KIND_INFO[entry.kind].list].find((i) => i.id === entry.id);
      if (!item) continue; // stale: nothing to restore, but the stack still advances
      reverse.push({ action: "move", kind: entry.kind, id: entry.id, before: WB_KIND_INFO[entry.kind].payload(item) });
      Object.assign(item, entry.before);
      rows.push({ kind: entry.kind, item });
    }
    await wbSaveMany(rows);
    return reverse;
  }

  function wbMapNodeTakeBack(d) {
    const kept = wbMapNodePool.get(d.id);
    if (!kept) return null;
    wbMapNodePool.delete(d.id);
    if (kept.__data__ !== d) return null;
    kept._wbTakenBack = true;
    return kept;
  }

  function wbScheduleStickyDates() {
    clearTimeout(wbStickyDates.timer);
    wbStickyDates.timer = setTimeout(wbPaintStickyDates, 250);
  }

  async function wbPaintStickyDates() {
    const papers = [...(wbInstances.container()?.querySelectorAll(".wb-sticky") || [])];
    const words = (el) => String(el.__data__?.data?.content || "");
    const ask = [...new Set(papers.map(words).filter((t) => t.trim() && !wbStickyDates.read.has(t)))].slice(0, 200);
    if (ask.length) {
      try {
        const got = await apiJson("/read/dates", { method: "POST", silent: true, body: JSON.stringify({ texts: ask, tz_offset_minutes: -new Date().getTimezoneOffset() }) });
        ask.forEach((text, i) => wbStickyDates.read.set(text, got.dates[i] || null));
      } catch {
        return;
      }
    }
    for (const paper of papers) {
      const day = wbStickyDates.read.get(words(paper));
      let tag = paper.querySelector(":scope > .wb-sticky-date");
      if (!day) {
        tag?.remove();
        continue;
      }
      if (!tag) {
        tag = chip("", "tag wb-sticky-date", (event) => {
          event.stopPropagation();
          wbStickyRemind(paper.__data__, wbStickyDates.read.get(words(paper)));
        });
        tag.addEventListener("pointerdown", (event) => event.stopPropagation());
        paper.appendChild(tag);
      }
      setLabel(tag, `${day.reminder ? "ph:bell-simple" : "ph:calendar-blank"} ${day.short}`);
      tag.title = day.reminder ? `Read as ${day.read_as}. Press to set a reminder.` : `Read as ${day.read_as}.`;
      tag.setAttribute("aria-label", tag.title);
    }
  }

  async function wbStickyRemind(d, day) {
    if (!d || !day?.reminder) return;
    try {
      const reminder = await apiJson("/reminders", {
        method: "POST",
        body: JSON.stringify({ text: day.reminder.text, due_at: day.reminder.due_at, priority: "normal", recurring: "none" }),
      });
      loadReminders();
      toast(`Reminder set: ${relativeWhen(reminder.due_at)}.`);
      pushBinPairUndo("Reminder set", `/reminders/${reminder.id}`, `/reminders/${reminder.id}/restore`, true, loadReminders);
    } catch (error) {
      toast(`The reminder was not set: ${error.message}`, true);
    }
  }

  function renderWbObjects(canvas, stackRank = wbStackRanks()) {
    wbScheduleStickyDates();

    // Shared by both `objDrag` (bound to the whole `.wb-object`) and
    // `gripDrag` (bound only to `.wb-object-grip`, see below): `this` is
    // whichever element the gesture actually started on, so every DOM write
    // goes through `this.closest(".wb-object")` rather than `this` directly,
    // the same convention `resizeDrag`'s own "drag" handler already uses.
    function objDragStart(event, d) {
      if (window.currentTool === "eraser" || window.currentTool === "delete" || window.currentTool === "bucket") return;
      // A link tool on a text box starts a *link* from it, through the same
      // three handlers the cards use, see `wbLinkItem`.
      if (window.currentTool?.startsWith("link-")) { d._linkKind = "object"; return dragStart.call(this, event, d); }
      d._linkedSketches = wbLinkedSketchesFor(d.id, "object");
      // A map node's tree edges are not sketches (see `wbMapEdgesFor`), so the
      // line above finds none of them: collected here for the same reason and
      // at the same moment.
      d._mapEdges = wbMapEdgesFor(d.id);
      // `.raise()` deliberately does NOT happen here, moved to objDragMove.
      // See the matching comment on the card drag's own `dragging` for the
      // real bug this caused (raising mid-`start` breaks the browser's click
      // synthesis, so a plain click-to-select on an object never fired).
      // See the matching comment on the card drag's own `dragStart`: a raw,
      // never-snapped running position, so small per-frame deltas actually
      // accumulate instead of being rounded away against the previous
      // frame's already-snapped value.
      d._rawX = d.x;
      d._rawY = d.y;
      d._dragOriginX = d.x;
      d._dragOriginY = d.y;
      d._raised = false;
      d._moveUndoBefore = WB_KIND_INFO.object.payload(d);
      d._altCopy = Boolean(event.sourceEvent?.altKey);
      d._gesture = wbBeginGesture(() => wbRestoreMove("object", d), true);
      // Bulk-move detection deliberately waits for the first real
      // "drag" frame below, not decided here, see the matching comment on
      // the sketch drag's own "start" for the click-toggle bug that caused.
    }
    function objDragMove(event, d) {
      if (window.currentTool === "eraser" || window.currentTool === "delete" || window.currentTool === "bucket") return;
      if (window.currentTool?.startsWith("link-")) return dragging.call(this, event, d);
      if (d._gesture?.cancelled) return;
      const step = wbTouchSlopStep(d._gesture, event);
      if (!step) return;
      if (d._bulkOrigin === undefined) {
        //: **A map node drags its branch with it** (MINDMAP_PLAN.md §12.1 item
        //: 8). Decided on the first real drag frame, like the marquee case
        //: beside it and for the same reason (see the sketch drag's own "start"
        //: comment): deciding at `start` turns a click into a bulk move.
        //: Ctrl held means the topic travels alone, and is read here because
        //: that is the frame the decision is made in.
        d._dragAlone = Boolean(event.sourceEvent?.ctrlKey || event.sourceEvent?.metaKey);
        d._bulkOrigin = wbDragIsBulkMove("object", d.id)
          ? wbCaptureBulkMoveOrigin(wbMultiKey("object", d.id))
          : wbMapBranchDragOrigin(d, d._dragAlone) || wbFrameDragOrigin(d, d._dragAlone);
      }
      //: Once per gesture, not once per move: the card drag beside this one
      //: took the same fix (INBOX 114, and see its own comment). `raise()`
      //: reappends the element even when it is already last, and a DOM move
      //: invalidates layout, so every frame's first `getBoundingClientRect`
      //: (the drop target's, below) paid for a full re-layout of the board.
      if (!d._raised) {
        d3.select(this.closest(".wb-object")).raise();
        d._raised = true;
      }
      // d3.drag's dx/dy are raw screen pixels, not board-space, the
      // resize handles below already divide by the zoom scale for exactly
      // this reason; a plain drag has to as well, or a card/object moves
      // faster than the cursor when zoomed out and slower when zoomed in.
      const transform = d3.zoomTransform(wbInstances.container());
      d._rawX = (d._rawX ?? d.x) + step.dx / transform.k;
      d._rawY = (d._rawY ?? d.y) + step.dy / transform.k;
      const bypassSnap = event.sourceEvent?.altKey;
      //: **Snapped by how far it moved, not by where it is** (the owner:
      //: "dragging a objects doesnt stay on the mouse and goes off to the side
      //: of where my mouse was on the object when I started dragging it").
      //: Rounding the absolute position means an item that was not already on a
      //: grid line jumps up to half a cell the instant the drag begins and then
      //: stays that far from the cursor for the rest of it: the item is under
      //: your pointer when you press and beside it when you move. Rounding the
      //: *delta* keeps the grab point exactly where you took hold of it and
      //: still moves in whole grid steps, and for the ordinary case (an item
      //: that is already on the grid, because it was placed or dragged with
      //: snap on) the two are the same number.
      //: Shift keeps the move on one axis (see `wbAxisLock`).
      const lock = wbAxisLock(d._rawX - d._dragOriginX, d._rawY - d._dragOriginY, event.sourceEvent?.shiftKey);
      d.x = d._dragOriginX + (lock === "y" ? 0 : wbSnap(d._rawX - d._dragOriginX, bypassSnap));
      d.y = d._dragOriginY + (lock === "x" ? 0 : wbSnap(d._rawY - d._dragOriginY, bypassSnap));
      // Smart alignment guides: asked for directly ("draw.io and Microsoft
      // PowerPoint have... dotted alignment rule guides"). Same Alt bypass as
      // grid-snap just above: holding it means "no snap assistance at all
      // for this drag", one concept, not two separate modifier keys to learn.
      if (!bypassSnap) {
        //: The group's own box when several things are moving, the item's when
        //: one is. Either way the delta lands on `d`, and `wbApplyBulkMove`
        //: below carries the rest of the selection by the same amount.
        const group = wbBulkGroupBox(d, "object");
        const own = wbRotatedBounds(d.x, d.y, d.width, d.height, wbItemRotation("object", d));
        const { dx, dy, guideLines } = wbAlignmentGuides(
          wbDragExcludeKeys(d, "object"),
          group ? group.x : own.x,
          group ? group.y : own.y,
          group ? group.w : own.w,
          group ? group.h : own.h,
          wbAlignTol()
        );
        if (lock !== "y") d.x += dx;
        if (lock !== "x") d.y += dy;
        wbShowAlignmentGuides(guideLines);
      } else {
        wbClearAlignmentGuides();
      }
      d3.select(this.closest(".wb-object")).style("transform", wbItemTransform(d));
      //: The branch first and this topic's own lines after it, for the reason
      //: `wbApplyBulkMove` gives: a line drawn before its other end has moved
      //: is a line a frame behind.
      if (d._bulkOrigin) wbApplyBulkMove(d._bulkOrigin, d.x - d._dragOriginX, d.y - d._dragOriginY);
      if (d._linkedSketches?.length) wbUpdateLinkedSketches(d.id, d._linkedSketches);
      if (d._mapEdges?.length) wbUpdateMapEdges(d._mapEdges);
      wbQueueSelectionBar();
      // The topic this branch would land on, lit as you pass over it. From the
      // pointer's own position rather than the node's, because what you aim at
      // is where you are pointing, not where the box has caught up to.
      const source = event.sourceEvent;
      if (source && wbIsMap() && WB_MAP_KINDS.has(d.kind)) {
        d._dropTarget = wbMapDropTargetAt(d, source.clientX, source.clientY);
        wbMapShowDropTarget(d._dropTarget?.id ?? null);
        //: Not over a topic: a gap among its siblings, where the layout stacks
        //: them. One topic only: a group drag stays a placement.
        d._siblingSlot = d._dropTarget || d._dragAlone || d._bulkOrigin ? null : wbMapSiblingSlotAt(d, source.clientX, source.clientY);
        wbMapShowSlotCue(d._siblingSlot);
      }
    }
    async function objDragEnd(event, d) {
      if (window.currentTool === "eraser" || window.currentTool === "delete" || window.currentTool === "bucket") return;
      if (window.currentTool?.startsWith("link-")) { const r = dragEndNode.call(this, event, d); d._linkKind = null; return r; }
      //: Dropped on the delete target: put back, then deleted (INBOX 660).
      wbTrashTake(d._gesture, "object", d);
      d._linkedSketches = null;
      // Dropped: the paths this drag held references to are about to be
      // replaced by the next render, and a stale element would be updated in
      // place forever (invisibly, since it is no longer in the document).
      d._mapEdges = null;
      wbClearAlignmentGuides();
      const bulkOrigin = d._bulkOrigin;
      // Reset unconditionally: a solo drag sets this to `null` (see
      // "drag" above), and leaving it there would make the *next* gesture's
      // `=== undefined` check think bulk-move was already decided and skip
      // redetecting it, permanently treating this object as "never bulk"
      // even after it later joins a multi-selection.
      delete d._bulkOrigin;
      //: Dropped on another topic: that is a transplant, not a placement, and
      //: it replaces the ordinary save below entirely (`/move` is the only
      //: endpoint that may write `parent_id`, and it re-lays the branch after).
      const dropTarget = d._dropTarget;
      const slot = d._siblingSlot;
      delete d._siblingSlot;
      const alone = d._dragAlone;
      delete d._dropTarget;
      delete d._dragAlone;
      wbMapClearDropTarget();
      const altCopy = d._altCopy;
      delete d._altCopy;
      if (wbEndGesture(d._gesture)) {
        delete d._gesture;
        delete d._moveUndoBefore;
        return;
      }
      delete d._gesture;
      if (dropTarget) {
        //: Where the branch was picked up, so the transplant's one Undo puts it
        //: back there rather than where it was let go (INBOX 410).
        const before = new Map();
        if (d._moveUndoBefore) before.set(d.id, { x: d._moveUndoBefore.x, y: d._moveUndoBefore.y });
        for (const entry of bulkOrigin?.values() || []) {
          if (entry.kind === "object" && !before.has(entry.id)) before.set(entry.id, { x: entry.x, y: entry.y });
        }
        delete d._moveUndoBefore;
        if (bulkOrigin) await wbSaveBulkMove(bulkOrigin);
        await wbMapTransplant(d, dropTarget.id, alone, { before });
        return;
      }
      if (slot) {
        const origins = new Map();
        if (d._moveUndoBefore) origins.set(d.id, { x: d._moveUndoBefore.x, y: d._moveUndoBefore.y });
        for (const entry of bulkOrigin?.values() || []) {
          if (entry.kind === "object" && !origins.has(entry.id)) origins.set(entry.id, { x: entry.x, y: entry.y });
        }
        delete d._moveUndoBefore;
        await wbMapDropAmongSiblings(d, slot, origins);
        return;
      }
      const moveBefore = d._moveUndoBefore;
      delete d._moveUndoBefore;
      //: **A click is not a drop, and must not save.** `objDrag` runs for a
      //: plain click too (d3-drag listens for `mousedown`, and a click is a
      //: mousedown with no movement), and this used to PUT the object every
      //: time regardless. On its own that is only a wasted request; the bug is
      //: that the PUT carries whatever `d.data` held when the gesture ended,
      //: and a click on a control *inside* the node (the chevron, the count
      //: badge, the two add buttons) fires its own save in the same tick. Two
      //: PUTs to one row with no defined order: measured on the fold chevron,
      //: one click sent `collapsed: null` and `collapsed: true` and the map
      //: kept whichever landed second, so a branch folded on screen and came
      //: back unfolded on the next refresh. Found by `mindmap.js`'s SVG export
      //: check, which counted two edges where the map had four.
      //:
      //: The same "did it really move" test the undo entry below already used,
      //: hoisted above the save so it governs both.
      const reallyMoved = !moveBefore || moveBefore.x !== d.x || moveBefore.y !== d.y;
      if (reallyMoved) await wbSaveObject(d);
      if (d._unsaved) {
        //: A drop that could not be saved (offline, or the item is gone) goes back where it was taken
        //: from, with a word, rather than staying where the server does not have it (`_unsaved`, set by
        //: the save's catch).
        delete d._unsaved;
        if (moveBefore) Object.assign(d, { x: moveBefore.x, y: moveBefore.y });
        wbScheduleRender();
        toast(voiceLine("failed", "save the move", "the item went back where it was"), true, { action: ["Reload the board", () => fetchWhiteboardState().then(wbScheduleRender)] });
        return;
      }
      const primary = moveBefore && reallyMoved
        ? { action: "move", kind: "object", id: d.id, before: moveBefore }
        : null;
      await wbFinishDrag(primary, bulkOrigin, altCopy);
      // A map node that was actually moved is now pinned, see
      // `wbMapPinOnDrag`. Gated on the same "did it really move" check the
      // undo entry uses, so a click is never mistaken for a placement.
      if (primary) await wbMapPinOnDrag(d);
    }

    const objDrag = d3.drag()
      // A resize handle owns its own drag (below); a text box's own text
      // needs plain clicks/selection to reach it, not a canvas-wide drag. And,
      // same reasoning as the card drag's own filter above: a brush tool must
      // be able to draw over an image/text object, not drag it. `.wb-object-grip`
      // has its own separate drag instance (`gripDrag`, below): excluded here
      // so a grip grab doesn't *also* start this instance for the same
      // gesture. A real bug caught live: excluding it here alone isn't enough
      //, `objDrag` is one shared behaviour object bound to both the object
      // and the grip, so its filter runs for *both* elements' own pointerdown,
      // and target-closest can't tell "the grip's own listener" from "the
      // object's listener catching a bubbled grip click" apart. `gripDrag`
      // below exists precisely because that distinction needs two behaviour
      // objects, not one filter.
      .filter((event) => {
        //: **The primary button only** (the owner, 2026-09-24: the middle-button
        //: pan "jerks"). d3-drag's own default filter is `!event.button`, and
        //: writing a filter replaces it rather than adding to it, so this one
        //: took every button: a middle press on a topic or a card started a
        //: drag of that item and stopped the event before the board's pan ever
        //: saw it (measured, `midpanwheel.js`: a 200px middle drag started on
        //: the root moved the board 0px). The middle button is the pan from
        //: anywhere, which is what `wbZoomFilter` promises.
        if (event.button || wbIsSecondTouch(event)) return false;
        if (WB_BRUSH_TOOLS.has(window.currentTool) || window.currentTool === "lasso") return false;
        if (event.target.closest(
          ".wb-resize-handle, .wb-rotate-handle, .wb-object-grip"
          + ", .wb-map-resize-grip"
        )) return false;
        // `.wb-text-content` used to be excluded outright, which is what left a
        // text box draggable only by its grip, see `wbBeginTextEdit`. It only
        // needs to keep the pointer while it is *being edited*, for the caret
        // and for selecting words; the rest of the time it is just the face of
        // a box and drags like one.
        //
        // **Asked for by class, this missed the map node entirely.** Reported:
        // "I cant highlight text in mindmap text boxes." A map node's editor is
        // `.wb-map-text`, not `.wb-text-content`, so this filter let the drag
        // run: measured, a click-drag across a node being edited selected the
        // empty string and moved the node 165px instead. The node's own
        // `pointerdown` stopPropagation cannot help, d3-drag listens for
        // `mousedown`, and this file already records that two event families
        // cannot cancel each other (see the marquee's handle-layer comment).
        // Asking the *element* whether it is editable rather than naming the
        // classes that happen to be editable today is what stops the next
        // editable surface on the canvas from re-learning this.
        const text = event.target.closest("[contenteditable]");
        if (text && text.isContentEditable) return false;
        return true;
      })
      .on("start", objDragStart)
      .on("drag", objDragMove)
      .on("end", objDragEnd);

    // The grip's own drag instance (see the comment above), `stopPropagation`
    // on start is the same fix `resizeDrag`/`objectRotateDrag` already use to
    // keep their own handle grabs from also bubbling into the object's own
    // `objDrag` listener.
    const gripDrag = d3.drag()
      // The grip sits inside the box it moves, see `wbStableDragContainer`.
      .container(wbStableDragContainer(".wb-object"))
      .filter((event) => !wbIsSecondTouch(event) && !event.button && !WB_BRUSH_TOOLS.has(window.currentTool) && window.currentTool !== "lasso")
      .on("start", function (event, d) {
        event.sourceEvent.stopPropagation();
        objDragStart.call(this, event, d);
      })
      .on("drag", objDragMove)
      .on("end", objDragEnd);

    function resizeDrag(handle) {
      return d3.drag()
        // The handle sits inside the object it resizes, see
        // `wbStableDragContainer`. Matters for `w`/`n`, which move x/y too.
        .container(wbStableDragContainer(".wb-object"))
        .on("start", function (event, d) {
          event.sourceEvent.stopPropagation(); // don't also start objDrag
          d._resizeUndoBefore = WB_KIND_INFO.object.payload(d);
          //: From where the gesture began rather than frame on frame, like the
          //: card's resize: a proportion held with Shift is a proportion of the
          //: box you took hold of, and a per-frame delta has no memory of it.
          d._resizeStart = { x: d.x, y: d.y, w: d.width, h: d.height, dx: 0, dy: 0 };
          d._linkedSketches = wbLinkedSketchesFor(d.id, "object");
          d._gesture = wbBeginGesture(() => wbRestoreBox("object", d, d._resizeUndoBefore));
        })
        .on("drag", function (event, d) {
          const start = d._resizeStart;
          if (!start || d._gesture?.cancelled) return;
          const transform = d3.zoomTransform(wbInstances.container());
          start.dx += event.dx / transform.k;
          start.dy += event.dy / transform.k;
          const box = wbResizeBox(start, handle, start.dx, start.dy,
            event.sourceEvent.shiftKey || wbKeepsRatio("object", d), event.sourceEvent.altKey, WB_OBJECT_MIN_SIZE);
          let newWidth = box.w, newHeight = box.h, newX = box.x, newY = box.y;
          if (!event.sourceEvent.shiftKey && !event.sourceEvent.altKey) {
            ({ width: newWidth, height: newHeight } = wbGuidedResize("object", d, handle, start, newWidth, newHeight, { off: false }));
            newX = handle.includes("w") ? start.x + start.w - newWidth : start.x;
            newY = handle.includes("n") ? start.y + start.h - newHeight : start.y;
          } else {
            //: Shift (keep the ratio) and Alt (no guides) skip the guided
            //: resize, which is what draws the size readout; it shows anyway.
            wbShowAlignmentGuides([]);
            wbShowSizeReadout({ x: newX, y: newY, w: newWidth, h: newHeight });
          }
          d.x = newX;
          d.y = newY;
          d.width = newWidth;
          d.height = newHeight;
          const el = d3.select(this.closest(".wb-object"));
          el.style("width", `${d.width}px`)
            .style("height", `${d.height}px`)
            .style("transform", wbItemTransform(d));
          //: A sticker's glyph is its box (decision 44), so it grows with the
          //: grip, not on the next render (the 22-10 bug doc: "Emojis don't
          //: size or scale with its borders").
          if (d.data?.sticker) el.select(".wb-text-content").style("font-size", `${wbStickerSize(d)}px`);
          //: **The lines and the clone arrows follow a resize as they follow a
          //: move** (INBOX 746's "the arrows dont resize either"). The box a
          //: link aims at is read from the measured size the last render
          //: cached, so that entry goes first; without both lines a stretched
          //: sticky kept its links ending where its old sides were until the
          //: next render (measured 14.7 and 48 board units off the outline).
          wbMapNodeSizeCache?.delete(d.id);
          if (d._linkedSketches?.length) wbUpdateLinkedSketches(d.id, d._linkedSketches);
          wbQueueSelectionBar();
        })
        .on("end", async (event, d) => {
          wbClearAlignmentGuides();
          delete d._resizeStart;
          delete d._linkedSketches;
          const before = d._resizeUndoBefore;
          delete d._resizeUndoBefore;
          const cancelled = wbEndGesture(d._gesture);
          delete d._gesture;
          if (cancelled || (before && before.width === d.width && before.height === d.height)) return;
          await wbSaveObject(d);
          if (before) wbPushUndo({ action: "move", kind: "object", id: d.id, before });
          //: The save repaints nothing, and what a box draws from its size (a
          //: sticker's glyph, a frame's title, a table's grid) waited for some
          //: later render to catch up.
          wbScheduleRender();
        });
    }

    //: Same as `nodeRotateDrag` above: kept as two small copies rather than
    //: one shared function because they close over different elements/PUT
    //: helpers (`.node-card` vs `.wb-object`, `wbSaveNode` vs `wbSaveObject`),
    //: the same reasoning `nodeResizeDrag`'s own comment already gives for not
    //: sharing with `resizeDrag`.
    function objectRotateDrag() {
      //: Not d3's default filter, which refuses a Ctrl press: Ctrl is how a
      //: frame is turned without what it holds.
      return d3.drag()
        .clickDistance(WB_CLICK_SLOP)
        .filter((event) => !event.button)
        .on("start", (event, d) => {
          event.sourceEvent.stopPropagation();
          d._rotateUndoBefore = WB_KIND_INFO.object.payload(d);
          //: The links touching it, found once: a turn moves their endpoints
          //: as much as a move does, and without this they stayed where the
          //: unturned box had them until the next move (INBOX 647).
          d._linkedSketches = wbLinkedSketchesFor(d.id, "object");
          //: Decided here, not per frame: the set a turn carries is the set
          //: inside the frame when the grip was taken.
          const alone = Boolean(event.sourceEvent.ctrlKey || event.sourceEvent.metaKey);
          d._turnFrom = d.rotation || 0;
          d._turnOrigin = wbFrameTurnOrigin(d, alone);
          d._gesture = wbBeginGesture(() => {
            wbRestoreBox("object", d, d._rotateUndoBefore);
            wbFrameTurnRevert(d);
          });
        })
        .on("drag", (event, d) => {
          if (d._gesture?.cancelled) return;
          const el = wbInstances.query(`.wb-object[data-id="${d.id}"]`);
          if (!el) return;
          const rect = el.getBoundingClientRect();
          d.rotation = wbAngleFromCenterDeg(
            rect.left + rect.width / 2, rect.top + rect.height / 2,
            event.sourceEvent.clientX, event.sourceEvent.clientY,
            event.sourceEvent.shiftKey
          );
          el.style.transform = wbItemTransform(d);
          wbFrameTurnLive(d);
          if (d._linkedSketches?.length) wbUpdateLinkedSketches(d.id, d._linkedSketches);
          wbQueueSelectionBar();
        })
        .on("end", async (event, d) => {
          const before = d._rotateUndoBefore;
          delete d._rotateUndoBefore;
          delete d._linkedSketches;
          const cancelled = wbEndGesture(d._gesture);
          delete d._gesture;
          if (cancelled || (before && (before.rotation || 0) === (d.rotation || 0))) {
            wbFrameTurnRevert(d);
            return;
          }
          await wbSaveObject(d);
          wbFmtState.keys?.record({ kind: "turn", deg: (d.rotation || 0) - (before?.rotation || 0) });
          if (!d._turnOrigin) {
            if (before) wbPushUndo({ action: "move", kind: "object", id: d.id, before });
            return;
          }
          await wbFrameTurnEnd(d, before && { action: "move", kind: "object", id: d.id, before });
        });
    }

    // The map facts for this render pass, computed once here rather than per
    // node: `wbMapColors` walks the whole tree by design (see its own comment),
    // and calling it from inside a per-node callback would walk it once per node.
    const mapIndex = wbIsMap() ? wbMapIndex() : null;
    //: Each topic's level (MINDMAP_PLAN.md decision 38), before anything is
    //: painted or measured: its look, and so its size, depend on it.
    if (mapIndex) wbMapLevels(mapIndex);
    const mapColors = mapIndex ? wbMapNodeColors(mapIndex) : null;
    const mapFills = mapIndex ? wbMapFills(mapIndex) : null;
    const mapHidden = mapIndex ? wbMapConcealed(mapIndex) : null;
    // The focus bar's counts, the legend's rows and the template offer all
    // describe the map this pass is about to draw (§5 items 18 to 21).
    wbSyncMapViews(mapIndex);
    // **A collapsed branch leaves the DOM rather than being hidden with CSS.**
    // The export, the board bounds, the marquee and every `querySelector` in
    // this file read the DOM, a `display: none` node would still be found by
    // all four, so a folded branch would keep showing up in exports and keep
    // stretching the board's bounds while being invisible on screen.
    const objectData = mapHidden?.size
      ? (wbState.objects || []).filter((o) => !mapHidden.has(o.id))
      : (wbState.objects || []);
    const objectSelection = canvas.selectAll(".wb-object")
      .data(objectData, (d) => d.id);

    // A map node is `height: auto`, its own text decides how tall it is, so a
    // long topic grows its box instead of being sliced by `overflow: hidden`,
    // which is the failure CLAUDE.md records costing six rounds on one popup.
    const objectHeight = (d) => (WB_MAP_KINDS.has(d.kind) ? "auto" : `${d.height}px`);

    const objectEnter = objectSelection.enter()
      .append((d) => wbMapNodeTakeBack(d) || document.createElement("div"))
      .attr("class", (d) => `wb-object wb-object-${d.kind}`)
      .attr("data-id", (d) => d.id)
      .style("transform", wbItemTransform)
      .style("width", (d) => `${(WB_MAP_KINDS.has(d.kind) && wbMapNodeSize.narrow(d)) || d.width}px`)
      .style("height", objectHeight)
      .style("z-index", (d) => stackRank.get(`object:${d.id}`))
      .call(objDrag)
      .on("click", (event, d) => {
        // ROADMAP row 0(b), asked for directly: with the Hand active, a plain
        // click on something switches to Select and selects it. A pan is a
        // drag; a click that moved nothing is a choice of *this*, and every
        // whiteboard app (Miro, FigJam, tldraw) reads it that way.
        if (window.currentTool === "select" || window.currentTool === "pan") {
          event.stopPropagation();
          if (window.currentTool === "pan") wbSelectToolRef?.("select");
          wbHandleItemClick("object", d.id, event);
          return;
        }
        if (window.currentTool === "delete" || window.currentTool === "eraser") wbDeleteObject(d);
      })
      .on("pointerenter", (event, d) => {
        if (window.currentTool === "eraser" && wbErasing) wbDeleteObject(d);
      });

    objectEnter.each(function (d) {
      const el = d3.select(this);
      //: A topic coming back out of a fold keeps the body it was built with
      //: (`wbMapNodeTakeBack`): its handlers close over this same datum. The
      //: class line above reset its classes, so the one the build adds goes
      //: back on, and the paint below runs in full because its key is gone.
      if (this._wbTakenBack) {
        delete this._wbTakenBack;
        el.classed("wb-map-node", true);
        this._wbPaintKey = undefined;
        return;
      }
      if (d.kind === "image") {
        // Asked for directly: an image deleted out from under a board (via
        // the Library gallery's own delete, or by hand off disk) left a
        // plain broken-image glyph: "there should probably be a placeholder
        // or closable box that says it is deleted in its place." The close
        // button removes the object outright rather than leaving a
        // permanently-broken box on the board.
        el.append("img").attr("src", mediaSrc(d.data.url) || "").attr("alt", "")
          .on("error", function () {
            d3.select(this).remove();
            if (el.select(".wb-object-deleted").empty()) {
              const placeholder = el.append("div").attr("class", "wb-object-deleted");
              placeholder.append("span").text("Image deleted");
              placeholder.append("button")
                .attr("type", "button")
                .attr("class", "ghost small icon-button")
                .attr("title", "Remove this")
                .attr("aria-label", "Remove this")
                //: `setLabel`, not `.text("\u2715")`: a typed cross renders in
                //: the page font at the text's own weight beside Phosphor icons
                //: everywhere else in this bar. d3 has no icon idiom, so the
                //: element is handed to the app's own one.
                .each(function () { setLabel(this, "ph:x"); })
                .on("click", (event) => { event.stopPropagation(); wbDeleteObject(d); });
            }
          });
      } else if (d.kind === "frame") {
        wbBuildFrame(el, d);
      } else if (d.kind === "table") {
        wbBuildTable(el, d);
      } else if (d.kind === "diagram") {
        wbBuildDiagram(el, d);
      } else if (WB_MAP_KINDS.has(d.kind)) {
        // A map node, not a text box. Checked before the `else` below because
        // that branch is "everything that isn't an image", which is what drew a
        // topic as a bare, unlabelled text box for as long as the kinds existed
        // without this: stored, served, and on screen as nothing recognisable.
        wbBuildMapNode(el, d);
      } else {
        // Fill/border, asked for directly (the properties panel): set on the
        // outer object div, which is what `.wb-object-text`'s own default
        // background/border style, so an unset value falls back to the CSS
        // default rather than an empty override.
        el.style("background", wbPaperPaint(d.data)).style("border-color", d.data.border_color || "");
        // Asked for directly ("objects are also difficult and annoying to
        // move around"): `.wb-text-content` fills the entire box and both
        // the filter above and its own pointerdown handler below correctly
        // keep drag away from it while typing, which meant the *only*
        // draggable surface left was the ~0.5rem padding strip around the
        // text, the same width as the resize handles that sit right on top
        // of it. A dedicated grip, same convention as the panels' own
        // `.wb-panel-grip`, gives a guaranteed, adequately-sized place to
        // grab regardless of how much text is in the box. Text objects only: 
        // an image has no competing contenteditable claim on its body, so it
        // was already fully draggable once the resize-handle bug above was
        // fixed.
        el.append("div")
          .attr("class", "wb-object-grip")
          .attr("title", "Drag to move")
          .text("⠿")
          .call(gripDrag);
        const content = el.append("div")
          .attr("class", "wb-text-content")
          // Not editable until asked, see `wbBeginTextEdit` for why.
          .attr("contenteditable", "false")
          .style("color", d.data.color ? wbReadableInk(d.data.color, d.data.bg || wbBoardBg()) : "")
          .style("font-size", d.data.font_size ? `${d.data.font_size}px` : "")
          .text(d.data.content || "");
        // Saved on blur, not on every keystroke, a PUT per character would
        // flood the server and make undo/redo of everything *else* land
        // between two half-typed states.
        content.on("blur", function () {
          wbEndTextEdit(this);
          const edited = wbEditedText(this);
          //: Unchanged: nothing to save or record, but the box still goes back
          //: from its raw source to the rendered view.
          //: Formatted from the selection bar or Ctrl+B: shown rendered (K24).
          const formatted = this.dataset.wbFormatted === "1";
          delete this.dataset.wbFormatted;
          const grownFrom = this.wbBeforeGrow;
          delete this.wbBeforeGrow;
          if (d.data.content === edited) {
            if (grownFrom) {
              wbPushUndo({ action: "move", kind: "object", id: d.id, before: grownFrom });
              wbSaveObject(d);
            }
            wbScheduleRender();
            return;
          }
          wbPushUndo({ action: "move", kind: "object", id: d.id, before: grownFrom || WB_KIND_INFO.object.payload(d) });
          d.data = formatted ? { ...d.data, content: edited, md: true } : { ...d.data, content: edited };
          wbGrowBoxToWords(this, d);
          wbSaveObject(d);
          //: A formatted edit is shown rendered (K24), and nothing else asked for
          //: that: the box kept its raw `**x**` or `{{size=24|x}}` source on
          //: screen until some other change repainted the board.
          if (formatted) wbScheduleRender();
        });
        content.on("input", function () {
          if (this.isContentEditable) wbGrowBoxToWords(this, d);
        });
        // Typing is text-box business, not the canvas's: Delete/Backspace
        // here must edit the text, not delete the whole box the way the same
        // keys do when an object is merely *selected*. Both of these are gated
        // on actually being in edit mode now: a box that is not being edited
        // has to let the pointer through to the object's own drag, and its
        // Delete key belongs to the canvas again.
        content.on("keydown", function (event) {
          if (!this.isContentEditable) return;
          event.stopPropagation();
          //: **Escape ends the edit and leaves the box selected** (INBOX 445),
          //: what Excalidraw, tldraw and Figma all do. The line above stopped
          //: every key, Escape with them, so the caret stayed in the box after
          //: Escape and the next tool letter (T, R) was typed into the sticky
          //: instead of picking the tool. Blurring runs the save above.
          if (event.key === "Escape") {
            event.preventDefault();
            this.blur();
            selectWbItem("object", d.id);
            wbInstances.container()?.focus({ preventScroll: true });
            return;
          }
          if (event.key === "Tab" && !event.ctrlKey && !event.altKey && !event.metaKey) {
            if (wbIndentEditableLines(this, event.shiftKey)) event.preventDefault();
          }
          if (wbTextFormatKey(event)) return;
          //: **Sticky chain** (WHITEBOARD_PLAN gap row 6, Miro's Tab): Ctrl+Enter
          //: ends this sticky and starts the next beside it, same paper and size.
          //: Not Tab, which indents a sticky's lines here.
          if (event.key === "Enter" && (event.ctrlKey || event.metaKey) && wbIsSticky(d)) {
            event.preventDefault();
            this.blur();
            wbCreateSticky(0, 0, { x: d.x + d.width + 24, y: d.y, w: d.width, h: d.height }, d);
          }
        });
        content.on("pointerdown", function (event) {
          if (this.isContentEditable) event.stopPropagation();
        });
        content.on("dblclick", function (event) {
          event.stopPropagation();
          if (wbJustDrilled()) return;
          wbBeginTextEdit(this);
        });
      }
      // A map node gets neither. Its height is its text's (see `objectHeight`),
      // so a vertical resize handle would fight the content and lose; and a
      // rotated node is a node whose edges no longer meet its anchors, which
      // makes the tree unreadable for no gain a mind-mapper has ever asked for.
      // The eight handles and the rotate grip also sit exactly where the
      // chevron and the `+` do, and would swallow both.
      if (WB_MAP_KINDS.has(d.kind)) return;
      wbArmHandles(this, () => wbBuildObjectHandles(el, d.kind));
    });

    //: The eight sizes and the turn grip of one object, built on first need
    //: (`wbArmHandles`).
    function wbBuildObjectHandles(el, kind) {
      for (const handle of ["nw", "n", "ne", "e", "se", "s", "sw", "w"]) {
        el.append("div")
          .attr("class", "wb-resize-handle")
          .attr("data-handle", handle)
          //: **The gesture says it exists.** The rotate grip beside these has
          //: carried a title explaining its own modifier since it was built;
          //: these had none, so double-tapping to fit was real and invisible,
          //: which is indistinguishable from missing and was duly reported as
          //: missing.
          .attr("title", wbResizeHandleTitle(kind))
          .call(resizeDrag(handle));
      }
      //: A table's grid holds nothing square once turned. A frame does turn
      //: (INBOX 1327, reversing decision 14's "no rotation"), and what lies
      //: wholly inside it turns with it (decision 42, `wbFrameTurnOrigin`).
      if (kind === "table") return;
      el.append("div")
        .attr("class", "wb-rotate-handle")
        .attr("title", wbRotateGripTitle(kind))
        .call(objectRotateDrag());
    }

    wbWireContextMenu(objectEnter, "object");

    const objectUpdate = objectEnter.merge(objectSelection);
    //: **A render repaints the objects that changed, not every object on the
    //: board** (MINDMAP_PLAN.md §13a, the render pass). The four `.style` calls
    //: this replaces ran for every object on every render, and the `.each`
    //: below them repainted every map node whether or not anything about it had
    //: moved: at 500 topics that was 2,000 style writes and 500 full node
    //: repaints for a change to one of them.
    //:
    //: The key is every input this pass reads, in one string. An object whose
    //: key is what it was last render draws exactly what it is already
    //: drawing, so the cheapest correct thing to do with it is nothing. A fresh
    //: element (the enter selection) has no key at all, so it always paints.
    //: `wbObjectPaintKey` is the one list of those inputs: a property this pass
    //: starts reading has to go into it, and the way that failure shows is a
    //: node that stops following a change, which is what `mapstrip.js`,
    //: `maptheme.js`, `mapline.js` and `maprejoin.js` each ask about directly.
    const paintCtx = {
      index: mapIndex,
      colors: mapColors,
      //: A fill can come from an ancestor, so a topic whose own data did not
      //: change can still need repainting when its branch is filled.
      fills: mapFills,
      //: Read once for the pass, not once per node: both are board-wide, and
      //: `wbMapThemedData` merges the theme underneath every node's own data.
      layout: mapIndex ? wbMapLayout() : "",
      theme: mapIndex ? JSON.stringify(wbMapTheme()) : "",
      fold: wbBoardBackground().sticky_fold !== false,
    };
    // An image's own src can change (rare: nothing in this UI replaces one
    // yet, but a future paste-to-replace shouldn't need this rewritten) and a
    // text box's saved colour/size might have changed elsewhere (undo/redo);
    // the text itself is deliberately left alone here so a re-render mid-edit
    // (another item moving, say) can't overwrite what's being typed.
    //: **Moves are written after the measure, and only what was repainted is
    //: measured** (FEAT-02's 100ms gate). A tidy that shifts two hundred topics
    //: wrote two hundred transforms here, and the measure's first
    //: `offsetHeight` then restyled all of them before reading one height
    //: (traced: 37 to 63ms, 1,260 elements, on every Tab at 301 topics). A
    //: move changes no size, so the measure now reads only the topics this
    //: pass repainted, with nothing else dirty yet, and the moves are written
    //: after it, to be restyled once with the rest of the frame.
    const movesLater = [];
    const repainted = new Set();
    objectUpdate.each(function (d) {
      //: Before the paint-key skip: another item's order command moves this
      //: one's rank without changing anything this one would repaint.
      //: Kept on the element: this pass and the enter above are the only writers of an object's z-index, and
      //: reading it back off `style` cost 0.6 ms for 500.
      const rank = stackRank.get(`object:${d.id}`) ?? "";
      if (this._wbRank !== rank) {
        this.style.zIndex = String(rank);
        this._wbRank = rank;
      }
      const key = wbObjectPaintKey(d, paintCtx);
      //: **A move is a transform, not a repaint** (audit FEAT-02): the key left
      //: out x and y so a tidy that shifts two hundred topics down for one new
      //: one writes two hundred transforms, not two hundred full repaints
      //: (measured: 409ms of `setAttribute` in one Tab at 301 topics).
      if (this._wbPaintKey === key) {
        const place = wbItemTransform(d);
        if (this.style.transform !== place) movesLater.push([this, place]);
        return;
      }
      repainted.add(this);
      this._wbPaintKey = key;
      //: Drawn live for this pass, so the measure below reads what the new
      //: content really needs rather than the size it was culled at. The next
      //: cull (queued at the end of the render) puts it back if it is still
      //: off screen.
      if (this.classList.contains("wb-culled")) this.classList.remove("wb-culled");
      const el = d3.select(this);
      this.style.transform = wbItemTransform(d);
      this.style.width = `${(WB_MAP_KINDS.has(d.kind) && wbMapNodeSize.narrow(d)) || d.width}px`;
      this.style.height = objectHeight(d);
      if (!WB_MAP_KINDS.has(d.kind)) {
        this.style.opacity = d.data?.alpha != null && d.data.alpha < 1 ? String(d.data.alpha) : "";
        this.style.filter = wbShadowCss(d.data) || "";
        this.style.borderRadius = Array.isArray(d.data?.radii) ? d.data.radii.map((r) => `${r}px`).join(" ") : "";
        if (d.kind === "text") this.style.padding = d.data?.pad != null ? `${d.data.pad}px` : "";
        wbPaintVotes(this, d);
      }
      if (d.kind === "image") {
        const pix = wbPixel(d.data, d.width, d.height);
        const turned = pix.turn === 90 || pix.turn === 270;
        //: The border is an outline drawn inside the box, so the picture keeps its size.
        const edge = d.data.border_width > 0 ? d.data.border_width : 0;
        this.style.outline = edge ? `${edge}px solid ${d.data.border_color && d.data.border_color !== "transparent" ? d.data.border_color : "#333333"}` : "";
        this.style.outlineOffset = edge ? `-${edge}px` : "";
        el.select("img").attr("src", mediaSrc(d.data.url) || "").style("border-radius", d.data.radii ? "inherit" : null)
          .style("clip-path", wbCropClip(d.data.crop, d.data.trim) || null)
          .style("transform", pix.transform || null).style("filter", pix.filter || null)
          .style("position", turned ? "absolute" : null).style("left", turned ? "50%" : null).style("top", turned ? "50%" : null)
          .style("width", turned ? `${pix.w}px` : null).style("height", turned ? `${pix.h}px` : null);
      } else if (WB_MAP_KINDS.has(d.kind)) {
        wbPaintMapNode(el, d, mapIndex, mapColors, mapFills);
        //: The topic an add is about to type in is made editable here, before
        //: the measure below reads, so the read is the one flush (`wbBeginTextEdit`).
        const typing = wbAddGate.renderHold?.editId === d.id ? this.querySelector(".wb-map-text") : null;
        if (typing) {
          //: Selected, the old selection let go, in the same pass and before the
          //: editable attribute (which restyles at once): the `selectWbItem` that
          //: follows then finds the classes already right.
          for (const old of wbApplySelectionHighlight.marked || []) old.classList.remove("wb-selected", "wb-in-group");
          this.classList.add("wb-selected");
          (wbApplySelectionHighlight.marked ??= new Set()).add(this);
          wbBeginTextEdit(typing, undefined, true);
        }
      } else if (d.kind === "frame") {
        const title = this.querySelector(".wb-frame-title");
        if (title && !title.isContentEditable) title.textContent = wbFrameTitle(d);
        wbPaintFrame(this, d);
      } else if (d.kind === "table") {
        wbPaintTable(this, d);
      } else if (d.kind === "diagram") {
        wbPaintDiagram(this, d);
      } else {
        const sticky = wbIsSticky(d);
        el.classed("wb-sticky", sticky);
        el.classed("wb-no-fold", sticky && !wbStickyFolds(d));
        //: The paper's colour is the fold's too (`.wb-sticky::after`); a
        //: sticky's edge is its lift, never a drawn border.
        if (sticky) this.style.setProperty("--wb-paper", d.data.bg || WB_STICKY_PAPERS[0].value);
        else this.style.removeProperty("--wb-paper");
        el.style("background", wbPaperPaint(d.data)).style("border-color", sticky ? "" : d.data.border_color || "");
        const textEl = el.select(".wb-text-content");
        //: **A sticker** (MINDMAP_PLAN.md decision 44): an emoji with no card,
        //: its glyph sized to its box, so resizing it is resizing the emoji.
        const sticker = Boolean(d.data.sticker);
        el.classed("wb-sticker", sticker);
        //: Up and down the box (the Format panel's Vertical row): the
        //: stylesheet centres or bottoms the text from this.
        if (d.data.valign === "middle" || d.data.valign === "bottom") this.dataset.valign = d.data.valign;
        else delete this.dataset.valign;
        //: A card with a fill and no ink of its own takes the ink that reads
        //: on that fill (`wbCoreInkFor`), not the theme's: a dark blue card in
        //: the light theme drew dark text on it (the owner at release, the
        //: README's board shot).
        textEl.style("color", d.data.color || (d.data.bg && wbCoreInkFor(d.data.bg)) || "")
          .style("font-size", sticker ? `${wbStickerSize(d)}px` : d.data.font_size ? `${d.data.font_size}px` : "")
          .style("text-align", d.data.align || "")
          .style("line-height", d.data.line_height || "")
          .style("letter-spacing", d.data.letter_spacing ? `${d.data.letter_spacing}px` : "")
          .style("font-weight", d.data.bold ? "700" : "")
          .style("font-style", d.data.italic ? "italic" : "")
          .style("text-decoration", [d.data.underline && "underline", d.data.strike && "line-through"].filter(Boolean).join(" "))
          .style("font-family", WB_ITEM_FONTS[d.data.font_family] || "");
        wbPaintTextDir(textEl.node(), d.data.text_dir, d.data.text_alpha);
        if (document.activeElement !== textEl.node()) wbPaintTextContent(textEl.node(), d);
      }
      wbFmtState.effects?.paintObject(this, d); // a sticky's flip side and its words' shadow (whiteboard-effects.js)
    });

    objectSelection.exit()
      .each(function (d) {
        //: Folded away, not deleted: kept for the expand that brings it back.
        if (mapHidden?.has(d.id) && WB_MAP_KINDS.has(d.kind)) wbMapNodePool.set(d.id, this);
      })
      .remove();
    //: After the enter has taken back what it wanted: a kept element whose
    //: topic is no longer folded away and was not taken back (deleted, or the
    //: board changed under it) is let go.
    for (const id of wbMapNodePool.keys()) {
      if (!mapHidden?.has(id)) wbMapNodePool.delete(id);
    }

    //: **Every topic measured in one pass, after every write, never between
    //: them** (MINDMAP_PLAN.md §13a). This loop used to be the last two lines
    //: of the `.each` above, one `offsetHeight` read per node interleaved with
    //: that node's own style writes. A style write invalidates layout for the
    //: whole document, so each of those reads flushed a fresh layout of the
    //: entire board: 500 nodes cost 500 full layouts, which is where this
    //: render's superlinearity actually lived (renderWbObjects: 405.6ms of a
    //: 527ms render at 500 topics, against 32.1ms for the painting itself).
    //: Reads on their own flush once and are then free, so the same
    //: information now costs one layout.
    //:
    //: The stored `height` is what the bounds, the alignment guides and the
    //: tidy layout all read, and a map node's real height is whatever its text
    //: needed; the value rides along to the server on the node's next real
    //: save. The size cache is filled from the same reads because
    //: `wbRenderMapEdges` runs next and asks for both ends of every edge: that
    //: is what keeps `wbMapNodeSize` off `document.querySelector` for a board
    //: whose elements this pass is holding already.
    if (mapIndex) {
      if (!wbMapNodeSizeCache) wbMapNodeSizeCache = new Map();
      objectUpdate.each(function (d) {
        if (!WB_MAP_KINDS.has(d.kind)) return;
        //: A topic this pass did not repaint is the size it last measured (a
        //: move is not a resize), and a culled one was not repainted either.
        if (!repainted.has(this) || this.classList.contains("wb-culled")) {
          //: **The height it was last measured at, not the stored one.** A state
          //: fetched from the server hands every topic back the server's
          //: placeholder height (120), while the element on screen is what its
          //: text needs (44 for one line): a topic this pass did not repaint
          //: took the 120 into the cache, and `wbMapNodeSize` then put a pan,
          //: a ring and an edge end 38px off the box (`mapstrip.js` at 1440, 12px
          //: at 390: the "94px" row, 2 x 47). An element measured once keeps its
          //: own number; one never measured and not culled is read now below.
          const known = this._wbMeasuredH;
          if (d.width && (known || (d.height && this.classList.contains("wb-culled")))) {
            wbMapNodeSizeCache.set(d.id, { w: d.width, h: known || d.height });
            if (known) d.height = known;
            return;
          }
          if (this.classList.contains("wb-culled")) return;
        }
        const h = this.offsetHeight;
        if (!h) return;
        wbMapNodeSizeCache.set(d.id, { w: this.offsetWidth, h });
        this._wbMeasuredH = h;
        d.height = h;
      });
    }
    if (wbAddGate.renderHold) wbAddGate.renderHold.moves.push(...movesLater);
    else for (const [el, place] of movesLater) el.style.transform = place;
  }

  //: The file's surface: what other files call (L634).
  //: Private names a sweep drives (scratchpad/ui-sweeps), on an exported name so the shared scope does not grow.
  renderWbObjects.sweep = { wbResizeHandleTitle, wbScheduleStickyDates };
  Object.assign(window, { wbScheduleRender, wbCloseOrphanedPopovers, wbDeleteSketch, wbDeleteNode, wbDeleteObject, wbResetRotation, wbCardFitHeight, wbFitImage, wbFitToText, wbSaveNode, wbSaveObject, wbSaveMany, wbSketchSetD, wbSketchSetProps, wbTakeMoveRun, wbApplyMoveRun, renderWbObjects });
})();
