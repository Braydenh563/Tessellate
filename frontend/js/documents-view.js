// The document editor's CodeMirror view glue, carved out of documents.js (OPEN W28 D21):
// the key chords and keymap, the extension list, the findings plugin, the editor mount,
// the code-draw and language syncs, the gutter and the line clipboard. Loaded right before
// documents.js (app.js): its top level only declares, and documents.js calls into it at load
// (setDocView -> docCmSyncLanguage, the toolbar -> docCmSyncGutter); it reads documents.js's
// globals only inside functions.

//: **Ctrl+Shift+Z is redo, whatever the key reports.** Shift+Z arrives as
//: `key: "z"` with Caps Lock on, and the keymap then matched Mod-z (undo):
//: dogfood item 1. A binding cannot see the event, so a DOM handler.
function docRedoChord(CM) {
  return CM.state.Prec.highest(CM.view.EditorView.domEventHandlers({
    keydown: (event, view) => {
      if (!(event.ctrlKey || event.metaKey) || event.altKey) return false;
      const key = event.key.toLowerCase();
      //: C32 (gsweep): the keyboard's undo and redo in the document gave no notice while the
      //: status bar's did; the document's own view goes through `docUndo`/`docRedo`, which say so
      //: ("info" shows even with notifications muted). A note's box keeps CodeMirror's own.
      const mine = typeof docCmView !== "undefined" && view === docCmView;
      if (key === "z" && event.shiftKey) {
        event.preventDefault();
        if (mine) docRedo();
        else CM.commands.redo(view);
        return true;
      }
      if (mine && !event.shiftKey && (key === "z" || key === "y")) {
        event.preventDefault();
        if (key === "z") docUndo();
        else docRedo();
        return true;
      }
      return false;
    },
  }));
}

//: The chords the fallback textarea's own `keydown` handler carries, as a
//: keymap instead. They cannot simply be re-attached to CodeMirror's DOM: it
//: is a contenteditable with its own key handling and its own IME support, so
//: a listener bolted onto it would fight the editor rather than extend it.
//: Same behaviour and the same order (the shifted S before the plain one, for
//: the reason that handler's own comment gives).
function docProseChord(run) {
  if (!docFileType().previewable) return false;
  run();
  return true;
}

//: **The insert panels' chords** (INBOX 1544), one list for the document and
//: every note box: Ctrl+; emoji, Ctrl+Shift+; icons, Ctrl+' symbols and
//: Ctrl+Shift+' the calculator (Alt+= is the equation, `lazy-entries.js`). The
//: base key is read, as for the list chords. Each is a row of `DOC_COMMANDS`, so
//: the shortcut sheet lists it; `apply(kind)` says how the caller runs a kind.
docCmKeymap.insert = (apply) => [["Mod-;", "emoji"], ["Mod-Shift-;", "icon"], ["Mod-'", "symbol"], ["Mod-Shift-'", "calculator"]].map(([key, kind]) => ({ key, run: () => apply(kind) }));

//: **Ctrl+K with a selection makes a link** (INBOX 1559). True when it did;
//: false (no selection, or a code file, which keeps its own Ctrl+K chord)
//: hands the key on to the command palette.
docCmKeymap.link = (box) => !!box && docFileType().previewable && box.selectionStart !== box.selectionEnd && (applyMarkdown("link"), true);

