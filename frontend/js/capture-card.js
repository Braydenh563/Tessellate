// The Notes tab's capture card (INBOX 1479). The bar above the list is one line
// in index.html; its first focus fetches this file (notes-list.js), which
// opens the card in place: a title, the words, Close and Save. The draft is
// kept on every edit, so Close, a reload or a crash never costs the words.
// Escape closes, Ctrl+Enter saves. A saved note goes the one way a quick note
// goes (`createNoteSafely`, held offline; `announceSavedNote`).

const CAPTURE_DRAFT_KEY = "captureCardDraft";

const captureCard = { root: null, returning: false, saving: false };

function captureCardEl(tag, className, attrs = {}) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  for (const [name, value] of Object.entries(attrs)) node.setAttribute(name, value);
  return node;
}

function captureCardField(name) {
  return captureCard.root.querySelector(`[data-cc="${name}"]`);
}

function captureCardStatus(text, isError = false) {
  const status = captureCardField("status");
  status.textContent = text;
  status.classList.toggle("error", isError);
}

function buildCaptureCard() {
  const root = captureCardEl("div", "capture-card", { id: "capture-card", role: "group", "aria-label": "New note", hidden: "" });
  const composer = captureCardEl("div", "note-composer");
  composer.append(
    captureCardEl("input", "capture-card-title", { type: "text", maxlength: "200", placeholder: "Title", "aria-label": "Title", autocomplete: "off", "data-cc": "title" }),
    captureCardEl("textarea", "capture-card-body", { rows: "3", placeholder: "Take a note…", "aria-label": "Note", "data-cc": "body" }),
  );
  const status = captureCardEl("p", "status capture-card-status", { role: "status", "data-cc": "status" });
  const foot = captureCardEl("div", "capture-card-foot");
  const close = captureCardEl("button", "ghost small", { type: "button", "data-cc": "close", title: "Close (Esc)" });
  close.textContent = "Close";
  const save = captureCardEl("button", "accent small", { type: "button", "data-cc": "save", title: "Save (Ctrl+Enter)" });
  save.textContent = "Save";
  foot.append(captureCardEl("span", "capture-card-spacer"), close, save);
  root.append(composer, status, foot);
  captureCard.root = root;
  $("capture-bar").append(root);
  wireCaptureCard();
  //: The bar keeps the focus after Close: Enter on it opens the card again.
  $("capture-bar-input").addEventListener("keydown", (event) => {
    if (event.key === "Enter") openCaptureCard(event.target);
  });
}

function wireCaptureCard() {
  const root = captureCard.root;
  root.addEventListener("input", () => {
    keepCaptureDraft();
    if (captureCardField("status").classList.contains("error")) captureCardStatus("");
  });
  root.addEventListener("keydown", captureCardKeys);
  captureCardField("close").addEventListener("click", closeCaptureCard);
  captureCardField("save").addEventListener("click", saveCaptureCard);
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

function captureCardDraft() {
  return { title: captureCardField("title").value, body: captureCardField("body").value };
}

function keepCaptureDraft() {
  const draft = captureCardDraft();
  if (draft.title.trim() || draft.body.trim()) prefs.set(CAPTURE_DRAFT_KEY, JSON.stringify(draft));
  else prefs.remove(CAPTURE_DRAFT_KEY);
}

function restoreCaptureDraft() {
  const draft = prefs.json(CAPTURE_DRAFT_KEY, {});
  captureCardField("title").value = typeof draft.title === "string" ? draft.title : "";
  captureCardField("body").value = typeof draft.body === "string" ? draft.body : "";
  const restored = Boolean(draft.title || draft.body);
  captureCardStatus(restored ? "Your unsaved words are back." : "");
  return restored;
}

//: Called by the bar's first focus (notes-list.js) with the field that took it.
function openCaptureCard(from) {
  //: Closing hands the focus back to the bar, whose focusin would reopen the card.
  if (captureCard.returning) return;
  const bar = $("capture-bar");
  if (!captureCard.root) buildCaptureCard();
  const typed = from?.id === "capture-bar-input" ? from.value : "";
  if (!captureCard.root.hidden) return;
  const restored = restoreCaptureDraft();
  const body = captureCardField("body");
  if (typed) body.value = restored ? `${body.value}\n${typed}` : typed;
  if (from?.id === "capture-bar-input") from.value = "";
  captureCard.root.hidden = false;
  bar.classList.add("is-open");
  keepCaptureDraft();
  body.focus();
  body.setSelectionRange(body.value.length, body.value.length);
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
  captureCardField("title").value = "";
  captureCardField("body").value = "";
  prefs.remove(CAPTURE_DRAFT_KEY);
  captureCardStatus("");
}

async function saveCaptureCard() {
  if (captureCard.saving) return;
  const draft = captureCardDraft();
  const content = withTitle(draft.body.trim(), draft.title).trim();
  if (!content) {
    captureCardStatus("Write something first, then save.", true);
    return;
  }
  captureCard.saving = true;
  const button = captureCardField("save");
  button.disabled = true;
  captureCardStatus("Saving…");
  try {
    await ensureModule("quickNote");
    const result = await createNoteSafely({ content });
    resetCaptureCard();
    closeCaptureCard();
    if (result.queued) toast("Saved on this device. It goes into your notebook as soon as the server answers.");
    else announceSavedNote(result.saved);
  } catch (error) {
    //: Refused or failed and not held: the words stay, with the reason under them.
    captureCardStatus(error.message, true);
  } finally {
    captureCard.saving = false;
    button.disabled = false;
  }
}
