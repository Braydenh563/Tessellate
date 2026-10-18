// quick-note.js: Quick note, and the outbox every note box shares (INBOX 434,
// the owner: "make the note filing and how the user can make notes the
// fastest, most reliable and easiest thing to use the user has ever seen").
//
// A lazy piece (app.js `LAZY_MODULES.quickNote`), fetched a few seconds after
// boot rather than on first use, and that timing is load-bearing: the outbox
// is for the moment the server has gone away, which is exactly when a script
// can no longer be fetched. Boot code reaches it through
// `LAZY_ENTRY_POINTS`, so a call made before it arrives loads it.
//
// Two things live here:
//
// 1. **The outbox.** A note saved while the server is not answering (the
//    fetch itself threw) is kept in this browser's storage and sent again on
//    `noteServerUp` (status.js), every fifteen seconds while any waits, and
//    when this file loads. Before: the composer said "Failed to fetch" and
//    nothing ever sent it. Each note carries a `client_key`, so a resend of a
//    save whose answer was lost is answered with the first note
//    (routes_entries.py `_already_delivered`), not a second copy.
// 2. **Quick note.** Alt+N (or the palette) opens a small dialog that saves
//    without leaving the page. Ctrl+Enter saves, `#word` tags, Escape closes
//    and keeps the words, "Open in Capture" carries them to the full
//    composer. A plain textarea, not the live editor: that arrives with the
//    Library bundle (1.7 MB), and a popup whose point is speed must not wait.

const NOTE_OUTBOX_KEY = "noteOutbox";
const QUICK_NOTE_DRAFT_KEY = "quickNoteDraft";
const NOTE_OUTBOX_RETRY_MS = 15000;

function noteOutbox() {
  try {
    const list = prefs.json(NOTE_OUTBOX_KEY, []);
    return Array.isArray(list) ? list : [];
  } catch {
    return [];
  }
}

//: Answers whether the list was written: a full or blocked storage is the
//: one case the outbox cannot help, and the caller then keeps the words on
//: screen instead of clearing them.
function writeNoteOutbox(list) {
  if (list.length) {
    if (!prefs.set(NOTE_OUTBOX_KEY, JSON.stringify(list))) return false;
  } else prefs.remove(NOTE_OUTBOX_KEY);
  renderNoteOutbox();
  renderPendingNoteRows();
  return true;
}