function docCmKeymap(CM) {
  const surface = () => docSurface();
  return [
    //: A Live table's own Enter and arrows, first so they are asked before
    //: anything that would treat a row as a line of text; each declines
    //: (returns false) everywhere that is not a Live table cell.
    { key: "Enter", run: (view) => docTableKeyMove(view, "Enter") },
    //: And a fresh remark's Enter steps past its closing marker (DX24).
    { key: "Enter", run: (view) => docAnnotateSelection.end(view) },
    { key: "Mod-Enter", run: (view) => docTableCtrlEnter(view) },
    { key: "ArrowDown", run: (view) => docTableKeyMove(view, "ArrowDown") },
    { key: "ArrowUp", run: (view) => docTableKeyMove(view, "ArrowUp") },
    //: A markdown document moves a block, not a line (`docBlockMoveEdit`); a
    //: code file declines and the default line move answers.
    { key: "Alt-ArrowUp", run: (view) => docBlockMoveRun(view, -1) },
    { key: "Alt-ArrowDown", run: (view) => docBlockMoveRun(view, 1) },
    {
      key: "Escape",
      run: () => {
        //: Arms the Tab escape hatch (see `docTabEscapes`); the search panel's
        //: own keymap closes itself on Escape, so this one never consumes it.
        //: Not when this Escape is about to close a menu or a tooltip: it was
        //: spent on that, and arming then threw the next Tab out of the editor
        //: minutes later (DX4, audit 1102).
        docTabEscapes = ![...document.querySelectorAll('[role="menu"], .cm-tooltip')].some((el) => el.getClientRects().length > 0);
        return false;
      },
    },
    //: Escape inside a remark leaves it, past the closing marker (DX24).
    { key: "Escape", run: (view) => docAnnotateSelection.end(view, true) },
    //: Tab indents, in prose as well as code, with Escape-then-Tab as the way
    //: out. `docTabEscapes` above carries the whole reason.
    {
      key: "Tab",
      run: () => {
        if (docTakeTabEscape()) return false;
        indentDocSelection(surface(), false);
        return true;
      },
    },
    {
      key: "Shift-Tab",
      run: () => {
        if (docTakeTabEscape()) return false;
        //: A code file keeps Shift+Tab with nothing to outdent, as Tab keeps
        //: its press (1031 CE5: it left for the dock mid-edit); Escape, then
        //: Tab or Shift+Tab, is the way out. Prose still falls through.
        if (!docCanOutdent(surface())) return !docFileType().previewable;
        indentDocSelection(surface(), true);
        return true;
      },
    },
    { key: "Mod-/", run: () => { toggleDocComment(surface()); return true; } },
    //: The chords below write markdown syntax. In a code file they decline
    //: (`docProseChord`), so Ctrl+B does not wrap a Python line in `**` and
    //: the engine's own binding for the key answers instead.
    { key: "Mod-Shift-s", run: () => docProseChord(() => { wrapDocSelection("~~", "struck through"); }) },
    { key: "Mod-s", run: () => { saveDocument(); return true; } },
    { key: "Mod-b", run: () => docProseChord(() => { wrapDocSelection("**", "bold text"); }) },
    { key: "Mod-i", run: () => docProseChord(() => { wrapDocSelection("*", "italic text"); }) },
    //: Underline, the one chord every word processor shares. CodeMirror binds
    //: Mod-u to "undo selection", which on a prose page just collapses the
    //: selection and reads as the key being dead.
    { key: "Mod-u", run: () => docProseChord(() => { applyMarkdown("underline"); }) },
    { key: "Mod-e", run: () => docProseChord(() => { wrapDocSelection("`"); }) },
    { key: "Mod-1", run: () => docProseChord(() => { applyMarkdown("h1"); }) },
    { key: "Mod-2", run: () => docProseChord(() => { applyMarkdown("h2"); }) },
    { key: "Mod-3", run: () => docProseChord(() => { applyMarkdown("h3"); }) },
    //: Ctrl+Alt+1 to 6 (INBOX 1559): the browser keeps Ctrl+1 to 3 for its tabs.
    //: Ctrl+K on selected text makes a link; with none it declines, and the
    //: app's palette answers.
    ...[1, 2, 3, 4, 5, 6].map((n) => ({ key: `Mod-Alt-${n}`, run: () => docProseChord(() => { applyMarkdown(`h${n}`); }) })),
    { key: "Mod-k", run: () => docCmKeymap.link(docSurface()) },
    //: Google Docs' list chords; the base key is read, so Shift's `*` is 8.
    { key: "Mod-Shift-8", run: () => docProseChord(() => { applyMarkdown("ul"); }) },
    { key: "Mod-Shift-7", run: () => docProseChord(() => { applyMarkdown("ol"); }) },
    { key: "Mod-Shift-9", run: () => docProseChord(() => { applyMarkdown("task"); }) },
    ...docCmKeymap.insert((kind) => (kind === "calculator" ? (applyMarkdown(kind), true) : docProseChord(() => { applyMarkdown(kind); }))),
    //: One gesture, one entry point: `toggleDocFindBar` opens the engine's
    //: panel here and the app's own bar on the fallback, so this binding does
    //: not have to know which is on screen.
    { key: "Mod-f", run: () => { toggleDocFindBar(true); return true; } },
    //: VS Code's Go to line. A code file only; CodeMirror's own binding for
    //: the key (find next) stays for prose and on F3.
    { key: "Mod-g", run: (view) => (docFileType().previewable ? false : CM.search.gotoLine(view)) },
    //: Prose and plain text get it on Ctrl+Alt+G (L4): Ctrl+G stays find next there.
    { key: "Mod-Alt-g", run: (view) => CM.search.gotoLine(view) },
    //: Ctrl+H is Replace in every word processor and editor; the panel is the
    //: same, with the cursor in its Replace field. Cmd+H hides the app on a
    //: Mac, so Cmd+Option+F, VS Code's Mac chord, does the same (audit 1028 D31).
    { key: "Mod-h", run: () => docOpenReplace() },
    { key: "Mod-Alt-f", run: () => docOpenReplace() },
    //: Find in every document (INBOX 404), VS Code's search across files.
    { key: "Mod-Shift-f", run: () => docFindInDocuments() },
    //: The formatting toolbar, shown or hidden (INBOX 574).
    { key: "Mod-Shift-x", run: () => { toggleDocToolbar(); return true; } },
  ];
}

//: Everything the view is built from. Split out so the mount and a later
//: rebuild (`docResetDocument`) cannot drift.
//: **A click in a live-view table cell lands where it was pressed** (owner:
//: "I can't edit specific boxes in tables in the document editor live
//: view"). The cells are laid out as a CSS grid over one line of source, and
//: CodeMirror's own coordinate mapping reads that line as if it were flowing
//: text: measured, a click at the end of "r2b" put the caret at the cell's
//: start and a click inside "r1a" put it in the next cell. The browser's own
//: caret resolver does know the grid, so the press is resolved with it and
//: handed to the view as a position. Focus is taken explicitly because a
//: handled mousedown skips CodeMirror's own focus step: the first version of
//: this returned `true` without it, and every keystroke after the click went
//: nowhere. A drag, a Shift or Alt click, and anything but the main button
//: stay CodeMirror's.
function docTableCellClick(event, view) {
  if (event.button !== 0 || event.shiftKey || event.altKey || event.detail > 1) return false;
  if (!event.target.closest?.(".cm-md-td, .cm-md-th")) return false;
  let node = null;
  let offset = 0;
  if (document.caretPositionFromPoint) {
    const hit = document.caretPositionFromPoint(event.clientX, event.clientY);
    if (hit) ({ offsetNode: node, offset } = hit);
  } else if (document.caretRangeFromPoint) {
    const hit = document.caretRangeFromPoint(event.clientX, event.clientY);
    if (hit) ({ startContainer: node, startOffset: offset } = hit);
  }
  if (!node || !view.contentDOM.contains(node)) return false;
  let pos;
  try {
    pos = view.posAtDOM(node, offset);
  } catch {
    return false;
  }
  event.preventDefault();
  view.focus();
  view.dispatch({ selection: { anchor: pos }, scrollIntoView: false, userEvent: "select.pointer" });
  return true;
}

