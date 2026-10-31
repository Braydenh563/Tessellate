// The Notes tab's capture card (INBOX 1479). The bar above the list is one line
// in index.html; its first focus fetches this file (notes-list.js), which
// opens the card in place: a title, the words or a checklist, Close and Save.
// The draft is kept on every edit, so Close, a reload or a crash never costs
// the words. Escape closes, Ctrl+Enter saves. A saved note goes the one way a
// quick note goes (`createNoteSafely`, held offline; `announceSavedNote`).
// A to-do is the checklist markdown the notes list already draws (`- [ ] x`).

const CAPTURE_DRAFT_KEY = "captureCardDraft";
const CAPTURE_TASK_LINE = /^\s*(?:[-*+]\s+(?:\[[ xX]\]\s+)?)?/;

const captureCard = { root: null, returning: false, saving: false, mode: "note", colour: null, due: null, pictures: [], suggestTimer: 0, suggestSeq: 0, sketchHost: null };

function captureCardEl(tag, className, attrs = {}) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  for (const [name, value] of Object.entries(attrs)) node.setAttribute(name, value);
  return node;
}

function captureCardButton(className, label, icon, field) {
  const button = captureCardEl("button", className, { type: "button", "data-cc": field, title: label, "aria-label": label });
  button.append(captureCardEl("i", `ph ${icon}`, { "aria-hidden": "true" }));
  return button;
}

function captureCardField(name) {
  return captureCard.root.querySelector(`[data-cc="${name}"]`);
}

function captureCardStatus(text, isError = false) {
  const status = captureCardField("status");
  status.textContent = text;
  status.classList.toggle("error", isError);
}

function captureModeSeg() {
  const seg = captureCardEl("div", "seg capture-card-modes", { role: "group", "aria-label": "Kind of note" });
  for (const [mode, label] of [["note", "Note"], ["todo", "To-do"]]) {
    const button = captureCardEl("button", "", { type: "button", "data-mode": mode, "aria-pressed": "false" });
    button.textContent = label;
    seg.append(button);
  }
  return seg;
}

function captureCardHead() {
  const head = captureCardEl("div", "capture-card-head");
  head.append(
    captureCardEl("input", "capture-card-title", { type: "text", maxlength: "200", placeholder: "Title", "aria-label": "Title", autocomplete: "off", "data-cc": "title" }),
    captureCardEl("span", "capture-card-bell", { "data-cc": "bell" }),
  );
  return head;
}

function buildCaptureCard() {
  const root = captureCardEl("div", "capture-card", { id: "capture-card", role: "group", "aria-label": "New note", hidden: "" });
  const composer = captureCardEl("div", "note-composer");
  composer.append(
    captureCardHead(),
    captureCardEl("textarea", "capture-card-body", { rows: "3", placeholder: "Take a note…", "aria-label": "Note", "data-cc": "body" }),
    captureItemsBox(),
    captureCardEl("input", "capture-card-tags", { type: "text", placeholder: "#tag1 #tag2", "aria-label": "Tags", autocomplete: "off", "data-cc": "tags" }),
  );
  const status = captureCardEl("p", "status capture-card-status", { role: "status", "data-cc": "status" });
  const foot = captureCardEl("div", "capture-card-foot");
  const close = captureCardEl("button", "ghost small", { type: "button", "data-cc": "close", title: "Close (Esc)" });
  close.textContent = "Close";
  const save = captureCardEl("button", "accent small", { type: "button", "data-cc": "save", title: "Save (Ctrl+Enter)" });
  save.textContent = "Save";
  foot.append(captureModeSeg(), captureCardEl("span", "capture-card-spacer"), close, save);
  root.append(
    composer,
    captureCardEl("div", "recent hidden", { "data-cc": "suggest", "aria-live": "polite" }),
    captureCardEl("div", "capture-card-colours", { "data-cc": "colours" }),
    status,
    foot,
  );
  captureCard.root = root;
  $("capture-bar").append(root);
  wireCaptureCard();
}

