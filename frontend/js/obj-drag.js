// obj-drag.js: the one pointer gesture for moving an object (INBOX 1467,
// parts 2 and 4). Lazy, loaded by obj-ref.js. A press on a card arms it; the
// gesture goes live only after the pointer has moved 5px and been held 150ms,
// so a click, a double click, a scroll flick and a text selection are
// untouched. While live a small ghost card follows the pointer and the
// current mode (`OBJ_MODES`: obj-reorder.js's `reorder`, obj-carry.js's
// `carry`) decides what the pointer is over, and may hand the gesture to another
// mode (`route`). Escape or a press of another
// button ends it with no change. Mouse and pen only: a finger on a card is
// a scroll, and a long-press drag for touch is left for a device that can
// check it.

const OBJ_DRAG_PX = 5;
const OBJ_DRAG_MS = 150;
//: Where a press never starts a drag: the card's own controls.
const OBJ_NO_GRAB = "input, select, textarea, [contenteditable='true'], button, a[href], summary, [draggable='true'], .chip-interactive, .menu-wrap, label";
const OBJ_ICON = { note: "ph-note", document: "ph-file-text", board: "ph-squares-four", map: "ph-tree-structure", image: "ph-image", file: "ph-file" };

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

//: Whether a press may arm a drag, and from which card: `{ card, ref }`.
//: The modes' `grab(hit)` may add to it (the reorder mode's surface).
function objDragSeed(event) {
  if (event.button !== 0 || event.pointerType === "touch" || event.defaultPrevented) return null;
  const control = event.target.closest?.(OBJ_NO_GRAB);
  //: A tray item is a button you click to paste and also drag out.
  if (control && !control.matches(".obj-tray-use")) return null;
  const hit = objCardAt(event.target);
  if (!hit) return null;
  const mode = Object.keys(OBJ_MODES).find((name) => OBJ_MODES[name].grab?.(hit));
  return mode ? { ...hit, mode, ...OBJ_MODES[mode].grab(hit) } : null;
}

function objDragArm(event) {
  const seed = objDragNow ? null : objDragSeed(event);
  if (!seed) return;
  objDragNow = { ...seed, id: event.pointerId, x0: event.clientX, y0: event.clientY, x: event.clientX, y: event.clientY, t0: event.timeStamp, live: false };
  objDragListen(true);
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
}

function objDragNoNative(event) {
  event.preventDefault();
}

//: Past the distance too early is a swipe or a selection, not a hold: the
//: press is let go of. Held long enough and then moved is the drag.
function objDragVerdict(g, event) {
  const far = Math.hypot(event.clientX - g.x0, event.clientY - g.y0) >= OBJ_DRAG_PX;
  if (!far) return "wait";
  return event.timeStamp - g.t0 >= OBJ_DRAG_MS ? "start" : "swipe";
}

function objDragMove(event) {
  const g = objDragNow;
  if (!g || event.pointerId !== g.id) return;
  g.x = event.clientX;
  g.y = event.clientY;
  if (!g.live) {
    const verdict = objDragVerdict(g, event);
    if (verdict === "swipe") return objDragFinish(true, event);
    if (verdict === "wait") return;
    objDragBegin(g);
  }
  objDragFrame(g);
}

function objDragBegin(g) {
  g.live = true;
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
//: the hand is still).
function objDragTick(g) {
  if (objDragNow !== g) return;
  const box = g.scroller?.getBoundingClientRect();
  const near = box ? Math.max(0, 48 - (g.y - box.top), g.y - (box.bottom - 48)) : 0;
  if (near > 0) {
    g.scroller.scrollTop += (g.y < (box.top + box.bottom) / 2 ? -1 : 1) * Math.ceil(near / 6);
    OBJ_MODES[g.mode].update(g);
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

function objDragFinish(cancel, event) {
  const g = objDragNow;
  objDragNow = null;
  objDragListen(false);
  if (!g?.live) return;
  cancelAnimationFrame(g.tick);
  OBJ_MODES[g.mode][cancel ? "cancel" : "drop"](g, event);
  g.ghost.remove();
  document.removeEventListener("selectstart", objDragNoNative, true);
  document.documentElement.classList.remove("obj-dragging");
  objDragSwallowClick();
}

window.addEventListener("pointerdown", objDragArm, true);
