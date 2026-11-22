(() => {
  // whiteboard-tree.js: the mind-map tree on a board, moved out of whiteboard.js (L634).
  // Wrapped: only what other files call goes on `window`; nothing here runs at load.

  //: Mind-mapping (ROADMAP item 25): "Arrange as mind map" auto-positions
  //: everything reachable from a selected card via the whiteboard's own
  //: links into a Tree or Radial layout, reusing the Graph tab's own
  //: `d3.hierarchy`/`d3.tree` approach (see `layoutHierarchy` above) rather
  //: than a second layout engine, just against the whiteboard's plain
  //: node/link data instead of the notebook's category/reply structure (no
  //: categories here, so none of that grouping machinery is needed). A link
  //: graph isn't necessarily a tree, cycles, a card linked to two others
  //: that are themselves linked, so a BFS from the root turns whatever is
  //: reachable into a real spanning tree (first link found wins the "parent"
  //: slot), which is the only sense "arrange everything connected to it" can
  //: have for a layout that needs one parent per node.
  const WB_MINDMAP_TREE_ROW = 170;
  const WB_MINDMAP_TREE_COL = 320;
  const WB_MINDMAP_RADIAL_STEP = 260;

  //: The undirected adjacency every mind-map operation starts from, every
  //: link sketch touching two *currently real* nodes (a stale link to an
  //: already-deleted card is silently excluded, same as the render path
  //: already does).
  function wbLinkAdjacency() {
    const adjacency = new Map();
    const addEdge = (a, b) => {
      if (!adjacency.has(a)) adjacency.set(a, new Set());
      if (!adjacency.has(b)) adjacency.set(b, new Set());
      adjacency.get(a).add(b);
      adjacency.get(b).add(a);
    };
    const nodeIds = new Set(wbState.nodes.map((n) => n.id));
    for (const sketch of wbState.sketches) {
      let parsed;
      try {
        parsed = JSON.parse(sketch.data);
      } catch {
        continue;
      }
      if (!parsed.type || !parsed.type.startsWith("link-")) continue;
      if (nodeIds.has(parsed.sourceId) && nodeIds.has(parsed.targetId)) addEdge(parsed.sourceId, parsed.targetId);
    }
    return adjacency;
  }

  //: A BFS spanning tree from `rootId`, in the `{parentOf, childrenOf}` shape
  //: both `wbArrangeMindMap` and the Tab/Enter branch-entry commands share.
  function wbMindMapSpanningTree(rootId) {
    const adjacency = wbLinkAdjacency();
    const parentOf = new Map([[rootId, null]]);
    const childrenOf = new Map([[rootId, []]]);
    const queue = [rootId];
    while (queue.length) {
      const current = queue.shift();
      for (const neighbour of adjacency.get(current) || []) {
        if (parentOf.has(neighbour)) continue;
        parentOf.set(neighbour, current);
        childrenOf.get(current).push(neighbour);
        childrenOf.set(neighbour, []);
        queue.push(neighbour);
      }
    }
    return { parentOf, childrenOf };
  }

  async function wbArrangeMindMap(rootId, kind) {
    const root = wbState.nodes.find((n) => n.id === rootId);
    if (!root) return;
    const { parentOf, childrenOf } = wbMindMapSpanningTree(rootId);
    if (parentOf.size < 2) {
      toast("Nothing linked to this card to arrange.");
      return;
    }

    // d3.hierarchy wants a tree of plain objects with a `children` accessor: 
    // built once, keyed by node id, the same shape `layoutHierarchy` above
    // builds from `children`/`groups`.
    const buildTree = (id) => ({ id, children: (childrenOf.get(id) || []).map(buildTree) });
    const laid = d3.hierarchy(buildTree(rootId));

    const positions = new Map();
    if (kind === "radial") {
      // Same `d3.tree().size([2*Math.PI, 1])` call `layoutHierarchy`'s own
      // radial branch uses; ring spacing is a plain fixed step per depth
      // here rather than that function's label-aware `radialRings` sizing,
      // since a mind map has no per-ring label-width category to budget for.
      d3.tree().size([2 * Math.PI, 1])(laid);
      laid.each((point) => {
        const radius = point.depth * WB_MINDMAP_RADIAL_STEP;
        positions.set(point.data.id, {
          x: radius * Math.cos(point.x - Math.PI / 2),
          y: radius * Math.sin(point.x - Math.PI / 2),
        });
      });
    } else {
      d3.tree().nodeSize([WB_MINDMAP_TREE_ROW, WB_MINDMAP_TREE_COL])(laid);
      laid.each((point) => {
        positions.set(point.data.id, { x: point.depth * WB_MINDMAP_TREE_COL, y: point.x });
      });
    }

    // The layout is computed around (0,0) at the root, shift the whole
    // result so the root card itself doesn't move, only what's connected to
    // it, which is what "arrange everything connected to it" (not "recentre
    // my board") actually asked for.
    const rootPos = positions.get(rootId);
    const dx = root.x - rootPos.x, dy = root.y - rootPos.y;
    const rows = [];
    for (const [id, pos] of positions) {
      if (id === rootId) continue;
      const node = wbState.nodes.find((n) => n.id === id);
      if (!node) continue;
      node.x = wbSnap(pos.x + dx);
      node.y = wbSnap(pos.y + dy);
      rows.push({ kind: "node", item: node });
    }
    await wbSaveMany(rows);

    // Cached for the Tab/Enter branch-entry commands below, so a card added
    // right after an arrange lands in the layout it was just shown, not a
    // freshly re-derived (and possibly different, since BFS parent choice
    // isn't unique when a card has more than one link back toward the root)
    // spanning tree.
    window.wbMindMap = { rootId, parentOf, childrenOf, kind };
    wbScheduleRender();
    toast(`Arranged ${nounCount(parentOf.size, "card")} as a ${kind === "radial" ? "radial" : "tree"} mind map.`);
  }

  //: Tab/Enter branch entry (item 25's second piece) needs to know a card's
  //: "parent" in mind-map terms, which a whiteboard link doesn't carry on its
  //: own (just two ids, no direction). Reuses the cached map from a prior
  //: `wbArrangeMindMap` run when the given card is part of it; otherwise
  //: seeds one lazily, rooted at the card itself, from the board's current
  //: links: so Tab/Enter still work sensibly on a board nobody has arranged
  //: yet, not only right after clicking Tree/Radial.
  function wbMindMapEnsureMap(fromId) {
    if (!window.wbMindMap || !window.wbMindMap.parentOf.has(fromId)) {
      const { parentOf, childrenOf } = wbMindMapSpanningTree(fromId);
      window.wbMindMap = { rootId: fromId, parentOf, childrenOf, kind: window.wbMindMap?.kind || "radial" };
    }
    return window.wbMindMap;
  }

  //: Creates a real note, a whiteboard card for it, and a link from
  //: `parentId`, the one operation both Tab and Enter reduce to, differing
  //: only in which card counts as the parent.
  async function wbMindMapAddCard(parentId, x, y) {
    const entry = await apiJson("/entries", { method: "POST", body: JSON.stringify({ content: "New branch", map_topic: true, defer_filing: true }) });
    wbPushUndo({ action: "noteMade", entryId: entry.id });
    const nodeRes = await apiJson("/whiteboard/nodes", {
      method: "POST",
      body: JSON.stringify({ entry_id: entry.id, board_id: window.currentBoardId ?? null, x: wbSnap(x), y: wbSnap(y), z: 1 }),
    });
    wbState.nodes.push(nodeRes);
    const sketchRes = await apiJson("/whiteboard/sketches", {
      method: "POST",
      body: JSON.stringify({
        data: JSON.stringify({
          type: "link-curved",
          sourceId: parentId,
          targetId: nodeRes.id,
          color: window.currentStrokeColor || "#ffffff",
        }),
        x: 0, y: 0, z: 1, board_id: window.currentBoardId ?? null,
      }),
    });
    wbState.sketches.push(sketchRes);

    // The card about to render reads its text out of `allEntries`, which was
    // fetched before this note existed. Without this the new branch renders
    // as a placeholder and never resolves, see the `!entry` branch in the
    // card renderer.
    await refreshEntries([entry.id]);

    const map = wbMindMapEnsureMap(parentId);
    map.parentOf.set(nodeRes.id, parentId);
    if (!map.childrenOf.has(parentId)) map.childrenOf.set(parentId, []);
    map.childrenOf.get(parentId).push(nodeRes.id);
    map.childrenOf.set(nodeRes.id, []);

    selectWbItem("node", nodeRes.id);
    wbScheduleRender();
    // **A new branch is an empty thought, so it opens ready to be typed.**
    // Before this it was a card reading "New branch" and nothing else: the
    // gesture created a node and then left you to find the way to name it,
    // which is the difference between a mind-mapping tool and a diagram
    // editor. `wbScheduleRender` is async, so this waits for the card to
    // exist rather than assuming it does.
    requestAnimationFrame(() => wbEditNodeText(nodeRes.id));
    return nodeRes;
  }

  function wbEditNodeText(nodeId, firstKey = "", whole = null) {
    wbAddGate.cardRetypeId = null;
    const node = wbState.nodes.find((n) => n.id === nodeId);
    if (!node) return;
    const card = wbInstances.query(`.node-card[data-id="${nodeId}"]`);
    const content = card?.querySelector(".wb-card-content");
    if (!content) return;
    const entry = whole || allEntries.find((e) => e.id === node.entry_id);
    //: A clipped row is fetched whole first and edited from what `fullEntry` returns: the editor's text is what gets saved.
    if (entry?.content_truncated) return void fullEntry(entry.id).then((read) => wbEditNodeText(nodeId, firstKey, read), (error) => toast(error.message, true));
    const original = entry?.content || "";

    const box = document.createElement("textarea");
    box.className = "wb-card-editor";
    //: **The app's note engine, not a bare textarea** (DOCUMENTS_PLAN Phase
    //: 8c, the board half). The id is the `NOTE_SURFACES` row, so the focus
    //: below mounts the same editor every other note box has: Live rendering,
    //: the "/" menu, undo, Ctrl+B. One card is edited at a time, which is what
    //: lets the id be fixed.
    box.id = "wb-card-editor";
    box.value = original;
    //: The card's own contract, handed to the engine as keys because once the
    //: view is mounted the textarea never sees a keystroke again: the four
    //: listeners this used to hang off it (Enter, Escape, blur, and the
    //: stopPropagation guard) all went quiet the moment a view sat over it,
    //: which is why this row could not simply be added to the table.
    box.noteSurfaceKeys = [
      { key: "Enter", run: () => { finish(true); return true; } },
      {
        key: "Shift-Enter",
        run: (view) => {
          view.dispatch(view.state.replaceSelection("\n"), { scrollIntoView: true });
          return true;
        },
      },
      { key: "Escape", run: () => { finish(false); return true; } },
    ];
    content.replaceChildren(box);
    box.focus({ preventScroll: true });
    box.select();
    if (firstKey) box.setRangeText(firstKey, 0, box.value.length, "end");

    //: Listeners on the card's content element rather than on the textarea,
    //: so they hold whichever of the two has the focus, and all of them go
    //: with the edit (`signal`), since the content element outlives it.
    const listening = new AbortController();
    let settled = false;
    const finish = async (save) => {
      if (settled) return;
      settled = true;
      listening.abort();
      const text = box.value.trim();
      const keep = save && text ? text : original;
      if (save && text && text !== original) {
        try {
          await apiJson(`/entries/${node.entry_id}`, {
            method: "PUT",
            body: JSON.stringify({ content: text }),
          });
          wbPushUndo({ action: "note", entryId: node.entry_id, content: original });
          // The card reads its text out of `allEntries`; without this the next
          // render would use the old content and the edit would look discarded.
          await loadEntries();
        } catch (err) {
          toast(err.message || voiceLine("failed", { what: "save that" }), true);
        }
      }
      // **Put the text back by hand, not by re-rendering.** Found live: after
      // saving, the textarea was still on the card. `wbScheduleRender` runs a
      // d3 data join, and card *content* is only built in the `enter`
      // selection: an existing card keeps whatever DOM it already has, which
      // here was the editor. So the edit saved correctly to the server and
      // looked like it had done nothing, which is the worst of both.
      content.replaceChildren();
      renderMarkdown(content, keep);
      wbScheduleRender();
      if (save && wbSelectedItem?.kind === "node" && wbSelectedItem.id === nodeId) wbAddGate.cardRetypeId = nodeId;
    };

    // Enter commits, Shift+Enter is a real newline, the convention for a
    // single-idea field. Escape abandons. Blur commits, because clicking away
    // to the next card is the most common way to finish one.
    //
    // This listener is the textarea's half, for the moment before the engine
    // has mounted (the bundle can take a beat on a first card) and for a
    // session where it cannot load; `noteSurfaceKeys` above is the view's half.
    box.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        finish(true);
      } else if (event.key === "Escape") {
        event.preventDefault();
        finish(false);
      } else if (event.key === "Tab") {
        //: A tab in the text, as the engine's Tab indents, rather than the
        //: browser walking the focus out of the card and committing it.
        event.preventDefault();
        box.setRangeText("\t", box.selectionStart, box.selectionEnd, "end");
      }
    }, { signal: listening.signal });
    //: **The guard: a key typed in the card is text, never a board gesture**
    //: (Tab and Enter make branches). On the content element, so it holds for
    //: the view as well as the textarea: a key's bubble passes through here on
    //: its way to the board's document-level handlers either way.
    content.addEventListener("keydown", (event) => event.stopPropagation(), {
      signal: listening.signal,
    });
    //: Blur commits, judged a tick later and against the content element:
    //: mounting the engine moves the textarea into its wrapper, which blurs it
    //: for a moment before the view takes the focus, and that is not the
    //: person clicking away.
    content.addEventListener("focusout", (event) => {
      if (content.contains(event.relatedTarget)) return;
      setTimeout(() => {
        if (!content.contains(document.activeElement)) finish(true);
      }, 0);
    }, { signal: listening.signal });
  }

  //: Tab: a new child of the selected card, at "the next open radial slot":
  //: evenly spaced by angle among the parent's existing children (plus the
  //: one about to be added, so a lone first child doesn't land straight on
  //: top of the parent), one ring further out.
  async function wbMindMapAddChild(parentId) {
    const parent = wbState.nodes.find((n) => n.id === parentId);
    if (!parent) return;
    const map = wbMindMapEnsureMap(parentId);
    const existing = (map.childrenOf.get(parentId) || []).length;
    const slots = Math.max(existing + 1, 3);
    // **Fan out sideways first, not upwards.** The offset used to be
    // `-Math.PI / 2`, straight up, so the very first branch off a root card
    // landed one full ring *above* it. Driven live: a map created at the
    // canvas centre put its first Tab branch off the top edge, clipped and
    // half unreadable, which is a bad first impression of the one gesture the
    // whole feature turns on. Sideways is also how every mind-mapping tool
    // fans a first child, because a page is wider than it is tall.
    const angle = (existing / slots) * 2 * Math.PI;
    const parentBox = wbItemBBox("node", parent);
    const cx = (parentBox.minX + parentBox.maxX) / 2, cy = (parentBox.minY + parentBox.maxY) / 2;
    const w = parent.width || WB_CARD_DEFAULT_SIZE.w, h = parent.height || WB_CARD_DEFAULT_SIZE.h;
    await wbMindMapAddCard(
      parentId,
      cx + WB_MINDMAP_RADIAL_STEP * Math.cos(angle) - w / 2,
      cy + WB_MINDMAP_RADIAL_STEP * Math.sin(angle) - h / 2
    );
  }

  //: Enter: a new sibling of the selected card (a child of *its* parent).
  //: A card with no known parent (the mind map's own root, or one never
  //: linked to anything) has no sibling slot to fill, falls back to adding
  //: a child of the card itself, the only branch that makes sense there.
  async function wbMindMapAddSibling(cardId) {
    const map = wbMindMapEnsureMap(cardId);
    const parentId = map.parentOf.get(cardId);
    await wbMindMapAddChild(parentId == null ? cardId : parentId);
  }

  //: The file's surface: what other files call (L634).
  Object.assign(window, { wbArrangeMindMap, wbMindMapAddCard, wbEditNodeText, wbMindMapAddChild, wbMindMapAddSibling });
})();
