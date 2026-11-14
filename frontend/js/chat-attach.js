// chat-attach.js: extract notes, attaching notes and images, the attach button,
// suggested-question chips (`.followups`), the answer timer. Moved out of app.js on 2026-09-26 as one
// contiguous range (INBOX 426 cc, docs/roadmap/agent-remaining/appjs-split.md).
// A classic script sharing app.js's globals, loaded in app.js's old order;
// nothing in an earlier file calls into it while the page loads
// (scratchpad/appjs-map.js --check).

// --- extract notes (BACKLOG.md §62) ---------------------------------------------
// Select a block of writing, the Writing Room's draft, a Document's body, or
// several notes' content selected on the whiteboard, and split it into one
// or more AI-drafted notes, auto-linked with real reasons. Always a preview
// first, matching Draft AI edit's own "read it, then accept" shape: nothing
// is saved until "Save notes" is pressed, since this can silently multiply
// one piece of writing into several permanent notes.

// The last preview response, kept so commit can look up each kept note's
// server-decided category and each kept link's server-generated reason: 
// the DOM only holds what the user is allowed to edit (title, content, tags,
// keep/drop), not those.
let extractProposal = null;

async function openExtractPreview(text, { sourceEntryIds = [], sourceDocumentId = null } = {}) {
  const trimmed = (text || "").trim();
  if (!trimmed) {
    toast("Select some text to extract notes from first.");
    return;
  }
  extractProposal = { source_document_id: sourceDocumentId };
  const panel = $("extract-panel");
  panel.classList.remove("hidden");
  $("extract-notes-list").innerHTML = "";
  $("extract-links-list").innerHTML = "";
  $("extract-commit").disabled = true;
  const status = $("extract-status");
  status.classList.remove("error");
  setLabel(status, "ph:spin Reading it over…");
  try {
    const body = await apiJson("/entries/extract/preview", {
      method: "POST",
      body: JSON.stringify({ text: trimmed, source_entry_ids: sourceEntryIds }),
    });
    extractProposal = { ...body, source_document_id: sourceDocumentId };
    await lazyScript("/js/extract-preview.js");
    renderExtractPreview(body);
  } catch (error) {
    status.classList.add("error");
    status.textContent = error.message;
  }
}

// What a link's `kind` (from `ai.extractor`) reads as in the preview.
//: The proposal's cards (`renderExtractPreview`) are extract-preview.js, fetched
//: with the first proposal: only an extraction reaches them.
function closeExtractPreview() {
  $("extract-panel").classList.add("hidden");
  extractProposal = null;
}

// --- attaching notes to a chat message ------------------------------------------
// "Use this note, specifically" is a stronger signal than any similarity
// score, so attached notes are sent to the model ahead of whatever retrieval
// finds. The picker searches the notes already loaded in memory, no request
// per keystroke, and it works the moment it's opened.

let attachedNoteIds = [];
// The set sent with the most recent message, so regenerate can reuse it.
let lastChatAttachments = [];

// --- attaching images to a chat message (vision-capable models) ----------------
// Same shape as note attachments just above, uploaded through the existing
// /media/upload (the note/document editors' own drag-and-drop endpoint) so
// there is one upload path in the app, not two. `attachedImages` holds
// {id, url}: the id is what the server needs, the url is what renders the
// thumbnail without a second round trip.
let attachedImages = [];
let lastChatImageAttachments = [];


function renderImageAttachments() {
  const box = $("chat-image-attachments");
  if (!box) return;
  box.replaceChildren();
  box.classList.toggle("hidden", attachedImages.length === 0);
  $("attach-image")?.classList.toggle("has-attachments", attachedImages.length > 0);
  for (const image of attachedImages) {
    // A staged image has no server url yet, its bytes are local, so the
    // object URL is what draws it. `mediaSrc` is still right for one already
    // uploaded: a plain <img> never attaches X-Auth-Token.
    box.appendChild(
      attachmentChip({
        name: image.name || "Image",
        size: image.file?.size,
        thumb: image.objectUrl || mediaSrc(image.url),
        removeTitle: "Remove this image",
        onRemove: () => {
          attachedImages = attachedImages.filter((img) => img.key !== image.key);
          // An object URL is a document-lifetime reference to a Blob:
          // dropping the array entry alone leaks the bytes while the tab is open.
          if (image.objectUrl) URL.revokeObjectURL(image.objectUrl);
          renderImageAttachments();
          announce(`Removed image. ${attachedImages.length} image(s) attached.`);
          // A staged image was never uploaded (see `attachImageFiles`), so
          // there is nothing to tell the server. One already on the server (a
          // regenerate re-using an earlier message) is left alone: the sent
          // message still references it.
        },
      }),
    );
  }
}

