// chat-attach.js: extract notes, attaching notes and images, the attach button,
// follow-up chips, the answer timer. Moved out of app.js on 2026-09-26 as one
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
    renderExtractPreview(body);
  } catch (error) {
    status.classList.add("error");
    status.textContent = error.message;
  }
}

// What a link's `kind` (from `ai.extractor`) reads as in the preview.
const EXTRACT_LINK_KIND_LABEL = { sibling: "new note", source: "source", related: "related" };

function extractRefLabel(ref, notes) {
  if (ref.startsWith("existing:")) return "an existing note";
  const note = notes.find((n) => n.ref === ref);
  return note ? note.title || clipText(notePreviewText(note.content), 30) : ref;
}

function renderExtractPreview(body) {
  const status = $("extract-status");
  status.classList.remove("error");
  status.textContent =
    body.message ||
    `${body.notes.length} note${body.notes.length === 1 ? "" : "s"} proposed: review, then save.`;

  // Built with createElement, not an `innerHTML` template per iteration.
  // The old version escaped everything correctly, so this is not a security
  // fix: it is this file's own rule (see the header comment: "All DOM nodes
  // are built with createElement/textContent, never innerHTML"), and the rule
  // exists because an `innerHTML` assignment inside a loop re-invokes the HTML
  // parser once per proposed note, and because the next person to add a field
  // here is one forgotten `escapeHtml` away from an injection.
  const field = (type, className, { placeholder, label, value } = {}) => {
    const input = document.createElement("input");
    input.type = type;
    input.className = className;
    if (placeholder) input.placeholder = placeholder;
    if (label) input.setAttribute("aria-label", label);
    if (value !== undefined) input.value = value;
    return input;
  };

  const list = $("extract-notes-list");
  list.replaceChildren();
  for (const note of body.notes) {
    const card = document.createElement("div");
    card.className = "extract-note-card";
    card.dataset.ref = note.ref;

    const keepLabel = document.createElement("label");
    keepLabel.className = "row align-center checkbox-label";
    const keep = field("checkbox", "extract-note-keep");
    keep.checked = true;
    keepLabel.append(keep, document.createTextNode(" Keep this note"));

    const title = field("text", "extract-note-title", {
      placeholder: "Title (optional)",
      label: "Note title",
      value: note.title || "",
    });

    const content = document.createElement("textarea");
    content.className = "extract-note-content";
    content.rows = 6;
    content.setAttribute("aria-label", "Note content");
    content.value = note.content;

    const meta = document.createElement("div");
    meta.className = "row extract-note-meta";
    const category = document.createElement("span");
    category.className = "muted extract-note-category";
    category.textContent = `Filed under: ${note.category}`;
    meta.append(
      category,
      field("text", "extract-note-tags", {
        placeholder: "Tags, comma separated",
        label: "Tags for this note",
      })
    );

    card.append(keepLabel, title, content, meta);
    list.appendChild(card);
  }

  const linksBox = $("extract-links-list");
  linksBox.replaceChildren();
  if (body.links.length) {
    const heading = document.createElement("p");
    heading.className = "muted";
    heading.textContent = "Links";
    linksBox.appendChild(heading);
  }
  for (const link of body.links) {
    const row = document.createElement("label");
    row.className = "row align-center extract-link-row checkbox-label";
    row.dataset.sourceRef = link.source_ref;
    row.dataset.targetRef = link.target_ref;
    const kindLabel = EXTRACT_LINK_KIND_LABEL[link.kind] || "note";
    // Raw, not escaped: this now goes into a text node, where escaping would
    // render the entities literally ("A &amp; B" on screen).
    const target = link.target_preview || extractRefLabel(link.target_ref, body.notes);
    const keep = document.createElement("input");
    keep.type = "checkbox";
    keep.className = "extract-link-keep";
    keep.checked = true;
    const desc = document.createElement("span");
    desc.className = "extract-link-desc";
    const why = document.createElement("span");
    why.className = "muted";
    why.textContent = `(${kindLabel}: ${link.reason})`;
    desc.append(
      document.createTextNode(
        `${extractRefLabel(link.source_ref, body.notes)} → ${target} `
      ),
      why
    );
    row.append(keep, desc);
    linksBox.appendChild(row);
  }

  $("extract-commit").disabled = body.notes.length === 0;
}

function closeExtractPreview() {
  $("extract-panel").classList.add("hidden");
  extractProposal = null;
}

