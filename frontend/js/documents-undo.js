// documents-undo.js: undo and redo through the editor's history, and what Ctrl+Z reaches.
// Moved out of documents.js whole (L-documents-117) and wrapped: only what other files call goes on `window`.
(() => {
  // Undo, and where it comes from now (PLAN.md §2 D3, DOCUMENTS_PLAN Phase 2)
  // =============================================================================
  //
  // **What used to be here.** A stack of whole-document snapshots, 200 deep,
  // coalesced on a 500 ms window, fed from `markDocDirty` and applied as a
  // minimal range edit. It existed for one reason, and the reason was the Live
  // view: a `<textarea>` keeps a native undo history, but that history belongs
  // to *one element*, and Live gave every paragraph its own textarea, created
  // when you clicked into it and destroyed when you left. Type in Live, switch
  // to Source, press Ctrl+Z, and the box you were now in had never seen the
  // edit. That is PLAN D3's own acceptance line, and it was broken.
  //
  // **Why it goes.** Phase 2 leaves exactly one editing surface in every view.
  // Where the engine is mounted, CodeMirror keeps a real history over
  // transactions, which is strictly better than snapshots: it knows what
  // changed rather than inferring it, it survives a view switch because there
  // is no second box to switch to, and one Ctrl+Z undoes a Replace all as one
  // thing. Where the engine is not mounted the surface is a single textarea
  // with its own native history, and `docReplaceRange` already keeps the
  // toolbar's edits inside it. Neither case has the problem the stack was
  // written for, and keeping two histories fed by the same edits is the shape
  // where Ctrl+Z walks one of them while the editor shows the other.
  //
  // What survives is the diff, because the surface adapter uses it to turn "the
  // document is now this string" into the one edit that was actually made.

  //: The smallest range that differs, as `[from, to, text]` against `before`.
  //: Common prefix and common suffix, enough to turn a whole rebuilt document
  //: into the one insertion or deletion a person made, which is what keeps a
  //: caller that hands over a full string from costing the length of the
  //: document and from collapsing into a single undoable rewrite.
  function docUndoDiffRange(before, after) {
    let start = 0;
    const shortest = Math.min(before.length, after.length);
    while (start < shortest && before[start] === after[start]) start += 1;
    let tail = 0;
    while (
      tail < shortest - start &&
      before[before.length - 1 - tail] === after[after.length - 1 - tail]
    ) {
      tail += 1;
    }
    return [start, before.length - tail, after.slice(start, after.length - tail)];
  }

  //: **A scripted edit is its own undo step.** Called at the top of every one
  //: (a toolbar button, an indent, a comment toggle), *before* it runs. On the
  //: engine it arms an `isolateHistory` annotation that the next transaction
  //: carries, so a Bold pressed half a second after typing cannot be folded
  //: into the sentence it was applied to; on the fallback textarea the
  //: browser's own history already breaks on a scripted `insertText`.
  let docCmBreakNext = false;

  function docUndoBreak() {
    docCmBreakNext = true;
  }

  //: Consumed by the adapter's own dispatches. Returns `undefined` rather than
  //: an empty array when nothing is armed, because that is what CodeMirror
  //: expects for "no annotations".
  function docCmIsolate() {
    if (!docCmBreakNext) return undefined;
    docCmBreakNext = false;
    const CM = window.CM6;
    return CM ? CM.commands.isolateHistory.of("before") : undefined;
  }

  function docUndo() {
    const CM = window.CM6;
    //: C32: these histories hold no labels, so the notice names the place; "info" shows even when muted.
    if (docCmView && CM) return CM.commands.undo(docCmView) && (toast("Undone: last change on this document", "info"), true);
    //: The fallback is one textarea, so the browser's own history is the right
    //: one and a second would only disagree with Ctrl+Z: which is what
    //: `applyMarkdown`'s own comment said before Live ever existed.
    docSurface()?.focus();
    return document.execCommand("undo");
  }

  //: **When each of this document's own steps was made**, by history depth and
  //: per document (its history is kept per document for the session), so the
  //: status bar can tell whether Ctrl+Z belongs to the editor or to an act on
  //: the app's stack (`appStackIsNewer`, status.js). A scripted write outside
  //: the history (a restored version) is not a step and is not stamped.
  const docHistoryTimes = new Map();
  const docHistoryUndone = new Map();

  function docHistoryStamp(update) {
    const CM = window.CM6;
    if (!CM || !currentDoc) return;
    const id = currentDoc.id;
    if (update.transactions.some((tr) => tr.isUserEvent("undo"))) {
      docHistoryUndone.set(id, Date.now());
      return;
    }
    if (update.transactions.some((tr) => tr.isUserEvent("redo"))) return;
    if (update.transactions.every((tr) => tr.annotation(CM.state.Transaction.addToHistory) === false)) return;
    const times = docHistoryTimes.get(id) || [];
    times[CM.commands.undoDepth(update.state)] = Date.now();
    docHistoryTimes.set(id, times);
  }

  window.docUndoAt = () => {
    if (!docCmView || !window.CM6 || !currentDoc) return 0;
    const depth = window.CM6.commands.undoDepth(docCmView.state);
    return depth ? (docHistoryTimes.get(currentDoc.id) || [])[depth] || 0 : 0;
  };
  window.docRedoAt = () => {
    if (!docCmView || !window.CM6 || !currentDoc) return 0;
    return window.CM6.commands.redoDepth(docCmView.state) ? docHistoryUndone.get(currentDoc.id) || 0 : 0;
  };

  //: For the status bar's pair (`surfaceHistory`): this document's own steps.
  window.docCanUndo = () => (docCmView && window.CM6 ? window.CM6.commands.undoDepth(docCmView.state) > 0 : Boolean(currentDoc));
  window.docCanRedo = () => (docCmView && window.CM6 ? window.CM6.commands.redoDepth(docCmView.state) > 0 : Boolean(currentDoc));


  // =============================================================================

  //: The file's surface: what other files call (L-documents-117).
  Object.assign(window, { docUndoDiffRange, docUndoBreak, docCmIsolate, docUndo, docHistoryStamp });
})();
