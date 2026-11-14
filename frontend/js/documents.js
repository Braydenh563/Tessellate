// documents.js: the document editor (split out of app.js).
//
// Loaded after app.js (see index.html's <script> ordering comment): every
// reference here into app.js globals (docs helpers aside, things like
// switchTab, apiJson, toast, $, promptDialog, setPreference) is a runtime
// call inside a function body, never a parse-time reference, so load order
// only matters for the reverse direction, anything in app.js that calls
// into documents.js (loadDocuments, renderDocStorage, createDocument) does
// so from inside its own functions too, which by the time they run have
// always already had this script loaded (same DOMContentLoaded pass, no
// user interaction possible in between).
//
// initDocSidebarTabs() used to be called from app.js's own top-level wiring
// (right after initNotesSubtabs()). That call site is gone from app.js now
// that the function moved here, this file calls it itself instead, at the
// end, so it still runs exactly once per load and in the same relative
// order (after app.js's synchronous top-level code, before any user input
// is possible).

// --- documents: long-form writing -----------------------------------------------
// Documents are separate from notes on purpose. A note is a captured thought;
// a document is something you sit down and write. Sharing storage would put
// every half-finished draft into note search and the graph.


//: The `docOpenSeq` the tab's loader last settled at. Anything asked since,
//: including before the loader started, is an open the loader must not
//: override with the last document (DC7).
const docLoadSeen = { seq: 0 };

// --- which of the four views is showing ----------------------------------------
//
// "source" (the plain textarea), "live" (render-as-you-write), "split" (source
// beside a rendered pane) or "rendered" (the finished document alone, no
// editor). Per-device workspace state rather than a preference on the document:
// which way you like to look at your writing does not belong in a backup, and
// is the same kind of thing as `graph-layout`.
//
// "rendered" is deliberately a peer of "split" rather than a sub-state of it.
// Asked for as a "full toggle switch between editor mode and rendered mode *or*
// the split view", i.e. reading the finished page at full width is its own
// thing, not split-with-one-pane-collapsed.
const DOC_VIEW_KEY = "doc-view-mode";
//: `plain` is the owner's ask of 2026-09-09: "I want to be able to use the
//: documents tab as a plain text editor like before as a view option (not the
//: defaul though)". It is Source with the language compartment empty, so it
//: has no grammar and therefore no highlighting; see `docCmViewLanguage`.
const DOC_VIEWS = ["source", "live", "split", "rendered", "plain"];
//: The two ways of editing that need no rendered form, so the two a `.py`
//: file may be in. Named once, because three separate places used to spell it
//: out as `!== "source"` and Plain would have been refused by all three.
const DOC_VIEWS_UNRENDERED = ["source", "plain"];
//: True while Source is on screen only because the open file is code (INBOX
//: 904 B21/B22: a code file's forced Source was written to the stored view,
//: so every markdown document after it opened in Source, and a document
//: switched back from `.py` to `.md` stayed there). Nothing stored, nothing
//: remembered as the last editing view; the file type coming back to a
//: markdown one restores the view the person actually chose.
//: `allows(type, mode)`: a markdown document may be in any view, a code file in the two that
//: need no rendered form, and a diagram (the `mmd` type, 1546 D5) also in Blocks (the Read
//: button's mode) and Split, where the block pane is the preview. `type` is the last file type
//: synced, so a diagram opens in Blocks.
const docViewState = {
  held: false,
  //: A diagram's rendered view has two layouts, Canvas (the default) and Blocks (R7, 1621 D6).
  layout: "canvas",
  tableGrips: null,
  blockHandle: null,
  type: "md",
  allows: (type, mode) => type.previewable || DOC_VIEWS_UNRENDERED.includes(mode) || (type.ext === "mmd" && ["split", "rendered", "canvas", "blocks"].includes(mode)),
};

