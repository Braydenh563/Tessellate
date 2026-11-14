// capture-ask.js: capture, notes and documents, Ask, suggested questions, Ask
// history. Moved out of app.js on 2026-09-26 as one contiguous range (INBOX 426
// cc, docs/roadmap/agent-remaining/appjs-split.md). A classic script sharing
// app.js's globals, loaded in app.js's old order; nothing in an earlier file
// calls into it while the page loads (scratchpad/appjs-map.js --check).

// --- capture -----------------------------------------------------------------

// Human explanations of how a note was filed ("visuals of what happened").
// A "go to it" link beside the save confirmation. Replaced each save, and
// cleared as soon as you start typing the next note.
function offerJumpToNewNote(saved, status) {
  if (!saved || !saved.id) return;
  const jump = document.createElement("button");
  jump.type = "button";
  jump.className = "ghost small jump-to-note";
  setLabel(jump, "ph:arrow-right Go to it");
  jump.title = "Open this note in your list";
  jump.addEventListener("click", () => flashEntry(saved.id));
  status.append(" ", jump);
  //: The way back to writing, on Capture itself: the Notes dock (and its
  //: New note) is hidden while Capture shows, so the line offers the box
  //: (blind test 2026-10-31, item 9). The same small button as "Go to it".
  status.append(" ", smallButton("ph:pencil-simple Write another", "Back to the box for the next note", focusCaptureBox));
  //: A notebook's first note: the first steps' third, asking, offered here (25c).
  if (allEntries.length === 1) status.append(" ", smallButton("ph:chat-circle Ask about it", "Ask your notebook; the answer comes from your notes", openAskFromDashboard));
}

// A note whose filing waits runs after its POST returns, so the composer has
// to find out where it landed some other way. It polls this one endpoint, 
// three fields, no joins, on a widening interval, because the answer
// arrives either in well under a second (a semantic match, no model call)
// or in however long the local model takes, and a fixed 250ms poll would
// spend most of its requests on the gap between those two.
//
// Giving up is deliberately quiet. The note is already saved and already in
// the list; the only thing a timeout costs is the toast, and a notebook
// whose model has gone away should not accumulate error messages for notes
// that saved perfectly well.
const FILING_POLL_STEPS = [400, 600, 900, 1400, 2000, 3000, 4000, 6000, 8000];
//: **Watched until it settles, not for 26 seconds.** Filing waits its turn
//: in the one-at-a-time model queue (core/jobs.py), behind captions and a
//: model that may still be loading, so on a first launch it can take
//: minutes. The poller used to give up after its nine steps without
//: re-reading the list, and the card said "Filing…" forever even once the
//: note was filed (owner, 0.3.31). After the steps it keeps asking every
//: eight seconds for up to ten minutes, and whatever happens it re-reads
//: the list at the end so the card shows what the server says.
const FILING_WATCH_LIMIT_MS = 10 * 60 * 1000;
const filingWatches = new Set();

async function watchFiling(entry, { quiet = false } = {}) {
  if (!entry || filingWatches.has(entry.id)) return;
  filingWatches.add(entry.id);
  const started = Date.now();
  let step = 0;
  //: **A stand-in is followed to the model's answer**
  //: (tests/test_filing_standin_watch.py). A slow model's note is filed by
  //: its words first (`standin`) and the answer replaces it when it lands;
  //: the watch used to stop at the stand-in, so the line said "Health" and
  //: nothing said the model then moved it to Work.
  let standIn = null;
  try {
    while (Date.now() - started < FILING_WATCH_LIMIT_MS) {
      const wait = FILING_POLL_STEPS[Math.min(step, FILING_POLL_STEPS.length - 1)];
      step += 1;
      await new Promise((r) => setTimeout(r, wait));
      let status;
      try {
        status = await apiJson(`/entries/${entry.id}/filing`, { silent: true });
      } catch {
        return; // deleted, or the server went away, nothing to report
      }
      if (status.filing_state === "pending") continue;
      if (status.filing_state === "standin") {
        if (!standIn) {
          standIn = status;
          settleCaptureStatus(status);
        }
        continue;
      }
      if (standIn) {
        const before = filingOutcomeText(standIn);
        const changed = status.category !== standIn.category;
        settleCaptureStatus(status, before);
        if (changed && !quiet) {
          const from = standIn.category;
          toastAction(
            `${aiNameNow()} read it and moved it from “${from}” to “${status.category}”.`,
            `Put it back in ${from}`,
            () => moveNotesToCategory([entry.id], from),
          );
        }
        return;
      }
      //: **Said once, where the person is looking** (INBOX 432). The
      //: composer's line and a toast both carried the same sentence, so a
      //: save from Capture read it twice; the toast is for someone who has
      //: left the composer since.
      const shown = settleCaptureStatus(status);
      if (quiet) return;
      const text = filingOutcomeText(status);
      if (status.filed_by === "none" || status.filing_state === "failed") {
        if (!shown) toastAction(text, "Choose category", () => chooseNoteCategory([entry.id], status.category));
      } else if (!shown) {
        toastAction(text, "Go to it", () => flashEntry(entry.id), { go: { open: "entry", id: entry.id } });
      }
      // The near-duplicate search moved into the same background pass, so
      // this warning arrives here now rather than on the create response.
      // Still purely informational, still never blocking, the note saved.
      if (status.similar) {
        toastAction(`This is close to an existing note, “${status.similar.preview}”.`, "Open it", () => flashEntry(status.similar.id), { go: { open: "entry", id: status.similar.id } });
      }
      return;
    }
  } finally {
    filingWatches.delete(entry.id);
    // The card in the list still says "Filing…" and still shows the holding
    // category until something re-reads it.
    await refreshEntries([entry.id]);
  }
}

//: The composer's line said "Filing it in the background" until the next
//: save, long after the note had been filed. Replaced only while it still
//: says that, so a newer save's own status is never overwritten.
//: `from` is the text it may replace: the pending line, or the stand-in's
//: line when the model's answer follows it.
function settleCaptureStatus(status, from = filedByText({ filing_state: "pending" })) {
  //: The line's first node is the text; `offerJumpToNewNote` appends its
  //: "Go to it" button after it, and that button stays. Answers whether the
  //: line said it on screen, so the caller knows a toast would repeat it.
  const line = $("save-status");
  const text = line?.firstChild;
  if (!text || text.nodeType !== Node.TEXT_NODE) return false;
  if (text.nodeValue !== from) return false;
  if (line.dataset.entryId && line.dataset.entryId !== String(status.id)) return false;
  text.nodeValue = filingOutcomeText(status);
  //: A pick the app is not sure of (its number under the review line, after
  //: the calibration in `ai/filing_certainty.py`) keeps its "Go to it" and
  //: gets the same one-tap alternatives; a pick nothing could make is
  //: replaced by "Choose category".
  const unsurePick = status.filed_by === "ai" && status.ai_confidence > 0
    && status.ai_confidence < REVIEW_THRESHOLD && (status.suggestions || []).length > 0;
  const nothingFiled = status.filed_by === "none" || status.filing_state === "failed";
  if (nothingFiled || unsurePick) {
    const jump = nothingFiled ? line.querySelector(".jump-to-note") : null;
    if (jump) {
      const choose = jump.cloneNode(false);
      setLabel(choose, "ph:folder-open Choose category");
      choose.title = "Pick this note's category yourself";
      choose.addEventListener("click", () => chooseNoteCategory([status.id], status.category));
      jump.replaceWith(choose);
    }
    //: **One tap to file it** (INBOX 434): the categories its words lean
    //: to, then the ones used last, beside Choose category. A guess shown
    //: as a choice costs a glance; a guess filed is a note lost.
    //: Each choice carries its why in its tooltip (WORLD_CLASS 23,
    //: decision 3), and a new category the topic list proposes comes last,
    //: made only when pressed (decision 2).
    const offer = (label, name, title) => {
      const pick = smallButton(label, title, async () => {
        const moved = await moveNotesToCategory([status.id], name);
        if (!moved) return;
        for (const other of line.querySelectorAll(".capture-suggest")) other.remove();
        line.querySelector(".jump-to-note")?.remove();
        text.nodeValue = `Filed by you under “${name}”.`;
      });
      pick.classList.add("capture-suggest");
      line.appendChild(pick);
    };
    for (const name of (status.suggestions || []).slice(0, 3)) {
      const why = status.suggestion_reasons?.[name];
      offer(`ph:folder ${name}`, name, why ? `File it under ${name}. ${why}` : `File it under ${name}`);
    }
    if (status.proposal?.name) {
      offer(`ph:folder-plus New: ${status.proposal.name}`, status.proposal.name, `Make the category ${status.proposal.name} and file it there. ${status.proposal.why}`);
    }
  }
  return line.offsetParent !== null;
}

