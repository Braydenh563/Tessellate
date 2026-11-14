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
      if (!kept) toast(error.message || voiceLine("failed", { what: `read "${file.name}"` }), true);
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
      : `Added ${nounCount(made.length, "file")} to your documents.`;
  toastAction(label, made.length === 1 ? "Open it" : "Show them", () => {
    switchTab("documents");
    if (made.length === 1) openDocument(first.id);
  }, { go: made.length === 1 ? { open: "doc", id: first.id } : { tab: "documents" } });
}
