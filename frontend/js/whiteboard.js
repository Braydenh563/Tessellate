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
//: The phone tools opener's label, refreshed from wherever a tool is chosen
//: (`selectWbTool` is inside `initWhiteboard`'s closure, and so is the
//: opener). Null until a board has been opened once.
let wbToolsOpenerSyncRef = null;
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
// Same shape, for refreshing the "Line ends" control's displayed value when
// the active tool switches between Line and Arrow (each now has its own
// remembered end-style: see the live-reported bug fix in `initWhiteboard`).
let wbRefreshArrowStyleControlRef = null;
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
const WB_EXPANDED_MAX = 500;

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
  for (const card of document.querySelectorAll(".node-card")) {
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

// {action: "delete"|"create", kind: "sketch"|"node", payload, id}. Bounded
// so an hour of erasing doesn't grow this forever; only the newest matters.
let wbUndoStack = [];
// ROADMAP.md Tier 2 §11: a redo stack, the same shape as the sketch pad's
// own history: cleared whenever a fresh action is pushed onto wbUndoStack,
// since redoing something that predates a new action would resurrect a
// version of the board the newer action never saw.
let wbRedoStack = [];
//: **A hundred steps, not twenty** (INBOX 445). Building a sixty-topic map
//: by keys pushes two entries a topic (the create and the rename), so twenty
//: reached back ten topics; Excalidraw keeps about a hundred and tldraw more.
//: An entry is a payload of one row (a deleted map branch, its rows), so the
//: whole stack stays well under a megabyte at a hundred.
const WB_UNDO_MAX = 100;
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
  d3.select("#wb-html-layer").style("transform", css);
  d3.select("#wb-svg-layer").style("transform", css);
  d3.select("#wb-overlay-layer").style("transform", css);
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
  const rect = document.getElementById("whiteboard-container")?.getBoundingClientRect() ?? null;
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
  const el = document.getElementById("whiteboard-container");
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
  return wbScreenToBoard(clientX, clientY, wbCanvasOrigin(), d3.zoomTransform(document.getElementById("whiteboard-container")));
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
  const el = document.getElementById("whiteboard-container");
  if (el && !el.classList.contains("wb-hand-pan")) el.classList.add("wb-hand-pan");
}

function wbEndPanShield() {
  document.getElementById("whiteboard-container")?.classList.remove("wb-hand-pan");
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
const WB_MOVING_MS = 180;
function wbMarkMoving() {
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
  const container = document.getElementById("whiteboard-container");
  const drag = wbNavState.drag;
  const size = drag
    ? { width: drag.width, height: drag.height }
    : container ? { width: container.clientWidth, height: container.clientHeight } : null;
  wbSyncGridToTransform(t);
  wbFmtState.opts?.drawRulers(t);
  if (typeof nameMarkBuddyCanvasZoom === "function") nameMarkBuddyCanvasZoom(t.k);
  //: In the same frame as the transform it answers, so a topic panned into
  //: view is drawn on the frame it arrives in rather than one later.
  wbCullNow(t, size);
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
      const container = document.getElementById("whiteboard-container");
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

function wbCullNow(transform, size) {
  if (wbCullHeld) return;
  const container = document.getElementById("whiteboard-container");
  const layer = document.getElementById("wb-html-layer");
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
  const mx = w * WB_CULL_MARGIN;
  const my = h * WB_CULL_MARGIN;
  const x0 = (-mx - t.x) / k;
  const x1 = (w + mx - t.x) / k;
  const y0 = (-my - t.y) / k;
  const y1 = (h + my - t.y) / k;
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
  for (const el of layer.children) {
    const d = el.__data__;
    if (!d || typeof d.x !== "number") continue;
    const tiny = (d.width || WB_CARD_DEFAULT_SIZE.w) * k < WB_TINY_SCREEN_W || (d.height || WB_CARD_DEFAULT_SIZE.h) * k < WB_TINY_SCREEN_H;
    if (el.classList.contains("wb-tiny") !== tiny) el.classList.toggle("wb-tiny", tiny);
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
  const edges = document.querySelector("#wb-zoom-group .wb-map-edges");
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
      if (held.wrap.classList.contains("wb-culled") !== cull) held.wrap.classList.toggle("wb-culled", cull);
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

let wbInvZoomTimer = 0;

function wbSyncGridToTransform(transform) {
  const el = document.getElementById("whiteboard-container");
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
  const inv = String(1 / (t.k || 1));
  clearTimeout(wbInvZoomTimer);
  if (wbInvZoomValue === inv) return;
  wbInvZoomTimer = setTimeout(() => wbPublishInvZoom(el, inv), 120);
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
  ".wb-map-collapse",
  ".wb-map-count",
  ".wb-sketch-rotate-handle",
  ".wb-rotate-handle-stem",
];
let wbInvZoomSheet = null;
let wbInvZoomValue = "1";

//: **The board's layers are rasterised again once a zoom has settled**
//: (INBOX 791, "labels look pixelated"). A layer promoted with `will-change:
//: transform` keeps the raster it was first painted at, and a compositor
//: that does not re-raster on a later scale change draws a link label, which
//: is SVG text, as a stretched bitmap. Dropping the hint for one frame and
//: restoring the sheet's own makes the next paint at the current scale; all
//: three go in the same frame so the pan pipelines stay together.
function wbRefreshRaster() {
  const layers = ["wb-html-layer", "wb-svg-layer", "wb-overlay-layer"].map((id) => document.getElementById(id)).filter(Boolean);
  for (const layer of layers) layer.style.willChange = "auto";
  requestAnimationFrame(() => {
    for (const layer of layers) layer.style.willChange = "";
  });
}

function wbPublishInvZoom(el, inv) {
  wbInvZoomValue = inv;
  wbRefreshRaster();
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
  wbInvZoomSheet.replaceSync(`${WB_INV_ZOOM_GRIPS.join(", ")} { --wb-inv-zoom: ${inv}; }`);
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
  const container = document.getElementById("whiteboard-container");
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
  const node = document.querySelector(`.wb-object[data-id="${frame.id}"]`);
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

//: **The box the whole selection occupies, for a group drag.**
//:
//: A single drag asks the guides about the item under the pointer. A group
//: drag has no single item to ask about, which is why it used to ask about
//: nothing: the guide block was written `if (!bypassSnap && !d._bulkOrigin)`,
//: so selecting several things and moving them turned the alignment guides
//: off, exactly when lining things up is what you are doing.
//:
//: What a group should align is its own outer box, which is what every
//: drawing app does with a multi-selection. `_bulkOrigin` holds every *other*
//: member at the position the drag started from (the dragged item is
//: deliberately not in it, since its own handler moves it), so the group's
//: starting box is those plus the dragged item's own origin, and its box
//: this frame is that shifted by how far the dragged item has come.
//:
//: Returns null when there is nothing to measure, so the caller falls back
//: to the plain single-item path rather than guessing.
//: `self` is for a dragged item that has no x/y/width/height of its own: a
//: sketch is a path, and its box has to be measured from that path rather
//: than read off the datum. Pass `{minX, minY, maxX, maxY, dx, dy}` (the
//: item's box *before* this drag, and how far it has come) and the rest of
//: the maths is identical, which is the point of threading it through here
//: instead of writing the union a second time.
function wbBulkGroupBox(d, kind, self = null) {
  if (!d._bulkOrigin || !d._bulkOrigin.size) return null;
  if (!self && (d._dragOriginX === undefined || d._dragOriginY === undefined)) return null;
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  const add = (box) => {
    if (!box) return;
    minX = Math.min(minX, box.minX);
    minY = Math.min(minY, box.minY);
    maxX = Math.max(maxX, box.maxX);
    maxY = Math.max(maxY, box.maxY);
  };
  add(
    self || {
      minX: d._dragOriginX,
      minY: d._dragOriginY,
      maxX: d._dragOriginX + (d.width || WB_CARD_DEFAULT_SIZE.w),
      maxY: d._dragOriginY + (d.height || WB_CARD_DEFAULT_SIZE.h),
    }
  );
  for (const entry of d._bulkOrigin.values()) {
    if (entry.kind === "sketch") {
      add(wbPathBBox(entry.d));
    } else if (entry.x !== undefined) {
      add({
        minX: entry.x,
        minY: entry.y,
        maxX: entry.x + (entry.item.width || WB_CARD_DEFAULT_SIZE.w),
        maxY: entry.y + (entry.item.height || WB_CARD_DEFAULT_SIZE.h),
      });
    }
  }
  if (!Number.isFinite(minX)) return null;
  const dx = self ? self.dx : d.x - d._dragOriginX;
  const dy = self ? self.dy : d.y - d._dragOriginY;
  return { x: minX + dx, y: minY + dy, w: maxX - minX, h: maxY - minY };
}

//: Which keys the guides must ignore: everything moving this frame. The
//: dragged item alone for a plain drag, the whole selection for a group one,
//: since `_bulkOrigin` was built from it.
function wbDragExcludeKeys(d, kind) {
  if (!d._bulkOrigin || !d._bulkOrigin.size) return new Set([wbMultiKey(kind, d.id)]);
  return new Set([wbMultiKey(kind, d.id), ...d._bulkOrigin.keys()]);
}

function wbAlignmentGuides(excludeKeys, x, y, w, h, tol = WB_ALIGN_SNAP_PX) {
  const dragged = { left: x, centerX: x + w / 2, right: x + w, top: y, centerY: y + h / 2, bottom: y + h };
  let bestX = null, bestY = null;
  const others = wbGuideBoxes(excludeKeys, { x, y, w, h });
  {
    for (const box of others) {
      const other = {
        left: box.minX, centerX: (box.minX + box.maxX) / 2, right: box.maxX,
        top: box.minY, centerY: (box.minY + box.maxY) / 2, bottom: box.maxY,
      };
      for (const edge of ["left", "centerX", "right"]) {
        if (box.only && box.only !== edge) continue;
        const delta = other[edge] - dragged[edge];
        if (Math.abs(delta) <= tol && (!bestX || Math.abs(delta) < Math.abs(bestX.delta))) {
          bestX = { delta, at: other[edge], y1: Math.min(dragged.top, other.top), y2: Math.max(dragged.bottom, other.bottom), kind: edge === "centerX" ? "center" : "edge" };
        }
      }
      for (const edge of ["top", "centerY", "bottom"]) {
        if (box.only && box.only !== edge) continue;
        const delta = other[edge] - dragged[edge];
        if (Math.abs(delta) <= tol && (!bestY || Math.abs(delta) < Math.abs(bestY.delta))) {
          bestY = { delta, at: other[edge], x1: Math.min(dragged.left, other.left), x2: Math.max(dragged.right, other.right), kind: edge === "centerY" ? "center" : "edge" };
        }
      }
    }
  }
  //: **The line spans every box that shares it** (Figma, Miro), not only the
  //: nearest one: a second pass over the boxes, run only on a frame that
  //: snapped, extends the line across each box whose edge or centre sits on
  //: it and across the dragged box as it lands.
  const guideLines = [];
  const dx0 = bestX ? bestX.delta : 0, dy0 = bestY ? bestY.delta : 0;
  if (bestX) {
    let y1 = Math.min(bestX.y1, dragged.top + dy0), y2 = Math.max(bestX.y2, dragged.bottom + dy0);
    for (const box of others) {
      if (Math.abs(box.minX - bestX.at) < 0.5 || Math.abs(box.maxX - bestX.at) < 0.5 || Math.abs((box.minX + box.maxX) / 2 - bestX.at) < 0.5) {
        y1 = Math.min(y1, box.minY);
        y2 = Math.max(y2, box.maxY);
      }
    }
    guideLines.push({ x1: bestX.at, y1: y1 - 12, x2: bestX.at, y2: y2 + 12, kind: bestX.kind });
  }
  if (bestY) {
    let x1 = Math.min(bestY.x1, dragged.left + dx0), x2 = Math.max(bestY.x2, dragged.right + dx0);
    for (const box of others) {
      if (Math.abs(box.minY - bestY.at) < 0.5 || Math.abs(box.maxY - bestY.at) < 0.5 || Math.abs((box.minY + box.maxY) / 2 - bestY.at) < 0.5) {
        x1 = Math.min(x1, box.minX);
        x2 = Math.max(x2, box.maxX);
      }
    }
    guideLines.push({ x1: x1 - 12, y1: bestY.at, x2: x2 + 12, y2: bestY.at, kind: bestY.kind });
  }
  let dx = dx0, dy = dy0;

  // Equal-spacing guides ("same spacing", asked for directly): only tried on
  // an axis the edge/center snap above didn't already claim, so a card never
  // fights between "line up with this edge" and "match this gap" mid-drag.
  // Scoped to the single nearest neighbour each side, not every possible
  // triple: that is what draw.io and PowerPoint show too, and it keeps this
  // O(n) per drag frame like the alignment pass above it, not O(n^2).
  if (!bestX) {
    const rowMates = others.filter((b) => (!b.only || b.only === "left" || b.only === "right") && b.minY < dragged.bottom && b.maxY > dragged.top);
    const left = rowMates.filter((b) => b.maxX <= dragged.left + tol).sort((a, b) => b.maxX - a.maxX)[0];
    const right = rowMates.filter((b) => b.minX >= dragged.right - tol).sort((a, b) => a.minX - b.minX)[0];
    if (left && right) {
      const gapLeft = dragged.left - left.maxX, gapRight = right.minX - dragged.right;
      if (gapLeft >= 0 && gapRight >= 0 && Math.abs(gapLeft - gapRight) <= tol) {
        const avgGap = (gapLeft + gapRight) / 2;
        dx = left.maxX + avgGap - dragged.left;
        const midY = (Math.max(left.minY, dragged.top) + Math.min(left.maxY, dragged.bottom)) / 2;
        guideLines.push({ x1: left.maxX, y1: midY, x2: dragged.left + dx, y2: midY, kind: "spacing" });
        guideLines.push({ x1: dragged.right + dx, y1: midY, x2: right.minX, y2: midY, kind: "spacing" });
      }
    }
    //: **Continue a row's spacing** (Figma and draw.io): with nothing on the
    //: other side, the gap to the nearest item matches the gap that item
    //: keeps to its own neighbour, so the third box of a row lands where the
    //: first two set the rhythm.
    if (!guideLines.some((l) => l.kind === "spacing" && l.y1 === l.y2)) {
      const series = wbSpacingSeries(rowMates, dragged, "x", tol);
      if (series) {
        dx = series.delta;
        guideLines.push(...series.lines);
      }
    }
  }
  if (!bestY) {
    const colMates = others.filter((b) => (!b.only || b.only === "top" || b.only === "bottom") && b.minX < dragged.right && b.maxX > dragged.left);
    const above = colMates.filter((b) => b.maxY <= dragged.top + tol).sort((a, b) => b.maxY - a.maxY)[0];
    const below = colMates.filter((b) => b.minY >= dragged.bottom - tol).sort((a, b) => a.minY - b.minY)[0];
    if (above && below) {
      const gapAbove = dragged.top - above.maxY, gapBelow = below.minY - dragged.bottom;
      if (gapAbove >= 0 && gapBelow >= 0 && Math.abs(gapAbove - gapBelow) <= tol) {
        const avgGap = (gapAbove + gapBelow) / 2;
        dy = above.maxY + avgGap - dragged.top;
        const midX = (Math.max(above.minX, dragged.left) + Math.min(above.maxX, dragged.right)) / 2;
        guideLines.push({ x1: midX, y1: above.maxY, x2: midX, y2: dragged.top + dy, kind: "spacing" });
        guideLines.push({ x1: midX, y1: dragged.bottom + dy, x2: midX, y2: below.minY, kind: "spacing" });
      }
    }
    if (!guideLines.some((l) => l.kind === "spacing" && l.x1 === l.x2)) {
      const series = wbSpacingSeries(colMates, dragged, "y", tol);
      if (series) {
        dy = series.delta;
        guideLines.push(...series.lines);
      }
    }
  }

  return { dx, dy, guideLines };
}

//: A row (`axis` "x") or column ("y") of boxes beside the dragged one: if the
//: gap from it to its nearest neighbour on one side is within snapping of the
//: gap that neighbour keeps to the next one out, the move that makes the two
//: equal and the two spacing marks. Pure (node-tested).
function wbSpacingSeries(mates, dragged, axis, tol = WB_ALIGN_SNAP_PX) {
  const lo = axis === "x" ? "minX" : "minY", hi = axis === "x" ? "maxX" : "maxY";
  const dLo = axis === "x" ? dragged.left : dragged.top, dHi = axis === "x" ? dragged.right : dragged.bottom;
  const cross = (b) => (axis === "x"
    ? (Math.max(b.minY, dragged.top) + Math.min(b.maxY, dragged.bottom)) / 2
    : (Math.max(b.minX, dragged.left) + Math.min(b.maxX, dragged.right)) / 2);
  const mark = (a, b, at) => (axis === "x"
    ? { x1: a, y1: at, x2: b, y2: at, kind: "spacing" }
    : { x1: at, y1: a, x2: at, y2: b, kind: "spacing" });
  let best = null;
  for (const side of [-1, 1]) {
    const near = side < 0
      ? mates.filter((b) => b[hi] <= dLo + tol).sort((a, b) => b[hi] - a[hi])[0]
      : mates.filter((b) => b[lo] >= dHi - tol).sort((a, b) => a[lo] - b[lo])[0];
    if (!near) continue;
    const far = side < 0
      ? mates.filter((b) => b !== near && b[hi] <= near[lo]).sort((a, b) => b[hi] - a[hi])[0]
      : mates.filter((b) => b !== near && b[lo] >= near[hi]).sort((a, b) => a[lo] - b[lo])[0];
    if (!far) continue;
    const gap = side < 0 ? near[lo] - far[hi] : far[lo] - near[hi];
    const mine = side < 0 ? dLo - near[hi] : near[lo] - dHi;
    if (gap < 0 || mine < 0 || Math.abs(mine - gap) > tol) continue;
    const delta = side < 0 ? gap - mine : mine - gap;
    if (best && Math.abs(delta) >= Math.abs(best.delta)) continue;
    const at = cross(near);
    best = {
      delta,
      lines: side < 0
        ? [mark(far[hi], near[lo], at), mark(near[hi], dLo + delta, at)]
        : [mark(dHi + delta, near[lo], at), mark(near[hi], far[lo], at)],
    };
  }
  return best;
}

//: **Guides for an edge being dragged** (INBOX 825 item 2, INBOX 826's E4):
//: a resize, and a shape or box drawn out, snap the moving edge to another
//: item's edge or centre and the moving size to a neighbour's width or
//: height, each shown by a guide line; then the grid when snap is on, and a
//: card's content height (`fit`) for its bottom edge. `box` is {x, y, w, h},
//: `edges` the moving sides ("se", "w"). Pure apart from `wbGuideBoxes`
//: (node-tested in tests/test_wb_resize_guides.py).
function wbResizeGuides(excludeKeys, box, edges, { fit = null, grid = 0, min = 1, tol = WB_ALIGN_SNAP_PX } = {}) {
  const others = wbGuideBoxes(excludeKeys, box);
  const out = { x: box.x, y: box.y, w: box.w, h: box.h, guideLines: [] };
  const axis = (horizontal) => {
    const hi = horizontal ? edges.includes("e") : edges.includes("s");
    const lo = horizontal ? edges.includes("w") : edges.includes("n");
    if (!hi && !lo) return;
    const start = horizontal ? box.x : box.y, size = horizontal ? box.w : box.h;
    const fixed = hi ? start : start + size;
    const moving = hi ? start + size : start;
    const [minK, maxK, cMin, cMax] = horizontal ? ["minX", "maxX", "minY", "maxY"] : ["minY", "maxY", "minX", "maxX"];
    const crossLo = horizontal ? box.y : box.x, crossHi = crossLo + (horizontal ? box.h : box.w);
    let best = null;
    const offer = (target, line) => {
      const delta = target - moving;
      if (Math.abs(delta) > tol || (best && Math.abs(delta) >= Math.abs(best.delta))) return;
      if (Math.abs(target - fixed) < min) return;
      best = { delta, target, line };
    };
    const across = (at, a, b, kind) => (horizontal
      ? { x1: at, y1: a, x2: at, y2: b, kind }
      : { x1: a, y1: at, x2: b, y2: at, kind });
    for (const other of others) {
      const a = Math.min(crossLo, other[cMin]) - 20, b = Math.max(crossHi, other[cMax]) + 20;
      offer(other[minK], across(other[minK], a, b, "edge"));
      offer(other[maxK], across(other[maxK], a, b, "edge"));
      if (other.only) continue; // a frame's margin line: an edge to land on, not a centre or a size
      offer((other[minK] + other[maxK]) / 2, across((other[minK] + other[maxK]) / 2, a, b, "center"));
      const span = other[maxK] - other[minK];
      offer(hi ? fixed + span : fixed - span, [
        { mark: true, at: other[cMin] - 8, from: other[minK], to: other[maxK] },
      ]);
    }
    if (fit && !horizontal && hi) offer(fixed + fit, across(fixed + fit, crossLo - 20, crossHi + 20, "edge"));
    if (!best && grid) {
      const target = Math.round(moving / grid) * grid;
      if (Math.abs(target - fixed) >= min) best = { delta: target - moving, target, line: null };
    }
    if (!best) return;
    const lowEdge = hi ? fixed : best.target, highEdge = hi ? best.target : fixed;
    if (horizontal) { out.x = lowEdge; out.w = highEdge - lowEdge; } else { out.y = lowEdge; out.h = highEdge - lowEdge; }
    //: A size match marks both measures: the neighbour's and the one it set.
    if (Array.isArray(best.line)) {
      const m = best.line[0];
      const mark = (at, from, to, extra) => ({
        ...(horizontal ? { x1: from, y1: at, x2: to, y2: at } : { x1: at, y1: from, x2: at, y2: to }),
        kind: "spacing", ...extra,
      });
      //: Only the item being resized wears the number, and it stands clear of
      //: the grips on its edge (K19); the neighbour's measure is a bare line.
      out.guideLines.push(mark(m.at, m.from, m.to, { label: false }), mark(crossLo - 8, lowEdge, highEdge, { out: true }));
    } else if (best.line) out.guideLines.push(best.line);
  };
  axis(true);
  axis(false);
  return out;
}

//: The size beside what is being drawn or resized ("120 x 80", E4), in the
//: guides' own group so it goes when they do; a constant screen size.
function wbShowSizeReadout(box) {
  const group = document.getElementById("wb-align-guides");
  const container = document.getElementById("whiteboard-container");
  if (!group || !container) return;
  const k = d3.zoomTransform(container).k || 1;
  const words = `${Math.round(box.w)} x ${Math.round(box.h)}`;
  const ns = "http://www.w3.org/2000/svg";
  const g = document.createElementNS(ns, "g");
  g.setAttribute("class", "wb-size-readout");
  g.setAttribute("transform", `translate(${box.x + box.w / 2} ${box.y + box.h}) scale(${1 / k}) translate(0 16)`);
  const width = words.length * 7 + 12;
  const plate = document.createElementNS(ns, "rect");
  plate.setAttribute("x", String(-width / 2));
  plate.setAttribute("y", "-10");
  plate.setAttribute("width", String(width));
  plate.setAttribute("height", "20");
  plate.setAttribute("rx", "4");
  const text = document.createElementNS(ns, "text");
  text.setAttribute("text-anchor", "middle");
  text.setAttribute("dominant-baseline", "central");
  text.textContent = words;
  g.append(plate, text);
  group.appendChild(g);
  wbMeasuring(true);
}

//: While a size or gap badge shows, the arrow grips and the turn handle hide:
//: they sit on the same spots (22 px out, mid-side) and covered the numbers
//: (the owner 2026-10-26: "sizes still get cut off"). Neither works mid-drag.
function wbMeasuring(on) {
  document.getElementById("whiteboard-container")?.classList.toggle("wb-measuring", on);
}

//: One resize frame through the guides: the box the handle has made, snapped
//: (unless `off`), the lines and the size drawn. Returns the new width and
//: height; the caller places x and y from them as before.
function wbGuidedResize(kind, d, handle, start, width, height, { off = false, fit = null } = {}) {
  const box = {
    x: handle.includes("w") ? start.x + start.w - width : start.x,
    y: handle.includes("n") ? start.y + start.h - height : start.y,
    w: width,
    h: height,
  };
  const snapped = off ? { ...box, guideLines: [] } : wbResizeGuides(new Set([wbMultiKey(kind, d.id)]), box, handle, {
    fit, grid: wbSnapOn() ? WB_GRID_SPACING : 0, min: WB_OBJECT_MIN_SIZE, tol: wbAlignTol(),
  });
  wbShowAlignmentGuides(snapped.guideLines);
  wbShowSizeReadout(snapped);
  return { width: snapped.w, height: snapped.h };
}

//: **A box drawn out from a press snaps its moving corner** (E4): the
//: corner under the pointer goes through the edge guides, and the size shows
//: beside it. Every closed shape is drawn corner to corner, the ellipse
//: included (dogfood 2026-10-25 item 7: a circle grown from its centre
//: put its top under the toolbar and felt unlike the rectangle). Alt draws
//: from the centre without snapping (`wbDragBox`); Shift (a square) is left
//: alone.
function wbDrawOutSnap(sx, sy, x, y, event) {
  const dx = x - sx, dy = y - sy;
  const box = { x: Math.min(sx, x), y: Math.min(sy, y), w: Math.abs(dx), h: Math.abs(dy) };
  if (event.shiftKey || event.altKey) {
    //: Shift (a square) and Alt (from the centre, unsnapped) are left to
    //: `wbDragBox`; the readout shows the box it will draw.
    wbShowAlignmentGuides([]);
    wbShowSizeReadout(wbDragBox(sx, sy, x, y, event));
    return [x, y];
  }
  const edges = (dx >= 0 ? "e" : "w") + (dy >= 0 ? "s" : "n");
  const snapped = wbResizeGuides(null, box, edges, {
    grid: wbSnapOn() ? WB_GRID_SPACING : 0, min: 1, tol: wbAlignTol(),
  });
  wbShowAlignmentGuides(snapped.guideLines);
  wbShowSizeReadout(snapped);
  return [edges.includes("e") ? snapped.x + snapped.w : snapped.x, edges.includes("s") ? snapped.y + snapped.h : snapped.y];
}

//: Default guide colours, one per `kind` `wbAlignmentGuides` can report: 
//: "edge" (an outer border lining up with another), "center" (mid-points
//: lining up, the draw.io/PowerPoint convention of a *different* colour so
//: the two are never confused at a glance), and "spacing" (equal gaps).
//: Overridable per the direct ask ("colours should be alterable"); the
//: picker lives in the whiteboard's own shape-menu dropdown rather than a
//: new top menu bar, see HISTORY.md for why that redesign is deferred.
//: The defaults live in CSS (`.wb-align-guide-<kind>`, one ink per theme, so
//: each passes 3:1 on the canvas in light and dark); only a colour the owner
//: picked is written here, and it wins over the class.
function wbAlignGuideColor(kind) {
  return prefs.get(`wb-guide-color-${kind}`, null) || "";
}

//: Draws (or clears) the guide lines `wbAlignmentGuides` found. A "spacing"
//: line also gets its length as a label at a constant screen size (Figma's
//: distance badges), so an equal-gap guide says what the gap is.
const WB_BADGE_CLEAR_PX = 22;
function wbShowAlignmentGuides(lines) {
  //: The overlay layer, above the cards in DOM order: in `#wb-zoom-group` (the base SVG) a guide ran
  //: under every note card it lined up with (owner, 2026-11-10, INBOX 1725). Same pan and zoom.
  const zoomGroup = document.getElementById("wb-overlay-zoom-group") || document.getElementById("wb-zoom-group");
  if (!zoomGroup) return;
  let group = document.getElementById("wb-align-guides");
  if (!group) {
    group = document.createElementNS("http://www.w3.org/2000/svg", "g");
    group.setAttribute("id", "wb-align-guides");
    group.setAttribute("pointer-events", "none");
    zoomGroup.appendChild(group);
  }
  group.replaceChildren();
  wbMeasuring(false);
  if (!lines.length) return;
  const ns = "http://www.w3.org/2000/svg";
  const container = document.getElementById("whiteboard-container");
  const k = (container && d3.zoomTransform(container).k) || 1;
  for (const line of lines) {
    const kind = line.kind || "edge";
    const el = document.createElementNS(ns, "line");
    el.setAttribute("x1", line.x1);
    el.setAttribute("y1", line.y1);
    el.setAttribute("x2", line.x2);
    el.setAttribute("y2", line.y2);
    el.setAttribute("class", `wb-align-guide-line wb-align-guide-${kind}`);
    const picked = wbAlignGuideColor(kind);
    if (picked) el.style.stroke = picked;
    group.appendChild(el);
    if (kind !== "spacing" || line.label === false) continue;
    const length = Math.round(Math.hypot(line.x2 - line.x1, line.y2 - line.y1));
    if (length * k < 22) continue; // a label wider than its gap is noise
    const label = document.createElementNS(ns, "g");
    label.setAttribute("class", "wb-align-guide-label");
    //: A badge on the edge being dragged sits over that edge's own grip (the
    //: "34" under the left handle, K19): it steps off the line, away from the box.
    const clear = line.out ? WB_BADGE_CLEAR_PX / k : 0;
    const bx = (line.x1 + line.x2) / 2 - (line.x1 === line.x2 ? clear : 0);
    const by = (line.y1 + line.y2) / 2 - (line.y1 === line.y2 ? clear : 0);
    label.setAttribute("transform", `translate(${bx} ${by}) scale(${1 / k})`);
    const words = String(length);
    const width = words.length * 7 + 10;
    const plate = document.createElementNS(ns, "rect");
    plate.setAttribute("x", String(-width / 2));
    plate.setAttribute("y", "-9");
    plate.setAttribute("width", String(width));
    plate.setAttribute("height", "18");
    plate.setAttribute("rx", "4");
    if (picked) plate.style.fill = picked;
    const text = document.createElementNS(ns, "text");
    text.setAttribute("text-anchor", "middle");
    text.setAttribute("dominant-baseline", "central");
    text.textContent = words;
    label.append(plate, text);
    group.appendChild(label);
    wbMeasuring(true);
  }
}

function wbClearAlignmentGuides() {
  document.getElementById("wb-align-guides")?.remove();
  wbMeasuring(false);
}

function wbApplyGrid() {
  const el = document.getElementById("whiteboard-container");
  if (!el) return;
  el.dataset.wbGrid = wbGridType();
  wbSyncGridToTransform();
}

//: **A board's look lives on the board** (WHITEBOARD_PLAN decision 24,
//: FEAT-06). It used to be one localStorage colour shared by every board and
//: a per-board localStorage image, so neither synced, neither was in a
//: backup, the desktop window and a browser tab drew different boards, and
//: media cleanup deleted the image as an orphan. Now `background {color,
//: image}` is in the board's settings and arrives with its state
//: (`wbState.background`); grid and snap stay per device.
function wbBoardBackground() {
  return (wbState && wbState.background) || {};
}

//: The theme's own board colour as a hex string, read with no colour of the
//: board's on the container, so "reset" still means the current theme.
function wbThemeBoardHex() {
  const el = document.getElementById("whiteboard-container");
  if (!el) return null;
  const rgb = getComputedStyle(el).backgroundColor;
  const m = rgb.match(/(\d+),\s*(\d+),\s*(\d+)/);
  return m ? "#" + m.slice(1, 4).map((n) => Number(n).toString(16).padStart(2, "0")).join("") : null;
}

function wbApplyBackground() {
  const el = document.getElementById("whiteboard-container");
  if (!el) return;
  const bg = wbBoardBackground();
  el.style.removeProperty("--wb-board-bg");
  const themeHex = bg.color ? null : wbThemeBoardHex();
  if (bg.color) el.style.setProperty("--wb-board-bg", bg.color);
  // `mediaSrc`, not the bare url, a CSS `background-image: url(...)` is a
  // plain resource load, same as `<img src>`, so it never attaches
  // X-Auth-Token either.
  el.style.setProperty("--wb-bg-image", bg.image ? `url("${mediaSrc(bg.image)}")` : "none");
  const picker = document.getElementById("wb-bg-color-picker");
  if (picker && (bg.color || themeHex)) picker.value = bg.color || themeHex;
  //: The board's grid: its spacing and its colour (the theme's own tint when none is set).
  WB_GRID_SPACING = bg.grid_size || 24;
  if (bg.grid_color) el.style.setProperty("--wb-grid-ink", bg.grid_color);
  else el.style.removeProperty("--wb-grid-ink");
  wbSyncGridToTransform();
  wbFmtState.opts?.sync(bg);
  const fold = document.getElementById("wb-sticky-fold");
  if (fold) fold.checked = bg.sticky_fold !== false;
  const rough = document.getElementById("wb-rough-toggle");
  if (rough) rough.checked = bg.rough === true;
  const imageButton = document.getElementById("wb-bg-image");
  if (imageButton) {
    const words = bg.image ? "Remove the background image" : "Set a background image";
    imageButton.title = words;
    imageButton.setAttribute("aria-label", words);
  }
}

//: Writes a patch of the board's look and pushes one undo step for it. The
//: default scratch board has no note to keep settings on, so it says so.
async function wbSetBackground(patch, { undo = true } = {}) {
  const id = window.currentBoardId;
  if (!id) {
    toast("The default board keeps the theme's look. Make a board of your own to give it one.", "info");
    wbApplyBackground();
    return false;
  }
  const before = { ...wbBoardBackground() };
  try {
    const out = await apiJson(`/whiteboard/boards/${id}`, { method: "PUT", body: JSON.stringify({ background: patch }) });
    if (String(window.currentBoardId ?? "") !== String(id)) return false;
    wbState.background = out.background || {};
  } catch (err) {
    toast(err.message || voiceLine("failed", { what: "change the background" }), true);
    wbApplyBackground();
    return false;
  }
  wbApplyBackground();
  //: The sticky notes' fold and the hand-drawn look follow the board's.
  if ("sticky_fold" in patch || "rough" in patch) wbScheduleRender();
  if (undo) wbPushUndo({ action: "background", before });
  return true;
}

//: **Once per board on this device, the old per-browser look moves onto the
//: board.** A board that already has a look of its own is never overwritten.
//: The per-board image key is removed once moved; the old colour was one key
//: for every board, so it stays until each board this device opens has taken
//: it, and a flag per board says which have.
async function wbMigrateBackground() {
  const id = window.currentBoardId;
  if (!id || wbIsMap()) return;
  let image = null, color = null, done = false;
  try {
    image = prefs.get(`wb-bg-image-${id}`, null);
    color = prefs.get("wb-bg-color", null);
    done = prefs.get(`wb-bg-moved-${id}`, null) === "1";
  } catch {
    return;
  }
  if (done || (!image && !color)) return;
  const have = wbBoardBackground();
  const patch = {};
  if (image && !have.image && /^\/media\/[A-Za-z0-9]/.test(image)) patch.image = image;
  if (color && !have.color && /^#[0-9a-f]{6}$/i.test(color)) patch.color = color;
  if (Object.keys(patch).length && !(await wbSetBackground(patch, { undo: false }))) return;
  try {
    prefs.remove(`wb-bg-image-${id}`);
    prefs.set(`wb-bg-moved-${id}`, "1");
  } catch {
    // Private mode: it is on the board now either way.
  }
}

// A tiny inline SVG baked into a `cursor:` value, so the OS/GPU renders and
// positions it: zero JS on the hot path. This replaces an earlier version
// that tracked the pointer with a `mousemove`-positioned `<div>`: reported
// (and reproduced) as "my mouse keeps snapping to an invisible grid", a
// JS-positioned cursor only moves on however often `mousemove` actually
// fires, which is both slower and less regular than the compositor placing
// a real cursor image, so on a fast swipe the dot visibly lagged and then
// jumped to catch up. A `cursor:` image has no such step: once set, the
// browser draws it exactly like the system arrow.
function wbCursorUrl(inner, { size = 26, hx = 3, hy = size - 3 } = {}) {
  const svg =
    `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" ` +
    `viewBox="0 0 ${size} ${size}">${inner}</svg>`;
  return `url("data:image/svg+xml,${encodeURIComponent(svg)}") ${hx} ${hy}`;
}

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
//: Takes the pen width rather than reading it: `WB_STROKE_WIDTH` is a `let`
//: inside `initWhiteboard`, not a module constant, so a module-level function
//: that read it threw `WB_STROKE_WIDTH is not defined` on the first stroke
//: (found by the sweep, which drew nothing at all and said so).
function wbHighlighterWidth(penWidth) {
  return highlighterWidth(penWidth);
}

//: **The blend follows the backdrop.** Multiply is worth 20 luminance units a
//: pass on a light board and 3 on a dark one (measured with pngpixel.py on
//: two crossing strokes: 252.9 / 229.6 / 211.5 light, 26.4 / 23.6 / 22.0
//: dark), so on a dark board it is a blend that costs the ink its colour and
//: buys almost nothing. `screen` is the same signal in the direction a dark
//: surface can move. Inline rather than a class because the export clones
//: these nodes into a standalone SVG where a stylesheet does not follow them,
//: which is also why it has to be re-applied when the mode changes: see
//: `wbRefreshHighlighterBlend`.
function wbHighlighterBlend() {
  return highlighterBlend(document.documentElement.dataset.mode === "dark");
}

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
  const drawing = document.querySelector("#wb-overlay-zoom-group > path.wb-live-highlighter");
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

//: The Format panel's shadow (decision 19): one soft drop on a shape, a line,
//: a text box and a picture, and in the export. The offset and blur are the
//: item's own (`shadow_x`, `shadow_y`, `shadow_blur`; wb5), and an item that
//: set none keeps the original 0, 2 and 4.
function wbShadowOf(look) {
  const n = (v, d) => (v === null || v === undefined || v === "" || !Number.isFinite(Number(v)) ? d : Number(v));
  return { x: n(look?.shadow_x, 0), y: n(look?.shadow_y, 2), blur: n(look?.shadow_blur, 4) };
}

//: **Crop a picture to a shape** (`data.crop`; INBOX 1313 row 13). Corner
//: points as shares of the picture's box, so one table draws the board's CSS
//: clip and the export's path at any size. An ellipse is a circle on a square.
const WB_CROPS = {
  ellipse: null,
  diamond: [[0.5, 0], [1, 0.5], [0.5, 1], [0, 0.5]],
  hexagon: [[0.25, 0], [0.75, 0], [1, 0.5], [0.75, 1], [0.25, 1], [0, 0.5]],
  triangle: [[0.5, 0], [1, 1], [0, 1]],
};

//: **A rectangle crop** (`data.trim`, percent of the picture cut from the top, right, bottom and left) shares
//: this clip: the shape (or a plain rectangle) is fitted inside what the trim leaves. With `size` ([w, h]) the
//: answer is the export's SVG path at that size, without it the board's CSS `clip-path`; "" clips nothing.
function wbCropClip(crop, trim, size) {
  const known = Object.prototype.hasOwnProperty.call(WB_CROPS, crop);
  const [top, right, bottom, left] = [0, 1, 2, 3].map((i) => Math.max(0, Math.min(90, Number(trim?.[i]) || 0)) / 100);
  const fits = left + right < 0.95 && top + bottom < 0.95;
  const [x0, y0, x1, y1] = fits ? [left, top, 1 - right, 1 - bottom] : [0, 0, 1, 1];
  if (!known && x0 + y0 + (1 - x1) + (1 - y1) === 0) return "";
  const [w, h] = size || [100, 100];
  const num = (v) => +(v * 100).toFixed(2);
  const points = (known ? WB_CROPS[crop] : [[0, 0], [1, 0], [1, 1], [0, 1]]);
  if (points) {
    const at = points.map(([x, y]) => [x0 + x * (x1 - x0), y0 + y * (y1 - y0)]);
    return size ? `M ${at.map(([x, y]) => `${+(x * w).toFixed(2)} ${+(y * h).toFixed(2)}`).join(" L ")} Z`
      : `polygon(${at.map(([x, y]) => `${num(x)}% ${num(y)}%`).join(", ")})`;
  }
  if (!size) return `ellipse(${num((x1 - x0) / 2)}% ${num((y1 - y0) / 2)}% at ${num((x0 + x1) / 2)}% ${num((y0 + y1) / 2)}%)`;
  const [rx, ry, cy] = [(x1 - x0) * w / 2, (y1 - y0) * h / 2, (y0 + y1) * h / 2];
  return `M ${x0 * w} ${cy} A ${rx} ${ry} 0 1 0 ${x1 * w} ${cy} A ${rx} ${ry} 0 1 0 ${x0 * w} ${cy} Z`;
}

function wbCropPath(crop, w, h, trim) {
  return wbCropClip(crop, trim, [w, h]);
}

//: **Edit image** (WHITEBOARD_PLAN section 1): a picture's quarter turn, flips
//: and filters live in `data` (`turn`, `flip_x`, `flip_y`, `grey`, `bright`,
//: `contrast`) and are drawn over the untouched file, so Undo and "Reset" are
//: exact. The crop, trim and corner clips sit on the picture's own (turned)
//: frame, so they turn with it; a quarter turn swaps that frame's width and height.
//: One function (the shared scope has a name cap): `filter` is the CSS filter, `w`/`h` the picture's own frame,
//: `transform` the CSS one and `svg` the export's.
function wbPixel(data, w, h) {
  const level = (v) => (Number.isInteger(v) && v >= 20 && v <= 200 && v !== 100 ? v / 100 : 0);
  const filter = [data?.grey === true ? "grayscale(1)" : "", level(data?.bright) ? `brightness(${level(data.bright)})` : "",
    level(data?.contrast) ? `contrast(${level(data.contrast)})` : ""].filter(Boolean).join(" ");
  const turn = [90, 180, 270].includes(data?.turn) ? data.turn : 0;
  const quarter = turn === 90 || turn === 270;
  const fx = data?.flip_x === true ? -1 : 1;
  const fy = data?.flip_y === true ? -1 : 1;
  const parts = [];
  if (quarter) parts.push("translate(-50%, -50%)");
  if (fx < 0 || fy < 0) parts.push(`scale(${fx}, ${fy})`);
  if (turn) parts.push(`rotate(${turn}deg)`);
  const [lw, lh] = quarter ? [h, w] : [w, h];
  const plain = !turn && fx > 0 && fy > 0;
  return { w: lw, h: lh, turn, filter, transform: parts.join(" "),
    svg: plain ? "" : `translate(${w / 2} ${h / 2}) scale(${fx} ${fy}) rotate(${turn}) translate(${-lw / 2} ${-lh / 2})` };
}

//: **Voting dots** (Miro's; INBOX 1313 row 14): `data.votes`, how many dots a
//: board item holds, drawn as a pill on its top-right corner. Added and taken
//: off from the Board menu and Ctrl+K, one Undo step each
//: for every selected item; zero is none and is not stored.
const WB_VOTE_MAX = 99;

function wbVotesAfter(current, delta) {
  const next = Math.max(0, Math.min(WB_VOTE_MAX, (Number(current) || 0) + delta));
  return next || undefined;
}

function wbVoteTargets() {
  return wbFmtEntries().filter((e) => e.kind === "object" && !WB_MAP_KINDS.has(e.item.kind) && !wbIsLocked(e.kind, e.item));
}

async function wbSetVotes(entries, change) {
  await wbRecordGesture(async () => {
    for (const e of entries) {
      const votes = change(e.item.data?.votes);
      const data = { ...e.item.data };
      if (votes) data.votes = votes;
      else delete data.votes;
      e.item.data = data;
    }
    await wbSaveMany(entries.map((e) => ({ kind: "object", item: e.item })));
  });
  wbScheduleRender();
}

async function wbVoteSelection(delta) {
  const targets = wbVoteTargets();
  if (!targets.length) {
    toast("Select a note, text box, picture or frame to vote on.");
    return;
  }
  await wbSetVotes(targets, (n) => wbVotesAfter(n, delta));
  const total = targets.reduce((sum, e) => sum + (e.item.data?.votes || 0), 0);
  wbAnnounce(delta > 0 ? `Dot added: ${nounCount(total, "dot")} on the selection.` : `Dot taken off: ${nounCount(total, "dot")} on the selection.`);
}

async function wbClearVotes() {
  const held = (wbState.objects || []).filter((o) => !WB_MAP_KINDS.has(o.kind) && o.data?.votes && !wbIsLocked("object", o));
  if (!held.length) {
    toast("No item on this board has a vote dot.");
    return;
  }
  await wbSetVotes(held.map((item) => ({ kind: "object", item })), () => undefined);
  wbAnnounce(`Dots cleared from ${nounCount(held.length, "item")}.`);
}

//: The dots in an export: the same pill, at the corner the board draws it,
//: in the colours the live badge shows.
function wbSvgVotes(obj) {
  const badge = document.querySelector(`#wb-html-layer .wb-object[data-id="${obj.id}"] > .wb-votes`);
  const fill = badge ? wbExportColour(getComputedStyle(badge).backgroundColor) : "#2f5bd3";
  const ink = badge ? wbExportColour(getComputedStyle(badge).color) : "#ffffff";
  const w = Math.max(16, 8 + String(obj.data.votes).length * 7);
  return `<rect x="${obj.width - w + 8}" y="-8" width="${w}" height="16" rx="8" fill="${fill}" />` +
    `<text x="${obj.width - w / 2 + 8}" y="0" font-size="11" font-weight="700" text-anchor="middle" dominant-baseline="central" fill="${ink}">${obj.data.votes}</text>`;
}

function wbPaintVotes(el, d) {
  wbMapLazy.paintStamps(el, d);
  const n = d.data?.votes || 0;
  let badge = el.querySelector(":scope > .wb-votes");
  if (!n) {
    badge?.remove();
    return;
  }
  if (!badge) {
    badge = document.createElement("span");
    badge.className = "wb-votes";
    badge.setAttribute("role", "img");
    el.appendChild(badge);
  }
  badge.textContent = String(n);
  badge.setAttribute("aria-label", n === 1 ? "1 vote" : `${n} votes`);
}

//: **A workshop timer**: a countdown pill at the board's top, from the Board
//: menu's Workshop group. Kept in the page only (a workshop is now, not a
//: property of the board), read against the clock rather than counted, so a
//: backgrounded tab is still right. One timeout at a time, aimed at the next
//: change of the shown second, and none once it ends or is stopped.
const wbTimer = { end: 0, tick: 0, bar: null, time: null };

function wbTimerLeft(end, now) {
  return Math.max(0, end - now);
}

function wbTimerText(ms) {
  const seconds = Math.ceil(Math.max(0, ms) / 1000);
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}

function wbTimerBar() {
  if (wbTimer.bar?.isConnected) return wbTimer.bar;
  const host = document.getElementById("wb-present-bar")?.parentElement;
  if (!host) return null;
  const bar = document.createElement("div");
  bar.id = "wb-timer-bar";
  bar.className = "whiteboard-floating-panel wb-timer-bar card glass hidden";
  bar.setAttribute("role", "timer");
  bar.setAttribute("aria-label", "Workshop timer");
  const glyph = document.createElement("i");
  glyph.className = "ph ph-timer";
  glyph.setAttribute("aria-hidden", "true");
  const time = document.createElement("span");
  time.className = "wb-timer-time";
  const stop = document.createElement("button");
  stop.type = "button";
  stop.className = "ghost small icon-only";
  stop.title = "Stop the timer";
  stop.setAttribute("aria-label", "Stop the timer");
  const x = document.createElement("i");
  x.className = "ph ph-x";
  x.setAttribute("aria-hidden", "true");
  stop.appendChild(x);
  stop.addEventListener("click", () => wbTimerStop());
  bar.append(glyph, time, stop);
  host.appendChild(bar);
  Object.assign(wbTimer, { bar, time });
  return bar;
}

function wbTimerStart(minutes) {
  wbTimerStop(true);
  const bar = wbTimerBar();
  if (!bar) return;
  wbTimer.end = Date.now() + minutes * 60000;
  bar.classList.remove("hidden", "wb-timer-done");
  wbTimerPaint();
  wbAnnounce(`Timer started: ${nounCount(minutes, "minute")}.`);
}

function wbTimerPaint() {
  const left = wbTimerLeft(wbTimer.end, Date.now());
  wbTimer.time.textContent = wbTimerText(left);
  //: Just under the board's top bar wherever it wraps to (measured: the
  //: bar's two rows at a phone's width), read once a second, never on a frame.
  const top = document.getElementById("wb-topbar")?.getBoundingClientRect().bottom;
  const box = wbTimer.bar.offsetParent?.getBoundingClientRect();
  if (top != null && box) wbTimer.bar.style.top = `${Math.round(top - box.top + 8)}px`;
  if (left > 0) {
    clearTimeout(wbTimer.tick);
    wbTimer.tick = setTimeout(wbTimerPaint, (left % 1000 || 1000) + 5);
    return;
  }
  wbTimer.tick = 0;
  wbTimer.bar.classList.add("wb-timer-done");
  toast("Time is up.");
  wbAnnounce("Time is up.");
}

function wbTimerStop(quiet) {
  clearTimeout(wbTimer.tick);
  wbTimer.tick = 0;
  wbTimer.bar?.classList.add("hidden");
  wbTimer.bar?.classList.remove("wb-timer-done");
  if (!quiet) wbAnnounce("Timer stopped.");
}

function wbOpenTimerMenu() {
  const items = [1, 3, 5, 10, 15, 30].map((m) => makeMenuItem(`ph:timer ${nounCount(m, "minute")}`, `Count down ${nounCount(m, "minute")} on the board`, () => wbTimerStart(m)));
  if (wbTimer.bar && !wbTimer.bar.classList.contains("hidden")) items.push(makeMenuItem("ph:x Stop the timer", "Take the timer off the board", () => wbTimerStop()));
  const at = document.getElementById("whiteboard-container")?.getBoundingClientRect();
  openMenuAtPoint(items, "Workshop timer", at ? at.left + at.width / 2 - 80 : 120, at ? at.top + 64 : 120);
}

function wbShadowCss(look) {
  if (!look?.shadow) return null;
  const { x, y, blur } = wbShadowOf(look);
  return `drop-shadow(${x}px ${y}px ${blur}px rgb(0 0 0 / 0.28))`;
}

//: The same shadow as an SVG filter for the exported picture: defined once in
//: `parts` under an id that names its numbers, and the attribute that uses it.
//: A blur is a standard deviation of half its pixels, as in CSS.
function wbExportShadow(parts, look) {
  const { x, y, blur } = wbShadowOf(look);
  const id = `wb-export-shadow-${x}_${y}_${blur}`;
  const def = `<defs><filter id="${id}" x="-30%" y="-30%" width="160%" height="160%">` +
    `<feDropShadow dx="${x}" dy="${y}" stdDeviation="${blur / 2}" flood-color="#000" flood-opacity="0.28"/></filter></defs>`;
  if (!parts.includes(def)) parts.push(def);
  return ` filter="url(#${id})"`;
}

//: SVG `stroke-dasharray` for each style, scaled to the actual stroke width
//: so a thick dashed line doesn't look like a row of dots. `null` (solid)
//: means "don't set the attribute at all", not "set it to empty".
//: A custom `pattern` (draw.io's "8 4": dash, gap, dash... in line widths,
//: `wbDashPatternOf`) wins over the named style.
function wbDashArray(style, width, pattern = null) {
  if (pattern) return pattern.map((n) => Math.round(n * width * 100) / 100).join(" ");
  if (style === "dashed") return `${width * 3} ${width * 2}`;
  if (style === "dotted") return `${width} ${width * 1.6}`;
  return null;
}

//: **Flow** (draw.io's flowAnimation, `data.flow`): the dashes march along
//: the line, one loop per dash pattern so it never jumps. A Web Animation on
//: the path, not a stylesheet rule, because the loop's length is the
//: element's own and the sheets declare no per-element token for it. Kept on
//: the element and replaced only when the period changes, so a render does not
//: restart it; held still under the OS hint and both of the app's switches.
//: The export clones the attributes, so it draws the dashes still.
function wbSetFlowAnimation(path, period) {
  if (!path) return;
  const root = document.documentElement;
  const still = reducedMotionWanted() || root.dataset.uiMotion === "off";
  const want = period > 0 && !still && typeof path.animate === "function" ? period : 0;
  if (path.__wbFlowPeriod === want) return;
  path.__wbFlowAnim?.cancel();
  path.__wbFlowAnim = null;
  path.__wbFlowPeriod = want;
  if (want) {
    path.__wbFlowAnim = path.animate(
      [{ strokeDashoffset: "0px" }, { strokeDashoffset: `${-want}px` }],
      { duration: 800, iterations: Infinity, easing: "linear" },
    );
  }
}

//: A typed dash pattern as numbers, or null when it is not one: one to six
//: positive numbers of at most 200, split by spaces or commas.
function wbDashPatternOf(text) {
  const parts = String(text ?? "").split(/[\s,]+/).filter(Boolean);
  if (!parts.length || parts.length > 6) return null;
  const numbers = parts.map(Number);
  return numbers.every((n) => Number.isFinite(n) && n > 0 && n <= 200) ? numbers : null;
}

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

//: Two head-stroke subpaths meeting at `(tipX, tipY)`, angled back from
//: `approachAngle` (the direction the shaft arrives *from*, in radians), 
//: factored out so both ends of an arrow can draw one (`currentArrowEndStyle`,
//: reported directly: "can't change arrow heads").
//: The box a shape tool draws from the press `(sx, sy)` to the pointer: corner
//: to corner; Shift makes it square, grown towards the pointer so a drag up
//: and left still ends under it (it straddled the press, INBOX 1352 gap 1);
//: Alt draws it from its centre, as Alt resizes from the centre (decision
//: 40). One model for every closed shape, the ellipse included.
function wbDragBox(sx, sy, x, y, mods = {}) {
  let dx = x - sx, dy = y - sy;
  if (mods.shiftKey) {
    const side = Math.max(Math.abs(dx), Math.abs(dy));
    dx = Math.sign(dx || 1) * side;
    dy = Math.sign(dy || 1) * side;
  }
  const w = Math.abs(dx), h = Math.abs(dy);
  if (mods.altKey) return { x: sx - w, y: sy - h, w: 2 * w, h: 2 * h };
  return { x: Math.min(sx, sx + dx), y: Math.min(sy, sy + dy), w, h };
}

//: The ellipse in the box `wbDragBox` gives the same drag (dogfood
//: 2026-10-25 item 7: it used to centre on the press by default).
function wbEllipseDrawD(sx, sy, x, y, mods = {}) {
  const { x: left, y: top, w, h } = wbDragBox(sx, sy, x, y, mods);
  const rx = w / 2, ry = h / 2;
  return `M ${left} ${top + ry} a ${rx} ${ry} 0 1 0 ${w} 0 a ${rx} ${ry} 0 1 0 ${-w} 0`;
}

//: Shift snaps a line's far end to the nearest 45 degrees, keeping its
//: length (INBOX 1352 gap 3).
function wbSnap45(sx, sy, x, y) {
  const step = Math.PI / 4;
  const angle = Math.round(Math.atan2(y - sy, x - sx) / step) * step;
  const d = Math.hypot(x - sx, y - sy);
  return [sx + Math.round(Math.cos(angle) * d * 100) / 100, sy + Math.round(Math.sin(angle) * d * 100) / 100];
}

//: A closed shape's path in its drawn box. Plain `L` commands for the
//: triangle and diamond, as the pen and line tools use, so
//: wbTransformPathD and wbPathBBox have no new command to learn.
function wbClosedShapeD(tool, { x, y, w, h }) {
  if (tool === "rect") return `M ${x} ${y} h ${w} v ${h} h ${-w} Z`;
  if (tool === "triangle") return `M ${x + w / 2} ${y} L ${x + w} ${y + h} L ${x} ${y + h} Z`;
  if (tool === "diamond") return `M ${x + w / 2} ${y} L ${x + w} ${y + h / 2} L ${x + w / 2} ${y + h} L ${x} ${y + h / 2} Z`;
  const more = WB_MORE_SHAPES[tool];
  return more ? more.d(x, y, Math.max(w, 1), Math.max(h, 1)) : "";
}

function wbArrowHeadPath(tipX, tipY, approachAngle, headLen) {
  const h1x = tipX - headLen * Math.cos(approachAngle - Math.PI / 6);
  const h1y = tipY - headLen * Math.sin(approachAngle - Math.PI / 6);
  const h2x = tipX - headLen * Math.cos(approachAngle + Math.PI / 6);
  const h2y = tipY - headLen * Math.sin(approachAngle + Math.PI / 6);
  return `M ${tipX} ${tipY} L ${h1x} ${h1y} M ${tipX} ${tipY} L ${h2x} ${h2y}`;
}

//: Every cap kind a line/arrow/link end can wear, asked for directly ("a
//: full line/arrow end-cap system... circle/square/multi-line ends,
//: independently per end"), the shared arrowhead control only ever grew
//: from Arrow-only to Line-and-Arrow, still one shape. Each is its own
//: closed subpath appended to the shaft's own `d`, same convention
//: `wbArrowHeadPath` already established (a stroked path, no separate SVG
//: element, so hit-testing/move/resize/export keep treating the whole
//: sketch as the one path they already know how to handle), "arrow" here
//: is exactly `wbArrowHeadPath`'s own two-line V, kept for a single call
//: site to switch on.
//: **The plain ends, drawn closed or open** (INBOX 792, the owner: "there is
//: only one actual arrow option for the links"): `arrow` is the open V,
//: `triangle` the solid arrowhead, `diamond` and `diamond-filled` the UML
//: aggregation and composition marks, `bar` a stop line at the tip. A filled
//: end is a closed outline with smaller copies of itself inside it, a stroke's
//: width apart: the end stays one more subpath of the shaft's own `d`, so a
//: line with a solid head is still one stroked path (hit-testing, move,
//: resize and every export read it as before) and no end needs a fill.
//: `triangle-open` (UML's inheritance mark) and `circle-filled` were added for
//: the owner's "more arrow options" (2026-10-11): the hollow triangle stops the
//: shaft at its base like the other hollow ends; the filled circle is rings
//: stepping in by a stroke width, the solid ends' own trick.
//: The plan's decision E2 (WHITEBOARD_PLAN, INBOX 826) added `stealth` (the
//: concave arrow), `cross`, `half-arrow` and `double-arrow`; its "dot" is the
//: filled circle already here. E3 added `memorymap`, the signature end.
const WB_CAP_KINDS = ["none", "memorymap", "arrow", "triangle", "triangle-open", "stealth", "diamond", "diamond-filled", "bar", "circle", "circle-filled", "square", "multiline", "cross", "half-arrow", "double-arrow", "er-one", "er-one-only", "er-zero-one", "er-many", "er-one-many", "er-zero-many"];
const WB_SOLID_CAPS = new Set(["triangle", "diamond-filled"]);

//: **An end's size** (decision E2): small, medium or large, beside each end
//: menu, stored per end as `startCapSize`/`endCapSize` ("s" or "l"; absent
//: is medium, so every saved line keeps its look). It scales the end's
//: length, never the stroke the solid ends step in by.
const WB_CAP_SIZE_SCALE = { s: 0.7, l: 1.45 };
function wbCapScale(size) {
  return WB_CAP_SIZE_SCALE[size] || 1;
}
//: The stored fields for caps read by `wbLinkCaps`/`wbSketchCaps`: medium
//: (or anything unknown) clears the field.
function wbCapSizeFields(caps) {
  const keep = (v) => (WB_CAP_SIZE_SCALE[v] ? v : undefined);
  return { startCapSize: keep(caps.startSize), endCapSize: keep(caps.endSize) };
}

//: The entity-relationship ends (the features audit W4): what is nearest the
//: line's body, then what is at the tip. `null` near: one mark only.
const WB_ER_CAPS = {
  "er-one": [null, "one"],
  "er-one-only": ["one", "one"],
  "er-zero-one": ["zero", "one"],
  "er-many": [null, "many"],
  "er-one-many": ["one", "many"],
  "er-zero-many": ["zero", "many"],
};

//: **A hollow end stops the shaft at its own edge.** An outline diamond,
//: circle or square drew the shaft on through its middle to the tip (the
//: owner: the shaft shows through the shape). How far back from the tip the
//: shape reaches along the line is the inset: the diamond's rear point, the
//: circle's and the square's diameter. Solid ends and open marks need none.
const WB_HOLLOW_INSET = { diamond: (h) => h * 1.1, "triangle-open": (h) => h, circle: (h) => (h * 2) / 3, square: (h) => (h * 2) / 2.6 };
function wbHollowInset(kind, headLen) {
  return WB_HOLLOW_INSET[kind]?.(headLen) || 0;
}

//: `pt` moved toward `toward` by the cap's inset (never past 90% of the way, so
//: a short segment keeps a stub), or `pt` itself under any other cap.
function wbShaftEnd(pt, toward, cap, headLen, size) {
  const inset = wbHollowInset(cap, headLen * wbCapScale(size));
  const dist = Math.hypot(toward.x - pt.x, toward.y - pt.y);
  if (!inset || !dist) return pt;
  const share = Math.min(inset, dist * 0.9) / dist;
  return { x: pt.x + (toward.x - pt.x) * share, y: pt.y + (toward.y - pt.y) * share };
}

function wbCapPath(kind, tipX, tipY, approachAngle, headLen, size) {
  if (!kind || kind === "none") return "";
  //: The solid ends step in by the line's own width, read before the size
  //: scales the length (the head is `width * 4 + 6` long at medium).
  const stroke = Math.max(1, (headLen - 6) / 4);
  headLen *= wbCapScale(size);
  if (kind === "arrow") return wbArrowHeadPath(tipX, tipY, approachAngle, headLen);
  const extra = wbCapPathMore(kind, tipX, tipY, approachAngle, headLen, stroke);
  if (extra !== null) return extra;
  // The entity-relationship ends (the features audit W4, draw.io's ER set):
  // a bar for "one", a ring for "zero" and the crow's foot for "many", read
  // from the shape outward, so "zero-many" is a ring nearest the line's body
  // and the foot at the tip. Each part is drawn back from the tip by a fixed
  // share of the head length, so the marks keep apart at every line width.
  if (WB_ER_CAPS[kind]) {
    const cos = Math.cos(approachAngle), sin = Math.sin(approachAngle);
    const perpX = -sin, perpY = cos;
    const half = headLen * 0.45;
    const at = (back) => ({ x: tipX - cos * back, y: tipY - sin * back });
    const bar = (back) => {
      const p = at(back);
      return `M ${p.x - perpX * half} ${p.y - perpY * half} L ${p.x + perpX * half} ${p.y + perpY * half}`;
    };
    const ring = (back) => {
      const r = headLen * 0.22, p = at(back + r);
      return `M ${p.x - r} ${p.y} A ${r} ${r} 0 1 0 ${p.x + r} ${p.y} A ${r} ${r} 0 1 0 ${p.x - r} ${p.y} Z`;
    };
    const foot = () => {
      const root = at(headLen * 0.7);
      return `M ${root.x} ${root.y} L ${tipX + perpX * half} ${tipY + perpY * half} M ${root.x} ${root.y} L ${tipX - perpX * half} ${tipY - perpY * half}`;
    };
    const [near, far] = WB_ER_CAPS[kind];
    const tip = far === "many" ? foot() : bar(headLen * 0.3);
    const inner = near === "zero" ? ring(headLen * 0.85) : bar(headLen * 0.85);
    return near ? `${inner} ${tip}` : tip;
  }
  if (kind === "bar") {
    const cos = Math.cos(approachAngle), sin = Math.sin(approachAngle);
    const half = headLen * 0.5;
    return `M ${tipX - sin * half} ${tipY + cos * half} L ${tipX + sin * half} ${tipY - cos * half}`;
  }
  if (kind === "triangle" || kind === "triangle-open" || kind === "diamond" || kind === "diamond-filled") {
    const cos = Math.cos(approachAngle), sin = Math.sin(approachAngle);
    //: Points in the line's own frame: along (back from the tip) and across.
    const shape = kind === "triangle" || kind === "triangle-open"
      ? [[0, 0], [headLen, headLen * 0.4], [headLen, -headLen * 0.4]]
      : [[0, 0], [headLen * 0.55, headLen * 0.34], [headLen * 1.1, 0], [headLen * 0.55, -headLen * 0.34]];
    const mid = [shape.reduce((n, p) => n + p[0], 0) / shape.length, 0];
    const draw = (scale) => {
      const pts = shape.map(([back, across]) => {
        const b = mid[0] + (back - mid[0]) * scale, a = across * scale;
        return `${+(tipX - cos * b - sin * a).toFixed(2)} ${+(tipY - sin * b + cos * a).toFixed(2)}`;
      });
      return `M ${pts.join(" L ")} Z`;
    };
    if (!WB_SOLID_CAPS.has(kind)) return draw(1);
    //: The copies step in by a stroke width, until one would be thinner than
    //: the stroke itself.
    const reach = Math.min(...shape.map(([back, across]) => Math.hypot(back - mid[0], across))) || headLen / 2;
    const step = (stroke * 0.8) / reach;
    const out = [];
    for (let scale = 1; scale > step * 0.5; scale -= step) out.push(draw(scale));
    return out.join(" ");
  }
  if (kind === "circle" || kind === "circle-filled") {
    const r = headLen / 3;
    // Centred a radius back from the tip along the shaft, so the circle
    // sits *at* the end rather than half hanging past it.
    const cx = tipX - r * Math.cos(approachAngle), cy = tipY - r * Math.sin(approachAngle);
    const ring = (q) => `M ${+(cx - q).toFixed(2)} ${+cy.toFixed(2)} A ${+q.toFixed(2)} ${+q.toFixed(2)} 0 1 0 ${+(cx + q).toFixed(2)} ${+cy.toFixed(2)} A ${+q.toFixed(2)} ${+q.toFixed(2)} 0 1 0 ${+(cx - q).toFixed(2)} ${+cy.toFixed(2)} Z`;
    if (kind === "circle") return `M ${cx - r} ${cy} A ${r} ${r} 0 1 0 ${cx + r} ${cy} A ${r} ${r} 0 1 0 ${cx - r} ${cy} Z`;
    //: Filled: rings a stroke's width apart down to the centre.
    const step = Math.max(0.8, stroke * 0.8);
    const out = [];
    for (let q = r; q > step * 0.25; q -= step) out.push(ring(q));
    return out.join(" ");
  }
  if (kind === "square") {
    const s = headLen / 2.6;
    const cx = tipX - s * Math.cos(approachAngle), cy = tipY - s * Math.sin(approachAngle);
    const cos = Math.cos(approachAngle), sin = Math.sin(approachAngle);
    const corner = (dx, dy) => `${cx + dx * cos - dy * sin} ${cy + dx * sin + dy * cos}`;
    return `M ${corner(-s, -s)} L ${corner(s, -s)} L ${corner(s, s)} L ${corner(-s, s)} Z`;
  }
  // "multiline": two short perpendicular ticks near the tip, the
  // ER-diagram "many" mark, and a visually distinct third option from a
  // filled dot or square rather than a second arrow variant.
  const cos = Math.cos(approachAngle), sin = Math.sin(approachAngle);
  const perpX = -sin, perpY = cos;
  const half = headLen * 0.4;
  const tick = (back) => {
    const bx = tipX - cos * back, by = tipY - sin * back;
    return `M ${bx - perpX * half} ${by - perpY * half} L ${bx + perpX * half} ${by + perpY * half}`;
  };
  return `${tick(headLen * 0.35)} ${tick(headLen * 0.75)}`;
}

//: The two end-size menus show the selection's sizes, and sit dimmed beside
//: an end with no mark (a size there would change nothing).
function wbShowCapSizes(caps) {
  for (const which of ["start", "end"]) {
    const el = document.getElementById(`wb-prop-${which}size`);
    if (!el) continue;
    el.value = caps[`${which}Size`] || "m";
    const none = caps[`${which}Cap`] === "none";
    el.disabled = none;
    //: **No size for an end with no mark** (the 22-10 bug doc, the bar "too
    //: long and wide"): a greyed "Medium" beside "None" said nothing and was
    //: two of the line bar's widest controls. The size comes back with a mark.
    (el.closest(".select-shell") || el).classList.toggle("hidden", none);
  }
}

//: A filled triangle as copies of itself scaled about its centroid, a
//: stroke's width apart (the solid ends' trick), until the next copy would be
//: thinner than the stroke. `pts` are [x, y] board points.
function wbFilledTriangle(pts, stroke) {
  const cx = (pts[0][0] + pts[1][0] + pts[2][0]) / 3, cy = (pts[0][1] + pts[1][1] + pts[2][1]) / 3;
  const side = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1]);
  const area = Math.abs((pts[1][0] - pts[0][0]) * (pts[2][1] - pts[0][1]) - (pts[2][0] - pts[0][0]) * (pts[1][1] - pts[0][1])) / 2;
  const inradius = (2 * area) / (side(pts[0], pts[1]) + side(pts[1], pts[2]) + side(pts[2], pts[0]) || 1);
  //: At most half a step, so a slim triangle still gets a middle copy.
  const step = Math.min(0.5, (stroke * 0.8) / (inradius || 1));
  const out = [];
  for (let scale = 1; scale > 0 && (out.length === 0 || scale > step * 0.5); scale -= step) {
    out.push("M " + pts.map(([x, y]) => `${+(cx + (x - cx) * scale).toFixed(2)} ${+(cy + (y - cy) * scale).toFixed(2)}`).join(" L ") + " Z");
  }
  return out.join(" ");
}

//: The ends decisions E2 and E3 added, or null for any other kind. Each is
//: drawn in the line's own frame: `at(back, across)` is a point `back` from
//: the tip along the line and `across` to its side.
function wbCapPathMore(kind, tipX, tipY, approachAngle, headLen, stroke) {
  const cos = Math.cos(approachAngle), sin = Math.sin(approachAngle);
  const at = (back, across) => [+(tipX - cos * back - sin * across).toFixed(2), +(tipY - sin * back + cos * across).toFixed(2)];
  const line = (a, b) => `M ${a[0]} ${a[1]} L ${b[0]} ${b[1]}`;
  const L = headLen;
  if (kind === "stealth") {
    //: The concave arrow: two filled halves meeting at the notch.
    const tip = at(0, 0), notch = at(L * 0.62, 0);
    return `${wbFilledTriangle([tip, at(L, L * 0.42), notch], stroke)} ${wbFilledTriangle([tip, notch, at(L, -L * 0.42)], stroke)}`;
  }
  if (kind === "cross") {
    const c = L * 0.45, h = L * 0.3;
    return `${line(at(c - h, -h), at(c + h, h))} ${line(at(c - h, h), at(c + h, -h))}`;
  }
  if (kind === "half-arrow") {
    return line(at(0, 0), at(L * Math.cos(Math.PI / 6), -L * Math.sin(Math.PI / 6)));
  }
  if (kind === "double-arrow") {
    const v = (back) => `${line(at(back, 0), at(back + L * 0.82, L * 0.44))} ${line(at(back, 0), at(back + L * 0.82, -L * 0.44))}`;
    return `${v(0)} ${v(L * 0.5)}`;
  }
  if (kind === "memorymap") {
    //: **The signature end** (decision E3): the brand mark's node, a dot at
    //: the end of a spoke a quarter its length across (favicon.svg: r 7.5 on
    //: a 30-unit spoke), sitting at the tip, with an open chevron behind it
    //: whose arms are the mark's spokes. Candidate A of three (C3).
    const r = L * 0.25;
    const centre = at(r, 0);
    const out = [];
    for (let q = r; q > Math.max(0.8, stroke * 0.8) * 0.25; q -= Math.max(0.8, stroke * 0.8)) {
      out.push(`M ${+(centre[0] - q).toFixed(2)} ${centre[1]} A ${+q.toFixed(2)} ${+q.toFixed(2)} 0 1 0 ${+(centre[0] + q).toFixed(2)} ${centre[1]} A ${+q.toFixed(2)} ${+q.toFixed(2)} 0 1 0 ${+(centre[0] - q).toFixed(2)} ${centre[1]} Z`);
    }
    const gap = r * 2 + stroke;
    out.push(`${line(at(gap, 0), at(gap + L * 0.8, L * 0.46))} ${line(at(gap, 0), at(gap + L * 0.8, -L * 0.46))}`);
    return out.join(" ");
  }
  return null;
}

function wbCursorForTool(tool, strokeColor, strokeWidth) {
  const color = /^#[0-9a-fA-F]{3,8}$/.test(strokeColor || "") ? strokeColor : "#ffffff";
  if (WB_BRUSH_TOOLS.has(tool)) {
    // A crosshair with a dot in the actual stroke colour at its centre, a
    // plain crosshair can't say what colour is about to land. The dot's own
    // radius now tracks the stroke-width slider too (asked for directly:
    // "the size should be represented on the cursor tip"), clamped to what
    // a 32x32 cursor image can actually show and still stay a browser-legal
    // cursor size cross-platform (Safari caps well below Chrome/Firefox).
    const size = 32, c = size / 2;
    const r = Math.max(3, Math.min(13, Math.round((Number(strokeWidth) || 3) / 2) + 2));
    const inner =
      `<line x1="${c}" y1="1" x2="${c}" y2="${c - r - 2}" stroke="#000" stroke-opacity=".55" stroke-width="1.5"/>` +
      `<line x1="${c}" y1="${c + r + 2}" x2="${c}" y2="${size - 1}" stroke="#000" stroke-opacity=".55" stroke-width="1.5"/>` +
      `<line x1="1" y1="${c}" x2="${c - r - 2}" y2="${c}" stroke="#000" stroke-opacity=".55" stroke-width="1.5"/>` +
      `<line x1="${c + r + 2}" y1="${c}" x2="${size - 1}" y2="${c}" stroke="#000" stroke-opacity=".55" stroke-width="1.5"/>` +
      `<circle cx="${c}" cy="${c}" r="${r}" fill="${color}" stroke="#000" stroke-opacity=".45"/>`;
    return `${wbCursorUrl(inner, { size, hx: c, hy: c })}, crosshair`;
  }
  if (tool === "eraser") {
    const inner =
      `<g transform="rotate(-30 13 13)">` +
      `<rect x="4" y="9" width="16" height="10" rx="2" fill="#f4d9d9" stroke="#8a4a4a" stroke-width="1.5"/>` +
      `<rect x="4" y="9" width="7" height="10" rx="2" fill="#e7bcbc"/>` +
      `</g>`;
    return `${wbCursorUrl(inner, { hx: 6, hy: 20 })}, cell`;
  }
  if (tool === "delete") {
    const inner =
      `<path d="M6 7h14M11 7V4h4v3M9 7l1 15h6l1-15" fill="none" stroke="#d9534f" ` +
      `stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>`;
    return `${wbCursorUrl(inner, { hx: 13, hy: 3 })}, not-allowed`;
  }
  if (tool === "link-straight" || tool === "link-curved") return "crosshair";
  if (tool === "lasso") return "crosshair";
  // Bucket, sticky and text had no case here, so all three fell through to
  // the `""` Pan returns, and `""` means "whatever the CSS says", which for
  // `.whiteboard-container` is `cursor: grab`: measured, three of the app's
  // eighteen board tools showed the open hand that means "drag the canvas"
  // while a click would have filled a shape, dropped a sticky or placed a
  // text box. Same fall-through that Select was fixed for, three tools later.
  if (tool === "bucket") {
    // A tipped bucket with a drip in the colour that is about to land, the
    // same "the cursor says what colour" idea the brush crosshair carries.
    const inner =
      `<g transform="rotate(-35 13 12)">` +
      `<path d="M6 8h12l-1.6 9.5a2 2 0 0 1-2 1.7h-4.8a2 2 0 0 1-2-1.7Z" fill="${color}" ` +
      `stroke="#000" stroke-opacity=".55" stroke-width="1.5" stroke-linejoin="round"/>` +
      `<path d="M6 8h12" fill="none" stroke="#000" stroke-opacity=".55" stroke-width="1.5"/>` +
      `</g>` +
      `<path d="M20 16c1.6 2 2.4 3.2 2.4 4.1a2.4 2.4 0 0 1-4.8 0c0-.9.8-2.1 2.4-4.1Z" ` +
      `fill="${color}" stroke="#000" stroke-opacity=".45" stroke-width="1"/>`;
    return `${wbCursorUrl(inner, { hx: 4, hy: 4 })}, crosshair`;
  }
  // `copy` and `text` rather than two more drawn images: both are system
  // cursors that already mean exactly this ("this click makes a new thing"
  // and "text goes here"), and a system cursor is the one that stays legible
  // over any board colour on any platform.
  if (tool === "sticky" || tool === "frame") return "copy";
  if (tool === "text") return "text";
  // Reported directly: "the cursor on the selection tool is wrong, it should
  // be a mouse pointer." Select had no case here, so it fell through to the
  // same `""` Pan returns: and `""` means "whatever the CSS says", which for
  // `.whiteboard-container` is `cursor: grab`. So the one tool whose whole
  // job is clicking things showed the open hand that means "drag the canvas",
  // and the two modes were indistinguishable from the pointer alone. `default`
  // (the plain arrow) is what every drawing app shows for select.
  if (tool === "select") return "default";
  return ""; // pan: the CSS grab/grabbing pair already says it
}

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

function wbGroupChain(item) {
  return item?.group_id ? String(item.group_id).split(WB_GROUP_SEP).filter(Boolean) : [];
}

function wbTopGroup(item) {
  return wbGroupChain(item)[0] || null;
}

function wbNewGroupId() {
  const bytes = crypto.getRandomValues ? crypto.getRandomValues(new Uint8Array(6)) : Array.from({ length: 6 }, () => Math.random() * 256);
  return Array.from(bytes, (b) => "abcdefghijklmnopqrstuvwxyz0123456789"[b % 36]).join("");
}

//: The chain every item in `items` starts with (empty when they share none).
function wbCommonGroupPrefix(items) {
  const chains = items.map(wbGroupChain);
  if (!chains.length) return [];
  const prefix = [];
  for (let i = 0; i < chains[0].length; i += 1) {
    const seg = chains[0][i];
    if (!chains.every((c) => c[i] === seg)) break;
    prefix.push(seg);
  }
  return prefix;
}

//: Each board item whose chain starts with `prefix` (all of them for none).
function wbItemsWithGroupPrefix(prefix) {
  const out = [];
  for (const [kind, list] of Object.entries(WB_LIST_BY_KIND)) {
    for (const item of wbState[list] || []) {
      const chain = wbGroupChain(item);
      if (prefix.every((seg, i) => chain[i] === seg)) out.push({ kind, item });
    }
  }
  return out;
}

//: An id too long to nest under (a 36-character one from before chains) is
//: swapped for a short one on every item that carries it.
function wbShortenGroupIds(entries, rows) {
  const long = new Set();
  for (const e of entries) for (const seg of wbGroupChain(e.item)) if (seg.length > 8) long.add(seg);
  for (const seg of long) {
    const short = wbNewGroupId();
    for (const { kind, item } of wbItemsWithGroupPrefix([])) {
      const chain = wbGroupChain(item);
      if (!chain.includes(seg)) continue;
      item.group_id = chain.map((c) => (c === seg ? short : c)).join(WB_GROUP_SEP);
      rows.push({ kind, item });
    }
  }
}

async function wbGroupSelection() {
  const entries = wbSelectionEntries();
  if (entries.length < 2) {
    toast("Select more than one item to group them.");
    return;
  }
  const groupId = wbNewGroupId();
  await wbRecordGesture(async () => {
    const rows = [];
    wbShortenGroupIds(entries, rows);
    const chains = entries.map((e) => [groupId, ...wbGroupChain(e.item)].join(WB_GROUP_SEP));
    if (chains.some((c) => c.length > WB_GROUP_MAX_LEN)) {
      //: The shortened ids above are already on the items; they are saved
      //: even when the group is refused, or the board and the server differ.
      if (rows.length) await wbSaveMany(rows);
      toast("Groups nest five deep at most.");
      return;
    }
    for (let i = 0; i < entries.length; i += 1) {
      entries[i].item.group_id = chains[i];
      rows.push({ kind: entries[i].kind, item: entries[i].item });
    }
    await wbSaveMany(rows);
    toast("Grouped.");
  });
  wbUpdateContextBar();
}

//: **Which of Group and Ungroup the selection can use** (B29: "the ungroup
//: button on the popup tools doesn't change"). Both buttons stayed on the bar
//: through every selection, so grouping changed nothing the eye could see.
//: One or the other, never both (the owner, 10-25: "the group and ungroup
//: button show at the same time"): a selection that shares a group ungroups
//: it; anything else of two or more groups (a group with loose items, or two
//: groups, makes a group of groups).
function wbGroupButtonState(items) {
  const shared = items.length > 0 && wbCommonGroupPrefix(items).length > 0;
  return { canGroup: items.length > 1 && !shared, canUngroup: shared };
}

function wbSyncGroupButtons() {
  const state = wbGroupButtonState(wbSelectionEntries().map((e) => e.item));
  document.getElementById("wb-multi-group")?.classList.toggle("hidden", !state.canGroup);
  document.getElementById("wb-multi-ungroup")?.classList.toggle("hidden", !state.canUngroup);
}

//: Takes the innermost group the selection shares off each member, so the
//: groups inside it stay groups. One Undo step.
async function wbUngroupSelection() {
  const lone = wbSelectedItem && (wbState[WB_LIST_BY_KIND[wbSelectedItem.kind]] || []).find((i) => i.id === wbSelectedItem.id);
  const entries = wbMultiSelection.size ? wbSelectionEntries() : lone ? [{ kind: wbSelectedItem.kind, item: lone }] : [];
  const prefix = wbCommonGroupPrefix(entries.map((e) => e.item));
  if (!prefix.length) return;
  const depth = prefix.length - 1;
  await wbRecordGesture(async () => {
    for (const { item } of entries) {
      const chain = wbGroupChain(item);
      chain.splice(depth, 1);
      item.group_id = chain.length ? chain.join(WB_GROUP_SEP) : null;
    }
    await wbSaveMany(entries);
  });
  toast("Ungrouped.");
  wbUpdateContextBar();
}

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

function wbItemElIndexed(key, retry = true) {
  const layer = document.getElementById("wb-html-layer");
  if (!layer) return null;
  const index = wbItemElIndex;
  if (index.count !== layer.childElementCount || index.last !== layer.lastElementChild) {
    index.byKey.clear();
    for (const child of layer.children) {
      const kind = child.classList.contains("node-card") ? "node" : child.classList.contains("wb-object") ? "object" : "";
      if (kind) index.byKey.set(`${kind}:${child.dataset.id}`, child);
    }
    index.count = layer.childElementCount;
    index.last = layer.lastElementChild;
  }
  const el = index.byKey.get(key);
  if (!el || el.isConnected) return el || null;
  index.count = -1;
  return retry ? wbItemElIndexed(key, false) : null;
}

function wbItemElement(kind, id) {
  const key = `${kind}:${id}`;
  const cached = wbItemElCache.get(key);
  if (cached && cached.isConnected) return cached;
  const el = wbItemElIndexed(key);
  if (el) wbItemElCache.set(key, el);
  else wbItemElCache.delete(key);
  return el;
}

//: A kind-agnostic bounding box (board coordinates, top-left/bottom-right)
//: for alignment/distribute/nudge math, which all need to compare items of
//: different kinds against each other. A sketch has no width/height of its
//: own, its path data *is* its shape, so its box comes from
//: `wbPathBBox`, while a card/object's box is just its x/y plus whichever
//: width/height it currently has (falling back to the same defaults their
//: own resize code uses).
function wbItemBBox(kind, item) {
  if (kind === "sketch") {
    // Mid-drag the moving path lives in `_dragLiveD`; the stored `data` is
    // still where the shape started, and a link following it would lag a
    // whole gesture behind.
    if (typeof item._dragLiveD === "string") return wbPathBBox(item._dragLiveD);
    //: A resize in flight keeps its path in `_liveD` until release; the
    //: Format panel's numbers read this box while the grip is held.
    if (typeof item._liveD === "string") return wbPathBBox(item._liveD);
    const parsed = wbSketchParsedData(item);
    if (!parsed) return null; // a link sketch: no shape of its own to align
    return wbPathBBox(parsed.d);
  }
  let w = item.width, h = item.height;
  // A card with no stored size (never manually resized) grows to fit its own
  // text: reported directly, with a screenshot: link anchor points sat well
  // inside a tall card's real border, because every unresized card was
  // assumed to be exactly WB_CARD_DEFAULT_SIZE.h (150px) regardless of how
  // much taller its actual content rendered it. Measured from the live DOM
  // instead, converted to board space with the same zoom-transform division
  // every drag handler already uses (`transform.k`), falls back to the
  // fixed default below only when the element genuinely isn't rendered.
  if (kind === "node") {
    const el = wbItemElement("node", item.id);
    if (el && el.offsetWidth && el.offsetHeight) {
      // Rendered size wins over a stored one for the same reason as
      // objects below: a card's text can push it taller than the height it
      // was last resized to.
      w = el.offsetWidth;
      h = el.offsetHeight;
    } else if (el) {
      // `offsetWidth/Height`, not `getBoundingClientRect()`: the rect is the
      // axis-aligned box of the *rotated* card, wider and taller than the
      // card itself, so a rotated note's links landed on a box that does
      // not exist (reported: "I rotated a note and the connection didn't
      // stick to the edge"). Layout size is unrotated and unscaled.
      w = w || el.offsetWidth;
      h = h || el.offsetHeight;
    }
  }
  // A text box or sticky can render taller than its stored height once its
  // text wraps (the element grows; the row does not), so the rendered size
  // wins when the element is on screen, a link aimed at the stored box
  // stopped short of the visible one.
  if (kind === "object") {
    //: **The measurement the render already took, when there is one**
    //: (MINDMAP_PLAN.md §13a). `wbContentBounds` asks this of every item on
    //: the board, so on a 500-topic map the fit that runs on open was 500
    //: document walks and 500 layout reads: 127.2ms of the open, for boxes
    //: `renderWbObjects` had just measured in one pass. The cache holds
    //: exactly those numbers (`offsetWidth`/`offsetHeight`, same reads, same
    //: elements) and is dropped by every render and at the end of every
    //: gesture, so a hit here cannot be older than what is on screen.
    const measured = wbMapNodeSizeCache?.get(item.id);
    if (measured) {
      w = measured.w;
      h = measured.h;
    } else {
      const el = wbItemElement("object", item.id);
      if (el && el.offsetWidth && el.offsetHeight) {
        w = el.offsetWidth;
        h = el.offsetHeight;
      }
    }
  }
  w = w || (kind === "node" ? WB_CARD_DEFAULT_SIZE.w : WB_OBJECT_MIN_SIZE);
  h = h || (kind === "node" ? WB_CARD_DEFAULT_SIZE.h : WB_OBJECT_MIN_SIZE);
  return { minX: item.x, minY: item.y, maxX: item.x + w, maxY: item.y + h };
}

// --- Getting around a board bigger than the screen -------------------------
//
// Three things any canvas needs once it holds more than one screenful, none
// of which this board had. Measured on a live board before building, rather
// than assumed:
//
//   * **There was no overview at all.** `board-minimap` in this file is the
//     *library thumbnail* drawn on a board's card in Boards & maps, it never
//     rendered on the canvas and has no viewport rectangle. Searching the DOM
//     of an open board for `.wb-minimap`/`#wb-minimap` found nothing.
//   * **There was no way to find a card by its words.** A board is made of
//     notes, and the notebook can full-text search every note in it, except
//     when they are laid out on a board, where the only way to find one was
//     to pan around looking.
//   * **"Fit to Screen" did not fit.** It was
//     `wbZoom.transform(d3.zoomIdentity)`, a reset to 100% at the origin. On
//     a board whose content sits at x=2000 that shows blank canvas, which
//     reads as the board having been wiped rather than as a navigation bug.
//
// All three are answered here, and all three share `wbContentBounds()`.

/** The bounding box of everything on the board, in board coordinates. */
function wbContentBounds() {
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  const grow = (box) => {
    if (!box) return;
    if (box.minX < minX) minX = box.minX;
    if (box.minY < minY) minY = box.minY;
    if (box.maxX > maxX) maxX = box.maxX;
    if (box.maxY > maxY) maxY = box.maxY;
  };
  // `wbItemBBox` already knows every kind's quirks: a link sketch has no
  // shape of its own and returns null, an unresized card is measured from
  // the live DOM. Reusing it is what keeps the navigator, the fit and the
  // search agreeing with the alignment guides about where things are.
  for (const [kind, list] of Object.entries(WB_LIST_BY_KIND)) {
    for (const item of wbState[list] || []) grow(wbItemBBox(kind, item));
  }
  if (!Number.isFinite(minX)) return null;
  return { minX, minY, maxX, maxY, width: maxX - minX, height: maxY - minY };
}

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

function wbFreeArea(container) {
  const box = container.getBoundingClientRect();
  const area = { left: 0, top: 0, right: box.width, bottom: box.height };
  const sides = { left: 0, top: 0, right: box.width, bottom: box.height };
  for (const selector of WB_FIT_OCCLUDERS) {
    const el = document.querySelector(selector);
    if (!el || el.hidden || el.closest(".hidden")) continue;
    const style = getComputedStyle(el);
    if (style.display === "none" || style.visibility === "hidden") continue;
    const r = el.getBoundingClientRect();
    const x0 = r.left - box.left, x1 = r.right - box.left, y0 = r.top - box.top, y1 = r.bottom - box.top;
    if (r.width < 4 || r.height < 4 || x1 <= 0 || x0 >= box.width || y1 <= 0 || y0 >= box.height) continue;
    const tall = r.height >= box.height * 0.5 && r.width < box.width * 0.6;
    if (tall) {
      if (x0 + x1 < box.width) sides.left = Math.max(sides.left, x1);
      else sides.right = Math.min(sides.right, x0);
    } else if (y0 + y1 < box.height) sides.top = Math.max(sides.top, y1);
    else sides.bottom = Math.min(sides.bottom, y0);
  }
  area.top = sides.top;
  area.bottom = sides.bottom;
  if (sides.right - sides.left >= box.width / 3) {
    area.left = sides.left;
    area.right = sides.right;
  }
  if (area.bottom - area.top < box.height / 3) {
    area.top = 0;
    area.bottom = box.height;
  }
  return area;
}

function wbSameView(a, b) {
  return Boolean(a && b) && Math.abs(a.k - b.k) < 0.001 && Math.abs(a.x - b.x) < 1 && Math.abs(a.y - b.y) < 1;
}

//: A panel opening, closing or the window changing size refits a view that
//: is still where the last fit put it, and leaves any other view alone.
function wbRefitIfFitted() {
  const container = document.getElementById("whiteboard-container");
  if (!wbFit.on || !container || !container.offsetParent || !container.clientWidth) return;
  wbZoomToFit({ padding: wbFit.padding });
}

/**
 * Put everything on the board on screen at once.
 *
 * Never zooms *in* past 1: `scaleExtent` allows 4x, but magnifying two cards
 * until they fill a 1440px window is not what anyone means by "fit".
 */
function wbZoomToFit({ animate = true, padding = 64, bounds = wbContentBounds(), maxScale = 1, refit = true } = {}) {
  const container = document.getElementById("whiteboard-container");
  if (!container) return;
  const sel = d3.select(container);
  if (!bounds) {
    // An empty board genuinely has nothing to fit, and the origin at 100% is
    // where the first card will land, so that is the honest destination.
    (animate ? sel.transition().duration(300) : sel).call(wbZoom.transform, d3.zoomIdentity);
    return;
  }
  const free = wbFreeArea(container);
  const k = Math.max(
    0.1,
    Math.min(
      maxScale,
      (free.right - free.left - padding * 2) / Math.max(bounds.width, 1),
      (free.bottom - free.top - padding * 2) / Math.max(bounds.height, 1),
    ),
  );
  const cx = bounds.minX + bounds.width / 2;
  const cy = bounds.minY + bounds.height / 2;
  const target = d3.zoomIdentity
    .translate((free.left + free.right) / 2 - k * cx, (free.top + free.bottom) / 2 - k * cy)
    .scale(k);
  //: Only Fit everything keeps fitting while the board settles; a zoom to
  //: the selection is a place, and the next layout must not pull it back out.
  wbFit.on = refit;
  wbFit.padding = padding;
  wbFit.target = target;
  wbFit.until = Date.now() + (animate ? 600 : 100);
  if (!animate) {
    sel.call(wbZoom.transform, target);
    return;
  }
  //: **The cull draws the destination once, then holds** (INBOX 431: the
  //: overview's Fit "reallllly glitchy and laggy"). A fit ends with
  //: everything on screen, so everything has to be drawn by its last frame
  //: whatever happens on the way. Culled frame by frame, a fit that zooms
  //: out brought a few more items in on every frame of its 350ms, so every
  //: frame restyled, laid out and painted, and on a 150-topic map at a 4x
  //: throttle the animation managed 12 frames, p95 233ms. Drawn against the
  //: destination first, the frames between restyle nothing (the zoom still
  //: re-rasters the board at each scale); the hold lifts when the animation
  //: ends or anything interrupts it. Measured against culling every frame,
  //: with everything else equal: the map's heavy frames went from five
  //: (100 to 233ms) to one at the press and a run of 50 to 83ms.
  //:
  //: The hold is this fit's own: a fit started over a running one
  //: interrupts it, and that one's release must not lift the new hold.
  wbCullHeld = 0;
  wbCullNow(target);
  const hold = ++wbCullHoldCount;
  wbCullHeld = hold;
  const release = () => {
    if (wbCullHeld !== hold) return;
    wbCullHeld = 0;
    wbScheduleCull();
  };
  //: A backstop: a transition whose element went away (the board closed
  //: mid-fit) may fire neither event, and a hold left on would stop culling
  //: for every later pan.
  setTimeout(release, 700);
  sel
    .transition()
    .duration(350)
    .on("end.cullhold", release)
    .on("interrupt.cullhold", release)
    .call(wbZoom.transform, target);
}

//: **Zoom steps (Ctrl+=, Ctrl+-, the zoom buttons) keep one point still**
//: (the owner, 2026-10-26: "does control +/- zoom in on the selection?"). The
//: selection's centre when something is selected, else the pointer when it is
//: over the board, else the view's centre. One read of the pointer per step,
//: none per frame.
function wbZoomAnchor({ usePointer = true } = {}) {
  const container = document.getElementById("whiteboard-container");
  const rect = container.getBoundingClientRect();
  const t = d3.zoomTransform(container);
  const bounds = wbSelectionBounds();
  if (bounds) return [t.applyX(bounds.minX + bounds.width / 2), t.applyY(bounds.minY + bounds.height / 2)];
  const p = usePointer ? wbPointerClient : null;
  if (p && p.clientX >= rect.left && p.clientX <= rect.right && p.clientY >= rect.top && p.clientY <= rect.bottom) {
    return [p.clientX - rect.left, p.clientY - rect.top];
  }
  return [rect.width / 2, rect.height / 2];
}

function wbZoomStep(factor, { duration = 160, usePointer = true } = {}) {
  const container = document.getElementById("whiteboard-container");
  if (!container) return;
  d3.select(container).transition().duration(duration).call(wbZoom.scaleBy, factor, wbZoomAnchor({ usePointer }));
}

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

function wbBoardHasFocus() {
  const view = document.getElementById("library-view-whiteboard");
  if (!view || view.classList.contains("hidden") || !view.getClientRects().length) return false;
  if (document.querySelector("dialog[open]")) return false;
  const active = document.activeElement;
  if (!active || active === document.body) return true;
  if (!view.contains(active)) return false;
  const tag = active.tagName.toLowerCase();
  return !(tag === "input" || tag === "textarea" || tag === "select" || active.isContentEditable);
}

function wbZoomKey(e) {
  if (!(e.ctrlKey || e.metaKey) || e.altKey) return;
  const run = WB_ZOOM_KEYS[e.code];
  if (!run || (e.shiftKey && /[01]$/.test(e.code)) || !wbBoardHasFocus()) return;
  e.preventDefault();
  e.stopPropagation();
  run();
}

function wbZoomTo100() {
  const container = document.getElementById("whiteboard-container");
  if (!container) return;
  d3.select(container).transition().duration(160).call(wbZoom.scaleTo, 1, wbZoomAnchor({ usePointer: false }));
}

//: **Zoom to the selection** (Shift+2, draw.io's and Figma's key): the
//: selected items fill the free canvas, magnified up to 2x so one small
//: shape is readable, never past it.
function wbZoomToSelection() {
  const bounds = wbSelectionBounds();
  if (!bounds) {
    toast("Select something to zoom to.");
    return;
  }
  wbZoomToFit({ bounds, padding: 32, maxScale: 2, refit: false });
}

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

function wbMapFrameScales(container) {
  const phone = container.clientWidth <= WB_MAP_PHONE_MAX_WIDTH;
  return phone
    ? { min: WB_MAP_PHONE_SCALE, open: WB_MAP_PHONE_SCALE, pad: 16, centre: true }
    : { min: WB_MAP_OPEN_MIN_SCALE, open: 1, pad: 64, centre: false };
}

//: **Frame a map when it opens**, rather than leaving the canvas wherever the
//: last board left it.
//:
//: Reported (mindmap.md H item 2, measured while reproducing report B): a map
//: whose root sits at the board origin opens with that root under
//: `#wb-topbar`, and a double-click on its text hits the top bar instead of
//: the node. Measured before this: the root's box was (16, 128)-(216, 172)
//: against a top bar of (24, 136)-(1416, 182), and `elementFromPoint` at the
//: root's own centre returned a top-bar button.
//:
//: Fit first, because a map is a tree and its shape is the point; but a fit
//: that lands under `WB_MAP_OPEN_MIN_SCALE` is a picture of a map rather than
//: a map, so a big one opens on its root at 1:1 instead. Only maps: an
//: ordinary board is a place you arrange by hand, and re-framing one on every
//: open would throw away the view its owner left it in.
function wbFrameMapOnOpen() {
  if (!wbIsMap()) return;
  const container = document.getElementById("whiteboard-container");
  if (!container) return;
  const scales = wbMapFrameScales(container);
  wbZoomToFit({ animate: false, padding: scales.pad });
  if (d3.zoomTransform(container).k >= scales.min) return;
  const root = wbMapIndex().roots[0];
  const bounds = wbContentBounds();
  if (!root || !bounds) return;
  //: Not a fit any more: a panel opening must not refit this view back to the
  //: illegible one (`wbRefitIfFitted` did exactly that 50ms after open on a
  //: wide window, so the same map opened at 0.4 there and at 1:1 on a narrow
  //: one).
  wbFit.on = false;
  const target = wbMapOpenTarget(bounds, wbItemBBox("object", root), wbFreeArea(container), scales.open, 48, scales.centre);
  d3.select(container).call(wbZoom.transform, d3.zoomIdentity.translate(target.x, target.y).scale(target.k));
}

//: **Where a map too big to fit opens at 1:1.** Owner, 2026-10-19: "when I go
//: onto the mindmap it doesnt focus me on the content and puts me down and to
//: the right where nothing is." The old fallback centred the root in the free
//: area, which for a map that grows right and down from its root (every
//: import, every ladder) leaves the top-left half of the screen empty and the
//: topics off the bottom-right. Per axis: start the view at the content's own
//: edge, so the empty space is on the far side; if that would push the root
//: out of view (a root in the middle of a radial map), centre on the root
//: instead.
function wbMapOpenTarget(bounds, rootBox, free, k, pad = 48, centre = false) {
  const axis = (lo, rLo, rHi, a0, a1) => {
    const span = (a1 - a0) / k;
    let start = lo - pad / k;
    if (centre || rLo < start || rHi > start + span) start = (rLo + rHi) / 2 - span / 2;
    return a0 - start * k;
  };
  return {
    k,
    x: axis(bounds.minX, rootBox.minX, rootBox.maxX, free.left, free.right),
    y: axis(bounds.minY, rootBox.minY, rootBox.maxY, free.top, free.bottom),
  };
}

//: **Each board keeps its own view for the session.** Boards and maps share
//: one d3 camera, so opening a second board used to inherit the first one's
//: pan and zoom, which on a map read as "nowhere". The view is remembered per
//: board id on the way out and put back on the way in, but only if some of the
//: content would be on screen with it; otherwise the board is framed afresh.
const wbBoardViews = new Map();

function wbRememberBoardView() {
  const id = window.currentBoardId;
  const container = document.getElementById("whiteboard-container");
  if (id == null || !container || !container.clientWidth || typeof wbZoom === "undefined") return;
  const t = d3.zoomTransform(container);
  wbBoardViews.set(id, { x: t.x, y: t.y, k: t.k });
  //: Past a reload too (per device, like the board's background image): the view of a board left open is its last.
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

/** Does this view show the content well enough to keep (INBOX 1428)?
 *  Any overlap used to count, so a board opened on a view showing only its
 *  corner stayed there ("it didnt fit the content to my screen at all"). Kept
 *  when half the content is on screen, or what is on screen fills a third of
 *  the canvas (a big board zoomed in on one part). */
function wbViewShowsContent(view, bounds, free) {
  if (!view || !bounds) return false;
  const x0 = view.x + view.k * bounds.minX, x1 = view.x + view.k * bounds.maxX;
  const y0 = view.y + view.k * bounds.minY, y1 = view.y + view.k * bounds.maxY;
  const seenW = Math.min(x1, free.right) - Math.max(x0, free.left);
  const seenH = Math.min(y1, free.bottom) - Math.max(y0, free.top);
  if (seenW <= 0 || seenH <= 0) return false;
  const seen = seenW * seenH;
  const whole = Math.max(1, (x1 - x0) * (y1 - y0));
  const room = Math.max(1, (free.right - free.left) * (free.bottom - free.top));
  return seen / whole >= 0.5 || seen / room >= 0.33;
}

//: Whether a view puts a whole board-space box inside the free canvas.
function wbViewHoldsBox(view, box, free) {
  const x0 = view.x + view.k * box.minX, x1 = view.x + view.k * box.maxX;
  const y0 = view.y + view.k * box.minY, y1 = view.y + view.k * box.maxY;
  return x0 >= free.left && x1 <= free.right && y0 >= free.top && y1 <= free.bottom;
}

/** Put a board's remembered view back, or frame it when it has none to give. */
function wbRestoreOrFrameBoard(boardId, restore = false) {
  const container = document.getElementById("whiteboard-container");
  if (!container) return;
  const saved = boardId == null ? null : wbBoardViews.get(boardId) || wbRememberBoardView.stored(boardId);
  //: `restore`: the caller is putting a board back (a document's board panel closing, documents-board.js), so the camera it had is
  //: kept as it was whatever the room to measure it by.
  if (saved && restore) {
    wbFit.on = false;
    d3.select(container).call(wbZoom.transform, d3.zoomIdentity.translate(saved.x, saved.y).scale(saved.k));
    return;
  }
  const bounds = wbContentBounds();
  const free = wbFreeArea(container);
  //: **A map's remembered view must show its centre topic clear of the
  //: chrome** (dog2 item 12: at 700 the root opened 54px under the left rail,
  //: the view kept from a Tab that had panned to its child). A board keeps
  //: any view that shows some of it; a map whose root is hidden is framed.
  const mapRoot = wbIsMap() ? wbMapIndex().roots[0] : null;
  const rootBox = mapRoot ? wbItemBBox("object", mapRoot) : null;
  const rootShown = !rootBox || (saved && wbViewHoldsBox(saved, rootBox, free));
  if (saved && rootShown && wbViewShowsContent(saved, bounds, free)) {
    wbFit.on = false;
    d3.select(container).call(wbZoom.transform, d3.zoomIdentity.translate(saved.x, saved.y).scale(saved.k));
    return;
  }
  if (wbIsMap()) return wbFrameMapOnOpen();
  //: With no view of its own the camera on screen is the last board's, so
  //: it is never kept: the board is framed (INBOX 1428).
  if (bounds) wbZoomToFit({ animate: false });
}

//: **The canvas is panned by its transform and never by scrolling** (mapdeeppan.js:
//: Tab under "Cells" at 1440x900 moved the whole map 351px with the zoom
//: transform unchanged, because the browser scrolls an `overflow: hidden` box
//: to bring a newly focused editor into view and centres it, 627px in the
//: report). Any such scroll (a focus, a caret, a find) is folded into the zoom
//: transform at once, so the view the saved camera, Fit and the reveal rules
//: read is the view on screen; the editors also focus with `preventScroll`.
function wbFoldNativeScroll(event) {
  const el = event.currentTarget;
  const dx = el.scrollLeft, dy = el.scrollTop;
  if (!dx && !dy) return;
  el.scrollLeft = 0;
  el.scrollTop = 0;
  const t = d3.zoomTransform(el);
  d3.select(el).call(wbZoom.transform, d3.zoomIdentity.translate(t.x - dx, t.y - dy).scale(t.k));
}

/** Centre the viewport on one board-space rectangle, keeping the current zoom. */
function wbCenterOn(box, { animate = true, minScale = 0.55 } = {}) {
  const container = document.getElementById("whiteboard-container");
  if (!container || !box) return;
  const sel = d3.select(container);
  const free = wbFreeArea(container);
  const current = d3.zoomTransform(container);
  // Jumping to a match at 0.12x would land on a card too small to read, so
  // ease the zoom up to something legible, but never zoom *out* to get
  // there, because that would undo a deliberate close-up.
  const k = Math.max(current.k, Math.min(minScale, 1));
  const cx = (box.minX + box.maxX) / 2;
  const cy = (box.minY + box.maxY) / 2;
  const target = d3.zoomIdentity
    .translate((free.left + free.right) / 2 - k * cx, (free.top + free.bottom) / 2 - k * cy)
    .scale(k);
  (animate ? sel.transition().duration(300) : sel).call(wbZoom.transform, target);
}

//: **A selection is kept clear of the bottom docks** (wb4's found-not-fixed:
//: a shape low on the board had its lower grips under the zoom pill and the
//: tool row, 3 of 8 at 390x844 and 3 of 8 at 1440x900, so the edge that
//: resizes it could not be pressed). Figma and Miro move the view; a grip
//: cannot sit above a dock, which is a sibling of the canvas. Once the
//: selection has settled (350 ms with no press, so a double-click is never
//: interrupted), the view slides up just far enough that the selection's
//: bottom edge and its grips clear the docks it overlaps, and never so far
//: that its top meets the bar above it. A pan afterwards is the person's own:
//: the signature of the selection (what and where, in board units) has to
//: change before the view moves again.
const WB_REVEAL_DOCKS = "#wb-tools-panel, .whiteboard-floating-panel[data-panel-id=\"zoom\"]";
let wbRevealSig = "";
let wbRevealTimer = 0;

function wbQueueReveal() {
  clearTimeout(wbRevealTimer);
  wbRevealTimer = setTimeout(wbRevealSelection, 350);
}

function wbRevealSelection() {
  const container = document.getElementById("whiteboard-container");
  let b = null;
  try {
    b = container?.offsetParent && wbSelectionBounds();
  } catch {
    // The selected item went (deleted, or the board changed) while the timer ran.
  }
  if (!b || document.activeElement?.matches?.("input, textarea, [contenteditable]")) return;
  const sig = [...wbSelectedKeys()].join(",") + `|${Math.round(b.minX)},${Math.round(b.minY)},${Math.round(b.width)},${Math.round(b.height)}`;
  if (sig === wbRevealSig) return;
  wbRevealSig = sig;
  const t = d3.zoomTransform(container), r = container.getBoundingClientRect();
  const pad = 40; // wbSelectionBounds' own margin
  const left = r.left + t.x + (b.minX + pad) * t.k, right = left + (b.width - 2 * pad) * t.k;
  const top = r.top + t.y + (b.minY + pad) * t.k, bottom = top + (b.height - 2 * pad) * t.k;
  let dockTop = Infinity;
  for (const el of document.querySelectorAll(WB_REVEAL_DOCKS)) {
    const d = el.getBoundingClientRect();
    if (d.width < 4 || d.right < left - 8 || d.left > right + 8 || d.bottom < top || d.top > bottom + 10) continue;
    dockTop = Math.min(dockTop, d.top);
  }
  const shift = Math.min(bottom + 14 - dockTop, top - (r.top + wbFreeArea(container).top + 56));
  if (!(shift >= 4)) return;
  d3.select(container).transition().duration(200).call(wbZoom.transform, d3.zoomIdentity.translate(t.x, t.y - shift).scale(t.k));
}

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

function wbShowToolSettings(tool) {
  const wanted = new Set(WB_TOOL_SETTINGS[tool] || []);
  for (const el of document.querySelectorAll("#wb-context [data-wb-tool-setting]")) {
    // An enhanced <select> is drawn by its shell; hiding the native one alone
    // would leave the opener showing (`enhanceSelect`, sheets-selects.js).
    const shown = el.closest(".select-shell") || el;
    shown.classList.toggle("hidden", !wanted.has(el.dataset.wbToolSetting));
  }
  return wanted;
}

//: The two "what is selected, if it is of this kind" lookups. Module-level
//: because both the properties panel's own controls and the copy-style
//: actions below need them, and they close over nothing but module state.
function wbSelectedSketchOrNull() {
  if (!wbSelectedItem || wbSelectedItem.kind !== "sketch") return null;
  return wbState.sketches.find((s) => s.id === wbSelectedItem.id) || null;
}

function wbSelectedTextObjectOrNull() {
  if (!wbSelectedItem || wbSelectedItem.kind !== "object") return null;
  const obj = wbState.objects?.find((o) => o.id === wbSelectedItem.id);
  return obj && obj.kind === "text" ? obj : null;
}

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

function wbPickStyle(source, keys) {
  const out = {};
  for (const key of keys) if (source?.[key] !== undefined) out[key] = source[key];
  return out;
}

//: A sticker's glyph size: most of its box's shorter side (decision 44).
function wbStickerSize(obj) {
  return Math.max(12, Math.round(Math.min(obj.width || 96, obj.height || 96) * 0.72));
}

function wbCopySelectedStyle() {
  //: A map topic's look (MINDMAP_PLAN.md decision 42): pasted onto topics
  //: only, refused on a shape the way a shape's is refused on a text box.
  const topic = wbSelectedMapNode();
  if (topic) {
    wbCopiedStyle = { kind: "topic", style: wbMapTopicStyle(topic) };
    return toast("Style copied. Select topics and press Ctrl+Alt+V.");
  }
  const sketch = wbSelectedSketchOrNull();
  if (sketch) {
    let parsed = null;
    try { parsed = JSON.parse(sketch.data); } catch { parsed = null; }
    if (!parsed) return toast("That item has no style to copy.");
    wbCopiedStyle = { kind: "sketch", style: wbPickStyle(parsed, WB_SKETCH_STYLE_KEYS) };
    return toast("Style copied. Select a shape or link and press Ctrl+Alt+V.");
  }
  const obj = wbSelectedTextObjectOrNull();
  if (obj) {
    wbCopiedStyle = { kind: "object", style: wbPickStyle(obj.data, WB_OBJECT_STYLE_KEYS) };
    return toast("Style copied. Select a text box and press Ctrl+Alt+V.");
  }
  toast("Select a shape, link, text box or topic first.");
}

async function wbPasteCopiedStyle() {
  if (!wbCopiedStyle) return toast("Copy a style first (Ctrl+Alt+C).");
  // Every item in a multi-selection, so restyling a diagram is one action
  // rather than one per shape, the same reach `wbApplyBulkMove` already has.
  const entries = wbMultiSelection.size > 0
    ? wbSelectionEntries()
    : (wbSelectedItem ? [wbSelectedItem] : []);
  if (!entries.length) return toast("Select something to paste the style onto.");

  let applied = 0;
  let skipped = 0;
  const rows = [];
  for (const entry of entries) {
    const list = wbState[WB_LIST_BY_KIND[entry.kind]] || [];
    const item = list.find((i) => i.id === entry.id);
    if (!item) continue;
    if (wbCopiedStyle.kind === "topic") {
      if (entry.kind === "object" && WB_MAP_KINDS.has(item.kind)) {
        await wbMapSetNodeStyle(item, { ...wbCopiedStyle.style }, { rows });
        applied += 1;
      } else {
        skipped += 1;
      }
    } else if (entry.kind === "sketch" && wbCopiedStyle.kind === "sketch") {
      if (wbSketchSetProps(item, { ...wbCopiedStyle.style })) rows.push({ kind: "sketch", item });
      applied += 1;
    } else if (entry.kind === "object" && wbCopiedStyle.kind === "object" && item.kind === "text") {
      item.data = { ...item.data, ...wbCopiedStyle.style };
      rows.push({ kind: "object", item });
      applied += 1;
    } else {
      skipped += 1;
    }
  }
  await wbSaveMany(rows);
  wbScheduleRender();
  wbUpdateContextBar();
  if (!applied) return toast("That style does not fit what you selected.");
  toast(skipped
    ? `Style pasted onto ${applied}. ${skipped} skipped: a different kind of item.`
    : `Style pasted onto ${applied}.`);
}

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

//: The reset fields for one sketch, or null for a drawing with nothing to
//: reset (a highlighter's look is its tool). A line whose ends are drawn in
//: its own path has them redrawn at the default width.
function wbSketchStyleReset(parsed) {
  if (!parsed || parsed.shape === "highlighter") return null;
  const patch = Object.fromEntries(WB_SKETCH_RESET_KEYS.map((key) => [key, undefined]));
  if (typeof parsed.d === "string" && wbSketchTakesCaps(parsed)) {
    const caps = wbSketchCaps(parsed);
    if (caps.startCap !== "none" || caps.endCap !== "none") {
      patch.d = wbRegenerateShapeCaps(parsed.d, caps.startCap, caps.endCap, 3 * 4 + 6, null);
    }
  }
  return patch;
}

//: The data an object keeps after a reset, or null for one with no look of
//: its own here (a card follows the board; a map topic is reset by its map).
function wbObjectStyleReset(obj) {
  if (!obj?.data || WB_MAP_KINDS.has(obj.kind)) return null;
  const data = { ...obj.data };
  for (const key of WB_OBJECT_RESET_KEYS) delete data[key];
  if (wbIsSticky(obj)) Object.assign(data, { sticky: true, bg: WB_STICKY_PAPERS[0].value, color: "#2a2a1f", font_size: 16 });
  return data;
}

async function wbResetSelectedStyle() {
  const entries = wbMultiSelection.size > 0 ? wbSelectionEntries() : (wbSelectedItem ? [wbSelectedItem] : []);
  if (!entries.length) return toast("Select something to reset its style.");
  let reset = 0;
  await wbRecordGesture(async () => {
    const rows = [];
    for (const entry of entries) {
      const item = (wbState[WB_LIST_BY_KIND[entry.kind]] || []).find((i) => i.id === entry.id);
      if (!item || wbIsLocked(entry.kind, item)) continue;
      if (entry.kind === "object" && WB_MAP_KINDS.has(item.kind)) {
        const patch = {};
        for (const key of WB_MAP_STYLE_KEYS) patch[key] = null;
        await wbMapSetNodeStyle(item, patch, { undo: false, rows });
        reset += 1;
      } else if (entry.kind === "sketch") {
        let parsed = null;
        try { parsed = JSON.parse(item.data); } catch { parsed = null; }
        const patch = wbSketchStyleReset(parsed);
        if (!patch) continue;
        wbSketchSetProps(item, patch);
        rows.push({ kind: "sketch", item });
        reset += 1;
      } else if (entry.kind === "object") {
        const data = wbObjectStyleReset(item);
        if (!data) continue;
        item.data = data;
        rows.push({ kind: "object", item });
        reset += 1;
      }
    }
    await wbSaveMany(rows);
  });
  wbScheduleRender();
  wbUpdateContextBar();
  if (typeof wbFormatSyncSoon === "function") wbFormatSyncSoon();
  if (!reset) return toast("Nothing selected has a style of its own to reset.");
  wbAnnounce(reset === 1 ? "Style reset." : `Style reset on ${reset} items.`);
}

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
const WB_CONTEXT_MENU_SECTIONS = ["more-style", "more-card", "more-guides", "more-notes", "more-mindmap", "more-tidy", "more-shape", "more-link"];

//: Which row of the table a selection reads. Returns null when the bar has
//: nothing to say, which is what closes it.
function wbContextKindOf(sel, item) {
  if (!sel || !item) return null;
  if (sel.kind === "sketch") {
    let parsedLink = null;
    try {
      const candidate = JSON.parse(item.data);
      if (candidate && (candidate.type || "").startsWith("link-")) parsedLink = candidate;
    } catch { /* not JSON: not a link either */ }
    //: **A cross-link on a map has no board bar** (§13c). Its whole control
    //: surface is the map's own link ring now, and the board's bar was the
    //: second vocabulary for the same object that §13.2 measured (ink, caps
    //: and stroke, against the ring's own words). A link between a topic and a
    //: card, or any link on an ordinary board, still gets the bar: it is not
    //: one of the map's two kinds of connection and the ring has nothing to
    //: say about it.
    if (parsedLink && wbMapCrossLinkInfo(item.id)) return null;
    if (parsedLink) return "link";
    const parsed = wbSketchParsedData(item);
    if (!parsed) return null;
    return WB_FILLABLE_SHAPES.has(parsed.shape) ? "shape" : "line";
  }
  if (sel.kind === "node") return "note";
  //: A frame has no style to set and no order to change: it stays below
  //: what it holds (decision 14), so the bar has nothing to offer it.
  if (sel.kind === "object" && item.kind === "frame") return null;
  if (sel.kind === "object") return item.kind === "text" ? "text" : "image";
  return null;
}

//: Shows exactly the groups a row names and hides the rest, in one pass, so
//: a control can never be left over from the last selection.
function wbApplyContextRow(row) {
  const bar = new Set(row?.bar || []);
  const more = new Set(row?.more || []);
  for (const name of WB_CONTEXT_GROUPS) {
    for (const el of document.querySelectorAll(`#wb-context [data-wb-ctx="${name}"]`)) {
      el.classList.toggle("hidden", !bar.has(name));
    }
  }
  for (const name of WB_CONTEXT_MENU_SECTIONS) {
    for (const el of document.querySelectorAll(`#wb-context-menu [data-wb-ctx="${name}"]`)) {
      el.classList.toggle("hidden", !more.has(name));
    }
  }
  // The rows inside the Style section that only some kinds can use.
  for (const id of ["wb-prop-nostroke-row", "wb-prop-md-row", "wb-prop-bullets-row", "wb-fill-opacity-row", "wb-stroke-none-row"]) {
    document.getElementById(id)?.classList.add("hidden");
  }
  // What acts on a selection, back for every row that has one; the held-tool
  // row takes them away again (`wbHideSelectionActions`).
  for (const id of WB_SELECTION_ONLY_CONTROLS) document.getElementById(id)?.classList.remove("hidden");
  wbContextMoreWrap()?.classList.remove("hidden");
}

//: **With a tool held and nothing selected, the bar has no selection to act
//: on** (INBOX 445). Duplicate, Delete and the More menu's copy and paste of
//: a style stayed on it and did nothing when pressed; the More menu itself is
//: kept only for a shape tool, whose fill opacity and stroke live there.
const WB_SELECTION_ONLY_CONTROLS = ["wb-selbar-duplicate", "wb-selbar-delete", "wb-copy-style-row"];

function wbContextMoreWrap() {
  return document.querySelector("#wb-context [data-wb-menu-toggle]")?.closest(".wb-board-menu-wrap") || null;
}

function wbHideSelectionActions(keepMore) {
  for (const id of WB_SELECTION_ONLY_CONTROLS) document.getElementById(id)?.classList.add("hidden");
  wbContextMoreWrap()?.classList.toggle("hidden", !keepMore);
}

//: **The bar with nothing selected sits over the rail.** Placed here rather
//: than in `wbUpdateSelectionBar` for one measured reason: that function runs
//: on every frame of every pan (`handleWbZoom`), and this position depends on
//: the rail and the host, neither of which a pan moves. `data-wb-anchor` is
//: how the pan frame knows to leave it alone without asking any question that
//: costs a DOM walk; the same lesson the text-editing query above records.
function wbParkContextOnRail(on) {
  const bar = document.getElementById("wb-context");
  const host = document.getElementById("library-view-whiteboard");
  if (!bar || !host) return;
  if (!on) {
    bar.classList.add("hidden");
    delete bar.dataset.wbAnchor;
    return;
  }
  bar.dataset.wbAnchor = "rail";
  bar.classList.remove("hidden");
  // One bar over this canvas, never two (the map strip's own rule).
  document.getElementById("wb-map-strip")?.classList.add("hidden");
  const hostRect = host.getBoundingClientRect();
  const rail = document.getElementById("wb-tools-panel")?.getBoundingClientRect();
  const w = bar.offsetWidth;
  const h = bar.offsetHeight;
  const left = Math.max(8, Math.min(Math.max(8, hostRect.width - w - 8), hostRect.width / 2 - w / 2));
  // Ten pixels over the rail, and never off the top: on a short window the
  // rail's own top edge can be less than the bar's height from the top bar.
  const railTop = rail && rail.height ? rail.top - hostRect.top : hostRect.height - 72;
  const topBar = document.getElementById("wb-topbar")?.getBoundingClientRect();
  const floor = topBar ? topBar.bottom - hostRect.top + 8 : 56;
  bar.style.left = `${Math.round(left)}px`;
  bar.style.top = `${Math.round(Math.max(floor, railTop - h - 10))}px`;
}

//: Filled first, placed second, never the other way round: the bar is centred
//: on the selection from its own measured width, and a bar still holding the
//: last selection's controls is a different width. The map strip's own comment
//: a few hundred lines down records exactly the same trap for the same reason.
function wbUpdateContextBar() {
  const bar = document.getElementById("wb-context");
  if (!bar) return;
  wbFormatSyncSoon();
  wbFmtState.effects?.refreshStatus();
  if (wbFillContextBar() === "rail") wbParkContextOnRail(true);
  else wbUpdateSelectionBar();
}

//: What the bar holds, from `WB_CONTEXT_CONTROLS`. Returns "rail" when it is
//: showing a held tool's own settings and so belongs over the rail rather than
//: over a selection it does not have.
function wbFillContextBar() {
  const bar = document.getElementById("wb-context");
  WB_CTX_FOLD.sig = null;
  if (!bar) return null;
  const show = (...ids) => ids.forEach((id) => document.getElementById(id)?.classList.remove("hidden"));

  // A multi-selection has no one fill or stroke to edit (mixed kinds), but it
  // does have arrange, which only means anything here.
  if (wbMultiSelection.size > 0) {
    //: Only topics, on a map: the map's group, and neither Duplicate (a copy
    //: of several topics lands as loose roots) nor the More menu, whose
    //: format, style and guides rows are all the board's.
    const mapTopics = wbMapMultiTopics();
    if (mapTopics) {
      wbApplyContextRow(WB_CONTEXT_CONTROLS.mapmulti);
      document.getElementById("wb-selbar-duplicate")?.classList.add("hidden");
      wbContextMoreWrap()?.classList.add("hidden");
      wbSyncMapMulti(mapTopics);
      delete bar.dataset.wbAnchor;
      return null;
    }
    wbApplyContextRow(WB_CONTEXT_CONTROLS.multi);
    wbSyncGroupButtons();
    // Extract notes (BACKLOG.md §62) only makes sense once the selection
    // actually includes a note card's content to extract from; a selection of
    // pure shapes has no "notes-in-context".
    const hasNoteCard = wbSelectionEntries().some((e) => e.kind === "node");
    document.querySelector('#wb-context-menu [data-wb-ctx="more-notes"]')?.classList.toggle("hidden", !hasNoteCard);
    //: Tidy only once the selection holds a connector to lay out along.
    document.querySelector('#wb-context-menu [data-wb-ctx="more-tidy"]')?.classList.toggle("hidden", !wbTidyEdges(wbSelectionEntries()).length);
    delete bar.dataset.wbAnchor;
    return null;
  }

  // The bar is also where a drawing tool's own settings live, so it opens for
  // a held tool with nothing selected: otherwise picking the pen would hide
  // the pen's own thickness. This is the split every whiteboard app makes,
  // tools in the rail, their properties in the context surface.
  if (!wbSelectedItem) {
    const settings = wbShowToolSettings(window.currentTool);
    const toolDraws = settings.size > 0;
    wbApplyContextRow(toolDraws ? WB_CONTEXT_CONTROLS.tool : null);
    // The More menu's two shape rows, for the tools that draw a shape.
    if (settings.has("fill")) show("wb-fill-opacity-row", "wb-stroke-none-row");
    if (toolDraws) wbHideSelectionActions(settings.has("fill"));
    if (!toolDraws) wbParkContextOnRail(false);
    return toolDraws ? "rail" : null;
  }
  delete bar.dataset.wbAnchor;

  const { kind, id } = wbSelectedItem;
  const item = (wbState[WB_LIST_BY_KIND[kind]] || []).find((i) => i.id === id);
  const which = wbContextKindOf(wbSelectedItem, item);
  wbApplyContextRow(which ? WB_CONTEXT_CONTROLS[which] : null);
  if (!which) return;

  //: The ink swatch's word says what it colours (the owner, 2026-10-11).
  const inkWord = { link: "Line", line: "Line", shape: "Border", text: "Text" }[which];
  const inkWordEl = document.getElementById("wb-prop-color-word");
  if (inkWordEl && inkWord) inkWordEl.textContent = inkWord;
  document.getElementById("wb-prop-color")?.setAttribute("aria-label", `${inkWord || "Line"} colour`);
  if (which === "link") {
    const parsed = JSON.parse(item.data);
    document.getElementById("wb-prop-color").value = parsed.color || "#ffffff";
    document.getElementById("wb-prop-width").value = parsed.width || 3;
    const caps = wbLinkCaps(parsed);
    document.getElementById("wb-prop-startcap").value = caps.startCap;
    document.getElementById("wb-prop-endcap").value = caps.endCap;
    wbShowCapSizes(caps);
    document.getElementById("wb-prop-dash").value = parsed.dash || "solid";
    document.getElementById("wb-prop-route").value = wbLinkRouteName(parsed);
    //: The Label button is for a board connector (a map's cross-link is
    //: worded through its ring); it says "Edit" once there are words.
    const labelButton = document.getElementById("wb-prop-label");
    if (labelButton) {
      labelButton.classList.toggle("hidden", !wbLinkTakesLabel(item, parsed));
      labelButton.title = parsed.label ? "Change this connector's label (Enter)" : "Add a label to this connector (Enter)";
    }
    return;
  }

  if (which === "line" || which === "shape") {
    const parsed = wbSketchParsedData(item);
    document.getElementById("wb-prop-color").value = parsed.color || "#000000";
    document.getElementById("wb-prop-width").value = parsed.width || 3;
    document.getElementById("wb-prop-dash").value = parsed.dash || "solid";
    show("wb-prop-nostroke-row");
    document.getElementById("wb-prop-nostroke").checked = Boolean(parsed.noStroke);
    // **The caps come off the object, never off the tool's default** (the
    // plan's section 2 item 4, and a live report before it): a drawn line
    // reported "Arrow" at both ends because the control was showing
    // `window.currentArrowStyle` rather than what was on the shape.
    const isArrow = wbSketchTakesCaps(parsed);
    document.querySelector('#wb-context [data-wb-ctx="caps"]')?.classList.toggle("hidden", !isArrow);
    if (isArrow) {
      const caps = wbSketchCaps(parsed);
      document.getElementById("wb-prop-startcap").value = caps.startCap;
      document.getElementById("wb-prop-endcap").value = caps.endCap;
      wbShowCapSizes(caps);
    }
    if (which === "shape") {
      document.getElementById("wb-prop-shapefill").value = parsed.fill || "#3355ff";
      const filled = wbColour.fillIsOn("sketch", parsed);
      document.getElementById("wb-prop-shapefill-on").checked = filled;
      //: Dimmed, not disabled: a fill picked from its well turns it on.
      document.getElementById("wb-prop-shapefill").classList.toggle("wb-colour-off", !filled);
    }
    return;
  }

  if (which === "text") {
    //: A sticky's papers, first on its bar, the current one pressed.
    const paper = document.querySelector('#wb-context [data-wb-ctx="paper"]');
    if (paper) {
      const sticky = wbIsSticky(item);
      paper.classList.toggle("hidden", !sticky);
      if (sticky) wbFillPaperPicker(paper, item);
    }
    for (const button of document.querySelectorAll("#wb-prop-align button")) {
      button.classList.toggle("active", button.dataset.align === (item.data.align || "left"));
    }
    show("wb-prop-md-row", "wb-prop-bullets-row");
    document.getElementById("wb-prop-md").checked = Boolean(item.data.md);
    document.getElementById("wb-prop-color").value = item.data.color || "#1f2430";
    document.getElementById("wb-prop-bg").value = item.data.bg === "transparent" ? "#ffffff" : (item.data.bg || "#ffffff");
    document.getElementById("wb-prop-bg-none").checked = item.data.bg === "transparent";
    document.getElementById("wb-prop-border").value = item.data.border_color === "transparent" ? "#8888aa" : (item.data.border_color || "#8888aa");
    document.getElementById("wb-prop-border-none").checked = item.data.border_color === "transparent";
    document.getElementById("wb-prop-fontsize").value = item.data.font_size || 16;
    // A text box has no line ends and no drawn width; the ink group's width
    // field is a stroke thickness, which a box does not have either.
    document.getElementById("wb-prop-width").parentElement?.classList.add("hidden");
    return;
  }

  if (which === "note") {
    // Mind-mapping (item 25): only worth offering once the card actually has
    // something to arrange; a card with no links is already exactly where a
    // "mind map of one" would put it.
    const hasLink = wbState.sketches.some((s) => {
      try {
        const p = JSON.parse(s.data);
        return p.type && p.type.startsWith("link-") && (p.sourceId === item.id || p.targetId === item.id);
      } catch {
        return false;
      }
    });
    document.querySelector('#wb-context-menu [data-wb-ctx="more-mindmap"]')?.classList.toggle("hidden", !hasLink);
  }
}

//: Mind-mapping (ROADMAP item 25): "Arrange as mind map" auto-positions
//: everything reachable from a selected card via the whiteboard's own
//: links into a Tree or Radial layout, reusing the Graph tab's own
//: `d3.hierarchy`/`d3.tree` approach (see `layoutHierarchy` above) rather
//: than a second layout engine, just against the whiteboard's plain
//: node/link data instead of the notebook's category/reply structure (no
//: categories here, so none of that grouping machinery is needed). A link
//: graph isn't necessarily a tree, cycles, a card linked to two others
//: that are themselves linked, so a BFS from the root turns whatever is
//: reachable into a real spanning tree (first link found wins the "parent"
//: slot), which is the only sense "arrange everything connected to it" can
//: have for a layout that needs one parent per node.
const WB_MINDMAP_TREE_ROW = 170; // spacing across the fan-out axis
const WB_MINDMAP_TREE_COL = 320; // spacing per depth level, left → right
const WB_MINDMAP_RADIAL_STEP = 260; // ring spacing per depth level

//: The undirected adjacency every mind-map operation starts from, every
//: link sketch touching two *currently real* nodes (a stale link to an
//: already-deleted card is silently excluded, same as the render path
//: already does).
function wbLinkAdjacency() {
  const adjacency = new Map();
  const addEdge = (a, b) => {
    if (!adjacency.has(a)) adjacency.set(a, new Set());
    if (!adjacency.has(b)) adjacency.set(b, new Set());
    adjacency.get(a).add(b);
    adjacency.get(b).add(a);
  };
  const nodeIds = new Set(wbState.nodes.map((n) => n.id));
  for (const sketch of wbState.sketches) {
    let parsed;
    try {
      parsed = JSON.parse(sketch.data);
    } catch {
      continue;
    }
    if (!parsed.type || !parsed.type.startsWith("link-")) continue;
    if (nodeIds.has(parsed.sourceId) && nodeIds.has(parsed.targetId)) addEdge(parsed.sourceId, parsed.targetId);
  }
  return adjacency;
}

//: A BFS spanning tree from `rootId`, in the `{parentOf, childrenOf}` shape
//: both `wbArrangeMindMap` and the Tab/Enter branch-entry commands share.
function wbMindMapSpanningTree(rootId) {
  const adjacency = wbLinkAdjacency();
  const parentOf = new Map([[rootId, null]]);
  const childrenOf = new Map([[rootId, []]]);
  const queue = [rootId];
  while (queue.length) {
    const current = queue.shift();
    for (const neighbour of adjacency.get(current) || []) {
      if (parentOf.has(neighbour)) continue;
      parentOf.set(neighbour, current);
      childrenOf.get(current).push(neighbour);
      childrenOf.set(neighbour, []);
      queue.push(neighbour);
    }
  }
  return { parentOf, childrenOf };
}

async function wbArrangeMindMap(rootId, kind) {
  const root = wbState.nodes.find((n) => n.id === rootId);
  if (!root) return;
  const { parentOf, childrenOf } = wbMindMapSpanningTree(rootId);
  if (parentOf.size < 2) {
    toast("Nothing linked to this card to arrange.");
    return;
  }

  // d3.hierarchy wants a tree of plain objects with a `children` accessor: 
  // built once, keyed by node id, the same shape `layoutHierarchy` above
  // builds from `children`/`groups`.
  const buildTree = (id) => ({ id, children: (childrenOf.get(id) || []).map(buildTree) });
  const laid = d3.hierarchy(buildTree(rootId));

  const positions = new Map();
  if (kind === "radial") {
    // Same `d3.tree().size([2*Math.PI, 1])` call `layoutHierarchy`'s own
    // radial branch uses; ring spacing is a plain fixed step per depth
    // here rather than that function's label-aware `radialRings` sizing,
    // since a mind map has no per-ring label-width category to budget for.
    d3.tree().size([2 * Math.PI, 1])(laid);
    laid.each((point) => {
      const radius = point.depth * WB_MINDMAP_RADIAL_STEP;
      positions.set(point.data.id, {
        x: radius * Math.cos(point.x - Math.PI / 2),
        y: radius * Math.sin(point.x - Math.PI / 2),
      });
    });
  } else {
    d3.tree().nodeSize([WB_MINDMAP_TREE_ROW, WB_MINDMAP_TREE_COL])(laid);
    laid.each((point) => {
      positions.set(point.data.id, { x: point.depth * WB_MINDMAP_TREE_COL, y: point.x });
    });
  }

  // The layout is computed around (0,0) at the root, shift the whole
  // result so the root card itself doesn't move, only what's connected to
  // it, which is what "arrange everything connected to it" (not "recentre
  // my board") actually asked for.
  const rootPos = positions.get(rootId);
  const dx = root.x - rootPos.x, dy = root.y - rootPos.y;
  const rows = [];
  for (const [id, pos] of positions) {
    if (id === rootId) continue;
    const node = wbState.nodes.find((n) => n.id === id);
    if (!node) continue;
    node.x = wbSnap(pos.x + dx);
    node.y = wbSnap(pos.y + dy);
    rows.push({ kind: "node", item: node });
  }
  await wbSaveMany(rows);

  // Cached for the Tab/Enter branch-entry commands below, so a card added
  // right after an arrange lands in the layout it was just shown, not a
  // freshly re-derived (and possibly different, since BFS parent choice
  // isn't unique when a card has more than one link back toward the root)
  // spanning tree.
  window.wbMindMap = { rootId, parentOf, childrenOf, kind };
  wbScheduleRender();
  toast(`Arranged ${nounCount(parentOf.size, "card")} as a ${kind === "radial" ? "radial" : "tree"} mind map.`);
}

//: Tab/Enter branch entry (item 25's second piece) needs to know a card's
//: "parent" in mind-map terms, which a whiteboard link doesn't carry on its
//: own (just two ids, no direction). Reuses the cached map from a prior
//: `wbArrangeMindMap` run when the given card is part of it; otherwise
//: seeds one lazily, rooted at the card itself, from the board's current
//: links: so Tab/Enter still work sensibly on a board nobody has arranged
//: yet, not only right after clicking Tree/Radial.
function wbMindMapEnsureMap(fromId) {
  if (!window.wbMindMap || !window.wbMindMap.parentOf.has(fromId)) {
    const { parentOf, childrenOf } = wbMindMapSpanningTree(fromId);
    window.wbMindMap = { rootId: fromId, parentOf, childrenOf, kind: window.wbMindMap?.kind || "radial" };
  }
  return window.wbMindMap;
}

//: Creates a real note, a whiteboard card for it, and a link from
//: `parentId`, the one operation both Tab and Enter reduce to, differing
//: only in which card counts as the parent.
async function wbMindMapAddCard(parentId, x, y) {
  const entry = await apiJson("/entries", { method: "POST", body: JSON.stringify({ content: "New branch", map_topic: true, defer_filing: true }) });
  wbPushUndo({ action: "noteMade", entryId: entry.id });
  const nodeRes = await apiJson("/whiteboard/nodes", {
    method: "POST",
    body: JSON.stringify({ entry_id: entry.id, board_id: window.currentBoardId ?? null, x: wbSnap(x), y: wbSnap(y), z: 1 }),
  });
  wbState.nodes.push(nodeRes);
  const sketchRes = await apiJson("/whiteboard/sketches", {
    method: "POST",
    body: JSON.stringify({
      data: JSON.stringify({
        type: "link-curved",
        sourceId: parentId,
        targetId: nodeRes.id,
        color: window.currentStrokeColor || "#ffffff",
      }),
      x: 0, y: 0, z: 1, board_id: window.currentBoardId ?? null,
    }),
  });
  wbState.sketches.push(sketchRes);

  // The card about to render reads its text out of `allEntries`, which was
  // fetched before this note existed. Without this the new branch renders
  // as a placeholder and never resolves, see the `!entry` branch in the
  // card renderer.
  await refreshEntries([entry.id]);

  const map = wbMindMapEnsureMap(parentId);
  map.parentOf.set(nodeRes.id, parentId);
  if (!map.childrenOf.has(parentId)) map.childrenOf.set(parentId, []);
  map.childrenOf.get(parentId).push(nodeRes.id);
  map.childrenOf.set(nodeRes.id, []);

  selectWbItem("node", nodeRes.id);
  wbScheduleRender();
  // **A new branch is an empty thought, so it opens ready to be typed.**
  // Before this it was a card reading "New branch" and nothing else: the
  // gesture created a node and then left you to find the way to name it,
  // which is the difference between a mind-mapping tool and a diagram
  // editor. `wbScheduleRender` is async, so this waits for the card to
  // exist rather than assuming it does.
  requestAnimationFrame(() => wbEditNodeText(nodeRes.id));
  return nodeRes;
}

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

function wbEditNodeText(nodeId, firstKey = "", whole = null) {
  wbAddGate.cardRetypeId = null;
  const node = wbState.nodes.find((n) => n.id === nodeId);
  if (!node) return;
  const card = document.querySelector(`.node-card[data-id="${nodeId}"]`);
  const content = card?.querySelector(".wb-card-content");
  if (!content) return;
  const entry = whole || allEntries.find((e) => e.id === node.entry_id);
  //: A clipped row is fetched whole first and edited from what `fullEntry` returns: the editor's text is what gets saved.
  if (entry?.content_truncated) return void fullEntry(entry.id).then((read) => wbEditNodeText(nodeId, firstKey, read), (error) => toast(error.message, true));
  const original = entry?.content || "";

  const box = document.createElement("textarea");
  box.className = "wb-card-editor";
  //: **The app's note engine, not a bare textarea** (DOCUMENTS_PLAN Phase
  //: 8c, the board half). The id is the `NOTE_SURFACES` row, so the focus
  //: below mounts the same editor every other note box has: Live rendering,
  //: the "/" menu, undo, Ctrl+B. One card is edited at a time, which is what
  //: lets the id be fixed.
  box.id = "wb-card-editor";
  box.value = original;
  //: The card's own contract, handed to the engine as keys because once the
  //: view is mounted the textarea never sees a keystroke again: the four
  //: listeners this used to hang off it (Enter, Escape, blur, and the
  //: stopPropagation guard) all went quiet the moment a view sat over it,
  //: which is why this row could not simply be added to the table.
  box.noteSurfaceKeys = [
    { key: "Enter", run: () => { finish(true); return true; } },
    {
      key: "Shift-Enter",
      run: (view) => {
        view.dispatch(view.state.replaceSelection("\n"), { scrollIntoView: true });
        return true;
      },
    },
    { key: "Escape", run: () => { finish(false); return true; } },
  ];
  content.replaceChildren(box);
  box.focus({ preventScroll: true });
  box.select();
  if (firstKey) box.setRangeText(firstKey, 0, box.value.length, "end");

  //: Listeners on the card's content element rather than on the textarea,
  //: so they hold whichever of the two has the focus, and all of them go
  //: with the edit (`signal`), since the content element outlives it.
  const listening = new AbortController();
  let settled = false;
  const finish = async (save) => {
    if (settled) return;
    settled = true;
    listening.abort();
    const text = box.value.trim();
    const keep = save && text ? text : original;
    if (save && text && text !== original) {
      try {
        await apiJson(`/entries/${node.entry_id}`, {
          method: "PUT",
          body: JSON.stringify({ content: text }),
        });
        wbPushUndo({ action: "note", entryId: node.entry_id, content: original });
        // The card reads its text out of `allEntries`; without this the next
        // render would use the old content and the edit would look discarded.
        await loadEntries();
      } catch (err) {
        toast(err.message || voiceLine("failed", { what: "save that" }), true);
      }
    }
    // **Put the text back by hand, not by re-rendering.** Found live: after
    // saving, the textarea was still on the card. `wbScheduleRender` runs a
    // d3 data join, and card *content* is only built in the `enter`
    // selection: an existing card keeps whatever DOM it already has, which
    // here was the editor. So the edit saved correctly to the server and
    // looked like it had done nothing, which is the worst of both.
    content.replaceChildren();
    renderMarkdown(content, keep);
    wbScheduleRender();
    if (save && wbSelectedItem?.kind === "node" && wbSelectedItem.id === nodeId) wbAddGate.cardRetypeId = nodeId;
  };

  // Enter commits, Shift+Enter is a real newline, the convention for a
  // single-idea field. Escape abandons. Blur commits, because clicking away
  // to the next card is the most common way to finish one.
  //
  // This listener is the textarea's half, for the moment before the engine
  // has mounted (the bundle can take a beat on a first card) and for a
  // session where it cannot load; `noteSurfaceKeys` above is the view's half.
  box.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      finish(true);
    } else if (event.key === "Escape") {
      event.preventDefault();
      finish(false);
    } else if (event.key === "Tab") {
      //: A tab in the text, as the engine's Tab indents, rather than the
      //: browser walking the focus out of the card and committing it.
      event.preventDefault();
      box.setRangeText("\t", box.selectionStart, box.selectionEnd, "end");
    }
  }, { signal: listening.signal });
  //: **The guard: a key typed in the card is text, never a board gesture**
  //: (Tab and Enter make branches). On the content element, so it holds for
  //: the view as well as the textarea: a key's bubble passes through here on
  //: its way to the board's document-level handlers either way.
  content.addEventListener("keydown", (event) => event.stopPropagation(), {
    signal: listening.signal,
  });
  //: Blur commits, judged a tick later and against the content element:
  //: mounting the engine moves the textarea into its wrapper, which blurs it
  //: for a moment before the view takes the focus, and that is not the
  //: person clicking away.
  content.addEventListener("focusout", (event) => {
    if (content.contains(event.relatedTarget)) return;
    setTimeout(() => {
      if (!content.contains(document.activeElement)) finish(true);
    }, 0);
  }, { signal: listening.signal });
}

//: Tab: a new child of the selected card, at "the next open radial slot":
//: evenly spaced by angle among the parent's existing children (plus the
//: one about to be added, so a lone first child doesn't land straight on
//: top of the parent), one ring further out.
async function wbMindMapAddChild(parentId) {
  const parent = wbState.nodes.find((n) => n.id === parentId);
  if (!parent) return;
  const map = wbMindMapEnsureMap(parentId);
  const existing = (map.childrenOf.get(parentId) || []).length;
  const slots = Math.max(existing + 1, 3);
  // **Fan out sideways first, not upwards.** The offset used to be
  // `-Math.PI / 2`, straight up, so the very first branch off a root card
  // landed one full ring *above* it. Driven live: a map created at the
  // canvas centre put its first Tab branch off the top edge, clipped and
  // half unreadable, which is a bad first impression of the one gesture the
  // whole feature turns on. Sideways is also how every mind-mapping tool
  // fans a first child, because a page is wider than it is tall.
  const angle = (existing / slots) * 2 * Math.PI;
  const parentBox = wbItemBBox("node", parent);
  const cx = (parentBox.minX + parentBox.maxX) / 2, cy = (parentBox.minY + parentBox.maxY) / 2;
  const w = parent.width || WB_CARD_DEFAULT_SIZE.w, h = parent.height || WB_CARD_DEFAULT_SIZE.h;
  await wbMindMapAddCard(
    parentId,
    cx + WB_MINDMAP_RADIAL_STEP * Math.cos(angle) - w / 2,
    cy + WB_MINDMAP_RADIAL_STEP * Math.sin(angle) - h / 2
  );
}

//: Enter: a new sibling of the selected card (a child of *its* parent).
//: A card with no known parent (the mind map's own root, or one never
//: linked to anything) has no sibling slot to fill, falls back to adding
//: a child of the card itself, the only branch that makes sense there.
async function wbMindMapAddSibling(cardId) {
  const map = wbMindMapEnsureMap(cardId);
  const parentId = map.parentOf.get(cardId);
  await wbMindMapAddChild(parentId == null ? cardId : parentId);
}

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

//: `move` marks the three item drags (a card, a box or topic, a shape), the
//: gestures the delete target answers (`wbTrashTake`).
function wbBeginGesture(restore, move = false) {
  wbGesture = { restore, cancelled: false, move };
  return wbGesture;
}

function wbEndGesture(gesture) {
  if (gesture && wbGesture === gesture) wbGesture = null;
  return Boolean(gesture?.cancelled);
}

//: Called by the board's Escape before anything else Escape does: a gesture
//: in flight is the one thing on screen the key can mean.
function wbCancelGesture() {
  const gesture = wbGesture;
  if (!gesture || gesture.cancelled) return false;
  gesture.cancelled = true;
  try {
    gesture.restore?.();
  } finally {
    wbClearAlignmentGuides();
    wbTrashHide();
  }
  return true;
}

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

function wbTouchSlopStep(gesture, event, unit = 1, slop = WB_TOUCH_SLOP) {
  const { dx, dy } = event;
  const touch = String(event.sourceEvent?.type || "").startsWith("touch");
  if (!gesture || gesture.slopDone) return { dx, dy };
  gesture.slopX = (gesture.slopX || 0) + dx;
  gesture.slopY = (gesture.slopY || 0) + dy;
  if (Math.hypot(gesture.slopX, gesture.slopY) * unit < (touch ? slop : WB_CLICK_SLOP)) return null;
  gesture.slopDone = true;
  return { dx: gesture.slopX, dy: gesture.slopY };
}

//: True for the touch-start of a second finger (or a third). d3-drag's filter
//: gets the touch-start itself as `event`.
function wbIsSecondTouch(event) {
  return String(event?.type || "").startsWith("touch") && (event.touches?.length || 0) > 1;
}

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

function wbTrashTarget() {
  if (wbTrash.el?.isConnected) return wbTrash.el;
  const host = document.getElementById("wb-present-bar")?.parentElement;
  if (!host) return null;
  wbTrash.el = document.createElement("div");
  wbTrash.el.className = "whiteboard-floating-panel wb-trash card glass hidden";
  wbTrash.el.setAttribute("aria-hidden", "true");
  const icon = document.createElement("i");
  icon.className = "ph ph-trash";
  const label = document.createElement("span");
  label.className = "wb-trash-label";
  wbTrash.el.append(icon, label);
  //: The sidebar's drags (Library tiles, Layers rows) are the browser's own drag and drop, which sends no pointer
  //: moves, so the target answers dragover, dragleave and drop itself (INBOX 660 follow-up, LEDGER L262).
  wbTrash.el.addEventListener("dragover", (e) => {
    if (!wbTrash.drop) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    if (!wbTrash.el.classList.contains("wb-trash-hot")) wbTrashSetHot(true);
  });
  wbTrash.el.addEventListener("dragleave", (e) => {
    if (!wbTrash.drop || wbTrash.el.contains(e.relatedTarget)) return;
    //: Crossing from the icon to the label leaves a child with no related target in some engines: only the pointer's place says it left.
    const r = wbTrash.el.getBoundingClientRect();
    const inside = e.clientX > r.left && e.clientX < r.right && e.clientY > r.top && e.clientY < r.bottom;
    if (!inside) wbTrashSetHot(false);
  });
  wbTrash.el.addEventListener("drop", (e) => {
    if (!wbTrash.drop) return;
    e.preventDefault();
    const drop = wbTrash.drop;
    wbTrash.dndEnd();
    drop();
  });
  host.appendChild(wbTrash.el);
  return wbTrash.el;
}

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

function wbTrashSetHot(hot) {
  const el = wbTrashTarget();
  if (!el) return;
  el.classList.toggle("wb-trash-hot", hot);
  el.querySelector(".wb-trash-label").textContent = hot ? "Release to delete" : "Drop here to delete";
}

function wbTrashHide() {
  wbTrash.rect = null;
  if (wbTrash.el) wbTrash.el.classList.add("hidden");
}

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

//: Called first thing by each item drag's end, while the drag still holds
//: what `restore` needs. True when the drop was on the target: the move is
//: put back, the gesture is marked cancelled (so the end saves nothing) and
//: the delete is under way.
function wbTrashTake(gesture, kind, d) {
  const hit = Boolean(gesture && gesture === wbGesture && gesture.move && !gesture.cancelled && gesture.overTrash);
  wbTrashHide();
  if (!hit) return false;
  const keys = wbDragIsBulkMove(kind, d.id) ? [...wbMultiSelection] : [wbMultiKey(kind, d.id)];
  gesture.cancelled = true;
  try {
    gesture.restore?.();
  } finally {
    wbClearAlignmentGuides();
  }
  wbTrashDelete(keys);
  return true;
}

async function wbTrashDelete(keys) {
  const rank = { sketch: 0, node: 1, object: 2 };
  const ordered = [...keys].sort((a, b) => rank[a.split(":")[0]] - rank[b.split(":")[0]]);
  const find = (key) => {
    const sep = key.indexOf(":");
    const kind = key.slice(0, sep), id = Number(key.slice(sep + 1));
    return [kind, (wbState[WB_LIST_BY_KIND[kind]] || []).find((i) => i.id === id)];
  };
  const map = wbIsMap();
  const topics = () => (wbState.objects || []).filter((o) => WB_MAP_KINDS.has(o.kind)).length;
  const topicsBefore = map ? topics() : 0;
  wbMultiSelection.clear();
  clearWbSelection();
  await wbRecordGesture(async () => {
    for (const key of ordered) {
      const [kind, item] = find(key);
      if (!item) continue;
      if (kind === "sketch") await wbDeleteSketch(item);
      else if (kind === "node") await wbDeleteNode(item);
      else await wbDeleteObject(item);
    }
  });
  wbApplySelectionHighlight();
  wbScheduleRender();
  const gone = ordered.filter((key) => !find(key)[1]).length;
  if (!gone) return;
  const step = wbUndoStack[wbUndoStack.length - 1];
  const topicsGone = map ? topicsBefore - topics() : 0;
  const words = topicsGone
    ? `Deleted ${nounCount(topicsGone, "topic")}.`
    : `Deleted ${gone === 1 ? "1 item" : `${gone} items`}.`;
  wbAnnounce(words);
  toastAction(words, "Undo", async () => {
    //: The toast's Undo is the stack's own step, and only while it is the
    //: last thing done: Ctrl+Z may already have taken it back.
    if (wbUndoStack[wbUndoStack.length - 1] === step) await wbUndo();
  });
}

//: Put a moved item (and whatever moved with it) back where the drag found
//: it, on screen only: nothing was saved yet, so nothing needs unsaving.
function wbRestoreMove(kind, d) {
  if (kind === "sketch") {
    const el = document.querySelector(`.sketch-group[data-id="${d.id}"]`);
    if (d._dragOriginalD != null) {
      el?.querySelector(".sketch-path")?.setAttribute("d", d._dragOriginalD);
      el?.querySelector(".sketch-hitbox")?.setAttribute("d", d._dragOriginalD);
      wbLayoutShapeLabel(el);
    }
    delete d._dragLiveD;
  } else {
    d.x = d._dragOriginX;
    d.y = d._dragOriginY;
    const el = document.querySelector(WB_SELECTOR_BY_KIND[kind](d.id));
    if (el) el.style.transform = wbItemTransform(d);
  }
  if (d._bulkOrigin) {
    wbApplyBulkMove(d._bulkOrigin, 0, 0);
    for (const entry of d._bulkOrigin.values()) delete entry.item._liveD;
  }
  if (d._linkedSketches?.length) wbUpdateLinkedSketches(d.id, d._linkedSketches);
  if (d._mapEdges?.length) wbUpdateMapEdges(d._mapEdges);
  if (wbIsMap()) wbMapClearDropTarget();
  delete d._dropTarget;
  wbUpdateSelectionBar();
}

//: Put a resized or turned card or text box back to the box it had when the
//: grip was taken, from the undo snapshot the grip already keeps.
function wbRestoreBox(kind, d, before) {
  if (!before) return;
  for (const key of ["x", "y", "width", "height", "rotation"]) d[key] = before[key];
  const el = document.querySelector(WB_SELECTOR_BY_KIND[kind](d.id));
  if (!el) return;
  el.style.width = d.width ? `${d.width}px` : "";
  el.style.height = d.height ? `${d.height}px` : "";
  el.style.transform = wbItemTransform(d);
}

//: **Shift keeps a move on one axis** (Figma, Miro, tldraw, PowerPoint): the
//: axis the pointer has travelled further along wins, decided afresh every
//: frame so a drag that turns the corner follows it. `null` means free.
function wbAxisLock(dx, dy, shiftKey) {
  if (!shiftKey) return null;
  return Math.abs(dx) >= Math.abs(dy) ? "x" : "y";
}

//: The undo entries for every member a drag carried besides the item under
//: the pointer. A group move used to undo only the one item that was grabbed
//: and leave the rest of the group where it landed ("a real limitation, not
//: attempted further", the node drag's end said): the origin map already
//: holds where each member started, so the whole move is one step now.
function wbBulkUndoEntries(origin) {
  const out = [];
  for (const entry of origin?.values() || []) {
    const before = WB_KIND_INFO[entry.kind].payload(entry.item);
    if (entry.kind === "sketch") {
      let parsed = null;
      try { parsed = JSON.parse(entry.item.data); } catch { parsed = null; }
      if (!parsed) continue;
      parsed.d = entry.d;
      before.data = JSON.stringify(parsed);
    } else {
      if (entry.item.x === entry.x && entry.item.y === entry.y) continue;
      before.x = entry.x;
      before.y = entry.y;
    }
    out.push({ action: "move", kind: entry.kind, id: entry.id, before });
  }
  return out;
}

//: **Alt-drag leaves a copy behind** (tldraw, Figma, Miro and Excalidraw all
//: bind it). Made at the drop, at the place every dragged item was taken
//: from, rather than at the press: a copy created mid-gesture needs a render
//: to appear, and a render during a drag is exactly what this file keeps
//: finding kills the drag. What is left behind and what is carried look the
//: same, so where the copy is made is invisible except for that.
//:
//: Two things are not copied, each for a reason that is not this gesture's:
//: a note card (one card per note per board, `wbCopySelection`'s own note)
//: and a map topic (a copy of a topic's row is a topic with no place in
//: the tree, which is not what anyone dragging a branch means by a copy).
//: A group copied together is a new group, not new members of the old one.
async function wbDropCopies(befores) {
  const created = await wbCreateCopies(
    befores
      .filter(({ kind, before }) => kind !== "node" && !(kind === "object" && WB_MAP_KINDS.has(before.kind)))
      .map(({ kind, before }) => ({ kind, payload: before })),
    0, 0
  );
  if (befores.some((b) => b.kind === "node")) {
    toast("A note card can't be copied: drag the note in again from the Library for a second card.");
  }
  return created;
}

//: Make copies of `items` ({kind, payload}) moved by (dx, dy), and return
//: their "create" undo entries. The one maker behind Alt-drag, Ctrl+D and
//: paste, so a copy is the same thing however it was asked for: a group
//: copied whole is a new group, and a shape moves by its path, not its x/y
//: (see `wbTransformPathD`: a sketch's own x/y do not place it).
async function wbCreateCopies(items, dx, dy, noComments = false) {
  const groups = new Map();
  const wire = items.map(({ kind, payload, key, src, dst }, i) => {
    const body = { ...payload, board_id: window.currentBoardId ?? null };
    if (kind === "sketch") {
      const parsed = JSON.parse(body.data || "{}");
      if (dx || dy) {
        if (typeof parsed.d === "string") parsed.d = wbTransformPathD(parsed.d, { dx, dy });
        else wbShiftLinkGeometry(parsed, dx, dy);
      }
      if (noComments) delete parsed.comments;
      body.data = JSON.stringify(parsed);
    } else {
      body.x = (body.x || 0) + dx;
      body.y = (body.y || 0) + dy;
      if (noComments) wbWithoutComments(body);
    }
    //: Each id in the chain gets its own fresh one, so a pasted group of
    //: groups is still nested and never joins the original.
    if (body.group_id) {
      body.group_id = wbGroupChain(body).map((seg) => {
        if (!groups.has(seg)) groups.set(seg, wbNewGroupId());
        return groups.get(seg);
      }).join(WB_GROUP_SEP);
    }
    const row = { key: key || `i${i}` };
    if (kind === "sketch") Object.assign(row, { sketch: body, src: src || null, dst: dst || null });
    else row.object = body;
    return row;
  });
  //: One request for the whole paste (the server makes the rows in one
  //: transaction and points each copied link at its new ends), where it was
  //: one request per item: measured in WHITEBOARD_PLAN 1355.
  let res;
  try {
    res = await apiJson(`/whiteboard/boards/${window.currentBoardId ?? 0}/paste`, { method: "POST", body: JSON.stringify({ items: wire }) });
  } catch (err) {
    toast(err.message || voiceLine("failed", { what: "make that copy" }), true);
    return [];
  }
  wbState.objects.push(...res.objects);
  wbState.sketches.push(...res.sketches);
  return [
    ...res.objects.map((o) => ({ action: "create", kind: "object", id: o.id })),
    ...res.sketches.map((o) => ({ action: "create", kind: "sketch", id: o.id })),
  ];
}

//: A copy without the threads on it: a card's `comments` column, an object's
//: `data.comments`.
function wbWithoutComments(body) {
  if ("comments" in body) body.comments = null;
  if (body.data && typeof body.data === "object") {
    const { comments, ...rest } = body.data;
    body.data = rest;
  }
}

//: A copied link carries its own free ends and bends in board units, so a
//: moved copy moves them too (a path's `d` is moved by `wbTransformPathD`).
function wbShiftLinkGeometry(parsed, dx, dy) {
  for (const name of ["sourcePoint", "targetPoint"]) {
    if (parsed[name]) parsed[name] = { x: parsed[name].x + dx, y: parsed[name].y + dy };
  }
  if (Array.isArray(parsed.points)) parsed.points = parsed.points.map((p) => ({ x: p.x + dx, y: p.y + dy }));
}

//: One undo step for a whole drag: the item under the pointer, the members
//: it carried, and the copies an Alt-drag left behind.
function wbPushDragUndo(entries) {
  const all = entries.filter(Boolean);
  if (all.length === 0) return;
  wbPushUndo(all.length === 1 ? all[0] : { action: "batch", entries: all });
}

//: Everything a drag that ends has to do after its own item is saved: the
//: carried members saved, the copies made, and one undo step pushed for it.
async function wbFinishDrag(primary, bulkOrigin, altCopy) {
  wbFmtState.keys?.recordDrag(primary);
  const carried = wbBulkUndoEntries(bulkOrigin);
  if (bulkOrigin) await wbSaveBulkMove(bulkOrigin);
  const bends = await wbCarryWaypoints(primary, bulkOrigin);
  let copies = [];
  if (altCopy && (primary || carried.length)) {
    copies = await wbDropCopies([primary, ...carried].filter(Boolean));
  }
  wbPushDragUndo([primary, ...carried, ...bends, ...copies]);
  if (copies.length || bends.length) wbScheduleRender();
}

//: **A connector's bends move with what it joins** (wb-phase2 step 5,
//: draw.io's rule): when both its ends were carried by one drag, its
//: waypoints go the same way, so a moved group keeps its lines' shape rather
//: than leaving their bends behind. Returns the undo entries, which ride in
//: the drag's one step.
async function wbCarryWaypoints(primary, origin) {
  if (!origin?.size) return [];
  let dx = 0, dy = 0, found = false;
  for (const entry of origin.values()) {
    if (entry.kind === "sketch") {
      const was = typeof entry.d === "string" ? wbPathBBox(entry.d) : null;
      const now = was && wbItemBBox("sketch", entry.item);
      if (was && now) [dx, dy, found] = [now.minX - was.minX, now.minY - was.minY, true];
    } else if (entry.x !== undefined) {
      [dx, dy, found] = [entry.item.x - entry.x, entry.item.y - entry.y, true];
    }
    if (found) break;
  }
  if (!found || (!dx && !dy)) return [];
  const moved = new Set(origin.keys());
  if (primary) moved.add(wbMultiKey(primary.kind, primary.id));
  const out = [];
  const rows = [];
  for (const sketch of wbState.sketches || []) {
    let data = null;
    try {
      data = JSON.parse(sketch.data);
    } catch {
      continue;
    }
    if (!data || !String(data.type || "").startsWith("link-") || !Array.isArray(data.points) || !data.points.length) continue;
    const ends = [[data.sourceKind || "node", data.sourceId], [data.targetKind || "node", data.targetId]];
    if (!ends.every(([kind, id]) => id != null && moved.has(wbMultiKey(kind, id)))) continue;
    const before = WB_KIND_INFO.sketch.payload(sketch);
    wbSketchSetProps(sketch, { points: data.points.map((p) => ({ x: Math.round(p.x + dx), y: Math.round(p.y + dy) })) });
    rows.push({ kind: "sketch", item: sketch });
    out.push({ action: "move", kind: "sketch", id: sketch.id, before });
  }
  await wbSaveMany(rows);
  return out;
}

//: **A map's own nodes go in one request.** A tidy of a two hundred node map
//: was two hundred PUTs, two hundred transactions and a map half arranged for
//: as long as they took, with nothing to roll back to when one of them failed
//: (recorded as "Tidy still persists one node at a time"). `move-many` takes
//: the whole set, so the batch either lands or does not. Everything that is
//: not a map node on a map board still goes one at a time: a sketch's `d` and
//: an image's box are not what that endpoint moves.
//:
//: Chunked at 200 against the endpoint's own 400, so a map twice the size of
//: anything built here still goes in two requests rather than in four hundred.
//: A failure falls back to the per-object path rather than surfacing: the
//: caller has already painted the new positions, and the fallback is the code
//: that was doing this until now.
const WB_MOVE_MANY_CHUNK = 200;

async function wbSaveMapBulkMove(origin) {
  const boardId = window.currentBoardId;
  if (!boardId || !wbIsMap()) return null;
  const batched = [];
  for (const entry of origin.values()) {
    if (entry.kind === "object" && WB_MAP_KINDS.has(entry.item?.kind)) batched.push(entry);
  }
  //: One node is not a batch: a single PUT says more in its own event log and
  //: costs the same.
  if (batched.length < 2) return null;
  try {
    for (let at = 0; at < batched.length; at += WB_MOVE_MANY_CHUNK) {
      const slice = batched.slice(at, at + WB_MOVE_MANY_CHUNK);
      await apiJson(`/whiteboard/boards/${boardId}/nodes/move-many`, {
        method: "PUT",
        body: JSON.stringify({
          moves: slice.map((entry) => ({ id: entry.item.id, x: entry.item.x, y: entry.item.y })),
        }),
      });
    }
  } catch (err) {
    return null;
  }
  return new Set(batched);
}

async function wbSaveBulkMove(origin) {
  //: **And is rebuilt where the items landed, before the save goes out.** The
  //: translate above is a view of the drag, not the truth: the items' own
  //: coordinates have moved, so the outline has to be recomputed from them or
  //: it keeps the offset for as long as the selection lasts. Measured before
  //: the fix: after the drag ended the box was still at the position the
  //: items had started from, not just during the gesture.
  //:
  //: Here rather than in each of the three per-kind drag handlers, because
  //: this is the one function all three end at, and it runs after the drag is
  //: over, so replacing the handle elements can no longer cut a gesture short.
  wbApplySelectionHighlight();
  const done = await wbSaveMapBulkMove(origin);
  const rows = [];
  for (const entry of origin.values()) {
    if (done && done.has(entry)) continue;
    if (entry.kind === "sketch") {
      if (!entry.item._liveD) continue;
      wbSketchSetD(entry.item, entry.item._liveD);
      delete entry.item._liveD;
    }
    rows.push({ kind: entry.kind, item: entry.item });
  }
  await wbSaveMany(rows);
}


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
//: **Each board and map keeps its own history** (the owner, 2026-10-05: "undo
//: and redo history for specific documents, whiteboards, mindmaps"). One pair
//: of stacks served every board, so Ctrl+Z on a second board replayed the
//: first board's steps against rows it could not see, or re-made them there.
//: The pair is swapped by board on every read, kept for the session.
const wbHistoryByBoard = new Map();
let wbHistoryBoard = null;

function wbHistoryFor() {
  const key = String(window.currentBoardId ?? "default");
  if (key === wbHistoryBoard) return;
  if (wbHistoryBoard !== null) wbHistoryByBoard.set(wbHistoryBoard, { undo: wbUndoStack, redo: wbRedoStack });
  const kept = wbHistoryByBoard.get(key);
  wbUndoStack = kept ? kept.undo : [];
  wbRedoStack = kept ? kept.redo : [];
  wbHistoryBoard = key;
  if (!kept) wbHistoryRestore(key);
}

//: **And across a reload** (INBOX 553(b), decision 17 as amended): a board
//: met for the first time this session takes back what was stored for it
//: (undo-store.js), unless a step has been taken on it in the meantime.
//: Nothing is written for a board until its stored history has been read,
//: so an open that is quicker than the read cannot overwrite it with nothing.
const wbHistoryRead = new Set();

function wbHistoryRestore(key) {
  if (key === "default" || typeof undoStoreGet !== "function") {
    wbHistoryRead.add(key);
    return;
  }
  undoStoreGet(`board:${key}`).then((stored) => {
    wbHistoryRead.add(key);
    if (wbHistoryBoard !== key || !stored || wbUndoStack.length || wbRedoStack.length) return;
    wbUndoStack = Array.isArray(stored.undo) ? stored.undo : [];
    wbRedoStack = Array.isArray(stored.redo) ? stored.redo : [];
    wbUpdateUndoRedoButtons();
  });
}

function wbUpdateUndoRedoButtons() {
  wbHistoryFor();
  if (typeof undoStorePut === "function" && wbHistoryRead.has(wbHistoryBoard) && wbHistoryBoard !== "default") {
    undoStorePut(`board:${wbHistoryBoard}`, undoStoreBoardValue(wbUndoStack, wbRedoStack));
  }
  const undoBtn = document.getElementById("wb-undo");
  const redoBtn = document.getElementById("wb-redo");
  if (undoBtn) undoBtn.disabled = wbUndoStack.length === 0;
  if (redoBtn) redoBtn.disabled = wbRedoStack.length === 0;
  //: The status bar's pair is the same pair, one floor down (`renderUndoBar`
  //: reads `wbCanUndo`/`wbCanRedo` while a board is open), so it is repainted
  //: with these rather than left showing the app stack's state.
  //: Once a frame, not on the press (OPEN 813): the repaint reads layout, and
  //: run inline it made every add wait for a flush.
  if (typeof scheduleUndoBar === "function") scheduleUndoBar();
}

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

function wbDropUndoEntry(entry) {
  const at = wbUndoStack.lastIndexOf(entry);
  if (at !== -1) wbUndoStack.splice(at, 1);
  //: An eraser swipe folds its deletes into one batch (L-whiteboard-35), so a failed one is found inside it.
  else for (const top of wbUndoStack) if (top.action === "batch" && top.entries.includes(entry)) top.entries.splice(top.entries.indexOf(entry), 1);
  wbUpdateUndoRedoButtons();
}

//: A delete the server refused: the undo entry goes, the redo history the
//: push wiped comes back, and the user is told (audit B8; it was a console line).
//: The ink a stored black or white default draws in on this board (audit U1):
//: those two are the app's own theme defaults, not a choice, so they follow
//: the board's background; any other colour is the person's and stays.
function wbDefaultInk(color) {
  const c = String(color || "").toLowerCase();
  return c === "#000000" || c === "#ffffff" ? wbReadableInk(c, wbBoardBg()) : color;
}

//: `pass` is true for the rest of one synchronous render (a microtask clears
//: it): every stroke asks for the same colour, and building the signature
//: below walked the root's attributes 280 times a render (W30, 2.4 ms).
const wbBoardBgCache = { sig: "", value: "", pass: false, out: "" };
function wbBoardBg() {
  if (wbBoardBgCache.pass) return wbBoardBgCache.out;
  const el = document.getElementById("whiteboard-container");
  if (!el) return "";
  const root = document.documentElement;
  let sig = el.style.getPropertyValue("--wb-board-bg");
  for (const attr of root.attributes) sig += `|${attr.name}=${attr.value}`;
  if (wbBoardBgCache.sig !== sig) Object.assign(wbBoardBgCache, { sig, value: getComputedStyle(el).backgroundColor });
  //: Transparent says nothing about the board: no remap.
  return (wbBoardBgCache.out = /,\s*0\)$/.test(wbBoardBgCache.value) ? "" : wbBoardBgCache.value);
}

function wbDeleteFailed(entry, redoBefore, e, retry) {
  wbDropUndoEntry(entry);
  if (!wbRedoStack.length) wbRedoStack = redoBefore;
  wbUpdateUndoRedoButtons();
  toast(voiceLine("failed", { what: "delete that" }), true, { action: ["Try again", retry] });
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

function wbPushUndo(entry) {
  wbHistoryFor();
  //: A lane marked Stack stacks its children after any change; the moves join this step (outside a gesture, which does it itself).
  if (wbRecordDepth === 0) entry = wbBoardState.lane?.settle(entry) || entry;
  wbUndoStack.push(entry);
  if (wbUndoStack.length > WB_UNDO_MAX) wbUndoStack.shift();
  // A fresh action makes whatever redo history existed unreachable, the
  // same rule the sketch pad's own `sketchSaveSnapshot` already follows.
  wbRedoStack = [];
  wbUpdateUndoRedoButtons();
}

//: **Restored topics have new ids, so every history entry that names an old
//: one is rewritten** (INBOX 445, second audit). A branch deleted and then
//: brought back by Undo is made again by `POST`, which hands out fresh ids; an
//: older entry ("undo the creation of topic 7", "put topic 7 back under 3")
//: still said 7 and went to a row that no longer existed, so one more Ctrl+Z
//: after a restore failed or did nothing. Called by `wbMapRestoreRows` with the
//: ids it just minted, over both stacks, and over a link's two ends because a
//: link sketch names its topics by id as well. Original ids cannot be reused
//: instead: the create route assigns them.
//: Cards and shapes too (INBOX 537): a link names a card or a shape by id as
//: well, and a card brought back by Undo is a new row like any other.
//: **Each id is translated once per Undo or Redo** (INBOX 898, found by the
//: live check: Ctrl+Z, Ctrl+Shift+Z, Ctrl+Z on a Mermaid import left a shape
//: behind). Items brought back are new rows, and the table hands out the ids it
//: has free, which are often the very ids that were just deleted: topic 9 comes
//: back as 8 and topic 8 as 9. Applied one item at a time, a step that named 9
//: was changed to 8 and then, by the next item, to 9 again. Every field that
//: has been translated is remembered here until the history step is over, and
//: is not translated a second time.
let wbRemapSeen = new WeakMap();

function wbRemapUndoIds(objects, sketches = new Map(), nodes = new Map()) {
  if (!objects.size && !sketches.size && !nodes.size) return;
  //: A single translation outside a batch has nothing to collide with.
  if (!wbHistoryInFlight.length) wbRemapSeen = new WeakMap();
  const obj = (id) => (objects.has(id) ? objects.get(id) : id);
  const sketch = (id) => (sketches.has(id) ? sketches.get(id) : id);
  const node = (id) => (nodes.has(id) ? nodes.get(id) : id);
  const byKind = { object: obj, sketch, node };
  const once = (holder, key, map) => {
    let keys = wbRemapSeen.get(holder);
    if (!keys) wbRemapSeen.set(holder, (keys = new Set()));
    if (keys.has(key)) return;
    const was = holder[key];
    holder[key] = map(was);
    if (holder[key] !== was) keys.add(key);
  };
  //: A link names its two topics, cards or shapes inside its JSON.
  const linkEnds = (holder) => {
    const text = holder.data;
    if (typeof text !== "string" || !text.includes("link-")) return;
    try {
      const data = JSON.parse(text);
      if (!data || typeof data !== "object" || !String(data.type || "").startsWith("link-")) return;
      const ends = { sourceId: data.sourceKind, targetId: data.targetKind };
      const done = wbRemapSeen.get(holder) || new Set();
      let changed = false;
      for (const [field, kind] of Object.entries(ends)) {
        if (done.has(`data.${field}`)) continue;
        const mapped = byKind[kind || "node"]?.(data[field]) ?? data[field];
        if (mapped !== data[field]) {
          data[field] = mapped;
          done.add(`data.${field}`);
          changed = true;
        }
      }
      if (changed) {
        holder.data = JSON.stringify(data);
        wbRemapSeen.set(holder, done);
      }
    } catch {
      // Not JSON: nothing to translate.
    }
  };
  const walk = (entry) => {
    if (!entry) return;
    if (entry.action === "batch") {
      entry.entries.forEach(walk);
      return;
    }
    if (entry.kind === "object") {
      if (entry.id != null) once(entry, "id", obj);
      if (entry.parentId != null) once(entry, "parentId", obj);
      if (Array.isArray(entry.ids)) entry.ids.forEach((_, at) => once(entry.ids, at, obj));
      for (const row of entry.rows || []) {
        once(row, "id", obj);
        if (row.parent_id != null) once(row, "parent_id", obj);
      }
    }
    if (entry.kind === "sketch" && entry.id != null) once(entry, "id", sketch);
    if (entry.kind === "node" && entry.id != null) once(entry, "id", node);
    for (const key of ["payload", "before"]) {
      if (entry.kind === "sketch" && entry[key]) linkEnds(entry[key]);
    }
    for (const link of entry.links || []) {
      once(link, "id", sketch);
      linkEnds(link);
    }
  };
  wbUndoStack.forEach(walk);
  wbRedoStack.forEach(walk);
  for (const list of wbHistoryInFlight) list.forEach(walk);
}

//: The steps of a batch being replayed right now, and the reverses it has made
//: so far (`wbApplyHistoryEntry`), so an id remap reaches them too.
const wbHistoryInFlight = [];

//: **One gesture, one Undo step, read off what it changed** (INBOX 537: "the
//: undo and redo across the application needs to cover EVERYTHING"). A
//: gesture in `WB_RECORDED` (the end of this file) snapshots every row and the
//: map's settings, runs, and pushes the difference as one batch in place of
//: whatever it pushed itself, so a write nobody recorded by hand (a fold, a
//: tidy, a parent unfolded on the way, a theme) cannot be left out.
let wbRecordDepth = 0;

function wbBoardRows() {
  const rows = new Map();
  for (const kind of ["node", "sketch", "object"]) {
    const { list, payload } = WB_KIND_INFO[kind];
    for (const item of wbState?.[list] || []) {
      rows.set(`${kind}:${item.id}`, { kind, id: item.id, parent: item.parent_id ?? null, json: JSON.stringify(payload(item)) });
    }
  }
  return rows;
}

function wbBoardSettings() {
  const s = wbIsMap() ? window.wbMapState : null;
  return s ? JSON.stringify({ layout: s.layout ?? null, numbered: Boolean(s.numbered), theme: s.theme || {} }) : null;
}

const wbIsLinkRow = (row) => row.kind === "sketch" && /"type"\s*:\s*"link-/.test(JSON.parse(row.json).data || "");

//: The steps that take the board from now back to `was`, in the order that
//: works: lost rows back first (a map's topics as one branch, parents first),
//: then topics back under their old parents (all lifted to the top first when
//: several moved, so no step can make a ring `/move` refuses), then what the
//: gesture made goes (links first, children before parents), then every
//: changed row is written back whole.
function wbHistoryFromRows(was, wasBoard) {
  const now = wbBoardRows();
  const lost = [], made = [], reparent = [], change = [];
  for (const [key, row] of was) {
    const cur = now.get(key);
    if (!cur) { lost.push(row); continue; }
    if (cur.json !== row.json) change.push({ action: "move", kind: row.kind, id: row.id, before: JSON.parse(row.json) });
    if (row.kind === "object" && cur.parent !== row.parent) reparent.push(row);
  }
  for (const [key, row] of now) if (!was.has(key)) made.push(row);
  const steps = [];
  const board = wbBoardSettings();
  if (board !== wasBoard && wasBoard) steps.push({ action: "board", before: wasBoard });
  const isTopic = (row) => row.kind === "object" && WB_MAP_KINDS.has(JSON.parse(row.json).kind) && wbIsMap();
  const topics = lost.filter(isTopic).map((row) => ({ ...JSON.parse(row.json), id: row.id, parent_id: row.parent }));
  const byId = new Map(topics.map((t) => [t.id, t]));
  const depth = (t, n = 0) => (n < 500 && byId.has(t.parent_id) ? depth(byId.get(t.parent_id), n + 1) + 1 : 0);
  topics.sort((a, b) => depth(a) - depth(b));
  if (topics.length) steps.push({ action: "subtree", kind: "object", rows: topics, links: [] });
  const restore = lost.filter((row) => !isTopic(row)).sort((a, b) => wbIsLinkRow(a) - wbIsLinkRow(b));
  for (const row of restore) steps.push({ action: "delete", kind: row.kind, payload: JSON.parse(row.json), oldId: row.id });
  if (reparent.length > 1) for (const row of reparent) steps.push({ action: "reparent", kind: "object", id: row.id, parentId: null });
  for (const row of reparent) steps.push({ action: "reparent", kind: "object", id: row.id, parentId: row.parent });
  const order = { sketch: 0, node: 1, object: 2 };
  const madeDepth = (row) => { let d = 0, p = row.parent; while (p != null && d < 500) { d += 1; p = now.get(`object:${p}`)?.parent ?? null; } return d; };
  made.sort((a, b) => wbIsLinkRow(b) - wbIsLinkRow(a) || order[a.kind] - order[b.kind] || madeDepth(b) - madeDepth(a));
  for (const row of made) steps.push({ action: "create", kind: row.kind, id: row.id });
  return [...steps, ...change];
}

async function wbRecordGesture(run, args = []) {
  if (wbRecordDepth > 0 || !wbState) return run(...args);
  wbHistoryFor();
  const boardId = window.currentBoardId;
  const rows = wbBoardRows();
  const board = wbBoardSettings();
  const had = new Set(wbUndoStack);
  wbRecordDepth += 1;
  try {
    const out = await run(...args);
    await wbBoardState.lane?.settleNow();
    return out;
  } finally {
    wbRecordDepth -= 1;
    if (window.currentBoardId === boardId) {
      //: A note's own steps cannot be read off the board's rows, so they stay.
      const notes = [];
      for (let i = wbUndoStack.length - 1; i >= 0; i -= 1) {
        if (had.has(wbUndoStack[i])) continue;
        const [inner] = wbUndoStack.splice(i, 1);
        if (/^note/.test(inner.action || "")) notes.unshift(inner);
      }
      const steps = [...wbHistoryFromRows(rows, board), ...notes];
      if (steps.length) wbPushUndo(steps.length === 1 ? steps[0] : { action: "batch", entries: steps });
      else wbUpdateUndoRedoButtons();
    }
  }
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

onSurface("board", () => {
  const board = document.getElementById("whiteboard-container");
  const reach = (e) => {
    const el = e.target?.closest?.(".wb-object, .node-card");
    if (el) wbEnsureHandles(el);
  };
  board?.addEventListener("pointerover", reach, { passive: true });
  board?.addEventListener("focusin", reach);
});

function wbStableDragContainer(itemSelector) {
  return function () {
    return this.closest(itemSelector)?.parentNode || this.parentNode;
  };
}

// whiteboard-textedit.js: whiteboard-textedit.js: the text box and sticky editor, runs, text style bar and (moved out, L286).
//: The parents of the topics one Undo took away, in the order they went. A
//: batch (a duplicated branch) removes several, and most of their parents go
//: with them, so `wbUndo` picks the first that is still on the board.
let wbUndoParents = [];
// whiteboard-comments.js: whiteboard-comments.js: comments threads, item links and their marks on the boar (moved out, L286).
let wbCommentState = null;
// whiteboard-frames.js: whiteboard-frames.js: frames: create, fit, turn, title, draw (decision 14). (moved out, L286).
const WB_PLACE_MIN = { text: { w: 60, h: 32 }, sticky: { w: 80, h: 60 }, frame: { w: 120, h: 80 } };

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
  const container = document.getElementById("whiteboard-container");
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

async function initWhiteboard() {
  surfaceBuild("board");
  if (wbInitialized) return;
  wbInitialized = true;
  
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
    document.getElementById("whiteboard-container")?.classList.toggle("wb-mid-pan", on);
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
  container.node().addEventListener("scroll", wbFoldNativeScroll);
  // Shift+wheel pans sideways; every other wheel is d3-zoom's, by
  // `wbZoomFilter`, which prevents the page scrolling too. `passive: false`
  // here so the page behind the board does not scroll on a shifted wheel.
  if (!container.node().dataset.wbWheelPan) {
    container.node().dataset.wbWheelPan = "1";
    container.node().addEventListener("wheel", (e) => {
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
      const k = d3.zoomTransform(container.node()).k || 1;
      const unit = e.deltaMode === 1 ? 16 : e.deltaMode === 2 ? 400 : 1;
      let dx = e.deltaX * unit, dy = e.deltaY * unit;
      //: Shift+wheel on a mouse turns the notch sideways; a trackpad scroll
      //: already carries both axes and keeps them.
      if (!dx && !wbTrackpadPan(e)) { dx = dy; dy = 0; }
      container.call(wbZoom.translateBy, -dx / k, -dy / k);
    }, { passive: false });
  }
  
  // Toolbar hooks
  document.getElementById("wb-zoom-in").addEventListener("click", () => wbZoomStep(1.2, { duration: 250, usePointer: false }));
  document.getElementById("wb-zoom-out").addEventListener("click", () => wbZoomStep(0.8, { duration: 250, usePointer: false }));
  // Was `wbZoom.transform(d3.zoomIdentity)`, a reset to 100% at the origin,
  // under a button labelled "Fit to Screen". See `wbZoomToFit`.
  document.getElementById("wb-zoom-fit").addEventListener("click", () => wbZoomToFit());
  //: The level is a typeable field (value-field.js); drawn now, since the markup holds only its host.
  wbShowZoomLevel(d3.zoomTransform(document.getElementById("whiteboard-container")).k || 1);

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
      toast(err.message || voiceLine("failed", { what: "rename that board" }), true);
    }
  });
  $("wb-map-layout")?.addEventListener("change", (e) => wbMapSetLayout(e.target.value));
  $("wb-map-link-style")?.addEventListener("change", (e) => wbMapSetLinkStyle(e.target.value));
  for (const type of ["pointerover", "focusin"]) {
    $("whiteboard-container")?.addEventListener(type, (e) => {
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
        document.getElementById("whiteboard-container")?.focus({ preventScroll: true });
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
      container.node().style.setProperty("--wb-board-bg", e.target.value);
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
        panel.dispatchEvent(new Event("wb-panel-resize"));
        // A hidden panel measures 0, and a 0 here would collapse the offset
        // of whatever is clearing it right on top of the panel above. The
        // CSS fallbacks stay in charge until there is a real size to use.
        if (box.height > 0) wbPanelMetricsRoot.style.setProperty(`--wb-h-${name}`, `${Math.round(box.height)}px`);
        // The tools panel's width is read back by its own side-dock rule
        // (`width: var(--wb-w-tools)`), so a width taken while it lay along the
        // bottom (758px at 768) became the side column's width.
        if (box.width > 0 && (name !== "tools" || panel.dataset.dock === "side")) wbPanelMetricsRoot.style.setProperty(`--wb-w-${name}`, `${Math.round(box.width)}px`);
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
      toast(err.message || voiceLine("failed", { what: "set that background image" }), true);
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
  let isDrawing = false;
  let currentDrawPath = null;
  let currentDrawData = []; // array of [x, y]
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
  let WB_STROKE_WIDTH = Number(prefs.get("wb-stroke-width", null)) || 3;
  const strokeWidthInput = document.getElementById("wb-stroke-width");
  const strokeWidthBadge = document.getElementById("wb-stroke-width-badge");
  let strokeWidthBadgeTimer = null;
  function showStrokeWidthBadge() {
    if (!strokeWidthBadge || !strokeWidthInput) return;
    const r = strokeWidthInput.getBoundingClientRect();
    strokeWidthBadge.textContent = `${WB_STROKE_WIDTH}px`;
    strokeWidthBadge.style.left = `${r.left + r.width / 2}px`;
    strokeWidthBadge.style.top = `${r.top - 8}px`;
    strokeWidthBadge.classList.remove("hidden");
    clearTimeout(strokeWidthBadgeTimer);
    strokeWidthBadgeTimer = setTimeout(() => strokeWidthBadge.classList.add("hidden"), 900);
  }
  if (strokeWidthInput) {
    strokeWidthInput.value = String(WB_STROKE_WIDTH);
    strokeWidthInput.addEventListener("input", (e) => {
      WB_STROKE_WIDTH = Number(e.target.value) || 3;
      prefs.set("wb-stroke-width", String(WB_STROKE_WIDTH));
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
    const headLen = (parsed.width || WB_STROKE_WIDTH) * 4 + 6;
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

  const containerEl = document.getElementById("whiteboard-container");
  const undoBtn = document.getElementById("wb-undo");

  function updateWbCursor() {
    containerEl.setAttribute("data-current-tool", window.currentTool);
    containerEl.style.cursor = wbCursorForTool(window.currentTool, window.currentStrokeColor, WB_STROKE_WIDTH);
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
    wbAbandonStroke();
    wbDropLostGesture();
    window.currentTool = tool;
    //: A link tool's anchor dots belong to that tool (INBOX 573).
    if (!String(tool).startsWith("link-") && !wbLinkDragActive) wbClearAnchorHints();
    if (toolGroup) {
      toolGroup.querySelectorAll("button[data-tool]").forEach((b) => {
        b.classList.toggle("active", b.dataset.tool === tool);
      });
    }
    // The zoom behaviour stays attached for every tool. It used to be
    // detached for all but Pan so a drag could not fight drawing, but
    // `wbZoomFilter` (top of file) now makes that decision per event, and
    // detaching also removed **wheel zoom**, so you could not zoom or scroll
    // the canvas while any drawing tool was selected without switching tool
    // and switching back. That was a large part of the reported "constantly
    // having to switch between tools".
    container.call(wbZoom).on("dblclick.zoom", null);
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
    wbToolsOpenerSyncRef?.();
    updateWbCursor();
    wbFmtState.hints?.toolHint(tool);
    wbFmtState.effects?.refreshStatus();
    // The properties panel now also carries the style a drawing tool will
    // use, so a tool switch has to reopen/close it, see its own comment.
    wbUpdateContextBar();
  }

  wbSelectToolRef = selectWbTool;

  if (toolGroup) {
    toolGroup.addEventListener("click", (e) => {
      const btn = e.target.closest("button[data-tool]");
      if (btn) selectWbTool(btn.dataset.tool);
    });
  }

  // --- the tools as a sheet on a phone ---------------------------------------
  // UI_MODERNISATION_PLAN Phase 11 item 7, "creation tools in a sheet".
  // Measured at 390x844 first: the rail is a 364x56 band under a 364x604
  // canvas, and the band holds 835px of tools scrolled through a 358px
  // window, so 16 of its 31 buttons were on screen at once and the Shapes
  // section showed one of its seven. A row you scroll sideways to find a tool
  // in is not a palette, and it is 56px of a 844px screen either way.
  //
  // What opens is `openSheet`, and what is in it is `#wb-tool-group` itself,
  // moved in and put back on close. That is the whole design: the delegated
  // `[data-tool]` listener above, every section label, every key and the
  // shape menu are the ones that were already there, so a tool added to the
  // rail is in the sheet without anybody remembering to add it twice.
  let wbToolsSheetClose = null;
  let wbToolsWords = [];
  const toolsOpener = document.getElementById("wb-tools-opener");

  function wbSyncToolsOpener() {
    const label = document.getElementById("wb-tools-opener-label");
    if (!label || !toolGroup) return;
    //: The opener says which tool is in hand, because on a phone it is the
    //: only place the rail's own "active" mark can be read.
    const active = toolGroup.querySelector("button[data-tool].active");
    //: The key in brackets is for a keyboard; on a phone it read "Select (V)".
    const name = (active?.getAttribute("aria-label") || active?.title || "").split(" (")[0];
    label.textContent = name ? name.replace(/ tool$/i, "") : "Tools";
  }

  function wbOpenToolsSheet() {
    if (wbToolsSheetClose || !toolGroup || typeof openSheet !== "function") return;
    const home = { parent: toolGroup.parentNode, next: toolGroup.nextSibling };
    toolsOpener?.setAttribute("aria-expanded", "true");
    wbToolsSheetClose = openSheet({
      label: "Tools",
      name: "wb-tools",
      returnFocus: toolsOpener,
      build: (card, close) => {
        const body = document.createElement("div");
        body.className = "wb-tools-palette";
        body.appendChild(toolGroup);
        card.appendChild(body);
        //: **A word under every icon** (audit 1028 U21: 31 icon-only tiles, and
        //: a touch screen has no tooltip to ask). The word is the button's own
        //: name without its key, so the accessible name still contains it (WCAG
        //: 2.5.3), and it is taken out again on close: the rail above 600px is
        //: icons by design.
        for (const button of toolGroup.querySelectorAll("button[aria-label], button[title]")) {
          if (button.textContent.trim()) continue;
          const full = (button.getAttribute("aria-label") || button.title || "").replace(/\s*\(.*$/, "").replace(/ tool$/i, "").trim();
          // A name too long for one line of a tile gets its short word; the short word is still inside the full name.
          const short = {
            "Upload an image onto the board": "Image",
            "Emoji and icons": "Emoji",
            "Lasso select": "Lasso",
            "Sticky note": "Sticky",
            "Straight link": "Straight",
            "Curved link": "Curved",
          };
          const name = short[full] || full;
          if (!name) continue;
          const word = document.createElement("span");
          word.className = "wb-tool-word";
          word.textContent = name;
          button.appendChild(word);
          button.classList.add("wb-tool-worded");
          wbToolsWords.push(word);
        }
        //: Picking a tool is the end of the errand, so the sheet gets out of
        //: the way and the board is there to draw on. The `close` the recipe
        //: hands `build`, not the variable the call assigns afterwards, and
        //: bound on the card so it cannot outlive the sheet.
        //:
        //: **Captured**, because the shape menu's rows stop their own click
        //: from bubbling (they have to: a docked menu is reparented to
        //: `<body>` while it is open, so it cannot rely on reaching
        //: `#wb-tool-group`'s delegated listener). Measured: picking
        //: Rectangle set the tool and left the sheet open over the board it
        //: had just been chosen for.
        card.addEventListener(
          "click",
          (event) => {
            if (event.target.closest("button[data-tool]")) close();
          },
          true
        );
      },
      onClose: () => {
        for (const word of wbToolsWords) {
          word.parentElement?.classList.remove("wb-tool-worded");
          word.remove();
        }
        wbToolsWords = [];
        home.parent.insertBefore(toolGroup, home.next);
        wbToolsSheetClose = null;
        toolsOpener?.setAttribute("aria-expanded", "false");
        wbSyncToolsOpener();
      },
    });
  }

  if (toolsOpener) {
    toolsOpener.addEventListener("click", () => {
      if (wbToolsSheetClose) wbToolsSheetClose();
      else wbOpenToolsSheet();
    });
    //: A window dragged past the band with the sheet open would leave the
    //: rail's own tools inside a dialog the desktop layout has no opener for.
    WB_PHONE.addEventListener("change", () => wbToolsSheetClose?.());
    wbSyncToolsOpener();
    wbToolsOpenerSyncRef = wbSyncToolsOpener;
  }

  // Docked as a sidebar, the toolbar panel scrolls (`overflow-y: auto`, so a
  // tall tool column fits above the canvas), three attempts at this,
  // reported directly each time: (1) CSS-only positioning was clipped by
  // that same overflow (setting only `overflow-y` coerces `overflow-x` to
  // `auto` too, clipping both axes, a real CSS rule, not a bug in that one
  // declaration). (2) `position: fixed` should escape an ancestor's overflow
  // entirely, but this panel's `.glass` class sets `backdrop-filter`, which: 
  // like `transform`/`filter`, creates a new containing block for fixed
  // descendants and traps them right back inside it. (3) toggling the whole
  // panel's `overflow` to `visible` while a menu was open avoided the clip,
  // but also uncapped the tool column's own `max-height` for as long as the
  // menu stayed open, spilling tools out past the panel's bottom edge with
  // no scrollbar to reach them.
  //
  // The only thing that both escapes the clip *and* leaves the scrolling
  // tool column alone is not being inside it: the open menu is reparented to
  // <body> (remembering where it came from, to put it back on close) and
  // positioned from the toggle's own `getBoundingClientRect()`, same as any
  // popover library would. Its own click listener below (rather than relying
  // on bubbling to #wb-tool-group's delegated one) is what makes that safe, 
  // a tool button click needs to work identically whether the menu is
  // sitting in its normal spot (bottom-docked) or reparented to <body>
  // (side-docked, open).
  function wbOpenDockedMenu(menu, toggle) {
    menu.classList.remove("hidden");
    toggle.setAttribute("aria-expanded", "true");
    const panel = toggle.closest(".whiteboard-floating-panel");
    if (panel?.dataset.dock === "side" && !menu._wbHome) {
      menu._wbHome = { parent: menu.parentNode, next: menu.nextSibling };
      document.body.appendChild(menu);
      const toggleRect = toggle.getBoundingClientRect();
      menu.style.position = "fixed";
      menu.style.left = `${toggleRect.right + 8}px`;
      menu.style.top = `${toggleRect.top}px`;
      menu.style.bottom = "auto";
      menu.style.transform = "none";
      menu.style.zIndex = "200";
      // The menu can be bigger than the toggle it opened from, the shape
      // menu's fill/stroke/guide-colour rows run well past the toolbar's
      // own height, and a toggle near the bottom of a tall docked column
      // put `top: toggleRect.top` most of the way down the screen already.
      // Reported directly ("go out of the window"). Clamped against the
      // real viewport rather than just the toggle's position: measured
      // after being placed, since its actual rendered size isn't known
      // until it's in the DOM and visible.
      const margin = 8;
      const menuRect = menu.getBoundingClientRect();
      if (menuRect.right > window.innerWidth - margin) {
        menu.style.left = `${Math.max(margin, window.innerWidth - menuRect.width - margin)}px`;
      }
      if (menuRect.bottom > window.innerHeight - margin) {
        menu.style.top = `${Math.max(margin, window.innerHeight - menuRect.height - margin)}px`;
      }
    }
    wbLiftMenuOffOptionsBar(menu);
  }

  //: **A tool's kind popover and its options bar are one surface, not two
  //: that cross** (INBOX 823, the owner's screenshot: the Line and Arrow
  //: choice drawn under the bar holding Size, Plain and Solid). Measured at
  //: 1440 (`scratchpad/ui-sweeps/toolpop.js`): the popover (z 20) sat 6,232px2
  //: under the bar (z 22) it opens next to. Lifted clear of the bar, an 8px
  //: gap above it, with the individual `translate` property so it composes
  //: with whichever placement the dock gave it.
  function wbLiftMenuOffOptionsBar(menu) {
    menu.style.translate = "";
    const bar = document.getElementById("wb-context");
    if (!bar || bar.classList.contains("hidden")) return;
    const b = bar.getBoundingClientRect();
    const m = menu.getBoundingClientRect();
    if (!b.width || !m.width) return;
    const across = m.left < b.right && m.right > b.left && m.top < b.bottom && m.bottom > b.top;
    if (across) menu.style.translate = `0 ${Math.round(b.top - 8 - m.bottom)}px`;
  }

  function wbCloseDockedMenu(menu, toggle) {
    menu.classList.add("hidden");
    toggle.setAttribute("aria-expanded", "false");
    if (menu._wbHome) {
      menu._wbHome.parent.insertBefore(menu, menu._wbHome.next);
      menu._wbHome = null;
      menu.style.position = "";
      menu.style.left = "";
      menu.style.top = "";
      menu.style.bottom = "";
      menu.style.transform = "";
      menu.style.zIndex = "";
    }
    menu.style.translate = "";
  }

  // Asked for directly: a plain click/tap on the toggle's icon selects the
  // tool it's already showing (matching every other toolbar button, and
  // matching what the toggle looks like it should do). The picker only
  // opens from the caret, a right-click, a double-click, or, touch has
  // neither of those: holding the tool down.
  //: **The caret is a target** (OPEN row 847): it had `pointer-events: none`,
  //: so its own test never matched and a click on it picked the tool. It is
  //: 10px across, so the toggle's right 14px count as the caret too; a
  //: keyboard press (no pointer, `detail` 0) still picks the tool.
  function wbToggleCaretHit(toggle, e) {
    const caret = toggle.querySelector(".wb-shape-caret");
    if (!caret) return false;
    if (e.target.closest(".wb-shape-caret")) return true;
    return e.detail > 0 && e.clientX >= toggle.getBoundingClientRect().right - 14;
  }
  function wbWireToggleGestures(toggle, menu, getLastTool) {
    if (!toggle || !menu) return;
    const picker = toggle.parentElement; // #wb-shape-picker / #wb-select-picker
    toggle.addEventListener("click", (e) => {
      e.stopPropagation();
      if (wbToggleCaretHit(toggle, e)) {
        if (menu.classList.contains("hidden")) wbOpenDockedMenu(menu, toggle);
        else wbCloseDockedMenu(menu, toggle);
      } else {
        //: A press on the control that opened the list shuts it (INBOX 681), and
        //: still picks the tool the button shows.
        if (!menu.classList.contains("hidden")) wbCloseDockedMenu(menu, toggle);
        selectWbTool(getLastTool());
      }
    });
    toggle.addEventListener("dblclick", (e) => {
      e.stopPropagation();
      wbOpenDockedMenu(menu, toggle);
    });
    //: The right-click and the hold open the list and, pressed again, shut it.
    const toggleDocked = () => {
      if (menu.classList.contains("hidden")) wbOpenDockedMenu(menu, toggle);
      else wbCloseDockedMenu(menu, toggle);
    };
    toggle.addEventListener("contextmenu", (e) => {
      e.preventDefault();
      e.stopPropagation();
      toggleDocked();
    });
    //: The hold, through the app's own `wireLongPress` (navigation.js) rather than
    //: a fourth copy of a 500ms timer with its own cancel set. It also
    //: removes the `suppressClick` latch this carried: the recipe swallows
    //: the click the lift synthesises, which is the thing that latch was
    //: written to survive, and a latch that is only cleared by the *next*
    //: click is a click lost whenever no click follows.
    wireLongPress(toggle, toggleDocked);
    //: **And from the keyboard.** Enter on the toggle picks the tool it shows
    //: (the click above), and the caret, the right-click, the double-click
    //: and the hold are all pointer gestures, so a keyboard had no way into
    //: the shapes at all (menus.js: "nothing opened"). ArrowDown and ArrowUp
    //: are the menu button's own keys (WAI-ARIA): open, and land on the
    //: first or last shape; the menu's own arrows and Escape take it from
    //: there.
    toggle.setAttribute("aria-controls", menu.id);
    //: The roles at boot, never in the markup (the rule `wbStampMenuRoles`
    //: keeps for the top-bar menus): a `role="menu"` with no menuitems in it
    //: is announced as an empty menu, and `wireMenuKeyboard` walks menuitems.
    for (const group of menu.querySelectorAll(".wb-shape-menu-group")) group.setAttribute("role", "group");
    for (const item of menu.querySelectorAll("button[data-tool]")) item.setAttribute("role", "menuitem");
    wireMenuKeyboard(menu, toggle);
    //: `wireMenuKeyboard`'s Escape closes `.action-menu`s, which this is not,
    //: and it stops the key there, so the board's own Escape never saw it
    //: either: measured, Escape left the shapes open (menus.js at 1024).
    menu.addEventListener("keydown", (e) => {
      if (e.key !== "Escape" || menu.classList.contains("hidden")) return;
      wbCloseDockedMenu(menu, toggle);
      toggle.focus({ preventScroll: true });
    });
    toggle.addEventListener("keydown", (e) => {
      if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
      if (!menu.classList.contains("hidden")) return;
      e.preventDefault();
      wbOpenDockedMenu(menu, toggle);
      const items = [...menu.querySelectorAll('[role="menuitem"], button')].filter(
        (b) => !b.disabled && b.getClientRects().length > 0
      );
      (e.key === "ArrowDown" ? items[0] : items[items.length - 1])?.focus();
    });

    // Handled directly rather than relying on the click bubbling up to
    // #wb-tool-group's own delegated listener: once open+side-docked, the
    // menu is reparented to <body> (see wbOpenDockedMenu) and is no longer
    // a descendant of #wb-tool-group at all, so that bubbling path stops
    // reaching it. stopPropagation here is what it is safe now, unlike the
    // old bottom-docked-only version of this handler, this is the only
    // listener that will ever see the click, in either dock mode.
    menu.addEventListener("click", (e) => {
      const btn = e.target.closest("button[data-tool]");
      if (btn) {
        e.stopPropagation();
        selectWbTool(btn.dataset.tool);
      }
    });
    document.addEventListener("click", (e) => {
      if (!menu.classList.contains("hidden") && !picker.contains(e.target) && !menu.contains(e.target)) {
        wbCloseDockedMenu(menu, toggle);
      }
    });
  }

  wbWireToggleGestures(shapeToggle, shapeMenu, () => lastShapeTool);

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
  const wbCanvasEl = () => document.getElementById("whiteboard-container");
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
  container.node()?.addEventListener("pointerdown", (e) => {
    // Any editable body, not the two class names that were editable when
    // this was written: pulling focus to the canvas out from under a map
    // node's editor is the other half of "I cant highlight text in mindmap
    // text boxes", the caret went to the container mid-gesture.
    if (e.target.closest(".whiteboard-floating-panel, [contenteditable=true]")) return;
    document.getElementById("whiteboard-container")?.focus({ preventScroll: true });
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
    if (!container.node()?.contains(e.target)) wbMapKeysArmed = false;
  });

  //: On `window`, capturing, so it runs before the app zoom's own capture
  //: listener on `document` (settings-panes.js) and can stop it.
  window.addEventListener("keydown", wbZoomKey, true);
  document.addEventListener("keydown", (e) => {
    if (typeof e.key !== "string") return; // a keydown with no key (see the ring's handler above)
    const view = document.getElementById("library-view-whiteboard");
    if (!view || view.classList.contains("hidden")) return;
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
        const onMap = !at || at === document.body || at.closest?.("#whiteboard-container");
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
        const el = document.querySelector(`.wb-object[data-id="${mapNode.id}"]`);
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

  // Opens in Select, like every whiteboard app, panning is always
  // available on held space and the middle mouse button regardless.
  selectWbTool("select"); // the initial state

  // Drawing event handlers on the SVG itself or container
  const svgCanvas = document.getElementById("wb-svg-layer");

  function getLogicalMouse(e) {
    return wbClientToBoard(e.clientX, e.clientY);
  }
  
  // The eraser doesn't draw: it deletes whatever the pointer crosses while
  // held, which is renderWhiteboard's job (it owns the sketch/node elements
  // this has to hit-test against). All this needs to track is "is the
  // button currently down", on the container so it works over both the SVG
  // sketch layer and the HTML card layer.
  // Pointer events, not mouse events: they unify mouse/touch/pen into one
  // stream, which is what lets a finger draw, erase and pan here at all, 
  // touch never dispatches "mouse*" events reliably, and never dispatches
  // them for a stylus. `touch-action: none` on .whiteboard-container (CSS)
  // is the other half of this: without it the browser eats the gesture for
  // page-scroll before a single pointer event reaches here.
  containerEl.addEventListener("pointerdown", (e) => {
    if (window.currentTool === "eraser") {
      wbErasing = true;
      wbEraseHad = new Set(wbUndoStack);
      // Reported directly: "with the eraser, I can't touch and drag to
      // delete items" (the pen works fine touch-dragged the same way).
      // Touch, unlike a mouse, implicitly captures the pointer to
      // whatever element received this pointerdown, so a dragging finger
      // never fires `pointerenter` on the *other* sketches/cards it passes
      // over; the eraser's per-element `pointerenter` handlers (below) can
      // only ever catch the one thing first touched. Releasing capture
      // explicitly restores normal per-element pointer events for the rest
      // of the gesture, and `pointermove` here (coordinate-based, not
      // target-based) is the second half, it doesn't depend on capture
      // behaving correctly at all, so it also covers browsers/pens where
      // pointerenter is delivered unreliably during a fast drag.
      e.target.releasePointerCapture?.(e.pointerId);
    }
  });
  window.addEventListener("pointerup", () => {
    wbErasing = false;
    wbEraseSettle();
  });
  //: Every sample the browser coalesced into this event is hit-tested, so a
  //: fast finger or pen stroke between two events erases what it crossed
  //: (audit B21); `pointerenter` alone never fires reliably on touch or pen.
  //: One swipe, one Undo step (L-whiteboard-35): each delete pushes its own
  //: entry as it lands, and the swipe's end folds them into one batch.
  let wbEraseHad = null;
  function wbEraseSettle() {
    if (!wbEraseHad) return;
    const had = wbEraseHad;
    wbEraseHad = null;
    const mine = wbUndoStack.filter((entry) => !had.has(entry) && entry.action === "delete");
    if (mine.length < 2) return;
    for (const entry of mine) wbUndoStack.splice(wbUndoStack.indexOf(entry), 1);
    wbPushUndo({ action: "batch", entries: mine });
  }
  function wbEraseAt(clientX, clientY) {
    const el = document.elementFromPoint(clientX, clientY);
    const sketchEl = el?.closest(".sketch-group");
    if (sketchEl) {
      const item = wbState.sketches.find((s) => s.id === Number(sketchEl.dataset.id));
      if (item) wbDeleteSketch(item);
      return;
    }
    const cardEl = el?.closest(".node-card");
    if (cardEl) {
      const item = wbState.nodes.find((n) => n.id === Number(cardEl.dataset.id));
      if (item) wbDeleteNode(item);
      return;
    }
    const objEl = el?.closest(".wb-object");
    if (objEl) {
      const item = (wbState.objects || []).find((o) => o.id === Number(objEl.dataset.id));
      if (item) wbDeleteObject(item);
    }
  }
  containerEl.addEventListener("pointermove", (e) => {
    if (window.currentTool !== "eraser" || !wbErasing) return;
    const samples = e.getCoalescedEvents?.() ?? [];
    for (const p of samples.length ? samples : [e]) wbEraseAt(p.clientX, p.clientY);
  });
  // Clicking empty canvas with Select active clears the selection, every
  // card/sketch's own click handler calls stopPropagation() under Select,
  // so a click that reaches here was never on an item. A completed marquee
  // drag (below) also ends on empty canvas, which fires this same native
  // `click` right afterward (unlike d3.drag, a plain addEventListener drag
  // gets no automatic click-suppression), `wbMarqueeJustSelected` is the
  // one-shot flag that stops it from wiping out the selection the marquee
  // just made.
  containerEl.addEventListener("click", (e) => {
    //: A press on a shape's own grip that did not move is not a click on
    //: the canvas. The grips live in their own handle group rather than in
    //: the shape (see `wbIsEmptyCanvasTarget`), so nothing stopped this
    //: click, and it deselected the shape: the grips vanished under the
    //: pointer, and the second half of a double-click on the rotate grip
    //: landed on bare canvas (measured: the reset never ran).
    if (e.target.closest?.(".wb-sketch-handle-group")) return;
    if (window.currentTool === "select" || window.currentTool === "lasso") {
      if (wbMarqueeJustSelected) {
        wbMarqueeJustSelected = false;
      } else if (window.currentTool === "select" && wbSelectFrameAt(...getLogicalMouse(e), 8 / (d3.zoomTransform(containerEl).k || 1))) {
        // A click on a panel's body or a frame's edge selected that frame.
      } else if (window.currentTool === "select" && wbPointInSelectionBounds(...getLogicalMouse(e))) {
        // A click inside the selection's box is on the selection: it stays.
      } else {
        clearWbSelection();
        // The other half of the Escape fix: a click on empty canvas is the
        // first thing anyone tries on a rectangle that will not go away.
        wbClearSelectionOverlays();
      }
    }
    // A text box is placed by clicking, not dragged like a shape, it has
    // no natural "size while dragging" the way a rect does, so click-to-drop
    // at a sensible default size (typed into afterward) is the same model
    // OneNote and every sticky-note tool already use.
    // No `e.target` check: like the Select-clear branch above, this relies
    // on an item's own click handler having already called stopPropagation()
    // if the click actually landed on a card/sketch/object, a click that
    // reaches here bubbled up from truly empty canvas either way.
    if (wbPlaceJustDrawn) {
      wbPlaceJustDrawn = false;
      return;
    }
    if (window.currentTool === "text") {
      const [x, y] = getLogicalMouse(e);
      wbCreateTextBox(x, y);
    }
    if (window.currentTool === "sticky") {
      const [x, y] = getLogicalMouse(e);
      wbCreateSticky(x, y);
    }
    if (window.currentTool === "frame") {
      const [x, y] = getLogicalMouse(e);
      wbCreateFrame(x, y);
    }
  });

  // Rectangle marquee select: reported directly ("area select... missing").
  // Only engages when the pointerdown target is genuinely empty canvas: a
  // card/sketch/object's own drag already claims the gesture otherwise (the
  // node/object drags' `.filter()`, the sketch drag's own tool check), so
  // checking the target here is enough without a second stopPropagation
  // dance.
  //
  // **The handle layer has to be in this list, and stopPropagation cannot
  // stand in for it.** Reported: "when I adjust things like links, the area
  // select happens too", dragging a link's endpoint drew a selection
  // marquee across the board at the same time. The endpoint handles are not
  // inside `.sketch-group`; they live in their own `.wb-sketch-handle-group`
  // over in `#wb-overlay-zoom-group`, precisely so a card can sit above the
  // base layer without burying them. So they passed this test as empty
  // canvas.
  //
  // Their drag does call `stopPropagation` on d3-drag's "start", and that is
  // why this looked correct. It fires on the wrong event: d3-drag listens for
  // `mousedown`, this listens for `pointerdown`, and a pointerdown is
  // dispatched *before* the compatibility mousedown it generates. By the time
  // the handle stops propagation the marquee has already begun. Two event
  // families cannot cancel each other, so the target check is the only place
  // this can be fixed.
  function wbIsEmptyCanvasTarget(target) {
    // `.sketch-group:not(.wb-link-sketch)`: see the class's own note in the
    // sketch render. A drawn shape claims the gesture (it can be moved by its
    // body); a link cannot be, and its 20px hit band was swallowing the
    // marquee wherever a connector crossed the canvas.
    return wbIsBareCanvas(target);
  }
  function rectsIntersect(ax, ay, aw, ah, bx, by, bw, bh) {
    return ax < bx + bw && ax + aw > bx && ay < by + bh && ay + ah > by;
  }
  let wbMarqueeStart = null;
  //: One-shot, the placing twin of `wbMarqueeJustSelected`: a drawn text box
  //: or sticky spends the canvas click its own release makes.
  let wbPlaceJustDrawn = false;
  let wbMarqueeEl = null;
  let wbMarqueeJustSelected = false;
  //: The latest pointer position (board units) and the frame that will draw
  //: it, so a burst of moves inside one frame is one write (`wbDrawMarquee`).
  let wbMarqueeAt = null;
  let wbMarqueeFrame = 0;
  let wbMarqueeInk = "";
  //: End the marquee gesture and take its rectangle off the canvas. Every
  //: exit from the drag goes through here, the completed one, the cancelled
  //: one, and the sweep `wbClearSelectionOverlays` runs, so there is exactly
  //: one place that can forget to remove the element.
  function wbEndMarqueeDrag() {
    if (wbMarqueeStart?.place) wbClearAlignmentGuides();
    //: A selection drag cut off (cancelled, capture lost) goes back where it
    //: was; one that ended normally cleared `wbMarqueeStart` first.
    if (wbMarqueeStart?.move && wbMarqueeStart.origin) {
      wbApplyBulkMove(wbMarqueeStart.origin, 0, 0);
      for (const entry of wbMarqueeStart.origin.values()) delete entry.item._liveD;
    }
    wbMarqueeEl?.remove();
    wbMarqueeEl = null;
    wbMarqueeStart = null;
    if (wbMarqueeFrame) cancelAnimationFrame(wbMarqueeFrame);
    wbMarqueeFrame = 0;
    wbMarqueeAt = null;
  }
  containerEl.addEventListener("pointerdown", (e) => {
    //: A new press is a new gesture: a one-shot left by a drag released off
    //: the board (no click ever reached the canvas to spend it) must not
    //: swallow this press's click.
    wbMarqueeJustSelected = false;
    wbPlaceJustDrawn = false;
    //: **The text and sticky tools draw their box too** (the owner,
    //: 2026-09-24: "I cant drag to create a custom sized textbox on the
    //: whiteboard when selected on the textbox tool", "same with the sticky
    //: notes"). A click still drops the default size (the canvas `click`
    //: below); a press that travels draws the box it will make, with the
    //: marquee's own dashed rectangle and the same 4-unit threshold, so the
    //: two gestures cannot disagree about where a click ends and a drag
    //: begins.
    //: And the frame tool (decision 14), the same two gestures.
    const place = ["text", "sticky", "frame"].includes(window.currentTool) ? window.currentTool : null;
    if ((window.currentTool !== "select" && !place) || !wbIsEmptyCanvasTarget(e.target)) return;
    //: A finger on bare canvas with Select pans (`wbZoomFilter`), so it is
    //: not also the start of an area select.
    if (!place && e.pointerType === "touch") return;
    // Primary button only. A right-click opens the context menu and a middle
    // click pans; neither ends with the pointerup this drag is waiting for,
    // so both used to start a rectangle that nothing would ever remove.
    if (e.button !== 0 || !e.isPrimary) return;
    // A gesture already in flight loses its rectangle rather than orphaning
    // it: `wbMarqueeEl` is one variable, so a second pointerdown overwrote
    // the reference to the first rect and left it on the canvas forever.
    wbEndMarqueeDrag();
    const [x, y] = getLogicalMouse(e);
    //: **Nothing is claimed until the pointer actually travels.** The
    //: rectangle and the pointer capture used to be taken here, on the press,
    //: and a capture re-targets the compatibility `click` at the capturing
    //: element: harmless while this only ever began over bare canvas, fatal
    //: the moment it also begins over a link (see `wbIsEmptyCanvasTarget`),
    //: because the link's own click, which is what selects it, was delivered
    //: to the container instead and a connector could no longer be clicked.
    //: Deferring both to the first real movement keeps the press a press: a
    //: click reaches whatever was under it, and a drag is still a drag from
    //: the point it started at.
    //: A press inside the selection's box drags the selection (Shift adds to
    //: it, so that press stays a marquee).
    const move = !place && !e.shiftKey && window.currentTool === "select" && wbPointInSelectionBounds(x, y);
    wbMarqueeStart = { x, y, shiftKey: e.shiftKey, pointerId: e.pointerId, pending: true, place, move };
    //: **The overlay layer, above the cards.** INBOX 84: "whiteboard
    //: rectangle selection draws behind objects." `#wb-zoom-group` lives in
    //: `#wb-svg-layer`, which is *under* `#wb-html-layer` by DOM order, on
    //: purpose, so a pen stroke passes behind a card. A marquee is the
    //: opposite case: it says what you are about to select, and a rectangle
    //: hidden behind the very things it is selecting says nothing. The lasso
    //: has always gone to `#wb-overlay-zoom-group` for exactly this reason
    //: (see its own append below); the rectangle never did.
  });
  //: The rectangle itself, made on the first movement past the threshold the
  //: completed gesture is judged by anyway. Split out so both the press and
  //: the move can read it.
  //: **Drawn on the compositor, once a frame** (INBOX 410: "drag selection on
  //: the whiteboard and mindmap is laggy as well"). The rectangle was an SVG
  //: `<rect>` in the overlay layer whose four attributes were rewritten on
  //: every pointermove. Each rewrite changed a paint chunk's bounds, and a
  //: changed chunk makes Chrome re-layerize the whole page, whose cost grows
  //: with everything on the board: traced over one 80-move drag
  //: (`scratchpad/ui-sweeps/marqueeperf.js`), Layerize took 1275ms on a board
  //: of 200 text boxes and 616ms on a map of 200 topics, with frames of 50ms
  //: at the 95th percentile and 83ms at worst.
  //:
  //: **Not a DOM change at all: a canvas.** The obvious fix, five 1px boxes
  //: moved by `transform` on layers of their own, was measured first and
  //: is not one: on a map of 200 topics, 60 frames of transform writes cost
  //: 419ms of Layerize, the same as 60 frames of `<rect>` attribute writes
  //: (445ms), because any style or attribute change re-layerizes a page this
  //: size. 60 frames of drawing on a canvas cost 8.7ms. So the rectangle is
  //: drawn on a canvas the size of the container, made when the drag starts
  //: and removed when it ends, redrawn at most once a frame from the last
  //: pointer position of that frame. It keeps the dashed accent edge and the
  //: 12% accent wash the SVG rectangle had.
  //: **A box being placed is drawn as what it will be** (the owner,
  //: 2026-10-10: "dragging to create any object should ghost preview that
  //: object, not be the drag selection", and "I tried dragging to create a
  //: frame and it randomly visually cut off half way on the screen"). The
  //: frame, sticky and text tools drew the selection marquee, a dashed
  //: accent wash on a canvas the size of the container as it was when the
  //: drag began, which said "select" rather than "a frame goes here" and was
  //: cut wherever that canvas ended. The ghost is an element of the card
  //: layer in board units, drawn in the placed kind's own look (a frame's
  //: edge and title, a sticky's paper, a text box's dashed field), so it pans
  //: and zooms with the board and covers the whole box the release makes.
  //: The selection marquee keeps its canvas (INBOX 410's cost).
  function wbBeginPlaceGhost(pointerId, place) {
    const layer = document.getElementById("wb-html-layer");
    if (!layer) return wbBeginMarqueeRect(pointerId);
    wbMarqueeEl = document.createElement("div");
    wbMarqueeEl.className = "wb-place-ghost";
    wbMarqueeEl.dataset.kind = place;
    wbMarqueeEl.dataset.label = place === "frame" ? "Frame" : place === "sticky" ? "" : "Text";
    wbMarqueeEl.setAttribute("aria-hidden", "true");
    layer.appendChild(wbMarqueeEl);
    wbBoardState.capture(containerEl, pointerId);
  }
  function wbBeginMarqueeRect(pointerId) {
    wbMarqueeEl = document.createElement("canvas");
    wbMarqueeEl.className = "wb-marquee";
    wbMarqueeEl.setAttribute("aria-hidden", "true");
    const ratio = window.devicePixelRatio || 1;
    const w = containerEl.clientWidth, h = containerEl.clientHeight;
    wbMarqueeEl.width = Math.max(1, Math.round(w * ratio));
    wbMarqueeEl.height = Math.max(1, Math.round(h * ratio));
    wbMarqueeEl.style.width = `${w}px`;
    wbMarqueeEl.style.height = `${h}px`;
    //: Through `wbExportColour`, because a canvas cannot read a `var()` and
    //: the accent may be a `color-mix()` the canvas does not parse either.
    const accent = wbExportColour(getComputedStyle(containerEl).getPropertyValue("--accent").trim());
    wbMarqueeInk = accent && accent !== "none" ? accent : "#3b82f6";
    containerEl.appendChild(wbMarqueeEl);
    // **The capture is the fix.** Without it every pointermove and pointerup
    // outside the container went to whatever element was under the cursor,
    // so a drag that ended over the top bar, over the left rail or off the
    // window simply never finished, and left its rectangle behind.
    wbBoardState.capture(containerEl, pointerId);
  }
  //: The selection drag's frames: the same 4-unit threshold as the marquee,
  //: then the whole selection by the pointer's travel from the press, Shift on
  //: one axis, grid-snapped by distance like a card's own drag.
  function wbSelectionDragMove(e) {
    const start = wbMarqueeStart;
    const [x, y] = getLogicalMouse(e);
    if (start.pending) {
      if (Math.abs(x - start.x) < 4 && Math.abs(y - start.y) < 4) return;
      start.origin = wbSelectionDragOrigin();
      if (!start.origin) return wbEndMarqueeDrag();
      start.pending = false;
      wbBoardState.capture(containerEl, start.pointerId);
    }
    const lock = wbAxisLock(x - start.x, y - start.y, e.shiftKey);
    wbApplyBulkMove(start.origin, lock === "y" ? 0 : wbSnap(x - start.x, e.altKey), lock === "x" ? 0 : wbSnap(y - start.y, e.altKey));
    wbQueueSelectionBar();
  }
  function wbEndSelectionDrag() {
    const { origin, pending } = wbMarqueeStart;
    wbMarqueeStart = null;
    wbEndMarqueeDrag();
    //: The release's own click lands on the canvas: it is not a clear.
    wbMarqueeJustSelected = true;
    if (pending || !origin) return;
    wbFinishDrag(null, origin, false);
  }
  window.addEventListener("pointermove", (e) => {
    if (!wbMarqueeStart) return;
    if (wbMarqueeStart.move) return wbSelectionDragMove(e);
    let [x, y] = getLogicalMouse(e);
    //: Shift makes a drawn box square, read live rather than from the press
    //: (on the marquee the press's Shift means "add to the selection").
    if (wbMarqueeStart.place && e.shiftKey) [x, y] = wbSquareCorner(wbMarqueeStart, x, y);
    else if (wbMarqueeStart.place && !wbMarqueeStart.pending) [x, y] = wbDrawOutSnap(wbMarqueeStart.x, wbMarqueeStart.y, x, y, e);
    if (wbMarqueeStart.pending) {
      // The same 4 units the completed gesture is measured against below, so
      // a press that never becomes a drag draws nothing and claims nothing.
      if (Math.abs(x - wbMarqueeStart.x) < 4 && Math.abs(y - wbMarqueeStart.y) < 4) return;
      wbMarqueeStart.pending = false;
      if (wbMarqueeStart.place) wbBeginPlaceGhost(wbMarqueeStart.pointerId, wbMarqueeStart.place);
      else wbBeginMarqueeRect(wbMarqueeStart.pointerId);
      // Placed now, before its first paint, so it never shows as a dot at
      // the container's corner for a frame.
      wbMarqueeAt = [x, y];
      wbDrawMarquee();
      return;
    }
    wbMarqueeAt = [x, y];
    if (!wbMarqueeFrame) wbMarqueeFrame = requestAnimationFrame(wbDrawMarquee);
  });
  //: The board point under the pointer, to the container's own pixels: the
  //: inverse of `getLogicalMouse`, so the box is where the selection is.
  function wbDrawMarquee() {
    wbMarqueeFrame = 0;
    if (!wbMarqueeEl || !wbMarqueeStart || !wbMarqueeAt) return;
    const t = d3.zoomTransform(containerEl);
    //: A box being placed is drawn at the size it will be made, minimum and
    //: all, so what the ghost shows is what the release creates.
    const box = wbMarqueeStart.place ? wbPlaceBox(wbMarqueeStart, wbMarqueeAt[0], wbMarqueeAt[1]) : null;
    if (box && wbMarqueeEl.classList.contains("wb-place-ghost")) return wbMoveSizeGhost(box);
    const x0 = t.applyX(box ? box.x : wbMarqueeStart.x), y0 = t.applyY(box ? box.y : wbMarqueeStart.y);
    const x1 = t.applyX(box ? box.x + box.w : wbMarqueeAt[0]), y1 = t.applyY(box ? box.y + box.h : wbMarqueeAt[1]);
    const l = Math.round(Math.min(x0, x1)), top = Math.round(Math.min(y0, y1));
    const w = Math.round(Math.abs(x1 - x0)), h = Math.round(Math.abs(y1 - y0));
    const ratio = window.devicePixelRatio || 1;
    //: **The canvas follows the container, every frame** (the owner,
    //: 2026-10-10: a drag preview "randomly visually cut off half way on the
    //: screen"). It was sized once, when the drag began; a container that
    //: grew during the drag (a panel closing, the window maximised, a rail
    //: still animating when the press landed) left the rest of the rectangle
    //: past the canvas's edge, undrawn. Two reads and a compare per frame.
    wbFitMarqueeCanvas(ratio);
    const g = wbMarqueeEl.getContext("2d");
    g.setTransform(ratio, 0, 0, ratio, 0, 0);
    g.clearRect(0, 0, wbMarqueeEl.width, wbMarqueeEl.height);
    if (!w || !h) return;
    g.fillStyle = wbMarqueeInk;
    g.strokeStyle = wbMarqueeInk;
    g.globalAlpha = 0.12;
    g.fillRect(l, top, w, h);
    g.globalAlpha = 1;
    g.lineWidth = 1;
    g.setLineDash([4, 3]);
    g.strokeRect(l + 0.5, top + 0.5, Math.max(0, w - 1), Math.max(0, h - 1));
  }
  //: **A drag past the edge moves the board** (INBOX 608, the owner: "when I
  //: drag select off the screen on the whiteboard and mind map ... it doesnt
  //: scroll down or up or the way I am dragging"). A marquee, an item or a
  //: branch carried to the edge of the canvas used to stop there: the board
  //: did not move, so anything past the edge could not be reached without
  //: letting go. Every whiteboard app pans here (Miro, FigJam, draw.io).
  //:
  //: A band inside each edge of the canvas; the deeper the pointer is in it
  //: (or past it, off the canvas, which the pointer capture still reports),
  //: the faster the board moves, up to `max` screen pixels a frame. Eased
  //: (squared), so the first few pixels of the band creep and a pointer held
  //: at the very edge travels. One frame loop while the pointer is in a band,
  //: none otherwise.
  //:
  //: After each step the pointer is replayed where it is: the marquee is
  //: redrawn from it, and an item drag gets a synthetic move at the same
  //: screen point, which d3-drag measures against its container (a layer
  //: that moved with the pan), so the item travels exactly as far as the
  //: board did and stays under the pointer. A rotation is excluded (an
  //: angle does not need room), and so are the pen tools and the hand.
  const wbEdgePan = { x: 0, y: 0, buttons: 0, frame: 0, turn: false, band: 56, max: 22 };
  //: The placing ghost is a box in board space, not the marquee canvas: it
  //: moves by transform (its layer, `will-change`) and takes the size the
  //: release will create, so the only per-move layout is its own.
  function wbMoveSizeGhost(box) {
    wbMarqueeEl.style.transform = `translate(${box.x}px, ${box.y}px)`;
    wbMarqueeEl.style.width = `${box.w}px`;
    wbMarqueeEl.style.height = `${box.h}px`;
  }
  //: The canvas's bitmap and box follow the container's size, compared
  //: before written: a style write on every move would re-layerize the
  //: page (tests/test_marquee_cost.py), so this is a resize, not a draw.
  function wbFitMarqueeCanvas(ratio) {
    const cw = containerEl.clientWidth, ch = containerEl.clientHeight;
    const bw = Math.max(1, Math.round(cw * ratio)), bh = Math.max(1, Math.round(ch * ratio));
    if (wbMarqueeEl.width === bw && wbMarqueeEl.height === bh) return;
    wbMarqueeEl.width = bw;
    wbMarqueeEl.height = bh;
    wbMarqueeEl.style.width = `${cw}px`;
    wbMarqueeEl.style.height = `${ch}px`;
  }
  window.addEventListener("pointerdown", (e) => {
    wbEdgePan.turn = Boolean(e.target?.closest?.(".wb-rotate-handle, .wb-sketch-rotate-handle"));
  }, true);
  function wbEdgePanWanted() {
    if (!(wbEdgePan.buttons & 1) || WB_BRUSH_TOOLS.has(window.currentTool) || window.currentTool === "pan") return false;
    const wanted = (wbMarqueeEl && wbMarqueeStart && !wbMarqueeStart.pending) || Boolean(wbGesture && !wbGesture.cancelled && !wbGesture.overTrash && !wbEdgePan.turn);
    return wanted && !wbCompanionHeld(null, "edge pan");
  }
  //: Screen pixels a frame along one axis: positive moves the board's
  //: content towards the far edge (so the near side comes into view).
  function wbEdgePanSpeed(near, far, band) {
    const depth = near > 0 ? near : far > 0 ? -far : 0;
    if (!depth) return 0;
    const share = Math.min(1, Math.abs(depth) / band);
    return Math.sign(depth) * Math.max(1, Math.round(wbEdgePan.max * share * share));
  }
  function wbEdgePanTick() {
    wbEdgePan.frame = 0;
    if (!wbEdgePanWanted() || !document.body.contains(containerEl)) return;
    const r = containerEl.getBoundingClientRect();
    const band = Math.min(wbEdgePan.band, r.width / 5, r.height / 5);
    const vx = wbEdgePanSpeed(r.left + band - wbEdgePan.x, wbEdgePan.x - (r.right - band), band);
    const vy = wbEdgePanSpeed(r.top + band - wbEdgePan.y, wbEdgePan.y - (r.bottom - band), band);
    if (!vx && !vy) return;
    const k = d3.zoomTransform(containerEl).k || 1;
    d3.select(containerEl).call(wbZoom.translateBy, vx / k, vy / k);
    const at = { clientX: wbEdgePan.x, clientY: wbEdgePan.y, buttons: wbEdgePan.buttons, bubbles: true, cancelable: true, view: window };
    if (wbMarqueeEl && wbMarqueeStart) {
      wbMarqueeAt = getLogicalMouse(at);
      wbDrawMarquee();
    } else {
      //: d3-drag's own move listener, called directly: a broadcast
      //: mousemove re-entered the right-press, hover and marquee listeners
      //: with coordinates nobody moved to (audit B16).
      d3.select(window).on("mousemove.drag")?.call(window, new MouseEvent("mousemove", at));
    }
    wbEdgePan.frame = requestAnimationFrame(wbEdgePanTick);
  }
  window.addEventListener("pointermove", (e) => {
    if (e.pointerType === "touch") return;
    wbEdgePan.x = e.clientX;
    wbEdgePan.y = e.clientY;
    wbEdgePan.buttons = e.buttons;
    if (!wbEdgePan.frame && wbEdgePanWanted()) wbEdgePan.frame = requestAnimationFrame(wbEdgePanTick);
  });
  window.addEventListener("pointerup", () => {
    wbEdgePan.buttons = 0;
    if (wbEdgePan.frame) cancelAnimationFrame(wbEdgePan.frame);
    wbEdgePan.frame = 0;
  }, true);
  // Anchor points weren't discoverable until a link drag was already under
  // way: asked for directly: "when I hover over objects, their anchor
  // points should display... so I can connect them." A plain hover with a
  // link-type tool selected, no drag started yet, now shows the same 8
  // fixed-point hints the in-progress drag already draws (`wbShowAnchorHints`,
  // shared so the two can't drift visually apart). Skips while an actual
  // link drag is running (`wbLinkDragActive`), that path already redraws
  // hints every frame from the live pointer position, and this would just
  // be a second, slightly-stale write to the same DOM nodes.
  //: On the container, not on each handle: the handles are rebuilt by the
  //: render on every change, and a listener bound per handle is a listener
  //: lost on the next repaint (the mistake `wbWireContextMenu` documents).
  containerEl.addEventListener("dblclick", (e) => {
    const turn = e.target.closest?.(".wb-rotate-handle, .wb-sketch-rotate-handle");
    if (turn) {
      e.preventDefault();
      e.stopPropagation();
      wbResetRotation(turn, e.ctrlKey || e.metaKey);
      return;
    }
    const handle = e.target.closest?.(".wb-resize-handle, .wb-map-resize-grip");
    if (!handle) return;
    e.preventDefault();
    e.stopPropagation();
    //: A frame fits what it holds, not its own text: the edge named by the
    //: handle, or the two of a corner (INBOX 821).
    const frameEl = handle.closest(".wb-object-frame");
    if (frameEl && handle.dataset.handle) {
      wbFrameFit((wbState.objects || []).find((o) => o.id === Number(frameEl.dataset.id)), handle.dataset.handle);
      return;
    }
    const owner = handle.closest(".wb-object, .node-card");
    if (owner?.classList.contains("wb-object-image")) wbFitImage(owner);
    else wbFitToText(owner);
  });

  //: **The two gestures a map has to answer on its own canvas** (MINDMAP_PLAN
  //: §13, the owner: the tools "dont show themselves how id expect"). Both
  //: were measured doing nothing at all before this: a right-click on empty
  //: map canvas opened no menu, and a double-click added no topic, so the
  //: first two things anybody tries on a blank part of a mind map were dead.
  //: Neither adds a resting affordance to the canvas (§13's decision 5); both
  //: are the app's own recipes, `openMenuAtPoint` for the menu and the map's
  //: own create for the topic.
  //:
  //: **A board answers the double-click too** (the conventions pass,
  //: 2026-09-23): a text box where you pressed, ready to type, which is what
  //: Excalidraw and tldraw do on bare canvas. Measured doing nothing before.
  //: A sticky is one key away (N) and in the canvas menu below; the text box
  //: is the plainer of the two, and the one both of those apps make.
  //:
  //: A branch line is not bare canvas here, whatever `wbIsEmptyCanvasTarget`
  //: says for a marquee: a double-click on a line asks for its label (see
  //: `wbWireMapEdgeGestures`), and it used to fall through to this and make a
  //: new trunk on top of the line.
  containerEl.addEventListener("dblclick", (e) => {
    if (window.currentTool !== "select") return;
    if (!wbIsEmptyCanvasTarget(e.target) || wbIsEditingTarget(e.target)) return;
    if (e.target.closest?.(".wb-map-edge-group, .sketch-group")) return;
    e.preventDefault();
    const [x, y] = getLogicalMouse(e);
    if (wbIsMap()) wbMapAddRootAt(x, y);
    else wbCreateTextBox(x, y);
  });

  //: One builder for the canvas menu, because the right-click and the hold
  //: are the same menu and a second copy is how the two come to disagree
  //: (DESIGN.md: every `contextmenu` listener is counted against a
  //: `wireLongPress` call in the same file, and `tests/test_ui_recipes.py`
  //: fails a right-click menu with no long-press twin).
  const openMapCanvasMenu = (clientX, clientY) => {
    const [x, y] = getLogicalMouse({ clientX, clientY });
    const index = wbMapIndex();
    const folded = index.nodes.filter((n) => n.data?.collapsed).length;
    const open = wbMapFoldToLevel.open(index);
    //: One more or one less level, each greyed unless it changes something (INBOX 1774).
    const hiddenByFold = wbMapHidden(index);
    const moreLevel = makeMenuItem("ph:plus-circle Show one more level", "Open the shallowest folded branches (Alt+=)", () => wbMapFoldToLevel({ by: 1 }));
    const lessLevel = makeMenuItem("ph:minus-circle Show one less level", "Fold the deepest open branches (Alt+-)", () => wbMapFoldToLevel({ by: -1 }));
    moreLevel.disabled = !wbMapBuild.ring(index, hiddenByFold, 1).ids.length;
    lessLevel.disabled = !wbMapBuild.ring(index, hiddenByFold, -1).ids.length;
    const items = [
      makeMenuItem("ph:plus-circle Add a topic here", "A new trunk, where you pressed: or double-click the canvas", () => wbMapAddRootAt(x, y)),
      makeMenuItem("ph:broom Tidy the map", "Lay every unpinned topic out again", () => wbMapTidy()),
      makeMenuItem(
        folded ? `ph:arrows-out-line-vertical Open every folded branch (${folded})` : "ph:arrows-out-line-vertical Open every folded branch",
        folded ? "This map has folded branches" : "Nothing is folded on this map",
        () => wbMapExpandAll()
      ),
      makeMenuItem(
        `ph:arrows-in-line-vertical Fold every branch${open ? ` (${open})` : ""}`,
        open ? "Show the trunks only (Alt+1)" : "Every branch is already folded",
        () => wbMapFoldToLevel(1)
      ),
      moreLevel,
      lessLevel,
      makeMenuItem("ph:frame-corners Fit everything", "Show the whole map (Shift+1)", () =>
        document.getElementById("wb-zoom-fit")?.click()
      ),
    ];
    openMenuAtPoint(items, "This map", clientX, clientY);
  };

  //: **And a board's canvas has its own menu** (the conventions pass): the
  //: browser's page menu is what a right-click on bare board canvas used to
  //: open, where Figma, Miro and tldraw all give paste, select all and the
  //: zoom. Each row names its key, so the menu is also where the keys are
  //: learnt.
  const openBoardCanvasMenu = (clientX, clientY) => {
    const [x, y] = getLogicalMouse({ clientX, clientY });
    const items = [];
    if (wbClipboard) {
      const count = wbClipboard.things;
      items.push(makeMenuItem(
        count > 1 ? `ph:clipboard-text Paste ${nounCount(count, "item")} here` : "ph:clipboard-text Paste here",
        "Ctrl+V pastes beside the original, Ctrl+Shift+V in place", () => wbPasteClipboard({ at: [x, y] })
      ));
      items.push(makeMenuItem("ph:clipboard Paste here without comments", "Ctrl+Alt+Shift+V", () => wbPasteClipboard({ at: [x, y], noComments: true })));
    }
    items.push(makeMenuItem("ph:clipboard-text Paste special", "Choose how the clipboard lands", () => wbPasteSpecialMenu()));
    items.push(
      makeMenuItem("ph:text-t Add a text box here", "Or double-click the canvas", () => wbCreateTextBox(x, y)),
      makeMenuItem("ph:note Add a sticky note here", "N", () => wbCreateSticky(x, y)),
      makeMenuItem("ph:frame-corners Add a frame here", "F", () => wbCreateFrame(x, y)),
      makeMenuItem("ph:selection-all Select all", "Ctrl+A", () => wbSelectAllItems()),
      makeMenuItem("ph:magnifying-glass Zoom to 100%", "Ctrl+1", wbZoomTo100),
      makeMenuItem("ph:frame-corners Fit everything", "Shift+1", () => wbZoomToFit()),
    );
    //: The way back to a locked item (decision 15): it lets the pointer
    //: through, so a right-click on it lands here, on the board.
    //: Right-click on the locked item itself unlocks that one, first.
    const lockedHere = wbLockedItemAt(x, y);
    if (lockedHere) {
      items.unshift(makeMenuItem(
        "ph:lock-simple-open Unlock this item", "It is locked, so the pointer passes through it",
        () => wbSetLocked([[lockedHere.kind, lockedHere.item]], false)
      ));
    }
    const locked = wbLockedItems().length;
    if (locked) {
      items.push(makeMenuItem(
        `ph:lock-simple-open Unlock ${locked} locked item${locked === 1 ? "" : "s"}`,
        "Ctrl+Shift+L with nothing selected", () => wbUnlockAll()
      ));
    }
    openMenuAtPoint(items, "This board", clientX, clientY);
  };

  //: The first press on a locked item, which lets the pointer through, says how to unlock it.
  containerEl.addEventListener("pointerdown", wbOnLockPress, true);

  const wbCanvasMenuWanted = (target) =>
    wbIsEmptyCanvasTarget(target) && !wbIsEditingTarget(target)
    && !target.closest?.(".wb-map-edge-group, .sketch-group");
  const openCanvasMenu = (clientX, clientY) => (wbIsMap()
    ? openMapCanvasMenu(clientX, clientY)
    : openBoardCanvasMenu(clientX, clientY));

  //: **Right-drag pans, a plain right-click opens the menu** (C03, the owner:
  //: "hard to move around the whiteboard with a mouse, copy draw.io and have
  //: right click hold down drag panning"). The browser sends `contextmenu`
  //: on the press (Linux) or the release (Windows), so "suppress it only
  //: when the drag moved" cannot be written (wbrightpan.js header). Instead
  //: the native event on bare canvas is always swallowed while a right press
  //: is in flight or just ended, and the app's own menu opens on the
  //: release when the pointer stayed inside the slop. A `contextmenu` with
  //: no press behind it (the menu key) still opens the menu.
  const WB_RIGHT_SLOP = 4;
  let wbRightPress = null;
  const wbRightOwns = () => wbRightPress && (!wbRightPress.up || Date.now() - wbRightPress.upAt < 400);
  window.addEventListener("mousedown", (e) => {
    if (e.button !== 2) return;
    wbRightPress = containerEl.contains(e.target) && wbCanvasMenuWanted(e.target)
      ? { x: e.clientX, y: e.clientY, moved: false, up: false, upAt: 0 } : null;
  }, true);
  window.addEventListener("mousemove", (e) => {
    if (!wbRightPress || wbRightPress.up) return;
    if ((e.buttons & 2) !== 2) { wbRightPress = null; return; }
    if (wbRightPress.moved) return;
    if (Math.hypot(e.clientX - wbRightPress.x, e.clientY - wbRightPress.y) < WB_RIGHT_SLOP) {
      //: Hold the zoom's own move listener (capture, on the window, added
      //: after this one) until the press is a drag.
      e.stopImmediatePropagation();
    } else {
      wbRightPress.moved = true;
    }
  }, true);
  window.addEventListener("mouseup", (e) => {
    if (e.button !== 2 || !wbRightPress || wbRightPress.up) return;
    wbRightPress.up = true;
    wbRightPress.upAt = Date.now();
    if (!wbRightPress.moved) {
      const { clientX, clientY } = e;
      setTimeout(() => openCanvasMenu(clientX, clientY), 0);
    }
  }, true);
  containerEl.addEventListener("contextmenu", (e) => {
    //: A topic and a line have rings of their own, and both stop the event
    //: before it reaches here; this is the canvas itself, which had nothing.
    if (!wbCanvasMenuWanted(e.target)) return;
    e.preventDefault();
    if (wbRightOwns()) return;
    openCanvasMenu(e.clientX, e.clientY);
  });

  //: The same menu from a hold, which is the right-click a phone has.
  wireLongPress(containerEl, (event, point) => {
    if (!wbCanvasMenuWanted(event.target)) return;
    openCanvasMenu(point.x, point.y);
  });

  //: Where a keyboard paste lands (`wbPointerOnBoard`).
  containerEl.addEventListener("pointermove", (e) => {
    wbPointerClient = { clientX: e.clientX, clientY: e.clientY };
  }, { passive: true });
  containerEl.addEventListener("pointerleave", () => { wbPointerClient = null; });

  containerEl.addEventListener("pointermove", wbOnFrame((e) => {
    if (wbLinkDragActive) return;
    //: Off a link tool there are no dots to show, and any left over go (INBOX
    //: 573: the cross-link tool's dots stayed on a topic after switching back
    //: to Select, through Escape, a press on the canvas, Undo and a tab switch).
    if (window.currentTool === "select" && !e.buttons) {
      portHover(e);
      return;
    }
    if (!window.currentTool || !window.currentTool.startsWith("link-")) {
      wbClearAnchorHints();
      return;
    }
    const [x, y] = getLogicalMouse(e);
    // Every linkable thing, in its rotated frame, this was cards only, on
    // their unrotated box (reported: stickies "light up" wrong).
    const hit = wbLinkCandidateAt(x, y);
    if (hit) wbShowAnchorHints(hit[0], hit[1], wbNearestAnchor(hit[0], hit[1], x, y));
    else wbClearAnchorHints();
  }, true), { passive: true });

  // --- Connection points with Select (wb-phase2 step 5; draw.io's ports) ---
  //
  // With Select, pointing at a shape, card or text box shows its connection
  // points (`wbAnchorPositions`: a polygon's corners and side middles, an
  // ellipse's compass points), and a press on one draws a connector from it
  // (an elbow with an arrow, as clone-and-connect makes) to the item it is
  // let go on, at that item's nearest point, or to a free end on empty board.
  // Not on what is selected (its resize grips sit where its ports are), a
  // locked item, a map (whose lines are its tree), or touch (no hover).
  const port = { kind: null, item: null, drag: null };
  const zoomK = () => d3.zoomTransform(containerEl).k || 1;
  const portTarget = (x, y) => {
    let hit = wbLinkCandidateAt(x, y);
    if (!hit && port.item) {
      //: Keep the points while the pointer is just outside the outline,
      //: which is where it is on its way to one of them.
      const box = wbItemBBox(port.kind, port.item);
      const pad = 14 / zoomK();
      if (box && x >= box.minX - pad && x <= box.maxX + pad && y >= box.minY - pad && y <= box.maxY + pad) hit = [port.kind, port.item];
    }
    if (!hit || wbIsMap() || wbIsLocked(hit[0], hit[1]) || wbSelectedKeys().has(wbMultiKey(hit[0], hit[1].id))) return null;
    return hit;
  };
  function portHover(e) {
    if (e.pointerType === "touch" || port.drag) return;
    const [x, y] = getLogicalMouse(e);
    const hit = portTarget(x, y);
    if (!hit) {
      if (port.item) wbClearAnchorHints();
      port.kind = null;
      port.item = null;
      return;
    }
    [port.kind, port.item] = hit;
    wbShowAnchorHints(hit[0], hit[1], wbNearestAnchor(hit[0], hit[1], x, y, WB_PORT_HIT_PX / zoomK()));
  }
  const portEnd = () => {
    port.drag?.path?.remove();
    port.drag = null;
    wbLinkDragActive = false;
    wbClearAnchorHints();
    wbFmtState.linkEdge?.cue(null);
  };
  containerEl.addEventListener("pointerdown", (e) => {
    if (e.button !== 0 || e.pointerType === "touch" || window.currentTool !== "select" || !port.item || e.altKey || e.shiftKey) return;
    //: A selected connector's end grip wins over a port beneath it (INBOX
    //: 1328: dragging the end of an arrow drew a second arrow instead,
    //: because the grip sits on the very edge point the item's port is).
    if (e.target?.closest?.(".wb-link-endpoint-handle, .wb-resize-handle, .wb-rotate-handle")) return;
    const [x, y] = getLogicalMouse(e);
    if (!portTarget(x, y)) return;
    //: Near enough to a point, and never so far that a small shape on screen
    //: is all points: at most a fifth of its shorter side, so its middle is
    //: still the shape (measured at a phone's fitted zoom: a 36px-tall box
    //: was a connector from its middle at a flat 9px).
    const box = wbItemBBox(port.kind, port.item);
    const side = box ? Math.min(box.maxX - box.minX, box.maxY - box.minY) * zoomK() : 0;
    const anchor = wbNearestAnchor(port.kind, port.item, x, y, Math.min(WB_PORT_HIT_PX, side * 0.2) / zoomK());
    if (!anchor) return;
    //: Before d3-drag's mousedown: a pointerdown's default prevented is
    //: the mouse events it would have made, so the item does not move.
    e.preventDefault();
    e.stopPropagation();
    const start = wbAnchorPoint(port.kind, port.item, anchor);
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("class", "wb-port-preview");
    path.setAttribute("fill", "none");
    path.setAttribute("stroke", window.currentStrokeColor || "#888888");
    path.setAttribute("stroke-width", "2");
    path.setAttribute("stroke-dasharray", "6 4");
    path.setAttribute("pointer-events", "none");
    document.getElementById("wb-zoom-group")?.appendChild(path);
    port.drag = { kind: port.kind, item: port.item, anchor, start, path, moved: false, id: e.pointerId };
    wbLinkDragActive = true;
    wbBoardState.capture(containerEl, e.pointerId);
  }, true);
  //: The line and `moved` follow every event (release reads `moved`); only
  //: the anchor hit test waits for the frame.
  const portHints = wbOnFrame(({ drag, x, y }) => {
    if (port.drag !== drag) return;
    const hit = wbLinkCandidateAt(x, y, drag.kind, drag.item.id);
    if (hit) wbShowAnchorHints(hit[0], hit[1], wbNearestAnchor(hit[0], hit[1], x, y));
    else wbShowAnchorHints(drag.kind, drag.item, drag.anchor);
    wbFmtState.linkEdge?.cue(hit ? null : [x, y]);
  });
  containerEl.addEventListener("pointermove", (e) => {
    const drag = port.drag;
    if (!drag) return;
    const [x, y] = getLogicalMouse(e);
    drag.moved = drag.moved || Math.hypot(x - drag.start.x, y - drag.start.y) * zoomK() > 4;
    drag.path.setAttribute("d", `M ${drag.start.x} ${drag.start.y} L ${x} ${y}`);
    portHints({ drag, x, y });
  });
  containerEl.addEventListener("keydown", (e) => {
    if (port.drag && e.key === "Escape") {
      e.stopPropagation();
      portEnd();
    }
  }, true);
  containerEl.addEventListener("pointerup", async (e) => {
    const drag = port.drag;
    if (!drag) return;
    const [x, y] = getLogicalMouse(e);
    portEnd();
    //: The click the release makes lands on the container (the pointer was
    //: captured there), which reads it as a click on empty board and clears
    //: the selection this is about to make: swallowed, for this task only.
    const swallow = (ev) => {
      ev.stopPropagation();
      ev.preventDefault();
    };
    window.addEventListener("click", swallow, true);
    setTimeout(() => window.removeEventListener("click", swallow, true), 0);
    if (!drag.moved) {
      //: A press that did not travel is a click on the item it is on.
      selectWbItem(drag.kind, drag.item.id);
      return;
    }
    const hit = wbLinkCandidateAt(x, y, drag.kind, drag.item.id);
    const data = {
      type: "link-straight",
      route: "elbow",
      sourceId: drag.item.id,
      sourceKind: drag.kind === "node" ? undefined : drag.kind,
      sourceAnchor: drag.anchor,
      color: window.currentStrokeColor || "#888888",
      width: 2,
      endCap: "arrow",
    };
    if (hit) {
      data.targetId = hit[1].id;
      data.targetKind = hit[0] === "node" ? undefined : hit[0];
      data.targetAnchor = wbNearestAnchor(hit[0], hit[1], x, y) || undefined;
    } else {
      const edge = wbFmtState.linkEdge?.hitAt(x, y);
      data.targetPoint = edge ? { x: edge.x, y: edge.y } : { x: Math.round(x), y: Math.round(y) };
      if (edge) data.targetEdge = { id: edge.id, t: edge.t };
    }
    try {
      const made = await apiJson("/whiteboard/sketches", {
        method: "POST",
        body: JSON.stringify({ data: JSON.stringify(data), x: 0, y: 0, z: wbStackNewZ("sketch"), board_id: window.currentBoardId ?? null }),
      });
      wbState.sketches.push(made);
      wbPushUndo({ action: "create", kind: "sketch", id: made.id });
      renderWhiteboardNow();
      selectWbItem("sketch", made.id);
      wbAnnounce(hit || data.targetEdge ? "Connected." : "Connector drawn to a free end.");
    } catch (error) {
      toast(error.message || "The connector could not be made.", true);
    }
  });

  // On `window`, not on the container, and for three event names rather than
  // one. The container's own pointerup is not enough: a capture can be lost
  // (`lostpointercapture`), a gesture can be taken over by the browser
  // (`pointercancel`), and a synthetic pointerdown was never captured at all.
  // Every one of those used to leave the rectangle on the board.
  wbBoardState.onGestureLost(() => wbEndMarqueeDrag());
  window.addEventListener("pointerup", (e) => {
    if (!wbMarqueeStart) return;
    if (wbMarqueeStart.move) return wbEndSelectionDrag();
    let [x, y] = getLogicalMouse(e);
    const start = wbMarqueeStart;
    if (start.place && e.shiftKey) [x, y] = wbSquareCorner(start, x, y);
    else if (start.place) [x, y] = wbDrawOutSnap(start.x, start.y, x, y, e);
    wbClearAlignmentGuides();
    const mx = Math.min(start.x, x), my = Math.min(start.y, y);
    const mw = Math.abs(x - start.x), mh = Math.abs(y - start.y);
    //: Shift at the press or at the release adds (the owner, 2026-10-07).
    const shiftKey = start.shiftKey || e.shiftKey;
    wbEndMarqueeDrag();
    // Too small to be a deliberate drag, the plain "click" listener above
    // already handles this as a click-to-clear-selection instead (or, with
    // the text and sticky tools, as a click that drops the default size).
    if (mw < 4 && mh < 4) return;
    if (start.place) {
      //: The release makes a `click` on the canvas as well, which would drop
      //: a second, default-sized box where the drag ended.
      wbPlaceJustDrawn = true;
      const box = wbPlaceBox(start, x, y);
      if (start.place === "sticky") wbCreateSticky(x, y, box);
      else if (start.place === "frame") wbCreateFrame(x, y, box);
      else wbCreateTextBox(x, y, box);
      return;
    }
    if (!shiftKey) wbMultiSelection.clear();
    //: The one item selected before a Shift-drag stays in: it lives in
    //: `wbSelectedItem`, not the set, and was dropped (the owner, 2026-10-07).
    else if (wbSelectedItem) wbMultiSelection.add(wbMultiKey(wbSelectedItem.kind, wbSelectedItem.id));
    for (const node of wbState.nodes) {
      if (node.locked || wbFmtState.isolate?.outside("node", node)) continue; // decision 15: out of reach until unlocked
      const el = document.querySelector(WB_SELECTOR_BY_KIND.node(node.id));
      const w = el?.offsetWidth || 250, h = el?.offsetHeight || 150;
      if (rectsIntersect(mx, my, mw, mh, node.x, node.y, w, h)) {
        wbMultiSelection.add(wbMultiKey("node", node.id));
      }
    }
    for (const obj of wbState.objects || []) {
      if (wbIsLocked("object", obj) || wbFmtState.isolate?.outside("object", obj)) continue;
      //: A frame only when the sweep holds all of it (decision 14): a sweep
      //: drawn inside a frame is about what is in it, and taking the frame
      //: along would make the next drag carry the frame and everything else.
      const hit = obj.kind === "frame"
        ? mx <= obj.x && my <= obj.y && mx + mw >= obj.x + obj.width && my + mh >= obj.y + obj.height
        : rectsIntersect(mx, my, mw, mh, obj.x, obj.y, obj.width, obj.height);
      if (hit) {
        wbMultiSelection.add(wbMultiKey("object", obj.id));
      }
    }
    for (const sketch of wbState.sketches) {
      const parsed = wbSketchParsedData(sketch);
      if (!parsed) continue; // a link sketch: nothing here to select as a shape
      if (parsed.locked || wbFmtState.isolate?.outside("sketch", sketch)) continue;
      const bbox = wbPathBBox(parsed.d);
      if (bbox && rectsIntersect(mx, my, mw, mh, bbox.minX, bbox.minY, bbox.width, bbox.height)) {
        wbMultiSelection.add(wbMultiKey("sketch", sketch.id));
      }
    }
    //: **A sweep that caught one thing selects that thing properly.**
    //: Reported: "shapes like circles and lines dont visibly select and show
    //: anchor points when I highlight select over them". A drawn shape is a
    //: sketch, and a sketch's selection box and its eight anchors are drawn
    //: by `wbRenderSketchHandles`, which only ever runs for the *single*
    //: selection: a marquee cleared that and put the id in the multi set
    //: instead, where a sketch had no decoration of any kind. So sweeping
    //: over a circle really did select it and really did show nothing.
    //: Promoting a one-item sweep is the honest fix rather than a second
    //: decoration: one item selected by a sweep and the same item selected by
    //: a click are the same selection, and should look and behave the same.
    //: (A sweep over several still has no one box to hang anchors off, which
    //: is why the class also has a visible style of its own now.)
    wbSelectedItem = null;
    if (wbMultiSelection.size === 1) {
      const key = [...wbMultiSelection][0];
      const sep = key.indexOf(":");
      wbMultiSelection.clear();
      wbSelectedItem = { kind: key.slice(0, sep), id: Number(key.slice(sep + 1)) };
    }
    wbMarqueeJustSelected = true;
    wbApplySelectionHighlight();
  });

  // Freeform lasso select: asked for directly ("all the selection tools
  // (e.g. rectangle select and lasso)"). Same shape as the marquee just
  // above (empty-canvas-only pointerdown, shift to add, `wbMarqueeJustSelected`
  // shared so the trailing native "click" doesn't wipe the result) but hit-
  // tests each item's *centre point* against the traced polygon rather than
  // rectangle-intersecting its bounding box, a lasso is a freeform loop, so
  // "is this item's middle inside the loop" is the one test that stays
  // cheap (one ray-cast per item, not a polygon-clip against every edge) and
  // still matches what a user visually circled.
  function wbPointInPolygon(px, py, points) {
    let inside = false;
    for (let i = 0, j = points.length - 1; i < points.length; j = i++) {
      const [xi, yi] = points[i], [xj, yj] = points[j];
      const crosses = yi > py !== yj > py && px < ((xj - xi) * (py - yi)) / (yj - yi) + xi;
      if (crosses) inside = !inside;
    }
    return inside;
  }
  let wbLassoPoints = null;
  let wbLassoEl = null;
  let wbLassoShift = false;
  //: The lasso's half of `wbEndMarqueeDrag`, and it exists for the same
  //: reported bug: a loop released outside the container left its polyline
  //: on the canvas with nothing holding a reference to it.
  function wbEndLassoDrag() {
    wbLassoEl?.remove();
    wbLassoEl = null;
    wbLassoPoints = null;
  }
  //: Both drags, from anywhere in the file, see `wbCancelSelectionDragRef`.
  wbCancelSelectionDragRef = () => {
    //: In flight means drawn: a press that has not travelled yet is still a
    //: click (see the marquee's `pending`), and Escape then means what it
    //: means with nothing in hand.
    const inFlight = Boolean((wbMarqueeStart && !wbMarqueeStart.pending) || wbLassoEl);
    wbEndMarqueeDrag();
    wbEndLassoDrag();
    //: The release that ends a taken-back drag still makes a `click` on the
    //: canvas, and a canvas click clears the selection: the same one-shot a
    //: finished marquee uses keeps what Escape kept.
    if (inFlight) {
      wbMarqueeJustSelected = true;
      //: And a text or sticky box taken back is not then dropped at its
      //: default size by the same release.
      wbPlaceJustDrawn = true;
    }
    return inFlight;
  };
  containerEl.addEventListener("pointerdown", (e) => {
    // Unlike the marquee (`wbIsEmptyCanvasTarget`, above: empty canvas
    // only, since a drag starting *on* a card there means "move it"), a
    // lasso loop is drawn freeform and routinely starts right at the edge
    // of the first thing it means to circle, reported directly as "the
    // lasso tool doesn't work properly". Still excludes an actual handle,
    // which needs its own drag gesture to keep working.
    if (window.currentTool !== "lasso" || e.target.closest?.(".wb-resize-handle, .wb-rotate-handle, .wb-object-grip, .wb-link-endpoint-handle")) return;
    if (e.button !== 0 || !e.isPrimary) return;
    wbEndLassoDrag();
    const [x, y] = getLogicalMouse(e);
    wbLassoPoints = [[x, y]];
    wbLassoShift = e.shiftKey;
    wbLassoEl = document.createElementNS("http://www.w3.org/2000/svg", "polyline");
    wbLassoEl.setAttribute("class", "wb-lasso");
    wbLassoEl.setAttribute("points", `${x},${y}`);
    // The overlay layer, which paints above the HTML card layer, in the
    // base SVG the loop was drawn *under* every card and sticky (reported:
    // "the lasso select tool is behind everything").
    document.getElementById("wb-overlay-zoom-group").appendChild(wbLassoEl);
    wbBoardState.capture(containerEl, e.pointerId);
  });
  wbBoardState.onGestureLost(() => wbEndLassoDrag());
  window.addEventListener("pointermove", (e) => {
    if (!wbLassoPoints) return;
    const [x, y] = getLogicalMouse(e);
    wbLassoPoints.push([x, y]);
    wbLassoEl.setAttribute("points", wbLassoPoints.map(([px, py]) => `${px},${py}`).join(" "));
  });
  window.addEventListener("pointerup", () => {
    if (!wbLassoPoints) return;
    const points = wbLassoPoints, shiftKey = wbLassoShift;
    wbEndLassoDrag();
    if (points.length < 3) return; // a tap, not a loop, nothing to select
    if (!shiftKey) wbMultiSelection.clear();
    //: The one item selected before a Shift-drag stays in: it lives in
    //: `wbSelectedItem`, not the set, and was dropped (the owner, 2026-10-07).
    else if (wbSelectedItem) wbMultiSelection.add(wbMultiKey(wbSelectedItem.kind, wbSelectedItem.id));
    for (const node of wbState.nodes) {
      if (node.locked || wbFmtState.isolate?.outside("node", node)) continue; // decision 15: out of reach until unlocked
      const el = document.querySelector(WB_SELECTOR_BY_KIND.node(node.id));
      const w = el?.offsetWidth || 250, h = el?.offsetHeight || 150;
      if (wbPointInPolygon(node.x + w / 2, node.y + h / 2, points)) {
        wbMultiSelection.add(wbMultiKey("node", node.id));
      }
    }
    for (const obj of wbState.objects || []) {
      if (wbIsLocked("object", obj) || wbFmtState.isolate?.outside("object", obj)) continue;
      if (wbPointInPolygon(obj.x + obj.width / 2, obj.y + obj.height / 2, points)) {
        wbMultiSelection.add(wbMultiKey("object", obj.id));
      }
    }
    for (const sketch of wbState.sketches) {
      const parsed = wbSketchParsedData(sketch);
      if (!parsed) continue; // a link sketch: nothing here to select as a shape
      if (parsed.locked || wbFmtState.isolate?.outside("sketch", sketch)) continue;
      const bbox = wbPathBBox(parsed.d);
      if (bbox && wbPointInPolygon(bbox.minX + bbox.width / 2, bbox.minY + bbox.height / 2, points)) {
        wbMultiSelection.add(wbMultiKey("sketch", sketch.id));
      }
    }
    //: **A sweep that caught one thing selects that thing properly.**
    //: Reported: "shapes like circles and lines dont visibly select and show
    //: anchor points when I highlight select over them". A drawn shape is a
    //: sketch, and a sketch's selection box and its eight anchors are drawn
    //: by `wbRenderSketchHandles`, which only ever runs for the *single*
    //: selection: a marquee cleared that and put the id in the multi set
    //: instead, where a sketch had no decoration of any kind. So sweeping
    //: over a circle really did select it and really did show nothing.
    //: Promoting a one-item sweep is the honest fix rather than a second
    //: decoration: one item selected by a sweep and the same item selected by
    //: a click are the same selection, and should look and behave the same.
    //: (A sweep over several still has no one box to hang anchors off, which
    //: is why the class also has a visible style of its own now.)
    wbSelectedItem = null;
    if (wbMultiSelection.size === 1) {
      const key = [...wbMultiSelection][0];
      const sep = key.indexOf(":");
      wbMultiSelection.clear();
      wbSelectedItem = { kind: key.slice(0, sep), id: Number(key.slice(sep + 1)) };
    }
    wbMarqueeJustSelected = true;
    wbApplySelectionHighlight();
  });

  // Images: paste, drag-and-drop, or the upload button, asked for
  // directly, and all three funnel through the same upload+place path
  // `handleFileUpload` already established for notes (POST /media/upload,
  // then a placed reference, a board object here instead of markdown text).
  //: The most the notebook keeps of one upload (`routes_files.MAX_FILE_BYTES`), said before the
  //: upload starts and not after a 50 MB request fails (audit 1028 B28).
  const wbPictureCap = 50 * 1024 * 1024;
  function wbPictureTooBig() {
    toast("That picture is over 50 MB, the most the notebook keeps. Shrink it and try again.", "info");
  }

  //: A picture pasted as an address or as markup, not as a file (audit 1028 B28): `text/uri-list`
  //: naming a picture, or the first `<img>` of `text/html` when the plain text is empty or just
  //: that address (a paragraph with a picture in it is still a paragraph).
  function wbPastedPictureAddress(data, html) {
    const plain = (data?.getData("text/plain") || "").trim();
    const listed = (data?.getData("text/uri-list") || "").split(/\r?\n/).map((line) => line.trim()).find((line) => line && !line.startsWith("#"));
    if (listed && /^data:image\/|\.(?:png|jpe?g|gif|webp|avif|bmp|svg)(?:[?#]|$)/i.test(listed)) return listed;
    if (!html) return "";
    const src = new DOMParser().parseFromString(html, "text/html").querySelector("img[src]")?.getAttribute("src") || "";
    return src && (!plain || plain === src) ? src : "";
  }

  //: A `data:` picture is decoded to a file; one already in the notebook is placed as it is; a web
  //: address is refused with the reason, since the page may not fetch the web (`connect-src 'self'`).
  async function wbPlacePastedAddress(src, x, y) {
    const inline = /^data:(image\/[\w.+-]+);base64,([\s\S]*)$/i.exec(src);
    if (inline) {
      if (inline[2].length * 0.75 > wbPictureCap) return wbPictureTooBig();
      const bytes = Uint8Array.from(atob(inline[2]), (char) => char.charCodeAt(0));
      //: The upload route reads the type from the name's extension.
      const ext = inline[1].slice(6).toLowerCase().replace("jpeg", "jpg").replace("svg+xml", "svg");
      return wbPlaceUploadedImage(new File([bytes], `pasted-picture.${ext}`, { type: inline[1] }), x, y);
    }
    const local = src.startsWith(`${location.origin}/media/`) ? src.slice(location.origin.length) : src;
    if (local.startsWith("/media/")) return wbPlaceImageUrl(local, x, y);
    toast("This notebook works offline, so a picture from the web is not fetched. Save the picture, then paste or drop the file.");
  }

  async function wbPlaceUploadedImage(file, x, y) {
    if (wbFmtState.pdf?.isPdf(file)) return wbFmtState.pdf.place(file, x, y);
    if (!file) return;
    //: Said, not dropped silently (L-whiteboard-36): a board takes pictures and PDFs.
    if (!file.type?.startsWith("image/")) return toast(`A board takes pictures and PDFs; ${file.name || "that file"} is neither.`, "info");
    if (file.size > wbPictureCap) return wbPictureTooBig();
    try {
      const formData = new FormData();
      formData.append("file", file);
      //: Board-only until Save to Library: not listed, not read, not captioned (K18).
      formData.append("board", "true");
      const uploaded = await apiJson("/media/upload", {
        method: "POST",
        headers: authHeaders(),
        body: formData,
      });
      await wbPlaceImageUrl(uploaded.url, x, y);
    } catch (err) {
      toast(err.message || voiceLine("failed", { what: "add that image" }), true);
    }
  }

  async function wbPlaceImageUrl(url, x, y) {
    try {
      const img = new Image();
      const naturalSize = await new Promise((resolve) => {
        img.onload = () => resolve({ w: img.naturalWidth, h: img.naturalHeight });
        img.onerror = () => resolve({ w: 300, h: 200 });
        img.src = mediaSrc(url);
      });
      //: Its own size, shrunk only to sit inside the view (wbpaste-1026).
      const view = wbVisibleCanvasRect();
      const [vx0, vy0] = wbClientToBoard(view.left, view.top);
      const [vx1, vy1] = wbClientToBoard(view.right, view.bottom);
      const { width, height } = wbPasteImageSize(naturalSize.w, naturalSize.h, vx1 - vx0, vy1 - vy0);
      await wbCreateObject("image", { url }, x - width / 2, y - height / 2, width, height);
    } catch (err) {
      toast(err.message || voiceLine("failed", { what: "add that image" }), true);
    }
  }

  containerEl.addEventListener("dragover", (e) => {
    if (e.dataTransfer?.types?.includes("Files")) e.preventDefault();
  });
  containerEl.addEventListener("drop", (e) => {
    if (!e.dataTransfer?.files?.length) return;
    e.preventDefault();
    const [x, y] = getLogicalMouse(e);
    for (const file of e.dataTransfer.files) wbPlaceUploadedImage(file, x, y);
  });
  // Paste has no drop coordinate to place at, the centre of whatever's
  // currently in view reads better than always the same fixed board
  // position, which would stack every pasted image on top of the last one.
  //: On the document, not the canvas: a paste goes to whatever has the
  //: focus, which after a click on a rail tool is not the canvas. Taken only
  //: while a board is on screen and nothing that takes typing has the focus.
  document.addEventListener("paste", (e) => {
    if (!wbCommandsLive() || wbIsEditingTarget(e.target) || e.target.closest?.("input, textarea, select, .modal-overlay, .sheet-overlay")) return;
    wbBoardState.pasteArrived = true;
    const data = e.clipboardData;
    const html = data?.getData("text/html") || "";
    if (wbClipboard?.stamp && html.includes(`content="${wbClipboard.stamp}"`)) {
      e.preventDefault();
      wbPasteClipboard();
      return;
    }
    const files = [...(data?.items || [])].filter((i) => i.kind === "file").map((i) => i.getAsFile()).filter(Boolean);
    if (files.length) {
      e.preventDefault();
      const [x, y] = wbViewCentre();
      files.forEach((file, i) => wbPlaceUploadedImage(file, x + i * WB_GRID_SPACING, y + i * WB_GRID_SPACING));
      return;
    }
    const address = wbPastedPictureAddress(data, html);
    if (address) {
      e.preventDefault();
      const [x, y] = wbViewCentre();
      wbPlacePastedAddress(address, x, y);
      return;
    }
    const text = data?.getData("text/plain") || "";
    //: A map's paste of an outline under a topic is the map's own (MINDMAP
    //: §12.2, the map half of FEAT-09); here a map keeps its own clipboard.
    if (text.trim()) {
      //: Text on a map is the map's alone: falling through to the board's own
      //: clipboard pasted a stale copy beside the outline (wbpaste-1026 sweep).
      if (wbIsMap()) return;
      e.preventDefault();
      wbPasteText(text, wbPointerOnBoard());
      return;
    }
    if (wbClipboard) {
      e.preventDefault();
      wbPasteClipboard();
    }
  });
  document.addEventListener("copy", (e) => {
    if (wbCommandsLive() && !wbIsEditingTarget(e.target) && !e.target.closest?.("input, textarea, select")) wbOnBoardCopy(e);
  });
  document.addEventListener("cut", (e) => {
    if (wbCommandsLive() && !wbIsEditingTarget(e.target) && !e.target.closest?.("input, textarea, select")) wbOnBoardCopy(e);
  });
  const imageFileInput = document.getElementById("wb-image-file-input");
  document.getElementById("wb-add-image")?.addEventListener("click", () => imageFileInput?.click());
  //: The map topic's own picture input (§12.1 item 2's fourth), beside the
  //: board's: the same recipe, a different destination. `wbMapEditPicture`
  //: says which topic it was opened for.
  const mapPictureInput = document.getElementById("wb-map-picture-input");
  mapPictureInput?.addEventListener("change", async () => {
    const file = mapPictureInput.files && mapPictureInput.files[0];
    mapPictureInput.value = "";
    await wbMapTakePicture(file);
  });
  imageFileInput?.addEventListener("change", () => {
    const [x, y] = wbViewCentre();
    for (const file of imageFileInput.files) wbPlaceUploadedImage(file, x, y);
    imageFileInput.value = "";
  });

  // On `containerEl`, not `svgCanvas`, the same reasoning the eraser
  // listener above already follows. `svgCanvas` only ever sees a
  // pointerdown that lands directly on it or on something inside it; a
  // click that starts on a card (`#wb-html-layer`, a sibling painted on
  // top) never reaches it at all, which is the exact mechanism behind
  // "drawing over a note just moves the note". `containerEl` is an
  // ancestor of both layers, so it sees every pointerdown either way, 
  // and, with the card/object drags above now filtered out while a brush
  // tool is active, nothing else claims the gesture first.
  containerEl.addEventListener("pointerdown", (e) => {
    if (!WB_BRUSH_TOOLS.has(window.currentTool)) return;
    e.stopPropagation();
    isDrawing = true;
    const [x, y] = getLogicalMouse(e);
    
    currentDrawData = [[x, y, e.pressure]];
    currentDrawPath = document.createElementNS("http://www.w3.org/2000/svg", "path");
    // Fill only applies to the four closed shapes, and only when "no fill"
    // isn't checked: asked for directly ("fill colour/transparency...
    // options for no border/stroke or background").
    if ((WB_FILLABLE_SHAPES.has(window.currentTool) || WB_MORE_SHAPES[window.currentTool]) && !window.currentFillNone) {
      currentDrawPath.setAttribute("fill", window.currentFillColor);
      currentDrawPath.setAttribute("fill-opacity", String(window.currentFillOpacity / 100));
    } else {
      currentDrawPath.setAttribute("fill", "none");
    }
    currentDrawPath.setAttribute("stroke", window.currentStrokeNone ? "none" : window.currentStrokeColor);
    // A highlighter needs to be visibly wider and translucent, or it isn't a
    // highlighter: the sketch pad's own version of this exact control had
    // its opacity so low it was reported as invisible (HISTORY.md §46).
    currentDrawPath.setAttribute(
      "stroke-width",
      String(window.currentTool === "highlighter" ? wbHighlighterWidth(WB_STROKE_WIDTH) : WB_STROKE_WIDTH)
    );
    if (window.currentTool === "highlighter") {
      currentDrawPath.setAttribute("stroke-opacity", String(WB_HIGHLIGHTER_ALPHA));
      currentDrawPath.setAttribute("stroke-linecap", HIGHLIGHTER_STYLE.lineCap);
      // An inline style, not a class: the export clones these elements into a
      // standalone SVG where a stylesheet does not follow them, and
      // `el.style.x = ...` is the form this app's CSP allows (an inline
      // `style=` attribute in the markup is refused). The class beside it is
      // only a handle for `wbRefreshHighlighterBlend`.
      currentDrawPath.classList.add("wb-live-highlighter");
      currentDrawPath.style.mixBlendMode = wbHighlighterBlend();
    } else {
      currentDrawPath.setAttribute("stroke-linecap", "round");
    }
    currentDrawPath.setAttribute("stroke-linejoin", HIGHLIGHTER_STYLE.lineJoin);
    const dashArray = wbDashArray(window.currentDashStyle, WB_STROKE_WIDTH);
    if (dashArray) currentDrawPath.setAttribute("stroke-dasharray", dashArray);
    currentDrawPath.setAttribute("d", `M ${x} ${y}`);
    //: A solid pen or marker stroke is smoothed ink (whiteboard-ink-more.js): filled, its width following pressure.
    if ((window.currentTool === "draw" || window.currentTool === "highlighter") && wbFmtState.inkMore?.takesInk(window.currentDashStyle)) {
      currentDrawPath.__ink = { pointer: e.pointerType };
      wbFmtState.inkMore.liveStyle(currentDrawPath, window.currentStrokeNone ? "none" : window.currentStrokeColor, window.currentTool === "highlighter" ? WB_HIGHLIGHTER_ALPHA : null);
    }
    //: Over the cards while it is drawn: it lands on top (decision 43).
    document.getElementById("wb-overlay-zoom-group").appendChild(currentDrawPath);
  });
  
  //: The live stroke's outline when it is smoothed ink, "" when it is a plain stroke.
  function wbInkLiveD(last) {
    const ink = currentDrawPath?.__ink;
    if (!ink) return "";
    const tool = window.currentTool;
    const width = tool === "highlighter" ? wbHighlighterWidth(WB_STROKE_WIDTH) : WB_STROKE_WIDTH;
    return wbFmtState.inkMore.outline(currentDrawData, tool, width, ink.pointer, last);
  }
  containerEl.addEventListener("pointermove", (e) => {
    if (!isDrawing || !WB_BRUSH_TOOLS.has(window.currentTool)) return;
    e.stopPropagation();
    let [x, y] = getLogicalMouse(e);
    const tool = window.currentTool;
    if (tool !== "draw" && tool !== "highlighter" && tool !== "line" && tool !== "arrow") {
      [x, y] = wbDrawOutSnap(currentDrawData[0][0], currentDrawData[0][1], x, y, e);
    }
    
    if (window.currentTool === "draw" || window.currentTool === "highlighter") {
      // **Shift draws a straight run** (decision 7). Held mid-stroke it
      // replaces whatever has been drawn since the start point with one
      // segment, and letting go carries on freehand from there, which is how
      // a straightedge behaves and how every app that offers this does it.
      // The pen as well as the highlighter (INBOX 1352 gap 4).
      if (e.shiftKey) {
        const [sx0, sy0] = currentDrawData[0];
        currentDrawData.length = 1;
        currentDrawData.push([x, y, e.pressure]);
        currentDrawPath.setAttribute("d", wbInkLiveD(false) || `M ${sx0} ${sy0} L ${x} ${y}`);
        return;
      }
      currentDrawData.push([x, y, e.pressure]);
      const d = wbInkLiveD(false) || currentDrawData.map((pt, i) => (i === 0 ? `M ${pt[0]} ${pt[1]}` : `L ${pt[0]} ${pt[1]}`)).join(" ");
      currentDrawPath.setAttribute("d", d);
    } else {
      // Shape tools: only start and current point matter
      const [sx, sy] = currentDrawData[0];
      if (window.currentTool === "line" || window.currentTool === "arrow") {
        // One path, one or more subpaths, a plain SVG `d` string can hold
        // more than one `M`, and every subpath in it shares the same
        // stroke, so this is the shaft plus whichever head strokes the
        // *active tool's own* end-style calls for in a single element,
        // rather than several sketches that would each need their own undo
        // entry and could drift apart. Asked for directly: "regular lines
        // should also get line end options... arrow heads", the Line and
        // Arrow tools share the same "Line ends" control, so a plain line
        // *can* carry an arrowhead, but each tool keeps its own remembered
        // default (Line: none, Arrow: end): see the live-reported bug fix
        // on `currentLineEndStyle`/`currentArrowEndStyle` in `initWhiteboard`.
        const caps = wbToolCaps();
        const [ex, ey] = e.shiftKey ? wbSnap45(sx, sy, x, y) : [x, y];
        const liveHead = WB_STROKE_WIDTH * 4 + 6;
        const liveD = wbRegenerateShapeCaps(`M ${sx} ${sy} L ${ex} ${ey}`, caps.startCap, caps.endCap, liveHead);
        currentDrawPath.setAttribute("d", wbFmtState.inkMore?.trimShaft(liveD, caps.startCap, caps.endCap, liveHead, null, wbShaftEnd) || liveD);
      } else if (window.currentTool === "circle") {
        currentDrawPath.setAttribute("d", wbEllipseDrawD(sx, sy, x, y, e));
      } else {
        const d = wbClosedShapeD(window.currentTool, wbDragBox(sx, sy, x, y, e));
        if (d) currentDrawPath.setAttribute("d", d);
      }
    }
  });
  
  //: A stroke whose gesture is taken away (a tool switch, the browser's pointercancel, a release
  //: outside the board, which the container's own pointerup never hears) is dropped, not left
  //: as a live path with `isDrawing` still true (sm-1111 row 27).
  function wbAbandonStroke() {
    if (!isDrawing) return;
    isDrawing = false;
    currentDrawPath?.remove();
    currentDrawPath = null;
    currentDrawData = [];
    wbClearAlignmentGuides();
  }
  //: **A drag whose pointer is taken away is put back and let go** (sm-1111 row 27; this is the
  //: card, object, shape and link drags' half of `wbAbandonStroke`). A pointercancel, a window
  //: blur, a tool switch or a mouse move with no button held (the `mouseup` went to a native drag,
  //: another window or the OS) all mean the hand is gone. Measured before in Chromium, a card and a
  //: text box with a lost `mouseup`: the gesture stayed live, the item followed a buttonless hover
  //: and the delete target stayed up. d3-drag lets go of its window listeners only on `mouseup`,
  //: so one is sent after the cancel; the cancelled gesture's own handlers then save nothing.
  function wbDropLostGesture() {
    if (!wbCancelGesture()) return;
    window.dispatchEvent(new MouseEvent("mouseup", { view: window }));
  }
  window.addEventListener("pointercancel", wbDropLostGesture, true);
  window.addEventListener("blur", wbDropLostGesture);
  window.addEventListener("pointermove", (e) => {
    if (wbGesture && e.pointerType === "mouse" && e.buttons === 0) wbDropLostGesture();
  }, true);
  window.addEventListener("pointercancel", wbAbandonStroke);
  window.addEventListener("pointerup", wbAbandonStroke);
  containerEl.addEventListener("pointerup", async (e) => {
    if (!isDrawing || !WB_BRUSH_TOOLS.has(window.currentTool)) return;
    e.stopPropagation();
    isDrawing = false;
    wbClearAlignmentGuides();
    
    const [x, y] = getLogicalMouse(e);
    const [sx, sy] = currentDrawData[0];
    
    // A plain click with no drag, reported directly: the pen tool "doesn't
    // respond to a single click, only a drag", which the sketch pad's own
    // pen never had wrong (see `sketchEnd`'s own `!sketchMoved` branch, the
    // same fix mirrored here). A `moveto` with no `lineto` after it draws
    // nothing at all, so a stationary click has to add a near-zero-length
    // segment, round linecaps turn that into a visible dot, rather than
    // being discarded as "no shape to save".
    const isFreehand = window.currentTool === "draw" || window.currentTool === "highlighter";
    if (isFreehand && currentDrawData.length < 2) {
      currentDrawPath.setAttribute("d", wbInkLiveD(true) || `M ${sx} ${sy} L ${sx} ${sy + 0.1}`);
    } else if (isFreehand) {
      const settled = wbInkLiveD(true);
      if (settled) currentDrawPath.setAttribute("d", settled);
    } else if (!isFreehand && Math.abs(x - sx) < 2 && Math.abs(y - sy) < 2) {
      // Shape tools (line/arrow/rect/circle) need an actual drag to have a
      // size: a zero-size shape isn't a reasonable click-to-draw default
      // the way a pen dot is, so these are still discarded.
      if (currentDrawPath) currentDrawPath.remove();
      currentDrawPath = null;
      return;
    }
    
    // Save sketch to API. The backend schema has no width/opacity/fill/dash
    // columns, so all of it has to travel inside `data`, otherwise a saved
    // stroke reloads at the hardcoded 3px default regardless of what
    // #wb-stroke-width was actually set to when it was drawn (a real bug,
    // caught while wiring that control up: only the highlighter branch here
    // ever saved its own width; a plain pen/line/shape stroke silently lost
    // whatever size it was actually drawn at the moment the page reloaded).
    const d = currentDrawPath.getAttribute("d");
    const isHighlighter = window.currentTool === "highlighter";
    const more = WB_MORE_SHAPES[window.currentTool];
    const isFillable = WB_FILLABLE_SHAPES.has(window.currentTool) || Boolean(more);
    const blob = {
      d,
      color: currentStrokeColor,
      width: isHighlighter ? wbHighlighterWidth(WB_STROKE_WIDTH) : WB_STROKE_WIDTH,
      shape: more ? "custom" : window.currentTool,
    };
    if (more?.area) blob.label_area = more.area;
    if (currentDrawPath.__ink) Object.assign(blob, { ink: 1 }, wbFmtState.inkMore.keepPoints(currentDrawData, wbPathBBox(d)));
    //: The ends are stored by kind, so the bar and the Format panel read
    //: what was drawn rather than sniffing it out of the path.
    if (window.currentTool === "line" || window.currentTool === "arrow") Object.assign(blob, wbToolCaps());
    if (isHighlighter) {
      blob.opacity = WB_HIGHLIGHTER_ALPHA;
    } else {
      if (window.currentDashStyle !== "solid") blob.dash = window.currentDashStyle;
      if (window.currentStrokeNone) blob.noStroke = true;
      if (isFillable && !window.currentFillNone) {
        blob.fill = window.currentFillColor;
        blob.fillOpacity = window.currentFillOpacity / 100;
      }
    }
    //: An arrow or a line that starts or ends on a shape is a connector bound
    //: to it (the wb ledger, 10-25: the Line tool stayed a loose path). Its
    //: ends are the tool's own, so a line binds with none.
    const bound = window.currentTool === "arrow" || window.currentTool === "line" ? wbBoundArrowData(sx, sy, x, y, 10 / zoomK(), blob) : null;
    //: The board's default style starts every drawn shape, line, pen stroke and highlighter stroke, each under its own kind.
    const group = isFreehand ? (isHighlighter ? "highlighter" : "pen") : "shape";
    const drawn = wbFmtState.board?.withDefaults(group, blob, { fillable: isFillable }) ?? blob;
    const sketchData = {
      data: JSON.stringify(bound || drawn),
      x: 0,
      y: 0,
      z: wbStackNewZ("sketch"),
      board_id: window.currentBoardId
    };

    try {
      const res = await apiJson("/whiteboard/sketches", { method: "POST", body: JSON.stringify(sketchData) });
      wbState.sketches.push(res);
      wbPushUndo({ action: "create", kind: "sketch", id: res.id });
      // Hand off to renderWhiteboard's own data-bound element for this
      // sketch: a real bug found while adding the eraser: this raw `<path>`
      // is not part of the `g.sketch-group` selection renderWhiteboard binds
      // wbState.sketches to, so a stroke just drawn had no way to be deleted
      // or erased until a full reload re-fetched it from the server and
      // rendered it "properly" the first time.
      currentDrawPath.remove();
      //: A drawn shape is selected and the tool returns to Select (decision
      //: 44); the pen and highlighter keep their tool so strokes continue.
      if (!isFreehand) {
        renderWhiteboardNow();
        wbSelectToolRef?.("select");
        selectWbItem("sketch", res.id);
      } else {
        wbScheduleRender();
      }
    } catch (err) {
      //: Said on screen, not only in a console nobody has open (audit 1028 B22).
      toast(voiceLine("failed", { what: "save that drawing", why: err.message }), true);
      if (currentDrawPath) currentDrawPath.remove();
    }

    currentDrawPath = null;
    currentDrawData = [];
  });

  // Drop handler for Library
  document.getElementById("whiteboard-container").addEventListener("dragover", (e) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "copy";
  });
  
  document.getElementById("whiteboard-container").addEventListener("drop", async (e) => {
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
    toast(voiceLine("failed", { what: "add that note to the board", why: why }), true);
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

window.currentBoardId = null;

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
    toast(voiceLine("failed", { what: "open that board", why: err.message }), true);
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
        toast(err.message || voiceLine("failed", { what: "rename that board" }), true);
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
    const label = document.querySelector(`.wb-object[data-id="${root.id}"] .wb-map-text`);
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
      toast(err.message || voiceLine("failed", { what: "create that board" }), true);
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
      }).catch((err) => toast(err.message || voiceLine("failed", { what: "add the root topic" }), true));
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
    toast(err.message || voiceLine("failed", { what: "create that board" }), true);
  }
}

// --- Sketch move/resize (ROADMAP.md Tier 2 §11 / user-reported: "can't
// move objects drawn on the whiteboard", "can't resize... can't shorten
// lines") -------------------------------------------------------------------
//
// Cards and objects have real x/y/width/height columns; a sketch is just an
// SVG path string (`d`), so "move" and "resize" both mean rewriting the
// coordinates inside that string rather than moving a positioned element.
// This is *not* a general SVG path parser, it only has to round-trip
// exactly the commands this app's own drawing tools ever emit (see the
// `pointermove` handler above: `M`/`L` for pen and lines, `C` for link
// curves, `h`/`v`/`Z` for rect, `a` for circle): a path from anywhere else
// was never a possibility, so there is no reason to handle SVG's full
// command set.
//: `rotate` (degrees, about `anchorX`/`anchorY`) is what a sketch didn't
//: have: cards and objects rotate (a drag handle + a stored `rotation`
//: column), but a sketch *is* its path data, and rotating a path correctly
//: needs care `dx`/`sx` alone don't: `h`/`v` (a purely horizontal/vertical
//: relative line: this app's own rect tool emits them) can't represent a
//: rotated line at all, since rotating "purely horizontal" by anything
//: other than a multiple of 90° makes it not horizontal any more, so each
//: becomes an absolute `L` instead once rotation is non-zero. `a` (the
//: circle tool's arc pairs) stays relative, a rotation adds straight onto
//: the arc's own `x-axis-rotation` parameter and rotates its endpoint
//: delta; `rx`/`ry`/large-arc/sweep are unchanged, which is exact for a
//: *pure* rotation (no reflection): this app never emits a negative
//: scale, so that combination doesn't need handling here.
function wbTransformPathD(d, { dx = 0, dy = 0, sx = 1, sy = 1, rotate = 0, anchorX = 0, anchorY = 0 } = {}) {
  const theta = (rotate * Math.PI) / 180;
  const cos = Math.cos(theta), sin = Math.sin(theta);
  const mapPoint = (x, y) => {
    const scaledX = anchorX + (x - anchorX) * sx;
    const scaledY = anchorY + (y - anchorY) * sy;
    const relX = scaledX - anchorX, relY = scaledY - anchorY;
    return [anchorX + relX * cos - relY * sin + dx, anchorY + relX * sin + relY * cos + dy];
  };
  // A relative delta scales the same way a point's offset from the anchor
  // does, but never translates (dx/dy are a position's own change, not a
  // vector's).
  const mapDelta = (ddx, ddy) => {
    const scaledX = ddx * sx, scaledY = ddy * sy;
    return [scaledX * cos - scaledY * sin, scaledX * sin + scaledY * cos];
  };
  const tokens = d.match(/[MLCHVAZmlchvaz]|-?\d*\.?\d+(?:[eE]-?\d+)?/g);
  if (!tokens) return d;
  let i = 0, px = 0, py = 0; // current point, tracked only for h/v → L under rotation
  const out = [];
  while (i < tokens.length) {
    const cmd = tokens[i++];
    if (cmd === "M" || cmd === "L") {
      const x = parseFloat(tokens[i++]), y = parseFloat(tokens[i++]);
      const [mx, my] = mapPoint(x, y);
      out.push(cmd, mx, my);
      px = x; py = y;
    } else if (cmd === "C") {
      const n = [];
      for (let k = 0; k < 6; k++) n.push(parseFloat(tokens[i++]));
      const [x1, y1] = mapPoint(n[0], n[1]);
      const [x2, y2] = mapPoint(n[2], n[3]);
      const [x3, y3] = mapPoint(n[4], n[5]);
      out.push(cmd, x1, y1, x2, y2, x3, y3);
      px = n[4]; py = n[5];
    } else if (cmd === "h") {
      const ddx = parseFloat(tokens[i++]);
      if (rotate) {
        const [mx, my] = mapPoint(px + ddx, py);
        out.push("L", mx, my);
      } else {
        out.push(cmd, ddx * sx);
      }
      px += ddx;
    } else if (cmd === "v") {
      const ddy = parseFloat(tokens[i++]);
      if (rotate) {
        const [mx, my] = mapPoint(px, py + ddy);
        out.push("L", mx, my);
      } else {
        out.push(cmd, ddy * sy);
      }
      py += ddy;
    } else if (cmd === "a") {
      const rx = parseFloat(tokens[i++]) * sx, ry = parseFloat(tokens[i++]) * sy;
      const rot = parseFloat(tokens[i++]) + rotate, large = tokens[i++], sweep = tokens[i++];
      const edx = parseFloat(tokens[i++]), edy = parseFloat(tokens[i++]);
      const [mdx, mdy] = mapDelta(edx, edy);
      out.push(cmd, rx, ry, rot, large, sweep, mdx, mdy);
      px += edx; py += edy;
    } else if (cmd === "A") {
      //: The circle tool writes absolute arcs (`wbEllipseDrawD`), and this walk
      //: knew only the relative spelling, so it fell into the "unrecognised
      //: token" branch below and handed the path back unchanged: a circle
      //: could be selected and never moved, resized or rotated (the owner,
      //: 2026-09-14: "I still cant drag and select shapes"; measured in
      //: `scratchpad/ui-sweeps/marquee.js`, the pen strokes moved and every
      //: circle stayed). The endpoint is a point, so it maps as one.
      const rx = parseFloat(tokens[i++]) * sx, ry = parseFloat(tokens[i++]) * sy;
      const rot = parseFloat(tokens[i++]) + rotate, large = tokens[i++], sweep = tokens[i++];
      const ex = parseFloat(tokens[i++]), ey = parseFloat(tokens[i++]);
      const [mx, my] = mapPoint(ex, ey);
      out.push(cmd, rx, ry, rot, large, sweep, mx, my);
      px = ex; py = ey;
    } else if (cmd === "H") {
      const x = parseFloat(tokens[i++]);
      const [mx, my] = mapPoint(x, py);
      out.push("L", mx, my);
      px = x;
    } else if (cmd === "V") {
      const y = parseFloat(tokens[i++]);
      const [mx, my] = mapPoint(px, y);
      out.push("L", mx, my);
      py = y;
    } else if (cmd === "Z" || cmd === "z") {
      out.push(cmd);
    } else {
      return d; // an unrecognised token: leave the path untouched rather than corrupt it
    }
  }
  return out.join(" ");
}

//: The bounding box of a path this app drew, walked the same way a real SVG
//: renderer would (tracking the pen's current point through relative
//: commands) rather than just min/maxing every raw number, `h`/`v`/`a`'s
//: numbers are deltas and radii, not coordinates, and mixing them into a
//: coordinate min/max would produce a nonsense box.
function wbPathBBox(d) {
  const tokens = d.match(/[MLCHVAZmlchvaz]|-?\d*\.?\d+(?:[eE]-?\d+)?/g);
  if (!tokens) return null;
  let i = 0, px = 0, py = 0;
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  const visit = (x, y) => {
    minX = Math.min(minX, x); minY = Math.min(minY, y);
    maxX = Math.max(maxX, x); maxY = Math.max(maxY, y);
  };
  while (i < tokens.length) {
    const cmd = tokens[i++];
    if (cmd === "M" || cmd === "L") {
      px = parseFloat(tokens[i++]); py = parseFloat(tokens[i++]);
      visit(px, py);
    } else if (cmd === "C") {
      const n = [];
      for (let k = 0; k < 6; k++) n.push(parseFloat(tokens[i++]));
      visit(n[0], n[1]); visit(n[2], n[3]); visit(n[4], n[5]);
      px = n[4]; py = n[5];
    } else if (cmd === "h") {
      px += parseFloat(tokens[i++]);
      visit(px, py);
    } else if (cmd === "v") {
      py += parseFloat(tokens[i++]);
      visit(px, py);
    } else if (cmd === "a" || cmd === "A") {
      const rx = parseFloat(tokens[i++]), ry = parseFloat(tokens[i++]);
      i += 3; // x-axis-rotation, large-arc-flag, sweep-flag: unused for a bbox
      let ex = parseFloat(tokens[i++]), ey = parseFloat(tokens[i++]);
      //: The circle tool writes absolute arcs (`A`, `wbEllipseDrawD`), and this
      //: parser only knew the relative spelling: a circle's box collapsed to
      //: its first point, so a marquee dragged over one selected nothing
      //: unless it happened to cover that point (INBOX 252, the owner: "when
      //: I drag over shapes with the select tool, they dont get selected").
      if (cmd === "A") { ex -= px; ey -= py; }
      // Exact for the axis-aligned circle/ellipse this tool ever draws: two
      // half-arcs whose shared chord's midpoint is the ellipse's own centre.
      const midX = px + ex / 2, midY = py + ey / 2;
      visit(midX - rx, midY - ry);
      visit(midX + rx, midY + ry);
      px += ex; py += ey;
    } else if (cmd === "H") {
      px = parseFloat(tokens[i++]);
      visit(px, py);
    } else if (cmd === "V") {
      py = parseFloat(tokens[i++]);
      visit(px, py);
    }
    // Z/z closes back to the last M, doesn't move the pen for bbox purposes.
  }
  return isFinite(minX) ? { minX, minY, maxX, maxY, width: maxX - minX, height: maxY - minY } : null;
}

//: A handle drag's dx/dy (board-space) turned into the same
//: {sx, sy, anchorX, anchorY} shape `wbTransformPathD` takes: the opposite
//: corner/edge from whichever handle moved stays fixed, mirroring
//: `resizeDrag`'s own width/height-and-floor logic for image/text objects.
const WB_SKETCH_MIN_SIZE = 10;
//: A corner resize held to the proportions it started with: whichever axis
//: the pointer has stretched further (as a fraction of its own start) wins,
//: and the other follows it, so the corner stays under the pointer along the
//: axis being pulled hardest.
function wbKeepAspect(startW, startH, w, h) {
  const scale = Math.max(w / startW, h / startH);
  return { w: startW * scale, h: startH * scale };
}

//: **Alt resizes from the centre** (row 1600, the audit's C3; Figma, tldraw
//: and PowerPoint all hold it): the side opposite the handle moves by as much
//: the other way, so the box grows about its middle. A box's new frame from
//: where the gesture began (`start` is `{x, y, w, h}`), for the card and the
//: object handles; Shift on a corner still keeps the proportions.
function wbResizeBox(start, handle, dx, dy, shiftKey, altKey, min) {
  const grow = altKey ? 2 : 1;
  let w = start.w, h = start.h;
  if (handle.includes("e")) w = Math.max(min, start.w + grow * dx);
  if (handle.includes("w")) w = Math.max(min, start.w - grow * dx);
  if (handle.includes("s")) h = Math.max(min, start.h + grow * dy);
  if (handle.includes("n")) h = Math.max(min, start.h - grow * dy);
  if (handle.length === 2 && shiftKey) ({ w, h } = wbKeepAspect(start.w, start.h, w, h));
  if (altKey) return { x: start.x + (start.w - w) / 2, y: start.y + (start.h - h) / 2, w, h };
  return {
    x: handle.includes("w") ? start.x + start.w - w : start.x,
    y: handle.includes("n") ? start.y + start.h - h : start.y,
    w,
    h,
  };
}

function wbSketchResizeTransform(bbox, handle, dx, dy, shiftKey, altKey = false) {
  const { minX, minY, maxX, maxY } = bbox;
  if (altKey) {
    //: About the middle (see `wbResizeBox`): the same frame maths, read back
    //: as a scale about the centre.
    const box = wbResizeBox({ x: minX, y: minY, w: maxX - minX || 1, h: maxY - minY || 1 },
      handle, dx, dy, shiftKey, true, WB_SKETCH_MIN_SIZE);
    return {
      sx: handle.includes("e") || handle.includes("w") ? box.w / (maxX - minX || 1) : 1,
      sy: handle.includes("n") || handle.includes("s") ? box.h / (maxY - minY || 1) : 1,
      anchorX: (minX + maxX) / 2,
      anchorY: (minY + maxY) / 2,
    };
  }
  let newMinX = minX, newMaxX = maxX, newMinY = minY, newMaxY = maxY;
  if (handle.includes("e")) newMaxX = Math.max(minX + WB_SKETCH_MIN_SIZE, maxX + dx);
  if (handle.includes("w")) newMinX = Math.min(maxX - WB_SKETCH_MIN_SIZE, minX + dx);
  if (handle.includes("s")) newMaxY = Math.max(minY + WB_SKETCH_MIN_SIZE, maxY + dy);
  if (handle.includes("n")) newMinY = Math.min(maxY - WB_SKETCH_MIN_SIZE, minY + dy);
  // Reported directly: shift while resizing didn't snap to a square. Only a
  // corner handle ("nw"/"ne"/"se"/"sw", length 2) has two free axes to lock
  // together; the larger of the two free-form extents wins, and the corner
  // *opposite* the one being dragged stays anchored, matching `anchorX`/
  // `anchorY` below rather than recentring the shape.
  //: Shift keeps the shape's own proportions (see nodeResizeDrag), which is
  //: still a square for a shape that was drawn square.
  const isCorner = handle.length === 2;
  if (isCorner && shiftKey) {
    const { w, h } = wbKeepAspect(maxX - minX || 1, maxY - minY || 1, newMaxX - newMinX, newMaxY - newMinY);
    if (handle.includes("e")) newMaxX = newMinX + w; else newMinX = newMaxX - w;
    if (handle.includes("s")) newMaxY = newMinY + h; else newMinY = newMaxY - h;
  }
  const oldW = maxX - minX || 1, oldH = maxY - minY || 1;
  const sx = handle.includes("e") || handle.includes("w") ? (newMaxX - newMinX) / oldW : 1;
  const sy = handle.includes("n") || handle.includes("s") ? (newMaxY - newMinY) / oldH : 1;
  return { sx, sy, anchorX: handle.includes("w") ? maxX : minX, anchorY: handle.includes("n") ? maxY : minY };
}

//: A sketch's own `data` blob, whether it's `{d, color}` or the wider
//: `{d, color, width, opacity}` a highlighter carries (HISTORY.md): parsed
//: once so move/resize can rewrite just `d` and leave every other field
//: (colour, the highlighter's width/opacity) exactly as it was.
// Detected from the path data itself, not a stored "kind" field (sketches
// don't have one): rect/triangle/diamond's own preview-drawing code (above,
// in the pointermove handler) closes its path with Z; circle instead
// returns to its start point via two arc ("a") commands. Line/arrow/pen/
// highlighter never do either.
function wbSketchIsClosedShape(sketch) {
  const d = wbSketchParsedData(sketch)?.d || "";
  const trimmed = d.trim();
  return /[Zz]\s*$/.test(trimmed) || /\ba\s/i.test(trimmed);
}

// whiteboard-sketch-text.js: whiteboard-sketch-text.js: text inside shapes, fit-to-shape, connector labels an (moved out, L286).

//: The middle of a link's shaft: the first subpath of its drawn `d`, before
//: any arrowhead strokes appended after it, measured on one hidden path so
//: a curve's middle is where the curve is rather than the chord's.
let wbLinkMeasurePath = null;

// Paint-bucket tool: recolour whatever's clicked with the main toolbar's
// stroke colour. Closed shapes (rect/circle/triangle/diamond) get their
// fill set, since that's the area a bucket click reads as "inside" of;
// anything else (line/arrow/pen stroke) has no interior, so its stroke is
// recoloured instead, the same colour the rail's ink swatch shows.
async function wbBucketFillSketch(sketch) {
  const color = document.getElementById("wb-rail-ink")?.value || "#3355ff";
  let parsed;
  try {
    parsed = JSON.parse(sketch.data);
  } catch {
    return;
  }
  if (parsed && WB_FILLABLE_SHAPES.has(parsed.shape)) {
    await wbSaveSketchProps(sketch, { fill: color });
  } else {
    await wbSaveSketchProps(sketch, { color });
  }
  wbScheduleRender();
}

//: True once a sketch's `d` has more than one `M`, every shape this app's
//: own tools ever draw uses exactly one *except* an arrow (shaft + one or
//: two head subpaths, `wbArrowHeadPath`'s own `M`s). Good enough to tell
//: "this is an arrow" apart from a line/rect/circle/triangle/diamond/pen
//: stroke without a dedicated `kind` field on every sketch.
function wbSketchIsArrow(d) {
  return (d.match(/M/g) || []).length > 1;
}

//: **A straight line takes ends whether or not it has one yet** (the owner,
//: 2026-10-11: a plain line offered no arrowheads, because the bar showed the
//: end lists only for a path that already carried one).
function wbSketchTakesCaps(parsed) {
  if (!parsed || typeof parsed.d !== "string") return false;
  if (!/^M\s*-?[\d.]+(?:e-?\d+)?\s+-?[\d.]+(?:e-?\d+)?\s+L\s*-?[\d.]+(?:e-?\d+)?\s+-?[\d.]+(?:e-?\d+)?(?:\s+M|\s*$)/.test(parsed.d)) return false;
  return parsed.shape === "line" || parsed.shape === "arrow" || wbSketchIsArrow(parsed.d);
}

//: What the Line or Arrow tool puts on its two ends: which ends (`End`,
//: `Start`, `Both`, `Plain`) and the mark (`window.currentArrowHead`).
function wbToolCaps() {
  const style = (window.currentTool === "line" ? window.currentLineEndStyle : window.currentArrowEndStyle) || "none";
  const head = WB_CAP_KINDS.includes(window.currentArrowHead) ? window.currentArrowHead : "arrow";
  return {
    startCap: style === "start" || style === "both" ? head : "none",
    endCap: style === "end" || style === "both" ? head : "none",
  };
}

//: Rebuilds a line/arrow's own two end caps from its shaft, the shaft is
//: always the sketch's first subpath, `M sx sy L ex ey` (every arrow this
//: app draws starts that way), so either end's cap can be changed after
//: the fact without needing to have stored which shape was originally
//: chosen. Independently per end (`WB_CAP_KINDS` each): asked for
//: directly ("a full line/arrow end-cap system... circle/square/multi-line
//: ends"), replacing the single shared arrowhead-only version.
function wbRegenerateShapeCaps(d, startCap, endCap, headLen, sizes) {
  const m = d.match(/^M\s*(-?[\d.]+(?:e-?\d+)?)\s+(-?[\d.]+(?:e-?\d+)?)\s+L\s*(-?[\d.]+(?:e-?\d+)?)\s+(-?[\d.]+(?:e-?\d+)?)/);
  if (!m) return d;
  const sx = parseFloat(m[1]), sy = parseFloat(m[2]), ex = parseFloat(m[3]), ey = parseFloat(m[4]);
  const angle = Math.atan2(ey - sy, ex - sx);
  let out = `M ${sx} ${sy} L ${ex} ${ey}`;
  if (endCap && endCap !== "none") out += " " + wbCapPath(endCap, ex, ey, angle, headLen, sizes?.endSize);
  if (startCap && startCap !== "none") out += " " + wbCapPath(startCap, sx, sy, angle + Math.PI, headLen, sizes?.startSize);
  return out;
}

//: What style a drawn line/arrow's own path is *actually* carrying,
//: needed because the properties panel used to just show whatever the
//: active drawing tool's current default was (live-reported bug, same
//: session as the Line-tool-always-drew-an-arrowhead one above), which
//: lies the moment a sketch's real style differs from that default.
//: `wbArrowHeadPath` always starts its own subpath at the tip it's drawn
//: for, so a head is detected by which of the shaft's two endpoints each
//: extra `M` lands on: exact, not guessed, since these are the same
//: coordinates the shaft itself was drawn from.
function wbDetectArrowStyle(d) {
  const m = d.match(/^M\s*(-?[\d.]+(?:e-?\d+)?)\s+(-?[\d.]+(?:e-?\d+)?)\s+L\s*(-?[\d.]+(?:e-?\d+)?)\s+(-?[\d.]+(?:e-?\d+)?)/);
  if (!m) return "none";
  const sx = parseFloat(m[1]), sy = parseFloat(m[2]), ex = parseFloat(m[3]), ey = parseFloat(m[4]);
  let hasEnd = false, hasStart = false;
  //: **Scanned from *after* the shaft's own `M`, not from the start of `d`.**
  //: Reported: "arrow drawn shows both caps as Arrow in properties" -
  //: reproduced live: an arrow with only an end head stored no `startCap`/
  //: `endCap` fields at all (an older/legacy shape), so this ran, and `m[0]`
  //: (the shaft's own leading `M sx sy L ex ey`, matched above) begins with
  //: exactly the same `M sx sy` a *real* start-cap marker would - the loop
  //: below used to scan the whole string including that leading `M`, so
  //: every plain shaft with no start cap at all still measured a
  //: zero-distance "hit" on its own start point and reported one anyway.
  //: Slicing it off leaves only the head subpaths `wbArrowHeadPath` actually
  //: appended, which is what this function is supposed to be reading.
  for (const extra of d.slice(m[0].length).matchAll(/M\s*(-?[\d.]+(?:e-?\d+)?)\s+(-?[\d.]+(?:e-?\d+)?)/g)) {
    const x = parseFloat(extra[1]), y = parseFloat(extra[2]);
    if (Math.hypot(x - ex, y - ey) < 0.5) hasEnd = true;
    else if (Math.hypot(x - sx, y - sy) < 0.5) hasStart = true;
  }
  if (hasEnd && hasStart) return "both";
  if (hasEnd) return "end";
  if (hasStart) return "start";
  return "none";
}

//: A drawn line/arrow's own two cap kinds, the explicit `startCap`/
//: `endCap` fields (any of `WB_CAP_KINDS`) if this sketch has them, or
//: `wbDetectArrowStyle`'s older binary read translated to "arrow"/"none"
//: for one saved before the full end-cap system existed. Explicit fields
//: rather than shape-sniffing every cap kind out of the raw path: circle
//: and square are geometrically ambiguous with plenty of things a pen
//: stroke could also draw, where an arrow's two-line V (`wbDetectArrowStyle`)
//: is not: so a *new* cap choice is trusted and stored, and only a link
//: with no stored choice at all falls back to inferring one.
function wbSketchCaps(parsed) {
  const sizes = { startSize: parsed.startCapSize || null, endSize: parsed.endCapSize || null };
  if (parsed.startCap !== undefined || parsed.endCap !== undefined) {
    return { startCap: parsed.startCap || "none", endCap: parsed.endCap || "none", ...sizes };
  }
  const legacy = wbDetectArrowStyle(parsed.d);
  return {
    startCap: legacy === "start" || legacy === "both" ? "arrow" : "none",
    endCap: legacy === "end" || legacy === "both" ? "arrow" : "none",
    ...sizes,
  };
}

//: Two draggable handles at a selected link's own resolved endpoints, 
//: asked for directly: "I should be able to move the points where lines,
//: arrows and links connect on objects to other points or even make it a
//: dangling unattached point not attached to an object." Dragging one
//: rewrites *that end's* own reference (`sourceId`/`sourceAnchor` or
//: `targetId`/`targetAnchor`, reattach, snapping to the nearest of the
//: hovered card's 8 fixed anchors the same way creating a link already
//: does) or, released over empty canvas, `sourcePoint`/`targetPoint`, a
//: fixed board-space point with no card at all. `wbResolveLinkEndpoints`
//: already reads both shapes, so nothing else needs to change to render one.
// Remove every sketch handle group, from **both** layers it can live in.
//
// Reported with a screenshot: "when I change where links are connected on
// notes or objects on the whiteboard, these weird small circles are left
// hanging." They are link endpoint handles, and the cause was a layer split
// that the cleanup never caught up with, handles for a *link* are appended to
// `#wb-overlay-zoom-group` (they sit on a card's own border, which the base
// SVG paints underneath the card's HTML, so they had to move up a layer),
// while both existing clears only ever swept `#wb-zoom-group`. Every
// re-render appended a fresh group and none of the old ones was ever removed,
// so the circles accumulated.
//
// One helper, used by all three call sites, so a third layer cannot
// reintroduce the same gap quietly.
function wbClearSketchHandles() {
  for (const layer of ["#wb-zoom-group", "#wb-overlay-zoom-group"]) {
    d3.select(layer).selectAll(".wb-sketch-handle-group").remove();
  }
}

//: **A right-click on a link's own grip is a right-click on the link**
//: (MINDMAP_PLAN 13c's leftover). The bend grip and the two end grips live in
//: the overlay layer, not inside the link's `.sketch-group`, so a right-click
//: on one reached neither the link's menu (the board's, or on a map the
//: cross-link ring, both wired on the group by `wbWireContextMenu`) nor the
//: canvas's, and did nothing: on the one spot of the line drawn to be grabbed.
//: The press is handed to the link's own hit stroke at the same point, which
//: is exactly the right-click that already works a little way along the line.
function wbForwardGripContextMenu(event, sketchId) {
  const hit = document.querySelector(`.sketch-group[data-id="${sketchId}"] .sketch-hitbox`)
    || document.querySelector(`.sketch-group[data-id="${sketchId}"]`);
  if (!hit) return;
  event.preventDefault();
  event.stopPropagation();
  hit.dispatchEvent(new MouseEvent("contextmenu", {
    bubbles: true,
    cancelable: true,
    clientX: event.clientX,
    clientY: event.clientY,
    screenX: event.screenX,
    screenY: event.screenY,
    button: 2,
    buttons: 2,
  }));
}

function wbRenderLinkEndpointHandles(sketch, parsed) {
  const look = wbMapCrossLinkLook(parsed);
  const endpoints = (look && wbPathEnds(look.line)) || wbResolveLinkEndpoints(parsed);
  if (!endpoints) return;
  // The overlay layer (see its own comment in index.html), an endpoint
  // sits *on a card's own border* by definition, which the base SVG layer
  // paints underneath the card's HTML element. A handle there would be
  // both invisible and unclickable exactly where it's needed most.
  // Clear before drawing: this appends rather than data-joining, so without
  // it every call leaves its predecessor behind on the board.
  wbClearSketchHandles();
  const group = d3.select("#wb-overlay-zoom-group").append("g").attr("class", "wb-sketch-handle-group");
  const shape = look ? null : wbLinkShape(parsed);
  const drawnEnds = shape?.route === "elbow" ? wbElbowEnds(endpoints.source, endpoints.target, shape.points) : endpoints;

  // Every connector's bends are waypoint grips (`wbRenderWaypointHandles`).
  // A map's cross-link keeps its one bend handle: drag to curve it,
  // double-click to straighten it, at the control point so the thing you
  // grab is the thing that moves.
  if (!look) wbRenderWaypointHandles(group, sketch, parsed, endpoints);
  else {
    const mid = { x: (endpoints.source.x + endpoints.target.x) / 2, y: (endpoints.source.y + endpoints.target.y) / 2 };
    const bendLive = { x: parsed.bend?.x || 0, y: parsed.bend?.y || 0 };
    const paths = () => [".sketch-path", ".sketch-hitbox"].map((c) => document.querySelector(`.sketch-group[data-id="${sketch.id}"] ${c}`));
    const repaint = () => {
      const d = wbLinkPathD(parsed.type, endpoints.source, endpoints.target, wbLinkCaps(parsed), parsed.width, bendLive);
      for (const el of paths()) el?.setAttribute("d", d);
      wbLayoutLinkLabel(document.querySelector(`.sketch-group[data-id="${sketch.id}"]`));
      //: A map's ribbon is a filled outline; mid-bend the path is an open
      //: curve, which a fill would close into a wedge. Stroke it in the same
      //: colour until the render after the gesture redraws it properly.
      const drawn = paths()[0];
      if (look?.ribbon && drawn && drawn.getAttribute("fill") !== "none") {
        drawn.setAttribute("stroke", drawn.getAttribute("fill"));
        drawn.setAttribute("fill", "none");
      }
    };
    const handle = group.append("circle")
      .attr("class", "wb-link-bend-handle")
      .attr("cx", mid.x + bendLive.x).attr("cy", mid.y + bendLive.y)
      .attr("r", 6);
    handle.append("title").text("Drag to bend this link · double-click to straighten");
    handle.on("contextmenu", (event) => wbForwardGripContextMenu(event, sketch.id));
    handle.call(
      d3.drag()
        .on("start", (event) => event.sourceEvent.stopPropagation())
        .on("drag", function (event) {
          bendLive.x += event.dx;
          bendLive.y += event.dy;
          d3.select(this).attr("cx", mid.x + bendLive.x).attr("cy", mid.y + bendLive.y);
          repaint();
        })
        .on("end", async () => {
          const before = WB_KIND_INFO.sketch.payload(sketch);
          await wbSaveSketchProps(sketch, { bend: (bendLive.x || bendLive.y) ? { x: bendLive.x, y: bendLive.y } : undefined });
          wbPushUndo({ action: "move", kind: "sketch", id: sketch.id, before });
          wbScheduleRender();
        })
    ).on("dblclick", async (event) => {
      event.stopPropagation();
      const before = WB_KIND_INFO.sketch.payload(sketch);
      await wbSaveSketchProps(sketch, { bend: undefined });
      wbPushUndo({ action: "move", kind: "sketch", id: sketch.id, before });
      wbScheduleRender();
    });
  }

  //: Dragging a link's end onto something: any card, text box, sticky or
  //: shape, tested in its rotated frame. This was cards on their unrotated
  //: box, so an end dropped on a rotated sticky became a free point that
  //: floated just off it (reported, with a screenshot).
  const hoveredItemAt = (px, py) => wbLinkCandidateAt(px, py);

  for (const end of ["source", "target"]) {
    const other = end === "source" ? "target" : "source";
    const live = { x: drawnEnds[end].x, y: drawnEnds[end].y };
    group.append("circle")
      .attr("class", "wb-link-endpoint-handle")
      .attr("data-end", end)
      .attr("cx", live.x).attr("cy", live.y)
      .attr("r", 7)
      .style("cursor", "crosshair")
      .on("contextmenu", (event) => wbForwardGripContextMenu(event, sketch.id))
      .call(
        d3.drag()
          .on("start", (event) => event.sourceEvent.stopPropagation())
          .on("drag", function (event) {
            // No `/ transform.k` here: unlike the HTML-element card/object
            // drags elsewhere in this file, this circle's drag container
            // (its parent `<g>`, d3-drag's default) sits *inside* the zoomed
            // `#wb-overlay-zoom-group`. d3.pointer() resolves SVG coordinates
            // through the element's `getScreenCTM()`, which already folds in
            // every ancestor transform: so `event.dx`/`dy` arrive pre-divided
            // by the zoom scale. Dividing again here shrank every frame's
            // movement by a second factor of the zoom level: reported
            // directly ("when I drag the whiteboard links, it goes off my
            // cursor"), and confirmed live: at 2x zoom the handle trailed
            // the cursor by exactly half the dragged distance, growing every
            // frame, matching a `1/k` double-division exactly.
            live.x += event.dx;
            live.y += event.dy;
            d3.select(this).attr("cx", live.x).attr("cy", live.y);
            const previewPts = end === "source" ? [live, endpoints[other]] : [endpoints[other], live];
            const previewD = wbLinkPathD(parsed.type, previewPts[0], previewPts[1], wbLinkCaps(parsed), parsed.width, parsed.bend, wbLinkShape(parsed));
            document.querySelector(`.sketch-group[data-id="${sketch.id}"] .sketch-path`)?.setAttribute("d", previewD);
            document.querySelector(`.sketch-group[data-id="${sketch.id}"] .sketch-hitbox`)?.setAttribute("d", previewD);
            wbLayoutLinkLabel(document.querySelector(`.sketch-group[data-id="${sketch.id}"]`));

            const hit = hoveredItemAt(live.x, live.y);
            if (hit) wbShowAnchorHints(hit[0], hit[1], wbNearestAnchor(hit[0], hit[1], live.x, live.y));
            else wbClearAnchorHints();
            wbFmtState.linkEdge?.cue(hit ? null : [live.x, live.y], sketch.id);
          })
          .on("end", async () => {
            wbClearAnchorHints();
            wbFmtState.linkEdge?.cue(null);
            const before = WB_KIND_INFO.sketch.payload(sketch);
            const hit = hoveredItemAt(live.x, live.y);
            const partial = {};
            if (hit) {
              const [kind, item] = hit;
              partial[end + "Id"] = item.id;
              partial[end + "Kind"] = kind === "node" ? undefined : kind;
              partial[end + "Anchor"] = wbNearestAnchor(kind, item, live.x, live.y) || undefined;
              partial[end + "Point"] = undefined;
              partial[end + "Edge"] = undefined;
            } else {
              const edge = wbFmtState.linkEdge?.hitAt(live.x, live.y, sketch.id);
              partial[end + "Id"] = undefined;
              partial[end + "Kind"] = undefined;
              partial[end + "Anchor"] = undefined;
              partial[end + "Point"] = edge ? { x: edge.x, y: edge.y } : { x: live.x, y: live.y };
              partial[end + "Edge"] = edge ? { id: edge.id, t: edge.t } : undefined;
            }
            await wbSaveSketchProps(sketch, partial);
            wbPushUndo({ action: "move", kind: "sketch", id: sketch.id, before });
            wbScheduleRender();
          })
      );
  }
}

//: **A connector's bends, as grips** (the features audit W4, then the same
//: for straight and curved lines, wb-phase2 step 1). Each waypoint the person
//: placed is a filled grip: drag it to move the bend, double-click it to take
//: it out. Between them, in the middle of every run of the drawn line, a
//: small hollow grip adds one: drag it and the line goes through where it is
//: let go. The waypoints are saved in board units on the link (`points`);
//: an elbow's route between them is worked out again on every render, a
//: straight line runs through them in turn, and a curved one is one smooth
//: curve through all of them. A link from before this with the old single
//: `bend` shows that as one waypoint, and the first edit writes `points`.
function wbRenderWaypointHandles(group, sketch, parsed, endpoints) {
  if (["er", "iso", "loop"].includes(wbLinkShape(parsed)?.route)) return;
  const elbow = parsed.route === "elbow";
  const points = wbLinkWaypoints(parsed, endpoints).map((p) => ({ x: p.x, y: p.y }));
  const groupEl = () => document.querySelector(`.sketch-group[data-id="${sketch.id}"]`);
  const live = () => ({ ...parsed, points, bend: undefined });
  const ends = () => wbResolveLinkEndpoints(live()) || endpoints;
  const repaint = () => {
    const p = live(), e = ends();
    const d = wbLinkPathD(p.type, e.source, e.target, wbLinkCaps(p), p.width, null, wbLinkShape(p));
    for (const c of [".sketch-path", ".sketch-hitbox"]) groupEl()?.querySelector(c)?.setAttribute("d", d);
    wbLayoutLinkLabel(groupEl());
  };
  const save = async (said) => {
    const before = WB_KIND_INFO.sketch.payload(sketch);
    const kept = points.map((p) => ({ x: Math.round(p.x), y: Math.round(p.y) }));
    await wbSaveSketchProps(sketch, { points: kept.length ? kept : undefined, bend: undefined });
    wbPushUndo({ action: "move", kind: "sketch", id: sketch.id, before });
    if (said) wbAnnounce(said);
    wbScheduleRender();
  };
  for (const p of points) {
    const grip = group.append("circle")
      .attr("class", "wb-link-waypoint-handle")
      .attr("cx", p.x).attr("cy", p.y).attr("r", 6);
    grip.append("title").text("Drag to move this bend · double-click to take it out");
    grip.on("contextmenu", (event) => wbForwardGripContextMenu(event, sketch.id));
    //: Saved only when it moved: a save re-renders the grips, and one on the
    //: first click of a double-click took the grip the second click needed
    //: (measured: a double-click on a bend left it where it was).
    let moved = false;
    grip.call(d3.drag()
      .on("start", (event) => event.sourceEvent.stopPropagation())
      .on("drag", function (event) {
        moved = true;
        p.x += event.dx;
        p.y += event.dy;
        d3.select(this).attr("cx", p.x).attr("cy", p.y);
        repaint();
      })
      .on("end", () => {
        if (moved) save();
        moved = false;
      })).on("dblclick", (event) => {
      event.stopPropagation();
      points.splice(points.indexOf(p), 1);
      save("Bend taken out.");
    });
  }
  //: A label is pressed by its words (INBOX 1404), so a ring that would sit
  //: on them waits: the press would otherwise land on the ring.
  let labelBox = null;
  try { labelBox = groupEl()?.querySelector(":scope > .wb-link-label:not(.wb-link-label2)")?.getBBox() || null; } catch { labelBox = null; }
  const underLabel = (a) => Boolean(labelBox && labelBox.width && a.x > labelBox.x - 6 && a.x < labelBox.x + labelBox.width + 6 && a.y > labelBox.y - 6 && a.y < labelBox.y + labelBox.height + 6);
  for (const add of wbWaypointAddSpots(live(), ends(), groupEl()?.querySelector(".sketch-hitbox")?.getAttribute("d")).filter((a) => !underLabel(a))) {
    const grip = group.append("circle")
      .attr("class", "wb-link-waypoint-add")
      .attr("cx", add.x).attr("cy", add.y).attr("r", 4);
    grip.append("title").text("Drag to add a bend here");
    grip.on("contextmenu", (event) => wbForwardGripContextMenu(event, sketch.id));
    //: Added on the first move, not on the press: a click (or the two of a
    //: double-click) on the ring is not a drag, and inserting on press left
    //: one or two bends exactly where the ring was (measured: a double-click
    //: there saved the same point twice).
    const p = { x: add.x, y: add.y };
    let added = false;
    grip.call(
      d3.drag()
        .on("start", (event) => event.sourceEvent.stopPropagation())
        .on("drag", function (event) {
          if (!added) {
            added = true;
            const index = elbow ? wbWaypointInsert(points, add.line, p).findIndex((q) => q === p || (q.x === p.x && q.y === p.y)) : add.index;
            points.splice(index, 0, p);
            d3.select(this).attr("class", "wb-link-waypoint-handle").attr("r", 6);
          }
          p.x += event.dx;
          p.y += event.dy;
          d3.select(this).attr("cx", p.x).attr("cy", p.y);
          repaint();
        })
        .on("end", () => {
          if (added) save("Bend added. Drag it to move it, double-click to take it out.");
        })
    ).on("dblclick", (event) => {
      //: The ring sits on the line, so a double-click there is the line's
      //: own gesture (a bend where you double-click), not swallowed.
      event.stopPropagation();
      if (added) return;
      added = true;
      const index = elbow ? wbWaypointInsert(points, add.line, p).findIndex((q) => q.x === p.x && q.y === p.y) : add.index;
      points.splice(index, 0, p);
      save("Bend added. Drag it to move it, double-click to take it out.");
    });
  }
}

//: A link's waypoints as the grips and a double-click read them: its
//: `points`, or the one point an old link's single `bend` curve passes
//: through (a quadratic's middle is halfway from the chord to its control).
function wbLinkWaypoints(parsed, endpoints) {
  if (Array.isArray(parsed?.points) && parsed.points.length) return parsed.points;
  if (parsed?.route === "elbow" || !endpoints || !parsed?.bend || !(parsed.bend.x || parsed.bend.y)) return [];
  return [{
    x: (endpoints.source.x + endpoints.target.x) / 2 + parsed.bend.x / 2,
    y: (endpoints.source.y + endpoints.target.y) / 2 + parsed.bend.y / 2,
  }];
}

//: The line a link is drawn along, as points: an elbow's route, or the
//: stops a straight or curved link runs through. What a new waypoint's place
//: among the others is measured on.
function wbLinkDrawnLine(parsed, ends) {
  const shape = wbLinkShape(parsed);
  if (shape?.route === "elbow") {
    const e = wbElbowEnds(ends.source, ends.target, shape.points);
    return wbElbowRoute(e.source, e.target, ends.source.box, ends.target.box, shape.points);
  }
  return [ends.source, ...(shape?.points || []), ends.target].map((p) => ({ x: p.x, y: p.y }));
}

//: Where the add-a-bend grips sit: the middle of every run long enough to
//: aim at, on the line as drawn (a curve's own middle, not its chord's).
//: `index` is where a bend added there goes among the waypoints; an elbow's
//: runs are not one per waypoint, so it carries its route instead.
function wbWaypointAddSpots(parsed, ends, drawnD) {
  const shape = wbLinkShape(parsed);
  const spots = [];
  if (["er", "iso", "loop"].includes(shape?.route)) return spots;
  if (shape?.route === "elbow") {
    const line = wbLinkDrawnLine(parsed, ends);
    for (let i = 0; i < line.length - 1; i++) {
      const a = line[i], b = line[i + 1];
      if (Math.hypot(b.x - a.x, b.y - a.y) < 36) continue;
      spots.push({ x: (a.x + b.x) / 2, y: (a.y + b.y) / 2, line });
    }
    return spots;
  }
  if (!shape) {
    const mid = (drawnD && wbLinkMidpoint(drawnD, 0.5)) || { x: (ends.source.x + ends.target.x) / 2, y: (ends.source.y + ends.target.y) / 2 };
    return [{ x: mid.x, y: mid.y, index: 0 }];
  }
  const stops = [ends.source, ...shape.points, ends.target];
  const segs = shape.route === "curved" ? wbCurveThroughSegs(stops, ends.source.dir, ends.target.dir) : null;
  for (let i = 0; i < stops.length - 1; i++) {
    const a = stops[i], b = stops[i + 1];
    if (Math.hypot(b.x - a.x, b.y - a.y) < 36) continue;
    const mid = segs ? wbCubicAt(segs[i], 0.5) : { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
    spots.push({ x: mid.x, y: mid.y, index: i });
  }
  return spots;
}

//: Where a label sits along its line: 0 at the start, 1 at the end, the
//: middle when it was never moved.
function wbLinkLabelT(parsed) {
  const t = Number(parsed?.label_t);
  return Number.isFinite(t) && t >= 0 && t <= 1 ? t : 0.5;
}

//: The share of the drawn line nearest a point, sampled along the line's own
//: length so a curve is measured where it is.
function wbLinkNearestT(d, p) {
  const shaft = String(d || "").split(/\s(?=M)/)[0];
  if (!shaft || !wbLinkMeasurePath) return 0.5;
  wbLinkMeasurePath.setAttribute("d", shaft);
  let length = 0;
  try {
    length = wbLinkMeasurePath.getTotalLength();
  } catch {
    return 0.5;
  }
  if (!length) return 0.5;
  let best = Infinity, bestT = 0.5;
  const steps = 80;
  for (let i = 0; i <= steps; i++) {
    const q = wbLinkMeasurePath.getPointAtLength((length * i) / steps);
    const dist = Math.hypot(q.x - p.x, q.y - p.y);
    if (dist < best) {
      best = dist;
      bestT = i / steps;
    }
  }
  return Math.max(0.05, Math.min(0.95, bestT));
}

// The handles themselves: a fresh SVG group per selection, since (unlike a
// card/object's own always-present handles) a sketch has no fixed element to
// attach 8 children to; it's rebuilt on every selection change and after
// every `wbScheduleRender()` re-applies the current selection.
//: **A sweep that caught several things gets one box round all of them.**
//: Reported with two screenshots: "the highlight select only highlights the
//: shapes, it doesnt show the box and enchor points as it should like when I
//: individually select them". A single selection has had a box and eight
//: anchors for a long time; a multi-selection had only each item's own
//: highlight, so a face drawn from four shapes read as four selected things
//: with no handle between them.
//:
//: The anchors work, rather than being drawn for the look of it: they scale
//: every selected item about the opposite corner, which is the one gesture a
//: group box is *for*. The maths is `wbSketchResizeTransform`, the same
//: function a single shape's handles already use, so a group resize and a
//: shape resize cannot drift apart (shift-to-square included).
//:
//: No rotate handle. Rotating a group means rotating each item about the
//: group's centre, which for a card means a rotation *and* a move, and for a
//: sketch means baking a rotation into a path that is already rotated. It is
//: a real feature, not a line of code, and an unbuilt one is better absent
//: than drawn and inert.
function wbMultiSelectionEntries() {
  const entries = [];
  for (const key of wbMultiSelection) {
    const sep = key.indexOf(":");
    const kind = key.slice(0, sep);
    const id = Number(key.slice(sep + 1));
    if (kind === "node") {
      const node = (wbState.nodes || []).find((n) => n.id === id);
      if (node) entries.push({ kind, item: node });
    } else if (kind === "object") {
      const object = (wbState.objects || []).find((o) => o.id === id);
      if (object) entries.push({ kind, item: object });
    } else if (kind === "sketch") {
      const sketch = (wbState.sketches || []).find((k) => k.id === id);
      const parsed = sketch ? wbSketchParsedData(sketch) : null;
      //: A link has no `d` of its own (it is recomputed from its endpoints
      //: every render), so it cannot be scaled and is not part of the box.
      if (sketch && parsed) entries.push({ kind, item: sketch, parsed });
    }
  }
  return entries;
}

//: Every kind measured in board units, which is the one frame the three of
//: them share: a card's size lives on the element (its height is the text's
//: until someone drags it), an object carries its own, and a sketch's is its
//: path's extent.
function wbEntryBox(entry) {
  if (entry.kind === "sketch") {
    const bbox = wbPathBBox(entry.parsed.d);
    return bbox ? { minX: bbox.minX, minY: bbox.minY, maxX: bbox.maxX, maxY: bbox.maxY } : null;
  }
  const { item } = entry;
  const el = document.querySelector(WB_SELECTOR_BY_KIND[entry.kind](item.id));
  const w = item.width || el?.offsetWidth || WB_CARD_DEFAULT_SIZE.w;
  const h = item.height || el?.offsetHeight || WB_CARD_DEFAULT_SIZE.h;
  return { minX: item.x, minY: item.y, maxX: item.x + w, maxY: item.y + h };
}

//: **The box an item actually occupies, rotation included.**
//:
//: `wbEntryBox` above returns the item's *layout* box: the `x`, `y`, `width`
//: and `height` stored on the row, which is what a resize has to write back
//: and so is the only thing the group-scale maths may use. A rotated card
//: does not occupy that box. Measured with one card at 0 degrees and one at
//: 45: the group outline drawn from layout boxes missed the rotated card by
//: 61px above, 61px below and 21px to the right, so a selection you could
//: see was drawn inside a card you had selected.
//:
//: The corners of the layout box turned about its own centre, which is what
//: `translate() rotate()` does to the element (`transform-origin` resolves
//: to 50% 50% in the untouched box), and then the axis-aligned box around
//: those four points.
//:
//: Deliberately a second function rather than a change to `wbEntryBox`: the
//: two boxes answer different questions, and the group resize needs the
//: layout one. Giving it this one instead would write a rotated card's
//: bounding box back as its `width` and `height`, which grows the card every
//: time the group is scaled.
function wbEntryOutlineBox(entry) {
  const box = wbEntryBox(entry);
  if (!box) return null;
  const rotation = entry.kind === "sketch" ? 0 : entry.item.rotation || 0;
  if (!rotation) return box;
  const centre = wbBoxCenter(box);
  const corners = [
    { x: box.minX, y: box.minY },
    { x: box.maxX, y: box.minY },
    { x: box.minX, y: box.maxY },
    { x: box.maxX, y: box.maxY },
  ].map((corner) => wbRotatePoint(corner, centre, rotation));
  return {
    minX: Math.min(...corners.map((c) => c.x)),
    minY: Math.min(...corners.map((c) => c.y)),
    maxX: Math.max(...corners.map((c) => c.x)),
    maxY: Math.max(...corners.map((c) => c.y)),
  };
}

//: What every frame of a group drag is computed from, taken once at the
//: start: reading it back off the items each frame compounds the rounding
//: into a shape that drifts while the pointer is still.
function wbMultiSnapshot(boxes) {
  return boxes.map((row) => ({
    entry: row.entry,
    box: row.box,
    d: row.entry.kind === "sketch" ? row.entry.parsed.d : null,
    rotation: row.entry.kind === "sketch" ? 0 : (row.entry.item.rotation || 0),
    //: The whole row as it was, for the undo step and for Escape.
    before: WB_KIND_INFO[row.entry.kind].payload(row.entry.item),
  }));
}

//: Escape during a group's resize or turn: every member back as the grip
//: found it, on screen only (nothing was saved yet).
function wbRestoreMultiSnapshot(rows) {
  for (const row of rows || []) {
    const item = row.entry.item;
    if (row.entry.kind === "sketch") {
      delete item._liveD;
      delete item._dragLiveD;
      const selector = `.sketch-group[data-id="${item.id}"]`;
      document.querySelector(`${selector} .sketch-path`)?.setAttribute("d", row.d);
      document.querySelector(`${selector} .sketch-hitbox`)?.setAttribute("d", row.d);
      wbLayoutShapeLabel(document.querySelector(selector));
      continue;
    }
    wbRestoreBox(row.entry.kind, item, row.before);
  }
}

//: **What follows a group's resize or turn live** (the wb ledger, 10-25):
//: every connector touching a member, once (a link between two members is one
//: path), and each shape member's own outline, which is drawn in the board
//: layer apart from the group's box and stayed at the old size until release.
function wbMultiLiveLinks(rows) {
  const index = wbLinkSketchIndex();
  return [...new Set(rows.flatMap((r) => wbLinkedSketchesFor(r.entry.item.id, r.entry.kind, index)))];
}

function wbMultiMemberOutline(id) {
  return document.querySelector(`#wb-zoom-group .wb-sketch-handle-group[data-sketch-id="${id}"]`);
}

function wbFollowMultiOutline(id, liveD) {
  const box = wbMultiMemberOutline(id)?.querySelector(".wb-sketch-selection-box");
  const bb = liveD ? wbPathBBox(liveD) : null;
  if (!box || !bb) return;
  box.setAttribute("x", bb.minX - 2);
  box.setAttribute("y", bb.minY - 2);
  box.setAttribute("width", (bb.maxX - bb.minX) + 4);
  box.setAttribute("height", (bb.maxY - bb.minY) + 4);
}

//: Saving a whole group, one write at a time. Each write is the item's whole
//: row and the board's stale-client recovery reloads everything, which a
//: burst of simultaneous writes would race.
async function wbSaveMultiSnapshot(rows) {
  //: One undo step for the whole group (it had none: Ctrl+Z after resizing
  //: or turning a selection put nothing back).
  wbPushDragUndo(rows.map((row) => ({
    action: "move", kind: row.entry.kind, id: row.entry.item.id, before: row.before,
  })));
  for (const row of rows) {
    if (row.entry.kind !== "sketch") continue;
    const live = row.entry.item._liveD;
    delete row.entry.item._liveD;
    delete row.entry.item._dragLiveD;
    if (live) wbSketchSetD(row.entry.item, live);
  }
  await wbSaveMany(rows.map((row) => ({ kind: row.entry.kind, item: row.entry.item })));
  wbScheduleRender();
}

function wbRenderMultiSelectionHandles() {
  //: Not round several topics on a map (INBOX 617): the layout owns where a
  //: topic sits, so the box's eight sizes and its turn could only fight it.
  //: Each topic keeps its own outline (`.wb-in-group`).
  if (wbMapMultiTopics()) return;
  const entries = wbMultiSelectionEntries();
  if (entries.length < 2) return;
  const boxes = entries.map((entry) => ({ entry, box: wbEntryBox(entry) })).filter((row) => row.box);
  if (boxes.length < 2) return;
  //: The outline is drawn around what the items occupy (rotation included);
  //: `row.box` stays the layout box, because that is what the resize below
  //: writes back. See `wbEntryOutlineBox` for why the two cannot be one.
  const outlines = boxes.map((row) => wbEntryOutlineBox(row.entry) || row.box);
  const bbox = {
    minX: Math.min(...outlines.map((box) => box.minX)),
    minY: Math.min(...outlines.map((box) => box.minY)),
    maxX: Math.max(...outlines.map((box) => box.maxX)),
    maxY: Math.max(...outlines.map((box) => box.maxY)),
  };
  //: **Each member is outlined, and only the group carries grips** (INBOX
  //: 278's second half). A shape had nothing drawn round it at all in a
  //: marquee selection, which was reported ("when I drag select shapes, the
  //: individual anchor/rotate boxes dont appear... its fine for the notes but
  //: the shapes and lines arent selected visually and individually"), and the
  //: answer then was to give every member its own full set of handles. That
  //: is what the second screenshot in 278 shows: a three-item group drew
  //: **eight** rotate knobs and sixteen resize handles, one set per member
  //: plus the group's, so the stem the eye lands on rises from a member's own
  //: centre or sits below the group's top border, and no one of them reads as
  //: the group's. Both reports are answered by drawing the member's outline
  //: and nothing else: what is selected is still visible one by one, and
  //: there is exactly one thing to grab.
  for (const row of boxes) {
    if (row.entry.kind === "sketch") wbDrawSketchHandles(row.entry.item, { outlineOnly: true });
  }
  //: **The overlay layer, not the base one** (INBOX 262: "not being able to
  //: drag the edges of a group selection"). The base SVG paints *under*
  //: `#wb-html-layer`, which is where a card and its own eight handles live,
  //: so a group handle that landed on a member's corner was both invisible
  //: and unclickable: measured with `elementFromPoint` at each handle's own
  //: centre, 6 of the 8 returned a card's `.wb-resize-handle` instead. The
  //: link endpoint handles moved up here for exactly this reason and their
  //: comment records it; a group box is the same case, since its corners are
  //: the union of the members' corners and so sit on a member by definition.
  //:
  //: The members keep their own handles, visible and usable away from the
  //: group's eight: that was asked for directly ("when I drag select shapes,
  //: the individual anchor/rotate boxes dont appear"), so the fix is which
  //: layer wins the press, not which handles are drawn.
  const group = d3.select("#wb-overlay-zoom-group")
    .append("g")
    .attr("class", "wb-sketch-handle-group wb-multi-handle-group");
  const boxRect = group.append("rect").attr("class", "wb-sketch-selection-box");

  //: **The chrome is laid out from a box rather than drawn at fixed points.**
  //: Reported: "the group selection outline doesnt resize with the objects
  //: selected in side them when resizing or rotating the group selection".
  //: Every part of it was positioned once, from the bbox as it stood when the
  //: selection was made, so a drag moved the items and left the outline and
  //: its eight anchors behind: you were pulling a handle that was no longer on
  //: the corner it belonged to, with the box crossing the middle of what it
  //: was supposed to contain. One function that can be called again with a
  //: new box, from every frame of the drag, is the fix; a redraw is not,
  //: because it would replace the element the gesture is bound to.
  const handleAt = new Map();
  let stem = null, spinDot = null;
  function layoutGroupChrome(box) {
    boxRect
      .attr("x", box.minX - 2).attr("y", box.minY - 2)
      .attr("width", (box.maxX - box.minX) + 4)
      .attr("height", (box.maxY - box.minY) + 4);
    for (const [name, el] of handleAt) {
      const hx = name.includes("w") ? box.minX : name.includes("e") ? box.maxX : (box.minX + box.maxX) / 2;
      const hy = name.includes("n") ? box.minY : name.includes("s") ? box.maxY : (box.minY + box.maxY) / 2;
      el.attr("x", hx - 5).attr("y", hy - 5);
    }
    const cx = (box.minX + box.maxX) / 2;
    //: **The anchor, without which the grip leaves the box** (INBOX 278: "the
    //: rotate line and circle dont sit at the top center of a group
    //: selection... and instead sit off to the top left or right, or below the
    //: top border"). `.wb-sketch-rotate-handle` and `.wb-rotate-handle-stem`
    //: carry `scale(var(--wb-inv-zoom))` so a grip stays one size to the hand,
    //: and that rule keeps `transform-box` at its `view-box` default *because
    //: the code that draws them sets the origin in board units* (the rule says
    //: so in its own comment, and `wbDrawSketchHandles` does it for a single
    //: shape). This group never set one, so the scale resolved about the SVG
    //: view box's origin and multiplied the grip's own coordinates by `1 / k`:
    //: measured on a three-item group, the knob sat at board (680, 1344) at
    //: 0.5x and (170, 336) at 2x for a box whose top centre is (340, 672), so
    //: it flew down and right when you zoomed out and up and left when you
    //: zoomed in, while sitting exactly right at 1x. The foot of the stem is
    //: the point that must not move, the same anchor the single-shape handles
    //: use, and it is re-set here rather than once at creation because a
    //: resize drag calls this again with a new box.
    const anchor = `${cx}px ${box.minY}px`;
    if (stem) {
      stem.attr("x1", cx).attr("y1", box.minY).attr("x2", cx).attr("y2", box.minY - 28)
        .style("transform-origin", anchor);
    }
    if (spinDot) spinDot.attr("cx", cx).attr("cy", box.minY - 28).style("transform-origin", anchor);
  }

  //: The box the items now occupy, given the scale this frame is applying.
  //: The same arithmetic the items themselves get, so the outline cannot
  //: disagree with what it is drawn around.
  function scaledBox(t) {
    return {
      minX: t.anchorX + (bbox.minX - t.anchorX) * t.sx,
      minY: t.anchorY + (bbox.minY - t.anchorY) * t.sy,
      maxX: t.anchorX + (bbox.maxX - t.anchorX) * t.sx,
      maxY: t.anchorY + (bbox.maxY - t.anchorY) * t.sy,
    };
  }

  //: The state every frame of the drag is computed from. Taken once at the
  //: start rather than read back off the items, which would compound each
  //: frame's rounding into a shape that drifts while you hold the mouse
  //: still, the accumulation bug the single-shape handles document.
  let start = null, sizeLinks = [];
  let groupGesture = null;
  for (const handle of ["nw", "n", "ne", "e", "se", "s", "sw", "w"]) {
    const hx = handle.includes("w") ? bbox.minX : handle.includes("e") ? bbox.maxX : (bbox.minX + bbox.maxX) / 2;
    const hy = handle.includes("n") ? bbox.minY : handle.includes("s") ? bbox.maxY : (bbox.minY + bbox.maxY) / 2;
    let rawDX = 0, rawDY = 0;
    const handleEl = group.append("rect")
      .attr("class", "wb-sketch-resize-handle")
      .attr("data-handle", handle)
      .attr("x", hx - 5).attr("y", hy - 5)
      .attr("width", 10).attr("height", 10)
      .style("cursor", `${handle}-resize`)
      .call(
        d3.drag()
          .on("start", (event) => {
            event.sourceEvent.stopPropagation();
            rawDX = 0;
            rawDY = 0;
            start = wbMultiSnapshot(boxes);
            const rows = start;
            sizeLinks = wbMultiLiveLinks(rows);
            const links = sizeLinks;
            groupGesture = wbBeginGesture(() => {
              wbRestoreMultiSnapshot(rows);
              for (const row of rows) if (row.entry.kind === "sketch") wbFollowMultiOutline(row.entry.item.id, row.d);
              if (links.length) wbUpdateLinkedSketches(null, links);
              wbClearAlignmentGuides();
              layoutGroupChrome(bbox);
            });
          })
          .on("drag", (event) => {
            if (!start || groupGesture?.cancelled) return;
            const zoom = d3.zoomTransform(document.getElementById("whiteboard-container"));
            rawDX += event.dx / zoom.k;
            rawDY += event.dy / zoom.k;
            const raw = wbSketchResizeTransform(bbox, handle, rawDX, rawDY, event.sourceEvent.shiftKey, event.sourceEvent.altKey);
            //: **A corner scales a group proportionally** (the owner: "when I
            //: try to resizr the multiple selected objects with the group box,
            //: the items all go out of proportion and funky"). A single shape
            //: stretching on one axis is a shape being reshaped, which is what
            //: you asked for by grabbing its corner; a *set* of things doing it
            //: is every circle in the set turning into a different ellipse and
            //: every card into a different rectangle, which is never what the
            //: gesture meant. The driving axis wins, so the corner still
            //: follows the pointer in the direction it was pulled, and shift
            //: releases the lock for a deliberate stretch.
            const corner = handle.length === 2;
            const free = event.sourceEvent.shiftKey;
            const k = Math.abs(raw.sx - 1) >= Math.abs(raw.sy - 1) ? raw.sx : raw.sy;
            const t = corner && !free ? { ...raw, sx: k, sy: k } : raw;
            for (const row of start) {
              if (row.entry.kind === "sketch") {
                row.kind ??= wbSketchParsedData(row.entry.item)?.shapeKind || "";
                const newD = (wbFmtState.shapeTable?.resized(row.d, t, row.kind, wbTransformPathD, wbPathBBox) ?? wbTransformPathD(row.d, t));
                const selector = `.sketch-group[data-id="${row.entry.item.id}"]`;
                document.querySelector(`${selector} .sketch-path`)?.setAttribute("d", newD);
                document.querySelector(`${selector} .sketch-hitbox`)?.setAttribute("d", newD);
                wbLayoutShapeLabel(document.querySelector(selector));
                row.entry.item._liveD = newD;
                row.entry.item._dragLiveD = newD;
                wbFollowMultiOutline(row.entry.item.id, newD);
                continue;
              }
              const item = row.entry.item;
              item.x = t.anchorX + (row.box.minX - t.anchorX) * t.sx;
              item.y = t.anchorY + (row.box.minY - t.anchorY) * t.sy;
              item.width = Math.max(WB_OBJECT_MIN_SIZE, (row.box.maxX - row.box.minX) * t.sx);
              item.height = Math.max(WB_OBJECT_MIN_SIZE, (row.box.maxY - row.box.minY) * t.sy);
              //: The drag accumulator is a running position from the *last*
              //: drag, and anything that moves an item behind its back has to
              //: drop it or the next drag starts from where the item used to
              //: be.
              delete item._rawX;
              delete item._rawY;
              //: Written straight to the element rather than through a
              //: render: a render rebuilds the selection chrome, which
              //: includes the very handle this drag is bound to, and the
              //: gesture dies the moment its element is replaced. The
              //: single-shape handles avoid the same trap the same way.
              const el = document.querySelector(WB_SELECTOR_BY_KIND[row.entry.kind](item.id));
              if (el) {
                el.style.transform = wbItemTransform(item);
                el.style.width = `${item.width}px`;
                el.style.height = `${item.height}px`;
              }
            }
            if (sizeLinks.length) wbUpdateLinkedSketches(null, sizeLinks);
            const live = scaledBox(t);
            layoutGroupChrome(live);
            //: The size beside the box, as a single item's resize shows it.
            wbShowAlignmentGuides([]);
            wbShowSizeReadout({ x: live.minX, y: live.minY, w: live.maxX - live.minX, h: live.maxY - live.minY });
          })
          .on("end", async () => {
            wbClearAlignmentGuides();
            if (!start) return;
            const rows = start;
            start = null;
            const cancelled = wbEndGesture(groupGesture);
            groupGesture = null;
            if (cancelled) return;
            await wbSaveMultiSnapshot(rows);
          })
      );
    handleAt.set(handle, handleEl);
  }

  //: **And a rotate point above the box** (the owner: "the group boxes dont
  //: have a rotate point at the top"). Every item turns about the group's
  //: centre, which for a card or a text box is a move *and* a rotation of its
  //: own: the box travels round the centre and then faces the new direction.
  //: A shape has no rotation column, so its turn is baked into the path the
  //: same way its own rotate handle bakes one.
  //:
  //: The angle is absolute, read straight off the pointer's bearing from the
  //: centre, which is what makes the handle follow the cursor rather than
  //: drift by a per-frame delta. Shift snaps to 15 degrees, the same as
  //: everywhere else on this board.
  const centerX = (bbox.minX + bbox.maxX) / 2;
  const centerY = (bbox.minY + bbox.maxY) / 2;
  const handleY = bbox.minY - 28;
  stem = group.append("line")
    .attr("class", "wb-rotate-handle-stem")
    .attr("x1", centerX).attr("y1", bbox.minY).attr("x2", centerX).attr("y2", handleY);
  let spin = null, spinLinks = [];
  spinDot = group.append("circle")
    .attr("class", "wb-sketch-rotate-handle")
    .attr("cx", centerX).attr("cy", handleY).attr("r", 6)
    .style("cursor", "grab")
    .call(
      d3.drag()
        .on("start", (event) => {
          event.sourceEvent.stopPropagation();
          spin = wbMultiSnapshot(boxes);
          const rows = spin;
          //: Each link touching a turned card or box, once (a link between two
          //: selected items is one path), so its ends follow the turn live.
          //: Shapes too: a turned shape's live path is `_dragLiveD`, which the
          //: link's end reads, so a connector to a shape follows the turn.
          spinLinks = wbMultiLiveLinks(rows);
          const links = spinLinks;
          groupGesture = wbBeginGesture(() => {
            wbRestoreMultiSnapshot(rows);
            for (const row of rows) wbMultiMemberOutline(row.entry.item.id)?.removeAttribute("transform");
            if (links.length) wbUpdateLinkedSketches(null, links);
            group.attr("transform", null);
          });
        })
        .on("drag", (event) => {
          if (!spin || groupGesture?.cancelled) return;
          const angle = wbSketchAngleFromCenterDeg(
            centerX, centerY, event.sourceEvent, event.sourceEvent.shiftKey
          );
          const theta = (angle * Math.PI) / 180;
          const cos = Math.cos(theta), sin = Math.sin(theta);
          for (const row of spin) {
            if (row.entry.kind === "sketch") {
              const newD = wbTransformPathD(row.d, {
                rotate: angle, anchorX: centerX, anchorY: centerY,
              });
              const selector = `.sketch-group[data-id="${row.entry.item.id}"]`;
              document.querySelector(`${selector} .sketch-path`)?.setAttribute("d", newD);
              document.querySelector(`${selector} .sketch-hitbox`)?.setAttribute("d", newD);
              wbLayoutShapeLabel(document.querySelector(selector));
              row.entry.item._liveD = newD;
              row.entry.item._dragLiveD = newD;
              //: Its outline turns about the same centre as the group's box.
              wbMultiMemberOutline(row.entry.item.id)?.setAttribute("transform", `rotate(${angle} ${centerX} ${centerY})`);
              continue;
            }
            const item = row.entry.item;
            const w = row.box.maxX - row.box.minX, h = row.box.maxY - row.box.minY;
            //: The box turns about its own centre (`wbItemTransform` translates
            //: and then rotates, so the origin is the element's middle), which
            //: is why the point carried round the group's centre is the item's
            //: centre and not its corner.
            const relX = row.box.minX + w / 2 - centerX;
            const relY = row.box.minY + h / 2 - centerY;
            item.x = centerX + relX * cos - relY * sin - w / 2;
            item.y = centerY + relX * sin + relY * cos - h / 2;
            item.rotation = (row.rotation + angle) % 360;
            delete item._rawX;
            delete item._rawY;
            const el = document.querySelector(WB_SELECTOR_BY_KIND[row.entry.kind](item.id));
            if (el) el.style.transform = wbItemTransform(item);
          }
          if (spinLinks.length) wbUpdateLinkedSketches(null, spinLinks);
          //: The outline turns with what it contains rather than being
          //: recomputed as a new upright box: a box that stayed level while
          //: its contents turned is the "doesnt rotate with them" half of the
          //: same report, and an upright box round a turned set is also the
          //: wrong shape, since the set no longer fills it.
          group.attr("transform", `rotate(${angle} ${centerX} ${centerY})`);
        })
        .on("end", async () => {
          if (!spin) return;
          const rows = spin;
          spin = null;
          //: Dropped, not kept: the render that follows the save rebuilds this
          //: whole group from the items' new positions, and a transform left
          //: on it would be applied a second time on top of them.
          group.attr("transform", null);
          const cancelled = wbEndGesture(groupGesture);
          groupGesture = null;
          if (cancelled) return;
          await wbSaveMultiSnapshot(rows);
        })
    );
  layoutGroupChrome(bbox);
}

//: **A shape's lines and clone arrows follow it while it is stretched or
//: turned**, not only when it is moved (INBOX 740, 746). A move already keeps
//: its live path in `_dragLiveD`, which `wbItemBBox` and the outline a link
//: meets both read; a resize and a turn now put theirs there too for the
//: length of the gesture, and `null` takes it away at the end, before the
//: save writes the path for good.
function wbFollowLiveShape(sketch, liveD) {
  if (liveD == null) {
    delete sketch._dragLiveD;
    delete sketch._followLinks;
    return;
  }
  sketch._dragLiveD = liveD;
  if (!sketch._followLinks) sketch._followLinks = wbLinkedSketchesFor(sketch.id, "sketch");
  if (sketch._followLinks.length) wbUpdateLinkedSketches(sketch.id, sketch._followLinks);
  wbQueueSelectionBar();
}

function wbRenderSketchHandles() {
  wbClearSketchHandles();
  if (!wbSelectedItem || wbSelectedItem.kind !== "sketch") return;
  const sketch = wbState.sketches.find((s) => s.id === wbSelectedItem.id);
  if (!sketch) return;
  wbDrawSketchHandles(sketch);
}

//: **One shape's own box and anchors**, split out from the single-selection
//: renderer above so a sweep can draw them for every shape it caught. The
//: owner, with a screenshot of a selected face beside a pair of selected
//: notes: "when I drag select shapes, the individual anchor/rotate boxes dont
//: appear ... see how its fine for the notes but the shapes and lines arent
//: selected visually and individually??" A card and a text box carry their
//: eight handles as children of the element, so `.wb-selected` alone reveals
//: them; a shape is a path in the SVG layer with nowhere to keep handles, and
//: this is the only thing that draws them. It ran for the single selection
//: only, which is exactly the difference the screenshot shows.
//: `outlineOnly` draws the selection box and stops: a member of a group
//: selection is shown as selected without being given grips of its own, which
//: belong to the group (INBOX 278). A link's endpoint handles are grips too,
//: so that branch takes the same exit.
function wbDrawSketchHandles(sketch, { outlineOnly = false } = {}) {
  // A link sketch has no `.d` of its own: `wbSketchParsedData` returns
  // null for it, and the 8-point bbox resize handles below make no sense
  // for a path recomputed fresh from its endpoints every render anyway.
  // It gets its own two endpoint handles instead (below).
  let rawParsed;
  try { rawParsed = JSON.parse(sketch.data); } catch { rawParsed = null; }
  if (rawParsed && (rawParsed.type || "").startsWith("link-")) {
    if (!outlineOnly) wbRenderLinkEndpointHandles(sketch, rawParsed);
    return;
  }
  const parsed = wbSketchParsedData(sketch);
  if (!parsed) return;
  const bbox = wbPathBBox(parsed.d);
  if (!bbox) return;

  //: A lone selection's grips go in the overlay, above the HTML objects that
  //: can lie over the shape (3 of 8 grips were under a text box: measured
  //: with `elementFromPoint`); a multi member's bare outline stays under.
  const group = d3.select(outlineOnly ? "#wb-zoom-group" : "#wb-overlay-zoom-group")
    .append("g")
    .attr("class", "wb-sketch-handle-group")
    .attr("data-sketch-id", sketch.id);

  //: **One selection box for every kind** (WHITEBOARD_PLAN.md decision 6). A
  //: card and a text box wear a 1px `--accent` outline; a sketch wore a dashed
  //: 35%-opacity stroke *along its own path* instead, so the same click read
  //: as two different kinds of thing and a thin diagonal line had no box at
  //: all. This is that outline, drawn round the shape's own bbox.
  group.append("rect")
    .attr("class", "wb-sketch-selection-box")
    .attr("x", bbox.minX - 2).attr("y", bbox.minY - 2)
    .attr("width", (bbox.maxX - bbox.minX) + 4)
    .attr("height", (bbox.maxY - bbox.minY) + 4);

  if (outlineOnly) return;

  //: **The box and the grips follow a resize while it happens**, with the
  //: size beside them, as a card's do (the 22-10 bug doc: "Shape anchor
  //: points and selection borders don't resize with the user's" drag). They
  //: were drawn once from the old bbox and only moved on the release render.
  const placeGrips = (bb) => {
    const node = group.node();
    const box = node.querySelector(".wb-sketch-selection-box");
    box.setAttribute("x", bb.minX - 2);
    box.setAttribute("y", bb.minY - 2);
    box.setAttribute("width", (bb.maxX - bb.minX) + 4);
    box.setAttribute("height", (bb.maxY - bb.minY) + 4);
    for (const grip of node.querySelectorAll(".wb-sketch-resize-handle")) {
      const h = grip.dataset.handle;
      grip.setAttribute("x", (h.includes("w") ? bb.minX : h.includes("e") ? bb.maxX : (bb.minX + bb.maxX) / 2) - 5);
      grip.setAttribute("y", (h.includes("n") ? bb.minY : h.includes("s") ? bb.maxY : (bb.minY + bb.maxY) / 2) - 5);
    }
    const midX = (bb.minX + bb.maxX) / 2;
    const origin = `${midX}px ${bb.minY}px`;
    const stem = node.querySelector(".wb-rotate-handle-stem");
    if (stem) {
      stem.setAttribute("x1", midX);
      stem.setAttribute("x2", midX);
      stem.setAttribute("y1", bb.minY);
      stem.setAttribute("y2", bb.minY - 28);
      stem.style.transformOrigin = origin;
    }
    const turn = node.querySelector(".wb-sketch-rotate-handle");
    if (turn) {
      turn.setAttribute("cx", midX);
      turn.setAttribute("cy", bb.minY - 28);
      turn.style.transformOrigin = origin;
    }
  };

  for (const handle of ["nw", "n", "ne", "e", "se", "s", "sw", "w"]) {
    const hx = handle.includes("w") ? bbox.minX : handle.includes("e") ? bbox.maxX : (bbox.minX + bbox.maxX) / 2;
    const hy = handle.includes("n") ? bbox.minY : handle.includes("s") ? bbox.maxY : (bbox.minY + bbox.maxY) / 2;
    let rawDX = 0, rawDY = 0; // this handle's own running total for the drag closure below
    group.append("rect")
      .attr("class", "wb-sketch-resize-handle")
      .attr("data-handle", handle)
      .attr("x", hx - 5).attr("y", hy - 5)
      .attr("width", 10).attr("height", 10)
      .style("cursor", `${handle}-resize`)
      .call(
        d3.drag()
          .on("start", (event) => {
            event.sourceEvent.stopPropagation();
            // event.dx/dy are per-frame deltas (since the *previous* event,
            // not since the drag started), recomputing the transform from
            // the original bbox using only the latest frame's delta each
            // time would apply just that one frame's worth of movement and
            // throw the rest away. Accumulated from the start instead, the
            // same fix as the drag-snap accumulation bug above.
            rawDX = 0;
            rawDY = 0;
            sketch._resizeUndoBefore = WB_KIND_INFO.sketch.payload(sketch);
            sketch._gesture = wbBeginGesture(() => {
              delete sketch._liveD;
              document.querySelector(`.sketch-group[data-id="${sketch.id}"] .sketch-path`)?.setAttribute("d", parsed.d);
              document.querySelector(`.sketch-group[data-id="${sketch.id}"] .sketch-hitbox`)?.setAttribute("d", parsed.d);
              wbLayoutShapeLabel(document.querySelector(`.sketch-group[data-id="${sketch.id}"]`));
            });
          })
          .on("drag", (event) => {
            if (sketch._gesture?.cancelled) return;
            // No `/ transform.k`, for the reason the link endpoint handle
            // above already records: this rect's drag container is its parent
            // `<g>` inside the zoomed `#wb-zoom-group`, and d3.pointer
            // resolves SVG coordinates through `getScreenCTM()`, which has
            // already folded in every ancestor transform. `event.dx` arrives
            // in board units. Dividing again halved the gesture at 2x
            // (measured: a 60px drag on the east grip widened the shape by
            // 30px on screen, where the card's own grip moved the full 60).
            rawDX += event.dx;
            rawDY += event.dy;
            const t = wbSketchResizeTransform(bbox, handle, rawDX, rawDY, event.sourceEvent.shiftKey || wbKeepsRatio("sketch", sketch), event.sourceEvent.altKey);
            const newD = (wbFmtState.shapeTable?.resized(parsed.d, t, parsed.shapeKind, wbTransformPathD, wbPathBBox) ?? wbTransformPathD(parsed.d, t));
            document.querySelector(`.sketch-group[data-id="${sketch.id}"] .sketch-path`)?.setAttribute("d", newD);
            document.querySelector(`.sketch-group[data-id="${sketch.id}"] .sketch-hitbox`)?.setAttribute("d", newD);
            wbLayoutShapeLabel(document.querySelector(`.sketch-group[data-id="${sketch.id}"]`));
            sketch._liveD = newD; // read at drag end, without waiting for a full render
            wbFollowLiveShape(sketch, newD);
            const live = wbPathBBox(newD);
            if (live) {
              placeGrips(live);
              wbShowAlignmentGuides([]);
              wbShowSizeReadout({ x: live.minX, y: live.minY, w: live.maxX - live.minX, h: live.maxY - live.minY });
            }
          })
          .on("end", async () => {
            wbClearAlignmentGuides();
            wbFollowLiveShape(sketch, null);
            const before = sketch._resizeUndoBefore;
            delete sketch._resizeUndoBefore;
            if (wbEndGesture(sketch._gesture)) delete sketch._liveD;
            delete sketch._gesture;
            if (sketch._liveD) {
              const finalD = sketch._liveD;
              delete sketch._liveD;
              //: A stretch of a turned shape is a new shape: turning it back
              //: by the old angle would give a skewed one, not an upright one,
              //: so the kept turn goes with the resize.
              await wbSaveSketchProps(sketch, { d: finalD, turned: 0 });
              if (before) wbPushUndo({ action: "move", kind: "sketch", id: sketch.id, before });
            }
            wbScheduleRender();
          })
      );
  }

  // Rotation: asked for directly, the one thing cards/objects already had
  // (a drag handle above the item, Shift snaps to 15°) that a sketch
  // didn't, since its "shape" is its path data rather than a stored
  // rotation column. Baked into `d` on release via `wbTransformPathD`'s new
  // `rotate` support, the same "commit into the path" convention move and
  // resize already use for a sketch, not a live CSS transform, which
  // would need a rotation to remember and re-apply on every future edit
  // instead of just being the shape's own coordinates.
  const centerX = (bbox.minX + bbox.maxX) / 2, centerY = (bbox.minY + bbox.maxY) / 2;
  const handleY = bbox.minY - 28;
  //: The anchor both halves of this control are scaled about, in board units:
  //: the point where the stem meets the shape. See the grip rules in
  //: 07-whiteboard-misc.css: the circle and the stem are siblings rather than
  //: an element and its pseudo-element, so the shared origin cannot be written
  //: as a percentage of either one and has to come from the bbox here.
  const rotateAnchor = `${centerX}px ${bbox.minY}px`;
  group.append("line")
    .attr("class", "wb-rotate-handle-stem")
    .style("transform-origin", rotateAnchor)
    .attr("x1", centerX).attr("y1", bbox.minY).attr("x2", centerX).attr("y2", handleY);
  // Absolute, not incremental: the handle sits straight above the shape's
  // centre (0°, the same reference `wbAngleFromCenterDeg` uses), so the
  // rotation applied is exactly the pointer's own angle from vertical, the
  // same "the handle follows your cursor" feel `nodeRotateDrag` above
  // already established for cards.
  let rotateOriginalD = null, rotateLiveD = null, rotateLiveAngle = 0, spinEls = null;
  const shapeGrip = group.append("circle")
    .attr("class", "wb-sketch-rotate-handle")
    // r 6, not 7: the card and text-box grip is 12px across
    // (`.wb-rotate-handle`), and 14 against 12 was the one measured difference
    // left between the two recipes.
    .attr("cx", centerX).attr("cy", handleY).attr("r", 6)
    .style("transform-origin", rotateAnchor)
    .style("cursor", "grab")
    .call(
      d3.drag()
        .on("start", (event) => {
          event.sourceEvent.stopPropagation();
          rotateOriginalD = parsed.d;
          sketch._rotateUndoBefore = WB_KIND_INFO.sketch.payload(sketch);
          sketch._gesture = wbBeginGesture(() => {
            rotateLiveD = null;
            group.attr("transform", null);
            document.querySelector(`.sketch-group[data-id="${sketch.id}"] .sketch-path`)?.setAttribute("d", parsed.d);
            document.querySelector(`.sketch-group[data-id="${sketch.id}"] .sketch-hitbox`)?.setAttribute("d", parsed.d);
            wbLayoutShapeLabel(document.querySelector(`.sketch-group[data-id="${sketch.id}"]`));
          });
        })
        .on("drag", (event) => {
          if (sketch._gesture?.cancelled) return;
          const currentAngle = wbSketchAngleFromCenterDeg(centerX, centerY, event.sourceEvent, event.sourceEvent.shiftKey);
          const newD = wbTransformPathD(rotateOriginalD, { rotate: currentAngle, anchorX: centerX, anchorY: centerY });
          rotateLiveD = newD;
          rotateLiveAngle = currentAngle;
          //: **The box turns with the shape** (the wb ledger, 10-25): it was
          //: drawn once round the upright shape and stayed there while the
          //: shape swung out of it. The whole handle group turns about the
          //: same centre, as a card's outline does, and the grip stays under
          //: the pointer; the release render draws the new shape's own box.
          group.attr("transform", `rotate(${currentAngle} ${centerX} ${centerY})`);
          //: Looked up on the first frame, not every frame.
          spinEls ||= wbSketchLiveEls(sketch.id);
          spinEls.path?.setAttribute("d", newD);
          spinEls.hit?.setAttribute("d", newD);
          wbLayoutShapeLabel(spinEls.g);
          wbFollowLiveShape(sketch, newD);
        })
        .on("end", async () => {
          spinEls = null;
          wbFollowLiveShape(sketch, null);
          const before = sketch._rotateUndoBefore;
          delete sketch._rotateUndoBefore;
          if (wbEndGesture(sketch._gesture)) rotateLiveD = null;
          delete sketch._gesture;
          if (rotateLiveD) {
            const finalD = rotateLiveD;
            rotateLiveD = null;
            //: The running total `wbResetRotation` turns the shape back by.
            const turned = ((Number(parsed.turned) || 0) + rotateLiveAngle) % 360;
            await wbSaveSketchProps(sketch, { d: finalD, turned });
            //: Repeat last turns the next selection by what this drag turned by (the turn is baked into the path, so there
            //: is no stored rotation to read it back from).
            wbFmtState.keys?.record({ kind: "turn", deg: rotateLiveAngle });
            if (before) wbPushUndo({ action: "move", kind: "sketch", id: sketch.id, before });
            //: Only after a real turn. A render rebuilds this grip, and a
            //: press that turned nothing (half of a double-click) then left
            //: the second press on a different element, so the browser sent
            //: the double-click to the canvas behind it and the reset never
            //: ran (measured: the event's target was `#wb-svg-layer`).
            wbScheduleRender();
          }
        })
    );
  //: The grip's two gestures, written on it: an SVG shape's tooltip is its
  //: `<title>`, the same way the map's line grip says what it does.
  shapeGrip.append("title").text("Drag to rotate: Shift snaps to 15°, double-click stands it upright");
}

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

function wbScheduleRender() {
  if (wbRenderQueued) return;
  wbRenderQueued = true;
  wbRenderFrame = requestAnimationFrame(() => {
    wbRenderFrame = 0;
    wbRenderQueued = false;
    renderWhiteboard();
    wbUpdateSelectionBar();
    wbSyncBoardCount();
    wbMapAfterRender();
    wbFmtState.opts?.afterRender();
  });
}

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

function wbCloseOrphanedPopovers() {
  editorCloseOrphans();
  for (const popover of WB_ITEM_POPOVERS) {
    const ref = popover.ref();
    if (ref && !wbFindItem(ref.kind, ref.id)) popover.close();
  }
}

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
  wbRenderNavigator();
  wbSyncBoardCount();
  wbMapAfterRender();
}

//: Delete a sketch, node or object by item (audit 1028 B7). Plain top-level
//: functions: nothing here closes over a render, so the Delete key, the
//: eraser, the menus and the selection bar all call the one function and no
//: stale closure can be the one that runs. The eraser is a drag: mouseenter
//: fires for everything the pointer crosses while `wbErasing` is true.
async function wbDeleteSketch(d) {
  const deletingKey = `sketch:${d.id}`;
  if (wbDeleting.has(deletingKey)) return;
  wbDeleting.add(deletingKey);
  //: With the links that end on it, which the server drops too (INBOX 537),
  //: and taken off the stack by identity, not by `pop`: a second delete in
  //: flight may have pushed after this one.
  const links = wbLinksTouching("sketch", d.id);
  const edgeEnds = wbFmtState.linkEdge?.beforeDelete(d); // connector ends on this one float free (whiteboard-link-edge.js)
  const entry = { action: "delete", kind: "sketch", payload: WB_KIND_INFO.sketch.payload(d), oldId: d.id, links, edgeEnds };
  const redoBefore = wbRedoStack;
  wbPushUndo(entry);
  try {
    await apiJson(`/whiteboard/sketches/${d.id}`, { method: "DELETE" });
    wbState.sketches = wbState.sketches.filter((s) => s.id !== d.id);
    wbForgetLinks(links);
    await wbFmtState.linkEdge?.afterDelete(edgeEnds);
    wbScheduleRender();
  } catch (e) {
    wbDeleteFailed(entry, redoBefore, e, () => wbDeleteSketch(d)); // the delete never happened, so neither did the undo entry
  } finally {
    wbDeleting.delete(deletingKey);
  }
}

async function wbDeleteNode(d) {
  const deletingKey = `node:${d.id}`;
  if (wbDeleting.has(deletingKey)) return;
  wbDeleting.add(deletingKey);
  const links = wbLinksTouching("node", d.id);
  const entry = { action: "delete", kind: "node", payload: WB_KIND_INFO.node.payload(d), oldId: d.id, links };
  const redoBefore = wbRedoStack;
  wbPushUndo(entry);
  try {
    await apiJson(`/whiteboard/nodes/${d.id}`, { method: "DELETE" });
    wbState.nodes = wbState.nodes.filter((n) => n.id !== d.id);
    wbForgetLinks(links);
    wbScheduleRender();
  } catch (e) {
    wbDeleteFailed(entry, redoBefore, e, () => wbDeleteNode(d));
  } finally {
    wbDeleting.delete(deletingKey);
  }
}

async function wbDeleteObject(d) {
  // The same rule as the map's own subtree delete, at the other door: this
  // is what the Delete tool, the context menu's Delete and the selection
  // bar all call, and a rule enforced at one of two doors is not a rule.
  if (WB_MAP_KINDS.has(d.kind) && wbMapDeleteEmptiesMap(d.id)) {
    wbMapRefuseLastTopic();
    return;
  }
  const deletingKey = `object:${d.id}`;
  if (wbDeleting.has(deletingKey)) return;
  wbDeleting.add(deletingKey);
  const entry = { action: "delete", kind: "object", payload: WB_KIND_INFO.object.payload(d), oldId: d.id, parentId: d.parent_id ?? null, links: wbLinksTouching("object", d.id) };
  const redoBefore = wbRedoStack;
  wbPushUndo(entry);
  try {
    const res = await apiJson(`/whiteboard/objects/${d.id}`, { method: "DELETE" });
    //: **A topic's branch is on the entry too** (INBOX 537): the server took
    //: the whole subtree, and an entry of one row brought back one topic.
    if (Array.isArray(res?.deleted) && res.deleted.length > 1) {
      Object.assign(entry, { action: "subtree", rows: res.deleted, links: Array.isArray(res.links) ? res.links : [] });
    }
    wbForgetLinks(Array.isArray(res?.links) ? res.links : entry.links);
    // **Whatever the server says it deleted, not just the row we asked
    // about.** On a map this endpoint takes the node's whole subtree and
    // returns it as `deleted[]` (§9.1), so dropping only `d.id` here left
    // every descendant on the canvas as a card pointing at a row that no
    // longer exists: visible as nodes that survive a delete and then 404
    // on the next save. Found by deleting a branch with the Delete key and
    // counting: the server removed two rows, the board still drew one of
    // them. An ordinary text box or image has no children, so `deleted`
    // is a single row there and this is exactly what it always was.
    const gone = new Set(
      Array.isArray(res?.deleted) && res.deleted.length
        ? res.deleted.map((row) => row.id)
        : [d.id]
    );
    wbState.objects = wbState.objects.filter((o) => !gone.has(o.id));
    wbScheduleRender();
  } catch (e) {
    wbDeleteFailed(entry, redoBefore, e, () => wbDeleteObject(d));
  } finally {
    wbDeleting.delete(deletingKey);
  }
}

function renderWhiteboard() {
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
  document.getElementById("wb-empty-hint")?.classList.toggle("hidden", wbHintHidden);
  //: A card turned off still leaves one line on an empty board (audit 1028 B34).
  document.getElementById("wb-empty-cue")?.classList.toggle("hidden", !(wbHintHidden && !wbIsMap() && wbBoardHolds === 0));

  // Render Sketches (SVG)
  const svgGroup = d3.select("#wb-zoom-group");
  //: Every stroke's group wherever its band put it (decision 43); a new one
  //: is made in the base layer and `wbPlaceSketchBands` moves it.
  const sketchSelection = svgGroup.selectAll(() => document.querySelectorAll("#wb-zoom-group > g.sketch-group, #wb-html-layer > svg.wb-sketch-band > g.sketch-group"))
    .data((wbState.sketches || []).filter(wbSketchIsDrawable), d => d.id);
    

  // Move: reported directly: "can't move objects made or drawn on
  // whiteboard". Cards/objects get this from their own `d3.drag`; a sketch
  // never had one at all. Filtered to the Select tool only, the same as a
  // click here means "select" rather than "erase", under any other tool
  // (pan, a brush, eraser/delete) this must stay out of the way entirely,
  // pan in particular, since the canvas's own zoom/pan drag needs an
  // unclaimed pointerdown to reach it.
  const sketchDrag = d3.drag()
    .clickDistance(WB_CLICK_SLOP)
    .filter((event) => !wbIsSecondTouch(event) && !event.button && (window.currentTool === "select" || Boolean(window.currentTool?.startsWith("link-"))))
    .on("start", function (event, d) {
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
      //: A connector drawn between two cards has no path of its own to
      //: carry (its ends follow the cards), so it starts no move: the delete
      //: target came up on its drag and stayed (INBOX 1405).
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
    })
    .on("drag", function (event, d) {
      if (d._linkKind === "sketch") return dragging.call(this, event, d);
      if (d._dragOriginalD == null || d._gesture?.cancelled) return;
      const step = wbTouchSlopStep(d._gesture, event, d3.zoomTransform(document.getElementById("whiteboard-container")).k);
      if (!step) return;
      // First real movement of this gesture, decide once whether this is
      // a solo move or a bulk move of the whole multi-selection. Deferred
      // to here rather than "start" (see its own comment) specifically so
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
      const el = document.querySelector(`.sketch-group[data-id="${d.id}"]`);
      el?.querySelector(".sketch-path")?.setAttribute("d", newD);
      el?.querySelector(".sketch-hitbox")?.setAttribute("d", newD);
      wbNudgeShapeLabel(el, dx, dy);
      if (d._bulkOrigin) wbApplyBulkMove(d._bulkOrigin, dx, dy);
      if (d._linkedSketches?.length) wbUpdateLinkedSketches(d.id, d._linkedSketches);
      wbQueueSelectionBar();
      // Handles would otherwise trail the sketch by a whole render, cheap
      // to keep in step since there are at most 8 of them.
      wbClearSketchHandles();
    })
    .on("end", async function (event, d) {
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
    });

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

  const sketchUpdate = sketchEnter.merge(sketchSelection);

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
  sketchUpdate.each(function(d) {
    const strokeKey = strokePaintKey(d);
    const drawn = this.querySelector(".sketch-path");
    if (strokeKey && this._wbStrokeKey === strokeKey && drawn?.getAttribute("d") === this._wbStrokeD) return;
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
    d3.select(this).select(".sketch-hitbox").attr("d", hitboxData ?? pathData);
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
    const fillPaint = wbSyncFillDefs(this, d.id, shapeData);
    if (fillPaint) fill = fillPaint;
    d3.select(this).select(".sketch-path")
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
    wbSetFlowAnimation(d3.select(this).select(".sketch-path").node(), flowing ? flowPeriod : 0);
    //: The Format panel's opacity and shadow (decision 19), on the group so
    //: the label goes with the shape; an attribute and an inline style, both
    //: of which the export's clone keeps.
    const look = shapeData || linkData;
    d3.select(this)
      .attr("opacity", look?.alpha != null && look.alpha < 1 ? look.alpha : null)
      .style("filter", wbShadowCss(look));
    wbSyncSketchTip(this, look);
    // After the path, which the label is laid out from (decision 12).
    wbPaintShapeLabel(this, shapeData, d);
    wbFmtState.effects?.paintShape(this, shapeData, pathData, d.id); // glass, picture fill, label shadow (whiteboard-effects.js)
    wbPaintLinkLabel(this, d, linkData);
    this._wbStrokeKey = strokeKey;
    this._wbStrokeD = strokeKey ? pathData : null;
    //: The plain path, for the jump pass to go back to when its jumps no longer apply.
    this._wbPlainD = strokeKey ? pathData : null;
  });

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
  const canvas = d3.select("#wb-html-layer");
  //: One sort of the board's items serves the bands above, the cards here and the objects below (W30).
  const stackRank = new Map(stackOrder.map((e, i) => [e.key, i + 1]));
  const nodeSelection = canvas.selectAll(".wb-card.node-card")
    .data(wbState.nodes, d => d.id);
    

  //: Card resize: asked for directly ("resizing... cards"). `width`/`height`
  //: are nullable (unset means "auto", the CSS-sized default every card used
  //: before this existed); a resize sets them explicitly for the first time.
  //: Shares `resizeDrag`'s own maths (see `renderWbObjects`) rather than a
  //: second copy: the two differ only in which element/datum they close
  //: over, so it's built inline here with the same shape.
  function nodeResizeDrag(handle) {
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
        const card = document.querySelector(`.node-card[data-id="${d.id}"]`);
        d._fitH = card && !wbExpandedNodes.has(d.id) ? wbCardFitHeight(card) : null;
        d._gesture = wbBeginGesture(() => wbRestoreBox("node", d, d._resizeUndoBefore));
      })
      .on("drag", (event, d) => {
        if (d._gesture?.cancelled) return;
        const transform = d3.zoomTransform(document.getElementById("whiteboard-container"));
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
        const el = document.querySelector(`.node-card[data-id="${d.id}"]`);
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
  }

  //: Rotation: asked for directly, more than once ("rotations", "anchor
  //: points, rotations, resizing, cropping"). A single handle above the
  //: item's own top-centre, the same convention every drawing app uses;
  //: `getBoundingClientRect()`'s centre stays correct even mid-rotation
  //: (an axis-aligned box's centre coincides with the true rotation centre
  //: regardless of how far the box itself has turned), so this needs no
  //: zoom/pan math the way position drags do, only the *angle* to the
  //: cursor matters, and angle is unaffected by uniform scale/pan.
  function nodeRotateDrag() {
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
        const el = document.querySelector(`.node-card[data-id="${d.id}"]`);
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
  }

  const nodeEnter = nodeSelection.enter()
    .append("div")
    .attr("class", "wb-card node-card")
    .attr("data-id", (d) => d.id)
    .style("transform", wbItemTransform)
    .style("width", (d) => (d.width ? `${d.width}px` : ""))
    .style("height", (d) => (d.height ? `${d.height}px` : ""))
    .style("z-index", (d) => stackRank.get(`node:${d.id}`))
    .call(d3.drag()
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
      .on("end", dragEndNode))
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
  function wbCardExpandHeight(el, d) {
    if (!el) return;
    const stored = d.height ? `${d.height}px` : "";
    if (wbExpandedNodes.has(d.id)) {
      el.style.height = "";
      el.style.minHeight = stored;
    } else {
      el.style.height = stored;
      el.style.minHeight = "";
    }
  }

  nodeEnter.each(function (d) {
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
      wbCardExpandHeight(this.closest(".wb-node") || card.node(), d);
      //: Collapsing brings the clip back, which can make the toggle itself
      //: unnecessary (a note that fits the box it was collapsed into), so
      //: the answer is recomputed rather than assumed to still hold.
      wbSyncCardClamps();
      wbSaveExpandedNodes();
    });
  });

  nodeEnter.each(function () {
    const card = d3.select(this);
    wbArmHandles(this, () => {
      for (const handle of ["nw", "n", "ne", "e", "se", "s", "sw", "w"]) {
        card.append("div")
          .attr("class", "wb-resize-handle")
          .attr("data-handle", handle)
          //: The same title the object handles carry, for the same reason: the
          //: double-click-to-fit gesture had nothing on screen saying it existed.
          .attr("title", "Drag to resize: Shift keeps the proportions, double-click fits the card to its note")
          .call(nodeResizeDrag(handle));
      }
      card.append("div")
        .attr("class", "wb-rotate-handle")
        .attr("title", "Drag to rotate: Shift snaps to 15°, double-click stands it upright")
        .call(nodeRotateDrag());
    });
  });

  wbWireContextMenu(nodeEnter, "node");

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

//: One PUT body builder for a node, shared by every call site that saves
//: one (drag-end, resize-end, bulk-move, grouping), three of those used to
//: each build the body by hand, and it was exactly that duplication that
//: let a save silently drop `group_id` back to null the first time this
//: file added it (nothing reminded the third copy to include the new field).
//: **Double-tap an anchor and the box fits its text.** Asked for directly: "I
//: want to be able tot double tap anchor edges to auto resize notes,
//: textboxes, and nstickynotes etc to auto size adjust to the text in them".
//: The drag already resizes by hand; this is the same handle saying "as
//: small as it can be and still show everything", which is the size people
//: are dragging towards most of the time and cannot hit exactly.
//:
//: Height only. A text box's width is a line-length decision (the text
//: rewraps as it changes, so "fit the width" has no fixed point: narrowing
//: makes it taller, which makes nothing shorter), and its height is the one
//: dimension with a single right answer for a given width.
//:
//: `height: auto` then `scrollHeight`: the element's own layout is the only
//: thing that knows what the text, at this width, in this font, actually
//: needs. Measured live rather than estimated from character counts, which is
//: the version of this that is wrong for every font but the one it was tuned
//: against.
//: **Double-click the rotate grip and the item stands up straight again**
//: (the owner, 2026-09-23: "double clcike the rotate point above the top
//: centre of an object and reset it to its default rotate"). The same
//: gesture Figma, Miro and PowerPoint give the grip, and the partner of the
//: resize handle's double-click-to-fit just below: a handle's double-click
//: puts back the thing that handle changes.
//:
//: A card and a text box store their angle, so this is `rotation: 0`. A
//: shape bakes its turn into its path (see the sketch rotate grip), so it
//: keeps a running total of the turns it was given in `turned` and is
//: rotated back by that much about its own centre. A shape turned before
//: `turned` existed, or resized since (see the resize grip), has nothing to
//: go back by, and says so rather than guessing. A group's grip is not here: a group has no angle of its own,
//: only members that were each turned about its centre.
async function wbResetRotation(grip, alone = false) {
  const el = grip.closest(".node-card, .wb-object");
  if (el) {
    const kind = el.classList.contains("node-card") ? "node" : "object";
    const item = (wbState[WB_LIST_BY_KIND[kind]] || []).find((i) => i.id === Number(el.dataset.id));
    if (!item || !item.rotation) return;
    const before = WB_KIND_INFO[kind].payload(item);
    //: **A frame stood upright takes what it holds with it** (the 22-10 bug
    //: doc: "if I double click the rotate" node the frame resets and its
    //: contents stay turned). The same turn a drag of its grip makes, by
    //: minus its angle, in one Undo step; Ctrl stands the frame up alone.
    if (kind === "object" && item.kind === "frame") {
      item._turnFrom = item.rotation;
      item._turnOrigin = wbFrameTurnOrigin(item, alone);
    }
    item.rotation = 0;
    el.style.transform = wbItemTransform(item);
    if (item._turnOrigin) {
      wbFrameTurnLive(item);
      await wbSaveObject(item);
      await wbFrameTurnEnd(item, { action: "move", kind, id: item.id, before });
      wbScheduleRender();
      return;
    }
    delete item._turnOrigin;
    if (kind === "node") await wbSaveNode(item);
    else await wbSaveObject(item);
    wbPushUndo({ action: "move", kind, id: item.id, before });
    wbScheduleRender();
    return;
  }
  const sketch = wbSelectedSketchOrNull();
  const parsed = sketch && wbSketchParsedData(sketch);
  if (!parsed) return;
  const turned = Number(parsed.turned) || 0;
  if (!turned) {
    toast("This shape has no turn to take back: it is upright, or was resized or turned before its angle was kept.");
    return;
  }
  const box = wbPathBBox(parsed.d);
  if (!box) return;
  const before = WB_KIND_INFO.sketch.payload(sketch);
  const d = wbTransformPathD(parsed.d, {
    rotate: -turned, anchorX: (box.minX + box.maxX) / 2, anchorY: (box.minY + box.maxY) / 2,
  });
  await wbSaveSketchProps(sketch, { d, turned: 0 });
  wbPushUndo({ action: "move", kind: "sketch", id: sketch.id, before });
  wbScheduleRender();
}

//: The height a card's text needs, chrome included (see `wbFitToText`):
//: the double-click's answer, and the "fit content" snap of a card's resize.
function wbCardFitHeight(el) {
  const content = el.querySelector(".wb-card-content");
  const previous = el.style.height;
  let fitted = 0;
  if (content) {
    const saved = {
      overflow: content.style.overflow,
      maxHeight: content.style.maxHeight,
      height: content.style.height,
    };
    //: The chrome is measured *before* anything is opened up, while the card
    //: is still in its real layout: afterwards both boxes are growing and
    //: the difference between them is no longer the padding.
    const chrome = Math.max(0, el.offsetHeight - content.offsetHeight);
    content.style.overflow = "visible";
    content.style.maxHeight = "none";
    content.style.height = "auto";
    el.style.height = "auto";
    fitted = Math.ceil(content.scrollHeight) + chrome;
    el.style.height = previous;
    for (const [name, value] of Object.entries(saved)) {
      const prop = name === "maxHeight" ? "max-height" : name;
      if (value) content.style.setProperty(prop, value);
      else content.style.removeProperty(prop);
    }
  } else {
    el.style.height = "auto";
    fitted = Math.ceil(el.scrollHeight);
    el.style.height = previous;
  }
  return fitted;
}

//: **Each grip says what its double-click does on this kind** (OPEN.md: the
//: title said "fits the text" on a picture, which has none). A frame fits
//: what it holds, a picture has nothing to fit, a table or diagram fits its
//: content, the rest fit their words.
function wbResizeHandleTitle(kind) {
  if (kind === "frame") return "Drag to resize, double-click to fit this edge to what is inside";
  if (kind === "image") return "Drag to resize: Shift keeps the proportions, double-click fits the picture";
  //: A table or a diagram has no words to fit: the double-click takes the height its content needs (L261).
  if (kind === "table" || kind === "diagram") return "Drag to resize: Shift keeps the proportions, double-click fits the height to what is inside";
  return "Drag to resize: Shift keeps the proportions, double-click fits the text";
}

//: A picture's own proportions at the width it has now (pure, node-tested).
function wbImageFitHeight(natW, natH, width) {
  if (!(natW > 0 && natH > 0)) return width;
  return Math.max(WB_OBJECT_MIN_SIZE, Math.round((width * natH) / natW));
}

//: Double-click on a picture's grip: the box takes the picture's natural
//: aspect at the current width, one undo step.
async function wbFitImage(el) {
  const item = (wbState.objects || []).find((o) => o.id === Number(el.dataset.id));
  const img = el.querySelector("img");
  if (!item || !img) return;
  const next = wbImageFitHeight(img.naturalWidth, img.naturalHeight, item.width);
  if (Math.abs(item.height - next) < 2) {
    toast("Already the picture's own shape.");
    return;
  }
  const before = WB_KIND_INFO.object.payload(item);
  item.height = next;
  el.style.height = `${next}px`;
  await wbSaveObject(item);
  wbPushUndo({ action: "move", kind: "object", id: item.id, before });
  wbScheduleRender();
  toast("Fitted to the picture.");
}

async function wbFitToText(el) {
  if (!el) return;
  const id = Number(el.dataset.id);
  const isNode = el.classList.contains("node-card");
  const item = isNode
    ? (wbState.nodes || []).find((n) => n.id === id)
    : (wbState.objects || []).find((o) => o.id === id);
  if (!item) return;
  //: A map topic has no stored height at all until someone drags one in
  //: (`sized`), and its own rule is "the text owns the height". Fitting one
  //: is therefore not a new number, it is dropping the number: the same
  //: "Back to the branch" the context menu offers for every other hand-set
  //: property.
  if (WB_MAP_KINDS.has(item.kind)) {
    if (!item.data?.sized) {
      toast("This topic is already sized to its text.");
      return;
    }
    //: **The height is a number the server accepts, never null** (INBOX 716,
    //: the owner's log: `[HTTP 422] PUT /whiteboard/objects/57: Check the
    //: height and try again.`). `height` is not nullable on the object schema,
    //: so dropping it as `null` was refused, `wbSaveObject` took the refusal
    //: for a stale board and reloaded it from the server, and the server still
    //: had the manual size: the next move of the node saved the old box back.
    //: What the topic needs is what its text needs, so it is measured once the
    //: floor is gone and stored as the drawn height, which is also what
    //: `wbMapNodeSize` falls back to before an element exists.
    const before = WB_KIND_INFO.object.payload(item);
    el.style.removeProperty("min-height");
    item.data = { ...item.data, sized: false };
    item.height = Math.max(WB_MAP_HEIGHT_FLOOR, Math.round(el.offsetHeight) || WB_MAP_NODE_H);
    //: The line follows the box in the same frame. The size measured for the
    //: edges is cached per gesture (`wbMapNodeSize`), and nothing here is a
    //: pointer-up, so without this the branch kept ending at the old box until
    //: something else redrew it.
    wbForgetMapNodeSize(item.id);
    wbUpdateMapEdges(wbMapEdgesFor(item.id));
    await wbSaveObject(item);
    wbPushUndo({ action: "move", kind: "object", id: item.id, before });
    wbScheduleRender();
    toast("Sized to its text.");
    return;
  }
  //: **The card's own `scrollHeight` is not the answer for a note card.**
  //: Reported as the gesture not working at all: *"Double tap anchor resize
  //: nodes to auto size adjust"*. Measured, the gesture fires and the toast
  //: says "Sized to its text", and a 100px card holding fourteen wrapped
  //: lines came out 103px and still clipping.
  //:
  //: The reason is one rule further in. `.wb-card-content` carries
  //: `min-height: 0; overflow: hidden` on purpose (INBOX 238: without them a
  //: note's paragraphs were painted over the board), and a capped card also
  //: carries a `max-height`. Both mean the text is already clipped *inside*
  //: the card, so the card's own scroll height with `height: auto` is the
  //: height of a box that is clipping, not the height the text needs.
  //:
  //: So the measurement opens the content up too, reads, and puts every
  //: property back exactly as it found it. Restored with
  //: `removeProperty`/assignment of the saved value rather than by setting
  //: something "sensible": these elements are re-rendered from CSS, and
  //: leaving an inline `overflow` behind would silently disable the clipping
  //: that rule exists to do.
  //: **The text's height, plus the card's chrome.** Not the card's own
  //: `scrollHeight`, which is what this used to read and which cannot answer
  //: the question: `.wb-card-content` carries `min-height: 0` and
  //: `overflow: hidden` on purpose (INBOX 238, without them a note's
  //: paragraphs were painted over the board), so the text is already clipped
  //: *inside* the card and the card's scroll height is the height of a box
  //: that is clipping, not the height the text needs. Measured: a 100px card
  //: holding fourteen wrapped lines fitted to 100px, three times running,
  //: while the toast said it had been sized to its text.
  //:
  //: So the content is opened up and measured on its own, and the difference
  //: between the card and the content (padding, a thumbnail, a Show more
  //: row) is added back. Every property is restored to exactly what it was,
  //: by removal when it was not set inline: these elements are re-rendered
  //: from CSS, and an inline `overflow` left behind would silently disable
  //: the clipping that rule exists to do.
  const fitted = wbCardFitHeight(el);
  if (!fitted) return;
  //: The same floor the resize drag uses, so a fit cannot produce a box that
  //: a drag would refuse to make.
  const next = Math.max(WB_OBJECT_MIN_SIZE, fitted);
  if (Math.abs((item.height || 0) - next) < 2) {
    toast("Already sized to its text.");
    return;
  }
  const before = WB_KIND_INFO[isNode ? "node" : "object"].payload(item);
  item.height = next;
  el.style.height = `${next}px`;
  if (isNode) await wbSaveNode(item);
  else await wbSaveObject(item);
  wbPushUndo({ action: "move", kind: isNode ? "node" : "object", id: item.id, before });
  wbScheduleRender();
  toast("Sized to its text.");
}

async function wbSaveNode(node) {
  delete node._unsaved;
  try {
    const saved = await apiJson(`/whiteboard/nodes/${node.id}`, {
      method: "PUT",
      body: JSON.stringify({
        entry_id: node.entry_id,
        board_id: node.board_id ?? window.currentBoardId ?? null,
        x: node.x, y: node.y, z: node.z,
        width: node.width ?? null, height: node.height ?? null,
        rotation: node.rotation ?? null,
        group_id: node.group_id ?? null,
        locked: Boolean(node.locked),
        comments: node.comments ?? null,
      }),
    });
    Object.assign(node, saved);
  } catch {
    recordBrowserLog("WARN", [`[Whiteboard] card ${node.id} is stale: reloading the board`]);
    await fetchWhiteboardState();
    wbScheduleRender();
    node._unsaved = true;
  }
}

async function wbSaveObject(d) {
  //: A topic still on its way to the server (`wbMapAddChild`'s optimistic
  //: add) is saved once it has its real id.
  if (d._creating) return d._creating.then((ok) => (ok ? wbSaveObject(d) : undefined));
  if (d._undoing) return;
  delete d._unsaved;
  const body = {
    kind: d.kind, data: d.data, board_id: d.board_id,
    x: d.x, y: d.y, z: d.z, width: d.width, height: d.height,
    rotation: d.rotation ?? null,
    group_id: d.group_id ?? null,
  };
  try {
    const saved = await apiJson(`/whiteboard/objects/${d.id}`, {
      method: "PUT",
      body: JSON.stringify(body),
      keepalive: wbCommitOpenEdit.leaving === true,
    });
    //: **What changed here while the save was out stays** (audit FEAT-02):
    //: with the map's add no longer waiting for its saves, a tidy or a
    //: rename can land between this request and its answer, and taking the
    //: answer whole put the topic back where it was when the request left.
    const now = { x: d.x, y: d.y, data: d.data };
    Object.assign(d, saved);
    if (now.x !== body.x || now.y !== body.y) Object.assign(d, { x: now.x, y: now.y });
    if (now.data !== body.data) d.data = now.data;
  } catch {
    // Same recoverable-stale-client shape every other whiteboard write here
    // already follows: a 404 means this object (or its board) is gone.
    recordBrowserLog("WARN", [`[Whiteboard] object ${d.id} is stale: reloading the board`]);
    await fetchWhiteboardState();
    wbScheduleRender();
    d._unsaved = true;
  }
}

//: **A selection is saved in one request** (audit 1031 BD2: Ctrl+A on 362
//: items and two arrow presses sent 167 `PUT`s and three long tasks of 189 to
//: 274 ms). `rows` is `{ kind, item }`; the server takes each item's own `PUT`
//: body plus its id (`PUT /whiteboard/items/save-many`, one transaction, all
//: or nothing). One item, or a topic still being created, goes the old way.
async function wbSaveMany(rows) {
  //: An item twice (width then height on one card) is one row: the server
  //: refuses a batch that names an id twice.
  const seen = new Set();
  const ready = rows.filter((r) => {
    const key = `${r.kind}:${r.item?.id}`;
    if (!r.item || r.item._creating || seen.has(key)) return false;
    seen.add(key);
    return true;
  });
  const waiting = rows.filter((r) => r.item?._creating);
  for (const { kind, item } of waiting) await wbSaveRow(kind, item);
  if (ready.length < 2) {
    for (const { kind, item } of ready) await wbSaveRow(kind, item);
    return true;
  }
  //: The route takes at most 5,000 of a kind a request; a larger selection
  //: goes in slices of that size (each slice all or nothing, like move-many).
  for (let at = 0; at < ready.length; at += WB_SAVE_MANY_MAX) {
    if (!(await wbSaveManyBatch(ready.slice(at, at + WB_SAVE_MANY_MAX)))) return false;
  }
  return true;
}

const WB_SAVE_MANY_MAX = 5000;

//: One `save-many` request. False (after reloading the board) when it fails.
async function wbSaveManyBatch(slice) {
  const body = { nodes: [], sketches: [], objects: [] };
  for (const { kind, item } of slice) body[WB_KIND_INFO[kind].list].push({ id: item.id, ...WB_KIND_INFO[kind].payload(item) });
  try {
    await apiJson("/whiteboard/items/save-many", { method: "PUT", body: JSON.stringify(body) });
    return true;
  } catch {
    recordBrowserLog("WARN", ["[Whiteboard] a selection is stale: reloading the board"]);
    await fetchWhiteboardState();
    wbScheduleRender();
    return false;
  }
}

function wbSaveRow(kind, item) {
  if (kind === "sketch") return wbSaveSketchProps(item, {});
  return kind === "node" ? wbSaveNode(item) : wbSaveObject(item);
}

//: A sketch's `d` written into its data without saving it (a group drag's end).
function wbSketchSetD(sketch, d) {
  const parsed = wbSketchParsedData(sketch);
  if (!parsed) return;
  wbFmtState.inkMore?.follow(parsed, d, wbPathBBox);
  parsed.d = d;
  sketch.data = JSON.stringify(parsed);
}

//: `wbSaveSketchProps`' merge without its save, for a selection saved together
//: (`wbSaveMany`). False when the sketch holds nothing to merge into.
function wbSketchSetProps(sketch, partial) {
  let parsed = null;
  try {
    const candidate = JSON.parse(sketch.data);
    if (candidate && (typeof candidate.d === "string" || (candidate.type || "").startsWith("link-"))) parsed = candidate;
  } catch {
    parsed = null;
  }
  if (!parsed) return false;
  wbFmtState.inkMore?.follow(parsed, partial.d, wbPathBBox);
  Object.assign(parsed, partial);
  sketch.data = JSON.stringify(parsed);
  return true;
}

//: The leading run of plain moves in a batch of undo steps, taken off it, so the
//: run is put back with one request (`wbApplyMoveRun`); one move goes its own way.
function wbTakeMoveRun(pending) {
  let n = 0;
  while (n < pending.length && pending[n].action === "move" && WB_KIND_INFO[pending[n].kind]) n++;
  return n > 1 ? pending.splice(0, n) : [];
}

async function wbApplyMoveRun(run) {
  const rows = [];
  const reverse = [];
  for (const entry of run) {
    const item = wbState[WB_KIND_INFO[entry.kind].list].find((i) => i.id === entry.id);
    if (!item) continue; // stale: nothing to restore, but the stack still advances
    reverse.push({ action: "move", kind: entry.kind, id: entry.id, before: WB_KIND_INFO[entry.kind].payload(item) });
    Object.assign(item, entry.before);
    rows.push({ kind: entry.kind, item });
  }
  await wbSaveMany(rows);
  return reverse;
}

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

function wbMapNodeTakeBack(d) {
  const kept = wbMapNodePool.get(d.id);
  if (!kept) return null;
  wbMapNodePool.delete(d.id);
  if (kept.__data__ !== d) return null;
  kept._wbTakenBack = true;
  return kept;
}

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

function wbScheduleStickyDates() {
  clearTimeout(wbStickyDates.timer);
  wbStickyDates.timer = setTimeout(wbPaintStickyDates, 250);
}

async function wbPaintStickyDates() {
  const papers = [...document.querySelectorAll("#whiteboard-container .wb-sticky")];
  const words = (el) => String(el.__data__?.data?.content || "");
  const ask = [...new Set(papers.map(words).filter((t) => t.trim() && !wbStickyDates.read.has(t)))].slice(0, 200);
  if (ask.length) {
    try {
      const got = await apiJson("/read/dates", { method: "POST", silent: true, body: JSON.stringify({ texts: ask, tz_offset_minutes: -new Date().getTimezoneOffset() }) });
      ask.forEach((text, i) => wbStickyDates.read.set(text, got.dates[i] || null));
    } catch {
      return;
    }
  }
  for (const paper of papers) {
    const day = wbStickyDates.read.get(words(paper));
    let tag = paper.querySelector(":scope > .wb-sticky-date");
    if (!day) {
      tag?.remove();
      continue;
    }
    if (!tag) {
      tag = chip("", "tag wb-sticky-date", (event) => {
        event.stopPropagation();
        wbStickyRemind(paper.__data__, wbStickyDates.read.get(words(paper)));
      });
      tag.addEventListener("pointerdown", (event) => event.stopPropagation());
      paper.appendChild(tag);
    }
    setLabel(tag, `${day.reminder ? "ph:bell-simple" : "ph:calendar-blank"} ${day.short}`);
    tag.title = day.reminder ? `Read as ${day.read_as}. Press to set a reminder.` : `Read as ${day.read_as}.`;
    tag.setAttribute("aria-label", tag.title);
  }
}

async function wbStickyRemind(d, day) {
  if (!d || !day?.reminder) return;
  try {
    const reminder = await apiJson("/reminders", {
      method: "POST",
      body: JSON.stringify({ text: day.reminder.text, due_at: day.reminder.due_at, priority: "normal", recurring: "none" }),
    });
    loadReminders();
    toast(`Reminder set: ${relativeWhen(reminder.due_at)}.`);
    pushBinPairUndo("Reminder set", `/reminders/${reminder.id}`, `/reminders/${reminder.id}/restore`, true, loadReminders);
  } catch (error) {
    toast(`The reminder was not set: ${error.message}`, true);
  }
}

function renderWbObjects(canvas, stackRank = wbStackRanks()) {
  wbScheduleStickyDates();

  // Shared by both `objDrag` (bound to the whole `.wb-object`) and
  // `gripDrag` (bound only to `.wb-object-grip`, see below): `this` is
  // whichever element the gesture actually started on, so every DOM write
  // goes through `this.closest(".wb-object")` rather than `this` directly,
  // the same convention `resizeDrag`'s own "drag" handler already uses.
  function objDragStart(event, d) {
    if (window.currentTool === "eraser" || window.currentTool === "delete" || window.currentTool === "bucket") return;
    // A link tool on a text box starts a *link* from it, through the same
    // three handlers the cards use, see `wbLinkItem`.
    if (window.currentTool?.startsWith("link-")) { d._linkKind = "object"; return dragStart.call(this, event, d); }
    d._linkedSketches = wbLinkedSketchesFor(d.id, "object");
    // A map node's tree edges are not sketches (see `wbMapEdgesFor`), so the
    // line above finds none of them: collected here for the same reason and
    // at the same moment.
    d._mapEdges = wbMapEdgesFor(d.id);
    // `.raise()` deliberately does NOT happen here, moved to objDragMove.
    // See the matching comment on the card drag's own `dragging` for the
    // real bug this caused (raising mid-`start` breaks the browser's click
    // synthesis, so a plain click-to-select on an object never fired).
    // See the matching comment on the card drag's own `dragStart`: a raw,
    // never-snapped running position, so small per-frame deltas actually
    // accumulate instead of being rounded away against the previous
    // frame's already-snapped value.
    d._rawX = d.x;
    d._rawY = d.y;
    d._dragOriginX = d.x;
    d._dragOriginY = d.y;
    d._raised = false;
    d._moveUndoBefore = WB_KIND_INFO.object.payload(d);
    d._altCopy = Boolean(event.sourceEvent?.altKey);
    d._gesture = wbBeginGesture(() => wbRestoreMove("object", d), true);
    // Bulk-move detection is deliberately deferred to the first real
    // "drag" frame below, not decided here, see the matching comment on
    // the sketch drag's own "start" for the click-toggle bug that caused.
  }
  function objDragMove(event, d) {
    if (window.currentTool === "eraser" || window.currentTool === "delete" || window.currentTool === "bucket") return;
    if (window.currentTool?.startsWith("link-")) return dragging.call(this, event, d);
    if (d._gesture?.cancelled) return;
    const step = wbTouchSlopStep(d._gesture, event);
    if (!step) return;
    if (d._bulkOrigin === undefined) {
      //: **A map node drags its branch with it** (MINDMAP_PLAN.md §12.1 item
      //: 8). Decided on the first real drag frame, like the marquee case
      //: beside it and for the same reason (see the sketch drag's own "start"
      //: comment): deciding at `start` turns a click into a bulk move.
      //: Ctrl held means the topic travels alone, and is read here because
      //: that is the frame the decision is made in.
      d._dragAlone = Boolean(event.sourceEvent?.ctrlKey || event.sourceEvent?.metaKey);
      d._bulkOrigin = wbDragIsBulkMove("object", d.id)
        ? wbCaptureBulkMoveOrigin(wbMultiKey("object", d.id))
        : wbMapBranchDragOrigin(d, d._dragAlone) || wbFrameDragOrigin(d, d._dragAlone);
    }
    //: Once per gesture, not once per move: the card drag beside this one
    //: took the same fix (INBOX 114, and see its own comment). `raise()`
    //: reappends the element even when it is already last, and a DOM move
    //: invalidates layout, so every frame's first `getBoundingClientRect`
    //: (the drop target's, below) paid for a full re-layout of the board.
    if (!d._raised) {
      d3.select(this.closest(".wb-object")).raise();
      d._raised = true;
    }
    // d3.drag's dx/dy are raw screen pixels, not board-space, the
    // resize handles below already divide by the zoom scale for exactly
    // this reason; a plain drag has to as well, or a card/object moves
    // faster than the cursor when zoomed out and slower when zoomed in.
    const transform = d3.zoomTransform(document.getElementById("whiteboard-container"));
    d._rawX = (d._rawX ?? d.x) + step.dx / transform.k;
    d._rawY = (d._rawY ?? d.y) + step.dy / transform.k;
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
    // grid-snap just above: holding it means "no snap assistance at all
    // for this drag", one concept, not two separate modifier keys to learn.
    if (!bypassSnap) {
      //: The group's own box when several things are moving, the item's when
      //: one is. Either way the delta lands on `d`, and `wbApplyBulkMove`
      //: below carries the rest of the selection by the same amount.
      const group = wbBulkGroupBox(d, "object");
      const own = wbRotatedBounds(d.x, d.y, d.width, d.height, wbItemRotation("object", d));
      const { dx, dy, guideLines } = wbAlignmentGuides(
        wbDragExcludeKeys(d, "object"),
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
    d3.select(this.closest(".wb-object")).style("transform", wbItemTransform(d));
    //: The branch first and this topic's own lines after it, for the reason
    //: `wbApplyBulkMove` gives: a line drawn before its other end has moved
    //: is a line a frame behind.
    if (d._bulkOrigin) wbApplyBulkMove(d._bulkOrigin, d.x - d._dragOriginX, d.y - d._dragOriginY);
    if (d._linkedSketches?.length) wbUpdateLinkedSketches(d.id, d._linkedSketches);
    if (d._mapEdges?.length) wbUpdateMapEdges(d._mapEdges);
    wbQueueSelectionBar();
    // The topic this branch would land on, lit as you pass over it. From the
    // pointer's own position rather than the node's, because what you aim at
    // is where you are pointing, not where the box has caught up to.
    const source = event.sourceEvent;
    if (source && wbIsMap() && WB_MAP_KINDS.has(d.kind)) {
      d._dropTarget = wbMapDropTargetAt(d, source.clientX, source.clientY);
      wbMapShowDropTarget(d._dropTarget?.id ?? null);
      //: Not over a topic: a gap among its siblings, where the layout stacks
      //: them. One topic only: a group drag stays a placement.
      d._siblingSlot = d._dropTarget || d._dragAlone || d._bulkOrigin ? null : wbMapSiblingSlotAt(d, source.clientX, source.clientY);
      wbMapShowSlotCue(d._siblingSlot);
    }
  }
  async function objDragEnd(event, d) {
    if (window.currentTool === "eraser" || window.currentTool === "delete" || window.currentTool === "bucket") return;
    if (window.currentTool?.startsWith("link-")) { const r = dragEndNode.call(this, event, d); d._linkKind = null; return r; }
    //: Dropped on the delete target: put back, then deleted (INBOX 660).
    wbTrashTake(d._gesture, "object", d);
    d._linkedSketches = null;
    // Dropped: the paths this drag held references to are about to be
    // replaced by the next render, and a stale element would be updated in
    // place forever (invisibly, since it is no longer in the document).
    d._mapEdges = null;
    wbClearAlignmentGuides();
    const bulkOrigin = d._bulkOrigin;
    // Reset unconditionally: a solo drag sets this to `null` (see
    // "drag" above), and leaving it there would make the *next* gesture's
    // `=== undefined` check think bulk-move was already decided and skip
    // redetecting it, permanently treating this object as "never bulk"
    // even after it later joins a multi-selection.
    delete d._bulkOrigin;
    //: Dropped on another topic: that is a transplant, not a placement, and
    //: it replaces the ordinary save below entirely (`/move` is the only
    //: endpoint that may write `parent_id`, and it re-lays the branch after).
    const dropTarget = d._dropTarget;
    const slot = d._siblingSlot;
    delete d._siblingSlot;
    const alone = d._dragAlone;
    delete d._dropTarget;
    delete d._dragAlone;
    wbMapClearDropTarget();
    const altCopy = d._altCopy;
    delete d._altCopy;
    if (wbEndGesture(d._gesture)) {
      delete d._gesture;
      delete d._moveUndoBefore;
      return;
    }
    delete d._gesture;
    if (dropTarget) {
      //: Where the branch was picked up, so the transplant's one Undo puts it
      //: back there rather than where it was let go (INBOX 410).
      const before = new Map();
      if (d._moveUndoBefore) before.set(d.id, { x: d._moveUndoBefore.x, y: d._moveUndoBefore.y });
      for (const entry of bulkOrigin?.values() || []) {
        if (entry.kind === "object" && !before.has(entry.id)) before.set(entry.id, { x: entry.x, y: entry.y });
      }
      delete d._moveUndoBefore;
      if (bulkOrigin) await wbSaveBulkMove(bulkOrigin);
      await wbMapTransplant(d, dropTarget.id, alone, { before });
      return;
    }
    if (slot) {
      const origins = new Map();
      if (d._moveUndoBefore) origins.set(d.id, { x: d._moveUndoBefore.x, y: d._moveUndoBefore.y });
      for (const entry of bulkOrigin?.values() || []) {
        if (entry.kind === "object" && !origins.has(entry.id)) origins.set(entry.id, { x: entry.x, y: entry.y });
      }
      delete d._moveUndoBefore;
      await wbMapDropAmongSiblings(d, slot, origins);
      return;
    }
    const moveBefore = d._moveUndoBefore;
    delete d._moveUndoBefore;
    //: **A click is not a drop, and must not save.** `objDrag` runs for a
    //: plain click too (d3-drag listens for `mousedown`, and a click is a
    //: mousedown with no movement), and this used to PUT the object every
    //: time regardless. On its own that is only a wasted request; the bug is
    //: that the PUT carries whatever `d.data` held when the gesture ended,
    //: and a click on a control *inside* the node (the chevron, the count
    //: badge, the two add buttons) fires its own save in the same tick. Two
    //: PUTs to one row with no defined order: measured on the fold chevron,
    //: one click sent `collapsed: null` and `collapsed: true` and the map
    //: kept whichever landed second, so a branch folded on screen and came
    //: back unfolded on the next refresh. Found by `mindmap.js`'s SVG export
    //: check, which counted two edges where the map had four.
    //:
    //: The same "did it really move" test the undo entry below already used,
    //: hoisted above the save so it governs both.
    const reallyMoved = !moveBefore || moveBefore.x !== d.x || moveBefore.y !== d.y;
    if (reallyMoved) await wbSaveObject(d);
    if (d._unsaved) {
      //: A drop that could not be saved (offline, or the item is gone) goes back where it was taken
      //: from, with a word, rather than staying where the server does not have it (`_unsaved`, set by
      //: the save's catch).
      delete d._unsaved;
      if (moveBefore) Object.assign(d, { x: moveBefore.x, y: moveBefore.y });
      wbScheduleRender();
      toast(voiceLine("failed", { what: "save the move", why: "the item went back where it was" }), true, { action: ["Reload the board", () => fetchWhiteboardState().then(wbScheduleRender)] });
      return;
    }
    const primary = moveBefore && reallyMoved
      ? { action: "move", kind: "object", id: d.id, before: moveBefore }
      : null;
    await wbFinishDrag(primary, bulkOrigin, altCopy);
    // A map node that was actually moved is now pinned, see
    // `wbMapPinOnDrag`. Gated on the same "did it really move" check the
    // undo entry uses, so a click is never mistaken for a placement.
    if (primary) await wbMapPinOnDrag(d);
  }

  const objDrag = d3.drag()
    // A resize handle owns its own drag (below); a text box's own text
    // needs plain clicks/selection to reach it, not a canvas-wide drag. And,
    // same reasoning as the card drag's own filter above: a brush tool must
    // be able to draw over an image/text object, not drag it. `.wb-object-grip`
    // has its own separate drag instance (`gripDrag`, below): excluded here
    // so a grip grab doesn't *also* start this instance for the same
    // gesture. A real bug caught live: excluding it here alone isn't enough
    //, `objDrag` is one shared behaviour object bound to both the object
    // and the grip, so its filter runs for *both* elements' own pointerdown,
    // and target-closest can't tell "the grip's own listener" from "the
    // object's listener catching a bubbled grip click" apart. `gripDrag`
    // below exists precisely because that distinction needs two behaviour
    // objects, not one filter.
    .filter((event) => {
      //: **The primary button only** (the owner, 2026-09-24: the middle-button
      //: pan "jerks"). d3-drag's own default filter is `!event.button`, and
      //: writing a filter replaces it rather than adding to it, so this one
      //: took every button: a middle press on a topic or a card started a
      //: drag of that item and stopped the event before the board's pan ever
      //: saw it (measured, `midpanwheel.js`: a 200px middle drag started on
      //: the root moved the board 0px). The middle button is the pan from
      //: anywhere, which is what `wbZoomFilter` promises.
      if (event.button || wbIsSecondTouch(event)) return false;
      if (WB_BRUSH_TOOLS.has(window.currentTool) || window.currentTool === "lasso") return false;
      if (event.target.closest(
        ".wb-resize-handle, .wb-rotate-handle, .wb-object-grip"
        + ", .wb-map-resize-grip"
      )) return false;
      // `.wb-text-content` used to be excluded outright, which is what left a
      // text box draggable only by its grip, see `wbBeginTextEdit`. It only
      // needs to keep the pointer while it is *being edited*, for the caret
      // and for selecting words; the rest of the time it is just the face of
      // a box and drags like one.
      //
      // **Asked for by class, this missed the map node entirely.** Reported:
      // "I cant highlight text in mindmap text boxes." A map node's editor is
      // `.wb-map-text`, not `.wb-text-content`, so this filter let the drag
      // run: measured, a click-drag across a node being edited selected the
      // empty string and moved the node 165px instead. The node's own
      // `pointerdown` stopPropagation cannot help, d3-drag listens for
      // `mousedown`, and this file already records that two event families
      // cannot cancel each other (see the marquee's handle-layer comment).
      // Asking the *element* whether it is editable rather than naming the
      // classes that happen to be editable today is what stops the next
      // editable surface on the canvas from re-learning this.
      const text = event.target.closest("[contenteditable]");
      if (text && text.isContentEditable) return false;
      return true;
    })
    .on("start", objDragStart)
    .on("drag", objDragMove)
    .on("end", objDragEnd);

  // The grip's own drag instance (see the comment above), `stopPropagation`
  // on start is the same fix `resizeDrag`/`objectRotateDrag` already use to
  // keep their own handle grabs from also bubbling into the object's own
  // `objDrag` listener.
  const gripDrag = d3.drag()
    // The grip sits inside the box it moves, see `wbStableDragContainer`.
    .container(wbStableDragContainer(".wb-object"))
    .filter((event) => !wbIsSecondTouch(event) && !event.button && !WB_BRUSH_TOOLS.has(window.currentTool) && window.currentTool !== "lasso")
    .on("start", function (event, d) {
      event.sourceEvent.stopPropagation();
      objDragStart.call(this, event, d);
    })
    .on("drag", objDragMove)
    .on("end", objDragEnd);

  function resizeDrag(handle) {
    return d3.drag()
      // The handle sits inside the object it resizes, see
      // `wbStableDragContainer`. Matters for `w`/`n`, which move x/y too.
      .container(wbStableDragContainer(".wb-object"))
      .on("start", function (event, d) {
        event.sourceEvent.stopPropagation(); // don't also start objDrag
        d._resizeUndoBefore = WB_KIND_INFO.object.payload(d);
        //: From where the gesture began rather than frame on frame, like the
        //: card's resize: a proportion held with Shift is a proportion of the
        //: box you took hold of, and a per-frame delta has no memory of it.
        d._resizeStart = { x: d.x, y: d.y, w: d.width, h: d.height, dx: 0, dy: 0 };
        d._linkedSketches = wbLinkedSketchesFor(d.id, "object");
        d._gesture = wbBeginGesture(() => wbRestoreBox("object", d, d._resizeUndoBefore));
      })
      .on("drag", function (event, d) {
        const start = d._resizeStart;
        if (!start || d._gesture?.cancelled) return;
        const transform = d3.zoomTransform(document.getElementById("whiteboard-container"));
        start.dx += event.dx / transform.k;
        start.dy += event.dy / transform.k;
        const box = wbResizeBox(start, handle, start.dx, start.dy,
          event.sourceEvent.shiftKey || wbKeepsRatio("object", d), event.sourceEvent.altKey, WB_OBJECT_MIN_SIZE);
        let newWidth = box.w, newHeight = box.h, newX = box.x, newY = box.y;
        if (!event.sourceEvent.shiftKey && !event.sourceEvent.altKey) {
          ({ width: newWidth, height: newHeight } = wbGuidedResize("object", d, handle, start, newWidth, newHeight, { off: false }));
          newX = handle.includes("w") ? start.x + start.w - newWidth : start.x;
          newY = handle.includes("n") ? start.y + start.h - newHeight : start.y;
        } else {
          //: Shift (keep the ratio) and Alt (no guides) skip the guided
          //: resize, which is what draws the size readout; it shows anyway.
          wbShowAlignmentGuides([]);
          wbShowSizeReadout({ x: newX, y: newY, w: newWidth, h: newHeight });
        }
        d.x = newX;
        d.y = newY;
        d.width = newWidth;
        d.height = newHeight;
        const el = d3.select(this.closest(".wb-object"));
        el.style("width", `${d.width}px`)
          .style("height", `${d.height}px`)
          .style("transform", wbItemTransform(d));
        //: A sticker's glyph is its box (decision 44), so it grows with the
        //: grip, not on the next render (the 22-10 bug doc: "Emojis don't
        //: size or scale with its borders").
        if (d.data?.sticker) el.select(".wb-text-content").style("font-size", `${wbStickerSize(d)}px`);
        //: **The lines and the clone arrows follow a resize as they follow a
        //: move** (INBOX 746's "the arrows dont resize either"). The box a
        //: link aims at is read from the measured size the last render
        //: cached, so that entry goes first; without both lines a stretched
        //: sticky kept its links ending where its old sides were until the
        //: next render (measured 14.7 and 48 board units off the outline).
        wbMapNodeSizeCache?.delete(d.id);
        if (d._linkedSketches?.length) wbUpdateLinkedSketches(d.id, d._linkedSketches);
        wbQueueSelectionBar();
      })
      .on("end", async (event, d) => {
        wbClearAlignmentGuides();
        delete d._resizeStart;
        delete d._linkedSketches;
        const before = d._resizeUndoBefore;
        delete d._resizeUndoBefore;
        const cancelled = wbEndGesture(d._gesture);
        delete d._gesture;
        if (cancelled || (before && before.width === d.width && before.height === d.height)) return;
        await wbSaveObject(d);
        if (before) wbPushUndo({ action: "move", kind: "object", id: d.id, before });
        //: The save repaints nothing, and what a box draws from its size (a
        //: sticker's glyph, a frame's title, a table's grid) waited for some
        //: later render to catch up.
        wbScheduleRender();
      });
  }

  //: Same as `nodeRotateDrag` above: kept as two small copies rather than
  //: one shared function because they close over different elements/PUT
  //: helpers (`.node-card` vs `.wb-object`, `wbSaveNode` vs `wbSaveObject`),
  //: the same reasoning `nodeResizeDrag`'s own comment already gives for not
  //: sharing with `resizeDrag`.
  function objectRotateDrag() {
    //: Not d3's default filter, which refuses a Ctrl press: Ctrl is how a
    //: frame is turned without what it holds.
    return d3.drag()
      .clickDistance(WB_CLICK_SLOP)
      .filter((event) => !event.button)
      .on("start", (event, d) => {
        event.sourceEvent.stopPropagation();
        d._rotateUndoBefore = WB_KIND_INFO.object.payload(d);
        //: The links touching it, found once: a turn moves their endpoints
        //: as much as a move does, and without this they stayed where the
        //: unturned box had them until the next move (INBOX 647).
        d._linkedSketches = wbLinkedSketchesFor(d.id, "object");
        //: Decided here, not per frame: the set a turn carries is the set
        //: inside the frame when the grip was taken.
        const alone = Boolean(event.sourceEvent.ctrlKey || event.sourceEvent.metaKey);
        d._turnFrom = d.rotation || 0;
        d._turnOrigin = wbFrameTurnOrigin(d, alone);
        d._gesture = wbBeginGesture(() => {
          wbRestoreBox("object", d, d._rotateUndoBefore);
          wbFrameTurnRevert(d);
        });
      })
      .on("drag", (event, d) => {
        if (d._gesture?.cancelled) return;
        const el = document.querySelector(`.wb-object[data-id="${d.id}"]`);
        if (!el) return;
        const rect = el.getBoundingClientRect();
        d.rotation = wbAngleFromCenterDeg(
          rect.left + rect.width / 2, rect.top + rect.height / 2,
          event.sourceEvent.clientX, event.sourceEvent.clientY,
          event.sourceEvent.shiftKey
        );
        el.style.transform = wbItemTransform(d);
        wbFrameTurnLive(d);
        if (d._linkedSketches?.length) wbUpdateLinkedSketches(d.id, d._linkedSketches);
        wbQueueSelectionBar();
      })
      .on("end", async (event, d) => {
        const before = d._rotateUndoBefore;
        delete d._rotateUndoBefore;
        delete d._linkedSketches;
        const cancelled = wbEndGesture(d._gesture);
        delete d._gesture;
        if (cancelled || (before && (before.rotation || 0) === (d.rotation || 0))) {
          wbFrameTurnRevert(d);
          return;
        }
        await wbSaveObject(d);
        wbFmtState.keys?.record({ kind: "turn", deg: (d.rotation || 0) - (before?.rotation || 0) });
        if (!d._turnOrigin) {
          if (before) wbPushUndo({ action: "move", kind: "object", id: d.id, before });
          return;
        }
        await wbFrameTurnEnd(d, before && { action: "move", kind: "object", id: d.id, before });
      });
  }

  // The map facts for this render pass, computed once here rather than per
  // node: `wbMapColors` walks the whole tree by design (see its own comment),
  // and calling it from inside a per-node callback would walk it once per node.
  const mapIndex = wbIsMap() ? wbMapIndex() : null;
  //: Each topic's level (MINDMAP_PLAN.md decision 38), before anything is
  //: painted or measured: its look, and so its size, depend on it.
  if (mapIndex) wbMapLevels(mapIndex);
  const mapColors = mapIndex ? wbMapNodeColors(mapIndex) : null;
  const mapFills = mapIndex ? wbMapFills(mapIndex) : null;
  const mapHidden = mapIndex ? wbMapConcealed(mapIndex) : null;
  // The focus bar's counts, the legend's rows and the template offer all
  // describe the map this pass is about to draw (§5 items 18 to 21).
  wbSyncMapViews(mapIndex);
  // **A collapsed branch leaves the DOM rather than being hidden with CSS.**
  // The export, the board bounds, the marquee and every `querySelector` in
  // this file read the DOM, a `display: none` node would still be found by
  // all four, so a folded branch would keep showing up in exports and keep
  // stretching the board's bounds while being invisible on screen.
  const objectData = mapHidden?.size
    ? (wbState.objects || []).filter((o) => !mapHidden.has(o.id))
    : (wbState.objects || []);
  const objectSelection = canvas.selectAll(".wb-object")
    .data(objectData, (d) => d.id);

  // A map node is `height: auto`, its own text decides how tall it is, so a
  // long topic grows its box instead of being sliced by `overflow: hidden`,
  // which is the failure CLAUDE.md records costing six rounds on one popup.
  const objectHeight = (d) => (WB_MAP_KINDS.has(d.kind) ? "auto" : `${d.height}px`);

  const objectEnter = objectSelection.enter()
    .append((d) => wbMapNodeTakeBack(d) || document.createElement("div"))
    .attr("class", (d) => `wb-object wb-object-${d.kind}`)
    .attr("data-id", (d) => d.id)
    .style("transform", wbItemTransform)
    .style("width", (d) => `${(WB_MAP_KINDS.has(d.kind) && wbMapNodeSize.narrow(d)) || d.width}px`)
    .style("height", objectHeight)
    .style("z-index", (d) => stackRank.get(`object:${d.id}`))
    .call(objDrag)
    .on("click", (event, d) => {
      // ROADMAP row 0(b), asked for directly: with the Hand active, a plain
      // click on something switches to Select and selects it. A pan is a
      // drag; a click that moved nothing is a choice of *this*, and every
      // whiteboard app (Miro, FigJam, tldraw) reads it that way.
      if (window.currentTool === "select" || window.currentTool === "pan") {
        event.stopPropagation();
        if (window.currentTool === "pan") wbSelectToolRef?.("select");
        wbHandleItemClick("object", d.id, event);
        return;
      }
      if (window.currentTool === "delete" || window.currentTool === "eraser") wbDeleteObject(d);
    })
    .on("pointerenter", (event, d) => {
      if (window.currentTool === "eraser" && wbErasing) wbDeleteObject(d);
    });

  objectEnter.each(function (d) {
    const el = d3.select(this);
    //: A topic coming back out of a fold keeps the body it was built with
    //: (`wbMapNodeTakeBack`): its handlers close over this same datum. The
    //: class line above reset its classes, so the one the build adds goes
    //: back on, and the paint below runs in full because its key is gone.
    if (this._wbTakenBack) {
      delete this._wbTakenBack;
      el.classed("wb-map-node", true);
      this._wbPaintKey = undefined;
      return;
    }
    if (d.kind === "image") {
      // Asked for directly: an image deleted out from under a board (via
      // the Library gallery's own delete, or by hand off disk) left a
      // plain broken-image glyph: "there should probably be a placeholder
      // or closable box that says it is deleted in its place." The close
      // button removes the object outright rather than leaving a
      // permanently-broken box on the board.
      el.append("img").attr("src", mediaSrc(d.data.url) || "").attr("alt", "")
        .on("error", function () {
          d3.select(this).remove();
          if (el.select(".wb-object-deleted").empty()) {
            const placeholder = el.append("div").attr("class", "wb-object-deleted");
            placeholder.append("span").text("Image deleted");
            placeholder.append("button")
              .attr("type", "button")
              .attr("class", "ghost small icon-button")
              .attr("title", "Remove this")
              .attr("aria-label", "Remove this")
              //: `setLabel`, not `.text("\u2715")`: a typed cross renders in
              //: the page font at the text's own weight beside Phosphor icons
              //: everywhere else in this bar. d3 has no icon idiom, so the
              //: element is handed to the app's own one.
              .each(function () { setLabel(this, "ph:x"); })
              .on("click", (event) => { event.stopPropagation(); wbDeleteObject(d); });
          }
        });
    } else if (d.kind === "frame") {
      wbBuildFrame(el, d);
    } else if (d.kind === "table") {
      wbBuildTable(el, d);
    } else if (d.kind === "diagram") {
      wbBuildDiagram(el, d);
    } else if (WB_MAP_KINDS.has(d.kind)) {
      // A map node, not a text box. Checked before the `else` below because
      // that branch is "everything that isn't an image", which is what drew a
      // topic as a bare, unlabelled text box for as long as the kinds existed
      // without this: stored, served, and on screen as nothing recognisable.
      wbBuildMapNode(el, d);
    } else {
      // Fill/border, asked for directly (the properties panel): set on the
      // outer object div, which is what `.wb-object-text`'s own default
      // background/border style, so an unset value falls back to the CSS
      // default rather than an empty override.
      el.style("background", wbPaperPaint(d.data)).style("border-color", d.data.border_color || "");
      // Asked for directly ("objects are also difficult and annoying to
      // move around"): `.wb-text-content` fills the entire box and both
      // the filter above and its own pointerdown handler below correctly
      // keep drag away from it while typing, which meant the *only*
      // draggable surface left was the ~0.5rem padding strip around the
      // text, the same width as the resize handles that sit right on top
      // of it. A dedicated grip, same convention as the panels' own
      // `.wb-panel-grip`, gives a guaranteed, adequately-sized place to
      // grab regardless of how much text is in the box. Text objects only: 
      // an image has no competing contenteditable claim on its body, so it
      // was already fully draggable once the resize-handle bug above was
      // fixed.
      el.append("div")
        .attr("class", "wb-object-grip")
        .attr("title", "Drag to move")
        .text("⠿")
        .call(gripDrag);
      const content = el.append("div")
        .attr("class", "wb-text-content")
        // Not editable until asked, see `wbBeginTextEdit` for why.
        .attr("contenteditable", "false")
        .style("color", d.data.color ? wbReadableInk(d.data.color, d.data.bg || wbBoardBg()) : "")
        .style("font-size", d.data.font_size ? `${d.data.font_size}px` : "")
        .text(d.data.content || "");
      // Saved on blur, not on every keystroke, a PUT per character would
      // flood the server and make undo/redo of everything *else* land
      // between two half-typed states.
      content.on("blur", function () {
        wbEndTextEdit(this);
        const edited = wbEditedText(this);
        //: Unchanged: nothing to save or record, but the box still goes back
        //: from its raw source to the rendered view.
        //: Formatted from the selection bar or Ctrl+B: shown rendered (K24).
        const formatted = this.dataset.wbFormatted === "1";
        delete this.dataset.wbFormatted;
        const grownFrom = this.wbBeforeGrow;
        delete this.wbBeforeGrow;
        if (d.data.content === edited) {
          if (grownFrom) {
            wbPushUndo({ action: "move", kind: "object", id: d.id, before: grownFrom });
            wbSaveObject(d);
          }
          wbScheduleRender();
          return;
        }
        wbPushUndo({ action: "move", kind: "object", id: d.id, before: grownFrom || WB_KIND_INFO.object.payload(d) });
        d.data = formatted ? { ...d.data, content: edited, md: true } : { ...d.data, content: edited };
        wbGrowBoxToWords(this, d);
        wbSaveObject(d);
        //: A formatted edit is shown rendered (K24), and nothing else asked for
        //: that: the box kept its raw `**x**` or `{{size=24|x}}` source on
        //: screen until some other change repainted the board.
        if (formatted) wbScheduleRender();
      });
      content.on("input", function () {
        if (this.isContentEditable) wbGrowBoxToWords(this, d);
      });
      // Typing is text-box business, not the canvas's: Delete/Backspace
      // here must edit the text, not delete the whole box the way the same
      // keys do when an object is merely *selected*. Both of these are gated
      // on actually being in edit mode now: a box that is not being edited
      // has to let the pointer through to the object's own drag, and its
      // Delete key belongs to the canvas again.
      content.on("keydown", function (event) {
        if (!this.isContentEditable) return;
        event.stopPropagation();
        //: **Escape ends the edit and leaves the box selected** (INBOX 445),
        //: what Excalidraw, tldraw and Figma all do. The line above stopped
        //: every key, Escape with them, so the caret stayed in the box after
        //: Escape and the next tool letter (T, R) was typed into the sticky
        //: instead of picking the tool. Blurring runs the save above.
        if (event.key === "Escape") {
          event.preventDefault();
          this.blur();
          selectWbItem("object", d.id);
          document.getElementById("whiteboard-container")?.focus({ preventScroll: true });
          return;
        }
        if (event.key === "Tab" && !event.ctrlKey && !event.altKey && !event.metaKey) {
          if (wbIndentEditableLines(this, event.shiftKey)) event.preventDefault();
        }
        if (wbTextFormatKey(event)) return;
        //: **Sticky chain** (WHITEBOARD_PLAN gap row 6, Miro's Tab): Ctrl+Enter
        //: ends this sticky and starts the next beside it, same paper and size.
        //: Not Tab, which indents a sticky's lines here.
        if (event.key === "Enter" && (event.ctrlKey || event.metaKey) && wbIsSticky(d)) {
          event.preventDefault();
          this.blur();
          wbCreateSticky(0, 0, { x: d.x + d.width + 24, y: d.y, w: d.width, h: d.height }, d);
        }
      });
      content.on("pointerdown", function (event) {
        if (this.isContentEditable) event.stopPropagation();
      });
      content.on("dblclick", function (event) {
        event.stopPropagation();
        if (wbJustDrilled()) return;
        wbBeginTextEdit(this);
      });
    }
    // A map node gets neither. Its height is its text's (see `objectHeight`),
    // so a vertical resize handle would fight the content and lose; and a
    // rotated node is a node whose edges no longer meet its anchors, which
    // makes the tree unreadable for no gain a mind-mapper has ever asked for.
    // The eight handles and the rotate grip also sit exactly where the
    // chevron and the `+` do, and would swallow both.
    if (WB_MAP_KINDS.has(d.kind)) return;
    wbArmHandles(this, () => wbBuildObjectHandles(el, d.kind));
  });

  //: The eight sizes and the turn grip of one object, built on first need
  //: (`wbArmHandles`).
  function wbBuildObjectHandles(el, kind) {
    for (const handle of ["nw", "n", "ne", "e", "se", "s", "sw", "w"]) {
      el.append("div")
        .attr("class", "wb-resize-handle")
        .attr("data-handle", handle)
        //: **The gesture says it exists.** The rotate grip beside these has
        //: carried a title explaining its own modifier since it was built;
        //: these had none, so double-tapping to fit was real and invisible,
        //: which is indistinguishable from missing and was duly reported as
        //: missing.
        .attr("title", wbResizeHandleTitle(kind))
        .call(resizeDrag(handle));
    }
    //: A table's grid holds nothing square once turned. A frame does turn
    //: (INBOX 1327, reversing decision 14's "no rotation"), and what lies
    //: wholly inside it turns with it (decision 42, `wbFrameTurnOrigin`).
    if (kind === "table") return;
    el.append("div")
      .attr("class", "wb-rotate-handle")
      .attr("title", wbRotateGripTitle(kind))
      .call(objectRotateDrag());
  }

  wbWireContextMenu(objectEnter, "object");

  const objectUpdate = objectEnter.merge(objectSelection);
  //: **A render repaints the objects that changed, not every object on the
  //: board** (MINDMAP_PLAN.md §13a, the render pass). The four `.style` calls
  //: this replaces ran for every object on every render, and the `.each`
  //: below them repainted every map node whether or not anything about it had
  //: moved: at 500 topics that was 2,000 style writes and 500 full node
  //: repaints for a change to one of them.
  //:
  //: The key is every input this pass reads, in one string. An object whose
  //: key is what it was last render draws exactly what it is already
  //: drawing, so the cheapest correct thing to do with it is nothing. A fresh
  //: element (the enter selection) has no key at all, so it always paints.
  //: `wbObjectPaintKey` is the one list of those inputs: a property this pass
  //: starts reading has to go into it, and the way that failure shows is a
  //: node that stops following a change, which is what `mapstrip.js`,
  //: `maptheme.js`, `mapline.js` and `maprejoin.js` each ask about directly.
  const paintCtx = {
    index: mapIndex,
    colors: mapColors,
    //: A fill can come from an ancestor, so a topic whose own data did not
    //: change can still need repainting when its branch is filled.
    fills: mapFills,
    //: Read once for the pass, not once per node: both are board-wide, and
    //: `wbMapThemedData` merges the theme underneath every node's own data.
    layout: mapIndex ? wbMapLayout() : "",
    theme: mapIndex ? JSON.stringify(wbMapTheme()) : "",
    fold: wbBoardBackground().sticky_fold !== false,
  };
  // An image's own src can change (rare: nothing in this UI replaces one
  // yet, but a future paste-to-replace shouldn't need this rewritten) and a
  // text box's saved colour/size might have changed elsewhere (undo/redo);
  // the text itself is deliberately left alone here so a re-render mid-edit
  // (another item moving, say) can't overwrite what's being typed.
  //: **Moves are written after the measure, and only what was repainted is
  //: measured** (FEAT-02's 100ms gate). A tidy that shifts two hundred topics
  //: wrote two hundred transforms here, and the measure's first
  //: `offsetHeight` then restyled all of them before reading one height
  //: (traced: 37 to 63ms, 1,260 elements, on every Tab at 301 topics). A
  //: move changes no size, so the measure now reads only the topics this
  //: pass repainted, with nothing else dirty yet, and the moves are written
  //: after it, to be restyled once with the rest of the frame.
  const movesLater = [];
  const repainted = new Set();
  objectUpdate.each(function (d) {
    //: Before the paint-key skip: another item's order command moves this
    //: one's rank without changing anything this one would repaint.
    //: Kept on the element: this pass and the enter above are the only writers of an object's z-index, and
    //: reading it back off `style` cost 0.6 ms for 500.
    const rank = stackRank.get(`object:${d.id}`) ?? "";
    if (this._wbRank !== rank) {
      this.style.zIndex = String(rank);
      this._wbRank = rank;
    }
    const key = wbObjectPaintKey(d, paintCtx);
    //: **A move is a transform, not a repaint** (audit FEAT-02): the key left
    //: out x and y so a tidy that shifts two hundred topics down for one new
    //: one writes two hundred transforms, not two hundred full repaints
    //: (measured: 409ms of `setAttribute` in one Tab at 301 topics).
    if (this._wbPaintKey === key) {
      const place = wbItemTransform(d);
      if (this.style.transform !== place) movesLater.push([this, place]);
      return;
    }
    repainted.add(this);
    this._wbPaintKey = key;
    //: Drawn live for this pass, so the measure below reads what the new
    //: content really needs rather than the size it was culled at. The next
    //: cull (queued at the end of the render) puts it back if it is still
    //: off screen.
    if (this.classList.contains("wb-culled")) this.classList.remove("wb-culled");
    const el = d3.select(this);
    this.style.transform = wbItemTransform(d);
    this.style.width = `${(WB_MAP_KINDS.has(d.kind) && wbMapNodeSize.narrow(d)) || d.width}px`;
    this.style.height = objectHeight(d);
    if (!WB_MAP_KINDS.has(d.kind)) {
      this.style.opacity = d.data?.alpha != null && d.data.alpha < 1 ? String(d.data.alpha) : "";
      this.style.filter = wbShadowCss(d.data) || "";
      this.style.borderRadius = Array.isArray(d.data?.radii) ? d.data.radii.map((r) => `${r}px`).join(" ") : "";
      if (d.kind === "text") this.style.padding = d.data?.pad != null ? `${d.data.pad}px` : "";
      wbPaintVotes(this, d);
    }
    if (d.kind === "image") {
      const pix = wbPixel(d.data, d.width, d.height);
      const turned = pix.turn === 90 || pix.turn === 270;
      //: The border is an outline drawn inside the box, so the picture keeps its size.
      const edge = d.data.border_width > 0 ? d.data.border_width : 0;
      this.style.outline = edge ? `${edge}px solid ${d.data.border_color && d.data.border_color !== "transparent" ? d.data.border_color : "#333333"}` : "";
      this.style.outlineOffset = edge ? `-${edge}px` : "";
      el.select("img").attr("src", mediaSrc(d.data.url) || "").style("border-radius", d.data.radii ? "inherit" : null)
        .style("clip-path", wbCropClip(d.data.crop, d.data.trim) || null)
        .style("transform", pix.transform || null).style("filter", pix.filter || null)
        .style("position", turned ? "absolute" : null).style("left", turned ? "50%" : null).style("top", turned ? "50%" : null)
        .style("width", turned ? `${pix.w}px` : null).style("height", turned ? `${pix.h}px` : null);
    } else if (WB_MAP_KINDS.has(d.kind)) {
      wbPaintMapNode(el, d, mapIndex, mapColors, mapFills);
      //: The topic an add is about to type in is made editable here, before
      //: the measure below reads, so the read is the one flush (`wbBeginTextEdit`).
      const typing = wbAddGate.renderHold?.editId === d.id ? this.querySelector(".wb-map-text") : null;
      if (typing) {
        //: Selected, the old selection let go, in the same pass and before the
        //: editable attribute (which restyles at once): the `selectWbItem` that
        //: follows then finds the classes already right.
        for (const old of wbApplySelectionHighlight.marked || []) old.classList.remove("wb-selected", "wb-in-group");
        this.classList.add("wb-selected");
        (wbApplySelectionHighlight.marked ??= new Set()).add(this);
        wbBeginTextEdit(typing, undefined, true);
      }
    } else if (d.kind === "frame") {
      const title = this.querySelector(".wb-frame-title");
      if (title && !title.isContentEditable) title.textContent = wbFrameTitle(d);
      wbPaintFrame(this, d);
    } else if (d.kind === "table") {
      wbPaintTable(this, d);
    } else if (d.kind === "diagram") {
      wbPaintDiagram(this, d);
    } else {
      const sticky = wbIsSticky(d);
      el.classed("wb-sticky", sticky);
      el.classed("wb-no-fold", sticky && !wbStickyFolds(d));
      //: The paper's colour is the fold's too (`.wb-sticky::after`); a
      //: sticky's edge is its lift, never a drawn border.
      if (sticky) this.style.setProperty("--wb-paper", d.data.bg || WB_STICKY_PAPERS[0].value);
      else this.style.removeProperty("--wb-paper");
      el.style("background", wbPaperPaint(d.data)).style("border-color", sticky ? "" : d.data.border_color || "");
      const textEl = el.select(".wb-text-content");
      //: **A sticker** (MINDMAP_PLAN.md decision 44): an emoji with no card,
      //: its glyph sized to its box, so resizing it is resizing the emoji.
      const sticker = Boolean(d.data.sticker);
      el.classed("wb-sticker", sticker);
      //: Up and down the box (the Format panel's Vertical row): the
      //: stylesheet centres or bottoms the text from this.
      if (d.data.valign === "middle" || d.data.valign === "bottom") this.dataset.valign = d.data.valign;
      else delete this.dataset.valign;
      //: A card with a fill and no ink of its own takes the ink that reads
      //: on that fill (`wbCoreInkFor`), not the theme's: a dark blue card in
      //: the light theme drew dark text on it (the owner at release, the
      //: README's board shot).
      textEl.style("color", d.data.color || (d.data.bg && wbCoreInkFor(d.data.bg)) || "")
        .style("font-size", sticker ? `${wbStickerSize(d)}px` : d.data.font_size ? `${d.data.font_size}px` : "")
        .style("text-align", d.data.align || "")
        .style("line-height", d.data.line_height || "")
        .style("letter-spacing", d.data.letter_spacing ? `${d.data.letter_spacing}px` : "")
        .style("font-weight", d.data.bold ? "700" : "")
        .style("font-style", d.data.italic ? "italic" : "")
        .style("text-decoration", [d.data.underline && "underline", d.data.strike && "line-through"].filter(Boolean).join(" "))
        .style("font-family", WB_ITEM_FONTS[d.data.font_family] || "");
      wbPaintTextDir(textEl.node(), d.data.text_dir, d.data.text_alpha);
      if (document.activeElement !== textEl.node()) wbPaintTextContent(textEl.node(), d);
    }
    wbFmtState.effects?.paintObject(this, d); // a sticky's flip side and its words' shadow (whiteboard-effects.js)
  });

  objectSelection.exit()
    .each(function (d) {
      //: Folded away, not deleted: kept for the expand that brings it back.
      if (mapHidden?.has(d.id) && WB_MAP_KINDS.has(d.kind)) wbMapNodePool.set(d.id, this);
    })
    .remove();
  //: After the enter has taken back what it wanted: a kept element whose
  //: topic is no longer folded away and was not taken back (deleted, or the
  //: board changed under it) is let go.
  for (const id of wbMapNodePool.keys()) {
    if (!mapHidden?.has(id)) wbMapNodePool.delete(id);
  }

  //: **Every topic measured in one pass, after every write, never between
  //: them** (MINDMAP_PLAN.md §13a). This loop used to be the last two lines
  //: of the `.each` above, one `offsetHeight` read per node interleaved with
  //: that node's own style writes. A style write invalidates layout for the
  //: whole document, so each of those reads flushed a fresh layout of the
  //: entire board: 500 nodes cost 500 full layouts, which is where this
  //: render's superlinearity actually lived (renderWbObjects: 405.6ms of a
  //: 527ms render at 500 topics, against 32.1ms for the painting itself).
  //: Reads on their own flush once and are then free, so the same
  //: information now costs one layout.
  //:
  //: The stored `height` is what the bounds, the alignment guides and the
  //: tidy layout all read, and a map node's real height is whatever its text
  //: needed; the value rides along to the server on the node's next real
  //: save. The size cache is filled from the same reads because
  //: `wbRenderMapEdges` runs next and asks for both ends of every edge: that
  //: is what keeps `wbMapNodeSize` off `document.querySelector` for a board
  //: whose elements this pass is holding already.
  if (mapIndex) {
    if (!wbMapNodeSizeCache) wbMapNodeSizeCache = new Map();
    objectUpdate.each(function (d) {
      if (!WB_MAP_KINDS.has(d.kind)) return;
      //: A topic this pass did not repaint is the size it last measured (a
      //: move is not a resize), and a culled one was not repainted either.
      if (!repainted.has(this) || this.classList.contains("wb-culled")) {
        //: **The height it was last measured at, not the stored one.** A state
        //: fetched from the server hands every topic back the server's
        //: placeholder height (120), while the element on screen is what its
        //: text needs (44 for one line): a topic this pass did not repaint
        //: took the 120 into the cache, and `wbMapNodeSize` then put a pan,
        //: a ring and an edge end 38px off the box (`mapstrip.js` at 1440, 12px
        //: at 390: the "94px" row, 2 x 47). An element measured once keeps its
        //: own number; one never measured and not culled is read now below.
        const known = this._wbMeasuredH;
        if (d.width && (known || (d.height && this.classList.contains("wb-culled")))) {
          wbMapNodeSizeCache.set(d.id, { w: d.width, h: known || d.height });
          if (known) d.height = known;
          return;
        }
        if (this.classList.contains("wb-culled")) return;
      }
      const h = this.offsetHeight;
      if (!h) return;
      wbMapNodeSizeCache.set(d.id, { w: this.offsetWidth, h });
      this._wbMeasuredH = h;
      d.height = h;
    });
  }
  if (wbAddGate.renderHold) wbAddGate.renderHold.moves.push(...movesLater);
  else for (const [el, place] of movesLater) el.style.transform = place;
}

//: Everything `renderWbObjects` reads when it paints one object, as one
//: string (MINDMAP_PLAN.md §13a). Two renders with the same key for an object
//: would write the same pixels, so the second one skips it.
//:
//: **The map fields are the ones that are not on the object.** A topic's
//: colour comes from its branch, its chevron from how many children it has,
//: its badge from how many topics are folded under it, its spine from which
//: side its parent is on, and everything the strip sets comes from the node's
//: data with the map's theme merged underneath: all five change without the
//: row itself changing, so all five are in the key.
//:
//: `height` is deliberately left out for a map node, because a map node's
//: height is its text's: the measure pass at the end of `renderWbObjects`
//: writes what was drawn back onto the datum, so including it would make
//: every node's key differ from its own last render, for ever. The one
//: exception is a topic somebody has resized by hand (`sized`), whose stored
//: height is written back as a `min-height` and therefore is an input.
function wbObjectPaintKey(d, ctx) {
  //: No x or y: a position is applied as a transform without a repaint (the
  //: update pass above). The one paint that reads a topic's own x is the
  //: both-sides spine, added below with its parent's.
  const base = `${d.kind}|${d.z}|${d.width}|${d.rotation ?? ""}|${JSON.stringify(d.data ?? null)}`;
  //: The board's sticky-fold default is read by the paint (`wbStickyFolds`).
  if (!WB_MAP_KINDS.has(d.kind)) return `${base}|${d.height}|${ctx.fold}`;
  const index = ctx.index;
  const children = index?.childrenOf.get(d.id)?.length || 0;
  const buried = d.data?.collapsed && index ? wbMapSubtree(index, d.id).length - 1 : 0;
  //: Only where it is read: `wb-map-node-mirrored` is decided from the
  //: parent's own box on a both-sides map, and on every other layout the
  //: side is the layout's, so a parent moving cannot change a child's spine.
  let parentBox = "";
  //: A branch with its own structure draws its topics by that layout (`_bl`).
  if ((d._bl || ctx.layout) === "tree-both" && index) {
    const parent = index.byId.get(d.parent_id);
    if (parent) parentBox = `${parent.x}:${parent.width ?? ""}:${d.x}`;
  }
  return `${base}|${d.data?.sized ? d.height : ""}|${wbMapLabel(d)}|${ctx.colors?.get(d.id) || ""}` +
    `|${children}|${buried}|${d.parent_id ?? ""}|${parentBox}|${ctx.layout}|${d._bl || ""}|${ctx.theme}` +
    `|${ctx.fills?.get(d.id) ?? ""}|${wbMapLevelOf(d) ?? ""}` +
    //: The tasks under it (MINDMAP_PLAN.md decision 15): a child ticked
    //: changes this topic's "1/2" without changing anything of its own.
    `|${(() => { const t = index ? wbMapTaskTally(index).get(d.id) : null; return t ? `${t.done}/${t.total}` : ""; })()}` +
    //: Its number (decision 17): a sibling added above it renumbers it.
    `|${wbMapNumberOf(index, d.id)}`;
}

//: **Every link sketch on the board, parsed once and filed under both of its
//: ends** (MINDMAP_PLAN.md §13a). Built by whoever is about to ask about more
//: than one item, which is `wbCaptureBulkMoveOrigin`: it is handed the whole
//: branch under a dragged topic, and the alternative is `wbLinkedSketchesFor`
//: walking and re-parsing every sketch on the board once per member.
//:
//: Keyed `kind:id`, the same pair `wbLinkedSketchesFor` matches on. The keys
//: are strings, so a link whose stored id is `"12"` rather than `12` now finds
//: its node where the scan's `===` did not: nothing in this app writes one,
//: since both come from the same rows, and a link that cannot find its end is
//: a line left behind by a drag either way.
//:
//: A sketch with both ends on one item is filed once, which is what the scan's
//: `atSource || atTarget` did.
function wbLinkSketchIndex() {
  const byEnd = new Map();
  for (const sketch of wbState.sketches || []) {
    const parsed = wbParsedLink(sketch);
    if (!parsed) continue;
    const pair = { sketch, parsed };
    const source = `${parsed.sourceKind || "node"}:${parsed.sourceId}`;
    const target = `${parsed.targetKind || "node"}:${parsed.targetId}`;
    for (const end of target === source ? [source] : [source, target]) {
      const list = byEnd.get(end);
      if (list) list.push(pair);
      else byEnd.set(end, [pair]);
    }
  }
  return byEnd;
}

//: **A sketch's JSON parsed once per version of its data** (audit 1028 B17):
//: the link lookups walk every sketch on the board, strokes included, and
//: most of them are not links. Keyed by id and checked against the data
//: string itself, so an edit (a new string) is parsed again and nothing stale
//: is served. Only link records are kept, as the callers only read them; a
//: stroke or a bad blob is remembered as null so it is not parsed again.
const wbLinkParseCache = new Map();

function wbParsedLink(sketch) {
  const hit = wbLinkParseCache.get(sketch.id);
  if (hit && hit.data === sketch.data) return hit.link;
  let link = null;
  try {
    const parsed = JSON.parse(sketch.data);
    if (parsed && typeof parsed.type === "string" && parsed.type.startsWith("link-")) link = parsed;
  } catch {
    link = null;
  }
  wbLinkParseCache.set(sketch.id, { data: sketch.data, link });
  return link;
}

//: The sketches touching `nodeId`, pre-parsed once. `wbUpdateLinkedSketches`
//: used to do this same JSON.parse-and-scan of *every* sketch on the board on
//: every single mousemove frame of a card drag, a board with a few hundred
//: sketches (strokes plus link lines) turns a drag into dozens of full-board
//: parses a second, visible as stutter on a busy board. `dragStart` below
//: builds this list once per drag instead; a card gains or loses a link only
//: between drags, never mid-drag, so it doesn't need to be live.
function wbLinkedSketchesFor(nodeId, kind = "node", index = null) {
  //: **One parse of the board, not one parse per item asking**
  //: (MINDMAP_PLAN.md §13a). Given an index (see `wbLinkSketchIndex`), this
  //: is a lookup. Without one it is the scan below, which is right for the
  //: single item a solo drag picks up and quadratic for a bulk move, which
  //: hands this every topic under the one grabbed: a branch of two hundred
  //: topics over a board of a few hundred link sketches was two hundred full
  //: scans with a `JSON.parse` in each of them, before the pointer had moved.
  if (index) return index.get(`${kind}:${nodeId}`) || [];
  const found = [];
  for (const sketch of wbState.sketches) {
    const parsed = wbParsedLink(sketch);
    if (!parsed) continue;
    const atSource = parsed.sourceId === nodeId && (parsed.sourceKind || "node") === kind;
    const atTarget = parsed.targetId === nodeId && (parsed.targetKind || "node") === kind;
    if (!atSource && !atTarget) continue;
    found.push({ sketch, parsed });
  }
  return found;
}

//: Recomputes just the link-sketch paths touching `nodeId`, without a full
//: `wbScheduleRender()`, reported directly as "resizing and drawing shapes
//: is glitchy and slow to update". `dragging` below used to call the full
//: render on every single mousemove frame of a card drag, purely to keep a
//: link line's endpoint following the card, which re-binds *every* card,
//: sketch and object on the board, dozens of times a second, for one card's
//: own link. Mirrors the link-path maths in `renderWhiteboard`'s own
//: `sketchUpdate.each` exactly, so the two can't drift apart.
//: `precomputed`, when given, skips the board-wide scan, see
//: `wbLinkedSketchesFor`'s own comment for why `dragging` always passes one.
function wbUpdateLinkedSketches(nodeId, precomputed) {
  const pairs = precomputed || wbLinkedSketchesFor(nodeId);
  for (const entry of pairs) {
    const { sketch, parsed } = entry;
    const look = wbMapCrossLinkLook(parsed);
    const endpoints = look ? null : wbResolveLinkEndpoints(parsed);
    if (!look && !endpoints) continue;
    const plainD = look
      ? look.d
      : wbLinkPathD(parsed.type, endpoints.source, endpoints.target, wbLinkCaps(parsed), parsed.width, parsed.bend, wbLinkShape(parsed));
    //: A connector shape follows the drag as its outline (the plain line stays the hit band).
    const shaped = !look && parsed.shape ? wbFmtState.shapeMore?.shapedLink(parsed, endpoints) : null;
    const pathData = shaped ? shaped.d : plainD;
    //: **The two paths, found once per gesture rather than once per frame**
    //: (MINDMAP_PLAN.md §13a). Three document-wide queries per link per frame
    //: is thousands of walks of the document a second on a board that mixes a
    //: branch with a few hundred links, for elements that a render keyed by
    //: id does not replace. `isConnected` is the revalidation, the same shape
    //: `wbBulkMoveElement` already uses: a sketch deleted mid-gesture is gone
    //: from the document and has to be looked for again rather than written
    //: to invisibly for ever.
    if (!entry.el || !entry.el.isConnected) {
      entry.el = document.querySelector(`.sketch-group[data-id="${sketch.id}"]`);
      entry.path = entry.el?.querySelector(".sketch-path") || null;
      entry.hitbox = entry.el?.querySelector(".sketch-hitbox") || null;
    }
    entry.path?.setAttribute("d", pathData);
    entry.hitbox?.setAttribute("d", look ? look.line : shaped ? shaped.centre : pathData);
    //: A connector's label rides on the line (decision 13), looked up once
    //: per gesture like the two paths.
    if (entry.label === undefined || (entry.label && !entry.label.isConnected)) {
      entry.label = entry.el?.querySelector(":scope > .wb-link-label") || null;
    }
    if (entry.label) wbLayoutLinkLabel(entry.el);
    wbFmtState.linkEdge?.follow(sketch.id, wbUpdateLinkedSketches); // the connectors that end on this one
  }
}

function dragStart(event, d) {
  // Eraser/delete don't move cards: a swipe meant to erase a run of cards
  // must not also drag the first one it touches out from under the pointer.
  if (window.currentTool === "eraser" || window.currentTool === "delete" || window.currentTool === "bucket") return;
  if (window.currentTool && window.currentTool.startsWith("link-")) {
    // Real anchors: snap the link's own start to whichever of the source
    // card's 8 fixed points the drag actually began near, so a link from a
    // specific corner stays pinned there through a later resize, `null`
    // (nothing near enough) is the free/floating case, resolved fresh every
    // render in `wbLinkEndpoints` instead of frozen at drag-start.
    const [startX, startY] = d3.pointer(event, document.getElementById("wb-zoom-group"));
    d.linkSourceAnchor = wbNearestAnchor(d._linkKind || "node", d, startX, startY);
    wbLinkDragActive = true;
    wbShowAnchorHints(d._linkKind || "node", d, d.linkSourceAnchor);
    d.linkingPath = document.createElementNS("http://www.w3.org/2000/svg", "path");
    d.linkingPath.setAttribute("fill", "none");
    d.linkingPath.setAttribute("stroke", window.currentStrokeColor || "#ffffff");
    d.linkingPath.setAttribute("stroke-width", "3");
    document.getElementById("wb-zoom-group").appendChild(d.linkingPath);
    //: Escape mid-draw drops the line being drawn and makes nothing.
    d._gesture = wbBeginGesture(() => {
      d.linkingPath?.remove();
      d.linkingPath = null;
      wbLinkDragActive = false;
      wbClearAnchorHints();
      wbMapClearLinkCue();
    });
  } else {
    // `.raise()` deliberately does NOT happen here, see the matching
    // comment in `dragging` below for a real bug this caused.
    // Reported directly: "hard to move notes diagonally when on grid lock".
    // `dragging` below used to re-snap the *already-snapped* `d.x`/`d.y`
    // every frame: each small per-frame delta got rounded straight back to
    // the same grid line it started from, discarding the sub-grid remainder
    // instead of carrying it forward, so many frames of real motion could
    // add up to nothing until one single frame happened to cross a whole
    // grid step by itself. A raw (never-snapped) running position, seeded
    // here and only read through `wbSnap` when applying/saving, fixes it:
    // every pixel of real cursor motion accumulates, and only the *display*
    // rounds to the grid.
    d._rawX = d.x;
    d._rawY = d.y;
    d._dragOriginX = d.x;
    d._dragOriginY = d.y;
    // See wbLinkedSketchesFor's own comment: parsed once here rather than on
    // every frame of the drag that's about to start.
    d._linkedSketches = wbLinkedSketchesFor(d.id);
    d._raised = false;
    // Asked for directly: undo should cover a move, not only create/delete.
    // Snapshotted before anything below can mutate `d`.
    d._moveUndoBefore = WB_KIND_INFO.node.payload(d);
    d._altCopy = Boolean(event.sourceEvent?.altKey);
    d._gesture = wbBeginGesture(() => wbRestoreMove("node", d), true);
    // Bulk-move detection is deliberately deferred to the first real
    // "drag" frame below, not decided here, see the matching comment on
    // the sketch drag's own "start" for the click-toggle bug that caused.
  }
}

function dragging(event, d) {
  if (window.currentTool === "eraser" || window.currentTool === "delete" || window.currentTool === "bucket") return;
  if (d._gesture?.cancelled) return;
  if (window.currentTool && window.currentTool.startsWith("link-")) {
    const [mx, my] = d3.pointer(event, document.getElementById("wb-zoom-group"));

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
    const transform = d3.zoomTransform(document.getElementById("whiteboard-container"));
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

async function dragEndNode(event, d) {
  if (window.currentTool && window.currentTool.startsWith("link-")) {
    const cancelledLink = wbEndGesture(d._gesture);
    delete d._gesture;
    // The in-flight cue goes with the gesture, released or taken back.
    wbMapClearLinkCue();
    if (cancelledLink) {
      d.linkingPath?.remove();
      d.linkingPath = null;
      d.linkSourceAnchor = null;
      return;
    }
    if (d.linkingPath) d.linkingPath.remove();
    d.linkingPath = null;
    wbLinkDragActive = false;
    wbClearAnchorHints();

    const [mx, my] = d3.pointer(event, document.getElementById("wb-zoom-group"));

    const sourceKind = d._linkKind || "node";
    const hit = wbLinkCandidateAt(mx, my, sourceKind, d.id);
    const targetNode = hit ? hit[1] : null;
    const targetKind = hit ? hit[0] : "node";

    if (targetNode && await wbMapJoinByLink(d, targetNode)) {
      // The map took it as a branch: see `wbMapJoinByLink`. No sketch, and
      // the transplant has already tidied, rendered and said what it did.
      d.linkSourceAnchor = null;
      return;
    }
    if (targetNode) {
       // The release point's own nearest anchor on the target, same as the
       // source got at drag-start, `null` (nothing near enough) persists
       // as a free/floating end, same as the source's own case.
       const targetAnchor = wbNearestAnchor(targetKind, targetNode, mx, my);
       const crossLink = wbIsMap() && WB_MAP_KINDS.has(d.kind) && WB_MAP_KINDS.has(targetNode.kind);
       const tool = crossLink ? wbMapCrossLinkType() : window.currentTool;
       const linkBase = {
            type: tool,
            sourceId: d.id,
            targetId: targetNode.id,
            sourceKind: sourceKind === "node" ? undefined : sourceKind,
            targetKind: targetKind === "node" ? undefined : targetKind,
            color: window.currentStrokeColor || "#ffffff",
            sourceAnchor: d.linkSourceAnchor || undefined,
            targetAnchor: targetAnchor || undefined,
            //: A board link wears the held tool's ends; a map's cross-link
            //: keeps the map's own look.
            ...(crossLink ? {} : wbToolCaps()),
       };
       //: A board's default connector style (Set as default style) starts every new link, a map's cross-link too.
       const sketchData = {
         data: JSON.stringify(wbFmtState.board?.withDefaults("link", linkBase) ?? linkBase),
         x: 0, y: 0, z: wbStackNewZ("sketch"),
         board_id: window.currentBoardId
       };
       try {
         const res = await apiJson("/whiteboard/sketches", { method: "POST", body: JSON.stringify(sketchData) });
         wbState.sketches.push(res);
         wbPushUndo({ action: "create", kind: "sketch", id: res.id });
         //: **A cross-link has to be *told* it is one, before it is drawn**
         //: (MINDMAP_PLAN §13c). What marks a link sketch as a cross-link is
         //: the board tree's `cross_links`, which is fetched with the map's
         //: state, so a link drawn now and rendered now carried none of the
         //: map's treatment: it was drawn as an ordinary board connector, in
         //: the pen's colour and solid, until the board was next opened. That
         //: is the most literal possible form of "there are two types of
         //: connections" and the reason this refresh is awaited before the
         //: render rather than left to the next reload.
         if (wbIsMap()) await wbRefreshMapState();
         wbScheduleRender();
         //: **Say which of the two it made** (MINDMAP_PLAN §13c). One gesture
         //: produces either kind, decided by whether the far end is already in
         //: the tree (`wbMapJoinByLink`), and §13.2's finding was that nothing
         //: on screen says which is about to happen. The branch half has said
         //: so since it was built ("Connected to ... as a branch"); this is
         //: the other half, in the same words the ring and the rail now use.
         if (wbIsMap() && wbMapCrossLinkInfo(res.id)) {
           toast("Cross-link made: it joins two branches without changing the tree.");
         }
       } catch (err) {
         toast(voiceLine("failed", { what: "connect those", why: err.message }), true);
       }
    }
    d.linkSourceAnchor = null;
  } else {
    //: Dropped on the delete target: put back, then deleted (INBOX 660).
    wbTrashTake(d._gesture, "node", d);
    wbClearAlignmentGuides();
    // Sync back to API.
    //
    // `board_id` has to go with it. The server takes the whole node on a PUT,
    // so omitting it read as "move this to the global board", dragging a card
    // on a named board silently moved it off that board.
    //
    // And a 404 here is recoverable rather than fatal: it means this client's
    // copy of the board is stale (the note was purged, or the board was
    // rebuilt). Refetching puts the screen back in step; leaving it, as this
    // did, shows a card sitting where you dropped it that is not saved
    // anywhere: the worst of both answers.
    const moveBefore = d._moveUndoBefore;
    delete d._moveUndoBefore;
    // Reset unconditionally, even when this gesture wasn't a bulk move,
    // see the matching comment in objDrag's own "end" for why leaving a
    // solo drag's `null` in place would break bulk-move detection later.
    const bulkOrigin = d._bulkOrigin;
    delete d._bulkOrigin;
    const altCopy = d._altCopy;
    delete d._altCopy;
    const cancelled = wbEndGesture(d._gesture);
    delete d._gesture;
    if (cancelled) return;
    //: A click is not a drop (see objDrag's own "end"): only a card that
    //: really moved is saved.
    const moved = moveBefore && (moveBefore.x !== d.x || moveBefore.y !== d.y);
    if (moved || !moveBefore) await wbSaveNode(d);
    if (d._unsaved) {
      //: Not saved: back where it was taken from (see objDragEnd's twin).
      delete d._unsaved;
      if (moveBefore) Object.assign(d, { x: moveBefore.x, y: moveBefore.y });
      wbScheduleRender();
      toast(voiceLine("failed", { what: "save the move", why: "the item went back where it was" }), true, { action: ["Reload the board", () => fetchWhiteboardState().then(wbScheduleRender)] });
      return;
    }
    //: The whole drag is one undo step now, carried members and Alt copies
    //: included (`wbFinishDrag`); this used to undo only the card grabbed.
    await wbFinishDrag(moved ? { action: "move", kind: "node", id: d.id, before: moveBefore } : null, bulkOrigin, altCopy);
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
  //: A board restored with the page gets here while the boards bundle is still loading; the
  //: Library side (`wbSideState`, the tiles) is later in it (INBOX 1530 f).
  await ensureModule("boards");
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
    ? document.querySelector(`.node-card[data-id="${wbSelectedItem.id}"]`)
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
  const plain = window[name];
  //: `Object.assign` carries a gesture's helper properties (`wbMapFoldToLevel.open`, `.sync`) across.
  if (typeof plain === "function") window[name] = Object.assign((...args) => wbRecordGesture(plain, args), plain);
}
{
  const plain = window.wbMapTransplant;
  window.wbMapTransplant = async (...args) => {
    wbRecordDepth += 1;
    try {
      return await plain(...args);
    } finally {
      wbRecordDepth -= 1;
    }
  };
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