//: Where a filed note landed, in words that are true for every way it can
//: land. A confidence is only quoted when something actually decided.
function filingOutcomeText(status) {
  if (status.filing_state === "failed") {
    return `Saved in “${status.category}”: ${aiNameNow()} couldn't file it.`;
  }
  //: Filed by its words while the model is still reading it: said as a
  //: holding place, since the model's answer may move it.
  if (status.filing_state === "standin") {
    return `Filed under “${status.category}” for now: ${aiNameNow()} is still reading it.`;
  }
  //: Health, money, family, the law and identity wait for the person
  //: (WORLD_CLASS 23, decision 6; Settings can let them file).
  if (status.filed_by === "none" && status.held_sensitive?.category) {
    return `Saved in “${status.category}”: it reads as ${status.held_sensitive.topic}, so it waits for you to choose.`;
  }
  //: The words' own reason for waiting, the same line the hint said
  //: (INBOX 1583: "A close call between Hobbies and Study, ...").
  //: The line starts "It", "A" or "Not", never a name, so the lower case is safe.
  if (status.filed_by === "none" && status.waits_why) {
    return `Saved in “${status.category}”: ${status.waits_why[0].toLowerCase()}${status.waits_why.slice(1)}`;
  }
  if (status.filed_by === "none") {
    return aiIsOff()
      ? `Saved in “${status.category}”: no AI model is running to file it.`
      : `Saved in “${status.category}”: ${aiNameNow()} couldn't decide where it goes.`;
  }
  if (status.filed_by === "user") return `Filed by you under “${status.category}”.`;
  //: Filed with no model, from the notes already filed (INBOX 434): said as
  //: what it is, so it is never mistaken for the AI's judgement.
  //: With its why (WORLD_CLASS 23, decision 3): the words shared, the notes
  //: it joins.
  if (status.filed_by === "words") {
    return status.why ? `Filed under “${status.category}”. ${status.why}` : `Filed under “${status.category}”: it reads like your other notes there.`;
  }
  //: **A low number is said as doubt, not as a verdict.** The number is the
  //: app's calibrated estimate (a small model's own figure is never shown as
  //: it said it), so under the review line the line asks for a look and the
  //: alternatives come beside it.
  if (status.ai_confidence > 0 && status.ai_confidence < REVIEW_THRESHOLD) {
    return `Filed under “${status.category}”, but only ${status.ai_confidence}% sure. Pick another if it is wrong.`;
  }
  return status.ai_confidence
    ? `Filed under “${status.category}” (${status.ai_confidence}% sure).`
    : `Filed under “${status.category}”.`;
}

function filedByText(saved) {
  if (saved.filing_state === "pending") {
    //: UX-17 (audit 2026-10-05): with no model known to be running, the
    //: background filing is by the notes already filed, so it says so rather
    //: than promising the AI the status bar says is off.
    return modelStatus?.model_ready
      ? "Saved. Filing it in the background, keep writing."
      : "Saved. Filing it by your other notes, keep writing.";
  }
  switch (saved.filed_by) {
    case "semantic-match":
      return `Filed under “${saved.category}” (${saved.ai_confidence}% sure): matched by meaning, no AI call needed`;
    case "llm":
      //: **"Atlas, running qwen2.5:7b"**, the form the owner's own decision
      //: names (INBOX 225): the librarian's name is what the app calls
      //: itself, and the model's name stays beside it, because "which model
      //: decided this" is the question this line exists to answer and a
      //: persona name alone would stop answering it.
      return `Filed under “${saved.category}” (${saved.ai_confidence}% sure): decided by ${aiNameNow()}${
        modelStatus && modelStatus.chat_model ? `, running ${modelStatus.chat_model}` : ""
      }`;
    case "user":
      return `Filed by you under “${saved.category}”: ${aiNameNow()} stayed out of it`;
    default:
      return `Saved as “${saved.category}”: ${aiNameNow()} wasn't available to file it`;
  }
}

// --- notes ↔ documents ------------------------------------------------------
// Asked for directly: "a way to link documents to new notes I create in the
// capture tab… the documents and notes sections need to be more integrated".
// The picker adds; the chips are how you take one back off before saving.

const captureDocuments = new Set();

//: Files waiting to become attachments on a note that does not exist yet.
//: The long "why staging" explanation lives on `handleFileUpload`, which is
//: the only thing that fills this.
//:
//: **Declared here, ~19,000 lines before its first write, and that is the
//: fix for a real crash.** It was originally declared next to
//: `handleFileUpload`, near the end of the file, but `renderCaptureFiles`
//: reads it, and the draft-restore IIFE calls that at module load time, from
//: *earlier* in the file. `let` is hoisted into the temporal dead zone
//: rather than initialised, so that read threw `Cannot access
//: 'captureStagedFiles' before initialization`, which aborted the rest of
//: app.js: `initAuth` never ran, the splash never hid, and the app sat on
//: its loading screen forever. Reported exactly that way, and caught by the
//: boot guard added the same session, which is the only reason the cause was
//: visible at all rather than being a silent hang.
//:
//: `node --check` does not catch this: it is valid syntax and a runtime
//: ordering fault. The lesson for anything similar: module-level state read
//: during load must be declared above every path that runs at load.
let captureStagedFiles = [];

async function loadCaptureDocuments() {
  //: To the end, not the first page: the picker exists to file this note
  //: under *any* document, and a document past the server's page would be
  //: invisible with nothing on screen saying so (`archive/agent-remaining/
  //: list-paging.md`). `apiPagedList` is one request at any realistic size.
  //: A failed read keeps the list already held (null) rather than emptying the picker.
  renderCaptureDocuments(await apiPagedList("/documents", 200).catch(() => null));
  document.dispatchEvent(new Event("filing-options"));
}

// Ask for a title and start an empty document. Shared by the capture box and
// the note card's "Add to a document", so both offer the same thing.
async function createDocumentNamed(suggestion = "") {
  const asking = promptDialog("Title for the new document", suggestion, { confirmLabel: "Create" });
  //: Create with nothing typed closed the dialog and said nothing (dog2 item
  //: 15); `required` makes it say so (promptDialog checks the field's validity).
  document.querySelector(".prompt-card input").required = true;
  const title = await asking;
  if (!title) return null;
  try {
    const doc = await apiJson("/documents", {
      method: "POST",
      body: JSON.stringify({ title, content: "" }),
    });
    offerCreateUndo(doc);
    return doc; // the documents tab refetches on switch, so nothing to sync
  } catch (error) {
    toast(error.message, true);
    return null;
  }
}

let captureDocumentTitles = new Map();
// The last list the server gave us, so removing a chip can put that document
// back in the adder's menu without a second round trip.
let captureDocumentList = [];

function renderCaptureDocuments(documents) {
  if (documents) {
    captureDocumentList = documents;
    captureDocumentTitles = new Map(documents.map((d) => [String(d.id), d.title]));
  }
  const box = $("entry-document-chips");
  box.replaceChildren();
  for (const id of captureDocuments) {
    const chipEl = chip(`ph:file-text ${captureDocumentTitles.get(String(id)) || id} ph:x`, "tag", () => {
      captureDocuments.delete(id);
      renderCaptureDocuments();
    });
    chipEl.title = "Don't attach this note to that document after all";
    box.appendChild(chipEl);
  }
  renderCaptureDocumentAdder();
}