// -----------------------------------------------------------------------------
// The code side (diagnostics, completions, Emmet, hover, symbols, sticky
// scroll, go to definition, Run, format, quick fixes) is in documents-code.js,
// which the Library bundle loads before this file. See its header.
// -----------------------------------------------------------------------------


//: The code editor's minimap, merge view, palette rows and output grip
//: (documents-ide.js, Brief 42), fetched as this file runs rather than listed
//: in app.js's bundle table, whose gzipped size is ratcheted. A code file
//: opened before it lands gets its tools again once it has.
//: The palette rows and the history menu reach documents-ide.js through here, so
//: one pressed before the file has landed waits for it instead of throwing.
function docIdeCall(name, ...args) {
  return lazyScript("/js/documents-ide.js").then((ok) => ok && window[name](...args));
}

//: Fetched once documents.js has run, not as this file runs: the idle warm-up puts the bundle on the page one file at a time, so a fetch started here ran documents-ide.js before documents.js had defined `docToolPref` and `docCmView` (two ReferenceErrors, and the IDE's setup stopped at its first line). `typeof` because the bundle may have failed to load.
lazyScript("/js/documents.js").then(() => lazyScript("/js/documents-ide.js")).then(() => {
  const CM = window.CM6;
  //: Here, not at the IDE script's top level: that script can run before documents.js has declared `docToolPref` (page error "docToolPref is not defined").
  if (typeof docToolPref === "function" && $("doc-minimap")) $("doc-minimap").checked = docToolPref("codeMinimap", false);
  if (typeof docCmView !== "undefined" && docCmView && CM && docCmParts.code && !docFileType().previewable) {
    docCmView.dispatch({ effects: docCmParts.code.reconfigure(docCodeTools(CM)) });
  }
});

function docCmExtensions(CM) {
  const type = docFileType();
  docCmParts.language = new CM.state.Compartment();
  docCmParts.theme = new CM.state.Compartment();
  docCmParts.gutter = new CM.state.Compartment();
  docCmParts.wrap = new CM.state.Compartment();
  docCmParts.live = new CM.state.Compartment();
  docCmParts.spell = new CM.state.Compartment();
  docCmParts.reading = new CM.state.Compartment();
  docCmParts.code = new CM.state.Compartment();
  docCmParts.placeholder = new CM.state.Compartment();
  if (!docFindingsEffect) docFindingsEffect = CM.state.StateEffect.define();
  return [
    //: First, so its gutter is the leftmost: the error mark sits outside the
    //: line numbers, where every code editor the owner compares this with
    //: puts it.
    docCmParts.code.of(docCodeTools(CM)),
    //: Live's decorations, off until `setDocView` turns them on. Findings are
    //: a separate plugin because they are drawn in *every* view: an underline
    //: under a misspelling is not a rendering of the markdown, it is the
    //: checker saying something, and switching to Source to see the raw text
    //: is not a reason to stop being told.
    docCmParts.live.of(docView === "live" ? docLiveExtensions(CM) : []),
    CM.state.Prec.high(docFindingsPlugin(CM)),
    //: Whole-line copy and cut with an empty selection (INBOX 652).
    CM.state.Prec.high(docLineClipboardExtension(CM)),
    //: Suggestion mode and read aloud (PROSE-TOOLS), inert until asked for.
    docProseToolExtensions(CM),
    //: The dimming is a compartment because it is a preference that changes
    //: while the view is live; the typewriter listener is not, because it is
    //: inert until its flag is on and reconfiguring an extension to say
    //: "return early" buys nothing.
    docCmParts.reading.of(docReadingModes.dimOthers ? docReadingPlugin(CM) : []),
    docTypewriterExtension(CM),
    docCmParts.gutter.of(docCmGutter(CM)),
    //: Folding, wherever the gutter is: a heading section, a fenced block and
    //: a `[!note]-` callout all fold with or without the line numbers on.
    CM.language.codeFolding(),
    CM.view.keymap.of(CM.language.foldKeymap),
    docHeadingFold(CM),
    docCalloutFold(CM),
    CM.view.highlightSpecialChars(),
    CM.commands.history(),
    CM.view.drawSelection(),
    CM.view.dropCursor(),
    CM.state.EditorState.allowMultipleSelections.of(true),
    CM.language.indentOnInput(),
    CM.language.syntaxHighlighting(CM.language.defaultHighlightStyle, { fallback: true }),
    CM.language.bracketMatching(),
    CM.search.highlightSelectionMatches(),
    //: The panel at the top, where the app's own find bar already sits, so
    //: the control does not move when the engine takes over from the
    //: fallback. Its chrome is restyled in 09-editor.css onto this app's
    //: field and button recipe.
    CM.search.search({ top: true }),
    docCmSearchCount(CM),
    CM.view.rectangularSelection(),
    CM.view.crosshairCursor(),
    docCmParts.wrap.of(docCmDrawFor(CM, type)),
    docCmParts.language.of(docCmViewLanguage(CM)),
    docCmParts.theme.of(docCmTheme(CM)),
    docCmHighlight(CM),
    docCmParts.placeholder.of(CM.view.placeholder(docPlaceholderText || "")),
    //: This app's chords first, then CodeMirror's own defaults, so a binding
    //: the editor already had wins over the library's.
    docRedoChord(CM),
    CM.view.keymap.of([
      ...docCmKeymap(CM),
      ...CM.search.searchKeymap,
      ...CM.commands.historyKeymap,
      ...CM.commands.defaultKeymap,
    ]),
    //: The disarming half of the Escape-then-Tab hatch. Anything that is not
    //: part of that chord means the writer went back to writing, and a flag
    //: still armed then would send the next Tab to the toolbar instead of
    //: into the line. A plain DOM handler, because a keymap can only match keys
    //: it names, and at the highest precedence, because a key the keymap
    //: handles (an arrow, a letter's own binding) ends the event before a
    //: default-precedence handler is asked, which left the flag armed after
    //: "Escape, arrow, Tab" (DX4, audit 1102). A pointer press disarms it too,
    //: whatever else answers the press. Never handles the event (always false).
    CM.state.Prec.highest(CM.view.EditorView.domEventHandlers({
      keydown: (event) => {
        if (event.key !== "Tab" && event.key !== "Shift" && event.key !== "Escape") {
          docTabEscapes = false;
        }
        //: Ctrl+Shift+V: the paste that follows is plain text (FEAT-04).
        docPastePlain = (event.ctrlKey || event.metaKey) && event.shiftKey && event.key.toLowerCase() === "v";
        return false;
      },
      mousedown: () => {
        docTabEscapes = false;
        return false;
      },
    })),
    CM.view.EditorView.domEventHandlers({
      mousedown: (event, view) => docTableCellClick(event, view),
    }),
    //: Ahead of the markdown language's own paste-a-URL-as-a-link, which would
    //: take a web address over selected words first and leave no paste chip.
    CM.state.Prec.high(CM.view.EditorView.domEventHandlers({
      paste: (event, view) => docTablePasteEvent(event, view) || docSmartPasteEvent(event, view) || docRichPasteEvent(event, view),
    })),
    CM.view.EditorView.updateListener.of(docCmUpdate),
    //: **The browser's own spellcheck, and the one condition it stays on
    //: under.** CodeMirror turns it off by default, and for a code editor
    //: that is right: a red squiggle under every identifier is noise. This is
    //: a writing surface, so while this app's own checker knew 42 typos the
    //: browser's dictionary was by far the better of the two and it was left
    //: on. That is what the owner was clicking: "no edit suggestions popup
    //: panel appears when I click on underlined words" is a native squiggle
    //: the app cannot see, under a word the app has no finding for.
    //:
    //: Now that there is a real word list the app draws its own underline
    //: under the same words, and its underline opens a menu. Two marks under
    //: one word, only one of which answers a click, is worse than either
    //: alone, so the browser's goes off the moment the list is ready and
    //: comes back if it never loads.
    docCmParts.spell.of(docCmSpellcheck(CM)),
    //: Named (WCAG 4.1.2, INBOX 433: axe, aria-input-field-name): the
    //: editable had a role of textbox and no name at all.
    //: And described (W26): Tab indents here, so the way out is said where a screen reader finds it.
    CM.view.EditorView.contentAttributes.of({ "aria-label": "Document text", "aria-description": "Tab indents. To leave the editor, press Escape, then Tab." }),
  ];
}

