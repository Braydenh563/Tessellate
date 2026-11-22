// Tessellate: Whiteboard subsystem (extracted from app.js).
//
// This is the "Whiteboard" tab: boards, cards, sketches-as-objects, links,
// mind-mapping, export: the OneNote/draw.io-style canvas built across
// HISTORY.md §53-§58/§61 (ROADMAP.md Priority 0 item 2; style.css's half of
// that item was split first, into frontend/css/*.css).
//
// Loaded as a second classic (non-module) <script> tag, after app.js, so it
// shares app.js's global scope: everything here can call `$`, `api`,
// `apiJson`, `toast`, `switchTab`, `confirmDialog`, `openSketch` (the
// separate Quick Sketch modal, see below) and the rest of app.js's helpers
// directly, and app.js's command palette calls `createNewBoard`/
// `wbShowCanvasView` right back. None of that requires a particular load
// order: every cross-file call here happens at runtime, inside a function
// body or an event-listener callback, never at parse time. app.js loads
// first only because this file's own top-level code (the `wbZoom = d3.zoom()`
// assignment) needs `d3` from /vendor/d3.v7.min.js, which the existing
// script order already guarantees, nothing here needs app.js to have run
// first.
//
// NOT included here: the "Quick Sketch" pad (`openSketch`/`closeSketch`/
// `saveSketch`, sketch-pad.js and its `.sp-*` markup), which stayed in
// app.js. It looks related by name, the task that produced this split
// flagged it explicitly for a call, but it is a separate, still-live Wave F
// ("Platform") feature: a full-screen freehand pad that saves a PNG as a
// note, reachable from the command palette and the floating action menu,
// unrelated by call graph to the board/card system below except that the
// whiteboard toolbar's "Add sketch" button opens it (`openSketch()`, called
// at runtime from `initWhiteboard`). Moving it here would have been a scope
// mistake, not a cleanup, so it was left where it was.
//
// ALSO NOT included here any more: the Library's Documents/Image-Gallery
// sub-tabs, their own selection state, and the `#library-subtabs` switcher: 
// all genuinely Library-owned code (they switch and populate OTHER Library
// sub-tabs, not this one) that had ended up in this file's own
// DOMContentLoaded listener purely because it was written in the same block
// as this tab's own two controls (`wb-boards-new`/`wb-back-to-boards`,
// still below). Moved out to frontend/js/library.js in the app.js split's
// second file (§88.3); see that file's own header for the full list and the
// reasoning. `renderLibraryBoardsGallery`/`wbShowBoardsLanding`/
// `wbShowCanvasView` stayed: they render and switch between *this* tab's
// own two views (a boards gallery and the canvas), which is whiteboard's own
// concern even though the gallery happens to live inside the Library's
// Whiteboard sub-tab.

// ======================= WHITEBOARD LOGIC =======================
// **Held-space panning, middle-mouse panning, and wheel zoom from every
// tool.** Reported directly: "the whiteboard is really annoying to use with
// the tools, I'm constantly having to switch between tools to select and move
// around."
//
// That was structural rather than a missing shortcut. Panning *was* a tool, 
// you pressed V to pan and S to select, and `selectWbTool` disabled the zoom
// behaviour outright for every other tool (`container.on(".zoom", null)`),
// which also took **wheel zoom** with it. So while drawing you could neither
// scroll the canvas nor zoom it without first changing tool and then changing
// back.
//
// Every drawing app people already know (Figma, Excalidraw, tldraw) solves
// this the same way, and it is a filter rather than a mode: the zoom
// behaviour stays attached at all times, and decides per-event whether a
// gesture is a pan. Held space, the middle or the right mouse button pans
// from *any* tool; a plain left-drag pans only with Pan, so the Select drag
// on bare canvas stays the marquee and drawing and the lasso are untouched.
let wbSpaceHeld = false;
//: **Tab on a map adds a topic only after the person has engaged the map**
//: (MINDMAP_PLAN, decisions: "Tab adds only when armed"). Set by a pointer
//: press on the canvas, a selection or any map key, cleared when focus lands
//: on a control outside the canvas, so the Tab that brings focus in, and the
//: Tab after it, move on as Tab does everywhere else instead of adding a topic.
let wbMapKeysArmed = false;
//: True from a middle-button press inside the boards view to its release (or
//: the window losing focus), set by the capture listeners in initWhiteboard.
let wbMidPanHeld = false;

//: Paste and hover-lock bookkeeping, one name in the shared scope.
const wbBoardState = { pasteArrived: false, lockHintSaid: false, wheel: { at: -1e9, pad: false }, lane: null };

//: A two-finger trackpad scroll pans (both axes); a pinch (ctrlKey, which
//: browsers synthesise for it) and a mouse wheel zoom. The decision is made
//: per gesture, not per event (INBOX 1327): a vertical-only frame of a
//: two-finger scroll has no deltaX, and judging frames alone made the board
//: flip between panning and zooming mid-gesture. A gesture is a run of wheel
//: events less than 200ms apart; one trackpad-looking event (a sideways part,
//: or small or fractional pixel deltas, where a wheel notch is a steady 50px
//: or more) makes the rest of it a pan. Fed once per event by both the d3
//: filter and the board's own wheel listener, so the latch is advanced once
//: per event timestamp.
function wbTrackpadPan(event) {
  if (event.ctrlKey || event.metaKey || event.deltaMode !== 0) return false;
  const g = wbBoardState.wheel;
  const now = event.timeStamp || 0;
  if (g.at !== now) {
    if (now - g.at > 200 || now < g.at) g.pad = false;
    g.at = now;
    const dy = Math.abs(event.deltaY);
    //: A mouse notch is a whole multiple of 120 in `wheelDeltaY` whatever the
    //: display scale (the owner, 2026-10-19: the wheel scrolled instead of
    //: zooming; at a fractional Windows scale a notch's deltaY is fractional,
    //: which read as a trackpad). Trackpads report arbitrary values there.
    const raw = Math.abs(event.wheelDeltaY || 0);
    const notch = raw > 0 && raw % 120 === 0 && event.deltaX === 0;
    if (!notch && (event.deltaX !== 0 || (dy > 0 && (dy < 50 || dy % 1 !== 0)))) g.pad = true;
  }
  return g.pad;
}

//: **The companion's press is the companion's** (INBOX 1432, the owner:
//: "when I move the companion the board pans a bit with it as well"). While
//: it is held nothing pans the board, and anything that tries is written to
//: the log with its source, once a press: Chromium here never panned, so the
//: owner's next log names the path.
function wbCompanionHeld(event, why) {
  //: No companion before the faces are in (`charactersLoaded`, lazy-entries.js).
  if (!charactersLoaded || !nmb.grabbed) return false;
  if (nmb.grabbed !== "logged") {
    nmb.grabbed = "logged";
    const line = `board pan refused while the companion was held: ${why} ${event?.type || "code"} ${event?.pointerType || ""} buttons=${event?.buttons ?? ""} on ${event?.target?.tagName || ""}`;
    //: The lag log reaches the server's terminal, which is what the owner pastes.
    if (typeof lagNote === "function") lagNote("companion", 0, line);
    else recordBrowserLog("WARN", [line]);
  }
  return true;
}

function wbZoomFilter(event) {
  if (wbCompanionHeld(event, "filter")) return false;
  //: **A plain wheel zooms about the pointer** (the owner, 2026-10-18: "mouse
  //: scroll on the whiteboard and mindmap still doesnt zoom"; this reverses the
  //: earlier plain-wheel pan, recorded in WHITEBOARD_PLAN decision 24). Ctrl or
  //: a trackpad pinch zooms too; Shift+wheel is left out so the native
  //: listener in initWhiteboard can pan sideways. Panning is a drag, Space, or
  //: the middle button.
  //: Never while the middle button is held: see the plain-wheel listener in
  //: initWhiteboard, the same stray tilt with Ctrl down would zoom mid-pan.
  if (event.type === "wheel") return (event.ctrlKey || event.metaKey || !event.shiftKey) && !wbTrackpadPan(event) && !wbMidPanHeld && (event.buttons & 4) !== 4;
  // Middle button pans from anywhere. `buttons` rather than `button` because
  // mousemove reports the held set, and the drag half of the gesture needs to
  // pass the filter too.
  if (event.button === 1 || (event.buttons & 4) === 4) return true;
  //: Right button pans from bare canvas only (draw.io's convention: a card or
  //: a drawn shape keeps its right-click menu). The press that does not move
  //: past the slop is a click, see the right-press bookkeeping in
  //: initWhiteboard.
  if (event.type === "mousedown" && event.button === 2) return wbIsBareCanvas(event.target);
  //: **Two fingers always navigate; one finger belongs to the tool.**
  //: (UI_MODERNISATION_PLAN Phase 11 item 7, "view and light edit only on a
  //: phone: pan, zoom, select, move".) One finger stays as it was, for the
  //: reason below: a drag while a brush is selected is a stroke, and stealing
  //: it for a pan would make the board undrawable on a tablet. But that left
  //: a phone with no way to move or zoom the board at all unless it first
  //: went and found the Pan tool: measured at 390x844 on a fresh board, a
  //: pinch from 80px to 280px between the fingers with the default Select
  //: tool scaled it by exactly 1.000. Two fingers is what every drawing app
  //: people already know reserves for the camera (Figma, Excalidraw,
  //: Procreate), and it cannot collide with a tool, because no tool here is
  //: drawn with two.
  if (event.type.startsWith("touch")) {
    if (event.touches && event.touches.length > 1) return true;
    //: **And one finger on bare canvas pans with Select too** (INBOX 430,
    //: the owner: "the whiteboard doesn't pan by touch drag", with Select,
    //: the tool a board opens on: measured with `wbtouchpan.js`, a finger
    //: dragged 80px over empty canvas moved it 0px at 390 and 768). On a
    //: touch screen a drag across nothing is how every canvas app moves the
    //: view; a finger that starts on a card still moves the card, and the
    //: area select stays with a mouse or a pen, where a drag across nothing
    //: has always meant it. Drawing tools keep the finger for the stroke.
    if (window.currentTool === "select") return wbIsBareCanvas(event.target);
    return window.currentTool === "pan";
  }
  // Left button: Pan tool, or space held down.
  if (event.button === 0 || event.buttons === 1 || event.buttons === 0) {
    //: **A left drag on empty canvas draws the selection box, on a map and a
    //: board alike** (the owner, 2026-10-30, INBOX 1452: "left click drag
    //: select instead of pan on the whiteboard and mindmap is the way to go,
    //: that way right click hold can be pan and trackpad users two finger
    //: pan"). This reverses INBOX 1445 and 1450, where the plain drag panned
    //: and Shift drew the box; the right button, two trackpad fingers, Space
    //: and the middle button pan.
    return window.currentTool === "pan" || wbSpaceHeld;
  }
  return false;
}

//: Nothing on the board under this point: not a card, a drawn shape (a link
//: is not one, its hit band is canvas), an object or a handle. One test for
//: the touch pan above and the area select in initWhiteboard, which must
//: agree about what a press on nothing is.
function wbIsBareCanvas(target) {
  return !target?.closest?.(
    ".node-card, .sketch-group:not(.wb-link-sketch), .wb-object,"
    + " .wb-sketch-handle-group, .wb-resize-handle",
  );
}

let wbZoom = d3
  .zoom()
  .scaleExtent([0.1, 4])
  .wheelDelta(zoomWheelDelta)
  .filter(wbZoomFilter)
  .on("zoom", handleWbZoom)
  .on("start.companion", (e) => wbCompanionHeld(e.sourceEvent, "zoom"))
  .on("end.shield", wbEndPanShield);
//: Whether the view is where the last "Fit to screen" put it (INBOX 792):
//: the destination, and until when the fit's own animation is running.
const wbFit = { on: false, target: null, until: 0, padding: 64 };
let wbState = { nodes: [], sketches: [], objects: [] };
let wbHintForcedOpen = false; // the "?" help button's override: see renderWhiteboard
let wbInitialized = false;
// ROADMAP.md Tier 2 §11: Select was folded into Pan, with no visible
// "this is selected" state and no way to delete without switching to the
// Delete tool. `{kind: "sketch"|"node", id}` of whatever's currently
// selected, or null. Rotate isn't part of this, `WhiteboardNode` has no
// angle column at all, so rotation needs a real backend change, not a
// frontend-only pass; left as its own separate item.
let wbSelectedItem = null;
// ROADMAP.md Tier 2 §11 / reported directly: "multi-select, holding down
// shift, area select... missing". A set of `"kind:id"` strings, alongside
// (not replacing) `wbSelectedItem`, a lone selection still goes through
// the single-item path (it's what the sketch resize handles and copy/paste
// are built around, and both only ever make sense for exactly one item);
// this is populated only once a second item joins, via shift-click or a
// marquee drag.
const wbMultiSelection = new Set();
// `selectWbTool` is a closure defined inside `initWhiteboard` (it needs that
// scope's `container`/`toolGroup`); this holds the current one so code
// outside it, placing a text box switches back to Select once typed , 
// can still call it, the same shape the delete-refs above already use.
let wbSelectToolRef = null;
// Same shape again, for the marquee/lasso selection drag. Reported directly:
// "there's a permanent selection box on my mindmap", a dashed accent
// rectangle sitting on the canvas at rest, ~330x375, with nothing selected.
//
// Measured, not guessed: the rect is a real `.wb-marquee` element, and it
// leaked three different ways, all of them because the *only* thing that
// removed it was a `pointerup` on the board container. Release the button
// anywhere else (over the top bar, over the left rail, off the window) and
// the pointerup never reaches that listener; a second pointerdown then
// overwrote `wbMarqueeEl` and orphaned the first rect for good. It survives
// a re-render and a board reopen too, because it lives in `#wb-zoom-group`,
// which the render joins by data and never clears wholesale.
//
// So the drag now captures the pointer and ends on `pointerup`,
// `pointercancel` or `lostpointercapture`, and this ref lets Escape, a
// click on empty canvas and every board load sweep up anything that still
// got left behind.
let wbCancelSelectionDragRef = null;
//: Remove any marquee/lasso rectangle still on the canvas, wherever it came
//: from. Safe to call at any time: with no drag in flight there is nothing
//: to find. Deliberately a DOM sweep rather than "remove the element I am
//: holding", the leak this fixes was precisely an element nothing was
//: holding any more.
//: Returns whether a drag was actually in flight, which is what Escape needs
//: to know: taking back a drag is all the key does then.
function wbClearSelectionOverlays() {
  const inFlight = Boolean(wbCancelSelectionDragRef?.());
  for (const stray of document.querySelectorAll(".wb-marquee, .wb-lasso")) stray.remove();
  if (!wbLinkDragActive) wbClearAnchorHints();
  return inFlight;
}
// True only between an eraser mousedown and mouseup, the drawing tools
// leave one mark per click-drag, the eraser is meant to remove everything
// the pointer crosses while held, so it needs a "currently held" flag the
// per-item hover handlers in renderWhiteboard can check.
let wbErasing = false;
// True for the span of an in-progress link drag (dragStart → dragEndNode on
// a card, with a link-type tool selected), lets the plain hover listener
// in initWhiteboard step aside rather than fight the drag's own per-frame
// anchor-hint redraw with a second, slightly-stale one.
let wbLinkDragActive = false;
// Which attached-note cards are expanded past their clamp, keyed by node id
// (the whiteboard attachment, not the note itself), same "remember per card"
// shape as `expandedNotes` on the Notes list.
//
//: **Kept across sessions**, asked for directly: "the state of note objects
//: in the whiteboard and mindmap for if they are expanded or not should be
//: persistant" (INBOX 238). It was a session-only Set, so every reload
//: re-clamped a board someone had spent a minute opening the right cards on.
//:
//: In `localStorage`, which is where every other thing this board remembers
//: about how it is being *looked at* already lives: the grid and snap
//: settings, the alignment guide colours (the background is the board's now),
//: the navigator's open state, the map's perspective. Which cards are open
//: is that kind of fact, not part of the board's content, and keeping it
//: here needs no migration and no round trip on a click.
//:
//: One key rather than one per board: a node id is unique across boards, so
//: nothing is gained by splitting it, and a single list is what makes the
//: cap below able to bound the whole thing.
const WB_EXPANDED_KEY = "wb-expanded-nodes";
//: Enough for any real board, and a ceiling so this cannot grow forever as
//: boards and their cards are deleted. Deleting a board does not come back
//: here to tidy up, and it should not have to: the oldest entries fall off
//: instead, and the only cost of dropping one is a card that opens clamped.
//: The ceiling, WB_EXPANDED_MAX, is a local of wbSaveExpandedNodes (the shared-scope ratchet, L634).

const wbExpandedNodes = new Set(
  (() => {
    try {
      const saved = prefs.json(WB_EXPANDED_KEY, []);
      return Array.isArray(saved) ? saved.filter((id) => Number.isFinite(id)) : [];
    } catch {
      //: A key someone edited by hand, or a storage a browser has switched
      //: off. Neither is worth failing the whole board's script over, and
      //: "every card opens clamped" is the same as the old behaviour.
      return [];
    }
  })()
);

function wbSaveExpandedNodes() {
  const WB_EXPANDED_MAX = 500;
  try {
    //: Newest last, so the slice keeps the cards most recently opened. A
    //: `Set` iterates in insertion order, which is what makes that true
    //: without tracking a timestamp per id.
    const ids = [...wbExpandedNodes].slice(-WB_EXPANDED_MAX);
    if (ids.length !== wbExpandedNodes.size) {
      wbExpandedNodes.clear();
      for (const id of ids) wbExpandedNodes.add(id);
    }
    prefs.set(WB_EXPANDED_KEY, JSON.stringify(ids));
  } catch {
    //: Storage full or blocked. The board still works; it just forgets.
  }
}

//: Show the "Show more" only on the cards that are actually hiding
//: something. Every read happens before every write, deliberately: a loop
//: that measured one card and then changed it would force the browser to
//: lay the whole board out again for the next measurement, which on a two
//: hundred card board is two hundred reflows instead of one.
//:
//: **An expanded card shows "Show less" only when it would hide something**
//: (INBOX 825, the owner: "idk why that show less button is there, all the
//: text is showing"). It used to keep its control whatever it measured, so a
//: card opened once and later sized to hold its text wore a "Show less" that
//: changed nothing. Collapsed, a card is as tall as its stored height, or
//: eight lines when it has none; so an expanded card needs the control only
//: when it stands taller than that (`wbCardMoreNeeded`, node-tested).
function wbSyncCardClamps() {
  const wanted = [];
  for (const card of wbInstances.queryAll(".node-card")) {
    //: A culled card keeps the toggle it had: asking its content for a
    //: height would lay out the very subtree the cull is there to skip.
    if (card.classList.contains("wb-culled")) continue;
    const content = card.querySelector(".wb-card-content");
    const toggle = card.querySelector(".wb-card-more");
    if (!content || !toggle) continue;
    const clamped = content.classList.contains("wb-card-content-clamped");
    wanted.push([toggle, wbCardMoreNeeded({
      clamped,
      scrollH: content.scrollHeight,
      clientH: content.clientHeight,
      //: The toggle's own row is not text: a card is measured without it.
      cardH: card.offsetHeight - (toggle.hidden ? 0 : toggle.offsetHeight),
      floorH: parseFloat(card.style.minHeight) || 0,
      capH: clamped ? 0 : wbNum(getComputedStyle(content).fontSize, 16) * 1.4 * 8,
    })]);
  }
  for (const [toggle, needed] of wanted) toggle.hidden = !needed;
}

function wbCardMoreNeeded({ clamped, scrollH, clientH, cardH, floorH, capH }) {
  if (clamped) return scrollH > clientH + 1;
  return floorH ? cardH > floorH + 1 : scrollH > capH + 1;
}

//: One sync per frame however many renders asked for it. `renderWhiteboard`
//: runs on every state change and a drag can fire several in a frame;
//: measuring once at the end of the frame is both cheaper and more correct,
//: since it reads the layout every one of those renders has settled into.
let wbClampSyncFrame = null;
function wbScheduleCardClampSync() {
  if (wbClampSyncFrame !== null) return;
  wbClampSyncFrame = requestAnimationFrame(() => {
    wbClampSyncFrame = null;
    wbSyncCardClamps();
  });
}

