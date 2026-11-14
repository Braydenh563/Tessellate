// documents-save.js: saving a document, a conflict, and expanding a note into one.
// Moved out of documents.js whole (L335) and wrapped: only what other files call goes on `window`; nothing here runs at load.
(() => {
  let docEditSeq = 0;
  function markDocDirty() {
    docEditSeq += 1;
    // Read off the surface, so they are right even before the save lands: the
    // point of them is live feedback while writing. Scheduled rather than run
    // here, because each is a pass over the whole document, see
    // `scheduleDocFacts`.
    scheduleDocFacts();
    // No document yet? Typing makes one, then this save proceeds normally.
    if (!currentDoc) {
      //: A create that failed is not asked again on every key: the words are kept
      //: and one retry runs after a pause (audit 1028 D3).
      if (docSaveQueue.newRetry) return keepDocEditLocally();
      const retryMs = 8000;
      ensureDocumentExists().then(() => {
        forgetDocEditLocally("new");
        markDocDirty();
      }, (error) => {
        $("doc-saved").textContent = "Not saved";
        $("doc-status").classList.add("error");
        //: The retry below is silent otherwise: say that one is coming.
        $("doc-status").textContent = `${String(error.message).replace(/[.\s]+$/, "")}. It will try again in ${retryMs / 1000} seconds.`;
        keepDocEditLocally();
        docSaveQueue.newRetry = setTimeout(() => {
          docSaveQueue.newRetry = null;
          if (!currentDoc && (docText().trim() || $("doc-title").value.trim())) markDocDirty();
        }, retryMs);
      });
      return;
    }
    docDirty = true;
    if (docConflictPending?.id === currentDoc.id) return;
    docSetStatusText($("doc-saved"), "Unsaved…");
    clearTimeout(docSaveTimer);
    // Autosave, but not on every keystroke, a pause is the natural moment.
    docSaveTimer = setTimeout(() => saveDocument({ silent: true }), 1200);
  }
  let docConflictOpen = false;
  const docSaveQueue = { inFlight: null, again: null, newRetry: null, newOffered: false };
  async function saveDocument({ silent = false } = {}) {
    if (docConflictPending && docConflictPending.id !== currentDoc?.id) docConflictPending = null;
    if (!currentDoc || docConflictOpen) return;
    //: A save asked for by hand is the answer the banner waits for: it opens the
    //: dialog. The autosave stays quiet.
    if (docConflictPending) {
      if (!silent) await docResolveConflict(docConflictPending.current, docText(), false, false);
      return;
    }
    if (docSaveQueue.inFlight) {
      docSaveQueue.again = { silent: silent && (docSaveQueue.again ? docSaveQueue.again.silent : true) };
      await docSaveQueue.inFlight;
      return;
    }
    let release;
    docSaveQueue.inFlight = new Promise((resolve) => (release = resolve));
    try {
      await docSaveOnce(silent);
    } finally {
      docSaveQueue.inFlight = null;
      const again = docSaveQueue.again;
      docSaveQueue.again = null;
      if (again) await saveDocument(again).catch(() => {});
      release();
    }
  }
  function docFillBlankTitle() {
    const field = $("doc-title");
    if (!currentDoc || field.value.trim()) return false;
    field.value = /^untitled document \d+$/i.test(currentDoc.title || "") ? currentDoc.title : docNextName();
    return true;
  }
  let docSaveFailedSaid = false;
  async function docSaveOnce(silent) {
    clearTimeout(docSaveTimer);
    const savingId = currentDoc.id;
    const seqAtStart = docEditSeq;
    //: A title emptied while typing is not written: the autosave keeps the
    //: stored one, and leaving the field (or saving by hand) names it (D17).
    if (!silent) docFillBlankTitle();
    const title = $("doc-title").value.trim() || currentDoc.title || docNextName();
    const content = docText();
    try {
      const saved = await apiJson(`/documents/${currentDoc.id}`, {
        method: "PUT",
        // `file_type` every time, not only when it changed: the server treats
        // null as "leave it alone", so sending the current value is harmless,
        // and omitting it would make a type change depend on which save
        // happened to run next.
        //: `base_hash`: the hash of the text this editor last had from the
        //: server (`currentDoc` is replaced by every save's answer), so a
        //: save over text another window has since saved is refused with 409
        //: rather than overwriting it (WORLD_CLASS_PLAN 22.1 item 5).
        body: JSON.stringify({ title, content, file_type: currentDoc.file_type || "md", base_hash: currentDoc.content_hash, base_threads_hash: currentDoc.threads_hash, threads: renderDocComments.threads() }),
      });
      //: A name another document already has is said once per document and name, on the
      //: first save under it (a new document's first autosave, or a rename), and left as
      //: typed (audit 1028 U38): a suffix added unasked would change what the person wrote.
      const alike = String(saved.title || "").trim().toLowerCase();
      const said = (docSaveOnce.said ||= new Set());
      const named = docsMadeThisSession.has(saved.id) || (currentDoc?.id === saved.id && currentDoc.title !== saved.title);
      if (named && alike && !said.has(`${saved.id}:${alike}`) && docs.some((d) => d.id !== saved.id && String(d.title || "").trim().toLowerCase() === alike)) {
        said.add(`${saved.id}:${alike}`);
        toast(`Another document is called “${saved.title.trim()}” too. Rename one if you want to tell them apart.`);
      }
      docs = docs.map((d) => (d.id === saved.id ? { ...d, ...saved } : d));
      renderDocList();
      if (currentDoc?.id !== savingId) return;
      currentDoc = saved;
      //: Typed during the request: still dirty (D2).
      if ((docDirty = docEditSeq !== seqAtStart)) {
        keepDocEditLocally();
        return docSetStatusText($("doc-saved"), "Unsaved…");
      }
      forgetDocEditLocally(saved.id);
      docSaveFailedSaid = false;
      $("doc-saved").textContent = "Saved";
      if (!silent) toast("Document saved.");
      //: An open preview shows what was saved (D6).
      docRunAfterSave();
      //: A ```query block lists what matches, and the save may have changed it (documents-base.js).
      document.dispatchEvent(new CustomEvent("doc-saved"));
    } catch (error) {
      if (isEditConflict(error)) {
        await docResolveConflict(error.detail.current, content, silent);
        return;
      }
      $("doc-saved").textContent = "Not saved";
      keepDocEditLocally();
      $("doc-status").classList.add("error");
      $("doc-status").textContent = error.message;
      //: Said once per run of failures, with a way to try again (audit 1028
      //: D34): the status bar's two words were the only sign, and autosave
      //: retrying every pause must not stack a toast each time.
      if (!docSaveFailedSaid) {
        docSaveFailedSaid = true;
        toast(voiceLine("failed", { what: "save the document", why: `${String(error.message || "no answer").replace(/\.$/, "")}. The text is kept on this device.` }), true, {
          action: ["Try again", () => saveDocument({ silent: false })],
        });
      }
    }
  }
  async function docResolveConflict(current, mine, silent, fromSave = true) {
    $("doc-saved").textContent = "Not saved";
    if (silent) {
      docConflictPending = { id: current.id, current };
      keepDocEditLocally();
      const saved = $("doc-saved");
      saved.textContent = "Changed in another window. ";
      saved.append(smallButton("Resolve", "Compare the two versions, keep yours or take the other window's", () => docResolveConflict(current, docText(), false, false)));
      return;
    }
    docConflictPending = null;
    docConflictOpen = true;
    let answer = null;
    try {
      answer = await editConflictPrompt({ noun: "document", mine, theirs: current.content || "" });
    } finally {
      docConflictOpen = false;
    }
    if (!currentDoc || currentDoc.id !== current.id) return;
    if (answer === "mine") {
      currentDoc = { ...currentDoc, content_hash: current.content_hash, threads_hash: current.threads_hash };
      //: Directly, not through saveDocument, when this runs inside the save in
      //: flight; from the banner there is none, so the queue is the way in.
      if (fromSave) await docSaveOnce(silent);
      else await saveDocument({ silent: false });
    } else if (answer === "theirs") {
      currentDoc = { ...currentDoc, ...current };
      //: Their comment threads too: the panel's copy is the one the next save sends.
      renderDocComments.reload();
      //: The title box too (audit 1028 D10): left on the old title, the next
      //: save sent it back over the one just taken.
      $("doc-title").value = current.title || "";
      docSurface().text = current.content || "";
      renderDocComments();
      renderDocPreview();
      docDirty = false;
      $("doc-saved").textContent = "Saved";
      docs = docs.map((d) => (d.id === current.id ? { ...d, ...current } : d));
      renderDocList();
    }
  }

  //: The file's surface: what other files call (L335).
  Object.assign(window, { markDocDirty, docSaveQueue, saveDocument, docFillBlankTitle });
})();