//: The browser's checker is the fallback, not the default: it is on exactly
//: while this app has no dictionary of its own to check against.
function docCmSpellcheck(CM) {
  return CM.view.EditorView.contentAttributes.of({
    //: A code file never takes the browser's squiggles (`docCodeSpellFindings`).
    spellcheck: docWordlistReady() || !docFileType().previewable ? "false" : "true",
  });
}

//: Called when the word list lands, which is the one moment the answer above
//: changes. A compartment rather than a rebuild: rebuilding the editor's
//: extensions would throw away the undo history and the scroll position for
//: the sake of one attribute.
function docCmApplySpellcheck() {
  const CM = window.CM6;
  if (!docCmView || !CM || !docCmParts.spell) return;
  if (!docCmChanged("spell", String(docWordlistReady() || !docFileType().previewable))) return;
  docCmView.dispatch({ effects: docCmParts.spell.reconfigure(docCmSpellcheck(CM)) });
}

//: **The one place a CodeMirror change becomes an app change.** The library
//: raises a native `input` on its contenteditable *and* calls this, while a
//: scripted transaction raises only this: so the delegated `input` listeners
//: skip anything from inside the view (`docEventFromCm`) and this drives the
//: pipeline for typed and scripted edits alike.
function docCmUpdate(update) {
  if (update.docChanged) {
    docHistoryStamp(update);
    runDocFacts.outlineSame = runDocFacts.outlineSame !== false && outlineNeutral();
    docSurfaceChanged();
    docHistoryPersist();
    //: **Autocorrect, which never ran once under the engine.** The delegated
    //: `input` listener that calls it returns early for anything inside the
    //: view (`docEventFromCm`), because the engine reports its changes here
    //: instead and running both would do every pass twice. That listener was
    //: also the only caller of `docAutocorrectAt`, so switching the surface
    //: to CodeMirror silently turned the feature off: measured 2026-09-12,
    //: typing "teh " with autocorrect switched on left "teh ".
    //:
    //: Postponed by a microtask rather than called here, because this runs
    //: *during* the view's own update and dispatching a transaction into an
    //: update in progress is the one thing CodeMirror will not have. A
    //: microtask still runs before the frame is painted, so the correction is
    //: never visible as two states.
    //:
    //: Only a typed insertion: `isUserEvent("input.type")` is false for the
    //: correction's own transaction, which is what keeps this from looking at
    //: its own work, and false for every scripted rewrite (the AI panel, a
    //: template, a paste is "input.paste"), none of which a writer typed.
    if (update.transactions.some((tr) => tr.isUserEvent("input.type"))) {
      const surface = docSurface();
      queueMicrotask(() => docAutocorrectAt(surface));
    }
    docToolsOnInput(docSurface());
    //: editor.js hangs the "/" and `[[` triggers off a DOM `input` event,
    //: which the engine never raises for a typed character: it applies the
    //: change itself. Called rather than dispatched, so there is no synthetic
    //: event on a contenteditable and no second pass through this pipeline.
    if (typeof editorHandleInput === "function") editorHandleInput(docSurface());
    if (!$("doc-suggest-menu")?.classList.contains("hidden")) closeDocSuggest();
  } else if (!$("doc-suggest-menu")?.classList.contains("hidden")) {
    //: **The word moved without a scroll.** Putting the caret on a line, or
    //: taking the focus off the editor, makes the Live view reveal or hide
    //: that line's markup, and the words after it slide sideways under an
    //: open menu (measured: 16px, the menu left pointing at the gap before
    //: the word). No scroll or resize event is raised for that, so the
    //: engine's own update is the signal, answered once per frame.
    docScheduleSuggestFollow();
  }
  if (update.selectionSet) {
    //: An edit drew it already (`docToolsOnInput`).
    if (!update.docChanged) renderDocCaret();
    //: The outline follows the caret too, on the same beat the breadcrumb
    //: does: an arrow key raises no scroll and no `input`, so without this the
    //: two rows that both answer "where am I" would disagree until the view
    //: moved. Scheduled, not marked, because a held-down arrow key fires far
    //: faster than a class swap needs to be painted. Only when the caret's
    //: line moved (DX1): a key typed on a line cannot move the outline's mark.
    const line = update.state.doc.lineAt(update.state.selection.main.head).number;
    if (line !== docCmUpdate.spyLine) {
      docCmUpdate.spyLine = line;
      scheduleDocOutlineSpy();
    }
  }

  //: **Could this edit change the outline?** (DX1) The rows are drawn from
  //: the heading lines (ATX, and a setext underline with the line above it),
  //: the fences that hide headings, the task boxes that are counted and the
  //: line numbers, so an edit inside one line touching none of those leaves
  //: every row as it was. Measured before: the outline was rebuilt on every
  //: pause in the typing, 93 ms per 22 keys at 1x in a 3,120-line document. A
  //: code file's symbols can come from any line, so its edits always count.
  //: Nested, not a global: the shared scope is at its cap.
  function outlineNeutral() {
    if (!docFileType().previewable) return false;
    const mark = /^\s{0,3}#|^\s*(?:```|~~~)|\[[ xX]\]|^\s*(?:=+|-+)\s*$/;
    const before = update.startState.doc;
    const after = update.state.doc;
    let neutral = true;
    update.changes.iterChanges((fromA, toA, fromB, toB, inserted) => {
      if (!neutral) return;
      if (inserted.lines > 1 || before.sliceString(fromA, toA).includes("\n")) {
        neutral = false;
        return;
      }
      const line = after.lineAt(fromB);
      const next = line.number < after.lines ? after.line(line.number + 1).text : "";
      if (mark.test(before.lineAt(fromA).text) || mark.test(line.text) || /^\s*(?:=+|-+)\s*$/.test(next)) neutral = false;
    });
    return neutral;
  }
}

