(() => {
  // whiteboard-map-record.js: the map's Undo-recorded commands (add, move, fold, tidy, layout, theme, cross-links) and what only they use.
  // Moved out of whiteboard-map.js (L-whiteboard-49) and wrapped. Each command is bound once through `wbRecorded` (whiteboard-map.js), so a call from here and a call through `window` are the same recorded gesture.

  //: The seven fields a level can set (the server's `MAP_LEVEL_FIELDS`). `fill`
  //: here is `solid`, `tint` or `none`: a level's fill, read by the paint pass
  //: only where the topic and its branch said nothing (`wbMapFillOf`).
  const WB_MAP_LEVEL_FIELDS = ["font_size", "bold", "italic", "shape", "spine", "fill", "edge_width", "effect"];

  //: Write one patch onto the map's theme and redraw.
  //:
  //: One request whatever the map's size, because the theme is resolved when a
  //: topic is painted rather than written onto every topic: that is what makes
  //: it reversible, and what makes a deliberate per-topic choice impossible to
  //: overwrite with it.
  //: One Undo step on the board's history (INBOX 898): the rows and the map's
  //: settings are compared before and after, whatever the act wrote.
  const wbMapSetTheme = wbRecorded("wbMapSetTheme",
  function wbMapSetTheme(...args) {
    return wbMapSetThemeNow(...args);
  });

  async function wbMapSetThemeNow(patch) {
    const boardId = window.currentBoardId;
    if (!boardId || !wbIsMap()) return false;
    try {
      await apiJson(`/whiteboard/boards/${boardId}`, {
        method: "PUT",
        body: JSON.stringify({ theme: patch }),
      });
      const theme = { ...wbMapTheme() };
      for (const [key, value] of Object.entries(patch)) {
        if (value === null || value === false || value === "") delete theme[key];
        else theme[key] = value;
      }
      window.wbMapState = { ...window.wbMapState, theme };
      //: A palette is a name here and its colours are the server's, so a new
      //: one is read back with the tree rather than looked up in a second copy.
      if ("palette" in patch) await wbRefreshMapState();
      wbApplyMapFont();
      renderWhiteboardNow();
      wbSyncMapLinkStyle();
      //: New gaps mean new places: the whole map, laid out again.
      if ("spacing" in patch && wbMapLayout() !== "free") await wbMapTidy({ quiet: true });
      const selected = wbSelectedMapNode();
      if (selected) wbSyncMapStrip(selected);
      return true;
    } catch (err) {
      toast(err.message || voiceLine("failed", { what: "change how this map draws" }), true);
      return false;
    }
  }

  //: **"Back to the branch" at the map's scope, not a second idea** (§13e).
  //: The ring's reset drops one topic's own look so it follows what it
  //: inherits; with a theme, what a topic inherits is the map, so the same
  //: sentence said about every topic is the bulk operation §13.4 found missing.
  //: One endpoint and one transaction, `move-many`'s own reason: a reset that
  //: is one request per topic leaves a two-hundred-topic map half done if any
  //: one of them fails.
  //: One Undo step on the board's history (INBOX 898): the rows and the map's
  //: settings are compared before and after, whatever the act wrote.
  const wbMapClearEveryTopic = wbRecorded("wbMapClearEveryTopic",
  function wbMapClearEveryTopic(...args) {
    return wbMapClearEveryTopicNow(...args);
  });

  async function wbMapClearEveryTopicNow() {
    const boardId = window.currentBoardId;
    if (!boardId || !wbIsMap()) return;
    const ok = await confirmDialog(
      "Every topic goes back to following this map, losing the colours, shapes "
      + "and line styles that were set on them one at a time. Pictures stay.",
      { confirmLabel: "Back to the map", cancelLabel: "Leave them" }
    );
    if (!ok) return;
    try {
      const out = await apiJson(`/whiteboard/boards/${boardId}/nodes/clear-style`, { method: "POST" });
      const count = Number(out?.cleared) || 0;
      //: A full re-fetch rather than a patch of `wbState`: the endpoint dropped
      //: a key from every topic's data in one transaction, and the objects this
      //: tab is holding are now wrong about all of them.
      await fetchWhiteboardState();
      renderWhiteboardNow();
      toast(count
        ? `${nounCount(count, "topic")} back to following this map.`
        : "Every topic was already following this map.");
    } catch (err) {
      toast(err.message || voiceLine("failed", { what: "reset the topics" }), true);
    }
  }

  //: Ctrl+Shift+Up/Down (and Left/Right, for the layouts whose siblings run
  //: across): swap a topic with the sibling before or after it. **One undo
  //: step for the whole visible change**: the two keys and every position the
  //: tidy then moved, compared against a snapshot, because a tidy pushes no
  //: undo entry of its own and taking back only the keys would leave two
  //: branches drawn in each other's places.
  const wbMapMoveAmongSiblings = wbRecorded("wbMapMoveAmongSiblings",
  async function wbMapMoveAmongSiblings(id, dir) {
    const index = wbMapIndex();
    const node = index.byId.get(id);
    if (!node) return false;
    const siblings = wbMapSiblingsOf(index, node);
    const at = siblings.findIndex((s) => s.id === id);
    const other = siblings[at + dir];
    if (!other) {
      toast(dir < 0 ? "This topic is already first among its siblings." : "This topic is already last among its siblings.");
      return false;
    }
    const before = new Map(index.nodes.map((o) => [o.id, WB_KIND_INFO.object.payload(o)]));
    const mine = wbMapOrderKey(node);
    const theirs = wbMapOrderKey(other);
    node.data = { ...node.data, order: theirs };
    other.data = { ...other.data, order: mine };
    await Promise.all([wbSaveObject(node), wbSaveObject(other)]);
    if (wbMapLayout() === "free") {
      toast("Moved in the outline. This map's layout is Free, so the canvas stays as it is.");
    } else {
      await wbMapTidyBranch(node.parent_id ?? null);
    }
    renderWhiteboardNow();
    const entries = [];
    for (const obj of wbMapIndex().nodes) {
      const was = before.get(obj.id);
      if (was && (was.x !== obj.x || was.y !== obj.y || was.data !== obj.data)) {
        entries.push({ action: "move", kind: "object", id: obj.id, before: was });
      }
    }
    if (entries.length) wbPushUndo(entries.length === 1 ? entries[0] : { action: "batch", entries });
    return true;
  });

  //: **Sort a topic's branches** (XMind's "Sort", MindManager's "Sort
  //: subtopics"): its children reordered by their words, A to Z or Z to A,
  //: numbers read as numbers, so "Step 2" comes before "Step 10". The same
  //: `data.order` key the move keys write, so the outline and the exports
  //: agree; one Undo step (the name is in `WB_RECORDED`).
  const wbMapSortChildren = wbRecorded("wbMapSortChildren",
  async function wbMapSortChildren(id, dir = 1) {
    const index = wbMapIndex();
    const kids = index.childrenOf.get(id) || [];
    if (kids.length < 2) {
      toast("This topic needs at least two branches to sort.");
      return false;
    }
    const word = (o) => String(wbMapLabel(o) || "");
    const sorted = [...kids].sort((x, y) => dir * word(x).localeCompare(word(y), undefined, { numeric: true, sensitivity: "base" }) || x.id - y.id);
    sorted.forEach((kid, at) => { kid.data = { ...kid.data, order: at + 1 }; });
    await wbSaveMany(sorted.map((item) => ({ kind: "object", item })));
    if (wbMapLayout() === "free") toast("Sorted in the outline. This map's layout is Free, so the canvas stays as it is.");
    else await wbMapTidyBranch(id);
    renderWhiteboardNow();
    wbAnnounce(`Branches sorted ${dir > 0 ? "A to Z" : "Z to A"}.`);
    return true;
  });

  //: Turn the numbering on or off for this map: one `PUT`, then a render,
  //: because every topic's prefix changes with it.
  //: One Undo step on the board's history (INBOX 898): the rows and the map's
  //: settings are compared before and after, whatever the act wrote.
  const wbMapSetNumbered = wbRecorded("wbMapSetNumbered",
  function wbMapSetNumbered(...args) {
    return wbMapSetNumberedNow(...args);
  });

  async function wbMapSetNumberedNow(on) {
    const boardId = window.currentBoardId;
    if (!boardId || !wbIsMap()) return false;
    try {
      await apiJson(`/whiteboard/boards/${boardId}`, {
        method: "PUT",
        body: JSON.stringify({ numbered: Boolean(on) }),
      });
      window.wbMapState = { ...window.wbMapState, numbered: Boolean(on) };
      renderWhiteboardNow();
      wbSyncMapChrome();
      wbAnnounce(on ? "Branches numbered." : "Branches not numbered.");
      return true;
    } catch (err) {
      toast(err.message || voiceLine("failed", { what: "change the numbering" }), true);
      wbSyncMapChrome();
      return false;
    }
  }

  // whiteboard-map-notes.js: whiteboard-map-notes.js: map note topics, the note behind a topic and folding. (moved out, L286).
  //: Open every folded branch on the map (§12.1 item 7's third route, after the
  //: badge and the chevron), saved in one request (`wbSaveMany`, BD2).
  const wbMapExpandAll = wbRecorded("wbMapExpandAll",
  async function wbMapExpandAll() {
    const folded = wbMapIndex().nodes.filter((o) => o.data?.collapsed);
    if (!folded.length) {
      toast("Nothing is folded away on this map.");
      return;
    }
    for (const node of folded) node.data = { ...node.data, collapsed: false };
    await wbSaveMany(folded.map((item) => ({ kind: "object", item })));
    renderWhiteboardNow();
    wbSyncMapToolState();
    toast(`Opened ${folded.length} branch${folded.length === 1 ? "" : "es"}.`);
  });

  //: **Fold to a level** (the features audit, Phase D: "fold-to-level (Alt+1
  //: to 9)"; XMind's and MindNode's "show levels"). Alt+N leaves the first N
  //: levels of every trunk open and folds each topic at level N that has a
  //: branch under it, so a map of two hundred topics reads as its outline at
  //: one press and opens a level at a time. Level 1 is the trunks alone. Only
  //: the topics whose fold changes are saved, and the whole press is one Undo
  //: step (`WB_RECORDED`, whiteboard.js).
  const wbMapFoldToLevel = wbRecorded("wbMapFoldToLevel",
  async function wbMapFoldToLevel(level) {
    if (!wbIsMap()) return;
    const index = wbMapIndex();
    const changed = [];
    //: **One more or one less level** (INBOX 1774): `{ by: 1 }` opens the
    //: shallowest ring of folded topics, `{ by: -1 }` folds the deepest ring
    //: of open ones, so a ragged map is never re-levelled and a branch opened
    //: by hand is never shut by "more".
    if (level && typeof level === "object") {
      const by = Number(level.by) < 0 ? -1 : 1;
      const ring = wbMapBuild.ring(index, wbMapHidden(index), by);
      if (!ring.ids.length) {
        toast(by > 0 ? "Every level is showing." : "Only the centre is showing.");
        return;
      }
      for (const id of ring.ids) {
        const node = index.byId.get(id);
        node.data = { ...node.data, collapsed: ring.fold };
        changed.push(node);
      }
      await wbSaveMany(changed.map((item) => ({ kind: "object", item })));
      renderWhiteboardNow();
      wbSyncMapToolState();
      const shown = wbMapBuild.levels(index, wbMapHidden(index));
      toast(shown === 1 ? "Showing the trunks only." : `Showing ${shown} levels.`);
      return;
    }
    const want = Math.max(1, Math.min(9, Math.round(Number(level) || 1)));
    const seen = new Set();
    const stack = index.roots.map((root) => [root, 1]);
    while (stack.length) {
      const [node, depth] = stack.pop();
      if (seen.has(node.id)) continue;
      seen.add(node.id);
      const kids = index.childrenOf.get(node.id) || [];
      for (const child of kids) stack.push([child, depth + 1]);
      if (!kids.length) continue;
      const fold = depth >= want;
      if (Boolean(node.data?.collapsed) !== fold) {
        node.data = { ...node.data, collapsed: fold };
        changed.push(node);
      }
    }
    await wbSaveMany(changed.map((item) => ({ kind: "object", item })));
    if (changed.length) {
      renderWhiteboardNow();
      wbSyncMapToolState();
    }
    if (want === 1) toast(changed.length ? `Folded ${changed.length} branch${changed.length === 1 ? "" : "es"}.` : "Every branch is already folded.");
    else toast(`Showing ${want} levels.`);
  });

  //: **Fold every branch** (INBOX 1773) is `wbMapFoldToLevel(1)`, the twin of
  //: Open every folded branch. `open` counts the topics with a branch under
  //: them that are open (what a level-1 fold would change); `sync` enables the
  //: two twins only when they would change something. Properties, not globals.
  wbMapFoldToLevel.open = function foldOpen(index) {
    const map = index || wbMapIndex();
    return map.nodes.filter((n) => !n.data?.collapsed && (map.childrenOf.get(n.id) || []).length).length;
  };
  wbMapFoldToLevel.sync = function foldSync() {
    if (!wbIsMap()) return;
    const index = wbMapIndex();
    const open = wbMapFoldToLevel.open(index);
    const folded = index.nodes.filter((n) => n.data?.collapsed).length;
    for (const id of ["wb-map-fold-all", "wb-side-map-fold"]) {
      const el = document.getElementById(id);
      if (el) el.disabled = !open;
    }
    for (const id of ["wb-map-expand-all", "wb-side-map-expand"]) {
      const el = document.getElementById(id);
      if (el) el.disabled = !folded;
    }
  };

  //: Put a new topic between a parent and one of its children: the new topic
  //: takes the parent, and the child takes the new topic.
  //:
  //: Two steps, and the second is a `/move` rather than a create-with-parent,
  //: because the child already exists and `parent_id` is only writable through
  //: the endpoint that runs the cycle check. The new topic opens for typing
  //: like every other add on this map.
  //:
  //: **One Undo step that puts the child back** (INBOX 537: the create was in
  //: history and the move was not, so Ctrl+Z deleted the new topic and left
  //: the child's branch with no parent, cut off from the map). The batch
  //: replays in order: the child goes back under its parent, then the new
  //: topic goes, then every topic the tidy moved returns to where it was.
  const wbMapInsertBetween = wbRecorded("wbMapInsertBetween",
  async function wbMapInsertBetween(parentId, childId) {
    const boardId = window.currentBoardId;
    if (!boardId) return;
    const payload = WB_KIND_INFO.object.payload;
    const rows = new Map(wbMapIndex().nodes.map((n) => [n.id, payload(n)]));
    const created = await wbMapCreateNode({ parentId });
    if (!created) return;
    //: `wbMapCreateNode` pushed its own create entry; this gesture is one step.
    const top = wbUndoStack[wbUndoStack.length - 1];
    if (top?.action === "create" && top.id === created.id) wbUndoStack.pop();
    const history = [];
    const child = (wbState.objects || []).find((o) => o.id === childId);
    //: **It takes its child's place** (the owner, 2026-10-10: "when I added a
    //: mindmap node in between, it changed the colour of the other nodes in the
    //: branch and the spacing is really close"): the child's spot, so the
    //: both-sides split keeps the branch on its side and the tidy opens the
    //: gap from where the branch was, and its slot among the siblings, so the
    //: branch does not jump to the end of the list.
    if (child) {
      created.x = child.x;
      created.y = child.y;
      created.data = { ...created.data, order: wbMapOrderKey(child) };
      await wbSaveObject(created);
    }
    if (child) {
      try {
        const moved = await apiJson(`/whiteboard/boards/${boardId}/nodes/${childId}/move`, {
          method: "PUT",
          body: JSON.stringify({ parent_id: created.id }),
        });
        Object.assign(child, moved);
        history.push({ action: "reparent", kind: "object", id: childId, parentId });
      } catch (err) {
        toast(err.message || voiceLine("failed", { what: "move that topic under the new one" }), true);
      }
    }
    history.push({ action: "create", kind: "object", id: created.id });
    selectWbItem("object", created.id);
    await wbMapTidyBranch(parentId);
    for (const node of wbMapIndex().nodes) {
      const row = rows.get(node.id);
      if (row && (row.x !== node.x || row.y !== node.y)) {
        history.push({ action: "move", kind: "object", id: node.id, before: row });
      }
    }
    wbPushUndo({ action: "batch", entries: history });
    renderWhiteboardNow();
    wbMapEditNode(created.id);
  });

  const wbMapAddChild = wbRecorded("wbMapAddChild",
  async function wbMapAddChild(parentId, { order = null } = {}) {
    const boardId = window.currentBoardId;
    if (!boardId) return null;
    wbMapTypeahead = { text: "", at: performance.now() };
    let parent = parentId != null ? (wbState.objects || []).find((o) => o.id === parentId) : null;
    if (parent?._creating) {
      if (!(await parent._creating)) {
        wbMapTypeahead = null;
        return null;
      }
      parentId = parent.id;
    }
    if (parentId != null && !parent) parent = (wbState.objects || []).find((o) => o.id === parentId) || null;
    const created = {
      id: -(++wbMapProvisionalSeq),
      board_id: boardId,
      kind: "topic",
      parent_id: parent ? parent.id : null,
      x: 0,
      y: 0,
      z: 1,
      //: The server's own default width; the height is the text's, measured by
      //: the render.
      width: WB_MAP_NODE_W,
      height: null,
      rotation: null,
      data: { content: WB_MAP_NEW_TOPIC, ...(order != null ? { order } : {}) },
      //: The first rename is part of making it: one Undo step, not two
      //: (audit FEAT-15). Cleared by the label's first commit.
      _fresh: true,
    };
    wbState.objects = wbState.objects || [];
    wbMapFreshPlace(created, parent);
    wbState.objects.push(created);
    // Expanding first: adding a child to a collapsed node would otherwise put
    // the new node straight into the hidden set, so the gesture would appear to
    // do nothing at all.
    const expand = Boolean(parent?.data?.collapsed);
    if (expand) parent.data = { ...parent.data, collapsed: false };
    //: The branch laid out without a render or a save of its own: the one
    //: render below draws it, and the save goes after the create.
    const origin = wbMapTidyBranchPlan(parentId, created);
    //: **The new places as data only** (FEAT-02's 100ms gate): the render
    //: right below writes every moved topic's transform and every line, after
    //: its measure, so writing them here as well was the same work twice and
    //: left the whole moved map dirty for the measure's first read. A plan that
    //: carries a drawn line (a cross-link) is applied in full, as before.
    if (origin && [...origin.values()].every((entry) => entry.kind !== "sketch")) {
      for (const entry of origin.values()) {
        entry.item.x = entry.x;
        entry.item.y = entry.y;
      }
      wbScheduleCull();
    } else if (origin) wbApplyBulkMove(origin, 0, 0);
    const undo = { action: "create", kind: "object", id: created.id };
    wbPushUndo(undo);
    wbAddGate.barDeferred = true;
    wbAddGate.renderHold = { moves: [], edges: false };
    try {
      wbMapCache.renderAdd(created, origin, expand);
      //: Opened before the selection is announced: the editor's focus then finds
      //: the tree the measure left clean, and the selection's chrome (the dock,
      //: the bar) is restyled after the topic is typeable, in the same task.
      wbMapEditNode(created.id, { now: true });
      selectWbItem("object", created.id);
      wbMapRevealTopic(created);
    } finally {
      //: A topic the render made editable that the editor never took over (it bailed) is put back.
      wbBeginTextEdit.drop(wbItemElement("object", created.id)?.querySelector(".wb-map-text"));
      wbRenderRelease();
      wbSyncMapEdgeHandles();
      wbAddGate.barDeferred = false;
    }
    created._creating = wbMapAdoptProvisional(created, { expand: expand ? parent : null, origin, order });
    //: The editor is already open; what waits here is the caller, so a caller
    //: that uses the topic it gets back (a script, the recorded gesture's
    //: after-snapshot) gets it with its real id, or null when it was refused.
    return (await created._creating) ? created : null;
  });

  //: Where a new topic starts, before any tidy: beside its parent and under
  //: its last sibling's whole branch (`wbMapPlaceAsChild`'s rule and the
  //: server's `_next_position`), or under everything for a new trunk. On a
  //: Free map this is where it stays.
  function wbMapFreshPlace(row, parent) {
    const index = wbMapIndex();
    const size = (node) => wbMapNodeSize(node);
    const below = (nodes) => {
      let bottom = -Infinity;
      for (const top of nodes) {
        for (const node of wbMapSubtree(index, top.id)) bottom = Math.max(bottom, node.y + size(node).h);
      }
      return bottom;
    };
    //: Its height before it has an element to measure: a sibling's, or any
    //: branch topic's, so the tidy centres it as it will be drawn rather than
    //: at the default box and 6px off once measured.
    const like = (parent && (index.childrenOf.get(parent.id) || [])[0]) || index.nodes.find((n) => n.parent_id != null && n !== row);
    if (like && !row.height) row.height = size(like).h;
    if (!parent) {
      row.x = index.roots.length ? Math.min(...index.roots.map((r) => r.x)) : 0;
      row.y = index.roots.length ? below(index.roots) + wbMapGapDepth() : 0;
      return;
    }
    let siblings = index.childrenOf.get(parent.id) || [];
    const mid = (node) => node.x + size(node).w / 2;
    //: **The central topic's children go to the side with fewer** (bug sweep
    //: 2026-10-12: 7 of 8 stacked on one side), right on a tie; the new one
    //: goes under that side's last branch. Other topics' children are not
    //: moved (below: they grow away from the trunk).
    if (parent.parent_id == null) {
      const lefts = siblings.filter((n) => n !== row && mid(n) < mid(parent));
      const rights = siblings.filter((n) => n !== row && mid(n) >= mid(parent));
      const toLeft = lefts.length < rights.length;
      siblings = toLeft ? lefts : rights;
      const width = row.width || WB_MAP_NODE_W;
      if (toLeft) row.x = (lefts.length ? Math.max(...lefts.map((n) => n.x + size(n).w)) : parent.x - wbMapGapDepth()) - width;
      else row.x = rights.length ? Math.min(...rights.map((n) => n.x)) : parent.x + size(parent).w + wbMapGapDepth();
      row.y = siblings.length ? below(siblings) + wbMapGapBreadth() : parent.y;
      return;
    }
    //: **A branch grows away from its trunk** (the owner, 2026-10-11: a child
    //: added under a left-hand topic landed on its right, back toward the
    //: trunk, and on a Free map that is where it stayed). The side is the one
    //: the parent is drawn on, read from its centre against its trunk's.
    let trunk = parent;
    for (let hops = 0; trunk.parent_id != null && index.byId.get(trunk.parent_id) && hops < 200; hops++) trunk = index.byId.get(trunk.parent_id);
    const leftward = trunk !== parent && mid(parent) < mid(trunk);
    const width = row.width || WB_MAP_NODE_W;
    if (leftward) {
      row.x = (siblings.length ? Math.max(...siblings.map((n) => n.x + size(n).w)) : parent.x - wbMapGapDepth()) - width;
    } else {
      row.x = siblings.length ? Math.min(...siblings.map((n) => n.x)) : parent.x + size(parent).w + wbMapGapDepth();
    }
    row.y = siblings.length ? below(siblings) + wbMapGapBreadth() : parent.y;
  }

  //: The provisional topic made real: POST it where the tidy put it, swap its
  //: id for the server's everywhere it is held (the row, its element, the
  //: selection, the Undo stacks), then write what the POST could not carry
  //: (its place among its siblings, the text typed so far) and the tidy's
  //: moves. Resolves true once it has its id, false when the server refused
  //: it, in which case the topic is taken back off the canvas.
  async function wbMapAdoptProvisional(row, { expand = null, origin = null, order = null } = {}) {
    const tempId = row.id;
    let made;
    try {
      made = await apiJson(`/whiteboard/boards/${row.board_id}/nodes`, {
        method: "POST",
        body: JSON.stringify({ kind: "topic", parent_id: row.parent_id, text: WB_MAP_NEW_TOPIC, x: row.x, y: row.y }),
      });
    } catch (err) {
      delete row._creating;
      wbState.objects = (wbState.objects || []).filter((o) => o !== row);
      const step = wbUndoStack.find((e) => e.action === "create" && e.id === tempId);
      if (step) wbDropUndoEntry(step);
      toast(err.message || voiceLine("failed", { what: "add that node" }), true);
      wbScheduleRender();
      return false;
    }
    row.id = made.id;
    const el = document.querySelector(`.wb-object[data-id="${tempId}"]`);
    if (el) el.dataset.id = String(made.id);
    if (wbSelectedItem?.kind === "object" && wbSelectedItem.id === tempId) wbSelectedItem.id = made.id;
    const size = wbMapNodeSizeCache?.get(tempId);
    if (size) wbMapNodeSizeCache.set(made.id, size);
    wbRemapUndoIds(new Map([[tempId, made.id]]));
    delete row._creating;
    //: What the server knows that this row does not (its timestamps), without
    //: taking back what has happened here since: the place the tidy gave it
    //: and whatever has been typed.
    for (const key of Object.keys(made)) {
      if (!["x", "y", "data", "id", "width", "height"].includes(key)) row[key] = made[key];
    }
    if (!row.width) row.width = made.width;
    if (!row.height) row.height = made.height;
    const typed = row.data?.content !== WB_MAP_NEW_TOPIC;
    if (order != null || typed) wbSaveObject(row);
    if (expand) wbSaveObject(expand);
    if (origin?.size) wbSaveBulkMove(origin);
    //: The lines into and out of it are keyed by the old id: they, their
    //: mid-line `+` and its waypoint handle are drawn again under the new. Not
    //: a whole render (MINDMAP_PLAN 15, row 4: one render per act, not two);
    //: the topic itself took its new id on its element above.
    wbRenderMapEdges({ only: new Set([made.id]) });
    return true;
  }

  //: **A new trunk where the person pointed** (MINDMAP_PLAN §13, the owner:
  //: the map's tools "dont show themselves how id expect"). Double-clicking
  //: empty canvas is how a new topic is made in Coggle, XMind and every
  //: whiteboard in this app's own reference list, and on a map it did nothing
  //: at all: measured, 3 topics before and 3 after. The rail's "Add a
  //: top-level topic" was the only route, and it puts the new trunk wherever
  //: the layout decides.
  //:
  //: Pinned, because the position is a decision the person made with the
  //: pointer: that is the same bargain `wbMapPinOnDrag` strikes for a dragged
  //: node, and without it the next tidy would move the new trunk away from the
  //: spot that was just chosen.
  const wbMapAddRootAt = wbRecorded("wbMapAddRootAt",
  async function wbMapAddRootAt(x, y) {
    const created = await wbMapCreateNode({ parentId: null });
    if (!created) return null;
    created.x = Math.round(x - (created.width || WB_MAP_NODE_W) / 2);
    created.y = Math.round(y - (created.height || WB_MAP_NODE_H) / 2);
    created.data = { ...created.data, pinned: true };
    await wbSaveObject(created);
    selectWbItem("object", created.id);
    renderWhiteboardNow();
    wbMapEditNode(created.id);
    return created;
  });

  //: Add a child that **points at something the library already holds**
  //: (MINDMAP_PLAN.md §5 item 11).
  //:
  //: The label is *not* sent. `POST /boards/{id}/nodes` takes the kind and the
  //: id and resolves the title itself, and `GET /tree` re-resolves it on every
  //: load (§9.2): so renaming the note renames the node, which is the whole
  //: reason a reference node is different from a topic with the same words in
  //: it. `text` is left empty deliberately: a copy of the title stored here
  //: would be the value that goes stale, and `wbMapLabel` prefers the resolved
  //: one anyway.
  //:
  //: `wbRefreshMapState` is re-run before the render because the resolved label
  //: lives in `wbMapState.labels`, which only that call fills, without it the
  //: new node draws with no text at all until the next board load, which is
  //: exactly the "renders as a blank box" failure §10.2 already fixed once for
  //: topics.
  const wbMapAddReference = wbRecorded("wbMapAddReference",
  async function wbMapAddReference(parentId) {
    if (typeof pickLibraryItemDialog !== "function") return null;
    const chosen = await pickLibraryItemDialog("Point a new node at…", { noUploads: true });
    if (!chosen) return null;
    const created = await wbMapCreateNode({
      parentId,
      kind: chosen.kind,
      text: "",
      refId: chosen.id,
    });
    if (!created) return null;
    const parent = (wbState.objects || []).find((o) => o.id === parentId);
    if (parent?.data?.collapsed) {
      parent.data = { ...parent.data, collapsed: false };
      await wbSaveObject(parent);
    }
    await wbRefreshMapState();
    selectWbItem("object", created.id);
    await wbMapTidyBranch(parentId);
    renderWhiteboardNow();
    toast(`Added “${chosen.label}” to the map.`);
    return created;
  });

  //: Ctrl+D on a topic: the same text and look, right after it among its
  //: siblings, one undo step (the create), the copy selected. Its children are
  //: not copied: a duplicate branch is Copy and Paste's job, and a key that
  //: quietly copied forty topics would be a surprise.
  const wbMapDuplicateTopic = wbRecorded("wbMapDuplicateTopic",
  async function wbMapDuplicateTopic(node) {
    const index = wbMapIndex();
    const parentId = node.parent_id != null && index.byId.has(node.parent_id) ? node.parent_id : null;
    const created = await wbMapCreateNode({
      parentId, kind: node.kind, text: node.data?.text ?? "", refId: node.data?.ref_id ?? null,
    });
    if (!created) return null;
    const siblings = wbMapSiblingsOf(index, node);
    const neighbour = siblings[siblings.findIndex((s) => s.id === node.id) + 1];
    //: Its look comes along; whether it is folded and where it sorts do not.
    const look = { ...(node.data || {}) };
    delete look.collapsed;
    delete look.order;
    created.data = { ...look, ...created.data, text: node.data?.text ?? "" };
    if (neighbour) created.data.order = wbMapKeyBetween(node, neighbour);
    await wbSaveObject(created);
    selectWbItem("object", created.id);
    await wbMapTidyBranch(parentId);
    renderWhiteboardNow();
    return created;
  });

  //: Shift+Tab: outdent: this node becomes a sibling of its own parent.
  //:
  //: Through `/move`, never `PUT /objects/{id}`, because the move endpoint is
  //: the only one that runs the cycle check, §9.3 says so in as many words, and
  //: `PUT` deliberately does not touch `parent_id` so the check cannot be
  //: bypassed by using the wrong endpoint.
  const wbMapOutdent = wbRecorded("wbMapOutdent",
  async function wbMapOutdent(id) {
    const boardId = window.currentBoardId;
    const index = wbMapIndex();
    const node = index.byId.get(id);
    if (!boardId || !node) return;
    const parent = node.parent_id != null ? index.byId.get(node.parent_id) : null;
    if (!parent) {
      toast("This is already a top-level topic.");
      return;
    }
    //: Every topic's row as it stands, so the one history entry can put back
    //: whatever the tidy moves along with the parent (the shape
    //: `wbMapTransplant` records for a drag).
    const rows = new Map(index.nodes.map((n) => [n.id, WB_KIND_INFO.object.payload(n)]));
    try {
      const moved = await apiJson(`/whiteboard/boards/${boardId}/nodes/${id}/move`, {
        method: "PUT",
        body: JSON.stringify({ parent_id: parent.parent_id ?? null }),
      });
      Object.assign(node, moved);
      await wbMapTidyBranch(moved.parent_id ?? null);
      //: **One Undo step** (INBOX 445, second audit: Shift+Tab was the one
      //: structural key with no history, so Ctrl+Z took back whatever came
      //: before it).
      const history = [{ action: "reparent", kind: "object", id, parentId: parent.id }];
      for (const now of wbMapIndex().nodes) {
        const row = rows.get(now.id);
        if (row && (row.x !== now.x || row.y !== now.y)) {
          history.push({ action: "move", kind: "object", id: now.id, before: row });
        }
      }
      wbPushUndo(history.length === 1 ? history[0] : { action: "batch", entries: history });
      renderWhiteboardNow();
    } catch (err) {
      toast(err.message || voiceLine("failed", { what: "move that node" }), true);
    }
  });

  //: The explicit version of what deleting the last node would have done by
  //: accident: take everything away, then leave one blank topic open for
  //: typing, which is the state a new map starts in.
  //:
  //: Deleting the roots is enough to delete the map: `DELETE
  //: /whiteboard/objects/{id}` takes a node's whole subtree with it (§9.1), so
  //: one request per root removes every descendant too.
  //: One Undo step on the board's history (INBOX 898): the rows and the map's
  //: settings are compared before and after, whatever the act wrote.
  const wbMapClearToOneTopic = wbRecorded("wbMapClearToOneTopic",
  function wbMapClearToOneTopic(...args) {
    return wbMapClearToOneTopicNow(...args);
  });

  async function wbMapClearToOneTopicNow() {
    if (!wbIsMap()) return;
    const roots = wbMapIndex().roots;
    for (const root of roots) {
      try {
        const res = await apiJson(`/whiteboard/objects/${root.id}`, { method: "DELETE" });
        const gone = new Set((Array.isArray(res?.deleted) ? res.deleted : []).map((row) => row.id));
        gone.add(root.id);
        wbState.objects = (wbState.objects || []).filter((o) => !gone.has(o.id));
      } catch (err) {
        toast(err.message || voiceLine("failed", { what: "clear the map" }), true);
        return;
      }
    }
    clearWbSelection();
    await wbMapAddChild(null);
  }


  //: The chevron: fold a branch away, or bring it back. `collapsed` is per-node
  //: view state in the object's own JSON blob (§9.1), so it survives a reload
  //: and the tree endpoint hands it back, a fold you made yesterday is still
  //: folded today, which is the only version of this that is worth having.
  const wbMapToggleCollapse = wbRecorded("wbMapToggleCollapse",
  async function wbMapToggleCollapse(id) {
    const node = (wbState.objects || []).find((o) => o.id === id);
    if (!node) return;
    node.data = { ...node.data, collapsed: !node.data?.collapsed };
    wbScheduleRender();
    await wbSaveObject(node);
  });

  //: Lay the map out and save it: compute everything, paint once, then write.
  //:
  //: The three phases are the point. `wbMapTidyPositions` touches nothing;
  //: `wbApplyBulkMove` moves every element in one pass; `wbSaveBulkMove` is the
  //: only part that goes near the network, and it runs after the paint. That is
  //: §8's "auto-layout must run off the paint path", and it reuses the two
  //: functions a multi-item drag already uses rather than writing a third way to
  //: move a set of things.
  const wbMapTidy = wbRecorded("wbMapTidy",
  async function wbMapTidy({ onlyBranch = null, quiet = false } = {}) {
    if (!wbIsMap()) return 0;
    const layout = wbMapLayout();
    if (!wbMapLaysOut()) {
      if (!quiet) toast("This map's layout is Free, pick a layout to tidy it.");
      return 0;
    }
    const origin = wbMapTidyOrigin(onlyBranch, layout);
    if (!origin.size) return 0;
    // Zero delta, because each entry already carries its own target, the
    // bulk-move helper adds `dx`/`dy` to the origin it was given, so handing it
    // the destinations and no delta is how one shared helper does a per-node
    // layout as well as a rigid drag.
    wbApplyBulkMove(origin, 0, 0);
    renderWhiteboardNow();
    //: **A tidy that pushed the map off the canvas frames it again.** Recorded
    //: by the seventh run and left as a decision rather than a bug: measured at
    //: 390x844 after a tidy, the trunk's own box sat at x=-95 and
    //: `elementFromPoint` at its centre returned the shell behind the canvas, so
    //: the one node a person would reach for was not on screen. §12.0 says
    //: auto-arrange is a command and not a constant, which is why this does not
    //: frame on every tidy: it frames only a *whole-map* tidy, and only when
    //: something has actually gone past an edge. A branch tidy is the silent
    //: half of pressing Tab and must never move the view while someone is
    //: typing, and a tidy whose result already fits is a view nobody asked to
    //: have changed.
    if (onlyBranch == null && wbMapSpillsOffCanvas()) wbFrameSpilledMap();
    await wbSaveBulkMove(origin);
    return origin.size;
  });

  //: The moves a tidy would make, as a bulk-move origin, touching nothing
  //: (`wbMapTidy` applies, paints and saves them; the optimistic add applies
  //: them and leaves the paint to its one render).
  function wbMapTidyOrigin(onlyBranch, layout = wbMapLayout()) {
    const index = wbMapIndex();
    const positions = wbMapTidyPositions(index, layout);
    const origin = new Map();
    if (!positions.size) return origin;

    // Which nodes this run is allowed to move. A branch tidy (after adding a
    // child) touches only that branch, so the rest of the map does not jump
    // under you while you are typing into a new node.
    const scope = onlyBranch != null
      ? new Set(wbMapSubtree(index, onlyBranch).map((o) => o.id))
      : null;

    for (const [id, pos] of positions) {
      const obj = index.byId.get(id);
      if (!obj) continue;
      if (scope && !scope.has(id)) continue;
      // **A dragged node is pinned, and a pinned node keeps its place.** That is
      // Coggle's bargain: tidy is on demand, and anything you positioned by hand
      // is a decision, not a thing to be undone by the next tidy. Its children
      // still take their tidy positions, the fold is in the branch, not the
      // whole map.
      if (obj.data?.pinned) continue;
      //: **A branch under a pinned topic is tidied where that topic sits** (the
      //: owner, 2026-10-11: a child added under a dragged topic took the
      //: layout's own column, 1,400px away, with its line across the map). Its
      //: tidy place is shifted by how far the nearest pinned ancestor was
      //: dragged from its own, so the branch keeps its shape beside it.
      let ancestor = obj.parent_id != null ? index.byId.get(obj.parent_id) : null;
      for (let hops = 0; ancestor && !ancestor.data?.pinned && hops < 200; hops++) {
        ancestor = ancestor.parent_id != null ? index.byId.get(ancestor.parent_id) : null;
      }
      const home = ancestor ? positions.get(ancestor.id) : null;
      const to = home ? { x: pos.x + (ancestor.x - home.x), y: pos.y + (ancestor.y - home.y) } : pos;
      if (Math.abs(obj.x - to.x) < 0.5 && Math.abs(obj.y - to.y) < 0.5) continue;
      origin.set(wbMultiKey("object", id), { kind: "object", id, item: obj, x: to.x, y: to.y });
    }
    return origin;
  }

  //: A whole-map tidy that spilled fits the map, as it always did; only a narrow
  //: canvas (`wbMapFrameScales`) takes the phone frame, where a fit reads at 4px.
  //: On desktop `wbFrameMapOnOpen` would jump a large map to its root at 1:1
  //: instead of showing all of it.
  function wbFrameSpilledMap() {
    const container = document.getElementById("whiteboard-container");
    if (container && wbMapFrameScales(container).open < 1) wbFrameMapOnOpen();
    else wbZoomToFit({ animate: false });
  }

  //: Is any part of the map outside the canvas right now? Read off the rendered
  //: boxes rather than off the stored coordinates, because what matters is what
  //: is on screen at the zoom in force, which is the thing the report was about.
  function wbMapSpillsOffCanvas() {
    const container = document.getElementById("whiteboard-container");
    if (!container) return false;
    const box = container.getBoundingClientRect();
    let spilled = false;
    for (const el of document.querySelectorAll("#wb-html-layer .wb-object")) {
      const r = el.getBoundingClientRect();
      if (r.width === 0 && r.height === 0) continue;
      if (r.left < box.left || r.top < box.top || r.right > box.right || r.bottom > box.bottom) {
        spilled = true;
        break;
      }
    }
    return spilled;
  }

  //: The add's tidy (`wbMapAddChild`): the branch's moves, with the new topic
  //: placed directly (it has no element yet for a move to carry), or null on a
  //: Free map, where a new topic stays where it was put.
  function wbMapTidyBranchPlan(parentId, fresh) {
    if (!wbIsMap() || !wbMapLaysOut()) return null;
    const layout = wbMapLayout();
    const origin = wbMapTidyOrigin(wbMapTidyBranchScope(parentId), layout);
    const own = origin.get(wbMultiKey("object", fresh.id));
    if (own) {
      fresh.x = own.x;
      fresh.y = own.y;
      origin.delete(wbMultiKey("object", fresh.id));
    }
    //: Every moved topic's element from one walk of the layer, not one
    //: document-wide query each (93ms of a Tab at 301 topics, profiled).
    if (origin.size) {
      const byId = new Map();
      for (const el of document.querySelectorAll("#wb-html-layer .wb-object[data-id]")) byId.set(el.dataset.id, el);
      for (const entry of origin.values()) entry.el = byId.get(String(entry.id)) || null;
    }
    return origin;
  }

  //: Copy a branch: this topic and everything under it, as a sibling of itself.
  //:
  //: Built from the node endpoint rather than from the board's copy/paste,
  //: which works on a flat selection and would paste ten unrelated boxes where
  //: a branch was. Parents before children (`wbMapSubtree` returns them in that
  //: order), so every child's new parent already exists by the time it is
  //: created: an old id maps to a new one exactly once.
  const wbMapCopyBranch = wbRecorded("wbMapCopyBranch",
  async function wbMapCopyBranch(id) {
    const index = wbMapIndex();
    const source = index.byId.get(id);
    if (!source) return;
    const subtree = wbMapSubtree(index, id);
    if (subtree.length > WB_MAP_COPY_MAX) {
      toast(`That branch has ${nounCount(subtree.length, "topic")}: copying stops at ${WB_MAP_COPY_MAX}.`, "info");
      return;
    }
    const mapped = new Map();
    for (const node of subtree) {
      const parentId = node.id === id
        ? (index.byId.has(node.parent_id) ? node.parent_id : null)
        : mapped.get(node.parent_id);
      // A child whose parent failed to copy has nowhere to go: stop rather than
      // scattering the rest of the branch at the top level.
      if (node.id !== id && parentId == null) break;
      const created = await wbMapCreateNode({
        parentId: parentId ?? null,
        kind: node.kind,
        text: wbMapLabel(node),
        refId: node.data?.ref_id ?? null,
      });
      if (!created) break;
      // The copy looks like the original: the styling lives in `data` and the
      // create endpoint only takes a label, so it is written straight after.
      const style = {};
      for (const key of [...WB_MAP_STYLE_KEYS, ...WB_MAP_CONTENT_KEYS]) {
        if (node.data?.[key] != null) style[key] = node.data[key];
      }
      if (Object.keys(style).length) {
        created.data = { ...created.data, ...style };
        await wbSaveObject(created);
      }
      mapped.set(node.id, created.id);
    }
    await wbMapTidy({ quiet: true });
    renderWhiteboardNow();
    const rootCopy = mapped.get(id);
    if (rootCopy) selectWbItem("object", rootCopy);
    toast(`Copied ${nounCount(mapped.size, "topic")}.`);
  });

  //: A branch big enough that copying it is a mistake rather than an intention.
  //: One POST per node (there is no bulk create), so a thousand-node branch
  //: would be a thousand requests: the same shape `wbSaveBulkMove` already
  //: pays for, and the reason a cap is kinder than a progress bar here.
  const WB_MAP_COPY_MAX = 120;

  //: What a copy carries that "back to the branch" must **not** drop: a picture
  //: in a topic (§12.1 item 2's fourth) is content, not a look. Reset's whole
  //: promise is that it is the safe way out of a topic you have over-decorated,
  //: and a reset that also threw away the picture somebody uploaded would make
  //: it the one control on this map you cannot press to find out what it does.
  //: Two lists rather than one flag, because the two questions are different
  //: ones and a boolean beside each key would be read as neither.
  //: A task (decision 15) is content for the same reason: "reset this topic's
  //: look" must not untick or un-task anything.
  //: And a note (decision 18): a reset is about looks, never about words.
  //: And a boundary and a summary (decisions 19, 20): what the map says.
  const WB_MAP_CONTENT_KEYS = [
    "image", "task", "note", "boundary", "boundary_label", "boundary_set", "summary", "summary_span",
    "priority", "progress", "flag", "markers", "due", "due_time", "start", "recording", "branch_layout", "callout", "labels", "stamps", "stamped",
  ];

  //: Remove this topic and keep its branch: the children move up to its parent
  //: first, then the node goes. Through `/move`, which is the only endpoint
  //: that runs the cycle check (`wbMapOutdent`'s own comment), and children
  //: first so a failure leaves the branch attached to something rather than
  //: orphaned under a node that no longer exists.
  //: One Undo step on the board's history (INBOX 898): the rows and the map's
  //: settings are compared before and after, whatever the act wrote.
  const wbMapRemoveKeepingBranch = wbRecorded("wbMapRemoveKeepingBranch",
  function wbMapRemoveKeepingBranch(...args) {
    return wbMapRemoveKeepingBranchNow(...args);
  });

  async function wbMapRemoveKeepingBranchNow(id) {
    const boardId = window.currentBoardId;
    const index = wbMapIndex();
    const node = index.byId.get(id);
    if (!boardId || !node) return;
    const children = index.childrenOf.get(id) || [];
    // The last-topic rule, at this door too: removing the only topic on the map
    // empties it, and §12.0 says a map is never empty.
    if (!children.length && wbMapDeleteEmptiesMap(id)) {
      wbMapRefuseLastTopic();
      return;
    }
    const parentId = index.byId.has(node.parent_id) ? node.parent_id : null;
    try {
      //: The whole branch in one request when there is more than one child: the
      //: half-moved branch a failure used to leave behind is the reason
      //: `move-many` exists. One child is still one `/move`, which says what it
      //: did in its own event rather than as a batch of one.
      if (children.length > 1) {
        const moved = await apiJson(`/whiteboard/boards/${boardId}/nodes/move-many`, {
          method: "PUT",
          body: JSON.stringify({
            moves: children.map((child) => ({ id: child.id, reparent: true, parent_id: parentId })),
          }),
        });
        for (const after of moved || []) Object.assign(index.byId.get(after.id) || {}, after);
      } else {
        for (const child of children) {
          const after = await apiJson(`/whiteboard/boards/${boardId}/nodes/${child.id}/move`, {
            method: "PUT",
            body: JSON.stringify({ parent_id: parentId }),
          });
          Object.assign(child, after);
        }
      }
    } catch (err) {
      toast(err.message || voiceLine("failed", { what: "move that branch up" }), true);
      return;
    }
    await wbMapDeleteSubtree(id);
    await wbMapTidyBranch(parentId);
  }

  //: Sever (§12.1 item 9): cut a topic free of its parent so it becomes a trunk
  //: of its own, branch and all. `parent_id: null` is a move the endpoint
  //: already supports; floating topics are allowed by §12.0 ("multiple roots
  //: are allowed"), so this needs no new rule, only a way to ask for it.
  //: One Undo step on the board's history (INBOX 898): the rows and the map's
  //: settings are compared before and after, whatever the act wrote.
  const wbMapSever = wbRecorded("wbMapSever",
  function wbMapSever(...args) {
    return wbMapSeverNow(...args);
  });

  async function wbMapSeverNow(id) {
    const boardId = window.currentBoardId;
    const index = wbMapIndex();
    const node = index.byId.get(id);
    if (!boardId || !node) return;
    if (node.parent_id == null || !index.byId.has(node.parent_id)) {
      toast("This topic is already a trunk of its own.");
      return;
    }
    const oldParent = node.parent_id;
    try {
      const moved = await apiJson(`/whiteboard/boards/${boardId}/nodes/${id}/move`, {
        method: "PUT",
        body: JSON.stringify({ parent_id: null }),
      });
      Object.assign(node, moved);
    } catch (err) {
      toast(err.message || voiceLine("failed", { what: "cut that topic free" }), true);
      return;
    }
    // A severed topic keeps the colour it had as part of the branch it left,
    // which would be a lie about where it belongs: it is its own trunk now, so
    // it starts the palette again like every other trunk's children do.
    if (node.data?.color) await wbMapSetNodeStyle(node, { color: null });
    await wbMapTidyBranch(oldParent);
    renderWhiteboardNow();
    toastAction("Cut free as its own trunk.", "Put it back", () => wbUndo());
  }

  //: **"Use this look for its level"** (decision 41, Illustrator's Redefine
  //: graphic style). The topic's own level fields go into its level's look and
  //: off the topic, so it and every topic at that level that was never told
  //: otherwise draw alike. One gesture (`WB_RECORDED`), so one Undo step.
  const wbMapUseLookForLevel = wbRecorded("wbMapUseLookForLevel",
  async function wbMapUseLookForLevel(id) {
    const node = (wbState.objects || []).find((o) => o.id === id);
    const level = wbMapLevelOf(node);
    if (!node || level === undefined) return;
    const levels = JSON.parse(JSON.stringify(wbMapTheme().levels || {}));
    const look = { ...(levels[String(level)] || {}) };
    const patch = {};
    for (const field of WB_MAP_LEVEL_FIELDS) {
      let value = node.data?.[field];
      if (value === undefined || value === null || value === "") continue;
      //: A topic's fill words are not a level's: its tint is `self`, and a
      //: branch fill is a cascade, which is the branch's and not a level's.
      if (field === "fill") {
        if (value === "branch") continue;
        if (value === "self") value = "tint";
      }
      //: Size 0 is the pin for "the app's own size", which a level says by
      //: saying nothing.
      if (field === "font_size" && !value) {
        delete look.font_size;
      } else {
        look[field] = value;
      }
      patch[field] = null;
    }
    if (!Object.keys(patch).length) {
      toast("This topic has no look of its own to give its level.");
      return;
    }
    levels[String(level)] = look;
    await wbMapSetTheme({ levels });
    await wbMapSetNodeStyle(node, patch);
    renderWhiteboardNow();
    toast(`Every one of ${WB_MAP_LEVEL_NAMES[level]} that was never given its own look now looks like this.`);
  });

  // whiteboard-map-waypoints.js: whiteboard-map-waypoints.js: map line waypoints, cross-link handles and their me (moved out, L286).
  //: Turn a cross-link around. The row's two ends swap, which is the whole of
  //: it: a cross-link is not stored on either topic, so nothing in the tree
  //: moves and nothing has to be tidied. The anchors swap with them, or a line
  //: turned around would leave from the edge its far end used to arrive at.
  //: One Undo step on the board's history (INBOX 898): the rows and the map's
  //: settings are compared before and after, whatever the act wrote.
  const wbMapReverseCrossLink = wbRecorded("wbMapReverseCrossLink",
  function wbMapReverseCrossLink(...args) {
    return wbMapReverseCrossLinkNow(...args);
  });

  async function wbMapReverseCrossLinkNow(sketchId) {
    const info = wbMapCrossLinkInfo(sketchId);
    if (!info) return;
    const data = {
      ...info.data,
      sourceId: info.data.targetId,
      targetId: info.data.sourceId,
      sourceKind: info.data.targetKind,
      targetKind: info.data.sourceKind,
      sourceAnchor: info.data.targetAnchor,
      targetAnchor: info.data.sourceAnchor,
    };
    const sketch = info.sketch;
    try {
      //: The whole row, not the one field: `PUT /sketches/{id}` takes a
      //: `WhiteboardSketchBase`, so a body of `{data}` alone is a 422 rather
      //: than a partial update.
      const saved = await apiJson(`/whiteboard/sketches/${sketchId}`, {
        method: "PUT",
        body: JSON.stringify({
          data: JSON.stringify(data), board_id: sketch.board_id,
          x: sketch.x, y: sketch.y, z: sketch.z, group_id: sketch.group_id ?? null,
        }),
      });
      Object.assign(info.sketch, saved);
    } catch (err) {
      toast(err.message || voiceLine("failed", { what: "turn that cross-link around" }), true);
      return;
    }
    renderWhiteboardNow();
    toast("Turned the cross-link around.");
  }

  //: **A cross-link promoted to a branch** (§13c). The one action that teaches
  //: the difference between the map's two kinds of connection by undoing a
  //: choice the gesture made for you: `wbMapJoinByLink` decides between the two
  //: from whether the far end is already in the tree, which is invisible, so
  //: this is the way back for the case it guessed wrong. The far end moves
  //: under the near one, its own branch comes with it, and the cross-link row
  //: goes: keeping it would draw a dashed line over the branch it just became.
  //: One Undo step on the board's history (INBOX 898): the rows and the map's
  //: settings are compared before and after, whatever the act wrote.
  const wbMapCrossLinkToBranch = wbRecorded("wbMapCrossLinkToBranch",
  function wbMapCrossLinkToBranch(...args) {
    return wbMapCrossLinkToBranchNow(...args);
  });

  async function wbMapCrossLinkToBranchNow(sketchId) {
    const info = wbMapCrossLinkInfo(sketchId);
    if (!info) return;
    const { source, target, index } = info;
    const descendants = new Set(wbMapSubtree(index, target.id).map((o) => o.id));
    if (descendants.has(source.id)) {
      toast(`"${wbMapLabel(source)}" is already under "${wbMapLabel(target)}": turn the cross-link around first.`, "info");
      return;
    }
    if (!(await wbMapTransplant(target, source.id, false, { via: "link" }))) return;
    try {
      await apiJson(`/whiteboard/sketches/${sketchId}`, { method: "DELETE" });
      wbState.sketches = (wbState.sketches || []).filter((x) => x.id !== sketchId);
    } catch (err) {
      toast(err.message || "The branch was made, but the cross-link is still there.", true);
    }
    await wbRefreshMapState();
    renderWhiteboardNow();
  }

  //: Cut a cross-link: the row goes and neither topic is touched, which is the
  //: difference between this and cutting a branch (that one re-parents).
  //: One Undo step on the board's history (INBOX 898): the rows and the map's
  //: settings are compared before and after, whatever the act wrote.
  const wbMapCutCrossLink = wbRecorded("wbMapCutCrossLink",
  function wbMapCutCrossLink(...args) {
    return wbMapCutCrossLinkNow(...args);
  });

  async function wbMapCutCrossLinkNow(sketchId) {
    const info = wbMapCrossLinkInfo(sketchId);
    if (!info) return;
    try {
      await apiJson(`/whiteboard/sketches/${sketchId}`, { method: "DELETE" });
    } catch (err) {
      toast(err.message || voiceLine("failed", { what: "cut that cross-link" }), true);
      return;
    }
    wbState.sketches = (wbState.sketches || []).filter((x) => x.id !== sketchId);
    await wbRefreshMapState();
    renderWhiteboardNow();
    toast("Cut the cross-link. Both topics kept their branches.");
  }

  //: Turn a line around: the topic below becomes the one above.
  //:
  //: Two moves, in this order, and the order is the whole of it. Moving the
  //: parent under the child while the child is still under the parent is
  //: exactly the ring `/move`'s cycle check refuses, so the child is lifted to
  //: the parent's own parent first: after that neither is a descendant of the
  //: other and the second move is an ordinary re-parent.
  //: One Undo step on the board's history (INBOX 898): the rows and the map's
  //: settings are compared before and after, whatever the act wrote.
  const wbMapReverseEdge = wbRecorded("wbMapReverseEdge",
  function wbMapReverseEdge(...args) {
    return wbMapReverseEdgeNow(...args);
  });

  async function wbMapReverseEdgeNow(childId) {
    const boardId = window.currentBoardId;
    const index = wbMapIndex();
    const child = index.byId.get(childId);
    const parent = child ? index.byId.get(child.parent_id) : null;
    if (!boardId || !child || !parent) return;
    const grandparent = index.byId.has(parent.parent_id) ? parent.parent_id : null;
    const move = (id, parentId) => apiJson(
      `/whiteboard/boards/${boardId}/nodes/${id}/move`,
      { method: "PUT", body: JSON.stringify({ parent_id: parentId }) }
    );
    try {
      Object.assign(child, await move(child.id, grandparent));
      Object.assign(parent, await move(parent.id, child.id));
    } catch (err) {
      toast(err.message || voiceLine("failed", { what: "turn that line around" }), true);
      return;
    }
    await wbMapTidy({ quiet: true });
    renderWhiteboardNow();
    toast("Turned the line around.");
  }

  //: Change the layout, then lay the map out in it. Changing a layout without
  //: applying it would leave the picker saying "tree-down" over a map still
  //: arranged sideways, which is a control that reports a state the screen
  //: disagrees with: the shape of bug this app has been bitten by repeatedly.
  //: One Undo step on the board's history (INBOX 898): the rows and the map's
  //: settings are compared before and after, whatever the act wrote.
  const wbMapSetLayout = wbRecorded("wbMapSetLayout",
  function wbMapSetLayout(...args) {
    return wbMapSetLayoutNow(...args);
  });

  //: `quiet`: the caller has just said which layout it wants (a template), so
  //: "Laid out 7 nodes" would only cover the map it drew (blind test 1031, 390px).
  async function wbMapSetLayoutNow(layout, { quiet = false } = {}) {
    const boardId = window.currentBoardId;
    if (!boardId || !wbIsMap()) return;
    try {
      await apiJson(`/whiteboard/boards/${boardId}`, {
        method: "PUT",
        body: JSON.stringify({ layout }),
      });
      window.wbMapState = { ...window.wbMapState, layout };
      wbSyncMapChrome();
      const moved = await wbMapTidy({ quiet: true });
      renderWhiteboardNow();
      if (quiet) return;
      toast(layout === "free"
        ? "Layout set to Free, nodes stay where you put them."
        : `Laid out ${nounCount(moved, "node")}.`);
    } catch (err) {
      toast(err.message || voiceLine("failed", { what: "change the layout" }), true);
    }
  }

  //: The file's surface: what other files call (L-whiteboard-49).
  Object.assign(window, { wbMapSetTheme, wbMapClearEveryTopic, wbMapMoveAmongSiblings, wbMapSortChildren, wbMapSetNumbered, wbMapExpandAll, wbMapFoldToLevel, wbMapInsertBetween, wbMapAddChild, wbMapAddRootAt, wbMapAddReference, wbMapDuplicateTopic, wbMapOutdent, wbMapClearToOneTopic, wbMapToggleCollapse, wbMapTidy, wbMapCopyBranch, wbMapRemoveKeepingBranch, wbMapSever, wbMapUseLookForLevel, wbMapReverseCrossLink, wbMapCrossLinkToBranch, wbMapCutCrossLink, wbMapReverseEdge, wbMapSetLayout });
})();