function newNoteClientKey() {
  return `n-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

//: The server is gone, rather than answering no: `fetch` itself threw.
function noteServerGone(error) {
  return error instanceof TypeError;
}

//: Hold a note for later. Answers whether it is held.
function noteOutboxAdd(body) {
  const list = noteOutbox();
  list.push({ ...body, client_key: body.client_key || newNoteClientKey(), queued_at: Date.now() });
  const held = writeNoteOutbox(list);
  scheduleNoteOutboxFlush();
  return held;
}

//: Save a note, or hold it when the server is gone. Answers `{ saved }` or
//: `{ queued: true }`; a refusal (a 4xx, a 5xx) is thrown as it would be.
async function createNoteSafely(body) {
  const payload = { defer_filing: true, inline_tags: true, ...body };
  payload.client_key = payload.client_key || newNoteClientKey();
  try {
    return { saved: await apiJson("/entries", { method: "POST", body: JSON.stringify(payload) }) };
  } catch (error) {
    if (!noteServerGone(error) || !noteOutboxAdd(payload)) throw error;
    return { queued: true };
  }
}

let noteOutboxTimer = 0;
let noteOutboxFlushing = null;

function scheduleNoteOutboxFlush() {
  clearTimeout(noteOutboxTimer);
  if (noteOutbox().length) noteOutboxTimer = setTimeout(flushNoteOutbox, NOTE_OUTBOX_RETRY_MS);
}

//: Send every held note, oldest first. Stops at the first sign the server is
//: still gone (or the notebook is locked) and tries again later; one at a
//: time, so a resend can never race itself.
function flushNoteOutbox() {
  if (noteOutboxFlushing) return noteOutboxFlushing;
  if (!noteOutbox().length || !authToken()) return Promise.resolve(0);
  noteOutboxFlushing = (async () => {
    let sent = 0;
    for (const item of noteOutbox()) {
      const { queued_at: _queuedAt, ...payload } = item;
      try {
        const saved = await apiJson("/entries", { method: "POST", body: JSON.stringify(payload), silent: true });
        writeNoteOutbox(noteOutbox().filter((held) => held.client_key !== item.client_key));
        sent += 1;
        pushEntryCreateUndo(saved, "Saved a note kept on this device");
        if (saved.filing_state === "pending") watchFiling(saved, { quiet: true });
      } catch (error) {
        if (noteServerGone(error) || error.isLockout || !error.status || error.status >= 500 || error.status === 429) break;
        //: Answered and refused (a note over the size cap, say): resending
        //: would be refused forever, so the words go back where they can be
        //: fixed, Capture's box, after anything already in it.
        writeNoteOutbox(noteOutbox().filter((held) => held.client_key !== item.client_key));
        returnNoteToCapture(payload.content, error.message);
      }
    }
    if (sent) {
      toast(sent === 1 ? "The note kept on this device is in your notebook now." : `The ${sent} notes kept on this device are in your notebook now.`);
      loadEntries().catch(() => {});
    }
    return sent;
  })().finally(() => {
    noteOutboxFlushing = null;
    scheduleNoteOutboxFlush();
  });
  return noteOutboxFlushing;
}

function returnNoteToCapture(content, reason) {
  const box = $("entry-content");
  if (!box || !content) return;
  box.value = box.value.trim() ? `${box.value}\n\n${content}` : content;
  box.dispatchEvent(new Event("input", { bubbles: true }));
  toastAction(`A note kept on this device was refused (${reason}). It is back in Capture.`, "Open Capture", () => startNewNote(), { go: { open: "capture" } });
}

//: One notice above the Capture box while anything is held, with a way to
//: try now rather than wait out the timer.
function renderNoteOutbox() {
  const notice = $("note-outbox-notice");
  if (!notice) return;
  const count = noteOutbox().length;
  notice.classList.toggle("hidden", !count);
  if (!count) return;
  const text = notice.querySelector(".note-outbox-text");
  setLabel(
    text,
    `ph:cloud-slash ${count === 1 ? "1 note is" : `${count} notes are`} kept on this device until the server answers.`,
  );
}

//: A held note is a pending row at the top of `#entry-list`, in the note
//: card's shape, with no actions (each needs a server). Redrawn by every
//: outbox write and by `renderEntries`; not under a filter or search (it has
//: no category yet). Inserted, not appended: this may run after the list
//: painted, when the script had to be fetched first.
function renderPendingNoteRows() {
  const list = $("entry-list");
  if (!list) return;
  for (const old of list.querySelectorAll(":scope > li.pending-note")) old.remove();
  const filtered = noteSearch || activeCategory || draftsOnly || favouritesOnly;
  const held = filtered ? [] : noteOutbox();
  if (!held.length) return;
  const rows = document.createDocumentFragment();
  //: Newest first, as the list is.
  for (const item of held.slice().reverse()) {
    const li = document.createElement("li");
    li.className = "pending-note";
    li.dataset.pendingKey = item.client_key;
    //: Capture folds its title in as a leading `# Heading` (`withTitle`); the
    //: saved card shows that line as the title, so the held row does too.
    const [, heading, body] = /^# ([^\n]+)\n*([\s\S]*)$/.exec(item.content || "") || [null, "", item.content || ""];
    if (heading) {
      const title = document.createElement("p");
      title.className = "entry-title";
      title.textContent = heading;
      li.appendChild(title);
    }
    const content = document.createElement("p");
    content.className = "entry-content";
    renderNoteText(content, body, []);
    li.appendChild(content);
    const meta = document.createElement("div");
    meta.className = "entry-meta note-meta";
    const waiting = chip("ph:cloud-slash Waiting to save", "item-label");
    waiting.title = "Kept on this device until the server answers. It is sent on its own.";
    meta.appendChild(waiting);
    for (const tag of item.tags || []) meta.appendChild(chip(tag, "tag hashtag"));
    li.appendChild(meta);
    rows.appendChild(li);
  }
  list.insertBefore(rows, list.firstChild);
  $("empty-message")?.classList.add("hidden");
}

// --- Quick note --------------------------------------------------------------

function quickNoteBox() {
  return $("quick-note-text");
}

function quickNoteStatus(text, error = false) {
  const status = $("quick-note-status");
  status.textContent = text;
  status.classList.toggle("error", error);
}

function openQuickNote() {
  const dialog = $("quick-note");
  if (!dialog) return;
  const box = quickNoteBox();
  if (!dialog.open) {
    let draft = "";
    try {
      draft = prefs.get(QUICK_NOTE_DRAFT_KEY, null) || "";
    } catch {
      draft = "";
    }
    if (!box.value) box.value = draft;
    const held = noteOutbox().length;
    quickNoteStatus(
      held
        ? `${held === 1 ? "1 note is" : `${held} notes are`} waiting for the server on this device.`
        : draft
          ? "Your unsaved words are back."
          : "",
    );
    dialog.showModal();
  }
  //: The chips under the box (quickadd.js): a #tag is saved as a tag; a day
  //: or time is an offer of a reminder on the note, off until pressed,
  //: unless the words begin as a reminder does.
  quickAddAttach(box, "note", { offKinds: ["date", "time", "datetime", "duration", "recurrence"] });
  box.focus();
  box.setSelectionRange(box.value.length, box.value.length);
}

function keepQuickNoteDraft() {
  try {
    const text = quickNoteBox().value;
    if (text.trim()) prefs.set(QUICK_NOTE_DRAFT_KEY, text);
    else prefs.remove(QUICK_NOTE_DRAFT_KEY);
  } catch {
    // Storage blocked: the words are still in the box while it is open.
  }
}

function clearQuickNote() {
  quickNoteBox().value = "";
  quickAddClear(quickNoteBox());
  keepQuickNoteDraft();
}

let quickNoteSaving = false;

async function saveQuickNote() {
  if (quickNoteSaving) return;
  const content = quickNoteBox().value.trim();
  if (!content) {
    quickNoteStatus("Write something first, then save.", true);
    return;
  }
  quickNoteSaving = true;
  const button = $("quick-note-save");
  button.disabled = true;
  quickNoteStatus("Saving…");
  try {
    const slots = await quickAddSlots(quickNoteBox());
    const result = await createNoteSafely({ content, tags: slots?.tags || [] });
    clearQuickNote();
    $("quick-note").close();
    if (result.queued) {
      //: The reminder chip needs the saved note's id, which a held note does
      //: not have yet: said, not dropped without a word.
      toast(`Saved on this device. It goes into your notebook as soon as the server answers.${slots?.due ? " Its reminder was not set: add it once the note is in." : ""}`);
      return;
    }
    const saved = result.saved;
    const reminded = slots?.due ? await quickNoteReminder(saved.id, slots) : "";
    toastAction(
      (saved.filing_state === "pending" ? "Saved. Filing it now." : `Filed under “${saved.category}”.`) + reminded,
      "Go to it",
      () => flashEntry(saved.id),
      { go: { open: "entry", id: saved.id } },
    );
    //: In the list now, not when filing settles: measured, 2 to 4 s later
    //: on every tab but the dashboard when this waited on the watch.
    refreshEntries([saved.id]).catch(() => {});
    if (saved.filing_state === "pending") watchFiling(saved);
    pushUndo(
      "Created a note",
      async () => {
        await api(`/entries/${saved.id}`, { method: "DELETE" });
        await refreshEntries([saved.id]);
      },
      async () => {
        await api(`/entries/${saved.id}/restore`, { method: "POST" });
        await refreshEntries([saved.id]);
      },
    );
  } catch (error) {
    //: Refused or failed and not held: the words stay in the box (and in
    //: storage, from the last keystroke), with the reason under them.
    quickNoteStatus(error.message, true);
  } finally {
    quickNoteSaving = false;
    button.disabled = false;
  }
}

//: The reminder the note's chips said, on the note itself: answers the words
//: the toast adds, empty when the server refused it (the note is kept).
async function quickNoteReminder(entryId, slots) {
  try {
    const text = (slots.title.split("\n")[0] || "Quick note").slice(0, 100);
    const reminder = await apiJson("/reminders", {
      method: "POST",
      body: JSON.stringify({ text, due_at: slots.due.toISOString(), entry_id: entryId, priority: "normal", recurring: slots.recurring || "none" }),
    });
    loadReminders();
    reminderMadeUndo(reminder);
    return ` Reminder set: ${relativeWhen(reminder.due_at)}.`;
  } catch (error) {
    return ` The reminder was not set: ${error.message}`;
  }
}

//: The full composer, for a note that has outgrown the popup: the words move
//: (after anything Capture already holds) and the popup's copy is cleared.
function quickNoteToCapture() {
  const text = quickNoteBox().value;
  $("quick-note").close();
  startNewNote();
  if (!text.trim()) return;
  const box = $("entry-content");
  box.value = box.value.trim() ? `${box.value}\n\n${text}` : text;
  box.dispatchEvent(new Event("input", { bubbles: true }));
  clearQuickNote();
}

// --- A pasted link, offered as the page -------------------------------------
//
// A bare http(s) address pasted into Capture or Quick note stays as typed. When
// the web is allowed (Settings, Web search; off by default, and this app goes
// online for nothing else here) a toast offers to save the page itself as a
// note, its title, its text and its address, through the web clipper
// (`POST /links/clip`, core/webclip.py), which had no door in the interface at
// all. The fetch is made only on that press. With the web off nothing is
// offered, so the toast never promises what the app will then refuse.
const PASTED_LINK = /^https?:\/\/\S+$/i;

async function clipPastedLink(url) {
  const progress = toastProgress("Reading the page…");
  try {
    const note = await apiJson("/links/clip", { method: "POST", body: JSON.stringify({ url }) });
    pushEntryCreateUndo(note, "Clipped a page as a note");
    progress.done(`Saved “${note.source_title || url}” as a note, filing it now.`, {
      actionLabel: "Open",
      onAction: () => flashEntry(note.id),
      go: { open: "entry", id: note.id },
    });
    refreshEntries([note.id]).catch(() => {});
    if (note.filing_state === "pending") watchFiling(note, { quiet: true });
  } catch (error) {
    progress.done(error.message || "Couldn't read that page.", { isError: true });
  }
}

document.addEventListener("paste", (event) => {
  if (!event.target.closest?.("#quick-note, #capture")) return;
  if (!(prefsCache && prefsCache.web_search_enabled)) return;
  const text = (event.clipboardData?.getData("text/plain") || "").trim();
  if (text.length > 2000 || !PASTED_LINK.test(text)) return;
  toastAction("That is a link. Save the page it points to as a note of its own?", "Clip the page", () => clipPastedLink(text));
});

(() => {
  const box = quickNoteBox();
  if (!box) return;
  box.addEventListener("input", () => {
    keepQuickNoteDraft();
    if ($("quick-note-status").classList.contains("error")) quickNoteStatus("");
  });
  box.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && (event.ctrlKey || event.metaKey) && !event.isComposing) {
      event.preventDefault();
      saveQuickNote();
    }
  });
  $("quick-note-save").addEventListener("click", saveQuickNote);
  $("quick-note-more").addEventListener("click", quickNoteToCapture);
  $("quick-note-close").addEventListener("click", () => $("quick-note").close());
  $("note-outbox-retry")?.addEventListener("click", () => flushNoteOutbox());
  //: Back on the network the browser knows about (a laptop's wifi), as well
  //: as the server answering again.
  window.addEventListener("online", () => flushNoteOutbox());
  //: A modal dialog is drawn in the top layer, above the lock screen, so a
  //: lock closes Quick note (its words wait in storage, as Capture's draft
  //: does) rather than leaving them readable over it; an unlock sends
  //: whatever was held while the notebook was locked.
  const lock = $("lock-overlay");
  if (lock) {
    new MutationObserver(() => {
      if (lock.classList.contains("hidden")) flushNoteOutbox();
      else $("quick-note").close();
    }).observe(lock, { attributes: true, attributeFilter: ["class"] });
  }
  renderNoteOutbox();
  flushNoteOutbox();
})();

