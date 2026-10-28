// -----------------------------------------------------------------------------
// The code editor's VS Code pieces, Brief 42 (DOCUMENTS_PLAN 21 and 25)
// -----------------------------------------------------------------------------
//
// The owner, 2026-10-10: "it leaves a lot to be desired and just sucks
// compared to vs code and other IDEs. make sure to make full use of the
// vendored repositories and libraries". Measured first (scratchpad/ui-sweeps/
// docs42.js): no minimap, no fold all or problems panel in the palette, no
// comparison with a saved version in the editor, the active line's number
// drawn at weight 400 with no border. This file is those pieces, on the
// packages the bundle gained for them (`CM6.merge`, `CM6.showMinimap`).
//
// Its own file, loaded after documents.js in the Library bundle, so the
// editor's size ratchets do not move. documents-code.js mounts the one
// compartment below from `docCompletionExtras`, a call made at open time,
// never at load, so the order of the files is not load-bearing.

//: One compartment for everything here, reused across documents: the
//: minimap when the preference is on, the merge view while comparing.
//: `compare` is `{ docId, label, text }` for the version being compared.
//: `split` is the second editor while the split is on, `sync` the annotation
//: its edits carry, `chordAt` when Ctrl+K was pressed in the editor and `chordTimer` its wait.
const docIde = { slot: null, compare: null, split: null, splitDoc: null, sync: null, chordAt: 0, chordTimer: 0, keysReturn: null };

function docIdeExtensions(CM, type) {
  if (!docIde.slot) docIde.slot = new CM.state.Compartment();
  //: A comparison belongs to the document it was opened on; opening
  //: another one ends it rather than diffing the new text against it.
  if (docIde.compare && docIde.compare.docId !== (currentDoc && currentDoc.id)) docIde.compare = null;
  return docIde.slot.of(docIdeSlot(CM, type));
}

function docIdeSlot(CM, type) {
  const out = [
    //: CodeMirror owns the editor's `class` attribute and rewrites it on
    //: every focus change, so `syncDocFileType`'s `classList.toggle` was
    //: gone the first time the editor took focus (measured: the class
    //: present at open, absent once focused). Declared here it is kept.
    CM.view.EditorView.editorAttributes.of({ class: "doc-content-code" }),
    //: The panel's chords (Ctrl+J, Ctrl+Shift+M Problems, Ctrl+Shift+Y the
    //: Console), the palette, the split: before the keymaps, and stopped
    //: here, because the app's registry gives Ctrl+Shift+P and Ctrl+Shift+Y
    //: to other things and would answer them too (`docIdeKeydown`).
    CM.state.Prec.highest(CM.view.EditorView.domEventHandlers({ keydown: (event) => docIdeKeydown(event) })),
    //: The split's other half follows this one's edits (`docIdeToggleSplit`).
    CM.view.EditorView.updateListener.of((update) => docIdeSplitFollow(update)),
  ];
  if (docToolPref("codeMinimap", false)) {
    out.push(
      CM.showMinimap.compute(["doc"], () => ({
        create: () => {
          const dom = document.createElement("div");
          dom.className = "doc-minimap";
          return { dom };
        },
        //: Blocks, not characters: a block per word is legible at this
        //: scale and costs a tenth of the paint (the package's own advice).
        displayText: "blocks",
        showOverlay: "always",
      }))
    );
  }
  if (docIde.compare) {
    out.push(
      CM.merge.unifiedMergeView({
        original: docIde.compare.text,
        mergeControls: true,
        gutter: true,
        highlightChanges: true,
        syntaxHighlightDeletions: true,
      })
    );
  }
  return out;
}

function docIdeReconfigure() {
  const CM = window.CM6;
  if (!docCmView || !CM || !docIde.slot) return;
  docCmView.dispatch({ effects: docIde.slot.reconfigure(docIdeSlot(CM, docFileType())) });
}

