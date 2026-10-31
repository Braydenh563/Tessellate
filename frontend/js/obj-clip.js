// obj-clip.js: copy and paste an object (INBOX 1467, part 3). Lazy, loaded by
// obj-ref.js. Ctrl/Cmd+C on a focused card, or "Copy" in a card's menu, puts
// the reference on an in-app clipboard (`objClip`) and its plain link on the
// system clipboard, and says so in a toast. Ctrl/Cmd+V then does what a drop
// does there (`objRender`): a chat composer stages an attachment, a reminder
// field takes the title, a board takes a card, and a note or document editor
// takes the link as text through the browser's own paste, so nothing needs
// doing for it.
//
// The system clipboard is the source of truth for "is this paste ours": the
// in-app reference is used only while the clipboard still holds the very text
// it wrote, so a later copy of anything else (words, a picture) is an
// ordinary paste.

let objClip = null;

const OBJ_EDITABLE = "input, textarea, select, [contenteditable='true'], .cm-editor";

function objToastCopied(ref) {
  const name = ref.title.length > 40 ? `${ref.title.slice(0, 39)}…` : ref.title;
  toast(`Copied “${name}”`);
  announce(`Copied ${OBJ_NOUN[ref.kind].toLowerCase()} ${ref.title}.`);
}

//: Put a reference on both clipboards. `data` is a copy event's clipboardData
//: (synchronous, no permission); without one a copy is asked for, then the
//: async clipboard; a refusal is not an error, the in-app clipboard holds the object.
function objClipPut(ref, data) {
  objClip = { ref, text: objLinkText(ref) };
  if (data) data.setData("text/plain", objClip.text);
  else if (!objCopyByEvent(objClip.text)) navigator.clipboard?.writeText?.(objClip.text)?.catch(() => {});
  objToastCopied(ref);
}

//: A menu click has no clipboardData of its own: ask the browser for a copy and
//: answer it with the text, which needs no permission inside a click.
function objCopyByEvent(text) {
  const answer = (event) => {
    event.stopImmediatePropagation();
    event.preventDefault();
    event.clipboardData.setData("text/plain", text);
  };
  document.addEventListener("copy", answer, { once: true, capture: true });
  const done = document.execCommand?.("copy");
  document.removeEventListener("copy", answer, true);
  return Boolean(done);
}

//: A card's own tick is the first Tab stop of a document, board or picture: it is the card for a copy.
const OBJ_TICK = "input[type='checkbox'], input[type='radio']";

document.addEventListener("copy", (event) => {
  const el = document.activeElement;
  const field = el?.closest?.(OBJ_EDITABLE);
  if ((field && !field.matches(OBJ_TICK)) || window.getSelection()?.toString()) return;
  const hit = objCardAt(el);
  if (!hit) return;
  event.preventDefault();
  objClipPut(hit.ref, event.clipboardData);
});

//: Where a paste lands: the focused destination, or the open board when no
//: field has the focus. Text fields are left to the browser.
function objPasteDestination(target) {
  const dest = objDestinationAt(target);
  if (dest && dest.type !== "text" && dest.type !== "tray" && dest.type !== "board") return dest;
  if (dest?.type === "text" || target?.closest?.(OBJ_EDITABLE)) return null;
  //: A mind map has its own outline paste, which runs when this lets go.
  if (!window.wbCommandsLive?.() || window.wbIsMap?.()) return null;
  return { type: "board", el: $("whiteboard-container") };
}

document.addEventListener("paste", (event) => {
  if (!objClip || event.clipboardData?.getData("text/plain") !== objClip.text) return;
  const dest = objPasteDestination(document.activeElement);
  if (!dest) return;
  event.preventDefault();
  event.stopPropagation();
  objPasteAt(objClip.ref, dest);
}, true);

//: The one landing for a paste, a drop and a tray click: renders, and says why
//: when it could not.
function objPasteAt(ref, dest) {
  if (dest.type === "chat" && ref.kind === "note" && attachedNoteIds.includes(ref.id)) return toast("Already attached", "info");
  if (!objRender(ref, dest)) return toast(dest.type === "chat" ? "That message has all the attachments it takes." : "Nothing here takes that.", "info");
  if (dest.type === "chat") announce(`Attached ${ref.title} to the message.`);
}

