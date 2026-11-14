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


let docs = [];
let currentDoc = null;   // {id, title, content, ...}
let docDirty = false;
//: Which `openDocument` call is the newest (see there).
let docOpenSeq = 0;
//: The `docOpenSeq` the tab's loader last settled at. Anything asked since,
//: including before the loader started, is an open the loader must not
//: override with the last document (DC7).
const docLoadSeen = { seq: 0 };
let docSaveTimer = null;

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
let docView = "source";
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

//: The editing mode the Edit button returns to after Read (DOCUMENTS_PLAN
//: Phase 1 item 2): Live, Source or Split, whichever was last in use.
let lastEditView = "live";

//: The CodeMirror view once it exists, null before the bundle has loaded and
//: null for good if it fails to. Read by `docSurface()` on every call, so the
//: hand-over is one assignment rather than a re-wiring pass.
let docCmView = null;
//: The empty-document prompt, kept here because the two engines spell it
//: differently: a textarea has a `placeholder` attribute, CodeMirror has a
//: placeholder extension that is built from this when the view is created.
let docPlaceholderText = "";

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


//: **Choosing is not making** (INBOX 410, the owner: "when selecting a
//: template, I want to be able to confirm my template selection, not have it
//: instantly be made when I press it"). A row is a radio: a click chooses it
//: and the preview shows the page it would make; the dialog's one filled
//: button (Use this template), Enter on the list, or a double click makes it.
//: The arrows walk the rows, and the first row is chosen when the dialog
//: opens, so one Enter still makes a page the way one Enter did before. The
//: preview follows the choice and not the pointer: a pane showing the row
//: under the mouse while the button below would make the row that was
//: clicked is two answers to "what will I get". The choice lives here, not
//: on a row, so the Use button (wired once, beside the other document
//: controls) can read it.
let docTemplateMade = false;


function docTemplateListKeys(event) {
  const rows = [...event.currentTarget.querySelectorAll(".doc-template-choice")];
  if (!rows.length) return;
  const index = rows.findIndex((row) => row.getAttribute("aria-checked") === "true");
  const step = { ArrowDown: 1, ArrowRight: 1, ArrowUp: -1, ArrowLeft: -1 }[event.key];
  let next = null;
  if (step) next = rows[(index + step + rows.length) % rows.length];
  else if (event.key === "Home") next = rows[0];
  else if (event.key === "End") next = rows[rows.length - 1];
  if (next) {
    event.preventDefault();
    chooseDocTemplate(DOC_TEMPLATES.find((t) => t.id === next.dataset.template), { focus: true });
  } else if (event.key === "Enter") {
    //: Enter on a focused button would fire its click, which only chooses;
    //: on this list Enter is the confirmation, as it is on a form.
    event.preventDefault();
    useDocTemplate();
  }
}

function openDocTemplateDialog() {
  const dialog = $("doc-template-dialog");
  const list = $("doc-template-list");
  if (!dialog || !list) return;
  docTemplateMade = false;
  list.replaceChildren();
  //: Writing, Planning, then Code (INBOX 788, DX30): a heading row where the group
  //: changes, not a second list, so the arrows still walk every row.
  let group = "";
  for (const template of DOC_TEMPLATES) {
    if ((template.group || "writing") !== group) {
      group = template.group || "writing";
      const head = document.createElement("li");
      head.setAttribute("role", "presentation");
      head.className = "doc-template-group muted text-xs";
      head.textContent = { code: "Code", planning: "Planning" }[group] || "Writing";
      list.appendChild(head);
    }
    const li = document.createElement("li");
    li.setAttribute("role", "presentation");
    const button = document.createElement("button");
    button.type = "button";
    button.className = "ghost doc-template-choice";
    button.setAttribute("role", "radio");
    button.setAttribute("aria-checked", "false");
    button.dataset.template = template.id;
    const name = document.createElement("strong");
    name.textContent = template.title;
    const hint = document.createElement("span");
    hint.className = "muted text-sm";
    hint.textContent = template.hint;
    //: The chosen row's check, the mark every menu in the app uses for
    //: "in effect": the fill alone would be colour alone.
    const check = document.createElement("i");
    check.className = "ph ph-check doc-template-check";
    check.setAttribute("aria-hidden", "true");
    button.append(name, hint, check);
    button.addEventListener("click", () => chooseDocTemplate(template));
    button.addEventListener("dblclick", useDocTemplate);
    li.appendChild(button);
    list.appendChild(li);
  }
  dialog.showModal();
  chooseDocTemplate(DOC_TEMPLATES[0], { focus: true });
}

//: **The page a template makes, before it is made** (DOCUMENTS_PLAN Phase 4:
//: templates "offered with a preview"). The gallery offered a sentence per
//: row ("Brief, criteria, sections, sources, timeline."), which says what a
//: template is about and not what it looks like. This is the filled body,
//: through the same `docTemplateFill` the button uses and the same
//: `renderMarkdown` the document's own preview uses, shrunk to a page in the
//: dialog's second column, so what is shown is exactly what would be created.
function showDocTemplatePreview(template) {
  const pane = $("doc-template-preview");
  if (!pane || !template) return;
  if (pane.dataset.template === template.id) return;
  pane.dataset.template = template.id;
  const page = document.createElement("div");
  page.className = "doc-template-page md";
  const filled = docTemplateFill(template);
  if (filled.content) {
    //: A code template previews as the code it makes, not as prose.
    renderMarkdown(page, template.fileType ? `\`\`\`${template.fileType}\n${filled.content}\`\`\`\n` : filled.content);
  } else {
    const empty = document.createElement("p");
    empty.className = "muted doc-template-empty";
    empty.textContent = template.hint;
    page.appendChild(empty);
  }
  pane.replaceChildren(page);
}

// Guards against creating several documents from one fast burst of typing.
let creatingDocument = null;
// Ids `ensureDocumentExists` made since the page loaded; the only ones `docDropIfUntouched` may bin.
const docsMadeThisSession = new Set();

async function ensureDocumentExists() {
  if (currentDoc) return currentDoc;
  if (creatingDocument) return creatingDocument;
  creatingDocument = (async () => {
    const doc = await apiJson("/documents", {
      method: "POST",
      body: JSON.stringify({ title: $("doc-title").value.trim() || docNextName(), content: "", file_type: docTypeState.pending || "md" }),
    });
    await ensureModule("library"); // the list redraw below reaches the files later in the bundle (INBOX 1530 f)
    docTypeState.pending = null;
    currentDoc = doc;
    docsMadeThisSession.add(doc.id);
    docs.unshift({ ...doc });
    // The list gains an "Untitled" row the moment this returns, so show the
    // same name in the title box, otherwise the document you're typing into
    // appears to have no name while the sidebar says it has one.
    if (!$("doc-title").value.trim()) $("doc-title").value = doc.title;
    renderDocList();
    $("doc-empty").classList.add("hidden");
    return doc;
  })();
  try {
    return await creatingDocument;
  } finally {
    creatingDocument = null;
  }
}


//: While the edit-conflict prompt is up, autosave waits for its answer
//: rather than asking again every 1.2s of typing behind it.
//: **An autosave's conflict waits in the status line, not in a dialog** (audit
//: 1028 D9). A silent save hit the modal in the middle of a sentence, which
//: took the focus and sent the next keystrokes to it. Now the save stops, the
//: status says the document changed in another window and offers "Resolve",
//: and the dialog opens when asked for (or on an explicit save). `{ id,
//: current }`: the other window's version, for the document it is about.
let docConflictPending = null;


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

// A target word count, set per document and kept client-side, it's a
// writing aid, not notebook data, so it doesn't need a column or to survive
// a restore onto another machine the way the document's own content does.
function docWordGoalKey(id) {
  return `docWordGoal:${id}`;
}

function getDocWordGoal(id) {
  if (!id) return 0;
  return Number(prefs.get(docWordGoalKey(id), null)) || 0;
}

function setDocWordGoal(id, goal) {
  if (!id) return;
  if (goal > 0) {
    prefs.set(docWordGoalKey(id), String(goal));
  } else {
    prefs.remove(docWordGoalKey(id));
  }
}

//: **The goal, and only the goal.** The word count, the reading time and the
//: character count moved to the editor's own status bar (`renderDocStatusBar`)
//: when the top dock was rebuilt, reported as "redesign, rearrange, fix, and
//: update the section with the word count, word goal etc elements". Facts
//: about the text belong beside the text; what is left here is the *target*,
//: which is a thing you set rather than a thing you read, and it is drawn as
//: its own control on the same bar.
//:
//: Kept as a separate function from the status bar's because it is called from
//: four places that mean "the document changed", and because a goal is
//: per-document state while the counts are pure arithmetic over the box.
function renderDocStats() {
  const button = $("doc-word-goal");
  const label = $("doc-goal-label");
  if (!button || !label) return;
  //: A word-count goal is for writing: a code file has no use for one, so it
  //: also skips the word count (a whole-document pass: about 200 ms a pause
  //: on a 7,000-line file at 4x CPU, audit 1031 row 23 CE3).
  const code = docIsCodeFile();
  button.classList.toggle("hidden", code);
  if (code) return;
  const { words } = docPlainText.counts(docCommentStrip(docText()));
  const goal = currentDoc ? getDocWordGoal(currentDoc.id) : 0;
  button.setAttribute("aria-pressed", String(goal > 0));
  button.classList.toggle("has-findings", goal > 0 && words >= goal);
  if (!goal) {
    label.textContent = "Set a goal";
    button.title = "Set a word-count goal for this document";
    //: The progress ring is meaningless without a target, so it is not drawn
    //: rather than drawn empty, an empty meter reads as "you have written
    //: nothing", which is a different and usually false claim.
    button.style.removeProperty("--doc-goal-pct");
    button.classList.remove("has-goal");
    return;
  }
  const pct = Math.min(100, Math.round((words / goal) * 100));
  label.textContent = `${words.toLocaleString()} / ${goal.toLocaleString()} · ${pct}%`;
  button.title = `Goal: ${goal.toLocaleString()} words: click to change it`;
  //: A custom property rather than an inline `style` attribute, which this
  //: app's CSP refuses. Same rule the Loose ends meter follows.
  button.style.setProperty("--doc-goal-pct", `${pct}%`);
  button.classList.add("has-goal");
}

function promptDocWordGoal() {
  if (!currentDoc) return;
  const current = getDocWordGoal(currentDoc.id);
  $("doc-word-goal-input").value = current || "";
  $("doc-word-goal-dialog").showModal();
  $("doc-word-goal-input").focus();
}

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

//: State the outline and the breadcrumbs share with the rest of this file (the
//: outline's rebuild writes both; documents-outline.js reads and resets them).
//: `headings` is **the headings the outline last read.** The breadcrumb needs
//: them on every keystroke (`renderDocCaret` runs then, and the caret is what
//: the trail is about), and finding them is a scan of the whole document: on a
//: 20k-word file that is a 20k-element split per character typed. The outline
//: is rebuilt on a pause in typing, so a heading written a moment ago reaches
//: the trail on the same beat it reaches the outline, which is the beat a
//: writer is already watching. `crumbsKey` is what the row says, as one string,
//: so the common case (a keystroke that moves the caret inside the same
//: section) costs a comparison rather than a rebuild of four buttons per
//: character typed.
const docOutlineState = { headings: [], crumbsKey: "" };

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


//: **Where you are in the document, marked in its outline.** The owner, of
//: the sidebar redesign: "mostly outline". Measured before this existed:
//: scrolled to 70% of a 21-heading document, zero rows under `#doc-outline`
//: carried a current class or `aria-current`, and the outline's own scrollTop
//: stayed 0. A table of contents that cannot say which heading you are in is
//: a list of links, and it is the one thing every editor this is measured
//: against (Obsidian, Typora, Notion) does have.
//:
//: Kept as a flat line-and-button list rather than re-read from the DOM on
//: every scroll: the marking runs on a scroll event and must not walk the
//: document, and rebuilding the outline per scroll was the obvious wrong
//: answer this avoids.
let docOutlineRows = [];
//: What the rows were last drawn from; see the early return in renderDocOutline.
let docOutlineMarked = -1;

//: Which row is in the air. One number rather than a `dataTransfer` payload,
//: because the payload a browser hands back on `drop` is a string and the one
//: thing this needs is an index into the list the drag started from.
let docOutlineSpyFrame = 0;


//: The filter box's own wiring, once. `input` rather than a debounce: the
//: work behind it is a pass over the headings this file already holds, not a
//: request, and a debounce on a list that redraws in under a millisecond is
//: latency bought for nothing.
//:
//: Escape clears it rather than closing anything, which is what Escape means
//: in every other search box in this app, and it is the only way back to the
//: whole outline that does not involve selecting the text first.
onDomReady(() => {
  const box = $("doc-outline-filter");
  if (!box) return;
  box.addEventListener("input", () => renderDocOutline());
  box.addEventListener("keydown", (event) => {
    if (event.key !== "Escape" || !box.value) return;
    event.stopPropagation();
    box.value = "";
    renderDocOutline();
  });
});


//: Set by `renderDocPreview`, read by `docScrollAnchors`. Zero until the
//: preview has been drawn once, which is also when there are no stamps to
//: read, so the default is never used as an answer.
let docPreviewLineShift = 0;