//: The undo and redo stacks, the record depth and the id-remap memory live in whiteboard-undo.js behind `wbStacks`
//: (`.undo`, `.redo`, `.depth`, `.remapSeen`), so no other file shares a top-level `let` with it (L-whiteboard-52).
// Ids currently mid-DELETE. The eraser's mouseenter can fire again for the
// same still-on-screen item before its first DELETE round-trip resolves (a
// slow request, or the pointer wobbling back over it), without this a
// second call pushes a second undo entry and fires a second DELETE for
// something already gone, and the 404 catch then pops the *wrong* undo
// entry off the stack (whatever else was pushed in between).
//: A Set that can say when it is empty (audit B9): Undo and Redo wait on it, so
//: an Undo pressed while a DELETE is in flight cannot restore a row the server
//: then deletes, and a delete that fails has dropped its entry before Undo runs.
class WbPendingSet extends Set {
  #waiting = [];
  delete(key) {
    const had = super.delete(key);
    if (!this.size) for (const resolve of this.#waiting.splice(0)) resolve();
    return had;
  }
  settled() {
    return this.size ? new Promise((resolve) => this.#waiting.push(resolve)) : Promise.resolve();
  }
}
const wbDeleting = new WbPendingSet();

//: **All three layers pan the same way** ("shapes and links lag behind"): the
//: SVG groups take a CSS transform like the cards, so the compositor moves
//: them. Safe because every drag resolves points through `getScreenCTM()`,
//: measured to fold a CSS transform in identically; `transform-origin: 0 0`
//: is set in CSS beside the layers. The layer transform is written on every
//: event (the compositor paints the last one anyway); grid variables, the
//: selection bar and the navigator wait for one frame (PLAN.md P2;
//: `panlag.js`). A frame of latency is not measurable on this box.
let wbZoomFrame = 0;
let wbZoomPending = null;

//: **Why the pan transform is on the two `<svg>` roots and not on the `<g>`
//: inside them** (INBOX 183: "the note objects are fine, but all shapes, lines
//: and connections lagg behind in position and arent synched").
//:
//: Two earlier passes moved these three transforms into one place and gave
//: them one `will-change`, and the report came back both times, because
//: `will-change: transform` on an SVG `<g>` promotes nothing: Chromium cannot
//: composite an element inside an SVG fragment, it paints the whole fragment
//: into whatever layer the `<svg>` root lives in. Measured through the CDP
//: layer tree on a live board (`scratchpad/ui-sweeps/panlayers.js`): a note
//: card was its own composited layer while `svg#wb-svg-layer`, which holds
//: every shape, line and stroke, was not in the layer list at all. So a pan
//: moved the cards on the compositor and re-rastered the shapes on the main
//: thread, and a frame can be presented with the card already moved and the
//: shape's new tiles not yet ready. That is the report, exactly: the notes are
//: fine and everything drawn lags.
//:
//: The transform therefore has to sit on an element that *can* be composited,
//: which is the `<svg>` root. The one thing that changes is clipping: a `<g>`
//: translated inside its viewport is clipped at the viewport, a translated
//: root takes its viewport with it, so the roots are `overflow: visible` and
//: the container's own `overflow: hidden` does the clipping instead. Probed
//: before it was written (`scratchpad/ui-sweeps/panprobe.js`): a rectangle
//: 2200px outside the viewport, panned in, paints (pixel 255,0,255 at its
//: centre) and hit-tests (`elementFromPoint` returns it).
//:
//: The consequence for every other reader: `#wb-svg-layer`'s bounding rect is
//: no longer the canvas origin, it moves with the pan. `wbCanvasOriginRect`
//: below is that origin, and it is the container's own box, which is the same
//: rectangle the SVG used to report and cannot ever move.
function wbApplyZoomTransform(t) {
  const css = `translate(${t.x}px, ${t.y}px) scale(${t.k})`;
  d3.select(wbInstances.layer("wb-html-layer")).style("transform", css);
  d3.select(wbInstances.layer("wb-svg-layer")).style("transform", css);
  d3.select(wbInstances.layer("wb-overlay-layer")).style("transform", css);
}

//: The board's origin in screen coordinates: where board 0,0 sits before the
//: pan transform is applied. Every screen-to-board conversion in this file
//: subtracts the live d3 transform itself, so what it needs here is the
//: untransformed canvas box, and since the swap above that is the container
//: rather than the SVG (which now moves).
//:
//: **Measured once per gesture** (MINDMAP_PLAN.md §13a). Every frame of a
//: drag writes SVG geometry (`d` on each moved edge) before anything asks
//: for this, and an SVG attribute write dirties layout, so each frame's first
//: `getBoundingClientRect` paid for a fresh layout of the whole board. On a
//: 500-topic branch drag that single call was the largest cost left on the
//: path once the topic measurements and the element lookups were cached.
//:
//: The canvas box cannot move during a gesture: a pointer is down on it. It
//: can move between gestures (a panel opens, the window resizes, the page
//: scrolls, full screen is toggled), so the cache is dropped at the start of
//: every gesture as well as at the end of one, and on resize and scroll.
let wbCanvasRectCache = null;

function wbClearCanvasRectCache() {
  wbCanvasRectCache = null;
  wbCanvasOriginCache = null;
}

function wbCanvasOriginRect() {
  if (wbCanvasRectCache) return wbCanvasRectCache;
  //: Null until the board's template is stamped (row 21): a window resize before
  //: the first board open must not throw (e2e editor-keys at 700 px).
  const rect = wbInstances.container()?.getBoundingClientRect() ?? null;
  wbCanvasRectCache = rect;
  return rect;
}

//: **The one conversion from a point on screen to a point on the board**
//: (INBOX 664: "Placing coordinates of templates on the mindmap and
//: whiteboard could be improved (little off from the cursor)"). Nine places
//: wrote `(clientX - rect.left - t.x) / t.k` by hand; they now all come here,
//: so a correction made once is made for every drop, paste and pointer.
//:
//: `origin` is where the layers' 0,0 sits on screen before the pan: the
//: container's border box, plus its border (the layers are placed in the
//: padding box), less any scroll of the container (an `overflow: hidden` box
//: can still be scrolled, by a `focus()` on something inside it), and
//: `scale` is any CSS transform an ancestor puts on the whole canvas, read as
//: the drawn width over the laid-out width. A device pixel ratio needs no
//: term: `clientX` and the rect are both in CSS pixels. Pure, so the node
//: test can hold it (tests/test_wb_drop_place.py).
function wbScreenToBoard(clientX, clientY, origin, t) {
  const s = origin.scale || 1;
  return [((clientX - origin.left) / s - t.x) / t.k, ((clientY - origin.top) / s - t.y) / t.k];
}

//: The origin `wbScreenToBoard` wants, cached with the rect it is read from
//: and dropped with it (`wbClearCanvasRectCache`), so a drag pays for it once.
let wbCanvasOriginCache = null;

function wbCanvasOrigin() {
  if (wbCanvasOriginCache && wbCanvasRectCache) return wbCanvasOriginCache;
  const el = wbInstances.container();
  const rect = wbCanvasOriginRect();
  let scale = el.offsetWidth ? rect.width / el.offsetWidth : 1;
  //: `offsetWidth` is rounded to a whole pixel and the rect is not, so an
  //: unscaled canvas reads 0.9996 or so: only a real transform counts.
  if (!Number.isFinite(scale) || Math.abs(scale - 1) < 0.01) scale = 1;
  wbCanvasOriginCache = {
    left: rect.left + (el.clientLeft - el.scrollLeft) * scale,
    top: rect.top + (el.clientTop - el.scrollTop) * scale,
    scale,
  };
  return wbCanvasOriginCache;
}

//: The inverse, for a thing placed on screen at a board point (the paste
//: chip). Pure, with `wbScreenToBoard`, so one round trip holds both.
function wbBoardToScreen(x, y, origin, t) {
  const s = origin.scale || 1;
  return [origin.left + (x * t.k + t.x) * s, origin.top + (y * t.k + t.y) * s];
}

function wbClientToBoard(clientX, clientY) {
  return wbScreenToBoard(clientX, clientY, wbCanvasOrigin(), d3.zoomTransform(wbInstances.container()));
}

window.addEventListener("pointerdown", wbClearCanvasRectCache, true);
window.addEventListener("pointerup", wbClearCanvasRectCache, true);
window.addEventListener("pointercancel", wbClearCanvasRectCache, true);
window.addEventListener("resize", wbClearCanvasRectCache);
window.addEventListener("scroll", wbClearCanvasRectCache, true);
//: And whenever nothing is being dragged, which closes the one gap the five
//: above leave: a keyboard shortcut can open a panel and move the canvas
//: without any pointer event at all, and the next read would have been taken
//: against the box the canvas used to have. `buttons` is 0 for a hover and
//: non-zero for every frame of a gesture, so this costs a hovering pointer
//: exactly what it cost before the cache and costs a drag nothing.
window.addEventListener(
  "pointermove",
  (event) => {
    if (!event.buttons) wbClearCanvasRectCache();
  },
  true
);

//: **The pan shield goes up on the first move of a pointer pan** (MINDMAP_PLAN
//: 13a-view; the rule and its reasons are on `.wb-pan-shield`). On the move,
//: not the press: a press that never moves is a click, and its click has to
//: land on whatever was under it rather than on the shield. A class on the
//: container is cheap here only because no rule for the container itself
//: reads it; the one rule that does styles the shield alone.
function wbStartPanShield(e) {
  const type = e.sourceEvent?.type;
  if (type !== "mousemove" && type !== "pointermove") return;
  const el = wbInstances.container();
  if (el && !el.classList.contains("wb-hand-pan")) el.classList.add("wb-hand-pan");
}

function wbEndPanShield() {
  wbInstances.container()?.classList.remove("wb-hand-pan");
  //: The bar was placed from held measurements all through the pan; place it
  //: once with real ones when the pan has been idle, so its clearance from the
  //: handle is exact again. **Not at every gesture end:** a wheel gesture ends
  //: whenever frames come slower than d3's 150 ms, so on a heavy board every
  //: step ended one, and a full measure per step is the lag this removes
  //: (measured 2026-10-12: 19 ends in 20 steps, 72 ms each).
  if (!wbAddGate.panBarHold) return;
  clearTimeout(wbAddGate.panBarTimer);
  wbAddGate.panBarTimer = setTimeout(() => {
    wbAddGate.panBarTimer = 0;
    if (wbAddGate.panBarHold) wbUpdateSelectionBar();
  }, 250);
}

//: **No blur over moving pixels** (the owner, 2026-10-12: a trackpad pan of a
//: mind map "slow and laggy" with a tool panel showing). The panels over a
//: board are glass, and a backdrop blur samples what is under it, which moves
//: every pan frame: five panels re-blurred per frame, 85 frames in 2 s against
//: 117 with Glass off (tests/test_wb_pan_blur.py). The blur is dropped while
//: the board moves (`#wb-canvas-view.wb-moving`, library-lazy.css) and comes
//: back this long after the last pan or zoom step.
function wbMarkMoving() {
  //: Local, not a top-level name (the shared-scope ratchet, L634).
  const WB_MOVING_MS = 180;
  const view = document.getElementById("wb-canvas-view");
  if (view && !view.classList.contains("wb-moving")) view.classList.add("wb-moving");
  clearTimeout(wbMarkMoving.timer);
  wbMarkMoving.timer = setTimeout(() => view?.classList.remove("wb-moving"), WB_MOVING_MS);
}

function handleWbZoom(e) {
  wbMarkMoving();
  //: A view that is not where the last fit put it is not "fitted" any more,
  //: so a panel opening does not pull it back (`wbRefitIfFitted`).
  if (wbFit.on && (e.sourceEvent || (Date.now() > wbFit.until && !wbSameView(e.transform, wbFit.target)))) wbFit.on = false;
  wbStartPanShield(e);
  wbApplyZoomTransform(e.transform);
  wbZoomPending = e.transform;
  if (wbZoomFrame) return;
  wbZoomFrame = requestAnimationFrame(wbZoomFrameWork);
}

//: Everything a pan or zoom costs beyond the transform itself, once a frame.
function wbZoomFrameWork() {
  wbZoomFrame = 0;
  const t = wbZoomPending;
  wbZoomPending = null;
  if (!t) return;
  //: **The canvas size is read once, before anything here writes** (INBOX
  //: 431). The grid writes three custom properties on the container and the
  //: cull toggles classes on the items it brings into view; a size read
  //: after either forced the browser to restyle the board inside this
  //: callback, and the overview read it last, after both. Traced on a
  //: 150-topic map at a 4x throttle, an overview drag spent 1.3s of its 4.7s
  //: in that forced restyle. Read first, the restyle happens once, in the
  //: frame's own rendering step.
  //:
  //: An overview drag measured the canvas at its press, and the canvas
  //: cannot change size while a pointer is held on the overview.
  const container = wbInstances.container();
  const drag = wbNavState.drag;
  const size = drag
    ? { width: drag.width, height: drag.height }
    : container ? { width: container.clientWidth, height: container.clientHeight } : null;
  wbSyncGridToTransform(t);
  wbFmtState.opts?.drawRulers(t);
  if (typeof nameMarkBuddyCanvasZoom === "function") nameMarkBuddyCanvasZoom(t.k);
  //: In the same frame as the transform it answers, so a topic panned into
  //: view is drawn on the frame it arrives in rather than one later.
  //:
  //: **A zoom step culls only when the window has left what was drawn**
  //: (L-mindmap-17). The cull draws half a window past every side, and a
  //: pinch step is about 1.18x, so most steps of a zoom show nothing the last
  //: cull did not already draw; culling each one anyway hid and showed edges
  //: at the margin every step (8 to 16ms a step at 500 topics). The full
  //: cull runs once when the zoom settles (`wbZoomSettle`). A pan culls every
  //: frame as before: it is what brings new ground into view.
  const scaling = t.k !== wbZoomSettle.k;
  wbZoomSettle.k = t.k;
  wbCullNow(t, size, scaling);
  if (scaling) wbZoomSettle();
  clearTimeout(wbAddGate.panBarTimer);
  wbAddGate.panBarTimer = 0;
  wbUpdateSelectionBar(true);
  //: The format bar of a topic or text box being edited rides the board
  //: with it (INBOX 817), in the same frame.
  if (typeof selectionBarState === "object" && (selectionBarState.textarea?.id === "wb-topic-edit" || selectionBarState.textarea?.id === "wb-text-edit")) selectionBarSync();
  // The overview's viewport rectangle is only true for one transform, so it
  // moves with every pan and zoom; the items in it do not, and are not
  // redrawn (`wbNavigatorUpdateViewport`). It returns immediately when the
  // overview is closed, which is the common case.
  wbNavigatorUpdateViewport(t, size);
  wbShowZoomLevel(t.k);
}

//: The zoom dock says the level (INBOX 1352 gap 5: three icons and no
//: number). Written only when the rounded percent changes, to an element
//: found once, so a pan costs nothing here.
function wbShowZoomLevel(k) {
  const pct = Math.round(k * 100);
  const zl = (wbShowZoomLevel.state ||= { pct: -1, el: null });
  if (pct === zl.pct) return;
  zl.pct = pct;
  zl.el ||= document.getElementById("wb-zoom-level");
  if (!zl.el) return;
  //: A typeable number with a dropdown (INBOX 1694 b, value-field.js), built on the first paint: Enter zooms about the centre.
  zl.field ||= valueField(zl.el, {
    value: pct,
    min: 10,
    max: 400,
    label: "Zoom percent",
    format: (v) => `${Math.round(v)}%`,
    presets: [25, 50, 75, 100, 150, 200, 400, { label: "Fit", run: () => wbZoomToFit() }],
    onCommit: (v) => {
      const container = wbInstances.container();
      if (container) d3.select(container).transition().duration(160).call(wbZoom.scaleTo, v / 100, wbZoomAnchor({ usePointer: false }));
    },
  });
  zl.field.set(pct);
  wbFmtState.effects?.refreshStatus();
}

//: Run a queued zoom frame now rather than on the next one: for a transform
//: set from inside an animation frame (the overview's drag), whose own frame
//: would otherwise land the grid, the cull and the rectangle one frame late.
function wbFlushZoomFrame() {
  if (!wbZoomFrame) return;
  cancelAnimationFrame(wbZoomFrame);
  wbZoomFrameWork();
}

//: **Only what is near the window is drawn** (MINDMAP_PLAN.md 13a-view,
//: INBOX 312). Every card, text box and topic on the board is a DOM element
//: under the layer the pan moves, and a topic is nineteen of them: a
//: 500-topic map is eleven thousand elements, and every restyle, hit test and
//: repaint of the layer walked all of them whether or not one was on screen.
//: Measured on that map, a tool switch restyled the board in 120ms; with the
//: topics off screen culled, 40ms.
//:
//: **`content-visibility: hidden`, not `display: none` and not detaching.**
//: A culled item keeps its box, so everything that measures an item (the
//: export, `wbItemBBox`, `wbMapSpillsOffCanvas`, a drag's drop target) reads
//: the same numbers it always did; `contain-intrinsic-size: auto` on the
//: items (07-whiteboard-misc.css) is what makes the height the one it last
//: drew at. Only what is inside it stops being styled, laid out, painted and
//: hit. `content-visibility: auto` was measured first and culled nothing
//: here: the browser's own on-screen test does not see through the pan's
//: transform, so all 500 topics stayed live.
//:
//: **What is never culled:** the selection, anything being dragged, and
//: anything holding focus, which is the text being typed into. Those are the
//: things a gesture is reaching for, and they can sit off screen: a new
//: topic opens its editor before the view has moved to it.
//:
//: The margin is half the window on every side, so a pan draws what it is
//: about to show a whole half-screen before it arrives, and the cull runs
//: once per pan frame, in the frame's own rAF.
const WB_CULL_MARGIN = 0.5;
let wbCullFrame = 0;
//: Non-zero while an animated fit runs: the cull has drawn the fit's
//: destination and does nothing until it lands (`wbZoomToFit`).
let wbCullHeld = 0;
let wbCullHoldCount = 0;

function wbScheduleCull() {
  if (wbCullFrame) return;
  wbCullFrame = requestAnimationFrame(() => {
    wbCullFrame = 0;
    //: **The canvas size from the gesture's cached box, never a fresh read**
    //: (INBOX 445). A drag schedules this once a frame after it has written
    //: every moved item's transform and every moved line's `d`, so reading
    //: `clientWidth` here forced the browser to lay the board out again
    //: inside the callback: measured on a 61-topic branch drag, 1.9ms a
    //: frame, the largest single cost of the drag. `wbCanvasOriginRect` is
    //: measured once per gesture, and the canvas cannot change size while a
    //: pointer is down on it.
    const rect = wbCanvasOriginRect();
    if (rect) wbCullNow(undefined, { width: rect.width, height: rect.height });
  });
}

//: Run once a zoom has had no scale change for `wbZoomSettle.ms`: the
//: one full redraw a zoom gets (the cull here; the grips' true size in
//: `wbSyncGridToTransform`, which shares the wait).
function wbZoomSettle() {
  clearTimeout(wbZoomSettle.timer);
  wbZoomSettle.timer = setTimeout(() => wbCullNow(), wbZoomSettle.ms);
}
wbZoomSettle.ms = 250;

//: `unlessDrawn`: nothing to do when the window, at this transform, is inside
//: the ground the last cull drew (`wbCullNow.drawn`, board units).
function wbCullNow(transform, size, unlessDrawn = false) {
  if (wbCullHeld) return;
  const container = wbInstances.container();
  const layer = wbInstances.layer("wb-html-layer");
  if (!container || !layer) return;
  //: `size` when the caller has read it before writing anything this frame
  //: (`wbZoomFrameWork`); a read here otherwise.
  const w = size ? size.width : container.clientWidth;
  const h = size ? size.height : container.clientHeight;
  //: A hidden board (another tab, the boards gallery) has no window to cull
  //: against; leave it as it is rather than culling everything.
  if (!w || !h) return;
  const t = transform || d3.zoomTransform(container);
  const k = t.k || 1;
  const drawn = wbCullNow.drawn;
  if (unlessDrawn && drawn && -t.x / k >= drawn.x0 && (w - t.x) / k <= drawn.x1 && -t.y / k >= drawn.y0 && (h - t.y) / k <= drawn.y1) return;
  const mx = w * WB_CULL_MARGIN;
  const my = h * WB_CULL_MARGIN;
  const x0 = (-mx - t.x) / k;
  const x1 = (w + mx - t.x) / k;
  const y0 = (-my - t.y) / k;
  const y1 = (h + my - t.y) / k;
  wbCullNow.drawn = { x0, x1, y0, y1 };
  //: A box from what the datum says rather than from the element: reading
  //: a box would flush layout on every pan frame. Padded by half its larger
  //: side, so a rotated item's corners and a card taller than its stored
  //: height are both inside it.
  const outside = (x, y, bw, bh) => {
    const pad = Math.max(bw, bh) / 2;
    return x + bw + pad < x0 || x - pad > x1 || y + bh + pad < y0 || y - pad > y1;
  };
  const focused = document.activeElement;
  //: **Too small on screen for its grips, it drags** (L-whiteboard-15). The
  //: resize grips keep ten screen pixels at every zoom, so on a 500-box board
  //: at the fit zoom (0.23) a 42 by 16 px text box was mostly grip and a
  //: press on it resized nothing and moved nothing (wb500perf.js). Below
  //: this size the grips are absent (07-whiteboard-misc.css); zoom in, or
  //: the Format panel's size fields, to resize it.
  const WB_TINY_SCREEN_W = 40;
  const WB_TINY_SCREEN_H = 28;
  //: A dragged branch's topics sit in its layer for the gesture (`wbMapDragLayer.open`).
  const dragLayer = wbMapDragLayer.live?.layer?.el;
  for (const el of dragLayer ? [...layer.children, ...dragLayer.children] : layer.children) {
    const d = el.__data__;
    if (!d || typeof d.x !== "number") continue;
    const tiny = (d.width || WB_CARD_DEFAULT_SIZE.w) * k < WB_TINY_SCREEN_W || (d.height || WB_CARD_DEFAULT_SIZE.h) * k < WB_TINY_SCREEN_H;
    //: Mid-zoom the marks wait for the settle's full cull: crossing the size flips hundreds of
    //: topics' grips on one step (mapperf 500, worst zoom 29 to 96ms).
    if (!unlessDrawn && el.classList.contains("wb-tiny") !== tiny) el.classList.toggle("wb-tiny", tiny);
    const keep =
      el.classList.contains("wb-selected") ||
      el.classList.contains("dragging") ||
      (focused && focused !== document.body && el.contains(focused));
    const bw = d.width || WB_CARD_DEFAULT_SIZE.w;
    const bh = d.height || WB_CARD_DEFAULT_SIZE.h;
    const cull = !keep && outside(d.x, d.y, bw, bh);
    if (el.classList.contains("wb-culled") !== cull) el.classList.toggle("wb-culled", cull);
  }
  //: A map's tree lines, by the box of their two ends: a line with one end on
  //: screen is on screen. `display: none` is right for these: nothing ever
  //: measures a line's element, only its ends.
  const edges = wbInstances.query("#wb-zoom-group .wb-map-edges");
  const cache = edges?._wbMapEdges;
  if (cache instanceof Map && cache.size) {
    const byId = new Map((wbState.objects || []).map((o) => [o.id, o]));
    for (const [key, held] of cache) {
      const cut = key.indexOf(":");
      const a = byId.get(Number(key.slice(0, cut)));
      const b = byId.get(Number(key.slice(cut + 1)));
      if (!a || !b) continue;
      const left = Math.min(a.x, b.x);
      const top = Math.min(a.y, b.y);
      const right = Math.max(a.x + (a.width || 0), b.x + (b.width || 0));
      const bottom = Math.max(a.y + (a.height || 0), b.y + (b.height || 0));
      const cull = outside(left, top, right - left, bottom - top);
      if (held.wrap.classList.contains("wb-culled") === cull) continue;
      //: A line a drop left undrawn off screen is drawn as it comes on (`wbUpdateMapEdges`, `onScreen`).
      if (!cull && held.path._wbMoved) wbUpdateMapEdges.drawHeld([held.path]);
      held.wrap.classList.toggle("wb-culled", cull);
    }
  }
}

window.addEventListener("resize", wbScheduleCull);

//: The grid's spacing in board coordinates. Scaled by the zoom so a square
//: stays a square of the *board*, not of the screen, panning and zooming
//: move the ruling with the content, which is the whole point of a grid you
//: can snap to.
//: A board may set its own (Format panel, Board: `background.grid_size`); `wbApplyBackground` assigns it, so snap,
//: the nudge and the drawn grid all read the one value.
let WB_GRID_SPACING = 24;

//: A card's default size before a resize ever sets `width`/`height`
//: explicitly: the CSS auto-size every card used before resize existed,
//: and the same figure this file's own drop-centring/link-anchor math has
//: assumed all along (see the drop handler and `dragStart`'s own comments).
const WB_CARD_DEFAULT_SIZE = { w: 250, h: 150 };

function wbSyncGridToTransform(transform) {
  const el = wbInstances.container();
  if (!el) return;
  const t = transform || d3.zoomTransform(el);
  el.style.setProperty("--wb-grid-size", `${WB_GRID_SPACING * t.k}px`);
  el.style.setProperty("--wb-grid-offset-x", `${t.x}px`);
  el.style.setProperty("--wb-grid-offset-y", `${t.y}px`);
  //: **And the inverse scale, for anything that must not grow with the board.**
  //: The grid is not the only thing that has to be told what the zoom is. A
  //: grip is a target for a finger rather than part of the drawing, and
  //: measured on a real board, every handle on this canvas was 20px across at
  //: 2x and 5px at 0.5x: the card handles ride `#wb-html-layer`'s CSS scale,
  //: and the sketch and link handles are SVG geometry inside `#wb-zoom-group`,
  //: so both kinds are multiplied by `k`. One `scale(1 / k)` on the handle
  //: cancels that exactly, which is what `--wb-inv-zoom` is for (see the grip
  //: rules in 07-whiteboard-misc.css).
  //:
  //: Published here, once per zoom frame, rather than read per element:
  //: `d3.zoomTransform` per handle would put work back into the pan path this
  //: file has twice been cleared of, and one custom property reaches all
  //: twenty-odd of them through inheritance.
  //: **Only when the scale has changed, and once the zoom has come to rest.**
  //: This one inherits (every grip reads it), so each write re-styles the
  //: whole board: traced on a 60-topic map, a ctrl-wheel zoom spent 1,448ms
  //: re-styling 1,713 elements per step. A pan does not change `k` and
  //: writes nothing; a zoom writes once, 120ms after its last step, so the
  //: grips ride the board's scale for the length of the gesture and snap to
  //: their true size when it stops.
  //: Per board (L-whiteboard-56): an embed keeps its own scale, value and timer.
  const inst = wbInstances.active;
  const inv = String(1 / (t.k || 1));
  clearTimeout(inst.invTimer);
  if (inst.invZoom === inv) return;
  //: **"Stops" is the zoom's settle, not a 120ms gap** (L-mindmap-17). One
  //: publish re-styles every grip on the board (2,000 at 500 topics, 70 to
  //: 180ms), and a slow pinch on a big map has steps more than 120ms apart,
  //: so the publish landed inside the gesture: mapperf's worst zoom step at
  //: 500 topics, 320ms, was one. It waits for the same quiet as the cull.
  inst.invTimer = setTimeout(() => wbPublishInvZoom(el, inv, inst), wbZoomSettle.ms);
}

//: **Written onto the grips, not inherited down the whole board** (INBOX
//: 431). Even once per zoom, the write above re-styled every element under
//: the container, because an inherited custom property changed at the top of
//: it: measured on a 150-topic map (4,212 elements) at a 4x throttle, 290ms
//: for one write, and the largest single frame of every fit, the overview's
//: included. A rule in a constructed sheet that names the grips sets the
//: property on them alone, so a change re-styles what matches it: 40ms on
//: the same map. A constructed sheet because the CSP refuses an injected
//: `<style>` (as `applyCustomCss` in settings.js found). The selectors are
//: every rule in 07-whiteboard-misc.css that reads the property, and
//: `tests/test_wb_navigator_cost.py` keeps the two lists the same.
const WB_INV_ZOOM_GRIPS = [
  ".wb-object-frame .wb-frame-title",
  ".wb-map-edge-end",
  ".wb-comment-pin",
  ".wb-lock-pin",
  ".wb-resize-handle",
  ".wb-rotate-handle",
  ".wb-sketch-resize-handle",
  ".wb-link-endpoint-handle",
  ".wb-link-bend-handle",
  ".wb-link-waypoint-handle",
  ".wb-link-waypoint-add",
  ".wb-clone-grip",
  ".wb-map-edge-handle",
  ".wb-map-resize-grip",
  ".wb-map-actions",
  //: Their small-zoom and downward-flow placements (L360) read it too.
  "#whiteboard-container[data-wb-zoom-far] .wb-map-actions",
  "#whiteboard-container .wb-map-node[data-flow=down] .wb-map-actions",
  ".wb-embed[data-wb-zoom-far] .wb-map-actions",
  ".wb-embed .wb-map-node[data-flow=down] .wb-map-actions",
  ".wb-map-collapse",
  ".wb-map-count",
  ".wb-sketch-rotate-handle",
  ".wb-rotate-handle-stem",
];
let wbInvZoomSheet = null;

//: **The board's layers are rasterised again once a zoom has settled**
//: (INBOX 791, "labels look pixelated"). A layer promoted with `will-change:
//: transform` keeps the raster it was first painted at, and a compositor
//: that does not re-raster on a later scale change draws a link label, which
//: is SVG text, as a stretched bitmap. Dropping the hint for one frame and
//: restoring the sheet's own makes the next paint at the current scale; all
//: three go in the same frame so the pan pipelines stay together.
function wbRefreshRaster(el) {
  const layers = ["wb-html-layer", "wb-svg-layer", "wb-overlay-layer"]
    .map((id) => el.querySelector(`#${id}, [data-wb-layer="${id}"]`)).filter(Boolean);
  for (const layer of layers) layer.style.willChange = "auto";
  requestAnimationFrame(() => {
    for (const layer of layers) layer.style.willChange = "";
  });
}

function wbPublishInvZoom(el, inv, inst = wbInstances.page) {
  inst.invZoom = inv;
  wbRefreshRaster(el);
  //: Below half zoom a topic's link button goes (INBOX 816): `inv` is 1 / zoom.
  el.toggleAttribute("data-wb-zoom-far", Number(inv) > 2);
  //: The clone arrows stand a fixed number of screen pixels off their sides.
  wbLayoutCloneGrips();
  const supported =
    typeof CSSStyleSheet !== "undefined"
    && "replaceSync" in CSSStyleSheet.prototype
    && "adoptedStyleSheets" in Document.prototype;
  if (!supported) {
    el.style.setProperty("--wb-inv-zoom", inv);
    return;
  }
  if (!wbInvZoomSheet) {
    wbInvZoomSheet = new CSSStyleSheet();
    document.adoptedStyleSheets = [...document.adoptedStyleSheets, wbInvZoomSheet];
  }
  wbInvZoomSheet.replaceSync(wbInvZoomRules());
}

//: The page board's rule, then one per embed, scoped to its box: `:is()` takes
//: its most specific argument's weight (an id), so an embed's own scale wins
//: over the page's inside it (L-whiteboard-56).
function wbInvZoomRules() {
  const grips = WB_INV_ZOOM_GRIPS.join(", ");
  return wbInstances.list.map((inst) => (inst.container
    ? `[data-wb-embed="${inst.key}"] :is(${grips}) { --wb-inv-zoom: ${inst.invZoom}; }`
    : `${grips} { --wb-inv-zoom: ${inst.invZoom}; }`)).join("\n");
}

function wbGridType() {
  return prefs.get("wb-grid", null) || "none";
}

function wbSnapOn() {
  // Snapping without a visible grid is a mystery, not a feature, the
  // toggle stays honest by only applying while a grid is actually shown.
  return prefs.get("wb-snap", null) === "on" && wbGridType() !== "none";
}

//: Round a board coordinate to the nearest grid intersection, when snap is
//: on. A no-op otherwise, so every call site can use it unconditionally.
//: `bypass` (asked for directly: Alt held during a drag temporarily
//: releases the grid lock, the same convention Figma/Illustrator use) skips
//: the rounding for just this one call, without needing the snap toggle
//: itself touched.
//: Not a finite number is 0 (B33): NaN is invalid where used, not where set.
function wbSnap(value, bypass) {
  if (!Number.isFinite(value)) return 0;
  return wbSnapOn() && !bypass ? Math.round(value / WB_GRID_SPACING) * WB_GRID_SPACING : value;
}

//: Smart alignment guides while dragging (asked for directly: "the
//: recognisable popup alignment guides... draw.io and Microsoft
//: PowerPoint have... dotted alignment rule guides... subtly snap"). Scoped
//: to cards and objects as both the dragged item and the things it aligns
//: against: sketches are freehand strokes, not the kind of rectangular
//: "object" this pattern is normally drawn against in the apps it's
//: modelled on. Independent per axis: an X-axis snap and a Y-axis snap can
//: both fire on the same frame (a corner aligning with another item's
//: corner), each drawing its own guide line.
//: Screen pixels, not board units: `wbAlignTol` divides by the zoom, so the
//: pull is the same distance under the pointer at 20% and at 400%.
const WB_ALIGN_SNAP_PX = 6;
function wbAlignTol() {
  const container = wbInstances.container();
  const k = container ? d3.zoomTransform(container).k : 1;
  return WB_ALIGN_SNAP_PX / (k || 1);
}

//: A box's axis-aligned bounds once rotated about its centre, so a tilted
//: card or object aligns by the edges it shows. Pure (node-tested).
function wbRotatedBounds(x, y, w, h, deg) {
  if (!deg) return { x, y, w, h };
  const rad = (deg * Math.PI) / 180;
  const cos = Math.abs(Math.cos(rad)), sin = Math.abs(Math.sin(rad));
  const rw = w * cos + h * sin, rh = w * sin + h * cos;
  return { x: x + w / 2 - rw / 2, y: y + h / 2 - rh / 2, w: rw, h: rh };
}

//: **The other items' boxes, gathered once per gesture, not once per pointer
//: move** (INBOX 114, "laggy to drag and pan", three passes unattributed).
//: Measured on an 80-card board: `wbAlignmentGuides` cost 7.67ms per move,
//: because every move ran a `querySelector` and an `offsetWidth` read per
//: card, and the first of those reads after the dragged card's transform
//: write forces a layout of the whole board. A mouse reports at 120Hz or
//: more, so that was a frame's budget spent before anything was painted. The
//: other cards do not move while one is dragged, so their boxes are read
//: once, on the first move, and reused until the pointer is released.
let wbGuideBoxCache = null;

//: `excludeKeys` is a set of `wbMultiKey` strings, because what has to be
//: left out of the targets is *everything being dragged*, which is one item
//: for a plain drag and the whole selection for a group one. It used to be a
//: single kind and id, so a group drag would have snapped its own members to
//: each other, which is why group drags had no guides at all.
//:
//: **`at` is the box being moved or sized, and it picks which frames' margins
//: count** (INBOX 1563): a frame's four margin lines (`wbGuideBoxes.walls`)
//: are targets only for a box whose centre is inside that frame, so a card
//: far outside never snaps to a line it cannot see the use of.
function wbGuideBoxes(excludeKeys, at = null) {
  //: The board's Guides switch (Format > Board): off, nothing offers a line to snap to or draw.
  if (wbBoardBackground().guides === false) return [];
  const key = excludeKeys ? [...excludeKeys].sort().join(",") : "";
  if (wbGuideBoxCache && wbGuideBoxCache.key === key) return wbGuideBoxes.within(wbGuideBoxCache.boxes, at);
  const boxes = [];
  for (const [kind, listName] of [["node", "nodes"], ["object", "objects"]]) {
    for (const item of wbState[listName] || []) {
      if (excludeKeys && excludeKeys.has(wbMultiKey(kind, item.id))) continue;
      if (wbItemHidden(kind, item)) continue;
      const box = wbItemBBox(kind, item);
      if (!box) continue;
      const deg = wbItemRotation(kind, item);
      if (deg) {
        const r = wbRotatedBounds(box.minX, box.minY, box.maxX - box.minX, box.maxY - box.minY, deg);
        boxes.push({ minX: r.x, minY: r.y, maxX: r.x + r.w, maxY: r.y + r.h });
      } else boxes.push(box);
    }
  }
  //: **The drawn shapes too** (wb-phase2 step 4): a flowchart's boxes are
  //: sketches, so a shape dragged among them had nothing to line up with.
  //: A shape is a sketch with a `shape` or a closed path; a freehand stroke
  //: and a connector are not targets (draw.io aligns to shapes, not ink).
  for (const sketch of wbState.sketches || []) {
    if (excludeKeys && excludeKeys.has(wbMultiKey("sketch", sketch.id))) continue;
    const parsed = wbSketchParsedData(sketch);
    if (!parsed || !(parsed.shape || wbShapeLabelKind(parsed)) || wbItemHidden("sketch", sketch)) continue;
    const box = wbItemBBox("sketch", sketch);
    if (box) boxes.push(box);
  }
  //: **A frame's margins are targets inside it** (INBOX 1563, the owner: "in
  //: these frames, I cant align objects with a margin or like the header
  //: text or have nice spacing between them"). Four zero-thickness boxes, the
  //: inner left, right, top and bottom lines at the frame's own padding. They
  //: are ordinary boxes to the alignment and the equal-spacing passes, so a
  //: card lands on the margin, or the same distance from it as from its
  //: neighbour, with the guide the canvas already draws.
  for (const frame of wbState.objects || []) {
    if (frame.kind !== "frame" || (excludeKeys && excludeKeys.has(wbMultiKey("object", frame.id)))) continue;
    if (wbItemHidden("object", frame) || wbItemRotation("object", frame)) continue;
    boxes.push(...wbGuideBoxes.walls(frame, wbGuideBoxes.insets(frame)));
  }
  wbGuideBoxCache = { key, boxes };
  return wbGuideBoxes.within(boxes, at);
}

//: The boxes a gesture sees: every box, less the margins of frames the moving
//: box is not in (its centre outside the frame's outer box).
wbGuideBoxes.within = (boxes, at) => {
  if (!at || !boxes.some((b) => b.wall)) return boxes;
  const cx = at.x + at.w / 2, cy = at.y + at.h / 2;
  return boxes.filter((b) => !b.wall || (cx >= b.wall.minX && cx <= b.wall.maxX && cy >= b.wall.minY && cy <= b.wall.maxY));
};

//: A frame's four margin lines as boxes, given its insets (`{left, right,
//: top, bottom}` from its outer edge); none when the margins leave no room.
//: `only` names the one edge of a dragged box a line is for (the left line
//: is for a left edge, not for a centre or a right edge that happens to pass
//: it), and `wall` the frame's outer box, for `within`. Pure (node-tested).
wbGuideBoxes.walls = (frame, ins) => {
  if (!ins) return [];
  const wall = { minX: frame.x, minY: frame.y, maxX: frame.x + frame.width, maxY: frame.y + frame.height };
  const l = wall.minX + ins.left, r = wall.maxX - ins.right, t = wall.minY + ins.top, b = wall.maxY - ins.bottom;
  if (r <= l || b <= t) return [];
  return [
    { minX: l, maxX: l, minY: t, maxY: b, only: "left", wall },
    { minX: r, maxX: r, minY: t, maxY: b, only: "right", wall },
    { minX: l, maxX: r, minY: t, maxY: t, only: "top", wall },
    { minX: l, maxX: r, minY: b, maxY: b, only: "bottom", wall },
  ];
};

//: How far a frame's margins sit inside its edge, in board units, read from
//: what is drawn so they are the frame's own tokens and never a copy of them:
//: the side and bottom margins are `--space-7`, the panel's padding; a
//: panel's left is its header text's left edge (the title's own padding) and
//: its top is under the header and the subtitle, a margin below the lower of
//: the two. A frame whose title hangs above its edge has no header inside.
//: Null when the frame is not drawn.
wbGuideBoxes.insets = (frame) => {
  const node = wbInstances.query(`.wb-object[data-id="${frame.id}"]`);
  if (!node) return null;
  const probe = document.createElement("div");
  probe.style.position = "absolute";
  probe.style.visibility = "hidden";
  probe.style.width = "var(--space-7)";
  node.appendChild(probe);
  const pad = parseFloat(getComputedStyle(probe).width) || 0;
  probe.remove();
  if (!node.classList.contains("wb-frame-panel")) return { left: pad, right: pad, top: pad, bottom: pad };
  const border = parseFloat(getComputedStyle(node).borderLeftWidth) || 0;
  const title = node.querySelector(".wb-frame-title");
  const head = node.querySelector(".wb-frame-hint:not([hidden])") || title;
  const text = title ? title.offsetLeft + (parseFloat(getComputedStyle(title).paddingLeft) || 0) : pad;
  const below = head ? head.offsetTop + head.offsetHeight : 0;
  return { left: border + text, right: border + text, top: border + below + pad, bottom: border + pad };
};

function wbClearGuideBoxCache() {
  wbGuideBoxCache = null;
}

// Every drag ends in one of these, whichever element it started on.
window.addEventListener("pointerup", wbClearGuideBoxCache, true);
window.addEventListener("pointercancel", wbClearGuideBoxCache, true);

//: Draws (or clears) the guide lines `wbAlignmentGuides` found. A "spacing"
//: line also gets its length as a label at a constant screen size (Figma's
//: distance badges), so an equal-gap guide says what the gap is.
const WB_BADGE_CLEAR_PX = 22;

// Asked for directly: the sketch pad is meant to be a lite version of the
// whiteboard, so the whiteboard should have at least everything the sketch
// pad does. It already covered pen ("draw"), line, rect, circle and
// eraser; highlighter and arrow were the two genuinely missing ones (a
// third, text, needs its own SVG element type, a `<path>` can't render
// text: and is scoped separately rather than force-fit into this list).
//: **More shapes in the flyout** (the owner, 2026-10-11: "can you add more
//: shapes"). Each is drawn in the dragged box, Shift for equal sides, and
//: stored as the library's own `custom` shape (decision 25): closed,
//: fillable, its words in `area` (fractions of its box). The outlines are the
//: General set's (board-library/general.json), so a hexagon drawn here and
//: one placed from the library are the same shape.
const wbShapeAt = (x, y, w, h) => (fx, fy) => `${+(x + fx * w).toFixed(1)} ${+(y + fy * h).toFixed(1)}`;
const wbShapePoly = (pts) => (x, y, w, h) => {
  const at = wbShapeAt(x, y, w, h);
  return `M ${pts.map(([fx, fy]) => at(fx, fy)).join(" L ")} Z`;
};
const WB_MORE_SHAPES = {
  "shape-rounded": {
    label: "Rounded rectangle", icon: "ph:rectangle",
    d: (x, y, w, h) => {
      //: Corners as curves, not arcs: the box a path is measured by
      //: (`wbItemBBox`) reads an arc's radii as a point and grew by one.
      const r = Math.min(16, w / 4, h / 4), k = r * 0.45;
      const at = wbShapeAt(x, y, 1, 1);
      return `M ${at(r, 0)} L ${at(w - r, 0)} C ${at(w - k, 0)} ${at(w, k)} ${at(w, r)} L ${at(w, h - r)} C ${at(w, h - k)} ${at(w - k, h)} ${at(w - r, h)} L ${at(r, h)} C ${at(k, h)} ${at(0, h - k)} ${at(0, h - r)} L ${at(0, r)} C ${at(0, k)} ${at(k, 0)} ${at(r, 0)} Z`;
    },
  },
  "shape-ellipse": {
    label: "Ellipse", icon: "ph:circle", area: { x: 0.15, y: 0.15, w: 0.7, h: 0.7 },
    d: (x, y, w, h) => {
      const rx = +(w / 2).toFixed(1), ry = +(h / 2).toFixed(1), at = wbShapeAt(x, y, w, h);
      return `M ${at(0, 0.5)} A ${rx} ${ry} 0 1 1 ${at(1, 0.5)} A ${rx} ${ry} 0 1 1 ${at(0, 0.5)} Z`;
    },
  },
  "shape-hexagon": {
    label: "Hexagon", icon: "ph:hexagon", area: { x: 0.15, y: 0, w: 0.7, h: 1 },
    d: wbShapePoly([[0.1875, 0], [0.8125, 0], [1, 0.5], [0.8125, 1], [0.1875, 1], [0, 0.5]]),
  },
  "shape-parallelogram": {
    label: "Parallelogram", icon: "ph:parallelogram", area: { x: 0.15, y: 0, w: 0.7, h: 1 },
    d: wbShapePoly([[0.175, 0], [1, 0], [0.825, 1], [0, 1]]),
  },
  "shape-star": {
    label: "Star", icon: "ph:star", area: { x: 0.3, y: 0.35, w: 0.4, h: 0.35 },
    d: wbShapePoly([[0.5, 0], [0.627, 0.325], [0.976, 0.346], [0.706, 0.567], [0.794, 0.904], [0.5, 0.717], [0.206, 0.904], [0.294, 0.567], [0.024, 0.346], [0.373, 0.325]].map(([fx, fy]) => [(fx - 0.024) / 0.952, fy / 0.904])),
  },
  "shape-cylinder": {
    label: "Cylinder", icon: "ph:database", area: { x: 0, y: 0.25, w: 1, h: 0.65 },
    d: (x, y, w, h) => {
      const rx = +(w / 2).toFixed(1), ry = +Math.max(2, h * 0.133).toFixed(1), at = wbShapeAt(x, y, 1, 1);
      return `M ${at(0, ry)} A ${rx} ${ry} 0 0 1 ${at(w, ry)} L ${at(w, h - ry)} A ${rx} ${ry} 0 0 1 ${at(0, h - ry)} Z M ${at(0, ry)} A ${rx} ${ry} 0 0 0 ${at(w, ry)}`;
    },
  },
  "shape-cloud": {
    label: "Cloud", icon: "ph:cloud", area: { x: 0.2, y: 0.35, w: 0.6, h: 0.5 },
    d: (x, y, w, h) => {
      //: The library's cloud, its control points read to its own bounds (8 to
      //: 160 across, 14 to 92 down) so it fills the dragged box.
      const at = wbShapeAt(x, y, w, h);
      const p = (px, py) => at((px - 8) / 152, (py - 14) / 78);
      return `M ${p(40, 90)} C ${p(12, 90)} ${p(8, 58)} ${p(32, 52)} C ${p(30, 26)} ${p(66, 18)} ${p(80, 38)} C ${p(92, 14)} ${p(136, 20)} ${p(134, 50)} C ${p(160, 54)} ${p(158, 92)} ${p(128, 90)} Z`;
    },
  },
  "shape-callout": {
    label: "Speech bubble", icon: "ph:chat-teardrop", area: { x: 0, y: 0, w: 1, h: 0.76 },
    d: wbShapePoly([[0, 0], [1, 0], [1, 0.76], [0.4, 0.76], [0.225, 1], [0.25, 0.76], [0, 0.76]]),
  },
  "shape-block-arrow": {
    label: "Block arrow", icon: "ph:arrow-fat-right", area: { x: 0, y: 0.25, w: 0.7, h: 0.5 },
    d: wbShapePoly([[0, 0.25], [0.667, 0.25], [0.667, 0], [1, 0.5], [0.667, 1], [0.667, 0.75], [0, 0.75]]),
  },
};

const WB_BRUSH_TOOLS = new Set(["draw", "line", "rect", "circle", "highlighter", "arrow", "triangle", "diamond", ...Object.keys(WB_MORE_SHAPES)]);
//: **The highlighter is a marker that multiplies** (WHITEBOARD_PLAN.md
//: decision 7: "marker with `mix-blend-mode: multiply` at 40% opacity, width
//: 12 to 24, Shift for straight"), which is what FigJam and Apple Freeform
//: both do and what makes two crossing strokes read as two passes of one pen
//: rather than as a third, lighter colour.
//:
//: **The numbers are not here any more.** Decision 7's other half, decided
//: 2026-09-20: the quick-sketch pad and this board are two renderers of one
//: highlighter, and what they share is `HIGHLIGHTER_STYLE` in `media.js` (the
//: alpha, the multiplier, the 12 to 24 clamp, the cap and join, and the blend
//: per backdrop). This file only asks it. The board and the pad were 0.4 with
//: multiply against 0.35 with no blend before that.
const WB_HIGHLIGHTER_ALPHA = HIGHLIGHTER_STYLE.alpha;

//: Every highlighter stroke on the board, re-blended for the mode that is on
//: now. `renderWhiteboard` already sets the blend on every render, so this
//: exists for the one case a render does not follow: the theme changing under
//: a board that is already open. The observer below is the hook (a mode
//: change is an attribute write on `<html>`, and `applyResolvedMode` in
//: settings.js is reached from the toggle, the presets and the OS media
//: query alike, so watching the attribute cannot miss a route the way
//: listening to one of the three could).
function wbRefreshHighlighterBlend() {
  const blend = wbHighlighterBlend();
  for (const path of document.querySelectorAll(".sketch-path")) {
    if (path.style.mixBlendMode) path.style.mixBlendMode = blend;
  }
  const drawing = wbInstances.query("#wb-overlay-zoom-group > path.wb-live-highlighter");
  if (drawing) drawing.style.mixBlendMode = blend;
}

new MutationObserver(wbRefreshHighlighterBlend).observe(document.documentElement, {
  attributes: true,
  attributeFilter: ["data-mode"],
});

//: The four closed shape tools fill applies to, a pen/highlighter/line/
//: arrow stroke has no enclosed area a fill would read as filling. Module
//: scope (not inside `initWhiteboard`) since both the live-draw handlers
//: and `renderWhiteboard` (a separate top-level function) need it.
//: `custom` is a shape from the library (a built-in set or one saved from a
//: drawing, WHITEBOARD_PLAN decision 25): closed, fillable, takes text in its
//: `label_area` (fractions of its box) or the whole box.
const WB_FILLABLE_SHAPES = new Set(["rect", "circle", "triangle", "diamond", "custom"]);

//: **Crop a picture to a shape** (`data.crop`; INBOX 1313 row 13). Corner
//: points as shares of the picture's box, so one table draws the board's CSS
//: clip and the export's path at any size. An ellipse is a circle on a square.
const WB_CROPS = {
  ellipse: null,
  diamond: [[0.5, 0], [1, 0.5], [0.5, 1], [0, 0.5]],
  hexagon: [[0.25, 0], [0.75, 0], [1, 0.5], [0.75, 1], [0.25, 1], [0, 0.5]],
  triangle: [[0.5, 0], [1, 1], [0, 1]],
};

//: **Voting dots** (Miro's; INBOX 1313 row 14): `data.votes`, how many dots a
//: board item holds, drawn as a pill on its top-right corner. Added and taken
//: off from the Board menu and Ctrl+K, one Undo step each
//: for every selected item; zero is none and is not stored.
const WB_VOTE_MAX = 99;

//: **A workshop timer**: a countdown pill at the board's top, from the Board
//: menu's Workshop group. Kept in the page only (a workshop is now, not a
//: property of the board), read against the clock rather than counted, so a
//: backgrounded tab is still right. One timeout at a time, aimed at the next
//: change of the shown second, and none once it ends or is stopped.
const wbTimer = { end: 0, tick: 0, bar: null, time: null };

//: **Rounded corners** (draw.io's "rounded", `data.round`): every corner of a
//: path made only of M, L and Z becomes a quadratic curve that starts and
//: ends a radius from it, held to half of each side so two corners never
//: cross. A path with any other command is returned as it came.
//: `shaftOnly` rounds the first subpath and leaves the rest as it came: a
//: connector's arrowheads are the subpaths after its line, and a rounded tip
//: would be a different head.
function wbRoundedPathD(d, radius, shaftOnly = false) {
  const r = Number(radius);
  if (!(r > 0) || typeof d !== "string") return d;
  if (shaftOnly) {
    const cut = d.indexOf("M", 1);
    return cut < 0 ? wbRoundedPathD(d, r) : `${wbRoundedPathD(d.slice(0, cut).trim(), r)} ${d.slice(cut)}`;
  }
  const tokens = d.match(/[A-Za-z]|-?\d*\.?\d+(?:e[-+]?\d+)?/g) || [];
  const subpaths = [];
  let current = null;
  for (let i = 0; i < tokens.length; i += 1) {
    const cmd = tokens[i];
    if (cmd !== "M" && cmd !== "L" && cmd !== "Z") return d;
    if (cmd === "Z") {
      if (current) current.closed = true;
      continue;
    }
    const x = Number(tokens[i + 1]);
    const y = Number(tokens[i + 2]);
    if (!Number.isFinite(x) || !Number.isFinite(y)) return d;
    i += 2;
    if (cmd === "M") {
      current = { pts: [[x, y]], closed: false };
      subpaths.push(current);
    } else if (current) {
      const last = current.pts[current.pts.length - 1];
      if (last[0] !== x || last[1] !== y) current.pts.push([x, y]);
    }
  }
  const f = (n) => String(Math.round(n * 100) / 100);
  const at = (p, q, dist) => {
    const len = Math.hypot(q[0] - p[0], q[1] - p[1]) || 1;
    return [p[0] + ((q[0] - p[0]) / len) * dist, p[1] + ((q[1] - p[1]) / len) * dist];
  };
  const out = [];
  for (const { pts, closed } of subpaths) {
    if (closed && pts.length > 1) {
      const [first] = pts;
      const [lastPt] = pts.slice(-1);
      if (first[0] === lastPt[0] && first[1] === lastPt[1]) pts.pop();
    }
    const n = pts.length;
    if (n < 3 && !closed) {
      out.push(`M${f(pts[0][0])} ${f(pts[0][1])}${n > 1 ? ` L${f(pts[1][0])} ${f(pts[1][1])}` : ""}`);
      continue;
    }
    const corner = (i) => {
      const prev = pts[(i - 1 + n) % n];
      const next = pts[(i + 1) % n];
      const here = pts[i];
      const rr = Math.min(r, Math.hypot(prev[0] - here[0], prev[1] - here[1]) / 2, Math.hypot(next[0] - here[0], next[1] - here[1]) / 2);
      return { a: at(here, prev, rr), b: at(here, next, rr), here };
    };
    if (closed) {
      const c0 = corner(0);
      let text = `M${f(c0.b[0])} ${f(c0.b[1])}`;
      for (let i = 1; i < n; i += 1) {
        const c = corner(i);
        text += ` L${f(c.a[0])} ${f(c.a[1])} Q${f(c.here[0])} ${f(c.here[1])} ${f(c.b[0])} ${f(c.b[1])}`;
      }
      text += ` L${f(c0.a[0])} ${f(c0.a[1])} Q${f(c0.here[0])} ${f(c0.here[1])} ${f(c0.b[0])} ${f(c0.b[1])} Z`;
      out.push(text);
    } else {
      let text = `M${f(pts[0][0])} ${f(pts[0][1])}`;
      for (let i = 1; i < n - 1; i += 1) {
        const c = corner(i);
        text += ` L${f(c.a[0])} ${f(c.a[1])} Q${f(c.here[0])} ${f(c.here[1])} ${f(c.b[0])} ${f(c.b[1])}`;
      }
      text += ` L${f(pts[n - 1][0])} ${f(pts[n - 1][1])}`;
      out.push(text);
    }
  }
  return out.join(" ");
}

//: A property of `wbRoundedPathD`, not a name of its own: the shared scope is at its cap (test_global_scope_ratchet).
//: **Curved lines** (draw.io's "curved", `data.curve`): a path made only of M, L and Z
//: becomes a Catmull-Rom spline through the same points, as cubics, so the line is smooth
//: and still passes through every point. Fewer than three points, or any other command,
//: comes back as it came; `shaftOnly` leaves a connector's arrowheads alone, as the rounding does.
wbRoundedPathD.curved = function (d, shaftOnly = false) {
  if (typeof d !== "string") return d;
  if (shaftOnly) {
    const cut = d.indexOf("M", 1);
    return cut < 0 ? wbRoundedPathD.curved(d) : `${wbRoundedPathD.curved(d.slice(0, cut).trim())} ${d.slice(cut)}`;
  }
  const tokens = d.match(/[A-Za-z]|-?\d*\.?\d+(?:e[-+]?\d+)?/g) || [];
  const pts = [];
  let closed = false;
  for (let i = 0; i < tokens.length; i += 1) {
    if (tokens[i] === "Z") closed = true;
    else if (tokens[i] === "M" || tokens[i] === "L") {
      if ((tokens[i] === "M") !== (i === 0) || pts.length > 0 && closed) return d;
      pts.push([Number(tokens[i + 1]), Number(tokens[i + 2])]);
      i += 2;
    } else return d;
  }
  if (closed && pts.length > 1 && pts[0][0] === pts.at(-1)[0] && pts[0][1] === pts.at(-1)[1]) pts.pop();
  const n = pts.length;
  if (n < 3 || pts.some((p) => !Number.isFinite(p[0]) || !Number.isFinite(p[1]))) return d;
  const f = (v) => String(Math.round(v * 100) / 100);
  const pick = (i) => (closed ? pts[(i + n) % n] : pts[Math.max(0, Math.min(n - 1, i))]);
  let text = `M${f(pts[0][0])} ${f(pts[0][1])}`;
  for (let i = 0; i < (closed ? n : n - 1); i += 1) {
    const [p0, p1, p2, p3] = [pick(i - 1), pick(i), pick(i + 1), pick(i + 2)];
    const c1 = [p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6];
    const c2 = [p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6];
    text += ` C${f(c1[0])} ${f(c1[1])} ${f(c2[0])} ${f(c2[1])} ${f(p2[0])} ${f(p2[1])}`;
  }
  return closed ? `${text} Z` : text;
};

// The visible half of Select, asked for directly ("select... as a real
// tool, not folded into pan"). Re-applied after every `wbScheduleRender()`
// (elements are rebuilt on each render, so a class set on the old DOM node
// would vanish silently) as well as right after a click.
const WB_SELECTOR_BY_KIND = {
  sketch: (id) => `.sketch-group[data-id="${id}"]`,
  node: (id) => `.node-card[data-id="${id}"]`,
  object: (id) => `.wb-object[data-id="${id}"]`,
};

const wbMultiKey = (kind, id) => `${kind}:${id}`;

// Asked for directly, more than once: "changing properties of shapes and
// text boxes... fill, border". Single-selection only: the same reasoning
// Grouping: asked for directly (Ctrl+G / Ctrl+Shift+G). Unlike
// `wbMultiSelection` (in-memory, gone on reload), a group's id is persisted
// on every member's own `group_id` column, so clicking any one member later
// reselects the whole set, the other half of this feature lives in
// `wbHandleItemClick` below.
//
//: **Groups nest** (the owner, INBOX 1354: "if I have 7 items and group 5 but
//: then highlight the grouped 5 and the other two can it group them all again
//: and then if I ungroup them the 5 will also remain grouped?"). `group_id` is
//: a chain, outermost first, joined by `>`: the 5 hold `outer>inner`, the 2
//: hold `outer`. Grouping puts a new id in front; ungrouping takes the one the
//: selection shares off. The column is 40 characters, so new ids are 6 and a
//: chain is five deep at most; an old 36-character id is re-keyed short, on
//: every member at once, the first time it is nested.
const WB_GROUP_SEP = ">";
const WB_GROUP_MAX_LEN = 40;

//: **The element a card or object is drawn as, looked up once, not per call**
//: (INBOX 424a). `wbItemBBox` is asked about every member of a selection on
//: every drag frame (through the selection bar's `wbSelectionBounds`), and
//: each ask opened with a document-wide attribute query: measured at 4x CPU,
//: dragging a 20-item selection 40 moves on a 250-object board spent 2.6s of
//: its 8.6s in `querySelector`. The same `isConnected` test
//: `wbBulkMoveElement` uses keeps it honest: a render that replaced the
//: element disconnects the cached one, so the next ask finds the new one.
//: `renderWhiteboard` empties the map so a deleted item's detached element is
//: not held on to.
const wbItemElCache = new Map();

//: **A miss is as cheap as a hit** (audit 1031 BD3). Opening the 302-item
//: board asked for every item's element before the first render had made one,
//: and each miss walked the whole document: 115 of the open's 848 ms at 4x. The
//: cards and objects are the children of `#wb-html-layer`, so one pass over
//: them builds a key index, rebuilt when the layer's child count moves or a
//: render empties the cache; a lookup is then one `Map.get`.
const wbItemElIndex = { byKey: new Map(), count: -1, last: null };

//: **What a fit fits into: the canvas the person can see** (INBOX 792, the
//: owner: "the fitting to screen features ... should be based on what panels
//: are currently showing and the screen resolution/size"). The canvas is one
//: box under the top bar, the tools dock, the sidebar and the Format panel,
//: so a fit to the box parked content under them. The free area is the box
//: less whichever of those is showing, each taken off the side it sits on
//: (a wide one off the top or bottom, a tall one off the left or right), in
//: the box's own coordinates. A window too narrow to leave a third of the box
//: (the sidebar a sheet over a phone) keeps its sides, since a fit into a
//: sliver is worse than one that runs under a sheet.
const WB_FIT_OCCLUDERS = ["#wb-topbar", "#wb-tools-panel", "#wb-sidebar", "#wb-format"];

//: **The camera from the keyboard, as InDesign has it** (the owner,
//: 2026-11-01, INBOX 1509: "ctrl +/- to zoom out and zoom in foccused on
//: selected objects or in general on the whiteboard if focused on it like
//: with adobe indesign"). Ctrl or Cmd with + or = steps in and with - steps
//: out by the zoom buttons' own factors, about the selection's centre when
//: something is selected, else the view's centre (`wbZoomAnchor`, the
//: pointer left out: a key is not aimed). Ctrl+0 fits the board, Ctrl+1 is
//: 100% about the same point. Measured before: one Ctrl+= zoomed the board
//: 1.2x and the whole app from 100% to 105% as well, because the app zoom's
//: capture listener took the same key; while the board has the focus the key
//: is the board's alone, so this stops it there. Never while typing (the
//: app zoom keeps the key then), and not while a dialog or a panel outside
//: the board holds the focus. `e.code`, because Ctrl+= arrives as "+" or "="
//: depending on the layout.
const WB_ZOOM_KEYS = {
  Equal: () => wbZoomStep(1.2, { usePointer: false }),
  NumpadAdd: () => wbZoomStep(1.2, { usePointer: false }),
  Minus: () => wbZoomStep(0.8, { usePointer: false }),
  NumpadSubtract: () => wbZoomStep(0.8, { usePointer: false }),
  Digit0: () => wbZoomToFit(),
  Numpad0: () => wbZoomToFit(),
  Digit1: () => wbZoomTo100(),
  Numpad1: () => wbZoomTo100(),
};

//: A fit tighter than this is a map you cannot read: the nodes are there, the
//: words in them are not. Below it, framing the root at 1:1 beats fitting the
//: whole tree, which is what every map tool does on open.
const WB_MAP_OPEN_MIN_SCALE = 0.45;

//: **On a phone the floor is the text, not the tree** (blind test 1031, 390px:
//: a 7-topic template framed at 0.24, so a 17px topic read at 4px, a pill was
//: 44x11 and the 24px add handle covered it). The owner, 2026-11-09: fit the
//: whole map down to a minimum readable zoom, and when it is still too big,
//: centre the root at that zoom. A topic's own text is 17px, so 0.65 reads at
//: 11px (the floor; 0.72 read at 12px but left a 5-topic map 1 of 5 in view),
//: and the fit's margin is 16px rather than 64 (the canvas is 372px wide). The
//: canvas width is the test rather than the pointer: a narrow desktop window
//: has the same problem.
const WB_MAP_PHONE_MAX_WIDTH = 600;
const WB_MAP_PHONE_SCALE = 0.65;

//: **Each board keeps its own view for the session.** Boards and maps share
//: one d3 camera, so opening a second board used to inherit the first one's
//: pan and zoom, which on a map read as "nowhere". The view is remembered per
//: board id on the way out and put back on the way in, but only if some of the
//: content would be on screen with it; otherwise the board is framed afresh.
const wbBoardViews = new Map();

function wbRememberBoardView() {
  const id = window.currentBoardId;
  const container = wbInstances.container();
  if (id == null || !container || !container.clientWidth || typeof wbZoom === "undefined") return;
  const t = d3.zoomTransform(container);
  wbBoardViews.set(id, { x: t.x, y: t.y, k: t.k });
  //: Past a reload too (per device, like the board's background image): the view a board was last shown at is the one it reopens at.
  prefs.set(`wb-view-${id}`, JSON.stringify({ x: t.x, y: t.y, k: t.k }));
}
window.addEventListener("pagehide", wbRememberBoardView);

//: The view a board was left on in an earlier visit; anything that is not three finite numbers is no view.
wbRememberBoardView.stored = (id) => {
  try {
    const view = JSON.parse(prefs.get(`wb-view-${id}`, "null"));
    return view && Number.isFinite(view.x) && Number.isFinite(view.y) && Number.isFinite(view.k) && view.k > 0 ? view : null;
  } catch {
    return null;
  }
};
let wbRevealSig = "";
let wbRevealTimer = 0;

window.addEventListener("pointerdown", () => clearTimeout(wbRevealTimer), true);
window.addEventListener("pointerup", () => { if (wbSelectedItem || wbMultiSelection.size) wbQueueReveal(); }, true);

// whiteboard-navigator.js: whiteboard-navigator.js: the live minimap: its paint, cost gate and drag. (moved out, L286).
// whiteboard-search.js: whiteboard-search.js: the find-a-card bar. (moved out, L286).

// whiteboard-connectors.js: whiteboard-connectors.js: connection anchors, link routing and the connector pan (moved out, L286).

// whiteboard-arrange.js: whiteboard-arrange.js: align, distribute and arrange commands. (moved out, L286).

// as the resize handles above, there is no one set of properties to show
// for a mixed multi-selection. A node (note card) and an image object have
// nothing here to edit yet (a card's own text is the note; an image has no
// stroke/fill of its own), so the panel just stays hidden for those.
//: **Which of the bar's tool settings each held tool actually reads**
//: (INBOX 445), by the `data-wb-tool-setting` each control carries. The bar
//: used to show all four for fourteen tools: the pen offered arrowheads and a
//: fill, a link offered a size, a dash and a fill it never reads (a link takes
//: the rail's ink and nothing else), and the eraser, the sticky, the text box
//: and the fill bucket offered settings none of them use. A control that does
//: nothing when changed reads as broken. A tool missing here shows no bar;
//: the ink well on the rail is still its colour.
const WB_TOOL_SETTINGS = {
  draw: ["size", "dash"],
  highlighter: ["size"],
  line: ["size", "ends", "head", "dash"],
  arrow: ["size", "ends", "head", "dash"],
  //: A link takes the rail's ink and its ends (dog2 item 13: drawn with the
  //: Link tool it had no head and no way to ask for one). It shares the
  //: Arrow tool's ends, which start at an end arrow.
  "link-straight": ["ends", "head"],
  "link-curved": ["ends", "head"],
  rect: ["size", "dash", "fill"],
  circle: ["size", "dash", "fill"],
  triangle: ["size", "dash", "fill"],
  diamond: ["size", "dash", "fill"],
  ...Object.fromEntries(Object.keys(WB_MORE_SHAPES).map((tool) => [tool, ["size", "dash", "fill"]])),
};

//: **Copy a style off one thing and put it on another.** Asked for directly:
//: "I want a tool or way to copy styles of shapes and links and add them to
//: another shape or link connector of a similar type."
//:
//: Modelled on Excalidraw's copy/paste-style rather than on PowerPoint's
//: format-painter *mode*: select a source, copy, select a target, paste. A
//: painter mode would mean a third cursor state and a "what am I armed with"
//: question on every click; this reuses the selection the board already has.
//:
//: "A similar type" is enforced, not assumed, a text box's style is its
//: font size and its background, a sketch's is its stroke and fill, and
//: pasting one onto the other would either do nothing or write fields the
//: renderer does not read. The copy remembers which kind it came from and
//: refuses the mismatch out loud.
let wbCopiedStyle = null; // { kind: "sketch" | "object", style: {...} }

// Only the fields that are style. Deliberately not `d` (the geometry), not
// `type`, not position: pasting a style must never move or reshape the
// thing it lands on.
const WB_SKETCH_STYLE_KEYS = [
  "color", "width", "dash", "fill", "fillOpacity", "opacity", "noStroke", "startCap", "endCap", "startCapSize", "endCapSize",
  "dashPattern", "round", "curve", "flow", "gradient", "fillStyle", "jumpSize", "gapStart", "gapEnd", "arrowBody", "arrowHead",
  "shadow", "shadow_x", "shadow_y", "shadow_blur",
];
const WB_OBJECT_STYLE_KEYS = ["color", "bg", "border_color", "font_size", "radii", "pad", "shadow", "shadow_x", "shadow_y", "shadow_blur"];

//: **Reset style** (INBOX 747, the owner: "there's no way to reset a object
//: back to default style"). Every look field a kind's controls can set is
//: taken off, so the item draws as a new one of its kind would: the theme's
//: ink, no fill, a solid 3-wide line, its text at the default size. What it
//: says, where it is, its ends' marks and a connector's route are kept. A
//: sticky goes back to the first paper; a map topic back to following its
//: map and level (`wbMapResetToBranch`'s keys). One undo step for the lot.
const WB_SKETCH_RESET_KEYS = [
  "color", "width", "dash", "fill", "fillOpacity", "opacity", "noStroke", "alpha", "shadow", "shadow_x", "shadow_y", "shadow_blur", "rough", "jumps", "round", "curve", "dashPattern", "flow", "gradient", "fillStyle", "jumpSize", "gapStart", "gapEnd", "arrowBody", "arrowHead",
  "startCapSize", "endCapSize", "label_size", "label_color", "label_bold", "label_italic", "label_underline", "label_strike", "label_font", "label_align", "label_valign", "label_lh", "label_ls", "label_shadow", "glass", "fill_image", "label_dir", "label_alpha",
];
const WB_OBJECT_RESET_KEYS = ["color", "bg", "border_color", "font_size", "bold", "italic", "underline", "strike", "font_family", "align", "valign", "line_height", "letter_spacing", "text_shadow", "text_dir", "text_alpha", "alpha", "shadow", "shadow_x", "shadow_y", "shadow_blur", "radii", "pad", "fold"];

//: **The kind to controls table** (WHITEBOARD_PLAN.md decision 2). One row
//: per thing that can be selected, saying which of the context bar's groups
//: it shows and which sections of the "..." menu it opens. A new kind of
//: object gets its controls by adding a row here, not by adding a panel; and
//: "the bar shows only what applies" is then a property of this table rather
//: than of forty `classList.toggle` calls spread through a function.
//:
//: The keys are the selection's shape, not the storage kind: a `sketch` is a
//: drawn line, an arrow or a closed shape and those take different controls,
//: and an `object` is a text box or a picture. `wbContextKindOf` below turns
//: a selection into one of these names.
const WB_CONTEXT_CONTROLS = {
  // Nothing selected, a drawing tool held: what the next stroke will use.
  tool: { bar: ["tool"], more: ["more-style"] },
  line: { bar: ["ink", "caps", "stroke", "order"], more: ["more-link", "more-style"] },
  shape: { bar: ["ink", "stroke", "fill", "order"], more: ["more-link", "more-shape", "more-style"] },
  link: { bar: ["ink", "route", "caps", "stroke"], more: ["more-style"] },
  text: { bar: ["ink", "text", "order"], more: ["more-link", "more-style", "more-card"] },
  image: { bar: ["order"], more: ["more-link", "more-style"] },
  // A note card: its look comes from the note, so what it offers is where it
  // sits and what it can become.
  note: { bar: ["order"], more: ["more-mindmap", "more-notes"] },
  multi: { bar: ["arrange", "order"], more: ["more-tidy", "more-notes"] },
  //: Several topics on a map (INBOX 617, `wbMapMultiTopics`): the map's own
  //: verbs, never the board's arrange and order, which fight the layout.
  mapmulti: { bar: ["mapmulti"], more: [] },
};

//: Every group and menu section the table can name, so hiding "everything
//: else" never has to list them.
const WB_CONTEXT_GROUPS = ["tool", "ink", "route", "caps", "stroke", "fill", "paper", "text", "arrange", "order", "mapmulti"];
// spacing across the fan-out axis
// spacing per depth level, left → right
// ring spacing per depth level

/** Put a card into edit mode with its text selected.
 *
 *  A concept map is written by typing, so the node a branch gesture just
 *  created has to be typeable *now*, not after finding a menu. Selecting
 *  the placeholder means the first keystroke replaces it, which is what
 *  makes `Tab, type, Tab, type` a fluent way to work rather than a sequence
 *  of edits.
 */
//: **After Enter names a card, letters name it again** (audit 2026-10-05,
//: UX-06). The editor's Enter left the card selected and the next word typed
//: went to the board's tool keys: "Flowers" picked five tools and drew a
//: stray shape. Now, until the selection moves on, a printable key on that
//: card opens it for typing with the key as its first letter (XMind's rule
//: for a selected topic); Tab and Enter still branch. Elsewhere a letter is
//: still a tool key. The focus is left where it was, not moved to the
//: canvas as a map's is (decision 27): a focused board canvas reads Tab as
//: "walk the items" (`wbWalkItems`), which would take the branch key away.
const wbAddGate = { cardRetypeId: null, renderHold: null, barDeferred: false, barDeferredQueued: false, panBarHold: null, panBarTimer: 0 };

// whiteboard-bar.js: whiteboard-bar.js: the selection bar and context strip over a map or board. (moved out, L286).
//: **Once a frame during a drag, not once a move** (INBOX 424a). A drag move
//: can arrive several times between two paints (a fast mouse, a slow
//: machine), and each one placed the bar from scratch: the selection's
//: bounds, a style flush for the bar's own size, two rect reads. Only the
//: last placement before a paint is ever seen, so the drag handlers queue
//: one and the frame places it from whatever the selection is by then. Every
//: other caller (a click, a render, a pan frame) still places it at once.
let wbSelectionBarFrame = 0;

// whiteboard-stacking.js: whiteboard-stacking.js: the stacking order, layer order and the bulk move of a s (moved out, L286).
//: **A dragged selection's bar moves by the drag, it is not re-measured**
//: (INBOX 445). The bar over a multi-selection is placed from the union of
//: every member's box, and `wbItemBBox` reads a text box's or card's rendered
//: size, so each frame of a group drag measured all of them straight after
//: the drag had written their transforms: a forced layout per frame, two
//: per move counted, and on an 80-item drag 165ms of 40 moves in
//: `wbUpdateSelectionBar` alone. The members move rigidly, so the box at the
//: start plus the drag's delta is the same box. Set by `wbApplyBulkMove`,
//: dropped when the pointer comes up, after which the bar measures again.
let wbBulkBarBounds = null;
window.addEventListener("pointerup", () => { wbBulkBarBounds = null; }, true);
window.addEventListener("pointercancel", () => { wbBulkBarBounds = null; }, true);

// --- The gesture conventions (the owner, 2026-09-23) -----------------------
//
// "the whiteboard and mindmap are still missing a lot of those small features
// that we as user's use all the time and take for granted but very much
// notice when they arent there." What follows is shared by the three drags
// (card, object, shape), their resize and rotate grips and the link draw:
// Escape to put a gesture back, Shift to keep a move on one axis, Alt to
// leave a copy behind, and one undo step for everything a drag moved.
// `scratchpad/ui-sweeps/canvasconventions.js` measures each of them.

//: **The gesture in flight, so Escape can put it back.** Every editor people
//: know treats Escape mid-drag as "never mind": Figma, tldraw and Excalidraw
//: all return the item to where it was taken from and record nothing. d3-drag
//: has no way to abort a gesture from outside, so a cancelled one is left to
//: run out: its handlers read `cancelled`, ignore the rest of the pointer's
//: travel and save nothing when it is released. `restore` is written by the
//: drag that begins the gesture, because only it knows what it changed.
let wbGesture = null;

//: **A finger carries nothing until it has travelled, and a second finger
//: carries nothing at all** (INBOX 888, the owner: "I tried pinching to zoom
//: out on my phone when on the whiteboard and instead I accidentally started
//: moving a note"). Measured at 390x844 with real two-finger touch events
//: (`scratchpad/ui-sweeps/wbpinch.js`): the first finger of a pinch landed on
//: a note, the card's drag began on the touch-start and followed it, and the
//: second finger either started a second drag (on the same note, so the pinch
//: never reached the zoom: scale 1 to 1) or went to the zoom while the first
//: finger kept dragging (a note moved 12px and 61px, a text box 206px and
//: 373px away). Three parts:
//:   1. `wbTouchSlopStep`: a touch drag only starts to move its item once the
//:      finger has travelled `WB_TOUCH_SLOP` screen pixels, and then moves it
//:      by the whole distance so far, so nothing is lost. A mouse and a pen
//:      keep their instant drag.
//:   2. `wbIsSecondTouch`, in the three item drags' filters: a touch-start
//:      with two fingers down is never a drag, so the event reaches d3-zoom
//:      (which registers every finger on the screen, not only the new one).
//:   3. The window's touch-start listener in `initWhiteboard`: a second finger
//:      puts any drag in flight back (`wbCancelGesture`, the same restore
//:      Escape uses), so the first finger's travel before the second landed
//:      leaves no trace.
const WB_TOUCH_SLOP = 8;

//: `gesture` is `d._gesture`, the object `wbBeginGesture` made for this drag, so
//: the running total starts at zero with every drag. `unit` is how many screen
//: pixels one of the event's units is: 1 for a card (screen pixels), the zoom
//: scale for a shape (its drag measures in board units). Returns the movement
//: to apply, or null while the finger is still inside the slop.
//:
//: **A mouse gets a slop too, of 3px** (the owner, INBOX 1354: moving and
//: editing "is very finicky"). Without one, a click that slipped 2px moved
//: the shape 2px and, because d3 then swallows the click, selected nothing.
//: `WB_CLICK_SLOP` is the same distance given to the drags' `clickDistance`,
//: so a press that moved less than it is a click and nothing else.
const WB_CLICK_SLOP = 3;

//: **Drag to delete** (INBOX 660, the owner: "I want to be able to drag
//: elements on the whiteboard and mindmap onto a popup delete button to
//: delete them"; Miro, Freeform and every phone home screen do it). While a
//: card, a box, a shape or a map topic is carried, a target floats at the
//: foot of the canvas (`.wb-trash`, a `.whiteboard-floating-panel`, so the
//: glass-off list already holds it); the pointer over it turns it to the
//: error ink and says "Release to delete". Let go there and the drag is put
//: back first (the gesture's own `restore`, so nothing moved is saved), then
//: what was carried is deleted as one Undo step (`wbRecordGesture`, the
//: selection's own delete) with a toast offering Undo. A topic takes its
//: branch, as its Delete does (the server deletes the subtree). Escape, or a
//: drop anywhere else, leaves it a plain move or no move. Keyboard people
//: keep Delete; the target is pointer-only and hidden from the tree, and its
//: two states are said in the board's live region.
//:
//: It sits above the edge auto-pan's band (3.5rem, `wbEdgePan.band`), so the
//: board does not scroll away while the pointer travels to it, and the pan
//: holds still while the pointer is over it.
const wbTrash = { el: null, rect: null, down: [0, 0], drop: null };

//: A sidebar item being dragged (a Library tile you made, a Layers row): `drop` runs if it is let go on the target.
//: Called from that list's dragstart; its dragend calls `wbTrash.dndEnd`.
wbTrash.dndBegin = (drop) => {
  const el = wbTrashTarget();
  if (!el) return;
  wbTrash.drop = drop;
  wbTrashSetHot(false);
  el.classList.add("wb-trash-dnd");
  el.classList.remove("hidden");
};

wbTrash.dndEnd = () => {
  wbTrash.drop = null;
  wbTrash.el?.classList.remove("wb-trash-dnd");
  wbTrashSetHot(false);
  wbTrashHide();
};

window.addEventListener("pointerdown", (e) => { wbTrash.down = [e.clientX, e.clientY]; }, true);
window.addEventListener("pointermove", (e) => {
  const g = wbGesture;
  if (!g || !g.move || g.cancelled) {
    if (wbTrash.rect) wbTrashHide();
    return;
  }
  if (!wbTrash.rect) {
    //: Shown on the drag's first few pixels, never on a click.
    if (Math.hypot(e.clientX - wbTrash.down[0], e.clientY - wbTrash.down[1]) < 6) return;
    const el = wbTrashTarget();
    if (!el) return;
    wbTrashSetHot(false);
    el.classList.remove("hidden");
    wbTrash.rect = el.getBoundingClientRect();
  }
  const r = wbTrash.rect;
  const pad = 8;
  const over = e.clientX >= r.left - pad && e.clientX <= r.right + pad && e.clientY >= r.top - pad && e.clientY <= r.bottom + pad;
  if (over !== Boolean(g.overTrash)) {
    g.overTrash = over;
    wbTrashSetHot(over);
    wbAnnounce(over ? "Over Delete. Release to delete, or move away to keep it." : "Off Delete.");
  }
}, true);
//: A sidebar drag ends the pointer stream with a pointercancel the moment the browser takes the drag over, so that one leaves the target up.
window.addEventListener("pointercancel", () => { if (!wbTrash.drop) wbTrashHide(); }, true);
//: Any drag whose end returns before its own `wbTrashTake` and
//: `wbEndGesture` would leave the target up and the move live until the next
//: drag (INBOX 1405), so after every release, once the drags' own end
//: handlers have run, a move still carried is let go and the target hidden.
window.addEventListener("pointerup", () => setTimeout(() => {
  if (wbGesture?.move) wbGesture = null;
  wbTrashHide();
}), true);


// Copy/paste: reported directly: "can't copy/paste objects drawn or made
// on whiteboard". One snapshot, not a real OS clipboard: this app has
// nothing to gain from `navigator.clipboard` here (no cross-tab/cross-app
// paste target makes sense for a sketch's own path data), and a plain
// in-memory value is simpler and needs no permission prompt.
let wbClipboard = null; // { items: [{kind, payload}], box: {minX, minY, maxX, maxY}, stamp, at }
//: Whether the browser's paste event followed the last Ctrl+V (FEAT-09).

//: Where the pointer last was over the canvas, or null once it has left.
//: Paste lands here (below), which is what Figma, Miro and tldraw all do
//: with a keyboard paste while the pointer is on the canvas. Kept as the raw
//: client point and turned into board units only when a paste asks: it is
//: written on every pointer move, pans included, and a layout read per move
//: is the cost the pan path has been cleared of (`wbSyncGridToTransform`).
let wbPointerClient = null;

// whiteboard-place.js: whiteboard-place.js: paste from other apps, where a placed thing lands, clone an (moved out, L286).
// --- Right-click / long-press menu for a selection (ROADMAP §89.12) --------
//
// Asked as a question, alongside cut above: today the only way to act on a
// selection is a keyboard shortcut, and `wbOpenDockedMenu`'s reparent-to-body
// technique (a few hundred lines up) is the only precedent in this file for
// a menu that has to escape a clipped, scrolling ancestor, so this reuses
// that shape rather than inventing a second one, just triggered by a gesture
// on the canvas instead of a toolbar toggle.
let wbCtxMenuEl = null;
// whiteboard-ctxmenu.js: whiteboard-ctxmenu.js: the right-click and long-press menu for a selection. (moved out, L286).
//: **One way to hold a pointer for a drag** (L271). The board's raw pointer
//: drags (marquee, placing a box, the selection drag, a port's connector,
//: the lasso, the navigator's frame) each took capture in its own try block
//: and ended on its own pair of window listeners. Capture keeps the moves and
//: the release coming when the pointer leaves the container; a synthetic
//: press (a test, an assistive tool) has no live pointer to capture, and the
//: window listeners still end it. Item drags stay on d3.drag, which captures
//: for itself, and the right-press gate stays on mouse events because that is
//: what d3.zoom listens to.
//: Held on `wbBoardState`, so the pair adds no name to the shared scope.
wbBoardState.capture = (el, pointerId) => {
  try {
    el.setPointerCapture(pointerId);
  } catch {
    /* no live pointer: the gesture's window listeners end it */
  }
};
//: A gesture taken away (the browser's pointercancel, a lost capture) ends
//: the same way a release would.
wbBoardState.onGestureLost = (end) => {
  window.addEventListener("pointercancel", end);
  window.addEventListener("lostpointercapture", end);
};

//: `pass` is true for the rest of one synchronous render (a microtask clears
//: it): every stroke asks for the same colour, and building the signature
//: below walked the root's attributes 280 times a render (W30, 2.4 ms).
const wbBoardBgCache = { sig: "", value: "", pass: false, out: "" };

// The shared half of undo and redo: pop one entry off `from`, apply its
// inverse, and push what would undo *that* onto `to`. Undo and redo are
// each other's mirror image: pop from one stack, push the reverse onto
// the other: so one function drives both rather than two near-duplicates
// that could drift apart.
//: Per-kind: the collection endpoint, which key in `wbState` holds it, and
//: how to turn a live item back into a POST body. One table rather than a
//: three-way ternary repeated at every call site, adding the "object" kind
//: (images/text boxes) here is the only change `wbApplyHistoryEntry` needed
//: to cover them too.
const WB_KIND_INFO = {
  sketch: {
    base: "/whiteboard/sketches",
    list: "sketches",
    payload: (d) => ({ data: d.data, board_id: d.board_id, x: d.x, y: d.y, z: d.z, group_id: d.group_id ?? null }),
  },
  node: {
    base: "/whiteboard/nodes",
    list: "nodes",
    payload: (d) => ({
      entry_id: d.entry_id, board_id: d.board_id, x: d.x, y: d.y, z: d.z,
      width: d.width ?? null, height: d.height ?? null, rotation: d.rotation ?? null,
      group_id: d.group_id ?? null, locked: Boolean(d.locked), comments: d.comments ?? null,
      hidden: Boolean(d.hidden),
    }),
  },
  object: {
    base: "/whiteboard/objects",
    list: "objects",
    payload: (d) => ({
      kind: d.kind, data: d.data, board_id: d.board_id,
      x: d.x, y: d.y, z: d.z, width: d.width, height: d.height,
      rotation: d.rotation ?? null, group_id: d.group_id ?? null,
    }),
  },
};

onSurface("board", () => {
  const board = document.getElementById("whiteboard-container"); // page wiring, at load (L-whiteboard-53)
  const reach = (e) => {
    const el = e.target?.closest?.(".wb-object, .node-card");
    if (el) wbEnsureHandles(el);
  };
  board?.addEventListener("pointerover", reach, { passive: true });
  board?.addEventListener("focusin", reach);
});

// whiteboard-textedit.js: whiteboard-textedit.js: the text box and sticky editor, runs, text style bar and (moved out, L286).
//: The parents of the topics one Undo took away, in the order they went. A
//: batch (a duplicated branch) removes several, and most of their parents go
//: with them, so `wbUndo` picks the first that is still on the board.
let wbUndoParents = [];
// whiteboard-comments.js: whiteboard-comments.js: comments threads, item links and their marks on the boar (moved out, L286).
let wbCommentState = null;
// whiteboard-frames.js: whiteboard-frames.js: frames: create, fit, turn, title, draw (decision 14). (moved out, L286).
const WB_PLACE_MIN = { text: { w: 60, h: 32 }, sticky: { w: 80, h: 60 }, frame: { w: 120, h: 80 } };

//: **The whole bundle before the wiring** (owner report on #222): a board restored with the
//: page opens while the later files are still arriving, and the wiring reaches into them
//: (`wbFmtState` in whiteboard-format.js); a throw there left no handler wired, stuck on one
//: tool. The flag is set first, so a second call adds nothing (tests/test_wb_init_order.py).
async function initWhiteboard() {
  surfaceBuild("board");
  if (wbInitialized) return;
  wbInitialized = true;
  await ensureModule("boards");
  //: Two hooks `selectWbTool` calls, set further down this closure: refreshing
  //: the "Line ends" control when the tool switches between Line and Arrow, and
  //: the phone tools opener's label. Locals since L-whiteboard-53 (nothing
  //: outside this closure read them; freed two shared names).
  let wbRefreshArrowStyleControlRef = null;
  //: A holder, not a `let`, so the tools sheet (whiteboard-toolsheet.js) can set it.
  const wbToolsOpenerSync = { fn: null };
  //: Pan, zoom and gesture listeners (whiteboard-pan.js): it shares only the names passed and returned here.
  wbInitPan({ selectWbTool });
  //: The pen's state in one holder, not four `let`s, so the stroke handlers
  //: (whiteboard-strokes.js) can read and set it from their own file. `abandon` and
  //: `dropLost` are set there too; a tool switch before that has nothing to drop.
  const wbPen = { drawing: false, path: null, data: [] /* array of [x, y] */, width: 3 };
  // Reported directly: a white stroke, hardcoded regardless of theme, on a
  // light-theme board whose background (`--wb-board-bg: var(--modal-bg)`,
  // theme-aware) is itself light, drawing anything was invisible from the
  // first stroke. Defaults to black on light, white on dark, matching
  // whichever the board's own background actually resolves to; a saved
  // choice (persisted the same way the board's own background colour is)
  // always wins over the theme default.
  const savedStroke = prefs.get("wb-stroke-color", null);
  window.currentStrokeColor =
    savedStroke || (document.documentElement.dataset.mode === "dark" ? "#ffffff" : "#000000");
  // Shared with the mousedown handler below, so the cursor preview drawn
  // here is never a different size than what actually gets drawn. Was a
  // fixed `const` (asked about directly: "does the whiteboard have a tool
  // for adjusting pen size... line/shape width?", it didn't), now `let`,
  // driven by `#wb-stroke-width` below, so every closure over this variable
  // (the highlighter's own 4x multiplier, arrowhead length, the saved
  // sketch's own width) picks up a change without needing to be rewired.
  wbPen.width = Number(prefs.get("wb-stroke-width", null)) || 3;
  const strokeWidthInput = document.getElementById("wb-stroke-width");
  const strokeWidthBadge = document.getElementById("wb-stroke-width-badge");
  let strokeWidthBadgeTimer = null;
  function showStrokeWidthBadge() {
    if (!strokeWidthBadge || !strokeWidthInput) return;
    const r = strokeWidthInput.getBoundingClientRect();
    strokeWidthBadge.textContent = `${wbPen.width}px`;
    strokeWidthBadge.style.left = `${r.left + r.width / 2}px`;
    strokeWidthBadge.style.top = `${r.top - 8}px`;
    strokeWidthBadge.classList.remove("hidden");
    clearTimeout(strokeWidthBadgeTimer);
    strokeWidthBadgeTimer = setTimeout(() => strokeWidthBadge.classList.add("hidden"), 900);
  }
  if (strokeWidthInput) {
    strokeWidthInput.value = String(wbPen.width);
    strokeWidthInput.addEventListener("input", (e) => {
      wbPen.width = Number(e.target.value) || 3;
      prefs.set("wb-stroke-width", String(wbPen.width));
      updateWbCursor();
      showStrokeWidthBadge();
    });
  }

  const toolGroup = document.getElementById("wb-tool-group");
  const arrowStyleSelect = document.getElementById("wb-arrow-style");
  // Live-reported: "I selected the line tool and it still drew with an
  // arrow head." Line and Arrow share this one control (asked for
  // directly, so a plain line *can* carry a head), but they used to share
  // a single `currentArrowStyle` value too: so drawing with Arrow first
  // (default "end") left Line permanently defaulting to an arrowhead as
  // well, since nothing ever reset it. Each tool now keeps its own
  // default (Line: none, Arrow: end) and its own localStorage key; the
  // control itself still reads/writes whichever tool is currently active,
  // via `wbCurrentEndStyleKind`/`wbSetCurrentEndStyle` below.
  window.currentLineEndStyle = prefs.get("wb-line-end-style", null) || "none";
  window.currentArrowEndStyle = prefs.get("wb-arrow-style", null) || "end";
  function wbCurrentEndStyleKind() {
    return window.currentTool === "line" ? "line" : "arrow";
  }
  function wbCurrentEndStyle() {
    return wbCurrentEndStyleKind() === "line" ? window.currentLineEndStyle : window.currentArrowEndStyle;
  }
  function wbSetCurrentEndStyle(value) {
    if (wbCurrentEndStyleKind() === "line") {
      window.currentLineEndStyle = value;
      prefs.set("wb-line-end-style", value);
    } else {
      window.currentArrowEndStyle = value;
      prefs.set("wb-arrow-style", value);
    }
  }
  wbRefreshArrowStyleControlRef = () => {
    if (arrowStyleSelect) arrowStyleSelect.value = wbCurrentEndStyle();
  };
  if (arrowStyleSelect) {
    arrowStyleSelect.value = wbCurrentEndStyle();
    arrowStyleSelect.addEventListener("change", (e) => wbSetCurrentEndStyle(e.target.value));
  }
  //: **The mark those ends wear** (the owner, 2026-10-11: "more arrow
  //: options"): any of the selection's end kinds, one remembered choice for
  //: both tools; the ends list above says where it goes.
  const arrowHeadSelect = document.getElementById("wb-arrow-head");
  const endList = document.getElementById("wb-prop-endcap");
  if (arrowHeadSelect && endList && !arrowHeadSelect.options.length) {
    for (const node of endList.children) arrowHeadSelect.append(node.cloneNode(true));
    arrowHeadSelect.querySelector('option[value="none"]')?.remove();
  }
  window.currentArrowHead = WB_CAP_KINDS.includes(prefs.get("wb-arrow-head", null)) ? prefs.get("wb-arrow-head", null) : "arrow";
  if (arrowHeadSelect) {
    arrowHeadSelect.value = window.currentArrowHead;
    arrowHeadSelect.addEventListener("change", (e) => {
      window.currentArrowHead = WB_CAP_KINDS.includes(e.target.value) ? e.target.value : "arrow";
      prefs.set("wb-arrow-head", window.currentArrowHead);
    });
  }

  // Fill/stroke-style controls for the shape tools, asked for directly
  // ("stroke width, style, and colour... fill colour/transparency...
  // options for no border/stroke or background"). Persisted the same way
  // every other drawing preference here already is, so a choice survives a
  // reload instead of resetting to "no fill, solid" every session.
  const fillColorInput = document.getElementById("wb-fill-color");
  const fillOpacityInput = document.getElementById("wb-fill-opacity");
  const fillOnInput = document.getElementById("wb-fill-on");
  const strokeStyleSelect = document.getElementById("wb-stroke-style");
  const strokeNoneInput = document.getElementById("wb-stroke-none");

  window.currentFillColor = prefs.get("wb-fill-color", null) || "#3355ff";
  window.currentFillOpacity = Number(prefs.get("wb-fill-opacity", null) ?? 100);
  window.currentFillNone = prefs.get("wb-fill-none", null) !== "off"; // default on (no fill)
  window.currentDashStyle = prefs.get("wb-stroke-style", null) || "solid";
  window.currentStrokeNone = prefs.get("wb-stroke-none", null) === "on";

  if (fillColorInput) {
    fillColorInput.value = window.currentFillColor;
    fillColorInput.addEventListener("input", (e) => {
      window.currentFillColor = e.target.value;
      prefs.set("wb-fill-color", e.target.value);
    });
  }
  if (fillOpacityInput) {
    fillOpacityInput.value = String(window.currentFillOpacity);
    fillOpacityInput.addEventListener("input", (e) => {
      window.currentFillOpacity = Number(e.target.value);
      prefs.set("wb-fill-opacity", e.target.value);
    });
  }
  //: **The switch says Fill, so on means filled** (INBOX 445). It was the
  //: "no fill" checkbox drawn as a switch labelled Fill: on by default, which
  //: read as "shapes are filled" and drew them hollow, and turning it off
  //: filled them. The stored preference keeps its old meaning (`wb-fill-none`,
  //: "on" for hollow), so nobody's saved choice flips.
  if (fillOnInput) {
    fillOnInput.checked = !window.currentFillNone;
    fillOnInput.addEventListener("change", (e) => {
      window.currentFillNone = !e.target.checked;
      prefs.set("wb-fill-none", e.target.checked ? "off" : "on");
    });
  }
  if (strokeStyleSelect) {
    strokeStyleSelect.value = window.currentDashStyle;
    strokeStyleSelect.addEventListener("change", (e) => {
      window.currentDashStyle = e.target.value;
      prefs.set("wb-stroke-style", e.target.value);
    });
  }
  if (strokeNoneInput) {
    strokeNoneInput.checked = window.currentStrokeNone;
    strokeNoneInput.addEventListener("change", (e) => {
      window.currentStrokeNone = e.target.checked;
      prefs.set("wb-stroke-none", e.target.checked ? "on" : "off");
    });
  }

  // Alignment-guide colours: asked for directly ("colours should be
  // alterable"). `wbAlignGuideColor` already reads localStorage on every
  // guide redraw, so these listeners only need to persist the choice; no
  // live guide is showing while this dropdown is open to also repaint.
  for (const kind of ["edge", "center", "spacing"]) {
    const input = document.getElementById(`wb-guide-color-${kind}`);
    if (!input) continue;
    input.value = wbAlignGuideColor(kind);
    input.addEventListener("input", (e) => {
      prefs.set(`wb-guide-color-${kind}`, e.target.value);
    });
  }

  // The properties panel's own controls: each reads `wbSelectedItem` fresh
  // at change time rather than closing over it, since the panel can stay
  // open across several edits to the same selection. The two lookups these
  // use are module-level (see above `wbCopySelectedStyle`): they read only
  // `wbSelectedItem`/`wbState`, and the copy-style actions need them too.
  document.getElementById("wb-copy-style")?.addEventListener("click", wbCopySelectedStyle);
  document.getElementById("wb-paste-style")?.addEventListener("click", wbPasteCopiedStyle);
  document.getElementById("wb-reset-style")?.addEventListener("click", wbResetSelectedStyle);
  document.getElementById("wb-prop-bold")?.addEventListener("click", () => wbWrapTextSelection("**"));
  document.getElementById("wb-prop-italic")?.addEventListener("click", () => wbWrapTextSelection("*"));
  document.getElementById("wb-prop-bullets")?.addEventListener("click", wbBulletTextLines);
  document.getElementById("wb-prop-align")?.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-align]");
    const item = wbSelectedTextObjectOrNull();
    if (!button || !item) return;
    const before = WB_KIND_INFO.object.payload(item);
    wbPushUndo({ action: "move", kind: "object", id: item.id, before });
    item.data = { ...item.data, align: button.dataset.align };
    wbSaveObject(item);
    wbScheduleRender();
    wbUpdateContextBar();
  });
  document.getElementById("wb-prop-md")?.addEventListener("change", (event) => {
    const item = wbSelectedTextObjectOrNull();
    if (!item) return;
    const before = WB_KIND_INFO.object.payload(item);
    wbPushUndo({ action: "move", kind: "object", id: item.id, before });
    item.data = { ...item.data, md: event.target.checked };
    wbSaveObject(item);
    wbScheduleRender();
  });
  // The context bar's action buttons reuse the keyboard paths exactly
  // (Ctrl+D, [ ], Delete) so the two can never disagree.
  const selBar = document.getElementById("wb-context");
  if (selBar) {
    // Keep the board's focus, but not on the controls people type into or
    // drag: swallowing mousedown on the whole bar took the caret out of the
    // width field and stopped a slider taking a drag at all.
    selBar.addEventListener("mousedown", (e) => {
      if (e.target.closest("input, select, textarea, [contenteditable=true]")) return;
      e.preventDefault();
    });
    //: One step each (FEAT-07); the bar's two are the step pair, and the
    //: Arrange menu and the right-click menu add the front and back.
    const actions = {
      "wb-selbar-duplicate": () => {
        wbDuplicateSelection();
      },
      "wb-selbar-back": () => wbStepSelectionZOrder(-1),
      "wb-selbar-forward": () => wbStepSelectionZOrder(1),
      "wb-selbar-to-back": () => wbSendSelectionZOrder(false),
      "wb-selbar-to-front": () => wbSendSelectionZOrder(true),
      "wb-selbar-delete": () => deleteWbSelection(),
      "wb-selbar-export": () => wbExportBoard(document.getElementById("wb-selbar-export")),
    };
    for (const [id, fn] of Object.entries(actions)) {
      document.getElementById(id)?.addEventListener("click", (e) => { e.stopPropagation(); fn(); });
    }
  }
  document.getElementById("wb-prop-color")?.addEventListener("change", async (e) => {
    const sketch = wbSelectedSketchOrNull();
    if (sketch) {
      const before = WB_KIND_INFO.sketch.payload(sketch);
      wbPushUndo({ action: "move", kind: "sketch", id: sketch.id, before });
      await wbSaveSketchProps(sketch, { color: e.target.value });
      wbScheduleRender();
      return;
    }
    const obj = wbSelectedTextObjectOrNull();
    if (obj) {
      const before = WB_KIND_INFO.object.payload(obj);
      wbPushUndo({ action: "move", kind: "object", id: obj.id, before });
      obj.data = { ...obj.data, color: e.target.value };
      await wbSaveObject(obj);
      wbScheduleRender();
    }
  });
  document.getElementById("wb-prop-width")?.addEventListener("change", async (e) => {
    const sketch = wbSelectedSketchOrNull();
    if (!sketch) return;
    const width = Math.max(1, Math.min(40, Number(e.target.value) || 3));
    const before = WB_KIND_INFO.sketch.payload(sketch);
    wbPushUndo({ action: "move", kind: "sketch", id: sketch.id, before });
    await wbSaveSketchProps(sketch, { width });
    wbScheduleRender();
  });
  // Start/end cap dropdowns: independently per end (asked for directly),
  // replacing the single shared "which end gets an arrowhead" control.
  // Shared by both: reads the *other* end's current cap first (from
  // whichever field it's actually stored in, the explicit new one, or
  // the legacy `endStyle` for a link that predates it) so changing one end
  // never silently resets the other.
  async function wbSetCap(which, value) {
    const sketch = wbSelectedSketchOrNull();
    if (!sketch) return;
    const before = WB_KIND_INFO.sketch.payload(sketch);
    wbPushUndo({ action: "move", kind: "sketch", id: sketch.id, before });
    let linkParsed = null;
    try {
      const candidate = JSON.parse(sketch.data);
      if (candidate && (candidate.type || "").startsWith("link-")) linkParsed = candidate;
    } catch { /* not a link */ }
    if (linkParsed) {
      // A link's caps are computed at render time from `startCap`/`endCap`
      // (`wbLinkPathD`), not baked into a stored path the way a drawn
      // arrow's is: nothing to regenerate, just persist the choice.
      const current = wbLinkCaps(linkParsed);
      current[which] = value;
      await wbSaveSketchProps(sketch, {
        startCap: current.startCap, endCap: current.endCap, endStyle: undefined, ...wbCapSizeFields(current),
      });
      wbScheduleRender();
      return;
    }
    const parsed = wbSketchParsedData(sketch);
    if (!wbSketchTakesCaps(parsed)) return;
    const current = wbSketchCaps(parsed);
    current[which] = value;
    const headLen = (parsed.width || wbPen.width) * 4 + 6;
    const newD = wbRegenerateShapeCaps(parsed.d, current.startCap, current.endCap, headLen, current);
    await wbSaveSketchProps(sketch, { d: newD, startCap: current.startCap, endCap: current.endCap, ...wbCapSizeFields(current) });
    wbScheduleRender();
  }
  document.getElementById("wb-prop-startsize")?.addEventListener("change", (e) => wbSetCap("startSize", e.target.value));
  document.getElementById("wb-prop-endsize")?.addEventListener("change", (e) => wbSetCap("endSize", e.target.value));
  document.getElementById("wb-prop-startcap")?.addEventListener("change", (e) => wbSetCap("startCap", e.target.value));
  document.getElementById("wb-prop-route")?.addEventListener("change", (e) => wbSetLinkRoute(e.target.value));
  document.getElementById("wb-prop-label")?.addEventListener("click", () => {
    const sketch = wbSelectedItem?.kind === "sketch" ? wbFindItem("sketch", wbSelectedItem.id) : null;
    if (sketch) wbEditLinkLabel(sketch);
  });
  document.getElementById("wb-prop-endcap")?.addEventListener("change", (e) => wbSetCap("endCap", e.target.value));
  document.getElementById("wb-prop-bg")?.addEventListener("change", async (e) => {
    const obj = wbSelectedTextObjectOrNull();
    if (!obj) return;
    const before = WB_KIND_INFO.object.payload(obj);
    wbPushUndo({ action: "move", kind: "object", id: obj.id, before });
    obj.data = { ...obj.data, bg: e.target.value };
    document.getElementById("wb-prop-bg-none").checked = false;
    await wbSaveObject(obj);
    wbScheduleRender();
  });
  document.getElementById("wb-prop-bg-none")?.addEventListener("change", async (e) => {
    const obj = wbSelectedTextObjectOrNull();
    if (!obj) return;
    const before = WB_KIND_INFO.object.payload(obj);
    wbPushUndo({ action: "move", kind: "object", id: obj.id, before });
    // "transparent" is a real, distinguishable value, `bg || ""` (the
    // render path) would otherwise fall back to the CSS default translucent
    // panel look for an empty string, not the "no fill at all" this asks
    // for. Asked for directly: "options for no border/stroke or background".
    obj.data = { ...obj.data, bg: e.target.checked ? "transparent" : document.getElementById("wb-prop-bg").value };
    await wbSaveObject(obj);
    wbScheduleRender();
  });
  document.getElementById("wb-prop-border")?.addEventListener("change", async (e) => {
    const obj = wbSelectedTextObjectOrNull();
    if (!obj) return;
    const before = WB_KIND_INFO.object.payload(obj);
    wbPushUndo({ action: "move", kind: "object", id: obj.id, before });
    obj.data = { ...obj.data, border_color: e.target.value };
    document.getElementById("wb-prop-border-none").checked = false;
    await wbSaveObject(obj);
    wbScheduleRender();
  });
  document.getElementById("wb-prop-border-none")?.addEventListener("change", async (e) => {
    const obj = wbSelectedTextObjectOrNull();
    if (!obj) return;
    const before = WB_KIND_INFO.object.payload(obj);
    wbPushUndo({ action: "move", kind: "object", id: obj.id, before });
    obj.data = { ...obj.data, border_color: e.target.checked ? "transparent" : document.getElementById("wb-prop-border").value };
    await wbSaveObject(obj);
    wbScheduleRender();
  });
  document.getElementById("wb-prop-dash")?.addEventListener("change", async (e) => {
    const sketch = wbSelectedSketchOrNull();
    if (!sketch) return;
    const before = WB_KIND_INFO.sketch.payload(sketch);
    wbPushUndo({ action: "move", kind: "sketch", id: sketch.id, before });
    await wbSaveSketchProps(sketch, { dash: e.target.value === "solid" ? undefined : e.target.value });
    wbScheduleRender();
  });
  document.getElementById("wb-prop-nostroke")?.addEventListener("change", async (e) => {
    const sketch = wbSelectedSketchOrNull();
    if (!sketch) return;
    const before = WB_KIND_INFO.sketch.payload(sketch);
    wbPushUndo({ action: "move", kind: "sketch", id: sketch.id, before });
    await wbSaveSketchProps(sketch, { noStroke: e.target.checked || undefined });
    wbScheduleRender();
  });
  document.getElementById("wb-prop-shapefill")?.addEventListener("change", async (e) => {
    document.getElementById("wb-prop-shapefill-on").checked = true;
    document.getElementById("wb-prop-shapefill").classList.remove("wb-colour-off");
    await wbFmtApply("fill", (entry) => (entry.kind === "sketch" ? wbColour.fillColour("sketch", wbFmtSketch(entry), e.target.value) : null), "Fill colour changed.");
  });
  //: The same toggle as the Format panel's (`wbFillTogglePatch`): off keeps the
  //: shape's colour, on brings it back (INBOX 1685).
  document.getElementById("wb-prop-shapefill-on")?.addEventListener("change", async (e) => {
    document.getElementById("wb-prop-shapefill").classList.toggle("wb-colour-off", !e.target.checked);
    const colour = document.getElementById("wb-prop-shapefill").value;
    await wbFmtApply("fill", (entry) => (entry.kind === "sketch" ? wbColour.fillToggle("sketch", wbFmtSketch(entry), e.target.checked, colour) : null),
      e.target.checked ? "Filled." : "Fill taken off.");
    wbUpdateContextBar();
  });
  document.getElementById("wb-prop-fontsize")?.addEventListener("change", async (e) => {
    const obj = wbSelectedTextObjectOrNull();
    if (!obj) return;
    const before = WB_KIND_INFO.object.payload(obj);
    wbPushUndo({ action: "move", kind: "object", id: obj.id, before });
    const fontSize = Math.max(8, Math.min(200, Number(e.target.value) || 16));
    obj.data = { ...obj.data, font_size: fontSize };
    await wbSaveObject(obj);
    wbScheduleRender();
  });
  document.getElementById("wb-multi-group")?.addEventListener("click", wbGroupSelection);
  document.getElementById("wb-multi-ungroup")?.addEventListener("click", wbUngroupSelection);
  document.getElementById("wb-align-left")?.addEventListener("click", () => wbAlignSelection("left"));
  document.getElementById("wb-align-hcenter")?.addEventListener("click", () => wbAlignSelection("hcenter"));
  document.getElementById("wb-align-right")?.addEventListener("click", () => wbAlignSelection("right"));
  document.getElementById("wb-align-top")?.addEventListener("click", () => wbAlignSelection("top"));
  document.getElementById("wb-align-vcenter")?.addEventListener("click", () => wbAlignSelection("vcenter"));
  document.getElementById("wb-align-bottom")?.addEventListener("click", () => wbAlignSelection("bottom"));
  document.getElementById("wb-distribute-h")?.addEventListener("click", () => wbDistributeSelection("horizontal"));
  document.getElementById("wb-distribute-v")?.addEventListener("click", () => wbDistributeSelection("vertical"));
  document.getElementById("wb-same-width")?.addEventListener("click", () => wbSameSizeSelection("width"));
  document.getElementById("wb-same-height")?.addEventListener("click", () => wbSameSizeSelection("height"));
  document.getElementById("wb-extract-notes")?.addEventListener("click", wbExtractNotes);
  document.getElementById("wb-mindmap-tree")?.addEventListener("click", () => {
    if (wbSelectedItem?.kind === "node") wbArrangeMindMap(wbSelectedItem.id, "tree");
  });
  document.getElementById("wb-mindmap-radial")?.addEventListener("click", () => {
    if (wbSelectedItem?.kind === "node") wbArrangeMindMap(wbSelectedItem.id, "radial");
  });

  //: The active board's container, read when a handler runs: the same element
  //: for the page board, an embed's own box for an embed (L-whiteboard-54).
  const boardEl = () => wbInstances.container();
  const undoBtn = document.getElementById("wb-undo");

  function updateWbCursor() {
    boardEl().setAttribute("data-current-tool", window.currentTool);
    boardEl().style.cursor = wbCursorForTool(window.currentTool, window.currentStrokeColor, wbPen.width);
  }

  // The six shape tools folded into the toolbar's own dropdown: asked for
  // directly ("the tool bar is getting quite long"). Kept as one list so
  // the toggle button's own icon/active-state and the arrow-style control's
  // relevance can both key off it without drifting apart.
  const WB_SHAPE_TOOLS = new Set(["line", "arrow", "rect", "circle", "triangle", "diamond", ...Object.keys(WB_MORE_SHAPES)]);
  let lastShapeTool = "line"; // what a plain click on the toggle (not the caret) selects
  const shapeToggle = document.getElementById("wb-shape-toggle");
  const shapeToggleIcon = document.getElementById("wb-shape-toggle-icon");
  const shapeMenu = document.getElementById("wb-shape-menu");

  // The selection tools were a dropdown; they are three peer buttons now
  // (see index.html) so there is no toggle left to keep in sync.

  // The one place a tool switch happens, so the toolbar click and the
  // keyboard shortcuts below can never drift out of sync with each other.
  function selectWbTool(tool) {
    wbPen.abandon?.();
    wbPen.dropLost?.();
    window.currentTool = tool;
    //: A link tool's anchor dots belong to that tool (INBOX 573).
    if (!String(tool).startsWith("link-") && !wbLinkDragActive) wbClearAnchorHints();
    // The zoom behaviour stays attached for every tool. It used to be
    // detached for all but Pan so a drag could not fight drawing, but
    // `wbZoomFilter` (top of file) now makes that decision per event, and
    // detaching also removed **wheel zoom**, so you could not zoom or scroll
    // the canvas while any drawing tool was selected without switching tool
    // and switching back. That was a large part of the reported "constantly
    // having to switch between tools".
    d3.select(wbInstances.container()).call(wbZoom).on("dblclick.zoom", null);
    showWbTool(tool);
    wbFmtState.hints?.toolHint(tool);
  }

  //: What a tool switch shows: the rail's mark, the shape toggle, the cursor, the status and the
  //: context bar. Also run alone, as `wbSelectToolRef.swap`, when a board instance goes live with
  //: its own tool (L-whiteboard-61): a stroke or a drag still going on is left alone (an embed's
  //: reload swaps boards for its draw, mid-stroke included), and no first-use hint is shown.
  function showWbTool(tool) {
    if (toolGroup) {
      toolGroup.querySelectorAll("button[data-tool]").forEach((b) => {
        b.classList.toggle("active", b.dataset.tool === tool);
      });
    }
    // The toggle shows whichever shape is actually active (and reads as
    // "on" the same way any other tool button does) instead of a fixed
    // icon: picking "circle" from the menu should look exactly like
    // picking "circle" used to when it was its own top-level button.
    if (shapeToggle && WB_SHAPE_TOOLS.has(tool)) {
      lastShapeTool = tool;
      const chosen = shapeMenu?.querySelector(`button[data-tool="${tool}"] svg`);
      if (chosen && shapeToggleIcon) shapeToggleIcon.innerHTML = chosen.innerHTML;
      shapeToggle.classList.add("active");
    } else if (shapeToggle) {
      shapeToggle.classList.remove("active");
    }
    if (shapeMenu && shapeToggle) wbCloseDockedMenu(shapeMenu, shapeToggle);
    wbRefreshArrowStyleControlRef?.();
    wbToolsOpenerSync.fn?.();
    updateWbCursor();
    wbFmtState.effects?.refreshStatus();
    // The properties panel now also carries the style a drawing tool will
    // use, so a tool switch has to reopen/close it, see its own comment.
    wbUpdateContextBar();
  }

  wbSelectToolRef = Object.assign(selectWbTool, {
    swap(tool) {
      window.currentTool = tool;
      showWbTool(tool);
    },
  });

  if (toolGroup) {
    toolGroup.addEventListener("click", (e) => {
      const btn = e.target.closest("button[data-tool]");
      if (btn) selectWbTool(btn.dataset.tool);
    });
  }

  //: Tools sheet and docked menus (whiteboard-toolsheet.js): it shares only the names passed and returned here.
  const { wbCloseDockedMenu, wbWireToggleGestures } = wbInitToolsSheet({ toolGroup, wbToolsOpenerSync, selectWbTool });

  wbWireToggleGestures(shapeToggle, shapeMenu, () => lastShapeTool);

  //: Board menus and keyboard shortcuts (whiteboard-menus.js): it shares only the names passed and returned here.
  wbInitMenus({ updateWbCursor, undoBtn, selectWbTool });

  //: Drawing, erasing and marquee select (whiteboard-pointer.js): it shares only the names passed and returned here.
  const { getLogicalMouse, zoomK } = wbInitPointer({ selectWbTool, boardEl });

  //: Pen strokes (whiteboard-strokes.js): it shares only the names passed and returned here.
  wbInitStrokes({ wbPen, getLogicalMouse, zoomK });

  // Drop handler for Library
  wbInstances.on("dragover", (e) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "copy";
  });
  
  wbInstances.on("drop", async (e) => {
    e.preventDefault();
    const dropped = e.dataTransfer.getData("text/plain");
    if (!dropped) return;
    //: **Only a note id may be dropped here.** `text/plain` is whatever the
    //: drag carried, and a selection, a url or a filename all satisfy a bare
    //: truthiness test: `parseInt` then gave `NaN`, `JSON.stringify` wrote it
    //: as `null`, and the server answered 422 with "entry_id: Input should be
    //: a valid integer, input: null". Seen in the owner's console on
    //: 2026-09-09, beside an "Error creating node: {}" that said nothing.
    const entryId = Number.parseInt(dropped, 10);
    if (!Number.isInteger(entryId) || entryId <= 0) {
      toast("Drop a note from the Library onto the board. That was not a note.", "info");
      return;
    }
    
    // Reported directly: "I dragged a note from the library dropdown onto
    // the board but the note appeared in the top left, not in the centre
    // where I placed it." The point is read against the container, the
    // element `d3.zoom` is attached to, which never itself carries the pan
    // and zoom (the layers inside it do), in the one conversion every drop
    // shares (`wbClientToBoard`).
    const at = wbClientToBoard(e.clientX, e.clientY);

    wbPlaceNote(entryId, at);
  });


  
  await fetchWhiteboardState();
  wbScheduleRender();
}

