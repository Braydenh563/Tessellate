// chat-docs.js: what happens to a non-image file chosen in the chat (imported as a document, or kept
// in the Library when its words cannot be read). Moved whole from chat-attach.js to be fetched on the
// first such file (`LAZY_MODULES.chatDocs`, stand-ins installed by lazy-entries.js): its callers
// (`attachChatFiles`, the popup agent's staging) already await it. The boot scripts were over their
// gzip total when the Quick capture card began sharing the attachment chip.

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
    async () => {
      await switchTab("library");
      document.querySelector('#library-subtabs [data-media-kind="files"]')?.click();
    },
    { go: { tab: "library", media: "files" } },
  );
  return true;
}

//: **Staged, not imported.** The owner, 2026-11-22: a .py chosen in the chat was in the Documents
//: library before the message was sent. Now the file stays in the browser as a chip, the same way an
//: image does (`attachImageFiles`), and `commitStagedDocuments` imports it on send. Removing the chip,
//: or leaving the message unsent, leaves nothing on the server: no document, no Library file.
async function importChatDocuments(files) {
  for (const file of files) {
    if (attachedDocuments.length >= MAX_CHAT_DOCUMENTS) break;
    attachedDocuments.push({ key: `staged-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`, file, name: file.name });
  }
  renderDocumentAttachments();
  announce(`${nounCount(attachedDocuments.length, "document")} attached. Saved to your documents when you send.`);
}

//: On send: each staged file becomes a real document (or, when its words cannot be read, a Library file),
//: and its chip keeps the document's id so the bubble links to it. A file that could be neither is
//: dropped from the message with its own toast, as the attach step used to do.
async function commitStagedDocuments() {
  const made = [];
  for (const staged of attachedDocuments.filter((d) => d.file)) {
    const form = new FormData();
    form.append("file", staged.file);
    try {
      // Same header handling as commitStagedImages: a FormData body needs the
      // browser to set its own multipart boundary.
      const document_ = await apiJson("/documents/import", {
        method: "POST",
        headers: authHeaders(),
        body: form,
      });
      Object.assign(staged, { id: document_.id, name: document_.title, file: null });
      made.push(document_);
    } catch (error) {
      //: **A file the app cannot read is still a file worth keeping** (REDESIGN.md §R7.2): a PDF whose
      //: text cannot be extracted goes to `/media/upload`, the Library's own store, and the toast says
      //: where it went and why the text is missing.
      const kept = await keepUnreadableChatFile(staged.file, error);
      if (!kept) toast(error.message || voiceLine("failed", `read "${staged.name}"`), true);
      staged.file = null;
    }
  }
  attachedDocuments = attachedDocuments.filter((d) => d.id);
  renderDocumentAttachments();
  if (!made.length) return;
  offerCreatedDocsUndo(made);
  const first = made[0];
  const label =
    made.length === 1
      ? `Added “${first.title}” to your documents.`
      : `Added ${nounCount(made.length, "file")} to your documents.`;
  toastAction(label, made.length === 1 ? "Open it" : "Show them", () => {
    switchTab("documents");
    if (made.length === 1) openDocument(first.id);
  }, { go: made.length === 1 ? { open: "doc", id: first.id } : { tab: "documents" } });
}