//: The hunks between a saved version and the editor, as the merge view
//: draws them. Pure, so `tests/test_code_ide_b42.py` runs it in node.
function docIdeChunks(CM, original, state) {
  return CM.merge.Chunk.build(CM.state.Text.of(original.split("\n")), state.doc);
}

//: The transaction that puts one hunk back the way the version had it,
//: and nothing else: the merge view's own Reject, reachable from the
//: palette for the hunk at the caret. Its line-break rule is the
//: package's: a hunk ends on the line after its last changed line.
function docIdeRevertSpec(CM, original, state, chunk) {
  const orig = CM.state.Text.of(original.split("\n"));
  let insert = orig.sliceString(chunk.fromA, Math.max(chunk.fromA, chunk.toA - 1));
  if (chunk.fromA !== chunk.toA && chunk.toB <= state.doc.length) insert += state.lineBreak;
  return { changes: { from: chunk.fromB, to: Math.min(state.doc.length, chunk.toB), insert } };
}

function docIdeCodeView() {
  return docCmView && currentDoc && !docFileType().previewable ? docCmView : null;
}

function docIdeFoldAll(unfold) {
  const view = docIdeCodeView();
  const CM = window.CM6;
  if (!view || !CM) return false;
  return unfold ? CM.language.unfoldAll(view) : CM.language.foldAll(view);
}

function docIdeToggleMinimap(on) {
  if (docFileType().previewable) return false;
  const next = on === undefined ? !docToolPref("codeMinimap", false) : Boolean(on);
  docSaveToolPref("codeMinimap", next);
  const box = $("doc-minimap");
  if (box) box.checked = next;
  docIdeReconfigure();
  return true;
}

//: Compare with a saved version: the history's list, newest first, as a
//: menu at the caret; picking one opens the merge view against it.
async function docIdeCompareMenu() {
  const view = docIdeCodeView();
  if (!view) return false;
  let entries = [];
  try {
    entries = await apiJson(`/documents/${currentDoc.id}/revisions`);
  } catch (error) {
    toast(`Could not read this document's history: ${error.message}`, true);
    return false;
  }
  const items = entries.length
    ? entries.slice(0, 30).map((entry) => ({
      label: `ph:clock-counter-clockwise ${formatDocHistoryWhen(entry.created_at)}`,
      title: `${nounCount(entry.words, "word")} changed`,
      run: () => docIdeCompareWith(entry.id, formatDocHistoryWhen(entry.created_at)),
    }))
    : [{ label: "ph:info No saved versions yet", disabled: true, run: () => {} }];
  const at = view.coordsAtPos(view.state.selection.main.head) || view.contentDOM.getBoundingClientRect();
  openMenuAtPoint(items, "Compare with a saved version", at.left, at.bottom);
  return true;
}

function formatDocHistoryWhen(iso) {
  const when = new Date(iso);
  return Number.isNaN(when.getTime()) ? String(iso) : whenText(when);
}

async function docIdeCompareWith(revisionId, label) {
  if (!docIdeCodeView()) return false;
  const docId = currentDoc.id;
  const full = await apiJson(`/documents/${docId}/revisions/${revisionId}`);
  if (!currentDoc || currentDoc.id !== docId) return false;
  docIde.compare = { docId, label, text: String(full.content ?? "") };
  docIdeReconfigure();
  toast(`Comparing with the version from ${label}. Reject puts a hunk back; Stop comparing ends it.`);
  return true;
}

function docIdeStopCompare() {
  if (!docIde.compare) return false;
  docIde.compare = null;
  docIdeReconfigure();
  return true;
}

//: The hunk at the caret, put back as the compared version had it.
function docIdeRevertAtCaret() {
  const view = docIdeCodeView();
  const CM = window.CM6;
  if (!view || !CM || !docIde.compare) return false;
  const head = view.state.selection.main.head;
  const chunk = docIdeChunks(CM, docIde.compare.text, view.state)
    .find((c) => head >= c.fromB && head <= Math.max(c.fromB, c.toB));
  if (!chunk) {
    toast("The caret is not in a changed hunk.");
    return false;
  }
  view.dispatch(docIdeRevertSpec(CM, docIde.compare.text, view.state, chunk));
  return true;
}

