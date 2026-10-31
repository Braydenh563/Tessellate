// obj-tray.js: the tray, a few objects held while you go somewhere else
// (INBOX 1467, part 5). Lazy, loaded by obj-ref.js. A control in the status
// bar (`#status-tray`) with a count; filled by a drop onto it or "Add to tray"
// in a card's menu; opened, it lists what it holds. An item is dragged out (it
// is a card like any other, so the carry mode takes it), or clicked to paste
// where you were typing, or removed. The tray holds references only, in memory
// and in `sessionStorage` (try/catch: it can come back empty), so it survives
// a page change and a reload of the tab but not the browser.

const OBJ_TRAY_KEY = "obj-tray";
const OBJ_TRAY_MAX = 30;

let objTray = objTrayRead();
//: The field that had the focus when the tray was pressed, which is where a
//: click on an item pastes (opening the tray takes the focus away).
let objTrayFrom = null;

function objTrayRead() {
  try {
    const rows = JSON.parse(sessionStorage.getItem(OBJ_TRAY_KEY) || "[]");
    return rows.map((row) => objRef(row.kind, row.id, row.title, row.url)).filter(Boolean).slice(0, OBJ_TRAY_MAX);
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
  objTray = [...objTray, ref];
  objTrayChanged();
  return true;
}

function objTrayRemove(key) {
  objTray = objTray.filter((row) => objKey(row) !== key);
  objTrayChanged();
}

function objTrayClear() {
  const was = objTray;
  if (!was.length) return;
  objTray = [];
  objTrayChanged();
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
  else body.textContent = "Drop a card here, or choose Add to tray in its menu.";
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
  use.title = "Paste where you were typing, or drag it out";
  setLabel(use, `${OBJ_ICON_LABEL[ref.kind]} ${ref.title}`);
  use.addEventListener("click", () => objTrayPaste(ref));
  const remove = smallButton("ph:x", `Take ${ref.title} out of the tray`, () => objTrayRemove(objKey(ref)));
  li.append(use, remove);
  return li;
}

const OBJ_ICON_LABEL = Object.fromEntries(Object.entries(OBJ_ICON).map(([kind, icon]) => [kind, `ph:${icon.slice(3)}`]));

//: Where a click on an item lands: the field that had the focus, else the open
//: board. Unlike a paste it also takes text fields, which it writes into.
function objTrayDestination() {
  const dest = objDestinationAt(objTrayFrom);
  if (dest && dest.type !== "tray") return dest;
  return window.wbCommandsLive?.() ? { type: "board", el: $("whiteboard-container") } : null;
}

function objTrayPaste(ref) {
  const dest = objTrayDestination();
  if (!dest) return toast("Click into a chat box, a note or a board first, then choose it.", "info");
  closeHelpPopovers();
  objPasteAt(ref, dest);
}

OBJ_RENDERERS.tray = (ref) => {
  const held = objTrayAdd(ref);
  toast(held ? `Added “${ref.title}” to the tray.` : "The tray is full. Take something out first.", held ? undefined : "info");
  return true;
};

OBJ_MENU_ROWS.push({ label: "Add to tray", run: (ref) => OBJ_RENDERERS.tray(ref) });

(() => {
  const button = $("status-tray");
  const panel = $("obj-tray");
  if (!button || !panel) return;
  //: Before the click moves the focus to the button.
  button.addEventListener("pointerdown", () => { objTrayFrom = document.activeElement; }, true);
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
    if (button.getAttribute("aria-expanded") === "true") placeHelpPopover(panel, button);
  });
  objTrayPaint();
})();
