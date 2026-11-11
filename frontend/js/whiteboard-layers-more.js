(() => {
  // whiteboard-layers-more.js: the last of draw.io's layer rows (WHITEBOARD_PLAN section 10, "Layer order" and
  // "Named layers: duplicate"). A layer's menu gains Bring the layer to the front, Send the layer to the back and
  // Duplicate the layer. Show, hide, lock, current layer, move the selection here and select what is on it were
  // built before (whiteboard-library.js, `wbNamedLayerMenu`); this adds three rows to the same menu and nothing else.

  //: The layer's items, bottom first, as `{ kind, item }`, by the board's one stacking order.
  function inStackOrder(layerId) {
    return wbNamedLayerItems(layerId)
      .map(([kind, item]) => ({ kind, item }))
      .sort(wbStackCompare);
  }

  //: The whole layer to the front or back of the stack, its own order kept: to the front the lowest goes first
  //: (each lands on top of the last), to the back the highest goes first. One Undo step, one save.
  async function sendLayer(layer, toFront) {
    const items = inStackOrder(layer.id);
    if (!items.length) {
      toast(`${layer.name} has nothing on it.`, "info");
      return 0;
    }
    const entries = [];
    const rows = [];
    for (const { kind, item } of toFront ? items : items.reverse()) {
      const entry = wbSetZOrder(kind, item, toFront, rows);
      if (entry) entries.push(entry);
    }
    await wbCommitMoves(rows, entries);
    const said = `${layer.name} ${toFront ? "brought to the front" : "sent to the back"}.`;
    wbAnnounce(said);
    toast(said);
    return items.length;
  }

  //: A copy of the layer and what is on it, drawn a grid step across and down and put on a layer of its own named
  //: "<name> copy": the items are copied by the board's own Duplicate, which selects the copies.
  async function duplicateLayer(layer) {
    const items = wbNamedLayerItems(layer.id);
    if (!items.length) {
      toast(`${layer.name} has nothing on it to copy.`, "info");
      return 0;
    }
    //: The copy, the layer and the move are three Undo entries as the board makes them; they are bundled into the
    //: one step the person took (a batch replays them back to front).
    const mark = wbUndoStack.length;
    clearWbSelection();
    for (const [kind, item] of items) wbMultiSelection.add(wbMultiKey(kind, item.id));
    await wbDuplicateSelection();
    let moved = 0;
    if (wbMultiSelection.size || wbSelectedItem) {
      const copy = { id: `l${Date.now().toString(36)}`, name: `${layer.name} copy`.slice(0, 60), hidden: false, locked: false };
      if (await wbSaveNamedLayers([...(wbState.layers || []), copy], { said: `Layer ${copy.name} added.` })) moved = await wbMoveSelectionToLayer(copy.id);
    }
    const steps = wbUndoStack.splice(mark);
    if (steps.length) wbPushUndo(steps.length === 1 ? steps[0] : { action: "batch", entries: steps });
    return moved;
  }

  //: The menu rows, spread into `wbNamedLayerMenu`'s list after Select what is on it.
  function rows(layer) {
    return [
      { label: "ph:arrow-line-up Bring the layer to the front", title: "All of its items over everything else, in their own order", run: () => sendLayer(layer, true) },
      { label: "ph:arrow-line-down Send the layer to the back", title: "All of its items under everything else, in their own order", run: () => sendLayer(layer, false) },
      { label: "ph:copy Duplicate the layer", title: "A copy of what is on it, on a new layer", run: () => duplicateLayer(layer) },
    ];
  }

  wbFmtState.layersMore = { rows, sendLayer, duplicateLayer, inStackOrder };
})();