//: **The picked documents are chips; the control that adds one is an adder.**
//:
//: Reported by the owner (INBOX 116) as "the add to document combobox not
//: changing", and it was not a bug in the handler: the handler wrote
//: `event.target.value = ""` on every pick *on purpose*, because a note can
//: go onto several documents and the select could only ever show one. So the
//: box snapped back to "None" the instant you chose something and the choice
//: appeared as a chip beside it. A select that refuses to hold the value you
//: just gave it reads as broken however correct its reasons are.
//:
//: The decision (recorded in UI_MODERNISATION_PLAN, "Decisions made"): a
//: thing you pick and it *acts* is a menu, and the recipe for a menu behind a
//: worded button is `labelledMenu` (DESIGN.md's recipe index). That is also
//: the shape "Attach" and "From library" already have on this same row, so
//: the three now read as one family of adders rather than one dropdown and
//: two buttons.
//:
//: Rebuilt rather than mutated on every render: the menu's contents depend on
//: which documents are already chips, and a five-item list is cheaper to
//: rebuild than to diff.
function renderCaptureDocumentAdder() {
  const slot = $("entry-document-adder");
  if (!slot) return;
  const items = [];
  for (const doc of captureDocumentList) {
    if (captureDocuments.has(doc.id)) continue;
    //: A menu past five rows is grouped (DESIGN.md, kebabMenu): the documents,
    //: then the one way to make another.
    items.push({
      ...makeMenuItem(`ph:file-text ${doc.title}`, `Attach this note to “${doc.title}”`, () => {
        captureDocuments.add(doc.id);
        renderCaptureDocuments();
      }),
      group: "Documents",
    });
  }
  // Asked for: "the add to document should have the option for a new document
  // as well". Wanting to file a note under something that does not exist yet
  // is the normal case at the start of a project, and leaving to make the
  // document loses the note you were in the middle of writing.
  items.push({
    ...makeMenuItem("ph:plus New document…", "Start a document and attach this note to it", async () => {
      const doc = await createDocumentNamed($("entry-content").value.trim().slice(0, 60));
      if (!doc) return;
      captureDocuments.add(doc.id);
      await loadCaptureDocuments(); // so the new one is in the list to remove
    }),
    group: "New",
  });
  const adder = labelledMenu("ph:file-plus Add to document", items, "Add to document", "ghost");
  slot.replaceChildren(adder);
}

//: Filing options (owner, 2026-11-11, decision 6): a kebabMenu by the Filing row for
//: `ask_when_unsure`, the key Settings writes. A block of its own adds no shared name; wired
//: once the Notes surface is built, so a document made elsewhere (documents.js calls
//: `loadCaptureDocuments`) cannot build the Notes template just to fill this slot.
onSurface("notes", () => {
  async function render(on) {
    const slot = $("capture-filing-options");
    if (!slot) return;
    if (typeof on !== "boolean") on = Boolean((await apiJson("/preferences").catch(() => null))?.ask_when_unsure);
    const flip = async () => {
      //: Read back: `setPreference` toasts a failed save, and the label must not flip then.
      await setPreference("ask_when_unsure", !on);
      render();
    };
    slot.replaceChildren(
      kebabMenu(
        [
          {
            ...makeMenuItem(`ph:${on ? "check-circle" : "circle"} Ask me when it is not sure: ${on ? "on" : "off"}`, "Unsure filings wait for you", flip),
            group: "Filing",
          },
          {
            ...makeMenuItem("ph:gear Filing settings", "In Settings, Background tasks", () => openSettingsModal("tasks", "pref-ask-when-unsure")),
            group: "Settings",
          },
        ],
        "Filing options",
      ),
    );
  }
  document.addEventListener("filing-options", () => render());
  //: Delegated: `$()` on a Settings id would build it at load.
  document.addEventListener("change", (e) => {
    if (e.target?.id === "pref-ask-when-unsure") render(e.target.checked);
  });
});

//: **Template variables** (WORLD_CLASS_PLAN 5 item 4). `{date}` was the one
//: a note template had; `{{date}}` and `{{time}}` read the same way (one or
//: two braces), `{{clipboard}}` is what is on the clipboard when the template
//: is used, and `{{cursor}}` is where the caret lands. The preview shows the
//: clipboard as a placeholder rather than reading it before anything is chosen.
const NOTE_TEMPLATE_CURSOR = "{{cursor}}";

//: The date a template or the "/" menu writes (audit 1031 N24): the words the
//: app uses everywhere else ("Oct 31, 2026"), not the numeric "10/31/2026".
const stampDate = (when) => when.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });

function noteTemplateText(raw, clipboard = "[clipboard]") {
  const now = new Date();
  return String(raw || "")
    .replace(/\{\{?date\}\}?/g, stampDate(now))
    .replace(/\{\{?time\}\}?/g, now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }))
    .replaceAll("{{clipboard}}", clipboard);
}

//: The text and the caret for Use this template: the clipboard read only
//: when the template asks for it, an unreadable one (refused, empty, no
//: permission) filled as nothing and said once.
async function noteTemplateForUse(template) {
  const raw = String(template?.content || "");
  let clipboard = "";
  if (raw.includes("{{clipboard}}")) {
    try {
      clipboard = (await navigator.clipboard.readText()) || "";
    } catch {
      toast("Couldn't read the clipboard, so that part of the template is empty.", "info");
    }
  }
  const full = noteTemplateText(raw, clipboard);
  const caret = full.indexOf(NOTE_TEMPLATE_CURSOR);
  return { text: full.replaceAll(NOTE_TEMPLATE_CURSOR, ""), caret };
}

//: The rich editor mounted over `box`, or null: `noteSurfaceFor` lives in
//: the documents bundle, which may not have arrived, and its answer is
//: read, so it cannot be a stand-in. The one guard for every caller.
function noteSurfaceIfAny(box) {
  return typeof noteSurfaceFor === "function" ? noteSurfaceFor(box) : null;
}

function openDocumentFromNote(documentId) {
  switchTab("documents");
  // The tab's own loader races us otherwise, and opens the last document.
  setTimeout(() => openDocument(documentId), 150);
}

// ROADMAP.md Tier 2 §16d, asked for directly: an optional title field
// where a note is created. Not a second stored field, it writes the same
// leading `# heading` line `manager.extract_title` already reads on every
// note (§43), so a title typed here reads back identically to one typed
// as the note's own first line. Only prepended when the title box actually
// has something in it, so a note with no title is unchanged from today.
//: **Under the property block, never above it** (meetings-644 audit, item 6).
//: A note of a type opens with its `---` block, and a block is a block only
//: at the very top: a title written above it turned every property into
//: body text. So the heading goes after the closing fence when there is one.
function withTitle(content, title) {
  const trimmed = (title || "").trim();
  const body = stripFrontmatter(content);
  return trimmed ? `${content.slice(0, content.length - body.length)}# ${trimmed}\n\n${body.replace(/^\n+/, "")}` : content;
}

// Shared by saveEntry and saveEntryAsDraft: clear the capture box and every
// field that goes with it once the content has actually been saved
// somewhere. Pulled out rather than left duplicated, both paths need
// exactly this, and it drifting between two copies is how one of them ends
// up leaving a stale category or template selected after a save.
//: **"Keep writing" means the caret is still there** (INBOX 432). The Save
//: button took the focus and kept it, so the next thought typed after a save
//: went nowhere: measured, the box stayed empty and its placeholder showed.
//: The editor view when one is mounted, the textarea otherwise.
function focusCaptureBox() {
  const box = $("entry-content");
  const surface = noteSurfaceIfAny(box);
  if (surface) surface.focus();
  else box?.focus();
}

function resetCaptureForm(contentBox, titleBox) {
  contentBox.value = "";
  if (titleBox) titleBox.value = "";
  renderEntryAttachmentChips();
  autoGrow(contentBox); // the box shrinks back with its content
  // It's saved for real now: the words, the title and the tags.
  for (const key of ["captureDraft", "captureDraftTitle", "captureDraftTags"]) prefs.remove(key);
  createNoteSafely.lock?.reset();
  $("entry-count").textContent = "0 words";
  $("entry-tags").value = "";
  $("entry-category").value = "";
  captureDocuments.clear();
  renderCaptureDocuments();
  clearCaptureTagSuggestions();
  // NOT cleared here: `captureStagedFiles`. `saveEntry` hands the list to
  // `uploadStagedFiles`, which takes ownership of it and empties it itself.
  // Clearing here as well would race that and silently drop the attachments
  // on every save: the composer resets before the uploads finish, by
  // design. `saveEntryAsDraft` clears it explicitly instead, below.
  renderCaptureFiles();
}