//: --- The board ------------------------------------------------------------
//: A note is a card (the board's own drop, `wbPlaceNote`); anything else is a
//: text box holding its link, which the board draws as a chip or a link card.
//: `dest.at` is a client point (a drop); a paste has none and lands in view.
async function objBoardText(ref, at) {
  const item = wbPasteTextBoxItem(objLinkText(ref), at[0], at[1], { md: true });
  let made = [];
  await wbRecordGesture(async () => {
    made = await wbCreateCopies([item], 0, 0);
  });
  wbSelectMade(made);
  wbAnnounce(`Placed ${ref.title} on the board.`);
}

OBJ_RENDERERS.board = (ref, dest) => {
  if (!window.wbCommandsLive?.()) return false;
  if (wbIsMap()) {
    toast("A mind map takes an outline. Open a board to place it.", "info");
    return false;
  }
  const at = dest.at ? wbClientToBoard(dest.at.x, dest.at.y) : wbViewCentre();
  if (ref.kind === "note") wbPlaceNote(ref.id, at);
  else objBoardText(ref, at);
  return true;
};

//: --- The card's menu --------------------------------------------------------
//: `kebabMenu` calls this as a menu opens (sheets-selects.js): a menu inside a
//: card gets Copy beneath its own rows, once.
function objKebabRows(menu) {
  //: Not a link's own menu inside a note card: its rows are about the link, and Copy would take the note.
  const hit = !menu.dataset.objRows && !menu.closest(".link-connection") && objCardAt(menu);
  if (!hit) return;
  menu.dataset.objRows = "1";
  const rule = document.createElement("div");
  rule.className = "menu-sep";
  rule.setAttribute("role", "separator");
  const shown = OBJ_MENU_ROWS.filter((row) => !row.show || row.show(hit.card));
  //: A list in Custom order is being arranged: its Move rows lead the menu
  //: (blind test 2026-10-31: they were last of fourteen, with no icon).
  const arranging = objArranging(hit.card);
  const moves = arranging ? shown.filter((row) => row.moves) : [];
  const rows = shown.filter((row) => !moves.includes(row)).map((row) => objMenuRow(row, hit.card));
  if (moves.length) menu.prepend(...moves.map((row) => objMenuRow(row, hit.card)), rule.cloneNode());
  //: Above a menu's own delete, not after it.
  const danger = menu.querySelector(":scope > .menu-danger");
  if (danger) danger.before(rule, ...rows);
  else menu.append(rule, ...rows);
}

//: Whether the card's list is in Custom order (a list's sort select says so).
function objArranging(card) {
  const hit = objSurfaceAt(card);
  return Boolean(hit && $(hit.def.select)?.value === "custom");
}

function objMenuRow(row, card) {
  const button = document.createElement("button");
  button.className = "menu-item";
  button.setAttribute("role", "menuitem");
  setLabel(button, row.icon ? `ph:${row.icon} ${row.label}` : row.label);
  button.addEventListener("click", (event) => {
    event.stopPropagation();
    closeActionMenus();
    const ref = objRefFromCard(card);
    if (ref) row.run(ref, card);
  });
  return button;
}

//: Rows later files add to (the tray, part 5): `{ label, run(ref, card), show?(card) }`.
//: Move up and Move down are the drag's other way (obj-reorder.js's `objReorderStep`):
//: a phone has no drag and no Alt key.
const OBJ_MENU_ROWS = [
  { label: "Copy card", run: (ref) => objClipPut(ref) },
  { label: "Move up", icon: "arrow-up", moves: true, show: (card) => Boolean(objSurfaceAt(card)), run: (ref, card) => objReorderStep(objSurfaceAt(card), -1, false) },
  { label: "Move down", icon: "arrow-down", moves: true, show: (card) => Boolean(objSurfaceAt(card)), run: (ref, card) => objReorderStep(objSurfaceAt(card), 1, false) },
];
