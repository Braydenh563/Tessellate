// documents-export-ops.js: export to .md, .html, .docx, .pdf and a bundle, and the delete, rename, archive and restore operations with their Undo.
// Moved out of documents.js whole (L-documents-117) and wrapped: only what other files call goes on `window`.
(() => {
  //: One file name for every export: the server's rule (`_safe_filename`)
  //: written once more for the formats the browser builds itself, so a
  //: document is "Sleep-essay" as .md, .zip, .docx and .html alike.
  function docExportName(title, ext) {
    //: A code file's title is its file name ("app.py"): the dot stays, so the
    //: download is "app.py.html" and not "apppy.html".
    const cleaned = String(title || "").replace(/[^\p{L}\p{N}_\s.-]/gu, "").replace(/\.{2,}/g, ".").replace(/^\.+/, "").trim() || "document";
    return `${cleaned.replace(/[\s_]+/g, "-").slice(0, 60)}.${ext}`;
  }

  //: **One download, four routes to it.** The markdown, the bundle and the Word
  //: file are the same three steps (ask the server, read the filename off the
  //: header, save the blob) and differed only in the path, which is how the
  //: second one grows a subtly different error path from the first. The message
  //: on a refusal is the server's own `detail` where there is one: "this install
  //: has no Word exporter" is worth reading, and "Export failed (501)" is not.
  async function downloadDocumentExport(path, fallbackName) {
    if (!currentDoc) return;
    //: Fetched rather than navigated to. A plain link carries no X-Auth-Token,
    //: so the server answers 401 and the browser renders that error *in place of
    //: the app*: it navigates away instead of downloading.
    try {
      // `api()` (F5) throws the server's own sentence on a refusal.
      const response = await api(`/documents/${currentDoc.id}/${path}`);
      const disposition = response.headers.get("content-disposition") || "";
      const match = disposition.match(/filename="([^"]+)"/);
      await saveFile(match ? match[1] : fallbackName, await response.blob());
      const assets = Number(response.headers.get("X-Assets") || 0);
      if (assets > 0) {
        toast(`Saved with ${nounCount(assets, "image")} beside it`);
      }
    } catch (error) {
      $("doc-status").classList.add("error");
      $("doc-status").textContent = error.message;
    }
  }

  //: A code file: no rendered form, and not the plain text or CSV a Word file or
  //: an image bundle still makes sense for. Its Download as .py is the file.
  function docIsCodeFile() {
    const type = docFileType();
    return !type.previewable && !["txt", "csv"].includes(type.ext);
  }

  //: The prose exports (images bundle, Word) turn markdown into something; a
  //: code file has no markdown, so they say so rather than saving a mangled file
  //: (the palette reaches these through a button the menu has hidden).
  function docCodeExportRefused(what) {
    if (!docIsCodeFile()) return false;
    toast(`${what} is for writing. A code file downloads as itself: use Download as .${docFileType().ext}.`, "info");
    return true;
  }

  function exportDocumentBundle() {
    if (docCodeExportRefused("The image bundle")) return;
    return downloadDocumentExport("export.zip", "document.zip");
  }

  //: Replace in every document: the dialog's code is documents-replace.js,
  //: fetched on the first press (audit 1031 DC13).
  async function openDocReplace(carry = null) {
    if (!(await lazyScript("/js/documents-replace.js"))) return toast("Replace in every document could not be loaded.", true, { action: ["Try again", () => openDocReplace(carry)] });
    return docReplaceOpen(carry);
  }

  //: Written in the browser by documents-word.js (Brief 42), loaded on the
  //: first press: no server extra to install, so no 501.
  async function exportDocumentDocx() {
    if (docCodeExportRefused("The Word export")) return;
    if (!(await lazyScript("/js/documents-word.js"))) return toast("The Word writer could not be loaded.", true, { action: ["Try again", exportDocumentDocx] });
    return docWordExport();
  }

  //: The same fetch, name and save as the zip and the Word file (audit FE-16:
  //: this was a second copy of `downloadDocumentExport`).
  function exportDocumentMarkdown() {
    return downloadDocumentExport("export.md", "document.md");
  }


  //: What comes out of the app and what does not. Everything in this list is
  //: something that works only inside a running Tessellate: a button with a
  //: listener that no longer exists, an icon whose font is not in the file, a
  //: link to `/documents/12`. Shipped as-is they would be an empty square, a
  //: dead control and a 404; dropped, the page reads.
  //: **One list of the renderer's chrome for the page, the file and the paper**
  //: (audit 1102 DX8, DX9): a code or table bar ("JS", "Copy", "Save"), a
  //: remote picture's "not loaded" note and a footnote's "Back" link are
  //: controls for the screen. The HTML export, the Word export
  //: (documents-word.js adds `button`) and the print rule
  //: (`body.printing-doc` in library-lazy.css) all drop these three, and
  //: `tests/test_docs_1102_dx.py` pins that the lists agree.
  const DOC_EXPORT_STRIP = ".code-bar, .entry-image-note, a.md-fn-back, .code-actions, select, textarea, script, iframe, object, embed, i.ph, .ph-lead";

  //: **A control goes; the words it was wrapped around stay.** A `[[wikilink]]`
  //: renders as a `button.wiki-link` here, because in the app it opens the thing
  //: it names. Removing it with the other controls took the name out of the
  //: sentence: an exported page read "A link into the app: ." Measured, and it
  //: is the reason this is two rules rather than one selector.
  function docExportUnwrapControls(root) {
    for (const node of [...root.querySelectorAll("button")]) {
      const words = (node.textContent || "").trim();
      //: A table of notes names each row by a button (`db-open`); the words are the row, so they stay as text like a wiki link does.
      if (!words || !node.matches(".wiki-link, .db-open")) {
        node.remove();
        continue;
      }
      const span = document.createElement("span");
      span.className = "doc-export-link";
      span.textContent = words;
      node.replaceWith(span);
    }
  }

  //: **The rendered pane's headings start at `h3`**, because the app's page
  //: already has an `h1` and an `h2` above the document and a pane that shouted
  //: over them would be wrong on screen. A file on its own has no such page: its
  //: first heading is the top of the only document there is. So the levels shift
  //: by two on the way out, which is the same hierarchy with its top where a
  //: standalone page expects it. The map is written out rather than computed so
  //: that `h6`, which has nowhere lower to go, is a decision rather than an
  //: arithmetic accident.
  const DOC_EXPORT_HEADINGS = { H3: "h1", H4: "h2", H5: "h3", H6: "h4" };

  function docExportPromoteHeadings(root) {
    //: The list is taken before anything is replaced: promoting in place while
    //: iterating a live list would walk into the `h1`s it has just made.
    for (const node of [...root.querySelectorAll("h3, h4, h5, h6")]) {
      const tag = DOC_EXPORT_HEADINGS[node.tagName];
      if (!tag) continue;
      const swap = document.createElement(tag);
      for (const attribute of [...node.attributes]) swap.setAttribute(attribute.name, attribute.value);
      while (node.firstChild) swap.appendChild(node.firstChild);
      node.replaceWith(swap);
    }
  }

  //: A plotted graph and a table of notes carry controls for the screen (zoom, sliders, refresh, the edit pencil). A file has none of
  //: them; the key's swatch is a coloured box whose colour is a style, which the clean-up below drops, so it becomes a drawn bar first.
  //: A property of `docExportClean`, not a name of its own: the shared scope's name count has no slack.
  function docExportClean(root) {
    for (const node of root.querySelectorAll(DOC_EXPORT_STRIP)) node.remove();
    docExportClean.figures(root);
    return docExportClean.rest(root);
  }

  docExportClean.figures = (root) => {
    //: A video is a player on screen and a line of text in a file or on paper: no poster, only its name.
    for (const box of [...root.querySelectorAll(".doc-video")]) {
      const note = document.createElement("p");
      note.className = "doc-export-missing";
      note.textContent = box.querySelector(".doc-video-name")?.textContent || "Video";
      box.replaceWith(note);
    }
    for (const swatch of [...root.querySelectorAll(".dg-swatch")]) {
      const bar = document.createElementNS("http://www.w3.org/2000/svg", "svg");
      bar.setAttribute("class", "dg-swatch");
      bar.setAttribute("width", "16");
      bar.setAttribute("height", "4");
      const fill = document.createElementNS("http://www.w3.org/2000/svg", "rect");
      fill.setAttribute("width", "16");
      fill.setAttribute("height", "4");
      fill.setAttribute("fill", swatch.style.background || "currentColor");
      bar.append(fill);
      swatch.replaceWith(bar);
    }
    for (const node of root.querySelectorAll(".dg-tools, .dg-params, .dg-edit, .db-edit, .db-bar button")) node.remove();
  };

  docExportClean.rest = (root) => {
    docExportUnwrapControls(root);
    docExportPromoteHeadings(root);
    for (const box of root.querySelectorAll('input:not([type="checkbox"])')) box.remove();
    //: A task box stays, because an unticked box in a list is part of what the
    //: document says. Disabled, because ticking it in an exported file would
    //: change nothing anywhere and a control that does nothing is a lie.
    for (const box of root.querySelectorAll('input[type="checkbox"]')) {
      box.setAttribute("disabled", "disabled");
      box.removeAttribute("onclick");
    }
    for (const link of root.querySelectorAll("a[href]")) {
      const href = link.getAttribute("href") || "";
      const external = /^(https?:|mailto:|#)/i.test(href);
      if (!external) link.removeAttribute("href");
    }
    //: Every `data-` attribute in the preview is a handle for this app's own
    //: listeners (a finding's index, a block id, a note id). None of them mean
    //: anything in a file, and one of them, a note id, is data about somebody's
    //: notebook travelling inside a document they meant to share.
    for (const node of root.querySelectorAll("*")) {
      for (const attribute of [...node.attributes]) {
        if (attribute.name.startsWith("data-") || attribute.name.startsWith("on")) {
          node.removeAttribute(attribute.name);
        }
        //: The CSP refuses an inline style in this app's own page and an
        //: exported file has no CSP at all, which is exactly why they are
        //: stripped rather than kept: a style attribute here would be the app's
        //: own token vocabulary (`var(--accent-soft)`) resolving to nothing.
        if (attribute.name === "style") node.removeAttribute("style");
      }
    }
    //: A saved file has no script (L-documents-98, measured in Chromium): a board card dragged there dropped nowhere, and the
    //: view switch and the Group by and Date in pickers were empty shells (a bare "Group by" label), so none of it goes in.
    for (const node of root.querySelectorAll(".db-choose, .db-views, .db-body .menu-wrap")) node.remove();
    for (const card of root.querySelectorAll(".db-card[draggable]")) card.removeAttribute("draggable");
    return root;
  };

  //: The HTML and PDF exports live in documents-export.js, fetched on the first
  //: press of either (audit 1031 DC13).
  async function exportDocumentHtml() {
    if (!(await lazyScript("/js/documents-export.js"))) return toast("The export could not be loaded.", true, { action: ["Try again", exportDocumentHtml] });
    return docExportHtmlRun();
  }

  //: The deck is the same export cut at its headings, so it is a property of the
  //: stand-in rather than a name of its own in the shared scope.
  exportDocumentHtml.slides = async () => {
    if (!(await lazyScript("/js/documents-export.js"))) return toast("The export could not be loaded.", true, { action: ["Try again", exportDocumentHtml.slides] });
    return docExportHtmlRun(true);
  };

  async function exportDocumentPdf() {
    if (!(await lazyScript("/js/documents-export.js"))) return toast("The export could not be loaded.", true, { action: ["Try again", exportDocumentPdf] });
    return docExportPdfRun();
  }


  //: **A deleted document goes to the recycle bin** (WORLD_CLASS_PLAN 5 item
  //: 10), as a note does: `DELETE /documents/{id}` bins it, and Undo is
  //: `POST /documents/{id}/restore`, the same document with its id, its history,
  //: its attached notes and its reminders. Before the bin, Undo re-created the
  //: text as a new document and everything that pointed at the old id was lost.
  //: `pushUndo` puts it on the app-wide stack (Ctrl+Z, the status bar's Undo)
  //: and `toastAction` offers it at once, which is when people notice.
  //: `documents-undone`: the Library lists documents and diagrams too and redraws only on its own actions, so an undo or redo of one (toast, Ctrl+Z, status bar) left a row gone or old until the tab was re-entered (dgmlive2 1108); library.js listens.
  async function deleteDocumentWithUndo(doc, ask = false) {
    //: `ask`: the menus' own question first; false means it was declined and nothing was deleted.
    if (ask && !(await confirmDialog(`Delete "${doc.title || "Untitled"}"? You can undo this straight after.`))) return false;
    await apiJson(`/documents/${doc.id}`, { method: "DELETE" });
    const title = doc.title || "Untitled";
    const action = pushUndo(
      `Moved “${title}” to the bin`,
      async () => {
        await apiJson(`/documents/${doc.id}/restore`, { method: "POST" });
        await loadDocuments(doc.id);
        document.dispatchEvent(new Event("documents-undone"));
      },
      async () => {
        await apiJson(`/documents/${doc.id}`, { method: "DELETE" });
        await loadDocuments();
        document.dispatchEvent(new Event("documents-undone"));
      }
    );
    toastAction(`Moved ${toastName(title, "the document")} to the bin.`, "Undo", async () => {
      await action.undo();
      //: `settleUndoFromToast`, not a bare stack pop: the toast's Undo and the
      //: status bar's Undo are the same action, and without this a later Ctrl+Z
      //: would run the same restore a second time.
      settleUndoFromToast(action);
      toast(`Restored ${toastName(title, "the document")}.`);
    });
  }

  //: **Every act on a document is one undo step** (DOCUMENTS 24 row 1, rule
  //: 1.8). Each goes through `offerUndo`: the step on the app's stack (Ctrl+Z,
  //: the status bar, its history menu) and the toast's Undo are one entry, and
  //: each undo is the server's own inverse (unarchive, re-attach, the old title
  //: put back), so nothing is re-created under a new id. Measured with
  //: `undo.js` and `docacts76.js`: 2 of 11 acts undid before this, 11 of 11 after.
  function docPutFields(id, fields) {
    return apiJson(`/documents/${id}`, { method: "PUT", body: JSON.stringify(fields) });
  }

  async function renameDocumentWithUndo(doc, next) {
    const before = doc.title || "Untitled";
    //: **A write's answer is the row** (audit 1031 DC7, second half): the PUT
    //: returns the document, so the list takes it in place, and the open
    //: document's title box and record follow, where a read of the whole list
    //: (two pages at 230 documents) and a reopen of the open one used to.
    const settle = async (saved, title) => {
      if (currentDoc?.id === saved.id) {
        $("doc-title").value = title;
        currentDoc = { ...currentDoc, title: saved.title, updated_at: saved.updated_at };
      }
      if (!docs.some((d) => d.id === saved.id)) return loadDocuments(currentDoc?.id);
      docs = docs.map((d) => (d.id === saved.id ? { ...d, ...saved } : d));
      renderDocList();
    };
    //: `put` stays one expression so the PUT sits in this function, beside the
    //: `offerUndo` that carries it: tests/test_undo_coverage.py reads a block body
    //: as a function of its own and then finds a write with no undo near it.
    const undone = () => document.dispatchEvent(new Event("documents-undone"));
    const put = async (title) => settle(await docPutFields(doc.id, { title }), title).then(undone);
    const saved = await docPutFields(doc.id, { title: next });
    offerUndo(`Renamed “${clipText(before, 40)}”`, `Renamed to “${clipText(next, 40)}”.`, () => put(before), () => put(next));
    await settle(saved, next);
  }

  async function archiveDocumentWithUndo(doc) {
    const archive = async () => {
      await apiJson(`/documents/${doc.id}/archive`, { method: "PUT" });
      if (currentDoc?.id === doc.id) currentDoc = null;
      await loadDocuments(currentDoc?.id);
    };
    await archive();
    offerUndo(
      `Archived “${clipText(doc.title || "Untitled", 40)}”`,
      "Archived. It is in the Library's Shelved filter.",
      async () => {
        await apiJson(`/documents/${doc.id}/unarchive`, { method: "PUT" });
        await loadDocuments(doc.id);
        document.dispatchEvent(new Event("documents-undone"));
      },
      async () => {
        await archive();
        document.dispatchEvent(new Event("documents-undone"));
      }
    );
  }

  //: Creating is an act too: its undo bins the new document (the recycle bin
  //: keeps its id), its redo brings the same one back. On the stack with no
  //: toast: the new page opening is the answer, and a toast on every page made
  //: would be noise.
  function offerCreateUndo(doc) {
    pushUndo(
      `Created “${clipText(doc.title || "Untitled", 40)}”`,
      async () => {
        await apiJson(`/documents/${doc.id}`, { method: "DELETE" });
        if (currentDoc?.id === doc.id) currentDoc = null;
        await loadDocuments(currentDoc?.id);
      },
      async () => {
        await apiJson(`/documents/${doc.id}/restore`, { method: "POST" });
        await loadDocuments(doc.id);
      }
    );
  }

  //: Several documents made by one act (an import): one step that bins them all
  //: and, on redo, brings the same ones back.
  function offerCreatedDocsUndo(docs) {
    if (docs.length === 1) return offerCreateUndo(docs[0]);
    const each = (verb) => async () => {
      for (const doc of docs) {
        if (verb === "bin") await apiJson(`/documents/${doc.id}`, { method: "DELETE" });
        else await apiJson(`/documents/${doc.id}/restore`, { method: "POST" });
      }
      await loadDocuments(currentDoc?.id);
    };
    return pushUndo(`Imported ${nounCount(docs.length, "document")}`, each("bin"), each("restore"));
  }

  //: A note's link to this document, either way round. The server answers with
  //: the whole document, which is what the panel draws from.
  async function docSetNoteLink(docId, noteId, linked) {
    const full = linked
      ? await apiJson(`/documents/${docId}/notes`, { method: "POST", body: JSON.stringify({ entry_id: noteId }) })
      : await apiJson(`/documents/${docId}/notes/${noteId}`, { method: "DELETE" });
    if (currentDoc?.id === docId) currentDoc = full;
    renderDocNotes();
    //: Detaching can move a note *into* the backlinks list: it may still
    //: mention this document by [[title]], and that connection only becomes
    //: visible once it is no longer filed under it.
    renderDocBacklinks();
    loadEntries();
  }

  async function unlinkDocNoteWithUndo(note) {
    const docId = currentDoc.id;
    await docSetNoteLink(docId, note.id, false);
    offerUndo("Detached a note", "Note detached. The note itself is kept.", () => docSetNoteLink(docId, note.id, true), () => docSetNoteLink(docId, note.id, false));
  }

  async function docSetBookmark(docId, bookmarkId, attached) {
    await (attached
      ? apiJson(`/documents/${docId}/bookmarks`, { method: "POST", body: JSON.stringify({ bookmark_id: bookmarkId }) })
      : apiJson(`/documents/${docId}/bookmarks/${bookmarkId}`, { method: "DELETE" }));
    if (currentDoc?.id === docId) renderDocBookmarks();
  }

  async function docBookmarkWithUndo(bookmarkId, attached) {
    const docId = currentDoc.id;
    await docSetBookmark(docId, bookmarkId, attached);
    offerUndo(
      attached ? "Attached a link" : "Removed a link",
      attached ? "Link attached." : "Link removed.",
      () => docSetBookmark(docId, bookmarkId, !attached),
      () => docSetBookmark(docId, bookmarkId, attached)
    );
  }

  //: The restored text goes in outside the editor's own history: the restore is
  //: one step on the app's stack, and the same change in both would have Ctrl+Z
  //: undo it twice.
  //: `keep` puts the change on the undo stack as one step: a replace across
  //: documents is the person's act, so Ctrl+Z in the editor takes it back (1031
  //: DC4: it did nothing, because the text came in outside the history).
  function docWriteOutsideHistory(text, keep = false) {
    const CM = window.CM6;
    if (!docCmView || !CM) {
      docSurface().text = text;
      return;
    }
    const current = docStr(docCmView.state.doc);
    if (current === text) return;
    const [from, to, insert] = docUndoDiffRange(current, text);
    docCmView.dispatch({ changes: { from, to, insert }, annotations: CM.state.Transaction.addToHistory.of(keep) });
  }

  function docShowSaved(saved, keep = false) {
    docs = docs.map((d) => (d.id === saved.id ? { ...d, ...saved } : d));
    if (currentDoc?.id !== saved.id) {
      renderDocList();
      return;
    }
    currentDoc = saved;
    docWriteOutsideHistory(saved.content || "", keep);
    $("doc-title").value = saved.title || "";
    renderDocPreview();
    docDirty = false;
    //: The write above reads as an edit and starts the autosave; the text is the server's own,
    //: and a save of it after an Undo had changed it again was a false 409 (L-documents-41).
    clearTimeout(docSaveTimer);
    $("doc-saved").textContent = "Saved";
    renderDocList();
  }

  //: **A restore is one step, not a confirm** (DOCUMENTS 24 row 4, the rule
  //: note-history.js's `restoreTo` already follows): it happens at once and
  //: Ctrl+Z puts back, byte for byte, the text and title that were on screen.
  async function restoreDocVersionWithUndo(entry) {
    const docId = currentDoc.id;
    const before = { content: docText(), title: $("doc-title").value.trim() || undefined, revision_source: "restore" };
    const restore = async () =>
      docShowSaved(await apiJson(`/documents/${docId}/revisions/${entry.id}/restore`, { method: "POST" }));
    await restore();
    offerUndo(
      `Restored the version from ${whenText(entry.created_at)}`,
      "Restored. Undo puts back the version you had.",
      async () => docShowSaved(await docPutFields(docId, before)),
      restore
    );
  }

  async function deleteCurrentDocument() {
    if (!currentDoc) return;
    if (!(await confirmDialog(`Delete "${currentDoc.title}"? You can undo this straight after.`))) return;
    const doomed = currentDoc;
    currentDoc = null;
    await deleteDocumentWithUndo(doomed);
    await loadDocuments();
  }

  //: The file's surface: what other files call (L-documents-117).
  Object.assign(window, { docExportName, docIsCodeFile, openDocReplace, DOC_EXPORT_STRIP, docExportClean, deleteDocumentWithUndo, renameDocumentWithUndo, archiveDocumentWithUndo, offerCreateUndo, offerCreatedDocsUndo, unlinkDocNoteWithUndo, docBookmarkWithUndo, docShowSaved, restoreDocVersionWithUndo });

  $("doc-connections").addEventListener("click", () => {
    if (!currentDoc) return;
    // Closes the ⋯ disclosure first: it is a `<details>`, so it stays open
    // behind the dialog otherwise, and it is the same width as the dialog's
    // own left edge.
    $("doc-dock-menu")?.removeAttribute("open");
    lazyScript("/js/connections.js").then(() => openConnections("documents", currentDoc.id, currentDoc.title || "This document"));
  });

  $("doc-copy-link").addEventListener("click", () => {
    $("doc-dock-menu")?.removeAttribute("open");
    if (currentDoc) copyObjectAddress("document", currentDoc.id);
  });

  $("doc-export-md").addEventListener("click", exportDocumentMarkdown);

  $("doc-export-html").addEventListener("click", exportDocumentHtml);

  $("doc-export-slides").addEventListener("click", exportDocumentHtml.slides);

  //: A diagram's picture from the open page (R10): the editor's own text, so an unsaved change is in it.
  for (const [id, how] of [["doc-export-svg", "svg"], ["doc-export-picture", "png"], ["doc-copy-picture", "picture"]]) {
    $(id).addEventListener("click", async () => {
      $("doc-dock-menu")?.removeAttribute("open");
      if (await ensureModule("diagramEmbed")) diagramModel.embed.out(how, docText(), currentDoc?.title);
    });
  }

  $("doc-export-zip").addEventListener("click", exportDocumentBundle);

  $("doc-export-docx").addEventListener("click", exportDocumentDocx);

  $("doc-export-pdf").addEventListener("click", exportDocumentPdf);

  $("doc-delete").addEventListener("click", deleteCurrentDocument);

  $("doc-attach-bookmark").addEventListener("click", attachBookmarkToDocument);

  //: **A document's headings as a new mind map** (MINDMAP_PLAN decision 35):
  //: the map side does the work (`wbMapFromDocument`, whiteboard-map.js), from
  //: the text as it stands in the editor, saved or not.
  $("doc-map-headings")?.addEventListener("click", () => {
    if (currentDoc) wbMapFromDocument(currentDoc, docText());
  });
})();
