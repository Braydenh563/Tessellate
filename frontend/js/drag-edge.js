// drag-edge.js: a drag-selection near the edge of a list scrolls it, moved out
// of selection.js on 2026-10-05 for the boot-script gzip budget
// (tests/test_boot_budget.py). Only a held mouse drag reaches it, so the boot
// carries nothing but its `LAZY_MODULES.dragEdge` row (app.js), fetched a few
// seconds after boot with the other late bundles; this file's top level wires
// the three listeners itself (phone-shell.js used to call
// `initDragSelectEdgeScroll`).

//: **A drag-selection near the top or bottom of a list scrolls it** (INBOX
//: 608, the owner: "when I drag select off the screen ... it doesnt scroll
//: down or up or the way I am dragging"; the boards and maps pan, see
//: `wbEdgePan` in whiteboard.js, which is tied to the board's zoom and cannot
//: be reused here, so this is the same shape for a plain scroller).
//:
//: Chromium already scrolls a text selection in the last ~20px of a scroller
//: and past it (measured: 700 to 1,100px a second at the edge, 0 from 25px
//: in), so a held drag 40px from the edge, where a hand naturally rests when
//: it is not aiming at the very pixel, did nothing. This takes over from 20px
//: out to 56px and leaves the rest to the browser, so the two never add up.
//: Faster the deeper in (linear, 1px a frame at 56px to 12 at 20px, about
//: the browser's own pace there), and the selection is extended to whatever
//: is now under the pointer, because content that scrolls under a
//: still mouse sends no `mousemove`.
//:
//: Opt-in by zone, not for every scroller: a code editor, a canvas and a
//: textarea each scroll themselves. Mouse only: a touch selection scrolls by
//: its own handles.
//: **It also brings the object-move scripts** (obj-ref.js, INBOX 1467: drag to
//: reorder, copy and paste an object, the drag ghost, the tray). They are the
//: same kind of late pointer code, and a row of their own in `LAZY_MODULES`
//: would not fit the boot script's gzip cap; this file is already preloaded.
["/css/objmove-lazy.css", "/js/obj-ref.js"].forEach(lazyScript);

const DRAG_EDGE = { x: 0, y: 0, el: null, frame: 0 };
function dragEdgeTick() {
  const d = DRAG_EDGE;
  const sel = window.getSelection();
  d.frame = 0;
  if (!d.el?.isConnected || sel.isCollapsed || !d.el.contains(sel.anchorNode)) return;
  //: 1 to 12px a frame between 56px and 20px from an edge, the browser's own below.
  const pace = (dist) => (dist > 20 && dist < 56 ? Math.round(1 + (11 * (56 - dist)) / 36) : 0);
  const box = d.el.getBoundingClientRect();
  const step = pace(box.bottom - d.y) || -pace(d.y - box.top);
  const was = d.el.scrollTop;
  d.el.scrollTop = was + step;
  const at = d.el.scrollTop !== was && document.caretPositionFromPoint?.(d.x, d.y);
  if (at && d.el.contains(at.offsetNode)) sel.extend(at.offsetNode, at.offset);
  d.frame = requestAnimationFrame(dragEdgeTick);
}
//: The list a press at `target` would scroll, or null outside the zones.
function dragEdgeZone(target) {
  let el = target?.closest?.("#entry-list, .library-view-section");
  while (el && el !== document.documentElement && !(/auto|scroll/.test(getComputedStyle(el).overflowY) && el.scrollHeight > el.clientHeight)) el = el.parentElement;
  return el || null;
}
function initDragSelectEdgeScroll() {
  const d = DRAG_EDGE;
  document.addEventListener("mousedown", (e) => {
    d.el = e.button === 0 ? dragEdgeZone(e.target) : null;
  }, true);
  //: **A drag already under way when this file arrives** (selection.js's
  //: `EDGE_SCROLL_HELD`): the press that fetched it, picked up here so the very
  //: first drag after boot scrolls too. Before, a drag begun in the first
  //: seconds (before the preload) or on a slow disk did nothing at the edge
  //: (qa-1005, `search1005-lazy.js` FIRST=1: 0px, then 432px).
  EDGE_SCROLL_HELD.ready = true;
  const held = EDGE_SCROLL_HELD.press;
  if (held) {
    Object.assign(d, { el: dragEdgeZone(held.target), x: held.x, y: held.y });
    if (d.el) d.frame = requestAnimationFrame(dragEdgeTick);
  }
  document.addEventListener("mousemove", (e) => {
    if (!d.el || !(e.buttons & 1)) return;
    d.x = e.clientX;
    d.y = e.clientY;
    d.frame ||= requestAnimationFrame(dragEdgeTick);
  }, true);
  document.addEventListener("mouseup", () => {
    d.el = null;
    cancelAnimationFrame(d.frame);
    d.frame = 0;
  }, true);
}

//: **The lag log rides this bundle** (lag-watch.js): app.js is at its gzip
//: ratchet (tests/test_static_compression.py), and this file is fetched with
//: the late bundles three seconds after boot, which is when the watcher
//: should start; its observers are buffered, so boot's own stalls still count.
lazyScript("/js/lag-watch.js");
//: Movable panels (INBOX 1427) ride along with this late bundle (row in lazy-entries.js).
ensureModule("panelMovable");
initDragSelectEdgeScroll();
