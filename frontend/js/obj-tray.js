// obj-tray.js: the tray, a few objects held while you go somewhere else
// (INBOX 1467, part 5). Lazy, loaded by obj-ref.js. A control in the status
// bar (`#status-tray`) with a count; filled by a drop onto it or "Add to tray"
// in a card's menu; opened, it lists what it holds. An item is dragged out (it
// is a card like any other, so the carry mode takes it), or clicked to paste
// where you were typing, or removed. The tray holds references only, in memory
// and in `sessionStorage` (try/catch: it can come back empty), so it survives
// a page change, a reload of the tab and a switch of space (which reloads the
// page) but not the browser. One tray for the notebook (audit 1031 Z1): a
// space is a filter, and "somewhere else" is most often another space.

const OBJ_TRAY_KEY = "obj-tray";
const OBJ_TRAY_MAX = 30;

let objTray = objTrayRead();
//: The field that had the focus when the tray was pressed, which is where a
//: click on an item pastes (opening the tray takes the focus away).
let objTrayFrom = null;

//: A reference remembers the space it was held in, because a card from one
//: space answers 404 in another: using it there is refused with a sentence
//: (objTrayPaste) instead of attaching a note that cannot be read.
function objTraySpace() {
  const id = window.activeSpaceId?.() ?? "all";
  return id === "all" ? "" : id;
}

function objTrayRead() {
  try {
    const rows = JSON.parse(sessionStorage.getItem(OBJ_TRAY_KEY) || "[]");
    return rows
      .map((row) => {
        const ref = objRef(row.kind, row.id, row.title, row.url);
        return ref && { ...ref, space: String(row.space || "") };
      })
      .filter(Boolean)
      .slice(0, OBJ_TRAY_MAX);
  } catch {
    return [];
  }
}

function objTrayWrite() {
  try {
    sessionStorage.setItem(OBJ_TRAY_KEY, JSON.stringify(objTray));
  } catch {
    // The tray still works from memory.
  }
}

//: True when held (already there counts); false when the tray is full.
function objTrayAdd(ref) {
  if (objTray.some((row) => objKey(row) === objKey(ref))) return true;
  if (objTray.length >= OBJ_TRAY_MAX) return false;
  objTray = [...objTray, { ...ref, space: ref.space ?? objTraySpace() }];
  objTrayChanged();
  return true;
}

//: A redraw replaces the buttons, so the one that had the focus is gone: the
//: focus goes to the item that took its place (or the next control, or the
//: trigger when the tray is empty).
function objTrayKeepFocus(change, at) {
  const holder = document.activeElement?.closest?.("#obj-tray, .obj-tray");
  change();
  if (!holder) return;
  const uses = holder.querySelectorAll(".obj-tray-use");
  const next = uses[Math.min(at, uses.length - 1)] || holder.querySelector("button:not(:disabled)") || $("status-tray");
  next?.focus();
}

function objTrayRemove(key) {
  const at = objTray.findIndex((row) => objKey(row) === key);
  objTrayKeepFocus(() => {
    objTray = objTray.filter((row) => objKey(row) !== key);
    objTrayChanged();
  }, at);
}

function objTrayClear() {
  const was = objTray;
  if (!was.length) return;
  objTrayKeepFocus(() => {
    objTray = [];
    objTrayChanged();
  }, 0);
  offerUndo("Clear tray", "Tray cleared", () => { objTray = was; objTrayChanged(); }, () => { objTray = []; objTrayChanged(); });
}

function objTrayChanged() {
  objTrayWrite();
  objTrayPaint();
}

function objTrayCountWords(count) {
  return count ? `Tray, ${count} held` : "Tray, empty";
}

function objTrayPaint() {
  const button = $("status-tray");
  const count = objTray.length;
  if (button) {
    const badge = button.querySelector(".status-tray-count");
    badge.textContent = count || "";
    badge.classList.toggle("hidden", !count);
    //: Square while it holds only its icon (`icon-only`), as wide as its count when it has one.
    button.classList.toggle("has-count", Boolean(count));
    button.setAttribute("aria-label", objTrayCountWords(count));
  }
  objTrayList();
}

//: The tray's words and rows, drawn into the status bar's panel and, on a
//: phone (no bar), into the sheet the header's More menu opens.
function objTrayList() {
  const panel = $("obj-tray");
  const holders = [panel, document.querySelector('[data-sheet="obj-tray"] .obj-tray')].filter(Boolean);
  for (const holder of holders) objTrayDraw(holder);
  if (panel && !panel.classList.contains("hidden")) placeHelpPopover(panel, $("status-tray"));
}

function objTrayDraw(holder) {
  const rows = objTray.map(objTrayRow);
  const head = document.createElement("div");
  head.className = "obj-tray-head";
  const title = document.createElement("strong");
  title.textContent = "Tray";
  const clear = smallButton("Clear all", "Take everything out of the tray", objTrayClear);
  clear.disabled = !rows.length;
  head.append(title, clear);
  const body = document.createElement(rows.length ? "ul" : "p");
  body.className = rows.length ? "obj-tray-list" : "obj-tray-empty muted";
  if (rows.length) body.append(...rows);
  else body.textContent = window.matchMedia?.("(pointer: fine)").matches ? "Drop a card here, or choose Add to tray in its menu." : "Choose Add to tray in a card's menu.";
  holder.replaceChildren(head, body);
}