function wireCaptureCard() {
  const root = captureCard.root;
  root.addEventListener("input", () => {
    keepCaptureDraft();
    if (captureCardField("status").classList.contains("error")) captureCardStatus("");
  });
  root.addEventListener("keydown", captureCardKeys);
  root.addEventListener("click", (event) => {
    const mode = event.target.closest(".capture-card-modes button")?.dataset.mode;
    if (mode) setCaptureMode(mode);
  });
  captureCardField("close").addEventListener("click", closeCaptureCard);
  captureCardField("save").addEventListener("click", saveCaptureCard);
  //: The bar keeps the focus after Close: Enter on it opens the card again.
  $("capture-bar-input").addEventListener("keydown", (event) => {
    if (event.key === "Enter") openCaptureCard(event.target);
  });
}

function captureCardKeys(event) {
  if (event.key === "Escape") {
    event.preventDefault();
    event.stopPropagation();
    closeCaptureCard();
  } else if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
    event.preventDefault();
    saveCaptureCard();
  }
}

// --- To-do rows --------------------------------------------------------------

function captureItemsBox() {
  const box = captureCardEl("div", "capture-card-items", { "data-cc": "items", hidden: "" });
  const add = captureCardEl("button", "ghost small capture-card-add", { type: "button", "data-cc": "add" });
  add.append(captureCardEl("i", "ph ph-plus ph-lead", { "aria-hidden": "true" }), "Add");
  add.addEventListener("click", () => addCaptureItem("", null));
  box.append(captureCardEl("div", "capture-card-rows", { "data-cc": "rows" }), add);
  return box;
}

function captureItemRow(text) {
  const row = captureCardEl("div", "capture-card-item");
  const grip = captureCardButton("ghost icon-only small capture-card-grip", "Move this item (drag, or Alt+Up and Alt+Down)", "ph-dots-six-vertical", "grip");
  const field = captureCardEl("input", "capture-card-item-text", { type: "text", placeholder: "Item", "aria-label": "Item", autocomplete: "off" });
  field.value = text;
  field.addEventListener("keydown", captureItemKeys);
  const remove = captureCardButton("ghost icon-only small", "Remove this item", "ph-x", "remove");
  remove.addEventListener("click", () => removeCaptureItem(row));
  grip.addEventListener("pointerdown", (event) => captureGripDrag(event, row));
  row.append(grip, field, remove);
  return row;
}

//: A row after `after` (or at the end), focused unless it is a restore.
function addCaptureItem(text, after, focus = true) {
  const rows = captureCardField("rows");
  const row = captureItemRow(text);
  rows.insertBefore(row, after ? after.nextSibling : null);
  if (focus) row.querySelector("input").focus();
  return row;
}

function removeCaptureItem(row) {
  const rows = captureCardField("rows");
  const neighbour = row.previousElementSibling || row.nextElementSibling;
  if (rows.children.length > 1) row.remove();
  else row.querySelector("input").value = "";
  (neighbour || rows.firstElementChild)?.querySelector("input")?.focus();
  keepCaptureDraft();
}

function moveCaptureItem(row, step) {
  const sibling = step < 0 ? row.previousElementSibling : row.nextElementSibling;
  if (!sibling) return;
  row.parentElement.insertBefore(row, step < 0 ? sibling : sibling.nextSibling);
  row.querySelector("input").focus();
  keepCaptureDraft();
}

function captureItemKeys(event) {
  const row = event.target.closest(".capture-card-item");
  if (event.altKey && (event.key === "ArrowUp" || event.key === "ArrowDown")) {
    event.preventDefault();
    moveCaptureItem(row, event.key === "ArrowUp" ? -1 : 1);
  } else if (event.key === "Enter" && !event.ctrlKey && !event.metaKey) {
    event.preventDefault();
    addCaptureItem("", row);
  } else if (event.key === "Backspace" && !event.target.value) {
    event.preventDefault();
    removeCaptureItem(row);
  }
}

//: Dragging by the grip: the row follows the pointer by swapping with the row
//: it is over, so the order on screen is the order that saves.
function captureGripDrag(event, row) {
  event.preventDefault();
  const list = row.parentElement;
  const move = (pointer) => {
    const over = [...list.children].find((other) => {
      const box = other.getBoundingClientRect();
      return other !== row && pointer.clientY >= box.top && pointer.clientY <= box.bottom;
    });
    if (!over) return;
    const below = over.compareDocumentPosition(row) & Node.DOCUMENT_POSITION_FOLLOWING;
    list.insertBefore(row, below ? over : over.nextSibling);
  };
  const stop = () => {
    window.removeEventListener("pointermove", move);
    window.removeEventListener("pointerup", stop);
    window.removeEventListener("pointercancel", stop);
    row.classList.remove("is-dragging");
    keepCaptureDraft();
  };
  row.classList.add("is-dragging");
  window.addEventListener("pointermove", move);
  window.addEventListener("pointerup", stop);
  window.addEventListener("pointercancel", stop);
}

