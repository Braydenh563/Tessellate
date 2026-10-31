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
//: Docking, the reset button and Settings' "Panels open where you left them"
//: (INBOX 1434): DESIGN.md `panelMovable`.
const PANEL_KEY = "tessellate.panels";
const PANEL_STEP = 16;
const PANEL_MIN_W = 280;
const PANEL_MIN_H = 160;
const PANEL_MEDIA = "(min-width: 600px) and (pointer: fine)";
const PANEL_SKIP = "button, a, input, select, textarea, summary, [contenteditable], .panel-grip";
const PANEL_STATE = new WeakMap();
//: INBOX 1472: a band from the very edge (0px, and past it when the pointer is
//: captured outside the window) in to 48px. It was 24 with `x >= vw - 24`, which
//: the last pixel column (`vw - 1`) made 23 on the right and bottom.
const PANEL_EDGE = 48;
const PANEL_ZONES = ["left", "right", "max", "bottom", "tl", "tr", "bl", "br"];
//: INBOX 1474 (split screen): the narrowest the app may be squeezed to.
const PANEL_PUSH_MIN = 640;

//: Pure maths, kept apart so tests/test_panel_movable.py can run it in node.
//: **A panel stays inside the free area** (INBOX 1474, the owner: "I can drag
//: the attach panel behind the sidebar"): `safe` is the window minus the
//: sidebar, the status bar and any panel docked to a side (`panelSafe`), and
//: the whole panel stays in it when it fits, else its top left does.
function panelClampMove(rect, ox, oy, nx, ny, vw, vh, headH, safe) {
  const b = safe || { left: 0, top: 0, right: vw, bottom: vh };
  const left = Math.min(Math.max(rect.left + nx - ox, b.left), Math.max(b.left, b.right - rect.width));
  const top = Math.min(Math.max(rect.top + ny - oy, 0), Math.max(0, b.bottom - Math.max(rect.height, headH)));
  return { x: ox + (left - rect.left), y: oy + (top - rect.top) };
}
function panelClampSize(rect, w, h, vw, vh) {
  const minW = Math.min(PANEL_MIN_W, rect.width);
  const minH = Math.min(PANEL_MIN_H, rect.height);
  const maxW = Math.max(minW, vw - Math.max(0, rect.left));
  const maxH = Math.max(minH, vh - Math.max(0, rect.top));
  return { w: Math.round(Math.min(Math.max(w, minW), maxW)), h: Math.round(Math.min(Math.max(h, minH), maxH)) };
}
//: Which zone the pointer is in, "" for none; edges within PANEL_EDGE, corners
//: when two meet.
function panelSnapZone(x, y, vw, vh) {
  const l = x <= PANEL_EDGE;
  const r = x >= vw - 1 - PANEL_EDGE;
  const t = y <= PANEL_EDGE;
  const b = y >= vh - 1 - PANEL_EDGE;
  //: The top band is read by thirds so one gesture always gives one height:
  //: the middle third maximises, the outer thirds are the top quarters.
  if (t) return x < vw / 3 ? "tl" : x > (2 * vw) / 3 ? "tr" : "max";
  if (b) return l ? "bl" : r ? "br" : "bottom";
  return l ? "left" : r ? "right" : "";
}
//: `safe` ({left, top, right, bottom}) keeps zones off the app's own bars.
function panelZoneRect(zone, vw, vh, inset, safe) {
  if (!PANEL_ZONES.includes(zone)) return null;
  const sx = safe ? safe.left : 0;
  const sy = safe ? safe.top : 0;
  const sr = safe ? safe.right : vw;
  const sb = safe ? safe.bottom : vh;
  const halfW = Math.round((sr - sx - 3 * inset) / 2);
  const halfH = Math.round((sb - sy - 3 * inset) / 2);
  const w = zone === "left" || zone === "right" || zone.length === 2 ? halfW : sr - sx - 2 * inset;
  const h = zone === "bottom" || zone.length === 2 ? halfH : sb - sy - 2 * inset;
  const east = zone === "right" || zone === "tr" || zone === "br";
  const south = zone === "bottom" || zone === "bl" || zone === "br";
  return { left: east ? sr - inset - w : sx + inset, top: south ? sb - inset - h : sy + inset, width: w, height: h };
}
//: The window minus the top bar, the status bar, a side tab rail, a sidebar
//: and the panels docked to a side, read when a drag starts or a dock is
//: fitted, never per move. `except` is the panel being placed.
function panelSafe(vw, vh, except, ignore = "") {
  const safe = { left: 0, top: 0, right: vw, bottom: vh };
  const seen = (id) => {
    const el = document.getElementById(id);
    return el && el.getClientRects().length ? el.getBoundingClientRect() : null;
  };
  const bar = seen("top-bar");
  const foot = seen("status-bar");
  const tabs = seen("tab-bar");
  if (bar) safe.top = Math.max(0, Math.round(bar.bottom));
  if (foot) safe.bottom = Math.min(vh, Math.round(foot.top));
  if (tabs && tabs.height > tabs.width && tabs.left < vw / 2 && ignore !== "left") safe.left = Math.round(tabs.right);
  const sides = [...document.querySelectorAll("aside.sidebar-panel")].filter((el) => !(except && el.contains(except)));
  const docked = [...document.querySelectorAll(".panel-movable-on")].filter((el) => el !== except && PANEL_STATE.get(el)?.dock);
  for (const el of [...sides, ...docked]) {
    if (!panelShown(el)) continue;
    const r = el.getBoundingClientRect();
    const zone = PANEL_STATE.get(el)?.dock || "";
    if (zone === "max" || zone === "bottom" || r.width >= vw - 2 || (el.tagName === "ASIDE" && r.height <= r.width)) continue;
    const west = r.left + r.width / 2 < vw / 2;
    //: A side the app is about to be pushed away from is not an obstacle.
    if (ignore === (west ? "left" : "right")) continue;
    if (west) safe.left = Math.max(safe.left, Math.round(r.right));
    else safe.right = Math.min(safe.right, Math.round(r.left));
  }
  return safe;
}
//: **Split screen** (INBOX 1474, the owner: "there's no point in docking if it
//: hides half the screen"). A panel docked to the left or right half pushes the
//: app aside: `--dock-push-left/right` on the root, read by `body`'s padding
//: (panel-movable-lazy.css, eased with `--ui-base`, instant with motion off).
//: Corner docks, the bottom and the maximise never push, and a panel that is
//: not fixed to the window (it would ride the push) does not either. One
//: preference, Settings, Appearance, and the head's toggle both write it.
function panelPushOn() {
  return prefs.get("panel-push", "on") !== "off";
}
function panelPinned(panel) {
  for (let el = panel; el && el !== document.body; el = el.parentElement) {
    if (getComputedStyle(el).position === "fixed") return true;
  }
  return false;
}
function panelShown(el) {
  return el.getClientRects().length > 0 && !el.closest("[data-panel-min]");
}
function panelPushSide(panel, zone) {
  return (zone === "left" || zone === "right") && panelMovableOn() && panelPinned(panel) ? zone : "";
}
function panelPushSync() {
  const vw = window.innerWidth;
  let l = 0;
  let r = 0;
  for (const el of document.querySelectorAll(".panel-movable-on")) {
    const st = PANEL_STATE.get(el);
    const side = st && panelShown(el) ? panelPushSide(el, st.dock) : "";
    if (st && st.push) st.push.hidden = !side;
    if (st && st.push) st.push.setAttribute("aria-pressed", String(panelPushOn()));
    if (!side || !panelPushOn()) continue;
    const b = el.getBoundingClientRect();
    if (side === "left") l = Math.max(l, Math.round(b.right));
    else r = Math.max(r, Math.round(vw - b.left));
  }
  if (vw - l - r < PANEL_PUSH_MIN) l = r = 0;
  const root = document.documentElement;
  root.style.setProperty("--dock-push-left", `${l}px`);
  root.style.setProperty("--dock-push-right", `${r}px`);
  root.toggleAttribute("data-dock-push", l + r > 0);
}
//: `data-panel-zones="left right max"` on a panel limits its zones.
function panelZoneFor(panel, zone) {
  const only = panel.dataset.panelZones;
  return !only || only.split(/\s+/).includes(zone) ? zone : "";
}
function panelRestoreOn() {
  return prefs.get("panel-pos", "on") !== "off";
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
//: An entry is `[x, y, w, h, dock?, layout?]`. `layout` is the panel's
//: `data-panel-layout` when it was stored (INBOX 1454): a panel whose layout
//: changed under a stored entry bumps it, and the old entry is not applied.
function panelStoreRead(id, layout = 0) {
  const e = panelStoreParse(prefs.get(PANEL_KEY, ""))[id];
  if (!Array.isArray(e) || e.length < 4 || e.length > 6) return null;
  const [x, y, w, h, dock, ver] = e;
  if (![x, y].every(Number.isFinite) || (w !== null && !Number.isFinite(w)) || (h !== null && !Number.isFinite(h))) return null;
  if ((ver || 0) !== layout) return null;
  return PANEL_ZONES.includes(dock) ? { x, y, w, h, dock } : { x, y, w, h };
}
function panelStoreWrite(id, st, layout = 0) {
  //: prefs swallows a private window or blocked storage: the panel still works.
  const all = panelStoreParse(prefs.get(PANEL_KEY, ""));
  if (st) {
    all[id] = [Math.round(st.x), Math.round(st.y), st.w, st.h];
    if (st.dock || layout) all[id].push(st.dock || "");
    if (layout) all[id].push(layout);
  } else {
    delete all[id];
  }
  prefs.setJSON(PANEL_KEY, all);
}
//: Whether a stored entry still makes sense for the panel as it is now: a
//: size under the minimum (the panel's own natural size when that is smaller),
//: a size past the window, a place a whole window away, or a zone the panel
//: does not allow. The old check only clamped a place into the window, and its
//: size minimum was the stored size itself, so a squashed entry stayed squashed.
function panelStoreFits(saved, nat, vw, vh, zones) {
  if (Math.abs(saved.x) > vw || Math.abs(saved.y) > vh) return false;
  if (saved.w !== null && (saved.w < Math.min(PANEL_MIN_W, nat.width) || saved.w > vw)) return false;
  if (saved.h !== null && (saved.h < Math.min(PANEL_MIN_H, nat.height) || saved.h > vh)) return false;
  return !saved.dock || !zones || zones.split(/\s+/).includes(saved.dock);
}
//: `data-panel-layout` on the panel or its dialog host, 0 when absent.
function panelLayout(panel) {
  const host = panel.closest('dialog, [role="dialog"]');
  return Number(panel.dataset.panelLayout || (host && host.dataset.panelLayout)) || 0;
}

function panelMovableOn() {
  return window.matchMedia(PANEL_MEDIA).matches;
}
//: The nearest ancestor-or-self that holds a head and sits in a dialog.
//: **Always the whole panel: the dialog itself, or the card that is its direct
//: child.** The head's own parent used to be taken, which is the card only when
//: the head sits straight in it; the OCR workspace wraps its head and tool row
//: in `.ocr-head`, so a drag moved that wrapper alone, the head bar drawn across
//: the middle of a body that stayed put (INBOX 1448). Climb from the element
//: that holds the head to the host's top-most box.
function panelOf(node) {
  const host = node instanceof Element ? node.closest('dialog, [role="dialog"]') : null;
  if (!host) return null;
  for (let el = node; el; el = el.parentElement) {
    if (!el.querySelector(":scope > .dialog-head")) continue;
    let top = el;
    while (top !== host && top.parentElement && top.parentElement !== host) top = top.parentElement;
    return top.closest("[data-panel-fixed]") ? null : top;
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
    st = { x: 0, y: 0, w: null, h: null, dock: "", pre: null, nat: null, id: panelId(panel), grip: null, reset: null, push: null, min: null, skip: false };
    PANEL_STATE.set(panel, st);
  }
  return st;
}
function panelApply(panel, st) {
  panel.style.translate = st.x || st.y ? `${st.x}px ${st.y}px` : "";
  //: **The scrim lifts once a panel is moved** (INBOX 1450, the owner:
  //: "there's no point in dragging windows if the background is darkened
  //: ... it should only be dark in the default position"). A panel moved,
  //: docked or resized is put where it is to see what is beside it; at its
  //: default place the dim stays. The panel is still modal (focus, Esc).
  panelScrimLift(panel, st);
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
//: The dimmed layer behind a panel: its `dialog` (the ::backdrop) or the
//: fixed overlay that holds it.
function panelScrimOf(panel) {
  return panel.closest("dialog, .modal-overlay, [id$='-overlay']");
}
function panelScrimLift(panel, st) {
  panelScrimOf(panel)?.toggleAttribute("data-panel-moved", Boolean(st.x || st.y || st.dock || st.w !== null));
}
//: One level down too: the OCR workspace wraps its head in `.ocr-head`, so it
//: had no reset button and none of the head's grab cursor or no-select rule,
//: and a drag there highlighted text (the owner 2026-10-29).
function panelHeadOf(panel) {
  return panel.querySelector(":scope > .dialog-head, :scope > * > .dialog-head");
}
//: Keeps a panel inside the window: size first, then place.
function panelClamp(panel, st) {
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const head = panelHeadOf(panel);
  const headH = head ? head.offsetHeight : 40;
  const safe = panelSafe(vw, vh, panel);
  const place = () => {
    const r = panel.getBoundingClientRect();
    //: Whole panel inside the free area when it fits (a window resize or a
    //: reload brings it back), else its top left.
    const m = panelClampMove(r, st.x, st.y, st.x, st.y, vw, vh, headH, safe);
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
    //: The minimum is the panel's natural size at most, not the size it was
    //: just given (that made a stored squash its own floor).
    const ref = st.nat ? { left: r.left, top: r.top, width: st.nat.width, height: st.nat.height } : r;
    const c = panelClampSize(ref, st.w ?? r.width, st.h ?? r.height, vw, vh);
    if (st.w !== null) st.w = c.w;
    if (st.h !== null) st.h = c.h;
    panelApply(panel, st);
    place();
  }
}
//: The one preview, reused: top layer (a modal dialog's own layer sits under
//: it), click-through. Its padding is `--space-3`, so the inset is read from it
//: (a density-aware length) rather than parsed out of a calc().
//: The snap preview and the open-panel observer, made on first use.
const PANEL_LIVE = { preview: null, watch: null };
function panelPreviewEl() {
  if (!PANEL_LIVE.preview || !PANEL_LIVE.preview.isConnected) {
    PANEL_LIVE.preview = document.createElement("div");
    PANEL_LIVE.preview.className = "panel-snap-preview";
    PANEL_LIVE.preview.setAttribute("popover", "manual");
    PANEL_LIVE.preview.setAttribute("aria-hidden", "true");
    document.body.appendChild(PANEL_LIVE.preview);
  }
  return PANEL_LIVE.preview;
}
function panelInset() {
  return parseFloat(getComputedStyle(panelPreviewEl()).paddingLeft) || 12;
}
function panelShowZone(r) {
  const el = panelPreviewEl();
  try {
    if (!r) {
      if (el.matches(":popover-open")) el.hidePopover();
      return;
    }
    el.style.left = `${r.left}px`;
    el.style.top = `${r.top}px`;
    el.style.width = `${r.width}px`;
    el.style.height = `${r.height}px`;
    if (!el.matches(":popover-open")) el.showPopover();
  } catch (_) {
    /* no popover support: the drop still docks, only the preview is missing */
  }
}
//: Fill the dock zone: size first, then one rect read to learn where the
//: centred layout put it, and translate the difference.
function panelFit(panel, st) {
  const z = panelZoneRect(st.dock, window.innerWidth, window.innerHeight, panelInset(), panelSafe(window.innerWidth, window.innerHeight, panel, panelPushOn() ? panelPushSide(panel, st.dock) : ""));
  if (!z) {
    st.dock = "";
    return;
  }
  st.w = z.width;
  st.h = z.height;
  panelApply(panel, st);
  const r = panel.getBoundingClientRect();
  st.x += z.left - r.left;
  st.y += z.top - r.top;
  panelApply(panel, st);
  panelPushSync();
}
function panelDock(panel, st, zone) {
  if (!st.dock) st.pre = { w: st.w, h: st.h };
  st.dock = zone;
  panelFit(panel, st);
}
function panelUnsnap(st) {
  st.dock = "";
  st.w = st.pre ? st.pre.w : null;
  st.h = st.pre ? st.pre.h : null;
  st.pre = null;
}
//: The reset button shows only while there is something to put back.
function panelSync(panel) {
  const st = panelSt(panel);
  if (st.reset) st.reset.hidden = !(st.x || st.y || st.w !== null || st.h !== null || st.dock);
}
//: Closing a panel with "open where you left them" off puts it back in the
//: middle (the saved place stays). One observer for all panels; it wakes only
//: when a panel appears or disappears.
function panelWatchOpen(panel) {
  if (typeof IntersectionObserver === "undefined") return;
  PANEL_LIVE.watch ||= new IntersectionObserver((list) => {
    for (const en of list) {
      if (en.isIntersecting || panelRestoreOn() || en.target.closest("[data-panel-min]")) continue;
      const st = panelSt(en.target);
      st.x = st.y = 0;
      st.w = st.h = null;
      st.dock = "";
      st.pre = null;
      panelApply(en.target, st);
      panelSync(en.target);
    }
    panelPushSync();
  });
  PANEL_LIVE.watch.observe(panel);
}
function panelFull(panel) {
  const r = panel.getBoundingClientRect();
  return r.width >= window.innerWidth - 2 && r.height >= window.innerHeight - 2;
}
function panelReset(panel) {
  const st = panelSt(panel);
  st.x = st.y = 0;
  st.w = st.h = null;
  st.dock = "";
  st.pre = null;
  panelApply(panel, st);
  if (st.id) panelStoreWrite(st.id, null);
  panelSync(panel);
  panelPushSync();
}
//: The grip's double-click: the size goes back, the place stays (a docked
//: panel is all size, so it goes back to the middle like the head's).
function panelResetSize(panel) {
  const st = panelSt(panel);
  if (st.dock) {
    panelReset(panel);
    return;
  }
  st.w = st.h = null;
  st.pre = null;
  panelApply(panel, st);
  panelClamp(panel, st);
  panelSave(panel);
}
function panelSave(panel) {
  const st = panelSt(panel);
  if (st.id) panelStoreWrite(st.id, st, panelLayout(panel));
  panelScrimLift(panel, st);
  panelSync(panel);
  panelPushSync();
}
//: Adopt a panel once: restore, add the grip. Cheap to call again.
function panelAdopt(panel) {
  if (!panel || !panelMovableOn()) return;
  const st = panelSt(panel);
  if (st.skip) return;
  if (!panel.classList.contains("panel-movable-on")) {
    if (panelFull(panel)) { st.skip = true; return; }
    //: Not laid out yet (a panel touched while hidden): adopt it next time.
    const nat = panel.getBoundingClientRect();
    if (!nat.width || !nat.height) return;
    st.nat = { width: nat.width, height: nat.height };
    panel.classList.add("panel-movable-on");
    panelWatchOpen(panel);
    let saved = st.id && panelRestoreOn() ? panelStoreRead(st.id, panelLayout(panel)) : null;
    //: A stored entry that does not fit this panel opens it at the default and
    //: is forgotten, rather than applied and left broken (INBOX 1454).
    if (saved && !panelStoreFits(saved, nat, window.innerWidth, window.innerHeight, panel.dataset.panelZones)) {
      panelStoreWrite(st.id, null);
      saved = null;
    }
    if (saved) {
      Object.assign(st, saved);
      panelApply(panel, st);
      if (st.dock) panelFit(panel, st);
      else panelClamp(panel, st);
    }
  }
  panelHeadOf(panel)?.classList.add("panel-drag-head");
  if (!st.reset || !st.reset.isConnected) {
    const head = panelHeadOf(panel);
    const actions = head && head.querySelector(":scope > .dialog-head-actions");
    if (head) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "icon-only ghost small dialog-head-btn panel-reset";
      btn.setAttribute("aria-label", "Put back in the middle");
      btn.title = "Put back in the middle. Double-clicking the title bar does the same.";
      const icon = document.createElement("i");
      icon.className = "ph ph-arrow-counter-clockwise";
      icon.setAttribute("aria-hidden", "true");
      btn.appendChild(icon);
      (actions || head).insertBefore(btn, actions ? actions.firstChild : null);
      st.reset = btn;
      const push = document.createElement("button");
      push.type = "button";
      push.className = "icon-only ghost small dialog-head-btn panel-push";
      push.setAttribute("aria-label", "Move the app aside while docked");
      push.title = "Move the app aside while this panel is docked to a side";
      push.hidden = true;
      const pushIcon = document.createElement("i");
      pushIcon.className = "ph ph-columns";
      pushIcon.setAttribute("aria-hidden", "true");
      push.appendChild(pushIcon);
      (actions || head).insertBefore(push, btn);
      st.push = push;
      if (panelPinned(panel)) {
        const min = document.createElement("button");
        min.type = "button";
        min.className = "icon-only ghost small dialog-head-btn panel-min";
        const minIcon = document.createElement("i");
        minIcon.className = "ph ph-minus";
        minIcon.setAttribute("aria-hidden", "true");
        min.appendChild(minIcon);
        min.addEventListener("click", () => panelMinimise(panel));
        const close = panelCloseBtn(panel);
        if (close) close.parentElement.insertBefore(min, close);
        else (actions || head).appendChild(min);
        st.min = min;
      }
    }
  }
  if (st.min) {
    const label = panelTitle(panel);
    st.min.setAttribute("aria-label", `Minimise ${label}`);
    st.min.title = `Minimise ${label} (Shift+Escape)`;
  }
  panelSync(panel);
  if (!st.grip || !st.grip.isConnected || st.grip.parentElement !== panel) {
    const grip = document.createElement("button");
    grip.type = "button";
    grip.className = "panel-grip";
    grip.setAttribute("aria-label", "Move or resize this panel");
    grip.title = "Drag to resize. Double-click resets the size. Arrow keys move, Shift and arrow keys resize, Home resets.";
    panel.appendChild(grip);
    st.grip = grip;
    panelGripRoom(panel, grip);
  }
}
//: The grip is the card's last row and hangs into its padding (INBOX 1454):
//: the padding in pixels is read once here and written as the grip's margins
//: and sticky `bottom`, capped at the grip's own size so a deep padding does
//: not float it. Cards differ (20 by 16 on `.card`, 12.8 on a popup, 0 on the
//: palette), which is why the CSS cannot say it.
function panelGripRoom(panel, grip) {
  const cs = getComputedStyle(panel);
  const size = grip.offsetHeight || 28;
  const cap = (v) => Math.max(0, Math.min(parseFloat(v) || 0, size));
  const pb = cap(cs.paddingBottom);
  grip.style.marginRight = `${-cap(cs.paddingRight)}px`;
  grip.style.marginBottom = `${-pb}px`;
  grip.style.bottom = `${-pb}px`;
}
function panelHeadDown(e) {
  const head = e.target.closest(".dialog-head");
  const panel = head && panelOf(head);
  if (!panel || e.button !== 0 || e.target.closest(PANEL_SKIP) || !panelMovableOn()) return;
  panelAdopt(panel);
  const st = panelSt(panel);
  if (st.skip) return;
  let rect = panel.getBoundingClientRect();
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const hh = head.offsetHeight;
  const inset = panelInset();
  const safe = panelSafe(vw, vh, panel);
  //: With the push on, a side dock is laid against the window's own edge: the
  //: sidebar and the rail beside it are pushed over with the rest of the app.
  const pushing = panelPushOn() && panelPinned(panel);
  const sideSafe = { left: pushing ? panelSafe(vw, vh, panel, "left") : safe, right: pushing ? panelSafe(vw, vh, panel, "right") : safe };
  let moved = 0;
  let x0 = e.clientX;
  let y0 = e.clientY;
  let ox = st.x;
  let oy = st.y;
  let zone = "";
  let lifted = false;
  panel.classList.add("panel-moving");
  head.setPointerCapture(e.pointerId);
  const move = (ev) => {
    if (st.dock) {
      //: Off the edge: back to the size it had, under the pointer (the one
      //: layout read of a drag, and only for a docked panel).
      if (Math.abs(ev.clientX - x0) + Math.abs(ev.clientY - y0) < 6) return;
      const fx = (x0 - rect.left) / rect.width;
      panelUnsnap(st);
      panelApply(panel, st);
      panelPushSync();
      const r = panel.getBoundingClientRect();
      st.x += ev.clientX - fx * r.width - r.left;
      st.y += ev.clientY - (y0 - rect.top) - r.top;
      rect = { left: ev.clientX - fx * r.width, top: ev.clientY - (y0 - rect.top), width: r.width, height: r.height };
      ox = st.x;
      oy = st.y;
      x0 = ev.clientX;
      y0 = ev.clientY;
    }
    const m = panelClampMove(rect, ox, oy, ox + ev.clientX - x0, oy + ev.clientY - y0, vw, vh, hh, safe);
    st.x = m.x;
    st.y = m.y;
    panel.style.translate = `${m.x}px ${m.y}px`;
    //: The dim lifts as the drag starts, not as it ends (it popped on release).
    if (!lifted && Math.abs(ev.clientX - e.clientX) + Math.abs(ev.clientY - e.clientY) > 4) {
      lifted = true;
      panelScrimLift(panel, st);
    }
    moved = Math.max(moved, Math.abs(ev.clientX - e.clientX) + Math.abs(ev.clientY - e.clientY));
    const z = panelZoneFor(panel, panelSnapZone(ev.clientX, ev.clientY, vw, vh));
    if (z !== zone) {
      zone = z;
      panelShowZone(z ? panelZoneRect(z, vw, vh, inset, sideSafe[z] || safe) : null);
    }
  };
  const done = (ev) => {
    head.removeEventListener("pointermove", move);
    head.removeEventListener("pointerup", done);
    head.removeEventListener("pointercancel", done);
    panel.classList.remove("panel-moving");
    //: The drop reads the pointer where it was let go, not the last move: a
    //: flick to the very edge can end with no move event at the edge.
    if (ev.type === "pointerup" && moved > 4) zone = panelZoneFor(panel, panelSnapZone(ev.clientX, ev.clientY, vw, vh));
    if (zone) panelShowZone(null);
    if (zone && ev.type === "pointerup") panelDock(panel, st, zone);
    panelSave(panel);
    if (moved > 4) {
      //: A drag is not a click on the head: swallow the one that follows.
      const eat = (c) => { c.stopPropagation(); c.preventDefault(); };
      head.addEventListener("click", eat, { capture: true, once: true });
      setTimeout(() => head.removeEventListener("click", eat, true), 80);
    }
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
  st.dock = "";
  st.pre = null;
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
  st.dock = "";
  st.pre = null;
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
    const m = panelClampMove(before, st.x, st.y, st.x + d.dx, st.y + d.dy, vw, vh, head ? head.offsetHeight : 40, panelSafe(vw, vh, panel));
    st.x = m.x;
    st.y = m.y;
  }
  panelApply(panel, st);
  panelSave(panel);
}
//: **Minimise** (INBOX 1475, the owner: "popups should have a minimise button
//: with a popup or indicator somewhere so the user can open it up or close the
//: popup"). A pinned panel (a dialog or overlay) hides with its state kept and
//: shows as a pill in `#panel-min-tray`, floating above the composer at the
//: content's bottom left; the pill restores it, its x closes it. A dialog is
//: re-opened non-modal while hidden (a modal one would keep the app inert) and
//: modal again on restore; the `close` it fires is swallowed so the panel's own
//: close handling does not run. Shift+Escape minimises from the keyboard.
const PANEL_MIN = new Map();
function panelMinHost(panel) {
  return panel.closest("dialog") || panelScrimOf(panel) || panel;
}
function panelTitle(panel) {
  const el = panel.querySelector(".dialog-head-title");
  return el ? el.textContent.trim().replace(/\s+/g, " ") || "Panel" : "Panel";
}
function panelCloseBtn(panel) {
  const head = panelHeadOf(panel);
  return head && head.querySelector('button[aria-label^="Close"], button[title^="Close"], button[data-close]');
}
function panelReopen(host, modal) {
  const quiet = (e) => {
    if (e.target !== host) return;
    e.stopPropagation();
    window.removeEventListener("close", quiet, true);
  };
  window.addEventListener("close", quiet, true);
  host.close();
  if (modal) host.showModal();
  else host.show();
}
function panelMinTray() {
  let tray = document.getElementById("panel-min-tray");
  if (!tray) {
    tray = document.createElement("div");
    tray.id = "panel-min-tray";
    tray.setAttribute("role", "group");
    tray.setAttribute("aria-label", "Minimised panels");
    tray.setAttribute("popover", "manual");
    document.body.appendChild(tray);
  }
  return tray;
}
//: Above the chat composer when it is on screen, else above the status bar, at
//: the left of the page the reader is on.
function panelMinPlace() {
  const tray = document.getElementById("panel-min-tray");
  if (!tray) return;
  const shown = (el) => (el && el.getClientRects().length ? el.getBoundingClientRect() : null);
  const page = shown(document.querySelector("#app-main > .tab-page:not(.hidden)"));
  const dock = shown(document.querySelector(".chat-dock"));
  const foot = shown(document.getElementById("status-bar"));
  const gap = parseFloat(getComputedStyle(tray).paddingLeft) || 8;
  const left = (dock || page || { left: 0 }).left + gap;
  const floor = dock ? dock.top : foot ? foot.top : window.innerHeight;
  tray.style.left = `${Math.round(left)}px`;
  tray.style.bottom = `${Math.round(window.innerHeight - floor + gap)}px`;
}
function panelChip(panel, host) {
  const title = panelTitle(panel);
  const chip = document.createElement("span");
  chip.className = "panel-chip";
  const open = document.createElement("button");
  open.type = "button";
  open.className = "panel-chip-open";
  open.setAttribute("aria-label", `Restore ${title}`);
  const glyph = panel.querySelector(".dialog-head-title .ph");
  const icon = document.createElement("i");
  icon.className = glyph ? [...glyph.classList].filter((c) => c !== "ph-lead").join(" ") : "ph ph-app-window";
  icon.setAttribute("aria-hidden", "true");
  const name = document.createElement("span");
  name.textContent = title;
  open.append(icon, name);
  open.addEventListener("click", () => panelRestore(host));
  const x = document.createElement("button");
  x.type = "button";
  x.className = "panel-chip-x";
  x.setAttribute("aria-label", `Close ${title}`);
  x.title = `Close ${title}`;
  const xi = document.createElement("i");
  xi.className = "ph ph-x";
  xi.setAttribute("aria-hidden", "true");
  x.appendChild(xi);
  x.addEventListener("click", () => panelRestore(host, true));
  chip.append(open, x);
  return chip;
}
function panelMinimise(panel) {
  const host = panelMinHost(panel);
  if (PANEL_MIN.has(host)) return;
  const modal = host.tagName === "DIALOG" && host.matches(":modal");
  const chip = panelChip(panel, host);
  PANEL_MIN.set(host, { panel, chip, modal });
  host.setAttribute("data-panel-min", "");
  host.inert = true;
  if (host.tagName === "DIALOG" && host.open) panelReopen(host, false);
  const tray = panelMinTray();
  tray.appendChild(chip);
  if (!tray.matches(":popover-open")) tray.showPopover();
  panelMinPlace();
  panelPushSync();
  chip.querySelector(".panel-chip-open").focus({ preventScroll: true });
}
function panelRestore(host, close = false) {
  const m = PANEL_MIN.get(host);
  if (!m) return;
  PANEL_MIN.delete(host);
  m.chip.remove();
  host.removeAttribute("data-panel-min");
  host.inert = false;
  if (!PANEL_MIN.size) panelMinTray().hidePopover();
  if (host.tagName === "DIALOG" && host.open && m.modal) panelReopen(host, true);
  const gone = host.tagName === "DIALOG" ? !host.open : host.classList.contains("hidden");
  if (gone) return;
  panelPushSync();
  const btn = close ? panelCloseBtn(m.panel) : panelSt(m.panel).min;
  if (btn) btn.focus({ preventScroll: true });
  if (close) (btn ? btn.click() : host.tagName === "DIALOG" && host.close());
}
function panelMinKey(e) {
  if (e.key !== "Escape" || !e.shiftKey || !(e.target instanceof Element)) return;
  const host = e.target.closest('dialog, [role="dialog"]');
  const head = host && host.querySelector(".dialog-head");
  const panel = head && panelOf(head);
  if (!panel || !panelSt(panel).min) return;
  e.preventDefault();
  e.stopPropagation();
  panelMinimise(panel);
}
function panelPushToggle() {
  const on = !panelPushOn();
  prefs.set("panel-push", on ? "on" : "off");
  const box = document.getElementById("panel-push-toggle");
  if (box) box.checked = on;
  document.querySelectorAll(".panel-movable-on").forEach((panel) => {
    const st = panelSt(panel);
    if (st.dock && panel.getClientRects().length) panelFit(panel, st);
  });
  panelPushSync();
}
let panelResizeTimer = 0;
function panelWindowResized() {
  clearTimeout(panelResizeTimer);
  panelResizeTimer = setTimeout(() => {
    if (PANEL_MIN.size) panelMinPlace();
    const on = panelMovableOn();
    document.querySelectorAll(".panel-movable-on").forEach((panel) => {
      const st = panelSt(panel);
      if (!on) {
        st.x = st.y = 0;
        st.w = st.h = null;
        panelApply(panel, st);
      } else if (panel.getClientRects().length) {
        if (st.dock) panelFit(panel, st);
        else panelClamp(panel, st);
      }
    });
  }, 120);
}
if (typeof document !== "undefined" && document.addEventListener) {
  document.addEventListener("focusin", (e) => { const p = panelOf(e.target); if (p) panelAdopt(p); }, true);
  document.addEventListener("keydown", panelMinKey, true);
  //: A pill rides above the page the reader is on: put it back after a tab change.
  document.addEventListener("click", () => { if (PANEL_MIN.size) setTimeout(panelMinPlace, 250); }, true);
  document.addEventListener("pointerover", (e) => {
    const t = e.target;
    if (t instanceof Element && t.closest(".dialog-head")) { const p = panelOf(t); if (p) panelAdopt(p); }
  }, true);
  document.addEventListener("pointerdown", (e) => {
    if (!(e.target instanceof Element)) return;
    if (e.target.closest(".panel-grip")) panelGripDown(e);
    else if (e.target.closest(".dialog-head")) panelHeadDown(e);
  }, true);
  //: A press on a head must not take the focus from the control that has it
  //: nor start a text selection (a pointerdown handler cannot stop either).
  document.addEventListener("mousedown", (e) => {
    const head = e.target instanceof Element && e.target.closest(".dialog-head.panel-drag-head");
    if (head && e.button === 0 && !e.target.closest(PANEL_SKIP) && panelMovableOn()) e.preventDefault();
  }, true);
  document.addEventListener("click", (e) => {
    const btn = e.target instanceof Element && e.target.closest(".panel-reset");
    const panel = btn && panelOf(btn);
    if (panel) panelReset(panel);
    if (e.target instanceof Element && e.target.closest(".panel-push")) panelPushToggle();
  }, true);
  document.addEventListener("dblclick", (e) => {
    if (!(e.target instanceof Element)) return;
    const grip = e.target.closest(".panel-grip");
    if (grip) {
      if (grip.parentElement && grip.parentElement.classList.contains("panel-movable-on")) panelResetSize(grip.parentElement);
      return;
    }
    if (e.target.closest(PANEL_SKIP)) return;
    const head = e.target.closest(".dialog-head");
    const panel = head && panelOf(head);
    if (panel && panel.classList.contains("panel-movable-on")) panelReset(panel);
  }, true);
  document.addEventListener("keydown", (e) => {
    if (e.target instanceof Element && e.target.closest(".panel-grip")) panelGripKey(e);
  }, true);
  window.addEventListener("resize", panelWindowResized);
}
