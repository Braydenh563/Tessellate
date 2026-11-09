// documents-ai.js: the AI edit panel (split out of documents.js, audit 1031
// DC13).
//
// What is here: the panel behind the dock's AI button: the verb, the
// instruction, the request, the proposal's diff with a box per change, Replace
// with this, and the edit log. What stayed in documents.js: the controller the
// cancel button aborts (`docAiController`), `closeDocAiPanel` (the lock screen
// calls it, so it cannot wait for a fetch), the diff drawing the history
// shares (`docRenderDiff`), and the buttons' wiring, which goes through
// `docAiLazy`.
//
// **Loaded on the first press** of any of the panel's controls, the way
// documents-word.js is. Its top level is declarations and the one listener on
// the result box, which does nothing until the panel has been opened.

// --- AI editing ---
// Always a proposal. Writing straight into the document would be the most
// destructive thing in the app. Three verbs (reskinned from a single
// rewrite action into a small general assistant, asked for directly):
// "edit" rewrites the target, "write" inserts a new passage without
// touching what's there, "remove" deletes on request. All three go through
// the same /ai-edit endpoint (routes_documents.py) with a `verb` field.
(() => {
  function docAiVerb() {
    return $("doc-ai-panel").querySelector('input[name="doc-ai-verb"]:checked')?.value || "edit";
  }

  //: **The result area is shown by the result arriving, and by nothing else**
  //: (INBOX 158). One function rather than a `classList` call at each of the four
  //: places that change the answer's state (opening, running, switching verb,
  //: clearing), because the bug this replaces was not a missing class, it was four
  //: places disagreeing about whether there was an answer: an empty 309px textarea
  //: under a label describing text that was not there, over a Replace button for
  //: nothing, in 43% of the dialog.
  function showDocAiResult(text) {
    const block = $("doc-ai-result-block");
    const result = $("doc-ai-result");
    if (!block || !result) return;
    result.value = text || "";
    //: A "remove" whose answer is the passage with nothing left in it is still an
    //: answer, and `acceptDocAiEdit` already treats that case as valid, so the
    //: block is shown for an empty string and hidden only for nothing at all.
    block.classList.toggle("hidden", text === null || text === undefined);
    stagePrimary("doc-ai-run", "doc-ai-accept", !block.classList.contains("hidden"));
    setDocAiProposal(text === null || text === undefined ? null : result.value);
  }

  //: **The proposal, as a change rather than as a wall of text**
  //: (DOCUMENTS_PLAN Phase 5 item 3). The panel used to hand back the model's
  //: whole answer in a textarea: for "tighten this" over a 900-word document
  //: that is nine hundred words to read to find the four it touched, and the
  //: only two answers available were all of it or none of it.
  //:
  //: The state here is two things and the textarea is the third: the *target*
  //: (what the model was asked to change, the selection or the document), the
  //: model's answer as a list of changes against it, and the set of changes the
  //: reader has skipped. The textarea always holds the text that pressing accept
  //: would apply, so the diff explains the textarea rather than competing with
  //: it, and `acceptDocAiEdit` needs no knowledge of any of this: it still reads
  //: the textarea, which is what it has always done.
  let docAiOps = [];
  let docAiHunks = [];
  let docAiSkips = new Set();
  let docAiTarget = null;
  let docAiDiffTimer = null;

  //: "Write" has no target: it inserts new text and changes nothing, so a diff
  //: of it is the whole answer marked as added, which says less than the answer
  //: itself. The block is hidden for that verb rather than drawn empty.
  function docAiDiffTarget() {
    if (docAiVerb() === "write") return null;
    const selection = $("doc-ai-panel").dataset.selection || "";
    return selection || docSurface().text;
  }

  function setDocAiProposal(text) {
    docAiTarget = text === null || text === undefined ? null : docAiDiffTarget();
    if (docAiTarget === null) {
      docAiOps = [];
      docAiHunks = [];
    } else {
      docAiOps = docDiffLines(docAiTarget, text);
      docAiHunks = docDiffHunks(docAiOps);
    }
    docAiSkips = new Set();
    renderDocAiDiff();
  }

  function renderDocAiDiff() {
    const block = $("doc-ai-diff-block");
    const view = $("doc-ai-diff");
    const head = $("doc-ai-diff-head");
    if (!block || !view || !head) return;
    if (!docAiOps.length) {
      block.classList.add("hidden");
      view.replaceChildren();
      return;
    }
    block.classList.remove("hidden");
    const stat = docDiffStat(docAiOps);
    const count = docAiHunks.length;
    head.textContent = !count
      ? "No change: the model gave back the same text."
      : count === 1
        ? `One change, +${stat.added} −${stat.removed} lines. Skip it to leave the text as it is.`
        : `${nounCount(count, "change")}, +${stat.added} −${stat.removed} lines. Skip any you don't want.`;
    //: Kept across a redraw: toggling the fourth change of eight must not take
    //: the reader back to the first.
    const scroll = view.scrollTop;
    docRenderDiff(view, docAiOps, {
      hunks: docAiHunks,
      skipped: docAiSkips,
      onToggleHunk: toggleDocAiHunk,
      emptyText: "No change: the model gave back the same text.",
    });
    view.scrollTop = scroll;
  }

  function toggleDocAiHunk(index) {
    if (docAiSkips.has(index)) docAiSkips.delete(index);
    else docAiSkips.add(index);
    //: Setting `.value` from script fires no `input` event, which is what keeps
    //: this and the listener below from chasing each other: a toggle writes the
    //: textarea, a person typing rebuilds the diff, and neither triggers the
    //: other.
    $("doc-ai-result").value = docDiffApply(docAiOps, docAiHunks, docAiSkips);
    renderDocAiDiff();
  }

  //: Edited by hand, the answer becomes the proposal: the diff is rebuilt
  //: against the same target and every change starts kept again, because a skip
  //: is a statement about a change that may no longer exist.
  function docAiResultEdited() {
    if (docAiTarget === null) return;
    docAiOps = docDiffLines(docAiTarget, $("doc-ai-result").value);
    docAiHunks = docDiffHunks(docAiOps);
    docAiSkips = new Set();
    renderDocAiDiff();
  }

  $("doc-ai-result").addEventListener("input", () => {
    if (docAiDiffTimer) clearTimeout(docAiDiffTimer);
    docAiDiffTimer = setTimeout(docAiResultEdited, 300);
  });

  // The run button, the instruction placeholder, and the scope hint all read
  // differently per verb: kept in one place so switching verbs updates all
  // three together rather than three separate change listeners drifting.
  function syncDocAiPanel() {
    const verb = docAiVerb();
    const selection = ($("doc-ai-panel").dataset.selection || "").trim();
    const selectionWords = wordCount(selection);

    const runLabel = { edit: "Suggest an edit", write: "Write it", remove: "Remove it" }[verb];
    setLabel($("doc-ai-run"), `ph:sparkle ${runLabel}`);

    $("doc-ai-instruction").placeholder =
      verb === "write"
        ? "e.g. “add a conclusion”, “write an intro paragraph”"
        : verb === "remove"
          ? selection
            ? "Optional: leave blank to remove the selection as-is"
            : "e.g. “remove the paragraph about pricing”"
          : "e.g. “tighten this”, “make it more formal”, “add a conclusion”";

    if (verb === "write") {
      $("doc-ai-scope").textContent = selection
        ? `Inserting new text directly after the ${selectionWords} selected word(s).`
        : "Inserting new text at the end of the document.";
    } else if (verb === "remove") {
      $("doc-ai-scope").textContent = selection
        ? `Removing the ${selectionWords} selected word(s): or say what to remove from within them.`
        : "Say what to remove from the whole document.";
    } else {
      $("doc-ai-scope").textContent = selection
        ? `Rewriting the ${selectionWords} selected word(s).`
        : "Rewriting the whole document. Select some text first to work on just that.";
    }

    const acceptLabel = { edit: "Replace with this", write: "Insert this", remove: "Remove it" }[verb];
    $("doc-ai-accept").textContent = acceptLabel;
  }

  //: Switching verb throws the proposal away, and that is a fix rather than a
  //: tidy-up: the panel used to keep it, so a passage the model rewrote for "Edit"
  //: stayed on screen with "Remove it" under it, and pressing that button deleted
  //: the selection and replaced it with the rewrite. The status line says so,
  //: because a proposal vanishing with no explanation reads as a failure.
  function docAiVerbChanged() {
    const had = !$("doc-ai-result-block").classList.contains("hidden");
    showDocAiResult(null);
    syncDocAiPanel();
    if (had) {
      const status = $("doc-ai-status");
      status.classList.remove("error");
      status.textContent = "Ask again: the last suggestion was for a different job.";
    }
  }

  function openDocAiPanel() {
    if (!currentDoc) return;
    const box = docSurface();
    const { from, to } = box.selection();
    $("doc-ai-panel").dataset.selection = box.text.slice(from, to);
    // Always opens back on "Edit", the panel's original, still-default
    // behaviour: rather than remembering whatever verb was last used, so a
    // stray "Remove it" click a moment after opening isn't primed by the
    // previous document's choice.
    const editRadio = $("doc-ai-panel").querySelector('input[name="doc-ai-verb"][value="edit"]');
    if (editRadio) editRadio.checked = true;
    showDocAiResult(null);
    $("doc-ai-status").textContent = "";
    syncDocAiPanel();
    $("doc-ai-panel").classList.remove("hidden");
    $("doc-ai-instruction").focus();
  }

  async function runDocAiEdit() {
    const verb = docAiVerb();
    const instruction = $("doc-ai-instruction").value.trim();
    const selection = $("doc-ai-panel").dataset.selection || "";
    const status = $("doc-ai-status");
    // Mirrors routes_documents.ai_edit's own validation exactly, so a bad
    // request never reaches the network at all: "write" always needs words,
    // "remove" can skip them only when a selection already says what to
    // remove, "edit" is the original required-instruction behaviour.
    if (verb === "write" && !instruction) {
      status.classList.add("error");
      status.textContent = "Say what to write.";
      return;
    }
    if (verb === "remove" && !instruction && !selection.trim()) {
      status.classList.add("error");
      status.textContent = "Say what to remove, or select it first.";
      return;
    }
    if (verb === "edit" && !instruction) {
      status.classList.add("error");
      status.textContent = "Say what you'd like changed.";
      return;
    }
    status.classList.remove("error");
    //: The same first phase the chat surfaces open with (INBOX 649); this call is
    //: one request with no stream, so it has no later phase to move to.
    setLabel(status, `ph:spin ${progressPhaseText("reaching")}`);
    docAiController = new AbortController();
    $("doc-ai-run").classList.add("hidden");
    $("doc-ai-cancel-run").classList.remove("hidden");
    try {
      const body = await apiJson(`/documents/${currentDoc.id}/ai-edit`, {
        method: "POST",
        signal: docAiController.signal,
        body: JSON.stringify({ instruction, selection, verb }),
      });
      showDocAiResult(body.revised);
      status.textContent = body.message || "Read it over, then accept or cancel.";
      if (body.message) status.classList.add("error");
    } catch (error) {
      if (error.name === "AbortError") {
        status.textContent = "Stopped. The document is untouched.";
      } else {
        status.classList.add("error");
        status.textContent = error.message;
      }
    } finally {
      docAiController = null;
      $("doc-ai-run").classList.remove("hidden");
      $("doc-ai-cancel-run").classList.add("hidden");
    }
  }

  // The undo/redo half of "allow edits made by the AI to be undone or
  // altered before and after they are set" (asked for directly): before
  // acceptance, the result textarea above already covers "altered" (edit
  // the AI's suggestion, then accept whatever's left). This is "undone...
  // after": pushed onto the app's existing global undo stack (an immediate
  // Ctrl+Z / status-bar Undo, session-only) alongside a durable per-document
  // changelog entry (ai-edit-log, survives reload, lists every edit with its
  // own Revert): see the dialog's own comment in index.html for why both.
  function pushDocAiUndo(docId, label, beforeContent, afterContent) {
    const applyContent = async (content) => {
      const title = currentDoc && currentDoc.id === docId ? currentDoc.title : undefined;
      const saved = await apiJson(`/documents/${docId}`, {
        method: "PUT",
        body: JSON.stringify({ content, ...(title !== undefined ? { title } : {}) }),
      });
      if (currentDoc && currentDoc.id === docId) {
        currentDoc = saved;
        docSurface().text = content;
        renderDocPreview();
        docDirty = false;
        $("doc-saved").textContent = "Saved";
      }
      docs = docs.map((d) => (d.id === docId ? { ...d, ...saved } : d));
      renderDocList();
    };
    pushUndo(
      label,
      () => applyContent(beforeContent),
      () => applyContent(afterContent)
    );
  }

  async function recordDocAiEditLog(docId, verb, instruction, selection, beforeContent, afterContent) {
    try {
      await apiJson(`/documents/${docId}/ai-edit-log`, {
        method: "POST",
        body: JSON.stringify({
          verb,
          instruction,
          selection,
          before_content: beforeContent,
          after_content: afterContent,
        }),
        silent: true,
      });
    } catch {
      // Best-effort: the changelog is a record of an edit that has already
      // happened (and is already undoable via the global stack above), a
      // network hiccup writing the log entry must not read as the edit
      // itself having failed.
    }
  }

  //: **An answer far shorter than what it replaces is asked about first** (1031
  //: DC6: two characters replaced 1,272 in one click, the diff the only sign).
  //: Only a rewrite or a removal over a target of 200 characters or more, and
  //: only under a fifth of its length; a removal's own gap is not a short answer.
  const DOC_AI_SHORT_SHARE = 0.2;
  const DOC_AI_SHORT_FROM = 200;
  function docAiAnswerIsShort(verb, target, revised) {
    if (verb === "write" || target.length < DOC_AI_SHORT_FROM) return false;
    return revised.trim().length < target.length * DOC_AI_SHORT_SHARE;
  }

  async function acceptDocAiEdit() {
    const revised = $("doc-ai-result").value;
    if (!revised.trim() && docAiVerb() !== "remove") return;
    const verb = docAiVerb();
    const instruction = $("doc-ai-instruction").value.trim();
    const selection = $("doc-ai-panel").dataset.selection || "";
    const box = docSurface();
    if (docAiAnswerIsShort(verb, selection || box.text, revised)) {
      const ask = `The model sent much less than the text (${nounCount(revised.trim().length, "character")} for ${nounCount((selection || box.text).length, "character")}). Replace anyway?`;
      if (!(await confirmDialog(ask, { confirmLabel: "Replace anyway" }))) return;
    }
    const beforeContent = box.text;
    const docId = currentDoc.id;

    if (verb === "write") {
      // Inserts rather than replaces, the selection (if any) is only the
      // anchor point, and stays exactly as it was.
      if (selection) {
        const at = box.text.indexOf(selection);
        const insertAt = at === -1 ? box.text.length : at + selection.length;
        const before = box.text.slice(0, insertAt);
        const after = box.text.slice(insertAt);
        const glue = before && !before.endsWith("\n\n") ? (before.endsWith("\n") ? "\n" : "\n\n") : "";
        box.text = before + glue + revised + after;
      } else {
        const glue = box.text && !box.text.endsWith("\n\n") ? (box.text.endsWith("\n") ? "\n" : "\n\n") : "";
        box.text = box.text + glue + revised;
      }
    } else if (selection) {
      // "edit" and "remove" both replace the target with what the model
      // returned: for "remove" that's the same text with the requested
      // part gone, so no separate apply logic is needed.
      const at = box.text.indexOf(selection);
      box.text =
        at === -1
          ? box.text
          : box.text.slice(0, at) + revised + box.text.slice(at + selection.length);
    } else {
      box.text = revised;
    }

    const afterContent = box.text;
    closeDocAiPanel();
    markDocDirty();
    renderDocPreview();
    saveDocument({ silent: true });

    const label = { edit: "AI edit", write: "AI write", remove: "AI remove" }[verb];
    pushDocAiUndo(
      docId,
      instruction ? `${label}: “${instruction.length > 40 ? instruction.slice(0, 39) + "…" : instruction}”` : label,
      beforeContent,
      afterContent
    );
    recordDocAiEditLog(docId, verb, instruction, selection, beforeContent, afterContent);

    toast(
      verb === "write"
        ? "Inserted Atlas's text."
        : verb === "remove"
          ? "Removed."
          : "Applied Atlas's edit."
    );
  }

  //: The file's whole surface: what other files and the stand-ins call (ranked row 37a).
  Object.assign(window, { acceptDocAiEdit, docAiVerbChanged, openDocAiPanel, runDocAiEdit });
})();
