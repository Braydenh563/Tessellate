// writing-desk.js: the writing desk's model passes (compose, name the
// draft, save it as a note), loaded on the first press of one of its
// buttons (app.js `LAZY_MODULES.writingDesk`). Moved out of chat-agent.js
// on 2026-10-10 when the boot scripts passed their gzip total; every
// function here is reached by a gesture and read by no caller, the shape
// `LAZY_ENTRY_POINTS` stands in for.

//: **One pass at the desk, streamed.** Measured before this: a draft against
//: a stand-in model server took 22.9 seconds to arrive and arrived in one
//: piece, because `/drafts/compose` could not answer until the model had
//: finished. `/drafts/compose/stream` speaks the same NDJSON the chat and the
//: Guide do, so this reader is the third of the same shape rather than a new
//: protocol.
//:
//: **The draft in the box is never written over until the first token of the
//: new one arrives**, and is put back if the pass fails or is stopped: a
//: half-written revision over settled writing is the one outcome this feature
//: must never produce.
async function composeDraft() {
  const written = $("draft-thoughts").value;
  // Only the part they've added since the last pass. If they edited earlier
  // text, the prefix no longer matches and everything is sent again, the
  // safe direction: the model repeats itself rather than losing a thought.
  const thoughts = written.startsWith(foldedThoughts)
    ? written.slice(foldedThoughts.length).trim()
    : written.trim();
  const draft = $("draft-text").value;
  if (!thoughts && !draft.trim()) {
    setDraftStatus("Write a thought first.", true);
    $("draft-thoughts").focus();
    return;
  }
  const instruction = $("draft-instruction").value.trim();
  setDraftStatus("");
  setDraftWorking(draft.trim() ? "ph:spin Revising…" : "ph:spin Drafting…");
  const thinkingHost = $("draft-thinking");
  const thinking = thinkingFoldIn(thinkingHost);
  const thinkingText = thinking.querySelector(".thinking");
  thinkingText.textContent = "";
  thinkingHost.classList.add("hidden");
  thinking.open = false;
  draftController = new AbortController();
  setDraftBusy(true);

  let streamed = "";
  let started = false;
  let thought = "";
  let done = null;
  try {
    await streamDraft(
      {
        thoughts,
        draft,
        instruction,
        kind: $("draft-kind").value,
        tone: $("draft-tone").value,
        length: $("draft-length").value,
        source_ids: draftSources.map((s) => s.id),
      },
      draftController.signal,
      (event) => {
        if (event.type === "thinking") {
          thought += event.text;
          thinkingHost.classList.remove("hidden");
          thinking.open = true;
          // Capped, so `thinkingPaint` keeps the newest line in view: a box
          // that always shows its first line stops saying anything.
          thinkingPaint(thinking, thought);
        } else if (event.type === "delta") {
          if (!started) {
            started = true;
            // The first token is the moment the old draft is safe to replace:
            // an undo point goes in here, not before the call.
            if (draft.trim()) pushDraftUndo();
            $("draft-text").value = "";
          }
          streamed += event.text;
          $("draft-text").value = streamed;
          updateDraftCount();
        } else if (event.type === "done") {
          done = event;
        }
      }
    );
  } catch (error) {
    $("draft-text").value = draft;
    updateDraftCount();
    if (error.name === "AbortError") {
      // Nothing was kept, so nothing is lost, say so rather than showing it
      // as a failure.
      setDraftStatus("Stopped. Your thoughts and draft are untouched.");
    } else {
      setDraftStatus(error.message, true);
    }
    draftController = null;
    setDraftBusy(false);
    return;
  }
  draftController = null;
  setDraftBusy(false);

  const finished = done && typeof done.draft === "string" ? done.draft : streamed;
  $("draft-text").value = finished || draft;
  updateDraftCount();
  // Collapsed once it lands: the thinking is worth watching and not worth
  // keeping open over the draft it was about.
  thinking.classList.toggle("hidden", !thought);
  thinking.open = false;
  if (done && done.message) {
    setDraftStatus(done.message, true);
  } else {
    // The thoughts have been folded in, remember that, but never delete what
    // they wrote. Clearing the box was reported twice as the app eating the
    // user's text, and it is: the raw thoughts are often the only copy of an
    // idea, and the draft is a rewrite of them, not a replacement.
    if (thoughts) foldedThoughts = written;
    $("draft-instruction").value = "";
    rememberDraftVersion($("draft-text").value);
    setDraftStatus(
      thoughts
        ? "Folded your thoughts into the draft, your notes above are untouched."
        : "Draft updated: edit it, or add more thoughts."
    );
    announce("The draft has been updated.");
  }
  saveDraftLocally();
}

