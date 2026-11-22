(() => {
  // whiteboard-menus.js: the board's menus (open, close, clip) and its keyboard shortcuts; a section of initWhiteboard (L634).
  // Wrapped: initWhiteboard calls it once, passing the names it shares; nothing here runs at load.
  function wbInitMenus({ updateWbCursor, undoBtn, selectWbTool }) {
    // Asked for directly: the toolbar should be adjustable as a sidebar, not
    // only a bottom bar. `data-dock` drives the CSS (row vs. column layout,
    // which edge it's pinned to); persisted so the choice survives a reload
    // the same way panel positions already do.
    // **Three grouped menus in the top bar, Insert, View, Board.** Asked
    // for: "add more features in the top bar and spread them out in grouped
    // section dropdowns." One `.wb-board-menu-wrap` per menu; opening one
    // closes the others; an outside click or Escape (capture phase: the
    // board's own keydown swallows Escape from a focused toolbar button)
    // closes all. The Insert menu reuses the dock's own tool buttons so the
    // two can never disagree about what a sticky or a text box is.
    //: Each menu is held by reference rather than found again through its wrap:
    //: once `escapeMenuIfClipped` has moved it to <body> it is no longer inside
    //: the wrap at all, and a `wrap.querySelector` close would find nothing and
    //: leave the menu open for good.
    const boardMenus = [...document.querySelectorAll(".wb-board-menu-wrap")]
      .map((wrap) => ({ toggle: wrap.querySelector("[data-wb-menu-toggle]"), menu: wrap.querySelector(".wb-board-menu") }))
      .filter((pair) => pair.toggle && pair.menu);
    for (const { menu, toggle } of boardMenus) {
      wbFoldMenuSubmenus(menu);
      wbStampMenuRoles(menu);
      //: The arrow keys, Home and End, from the same function every other menu
      //: in the app uses (`wireMenuKeyboard`, app.js). Measured before it was
      //: called here (`scratchpad/ui-sweeps/wbtopbar.js`): all five top-bar
      //: menus opened with `role="menu"` and not one `role="menuitem"` in them,
      //: so a screen reader was told "menu, 0 items", and ArrowDown moved the
      //: focus nowhere. Tab stepped through the items, because they are buttons,
      //: which is why nobody driving it with a mouse ever saw this.
      wireMenuKeyboard(menu, toggle);
    }
    const closeAllWbMenus = () => {
      //: A flyout lives at <body> while open, so it is found there, not in a menu.
      for (const sub of document.querySelectorAll(".submenu.wb-board-menu:not(.hidden)")) {
        sub.classList.add("hidden");
        sub._escapedOpener.setAttribute("aria-expanded", "false");
        restoreEscapedMenu(sub);
      }
      for (const { toggle, menu } of boardMenus) {
        menu.classList.add("hidden");
        toggle.setAttribute("aria-expanded", "false");
        //: A nested level (under 820) reopens at the menu's top rows.
        for (const open of menu.querySelectorAll(".menu-group-open")) open.classList.remove("menu-group-open");
        menu.classList.remove("menu-nested");
        // Back where it lives, and the stylesheet's own cap back: the next open
        // measures from scratch rather than from a stale number.
        restoreEscapedMenu(menu);
        menu.style.maxHeight = "";
      }
    };
    //: **A top-bar menu stays inside the window and scrolls when it is taller.**
    //:
    //: Reported with a screenshot of the View menu (INBOX 43): the menus "clip
    //: at the bottom of the panel and do not scroll". A cap alone was not the
    //: whole story: measured at 1280x640 with a board open, View and Arrange
    //: both ended at y=628 inside a 640px window, correctly capped, while
    //: `#library-view-whiteboard` (`overflow: hidden`) ends at y=579, so the
    //: last 49px of each menu were cut off by an ancestor and unreachable,
    //: scrollbar or no scrollbar. Escaping that ancestor is what fixed it.
    //:
    //: `escapeAndCapMenu` (menus.js) is that fix, and `details.dock-menu`'s too:
    //: this file used to hold its own copy of it, identical down to the margin
    //: and the 120px floor, which is how a later improvement to one of them
    //: would have missed the other. It is deliberately not the same recipe as
    //: `wireEscapedActionMenu`'s `place()`, which positions its menu itself;
    //: these menus keep the position the stylesheet gives them whenever nothing
    //: clips them, and only their height is decided. The reasons are written out
    //: at both functions in app.js.
    //: The open is one named function rather than the body of each toggle's
    //: listener: it shows the menu and then measures it, which is one layout
    //: per click and unavoidable, but written inside the loop that binds the
    //: listeners it read as a write-then-read per turn to
    //: `test_no_loop_reads_layout_after_writing_style`, which cannot tell a
    //: listener body from the loop's own.
    function toggleBoardMenu(toggle, menu) {
      const wasHidden = menu.classList.contains("hidden");
      closeAllWbMenus();
      if (wasHidden) {
        menu.classList.remove("hidden");
        toggle.setAttribute("aria-expanded", "true");
        // Before the measurement: a switch's own state can change how tall
        // the list is.
        syncPanelSwitches();
        wbMapFoldToLevel.sync();
        wbSyncCommandRows(menu);
        menu.classList.remove("wb-menu-one-col");
        escapeAndCapMenu(menu, toggle);
        //: **Hung from what opened it, every one of them** (INBOX 396). A
        //: top-bar menu escaped to <body> went through `placeEscapedMenu`'s
        //: last resort when the window could not hold it below or above its
        //: button, and was pinned across the button instead: measured, Arrange
        //: at 1440x600 drew from 99 to 592 over its own toggle and the top
        //: bar, and at 1280x520 Insert, Arrange and Board did the same. The
        //: context bar's menu already had the fix; the top bar's use it with
        //: their own toggle as the edge, so each opens under its button and
        //: scrolls inside the room there (`wbmenuroom.js`).
        //: **Two columns only while they fit.** The View menu is a two-column
        //: box, and a multi-column box under a height cap does not scroll its
        //: overflow: it adds columns beside itself, out past the menu's edge.
        //: Measured on a mind map's View: at 390 (the phone rule now drops the
        //: columns) and at 1024x480, 1015px of columns in a 510px menu capped
        //: to 280px. Overflow sideways is the sign; one scrolling column is
        //: the answer, placed and capped again at its new size.
        const edge = menu.id === "wb-context-menu" ? document.getElementById("wb-context") : toggle;
        wbKeepMenuBesideBar(menu, edge);
        if (menu.scrollWidth > menu.clientWidth + 1) {
          menu.classList.add("wb-menu-one-col");
          escapeAndCapMenu(menu, toggle);
          wbKeepMenuBesideBar(menu, edge);
        }
        if (menu.classList.contains("wb-map-strip-menu")) wbMapStripMenuOffTopic(menu, toggle);
      }
    }
    for (const { toggle, menu } of boardMenus) {
      toggle.addEventListener("click", (e) => {
        e.stopPropagation();
        toggleBoardMenu(toggle, menu);
      });
    }
    document.addEventListener("click", (e) => {
      if (e.target.closest(".wb-board-menu, .wb-board-menu-wrap")) return;
      // A Panels switch forwards to the top bar's own toggle with a synthetic
      // `.click()`, which bubbled here as an "outside" click and shut the
      // menu the moment a switch was used (reported). Only a real pointer
      // or keyboard click outside the menu closes it.
      if (!e.isTrusted) return;
      closeAllWbMenus();
    });
    document.addEventListener("keydown", (e) => {
      //: In a flyout (or a nested level) Escape is the flyout's: it closes back to its row.
      if (e.key !== "Escape" || document.activeElement.closest(".submenu.wb-board-menu:not(.hidden)")) return;
      //: Escape hands the focus back to the toggle that opened the menu, which
      //: is the half of the contract that was missing: the menu closed and the
      //: focus stayed on the item that had just vanished, so the next Tab
      //: started from the top of the document. The toggle is read *before* the
      //: close, because closing clears the state that says which one was open.
      //: Only when the focus is in the menu or on its own toggle: Escape is a
      //: board-wide key (it leaves full screen, it drops a selection), and a
      //: press with the focus on the canvas must not pull it into the bar.
      const open = boardMenus.find(({ menu }) => !menu.classList.contains("hidden"));
      const inside = open && (open.menu.contains(document.activeElement) || document.activeElement === open.toggle);
      closeAllWbMenus();
      if (inside) open.toggle.focus();
      //: **With a menu open, Escape closes the menu and nothing else.** It went
      //: on to the board's own Escape, which drops the selection: measured, a
      //: text box selected, its More menu or Arrange opened, one Escape, and
      //: the menu, the selection and the context bar were all gone, so the next
      //: press on the bar's More landed on the canvas (`wbmenuroom.js`). One key
      //: undoes one thing, the innermost, as it does in every editor.
      if (open) {
        e.preventDefault();
        e.stopPropagation();
      }
    }, true);
    // Edit / Arrange menu items forward to the control that already owns the
    // action (`data-wb-click`), so a menu can never drift from the dock, the
    // drawer or the selection bar. `data-wb-fn` is for the one action with
    // no button of its own.
    document.addEventListener("click", (e) => {
      //: `.wb-menu-item` as well as the two forwarding attributes: an item that
      //: owns its own listener (Rename, New board, the two map rows) used to
      //: leave the menu standing open behind the dialog it had just opened,
      //: because only the forwarding items closed it.
      //: `[data-wb-closes]` is the six action rows drawn as a label and a button
      //: (Export, Clear, Add to a note, Map to document, Copy app link, Delete):
      //: they left the menu open over the dialog or picker they opened, which at
      //: 390 wide covered its middle (tests/test_wb_menu_rows_close.py).
      const item = e.target.closest(".wb-board-menu [data-wb-click], .wb-board-menu [data-wb-fn], .wb-board-menu [data-wb-cmd], .wb-board-menu .wb-menu-item, .wb-board-menu [data-wb-closes]");
      if (!item) return;
      e.stopPropagation();
      closeAllWbMenus();
      //: A row named after a command in `WB_COMMANDS` (whiteboard-commands.js).
      if (item.dataset.wbCmd) { wbRunCommand(item.dataset.wbCmd); return; }
      if (item.dataset.wbFn === "select-all") { wbSelectAllItems(); return; }
      if (item.dataset.wbFn === "present") { wbStartPresenting(); return; }
      if (item.dataset.wbClick) document.getElementById(item.dataset.wbClick)?.click();
    });
    //: **A board can change its mind.** Reported: "when I press the boards
    //: dropdown to change boards, I cant tell which one is a whiteboard and
    //: which one is a mindmap". The picker has grouped the two kinds under
    //: `<optgroup>` since MINDMAP_PLAN §5 item 12, and it can only group boards
    //: that say which kind they are: `_board_settings` defaults every board that
    //: predates maps to "board", which is the right default and the wrong answer
    //: for a board somebody has been using as a map ever since. The route has
    //: taken a `type` from the beginning (`rename_board`, "also where a board
    //: becomes a map and back"); nothing in the app ever sent one.
    //:
    //: The default scratch board has no note behind it and so no settings to
    //: store, which is why the control says so rather than failing quietly.
    document.getElementById("wb-board-kind")?.addEventListener("click", async () => {
      closeAllWbMenus();
      const boardId = window.currentBoardId ?? null;
      if (!boardId) {
        toast("The default board cannot change kind. Make a new board to start a mind map.", "info");
        return;
      }
      const becomingMap = !wbIsMap();
      try {
        await apiJson(`/whiteboard/boards/${boardId}`, {
          method: "PUT",
          body: JSON.stringify({ type: becomingMap ? "map" : "board" }),
        });
      } catch (error) {
        toast(error.message || "That board could not be changed.", true);
        return;
      }
      //: Reopened rather than patched in place: the two kinds draw different
      //: chrome, different tools and a different renderer, and a half-switched
      //: board is the shape of bug this file has had before.
      await openWhiteboardBoard(boardId);
      wbBoardPutStep(becomingMap ? "Made the board a mind map" : "Made the map a whiteboard", boardId, { type: becomingMap ? "board" : "map" }, { type: becomingMap ? "map" : "board" }, true);
      toast(becomingMap ? "Now a mind map." : "Now a whiteboard.");
    });

    document.getElementById("wb-insert-menu")?.addEventListener("click", (e) => {
      const choice = e.target.closest("[data-wb-insert]");
      if (!choice) return;
      closeAllWbMenus();
      const what = choice.dataset.wbInsert;
      //: Enter on the item (detail 0) is not a pointer that can click the board
      //: next, so a sticky note, text box or frame is placed where the view is
      //: centred (audit U3), not left as an armed tool on a dropped focus.
      const byKey = e.detail === 0 && { sticky: wbCreateSticky, text: wbCreateTextBox, frame: wbCreateFrame }[what];
      if (byKey) byKey(...wbViewCentre());
      else if (what === "image") document.getElementById("wb-add-image")?.click();
      else if (what === "note") document.getElementById("wb-add-note")?.click();
      else document.querySelector(`#wb-tool-group [data-tool="${what}"]`)?.click();
    });

    // **Panels, managed in one place.** Asked for: "there needs to be a window
    // option to manage what windows are showing and not". Four switches in
    // the Board menu: Context bar (a preference: off means the bar never
    // opens, even with a selection; the class is read by CSS), and Overview,
    // Library and Search, which are the same toggles the top bar carries,
    // shown as on/off so their state can be read without hunting for them.
    const propsPref = document.getElementById("wb-panel-props");
    const viewHost = document.getElementById("library-view-whiteboard");
    //: The class and the switch now govern the context bar, which is what
    //: replaced the drawer this preference was written for. The storage key is
    //: unchanged on purpose: a person who turned the drawer off once should not
    //: have the new surface turn itself back on under them.
    const applyPropsPref = (on) => {
      viewHost?.classList.toggle("wb-hide-context", !on);
      if (propsPref) propsPref.checked = on;
    };
    applyPropsPref(prefs.get("wb-panel-props", null) !== "off");
    propsPref?.addEventListener("change", () => {
      prefs.set("wb-panel-props", propsPref.checked ? "on" : "off");
      applyPropsPref(propsPref.checked);
    });
    const panelSwitches = [
      ["wb-panel-overview", "wb-navigator", () => wbToggleNavigator()],
      ["wb-panel-library", "wb-sidebar-panel", () => document.getElementById("wb-add-note")?.click()],
      //: The View menu's switch is the only control for Find now (the top bar's duplicate icon went, L265).
      ["wb-panel-search", "wb-search-bar", () => (document.getElementById("wb-search-bar")?.classList.contains("hidden") ? wbOpenBoardSearch() : wbCloseBoardSearch())],
    ];
    function syncPanelSwitches() {
      for (const [switchId, panelId] of panelSwitches) {
        const sw = document.getElementById(switchId);
        const panel = document.getElementById(panelId);
        if (sw && panel) sw.checked = !panel.classList.contains("hidden");
      }
    }
    for (const [switchId, , toggle] of panelSwitches) {
      document.getElementById(switchId)?.addEventListener("change", () => {
        toggle();
        syncPanelSwitches();
      });
    }

    const toolsPanel = document.getElementById("wb-tools-panel");
    const dockToggle = document.getElementById("wb-dock-toggle");
    if (toolsPanel && dockToggle) {
      const applyDock = (dock) => {
        toolsPanel.dataset.dock = dock;
        //: On the view too, so the board's sidebar can stand beside a side dock
        //: rather than over it (INBOX 596; 07-whiteboard-misc.css).
        viewHost?.setAttribute("data-wb-dock", dock);
        //: A menu row, so its words are the action (INBOX 793).
        const words = dock === "bottom" ? "Dock the tools at the side" : "Dock the tools at the bottom";
        dockToggle.title = words;
        dockToggle.setAttribute("aria-label", words);
        setLabel(dockToggle, `ph:sidebar-simple ${words}`);
      };
      applyDock(prefs.get("wb-toolbar-dock", null) || "bottom");
      dockToggle.addEventListener("click", () => {
        const next = toolsPanel.dataset.dock === "bottom" ? "side" : "bottom";
        prefs.set("wb-toolbar-dock", next);
        applyDock(next);
      });
    }

    //: **Toasts stand above the bottom dock** (dogfood 2026-10-25 item 22: a
    //: "Created" toast sat over the dock's right end for six seconds at 1280
    //: and over most of it at 700). The dock's height changes with the window
    //: (46px on one row, 101 on two), so the toast box's `bottom` is set from
    //: where the dock's top really is. Cleared whenever the dock is hidden
    //: (another tab, the board closed), docked at the side, or the window is a
    //: phone's (under 600, whose toasts have their own place), which leaves
    //: the stylesheet's placement as it was.
    if (toolsPanel) {
      const liftToasts = () => {
        const toastBox = document.getElementById("toast-box");
        if (!toastBox) return;
        const box = toolsPanel.getBoundingClientRect();
        const low = box.width > 0 && toolsPanel.dataset.dock !== "side" && window.innerWidth >= 600
          && box.top > window.innerHeight / 2;
        toastBox.style.bottom = low ? `calc(${Math.round(window.innerHeight - box.top)}px + var(--space-2))` : "";
      };
      toolsPanel.addEventListener("wb-panel-resize", liftToasts);
      window.addEventListener("resize", liftToasts);
    }

    // **The ink swatch on the rail is the drawing colour** (WHITEBOARD_PLAN.md
    // decision 1). It was a row in the properties drawer as well until Phase 2
    // removed that drawer; one control for one setting, on the surface that
    // holds the tool it belongs to.
    //
    // `input` as well as `change`: a native colour picker fires `input`
    // continuously while a colour is being dragged and `change` once at the end,
    // and a swatch that only catches up when the dialog closes is exactly the
    // "does this control do anything" read this group exists to fix.
    const railInk = document.getElementById("wb-rail-ink");
    if (railInk) {
      railInk.value = window.currentStrokeColor;
      for (const type of ["input", "change"]) {
        railInk.addEventListener(type, (e) => {
          window.currentStrokeColor = e.target.value;
          prefs.set("wb-stroke-color", e.target.value);
          updateWbCursor();
        });
      }
    }

    if (undoBtn) {
      undoBtn.disabled = true;
      undoBtn.addEventListener("click", wbUndo);
    }
    const redoBtn = document.getElementById("wb-redo");
    if (redoBtn) {
      redoBtn.disabled = true;
      redoBtn.addEventListener("click", wbRedo);
    }

    // Keyboard shortcuts, asked for as part of the wider usability pass: a
    // toolbar of eight icon buttons is not obviously faster than the tool you
    // already have your hand on, and every serious drawing app (Figma,
    // Excalidraw, tldraw) uses this exact letter set for exactly that reason, 
    // muscle memory transfers in, rather than having to be learned from
    // scratch. Guarded to the whiteboard sub-tab and away from anything with
    // its own idea of what typing means (an input, a textarea, a
    // contenteditable note), the same guard the app's other global shortcuts
    // already use.
    const WB_TOOL_KEYS = {
      // V selects and H is the hand, the way every whiteboard people already
      // know binds them. V used to be Pan (and S Select); S stays as an alias
      // so the old habit still works.
      v: "select",
      h: "pan",
      s: "select",
      k: "lasso",
      p: "draw",
      m: "highlighter",
      l: "line",
      a: "arrow",
      r: "rect",
      o: "circle",
      g: "triangle",
      d: "diamond",
      t: "text",
      e: "eraser",
      b: "bucket",
      x: "delete",
      // WHITEBOARD_PLAN.md decision 8 names N for the sticky and C for the
      // connector; both were tools with no key at all, which the Phase 1 sweep
      // measured ("18 tools, 3 without a key"). The board has *two* connectors
      // and the decision names one letter, so the second takes the shifted form
      // of the same letter (recorded in INBOX with its recommendation rather
      // than decided here; see `WB_TOOL_SHIFT_KEYS` below).
      n: "sticky",
      c: "link-straight",
      // tldraw's key for the same tool (decision 14). A selected map topic
      // keeps F for its focus: that handler runs first and returns.
      f: "frame",
    };
    // Shift + the same letter, for the second tool of a pair. One table rather
    // than an `if` beside the dispatch, so a third pair cannot be added in a
    // different shape.
    const WB_TOOL_SHIFT_KEYS = {
      c: "link-curved",
    };
    // Keys that press a button rather than pick a tool: uploading an image is an
    // action with a file dialog behind it, not a mode you hold. Declared on the
    // markup (`data-wb-key`) so the sweep reads the same source the tooltip does.
    const WB_ACTION_KEYS = {
      i: "wb-add-image",
    };
    // Held space = pan, from whatever tool you are holding. The flag is read by
    // `wbZoomFilter`; nothing about the active tool changes, so releasing space
    // puts you back exactly where you were rather than in a different mode.
    //
    // The cursor changes with it, because a modifier that alters what a drag
    // does has to say so before the drag, a grab cursor is how every canvas
    // app signals this, and without it "space does something" is a secret.
    const wbCanvasEl = () => wbInstances.container();
    function wbSetSpaceHeld(held) {
      if (wbSpaceHeld === held) return;
      wbSpaceHeld = held;
      const el = wbCanvasEl();
      if (el) el.classList.toggle("wb-space-pan", held);
    }
    document.addEventListener("keyup", (e) => {
      if (e.code === "Space") wbSetSpaceHeld(false);
    });
    // A board left while space is down would otherwise stay stuck in pan.
    window.addEventListener("blur", () => wbSetSpaceHeld(false));

    // **Clicking the board gives the board the keyboard.** Single-key
    // shortcuts are guarded (correctly) against firing while a field has
    // focus, but a canvas is not focusable by default, so clicking it left
    // focus wherever it happened to be, on whatever control was touched last,
    // or on the lock screen's own password field for a freshly unlocked app.
    // A `tabindex` (index.html) plus this makes the board take focus the way
    // every other surface does, so the tool keys work after clicking the thing
    // they act on. It was out of the tab order while Tab on it did nothing; it
    // is a stop since INBOX 445, because Tab on it now walks the items
    // (`wbWalkItems`), which is the only way to a shape without a pointer.
    wbInstances.on("pointerdown", (e) => {
      // Any editable body, not the two class names that were editable when
      // this was written: pulling focus to the canvas out from under a map
      // node's editor is the other half of "I cant highlight text in mindmap
      // text boxes", the caret went to the container mid-gesture.
      if (e.target.closest(".whiteboard-floating-panel, [contenteditable=true]")) return;
      wbInstances.container()?.focus({ preventScroll: true });
      // A press on the map is the strongest way to say you are working in it.
      wbMapKeysArmed = true;
    });
    //: **Focus landing on any control outside the canvas disarms Tab.** The
    //: keyboard user walking the toolbar is not working in the map, and the Tab
    //: that carries focus off the last control lands on the page body, where an
    //: armed flag from an earlier click would add a topic (measured: sixty Tabs
    //: from the top bar added fifteen). The canvas, its topics and the editor
    //: inside a topic are not "outside", so a topic being typed into keeps it.
    document.addEventListener("focusin", (e) => {
      if (!wbInstances.container()?.contains(e.target)) wbMapKeysArmed = false;
    });

    //: On `window`, capturing, so it runs before the app zoom's own capture
    //: listener on `document` (settings-panes.js) and can stop it.
    window.addEventListener("keydown", wbZoomKey, true);
    document.addEventListener("keydown", (e) => {
      if (typeof e.key !== "string") return; // a keydown with no key (see the ring's handler above)
      const view = document.getElementById("library-view-whiteboard");
      //: A key typed inside an embed is for that board (L-whiteboard-54), and only
      //: when it may be edited; any other is the page board's, while it shows.
      const embed = wbInstances.embedFor(e.target);
      if (embed ? !embed.editable : (!view || view.classList.contains("hidden"))) return;
      wbInstances.activate(embed || wbInstances.page);
      //: **Escape takes back a gesture in flight** before it does anything
      //: else (see `wbCancelGesture`): with a drag, a resize, a turn or a line
      //: half drawn, that is the only thing the key can mean, and the
      //: selection it would otherwise clear is the one being dragged.
      if (e.key === "Escape" && wbCancelGesture()) {
        e.preventDefault();
        e.stopImmediatePropagation();
        return;
      }
      const tag = (document.activeElement?.tagName || "").toLowerCase();
      // Ctrl+F is deliberately *not* bound here. The app already owns it for
      // "Find on this page", and binding it a second time opened both bars at
      // once: `preventDefault` does not stop another listener, only the
      // browser. `openGlobalFind` in wiring.js now hands off to the board search
      // when a board is open, which is one owner for one shortcut and the same
      // shape as the handoff it already does for the lightbox's find.
      // `offsetParent` is the visibility half, and it is load-bearing: the lock
      // overlay's own password field keeps DOM focus after the overlay is
      // hidden, so on a freshly unlocked app `activeElement` is an `<input>`
      // that nobody can see or type into, and this guard then swallowed every
      // single-key shortcut on the board (V/H/P, `n`, `/`) for the whole
      // session. Measured, not guessed: `document.activeElement` read
      // `INPUT#lock-password` on a board that had been open for minutes. A
      // field you cannot see is not a field you are typing in.
      const active = document.activeElement;
      const typing = active
        && (tag === "input" || tag === "textarea" || active.isContentEditable)
        && active.offsetParent !== null;
      if (typing) return;
      //: Ctrl+H is find and replace, as in draw.io and every editor; the
      //: browser's history window has no meaning inside the app.
      if ((e.ctrlKey || e.metaKey) && !e.altKey && !e.shiftKey && e.key.toLowerCase() === "h" && !wbIsMap()) {
        e.preventDefault();
        wbOpenBoardSearch({ replace: true });
        return;
      }
      if (wbMapCatchTypeahead(e)) return;
      // **Shift+N for the overview, because bare N is the sticky note**
      // (WHITEBOARD_PLAN.md decision 8). This took the bare letter first,
      // "matching the single-letter tool keys this board already uses", and the
      // plan then gave that letter to a tool, which is the collision the Phase 1
      // sweep found: N selected nothing and opened the overview instead. Same
      // letter shifted rather than a third letter invented, the same shape the
      // second connector takes on Shift+C. Modifier chords are still left alone
      // so Ctrl+N opens a browser window.
      // `e.shiftKey` plus the lower-cased letter, not `e.key === "N"`: a real
      // keyboard reports the shifted letter as "N", but not every source does
      // (Playwright's own `Shift+n` sends shiftKey with key "n"), and the rest
      // of this handler already reads letters the lower-cased way.
      if (e.shiftKey && e.key.toLowerCase() === "n" && !e.ctrlKey && !e.metaKey && !e.altKey) {
        e.preventDefault();
        wbToggleNavigator();
        return;
      }
      //: "/" goes to the Library search (draw.io's sidebar search); Ctrl+F is the board's find.
      if (e.key === "/" && !e.ctrlKey && !e.metaKey && !e.altKey) {
        e.preventDefault();
        wbOpenSidebar("library");
        return;
      }
      if (e.code === "Space") {
        //: **Space stays the pan, except on a fold control** (MINDMAP_PLAN.md
        //: §12.0). §12.1 item 7 asks for "reopens on click and on Space", and
        //: held space is this canvas's pan gesture from every tool
        //: (`wbZoomFilter`): a map node is selected nearly all the time once
        //: someone is editing, so binding Space to collapse would take the pan
        //: away exactly when it is most used, and would make a map pan
        //: differently from a board. So Space folds a branch where the plan
        //: asked it to, on the fold control itself: with the keyboard focus on
        //: a node's chevron or the dock's Collapse button, this handler stands
        //: aside and the browser's own button activation runs (the dock's own
        //: Collapse button left with §12.5; the ring's Fold slot took its place).
        //: `C` is the key
        //: for the same thing with the canvas focused (below).
        if (document.activeElement?.closest(".wb-map-collapse, #wb-radial-collapse")) return;
        // preventDefault so the page does not scroll under the board, and so a
        // focused toolbar button is not "clicked" by the space that is panning.
        e.preventDefault();
        wbSetSpaceHeld(true);
        return;
      }
      // Escape cascades one level at a time, the way every editor does it:
      // with something selected it clears the selection and leaves the tool
      // alone; with nothing selected it returns to Select. One key that did
      // both at once meant deselecting a shape mid-pen-session also threw
      // away the pen.
      if (e.key === "Escape") {
        // A selection drag in flight (or a rectangle a previous one left
        // behind) goes first, Escape is where people reach when something is
        // stuck on the canvas, and it did nothing about this before.
        //:
        //: **And when one was in flight, that is all it does** (the conventions
        //: pass, `wbmarqueeescape.js`). It went on to clear the selection too,
        //: so a Shift-drag meant to add to a selection, taken back with Escape,
        //: lost the selection it was adding to: one key, two things undone.
        //: The drag's own release then finds nothing to finish, so the rest of
        //: the pointer's travel selects nothing either.
        if (wbClearSelectionOverlays()) return;
        if (wbSelectedItem || wbMultiSelection.size > 0) clearWbSelection();
        else selectWbTool("select");
        return;
      }
      // --- a map's own keys (MINDMAP_PLAN.md §5 item 5) ----------------------
      //
      // Obsidian Canvas Mindmap's set, which is the de-facto standard, and the
      // reason this block sits *above* the card gestures and the arrow-key
      // nudge below rather than beside them: on a map, Delete means "this
      // subtree, undoably" and the arrows mean "walk the tree", both of which
      // the generic handlers further down would otherwise have already claimed.
      // Every branch returns, so nothing here falls through to them.
      //: Tab on a focused board canvas walks its items (`wbWalkItems`); off the
      //: end it is left to the browser, so focus moves on.
      if (
        e.key === "Tab" && !e.ctrlKey && !e.metaKey && !e.altKey && !wbIsMap()
        && document.activeElement?.id === "whiteboard-container"
      ) {
        if (wbWalkItems(e.shiftKey ? -1 : 1)) e.preventDefault();
        return;
      }
      const mapNode = wbSelectedMapNode();
      if (mapNode) {
        //: Any real key (not a bare modifier) means the person is working in
        //: the map; arrows, Enter, F2 and the rest below all arm Tab.
        if (e.key !== "Tab" && !["Shift", "Control", "Alt", "Meta"].includes(e.key)) wbMapKeysArmed = true;
        if (e.key === "Tab") {
          //: **Not armed, or focus is on some other control: Tab is Tab.** With
          //: a topic selected it used to add a child from anywhere, so a
          //: keyboard user could not leave the map without Escape first, and the
          //: Tab that carried focus in added a topic nobody asked for
          //: (INBOX 445, second audit). Focus on the canvas (or on nothing)
          //: after a click or a map key still adds; Escape then Tab leaves.
          const at = document.activeElement;
          const onMap = !at || at === document.body || Boolean(wbInstances.container()?.contains(at));
          if (!wbMapKeysArmed || !onMap) return;
          e.preventDefault();
          // Shift+Tab outdents. Through `/move`, which is the only endpoint
          // that runs the cycle check, see `wbMapOutdent`.
          if (e.shiftKey) wbMapOutdent(mapNode.id);
          else wbMapAddChild(mapNode.id);
          return;
        }
        if (e.key === "Enter" && !e.ctrlKey && !e.metaKey && !e.altKey) {
          e.preventDefault();
          wbMapAddSibling(mapNode.id, { above: e.shiftKey });
          return;
        }
        if (e.key === "Enter" && (e.ctrlKey || e.metaKey) && !e.shiftKey && !e.altKey) {
          e.preventDefault();
          wbMapInsertParent(mapNode.id);
          return;
        }
        //: Ctrl+Shift+arrows move the topic among its siblings (§12.0's keys;
        //: missing until INBOX 445). Up and Left are earlier, Down and Right
        //: later, so the keys read the same in a tree laid out across.
        if (
          (e.ctrlKey || e.metaKey) && e.shiftKey && !e.altKey
          && ["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"].includes(e.key)
        ) {
          e.preventDefault();
          wbMapMoveAmongSiblings(mapNode.id, e.key === "ArrowUp" || e.key === "ArrowLeft" ? -1 : 1);
          return;
        }
        if (e.key === "F2") {
          e.preventDefault();
          wbMapEditNode(mapNode.id);
          return;
        }
        //: C folds and unfolds the selected branch, the canvas-focused half of
        //: the Space decision above. A letter rather than a modifier chord
        //: because it sits beside the map's other bare keys (Tab, Enter, F,
        //: the arrows). `c` became the connector's key on a *board*
        //: (WHITEBOARD_PLAN decision 8, `WB_TOOL_KEYS`), and Connect is one of
        //: the three sections a map keeps. The two never collide because this
        //: branch runs only with a map node selected and returns: with a topic
        //: in hand C folds it, with nothing selected C reaches for the
        //: cross-link, which is the only thing C could usefully mean there.
        if ((e.key === "m" || e.key === "M") && !e.ctrlKey && !e.metaKey && !e.altKey && !e.shiftKey) {
          e.preventDefault();
          wbMapMoveUnder(mapNode.id);
          return;
        }
        if ((e.key === "c" || e.key === "C") && !e.ctrlKey && !e.metaKey && !e.altKey) {
          e.preventDefault();
          //: **Shift+C connects instead** (§12.5, so that every slot in the ring
          //: is also a key). On a board Shift+C is the curved connector, so this
          //: is the same letter doing the same kind of thing with a topic in
          //: hand: pick the connector and say what to drag.
          if (e.shiftKey) {
            selectWbTool("link-straight");
            toast("Drag from this topic to the one it should join.");
            return;
          }
          wbMapToggleCollapse(mapNode.id);
          return;
        }
        //: The ring's "More" as a key: the platform's own menu key, and Shift+F10
        //: for the keyboards without one. Both are what a browser fires for a
        //: context menu, so this is the same gesture the pointer makes, from the
        //: keyboard, and it is why nothing in the node's menu is pointer-only.
        if (e.key === "ContextMenu" || (e.key === "F10" && e.shiftKey)) {
          e.preventDefault();
          const el = wbInstances.query(`.wb-object[data-id="${mapNode.id}"]`);
          const box = el?.getBoundingClientRect();
          wbCloseMapRadial();
          wbOpenMapNodeMenu(mapNode, box ? box.left + box.width / 2 : 0, box ? box.bottom + 4 : 0);
          return;
        }
        //: F focuses here, and F again lets the whole map back (§5 item 18).
        //: One key for both directions because focus is a mode you look through
        //: rather than a thing you set: the way out has to be as cheap as the
        //: way in, or people stop using it.
        if ((e.key === "f" || e.key === "F") && !e.ctrlKey && !e.metaKey && !e.altKey) {
          e.preventDefault();
          if (wbMapFocusState && wbMapFocusState.id === mapNode.id) wbMapClearFocus();
          else wbMapSetFocus(mapNode.id);
          return;
        }
        if ((e.key === "Delete" || e.key === "Backspace") && !e.ctrlKey && !e.metaKey) {
          e.preventDefault();
          wbMapDeleteSubtree(mapNode.id);
          return;
        }
        // The arrows walk the tree, but only unmodified. Shift/Ctrl arrows stay
        // with the nudge below, so a node that genuinely needs moving by hand
        // still can be.
        if (
          ["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"].includes(e.key)
          && !e.shiftKey && !e.ctrlKey && !e.metaKey && !e.altKey
        ) {
          e.preventDefault();
          wbMapNavigate(mapNode.id, e.key);
          return;
        }
      }

      // Delete/Backspace with a selection, the other half of Select as a
      // real tool: previously the only way to delete anything was switching
      // to the Delete tool and clicking it.
      // wbMultiSelection alongside wbSelectedItem: deleteWbSelection() already
      // handles a marquee multi-select correctly, but this guard only ever
      // checked the single-item variable - the two are mutually exclusive by
      // construction, so a multi-selection left this false and Delete/
      // Backspace silently did nothing. Reported directly.
      if ((e.key === "Delete" || e.key === "Backspace") && (wbSelectedItem || wbMultiSelection.size > 0)) {
        e.preventDefault();
        deleteWbSelection();
        return;
      }
      //: **Undo and redo are not bound here any more.** Reported: "ctrl z undo
      //: and redo cont trigger in the whiteboard/mind map". Two listeners on
      //: `document` both matched the chord: the app's own global stack
      //: (`shortcuts.undo`) and this one. `preventDefault` does not stop another
      //: listener, so both ran, and which of the two stacks answered depended on
      //: which had something in it: press it with a deleted note in the app's
      //: stack and the board's move was left alone while a note came back
      //: somewhere else entirely. The app's handler hands the chord to
      //: `wbUndo`/`wbRedo` when a board is open, which is one owner for one
      //: shortcut, the same handoff Ctrl+F already uses. They stay on `window`
      //: below for it to call.
      //: Not `preventDefault`: the browser's copy, cut and paste events have to
      //: follow, so the board's items reach the system clipboard (`wbOnBoardCopy`)
      //: and a paste can bring text or a picture in from another app (FEAT-09).
      if ((e.ctrlKey || e.metaKey) && !e.shiftKey && e.key.toLowerCase() === "c") {
        wbCopySelection();
        return;
      }
      if ((e.ctrlKey || e.metaKey) && !e.shiftKey && e.key.toLowerCase() === "x") {
        wbCutSelection();
        return;
      }
      //: Ctrl+Alt+Shift+V: the board's copy without its comment threads (the
      //: owner: an option, never the default). Before Ctrl+Shift+V, which it contains.
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.altKey && e.key.toLowerCase() === "v" && wbClipboard) {
        e.preventDefault();
        wbPasteClipboard({ noComments: true });
        return;
      }
      //: Ctrl+Shift+V: the board's copy again, exactly where it was. With
      //: nothing copied here the browser's own plain-text paste goes on.
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key.toLowerCase() === "v" && wbClipboard) {
        e.preventDefault();
        wbPasteClipboard({ inPlace: true });
        return;
      }
      if ((e.ctrlKey || e.metaKey) && !e.shiftKey && e.key.toLowerCase() === "v") {
        //: If no paste event arrives (a shell that keeps the clipboard to
        //: itself), the board's own clipboard is pasted as before.
        wbBoardState.pasteArrived = false;
        setTimeout(() => {
          if (!wbBoardState.pasteArrived && wbClipboard) wbPasteClipboard();
        }, 120);
        return;
      }
      //: Ctrl/Cmd with +, -, 0 and 1 are `wbZoomKey`'s, taken before this.
      if (e.shiftKey && !e.ctrlKey && !e.metaKey && !e.altKey && e.code === "Digit1") {
        e.preventDefault();
        wbZoomToFit();
        return;
      }
      if (e.shiftKey && !e.ctrlKey && !e.metaKey && !e.altKey && e.code === "Digit2") {
        e.preventDefault();
        wbZoomToSelection();
        return;
      }
      //: Alt+1 to 9 on a map: show that many levels (`wbMapFoldToLevel`).
      if (e.altKey && !e.ctrlKey && !e.metaKey && !e.shiftKey && /^Digit[1-9]$/.test(e.code) && wbIsMap()) {
        e.preventDefault();
        wbMapFoldToLevel(Number(e.code.slice(5)));
        return;
      }
      //: Alt+= and Alt+- on a map: one more or one less level (INBOX 1774). On
      //: the canvas only: in a writing box Alt+= stays the equation editor
      //: (this handler is the canvas's, after the editors have kept their keys),
      //: and never while presenting, when no key edits the map (decision 21).
      if (e.altKey && !e.ctrlKey && !e.metaKey && !e.shiftKey && (e.code === "Equal" || e.code === "Minus") && wbIsMap() && !wbPresent) {
        e.preventDefault();
        wbMapFoldToLevel({ by: e.code === "Equal" ? 1 : -1 });
        return;
      }
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key.toLowerCase() === "g") {
        e.preventDefault();
        wbUngroupSelection();
        return;
      }
      //: Lock what is selected; with nothing selected, unlock everything
      //: (decision 15). Not on a map, whose topics have their own keys.
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && !e.altKey && e.key.toLowerCase() === "l" && !wbIsMap()) {
        e.preventDefault();
        if (wbMultiSelection.size || wbSelectedItem) wbLockSelection();
        else wbUnlockAll();
        return;
      }
      if ((e.ctrlKey || e.metaKey) && !e.shiftKey && e.key.toLowerCase() === "g") {
        e.preventDefault();
        wbGroupSelection();
        return;
      }
      //: The Format panel (decision 19); the app's own Ctrl+Shift+P steps
      //: aside on a board (`wbOwnsChord`).
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && !e.altKey && e.key.toLowerCase() === "p") {
        e.preventDefault();
        wbRunCommand("format-panel");
        return;
      }
      //: Clone and connect: Alt+Shift+Arrow copies the shape that way and joins.
      if (e.altKey && e.shiftKey && !e.ctrlKey && !e.metaKey && e.key.startsWith("Arrow") && wbCloneSource()) {
        e.preventDefault();
        wbCloneConnect({ ArrowRight: "right", ArrowLeft: "left", ArrowDown: "down", ArrowUp: "up" }[e.key]);
        return;
      }
      //: Save what is selected (or the topic's branch) to the library.
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && !e.altKey && e.key.toLowerCase() === "s") {
        e.preventDefault();
        wbRunCommand(wbIsMap() ? "save-branch" : "save-selection");
        return;
      }
      // Mind-mapping's keyboard-driven branch entry (item 25's second piece,
      // asked for directly): Tab adds a linked child of the selected card,
      // Enter adds a sibling. The actual ergonomic difference between "a
      // whiteboard you can draw a mind map on" and "a mind-mapping tool", 
      // dragging cards one at a time to fake this defeats the point of
      // having it. Guarded to a single selected *card*, a sketch or object
      // has no "branch" of its own to add one to.
      if (e.key === "Tab" && wbSelectedItem?.kind === "node") {
        e.preventDefault();
        wbMindMapAddChild(wbSelectedItem.id);
        return;
      }
      //: F2 starts editing like Enter (draw.io's second key); a map topic's Enter and F2 differ below.
      //: Not on a focused button: Enter there is the button's own (the Format panel's Add point took the label edit instead).
      const editKey = (e.key === "Enter" || e.key === "F2") && !e.shiftKey && !e.ctrlKey && !e.metaKey && !e.altKey
        && !(e.key === "Enter" && document.activeElement?.closest("button, [role='button'], a[href], summary"));
      if (editKey && !wbIsMap() && wbKeyboardEnter()) {
        e.preventDefault();
        return;
      }
      //: Enter on one selected shape types into it (decision 12; tldraw's key).
      if (editKey && wbSelectedItem?.kind === "sketch" && wbMultiSelection.size <= 1) {
        const sketch = (wbState.sketches || []).find((s) => s.id === wbSelectedItem.id);
        if (sketch && wbShapeLabelKind(wbSketchParsedData(sketch))) {
          e.preventDefault();
          wbEditShapeLabel(sketch);
          return;
        }
        //: And on one selected connector, its label (decision 13).
        let linkParsed = null;
        try {
          linkParsed = sketch ? JSON.parse(sketch.data) : null;
        } catch {
          linkParsed = null;
        }
        if (sketch && wbLinkTakesLabel(sketch, linkParsed)) {
          e.preventDefault();
          wbEditLinkLabel(sketch);
          return;
        }
      }
      if (e.key === "Enter" && wbSelectedItem?.kind === "node") {
        e.preventDefault();
        wbMindMapAddSibling(wbSelectedItem.id);
        return;
      }
      //: **Ctrl+arrows resize** (draw.io's keys): right and down grow, left and
      //: up shrink, from the top-left corner. Ctrl alone is 1 px; with Shift a
      //: grid cell with snap on, else 10. A burst of presses is one Undo step.
      if ((e.ctrlKey || e.metaKey) && !e.altKey && !wbIsMap()
        && ["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"].includes(e.key)
        && (wbSelectedItem || wbMultiSelection.size > 0)) {
        e.preventDefault();
        const step = e.shiftKey ? (wbSnapOn() ? WB_GRID_SPACING : 10) : 1;
        const dw = e.key === "ArrowRight" ? step : e.key === "ArrowLeft" ? -step : 0;
        const dh = e.key === "ArrowDown" ? step : e.key === "ArrowUp" ? -step : 0;
        wbResizeSelectionBy(dw, dh);
        return;
      }
      // Arrow-key nudge, asked for directly. Grid step while snap is on (the
      // nudge should land on the same grid a drag would), else 1px/10px, 
      // Shift for the bigger jump, the same convention a slider's own arrow
      // keys use elsewhere in this app.
      if (
        ["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"].includes(e.key) &&
        (wbSelectedItem || wbMultiSelection.size > 0)
      ) {
        e.preventDefault();
        //: Shift is the big step whether or not snap is on (INBOX 175: "hold
        //: shift and use arrows ... move them further distance increments
        //: like in adobe software"): one grid cell or 1px plain, five cells or
        //: 10px with Shift, which is Illustrator's and Figma's convention.
        const base = wbSnapOn() ? WB_GRID_SPACING : 1;
        const step = e.shiftKey ? base * (wbSnapOn() ? 5 : 10) : base;
        const dx = e.key === "ArrowLeft" ? -step : e.key === "ArrowRight" ? step : 0;
        const dy = e.key === "ArrowUp" ? -step : e.key === "ArrowDown" ? step : 0;
        wbNudgeSelection(dx, dy);
        return;
      }
      // Copy/paste style: Ctrl+Alt+C / Ctrl+Alt+V, the chord Excalidraw uses,
      // and checked before the modifier bail-out below since it *is* a chord.
      if ((e.ctrlKey || e.metaKey) && e.altKey && !e.shiftKey) {
        const key = e.key.toLowerCase();
        if (key === "c") { e.preventDefault(); wbCopySelectedStyle(); return; }
        if (key === "v") { e.preventDefault(); wbPasteCopiedStyle(); return; }
        if (key === "d") { e.preventDefault(); wbFmtState.board?.setDefault(); return; }
      }
      // Ctrl+D duplicates the selection in place (PLAN.md W6): the chord
      // Figma, Miro and tldraw share. Implemented as copy+paste through the
      // clipboard the app already has, with the clipboard put back afterwards
      // so a duplicate never overwrites something you meant to paste later.
      if ((e.ctrlKey || e.metaKey) && !e.altKey && !e.shiftKey && e.key.toLowerCase() === "a") {
        e.preventDefault();
        wbSelectAllItems();
        return;
      }
      if ((e.ctrlKey || e.metaKey) && !e.altKey && !e.shiftKey && e.key.toLowerCase() === "d") {
        e.preventDefault();
        wbDuplicateSelection();
        return;
      }
      //: Ctrl+E: Edit style as text (draw.io's Edit Style), for the one selected item.
      if ((e.ctrlKey || e.metaKey) && !e.altKey && !e.shiftKey && e.key.toLowerCase() === "e" && wbSelectedItem) {
        e.preventDefault();
        wbFmtState.raw?.open();
        return;
      }
      //: `]` and `[` are one step; Ctrl+] and Ctrl+[ go to the front and the
      //: back (FEAT-07: draw.io's, Figma's and PowerPoint's split). `e.code`
      //: as well, because Ctrl changes what some layouts report as the key.
      const bracket = e.key === "]" || e.code === "BracketRight" ? 1 : e.key === "[" || e.code === "BracketLeft" ? -1 : 0;
      if (bracket && !e.altKey && !e.shiftKey && !wbIsMap() && (wbSelectedItem || wbMultiSelection.size)) {
        e.preventDefault();
        if (e.ctrlKey || e.metaKey) wbSendSelectionZOrder(bracket > 0);
        else wbStepSelectionZOrder(bracket);
        return;
      }
      if (e.ctrlKey || e.metaKey || e.altKey) return; // leave browser/OS shortcuts alone
      if (
        wbAddGate.cardRetypeId != null && e.key.length === 1 && e.key !== " " && !wbIsMap()
        && wbSelectedItem?.kind === "node" && wbSelectedItem.id === wbAddGate.cardRetypeId && !wbMultiSelection.size
      ) {
        e.preventDefault();
        wbEditNodeText(wbAddGate.cardRetypeId, e.key);
        return;
      }
      const letter = e.key.toLowerCase();
      //: Shift+H and Shift+V flip what is selected (Figma's keys) when it can be
      //: flipped; with nothing flippable they pick the hand and Select as before.
      if (e.shiftKey && (letter === "h" || letter === "v") && wbCommandApplies(WB_COMMAND_BY_ID.get(`flip-${letter}`))) {
        e.preventDefault();
        wbRunCommand(`flip-${letter}`);
        return;
      }
      // Shift first: `e.key` for Shift+C is "C", which lower-cases onto the
      // unshifted tool, so reading the shift table second would make the two
      // connectors unreachable from each other.
      // A shifted letter with no pair still picks the unshifted tool, which is
      // what it did before this table existed: Shift+P has always been the pen.
      const mapped = (e.shiftKey && WB_TOOL_SHIFT_KEYS[letter]) || WB_TOOL_KEYS[letter];
      //: **A map's keys never pick a tool its rail does not show** (INBOX 445).
      //: R, P, M and the rest are hidden from a map's rail (`WB_BOARD_ONLY_TOOLS`)
      //: but their letters still chose them: measured, R on a map left the rect
      //: tool live, the board's stroke bar showing and the topic deselected, and
      //: a word typed on a map walked through a dozen hidden tools. The letter
      //: falls through instead, so M on a map is the app's quick-nav chord again.
      if (mapped && wbIsMap() && WB_BOARD_ONLY_TOOLS.has(mapped)) return;
      if (mapped) {
        if (mapped !== "select") clearWbSelection(); // switching away from Select drops it
        selectWbTool(mapped);
        return;
      }
      if (WB_ACTION_KEYS[letter]) {
        const btn = document.getElementById(WB_ACTION_KEYS[letter]);
        //: The same rule for the action keys: I's picture button lives in the
        //: rail's board-only Add section, so on a map it is not there to press.
        if (btn && btn.closest('[data-wb-surface="board"]') && wbIsMap()) return;
        if (btn) {
          e.preventDefault();
          btn.click();
        }
      }
    });
  }

  //: The file's surface: what other files call (L634).
  Object.assign(window, { wbInitMenus });
})();