//: The clipboard's text as a new note, filed by Atlas like any capture
//: (`createNoteSafely`, the quick note's path, so a note pasted while the
//: server is gone waits in the outbox rather than being lost). Undo bins it.
//: Here, not settings-wiring.js, since 2026-10-06: a chord's work, loaded on
//: first use (`LAZY_ENTRY_POINTS.quickNote`), beside the function it calls.
async function pasteClipboardAsNote() {
  let text = "";
  try {
    text = ((await navigator.clipboard.readText()) || "").trim();
  } catch {
    toast("Couldn't read the clipboard here. Paste into Capture instead.", "info");
    return;
  }
  if (!text) return toast("There is no text on the clipboard to save.", "info");
  const result = await createNoteSafely({ content: text }).catch((error) => {
    toast(error.message, true);
    return null;
  });
  if (!result) return;
  if (result.queued) return toast("Saved here; it is sent when the app's server is back.");
  const id = result.saved.id;
  refreshEntries([id]);
  const bin = async () => {
    await apiJson(`/entries/${id}`, { method: "DELETE" });
    refreshEntries([id]);
  };
  const back = async () => {
    await apiJson(`/entries/${id}/restore`, { method: "POST" });
    refreshEntries([id]);
  };
  const action = pushUndo("Pasted a note", bin, back);
  toastAction("Saved what you copied as a new note.", "Undo", async () => {
    settleUndoFromToast(action);
    await bin();
  });
}

