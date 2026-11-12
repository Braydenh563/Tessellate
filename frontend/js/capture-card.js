// The Notes tab's capture card (INBOX 1479). The bar above the list is one line
// in index.html; its first focus fetches this file (notes-list.js), which
// opens the card in place: a title, the words or a checklist, Close and Save.
// The draft is kept on every edit, so Close, a reload or a crash never costs
// the words. Escape closes, Ctrl+Enter saves. A saved note goes the one way a
// quick note goes (`createNoteSafely`, held offline; `announceSavedNote`).
// A to-do is the checklist markdown the notes list already draws (`- [ ] x`).

(() => {
  const CAPTURE_DRAFT_KEY = "captureCardDraft";
  const CAPTURE_TASK_LINE = /^\s*(?:[-*+]\s+(?:\[[ xX]\]\s+)?)?/;

  const captureCard = { root: null, host: null, returning: false, saving: false, mode: "note", colour: null, due: null, pictures: [], files: [], made: null, discardOnClose: false, suggestTimer: 0, suggestSeq: 0, sketchHost: null, buddyTimer: 0 };


  //: **One card, two bars** (INBOX 1592): methods on the state, not more globals. `place` moves the card
  //: into `host`. Open in the other bar, it closes there first (its words are kept in the draft and come
  //: back when it shows here); a bar the dashboard threw away on a redraw leaves the card detached, and it
  //: is shut the same way.
  captureCard.place = (host) => {
    if (captureCard.host === host && captureCard.root.parentElement === host) return;
    if (!captureCard.root.hidden) {
      keepCaptureDraft();
      captureCard.root.hidden = true;
    }
    captureCard.host?.classList.remove("is-open");
    captureCard.host = host;
    host.append(captureCard.root);
  };

  //: A dashboard redraw while the card is open: the new bar (`captureBar`, notes-list.js) takes it over and
  //: shows it as it was, so a refresh never closes what you are typing in.
  captureCard.adopt = (host) => {
    if (!captureCard.root || captureCard.root.hidden || captureCard.root.isConnected) return;
    captureCard.place(host);
    captureCard.root.hidden = false;
    host.classList.add("is-open");
    restoreCaptureDraft();
    setCaptureMode(captureCard.mode, false);
  };

  //: **Atlas is never left over the card's controls** (INBOX 1592). Its check steps it aside once a control
  //: is under it, but only when asked, and the page observer asks for nothing: the card changes its box
  //: when it opens, closes, changes kind, and when the colours, the bell, the picture strip or the tag
  //: suggestions arrive, so each calls this. Once the layout has settled (a burst is one look) the card is
  //: brought fully into view (a dashboard card low on the page had its Save under the status bar: 840 to
  //: 872 in a scroller ending at 865), then the companion is told (`mm:controls-changed`, avatars.js).
  captureCard.settle = () => {
    clearTimeout(captureCard.buddyTimer);
    captureCard.buddyTimer = setTimeout(() => {
      const root = captureCard.root;
      if (!root.hidden && root.contains(document.activeElement)) root.scrollIntoView({ block: "nearest" });
      document.dispatchEvent(new Event("mm:controls-changed"));
    }, 200);
  };

  //: **The lock** (INBOX 1695 a): this one note private. It starts as Settings' "New notes start
  //: private" says, and a save sends `private` only when it differs, so null still follows Settings.
  //: Built with the extras (`mountCaptureExtras`), into the foot before Close.
  //: The two calls are quick-note.js's `createNoteSafely.lock` (`mountLock` loads that file; the desk shell has no toggle).
  captureCard.lockSync = (on) => captureCardField("private") && createNoteSafely.lock.sync(captureCardField("private"), on);
  captureCard.lockAsk = () => (captureCardField("private") ? createNoteSafely.lock.ask(captureCardField("private")) : {});

  captureCard.mountLock = async () => {
    if (captureCardField("private")) return;
    await ensureModule("quickNote");
    const button = captureCardEl("button", "ghost small lock-toggle", { type: "button", "data-cc": "private", "aria-pressed": "false" });
    button.append(captureCardEl("i", "ph ph-lock-open ph-lead", { "aria-hidden": "true" }), " ", captureCardEl("span", "lock-toggle-label"));
    button.addEventListener("click", () => createNoteSafely.lock.flip(button, "captureCardPrivate"));
    captureCardField("close").before(button);
    //: The card's draft keeps the lock too (a reload puts it back).
    captureCard.lockSync(prefs.has("captureCardPrivate") ? prefs.get("captureCardPrivate") === "true" : undefined);
  };

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

  function buildCaptureCard() {
    const root = captureCardEl("div", "capture-card", { id: "capture-card", role: "group", "aria-label": "New note", hidden: "" });
    const composer = captureCardEl("div", "note-composer");
    //: The title and the bell share a row.
    const head = captureCardEl("div", "capture-card-head");
    head.append(
      captureCardEl("input", "capture-card-title", { type: "text", maxlength: "200", placeholder: "Title", "aria-label": "Title", autocomplete: "off", "data-cc": "title" }),
      captureCardEl("span", "capture-card-bell", { "data-cc": "bell" }),
    );
    composer.append(
      head,
      captureCardEl("textarea", "capture-card-body", { id: "capture-card-body", rows: "3", placeholder: "Take a note…", "aria-label": "Note", "data-cc": "body", "data-autocorrect": "" }),
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
      button.classList.toggle("active", button.dataset.mode === next);
    }
    keepCaptureDraft();
    if (focus) focusCaptureCard();
    captureCard.settle();
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

  //: Called by a bar's first focus (notes-list.js `captureBar`) with the field
  //: that took it and the event's type: a click on the bar's picture button opens
  //: the picker too, even when the press's focus has already opened the card.
  //: One card, two bars (the Notes tab's and the dashboard's Quick capture): the
  //: card moves into the bar that was used, and the draft is the one draft.
  function openCaptureCard(from, type) {
    //: Closing hands the focus back to the bar, whose focusin would reopen the card.
    if (captureCard.returning) return;
    const host = from?.closest?.(".capture-bar");
    if (!host) return;
    if (!captureCard.root) buildCaptureCard();
    captureCard.place(host);
    if (captureCard.root.hidden) showCaptureCard(from);
    const pick = type === "click" && Boolean(from?.closest?.(".capture-bar-picture"));
    //: Pictures and files waiting for Save are the first lazy file (the desk's window has it too);
    //: the colour dots, the bell, Draw and the tag suggestions are the second (the app's alone).
    Promise.all([lazyScript("/js/attach-accept.js"), lazyScript("/js/capture-stage.js")]).then((ok) => ok.every(Boolean) && mountCaptureStage(pick));
    lazyScript("/js/capture-card-more.js").then((ok) => ok && mountCaptureExtras());
  }

  function showCaptureCard(from) {
    const typedInto = from?.classList?.contains("capture-bar-input");
    const typed = typedInto ? from.value : "";
    const restored = restoreCaptureDraft();
    const body = captureCardField("body");
    if (typed) body.value = restored ? `${body.value}\n${typed}` : typed;
    if (typedInto) from.value = "";
    captureCard.root.hidden = false;
    captureCard.host.classList.add("is-open");
    //: A bar's To-do icon opens the card as a list; anything else keeps the mode the draft was in.
    setCaptureMode(from?.closest?.(".capture-bar-todo") ? "todo" : captureCard.mode);
  }

  function closeCaptureCard() {
    //: The desk's note is a window that rests when it closes: what it held back goes with it.
    if (captureCard.discardOnClose && captureCard.root.dataset.stage) discardCaptureStage();
    keepCaptureDraft();
    captureCard.root.hidden = true;
    captureCard.host.classList.remove("is-open");
    captureCard.returning = true;
    captureCard.host.querySelector(".capture-bar-input")?.focus({ preventScroll: true });
    setTimeout(() => {
      captureCard.returning = false;
    }, 0);
    captureCard.settle();
  }

  function resetCaptureCard() {
    if (captureCard.root.dataset.stage) discardCaptureStage();
    else captureCard.pictures = [];
    captureCardField("save").textContent = "Save";
    captureCardField("title").value = "";
    captureCardField("body").value = "";
    fillCaptureItems([]);
    captureCardField("tags").value = "";
    captureCard.colour = null;
    captureCard.due = null;
    prefs.remove("captureCardPrivate");
    captureCard.lockSync();
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
    //: A note made whose files did not all go: Save sends those again, it never writes a second note.
    if (captureCard.made) return retryCaptureFiles();
    const text = captureCardContent();
    const held = captureCard.pictures.length + captureCard.files.length;
    if (!text && !held) {
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
      //: A note of files alone is named by them: a note cannot be empty.
      const names = captureCard.files.map((file) => file.name).join(", ");
      const body = { content: [text, pictures].filter(Boolean).join("\n\n") || names, tags: captureTagList(draft.tags) };
      if (draft.colour) body.colour = draft.colour;
      Object.assign(body, captureCard.lockAsk());
      //: Files need the note's id, so a note with files is not held for later: it fails whole and stays staged.
      const result = await createNoteSafely(body, { online: captureCard.files.length > 0 });
      if (result.saved && captureCard.files.length) {
        captureCard.made = { result, draft };
        return await retryCaptureFiles();
      }
      await finishCaptureSave(result, draft);
    } catch (error) {
      //: Refused or failed and not held: the words and what was staged stay, with the reason under them.
      captureCardStatus(`${error.message} Press Save to try again.`, true);
      button.textContent = "Try again";
    } finally {
      captureCard.saving = false;
      button.disabled = false;
    }
  }

  //: The files of a note that now has an id. Whatever fails stays staged under a Try again.
  async function retryCaptureFiles() {
    const { result, draft } = captureCard.made;
    captureCard.saving = true;
    const button = captureCardField("save");
    button.disabled = true;
    captureCardStatus("Attaching files…");
    try {
      const { failed, entry } = await attachCaptureFiles(result.saved.id);
      if (entry) result.saved = entry;
      if (failed.length) {
        captureCardStatus(`Saved the note, but ${failed.length === 1 ? "a file" : `${failed.length} files`} did not attach (${failed.join("; ")}). Press Save to try again.`, true);
        button.textContent = "Try again";
        return;
      }
      captureCard.made = null;
      await finishCaptureSave(result, draft);
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
    //: The arguments run before announceSavedNote's stand-in can fetch quick-note.js, so the reminder's own file is awaited here.
    const reminder = slots && (await ensureModule("quickNote")) ? await quickNoteReminder(result.saved.id, slots) : "";
    announceSavedNote(result.saved, reminder);
  }

  function captureReminderText(draft) {
    const first = (draft.mode === "todo" ? captureLinesToItems(captureItemsToLines(draft.items)) : captureLinesToItems(draft.body))[0];
    return first || "Note";
  }

  //: "#a #b, c" is three tags: split on spaces and commas, the hash is optional.
  function captureTagList(text) {
    return [...new Set(text.split(/[\s,]+/).map((tag) => tag.replace(/^#+/, "").trim()).filter(Boolean))];
  }

  Object.assign(window, { captureCard, captureCardButton, captureCardDraft, captureCardEl, captureCardField, captureCardStatus, captureItemsToLines, captureTagList, focusCaptureCard, keepCaptureDraft, openCaptureCard });
})();
