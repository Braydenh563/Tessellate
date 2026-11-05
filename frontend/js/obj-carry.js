// obj-carry.js: carry an object anywhere (INBOX 1467, part 4). Lazy, loaded by
// obj-ref.js. obj-drag.js hands over a card pressed anywhere that is not a
// reorderable list, or dragged out of one: a ghost follows the pointer (the
// engine's), the targets that would take it get an outline, and a drop does
// what a paste does there (`objPasteAt`). Hovering a top tab for half a second
// opens that page mid-drag, so a card can be carried across pages without
// letting go. Escape, or a drop where nothing takes it, changes nothing.
// A note can also be filed by dropping it on a category in the sidebar or, with
// the space switcher's menu opened by hovering its button, on a space (audit
// 1031 Z19): the same move as the menus, with the same Undo.

const OBJ_NAV_HOLD_MS = 500;
//: Of the text fields only these are places a link belongs; a search box or a
//: setting is not.
const OBJ_CARRY_EDIT = "textarea, .cm-editor, [contenteditable='true']";
const OBJ_TAB = "#tab-bar [data-tab]";

//: Where a note is filed by dropping it: a category row, a space's row in the
//: switcher's menu (not "All spaces", which is a view). Only notes are filed.
const OBJ_FILE_DESTS = [
  { type: "category", sel: "#category-list li[data-category]" },
  { type: "space", sel: '#space-menu [data-space-id]:not([data-space-id="all"])' },
];
const OBJ_SPACE_BUTTON = "#space-switcher-btn";

//: **The tray as a drop target** (INBOX 1593), one object so it is one name in the shared scope.
//: The zone is the button and the open panel with room around them: the 28 px button
//: grown by `REACH`, the panel grown by half of it and the gap between the two (the panel
//: sits a caret's height above its button), so a pointer can travel from one to the other
//: without leaving it. The spring: a drag held over the zone for `SPRING_MS` opens the
//: tray, and a tray the drag opened shuts again unless the card landed in it. Both press the
//: button itself, so placement, focus and `aria-expanded` are what a hand gets. A phone has
//: no bar (no box) and so no zone and no spring.
const objTrayDoor = (() => {
  const REACH = 12;
  const SPRING_MS = 400;
  const isOpen = () => $("status-tray")?.getAttribute("aria-expanded") === "true";
  const zone = () => {
    const button = $("status-tray");
    const panel = $("obj-tray");
    const b = button?.getBoundingClientRect();
    if (!b?.width) return [];
    const grow = (r, by) => ({ left: r.left - by, top: r.top - by, right: r.right + by, bottom: r.bottom + by });
    const rects = [grow(b, REACH)];
    if (!panel || panel.classList.contains("hidden")) return rects;
    const p = panel.getBoundingClientRect();
    rects.push(grow(p, REACH / 2));
    const span = { left: Math.max(b.left, p.left) - REACH, right: Math.min(b.right, p.right) + REACH };
    if (p.bottom <= b.top) rects.push({ ...span, top: p.bottom, bottom: b.top });
    else if (p.top >= b.bottom) rects.push({ ...span, top: b.bottom, bottom: p.top });
    return rects;
  };
  const hit = (x, y) => zone().some((r) => x >= r.left && x <= r.right && y >= r.top && y <= r.bottom);
  return {
    zone,
    hit,
    isOpen,
    //: Over the zone long enough: open it. Off the zone first: forget it.
    cue(g) {
      if (!hit(g.x, g.y)) {
        clearTimeout(g.trayTimer);
        g.trayTimer = 0;
        return;
      }
      if (g.trayTimer || g.trayOpened || isOpen()) return;
      g.trayTimer = setTimeout(() => {
        g.trayTimer = 0;
        const button = $("status-tray");
        if (!button?.getBoundingClientRect().width || isOpen()) return;
        button.click();
        g.trayOpened = true;
      }, SPRING_MS);
    },
    shut() {
      if (isOpen()) $("status-tray").click();
    },
  };
})();

function objCarryFileTarget(g) {
  if (g.ref?.kind !== "note") return null;
  const el = document.elementFromPoint(g.x, g.y);
  const row = el && OBJ_FILE_DESTS.find((dest) => el.closest(dest.sel));
  return row ? { type: row.type, el: el.closest(row.sel) } : null;
}

//: What would take the card under the pointer: `{ type, el }`, or null.
function objCarryTarget(g) {
  const filed = objCarryFileTarget(g);
  if (filed) return filed;
  const dest = objDestinationAt(document.elementFromPoint(g.x, g.y));
  //: Nothing exact under the pointer but inside the tray's reach: the tray takes it.
  if (!dest) return objTrayDoor.hit(g.x, g.y) ? { type: "tray", el: $("status-tray") } : null;
  if (dest.type === "text") return dest.el.matches(OBJ_CARRY_EDIT) ? dest : null;
  if (dest.type === "board") return window.wbCommandsLive?.() && !wbIsMap() ? dest : null;
  return dest;
}

