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
  if (!dest) return null;
  if (dest.type === "text") return dest.el.matches(OBJ_CARRY_EDIT) ? dest : null;
  if (dest.type === "board") return window.wbCommandsLive?.() && !wbIsMap() ? dest : null;
  return dest;
}

function objCarryMark(g, el) {
  if (g.marked === el) return;
  g.marked?.classList.remove("obj-target");
  el?.classList.add("obj-target");
  g.marked = el || null;
}

//: Half a second on a page's tab opens the page; moving off the tab first
//: forgets it. There is no edge sliding: the tab is the only door.
function objCarryNav(g) {
  objCarrySpaceMenu(g);
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

//: Half a second over the space switcher opens its menu, so a note can be
//: dropped on a space without letting go; the menu closes again at the end.
function objCarrySpaceMenu(g) {
  if (g.ref?.kind !== "note") return;
  const over = document.elementFromPoint(g.x, g.y)?.closest(OBJ_SPACE_BUTTON);
  if (!over) return void clearTimeout(g.spaceTimer);
  if (g.spaceTimer || g.spaceOpened) return;
  g.spaceTimer = setTimeout(() => {
    g.spaceOpened = true;
    if ($("space-menu").classList.contains("hidden")) over.click();
  }, OBJ_NAV_HOLD_MS);
}

function objCarryBegin(g) {
  Object.assign(g, { scroller: null, marked: null, hoverTab: "", hoverEl: null, hoverTimer: 0, spaceTimer: 0, spaceOpened: false });
}

//: What is outlined for a target: the composer's whole box, not its text area (which draws no outline).
function objCarryOutline(dest) {
  return dest?.type === "chat" ? dest.el.closest(".chat-dock") || dest.el : dest?.el;
}

function objCarryUpdate(g) {
  g.hoverTab || objCarryMark(g, objCarryOutline(objCarryTarget(g)));
  objCarryNav(g);
}

function objCarryEnd(g) {
  clearTimeout(g.hoverTimer);
  clearTimeout(g.spaceTimer);
  if (g.spaceOpened) closeSpaceMenu();
  g.spaceOpened = false;
  document.querySelectorAll(".obj-target").forEach((el) => el.classList.remove("obj-target"));
  g.marked = null;
}

function objCarryDrop(g) {
  const dest = objCarryTarget(g);
  objCarryEnd(g);
  if (dest) objPasteAt(g.ref, { ...dest, at: { x: g.x, y: g.y } });
}

//: Back over the list the card came from, it is a reorder again.
function objCarryRoute(g) {
  if (!g.surface) return "carry";
  const box = g.surface.list.getBoundingClientRect();
  const inside = g.x >= box.left && g.x <= box.right && g.y >= box.top && g.y <= box.bottom;
  return inside && g.surface.unit.isConnected ? "reorder" : "carry";
}

//: Last in `OBJ_MODES`: every card that no earlier mode took is carried.
OBJ_MODES.carry = { grab: () => ({}), begin: objCarryBegin, update: objCarryUpdate, drop: objCarryDrop, cancel: objCarryEnd, route: objCarryRoute };

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