window.currentBoardId = null;

//: Create a board: or a map, which is the same thing with a `type` on it
//: (MINDMAP_PLAN.md §4 chose option B: one data model, two behaviours).
//:
//: `preset` lets the Library's "New mind map" action skip straight to the map
//: half without the dialog having to be answered twice; left alone, the dialog
//: asks, defaulting to whatever it was told.
//: **The kind the dialog opens on** (INBOX 183: "still no default board type
//: selected"). Measured before changing anything
//: (`scratchpad/ui-sweeps/newboard.js`): a kind *was* pre-selected, and
//: visibly, Board filled with the accent against a transparent Mind map. What
//: was missing is that it was always Board, so someone building maps chose Mind
//: map on every single one. The last kind actually created is remembered here
//: and becomes the default; an explicit `preset` (the Library's "New mind map")
//: still wins, and a first run with nothing remembered is Board as before.
const WB_LAST_BOARD_KIND = "wbLastBoardKind";

//: A handle drag's dx/dy (board-space) turned into the same
//: {sx, sy, anchorX, anchorY} shape `wbTransformPathD` takes: the opposite
//: corner/edge from whichever handle moved stays fixed, mirroring
//: `resizeDrag`'s own width/height-and-floor logic for image/text objects.
const WB_SKETCH_MIN_SIZE = 10;

