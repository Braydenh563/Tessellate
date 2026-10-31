// obj-reorder.js: drag a card to a new place in its list, or press Alt+Up /
// Alt+Down on it, and the list becomes "Custom order" (INBOX 1467, part 2).
// Lazy, loaded by obj-ref.js; the pointer gesture is obj-drag.js's, the stored
// order and the drop arithmetic are obj-order.js's.
//
// **Custom order is set only by a drop at a new place.** A drop where the card
// started, Escape and a click change nothing: not the sort, not the stored
// order, not the undo stack. The move is one Undo (`offerUndo`) that puts the
// previous sort and order back.

//: The lists that can be put in order. `list` holds the cards as direct
//: children (`unit` says which); `select` is the sort control the list already
//: has, which gains a "Custom order" option. `all()` names every object of the
//: list (not only the page or the filter on screen) in the sort it has now: the
//: first reorder stores that, so nothing off the page is left unplaced.
//: `top()` is a test for the cards a sort keeps first whatever the order.
const OBJ_SURFACES = [
  {
    scope: "notes", list: "#entry-list", unit: "li[data-id]", select: "note-sort",
    all: () => sortEntries(allEntries).map((entry) => `note:${entry.id}`),
    top: () => {
      const pinned = new Set(allEntries.filter((entry) => entry.pinned).map((entry) => `note:${entry.id}`));
      return (key) => pinned.has(key);
    },
  },
  {
    scope: "docs", list: "#library-docs-list", unit: "li", select: "library-docs-sort",
    all: () => [...libraryDocsAll].sort(LIBRARY_DOC_SORTS[libraryDocSort()]).map((doc) => `document:${doc.id}`),
  },
  {
    scope: "boards", list: "#library-boards-grid", unit: ".library-board-card", select: "library-boards-sort",
    all: () => wbVisibleBoards(window.wbBoardsAll || [], "").filter((board) => board.id !== null).map((board) => `${board.type === "map" ? "map" : "board"}:${board.id}`),
  },
  {
    scope: "media", list: "#library-images-grid", unit: ".library-image-tile", select: "library-media-sort",
    all: () => [...libraryImagesCache].sort(LIBRARY_MEDIA_SORTS[libraryMediaSort()]).map((row) => `${row._isImage && !row._isAttachment ? "image" : "file"}:${row.id}`),
  },
];

//: A list item's reference: the item is the card, or wraps it (a document row's `li`).
function objUnitRef(unit) {
  return (objCardAt(unit) || objCardAt(unit.firstElementChild))?.ref || null;
}

function objUnitKey(unit) {
  const ref = objUnitRef(unit);
  return ref ? objKey(ref) : "";
}

//: The cards of a list in screen order (the drag's own gap and a lifted card
//: are not cards).
function objUnitsOf(list, def) {
  return [...list.children].filter((el) => el.matches(def.unit) && !el.classList.contains("obj-gap"));
}

//: Which list a card sits in, from any element in it: `{ def, list, unit }`.
function objSurfaceAt(target) {
  for (const def of OBJ_SURFACES) {
    const list = target?.closest?.(def.list);
    const unit = list && [...list.children].find((el) => el.contains(target));
    if (unit?.matches(def.unit)) return { def, list, unit };
  }
  return null;
}

function objSetSort(def, value) {
  const select = $(def.select);
  if (!select) return;
  select.value = value;
  select.dispatchEvent(new Event("change", { bubbles: true }));
}

//: The visible keys in the order the list would show them under `order`.
function objShownUnder(def, keys, order) {
  const at = new Map(order.map((key, i) => [key, i]));
  const top = def.top?.() || (() => false);
  return keys.slice().sort((a, b) => Number(top(b)) - Number(top(a)) || at.get(a) - at.get(b));
}

//: The one place a new order is stored, the sort switched and Undo offered.
//: `keys` are the visible cards' keys in screen order before the move. False,
//: and nothing at all changed, when the list would look the same afterwards (a
//: drag round a pinned note: pinned notes stay on top in every order).
function objReorderCommit(def, ref, keys, from, to, quiet = false) {
  const stored = objOrderLoad(def.scope);
  const whole = def.all?.() || [];
  const next = objMergeOrder(whole.length ? whole : stored, keys, objMoveKey(keys, from, to));
  if (objShownUnder(def, keys, next).every((key, i) => key === keys[i])) return false;
  const was = $(def.select)?.value || "newest";
  const apply = (order, sort) => {
    objOrderSave(def.scope, order);
    objSetSort(def, sort);
    objRefocus(def, objKey(ref), 90);
  };
  apply(next, "custom");
  //: A key press is announced and Ctrl+Z undoes it; a toast for each press piled up.
  if (quiet) pushUndo(`Move ${ref.title}`, () => apply(stored, was), () => apply(next, "custom"));
  else offerUndo(`Move ${ref.title}`, `Moved “${ref.title}”`, () => apply(stored, was), () => apply(next, "custom"));
  return true;
}

//: --- The pointer mode ----------------------------------------------------------
function objReorderGrab(hit) {
  const surface = objSurfaceAt(hit.card);
  return surface ? { surface } : null;
}

function objReorderBegin(g) {
  const { def, list, unit } = g.surface;
  const units = objUnitsOf(list, def);
  Object.assign(g, { keys: units.map(objUnitKey), start: units.indexOf(unit), index: units.indexOf(unit), scroller: objScrollerOf(list) });
  g.gap = document.createElement(unit.tagName === "LI" ? "li" : "div");
  g.gap.className = "obj-gap";
  const box = unit.getBoundingClientRect();
  Object.assign(g.gap.style, { height: `${box.height}px`, width: unit.tagName === "LI" ? "" : `${box.width}px` });
  unit.after(g.gap);
  unit.classList.add("obj-lifted");
  unit.style.display = "none";
}