//: Moved from chat.js on 2026-10-07 (boot gzip budget): a press's work,
//: loaded on first use (`LAZY_ENTRY_POINTS.quickNote`).

// One-click capture from a chat answer. The text-selection popup's "Save as
// draft note" already reaches chat bubbles, but only for whatever's
// highlighted: this needs no selection at all, so the whole answer is one
// press away instead of a select-then-click.
//: **A conversation, kept as a document.**
//:
//: The transcript already exports as a file (the menu's Export row); this keeps it
//: *inside* the notebook, where it is searchable, linkable and editable like
//: everything else. Titled after the conversation so the Documents list reads
//: as a list of conversations rather than of dated blobs.
async function saveChatAsDocument() {
  const text = chatTranscriptText();
  if (!text) return toast("There is nothing to save yet.");
  const title = ($("chat-title")?.textContent || "Chat").trim();
  try {
    const doc = await apiJson("/documents", {
      method: "POST",
      body: JSON.stringify({
        title: `${title}: chat`,
        content: `# ${title}\n\n${text}\n`,
      }),
    });
    chatWriteRecord("chatDocumentUndo", doc);
    toastAction("Saved to your documents.", "Open it", () => {
      switchTab("documents");
      openDocument(doc.id);
    }, { go: { open: "doc", id: doc.id } });
  } catch (error) {
    toast(error.message || "Couldn't save that document.", true);
  }
}