// **Tag suggestions while composing, not just after saving.** Reported
// directly: "the ai and application doesnt suggest tags either before
// creating a new note or after". `/entries/suggest-tags` needs only the
// draft's text and title (INBOX 781: the same engine as the note card's and
// Tag and file with Atlas), so it runs on the Capture box, debounced.
let captureTagSuggestTimer = null;
let captureTagSuggestSeq = 0; // invalidated on every keystroke, a slow reply
// to an earlier, shorter draft must never overwrite what a newer one asked for.

function clearCaptureTagSuggestions() {
  captureTagSuggestSeq++;
  clearTimeout(captureTagSuggestTimer);
  const row = $("entry-tag-suggestions");
  row.replaceChildren();
  row.classList.add("hidden");
}

//: The filing is not offered here: the offers row under the box is the one
//: filing hint (quickadd.js, `lexical_filing.filing_call`, INBOX 1583), where a
//: chip of this row's own said "File under Hobbies" beside "File in Hobbies".
function renderCaptureTagSuggestions(tags, reasons) {
  const row = $("entry-tag-suggestions");
  row.replaceChildren();
  if (!tags.length) {
    row.classList.add("hidden");
    return;
  }
  const label = document.createElement("span");
  label.className = "muted";
  label.textContent = "Suggested:";
  row.appendChild(label);
  for (const tag of tags) {
    const tagChip = chip(`ph:plus ${tag}`, "tag", () => {
      const box = $("entry-tags");
      const have = box.value.split(",").map((t) => t.trim()).filter(Boolean);
      if (!have.includes(tag)) box.value = [...have, tag].join(", ");
      box.dispatchEvent(new Event("input")); // kept with the draft
      tagChip.remove();
      if (!row.querySelector(".chip")) row.classList.add("hidden");
    });
    tagChip.title = reasons?.[tag] || `Add the "${tag}" tag`;
    row.appendChild(tagChip);
  }
  row.classList.remove("hidden");
}

function scheduleCaptureTagSuggestions() {
  clearTimeout(captureTagSuggestTimer);
  const content = $("entry-content").value.trim();
  // Not worth a round trip for a fragment this short, nothing useful to
  // label yet, and it would just relabel itself a few keystrokes later.
  if (content.length < 20) {
    clearCaptureTagSuggestions();
    return;
  }
  captureTagSuggestTimer = setTimeout(async () => {
    const seq = ++captureTagSuggestSeq;
    const tags = $("entry-tags").value.split(",").map((t) => t.trim()).filter(Boolean);
    const draft = JSON.stringify({ content, tags, title: $("entry-title")?.value || "" });
    const result = await apiJson("/entries/suggest-tags", { method: "POST", body: draft }).catch(() => ({}));
    if (seq !== captureTagSuggestSeq) return; // superseded by a later keystroke
    renderCaptureTagSuggestions(result.suggested_tags || [], result.suggested_tag_reasons);
  }, 1200);
}

//: Says an empty note cannot be saved, and wipes that line as soon as the person answers it. Bound
//: once per complaint rather than at startup, so a composer that never
//: errored carries no listener at all, and `{ once: true }` means the pair
//: cannot accumulate over a session of near-misses.
function captureNeedsWords() {
  const status = $("save-status");
  status.textContent = "Write something first, then save.";
  status.classList.add("error");
  const clear = () => {
    if (!status.classList.contains("error")) return;
    status.textContent = "";
    status.classList.remove("error");
  };
  $("entry-content")?.addEventListener("input", clear, { once: true });
  $("entry-title")?.addEventListener("input", clear, { once: true });
}

//: **The server is gone, not the note** (INBOX 434): held in the outbox
//: (quick-note.js) and the box cleared. Staged files cannot be held, so then
//: the words stay, saying why. Answers whether it said anything.
async function heldOffline(error, body, contentBox, titleBox) {
  if (!(error instanceof TypeError)) return false;
  const status = $("save-status");
  if (captureStagedImages.length || captureStagedFiles.length || !(await noteOutboxAdd(body))) {
    status.textContent = "The server is not answering. Your note is kept here; save again when it is back.";
    status.classList.add("error");
    return true;
  }
  resetCaptureForm(contentBox, titleBox);
  focusCaptureBox();
  status.textContent = "Saved on this device. It goes into your notebook as soon as the server answers.";
  return true;
}

async function saveEntry() {
  const contentBox = $("entry-content");
  const titleBox = $("entry-title");
  const status = $("save-status");
  const button = $("save-btn");

  const content = withTitle(contentBox.value.trim(), titleBox?.value);
  if (!content) {
    //: No exclamation mark (the copy rule), and it clears itself the moment
    //: anything is typed. Reported on 2026-09-09: "the words 'write something
    //: first' is at the bottom of the note capture tab when I didnt do
    //: anything?? maybe I fumbled a button." Nothing ever cleared this line,
    //: so one press of Save (or of Ctrl+S, which reaches the same button) on
    //: an empty box left an error sitting under the composer for the rest of
    //: the session, long after it had stopped being true.
    captureNeedsWords();
    return;
  }
  const tags = $("entry-tags").value.split(",").map((t) => t.trim()).filter(Boolean);
  const category = await resolveCategoryChoice($("entry-category"));
  if (category === undefined) return;

  // Filing in the background is the default, and the reason is the whole
  // point of the preference: filing asks a local model, so on a small
  // machine this form used to sit disabled behind "Filing…" for seconds
  // per note: reported as "the making of new notes was slow and annoying…
  // I feel like the note panels should disappear while filing and
  // continuing in the backend with a popup notification so I dont have to
  // wait twiddling my thumbs". Choosing a category yourself skips it
  // either way: there is nothing to wait for.
  const deferFiling = !category && (prefsCache?.background_filing ?? true);

  const payload = { content, tags, category, document_ids: [...captureDocuments], defer_filing: deferFiling, inline_tags: true, ...createNoteSafely.lock?.ask() };
  button.disabled = true;
  status.classList.remove("error");
  //: Saving settles at once, so it stays words; the model's wait has the ring.
  if (category || deferFiling) {
    status.textContent = "Saving…";
  } else {
    setLabel(
      status,
      modelStatus && !modelStatus.embedding_ready
        ? "ph:spin Filing… (the search AI is still warming up, this first one can take longer)"
        : "ph:spin Filing… (Atlas is reading and categorising your note)",
    );
  }
  try {
    //: **The pictures go up before the note does.** They were staged as
    //: `staged:<key>` urls while the note had no id (see `captureStagedImages`);
    //: this is the moment the user commits, so the bytes are uploaded and every
    //: placeholder in the text is replaced with the url the upload returned.
    //: A failure throws out of here and the save stops with the reason, a note
    //: saved with a dead `staged:` url in it would be a broken picture forever,
    //: and dropping the picture silently would be worse.
    const stagedUrls = await commitCaptureImages();
    payload.content = rewriteStagedUrls(content, stagedUrls);
    const saved = await apiJson("/entries", { method: "POST", body: JSON.stringify(payload) });
    clearStagedImages();
    status.textContent = filedByText(saved);
    //: Which note this line is about: three notes saved in a row each poll
    //: for their own filing, and the first answer used to overwrite the
    //: line the third save had just written (measured, INBOX 432).
    status.dataset.entryId = String(saved.id);
    //: Undo is on the stack the moment the note exists, not after the list
    //: refreshes below: Ctrl+Z pressed in that gap found an empty stack and did
    //: nothing (e2e capture-filing "Undo takes a new note back").
    pushUndo(
      "Created a note",
      async () => {
        await api(`/entries/${saved.id}`, { method: "DELETE" });
        await refreshEntries([saved.id]);
      },
      async () => {
        await api(`/entries/${saved.id}/restore`, { method: "POST" });
        await refreshEntries([saved.id]);
      }
    );
    if (saved.filing_state === "pending") watchFiling(saved);
    // The note finally has an id, which is the only thing the staged files
    // were ever waiting for. Not awaited: the composer is already clear and
    // the toasts report per file, making Save wait on N uploads would put
    // back exactly the blocking this session removed from filing.
    uploadStagedFiles(saved.id);
    if (saved.similar) {
      // Duplicate detection (Wave B): informational, never blocking.
      toast(
        `Heads up: this is ${Math.round(saved.similar.similarity * 100)}% similar ` +
          `to an existing note, “${saved.similar.preview}”`
      );
    }
    resetCaptureForm(contentBox, titleBox);
    focusCaptureBox();
    await refreshEntries([saved.id]);
    loadSuggestions(); // new categories → fresher recommended questions
    // Saving from Capture leaves you on Capture, with the note you just wrote
    // now somewhere in a list on another sub-tab. Offer to go to it rather
    // than making you switch tabs and hunt (user request). An offer, not a
    // jump: capturing several thoughts in a row is the common case, and
    // teleporting away after each one would fight that.
    offerJumpToNewNote(saved, status);
  } catch (error) {
    if (await heldOffline(error, payload, contentBox, titleBox)) return;
    status.textContent = error.message;
    status.classList.add("error");
  } finally {
    button.disabled = false;
  }
}