$("doc-minimap")?.addEventListener("change", (event) => docIdeToggleMinimap(event.target.checked));
if ($("doc-minimap")) $("doc-minimap").checked = docToolPref("codeMinimap", false);

// --- INBOX 736: the output panel's height ------------------------------------------
//
// The owner, 2026-10-06: "I cant adjust the height of this output bottom
// panel". The sidebars' grip (`.sidebar-resize`: the role, the keys, the
// double click) laid along the panel's top edge, the height kept per
// document because a file that prints three lines and one that renders a
// page want different panels.

const DOC_RUN_HEIGHT_KEY = "doc-run-heights";
const DOC_RUN_HEIGHT_MIN = 96;

function docIdeRunHeights() {
  try {
    return prefs.json(DOC_RUN_HEIGHT_KEY, null) || {};
  } catch {
    return {};
  }
}

//: One height per tab (D8): Output's per document, as before (a file that
//: prints three lines and one that renders a page want different panels);
//: Problems, Tests and the Console one each, for every document.
function docIdeRunSaveHeight(px, tab = docRun?.tab) {
  if (!currentDoc) return;
  const key = tab && tab !== "output" ? `panel:${tab}` : currentDoc.id;
  const all = docIdeRunHeights();
  if (px === null) delete all[key];
  else all[key] = Math.round(px);
  prefs.setJSON(DOC_RUN_HEIGHT_KEY, all);
}

function docIdeRunSavedHeight(tab) {
  if (!currentDoc) return undefined;
  return docIdeRunHeights()[tab && tab !== "output" ? `panel:${tab}` : currentDoc.id];
}

function docIdeRunApply(dom, px, save = true) {
  const max = Math.max(DOC_RUN_HEIGHT_MIN, Math.round(window.innerHeight * 0.8));
  if (px === null) {
    dom.style.height = "";
    if (save) docIdeRunSaveHeight(null);
    return;
  }
  const next = Math.min(Math.max(Math.round(px), DOC_RUN_HEIGHT_MIN), max);
  dom.style.height = `${next}px`;
  if (save) docIdeRunSaveHeight(next);
}