//: The NDJSON reader for the writing desk. Hand-rolled rather than through
//: `apiJson`, which cannot expose a streaming body, and deliberately small:
//: the chat's reader carries a turn's worth of event kinds and an idle
//: timeout for a conversation that can stall for minutes, and none of that
//: belongs to a one-shot draft. A malformed line is skipped rather than
//: thrown out of the loop, the same rule the chat reader keeps, so one bad
//: frame cannot lose a draft that is already half written.
async function streamDraft(body, signal, onEvent) {
  // `api.stream` (F5): the Response, with 401 and refusals already handled.
  const response = await api.stream("/drafts/compose/stream", {
    method: "POST",
    body: JSON.stringify(body),
    signal,
  });
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffered = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffered += decoder.decode(value, { stream: true });
    const lines = buffered.split("\n");
    buffered = lines.pop(); // the last piece may be half a line
    for (const line of lines) {
      if (!line.trim()) continue;
      try {
        onEvent(JSON.parse(line));
      } catch {
        recordBrowserLog("WARN", [`[Draft stream] Unparseable line: ${line.slice(0, 80)}`]);
      }
    }
  }
}

//: **Name the draft.** `POST /drafts/title` shipped with the writing room
//: and had no caller anywhere: the model could name a finished draft and
//: nothing ever asked it to. A note's title in this app is its leading
//: `# Heading` (see `withTitle`), which is the one part of a long draft
//: nobody writes, and the capture box has a title field while this panel
//: never did.
//:
//: Undoable like every other pass here, for the reason `pushDraftUndo`
//: carries at length: handing your writing to the model is never a one-way
//: door. An existing heading is replaced rather than stacked, because
//: pressing this twice must not leave two of them.
async function suggestDraftTitle() {
  const box = $("draft-text");
  const button = $("draft-title");
  const draft = box.value.trim();
  if (!draft) {
    setDraftStatus("Write a draft first, then it has something to name.", true);
    return;
  }
  button.disabled = true;
  setDraftStatus("");
  setDraftWorking("ph:spin Thinking of a title…");
  try {
    const body = await apiJson("/drafts/title", {
      method: "POST",
      body: JSON.stringify({ draft }),
    });
    const title = (body.title || "").trim();
    //: The route answers `""` rather than an error when the model is not
    //: running or its answer was not a title (too long, too many words: see
    //: `drafter.suggest_title`). That is a real answer and it gets a real
    //: sentence, not a thrown error.
    if (!title) {
      setDraftStatus(`Couldn't think of a title for this one. ${aiNameNow()} may not be running.`, true);
      return;
    }
    pushDraftUndo();
    box.value = draftWithHeading(box.value, title);
    updateDraftCount();
    saveDraftLocally();
    setDraftStatus(`Titled "${title}". Undo puts it back.`);
  } catch (error) {
    setDraftStatus(error.message, true);
  } finally {
    button.disabled = false;
    setDraftWorking();
  }
}