// --- The two modes -----------------------------------------------------------

function captureLinesToItems(text) {
  return text.split("\n").map((line) => line.replace(CAPTURE_TASK_LINE, "").trim()).filter(Boolean);
}

function captureItemsToLines(items) {
  return items.filter((item) => item.trim()).map((item) => `- [ ] ${item.trim()}`).join("\n");
}

function captureCardItems() {
  return [...captureCardField("rows").querySelectorAll("input")].map((input) => input.value);
}

function fillCaptureItems(items) {
  const rows = captureCardField("rows");
  rows.replaceChildren();
  for (const text of items.length ? items : [""]) addCaptureItem(text, null, false);
}

//: Switching carries the words over: the body's lines become items, and the
//: items become checklist lines in the body, so neither way loses anything.
function setCaptureMode(mode, focus = true) {
  const next = mode === "todo" ? "todo" : "note";
  const body = captureCardField("body");
  if (next !== captureCard.mode) {
    if (next === "todo") fillCaptureItems(captureLinesToItems(body.value));
    else body.value = [body.value.trim(), captureItemsToLines(captureCardItems())].filter(Boolean).join("\n");
  }
  captureCard.mode = next;
  body.hidden = next === "todo";
  captureCardField("items").hidden = next !== "todo";
  for (const button of captureCard.root.querySelectorAll(".capture-card-modes [data-mode]")) {
    button.setAttribute("aria-pressed", String(button.dataset.mode === next));
  }
  keepCaptureDraft();
  if (focus) focusCaptureCard();
}

function focusCaptureCard() {
  if (captureCard.mode === "todo") {
    const inputs = [...captureCardField("rows").querySelectorAll("input")];
    (inputs.find((input) => !input.value) || inputs.at(-1))?.focus();
    return;
  }
  const body = captureCardField("body");
  body.focus();
  body.setSelectionRange(body.value.length, body.value.length);
}

// --- The draft ---------------------------------------------------------------

function captureCardDraft() {
  return {
    title: captureCardField("title").value,
    body: captureCardField("body").value,
    mode: captureCard.mode,
    items: captureCardItems(),
    tags: captureCardField("tags").value,
    colour: captureCard.colour,
    due: captureCard.due,
  };
}

function keepCaptureDraft() {
  const draft = captureCardDraft();
  const words = draft.title.trim() || draft.body.trim() || draft.tags.trim() || draft.items.some((item) => item.trim());
  if (words) prefs.set(CAPTURE_DRAFT_KEY, JSON.stringify(draft));
  else prefs.remove(CAPTURE_DRAFT_KEY);
}

function restoreCaptureDraft() {
  const draft = prefs.json(CAPTURE_DRAFT_KEY, {});
  captureCardField("title").value = typeof draft.title === "string" ? draft.title : "";
  captureCardField("body").value = typeof draft.body === "string" ? draft.body : "";
  captureCardField("tags").value = typeof draft.tags === "string" ? draft.tags : "";
  fillCaptureItems(Array.isArray(draft.items) ? draft.items.filter((item) => typeof item === "string") : []);
  captureCard.mode = draft.mode === "todo" ? "todo" : "note";
  captureCard.colour = typeof draft.colour === "string" ? draft.colour : null;
  captureCard.due = typeof draft.due === "string" ? draft.due : null;
  const restored = Boolean(draft.title || draft.body || draft.tags || draft.items?.some?.((item) => item));
  captureCardStatus(restored ? "Your unsaved words are back." : "");
  return restored;
}

