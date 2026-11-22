(() => {
  // whiteboard-pan.js: middle-button pan, wheel and pinch zoom, the board settings controls (background, sticky fold, rough) and the export button; a section of initWhiteboard (L634).
  // Wrapped: initWhiteboard calls it once, passing the names it shares; nothing here runs at load.
  function wbInitPan({ selectWbTool }) {
    const container = d3.select("#whiteboard-container");
    //: **Middle button: the pan, and nothing else** (INBOX 167: "when I push
    //: down my middle scroll wheel on my mouse to pan the whiteboard, it is
    //: very glitch and jittery"). On Windows, Chromium and Edge start their
    //: own autoscroll on a middle-button press over anything scrollable unless
    //: the `mousedown` is default-prevented, so the page scrolled with the
    //: pointer while d3-zoom panned the board with it: two scrolls of one
    //: gesture, fighting. `mousedown`, not `pointerdown`: preventing the
    //: pointer event would also suppress the compatibility mouse event d3-zoom
    //: listens for and the pan would never start. Reasoned from the browser's
    //: documented behaviour; this sandbox has no autoscroll to observe.
    //: Registered in the capture phase and before the zoom behaviour: d3-zoom's
    //: own mousedown handler stops immediate propagation, so a bubbling
    //: listener added after it on the same element never runs at all
    //: (measured: the first version of this, added below `call(wbZoom)`,
    //: prevented nothing).
    //: On the window rather than the container: measured with a real press,
    //: the event's target was a layer over the board and the container's own
    //: capture listener never saw it, while a synthetic press on the container
    //: was prevented. Anything inside the boards view counts.
    //: The second half of the same report (INBOX 183: "panning ... by pressing
    //: down the scrollwheel with a mouse is horrible and doesnt work"). The
    //: autoscroll guard below was already here and is not enough on its own,
    //: because nothing else about the gesture said it was a pan: the cursor
    //: stayed an arrow over the board while the board moved under it, and the
    //: release fired an `auxclick`, which on Linux is also the primary-selection
    //: paste. A hand tool drag says "grabbing" the whole time; this now says the
    //: same thing through the same class the held-space pan uses, so the three
    //: ways to pan look identical while they run.
    //: A second finger on the board puts any drag in flight back and leaves the
    //: gesture to the zoom (INBOX 888; `wbIsSecondTouch` above). Capture, on the
    //: window, for the reason the middle-button listener below gives.
    //: **And the zoom has to be able to hear the first finger.** d3-drag listens
    //: for a touch's moves and ends on the element the touch began on, and ends
    //: each with `stopImmediatePropagation`, so with the first finger on a card
    //: its moves never reach d3-zoom on the container: measured, a pinch from a
    //: note moved the scale 1 to 1 (`wbpinch.js`) because the zoom only ever
    //: heard the second finger. For as long as two fingers are down the events
    //: are told not to stop, which leaves d3-drag's own bookkeeping to run its
    //: course (it ends its gesture on the finger's lift, and its handlers read
    //: the cancelled gesture and save nothing).
    let wbPinching = false;
    window.addEventListener("touchstart", (event) => {
      if (event.touches.length < 2 || !event.target?.closest?.("#library-view-whiteboard")) return;
      wbPinching = true;
      wbCancelGesture();
    }, { capture: true, passive: true });
    for (const type of ["touchmove", "touchend", "touchcancel"]) {
      window.addEventListener(type, (event) => {
        if (!wbPinching) return;
        Object.defineProperty(event, "stopImmediatePropagation", { value() {}, configurable: true });
        if (type !== "touchmove" && event.touches.length === 0) wbPinching = false;
      }, { capture: true, passive: true });
    }
    const midPanClass = (on) => {
      wbMidPanHeld = on;
      wbInstances.container()?.classList.toggle("wb-mid-pan", on);
    };
    window.addEventListener("mousedown", (event) => {
      if (event.button === 1 && event.target?.closest?.("#library-view-whiteboard")) {
        event.preventDefault();
        midPanClass(true);
      }
    }, true);
    //: On the window, not the container: a pan that ends with the pointer over
    //: the top bar or off the window would otherwise leave the grabbing cursor
    //: on for good, which is exactly the shape the stray marquee had.
    for (const end of ["mouseup", "blur", "pointercancel"]) {
      window.addEventListener(end, (event) => {
        if (end !== "mouseup" || event.button === 1) midPanClass(false);
      }, true);
    }
    //: The middle release itself: an `auxclick` inside the board is the tail of
    //: a pan and never a command, and letting it through is what makes a pan
    //: paste on Linux or open a link in a card in a new tab.
    window.addEventListener("auxclick", (event) => {
      if (event.button === 1 && event.target?.closest?.("#library-view-whiteboard")) event.preventDefault();
    }, true);
    container.call(wbZoom).on("dblclick.zoom", null);
    //: Pan and zoom listeners: `view`, so a read-only embed gets them too.
    wbInstances.on("scroll", wbFoldNativeScroll, undefined, true);
    // Shift+wheel pans sideways; every other wheel is d3-zoom's, by
    // `wbZoomFilter`, which prevents the page scrolling too. `passive: false`
    // here so the page behind the board does not scroll on a shifted wheel.
    if (!container.node().dataset.wbWheelPan) {
      container.node().dataset.wbWheelPan = "1";
      wbInstances.on("wheel", (e) => {
        //: **A wheel held down is a pan, not a scroll** (the owner, 2026-09-24,
        //: from the desktop window: the middle-button pan "jerks repeatedly to
        //: the left side of the screen until i let go"). Pressing a wheel hard
        //: enough to click it rocks it on most Windows mice, and a rocked wheel
        //: is a horizontal wheel event, repeated for as long as it is held.
        //: Each one panned the board sideways on top of d3-zoom's own drag,
        //: which keeps the pressed point under the pointer from wherever the
        //: board then is: measured with a tilt between every move of a 300px
        //: drag, the board ran 3300 to 3600px sideways whichever way the hand
        //: went (`midpanwheel.js`). While the middle button is down the drag
        //: is the only thing that moves the board; the event is still
        //: prevented so the page behind cannot scroll either. `buttons` for
        //: the press the event itself reports, the flag for a driver whose
        //: synthetic wheel events carry no buttons at all.
        if ((e.buttons & 4) === 4 || wbMidPanHeld) {
          e.preventDefault();
          return;
        }
        if (e.ctrlKey || e.metaKey || !(e.shiftKey || wbTrackpadPan(e))) return;
        e.preventDefault();
        const el = d3.select(e.currentTarget);
        const k = d3.zoomTransform(el.node()).k || 1;
        const unit = e.deltaMode === 1 ? 16 : e.deltaMode === 2 ? 400 : 1;
        let dx = e.deltaX * unit, dy = e.deltaY * unit;
        //: Shift+wheel on a mouse turns the notch sideways; a trackpad scroll
        //: already carries both axes and keeps them.
        if (!dx && !wbTrackpadPan(e)) { dx = dy; dy = 0; }
        el.call(wbZoom.translateBy, -dx / k, -dy / k);
      }, { passive: false }, true);
    }
    
    // Toolbar hooks
    document.getElementById("wb-zoom-in").addEventListener("click", () => wbZoomStep(1.2, { duration: 250, usePointer: false }));
    document.getElementById("wb-zoom-out").addEventListener("click", () => wbZoomStep(0.8, { duration: 250, usePointer: false }));
    // Was `wbZoom.transform(d3.zoomIdentity)`, a reset to 100% at the origin,
    // under a button labelled "Fit to Screen". See `wbZoomToFit`.
    document.getElementById("wb-zoom-fit").addEventListener("click", () => wbZoomToFit());
    //: The level is a typeable field (value-field.js); drawn now, since the markup holds only its host.
    wbShowZoomLevel(d3.zoomTransform(wbInstances.container()).k || 1);

    // **An arrow, not the function directly.** `addEventListener` passes the
    // click event as the first argument, which would land in
    // `toggleWhiteboardFullscreen`'s own `force` parameter: a `MouseEvent` is
    // truthy, so `force === undefined` was never true and the toggle could
    // only ever turn full screen *on*. Reported as "I cant exit full screen
    // mode in the whiteboard".
    document.getElementById("wb-fullscreen")?.addEventListener("click", () => toggleWhiteboardFullscreen());

    // --- Navigator ----------------------------------------------------------
    document.getElementById("wb-navigator-close")?.addEventListener("click", () => wbToggleNavigator(false));
    document.getElementById("wb-navigator-fit")?.addEventListener("click", () => wbZoomToFit());
    const navMap = document.getElementById("wb-navigator-map");
    if (navMap) {
      // Pointer events rather than mouse events, so a pen or a touch drag on a
      // tablet moves the viewport too, this is a drawing app, and the board is
      // reachable from a touchscreen. The drag itself, and why it is shaped as
      // it is, is at `wbNavigatorDragStart`.
      navMap.addEventListener("pointerdown", wbNavigatorDragStart);
      navMap.addEventListener("pointermove", wbNavigatorDragMove);
      navMap.addEventListener("pointerup", wbNavigatorDragEnd);
      navMap.addEventListener("pointercancel", wbNavigatorDragEnd);
      navMap.addEventListener("lostpointercapture", wbNavigatorDragEnd);
    }
    try {
      if (prefs.get("wb-navigator-open", null) === "1") wbToggleNavigator(true);
    } catch {
      /* private mode: open it by hand */
    }

    // --- Find a card on this board ------------------------------------------
    document.getElementById("wb-search-close")?.addEventListener("click", wbCloseBoardSearch);
    document.getElementById("wb-search-prev")?.addEventListener("click", () => wbBoardSearchGo(-1));
    document.getElementById("wb-search-next")?.addEventListener("click", () => wbBoardSearchGo(1));
    const searchInput = document.getElementById("wb-search-input");
    if (searchInput) {
      searchInput.addEventListener("input", () => wbBoardSearchRun(searchInput.value));
      searchInput.addEventListener("keydown", (event) => {
        if (event.key === "Enter") {
          event.preventDefault();
          // Enter re-runs nothing: the matches are already live from `input`.
          // It only steps, which is what every find bar in every editor does.
          wbBoardSearchGo(event.shiftKey ? -1 : 1);
        } else if (event.key === "Escape") {
          event.preventDefault();
          wbCloseBoardSearch();
        }
      });
    }
    
    //: The top bar's Sidebar button opens and closes the board's sidebar
    //: (decision 26, whiteboard-library.js) on the tab it was left on.
    $("wb-add-note").addEventListener("click", () => {
      const panel = $("wb-sidebar-panel");
      if (panel && !panel.classList.contains("hidden")) wbCloseSidebar();
      else wbOpenSidebar(null);
    });

    const btnAddSketch = document.getElementById("wb-add-sketch");
    if (btnAddSketch) {
      btnAddSketch.addEventListener("click", () => {
        openSketch();
      });
    }

    const boardSelect = document.getElementById("wb-board-select");
    if (boardSelect) {
      boardSelect.addEventListener("change", async (e) => {
        window.currentBoardId = e.target.value || null;
        await fetchWhiteboardState();
        wbScheduleRender();
        // The look is the board's, so switching boards redraws it.
        await wbMigrateBackground();
        wbApplyBackground();
      });
    }
    //: Not `createNewBoard` itself: passed as the listener it received the click
    //: event as `preset`, and an Event is truthy, so the dialog opened with a
    //: kind nothing in the segment could match (INBOX 197).
    $("wb-new-board")?.addEventListener("click", () => createNewBoard());
    $("wb-rename-board")?.addEventListener("click", renameCurrentBoard);
    //: L348: the model names the board from what is on it, else its first words do; renamed through Rename's undoable path.
    $("wb-suggest-board-name")?.addEventListener("click", async () => {
      const boardId = window.currentBoardId;
      if (!boardId) return;
      const current = document.getElementById("wb-board-select")?.selectedOptions?.[0]?.dataset.title || "";
      const got = await apiJson(`/whiteboard/boards/${boardId}/suggest-title`, { method: "POST" }).catch((e) => toast(e.message, true));
      if (!got?.title || got.title === current || window.currentBoardId !== boardId) return;
      try {
        const board = await apiJson(`/whiteboard/boards/${boardId}`, { method: "PUT", body: JSON.stringify({ title: got.title }) });
        await refreshBoardList(board);
        wbBoardPutStep(`Renamed the board to \u201c${board.title}\u201d`, boardId, { title: current }, { title: board.title });
      } catch (err) {
        toast(err.message || voiceLine("failed", "rename that board"), true);
      }
    });
    $("wb-map-layout")?.addEventListener("change", (e) => wbMapSetLayout(e.target.value));
    $("wb-map-link-style")?.addEventListener("change", (e) => wbMapSetLinkStyle(e.target.value));
    for (const type of ["pointerover", "focusin"]) {
      wbInstances.on(type, (e) => {
        const node = e.target.closest?.(".wb-map-node");
        if (node) wbMapCache.part(node, "grip");
      }, { passive: true });
    }
    //: Phase 5's controls (§5 items 18 to 21). Wired here with the rest of the
    //: board chrome rather than inside their own render functions, which is the
    //: shape `tests/test_frontend_handlers.py` exists to keep: a listener added
    //: where an element is drawn is a listener added again every time it is
    //: redrawn.
    $("wb-map-perspective")?.addEventListener("change", (e) => wbMapSetPerspective(e.target.value));
    $("wb-map-theme-item")?.addEventListener("click", wbMapThemeDialog);
    $("wb-map-numbered")?.addEventListener("change", (e) => wbMapSetNumbered(e.target.checked));
    $("wb-map-dim")?.addEventListener("change", (e) => wbMapSetDim(e.target.checked));
    $("wb-map-stats-item")?.addEventListener("click", wbShowMapStats);
    $("wb-zoom-actual")?.addEventListener("click", wbZoomTo100);
    $("wb-map-expand-all")?.addEventListener("click", wbMapExpandAll);
    $("wb-map-fold-all")?.addEventListener("click", () => wbMapFoldToLevel(1));
    $("wb-map-focus-less")?.addEventListener("click", () => wbMapStepFocus(-1));
    $("wb-map-focus-more")?.addEventListener("click", () => wbMapStepFocus(1));
    $("wb-map-focus-clear")?.addEventListener("click", wbMapClearFocus);
    $("wb-map-templates-dismiss")?.addEventListener("click", wbDismissMapTemplates);
    //: A root, because there is nothing on the map to hang it off: `null` as the
    //: parent is exactly what `wbMapAddChild` already means by a top-level
    //: topic, and it opens the new node for typing like every other add does.
    $("wb-map-empty-add")?.addEventListener("click", () => wbMapAddChild(null));
    //: The map dock (MINDMAP_PLAN.md §12.1 item 1). Every one of these already
    //: existed as a key or a hover affordance and nothing else, which is the
    //: owner's complaint in one line: "the mindmap needs to be more separated
    //: with its own controls". No new behaviour is written here on purpose,
    //: these call the same functions Tab, Enter, F and the node's own chevron
    //: call, so the two routes cannot drift.
    $("wb-map-add-root")?.addEventListener("click", () => wbMapAddChild(null));
    //: The emoji and icon library, on the dock of both surfaces (the owner,
    //: 2026-10-10: "Idk where it is or how to use it"); the picker opens
    //: beside the button that asked.
    for (const id of ["wb-add-sticker", "wb-map-add-sticker"]) {
      $(id)?.addEventListener("click", (event) => wbOpenStickerPicker(event.currentTarget));
    }
    //: Focus is one key in both directions (see the F handler), so it is one
    //: button in both directions too.
    $("wb-map-focus-here")?.addEventListener("click", () => {
      const node = wbSelectedMapNode();
      if (!node) return;
      if (wbMapFocusState && wbMapFocusState.id === node.id) wbMapClearFocus();
      else wbMapSetFocus(node.id);
    });
    //: **The ring names what is under the pointer.** See the caption's own rule
    //: in 07-whiteboard-misc.css: eight icon-only circles are eight guesses
    //: otherwise, and a tooltip arrives late and lands over the slot it
    //: describes. Delegated on each ring rather than wired per slot, so the two
    //: rings and every slot added to either are covered by the same four
    //: listeners; `aria-label` is the source, so the caption and the screen
    //: reader cannot say different things.
    for (const ring of document.querySelectorAll(".wb-map-radial")) {
      const caption = ring.querySelector(".wb-map-radial-caption");
      if (!caption) continue;
      const say = (target) => {
        const slot = target?.closest?.(".wb-map-radial-slot");
        if (!slot) return;
        const label = slot.getAttribute("aria-label") || "";
        const hint = slot.dataset.altHint;
        caption.textContent = hint ? `${label} · ${hint}` : label;
      };
      //: **At rest the caption says the keys** (§12.5, and the brief's "show them
      //: in the ring's caption"): every slot in the ring is also a key, and the
      //: ring is meant to be a shortcut rather than the only way in. So the
      //: caption is never empty on the node ring: it names the slot under the
      //: pointer, and the key set when nothing is under it. `data-rest` is on the
      //: markup so the copy sits with the rest of the ring's words.
      const clear = () => { caption.textContent = caption.dataset.rest || ""; };
      caption.textContent = caption.dataset.rest || "";
      ring.addEventListener("pointerover", (event) => say(event.target));
      ring.addEventListener("pointerout", clear);
      ring.addEventListener("focusin", (event) => {
        say(event.target);
        const slot = event.target?.closest?.(".wb-map-radial-slot");
        if (slot?.matches(":focus-visible")) wbMarkMapRadialSector(ring, slot);
      });
      ring.addEventListener("focusout", () => {
        clear();
        wbMarkMapRadialSector(ring, null);
      });
      //: **The ring's own keys** (the pie menu, 2026-09-24): the arrows walk
      //: the sectors, Enter or Space runs the one in hand, Escape closes the
      //: ring and puts the focus back on the board. Handled here and stopped
      //: here, because every one of these keys means something else to the
      //: board's own handler on the document: Enter adds a topic beside,
      //: Escape drops the selection, the arrows walk the tree, and Tab adds a
      //: child, so Tab is only stopped (the browser still moves the focus on,
      //: out of the toolbar, which is what Tab does in one).
      ring.addEventListener("keydown", (event) => {
        const slot = event.target?.closest?.(".wb-map-radial-slot");
        if (!slot) return;
        const to = {
          ArrowRight: () => wbMapRadialStep(ring, slot, 1),
          ArrowDown: () => wbMapRadialStep(ring, slot, 1),
          ArrowLeft: () => wbMapRadialStep(ring, slot, -1),
          ArrowUp: () => wbMapRadialStep(ring, slot, -1),
          Home: () => wbMapRadialStep(ring, slot, "first"),
          End: () => wbMapRadialStep(ring, slot, "last"),
        }[event.key];
        if (event.key === "Tab") {
          event.stopPropagation();
          return;
        }
        if (to) {
          to()?.focus();
        } else if (event.key === "Enter" || event.key === " ") {
          //: A click the slot's own handler reads exactly as a pointer's,
          //: Alt included: Alt+Enter on Add child removes the branch, as
          //: Alt+click does.
          slot.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true, altKey: event.altKey }));
        } else if (event.key === "Escape") {
          if (ring.id === "wb-map-radial") wbCloseMapRadial();
          else wbCloseMapLinkRadial();
          wbInstances.container()?.focus({ preventScroll: true });
        } else {
          return;
        }
        event.preventDefault();
        event.stopPropagation();
      });
    }
    //: The node radial (§12.1 item 3). Each slot reads the node the ring was
    //: opened for, acts, and closes: a ring that stayed open over a map that has
    //: just been re-laid-out would be pointing at empty canvas.
    const radialSlot = (id, run) => {
      $(id)?.addEventListener("click", async (event) => {
        const node = wbMapRadialNode();
        wbCloseMapRadial();
        if (node) await run(node, event);
      });
    };
    radialSlot("wb-radial-child", (node, event) => (
      // Alt swaps the adds for the removes, which is Coggle's gesture. Read
      // from the event rather than from a flag the ring kept, so a keyboard
      // activation with Alt held is the same as a click with Alt held.
      event.altKey ? wbMapDeleteSubtree(node.id) : wbMapAddChild(node.id)
    ));
    radialSlot("wb-radial-sibling", (node, event) => (
      event.altKey ? wbMapRemoveKeepingBranch(node.id) : wbMapAddSibling(node.id)
    ));
    radialSlot("wb-radial-collapse", (node) => wbMapToggleCollapse(node.id));
    radialSlot("wb-radial-delete", (node) => wbMapDeleteSubtree(node.id));
    //: **Connect, from the topic in hand** (§12.5, INBOX 180: "I cant properly
    //: reconnect things that are disconnected"). The connector was a tool in the
    //: dock and nothing on the node, so joining a loose topic to the tree meant
    //: knowing that the tool existed and that `wbMapJoinByLink` reads a line
    //: between a loose node and a tree node as "attach it". This slot picks that
    //: tool and says what to do with it, which is the whole of the discovery
    //: problem; the drag itself is the tool's, unchanged.
    radialSlot("wb-radial-connect", () => {
      selectWbTool("link-straight");
      toast("Drag from this topic to the one it should join.");
    });
    //: **More: the node's own menu** (§12.5). A right-click on a map node opens
    //: the ring, which means the flat menu it used to open was unreachable: the
    //: audit found all eight of its items dead on a map node. The ring keeps six
    //: slots and this is the door to the rest, so nothing is ring-only and the
    //: menu is a list of words rather than a ring of icons for the actions that
    //: are easier to read than to aim at.
    //: **The sector's box is read when it is pressed** (INBOX 421 a). What the
    //: person pressed is where the menu belongs, and the press is the one
    //: moment the sector is certainly on screen: between it and the click the
    //: board polls, renders and may pan, and a ring that was re-placed or
    //: hidden in between gave a box of zeroes at click time. Kept for the one
    //: click that follows (a few seconds at most), and copied, so nothing later
    //: can change it under the menu.
    window.addEventListener("pointerdown", (event) => {
      const slot = $("wb-radial-more");
      if (slot) slot._menuWasOpen = event.target.closest?.("#wb-radial-more") ? Boolean(wbCtxMenuEl && !wbCtxMenuEl.classList.contains("hidden")) : undefined;
    }, true);
    $("wb-radial-more")?.addEventListener("pointerdown", (event) => {
      const slot = event.currentTarget;
      const rect = wbMapRadialSectorRect(slot);
      slot._pressed = {
        rect: wbMenuAnchorOk(rect) ? { ...rect } : null,
        x: event.clientX,
        y: event.clientY,
        at: Date.now(),
      };
    });
    $("wb-radial-more")?.addEventListener("click", (event) => {
      event.stopPropagation();
      const slot = event.currentTarget;
      const pressed = slot._pressed && Date.now() - slot._pressed.at < 4000 ? slot._pressed : null;
      slot._pressed = null;
      const node = wbMapRadialNode();
      const ring = document.getElementById("wb-map-radial");
      const box = ring?.getBoundingClientRect();
      if (!node) return;
      //: **A second press on More closes its menu** (INBOX 1626: "if I click a
      //: button ... and a popup menu shows, if I click that button again, I
      //: expect the popup menu to close"). This handler stops the click, so the
      //: page's outside-click close never sees it. The ring stays, and the
      //: focus stays on More.
      //: Read at the press, in the window's capture phase, because the page's
      //: outside-press close has already hidden the menu by the time this
      //: click arrives (a keyboard Enter has no press, so its live state).
      const wasOpen = slot._menuWasOpen ?? (wbCtxMenuEl && !wbCtxMenuEl.classList.contains("hidden"));
      slot._menuWasOpen = undefined;
      if (wasOpen) {
        wbCloseContextMenu();
        slot.focus({ preventScroll: true });
        return;
      }
      //: **The ring stays while its menu is open** (owner: "the referring
      //: radial menu closes when I open the more menu"): the menu is the ring's
      //: own overflow, and the ring is what says which topic it is about. The
      //: menu opens beside its More button rather than over the ring (see
      //: `wbOpenMapNodeMenu`); picking anything, or Escape, or a click
      //: elsewhere, closes both.
      //: The ring's own box is a zero-sized point at its centre, so "laid out"
      //: is a position, not a size; a hidden ring reads 0,0, which is no point
      //: at all (see `wbOpenMapNodeMenu`'s fallback).
      const laid = box && (box.left || box.top);
      const x = laid ? box.right + 8 : event.clientX || pressed?.x || 0;
      const y = laid ? box.top : event.clientY || pressed?.y || 0;
      //: The More *sector's* box, not the button's: every sector is a button
      //: the size of the whole ring, clipped to its wedge, so the button's own
      //: rect is the ring's square and a menu hung from it hung from the ring.
      //: In order: the box read at the press, the box now (a keyboard Enter has
      //: no press), and then nothing, which `wbOpenMapNodeMenu` answers with
      //: the point or the topic's own box. Never the button itself: its rect
      //: is the ring's whole square, or zeroes once hidden.
      const live = wbMapRadialSectorRect(slot);
      wbOpenMapNodeMenu(node, x, y, pressed?.rect || (wbMenuAnchorOk(live) ? live : null));
    });

    //: The link ring (§12.1 item 4). Same shape as the node ring's slots, one
    //: difference: the colour well is an `<input>`, so it listens for `change`
    //: and closes the ring itself rather than on the click that opened the
    //: browser's own picker.
    const linkNode = () => {
      if (wbMapLinkRadialFor == null) return null;
      const node = (wbState.objects || []).find((o) => o.id === wbMapLinkRadialFor);
      if (!node) wbCloseMapLinkRadial();
      return node || null;
    };
    const linkSlot = (id, run) => {
      $(id)?.addEventListener("click", async () => {
        const node = linkNode();
        wbCloseMapLinkRadial();
        if (node) await run(node);
      });
    };
    //: Each slot is two actions, one per kind of line, chosen from the subject
    //: the ring was opened on rather than from what the slot last said: the
    //: words are re-written by `wbSyncMapLinkRadial` on open, and a handler that
    //: read them back would be reading its own label.
    const crossSlot = (id, onBranch, onCross) => {
      $(id)?.addEventListener("click", async () => {
        const sketchId = wbMapLinkRadialCross;
        const node = sketchId == null ? linkNode() : null;
        wbCloseMapLinkRadial();
        if (sketchId != null) await onCross(sketchId);
        else if (node) await onBranch(node);
      });
    };
    crossSlot("wb-link-reverse", (node) => wbMapReverseEdge(node.id), (id) => wbMapReverseCrossLink(id));
    crossSlot("wb-link-label", (node) => wbMapLabelEdge(node.id), (id) => wbMapCrossLinkToBranch(id));
    crossSlot("wb-link-cut", (node) => wbMapSever(node.id), (id) => wbMapCutCrossLink(id));

    wbWireMapChoices();
    wbWireMapMulti();
    //: The node edit strip (§12.1 item 2). Every handler reads the selection at
    //: the moment it fires rather than closing over a node: the strip is one set
    //: of controls that moves between nodes, so a captured node is a control
    //: that keeps editing whatever was selected when the page loaded.
    //: **Three-state against the map's theme** (§13e), which is the rule
    //: `edge_arrow` below has always followed: store the choice only when it
    //: differs from what this topic would draw anyway. On an unthemed map that
    //: is the behaviour these two have always had, `true` or nothing; on a map
    //: whose theme says bold, pressing the button off has to store an explicit
    //: `false`, because `null` there means "follow the map" and would leave the
    //: topic bold. A person pressing a toggle and watching nothing happen is
    //: the one outcome a toggle must never have.
    for (const [id, field] of [["wb-map-bold", "bold"], ["wb-map-italic", "italic"]]) {
      $(id)?.addEventListener("click", () => {
        const node = wbSelectedMapNode();
        if (node) wbMapSetNodeStyle(node, { [field]: wbMapToggleValue(node, field) });
      });
    }
    //: **A core idea, stored as nothing at all when it is off.** `|| null`
    //: rather than `false` for the same reason "M" stores no font size: a map
    //: made before core nodes existed and one whose node was marked and then
    //: unmarked are the same map, and neither should carry the field into an
    //: export.
    $("wb-map-core")?.addEventListener("click", () => {
      const node = wbSelectedMapNode();
      if (node) wbMapSetNodeStyle(node, { core: !node.data?.core || null });
    });
    $("wb-map-text-size")?.addEventListener("change", (e) => {
      if (wbMapStripSyncing) return;
      const node = wbSelectedMapNode();
      //: "0" is the pin to the app's own size (decision 9), offered only while
      //: the map themes the size; any other empty or zero is no size at all.
      const raw = e.target.value;
      if (node) wbMapSetNodeStyle(node, { font_size: raw === "0" ? 0 : (Number(raw) || null) });
    });
    $("wb-map-align")?.addEventListener("change", (e) => {
      if (wbMapStripSyncing) return;
      const node = wbSelectedMapNode();
      // Empty means "auto", which is no stored alignment at all rather than
      // `left`: a node that has never been aligned and one aligned left read
      // the same on screen and must not read the same in an export.
      if (node) wbMapSetNodeStyle(node, { align: e.target.value || null });
    });
    $("wb-map-strip-icon")?.addEventListener("change", (e) => {
      if (wbMapStripSyncing) return;
      const node = wbSelectedMapNode();
      if (node) wbMapSetNodeStyle(node, { icon: e.target.value || null });
    });
    $("wb-map-shape")?.addEventListener("change", (e) => {
      if (wbMapStripSyncing) return;
      const node = wbSelectedMapNode();
      // Empty is rounded, stored as nothing at all, for the same reason "M"
      // stores no font size: a map made before shapes existed and one somebody
      // set back to rounded are the same map, and neither should carry a field.
      if (node) wbMapSetNodeStyle(node, { shape: e.target.value || null });
    });
    //: The bar on the node's edge (item 177). Same empty-is-the-default rule as
    //: the shape above it: solid is what a map has always drawn, so choosing it
    //: stores nothing rather than pinning the node to today's stylesheet.
    //: A topic's shadow or glow (MINDMAP_PLAN §14.4). Empty is no effect of
    //: its own; `none` (the row a level with an effect adds) keeps it plain.
    $("wb-map-effect")?.addEventListener("change", (e) => {
      if (wbMapStripSyncing) return;
      const node = wbSelectedMapNode();
      if (node) wbMapSetNodeStyle(node, { effect: e.target.value || null });
    });
    $("wb-map-spine")?.addEventListener("change", (e) => {
      if (wbMapStripSyncing) return;
      const node = wbSelectedMapNode();
      if (node) wbMapSetNodeStyle(node, { spine: e.target.value || null });
    });
    //: The fill. Re-renders the board rather than the one node, the way the
    //: colour does: "Fill with its branch" changes every topic under this one.
    $("wb-map-fill")?.addEventListener("change", async (e) => {
      if (wbMapStripSyncing) return;
      const node = wbSelectedMapNode();
      if (!node) return;
      await wbMapSetNodeStyle(node, { fill: e.target.value || null });
      renderWhiteboardNow();
      wbSyncMapFill(node);
    });
    //: The line into the selected topic (item 177). All three re-render the
    //: board rather than only the node, the way the link ring's own slots do: an
    //: edge belongs to two nodes and is drawn in the shared `.wb-map-edges`
    //: layer, so repainting one node cannot redraw it.
    $("wb-map-edge-width")?.addEventListener("change", async (e) => {
      if (wbMapStripSyncing) return;
      const node = wbSelectedMapNode();
      if (!node) return;
      await wbMapSetNodeStyle(node, { edge_width: e.target.value || null });
      renderWhiteboardNow();
    });
    $("wb-map-edge-dashed")?.addEventListener("click", async () => {
      const node = wbSelectedMapNode();
      if (!node) return;
      await wbMapSetNodeStyle(node, { edge_dashed: wbMapToggleValue(node, "edge_dashed") });
      renderWhiteboardNow();
    });
    //: The label's look on that line (the board connector's four: size, colour,
    //: bold, chip), written beside `edge_label` and painted by `wbRenderMapEdges`.
    const labelLook = async (patch) => {
      const node = wbSelectedMapNode();
      if (!node) return;
      await wbMapSetNodeStyle(node, patch);
      renderWhiteboardNow();
    };
    $("wb-map-label-size")?.addEventListener("change", (e) => {
      const size = Math.max(8, Math.min(72, Math.round(Number(e.target.value) || 0)));
      labelLook({ edge_label_size: size && size !== 12 ? size : null });
    });
    $("wb-map-label-color")?.addEventListener("change", (e) => labelLook({ edge_label_color: e.target.value }));
    for (const [id, key] of [["wb-map-label-bold", "edge_label_bold"], ["wb-map-label-chip", "edge_label_chip"]]) {
      $(id)?.addEventListener("click", (e) => labelLook({ [key]: e.currentTarget.getAttribute("aria-pressed") === "true" ? null : true }));
    }
    $("wb-map-edge-arrow")?.addEventListener("click", async () => {
      const node = wbSelectedMapNode();
      if (!node) return;
      //: Stored only when it differs from what this line would draw anyway, so
      //: a map does not fill up with fields pinning every branch to today's
      //: default: a ribbon has no head and a plain stroke has one.
      const want = !wbMapEdgeHasArrow(node);
      const fallback = !wbMapEdgeIsRibbon(node);
      await wbMapSetNodeStyle(node, {
        edge_arrow: want === fallback ? null : (want ? "on" : "off"),
      });
      renderWhiteboardNow();
    });
    //: The line's shape, from the link ring (§12.5). `curve` is stored as no
    //: value at all, the way the strip's "M" is: the default has to stay the
    //: default, or a map full of nodes pinned to "curve" would stop following a
    //: later change to how a map draws.
    $("wb-map-edge-shape")?.addEventListener("change", async (e) => {
      if (wbMapStripSyncing) return;
      const node = wbSelectedMapNode();
      if (!node) return;
      await wbMapSetNodeStyle(node, { edge_style: e.target.value || null });
      renderWhiteboardNow();
    });
    //: Back to the branch, from the node ring (§12.5): it drops every choice the
    //: rest of this strip makes, so it is the last control in it.
    $("wb-map-reset")?.addEventListener("click", () => {
      const node = wbSelectedMapNode();
      if (node) wbMapResetToBranch(node.id);
    });
    $("wb-map-strip-color")?.addEventListener("change", async (e) => {
      const node = wbSelectedMapNode();
      if (!node) return;
      // A colour carries down the branch, so this one *does* redraw the board:
      // every descendant's card and every edge below it changes with it.
      wbPushUndo({ action: "move", kind: "object", id: node.id, before: WB_KIND_INFO.object.payload(node) });
      node.data = { ...node.data, color: e.target.value };
      await wbSaveObject(node);
      renderWhiteboardNow();
    });
    $("wb-map-tidy")?.addEventListener("click", async () => {
      const moved = await wbMapTidy({ quiet: true });
      toast(moved
        ? `Tidied ${nounCount(moved, "node")}.`
        : "Everything is already where this layout puts it.");
    });
    //: A card put away leaves its one line on the empty board (`#wb-empty-cue`, audit 1028 B34).
    $("wb-empty-hint-close")?.addEventListener("click", () => {
      $("wb-empty-hint")?.classList.add("hidden");
      $("wb-empty-cue")?.classList.remove("hidden");
    });
    $("wb-empty-hint-dismiss")?.addEventListener("click", () => {
      prefs.set("wbEmptyHintDismissed", "1");
      wbHintForcedOpen = false;
      $("wb-empty-hint")?.classList.add("hidden");
      $("wb-empty-cue")?.classList.remove("hidden");
    });
    //: The board's help is its own sheet now (INBOX 566): the Board menu's row
    //: and the empty board's card open it, as "?" does.
    $("wb-help-btn")?.addEventListener("click", () => wbOpenHelpSheet());
    //: The card dismissed with "Don't show on new boards" has a way back (1031
    //: BD11: only the Help sheet did); it also turns the preference off.
    $("wb-show-hints")?.addEventListener("click", () => {
      prefs.remove("wbEmptyHintDismissed");
      wbHintForcedOpen = true;
      $("wb-empty-hint")?.classList.remove("hidden");
      $("wb-empty-cue")?.classList.add("hidden");
    });
    $("wb-empty-hint-keys")?.addEventListener("click", () => wbOpenHelpSheet());

    // Board background colour, asked for directly, the ambient generative-art
    // canvas showed straight through the board before this (`--wb-board-bg`,
    // declared in :root, is the fix for anyone who never touches the picker).
    // `input` previews live while dragging the swatch; `change` (fires once,
    // on release/close) is what actually persists, so dragging across ten
    // hues doesn't write ten times.
    //: The colour is the board's (decision 24): `input` previews while the
    //: swatch is dragged, `change` (once, on release) writes it to the board.
    const bgColorPicker = document.getElementById("wb-bg-color-picker");
    const bgColorReset = document.getElementById("wb-bg-color-reset");
    if (bgColorPicker) {
      bgColorPicker.addEventListener("input", (e) => {
        wbInstances.container().style.setProperty("--wb-board-bg", e.target.value);
      });
      bgColorPicker.addEventListener("change", (e) => {
        wbSetBackground({ color: e.target.value });
      });
    }
    // Back to the theme's own board colour, still the current theme's after a
    // light/dark switch, not a hex remembered once.
    if (bgColorReset && bgColorPicker) {
      bgColorReset.addEventListener("click", async () => {
        if (await wbSetBackground({ color: null })) toast("Board background reset to the theme default.");
      });
    }

    // Draggable toolbar panels, asked for directly. Only the small ⠿ grip
    // starts a drag: the panels are almost entirely buttons and inputs, so
    // "grab anywhere on the panel" would fight every click they already
    // handle. Clamped to `#library-view-whiteboard`'s own box, which is the
    // visible window for this view (it fills the tab below the header), so a
    // dragged panel stops at the edge instead of sliding out under the tab bar
    // or off the side of the screen.
    function makeWbPanelDraggable(panel, storageKey) {
      const grip = panel.querySelector(".wb-panel-grip");
      const bounds = document.getElementById("library-view-whiteboard");
      if (!grip || !bounds) return;

      function clamp(left, top) {
        const boundsRect = bounds.getBoundingClientRect();
        const panelRect = panel.getBoundingClientRect();
        const maxLeft = Math.max(0, boundsRect.width - panelRect.width);
        const maxTop = Math.max(0, boundsRect.height - panelRect.height);
        return [Math.min(Math.max(0, left), maxLeft), Math.min(Math.max(0, top), maxTop)];
      }

      function place(left, top) {
        panel.style.left = `${left}px`;
        panel.style.top = `${top}px`;
        panel.style.right = "auto";
        panel.style.bottom = "auto";
        // The bottom-center panel is horizontally centred via `left: 50%` +
        // `transform: translateX(-50%)`, a centring trick, not a drag offset.
        // Left uncleared, an explicit `left` still renders shifted left by
        // half the panel's own width, so a drag ends up visibly ~200px from
        // wherever the pointer actually released it (found by measuring, not
        // by reading the CSS, the rendered box and the styled `left` disagreed
        // by exactly panelWidth / 2).
        panel.style.transform = "none";
      }

      const saved = prefs.get(storageKey, null);
      if (saved) {
        try {
          const { left, top } = JSON.parse(saved);
          const [cLeft, cTop] = clamp(left, top);
          place(cLeft, cTop);
        } catch {
          // A corrupt saved value is not worth failing over, the panel just
          // keeps its CSS-anchored corner instead.
        }
      }

      let dragging = false;
      let startX = 0;
      let startY = 0;
      let startLeft = 0;
      let startTop = 0;

      grip.addEventListener("pointerdown", (e) => {
        dragging = true;
        wbBoardState.capture(grip, e.pointerId);
        grip.classList.add("is-dragging");
        const panelRect = panel.getBoundingClientRect();
        const boundsRect = bounds.getBoundingClientRect();
        // Converts from whichever CSS corner (top-left/top-right/…) the panel
        // started anchored to into an explicit left/top box, so the first drag
        // of a session moves it from wherever it visually is rather than
        // snapping somewhere else first.
        startLeft = panelRect.left - boundsRect.left;
        startTop = panelRect.top - boundsRect.top;
        startX = e.clientX;
        startY = e.clientY;
        place(startLeft, startTop);
        e.preventDefault();
      });

      grip.addEventListener("pointermove", (e) => {
        if (!dragging) return;
        const [left, top] = clamp(startLeft + (e.clientX - startX), startTop + (e.clientY - startY));
        place(left, top);
      });

      function endDrag(e) {
        if (!dragging) return;
        dragging = false;
        grip.classList.remove("is-dragging");
        if (e?.pointerId != null) grip.releasePointerCapture?.(e.pointerId);
        prefs.set(
          storageKey,
          JSON.stringify({ left: parseFloat(panel.style.left) || 0, top: parseFloat(panel.style.top) || 0 })
        );
      }
      grip.addEventListener("pointerup", endDrag);
      grip.addEventListener("pointercancel", endDrag);

      // The box can resize (window resize, the library sidebar opening) after
      // a position was saved for a larger one, reclamp so a panel never ends
      // up partly or fully off-screen.
      new ResizeObserver(() => {
        if (!panel.style.left) return;
        const [left, top] = clamp(wbNum(panel.style.left), wbNum(panel.style.top));
        place(left, top);
      }).observe(bounds);
    }

    document.querySelectorAll(".whiteboard-floating-panel[data-panel-id]").forEach((panel) => {
      makeWbPanelDraggable(panel, `wb-panel-pos-${panel.dataset.panelId}`);
    });

    // **The panels clear each other by measurement, not by a tuned constant.**
    //
    // Reported a third time, as "the properties and top right panel overlap
    // each other... they need to be better and more responsive". The properties
    // panel sat at a hardcoded `top: 11rem`, which is a guess at how tall the
    // top-right panel happens to be, and the CSS comment on it records the
    // guess being bumped from 6rem, then from 10rem, after the same report each
    // time. It cannot be a constant: that panel wraps its eight controls onto
    // one, two or three rows depending on the board's width, so its height is a
    // function of the viewport. The same guessing shows up twice more, the
    // gesture strip's own `bottom`, and the narrow-window rule that lifts the
    // zoom cluster by `30vh` because, as its comment says, "CSS cannot measure
    // a sibling".
    //
    // A ResizeObserver can. Each panel that others have to clear publishes its
    // own height as a custom property on the view, and every rule that needs to
    // sit above or below one derives its offset from that, so the layout is
    // correct at every width, at every wrap count, and after any change to a
    // panel's contents, with no number left to re-tune.
    //
    // Deliberately *not* wired into the drag system: a panel the reader has
    // dragged carries inline `top`/`left`, which wins over these rules anyway,
    // so a custom position keeps working exactly as before.
    const wbPanelMetricsRoot = document.getElementById("library-view-whiteboard");
    if (wbPanelMetricsRoot && typeof ResizeObserver !== "undefined") {
      // "library" is gone (its controls are in the top bar now) but the token
      // stays declared for the one rule in 06-timeline-dialogs.css that the
      // later drawer rule overrides; "topbar" and "zoom" are what the drawer,
      // the sidebar, the search bar and the overview clear today.
      for (const [panelId, name] of [["topbar", "topbar"], ["tools", "tools"], ["zoom", "zoom"]]) {
        const panel = document.querySelector(`[data-panel-id="${panelId}"]`);
        if (!panel) continue;
        //: The observer's first callback runs right after layout, so the panel
        //: is read there with no forced layout; a synchronous first `publish()`
        //: forced the whole board's first layout inside `initWhiteboard`
        //: (78ms at 4x throttle, INBOX 1426 L5). The listeners (the toasts
        //: above the dock) are told BEFORE the property is written, so they
        //: read a clean layout rather than flushing the style change.
        const publish = (entries) => {
          const size = entries && entries[0] && entries[0].borderBoxSize && entries[0].borderBoxSize[0];
          const box = size ? { width: size.inlineSize, height: size.blockSize } : panel.getBoundingClientRect();
          //: The tools row is a pill on one line and a card once wrapped: its
          //: first and last shown sections' rows, read before anything below
          //: writes a style (the listeners and the properties).
          let wrapped = false;
          if (name === "tools") {
            const shown = [...(panel.querySelector(".wb-tool-group")?.children || [])].filter((el) => el.offsetParent);
            wrapped = shown.length > 1 && shown[shown.length - 1].offsetTop > shown[0].offsetTop + 4;
          }
          panel.dispatchEvent(new Event("wb-panel-resize"));
          // A hidden panel measures 0, and a 0 here would collapse the offset
          // of whatever is clearing it right on top of the panel above. The
          // CSS fallbacks stay in charge until there is a real size to use.
          if (box.height > 0) wbPanelMetricsRoot.style.setProperty(`--wb-h-${name}`, `${Math.round(box.height)}px`);
          // The tools panel's width is read back by its own side-dock rule
          // (`width: var(--wb-w-tools)`), so a width taken while it lay along the
          // bottom (758px at 768) became the side column's width.
          if (box.width > 0 && (name !== "tools" || panel.dataset.dock === "side")) wbPanelMetricsRoot.style.setProperty(`--wb-w-${name}`, `${Math.round(box.width)}px`);
          if (name === "tools") panel.classList.toggle("wb-rail-wrapped", wrapped && panel.dataset.dock !== "side");
        };
        new ResizeObserver(publish).observe(panel);
      }
    }

    //: A panel opening or closing, or the window changing size, refits a view
    //: that is still where the last fit put it (INBOX 792). Settled for a
    //: moment first: the sidebar's width eases, and a refit per frame of it
    //: would chase it.
    if (typeof ResizeObserver !== "undefined") {
      let refitTimer = 0;
      const refit = () => {
        //: **A rect read while the canvas was hidden is dropped when it shows**
        //: (wb5): the origin cache is cleared by pointer events, and a canvas
        //: that appears, or a panel that opens beside it, sends none, so a
        //: paste chip or drop read the board 16px left and 60px high (the
        //: library's own padding and tab bar) until the pointer next moved.
        //: The canvas and the panels beside it are all watched here already.
        wbClearCanvasRectCache();
        clearTimeout(refitTimer);
        refitTimer = setTimeout(wbRefitIfFitted, 200);
      };
      for (const id of ["whiteboard-container", "wb-sidebar", "wb-format", "wb-tools-panel"]) {
        const el = document.getElementById(id);
        if (el) new ResizeObserver(refit).observe(el);
      }
    }

    // Asked for directly: once a panel's been dragged there was no way back to
    // its default corner short of clearing localStorage by hand. Clears every
    // panel's saved position and its drag-time inline styles (left/top/right/
    // bottom/transform, all set by `place()` above) so each panel's own
    // top-left/top-right/bottom-center CSS class: never removed, only ever
    // overridden by the inline styles, takes back over.
    const resetPanelsBtn = document.getElementById("wb-reset-panels");
    if (resetPanelsBtn) {
      resetPanelsBtn.addEventListener("click", () => {
        document.querySelectorAll(".whiteboard-floating-panel[data-panel-id]").forEach((panel) => {
          prefs.remove(`wb-panel-pos-${panel.dataset.panelId}`);
          panel.style.left = "";
          panel.style.top = "";
          panel.style.right = "";
          panel.style.bottom = "";
          panel.style.transform = "";
        });
        toast("Panel positions reset.");
      });
    }

    // Grid, snap-to-grid and a board background image (all asked for
    // directly). Each is a per-browser display preference like the board
    // colour beside them, so all three live in localStorage rather than
    // costing the notebook a schema column the server would never read.
    const gridSelect = $("wb-grid-select");
    if (gridSelect) {
      gridSelect.value = wbGridType();
      gridSelect.addEventListener("change", (e) => {
        prefs.set("wb-grid", e.target.value);
        wbApplyGrid();
        // Snap only bites while a grid is visible, so the checkbox has to
        // follow the grid going away rather than silently staying "on".
        $("wb-snap-toggle").disabled = e.target.value === "none";
      });
    }
    $("wb-sticky-fold")?.addEventListener("change", (e) => wbSetBackground({ sticky_fold: e.target.checked }));
    $("wb-rough-toggle")?.addEventListener("change", (e) => wbSetBackground({ rough: e.target.checked }));
    const snapToggle = $("wb-snap-toggle");
    if (snapToggle) {
      snapToggle.checked = prefs.get("wb-snap", null) === "on";
      snapToggle.disabled = wbGridType() === "none";
      snapToggle.addEventListener("change", (e) => {
        prefs.set("wb-snap", e.target.checked ? "on" : "off");
      });
    }
    const bgImageInput = $("wb-bg-image-input");
    $("wb-bg-image")?.addEventListener("click", async () => {
      // A background already set means the button's job is to offer removing
      // it: a second "clear it" control for something most boards never use
      // would be permanent clutter on a panel that is already busy.
      if (wbBoardBackground().image) {
        if (await confirmDialog("Remove this board's background image?")) {
          if (await wbSetBackground({ image: null })) toast("Background image removed. Ctrl+Z puts it back.");
        }
        return;
      }
      bgImageInput?.click();
    });
    bgImageInput?.addEventListener("change", async () => {
      const file = bgImageInput.files?.[0];
      bgImageInput.value = "";
      if (!file) return;
      try {
        const formData = new FormData();
        formData.append("file", file);
        formData.append("board", "true");
        const uploaded = await apiJson("/media/upload", {
          method: "POST",
          headers: authHeaders(),
          body: formData,
        });
        if (await wbSetBackground({ image: uploaded.url })) toast("Background image set.");
      } catch (err) {
        toast(err.message || voiceLine("failed", "set that background image"), true);
      }
    });
    wbApplyGrid();
    wbApplyBackground();

    $("wb-clear-board")?.addEventListener("click", wbClearBoard);
    $("wb-delete-board")?.addEventListener("click", wbDeleteCurrentBoard);
    $("wb-add-to-note")?.addEventListener("click", wbAddBoardToNote);
    $("wb-map-to-doc")?.addEventListener("click", () => wbMapWriteDocument());
    $("wb-board-to-doc")?.addEventListener("click", () => wbMapWriteDocument());
    $("wb-map-study")?.addEventListener("click", () => wbMapStartStudy());
    $("wb-map-build")?.addEventListener("click", () => wbMapBuild.start());
    $("wb-copy-link")?.addEventListener("click", () => {
      const id = window.currentBoardId ?? null;
      if (id === null) return toast("The default board has no address. Make a board first.");
      copyObjectAddress(wbIsMap() ? "map" : "board", id);
    });
    $("wb-export")?.addEventListener("click", () => wbExportBoard());

    // Tool Selection
    window.currentTool = "pan";
  }

  //: The file's surface: what other files call (L634).
  Object.assign(window, { wbInitPan });
})();