//: **The prose findings, as decorations** (DOCUMENTS_PLAN Phase 2 decision 5).
//:
//: Phase 0 drew these on a `<div>` behind a transparent-ink textarea, because
//: a textarea's value is a string and there is nothing in it to underline.
//: That layer had to copy twenty-six computed properties to keep its glyphs on
//: top of the real ones, and the comment on `DOC_BACKDROP_PROPS` records what
//: happens when one of them is missed: the underline is right at the top of
//: the file and a word out at the bottom. A decoration has no geometry to keep
//: in step, because it *is* the text.
//:
//: Only the findings that still describe the text as it is now, and only the
//: ones on screen: the prose pass is debounced, so between a keystroke and the
//: next pass every offset after the caret is stale, and painting a stale
//: offset draws a squiggle under the wrong word, which is the one thing a
//: checker must never do.
let docFindingsPluginCache = null;

function docFindingsPlugin(CM) {
  if (docFindingsPluginCache) return docFindingsPluginCache;
  const { Decoration, ViewPlugin } = CM.view;

  function build(view) {
    const doc = view.state.doc;
    const ranges = [];
    docProseFound.forEach((finding, index) => {
      if (DOC_FINDING_SKIP.has(finding.rule)) return;
      if (doc.sliceString(finding.start, finding.end) !== finding.text) return;
      const visible = view.visibleRanges.some(
        (range) => finding.start < range.to && finding.end > range.from
      );
      if (!visible) return;
      ranges.push(
        Decoration.mark({
          class: `cm-finding cm-finding-${docFindingKind(finding)}`,
          //: The *index*, not the finding: a decoration's DOM is rebuilt on
          //: every repaint, so anything hung on the element would be gone by
          //: the time a click needed it. `docFindingMarks` resolves it back.
          attributes: { "data-doc-finding": String(index), title: finding.message },
        }).range(finding.start, finding.end)
      );
    });
    docProse.painted = docProse.sig();
    return Decoration.set(ranges, true);
  }

  docFindingsPluginCache = ViewPlugin.fromClass(
    class {
      constructor(view) {
        this.decorations = build(view);
      }
      update(update) {
        const told =
          docFindingsEffect &&
          update.transactions.some((tr) =>
            tr.effects.some((effect) => effect.is(docFindingsEffect))
          );
        if (update.docChanged) docProse.remap(update.changes);
        if (update.docChanged || update.viewportChanged || told) {
          this.decorations = build(update.view);
        }
      }
    },
    { decorations: (plugin) => plugin.decorations }
  );
  return docFindingsPluginCache;
}