async function commitExtractPreview() {
  if (!extractProposal) return;
  const keptRefs = new Set();
  const notes = [];
  for (const card of $("extract-notes-list").querySelectorAll(".extract-note-card")) {
    if (!card.querySelector(".extract-note-keep").checked) continue;
    const ref = card.dataset.ref;
    const original = extractProposal.notes.find((n) => n.ref === ref);
    if (!original) continue;
    const content = card.querySelector(".extract-note-content").value.trim();
    if (!content) continue; // an edited-down-to-nothing note is dropped, not saved empty
    keptRefs.add(ref);
    notes.push({
      ref,
      title: card.querySelector(".extract-note-title").value.trim(),
      content,
      category: original.category,
      tags: card
        .querySelector(".extract-note-tags")
        .value.split(",")
        .map((t) => t.trim())
        .filter(Boolean),
    });
  }
  if (!notes.length) {
    toast("Keep at least one note to save.");
    return;
  }

  const links = [];
  for (const row of $("extract-links-list").querySelectorAll(".extract-link-row")) {
    if (!row.querySelector(".extract-link-keep").checked) continue;
    const sourceRef = row.dataset.sourceRef;
    const targetRef = row.dataset.targetRef;
    if (!keptRefs.has(sourceRef)) continue; // its source note was dropped
    if (!targetRef.startsWith("existing:") && !keptRefs.has(targetRef)) continue; // its sibling was dropped
    const original = extractProposal.links.find(
      (l) => l.source_ref === sourceRef && l.target_ref === targetRef
    );
    if (original) links.push({ source_ref: sourceRef, target_ref: targetRef, reason: original.reason });
  }

  $("extract-commit").disabled = true;
  const status = $("extract-status");
  status.classList.remove("error");
  status.textContent = "Saving…";
  try {
    const result = await apiJson("/entries/extract/commit", {
      method: "POST",
      body: JSON.stringify({
        notes,
        links,
        source_document_id: extractProposal.source_document_id || null,
      }),
    });
    closeExtractPreview();
    const madeIds = result.notes.map((n) => n.id).filter((id) => id != null);
    if (madeIds.length) {
      pushRoutePairUndo(
        `Saved ${madeIds.length} extracted note${madeIds.length === 1 ? "" : "s"}`,
        madeIds.map((id) => [`/entries/${id}`, "DELETE"]),
        madeIds.map((id) => [`/entries/${id}/restore`, "POST"]),
        () => refreshEntries(madeIds)
      );
    }
    toast(`Saved ${result.notes.length} note${result.notes.length === 1 ? "" : "s"}.`);
    await loadEntries();
  } catch (error) {
    status.classList.add("error");
    status.textContent = error.message;
    $("extract-commit").disabled = false;
  }
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
    const chipEl = document.createElement("span");
    // Reuses the note-composer's own image-attachment look
    // (04-chat-dock-appearance.css) rather than inventing a second one.
    chipEl.className = "chip attachment-chip attachment-chip-image";
    const thumb = document.createElement("img");
    // A staged image has no server url yet, its bytes are local, so the
    // object URL is what draws it. `mediaSrc` is still right for one already
    // uploaded: a plain <img> never attaches X-Auth-Token.
    thumb.src = image.objectUrl || mediaSrc(image.url);
    thumb.alt = "";
    const remove = document.createElement("button");
    remove.className = "attachment-remove";
    remove.type = "button";
    setLabel(remove, "ph:x");
    remove.title = "Remove this image";
    remove.setAttribute("aria-label", remove.title);
    remove.addEventListener("click", async () => {
      attachedImages = attachedImages.filter((img) => img.key !== image.key);
      // An object URL is a document-lifetime reference to a Blob: dropping the
      // array entry alone leaks the image's bytes for as long as the tab is
      // open.
      if (image.objectUrl) URL.revokeObjectURL(image.objectUrl);
      renderImageAttachments();
      announce(`Removed image. ${attachedImages.length} image(s) attached.`);
      // Nothing to tell the server about: a staged image has never been
      // uploaded (see `attachImageFiles`). The delete call that used to live
      // here existed because attaching uploaded immediately, so removing had
      // to clean up after it, staging removes the need rather than the
      // symptom. An image that *is* already on the server (a regenerate
      // re-using an earlier message's attachments) keeps its id and is left
      // alone, because the sent message still references it.
    });
    chipEl.append(thumb, remove);
    box.appendChild(chipEl);
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

//: Upload whatever is still staged, and return the attachment list with real
//: ids. Called at the moment a message is actually sent, the point where the
//: user has committed to it and the server needs to know.
//:
//: A failure here has to stop the send rather than drop the picture quietly:
//: a message that arrives without the image it was written about is worse
//: than one that refuses to send and says why.
async function commitStagedImages() {
  for (const image of attachedImages) {
    if (image.id) continue; // already on the server (a regenerate re-uses these)
    const form = new FormData();
    form.append("file", image.file);
    // No explicit Content-Type: the browser sets its own multipart boundary
    // for a FormData body, and `api()`'s default JSON header would be wrong
    // here: the same reason the editor's own image-drop upload overrides
    // headers rather than merging.
    const uploaded = await apiJson("/media/upload", {
      method: "POST",
      headers: authHeaders(),
      body: form,
    });
    image.id = uploaded.id;
    image.url = uploaded.url;
    image.name = uploaded.filename || image.name;
  }
  return attachedImages;
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
function isImageFile(file) {
  // The type the browser reports, falling back to the extension, a file
  // dragged from some archives arrives with an empty `type`.
  if ((file.type || "").startsWith("image/")) return true;
  return /\.(png|jpe?g|gif|webp|bmp|avif|ico|tiff?|heic|heif|svg)$/i.test(file.name || "");
}

async function attachChatFiles(files) {
  const all = Array.from(files);
  const images = all.filter(isImageFile);
  const documents = all.filter((f) => !isImageFile(f));
  if (images.length) await attachImageFiles(images);
  if (documents.length) await importChatDocuments(documents);
}

//: The suffixes `/media/upload` accepts (`MEDIA_SUFFIXES`, routes_files.py).
//: Kept as a literal rather than fetched: it is a fallback path that must not
//: itself need a round trip to decide whether it can run.
const MEDIA_FALLBACK_SUFFIXES = /\.(png|jpe?g|gif|webp|avif|bmp|ico|pdf)$/i;

async function keepUnreadableChatFile(file, error) {
  if (!MEDIA_FALLBACK_SUFFIXES.test(file.name || "")) return false;
  const form = new FormData();
  form.append("file", file);
  form.append("direct", "true");
  try {
    await apiJson("/media/upload", {
      method: "POST",
      headers: authHeaders(),
      body: form,
    });
  } catch {
    return false;
  }
  //: Both halves, because either alone is misleading: "saved to your Library"
  //: without the reason looks like the import worked, and the reason without
  //: the destination looks like the file was lost.
  toastAction(
    `Kept “${file.name}” in your Library, ${error?.message || "its text could not be read"}`,
    "Show it",
    () => {
      switchTab("library");
      if (typeof renderLibrary === "function") renderLibrary();
    },
    { go: { tab: "library" } },
  );
  return true;
}

async function importChatDocuments(files) {
  const made = [];
  for (const file of files) {
    const form = new FormData();
    form.append("file", file);
    try {
      // Same header handling as attachImageFiles: a FormData body needs the
      // browser to set its own multipart boundary, so apiJson's JSON default
      // has to be overridden rather than merged.
      const document = await apiJson("/documents/import", {
        method: "POST",
        headers: authHeaders(),
        body: form,
      });
      made.push(document);
    } catch (error) {
      //: **A file the app cannot read is still a file worth keeping.**
      //:
      //: Reported: *"make sure the file upload and staging as chips works
      //: because I tried to upload two pdf files and nothing showed up."*
      //: Nothing showed up because `/documents/import` answers 422 for a PDF
      //: whose text cannot be extracted, which on an install without
      //: markitdown is *every* PDF, and a 422 became one toast that expired.
      //: So the paperclip advertised PDFs, refused them, and left no trace.
      //:
      //: REDESIGN.md §R7.2's reversal is the rule here and it is explicit:
      //: PDFs and documents must be viewable, downloadable and manageable
      //: **without any AI model in the loop**. Failing to read a PDF's words
      //: is not a reason to throw the PDF away. So the bytes go to
      //: `/media/upload`, the Library's own store, which takes PDFs, and
      //: the user is told where it went and why the text is missing.
      const kept = await keepUnreadableChatFile(file, error);
      if (!kept) toast(error.message || `Couldn't read "${file.name}".`, true);
    }
  }
  if (!made.length) return;
  offerCreatedDocsUndo(made);
  // **Staged on the message, not just imported and announced.** The toast
  // below still says where the file went, but a toast is a moment and the
  // report was about what is left behind: "images and files uploaded into a
  // chat conversation arent rendered with the chat messages". An imported
  // document is now an attachment of the message being written, exactly as
  // an image is: a chip in the composer, then a chip in the bubble, then a
  // way back to the document.
  for (const document of made) {
    if (attachedDocuments.length >= MAX_CHAT_DOCUMENTS) break;
    attachedDocuments.push({ id: document.id, name: document.title });
  }
  renderDocumentAttachments();

  const first = made[0];
  const label =
    made.length === 1
      ? `Added “${first.title}” to your documents.`
      : `Added ${made.length} files to your documents.`;
  toastAction(label, made.length === 1 ? "Open it" : "Show them", () => {
    switchTab("documents");
    if (made.length === 1) openDocument(first.id);
  }, { go: made.length === 1 ? { open: "doc", id: first.id } : { tab: "documents" } });
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
    const chipEl = document.createElement("span");
    chipEl.className = "chip attachment-chip";
    const label = document.createElement("span");
    setLabel(label, `ph:paperclip ${file.name}`);
    const remove = document.createElement("button");
    remove.className = "attachment-remove";
    remove.type = "button";
    //: Through `setLabel`, like every other close in the app. It was a typed
    //: U+2715, written as an escape, which is how it passed the glyph lint
    //: while nine other close buttons were being converted.
    setLabel(remove, "ph:x");
    remove.title = `Don't send “${file.name}” with this message`;
    remove.setAttribute("aria-label", remove.title);
    remove.addEventListener("click", () => {
      attachedFiles = attachedFiles.filter((f) => f.id !== file.id);
      renderFileAttachments();
      announce(`Removed attachment. ${attachedFiles.length} file(s) attached.`);
    });
    chipEl.append(label, remove);
    box.appendChild(chipEl);
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
    const chipEl = document.createElement("span");
    chipEl.className = "chip attachment-chip";
    const label = document.createElement("span");
    setLabel(label, `ph:tree-structure ${board.name}`);
    const remove = document.createElement("button");
    remove.className = "attachment-remove";
    remove.type = "button";
    setLabel(remove, "ph:x");
    remove.title = `Don't send “${board.name}” with this message`;
    remove.setAttribute("aria-label", remove.title);
    remove.addEventListener("click", () => {
      attachedBoards = attachedBoards.filter((b) => b.id !== board.id);
      renderBoardAttachments();
      announce(`Removed attachment. ${attachedBoards.length} map(s) attached.`);
    });
    chipEl.append(label, remove);
    box.appendChild(chipEl);
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
function attachDocumentToChat(id, name) {
  if (!id) return false;
  if (attachedDocuments.some((d) => d.id === id)) {
    renderDocumentAttachments();
    return true; // already staged: the badge the caller wanted is on screen
  }
  if (attachedDocuments.length >= MAX_CHAT_DOCUMENTS) return false;
  attachedDocuments.push({ id, name: name || "Document" });
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
    const chipEl = document.createElement("span");
    chipEl.className = "chip attachment-chip";
    const label = document.createElement("span");
    setLabel(label, `ph:file-text ${document_.name}`);
    const remove = document.createElement("button");
    remove.className = "attachment-remove";
    remove.type = "button";
    setLabel(remove, "ph:x");
    remove.title = `Don't send “${document_.name}” with this message`;
    remove.setAttribute("aria-label", remove.title);
    remove.addEventListener("click", () => {
      attachedDocuments = attachedDocuments.filter((d) => d.id !== document_.id);
      renderDocumentAttachments();
      announce(`Removed attachment. ${attachedDocuments.length} document(s) attached.`);
    });
    chipEl.append(label, remove);
    box.appendChild(chipEl);
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
  const chipEl = document.createElement("span");
  chipEl.className = "chip attachment-chip";
  //: The full passage on hover. A chip can only show a few words of it, and
  //: "which selection is this?" is the one question it has to answer.
  chipEl.title = attachedSelection.text;
  const label = document.createElement("span");
  const words = attachedSelection.text.replace(/\s+/g, " ").trim();
  const shown = words.length > 42 ? `${words.slice(0, 41)}…` : words;
  //: A page's reading (the OCR workspace, INBOX 717) has a file and a page,
  //: not a line in an editor.
  setLabel(label, attachedSelection.kind === "reading"
    ? `ph:scan ${attachedSelection.title}: “${shown}”`
    : `ph:text-aa ${attachedSelection.title} · line ${attachedSelection.line}: “${shown}”`);
  const remove = document.createElement("button");
  remove.className = "attachment-remove";
  remove.type = "button";
  setLabel(remove, "ph:x");
  remove.title = "Don't send this with your message";
  remove.setAttribute("aria-label", remove.title);
  remove.addEventListener("click", () => {
    clearSelectionAttachment();
    announce("Selection removed.");
  });
  chipEl.append(label, remove);
  box.appendChild(chipEl);
}

//: **Re-validated at send, not trusted from when it was attached.** This is
//: the part of odysseus's `getSelectionContext()` worth porting exactly
//: (`static/js/document.js`, AGPL: this project is AGPL-3.0, see
//: ANALYSIS.md): between selecting a passage and pressing send, the user can
//: type above it, undo, or edit the note entirely, and stored offsets then
//: point at *different words*. Sending those would hand the model text from a
//: region the user is no longer looking at, attributed to a line number that
//: is now someone else's line: wrong in the most confusing possible way.
//:
//: Three outcomes, and each is said plainly to the model rather than papered
//: over: the offsets still hold; the passage moved (found elsewhere, so the
//: line number is recomputed); or the passage is gone from the surface, in
//: which case the text is still sent, the user asked about it, but with no
//: position claimed at all.
function revalidateSelection(context) {
  //: A reading is a copy of what was read, not a place in a surface.
  if (context.kind === "reading") return { ...context, position: "exact" };
  //: **Through `docSurfaceById`, never `getElementById` alone.** A document
  //: whose CodeMirror engine has mounted keeps `#doc-content` in the markup as
  //: the form's empty value carrier: it is still an `HTMLTextAreaElement` and
  //: its `.value` is still `""`, so reading it directly passed the type check
  //: and then told the model every document passage was `gone` while the
  //: passage was on screen (measured on the branch head by
  //: `scratchpad/ui-sweeps/docsel.js`: "gone" for an untouched selection).
  //: `docSurfaceById` resolves `doc-content` to whichever surface is editing,
  //: and a note box that has mounted the engine the same way.
  //:
  //: Guarded by `typeof`, because documents.js is in the Library's lazy bundle
  //: (`LAZY_MODULES`) and a selection taken from the capture box can be sent
  //: before that bundle has ever loaded; the textarea is the right answer
  //: there anyway.
  const el = document.getElementById(context.surfaceId);
  const surface =
    typeof docSurfaceById === "function"
      ? docSurfaceById(context.surfaceId)
      //: `{ text }` rather than the element itself, so the one line below that
      //: reads the words reads the same property in both branches.
      : el instanceof HTMLTextAreaElement
        ? { text: el.value }
        : null;
  if (!surface || typeof surface.text !== "string") {
    //: The note was closed or the document navigated away from. Nothing to
    //: check against, so nothing is claimed.
    return { ...context, position: "unknown" };
  }
  const value = surface.text;
  if (value.slice(context.start, context.end) === context.text) {
    return { ...context, position: "exact" };
  }
  const found = value.indexOf(context.text);
  if (found === -1) return { ...context, position: "gone" };
  const upToCaret = value.slice(0, found + context.text.length);
  return {
    ...context,
    start: found,
    end: found + context.text.length,
    line: upToCaret.split("\n").length,
    column: upToCaret.length - (upToCaret.lastIndexOf("\n") + 1) + 1,
    position: "moved",
  };
}

//: What the model is actually told. Terse on purpose: it rides on every
//: message that carries a selection, and the tool schemas are already the
//: dominant fixed cost of a round (§R5 item 1).
function selectionContextBlock(context) {
  if (context.kind === "reading") {
    return [`The user is asking about the text read (OCR) from ${context.title}:`, "", context.text, ""].join("\n");
  }
  const where =
    context.position === "gone" || context.position === "unknown"
      ? `${context.title} (the user has since edited it, so this passage may no longer be there)`
      : `${context.title}, line ${context.line}, column ${context.column}`;
  const parts = [`The user has selected this passage in ${where}:`, "", context.text, ""];
  const around = [context.before, context.after].some((t) => (t || "").trim());
  if (around) {
    parts.push(
      "Immediately around it, for context only, do not treat it as the question:",
      "",
      `…${context.before}⟦selection⟧${context.after}…`
    );
  }
  return parts.join("\n");
}

function attachedNotes() {
  return attachedNoteIds
    .map((id) => allEntries.find((e) => e.id === id))
    .filter(Boolean);
}

//: The notes an answer named, as short titles, sent back on its history turn
//: so "delete the other one" can name the note (`reading.follow`, decision 57).
function chatTurnObjects(sources) {
  return (sources || []).filter((s) => s.kind === "note").slice(0, 5)
    .map((s) => String(s.label || "").replace(/…$/, "").split(/[:.!?]/)[0].trim().slice(0, 80))
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
  return String(md ?? "")
    .replace(/^\s{0,3}(?:#{1,6}\s+|>\s?|[-*+]\s+|\d+[.)]\s+)/gm, "")
    .replace(/!?\[([^\]]{0,300})\]\([^)]{0,500}\)?/g, "$1")
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
  button.setAttribute("aria-pressed", String(on));
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
    const chipEl = document.createElement("span");
    chipEl.className = "chip attachment-chip";
    chipEl.title = entry.content;
    const label = document.createElement("span");
    setLabel(label, `ph:paperclip ${noteLabel(entry)}`);
    const remove = document.createElement("button");
    remove.className = "attachment-remove";
    remove.type = "button";
    setLabel(remove, "ph:x");
    remove.title = `Remove "${noteLabel(entry, 24)}"`;
    remove.setAttribute("aria-label", remove.title);
    remove.addEventListener("click", () => {
      attachedNoteIds = attachedNoteIds.filter((id) => id !== entry.id);
      renderAttachments();
      renderNotePickerList();
      announce(`Removed attachment. ${attachedNoteIds.length} note(s) attached.`);
    });
    chipEl.append(label, remove);
    box.appendChild(chipEl);
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
        return [notePickerFacts(when && `Edited ${when}`, row.words ? `${row.words} word${row.words === 1 ? "" : "s"}` : "")];
      },
      search: (row) => `${row.title || ""} ${row.preview || ""}`,
      isOn: (row) => attachedDocuments.some((d) => d.id === row.id),
      add: (row) => attachDocumentToChat(row.id, row.title || "Document"),
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
      face: (row) => (row.has_pages ? notePickerPage(`/files/${row.id}/pdf-page/0`) : null),
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
//: grid, and between the source tabs), Space ticks the row, Enter is Done,
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
    event.preventDefault();
    $("note-picker-done").click();
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
    button.setAttribute("aria-selected", String(on));
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
  if (window.matchMedia(PHONE_TABS).matches && typeof openSheet === "function") {
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
  $("note-picker-search").focus();
}

function closeNotePicker() {
  if (notePickerSheetClose) {
    notePickerSheetClose();
    return;
  }
  $("note-picker-panel").classList.add("hidden");
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
  if (!window.matchMedia(PHONE_TABS).matches || typeof openSheet !== "function") return;
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

//: **The way onward, built in one place so both paths draw the same buttons.**
//:
//: Reported: "the continue step and edit step buttons in the chat arent
//: persistent and disappeared when I came back to the chat". They were built
//: only while the stream was finishing, from local variables (`stopped`,
//: `stoppedAtStep`, the skill and its inputs) that nothing wrote down, so a
//: run you stopped offered Resume until the moment you changed tab and then
//: silently stopped offering it, with the run's work still sitting there and
//: no way back to it. The state is saved on the turn now (`resume` in the
//: turn body) and `openConversation` calls this with it, which is the same
//: shape the Sources panel, the grounding chips and the followups each had
//: to be given for the same reason.
//:
//: One function rather than a copy in the reopen path: the comment on
//: `assistantMessageActions` is about exactly this pair of paths drifting.
function appendRunResumeControls(bubble, spec) {
  if (!bubble || !spec) return;
  const stopped = Boolean(spec.stopped);
  const stoppedAtStep = typeof spec.stoppedAtStep === "number" ? spec.stoppedAtStep : null;
  const pausedForManual = Boolean(spec.pausedForManual);
  const ranOutOfRounds = Boolean(spec.ranOutOfRounds);
  const editStepAction = (index) => ({
    label: `ph:pencil-simple Edit step ${index + 1}`,
    title: "Rewrite this step and run just it, leaving the rest for afterwards",
    onClick: async () => {
      const text = await promptDialog(
        `Rewrite step ${index + 1} and run just that step. Earlier steps are ` +
          "not repeated, and the rest of the skill is left to resume afterwards.",
        spec.timeline?.stepText?.(index) || "",
        { confirmLabel: "Run this step" }
      );
      if (!text || !text.trim()) return false;
      sendChatMessage(`${spec.skill}: step ${index + 1}`, {
        skill: spec.skill,
        skillInputs: spec.skillInputs || {},
        skillOnlyStep: index,
        skillStepText: text.trim(),
        skipPlanMode: true,
      });
      return true;
    },
  });

  if (stopped && stoppedAtStep !== null && spec.skill) {
    bubble.appendChild(
      continueRunControls({
        also: editStepAction(stoppedAtStep),
        label: `ph:play Resume from step ${stoppedAtStep + 1}`,
        hint: "You stopped this. Earlier steps are not repeated.",
        onClick: () =>
          sendChatMessage(`${spec.skill}: from step ${stoppedAtStep + 1}`, {
            skill: spec.skill,
            skillInputs: spec.skillInputs || {},
            skillFromStep: stoppedAtStep,
            skipPlanMode: true,
          }),
      })
    );
  } else if (stopped && (spec.skill || spec.hasTools)) {
    //: A stopped run with no step to name, a plain agent turn, or a skill
    //: stopped before its first step finished. It still did work worth not
    //: repeating, so the offer is the same one the round limit gets.
    bubble.appendChild(
      continueRunControls({
        label: "ph:play Resume",
        hint: "Picks up from what it had already done.",
        onClick: () =>
          sendChatMessage(
            "Continue from where you stopped. Don't redo what you have " +
              "already done: carry on with what is left, and say when it is " +
              "all finished.",
            { useTools: true }
          ),
      })
    );
  } else if (!stopped && stoppedAtStep !== null && spec.skill && pausedForManual) {
    bubble.appendChild(
      manualPauseControls({
        onContinue: (note) =>
          sendChatMessage(`${spec.skill}: from step ${stoppedAtStep + 1}`, {
            skill: spec.skill,
            skillInputs: spec.skillInputs || {},
            skillFromStep: stoppedAtStep,
            skillManual: true,
            skillManualNote: note,
            skipPlanMode: true,
          }),
      })
    );
  } else if (!stopped && stoppedAtStep !== null && spec.skill) {
    bubble.appendChild(
      continueRunControls({
        also: editStepAction(stoppedAtStep),
        label: `ph:arrow-clockwise Resume from step ${stoppedAtStep + 1}`,
        hint: "Earlier steps are not repeated.",
        onClick: () =>
          sendChatMessage(`${spec.skill}: from step ${stoppedAtStep + 1}`, {
            skill: spec.skill,
            skillInputs: spec.skillInputs || {},
            skillFromStep: stoppedAtStep,
            skipPlanMode: true,
          }),
      })
    );
  } else if (!stopped && ranOutOfRounds) {
    bubble.appendChild(
      continueRunControls({
        label: "ph:arrow-right Continue",
        hint: "Picks up from what it had already done.",
        onClick: () =>
          sendChatMessage(
            "Continue from where you stopped. Don't redo what you have " +
              "already done: carry on with what is left, and say when it is " +
              "all finished.",
            { useTools: true }
          ),
      })
    );
  }
}

//: A stray key typed against the last word ("dentist\\") goes before the bubble
//: shows it, as the server already reads it (question_noise); an emoticon
//: (":\\") and a lone key stay.
function chatTidyTyped(text) {
  const m = /([\w?.!)"'])[\\|`~^]+\s*$/.exec(text);
  return m ? text.slice(0, m.index + 1) : text;
}

async function sendChatMessage(preset, opts = {}) {
  const input = $("chat-input");
  const status = $("chat-status");
  const typed = chatTidyTyped((preset ?? input.value).trim());
  if (!typed) return;

  // Plan mode is applied here, on the way out, rather than by whatever control
  // was pressed: so Send, Enter and a suggestion chip all get planned when the
  // mode is on. `opts.plan` means this message IS a plan already (the plan
  // runner re-sends through here), so it must not be planned again.
  //
  // The user's own words go in the bubble; the planning instruction is appended
  // for the model only. `displayText` already exists for exactly this.
  const planned = opts.plan || opts.skipPlanMode ? null : applyPlanMode(typed);
  let question = planned || typed;
  if (planned && !opts.displayText) opts = { ...opts, displayText: typed };
  //: **The selection joins the question here, and only for the model.** It is
  //: appended after Plan mode's own rewrite for the same reason that rewrite
  //: exists at all: `displayText` is what the user said, and showing them a
  //: block of their own note quoted back at them under their question would
  //: read as the app putting words in their mouth. The chip above the box is
  //: what tells them it is going.
  //:
  //: Re-validated at this moment rather than reused from when it was attached
  //:, see `revalidateSelection` for what changes in between and why sending
  //: stale offsets is the worst of the three outcomes.
  const sentSelection = attachedSelection ? revalidateSelection(attachedSelection) : null;
  if (sentSelection) {
    if (!opts.displayText) opts = { ...opts, displayText: typed };
    question = `${question}\n\n${selectionContextBlock(sentSelection)}`;
  }
  //: A cited web page joins the same way and for the same reason: the model
  //: reads it, the bubble shows only what the user typed, and the chip above
  //: the box is what said it was going.
  if (attachedWebPage) {
    if (!opts.displayText) opts = { ...opts, displayText: typed };
    question = `${question}\n\n${webPageContextBlock(attachedWebPage)}`;
  } else if (chatWeb.lastUrl && (await ensureModule("webClip"))) {
    const page = await webFollowUp(typed, chatWeb.lastUrl);
    if (page) {
      if (!opts.displayText) opts = { ...opts, displayText: typed };
      question = `${question}\n\n${webPageContextBlock(page)}`;
    }
  }
  lastChatQuestion = question;
  if (!opts.replaceLast) regenerateLastAnswer.retries = 0; // a new question is a first ask

  // Consumed once: this send, button click or free-typed reply alike, is
  // the answer to whatever question was pending, and the next one after it
  // is an ordinary message again.
  const answeringAgent = opts.answeringAgent ?? chatAwaitingAgentAnswer;
  chatAwaitingAgentAnswer = false;
  // Whatever is sent while a question card waits is its answer (INBOX 171):
  // the card folds into its chip and cannot send a second one.
  settlePendingAgentQuestion(opts.displayText ?? typed);

  // **Staged images become real uploads here**, at the moment the message is
  // actually committed: see `attachImageFiles` for why nothing was uploaded
  // when they were attached.
  //
  // Before the snapshot below, because that snapshot reads `img.id` and a
  // staged image has none until this runs. A failure stops the send and says
  // so: a message arriving without the picture it was written about is worse
  // than one that refuses and explains.
  if (!opts.imageMediaIds) {
    try {
      await commitStagedImages();
    } catch (error) {
      toast(error.message || "Couldn't upload the attached image.", true);
      return;
    }
  }

  // Snapshot the attachments for this message. A regenerate re-uses the same
  // ones; a fresh send clears them, so they don't silently ride along on
  // every later question.
  const sentAttachments = opts.noteIds || attachedNoteIds.slice();
  const sentImages = opts.imageMediaIds || attachedImages.map((img) => img.id);
  const sentDocuments = opts.documentIds || attachedDocuments.map((d) => d.id);
  const sentFiles = opts.fileIds || attachedFiles.map((f) => f.id);
  const sentBoards = opts.boardIds || attachedBoards.map((b) => b.id);
  // What the bubble will draw. Built here, while the composer still knows the
  // names and urls: after the clear below there is nothing left to build it
  // from, and a round trip to re-fetch what we already had would show the
  // message without its pictures for as long as that took.
  const sentAttachmentCards = opts.attachmentCards || [
    ...attachedImages.map((img) => ({
      kind: "image",
      id: img.id,
      url: img.url,
      name: img.name || "Attached image",
      // A just-uploaded image has no caption yet, captioning runs in the
      // background once the message commits it. Reopening the chat picks the
      // caption up from `GET /conversations/{id}`, which is where it lands.
      caption: "",
      text: "",
    })),
    ...attachedDocuments.map((d) => ({ kind: "document", id: d.id, name: d.name })),
    // Library files: the same card list as the other kinds, so the bubble
    // shows every reference the question was given rather than three of four.
    ...attachedFiles.map((f) => ({ kind: "file", id: f.id, name: f.name })),
    // A mind map, same card list again, the bubble has to show every
    // reference the question was given, and a map is the one whose absence
    // would be least obvious (its outline is invisible in the transcript).
    ...attachedBoards.map((b) => ({ kind: "map", id: b.id, name: b.name })),
    // The paperclip's own attachments. Same card list as the other two kinds
    // so the bubble shows every reference this question was given, not two of
    // the three.
    ...attachedNotes().map((entry) => ({
      kind: "note",
      id: entry.id,
      name: noteLabel(entry, 60),
    })),
  ];
  if (!opts.replaceLast) {
    // Remembered so a regenerate re-runs with the same references, by then
    // the picker has been cleared.
    lastChatAttachments = sentAttachments;
    lastChatImageAttachments = attachedImages.slice();
    lastChatDocumentAttachments = attachedDocuments.slice();
    lastChatFileAttachments = attachedFiles.slice();
    lastChatBoardAttachments = attachedBoards.slice();
    // The staged bytes are on the server now, so the local Blob references
    // are dead weight: an object URL lives as long as the document unless it
    // is revoked, and a chat session sending several images would hold every
    // one of them in memory for the life of the tab. The upload's real url is
    // what the sent bubble draws from, so nothing on screen depends on these.
    for (const image of attachedImages) {
      if (image.objectUrl) URL.revokeObjectURL(image.objectUrl);
      image.objectUrl = null;
    }
    attachedNoteIds = [];
    attachedImages = [];
    attachedDocuments = [];
    attachedFiles = [];
    attachedBoards = [];
    //: Cleared with the rest, and for the same stated reason: a selection that
    //: rode along on every later question would be the app answering about a
    //: paragraph the user stopped talking about three messages ago.
    attachedSelection = null;
    attachedWebPage = null;
    renderAttachments();
    renderImageAttachments();
    renderDocumentAttachments();
    renderFileAttachments();
    renderBoardAttachments();
    renderSelectionAttachment();
    renderWebPageAttachment();
    closeNotePicker();
  }

  //: Same loan as in `openConversation`: `chatEmptyState` can have moved this
  //: element inside `#chat-messages`, and a caller that cleared the pane first
  //: would find it gone.
  $("chat-suggest")?.classList.add("hidden");
  input.value = "";
  autoGrow(input); // a cleared box must not keep the height of what was in it
  // The draft is gone, so the suggestions about it are too, including the
  // ones that were dismissed, which belonged to that draft and not to the
  // next one.
  resetChatNudge();
  //: The box is disabled while the answer streams, and a disabled box loses
  //: the focus to the page: Tab then started again from the top of the app,
  //: and nothing on screen held the keyboard. The Stop button takes it
  //: instead, so Enter, Space and Escape all stop the answer from where the
  //: person already is; `releaseChatComposer` and the stream's end give it
  //: back to the box.
  const composerHadFocus = document.activeElement === input;
  input.disabled = true;
  hide("chat-send");
  show("chat-stop");
  if (composerHadFocus) $("chat-stop").focus({ preventScroll: true });
  status.classList.remove("error");
  status.textContent = "Searching your notes…";
  startChatTimer();

  // Regenerate re-runs the same question without adding a duplicate "you".
  //
  // `displayText` is what the *user* said when the message carries an
  // instruction they did not type, Plan Plan appends one. Showing the appended
  // sentence back to them would read as the app putting words in their mouth,
  // and hiding the request entirely would leave the plan looking as though it
  // came from nowhere; the button they pressed is the explanation.
  const userBubble = opts.skipUserBubble
    ? null
    : addBubble("user", opts.displayText || question, sentAttachmentCards);
  //: A chip's question names the one it was offered under (INBOX 490); a
  //: regenerate keeps what the question it re-asks already had.
  const followupOf = opts.followupOf || (opts.skipUserBubble ? [...$("chat-messages").querySelectorAll(".msg.user")].at(-1)?.dataset.followupOf : "") || null;
  markFollowup(userBubble, followupOf);
  //: **Who answers this question, captured once**, the way `effectiveUseTools`
  //: is below: the picker can move on while this reply is still streaming,
  //: and the bubble's face, the request and the saved turn must all name the
  //: persona that actually answered (the owner: "the avatars need to persist
  //: for what persona was used").
  const sentPersona = $("persona-select").value || aiNameNow();
  const { bubble, stepsHolder, recordsHolder, groundingHolder, timeline, paintHooks } = addAssistantBubble(sentPersona);
  // The live counter rides in the bubble it is timing, and leaves with it.
  mountChatTimer(bubble);
  // A newer answer exists, so the previous one's chips stop being the end of
  // the thread: this bubble is, and it has none yet.
  refreshFollowupVisibility();
  // A placeholder until the first event arrives; the first real step evicts it.
  const pending = document.createElement("div");
  pending.className = "agent-step step-pending";
  const pendingLine = progressLine(null, { persona: sentPersona, words: true });
  pending.appendChild(pendingLine);
  stepsHolder.appendChild(pending);
  // The placeholder trails the work rather than vanishing at the first event,
  // so a turn that thinks for a while still shows one live line.
  //: `turnEnded`: `clearPending` appends, and appending a removed node puts it
  //: back, so a late delta after `finally` re-attached "Writing the answer"
  //: under a finished turn. The flag says the turn is over.
  let turnEnded = false;
  const clearPending = () => {
    if (turnEnded) return;
    //: Only when not already last: `onAnswer` calls this per delta, and
    //: re-appending the last child restarts its CSS animation, which froze
    //: the three dots.
    if (stepsHolder.lastElementChild === pending) return;
    stepsHolder.appendChild(pending);
  };
  //: The line's words and shape are driven by `streamChat` itself (`progress:
  //: pendingLine` below), from the events that really arrive (INBOX 649), so
  //: no handler in this turn names a stage of its own.
  // **The turn is marked as generating for its whole length, not just until
  // the first event.** Reported as "none of the generating animations work",
  // and this is the mechanism: `clearPending` above runs on the first event
  // of *any* kind: including `meta`, which this app emits almost
  // immediately, well before the model has produced a word. So the dots
  // appeared for a few hundred milliseconds and then the bubble sat
  // completely still for however long the model actually took, which reads
  // as nothing happening at all.
  //
  // A class on the bubble, cleared in the `finally` that ends the stream, is
  // the state that genuinely lasts as long as the work does, every step
  // that arrives can still evict its own placeholder without taking the
  // "still working" signal down with it.
  bubble.classList.add("is-generating");
  let meta = null;
  //: This turn's row in the Agent Activity panel, or null while the turn has
  //: done nothing worth a row. **Created lazily, on the first plan or the
  //: first tool call**, and that is deliberate: a plain question with a plain
  //: answer is not a "run", and a row per chat message would rebuild the wall
  //: of text this panel was just taken apart to stop being.
  let activityRun = null;
  let toolsActed = false;
  let stats = null;
  // Captured so the final save below can persist it. Reported directly: the
  // "Grounded in" chips under a direct Q&A answer only ever existed for the
  // live stream: reopening the chat, or leaving the tab and coming back,
  // showed an answer with no sources at all. Same unfixed-until-now shape as
  // raw_results/search_mode/match_info a few lines below, which got exactly
  // this treatment already for the same reported-missing-on-reload reason.
  let groundingSentences = null;
  let chatOffer = null;
  let composedNext = []; // a composed answer's own next questions (INBOX 725)
  //: **Numbered while it streams, as the Ask tab is** (INBOX 320, the
  //: askcite row): the backend sends the rows so far each time a sentence
  //: completes (`grounding_live`), and the markers are put back after every
  //: live paint, which rebuilds the step. The numbering is the final pass's
  //: own (`chatSourcesFrom` over this turn's meta), so a digit that appears
  //: mid-answer is the digit it keeps. The `grounding` event still replaces
  //: these rows when the stream ends.
  let liveSources = null;
  const placeLiveCitations = () => {
    if (groundingSentences?.length) {
      addInlineCitations(
        bubble.querySelectorAll(".bubble-answer"),
        groundingSentences,
        meta?.raw_results || [],
        liveSources
      );
    }
  };
  paintHooks.afterAnswerPaint = placeLiveCitations;
  // INBOX 272 part 1: set when the model couldn't call tools and the turn
  // was silently answered as plain Q&A instead. Captured here, rendered
  // once the stream is over (same reason `groundingSentences` waits: a
  // notice drawn mid-stream would be for a bubble the live renderer is
  // about to rebuild).
  let toolsUnsupportedEvent = null;
  // Whether the user pressed Stop. An empty answer they asked for needs no
  // explanation; one they didn't ask for does.
  let stopped = false;
  // Set when the agent ends its turn by handing the job to a saved skill.
  // The run can't start from inside the stream, this turn is still holding
  // the input box and the conversation, so it is remembered and started
  // once everything below has run.
  let handoff = null;
  // Set when the turn ended by asking the person something: the question is
  // the answer, and "the model finished without writing anything" over a
  // question card (INBOX 169, with a screenshot) blamed the model for
  // doing what it was told.
  let asked = false;
  let askedQuestion = null;
  // Set when the turn stopped because it ran out of rounds, and, for a skill
  // run: the step it did not get past. Both become a button at the end of the
  // bubble rather than a sentence asking the user to type "carry on".
  let ranOutOfRounds = false;
  let stoppedAtStep = null;
  let pausedForManual = false;
  const startedAt = performance.now();
  const toolEvents = []; // {label, ok}: persisted so chips survive a reload
  //: Everything this turn opened, deduped on kind+id, for the Sources panel.
  //: A Map rather than an array because a turn that reads the same note twice
  //: has one source, not two, and `touched` arrives per tool call.
  const touchedItems = new Map();
  chatController = new AbortController();
  const controller = chatController;
  //: The app's mark lifts its cells while a turn runs (phone-shell.js).
  if (typeof syncEmblemBusy === "function") syncEmblemBusy();
  //: Atlas looks up to think while a turn runs (avatars.js).
  if (typeof setAtlasMood === "function") setAtlasMood("thinking");

  // --- the turn owns its conversation ----------------------------------------
  // `chatConv` is reassigned by every switch, and saves used to read it live,
  // so a turn that finished after a switch was written into whichever chat was
  // open. `convRef` pins the asking conversation; `viewing()` says whether it
  // is still on screen, the only time this turn may touch the pane.
  const convRef = chatConv;
  const viewing = () => chatConv === convRef;

  // The live nodes, kept: `openConversation` rebuilds the transcript, so coming
  // back re-attaches these same still-streaming elements. Set once here, never
  // by a switch, or the notice names the wrong conversation.
  chatStreaming = {
    conv: convRef,
    title: $("chat-title").textContent || "that chat",
    nodes: [userBubble, bubble].filter(Boolean),
    announced: false,
  };

  // --- checkpointing a long turn --------------------------------------------
  // A row for this turn already exists, so the save at the end has to update
  // it rather than append a second copy of the same exchange.
  let checkpointed = false;
  let checkpointInFlight = false;
  //: The checkpoint's own promise, so the save at the end can wait for it.
  //: Without it a fast model finished while the first checkpoint's create
  //: was still in flight, the end save saw no id yet and created a second
  //: conversation: the README's Chat shot listed "What is left before the
  //: Harbor launch?" twice, 43ms apart (INBOX 431 (g)).
  let checkpointRun = null;

  // Write what the turn has so far. Called at each agent round boundary, so a
  // ten-minute run that dies at minute nine leaves nine minutes of work in the
  // conversation instead of nothing.
  //
  // One in flight at a time: rounds can finish close together, and two
  // creates racing each other would make two conversations out of one thread.
  function checkpointTurn() {
    if (checkpointInFlight) return checkpointRun;
    checkpointInFlight = true;
    checkpointRun = writeCheckpoint();
    return checkpointRun;
  }
  async function writeCheckpoint() {
    try {
      const partial = {
        question,
        // A turn that ended by asking saves the question as its answer, so a
        // reloaded thread shows what was asked rather than an empty bubble
        // (INBOX 171: "all the ai responses dissappeared"; the question
        // lives in the bubble's output area, which is not a serialised step).
        answer: timeline.text() || (askedQuestion ? `Asked: ${askedQuestion}` : ""),
        thinking: timeline.thinkingText() || null,
        tools: toolEvents.length ? toolEvents : null,
        steps: timeline.serialise(),
        // No stats or elapsed yet, the turn is not over, and a half-turn's
        // numbers reported as final would be wrong rather than incomplete.
        image_media_ids: sentImages.length ? sentImages : null,
        document_ids: sentDocuments.length ? sentDocuments : null,
        file_ids: sentFiles.length ? sentFiles : null,
        note_ids: sentAttachments.length ? sentAttachments : null,
        followup_of: followupOf,
        persona: savedPersona(sentPersona),
      };
      if (convRef.id === null) {
        const created = await apiJson("/conversations", {
          method: "POST",
          body: JSON.stringify(partial),
          silent: true,
        });
        convRef.id = created.id;
        if (viewing()) $("chat-title").textContent = created.title;
        applyPendingChatTitle(created.id, viewing());
        loadConversationList();
      } else if (checkpointed || opts.replaceLast) {
        await apiJson(`/conversations/${convRef.id}/turns/last`, {
          method: "PUT",
          body: JSON.stringify(partial),
          silent: true,
        });
      } else {
        await apiJson(`/conversations/${convRef.id}/turns`, {
          method: "POST",
          body: JSON.stringify(partial),
          silent: true,
        });
      }
      checkpointed = true;
    } catch {
      // Deliberately silent. This is insurance running behind a live answer;
      // a toast here would interrupt the thing it exists to protect, and the
      // save at the end of the turn reports its own failure.
    } finally {
      checkpointInFlight = false;
    }
  }

  //: **A new chat gets its row at send time, not at the first agent round.**
  //: A plain answer has no round boundary, so a chat started with one had no
  //: row, and so no entry in the list, until the reply finished: start a new
  //: chat, open another, and the first one could not be reached again until
  //: it was done (the owner, 2026-10-12). The row holds the question and an
  //: empty answer; `openConversation` already drops that partial turn and
  //: puts the live bubbles back (`isStreamingConversation`).
  if (convRef.id === null) checkpointTurn();

  // Captured once, not re-read at save time: the toggle can move on to the
  // next message while this one is still streaming, and the meta line and
  // the saved turn must both say what actually answered *this* question.
  //: Agent only when something can call tools: the saved toggle stays on with
  //: no model (renderChatModeSeg greys it), and a turn sent then is Ask's.
  const effectiveUseTools = opts.useTools ?? ($("tools-toggle").checked && !(aiIsOff() && !modelStatus?.tools_engine));

  let slowLoadTimeout;
  try {
    slowLoadTimeout = setTimeout(() => {
      if (!meta && !stopped) {
        status.textContent = "Loading model… (this may take a moment)";
      }
    }, 5000);
    await streamChat({
      progress: pendingLine,
      question,
      history: chatHistoryToSend(),
      attempt: opts.attempt,
      persona: sentPersona,
      mode: $("response-mode-select").value || null,
      useTools: effectiveUseTools,
      noteIds: sentAttachments,
      imageMediaIds: sentImages,
      documentIds: sentDocuments,
      fileIds: sentFiles,
      boardIds: sentBoards,
      skill: opts.skill,
      skillInputs: opts.skillInputs,
      skillFromStep: opts.skillFromStep,
      skillOnlyStep: opts.skillOnlyStep,
      skillStepText: opts.skillStepText,
      // Read live rather than captured at launch: a run that started
      // straight-through and is now being Resumed can still be switched to
      // step-by-step, and vice versa.
      skillManual: opts.skillManual ?? Boolean($("skill-manual-toggle")?.checked),
      skillManualNote: opts.skillManualNote,
      plan: opts.plan,
      attachedNotesOnly: opts.attachedNotesOnly,
      answeringAgent,
      signal: controller.signal,
      onMeta: (m) => {
        meta = m;
        //: No model runs: the answer is composed from the notes (INBOX 725).
        status.textContent = m && m.composed ? "Composing from your notes, no AI…" : "The model is writing…";
      },
      onRelated: (event) => {
        renderRelatedElsewhere(groundingHolder, event.items);
      },
      onUnsupported: (event) => {
        toolsUnsupportedEvent = event;
      },
      onGroundingLive: (event) => {
        groundingSentences = event.sentences || [];
        liveSources ??= chatSourcesFrom({ meta, toolEvents: [], touched: [] });
        placeLiveCitations();
      },
      onGrounding: (event) => {
        groundingSentences = event.sentences;
        composedNext = Array.isArray(event.next) ? event.next : [];
        renderAnswerGrounding(
          groundingHolder,
          event.sentences,
          meta?.raw_results || [],
          //: Every prose block of this turn, not the first: see
          //: `addInlineCitations`. A skill run has one per step.
          bubble.querySelectorAll(".bubble-answer"),
          //: The turn's own question, so opening a source here teaches the
          //: search the same thing it learns from the Ask tab.
          question,
          null,
          event.support || null,
          meta?.picture_alts || null
        );
        //: Each insight line the answer said carries Confirm and Not right
        //: (CHAT_PLAN decision 60), under the answer, one row each.
        for (const insight of event.insights || []) {
          if (insight.confirmed) continue;
          const line = insightLine(insight, insight.in_answer ? (insight.rule === "drift" ? "Is that open plan right?" : "Is that pattern right?") : `Pattern: ${insight.short}.`, (row, verdict, result) => {
            row.textContent = verdict === "confirmed" ? `Confirmed: ${result.line}` : "Not right: it will not be shown again.";
          }, "muted");
          groundingHolder.appendChild(line);
        }
      },
      onPlan: (event) => {
        clearPending();
        timeline.plan(event);
        //: A turn's own card: its tool rows are already in the panel's run.
        if (event.kind === "turn") return chatScrollToEnd();
        // …and the same run as one row in the activity panel. Both are drawn
        // from this one event, so they cannot disagree about how many steps
        // there are or what the run is called.
        activityRun = addAgentRun({
          kind: event.kind === "plan" ? "plan" : "skill",
          name: event.skill || "Run",
          icon: event.kind === "plan" ? "ph:compass" : "ph:lightning",
          steps: event.steps || [],
        });
        openPanelForRun(activityRun);
        status.textContent =
          event.kind === "plan"
            ? `Working through ${(event.steps || []).length} steps…`
            : `Running “${event.skill}”…`;
        chatScrollToEnd();
      },
      onStep: (event) => {
        clearPending();
        timeline.step(event);
        if (event.kind !== "turn") agentRunStep(activityRun, event);
        if (event.state === "running") {
          status.textContent = `Step ${event.index + 1}: ${event.text}`;
        }
        chatScrollToEnd();
      },
      onResult: (event) => {
        clearPending();
        timeline.result(event);
        // Where the run stopped, if it did. A number here means the steps
        // after it never ran.
        stoppedAtStep = typeof event.stopped_at === "number" ? event.stopped_at : null;
        pausedForManual = Boolean(event.paused);
        // A skill that changed notes has just made the list on screen stale.
        if ((event.changes || []).length) loadEntries();
        chatScrollToEnd();
      },
      onLimit: () => {
        // Out of rounds with tools still in flight. Only remembered here: the
        // offer to continue belongs beneath the answer that says it stopped,
        // and that answer has not been written yet.
        ranOutOfRounds = true;
      },
      onThinking: (delta) => {
        clearPending();
        timeline.thinking(delta);
        //: Reasoning is still waiting, as far as the reader is concerned:
        //: `streamChat` sets the "thinking" phase (dots) before this runs, so
        //: a turn that thinks *after* writing goes back to dots.
        status.textContent = "The model is thinking…";
        chatScrollToEnd();
      },
      onAnswer: (delta) => {
        clearPending();
        timeline.answer(delta);
        status.textContent = "The model is writing…";
        chatScrollToEnd();
      },
      onTool: (event) => {
        clearPending();
        //: The fallback strips the failed call's own icon token before
        //: prefixing the warning one. `setLabel` only resolves a token at the
        //: start of the string, so `ph:warning ph:books Listed notes` renders
        //: one warning glyph and then prints "ph:books" as literal text: 
        //: the same defect reported in the palette's status line, one branch
        //: over and only reachable when a tool fails.
        const label = event.ok
          ? event.label
          : `ph:warning ${(event.error || event.label || "").replace(/^ph:[\w-]+\s*/, "")}`;
        timeline.tool(toolChip(label, event.ok, event));
        pushAgentChangeUndo(event.change, event);
        //: The same call, filed in the panel under the step that made it. A
        //: second `toolChip` rather than the same node: one element cannot be
        //: in two places, and the panel's copy has to survive the chat being
        //: cleared or the conversation being closed.
        if (!activityRun) {
          // An agent turn with no plan is still a run, it is what the report
          // called "agent model activity", and its first tool call is the
          // moment it becomes one.
          activityRun = addAgentRun({
            kind: "agent",
            name: agentRunTitle(question),
            icon: "ph:strategy",
          });
          openPanelForRun(activityRun);
        }
        agentRunTool(activityRun, toolChip(label, event.ok, event));
        toolEvents.push(event); // remember for persistence
        for (const item of event.touched || []) {
          touchedItems.set(`${item.kind}:${item.id}`, item);
        }
        if (event.proposal) {
          // Asked where it was suggested, not in a settings page nobody opens.
          const card = document.createElement("div");
          renderMemoryProposal(card, event.proposal);
          timeline.tool(card.firstElementChild || card);
        }
        if (event.ok) toolsActed = true;
        status.textContent = "The model is making changes…";
        chatScrollToEnd();
      },
      //: The web pages an answer from no model read (CHAT_PLAN decision 37).
      onWebSources: (event) => ensureModule("askCompose").then(() => renderWebSources(timeline.holder, event.sources)),
      //: A bar of counts from a no-model answer (CHAT_PLAN decision 59, step
      //: 2), drawn by the Ask box's chart recipe under the answer's line.
      onChart: (event) => ensureModule("askHistory").then(() => {
        const host = document.createElement("div");
        host.className = "ask-chart";
        timeline.holder.appendChild(host);
        drawAskChart(host, event.chart);
        chatScrollToEnd();
      }),
      onConfirm: (event) => {
        clearPending();
        const card = document.createElement("div");
        renderToolConfirm(card, event);
        //: An act's card is the answer's own (CHAT_PLAN decision 38), under
        //: its line, never folded away in a step group with its Confirm.
        if (event.type === "act") timeline.holder.appendChild(card);
        else timeline.tool(card.firstElementChild || card);
        status.textContent = "Waiting for your confirmation…";
      },
      onAsk: (event) => {
        clearPending();
        //: **The question is output, not a step.**
        //:
        //: Reported: *"the question the agent asked me appeared in the step
        //: and not the actual output."* A step group folds itself shut into
        //: "Finished 1 step" the moment prose starts (`startAnswer`), so a
        //: question filed there is a question that disappears while it is
        //: still waiting to be answered, and the answer box underneath then
        //: says the model wrote nothing, which is the screenshot.
        //:
        //: `recordsHolder` is the bubble's own output area, under the steps
        //: and above the sources, where everything else the turn is waiting
        //: on (a confirmation, a memory proposal's outcome) already lands.
        const card = document.createElement("div");
        renderAgentQuestion(card, event);
        recordsHolder.appendChild(card.firstElementChild || card);
        status.textContent = "Waiting for your answer…";
        chatAwaitingAgentAnswer = true;
        asked = true;
        askedQuestion = event.question;
      },
      onRunSkill: (event) => {
        // The model picked a saved skill for this job (§33). Its turn is over;
        // the run starts below, once this one has finished tidying up.
        clearPending();
        timeline.tool(toolChip(event.label, true));
        toolEvents.push({ label: event.label, ok: true });
        status.textContent = `Starting “${event.skill}”…`;
        handoff = event;
        chatScrollToEnd();
      },
      onRunPlan: (event) => {
        // The model decided the job has several parts and planned it (§35K).
        // Same handover as a skill: the turn is over and the steps run one at
        // a time below, so nothing is left half-done.
        clearPending();
        timeline.tool(toolChip(event.label, true));
        toolEvents.push({ label: event.label, ok: true });
        status.textContent = "Working out the steps…";
        handoff = event;
        chatScrollToEnd();
      },
      onCompressReview: (event) => {
        // The model asked to compress the chat (§37I). Unlike run_skill/
        // run_plan this isn't a run to start, it opens the same review
        // panel the manual Compress button fills in, and the summary is
        // used only if the user presses Apply there. Not set on `handoff`:
        // that path always starts something; this one waits for a person.
        clearPending();
        const label = "ph:arrows-in Suggested compressing the earlier messages";
        timeline.tool(toolChip(label, true));
        toolEvents.push({ label, ok: true });
        showCompressReview(event, event.turns);
        status.textContent = "Waiting for you to review the summary…";
        chatScrollToEnd();
      },
      onOffer: (event) => { chatOffer = event.offer || null; },
      onStats: (event) => {
        // A round finished. Asked for directly: *"a new chat should be saved
        // after agent turns as well, not after the whole response is
        // complete."* Correct, and the reason is that an agent turn is minutes
        // of work on a local model, closing the window, a stall, or the
        // server going away halfway through used to lose **the entire
        // conversation**, because nothing was written until the last round
        // returned. A checkpoint per round means the worst case is losing the
        // round in progress rather than the thread.
        //
        // Fire-and-forget, and silent: a checkpoint that interrupts the answer
        // to complain about the network would be worse than the data loss it
        // is preventing. The turn's real save still happens at the end and
        // overwrites this with the finished version.
        if (event.round) checkpointTurn();
        //: The header's context meter, updated live rather than at the end of
        //: the turn: on a long agent run the window fills round by round, and
        //: the number is only useful while there is still a decision to make
        //: about it.
        renderChatContextMeter(event);
        // An agent turn reports once per round, so these accumulate: output
        // tokens and generation time add up, while the prompt size is the
        // largest context the model was given rather than the sum.
        if (!stats) {
          stats = { ...event };
          return;
        }
        stats.model = event.model || stats.model;
        stats.prompt_tokens = Math.max(stats.prompt_tokens || 0, event.prompt_tokens || 0);
        stats.output_tokens = (stats.output_tokens || 0) + (event.output_tokens || 0);
        stats.eval_ms = (stats.eval_ms || 0) + (event.eval_ms || 0);
        // The agent tags each round; the highest is how many it took.
        stats.round = Math.max(stats.round || 0, event.round || 0);
        // The window doesn't change between rounds, but the peak prompt does, 
        // and the peak is the one worth reporting, because it is the round
        // that came closest to overflowing.
        stats.context_tokens = event.context_tokens || stats.context_tokens;
        // One estimated round makes the whole total an estimate. Reporting a
        // mixed figure as measured would be the dishonest way round.
        if (event.usage_source === "estimated") stats.usage_source = "estimated";
      },
    });
    if (viewing()) status.textContent = "";
  } catch (error) {
    if (error.name === "AbortError") {
      stopped = true;
      if (viewing()) status.textContent = "Stopped.";
    } else {
      // The timeline is this turn's own, detached or not, so it is always
      // marked failed; only the shared status line is conditional.
      //: The step names what failed, in the server's own plain sentence
      //: (owner, 2026-10-17: the old fixed line said nothing). A message
      //: too long to be a sentence, or none, falls back to a line that still
      //: says what to do next.
      const said = String(error && error.message ? error.message : "").trim();
      timeline.failRunningStep(
        said && said.length <= 160 ? said : "The model stopped before it finished. Try again, or check Settings, Models."
      );
      if (viewing()) {
        status.textContent = error.message;
        status.classList.add("error");
      }
    }
  } finally {
    clearTimeout(slowLoadTimeout);
    // Whatever happened, answered, stopped, errored, the turn is no longer
    // generating, so the signal that says it is has to come down here rather
    // than on any one success path.
    bubble.classList.remove("is-generating");
    // The one place the trailing progress line is taken down, the turn is
    // genuinely over here, whether it ended, errored or was aborted. The flag
    // goes up *first*: see `clearPending` for the callback that used to run
    // after this line and put the node straight back.
    turnEnded = true;
    pending.remove();
    //: **Every visual "still working" state comes down here, on every exit.**
    //:
    //: Reported with a screenshot of a finished skill run still showing both
    //: the streaming caret and "Writing the answer…". `finalise()` was called
    //: on the success path only, so a turn that ended any other way, an
    //: error, a stop, the round limit, kept the caret blinking on prose that
    //: had stopped arriving. It is idempotent, so calling it here as well
    //: costs nothing and closes every path at once, which is the property the
    //: success-path-only version could never have.
    timeline.finalise?.();
    //: Whatever step group is still open stops saying "Working", see
    //: `agentTimeline.finish`.
    timeline.finish?.();
    //: …and the same for this turn's row in the activity panel, on the same
    //: every-exit reasoning: a row still saying "Running" after the turn
    //: errored or was stopped is the panel telling a lie for the rest of the
    //: session. `stoppedAtStep`/`pausedForManual` come from the `result`
    //: event, so the row can say *how* it ended rather than only that it did.
    const endState = stopped
      ? "stalled"
      : pausedForManual
        ? "paused"
        : typeof stoppedAtStep === "number"
          ? activityRun?.steps?.[stoppedAtStep]?.state === "failed"
            ? "failed"
            : "stalled"
          : "done";
    endAgentRun(activityRun, { state: endState });
    //: …and Atlas's face says how it went, for a moment.
    if (typeof setAtlasMood === "function") {
      setAtlasMood(endState === "done" ? "happy" : endState === "failed" ? "surprised" : "calm", 5000);
    }
    // Only if it is still ours. Switching away and sending a second message
    // installs a new controller, and this line firing late would null it, 
    // leaving Stop wired to nothing while a stream was genuinely running.
    if (chatController === controller) {
      chatController = null;
      stopChatTimer();
      if (typeof syncEmblemBusy === "function") syncEmblemBusy();
      // The turn is over: it is saved (or about to be) and a reload of this
      // thread will render it like any other. Re-attaching these nodes after
      // that point would show it twice.
      if (chatStreaming && chatStreaming.conv === convRef) chatStreaming = null;
    }
    // The composer belongs to whatever conversation is on screen. A turn that
    // finishes after the reader has moved on must not re-enable, refocus or
    // re-label the box they are now typing into, releaseChatComposer already
    // put it back when they switched.
    if (viewing()) {
      input.disabled = false;
      show("chat-send");
      //: The focus goes back to the box only from the Stop button (which
      //: took it when the answer began, `sendChatMessage`) or from nowhere:
      //: a reader who moved to the search box or the sidebar while the
      //: answer streamed keeps their place, rather than having the box take
      //: it as the answer ends (the review, 2026-09-27).
      const fromStop = document.activeElement === $("chat-stop") || document.activeElement === document.body;
      hide("chat-stop");
      if (fromStop) input.focus();
    }
  }

  clearPending();
  timeline.finalise();
  //: **The citations go back in after the final render.** Same defect as the
  //: Ask box's, one surface over and for the same reason: `onGrounding` writes
  //: the markers straight into the answer during the stream, and `finalise()`
  //: re-renders every prose step from its raw markdown, throwing all of them
  //: away a few milliseconds later. The grounding event always arrives before
  //: `done`, so this was true of every answer that had any.
  //: Built once, here, and handed to both the citation pass and the panel,
  //: so the digit in the prose and the digit on the row are the same number
  //: by construction rather than by two functions agreeing about order.
  const turnSources = chatSourcesFrom({
    meta,
    toolEvents,
    touched: [...touchedItems.values()],
  });
  //: The page this turn went out to read, for a follow-up about it
  //: (`webFollowUp`, web-clip.js).
  chatWeb.lastUrl = turnSources.find((source) => source.kind === "web" && source.url)?.url || null;
  if (groundingSentences?.length) {
    addInlineCitations(
      bubble.querySelectorAll(".bubble-answer"),
      groundingSentences,
      meta?.raw_results || [],
      turnSources
    );
  }
  placeAnswerFigures(bubble.querySelectorAll(".bubble-answer"), meta, question);
  //: An answer's one acting offer, the Ask box's (`digestOffer`): a place's link.
  if (chatOffer) ensureModule("askCompose").then(() => digestOffer([...bubble.querySelectorAll(".bubble-answer")].pop(), chatOffer)).catch(() => {});
  const answerRaw = timeline.text();
  const thinkingRaw = timeline.thinkingText();
  //: **The Sources panel replaces the old "N matching notes" disclosure here.**
  //: It is a superset, it carries the same retrieved notes and adds the
  //: files and pages the turn read and the things it opened, which had no
  //: home at all. `renderRecordsDetails` stays for the Ask tab, which has one
  //: answer rather than a thread and no tool events to fold in.
  const sourcesPanel = chatSourcesPanel({
    meta,
    toolEvents,
    touched: [...touchedItems.values()],
    sources: turnSources,
  });
  if (sourcesPanel) recordsHolder.appendChild(sourcesPanel);
  // INBOX 272 part 1: drawn once the stream is over, same reason
  // `groundingSentences` waits (a notice inserted mid-stream is inside a
  // bubble the live renderer is about to rebuild from raw markdown).
  if (toolsUnsupportedEvent) {
    renderToolsUnsupportedNotice(bubble, toolsUnsupportedEvent);
  }
  // What this answer cost: model, wall-clock time, tokens, speed.
  const elapsedMs = Math.round(performance.now() - startedAt);
  //: For the status bar's AI dot (Placed 2026-09-09 item 99 (c)).
  if (stats) {
    lastAnswerFacts = { model: stats.model || (meta && meta.answered_by) || "", ms: elapsedMs, used: Number(stats.prompt_tokens) || 0, window: Number(stats.context_tokens) || 0 };
    renderAiPill();
  }
  // A turn that only ran tools still cost time and tokens, so it gets a meta
  // line too: previously an agent turn with no prose showed nothing at all.
  //: **Who wrote it, in the head** (the owner, 2026-10-10: "should say if the
  //: composer or a specific ai model generated it"): "Atlas, from your notes"
  //: or "Atlas, <model>", where a chip under the answer used to say only the
  //: first. **And a composed answer arrives** ("Composer responses just
  //: appear, I think there should be an animation"): it lands in one piece,
  //: so its blocks rise in turn, `--motion-step` apart, as a streamed one
  //: grows; under reduced motion it simply appears.
  //: No model wrote it and it is not quoted from the notes (a greeting, a
  //: time, a count, a capability answer): the engine answered, and says so
  //: ("hey :D" got an unlabelled "Atlas", the owner, 2026-10-12).
  const by = meta?.composed ? "from your notes" : stats?.model || meta?.answered_by || (meta ? "composer" : "");
  const who = bubble.querySelector(".msg-role > span:last-child");
  if (answerRaw && by && who) who.textContent = `${bubble.dataset.persona}, ${by}`;
  if (meta?.composed && !reducedMotionWanted()) {
    bubble.querySelectorAll(".bubble-answer > *").forEach((el, i) =>
      el.animate([{ opacity: 0, translate: "0 4px" }, {}], { duration: 200, delay: i * 60, easing: "ease-out", fill: "backwards" }));
  }
  if (answerRaw || toolEvents.length) {
    bubble.appendChild(
      messageMetaLine({
        model: (stats && stats.model) || (meta && meta.answered_by),
        elapsedMs,
        stats,
        toolCount: toolEvents.length,
        rounds: (stats && stats.round) || 0,
        usedTools: effectiveUseTools,
      })
    );
  }
  // A turn that stopped short offers the way onward, in the two shapes it can
  // take. Not shown when the user pressed Stop, they know why it ended, and
  // not when a skill run finished every step it had.
  // A run that stopped early is exactly the kind of thing you find out about
  // ten minutes later, having walked away from a long job (§36E). The Resume
  // button below is the fix in the moment; this is the record afterwards.
  // A deliberate manual-mode pause is not a failure and not something to
  // notify about ten minutes later, the person is sitting right here
  // waiting for the Continue button, which is the whole point of asking for
  // it. Only an *unplanned* stop (a real failure, or running out of rounds)
  // earns the notification.
  if (!stopped && !pausedForManual && (stoppedAtStep !== null || ranOutOfRounds)) {
    recordNotification({
      kind: "run",
      title: opts.skill ? `“${opts.skill}” stopped early` : "A long answer stopped early",
      detail:
        stoppedAtStep !== null
          ? `Got as far as step ${stoppedAtStep + 1}. Reopen the chat to resume.`
          : "It ran out of rounds. Reopen the chat to continue.",
      key: `run:${opts.skill || "answer"}:${Date.now()}`,
      action: { tab: "chat" },
    });
  }
  //: **A run you stopped can be picked up again.** Reported: "cant continue
  //: canceled skills??", and it was exactly that, every resume control below
  //: was guarded by `!stopped`. The guard belongs on the *notification* above
  //: (nobody wants to be told ten minutes later about a stop they chose) and
  //: never belonged on the button: pressing Stop means "not right now", not
  //: "throw away the six steps that already ran". Resuming a stopped run is
  //: the same call as resuming one that hit the round limit, and the step it
  //: reached was already being tracked for the other case.
  //: **Phase D's third third.** Resuming carries on from the step that stopped
  //: the run; this changes that step first. A run that stalled on step 4
  //: because the step was written for a bigger model is fixed by rewriting
  //: step 4, and without this the only way to find out whether the rewrite
  //: works is to run the whole skill again, every earlier step of which writes
  //: to the notebook. It runs that step and stops, so the rest of the skill is
  //: still there to resume afterwards.
  //: Built from this turn's own state and, on a reopened conversation, from
  //: the copy of it saved with the turn. See `appendRunResumeControls`.
  const resumeState = {
    skill: opts.skill || null,
    skillInputs: opts.skillInputs || {},
    stopped,
    stoppedAtStep,
    pausedForManual,
    ranOutOfRounds,
    hasTools: toolEvents.length,
  };
  appendRunResumeControls(bubble, { ...resumeState, timeline });
  chatScrollToEnd();
  if (toolsActed) refreshAfterToolChanges(); // the AI changed real data
  if (handoff) {
    // Start the run as its own message, down the same path the Skill dropdown
    // uses: so the plan, the ticked steps, the change list and every Undo
    // work here exactly as they do when the user picks the skill themselves.
    // Deferred by a task because this turn is still finishing: it re-enables
    // the input box in `finally`, and the run needs to disable it again.
    //: A plan the model drew waits for Run the plan (row 3: approved once,
    //: with each step's writes listed); a skill the person saved starts.
    const plan = handoff;
    if (plan.type === "run_plan") planProposalCard(timeline.holder, plan, () => startPlannedRun(plan.goal, plan.steps));
    else setTimeout(() => startSkill({ name: plan.skill }, plan.inputs || {}), 0);
  }
  if (!answerRaw) {
    // The model returned nothing. This used to return early and leave the
    // bubble sitting there with the notes disclosure, no answer, no error and
    // no buttons: a dead end with nothing to click and nothing explaining it.
    if (opts.replaceLast) {
      // A regenerate already removed the old answer; don't leave a blank in
      // its place, since the previous one is gone either way.
      bubble.remove();
      toast("The model returned nothing that time. Try again.", "info");
      return;
    }
    // A turn that ended by starting a skill said nothing on purpose, the run
    // below is the answer. Complaining that the model wrote nothing would be
    // wrong, and the retry button would re-run the choosing turn rather than
    // the skill.
    if (!stopped && !handoff && !asked) {
      const note = document.createElement("p");
      note.className = "muted";
      note.textContent =
        "The model finished without writing anything. That usually means it ran " +
        "out of context or the model is struggling with this question, try again, " +
        "or rephrase it.";
      timeline.ensureAnswerBox().replaceChildren(note);
      // Retry and delete at minimum, so there's always a way forward.
      bubble.appendChild(
        chatMessageActions([
          { label: "ph:arrow-clockwise", title: "Try again", onClick: () => regenerateLastAnswer() },
          { label: "ph:trash", title: "Delete this message", onClick: () => removeChatBubble(bubble) },
        ])
      );
      chatScrollToEnd();
    }
    return;
  }
  // Per-message actions: one shared list with the reopened-conversation path,
  // see `assistantMessageActions` for why that matters.
  bubble.appendChild(
    assistantMessageActions({ bubble, text: answerRaw, question })
  );

  // Regenerate replaces the last turn; a normal send appends a new one.
  if (opts.replaceLast && convRef.turns.length) {
    convRef.turns[convRef.turns.length - 1] = { question, answer: answerRaw, objects: chatTurnObjects(turnSources) };
  } else {
    convRef.turns.push({ question, answer: answerRaw, objects: chatTurnObjects(turnSources) });
  }
  // Persist the finished turn so the chat survives restarts. A checkpoint
  // still on its way is let land first, so this sees its id and replaces its
  // row rather than racing it to create a second conversation.
  if (checkpointRun) await checkpointRun;
  try {
    const payload = {
      question,
      answer: answerRaw || (askedQuestion ? `Asked: ${askedQuestion}` : ""),
      thinking: thinkingRaw || null,
      tools: toolEvents.length ? toolEvents : null,
      // The run in the order it happened, so reopening the chat shows the
      // same step-by-step process rather than a flattened summary.
      steps: timeline.serialise(),
      // What this turn cost, so the conversation can show a running total.
      // Prompt + output, because both were sent through the model.
      tokens: stats
        ? (stats.prompt_tokens || 0) + (stats.output_tokens || 0)
        : null,
      // The whole metadata line, not just its total. `tokens` above is a sum,
      // which is right for the conversation's running total and useless for
      // rebuilding "3.9k/8k window · 12 tok/s · llama3.2", so on reload the
      // line used to vanish and the answer looked like it came from nowhere.
      stats: stats || null,
      // §89.4: which mode actually answered this turn (Ask vs. Agent): a
      // conversation can span mode switches, so this has to be per-turn, not
      // read off the toggle's current state on reload.
      used_tools: effectiveUseTools,
      //: Which persona wrote this reply, so reopening the chat draws its face
      //: and not whichever persona the picker shows by then.
      persona: savedPersona(sentPersona),
      //: What the Resume and Edit-step buttons need to exist again after a
      //: reload (`appendRunResumeControls`). Sent only for a turn that has
      //: somewhere to resume *to*: an ordinary answer would otherwise carry
      //: five null fields on every row for the sake of a button it never
      //: draws.
      resume:
        resumeState.stoppedAtStep !== null ||
        resumeState.stopped ||
        resumeState.ranOutOfRounds
          ? resumeState
          : null,
      // How long the answer took, measured here because the client is the only
      // thing that saw the whole turn: the server reports per-round timings,
      // and an agent turn is several rounds plus the tool calls between them.
      elapsed_ms: elapsedMs,
      // The "N matching notes" disclosure's own data. Reported: "semantic
      // search results in chat messages keep disappearing" - true on every
      // reload, since none of this was ever saved. Only meaningful for a
      // grounded (non-conversational) turn that actually searched, so
      // omitted rather than sent empty when there's nothing to show.
      raw_results: meta?.raw_results?.length ? meta.raw_results : null,
      search_mode: meta?.search_mode || null,
      match_info: meta?.match_info && Object.keys(meta.match_info).length ? meta.match_info : null,
      connected_ids: meta?.connected_ids?.length ? meta.connected_ids : null,
      // The "Grounded in" chips' own data: same reasoning as raw_results
      // just above. Only meaningful alongside raw_results (renderAnswerGrounding
      // looks note content up in it), so there's nothing to persist without it.
      sentence_grounding: groundingSentences?.length ? groundingSentences : null,
      // Which uploads this turn actually used, asked for directly: without
      // this, a sent chat image had no record anywhere that anything still
      // used it, so the Library's "Clean orphaned media" tool (which can
      // only check notes, documents and whiteboard content for `/media/…`
      // references) would delete a real, sent attachment's file the moment
      // someone ran it. Persisting the ids here is what lets media_gc.py
      // recognise them as still in use.
      image_media_ids: sentImages.length ? sentImages : null,
      // Same reason as the ids above, one kind over: a document attached to a
      // message is what lets the bubble draw its chip again on reopen.
      document_ids: sentDocuments.length ? sentDocuments : null,
      file_ids: sentFiles.length ? sentFiles : null,
      // And the notes clipped with the paperclip, which until now were used to
      // build one prompt and then forgotten, the bubble showed no sign the
      // answer had been given a note to read.
      note_ids: sentAttachments.length ? sentAttachments : null,
      followup_of: followupOf,
      //: The thumbnails' words, so a reopened chat keeps them (INBOX 502).
      picture_alts: meta?.picture_alts && Object.keys(meta.picture_alts).length ? meta.picture_alts : null,
      picture_sizes: meta?.picture_sizes && Object.keys(meta.picture_sizes).length ? meta.picture_sizes : null,
    };
    if (convRef.id === null) {
      const created = await apiJson("/conversations", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      convRef.id = created.id;
      if (viewing()) {
        $("chat-title").textContent = created.title;
        renderChatUsage(created.tokens);
      }
      // A name typed before the first message was sent beats both the
      // question-derived title and the model's. See `renameCurrentConversation`.
      const namedByHand = applyPendingChatTitle(created.id, viewing());
      // Let the AI name the thread once there's something to name. Silent
      // best-effort: the question-derived title stays if the model can't.
      if (!namedByHand) {
        apiJson(`/conversations/${created.id}/retitle`, { method: "POST", silent: true })
          .then((named) => {
            if (chatConv.id === created.id) $("chat-title").textContent = named.title;
            loadConversationList();
          })
          .catch(() => {});
      }
    } else if (opts.replaceLast || checkpointed) {
      // `checkpointed` matters as much as `replaceLast` here: a long agent
      // turn has already written a row for this exchange (see checkpointTurn),
      // so appending would leave the conversation holding the same question
      // twice: once half-finished and once complete.
      const saved = await apiJson(`/conversations/${convRef.id}/turns/last`, {
        method: "PUT",
        body: JSON.stringify(payload),
      });
      if (viewing()) renderChatUsage(saved.tokens);
    } else {
      const saved = await apiJson(`/conversations/${convRef.id}/turns`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
      if (viewing()) renderChatUsage(saved.tokens);
    }
    loadConversationList();
  } catch {
    toast("Couldn't save this chat turn.", true);
  }
  loadRecentQuestions();
  loadMostUsed();
  // Last, and deliberately not awaited: the answer is already on screen and
  // saved, and this is a second model call. See offerFollowups. A composed
  // answer (no model running) brings its own next questions (INBOX 725).
  offerFollowups(bubble, question, answerRaw, meta?.composed ? composedNext : null);
}

// --- "what to ask next" chips under a finished answer -------------------------
//
// The empty-state chips (loadChatSuggestions) taught the feature for the first
// question and then went away, which left every turn after it ending on a blank
// box. These are the same idea for the turn you just read.
//
// Three things this must not do, all of which are why it lives out here rather
// than inside the streaming loop:
//
// - **Delay the answer.** It fires after the turn is rendered and saved, and
//   nothing awaits it.
// - **Show an error.** `/chat/followups` returns [] on every failure path
//   including the AI being off, and [] renders nothing at all. A row that says
//   "couldn't suggest anything" is worse than no row.
// - **Attach to the wrong bubble.** The reply can land after the reader has
//   sent another message or opened a different conversation, so the bubble it
//   was asked for has to still be on screen when it does.
async function offerFollowups(bubble, question, answer, given = null) {
  if (!bubble || !question || !answer) return;
  //: `given`: a composed answer's own next questions, already in hand.
  let picks = given || [];
  if (!given) {
    try {
      picks = await apiJson("/chat/followups", {
        method: "POST",
        silent: true,
        body: JSON.stringify({ question, answer }),
      });
    } catch {
      return; // no honest error state for a suggestion, see the module note
    }
  }
  if (!Array.isArray(picks) || !picks.length) return;
  // `isConnected` is the check that matters: a deleted turn, a cleared chat or
  // a switched conversation all detach the bubble, and appending to a detached
  // node is an invisible leak rather than a visible bug.
  if (!bubble.isConnected) return;
  renderFollowups(bubble, picks);
  // Saved, so they are still there next time. Reported directly: "suggested
  // repsponse continuation prompts in chat doesnt persist and disappears once
  // I switch chat sessions or quit the app", they never persisted because
  // nothing stored them; they lived only on this DOM node.
  //
  // Not awaited and silent, for the same reason the request above is: this is
  // bookkeeping behind a suggestion, and a failed save must not put an error
  // on screen over an answer that is fine.
  saveFollowups(bubble, picks);
}

// The strip itself, shared by the live path above and the reopen path in
// `openConversation`, two renderers would be two chances for a saved chip to
// look unlike a fresh one.
function renderFollowups(bubble, picks) {
  if (!bubble || !Array.isArray(picks) || !picks.length) return;
  // Stored, not only drawn: deleting the newest turn brings the previous
  // turn's chips back without asking the model again (the owner's report).
  bubble.dataset.followups = JSON.stringify(picks);
  refreshFollowupVisibility();
}

// Exactly one strip in the thread, on the last answer in it.
//
// Chips under an older answer are an invitation to fork the conversation
// backwards: clicking one sends its question as a *new* message at the end, so
// the suggestion and the place the reply lands are three exchanges apart. Only
// the newest answer is still the end of the thread, so only it gets them.
function refreshFollowupVisibility() {
  const bubbles = [...$("chat-messages").querySelectorAll(".msg.assistant")];
  const last = bubbles.at(-1);
  for (const bubble of bubbles) {
    const strip = bubble.querySelector(".chat-followups");
    if (bubble !== last) {
      strip?.remove();
      continue;
    }
    if (strip) continue; // already showing this turn's chips
    let picks = [];
    try {
      picks = JSON.parse(bubble.dataset.followups || "[]");
    } catch {
      picks = [];
    }
    if (picks.length) buildFollowupStrip(bubble, picks);
  }
}

function buildFollowupStrip(bubble, picks) {
  const strip = document.createElement("div");
  strip.className = "chat-followups";
  const label = document.createElement("span");
  label.className = "muted";
  label.textContent = "Next:";
  strip.appendChild(label);
  for (const pick of picks) {
    // chip()'s second argument is a class, not a tooltip, passing prose there
    // would put a sentence into `className`.
    strip.appendChild(chip(pick, "", () => sendChatMessage(pick, { followupOf: followupParent(bubble) })));
  }
  bubble.appendChild(strip);
  chatScrollToEnd();
}

// --- where a follow-up came from (INBOX 490: "hyperlinked bread crumbs") ----
// A chip's question keeps the one it was offered under (`followup_of` on the
// turn, words not an index, which a deleted turn would shift); its bubble
// links the chain back, a press scrolling to that question and lighting it.
function followupParent(bubble) {
  let el = bubble.previousElementSibling;
  while (el && !el.matches(".msg.user")) el = el.previousElementSibling;
  return el?.dataset.sent || "";
}

//: Saved content may carry Plan mode's block after the words.
const followupMatches = (sent, ref) => Boolean(sent) && (sent === ref || sent.startsWith(ref));

function followupChain(userBubble) {
  const users = [...$("chat-messages").querySelectorAll(".msg.user")];
  const chain = [];
  let at = users.indexOf(userBubble);
  let ref = userBubble.dataset.followupOf;
  while (ref && at > 0 && chain.length < 8) {
    let i = at - 1;
    while (i >= 0 && !followupMatches(users[i].dataset.sent, ref)) i -= 1;
    if (i < 0) break;
    chain.unshift(users[i]);
    at = i;
    ref = users[i].dataset.followupOf;
  }
  return chain;
}

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

function markFollowup(userBubble, ref) {
  if (!userBubble || !ref) return;
  userBubble.dataset.followupOf = ref;
  userBubble.querySelector(":scope > .chat-trail")?.remove();
  const chain = followupChain(userBubble);
  if (!chain.length) return;
  const trail = followupTrail(chain.map((b) => b.dataset.sent), (i) => {
    const target = chain[i];
    if (!target.isConnected) return;
    target.scrollIntoView({ behavior: reducedMotionWanted() ? "auto" : "smooth", block: "center" });
    target.classList.remove("flash");
    void target.offsetWidth; // restart the highlight on a second press
    target.classList.add("flash-target", "flash");
    clearTimeout(target.flashTimer);
    target.flashTimer = setTimeout(() => target.classList.remove("flash"), 2700);
  });
  userBubble.querySelector(":scope > .msg-body")?.before(trail);
}

async function saveFollowups(bubble, picks) {
  if (chatConv.id === null) return; // an unsaved chat has no turn to attach to
  // Which turn this bubble is: its index among the assistant bubbles, which is
  // exactly how every other per-turn endpoint in this file addresses one.
  const bubbles = [...$("chat-messages").querySelectorAll(".msg.assistant")];
  const index = bubbles.indexOf(bubble);
  if (index === -1) return;
  const conversationId = chatConv.id;
  await apiJson(`/conversations/${conversationId}/turns/${index}/followups`, {
    method: "PUT",
    silent: true,
    body: JSON.stringify({ followups: picks }),
  }).catch(() => {});
}

// Delete one Q&A exchange: its assistant bubble AND the user bubble just
// above it, from the screen, memory, and the saved conversation.
async function deleteChatTurn(assistantBubble) {
  if (chatController) return; // don't edit a chat mid-stream
  const bubbles = [...$("chat-messages").querySelectorAll(".msg.assistant")];
  const index = bubbles.indexOf(assistantBubble);
  if (index === -1) return;
  if (!(await confirmDialog("Delete this message?"))) return;

  if (chatConv.id !== null) {
    try {
      const id = chatConv.id;
      const result = await apiJson(`/conversations/${id}/turns/${index}`, {
        method: "DELETE",
      });
      chatWriteRecord("chatTurnUndo", id, index, result);
      if (result.conversation_deleted) {
        newChatConversation();
        loadConversationList();
        return;
      }
    } catch {
      toast("Couldn't delete that message.", true);
      return;
    }
  }
  // The user bubble is the one immediately before this assistant bubble.
  const userBubble = assistantBubble.previousElementSibling;
  if (userBubble && userBubble.classList.contains("user")) userBubble.remove();
  assistantBubble.remove();
  chatConv.turns.splice(index, 1);
  // The turn below is the end of the thread now, so its saved chips come back.
  refreshFollowupVisibility();
  if (!$("chat-messages").querySelector(".msg")) renderChatEmptyState();
  loadConversationList();
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

// Put the counter in the bubble this turn is being written into.
function mountChatTimer(bubble) {
  if (!bubble) return;
  chatTimerBox?.remove();
  const box = document.createElement("span");
  box.className = "msg-timer";
  box.setAttribute("aria-hidden", "true"); // the status line already says it aloud
  chatTimerBox = box;
  // Beside the role label, which is the bubble's own header row, it reads as
  // "LIBRARIAN · 4s" rather than as a number floating in the answer.
  (bubble.querySelector(".msg-role") || bubble).appendChild(box);
  paintChatTimer();
}

function paintChatTimer() {
  const box = chatTimerBox;
  if (!box) return;
  const seconds = Math.floor((performance.now() - chatTimerStartedAt) / 1000);
  // Plain seconds under a minute, m:ss above it, "97s" is a number you have
  // to convert, and by then it is the interesting case.
  box.textContent =
    seconds < 60
      ? `${seconds}s`
      : `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}

function startChatTimer() {
  // Started before the bubble exists, the clock has to include the wait for
  // the first byte, which on a cold local model is most of it. `mountChatTimer`
  // gives it somewhere to draw a moment later.
  clearInterval(chatTimerInterval);
  chatTimerStartedAt = performance.now();
  chatTimerInterval = setInterval(paintChatTimer, 1000);
}

function stopChatTimer() {
  clearInterval(chatTimerInterval);
  chatTimerInterval = null;
  // Taken off screen, not left showing: the answer is finished, and its
  // metadata line already carries the final duration. A live-looking counter above a
  // finished answer is the bug this replaced.
  chatTimerBox?.remove();
  chatTimerBox = null;
}

function releaseChatComposer({ announce = true } = {}) {
  //: Called by every way out of a chat: the page it read is that chat's.
  chatWeb.lastUrl = null;
  if (!chatController || !chatStreaming) return;
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

//: True when the conversation being opened is the one still being written to.
function isStreamingConversation(id) {
  return Boolean(chatController && chatStreaming && chatStreaming.conv.id === id);
}

//: Put the in-flight turn back on screen, still streaming.
//:
//: The nodes were never destroyed, `openConversation` detached them with
//: `replaceChildren()` and this re-appends the same elements, so whatever the
//: stream has written since is already in them and whatever it writes next
//: lands in front of the reader. That is the difference between the reported
//: "the response only shows after it is completed" and watching it arrive.
function reattachStreamingTurn() {
  if (!chatStreaming) return false;
  const host = $("chat-messages");
  clearChatEmptyState();
  for (const node of chatStreaming.nodes) host.appendChild(node);
  chatScrollToEnd();
  return true;
}

function newChatConversation() {
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
  // batch-a.md's "left open" item, its actual cause: `#chat-suggest` is on
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
  if (chatConv.id === null && !chatConv.turns.length) {
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