// whiteboard-sketch-text.js: whiteboard-sketch-text.js: text inside shapes, fit-to-shape, connector labels an (moved out, L286).

//: The middle of a link's shaft: the first subpath of its drawn `d`, before
//: any arrowhead strokes appended after it, measured on one hidden path so
//: a curve's middle is where the curve is rather than the chord's.
let wbLinkMeasurePath = null;

// Coalesce a burst of state changes into one paint.
//
// **This is the cause of the whiteboard feeling "janky and uncomfortable".**
// renderWhiteboard() below is a full d3 data-join over every sketch, node and
// object on the board, and it was called directly from 48 places. A single
// user action routinely touches several of them, move a card, update its
// links, mark the board dirty, refresh the selection, so one drag or one
// paste could repaint the entire board three or four times in the same frame,
// each pass re-joining every item and re-binding every handler.
//
// Nothing here makes the render itself cheaper. It makes it happen once per
// frame instead of once per state change, which is where the wasted work
// actually was. requestAnimationFrame rather than a microtask because the
// point is to land exactly one paint per displayed frame.
//
// **Safe to batch because no caller reads the DOM straight after rendering**, 
// checked across all 48 sites before converting them; a call followed by a
// getBoundingClientRect or querySelector would have needed to stay synchronous
// and none was. `renderWhiteboardNow()` is kept for anything that ever does.
let wbRenderQueued = false;
//: The queued frame itself, so a synchronous render can call it off rather
//: than merely lower the flag it checks (MINDMAP_PLAN.md §13a). Without this
//: `renderWhiteboardNow` left the frame standing: opening a board queues a
//: render, renders synchronously to measure the nodes for the fit, and then
//: paid for a second full render of the same unchanged board one frame later.
//: On a 500-topic map that was the whole board rendered twice on every open.
let wbRenderFrame = 0;

