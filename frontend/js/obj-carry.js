// obj-carry.js: carry an object anywhere (INBOX 1467, part 4). Lazy, loaded by
// obj-ref.js. obj-drag.js hands over a card pressed anywhere that is not a
// reorderable list, or dragged out of one: a ghost follows the pointer (the
// engine's), the targets that would take it get an outline, and a drop does
// what a paste does there (`objPasteAt`). Hovering a top tab for half a second
// opens that page mid-drag, so a card can be carried across pages without
// letting go. Escape, or a drop where nothing takes it, changes nothing.

const OBJ_NAV_HOLD_MS = 500;
//: Of the text fields only these are places a link belongs; a search box or a
//: setting is not.
const OBJ_CARRY_EDIT = "textarea, .cm-editor, [contenteditable='true']";
const OBJ_TAB = "#tab-bar [data-tab]";

//: What would take the card under the pointer: `{ type, el }`, or null.
function objCarryTarget(g) {
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
  Object.assign(g, { scroller: null, marked: null, hoverTab: "", hoverEl: null, hoverTimer: 0 });
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