//: **The filter row and the formula letters** (DOCUMENTS_PLAN gap row 12). A
//: filter is a view of the table, never an edit: it lives in `docViewState`
//: under the header's text (a table has no id in markdown, and the header is
//: what a person calls it), hides body rows in Live only, and is gone with the
//: page. `docViewState.tableFilter.set` repaints by re-sending the selection, which the
//: table decoration always rebuilds on.
docViewState.tableFilter = {
  key: (table) => table.rows[0].cells.map((cell) => cell.trim()).join("|"),
  of(table) {
    const filter = docViewState.tableFilters && docViewState.tableFilters[this.key(table)];
    return filter && filter.needle ? filter : null;
  },
  set(view, table, filter) {
    docViewState.tableFilters = docViewState.tableFilters || {};
    const key = this.key(table);
    if (filter && filter.needle) docViewState.tableFilters[key] = filter;
    else delete docViewState.tableFilters[key];
    if (view) view.dispatch({ selection: view.state.selection });
  },
  letters(col) {
    let letters = "";
    for (let n = col + 1; n > 0; n = Math.floor((n - 1) / 26)) letters = String.fromCharCode(65 + ((n - 1) % 26)) + letters;
    return letters;
  },
  async ask(context) {
    const column = (context.table.rows[0].cells[context.cell.col] || "").trim() || `column ${this.letters(context.cell.col)}`;
    const was = this.of(context.table);
    const needle = await promptDialog(`Show rows where ${column} contains`, was ? was.needle : "", { confirmLabel: "Filter" });
    if (needle !== null && needle !== undefined) {
      this.set(context.surface.view, context.table, { col: context.cell.col, needle: needle.trim() });
    }
    context.surface.focus();
  },
};

//: One-time reset (owner, 2026-10-25: Live should be the default, but their
//: browser held "source" from before). A view stored before this version key
//: existed is dropped once, so Live shows; every choice made afterwards is
//: kept, because the key is written in the same breath.
const DOC_VIEW_VERSION_KEY = "doc-view-mode-v";
const DOC_VIEW_VERSION = "2";
function docViewMigrate() {
  if (prefs.has(DOC_VIEW_VERSION_KEY)) return;
  prefs.remove(DOC_VIEW_KEY);
  prefs.set(DOC_VIEW_VERSION_KEY, DOC_VIEW_VERSION);
}

//: The view a markdown document opens in when it is not holding one: the
//: stored choice, else Live (Rendered on a phone, Phase 11 item 6).
function docDefaultView() {
  let stored = null;
  try {
    docViewMigrate();
    stored = prefs.get(DOC_VIEW_KEY, null);
  } catch {
    stored = null;
  }
  return stored || (window.matchMedia("(max-width: 599.98px)").matches ? "rendered" : "live");
}

// The two modes that put #doc-preview on screen. Kept as one predicate because
// every "is the rendered pane showing?" decision below has to agree with every
// other one: the split/rendered pair is exactly the shape that goes wrong when
// each site spells the check out for itself.
function docPreviewShowing(mode = docView) {
  return mode === "split" || mode === "rendered";
}


// =============================================================================
// Backlinks with context, and unlinked mentions (DOCUMENTS_PLAN Phase 4 item 1)
// =============================================================================
//
// What links *here*. The panel used to be a list of titles, which reads as a
// lookup: you learn that a connection exists and nothing about what it says.
// Two things turn it into knowledge, and they are the two Obsidian and Kortex
// both have: the sentence the link sits in, and the mentions that are not
// links yet.
//
// **The scan is the server's** (`GET /documents/{id}/backlinks`). The browser
// holds every note but no other document's *content*: the documents list
// deliberately carries a preview and not the text, because a document runs to
// thousands of words. A client-side scan would therefore have found note
// backlinks and silently missed every document one, which is the half-built
// shape this plan exists to stop. The endpoint's own reasoning is in
// routes_documents.py; what is here is the panel and the two actions.


