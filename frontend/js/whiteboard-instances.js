(() => {
  // whiteboard-instances.js: board state per instance (L-whiteboard-53, for L-documents-104).
  // Wrapped: two names on `window`, `wbInstances` (the board side) and `wbInstance` (the mount API documents
  // builds to, L-documents-104); nothing here runs at load but the page instance's creation and the event router.
  //
  //: **The board's globals keep meaning "the active board".** `wbState`,
  //: `currentBoardId`, `wbSelectedItem`, `wbMultiSelection`, `wbUndoStack`,
  //: `wbRedoStack` and `wbZoom` are read at about nine hundred sites; renaming
  //: each to an instance field was the riskier change. An instance holds its own
  //: copy of them while another board is active, and `activate` swaps the live
  //: globals out to the outgoing instance and in from the incoming one, so the
  //: full-page board is just the default instance and nothing it does changed.
  //: The container and its layers are found through the active instance
  //: (`container()`, `layer(id)`): the page board resolves them by id as before,
  //: a mounted one inside its own element by `data-wb-layer`, since an id can
  //: appear once on a page.
  const PAGE_CONTAINER = "whiteboard-container";
  //: The page behaviour's settings an embed's copy takes over
  //: (tests/test_wb_instances.py checks whiteboard.js's chain uses no other).
  const ZOOM_SETTINGS = ["scaleExtent", "wheelDelta", "filter", "clickDistance", "tapDistance", "duration"];
  const ZOOM_EVENTS = ["zoom", "start.companion", "end.shield"];
  const list = [];
  let active = null;
  let made = 0;

  function newInstance(container, boardId) {
    return {
      container, boardId: boardId ?? null, state: { nodes: [], sketches: [], objects: [] },
      selectedItem: null, multiSelection: new Set(), undoStack: [], redoStack: [], zoom: null,
      mapState: null, renderPending: false, changeFns: new Set(), editable: true, listeners: [],
      //: `stale`: a save failed while this board was not live, so it reads itself again when it is
      //: (the page board); `reload`: an embed's own read, which needs no live globals.
      stale: false, reload: null,
      invZoom: "1", invTimer: 0, key: ++made,
      //: The tool in hand on this board (L-whiteboard-61): a new one starts on the page board's first tool.
      tool: "pan",
      //: `wbHistoryBoard`, the board whose stacks `wbHistoryFor` holds live: an
      //: instance's own, so its first read keeps the stacks it has.
      historyBoard: String(boardId ?? "default"),
    };
  }

  //: **One zoom behaviour per container**, built from the page's own, so its
  //: transform lives on its own element (d3 keeps it there) and its listeners
  //: run the board's one handler with that instance live: a pan in a document
  //: never moves the page board.
  function instanceZoom(inst) {
    const zoom = d3.zoom();
    const base = wbInstances.page.zoom;
    for (const key of ZOOM_SETTINGS) zoom[key](base[key]());
    //: A read-only board has no tool, so any plain drag pans it (L-whiteboard-54);
    //: the wheel keeps the page's rule.
    if (!inst.editable) {
      const wheel = base.filter();
      zoom.filter(function (event) {
        return event.type === "wheel" ? wheel.call(this, event) : !event.ctrlKey && !(event.button > 1);
      });
    }
    for (const name of ZOOM_EVENTS) {
      const handler = base.on(name);
      if (handler) zoom.on(name, function (event) {
        if (active !== inst) activateInstance(inst);
        return handler.call(this, event);
      });
    }
    return zoom;
  }

  function stashGlobals(inst) {
    inst.state = wbState;
    inst.boardId = window.currentBoardId ?? null;
    inst.selectedItem = wbSelectedItem;
    inst.multiSelection = new Set(wbMultiSelection);
    inst.undoStack = wbStacks.undo;
    inst.redoStack = wbStacks.redo;
    inst.zoom = wbZoom;
    inst.mapState = window.wbMapState ?? null;
    inst.historyBoard = wbStacks.historyBoard;
    inst.tool = window.currentTool;
    inst.optsView = wbFmtState.opts?.view();
  }

  function restoreGlobals(inst) {
    wbState = inst.state;
    window.currentBoardId = inst.boardId;
    wbSelectedItem = inst.selectedItem;
    //: A const Set other code holds by reference: refilled, never replaced.
    wbMultiSelection.clear();
    for (const key of inst.multiSelection) wbMultiSelection.add(key);
    wbStacks.undo = inst.undoStack;
    wbStacks.redo = inst.redoStack;
    wbZoom = inst.zoom;
    window.wbMapState = inst.mapState;
    wbStacks.historyBoard = inst.historyBoard;
    window.currentTool = inst.tool;
    //: A board never shown starts on pixels and no page frames (L-whiteboard-67).
    wbFmtState.opts?.view(inst.optsView || { unit: "px", pagesKey: "" });
  }

  //: The same caches openWhiteboardBoard drops on a board switch: each answers
  //: for elements of the board that was live, and the next one has others.
  function dropBoardCaches() {
    wbItemElCache.clear();
    wbItemElIndex.count = -1;
    wbClearMapNodeSizeCache();
    Object.assign(wbBoardBgCache, { sig: "", pass: false });
    wbNavState.stale = true;
    wbLinkParseCache.clear();
    //: The canvas's screen box: a key or a paste routed to another board has no press to drop it first.
    wbClearCanvasRectCache();
  }

  //: Returns the outgoing board's nudge save (wbCancelBoardTimers), called while
  //: its globals are still live; nothing when `inst` is already active.
  function activateInstance(inst) {
    if (!inst || inst === active) return undefined;
    //: A render queued for the outgoing board is called off with its timers and
    //: queued again when that board is active once more.
    const pending = wbRenderQueued || Boolean(wbRenderFrame);
    const flushed = wbCancelBoardTimers();
    stashGlobals(active);
    active.renderPending = pending;
    active = inst;
    restoreGlobals(inst);
    dropBoardCaches();
    wbUpdateUndoRedoButtons();
    //: The toolbar and the incoming container's cursor show its own tool.
    wbSelectToolRef?.swap(inst.tool);
    //: The read counts only if it replaced `wbState` while `inst` was still live. The fetch
    //: toasts its own failure and drops an answer for another board, so either leaves
    //: `inst` stale and its next activation reads again (L-whiteboard-74).
    if (inst.stale) {
      inst.stale = false;
      const before = wbState;
      fetchWhiteboardState().then(() => {
        if (active === inst && wbState !== before) wbScheduleRender();
        else inst.stale = true;
      });
    }
    if (inst.renderPending) {
      inst.renderPending = false;
      wbScheduleRender();
    }
    return flushed;
  }

  //: A board inside `container`, on `boardId`, with its own state and zoom.
  //: Not activated: the first gesture on it, or the caller, does that.
  function mountInstance(container, boardId, editable = true) {
    const inst = newInstance(container, boardId);
    inst.editable = editable;
    inst.zoom = instanceZoom(inst);
    d3.select(container).call(inst.zoom).on("dblclick.zoom", null);
    list.push(inst);
    for (const entry of handlers) bindOne(inst, entry);
    return inst;
  }

  //: **The board's own listeners, on every instance's container** (L-whiteboard-54).
  //: initWhiteboard binds its pointer, key, wheel and drop handlers through `on` (`bindBoard` here),
  //: once; each instance, the page's and every embed's, gets its own copy, which
  //: makes that instance live before the handler runs, so a handler reads the
  //: board the event happened on. A read-only embed gets only the `view` ones
  //: (pan and zoom).
  const handlers = [];
  function bindOne(inst, entry) {
    if (!inst.editable && !entry.view) return;
    const el = inst.container || document.getElementById(PAGE_CONTAINER);
    if (!el) return;
    const fn = function (event) {
      if (active !== inst) activateInstance(inst);
      return entry.fn.call(this, event);
    };
    el.addEventListener(entry.type, fn, entry.opts);
    inst.listeners.push([el, entry.type, fn, entry.opts]);
  }
  function bindBoard(type, fn, opts, view = false) {
    const entry = { type, fn, opts, view };
    handlers.push(entry);
    for (const inst of list) bindOne(inst, entry);
  }
  function unbindInstance(inst) {
    for (const [el, type, fn, opts] of inst.listeners) el.removeEventListener(type, fn, opts);
    inst.listeners = [];
  }

  //: The embed an event's target is inside, or null: document-wide handlers
  //: (keys, paste) ask it to know whose board a keystroke is for.
  function embedFor(target) {
    if (!target) return null;
    return list.find((inst) => inst.container && inst.container.contains?.(target)) || null;
  }

  function unmountInstance(inst) {
    if (inst === wbInstances.page) throw new Error("the page board is never unmounted");
    if (active === inst) activateInstance(wbInstances.page);
    d3.select(inst.container).on(".zoom", null);
    unbindInstance(inst);
    clearTimeout(inst.invTimer);
    const at = list.indexOf(inst);
    if (at >= 0) list.splice(at, 1);
  }

  function activeContainer() {
    return active.container || document.getElementById(PAGE_CONTAINER);
  }

  function activeLayer(id) {
    return active.container ? active.container.querySelector(`[data-wb-layer="${id}"]`) : document.getElementById(id);
  }

  //: **A board selector, inside the active board** (L-whiteboard-55): searched in
  //: its container, the layer ids it names read as an embed's `data-wb-layer`.
  //: The page board's selector is unchanged and searched in the page container,
  //: so an embed's cards (same ids, same classes) are never found for the page.
  const LAYER_IDS = /#(wb-(?:svg-layer|zoom-group|shapes-group|lines-group|strokes-group|html-layer|overlay-layer|overlay-zoom-group))(?![\w-])/g;
  const scoped = (selector) => (active.container ? selector.replace(LAYER_IDS, '[data-wb-layer="$1"]') : selector);
  function queryOne(selector) {
    return activeContainer()?.querySelector(scoped(selector)) ?? null;
  }
  function queryEvery(selector) {
    return activeContainer()?.querySelectorAll(scoped(selector)) ?? [];
  }

  //: After each recorded edit (wbPushUndo): the active board's `onChange` listeners.
  function notifyChanged() {
    for (const fn of [...active.changeFns]) {
      try {
        fn();
      } catch (err) {
        console.warn("board onChange listener failed", err);
      }
    }
  }

  //: **An embed's own DOM**: the page board's three layers, found by
  //: `data-wb-layer` inside its container instead of by id.
  function embedSkeleton(box) {
    const svg = (layerId, cls) => {
      const el = document.createElementNS("http://www.w3.org/2000/svg", cls ? "svg" : "g");
      if (cls) el.setAttribute("class", cls);
      el.setAttribute("data-wb-layer", layerId);
      return el;
    };
    const base = svg("wb-svg-layer", "wb-svg-layer");
    const zoomGroup = svg("wb-zoom-group");
    zoomGroup.append(svg("wb-shapes-group"), svg("wb-lines-group"), svg("wb-strokes-group"));
    base.append(zoomGroup);
    const html = document.createElement("div");
    html.className = "wb-html-layer";
    html.setAttribute("data-wb-layer", "wb-html-layer");
    const overlay = svg("wb-overlay-layer", "wb-svg-layer");
    overlay.append(svg("wb-overlay-zoom-group"));
    box.append(base, html, overlay);
  }

  //: **Every board event finds its own board first** (L-whiteboard-62). Window and document
  //: listeners (keys, paste, the drags' window halves, the menus' outside clicks) read the
  //: live globals, so the board an event starts on is made live before any of them runs: one
  //: window capture listener, registered at load ahead of every board file after this one,
  //: activates the embed the target is in, or the page board for its own view and toolbar.
  //: Only the events that start something: a move or a lift during a drag stays with the
  //: board the drag began on, and so does a wheel turned while a button is held.
  const ROUTED = ["pointerdown", "mousedown", "touchstart", "contextmenu", "dblclick", "wheel", "keydown", "focusin", "paste", "drop"];
  function routeToBoard(event) {
    //: Only the page board: nothing to route, so every key and wheel in the app costs one compare (L-whiteboard-76).
    if (list.length === 1) return;
    if (event.type === "wheel" && event.buttons) return;
    const target = event.target;
    const onPageView = document.getElementById(PAGE_CONTAINER)?.contains?.(target) || target?.closest?.("#library-view-whiteboard");
    const inst = embedFor(target) || (onPageView ? page : null);
    if (inst) activateInstance(inst);
  }
  for (const type of ROUTED) window.addEventListener(type, routeToBoard, { capture: true, passive: true });

  //: Draws `inst` with its globals live, then gives them back. The render's
  //: page-wide chrome (the empty hint, the count, the navigator, the outline) is
  //: written for the page board only, so the page needs no redraw after it.
  function drawEmbed(inst) {
    const was = active;
    activateInstance(inst);
    try {
      renderWhiteboardNow();
    } finally {
      activateInstance(was);
    }
  }

  //: **The mount API** (L-documents-104): a board inside `host`, an empty element
  //: the caller owns. Resolves once the board is read and drawn.
  //: One run of initWhiteboard for every embed made before the page board was
  //: ever opened: it binds the board's handlers through `on`, so an embed made
  //: without waiting for it would be a board that cannot be edited (L-whiteboard-63).
  let embedBoardInit = null;
  let embedHints = 0;
  //: A board's title for an embed's accessible name: the boards list, shared by embeds made together and read again when a board is missing from it.
  let embedTitles = null;
  async function embedTitle(boardId) {
    if (boardId == null) return "";
    embedTitles ??= apiPagedList("/whiteboard/boards", 200, { silent: true }).catch(() => (embedTitles = null));
    const rows = await embedTitles;
    const found = rows?.find((row) => row.id === boardId);
    if (!found) embedTitles = null; //: A board made or renamed since the read: ask again next time.
    return found?.title?.trim() || "";
  }
  async function createEmbed(host, boardId, opts = {}) {
    const editable = opts.editable === true;
    //: Only a real promise is kept, and a failed one is dropped, so the next embed tries again (L-whiteboard-75).
    if (!embedBoardInit) {
      const run = window.initWhiteboard?.();
      if (run && typeof run.then === "function") embedBoardInit = run.catch((err) => { embedBoardInit = null; throw err; });
    }
    await embedBoardInit;
    const box = document.createElement("div");
    box.className = editable ? "whiteboard-container wb-embed" : "whiteboard-container wb-embed wb-embed-readonly";
    box.tabIndex = 0;
    //: **An embed is named and roled by what it can do** (L-whiteboard-72): a read-only one is a group
    //: (pan and zoom only), an editable one an application that points at a hidden keyboard hint.
    box.setAttribute("role", editable ? "application" : "group");
    box.setAttribute("aria-roledescription", "canvas");
    box.setAttribute("aria-label", opts.title || "Board");
    embedSkeleton(box);
    host.append(box);
    //: The hint sits beside the box in the host, not inside it: the box's children are the board's layers only.
    let hint = null;
    if (editable) {
      hint = document.createElement("span");
      hint.className = "visually-hidden";
      hint.id = `wb-embed-hint-${++embedHints}`;
      hint.textContent = "Tab moves through the items, the arrow keys move what is selected, and a letter picks a tool.";
      host.append(hint);
      box.setAttribute("aria-describedby", hint.id);
    }
    const inst = mountInstance(box, boardId, editable);
    box.setAttribute("data-wb-embed", String(inst.key));
    inst.destroyed = false;
    //: The title is looked up after the mount, so a slow list never holds the board back; "Board" stays until it lands.
    if (!opts.title) embedTitle(boardId).then((title) => { if (title && !inst.destroyed) box.setAttribute("aria-label", title); });
    //: `opts.historyKey` names this embed to its host, so its undo history is kept under its own key (L-whiteboard-70).
    if (opts.historyKey != null) wbEmbedHistoryRestore(inst, opts.historyKey);

    async function reloadEmbed() {
      const url = boardId ? `/whiteboard/?board_id=${boardId}` : "/whiteboard/";
      const [state, mapState] = await Promise.all([apiJson(url), wbRefreshMapState(boardId ?? null)]);
      if (inst.destroyed) return;
      if (active === inst) {
        wbState = state;
        window.wbMapState = mapState;
      } else {
        inst.state = state;
        inst.mapState = mapState;
      }
      drawEmbed(inst);
    }

    function destroyEmbed() {
      if (inst.destroyed) return;
      inst.destroyed = true;
      unmountInstance(inst);
      inst.changeFns.clear();
      box.remove();
      hint?.remove();
    }

    inst.reload = reloadEmbed;
    try {
      await reloadEmbed();
    } catch (err) {
      destroyEmbed();
      throw err;
    }
    return {
      instance: inst,
      destroy: destroyEmbed,
      reload: reloadEmbed,
      focus: () => box.focus(),
      onChange(fn) {
        inst.changeFns.add(fn);
        return () => inst.changeFns.delete(fn);
      },
    };
  }

  const page = newInstance(null, null);
  page.zoom = wbZoom;
  list.push(page);
  active = page;

  const wbInstances = {
    page, list, mount: mountInstance, unmount: unmountInstance, activate: activateInstance, container: activeContainer, layer: activeLayer, query: queryOne, queryAll: queryEvery, changed: notifyChanged, on: bindBoard, embedFor,
    get active() { return active; },
    //: The page board is live: its view's own chrome (the rulers, the map rings) is drawn for it only (L-whiteboard-60).
    get onPage() { return active === page; },
  };

  //: The file's surface: what other files call.
  Object.assign(window, { wbInstances, wbInstance: { create: createEmbed } });
})();
