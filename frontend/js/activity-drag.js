// activity-drag.js: move the Activity panel by its header (L-chat-13). Lazy
// (LAZY_MODULES.activityDrag): agent-activity.js loads it the first time the
// panel is shown, so the boot bundle pays one line for it.
//
// The panel sits fixed at the bottom left and covers whatever is there, so the
// reader can drag it by the header to somewhere else. Three rules:
//  - It stays inside the window: the saved spot is clamped on every drag, on
//    every resize and on load, so a smaller window never strands it off screen.
//  - The spot is kept in this browser's saved settings (`activityMonitorPos`, via prefs) and comes back on
//    the next visit; a double-click on the header clears it and puts the panel
//    home.
//  - On a phone the panel is a full-width sheet (CSS, under 600px), so there is
//    nothing to move and the saved spot is left alone.
(() => {
  const KEY = "activityMonitorPos";
  const panel = $("agent-monitor");
  const head = panel?.querySelector(".monitor-header");
  if (!panel || !head || panel.dataset.dragReady) return;
  panel.dataset.dragReady = "1";

  const sheet = () => window.matchMedia("(max-width: 599.98px)").matches;

  //: The nearest spot that keeps the whole panel on screen.
  function clampPos(pos, size, view) {
    const fit = (value, room) => Math.round(Math.min(Math.max(0, value), Math.max(0, room)));
    return { x: fit(pos.x, view.w - size.w), y: fit(pos.y, view.h - size.h) };
  }

  function saved() {
    const pos = prefs.json(KEY, {});
    return Number.isFinite(pos.x) && Number.isFinite(pos.y) ? pos : null;
  }

  function place(pos) {
    const box = panel.getBoundingClientRect();
    const at = pos && !sheet() ? clampPos(pos, { w: box.width, h: box.height }, { w: window.innerWidth, h: window.innerHeight }) : null;
    panel.style.left = at ? `${at.x}px` : "";
    panel.style.top = at ? `${at.y}px` : "";
    panel.style.bottom = at ? "auto" : "";
    return at;
  }

  function reset() {
    prefs.remove(KEY);
    place(null);
  }

  let grab = null;
  head.addEventListener("pointerdown", (event) => {
    if (event.button || sheet() || event.target.closest("button, a, input, .menu-wrap")) return;
    const box = panel.getBoundingClientRect();
    grab = { dx: event.clientX - box.left, dy: event.clientY - box.top };
    head.setPointerCapture?.(event.pointerId);
    panel.classList.add("is-dragging");
  });
  head.addEventListener("pointermove", (event) => {
    if (grab) place({ x: event.clientX - grab.dx, y: event.clientY - grab.dy });
  });
  const drop = () => {
    if (!grab) return;
    grab = null;
    panel.classList.remove("is-dragging");
    const box = panel.getBoundingClientRect();
    prefs.setJSON(KEY, { x: Math.round(box.left), y: Math.round(box.top) });
  };
  head.addEventListener("pointerup", drop);
  head.addEventListener("pointercancel", drop);
  head.addEventListener("dblclick", (event) => {
    if (!event.target.closest("button, a, input, .menu-wrap")) reset();
  });
  window.addEventListener("resize", () => place(saved()));

  place(saved());
})();
