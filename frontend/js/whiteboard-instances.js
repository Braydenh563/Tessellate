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

  function create(container, boardId) {
    return {
      container, boardId: boardId ?? null, state: { nodes: [], sketches: [], objects: [] },
      selectedItem: null, multiSelection: new Set(), undoStack: [], redoStack: [], zoom: null,
      mapState: null, renderPending: false, changeFns: new Set(), editable: true, listeners: [],
      invZoom: "1", invTimer: 0, key: ++made,
    };
  }

  //: **One zoom behaviour per container**, built from the page's own, so its
  //: transform lives on its own element (d3 keeps it there) and its listeners
  //: run the board's one handler with that instance live: a pan in a document
  //: never moves the page board.
  function zoomFor(inst) {
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
        if (active !== inst) activate(inst);
        return handler.call(this, event);
      });
    }
    return zoom;
  }

  function save(inst) {
    inst.state = wbState;
    inst.boardId = window.currentBoardId ?? null;
    inst.selectedItem = wbSelectedItem;
    inst.multiSelection = new Set(wbMultiSelection);
    inst.undoStack = wbUndoStack;
    inst.redoStack = wbRedoStack;
    inst.zoom = wbZoom;
    inst.mapState = window.wbMapState ?? null;
  }

  function load(inst) {
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
  function dropCaches() {
    wbItemElCache.clear();
    wbItemElIndex.count = -1;
    wbClearMapNodeSizeCache();
    Object.assign(wbBoardBgCache, { sig: "", pass: false });
    wbNavState.stale = true;
    wbLinkParseCache.clear();
  }

  //: Returns the outgoing board's nudge save (wbCancelBoardTimers), called while
  //: its globals are still live; nothing when `inst` is already active.
  function activate(inst) {
    if (!inst || inst === active) return undefined;
    //: A render queued for the outgoing board is called off with its timers and
    //: queued again when that board is active once more.
    const pending = wbRenderQueued || Boolean(wbRenderFrame);
    const flushed = wbCancelBoardTimers();
    save(active);
    active.renderPending = pending;
    active = inst;
    load(inst);
    dropCaches();
    wbUpdateUndoRedoButtons();
    if (inst.renderPending) {
      inst.renderPending = false;
      wbScheduleRender();
    }
    return flushed;
  }

  //: A board inside `container`, on `boardId`, with its own state and zoom.
  //: Not activated: the first gesture on it, or the caller, does that.
  function mount(container, boardId, editable = true) {
    const inst = create(container, boardId);
    inst.editable = editable;
    inst.zoom = zoomFor(inst);
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
      if (active !== inst) activate(inst);
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
  function unbind(inst) {
    for (const [el, type, fn, opts] of inst.listeners) el.removeEventListener(type, fn, opts);
    inst.listeners = [];
  }

  //: The embed an event's target is inside, or null: document-wide handlers
  //: (keys, paste) ask it to know whose board a keystroke is for.
  function embedFor(target) {
    if (!target) return null;
    return list.find((inst) => inst.container && inst.container.contains?.(target)) || null;
  }

  function unmount(inst) {
    if (inst === wbInstances.page) throw new Error("the page board is never unmounted");
    if (active === inst) activate(wbInstances.page);
    d3.select(inst.container).on(".zoom", null);
    unbind(inst);
    clearTimeout(inst.invTimer);
    const at = list.indexOf(inst);
    if (at >= 0) list.splice(at, 1);
  }

  function container() {
    return active.container || document.getElementById(PAGE_CONTAINER);
  }

  function layer(id) {
    return active.container ? active.container.querySelector(`[data-wb-layer="${id}"]`) : document.getElementById(id);
  }

  //: **A board selector, inside the active board** (L-whiteboard-55): searched in
  //: its container, the layer ids it names read as an embed's `data-wb-layer`.
  //: The page board's selector is unchanged and searched in the page container,
  //: so an embed's cards (same ids, same classes) are never found for the page.
  const LAYER_IDS = /#(wb-(?:svg-layer|zoom-group|shapes-group|lines-group|strokes-group|html-layer|overlay-layer|overlay-zoom-group))(?![\w-])/g;
  const scoped = (selector) => (active.container ? selector.replace(LAYER_IDS, '[data-wb-layer="$1"]') : selector);
  function queryOne(selector) {
    return container()?.querySelector(scoped(selector)) ?? null;
  }
  function queryEvery(selector) {
    return container()?.querySelectorAll(scoped(selector)) ?? [];
  }

  //: After each recorded edit (wbPushUndo): the active board's `onChange` listeners.
  function changed() {
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
  function skeleton(box) {
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
  const pageWake = () => activate(wbInstances.page);
  function pageListeners(on) {
    const el = document.getElementById(PAGE_CONTAINER);
    if (!el) return;
    for (const type of ["pointerdown", "focusin", "wheel"]) {
      if (on) el.addEventListener(type, pageWake, { capture: true, passive: true });
      else el.removeEventListener(type, pageWake, { capture: true });
    }
  }

  //: Draws `inst` with its globals live, then gives them back. The render's
  //: page-wide chrome (the empty hint, the count, the navigator, the outline) is
  //: written for the page board only, so the page needs no redraw after it.
  function draw(inst) {
    const was = active;
    activate(inst);
    try {
      renderWhiteboardNow();
    } finally {
      activate(was);
    }
  }

  //: **The mount API** (L-documents-104): a board inside `host`, an empty element
  //: the caller owns. Resolves once the board is read and drawn.
  async function createEmbed(host, boardId, opts = {}) {
    const editable = opts.editable === true;
    const box = document.createElement("div");
    box.className = editable ? "whiteboard-container wb-embed" : "whiteboard-container wb-embed wb-embed-readonly";
    box.tabIndex = 0;
    box.setAttribute("role", "application");
    box.setAttribute("aria-roledescription", "canvas");
    box.setAttribute("aria-label", "Board");
    skeleton(box);
    host.append(box);
    if (list.length === 1) pageListeners(true);
    const inst = mount(box, boardId, editable);
    box.setAttribute("data-wb-embed", String(inst.key));
    inst.destroyed = false;
    const wake = () => activate(inst);
    for (const type of ["pointerdown", "focusin"]) box.addEventListener(type, wake, { capture: true, passive: true });

    async function reload() {
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
      draw(inst);
    }

    function destroy() {
      if (inst.destroyed) return;
      inst.destroyed = true;
      for (const type of ["pointerdown", "focusin"]) box.removeEventListener(type, wake, { capture: true });
      unmount(inst);
      inst.changeFns.clear();
      box.remove();
      if (list.length === 1) pageListeners(false);
    }

    try {
      await reload();
    } catch (err) {
      destroy();
      throw err;
    }
    return {
      instance: inst,
      destroy,
      reload,
      focus: () => box.focus(),
      onChange(fn) {
        inst.changeFns.add(fn);
        return () => inst.changeFns.delete(fn);
      },
    };
  }

  const page = create(null, null);
  page.zoom = wbZoom;
  list.push(page);
  active = page;

  const wbInstances = {
    page, list, mount, unmount, activate, container, layer, query: queryOne, queryAll: queryEvery, changed, on: bindBoard, embedFor,
    get active() { return active; },
  };

  //: The file's surface: what other files call.
  Object.assign(window, { wbInstances, wbInstance: { create: createEmbed } });
})();
