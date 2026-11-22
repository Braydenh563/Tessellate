(() => {
  // whiteboard-boards.js: the board list, loading a board, renaming, and making a new board or map (moved out of whiteboard.js, L634).
  // Wrapped: only what other files call goes on `window`; nothing here runs at load.

  //: A note put on the open board as a card centred on the board point `at`,
  //: as one undo step. The board's own drop and the object paste and drop
  //: (`wbPlaceObject`, obj-clip.js) both come here.
  async function wbPlaceNote(entryId, at) {
    // Reported directly: a dropped note lands "quite offset from where I
    // dropped it". `d.x`/`d.y` are the card's own top-left corner, so the
    // card is centred on the drop point. It was centred on an assumed
    // 250x150, and a card is as tall as its text: a short note's card is
    // 100 high, so it sat 25px high at 100% and 50px at 200% (INBOX 664).
    // The default size is the first guess; the drawn card is then measured
    // and moved (`wbAnchorPlaced`) before the frame is painted.
    const nodeData = {
      entry_id: entryId,
      x: at[0] - WB_CARD_DEFAULT_SIZE.w / 2,
      y: at[1] - WB_CARD_DEFAULT_SIZE.h / 2,
      z: wbStackNewZ("node"),
      board_id: window.currentBoardId
    };

    try {
      //: One undo step, which a note dropped here never had: Ctrl+Z after a
      //: drop took back whatever was done before it.
      await wbRecordGesture(async () => {
        const res = await apiJson("/whiteboard/nodes", { method: "POST", body: JSON.stringify(nodeData) });
        // If it exists in state already, replace it. Otherwise push.
        const idx = wbState.nodes.findIndex(n => n.id === res.id);
        if (idx !== -1) {
          wbState.nodes[idx] = res;
          //: The one in-place replacement in this file, and the one case
          //: `wbLinkItem`'s index cannot see: same array, same length, a
          //: different object at that slot. Dropped by hand here so a link
          //: anchored to this card resolves to the row that is actually in
          //: state rather than to the one it replaced.
          wbForgetLinkItems(wbState.nodes);
        } else {
          wbState.nodes.push(res);
        }
        renderWhiteboardNow();
        await wbAnchorPlaced([{ kind: "node", item: res }], at);
      });
    } catch (err) {
      //: A console line printed "{}": an Error's `message` is not
      //: an enumerable own property, so the console's object view showed
      //: nothing at all and the reader was told a card failed without being
      //: told why. The message is what the server sent, and it belongs on
      //: screen rather than in a console nobody has open.
      const why = (err && err.message) || "the server refused it";
      toast(voiceLine("failed", "add that note to the board", why), true);
    }
  }

  function renderWbLibrary() {
    const list = document.getElementById("wb-library-list");
    //: Before the notebook's first page has come (a board opened straight
    //: from a link at start), skeletons, then the list once it lands (INBOX
    //: 596); never an empty panel that reads as "no notes".
    if (!entriesEverLoaded) {
      list.replaceChildren();
      showSkeletons(list, 5, "li");
      loadEntries().catch(() => {}).then(() => entriesEverLoaded && renderWbLibrary());
      return;
    }
    clearSkeletons(list);
    list.innerHTML = "";
    for (const entry of allEntries) {
      const li = document.createElement("li");
      li.className = "wb-library-item";
      // `notePreviewText` (shell-reminders.js), not the raw body. Reported with a
      // screenshot of this very list: a sketch note read "A real drawn sketch
      // ![A real drawn sket…", because its drawing lives in the note as inline
      // `![alt](/media/…)` markdown and this printed it verbatim. Every other
      // list of notes in the app already goes through this helper, the
      // whiteboard's own card renderer two hundred lines up included, so this
      // was the last place a note's markdown leaked into a label.
      const text = notePreviewText(entry.content || entry.preview || "");
      //: **A name over one muted line** (the owner, 2026-10-10: "text gets cut
      //: off on the note sidebar in the whiteboard"). The row was the title and
      //: the body run together and clamped to two lines by `-webkit-line-clamp`
      //: on the padded row itself, and a clamp paints the next line on into the
      //: row's bottom padding, which `overflow: hidden` clips at the padding
      //: edge: a third line showed sliced through its middle under every long
      //: row. The picker row's shape instead (DESIGN.md, `richPickerRow`): the
      //: note's first line as its name and the rest as one quiet line, each
      //: ellipsised by the stylesheet at the row's edge, never by a count.
      const name = entry.is_private ? "Private note" : noteNamePlain(entry.title || entry.content);
      const rest = entry.is_private ? "" : notePreviewText(bodyWithoutTitleLine(entry.content || "")).replace(/\s+/g, " ").trim();
      const title = document.createElement("span");
      title.className = "wb-library-item-title";
      title.textContent = name || (text ? text.slice(0, 120) : `Note ${entry.id}`);
      li.append(title);
      if (rest) {
        const more = document.createElement("span");
        more.className = "wb-library-item-preview";
        more.textContent = rest.slice(0, 240);
        li.append(more);
      }
      li.title = text || String(entry.id);
      li.draggable = true;
      li.addEventListener("dragstart", (e) => {
        e.dataTransfer.setData("text/plain", entry.id);
        e.dataTransfer.effectAllowed = "copy";
      });
      list.appendChild(li);
    }
  }

  //: **A response is only allowed to land on the board it was asked for.**
  //:
  //: Found while testing the board search, and it is worth writing down because
  //: it looked like a search bug for three rounds: `window.currentBoardId` read
  //: 128 (the board that had just been opened, and the one the picker showed)
  //: while `wbState.nodes` held the two cards of board 85. The board on screen
  //: was not the board the app thought was open.
  //:
  //: `openWhiteboardBoard` clicks the Boards & maps sub-tab, and that click
  //: starts its own load for whatever board was selected before; it then sets
  //: `currentBoardId` and starts a second load for the board actually asked
  //: for. Both used to `wbState = res` unconditionally, so whichever response
  //: happened to arrive last won, intermittently, which is why two identical
  //: probe runs disagreed.
  //:
  //: The guard is the ordinary one for an out-of-order response: remember which
  //: board the request was for, and throw the answer away if it is no longer
  //: the question being asked. Never mind "last write wins" with a sequence
  //: number: the board id *is* the identity here, and comparing it means a
  //: re-fetch of the same board still applies normally.
  async function fetchWhiteboardState() {
    const requestedBoardId = window.currentBoardId ?? null;
    try {
      const url = requestedBoardId ? `/whiteboard/?board_id=${requestedBoardId}` : "/whiteboard/";
      const res = await apiJson(url);
      if ((window.currentBoardId ?? null) !== requestedBoardId) return;
      wbState = res;
      // Before the board list, and awaited: everything that draws a map node
      // reads `window.wbMapState` for the board's type and for reference
      // labels, so a render that beat this call would draw the map as a plain
      // whiteboard once and then correct itself, a visible flash of the wrong
      // thing on every single board open.
      await wbRefreshMapState();
      wbSyncMapChrome();
      //: Here, the one fetch every way onto a board goes through, not only in
      //: `openWhiteboardBoard`: a map reached from the board picker or made by
      //: New board kept the board's rail (Notes, Layers, Pages), whose tabs a
      //: map sends back to Library, so only Library answered (INBOX 657).
      wbSyncSidebarKind();
      await refreshBoardList();
    } catch (err) {
      toast(voiceLine("failed", "open that board", err.message), true);
    }
  }

  // Reported directly: "the different board options confuse me." It used to
  // be every note in the notebook, since architecturally any note can serve as
  // a board_id: the picker took that literally and offered a 50-item dropdown
  // of notes that had never been anywhere near the whiteboard. GET
  // /whiteboard/boards lists only notes something is actually on, plus the
  // always-present default board (see routes_whiteboard.py for the full
  // writeup). Re-fetched on every state load rather than cached once: creating
  // or first-using a board should show up in the picker without a reload.
  // `justCreated`: a board this session just made, which won't come back from
  // the server yet: nothing is on it, and the endpoint only lists boards
  // something has actually been placed on (see its own docstring). Without
  // this, switching straight to a brand-new board made the dropdown fall back
  // to whatever option happened to match nothing, which looked like the new
  // board had failed to switch to at all.
  async function refreshBoardList(justCreated = null) {
    const select = document.getElementById("wb-board-select");
    if (!select) return;
    //: To the end, not the first page: `GET /whiteboard/boards` is paged now
    //: (`BOARDS_PAGE_SIZE`), and a picker that offers some of your boards is
    //: worse than one that takes a second request to offer all of them.
    const listed = await apiPagedList("/whiteboard/boards", 200, { silent: true }).catch(() => null);
    if (!listed) return;
    //: **The scratch board is offered when something is on it** (WHITEBOARD_PLAN
    //: decision 38; the owner, 2026-10-10: "also si there meant to be a
    //: default board??"). The server always lists it (`id: null`, "Default
    //: board"); the Library's gallery and counts already hid it while empty
    //: (`libraryListsBoard`), and this picker was the one place that offered
    //: an empty board nobody made. Kept while it is the board on screen.
    //: Not at the landing, where nothing is open: its empty row sat in the
    //: picker while the gallery above counted 0 boards and 0 maps.
    const landing = $("wb-boards-landing");
    const onCanvas = !landing || landing.classList.contains("hidden");
    const boards = listed.filter((b) => libraryListsBoard(b) || (b.id == null && window.currentBoardId == null && onCanvas));
    if (justCreated && !boards.some((b) => b.id === justCreated.id)) {
      boards.push({ ...justCreated, node_count: 0, sketch_count: 0, object_count: 0 });
    }
    select.replaceChildren();
    //: **A map says it is one, in the row** (MINDMAP_PLAN.md §5 item 12, the
    //: decision `mapChip` already follows on the timeline, in a note and in the
    //: chat). Reported: "whiteboards and mindmaps need to be differentiable in
    //: the boards selector". Measured before: five options reading
    //: `Title (N items)`, four of them maps, with nothing on any of them saying
    //: so, and an aria-label that called all five whiteboards.
    //:
    //: `<optgroup>` rather than a glyph in front of every label: a native
    //: `<option>` cannot hold the icon `mapChip` marks a map with (it renders as
    //: text only, and in the OS's own popup on Windows and macOS), so the choice
    //: is a character standing in for the icon or the platform's own way of
    //: saying "these are one kind and those are another". The app already uses
    //: `<optgroup>` for exactly that in three other selects, so this is the
    //: recipe rather than a fourth idea.
    //:
    //: Grouped only when both kinds are actually present: with nothing to tell
    //: it apart from, a lone "Whiteboards" heading above every row is a label
    //: that answers a question nobody asked.
    const mapsPresent = boards.some((b) => b.type === "map");
    const boardsPresent = boards.some((b) => b.type !== "map");
    const groups = new Map();
    if (mapsPresent && boardsPresent) {
      for (const [key, label] of [["map", "Mind maps"], ["board", "Whiteboards"]]) {
        const group = document.createElement("optgroup");
        group.label = label;
        groups.set(key, group);
        select.appendChild(group);
      }
    }
    for (const board of boards) {
      const opt = document.createElement("option");
      opt.value = board.id ?? "";
      // Images and text boxes count too, a board holding only those (no
      // cards or sketches) read as "(0 items)" here, which is exactly what
      // exposed this: a board with three text boxes on it, live-verified.
      //: **Each row says what it is** (INBOX 179: "I cant tell with this boards
      //: dropdown menu which is a whitebaord and which is a mindmap"). The
      //: optgroups above only appear when both kinds exist, so a list of two
      //: maps, or of one map and one board on a browser that draws optgroups
      //: quietly, said nothing. A word costs less than a guess, and a native
      //: <option> can carry nothing but text.
      const kind = board.type === "map" ? "Mind map" : "Board";
      opt.dataset.title = board.title;
      opt.dataset.kind = kind;
      opt.dataset.faceNarrow = board.title;
      opt.textContent = board.id === null
        ? `${kind} · ${board.title}`
        : `${kind} · ${board.title} (${wbBoardCountWords(board.type === "map",
        board.node_count, board.sketch_count - (board.link_count || 0), board.object_count || 0)})`;
      (groups.get(board.type === "map" ? "map" : "board") || select).appendChild(opt);
    }
    select.value = window.currentBoardId || "";
    // The default scratch board (`board_id=null`) has no underlying note to
    // rename: `rename_board` 404s on anything that isn't a real positive id.
    const renameBtn = document.getElementById("wb-rename-board");
    if (renameBtn) renameBtn.disabled = !window.currentBoardId;
    const suggestBtn = document.getElementById("wb-suggest-board-name");
    if (suggestBtn) suggestBtn.disabled = !window.currentBoardId;
  }

  //: **What the picker says a board holds** (audit 2026-10-05, UX-06). A map
  //: counts topics; a board counts what was put on it, and not the lines
  //: between cards, which are links rather than items. The open board's row is
  //: kept current from what is on screen (`wbSyncBoardCount`): it read
  //: "Pets (1 item)" with three cards on the board, because the list is
  //: fetched when the board opens and was never told about a Tab.
  function wbBoardCountWords(isMap, nodes, drawings, objects) {
    const n = isMap ? objects : nodes + Math.max(0, drawings) + objects;
    const noun = isMap ? "topic" : "item";
    return `${n} ${noun}${n === 1 ? "" : "s"}`;
  }

  function wbSyncBoardCount() {
    const opt = document.getElementById("wb-board-select")?.selectedOptions?.[0];
    if (!opt || !window.currentBoardId || !opt.dataset.title) return;
    const sketches = wbState.sketches || [];
    let links = 0;
    for (const sk of sketches) if (String(sk.data).includes('"type":"link-')) links++;
    const text = `${opt.dataset.kind} · ${opt.dataset.title} (${wbBoardCountWords(wbIsMap(),
    (wbState.nodes || []).length, sketches.length - links, (wbState.objects || []).length)})`;
    if (opt.textContent !== text) opt.textContent = text;
  }

  //: **The name is edited where it is read** (Brief 77, WHITEBOARD_PLAN
  //: "Deepened 2026-10-10" row 2): a field takes the board picker's place in
  //: the top bar, its words selected, so typing replaces them. Enter or leaving
  //: the field saves, Escape puts the name back; an empty or unchanged name
  //: writes nothing. Resolves with the saved title, or null.
  async function renameCurrentBoard() {
    const boardId = window.currentBoardId;
    const select = document.getElementById("wb-board-select");
    const bar = document.getElementById("wb-topbar");
    if (!boardId || !select || !bar) return Promise.resolve(null);
    document.getElementById("wb-name-field")?.blur();
    const current = select.selectedOptions?.[0]?.dataset.title || select.selectedOptions?.[0]?.textContent?.trim() || "";
    const field = document.createElement("input");
    field.type = "text";
    field.id = "wb-name-field";
    field.className = "wb-name-field";
    field.maxLength = 100;
    field.autocomplete = "off";
    field.value = current;
    field.setAttribute("aria-label", "Board name: Enter saves, Escape keeps the old one");
    field.title = "Enter saves, Escape keeps the old name";
    //: In the picker's place and at its width, so the bar does not move.
    const shell = select.closest(".select-shell") || select;
    field.style.width = `${Math.max(96, shell.getBoundingClientRect().width)}px`;
    shell.after(field);
    shell.hidden = true;
    return new Promise((resolve) => {
      let done = false;
      const finish = async (save) => {
        if (done) return;
        done = true;
        const name = field.value.trim();
        field.remove();
        shell.hidden = false;
        if (!save || !name || name === current || window.currentBoardId !== boardId) return resolve(null);
        try {
          const board = await apiJson(`/whiteboard/boards/${boardId}`, {
            method: "PUT",
            body: JSON.stringify({ title: name }),
          });
          await refreshBoardList(board);
          wbBoardPutStep(`Renamed the board to “${board.title}”`, boardId, { title: current }, { title: board.title });
          resolve(board.title);
        } catch (err) {
          toast(err.message || voiceLine("failed", "rename that board"), true);
          resolve(null);
        }
      };
      //: The board's own keys (Delete, V, N) must not see what is typed here.
      field.addEventListener("keydown", (e) => {
        e.stopPropagation();
        if (e.key === "Enter") {
          e.preventDefault();
          finish(true);
        } else if (e.key === "Escape") {
          e.preventDefault();
          finish(false);
        }
      });
      field.addEventListener("blur", () => finish(true));
      field.focus({ preventScroll: true });
      field.select();
    });
  }

  //: **New makes the board, then asks for its name in place** (Brief 77, row
  //: 2: a new board was four presses and a typed name, behind a dialog that
  //: had to be answered before there was anything to draw on). It is "Untitled
  //: board N" (`wbUntitledNames`, INBOX 739) and open at once; the templates
  //: stay one row away in the same New menu and in the Board menu.
  //: **A map the same way** (MINDMAP_PLAN 15, row 1: five presses and a typed
  //: name). It opens with its root topic in edit, because the root is what a
  //: person names first; what they type there names the map as well, while the
  //: map still carries the number it was given.
  async function wbNewUntitledBoard(kind = "board") {
    //: The name is asked for while the canvas comes up, not before it: one
    //: round trip off the press-to-first-topic time (row 4).
    const names = wbUntitledNames();
    wbShowCanvasView();
    await new Promise((resolve) => setTimeout(resolve, 60));
    const name = (await names)[kind];
    try {
      prefs.set(WB_LAST_BOARD_KIND, kind);
    } catch (err) { /* see wbRememberedBoardKind */ }
    await wbCreateBlankBoard(name, kind);
    const boardId = window.currentBoardId;
    if (!boardId) return;
    if (kind !== "map") {
      renameCurrentBoard();
      return;
    }
    const root = wbMapIndex().roots[0];
    if (!root) return;
    wbMapEditNode(root.id);
    requestAnimationFrame(() => {
      const label = wbInstances.query(`.wb-object[data-id="${root.id}"] .wb-map-text`);
      label?.addEventListener("blur", () => setTimeout(async () => {
        const typed = (label.textContent || "").trim();
        if (!typed || typed === name || window.currentBoardId !== boardId) return;
        try {
          const board = await apiJson(`/whiteboard/boards/${boardId}`, { method: "PUT", body: JSON.stringify({ title: typed.slice(0, 100) }) });
          await refreshBoardList(board);
          wbBoardPutStep(`Named the map “${board.title}”`, boardId, { title: name }, { title: board.title });
        } catch (err) { /* the map keeps its number; the topic kept its words */ }
      }), { once: true });
    });
  }

  function wbRememberedBoardKind() {
    try {
      const kind = prefs.get(WB_LAST_BOARD_KIND, null);
      return kind === "map" || kind === "board" ? kind : "board";
    } catch (err) {
      // Private mode, blocked site data: the default is the answer, not an error.
      return "board";
    }
  }

  //: **`reveal`: the canvas comes up when a board is chosen, not before** (INBOX
  //: 733: "it opens one of my whiteboards or mindmaps in the background rather
  //: than staying on the page I opened the create new board/mindmap panel
  //: from"). The Library's New menu used to show the canvas first, so the last
  //: board loaded behind the dialog and Cancel left it there. A caller already
  //: on the canvas passes nothing. The short wait is `openWhiteboardBoard`'s own:
  //: the canvas starts itself 50 ms after it is shown, and a board made before
  //: that would be drawn over by it.
  async function createNewBoard(preset = null, { reveal = false } = {}) {
    const showCanvas = async () => {
      if (!reveal) return;
      wbShowCanvasView();
      await new Promise((resolve) => setTimeout(resolve, 60));
    };
    //: **New board opens the template gallery** (BACKLOG 4b, decision 25):
    //: Blank, the built-in frames and your own templates, kind and name in one
    //: dialog (`wbOpenTemplateGallery`, whiteboard-library.js, in the same
    //: bundle as this file).
    if (typeof wbOpenTemplateGallery === "function") {
      const picked = await wbOpenTemplateGallery(preset || wbRememberedBoardKind());
      if (!picked) return;
      await showCanvas();
      try {
        prefs.set(WB_LAST_BOARD_KIND, picked.kind);
      } catch (err) { /* see wbRememberedBoardKind */ }
      if (!picked.ref) return wbCreateBlankBoard(picked.name, picked.kind);
      try {
        const board = await apiJson("/board-library/new-board", {
          method: "POST",
          body: JSON.stringify({ ...wbLibRefBody(picked.ref), name: picked.name, ink: wbLibInk() }),
        });
        window.wbLastCreatedBoard = board;
        await openWhiteboardBoard(board.id);
        if (board.type === "map") await wbMapTidyFresh();
        wbBoardMadeStep(board);
        //: A map frames itself (`wbFrameMapOnOpen`: a fit, or 1:1 on its root
        //: when the fit would be unreadable); fitting it again here made a
        //: wide template open at 17% on a phone.
        if (board.type !== "map") wbZoomToFit({ animate: false });
        toast(`"${board.title}" started from a template.`);
      } catch (err) {
        toast(err.message || voiceLine("failed", "create that board"), true);
      }
      return;
    }
    const answer = await promptDialog("Name the new board", "", {
      //: "Save" is what `promptDialog` says by default and it is the wrong verb
      //: for a dialog whose whole job is to make something that does not exist
      //: yet.
      confirmLabel: "Create",
      segment: {
        label: "What kind of board",
        value: preset || wbRememberedBoardKind(),
        // The icons are the same two the boards picker groups by and the Board
        // menu's Kind row uses, so the shape means the same thing everywhere.
        options: [
          {
            value: "board",
            label: "ph:squares-four Board",
            title: "A free canvas: notes, sketches, images",
          },
          {
            value: "map",
            label: "ph:tree-structure Mind map",
            title: "A tree: topics, branches and keyboard editing",
          },
        ],
      },
    });
    if (!answer) return;
    const kind = answer.choice === "map" ? "map" : "board";
    const name = (answer.text || "").trim()
      || (await wbUntitledNames())[kind];
    await showCanvas();
    //: Remembered on the way out, not on the click: a dialog someone dismissed
    //: said nothing about what they want next time.
    try {
      prefs.set(WB_LAST_BOARD_KIND, kind);
    } catch (err) { /* see wbRememberedBoardKind */ }
    return wbCreateBlankBoard(name, kind);
  }

  //: A blank board or map named `name`: the body `createNewBoard` always had.
  async function wbCreateBlankBoard(name, kind) {
    try {
      const board = await apiJson("/whiteboard/boards", {
        method: "POST",
        // A map is created **in** its layout, not converted into one afterwards:
        // `tree-right` is the layout every mainstream mindmapper opens in, and a
        // map that starts as `free` would put its first three nodes wherever the
        // server's fallback placement happened to drop them and only tidy up
        // once someone found the picker.
        body: JSON.stringify(
          kind === "map"
            ? { name: name.trim(), type: "map", layout: "tree-right" }
            : { name: name.trim() }
        ),
      });
      window.currentBoardId = board.id;
      if (kind === "map") {
        // One root topic, named after the map. **An empty canvas is the main
        // reason mindmap features go unused** (MINDMAP_PLAN.md §5 item 21), and
        // a map with nothing on it has no node to press Tab on, so the one
        // gesture the whole feature turns on would have nowhere to start.
        await apiJson(`/whiteboard/boards/${board.id}/nodes`, {
          method: "POST",
          body: JSON.stringify({ kind: "topic", parent_id: null, text: name.trim() }),
        }).catch((err) => toast(err.message || voiceLine("failed", "add the root topic"), true));
      }
      // `list_boards` only lists a board once something is actually placed on
      // it (see its own docstring), an empty new one is invisible to both
      // this dropdown (already handled below via `justCreated`) and the
      // landing gallery, which would otherwise make a board someone just
      // created appear to vanish the moment they go back to the list.
      window.wbLastCreatedBoard = board;
      // `fetchWhiteboardState`, not a bare GET: it is the one path that also
      // refreshes `window.wbMapState` and the top bar's map controls, and a map
      // created through a second copy of those two lines opened as an ordinary
      // whiteboard until the next board switch, the node was there, the Map
      // chip was not, and none of the keys worked.
      await fetchWhiteboardState();
      wbBoardMadeStep(board);
      wbScheduleRender();
      if (kind === "map") {
        // Selected, so Tab works on the very first keystroke. A map whose root
        // has to be clicked before the keyboard does anything teaches the wrong
        // thing about the feature in its first five seconds.
        const root = (wbState.objects || []).find((o) => WB_MAP_KINDS.has(o.kind));
        if (root) selectWbItem("object", root.id);
        renderWhiteboardNow();
        //: **Centred on the actual canvas, not wherever the server's own
        //: `tree-right` placement happened to land it.** Reported: a new map's
        //: first node opened under the top bar. The root is real DOM now
        //: (`renderWhiteboardNow` just ran), so its true rendered box is
        //: available for `wbCenterOn` (a guessed coordinate cannot do this:
        //: the visible canvas size is neither constant nor known until it is
        //: actually measured).
        if (root) wbCenterOn(wbItemBBox("object", root), { animate: false });
        //: One line and an action (U41, the owner 2026-11-03): the typing keys are in the Guide's map keys topic.
        toast(`Mind map "${board.title}" created. Tab adds a branch, Enter one beside it.`, false, { action: ["All keys", () => askAtlas("Mind map keys and controls")] });
      } else {
        toast(`Board "${board.title}" created.`);
      }
    } catch (err) {
      toast(err.message || voiceLine("failed", "create that board"), true);
    }
  }

  //: The file's surface: what other files call (L634).
  //: Private names a sweep drives (scratchpad/ui-sweeps), on an exported name so the shared scope does not grow.
  createNewBoard.sweep = { wbCreateBlankBoard };
  Object.assign(window, { wbPlaceNote, renderWbLibrary, fetchWhiteboardState, refreshBoardList, wbSyncBoardCount, renameCurrentBoard, wbNewUntitledBoard, createNewBoard });
})();