//: **A new document needs no name** (INBOX 739, the owner: "auto naming of
//: the whiteboards, mindmaps and documents like \"untitled #\" so the user
//: isnt forced to name a new object"). The next free number after every
//: "Untitled document N" there is, as `wbUntitledNames` does for boards and
//: maps, so a deleted one's number is not reused while a higher one exists.


// A note that outgrew itself becomes a document. Notes and documents were
// two islands: the only way across was copy and paste, which loses the link
// between them. The note is deliberately left alone, this is a promotion,
// not a move, and quietly deleting someone's note to "convert" it is the
// kind of helpfulness nobody asks for twice.
async function expandNoteIntoDocument(entry) {
  //: Several notes (a graph cluster or its selection) compose into one draft,
  //: a section each, on the server; one note keeps the path below.
  if (Array.isArray(entry)) {
    try {
      const doc = await apiJson("/documents/from-notes", { method: "POST", body: JSON.stringify({ note_ids: entry }) });
      offerCreateUndo(doc);
      switchTab("documents");
      await loadDocuments(doc.id);
      toast(`Started a draft from ${nounCount(entry.length, "note")}, the notes themselves are untouched.`);
    } catch (error) {
      toast(error.message, true);
    }
    return;
  }
  const text = entry.content || "";
  // The first line makes a reasonable title; the rest is the body.
  const [firstLine, ...rest] = text.split("\n");
  const title = (firstLine || "Untitled").replace(/^#+\s*/, "").slice(0, 120).trim();
  const body = rest.join("\n").trim() || text;
  try {
    const doc = await apiJson("/documents", {
      method: "POST",
      body: JSON.stringify({
        title: title || "Untitled",
        // A line back to where it came from, so the pair stay findable.
        content: `${body}\n\n---\n\nExpanded from note #${entry.id}.\n`,
      }),
    });
    offerCreateUndo(doc);
    switchTab("documents");
    await loadDocuments(doc.id);
    toast(`Started a document from this note, the note itself is untouched.`);
  } catch (error) {
    toast(error.message, true);
  }
}

// Words and reading time. Both are cheap to compute and are the two numbers
// anyone writing long-form actually wants on screen.


// --- find and replace: the editor's own search panel (DC10) ----------------
// The textarea fallback's hand-built find bar is gone (it only ever showed
// when CodeMirror failed to load, and a failed load has bigger problems):
// Ctrl+F, the toolbar button and Escape reach CodeMirror's panel, which marks
// every match, takes regular expressions and replaces as one undo step.
function docOpenReplace() {
  toggleDocFindBar(true);
  docCmView?.dom.querySelector(".cm-search input[name=replace]")?.focus();
  return true;
}

function toggleDocFindBar(open) {
  //: **CodeMirror's own search panel** (DOCUMENTS_PLAN Phase 2 decision 7): it
  //: searches the *document* through the editor's own index, highlights every
  //: match at once, knows about regular expressions and whole-word matching,
  //: and replaces through transactions so one Ctrl+Z undoes a Replace all.
  //: One entry point, so Ctrl+F, the toolbar button and Escape all reach it.
  //: With no engine (the textarea fallback after a failed load) the app's
  //: find over the page is the answer: it reads the text the page holds.
  const CM = window.CM6;
  if (!docCmView || !CM) {
    if (open !== false) openGlobalFind();
    return;
  }
  const open_ = open ?? !docCmView.dom.querySelector(".cm-search");
  if (open_) CM.search.openSearchPanel(docCmView);
  else CM.search.closeSearchPanel(docCmView);
  $("doc-find-toggle")?.setAttribute("aria-expanded", String(open_));
  if (!open_) docCmView.focus();
}


// =============================================================================
// The editor's own commands: one table, two doors (DOCUMENTS_PLAN Phase 4 item 4)
// =============================================================================
//
// The plan calls this "the single biggest fix for features that do not show
// themselves", and it asks for two things: a palette listing every editor
// action with its shortcut, and a `?` shortcut sheet "generated from the same
// table so the two cannot disagree". This is that table.
//
// **The decision the plan had not made, taken here because it had to be.** The
// plan names `Ctrl+K`, written before this app had a command palette of its
// own on exactly that chord (`openPalette`, app.js). Two palettes on one key
// is the collision the agent palette's own comment already records being
// caught twice. So the editor's commands *join* the palette the app has, in a
// group of their own, offered only while a document is actually open and on
// screen; the chord stays where every other surface's commands already live.
// A reader who presses Ctrl+K in a document now finds the document's own
// actions at the top of the list they already know, rather than a second list
// they have to learn.
//
// **A row whose action already has a button runs the button.** Not a copy of
// its handler: a copy is a second definition of what "Export as HTML" means,
// and the two drift the first time one is edited. The table carries the
// control's id and the run is a click, which is also why every one of these
// is reachable at all: a command that pointed at a function the dock no
// longer calls would look right here and do nothing.
//
// The table itself is in documents-commands.js, bracketed by `DOC-COMMANDS-BEGIN`/`END` so
// `tests/test_doc_commands.py` can read its shape without a browser.
//
// **Every row says its chord or "none"** (DOCUMENTS_PLAN section 25 row 6):
// an empty `keys` was a row nobody had decided about. "none" is a decision
// (no free chord that means it anywhere else, or a chord the app gives to
// something else), and the palette and the sheet show nothing for it.

//: Pressing a control that is in a closed `<details>` menu still works (the
//: browser dispatches to a hidden element quite happily), but a control that
//: is not in the document at all is a command that silently does nothing, so
//: it says so instead.
function docRunControl(id, what) {
  const el = $(id);
  if (!el) {
    toast(`${what} is not available here.`, "info");
    return;
  }
  el.click();
}

//: The icon for a `:ph-name:`, or null when the font has no such name: it stays
//: text (INBOX 1545). Asked of the font's own stylesheet, once per name; a sheet
//: not there or unreadable lets every name through, as before. Reading view
//: (through `appendPlainText`, hook-only so notes-list.js stays small) and Live
//: (documents-cm.js) both come here.
appendPlainText.icon = (name) => {
  const known = (appendPlainText.known ||= {});
  if (known[name] === undefined) {
    const sheet = [...document.styleSheets].find((s) => /\/phosphor\//.test(s.href));
    try {
      known[name] = !sheet || [...sheet.cssRules].some((r) => r.selectorText === `.ph.ph-${name}::before`);
    } catch {
      known[name] = true;
    }
  }
  return !known[name] ? null : Object.assign(document.createElement("i"), { className: `ph ph-${name} md-inline-icon`, role: "img", ariaLabel: name.replace(/-/g, " ") });
};


try {
  //: **Live is the default now.** Asked for: "I want the text editor to be
  //: EXACTLY LIKE OBSIDIAN. the user would bold a wor, click off it, and the
  //: word shows as bolded", which is what this mode does, and has done for a
  //: while; it was simply not the view anybody landed in, so the editor read
  //: as a plain markdown box with a preview button. Obsidian's own default is
  //: Live Preview for the same reason. A stored choice still wins, so nobody
  //: who picked Source is moved off it.
  //: **A phone opens a document to read it** (UI_MODERNISATION_PLAN Phase
  //: 11 item 6). Nothing stored means the width decides: Rendered below 600,
  //: Live Preview above, and a stored choice still wins at every width.
  setDocView(docDefaultView());
} catch {
  setDocView("source");
}
//: Escape leaves it: the same convention the whiteboard's and graph's own
//: full-screen toggles use, and asked the way the graph's is (see INBOX 275
//: at that handler): bubble phase, so an Escape the editor spends first
//: (closing a completion list or the slash menu, collapsing a selection)
//: arrives here already `defaultPrevented`; and never while a dialog or a
//: menu is open over the page, whose Escape it is. The earlier listener was
//: capture phase and so left focus mode underneath an open slash menu.
document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape" || event.defaultPrevented) return;
  if (!docFocusOn()) return;
  if (activeOverlay()) return;
  const menuOpen = [...document.querySelectorAll('[role="menu"], .cm-tooltip')]
    .some((el) => el.getClientRects().length > 0);
  if (menuOpen) return;
  if (event.target instanceof Element && event.target.closest("#doc-prose-panel, .cm-search, .cm-goto-line")) return;
  //: The sidebar panel is the innermost layer, so it takes the first Escape
  //: and the mode leaves on the next. The focus goes to its toggle only when
  //: it was inside the panel, which is about to stop being drawn.
  const tab = $("tab-documents");
  if (tab?.classList.contains("doc-focus-sidebar")) {
    const inside = event.target instanceof Element && !!event.target.closest("#doc-sidebar");
    setDocFocusSidebar(false);
    if (inside) $("doc-focus-sidebar")?.focus();
    return;
  }
  toggleDocFocus(false);
});
//: F11, the key that means "full screen" in every browser and in Word, only
//: while a document is on screen; everywhere else it is left to the browser.
//: In the editor's command table (`DOC_COMMANDS`, "focus"), which is what
//: puts it in the shortcut sheet and the palette.
document.addEventListener("keydown", (event) => {
  if (event.key !== "F11" || event.ctrlKey || event.metaKey || event.altKey || event.shiftKey) return;
  const tab = $("tab-documents");
  if (!tab || tab.classList.contains("hidden")) return;
  //: While a debug session is on, F11 is Step into (Brief 70), as in VS Code.
  if (docDebugOn()) return;
  event.preventDefault();
  toggleDocFocus();
});
docBoxEl().addEventListener("keydown", (event) => {
  // The fallback textarea's half of the Escape-then-Tab hatch, the same rule
  // the engine's keymap states (`docTabEscapes`), because which of the two
  // surfaces is mounted is not something a writer knows or should have to.
  if (event.key === "Escape") docTabEscapes = true;
  else if (event.key !== "Tab" && event.key !== "Shift") docTabEscapes = false;
  // Tab indents rather than leaving the field, in prose as well as in code.
  // An Escape immediately before it hands the key back to the browser, which
  // is the way out; `docTabEscapes` carries the whole reasoning.
  if (event.key === "Tab" && !event.shiftKey) {
    if (docTakeTabEscape()) return;
    event.preventDefault();
    indentDocSelection(docSurface(), false);
    return;
  }
  if (event.key === "Tab" && event.shiftKey) {
    if (docTakeTabEscape()) return;
    const box = docSurface();
    // Shift+Tab dedents when there is something to dedent, and otherwise
    // falls through to the browser's own focus-backwards: so a flush-left
    // caret is not a keyboard trap even for someone who never learns the
    // Escape chord.
    if (docCanOutdent(box)) {
      event.preventDefault();
      indentDocSelection(box, true);
      return;
    }
  }
  if (!(event.ctrlKey || event.metaKey)) return;
  // Ctrl+/ (and Ctrl+' on the layouts where / needs a modifier of its own).
  if (event.key === "/" || event.key === "?") {
    event.preventDefault();
    toggleDocComment(docSurface());
    return;
  }
  const key = event.key.toLowerCase();
  // Checked before the plain Ctrl+S save case: Shift turns "s" into "S",
  // which `.toLowerCase()` folds back to the same "s" this switch reads, so
  // whichever branch runs first wins and the shifted chord has to come
  // first, or it would save the document instead of striking the selection.
  if (key === "s" && event.shiftKey) { event.preventDefault(); wrapDocSelection("~~", "struck through"); }
  else if (key === "s") { event.preventDefault(); saveDocument(); }
  else if (key === "b") { event.preventDefault(); wrapDocSelection("**", "bold text"); }
  else if (key === "i") { event.preventDefault(); wrapDocSelection("*", "italic text"); }
  // Ctrl+1/2/3 headings and Ctrl+E inline code, the Notion / Typora /
  // Word set, so the hand does not leave the keyboard for the strip.
  else if (key === "1" || key === "2" || key === "3") { event.preventDefault(); applyMarkdown(`h${key}`); }
  else if (event.altKey && /^Digit[1-6]$/.test(event.code)) { event.preventDefault(); applyMarkdown(`h${event.code.slice(-1)}`); }
  else if (key === "k" && docCmKeymap.link(docSurface())) event.preventDefault();
  else if (key === "e") { event.preventDefault(); wrapDocSelection("`"); }
  // The browser's own Ctrl+F can't search a textarea's content at all, it
  // only sees page DOM text, and a textarea's text is its *value*, not DOM
  // text: so this isn't overriding useful native behaviour here.
  else if (key === "f") { event.preventDefault(); toggleDocFindBar(true); }
});
$("doc-find-toggle").addEventListener("click", () => toggleDocFindBar());
$("doc-replace-everywhere").addEventListener("click", () => openDocReplace());