// --- the code editor: line numbers, indent, comment toggle ---------------------
//
// Asked for directly: a code file should have "code lines as well as language
// detection and ctrl + / commenting or equivalent as well as indenting and
// dedenting". All three are keystroke-level, which is why the file-type table
// is fetched and cached rather than queried, see `loadDocFileTypes`.
//
// Built on the existing textarea rather than on a third-party code editor.
// This app has no build step (`frontend/js/app.js` is served as-is), so a real
// editor component would mean either a vendored bundle or a CDN, and the
// three behaviours that were actually asked for are a few dozen lines each
// against a textarea. What is genuinely lost by not using one is syntax
// *colouring*, which needs a tokeniser per language; that is a separate
// decision with a real dependency behind it, and pretending otherwise by
// half-highlighting a few keywords would look worse than plain monospace.


//: **The way out of an editor that takes the Tab key.** Owner: "on the
//: documents editor, I can't press tab to indent without it selecting an
//: element." Tab now indents in every document, prose as well as code, which
//: is what every writing tool does and what the report asks for; the reason
//: it was restricted to code files was never indentation, it was the exit:
//: a Tab the editor always swallows leaves a keyboard user inside it with no
//: way to reach the toolbar, the dock or the rest of the page.
//:
//: So the exit moves to the chord CodeMirror's own documentation recommends
//: for exactly this trade (its `indentWithTab` carries the same warning):
//: press Escape, then Tab, and the Tab is the browser's again. Escape is
//: already this app's "leave what you are in" key everywhere else, so it is
//: the one key a reader is most likely to try first, and it costs a writer
//: nothing because nothing else in the editor consumes a plain Tab.
//:
//: The second way out is unchanged and needs nothing learned: Shift+Tab on a
//: line with no indentation to remove falls through to the browser's own
//: focus-backwards rather than doing nothing.
let docTabEscapes = false;


// --- Live preview: the same editor, with decorations on -----------------------
//
// ROADMAP item 0, asked for again directly: "the notion/obsidian live md
// rendering after typing hybrid kind of md". The model both of those use, and
// the one implemented here: **the document renders in place, and the markdown
// markers hide themselves until the caret enters the thing they mark.** So
// `**bold**` is bold while you read it and `**bold**` while you edit it, and
// you never lose sight of the syntax you are actually typing.
//
// **What this replaces, and why it had to.** Until Phase 2 the Live view was a
// second editor: one `<textarea>` per paragraph, the rest of the document
// rendered to HTML beside them, the whole pane rebuilt whenever the prose
// check ran. It worked, and it was honest about its own limits, but the cost
// was structural. Measured in Chromium on the plan's own 20k-word document
// (`scratchpad/ui-sweeps/doctype.js`): a single keystroke in Live produced
// 1,178 markdown renders and a keydown p50 of 160 ms against a 30 ms gate,
// because every debounced prose pass tore down and rebuilt every block in the
// document. There is no tuning that fixes that shape; the pane has to stop
// being a thousand elements.
//
// Decorations are the fix and they are also the better editor. One document,
// one caret, one selection, one undo history, no block boundaries to fall
// between, and only the *visible* lines are ever decorated
// (`view.visibleRanges`), so the work per keystroke is a screenful rather than
// a document. It is Obsidian's own architecture, which is what was asked for.
//
// **What was lost, said plainly:** the Notion-style block handle, its drag to
// reorder and its move/duplicate/delete menu went with the block DOM. The
// drag is back (`docLiveExtensions.dragHandle`, DX29), a gutter grip over the
// one document that reuses the Alt+Up and Alt+Down move; the menu is still
// DOCUMENTS_PLAN Phase 3's.

// -----------------------------------------------------------------------------
// The table commands: what the editor does with the model above
// -----------------------------------------------------------------------------
//
// Everything here reads the caret, asks the model for a list of edits and
// dispatches them. There is no second copy of a table anywhere in it, which is
// what keeps Live and Source the same document rather than two renderings of
// one.


// --- rich paste: HTML from a web page, Word or Google Docs, as Markdown -------
//
// **A paste keeps its headings, emphasis, lists and links** (audit FEAT-04,
// 2026-10-05). The only HTML paste handler was the table's, so copying from a
// web page, Word or Google Docs (the commonest way text arrives in a writing
// app) put plain text in: headings, bold, lists and every link's address
// were gone. This walks the clipboard's HTML through `DOMParser` (which runs
// no script and loads nothing) over an allowlist, and writes Markdown, the
// document's own format, so what lands is ordinary text the editor already
// draws. Anything not on the list contributes its text and nothing else.
// Ctrl+Shift+V pastes plain text, as everywhere else.
//
// It takes the paste only when the HTML carries something plain text cannot
// (a heading, emphasis, a list, a link, a quote, code, a picture, a table):
// a code editor's copy is coloured spans and divs, and turning those into
// paragraphs would break the code it was copying.


let docPastePlain = false;