// "No option to save a note as a draft in the capture section" (user-
// reported). is_draft already existed as a note field, the text-selection
// popup, the Writing Room, and "save this answer as a draft note" in chat
// all set it: but the primary capture box had no path to it. Deliberately
// skips category resolution: a draft is "save this fast, decide later", the
// same reasoning the other three draft-creating call sites already use, 
// none of them file a category either.
async function saveEntryAsDraft() {
  const contentBox = $("entry-content");
  const titleBox = $("entry-title");
  const status = $("save-status");
  const button = $("save-draft-btn");

  const content = withTitle(contentBox.value.trim(), titleBox?.value);
  if (!content) {
    //: No exclamation mark (the copy rule), and it clears itself the moment
    //: anything is typed. Reported on 2026-09-09: "the words 'write something
    //: first' is at the bottom of the note capture tab when I didnt do
    //: anything?? maybe I fumbled a button." Nothing ever cleared this line,
    //: so one press of Save (or of Ctrl+S, which reaches the same button) on
    //: an empty box left an error sitting under the composer for the rest of
    //: the session, long after it had stopped being true.
    captureNeedsWords();
    return;
  }
  const tags = $("entry-tags").value.split(",").map((t) => t.trim()).filter(Boolean);

  const payload = { content, tags, document_ids: [...captureDocuments], is_draft: true, inline_tags: true, defer_filing: true, ...createNoteSafely.lock?.ask() };
  button.disabled = true;
  status.classList.remove("error");
  status.textContent = "Saving as draft…";
  try {
    //: Same commit-then-write order as a full save, a draft is a note with
    //: an id, so its pictures are real from the same moment.
    const stagedUrls = await commitCaptureImages();
    payload.content = rewriteStagedUrls(content, stagedUrls);
    const saved = await apiJson("/entries", { method: "POST", body: JSON.stringify(payload) });
    clearStagedImages();
    status.textContent = "Saved as a draft, find it later under Drafts in the sidebar.";
    resetCaptureForm(contentBox, titleBox);
    focusCaptureBox();
    // A draft is still a note with an id, so staged files attach to it the
    // same way. Doing this here rather than in `resetCaptureForm` is what
    // keeps that function from having to know which of its two callers has
    // already taken the list, see its own comment.
    uploadStagedFiles(saved.id);
    pushEntryCreateUndo(saved, "Saved a draft note");
    await refreshEntries([saved.id]);
  } catch (error) {
    if (await heldOffline(error, payload, contentBox, titleBox)) return;
    status.textContent = error.message;
    status.classList.add("error");
  } finally {
    button.disabled = false;
  }
}

// --- ask ----------------------------------------------------------------------

// Follow-on memory (Round 1): the running conversation, sent back so the
// model can handle "and what about…". Capped so requests stay small.
let conversation = [];
//: Indexes into `conversation` the question on screen followed on from, and
//: the chain a pressed follow-on chip hands the next question (INBOX 490).
let askTrail = [];
let askTrailPending = null;
const MAX_CLIENT_HISTORY = 4;
let askController = null; // AbortController for the in-flight stream
let lastQuestion = ""; // powers the Retry button

// Honest label for how the matching notes were found.
const SEARCH_MODE_LABELS = {
  // Both searches ran and their rankings were fused, which is the normal case
  // whenever an embedding backend is up. Named for what it is: "semantic
  // search" would now be a half-truth, and the label is the app's own account
  // of how it found what it is showing you.
  hybrid: "meaning + keywords",
  semantic: "semantic search",
  keyword: "keyword search",
  recent: "recent notes", // broad question → showing recent entries
  // These two were missing and rendered raw, so the panel said "dated", the
  // internal name, in a strip whose whole job is telling you in plain words how
  // the app found what it is showing you.
  dated: "by date",
  none: "nothing searched",
  // Matched the subject, not the stated time, see the note above
  // renderChatMeta's empty-results branch for the reasoning (§38 bug report:
  // a joke tagged joke/jokes/funny, asked about as "two weeks ago", was
  // actually three).
  outside_range: "matched, wrong time",
  //: The question named a category ("notes in Health"): its notes, newest
  //: first (search_manager._named_category).
  category: "that category",
};

// Say something to a screen reader without putting anything on screen. Used
// for changes whose only visible signal is colour or position.
//: `settle`: wait that long for the last call (a list drawn three times in one
//: filter says its count once); `once`: not again while the last settled line is
//: the same, so a redraw of an unchanged list is silent (audit 1028 S92).
function announce(message, { settle = 0, once = false } = {}) {
  const region = $("live-region");
  if (!region) return;
  if (settle) {
    clearTimeout(announce.timer);
    announce.timer = setTimeout(() => {
      if (once && announce.said === message) return;
      announce.said = message;
      announce(message);
    }, settle);
    return;
  }
  // Clearing first guarantees the change is seen as new even when the same
  // message is announced twice in a row.
  region.textContent = "";
  requestAnimationFrame(() => (region.textContent = message));
}

// Jump to an entry in the Notes tab and flash it, shared by search
// results, most-used, and related-notes chips.
//: What the popup agent's "Use the open note" toggle reads when nothing is
//: being edited: the last note this session actually opened. `flashEntry` is
//: every route to a note there is (a search result, a citation, the graph, a
//: wiki link), which is why the tracking sits here rather than at the dozen
//: call sites.
let lastOpenedEntryId = null;

//: Bring the currently-open edit form into view within its nearest scrolling
//: ancestor, without moving the page scroll position. Called after
//: `renderEntries()` rebuilds the list from scratch, which resets the notes
//: pane's scroll to the top: the editing note might then be off screen.
//: Nearest-scroller pattern per DESIGN.md: `scrollIntoView` walks every
//: ancestor to the page, including the page itself, which is not what we want.
function scrollEditingEntryIntoView(id) {
  const li = document.querySelector(`#entry-list li[data-id="${id}"]`);
  if (!li) return;
  let node = li.parentElement;
  while (node && node !== document.body) {
    const style = getComputedStyle(node);
    if (/(auto|scroll)/.test(style.overflowY) && node.scrollHeight > node.clientHeight + 1) {
      const liTop = li.getBoundingClientRect().top;
      const nodeTop = node.getBoundingClientRect().top;
      const liBottom = liTop + li.offsetHeight;
      const nodeBottom = nodeTop + node.clientHeight;
      if (liTop < nodeTop) {
        node.scrollTop += liTop - nodeTop - 8;
      } else if (liBottom > nodeBottom) {
        node.scrollTop += liBottom - nodeBottom + 8;
      }
      return;
    }
    node = node.parentElement;
  }
  // Fallback: page-level scroll, only if no scrolling ancestor found.
  const rect = li.getBoundingClientRect();
  if (rect.top < 0) window.scrollBy(0, rect.top - 8);
}