docListen("input", (event) => {
  //: CodeMirror raises its own `input` on the contenteditable *and* tells us
  //: through the update listener, and the update listener is the one that
  //: also sees scripted changes. Running both would do every pass twice.
  if (docEventFromCm(event.target)) return;
  const box = docToolsBoxFor(event.target);
  if (!box) return;
  //: Autocorrect first, because it edits the value the rest of this then
  //: measures: running the counts before it would show the pre-correction
  //: text for one frame.
  if (event.inputType === "insertText" || event.inputType === "insertLineBreak") {
    docAutocorrectAt(box);
  }
  docToolsOnInput(box);
});
docListen("keydown", (event) => {
  const box = docToolsBoxFor(event.target);
  if (!box) return;
  //: Before anything else this editor binds: Tab and the arrows mean the
  //: popup while it is open, and mean their usual thing the instant it is not.
  if (docCompleteKeydown(event, box)) { event.stopPropagation(); return; }
  if (event.key === "Tab" && !event.ctrlKey && !event.altKey && docTableTab(event, box)) {
    event.stopPropagation();
  }
}, true);
//: `selectionchange` is the only event that fires for a caret moved by the
//: keyboard, the mouse *and* by script, a `keyup`/`click` pair misses the
//: third, which is how a status bar drifts out of step with the caret it is
//: describing.
docListen("selectionchange", () => {
  if (!docToolsBoxFor(document.activeElement)) return;
  //: The engine's own update draws it for a caret in the view (`docCmUpdate`),
  //: so this was a second pass per key there (DX1).
  if (docEventFromCm(document.activeElement)) return;
  renderDocCaret();
});
docListen("focusout", (event) => {
  //: Only when focus is leaving the editor entirely: moving from one live-view
  //: block to the next must not close a popup that is about to be reopened.
  if (!docToolsBoxFor(event.target)) return;
  setTimeout(() => {
    if (!docToolsBoxFor(document.activeElement)) hideDocComplete();
  }, 0);
});
docListen(
  "mousedown",
  (event) => {
    if (!docCmView || event.detail !== 1 || event.button !== 0) return;
    if (!(event.target instanceof Node) || !docCmView.contentDOM.contains(event.target)) return;
    const pos = docCmView.posAtCoords({ x: event.clientX, y: event.clientY });
    docFirstPress = pos == null ? null : { pos, at: performance.now() };
  },
  true
);
docListen("dblclick", (event) => {
  const box = docToolsBoxFor(event.target);
  const pressed = docFirstPress && performance.now() - docFirstPress.at < 1000 ? docFirstPress.pos : null;
  if (box) docOpenSuggestAtCaret(box, { x: event.clientX, y: event.clientY }, true, pressed);
});
//: **One click on an underlined word, which is what an underline means
//: everywhere else.** DOCUMENTS_PLAN Phase 0 item 2, and the instruction it
//: comes from: "if something gets underlined, I want to be able to click on
//: that and see suggestions". Double-click and right-click both still work,
//: unchanged; this is the gesture nobody had to be told about.
//:
//: Two details decide whether this is helpful or infuriating:
//:
//:   * **The caret has not moved yet.** The click that opens this menu is the
//:     same click that places the caret, and `selectionStart` still holds the
//:     old position while the event is being dispatched. Read on the next
//:     frame, so the offset is the one the person just clicked.
//:   * **It does not take the focus.** A double-click or a right-click is a
//:     request for the menu, so those move focus into it; a plain click is
//:     usually someone putting the caret in a word to fix it by hand, and
//:     stealing focus would send their next keystrokes to a button. The menu
//:     opens beside the word and the caret stays where they put it, so typing
//:     just carries on and the menu closes on the next edit.
docListen("click", (event) => {
  if (event.detail > 1 || event.altKey || event.ctrlKey || event.metaKey) return;
  const box = docToolsBoxFor(event.target);
  if (!box) return;
  const point = { x: event.clientX, y: event.clientY };
  requestAnimationFrame(() => {
    //: A drag that selected something is not a click on a word.
    if (box.selectionStart !== box.selectionEnd) return;
    const finding = docFindingAtPoint(point.x, point.y) || docFindingAtOffset(docOffsetOf(box) ?? -1);
    if (!finding) return;
    //: Already open on this one (a double-click's first click got here first).
    if (docSuggestOpenFor === finding) return;
    docOpenSuggestFor(finding, false, point);
  });
});
//: Anywhere else closes it, the rule every menu in this app follows.
document.addEventListener("mousedown", (event) => {
  const menu = $("doc-suggest-menu");
  if (!menu || menu.classList.contains("hidden")) return;
  if (!menu.contains(event.target)) closeDocSuggest();
});
document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape") return;
  if (!$("doc-suggest-menu")?.classList.contains("hidden")) closeDocSuggest();
});
document.addEventListener("keydown", (event) => {
  const box = docFindingKeyBox(event.target);
  if (!box) return;
  if (event.key === "Enter" && event.altKey) {
    const offset = docOffsetOf(box);
    const finding = offset === null ? null : docFindingAtOffset(offset);
    if (!finding) return;
    event.preventDefault();
    docOpenSuggestFor(finding, true);
    return;
  }
  if (event.key !== "F8") return;
  if (!docProseFound.length) return;
  event.preventDefault();
  docGoToFinding(docFindingStep(box, event.shiftKey));
});
//: An edit moves every offset after it, so the menu that is open is about a
//: span that may no longer be there. Closed rather than refreshed: the person
//: has started typing, which is an answer to the suggestion.
docListen("input", (event) => {
  if (!docToolsBoxFor(event.target)) return;
  if (!$("doc-suggest-menu")?.classList.contains("hidden")) closeDocSuggest();
});


//: **The menu that changes a callout from where it is drawn** (INBOX 421 b).
//: One list for both places a rendered callout offers it (the icon in the
//: Live view, the block bar in the Read view), so the two cannot offer
//: different kinds. `apply(kind, fold)` writes the change; the rows are the
//: app's own menu rows (`kebabMenu` groups), with the current kind and fold
//: marked by a check glyph rather than by colour alone.
function calloutMenuItems(current, fold, apply) {
  const items = [];
  for (const [kind, meta] of Object.entries(CALLOUT_KINDS)) {
    items.push({
      group: "Kind",
      label: `${kind === current ? "ph:check" : meta.icon} ${meta.label}`,
      title: meta.about,
      run: () => apply(kind, fold),
    });
  }
  const folds = [
    ["", "ph:rows", "Always open"],
    ["-", "ph:caret-right", "Folded until clicked"],
    ["+", "ph:caret-down", "Foldable, starts open"],
  ];
  for (const [flag, icon, label] of folds) {
    items.push({
      group: "Folding",
      label: `${flag === fold ? "ph:check" : icon} ${label}`,
      title: label,
      run: () => apply(current, flag),
    });
  }
  return items;
}