//: `renderDocProse` calls this whenever the list changes. The rebuild walks
//: `docProseFound`, which is rarely past a few dozen entries, and draws only
//: what is on screen. **It sends nothing when the marks would be the ones
//: already drawn** (INBOX 1526): the plugin moves them with every edit, so the
//: pass that follows a key mostly finds them where they are, and a grammar or
//: link answer that changed nothing was a dispatch, a layout and 9 ms (4x) for
//: no mark. Answers (`soon`) share a 16 ms beat (a timer, not a new frame loop:
//: the wake-source census counts those): two that land together paint once.
function docCmRepaintFindings(soon = false) {
  if (!docCmView || !docFindingsEffect) return;
  const send = () => {
    docProse.frame = 0;
    if (!docCmView || !docFindingsEffect) return;
    const sig = docProse.sig();
    if (sig === docProse.painted) return;
    docProse.painted = sig;
    docCmView.dispatch({ effects: docFindingsEffect.of(null) });
  };
  if (soon === true && !document.hidden) {
    if (!docProse.frame) docProse.frame = setTimeout(send, 16);
    return;
  }
  clearTimeout(docProse.frame);
  send();
}

//: Build the view, hand the document over to it, and take the textarea out of
//: the layout. Seeded from the fallback's own value rather than from
//: `currentDoc`, so whatever is on screen at that moment is what the engine
//: starts with, including an unsaved edit.
function mountDocEditor(CM) {
  const host = $("doc-editor");
  const box = docBoxEl();
  if (!host || !box || docCmView) return docCmView;
  const state = CM.state.EditorState.create({
    doc: box.value,
    extensions: docCmExtensions(CM),
  });
  docCmView = new CM.view.EditorView({ state, parent: host });
  docCmView.scrollDOM.addEventListener("scroll", docProseScrolled, { passive: true });
  //: The document-level pipeline, re-registered on the surface that exists
  //: now: the fallback's own `input` listener is on an element the engine has
  //: just taken out of the layout.
  cmSurface(docCmView).onChange(docSurfaceInput);
  host.classList.remove("hidden");
  $("doc-source-wrap")?.classList.add("has-cm");
  //: The column beside the textarea is not the editor's gutter any more
  //: (decision 7), so it is taken down rather than left numbering a box
  //: nobody can see.
  applyDocGutter();
  wireDocSurfaceScroll(docSurface());
  docWatchAppearance();
  docGuardGlobalShortcuts(host);
  docFoldMarkedCallouts();
  return docCmView;
}

//: Called before a document is put on screen. Resolves to the view, or to
//: null when the bundle is unavailable, in which case everything carries on
//: against the textarea.
async function ensureDocEditor() {
  if (docCmView) return docCmView;
  if (docCmBroken) return null;
  const CM = await loadCodeMirror();
  if (!CM) return null;
  try {
    return mountDocEditor(CM);
  } catch (error) {
    docCmBroken = true;
    console.warn(
      `Tessellate: the editor could not start (${error.message}). The plain editor is still available.`
    );
    return null;
  }
}

//: **The app's bare shortcuts must not eat what you are typing.**
//:
//: app.js decides "is the user typing?" with
//: `["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement.tagName)`,
//: which was exactly right while every editing surface in this app was a
//: textarea. CodeMirror's editable is a `contenteditable` div, so that check
//: says no, and every unchorded shortcut fires while you write: measured, a
//: literal "/" in a document focused the global search box and swallowed the
//: rest of the word, and the `g`-then-letter tab jumps did the same thing
//: mid-sentence. The "/" menu and the `[[` picker simply never opened,
//: because their trigger character never reached the document.
//:
//: Stopped here rather than fixed there, and the phase matters. app.js's
//: handler is on `document` in the bubble phase and was registered first, so
//: nothing on `document` can get in front of it; a capture-phase listener
//: would run before the event reached CodeMirror at all and break the
//: editor's own key handling. A bubble listener on the host is between the
//: two: the engine has already had the keystroke, the global table never
//: sees it.
//:
//: Only single printable characters with no Ctrl, Alt or Meta, which is
//: exactly the set app.js's bare-shortcut loop can match. Chorded shortcuts
//: (Ctrl+K for the palette) still work from inside the editor, deliberately,
//: and so does every key this file's own delegated handlers listen for: F8,
//: Escape, Tab and the arrows are all longer than one character.
function docGuardGlobalShortcuts(host) {
  if (!host || host.dataset.shortcutGuard === "1") return;
  host.dataset.shortcutGuard = "1";
  host.addEventListener("keydown", (event) => {
    if (event.ctrlKey || event.metaKey || event.altKey) return;
    if (event.key.length !== 1) return;
    typingBurst.at = performance.now();
    event.stopPropagation();
  });
}

//: **Light and dark, without a hook into settings.js.** The appearance code
//: writes the resolved mode onto `<html data-mode>`; watching that attribute
//: is one observer here rather than a call added over there, and it catches
//: every route into a mode change (the toggle, the settings radio, the OS
//: following "System") because all of them go through that one write.
let docAppearanceWatcher = null;

function docWatchAppearance() {
  if (docAppearanceWatcher || typeof MutationObserver !== "function") return;
  docAppearanceWatcher = new MutationObserver(() => {
    if (!docCmView || !window.CM6 || !docCmParts.theme) return;
    docCmView.dispatch({ effects: docCmParts.theme.reconfigure(docCmTheme(window.CM6)) });
  });
  docAppearanceWatcher.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["data-mode", "data-theme"],
  });
}

