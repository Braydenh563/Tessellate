// obj-ref.js: one reference to any object in the notebook, and the one place
// that draws it at a destination (INBOX 1467, part 1). Lazy: brought by
// drag-edge.js, which the boot preloads, so app.js carries no row for it.
// reordering, copy and paste, the drag ghost and the tray (obj-*.js) all pass
// this shape around, so a card in any list is read one way and a destination
// takes it one way.
//
// A reference is `{ kind, id, title, url }`: kind is one of `OBJ_KINDS`, `url`
// is only set for an image or a file (the one thing a link to them needs).
// Cards carry `data-obj="kind:id"` (and `data-obj-title`, `data-obj-url`);
// a card that already says what it is (a Library "All" card's
// `data-stop-key`, a Timeline row's `data-key`, a Notes row's `data-id`) is
// read from there instead of being given a second attribute, so the boot
// scripts did not grow.

const OBJ_KINDS = ["note", "document", "board", "map", "image", "file"];
const OBJ_NOUN = { note: "Note", document: "Document", board: "Board", map: "Mind map", image: "Image", file: "File" };

//: Where a card says what it is, nearest first wins. `key` returns "kind:id".
const OBJ_CARD_SOURCES = [
  { sel: "[data-obj]", key: (card) => card.dataset.obj },
  { sel: "[data-stop-key]", key: (card) => card.dataset.stopKey },
  { sel: ".timeline-row[data-key]", key: (card) => card.dataset.key },
  { sel: "#entry-list > li[data-id]", key: (card) => `note:${card.dataset.id}` },
];
const OBJ_CARD_SELECTOR = OBJ_CARD_SOURCES.map((source) => source.sel).join(",");
//: Where a card keeps its words, for a card nothing has put `data-obj-title` on.
const OBJ_TITLE_SELECTOR = ".library-card-title, .doc-list-title, .timeline-title, .dash-list-title, .note-title, h3, h4";

function objDefaultTitle(kind, id) {
  return `${OBJ_NOUN[kind]} ${id}`;
}

//: The reference, or null for a kind that is not an object (a chat, a tag) or
//: an id that is missing. Whitespace in the title is folded and the title is
//: bounded, so a pasted heading cannot make a chip a paragraph long.
function objRef(kind, id, title = "", url = "") {
  if (!OBJ_KINDS.includes(kind) || id == null || id === "") return null;
  const value = /^\d+$/.test(String(id)) ? Number(id) : id;
  const clean = String(title || "").replace(/\s+/g, " ").trim().slice(0, 120);
  return { kind, id: value, title: clean || objDefaultTitle(kind, value), url: url ? String(url) : "" };
}

function objKey(ref) {
  return `${ref.kind}:${ref.id}`;
}

//: "kind:id" as a card writes it, or null.
function objParseKey(text) {
  const at = String(text || "").indexOf(":");
  return at < 1 ? null : { kind: text.slice(0, at), id: text.slice(at + 1) };
}

function objNoteTitle(id) {
  const entry = typeof allEntries !== "undefined" && allEntries.find((row) => row.id === Number(id));
  return entry ? noteNamePlain(entry.title || entry.content).slice(0, 80).trim() : "";
}

function objCardTitle(kind, id, card) {
  if (card.dataset.objTitle) return card.dataset.objTitle;
  if (kind === "note") return objNoteTitle(id) || card.querySelector(OBJ_TITLE_SELECTOR)?.textContent || "";
  return card.querySelector(OBJ_TITLE_SELECTOR)?.textContent || card.getAttribute("aria-label") || "";
}

//: The card element holding an object and its reference, from any element
//: inside it (or the card itself): `{ card, ref }`, or null.
function objCardAt(target) {
  const card = target?.closest?.(OBJ_CARD_SELECTOR);
  if (!card) return null;
  const source = OBJ_CARD_SOURCES.find((row) => card.matches(row.sel));
  const parsed = objParseKey(source.key(card));
  const ref = parsed && objRef(parsed.kind, parsed.id, objCardTitle(parsed.kind, parsed.id, card), card.dataset.objUrl);
  return ref ? { card, ref } : null;
}