//: Half a second on a page's tab opens the page; moving off the tab first
//: forgets it. There is no edge sliding: the tab is the only door.
function objCarryNav(g) {
  //: Half a second over the space switcher opens its menu, so a note can be
  //: dropped on a space without letting go; the menu closes again at the end.
  const over = g.ref?.kind === "note" && document.elementFromPoint(g.x, g.y)?.closest(OBJ_SPACE_BUTTON);
  if (!over) clearTimeout(g.spaceTimer);
  else if (!g.spaceTimer && !g.spaceOpened) {
    g.spaceTimer = setTimeout(() => {
      g.spaceOpened = true;
      if ($("space-menu").classList.contains("hidden")) over.click();
    }, OBJ_NAV_HOLD_MS);
  }
  const tab = document.elementFromPoint(g.x, g.y)?.closest(OBJ_TAB);
  const name = tab && tab.getAttribute("aria-selected") !== "true" ? tab.dataset.tab : "";
  if (g.hoverTab === name) return;
  clearTimeout(g.hoverTimer);
  g.hoverEl?.classList.remove("obj-target");
  g.hoverTab = name;
  g.hoverEl = name ? tab : null;
  g.hoverEl?.classList.add("obj-target");
  if (name) g.hoverTimer = setTimeout(() => switchTab(name), OBJ_NAV_HOLD_MS);
}

function objCarryBegin(g) {
  Object.assign(g, { scroller: null, marked: [], hoverTab: "", hoverEl: null, hoverTimer: 0, spaceTimer: 0, spaceOpened: false, trayTimer: 0, trayOpened: false });
}

//: What is outlined for a target: the composer's whole box, not its text area (which draws
//: no outline); for the tray, the button and the open panel both (the whole drop zone).
function objCarryUpdate(g) {
  if (!g.hoverTab) {
    const dest = objCarryTarget(g);
    const next = (dest?.type === "tray" ? [dest.el, objTrayDoor.isOpen() ? $("obj-tray") : null] : [dest?.type === "chat" ? dest.el.closest(".chat-dock") || dest.el : dest?.el]).filter(Boolean);
    if (next.length !== g.marked.length || next.some((el, at) => el !== g.marked[at])) {
      for (const el of g.marked) el.classList.remove("obj-target");
      for (const el of next) el.classList.add("obj-target");
      g.marked = next;
    }
  }
  objCarryNav(g);
  objTrayDoor.cue(g);
}

function objCarryEnd(g, landed = false) {
  clearTimeout(g.hoverTimer);
  clearTimeout(g.spaceTimer);
  clearTimeout(g.trayTimer);
  if (g.spaceOpened) closeSpaceMenu();
  g.spaceOpened = false;
  if (g.trayOpened && !landed) objTrayDoor.shut();
  g.trayOpened = false;
  document.querySelectorAll(".obj-target").forEach((el) => el.classList.remove("obj-target"));
  g.marked = [];
}

function objCarryDrop(g) {
  const dest = objCarryTarget(g);
  objCarryEnd(g, dest?.type === "tray");
  if (dest) objPasteAt(g.ref, { ...dest, at: { x: g.x, y: g.y } });
}

//: Back over the list the card came from, and not over a popup drawn on it, it is a
//: reorder again (the reorder route says which).
function objCarryRoute(g) {
  if (!g.surface) return "carry";
  const box = g.surface.list.getBoundingClientRect();
  const inside = g.x >= box.left && g.x <= box.right && g.y >= box.top && g.y <= box.bottom;
  return inside && g.surface.unit.isConnected ? OBJ_MODES.reorder.route(g) : "carry";
}

//: Last in `OBJ_MODES`: every card that no earlier mode took is carried.
OBJ_MODES.carry = { grab: () => ({}), begin: objCarryBegin, update: objCarryUpdate, drop: objCarryDrop, cancel: (g) => objCarryEnd(g), route: objCarryRoute };

//: A note dropped on a category or a space is filed there, with the toast and
//: Undo of the menus' own moves.
OBJ_RENDERERS.category = (ref, dest) => {
  moveNotesToCategory([ref.id], dest.el.dataset.category);
  return true;
};

OBJ_RENDERERS.space = (ref, dest) => {
  const space = spacesCache.find((row) => row.id === dest.el.dataset.spaceId);
  if (!space) return false;
  moveNotesToSpace([ref.id], space);
  return true;
};