//: **Chat's Make a mind map** (`chatKeep("map", text, name)`; "doc" is Save this chat as a document) (MINDMAP_PLAN.md §12.3 item 3): an answer, or
//: the whole conversation, outlined as a map by the same build a note's
//: Make a mind map uses (`/whiteboard/maps/from-text`), so no model is
//: needed. Lives here, not in chat.js, to stay out of the boot budget.
async function chatKeep(kind, text, name) {
  if (kind === "doc") return saveChatAsDocument();
  const body = (text || "").trim();
  if (!body) return toast("There is nothing to map yet.");
  try {
    const board = await apiJson("/whiteboard/maps/from-text", {
      method: "POST",
      body: JSON.stringify({ name: name || "", text: body }),
    });
    pushBinPairUndo("Made a mind map from a chat", `/entries/${board.id}`, `/entries/${board.id}/restore`, true, () => refreshEntries([board.id]));
    toastAction(`Mind map \u201c${board.title}\u201d made.`, "Open", () => openWhiteboardBoard(board.id), { go: { open: "board", id: board.id } });
  } catch (error) {
    toast(error.message || "Couldn't make a mind map from this chat.", true);
  }
}

async function saveChatAnswerAsNote(question, answer) {
  try {
    const content = question ? `${question}\n\n${answer}` : answer;
    const made = await apiJson("/entries", {
      method: "POST",
      body: JSON.stringify({ content, tags: ["chat"], is_draft: true, defer_filing: true }),
    });
    pushEntryCreateUndo(made, "Saved a chat answer as a note");
    toast("Saved as a draft note.");
    // Unconditional, not gated on the Notes tab being the one currently
    // open. Reported: a note saved from Chat "didn't show up in the
    // drafts" - it *was* saved, but `entries` (the in-memory list Notes
    // renders from) was never refetched, since switchTab("notes") doesn't
    // reload it either. The stale list only caught up whenever something
    // else happened to call loadEntries() next. refreshAfterToolChanges()
    // already calls this with no such guard, for the same reason.
    loadEntries();
  } catch (error) {
    toast(error.message || "Couldn't save that note.", true);
  }
}