//: Called by the bar's first focus (notes-list.js) with the field that took it
//: and the event's type: a click on the bar's picture button opens the picker
//: too, even when the press's focus has already opened the card.
function openCaptureCard(from, type) {
  //: Closing hands the focus back to the bar, whose focusin would reopen the card.
  if (captureCard.returning) return;
  if (!captureCard.root) buildCaptureCard();
  if (captureCard.root.hidden) showCaptureCard(from);
  const pick = type === "click" && Boolean(from?.closest?.("#capture-bar-picture"));
  //: The colour dots, the bell, the pictures and the tag suggestions are the second lazy file.
  lazyScript("/js/capture-card-more.js").then((ok) => ok && mountCaptureExtras(pick));
}

function showCaptureCard(from) {
  const typed = from?.id === "capture-bar-input" ? from.value : "";
  const restored = restoreCaptureDraft();
  const body = captureCardField("body");
  if (typed) body.value = restored ? `${body.value}\n${typed}` : typed;
  if (from?.id === "capture-bar-input") from.value = "";
  captureCard.root.hidden = false;
  $("capture-bar").classList.add("is-open");
  setCaptureMode(from?.closest?.(".capture-bar-modes button")?.dataset.mode || captureCard.mode);
}

function closeCaptureCard() {
  keepCaptureDraft();
  captureCard.root.hidden = true;
  $("capture-bar").classList.remove("is-open");
  captureCard.returning = true;
  $("capture-bar-input").focus({ preventScroll: true });
  setTimeout(() => {
    captureCard.returning = false;
  }, 0);
}

function resetCaptureCard() {
  for (const picture of captureCard.pictures) URL.revokeObjectURL(picture.preview);
  captureCard.pictures = [];
  if (captureCard.root.dataset.extras) renderCaptureThumbs();
  captureCardField("title").value = "";
  captureCardField("body").value = "";
  fillCaptureItems([]);
  captureCardField("tags").value = "";
  captureCard.colour = null;
  captureCard.due = null;
  prefs.remove(CAPTURE_DRAFT_KEY);
  captureCardStatus("");
}

//: What a save sends: the title as the leading heading, then the words or the
//: checklist lines. "" when there is nothing to save.
function captureCardContent() {
  const draft = captureCardDraft();
  const words = draft.mode === "todo" ? captureItemsToLines(draft.items) : draft.body.trim();
  return withTitle(words, draft.title).trim();
}

async function saveCaptureCard() {
  if (captureCard.saving) return;
  const text = captureCardContent();
  if (!text && !captureCard.pictures.length) {
    captureCardStatus("Write something first, then save.", true);
    return;
  }
  captureCard.saving = true;
  const button = captureCardField("save");
  button.disabled = true;
  captureCardStatus("Saving…");
  try {
    await ensureModule("quickNote");
    const draft = captureCardDraft();
    const pictures = captureCard.pictures.length ? await uploadCapturePictures() : "";
    const body = { content: [text, pictures].filter(Boolean).join("\n\n"), tags: captureTagList(draft.tags) };
    if (draft.colour) body.colour = draft.colour;
    const result = await createNoteSafely(body);
    await finishCaptureSave(result, draft);
  } catch (error) {
    //: Refused or failed and not held: the words stay, with the reason under them.
    captureCardStatus(error.message, true);
  } finally {
    captureCard.saving = false;
    button.disabled = false;
  }
}

//: What follows a save that was answered: the reminder the bell set goes on
//: the saved note (a held note has no id yet, so it says so), then the card
//: is emptied and closed.
async function finishCaptureSave(result, draft) {
  resetCaptureCard();
  closeCaptureCard();
  if (captureCard.root.dataset.extras) syncCaptureExtras();
  if (result.queued) {
    toast(`Saved on this device. It goes into your notebook as soon as the server answers.${draft.due ? " Its reminder was not set: add it once the note is in." : ""}`);
    return;
  }
  const slots = draft.due ? { title: draft.title.trim() || captureReminderText(draft), due: new Date(draft.due), recurring: "none" } : null;
  announceSavedNote(result.saved, slots ? await quickNoteReminder(result.saved.id, slots) : "");
}

function captureReminderText(draft) {
  const first = (draft.mode === "todo" ? captureLinesToItems(captureItemsToLines(draft.items)) : captureLinesToItems(draft.body))[0];
  return first || "Note";
}

//: "#a #b, c" is three tags: split on spaces and commas, the hash is optional.
function captureTagList(text) {
  return [...new Set(text.split(/[\s,]+/).map((tag) => tag.replace(/^#+/, "").trim()).filter(Boolean))];
}
