// obj-drag.js: the one pointer gesture for moving an object (INBOX 1467,
// parts 2 and 4). Lazy, loaded by obj-ref.js. A press on a card arms it; the
// gesture goes live only when the pointer moves after a *still* hold of 250ms
// (under 4px of travel meanwhile), or at once from a visible grip
// (`OBJ_GRIP`). A move before the hold is over is a text selection or a swipe
// and lets the press go, and a press that starts inside selected text is
// never a drag, so a click, a double click, a scroll flick and a slow text
// selection on a card are untouched. A press on a picture needs no hold (it has
// no words to select, and a quick drag would be the browser's own image drag),
// and a finger takes the hold itself: still for `OBJ_TOUCH_MS` lifts the card,
// and the page stops scrolling under it. While live a small ghost card follows the pointer and the
// current mode (`OBJ_MODES`: obj-reorder.js's `reorder`, obj-carry.js's
// `carry`, diagram-builder.js's `diagram`) decides what the pointer is over, and may hand the gesture to another
// mode (`route`). Escape or a press of another
// button ends it with no change.

//: Travel that ends a still hold (and, after the hold, starts the drag).
(() => {
  const OBJ_DRAG_PX = 4;
  //: How long a press must stay still before a move is a drag.
  const OBJ_DRAG_MS = 250;
  //: A finger's hold: still this long lifts the card (before it, a move is a scroll).
  //: Under the 500 ms of `wireLongPress`: a card lifted and not moved by then is that menu's press.
  const OBJ_TOUCH_MS = 350;
  //: How long the pointer rests on a card before its grip appears (the popup hit test is paid once, for the card it stops on).
  const OBJ_GRIP_REST_MS = 90;
  //: A visible handle on a card: a press on it is a drag from the first move.
  const OBJ_GRIP = "[data-obj-grip]";
  //: Where a press never starts a drag: the card's own controls.
  const OBJ_NO_GRAB = "input, select, textarea, [contenteditable='true'], button, a[href], summary, [draggable='true'], .chip-interactive, .menu-wrap, label";
  const OBJ_ICON = { note: "ph-note", document: "ph-file-text", diagram: "ph-flow-arrow", board: "ph-squares-four", map: "ph-tree-structure", image: "ph-image", file: "ph-file", upload: "ph-file", block: "ph-squares-four" };

  //: The gesture in progress (armed or live), or null.
  let objDragNow = null;
  //: What each mode does; the modes register themselves in their own files.
  const OBJ_MODES = {};

  function objGhostMake(ref) {
    const ghost = document.createElement("div");
    ghost.className = "obj-ghost";
    ghost.setAttribute("aria-hidden", "true");
    //: Above the sheets and popovers it crosses; set here so it is not a layer in the stylesheets' budget.
    ghost.style.zIndex = "3100";
    const icon = document.createElement("i");
    icon.className = `ph ${OBJ_ICON[ref.kind]}`;
    const words = document.createElement("span");
    words.textContent = ref.title;
    ghost.append(icon, words);
    return ghost;
  }

  function objPressOnGrip(target) {
    return Boolean(target?.closest?.(OBJ_GRIP));
  }

  //: Whether the press lands on words that are selected: it belongs to the
  //: selection (drag the words, or click to clear them), never to a card drag.
  function objPressInSelection(event) {
    const selection = window.getSelection?.();
    if (!selection || selection.isCollapsed || !selection.rangeCount) return false;
    const { clientX: x, clientY: y } = event;
    return [...selection.getRangeAt(0).getClientRects()].some((r) => x >= r.left && x <= r.right && y >= r.top && y <= r.bottom);
  }

  //: Whether a press may arm a drag, and from which card: `{ card, ref }`.
  //: The modes' `grab(hit)` may add to it (the reorder mode's surface).
  function objDragSeed(event) {
    if (event.button !== 0 || event.defaultPrevented) return null;
    //: A mode with its own cards (`seed`: a diagram's blocks, diagram-builder.js) answers before the app's object cards do.
    for (const name of Object.keys(OBJ_MODES)) {
      const own = OBJ_MODES[name].seed?.(event);
      if (own) return { ...own, mode: name, ...OBJ_MODES[name].grab(own) };
    }
    const grip = objPressOnGrip(event.target);
    const control = event.target.closest?.(OBJ_NO_GRAB);
    //: A tray item and a chat source card are buttons you click and also drag: a held drag carries the object.
    if (control && !control.matches(".obj-tray-use, .chat-source-card[data-obj]") && !grip) return null;
    //: The floating grip (below) is not inside the card it moves; it names it.
    const hit = objCardAt(event.target.closest?.(OBJ_GRIP)?.objCard || event.target);
    if (!grip && objPressInSelection(event)) {
      //: Words a failed try left selected on this card give way to a new hold (INBOX 1595); any other selection is the reader's.
      if (!hit?.card.objFailed) return null;
      window.getSelection().removeAllRanges();
    }
    if (!hit) return null;
    hit.card.objFailed = false;
    const mode = Object.keys(OBJ_MODES).find((name) => OBJ_MODES[name].grab?.(hit));
    //: A picture or a tray row has no text to select, so a press on one is a grip:
    //: a press that moves carries, a click that does not still pastes (INBOX 1603).
    const quick = grip || (event.pointerType !== "touch" && (event.target.tagName === "IMG" || Boolean(event.target.closest?.(".obj-tray-use"))));
    return mode ? { ...hit, mode, grip: quick, ...OBJ_MODES[mode].grab(hit) } : null;
  }

  function objDragArm(event) {
    const seed = objDragNow ? null : objDragSeed(event);
    if (!seed) return;
    objDragNow = { ...seed, id: event.pointerId, x0: event.clientX, y0: event.clientY, x: event.clientX, y: event.clientY, t0: event.timeStamp, live: false };
    objDragListen(true);
    //: The hold is over: the cursor says the card can be taken now.
    const g = objDragNow;
    g.touch = event.pointerType === "touch";
    g.cue = setTimeout(() => objDragCue(g), g.touch ? OBJ_TOUCH_MS : g.grip ? 0 : OBJ_DRAG_MS);
  }

  //: The hold is over. A mouse is told with the cursor; a finger lifts the card at
  //: once (a move is already the drag, and the page must not scroll).
  function objDragCue(g) {
    if (objDragNow !== g) return;
    g.card.classList.add("obj-armed");
    if (!g.touch) return;
    objDragBegin(g);
    objDragFrame(g);
  }

  function objDragListen(on) {
    const act = on ? "addEventListener" : "removeEventListener";
    window[act]("pointermove", objDragMove, true);
    window[act]("pointerup", objDragUp, true);
    window[act]("pointercancel", objDragUp, true);
    window[act]("keydown", objDragKey, true);
    //: A picture inside a card would start the browser's own drag a few
    //: pixels in and end this one; a text selection is only stopped once live.
    document[act]("dragstart", objDragNoNative, true);
    //: Non-passive and only while a gesture is armed, so scrolling elsewhere stays off the main thread.
    window[act]("touchmove", objDragNoScroll, { capture: true, passive: false });
    window[act]("contextmenu", objDragNoMenu, true);
  }

  function objDragNoScroll(event) {
    if (objDragNow?.live && event.cancelable) event.preventDefault();
  }

  //: A held finger asks for the system menu too; a lifted card is not that request.
  function objDragNoMenu(event) {
    if (!objDragNow?.touch || !objDragNow.moved) return;
    event.preventDefault();
    event.stopImmediatePropagation();
  }

  function objDragNoNative(event) {
    event.preventDefault();
  }

  //: Moving before the hold is over is a swipe or a text selection, not a drag:
  //: the press is let go of. Held still long enough and then moved is the drag,
  //: and a grip needs no hold.
  function objDragVerdict(g, event) {
    //: A finger drifts more than a hand on a mouse; before its hold a move is a scroll.
    const far = Math.hypot(event.clientX - g.x0, event.clientY - g.y0) >= (g.touch ? OBJ_DRAG_PX * 3 : OBJ_DRAG_PX);
    if (!far) return "wait";
    if (g.touch) return "swipe";
    return g.grip || event.timeStamp - g.t0 >= OBJ_DRAG_MS ? "start" : "swipe";
  }

  function objDragMove(event) {
    const g = objDragNow;
    if (!g || event.pointerId !== g.id) return;
    g.x = event.clientX;
    g.y = event.clientY;
    //: A lifted card the finger has not moved is still a long press, and gives way to its menu.
    g.moved ||= Math.hypot(g.x - g.x0, g.y - g.y0) >= OBJ_DRAG_PX * 3;
    if (!g.live) {
      const verdict = objDragVerdict(g, event);
      if (verdict === "swipe") {
        //: A mouse press that moved before the hold selects words under it; remember whose, so a press on them can retry.
        if (!g.touch) g.card.objFailed = true;
        return objDragFinish(true, event);
      }
      if (verdict === "wait") return;
      objDragBegin(g);
    }
    objDragFrame(g);
  }

  function objDragBegin(g) {
    g.live = true;
    //: The shared drag flag (menus.js): no popover closes under a card being carried.
    dragFlag.hold("obj");
    window.getSelection()?.removeAllRanges();
    document.documentElement.classList.add("obj-dragging");
    document.addEventListener("selectstart", objDragNoNative, true);
    g.ghost = objGhostMake(g.ref);
    document.body.append(g.ghost);
    OBJ_MODES[g.mode].begin(g);
    objDragSchedule(g);
  }

  //: The one frame loop, alive only while a drag is (nothing wakes at rest).
  function objDragSchedule(g) {
    g.tick = requestAnimationFrame(() => objDragTick(g));
  }

  function objDragFrame(g) {
    g.ghost.style.transform = `translate(${g.x + 14}px, ${g.y + 16}px)`;
    objDragRoute(g);
    OBJ_MODES[g.mode].update(g);
  }

  //: A card dragged out of its own list stops reordering and starts carrying,
  //: and dragged back in it reorders again: the mode names the one it wants next.
  function objDragRoute(g) {
    const next = OBJ_MODES[g.mode].route?.(g);
    if (!next || next === g.mode) return;
    OBJ_MODES[g.mode].cancel(g);
    g.mode = next;
    OBJ_MODES[next].begin(g);
  }

  //: A held pointer at a scroller's top or bottom edge keeps scrolling it, so a
  //: long list can be reordered from end to end (no `pointermove` arrives while
  //: the hand is still). The edge is the part of the box that is on screen, so a pane that runs past
  //: the window has its edge at the window's. A mode with `ancestors` also hands the scroll to the
  //: scrollers around it (the diagram pane inside a short document page, 1546 P2), the inner one
  //: first, and only a scroller that can still move that way.
  function objDragTick(g) {
    if (objDragNow !== g) return;
    //: Over the tray's drop zone the page holds still (INBOX 1603: "if I drag something
    //: over the tray, I dont want the page to scroll"); the status bar sits on the edge.
    if (objTrayDoor.hit(g.x, g.y)) return objDragSchedule(g);
    if (g.scroller && !g.edges) {
      g.edges = [g.scroller];
      if (OBJ_MODES[g.mode].ancestors) {
        for (let node = g.scroller.parentElement; node && node !== document.body; node = node.parentElement) {
          if (/auto|scroll/.test(getComputedStyle(node).overflowY)) g.edges.push(node);
        }
      }
    }
    for (const el of g.edges || []) {
      const box = el.getBoundingClientRect();
      const top = Math.max(box.top, 0);
      const bottom = Math.min(box.bottom, innerHeight);
      const near = Math.max(0, 48 - (g.y - top), g.y - (bottom - 48));
      const way = g.y < (top + bottom) / 2 ? -1 : 1;
      if (near <= 0 || (OBJ_MODES[g.mode].ancestors && (way < 0 ? el.scrollTop <= 0 : el.scrollTop + el.clientHeight >= el.scrollHeight - 1))) continue;
      el.scrollTop += way * Math.ceil(near / 6);
      OBJ_MODES[g.mode].update(g);
      break;
    }
    objDragSchedule(g);
  }

  function objDragUp(event) {
    if (objDragNow && event.pointerId === objDragNow.id) objDragFinish(event.type === "pointercancel", event);
  }

  function objDragKey(event) {
    if (event.key !== "Escape") return;
    event.preventDefault();
    event.stopPropagation();
    objDragFinish(true, event);
  }

  //: A click that follows a live drag is the drop landing on the card, not a
  //: request to open it.
  function objDragSwallowClick() {
    const stop = (event) => event.stopPropagation();
    window.addEventListener("click", stop, { capture: true, once: true });
    setTimeout(() => window.removeEventListener("click", stop, true), 0);
  }

  //: What navigation.js asks when a long press fires a menu: "" when no card was lifted, "moved" when the hold lifted a card and it moved (a drag, the menu stays away), "held" when it lifted one that was held still (the lift ends here, the menu opens).
  function objDragLifted() {
    if (!objDragNow?.live) return "";
    if (objDragNow.moved) return "moved";
    objDragFinish(true);
    return "held";
  }

  function objDragFinish(cancel, event) {
    const g = objDragNow;
    objDragNow = null;
    objDragListen(false);
    clearTimeout(g?.cue);
    g?.card.classList.remove("obj-armed");
    if (!g?.live) return;
    cancelAnimationFrame(g.tick);
    //: In a `finally`: a drop that throws must not leave the flag set, or no popover would ever close again.
    try {
      OBJ_MODES[g.mode][cancel ? "cancel" : "drop"](g, event);
    } finally {
      dragFlag.release("obj");
      g.ghost.remove();
      document.removeEventListener("selectstart", objDragNoNative, true);
      document.documentElement.classList.remove("obj-dragging");
      objDragSwallowClick();
    }
  }

  window.addEventListener("pointerdown", objDragArm, true);

  //: The grip (INBOX 1595): one handle that floats on the left edge of the card the pointer is
  //: over or that has the keyboard focus, and takes the card at once, with no hold. It is not part
  //: of any card's markup (a card renderer never changes) and names its card in `objCard`, which
  //: `objDragSeed` reads. Closed in a function so it adds no name to the shared scope. A finger has
  //: its own hold, so the stylesheet hides the grip where there is no hover.
  (() => {
    let grip = null;
    let card = null;
    let timer = 0;
    let rested = 0;

    //: The card under `target` that some mode would move, or null.
    const movable = (target) => {
      const hit = objDragNow || !target?.closest ? null : objCardAt(target);
      return hit && Object.keys(OBJ_MODES).some((name) => OBJ_MODES[name].grab?.(hit)) ? hit.card : null;
    };

    const hide = () => {
      clearTimeout(timer);
      clearTimeout(rested);
      card = null;
      grip?.classList.remove("is-on");
      window.removeEventListener("scroll", hide, true);
    };

    //: Keyboard focus keeps the grip after the pointer leaves; nothing else does.
    const settle = () => {
      if (card?.querySelector(":focus-visible") || card?.matches(":focus-visible")) return;
      hide();
    };

    function show(next) {
      clearTimeout(timer);
      clearTimeout(rested);
      if (next === card || !next.isConnected) return;
      if (!grip) {
        grip = document.createElement("span");
        grip.className = "obj-grip";
        grip.dataset.objGrip = "";
        grip.setAttribute("aria-hidden", "true");
        grip.title = "Drag to move this card";
        //: Above the cards and their sticky heads, under the drag ghost (3100); set here so it is not a layer in the stylesheets' budget.
        grip.style.zIndex = "3050";
        const dots = document.createElement("i");
        dots.className = "ph ph-dots-six-vertical";
        grip.append(dots);
        //: Under `<html>`, not `<body>` (INBOX 1726): a node added to the body re-asks every `:has()` subject of the page, 124 to 213ms on the Library Images tab at 4x.
        document.documentElement.append(grip);
      }
      const box = next.getBoundingClientRect();
      //: Half out of the card's left edge, level with the middle of a short card or the first line of a tall one.
      let left = Math.max(2, box.left - grip.offsetWidth / 2);
      let top = Math.max(2, box.top + Math.min(box.height, 56) / 2 - grip.offsetHeight / 2);
      //: A card with its own tick in that corner (INBOX 1605, the owner: "the drag popup and the
      //: selection boxes clash"): the tick keeps the corner and the grip steps wholly outside the
      //: card, or under the tick where the card is at the screen's edge. Any checkbox, so every card.
      const tick = [...next.querySelectorAll('input[type="checkbox"]')].find((t) => {
        const r = t.getBoundingClientRect();
        return r.width && r.left < left + grip.offsetWidth && r.right > left && r.top < top + grip.offsetHeight && r.bottom > top;
      });
      if (tick) {
        left = Math.max(2, box.left - grip.offsetWidth - 2);
        const r = tick.getBoundingClientRect();
        if (left + grip.offsetWidth > r.left) top = r.bottom + 4;
      }
      //: Only where the card's own column is on top: a popup over the card's edge (the
      //: activity panel, a dialog) keeps the grip off it (owner, 2026-11-03: "the drag icon
      //: button shows ... in front of popup windows"). The grip is a body layer above them all.
      const under = document.elementsFromPoint(left + grip.offsetWidth / 2, top + grip.offsetHeight / 2).find((el) => !grip.contains(el));
      if (under && !under.contains(next) && !next.contains(under)) return hide();
      card = next;
      grip.objCard = next;
      grip.style.left = `${left}px`;
      grip.style.top = `${top}px`;
      grip.classList.add("is-on");
      window.addEventListener("scroll", hide, { capture: true, passive: true });
    }

    //: **One look a frame, not one per `pointerover`** (INBOX 1667: 14 to 40ms of forced layout a call, 59
    //: calls in a 6s wheel at 4x): `show` reads boxes. The last target of the frame is looked at.
    let over = null;
    let overFrame = 0;
    const look = () => {
      overFrame = 0;
      const target = over;
      over = null;
      if (!target?.isConnected) return;
      const next = movable(target);
      //: **Rest before showing** (INBOX 1716 lag log, `show` 1192ms of self time on a hover): the popup test below is a hit test, 8 to 54ms a card at 4x on a
      //: page of 30,000 nodes, and a pointer crossing cards paid it for each. A card under the pointer for `OBJ_GRIP_REST_MS` gets the grip; the card already holding it is kept at once.
      clearTimeout(rested);
      if (next === card || next) {
        //: One read of the boxes a look: now for the card already holding the grip, after the rest for a new one.
        const showNext = () => show(next);
        if (next === card) return showNext();
        clearTimeout(timer);
        rested = setTimeout(showNext, OBJ_GRIP_REST_MS);
        return;
      }
      if (card) {
        clearTimeout(timer);
        timer = setTimeout(settle, 160);
      }
    };
    //: Nor for a card that scrolled under a resting pointer (INBOX 1667: 1.5s of forced layout in a wheel
    //: at 4x). The pointer's place is kept; once the scroll is still for 200ms the card under it is looked at once.
    let scrolledAt = 0;
    let rest = null;
    let restTimer = 0;
    const restLook = () => {
      if (!rest || performance.now() - scrolledAt < 200) return;
      over = document.elementFromPoint(rest.x, rest.y);
      rest = null;
      look();
    };
    const armRest = () => {
      clearTimeout(restTimer);
      restTimer = setTimeout(restLook, 220);
    };
    window.addEventListener("scroll", () => {
      scrolledAt = performance.now();
      if (rest) armRest();
    }, { capture: true, passive: true });
    document.addEventListener("pointerover", (event) => {
      if (event.pointerType === "touch") return;
      if (performance.now() - scrolledAt < 200) {
        rest = { x: event.clientX, y: event.clientY };
        return armRest();
      }
      rest = null;
      if (event.target === grip || grip?.contains(event.target)) {
        over = null;
        clearTimeout(rested);
        return clearTimeout(timer);
      }
      over = event.target;
      //: A timer after the frame, so the read is not the one that pays for the frame's own layout.
      if (!overFrame) {
        overFrame = 1;
        afterFrames(() => setTimeout(look), 1);
      }
    }, true);
    document.addEventListener("focusin", (event) => {
      const next = movable(event.target);
      if (next && event.target.matches?.(":focus-visible")) show(next);
    }, true);
    document.addEventListener("focusout", () => {
      if (card) timer = setTimeout(settle, 0);
    }, true);
    //: A press on the grip starts the drag; the handle then gets out of the way until the pointer moves on.
    window.addEventListener("pointerdown", (event) => {
      if (event.target === grip || grip?.contains(event.target)) hide();
    }, true);
  })();

  Object.assign(window, { OBJ_ICON, OBJ_MODES, objDragLifted, objDragMove });
})();