// Same one-click idea for reminders. No AI parse and no due-date prompt, 
// either would need a round trip or a decision before anything is saved,
// which is exactly what "one click" was asked to avoid, so this picks a
// plain default (tomorrow, 9am) and creates the reminder right away; the
// toast's "Edit" action jumps straight to it in the Reminders tab for
// anyone who wants a different time.
async function reminderFromChatAnswer(answer) {
  const text = answer.length > 100 ? answer.slice(0, 97).trim() + "…" : answer;
  const due = new Date();
  due.setDate(due.getDate() + 1);
  due.setHours(9, 0, 0, 0);
  try {
    const reminder = await apiJson("/reminders", {
      method: "POST",
      body: JSON.stringify({
        text: `Follow up: ${text}`,
        due_at: due.toISOString(),
        priority: "normal",
        recurring: "none",
      }),
    });
    askNotificationPermission();
    loadReminders();
    reminderMadeUndo(reminder);
    toastAction("Reminder set for tomorrow, 9am.", "Edit", () => {
      editingReminderId = reminder.id;
      return flashReminder(reminder.id);
    }, { go: { open: "reminder", id: reminder.id } });
  } catch (error) {
    toast(error.message || "Couldn't set a reminder.", true);
  }
}

//: A note saved in a stand-alone window (capture.html, clip.html) lands on this
//: window's Undo stack and Redo list (INBOX 898); the reply tells that window
//: it need not offer an Undo of its own (standalone-undo.js).
try {
  const standaloneNotes = new BroadcastChannel("memorymap-undo");
  standaloneNotes.onmessage = (event) => {
    if (event.data?.type !== "note-made" || event.data.id == null) return;
    pushEntryCreateUndo({ id: event.data.id }, event.data.label || "Saved a note");
    refreshEntries([event.data.id]).catch(() => {});
    standaloneNotes.postMessage({ type: "note-made-ack", id: event.data.id });
  };
} catch {
  // No BroadcastChannel: the stand-alone window offers its own Undo.
}
