// documents-blockref.js: copying a link to a block and revealing a block a link led to (split out of documents.js,
// DOCUMENTS_PLAN L327).
//
// **Loaded on the first use**: the toolbar's "Copy link to block" and a followed `[[Doc#^id]]` each call a stand-in
// in documents.js that fetches this file, and the real function of the same name replaces it on load. The model that
// finds and writes ids (the DOC-BLOCKREF region of documents.js) stays there: embeds read it as a document opens.
(() => {
  //: Give the block the caret is in an id, and hand back the reference a person
  //: can paste. The id is written into the document, which is the point: a block
  //: reference is a promise the text itself keeps, not an index this app holds.
  function docBlockRefAtCaret() {
    const surface = docSurface();
    if (!surface) return null;
    const text = docText();
    const made = docBlockEnsureIdEdits(text, surface.selectionStart);
    if (!made.id) return { id: null, reason: made.reason };
    if (made.edits.length) {
      docTableDispatch({ surface, text }, made.edits);
      markDocDirty();
    }
    return { id: made.id, reason: made.reason };
  }

  //: The `/` menu's "Link to this block". Copies `[[Title#^id]]`, because that
  //: is the form you paste into a note, a map node or a chat, and those three
  //: are what the plan asks a block reference to reach.
  async function docCopyBlockRef(mode = "link") {
    if (mode === "paste") return docPasteSyncedBlock();
    const synced = mode === "copy";
    const title = (currentDoc?.title || "").trim();
    if (!title) {
      toast("Give the document a title first, a block link is named by it.", "info");
      return;
    }
    const made = docBlockRefAtCaret();
    if (!made || !made.id) {
      toast("Put the caret in a paragraph first.", "info");
      return;
    }
    //: A synced block is the same reference as an embed (decision 82: the block stays in this document, the other place is a window onto it).
    const reference = `${synced ? "!" : ""}[[${title}#^${made.id}]]`;
    if (synced) prefs.set("doc-synced-clip", reference);
    //: Through the shared helper, not `navigator.clipboard`: it falls back to
    //: the copy dialog in the contexts where the API is not there at all, which
    //: is the desktop window's own case.
    await copyToClipboard(reference);
    toast(synced ? `Copied ${reference}. Paste it in another document, or use Paste synced block there.` : `Copied ${reference}`);
  }

  //: The `/` menu's "Paste synced block": the embed of the block last copied as one, put where the caret is, on a line of its own.
  function docPasteSyncedBlock() {
    const reference = prefs.get("doc-synced-clip", "");
    const surface = docSurface();
    if (!reference || !surface) {
      toast("Copy a paragraph as a synced block first (the / menu, Copy as synced block).", "info");
      return;
    }
    const text = docText();
    const at = surface.selectionStart;
    const lineStart = text.lastIndexOf("\n", at - 1) + 1;
    const lineEnd = text.indexOf("\n", at) < 0 ? text.length : text.indexOf("\n", at);
    const blank = !text.slice(lineStart, lineEnd).trim();
    docTableDispatch({ surface, text }, [{ from: at, to: at, insert: blank ? reference : `\n\n${reference}\n\n` }]);
    markDocDirty();
  }

  //: Put the caret on a block and say so. Used when a `[[Doc#^id]]` is followed:
  //: opening the document at the top and leaving the reader to find the
  //: paragraph is most of the way to not having followed the link at all.
  function docRevealBlock(blockId) {
    const found = docBlockFind(docText(), blockId);
    if (!found) {
      toast("That block is not in this document any more.", "info");
      return false;
    }
    const surface = docSurface();
    if (!surface) return false;
    surface.focus();
    //: The selection is the reveal: `setSelectionRange` on this surface already
    //: scrolls to what it selects, and selecting the block is both "here it is"
    //: and a sensible place to be left, because the next thing a reader does is
    //: copy it or edit it.
    surface.setSelectionRange(found.from, found.to);
    return true;
  }

  //: The file's whole surface: what other files and the stand-ins call (ranked row 37a).
  //: One name in the shared scope: documents.js keeps a stand-in per function
  //: (same name), which calls through this once the file is in.
  Object.assign(window, { docBlockrefPiece: { docCopyBlockRef, docRevealBlock } });
})();
