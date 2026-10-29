// panel-movable.js: every popup panel can be dragged by its head and resized
// from its bottom-right corner (INBOX 1427, the owner: "can you make all popup
// panels draggable??" then "and resizable?"). DESIGN.md recipe `panelMovable`.
// Lazy (`LAZY_MODULES.panelMovable`, preloaded three seconds after boot).

//: **Hooked centrally, opt-in by the head.** A panel is any element that holds
//: a `.dialog-head` (the head recipe every dialog, sheet and popup already
//: carries) as a direct child and sits inside a `dialog` or `[role="dialog"]`.
//: Delegated listeners (`focusin`, `pointerover` on a head, `pointerdown` on a
//: head or the grip) adopt it the first time it is touched; there is no
//: observer, no frame loop and nothing per panel. A panel that must stay put
//: says `data-panel-fixed` (the lint in tests/test_ui_recipes.py lists them).
//:
//: **Cheap while it moves.** The head's `pointerdown` reads the panel's rect
//: once; every `pointermove` after that is arithmetic and one write of the
//: `translate` property (it composes with a panel's own `transform` and its
//: opening animation, which `transform` would fight). The size is written with
//: the CSSOM, never a style attribute (the CSP). A centred panel moves its
//: left edge by half of any width change, a right-anchored one by all of it, so
//: the first 8px of a resize read the rect once to learn which, and the corner
//: stays under the pointer after that without another read.
//:
//: **Where it lives.** Position and size are kept per panel id in one
//: localStorage entry (try/catch: it can be missing), restored when the panel
//: is first touched after it opens, clamped to the window on open and on
//: window resize so the head never leaves the screen. A double-click on the
//: head forgets both. Only on a fine pointer at 600px or wider: below that a
//: panel is a sheet and stays one. A focusable grip (the last control in the
//: panel) is the keyboard route (WCAG 2.5.7): arrows move 16px, Shift and
//: arrows resize 16px, Home resets.
const PANEL_KEY = "tessellate.panels";
const PANEL_STEP = 16;
const PANEL_KEEP = 64;
const PANEL_MIN_W = 280;
const PANEL_MIN_H = 160;
const PANEL_MEDIA = "(min-width: 600px) and (pointer: fine)";
const PANEL_SKIP = "button, a, input, select, textarea, summary, [contenteditable], .panel-grip";
const PANEL_STATE = new WeakMap();

//: Pure maths, kept apart so tests/test_panel_movable.py can run it in node.
function panelClampMove(rect, ox, oy, nx, ny, vw, vh, headH) {
  const dx = nx - ox;
  const dy = ny - oy;
  const keep = Math.min(PANEL_KEEP, rect.width);
  const left = Math.min(Math.max(rect.left + dx, keep - rect.width), vw - keep);
  const top = Math.min(Math.max(rect.top + dy, 0), Math.max(0, vh - headH));
  return { x: ox + (left - rect.left), y: oy + (top - rect.top) };
}
function panelClampSize(rect, w, h, vw, vh) {
  const minW = Math.min(PANEL_MIN_W, rect.width);
  const minH = Math.min(PANEL_MIN_H, rect.height);
  const maxW = Math.max(minW, vw - Math.max(0, rect.left));
  const maxH = Math.max(minH, vh - Math.max(0, rect.top));
  return { w: Math.round(Math.min(Math.max(w, minW), maxW)), h: Math.round(Math.min(Math.max(h, minH), maxH)) };
}
function panelKeyDelta(key, shift) {
  const d = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] }[key];
  if (!d) return null;
  const s = d.map((n) => n * PANEL_STEP);
  return shift ? { dx: 0, dy: 0, dw: s[0], dh: s[1] } : { dx: s[0], dy: s[1], dw: 0, dh: 0 };
}
function panelStoreParse(raw) {
  try {
    const v = JSON.parse(raw || "{}");
    return v && typeof v === "object" && !Array.isArray(v) ? v : {};
  } catch (_) {
    return {};
  }
}
function panelStoreRead(id) {
  const e = panelStoreParse(prefs.get(PANEL_KEY, ""))[id];
  if (!Array.isArray(e) || e.length !== 4) return null;
  const [x, y, w, h] = e;
  if (![x, y].every(Number.isFinite) || (w !== null && !Number.isFinite(w)) || (h !== null && !Number.isFinite(h))) return null;
  return { x, y, w, h };
}
function panelStoreWrite(id, st) {
  //: prefs swallows a private window or blocked storage: the panel still works.
  const all = panelStoreParse(prefs.get(PANEL_KEY, ""));
  if (st) all[id] = [Math.round(st.x), Math.round(st.y), st.w, st.h];
  else delete all[id];
  prefs.setJSON(PANEL_KEY, all);
}