async function flashEntry(id) {
  lastOpenedEntryId = id;
  switchTab("notes");
  // The Notes tab is split into sub-tabs, and the note list lives in "browse".
  // Without this the card is found and scrolled to while its whole section is
  // display:none: so jumping to a note from a search result, the graph, or a
  // wiki link silently did nothing (user-reported).
  showNotesSection("browse");
  //: A note has an address (`#/notes/12`, router.js): a closer look at the
  //: list, so it refines the Notes entry rather than adding a step, and its
  //: opening words are what the window title says.
  const opened = allEntries.find((e) => e.id === id);
  recordTabVisit("notes", `note:${id}`, opened ? noteLabel(opened, 60) : "", { refine: true });
  activeCategory = null;
  // A draft target needs the Drafts filter ON now that drafts are excluded
  // from every other view (user-reported): otherwise jumping to one from
  // Library's "Open" button would find nothing.
  draftsOnly = Boolean(opened?.is_draft);
  // Same reason as the line above and the search reset below: a note that is
  // not pinned is filtered out of Favourites, so jumping to one while that
  // filter is on would scroll to nothing.
  favouritesOnly = false;
  // Clear any active filter too: a note that doesn't match the current search
  // is filtered out of the list, so there'd be nothing to scroll to.
  noteSearch = "";
  const searchBox = $("note-search");
  if (searchBox) searchBox.value = "";
  // The reset above fixes the view, so `resolveNotePage` can name the target's page.
  const targetPage = resolveNotePage(id);
  if (targetPage) notesCurrentPage = targetPage;
  //: Opening is the whole note, not a clipped row (blind test 2026-10-31).
  expandedRows.add(id);
  renderSidebar();
  noteEngine.jumpId = id; // paint through the target: later rows only exist after a scroll
  //: Awaited: before entry-card.js is in the draw waits for it, and the target must still be
  //: the one painted through when it comes (a deep link `#/notes/12` on a fresh load).
  try {
    if ((await renderEntries()) === false) return;
  } finally {
    noteEngine.jumpId = null;
  }
  requestAnimationFrame(() => {
    const card = document.querySelector(`#entry-list li[data-id="${id}"]`);
    if (!card) {
      //: Not a note after all (audit 1031 N48): the address goes back to the list rather than naming a dead id, and the last "Showing note" line leaves the live region.
      recordTabVisit("notes", "browse", "", { refine: true });
      announce("");
      return toast("No such note.");
    }
    //: A long way is a jump, not a glide: the Notes list is windowed
    //: (notes-list.js), and every row built on the way draws at its own
    //: height, so a smooth scroll aimed at the card's first place ended
    //: thousands of pixels short on a phone. Then it is centred again once
    //: the rows round it are built.
    const reduced = reducedMotionWanted();
    const far = Math.abs(card.getBoundingClientRect().top) > 2 * window.innerHeight;
    card.scrollIntoView({ behavior: reduced || far ? "auto" : "smooth", block: "center" });
    if (far) requestAnimationFrame(() => requestAnimationFrame(() => {
      document.querySelector(`#entry-list li[data-id="${id}"]`)?.scrollIntoView({ block: "center" });
    }));
    // Restart the animation even when the same note is jumped to twice in a
    // row: without the reflow the class is already there and nothing replays.
    card.classList.remove("flash");
    void card.offsetWidth;
    card.classList.add("flash");
    //: Focus lands on the note as a click leaves it (it was left on <body>), so
    //: the arrows, Enter and the Connections column read from it at once.
    card.focus({ preventScroll: true });
    // Announce it too: a colour change alone tells a screen-reader user
    // nothing about where they've just been sent.
    // Just the note's own text: card.textContent would drag in the category
    // chip, every tag, and the confidence badge.
    const body = card.querySelector(".entry-content")?.textContent || "";
    announce(`Showing note: ${body.trim().slice(0, 80)}`);
    clearTimeout(flashEntry.timer);
    flashEntry.timer = setTimeout(() => card.classList.remove("flash"), 2700);
    //: Every way to a note comes here (search, a link, the palette, the
    //: Library, the timeline, the graph, chat): the companion reads along
    //: with a long one, or covers its eyes for a private one (avatars.js).
    nameMarkBuddyNoteOpened(id);
  });
}

// ROADMAP.md Tier 2 §13: changeRow's View button only ever reached notes and
// documents: reminders and categories had no navigation target at all, on
// top of having no backend id/name resolver. Same shape as flashEntry above.
//: **A source opens its note at the quoted line** (CHAT_PLAN 8 row 7): the
//: card in the list, flashed as before, with the cited span marked. `from`
//: is the passage, or the clicked card whose answer's marks know it; the
//: marking is in reveal-targets.js, out of the boot (the reveal bundle).
function openNoteAtPassage(id, from) {
  flashEntry(id);
  ensureModule("reveal").then(() => markNotePassage(id, from));
}

async function flashReminder(id) {
  switchTab("reminders");
  // The change that brought us here (setting or completing a reminder) may
  // not match whatever filter was last active, "open" is the default, and
  // completing one is exactly the case where it would just have vanished.
  reminderFilter = "all";
  for (const b of $("reminder-filter").querySelectorAll("button")) {
    setActiveChoice(b, b.dataset.filter === "all");
  }
  await loadReminders();
  requestAnimationFrame(() => {
    const item = document.querySelector(`#reminder-groups li[data-id="${id}"]`);
    if (!item) return;
    const reduced = reducedMotionWanted();
    item.scrollIntoView({ behavior: reduced ? "auto" : "smooth", block: "center" });
    item.classList.remove("flash");
    void item.offsetWidth;
    item.classList.add("flash");
    announce(`Showing reminder: ${(item.textContent || "").trim().slice(0, 80)}`);
    clearTimeout(flashReminder.timer);
    flashReminder.timer = setTimeout(() => item.classList.remove("flash"), 2700);
  });
}

// Categories have no single note to scroll to, "View" means "show me what's
// in it", the same job the sidebar's own category filter already does.
function flashCategory(name) {
  switchTab("notes");
  showNotesSection("browse");
  activeCategory = name;
  draftsOnly = false;
  noteSearch = "";
  const searchBox = $("note-search");
  if (searchBox) searchBox.value = "";
  renderSidebar();
  renderEntries();
}

//: **What a sentence is matched on: its letters and digits, nothing else**
//: (INBOX 318). The grounded sentence is the answer's markdown source and the
//: page holds what the renderer made of it, and the two differ in exactly the
//: characters that carry no words: `**` and `*` vanish, a list's `- ` is
//: drawn as a bullet, a link keeps its text and loses its target, and
//: emphasis cuts one sentence into three text nodes. Measured with an answer
//: shaped the way a model writes (a lead-in, a list with bold labels, a
//: closing sentence with one word in italics): the grounding named every note
//: and not one marker was placed, because the old search looked for the raw
//: sentence inside one text node at a time. Compared on letters and digits
//: across the whole block, the formatting cannot make a sentence unfindable,
//: and it cannot make one match in the wrong place either: a sentence of a
//: dozen words is the same run of letters wherever it is drawn.
const CITATION_WORD_CHAR = /[\p{L}\p{N}]/u;

//: Where the marker goes once the sentence's last letter is found: after the
//: punctuation that closes it, and outside any bold or italic the sentence
//: ended inside, so the digit is not drawn bold because the last word was.
const CITATION_CLOSING = /[.!?:;,)\]"'”’。！？）」』】〕]/
const CITATION_INLINE_TAGS = new Set(["STRONG", "EM", "B", "I", "A", "CODE", "MARK", "S", "DEL", "SPAN"]);
//: **One mark per run, at its end** (the owner, 2026-09-24: "the amount of
//: intext referencing like with the 1's is a little excessive"; a four-sentence
//: paragraph from one guide carried four). Sentences of one paragraph backed by
//: the same notes are one claim, so one mark where the run ends; it stays where
//: the set of notes or the paragraph changes, and its hover passage moves to
//: the run's last mark.
const CITATION_BLOCK = "p, li, blockquote, td, th, h1, h2, h3, h4, h5, h6, dd";
//: **The citation peek** (INBOX 80): what a numbered mark stands for, next
//: to the mark. A `.help-popover` in everything but its content: lifted to
//: `<body>`, placed and flipped by `placeHelpPopover`, the shared popover
//: shell, caret and tier (DESIGN.md, "A preview of a cited source"). One at a
//: time, so moving along a line of marks swaps the preview rather than
//: stacking them.
//:
//: The body is the passage the sentence was grounded on, marked, with a
//: little of the note either side so it reads as part of something; a mark
//: with no passage (a note a tool read mid-turn) shows the note's opening
//: words. Characters, never rendered Markdown: the slice is taken at
//: character offsets and can begin mid-emphasis.
function evidenceSpan(className, text = "", tag = "span") {
  const el = document.createElement(tag);
  el.className = className;
  el.textContent = text;
  return el;
}

