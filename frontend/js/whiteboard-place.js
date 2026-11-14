(() => {
  // whiteboard-place.js: paste from other apps, where a placed thing lands, clone and connect.
  // Moved out of whiteboard.js whole (L286) and wrapped: only what other files call goes on `window`; nothing here runs at load.
  // --- Paste from other apps (FEAT-09) ----------------------------------------
  //
  // The features audit: pasting text onto a board did nothing (3 items before a
  // three-line paste, 3 after), because the board's Ctrl+V only ever read its
  // own clipboard and swallowed the key, so the browser's paste never arrived.
  // tldraw, Miro, FigJam and Excalidraw all make text into items. Now Ctrl+V
  // lets the paste happen and the paste decides: the board's own items when the
  // clipboard still holds what was copied here (its stamp, written into the
  // clipboard's HTML by `wbOnBoardCopy`), a picture as before, otherwise text:
  // a link becomes a link box, one line a text box, several lines a grid of
  // stickies, all one undo step.

  //: The words of what was copied, for the clipboard's plain text: what a
  //: paste into another app gets.
  function wbClipboardText(copied) {
    const words = [];
    for (const { kind, payload } of copied?.items || []) {
      if (kind === "object" && payload?.data?.content) words.push(String(payload.data.content));
      else if (kind === "sketch") {
        try {
          const label = JSON.parse(payload.data || "{}").label;
          if (label) words.push(String(label));
        } catch {
          // A stroke has no words.
        }
      }
    }
    return words.join("\n\n");
  }

  //: The copy event after the board's own Ctrl+C or Ctrl+X: the stamp goes into
  //: the clipboard's HTML and the words into its plain text.
  function wbOnBoardCopy(e) {
    if (!wbClipboard?.stamp || Date.now() - (wbClipboard.at || 0) > 2000) return;
    if (!e.clipboardData) return;
    const text = wbClipboardText(wbClipboard);
    const safe = text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    e.clipboardData.setData("text/plain", text || " ");
    e.clipboardData.setData("text/html", `<meta name="memorymap-board" content="${wbClipboard.stamp}"><pre>${safe}</pre>`);
    e.preventDefault();
  }

  //: **The middle of the canvas you can see, not of the box behind the chrome**
  //: (INBOX 664). The top bar, the side rail with its open panel and the tool
  //: dock all float over the canvas, so the container's own middle sat 162px
  //: left of the open area with the Library open (measured at 1440x900): a
  //: click on a Library tile put the shape a third of the way under the panel
  //: it was clicked in.
  //:
  //: Pure: `box` is the container's rect, `covers` the chrome's rects. A wide
  //: cover is a bar along the top or the bottom, a tall one a rail along the
  //: left or the right, whichever edge it sits nearer; the open area is inset
  //: from that edge to it, unless that would leave less than half the canvas
  //: (a phone's bottom sheet, a panel opened wide): then the cover is over the
  //: canvas rather than beside it, and the middle stays the canvas's own.
  function wbFreeCanvasRect(box, covers) {
    let { left, top, right, bottom } = box;
    const w = box.right - box.left;
    const h = box.bottom - box.top;
    for (const c of covers) {
      if (!c || !(c.right > c.left) || !(c.bottom > c.top)) continue;
      if (c.right <= box.left || c.left >= box.right || c.bottom <= box.top || c.top >= box.bottom) continue;
      const edge = c.right - c.left >= c.bottom - c.top
        ? (c.top - box.top <= box.bottom - c.bottom ? "top" : "bottom")
        : (c.left - box.left <= box.right - c.right ? "left" : "right");
      if (edge === "left" && c.right - box.left <= w / 2) left = Math.max(left, c.right);
      else if (edge === "right" && box.right - c.left <= w / 2) right = Math.min(right, c.left);
      else if (edge === "top" && c.bottom - box.top <= h / 2) top = Math.max(top, c.bottom);
      else if (edge === "bottom" && box.bottom - c.top <= h / 2) bottom = Math.min(bottom, c.top);
    }
    return { left, top, right, bottom };
  }

  //: The chrome that floats over a board: the top bar, the side rail and its
  //: panel, the tool dock (wherever it is docked).
  const WB_CANVAS_COVERS = ["wb-topbar", "wb-sidebar", "wb-tools-panel"];

  function wbVisibleCanvasRect() {
    const box = document.getElementById("whiteboard-container").getBoundingClientRect();
    const covers = [];
    for (const id of WB_CANVAS_COVERS) {
      const el = document.getElementById(id);
      if (el && el.offsetParent !== null && !el.hidden) covers.push(el.getBoundingClientRect());
    }
    return wbFreeCanvasRect(box, covers);
  }

  //: A number out of a CSS string or a stored value, or `fallback` when it is not
  //: finite ("normal", "auto", "", NaN): a raw `parseFloat` of those wrote `NaN`
  //: into a style or transform (audit B33). Use it wherever the result is used
  //: as a length.
  function wbNum(v, fallback = 0) {
    const n = typeof v === "number" ? v : parseFloat(v);
    return Number.isFinite(n) ? n : fallback;
  }

  //: The middle of what the canvas shows, in board units.
  function wbViewCentre() {
    const r = wbVisibleCanvasRect();
    return wbClientToBoard((r.left + r.right) / 2, (r.top + r.bottom) / 2);
  }

  // --- Where a placed thing lands (INBOX 664) ---------------------------------
  //
  // One rule for everything put on a board from somewhere else (the Library's
  // shapes and templates, a map's branch templates, an icon or emoji, a note,
  // an image): **the point of the thing you are holding stays under the
  // pointer.** A drag from a tile holds the tile's picture where it was
  // grabbed, so that point of the placed item lands under the pointer; a drag
  // with no picture of its own (a note, a file) puts the item's middle there; a
  // click puts the middle in the middle of the canvas you can see. A group (a
  // template) keeps its own layout and is anchored by its whole box. Snap to
  // grid, when it is on, moves the box's corner onto the grid afterwards, the
  // one allowed difference (`WB_GRID_SPACING`, 24 board units).
  //
  // Measured before (scratchpad/ui-sweeps/dropplace.js, 1440x900): a click
  // landed 162px left of the open canvas with the Library open; a drag ignored
  // where the tile was held (48px off for a rectangle held by its corner, 291px
  // for the Kanban template); a star or a cloud whose drawing is not centred in
  // its declared box sat 6 to 7px off; a note card 25px high; a map template
  // 236px right and down, its first topic's corner where the pointer was.

  //: How far to move `box` (board units) so its `frac` point is at `at`, with
  //: its corner then snapped to `grid` when one is given. Pure.
  function wbAnchorDelta(box, at, frac = [0.5, 0.5], grid = 0) {
    let dx = at[0] - (box.minX + (box.maxX - box.minX) * frac[0]);
    let dy = at[1] - (box.minY + (box.maxY - box.minY) * frac[1]);
    if (grid > 0) {
      dx = Math.round((box.minX + dx) / grid) * grid - box.minX;
      dy = Math.round((box.minY + dy) / grid) * grid - box.minY;
    }
    return [dx, dy];
  }

  //: The box around what a placement made, as it is drawn: a shape by its
  //: path's own `getBBox` (exact for the curves and arcs `wbPathBBox` bounds by
  //: their control points), a box or card by its rendered size (`wbItemBBox`).
  //: A link is left out: it is drawn between the things it joins.
  function wbPlacedBounds(rows) {
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    for (const { kind, item } of rows) {
      let box = null;
      if (kind === "sketch") {
        const parsed = wbSketchParsedData(item);
        if (!parsed) continue;
        const path = document.querySelector(`.sketch-group[data-id="${item.id}"] .sketch-path`);
        try {
          const b = path?.getBBox();
          if (b && (b.width || b.height)) box = { minX: b.x, minY: b.y, maxX: b.x + b.width, maxY: b.y + b.height };
        } catch {
          // Not rendered (culled, or the board closed): the path's own numbers.
        }
        box = box || wbItemBBox(kind, item);
      } else {
        box = wbItemBBox(kind, item);
      }
      if (!box) continue;
      minX = Math.min(minX, box.minX); minY = Math.min(minY, box.minY);
      maxX = Math.max(maxX, box.maxX); maxY = Math.max(maxY, box.maxY);
    }
    return Number.isFinite(minX) ? { minX, minY, maxX, maxY } : null;
  }

  //: Moves what was just placed so it lands by the rule above, after it has
  //: been drawn and before the frame is painted, so it never shows anywhere
  //: else. Called inside the placement's own `wbRecordGesture`, so the move is
  //: part of the one undo step. A move under a quarter of a board unit is not
  //: made: the placement was already right, and a save would only add a row to
  //: the board's history.
  async function wbAnchorPlaced(rows, at, frac = [0.5, 0.5]) {
    if (!at || !rows.length) return;
    const box = wbPlacedBounds(rows);
    if (!box) return;
    const [dx, dy] = wbAnchorDelta(box, at, frac, wbSnapOn() ? WB_GRID_SPACING : 0);
    if (Math.abs(dx) < 0.25 && Math.abs(dy) < 0.25) return;
    const origin = wbCaptureBulkMoveOrigin(null, new Set(rows.map((r) => wbMultiKey(r.kind, r.item.id))));
    wbApplyBulkMove(origin, dx, dy);
    await wbSaveBulkMove(origin);
    // A template's elbow joins keep their bends with the boxes they join.
    await wbCarryWaypoints(null, origin);
  }

  // --- Clone and connect (the features audit W4; draw.io's blue arrows) -------
  //
  // A flowchart is drawn one step at a time: this box, then the next one beside
  // it, joined. draw.io puts an arrow on each side of a hovered shape that does
  // exactly that in one click, and so does this, on the one selected shape or
  // text box: an arrow grip a little outside the middle of each side. A click
  // (or Alt+Shift+Arrow) makes a copy one gap away on that side, joins the two
  // with an elbow connector, and selects the copy, so the next press steps on.
  // One undo step. Not on a map, where Tab and Enter already add a topic.

  const WB_CLONE_GAP = 80;
  const WB_CLONE_DIRS = {
    right: { x: 1, y: 0, icon: "M -4 -6 L 4 0 L -4 6 Z", words: "right" },
    left: { x: -1, y: 0, icon: "M 4 -6 L -4 0 L 4 6 Z", words: "left" },
    down: { x: 0, y: 1, icon: "M -6 -4 L 0 4 L 6 -4 Z", words: "below" },
    up: { x: 0, y: -1, icon: "M -6 4 L 0 -4 L 6 4 Z", words: "above" },
  };
  //: All four sides (the owner, 2026-10-10: "you cant even see the top one").
  //: The top arrow stands beyond the rotate grip on the same line out of the
  //: side rather than on it: the grip is 12px across at 28px up, so the arrow
  //: sits at 42px, a clear gap past it, and the grip keeps its place
  //: (decision 6: the rotate stem is on top). The context bar stands that much
  //: higher while the arrows show (`wbUpdateSelectionBar`).
  const WB_CLONE_GRIP_DIRS = ["up", "right", "down", "left"];
  //: How far out from each side the arrow's centre sits, in screen pixels: the
  //: grips are drawn one size to the hand at any zoom, so their distance is too.
  //: **The up arrow stands clear of the rotation grip** (INBOX 1354, rotating
  //: "is very finicky"): both are fixed screen distances above the box, the
  //: grip 28px, and at 42 the arrow took presses 10px from the grip's centre.
  //: At 56 the grip's 14px reach on a touch screen ends before the arrow.
  const WB_CLONE_GRIP_OUT = { up: 56, right: 22, down: 22, left: 22 };

  //: The one selected item clone-and-connect works on, or null.
  function wbCloneSource() {
    if (wbIsMap() || wbMultiSelection.size > 1 || !wbSelectedItem) return null;
    const { kind, id } = wbSelectedItem;
    const item = wbFindItem(kind, id);
    if (!item || wbIsLocked(kind, item) || wbItemHidden(kind, item)) return null;
    if (kind === "object" && item.kind !== "text") return null;
    if (kind === "sketch" && !wbShapeLabelKind(wbSketchParsedData(item))) return null;
    const bbox = wbItemBBox(kind, item);
    return bbox ? { kind, id, item, bbox } : null;
  }

  //: `at`: a board point to put the copy's middle on (a drag from the arrow to empty space, which opened the shape
  //: picker and took its first row); else one step along the arrow.
  async function wbCloneConnect(dirName, at = null) {
    const source = wbCloneSource();
    const dir = WB_CLONE_DIRS[dirName];
    if (!source || !dir) {
      toast("Select one shape, text box or note card to copy and join.");
      return;
    }
    if (source.kind === "node") {
      await wbCloneNoteCard(source, dirName);
      return;
    }
    const w = source.bbox.maxX - source.bbox.minX, h = source.bbox.maxY - source.bbox.minY;
    //: A turned box copies along its own turned side, as its arrow points, and
    //: the copy keeps the turn (the payload carries it).
    const rot = wbItemRotation(source.kind, source.item);
    const step = wbRotatePoint({ x: dir.x * (w + WB_CLONE_GAP), y: dir.y * (h + WB_CLONE_GAP) }, { x: 0, y: 0 }, rot);
    const dx = at ? Math.round(at[0] - (source.bbox.minX + source.bbox.maxX) / 2) : Math.round(step.x);
    const dy = at ? Math.round(at[1] - (source.bbox.minY + source.bbox.maxY) / 2) : Math.round(step.y);
    let copy = null;
    await wbRecordGesture(async () => {
      const [made] = await wbCreateCopies([{ kind: source.kind, payload: WB_KIND_INFO[source.kind].payload(source.item) }], dx, dy);
      if (!made) return;
      copy = made;
      const link = await apiJson("/whiteboard/sketches", {
        method: "POST",
        body: JSON.stringify({
          data: JSON.stringify({
            type: "link-straight", route: "elbow",
            sourceId: source.id, sourceKind: source.kind === "node" ? undefined : source.kind,
            targetId: made.id, targetKind: made.kind === "node" ? undefined : made.kind,
            //: **Fixed ports at both ends** (the owner, 2026-10-10: "when I move
            //: the new connected sticky note, the point at which the link line
            //: connects to it changes vertically depending on where I drag it").
            //: With no anchor an end floats: it is wherever the line between the
            //: two centres crosses the outline, so it slid along the side with
            //: every move. draw.io's clone-and-connect joins the side the arrow
            //: was on to the facing side of the copy, and so does this: the
            //: middle of each, stored as box fractions (`wbAnchorPoint`), which
            //: turn and stretch with the box and never re-anchor.
            sourceAnchor: { x: 0.5 + dir.x / 2, y: 0.5 + dir.y / 2 },
            targetAnchor: { x: 0.5 - dir.x / 2, y: 0.5 - dir.y / 2 },
            color: (source.kind === "sketch" && wbSketchParsedData(source.item)?.color) || window.currentStrokeColor || "#888888",
            width: 2, endCap: "arrow",
          }),
          x: 0, y: 0, z: wbStackNewZ("sketch"), board_id: window.currentBoardId ?? null,
        }),
      });
      wbState.sketches.push(link);
    });
    if (!copy) return;
    selectWbItem(copy.kind, copy.id);
    wbScheduleRender();
    wbAnnounce(`Copied ${dir.words} and joined. Press again to keep going.`);
  }

  //: **A note card's arrow makes a new note** (WHITEBOARD_PLAN decision E1,
  //: INBOX 826): copying the card would put the same note on the board twice,
  //: so the arrow makes a new note in a card the size of this one, joined to it
  //: by an arrowed link side to side, and opens it for typing with its words
  //: selected. One undo step takes back the card, the link and the note.
  async function wbCloneNoteCard(source, dirName) {
    const dir = WB_CLONE_DIRS[dirName];
    const w = source.bbox.maxX - source.bbox.minX, h = source.bbox.maxY - source.bbox.minY;
    let made = null;
    await wbRecordGesture(async () => {
      const entry = await apiJson("/entries", { method: "POST", body: JSON.stringify({ content: "New note", defer_filing: true }) });
      wbPushUndo({ action: "noteMade", entryId: entry.id });
      made = await apiJson("/whiteboard/nodes", {
        method: "POST",
        body: JSON.stringify({
          entry_id: entry.id, board_id: window.currentBoardId ?? null,
          x: Math.round(source.item.x + dir.x * (w + WB_CLONE_GAP)), y: Math.round(source.item.y + dir.y * (h + WB_CLONE_GAP)),
          width: source.item.width, height: source.item.height, z: source.item.z || 1,
        }),
      });
      wbState.nodes.push(made);
      const link = await apiJson("/whiteboard/sketches", {
        method: "POST",
        body: JSON.stringify({
          data: JSON.stringify({
            type: "link-straight", route: "elbow", sourceId: source.id, targetId: made.id,
            sourceAnchor: { x: 0.5 + dir.x / 2, y: 0.5 + dir.y / 2 },
            targetAnchor: { x: 0.5 - dir.x / 2, y: 0.5 - dir.y / 2 },
            color: window.currentStrokeColor || "#888888", width: 2, endCap: "arrow",
          }),
          x: 0, y: 0, z: wbStackNewZ("sketch"), board_id: window.currentBoardId ?? null,
        }),
      });
      wbState.sketches.push(link);
    });
    if (!made) return;
    //: The card reads its words from `allEntries`, fetched before this note.
    await refreshEntries([made.entry_id]);
    selectWbItem("node", made.id);
    renderWhiteboardNow();
    wbAnnounce(`New note ${dir.words}, joined. Type its words.`);
    requestAnimationFrame(() => wbEditNodeText(made.id));
  }

  //: The four arrow grips round the selected shape, drawn in the overlay layer
  //: like the other grips, rebuilt with the selection and laid out by
  //: `wbLayoutCloneGrips`.
  function wbRenderCloneGrips() {
    document.getElementById("wb-clone-grips")?.remove();
    const source = wbCloneSource();
    const zoomGroup = document.getElementById("wb-overlay-zoom-group");
    if (!source || !zoomGroup || window.currentTool !== "select") return;
    const ns = "http://www.w3.org/2000/svg";
    const group = document.createElementNS(ns, "g");
    group.setAttribute("id", "wb-clone-grips");
    for (const name of WB_CLONE_GRIP_DIRS) {
      const dir = WB_CLONE_DIRS[name];
      //: The place on an outer group and the arrow inside it, so the arrow's
      //: stylesheet scale (one size to the hand at any zoom) does not replace
      //: the place, which a `transform` attribute and a CSS one on one element
      //: would.
      const at = document.createElementNS(ns, "g");
      at.dataset.dir = name;
      const grip = document.createElementNS(ns, "path");
      grip.setAttribute("class", "wb-clone-grip");
      grip.setAttribute("d", dir.icon);
      grip.dataset.dir = name;
      const title = document.createElementNS(ns, "title");
      title.textContent = source.kind === "node"
        ? `New note ${dir.words}, joined (Alt+Shift+Arrow)`
        : `Copy ${dir.words} and join (Alt+Shift+Arrow)`;
      grip.append(title);
      //: A drag from the arrow to empty space opens the shape picker there (`wbFmtState.libraryMore`); a click copies.
      grip.addEventListener("pointerdown", (e) => {
        e.stopPropagation();
        if (source.kind !== "node") wbFmtState.libraryMore?.gripPress(e, name);
      });
      grip.addEventListener("click", (e) => {
        e.stopPropagation();
        if (source.kind !== "node" && wbFmtState.libraryMore?.dragged()) return;
        wbCloneConnect(name);
      });
      at.append(grip);
      group.append(at);
    }
    zoomGroup.append(group);
    wbLayoutCloneGrips();
  }

  //: **The arrows follow the box they belong to** (INBOX 740 and the owner's
  //: 2026-10-07 and 2026-10-10 reports: "the edge arrows are still not moving").
  //: They were placed once, when the selection was drawn, off the box's upright
  //: bounds: a drag, a resize or a turn left them where the box had been, and
  //: on a turned box they stood off its unturned sides. Each is now put just
  //: outside the middle of its side of the box as it is this frame (the live
  //: path of a shape being stretched or turned, a text box's rendered size),
  //: turned with it, and pointing out of its side. Called by the selection
  //: bar's frame, which every move, resize and turn already asks for, and by
  //: the zoom, since the distance out is in screen pixels.
  function wbLayoutCloneGrips() {
    const group = document.getElementById("wb-clone-grips");
    if (!group) return;
    const source = wbCloneSource();
    if (!source) {
      group.remove();
      return;
    }
    const { item } = source;
    const live = source.kind === "sketch" && typeof item._liveD === "string" ? wbPathBBox(item._liveD) : null;
    const box = live || source.bbox;
    const container = document.getElementById("whiteboard-container");
    const k = (container && d3.zoomTransform(container).k) || 1;
    const rot = wbItemRotation(source.kind, item);
    const c = wbBoxCenter(box);
    const hw = (box.maxX - box.minX) / 2, hh = (box.maxY - box.minY) / 2;
    for (const at of group.children) {
      const name = at.dataset.dir;
      const dir = WB_CLONE_DIRS[name];
      if (!dir) continue;
      const out = (WB_CLONE_GRIP_OUT[name] || 22) / k;
      const p = wbRotatePoint({ x: c.x + dir.x * (hw + out), y: c.y + dir.y * (hh + out) }, c, rot);
      at.setAttribute("transform", `translate(${p.x} ${p.y})${rot ? ` rotate(${rot})` : ""}`);
    }
  }

  //: Ctrl+D: a copy of the selection beside it, one undo step, the copies
  //: selected so a second Ctrl+D steps on again. Leaves the clipboard alone,
  //: so a duplicate never overwrites something copied to paste later.
  async function wbDuplicateSelection() {
    //: **On a map a copy is a sibling** (MINDMAP_PLAN, 445 audit):
    //: the board's copy posts an object with no `parent_id`, so a duplicated
    //: topic landed as a loose root and undoing it left nothing selected.
    //: One selected topic is copied in place right after itself instead.
    const topic = wbMultiSelection.size <= 1 ? wbSelectedMapNode?.() : null;
    if (topic) {
      await wbMapDuplicateTopic(topic);
      return;
    }
    const copied = wbCopyableSelection();
    if (copied) await wbPlaceCopies(copied, null, 1);
  }

  // Cut: ROADMAP §89.12, asked as a question alongside the context menu
  // below. Same restrictions as copy (a card can't be cut, a link-sketch
  // can't be cut): wbCopySelection already toasts why, so cut just declines
  // to delete anything when the copy half refuses.
  function wbCutSelection() {
    //: A cut deletes the whole selection, so it only runs when the whole
    //: selection went onto the clipboard: a marquee that caught a note card
    //: would otherwise lose the card, which no copy was made of.
    const copied = wbCopyableSelection();
    const selected = wbMultiSelection.size || (wbSelectedItem ? 1 : 0);
    if (copied && copied.items.length < selected) {
      toast("Only part of this selection can be copied, so nothing was cut: note cards and links stay where they are.");
      return false;
    }
    if (!wbCopySelection()) return false;
    deleteWbSelection();
    return true;
  }

  //: The file's surface: what other files call (L286).
  Object.assign(window, { wbClipboardText, wbOnBoardCopy, wbVisibleCanvasRect, wbNum, wbViewCentre, wbAnchorDelta, wbAnchorPlaced, wbCloneSource, wbCloneConnect, wbRenderCloneGrips, wbLayoutCloneGrips, wbDuplicateSelection, wbCutSelection });
})();