async function attachImageFiles(files) {
  // Small and silent per-file, deliberately: a picker with several photos
  // selected shouldn't abort the whole batch because one was too big or the
  // wrong type: the same "drop what's wrong, keep what's fine" the note
  // picker already does with unresolved wiki-links.
  const room = 4 - attachedImages.length;
  for (const file of Array.from(files).slice(0, Math.max(0, room))) {
    // **Staged, not uploaded.** REDESIGN.md R7.2, asked for directly: "files
    // should only be staged and not permanently saved while uploaded to a
    // note that hasnt been saved yet, or chat messages that havent been sent
    // yet."
    //
    // Attaching used to `POST /media/upload` immediately, so an image
    // attached to a message that was never sent stayed on disk and in the
    // Library gallery forever. Removing the chip cleaned up after itself, but
    // *abandoning* the draft: closing the tab, switching conversation,
    // walking away: did not, and that is the common case rather than the
    // rare one.
    //
    // The bytes stay in the browser until `commitStagedImages()` runs on
    // send. The thumbnail renders from an object URL, so the preview costs no
    // round trip and the server learns nothing about a message that may never
    // exist.
    attachedImages.push({
      key: `staged-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      file,
      objectUrl: URL.createObjectURL(file),
      name: file.name,
    });
  }
  renderImageAttachments();
}

// --- one attach button, two destinations ---------------------------------------
//
// Asked for directly: the chat's image button should attach *any* file, 
// "images should appear in the image gallery (any image format), and the
// others should probably go in the documents subtab".
//
// The split is by what the file *is*, not by what was clicked, because the
// picker takes both at once and a person selecting four things does not expect
// to have sorted them first:
//
// - An image goes where images already went: uploaded to the gallery and
//   staged on this message, so a vision model can look at it.
// - Anything else is imported as a document (`POST /documents/import`, which
//   extracts its text via core/docview.py). It is then a real document in the
//   Documents sub-tab, which the AI can reach with its own list_documents /
//   get_document tools: rather than a file the app had nowhere to put.
//
// Failures are per-file and quiet, the same rule attachImageFiles already
// followed: a picker with four files selected must not lose three because one
// was a .mp4.
async function attachChatFiles(files) {
  const all = Array.from(files);
  const images = all.filter(isImageFile);
  const documents = all.filter((f) => !isImageFile(f));
  if (images.length) await attachImageFiles(images);
  if (documents.length) await importChatDocuments(documents);
}

//: Documents staged on the message being written. Same shape and same
//: lifecycle as `attachedImages` above: cleared on send, snapshotted for a
//: regenerate: because a person attaching a photo and a spreadsheet in one
//: go should not find the app treating them as two different kinds of act.
//:
//: Unlike an image, removing one of these does *not* delete the document:
//: `/documents/import` created a real document in the Documents tab and the
//: toast said so, so deleting it out from under that promise would be the
//: app taking back something it already told the user it had done.
let attachedDocuments = [];
let lastChatDocumentAttachments = [];

//: Four, matching the ceiling the import path already enforced inline. A
//: local model's context is the scarce thing here, and four whole documents
//: is already more than most of them can hold alongside a conversation.
const MAX_CHAT_DOCUMENTS = 4;

//: **Files from the Library, staged on the message.** Asked for directly: "I
//: want to be able to attach not just existing notes to a chat for context,
//: but also already uploaded files, documents, and images."
//:
//: A third list rather than folding files into `attachedDocuments`, because
//: they are a third table: a Library file is an Attachment row, a document is
//: a Document row, and the chat request carries `file_ids` and `document_ids`
//: separately for exactly that reason (routes_chat.py). Removing one never
//: deletes the file -- it was in the Library before this message and stays
//: there after it, the same promise `attachedDocuments` makes.
let attachedFiles = [];
let lastChatFileAttachments = [];

//: Four, matching `MAX_CHAT_DOCUMENTS` and the server's own `max_length=4`.
//: A file's text is capped at 12k characters server-side, so four of them is
//: already a large fraction of a small local model's context.
const MAX_CHAT_FILES = 4;

function attachLibraryFile(id, name) {
  if (attachedFiles.some((f) => f.id === id)) return true;
  if (attachedFiles.length >= MAX_CHAT_FILES) return false;
  attachedFiles.push({ id, name: name || "File" });
  renderFileAttachments();
  announce(`Attached “${name || "file"}”. ${attachedFiles.length} file(s) attached.`);
  return true;
}

function renderFileAttachments() {
  const box = $("chat-file-attachments");
  if (!box) return;
  box.replaceChildren();
  box.classList.toggle("hidden", attachedFiles.length === 0);
  for (const file of attachedFiles) {
    box.appendChild(
      attachmentChip({
        name: file.name,
        removeTitle: `Don't send “${file.name}” with this message`,
        onRemove: () => {
          attachedFiles = attachedFiles.filter((f) => f.id !== file.id);
          renderFileAttachments();
          announce(`Removed attachment. ${attachedFiles.length} file(s) attached.`);
        },
      }),
    );
  }
}

//: **Mind maps staged on the message** (MINDMAP_PLAN.md §5 item 11: "a map
//: can be attached to … a chat message, exactly as a file can today").
//:
//: A fourth list rather than folding maps into `attachedNotes`, even though a
//: board *is* an Entry and `note_ids` would have carried it. That is precisely
//: why it must not: a board's `content` is the single line `# My map`, so
//: attaching one as a note sends the model a heading and calls it a map. The
//: request carries `board_ids` separately (routes_chat.py) so the server can
//: send the map's *outline* instead.
let attachedBoards = [];
let lastChatBoardAttachments = [];

//: Four, matching `MAX_CHAT_DOCUMENTS`/`MAX_CHAT_FILES` and the server's own
//: `max_length=4`. An outline is capped at 3,000 characters server-side, so
//: four maps is ~12k, the same ceiling one attached file already has.
const MAX_CHAT_BOARDS = 4;

function attachBoardToChat(id, name) {
  if (!id) return false;
  if (attachedBoards.some((b) => b.id === id)) {
    renderBoardAttachments();
    return true;
  }
  if (attachedBoards.length >= MAX_CHAT_BOARDS) return false;
  attachedBoards.push({ id, name: name || "Mind map" });
  renderBoardAttachments();
  announce(`Attached “${name || "mind map"}”. ${attachedBoards.length} map(s) attached.`);
  return true;
}

function renderBoardAttachments() {
  const box = $("chat-board-attachments");
  if (!box) return;
  box.replaceChildren();
  box.classList.toggle("hidden", attachedBoards.length === 0);
  for (const board of attachedBoards) {
    box.appendChild(
      notebookCard({ kind: "map", id: board.id, name: board.name }, {
        removeTitle: `Don't send “${board.name}” with this message`,
        onRemove: () => {
          attachedBoards = attachedBoards.filter((b) => b.id !== board.id);
          renderBoardAttachments();
          announce(`Removed attachment. ${attachedBoards.length} map(s) attached.`);
        },
      }),
    );
  }
}

//: **Stage one document on the message being written.**
//:
//: The composer has staged documents as removable chips since files could be
//: dropped into chat, but the only way in was that import path, so every
//: *other* surface that wanted to ask the AI about a document had to paste its
//: text into the box instead. Reported about the Documents tab's own button:
//: "the 'check with ai' button in the documents should attach a link to the
//: document or an excerpt from the document to read but in a little attached
//: badge that can be removed so the document text isnt just pasted below."
//:
//: Returns false rather than throwing when it cannot: no id (an unsaved
//: document), or the four-attachment ceiling already reached. The caller
//: decides what to do about it, `docAiReview` falls back to pasting, because
//: silently asking a question about nothing is the worse failure.
function attachDocumentToChat(id, name, kind) {
  if (!id) return false;
  if (attachedDocuments.some((d) => d.id === id)) {
    renderDocumentAttachments();
    return true; // already staged: the badge the caller wanted is on screen
  }
  if (attachedDocuments.length >= MAX_CHAT_DOCUMENTS) return false;
  attachedDocuments.push({ id, name: name || "Document", kind });
  renderDocumentAttachments();
  announce(`Attached “${name || "document"}”. ${attachedDocuments.length} document(s) attached.`);
  return true;
}