//: **A pasted block starts its own line** (DX3, audit 1102). `## Heading` or a
//: fence written after "please" is not a heading or a fence, it is text with
//: marks in it. One rule for every block kind (heading, list, fence, table,
//: quote, rule, or more than one paragraph): when words come before the caret
//: on its line a blank line goes first, and when words follow the selection
//: on its line one goes after. Inline pastes (bold, a link) are left alone.
docRichPasteEvent.fit = (markdown, before, after) => {
  const block = /^(#{1,6} |[-*+] |\d+[.)] |```|\||>|---)/.test(markdown) || markdown.includes("\n\n");
  if (!block) return markdown;
  return `${before.trim() ? "\n\n" : ""}${markdown}${after.trim() ? "\n\n" : ""}`;
};


// Frontmatter and the properties panel: documents-props.js (DC13 remainder).

// =============================================================================
let docPrintComments = false;
let docAiController = null;
$("doc-code-snippets-open")?.addEventListener("click", () => docCodeSideFrom("snippets"));
$("doc-code-assist-open")?.addEventListener("click", () => docCodeSideFrom("assist"));
$("doc-new").addEventListener("click", () => createDocument());
$("doc-new-template")?.addEventListener("click", openDocTemplateDialog);
//: The Diagram builder's one door (documents-mermaid.js), as a button beside New: it was a row behind New's caret, two clicks and easy to miss (INBOX 1679).
$("doc-new-diagram")?.addEventListener("click", () => diagramModel.door({ doc: true }));
$("doc-template-list")?.addEventListener("keydown", docTemplateListKeys);
$("doc-template-use")?.addEventListener("click", useDocTemplate);
// Searching and sorting every document lives in the Library now (§36G), with
// the notes, chats and files beside them. This is the way there, said out loud
//, a list that silently stops at eight is a list that has lost your writing.
$("doc-browse-all").addEventListener("click", () => {
  switchTab("library");
  libraryKind = "document";
  renderLibraryOverview();
  renderLibraryFilters();
  renderLibrary();
});
// Used to be an open-by-default <details> in the sidebar; its body was tall
// enough to push the document list down, so it is a dialog now. The Close
// button and Escape both close it, Close via the generic [data-close-dialog]
// delegation set up below, Escape for free from <dialog>.showModal().
$("doc-storage-toggle").addEventListener("click", () => $("doc-storage-dialog").showModal());
$("doc-title").addEventListener("input", () => { markDocDirty(); scheduleDocPreview(); });
$("doc-title").addEventListener("blur", () => { if (docFillBlankTitle()) markDocDirty(); });
//: **Enter in the title starts the body** (audit 2026-10-05, UX-05), the way
//: Notion, Apple Notes and Obsidian behave: "Trip plan", Enter, "Day one..."
//: used to type on into the title and save it as one long name over an empty
//: body. ArrowDown at the end of the title goes there too. Not mid-IME.
$("doc-title").addEventListener("keydown", (event) => {
  if (event.isComposing || event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
  const title = event.currentTarget;
  const atEnd = title.selectionStart === title.value.length && title.selectionEnd === title.value.length;
  if (event.key !== "Enter" && !(event.key === "ArrowDown" && atEnd)) return;
  event.preventDefault();
  //: Read view (a phone opens a document in it) has no body to type in, so
  //: Enter goes back to the editing view last used, as the Edit button does.
  if (docView === "rendered") setDocView(lastEditView || "live");
  if (docCmView && docCmView.dom.isConnected && docCmView.dom.offsetParent !== null) {
    docCmView.dispatch({ selection: { anchor: 0 }, scrollIntoView: true });
    docCmView.focus();
    return;
  }
  //: Through the adapter (tests/test_doc_surface.py): the fallback box is
  //: only reached here when CodeMirror is not on screen.
  if (docBoxEl()?.offsetParent !== null && docBoxEl()) {
    const surface = docSurface();
    surface.focus();
    surface.setSelection(0);
  }
});
//: The dock's breadcrumb (INBOX 424 p): back to the Library's Documents list,
//: the place a document is opened from.
$("doc-back")?.addEventListener("click", () => {
  const crumb = $("doc-back");
  if (crumb.dataset.from) return openDocument(Number(crumb.dataset.from));
  switchTab("library");
  document.getElementById("library-subtab-docs")?.click();
});
//: Registered through the adapter rather than on the element, so the same
//: line serves whichever engine is underneath. `mountDocEditor` says it
//: again for the view it builds: a handler registered on the fallback's DOM
//: cannot follow the document into CodeMirror.
docSurface().onChange(docSurfaceInput);
// The gutter is a separate element beside the textarea, so it has to be told
// to follow it, because a textarea's own scroll does not move its siblings.
// The fallback's problem only: the engine's own gutter is inside the view and
// scrolls with it.
docBoxEl().addEventListener("scroll", (event) => {
  const gutter = $("doc-gutter");
  if (gutter && !gutter.classList.contains("hidden")) {
    gutter.scrollTop = event.currentTarget.scrollTop;
  }
});
// The document-textarea resize gap (Priority 0 #1): dragging #doc-content's
// native `resize: vertical` handle shorter pins the textarea's own height,
// but #doc-panes, a flex item of .doc-main with `flex: 1 1 auto`, keeps
// growing to fill the card exactly as before, because nothing about a CSS
// resize tells a flex *parent* to stop growing to fit it. The freed space
// used to be trapped inside #doc-panes, below the now-shorter textarea and
// above .doc-hint: dead space in the middle of the card instead of at its
// bottom, where a person would expect it. There's no CSS-only fix: nothing
// short of a user dragging the handle can tell us the textarea's size is no
// longer meant to track the flex layout, so this is the one place app.js
// answers "did a person just resize this" with a real yes/no rather than a
// CSS rule guessing at it. A mousedown that ends with a different height is
// as close as the DOM gets to "yes", ordinary typing or a value swap on
// loading a different document never changes offsetHeight.
{
  const box = docBoxEl();
  let heightBeforeDrag = null;
  box.addEventListener("mousedown", () => { heightBeforeDrag = box.offsetHeight; });
  document.addEventListener("mouseup", () => {
    if (heightBeforeDrag === null) return;
    if (box.offsetHeight !== heightBeforeDrag) {
      $("doc-panes").classList.add("doc-panes-manual");
    }
    heightBeforeDrag = null;
  });
}
initMarkdownToolbars();
$("doc-word-goal").addEventListener("click", promptDocWordGoal);
$("doc-counts")?.addEventListener("click", () => docRunTextTool("stats"));
$("doc-counts")?.addEventListener("keydown", (event) => {
  if (event.key !== "Enter" && event.key !== " ") return;
  event.preventDefault();
  docRunTextTool("stats");
});
//: **A button with no width is not a place to stand** (audit 1102 DX21): at 390
//: the counts give way entirely (an ellipsis in a 0px box), still visible to
//: the tab key as a focus stop nobody can see. It leaves the tab order while it
//: has no room and comes back when it has; the same statistics are one press
//: away in the document menu. Watched by `docGutterObserver`, whose callback
//: knows this one element.
watchDocGutter($("doc-counts"));
//: **A word goal for the day, and a streak** (L-documents-2). Words added to prose documents are counted per local day in
//: prefs (`docWriting`); a day that reaches the goal extends the streak, and a missed day starts it again. A jump of
//: more than WB words in one count is a paste or a load, not writing, and is not credited. Set from the word count's
//: menu (right-click, or the menu key); everything stays on this device. Fed by `renderDocCounts` with a `doc:counted` event.
// writing-streak:begin
(() => {
  const counts = $("doc-counts");
  if (!counts) return;
  const KEY = "docWriting";
  const GOALS = [250, 500, 1000, 2000];
  const PASTE = 200;
  let seen = { id: null, words: 0 };
  const dayOf = (date) => [date.getFullYear(), String(date.getMonth() + 1).padStart(2, "0"), String(date.getDate()).padStart(2, "0")].join("-");
  const today = () => dayOf(new Date());
  const yesterday = () => {
    const date = new Date();
    date.setDate(date.getDate() - 1);
    return dayOf(date);
  };
  const read = () => {
    let state = {};
    try {
      state = JSON.parse(prefs.get(KEY, "{}")) || {};
    } catch {
      state = {};
    }
    const day = today();
    return { goal: Number(state.goal) || 0, day, words: state.day === day ? Number(state.words) || 0 : 0, streak: Number(state.streak) || 0, last: state.last || "" };
  };
  const write = (state) => prefs.set(KEY, JSON.stringify(state));
  //: A streak that was last extended before yesterday has ended, whatever it was.
  const live = (state) => (state.last === state.day || state.last === yesterday() ? state.streak : 0);
  const line = (state) => {
    const days = live(state);
    const streak = days ? `, ${days}-day streak` : "";
    return state.goal ? `${state.words.toLocaleString()} of ${state.goal.toLocaleString()} words today${streak}` : `${state.words.toLocaleString()} words added today`;
  };
  counts.addEventListener("doc:counted", (event) => {
    const { id, words } = event.detail;
    const before = seen.id === id ? seen.words : null;
    seen = { id, words };
    const state = read();
    const delta = before === null ? 0 : words - before;
    if (delta > 0 && delta <= PASTE) {
      state.words += delta;
      if (state.goal && state.words >= state.goal && state.last !== state.day) {
        state.streak = state.last === yesterday() ? state.streak + 1 : 1;
        state.last = state.day;
      }
      write(state);
    }
    if (state.goal) counts.textContent += ` · ${state.words.toLocaleString()} of ${state.goal.toLocaleString()} today`;
    counts.title = `${DOC_COUNTS_TITLE_PROSE}. Right-click for the daily word goal`;
  });
  const openMenu = (x, y) => {
    if (docIsCodeFile()) return false;
    const state = read();
    const set = (goal) => () => write({ ...state, goal });
    const items = [{ group: "Today", label: "ph:pencil-simple-line " + line(state), disabled: true, run: () => {} }];
    for (const goal of GOALS) {
      items.push({ group: "Daily word goal", label: `${state.goal === goal ? "ph:check" : "ph:flag"} ${goal.toLocaleString()} words`, run: set(goal) });
    }
    items.push({ group: "Daily word goal", label: "ph:x No daily goal", run: set(0) });
    openMenuAtPoint(items, "Daily word goal", x, y, counts);
    return true;
  };
  counts.addEventListener("contextmenu", (event) => {
    const box = counts.getBoundingClientRect();
    if (openMenu(event.clientX || box.left, event.clientY || box.top)) event.preventDefault();
  });
  //: A finger's twin of the right-click (a hold on the counts).
  wireLongPress(counts, (event, point) => openMenu(point.x, point.y));
})();
// writing-streak:end
$("doc-word-goal-submit").addEventListener("click", () => {
  if (!currentDoc) return;
  //: The field's own limits say what is wrong (1031 DC9: a negative goal
  //: closed the dialog with no goal and no word), the way the form does.
  if (!$("doc-word-goal-input").reportValidity()) return;
  const goal = Math.max(0, Math.round(Number($("doc-word-goal-input").value)) || 0);
  setDocWordGoal(currentDoc.id, goal);
  renderDocStats();
  $("doc-word-goal-dialog").close();
});
for (const button of document.querySelectorAll("#doc-view-seg [data-doc-view], #doc-diagram-seg [data-doc-view], #doc-view-menu [data-doc-view]")) {
  // The unmodified title is stashed before syncDocFileType ever overwrites it
  // with the "no rendered form" explanation, so switching back to a markdown
  // document restores the real one rather than leaving the disabled text.
  button.dataset.docTitle = button.title;
  button.addEventListener("click", () =>
    setDocView(button.dataset.docViewGroup === "edit" ? lastEditView : button.dataset.docView)
  );
}
//: **A second door onto the line numbers, in the menu that is already about
//: how the document is shown.** The owner: "if I select a txt document,
//: and/or other code file document, and these can have line numbers as well."
//: They could, and the only control that said so lived on the formatting
//: strip, which PLAN.md D1 collapsed by default for good reasons that had
//: nothing to do with this. A preference nobody can find is a preference the
//: app does not have.
//:
//: The same `setDocGutter`, so this and the strip's button are two views of
//: one remembered choice rather than two settings; `applyDocGutter` writes
//: both their pressed states back.
//: The two draw switches show the stored choice (their change handlers are in documents-view.js).
if ($("doc-code-wrap")) $("doc-code-wrap").checked = docToolPref("codeWrap", false);
if ($("doc-whitespace")) $("doc-whitespace").checked = docToolPref("whitespace", false);
wireDocScrollSync();
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
$("doc-width-toggle")?.addEventListener("click", toggleDocWidth);
$("doc-width-menu")?.addEventListener("click", toggleDocWidth);
try {
  applyDocWidth(prefs.get(DOC_WIDTH_KEY, null) === "wide");
} catch {
  applyDocWidth(false);
}
$("doc-dim-others")?.addEventListener("click", () =>
  docRememberReading(DOC_DIM_KEY, !docReadingModes.dimOthers, applyDocDim)
);
$("doc-typewriter")?.addEventListener("click", () =>
  docRememberReading(DOC_TYPEWRITER_KEY, !docReadingModes.typewriter, applyDocTypewriter)
);
$("doc-serif")?.addEventListener("click", () =>
  docRememberReading(
    DOC_SERIF_KEY,
    !$("tab-documents")?.classList.contains("doc-serif"),
    applyDocSerif
  )
);
docRestoreReading();
(() => {
  //: **Zoom** (OPEN W23 D28): one size along the list, stopping at either end. The
  //: menu row cycles and wraps; a wheel that wrapped from the largest to the
  //: smallest would be a jolt, so this clamps.
  let lastAt = 0;
  function docZoomStep(current, delta) {
    const at = DOC_TEXT_SIZES.indexOf(current);
    const next = Math.min(DOC_TEXT_SIZES.length - 1, Math.max(0, (at < 0 ? 1 : at) + delta));
    return DOC_TEXT_SIZES[next];
  }

  //: Ctrl+wheel over a prose document steps the text size. A code file keeps its
  //: own metrics (the gutter is measured from the font), and the browser's page
  //: zoom is untouched everywhere else. Not passive: it has to stop the page zoom.
  $("tab-documents")?.addEventListener("wheel", (event) => {
    if (!event.ctrlKey || !event.deltaY || docIsCodeFile()) return;
    if (!event.target.closest?.(".doc-source-wrap, #doc-preview")) return;
    event.preventDefault();
    //: A trackpad sends dozens of events in one flick; one step per 150 ms keeps it a step, not a leap to the end.
    if (event.timeStamp - lastAt < 150) return;
    const now = docTypographyNow();
    const size = docZoomStep(now.size, event.deltaY < 0 ? 1 : -1);
    if (size === now.size) return;
    lastAt = event.timeStamp;
    prefs.set("doc-text-size", size);
    applyDocTypography(size, now.spacing);
  }, { passive: false });
})();
$("doc-text-size")?.addEventListener("click", () => docStepTypography("size"));
$("doc-paste-special")?.addEventListener("click", () => docPasteSpecialMenu());
$("doc-line-spacing")?.addEventListener("click", () => docStepTypography("spacing"));
docRestoreTypography();
let docFocusOwnsFullscreen = false;
document.addEventListener("fullscreenchange", () => {
  if (!document.fullscreenElement) docFocusOwnsFullscreen = false;
  docFocusSyncFullscreen();
});
$("doc-focus-toggle")?.addEventListener("click", () => toggleDocFocus());
$("doc-focus-exit")?.addEventListener("click", () => toggleDocFocus(false));
$("doc-focus-fullscreen")?.addEventListener("click", docFocusToggleFullscreen);
$("doc-focus-tools")?.addEventListener("click", () =>
  setDocFocusTools(!$("tab-documents")?.classList.contains("doc-focus-tools"))
);
$("doc-focus-sidebar")?.addEventListener("click", () =>
  setDocFocusSidebar(!$("tab-documents")?.classList.contains("doc-focus-sidebar"))
);
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
//: Brought back after a reload in the same session. The tab page may still
//: be hidden here (this file loads with the Library), which is fine: the
//: class waits on it, and `toggleDocFocus` only takes the caret when the
//: page is showing.
//:
//: **After the rest of the file has run, not in the middle of it.** Called
//: inline here, `docFocusFill` reached `renderDocCounts`, whose
//: `DOC_READING_WPM` is a `const` further down: a temporal-dead-zone error the
//: `catch` below swallowed, after the class was set and before Tools and the
//: sidebar were restored (measured: `doc-focus` came back, `doc-focus-tools`
//: never did, and the idle watch was never armed). A microtask runs once this
//: script has finished, when every `const` is initialised.
onDomReady(() => {
  try {
    if (sessionStorage.getItem(DOC_FOCUS_KEY) === "1") toggleDocFocus(true);
  } catch {
    // No storage, nothing to restore.
  }
});
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
$("doc-ai").addEventListener("click", () => docAiLazy("openDocAiPanel"));
//: A code document's Format: the selection when there is one, else the
//: whole file (`docFormatCode`). The press takes the focus from the editor,
//: so it is handed back: formatting is a step in the middle of typing.
$("doc-code-run")?.addEventListener("click", () => docRunCode());
$("doc-csv-grid")?.addEventListener("click", () => ensureModule("docCsvGrid").then(() => docViewState.csvGrid?.toggle()));
//: DOCUMENTS_PLAN 25 row 2: Run on a .py document with no Python yet is
//: disabled, and this line beside it is the way to the install.
$("doc-code-run-why")?.addEventListener("click", () => docRunOpenPythonExtra());
$("doc-code-format").addEventListener("click", async () => {
  await docFormatCode("auto");
  docCmView?.focus();
});
$("doc-ai-close").addEventListener("click", closeDocAiPanel);
$("doc-ai-cancel").addEventListener("click", closeDocAiPanel);
$("doc-ai-run").addEventListener("click", () => docAiLazy("runDocAiEdit"));
$("doc-ai-cancel-run").addEventListener("click", () => docAiController?.abort());
$("doc-ai-accept").addEventListener("click", () => docAiLazy("acceptDocAiEdit"));
$("doc-ai-instruction").addEventListener("keydown", (e) => {
  if (e.key === "Enter") { e.preventDefault(); docAiLazy("runDocAiEdit"); }
});
for (const radio of document.querySelectorAll('input[name="doc-ai-verb"]')) {
  radio.addEventListener("change", () => docAiLazy("docAiVerbChanged"));
}
$("doc-ai-history").addEventListener("click", openDocAiHistory);
$("doc-extract").addEventListener("click", openDocExtractPreview);
//: **A document's headings as a new mind map** (MINDMAP_PLAN decision 35):
//: the map side does the work (`wbMapFromDocument`, whiteboard-map.js), from
//: the text as it stands in the editor, saved or not.
$("doc-map-headings")?.addEventListener("click", () => {
  if (currentDoc) wbMapFromDocument(currentDoc, docText());
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
initDocSidebarTabs();
//: Applied on load as well as on click: the toolbar exists before a document
//: is opened, and a remembered mode that only took effect after the next
//: toggle would read as the setting not having been saved.
applyDocToolbarMode(docToolbarMode());
mountDocToolbarControls();

// =============================================================================
// The editor's own instruments: counts, completion, prose checks, autocorrect
// =============================================================================
//
// Asked for directly: *"improve and expand on some features in the document
// editor, take inspo from vs code and word with options to view more info like
// character count, inline auto fill suggestions, grammar checker + auto correct
// etc."*
//
// **Everything below is local arithmetic over the text in the box.** No model,
// no network, no service, which is not a limitation here, it is the
// requirement: this app's whole claim is that it works with the plug pulled,
// and a grammar checker that phones a server would be the first thing in it
// that does not. It also means every one of these is instant, which is what
// makes them usable while typing at all.
//
// What that rules out is honest to state: this cannot judge *meaning*. It will
// not know that a sentence is wrong, only that it repeats a word, runs long,
// or contains a spelling this list is sure about. Rules that would need
// judgement (its/it's, their/there in context) are deliberately absent, 
// a checker that is wrong a third of the time teaches people to ignore it,
// and then the two thirds it is right about go unread too.

//: The one surface each instrument acts on: whichever box the caret is in.
//: There is one editor now, in every view, so this is almost always the
//: document's own surface; the check survives because the fallback textarea
//: is still a real box when the engine is unavailable.
function docActiveBox() {
  const active = document.activeElement;
  if (active instanceof HTMLTextAreaElement && active.id === "doc-content") {
    return textareaSurface(active);
  }
  //: CodeMirror's editable is a `div`, not a textarea, so the check above
  //: cannot see it. `asSurface` maps any node inside the view onto the
  //: document's surface, which is what makes the caret-following instruments
  //: (the status bar, the completion popup, the findings menu) keep working
  //: once the engine is under them.
  return asSurface(active) || docSurface();
}

//: **Where the caret is, in pixels.** The standard mirror technique: a hidden
//: div that copies every property that affects text layout, holds the text up
//: to the caret, and reports where a marker span lands. There is no API for
//: this: `selectionStart` is an index, and a popup has to go somewhere on
//: screen.
//:
//: The property list is the part that has to be right: miss `font-family` or
//: `padding` and the popup drifts further from the caret the further down the
//: document you are, which reads as a positioning bug rather than a missing
//: line of CSS.
const DOC_MIRROR_PROPS = [
  "boxSizing", "width", "borderLeftWidth", "borderRightWidth", "borderTopWidth",
  "paddingTop", "paddingRight", "paddingBottom", "paddingLeft",
  "fontFamily", "fontSize", "fontWeight", "fontStyle", "letterSpacing",
  "lineHeight", "textTransform", "textIndent", "whiteSpace", "wordSpacing",
  "tabSize",
];

let docMirror = null;

//: The mirror itself, over a real textarea and an offset in its value. Split
//: out of `docCaretPoint` because it is the *textarea's* answer to the
//: question: CodeMirror has `coordsAtPos` and needs none of this, so the
//: adapter routes each surface to whichever one is right for it.
function docMirrorPoint(el, pos) {
  if (!docMirror) {
    docMirror = document.createElement("div");
    docMirror.className = "doc-caret-mirror";
    document.body.appendChild(docMirror);
  }
  const style = getComputedStyle(el);
  for (const prop of DOC_MIRROR_PROPS) docMirror.style[prop] = style[prop];
  //: `pre-wrap`, always: a textarea wraps and preserves whitespace, and a
  //: mirror that collapsed spaces would put the caret a word early on every
  //: line that has two of them.
  docMirror.style.whiteSpace = "pre-wrap";
  docMirror.style.overflowWrap = "break-word";
  docMirror.textContent = el.value.slice(0, pos);
  const marker = document.createElement("span");
  //: A zero-width space rather than nothing: an empty span has no box, so it
  //: reports the wrong position at the end of a line.
  marker.textContent = "​";
  docMirror.appendChild(marker);
  const boxRect = el.getBoundingClientRect();
  const markRect = marker.getBoundingClientRect();
  const mirrorRect = docMirror.getBoundingClientRect();
  const lineHeight = Number.parseFloat(style.lineHeight) || 18;
  const top = boxRect.top + (markRect.top - mirrorRect.top) - el.scrollTop;
  return {
    left: boxRect.left + (markRect.left - mirrorRect.left) - el.scrollLeft,
    top,
    bottom: top + lineHeight,
    lineHeight,
  };
}

//: **Where the caret is, in pixels, for whichever surface holds it.** The
//: shape the plan names (`coordsAt(pos) -> {left, top, bottom}`), with the
//: line height carried alongside because every caller here places a popup
//: *under* the line and needs to know how tall it is.
function docCaretPoint(box) {
  return box.coordsAt(box.selection().from);
}


// --- the prose check ----------------------------------------------------------
//
// **Rules, not judgement.** Each one has to be something a regular expression
// can be *sure* about, because a checker that is wrong a third of the time
// teaches people to ignore it, and then the two thirds it is right about go
// unread too. That is why there is no its/it's rule here: telling those apart
// needs the sentence's meaning, and this has none.
//
// `fix` is optional. A rule that can state the problem but not the answer
// ("this sentence is 47 words long") still earns its row: knowing where to look
// is most of the work. Only rules with a `fix` get a button.
const DOC_PROSE_RULES = [
  {
    id: "repeat",
    english: true,
    //: The classic, and the one nobody catches by re-reading: the eye supplies
    //: the missing word. Case-insensitive, and only for words worth repeating
    //: by accident: `\b(\w+)\s+\1\b` alone flags "had had" and "that that",
    //: which are both real English.
    test: /\b(the|a|an|and|to|of|in|is|it|that|for|on|with|as|at|be)\s+\1\b/gi,
    message: "The same word twice in a row",
    fix: (match) => match.split(/\s+/)[0],
  },
  {
    id: "double-space",
    test: /(?<=\S) {2,}(?=\S)/g,
    message: "More than one space between words",
    fix: () => " ",
  },
  {
    id: "space-before-punctuation",
    //: Not before `![[embed]]`: that `!` is the embed's own, not punctuation.
    //: Nor before a dotfile or an extension (" .gitignore", " .env"): the dot
    //: opens a name there (INBOX 1407). Nor the `!` of an image, `![alt](src)`
    //: (audit 1102 DX19): markdown syntax, not punctuation.
    test: /\s+([,.;:!?])(?!\[\[)(?!(?<=!)\[)(?!(?<=\.)[A-Za-z0-9])/g,
    message: "A space before punctuation",
    fix: (match) => match.trim(),
  },
  {
    id: "missing-space",
    //: After a full stop and before a capital, not after every full stop,
    //: because `3.5`, `file.md` and `e.g.` are all correct and common.
    test: /[a-z]{2}[.!?](?=[A-Z])/g,
    message: "No space after the full stop",
    fix: (match) => `${match} `,
  },
  {
    id: "missing-space-comma",
    //: Only before a letter. `1,000` and `a[1,2]` are both correct and common,
    //: and a rule that reformatted numbers would be worse than no rule.
    test: /,(?=[A-Za-z])/g,
    message: "No space after the comma",
    fix: () => ", ",
  },
  {
    id: "double-punctuation",
    test: /([,;:])\1+/g,
    message: "Punctuation repeated",
    fix: (match) => match[0],
  },
  {
    id: "confusion",
    english: true,
    //: your/you're, the one confusion Harper let through on the fixture
    //: (`tests/grammar_fixture_1026.json`): "Your going to love it", "your
    //: not late", "your welcome". Only the forms that cannot be possessive
    //: ("your going to", "your not", "your welcome." closing a clause),
    //: because "your welcome mat" and "your right to vote" are fine. No `fix`:
    //: the answer is offered and never applied by Fix all.
    test: /\b[Yy]our(?= (?:going to|gonna|not|supposed to|able to|ready to)\b| welcome(?:[.,!?]|\s*$| to\b))/gm,
    message: "“your” here is probably “you’re”",
    alternatives: (match) => [match[0] === "Y" ? "You’re" : "you’re"],
  },
  {
    id: "spelling",
    //: The same list autocorrect uses, so a document written with autocorrect
    //: off can still be cleaned up in one pass afterwards. Built below from
    //: `DOC_AUTOCORRECT` rather than typed twice.
    test: null,
    message: "A likely typo",
  },
  {
    id: "long-sentence",
    //: 45 words is not wrong, and this does not say it is, it says look here.
    //: No `fix`, because splitting a sentence is a decision about meaning and
    //: this knows none.
    test: null,
    message: "A very long sentence, worth a full stop somewhere",
  },
];

//: One table for the notes and the documents (audit 1031 N42): `AUTOCORRECT_TYPOS`, autocorrect.js,
//: which this bundle loads first. Two copies had drifted, 42 rows against 89.
const DOC_AUTOCORRECT = AUTOCORRECT_TYPOS;

const DOC_LONG_SENTENCE_WORDS = 45;

// --- the dictionary the spelling check actually reads -------------------------
//
// **What was wrong, and it was the whole check.** Until 2026-09-12 the
// spelling rule looked each word up in `DOC_AUTOCORRECT`, a hand-written table
// of 42 typos, and treated every word that was not in it as correctly spelled.
// That is not a spell checker, it is a list of 42 strings: "tets" was never
// flagged, and neither was anything else a person actually mistypes. The
// owner's two reports are the same cause seen from two sides. "Spelling errors
// and grammar arent picked up all the time" is the table being 42 entries
// long. "No edit suggestions popup panel appears when I click on underlined
// words" is subtler and worse: the underline being clicked was not this app's,
// it was the *browser's* native squiggle, drawn because the editor carries
// `spellcheck="true"`. The app had no finding at that word, so it had nothing
// to open a menu about, and the click did nothing.
//
// So the fix has to be a real dictionary, and the browser's squiggle has to
// go once there is one, or every misspelling carries two underlines and only
// one of them answers a click. `docBrowserSpellcheck` is that switch, and it
// is deliberately conditional rather than deleted: if the word list fails to
// load, the browser's checker is better than nothing and comes straight back.
//
// **Why it is a fetch and not a script.** 871KB of words parsed into a Set is
// work the first paint should never wait for, and most sessions never open a
// document at all. It loads on the first prose pass, which is 150ms after the
// first keystroke in a document at the earliest, and the pass re-runs itself
// when it arrives.

const DOC_WORDLIST_URL = "/vendor/wordlist/en.txt";

//: The words this app and the notes people keep in it are written in, that a
//: general English list does not carry. Kept here rather than appended to the
//: vendored file, so that file stays exactly what its build.sh produces and
//: the licence notice beside it keeps describing its contents.
const DOC_EXTRA_WORDS = [
  "apis", "async", "auth", "autocomplete", "autosave", "autosaved",
  "backend", "callout", "callouts", "changelog", "chatbot", "config", "configs",
  "csv", "dockerfile",
  "downvote", "dropdown", "dropdowns", "embeddings", "enum", "filepath",
  "frontend", "fullstack", "gitlab", "golang", "https", "iterable", "json",
  "kanban", "kubernetes", "linter", "localhost", "memorymap", "mindmap",
  "namespace", "navbar", "nodejs", "npm", "oauth", "onboarding", "passwordless",
  "pypi", "readme", "realtime", "rebase", "regexes", "retagging", "roadmap",
  "rustc", "scrollbar", "sdk", "signup", "standup", "struct", "subfolder",
  "subfolders", "todo", "todos", "tokenizer", "toml", "tooltip", "tooltips",
  "tsv", "ui", "uncached", "untagged", "upvote", "uri", "utf", "uuid", "ux",
  "viewport", "webapp", "webhook", "webhooks", "wireframe", "yaml", "yml",
  //: Found by running the app's own visible text past the list: 34 words in
  //: the whole of index.html were missing, and these are the ones a person
  //: would also write in a note. The rest were fragments ("ve", "nbsp") or
  //: real misspellings ("isnt"), which is the answer that check was for.
  "ctrl", "esc", "bundler", "dev", "embedder", "frontmatter", "minimap",
  "mistyped", "multiline", "outdent", "rebindable", "resizer", "stylesheet",
  "subtree", "uncategorised", "uncategorized", "unlinked", "unticked",
  //: The tools this app talks to by name. They appear in its own screens, so
  //: they will appear in notes about them.
  "gmail", "markitdown", "nomic", "ollama", "qwen", "searxng", "tesseract",
  //: INBOX 1407: the words an interface note uses (a draggable, resizable
  //: panel with scrollbars and a debounce) and the file names' own parts,
  //: found by the false-positive fixture `tests/grammar_fixture_1407.json`.
  "backoff", "clickable", "cron", "debounce", "draggable", "gitignore",
  "hoverable", "makefile", "pytest", "resizable", "scrollbars", "searchable",
  "sortable", "txt", "md", "bat",
];

let docWordlist = null;
//: One object, not two top-level lets (the global-scope ratchet).
const docWordlistState = { loading: false, failed: false };

//: Until this is true the checker makes no claim about whether a word is
//: spelled correctly, which is why every caller asks rather than assuming.
function docWordlistReady() {
  return docWordlist !== null;
}

function docLoadWordlist() {
  if (docWordlist || docWordlistState.loading || docWordlistState.failed) return;
  docWordlistState.loading = true;
  api(DOC_WORDLIST_URL, { silent: true })
    .then((response) => response.text())
    .then((text) => {
      const words = new Set(DOC_EXTRA_WORDS);
      //: **`trim()`, and it is the whole bug report.** Reported with a
      //: screenshot of 268 suggestions on a 298-word document, every one of
      //: them a real English word: "litterally everything isnt in the
      //: dictionary". The list loads, so the no-dictionary guard in
      //: `docWordKnown` never fires; it just matches nothing.
      //:
      //: The file is committed with unix line endings and this sandbox reads
      //: it that way, which is why `docs-spell.js` measured six findings over
      //: 8,000 characters with no false positives. Git on Windows checks text
      //: out with CRLF by default, so every entry arrives as `"offline\r"`,
      //: and `Set.has("offline")` is false for all 92,972 of them. One
      //: checkout on one platform turns the checker into a machine that flags
      //: the entire language.
      //:
      //: Trimming here rather than only pinning the file in `.gitattributes`
      //: (which this commit does as well): the attribute fixes the checkout,
      //: and this fixes every copy that already exists, plus any future list
      //: that arrives with trailing whitespace from wherever it was built.
      for (const line of text.split("\n")) {
        const word = line.trim();
        if (word) words.add(word);
      }
      docWordlist = words;
      docWordlistState.loading = false;
      //: The ranked suggestions are drawn from the same pool, so it has to be
      //: rebuilt, and the pass that ran without a dictionary has to run again
      //: now that there is one.
      docKnownWordsCache = null;
      docSpellCache = new Map();
      docCmApplySpellcheck();
      renderDocProse();
    })
    .catch(() => {
      //: Once, not on a loop: a failed fetch here means the file is missing
      //: from the build, and retrying on every keystroke would turn one
      //: mistake into a request storm. The browser's own checker stays on.
      docWordlistState.loading = false;
      docWordlistState.failed = true;
    });
}

//: A word the checker is willing to have an opinion about. Everything refused
//: here is refused because flagging it would be wrong far more often than it
//: would be right, and a checker that cries wolf is one that gets turned off.
function docSpellable(text, word, start, end) {
  //: Nor a run of more than 40 letters: that is a pasted token or a hash, and
  //: generating its one-edit neighbours aborted node on a 100,000-letter run.
  if (word.length < 2 || word.length > 40) return false;
  //: An acronym (API, HTTP, NASA) is not in any word list and is not a typo.
  if (word === word.toUpperCase()) return false;
  //: An internal capital means an identifier or a product name: Tessellate,
  //: docSurface, YouTube. Splitting and checking the halves would flag half
  //: the identifiers in any technical note.
  if (/[A-Z]/.test(word.slice(1))) return false;
  //: A letter run touching a digit, a path separator, an @ or a dot before
  //: more letters is part of something that is not prose: utf-8, app.js,
  //: me@example.com, C:\\Users. The word regex stops at those characters, so
  //: the only way to see them is to look at what is on either side.
  //: A suggestion's marker is a boundary, not a symbol (OPEN 1088): `{++`
  //: before and `++}` after (and the other CriticMarkup pairs) left
  //: `{++faque++}` with no finding while `{++the faque ++}` had one.
  const opened = /(?:\{\+\+|\{--|\{~~|\{==|\{>>|~>)$/.test(text.slice(Math.max(0, start - 3), start));
  const closed = /^(?:\+\+\}|--\}|~~\}|==\}|<<\}|~>)/.test(text.slice(end, end + 3));
  const before = start > 0 && !opened ? text[start - 1] : "";
  const after = end < text.length && !closed ? text[end] : "";
  if (/[0-9_/@\\#$%&*+=<>~]/.test(before) || /[0-9_/@\\#$%&*+=<>~]/.test(after)) return false;
  //: Next to é, ï, ß: a piece of a longer word (audit 1028 D8).
  if (/\p{L}/u.test(before) || /\p{L}/u.test(after)) return false;
  if (after === "." && /[A-Za-z]/.test(text[end + 1] || "")) return false;
  if (before === "." && /[A-Za-z]/.test(text[start - 2] || "")) return false;
  //: A dotfile (" .gitignore", ".env"): a dot that opens a name, with nothing
  //: but space or the line's start before it (INBOX 1407).
  if (before === "." && (start < 2 || /\s/.test(text[start - 2]))) return false;
  //: A short piece of a hyphenated word is a fragment of a compound that the
  //: word list holds whole or not at all: the "Fi" of Wi-Fi, the "x" of x-ray.
  //: Longer pieces ("anti-inflamatory") are still checked.
  if (word.length <= 3 && ((before === "-" && /[A-Za-z]/.test(text[start - 2] || "")) || (after === "-" && /[A-Za-z]/.test(text[end + 1] || "")))) {
    return false;
  }
  return true;
}

//: **A name is not a misspelling.** A capitalised word that is not the first
//: of its sentence is a person, a place or a product ("Okafor", "Priya",
//: "Aroha", "Zeynep", "Siobhan": 8 of the 13 false spelling marks on the
//: fixture), and no word list holds them. The first word of a sentence, a list
//: item, a heading or a table cell is capitalised whatever it is, so it keeps
//: the check but only where the checker has one confident correction
//: (`docSpellConfident`): "Recieve the report" is still caught, "Priya will
//: send" is not. What this gives up: a typo in a capitalised word in the
//: middle of a sentence ("Reveiw" in a title-case line) is not marked; adding
//: names to the dictionary was the only other answer and it never ends.
//: The exception is a swap of two letters that makes exactly one real word
//: ("Reveiw" is "Review", no name is spelled by swapping two letters of a
//: common word), which `docSpellTransposed` answers.
//: Returns "" for a word that is not capitalised.
function docSpellNameKind(text, word, start) {
  if (!/^[A-Z]/.test(word)) return "";
  //: Only the last 120 characters are read: a one-line document of 100,000
  //: characters made `lastIndexOf("\n")` scan back to its start for every
  //: capitalised word (measured: 24 ms became 277 ms).
  const window = text.slice(Math.max(0, start - 120), start);
  const newline = window.lastIndexOf("\n");
  const lead = newline >= 0 ? window.slice(newline + 1) : window;
  const atLineHead = newline >= 0 || start <= 120;
  const opens = atLineHead && /^[ \t]*(?:(?:[#>*+|-]+|\d+[.)]|\[[ xX]\])[ \t]*)*["'“‘(*_]*$/.test(lead);
  const afterStop = /[.!?]["')”’*_\]]*[ \t]+["'“‘(*_]*$/.test(lead);
  return opens || afterStop ? "initial" : "name";
}

//: Is this a word? Asked only of things `docSpellable` has already allowed.
//: A trailing possessive is stripped rather than listed: the vendored file
//: drops its 18,579 "word's" forms because this is cheaper and cannot get out
//: of step with the nouns it is built from.
function docWordKnown(word) {
  if (!docWordlist) return true;
  const bare = word.replace(/['’]s$/i, "").replace(/['’]+$/, "");
  if (!bare) return true;
  const lower = bare.toLowerCase();
  return docWordlist.has(lower) || docDictionary().has(lower);
}

//: The strings one edit away from a word, each tagged with *which* edit, and
//: the tag is the point. Norvig's shape for the generation, and the reason it
//: is this rather than a scan of the dictionary is arithmetic: a scan is
//: 93,000 edit-distance computations, this is a few hundred Set lookups, and
//: the two return the same answer for distance one.
//:
//: The tag ranks the answers, and ranking by *how specific the edit is* is
//: what makes the top row the word the writer meant. There are only n-1
//: transpositions of a word and n deletions, against 26n insertions and 25n
//: substitutions: so a candidate that needs only a swap is a far stronger
//: claim than one of twenty-five letters that could have gone in that slot.
//: Measured: "tets" ranked alphabetically offered tats, teas, teds, tees and
//: tens, and never "test", which is the one word anybody typing "tets" meant.
const DOC_ALPHABET = "abcdefghijklmnopqrstuvwxyz'";
const DOC_EDIT_SWAP = 0;
const DOC_EDIT_DROP = 1; // one letter too many was typed
const DOC_EDIT_ADD = 2; // one letter was missed
const DOC_EDIT_SWAP_LETTER = 3; // the wrong letter was typed

function docEditsOnce(word) {
  const out = new Map();
  const note = (candidate, rank) => {
    if (candidate === word) return;
    const seen = out.get(candidate);
    if (seen === undefined || rank < seen) out.set(candidate, rank);
  };
  for (let i = 0; i <= word.length; i += 1) {
    const head = word.slice(0, i);
    const tail = word.slice(i);
    if (tail) note(head + tail.slice(1), DOC_EDIT_DROP);
    if (tail.length > 1) note(head + tail[1] + tail[0] + tail.slice(2), DOC_EDIT_SWAP);
    for (const letter of DOC_ALPHABET) {
      if (tail) note(head + letter + tail.slice(1), DOC_EDIT_SWAP_LETTER);
      note(head + letter + tail, DOC_EDIT_ADD);
    }
  }
  return out;
}

function docSpellRoot(word) {
  return word.toLowerCase().replace(/['\u2019]s$/i, "");
}

//: Real words one or two edits from a misspelling, nearest first. Two edits
//: is only reached when one edit finds too few, because it costs the square
//: of the work and because a word with a one-edit neighbour almost always
//: meant that neighbour.
const DOC_TWO_EDIT_FLOOR = 2;

function docSpellGuesses(word, limit = DOC_SUGGEST_MAX, quick = false) {
  if (!docWordlist) return [];
  const lower = docSpellRoot(word);
  const near = [];
  const once = docEditsOnce(lower);
  for (const [candidate, rank] of once) {
    if (docWordlist.has(candidate)) near.push([candidate, rank]);
  }
  //: Two edits only when one found next to nothing. It costs the square of
  //: the work, and a word with any one-edit neighbour almost always meant one
  //: of those.
  if (!quick && near.length < DOC_TWO_EDIT_FLOOR) {
    const seen = new Set(near.map(([candidate]) => candidate));
    //: Two edits out, everything is equally weak evidence, so they all share
    //: one rank below every one-edit answer.
    outer: for (const middle of once.keys()) {
      for (const candidate of docEditsOnce(middle).keys()) {
        if (candidate === lower || seen.has(candidate)) continue;
        if (!docWordlist.has(candidate)) continue;
        seen.add(candidate);
        near.push([candidate, DOC_EDIT_SWAP_LETTER + 1]);
        if (near.length >= limit * 3) break outer;
      }
    }
  }
  near.sort((a, b) => {
    if (a[1] !== b[1]) return a[1] - b[1];
    //: Within one kind of edit: the first letter is the one a typist gets
    //: right, then the nearer length, then alphabetically so the same word
    //: always offers the same menu in the same order.
    const first = (b[0][0] === lower[0] ? 1 : 0) - (a[0][0] === lower[0] ? 1 : 0);
    if (first) return first;
    const length = Math.abs(a[0].length - lower.length) - Math.abs(b[0].length - lower.length);
    if (length) return length;
    return a[0] < b[0] ? -1 : 1;
  });
  const words = near.map(([candidate]) => candidate);
  const contraction = docSpellContraction(lower);
  if (contraction) words.unshift(contraction);
  return words.slice(0, limit);
}

//: **A misspelling's row names its nearest word** (audit 1102 DX19): "libary"
//: and "tomorow" showed only "not in the dictionary" until the row was opened.
//: One edit only (`quick`), cached on the finding, for the rows drawn; the menu
//: still offers every candidate. Empty when the dictionary was sure (the row
//: then has its own answer) or one edit finds nothing.
docSpellGuesses.hint = (finding) => {
  if (finding.rule !== "spelling" || finding.replacement !== null) return "";
  finding.hint ??= docMatchCase(finding.text, docSpellGuesses(finding.text, 1, true)[0] || "");
  return finding.hint;
};


//: One answer per word rather than per occurrence. A document says the same
//: word many times, the answers cannot change between two of them inside one
//: pass, and the generation above is the most expensive thing the checker
//: does. Cleared when the dictionary changes, which is the only thing that
//: can change an answer.
let docSpellCache = new Map();


let docProseFound = [];
//: "Hide all suggestions for now": the marks, the count and the list go quiet
//: for this sitting without touching the Settings switch or the dismissed
//: list. Not stored, like a dismissal, so it can never be forgotten about.
//: **`rules` keeps the rule pass for an answer that changes nothing it reads**
//: (audit 1028 D18 to D20). The grammar worker's answer and the link offers'
//: answer each repaint through `renderDocProse`, and the rules (a spelling
//: lookup per word, the long-sentence scan) are the larger half of its cost:
//: the repaint after the answer cost as much as the pass the key itself had
//: paid, for the same text and the same findings. Those two callers pass
//: `again`, and a pass that finds the same text under the same settings gets
//: the findings it already made (copies, because the caller shifts their
//: offsets). Every other caller (a key, a dismissal, a setting) runs afresh.
//: A method here rather than a function of its own: the shared scope is capped.
//: "list" is the suggestions, "dismissed" is the ones put away in this document.


// The prose tools (grammar, suggestion mode, the accessibility check, read
// aloud) are in documents-prose.js, which the Library bundle loads before
// this file. See its header.

// =============================================================================
// The three shapes a finding is drawn in (DOCUMENTS_PLAN Phase 0 and Phase 2)
// =============================================================================
//
// **What used to be here, and where it went.** Phase 0 drew the findings on a
// `<div>` behind the textarea: same text, same type, same size, with the
// textarea's own ink turned transparent so the reader looked at the div and
// typed into the box. It was the standard technique and it was the right
// answer while the surface was a textarea, but it cost twenty-six computed
// properties copied on every resize to keep two layers of glyphs on top of
// each other, and the comment it carried recorded what happens when one of
// them is missed: the underline is right at the top of the file and a word
// out by the bottom.
//
// Phase 2 decision 5 retires it. The findings are mark decorations inside the
// engine now (`docFindingsPlugin`), which have no geometry to keep in step
// because they *are* the text, and they are drawn in every view rather than
// only in the two the backdrop could cover. What is left here is the part
// that was never about the layer: which findings are drawable at all, and
// what shape each kind gets.


// --- inline completion --------------------------------------------------------
//
// **Where the words come from, and why not a dictionary.** A generic English
// word list would suggest "thereabouts" while you are writing about your own
// project and never once offer the word you actually use twenty times a day.
// The useful vocabulary of a document is the document, plus the notebook it
// sits in: your project names, your people, your jargon, spelled the way you
// spell them. So the index is built from this document's own words and the
// notebook's note titles and tags, which also means it needs no download, no
// model, and no network, and it is *right* on the first character rather than
// after a paragraph of context.


let docCompleteWords = null;


// --- autocorrect --------------------------------------------------------------


// --- wiring -------------------------------------------------------------------
//
// One delegated pair on `document` rather than listeners per box: the live
// view replaces its textareas on every render, and per-box listeners are the
// shape that silently accumulates duplicates (tests/test_frontend_handlers.py
// exists because of exactly that).


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

//: **Tab moves between table cells**, on the one model the renderer and the
//: cell menu also use.
//:
//: This was a second reading of the line before Phase 3: it found the pipes
//: with a scan that required the row to *start* with one, so a table written
//: without outer pipes (which GFM allows and people write) had no Tab at all;
//: it could not tell a header from a body row except by a regex for dashes;
//: and the row it added was `| | |` whatever the table around it looked like.
//: All three are properties of the parse, and there is a parse now. Returns
//: false anywhere that is not a table, so the indent behaviour below is
//: untouched.
function docTableTab(event, box) {
  const context = docTableContext(box);
  if (!context) return false;
  event.preventDefault();
  docTableTabStep(event.shiftKey, context);
  return true;
}

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

//: **Clicking the flagged word itself.** Reported: "I cant click on the
//: flagged word or phrase and see a popup for suggested fixes."
//:
//: A `<textarea>` cannot carry marks inside its text, its value is a string,
//: not a DOM: so there is nothing there to underline and nothing to click.
//: What there *is* is a caret with an offset, which is exactly what a finding
//: is expressed in. So: double-click (or right-click) a word, and if a finding
//: covers that offset its menu opens at the caret. Stated plainly because the
//: absence of a squiggle is a real difference from Word, and the reason for it
//: is structural rather than an omission.
//:
//: With CodeMirror under the editor the squiggle is a real decoration in
//: every view, so the gesture below is no longer the substitute it was: it is
//: the keyboard route to the same menu the underline opens.
function docFindingAtOffset(offset) {
  return docProseFound.find((finding) => offset >= finding.start && offset <= finding.end) || null;
}

//: The caret, in the document's own coordinates. One editor, one set of
//: offsets: the live-block translation this used to carry went with the
//: per-paragraph boxes.
function docOffsetOf(box) {
  return box ? box.selection().from : null;
}

//: **The word under the pointer, found by asking the marks rather than the
//: textarea.** Right-clicking a word is how everyone expects to be offered a
//: correction for *that* word, and a right-click does not reliably move the
//: caret first, so reading `selectionStart` answered a question about wherever
//: the caret was last left. That is half of "i still cant select on an
//: underlined incorrectly spelled word and have a popup with suggestions".
//:
//: This used to call `document.caretPositionFromPoint`, and **that was wrong
//: in a way nothing here could see.** Measured in Chromium against a running
//: app: inside a `<textarea>` it returns the offset *within the visual line*,
//: not within the value. A caret at document offset 29 hit-tests as 6, at 50
//: as 5, at 60 as 15. So on every line but the first it looked up a finding at
//: an offset tens or hundreds of characters earlier, which either opened the
//: wrong word's menu or, far more often, silently found nothing and let the
//: browser's own menu through. The feature read as "sometimes it works".
//:
//: Since Phase 0 there is a better answer than an offset: there is a real
//: element at the exact place the finding is, so the question "which finding
//: is under this point" is a rectangle test against boxes the browser itself
//: laid out. No arithmetic, nothing to get wrong about wrapping, and it is the
//: same element the menu is then anchored to.
//:
//: The engine's marks carry the finding's *index* in an attribute rather than
//: a reference: a decoration's DOM is rebuilt whenever the view repaints, so
//: anything hung on the element itself would be gone by the time it was
//: needed. The index is resolved back here, once, against the list the
//: decorations were drawn from.
function docFindingMarks() {
  const marks = [];
  if (docCmView) {
    for (const el of docCmView.dom.querySelectorAll("[data-doc-finding]")) {
      const finding = docProseFound[Number(el.dataset.docFinding)];
      if (!finding) continue;
      el._docFinding = finding;
      marks.push(el);
    }
  }
  return marks;
}

//: **A mark is one element and can be several boxes, and this is the whole of
//: INBOX 128.** A finding that crosses a soft wrap is drawn as two fragments of
//: one inline element, and `getBoundingClientRect()` answers with the *union*
//: of them, which is a box neither fragment occupies: measured on a doubled
//: "the the" at a wrap point, fragments at `1187..1218` on one line and
//: `471..497` on the next, union `471..1218`, 747px wide and two lines tall.
//: Anchoring a menu to that opened it 716px to the left of the words that were
//: clicked ("the popup didnt appear right next to it but off to the side with a
//: wide gap"), and hit-testing against it claimed every unrelated word inside
//: those 747px as well. `getClientRects()` is the per-fragment answer, so both
//: the question "is the pointer on this finding" and the question "where do I
//: put the menu" are asked of the box the reader can actually see.
function docMarkRects(mark) {
  const rects = [...mark.getClientRects()].filter((rect) => rect.width || rect.height);
  return rects.length ? rects : [mark.getBoundingClientRect()];
}

function docRectHolds(rect, x, y) {
  return x >= rect.left && x <= rect.right && y >= rect.top && y <= rect.bottom;
}

//: The fragment the pointer is in, or, for a route with no pointer (the
//: keyboard, a panel row), the first one: a finding is read from its start, so
//: its first line is where someone looking for it will be looking.
function docMarkAnchor(mark, point) {
  const rects = docMarkRects(mark);
  if (point && rects.length > 1) {
    const hit = rects.find((rect) => docRectHolds(rect, point.x, point.y));
    if (hit) return hit;
  }
  return rects[0];
}

//: **Where a finding is on screen now, asked of the finding rather than of an
//: element somebody held on to** (INBOX 421 c: "sometimes document editor
//: dropdowns appear at the top of the screen ... sometimes it doesnt open at
//: all"). The Live view redraws the line under the pointer the moment a press
//: puts the caret on it (the line's markup is revealed), so the element a
//: right-click or a long-press started on can be detached by the time the
//: menu is placed, and a detached element measures `0,0,0,0`: the clamps then
//: put the menu in the top left of the window, which is the screenshot. The
//: live mark first; failing that the engine's own coordinates for the
//: finding's span; failing that null, and the caller reveals the word or does
//: not open, never opens at the origin.
function docRectUsable(rect) {
  return Boolean(rect) && Number.isFinite(rect.top) && Number.isFinite(rect.left)
    && !(rect.top === 0 && rect.left === 0 && rect.bottom === 0 && (rect.right || 0) === 0);
}

function docFindingAnchor(finding, point) {
  if (!finding) return null;
  const mark = docFindingMarks().find((el) => el._docFinding === finding);
  if (mark && mark.isConnected) {
    const rect = docMarkAnchor(mark, point);
    if (docRectUsable(rect)) return rect;
  }
  if (docCmView && Number.isFinite(finding.start)) {
    const size = docCmView.state.doc.length;
    const from = docCmView.coordsAtPos(Math.max(0, Math.min(finding.start, size)), 1);
    const to = docCmView.coordsAtPos(Math.max(0, Math.min(finding.end ?? finding.start, size)), -1);
    if (from && docRectUsable(from)) {
      const sameLine = to && Math.abs(to.top - from.top) < 2;
      return {
        left: from.left,
        right: sameLine ? Math.max(to.right, from.left) : from.left,
        top: from.top,
        bottom: from.bottom,
      };
    }
  }
  return null;
}

//: The finding a mark element stands for, even after the engine has thrown
//: the element away: `_docFinding` is only attached to marks that are in the
//: document when `docFindingMarks` runs, but the index on the element is
//: still the finding's index.
function docFindingOfMark(el) {
  if (!el) return null;
  if (el._docFinding) return el._docFinding;
  const index = Number(el.dataset?.docFinding);
  return Number.isInteger(index) ? docProseFound[index] || null : null;
}

//: **Where the first press of a double-click landed, in the text.** The press
//: puts the caret on the line and the Live view reveals its markup, so the
//: words shift right under a still pointer (measured: 16px for a line with
//: one `**bold**` span), and the second press lands on whatever slid under
//: it, not on the word that was double-clicked. Read in the capture phase,
//: before the engine handles the press and before anything moves.
let docFirstPress = null;
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

//: Whether a menu from `openMenuAtPoint` is showing. Its host is parked in
//: the body and the menu may have been reparented there by
//: `escapeMenuIfClipped`, so it is found by its opener's class.
function docPointerMenuOpen() {
  for (const menu of document.querySelectorAll(".action-menu:not(.hidden)")) {
    if (menu.closest(".pointer-menu-host") || menu._escapedOpener?.classList.contains("pointer-menu-anchor")) {
      return true;
    }
  }
  return false;
}

function docFindingAtPoint(x, y) {
  if (typeof x !== "number" || typeof y !== "number") return null;
  for (const mark of docFindingMarks()) {
    if (!mark._docFinding) continue;
    if (docMarkRects(mark).some((rect) => docRectHolds(rect, x, y))) return mark._docFinding;
  }
  return null;
}

//: Anchored to the word, not to the caret, wherever the word is a real
//: element. A menu that opens at the caret when the pointer is on the word is
//: a menu you have to look away to find.
//: **Put the word on screen before opening a menu about it** (DOCUMENTS_PLAN 12
//: D4). A mark's box is where the text *is laid out*, which is not the same as
//: where it can be seen: the editor clips its own overflow, so a finding one
//: screen below the fold measures at `top 651` inside an editor whose visible
//: box ends at `588`, and a menu anchored there is a menu pointing at nothing.
//: Centred rather than scrolled minimally, for the same reason the panel centres
//: (D3): a word brought just inside the bottom edge leaves the menu nowhere to
//: open but over the panel that asked for it.
//:
//: Returns whether it moved, because CodeMirror applies a scroll effect in its
//: own measure cycle: the mark's box is the old one until the next frame, and
//: the caller has to re-measure rather than trust what it just read.
function docRevealForSuggest(anchor, finding) {
  const host = docCmView ? docCmView.dom.getBoundingClientRect() : null;
  const CM = window.CM6;
  if (!host || !CM || !docCmView) return false;
  if (anchor.top >= host.top && anchor.bottom <= host.bottom) return false;
  docCmView.dispatch({
    effects: CM.view.EditorView.scrollIntoView(finding.start, { y: "center" }),
  });
  return true;
}

function docOpenSuggestFor(finding, focus = true, point = null, revealed = false) {
  //: **One surface** (INBOX 689): a menu opened at the pointer (a suggested
  //: change's, a link's) is the answer the press asked for, and the finding's
  //: popover opened over it is the overlap the owner reported. The change's
  //: menu carries the finding's answers itself (`docSuggestMenu`).
  if (docPointerMenuOpen()) return false;
  const anchor = docFindingAnchor(finding, point);
  if (anchor) {
    //: Once only: a finding the editor cannot bring into view (a folded
    //: construct, a zero-height line) would otherwise ask for a frame forever.
    if (!revealed && docRevealForSuggest(anchor, finding)) {
      requestAnimationFrame(() => docOpenSuggestFor(finding, focus, null, true));
      return true;
    }
    openDocSuggest(finding, anchor, focus);
    return true;
  }
  //: Not drawn at all: the finding is outside the lines the engine has laid
  //: out. Scrolled to, then asked again on the next frame, once. The caret
  //: used to be the fallback here, and the caret's own fallback, when the
  //: engine had no coordinates for it either, was the editor's top left
  //: corner: a menu about a word, opened at the top of the screen.
  if (!revealed && docCmView && window.CM6 && Number.isFinite(finding.start)) {
    docCmView.dispatch({
      effects: window.CM6.view.EditorView.scrollIntoView(finding.start, { y: "center" }),
    });
    requestAnimationFrame(() => docOpenSuggestFor(finding, focus, null, true));
    return true;
  }
  return false;
}

function docOpenSuggestAtCaret(box, point = null, focus = true, pressed = null) {
  let finding = point ? docFindingAtPoint(point.x, point.y) : null;
  //: The word the first press of a double-click was on, before the line
  //: shifted under the pointer (`docFirstPress`).
  if (!finding && pressed != null) finding = docFindingAtOffset(pressed);
  if (!finding) {
    //: The fallback, and it is the right one for a double-click: that gesture
    //: selects the word first, so the caret really is inside it.
    const offset = docOffsetOf(box);
    if (offset === null) return false;
    finding = docFindingAtOffset(offset);
  }
  if (!finding) return false;
  return docOpenSuggestFor(finding, focus, point);
}

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

  //: **The underlined word is a real element, so right-clicking it must work.**
  //: The other half of the same report. `docToolsBoxFor` only ever matched a
  //: `<textarea>`, so in Live view, the one view that *can* draw a squiggle,
  //: and therefore the view where anyone would try this, right-clicking the
  //: mark fell straight through to the browser's own menu. The app's menu was
  //: reachable only by left-clicking, which is not what an underline means
  //: anywhere else.
//: One body for the right-click and the long-press (UI Phase 11 item 9): a
//: flag opens its suggestion at the point, and a right-click or a hold on
//: the box itself opens the suggestion at the caret, only when there is
//: something to say (swallowing the browser's own menu over ordinary text
//: would take away spell-check, paste and everything else it carries for
//: the sake of a menu with nothing in it). Returns whether it opened
//: anything, so the mouse path keeps the browser's menu otherwise.
function docOpenSuggestAtPoint(target, point) {
  const flag = target instanceof Element ? target.closest(".doc-flag, .cm-finding") : null;
  if (flag) docFindingMarks(); // resolves the engine's marks back to findings
  //: Resolved to the *finding* and placed from that, never from `flag`'s own
  //: box: the press that raised this event may already have made the engine
  //: redraw the line, and then `flag` is a detached element measuring
  //: `0,0,0,0`, which is the menu at the top of the window (INBOX 421 c).
  const flagged = docFindingOfMark(flag);
  if (flagged) return docOpenSuggestFor(flagged, true, point);
  const box = docToolsBoxFor(target);
  if (!box) return false;
  return Boolean(docOpenSuggestAtCaret(box, point));
}

//: **The editor's own menu, last of the three.** Not for Shift+right-click
//: (the browser's menu: native spelling, Look up, Translate), not for a code
//: file (its own handler), not for the plain-textarea fallback. A press outside
//: the selection moves the caret there first, as a native menu would. A word
//: the app flagged keeps its suggestion popover, which is asked first.
function docEditorMenuAtPoint(event, point) {
  if (event.shiftKey || !(event.target instanceof Element)) return false;
  const surface = docToolsBoxFor(event.target);
  const view = surface && surface.view;
  if (!view || typeof docEditorMenuItems !== "function") return false;
  //: A code file keeps the browser's menu, except over a selection: there the menu carries the two note rows.
  const code = view.dom.classList.contains("doc-content-code");
  const sel = view.state.selection.main;
  if (code && sel.empty) return false;
  const at = view.posAtCoords(point);
  if (!code && at != null && (at < sel.from || at > sel.to)) view.dispatch({ selection: { anchor: at } });
  const items = code ? [...docClipboardMenuItems(view), ...docSelectionNoteItems(surface)] : docEditorMenuItems(view, point.x, point.y);
  openMenuAtPoint(items, "Document editor actions", point.x, point.y, view.contentDOM);
  return true;
}

//: The table's menu goes first (`docTableMenuAtPoint`, below), and takes the
//: press from the caret-level suggestion: the one this listener opens on any
//: press in a box with something to say. A misspelt word keeps its own. One
//: listener, because the long-press twin below is one call (a lint counts both).
document.addEventListener("contextmenu", (event) => {
  const point = { x: event.clientX, y: event.clientY };
  if (
    docTableMenuAtPoint(event.target, point.x, point.y) ||
    docOpenSuggestAtPoint(event.target, point) ||
    docEditorMenuAtPoint(event, point)
  ) {
    event.preventDefault();
  }
});
//: The hold does not open the editor's own menu (`docEditorMenuAtPoint`): on a
//: phone a hold in text is how a word gets selected, with the browser's handles.
//: The menu answers the contextmenu event a device sends, and the phone bar and
//: selection bar carry Turn into.
if (typeof wireLongPress === "function") {
  wireLongPress(
    document,
    (event, point) =>
      docTableMenuAtPoint(event.target, point.x, point.y) ||
      docOpenSuggestAtPoint(event.target, point),
    { selector: ".doc-flag, .cm-finding, .cm-content, .doc-table-grip, textarea" }
  );
}

//: **A right-click or a hold on a Live table cell opens the table's menu at
//: the pointer** (INBOX 904 B23: "I'm not given a popup menu for tables when I
//: right click them"). The same list as the ⋯ at the header's end
//: (`docTableMenuItems`). The caret goes to the pressed cell first, unless the
//: press is inside what is already selected (a column the person just
//: selected keeps its ranges); a misspelt word in the cell keeps its own menu,
//: which is the listener above. Anywhere else the browser's menu stays.
function docTableMenuAtPoint(target, x, y) {
  if (target instanceof Element && target.closest(".doc-flag, .cm-finding")) return false;
  const grip = target instanceof Element ? target.closest(".doc-table-grip") : null;
  if (grip) return docTableGripMenu(grip, x, y);
  //: By the element under the pointer when the event's own target is not a
  //: cell: with a selection drawn, the press can land on the selection layer.
  let cell = target instanceof Element ? target.closest(".cm-md-td") : null;
  if (!cell && target instanceof Element && target.closest(".cm-editor")) {
    cell = document.elementsFromPoint(x, y).map((el) => el.closest(".cm-md-td")).find(Boolean) || null;
  }
  const surface = cell && asSurface(cell);
  const view = surface && surface.view;
  if (!view) return false;
  //: The pressed cell comes from the element, not from the pixel: the empty
  //: part of a short cell maps to the start of the next one (the hidden pipe
  //: is between them), which put the caret a column to the right. The press
  //: point is only used inside the cell's own span.
  const from = view.posAtDOM(cell);
  const to = from + cell.textContent.length;
  //: A column's ranges, or a row's, press through; one range across several
  //: rows (the whole table) does not, since a menu acting on its first cell
  //: would not be acting on the cell that was pressed.
  const { doc, selection } = view.state;
  const touched = selection.ranges.some(
    (range) =>
      range.from <= to && range.to >= from && range.to > range.from &&
      (selection.ranges.length > 1 || doc.lineAt(range.from).number === doc.lineAt(range.to).number)
  );
  if (!touched) {
    const at = view.posAtCoords({ x, y });
    view.dispatch({ selection: { anchor: at == null ? from : Math.max(from, Math.min(at, to)) } });
  }
  const context = docTableContext(surface);
  if (!context) return false;
  //: The browser's own menu is replaced by this one, so it carries the three
  //: rows people reach for first (review note on PR 191: no Copy or Paste).
  openMenuAtPoint([...docClipboardMenuItems(view), ...docTableMenuItems(context)], "Table row and column actions", x, y);
  return true;
}

//: Copy, Cut and Paste for the right-click menu over a Live table. Plain text
//: only, which is all a cell holds. Paste reads the clipboard API, which a
//: webview may refuse; then it says so rather than doing nothing.
function docClipboardMenuItems(view) {
  const ranges = () => view.state.selection.ranges.filter((range) => !range.empty);
  const selected = () => ranges().map((range) => view.state.sliceDoc(range.from, range.to)).join("\n");
  const none = !ranges().length;
  return [
    {
      label: "Copy",
      group: "Clipboard",
      disabled: none,
      run: async () => {
        await copyToClipboard(selected());
        view.focus();
      },
    },
    {
      label: "Cut",
      group: "Clipboard",
      disabled: none,
      run: async () => {
        const text = selected();
        await copyToClipboard(text);
        view.dispatch(view.state.replaceSelection(""));
        view.focus();
      },
    },
    {
      label: "Paste",
      group: "Clipboard",
      run: async () => {
        let text = "";
        try {
          text = await navigator.clipboard.readText();
        } catch (error) {
          toast("Paste is blocked here. Press Ctrl+V in the cell.", "info");
          view.focus();
          return;
        }
        if (text) view.dispatch(view.state.replaceSelection(text.replace(/\r?\n/g, " ")));
        view.focus();
      },
    },
  ];
}

//: The same menu from an edge grip: the caret goes into the grip's own row or
//: column first (the column's header cell, or the row's first cell), so the
//: menu's "this row" and "this column" are the ones the grip stands for.
function docTableGripMenu(grip, x, y) {
  const surface = asSurface(grip);
  const view = surface && surface.view;
  const context = view && docTableContext(surface);
  if (!context) return false;
  const kind = grip.dataset.kind;
  const index = Number(grip.dataset.index);
  const cell = kind === "row"
    ? { row: index, col: Math.min(context.cell.col, context.table.columns - 1) }
    : { row: context.cell.row === context.table.delim ? 0 : context.cell.row, col: index };
  const span = docTableCellSpan(context.table, cell.row, cell.col);
  if (span) view.dispatch({ selection: { anchor: span.from } });
  const next = docTableContext(surface);
  if (!next) return false;
  openMenuAtPoint(docTableMenuItems(next), "Table row and column actions", x, y);
  return true;
}


//: **Hover opens it too, in a code file** (the owner, 2026-10-11): a squiggle
//: under a comment's or a string's word answers a pause of the pointer as it
//: answers a click or a right-click, with the same popover. A pause, not a
//: pass: moving across a line must not open a menu per word. Not focused, like
//: the plain click, so typing carries on; prose keeps click and right-click.
const DOC_HOVER_SUGGEST_MS = 450;
const docHoverSuggest = { timer: 0, mark: null };
docListen("mouseover", (event) => {
  const mark = event.target instanceof Element ? event.target.closest(".cm-finding") : null;
  if (mark === docHoverSuggest.mark) return;
  clearTimeout(docHoverSuggest.timer);
  docHoverSuggest.mark = mark;
  if (!mark || docFileType().previewable || !docToolsBoxFor(mark)) return;
  const point = { x: event.clientX, y: event.clientY };
  docHoverSuggest.timer = setTimeout(() => {
    if (docHoverSuggest.mark !== mark || !mark.isConnected) return;
    const finding = docFindingOfMark(mark);
    if (!finding || docSuggestOpenFor === finding) return;
    docOpenSuggestFor(finding, false, point);
  }, DOC_HOVER_SUGGEST_MS);
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

//: **The keyboard half of "click the underline", and both gestures are
//: borrowed rather than invented.** `Alt+Enter` on a flagged word opens its
//: menu and `F8`/`Shift+F8` walk the findings, which is what VS Code has
//: bound to exactly these two jobs; anyone who writes code already knows
//: them, and anyone who does not loses nothing. Word's own F7 is taken by
//: this app's shortcuts, and stepping through problems is the half people
//: actually use.
//:
//: They work from the menu as well as from the text: after F8 the focus is on
//: the first suggestion, and pressing F8 again there has to mean "the next
//: one" rather than nothing at all.
function docFindingKeyBox(target) {
  const box = docToolsBoxFor(target);
  if (box) return box;
  const menu = $("doc-suggest-menu");
  if (menu && !menu.classList.contains("hidden") && menu.contains(target)) {
    return docActiveBox() || docSurface();
  }
  return null;
}

//: The next finding after the caret, wrapping at the end. Wrapping rather than
//: stopping, because a stepper that goes quiet at the last item reads as
//: broken; the flash `docProseJump` draws is what says "back to the top".
function docFindingStep(box, backwards) {
  if (!docProseFound.length) return null;
  const here = docSuggestOpenFor && docProseFound.includes(docSuggestOpenFor)
    ? docSuggestOpenFor
    : null;
  //: Measured from the open menu's finding when there is one, so a run of F8s
  //: advances instead of returning to the same word: opening a menu leaves
  //: the caret inside the finding, and "the next one after the caret" would
  //: then be this one again.
  const from = here ? (backwards ? here.start : here.end) : docOffsetOf(box) ?? 0;
  if (backwards) {
    const before = docProseFound.filter((finding) => finding.end < from);
    return before.length ? before[before.length - 1] : docProseFound[docProseFound.length - 1];
  }
  return docProseFound.find((finding) => finding.start > from) || docProseFound[0];
}

function docGoToFinding(finding) {
  if (!finding) return false;
  docProseJump(finding);
  //: One frame, because `docProseJump` may have switched the view, scrolled a
  //: textarea or re-rendered the Live blocks, and the menu is anchored to a
  //: rectangle that none of those had settled yet.
  requestAnimationFrame(() => docOpenSuggestFor(finding, true));
  return true;
}

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

$("doc-dictionary-close")?.addEventListener("click", () => $("doc-dictionary-dialog")?.close());
$("doc-spelling-variant")?.addEventListener("change", async (event) => {
  prefsCache = await apiJson("/preferences", {
    method: "PUT",
    body: JSON.stringify({ spelling_variant: event.currentTarget.value }),
  }).catch(() => prefsCache);
  //: The variant decides which half of the pair table is a finding, so the
  //: lookup has to be rebuilt before the next pass reads it.
  docVariantFor = null;
  //: And the grammar checker's dialect with it (British or American rules).
  docGrammarCache = { text: null, findings: [] };
  renderDocProse();
});
//: Kinds of suggestion (L333): a ticked box is a kind shown; the ones left unticked are
//: saved as `prose_kinds_off` and sent with every grammar ask, so the worker drops them.
$("doc-prose-groups")?.addEventListener("change", async (event) => {
  const off = [...event.currentTarget.querySelectorAll("[data-prose-group]")].filter((box) => !box.checked).map((box) => box.dataset.proseGroup);
  prefsCache = await apiJson("/preferences", {
    method: "PUT",
    body: JSON.stringify({ prose_kinds_off: off }),
  }).catch(() => prefsCache);
  docGrammarCache = { text: null, findings: [] };
  renderDocProse();
});
$("doc-link-offers")?.addEventListener("change", async (event) => {
  prefsCache = await apiJson("/preferences", {
    method: "PUT",
    body: JSON.stringify({ link_offers: event.currentTarget.checked }),
  }).catch(() => prefsCache);
  DOC_LINK_OFFERS.text = null;
  DOC_LINK_OFFERS.findings = [];
  renderDocProse();
});
//: Link text (K11): the same preference as Settings, Writing. The grammar
//: answer is thrown away because what it keeps depends on the switch.
$("doc-check-link-text")?.addEventListener("change", async (event) => {
  prefsCache = await apiJson("/preferences", {
    method: "PUT",
    body: JSON.stringify({ check_link_text: event.currentTarget.checked }),
  }).catch(() => prefsCache);
  docGrammarCache = { text: null, findings: [] };
  renderDocProse();
});
$("doc-grammar-check")?.addEventListener("change", async (event) => {
  prefsCache = await apiJson("/preferences", {
    method: "PUT",
    body: JSON.stringify({ grammar_check: event.currentTarget.checked }),
  }).catch(() => prefsCache);
  docGrammarCache = { text: null, findings: [] };
  renderDocProse();
});
//: The same preference Settings, Preferences sets (`smart_punctuation`), here
//: beside the other writing checks; saved on the change, as the two above are.
$("doc-smart-punctuation")?.addEventListener("change", async (event) => {
  prefsCache = await apiJson("/preferences", {
    method: "PUT",
    body: JSON.stringify({ smart_punctuation: event.currentTarget.checked }),
  }).catch(() => prefsCache);
});

$("doc-prose")?.addEventListener("click", () => {
  const panel = $("doc-prose-panel");
  const chip = $("doc-prose");
  if (!panel || !chip) return;
  const open = panel.classList.contains("hidden");
  panel.classList.toggle("hidden", !open);
  chip.setAttribute("aria-expanded", String(open));
  if (open) renderDocProsePanel();
  docFocusSyncProse();
});

$("doc-focus-prose")?.addEventListener("click", () => {
  if (window.matchMedia(DOC_FOCUS_NARROW).matches && $("doc-prose-panel")?.classList.contains("hidden")) {
    setDocFocusSidebar(false);
  }
  $("doc-prose")?.click();
});

// --- where the suggestions panel sits (INBOX 410) ---------------------------
//
// The owner, 2026-09-24: "allow the suggestions panel to be docked on the
// right instead if the user wishes." Under the editor it takes height from a
// document that is usually taller than it is wide; beside it, on a wide
// window, it takes width the text column was not using. So both, the writer's
// choice from the panel's own head, remembered per browser (a layout
// preference about this screen, not about the notebook), and a column that
// resizes by the sidebars' own handle (`makeSidebarResizable` in sheets-selects.js: a
// `role="separator"` grip, drag, arrow keys, Home or a double click to reset).
//
// **Right means a column in `#doc-panes`**, beside the source and the preview,
// so split view and the right dock share one row and the editor gives up
// width rather than height. The panel element moves; nothing is rebuilt, so
// an open row and its scroll position survive the move. At 720px and below
// (where the sidebars' own handles stop, there being no room beside anything)
// it is always under the editor, whatever was chosen.
const DOC_PROSE_DOCK_KEY = "docProseDock";
const DOC_PROSE_WIDTH_KEY = "docProseWidth";
const DOC_PROSE_WIDTH_DEFAULT = 320;
const DOC_PROSE_WIDTH_MIN = 240;
const DOC_PROSE_NARROW = "(max-width: 720px)";

function docProseDockChoice() {
  try {
    return prefs.get(DOC_PROSE_DOCK_KEY, null) === "right" ? "right" : "bottom";
  } catch {
    return "bottom";
  }
}

//: The side in effect: the choice, except where there is no room for it.
function docProseDockSide() {
  return window.matchMedia(DOC_PROSE_NARROW).matches ? "bottom" : docProseDockChoice();
}

//: Clamped against the room there is: never under the floor, never more than
//: half the editor's row, so the text column is always the larger of the two.
function docProseApplyWidth(width) {
  const panel = $("doc-prose-panel");
  const panes = $("doc-panes");
  if (!panel || !panes) return DOC_PROSE_WIDTH_DEFAULT;
  const room = panes.getBoundingClientRect().width || window.innerWidth;
  const max = Math.max(DOC_PROSE_WIDTH_MIN, Math.round(room * 0.5));
  const clamped = Math.min(Math.max(Math.round(width), DOC_PROSE_WIDTH_MIN), max);
  //: On the tab page, not the panel: focus mode's side panel and the page's
  //: padding beside it read the same property (07-whiteboard-misc.css).
  ($("tab-documents") || panel).style.setProperty("--doc-prose-w", `${clamped}px`);
  try {
    prefs.set(DOC_PROSE_WIDTH_KEY, String(clamped));
  } catch {
    /* private mode: it just won't be remembered */
  }
  return clamped;
}

function docProseSavedWidth() {
  try {
    return Number(prefs.get(DOC_PROSE_WIDTH_KEY, null)) || DOC_PROSE_WIDTH_DEFAULT;
  } catch {
    return DOC_PROSE_WIDTH_DEFAULT;
  }
}

//: The grip, built once and moved with the panel: the sidebars' handle
//: (`.sidebar-resize`, the same role, keys and double click), on the panel's
//: leading edge because the panel grows away from the text, as the web panel's
//: does in chat.
let docProseGrip = null;

function docProseResizeHandle() {
  let handle = docProseGrip;
  if (handle) return handle;
  handle = document.createElement("div");
  docProseGrip = handle;
  handle.className = "sidebar-resize doc-prose-resize";
  handle.setAttribute("role", "separator");
  handle.setAttribute("aria-orientation", "vertical");
  handle.setAttribute("tabindex", "0");
  handle.setAttribute("aria-label", "Resize the suggestions: arrow keys, or drag");
  handle.title = "Drag to resize, double-click to reset";
  const panel = () => $("doc-prose-panel");
  //: The value it says (WCAG 4.1.2): the panel's own width, at most half the
  //: editor, so the stated maximum is the window's half.
  if ($("doc-prose-panel")) trackSeparatorValue(handle, $("doc-prose-panel"), DOC_PROSE_WIDTH_MIN, Math.max(DOC_PROSE_WIDTH_MIN, Math.round(window.innerWidth / 2)));
  handle.addEventListener("pointerdown", (event) => {
    event.preventDefault();
    const startX = event.clientX;
    const startWidth = panel().getBoundingClientRect().width;
    //: Dragging left (a negative delta) widens it: the mirror of a sidebar.
    trackSeparatorValue.drag((e) => docProseApplyWidth(startWidth - (e.clientX - startX)));
  });
  handle.addEventListener("keydown", (event) => {
    const step = event.shiftKey ? 40 : 12;
    const current = panel().getBoundingClientRect().width;
    if (event.key === "ArrowLeft") {
      event.preventDefault();
      docProseApplyWidth(current + step);
    } else if (event.key === "ArrowRight") {
      event.preventDefault();
      docProseApplyWidth(current - step);
    } else if (event.key === "Home") {
      event.preventDefault();
      docProseApplyWidth(DOC_PROSE_WIDTH_DEFAULT);
    }
  });
  handle.addEventListener("dblclick", () => docProseApplyWidth(DOC_PROSE_WIDTH_DEFAULT));
  return handle;
}

//: Put the panel where the side in effect says, and say so on the head's
//: toggle. Safe to call any number of times: a panel already in place is not
//: moved again.
function applyDocProseDock() {
  const panel = $("doc-prose-panel");
  const panes = $("doc-panes");
  const bar = $("doc-statusbar");
  if (!panel || !panes || !bar) return;
  const right = docProseDockSide() === "right";
  const handle = docProseResizeHandle();
  const focus = $("tab-documents")?.classList.contains("doc-focus") === true;
  if (right) {
    if (panel.parentElement !== panes) panes.append(handle, panel);
    docProseApplyWidth(docProseSavedWidth());
  } else {
    //: In focus mode the panel is a fixed side panel whatever side was chosen,
    //: so it has the grip and the remembered width too (INBOX 1408); the grip
    //: is fixed there, so it only has to sit before the panel.
    handle.remove();
    if (panel.previousElementSibling !== bar) bar.after(panel);
    if (focus) {
      panel.before(handle);
      docProseApplyWidth(docProseSavedWidth());
    }
  }
  panes.classList.toggle("doc-prose-right", right);
  panel.classList.toggle("doc-prose-right", right);
  //: The ⋯ names the side it would move to, so its head is drawn again (the
  //: head only: an open row and the scroll survive the move).
  panel.querySelector(".doc-prose-head")?.replaceWith(docProseHeader());
}

function toggleDocProseDock() {
  const next = docProseDockChoice() === "right" ? "bottom" : "right";
  try {
    prefs.set(DOC_PROSE_DOCK_KEY, next);
  } catch {
    /* private mode: it moves for this session only */
  }
  applyDocProseDock();
  //: Focus goes to the ⋯ the move was chosen from, which moved with the
  //: panel: the press that moved it should not lose the reader's place.
  $("doc-prose-panel")?.querySelector(".doc-prose-more button")?.focus();
}

window.matchMedia(DOC_PROSE_NARROW).addEventListener("change", applyDocProseDock);
applyDocProseDock();

for (const [name, id] of Object.entries(DOC_TOOL_KEYS)) {
  const input = $(id);
  if (!input) continue;
  //: `complete` defaults on and `autocorrect` defaults off, which is the
  //: difference between *offering* something and *doing* it to your text.
  input.checked = docToolPref(name, name === "complete");
  input.addEventListener("change", () => {
    docSaveToolPref(name, input.checked);
    if (name === "complete" && !input.checked) hideDocComplete();
  });
}


// =============================================================================
// The dictionary, the spelling variant, and the popup you get from a flagged word
// =============================================================================
//
// Asked for: *"the auto correct and grammar checker needs to be improved
// because I cant click on the flagged word or phrase and see a popup for
// suggested fixes or other options like adding to dictionary (a way to manage
// that dictionary), auto correct spelling (us, uk spelling etc), language
// translation etc. integrate all the usability that these features need and how
// the user would expect to use them."*
//
// The check itself was already right; what it had no shape for was *disagreeing
// with it*. A checker you cannot argue with is one you turn off, because the
// third time it flags your project's name you have no way to say "this is a
// word". So: every finding is a control, and the control's menu carries the
// four answers a person actually has, fix it, this is a word, not this time,
// and (for a spelling) always correct it for me.
//
// **The dictionary lives on the server** (`writing_dictionary`, routes_settings)
// rather than in `localStorage`, and the reason is the same as the spelling
// variant's: a word list you have to rebuild after clearing browser data is a
// list nobody adds to, and a variant that differs between the desktop shell and
// a browser tab is a checker that contradicts itself.


//: The setting's five values (VC6) read the one table: Australian and Indian
//: spell as the British column does for every pair here; Canadian is the
//: mixed one (`DOC_CA_KEEPS_UK`). The label is what a finding says.

//: Built once from the pairs above, in whichever direction the setting names.
//: A map rather than a scan, because this runs per word of the document.
let docVariantFor = null;


//: **The popup, and the four answers a person actually has.** Fix it, this is
//: a word, not this time, and, for a spelling, always correct it. Anchored
//: at the thing it is about, because a menu that opens somewhere else makes
//: you re-find the word you were looking at.
let docSuggestOpenFor = null;


// --- ranking the suggestions (DOCUMENTS_PLAN Phase 0 item 2) ------------------
//
// **Where a suggestion can honestly come from in an app with no dictionary
// file.** This checker knows a fixed list of unambiguous typos and a UK/US
// pair table, and that is the whole of its certainty. For a word it simply
// does not recognise it had nothing to offer at all, and a menu whose only
// row is "ignore this" is a menu that teaches you to stop opening it.
//
// So the order is by how much the app actually knows, strongest first:
//
//   1. the rule's own answer, where a rule was sure enough to have one;
//   2. the other spelling of a UK/US pair, so a document set to UK still sees
//      the US form offered rather than pretended out of existence;
//   3. the nearest words by edit distance in the words this app can claim to
//      know: your own dictionary, plus both halves of the pair table and the
//      corrections in the typo list;
//   4. the nearest words in your own writing, which is the only place your
//      project names, your people and your jargon exist.
//
// Nothing here is a guess dressed as an answer: every row is a real word from
// a list you could go and look at, and 3 and 4 are ordered by a distance the
// reader can feel (one letter out sorts above two).


//: The words this app can say it knows, as opposed to the words it has seen.
//: Rebuilt when the dictionary changes, which is the only thing that can add
//: to it.
let docKnownWordsCache = null;


//: The answers to a finding (rows as data, and the buttons drawn from them): documents-suggest.js, fetched on first
//: use. Each is a stand-in the piece's function of the same name replaces on load, so a caller awaits it.


//: **The popup, the translate hand-off, Discuss in chat and the AI review** are
//: documents-suggest.js, fetched on first use. Each name here is a stand-in: the
//: piece's own function of the same name replaces it on load, so calling the name
//: again after the fetch reaches the real one. Nothing reads their return.


//: Kept so the menu can be re-placed after it changes size, the AI wordings
//: arrive seconds after it opens and make it taller, and a menu that grew
//: downwards off the bottom of the window is a menu whose best suggestion is
//: unreachable.
let docSuggestAnchor = null;


window.addEventListener("resize", docSuggestFollowAnchor);
//: Capture, because the scroll that matters is the editor's own and a scroll
//: event does not bubble.
window.addEventListener("scroll", docSuggestFollowAnchor, true);


let docLastTranslateLanguage = "";


//: Last line, deliberately: everything above has to exist before the first
//: paint. See `renderDocTools`.
renderDocTools();

// =============================================================================
// The engine: CodeMirror 6 under the documents editor (DOCUMENTS_PLAN Phase 2)
// =============================================================================
//
// **Loaded when the first document is opened, never at boot.** The bundle is
// 772 KB (269 KB gzipped) and most sessions in this app never touch the
// Documents tab at all, so paying for it on every cold start would be a
// second of nothing in exchange for a feature that may not be used. INBOX 48
// argued the same shape for the graph's own vendored library. `?v=` is not
// applied: vendor URLs are exempt from the cache stamp
// (tests/test_asset_cache_busting.py) because the version lives in the pin in
// `frontend/vendor/codemirror/package.json`, not in the app's release number.
//
// **The textarea stays.** If the script fails to load, or the browser refuses
// it, `docSurface()` keeps answering with `#doc-content` and the editor keeps
// working exactly as it did. That is the whole reason the fallback is still
// in the markup, and it is why every call site had to go through the adapter
// first: this file must never be able to tell which one it is talking to.


//: True once loading or mounting has failed. Checked before every attempt, so
//: a broken bundle costs one request rather than one per document opened.
let docCmBroken = false;


//: How the prose findings tell the view to repaint. A `StateEffect` rather
//: than a bare `dispatch({})`, so the plugin can rebuild for exactly this and
//: ignore every other transaction that does not move the document or the
//: viewport. Created with the first view, because it needs `CM.state`.
let docFindingsEffect = null;


//: A different document is a different history: carrying the previous one
//: over would let Ctrl+Z paste the last document's text into this one, which
//: is the worst kind of undo bug because it reads as the app corrupting your
//: file. `setState` replaces the history along with the text, which is the
//: whole reason this is not a change transaction.
//:
//: **And each document keeps its own, for the session** (the owner,
//: 2026-10-05: "undo and redo history for specific documents"). The history
//: of the one being left is kept as JSON by its id and given back when it
//: opens again, but only over the very text it was taken against (an edit
//: made elsewhere since would make its steps wrong). A lock purges them all.
let docHistoryOwner = null;


//: **The lock screen has to empty the engine too, and it cannot know how.**
//:
//: `purgeLockedContent` (app.js) is this app's only privacy boundary on the
//: client: it clears every element that holds the notebook's own words, and
//: `#doc-content.value` was one of them. With CodeMirror mounted that value is
//: a stale fallback and the document itself lives in the view's state, which
//: `replaceChildren` on a list of ids cannot reach. Locking the notebook would
//: have left the whole open document readable behind the overlay: exactly the
//: finding that audit was written up for, reintroduced by a change nowhere
//: near it.
//:
//: Watched rather than called, because the purge belongs to app.js and the
//: engine belongs here. The overlay losing `hidden` is the one signal both
//: routes into locking share (the Lock button, and the 401 that re-shows it),
//: so it is the honest thing to observe.
docWatchLock();

// ---- from editor.js (search-boot-1005): calloutMenuItems ----
// Moved whole. Every use is in this file, so it is not needed before this file loads.

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