//: **How a file's text is drawn, in the wrap compartment** (INBOX 402):
//: prose wraps always; any other type wraps when Alt+Z (or the menu's row)
//: says so, and shows its spaces and tabs when "Show whitespace" does. Both
//: are per-viewer preferences, remembered like the other writing switches.
function docCmDrawFor(CM, type) {
  const parts = [];
  if (type.previewable || docToolPref("codeWrap", false)) parts.push(CM.view.EditorView.lineWrapping);
  if (!type.previewable && docToolPref("whitespace", false)) parts.push(CM.view.highlightWhitespace());
  return parts;
}

//: Flip one of the two, or set it: the preference, the view, the menu's
//: checkbox, in that order. Refused for prose, which has no such switch.
function docToggleCodeDraw(name, on) {
  const type = docFileType();
  if (type.previewable) return false;
  const next = on === undefined ? !docToolPref(name, false) : Boolean(on);
  docSaveToolPref(name, next);
  const CM = window.CM6;
  if (docCmView && CM && docCmParts.wrap) {
    docCmView.dispatch({ effects: docCmParts.wrap.reconfigure(docCmDrawFor(CM, type)) });
  }
  const box = $(name === "codeWrap" ? "doc-code-wrap" : "doc-whitespace");
  if (box) box.checked = next;
  return true;
}

$("doc-code-wrap")?.addEventListener("change", (event) => docToggleCodeDraw("codeWrap", event.target.checked));
$("doc-whitespace")?.addEventListener("change", (event) => docToggleCodeDraw("whitespace", event.target.checked));

//: The file type changed while the document was open: the language and the
//: wrapping follow it. Reconfigured rather than rebuilt, so the caret, the
//: scroll position and the undo history survive.
//:
//: The view is read here as well as the type, because Plain is defined as
//: "no language at all" and a file-type change while Plain is on must not
//: quietly turn the highlighting back on.
function docCmSyncFileType() {
  const CM = window.CM6;
  if (!docCmView || !CM || !docCmParts.language) return;
  const type = docFileType();
  const effects = docCmLanguageEffects(CM);
  if (docCmChanged("type", `${type.ext}|${docView === "plain"}`)) {
    effects.push(docCmParts.wrap.reconfigure(docCmDrawFor(CM, type)));
    if (docCmParts.code) effects.push(docCmParts.code.reconfigure(docCodeTools(CM)));
  }
  if (effects.length) docCmView.dispatch({ effects });
}

//: **What Plain means, in one function.** The owner: "I want to be able to
//: use the documents tab as a plain text editor like before as a view option
//: (not the defaul though)."
//:
//: "Like before" is the textarea: characters, a caret, and nothing colouring
//: or hiding any of them. Live already answers "render as I write" and Source
//: answers "show me the markdown", but Source still runs the markdown grammar,
//: so a heading is bold and a fence is tinted, which is not what "plain" is
//: asking for. Plain is the same editor with the language compartment empty:
//: no grammar, so no highlighting, no folding by syntax and no bracket
//: matching, and every other thing the editor does (undo, find, the findings,
//: the line numbers, autosave) is untouched. That is the smallest honest
//: definition, and it is one compartment rather than a fourth surface.
function docCmViewLanguage(CM) {
  if (docView === "plain") return [];
  return docCmLanguageFor(CM, docFileType().ext);
}

//: The view changed, so what the editor is allowed to highlight may have. One
//: effect, not a rebuild: the caret, the scroll position and the undo history
//: all survive a hop into Plain and back.
function docCmSyncLanguage() {
  const CM = window.CM6;
  if (!docCmView || !CM || !docCmParts.language) return;
  const effects = docCmLanguageEffects(CM);
  if (!effects.length) return;
  docCmView.dispatch({ effects });
  docCmSyncCodeTools();
}

//: **A setting the view already has is not sent again** (lagfix-1031:
//: `syncDocFileType` cost 26 to 364 ms on an open, and a CPU profile of twelve
//: opens put 213 of its 367 ms in `docCmSyncFileType`, in CodeMirror reading the
//: DOM selection after the dispatch). Every reconfigure is a transaction, so
//: `setDocView`, `docCmSyncFileType` and `docCmApplySpellcheck` each sent
//: theirs on every open, and opening a second Markdown file paid for changes
//: that changed nothing. Each is a pure function of the view and a small key
//: (extension and Plain, or the spellcheck answer), so that pair is the memo:
//: a new view (the engine remounted) never matches the old one.
const docCmApplied = new Map();
function docCmChanged(name, key) {
  const last = docCmApplied.get(name);
  if (last && last.view === docCmView && last.key === key) return false;
  docCmApplied.set(name, { view: docCmView, key });
  return true;
}

function docCmLanguageEffects(CM) {
  if (!docCmChanged("language", docView === "plain" ? "plain" : docFileType().ext)) return [];
  return [docCmParts.language.reconfigure(docCmViewLanguage(CM))];
}

//: The line-number preference, applied to the engine. `applyDocGutter` still
//: owns the *decision* (and the two note editors' own columns); this is only
//: how it reaches the view.
//: The one reading of the line-number preference that both the gutter itself
//: and the decorations that have to dodge it go through, so the two cannot
//: disagree about whether there are numbers on screen.
function docFenceGutterOn() {
  return docGutterWanted(!docFileType().previewable);
}

