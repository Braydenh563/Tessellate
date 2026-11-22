(() => {
  // whiteboard-clipboard.js: copy, paste and the item grips, moved out of whiteboard.js (L634).
  // Wrapped: only what other files call goes on `window`; nothing here runs at load.

  function wbPointerOnBoard() {
    if (!wbPointerClient) return null;
    return wbClientToBoard(wbPointerClient.clientX, wbPointerClient.clientY);
  }

  //: What a copy of the selection would carry: every selected item a copy can
  //: be made of, with the box they share. Several items now, not one (the
  //: conventions pass: a marquee, Ctrl+C, Ctrl+V gave nothing, so a group
  //: could not be copied at all and Ctrl+D ignored a multi-selection).
  //:
  //: A card is deliberately left out. `POST /whiteboard/nodes` is "one card
  //: per note per board" by design (routes_whiteboard.py's own comment: two
  //: cards for the same note stacked on each other reads as one card that
  //: won't drag properly): POSTing a copy would silently *move* the original
  //: card instead of creating a second one. A link is left out because it is
  //: recomputed from the two things it joins, not a shape of its own.
  function wbCopyableSelection({ quiet = false } = {}) {
    const entries = wbMultiSelection.size > 0
      ? wbSelectionEntries()
      : (() => {
          if (!wbSelectedItem) return [];
          const { kind, id } = wbSelectedItem;
          const item = (wbState[WB_LIST_BY_KIND[kind]] || []).find((i) => i.id === id);
          const bbox = item && wbItemBBox(kind, item);
          return item && bbox ? [{ kind, id, item, bbox }] : [];
        })();
    if (entries.length === 0) return null;
    const items = [];
    const picked = [];
    let cards = 0;
    const box = { minX: Infinity, minY: Infinity, maxX: -Infinity, maxY: -Infinity };
    for (const e of entries) {
      if (e.kind === "node") { cards++; continue; }
      if (e.kind === "sketch" && wbIsLinkSketch(e.item)) picked.push(e);
      else items.push({ kind: e.kind, key: `${e.kind}:${e.id}`, payload: WB_KIND_INFO[e.kind].payload(e.item) });
      box.minX = Math.min(box.minX, e.bbox.minX);
      box.minY = Math.min(box.minY, e.bbox.minY);
      box.maxX = Math.max(box.maxX, e.bbox.maxX);
      box.maxY = Math.max(box.maxY, e.bbox.maxY);
    }
    const links = wbCopiedLinks(new Set(items.map((i) => i.key)), new Set(picked.map((e) => e.id)));
    if (items.length + links.length === 0) {
      if (!quiet && cards) toast("A note card can't be copied: drag it, or drop the note again from the Library.");
      else if (!quiet && picked.length) toast("A link between things left behind can't be copied: copy the things it connects.");
      return null;
    }
    return { items: items.concat(links), things: items.length, box, board: window.currentBoardId ?? 0 };
  }

  function wbIsLinkSketch(sketch) {
    return /"type"\s*:\s*"link-/.test(sketch.data || "");
  }

  //: The links that go with a copy: every link between two copied things (the
  //: owner, 2026-10-26: copying several things lost the links between them),
  //: and a selected link with one free end whose attached end is copied. A
  //: link to a thing left behind is dropped, not left pointing at the original.
  function wbCopiedLinks(have, selectedIds) {
    const out = [];
    for (const s of wbState.sketches || []) {
      if (!wbIsLinkSketch(s)) continue;
      let p;
      try { p = JSON.parse(s.data); } catch { continue; }
      const end = (side) => (p[`${side}Id`] == null ? null : `${p[`${side}Kind`] || "node"}:${p[`${side}Id`]}`);
      const src = end("source"), dst = end("target");
      const attached = [src, dst].filter(Boolean);
      if (attached.some((k) => !have.has(k))) continue;
      if (attached.length < 2 && !selectedIds.has(s.id)) continue;
      out.push({ kind: "sketch", key: `sketch:${s.id}`, src, dst, payload: WB_KIND_INFO.sketch.payload(s) });
    }
    return out;
  }

  function wbCopySelection() {
    const copied = wbCopyableSelection();
    if (!copied) return false;
    //: The stamp is what the system clipboard carries back (`wbOnBoardCopy`),
    //: so a paste can tell "the items I copied here" from text copied since in
    //: another app (FEAT-09).
    copied.stamp = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    copied.at = Date.now();
    wbClipboard = copied;
    //: A copy from a menu has no copy event behind it, so the stamp is written
    //: here as well; a shell that refuses the async clipboard keeps the
    //: board's own clipboard, which a paste falls back to.
    try {
      const text = wbClipboardText(copied) || " ";
      const html = `<meta name="memorymap-board" content="${copied.stamp}"><pre>${text.replace(/&/g, "&amp;").replace(/</g, "&lt;")}</pre>`;
      navigator.clipboard?.write?.([new ClipboardItem({
        "text/plain": new Blob([text], { type: "text/plain" }),
        "text/html": new Blob([html], { type: "text/html" }),
      })]).catch(() => {});
    } catch {
      // No async clipboard here.
    }
    toast(copied.things > 1 ? `Copied ${copied.things} items.` : "Copied.");
    return true;
  }

  //: Make `copied` on the board, centred on `at` (board units) when given,
  //: else moved by `step` grid steps (0 is in place); select what was made
  //: and record it as one undo step.
  async function wbPlaceCopies(copied, at, step = 1, noComments = false) {
    if (!copied?.items.length) return [];
    const { box } = copied;
    const dx = at ? at[0] - (box.minX + box.maxX) / 2 : step * WB_GRID_SPACING;
    const dy = at ? at[1] - (box.minY + box.maxY) / 2 : step * WB_GRID_SPACING;
    const created = await wbCreateCopies(copied.items, dx, dy, noComments);
    if (created.length === 0) return created;
    wbPushDragUndo(created);
    wbSelectToolRef?.("select");
    const things = created.filter((c) => !(c.kind === "sketch" && wbIsLinkSketch(wbFindItem("sketch", c.id) || {})));
    if (things.length === 1) {
      selectWbItem(things[0].kind, things[0].id);
    } else {
      wbSelectedItem = null;
      wbMultiSelection.clear();
      for (const c of things) wbMultiSelection.add(wbMultiKey(c.kind, c.id));
      wbApplySelectionHighlight();
      wbUpdateSelectionBar();
    }
    wbScheduleRender();
    return created;
  }

  //: **Paste steps one grid square each time** (the owner, 2026-10-26: copy,
  //: cut and paste with several things). The first paste on the board the
  //: copy came from lands one step down and right, the next two, and so on; on
  //: another board the first lands in place. Ctrl+Shift+V is always in place,
  //: and "Paste here" in the canvas menu goes to the pointer.
  async function wbPasteClipboard({ at = null, inPlace = false, noComments = false } = {}) {
    const clip = wbClipboard;
    if (!clip) return;
    const here = window.currentBoardId ?? 0;
    const seen = clip.pasted?.board === here ? clip.pasted.n : (clip.board === here ? 0 : -1);
    const n = inPlace ? 0 : seen + 1;
    if (!inPlace && !at) clip.pasted = { board: here, n };
    await wbPlaceCopies(clip, at, n, noComments);
  }

  //: The ink a stored black or white default draws in on this board (audit U1):
  //: those two are the app's own theme defaults, not a choice, so they follow
  //: the board's background; any other colour is the person's and stays.
  function wbDefaultInk(color) {
    const c = String(color || "").toLowerCase();
    return c === "#000000" || c === "#ffffff" ? wbReadableInk(c, wbBoardBg()) : color;
  }
  function wbBoardBg() {
    if (wbBoardBgCache.pass) return wbBoardBgCache.out;
    const el = wbInstances.container();
    if (!el) return "";
    const root = document.documentElement;
    let sig = el.style.getPropertyValue("--wb-board-bg");
    for (const attr of root.attributes) sig += `|${attr.name}=${attr.value}`;
    if (wbBoardBgCache.sig !== sig) Object.assign(wbBoardBgCache, { sig, value: getComputedStyle(el).backgroundColor });
    //: Transparent says nothing about the board: no remap.
    return (wbBoardBgCache.out = /,\s*0\)$/.test(wbBoardBgCache.value) ? "" : wbBoardBgCache.value);
  }

  //: One call per frame with the newest event, for a pointermove handler that
  //: only paints (audit B5): the browser fires these faster than it paints, and
  //: a hit test per event is work nobody sees. Not for a handler that collects
  //: every point (the pen, the lasso).
  //: `after` runs it once that frame has drawn (a timer after the frame): the hover hit test reads every item's box,
  //: and run inside the frame it was the first reader after whatever else wrote (101 ms at 4x on 400 items).
  function wbOnFrame(fn, after = false) {
    let latest = null;
    const run = () => {
      const ev = latest;
      latest = null;
      fn(ev);
    };
    return (e) => {
      const idle = latest === null;
      latest = e;
      if (!idle) return;
      requestAnimationFrame(after ? () => setTimeout(run) : run);
    };
  }

  //: The links on the board with an end on this item: the server drops them
  //: with it (`_forget_links_to`), so a delete keeps them to put back.
  function wbLinksTouching(kind, id) {
    return (wbState.sketches || []).filter((s) => {
      let data = null;
      try { data = JSON.parse(s.data); } catch { return false; }
      if (!data || !String(data.type || "").startsWith("link-")) return false;
      return (data.sourceId === id && (data.sourceKind || "node") === kind)
        || (data.targetId === id && (data.targetKind || "node") === kind);
    }).map((s) => ({ ...WB_KIND_INFO.sketch.payload(s), id: s.id }));
  }

  function wbForgetLinks(links) {
    const gone = new Set((links || []).map((link) => link.id));
    if (gone.size) wbState.sketches = (wbState.sketches || []).filter((s) => !gone.has(s.id));
  }

  //: Draw `links` again with `oldId` (a `kind`) now `newId`; an end on an item
  //: no longer on the board is skipped, a line to nowhere.
  async function wbRestoreLinks(links, kind, oldId, newId) {
    const sketchRemap = new Map();
    const present = (k, id) => (wbState[WB_LIST_BY_KIND[k]] || []).some((i) => i.id === id);
    for (const link of links || []) {
      let data;
      try { data = JSON.parse(link.data); } catch { continue; }
      if (!data || typeof data !== "object") continue;
      let whole = true;
      for (const [idKey, kindKey] of [["sourceId", "sourceKind"], ["targetId", "targetKind"]]) {
        const k = data[kindKey] || "node";
        if (k === kind && data[idKey] === oldId) data[idKey] = newId;
        else if (!present(k, data[idKey])) whole = false;
      }
      if (!whole) continue;
      try {
        const made = await apiJson("/whiteboard/sketches", {
          method: "POST",
          body: JSON.stringify({ ...link, id: undefined, data: JSON.stringify(data) }),
        });
        wbState.sketches.push(made);
        sketchRemap.set(link.id, made.id);
      } catch { /* the item came back; a link that cannot is not worth failing it */ }
    }
    return sketchRemap;
  }

  //: A card/object's CSS transform: translate always, plus a rotate(deg)
  //: about its own centre when it has one. `translate() rotate()` (in that
  //: order) is the standard idiom for "move this box, then spin it in
  //: place": `transform-origin`'s default (50% 50%) is resolved once in the
  //: element's own untransformed box, so the rotation pivots on the box's own
  //: centre regardless of where the translate moved it to, the reverse order
  //: would instead swing the box around a point offset from its own body.
  //: **A drag handle that lives inside the thing it moves needs a container
  //: that doesn't.** Reported directly: text boxes "spasm positions and are
  //: basically unmovable".
  //:
  //: `d3.drag` measures each frame's `event.dx/dy` between two `d3.pointer`
  //: readings taken against its *container*, and that container defaults to
  //: `this.parentNode`. For a drag bound to the item itself (`objDrag`) the
  //: parent is `#wb-html-layer`, which holds still while one object moves, so
  //: the deltas are true screen pixels and `/ transform.k` converts them to
  //: board units correctly. But `.wb-object-grip` and `.wb-resize-handle` are
  //: *children* of the item, so their default container is the item, and the
  //: item's own `transform` is rewritten on every frame of the drag. For an
  //: HTML element `d3.pointer` returns `clientX - getBoundingClientRect().left`,
  //: so the origin it measures from moves by exactly the amount just applied
  //: and the next frame's delta is cancelled against it. The box judders in
  //: place instead of following the cursor.
  //:
  //: Only text objects get a grip (an image has no contenteditable competing
  //: for its body), which is why this was reported for text boxes alone. The
  //: resize handles have the same flaw on the `w`/`n` corners only: those are
  //: the ones that move `x`/`y` as well as the size, which is the standing
  //: "zoom-drift in move/resize handles" report.
  //:
  //: Pointing every such drag at the item's own parent is a no-op for the
  //: handles that were already fine (a stable origin either way) and a fix for
  //: the ones that were not.
  //: **Resize and turn handles are built the first time an item wants them**
  //: (audit 1031 BD3: the 302-item board held 2,718 handle elements, each with
  //: its attributes and a drag behaviour, built on every open: 679 of the
  //: 848 ms the render took at 4x, and every style and layout pass after it
  //: walked them too). A handle shows for a hovered, focused or selected item
  //: only, so `wbArmHandles` keeps the builder, and the pointer reaching the
  //: item, focus entering it or the selection naming it calls `wbEnsureHandles`.
  const WB_HANDLE_BUILDERS = new WeakMap();

  function wbArmHandles(el, build) {
    WB_HANDLE_BUILDERS.set(el, build);
  }

  function wbEnsureHandles(el) {
    const build = WB_HANDLE_BUILDERS.get(el);
    if (!build) return;
    WB_HANDLE_BUILDERS.delete(el);
    build();
  }

  function wbStableDragContainer(itemSelector) {
    return function () {
      return this.closest(itemSelector)?.parentNode || this.parentNode;
    };
  }

  function wbPlaceBox(start, x, y) {
    const min = WB_PLACE_MIN[start.place] || WB_PLACE_MIN.text;
    const w = Math.max(min.w, Math.abs(x - start.x));
    const h = Math.max(min.h, Math.abs(y - start.y));
    return {
      x: Math.round(x < start.x ? start.x - w : start.x),
      y: Math.round(y < start.y ? start.y - h : start.y),
      w: Math.round(w),
      h: Math.round(h),
    };
  }

  //: The corner that makes the box square, on the side the pointer is on: the
  //: longer of the two travels, in both directions.
  function wbSquareCorner(start, x, y) {
    const side = Math.max(Math.abs(x - start.x), Math.abs(y - start.y));
    return [start.x + Math.sign(x - start.x || 1) * side, start.y + Math.sign(y - start.y || 1) * side];
  }

  // Asked for directly. Deletes every card and sketch on the *current* board
  // (not other boards: clearing is scoped the same way everything else on
  // this screen is). Reuses the same undo entries a single delete already
  // pushes, one per item, rather than inventing a second "bulk" undo shape: 
  // so Ctrl+Z after Clear brings items back one at a time, exactly like an
  // eraser swipe over the same items would.
  //: Delete the board you are standing on.
  //:
  //: Reported: "there's no way to delete a board while in that board on the
  //: whiteboard and mindmap". The action existed only on the gallery card's
  //: kebab menu, so removing the board in front of you meant leaving it, finding
  //: it again in the list, and opening a menu on its card.
  //:
  //: The default board (`id === null`) is the one board that cannot go: it
  //: always exists, it is what the canvas falls back to, and the gallery
  //: already draws it without a kebab for the same reason. Saying so is better
  //: than hiding the row, which would leave the menu a different shape on that
  //: one board with nothing to explain the gap.
  //:
  //: `DELETE /entries/{id}` and not a whiteboard route, because a board **is**
  //: an Entry (MINDMAP_PLAN.md §4 option B) and that is the same call the
  //: gallery's own Delete makes. Afterwards the canvas has no board to show, so
  //: it goes back to the gallery rather than sitting on a board that is gone.
  //: **Put the board you are looking at into a note** (INBOX 309). The board's
  //: half of the feature; the note's half is the "/" menu's "Board or mind
  //: map".
  //:
  //: The row from the board index when it has it, because that is where the
  //: board's `type` lives and a mind map must not be written into a note as a
  //: whiteboard. Failing that, the picker's own label and `wbIsMap()`, which
  //: are what this file already trusts for the same two facts (see
  //: `wbDeleteCurrentBoard` just below, which reads the title the same way).
  async function wbAddBoardToNote() {
    const boardId = window.currentBoardId ?? null;
    if (boardId === null) {
      toast("The default board cannot go in a note. Make a board first.");
      return;
    }
    const row = (typeof mapBoardById === "function" && mapBoardById(boardId)) || null;
    const select = $("wb-board-select");
    const title =
      row?.title || select?.options?.[select.selectedIndex]?.textContent?.trim() || "This board";
    const type = row?.type || (wbIsMap() ? "map" : "board");
    await addBoardToNote({ id: boardId, title, type });
  }

  async function wbDeleteCurrentBoard() {
    const boardId = window.currentBoardId ?? null;
    if (boardId === null) {
      toast("The default board cannot be deleted. Use Clear to empty it.");
      return;
    }
    const select = $("wb-board-select");
    const title =
      select?.options?.[select.selectedIndex]?.textContent?.trim() || "this board";
    if (!(await wbDeleteBoard(boardId, title))) return;
    window.currentBoardId = null;
    wbShowBoardsLanding();
  }

  //: A board is a note, so deleting one moves it to the recycle bin, and the
  //: app's Undo (and the toast's) bring it back with everything on it (INBOX
  //: 537). The confirm used to say "This cannot be undone", which was untrue.
  async function wbBinBoard(id, bin) {
    await apiJson(bin ? `/entries/${id}` : `/entries/${id}/restore`, { method: bin ? "DELETE" : "POST" });
    //: **The board made a moment ago is drawn from memory** when the server omits
    //: it (an empty board is not listed: `drawLibraryBoardsGallery`), so a delete
    //: has to forget it too, or an empty map's card stays after "Moved to the
    //: bin" (INBOX 733). Undo puts it back the same way.
    if (bin && window.wbLastCreatedBoard?.id === id) {
      window.wbBinnedBoard = window.wbLastCreatedBoard;
      window.wbLastCreatedBoard = null;
    } else if (!bin && window.wbBinnedBoard?.id === id) {
      window.wbLastCreatedBoard = window.wbBinnedBoard;
      window.wbBinnedBoard = null;
    }
    await refreshBoardList();
    if ($("wb-boards-landing") && !$("wb-boards-landing").classList.contains("hidden")) renderLibraryBoardsGallery();
  }

  async function wbDeleteBoard(id, title) {
    try {
      await wbBinBoard(id, true);
    } catch (err) {
      toast(err.message || voiceLine("failed", { what: "delete that board" }), true);
      return false;
    }
    const action = pushUndo(`Deleted "${title}"`, () => wbBinBoard(id, false), () => wbBinBoard(id, true));
    toastAction(`Moved "${title}" to the bin.`, "Undo", async () => {
      await wbBinBoard(id, false);
      settleUndoFromToast(action);
    });
    return true;
  }

  async function wbClearBoard() {
    const total = wbState.nodes.length + wbState.sketches.length + (wbState.objects?.length || 0);
    if (total === 0) {
      toast("This board is already empty.");
      return;
    }
    const ok = await confirmDialog(
      `Clear this board? ${nounCount(total, "item")} will be removed. ` +
      "One Ctrl+Z puts them all back."
    );
    if (!ok) return;
    //: One Undo step (INBOX 537), read off the board before and after; and an
    //: item the server already dropped with another (a card's links, a topic's
    //: branch) is skipped rather than ending the clear part way.
    await wbRecordGesture(async () => {
      for (const kind of ["sketch", "node", "object"]) {
        const { base, list } = WB_KIND_INFO[kind];
        for (const item of [...(wbState[list] || [])]) {
          await apiJson(`${base}/${item.id}`, { method: "DELETE", silent: true }).catch(() => null);
        }
      }
      await fetchWhiteboardState();
    });
    wbSelectedItem = null;
    wbScheduleRender();
    await refreshBoardList();
    const left = wbState.nodes.length + wbState.sketches.length + (wbState.objects?.length || 0);
    toast(left ? voiceLine("failed", { what: "clear the whole board; what is left is shown" }) : "Board cleared.", Boolean(left));
  }

  // whiteboard-export.js: whiteboard-export.js: the board and map export (SVG, PNG, PDF, copy as image, th (moved out, L286).

  // The board's full extent, every card and sketch, with padding, computed
  // from what's actually rendered (`getBBox`/`offsetWidth`) rather than
  // guessed constants, so it stays right if a card's real size ever changes.
  function wbBoardBounds() {
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    //: One walk per kind, not one `querySelector` per item (W30 B23: 11 ms of an export of 280 sketches).
    const idIndex = (selector) => new Map([...document.querySelectorAll(selector)].reverse().map((el) => [el.dataset.id, el]));
    const cardEls = idIndex(".node-card");
    const sketchEls = idIndex(".sketch-group");
    for (const node of wbState.nodes) {
      const el = cardEls.get(String(node.id));
      const w = el ? el.offsetWidth : 250;
      const h = el ? el.offsetHeight : 150;
      minX = Math.min(minX, node.x);
      minY = Math.min(minY, node.y);
      maxX = Math.max(maxX, node.x + w);
      maxY = Math.max(maxY, node.y + h);
    }
    for (const sketch of wbState.sketches) {
      const el = sketchEls.get(String(sketch.id));
      if (!el) continue;
      try {
        const bbox = el.getBBox();
        minX = Math.min(minX, bbox.x);
        minY = Math.min(minY, bbox.y);
        maxX = Math.max(maxX, bbox.x + bbox.width);
        maxY = Math.max(maxY, bbox.y + bbox.height);
      } catch {
        /* getBBox throws on an element the browser hasn't laid out yet */
      }
    }
    for (const obj of wbState.objects || []) {
      minX = Math.min(minX, obj.x);
      minY = Math.min(minY, obj.y);
      maxX = Math.max(maxX, obj.x + obj.width);
      maxY = Math.max(maxY, obj.y + obj.height);
    }
    if (!Number.isFinite(minX)) return { minX: 0, minY: 0, width: 800, height: 600 };
    const pad = 60;
    return {
      minX: minX - pad,
      minY: minY - pad,
      width: maxX - minX + pad * 2,
      height: maxY - minY + pad * 2,
    };
  }

  //: Bounds of the current selection, asked for directly ("an export selection
  //: feature"). Reuses `wbSelectionEntries()` (already shared by
  //: align/distribute/nudge) for a real multi-selection; a lone
  //: `wbSelectedItem` falls back to `wbItemBBox` directly since that path
  //: never populates `wbMultiSelection`. A link sketch has no bbox of its
  //: own (`wbItemBBox` returns null for one), `null` here means "nothing
  //: exportable selected", which the export menu's own gating already checks.
  function wbSelectionBounds(pad = 40) {
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    const boxes = wbMultiSelection.size > 0
      ? wbSelectionEntries().map((e) => e.bbox)
      : wbSelectedItem
        ? [wbItemBBox(wbSelectedItem.kind, (wbState[WB_LIST_BY_KIND[wbSelectedItem.kind]] || []).find((i) => i.id === wbSelectedItem.id))].filter(Boolean)
        : [];
    for (const box of boxes) {
      minX = Math.min(minX, box.minX);
      minY = Math.min(minY, box.minY);
      maxX = Math.max(maxX, box.maxX);
      maxY = Math.max(maxY, box.maxY);
    }
    if (!Number.isFinite(minX)) return null;
    return { minX: minX - pad, minY: minY - pad, width: maxX - minX + pad * 2, height: maxY - minY + pad * 2 };
  }

  //: **A press anywhere inside the selection's box is a press on the
  //: selection** (INBOX 1486, the owner: "cant select in the middle to drag a
  //: group selection or object??"). Only a press on a member's own body used to
  //: drag it, so the empty space between a frame and its cards, or inside an
  //: unfilled shape, started a marquee and dropped the selection. Measured
  //: before: a frame and three cards selected, a press at an empty middle
  //: point and a 100px drag moved 0 of 4 objects and left 0 selected.
  function wbPointInSelectionBounds(x, y) {
    if (wbIsMap() || (!wbSelectedItem && wbMultiSelection.size === 0)) return false;
    const b = wbSelectionBounds(0);
    return Boolean(b) && x >= b.minX && x <= b.minX + b.width && y >= b.minY && y <= b.minY + b.height;
  }

  //: What that drag carries: the selection less anything locked, and a lone
  //: frame's contents (its title drag's rule). Null when nothing can move.
  function wbSelectionDragOrigin() {
    const base = wbMultiSelection.size > 0
      ? [...wbMultiSelection]
      : wbSelectedItem ? [wbMultiKey(wbSelectedItem.kind, wbSelectedItem.id)] : [];
    const keys = new Set();
    let lone = null;
    for (const key of base) {
      const sep = key.indexOf(":");
      const kind = key.slice(0, sep);
      const item = wbFindItem(kind, Number(key.slice(sep + 1)));
      if (!item || wbIsLocked(kind, item)) continue;
      keys.add(key);
      lone = base.length === 1 ? item : null;
    }
    if (lone && lone.kind === "frame") for (const key of wbFrameContents(lone)) keys.add(key);
    if (!keys.size) return null;
    return wbCaptureBulkMoveOrigin(null, keys.size === wbMultiSelection.size && keys.size > 1 ? wbMultiSelection : keys);
  }

  // What's actually framed on screen right now, in board-space coordinates, 
  // the inverse of the pan/zoom transform the container itself carries.
  function wbVisibleBounds() {
    const container = wbInstances.container();
    const transform = d3.zoomTransform(container);
    const rect = container.getBoundingClientRect();
    return {
      minX: -transform.x / transform.k,
      minY: -transform.y / transform.k,
      width: rect.width / transform.k,
      height: rect.height / transform.k,
    };
  }

  //: Which items an "export selection" pass should include: everything else
  //: in `wbBuildExportSvg` only needs a membership check, so this is the one
  //: place that reads `wbSelectedItem`/`wbMultiSelection` for it. `null` (not
  //: scope "selection") means "no filter", i.e. every other scope keeps
  //: exporting the whole board it always did.
  function wbSelectedKeys() {
    if (wbMultiSelection.size > 0) return wbMultiSelection;
    if (wbSelectedItem) return new Set([wbMultiKey(wbSelectedItem.kind, wbSelectedItem.id)]);
    return new Set();
  }


  //: **A `role="menu"` with no `role="menuitem"` in it is an empty menu.**
  //:
  //: The board's six menus (Insert, Edit, Arrange, View, Board in the top bar,
  //: and the context bar's own) are written in index.html rather than built by
  //: `kebabMenu`, which is the deliberate part: their rows are not all commands.
  //: Half of the View menu is a colour input, a grid select and four switches,
  //: and a command list cannot hold those. What was not deliberate is that the
  //: container declared `role="menu"` and nothing inside it declared anything,
  //: so a screen reader was handed a menu of nought items and the shared
  //: arrow-key wiring (`wireMenuKeyboard`) found nothing to move between.
  //: Measured before this existed (`scratchpad/ui-sweeps/wbtopbar.js`, at 1440
  //: and at 320): five menus, 0 items each, 8/7/10/19/5 buttons with no role,
  //: and ArrowDown moving no focus in any of them.
  //:
  //: Stamped here rather than written into the markup 76 times, because the
  //: markup is the one place it could drift: a row added to a menu next year
  //: takes its role from the shape it is given. The mapping is the ARIA one:
  //: a command is a `menuitem`, a labelled section is a `group`, and a row that
  //: is a wrapper around a native control (a select, a colour well, a checkbox
  //: in its own label) is `none`, which leaves that control exposed as itself
  //: rather than lying about it being a command.
  //: **The Arrange menu is submenus** (INBOX 1564, U15): each `[data-wb-submenu]`
  //: section ("ph:icon Name") becomes the menu recipe's own group row. The rows
  //: are moved, not rebuilt, so their `data-wb-cmd`, keycaps and ids stay. The
  //: flyout is a `.wb-board-menu` too: the row click, the outside-click test and
  //: the menu looks all find it. Under 820 it is a nested level (`.menu-nested`).
  function wbFoldMenuSubmenus(menu) {
    for (const section of menu.querySelectorAll("[data-wb-submenu]")) {
      const group = buildMenuGroupButton(section.dataset.wbSubmenu, [...section.children]);
      const panel = group.querySelector(".submenu");
      panel.classList.add("wb-board-menu");
      //: Named once for the close below (a flyout sets it on each open too).
      panel._escapedOpener = group.firstElementChild;
      panel._escapedOpener.title = section.dataset.wbSubmenuTitle;
      //: A whiteboard-only group (Board, Workshop; INBOX 1627) hides on a map as its section did.
      if (section.dataset.wbSurface) group.dataset.wbSurface = section.dataset.wbSurface;
      section.replaceWith(group);
    }
  }

  function wbStampMenuRoles(menu) {
    for (const section of menu.querySelectorAll(".wb-menu-section")) {
      section.setAttribute("role", "group");
    }
    for (const item of menu.querySelectorAll(".wb-menu-item")) {
      item.setAttribute("role", "menuitem");
    }
    //: Every other direct or sectioned child: a row that holds a control, a
    //: group label, a file input. `role="none"` is what makes the container a
    //: valid menu, and it is the honest answer for each of them: none of them
    //: is a command.
    for (const row of menu.querySelectorAll(".wb-menu-row, .wb-panel-group-label, input[type=\"file\"]")) {
      if (!row.hasAttribute("role")) row.setAttribute("role", "none");
    }
  }

  //: The file's surface: what other files call (L634).
  Object.assign(window, { wbPointerOnBoard, wbCopyableSelection, wbIsLinkSketch, wbCopySelection, wbPlaceCopies, wbPasteClipboard, wbDefaultInk, wbBoardBg, wbOnFrame, wbLinksTouching, wbForgetLinks, wbRestoreLinks, wbArmHandles, wbEnsureHandles, wbStableDragContainer, wbPlaceBox, wbSquareCorner, wbAddBoardToNote, wbDeleteCurrentBoard, wbBinBoard, wbDeleteBoard, wbClearBoard, wbBoardBounds, wbSelectionBounds, wbPointInSelectionBounds, wbSelectionDragOrigin, wbVisibleBounds, wbSelectedKeys, wbFoldMenuSubmenus, wbStampMenuRoles });
})();