function docIdeRunGrip(dom, view) {
  const handle = document.createElement("div");
  handle.className = "sidebar-resize doc-run-resize";
  handle.setAttribute("role", "separator");
  handle.setAttribute("aria-orientation", "horizontal");
  handle.setAttribute("tabindex", "0");
  handle.setAttribute("aria-label", "Resize the output: arrow keys, or drag");
  handle.title = "Drag to resize, double-click to reset";
  //: The value it says (WCAG 4.1.2) is the height: the helper's height axis.
  trackSeparatorValue(handle, dom, DOC_RUN_HEIGHT_MIN, Math.round(window.innerHeight * 0.8), "height");
  handle.addEventListener("pointerdown", (event) => {
    event.preventDefault();
    const startY = event.clientY;
    const start = dom.getBoundingClientRect().height;
    document.body.classList.add("resizing-sidebar");
    //: Dragging up (a negative delta) makes it taller: the panel grows away
    //: from its bottom edge, which stays put.
    const move = (e) => docIdeRunApply(dom, start - (e.clientY - startY));
    const stop = () => {
      document.body.classList.remove("resizing-sidebar");
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", stop);
      view.requestMeasure();
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", stop);
  });
  handle.addEventListener("keydown", (event) => {
    const step = event.shiftKey ? 64 : 16;
    const now = dom.getBoundingClientRect().height;
    if (event.key === "ArrowUp") docIdeRunApply(dom, now + step);
    else if (event.key === "ArrowDown") docIdeRunApply(dom, now - step);
    else if (event.key === "Home") docIdeRunApply(dom, null);
    else return;
    event.preventDefault();
    view.requestMeasure();
  });
  handle.addEventListener("dblclick", () => {
    docIdeRunApply(dom, null);
    view.requestMeasure();
  });
  dom.prepend(handle);
  //: Each tab its own height, set as the tab shows (`docRunShowTab`).
  dom.addEventListener("mm-panel-tab", (event) => {
    const saved = docIdeRunSavedHeight(event.detail);
    docIdeRunApply(dom, Number.isFinite(saved) ? saved : null, false);
  });
}

// -----------------------------------------------------------------------------
// The IDE shell (DOCUMENTS_PLAN 23, I3, Brief 71): the editor's own keys, its
// palette, the split and the keybindings sheet. The panel's tabs, Problems
// and the consoles are documents-code.js's (`docRunPanel`).
// -----------------------------------------------------------------------------

//: The editor's chords beyond the panel's, VS Code's each. The command
//: table (documents.js) carries the same keys for the palette and the sheet.
const DOC_IDE_KEYS = [
  { keys: "Ctrl+Shift+P", run: () => docIdeOpenPalette() },
  { keys: "F1", run: () => docIdeOpenPalette() },
  { keys: "Ctrl+\\", run: () => docIdeToggleSplit() },
];

//: A key in the code editor: the panel's chords, then the table above.
//: Handled ones stop here, so the app's registry (Ctrl+Shift+P clips a note,
//: Ctrl+Shift+Y the companion) does not answer them as well. Ctrl+K waits
//: for its second chord (`docIdeChordStart`), as VS Code does.
function docIdeKeydown(event) {
  let done = matchesShortcut(event, "Ctrl+K") && docIdeChordStart();
  if (!done) done = docPanelChord(event);
  if (!done) {
    const row = DOC_IDE_KEYS.find((r) => matchesShortcut(event, r.keys));
    if (row) {
      row.run();
      done = true;
    }
  }
  if (!done) return false;
  event.preventDefault();
  event.stopPropagation();
  return true;
}

//: Ctrl+K Ctrl+S, VS Code's keybindings chord (OPEN 1067). Ctrl+K in a code
//: file is still the app's palette, but it waits a moment for a second
//: chord rather than opening at once: the palette used to flash open and
//: shut before the sheet. Ctrl+S then opens the sheet, before the
//: registry's Ctrl+S could save; Escape drops the chord; a typed letter
//: opens the palette with the letter in it; any other key, or the wait
//: running out, opens the palette.
const DOC_IDE_CHORD_WAIT_MS = 400;

function docIdeChordStart() {
  clearTimeout(docIde.chordTimer);
  docIde.chordAt = Date.now();
  docIde.chordTimer = setTimeout(() => docIdeChordEnd(), DOC_IDE_CHORD_WAIT_MS);
  return true;
}

function docIdeChordEnd(seed = "") {
  clearTimeout(docIde.chordTimer);
  docIde.chordAt = 0;
  return Promise.resolve(openPalette()).then(() => {
    const input = $("palette-input");
    if (!seed || !input) return;
    input.value = seed;
    input.dispatchEvent(new Event("input", { bubbles: true }));
  });
}

window.addEventListener("keydown", (event) => {
  if (!docIde.chordAt) return;
  if (["Control", "Meta", "Shift", "Alt"].includes(event.key) || matchesShortcut(event, "Ctrl+K")) return;
  if (matchesShortcut(event, "Ctrl+S")) {
    clearTimeout(docIde.chordTimer);
    docIde.chordAt = 0;
    event.preventDefault();
    event.stopImmediatePropagation();
    docIdeOpenKeys();
    return;
  }
  if (event.key === "Escape") {
    clearTimeout(docIde.chordTimer);
    docIde.chordAt = 0;
    event.preventDefault();
    event.stopImmediatePropagation();
    return;
  }
  const printable = event.key.length === 1 && !event.ctrlKey && !event.metaKey && !event.altKey;
  if (printable) {
    event.preventDefault();
    event.stopImmediatePropagation();
  }
  docIdeChordEnd(printable ? event.key : "");
}, true);

//: The editor's palette (Ctrl+Shift+P, F1): the app's palette (the rich
//: picker, its keys and its preview), opened on ">", which narrows it to
//: this document's commands matched fuzzily (`paletteMatches`). One list,
//: not a second one.
async function docIdeOpenPalette() {
  await openPalette();
  const input = $("palette-input");
  if (!input) return false;
  input.value = "> ";
  input.dispatchEvent(new Event("input", { bubbles: true }));
  return true;
}

//: The second half's code tools (OPEN row 1066): the completion list, the
//: lint and its gutter, the snippets and the pairs and indent, as the first
//: half has them. Not the run panel or the breakpoint lane: a document has
//: one of each, the first half's, as VS Code's one panel serves both groups.
function docIdeSplitTools(CM) {
  const type = docFileType();
  if (type.previewable || ["txt", "csv"].includes(type.ext)) return [];
  const config = { activateOnTyping: true, maxRenderedOptions: 60 };
  if (type.ext === "css") config.override = docCssSources(CM);
  const native = ["js", "ts", "py", "css", "html"].includes(type.ext);
  return [
    CM.lint.linter(docCodeLintSource(CM), DOC_LINT_CONFIG),
    CM.lint.lintGutter(),
    CM.autocomplete.autocompletion(config),
    docNativeSnippets(CM, type.ext),
    native ? [] : docCodeCompletionData(CM),
    docCodeEditing(CM, type),
  ];
}

//: Split (Ctrl+\): a second editor on the same document beside the first,
//: its own caret and scroll (scroll sync off, VS Code's default). Each
//: half's edits reach the other through one annotation; the history is the
//: first half's, so Ctrl+Z in either undoes the last edit made in either.
function docIdeToggleSplit() {
  if (docIde.split) return docIdeCloseSplit();
  const CM = window.CM6;
  const main = docCmView;
  const host = $("doc-editor");
  if (!CM || !main || !host || docFileType().previewable) return false;
  if (!docIde.sync) docIde.sync = CM.state.Annotation.define();
  const carried = [docCmParts.language, docCmParts.theme, docCmParts.gutter, docCmParts.wrap]
    .filter(Boolean)
    .map((part) => {
      try {
        return part.get(main.state) || [];
      } catch {
        return [];
      }
    });
  const undo = (redo) => () => (redo ? CM.commands.redo(main) : CM.commands.undo(main));
  const state = CM.state.EditorState.create({
    doc: main.state.doc,
    extensions: [
      ...carried,
      ...docIdeSplitTools(CM),
      CM.view.lineNumbers(),
      CM.view.highlightActiveLine(),
      CM.view.highlightActiveLineGutter(),
      CM.view.drawSelection(),
      CM.language.bracketMatching(),
      CM.language.syntaxHighlighting(CM.language.defaultHighlightStyle, { fallback: true }),
      CM.state.EditorState.tabSize.of(main.state.tabSize),
      CM.view.EditorView.editorAttributes.of({ class: "doc-split-view doc-content-code" }),
      CM.view.EditorView.contentAttributes.of({ "aria-label": "The same file, second view" }),
      CM.state.Prec.highest(CM.view.EditorView.domEventHandlers({ keydown: (event) => docIdeKeydown(event) })),
      CM.view.keymap.of([
        { key: "Mod-z", run: undo(false) },
        { key: "Mod-y", run: undo(true) },
        { key: "Mod-Shift-z", run: undo(true) },
        ...CM.commands.defaultKeymap,
      ]),
    ],
  });
  const view = new CM.view.EditorView({
    state,
    dispatchTransactions: (trs, self) => {
      self.update(trs);
      for (const tr of trs) {
        if (tr.changes.empty || tr.annotation(docIde.sync)) continue;
        main.dispatch({ changes: tr.changes, annotations: [docIde.sync.of(true), CM.state.Transaction.userEvent.of(tr.annotation(CM.state.Transaction.userEvent) || "input")] });
      }
    },
  });
  docIde.split = view;
  docIde.splitDoc = currentDoc?.id ?? null;
  host.classList.add("doc-split-on");
  host.appendChild(view.dom);
  view.dispatch({ selection: { anchor: Math.min(main.state.selection.main.head, view.state.doc.length) }, scrollIntoView: true });
  view.focus();
  return true;
}

function docIdeCloseSplit() {
  const view = docIde.split;
  if (!view) return false;
  docIde.split = null;
  docIde.splitDoc = null;
  view.destroy();
  view.dom.remove();
  $("doc-editor")?.classList.remove("doc-split-on");
  docCmView?.focus();
  return true;
}

//: The first half's edits, into the second. Another document in the first
//: half (the editor is rebuilt for it) closes the split, and a second half
//: that has drifted (a whole-text replace that came by another way) takes
//: the first half's text again.
function docIdeSplitFollow(update) {
  const view = docIde.split;
  if (!view) return;
  if (docIde.splitDoc !== (currentDoc?.id ?? null) || update.view !== docCmView) {
    if (update.view === docCmView) docIdeCloseSplit();
    return;
  }
  if (!update.docChanged) return;
  for (const tr of update.transactions) {
    if (tr.changes.empty || tr.annotation(docIde.sync)) continue;
    view.dispatch({ changes: tr.changes, annotations: docIde.sync.of(true) });
  }
  if (view.state.doc.length !== update.state.doc.length) {
    view.dispatch({ changes: { from: 0, to: view.state.doc.length, insert: update.state.doc.toString() }, annotations: docIde.sync.of(true) });
  }
}

//: The keybindings sheet (DOCUMENTS_PLAN 25 row 6), Ctrl+K Ctrl+S: every row
//: of the command table with its key or "No key", searchable. DESIGN.md's
//: sheet of keys (the board's "?"): the dialog recipe, a search field, and
//: sections of `li.wb-help-row`. Built on first use.
function docIdeKeysOverlay() {
  let overlay = $("doc-keys-overlay");
  if (overlay) return overlay;
  overlay = document.createElement("div");
  overlay.id = "doc-keys-overlay";
  overlay.className = "modal-overlay hidden";
  overlay.setAttribute("role", "dialog");
  overlay.setAttribute("aria-modal", "true");
  overlay.setAttribute("aria-labelledby", "doc-keys-title");
  const card = document.createElement("div");
  card.className = "card modal-card wb-help-card doc-keys-card";
  const head = document.createElement("div");
  head.className = "dialog-head";
  const title = document.createElement("h2");
  title.className = "dialog-head-title";
  title.id = "doc-keys-title";
  const titleIcon = document.createElement("i");
  titleIcon.className = "ph ph-keyboard ph-lead";
  titleIcon.setAttribute("aria-hidden", "true");
  title.append(titleIcon, " Editor keys");
  const headActions = document.createElement("span");
  headActions.className = "dialog-head-actions";
  const close = document.createElement("button");
  close.type = "button";
  close.className = "icon-only ghost small dialog-head-btn";
  close.title = "Close (Esc)";
  close.setAttribute("aria-label", "Close");
  const closeIcon = document.createElement("i");
  closeIcon.className = "ph ph-x";
  closeIcon.setAttribute("aria-hidden", "true");
  close.appendChild(closeIcon);
  close.addEventListener("click", () => docIdeCloseKeys());
  headActions.appendChild(close);
  head.append(title, headActions);
  const intro = document.createElement("p");
  intro.className = "muted wb-help-intro";
  intro.textContent = "Every command the document editor has, and its key. Ctrl+Shift+P runs any of them by name.";
  const field = document.createElement("div");
  field.className = "search-field wb-help-search";
  const fieldIcon = document.createElement("i");
  fieldIcon.className = "ph ph-magnifying-glass search-field-icon";
  fieldIcon.setAttribute("aria-hidden", "true");
  const search = document.createElement("input");
  search.type = "search";
  search.id = "doc-keys-search";
  search.className = "search-field-input";
  search.placeholder = "Find a key or a command";
  search.setAttribute("aria-label", "Find a key or a command");
  search.autocomplete = "off";
  search.spellcheck = false;
  search.addEventListener("input", () => docIdeRenderKeys(search.value));
  field.append(fieldIcon, search);
  const sections = document.createElement("div");
  sections.className = "wb-help-sections";
  sections.id = "doc-keys-sections";
  const none = document.createElement("p");
  none.className = "muted wb-help-none hidden";
  none.id = "doc-keys-none";
  none.setAttribute("role", "status");
  none.textContent = "Nothing matches. Try a word like run, fold or bold.";
  card.append(head, intro, field, sections, none);
  overlay.appendChild(card);
  overlay.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    event.preventDefault();
    event.stopPropagation();
    docIdeCloseKeys();
  });
  wireBackdropClose(overlay, docIdeCloseKeys);
  document.body.appendChild(overlay);
  return overlay;
}