function docCmSyncGutter() {
  const CM = window.CM6;
  if (!docCmView || !CM || !docCmParts.gutter) return;
  if (docCmPartIs(docCmParts.gutter, docFenceGutterOn())) return;
  docCmView.dispatch({ effects: docCmParts.gutter.reconfigure(docCmGutter(CM)) });
}

//: **The gutter: numbers and folding, together, because they share a lane.**
//:
//: Decision 7 puts folding behind the same preference the line numbers are
//: behind, and that is not an arbitrary pairing: a fold arrow needs a column
//: to live in, and a column of arrows beside prose that has no numbers in it
//: is a strip of chevrons with nothing to anchor them. One choice, one lane,
//: `applyDocGutter` still owns the decision.
function docCmGutter(CM) {
  if (!docFenceGutterOn()) return [];
  //: **Only the gutter is in the gutter.** Folding itself moved into the base
  //: extensions when callouts became foldable (Phase 3 item 2): every fold
  //: this editor offers lived in here, so a markdown document, which opens
  //: with the line numbers off, had no folding at all and a callout's toggle
  //: would have been a chevron that did nothing. The arrow in the margin is a
  //: gutter control and stays; what it operates is not.
  //: **The arrow is an icon, not a character** (the owner, 2026-09-21: "make
  //: these dropdown arrows actually aligned and proper icons"). CodeMirror's
  //: `foldGutter` draws a text triangle by default, which rendered as a typed
  //: "v" in this app's font: the exact shape `tests/test_no_glyph_icons.py`
  //: exists to keep out, sitting beside a column of numbers it could not line
  //: up with because a glyph's box is its font's business, not the line's.
  //: `markerDOM` hands it the app's own caret instead, and the rule for
  //: `.cm-foldGutter` below gives the lane a box the size of a line so the
  //: arrow sits on the text it folds rather than near it.
  const markerDOM = (open) => {
    const icon = document.createElement("i");
    icon.className = `ph ph-caret-${open ? "down" : "right"} cm-fold-caret`;
    icon.setAttribute("aria-hidden", "true");
    return icon;
  };
  return [CM.view.lineNumbers(), CM.view.highlightActiveLineGutter(), CM.view.highlightActiveLine(), CM.language.foldGutter({ markerDOM })];
}

//: **Copy and cut with nothing selected take the whole line, as VS Code
//: does** (INBOX 652, the owner: "whole line copying or cutting ... quality
//: of life stuff"). CodeMirror already does the same inside the view (a
//: linewise copy is remembered and a paste of it goes above the current
//: line), measured on :8797 with `scratchpad/ui-sweeps/linecopy.js`; what
//: differed from VS Code was the clipboard text, `bravo` where VS Code puts
//: `bravo\n`, so pasting into any other app joined the line onto whatever
//: sat at the caret, and cutting the last line left an empty one behind.
//: This handler writes the line with its newline, remembers that text, and
//: pastes it as a whole line above the caret's own. One caret only: with
//: several, or any selection, CodeMirror's own behaviour is untouched.
const DOC_LINE_CLIP = { text: null };

function docLineClipboardRange(state) {
  const sel = state.selection;
  if (sel.ranges.length !== 1 || !sel.main.empty) return null;
  const line = state.doc.lineAt(sel.main.head);
  //: The last line has no newline after it, so cutting it takes the one
  //: before, which leaves the caret on the line above like VS Code.
  const last = line.to >= state.doc.length;
  const from = last && line.from > 0 ? line.from - 1 : line.from;
  const to = last ? line.to : line.to + 1;
  return { text: `${line.text}\n`, from, to };
}

function docLineClipboardEvent(event, view) {
  const hit = docLineClipboardRange(view.state);
  const data = event.clipboardData;
  if (!hit || !data) return false;
  data.clearData();
  data.setData("text/plain", hit.text);
  DOC_LINE_CLIP.text = hit.text;
  if (event.type === "cut" && !view.state.readOnly) {
    view.dispatch({ changes: { from: hit.from, to: hit.to }, scrollIntoView: true, userEvent: "delete.cut" });
  }
  return true;
}

function docLinePasteEvent(event, view) {
  const text = event.clipboardData?.getData("text/plain");
  const sel = view.state.selection;
  if (!DOC_LINE_CLIP.text || text !== DOC_LINE_CLIP.text || sel.ranges.length !== 1 || !sel.main.empty || view.state.readOnly) return false;
  const line = view.state.doc.lineAt(sel.main.head);
  view.dispatch({
    changes: { from: line.from, insert: text },
    selection: { anchor: sel.main.head + text.length },
    scrollIntoView: true,
    userEvent: "input.paste",
  });
  return true;
}

function docLineClipboardExtension(CM) {
  return CM.view.EditorView.domEventHandlers({
    copy: docLineClipboardEvent,
    cut: docLineClipboardEvent,
    paste: docLinePasteEvent,
  });
}

//: **A note box's numbers are the view's own** (INBOX 590). The capture box
//: and the note edit form used to number the editor from outside, with the
//: `.doc-gutter` column beside it copying the *hidden* textarea's metrics: a
//: 16px "1" beside 14.72px text, one number per hard line however many rows a
//: wrapped line took. `lineNumbers()` inside the view draws one number per
//: line at that line's own height, wrapped or not, the same column the
//: documents editor has; the outside column stays for the textarea before
//: the editor mounts (`.gutter-wrap:has(.cm-editor)` hides it after).
function noteSurfaceGutter(CM, host) {
  if (!host.closest?.(".gutter-wrap") || docGutterPref() !== "1") return [];
  return [CM.view.lineNumbers(), CM.view.highlightActiveLineGutter(), CM.view.highlightActiveLine()];
}
