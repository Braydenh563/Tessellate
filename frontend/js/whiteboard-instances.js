(() => {
  // whiteboard-instances.js: board state per instance (L-whiteboard-53, for L-documents-104).
  // Wrapped: two names on `window`, `wbInstances` (the board side) and `wbInstance` (the mount API documents
  // builds to, L-documents-104); nothing here runs at load but the page instance's creation.
  //
  //: **The board's globals keep meaning "the active board".** `wbState`,
  //: `currentBoardId`, `wbSelectedItem`, `wbMultiSelection`, `wbUndoStack`,
  //: `wbRedoStack` and `wbZoom` are read at about nine hundred sites; renaming
  //: each to an instance field was the riskier change. An instance holds its own
  //: copy of them while another board is active, and `activate` swaps the live
  //: globals out to the outgoing instance and in from the incoming one, so the
  //: full-page board is just the default instance and nothing it does changed.
  //: The container and its layers are found through the active instance
  //: (`wbInstances.container()`, `.layer(id)`): the page board resolves them by id as before,
  //: a mounted one inside its own element by `data-wb-layer`, since an id can
  //: appear once on a page.
  const PAGE_CONTAINER = "whiteboard-container";
  //: The page behaviour's settings an embed's copy takes over
  //: (tests/test_wb_instances.py checks whiteboard.js's chain uses no other).
  const ZOOM_SETTINGS = ["scaleExtent", "wheelDelta", "filter", "clickDistance", "tapDistance", "duration"];
  const ZOOM_EVENTS = ["zoom", "start.companion", "end.shield"];
  const list = [];
  let active = null;

  function newInstance(container, boardId) {
    return {
      container, boardId: boardId ?? null, state: { nodes: [], sketches: [], objects: [] },
      selectedItem: null, multiSelection: new Set(), undoStack: [], redoStack: [], zoom: null,
      mapState: null, renderPending: false, changeFns: new Set(),
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
    inst.undoStack = wbUndoStack;
    inst.redoStack = wbRedoStack;
    inst.zoom = wbZoom;
    inst.mapState = window.wbMapState ?? null;
  }

  function restoreGlobals(inst) {
    wbState = inst.state;
    window.currentBoardId = inst.boardId;
    wbSelectedItem = inst.selectedItem;
    //: A const Set other code holds by reference: refilled, never replaced.
    wbMultiSelection.clear();
    for (const key of inst.multiSelection) wbMultiSelection.add(key);
    wbUndoStack = inst.undoStack;
    wbRedoStack = inst.redoStack;
    wbZoom = inst.zoom;
    window.wbMapState = inst.mapState;
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
    if (inst.renderPending) {
      inst.renderPending = false;
      wbScheduleRender();
    }
    return flushed;
  }

  //: A board inside `container`, on `boardId`, with its own state and zoom.
  //: Not activated: the first gesture on it, or the caller, does that.
  function mountInstance(container, boardId) {
    const inst = newInstance(container, boardId);
    inst.zoom = instanceZoom(inst);
    d3.select(container).call(inst.zoom).on("dblclick.zoom", null);
    list.push(inst);
    return inst;
  }

  function unmountInstance(inst) {
    if (inst === wbInstances.page) throw new Error("the page board is never unmounted");
    if (active === inst) activateInstance(wbInstances.page);
    d3.select(inst.container).on(".zoom", null);
    const at = list.indexOf(inst);
    if (at >= 0) list.splice(at, 1);
  }

  function activeContainer() {
    return active.container || document.getElementById(PAGE_CONTAINER);
  }

  function activeLayer(id) {
    return active.container ? active.container.querySelector(`[data-wb-layer="${id}"]`) : document.getElementById(id);
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

  //: The page board becomes active again when it is touched or focused; bound
  //: while any embed exists and removed with the last one.
  const pageWake = () => activateInstance(wbInstances.page);
  function pageWakeListeners(on) {
    const el = document.getElementById(PAGE_CONTAINER);
    if (!el) return;
    for (const type of ["pointerdown", "focusin", "wheel"]) {
      if (on) el.addEventListener(type, pageWake, { capture: true, passive: true });
      else el.removeEventListener(type, pageWake, { capture: true });
    }
  }

  //: Draws `inst` with its globals live, then gives them back. The board's one
  //: render also writes page-wide chrome (the empty hint, the count), so the page
  //: board is drawn again on the next frame once it has been opened.
  function drawEmbed(inst) {
    const was = active;
    activateInstance(inst);
    try {
      renderWhiteboardNow();
    } finally {
      activateInstance(was);
    }
    if (was !== inst && wbInitialized) wbScheduleRender();
  }

  //: **The mount API** (L-documents-104): a board inside `host`, an empty element
  //: the caller owns. Resolves once the board is read and drawn.
  async function createEmbed(host, boardId, opts = {}) {
    const box = document.createElement("div");
    box.className = "whiteboard-container wb-embed";
    box.tabIndex = 0;
    box.setAttribute("role", "application");
    box.setAttribute("aria-roledescription", "canvas");
    box.setAttribute("aria-label", "Board");
    embedSkeleton(box);
    host.append(box);
    if (list.length === 1) pageWakeListeners(true);
    const inst = mountInstance(box, boardId);
    inst.editable = opts.editable === true;
    inst.destroyed = false;
    const wake = () => activateInstance(inst);
    for (const type of ["pointerdown", "focusin"]) box.addEventListener(type, wake, { capture: true, passive: true });

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
      for (const type of ["pointerdown", "focusin"]) box.removeEventListener(type, wake, { capture: true });
      unmountInstance(inst);
      inst.changeFns.clear();
      box.remove();
      if (list.length === 1) pageWakeListeners(false);
    }

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
    page, list, mount: mountInstance, unmount: unmountInstance, activate: activateInstance, container: activeContainer, layer: activeLayer, changed: notifyChanged,
    get active() { return active; },
  };

  //: The file's surface: what other files call.
  Object.assign(window, { wbInstances, wbInstance: { create: createEmbed } });
})();