function panelMovableOn() {
  return window.matchMedia(PANEL_MEDIA).matches;
}
//: The nearest ancestor-or-self that holds a head and sits in a dialog.
function panelOf(node) {
  if (!(node instanceof Element) || !node.closest('dialog, [role="dialog"]')) return null;
  for (let el = node; el; el = el.parentElement) {
    if (el.querySelector(":scope > .dialog-head")) return el.closest("[data-panel-fixed]") ? null : el;
  }
  return null;
}
function panelId(panel) {
  const host = panel.closest('dialog, [role="dialog"]');
  const own = panel.id || (host && (host.id || host.dataset.sheet));
  if (own) return own;
  const title = panel.querySelector(":scope > .dialog-head .dialog-head-title");
  return title ? "title-" + title.textContent.trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").slice(0, 40) : "";
}
function panelSt(panel) {
  let st = PANEL_STATE.get(panel);
  if (!st) {
    st = { x: 0, y: 0, w: null, h: null, id: panelId(panel), grip: null, skip: false };
    PANEL_STATE.set(panel, st);
  }
  return st;
}
function panelApply(panel, st) {
  panel.style.translate = st.x || st.y ? `${st.x}px ${st.y}px` : "";
  if (st.w === null) {
    panel.style.width = panel.style.maxWidth = "";
  } else {
    panel.style.width = `${st.w}px`;
    panel.style.maxWidth = "none";
  }
  if (st.h === null) {
    panel.style.height = panel.style.maxHeight = "";
  } else {
    panel.style.height = `${st.h}px`;
    panel.style.maxHeight = "none";
  }
}
function panelHeadOf(panel) {
  return panel.querySelector(":scope > .dialog-head");
}
//: Keeps a panel inside the window: size first, then place.
function panelClamp(panel, st) {
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const head = panelHeadOf(panel);
  const headH = head ? head.offsetHeight : 40;
  const place = () => {
    const r = panel.getBoundingClientRect();
    //: Whole panel inside the window when it fits (a drag may park it half
    //: off, a window resize or a reload brings it back), else its head.
    const left = Math.min(Math.max(r.left, 0), Math.max(0, vw - r.width));
    const top = Math.min(Math.max(r.top, 0), Math.max(0, vh - Math.max(r.height, headH)));
    const m = panelClampMove(r, st.x, st.y, st.x + left - r.left, st.y + top - r.top, vw, vh, headH);
    if (m.x === st.x && m.y === st.y) return;
    st.x = m.x;
    st.y = m.y;
    panelApply(panel, st);
  };
  //: Place, then size against the new place, then place again: a panel left
  //: off to one side must come back before its room is measured.
  place();
  if (st.w !== null || st.h !== null) {
    const r = panel.getBoundingClientRect();
    const c = panelClampSize(r, st.w ?? r.width, st.h ?? r.height, vw, vh);
    if (st.w !== null) st.w = c.w;
    if (st.h !== null) st.h = c.h;
    panelApply(panel, st);
    place();
  }
}
function panelFull(panel) {
  const r = panel.getBoundingClientRect();
  return r.width >= window.innerWidth - 2 && r.height >= window.innerHeight - 2;
}
function panelReset(panel) {
  const st = panelSt(panel);
  st.x = st.y = 0;
  st.w = st.h = null;
  panelApply(panel, st);
  if (st.id) panelStoreWrite(st.id, null);
}
function panelSave(panel) {
  const st = panelSt(panel);
  if (st.id) panelStoreWrite(st.id, st);
}
//: Adopt a panel once: restore, add the grip. Cheap to call again.
function panelAdopt(panel) {
  if (!panel || !panelMovableOn()) return;
  const st = panelSt(panel);
  if (st.skip) return;
  if (!panel.classList.contains("panel-movable-on")) {
    if (panelFull(panel)) { st.skip = true; return; }
    panel.classList.add("panel-movable-on");
    const saved = st.id ? panelStoreRead(st.id) : null;
    if (saved) {
      Object.assign(st, saved);
      panelApply(panel, st);
      panelClamp(panel, st);
    }
  }
  if (!st.grip || !st.grip.isConnected || st.grip.parentElement !== panel) {
    const grip = document.createElement("button");
    grip.type = "button";
    grip.className = "panel-grip";
    grip.setAttribute("aria-label", "Move or resize this panel");
    grip.title = "Drag to resize. Arrow keys move, Shift and arrow keys resize, Home resets.";
    panel.appendChild(grip);
    st.grip = grip;
  }
}
function panelHeadDown(e) {
  const head = e.target.closest(".dialog-head");
  const panel = head && panelOf(head);
  if (!panel || e.button !== 0 || e.target.closest(PANEL_SKIP) || !panelMovableOn()) return;
  panelAdopt(panel);
  const st = panelSt(panel);
  if (st.skip) return;
  const rect = panel.getBoundingClientRect();
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const hh = head.offsetHeight;
  const x0 = e.clientX;
  const y0 = e.clientY;
  const ox = st.x;
  const oy = st.y;
  panel.classList.add("panel-moving");
  head.setPointerCapture(e.pointerId);
  const move = (ev) => {
    const m = panelClampMove(rect, ox, oy, ox + ev.clientX - x0, oy + ev.clientY - y0, vw, vh, hh);
    st.x = m.x;
    st.y = m.y;
    panel.style.translate = `${m.x}px ${m.y}px`;
  };
  const done = () => {
    head.removeEventListener("pointermove", move);
    head.removeEventListener("pointerup", done);
    head.removeEventListener("pointercancel", done);
    panel.classList.remove("panel-moving");
    panelSave(panel);
  };
  head.addEventListener("pointermove", move);
  head.addEventListener("pointerup", done);
  head.addEventListener("pointercancel", done);
}
//: Resize with the left and top edges held where they were.
function panelGripDown(e) {
  const grip = e.target.closest(".panel-grip");
  const panel = grip && grip.parentElement;
  if (!panel || e.button !== 0 || !panelMovableOn()) return;
  e.preventDefault();
  const st = panelSt(panel);
  const rect = panel.getBoundingClientRect();
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const x0 = e.clientX;
  const y0 = e.clientY;
  const ox = st.x;
  const oy = st.y;
  const k = { x: null, y: null };
  grip.setPointerCapture(e.pointerId);
  panel.classList.add("panel-moving");
  const move = (ev) => {
    const dw = ev.clientX - x0;
    const dh = ev.clientY - y0;
    const c = panelClampSize(rect, rect.width + dw, rect.height + dh, vw, vh);
    st.w = c.w;
    st.h = c.h;
    panel.style.width = `${c.w}px`;
    panel.style.height = `${c.h}px`;
    panel.style.maxWidth = panel.style.maxHeight = "none";
    //: One read per axis, once the size has moved enough to tell.
    const sw = c.w - rect.width;
    const sh = c.h - rect.height;
    if (k.x === null && Math.abs(sw) >= 8) {
      k.x = Math.round(((panel.getBoundingClientRect().left - rect.left) / sw) * 2) / 2;
    }
    if (k.y === null && Math.abs(sh) >= 8) {
      k.y = Math.round(((panel.getBoundingClientRect().top - rect.top) / sh) * 2) / 2;
    }
    st.x = ox - (k.x || 0) * sw;
    st.y = oy - (k.y || 0) * sh;
    panel.style.translate = `${st.x}px ${st.y}px`;
  };
  const done = () => {
    grip.removeEventListener("pointermove", move);
    grip.removeEventListener("pointerup", done);
    grip.removeEventListener("pointercancel", done);
    panel.classList.remove("panel-moving");
    panelSave(panel);
  };
  grip.addEventListener("pointermove", move);
  grip.addEventListener("pointerup", done);
  grip.addEventListener("pointercancel", done);
}
function panelGripKey(e) {
  const grip = e.target.closest(".panel-grip");
  const panel = grip && grip.parentElement;
  if (!panel) return;
  const st = panelSt(panel);
  if (e.key === "Home") {
    e.preventDefault();
    e.stopPropagation();
    panelReset(panel);
    return;
  }
  const d = panelKeyDelta(e.key, e.shiftKey);
  if (!d) return;
  e.preventDefault();
  e.stopPropagation();
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const before = panel.getBoundingClientRect();
  if (d.dw || d.dh) {
    const c = panelClampSize(before, before.width + d.dw, before.height + d.dh, vw, vh);
    st.w = c.w;
    st.h = c.h;
    panelApply(panel, st);
    const after = panel.getBoundingClientRect();
    st.x += before.left - after.left;
    st.y += before.top - after.top;
  } else {
    const head = panelHeadOf(panel);
    const m = panelClampMove(before, st.x, st.y, st.x + d.dx, st.y + d.dy, vw, vh, head ? head.offsetHeight : 40);
    st.x = m.x;
    st.y = m.y;
  }
  panelApply(panel, st);
  panelSave(panel);
}
let panelResizeTimer = 0;
function panelWindowResized() {
  clearTimeout(panelResizeTimer);
  panelResizeTimer = setTimeout(() => {
    const on = panelMovableOn();
    document.querySelectorAll(".panel-movable-on").forEach((panel) => {
      const st = panelSt(panel);
      if (!on) {
        st.x = st.y = 0;
        st.w = st.h = null;
        panelApply(panel, st);
      } else if (panel.getClientRects().length) {
        panelClamp(panel, st);
      }
    });
  }, 120);
}
if (typeof document !== "undefined" && document.addEventListener) {
  document.addEventListener("focusin", (e) => { const p = panelOf(e.target); if (p) panelAdopt(p); }, true);
  document.addEventListener("pointerover", (e) => {
    const t = e.target;
    if (t instanceof Element && t.closest(".dialog-head")) { const p = panelOf(t); if (p) panelAdopt(p); }
  }, true);
  document.addEventListener("pointerdown", (e) => {
    if (!(e.target instanceof Element)) return;
    if (e.target.closest(".panel-grip")) panelGripDown(e);
    else if (e.target.closest(".dialog-head")) panelHeadDown(e);
  }, true);
  document.addEventListener("dblclick", (e) => {
    if (!(e.target instanceof Element) || e.target.closest(PANEL_SKIP)) return;
    const head = e.target.closest(".dialog-head");
    const panel = head && panelOf(head);
    if (panel && panel.classList.contains("panel-movable-on")) panelReset(panel);
  }, true);
  document.addEventListener("keydown", (e) => {
    if (e.target instanceof Element && e.target.closest(".panel-grip")) panelGripKey(e);
  }, true);
  window.addEventListener("resize", panelWindowResized);
}