//: **A floating bar or popover tied to an item closes when the item leaves
//: the board** (INBOX 1510(b): the text-format bar stayed after the box a
//: quick-add arrow made was deleted). Delete, undo, cut and a board switch
//: all end in a render, so the render asks once: an editor whose element is
//: gone (editor.js `editorCloseOrphans`), and each popover below whose item
//: is no longer in the board's state. Read by item, not by element, because
//: a render rebuilds the elements of items that are still here.
const WB_ITEM_POPOVERS = [
  { ref: () => wbCommentState && { kind: wbCommentState.kind, id: wbCommentState.id }, close: () => wbCloseComments() },
  { ref: () => typeof wbMapNoteState !== "undefined" && wbMapNoteState && { kind: "object", id: wbMapNoteState.id }, close: () => wbMapCloseNote() },
  { ref: () => typeof wbMarkerUi !== "undefined" && wbMarkerUi.pop && { kind: "object", id: wbMarkerUi.pop.id }, close: () => wbMapCloseMarkers() },
  { ref: () => typeof wbMapRadialFor !== "undefined" && wbMapRadialFor != null && { kind: "object", id: wbMapRadialFor }, close: () => wbCloseMapRadial() },
  { ref: () => typeof wbMapLinkRadialFor !== "undefined" && wbMapLinkRadialFor != null && { kind: "object", id: wbMapLinkRadialFor }, close: () => wbCloseMapLinkRadial() },
];

// The unbatched escape hatch. Prefer wbScheduleRender(); use this only when
// the very next statement has to read the rendered DOM.
function renderWhiteboardNow() {
  //: Whether a queued frame was called off, so the one thing it did that this
  //: function does not (the selection bar, below) still happens, and in the
  //: order that frame would have done it in.
  let cancelled = false;
  if (wbRenderFrame) {
    cancelAnimationFrame(wbRenderFrame);
    wbRenderFrame = 0;
    cancelled = true;
  }
  wbRenderQueued = false;
  renderWhiteboard();
  if (cancelled) wbUpdateSelectionBar();
  // A render replaces card elements, so the search highlight classes are gone
  // with them and the navigator's item rectangles are stale. Both re-apply
  // from state rather than being re-derived by their own callers.
  wbApplySearchHighlight();
  //: The navigator and the picker's count are the page board's chrome: an
  //: embed's draw (wbInstances' `draw`) leaves them be (L-whiteboard-58).
  if (!wbInstances.active.container) {
    wbRenderNavigator();
    wbSyncBoardCount();
  }
  wbMapAfterRender();
}

//: The pieces of one render, by job. Properties of the function so they add no names to the shared scope.
renderWhiteboard.parts = {};

//: The empty-board hint and cue, from what the board holds now.
renderWhiteboard.parts.wbSyncEmptyHint = function wbSyncEmptyHint() {
  // Objects count too: a board holding only a text box or an image is
  // not empty, and left out of this sum the hint sat on top of them.
  const wbBoardHolds = (wbState.nodes?.length || 0) + (wbState.sketches?.length || 0) + (wbState.objects?.length || 0);
  // Asked for directly: an option to turn the hint off entirely, once
  // it's served its purpose, `localStorage`, the same durability the
  // onboarding tour's own "don't show again" already uses.
  // `wbHintForcedOpen` overrides both checks: the "?" help button's way
  // back after a dismiss, or on a board that already has content.
  // A map gets `#wb-map-empty` instead: this panel is the whiteboard's
  // own help, and on an emptied map it was pens, shapes and the eraser
  // sitting over a surface none of them apply to.
  const wbHintHidden = !wbHintForcedOpen && (wbIsMap() || wbBoardHolds > 0 || prefs.get("wbEmptyHintDismissed", null) === "1");
  //: Both are the page board's: an embedded board's render leaves them be (L-whiteboard-58).
  if (!wbInstances.active.container) {
    document.getElementById("wb-empty-hint")?.classList.toggle("hidden", wbHintHidden);
    //: A card turned off still leaves one line on an empty board (audit 1028 B34).
    document.getElementById("wb-empty-cue")?.classList.toggle("hidden", !(wbHintHidden && !wbIsMap() && wbBoardHolds === 0));
  }
};