function objScrollerOf(el) {
  for (let node = el; node && node !== document.body; node = node.parentElement) {
    if (/auto|scroll/.test(getComputedStyle(node).overflowY) && node.scrollHeight > node.clientHeight) return node;
  }
  return document.scrollingElement;
}

function objReorderUpdate(g) {
  const { def, list, unit } = g.surface;
  //: Over the gap itself the card stays where it is: the gap is the empty slot,
  //: and the nearest *card* to it can be one a whole row away.
  const home = g.gap.getBoundingClientRect();
  if (g.x >= home.left && g.x <= home.right && g.y >= home.top && g.y <= home.bottom) return;
  const others = objUnitsOf(list, def).filter((el) => el !== unit);
  const index = objInsertIndex(others.map((el) => el.getBoundingClientRect()), g.x, g.y);
  if (index === g.index) return;
  g.index = index;
  const last = others.at(-1);
  if (others[index]) others[index].before(g.gap);
  else if (last) last.after(g.gap);
}

function objReorderRelease(g) {
  g.gap.remove();
  g.surface.unit.classList.remove("obj-lifted");
  g.surface.unit.style.display = "";
}

function objReorderDrop(g) {
  objReorderRelease(g);
  if (g.index !== g.start) objReorderCommit(g.surface.def, g.ref, g.keys, g.start, g.index);
}

//: Past a margin outside its own list the card is being carried, not reordered.
const OBJ_LEAVE_PX = 24;

function objReorderRoute(g) {
  const box = g.surface.list.getBoundingClientRect();
  const out = g.x < box.left - OBJ_LEAVE_PX || g.x > box.right + OBJ_LEAVE_PX || g.y < box.top - OBJ_LEAVE_PX || g.y > box.bottom + OBJ_LEAVE_PX;
  return out ? "carry" : "reorder";
}

OBJ_MODES.reorder = { grab: objReorderGrab, begin: objReorderBegin, update: objReorderUpdate, drop: objReorderDrop, cancel: objReorderRelease, route: objReorderRoute };

//: --- The keyboard ----------------------------------------------------------------
//: Alt+Up and Alt+Down on a focused card move it one place; the page says so.
function objReorderKey(event) {
  const dir = { ArrowUp: -1, ArrowDown: 1 }[event.key];
  if (!dir || !event.altKey || event.ctrlKey || event.metaKey || event.shiftKey || event.defaultPrevented) return;
  //: A field's own Alt+Arrow (a rename box inside a card) is not a move.
  if (event.target?.closest?.(OBJ_EDITABLE)) return;
  const hit = objSurfaceAt(document.activeElement);
  if (!hit || !objUnitRef(hit.unit)) return;
  event.preventDefault();
  event.stopPropagation();
  objReorderStep(hit, dir);
}

//: One place up or down: the keys' move and the card menu's Move up and Move
//: down rows (a drag has to have a way that is not a drag). `hit` is
//: `objSurfaceAt`'s. A key press is said and undone by Ctrl+Z; a menu click
//: (a phone has no keys) gets the toast with Undo.
function objReorderStep(hit, dir, byKey = true) {
  const ref = objUnitRef(hit.unit);
  const keys = objUnitsOf(hit.list, hit.def).map(objUnitKey);
  const from = keys.indexOf(objKey(ref));
  const to = from + dir;
  if (to < 0 || to >= keys.length) return announce(`${ref.title} is already ${dir < 0 ? "first" : "last"}.`);
  if (!objReorderCommit(hit.def, ref, keys, from, to, byKey)) return announce(`${ref.title} cannot move there.`);
  if (byKey) announce(`Moved ${ref.title} to place ${to + 1} of ${keys.length}. Ctrl+Z undoes it.`);
}

//: The list is drawn again after a move, sometimes twice (a document list
//: asks the server), so the card the hand was on gets the focus back until it
//: has held it for a few frames.
function objRefocus(def, key, tries, held = 0) {
  const list = document.querySelector(def.list);
  const unit = list && objUnitsOf(list, def).find((el) => objUnitKey(el) === key);
  const stop = unit && (unit.matches("[tabindex]") ? unit : unit.querySelector("[tabindex]"));
  const now = Boolean(unit?.contains(document.activeElement));
  if (stop && !now) stop.focus();
  if (tries > 0 && held < 8) setTimeout(() => objRefocus(def, key, tries - 1, now ? held + 1 : 0), 16);
}

//: **Notes' sort is boot code**, so the "custom" mode is added here instead of
//: in `sortEntries` (the boot scripts are at their gzip cap). Pinned notes stay
//: on top, as in every other order.
const objBaseSortEntries = sortEntries;
sortEntries = function sortEntriesWithCustom(entries) {
  if (noteSort !== "custom") return objBaseSortEntries(entries);
  const rank = objOrderCmp("notes", (entry) => `note:${entry.id}`);
  return [...entries].sort((a, b) => Number(b.pinned) - Number(a.pinned) || rank(a, b));
};

//: A list stored as "Custom order" is drawn before this file arrives in the
//: order it had; once it is here, the lists that chose it draw again.
function objReorderKick() {
  for (const def of OBJ_SURFACES) {
    const select = $(def.select);
    if (select?.value === "custom") select.dispatchEvent(new Event("change", { bubbles: true }));
  }
}

//: Capture, ahead of the lists' own arrow-key walking, which would move the focus instead.
window.addEventListener("keydown", objReorderKey, true);
objReorderKick();