//: The sheet's sections: the code editor's commands, then the ones every
//: document has, in the table's order; a row's keys are split into caps,
//: a two-chord sequence ("Ctrl+K Ctrl+S") into its two chords.
function docIdeRenderKeys(query = "") {
  const host = $("doc-keys-sections");
  if (!host) return 0;
  const words = String(query).toLowerCase().split(/\s+/).filter(Boolean);
  const sections = [
    { title: "Code files", rows: DOC_COMMANDS.filter((c) => c.code) },
    { title: "Every document", rows: DOC_COMMANDS.filter((c) => !c.code) },
  ];
  host.replaceChildren();
  let shown = 0;
  for (const section of sections) {
    const rows = section.rows.filter((c) => {
      const text = `${c.label} ${c.keys === "none" ? "no key" : c.keys}`.toLowerCase();
      return words.every((w) => text.includes(w));
    });
    if (!rows.length) continue;
    const box = document.createElement("section");
    box.className = "wb-help-section";
    const head = document.createElement("h3");
    head.className = "wb-help-section-head";
    head.textContent = section.title;
    const list = document.createElement("ul");
    list.className = "wb-help-list";
    list.setAttribute("aria-label", section.title);
    for (const command of rows) {
      const li = document.createElement("li");
      li.className = "wb-help-row";
      li.dataset.command = command.id;
      const icon = document.createElement("i");
      icon.className = `ph ${command.icon.replace(/^ph:/, "ph-")} wb-help-row-icon`;
      icon.setAttribute("aria-hidden", "true");
      const label = document.createElement("span");
      label.className = "wb-help-row-label";
      label.textContent = command.label;
      const keys = document.createElement("span");
      keys.className = "wb-help-row-keys";
      if (!command.keys || command.keys === "none") {
        keys.classList.add("muted");
        keys.textContent = "No key";
      } else {
        for (const chord of command.keys.split(" / ")) {
          const kbd = document.createElement("kbd");
          kbd.textContent = chord;
          keys.append(kbd);
        }
      }
      li.append(icon, label, keys);
      list.append(li);
      shown += 1;
    }
    box.append(head, list);
    host.append(box);
  }
  $("doc-keys-none")?.classList.toggle("hidden", shown > 0);
  return shown;
}

function docIdeOpenKeys() {
  const overlay = docIdeKeysOverlay();
  docIde.keysReturn = document.activeElement;
  const search = $("doc-keys-search");
  if (search) search.value = "";
  docIdeRenderKeys("");
  overlay.classList.remove("hidden");
  $("doc-keys-sections")?.scrollTo?.(0, 0);
  search?.focus();
  return true;
}

function docIdeCloseKeys() {
  const overlay = $("doc-keys-overlay");
  if (!overlay || overlay.classList.contains("hidden")) return false;
  overlay.classList.add("hidden");
  const back = docIde.keysReturn;
  docIde.keysReturn = null;
  if (back && back.isConnected && typeof back.focus === "function") back.focus();
  return true;
}