// Move: reported directly: "can't move objects made or drawn on
// whiteboard". Cards/objects get this from their own `d3.drag`; a sketch
// never had one at all. Filtered to the Select tool only, the same as a
// click here means "select" rather than "erase", under any other tool
// (pan, a brush, eraser/delete) this must stay out of the way entirely,
// pan in particular, since the canvas's own zoom/pan drag needs an
// unclaimed pointerdown to reach it.
renderWhiteboard.parts.wbSketchDrag = function wbSketchDrag() {
  return d3.drag()
    .clickDistance(WB_CLICK_SLOP)
    .filter((event) => !wbIsSecondTouch(event) && !event.button && (window.currentTool === "select" || Boolean(window.currentTool?.startsWith("link-"))))
    .on("start", renderWhiteboard.parts.wbSketchDragStart)
    .on("drag", renderWhiteboard.parts.wbSketchDragMove)
    .on("end", renderWhiteboard.parts.wbSketchDragEnd);
};

renderWhiteboard.parts.wbSketchDragStart = function wbSketchDragStart(event, d) {
  event.sourceEvent.stopPropagation();
  // A link tool drags a *link* out of the shape, not the shape, the same
  // delegation `objDrag` does for text boxes and stickies.
  if (window.currentTool?.startsWith("link-")) {
    if (!wbSketchParsedData(d)) return;
    d._linkKind = "sketch";
    return dragStart.call(this, event, d);
  }
  const parsed = wbSketchParsedData(d);
  d._linkedSketches = wbLinkedSketchesFor(d.id, "sketch");
  d._dragOriginalD = parsed ? parsed.d : null;
  d._moveUndoBefore = WB_KIND_INFO.sketch.payload(d);
  d._altCopy = Boolean(event.sourceEvent?.altKey);
  //: A connector drawn between two cards has no path of its own to carry (its ends follow the cards), so it starts
  //: no move: the delete target came up on its drag and stayed (INBOX 1405).
  d._gesture = d._dragOriginalD == null ? null : wbBeginGesture(() => wbRestoreMove("sketch", d), true);
  // Raw (never-snapped) running totals, applied fresh from the
  // *original* d each frame, the same fix as `dragging`'s own comment
  // above: re-snapping an already-snapped value every frame discards
  // the sub-grid remainder and can get stuck.
  d._dragRawDX = 0;
  d._dragRawDY = 0;
  // Selection itself is deliberately *not* touched here, it lives
  // entirely in the 'click' listener below, which only ever fires for a
  // genuinely unmoved gesture (d3 suppresses the native click once real
  // movement crosses the threshold). Doing it here too, keyed off "did
  // this drag start", was tried and had a real bug: `wbDragIsBulkMove`
  // is also true for a second shift-click meant to *toggle a member
  // back off* an existing multi-selection, so treating every "start" as
  // "begin a bulk move" swallowed that click's toggle entirely: a
  // second shift-click on an already-selected item did nothing.
  // `d._bulkOrigin` itself is decided lazily, on the first real "drag"
  // frame below, for the same reason.
};

renderWhiteboard.parts.wbSketchDragMove = function wbSketchDragMove(event, d) {
  if (d._linkKind === "sketch") return dragging.call(this, event, d);
  if (d._dragOriginalD == null || d._gesture?.cancelled) return;
  const step = wbTouchSlopStep(d._gesture, event, d3.zoomTransform(wbInstances.container()).k);
  if (!step) return;
  // First real movement of this gesture, decide once whether this is
  // a solo move or a bulk move of the whole multi-selection. Decided
  // here rather than "start" (see its own comment) specifically so
  // a zero-movement click never reaches this at all.
  if (d._bulkOrigin === undefined) {
    d._bulkOrigin = wbDragIsBulkMove("sketch", d.id)
      ? wbCaptureBulkMoveOrigin(wbMultiKey("sketch", d.id))
      : null;
  }
  // Board units already, no `/ transform.k`: this drag's container is the
  // sketch group's parent inside the zoomed `#wb-zoom-group` (see the link
  // endpoint handle's own note). A shape dragged at 2x followed the
  // pointer at half speed until this was measured: 30px of travel for a
  // 60px drag, against the card beside it, which moved the full 60.
  d._dragRawDX += step.dx;
  d._dragRawDY += step.dy;
  const bypassSnap = event.sourceEvent?.altKey;
  const lock = wbAxisLock(d._dragRawDX, d._dragRawDY, event.sourceEvent?.shiftKey);
  let dx = lock === "y" ? 0 : wbSnap(d._dragRawDX, bypassSnap);
  let dy = lock === "x" ? 0 : wbSnap(d._dragRawDY, bypassSnap);
  //: **A sketch gets the alignment guides too.** Reported: "Alignment bars
  //: don't appear for group selections". Measured, a group of *cards* has
  //: had them since `wbBulkGroupBox` landed, and they draw correctly; this
  //: handler is the one that never asked for them at all, solo or in a
  //: group. So a marquee that happened to catch a sketch, dragged by that
  //: sketch, was the one selection on the board with no guides, which is
  //: exactly the report.
  //:
  //: A sketch has no x/y/width/height, only a path, so its box comes from
  //: `wbPathBBox` and goes into the shared union through `self`.
  if (!bypassSnap) {
    const origin = wbPathBBox(d._dragOriginalD);
    if (origin) {
      const group = wbBulkGroupBox(d, "sketch", { ...origin, dx, dy });
      const box = group || {
        x: origin.minX + dx,
        y: origin.minY + dy,
        w: origin.maxX - origin.minX,
        h: origin.maxY - origin.minY,
      };
      const snap = wbAlignmentGuides(
        wbDragExcludeKeys(d, "sketch"), box.x, box.y, box.w, box.h, wbAlignTol()
      );
      if (lock !== "y") dx += snap.dx;
      if (lock !== "x") dy += snap.dy;
      wbShowAlignmentGuides(snap.guideLines);
    }
  } else {
    wbClearAlignmentGuides();
  }
  const newD = wbTransformPathD(d._dragOriginalD, { dx, dy });
  d._dragLiveD = newD;
  const el = wbInstances.query(`.sketch-group[data-id="${d.id}"]`);
  el?.querySelector(".sketch-path")?.setAttribute("d", newD);
  el?.querySelector(".sketch-hitbox")?.setAttribute("d", newD);
  wbNudgeShapeLabel(el, dx, dy);
  if (d._bulkOrigin) wbApplyBulkMove(d._bulkOrigin, dx, dy);
  if (d._linkedSketches?.length) wbUpdateLinkedSketches(d.id, d._linkedSketches);
  wbQueueSelectionBar();
  // Handles would otherwise trail the sketch by a whole render, cheap
  // to keep in step since there are at most 8 of them.
  wbClearSketchHandles();
};

renderWhiteboard.parts.wbSketchDragEnd = async function wbSketchDragEnd(event, d) {
  //: Every exit, before the early returns below: a guide left on the
  //: canvas after the drag that drew it is a line pointing at nothing.
  wbClearAlignmentGuides();
  if (d._linkKind === "sketch") {
    const r = dragEndNode.call(this, event, d);
    d._linkKind = null;
    return r;
  }
  if (d._dragOriginalD == null) {
    delete d._linkedSketches;
    return;
  }
  //: Dropped on the delete target: put back, then deleted (INBOX 660).
  wbTrashTake(d._gesture, "sketch", d);
  delete d._linkedSketches;
  const finalD = d._dragLiveD;
  const bulkOrigin = d._bulkOrigin;
  const moveBefore = d._moveUndoBefore;
  const altCopy = d._altCopy;
  delete d._dragOriginalD;
  delete d._dragRawDX;
  delete d._dragRawDY;
  delete d._dragLiveD;
  delete d._bulkOrigin;
  delete d._moveUndoBefore;
  delete d._altCopy;
  const cancelled = wbEndGesture(d._gesture);
  delete d._gesture;
  if (cancelled) {
    wbScheduleRender();
    return;
  }
  // `finalD`/`bulkOrigin` are only ever set once real movement occurred
  // (in "drag" above): a zero-movement click leaves both undefined, so
  // this correctly does nothing rather than a wasted save.
  if (finalD) await wbSaveSketchD(d, finalD);
  await wbFinishDrag(
    finalD && moveBefore ? { action: "move", kind: "sketch", id: d.id, before: moveBefore } : null,
    bulkOrigin, altCopy
  );
  wbScheduleRender();
};

//: A new sketch's group: its drag, double-click, path, hit band and context menu.
renderWhiteboard.parts.wbEnterSketches = function wbEnterSketches(sketchSelection, sketchDrag) {
  const sketchEnter = sketchSelection.enter()
    .append("g")
    .attr("class", "sketch-group")
    .attr("data-id", d => d.id)
    .call(sketchDrag)
    .on("dblclick", async (event, d) => {
      // Asked for directly: "double click on lines, add points for curving
      // lines and connections." Only a link has a bend; a drawn shape's own
      // double-click is left to whatever else wants it.
      let parsed = null;
      try { parsed = JSON.parse(d.data); } catch { parsed = null; }
      //: A closed shape's double-click types into it (decision 12).
      if (wbJustDrilled()) { event.stopPropagation(); return; }
      if (wbShapeLabelKind(parsed) && (window.currentTool === "select" || window.currentTool === "pan")) {
        event.stopPropagation();
        event.preventDefault();
        if (window.currentTool === "pan") wbSelectToolRef?.("select");
        selectWbItem("sketch", d.id);
        wbEditShapeLabel(d);
        return;
      }
      if (!parsed || !(parsed.type || "").startsWith("link-")) return;
      event.stopPropagation();
      if (["er", "iso", "loop"].includes(wbLinkShape(parsed)?.route)) {
        toast("This line is drawn from its two ends. Change the line shape to add bends.", "info");
        return;
      }
      const endpoints = wbResolveLinkEndpoints(parsed);
      if (!endpoints) return;
      const [px, py] = wbClientToBoard(event.clientX, event.clientY);
      //: A bend through the click, among the link's others in the order
      //: the line passes them (every connector style, wb-phase2 step 1).
      const live = { ...parsed, bend: undefined, points: wbLinkWaypoints(parsed, endpoints) };
      const points = wbWaypointInsert(live.points, wbLinkDrawnLine(live, endpoints), { x: px, y: py })
        .map((p) => ({ x: Math.round(p.x), y: Math.round(p.y) }));
      const before = WB_KIND_INFO.sketch.payload(d);
      await wbSaveSketchProps(d, { points, bend: undefined });
      wbPushUndo({ action: "move", kind: "sketch", id: d.id, before });
      wbAnnounce("Bend added. Drag it to move it, double-click it to take it out.");
      wbSelectToolRef?.("select");
      selectWbItem("sketch", d.id);
      wbScheduleRender();
    })
    .on("click", (event, d) => {
      // ROADMAP row 0(b), asked for directly: with the Hand active, a plain
      // click on something switches to Select and selects it. A pan is a
      // drag; a click that moved nothing is a choice of *this*, and every
      // whiteboard app (Miro, FigJam, tldraw) reads it that way.
      if (window.currentTool === "select" || window.currentTool === "pan") {
        event.stopPropagation(); // don't also hit the "empty canvas clears selection" handler
        if (window.currentTool === "pan") wbSelectToolRef?.("select");
        wbHandleItemClick("sketch", d.id, event);
        return;
      }
      // Reported directly, same family as the pen's single-click dot: a
      // plain click with the eraser (no drag across anything) did nothing, 
      // only `mouseenter` while `wbErasing` was true caught a stroke, which
      // needs movement to fire at all. The eraser is "delete, but you can
      // also drag across several", a single click should erase the one
      // thing clicked, the same as the delete tool does.
      if (window.currentTool === "delete" || window.currentTool === "eraser") wbDeleteSketch(d);
      if (window.currentTool === "bucket") { event.stopPropagation(); wbBucketFillSketch(d); }
    })
    .on("pointerenter", (event, d) => {
      if (window.currentTool === "eraser" && wbErasing) wbDeleteSketch(d);
    });

  sketchEnter.append("path")
    .attr("class", "sketch-hitbox")
    .attr("fill", "none")
    .attr("stroke", "transparent")
    .attr("stroke-width", "20")
    // A closed shape (rect/circle/triangle/diamond) reads as solid, so
    // clicking its interior should select it, not just the ~20px band
    // around its outline that's the only sensible hit-area an open pen/line
    // squiggle has. Reported directly ("shapes are hard to select"): every
    // sketch used `pointer-events: stroke`, so a rectangle's hollow middle
    // silently didn't count as a click on it.
    .attr("pointer-events", (d) => wbSketchIsClosedShape(d) ? "all" : "stroke");

  sketchEnter.append("path")
    .attr("class", "sketch-path")
    .attr("fill", "none")
    .attr("stroke-width", "3")
    .attr("stroke-linecap", "round")
    .attr("stroke-linejoin", "round")
    .attr("pointer-events", "none");

  wbWireContextMenu(sketchEnter, "sketch");
  return sketchEnter;
};

//: The link and cross-link classes on every sketch group.
renderWhiteboard.parts.wbClassSketches = function wbClassSketches(sketchUpdate) {
  // A cross-link on a map is drawn dashed (MINDMAP_PLAN.md §5 item 9, the
  // systems-map convention for "related, but not part of the tree"). The
  // sketch itself is untouched, this is a class, so the same link on an
  // ordinary board still draws exactly as it always did, and nothing about the
  // stored data changes when a board's type does.
  const crossLinkIds = new Set(
    wbIsMap() ? (window.wbMapState?.crossLinks || []).map((l) => `${l.from_id}:${l.to_id}`) : []
  );
  //: **A link's body is canvas, as far as starting a selection goes** (INBOX
  //: 180: "I cant drag highlight to select shapes"). Every link carries a
  //: transparent 20px hit band so it can be clicked, and that band is inside
  //: a `.sketch-group`, which `wbIsEmptyCanvasTarget` reads as "something is
  //: here, this gesture belongs to it". On a board whose connectors sweep
  //: across the middle, which is where anyone starts a rubber-band drag, the
  //: marquee therefore refused to begin and the drag did nothing at all.
  //: Nothing is lost by allowing it: a link cannot be dragged by its body
  //: (its own drag handler returns immediately, a link has no path data of
  //: its own to move), and a plain click still selects it, because a gesture
  //: under the marquee's 4px threshold ends without touching the selection.
  //: This class is what the test reads; it is set here rather than at enter
  //: so a sketch reclassified by an edit cannot keep a stale one.
  //: **A class is written only when it changes** (audit 1028 B4). d3's `classed` re-sets the
  //: `class` attribute even when the token is already right, so an unchanged board of 530
  //: sketches made 1,060 DOM writes a render (two per group, counted with a MutationObserver).
  const classIfChanged = (selection, name, want) => selection.each(function(d) {
    const on = !!want(d);
    if (this.classList.contains(name) !== on) this.classList.toggle(name, on);
  });
  classIfChanged(sketchUpdate, "wb-link-sketch", (d) => {
    try {
      return String(JSON.parse(d.data)?.type || "").startsWith("link-");
    } catch {
      return false;
    }
  });

  classIfChanged(sketchUpdate, "wb-map-crosslink", (d) => {
    if (!crossLinkIds.size) return false;
    let parsed;
    try {
      parsed = JSON.parse(d.data);
    } catch {
      return false;
    }
    return crossLinkIds.has(`${parsed?.sourceId}:${parsed?.targetId}`);
  });
};

//: The paint key of a stroke and the link ends read for this render, with the index of measured boxes.
renderWhiteboard.parts.wbSketchPaintKeys = function wbSketchPaintKeys() {
  //: **A pen or highlighter stroke is repainted only when its look can have
  //: changed** (audit 1028 B3, B4): the key is its data plus what decides the
  //: ink (the board's colour and the light or dark mode), the way
  //: `wbObjectPaintKey` does for a topic. Null for everything else: a
  //: connector's path comes from the items at its ends, and a shape has a
  //: label and a rough look. 300 strokes cost 90ms a render at 4x throttle
  //: whatever had moved; a gesture that moved a stroke's drawn path and did
  //: not put it back is caught by the skip's own check of that path.
  wbBoardBgCache.pass = false; // a second render in one task re-reads the colour
  const strokeInk = `${wbBoardBg()}|${document.documentElement.dataset.mode}`;
  wbBoardBgCache.pass = true;
  queueMicrotask(() => { wbBoardBgCache.pass = false; });
  //: A shape (W30 B4) adds its id (the rough seed) and the board's rough default; a connector
  //: adds the ends it resolves to now, so a moved or resized end repaints it. Words with a
  //: placeholder (`%date%`, `%page%`, `%length%` change with the day, the frames and the line),
  //: a map's cross-links and a raw path string never skip.
  const linkEnds = new Map();
  const strokePaintKey = (d) => {
    if (typeof d.data !== "string" || !d.data.startsWith("{")) return null;
    if (!d.data.includes("link-")) {
      if (/"shape":\s*"(?:draw|highlighter)"/.test(d.data)) return `${d.data}|${strokeInk}`;
      return d.data.includes('"d"') && !d.data.includes("%") ? `${d.data}|${d.id}|${strokeInk}|${wbBoardBackground().rough}` : null;
    }
    if (d.data.includes("%") || wbIsMap()) return null;
    let parsed = null;
    try { parsed = JSON.parse(d.data); } catch (e) { return null; }
    if (!String(parsed?.type || "").startsWith("link-") || wbMapCrossLinkLook(parsed)) return null;
    const ends = wbResolveLinkEndpoints(parsed);
    linkEnds.set(d.id, ends);
    return `${d.data}|${strokeInk}|${JSON.stringify(ends)}`;
  };
  //: **Every topic's box in one walk before the connectors read them** (W30 D26). The render cleared
  //: the size cache, so each link end asked `wbMapNodeSize` for its own `querySelector` walk of the
  //: page: with 500 topics and 300 links that was 7.4 s of 12 renders at 4x CPU (about 600 ms each).
  //: The index takes one `querySelectorAll` and one batch of reads, as a drag's first frame does.
  //: A board's connectors need the same batch (W30): each one read both ends'
  //: `offsetWidth` on a DOM the strokes before it had just written, 6.6 ms for 30
  //: connectors on 500 objects. The sizes are the ones on screen now, as before.
  //: Off a map only the objects a connector ends on are measured, found through the item index
  //: (`wbItemElement`): the walk over all 500 and their reads were 2.3 ms of a 10 ms render.
  const hasLinks = wbIsMap() || (wbState.sketches || []).some((s) => typeof s.data === "string" && s.data.includes("link-"));
  if (hasLinks && wbState.sketches?.length) wbIndexMapNodeElements(!wbIsMap());
  return { strokePaintKey, linkEnds };
};

//: What a sketch looks like, read from its data: path, ink, fill, dash and the link it is.
renderWhiteboard.parts.wbSketchLook = function wbSketchLook(d, linkEnds) {
  let pathData = d.data;
  let hitboxData = null;
  let shapedLine = false;
  let stroke = "var(--text-color)";
  let strokeWidth = "3";
  let strokeOpacity = 1;
  let fill = "none";
  let fillOpacity = 1;
  let dashArray = null;
  let isHighlighterStroke = false;
  let shapeData = null;
  let linkData = null;
  try {
    const parsed = JSON.parse(d.data);
    if (parsed.d) {
      shapeData = parsed;
      pathData = parsed.d;
      //: A hollow end (outline diamond, circle, square) stops the drawn shaft at its edge, as a link's does; the hit band keeps the whole line.
      if (wbSketchTakesCaps(parsed)) {
        const caps = wbSketchCaps(parsed);
        const trimmed = wbFmtState.inkMore?.trimShaft(parsed.d, caps.startCap, caps.endCap, (parsed.width || 3) * 4 + 6, caps, wbShaftEnd);
        if (trimmed && trimmed !== parsed.d) { hitboxData = parsed.d; pathData = trimmed; }
      }
      // `shape` names the tool that drew it, which is what says "highlighter"
      // rather than "a stroke that happens to carry an opacity": a pen
      // stroke restyled through the context bar could have one too.
      isHighlighterStroke = parsed.shape === "highlighter";
      stroke = parsed.noStroke ? "none" : (wbDefaultInk(parsed.color) || stroke);
      // Highlighter strokes carry their own width/opacity (see the mouseup
      // handler that writes them), everything else keeps the defaults
      // above, set explicitly every render so a reused element can't keep
      // a stale highlighter width after its data changes.
      if (parsed.width) strokeWidth = String(parsed.width);
      if (parsed.opacity != null) strokeOpacity = parsed.opacity;
      // Fill/dash: asked for directly ("fill colour/transparency...
      // stroke width, style, and colour"). Absent on any sketch drawn
      // before this existed, which is exactly why these default to "no
      // fill, solid" rather than reading undefined.
      if (parsed.fill) {
        fill = parsed.fill;
        fillOpacity = parsed.fillOpacity != null ? parsed.fillOpacity : 1;
      }
      dashArray = wbDashArray(parsed.dash || "solid", parsed.width || 3, wbDashPatternOf(parsed.dashPattern));
      //: Smoothed ink is the stroke's outline, filled with its colour (whiteboard-ink-more.js).
      if (parsed.ink) {
        fill = stroke;
        fillOpacity = strokeOpacity;
        stroke = "none";
        dashArray = null;
      }
    } else if (parsed.type && parsed.type.startsWith("link-")) {
      linkData = parsed;
      stroke = parsed.color || stroke;
      strokeWidth = String(parsed.width || 3);
      dashArray = wbDashArray(parsed.dash || "solid", parsed.width || 3, wbDashPatternOf(parsed.dashPattern));
      const look = wbMapCrossLinkLook(parsed);
      if (look) {
        //: The branch's own drawing (see `wbMapCrossLinkLook`): a ribbon is
        //: a filled outline, so it paints with fill and no stroke, and the
        //: hitbox keeps the centreline so the whole length stays a target.
        const colour = look.colour || stroke;
        pathData = look.d;
        hitboxData = look.line;
        stroke = look.ribbon ? "none" : colour;
        strokeWidth = String(look.width);
        dashArray = null;
        if (look.ribbon) {
          fill = colour;
          fillOpacity = 1;
        }
      } else {
        const endpoints = linkEnds.has(d.id) ? linkEnds.get(d.id) : wbResolveLinkEndpoints(parsed);
        pathData = endpoints ? wbLinkPathD(parsed.type, endpoints.source, endpoints.target, wbLinkCaps(parsed), parsed.width, parsed.bend, wbLinkShape(parsed)) : "";
        //: A connector shape (double, arrows, pipe, wire; `wbFmtState.shapeMore`): the outline round the centre
        //: line is what is drawn, the centre line stays the hit band and the label's path.
        const shaped = endpoints && parsed.shape ? wbFmtState.shapeMore?.shapedLink(parsed, endpoints) : null;
        if (shaped) {
          shapedLine = true;
          pathData = shaped.d;
          hitboxData = shaped.centre;
          strokeWidth = String(shaped.stroke);
          dashArray = null;
          if (shaped.paint !== "outline") {
            fill = stroke;
            fillOpacity = shaped.paint === "tube" ? 0.2 : 1;
          }
        }
      }
    }
  } catch(e) {}
  return { pathData, hitboxData, shapedLine, stroke, strokeWidth, strokeOpacity, fill, fillOpacity, dashArray, isHighlighterStroke, shapeData, linkData };
};

//: The look put on the sketch group's elements; returns the path drawn.
renderWhiteboard.parts.wbPaintSketchLook = function wbPaintSketchLook(node, d, look0) {
  let { pathData, hitboxData, shapedLine, stroke, strokeWidth, strokeOpacity, fill, fillOpacity, dashArray, isHighlighterStroke, shapeData, linkData } = look0;
  d3.select(node).select(".sketch-hitbox").attr("d", hitboxData ?? pathData);
  //: The hand-drawn look (canvasdepth2): only the drawn line is roughened,
  //: so the hit band, the ports and the label keep the true shape.
  //: Rounded corners (draw.io's, `data.round`) and flow (`data.flow`): the
  //: drawn line only, like the rough look, so the hit band keeps the true
  //: shape. A flowing line with no dashes of its own gets the dashed look,
  //: since the marching is the dashes moving.
  const styled = shapeData || linkData;
  const plainLine = !(linkData && wbMapCrossLinkLook(linkData)) && !shapedLine;
  if (styled?.round && plainLine) pathData = wbRoundedPathD(pathData, styled.round, Boolean(linkData));
  else if (styled?.curve && plainLine) pathData = wbRoundedPathD.curved(pathData, Boolean(linkData));
  const flowing = Boolean(styled?.flow) && plainLine;
  if (flowing && !dashArray) dashArray = wbDashArray("dashed", Number(strokeWidth) || 3);
  const flowPeriod = flowing && dashArray ? dashArray.split(" ").map(Number).reduce((a, b) => a + b, 0) * (dashArray.split(" ").length % 2 ? 2 : 1) : 0;
  if (wbDrawsRough(shapeData || linkData, !plainLine)) pathData = wbRoughD(pathData, d.id);
  // A gradient or a fill style swaps the plain colour for a paint server in
  // this group's own defs (null when there is none, which also drops a stale one).
  const fillPaint = wbSyncFillDefs(node, d.id, shapeData);
  if (fillPaint) fill = fillPaint;
  d3.select(node).select(".sketch-path")
    .classed("wb-flow", flowing)
    // The highlighter's multiply, re-applied every render and cleared on
    // every other kind so a reused element cannot keep it: the same reason
    // the width and opacity above are set explicitly rather than only when
    // present. Inline rather than a class because the export clones these
    // nodes into a standalone SVG.
    .style("mix-blend-mode", isHighlighterStroke ? wbHighlighterBlend() : null)
    // The flat end a marker leaves, set here rather than only on the live
    // path: the enter selection above appends every sketch with a round cap
    // and nothing updated it, so a highlighter stroke was square while it
    // was being drawn and round from the first render after mouseup
    // (measured: `getComputedStyle(...).strokeLinecap` read round on both
    // saved strokes while the pad read square).
    .attr("stroke-linecap", isHighlighterStroke ? HIGHLIGHTER_STYLE.lineCap : "round")
    .attr("stroke-linejoin", isHighlighterStroke ? HIGHLIGHTER_STYLE.lineJoin : "round")
    .attr("d", pathData)
    .attr("stroke", stroke)
    .attr("stroke-width", strokeWidth)
    .attr("stroke-opacity", strokeOpacity)
    .attr("fill", fill)
    .attr("fill-opacity", fillOpacity)
    // `null` removes the attribute entirely (d3's own convention) rather
    // than setting `stroke-dasharray=""`, which some renderers treat as
    // "zero-length dashes" instead of "solid", a reused element from a
    // dashed sketch must not leave a stale dasharray on a solid one.
    .attr("stroke-dasharray", dashArray);
  wbSetFlowAnimation(d3.select(node).select(".sketch-path").node(), flowing ? flowPeriod : 0);
  //: The Format panel's opacity and shadow (decision 19), on the group so
  //: the label goes with the shape; an attribute and an inline style, both
  //: of which the export's clone keeps.
  const look = shapeData || linkData;
  d3.select(node)
    .attr("opacity", look?.alpha != null && look.alpha < 1 ? look.alpha : null)
    .style("filter", wbShadowCss(look));
  wbSyncSketchTip(node, look);
  // After the path, which the label is laid out from (decision 12).
  wbPaintShapeLabel(node, shapeData, d);
  wbFmtState.effects?.paintShape(node, shapeData, pathData, d.id); // glass, picture fill, label shadow (whiteboard-effects.js)
  wbPaintLinkLabel(node, d, linkData);
  return pathData;
};

renderWhiteboard.parts.wbPaintSketch = function wbPaintSketch(d, strokePaintKey, linkEnds) {
  const strokeKey = strokePaintKey(d);
  const drawn = this.querySelector(".sketch-path");
  if (strokeKey && this._wbStrokeKey === strokeKey && drawn?.getAttribute("d") === this._wbStrokeD) return;
  const pathData = renderWhiteboard.parts.wbPaintSketchLook(this, d, renderWhiteboard.parts.wbSketchLook(d, linkEnds));
  this._wbStrokeKey = strokeKey;
  this._wbStrokeD = strokeKey ? pathData : null;
  //: The plain path, for the jump pass to go back to when its jumps no longer apply.
  this._wbPlainD = strokeKey ? pathData : null;
};