//: The draft with `title` as its leading `# Heading`: replacing the one it
//: already has, or put in front of it with the blank line markdown needs
//: between a heading and its first paragraph.
function draftWithHeading(draft, title) {
  const rest = draft.replace(/^\s*#\s+[^\n]*\n*/, "");
  return `# ${title}\n\n${rest.replace(/^\n+/, "")}`;
}

async function saveDraftAsNote(asDraft = false) {
  const content = $("draft-text").value.trim();
  const status = $("draft-status");
  if (!content) {
    status.classList.add("error");
    status.textContent = "There's no draft to save yet.";
    return;
  }
  status.classList.remove("error");
  status.textContent = "Saving…";
  const tags = $("draft-tags")
    .value.split(",")
    .map((t) => t.trim())
    .filter(Boolean);
  try {
    let entry;
    if (draftNoteId !== null) {
      // Carried on from a note, so it goes back to that note. A second copy
      // of a note you asked to continue is not a save, it is a fork, and the
      // two would drift from the moment it was made. The same undo entry the
      // rest of the app records for an edited note, so this is as reversible
      // as any other change to it.
      const before = allEntries.find((e) => e.id === draftNoteId)?.content ?? "";
      // The tags field only ever *adds* here: sending an empty list would
      // strip the tags the note already carries, and an empty box on this
      // desk means "I did not type any", never "take that note's tags off".
      entry = await apiJson(`/entries/${draftNoteId}`, {
        method: "PUT",
        body: JSON.stringify(tags.length ? { content, tags } : { content }),
      });
      pushEntryPutUndo(
        draftNoteId,
        "Carried a note on from the writing desk",
        { content: before },
        { content }
      );
    } else {
      // **A note by default, a draft when the caret says so** (owner,
      // 2026-10-17: "the translated note I filed got filed as a draft"). The
      // press says "Save as note" and now does it: filed in the background
      // like any capture. "Save as draft" keeps the old behaviour, findable
      // in the Drafts filter (sidebar, Library) like the text-selection
      // popup's draft.
      entry = await apiJson("/entries", {
        method: "POST",
        body: JSON.stringify({ content, tags, is_draft: asDraft === true, defer_filing: true }),
      });
    }
    const wroteBack = draftNoteId !== null;
    clearDraftTarget();
    foldedThoughts = "";
    $("draft-thoughts").value = "";
    $("draft-text").value = "";
    $("draft-tags").value = "";
    $("draft-thinking").classList.add("hidden");
    // The desk is clear, so its earlier versions and the notes this one was
    // written from go too: a row of "v1 v2 v3" over an empty box offers a way
    // back to drafts of a note that has already been filed.
    draftSources = [];
    draftVersions = [];
    renderDraftSources();
    renderDraftVersions();
    updateDraftCount();
    saveDraftLocally();
    const kept = asDraft === true && !wroteBack;
    status.textContent = wroteBack ? "Saved back to the note." : kept ? "Saved as a draft." : "Saved as a note.";
    toast(wroteBack ? "The note has been updated." : kept ? "Saved as a draft, find it under Drafts." : "Saved as a note, Atlas is filing it.");
    await refreshEntries([entry.id]);
    flashEntry(entry.id); // show them where it landed
  } catch (error) {
    status.classList.add("error");
    status.textContent = error.message;
  }
}

//: The spinner and its words while a pass runs, in the Atlas column's head
//: (INBOX 904 B76); no argument clears it. The status line below the user's
//: thoughts keeps what a pass said when it ended.
function setDraftWorking(label = "") {
  setLabel($("draft-working"), label);
  $("draft-working").classList.toggle("hidden", !label);
}

function setDraftBusy(busy) {
  $("draft-compose").classList.toggle("hidden", busy);
  $("draft-cancel").classList.toggle("hidden", !busy);
  $("draft-undo").disabled = busy || draftUndoStack.length === 0;
  // The draft box is being written into while this runs, so editing it would
  // be editing something that is about to be overwritten by the next chunk.
  $("draft-text").readOnly = busy;
  if (!busy) setDraftWorking();
  $("draft-refine").disabled = busy;
  $("writing-room").classList.toggle("draft-writing", busy);
}


//: The caret half of the Save split button: one other way to save, as a draft
//: (`kebabMenu`'s opener dressed as the split's second half, as the OCR
//: workspace's Read does in `ocrSyncReadMenu`). Drawn when the writing room is
//: first shown (`showNotesSection`), so the boot scripts do not carry it.
function draftSaveMenuInit() {
  const slot = $("draft-save-menu-slot");
  if (!slot || slot.firstChild) return;
  const wrap = kebabMenu(
    [{ label: "ph:note-pencil Save as draft", title: "Keep it in Drafts to finish later, unfiled", run: () => saveDraftAsNote(true) }],
    "More ways to save: as a draft"
  );
  const opener = wrap.querySelector(":scope > button");
  if (opener) {
    opener.id = "draft-save-menu";
    opener.classList.remove("icon-only");
    opener.classList.add("split-button-caret");
    setLabel(opener, "ph:caret-down");
    opener.title = "More ways to save";
    opener.setAttribute("aria-label", "More ways to save: as a draft");
  }
  slot.replaceChildren(wrap);
}