function objTraySheet() {
  openSheet({
    label: "Tray",
    name: "obj-tray",
    build: (card) => {
      const body = document.createElement("div");
      body.className = "obj-tray";
      card.appendChild(body);
      objTrayDraw(body);
    },
  });
}

function objTrayRow(ref) {
  const li = document.createElement("li");
  li.className = "obj-tray-item";
  li.dataset.obj = objKey(ref);
  li.dataset.objTitle = ref.title;
  if (ref.url) li.dataset.objUrl = ref.url;
  const use = document.createElement("button");
  use.type = "button";
  use.className = "ghost quiet obj-tray-use";
  setLabel(use, `${OBJ_ICON_LABEL[ref.kind]} ${ref.title}`);
  use.title = `${ref.title}: paste where you were typing, or drag it out`;
  use.setAttribute("aria-label", `${OBJ_NOUN[ref.kind]}: ${ref.title}`);
  use.addEventListener("click", () => objTrayPaste(ref));
  const remove = smallButton("ph:x", `Take ${ref.title} out of the tray`, () => objTrayRemove(objKey(ref)));
  li.append(use, remove);
  return li;
}

const OBJ_ICON_LABEL = Object.fromEntries(Object.entries(OBJ_ICON).map(([kind, icon]) => [kind, `ph:${icon.slice(3)}`]));

//: Where a click on an item lands: the field that had the focus, else the open
//: board. Unlike a paste it also takes text fields, which it writes into. The
//: remembered field must still be on screen: on a phone the hand leaves a tab
//: with a box in it, and a paste into a hidden box is a paste nobody sees.
function objTrayDestination() {
  const dest = objTrayFrom?.isConnected && objTrayFrom.getClientRects().length ? objDestinationAt(objTrayFrom) : null;
  if (dest && dest.type !== "tray") return dest;
  return window.wbCommandsLive?.() ? { type: "board", el: $("whiteboard-container") } : null;
}

function objTrayPaste(ref) {
  const here = objTraySpace();
  if (ref.space && here && ref.space !== here) {
    return toast(`“${ref.title}” is in another space. Switch to All spaces to use it here.`, "info");
  }
  const dest = objTrayDestination();
  if (!dest) return objTrayOffer(ref);
  closeHelpPopovers();
  objPasteAt(ref, dest);
}

//: **No box to paste into is a choice, not a dead end** (audit 1031 Z13): on a
//: phone the sheet is modal and nothing was ever focused, so the press used to
//: say "click into a box first", which the sheet itself stops. It offers what
//: needs no box: the chat's attachments, and opening the object.
function objTrayOffer(ref) {
  const hash = routeHashFor(ref.kind, ref.id);
  const open = { label: "Open", run: () => (location.hash = hash) };
  const message = `Choose where “${ref.title}” goes.`;
  if (!OBJ_STAGE[ref.kind]) return hash ? toastAction(message, open.label, open.run) : toast(`“${ref.title}” can be dragged into a chat, a note or a board.`, "info");
  const attach = async () => {
    closeHelpPopovers();
    await switchTab("chat");
    objPasteAt(ref, { type: "chat", el: $("chat-input") });
  };
  toastAction(message, "Attach to the chat", attach, hash ? { also: open } : {});
}

OBJ_RENDERERS.tray = (ref) => {
  if (objTray.some((row) => objKey(row) === objKey(ref))) return toast(`“${ref.title}” is already in the tray`, "info") || true;
  if (objTrayAdd(ref)) toast(`Added “${ref.title}” to the tray`);
  else toast("The tray is full. Take something out first.", "info");
  return true;
};

OBJ_MENU_ROWS.push({ label: "Add to tray", run: (ref) => OBJ_RENDERERS.tray(ref) });

(() => {
  const button = $("status-tray");
  const panel = $("obj-tray");
  if (!button || !panel) return;
  //: The last field the hand was in, whatever opens the tray (a pointer, a key, the
  //: phone's sheet), not what the press happens to find: opening it moves the focus.
  document.addEventListener("focusin", (event) => {
    const el = event.target;
    if (!el.closest?.("#obj-tray, .obj-tray, #status-tray") && objDestinationAt(el)) objTrayFrom = el;
  });
  //: Captured, ahead of the popover's own listener: a button with no box (below
  //: 600 the bar is not on screen and the header's menu presses it) opens the sheet.
  button.addEventListener("click", (event) => {
    if (button.getBoundingClientRect().width) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    objTraySheet();
  }, true);
  wireHelpPopover(button, panel);
  button.addEventListener("click", () => {
    if (button.getAttribute("aria-expanded") !== "true") return;
    placeHelpPopover(panel, button);
    //: Into the panel: it is last in the page, seven Tab stops from the button.
    (panel.querySelector(".obj-tray-use") || panel.querySelector("button:not(:disabled)"))?.focus();
  });
  panel.addEventListener("keydown", (event) => {
    if (event.key === "Escape") button.focus();
  });
  objTrayPaint();
})();