//: Card resize: asked for directly ("resizing... cards"). `width`/`height`
//: are nullable (unset means "auto", the CSS-sized default every card used
//: before this existed); a resize sets them explicitly for the first time.
//: Shares `resizeDrag`'s own maths (see `renderWbObjects`) rather than a
//: second copy: the two differ only in which element/datum they close
//: over, so it's built inline here with the same shape.
renderWhiteboard.parts.nodeResizeDrag = function nodeResizeDrag(handle) {
  let rawDX = 0, rawDY = 0;
  return d3.drag()
    // The handle sits inside the card it resizes, see
    // `wbStableDragContainer`. Matters for `w`/`n`, which move x/y too.
    .container(wbStableDragContainer(".node-card"))
    .on("start", (event, d) => {
      event.sourceEvent.stopPropagation();
      rawDX = 0;
      rawDY = 0;
      d._resizeUndoBefore = WB_KIND_INFO.node.payload(d);
      d._linkedSketches = wbLinkedSketchesFor(d.id, "node");
      //: Measured once, at the press: the height the text needs.
      const card = wbInstances.query(`.node-card[data-id="${d.id}"]`);
      d._fitH = card && !wbExpandedNodes.has(d.id) ? wbCardFitHeight(card) : null;
      d._gesture = wbBeginGesture(() => wbRestoreBox("node", d, d._resizeUndoBefore));
    })
    .on("drag", (event, d) => {
      if (d._gesture?.cancelled) return;
      const transform = d3.zoomTransform(wbInstances.container());
      rawDX += event.dx / transform.k;
      rawDY += event.dy / transform.k;
      const startW = d._resizeStartW ?? (d._resizeStartW = d.width || WB_CARD_DEFAULT_SIZE.w);
      const startH = d._resizeStartH ?? (d._resizeStartH = d.height || WB_CARD_DEFAULT_SIZE.h);
      const startX = d._resizeStartX ?? (d._resizeStartX = d.x);
      const startY = d._resizeStartY ?? (d._resizeStartY = d.y);
      const box = wbResizeBox({ x: startX, y: startY, w: startW, h: startH }, handle, rawDX, rawDY,
        event.sourceEvent.shiftKey, event.sourceEvent.altKey, WB_OBJECT_MIN_SIZE);
      let width = box.w, height = box.h, x = box.x, y = box.y;
      //: Guided, never preset (INBOX 825 item 2): a neighbour's edge, width
      //: or height, the grid, or the text's own height; Alt and Shift hold them off.
      if (!event.sourceEvent.shiftKey && !event.sourceEvent.altKey) {
        ({ width, height } = wbGuidedResize("node", d, handle, { x: startX, y: startY, w: startW, h: startH }, width, height, { fit: d._fitH }));
        if (handle.includes("w")) x = startX + (startW - width);
        if (handle.includes("n")) y = startY + (startH - height);
      }
      d.width = width;
      d.height = height;
      d.x = x;
      d.y = y;
      const el = wbInstances.query(`.node-card[data-id="${d.id}"]`);
      if (el) {
        el.style.width = `${width}px`;
        el.style.height = `${height}px`;
        el.style.transform = wbItemTransform(d);
      }
      //: **The arrows and the links follow a card's resize as they follow a
      //: move** (the owner, 2026-10-26: "the side arrows dont move with it").
      //: The object's resize did this; the card's left the four arrows and
      //: every link on the old box until the release (measured: the right
      //: arrow 17px outside the box at the press, 98px inside it at +120).
      wbMapNodeSizeCache?.delete(d.id);
      if (d._linkedSketches?.length) wbUpdateLinkedSketches(d.id, d._linkedSketches);
      wbQueueSelectionBar();
    })
    .on("end", async (event, d) => {
      wbClearAlignmentGuides();
      delete d._linkedSketches;
      delete d._fitH;
      delete d._resizeStartW;
      delete d._resizeStartH;
      delete d._resizeStartX;
      delete d._resizeStartY;
      const before = d._resizeUndoBefore;
      delete d._resizeUndoBefore;
      const cancelled = wbEndGesture(d._gesture);
      delete d._gesture;
      //: Escape put it back; and a press that resized nothing (each half of
      //: the double-click that fits the text is one) is not a resize.
      if (cancelled || (before && before.width === (d.width ?? null) && before.height === (d.height ?? null))) return;
      await wbSaveNode(d);
      wbFmtState.keys?.record({ kind: "turn", deg: (d.rotation || 0) - (before?.rotation || 0) });
      if (before) wbPushUndo({ action: "move", kind: "node", id: d.id, before });
      wbScheduleRender();
    });
};

//: Rotation: asked for directly, more than once ("rotations", "anchor
//: points, rotations, resizing, cropping"). A single handle above the
//: item's own top-centre, the same convention every drawing app uses;
//: `getBoundingClientRect()`'s centre stays correct even mid-rotation
//: (an axis-aligned box's centre coincides with the true rotation centre
//: regardless of how far the box itself has turned), so this needs no
//: zoom/pan math the way position drags do, only the *angle* to the
//: cursor matters, and angle is unaffected by uniform scale/pan.
renderWhiteboard.parts.nodeRotateDrag = function nodeRotateDrag() {
  return d3.drag()
    .on("start", (event, d) => {
      event.sourceEvent.stopPropagation();
      d._rotateUndoBefore = WB_KIND_INFO.node.payload(d);
      //: The links touching it, found once: a turn moves their endpoints
      //: as much as a move does, and without this they stayed where the
      //: unturned box had them until the next move (INBOX 647).
      d._linkedSketches = wbLinkedSketchesFor(d.id, "node");
      d._gesture = wbBeginGesture(() => wbRestoreBox("node", d, d._rotateUndoBefore));
    })
    .on("drag", (event, d) => {
      if (d._gesture?.cancelled) return;
      const el = wbInstances.query(`.node-card[data-id="${d.id}"]`);
      if (!el) return;
      const rect = el.getBoundingClientRect();
      d.rotation = wbAngleFromCenterDeg(
        rect.left + rect.width / 2, rect.top + rect.height / 2,
        event.sourceEvent.clientX, event.sourceEvent.clientY,
        event.sourceEvent.shiftKey
      );
      el.style.transform = wbItemTransform(d);
      if (d._linkedSketches?.length) wbUpdateLinkedSketches(d.id, d._linkedSketches);
      wbQueueSelectionBar();
    })
    .on("end", async (event, d) => {
      const before = d._rotateUndoBefore;
      delete d._rotateUndoBefore;
      delete d._linkedSketches;
      const cancelled = wbEndGesture(d._gesture);
      delete d._gesture;
      //: A press that turned nothing (each half of a double-click is one)
      //: saves nothing and leaves no undo step to press through.
      if (cancelled || (before && (before.rotation || 0) === (d.rotation || 0))) return;
      await wbSaveNode(d);
      if (before) wbPushUndo({ action: "move", kind: "node", id: d.id, before });
    });
};

//: A card's own drag; the filter keeps every drawing tool out of its way.
renderWhiteboard.parts.wbNodeDrag = function wbNodeDrag() {
  return d3.drag()
    .clickDistance(WB_CLICK_SLOP)
    // Reported directly: drawing over a note "just moves the note
    // instead" of drawing on it. Cards sit in `#wb-html-layer`, a sibling
    // painted on top of `#wb-svg-layer`, a pointerdown that lands on a
    // card never reaches the SVG layer's own draw listener at all, and
    // this drag (bound directly to the card) intercepted it first
    // regardless of which tool was active. Filtering it out here, rather
    // than only inside the start/drag handlers below, stops d3 from
    // capturing the gesture in the first place, so the same pointerdown
    // is free to bubble to `containerEl`'s brush listener instead.
    // A resize handle (below) owns its own drag, same reasoning as
    // `objDrag`'s own filter, and a real bug this filter's absence caused:
    // without the exclusion, this card-level drag also engaged for the
    // exact same pointerdown, and whichever one's gesture-tracking the
    // browser resolved first silently won, so a resize handle drag never
    // visibly resized anything.
    // `currentTool !== "lasso"`: reported directly ("the lasso tool
    // doesn't work properly"), a lasso loop is meant to start from
    // anywhere, including right at a card's own edge, but this filter
    // (unlike the lasso's own pointerdown listener) never excluded the
    // lasso tool the way it already excludes the brush tools, so a lasso
    // gesture begun on top of a card silently moved the card instead of
    // ever reaching the lasso's own draw logic.
    // `.wb-card-more`: the Show more/less toggle added below, without this
    // exclusion its pointerdown started a card drag the same way a resize
    // handle's did before it was excluded (see that comment above), so the
    // click never registered and the toggle silently did nothing.
    .filter((event) => !wbIsSecondTouch(event) && !WB_BRUSH_TOOLS.has(window.currentTool) && window.currentTool !== "lasso" && !event.ctrlKey && !event.button && !event.target.closest(".wb-resize-handle, .wb-rotate-handle, .wb-card-more"))
    .on("start", dragStart)
    .on("drag", dragging)
    .on("end", dragEndNode);
};

// Reported directly: "when I attach notes to a whiteboard I want to see
// the WHOLE note, not a cut-off version". This used to hard-truncate to
// 100 plain-text characters with no way back to the rest, worse than the
// Notes list's own long-note handling, which this now matches: render the
// full note through the app's real markdown renderer (not textContent: 
// a note can have headings, code, links), clamp it only past a height cap,
// and give it the same "Show more"/"Show less" control and wording as
// `.entry-more`, keyed by this whiteboard node's id in `wbExpandedNodes`
// (not the note's own id: the same note can sit on the board twice).
//: A card that is showing its whole note sizes to the note, with the stored
//: height kept as a floor so collapsing puts the box back exactly where the
//: person left it and an expanded card never becomes *smaller* than the one
//: they sized by hand. `height: ""` rather than `auto` so the element falls
//: back to the stylesheet's own rule rather than to a second hard value.
renderWhiteboard.parts.wbCardExpandHeight = function wbCardExpandHeight(el, d) {
  if (!el) return;
  const stored = d.height ? `${d.height}px` : "";
  if (wbExpandedNodes.has(d.id)) {
    el.style.height = "";
    el.style.minHeight = stored;
  } else {
    el.style.height = stored;
    el.style.minHeight = "";
  }
};

//: A new card's note, drawn through the markdown renderer with its Show more control.
renderWhiteboard.parts.wbBuildCard = function wbBuildCard(d, entriesById) {
  const card = d3.select(this);
  const entry = entriesById.get(String(d.entry_id));
  if (!entry) {
    // **"Loading…" with nothing loading.** `entriesById` is built from
    // `allEntries`, the app's in-memory note list, so a card whose note
    // was created *after* the last `loadEntries()` said "Loading…"
    // forever, because nothing here ever fetched it. Every path that
    // creates a note and immediately places it now refreshes that list
    // first (`wbMindMapAddCard`), which is the real
    // fix; this branch is the honest fallback for the case that remains:
    // a card pointing at a note that has actually been deleted.
    card.append("div").attr("class", "wb-card-content muted").node().textContent =
      "This note is no longer here";
    return;
  }
  // A sketch's actual content is a file attachment, not text, never
  // reflected here before (§89 item 10): thumb_attachment_id/thumb_url
  // covers that, entry.attachments covers a note with a real attached
  // image. Same priority libraryCard() (library.js) already uses. A
  // pasted/dropped image living as inline markdown in entry.content is
  // NOT handled here: that already renders through renderMarkdown below,
  // and would be shown twice if it were.
  const firstImageAttachment = (entry.attachments || []).find((a) => a.is_image);
  const thumbSrc = entry.thumb_attachment_id
    ? mediaSrc(`/files/${entry.thumb_attachment_id}`)
    : entry.thumb_url && !isRemoteImage(entry.thumb_url)
    ? mediaSrc(entry.thumb_url)
    : firstImageAttachment
    ? mediaSrc(`/files/${firstImageAttachment.id}`)
    : null;
  if (thumbSrc) {
    card.append("img").attr("class", "wb-card-thumb").attr("src", thumbSrc).attr("alt", "").attr("loading", "lazy");
  }
  const contentEl = card.append("div").attr("class", "wb-card-content").node();
  const text = entry.content || entry.preview || "";
  if (!text) {
    // The thumbnail above IS the content for a sketch/image-only note, 
    // "Empty note" next to a picture would read as a bug, not a note.
    if (!thumbSrc) contentEl.textContent = "Empty note";
    return;
  }
  renderMarkdown(contentEl, text);
  //: A clipped row (first 300 characters) is drawn again with the whole note once it arrives.
  if (entry.content_truncated) fullEntry(entry.id).then((whole) => {
    if (!contentEl.isConnected || contentEl.querySelector("textarea")) return;
    contentEl.replaceChildren();
    renderMarkdown(contentEl, whole.content);
    wbScheduleCardClampSync();
  }, () => {});
  //: **Whether a note needs a "Show more" is a question about the box, not
  //: about the note.** This used to ask `text.length > LONG_NOTE_CHARS ||
  //: lines > LONG_NOTE_LINES`, the Notes list's own rule, and returned
  //: early for anything under it. But the Notes list shows a note in a
  //: column as tall as the page, while a board card is exactly as tall as
  //: the person dragged it to, so the two questions have different
  //: answers: measured, a 324-character note (well under the 500-character
  //: threshold) in a 320x120 card laid out 215px of text, 112px of it
  //: below the card's own bottom edge, with no clamp and no way to ask for
  //: the rest. That is INBOX 238's "the text goes out of the panel
  //: border".
  //:
  //: So the toggle is built for every note that has text, and
  //: `wbSyncCardClamps` below hides it again on the cards where everything
  //: already fits. Hidden rather than absent because the answer changes
  //: whenever the card is resized, and a button that has to be created on
  //: a resize is a button that will be missing after one.
  const expanded = () => wbExpandedNodes.has(d.id);
  contentEl.classList.toggle("wb-card-content-clamped", !expanded());
  const toggle = card.append("button")
    .attr("type", "button")
    .attr("class", "entry-more wb-card-more")
    .attr("hidden", "")
    .text(expanded() ? "Show less" : "Show more");
  toggle.on("click", (event) => {
    event.stopPropagation();
    if (expanded()) wbExpandedNodes.delete(d.id);
    else wbExpandedNodes.add(d.id);
    contentEl.classList.toggle("wb-card-content-clamped", !expanded());
    toggle.text(expanded() ? "Show less" : "Show more");
    //: The box has to grow with what is now inside it. Reported with a
    //: screenshot of a poem running three paragraphs out through the
    //: bottom edge of its own card: a placed note carries a stored
    //: `height`, written below as an inline style, and "Show more" only
    //: ever unclamped the text, so the extra lines were laid out beyond a
    //: box that still measured what it did when the text was clipped.
    //: Applied to this card directly as well as in the merge below,
    //: because nothing redraws the board on a toggle.
    renderWhiteboard.parts.wbCardExpandHeight(this.closest(".wb-node") || card.node(), d);
    //: Collapsing brings the clip back, which can make the toggle itself
    //: unnecessary (a note that fits the box it was collapsed into), so
    //: the answer is recomputed rather than assumed to still hold.
    wbSyncCardClamps();
    wbSaveExpandedNodes();
  });
};

//: Handles arm lazily (wbArmHandles), so a card carries none until it is pointed at.
renderWhiteboard.parts.wbArmCardHandles = function wbArmCardHandles() {
  const card = d3.select(this);
  wbArmHandles(this, () => {
    for (const handle of ["nw", "n", "ne", "e", "se", "s", "sw", "w"]) {
      card.append("div")
        .attr("class", "wb-resize-handle")
        .attr("data-handle", handle)
        //: The same title the object handles carry, for the same reason: the
        //: double-click-to-fit gesture had nothing on screen saying it existed.
        .attr("title", "Drag to resize: Shift keeps the proportions, double-click fits the card to its note")
        .call(renderWhiteboard.parts.nodeResizeDrag(handle));
    }
    card.append("div")
      .attr("class", "wb-rotate-handle")
      .attr("title", "Drag to rotate: Shift snaps to 15°, double-click stands it upright")
      .call(renderWhiteboard.parts.nodeRotateDrag());
  });
};

//: Every card, new or kept: position, size, stack order and the eight-line cap.
renderWhiteboard.parts.wbUpdateCards = function wbUpdateCards(nodeSelection, nodeEnter, stackRank) {
  nodeSelection.merge(nodeEnter)
    .style("transform", wbItemTransform)
    .style("width", (d) => (d.width ? `${d.width}px` : ""))
    //: An expanded card is sized by its text, not by the height it was saved
    //: at (see `wbCardExpandHeight`), so a redraw does not clip it again.
    .style("height", (d) => (d.height && !wbExpandedNodes.has(d.id) ? `${d.height}px` : ""))
    .style("min-height", (d) => (d.height && wbExpandedNodes.has(d.id) ? `${d.height}px` : ""))
    .style("z-index", (d) => stackRank.get(`node:${d.id}`))
    //: The eight-line cap is for the card that has never been resized and so
    //: has no height of its own to clip against. A card with a stored height
    //: does, and applying both would clamp a 700px card to eight lines and
    //: leave the rest of it empty under a "Show more" hiding nothing.
    .each(function (d) {
      this.querySelector(".wb-card-content")
        ?.classList.toggle("wb-card-content-capped", !d.height);
    });
};

//: A render places every topic from its data; a dragged branch's layer would carry them a
//: second time, so it is undone first (the first line below).
function renderWhiteboard() {
  if (wbMapDragLayer.live) wbMapDragLayer.close();
  wbPruneSelection();
  //: A render replaces every map node's element, so every measurement taken
  //: from the previous set is about to describe something that is gone.
  wbClearMapNodeSizeCache();
  wbItemElCache.clear();
  wbItemElIndex.count = -1;
  //: And the overview's items were drawn from that set: the next pan frame
  //: redraws them rather than only moving its rectangle.
  wbNavState.stale = true;
  // Built once per render, not once per card: `allEntries.find(...)` inside
  // a per-card callback is O(cards × notebook size) on every single render
  //, for a large notebook that is real, measurable work paid on every
  // whiteboard update, not just once. A note's id never changes shape
  // (string vs number) across a session, so this Map stays valid for the
  // whole render pass below.
  const entriesById = new Map(allEntries.map((e) => [String(e.id), e]));

  renderWhiteboard.parts.wbSyncEmptyHint();

  // Render Sketches (SVG)
  const svgGroup = d3.select(wbInstances.layer("wb-zoom-group"));
  //: Every stroke's group wherever its band put it (decision 43); a new one
  //: is made in the base layer and `wbPlaceSketchBands` moves it.
  const sketchSelection = svgGroup.selectAll(() => wbInstances.queryAll("#wb-zoom-group > g.sketch-group, #wb-html-layer > svg.wb-sketch-band > g.sketch-group"))
    .data((wbState.sketches || []).filter(wbSketchIsDrawable), d => d.id);
    

  const sketchDrag = renderWhiteboard.parts.wbSketchDrag();

  const sketchEnter = renderWhiteboard.parts.wbEnterSketches(sketchSelection, sketchDrag);


  const sketchUpdate = sketchEnter.merge(sketchSelection);

  renderWhiteboard.parts.wbClassSketches(sketchUpdate);

  const { strokePaintKey, linkEnds } = renderWhiteboard.parts.wbSketchPaintKeys();
  sketchUpdate.each(function (d) { renderWhiteboard.parts.wbPaintSketch.call(this, d, strokePaintKey, linkEnds); });

  sketchSelection.exit().remove();
  //: Off a map the sizes were read before the objects below were repainted, so none is kept.
  if (!wbIsMap()) wbClearMapNodeSizeCache();
  //: **A shape's z is its paint order** (found with FEAT-07). SVG paints in
  //: document order, and a new sketch was appended last whatever its z, so
  //: Bring forward on a shape wrote a number nothing read. The groups are
  //: placed in the stack order by `wbPlaceSketchBands`, into the base layer
  //: or a band between two cards (decision 43), not by d3's `sort`, whose
  //: `order` would pull every group into one parent. Then each connector
  //: that jumps hops over the lines under it (wb-phase2 step 1), in paint
  //: order. Not on a map, whose lines have no order to keep.
  const sketchGroups = new Map(sketchUpdate.nodes().map((el) => [el.__data__.id, el]));
  const stackOrder = wbStackOrder();
  const painted = wbPlaceSketchBands(sketchGroups, stackOrder);
  if (!wbIsMap()) wbApplyLineJumps(painted);

  // Render Nodes (Cards)
  const canvas = d3.select(wbInstances.layer("wb-html-layer"));
  //: One sort of the board's items serves the bands above, the cards here and the objects below (W30).
  const stackRank = new Map(stackOrder.map((e, i) => [e.key, i + 1]));
  const nodeSelection = canvas.selectAll(".wb-card.node-card")
    .data(wbState.nodes, d => d.id);
    

  const nodeEnter = nodeSelection.enter()
    .append("div")
    .attr("class", "wb-card node-card")
    .attr("data-id", (d) => d.id)
    .style("transform", wbItemTransform)
    .style("width", (d) => (d.width ? `${d.width}px` : ""))
    .style("height", (d) => (d.height ? `${d.height}px` : ""))
    .style("z-index", (d) => stackRank.get(`node:${d.id}`))
    .call(renderWhiteboard.parts.wbNodeDrag())
    .on("click", (event, d) => {
      // ROADMAP row 0(b), asked for directly: with the Hand active, a plain
      // click on something switches to Select and selects it. A pan is a
      // drag; a click that moved nothing is a choice of *this*, and every
      // whiteboard app (Miro, FigJam, tldraw) reads it that way.
      if (window.currentTool === "select" || window.currentTool === "pan") {
        event.stopPropagation();
        if (window.currentTool === "pan") wbSelectToolRef?.("select");
        wbHandleItemClick("node", d.id, event);
        return;
      }
      // Same fix as the sketch group above: a single eraser click, no drag,
      // now erases the one card clicked instead of needing movement to
      // trigger a mouseenter.
      if (window.currentTool === "delete" || window.currentTool === "eraser") wbDeleteNode(d);
    })
    .on("pointerenter", (event, d) => {
      if (window.currentTool === "eraser" && wbErasing) wbDeleteNode(d);
    });
      
  nodeEnter.each(function (d) { renderWhiteboard.parts.wbBuildCard.call(this, d, entriesById); });

  nodeEnter.each(renderWhiteboard.parts.wbArmCardHandles);

  wbWireContextMenu(nodeEnter, "node");

  renderWhiteboard.parts.wbUpdateCards(nodeSelection, nodeEnter, stackRank);

  nodeSelection.exit().remove();

  //: After the heights above are on the elements, not before: the question
  //: each card is being asked is whether its text fits the box this render
  //: just gave it.
  wbScheduleCardClampSync();

  renderWbObjects(canvas, stackRank);
  if (typeof wbFmtState !== "undefined") wbFmtState.paintCaptions?.();

  // After the nodes, never before: an edge is drawn between two *measured*
  // boxes (`wbMapNodeSize` reads `offsetHeight`, since a map node's height is
  // its text's), so running this first would measure the previous render's
  // sizes and leave every edge one frame stale, visible as edges that lag
  // behind a node the moment its text changes length.
  //: Held while an add opens its topic (`wbAddGate.renderHold`): written right after.
  if (wbAddGate.renderHold) wbAddGate.renderHold.edges = true;
  else {
    wbRenderMapEdges();
    //: A map's boundaries and summaries, from the boxes just measured.
    wbRenderMapStructure();
  }

  // Every element above was just rebuilt, so any `.wb-selected` class set
  // before this render is gone with it, re-apply from the state that
  // actually persists (`wbSelectedItem`), not the DOM.
  wbApplySelectionHighlight();
  wbPaintLocks();
  wbPaintHidden();
  wbFmtState.isolate?.paint();
  wbFmtState.structure?.paint();
  wbPaintCommentMarks();
  wbCloseOrphanedPopovers();

  //: A frame later, not now: a fresh element has to be drawn once before it
  //: is culled, which is what gives `contain-intrinsic-size: auto` a size to
  //: remember it by (see `wbCullNow`).
  wbScheduleCull();
}

//: Min size a resize can shrink an object to, small enough for a sticky
//: note, too small to lose an image/text box entirely off the canvas.
const WB_OBJECT_MIN_SIZE = 40;

const WB_SAVE_MANY_MAX = 5000;

//: **A folded topic's element is kept for the expand that brings it back**
//: (INBOX 424e). A collapse takes a branch out of the DOM (see the note on
//: `objectData` in `renderWbObjects` for why it is removed rather than
//: hidden), and the expand that followed built every one of those topics
//: again from nothing: measured at 4x CPU, expanding the root of a 120-topic
//: map was one 1,207ms task, `wbBuildMapNode` and the `setAttribute`s under
//: it the largest part. The elements are kept here, by id, while their topic
//: is folded away, and the expand takes each one back instead of building it.
//:
//: Only for the very datum it was built for: the node's own controls close
//: over `d`, so an element built for an object that has since been replaced
//: (the board refetched) would act on a row the board no longer holds. That
//: one is built fresh, exactly as before.
const wbMapNodePool = new Map();

// Cards and sketches each render in their own function, inlined into
// renderWhiteboard directly; objects get their own function instead, two
// genuinely different element shapes (an <img>, a contenteditable <div>)
// sharing one drag+resize+select scaffold reads better factored out than
// inlined a third time.
//: **A sticky's day is a chip** (CHAT_PLAN section 2, the board's row): the
//: first day a sticky names ("launch friday 3pm") shows as a chip on its
//: paper, read by the server in one request for the board (`POST
//: /read/dates`, the one recogniser; quoted words skipped), and a day still
//: to come is a reminder a press away, with Undo. Painted on a pause after a
//: render, from a cache keyed by the words, so a pan or a move asks nothing.
const wbStickyDates = { timer: 0, read: new Map() };

//: **A sketch's JSON parsed once per version of its data** (audit 1028 B17):
//: the link lookups walk every sketch on the board, strokes included, and
//: most of them are not links. Keyed by id and checked against the data
//: string itself, so an edit (a new string) is parsed again and nothing stale
//: is served. Only link records are kept, as the callers only read them; a
//: stroke or a bad blob is remembered as null so it is not parsed again.
const wbLinkParseCache = new Map();