//: The one function that builds a reference from a card element.
function objRefFromCard(target) {
  return objCardAt(target)?.ref || null;
}

//: The plain link a reference is written as in text: the forms the app's own
//: "Copy wiki link" and the "/" menu write (`[[Title]]`, `![[board:12|Title]]`),
//: and Markdown for a picture or a file, which are addressed by their url.
function objLinkText(ref) {
  const name = ref.title.replace(/[[\]|]/g, " ").replace(/\s+/g, " ").trim();
  if (ref.kind === "note" || ref.kind === "document") return `[[${name}]]`;
  if (ref.kind === "board" || ref.kind === "map") return `![[${ref.kind}:${ref.id}|${name}]]`;
  if (!ref.url) return name;
  return ref.kind === "image" ? `![${name}](${ref.url})` : `[${name}](${ref.url})`;
}

//: --- Destinations ------------------------------------------------------------
//: What a drop or a paste lands on, by the element under the pointer or the
//: focus: first match wins, so the specific ones are first.
const OBJ_DESTS = [
  { type: "tray", sel: "#status-tray, #obj-tray" },
  { type: "chat", sel: "#chat-input, .chat-composer, .chat-dock" },
  { type: "reminder", sel: "#reminder-magic, #reminder-compose" },
  { type: "board", sel: "#whiteboard-container" },
  { type: "text", sel: "textarea, input[type='text'], input:not([type]), [contenteditable='true'], .cm-editor, #doc-editor" },
];

function objDestinationAt(target) {
  const el = target?.closest ? target : target?.parentElement;
  const row = el && OBJ_DESTS.find((dest) => el.closest(dest.sel));
  return row ? { type: row.type, el: el.closest(row.sel) } : null;
}

//: Chat staging, by kind, on the composer's own functions (chat-attach.js):
//: false means it could not (the four-attachment ceiling).
const OBJ_STAGE = {
  note: (ref) => {
    if (!attachedNoteIds.includes(ref.id)) attachedNoteIds.push(ref.id);
    renderAttachments();
    return true;
  },
  document: (ref) => attachDocumentToChat(ref.id, ref.title),
  board: (ref) => attachBoardToChat(ref.id, ref.title),
  map: (ref) => attachBoardToChat(ref.id, ref.title),
  file: (ref) => attachLibraryFile(ref.id, ref.title),
  image: (ref) => {
    if (attachedImages.some((row) => String(row.id) === String(ref.id))) return true;
    if (attachedImages.length >= 4) return false;
    attachedImages.push({ id: ref.id, url: ref.url, name: ref.title, key: `obj-${ref.id}` });
    renderImageAttachments();
    return true;
  },
};

//: Text goes in through the browser's edit pipeline, so the field's own Ctrl+Z
//: still works and a note or document editor sees an `input` event (its dirty
//: flag, autogrow, CodeMirror's state).
function objInsertText(el, text) {
  const field = el?.matches?.("textarea, input, [contenteditable], .cm-editor") ? el : null;
  const focus = field?.matches(".cm-editor") ? field.querySelector(".cm-content") : field;
  focus?.focus?.();
  return Boolean(focus) && Boolean(document.execCommand?.("insertText", false, text));
}

//: A destination type's renderer; obj-clip.js adds `board`, the tray its own.
const OBJ_RENDERERS = {
  chat: (ref) => OBJ_STAGE[ref.kind](ref),
  text: (ref, dest) => objInsertText(dest.el, objLinkText(ref)),
  reminder: (ref, dest) => objInsertText(dest.el.matches("textarea") ? dest.el : $("reminder-magic"), ref.title),
};

//: The one function that renders a reference at a destination
//: (`objDestinationAt`'s result). True when it landed.
function objRender(ref, dest) {
  const render = dest && OBJ_RENDERERS[dest.type];
  return Boolean(ref && render && render(ref, dest));
}

//: The rest of the object-move scripts ride with this one, in this order (each
//: only calls upwards at load); `lazyScript` is app.js's own loader, which keeps
//: dynamic scripts in order.
["/js/obj-order.js", "/js/obj-drag.js", "/js/obj-reorder.js", "/js/obj-clip.js", "/js/obj-carry.js", "/js/obj-tray.js"].forEach(lazyScript);