function renderDocumentAttachments() {
  const box = $("chat-doc-attachments");
  if (!box) return;
  box.replaceChildren();
  box.classList.toggle("hidden", attachedDocuments.length === 0);
  for (const document_ of attachedDocuments) {
    box.appendChild(
      notebookCard({ kind: document_.kind || "document", id: document_.id, name: document_.name }, {
        removeTitle: `Don't send “${document_.name}” with this message`,
        onRemove: () => {
          attachedDocuments = attachedDocuments.filter((d) => d.id !== document_.id);
          renderDocumentAttachments();
          announce(`Removed attachment. ${attachedDocuments.length} document(s) attached.`);
        },
      }),
    );
  }
}

//: **The passage the user is looking at**, carried from an editing surface to
//: the chat composer. REDESIGN.md §R7.1 item 1, and the request behind it:
//: *"able to highlight text and say something in the chat and the agent gets
//: the context of what is highlighted and cursor position."*
//:
//: One at a time, replaced rather than appended, and that is the difference
//: between this and the three attachment lists above. A selection is *where
//: you are*, not a thing you collect: selecting a second passage means you
//: changed your mind about the first, and a stack of them would send the
//: model four regions of four documents to reconcile.
let attachedSelection = null;

//: What `askAboutSelection` (editor.js) calls. Attaching switches to the chat
//: and puts the caret in the box, because the whole gesture is "select, ask", 
//: leaving the user on the note with a chip they cannot see would be the same
//: number of clicks as before with an extra step of confusion.
function attachSelectionContext(context) {
  attachedSelection = context;
  renderSelectionAttachment();
  switchTab("chat");
  //: **Asking about a passage turns Agent on when it can run** (the owner,
  //: 2026-10-10: "it put it in the chat but I was on "ask" mode, shouldnt it
  //: have been auto put on "agent"??"). A passage is usually something to act
  //: on (rewrite it, file it, link it), which only Agent can do. With no model
  //: and no Needle, Ask answers about the attached passage from the notes, so
  //: the mode is left alone rather than set to one that cannot run.
  const switched = agentModeAvailable() && !$("tools-toggle").checked;
  if (switched) setChatMode("agent");
  const input = $("chat-input");
  if (input) {
    input.focus();
    autoGrow(input);
  }
  announce(`${context.kind === "reading" ? "Text read from" : "Selection from"} ${context.title} attached to your next message.`);
  //: One toast, not two: a caller that says its own sentence (the OCR
  //: workspace) gets `switched` back and adds the mode to it.
  if (switched && !context.quiet) toast("Agent mode is on, so Atlas can act on what you attached.");
  return switched;
}

function clearSelectionAttachment() {
  attachedSelection = null;
  renderSelectionAttachment();
}

function renderSelectionAttachment() {
  const box = $("chat-selection-attachment");
  if (!box) return;
  box.replaceChildren();
  box.classList.toggle("hidden", !attachedSelection);
  if (!attachedSelection) return;
  //: The full passage on hover: a pill can only name where it is from, and
  //: "which selection is this?" is the one question it has to answer.
  const reading = attachedSelection.kind === "reading";
  box.appendChild(
    attachmentChip({
      name: attachedSelection.title,
      icon: reading ? "ph-scan" : "ph-text-aa",
      facts: reading ? "Reading" : `line ${attachedSelection.line}`,
      title: `${attachedSelection.title}${reading ? "" : `, line ${attachedSelection.line}`}: “${attachedSelection.text.replace(/\s+/g, " ").trim().slice(0, 300)}”`,
      removeTitle: "Don't send this with your message",
      onRemove: () => {
        clearSelectionAttachment();
        announce("Selection removed.");
      },
    }),
  );
}

function attachedNotes() {
  return attachedNoteIds
    .map((id) => allEntries.find((e) => e.id === id))
    .filter(Boolean);
}

function noteLabel(entry, length = 40) {
  const text = notePreviewText(entry.content).replace(/\s+/g, " ").trim();
  return text.length > length ? `${text.slice(0, length - 1)}…` : text || "(empty note)";
}

//: **A note's own words are Markdown, and a badge is not a source view.**
//:
//: Reported (INBOX 35 and 40) with a screenshot of chat badges reading
//: `**Ice Breakers:**` and `# CAB432`. The label a badge carries is the
//: note's opening words as they are stored, markers and all: the backend
//: sends it that way on a `grounding` row and on every `touched` item, and
//: `setLabel` writes it with `textContent`, so the reader gets the syntax
//: instead of what it means. The answer directly above renders the same
//: markup properly, which is what makes it read as a bug rather than as a
//: convention.
//:
//: One block-level pass first, for both helpers below. A label is one line,
//: so a heading marker, a quote marker and a bullet have nothing to say in
//: it, and links and images are flattened to their own text: these labels
//: live inside `<button>` chips, where `renderInlineMarkdown`'s real `<a>`
//: would be invalid markup and a click that navigates away from the chat.
//: `safeHref` guards the anchors this app does want; a badge simply does not
//: want one.
function flattenNoteMarkdown(md) {
  //: Front matter is the note's settings, not its words (INBOX 1323).
  return stripFrontmatter(md)
    .replace(/^\s{0,3}(?:#{1,6}\s+|>\s?|[-*+]\s+|\d+[.)]\s+)/gm, "")
    .replace(/!?\[([^\]|]{0,300})[^\]]{0,300}\]\([^)]{0,500}\)?/g, "$1")
    .replace(/\[\[([^[\]]{1,120})\]\]/g, "$1")
    .replace(/\s+/g, " ")
    .trim();
}

//: Plain characters, for anywhere only characters land: a `title`, an
//: `aria-label`, a string handed to the model. Built on `stripMarkdownPreview`
//: because that one already handles the case a truncated label always hits, a
//: slice landing inside `**bold te`, by deleting delimiters outright rather
//: than matching pairs.
function plainText(md) {
  return stripMarkdownPreview(flattenNoteMarkdown(md)).replace(/\s+/g, " ").trim();
}