function dragging(event, d) {
  if (window.currentTool === "eraser" || window.currentTool === "delete" || window.currentTool === "bucket") return;
  if (d._gesture?.cancelled) return;
  if (window.currentTool && window.currentTool.startsWith("link-")) {
    const [mx, my] = d3.pointer(event, wbInstances.layer("wb-zoom-group"));

    // A fixed source anchor stays put; a floating one re-aims at the live
    // pointer every frame: the same rectangle-intersection the render path
    // uses, not the old fixed centre-point.
    const fixedStart = wbAnchorPoint(d._linkKind || "node", d, d.linkSourceAnchor);
    const start = fixedStart || wbEdgePoint(d._linkKind || "node", d, mx, my);
    //: A cross-link between two map topics is drawn in the map's own curve
    //: while it is dragged; anything else keeps the tool the person picked
    //: (the first version of this curved every link from a text box, sticky
    //: or image on a plain board too).
    const tool = (wbIsMap() && WB_MAP_KINDS.has(d.kind)) ? wbMapCrossLinkType() : window.currentTool;
    d.linkingPath.setAttribute("d", wbLinkPathD(tool, start, { x: mx, y: my }));

    // Anchor hints follow whichever card, text box, sticky or shape the
    // pointer is over, so the drop target's own snap points are visible
    // before release.
    const hover = wbLinkCandidateAt(mx, my, d._linkKind || "node", d.id);
    if (hover) wbShowAnchorHints(hover[0], hover[1], wbNearestAnchor(hover[0], hover[1], mx, my));
    else wbShowAnchorHints(d._linkKind || "node", d, d.linkSourceAnchor);
    //: Which kind of connection the release will make, said before it is
    //: made (MINDMAP_PLAN §13c; `wbMapLinkCue`).
    const cue = wbMapLinkCue(d, hover ? hover[1] : null);
    d.linkingPath.classList.toggle("wb-link-preview-crosslink", cue === "cross-link");
  } else {
    // Pre-existing gap, not introduced this session, caught while adding
    // snap-to-grid here: event.dx/dy are raw screen pixels, the
    // link-drawing branch just above already divides by the zoom scale for
    // the same reason. Without it, a card dragged while zoomed moved faster
    // than the cursor when zoomed out and slower when zoomed in, and snap
    // would round a wrongly-scaled delta.
    const step = wbTouchSlopStep(d._gesture, event);
    if (!step) return;
    if (d._bulkOrigin === undefined) {
      d._bulkOrigin = wbDragIsBulkMove("node", d.id)
        ? wbCaptureBulkMoveOrigin(wbMultiKey("node", d.id))
        : null;
    }
    // Real bug, found live while testing click-to-select on a card: this
    // used to run in `dragStart`, unconditionally, on *every* pointerdown, 
    // including a plain click with zero movement. `.raise()` reappends the
    // node as its parent's last child (for z-order while actively
    // dragging), and doing that mid-gesture is enough to make the browser
    // never synthesize the following "click" event at all: confirmed by
    // instrumenting both the card's own click handler and the container's
    // "empty canvas" one and seeing *neither* fire, while an ordinary
    // sketch (whose own drag "start" never calls `.raise()`) selected
    // correctly the same way. Moved here, into `dragging`, which: unlike
    // `dragStart`, only ever runs after real movement has already
    // happened, so a plain click's click event is never touched.
    //: Once per gesture, not once per move (INBOX 114): `raise()` reappends
    //: the card even when it is already last, which invalidates layout on
    //: every pointer event for nothing.
    if (!d._raised) {
      d3.select(this).raise();
      d._raised = true;
    }
    const transform = d3.zoomTransform(wbInstances.container());
    d._rawX = (d._rawX ?? d.x) + step.dx / transform.k;
    d._rawY = (d._rawY ?? d.y) + step.dy / transform.k;
    // Asked for directly: Alt held during a drag temporarily releases the
    // grid lock, the same convention Figma/Illustrator use, a per-call
    // bypass rather than touching the snap toggle itself.
    const bypassSnap = event.sourceEvent?.altKey;
    //: **Snapped by how far it moved, not by where it is** (the owner:
    //: "dragging a objects doesnt stay on the mouse and goes off to the side
    //: of where my mouse was on the object when I started dragging it").
    //: Rounding the absolute position means an item that was not already on a
    //: grid line jumps up to half a cell the instant the drag begins and then
    //: stays that far from the cursor for the rest of it: the item is under
    //: your pointer when you press and beside it when you move. Rounding the
    //: *delta* keeps the grab point exactly where you took hold of it and
    //: still moves in whole grid steps, and for the ordinary case (an item
    //: that is already on the grid, because it was placed or dragged with
    //: snap on) the two are the same number.
    //: Shift keeps the move on one axis (see `wbAxisLock`).
    const lock = wbAxisLock(d._rawX - d._dragOriginX, d._rawY - d._dragOriginY, event.sourceEvent?.shiftKey);
    d.x = d._dragOriginX + (lock === "y" ? 0 : wbSnap(d._rawX - d._dragOriginX, bypassSnap));
    d.y = d._dragOriginY + (lock === "x" ? 0 : wbSnap(d._rawY - d._dragOriginY, bypassSnap));
    // Smart alignment guides: asked for directly ("draw.io and Microsoft
    // PowerPoint have... dotted alignment rule guides"). Same Alt bypass as
    // grid-snap just above: one modifier, "no snap assistance", not two.
    if (!bypassSnap) {
      const w = d.width || WB_CARD_DEFAULT_SIZE.w, h = d.height || WB_CARD_DEFAULT_SIZE.h;
      const group = wbBulkGroupBox(d, "node");
      const own = wbRotatedBounds(d.x, d.y, w, h, wbItemRotation("node", d));
      const { dx, dy, guideLines } = wbAlignmentGuides(
        wbDragExcludeKeys(d, "node"),
        group ? group.x : own.x,
        group ? group.y : own.y,
        group ? group.w : own.w,
        group ? group.h : own.h,
        wbAlignTol()
      );
      if (lock !== "y") d.x += dx;
      if (lock !== "x") d.y += dy;
      wbShowAlignmentGuides(guideLines);
    } else {
      wbClearAlignmentGuides();
    }
    d3.select(this).style("transform", wbItemTransform(d));
    wbQueueSelectionBar();
    // The rest of the selection first, so a line from this card to another
    // selected one is drawn to where that one is now (see `wbApplyBulkMove`).
    if (d._bulkOrigin) wbApplyBulkMove(d._bulkOrigin, d.x - d._dragOriginX, d.y - d._dragOriginY);
    // Update this card's own link lines directly rather than a full
    // wbScheduleRender(), see wbUpdateLinkedSketches's own comment for why
    // that was the "glitchy and slow to update" report.
    wbUpdateLinkedSketches(d.id, d._linkedSketches);
  }
}

// The Whiteboards sub-tab's own two controls. This DOMContentLoaded
// listener used to also hold the #library-subtabs switcher and the
// Documents/Media sub-tabs' refresh/search/upload wiring: none of that is
// whiteboard's own code (it switches between and wires OTHER Library
// sub-tabs), and it has moved to library.js, which is the Library's actual
// home now (ROADMAP.md §88.3 flagged this as "an accident worth fixing
// while splitting"). Only its listeners survive here, unchanged.
onDomReady(() => {
  //: "Whiteboard" says Board whatever kind was made last (INBOX 733: it
  //: opened on Mind map after a map), and the canvas is shown by the dialog's
  //: answer, never before it.
  //: The empty tab's New mind map (decision 38): the gallery on its Mind
  //: map tab. Bound here, not in navigation.js's empty-state table, because
  //: the empty state is drawn by this file, and the boot scripts are capped.
  $("library-boards-new-map")?.addEventListener("click", () => wbNewUntitledBoard("map"));
  $("wb-boards-new")?.addEventListener("click", () => wbNewUntitledBoard());
  //: Import (§5 item 17). The button opens the hidden input, the input does
  //: the work: the app's own file-picking pattern (`pickJsonFile`,
  //: `importMarkdown`), so a file arrives the same way here as everywhere
  //: else. Wired on the input's `change` rather than assigned as `onchange`
  //: inside the click handler, because a second click would then rebind it and
  //: `tests/test_frontend_handlers.py` exists to catch exactly that shape.
  //: The third way to start a map, beside New mind map and Import outline
  //: (§5 item 15). In the same row because it is the same kind of action:
  //: "start a map", from notes that already exist rather than from an empty
  //: canvas or from a file.
  $("wb-boards-generate")?.addEventListener("click", () => wbGenerateMapFromNotes());
  $("wb-boards-import")?.addEventListener("click", () => {
    $("wb-import-map-file")?.click();
  });
  $("wb-import-map-file")?.addEventListener("change", (event) => wbImportOutlineFile(event));
  //: **Import by drop** (MINDMAP_PLAN §12.2 item 10): an outline file let go
  //: anywhere on the boards landing imports as the Import button's picker
  //: would. Only a drag that carries a file is taken, so a card dragged
  //: inside the gallery keeps its own handling.
  const landing = $("wb-boards-landing");
  const carriesFile = (e) => [...(e.dataTransfer?.items || [])].some((i) => i.kind === "file");
  landing?.addEventListener("dragover", (e) => {
    if (!carriesFile(e)) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = "copy";
  });
  landing?.addEventListener("drop", (e) => {
    const file = e.dataTransfer?.files?.[0];
    if (!file) return;
    e.preventDefault();
    if (!/\.(opml|xml|mm|xmind|md|markdown|txt)$/i.test(file.name)) {
      toast("Drop an outline to import it: OPML, FreeMind, XMind, Markdown or plain text.", "info");
      return;
    }
    wbImportOutlineFile({ target: { files: [file], value: "" } });
  });
});
onSurface("board", () => $("wb-back-to-boards")?.addEventListener("click", wbShowBoardsLanding));

// The Whiteboards tab has two views sharing one subtab: a boards gallery
// (the landing view) and the actual canvas, asked for directly, replacing
// two separate doors onto the whiteboard (a bare canvas tab defaulting to
// whatever board was last open, plus a picker tab) with one. Canvas init
// is lazy and idempotent (`wbInitialized` guards it), so switching between
// the two views repeatedly costs nothing after the first time.
function wbShowCanvasView() {
  surfaceBuild("board");
  $("wb-boards-landing")?.classList.add("hidden");
  const view = $("wb-canvas-view");
  //: Whiteboards and mind maps both draw here. Fade in once the board has
  //: had its first frames, as the graph does, so the shapes are not seen
  //: arriving mid-layout (owner, 2026-10-12).
  view?.classList.add("wb-entering");
  view?.classList.remove("hidden");
  setTimeout(initWhiteboard, 50);
  setTimeout(() => view?.classList.remove("wb-entering"), 250);
}

function wbShowBoardsLanding() {
  //: A document's board panel (documents-board.js) answers this by closing itself: the board list is not what that page wants.
  if (!document.dispatchEvent(new CustomEvent("wb-leave", { cancelable: true }))) return;
  wbRememberBoardView();
  // First, because the boards list lives inside the element full screen
  // pins to the viewport, see `wbLeaveFullscreen` for what that looked
  // like when it was left on.
  wbLeaveFullscreen();
  $("wb-canvas-view")?.classList.add("hidden");
  $("wb-boards-landing")?.classList.remove("hidden");
  renderLibraryBoardsGallery();
  if (typeof scheduleUndoBar === "function") scheduleUndoBar();
}

//: Whether the board still has a use for an Escape (a selection, a tool, a menu, a find bar, a gesture, presenting): a document's
//: board panel (documents-board.js) closes only on the Escape the board did not need.
wbShowBoardsLanding.wantsEscape = () => {
  if (wbSelectedItem || wbMultiSelection.size > 0 || wbPresent) return true;
  if (window.currentTool && window.currentTool !== "select") return true;
  if (wbCtxMenuEl && !wbCtxMenuEl.classList.contains("hidden")) return true;
  if (document.getElementById("wb-search-bar")?.classList.contains("hidden") === false) return true;
  return Boolean(document.querySelector(".wb-marquee, .wb-lasso"));
};

//: Leaving the canvas has to leave full screen with it.
//:
//: Reported: "if i am still in whiteboard fullscreen and press the back to
//: boards button, the ui is broken." It was: `wb-fullscreen` pins
//: `#library-view-whiteboard` to `position: fixed; inset: 0` at z-index
//: 1000, and the *boards list* lives inside that same element, so going
//: back left the list covering the entire window, over the app header, the
//: Library sub-tabs and everything else, with no visible way out because the
//: control that turns it off is on the canvas you just left.
//:
//: Called from every exit rather than only from the back button: the board
//: picker, a board card and the Library sub-tabs can all take you off the
//: canvas too, and each would have had the same bug.
function wbLeaveFullscreen() {
  document.getElementById("library-view-whiteboard")?.classList.remove("wb-fullscreen");
  const button = document.getElementById("wb-fullscreen");
  if (button) {
    button.classList.remove("is-on");
    button.title = "Full screen (Esc to leave)";
    const icon = button.querySelector("i");
    if (icon) icon.className = "ph ph-arrows-out";
  }
}

//: Everything the board just left may still have a frame or a timer in
//: flight (audit 1028 B31): a reveal of the old selection scrolled the new
//: board, a moving flag stuck on. They are cancelled and their guards reset;
//: an unsaved nudge is written out, not dropped.
function wbCancelBoardTimers() {
  const frames = [wbClampSyncFrame, wbZoomFrame, wbCullFrame, wbSelectionBarFrame, wbRenderFrame];
  for (const id of frames) if (id) cancelAnimationFrame(id);
  wbClampSyncFrame = null;
  wbZoomFrame = 0;
  wbZoomPending = null;
  wbCullFrame = 0;
  wbSelectionBarFrame = 0;
  wbRenderFrame = 0;
  wbRenderQueued = false;
  for (const id of [wbRevealTimer, wbStickyDates.timer, wbAddGate.panBarTimer, wbMarkMoving.timer]) clearTimeout(id);
  wbRevealTimer = 0;
  wbStickyDates.timer = 0;
  wbAddGate.panBarTimer = 0;
  wbMarkMoving.timer = 0;
  wbMapCache.cancelAll();
  document.getElementById("wb-canvas-view")?.classList.remove("wb-moving");
  return wbFlushNudge();
}

// Jump to the real whiteboard canvas with a specific board loaded.
async function openWhiteboardBoard(boardId, opts = null) {
  //: A board restored with the page gets here mid-bundle; its timers and Library side are later files (INBOX 1530 f, #222).
  await ensureModule("boards");
  //: Opening a board is the page board's; an embed that was live gives its globals back first (L-whiteboard-53).
  wbInstances.activate(wbInstances.page);
  wbRememberBoardView();
  //: `stay`: the caller has put `#library-view-whiteboard` where the board is wanted (a document's board panel, documents-board.js).
  if (!opts?.stay) {
    openWhiteboardBoard.at = performance.now(); // read by boards-gallery.js `show`: its landing must not hide this board
    switchTab("library");
    //: Not pressed when it is already the chosen sub-tab: that press draws the boards list on a promise, which landed after
    //: `wbShowCanvasView` below and hid the board just opened (a second open from a board, seen in wbtrash660.js).
    const sub = document.querySelector('#library-subtabs button[data-target="library-view-whiteboard"]');
    if (!sub?.classList.contains("active")) sub?.click();
  }
  wbShowCanvasView();
  const nudgeSaved = wbCancelBoardTimers();
  wbLinkParseCache.clear(); // the next board's sketches are other ids
  //: **What the last board's renders left behind is dropped here** (audit 1028 B39:
  //: render state lived at module level with no reset). A frame queued for the old
  //: board is called off, and the element, size, colour and overview caches are
  //: emptied, so nothing measured on one board answers for the next.
  if (wbRenderFrame) cancelAnimationFrame(wbRenderFrame);
  wbRenderFrame = 0;
  wbRenderQueued = false;
  wbItemElCache.clear();
  wbItemElIndex.count = -1;
  wbClearMapNodeSizeCache();
  Object.assign(wbBoardBgCache, { sig: "", pass: false });
  wbNavState.stale = true;
  await new Promise((resolve) => setTimeout(resolve, 60));
  await nudgeSaved;
  window.currentBoardId = boardId ?? null;
  wbUpdateUndoRedoButtons();
  // Anything a previous board's selection drag left behind goes now. The
  // rectangle lives in `#wb-zoom-group`, which the render joins by data and
  // never empties, so without this a stray one followed you from board to
  // board and read as "a permanent selection box on my mindmap".
  wbClearSelectionOverlays();
  await fetchWhiteboardState();
  wbScheduleRender();
  await wbMigrateBackground();
  wbApplyBackground();
  //: Linked library copies whose source changed since the board was last open are brought up to date (library-more.js).
  wbFmtState.libraryMore?.copies.refresh();
  //: Bound frames (L-whiteboard-12): a card whose note changed elsewhere moves to its column.
  if (boardId != null && (wbState.objects || []).some((o) => o.kind === "frame" && o.data?.binds)) {
    apiJson(`/whiteboard/boards/${boardId}/binds/sync`, { method: "POST" }).then((got) => got?.moved?.length && fetchWhiteboardState().then(wbScheduleRender))
      .catch(() => toast("The bound frames could not check their cards; they are checked again when the board opens.", "info"));
  }
  renderWbGestureHints();
  //: Rendered now rather than on the next frame, because the framing below
  //: measures the nodes it is about to fit (a map node is `height: auto`, so
  //: its real size only exists once it is in the document).
  if (wbIsMap()) renderWhiteboardNow();
  wbRestoreOrFrameBoard(boardId ?? null, Boolean(opts?.restore));
  //: **A board is a place, so opening one is a navigation.** Asked as part of
  //: "is everythign wired to the nav history and universal undo/redo": it was
  //: not. `switchTab("library")` above records "library", and then opening
  //: board after board recorded nothing at all, so Back from the fourth board
  //: you looked at left the Library entirely rather than returning to the
  //: third. Documents, graph focus and chat conversations all already record
  //: their own identity this way (`doc:{id}`, `focus:{id}`, `conv:{id}`); this
  //: is the same key for the same reason.
  if (typeof recordTabVisit === "function" && !opts?.stay) {
    //: `mapBoardById` (note-cards.js) is the one board index every surface shares.
    const boardTitle = boardId ? mapBoardById(boardId)?.title : "";
    recordTabVisit("library", boardId ? `board:${boardId}` : "library-view-whiteboard", boardTitle || "");
  }
}

//: Where "concept maps are unlearnable" is actually answered.
//:
//: The map creates well, a root card, selected, and a toast naming Tab and
//: Enter. Then the toast goes, and the board says nothing at all about the
//: three gestures that *are* the feature. Everything else here is discoverable
//: by pointing at it; these are keys, and a key you were told about once is a
//: key you do not have.
//:
//: Two rules, both from the capture box's own hint: teach at the moment it
//: applies, and never nag. So it shows while the board is still small enough
//: to be starting (a map you have built out has taught you these already), and
//: dismissing it is permanent.
const WB_GESTURES_DISMISSED = "wbGesturesDismissed";
//: Up to this many cards still counts as "just started". Four is a root and
//: three branches: by then you have either used Tab or you are doing
//: something else with the board.
const WB_GESTURE_CARD_LIMIT = 4;

//: **Only while a card is selected, and never on a mind map** (the map UX
//: remainder, OPEN.md: "the keyboard hint strip sits over the canvas across
//: the bottom and covers content"). Measured before: on a map it counted
//: note cards, of which a map has none, so it stood over the bottom of every
//: new map (it said "the selected card" with nothing selected) until someone
//: found its x. Two things now teach the same keys at the moment they apply:
//: a selected topic's ring prints "Tab adds a child, Enter one beside, C
//: folds, Delete removes", and the rail's ? lists every key. So on a map the
//: strip is the third copy and goes; on a board it shows only while exactly
//: one note card is selected, which is the only time Tab and Enter do
//: anything, and never over the card it is about.
//: Read from storage once: this runs on every selection change.
let wbGesturesDismissed = null;

function renderWbGestureHints() {
  const strip = document.getElementById("wb-gestures");
  if (!strip) return;
  if (wbGesturesDismissed === null) {
    try {
      wbGesturesDismissed = prefs.get(WB_GESTURES_DISMISSED, null) === "1";
    } catch {
      //: A browser with storage blocked shows the hint every time, which is the
      //: safe direction to fail in: an extra reminder beats a silent feature.
      wbGesturesDismissed = false;
    }
  }
  const cards = (wbState && wbState.nodes ? wbState.nodes.length : 0);
  const card = !wbIsMap() && wbMultiSelection.size === 0 && wbSelectedItem?.kind === "node"
    ? wbInstances.query(`.node-card[data-id="${wbSelectedItem.id}"]`)
    : null;
  const wanted = Boolean(card) && !wbGesturesDismissed && cards <= WB_GESTURE_CARD_LIMIT;
  strip.classList.toggle("hidden", !wanted);
  if (!wanted) return;
  const a = strip.getBoundingClientRect();
  const b = card.getBoundingClientRect();
  const over = a.left < b.right && a.right > b.left && a.top < b.bottom && a.bottom > b.top;
  if (over) strip.classList.add("hidden");
}
window.renderWbGestureHints = renderWbGestureHints;

onSurface("board", () => {
  document.getElementById("wb-gestures-dismiss")?.addEventListener("click", () => {
    try {
      prefs.set(WB_GESTURES_DISMISSED, "1");
    } catch {
      /* nothing to persist to, hiding it for this session is still correct */
    }
    wbGesturesDismissed = true;
    document.getElementById("wb-gestures")?.classList.add("hidden");
  });
});

/** Full screen for the board, asked for directly ("the whiteboard
 *  definately needs a fullscreen mode because it feels too squished").
 *
 *  Measured before building: the canvas is 1376x676 inside a 1440x900
 *  window, so a quarter of the height is the app header, the Library
 *  sub-tab bar and the status bar. None of those help while drawing.
 *
 *  The class goes on `#library-view-whiteboard`, not on `#wb-canvas-view`.
 *  That looks like the wrong element and is not: `#wb-canvas-view` is a
 *  wrapper whose children are all absolutely positioned, so it measures
 *  **0px tall**: giving it `position: fixed; inset: 0` would size it, but
 *  the board would then be sized by a parent that had not been, which is
 *  the shape of bug this file already has a comment about further down.
 *  `#library-view-whiteboard` is the element that actually carries the
 *  board's height today, so it is the one to promote.
 *
 *  Escape leaves, matching every other full-screen surface in the app.
 */
function toggleWhiteboardFullscreen(force) {
  const host = document.getElementById("library-view-whiteboard");
  if (!host) return;
  // Only a real boolean forces a state; anything else (notably a DOM event
  // arriving from a listener registered by reference) means "toggle". Belt
  // and braces with the arrow at the call site, this one is what makes the
  // function safe to pass around at all.
  const on =
    typeof force === "boolean" ? force : !host.classList.contains("wb-fullscreen");
  host.classList.toggle("wb-fullscreen", on);
  const button = document.getElementById("wb-fullscreen");
  if (button) {
    button.classList.toggle("is-on", on);
    button.title = on ? "Leave full screen (Esc)" : "Full screen (Esc to leave)";
    const icon = button.querySelector("i");
    if (icon) icon.className = on ? "ph ph-arrows-in" : "ph ph-arrows-out";
  }
  // d3's zoom reads the container's size when it clamps a pan, and the
  // floating panels are positioned against it, neither notices a class
  // change on an ancestor on its own.
  window.dispatchEvent(new Event("resize"));
}

// Escape leaves full screen. Capture phase and a check that we are actually
// in it, so this never swallows an Escape meant for a dialog opened *over*
// the board (the properties panel's own inputs, a confirm), those are the
// common case and closing the whole board instead would be maddening.
document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape") return;
  const host = document.getElementById("library-view-whiteboard");
  if (!host || !host.classList.contains("wb-fullscreen")) return;
  //: A document's board panel is the board's own window, so its overlay is not a dialog over the board.
  if (document.querySelector(".modal-overlay:not(.hidden):not(.doc-board-overlay), .lightbox")) return;
  toggleWhiteboardFullscreen(false);
});

// whiteboard-present.js: whiteboard-present.js: presenting a board's frames: the slide walk, the laser po (moved out, L286).

let wbPresent = null;


//: The gestures that are one Undo step each, read off what they changed
//: (`wbRecordGesture`). Wrapped by name so every caller, the keys, the ring,
//: the menus, gets the recorded one. A gesture inside another runs plain.
//: `wbMapTransplant` keeps its own entry (it knows where a drag began), so
//: what it calls is not recorded twice.
const WB_RECORDED = [
  "wbMapSetTheme", "wbMapClearEveryTopic", "wbMapSetNumbered", "wbMapExpandAll", "wbMapFoldToLevel", "wbMapAddChild",
  "wbMapAddRootAt", "wbMapAddReference", "wbMapDuplicateTopic", "wbMapClearToOneTopic",
  "wbMapToggleCollapse", "wbMapCopyBranch", "wbMapRemoveKeepingBranch", "wbMapSever",
  "wbMapReverseCrossLink", "wbMapCrossLinkToBranch", "wbMapCutCrossLink", "wbMapReverseEdge",
  "wbMapSetLayout", "wbMapInsertBetween", "wbMapOutdent", "wbMapMoveAmongSiblings", "wbMapSortChildren",
  "wbMapTidy", "wbGroupSelection", "wbUngroupSelection",
  "wbPasteCopiedStyle", "wbMapUseLookForLevel", "wbArrangeMindMap", "wbMindMapAddCard", "wbBucketFillSketch", "wbFitToText",
];
for (const name of WB_RECORDED) {
  if (wbRecordedNames.has(name)) continue; //: Already bound through `wbRecorded` in its own file.
  const plain = window[name];
  //: `Object.assign` carries a gesture's helper properties (`wbMapFoldToLevel.open`, `.sync`) across.
  if (typeof plain === "function") window[name] = Object.assign((...args) => wbRecordGesture(plain, args), plain);
}
if (typeof window.wbMapTransplant === "function" && !window.wbMapTransplant.depthOnly) {
  window.wbMapTransplant = wbRecordedDepth(window.wbMapTransplant);
}

// ---- from selection.js (search-boot-1005): pickNotesDialog, addBoardToNote ----
// Moved whole. Every use is in this file, so it is not needed before this file loads.

//: **Several notes at once**, which `pickLibraryItemDialog` deliberately
//: cannot do: "make a map of these notes" is a list you assemble, so the rows
//: are the Attach picker's (`notePickerRow`: tile, name over its facts, a
//: check ring) and the dialog closes on its one filled button. The ticks live
//: in `chosen`, not the DOM, so a note stays chosen when a search hides its
//: row. Resolves with `{id, label}`s in the order they were ticked, or null
//: when dismissed; the button stays off until one row is on.
function pickNotesDialog(message, { confirmLabel = "Continue", limit = 40 } = {}) {
  return new Promise((resolve) => {
    const list = document.createElement("ul");
    list.className = "note-picker-list entry-pick-list";
    list.setAttribute("aria-label", "Your notes");
    const shell = pickerDialog({ title: message, placeholder: "Search your notes…", searchLabel: message, list });
    const chosen = new Map();
    const count = document.createElement("span");
    count.className = "muted";
    const confirm = smallButton(confirmLabel, confirmLabel, () => {
      if (chosen.size) shell.close([...chosen.entries()].map(([id, label]) => ({ id, label })));
    }, false);
    confirm.classList.add("accent");
    const cancel = smallButton("Cancel", "Cancel", () => shell.close(null));
    const foot = document.createElement("div");
    foot.className = "row space-dialog-actions";
    foot.append(count, cancel, confirm);

    const refreshCount = () => {
      count.textContent = chosen.size
        ? `${nounCount(chosen.size, "note")} chosen${chosen.size >= limit ? ` (the most is ${limit})` : ""}`
        : "Pick the notes to build from.";
      confirm.disabled = chosen.size === 0;
    };
    const shape = {
      label: (row) => noteLabel(row, 200),
      icon: () => "ph:note",
      meta: notePickerShape("notes").meta,
      isOn: (row) => chosen.has(row.id),
      add: (row) => {
        if (chosen.size >= limit) return false;
        chosen.set(row.id, noteLabel(row, 70));
      },
      remove: (row) => chosen.delete(row.id),
      full: `That is the most this can use at once: ${limit} notes.`,
    };
    const paint = () => {
      const term = shell.search.value.trim();
      const rows = (typeof allEntries !== "undefined" ? allEntries : [])
        .filter((entry) => !entry.is_draft && !entry.is_deleted && !entry.is_board && !entry.is_private)
        .filter((entry) => !term || noteLabel(entry, 200).toLowerCase().includes(term.toLowerCase()))
        .slice(0, 60);
      if (!rows.length) {
        const empty = pickerEmpty("notes", term, "ph:note", LIBRARY_PICK_SOURCES[0].hint);
        return pickerListState(list, empty.text, empty);
      }
      list.replaceChildren(
        ...rows.map((row) => {
          const li = notePickerRow(shape, row);
          li.classList.add("entry-pick-check");
          li.querySelector(".note-picker-box").addEventListener("change", refreshCount);
          return li;
        })
      );
      notePickerRoving(list, 0);
    };
    //: The keys: Down from the field enters the list, Up and Down walk it
    //: (Up from the first row goes back), Space ticks, Enter confirms.
    shell.search.addEventListener("keydown", (event) => {
      if (event.key !== "ArrowDown") return;
      event.preventDefault();
      list.querySelector(".note-picker-box")?.focus();
    });
    list.addEventListener("keydown", (event) => {
      const boxes = [...list.querySelectorAll(".note-picker-box")];
      const at = boxes.indexOf(document.activeElement);
      if (at < 0) return;
      if (event.key === "Enter") {
        event.preventDefault();
        return confirm.click();
      }
      const to = { ArrowDown: at + 1, ArrowUp: at - 1, Home: 0, End: boxes.length - 1 }[event.key];
      if (to === undefined) return;
      event.preventDefault();
      if (to < 0) return shell.search.focus();
      notePickerRoving(list, Math.min(to, boxes.length - 1))[Math.min(to, boxes.length - 1)].focus();
    });
    shell.search.addEventListener("input", paint);
    paint();
    refreshCount();
    shell.open(resolve, { foot });
  });
}

//: **The board's own way into a note** (INBOX 309), through
//: `appendSelectionToNote` rather than a second write path (one undo). The
//: index is invalidated first: a board made in the last eight seconds would
//: otherwise paint as a tombstone (`loadMapBoardIndex`'s `force`).
async function addBoardToNote(board) {
  if (!board || board.id == null) {
    toast("The default board has no name to put in a note. Make a board first.");
    return;
  }
  const isMap = board.type !== "board";
  await appendSelectionToNote(boardEmbedMarkdown(board), {
    jump: false,
    what: isMap ? "that map" : "that board",
    message: `Add \u201c${board.title || (isMap ? "this map" : "this board")}\u201d to which note?`,
  });
  if (typeof loadMapBoardIndex === "function") loadMapBoardIndex(true);
}

// `backdropIsDark` is about what the stroke composites *against*, which is
// not the same question as which theme is on. The pad's strokes land in their
// own transparent canvas stacked over a separate paper canvas, so the
// backdrop a canvas blend sees is the other strokes and never the paper: the
// pad passes false in both themes. The board's paths blend against the board
// itself, so it passes the resolved mode.
function highlighterBlend(backdropIsDark) {
  return backdropIsDark ? HIGHLIGHTER_STYLE.blendOnDark : HIGHLIGHTER_STYLE.blendOnLight;
}