//: **A cited note's pictures beside its citation** (INBOX 502): up to three
//: lazy thumbnails after the chip; one opens the note's pictures in the
//: lightbox. Alt: the caption or reading (`picture_alts`), else the Markdown's.
const GROUNDING_THUMBS = 3;
const pictureItems = (pictures) =>
  pictures.map((p) => ({ filename: p.url.split("/").pop(), getUrl: () => mediaSrc(p.url) }));

//: The Evidence checks switch, read once and again after Settings writes it
//: (`evidenceSwitchReset`). Unknown counts as on: the view is the default.
let evidenceSwitchLoad = null;
let evidenceChecksKnown = null;

function evidenceSwitchReset() {
  evidenceSwitchLoad = null;
  evidenceChecksKnown = null;
}

let evidenceViewCount = 0;

//: **Pictures inside the answer** (INBOX 526): the model writes `[picture N]`
//: (N = the note's prompt number, `.2` for its second picture); the token
//: becomes a figure after its block. No token: a cited note whose pictures are
//: the point gets one after its first citation. Three at most; run after the
//: citations, on every surface that shows an answer.
const PICTURE_TOKEN = /\[picture (\d{1,3})(?:\.(\d{1,2}))?\]/gi;
const FIGURES_MAX = 3;
const PICTURE_ASK = /\b(picture|photo|image|screenshot|sketch|drawing|diagram|whiteboard|scan|show me|look(s|ed)? like)/i;

//: A live paint holds back a half-written token.
function holdPictureTokens(text) {
  const clean = String(text ?? "").replace(PICTURE_TOKEN, "");
  const tail = clean.match(/\[[^\]\n]{0,14}$/);
  return tail && "[picture 9.9]".startsWith(tail[0].toLowerCase().replace(/\d+/g, "9")) ? clean.slice(0, tail.index) : clean;
}

//: **What the Ask tab draws under an answer** (CHAT_PLAN Phase 3, decision 8:
//: "Ask = Chat in single-turn mode"). Three components, none of them written
//: for this surface: `renderRelatedElsewhere`, `chatSourcesPanel` and the
//: follow-on strip are the Chat tab's, called here with the same object.
//:
//: Each gets its own container, which is the fix for a bug this restructuring
//: found: related items and grounding chips were both written into
//: `#ai-answer-grounding`, and `renderAnswerGrounding` opens with
//: `replaceChildren()`. The `related` event arrives before `grounding` on
//: every stream that has both, so "Elsewhere in your notebook" was built and
//: then deleted a moment later, on every answer, invisibly.
function clearAskAnswerFoot() {
  $("ask-answer-foot")?.classList.add("hidden");
  //: The last answer's "Only 2 of 6 sentences" notice goes with the rest of
  //: its foot. It sits beside the answer box, not in it, so emptying the box
  //: left it above the next question's thinking until that answer finished
  //: (the owner, INBOX 593: "the warning message appeared before the ai had
  //: even finished thinking").
  $("ai-answer")?.parentElement?.querySelector(":scope > .answer-support")?.remove();
  $("ask-answer-related")?.replaceChildren();
  $("ask-answer-sources")?.replaceChildren();
  $("ask-why")?.replaceChildren();
  $("ask-why")?.classList.add("hidden");
  const strip = $("ask-followups");
  if (strip) {
    strip.replaceChildren();
    strip.classList.add("hidden");
  }
}

//: **A follow-on is a question that keeps the answer above it** (decision 8:
//: "'Ask again' chips become follow-ups that carry the previous answer as
//: context"). The chips themselves are `/chat/followups`, the same second
//: model call the Chat tab makes after a turn is on screen, and clicking one
//: calls `askQuestion`, which sends `conversation` as history: so the context
//: is carried by the path every Ask turn already takes, not by a second one
//: built for chips.
//:
//: Silent on every failure, including the AI not running: an answer that
//: arrived is not made worse by having nothing to offer after it.
//: **The answer, kept** (CHAT_PLAN B12): a note, a document, or a mind map
//: of the notes it cites, from the ⋯ beside Copy; each goes on the undo
//: stack. Built on first use in ask-compose.js (lazy).
let askKept = null;

// Longer than the backend's own 120s per-chunk Ollama timeout (see the
// idle-read guard inside streamChat below) so a real "offline" answer from
// that always has time to arrive first.
const STREAM_IDLE_TIMEOUT_MS = 150_000;

//: **How long after the notes are in before "Waking the model…"** (INBOX 649).
//: A model already in memory starts its first token well inside this; one
//: that is being loaded from disk does not, and that quiet is the only signal
//: the stream gives, so it is the one honest basis for the phase.
const MODEL_LOAD_HINT_MS = 5000;

// Live markdown while streaming. Re-parsing the WHOLE accumulated answer on
// every animation frame is what made long answers feel laggy (each frame
// rebuilt the entire DOM). We now coalesce updates to ~15fps and skip the
// work entirely when the text hasn't changed: smooth, and far less main-
// thread churn, so other animations (the typing dots) don't stutter.
const LIVE_RENDER_INTERVAL_MS = 66;
//: `afterPaint`, when given, runs after every paint: a paint rebuilds the box
//: from raw markdown, so anything written into it afterwards (the Ask tab's
//: citation markers, placed while the answer streams, INBOX 320) has to be
//: written again each time or it lasts a fifteenth of a second.
// LIVE-BLOCKS-BEGIN
//: **Where a streaming answer can be cut into finished blocks** (audit 1028 E34).
//: Returns the offset of the last line that starts a new block after a blank
//: line, outside any fence, or `from` when there is none yet, or -1 when the
//: text holds a construct that spans blank lines or points back at an earlier
//: block (maths, columns, footnotes, a contents list), which is drawn whole.
//: A line that may continue the block above (an item, a table row, a quote,
//: an indented line) never starts one, and neither does a half-typed line.
//: A property of the renderer, not a name of its own: the shared scope is capped.
liveMarkdownRenderer.blockBreak = (text, from) => {
  if (/\[\^|\$\$|\[TOC\]|^\s*:::/im.test(text)) return -1;
  let best = from;
  let fenced = false;
  let blank = false;
  for (let at = from, end; (end = text.indexOf("\n", at)) !== -1; at = end + 1) {
    const line = text.slice(at, end);
    const fence = line.trim().startsWith("```");
    if (!fenced && blank && line.trim() && (fence || !/^(?:\s|[-*+](?:\s|$)|\d+[.)](?:\s|$)|[|>])/.test(line))) best = at;
    if (fence) fenced = !fenced;
    blank = !line.trim();
  }
  return best;
};
// LIVE-BLOCKS-END
function liveMarkdownRenderer(box, afterPaint = null) {
  let latest = "";
  let rendered = null;
  let timer = null;
  let lastRun = 0;
  //: Finished blocks are drawn once and kept (`kept` is their markdown,
  //: `keptCount` the nodes they made); a flush draws only the text after them
  //: into a scratch box and swaps it for what followed, so its cost is the
  //: open block, not the answer so far. Text that no longer starts with
  //: `kept` (a held-back picture token) or a box emptied by someone else
  //: starts over from the whole text.
  let kept = "";
  let keptCount = 0;
  const draw = (text) => {
    const scratch = document.createElement("div");
    renderMarkdown(scratch, text);
    box.append(...scratch.childNodes);
  };
  const paint = (clean) => {
    if (!clean.startsWith(kept) || box.childNodes.length < keptCount) [kept, keptCount] = ["", 0];
    const cut = liveMarkdownRenderer.blockBreak(clean, kept.length);
    if (cut < 0) [kept, keptCount] = ["", 0];
    while (box.childNodes.length > keptCount) box.lastChild.remove();
    if (cut > kept.length) {
      draw(clean.slice(kept.length, cut));
      kept = clean.slice(0, cut);
      keptCount = box.childNodes.length;
    }
    draw(clean.slice(kept.length));
  };

  let gap = LIVE_RENDER_INTERVAL_MS;
  const flush = () => {
    timer = null;
    lastRun = performance.now();
    if (latest === rendered) return; // nothing new since last paint
    rendered = latest;
    paint(holdPictureTokens(latest));
    afterPaint?.();
    gap = Math.max(LIVE_RENDER_INTERVAL_MS, (performance.now() - lastRun) * 4);
  };

  const render = (text) => {
    latest = text;
    if (timer) return;
    const wait = Math.max(0, gap - (performance.now() - lastRun));
    timer = setTimeout(flush, wait);
  };
  //: **The last paint has to be cancellable, or it lands after the turn is
  //: over.** Measured while fixing INBOX 40: a skill run's citation markers
  //: were placed correctly and then vanished within a frame or two, and this
  //: is what removed them. Every delta schedules a paint up to
  //: `LIVE_RENDER_INTERVAL_MS` in the future; the stream then ends,
  //: `finalise()` re-renders each step from its raw markdown and the caller
  //: puts the markers in, and *then* the timer that was already armed fires
  //: and repaints the box from `latest`, throwing them away again. Nothing
  //: about it is visible: the prose is identical, only the markers are gone,
  //: which is why it read as "citations do not work in a skill run" rather
  //: than as a race.
  render.stop = () => {
    if (timer) clearTimeout(timer);
    timer = null;
    rendered = latest; // so a later call cannot decide it still owes a paint
  };
  return render;
}

