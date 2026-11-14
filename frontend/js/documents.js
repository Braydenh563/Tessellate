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

let docWordlist = null;
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
let docCompleteWords = null;
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

