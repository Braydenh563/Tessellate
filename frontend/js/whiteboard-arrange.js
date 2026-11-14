(() => {
  // whiteboard-arrange.js: align, distribute, nudge, size and swap commands.
  // Moved out of whiteboard.js whole (L286) and wrapped: only what other files call goes on `window`; nothing here runs at load.
  //: Resolves `wbMultiSelection` into {kind, id, item, bbox} entries, dropping
  //: anything stale (deleted since selected) or box-less (a link sketch).
  //: Shared by align/distribute/nudge: every one of them needs exactly this.
  function wbSelectionEntries() {
    return [...wbMultiSelection]
      .map((key) => {
        const sep = key.indexOf(":");
        const kind = key.slice(0, sep), id = Number(key.slice(sep + 1));
        const item = (wbState[WB_LIST_BY_KIND[kind]] || []).find((i) => i.id === id);
        return item ? { kind, id, item, bbox: wbItemBBox(kind, item) } : null;
      })
      .filter((e) => e && e.bbox);
  }

  //: Moves one item by (dx, dy): a sketch by transforming its path, anything
  //: else by its own x/y, and returns the "move" undo entry for it. It does not
  //: save: the item goes onto `rows` and the caller saves the whole set once
  //: (`wbCommitMoves`, audit 1031 BD2: a selection is one request, not one per
  //: item). Shared by nudge/align/distribute/tidy, each of which moves a set of
  //: items as one user action and needs one entry per item to bundle into a batch.
  function wbMoveItemBy(kind, id, item, dx, dy, rows) {
    const before = WB_KIND_INFO[kind].payload(item);
    if (kind === "sketch") {
      wbSketchSetD(item, wbTransformPathD(wbSketchParsedData(item).d, { dx, dy }));
    } else {
      item.x = (item.x || 0) + dx;
      item.y = (item.y || 0) + dy;
    }
    rows.push({ kind, item });
    return { action: "move", kind, id, before };
  }

  //: The tail every selection action shares: the changed items saved in one
  //: request, then their undo entries pushed as one step.
  async function wbCommitMoves(rows, entries) {
    //: A refused batch has reloaded the board, so there is nothing to undo.
    if (await wbSaveMany(rows)) wbPushMoveBatch(entries);
  }

  //: Pushes N per-item move entries as the one undo step the user actually
  //: took: a single "batch" entry when more than one item moved, or the bare
  //: entry itself when only one did, so a plain single-item nudge doesn't pay
  //: for the extra indirection.
  function wbPushMoveBatch(entries) {
    if (entries.length === 0) return;
    wbPushUndo(entries.length === 1 ? entries[0] : { action: "batch", entries });
    wbScheduleRender();
  }

  // Alignment tools: asked for directly ("alignment tools... missing"), only
  // meaningful for two or more selected items. Aligns to the selection's own
  // overall bounding box, the same reference every other drawing app uses.
  //: **A key object** (draw.io, Figma "align to key object"): one item of the
  //: selection the others line up to, which itself stays put. Set with the
  //: "Align to this one" command; it holds while it is part of the selection and
  //: clears the moment it is not, so a stale key never moves the wrong thing.
  const wbKey = { object: null };

  function wbSetKeyObject() {
    const key = wbSelectedItem ? wbMultiKey(wbSelectedItem.kind, wbSelectedItem.id) : null;
    if (!key || !wbMultiSelection.has(key) || wbMultiSelection.size < 2) {
      toast("Select two or more items, with the one to line up to selected last.");
      return;
    }
    wbKey.object = wbKey.object === key ? null : key;
    toast(wbKey.object ? "Align commands now line up to this item and leave it where it is." : "Align commands use the whole selection again.");
  }

  //: The reference box and the entries that move. Pure (node-tested): with a
  //: key in the selection its own box is the reference and it is left out;
  //: otherwise the selection's outer box, as before.
  function wbAlignReference(entries, keyId) {
    const key = keyId ? entries.find((e) => `${e.kind}:${e.id}` === keyId) : null;
    if (key) return { box: key.bbox, moving: entries.filter((e) => e !== key) };
    return {
      box: {
        minX: Math.min(...entries.map((e) => e.bbox.minX)), maxX: Math.max(...entries.map((e) => e.bbox.maxX)),
        minY: Math.min(...entries.map((e) => e.bbox.minY)), maxY: Math.max(...entries.map((e) => e.bbox.maxY)),
      },
      moving: entries,
    };
  }

  async function wbAlignSelection(edge) {
    const entries = wbSelectionEntries();
    if (entries.length < 2) {
      toast("Select two or more items to align them.");
      return;
    }
    if (wbKey.object && !entries.some((e) => `${e.kind}:${e.id}` === wbKey.object)) wbKey.object = null;
    const { box, moving } = wbAlignReference(entries, wbKey.object);
    const target = { left: box.minX, right: box.maxX, top: box.minY, bottom: box.maxY,
      hcenter: (box.minX + box.maxX) / 2, vcenter: (box.minY + box.maxY) / 2 }[edge];

    const pushed = [];
    const rows = [];
    for (const e of moving) {
      let dx = 0, dy = 0;
      if (edge === "left") dx = target - e.bbox.minX;
      else if (edge === "right") dx = target - e.bbox.maxX;
      else if (edge === "hcenter") dx = target - (e.bbox.minX + e.bbox.maxX) / 2;
      else if (edge === "top") dy = target - e.bbox.minY;
      else if (edge === "bottom") dy = target - e.bbox.maxY;
      else if (edge === "vcenter") dy = target - (e.bbox.minY + e.bbox.maxY) / 2;
      if (dx === 0 && dy === 0) continue;
      pushed.push(wbMoveItemBy(e.kind, e.id, e.item, dx, dy, rows));
    }
    await wbCommitMoves(rows, pushed);
  }

  // Distribute: asked for as part of the same "alignment tools" request.
  // Needs three or more: the first and last (by leading edge, along the chosen
  // axis) stay put as the two ends, and whatever is between them is placed so
  // that every *gap* is the same.
  //
  // **Gaps, not centres** (WHITEBOARD_PLAN.md §2 item 4, "no
  // distribute-gaps", and decision 3). This spaced centres evenly until now,
  // which is the same thing only when every item is the same size: give three
  // boxes of 100, 300 and 100 an even centre spacing and the gap on one side
  // of the wide one is 100px smaller than the gap on the other, which is
  // exactly the arrangement a person reaches for this button to fix. Figma,
  // Illustrator and tldraw all offer the gap version under this name, and it
  // is the one that makes a row of mixed-width cards look like a row.
  async function wbDistributeSelection(axis) {
    const entries = wbSelectionEntries();
    if (entries.length < 3) {
      toast("Select three or more items to space them evenly.");
      return;
    }
    const minOf = (e) => (axis === "horizontal" ? e.bbox.minX : e.bbox.minY);
    const maxOf = (e) => (axis === "horizontal" ? e.bbox.maxX : e.bbox.maxY);
    entries.sort((a, b) => minOf(a) - minOf(b));
    const first = entries[0];
    const last = entries[entries.length - 1];
    const span = maxOf(last) - minOf(first);
    const used = entries.reduce((sum, e) => sum + (maxOf(e) - minOf(e)), 0);
    // Negative when the items overlap more than the span allows; the result is
    // then an even *overlap*, which is still the honest reading of "space these
    // evenly between the two ends" and is what the other apps do.
    const gap = (span - used) / (entries.length - 1);

    const pushed = [];
    const rows = [];
    let cursor = maxOf(first) + gap;
    for (let i = 1; i < entries.length - 1; i++) {
      const e = entries[i];
      const size = maxOf(e) - minOf(e);
      const delta = cursor - minOf(e);
      cursor += size + gap;
      // Sub-pixel: a move that rounds to nothing is a PUT and an undo entry for
      // no visible change.
      if (Math.abs(delta) < 0.5) continue;
      const dx = axis === "horizontal" ? delta : 0;
      const dy = axis === "horizontal" ? 0 : delta;
      pushed.push(wbMoveItemBy(e.kind, e.id, e.item, dx, dy, rows));
    }
    await wbCommitMoves(rows, pushed);
  }

  //: **A grid of N across** (CHAT_PLAN section 2, the board's acts: "arrange
  //: as a grid of 3" in the command palette, `acts.board_parse`). The selection,
  //: or the whole board when fewer than two are selected, in reading order
  //: (top, then left), into cells the size of the largest item with the paste
  //: grid's gap, from the group's own top-left corner so it stays where it was.
  //: One across is a column, all across a row; one move batch, so Undo takes the
  //: whole arrangement back.
  async function wbArrangeGridSelection(columns) {
    if (wbSelectionEntries().length < 2) wbSelectAllItems();
    const entries = wbSelectionEntries();
    if (entries.length < 2) {
      toast("Select two or more items to arrange them.");
      return;
    }
    const across = Math.max(1, Math.min(entries.length, columns || Math.ceil(Math.sqrt(entries.length))));
    entries.sort((a, b) => a.bbox.minY - b.bbox.minY || a.bbox.minX - b.bbox.minX);
    const width = Math.max(...entries.map((e) => e.bbox.maxX - e.bbox.minX));
    const height = Math.max(...entries.map((e) => e.bbox.maxY - e.bbox.minY));
    const left = Math.min(...entries.map((e) => e.bbox.minX));
    const top = Math.min(...entries.map((e) => e.bbox.minY));
    const { gap } = WB_PASTE_STICKY;
    const pushed = [];
    const rows = [];
    for (const [i, e] of entries.entries()) {
      const dx = left + (i % across) * (width + gap) - e.bbox.minX;
      const dy = top + Math.floor(i / across) * (height + gap) - e.bbox.minY;
      if (Math.abs(dx) < 0.5 && Math.abs(dy) < 0.5) continue;
      pushed.push(wbMoveItemBy(e.kind, e.id, e.item, dx, dy, rows));
    }
    await wbCommitMoves(rows, pushed);
  }

  //: The connectors with both ends in `entries`, as `[from, to]` member keys
  //: (`kind:id`), in the direction each was drawn.
  function wbTidyEdges(entries) {
    const keys = new Set(entries.map((e) => `${e.kind}:${e.id}`));
    const edges = [];
    for (const sketch of wbState.sketches) {
      let p;
      try {
        p = JSON.parse(sketch.data);
      } catch {
        continue;
      }
      if (!p?.type?.startsWith("link-")) continue;
      const from = `${p.sourceKind || "node"}:${p.sourceId}`, to = `${p.targetKind || "node"}:${p.targetId}`;
      if (from !== to && keys.has(from) && keys.has(to)) edges.push([from, to]);
    }
    return edges;
  }

  //: **Tidy as a tree** (draw.io Arrange > Layout > Vertical or Horizontal
  //: tree): the selected boxes in ranks along the connectors between them, top
  //: to bottom (`down`) or left to right. A box no connector points into is a
  //: root; siblings keep the order they had on the board, each box is centred in
  //: a cell the size of the largest, and the whole tree keeps the selection's
  //: top-left corner. One move batch, so Undo takes it all back.
  async function wbTidySelection(direction = "down") {
    const entries = wbSelectionEntries();
    const edges = wbTidyEdges(entries);
    if (entries.length < 2 || !edges.length) {
      toast("Select two or more shapes and the connectors between them to tidy them.");
      return;
    }
    const down = direction === "down";
    const byKey = new Map(entries.map((e) => [`${e.kind}:${e.id}`, e]));
    const along = (key) => (down ? byKey.get(key).bbox.minX : byKey.get(key).bbox.minY);
    const out = new Map(), into = new Map();
    for (const [from, to] of edges) {
      if (!out.has(from)) out.set(from, []);
      out.get(from).push(to);
      into.set(to, (into.get(to) || 0) + 1);
    }
    // Roots first, then anything a cycle left unreached, each in board order.
    const order = [...byKey.keys()].sort((a, b) => along(a) - along(b));
    const seen = new Set();
    const build = (key) => {
      seen.add(key);
      const kids = (out.get(key) || []).filter((k) => !seen.has(k)).sort((a, b) => along(a) - along(b));
      kids.forEach((k) => seen.add(k));
      return { key, children: kids.map(build) };
    };
    const forest = [];
    for (const key of [...order.filter((k) => !into.has(k)), ...order]) if (!seen.has(key)) forest.push(build(key));
    const width = Math.max(...entries.map((e) => e.bbox.maxX - e.bbox.minX));
    const height = Math.max(...entries.map((e) => e.bbox.maxY - e.bbox.minY));
    const gap = WB_PASTE_STICKY.gap;
    const [breadth, rank] = down ? [width + gap * 2, height + gap * 3] : [height + gap * 2, width + gap * 3];
    const laid = d3.tree().nodeSize([breadth, rank])(d3.hierarchy({ children: forest }));
    const points = laid.descendants().filter((n) => n.depth > 0);
    const low = Math.min(...points.map((n) => n.x));
    const left = Math.min(...entries.map((e) => e.bbox.minX));
    const top = Math.min(...entries.map((e) => e.bbox.minY));
    const pushed = [];
    const rows = [];
    for (const n of points) {
      const e = byKey.get(n.data.key);
      const cellX = down ? n.x - low : (n.depth - 1) * rank;
      const cellY = down ? (n.depth - 1) * rank : n.x - low;
      const dx = left + cellX + (width - (e.bbox.maxX - e.bbox.minX)) / 2 - e.bbox.minX;
      const dy = top + cellY + (height - (e.bbox.maxY - e.bbox.minY)) / 2 - e.bbox.minY;
      if (Math.abs(dx) < 0.5 && Math.abs(dy) < 0.5) continue;
      pushed.push(wbMoveItemBy(e.kind, e.id, e.item, dx, dy, rows));
    }
    await wbCommitMoves(rows, pushed);
    toast(`Tidied ${nounCount(entries.length, "item")} as a tree.`);
  }

  //: **Change a shape's kind in place** (draw.io Edit > Edit style > shape,
  //: Excalidraw's shape switch): the four drawn kinds and the shape flyout's
  //: own, each drawn by the code that draws it from the tool, into the box the
  //: shape has now. Text, colours, line and its connectors (bound by id) stay.
  const WB_SHAPE_SWAPS = {
    rect: { label: "Rectangle", icon: "ph:square", d: (x, y, w, h) => `M ${x} ${y} h ${w} v ${h} h ${-w} Z` },
    circle: { label: "Ellipse", icon: "ph:circle", d: (x, y, w, h) => wbEllipseDrawD(x, y, x + w, y + h) },
    triangle: { label: "Triangle", icon: "ph:triangle", d: (x, y, w, h) => `M ${x + w / 2} ${y} L ${x + w} ${y + h} L ${x} ${y + h} Z` },
    diamond: { label: "Diamond", icon: "ph:diamond", d: (x, y, w, h) => `M ${x + w / 2} ${y} L ${x + w} ${y + h / 2} L ${x + w / 2} ${y + h} L ${x} ${y + h / 2} Z` },
    ...Object.fromEntries(Object.entries(WB_MORE_SHAPES).filter(([k]) => k !== "shape-ellipse")),
  };

  //: The one selected closed shape, with its parsed data, or null.
  function wbSwapTarget() {
    if (!wbSelectedItem || wbSelectedItem.kind !== "sketch" || wbMultiSelection.size > 1) return null;
    const item = wbFindItem("sketch", wbSelectedItem.id);
    const parsed = item ? wbSketchParsedData(item) : null;
    return parsed && WB_FILLABLE_SHAPES.has(parsed.shape) ? { item, parsed } : null;
  }

  async function wbChangeShapeKind(kind) {
    const target = wbSwapTarget(), swap = WB_SHAPE_SWAPS[kind];
    if (!target || !swap) return;
    const { item, parsed } = target;
    const box = wbPathBBox(parsed.d);
    const before = WB_KIND_INFO.sketch.payload(item);
    const more = Boolean(WB_MORE_SHAPES[kind]);
    const next = { ...parsed, d: swap.d(box.minX, box.minY, Math.max(box.width, 1), Math.max(box.height, 1)), shape: more ? "custom" : kind };
    delete next.label_area;
    delete next.shapeKind;
    if (more) next.shapeKind = kind;
    if (swap.area) next.label_area = swap.area;
    item.data = JSON.stringify(next);
    await wbSaveSketchProps(item, {});
    wbPushUndo({ action: "move", kind: "sketch", id: item.id, before });
    wbScheduleRender();
    wbAnnounce(`Changed to ${swap.label.toLowerCase()}`);
  }

  //: The kinds as a menu at the More button (or the pointer), the current one
  //: left out.
  function wbOpenShapeSwapMenu(x, y) {
    const target = wbSwapTarget();
    if (!target) return;
    const now = target.parsed.shapeKind || target.parsed.shape;
    const items = Object.entries(WB_SHAPE_SWAPS)
      .filter(([kind]) => kind !== now)
      .map(([kind, swap]) => makeMenuItem(`${swap.icon} ${swap.label}`, `Change to ${swap.label.toLowerCase()}, keeping its text, colours and connectors`, () => wbChangeShapeKind(kind)));
    const at = wbContextMoreWrap()?.getBoundingClientRect();
    openMenuAtPoint(items, "Change the shape", x ?? (at ? at.left : 80), y ?? (at ? at.bottom + 4 : 80));
  }

  //: **Same size**, the third of WHITEBOARD_PLAN decision 3's eleven arrange
  //: actions and the one that had no function at all. Every selected item takes
  //: the largest one's width (or height); the largest rather than the
  //: first-clicked because a marquee selection has no first, and growing to the
  //: biggest never hides content the way shrinking to the smallest can.
  //:
  //: The item keeps its top-left corner: a resize that also moved things would
  //: undo the align someone almost certainly did just before this.
  async function wbSameSizeSelection(dim) {
    const entries = wbSelectionEntries();
    if (entries.length < 2) {
      toast("Select two or more items to give them the same size.");
      return;
    }
    const sizeOf = (e) => (dim === "width" ? e.bbox.maxX - e.bbox.minX : e.bbox.maxY - e.bbox.minY);
    const target = Math.max(...entries.map(sizeOf));
    const pushed = [];
    const rows = [];
    for (const e of entries) {
      const size = sizeOf(e);
      if (size <= 0 || Math.abs(size - target) < 0.5) continue;
      const done = wbSizeItemTo(e, dim, target, target / size, rows);
      if (done) pushed.push(done);
    }
    await wbCommitMoves(rows, pushed);
  }

  //: One item resized, in `wbMoveItemBy`'s shape and for the same reason: the
  //: history's "move" entry carries the item's whole payload, so a resize
  //: undoes through exactly the same PUT a move does (see
  //: `wbApplyHistoryEntry`). A drawn shape is a path, so it scales about its own
  //: top-left corner rather than taking a width field it does not have.
  function wbSizeItemTo(entry, dim, target, factor, rows) {
    const { kind, id, item, bbox } = entry;
    const before = WB_KIND_INFO[kind].payload(item);
    if (kind === "sketch") {
      const parsed = wbSketchParsedData(item);
      if (!parsed) return null;
      const grow = {
        sx: dim === "width" ? factor : 1,
        sy: dim === "height" ? factor : 1,
        anchorX: bbox.minX,
        anchorY: bbox.minY,
      };
      //: A shape the table draws (`shapeKind`, whiteboard-shape-table.js) is drawn again for its new box, not stretched.
      wbSketchSetD(item, wbFmtState.shapeTable?.resized(parsed.d, grow, parsed.shapeKind, wbTransformPathD, wbPathBBox) ?? wbTransformPathD(parsed.d, grow));
    } else {
      // Rounded: both columns are integers on the row, and a card whose stored
      // width is 219.99997 reads back as a different number than it was set to.
      if (dim === "width") item.width = Math.round(target);
      else item.height = Math.round(target);
    }
    rows.push({ kind, item });
    return { action: "move", kind, id, before };
  }

  //: The keyboard's resize (Ctrl+Shift+arrows): every selected item with a box
  //: of its own grows or shrinks by `dw` or `dh`, never under the smallest a
  //: grip allows, through `wbSizeItemTo` so it undoes as a move does.
  async function wbResizeSelectionBy(dw, dh) {
    //: One press at a time: a held key's repeats arrive faster than the save, and each reads the size the last left.
    const prior = wbBoardState.resizeChain || Promise.resolve();
    let release = null;
    wbBoardState.resizeChain = new Promise((resolve) => { release = resolve; });
    await prior;
    try {
      await wbBoardState.resizeOnce(dw, dh);
    } finally {
      release();
    }
  }

  //: The one press, as an object method so the page's global names stay as they were.
  wbBoardState.resizeOnce = async function wbResizeOnce(dw, dh) {
    const dim = dw ? "width" : "height";
    const box = wbFmtBox(wbFmtEntries().filter((e) => !wbIsLocked(e.kind, e.item)));
    const along = box && (dw ? box.maxX - box.minX : box.maxY - box.minY);
    if (along > 0) wbFmtState.keys?.record({ kind: "scale", axis: dw ? "w" : "h", factor: Math.max(8, along + (dw || dh)) / along });
    const delta = dw || dh;
    const pushed = [];
    const rows = [];
    for (const e of wbFmtEntries()) {
      if (!e.bbox || wbIsLocked(e.kind, e.item) || (e.kind === "object" && WB_MAP_KINDS.has(e.item.kind))) continue;
      if (e.kind === "sketch" && !["shape", "line", "arrow"].includes(wbFmtKind(e))) continue;
      const size = dim === "width" ? e.bbox.maxX - e.bbox.minX : e.bbox.maxY - e.bbox.minY;
      const from = e.kind === "sketch" ? size : e.item[dim] || size;
      const target = Math.max(WB_OBJECT_MIN_SIZE, from + delta);
      if (from <= 0 || Math.abs(target - from) < 0.5) continue;
      const done = wbSizeItemTo(e, dim, target, target / from, rows);
      if (done) pushed.push(done);
    }
    //: **One Undo step for a burst of presses** (as the nudge): a press within the burst window on the same
    //: selection saves its rows and leaves the first press's entry, which holds the sizes from before the burst.
    const key = pushed.map((p) => `${p.kind}:${p.id}`).sort().join(",");
    const burst = wbBoardState.resizeBurst;
    const joining = burst && burst.key === key && Date.now() - burst.at < WB_NUDGE_BURST_MS
      && wbUndoStack[wbUndoStack.length - 1] === burst.entry;
    if (joining) {
      burst.at = Date.now();
      await wbSaveMany(rows);
    } else if (await wbSaveMany(rows) && pushed.length) {
      wbPushMoveBatch(pushed);
      wbBoardState.resizeBurst = { key, at: Date.now(), entry: wbUndoStack[wbUndoStack.length - 1] };
    }
    wbScheduleRender();
  };

  // Extract notes (BACKLOG.md §62): the selected note cards' own content IS
  // the "notes-in-context", their combined text is what gets split, and each
  // card is also passed as an explicit source so the new note(s) link back to
  // where they came from, not just to whatever else in the notebook they
  // happen to resemble. Reuses `wbSelectionEntries()`, same as align/
  // distribute above, rather than a second way of reading the selection.
  async function wbExtractNotes() {
    const noteEntries = wbSelectionEntries().filter((e) => e.kind === "node");
    if (noteEntries.length === 0) {
      toast("Select at least one note card to extract from.");
      return;
    }
    const entryIds = [...new Set(noteEntries.map((e) => e.item.entry_id))];
    // A card whose note isn't in `allEntries` yet (created elsewhere, cache
    // not refreshed) is skipped rather than sent as empty text, it still
    // counts as a source id, just contributes nothing to read from. A clipped
    // row is read whole (`fullEntry`).
    const rows = await Promise.all(entryIds.map((id) => allEntries.some((e) => e.id === id) ? fullEntry(id).catch(() => null) : null));
    const text = rows
      .map((row) => row?.content)
      .filter(Boolean)
      .join("\n\n---\n\n");
    if (!text.trim()) {
      toast(voiceLine("failed", { what: "read the selected notes' content: try reloading the Notes tab first" }));
      return;
    }
    openExtractPreview(text, { sourceEntryIds: entryIds });
  }

  // Arrow-key nudge: asked for directly ("allow objects to be moved with
  // arrow keys"). Moves the whole current selection (single item or multi)
  // by one step; the keydown handler in initWhiteboard decides the step size
  // (grid spacing when snap is on, else 1px, 10px with Shift).
  //: **A burst of nudges is one undo step, and one save** (the conventions
  //: pass, 2026-09-23). Holding an arrow key sends thirty presses a second;
  //: each used to push its own undo entry, so taking back a two-second nudge
  //: meant pressing Ctrl+Z sixty times, where Figma, tldraw and PowerPoint
  //: take it back in one. Each press also saved on its own and applied the
  //: server's answer when it came back, so an answer to press one landing
  //: after press three put the item back two pixels (measured: five presses
  //: moved it three). So a burst moves the item on screen at once, pushes one
  //: entry holding where the burst began, and saves once when the keys stop.
  //: A burst ends after a pause, a different selection, or any other undo
  //: step landing on top of it.
  const WB_NUDGE_BURST_MS = 600;
  let wbNudgeBurst = null; // { key, entry, items: [{kind, item}], timer }

  //: The chords a board answers itself while it is on screen, which the app's
  //: global shortcuts step aside for (see app.js, where the chords are read).
  //: Only the ones that collide with an app shortcut are named: Ctrl+Shift+G
  //: (agent mode there, Ungroup here).
  function wbOwnsChord(e) {
    const view = document.getElementById("library-view-whiteboard");
    //: **Read from the markup, never from the layout** (a box or style read; INBOX 1662: the document keydown
    //: was 143ms, 137 of it forced layout, because this ran right after a click had dirtied the page): a view
    //: is shown when it and every ancestor lack `.hidden` (tabs hide that way), and a focused element is in the page.
    if (!view || view.closest(".hidden")) return false;
    const field = document.activeElement;
    const typing = field && (["INPUT", "TEXTAREA"].includes(field.tagName)
      || field.closest("[contenteditable]:not([contenteditable=false])"));
    if (typing) return false;
    //: Every printable key while a new map topic is on its way: it is the
    //: topic's text (`wbMapTypeahead`), not a shortcut.
    if (!e.ctrlKey && !e.metaKey && !e.altKey && e.key.length === 1 && wbMapTypeaheadLive()) return true;
    //: **Bare M is the highlighter on a board, never the "m" quick-nav chord**
    //: (INBOX 445, measured 2026-10-03). Both listeners answered the one key:
    //: the tool changed and the chord armed, so the chord guide's panel opened
    //: over the canvas, took the stroke's pointerup (the stroke was never
    //: saved), and the next tool letter inside the chord's window was read as
    //: a destination: M then D, the diamond, left the board for the Dashboard.
    //: On a map the highlighter does not exist, so the chord keeps the key.
    //: And bare T is the text tool, so the chord's new first key (C23) steps
    //: aside the same way; "m" still arms it on a board's map and everywhere else.
    if (!e.ctrlKey && !e.metaKey && !e.altKey && ["m", "t"].includes(e.key.toLowerCase())) {
      return !wbIsMap();
    }
    //: "/" is the Library search on a board; the app's "/" would jump to the notes search and leave the board.
    if (e.key === "/" && !e.ctrlKey && !e.metaKey && !e.altKey && !e.shiftKey) return true;
    //: Ctrl+Shift+G is Ungroup here (agent mode in the app); Ctrl+Shift+P is
    //: the Format panel here (clip a note in the app, decision 19).
    //: And Ctrl+Shift+V is Paste in place while the board holds a copy.
    return (e.ctrlKey || e.metaKey) && e.shiftKey && !e.altKey
      && (["g", "p"].includes(e.key.toLowerCase()) || (e.key.toLowerCase() === "v" && Boolean(wbClipboard)));
  }

  async function wbFlushNudge() {
    const burst = wbNudgeBurst;
    if (!burst) return;
    wbNudgeBurst = null;
    clearTimeout(burst.timer);
    await wbSaveMany(burst.items);
  }

  function wbNudgeSelection(dx, dy) {
    const entries = wbMultiSelection.size > 0
      ? wbSelectionEntries()
      : wbSelectedItem
        ? (() => {
            const { kind, id } = wbSelectedItem;
            const item = (wbState[WB_LIST_BY_KIND[kind]] || []).find((i) => i.id === id);
            const bbox = item && wbItemBBox(kind, item);
            return item && bbox ? [{ kind, id, item, bbox }] : [];
          })()
        : [];
    if (entries.length === 0) return;
    wbFmtState.keys?.record({ kind: "move", dx, dy });
    const key = entries.map((e) => wbMultiKey(e.kind, e.id)).sort().join(",");
    const joining = wbNudgeBurst && wbNudgeBurst.key === key
      && wbUndoStack[wbUndoStack.length - 1] === wbNudgeBurst.entry;
    if (!joining) {
      wbFlushNudge();
      const moves = entries.map((e) => ({
        action: "move", kind: e.kind, id: e.id, before: WB_KIND_INFO[e.kind].payload(e.item),
      }));
      const entry = moves.length === 1 ? moves[0] : { action: "batch", entries: moves };
      wbPushUndo(entry);
      wbNudgeBurst = { key, entry, items: entries.map((e) => ({ kind: e.kind, item: e.item })), timer: 0 };
    }
    for (const e of entries) {
      if (e.kind === "sketch") {
        const parsed = wbSketchParsedData(e.item);
        if (!parsed) continue;
        parsed.d = wbTransformPathD(parsed.d, { dx, dy });
        e.item.data = JSON.stringify(parsed);
      } else {
        e.item.x = (e.item.x || 0) + dx;
        e.item.y = (e.item.y || 0) + dy;
      }
    }
    wbScheduleRender();
    clearTimeout(wbNudgeBurst.timer);
    wbNudgeBurst.timer = setTimeout(wbFlushNudge, WB_NUDGE_BURST_MS);
  }

  //: The file's surface: what other files call (L286).
  Object.assign(window, { wbSelectionEntries, wbMoveItemBy, wbCommitMoves, wbSetKeyObject, wbAlignSelection, wbDistributeSelection, wbArrangeGridSelection, wbTidyEdges, wbTidySelection, wbSwapTarget, wbOpenShapeSwapMenu, wbSameSizeSelection, wbSizeItemTo, wbResizeSelectionBy, wbExtractNotes, wbOwnsChord, wbFlushNudge, wbNudgeSelection });
})();