function stopAnswer() {
  if (askController) askController.abort();
}

function newChat() {
  conversation = [];
  askTrail = [];
  askTrailPending = null;
  renderAskTrail();
  lastQuestion = "";
  clearAskAnswerFoot();
  $("chat-results").classList.add("hidden");
  $("ask-idle")?.classList.remove("hidden");
  $("new-chat-btn").classList.add("hidden");
  $("ask-status").textContent = "";
  $("question").value = "";
  loadSuggestions();
}

function retryAnswer() {
  if (lastQuestion) askQuestion(lastQuestion);
}

async function copyAnswer() {
  if (await copyToClipboard($("ai-answer").textContent, $("copy-btn"))) toast("Answer copied.");
}

// --- suggested questions (Round 1) ----------------------------------------------

async function loadSuggestions() {
  const box = document.getElementById("suggested-questions");
  // Only meaningful before the first answer of a conversation.
  if (!box || !document.getElementById("chat-results").classList.contains("hidden")) return;
  const picks = await apiJson("/chat/suggestions").catch(() => []);
  box.replaceChildren();
  box.classList.toggle("hidden", picks.length === 0);
  if (picks.length === 0) return;
  const label = document.createElement("span");
  label.className = "muted";
  label.textContent = "Try asking:";
  box.appendChild(label);
  for (const question of picks) {
    const chipEl = chip(question, "", () => askQuestion(question));
    box.appendChild(chipEl);
  }
}

// --- Ask history: browse back through every notes-only question, not just
// the last five as reask chips. Requested directly: "I want the ask feature
// to be basically a personal notes browser." Every turn behind this panel
// was already written server-side by chat_stream (routes_ask_history.py);
// this is read, search, pin, delete and "reopen" only. ---------------------

let askHistoryOpen = false;
//: The badge's last answer, kept so Get started (first-run.js) reads it instead of
//: asking again: at boot both asked within half a second, and a POST between them
//: (`/recordings/recover`) emptied the GET cache. `null` until the badge has read.
let askBadgeTotal = null;

async function loadAskHistoryBadge() {
  const badge = document.getElementById("ask-history-badge");
  if (!badge) return;
  const stats = await apiJson("/ask-history/stats").catch(() => null);
  if (stats) askBadgeTotal = stats.total || 0;
  if (!stats || !stats.total) {
    badge.classList.add("hidden");
    return;
  }
  //: The first answer ticks Get started's third step even when the person
  //: left for the dashboard before it finished (E2E first-run, 2026-10-27).
  if (stats.total === 1) renderFirstStepsLazy();
  badge.textContent = stats.total > 99 ? "99+" : String(stats.total);
  badge.classList.remove("hidden");
}

//: Every tags field gets the tag list under it (tag-suggest.js, lazy: the
//: first focus loads it). It replaced a `<datalist>`, whose arrow and list
//: Chromium drew at its own size and alignment (INBOX 435).
//: Typing or a press after Escape opens it again in the field that kept the
//: focus.
for (const type of ["focusin", "input", "click"]) {
  document.addEventListener(type, (event) => {
    const box = event.target;
    if (box.matches?.("#entry-tags, .note-edit-tags > input")) openTagSuggest(box);
    //: Every search box carries `data-search-scope`: the first focus loads its
    //: suggestions (search-suggest.js, lazy), and typing or a press after Escape
    //: opens them again. Not a `LAZY_ENTRY_POINTS` stand-in: app.js is at its cap.
    else if (box.matches?.("input[data-search-scope]")) ensureModule("searchSuggest").then(() => openSearchSuggest(box));
    else if (box.id === "chat-input" && type !== "click") ensureModule("chatGhost");
  });
}

//: A press on Private before quick-note.js has loaded (it is preloaded 3 s after boot) loads it and flips the lock itself:
//: its own listener is attached after this click has gone by. Once `lock` exists its listener takes every press.
onSurface("notes", () => {
  $("entry-private")?.addEventListener("click", async (event) => {
    if (!createNoteSafely.lock && (await ensureModule("quickNote"))) createNoteSafely.lock.flip(event.target.closest("button"), "captureDraftPrivate");
  });
});

//: Open questions (WORLD_CLASS_PLAN I3, row 7): the Notes, Questions view is
//: questions-view.js, lazy (INBOX 688 moved it to make room for the Ask box's
//: answer switch). The Ask scope it sets stays here: `askQuestion` reads it.
let askScope = null;

function showAskAsOf(on) {
  const row = $("ask-as-of-row");
  const box = $("ask-as-of");
  if (!row || !box) return;
  row.classList.toggle("hidden", !on);
  $("ask-time-travel")?.setAttribute("aria-pressed", on ? "true" : "false");
  if (on) {
    //: Nothing after today: the future has no notes to read.
    const today = new Date();
    const pad = (n) => String(n).padStart(2, "0");
    box.max = `${today.getFullYear()}-${pad(today.getMonth() + 1)}-${pad(today.getDate())}`;
    box.focus();
  } else {
    box.value = "";
  }
}

//: From app.js (its cap), 2026-10-06; read at call time only.
// --- capture templates (Wave B) ---------------------------------------------------

const BUILTIN_TEMPLATES = [
  { name: "Journal", content: "Journal: {weekday} {date}\n\nToday I " },
  { name: "Recipe", content: "Recipe: \n\nIngredients:\n- \n\nSteps:\n1. " },
  { name: "Contact", content: "Contact: \nPhone/email: \nWhere we met: \nNotes: " },
  { name: "Meeting", content: "---\ntype: Meeting\n---\n## Agenda\n\n1. {{cursor}}\n\n## Notes\n\n## Decisions\n\n- \n\n## Action items\n\n- [ ] \n" },
];

async function loadTemplates() {
  // Built-ins + the user's own (kept in preferences). Shared with the two
  // other boot readers (A2): at boot this joins the one request in flight, and
  // afterwards it reads the cache every PUT in this file keeps current, which
  // is why `saveTemplateList` (PUT, then this) still shows the new template.
  await loadPreferences().catch(() => prefsCache);
  // Saved filters live in the same payload, so draw them while it's fresh.
  renderSavedSearches();
  //: Saved searches are the search box's sidebar rows (search.js, lazy),
  //: fetched now only when there are some to draw.
  if (prefsCache?.saved_finds?.length) ensureModule("search");
  //: The Capture box's picker reads `templateCatalogue()` when it opens
  //: (`openNoteTemplateDialog`), so there is nothing to pre-build here: a
  //: template saved in Settings is in the next opening without a redraw.
}