//: A toggle that is on says so to a screen reader as well as to the eye: the
//: `.active` fill and `aria-pressed` move together (uisweep-1011: the
//: reminders' List and Calendar, Open, All and Done, and Select had the fill
//: only).
function setActiveChoice(button, on) {
  button.classList.toggle("active", on);
  button.setAttribute("aria-pressed", on);
}

//: **A note's or document's name as plain words**, the one way (INBOX 820: a
//: board's Layers row read "Note card: **Current Commit..."). Frontmatter
//: dropped, the first line that has words, its Markdown (heading, quote and
//: list marks, bold, italic, code, links, [[wiki links]]) turned into the
//: words it means. For any label, `title`, `aria-label`, toast or list row
//: that names a note; `limit` cuts at a whole word with an ellipsis. Not
//: `plainText`: that deletes every underscore and asterisk, which would turn
//: `my_file_name` into `myfilename`. `tests/test_ui_recipes.py` bars a
//: hand-rolled `.split("\n")[0]` on a note's content everywhere else.
function noteNamePlain(content, limit = 0) {
  const line = stripFrontmatter(String(content ?? "")).split("\n").map((l) => l.trim()).find(Boolean) || "";
  const name = notePreviewText(flattenNoteMarkdown(line.replace(/^(?:>\s*|[-*+]\s+\[[ xX]\]\s+)+/, ""))).replace(/^[#>\s]+/, "").trim();
  return limit ? clipText(name, limit) : name;
}

//: A badge whose text is a note's own words: `label` in `setLabel`'s grammar,
//: `md` rendered rather than printed (INBOX 35/40). The chip's CSS width does
//: the cutting, between whole rendered characters; only a pathological length
//: (over `length * 4`) falls back to a plain character cut.
function setNoteLabel(el, label, md, length = 40) {
  const text = String(label ?? "");
  const match = PH_LABEL.exec(text);
  const prefix = (match ? text.slice(match[0].length) : text).trim();
  const flat = flattenNoteMarkdown(md) || "(empty note)";
  const generousBudget = length * 4;
  const plain = plainText(flat) || "(empty note)";
  const holder = document.createElement("span");
  if (plain.length > generousBudget) {
    holder.textContent = `${plain.slice(0, generousBudget - 1)}…`;
  } else {
    // `compact`, so an image becomes its alt text rather than a thumbnail
    // inside a chip; `dismissible: false` for the same reason, there is no
    // room for a remove affordance on a badge.
    renderInlineMarkdown(holder, flat, null, true, { dismissible: false });
  }
  el.replaceChildren();
  if (match) {
    const icon = document.createElement("i");
    icon.className = `ph ph-${match[1]} ph-lead`;
    icon.setAttribute("aria-hidden", "true");
    holder.className = "ph-text";
    el.append(icon);
  }
  // Its own element now, not text prepended into `holder` (chat-b.md item
  // 2): the two need to survive a chip's ellipsis differently. The ordinal
  // ("1.") has to stay fully visible always, or a truncated "5. Some not…"
  // reads as "some note starting with 5", not "note five"; `flex-shrink: 0`
  // on `.note-label-prefix` is what the CSS side of that is. `holder` keeps
  // the `.ph-text` class and stays the ellipsis target every existing
  // per-chip rule (`.answer-related-chip > .ph-text` and its siblings) is
  // already keyed on, so the prefix element is additive, not a rename.
  if (prefix) {
    const prefixEl = document.createElement("span");
    prefixEl.className = "note-label-prefix";
    prefixEl.textContent = prefix;
    el.append(prefixEl);
  }
  if (match) el.append(holder);
  else el.append(...holder.childNodes);
  return el;
}

function renderAttachments() {
  const box = $("chat-attachments");
  box.replaceChildren();
  const notes = attachedNotes();
  box.classList.toggle("hidden", notes.length === 0);
  $("attach-note").classList.toggle("has-attachments", notes.length > 0);
  for (const entry of notes) {
    box.appendChild(
      notebookCard({ kind: "note", id: entry.id, name: entry.content }, {
        removeTitle: `Remove “${noteNamePlain(entry.content, 24) || "this note"}”`,
        onRemove: () => {
          attachedNoteIds = attachedNoteIds.filter((id) => id !== entry.id);
          renderAttachments();
          renderNotePickerList();
          announce(`Removed attachment. ${attachedNoteIds.length} note(s) attached.`);
        },
      }),
    );
  }
}

//: **Which store the picker is showing.** Asked for directly: "I want to be
//: able to attach not just existing notes to a chat for context, but also
//: already uploaded files, documents, and images." The paperclip beside this
//: button uploads something new; this picker is for what the notebook holds.
let notePickerSource = "notes";

//: Fetched once per opening (`openNotePicker` empties it) and per source, not
//: all up front: a notebook can hold thousands of files, and a session that
//: only wanted a note never looks at the other lists. It used to be emptied
//: never, so a document written after the first opening was not offered
//: until a reload.
const notePickerCache = { documents: null, files: null, images: null, maps: null };

//: "In Weekly review", or "In Weekly review and 2 more": where a file or a
//: picture is used, which places it better than a generated filename does.
function notePickerUsedIn(row) {
  const used = Array.isArray(row.used_by) ? row.used_by : [];
  const first = used[0]?.label;
  if (!first) return "";
  return used.length > 1 ? `In ${first} and ${used.length - 1} more` : `In ${first}`;
}

//: One line of facts, the parts that exist joined by a middle dot.
function notePickerFacts(...parts) {
  return parts.filter(Boolean).join(" · ");
}

//: One row's identity, label, icon, meta line and "is it attached" test, per
//: source. A table rather than five branches in the renderer: the renderer is
//: the same row for every source, and five copies of it is how they drift.
//: `meta` returns the nodes of the row's second line; `thumb` (images only)
//: puts the picture where the others have an icon; `nouns` names the source
//: in the loading, empty and truncation lines.
function notePickerShape(source) {
  if (source === "documents") {
    return {
      nouns: "documents",
      label: (row) => row.title || "Untitled document",
      //: A document has no rendered page anywhere in the app, so its tile
      //: says its kind: prose, a table or code (`file_type`, op4-1005).
      icon: (row) => {
        const type = row.file_type || "md";
        if (type === "md" || type === "txt") return "ph:file-text";
        return type === "csv" ? "ph:table" : "ph:file-code";
      },
      meta: (row) => {
        const when = relativeTime(row.updated_at);
        return [notePickerFacts(when && `Edited ${when}`, row.words && row.file_type !== "mmd" ? nounCount(row.words, "word") : "")];
      },
      search: (row) => `${row.title || ""} ${row.preview || ""}`,
      isOn: (row) => attachedDocuments.some((d) => d.id === row.id),
      add: (row) => attachDocumentToChat(row.id, row.title || "Document", row.file_type === "mmd" ? "diagram" : undefined),
      remove: (row) => {
        attachedDocuments = attachedDocuments.filter((d) => d.id !== row.id);
        renderDocumentAttachments();
      },
      empty: "No documents yet.",
    };
  }
  if (source === "maps") {
    return {
      nouns: "mind maps",
      label: (row) => row.title || "Untitled map",
      icon: () => "ph:tree-structure",
      //: The map's own shape, the Library's row-sized `mapPreview` (an empty
      //: map draws the shared ghost), so two maps are told apart by layout.
      face: (row) => mapPreview(row, { size: "row" }),
      //: The count is what the row adds over its title, and the reason this
      //: list comes from `/whiteboard/boards` rather than `allEntries`.
      meta: (row) => [notePickerFacts(mapCountLabel(row), relativeTime(row.updated_at))],
      search: (row) => row.title || "",
      isOn: (row) => attachedBoards.some((b) => b.id === row.id),
      add: (row) => attachBoardToChat(row.id, row.title || "Mind map"),
      remove: (row) => {
        attachedBoards = attachedBoards.filter((b) => b.id !== row.id);
        renderBoardAttachments();
      },
      empty: "No mind maps yet.",
    };
  }
  if (source === "files") {
    return {
      nouns: "files",
      label: (row) => row.original_name || "File",
      //: The file's own glyph, by its extension, from the table every other
      //: file surface reads (`attachmentIconClass`, notes-list.js).
      icon: (row) => `ph:${(attachmentIconClass(row.url || "", row.original_name || "file") || "ph-file").replace(/^ph-/, "")}`,
      //: A PDF shows its first page where the server can draw one
      //: (`has_pages`, the Library Files row's own test and URL); the row
      //: puts the glyph back if the page fails to load.
      face: (row) => (row.has_pages ? notePickerPage(row.page || `/files/${row.id}/pdf-page/0`) : null),
      meta: (row) => [notePickerFacts(
        ((row.original_name || "").includes(".") ? row.original_name.split(".").pop().toUpperCase() : (row.mime || "").split("/").pop()),
        row.size_bytes ? formatFileSize(row.size_bytes) : "",
        notePickerUsedIn(row),
      )],
      search: (row) => `${row.original_name || ""} ${row.caption || ""}`,
      isOn: (row) => attachedFiles.some((f) => f.id === row.id),
      add: (row) => attachLibraryFile(row.id, row.original_name || "File"),
      remove: (row) => {
        attachedFiles = attachedFiles.filter((f) => f.id !== row.id);
        renderFileAttachments();
      },
      empty: "No files yet.",
      upload: true,
    };
  }
  if (source === "images") {
    const name = (row) => row.original_name || row.filename || "Image";
    return {
      nouns: "images",
      grid: true,
      label: name,
      //: The picture itself, token-gated through `mediaSrc` (an `<img src>`
      //: cannot send the auth header). An Attachment's url is `/files/{id}`.
      thumb: (row) => mediaSrc(row.url || `/media/${row.filename}`),
      //: A caption is a sentence about the picture, which a camera's filename
      //: is not; failing one, where it is used; failing both, the name.
      meta: (row) => [row.caption || notePickerUsedIn(row) || name(row)],
      search: (row) => `${name(row)} ${row.caption || ""} ${notePickerUsedIn(row)}`,
      isOn: (row) =>
        row.store === "file"
          ? attachedFiles.some((f) => f.id === row.id)
          : attachedImages.some((i) => i.id === row.id),
      //: A library picture is attached by id, with no staging and no object
      //: URL: the bytes are already on the server.
      add: (row) => {
        if (row.store === "file") return attachLibraryFile(row.id, name(row));
        if (attachedImages.length >= 4) return false;
        attachedImages.push({ id: row.id, url: row.url || `/media/${row.filename}`, name: name(row) });
        renderImageAttachments();
        return true;
      },
      remove: (row) => {
        if (row.store === "file") {
          attachedFiles = attachedFiles.filter((f) => f.id !== row.id);
          renderFileAttachments();
          return;
        }
        attachedImages = attachedImages.filter((i) => i.id !== row.id);
        renderImageAttachments();
      },
      empty: "No images yet.",
      upload: true,
    };
  }
  return {
    nouns: "notes",
    label: (entry) => noteLabel(entry, 70),
    icon: () => "ph:note",
    //: The category is a dot in its own colour and quiet text (the Library
    //: card's shape, INBOX 467), never a filled badge; `paintCategoryDot` is
    //: the one place a category's colour is read.
    meta: (entry) => {
      const cat = document.createElement("span");
      cat.className = "note-picker-category";
      cat.textContent = entry.category || "Unfiled";
      paintCategoryDot(cat, entry.category);
      const when = relativeTime(entry.updated_at || entry.created_at);
      return when ? [cat, ` · ${when}`] : [cat];
    },
    search: (entry) => `${entry.content} ${(entry.tags || []).join(" ")} ${entry.category}`,
    isOn: (entry) => attachedNoteIds.includes(entry.id),
    add: (entry) => {
      if (!attachedNoteIds.includes(entry.id)) attachedNoteIds.push(entry.id);
      renderAttachments();
    },
    remove: (entry) => {
      attachedNoteIds = attachedNoteIds.filter((id) => id !== entry.id);
      renderAttachments();
    },
    empty: "No notes yet.",
  };
}

//: The empty state recipe (`.empty-state`): one sentence and, where there is
//: one, the one thing to do about it.
function notePickerEmpty(list, text, action) {
  const li = document.createElement("li");
  li.className = "empty-state note-picker-empty";
  const line = document.createElement("p");
  line.textContent = text;
  li.appendChild(line);
  if (action) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "ghost small";
    setLabel(button, action.label);
    button.addEventListener("click", action.run);
    li.appendChild(button);
  }
  list.appendChild(li);
}

function notePickerPage(url) {
  const img = document.createElement("img");
  img.alt = "";
  img.loading = "lazy";
  img.src = mediaSrc(url);
  return img;
}

//: The list is one tab stop: the row at `index` takes it, the rest are -1.
function notePickerRoving(list, index) {
  const boxes = [...list.querySelectorAll(".note-picker-box")];
  boxes.forEach((box, i) => {
    box.tabIndex = i === index ? 0 : -1;
  });
  return boxes;
}

//: How many cells one row of the image grid holds, read from the layout
//: rather than assumed, since the column count follows the panel's width.
function notePickerColumns(list) {
  if (!list.classList.contains("is-grid")) return 1;
  const cells = [...list.querySelectorAll(".note-picker-cell")];
  if (!cells.length) return 1;
  const top = cells[0].getBoundingClientRect().top;
  const n = cells.filter((cell) => Math.abs(cell.getBoundingClientRect().top - top) < 2).length;
  return Math.max(1, n);
}

//: **The keys** (INBOX 485): ↑ ↓ walk the rows (← → as well in the image
//: grid, and between the source tabs), Space or Enter ticks the row, Enter in the search field is Done,
//: Escape closes, Home and End jump, and a letter typed on a row goes to the
//: search field. ↓ from the field enters the list; ↑ from its first row
//: returns.
function notePickerKeydown(event) {
  if (event.altKey || event.ctrlKey || event.metaKey) return;
  const list = $("note-picker-list");
  const search = $("note-picker-search");
  const target = event.target;
  const tab = target.closest?.("#note-picker-sources [data-picker-source]");
  if (tab && (event.key === "ArrowLeft" || event.key === "ArrowRight")) {
    const tabs = [...document.querySelectorAll("#note-picker-sources [data-picker-source]")];
    const step = event.key === "ArrowRight" ? 1 : -1;
    const next = tabs[(tabs.indexOf(tab) + step + tabs.length) % tabs.length];
    event.preventDefault();
    setNotePickerSource(next.dataset.pickerSource, { focus: "tab" });
    return;
  }
  const boxes = [...list.querySelectorAll(".note-picker-box")];
  const at = boxes.indexOf(target);
  if (target === search) {
    if (event.key === "ArrowDown" && boxes.length) {
      event.preventDefault();
      notePickerRoving(list, 0);
      boxes[0].focus();
    } else if (event.key === "Enter") {
      event.preventDefault();
      $("note-picker-done").click();
    }
    return;
  }
  if (at < 0) return;
  const cols = notePickerColumns(list);
  const grid = cols > 1 || list.classList.contains("is-grid");
  let to = null;
  if (event.key === "ArrowDown") to = Math.min(boxes.length - 1, at + cols);
  else if (event.key === "ArrowUp") to = at - cols;
  else if (grid && event.key === "ArrowRight") to = Math.min(boxes.length - 1, at + 1);
  else if (grid && event.key === "ArrowLeft") to = Math.max(0, at - 1);
  else if (event.key === "Home") to = 0;
  else if (event.key === "End") to = boxes.length - 1;
  else if (event.key === "Enter") {
    //: C09: ticks the row; Done is Enter in the search field.
    event.preventDefault();
    target.click();
    return;
  } else if (event.key.length === 1 && event.key !== " ") {
    search.focus();
    return;
  }
  if (to === null) return;
  event.preventDefault();
  if (to < 0) {
    search.focus();
    return;
  }
  notePickerRoving(list, to);
  boxes[to].focus();
  boxes[to].closest("li")?.scrollIntoView({ block: "nearest" });
}

//: Switching source: the tab, the field's hint, and the list. The search is
//: cleared, since "cover" typed against notes means nothing against a list of
//: filenames, and a picker that opens on Files with a stale query and no rows
//: reads as an empty library.
function setNotePickerSource(source, { focus = "search" } = {}) {
  notePickerSource = source;
  for (const button of document.querySelectorAll("#note-picker-sources [data-picker-source]")) {
    const on = button.dataset.pickerSource === source;
    button.classList.toggle("active", on);
    button.setAttribute("aria-selected", on);
    button.tabIndex = on ? 0 : -1;
    if (on && focus === "tab") button.focus();
  }
  const search = $("note-picker-search");
  search.value = "";
  search.placeholder = `Search your ${notePickerShape(source).nouns}…`;
  renderNotePickerList();
  if (focus === "search") search.focus();
}

// **On a phone the panel is a sheet**, the same fix `openChatDockMore`
// already uses for the same shape of problem. Measured (INBOX 431, the
// chat attach redesign): the popover hangs above the composer with
// `bottom: calc(100% + 0.5rem)`, and at 390 the composer wraps into several
// rows, tall enough that the popover's own top half lands above where
// `#tab-chat` (the scrolling ancestor) actually paints -- present in the
// DOM, `getBoundingClientRect()` reporting a real box, and invisible on
// screen the whole time, with the chat's own empty state showing through
// where it should have been.
let notePickerSheetClose = null;

function openNotePicker() {
  const panel = $("note-picker-panel");
  for (const key of Object.keys(notePickerCache)) notePickerCache[key] = null;
  panel.classList.remove("hidden");
  $("attach-note").setAttribute("aria-expanded", "true");
  renderNotePickerList();
  if (window.matchMedia(PHONE_TABS).matches) {
    const home = { parent: panel.parentElement, next: panel.nextSibling };
    //: The sheet's own head already carries a title and a Close; this
    //: panel's `.dialog-head` (built for the floating popover) would only
    //: duplicate both.
    const head = panel.querySelector(".dialog-head");
    head?.classList.add("hidden");
    notePickerSheetClose = openSheet({
      label: "Attach",
      name: "attach",
      returnFocus: $("attach-note"),
      build: (card) => {
        card.classList.add("attach-card");
        card.appendChild(panel);
      },
      onClose: () => {
        notePickerSheetClose = null;
        head?.classList.remove("hidden");
        home.parent.insertBefore(panel, home.next);
        panel.classList.add("hidden");
        $("attach-note").setAttribute("aria-expanded", "false");
      },
    });
    $("note-picker-search").focus();
    return;
  }
  //: The floating popover hides the messages' action rows behind it (a class
  //: the sheet's CSS reads; not a `:has()` on the tab, AI9).
  $("tab-chat").classList.add("note-picker-open");
  $("note-picker-search").focus();
}

function closeNotePicker() {
  if (notePickerSheetClose) {
    notePickerSheetClose();
    return;
  }
  $("note-picker-panel").classList.add("hidden");
  $("tab-chat").classList.remove("note-picker-open");
  $("attach-note").setAttribute("aria-expanded", "false");
}

function notePickerOpen() {
  return !$("note-picker-panel").classList.contains("hidden");
}

// The answer-length/persona disclosure (§37C): same open/close shape as the
// note picker above, just for a settings pair instead of a list.
function chatDockMoreOpen() {
  return !$("chat-dock-more-panel").classList.contains("hidden");
}

// **On a phone the panel is a sheet** (UI_MODERNISATION_PLAN Phase 11 item
// 12). A popover hanging above a composer at the foot of a 390px window has
// the keyboard under it and the transcript over it; the sheet recipe is the
// phone's dialog. The panel itself moves into the sheet and back on close,
// never a copy, so its selects, its persona peek and every handler on them
// are the ones the desktop uses. `dockChatTools` has already moved the model
// picker and the tool toggles into it at that width.
let chatDockMoreSheetClose = null;

function openChatDockMore() {
  const panel = $("chat-dock-more-panel");
  const button = $("chat-dock-more-btn");
  panel.classList.remove("hidden");
  button.setAttribute("aria-expanded", "true");
  if (!window.matchMedia(PHONE_TABS).matches) return;
  const home = panel.parentElement;
  chatDockMoreSheetClose = openSheet({
    label: "How it answers",
    name: "chat-answers",
    returnFocus: button,
    build: (card) => {
      card.classList.add("chat-answers-card");
      card.appendChild(panel);
    },
    onClose: () => {
      chatDockMoreSheetClose = null;
      home.appendChild(panel);
      panel.classList.add("hidden");
      button.setAttribute("aria-expanded", "false");
    },
  });
}

function closeChatDockMore() {
  if (chatDockMoreSheetClose) {
    chatDockMoreSheetClose();
    return;
  }
  $("chat-dock-more-panel").classList.add("hidden");
  $("chat-dock-more-btn").setAttribute("aria-expanded", "false");
}

//: A stray key typed against the last word ("dentist\\") goes before the bubble
//: shows it, as the server already reads it (question_noise); an emoticon
//: (":\\") and a lone key stay.
function chatTidyTyped(text) {
  const m = /([\w?.!)"'])[\\|`~^]+\s*$/.exec(text);
  return m ? text.slice(0, m.index + 1) : text;
}

//: **A message sent while the answer on screen is still coming waits its
//: turn** (INBOX 1321) in the composer queue (chat.js). Stop shows exactly
//: while that answer streams.
async function sendChatMessage(preset, opts = {}) {
  const input = $("chat-input");
  if (chatQueue.busy()) {
    chatQueue.take(chatTidyTyped((preset ?? input.value).trim()));
    if (preset == null) {
      input.value = "";
      input.dispatchEvent(new Event("input"));
    }
    return;
  }
  //: After Stop the queue is held, not sent (owner, 2026-11-11): Send from the box runs the waiting
  //: messages oldest first, what is typed going last. No turn of its own: the `finally` drains the queue.
  const resume = preset == null && chatQueue.held && chatQueue.items.length > 0;
  if (resume) {
    const typed = chatTidyTyped(input.value.trim());
    if (typed) {
      chatQueue.items.push(typed);
      input.value = "";
      input.dispatchEvent(new Event("input"));
    }
  }
  chatQueue.held = false;
  try {
    if (resume) return;
    //: The turn itself is lazy (chat-turn.js, warmed when the box takes focus).
    if (!(await ensureModule("chatTurn"))) return lazyLoadFailed();
    return await chatSendTurn(preset, opts);
  } finally {
    chatQueue.finishing.delete(opts.finishing);
    chatQueue.next();
  }
}

//: Saved content may carry Plan mode's block after the words.
const followupMatches = (sent, ref) => Boolean(sent) && (sent === ref || sent.startsWith(ref));

//: Chat's and Ask's trail; `open(i)` is a press on the i-th question.
function followupTrail(questions, open) {
  const nav = document.createElement("nav");
  nav.className = "chat-trail";
  nav.setAttribute("aria-label", "This question followed on from");
  const head = document.createElement("span");
  head.className = "chat-trail-head";
  setLabel(head, "ph:arrow-bend-down-right Follow-up of");
  const list = document.createElement("ol");
  list.className = "chat-trail-list";
  questions.forEach((text, i) => {
    const item = document.createElement("li");
    const link = document.createElement("button");
    link.type = "button";
    link.className = "link-button chat-trail-link";
    link.textContent = text;
    link.title = text;
    link.addEventListener("click", () => open(i, link));
    item.appendChild(link);
    list.appendChild(item);
  });
  nav.append(head, list);
  return nav;
}

// --- leaving a conversation while it is still answering ------------------------
// The composer is handed back to whatever is on screen while the stream keeps
// running (not an abort: the answer is saved to the thread that asked it).
//: The streaming turn: its conversation, that conversation's title when sent,
//: and the live nodes. Set once in sendChatMessage, cleared when it ends.
let chatStreaming = null;

// --- how long this answer has been coming --------------------------------------
// ("can there be an active timer on responses"): ticked by a timer so it moves
// while the model is silent, and drawn in the bubble it times, removed when
// that bubble finishes; the metadata line keeps the final duration.
let chatTimerInterval = null;
let chatTimerStartedAt = 0;
//: The live counter's node, mounted inside the assistant bubble being
//: streamed. Null between turns: `paintChatTimer` is a no-op then.
let chatTimerBox = null;

function releaseChatComposer({ announce = true } = {}) {
  //: Called by every way out of a chat: the page it read is that chat's.
  chatWeb.lastUrl = null;
  if (!chatController || !chatStreaming) return;
  $("chat-messages").removeAttribute("aria-busy"); // this transcript is no longer the one streaming
  const input = $("chat-input");
  input.disabled = false;
  show("chat-send");
  hide("chat-stop");
  const status = $("chat-status");
  status.textContent = "";
  status.classList.remove("error");
  // The timer belongs to the composer, which has just been handed back to a
  // different conversation: leaving it ticking would time this chat's turn
  // against the next chat's empty box.
  chatTimerBox?.remove();
  chatTimerBox = null;
  $("chat-elapsed")?.classList.add("hidden"); // legacy composer slot, kept hidden
  // Once per stream, not once per switch. Reported: leaving and returning
  // repeatedly repeated the notice, and named whichever chat had just been
  // left rather than the one actually being answered. The title is the one
  // captured when the message was sent, for the same reason.
  if (announce && !chatStreaming.announced) {
    chatStreaming.announced = true;
    toast(
      `Still answering in “${chatStreaming.title}”: the reply will appear there.`
    );
  }
}

//: A private chat with messages asks before it is left (chat-private.js).
function chatLeaveHeld(retry) {
  if (!chatConv.private || !(chatConv.turns.length || chatStreaming?.conv === chatConv)) return false;
  chatPrivateLeave(retry);
  return true;
}

function syncChatPrivate() {
  $("chat-private-mark").hidden = !chatConv.private;
  $("chat-private-toggle").ariaPressed = String(!!chatConv.private);
}

function newChatConversation() {
  if (chatLeaveHeld(newChatConversation)) return;
  releaseChatComposer();
  recordTabVisit("chat", "new");
  chatConv = { id: null, turns: [] };
  chatPendingTitle = null;
  // A summary belongs to the conversation it summarised (§35I).
  chatSummary = null;
  renderCompressionState();
  lastChatQuestion = "";
  // A pending question belongs to the conversation that asked it, starting
  // a new one must not silently answering_agent-tag whatever gets typed first.
  chatAwaitingAgentAnswer = false;
  // batch-a.md's last item, its actual cause: `#chat-suggest` is on
  // loan to `.chat-empty` (see `openConversation`'s own long comment below)
  // whenever the pane it is leaving was itself empty with suggestions
  // already shown. A bare `replaceChildren()` throws the loaned element away
  // with the rest of `.chat-empty` rather than sending it home the way
  // `clearChatEmptyState` already knows how to; a `loadChatSuggestions()`
  // call still in flight for the *old* pane then resolves onto an id that no
  // longer exists anywhere in the document. `clearChatEmptyState` is a no-op
  // when there is no `.chat-empty` to begin with, so this costs nothing on
  // the common path (a chat that already had messages).
  clearChatEmptyState();
  $("chat-messages").replaceChildren();
  $("chat-title").textContent = "New chat";
  renderChatUsage(0);
  //: A fresh pane has no turn to measure, so the meter goes away rather than
  //: keeping the last conversation's number over an empty one.
  renderChatContextMeter(null);
  renderChatEmptyState();
  loadChatSuggestions();
  //: INBOX 34: `replaceChildren()` above fires no scroll event, so without
  //: this the jump-to-latest pill (and, before NO_SCROLL_TOP_TABS below,
  //: the reused down-arrow button) kept whatever visibility the *previous*
  //: conversation left them in, both correctly hidden on the tab's own
  //: first load but stale, and wrongly showing, the moment "+ New" was
  //: clicked from a conversation you had scrolled away in. Both controls
  //: re-check the actual (now empty) pane immediately instead of waiting
  //: for a scroll or resize that a brand-new chat may never get.
  syncChatJumpLatest();
  scrollTopUpdate?.();
  syncChatPrivate();
}

// Delete the conversation open in the main pane, saved or not.
//
// Saved chats already had a delete (sidebar kebab menu) and deleting a
// conversation's last turn deletes the conversation with it (deleteChatTurn
// above). What was missing was the chat you're actually looking at: a
// brand-new, never-sent pane had no affordance but "+ New", which resets it
// without saying so. So: nothing saved yet (no id, no turns) just resets
// silently, there is nothing to lose and nothing to confirm, and anything
// that made it to the server asks first, the same confirm the sidebar uses.
async function deleteCurrentChat() {
  if (chatConv.private || (chatConv.id === null && !chatConv.turns.length)) {
    newChatConversation();
    return;
  }
  if (!(await confirmDialog("Delete this chat?"))) return;
  let gone = null;
  if (chatConv.id !== null) {
    try {
      gone = await apiJson(`/conversations/${chatConv.id}`, { method: "DELETE" });
    } catch {
      toast("Couldn't delete this chat.", true);
      return;
    }
  }
  newChatConversation();
  loadConversationList();
  // Document delete already confirms this way; chat delete silently reset
  // the pane instead, the same success-feedback gap in miniature.
  if (gone) chatDeleteUndo(gone);
}

//: A deleted chat comes back with Undo (undo-1005), from all three of its
//: Deletes: the DELETE answers with the whole row (a chat is one row), and
//: `POST /conversations/restore` makes it again under its own id, pinned,
//: archived and dated as it was. `after` repaints the list it was deleted from.
function chatDeleteUndo(gone, after = () => {}) {
  if (!gone?.restore) return;
  const row = gone.restore;
  const remake = async () => {
    await apiJson("/conversations/restore", { method: "POST", body: JSON.stringify(row) });
    loadConversationList();
    after();
  };
  offerUndo(`Deleted the chat “${row.title}”`, "Chat deleted.", remake, async () => {
    await apiJson(`/conversations/${row.id}`, { method: "DELETE" });
    if (chatConv.id === row.id) newChatConversation();
    loadConversationList();
    after();
  });
}

//: **Every chat write is on the undo bar** (CHAT_PLAN 8 row 5): the helpers
//: are chat-undo.js, fetched on the first write, out of the boot scripts.
async function promptTitle(message, initial) {
  const asked = promptDialog(message, initial);
  //: A blank title cannot be saved (the field is required, so Save says
  //: so in place), which makes "" mean one thing: Esc or Cancel, and that
  //: changes nothing, so nothing is said (AI19; it toasted "Title kept.").
  const field = document.querySelector(".prompt-card input");
  field.maxLength = 120;
  field.required = true;
  return (await asked)?.trim() || null;
}

function chatWriteRecord(name, ...args) {
  lazyScript("/js/chat-undo.js").then(() => window[name](...args));
}

// Download the open conversation as clean Markdown (questions + answers).
async function exportChatMarkdown() {
  if (!chatConv.turns.length) {
    toast("Nothing to export yet, ask something first.");
    return;
  }
  const title = $("chat-title").textContent || "Chat";
  let md = `# ${title}\n\n`;
  for (const turn of chatConv.turns) {
    md += `**You:** ${turn.question}\n\n${turn.answer}\n\n---\n\n`;
  }
  const slug =
    title.toLowerCase().replace(/[^\w]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 40) ||
    "chat";
  await saveFile(`${slug}.md`, new Blob([md], { type: "text/markdown" }));
}
