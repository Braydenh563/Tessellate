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

// --- what kind of file this document is ----------------------------------------
//
// A document used to be markdown and only markdown. Asked for directly: the
// editor should handle code too, line numbers, language detection, Ctrl+/
// commenting, indent and dedent, the type should be changeable, and a new
// document should be creatable "of any filetype though it should default to
// md".
//
// The table comes from `GET /documents/file-types` rather than being written
// out here, and that is not tidiness. Indenting and comment-toggling happen
// inside a keydown handler and cannot wait for a round trip, so the frontend
// genuinely needs the whole table, which means either fetching it or keeping
// a second copy. A second copy is a second thing to update, and the failure
// mode of the two disagreeing is Ctrl+/ inserting the wrong comment marker
// into someone's file. So: fetched once, cached here.

//: The served file-type table, `docFileTypes`, lives in library.js with its
//: loader: the Library's list names a code file's lines and kind before the
//: editors load (1031 CE8).
//: The picker's state: `pending` is the type a blank page was started as (New's
//: caret, or the foot's button before anything is typed; null means markdown,
//: cleared when a document is shown); `menu` and `opener` are the foot's own.
const docTypeState = { pending: null, menu: null, opener: null };

//: Markdown's own entry, used before the fetch lands. Everything that reads a
//: file type has to work on the very first paint, and a null here would mean
//: a guard at every call site instead of one honest default in one place.
const DEFAULT_FILE_TYPE = {
  ext: "md",
  label: "Markdown",
  line_comment: "",
  block_comment: ["<!-- ", " -->"],
  indent: "  ",
  previewable: true,
};

// Called from loadDocuments (i.e. whenever the Documents tab is opened) rather
// than once at load, and a no-op once the table is in hand.
//
// It *was* called once at the bottom of this file, and a browser found what
// reading it could not: at that point the app has not been unlocked, so the
// fetch 401s, `docFileTypes` is set to [], and nothing ever asks again. The
// picker stayed an empty <select> for the whole session, every option gone,
// no error anywhere, and the code reads as correct at every line. Same shape as
// the app.js comment about a stale token firing "a dozen requests before the
// user has unlocked anything"; this was the same mistake in a new file.
// Hanging it off the tab load means the first request is always authenticated,
// and a failed one is retried the next time you open the tab instead of
// poisoning the cache for good.
async function loadDocFileTypes() {
  await loadDocTypeTable();
  if (!docFileTypes.length) return;
  docTypeMount();
  syncDocFileType();
}

//: The open document's type, never null. Falls back to markdown for a
//: document saved before file types existed, for an unknown extension, and
//: for the window between load and the fetch above landing.
function docFileType() {
  //: A blank page (no `currentDoc` yet) takes the type picked for it, so the
  //: first keystroke creates a file of that type (`docTypeState.pending`).
  const ext = (currentDoc ? currentDoc.file_type : docTypeState.pending) || "md";
  return docFileTypes.find((t) => t.ext === ext) || DEFAULT_FILE_TYPE;
}

//: What the foot's button does: on an open document the type changes and is
//: saved at once (a mode that has visibly switched but not persisted is one
//: reload away from silently reverting); on a blank page it is the type the
//: first keystroke will create.
async function docTypeChoose(ext) {
  if (!currentDoc) {
    docTypeState.pending = ext === "md" ? null : ext;
    docSetPlaceholder(docBlankPlaceholder());
    syncDocFileType({ prose: false });
    return;
  }
  if ((currentDoc.file_type || "md") === ext) return;
  currentDoc = { ...currentDoc, file_type: ext };
  syncDocFileType();
  await saveDocument({ silent: true });
}

function docBlankPlaceholder() {
  return docTypeState.pending
    ? `Start typing and a new .${docTypeState.pending} file is created for you.`
    : "Start typing and a new document is created for you.\n\nMarkdown works here, headings, **bold**, lists, tables, links.";
}

//: Both pickers are built once the table has arrived (`loadDocFileTypes`).
function docTypeMount() {
  const foot = $("doc-type-slot");
  if (foot && !foot.firstChild) {
    const { wrap, opener, menu } = docTypeMenu(docTypeChoose, "File type of this document");
    docTypeState.menu = menu;
    docTypeState.opener = opener;
    opener.id = "doc-type-button";
    opener.classList.remove("icon-only", "kebab-opener", "ghost", "small");
    opener.classList.add("doc-statusbar-item", "doc-statusbar-button", "doc-type-button");
    foot.replaceChildren(wrap);
  }
  const head = $("doc-new-type-slot");
  if (head && !head.firstChild) {
    const { wrap, opener } = docTypeMenu((ext) => startBlankDocument(ext), "Start a document of another type");
    opener.id = "doc-new-type";
    opener.classList.remove("icon-only", "ghost");
    opener.classList.add("split-button-caret");
    setLabel(opener, "ph:caret-down");
    opener.title = "New document of another type";
    head.replaceChildren(wrap);
  }
  //: Under 16rem the head's help, template and diagram buttons fold into this ⋯ (CSS `.doc-head-more`); it presses the real buttons.
  const tools = document.querySelector("#doc-sidebar-list .doc-head-tools");
  if (tools && !tools.querySelector(".doc-head-more")) {
    const press = (selector) => () => document.querySelector(selector)?.click();
    const more = kebabMenu(
      [
        { label: "ph:question About this list", run: press("#doc-sidebar-list .doc-head-tools .graph-help-toggle") },
        { label: "ph:layout New from a template", run: press("#doc-new-template") },
        { label: "ph:flow-arrow New diagram", run: press("#doc-new-diagram") },
      ],
      "More about the document list",
    );
    more.querySelector("button").id = "doc-head-more-button";
    more.classList.add("doc-head-more");
    tools.append(more);
  }
}

//: The foot's button names the type and its row wears the check. Only when the
//: type changed: opening one more document of the same type writes nothing.
function docTypeSync(type) {
  const opener = docTypeState.opener;
  if (!opener || opener.dataset.ext === type.ext) return;
  opener.dataset.ext = type.ext;
  setLabel(opener, `ph:${type.icon || "file-code"} ${type.label}`);
  opener.title = `File type: ${type.label} (.${type.ext}). Press to change it`;
  //: The name starts with the words drawn on the button (DC5, label-content-name-mismatch).
  opener.setAttribute("aria-label", `${type.label}, file type`);
  //: The menu itself, not `nextElementSibling`: an open menu is moved to `<body>`.
  const menu = docTypeState.menu;
  menu?.querySelector('[aria-current="true"]')?.removeAttribute("aria-current");
  menu?.querySelector(".doc-type-check")?.remove();
  const row = menu?.querySelector(`[data-doc-type="${type.ext}"]`);
  if (!row) return;
  row.setAttribute("aria-current", "true");
  const check = document.createElement("i");
  check.className = "ph ph-check ph-trail doc-type-check";
  check.setAttribute("aria-hidden", "true");
  row.append(check);
}

// Everything about the editor that depends on the type, applied in one place
// so a type change and opening a document of that type cannot diverge.
//: `prose: false` from `openDocument`, whose queued `renderDocTools` runs
//: the same check a frame later (DOCUMENTS 25 row 7).
function syncDocFileType({ prose = true } = {}) {
  const type = docFileType();
  docTypeSync(type);
  docSetPlaceholder(docPlaceholderFor(type));

  // A code file has no rendered form. Offering Live and Split for one is
  // offering to show a wall of escaped source, so those two options are
  // disabled rather than hidden (hidden controls that come and go make a
  // toolbar feel unstable), and a document already in one of them is moved
  // back to Source rather than left looking at nothing.
  if (type.ext === "mmd") syncDocFileType.diagramSeg($("doc-diagram-seg"));
  for (const button of document.querySelectorAll("#doc-view-seg [data-doc-view], #doc-diagram-seg [data-doc-view], #doc-view-menu [data-doc-view]")) {
    // The Edit group button is never disabled: setDocView maps it to Source
    // for a file with no rendered form, which is the mode it must reach.
    if (button.dataset.docViewGroup) continue;
    //: Plain is offered for a code file as readily as Source: "use the
    //: documents tab as a plain text editor" is exactly the thing you would
    //: want on a `.csv` or a `.php` the bundle has no mode for.
    button.disabled = !docViewState.allows(type, button.dataset.docView);
    button.title = button.disabled
      ? type.ext === "mmd" ? "A diagram has Picture, List, Split and Source." : `A .${type.ext} file has no rendered form, this is for markdown.`
      : button.dataset.docTitle || button.title;
  }
  //: A diagram's seg is Picture, List and Source (R7; Canvas and Blocks until INBOX 1661 i): the Edit and Read well gives way to it.
  if ($("doc-diagram-seg")) ($("doc-diagram-seg").hidden = type.ext !== "mmd", $("doc-view-seg").hidden = type.ext === "mmd");
  //: A diagram opens in Blocks the first time its type is synced after another type.
  const toDiagram = type.ext === "mmd" && docViewState.type !== "mmd";
  docViewState.type = type.ext;
  if (!docViewState.allows(type, docView) || toDiagram) setDocView(type.ext === "mmd" ? "canvas" : "source");
  //: And back: a markdown type again, and Source was only the code file's.
  else if (type.previewable && docViewState.held) setDocView(docDefaultView());
  //: The engine's own language and wrapping, where it is mounted.
  docCmSyncFileType();
  docCmApplySpellcheck();

  // The formatting toolbar is markdown syntax. In a .py file every button on
  // it inserts something wrong.
  $("doc-toolbar")?.classList.toggle("hidden", !type.previewable);
  if (typeof docSyncFormatShow === "function") docSyncFormatShow();
  //: And the other way round: Format lays out code, and has nothing to say
  //: to prose, plain text or a CSV. The pair swap in one place, so a
  //: document never shows both or neither.
  $("doc-code-format")?.classList.toggle("hidden", type.previewable || ["txt", "csv"].includes(type.ext));
  //: And the prose-only rows of the ⋯ menu: the image bundle, the Word file
  //: (`docCodeExportRefused`) and the heading map, which reads `#` lines. Print
  //: stays: a code file prints its own listing (`docCodePrintFill`).
  for (const id of ["doc-export-zip", "doc-export-docx", "doc-map-headings"]) $(id)?.classList.toggle("hidden", docIsCodeFile());
  $("doc-export-slides")?.classList.toggle("hidden", docIsCodeFile());
  //: Grid is the csv and tsv document's (documents-csvgrid.js); a grid still showing another file closes.
  for (const grid of document.querySelectorAll("#doc-csv-grid, [data-click-proxy=doc-csv-grid]")) grid.classList.toggle("hidden", type.ext !== "csv");
  if (docViewState.csvGrid?.isOpen() && (type.ext !== "csv" || docViewState.csvGrid.forDoc() !== (currentDoc?.id ?? null))) docViewState.csvGrid.close();
  $("doc-code-run")?.classList.toggle("hidden", !docRunnable(type));
  docRunSyncAvailability(type);
  //: Wrapping and whitespace are about a file that does not wrap by itself:
  //: every type but prose, plain text and CSV included (INBOX 402).
  for (const id of ["doc-code-wrap-row", "doc-whitespace-row", "doc-minimap-row"]) $(id)?.classList.toggle("hidden", type.previewable);

  // Line numbers, and the monospace/tab behaviour that goes with them.
  //: On the fallback textarea only. CodeMirror owns its own `class` and
  //: rewrites it on every focus change, so a class toggled onto the view's
  //: DOM is gone at the first focus; the engine's `doc-content-code` is
  //: declared through `editorAttributes` (documents-ide.js, `docIdeSlot`),
  //: mounted with the code tools on exactly the types this is true for.
  const code = !type.previewable;
  docBoxEl()?.classList.toggle("doc-content-code", code);
  $("tab-documents")?.classList.toggle("doc-is-code", code);
  //: A diagram's page is its own (INBOX 1679): the prose editor's Format, Assistant, Snippets, How to edit and Focus go (library-lazy.css), and the
  //: preview, which holds the builder, is no tab stop of its own, so Tab runs title, the seg, About, More, Add box, first block.
  $("tab-documents")?.classList.toggle("doc-is-diagram", type.ext === "mmd");
  if ($("doc-preview")) $("doc-preview").tabIndex = type.ext === "mmd" ? -1 : 0;
  //: The code panel (INBOX 788) comes back with a code file if it was open,
  //: and the sections tab with a prose document (INBOX 904 B18); its words
  //: and way in follow the type either way.
  const opener = $("doc-code-snippets-open");
  if (opener) {
    opener.title = code
      ? "Snippets: insert one at the caret, or save the selection as one"
      : "Sections: insert a ready-made block at the caret, or save the selection as one";
    opener.setAttribute("aria-label", code ? "Snippets" : "Sections");
  }
  //: Two prefs, because a code file left with its panel open must not open
  //: a column beside every prose document the person opens next.
  const sidePref = prefs.get(code ? "docCodeSide" : "docSectionsSide", "");
  if (sidePref) docCodeSideFrom(sidePref, true);
  else if (typeof docKit !== "undefined" && docKit.tab) docCodeSideClose();
  applyDocGutter();

  // A menu row, so it can say the whole thing rather than "⬇ .py".
  // `setLabel` because `textContent` here would wipe the icon element the
  // markup puts in front of the words.
  setLabel($("doc-export-md"), `ph:download-simple Download as .${type.ext}`);
  $("doc-export-md").title = `Download as a .${type.ext} file`;
  for (const id of ["doc-export-svg", "doc-export-picture", "doc-copy-picture"]) $(id)?.classList.toggle("hidden", type.ext !== "mmd");
  document.querySelector(".doc-diagram-export")?.classList.toggle("hidden", type.ext !== "mmd");
  //: A diagram's head menu keeps what is a verb on a diagram (Download first, Connections, History, Delete): the editor and writing
  //: switches, Read aloud and Extract notes mean nothing for a picture (OPEN W18, Q26: hide the file chrome).
  for (const el of [...(syncDocFileType.groups || []), $("doc-read-aloud"), $("doc-extract")]) el?.classList.toggle("hidden", type.ext === "mmd");

  //: **The prose check depends on the type, so a type change has to re-run
  //: it.** `openDocument` gets this through `renderDocTools`; changing the
  //: type of a document already open never did, and that was invisible while
  //: the findings only ever appeared in a panel nobody had open. They are
  //: drawn *on the document* now, so switching a markdown file to `.py` left
  //: squiggles under words in code until this ran: `renderDocProse` empties
  //: the findings for a code file, and the decorations go with them.
  if (prose) renderDocProse();
}

//: A diagram's Picture, List and Source (R7) are made the first time a diagram opens, not shipped in
//: the page (the boot element cap), on syncDocFileType, its one caller, not the shared scope; the stashed title and the click are what the page-load loop gives the others.
syncDocFileType.diagramSeg = function (seg) {
  if (!seg || seg.firstElementChild) return;
  for (const [mode, icon, label, title] of [
    ["canvas", "graph", "Picture", "Picture first: the drawing is wide, with a narrow list of its blocks beside it"],
    ["blocks", "list-bullets", "List", "List first: the blocks list is wide, with the drawing beside it"],
    ["source", "code", "Source", "The diagram as text, with its picture"],
  ]) {
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.docView = mode;
    button.title = title;
    button.dataset.docTitle = title;
    const glyph = document.createElement("i");
    glyph.className = `ph ph-${icon} ph-lead`;
    glyph.setAttribute("aria-hidden", "true");
    button.append(glyph, ` ${label}`);
    button.addEventListener("click", () => setDocView(mode));
    seg.append(button);
  }
  seg.addEventListener("keydown", (event) => {
    const step = { ArrowRight: 1, ArrowLeft: -1 }[event.key];
    const all = [...seg.children];
    const next = step && all[all.indexOf(document.activeElement) + step];
    if (!next) return;
    event.preventDefault();
    next.focus();
    next.click();
  });
};

// The dock's kebab closes when you pick something from it, and when you click
// away: `<details>` gives everything else (open on click and on Enter/Space,
// close on Escape, the ARIA) and neither of those two.
document.getElementById("doc-dock-menu")?.addEventListener("click", (event) => {
  //: Except the switches. Every other row here does one thing and is finished,
  //: so closing is right; a switch has a state, and a menu that shuts on the
  //: click hides the only feedback the switch gives you.
  if (event.target.closest(".doc-dock-menu-check")) return;
  if (event.target.closest(".doc-dock-menu-item")) {
    document.getElementById("doc-dock-menu").open = false;
  }
  //: A phone's row for a button the dock drops there (`data-click-proxy`, index.html) presses it,
  //: a task later: pressed inside this click, the page's outside-click close shut the help it opened.
  const proxy = event.target.closest("[data-click-proxy]")?.dataset.clickProxy;
  if (proxy) setTimeout(() => (document.getElementById(proxy) || document.querySelector(proxy))?.click());
});
document.addEventListener("click", (event) => {
  const menu = document.getElementById("doc-dock-menu");
  if (!menu?.open) return;
  //: The group flyouts are reparented to `<body>` while open (see
  //: `buildMenuGroupButton`), so a click inside one is not inside `menu` and
  //: the plain "clicked away" reading below would shut the whole thing before
  //: the row's own handler had run.
  const submenu = event.target.closest?.(".action-menu.submenu");
  if (submenu) {
    //: **And it is where a flyout row's close has to live**, for the same
    //: reason: nothing on the group or on `#doc-dock-menu` sees this click.
    //: The rules are the list's own, restated for rows that have moved into a
    //: flyout. A switch keeps the menu open, because a switch has a state you
    //: have to be able to see move and a menu that shuts on the click hides
    //: the only feedback it gives. A nested group opener is not a row. A row
    //: from one of *this* menu's flyouts closes it; one from some other
    //: menu's flyout is none of our business.
    if (!submenu.dataset.docDockSubmenu) return;
    if (event.target.closest(".doc-dock-menu-check")) return;
    if (!event.target.closest(".menu-item") || event.target.closest(".has-submenu")) return;
    menu.open = false;
    return;
  }
  if (menu.contains(event.target)) return;
  menu.open = false;
});

//: The formatting strip's menus (Highlight, Insert, the note strips' copies)
//: shut on a press anywhere outside them, the editor included: `<details>`
//: has no outside-press of its own and the click rule above is for the dock's
//: kebab, so a menu opened over the page stayed open while you typed
//: ("the highlight dropdown does not close on an outside press"). Capture,
//: because the editor's own mousedown handling stops the event bubbling. The
//: colour sheets are lists on `<body>`; a press in one is not outside.
//: The slash menu, pressed away from: a bare "/" that opened it is not text
//: the writer meant, so it comes back out. Capture, because the menu's own
//: outside-press (editor.js) closes it and forgets the box before this runs.
//: One with a word after it stays.
document.addEventListener(
  "mousedown",
  (event) => {
    const { open, textarea, trigger } = editorMenuState;
    if (!open || trigger !== "/" || !textarea || $("editor-menu")?.contains(event.target)) return;
    const bare = editorTokenAt(textarea, "/");
    if (bare && !bare.fragment) setTimeout(() => editorSplice(textarea, bare.start, bare.start + 1, ""), 0);
  },
  true
);
document.addEventListener(
  "pointerdown",
  (event) => {
    const open = document.querySelectorAll("details.doc-toolbar-menu[open]");
    if (!open.length || event.target.closest?.(".select-menu, .action-menu")) return;
    for (const menu of open) if (!menu.contains(event.target)) menu.open = false;
  },
  true
);

//: **Five download rows into one** (INBOX 262, the owner: "I want to combine
//: the "download as" options in it into a sub menu in that dropdown ... like
//: the ones in the meatball dropdowns in the your notes page").
//:
//: Measured before: the menu is 706px tall in a 900px window at 1440px wide,
//: 45 focusable rows, and on a taller, narrower window it runs to the bottom
//: edge with a scrollbar of its own, which is what the report's screenshot
//: shows. Four of those rows are the same verb.
//:
//: **The buttons are moved, not rebuilt.** They carry ids that this file
//: binds handlers to and that `test_frontend_ids` and
//: `test_frontend_handlers` both watch, so `buildMenuGroupButton` takes them
//: as elements. Everything else is the notes kebab's own group recipe: hover
//: or click to open, a flyout beside the row, an accordion at phone width,
//: clamped to the window on both axes.
//:
//: Built once, at load, rather than per open: these rows are static markup
//: and the groups are not rebuilt by anything.
function foldDocMenuGroup(label, ids) {
  const list = document.querySelector("#doc-dock-menu .doc-dock-menu-list");
  if (!list) return;
  const rows = ids.map((id) => document.getElementById(id)).filter(Boolean);
  if (rows.length < 2 || typeof buildMenuGroupButton !== "function") return;
  //: Already folded: this is called once at load, but a second call would
  //: otherwise wrap a group inside a group.
  if (rows[0].closest(".menu-group")) return;
  //: **A marker, because the group takes the rows with it.**
  //: `buildMenuGroupButton` appends each element into the flyout, so by the
  //: time it returns, `rows[0]` is no longer a child of this list and
  //: `insertBefore(group, rows[0])` throws `NotFoundError`. That throw is
  //: not local: this runs at the top level of documents.js, so it took the
  //: rest of the file's initialisation with it (`storageInfo`,
  //: `DOC_VIEWS_UNRENDERED` and `docCmView` all failed to initialise, and
  //: the editor would not open). A comment node holds the place instead.
  const marker = document.createComment("menu group");
  list.insertBefore(marker, rows[0]);
  const group = buildMenuGroupButton(label, rows);
  list.insertBefore(group, marker);
  marker.remove();
  //: **Marked, so the document-level handler below can recognise its own
  //: flyouts.** A listener on `group` is never called once the flyout is
  //: open, and that is not a subtlety worth rediscovering: `buildMenuGroupButton`
  //: reparents the panel to `<body>` so it can escape a clipping ancestor, so
  //: a click inside it does not bubble through the group at all. The first
  //: version of this bound the close to `group` and looked right; measured,
  //: clicking "Dim all but this paragraph" inside its flyout left the menu
  //: open, and so did every download row.
  const panel = group.querySelector(".action-menu.submenu");
  if (panel) panel.dataset.docDockSubmenu = "1";
  //: **The flyout's keys (audit D48).** These rows are the dock's own buttons and
  //: switches, which carry no `role`, so the group's Right and Arrow keys (menus.js,
  //: `[role="menuitem"]` rows) found none and the focus never left the group row.
  //: The switch rows are `<label>`s, so the walk takes a button or a shown label's
  //: input; the code-only labels stay `.hidden` on a prose document.
  const trigger = group.firstElementChild;
  const rowsOf = () => [...panel.querySelectorAll("button, label:not(.hidden) > input")].filter((row) => row.getClientRects().length);
  trigger.addEventListener("keydown", (event) => {
    if (["ArrowRight", "Enter", " "].includes(event.key)) rowsOf()[0]?.focus();
  });
  panel.addEventListener("keydown", (event) => {
    const down = event.key === "ArrowDown";
    if (!down && event.key !== "ArrowUp") return;
    const rows = rowsOf();
    rows[(rows.indexOf(document.activeElement) + (down ? 1 : rows.length - 1)) % rows.length]?.focus();
  });
  return group;
}

//: The dock menu's Escape and Tab, ahead of the capture handler in navigation.js
//: (a `window` capture listener runs before a `document` one). A group's flyout is
//: drawn at `<body>`, so the first Escape in one closed the whole menu under it and
//: left the flyout drawn; Tab walked off the end of the page. Both now close the
//: flyout (`closeActionMenus` puts the focus back on its group row), Escape from
//: inside one stops there, and Tab goes on from the group row.
window.addEventListener(
  "keydown",
  (event) => {
    if ((event.key !== "Escape" && event.key !== "Tab") || !$("doc-dock-menu")?.open) return;
    const inside = event.target.closest?.(".action-menu.submenu[data-doc-dock-submenu]");
    closeActionMenus();
    if (inside && event.key === "Escape") {
      event.preventDefault();
      event.stopPropagation();
    }
  },
  true
);

//: The diagram's two document controls are made here, not in index.html (CI: the boot document is capped at a
//: fixed element count and slice 8's button and row, with their icons, were four over). Same ids, classes, labels and
//: places as the markup had: New diagram right after New from a template, Download as .svg right before .png.
(() => {
  const add = (anchor, where, el) => anchor?.[where](el);
  if (!$("doc-new-diagram")) {
    const b = document.createElement("button");
    b.id = "doc-new-diagram";
    b.className = "ghost small icon-only";
    b.type = "button";
    b.title = "New diagram";
    b.setAttribute("aria-label", "New diagram");
    const i = document.createElement("i");
    i.className = "ph ph-flow-arrow";
    i.setAttribute("aria-hidden", "true");
    b.append(i);
    add($("doc-new-template"), "after", b);
  }
  if (!$("doc-export-svg")) {
    const row = document.createElement("button");
    row.id = "doc-export-svg";
    row.className = "menu-item doc-dock-menu-item hidden";
    row.type = "button";
    row.title = "Download the diagram as an SVG picture";
    setLabel(row, "ph:file-svg Download as .svg");
    add($("doc-export-picture"), "before", row);
  }
})();

//: **Three groups, because fourteen rows do not fit on a laptop.** Reported
//: twice: first that the menu "goes off the page", and after the downloads
//: were folded, that it "is still almost off the bottom of the screen".
//: Measured with the second report: the list is 562px of a 900px window at
//: 1440 wide, and at 1024x720 it runs 32px past the bottom edge.
//:
//: The groups are the ones the markup already argued for in its own comments,
//: not a fresh carve-up by row count. "What should be in front of you while
//: you write" is what the dim/typewriter/serif trio was built as, and the two
//: writing switches were put beside them for the same reason; they are one
//: group. What is left of the view rows is what the *editor* shows rather
//: than what the document is, so they are the other.
//:
//: `Connections`, `History`, `Extract notes` and `Delete document` stay in
//: the list: each is a verb on this document, none is a preference, and
//: hiding a one-off action behind a flyout costs a click every time to save a
//: row once.
//: **First in the list** (audit 1028 U32): taking a document out was the
//: ninth row, behind the layout switches. The rows keep their markup order;
//: the group is moved, so ids and handlers are untouched.
const docDownloadGroup = foldDocMenuGroup("ph:download-simple Download or print", [
  "doc-export-md", "doc-export-svg", "doc-export-picture", "doc-copy-picture", "doc-export-html", "doc-export-slides", "doc-export-zip", "doc-export-docx", "doc-export-pdf",
]);
docDownloadGroup?.parentElement?.prepend(docDownloadGroup);
syncDocFileType.groups = [foldDocMenuGroup("ph:layout Editor and layout", [
  "doc-format-toggle", "doc-width-menu", "doc-text-size", "doc-line-spacing", "doc-toolbar-mode", "doc-code-wrap-row", "doc-whitespace-row",
  "doc-minimap-row",
]), foldDocMenuGroup("ph:pencil-simple While you write", [
  "doc-paste-special", "doc-dim-others", "doc-typewriter", "doc-serif", "doc-margin-reader", "doc-autocorrect-row", "doc-complete-row",
])];

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

// DOC-SURFACE-BEGIN
// =============================================================================
// The editing surface, behind one adapter (DOCUMENTS_PLAN Phase 2 step 2)
// =============================================================================
//
// For most of this file's life the document *was* a `<textarea>`: forty-odd
// places spelled an edit as `$("doc-content").value.slice(...)` and a caret as
// `.selectionStart`, and that was fine while there was exactly one kind of
// box. Phase 2 puts CodeMirror 6 under the same editor, and a CodeMirror view
// has neither of those properties. The failure mode of getting this wrong is
// the quietest one this codebase has: the textarea stays in the DOM as the
// fallback, so every stale read *works*, it just answers with the text as it
// was before the real editor took over. Autosave then writes the old document
// back over the new one and nothing logs a thing.
//
// So: one adapter, and `tests/test_doc_surface.py` fails the build if a call
// site goes round it. `docSurface()` answers for whatever the document is
// being edited in right now; `textareaSurface(el)` wears the same interface
// over any other box (the note composer, the note edit form, a live-view
// paragraph), which is what lets the formatting toolbar, the "/" menu and the
// completion popup keep one implementation across all of them.
//
// **The interface is the plan's, plus the textarea's own names as aliases,
// and the aliases are deliberate.** `text` / `selection()` / `setSelection` /
// `replaceRange` / `onChange` / `coordsAt` / `focus` / `scrollTop` / `lineAt`
// are what the plan specifies and what new code should use. But the shared
// helpers in this file and in editor.js are written in `value` and
// `selectionStart`, they are correct, they are covered, and rewriting every
// line of them in the same commit that changes what is underneath is exactly
// how a refactor this size loses a case. The aliases mean those helpers
// become surface-agnostic by *receiving a surface instead of an element*,
// with no edit to their bodies: one small reviewable change each rather than
// forty rewritten expressions.

//: The CodeMirror view once it exists, null before the bundle has loaded and
//: null for good if it fails to. Read by `docSurface()` on every call, so the
//: hand-over is one assignment rather than a re-wiring pass.
let docCmView = null;

//: The fallback textarea itself. Named rather than looked up at each site
//: because a few things genuinely are about the *element*: its placeholder,
//: its disabled flag, the `doc-content-code` class and its line-number
//: column. Everything about the document's *text* goes through the surface
//: instead.
function docBoxEl() {
  return $("doc-content");
}

//: The empty-document prompt, kept here because the two engines spell it
//: differently: a textarea has a `placeholder` attribute, CodeMirror has a
//: placeholder extension that is built from this when the view is created.
let docPlaceholderText = "";

function docSetPlaceholder(text) {
  if (text === docPlaceholderText) return;
  docPlaceholderText = text;
  const el = docBoxEl();
  if (el) el.placeholder = text;
  //: CodeMirror builds its placeholder once; the compartment is how a later
  //: text (a code file's, a New caret's type) reaches the view.
  const CM = window.CM6;
  if (docCmView && CM && docCmParts.placeholder) {
    docCmView.dispatch({ effects: docCmParts.placeholder.reconfigure(CM.view.placeholder(text)) });
  }
}

//: What an empty page says, by the file type it holds (typepick-1031: an empty
//: .py file said "Markdown works here"). A blank page asks `docBlankPlaceholder`.
function docPlaceholderFor(type) {
  if (!currentDoc) return docBlankPlaceholder();
  if (type.previewable) return "# Start writing\n\nMarkdown works here, headings, **bold**, lists, tables, links.";
  return `An empty .${type.ext} file. Start typing, or paste ${type.label} here.`;
}

//: Surfaces are cached per element so `onChange` cannot stack a second
//: listener and so identity comparisons keep working across calls.
const docSurfaceCache = new WeakMap();

//: A textarea, wearing the surface interface.
function textareaSurface(el) {
  if (!el) return null;
  const cached = docSurfaceCache.get(el);
  if (cached) return cached;
  const surface = {
    el,
    kind: "textarea",
    id: el.id,
    isDocument: el.id === "doc-content",
    scrollEl: el,
    get text() { return el.value; },
    set text(next) { el.value = next; },
    //: The textarea's own names, see the section comment.
    get value() { return el.value; },
    set value(next) { el.value = next; },
    get selectionStart() { return el.selectionStart; },
    set selectionStart(at) { el.selectionStart = at; },
    get selectionEnd() { return el.selectionEnd; },
    set selectionEnd(at) { el.selectionEnd = at; },
    get classList() { return el.classList; },
    get dataset() { return el.dataset; },
    get scrollTop() { return el.scrollTop; },
    set scrollTop(at) { el.scrollTop = at; },
    get scrollHeight() { return el.scrollHeight; },
    get clientHeight() { return el.clientHeight; },
    selection() { return { from: el.selectionStart, to: el.selectionEnd }; },
    setSelection(from, to = from) { el.setSelectionRange(from, to); },
    setSelectionRange(from, to) { el.setSelectionRange(from, to); },
    setRangeText(text, from, to, mode) { el.setRangeText(text, from, to, mode); },
    //: Through the browser's own edit pipeline where it can be, so the native
    //: history survives: see `docReplaceRange`'s own comment.
    replaceRange(from, to, text) { docReplaceRange(surface, from, to, text); },
    onChange(fn) { el.addEventListener("input", fn); },
    coordsAt(pos) { return docMirrorPoint(el, pos); },
    lineAt(pos) {
      const text = el.value;
      const at = Math.max(0, Math.min(pos, text.length));
      const from = text.lastIndexOf("\n", at - 1) + 1;
      const found = text.indexOf("\n", at);
      const to = found === -1 ? text.length : found;
      return {
        number: text.slice(0, from).split("\n").length,
        from,
        to,
        text: text.slice(from, to),
      };
    },
    focus() { el.focus(); },
    blur() { el.blur(); },
    getBoundingClientRect() { return el.getBoundingClientRect(); },
    //: A programmatic write fires no `input`, and half this editor hangs off
    //: one. The name is the DOM's so the shared helpers need no edit.
    dispatchEvent(event) { return el.dispatchEvent(event); },
  };
  docSurfaceCache.set(el, surface);
  return surface;
}

//: The same interface over a CodeMirror view. Every write is a transaction,
//: which is what gives the editor one undo history for the whole document
//: instead of one per box: the thing PLAN D3's hand-rolled stack existed to
//: work around.
//: `meta` is what a *note* surface needs and the document does not: its own
//: id (`EDITOR_SURFACES` keys the "/" menu's context off it, and half the app
//: asks a surface what it is), and its own change handlers, because
//: `docSurfaceChangeHandlers` is the document's autosave pipeline and a note
//: box must not reach it. Absent, this is the document's own surface exactly
//: as it was (DOCUMENTS_PLAN Phase 8).
function cmSurface(view, meta = null) {
  const cached = docSurfaceCache.get(view);
  if (cached) return cached;
  const setRange = (from, to, insert, select) => {
    const length = view.state.doc.length;
    const start = Math.max(0, Math.min(from, length));
    const end = Math.max(start, Math.min(to, length));
    view.dispatch({
      changes: { from: start, to: end, insert },
      selection: select || undefined,
      scrollIntoView: true,
      annotations: docCmIsolate(),
    });
  };
  const surface = {
    get el() { return view.contentDOM; },
    kind: "codemirror",
    id: meta ? meta.id : "doc-content",
    isDocument: meta ? false : true,
    view,
    get scrollEl() { return view.scrollDOM; },
    get text() { return docStr(view.state.doc); },
    //: **The smallest change that gets there, not "the document is now this
    //: string".** Several callers still hand over a whole rebuilt document
    //: (the live view rewrites it on every keystroke, the AI panel replaces a
    //: passage by slicing). Dispatching that verbatim would make one history
    //: entry per keystroke that replaces the entire file, which costs
    //: proportional to the document on every character *and* makes Ctrl+Z
    //: undo the whole thing. The same prefix/suffix diff the D3 stack used.
    set text(next) {
      const current = docStr(view.state.doc);
      if (next === current) return;
      const [from, to, insert] = docUndoDiffRange(current, next);
      view.dispatch({ changes: { from, to, insert }, annotations: docCmIsolate() });
    },
    get value() { return this.text; },
    set value(next) { this.text = next; },
    get selectionStart() { return view.state.selection.main.from; },
    //: A textarea's rule: moving one end past the other drags it along.
    //: Without it start=12 then end=21 built 12..10, stored as 10..12, and
    //: Ctrl+B on nothing left `**bold text` selected (dogfood item 2).
    set selectionStart(at) { this.setSelection(at, Math.max(at, this.selectionEnd)); },
    get selectionEnd() { return view.state.selection.main.to; },
    set selectionEnd(at) { this.setSelection(Math.min(at, this.selectionStart), at); },
    get classList() { return view.dom.classList; },
    get dataset() { return view.dom.dataset; },
    get scrollTop() { return view.scrollDOM.scrollTop; },
    set scrollTop(at) { view.scrollDOM.scrollTop = at; },
    get scrollHeight() { return view.scrollDOM.scrollHeight; },
    get clientHeight() { return view.scrollDOM.clientHeight; },
    selection() {
      const range = view.state.selection.main;
      return { from: range.from, to: range.to };
    },
    setSelection(from, to = from) {
      const max = view.state.doc.length;
      const anchor = Math.max(0, Math.min(from, max));
      const head = Math.max(0, Math.min(to, max));
      view.dispatch({ selection: { anchor, head }, scrollIntoView: true });
    },
    setSelectionRange(from, to) { this.setSelection(from, to); },
    setRangeText(text, from, to, mode) {
      const at = from + text.length;
      const select =
        mode === "select"
          ? { anchor: from, head: at }
          : mode === "preserve"
            ? null
            : { anchor: at, head: at };
      setRange(from, to, text, select);
    },
    replaceRange(from, to, text) { setRange(from, to, text, null); },
    onChange(fn) { (meta ? meta.changeHandlers : docSurfaceChangeHandlers).push(fn); },
    coordsAt(pos) {
      const at = view.coordsAtPos(Math.max(0, Math.min(pos, view.state.doc.length)));
      if (!at) {
        //: `offscreen`, because the corner below is not where the position
        //: is: the engine has not laid that line out. A popup placed from it
        //: opens at the top of the editor (INBOX 421 c), so the popups ask
        //: for the caret to be brought into view instead.
        const box = view.dom.getBoundingClientRect();
        return { left: box.left, top: box.top, bottom: box.top + 18, lineHeight: 18, offscreen: true };
      }
      return { left: at.left, top: at.top, bottom: at.bottom, lineHeight: at.bottom - at.top };
    },
    //: Bring a position into the lines the engine has laid out, so
    //: `coordsAt` can answer for it (the "/" menu's use, `editorPositionMenu`).
    scrollIntoView(pos) {
      const CMx = window.CM6;
      if (!CMx) return;
      view.dispatch({
        effects: CMx.view.EditorView.scrollIntoView(Math.max(0, Math.min(pos, view.state.doc.length)), { y: "nearest" }),
      });
    },
    lineAt(pos) {
      const line = view.state.doc.lineAt(Math.max(0, Math.min(pos, view.state.doc.length)));
      return { number: line.number, from: line.from, to: line.to, text: line.text };
    },
    focus() { view.focus(); },
    blur() { view.contentDOM.blur(); },
    getBoundingClientRect() { return view.dom.getBoundingClientRect(); },
    //: **Nothing to dispatch, and that is not a stub.** Callers written for a
    //: textarea end a scripted write with an `input` event, because writing
    //: `.value` raises none and half this editor hangs off one. Every write
    //: through this adapter is a *transaction*, and the view's update
    //: listener has already run the same pipeline by the time this is
    //: reached: raising a synthetic event on a contenteditable would run it a
    //: second time and reset the autosave timer twice per edit. Returns true
    //: because that is what `dispatchEvent` means: nothing cancelled it.
    dispatchEvent() {
      return true;
    },
  };
  docSurfaceCache.set(view, surface);
  return surface;
}

//: Registered through `onChange` on a CodeMirror surface, and run by the
//: view's own update listener. A textarea surface registers the same
//: callbacks as real `input` listeners on the element, so the two engines
//: reach one pipeline by the same call.
const docSurfaceChangeHandlers = [];

function docSurfaceChanged() {
  for (const fn of docSurfaceChangeHandlers) fn();
}

//: **The document's editing surface, whatever it currently is.** Null only
//: before the markup exists, which is what keeps the `?.` at the call sites
//: honest rather than decorative.
function docSurface() {
  if (docCmView) return cmSurface(docCmView);
  return textareaSurface(docBoxEl());
}

//: **A document's text, read once per version** (audit 1028 D19). CodeMirror's
//: `Text.toString()` joins every line, so it costs the length of the document,
//: and one typed character used to ask for it 24 times (the facts pass, the
//: prose pass, the findings plugin, the autosave). A `Text` is immutable, so
//: the string is keyed by the object: every state has its own, the old ones are
//: collected with their states, and a second read is one map lookup.
const docStrCache = new WeakMap();
function docStr(doc) {
  let text = docStrCache.get(doc);
  if (text === undefined) {
    text = doc.toString();
    docStrCache.set(doc, text);
  }
  return text;
}

//: The document's text: the single most-read thing in this file.
function docText() {
  return docSurface()?.text ?? "";
}

//: A surface by box id, which is how the formatting toolbar and the "/" menu
//: address whichever editor they were mounted on. `doc-content` resolves to
//: the live surface rather than to the fallback element, so a toolbar press
//: reaches CodeMirror once it is mounted.
function docSurfaceById(id) {
  if (id === "doc-content") return docSurface();
  //: A board box being typed in has no element id (whiteboard.js, K24). Its answer is read, so no stand-in: without the boards bundle no board box exists to type in.
  const board = typeof wbEditorSurfaceById === "function" ? wbEditorSurfaceById(id) : null;
  if (board) return board;
  //: A note box that has mounted the engine (Phase 8) answers as its view for
  //: the same reason: the toolbar above it must write where the words are.
  const box = $(id);
  const mounted = typeof noteSurfaceFor === "function" ? noteSurfaceFor(box) : null;
  return mounted || textareaSurface(box);
}

//: Did this event come from inside the CodeMirror view? Asked in a handful of
//: delegated listeners that must not double up with the view's own update
//: listener.
function docEventFromCm(target) {
  return Boolean(docCmView && target instanceof Node && docCmView.dom.contains(target));
}

//: **One document-level listener per event type for what only the editor
//: needs** (audit 1028 D21). `input`, `selectionchange`, `mouseover` and the
//: rest were registered once each, for the life of the app, and ran on every
//: other tab: measured with the Documents bundle loaded and Notes on screen,
//: a pointer move cost 9.9 us against 3.6 us without it, a key 83 us against
//: 64 and a caret move 82 us against 40, each handler doing its own lookups
//: before finding the target was not an editor. Handlers that start from the
//: editor's own surface (`docToolsBoxFor`, `docEventFromCm`, a mark in the
//: view) register here instead: one listener per type and phase, which does
//: nothing while the Documents tab is hidden and otherwise runs them in the
//: order they were added. The table is a property of the function, as
//: `watchDocToolbarWidth` keeps its observer: the shared scope is capped.
function docListen(type, handler, capture = false) {
  docListen.table ||= new Map();
  const key = `${type}:${capture}`;
  let handlers = docListen.table.get(key);
  if (!handlers) {
    docListen.table.set(key, (handlers = []));
    document.addEventListener(
      type,
      (event) => {
        if ($("tab-documents")?.classList.contains("hidden")) return;
        //: Each as its own listener would have been: one that throws is reported, and the rest still run.
        for (const run of handlers) {
          try {
            run(event);
          } catch (error) {
            (window.reportError || console.error)(error);
          }
        }
      },
      capture
    );
  }
  handlers.push(handler);
}

//: An element, a surface, or nothing, as a surface. Call sites handed an
//: `event.target` need this; ones that already hold a surface pass through.
function asSurface(box) {
  if (!box) return null;
  if (box.kind === "textarea" || box.kind === "codemirror") return box;
  if (docCmView && box instanceof Node && docCmView.dom.contains(box)) return docSurface();
  //: A note editor that has mounted the engine (Phase 8): the textarea is
  //: still the form's value carrier and still the thing every caller holds,
  //: so it has to resolve to the view that is editing for it. Both
  //: directions, because a click lands in the view's own DOM and a handler
  //: holds the textarea.
  const mounted = typeof noteSurfaceFor === "function" ? noteSurfaceFor(box) : null;
  if (mounted) return mounted;
  return box instanceof HTMLTextAreaElement ? textareaSurface(box) : null;
}
// DOC-SURFACE-END

function setDocView(mode, { persist = true } = {}) {
  const type = docFileType();
  if (type.ext === "mmd" && (mode === "canvas" || mode === "blocks")) [docViewState.layout, mode] = [mode, "rendered"];
  // A code file has no rendered form, so it can only be one of the two views
  // that do not need one. Asked for any other, that is the honest answer
  // rather than an empty pane.
  if (!docViewState.allows(type, mode)) mode = type.ext === "mmd" ? "split" : "source";
  docView = DOC_VIEWS.includes(mode) ? mode : "source";
  //: Source in a code file is the file's only editing view, not a choice; a diagram's view is
  //: never stored, so the markdown documents after it open in the view the person chose.
  docViewState.held = !type.previewable && (docView === "source" || type.ext === "mmd");
  if (persist) try {
    if (!docViewState.held) prefs.set(DOC_VIEW_KEY, docView);
    //: Plain stored on a code file, then Source chosen back: Source is held (not stored), so the
    //: old "plain" outlived the choice and every later file opened uncoloured (L-documents-12).
    else if (docView === "source" && prefs.get(DOC_VIEW_KEY, null) === "plain") prefs.remove(DOC_VIEW_KEY);
  } catch {
    // A private window with storage blocked is not a reason to refuse to
    // change view: the choice just does not survive the reload.
  }

  // Where the editor was scrolled to, as a fraction, taken *before* anything is
  // hidden. syncDocScroll can't do this for the "rendered" hand-off: a hidden
  // textarea reports scrollHeight === clientHeight === 0, so its own zero-range
  // guard makes it a no-op and you land back at the top of a long document you
  // were halfway down.
  const editor = docSurface();
  //: Off the Documents tab the editor is hidden and reads 0: skipped, it forced a layout at load (27ms).
  //: Only Read uses it (below; the other views follow with `syncDocScroll`): read for
  //: every view it forced layout in the click that opens a document (INBOX 1530 c, 5 to 49 ms).
  const editorRange = editor && docView === "rendered" && prefs.get("activeTab", null) === "documents" ? editor.scrollHeight - editor.clientHeight : 0;
  const editorRatio = editorRange > 0 ? editor.scrollTop / editorRange : null;

  // The editor is on screen in every mode but Read; the preview is shown in
  // the two that include it. Only "split" gets the side-by-side class: in
  // "rendered" the preview is the sole child of a column flexbox and fills it
  // without any help.
  //
  //: **Live and Source are the same element now** (DOCUMENTS_PLAN Phase 2
  //: decision 3). The difference between them is one compartment: the
  //: markdown decorations are on in Live and off in Source. That is why this
  //: no longer hides the editor for Live, and why there is no second pane to
  //: keep in step with the first.
  $("doc-source-wrap").classList.toggle("hidden", docView === "rendered");
  //: Read by 09-editor.css: asked for directly, "the plain text view should
  //: be more like a vs code editor with a plain black or white background",
  //: which every other view (Live's decorations, Source's syntax colours)
  //: should not carry.
  $("doc-source-wrap").dataset.docView = docView;
  $("doc-preview").classList.toggle("hidden", !docPreviewShowing());
  $("doc-panes").classList.toggle("split", docView === "split");
  $("doc-panes").classList.toggle("reading", docView === "rendered");
  //: Nothing to format while reading (dogfood item 17); a code file never has the strip.
  $("doc-toolbar")?.classList.toggle("hidden", docView === "rendered" || !type.previewable);

  if (docView !== "rendered" && !docViewState.held) lastEditView = docView;
  for (const button of document.querySelectorAll("#doc-view-seg [data-doc-view], #doc-diagram-seg [data-doc-view], #doc-view-menu [data-doc-view]")) {
    // Edit is on for every mode that is not Read; the menu items behind
    // it mark the one editing mode in use.
    const mode = button.dataset.docView;
    const on = button.dataset.docViewGroup === "edit" ? docView !== "rendered" : mode === "canvas" || mode === "blocks" ? docView === "rendered" && docViewState.layout === mode : mode === docView;
    button.classList.toggle("active", on);
    button.setAttribute("aria-pressed", String(on));
    //: A diagram's Canvas, Blocks and Source are one tab stop (the chosen one), the arrows move between them.
    if (button.closest("#doc-diagram-seg")) button.tabIndex = on ? 0 : -1;
  }
  //: A view with none of the three on (Split) still leaves the seg reachable.
  const diagramSeg = $("doc-diagram-seg");
  if (diagramSeg?.firstElementChild && !diagramSeg.querySelector('[tabindex="0"]')) diagramSeg.firstElementChild.tabIndex = 0;

  if (docPreviewShowing()) {
    renderDocPreview();
    // Opening the preview on a document you have already scrolled into
    // should show the part you are looking at, not the top of the file.
    if (docView === "rendered") {
      const preview = $("doc-preview");
      const range = preview.scrollHeight - preview.clientHeight;
      if (editorRatio !== null && range > 0) preview.scrollTop = editorRatio * range;
    } else {
      syncDocScroll(editor);
    }
  }
  docSetLiveDecorations(docView === "live");
  //: The panel belongs to Live (Source shows the YAML itself, and Read renders
  //: it through the preview), so a view change is what puts it up or takes it
  //: down.
  renderDocProperties(true);
  //: Plain is the language compartment emptied, so entering *or leaving* it
  //: has to reconfigure that compartment. Routed through the same function the
  //: file-type change uses, so the two can never disagree about what a view is
  //: allowed to highlight.
  docCmSyncLanguage();
  //: And the gutter, for the same reason: Plain's default is "numbered"
  //: (docGutterWanted), so entering or leaving it changes what the engine
  //: should be showing. Without this the numbers only appeared on the next
  //: unrelated `applyDocGutter`, which reads as the setting not working.
  applyDocGutter();
  //: The engine caches the geometry it lays out with, and a view inside a
  //: `display: none` wrapper measures as zero. Asked for after the panes have
  //: been shown, for the same reason the gutter's metrics are.
  if (!$("doc-source-wrap").classList.contains("hidden")) docCmViewShown();
  //: After the panes have been shown and hidden, never before: the gutter's
  //: height is copied from a textarea that reports zeros while its wrapper is
  //: `display: none`.
  syncDocGutterMetrics();
}

async function loadDocuments(selectId = null) {
  warmDocumentEngine();
  if (docFactsStale && currentDoc) runDocFacts();
  //: Placeholders while it loads (INBOX 435 (6)); cleared on either answer.
  const sideList = document.getElementById("doc-list");
  showSkeletons(sideList, 4, "li");
  try {
    return await loadDocumentsNow(selectId);
  } finally {
    clearSkeletons(sideList);
  }
}

async function loadDocumentsNow(selectId) {
  //: Whether anything asked for a document since the loader last settled (a
  //: link to `#/docs/2`, New document), before or while this list loads: then
  //: that is the one to show, not the last.
  // Before the list, not after: the file-type table decides how the editor
  // behaves, and openDocument below reads it. Awaited rather than fired off,
  // so the picker is never briefly empty on the first visit to this tab.
  //: The list is asked for first and awaited after the table: two round trips that were in a row are side by side (L-documents-47, cold open).
  const listing = apiPagedList("/documents", DOCUMENTS_PAGE_SIZE).catch(() => null);
  await loadDocFileTypes();
  //: Paged, and read to the end: `GET /documents` hands back a page now
  //: (INBOX 117), and this list is not only the sidebar's eight rows. A
  //: `[[wiki link]]` resolves against `docs` by title (see
  //: `docLinkTargetFor`), so a document missing from it is a link that
  //: silently fails to resolve, not just a row missing from a list.
  //: A sentinel rather than `[]`, because an empty list and a failed request
  //: were the same value here and the sidebar said "No documents yet" for
  //: both. See `surfaceFailed` in navigation.js.
  const loaded = await listing;
  if (!loaded) {
    surfaceFailed(document.getElementById("doc-empty"), "your documents", () => loadDocuments(selectId));
    return;
  }
  surfaceRecovered(document.getElementById("doc-empty"));
  docs = loaded;
  renderDocList();
  //: Block embeds drawn before this list existed redraw now (documents-embeds.js `docEmbedFill`).
  document.dispatchEvent(new Event("docs-landed"));
  //: The loader's own opens count as settled, so only a person's request moves it.
  const asked = docOpenSeq !== docLoadSeen.seq;
  const opened = selectId ? selectId : !currentDoc && docs.length && !asked ? docs[0].id : null;
  const opening = opened ? openDocument(opened) : null;
  docLoadSeen.seq = docOpenSeq;
  offerKeptDocEdit(null);
  if (opening) return opening;
  if (!docs.length) showNoDocument();
}

//: How many documents the switcher shows. Searching and sorting all of them
//: is the Library's job (§36G); this list is here so the document you were in
//: ten minutes ago is one click away without leaving the page you are writing
//: on. The one you have *open* is always in it, however old, or the sidebar
//: would stop showing you where you are.
const RECENT_DOCS_SHOWN = 8;

function renderDocList() {
  const list = $("doc-list");
  list.replaceChildren();
  //: Last edited first, whatever order the list was fetched in: a save
  //: moves the row to the top without a refetch.
  const recent = [...docs].sort(
    (a, b) => String(b.updated_at || "").localeCompare(String(a.updated_at || "")) || b.id - a.id
  );
  const shown = recent.slice(0, RECENT_DOCS_SHOWN);
  if (currentDoc && !shown.some((d) => d.id === currentDoc.id)) {
    const open = docs.find((d) => d.id === currentDoc.id);
    if (open) shown[shown.length - 1] = open;
  }
  $("doc-empty").classList.toggle("hidden", docs.length > 0);

  for (const doc of shown) {
    const li = document.createElement("li");
    li.className = "doc-item";
    if (currentDoc && doc.id === currentDoc.id) li.classList.add("active");
    // A `<button>` the way this row used to be a `<button>` cannot also host
    // the kebab below: a button can't contain another button. Same
    // article-not-button shape renderLibraryDocuments() already uses for
    // exactly this reason, so the two Rename/Delete surfaces (this sidebar
    // and the Library's Documents sub-tab) look and behave the same way.
    // Reported: this list had never grown rename/delete at all, only Open.
    const button = document.createElement("div");
    button.className = "doc-item-button";
    button.setAttribute("role", "button");
    button.tabIndex = 0;
    const title = document.createElement("span");
    title.className = "doc-item-title";
    title.textContent = doc.title;
    //: The row is one line of title now, so a long one is cut with an
    //: ellipsis rather than wrapping the row to a second line. The whole
    //: title has to stay reachable, and the row is the thing under the
    //: pointer, so the tooltip goes on the row rather than on the span.
    button.title = doc.title || "Untitled";
    const meta = document.createElement("span");
    meta.className = "muted doc-item-meta";
    //: **What kind of file this is.** The list showed a word count and a
    //: time, so a .py and a .md were the same row: reported as part of the
    //: sidebar redesign. `file_type` is already in `GET /documents`'s summary
    //: (`_summary` in routes_documents.py), so this costs nothing, no second
    //: request and no per-row fetch.
    const type = document.createElement("span");
    type.className = "doc-item-type";
    type.textContent = `.${doc.file_type || "md"}`;
    meta.append(
      type,
      ` · ${docSizeText(doc)} · ${relativeTime(doc.updated_at)}`
    );
    button.append(title, meta);
    button.addEventListener("click", () => openDocument(doc.id));
    button.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" && event.key !== " ") return;
      event.preventDefault();
      openDocument(doc.id);
    });

    const menu = kebabMenu(
      [
        makeMenuItem("ph:pencil-simple Rename", "Rename this document", async () => {
          const next = await promptDialog("Rename this document", doc.title || "");
          if (!next || next === doc.title) return;
          await renameDocumentWithUndo(doc, next).catch((e) => toast(e.message, true));
        }),
        //: INBOX 904 B17: the model names it when one runs, else the document's
        //: own words do; renamed through Rename's undoable path.
        makeMenuItem("ph:sparkle Suggest a name", "A name from what the document says", async () => {
          const got = await apiJson(`/documents/${doc.id}/suggest-title`, { method: "POST" }).catch((e) => toast(e.message, true));
          if (got?.title && got.title !== doc.title) await renameDocumentWithUndo(doc, got.title).catch((e) => toast(e.message, true));
        }),
        appLinkMenuItem("document", doc.id),
        // Not destructive, so not grouped with Delete below, same
        // "keep it, but out of the way" action the Notes tab already has
        // for entries (BACKLOG §30b's named remaining scope: chats and
        // documents). Reachable again from the Library's Shelved filter.
        makeMenuItem("ph:archive Archive", "Keep it, but out of the way, not deleted", async () => {
          await archiveDocumentWithUndo(doc).catch((e) => toast(e.message, true));
        }),
        makeMenuItem("ph:trash Delete", "Delete this document", async () => {
          if (
            !(await confirmDialog(
              `Delete "${doc.title || "Untitled"}"? You can undo this straight after.`
            ))
          ) {
            return;
          }
          await deleteDocumentWithUndo(doc).catch((e) => toast(e.message, true));
          // Cleared, not just left stale: loadDocuments() only opens a
          // replacement when `currentDoc` is falsy - leaving it pointing at
          // the doc that was just deleted would keep the editor showing it.
          if (currentDoc && currentDoc.id === doc.id) currentDoc = null;
          loadDocuments(currentDoc?.id);
        }),
      ],
      `Actions for "${doc.title || "Untitled"}"`, { vertical: true });
    menu.classList.add("doc-item-menu");
    menu.addEventListener("click", (event) => event.stopPropagation());
    // Same clipping shape as the Library's own Documents-subtab kebab, a
    // scrolling list of rows with a `position: absolute` popup on the last
    // few. `kebabMenu()` now escapes every menu it builds, so this list gets
    // the fix without its own call.

    li.append(button, menu);
    list.appendChild(li);
  }
}

function showNoDocument() {
  currentDoc = null;
  docTypeState.pending = null;
  $("doc-title").value = "";
  docResetDocument("");
  // Deliberately NOT disabled. Disabling them meant that on a notebook with no
  // documents yet, clicking the editor did nothing and typing did nothing, 
  // a dead end whose only way out was noticing a small "+ New" button. Typing
  // now creates the document, which is what every editor does.
  $("doc-title").disabled = false;
  docBoxEl().disabled = false;
  docSetPlaceholder(docBlankPlaceholder());
  $("doc-saved").textContent = "";
  renderDocPreview();
  renderDocStats();
  renderDocOutline();
  renderDocProperties();
  renderDocComments();
  document.dispatchEvent(new CustomEvent("doc-shown", { detail: null }));
  //: **A new empty page opens to write in** (audit 1028 U8). A phone's default
  //: is Rendered, where the first tap on a blank page did nothing. Not stored:
  //: the next document still opens the way the person last chose.
  if (docView === "rendered") setDocView("live", { persist: false });
}

//: Runs `paint` once the frame with the new text has been drawn, if no later
//: open has started since (`docOpenSeq`).
function docAfterFirstPaint(seq, paint) {
  requestAnimationFrame(() =>
    setTimeout(() => {
      if (seq === docOpenSeq) paint();
    }, 0)
  );
}

async function openDocument(id) {
  //: Opened from a link in a document (an embedded diagram, a [[link]]): the dock's crumb names that document instead of the Library (dgbt-1109 13).
  //: A caller says so with `openDocument.back = true` on the line before its call; read and cleared here, before anything awaits.
  const from = openDocument.back && currentDoc && currentDoc.id !== id ? { id: currentDoc.id, title: currentDoc.title || "Untitled" } : null;
  openDocument.back = false;
  //: **Only the newest call opens** (tests/test_new_document_opens_new.py):
  //: the tab's loader opening the last document and New document opening
  //: the one it just made race, and the fetch that landed last won, leaving
  //: a person typing into an old document they took for the new one.
  const seq = ++docOpenSeq;
  //: The block bar belongs to the page being left: opened from a link under the pointer, nothing fires mouseleave, and it hung over the new page.
  docBlockBarClose();
  //: The place being left is written down first, while the surface still
  //: holds that document (see `docRememberPositionNow`).
  docRememberPositionNow();
  // Never lose unsaved work by switching away from it.
  //: A document waiting on its conflict asks now (not silently): leaving is
  //: the moment the answer is owed, and the banner is about to go.
  if (docDirty) await saveDocument({ silent: !docConflictPending });
  //: A document restored with the page can get here while the Library bundle is still loading; the files later in it (documents-tabs.js, margin-reader.js)
  //: are reached by the steps below (INBOX 1530 f). The board code is not in this bundle (`boards`).
  await ensureModule("library");
  docConflictPending = null;
  await docDropIfUntouched(id);
  //: **The engine is loaded here, and this is the only place it is.** Awaited
  //: before the text is handed over, so the document goes straight into
  //: CodeMirror rather than into the fallback and then into a view mounted a
  //: moment later, which is how the two would disagree on the very first
  //: paint. Failing is not an error path: `ensureDocEditor` resolves to null
  //: and everything below carries on against the textarea.
  //: The document is fetched while the bundle loads, not after it (L-documents-47).
  const fetching = apiJson(`/documents/${id}`).catch(() => null);
  await ensureDocEditor();
  const doc = await fetching;
  if (seq !== docOpenSeq) return;
  //: A fetch that failed says so (audit 1028 D35): the editor stays on the
  //: document it had, and the list goes back to marking that one.
  if (!doc) {
    toast("Couldn't open that document. The one on screen is unchanged.", true, { action: ["Try again", () => openDocument(id)] });
    renderDocList();
    return;
  }
  // ROADMAP.md item 13: "opening/closing a document" was the one remaining
  // gap in back/forward nav after chat's own conv:<id> fix. Same shape,
  // recorded here (not at each of openDocument's several call sites) so
  // none of them has to remember to, same reasoning openConversation's own
  // comment gives for doing it there instead of at ITS call sites.
  recordTabVisit("documents", `doc:${doc.id}`, doc.title || "Untitled document");
  currentDoc = doc;
  const crumb = $("doc-back");
  if (crumb) {
    crumb.dataset.from = from ? from.id : "";
    crumb.querySelector(".doc-back-label").textContent = from ? from.title : "Documents";
    crumb.title = from ? `Back to ${from.title}` : "Back to your documents in the Library";
    crumb.setAttribute("aria-label", crumb.title);
  }
  $("doc-title").disabled = false;
  docBoxEl().disabled = false;
  $("doc-title").value = doc.title;
  docResetDocument(doc.content, doc.id, { repaint: false });
  scheduleUndoBar();
  docDirty = false;
  $("doc-saved").textContent = "Saved";
  // Before the renders below: it decides which of them are even reachable
  // (a code document has no Live or Split) and puts the editor into the
  // right mode first, so nothing paints twice.
  syncDocFileType({ prose: false });
  renderDocPreview();
  renderDocStats();
  renderDocProperties();
  //: **The first screen first** (DOCUMENTS 25 row 7). The prose check, the
  //: outline and the side panels belong to the document and are repainted
  //: with it, a frame after the text is painted rather than before: each
  //: lays the editor out again (the outline asks which line the caret shows),
  //: measured at 390 as 607ms of a 1,286ms open for the outline alone.
  //: The outline first: it reads where the caret is before anything here
  //: writes (INBOX 1530 c), and the status bar and prose check need no layout.
  docAfterFirstPaint(seq, () => {
    renderDocOutline();
    renderDocTools();
    renderDocNotes();
    renderDocBacklinks();
    renderDocBookmarks();
    renderDocComments();
  });
  renderDocList();
  document.dispatchEvent(new CustomEvent("doc-shown", { detail: doc }));
  //: Before the place is restored, which stays last (tests/test_doc_long.py).
  offerKeptDocEdit(doc);
  docRestorePosition(doc.id);
}

//: **A document reopens where you left it.** Measured before this existed
//: (`docreturn.js`): a 21k-word document left at 20,000px with the caret there
//: reopened at scrollTop 0 and caret 0, and a reload did the same, so every
//: return to a long document began with finding the place again.
//:
//: What is kept is the caret and the *position at the top of the view* (a
//: character offset, not a pixel count): CodeMirror estimates the height of
//: lines it has not drawn, so a pixel scrollTop restored into a fresh view
//: lands somewhere else once the lines are measured, while an offset is
//: scrolled to by the engine's own scroll target, which it keeps re-applying
//: until the heights settle. Per document, in this browser (`localStorage`,
//: one map, the sixty most recent): it is how a person reads, not a property
//: of the file, so it must not travel in the document or reach a backup. A
//: document nobody has left, a position at the very top, and the textarea
//: fallback (no line-to-pixel map to take either number from) store and
//: restore nothing.
const DOC_POSITIONS_KEY = "doc-positions";
const DOC_POSITIONS_MAX = 60;
let docPositionTimer = 0;

function docPositionsRead() {
  try {
    const value = prefs.json(DOC_POSITIONS_KEY, {});
    return value && typeof value === "object" && !Array.isArray(value) ? value : {};
  } catch {
    return {};
  }
}

function docPositionsWrite(map) {
  const keys = Object.keys(map);
  if (keys.length > DOC_POSITIONS_MAX) {
    keys.sort((a, b) => (map[b].at || 0) - (map[a].at || 0));
    for (const stale of keys.slice(DOC_POSITIONS_MAX)) delete map[stale];
  }
  try {
    prefs.set(DOC_POSITIONS_KEY, JSON.stringify(map));
  } catch {
    // Storage blocked or full: the document just opens at the top, as before.
  }
}

//: The offset of the first character in view. `posAtCoords` with `precise`
//: false never returns null, so a short document answers 0.
function docTopOffset(view) {
  const rect = view.scrollDOM.getBoundingClientRect();
  if (rect.height < 1) return null;
  const pos = view.posAtCoords({ x: rect.left + 4, y: rect.top + 4 }, false);
  return Number.isFinite(pos) ? pos : null;
}

function docRememberPositionNow() {
  clearTimeout(docPositionTimer);
  docPositionTimer = 0;
  if (typeof currentDoc === "undefined" || !currentDoc?.id) return;
  const box = docSurface();
  //: Not while the editor is hidden (Read view): it measures 0x0 and would
  //: overwrite the real place with the top.
  if (!box || box.kind !== "codemirror" || box.view.scrollDOM.getBoundingClientRect().height < 1) return;
  const head = box.selection().from;
  const top = docTopOffset(box.view);
  if (top === null) return;
  const map = docPositionsRead();
  if (!head && !top) delete map[currentDoc.id];
  else map[currentDoc.id] = { head, top, at: Date.now() };
  docPositionsWrite(map);
}

//: Trailing, so a scroll or a held arrow key is one write when it stops, not
//: sixty a second.
function docRememberPosition() {
  if (docPositionTimer) return;
  docPositionTimer = setTimeout(docRememberPositionNow, 600);
}

//: A reload or a closed tab inside the 600ms is one more write, not a lost one.
window.addEventListener("pagehide", docRememberPositionNow);

//: **Words typed in the last 1.2 s survive a reload** (INBOX 648, the owner:
//: "unsaved edits survive tab switch, reload and restart"; measured by
//: tests-e2e/specs/documents.spec.js). Autosave waits for a pause, and a
//: Leave inside that pause, a closed desktop window (which asks nothing), or
//: a save the server refused ("Not saved") lost the newest words for good.
//: The text is kept on this device at that moment, dropped by the next save
//: that lands, and offered back the next time that document opens, the same
//: shape as the note form's kept edit (note-edit-panels.js).
//: One kept copy per document (audit 1028 D5): a single slot let a failed
//: save of one document be overwritten by the next. At most five, each for
//: two weeks and 2 MB (D4): documents carry no private flag and sit as plain
//: text on this computer's disk already, so a lock keeps them rather than
//: losing the words it exists to keep.
const DOC_EDIT_KEPT = "doc-edit-drafts";
const DOC_KEPT_MAX = 5;
const DOC_KEPT_DAYS = 14;

function docKeptDrafts() {
  let all = {};
  try {
    all = prefs.json(DOC_EDIT_KEPT, {}) || {};
  } catch {
    all = {};
  }
  const cutoff = Date.now() - DOC_KEPT_DAYS * 864e5;
  const stale = Object.keys(all).filter((id) => !(all[id]?.at > cutoff));
  for (const id of stale) delete all[id];
  //: Gone from storage too, not only from the offer.
  if (stale.length) prefs.setJSON(DOC_EDIT_KEPT, all);
  return all;
}

//: **A document not yet made keeps its words too** (audit 1028 D3): typing into
//: the blank page makes the row on the first key, and a refused or offline POST
//: left the words nowhere. Kept under the id "new" with the file type the page
//: was opened for; the first create that lands forgets it.
function keepDocEditLocally() {
  if (!currentDoc ? false : !docDirty) return;
  const content = docText();
  if (content.length > 2e6) return;
  try {
    const all = docKeptDrafts();
    if (!currentDoc) {
      if (!content.trim() && !$("doc-title").value.trim()) return;
      all.new = { id: "new", title: $("doc-title").value, content, at: Date.now(), type: docTypeState.pending || null };
      const recent = Object.values(all).sort((a, b) => b.at - a.at).slice(0, DOC_KEPT_MAX);
      return prefs.setJSON(DOC_EDIT_KEPT, Object.fromEntries(recent.map((kept) => [kept.id, kept])));
    }
    //: `base`: the hash of the server text this was typed over, so a later open can tell the copy is the newer (DX31).
    all[currentDoc.id] = { id: currentDoc.id, title: $("doc-title").value, content, at: Date.now(), base: currentDoc.content_hash };
    const newest = Object.values(all).sort((a, b) => b.at - a.at).slice(0, DOC_KEPT_MAX);
    prefs.setJSON(DOC_EDIT_KEPT, Object.fromEntries(newest.map((kept) => [kept.id, kept])));
  } catch {
    /* storage full or blocked: nothing more can be done at unload */
  }
}

function forgetDocEditLocally(id) {
  try {
    const all = docKeptDrafts();
    if (!(id in all)) return;
    delete all[id];
    if (Object.keys(all).length) prefs.setJSON(DOC_EDIT_KEPT, all);
    else prefs.remove(DOC_EDIT_KEPT);
  } catch {
    /* nothing kept, nothing to forget */
  }
}

window.addEventListener("pagehide", keepDocEditLocally);

//: Called by openDocument once the document is on screen. A kept copy whose
//: text is already the document's is dropped without a word. One typed over
//: the text the server still holds (`base` is its `content_hash`) is the newer
//: by construction, so it goes straight into the editor, as an edit that the
//: ordinary autosave saves, with Undo in the toast (DX31: a fast reload showed
//: the older text until a button was pressed). Any other is offered, not
//: applied: the server has moved on since, and which text wins is the
//: writer's to say.
function offerKeptDocEdit(doc) {
  //: No document: the unsaved new one, once per page load (`loadDocuments`). It comes back
  //: as a new page filled with its words, saved by the ordinary autosave.
  if (!doc) {
    const fresh = docKeptDrafts().new;
    if (!fresh || docSaveQueue.newOffered) return;
    docSaveQueue.newOffered = true;
    if (!fresh.content?.trim() && !fresh.title?.trim()) return forgetDocEditLocally("new");
    toastAction(`Your unsaved new document \u201c${clipText(fresh.title || "Untitled", 40)}\u201d was kept.`, "Put it back", async () => {
      await startBlankDocument(fresh.type);
      if (currentDoc) return;
      if (fresh.title) $("doc-title").value = fresh.title;
      const box = docSurface();
      if (box) docReplaceRange(box, 0, docText().length, String(fresh.content || ""));
      markDocDirty();
    });
    return;
  }
  const kept = docKeptDrafts()[doc.id];
  if (!kept) return;
  if (kept.content === doc.content && (kept.title || "") === (doc.title || "")) {
    forgetDocEditLocally(doc.id);
    return;
  }
  const put = (title, content) => {
    const box = docSurface();
    if (!currentDoc || currentDoc.id !== kept.id || !box) return false;
    if (title) $("doc-title").value = title;
    docReplaceRange(box, 0, docText().length, String(content || ""));
    return true;
  };
  const name = clipText(kept.title || "Untitled", 40);
  if (kept.base && kept.base === doc.content_hash) {
    if (!put(kept.title, kept.content)) return;
    markDocDirty();
    toastAction(`Restored your unsaved changes to \u201c${name}\u201d.`, "Undo", () => {
      if (!put(doc.title, doc.content)) return;
      forgetDocEditLocally(doc.id);
      clearTimeout(docSaveTimer);
      docDirty = false;
      $("doc-saved").textContent = "Saved";
    });
    return;
  }
  toastAction(`Your unsaved changes to \u201c${name}\u201d were kept.`, "Put them back", () => {
    if (put(kept.title, kept.content)) markDocDirty();
  });
}

function docRestorePosition(id) {
  const box = docSurface();
  const CM = window.CM6;
  if (!box || box.kind !== "codemirror" || !CM) return;
  const saved = docPositionsRead()[id];
  if (!saved) return;
  const view = box.view;
  const max = view.state.doc.length;
  const head = Math.max(0, Math.min(Number(saved.head) || 0, max));
  const top = Math.max(0, Math.min(Number(saved.top) || 0, max));
  if (!head && !top) return;
  view.dispatch({
    selection: { anchor: head },
    effects: CM.view.EditorView.scrollIntoView(top, { y: "start", yMargin: 0 }),
  });
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

//: One request at a time, and the last one wins. Switching documents quickly
//: used to be safe because this was synchronous over `allEntries`; it is a
//: fetch now, and two in flight would paint the slower one's answer under the
//: faster one's document. The same shape `renderDocBookmarks` uses.
let docBacklinksToken = 0;

//: **Link back: insert `[[Source]]` at the caret.** Deliberately the caret and
//: not the end of the document: every other insert in this editor (the "/"
//: menu, the table command, the properties command) writes where you are, and
//: an action that alone appended to the bottom would be the one place in the
//: editor where "insert" means something else.
function docInsertReferenceLink(bookmark) {
  const surface = docSurface();
  if (!surface) return;
  // Brackets would end the link text early, and a space or ")" the url.
  const text = String(bookmark.title || bookmark.url).replace(/[[\]]/g, "");
  const url = String(bookmark.url).replace(/ /g, "%20").replace(/\)/g, "%29");
  docReplaceRange(surface, surface.selectionStart, surface.selectionEnd, `[${text}](${url})`);
  markDocDirty();
  surface.focus();
}

async function renderDocBacklinks() {
  const wrap = $("doc-backlinks-wrap");
  const list = $("doc-backlinks");
  if (!wrap || !list) return;
  const token = ++docBacklinksToken;
  let body = null;
  if (currentDoc?.id != null) {
    body = await apiJson(`/documents/${currentDoc.id}/backlinks`, { silent: true }).catch(() => null);
  }
  if (token !== docBacklinksToken) return; // a newer document answered first
  const links = (body && body.links) || [];
  const mentions = (body && body.mentions) || [];
  //: Nothing to draw and nothing drawn before: the panel stays hidden without fetching its code
  //: (documents-backlinks.js). Rows drawn for the last document are cleared by the piece.
  if (!links.length && !mentions.length && !list.firstChild && !wrap.parentElement?.querySelector(".doc-mentions-wrap")) {
    wrap.classList.add("hidden");
    return;
  }
  if (!(await lazyScript("/js/documents-backlinks.js"))) return toast("The links panel could not be loaded.", true, { action: ["Try again", renderDocBacklinks] });
  if (token === docBacklinksToken) docBacklinksPaint(links, mentions);
}

// The notes this document draws on. Shown beside the outline because both
// answer the same question, what is this document made of.
function renderDocNotes() {
  const wrap = $("doc-notes-wrap");
  const list = $("doc-notes");
  const notes = (currentDoc && currentDoc.notes) || [];
  wrap.classList.toggle("hidden", !notes.length);
  list.replaceChildren();
  for (const note of notes) {
    const item = document.createElement("li");
    const open = document.createElement("button");
    open.type = "button";
    open.className = "outline-link";
    if (note.is_private) {
      setLabel(open, "ph:lock (private note)");
    } else {
      renderInlineMarkdown(open, note.preview, [], true);
    }
    open.title = "Show this note";
    open.addEventListener("click", () => {
      switchTab("notes");
      showNotesSection("browse"); // focusing inside a hidden section does nothing
      flashEntry(note.id);
    });
    const remove = smallButton("ph:x", "Detach this note from the document", () =>
      unlinkDocNoteWithUndo(note).catch((e) => toast(e.message, true))
    );
    item.append(open, remove);
    list.appendChild(item);
  }
}

// References (§30): saved links attached to this document, the Documents
// half of the same concept notes' own edit form already got this session.
async function renderDocBookmarks() {
  const list = $("doc-bookmarks");
  if (!list || !currentDoc) return;
  let attached;
  try {
    attached = await apiJson(`/documents/${currentDoc.id}/bookmarks`);
  } catch {
    return;
  }
  if (currentDoc?.id == null) return; // the document changed while this was in flight
  list.replaceChildren();
  for (const bookmark of attached) {
    const item = document.createElement("li");
    //: **One row per reference** (the owner, 2026-10-10: "references ... with
    //: the buttons on them"): its icon and title, then two icon buttons that
    //: lie over the row's right end only while the row is pointed at or
    //: focused (always on touch), so a long title keeps its width at rest.
    //: Earlier a link chip, an "Aa" and an X sat loose beside each other.
    item.className = "doc-outline-row doc-ref-row";
    const open = document.createElement("button");
    open.type = "button";
    open.className = "outline-link";
    setLabel(open, `ph:link ${bookmark.title || bookmark.url}`);
    open.title = bookmark.url;
    // safeHref() (notes-list.js): the same scheme guard library.js's bookmark rows
    // use, so a bookmark saved before INBOX 310's write-time check existed
    // can't reach window.open() with an unlisted scheme from here either.
    open.addEventListener("click", () => window.open(safeHref(bookmark.url), "_blank", "noopener,noreferrer"));
    //: **Into the text, not only beside it** (owner, 0.3.31: "how do I
    //: hyperlink or attach bookmark references in a document??"). Writes
    //: `[title](url)` at the caret, the way `docLinkBack` writes `[[Source]]`:
    //: every insert in this editor goes where you are.
    const insert = smallButton("ph:cursor-text", "Insert a link to it at the caret", () =>
      docInsertReferenceLink(bookmark)
    );
    const remove = smallButton("ph:link-break", "Remove it from this document", () =>
      docBookmarkWithUndo(bookmark.id, false).catch((e) => toast(e.message, true))
    );
    const tools = document.createElement("span");
    tools.className = "doc-ref-tools";
    for (const button of [insert, remove]) button.classList.add("icon-only", "doc-outline-row-action");
    tools.append(insert, remove);
    item.append(open, tools);
    list.appendChild(item);
  }
}

async function attachBookmarkToDocument() {
  if (!currentDoc) return;
  let all;
  try {
    all = await apiJson("/bookmarks");
  } catch (error) {
    toast(error.message, true);
    return;
  }
  if (!all.length) {
    toast("No saved bookmarks yet, add one in Library → Bookmarks first.");
    return;
  }
  const wrap = $("doc-bookmarks-wrap");
  //: **The picker and its way out are one row, and it replaces the button
  //: that opened it.** Before this the select was inserted above a
  //: still-visible "Attach a link", so asking to attach one left two
  //: full-width controls stacked with no way to change your mind but to pick
  //: something: the other half of "References stacks a close button above its
  //: own select". Opening it twice also stacked two selects, because nothing
  //: checked for one already there.
  const existing = wrap.querySelector(".doc-attach-row");
  //: The row's Escape listener goes with it: removing the row alone left the document-level one
  //: behind for every reopen (L327). One controller per picker, kept on this function.
  attachBookmarkToDocument.escape?.abort();
  if (existing) existing.remove();
  const row = document.createElement("div");
  row.className = "row doc-attach-row";
  const select = document.createElement("select");
  select.className = "bookmark-attach-picker";
  const placeholder = document.createElement("option");
  placeholder.textContent = "Pick a saved bookmark…";
  placeholder.value = "";
  select.appendChild(placeholder);
  for (const bookmark of all) {
    const option = document.createElement("option");
    option.value = String(bookmark.id);
    option.textContent = bookmark.title || bookmark.url;
    select.appendChild(option);
  }
  const escape = new AbortController();
  attachBookmarkToDocument.escape = escape;
  const close = () => {
    escape.abort();
    row.remove();
    $("doc-attach-bookmark").classList.remove("hidden");
    $("doc-attach-bookmark").focus();
  };
  //: Escape as well as the ✕, because a picker that opened on a button press
  //: is the shape everyone tries Escape on first.
  //:
  //: **On the document, not on the `<select>` or even on the row.**
  //: `enhanceSelect` in sheets-selects.js replaces every select in the page with a shell
  //: holding a `<button>` opener and a listbox, and takes the real select out
  //: of the tab order (`select-native-hidden`, `tabindex="-1"`), so the
  //: `select.focus()` below lands nowhere and the keystroke is dispatched at
  //: `document.body`. A listener on the element never fired; one on the row
  //: never fired either, because the event's target was outside it. Both were
  //: caught by measuring, not by reading: the sweep pressed Escape twice and
  //: the picker stayed open twice, and the row's children read back as SPAN
  //: and BUTTON rather than SELECT and BUTTON. Removed again in `close`, so
  //: nothing outlives the picker.
  function onEscape(event) {
    if (event.key !== "Escape") return;
    //: Only when the listbox is shut. Escape inside an open listbox is that
    //: menu's own way out, and taking it would close the picker from under
    //: someone who was only backing out of the list.
    if (row.querySelector('[aria-expanded="true"]')) return;
    event.preventDefault();
    close();
  }
  document.addEventListener("keydown", onEscape, { capture: true, signal: escape.signal });
  select.addEventListener("change", async () => {
    if (!select.value || !currentDoc) return;
    await docBookmarkWithUndo(Number(select.value), true).catch((e) => toast(e.message, true));
    close();
  });
  const cancel = smallButton("ph:x", "Don't attach a link", close);
  cancel.classList.add("doc-outline-row-action");
  row.append(select, cancel);
  wrap.insertBefore(row, $("doc-attach-bookmark"));
  $("doc-attach-bookmark").classList.add("hidden");
  //: `focusSelect` (sheets-selects.js), which is where this trap and its answer now live
  //: together. It was open-coded here first, before a sweep of the rest of the
  //: app found three more call sites doing the plain `.focus()` silently.
  focusSelect(select);
}

//: **Templates: a starting shape for the five documents people make most.**
//: Plain markdown with two placeholders; the whole feature is these strings,
//: the dialog in index.html and `createDocument(template)` below. Kept as
//: data rather than a server resource because a template is nothing but
//: text, and text that lives in one file is text a fresh session can read.
const DOC_TEMPLATES = [
  {
    id: "blank", title: "Blank", hint: "An empty page.", content: "",
  },
  {
    id: "lecture", title: "Lecture notes", hint: "Cornell-style: cues, notes, summary.",
    content: "# {{title}}\n\n**Date:** {{date}}\n**Unit / lecturer:** \n\n## Key questions\n\n- \n\n## Notes\n\n\n## Terms\n\n| Term | Meaning |\n| --- | --- |\n|  |  |\n\n## Summary (three sentences)\n\n\n## To follow up\n\n- [ ] \n",
  },
  //: The writing staples (audit 1102 DX30): the gallery had no letter, report,
  //: essay, CV or one-pager, the five a word processor opens with.
  {
    id: "letter", title: "Letter", hint: "Date, greeting, body and sign-off.",
    content: "# {{title}}\n\n{{date}}\n\nDear ,\n\n\n\nYours sincerely,\n\n",
  },
  {
    id: "report", title: "Report", hint: "Summary, background, findings, recommendations.",
    content: "# {{title}}\n\n**Date:** {{date}}\n**Prepared by:** \n\n## Summary\n\n\n## Background\n\n\n## Findings\n\n1. \n\n## Recommendations\n\n- \n\n## Appendix\n\n",
  },
  {
    id: "essay", title: "Essay", hint: "Thesis, three points, conclusion, references.",
    content: "# {{title}}\n\n## Introduction\n\nThesis: \n\n## First point\n\n\n## Second point\n\n\n## Third point\n\n\n## Conclusion\n\n\n## References\n\n1. \n",
  },
  {
    id: "cv", title: "CV", hint: "Profile, experience, education, skills.",
    content: "# {{title}}\n\nEmail · Phone · Place\n\n## Profile\n\n\n## Experience\n\n### Role, company (from to)\n\n- \n\n## Education\n\n### Qualification, place (year)\n\n## Skills\n\n- \n",
  },
  {
    id: "proposal", title: "One-page proposal", hint: "The problem, the idea, why now, cost, the ask.",
    content: "# {{title}}\n\n**Date:** {{date}}\n**From:** \n\n## The problem\n\n\n## The idea\n\n\n## Why now\n\n\n## Cost and time\n\n\n## The ask\n\n",
  },
  {
    id: "assignment", group: "planning", title: "Assignment plan", hint: "Brief, criteria, sections, sources, timeline.",
    content: "# {{title}}\n\n**Due:** \n**Unit:** \n**Weight:** \n\n## The brief, in my own words\n\n\n## Marking criteria\n\n- [ ] \n- [ ] \n\n## Outline\n\n1. Introduction, \n2. \n3. \n4. Conclusion, \n\n## Sources\n\n- \n\n## Timeline\n\n| When | What |\n| --- | --- |\n| {{date}} | Plan written |\n|  | Draft |\n|  | Edit and submit |\n",
  },
  {
    id: "meeting", group: "planning", title: "Meeting notes", hint: "Attendees, agenda, decisions, actions.",
    content: "# {{title}}\n\n**Date:** {{date}}\n**Attendees:** \n\n## Agenda\n\n1. \n\n## Notes\n\n\n## Decisions\n\n- \n\n## Actions\n\n- [ ] Who, what, by when\n",
  },
  {
    id: "decision", group: "planning", title: "Decision record", hint: "Context, options, decision, consequences.",
    content: "# {{title}}\n\n**Date:** {{date}}\n**Status:** proposed\n\n## Context\n\n\n## Options considered\n\n1. \n2. \n\n## Decision\n\n\n## Consequences\n\n- \n",
  },
  {
    id: "weekly", group: "planning", title: "Weekly review", hint: "What happened, what's next, what to drop.",
    content: "# Week of {{date}}\n\n## Went well\n\n- \n\n## Didn't\n\n- \n\n## Next week\n\n- [ ] \n\n## Stop doing\n\n- \n",
  },
  //: **The day's page** (DOCUMENTS_PLAN section 14). The whole of "daily notes"
  //: on this surface is this row: the Timeline owns the journal, its endpoints,
  //: its streak and its calendar strip, and a second create-or-return here
  //: would be the second implementation of one idea. What this adds is what a
  //: document is and a note is not, for a day that grows past a capture.
  //:
  //: `docTitle` is the ISO day and not the gallery's label, because the day's
  //: page is called by its day: it is the exact string `dailyNoteTitle` writes
  //: in app.js, which is the only thing that lets the Timeline recognise a day
  //: written here as that day's page.
  {
    id: "daily", group: "planning", title: "Daily", hint: "Today's page: what happened, what is open, what is next.",
    docTitle: "{{isodate}}",
    content: "# {{isodate}}\n\n## What happened\n\n- \n\n## Still open\n\n- [ ] \n\n## Next\n\n- \n",
  },
  //: **A p5.js sketch** (INBOX 735, the owner: "since p5.js is vendored, can
  //: it be a document option in the text editor??"). A JavaScript document
  //: whose Run shows the canvas beside the code, through the vendored p5
  //: only (run-core.js finds `setup` and `createCanvas`; Brief 69, D6).
  {
    id: "p5", title: "p5.js sketch", group: "code", hint: "Code and a live canvas: Run draws it beside the editor.",
    docTitle: "Sketch {{isodate}}",
    fileType: "js",
    content: "// A p5.js sketch: Run (Ctrl+Shift+Enter) draws it in the panel below.\nfunction setup() {\n  createCanvas(400, 300);\n}\n\nfunction draw() {\n  background(240);\n  circle(mouseX, mouseY, 40);\n}\n",
  },
  //: **Code templates** (INBOX 788, the owner: "can you add code templates
  //: as document templates as well??"). One starter per language the editor
  //: runs or highlights, each a document of its own type so it opens in the
  //: code view (`fileType`), and each one that runs says how in its first
  //: lines. `group` puts them under the gallery's Code heading. Template
  //: literals, so a `${` inside the code is escaped as `\${`.
  {
    id: "py-script", group: "code", title: "Python script", hint: "A main function and a test: Run runs the test.",
    docTitle: "Script {{isodate}}", fileType: "py",
    content: `"""{{title}}: what this script does, in one line."""


def greet(name: str) -> str:
    return f"Hello, {name}"


def main() -> None:
    print(greet("world"))


# Run (Ctrl+Shift+Enter) runs a file's tests when it has any, so it runs
# this one; move the test to its own file to run main() instead.
def test_greet():
    assert greet("Ada") == "Hello, Ada"


if __name__ == "__main__":
    main()
`,
  },
  {
    id: "py-cli", group: "code", title: "Command line tool", hint: "Python with argparse: options, help and an exit code.",
    docTitle: "CLI {{isodate}}", fileType: "py",
    content: `"""{{title}}: a command line tool.

From a terminal: python cli.py --name Ada --times 2
"""

import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Say hello.")
    parser.add_argument("--name", default="world", help="who to greet")
    parser.add_argument("--times", type=int, default=1, help="how many times")
    parser.add_argument("-v", "--verbose", action="store_true", help="say more")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    for _ in range(args.times):
        print(f"Hello, {args.name}")
    if args.verbose:
        print(f"Greeted {args.times} time(s).")
    return 0


if __name__ == "__main__":
    # The sandbox has no command line, so Run passes these arguments.
    main(["--name", "Ada", "--times", "2", "--verbose"])
`,
  },
  {
    id: "fastapi", group: "code", title: "FastAPI endpoint", hint: "A small API: a model, a read route and a create route.",
    docTitle: "API {{isodate}}", fileType: "py",
    content: `"""{{title}}: a FastAPI app.

Serve it from a terminal with fastapi and uvicorn installed:
    uvicorn app:app --reload
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()


class Item(BaseModel):
    name: str
    price: float


ITEMS: dict[int, Item] = {}


@app.get("/items/{item_id}")
def read_item(item_id: int) -> Item:
    if item_id not in ITEMS:
        raise HTTPException(status_code=404, detail="Item not found")
    return ITEMS[item_id]


@app.post("/items/{item_id}", status_code=201)
def create_item(item_id: int, item: Item) -> Item:
    ITEMS[item_id] = item
    return item
`,
  },
  {
    id: "js-module", group: "code", title: "JavaScript with tests", hint: "Functions and their tests: Run runs describe, it and expect.",
    docTitle: "Module {{isodate}}", fileType: "js",
    content: `// {{title}}: functions, then their tests.
// Run (Ctrl+Shift+Enter) runs the tests with describe, it and expect.

function slugify(text) {
  return String(text)
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

describe("slugify", () => {
  it("joins words with hyphens", () => {
    expect(slugify("Hello World")).toBe("hello-world");
  });

  it("drops punctuation at the ends", () => {
    expect(slugify("  Hi, there.  ")).toBe("hi-there");
  });
});
`,
  },
  {
    id: "html-page", group: "code", title: "HTML page", hint: "A page with a style and a script: Run shows it below.",
    docTitle: "Page {{isodate}}", fileType: "html",
    content: `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{title}}</title>
  <style>
    body { font-family: system-ui, sans-serif; margin: 2rem; line-height: 1.5; }
    button { padding: 0.5rem 1rem; }
  </style>
</head>
<body>
  <h1>{{title}}</h1>
  <p>Run (Ctrl+Shift+Enter) shows this page in the panel below.</p>
  <button id="count" type="button">Clicked 0 times</button>
  <script>
    let clicks = 0;
    document.getElementById("count").addEventListener("click", (event) => {
      clicks += 1;
      event.target.textContent = \`Clicked \${clicks} times\`;
    });
  </script>
</body>
</html>
`,
  },
  {
    id: "sql-schema", group: "code", title: "SQL schema", hint: "Two tables, some rows and a join: Run shows each result.",
    docTitle: "Schema {{isodate}}", fileType: "sql",
    content: `-- {{title}}: Run (Ctrl+Shift+Enter) runs each statement against an
-- empty in-memory SQLite database and shows every result as a table.

CREATE TABLE authors (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE books (
    id INTEGER PRIMARY KEY,
    author_id INTEGER NOT NULL REFERENCES authors (id),
    title TEXT NOT NULL,
    published INTEGER
);

INSERT INTO authors (name) VALUES ('Ursula K. Le Guin'), ('Italo Calvino');
INSERT INTO books (author_id, title, published) VALUES
    (1, 'The Dispossessed', 1974),
    (2, 'Invisible Cities', 1972);

SELECT authors.name, books.title, books.published
FROM books
JOIN authors ON authors.id = books.author_id
ORDER BY books.published;
`,
  },
  {
    id: "readme", group: "code", title: "README", hint: "What it is, how to install, use and test it.",
    docTitle: "README",
    content: "# {{title}}\n\nOne sentence on what this is and who it is for.\n\n## Install\n\n```bash\npip install -r requirements.txt\n```\n\n## Use\n\n```bash\npython main.py --help\n```\n\n## Test\n\n```bash\npython -m pytest\n```\n\n## Licence\n\n\n",
  },
  {
    id: "notebook", group: "code", title: "Notebook", hint: "Notes and code in cells, Jupyter style, in one Python file.",
    docTitle: "Notebook {{isodate}}", fileType: "py",
    content: `# %% [markdown]
# # {{title}}
# Notes and code in one file, Jupyter style. Each \`# %%\` line starts a
# cell. Run (Ctrl+Shift+Enter) runs the file; the palette's Run the cell
# at the caret (Ctrl+Shift+P) runs one.

# %%
numbers = [3, 1, 4, 1, 5, 9, 2, 6]
total = sum(numbers)
print(f"{len(numbers)} numbers, total {total}")

# %% [markdown]
# ## What the numbers say

# %%
mean = total / len(numbers)
print(f"mean {mean:.2f}, largest {max(numbers)}")
`,
  },
];

function docTemplateFill(template, typedTitle = "") {
  const now = new Date();
  const date = now.toLocaleDateString(undefined, { year: "numeric", month: "long", day: "numeric" });
  //: **`{{isodate}}` is the local day, built by hand rather than from
  //: `toISOString()`**, which converts to UTC first and so names yesterday for
  //: anyone east of it after their evening. "Today" is a fact about where the
  //: person is sitting; `routes_entries.py`'s D6 block makes the same argument
  //: for the server, which is why the day is the caller's there too.
  const iso = [
    now.getFullYear(),
    String(now.getMonth() + 1).padStart(2, "0"),
    String(now.getDate()).padStart(2, "0"),
  ].join("-");
  const time = now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  const fill = (text) => (text || "").replaceAll("{{date}}", date).replaceAll("{{isodate}}", iso).replaceAll("{{time}}", time);
  //: A template's gallery label and the title it gives the document are not
  //: always the same words: "Daily" names the choice in the gallery, and the
  //: document it makes is called by its day (`docTitle`, section 14).
  //: A title the person already typed is the name they chose (audit 1028 U34).
  const title = typedTitle || (template.id === "blank" ? docNextName() : fill(template.docTitle || template.title));
  //: `{{cursor}}` is where the caret lands (the note templates' word for it): taken out here, its offset handed back as `cursor`
  //: (-1 for none) for the caller to place; a section's fill keeps only `content`.
  const text = fill(template.content).replaceAll("{{title}}", title);
  const cursor = text.indexOf("{{cursor}}");
  return {
    title,
    content: text.replaceAll("{{cursor}}", ""),
    cursor,
    //: A code template (the p5 sketch) makes a document of its own type.
    ...(template.fileType ? { file_type: template.fileType } : {}),
  };
}

//: **A new document needs no name** (INBOX 739, the owner: "auto naming of
//: the whiteboards, mindmaps and documents like \"untitled #\" so the user
//: isnt forced to name a new object"). The next free number after every
//: "Untitled document N" there is, as `wbUntitledNames` does for boards and
//: maps, so a deleted one's number is not reused while a higher one exists.
// DOC-UNTITLED-BEGIN
function docUntitledName(titles) {
  //: The bare "Untitled document" is number one; the next is "... 2".
  const pattern = /^untitled document(?: (\d{1,6}))?$/i;
  let top = 0;
  for (const title of titles || []) {
    const match = pattern.exec(String(title || "").trim());
    if (match) top = Math.max(top, match[1] ? Number(match[1]) : 1);
  }
  return top ? `Untitled document ${top + 1}` : "Untitled document";
}

//: A document nobody touched: still named by the app (or not at all), still empty. The only
//: kind that is dropped on leaving; one word of text keeps it (dog3-1026 D20).
function docIsUntouched(title, text) {
  return /^(?:untitled(?: document)?(?: \d{1,6})?)?$/i.test(String(title || "").trim()) && !String(text || "").trim();
}
// DOC-UNTITLED-END
const docNextName = () => docUntitledName(docs.map((d) => d.title));

//: Leaving a document that was made and never written in (a keystroke in the
//: title, then undone; New, then another document) bins it, so the list does
//: not fill with "Untitled document N". Anything with a word in it stays.
async function docDropIfUntouched(nextId = null, { titled = false } = {}) {
  const doc = currentDoc;
  //: `titled`: a template is about to be made from the title the person typed, so
  //: the empty document that title started is the stray (audit 1028 U34).
  const untouched = titled ? !docText().trim() : docIsUntouched($("doc-title").value, docText());
  // Only a document made in this session: an older empty "Untitled document N" is the owner's.
  if (!doc || !docsMadeThisSession.has(doc.id) || doc.id === nextId || creatingDocument || !untouched) return;
  currentDoc = null;
  docs = docs.filter((d) => d.id !== doc.id);
  //: A delete that failed leaves the row on the server, so it goes back in the list (D36).
  await apiJson(`/documents/${doc.id}`, { method: "DELETE" }).catch(() => { docs = [doc, ...docs]; });
  renderDocList();
}

//: **A blank document is not made until it is written in** (dog1-1025 item
//: 16, decided): the editor opens empty and the first keystroke in the title
//: or the text creates the row (`ensureDocumentExists`), so cancelling or
//: walking away leaves nothing behind. A template has content, so it posts.
async function startBlankDocument(fileType = null) {
  const seq = ++docOpenSeq;
  docRememberPositionNow();
  if (docDirty) await saveDocument({ silent: true });
  await docDropIfUntouched();
  await ensureDocEditor();
  if (seq !== docOpenSeq) return;
  showNoDocument();
  //: A file of another type (New's caret): said in the empty page's own words.
  docTypeState.pending = fileType && fileType !== "md" ? fileType : null;
  if (docTypeState.pending) docSetPlaceholder(docBlankPlaceholder());
  syncDocFileType({ prose: false });
  docDirty = false;
  renderDocList();
  $("doc-title").focus();
}

async function createDocument(template = null) {
  if (!template) return startBlankDocument();
  //: A titled blank the person started and then swapped for a template is not
  //: left behind empty: its title carries into the template's document (U34).
  const started = currentDoc && docsMadeThisSession.has(currentDoc.id) && !docText().trim() ? $("doc-title").value.trim() : "";
  await docDropIfUntouched(null, { titled: true });
  const { cursor, ...body } = docTemplateFill(template, started && !docIsUntouched(started, "") ? started : "");
  const doc = await apiJson("/documents", {
    method: "POST",
    body: JSON.stringify(body),
  });
  loadCaptureDocuments(); // so Capture can attach to it straight away
  await loadDocuments(doc.id);
  offerCreateUndo(doc);
  //: A template with a `{{cursor}}` puts the caret there; without one the title is selected to be typed over.
  if (cursor >= 0 && docSurface()) {
    docSurface().focus?.();
    docSurface().setSelection(cursor);
    return;
  }
  $("doc-title").focus();
  $("doc-title").select();
}

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
let docTemplateChoice = null;
let docTemplateMade = false;

function chooseDocTemplate(template, { focus = false } = {}) {
  if (!template) return;
  docTemplateChoice = template;
  for (const row of document.querySelectorAll("#doc-template-list .doc-template-choice")) {
    const on = row.dataset.template === template.id;
    row.setAttribute("aria-checked", String(on));
    //: The radio pattern's roving tab stop: Tab reaches the chosen row only,
    //: the arrows move between rows.
    row.tabIndex = on ? 0 : -1;
    if (on && focus) row.focus();
  }
  showDocTemplatePreview(template);
}

async function useDocTemplate() {
  //: A double click is a click and then a dblclick, and Enter can follow
  //: either: one document per opening, whichever way it was confirmed.
  if (docTemplateMade || !docTemplateChoice) return;
  docTemplateMade = true;
  $("doc-template-dialog")?.close();
  await createDocument(docTemplateChoice);
}

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

//: Counts edits, so a save that lands knows whether words were typed
//: while it was in flight (those keep the document dirty).
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

//: While the edit-conflict prompt is up, autosave waits for its answer
//: rather than asking again every 1.2s of typing behind it.
let docConflictOpen = false;
//: **An autosave's conflict waits in the status line, not in a dialog** (audit
//: 1028 D9). A silent save hit the modal in the middle of a sentence, which
//: took the focus and sent the next keystrokes to it. Now the save stops, the
//: status says the document changed in another window and offers "Resolve",
//: and the dialog opens when asked for (or on an explicit save). `{ id,
//: current }`: the other window's version, for the document it is about.
let docConflictPending = null;

//: One save at a time: a second PUT in flight carried the old base_hash (a
//: false 409). One asked for meanwhile runs once after (audit 1028 D1).
//: `newRetry`: the pause timer after a failed first save (`markDocDirty`); `newOffered`: the kept new document was offered.
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

//: An emptied title keeps a name of the same kind rather than going back to a bare "Untitled".
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

//: The answer to an edit conflict on a document. "Keep mine" saves this
//: text from the other window's hash, so it goes through as a deliberate
//: overwrite (and the server keeps the other window's text as a revision,
//: as every content change does). "Take theirs" puts the other text in the
//: editor as saved. No answer leaves the text here, unsaved, and the next
//: edit asks again.
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
// Bracketed by `DOC-COMMANDS-BEGIN`/`END` so `tests/test_doc_commands.py` can
// read the table's shape without a browser.
//
// **Every row says its chord or "none"** (DOCUMENTS_PLAN section 25 row 6):
// an empty `keys` was a row nobody had decided about. "none" is a decision
// (no free chord that means it anywhere else, or a chord the app gives to
// something else), and the palette and the sheet show nothing for it.

// DOC-COMMANDS-BEGIN

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

//: The table. `keys` is the chord the editor already listens for, or "" where
//: the action has no chord: the shortcut sheet draws the rows that have one
//: and the palette draws all of them, which is the division the plan asks for
//: ("every editor action with its shortcut").
const DOC_COMMANDS = [
  { id: "save", icon: "ph:floppy-disk", label: "Save this document", keys: "Ctrl+S",
    run: () => saveDocument() },
  { id: "find", icon: "ph:magnifying-glass", label: "Find and replace in this document", keys: "Ctrl+F",
    run: () => toggleDocFindBar(true) },
  { id: "bold", icon: "ph:text-b", label: "Bold", keys: "Ctrl+B",
    run: () => wrapDocSelection("**", "bold text") },
  { id: "italic", icon: "ph:text-italic", label: "Italic", keys: "Ctrl+I",
    run: () => wrapDocSelection("*", "italic text") },
  { id: "underline", icon: "ph:text-underline", label: "Underline", keys: "Ctrl+U",
    run: () => applyMarkdown("underline") },
  { id: "strike", icon: "ph:text-strikethrough", label: "Strike through", keys: "Ctrl+Shift+S",
    run: () => wrapDocSelection("~~", "struck through") },
  { id: "code", icon: "ph:code", label: "Inline code", keys: "Ctrl+E",
    run: () => wrapDocSelection("`") },
  //: `alt` is a second chord for the same row (INBOX 1559): Ctrl+1 to 3 are the
  //: browser's tab switch, which a page cannot always take, so Ctrl+Alt+1 to 6
  //: (Google Docs' set) are the ones that work everywhere.
  { id: "h1", icon: "ph:text-h-one", label: "Heading 1", keys: "Ctrl+1", alt: "Ctrl+Alt+1",
    run: () => applyMarkdown("h1") },
  { id: "h2", icon: "ph:text-h-two", label: "Heading 2", keys: "Ctrl+2", alt: "Ctrl+Alt+2",
    run: () => applyMarkdown("h2") },
  { id: "h3", icon: "ph:text-h-three", label: "Heading 3", keys: "Ctrl+3", alt: "Ctrl+Alt+3",
    run: () => applyMarkdown("h3") },
  { id: "h4", icon: "ph:text-h-four", label: "Heading 4", keys: "Ctrl+Alt+4",
    run: () => applyMarkdown("h4") },
  { id: "h5", icon: "ph:text-h-five", label: "Heading 5", keys: "Ctrl+Alt+5",
    run: () => applyMarkdown("h5") },
  { id: "h6", icon: "ph:text-h-six", label: "Heading 6", keys: "Ctrl+Alt+6",
    run: () => applyMarkdown("h6") },
  { id: "comment", icon: "ph:chat-teardrop-text", label: "Comment on the selection", keys: "Ctrl+/",
    run: () => toggleDocComment(docSurface()) },
  { id: "indent", icon: "ph:text-indent", label: "Indent the line or list item", keys: "Tab", run: null },
  { id: "outdent", icon: "ph:text-outdent", label: "Outdent the line or list item", keys: "Shift+Tab", run: null },
  { id: "move-section", icon: "ph:arrows-down-up", label: "Move the section, from the outline", keys: "Alt+↑ / Alt+↓", run: null },
  { id: "move-block-up", icon: "ph:arrow-up", label: "Move the block at the caret up: a paragraph, list item, table or section", keys: "Alt+↑",
    run: () => docBlockMoveCommand(-1) },
  { id: "move-block-down", icon: "ph:arrow-down", label: "Move the block at the caret down: a paragraph, list item, table or section", keys: "Alt+↓",
    run: () => docBlockMoveCommand(1) },
  { id: "turn-into", icon: "ph:swap", label: "Turn into: paragraph, heading, list, to-do, quote, callout or code", keys: "none", prose: true,
    run: () => docTurnIntoMenu() },
  { id: "ul", icon: "ph:list-bullets", label: "Bulleted list", keys: "Ctrl+Shift+8", run: () => applyMarkdown("ul") },
  { id: "ol", icon: "ph:list-numbers", label: "Numbered list", keys: "Ctrl+Shift+7", run: () => applyMarkdown("ol") },
  { id: "task", icon: "ph:check-square", label: "Task list", keys: "Ctrl+Shift+9", run: () => applyMarkdown("task") },
  { id: "quote", icon: "ph:quotes", label: "Quote", keys: "none", run: () => applyMarkdown("quote") },
  //: Ctrl+K with a selection makes the link; with none the chord is the palette's
  //: (`docLinkChord`, INBOX 1559). The row works from the palette either way.
  { id: "link", icon: "ph:link", label: "Link (Ctrl+K on selected text)", keys: "Ctrl+K", run: () => applyMarkdown("link") },
  //: The insert panels (INBOX 1544): the picker on its three tabs, the equation
  //: editor and the calculator, pressed from here as from the Insert menu. The
  //: chords are bound for the document and every note box (`docCmKeymap.insert`).
  { id: "insert-emoji", icon: "ph:smiley", label: "Insert an emoji", keys: "Ctrl+;", prose: true,
    run: () => applyMarkdown("emoji") },
  { id: "insert-icon", icon: "ph:shapes", label: "Insert an icon", keys: "Ctrl+Shift+;", prose: true,
    run: () => applyMarkdown("icon") },
  { id: "insert-symbol", icon: "ph:pi", label: "Insert a symbol", keys: "Ctrl+'", prose: true,
    run: () => applyMarkdown("symbol") },
  { id: "insert-equation", icon: "ph:function", label: "Insert an equation", keys: "Alt+=", prose: true,
    run: () => applyMarkdown("equation") },
  { id: "insert-calculator", icon: "ph:calculator", label: "Open the calculator", keys: "Ctrl+Shift+'",
    run: () => applyMarkdown("calculator") },
  { id: "view-edit", icon: "ph:pencil-simple", label: "Edit this document", keys: "none",
    run: () => setDocView(lastEditView) },
  { id: "view-read", icon: "ph:book-open", label: "Read this document", keys: "none",
    run: () => setDocView("rendered") },
  { id: "formatting", icon: "ph:text-aa", label: "Show or hide the formatting toolbar", keys: "Ctrl+Shift+X",
    run: () => toggleDocToolbar() },
  { id: "focus", icon: "ph:corners-out", label: "Focus mode: only the page, the whole window", keys: "F11",
    run: () => docRunControl("doc-focus-toggle", "Focus mode") },
  { id: "typewriter", icon: "ph:arrows-in-line-horizontal", label: "Typewriter scrolling", keys: "none",
    run: () => docRunControl("doc-typewriter", "Typewriter scrolling") },
  { id: "dim-others", icon: "ph:circle-half-tilt", label: "Dim every paragraph but this one", keys: "none",
    run: () => docRunControl("doc-dim-others", "Dimming") },
  { id: "serif", icon: "ph:text-aa", label: "Serif reading face", keys: "none",
    run: () => docRunControl("doc-serif", "The serif face") },
  { id: "copy-formatted", icon: "ph:copy", label: "Copy as formatted text, to paste into Word or an email", keys: "none", prose: true,
    run: () => docCopyFormatted() },
  { id: "paste-special", icon: "ph:clipboard-text", label: "Paste special: plain text, Markdown source, code, quote, table, link or checklist", keys: "none",
    run: () => docPasteSpecialMenu() },
  { id: "paste-plain", icon: "ph:clipboard-text", label: "Paste as plain text", keys: "Ctrl+Shift+V",
    run: () => docPasteSpecial("plain") },
  { id: "paste-source", icon: "ph:file-code", label: "Paste as Markdown source, no conversion", keys: "none",
    run: () => docPasteSpecial("source") },
  { id: "paste-match", icon: "ph:text-indent", label: "Paste matching the surrounding text, list marks and quotes carried on", keys: "none",
    run: () => docPasteSpecial("match") },
  { id: "paste-code", icon: "ph:code-block", label: "Paste as a code block", keys: "none",
    run: () => docPasteSpecial("code") },
  { id: "paste-quote", icon: "ph:quotes", label: "Paste as a quote", keys: "none",
    run: () => docPasteSpecial("quote") },
  { id: "paste-table", icon: "ph:table", label: "Paste as a table, from a spreadsheet or CSV", keys: "none",
    run: () => docPasteSpecial("table") },
  { id: "paste-link", icon: "ph:link", label: "Paste as a link, over the selected words", keys: "none",
    run: () => docPasteSpecial("link") },
  { id: "paste-checklist", icon: "ph:check-square", label: "Paste as a checklist, one line per item", keys: "none",
    run: () => docPasteSpecial("checklist") },
  { id: "text-size", icon: "ph:text-aa", label: "Text size: small, medium or large", keys: "none", prose: true,
    run: () => docRunControl("doc-text-size", "Text size") },
  { id: "line-spacing", icon: "ph:arrows-vertical", label: "Line spacing: compact, comfortable or relaxed", keys: "none", prose: true,
    run: () => docRunControl("doc-line-spacing", "Line spacing") },
  { id: "stats", icon: "ph:chart-bar", label: "Document statistics: words, reading ease, repeated words", keys: "none",
    run: () => docRunTextTool("stats") },
  { id: "case-upper", icon: "ph:text-aa", label: "Selection to UPPER CASE", keys: "none",
    run: () => docRunTextTool("upper") },
  { id: "case-lower", icon: "ph:text-aa", label: "Selection to lower case", keys: "none",
    run: () => docRunTextTool("lower") },
  { id: "case-title", icon: "ph:text-aa", label: "Selection to Title Case", keys: "none",
    run: () => docRunTextTool("title") },
  { id: "case-sentence", icon: "ph:text-aa", label: "Selection to Sentence case", keys: "none",
    run: () => docRunTextTool("sentence") },
  { id: "sort-asc", icon: "ph:sort-ascending", label: "Sort the selected lines A to Z", keys: "none",
    run: () => docRunTextTool("sort-asc") },
  { id: "sort-desc", icon: "ph:sort-descending", label: "Sort the selected lines Z to A", keys: "none",
    run: () => docRunTextTool("sort-desc") },
  { id: "unique", icon: "ph:funnel", label: "Remove duplicate lines from the selection", keys: "none",
    run: () => docRunTextTool("unique") },
  { id: "number-headings", icon: "ph:list-numbers", label: "Number the headings (1, 1.1, 1.2)", keys: "none", prose: true,
    run: () => docRunTextTool("number-headings") },
  { id: "unnumber-headings", icon: "ph:list-numbers", label: "Remove the heading numbers", keys: "none", prose: true,
    run: () => docRunTextTool("unnumber-headings") },
  { id: "date-iso", icon: "ph:calendar-blank", label: "Insert today's date (2026-10-26)", keys: "none",
    run: () => docRunTextTool("date-iso") },
  { id: "date-long", icon: "ph:calendar-blank", label: "Insert today's date in words", keys: "none",
    run: () => docRunTextTool("date-long") },
  { id: "time", icon: "ph:clock", label: "Insert the time", keys: "none",
    run: () => docRunTextTool("time") },
  { id: "goal", icon: "ph:target", label: "Set a word goal", keys: "none",
    run: () => docRunControl("doc-word-goal", "The word goal") },
  { id: "ai", icon: "ph:sparkle", label: "Ask Atlas to edit this document", keys: "none",
    run: () => docRunControl("doc-ai", "AI editing") },
  { id: "extract", icon: "ph:scissors", label: "Extract notes from this document", keys: "none",
    run: () => docRunControl("doc-extract", "Extracting notes") },
  { id: "map-headings", icon: "ph:tree-structure", label: "Map this document's headings", keys: "none",
    run: () => docRunControl("doc-map-headings", "Mapping the headings") },
  { id: "history", icon: "ph:clock-counter-clockwise", label: "Every version this document has had", keys: "none",
    run: () => docRunControl("doc-history", "Version history") },
  { id: "connections", icon: "ph:graph", label: "What this document is joined to", keys: "none",
    run: () => docRunControl("doc-connections", "Connections") },
  { id: "export-md", icon: "ph:download-simple", label: "Download as .md", keys: "none",
    run: () => docRunControl("doc-export-md", "The markdown export") },
  { id: "export-html", icon: "ph:file-html", label: "Download as one .html file", keys: "none",
    run: () => docRunControl("doc-export-html", "The HTML export") },
  { id: "export-slides", icon: "ph:presentation-chart", label: "Download as a slide deck (.html)", keys: "none",
    run: () => docRunControl("doc-export-slides", "The slide deck export") },
  { id: "export-docx", icon: "ph:file-doc", label: "Download as Word (.docx)", keys: "none",
    run: () => docRunControl("doc-export-docx", "The Word export") },
  { id: "export-pdf", icon: "ph:file-pdf", label: "Print or save as PDF", keys: "none",
    run: () => docRunControl("doc-export-pdf", "The PDF export") },
  //: `code: true` rows are offered by the palette only while a code
  //: document is open; the shortcut sheet lists them always, marked by
  //: their wording as being for code.
  { id: "format", icon: "ph:brackets-curly", label: "Format the code, or the selected lines", keys: "Shift+Alt+F",
    code: true, run: () => docRunControl("doc-code-format", "Formatting") },
  { id: "quick-fix", icon: "ph:wrench", label: "Quick fixes for the problem at the caret", keys: "Alt+Enter",
    code: true, run: () => docOpenCodeFixes() },
  //: CodeMirror's default keymap has always bound this chord; the row is what
  //: puts it in the palette and the shortcut sheet (INBOX 402).
  { id: "block-comment", icon: "ph:brackets-angle", label: "Block comment around the selection", keys: "Shift+Alt+A",
    code: true, run: () => docCodeCommentAtCaret(docSurface(), true) },
  //: Emmet's editing commands (INBOX 402). No chord: VS Code has none for
  //: them either, and every free one is spoken for by something commoner.
  { id: "emmet-wrap", icon: "ph:brackets-angle", label: "Wrap the selection with an Emmet abbreviation", keys: "none",
    code: true, run: () => docEmmetWrap() },
  { id: "emmet-balance-out", icon: "ph:arrows-out-line-horizontal", label: "Select the enclosing tag (Emmet balance outward)", keys: "none",
    code: true, run: () => docEmmetBalance(false) },
  { id: "emmet-balance-in", icon: "ph:arrows-in-line-horizontal", label: "Select the tag inside (Emmet balance inward)", keys: "none",
    code: true, run: () => docEmmetBalance(true) },
  //: VS Code's Ctrl+Shift+O, without the chord: the registry gives it to a
  //: new chat. The outline panel lists the same symbols.
  { id: "symbols", icon: "ph:list-magnifying-glass", label: "Go to a symbol in this file", keys: "none",
    code: true, run: () => docOpenSymbols() },
  { id: "definition", icon: "ph:arrow-square-in", label: "Go to where the name at the caret is defined", keys: "F12",
    code: true, run: () => docGoToDefinition() },
  { id: "references", icon: "ph:list-magnifying-glass", label: "List every use of the name at the caret", keys: "Shift+F12",
    code: true, run: () => docShowReferences() },
  //: Every find chord named in one list, since Ctrl+G reads by file type
  //: (VS Code's Go to line in code, find next in prose, where F3 does it
  //: too and is the key listed; audit 1028 D32).
  { id: "replace-here", icon: "ph:swap", label: "Find and replace in this document", keys: "Ctrl+H",
    run: () => docOpenReplace() },
  { id: "goto-line", icon: "ph:arrow-line-down", label: "Go to a line", keys: "Ctrl+G",
    code: true, run: () => docCmView && window.CM6.search.gotoLine(docCmView) },
  //: Prose has Ctrl+G for find next, so its Go to line takes Ctrl+Alt+G (DOCUMENTS_PLAN 23 L4).
  { id: "goto-line-text", icon: "ph:arrow-line-down", label: "Go to a line in this text", keys: "Ctrl+Alt+G",
    prose: true, run: () => docCmView && window.CM6.search.gotoLine(docCmView) },
  { id: "find-next", icon: "ph:arrow-down", label: "Find the next match", keys: "F3",
    prose: true, run: () => docCmView && window.CM6.search.findNext(docCmView) },
  { id: "find-documents", icon: "ph:magnifying-glass", label: "Find in every document", keys: "Ctrl+Shift+F",
    run: () => docFindInDocuments() },
  { id: "replace-documents", icon: "ph:swap", label: "Replace in every document", keys: "none",
    run: () => openDocReplace() },
  { id: "run", icon: "ph:play", label: "Run this file and show its output", keys: "Ctrl+Shift+Enter",
    code: true, run: () => docRunCode() },
  { id: "run-tests", icon: "ph:flask", label: "Run the tests in this file", keys: "none",
    code: true, run: () => docRunCode({ mode: "test" }) },
  { id: "run-selection", icon: "ph:text-indent", label: "Run the selected lines", keys: "none",
    code: true, run: () => docRunSelection() },
  //: The code panel (INBOX 788, documents-codekit.js).
  { id: "assistant", icon: "ph:sparkle", label: "Assistant: explain, fix, write tests or refactor", keys: "none",
    code: true, run: () => docCodeSideFrom("assist") },
  //: For prose too (INBOX 904 B18): there it lists the text sections.
  { id: "snippets", icon: "ph:puzzle-piece", label: "Snippets and sections: insert one, or save the selection as one", keys: "none",
    run: () => docCodeSideFrom("snippets") },
  { id: "run-cell", icon: "ph:rows", label: "Run the cell at the caret (between # %% markers)", keys: "none",
    code: true, run: () => docRunCell() },
  //: Brief 70 (DOCUMENTS_PLAN 23, I2): Debug on VS Code's own keys, bound in
  //: the editor by `docDebugExtension` for the kinds it steps.
  { id: "debug", icon: "ph:bug", label: "Debug this file, or continue to the next breakpoint", keys: "F5",
    code: true, run: () => docDebugAct("continue") },
  { id: "debug-breakpoint", icon: "ph:circle", label: "Add or remove a breakpoint on the caret's line", keys: "F9",
    code: true, run: () => docDebugToggleHere() },
  { id: "debug-over", icon: "ph:arrow-bend-down-right", label: "Step over the line (while debugging)", keys: "F10",
    code: true, run: () => docDebugAct("over") },
  //: F11 is Focus mode's ("focus" above) except while a session is paused,
  //: as VS Code shares it between Step into and Full screen.
  { id: "debug-in", icon: "ph:arrow-elbow-down-right", label: "Step into the call (while debugging)", keys: "F11 while debugging",
    code: true, run: () => docDebugAct("in") },
  { id: "debug-out", icon: "ph:arrow-elbow-left-up", label: "Step out of the function (while debugging)", keys: "Shift+F11",
    code: true, run: () => docDebugAct("out") },
  { id: "debug-stop", icon: "ph:stop", label: "Stop debugging", keys: "Shift+F5",
    code: true, run: () => docDebugAct("stop") },
  { id: "code-wrap", icon: "ph:text-align-left", label: "Wrap long lines in a code file", keys: "Alt+Z",
    code: true, run: () => docToggleCodeDraw("codeWrap") },
  { id: "whitespace", icon: "ph:paragraph", label: "Show whitespace in a code file", keys: "none",
    code: true, run: () => docToggleCodeDraw("whitespace") },
  //: Brief 42 (documents-ide.js). The two fold chords are CodeMirror's
  //: `foldKeymap`, bound since Phase 2; Ctrl+Shift+M is VS Code's.
  { id: "fold-all", icon: "ph:arrows-in-line-vertical", label: "Fold every block in a code file", keys: "Ctrl+Alt+[",
    code: true, run: () => docIdeCall("docIdeFoldAll", false) },
  { id: "unfold-all", icon: "ph:arrows-out-line-vertical", label: "Unfold every block in a code file", keys: "Ctrl+Alt+]",
    code: true, run: () => docIdeCall("docIdeFoldAll", true) },
  { id: "toggle-fold", icon: "ph:caret-line-down", label: "Fold or unfold the block at the caret", keys: "Ctrl+Alt+.",
    code: true, run: () => docIdeCall("docIdeFoldAll", "toggle") },
  { id: "problems", icon: "ph:warning-circle", label: "List every problem in this file", keys: "Ctrl+Shift+M",
    code: true, run: () => docPanelToggle("problems") },
  { id: "problems-inline", icon: "ph:list-bullets", label: "List every problem in this file, inside the editor", keys: "none",
    code: true, run: () => docIdeCall("docIdeProblemsInline") },
  //: Brief 71 (I3, D8): the panel and its Console on VS Code's chords, the
  //: editor's palette, the split and this table as a sheet. The chords are
  //: answered in documents-ide.js (`docIdeKeydown`), which stops them before
  //: the registry's own Ctrl+Shift+P and Ctrl+Shift+Y.
  { id: "panel", icon: "ph:terminal-window", label: "Show or hide the panel: Output, Problems, Tests, Console", keys: "Ctrl+J",
    code: true, run: () => docPanelToggle(null) },
  { id: "console", icon: "ph:terminal", label: "Open the console: a line of Python or JavaScript in what the last run left", keys: "Ctrl+Shift+Y",
    code: true, run: () => docPanelToggle("console") },
  { id: "debug-panel", icon: "ph:bug", label: "Open the Debug tab: variables, watches, the call stack and breakpoints", keys: "Ctrl+Shift+D",
    code: true, run: () => docPanelToggle("debug") },
  { id: "command-palette", icon: "ph:command", label: "Run an editor command by name (also F1)", keys: "Ctrl+Shift+P",
    code: true, run: () => docIdeCall("docIdeOpenPalette") },
  { id: "split", icon: "ph:columns", label: "Split the editor: this file again, beside itself", keys: "Ctrl+\\",
    code: true, run: () => docIdeCall("docIdeToggleSplit") },
  { id: "outline", icon: "ph:tree-view", label: "Show the outline: this file's symbols, following the caret", keys: "none",
    code: true, run: () => showDocSidebarSection("outline") },
  { id: "keybindings", icon: "ph:keyboard", label: "Every editor command and its key", keys: "Ctrl+K Ctrl+S",
    code: true, run: () => docIdeCall("docIdeOpenKeys") },
  { id: "minimap", icon: "ph:sidebar-simple", label: "Show the minimap in a code file", keys: "none",
    code: true, run: () => docIdeCall("docIdeToggleMinimap") },
  { id: "compare-version", icon: "ph:git-diff", label: "Compare with a saved version", keys: "none",
    code: true, run: () => docIdeCall("docIdeCompareMenu") },
  { id: "compare-revert", icon: "ph:arrow-counter-clockwise", label: "Put back the compared hunk at the caret", keys: "none",
    code: true, run: () => docIdeCall("docIdeRevertAtCaret") },
  { id: "compare-stop", icon: "ph:x", label: "Stop comparing with a saved version", keys: "none",
    code: true, run: () => docIdeCall("docIdeStopCompare") },
];

// DOC-COMMANDS-END

//: **Only while a document is open and on screen.** The palette is reachable
//: from every tab, and "Bold" run from the Notes tab would wrap a selection in
//: a document nobody is looking at. `activeTab` is where the app keeps which
//: tab is showing (navigation.js's `switchTab` writes it), so this asks the same
//: question the tab bar answers.
//:
//: A row with no `run` is a keyboard-only move (Tab, Alt with an arrow): it
//: belongs in the shortcut sheet, which is a list of what the keys do, and not
//: in a palette, which is a list of things a press can perform.
function docPaletteCommands() {
  let tab = "";
  try {
    tab = prefs.get("activeTab", null) || "";
  } catch {
    //: Private mode. One group missing from the palette is the right failure.
    return [];
  }
  if (tab !== "documents" || !currentDoc) return [];
  const code = !docFileType().previewable;
  return DOC_COMMANDS.filter((command) => command.run && (!command.code || code) && (!command.prose || !code)).map((command) => ({
    group: "This document",
    label: `${command.icon} ${command.label}`,
    keys: command.keys === "none" ? "" : (command.alt || command.keys),
    run: command.run,
  }));
}

//: The `?` sheet's editor section, from the same table, so the two cannot
//: disagree. Called by `openShortcuts` (settings-wiring.js) rather than wired here,
//: because this file is in the Library's lazy bundle and the dialog can be
//: opened before it has ever loaded: the section then simply says so.
function renderDocShortcutSheet(list) {
  if (!list) return;
  list.replaceChildren();
  for (const command of DOC_COMMANDS) {
    if (!command.keys || command.keys === "none") continue;
    const li = document.createElement("li");
    const keys = document.createElement("span");
    keys.className = "shortcut-keys";
    //: One `<kbd>` per key, the shape the hand-written rows above it use, so
    //: a generated row and a written one are the same thing on screen.
    for (const chord of [command.keys, command.alt].filter(Boolean)) {
      if (chord !== command.keys) keys.append(" or ");
      for (const part of chord.split(/\s*\+\s*/)) {
        const kbd = document.createElement("kbd");
        kbd.textContent = part;
        keys.appendChild(kbd);
      }
    }
    const label = document.createElement("span");
    label.textContent = command.label;
    li.append(keys, label);
    list.appendChild(li);
  }
}

//: **Reordering the document from its outline** (DOCUMENTS_PLAN Phase 4 item
//: 3, PLAN D6). Dragging a row moves the *section*, the heading and everything
//: under it down to the next heading at the same level or shallower, which is
//: what a reader means by "move Results above Method".
//:
//: **The lines are re-scanned at the moment of the drop, never taken from the
//: outline's own rows.** The outline is rebuilt on a pause in typing, so a row
//: dragged a keystroke after an edit carries line numbers from the document as
//: it was, and moving that run would cut the wrong paragraphs out of the
//: middle of the text. `docScanHeadings` costs one pass over a string this
//: file already holds.
//:
//: The write goes through the surface's own `text` setter, which diffs prefix
//: and suffix and dispatches the smallest change that gets there, so a move is
//: one undo step rather than a whole-document replacement.
function docOutlineMoveSection(fromIndex, toIndex, after) {
  const box = docSurface();
  if (!box) return false;
  const text = box.text;
  const lines = text.split("\n");
  const headings = docScanHeadings(text);
  if (!headings[fromIndex] || !headings[toIndex]) return false;
  const src = docSectionRange(headings, fromIndex, lines.length);
  const dst = after
    ? docSectionRange(headings, toIndex, lines.length).to
    : headings[toIndex].line;
  //: **A section cannot be dropped inside itself**, which is what dragging a
  //: parent onto one of its own children asks for: the block would be cut out
  //: and put back into a hole that no longer exists. Refused rather than
  //: clamped, because there is no sensible place a reader could have meant.
  if (dst > src.from && dst < src.to) return false;
  if (dst === src.from) return false;
  const block = lines.slice(src.from, src.to);
  //: The last section of a document usually has no blank line after it, so
  //: moving it up would weld its last paragraph to the next heading. One
  //: blank line, and only when it is actually missing: everything else about
  //: the block's spacing is the writer's and is carried across untouched.
  if (block.length && block[block.length - 1].trim()) block.push("");
  const rest = [...lines.slice(0, src.from), ...lines.slice(src.to)];
  const at = dst > src.from ? dst - (src.to - src.from) : dst;
  rest.splice(at, 0, ...block);
  box.text = rest.join("\n");
  //: The outline is what was just dragged, so it is redrawn now rather than
  //: on the next pause: a list that still shows the old order for half a
  //: second reads as a drop that did not take.
  renderDocOutline();
  announce(`\u201c${headings[fromIndex].text}\u201d moved.`);
  return true;
}

//: Which side of a row the pointer is on. The midpoint, which is the rule
//: every list with a drop line uses, and the only one that lets a reader
//: place a section at the very end of a document.
function docOutlineDropAfter(row, clientY) {
  const box = row.getBoundingClientRect();
  return clientY > box.top + box.height / 2;
}

function docOutlineClearDrop() {
  for (const row of document.querySelectorAll("#doc-outline .is-drop-before, #doc-outline .is-drop-after")) {
    row.classList.remove("is-drop-before", "is-drop-after");
  }
}

//: **The keyboard half, which a drag can never be.** Alt with an arrow moves
//: the focused row's section past its neighbour, which is the same move the
//: drag makes and the only one this panel can offer somebody who is not using
//: a pointer. Alt because a bare arrow moves between rows and Ctrl+arrow is
//: the browser's own word jump; the same chord Notion and Obsidian use for
//: moving a block.
//:
//: Past its *neighbour in the outline*, not its sibling at the same level: the
//: rows are what the reader can see, and a rule that skipped rows would move
//: a section past things it looked like it was next to.
function docOutlineNudge(index, direction) {
  const headings = docScanHeadings(docText());
  const to = index + direction;
  if (!headings[index] || !headings[to]) return false;
  //: Downwards the section has to land *after* the row below it, upwards
  //: *before* the row above: "after" and "before" are the same two words the
  //: drop uses, so both routes end in one move function.
  //: **Asked for before the move, not after.** The write dispatches a
  //: transaction, which schedules the facts pass, which redraws this outline
  //: again a beat later: focusing a row here would put the ring on an element
  //: that is replaced milliseconds afterwards, and the measurement of that is
  //: `document.activeElement` coming back as `<body>`. So the row is named and
  //: every render restores it until the reader moves on (`docOutlineFocusKey`
  //: at the end of `renderDocOutline`).
  docOutlineFocusKey = docOutlineFoldKey(headings[index]);
  return docOutlineMoveSection(index, to, direction > 0);
}

//: **Alt+Up and Alt+Down in a markdown document move a block** (INBOX 904 B20,
//: the owner's "manage mode for lined documents", taken as the keyboard half
//: the owner's recommendation names). The editor's own line move is right for
//: code and wrong for prose: it swaps a line with the *blank line* beside it,
//: so `beta` moved up from under `alpha` lands between them and the next press
//: welds the two paragraphs. The unit here is what a reader sees as one thing:
//: a paragraph or quote or table (a run of lines), a fenced block (its blank
//: lines included), a list item with everything nested under it, a heading's
//: whole section. It swaps with the neighbour of the same kind and leaves the
//: blank lines between them where they were, so a move is one edit and moving
//: back is byte-exact.
//:
//: Pure: the text, the caret offset and a direction in; `{from, to, insert,
//: caret}` out, `{noop: true}` for "there is nothing to swap with" (swallowed,
//: so the default move cannot weld what this one refused), or null for "not
//: mine" (a blank line, the frontmatter), which leaves the key to the default.
//: Numbered items swap their *text* and keep their numbers.
function docBlockMoveEdit(text, offset, delta) {
  const source = String(text == null ? "" : text);
  const lines = source.split("\n");
  const starts = [];
  let total = 0;
  for (const line of lines) {
    starts.push(total);
    total += line.length + 1;
  }
  let row = 0;
  while (row + 1 < lines.length && starts[row + 1] <= offset) row += 1;
  //: A `---` frontmatter block is metadata, not a block of the document:
  //: nothing moves into it or out of it, and the lines in it are the default's.
  let first = 0;
  if (lines[0] === "---") {
    const close = lines.indexOf("---", 1);
    if (close > 0) first = close + 1;
  }
  if (row < first) return null;
  const fence = /^\s{0,3}(```|~~~)/;
  const atx = /^#{1,6}\s/;
  const blocks = [];
  for (let i = first; i < lines.length; ) {
    const line = lines[i];
    if (!line.trim()) {
      i += 1;
    } else if (fence.test(line)) {
      const mark = line.trim().slice(0, 3);
      let end = i + 1;
      while (end < lines.length && !lines[end].trim().startsWith(mark)) end += 1;
      end = Math.min(end + 1, lines.length);
      blocks.push({ from: i, to: end, kind: "code" });
      i = end;
    } else if (atx.test(line)) {
      blocks.push({ from: i, to: i + 1, kind: "heading" });
      i += 1;
    } else {
      let end = i + 1;
      while (end < lines.length && lines[end].trim() && !atx.test(lines[end]) && !fence.test(lines[end])) end += 1;
      blocks.push({ from: i, to: end, kind: "text" });
      i = end;
    }
  }
  const at = blocks.findIndex((block) => row >= block.from && row < block.to);
  if (at < 0) return null;
  const noop = { noop: true };
  const ordered = /^(\s*)(\d+)([.)])(\s+)/;
  // `a` is the earlier run, `b` the later; the caret's run is `b` for Up.
  const swap = (a, b, pad, keepNumbers) => {
    const aLines = lines.slice(a.from, a.to);
    const bLines = lines.slice(b.from, b.to);
    const gap = lines.slice(a.to, b.from);
    //: Two sections that touch have no blank line between them, and the last
    //: one of a document often has none after it: moved up it would weld its
    //: last paragraph to the next heading. One blank line, and the one the
    //: other side no longer needs comes off the end.
    if (pad && !gap.length && bLines.length && bLines[bLines.length - 1].trim()) {
      bLines.push("");
      if (b.to === lines.length && aLines.length && !aLines[aLines.length - 1].trim()) aLines.pop();
    }
    const moverIsB = row >= b.from;
    let shift = 0;
    const pa = keepNumbers ? ordered.exec(aLines[0]) : null;
    const pb = keepNumbers ? ordered.exec(bLines[0]) : null;
    if (pa && pb) {
      aLines[0] = pb[0] + aLines[0].slice(pa[0].length);
      bLines[0] = pa[0] + bLines[0].slice(pb[0].length);
      const mover = moverIsB ? b : a;
      if (row === mover.from) {
        const was = moverIsB ? pb[0].length : pa[0].length;
        const now = moverIsB ? pa[0].length : pb[0].length;
        const col = offset - starts[row];
        shift = col >= was ? now - was : Math.min(col, now) - col;
      }
    }
    const head = [...bLines, ...gap];
    const base = starts[a.from];
    const caret = moverIsB
      ? base + (offset - starts[b.from]) + shift
      : base + head.join("\n").length + (head.length ? 1 : 0) + (offset - starts[a.from]) + shift;
    const more = b.to < lines.length;
    //: `unit` is what the caret's block spans and `hopFrom`/`hopTo` the neighbour
    //: it swaps with (offsets in this text): the drag handle shows beside the
    //: unit and decides how many neighbours a drop is past.
    const edge = (run) => (run.to < lines.length ? starts[run.to] : source.length);
    const mover = moverIsB ? b : a;
    const hop = moverIsB ? a : b;
    return {
      from: base,
      to: more ? starts[b.to] : source.length,
      insert: [...head, ...aLines].join("\n") + (more ? "\n" : ""),
      caret,
      unit: { from: starts[mover.from], to: edge(mover) },
      hopFrom: starts[hop.from],
      hopTo: edge(hop),
    };
  };
  const swapItems = (one, two) => swap(one, two, false, true);

  //: A heading moves with its section, among the headings of its own level
  //: and inside its own parent: past a shallower heading it would change what
  //: it belongs to, which a move should never do silently.
  if (blocks[at].kind === "heading") {
    const headings = docScanHeadings(source).filter((h) => h.line >= first);
    const index = headings.findIndex((h) => h.line === row);
    if (index >= 0) {
      const level = headings[index].level;
      const own = docSectionRange(headings, index, lines.length);
      let target = -1;
      if (delta < 0) {
        for (let k = index - 1; k >= 0 && headings[k].level >= level; k -= 1) {
          if (headings[k].level === level) {
            target = k;
            break;
          }
        }
      } else {
        const next = headings.findIndex((h) => h.line === own.to);
        if (next >= 0 && headings[next].level === level) target = next;
      }
      if (target < 0) return noop;
      const other = docSectionRange(headings, target, lines.length);
      return delta < 0 ? swap(other, own, true, false) : swap(own, other, true, false);
    }
  }

  //: A list item is its line plus every line indented under it (a blank line
  //: counts when something indented follows it), and swaps with the item of
  //: the same indent beside it; the end of the list is the end of the move.
  const marker = /^(\s*)([-*+]|\d+[.)])\s+/;
  const indentOf = (line) => /^\s*/.exec(line)[0].length;
  if (marker.test(lines[row])) {
    const itemAt = (start) => {
      const depth = indentOf(lines[start]);
      let end = start + 1;
      while (end < lines.length) {
        let next = end;
        while (next < lines.length && !lines[next].trim()) next += 1;
        if (next >= lines.length || indentOf(lines[next]) <= depth) break;
        end = next + 1;
      }
      return { from: start, to: end };
    };
    const depth = indentOf(lines[row]);
    const own = itemAt(row);
    if (delta > 0) {
      let next = own.to;
      while (next < lines.length && !lines[next].trim()) next += 1;
      if (next >= lines.length || indentOf(lines[next]) !== depth || !marker.test(lines[next])) return noop;
      return swapItems(own, itemAt(next));
    }
    let k = row - 1;
    while (k >= first && !lines[k].trim()) k -= 1;
    for (; k >= first; k -= 1) {
      const line = lines[k];
      if (!line.trim()) continue;
      const here = indentOf(line);
      if (here === depth && marker.test(line)) return swapItems(itemAt(k), own);
      if (here <= depth) break;
    }
    return noop;
  }

  const other = blocks[at + delta];
  if (!other) return noop;
  return delta < 0 ? swap(other, blocks[at], false, false) : swap(blocks[at], other, false, false);
}

//: The key's half: only a markdown document (a code file keeps the editor's
//: own line move, which is what code wants), only a caret rather than a
//: selection (a selection of lines moves as lines, as it always did), and a
//: decline hands the key back so the default still answers it.
function docBlockMoveRun(view, delta) {
  if (!docFileType().previewable) return false;
  const selection = view.state.selection;
  if (selection.ranges.length !== 1 || !selection.main.empty) return false;
  const edit = docBlockMoveEdit(docStr(view.state.doc), selection.main.head, delta);
  if (!edit) return false;
  if (edit.noop) return true;
  view.dispatch({
    changes: { from: edit.from, to: edit.to, insert: edit.insert },
    selection: { anchor: edit.caret },
    scrollIntoView: true,
    userEvent: "move.line",
  });
  return true;
}

//: The palette's door to the same move: focus is in the palette, so it aims at
//: the editor and says what to do when the caret is not in a block.
function docBlockMoveCommand(delta) {
  if (!docCmView) return;
  docCmView.focus();
  if (!docBlockMoveRun(docCmView, delta)) announce("Put the caret in a paragraph, list item, table or section of a text document first.");
}

function renderDocOutline() {
  const list = $("doc-outline");
  const wrap = $("doc-outline-wrap");
  if (!list || !wrap) return;
  //: Read first, before this writes a row (INBOX 1530 c): the caret's line was
  //: asked after the rows were rebuilt, so the editor's geometry was laid out
  //: again inside the open (18 to 107 ms forced, the 1530 sweep).
  const where = docWhereLine();
  const text = docText();
  const lines = text.split("\n");
  //: A code file's outline is its symbols (INBOX 402), a markdown file's its
  //: headings; the same rows, the same breadcrumb. Never a code file read
  //: as markdown: every `# comment` in a Python file was a heading here.
  const fileType = docFileType();
  let headings = [];
  if (fileType.previewable) headings = docScanHeadings(text);
  else if (docCmView && window.CM6) headings = docCodeSymbols(window.CM6, docCmView.state, fileType.ext);

  //: **The tasks in each section, counted.** DOCUMENTS_PLAN Phase 3 item 2
  //: asks for "task lists with progress in the outline", and the outline is
  //: where it belongs rather than beside the list itself: a checklist knows
  //: how far along it is by being read, and what a reader cannot see from the
  //: text is how far along the *section* is without scrolling to the end of
  //: it.
  //:
  //: A heading counts its whole subtree, not the lines before the next
  //: heading of any level: "Release" showing 0/0 while the three sub-sections
  //: under it hold every task in the document would be a count that is
  //: accurate and useless. Fenced code is skipped, for the same reason the
  //: headings above skip it.
  const DOC_TASK_LINE = /^\s*(?:[-*+]|\d+[.)])\s+\[([ xX])\]/;
  headings.forEach((heading, index) => {
    let end = lines.length;
    for (let next = index + 1; next < headings.length; next += 1) {
      if (headings[next].level <= heading.level) {
        end = headings[next].line;
        break;
      }
    }
    let done = 0;
    let total = 0;
    let fenced = false;
    for (let at = heading.line + 1; at < end; at += 1) {
      if (lines[at].trim().startsWith("```")) {
        fenced = !fenced;
        continue;
      }
      if (fenced) continue;
      const task = DOC_TASK_LINE.exec(lines[at]);
      if (!task) continue;
      total += 1;
      if (task[1] !== " ") done += 1;
    }
    heading.tasks = total ? { done, total } : null;
  });

  //: **The Outline tab always shows an outline section, even with nothing in
  //: it.** It used to hide itself below two headings, which meant that opening
  //: the tab called Outline on a document without them showed a "References"
  //: heading, a button and a help link, and nothing that mentioned outlines at
  //: all. Reported as "the empty state is a bare heading with nothing under
  //: it". An empty state that says what fills it is the difference between a
  //: panel that is empty and a panel that looks broken.
  wrap.classList.remove("hidden");
  //: The count belongs beside the word, the way every other counted list in
  //: this sidebar reads, so the heading answers "how deep is this document"
  //: without the eye having to run down the list.
  const folds = docOutlineFolds();
  const needle = docOutlineFilterText();
  const visible = docOutlineVisibility(headings, needle, folds);
  const shownCount = visible.filter((row) => row.shown).length;
  const count = $("doc-outline-count");
  //: "3 of 18" while filtering, because a bare "3" over a list somebody has
  //: just narrowed reads as a document with three headings in it.
  if (count) {
    count.textContent = !headings.length
      ? ""
      : needle
        ? `${shownCount} of ${headings.length}`
        : String(headings.length);
  }
  //: The box appears with the headings that make it worth having, and takes
  //: its own text with it when it goes: a filter left set on a control nobody
  //: can see is an outline that is mysteriously short.
  const filterBox = $("doc-outline-filter");
  if (filterBox) {
    const wanted = headings.length >= DOC_OUTLINE_FILTER_FROM;
    if (!wanted && filterBox.value) filterBox.value = "";
    filterBox.classList.toggle("hidden", !wanted);
  }
  //: **Nothing the rows show has changed, so the rows stay.** This runs on
  //: every pause in the typing, and typing inside a paragraph changes no
  //: heading: rebuilding every row and then re-marking and re-scrolling the
  //: current one (two forced layouts) was the largest cost of typing in a
  //: long document (INBOX 424). Anything a row is drawn from is in the key.
  const outlineKey = JSON.stringify([
    headings.map((h) => [h.level, h.line, h.text, h.tasks && h.tasks.done, h.tasks && h.tasks.total, Boolean(h.symbol)]),
    needle, [...folds], visible.map((row) => [row.shown, row.foldable]),
  ]);
  if (outlineKey === docOutlineKey && docOutlineRows.length === headings.length && list.isConnected) {
    docOutlineState.headings = headings;
    renderDocCrumbs(where);
    return;
  }
  docOutlineKey = outlineKey;
  list.replaceChildren();
  const empty = $("doc-outline-empty");
  if (empty) {
    empty.classList.toggle("hidden", headings.length > 0);
    empty.textContent = headings.length
      ? ""
      : "Headings you write appear here, and each one jumps to its place in the document.";
  }
  docOutlineRows = [];
  headings.forEach((heading, index) => {
    const li = document.createElement("li");
    li.className = `outline-h${heading.level} outline-row`;
    li.classList.toggle("hidden", !visible[index].shown);
    //: **The fold control is a gutter at the row's left edge, the same width
    //: on every row**, drawn as a button where the heading has children under
    //: it and as an empty slot where it does not. It cannot go inside the row
    //: itself, which is already a `<button>` that jumps to the heading, and a
    //: button inside a button is neither valid nor reachable. It cannot step
    //: with the indent either: `.outline-link`'s own padding is what carries
    //: depth (05-sidebars-themes.css spends a paragraph on why the left edges
    //: have to line up), and a caret that moved with it would put the deepest
    //: rows' controls in four different columns.
    const twist = document.createElement(visible[index].foldable ? "button" : "span");
    twist.className = "outline-twist";
    if (visible[index].foldable) {
      const folded = folds.has(docOutlineFoldKey(heading));
      twist.type = "button";
      twist.setAttribute("aria-expanded", folded ? "false" : "true");
      twist.title = folded
        ? `Show what is under \u201c${heading.text}\u201d`
        : `Hide what is under \u201c${heading.text}\u201d`;
      twist.setAttribute("aria-label", twist.title);
      const glyph = document.createElement("i");
      glyph.className = folded ? "ph ph-caret-right" : "ph ph-caret-down";
      glyph.setAttribute("aria-hidden", "true");
      twist.appendChild(glyph);
      twist.addEventListener("click", () => {
        const key = docOutlineFoldKey(heading);
        const next = docOutlineFolds();
        if (next.has(key)) next.delete(key);
        else next.add(key);
        docOutlineSetFolds(next);
        //: Redrawn rather than toggled in place: the rows a fold hides are
        //: decided by one pass over the whole list (`docOutlineVisibility`),
        //: and a second way of deciding it here would be a second answer.
        renderDocOutline();
      });
    } else {
      twist.setAttribute("aria-hidden", "true");
    }
    li.appendChild(twist);
    const button = document.createElement("button");
    button.type = "button";
    button.className = "outline-link";
    //: The words in their own box, so a long heading ends in an ellipsis and its task count keeps its room
    //: (the owner, 2026-11-05: "outlines just get cut off with no ellipsis and the numbers on the right dont even show").
    const words = document.createElement("span");
    words.className = "outline-text";
    words.textContent = heading.text;
    button.appendChild(words);
    button.title = `Jump to “${heading.text}”`;
    if (heading.tasks) {
      const chip = document.createElement("span");
      const { done, total } = heading.tasks;
      chip.className = done === total ? "outline-tasks outline-tasks-done" : "outline-tasks";
      chip.textContent = `${done}/${total}`;
      //: The chip is a number on a row that is already a link, so the row's
      //: own name has to carry what the number means: a screen reader reading
      //: "Design notes 2/5" is reading a fraction with no unit.
      button.title = `Jump to “${heading.text}”: ${done} of ${nounCount(total, "task")} done`;
      chip.setAttribute("aria-label", `${done} of ${nounCount(total, "task")} done`);
      button.appendChild(chip);
    }
    button.addEventListener("click", () => jumpToDocLine(heading.line));
    //: **Drag to reorder.** On the `li` rather than on the button, because the
    //: gutter's caret is inside the row too and a reader who grabs the caret
    //: means the row. `draggable` only while nothing is being filtered: the
    //: rows on screen are then a search result rather than the document's
    //: order, and dropping one "between" two rows that are not next to each
    //: other in the document is a position nobody could have meant.
    //: A symbol is not a section: a function dragged by its first line would
    //: take the lines up to the next symbol with it, which is not the
    //: function. Code rows jump; only headings move.
    if (!needle && !heading.symbol) {
      li.draggable = true;
      li.addEventListener("dragstart", (event) => {
        docOutlineDragIndex = index;
        li.classList.add("is-dragging");
        event.dataTransfer.effectAllowed = "move";
        //: Something has to be set or Firefox refuses to start the drag, and
        //: the heading's own text is the honest thing to carry: dropped into
        //: any other editor it reads as what was dragged.
        event.dataTransfer.setData("text/plain", heading.text);
      });
      li.addEventListener("dragend", () => {
        docOutlineDragIndex = -1;
        li.classList.remove("is-dragging");
        docOutlineClearDrop();
      });
      li.addEventListener("dragover", (event) => {
        if (docOutlineDragIndex === -1 || docOutlineDragIndex === index) return;
        event.preventDefault();
        event.dataTransfer.dropEffect = "move";
        const after = docOutlineDropAfter(li, event.clientY);
        docOutlineClearDrop();
        li.classList.add(after ? "is-drop-after" : "is-drop-before");
      });
      li.addEventListener("dragleave", () => li.classList.remove("is-drop-before", "is-drop-after"));
      li.addEventListener("drop", (event) => {
        if (docOutlineDragIndex === -1 || docOutlineDragIndex === index) return;
        event.preventDefault();
        const from = docOutlineDragIndex;
        const after = docOutlineDropAfter(li, event.clientY);
        docOutlineDragIndex = -1;
        docOutlineClearDrop();
        if (!docOutlineMoveSection(from, index, after)) {
          toast("That section cannot go inside itself.", "info");
        }
      });
    }
    button.addEventListener("keydown", (event) => {
      if (!event.altKey || (event.key !== "ArrowUp" && event.key !== "ArrowDown")) return;
      if (heading.symbol) return;
      event.preventDefault();
      if (!docOutlineNudge(index, event.key === "ArrowDown" ? 1 : -1)) {
        announce("That section cannot move any further.");
      }
    });
    li.appendChild(button);
    list.appendChild(li);
    //: `row` as well as `button`, because the scroll-spy has to know whether
    //: the heading it wants to mark is on screen at all: a fold or a filter
    //: can hide the row the caret is in, and marking a hidden row is a mark
    //: nobody sees followed by a scroll to nothing.
    docOutlineRows.push({ line: heading.line, button, row: li });
  });
  //: The rows are new elements, so whatever was marked a moment ago is gone
  //: with them. Marked again here rather than waiting for the next scroll:
  //: the outline is rebuilt on a pause in typing, and a table of contents
  //: that forgets where you are every time you stop typing is worse than one
  //: that never knew.
  docOutlineMarked = -1;
  markDocOutline(where);
  //: **The focus ring, restored after a move rewrote the rows.** Kept across
  //: renders rather than applied once, because a move schedules a second
  //: render of its own (see `docOutlineNudge`), and given up the moment focus
  //: is somewhere this panel does not own: a reader who has gone back to
  //: typing must not have the ring yanked into the sidebar by a redraw.
  if (docOutlineFocusKey) {
    const active = document.activeElement;
    const ours = !active || active === document.body || list.contains(active);
    const wanted = ours
      ? headings.findIndex((heading) => docOutlineFoldKey(heading) === docOutlineFocusKey)
      : -1;
    if (!ours || wanted === -1) docOutlineFocusKey = "";
    else docOutlineRows[wanted]?.button.focus();
  }
  //: The breadcrumb reads this list rather than the document, so it is set
  //: here and the trail is redrawn on the same beat the outline is.
  docOutlineState.headings = headings;
  docOutlineState.crumbsKey = "";
  renderDocCrumbs(where);
}

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
let docOutlineKey = "";
let docOutlineMarked = -1;
//: The row a move asked to keep the focus ring on, as a fold key (level and
//: text), because that is the one name for a heading that survives the
//: document being rewritten around it.
let docOutlineFocusKey = "";

//: Which row is in the air. One number rather than a `dataTransfer` payload,
//: because the payload a browser hands back on `drop` is a string and the one
//: thing this needs is an index into the list the drag started from.
let docOutlineDragIndex = -1;
let docOutlineSpyFrame = 0;

//: The first line of the document that is on screen, zero-based.
//:
//: CodeMirror is asked where the top-left of its own scroller lands, which is
//: exact and costs one hit test. `posAtCoords` with `precise` false never
//: returns null, so a coordinate above the first line or below the last still
//: answers with the nearest position rather than with nothing.
//:
//: The textarea fallback has no line-to-pixel map at all, so it estimates
//: from the scroll fraction. That is honestly approximate, and it is the
//: surface nobody has when the engine loads; saying so here is cheaper than a
//: reader wondering why one branch is exact and the other is not.
function docVisibleTopLine() {
  const box = docSurface();
  if (!box) return 0;
  if (box.kind === "codemirror") {
    const view = box.view;
    const rect = view.scrollDOM.getBoundingClientRect();
    const pos = view.posAtCoords({ x: rect.left + 4, y: rect.top + 4 }, false);
    const at = Math.max(0, Math.min(Number(pos) || 0, view.state.doc.length));
    return view.state.doc.lineAt(at).number - 1;
  }
  const range = box.scrollHeight - box.clientHeight;
  if (range <= 0) return 0;
  const lines = box.text.split("\n").length;
  return Math.round((box.scrollTop / range) * Math.max(0, lines - 1));
}

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

//: **The caret's line, but only while the caret is on screen.**
//:
//: Reported (OPEN.md, doc-sidebar.md): typing in a section below the one at
//: the top of the view marked the wrong heading until the view scrolled.
//: Measured on a twelve-section document in a 512px box before this existed:
//: the caret in Section 3 with the view still at `scrollTop` 0, the outline
//: marked Section 1.
//:
//: **Which wins when the two disagree**, the question the next step had not answered:
//: the caret does, while it is visible. A caret you can see is where you are
//: writing, and every editor this is measured against (Obsidian, Typora)
//: follows it. Scroll far enough that the caret leaves the box and it is no
//: longer where you are looking, so the top of the view takes over again: that
//: is reading, not writing, and the same rule covers the Read pane, where
//: there is no caret to see at all.
//:
//: Null rather than a line number when there is nothing to say, so the caller
//: reads as the rule: "the caret's line if it is visible, otherwise the top of
//: the view".
function docCaretVisibleLine() {
  const box = docSurface();
  if (!box || box.kind !== "codemirror") {
    //: The textarea fallback has no line-to-pixel map (see `docVisibleTopLine`
    //: for the same gap), so there is no honest way to ask whether its caret
    //: is on screen. The viewport answer is the one it has always had.
    return null;
  }
  const view = box.view;
  const frame = view.scrollDOM.getBoundingClientRect();
  //: A hidden pane measures 0x0, and "top >= top and bottom <= bottom" would
  //: then be true of a coordinate that is nowhere.
  if (frame.height < 1) return null;
  let coords = null;
  try {
    coords = view.coordsAtPos(view.state.selection.main.head);
  } catch {
    //: A position mid-teardown, which CodeMirror answers for with null anyway.
    return null;
  }
  if (!coords) return null;
  if (coords.top < frame.top || coords.bottom > frame.bottom) return null;
  return view.state.doc.lineAt(view.state.selection.main.head).number - 1;
}

//: **The line the breadcrumb is about**: the caret's while it is on screen,
//: the top of the view otherwise, which is the rule the outline's mark has
//: always used (`markDocOutline`) and now the trail follows it too. Measured
//: (`doccrumbview.js`) in a 21k-word document scrolled to 60% with the caret
//: left on line 1: the outline marked the section in view and the trail above
//: the writing still said `Top > Annual report`, two rows that both answer
//: "where am I" giving two answers. The textarea fallback keeps the caret, its
//: only honest answer (it has no line-to-pixel map).
function docWhereLine() {
  const box = docSurface();
  if (!box || box.kind !== "codemirror") return docCaretLine();
  const caret = docCaretVisibleLine();
  return caret === null ? docVisibleTopLine() : caret;
}

//: The marked row, kept inside whichever box in the sidebar actually scrolls.
//: Bounded by `#doc-sidebar` on purpose: `scrollIntoView` walks every
//: scrolling ancestor, and the page is one of them, so the tidy one-liner
//: would yank the whole tab under the person's caret while they typed.
function keepOutlineRowInView(el) {
  const limit = $("doc-sidebar");
  if (!limit) return;
  let box = el.parentElement;
  while (box && limit.contains(box) && box.scrollHeight <= box.clientHeight + 1) {
    box = box.parentElement;
  }
  if (!box || !limit.contains(box)) return;
  const row = el.getBoundingClientRect();
  const frame = box.getBoundingClientRect();
  if (row.top < frame.top) box.scrollTop -= frame.top - row.top + 8;
  else if (row.bottom > frame.bottom) box.scrollTop += row.bottom - frame.bottom + 8;
}

//: `known` is `docWhereLine()` read by a caller before it wrote anything; a
//: render passes it, and the row is then brought into view after the frame's
//: layout rather than measured against rows it has just built.
function markDocOutline(known) {
  if (!docOutlineRows.length) return;
  //: The caret's section while the caret is on screen, the top of the view
  //: otherwise: see `docCaretVisibleLine` for why that is the order.
  const cm = docSurface()?.kind === "codemirror";
  let top = cm && known != null ? known : null;
  if (top === null) {
    const caret = docCaretVisibleLine();
    top = caret === null ? docVisibleTopLine() : caret;
  }
  //: The trail follows the same line (see `docWhereLine`); the textarea
  //: fallback keeps the caret for it.
  renderDocCrumbs(cm ? top : docCaretLine());
  //: The last heading at or above the top of the view: the section whose text
  //: you are reading, not the next one down.
  let index = 0;
  for (let i = 0; i < docOutlineRows.length; i++) {
    if (docOutlineRows[i].line > top) break;
    index = i;
  }
  //: **Up to the nearest row that is actually drawn.** A folded section's
  //: headings are still in this list (the spy is about the document, not
  //: about the panel), so the heading the caret is in may be hidden under a
  //: fold: the mark then belongs on the fold's own row, which is the one the
  //: reader can see and the one that says "you are somewhere in here". While
  //: a filter is running there may be no such row at all, and then nothing is
  //: marked, which is honest: the rows on screen are a search result, not a
  //: place in the document.
  while (index > 0 && docOutlineRows[index].row?.classList.contains("hidden")) index -= 1;
  if (docOutlineRows[index].row?.classList.contains("hidden")) index = -1;
  if (index === docOutlineMarked) return;
  for (const row of docOutlineRows) {
    row.button.classList.remove("is-current");
    row.button.removeAttribute("aria-current");
  }
  if (index === -1) {
    docOutlineMarked = -1;
    return;
  }
  const button = docOutlineRows[index].button;
  button.classList.add("is-current");
  //: `location` rather than `true`: this is where the reader is in a
  //: document, which is exactly what the token means, and it is what makes
  //: the mark reach a screen reader instead of being a colour.
  button.setAttribute("aria-current", "location");
  docOutlineMarked = index;
  if (known === undefined) keepOutlineRowInView(button);
  else afterFrames(() => setTimeout(() => button.isConnected && keepOutlineRowInView(button)), 1);
}

//: One mark per frame. A scroll fires far faster than anything needs to be
//: repainted, and the work behind it is a hit test plus a class swap.
function scheduleDocOutlineSpy() {
  //: **Read in the engine's own measure pass** (DX1): asked from a frame of
  //: its own, `coordsAtPos` laid the editor out a second time per key (357 ms
  //: over 60 keys at 4x CPU in a 3,120-line document).
  if (docCmView && docSurface()?.kind === "codemirror") {
    docCmView.requestMeasure({ key: scheduleDocOutlineSpy, read: docWhereLine, write: (line) => markDocOutline(line) });
    return;
  }
  if (docOutlineSpyFrame) return;
  docOutlineSpyFrame = requestAnimationFrame(() => {
    docOutlineSpyFrame = 0;
    markDocOutline();
  });
}

// Put the caret at the start of a line and scroll it into view. Done by
// character offset because that is the one coordinate both surfaces share: a
// textarea has no anchors, and CodeMirror's own `scrollIntoView` is reached
// through `setSelection` below rather than by arithmetic.
function jumpToDocLine(lineIndex) {
  const box = docSurface();
  if (!box) return;
  const lines = box.text.split("\n");
  const offset = lines.slice(0, lineIndex).reduce((n, l) => n + l.length + 1, 0);
  box.focus();
  box.setSelection(offset, offset + (lines[lineIndex] || "").length);
  if (box.kind === "codemirror") return; // the transaction above scrolled it
  // Approximate: scroll proportionally to where the line sits in the text.
  const ratio = lineIndex / Math.max(1, lines.length);
  box.scrollTop = Math.max(0, ratio * box.scrollHeight - box.clientHeight / 3);
}

// Answers "where is this actually kept?" with the real path, once.
let storageInfo = null;

async function renderDocStorage() {
  const el = $("doc-storage-path");
  if (!el) return;
  if (!storageInfo) {
    storageInfo = await apiJson("/storage").catch(() => null);
  }
  el.textContent = storageInfo ? storageInfo.database : "(couldn't read the path)";
}

// PLAN.md P4. With the preview open (Split/Rendered) every keystroke used to
// re-parse and re-render the whole document: measured on a 20k-word document
// with scratchpad/ui-sweeps/doctype.js, 44 keystrokes → 44 full renders,
// keydown p50 176ms / p95 272ms, the caret visibly lagged the typing. The
// preview is display, not state, so it can wait for the typing to pause:
// a 120ms trailing debounce, then an idle callback (with a ceiling, so a
// busy tab still repaints within a third of a second). Anything that needs
// the preview *now*, a view switch, a load, still calls renderDocPreview
// directly.
let docPreviewTimer = null;

//: Set by `renderDocPreview`, read by `docScrollAnchors`. Zero until the
//: preview has been drawn once, which is also when there are no stamps to
//: read, so the default is never used as an answer.
let docPreviewLineShift = 0;

function scheduleDocPreview() {
  const preview = $("doc-preview");
  if (!preview || preview.classList.contains("hidden")) return;
  clearTimeout(docPreviewTimer);
  docPreviewTimer = setTimeout(() => {
    docPreviewTimer = null;
    if (typeof requestIdleCallback === "function") {
      requestIdleCallback(() => renderDocPreview(), { timeout: 300 });
    } else {
      requestAnimationFrame(() => renderDocPreview());
    }
  }, 120);
}

function renderDocPreview() {
  const preview = $("doc-preview");
  if (preview.classList.contains("hidden")) return;
  //: 1546 D5: a diagram's preview is the block pane with its picture beside the blocks (diagram-
  //: builder.js); it keeps its own DOM between changes, so the preview is not emptied first.
  //: Each block gesture hands its printed source to `set` (one history step each: `docUndoBreak`);
  //: a typed edit or an undo comes back through here. Inline, not a named function: one global less.
  if (docFileType().ext === "mmd") {
    preview.dataset.dgmLayout = docViewState.layout;
    const text = docText();
    const io = { key: currentDoc?.id, name: $("doc-title").value, set: (next) => (docUndoBreak(), (docSurface().text = next)), undo: () => docUndo(), redo: () => docRedo(), get canUndo() { return docCanUndo(); }, get canRedo() { return docCanRedo(); } };
    ensureModule("diagramBuilder").then((ok) => {
      //: A diagram the blocks cannot take (another kind, over 120 blocks) opens in Split, which is Source with its picture
      //: and the one line saying why; once per document, so a person who goes back to Blocks is not sent out again.
      if (ok) return diagramModel.builder.show(preview, io, text).then((S) => {
        const seen = (docViewState.plain ??= new Set());
        if (S?.plain && docView === "rendered" && !seen.has(currentDoc?.id)) (seen.add(currentDoc?.id), setDocView("split", { persist: false }));
      });
      preview.replaceChildren(Object.assign(document.createElement("p"), { className: "muted", textContent: "The block editor did not load. Source still works." }));
    });
    return;
  }
  preview.replaceChildren();
  const title = ($("doc-title").value || "").trim();
  const text = docText();
  //: **The properties are not prose.** Rendered as markdown, a frontmatter
  //: block is a horizontal rule, a paragraph of `key: value` lines and
  //: another rule, which is what the preview showed until now for every
  //: document this app's own vault import wrote. They come out of the body
  //: and go back in above it as the same rows the panel draws, read-only.
  const fm = docFrontmatterParse(text);
  //: The block markers come out here rather than in the renderer: `^abc123`
  //: is what makes a paragraph linkable and it is not what the paragraph
  //: says, and this pane is the one a person reads and prints.
  //: **The remarks come out of the rendered pane** (Phase 5 item 1): a comment
  //: is a note to the author, and Read view is the document as it reads. In a
  //: print they become footnotes instead, so a PDF handed to somebody carries
  //: them rather than dropping them silently, which is what `docPrintComments`
  //: is set for by `exportDocumentPdf`.
  const remarks = docPrintComments ? docCommentFootnotes : docCommentStrip;
  const stripped = fm ? docFrontmatterStrip(text) : text;
  //: Suggested changes are drawn as struck and highlighted words (PROSE-TOOLS).
  const body = docSuggestForRead(remarks(docBlockStripIds(stripped)));
  //: **How far the preview's line numbers are from the editor's.** Every
  //: block this renders carries the line it came from (`data-src-line`,
  //: `renderMarkdown` in navigation.js), but it came from the line in the string
  //: below, not in the document: the title is prepended as a heading and the
  //: frontmatter is taken off the front, so the two texts are the same words
  //: at different line numbers. The split view's scroll map reads the stamps
  //: and has to undo this, or it lines the panes up two lines out on every
  //: titled document (`docScrollAnchors`).
  //:
  //: Both terms are prefix changes, which is what makes one number enough.
  //: The one transformation that is not is a remark removed by
  //: `docCommentStrip`, and only when the remark spans a line break: that
  //: shortens the text somewhere in the middle and everything below it drifts
  //: by those lines. Bounded, rare, and a line or two against the hundreds of
  //: pixels this map exists to remove, so it is written down here rather than
  //: paid for with a second parse of the document on every render.
  //: **Not twice** (INBOX 437 (4)): a body that already opens on its own
  //: name as a heading (every template, and most imports) read "Meeting
  //: notes" over "Meeting notes", so the name only goes on when it is not.
  const opens = body.trimStart().split("\n", 1)[0];
  const lead = !!title && !(/^#\s/.test(opens) && opens.slice(1).trim().toLowerCase() === title.toLowerCase());
  docPreviewLineShift =
    (lead ? 2 : 0) - (text.split("\n").length - stripped.split("\n").length);
  docRenderBody(preview, lead ? `# ${title}\n\n${body}` : body);
  //: Named, so a phone can leave it to the head row that already shows it
  //: (10-responsive.css, "The first line under the chrome").
  if (lead) {
    const head = preview.querySelector(":scope > .md-h1");
    head?.classList.add("doc-preview-title");
    //: The contents list was filled while the title looked like any heading;
    //: filled again without it, it leaves the added title out (DX23).
    head?.remove();
    mdFillTocs(preview);
    if (head) preview.prepend(head);
  }
  if (fm) {
    //: After the title, which is the document's name rather than part of its
    //: text, and before the first thing its author wrote.
    preview.insertBefore(docPropsReadNode(fm), preview.children[title ? 1 : 0] || null);
  }
  layerDocWikiLinks(preview);
  imageLayoutRoot(preview);
  docRenderMermaidIn(preview);
  docMathRender.graphIn(preview);
  docMathRender.baseIn(preview);
  docMathRender.queryIn(preview);
  docEmbedFill.editButtons(preview);
  docEmbedFill.tagChips(preview);
  docWireReadTasks(preview, text);
}

//: **Tick a task in the Read view.** The renderer draws every task box
//: disabled (it is shared with notes and chat, which have no source to write
//: back to). Here the document is open, so the Nth box is matched to the Nth
//: task line of the text, outside the properties and any code fence, and
//: switched on only when the counts agree: a box that cannot be traced to its
//: line stays as it was rather than ticking the wrong one.
const DOC_READ_TASK = /^(\s*[-*+]\s+)\[([ xX])\](\s)/;

function docTaskLines(text) {
  const lines = String(text).split("\n");
  const out = [];
  let at = 0;
  let fence = null;
  let i = 0;
  const fm = docFrontmatterParse(text);
  if (fm) {
    const cut = docFrontmatterStrip(text);
    const skipped = text.length - cut.length;
    while (at < skipped && i < lines.length) {
      at += lines[i].length + 1;
      i += 1;
    }
  }
  for (; i < lines.length; i += 1) {
    const line = lines[i];
    const mark = line.match(/^\s*(```+|~~~+)/);
    if (mark) {
      if (!fence) fence = mark[1][0];
      else if (mark[1][0] === fence) fence = null;
    } else if (!fence && DOC_READ_TASK.test(line)) {
      out.push({ from: at, line });
    }
    at += line.length + 1;
  }
  return out;
}

function docWireReadTasks(preview, text) {
  const boxes = [...preview.querySelectorAll("li.md-task input[type=checkbox]")];
  if (!boxes.length) return;
  const tasks = docTaskLines(text);
  if (tasks.length !== boxes.length) return;
  boxes.forEach((box, n) => {
    box.disabled = false;
    //: **The Live view's task box, not a second one** (audit 1102 DX21): a
    //: native box at the text's size was 14.7px, under the 24px a pressable
    //: target needs (WCAG 2.5.8), and a native box cannot be padded out. The
    //: press strip and the drawn box are `.cm-md-task-hit` and `.cm-md-task`
    //: (09-editor.css), the same two the Live widget uses, so the views agree.
    if (!box.parentElement.classList.contains("cm-md-task-hit")) {
      const hit = document.createElement("span");
      hit.className = "cm-md-task-hit";
      box.classList.add("cm-md-task");
      box.replaceWith(hit);
      hit.append(box);
    }
    box.dataset.docTask = String(n);
    box.setAttribute("aria-label", box.checked ? "Done" : "Not done");
  });
  if (preview.dataset.taskWired === "1") return;
  preview.dataset.taskWired = "1";
  //: A press on the strip beside the box lands on the strip (a pseudo-element
  //: cannot be the target), so it is forwarded to the box it belongs to.
  preview.addEventListener("click", (event) => {
    const hit = event.target instanceof Element ? event.target.closest(".cm-md-task-hit") : null;
    const box = hit?.firstElementChild;
    if (box && event.target === hit && !box.disabled) box.click();
  });
  preview.addEventListener("change", (event) => {
    const box = event.target;
    if (!(box instanceof HTMLInputElement) || box.dataset.docTask === undefined) return;
    const surface = docSurface();
    const task = docTaskLines(surface?.text ?? "")[Number(box.dataset.docTask)];
    const match = task && task.line.match(DOC_READ_TASK);
    if (!match) {
      box.checked = !box.checked;
      return;
    }
    const at = task.from + match[1].length + 1;
    surface.replaceRange(at, at + 1, box.checked ? "x" : " ");
    box.setAttribute("aria-label", box.checked ? "Done" : "Not done");
  });
}

//: **The document, rendered, with its columns side by side.** `renderMarkdown`
//: is the app's one markdown renderer and knows nothing about `:::columns`;
//: teaching it would put a documents-editor construct into the renderer every
//: note card and every chat message uses. So the text is split here, at the
//: blocks the model finds, and each column is rendered by that same renderer
//: into its own element. The result is one pass over the document either way,
//: and a document with no columns in it takes exactly the path it always did.
function docRenderBody(container, raw) {
  //: Footnotes over the whole document, before it is cut into pieces (audit
  //: FEAT-03): a note defined at the foot is cited from every piece above it,
  //: and each piece's own `renderMarkdown` would see only its half.
  const footnotes = mdFootnotePrepare(docPairInput.citeFootnotes(String(raw ?? "")).split("\n"));
  const text = footnotes.lines.join("\n");
  const pieces = () => {
    const blocks = docColumnsBlocks(text);
    if (!blocks.length) {
      container.replaceChildren();
      docRenderFlow(container, text);
      mdFootnotesFinish(container, footnotes.notes);
      //: Once more over the whole page: the flow is rendered in pieces (around
      //: block embeds and columns), and a `[TOC]` has to list every heading,
      //: not only the ones in its own piece.
      mdFillTocs(container);
      return;
    }
    container.replaceChildren();
    //: The line an offset is on, for the pieces' `lineBase`.
    const lineOf = (offset) => {
      let count = 0;
      for (let i = text.indexOf("\n"); i !== -1 && i < offset; i = text.indexOf("\n", i + 1)) count += 1;
      return count;
    };
    let at = 0;
    for (const block of blocks) {
      if (block.from > at) docRenderFlow(container, text.slice(at, block.from), lineOf(at));
      const box = document.createElement("div");
      box.className = `doc-cols md-cols md-cols-${block.columns.length}`;
      box.dataset.srcLine = String(block.openLine);
      box.style.setProperty("--doc-cols", String(Math.max(1, block.columns.length)));
      for (const column of block.columns) {
        const col = document.createElement("div");
        col.className = "doc-col";
        docRenderFlow(col, column.text, lineOf(column.from));
        box.appendChild(col);
      }
      container.appendChild(box);
      at = block.to;
    }
    if (at < text.length) docRenderFlow(container, text.slice(at), lineOf(at));
    mdFootnotesFinish(container, footnotes.notes);
    mdFillTocs(container);
  };
  //: Equation labels over the whole document too: `\eqref{k}` above its `\label{k}` names the number below it (OPEN F1).
  const labels = window.docMathRender?.labels;
  labels?.use(labels.index(raw));
  //: Held while the pieces render: a column's own render must not re-index its text alone, or `\eqref` to another column reads (?).
  if (labels) labels.held = true;
  try {
    pieces();
  } finally {
    if (labels) labels.held = false;
  }
}

//: `![[Document#^an-id]]` on its own line (DOCUMENTS_PLAN Phase 4 item 2).
//: The id shape is the model's, so a `#^` that is not a block reference stays
//: an ordinary embed and goes to the app's renderer as before.
const DOC_BLOCK_EMBED_LINE =
  /^[ \t]*!\[\[([^[\]\n]{1,120}#\^[A-Za-z0-9][A-Za-z0-9-]{0,31})\]\][ \t]*$/;

//: A run of markdown with its block embeds drawn by `docEmbedNode` rather
//: than by `renderMarkdown`.
//:
//: The app's one markdown renderer resolves an `![[name]]` through
//: `resolveWikiTarget`, which knows notes, boards and documents and cannot
//: know about a block: a block reference is written into a document's own
//: text by this editor, and `Doc#^abc123` is not a name anything can look up.
//: Left to it, a block embed rendered as "Nothing called that yet" in Read
//: view while the same line drew the block in Live, which is the two panes
//: disagreeing about what the document says. Split out here and handed to the
//: same filler the Live view's widget uses, so they cannot.
//:
//: `lineBase` is the line this piece starts on in the whole rendered text.
//: **Every block's `data-src-line` is a line of the whole text, not of its
//: piece.** `renderMarkdown` counts from the start of the string it is given,
//: and this renders the page in pieces (around block embeds and columns), so
//: every block after the first piece carried a line counted from the wrong
//: zero: the split view's anchors dropped them (`docScrollAnchors` skips a
//: line that goes backwards) and the block bar could not find them in the
//: text at all (INBOX 421 b's "change it from the rendered block").
function docRenderFlow(container, text, lineBase = 0) {
  const lines = String(text == null ? "" : text).split("\n");
  let buffer = [];
  let bufferStart = 0;
  const flush = () => {
    if (!buffer.length) return;
    docAppendRendered(container, buffer.join("\n"), lineBase + bufferStart);
    buffer = [];
  };
  lines.forEach((line, index) => {
    const match = DOC_BLOCK_EMBED_LINE.exec(line);
    if (!match) {
      if (!buffer.length) bufferStart = index;
      buffer.push(line);
      return;
    }
    flush();
    const host = document.createElement("div");
    host.className = "doc-embed-host";
    host.dataset.srcLine = String(lineBase + index);
    docEmbedFill(host, match[1].trim());
    container.appendChild(host);
  });
  flush();
}

//: `renderMarkdown` replaces its container's children, so a second call into
//: the same one would take the first's work away. Rendered into a spare
//: element and moved across, which is also what keeps every piece in document
//: order.
function docAppendRendered(container, text, lineBase = 0) {
  const spare = document.createElement("div");
  renderMarkdown(spare, text);
  if (lineBase) {
    for (const block of spare.children) {
      if (block.dataset.srcLine !== undefined) block.dataset.srcLine = String(Number(block.dataset.srcLine) + lineBase);
    }
  }
  while (spare.firstChild) container.appendChild(spare.firstChild);
}

//: The properties as they read rather than as they are edited: the same rows,
//: without the fields. Read view has no editing surface at all, so a panel of
//: inputs there would be a form that saves into a document you are not in.
function docPropsReadNode(fm) {
  const box = document.createElement("div");
  box.className = "doc-props doc-props-read";
  for (const entry of fm.entries) {
    const row = document.createElement("div");
    row.className = "doc-prop-row";
    const key = document.createElement("span");
    key.className = "doc-prop-key";
    key.textContent = entry.key;
    const value = document.createElement("div");
    value.className = "doc-prop-value";
    if (entry.kind === "list") {
      for (const item of entry.items) {
        const chipEl = document.createElement("span");
        chipEl.className = "chip doc-prop-chip";
        chipWords(chipEl, item.text);
        value.appendChild(chipEl);
      }
    } else {
      value.textContent = entry.value.text;
    }
    row.append(key, value);
    box.appendChild(row);
  }
  return box;
}

// [[Document title]] as clickable links in the preview, the same idea as a
// note's [[wiki link]] (renderNoteText) but resolving against `docs` by
// title instead of by content prefix, documents have real titles. A
// post-process over renderMarkdown's already-built DOM rather than a change
// to the parser itself: renderMarkdown is a hand-rolled block parser shared
// with notes/chat/dashboard, and layering a second concern into its inline
// pass is exactly the kind of touch that's cheap to get subtly wrong for
// every other caller. Skips text inside <code>/<pre> so a literal "[[x]]" in
// a fenced snippet isn't turned into a button.
function layerDocWikiLinks(container) {
  const targets = [];
  const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT, {
    acceptNode(node) {
      if (node.parentElement && node.parentElement.closest("code, pre")) {
        return NodeFilter.FILTER_REJECT;
      }
      return /\[\[[^[\]]{1,120}\]\]/.test(node.nodeValue)
        ? NodeFilter.FILTER_ACCEPT
        : NodeFilter.FILTER_SKIP;
    },
  });
  let node;
  while ((node = walker.nextNode())) targets.push(node);

  for (const textNode of targets) {
    const text = textNode.nodeValue;
    const pattern = /\[\[([^[\]]{1,120})\]\]/g;
    const frag = document.createDocumentFragment();
    let cursor = 0;
    let match;
    while ((match = pattern.exec(text)) !== null) {
      if (match.index > cursor) {
        frag.appendChild(document.createTextNode(text.slice(cursor, match.index)));
      }
      const name = match[1].trim();
      //: Through `docResolveWikiTarget` (above), which is the Notes tab's own
      //: resolver with documents tried first. This pane used to run its own
      //: exact-match-on-`e.title` lookup, which could not resolve the note
      //: form the `[[` picker actually inserts; see that function's comment.
      const target = docResolveWikiTarget(name);
      const label = docWikiTargetLabel(target);
      const link = document.createElement("button");
      link.type = "button";
      link.className = "wiki-link";
      //: The words, not the syntax the target happens to open with: see
      //: `wikiLinkLabel` in shell-reminders.js for why the raw `name` stays in the
      //: document and only what is drawn is cleaned.
      link.textContent = window.wikiLinkLabel ? window.wikiLinkLabel(name) : name;
      link.title = target
        ? `Open ${target.kind === "document" ? "" : `the ${target.kind} `}"${label}"`
        : `Nothing called "${name}" yet.`;
      link.addEventListener("click", (event) => {
        event.stopPropagation();
        docOpenResolvedWikiTarget(target, name);
      });
      frag.appendChild(link);
      cursor = pattern.lastIndex;
    }
    if (cursor < text.length) {
      frag.appendChild(document.createTextNode(text.slice(cursor)));
    }
    textNode.parentNode.replaceChild(frag, textNode);
  }
}

// The PDF export needs the rendered pane on screen for the duration of the
// print, whatever view the user was in, and puts them back afterwards. It is
// the only remaining caller of anything toggle-shaped, the Preview tickbox
// itself became the four-way #doc-view-seg (see setDocView), because with four
// modes a tickbox could not say which one you were in.
//
// It borrows "rendered" rather than "split": what gets printed is the preview
// pane, and at full width it lays out the way the PDF will. If the user is
// already in a mode showing the preview, leave them there, reflowing a pane
// mid-print is how a page break lands in the wrong place.
function withDocPreviewShown(fn) {
  const previous = docView;
  const restoring = !docPreviewShowing(previous);
  if (restoring) setDocView("rendered");
  renderDocPreview();
  fn(() => {
    if (restoring) setDocView(previous);
  });
}

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

//: Every gutter in the document, paired with the textarea it numbers. The
//: documents editor's gutter is the original (`#doc-gutter` beside
//: `#doc-content`); the note capture box and the note edit form get one each
//: from `mountGutterFor`, which records the pairing in `data-for`
//: (UI_MODERNISATION_PLAN Phase 7 item 2: "one toggle, remembered, working
//: for any file type, in all three").
function docGutters() {
  return [...document.querySelectorAll(".doc-gutter")]
    .map((gutter) => ({ gutter, box: gutter.dataset.for ? $(gutter.dataset.for) : docBoxEl() }))
    //: The document's own gutter is the fallback textarea's. Once CodeMirror
    //: is mounted the line numbers are `lineNumbers()` inside the view
    //: (DOCUMENTS_PLAN Phase 2 decision 7) and this column is not drawn at
    //: all, so it drops out of the list rather than numbering a hidden box.
    .filter((pair) => pair.box && !(docCmView && pair.box === docBoxEl()));
}

//: Everything that decides where a *row* sits. The stylesheet carries a static
//: copy of these so the column is not unstyled before this runs, but the
//: static copy is what went wrong: it said `padding-top: 0.5rem` while the
//: textarea's own padding is `--space-4`, which is `calc(0.6rem *
//: var(--density))`. Measured, at density 1, every number sat 1.59px above its
//: line, and the density setting could widen that at will. A number beside the
//: wrong line is not a small cosmetic error: it is the one thing a gutter is
//: for.
//:
//: Only what places a row (INBOX 590): the figures are smaller than the text
//: and set in the stylesheet, and a line box of the text's own height in px
//: centres each one on its row whatever size it is drawn at.
const DOC_GUTTER_PROPS = ["lineHeight", "paddingTop", "paddingBottom"];
const DOC_GUTTER_BASELINE = 0.43;

//: **The gutter is clipped to the textarea, not to the row it sits in.**
//: Reported with a screenshot: numbers 1 to 18 continuing below a textarea
//: that ended at 11. Both wrappers (`.doc-source-wrap` and `.gutter-wrap`) are
//: `align-items: stretch` flex rows, so the gutter took the row's height while
//: the textarea took its own; dragging `#doc-content`'s native resize handle
//: shorter left the column running on down the card. Measured before this: a
//: 260px textarea beside a 585px gutter, 325.4px of numbers past the end of
//: the box they number, and even untouched the gutter was 9.6px too tall.
//:
//: The height is also what makes the scroll lock-step possible at all. A
//: gutter that is taller than its textarea has a *shorter* scrollable range,
//: so `gutter.scrollTop = box.scrollTop` silently clamps: measured, the box at
//: 200 and the gutter stuck at 139, which is two and a half lines of drift
//: that grows the further down you scroll. Same height, same content height,
//: same range, and the assignment is then exact.
//: **Every read, then every write** (OPEN 1076, perfpolish): a write and a
//: layout read per gutter forced one layout per gutter; read all of them
//: first and the writes cost one layout after.
//:
//: **`only` is one box or a list of them** (lag trace, 2026-11-11): the observer below
//: hands over every box that resized in one delivery. A call per box put the
//: second box's reads after the first box's writes, a style and layout pass of
//: the whole page each (two numbered boxes beside 30k nodes, 4x CPU: 141ms over
//: a 20-frame drag); one call per delivery reads all of them, then writes.
function syncDocGutterMetrics(only = null) {
  const jobs = [];
  const wanted = only && (Array.isArray(only) ? only : [only]);
  for (const { gutter, box } of docGutters()) {
    if (wanted && !wanted.includes(box)) continue;
    if (gutter.classList.contains("hidden")) continue;
    const metrics = getComputedStyle(box);
    jobs.push({
      gutter,
      metrics: Object.fromEntries([...DOC_GUTTER_PROPS, "fontSize"].map((prop) => [prop, metrics[prop]])),
      own: parseFloat(getComputedStyle(gutter).fontSize),
      height: box.offsetHeight,
    });
  }
  for (const { gutter, metrics, own, height } of jobs) {
    gutter.style.lineHeight = metrics.lineHeight;
    //: **On the text's baseline, not its centre** (INBOX 590). A smaller
    //: figure in the same line box is centred on the row, which puts its
    //: baseline above the text's by about 0.43 of the difference in size
    //: (measured 2.1px for 11.2px figures beside 16px text, `gutter.js`).
    //: The figures move down by that much and the bottom padding gives it
    //: back, so the column's scroll range stays the box's.
    const drop = DOC_GUTTER_BASELINE * (parseFloat(metrics.fontSize) - own);
    //: Each padding is written once, to its final value: the plain copy and
    //: then the baseline drop on top of it were two invalidations a row.
    const lowered = drop > 0;
    gutter.style.paddingTop = lowered ? `calc(${metrics.paddingTop} + ${drop.toFixed(2)}px)` : metrics.paddingTop;
    gutter.style.paddingBottom = lowered
      ? `max(0px, calc(${metrics.paddingBottom} - ${drop.toFixed(2)}px))`
      : metrics.paddingBottom;
    gutter.style.height = `${height}px`;
  }
}

//: **The box changes height for reasons no event reports.** Dragging
//: `#doc-content`'s own `resize: vertical` handle, opening or closing the chat
//: dock, switching to Split, a note's textarea growing as it is typed into: a
//: `window.resize` listener sees none of them, and the height is exactly what
//: was wrong. One observer, every numbered box.
let docGutterObserver = null;

function watchDocGutter(box) {
  if (!box || typeof ResizeObserver !== "function") return;
  if (!docGutterObserver) {
    docGutterObserver = new ResizeObserver((entries) => {
      const boxes = [];
      for (const entry of entries) {
        //: The status bar's counts ride this one observer (the wake sources are
        //: capped): a box that has no width is not a tab stop (audit 1102 DX21).
        if (entry.target.id === "doc-counts") entry.target.tabIndex = entry.target.clientWidth >= 1 ? 0 : -1;
        else boxes.push(entry.target);
      }
      //: One pass for the whole delivery, reads before writes (see
      //: `syncDocGutterMetrics`).
      if (boxes.length) syncDocGutterMetrics(boxes);
    });
  }
  //: Observing the same element twice replaces the registration rather than
  //: adding a second one, so this is safe to call on every mount and every
  //: toggle.
  docGutterObserver.observe(box);
}

function renderDocGutter(only = null) {
  const pairs = docGutters().filter(({ gutter, box }) => (!only || box === only) && !gutter.classList.contains("hidden"));
  //: The layout reads first, for the reason `syncDocGutterMetrics` gives.
  const heights = pairs.map(({ box }) => box.offsetHeight);
  const tops = pairs.map(({ box }) => box.scrollTop);
  for (const [index, { gutter, box }] of pairs.entries()) {
    const lines = box.value.split("\n").length;
    // One text node of numbers, not one element per line: a 5,000-line file
    // is 5,000 elements to build and lay out on every keystroke otherwise,
    // and the gutter is doing nothing that needs per-line nodes.
    //: Three while the box has the focus: the caret's line is a span of its
    //: own (`.doc-gutter-current`, in the body ink), the editor's mark.
    const numbers = Array.from({ length: lines }, (_, i) => i + 1);
    const at = document.activeElement === box ? box.value.slice(0, box.selectionStart).split("\n").length : 0;
    if (!at) gutter.textContent = numbers.join("\n");
    else {
      const mark = document.createElement("span");
      mark.className = "doc-gutter-current";
      mark.textContent = String(at);
      const before = numbers.slice(0, at - 1).join("\n");
      const after = numbers.slice(at).join("\n");
      gutter.replaceChildren(before ? `${before}\n` : "", mark, after ? `\n${after}` : "");
    }
    //: Height on every paint, not only on mount: the textarea grows and
    //: shrinks with the pane, with the chat dock, and with its own resize
    //: handle, and none of those tells this code anything.
    gutter.style.height = `${heights[index]}px`;
    gutter.scrollTop = tops[index];
  }
}

//: Give a plain textarea a line-number gutter: wrap it, put the gutter
//: before it, and keep the two in step on input and scroll. The gutter copies
//: the textarea's own type metrics and top padding through the CSSOM (an
//: inline `style=` would be refused by the CSP), that, not a shared class,
//: is what makes "1" sit exactly beside the first line whatever font the box
//: uses. Idempotent, so the note edit form can call it on every open.
function mountGutterFor(textarea) {
  if (!textarea || !textarea.id || textarea.parentElement?.classList.contains("gutter-wrap")) {
    return textarea?.previousElementSibling || null;
  }
  const wrap = document.createElement("div");
  wrap.className = "gutter-wrap";
  const gutter = document.createElement("div");
  gutter.className = "doc-gutter hidden";
  gutter.dataset.for = textarea.id;
  gutter.setAttribute("aria-hidden", "true");
  //: Moving a focused element in the DOM blurs it, and this runs the first
  //: time the capture section shows, which is exactly when the phone's + has
  //: just put the caret in the box (measured: focus in at 7598ms, this wrap
  //: at 7753, focus out to nothing at 7737). The caret goes back where it was.
  //: In a microtask, not inline: this also runs at this file's own top level
  //: (`mountGutterFor($("entry-content"))` below), and a focus event fired
  //: mid-evaluation reached `mountNoteSurface` before `docCmBroken` had been
  //: declared (a TDZ ReferenceError on boot when the box starts focused).
  const hadFocus = document.activeElement === textarea;
  textarea.parentElement.insertBefore(wrap, textarea);
  wrap.append(gutter, textarea);
  if (hadFocus) queueMicrotask(() => textarea.focus());
  // The note edit form builds its <li> detached and inserts it afterwards,
  // so at this point `applyDocGutter` (which walks the *document*) cannot
  // see this gutter and `getComputedStyle` returns empty strings. Decide the
  // initial state from the remembered choice right here, and copy the type
  // metrics on the first frame the box is in the document, measured, the
  // form's gutter stayed hidden on every open without both.
  const on = docGutterPref() === "1";
  gutter.classList.toggle("hidden", !on);
  textarea.classList.toggle("has-gutter", on);
  //: One copy routine for every gutter in the app, so the documents editor's
  //: static `#doc-gutter` and the two note boxes' mounted ones cannot disagree
  //: about which properties matter. It grew `height` and the font weight and
  //: style when the column was measured against the text it numbers.
  const copyMetrics = () => {
    syncDocGutterMetrics(textarea);
    watchDocGutter(textarea);
    renderDocGutter(textarea);
  };
  if (textarea.isConnected) copyMetrics();
  else requestAnimationFrame(copyMetrics);
  //: Hidden is checked on this gutter first: `renderDocGutter` walks every
  //: `.doc-gutter` in the page before it looks at one (394 ms over 61 keys in
  //: a 14k-node page, perf-1031 item 2), so a hidden gutter costs no key.
  const paint = () => {
    if (!gutter.classList.contains("hidden")) renderDocGutter(textarea);
  };
  textarea.addEventListener("input", paint);
  for (const type of ["focus", "blur", "keyup", "mouseup"]) textarea.addEventListener(type, paint);
  textarea.addEventListener("scroll", () => {
    if (!gutter.classList.contains("hidden")) gutter.scrollTop = textarea.scrollTop;
  });
  return gutter;
}

//: The lines a selection touches, as [firstLine, lastLine] and the character
//: offsets that bracket them. Indent, dedent and comment-toggle all work on
//: whole lines, and all three need exactly this.
function docSelectedLines(box) {
  const value = box.value;
  const start = value.lastIndexOf("\n", box.selectionStart - 1) + 1;
  let end = value.indexOf("\n", box.selectionEnd);
  if (end === -1) end = value.length;
  // A selection ending exactly at a line start has not touched that line, 
  // without this, selecting one whole line by dragging comments out two.
  if (box.selectionEnd > box.selectionStart && box.selectionEnd === start) {
    end = box.selectionEnd;
  }
  return { start, end, text: value.slice(start, end) };
}

//: Replace a run of the textarea through the browser's own edit pipeline, so
//: the native undo stack keeps working. Assigning `.value` wipes it, which
//: would make Ctrl+Z stop working in exactly the editor where people press it
//: most: the single most important detail in this whole section.
function docReplaceRange(box, start, end, text) {
  //: CodeMirror has its own history and its own transaction pipeline, so the
  //: `execCommand` dance below is not only unnecessary there, it is wrong:
  //: `insertText` on a contenteditable goes through the browser rather than
  //: through the state, and the two would disagree about the document.
  if (box.kind === "codemirror") {
    box.replaceRange(start, end, text);
    return;
  }
  box.focus();
  box.setSelectionRange(start, end);
  if (!document.execCommand || !document.execCommand("insertText", false, text)) {
    // execCommand is deprecated and may be gone. Falling back to a direct
    // write loses native undo for that one edit, which beats the edit not
    // happening: and `markDocDirty` still runs, so nothing is lost.
    const value = box.value;
    box.value = value.slice(0, start) + text + value.slice(end);
  }
}

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

//: Reads the arming *and* clears it, so one Escape buys one Tab: an armed
//: flag left standing would make the next Tab after any Escape, minutes and
//: paragraphs later, throw the writer out of the editor.
function docTakeTabEscape() {
  const armed = docTabEscapes;
  docTabEscapes = false;
  return armed;
}

//: Shift+Tab has something to do only when there is indentation under the
//: selection (or a selection at all, which re-indents its lines). Otherwise
//: it is the browser's, which is what keeps a flush-left caret from being a
//: keyboard trap.
//: A markdown list item, at whatever depth. Tab and Shift+Tab treat one of
//: these as a *block* rather than as a run of characters: pressing Tab with
//: the caret in the middle of "- alpha" indents the bullet, it does not push
//: two spaces into the middle of the word, which is what every editor a
//: writer has used does and what this one did not (measured, 2026-09-12:
//: "- al|pha" plus Tab gave "- al  pha").
const DOC_LIST_LINE = /^([ \t]*)([-*+]|\d+[.)])(\s)/;

//: The number an ordered item at `indent` columns should carry, from the
//: lines above `start`: its previous sibling's plus one, or 1 when a shallower
//: line (the parent) or a break in the list comes first. Deeper lines are the
//: sibling's children and are skipped over.
function docOrderedNumberAt(value, start, indent) {
  const above = value.slice(0, Math.max(0, start - 1)).split("\n");
  for (let i = above.length - 1; i >= 0; i--) {
    const line = above[i];
    if (!line.trim()) continue;
    const m = /^([ \t]*)(?:(\d+)[.)]|[-*+])\s/.exec(line);
    if (!m) {
      if (/^\s/.test(line)) continue;
      return 1;
    }
    if (m[1].length > indent) continue;
    return m[1].length === indent && m[2] ? Number(m[2]) + 1 : 1;
  }
  return 1;
}

function docCanOutdent(box) {
  if (!box) return false;
  if (box.selectionEnd > box.selectionStart) return true;
  return /^[ \t]/.test(docSelectedLines(box).text);
}

function indentDocSelection(box, outdent) {
  //: One undo step per Tab, not one per burst, see `docUndoBreak`.
  docUndoBreak();
  const type = docFileType();
  const unit = type.indent || "  ";
  const { start, end, text } = docSelectedLines(box);
  const multiline = text.includes("\n") || box.selectionEnd > box.selectionStart;
  //: Read before anything is replaced: an edit moves the surface's own
  //: selection, so a caret read afterwards is the engine's guess rather than
  //: where the writer was.
  const caretWas = box.selectionStart;

  // A list item is indented as a whole, from wherever the caret sits in it,
  // and Shift+Tab pulls it back the same way. `DOC_LIST_LINE` carries the
  // reason. The caret is kept where it was in the text rather than being
  // dropped at the line start or spread over the line: an indent that moves
  // the caret is an indent you have to recover from.
  if (!multiline && DOC_LIST_LINE.test(text)) {
    const caret = caretWas;
    const leading = text.match(/^[ \t]*/)[0];
    let next = leading;
    if (!outdent) {
      next = leading + unit;
    } else if (leading.startsWith(unit)) {
      next = leading.slice(unit.length);
    } else {
      next = leading.slice(Math.min(leading.length, unit.length));
    }
    if (next === leading) return; // nothing to remove: the caller lets Tab go
    //: A numbered item that changes level takes its place in the new list:
    //: indented under "1. a" it is the first of a nested list ("1."), and
    //: brought back out it is the parent's next number. Left alone it kept
    //: "2." in a list of one, which renders as "2." and counts from there.
    const digits = /^\d+/.exec(text.slice(leading.length))?.[0] || "";
    const number = digits ? String(docOrderedNumberAt(box.value, start, next.length)) : "";
    docReplaceRange(box, start, start + leading.length + digits.length, next + number);
    const moved = next.length - leading.length + number.length - digits.length;
    const at = Math.max(start + next.length, caret + moved);
    box.setSelectionRange(at, at);
    markDocDirty();
    renderDocGutter();
    return;
  }

  // A plain Tab with no selection inserts one indent at the caret, which is
  // what Tab does in every editor. Only a selection (or Shift+Tab) means
  // "re-indent these lines".
  if (!multiline && !outdent) {
    const at = box.selectionStart;
    docReplaceRange(box, at, box.selectionEnd, unit);
    //: **After the indent, said rather than assumed.** The textarea's
    //: `insertText` leaves the caret after what it inserted; the engine's
    //: `replaceRange` maps a caret sitting exactly at the insertion point to
    //: *before* it. Measured 2026-09-23 in both a code and a markdown
    //: document: Tab then "a" at the start of `int x;` gave `a    int x;`,
    //: so every Tab in the editor since the engine landed put the next
    //: keystroke on the wrong side of the indent it had just made.
    box.setSelectionRange(at + unit.length, at + unit.length);
    markDocDirty();
    renderDocGutter();
    return;
  }

  const lines = text.split("\n");
  const changed = lines.map((line) => {
    if (!outdent) return line ? unit + line : line;
    // Dedent removes one indent unit, or, for a line indented with the
    // wrong-width whitespace, which happens constantly in a pasted file, 
    // up to that many leading spaces. Removing nothing when the line is
    // flush left is correct, not a failure.
    if (line.startsWith(unit)) return line.slice(unit.length);
    const leading = line.match(/^[ \t]+/);
    if (!leading) return line;
    return line.slice(Math.min(leading[0].length, unit.length));
  });
  const joined = changed.join("\n");
  docReplaceRange(box, start, end, joined);
  if (box.selectionEnd > box.selectionStart || multiline) {
    box.setSelectionRange(start, start + joined.length);
  } else {
    //: A Shift+Tab with no selection is a caret gesture, so it leaves a
    //: caret. Selecting the whole line here (what this did until 2026-09-12)
    //: meant the next character typed replaced the line the writer had just
    //: dedented.
    const moved = joined.length - text.length;
    const at = Math.min(Math.max(start, caretWas + moved), start + joined.length);
    box.setSelectionRange(at, at);
  }
  markDocDirty();
  renderDocGutter();
}

function toggleDocComment(box) {
  if (docCodeCommentAtCaret(box)) return;
  docUndoBreak();
  const type = docFileType();
  const { start, end, text } = docSelectedLines(box);
  const lines = text.split("\n");

  if (type.line_comment) {
    const marker = type.line_comment;
    const real = lines.filter((line) => line.trim());
    // Uncomment only when *every* non-blank line is already commented. The
    // other way round (any line commented -> uncomment all) silently strips
    // a real comment that happened to be inside the selection.
    const allCommented =
      real.length > 0 && real.every((line) => line.trimStart().startsWith(marker));
    const changed = lines.map((line) => {
      if (!line.trim()) return line;
      if (allCommented) {
        const at = line.indexOf(marker);
        // Drop one following space if this put one there, so a round trip
        // of comment-then-uncomment gives back exactly the original line.
        const after = line.slice(at + marker.length);
        return line.slice(0, at) + (after.startsWith(" ") ? after.slice(1) : after);
      }
      // Inserted after the existing indentation, not at column zero: a
      // comment marker flush left inside an indented block is legal and ugly,
      // and is not what any editor does.
      const indent = line.match(/^[ \t]*/)[0];
      return `${indent}${marker} ${line.slice(indent.length)}`;
    });
    docReplaceRange(box, start, end, changed.join("\n"));
    box.setSelectionRange(start, start + changed.join("\n").length);
  } else if (type.block_comment) {
    // No line-comment form at all (HTML, XML, CSS). Toggling a line means
    // wrapping it: a prefix would produce a file that no longer parses.
    const [open, close] = type.block_comment;
    const trimmed = text.trim();
    const wrapped = trimmed.startsWith(open.trim()) && trimmed.endsWith(close.trim());
    const changed = wrapped
      ? trimmed.slice(open.trim().length, trimmed.length - close.trim().length).trim()
      : `${open}${text}${close}`;
    docReplaceRange(box, start, end, changed);
    box.setSelectionRange(start, start + changed.length);
  } else {
    // Plain text genuinely has no comment syntax. Doing nothing quietly is
    // right: there is no sensible thing to insert.
    return;
  }
  markDocDirty();
  renderDocGutter();
}

//: **A code document comments by the language at the caret** (INBOX 402),
//: as VS Code does: one HTML file is three languages, so a line inside its
//: `<script>` takes `//`, inside `<style>` `/* */`, and the markup
//: `<!-- -->`; a JSX child takes `{/* */}`. The file-type table above has one
//: marker per file and cannot know that; CodeMirror's own command reads the
//: `commentTokens` of the grammar at the cursor. It keeps this function's
//: rules (uncomment only when every non-blank line is commented, the marker
//: after the indentation, a round trip exact; `tests/test_code_vscode.py`),
//: with one difference, VS Code's: a block of lines takes its marker at the
//: block's own indent, so the block keeps its shape. A grammar with no tokens
//: falls through to the file-type marker; prose, Plain and the textarea
//: fallback never come here.
function docCodeCommentRun(CM, target, block) {
  return block ? CM.commands.toggleBlockComment(target) : CM.commands.toggleComment(target);
}

function docCodeCommentAtCaret(box, block = false) {
  const CM = window.CM6;
  const type = docFileType();
  if (!CM || !docCmView || box?.view !== docCmView || type.previewable || docView === "plain") return false;
  const view = docCmView;
  const target = { state: view.state, dispatch: (tr) => view.dispatch(tr) };
  if (!docCodeCommentRun(CM, target, block)) return false;
  markDocDirty();
  return true;
}

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

//: The table the caret is in, with the cell it is in, or null.
function docTableContext(box = null) {
  const surface = box || docSurface();
  if (!surface) return null;
  const text = surface.text;
  const at = surface.selectionStart;
  const table = docTableParse(text, at);
  if (!table) return null;
  return { surface, text, table, cell: docTableCellAt(table, at) || { row: 0, col: 0 } };
}

//: One transaction for a whole operation, so Ctrl+Z takes back "insert a
//: column" rather than the seven cell edits it was made of.
function docTableDispatch(context, edits) {
  if (!edits || !edits.length) return false;
  const surface = context.surface;
  docUndoBreak();
  if (docCmView && surface.kind === "codemirror") {
    docCmView.dispatch({
      changes: edits.map((edit) => ({ from: edit.from, to: edit.to, insert: edit.insert })),
      scrollIntoView: true,
      annotations: docCmIsolate(),
    });
    return true;
  }
  surface.value = docTableApplyEdits(surface.text, edits);
  finishMarkdownEdit(surface, "doc-content");
  return true;
}

//: Run an operation and put the caret in a named cell, with that cell's text
//: selected so the next keystroke replaces it, which is what Tab does in every
//: table editor the plan names.
//:
//: The selection is worked out *after* the edits have landed rather than
//: predicted from the edits themselves: an insertion earlier in the table
//: moves every offset after it, and a caret computed in the old coordinates is
//: the classic way a table editor drops the caret a column to the left.
function docTableGo(context, edits, row, col) {
  docTableDispatch(context, edits);
  const surface = context.surface;
  let table = docTableParse(surface.text, context.table.from);
  if (!table || !table.rows[row]) return true;
  if (col >= table.rows[row].cells.length) {
    //: The cell GFM pads into existence but the text does not have yet. It has
    //: to be real before the caret can sit in it, or the next keystroke lands
    //: at the end of the previous cell.
    docTableDispatch({ surface, text: surface.text }, docTableFillRowEdits(table, row, col));
    table = docTableParse(surface.text, context.table.from);
  }
  const span = table && docTableCellSpan(table, row, col);
  if (!span) return true;
  const raw = table.rows[row].cells[col];
  //: **An empty cell takes the caret after its first space, not its last.**
  //: A new row is written `|  |  |`, two spaces a cell, and the caret was put
  //: after both: measured, Tab out of the last cell and "Three" typed gave
  //: `|  Three|`, a cell that no longer matched a single other one in the
  //: table. One space in is where a person would have typed it by hand.
  if (!raw.trim()) {
    const at = span.from + Math.min(1, raw.length);
    surface.setSelectionRange(at, at);
    return true;
  }
  const lead = (/^[ \t]*/.exec(raw) || [""])[0].length;
  const tail = (/[ \t]*$/.exec(raw) || [""])[0].length;
  surface.setSelectionRange(span.from + lead, Math.max(span.from + lead, span.to - tail));
  return true;
}

//: Tab moves to the next cell and Shift+Tab to the previous one, which is the
//: one gesture every editor in the plan's competitor table shares. Tab in the
//: last cell adds a row, for the same reason: a table you have to reach for a
//: menu to extend is a table people stop extending. The keydown listener at
//: the end of this file is what calls it (`docTableTab`), because that
//: listener already covers both surfaces.
function docTableTabStep(backwards, from = null) {
  const context = from || docTableContext();
  if (!context) return false;
  const step = docTableStepCell(context.table, context.cell.row, context.cell.col, backwards ? -1 : 1);
  if (step) return docTableGo(context, [], step.row, step.col);
  if (backwards) return false;
  const rows = context.table.rows.length;
  return docTableGo(context, docTableAddRowEdits(context.table, rows - 1), rows, 0);
}

//: The caret at the end of a cell's words, for the gestures that move rather
//: than select (Enter and the arrows): Tab selects the cell it lands in so
//: typing replaces it, and an arrow that did the same would turn the next
//: keystroke into a deletion.
function docTableCaretTo(context, row, col) {
  const surface = context.surface;
  let table = context.table;
  if (!table.rows[row]) return false;
  if (col >= table.rows[row].cells.length) {
    docTableDispatch({ surface, text: surface.text }, docTableFillRowEdits(table, row, col));
    table = docTableParse(surface.text, table.from);
    if (!table) return true;
  }
  const span = docTableCellSpan(table, row, Math.min(col, table.rows[row].cells.length - 1));
  if (!span) return true;
  const raw = surface.text.slice(span.from, span.to);
  const tail = (/[ \t]*$/.exec(raw) || [""])[0].length;
  const at = raw.trim() ? span.to - tail : span.from + Math.min(1, raw.length);
  surface.setSelectionRange(at, at);
  return true;
}

//: Leave a table downwards through `docTableExitEdit`, the way out as data.
function docTableExit(view, table, dropLast) {
  const out = docTableExitEdit(table, docStr(view.state.doc), dropLast);
  view.dispatch({ changes: out.changes, selection: { anchor: out.anchor }, scrollIntoView: true, userEvent: "input" });
  return true;
}

function docTableCtrlEnter(view) {
  const context = docTableContext();
  if (!context || context.surface.kind !== "codemirror" || context.surface.view !== view) return false;
  return docTableExit(view, context.table, false);
}

//: **Enter and the arrows in a Live table** (INBOX 425 i: "tables are still
//: really annoying to use and edit in the documents live view"). Measured
//: before this in `scratchpad/ui-sweeps/doctablework.js`: ArrowDown from the
//: third column landed in the fourth and ArrowUp into the header a column
//: off, because the editor moves by pixels over cells a grid has laid out;
//: Enter in the last row made a row but sent the caret to its first column;
//: and a table that ended the document (or began it) could not be left by
//: the arrows at all, so the only way to write under it was Source view.
//:
//: Now, in Live, the arrows keep the column from row to row (a cell whose
//: words wrap over several lines is walked through first, as any paragraph
//: is), Enter goes to the same column one row down and adds the row at the
//: end, and past the table's edge the arrows leave it, making the blank line
//: markdown needs when there is nothing on that side yet. Source keeps the
//: plain editor's keys: there the rows are text, and moving by column over
//: unaligned pipes would be the surprise.
function docTableKeyMove(view, key) {
  if (docView !== "live") return false;
  const sel = view.state.selection.main;
  if (!sel.empty || view.state.selection.ranges.length > 1) return false;
  const context = docTableContext();
  if (!context || context.surface.kind !== "codemirror" || context.surface.view !== view) return false;
  const { table, cell } = context;
  if (key === "Enter") {
    const last = table.rows[table.rows.length - 1];
    if (cell.row === table.rows.length - 1 && table.rows.length > 2 && !last.cells.some((c) => c.trim())) return docTableExit(view, table, true);
    //: A row typed by hand ends with its closing pipe: Enter there is the
    //: plain newline, so the next line is typed rather than found inside a
    //: cell (typed line by line, `| --- |` then Enter used to add an empty
    //: row and park the next line inside it).
    const line = view.state.doc.lineAt(sel.head);
    if (sel.head === line.to && line.text.trimEnd().endsWith("|")) return false;
    const next = docTableStepRow(table, cell.row, 1);
    if (next !== null) return docTableCaretTo(context, next, cell.col);
    const rows = table.rows.length;
    return docTableGo(context, docTableAddRowEdits(table, rows - 1), rows, cell.col);
  }
  const down = key === "ArrowDown";
  const moved = view.moveVertically(sel, down);
  const landed = docTableCellAt(table, moved.head);
  if (moved.head !== sel.head && landed && landed.row === cell.row && landed.col === cell.col) return false;
  const next = docTableStepRow(table, cell.row, down ? 1 : -1);
  if (next !== null) return docTableCaretTo(context, next, cell.col);
  if (down) return docTableExit(view, table, false);
  const doc = view.state.doc;
  if (table.from > 0) {
    view.dispatch({ selection: { anchor: table.from - 1 }, scrollIntoView: true });
  } else {
    view.dispatch({
      changes: { from: 0, insert: "\n\n" },
      selection: { anchor: 0 },
      scrollIntoView: true,
      userEvent: "input",
    });
  }
  return true;
}

//: A paste that is a spreadsheet's rows. Into a table, it fills cells from
//: the caret's (`docTablePasteEdits`); anywhere else in a markdown document,
//: it becomes a table of its own when the clipboard also carries an HTML
//: table (which every spreadsheet puts there) and the rows are a rectangle
//: of at least two by two, so tab-indented text pasted from a code editor is
//: still pasted as the text it was. Never in a code file.
function docTablePasteEvent(event, view) {
  if (view.dom.classList.contains("doc-content-code")) return false;
  const data = event.clipboardData;
  if (!data) return false;
  const grid = docTableGridFromText(data.getData("text/plain"));
  if (!grid) return false;
  const context = docTableContext();
  if (context && context.surface.kind === "codemirror" && context.surface.view === view) {
    const result = docTablePasteEdits(context.text, context.table, context.cell.row, context.cell.col, grid);
    if (!result) return false;
    event.preventDefault();
    docUndoBreak();
    view.dispatch({ changes: result.edit, userEvent: "input.paste", scrollIntoView: true });
    const table = docTableParse(docStr(view.state.doc), context.table.from);
    if (table) docTableCaretTo({ surface: context.surface, table }, result.row, result.col);
    return true;
  }
  const html = data.getData("text/html") || "";
  const square = grid.length >= 2 && grid[0].length >= 2 && grid.every((row) => row.length === grid[0].length);
  if (!/<table[\s>]/i.test(html) || !square) return false;
  event.preventDefault();
  const { state } = view;
  const sel = state.selection.main;
  const startLine = state.doc.lineAt(sel.from);
  const endLine = state.doc.lineAt(sel.to);
  //: A table is a block: it needs a blank line between it and the text on
  //: either side, or the line after it would be read as one more row.
  const textBefore = state.doc.sliceString(startLine.from, sel.from).trim();
  const lineAbove = startLine.number > 1 ? state.doc.line(startLine.number - 1).text.trim() : "";
  const textAfter = state.doc.sliceString(sel.to, endLine.to).trim();
  const lineBelow = endLine.number < state.doc.lines ? state.doc.line(endLine.number + 1).text.trim() : "";
  const before = textBefore ? "\n\n" : lineAbove ? "\n" : "";
  const after = textAfter ? "\n\n" : lineBelow ? "\n" : "";
  const table = docTableFromGrid(grid);
  docUndoBreak();
  view.dispatch({
    changes: { from: sel.from, to: sel.to, insert: before + table + after },
    selection: { anchor: sel.from + before.length + table.length },
    userEvent: "input.paste",
    scrollIntoView: true,
  });
  docPasteOfferTable(view, sel.from, before + table + after, data.getData("text/plain"));
  return true;
}

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
const DOC_RICH_TAGS = /<(h[1-6]|strong|b|em|i|a\s[^>]*href|ul|ol|blockquote|pre|code|img|table|del|s)[\s>]|<p[^>]*>(?:\s|&nbsp;)*[·•▪§Ø](?:\s|&nbsp;)|MsoList|mso-list/i;
//: **Emphasis kept only in a span's style counts too** (dog3d-1026:7: a lone
//: `<span style="font-weight:700">` arrived as plain text, because no tag in
//: the list above was in it). Not when the copy is code: an editor's copy is a
//: monospace, `white-space: pre` block whose coloured spans are sometimes bold
//: or italic, and those must stay code.
const DOC_RICH_STYLE = /font-weight\s*:\s*(bold|bolder|[6-9]00)\b|font-style\s*:\s*italic/i;
const DOC_CODE_HTML = /white-space\s*:\s*pre|font-family\s*:[^;"]*(mono|consolas|courier|menlo)/i;

function docHtmlIsRich(html) {
  return DOC_RICH_TAGS.test(html) || (DOC_RICH_STYLE.test(html) && !DOC_CODE_HTML.test(html));
}

let docPastePlain = false;

//: **Word's lists are paragraphs, not lists.** A pasted bullet from Word is a
//: `<p>` with `mso-list: l0 level2 lfo1` and a hidden marker span
//: (`mso-list: Ignore`) holding the bullet or "1.", so neither tag test saw a
//: list and "· item" arrived as plain text. Returns the Markdown line, indented
//: by the item's level, or "" for any other paragraph.
function docWordListLine(el, styleOf, inline) {
  const style = styleOf(el, "mso-list");
  //: **A list paragraph with its `mso-list` style stripped is still a list**
  //: (DX32, audit 1102): Word for the web, Outlook and a copy through another
  //: editor keep the `MsoListParagraph` class or only the bullet glyph, and
  //: "· item" arrived as a paragraph starting with a middle dot. One rule for
  //: both: the style, the class, or a leading glyph (`·`, `•`, `▪`, `§`, or
  //: Word's "o" set apart by two spaces) makes the paragraph an item.
  const glyph = /^[\s\u00a0]*(?:[·•▪◦‣§Ø]|o(?=[\s\u00a0]{2}))[\s\u00a0]+\S/.test(el.textContent);
  const styled = Boolean(style) && style !== "none";
  if (!styled && !glyph && !/MsoList/i.test(el.getAttribute("class") || "")) return "";
  const list = styled ? style : "";
  //: Without the style the depth is the indent: Word steps a level by half an inch.
  const inches = Number(/(\d*\.?\d+)in/.exec(styleOf(el, "margin-left"))?.[1] || 0);
  const level = Number(/level(\d+)/.exec(list)?.[1] || (inches ? Math.round(inches / 0.5) : 1));
  //: The marker span is nested (`<span Symbol><span mso-list:Ignore>`), so it
  //: is found by its style wherever it sits, read, and taken out.
  const marks = [...el.querySelectorAll("[data-mm-style]")].filter((c) => styleOf(c, "mso-list") === "ignore");
  const mark = marks.map((c) => c.textContent).join("");
  marks.forEach((c) => c.remove());
  const number = /^\s*(\d+)[.)]/.exec(mark)?.[1] || (/^\s*[a-z]{1,4}[.)]/i.test(mark) ? "1" : "");
  let text = [...el.childNodes].map(inline).join("").replace(/\s+/g, " ").trim();
  //: The glyph itself, when it was text rather than a marker span.
  if (glyph && !marks.length) text = text.replace(/^(?:[·•▪◦‣§Ø]|o)\s+/, "");
  return text ? `${"  ".repeat(Math.max(0, level - 1))}${number ? `${number}.` : "-"} ${text}` : "";
}

function docHtmlToMarkdown(html) {
  //: `style` renamed before parsing: the page's CSP refuses an inline style
  //: even in a parsed, inert document (a console error per attribute, and
  //: the value never reaches `el.style`), and the two it matters for are
  //: read from the text below.
  //: A `<style>` block goes too (Word opens every copy with one): an inline style element is refused
  //: by the CSP the same way, and its rules would style nothing in an inert document anyway (L890).
  const source = String(html || "").replace(/<style[\s\S]*?<\/style\s*>/gi, "").replace(/(<[^>]*?\s)style\s*=/gi, "$1data-mm-style=");
  const doc = new DOMParser().parseFromString(source, "text/html");
  const safeUrl = (url) => {
    const value = String(url || "").trim();
    const ok = /^(https?:|mailto:)/i.test(value) || (value.startsWith("/") && !value.startsWith("//"));
    //: Encoded: a ")" ended the Markdown link early (audit 1028 D16).
    return ok ? value.replace(/[\s()<>]/g, (c) => encodeURIComponent(c)) : "";
  };
  //: Google Docs wraps a whole copy in `<b style="font-weight:normal">`, and
  //: marks real bold and italic on spans by style rather than by tag.
  const styleOf = (el, prop) => {
    const m = new RegExp(`(?:^|;)\\s*${prop}\\s*:\\s*([^;]+)`, "i").exec(el.getAttribute("data-mm-style") || "");
    return m ? m[1].trim().toLowerCase() : "";
  };
  const isBold = (el) => {
    const tag = el.nodeName;
    const weight = styleOf(el, "font-weight");
    if (tag === "STRONG" || tag === "B") return !/^(normal|[1-5]00)$/.test(weight);
    return /^(bold|bolder|[6-9]00)$/.test(weight);
  };
  const isItalic = (el) => el.nodeName === "EM" || el.nodeName === "I" || styleOf(el, "font-style") === "italic";
  const inline = (node) => {
    if (node.nodeType === 3) return node.nodeValue.replace(/\s+/g, " ");
    if (node.nodeType !== 1) return "";
    const tag = node.nodeName;
    if (/^(SCRIPT|STYLE|META|TITLE|HEAD|TEMPLATE)$/.test(tag)) return "";
    if (tag === "BR") return "\n";
    if (tag === "IMG") {
      const src = safeUrl(node.getAttribute("src"));
      return src ? `![${(node.getAttribute("alt") || "").replace(/[[\]|]/g, "")}](${src})` : "";
    }
    let text = [...node.childNodes].map(inline).join("");
    if (tag === "CODE") return text.trim() ? `\`${text.replace(/`/g, "")}\`` : "";
    const wrap = (mark) => {
      const lead = text.match(/^\s*/)[0];
      const tail = text.match(/\s*$/)[0];
      const core = text.trim();
      return core ? `${lead}${mark}${core}${mark}${tail}` : text;
    };
    if (isBold(node)) text = wrap("**");
    if (isItalic(node)) text = wrap("*");
    if (tag === "DEL" || tag === "S" || tag === "STRIKE") text = wrap("~~");
    if (tag === "A") {
      const href = safeUrl(node.getAttribute("href"));
      const label = text.trim();
      if (href && label) return `[${label.replace(/[[\]]/g, "")}](${href})`;
    }
    return text;
  };
  const out = [];
  const para = (text) => {
    const clean = text.replace(/[ \t]+\n/g, "\n").replace(/\n[ \t]+/g, "\n").trim();
    if (clean) out.push(clean);
  };
  const BLOCK = /^(P|DIV|H[1-6]|UL|OL|LI|BLOCKQUOTE|PRE|TABLE|SECTION|ARTICLE|HEADER|FOOTER|MAIN|ASIDE|FIGURE|FIGCAPTION|HR|DL|DT|DD|BODY|HTML)$/;
  const list = (el, depth) => {
    let n = 0;
    for (const li of el.children) {
      if (li.nodeName !== "LI") continue;
      n += 1;
      const marker = el.nodeName === "OL" ? `${n}.` : "-";
      const own = [...li.childNodes].filter((c) => !(c.nodeType === 1 && /^(UL|OL)$/.test(c.nodeName)));
      const text = own.map(inline).join("").replace(/\s+/g, " ").trim();
      out.push(`${"  ".repeat(depth)}${marker} ${text}`);
      for (const sub of li.children) if (/^(UL|OL)$/.test(sub.nodeName)) list(sub, depth + 1);
    }
  };
  let wordRun = -1;
  const block = (el) => {
    let run = "";
    const flush = () => {
      para(run);
      run = "";
    };
    for (const child of el.childNodes) {
      const tag = child.nodeType === 1 ? child.nodeName : "";
      //: An inline wrapper round whole blocks (Google Docs' outer `<b>`) is
      //: walked as a container, or its paragraphs and lists would run together.
      if (tag && !BLOCK.test(tag) && child.querySelector("p, div, h1, h2, h3, h4, h5, h6, ul, ol, blockquote, pre, table")) {
        flush();
        block(child);
        continue;
      }
      if (!tag || !BLOCK.test(tag)) {
        run += inline(child);
        continue;
      }
      flush();
      const wordItem = tag === "P" ? docWordListLine(child, styleOf, inline) : "";
      const heading = /^H([1-6])$/.exec(tag);
      if (wordItem) {
        //: Word's list paragraphs run together as one tight list.
        //: `wordRun >= 0`: with nothing before it both sides were -1, and a list at the very start of a paste was appended to `out[-1]`, a property, and lost (DX32).
        if (wordRun >= 0 && wordRun === out.length - 1) out[wordRun] += `\n${wordItem}`;
        else {
          out.push(wordItem);
          wordRun = out.length - 1;
        }
      } else if (heading) {
        const text = inline(child).replace(/\s+/g, " ").trim();
        if (text) out.push(`${"#".repeat(Number(heading[1]))} ${text}`);
      } else if (tag === "UL" || tag === "OL") {
        const start = out.length;
        list(child, 0);
        //: A list is one block: its items are joined without blank lines.
        out.splice(start, out.length - start, out.slice(start).join("\n"));
      } else if (tag === "BLOCKQUOTE") {
        const inner = docHtmlToMarkdown(child.innerHTML);
        if (inner) out.push(inner.split("\n").map((line) => `> ${line}`.trimEnd()).join("\n"));
      } else if (tag === "PRE") {
        const code = child.textContent.replace(/\n$/, "");
        //: A block's language, when the page names it (`language-js` on the
        //: pre or its code, as GitHub and a Word import write it).
        const inner = child.querySelector("code");
        const lang = (/(?:^|\s)language-([\w+#-]+)/.exec(`${child.className} ${inner?.className || ""}`) || [])[1] || "";
        out.push("```" + lang + "\n" + code + "\n```");
      } else if (tag === "TABLE") {
        const grid = [...child.querySelectorAll("tr")].map((tr) =>
          [...tr.children].map((cell) => inline(cell).replace(/\s+/g, " ").replace(/\|/g, "\\|").trim())
        ).filter((row) => row.length);
        if (grid.length) out.push(docTableFromGrid(grid));
      } else if (tag === "HR") {
        out.push("---");
      } else {
        block(child);
      }
    }
    flush();
  };
  block(doc.body);
  return out.join("\n\n").replace(/\n{3,}/g, "\n\n").trim();
}

//: The paste handler: after the table's own (which keeps a grid pasted into
//: a table's cells), before CodeMirror's plain-text default.
function docRichPasteEvent(event, view) {
  const plain = docPastePlain;
  docPastePlain = false;
  if (plain || view.dom.classList.contains("doc-content-code")) return false;
  const html = event.clipboardData?.getData("text/html") || "";
  if (!html || !docHtmlIsRich(html)) return false;
  const markdown = docHtmlToMarkdown(html);
  if (!markdown) return false;
  event.preventDefault();
  const sel = view.state.selection.main;
  const doc = view.state.doc;
  //: Padded to start (and end) its own line when it is a block (DX3).
  const insert = docRichPasteEvent.fit(markdown, doc.lineAt(sel.from).text.slice(0, sel.from - doc.lineAt(sel.from).from), doc.lineAt(sel.to).text.slice(sel.to - doc.lineAt(sel.to).from));
  docUndoBreak();
  view.dispatch({
    changes: { from: sel.from, to: sel.to, insert },
    selection: { anchor: sel.from + insert.length },
    userEvent: "input.paste",
    scrollIntoView: true,
  });
  docPasteOfferRich(view, sel.from, insert, event.clipboardData.getData("text/plain"));
  return true;
}

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

//: The whole table, for the one command that is not an edit inside it. The
//: newline after it goes too, or deleting a table leaves the blank line it was
//: separated from the next paragraph by.
function docTableRemoveEdits(context) {
  const { table, text } = context;
  let to = table.to;
  if (text[to] === "\n") to += 1;
  return [{ from: table.from, to, insert: "" }];
}

//: Select a row, a column (one range per cell, so Delete clears them and
//: copy reads them) or the table. A textarea has one range only: the first
//: to the last.
function docTableSelect(context, kind) {
  const index = kind === "row" ? context.cell.row : kind === "column" ? context.cell.col : 0;
  const ranges = docTableSelectRanges(context.table, kind, index);
  if (!ranges.length) return false;
  const view = context.surface.view;
  const CM = window.CM6;
  if (view && CM) {
    const { EditorSelection } = CM.state;
    view.dispatch({
      selection: EditorSelection.create(ranges.map((range) => EditorSelection.range(range.from, range.to))),
      scrollIntoView: true,
    });
  } else {
    context.surface.setSelectionRange(ranges[0].from, ranges[ranges.length - 1].to);
  }
  return true;
}

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

//: The commands, as data, because three things read them: the cell menu, the
//: "/" menu's table entry and the tests. `run` takes the live context rather
//: than closing over one, so a menu built for the cell you opened it on still
//: acts on the cell you are in when you choose an item.
const DOC_TABLE_COMMANDS = [
  {
    id: "row-above",
    group: "rows",
    label: "Insert row above",
    title: "Add an empty row above this one",
    run: (context) =>
      docTableGo(context, docTableAddRowEdits(context.table, context.cell.row - 1),
        Math.max(context.cell.row, context.table.delim + 1), 0),
  },
  {
    id: "row-below",
    group: "rows",
    label: "Insert row below",
    title: "Add an empty row below this one",
    run: (context) =>
      docTableGo(context, docTableAddRowEdits(context.table, context.cell.row),
        Math.max(context.cell.row, context.table.delim) + 1, 0),
  },
  {
    id: "row-delete",
    group: "rows",
    label: "Delete row",
    title: "Remove this row",
    danger: true,
    //: The header and the delimiter are the table's shape rather than its
    //: contents: deleting either is "delete table", which is its own command.
    enabled: (context) => context.cell.row > context.table.delim,
    run: (context) =>
      docTableGo(context, docTableRemoveRowEdits(context.table, context.cell.row),
        Math.min(context.cell.row, context.table.rows.length - 2), context.cell.col),
  },
  {
    id: "col-left",
    group: "columns",
    label: "Insert column left",
    title: "Add a column before this one",
    run: (context) =>
      docTableGo(context, docTableAddColumnEdits(context.table, context.cell.col, true),
        context.cell.row, context.cell.col),
  },
  {
    id: "col-right",
    group: "columns",
    label: "Insert column right",
    title: "Add a column after this one",
    run: (context) =>
      docTableGo(context, docTableAddColumnEdits(context.table, context.cell.col),
        context.cell.row, context.cell.col + 1),
  },
  {
    id: "col-delete",
    group: "columns",
    label: "Delete column",
    title: "Remove this column",
    danger: true,
    enabled: (context) => context.table.columns > 1,
    run: (context) =>
      docTableGo(context, docTableRemoveColumnEdits(context.table, context.cell.col),
        context.cell.row, Math.max(0, context.cell.col - 1)),
  },
  {
    id: "row-up",
    group: "arrange",
    label: "Move row up",
    title: "Swap this row with the one above",
    enabled: (context) => context.cell.row > context.table.delim + 1,
    run: (context) =>
      docTableGo(context, docTableMoveRowEdits(context.table, context.cell.row, -1),
        context.cell.row - 1, context.cell.col),
  },
  {
    id: "row-down",
    group: "arrange",
    label: "Move row down",
    title: "Swap this row with the one below",
    enabled: (context) =>
      context.cell.row > context.table.delim && context.cell.row < context.table.rows.length - 1,
    run: (context) =>
      docTableGo(context, docTableMoveRowEdits(context.table, context.cell.row, 1),
        context.cell.row + 1, context.cell.col),
  },
  {
    id: "col-move-left",
    group: "arrange",
    label: "Move column left",
    title: "Swap this column with the one before it",
    enabled: (context) => context.cell.col > 0,
    run: (context) =>
      docTableGo(context, docTableMoveColumnEdits(context.table, context.cell.col, -1),
        context.cell.row, context.cell.col - 1),
  },
  {
    id: "col-move-right",
    group: "arrange",
    label: "Move column right",
    title: "Swap this column with the one after it",
    enabled: (context) => context.cell.col < context.table.columns - 1,
    run: (context) =>
      docTableGo(context, docTableMoveColumnEdits(context.table, context.cell.col, 1),
        context.cell.row, context.cell.col + 1),
  },
  {
    id: "sort-up",
    group: "arrange",
    label: "Sort A to Z",
    title: "Order the rows by this column, numbers as numbers",
    enabled: (context) => context.table.rows.length > context.table.delim + 2,
    run: (context) =>
      docTableGo(context, docTableSortEdits(context.table, context.cell.col, false),
        context.cell.row, context.cell.col),
  },
  {
    id: "sort-down",
    group: "arrange",
    label: "Sort Z to A",
    title: "Order the rows by this column, the other way",
    enabled: (context) => context.table.rows.length > context.table.delim + 2,
    run: (context) =>
      docTableGo(context, docTableSortEdits(context.table, context.cell.col, true),
        context.cell.row, context.cell.col),
  },
  {
    id: "filter",
    group: "filter",
    label: "Filter rows…",
    title: "Show only the rows whose cell in this column holds some text. The markdown keeps every row",
    enabled: (context) => !!context.surface.view && context.table.rows.length > context.table.delim + 1,
    run: (context) => {
      docViewState.tableFilter.ask(context);
      return true;
    },
  },
  {
    id: "filter-clear",
    group: "filter",
    label: "Show all rows",
    title: "Remove this table's filter",
    enabled: (context) => !!docViewState.tableFilter.of(context.table),
    run: (context) => {
      docViewState.tableFilter.set(context.surface.view, context.table, null);
      return true;
    },
  },
  ...[["sum", "Sum", "SUM"], ["avg", "Average", "AVG"], ["count", "Count", "COUNT"]].map(([id, word, fn]) => ({
    id: `formula-${id}`,
    group: "formula",
    label: `${word} of this column`,
    title: `Write =${fn}(column) in this cell: it shows the ${word.toLowerCase()} of the numbers in the column`,
    enabled: (context) => context.cell.row > context.table.delim,
    run: (context) =>
      docTableGo(context, docTableSetCellEdits(context.table, [{ row: context.cell.row, col: context.cell.col,
        text: `=${fn}(${docViewState.tableFilter.letters(context.cell.col)})` }]), context.cell.row, context.cell.col),
  })),
  {
    id: "select-row",
    group: "select",
    label: "Select row",
    title: "Select every cell of this row",
    enabled: (context) => context.cell.row !== context.table.delim,
    run: (context) => docTableSelect(context, "row"),
  },
  {
    id: "select-column",
    group: "select",
    label: "Select column",
    title: "Select this column's cells, to copy or clear them",
    run: (context) => docTableSelect(context, "column"),
  },
  {
    id: "select-table",
    group: "select",
    label: "Select table",
    title: "Select the whole table",
    run: (context) => docTableSelect(context, "table"),
  },
  {
    id: "align-left",
    group: "alignment",
    label: "Align left",
    title: "Align this column to the left",
    run: (context) => docTableGo(context, docTableAlignEdits(context.table, context.cell.col, "left"),
      context.cell.row, context.cell.col),
  },
  {
    id: "align-centre",
    group: "alignment",
    label: "Align centre",
    title: "Centre this column",
    run: (context) => docTableGo(context, docTableAlignEdits(context.table, context.cell.col, "center"),
      context.cell.row, context.cell.col),
  },
  {
    id: "align-right",
    group: "alignment",
    label: "Align right",
    title: "Align this column to the right",
    run: (context) => docTableGo(context, docTableAlignEdits(context.table, context.cell.col, "right"),
      context.cell.row, context.cell.col),
  },
  {
    id: "table-delete",
    group: "table",
    label: "Delete table",
    title: "Remove the whole table",
    danger: true,
    run: (context) => {
      docTableDispatch(context, docTableRemoveEdits(context));
      return true;
    },
  },
];

//: Named so the "/" menu, a shortcut or a test can run one without going
//: through the menu's DOM.
function docTableCommand(id) {
  const command = DOC_TABLE_COMMANDS.find((item) => item.id === id);
  const context = docTableContext();
  if (!command || !context) return false;
  if (command.enabled && !command.enabled(context)) return false;
  const done = command.run(context);
  context.surface.focus();
  return done !== false;
}

//: The cell menu, built from the app's own ⋯ recipe (`kebabMenu`) rather than
//: from scratch: DESIGN.md's index says a menu is `kebabMenu`, and a
//: hand-built one here would be the eleventh thing in this app that opens a
//: list of actions and the first that does it differently.
function docTableMenuItems(context) {
  return DOC_TABLE_COMMANDS.map((command) => ({
    label: command.label,
    title: command.title,
    danger: command.danger,
    //: Rows, columns, alignment, the table itself. Ten rows read as one list
    //: of ten before this, and finding "Align centre" in it meant knowing the
    //: order. `kebabMenu` draws a hairline wherever this name changes
    //: (DOCUMENTS_PLAN section 16).
    group: command.group,
    disabled: command.enabled ? !command.enabled(context) : false,
    run: () => docTableCommand(command.id),
  }));
}

function docTableMenu(context) {
  if (typeof kebabMenu !== "function") return document.createElement("span");
  const wrap = kebabMenu(docTableMenuItems(context), "Table row and column actions");
  //: **Pressing it must not move the caret out of the table** (the owner: the
  //: kebab "does nothing and just deselects the row when I try to press that
  //: meatball button"). The menu only exists while the selection is inside the
  //: table: the decoration that draws it is rebuilt from the selection, so the
  //: moment a pointer-down moves the caret out of the header row, the widget
  //: is unmounted, taking the menu that was opening with it. Measured: after a
  //: press, the widget was gone.
  //:
  //: `mousedown` is where the caret moves, so that is where it is refused. The
  //: click still lands and the menu still opens, and every command below then
  //: runs against a selection that is still where the person left it, which is
  //: also what makes "Insert row above" mean a row.
  wrap.addEventListener("mousedown", (event) => event.preventDefault());
  return wrap;
}

//: **Grips on a Live table's edges** (INBOX 904 B23: "lines on the edges and
//: rows and columns on the outside etc to select whole rows or columns, or to
//: add new rows or columns or even dragging icons to drag and rearrange
//: columns and rows"). While the caret is in a table: a bar above each column
//: and one beside each row (a click selects it, a drag moves it, a right-click
//: or a hold opens the table's menu there), and a plus at the end of the
//: header (a column) and under the last row (a row). Every drag has the menu's
//: Move row and Move column as its keyboard and touch alternative (WCAG 2.5.7).
//:
//: A layer inside the editor's scroller, so it scrolls with the text; the
//: geometry is read from the rendered cells (`requestMeasure`), never guessed
//: from the grid's template. Rebuilt only when that geometry changes, and never
//: mid-press, because a press that loses its element loses its release.
const DOC_GRIP_DRAG_PX = 4;

function docTableGripsPlugin(CM) {
  if (docViewState.tableGrips) return docViewState.tableGrips;
  const { ViewPlugin } = CM.view;
  docViewState.tableGrips = ViewPlugin.fromClass(
    class {
      constructor(view) {
        this.view = view;
        this.geo = null;
        this.sig = "";
        this.press = null;
        this.layer = document.createElement("div");
        this.layer.className = "doc-table-grips";
        this.line = document.createElement("div");
        this.line.className = "doc-table-grip-line hidden";
        view.scrollDOM.appendChild(this.layer);
        this.measure = {
          key: this,
          read: (v) => this.read(v),
          write: (geo) => this.write(geo),
        };
        for (const type of ["pointerdown", "pointermove", "pointerup", "pointercancel"]) {
          this.layer.addEventListener(type, (event) => this[type](event));
        }
        view.requestMeasure(this.measure);
      }
      update(update) {
        //: The loop's own flags go through one request per frame, outside the loop.
        if (update.docChanged || update.selectionSet || update.focusChanged) update.view.requestMeasure(this.measure);
        else if (update.viewportChanged || update.geometryChanged || update.heightChanged) {
          docMeasureNextFrame(this, update.view, this.measure);
        }
      }
      destroy() {
        this.measureDead = true;
        this.layer.remove();
      }

      read(view) {
        const doc = view.state.doc;
        const head = view.state.selection.main.head;
        //: Cheap exit for the common case: a caret on a line with no pipe is not
        //: in a table, and reading the document to say so on every keystroke of a
        //: long page would be the cost of a feature most lines never use.
        if (!doc.lineAt(head).text.includes("|") && !doc.lineAt(view.state.selection.main.anchor).text.includes("|")) return null;
        const table = docTableParse.at(doc, head);
        if (!table) return null;
        const scroller = view.scrollDOM;
        const sr = scroller.getBoundingClientRect();
        const rect = (el) => {
          const b = el.getBoundingClientRect();
          return {
            x: Math.round(b.left - sr.left - scroller.clientLeft + scroller.scrollLeft),
            y: Math.round(b.top - sr.top - scroller.clientTop + scroller.scrollTop),
            w: Math.round(b.width),
            h: Math.round(b.height),
          };
        };
        const rows = [];
        let cols = [];
        for (const el of view.contentDOM.querySelectorAll(".cm-line.cm-md-table")) {
          const pos = view.posAtDOM(el);
          const index = table.rows.findIndex((row) => pos >= row.from && pos <= row.to);
          if (index < 0) continue;
          rows.push({ row: index, ...rect(el) });
          if (index === 0) cols = [...el.querySelectorAll(".cm-md-td")].map((cell, col) => ({ col, ...rect(cell) }));
        }
        if (!rows.length || !cols.length) return null;
        rows.sort((a, b) => a.row - b.row);
        const left = Math.min(...rows.map((r) => r.x));
        const right = Math.max(...rows.map((r) => r.x + r.w));
        const last = rows[rows.length - 1];
        return {
          from: table.from,
          delim: table.delim,
          columns: table.columns,
          rows,
          cols,
          box: { left, top: rows[0].y, right, bottom: last.y + last.h },
          limit: scroller.clientWidth + scroller.scrollLeft,
        };
      }

      write(geo) {
        const signature = geo ? JSON.stringify([geo.from, geo.rows, geo.cols, geo.limit]) : "";
        if (this.press && this.press.drag) return;
        if (signature === this.sig) return;
        this.sig = signature;
        this.geo = geo;
        this.layer.replaceChildren();
        if (!geo) return;
        const put = (cls, kind, index, box, label) => {
          const el = document.createElement("div");
          el.className = cls;
          el.dataset.kind = kind;
          el.dataset.index = String(index);
          el.title = label;
          el.setAttribute("aria-hidden", "true");
          el.style.left = `${box.x}px`;
          el.style.top = `${box.y}px`;
          el.style.width = `${box.w}px`;
          el.style.height = `${box.h}px`;
          this.layer.appendChild(el);
          return el;
        };
        //: The hit areas are as high and as wide as the band the table's own
        //: spacing leaves (16px above the header, what the content's left
        //: padding allows beside the rows); the visible bar is drawn inside
        //: them by the stylesheet.
        const band = 16;
        const side = Math.max(8, Math.min(band, geo.box.left));
        const lastCol = geo.cols[geo.cols.length - 1];
        geo.cols.forEach((c) => {
          const shorten = c === lastCol ? band + 2 : 0;
          put("doc-table-grip doc-table-grip-col", "col", c.col, { x: c.x, y: geo.box.top - band, w: Math.max(8, c.w - shorten), h: band },
            `Column ${c.col + 1}: click to select, drag to move, right-click for more`);
        });
        geo.rows.forEach((r) => {
          put("doc-table-grip doc-table-grip-row", "row", r.row, { x: geo.box.left - side, y: r.y, w: side, h: r.h },
            `${r.row === 0 ? "Header row" : `Row ${r.row - geo.delim}`}: click to select, drag to move, right-click for more`);
        });
        const addCol = put("doc-table-add doc-table-add-col", "add-col", 0,
          { x: lastCol.x + lastCol.w - band, y: geo.box.top - band, w: band, h: band }, "Add a column at the end");
        const addRow = put("doc-table-add doc-table-add-row", "add-row", 0,
          { x: geo.box.left, y: geo.box.bottom, w: band, h: band }, "Add a row at the end");
        this.layer.appendChild(this.line);
      }

      pointerdown(event) {
        const grip = event.target instanceof Element ? event.target.closest(".doc-table-grip, .doc-table-add") : null;
        if (!grip || event.button !== 0 || !this.geo) return;
        //: Not a text press: the caret stays in the table, and the editor keeps
        //: its focus, which is what the commands read.
        event.preventDefault();
        this.press = { el: grip, kind: grip.dataset.kind, index: Number(grip.dataset.index), x: event.clientX, y: event.clientY, id: event.pointerId, drag: false, target: null };
        try {
          grip.setPointerCapture(event.pointerId);
        } catch {
          /* a pointer that is already gone: the release will not come, and the press is dropped below */
        }
      }

      pointermove(event) {
        const press = this.press;
        if (!press || event.pointerId !== press.id) return;
        //: The header is the table's shape, not a row that moves.
        const movable = press.kind === "col" || (press.kind === "row" && press.index > this.geo.delim);
        if (!press.drag && movable && Math.hypot(event.clientX - press.x, event.clientY - press.y) >= DOC_GRIP_DRAG_PX) {
          press.drag = true;
          this.layer.classList.add("is-dragging");
          press.el.classList.add("is-source");
        }
        if (!press.drag) return;
        const scroller = this.view.scrollDOM;
        const sr = scroller.getBoundingClientRect();
        const px = event.clientX - sr.left - scroller.clientLeft + scroller.scrollLeft;
        const py = event.clientY - sr.top - scroller.clientTop + scroller.scrollTop;
        const geo = this.geo;
        const line = this.line;
        line.classList.remove("hidden");
        if (press.kind === "col") {
          const slot = geo.cols.filter((c) => c.x + c.w / 2 < px).length;
          press.target = slot > press.index ? slot - 1 : slot;
          const edge = slot < geo.cols.length ? geo.cols[slot].x : geo.cols[geo.cols.length - 1].x + geo.cols[geo.cols.length - 1].w;
          line.className = "doc-table-grip-line doc-table-grip-line-col";
          line.style.left = `${edge}px`;
          line.style.top = `${geo.box.top}px`;
          line.style.height = `${geo.box.bottom - geo.box.top}px`;
          line.style.width = "";
        } else {
          const body = geo.rows.filter((r) => r.row > geo.delim);
          const slot = body.filter((r) => r.y + r.h / 2 < py).length;
          const slotRow = geo.delim + 1 + slot;
          press.target = slotRow > press.index ? slotRow - 1 : slotRow;
          const edge = slot < body.length ? body[slot].y : body[body.length - 1].y + body[body.length - 1].h;
          line.className = "doc-table-grip-line doc-table-grip-line-row";
          line.style.top = `${edge}px`;
          line.style.left = `${geo.box.left}px`;
          line.style.width = `${geo.box.right - geo.box.left}px`;
          line.style.height = "";
        }
      }

      pointerup(event) {
        const press = this.press;
        if (!press || event.pointerId !== press.id) return;
        this.finish();
        if (press.drag) {
          if (press.target != null && press.target !== press.index) this.commitMove(press);
          else this.view.requestMeasure(this.measure);
          return;
        }
        const grip = document.elementFromPoint(event.clientX, event.clientY);
        //: A release off the grip it began on is a cancelled press, as it is on
        //: every button.
        if (!(grip instanceof Element) || grip.closest(".doc-table-grip, .doc-table-add") !== press.el) return;
        this.click(press);
      }

      pointercancel() {
        if (this.press) this.finish();
        this.view.requestMeasure(this.measure);
      }

      finish() {
        const press = this.press;
        this.press = null;
        this.layer.classList.remove("is-dragging");
        this.line.classList.add("hidden");
        if (press && press.el) {
          press.el.classList.remove("is-source");
          try {
            press.el.releasePointerCapture(press.id);
          } catch {
            /* released already */
          }
        }
      }

      //: The live table the grips were drawn for, or null if the document moved
      //: under them.
      context() {
        const surface = asSurface(this.view.contentDOM) || docSurface();
        const context = surface && docTableContext(surface);
        return context && this.geo && context.table.from === this.geo.from ? context : null;
      }

      click(press) {
        const context = this.context();
        if (!context) return;
        const table = context.table;
        if (press.kind === "col" || press.kind === "row") {
          context.cell = press.kind === "row" ? { row: press.index, col: context.cell.col } : { row: context.cell.row, col: press.index };
          docTableSelect(context, press.kind === "col" ? "column" : "row");
        } else if (press.kind === "add-col") {
          context.cell = { row: context.cell.row === table.delim ? 0 : context.cell.row, col: table.columns - 1 };
          docTableCommandRun("col-right", context);
        } else if (press.kind === "add-row") {
          context.cell = { row: table.rows.length - 1, col: context.cell.col };
          docTableCommandRun("row-below", context);
        }
        this.view.focus();
      }

      commitMove(press) {
        const context = this.context();
        if (!context) return;
        const delta = press.target - press.index;
        const edits = press.kind === "col"
          ? docTableMoveColumnEdits(context.table, press.index, delta)
          : docTableMoveRowEdits(context.table, press.index, delta);
        docTableDispatch(context, edits);
        //: The moved row or column stays selected, so the person sees where it
        //: went and the next press acts on it.
        const table = docTableParse(context.surface.text, context.table.from);
        if (table) {
          const cell = press.kind === "col" ? { row: 0, col: press.target } : { row: press.target, col: 0 };
          docTableSelect({ surface: context.surface, table, cell }, press.kind === "col" ? "column" : "row");
        }
        this.view.focus();
      }
    }
  );
  return docViewState.tableGrips;
}

//: One command, by id, against a context the caller already holds. The named
//: `docTableCommand` reads the caret itself; a grip has just moved it.
function docTableCommandRun(id, context) {
  const command = DOC_TABLE_COMMANDS.find((item) => item.id === id);
  if (!command || (command.enabled && !command.enabled(context))) return false;
  return command.run(context) !== false;
}


// Frontmatter and the properties panel: documents-props.js (DC13 remainder).

// =============================================================================
// Block references (DOCUMENTS_PLAN Phase 4 item 2)
// =============================================================================
//
// A paragraph you can link to and embed, from a note, a map node or a chat.
//
// **The syntax is Obsidian's**, and the reason is the reason the columns fence
// is Pandoc's: a document written here should still say the same thing
// somewhere else. A block carries `^an-id` at the end of its last line; a link
// to it is `[[Document title#^an-id]]` and an embed of it is the same with a
// leading `!`, which is the form the embeds built in Phase 3 already parse the
// left half of.
//
// **The id is generated, never asked for.** Obsidian asks the same way: you
// copy a link to a block and the id appears in the text. A person naming
// their own ids is a person maintaining them, and the one thing a block
// reference must survive is the paragraph being rewritten around it.
//
// Everything between the markers below is pure string work with no DOM and no
// app globals in it, so `tests/test_doc_blockrefs.py` runs it in node. That is
// a property the tests enforce by existing, the same way the table and
// frontmatter models are tested.

// DOC-BLOCKREF-BEGIN

//: What an id may be. Deliberately narrower than Obsidian's (which allows any
//: non-space run): an id is generated here, so the only reason to accept more
//: is to read somebody else's file, and a `^` followed by punctuation is far
//: more likely to be a caret in prose ("2^31", "x ^ y") than a block id.
const DOC_BLOCK_ID = "[A-Za-z0-9][A-Za-z0-9-]{0,31}";
//: The trailing `^id` on a line, with the space before it, so removing the id
//: does not leave a space behind.
const DOC_BLOCK_ID_AT_END = new RegExp(`(?:^|[ \\t])\\^(${DOC_BLOCK_ID})[ \\t]*$`);
//: A list item's own bullet. A block id on a list belongs to the item, not to
//: the whole list, which is the one place "the block" is a single line.
const DOC_BLOCK_LIST_LINE = /^\s*(?:[-*+]|\d{1,9}[.)])\s+/;

//: `Document title#^an-id` split into its halves. Returns `blockId: null` for
//: a plain name, so every caller can use this and none has to know whether a
//: link happens to carry one.
function docBlockRefSplit(spec) {
  const text = String(spec == null ? "" : spec);
  const hash = text.indexOf("#^");
  if (hash === -1) return { name: text.trim(), blockId: null };
  const id = text.slice(hash + 2).trim();
  return {
    name: text.slice(0, hash).trim(),
    blockId: new RegExp(`^${DOC_BLOCK_ID}$`).test(id) ? id : null,
  };
}

//: Is this position inside a fenced code block? A `^id` written in one is an
//: example of the syntax rather than a use of it, and a block id may not be
//: put there at all: the text inside a fence is code, and appending to it
//: changes what the code says.
function docBlockInFence(lines, index) {
  let open = false;
  for (let i = 0; i < index; i++) {
    if (/^\s*(?:```|~~~)/.test(lines[i])) open = !open;
  }
  return open;
}

//: The block a position is in: `{from, to, lastFrom, lastTo}` over the text,
//: or null when there is no block there (a blank line, or inside a fence).
//:
//: A block is the run of non-blank lines around the position, except in a
//: list, where it is the item's own line. Both are what Obsidian does and
//: both are what a person means by "this paragraph".
function docBlockBounds(text, pos) {
  const body = String(text == null ? "" : text);
  const lines = body.split("\n");
  const starts = [];
  let at = 0;
  for (const line of lines) {
    starts.push(at);
    at += line.length + 1;
  }
  const clamped = Math.max(0, Math.min(body.length, pos | 0));
  let index = 0;
  while (index + 1 < lines.length && starts[index + 1] <= clamped) index++;
  if (!lines[index].trim()) return null;
  if (docBlockInFence(lines, index)) return null;
  let first = index;
  let last = index;
  if (!DOC_BLOCK_LIST_LINE.test(lines[index])) {
    while (first > 0 && lines[first - 1].trim() && !DOC_BLOCK_LIST_LINE.test(lines[first - 1])) {
      first--;
    }
    while (
      last + 1 < lines.length &&
      lines[last + 1].trim() &&
      !DOC_BLOCK_LIST_LINE.test(lines[last + 1])
    ) {
      last++;
    }
  }
  return {
    from: starts[first],
    to: starts[last] + lines[last].length,
    lastFrom: starts[last],
    lastTo: starts[last] + lines[last].length,
  };
}

//: The id a block already carries, as `{id, from, to}` over the text, or null.
//: The span includes the space before the `^`, so it round-trips: removing it
//: gives back exactly the line that was there before the id was added.
function docBlockIdOf(text, bounds) {
  if (!bounds) return null;
  const line = String(text).slice(bounds.lastFrom, bounds.lastTo);
  const match = DOC_BLOCK_ID_AT_END.exec(line);
  if (!match) return null;
  return {
    id: match[1],
    from: bounds.lastFrom + match.index,
    to: bounds.lastFrom + match.index + match[0].length,
  };
}

//: Every id already in a document, so a new one cannot collide with one.
function docBlockIds(text) {
  const found = new Set();
  for (const line of String(text == null ? "" : text).split("\n")) {
    const match = DOC_BLOCK_ID_AT_END.exec(line);
    if (match) found.add(match[1]);
  }
  return found;
}

//: A new id for this document. Six characters of base 36, which is 2.2 billion
//: of them: short enough to read in the text it is appended to, and the
//: collision check below makes the birthday problem somebody else's.
//:
//: `random` is a parameter so the test can make this total rather than
//: probabilistic; nothing in the app passes it.
function docBlockNewId(text, random) {
  const roll = typeof random === "function" ? random : Math.random;
  const taken = docBlockIds(text);
  for (let attempt = 0; attempt < 50; attempt++) {
    const id = Math.floor(roll() * 36 ** 6)
      .toString(36)
      .padStart(6, "0")
      .slice(-6);
    if (!taken.has(id)) return id;
  }
  return null;
}

//: The edits that give the block at `pos` an id, and the id itself. A block
//: that already has one is not touched: the whole point of an id is that a
//: link written yesterday still resolves.
//:
//: One `{from, to, insert}` over the end of the block's last line, which is
//: the same shape the table and frontmatter models write, and for the same
//: reason: it keeps every other byte of the document exactly as it was.
function docBlockEnsureIdEdits(text, pos, random) {
  const bounds = docBlockBounds(text, pos);
  if (!bounds) return { id: null, edits: [], reason: "no-block" };
  const existing = docBlockIdOf(text, bounds);
  if (existing) return { id: existing.id, edits: [], reason: "already" };
  const id = docBlockNewId(text, random);
  if (!id) return { id: null, edits: [], reason: "no-id" };
  const line = String(text).slice(bounds.lastFrom, bounds.lastTo);
  //: Trailing spaces are not kept in front of the id: two of them at the end
  //: of a markdown line are a hard line break, and `  ^id` would move it.
  const trimmed = line.replace(/[ \t]+$/, "");
  return {
    id,
    edits: [
      {
        from: bounds.lastFrom + trimmed.length,
        to: bounds.lastTo,
        insert: ` ^${id}`,
      },
    ],
    reason: "added",
  };
}

//: The block carrying an id: `{from, to, text}` over the document, with the
//: `^id` itself left out of the text (it is scaffolding, not content).
//: Returns null when nothing carries it, which is what a link to a block
//: somebody deleted looks like.
function docBlockFind(text, id) {
  const body = String(text == null ? "" : text);
  if (!new RegExp(`^${DOC_BLOCK_ID}$`).test(String(id || ""))) return null;
  const lines = body.split("\n");
  let at = 0;
  for (let index = 0; index < lines.length; index++) {
    const match = DOC_BLOCK_ID_AT_END.exec(lines[index]);
    if (match && match[1] === id && !docBlockInFence(lines, index)) {
      const bounds = docBlockBounds(body, at);
      if (!bounds) return null;
      const marker = docBlockIdOf(body, bounds);
      const whole = body.slice(bounds.from, bounds.to);
      const clean = marker
        ? whole.slice(0, marker.from - bounds.from) + whole.slice(marker.to - bounds.from)
        : whole;
      return { from: bounds.from, to: bounds.to, text: clean };
    }
    at += lines[index].length + 1;
  }
  return null;
}

//: The text as a *reader* sees it: every block marker taken out. A `^id` is
//: scaffolding the same way `[[` and `]]` are, so it belongs in the source
//: pane and in the file on disk, and nowhere in the rendered pane or the PDF
//: printed from it. The Live view already hides it; this is the same rule for
//: the pane that has no caret to bring it back.
//:
//: Markers inside a fence are left alone: there a `^id` is an example of the
//: syntax rather than a use of it, and a preview that rewrites code is a
//: preview saying something the file does not.
function docBlockStripIds(text) {
  let fenced = false;
  return String(text == null ? "" : text)
    .split("\n")
    .map((line) => {
      if (/^\s*(?:```|~~~)/.test(line)) {
        fenced = !fenced;
        return line;
      }
      return fenced ? line : line.replace(DOC_BLOCK_ID_AT_END, "");
    })
    .join("\n");
}

// DOC-BLOCKREF-END

// --- block references in the running editor ----------------------------------

//: Another document's text, fetched once for the embeds that need it. A page
//: holding six embeds of one document asks for it once, and the open document
//: is never fetched at all: its text is what is being typed.
const docBlockTextCache = new Map();

function docBlockDocumentText(doc) {
  if (!doc) return null;
  if (currentDoc && doc.id === currentDoc.id) return docText();
  if (doc.content != null) return doc.content;
  return docBlockTextCache.has(doc.id) ? docBlockTextCache.get(doc.id) : null;
}

//: Copy a link to the block at the caret, and put the caret on a block a link led to: documents-blockref.js,
//: fetched on first use. Each name is a stand-in that the piece's function of the same name replaces on load.
//: `mode`: "link" copies `[[Title#^id]]`; "copy" copies the embed `![[Title#^id]]` (a synced block); "paste" inserts the last one copied.
async function docCopyBlockRef(mode = "link") {
  if (!(await lazyScript("/js/documents-blockref.js"))) return toast("The block references could not be loaded.", true, { action: ["Try again", () => docCopyBlockRef(mode)] });
  return docBlockrefPiece.docCopyBlockRef(mode);
}

async function docRevealBlock(blockId) {
  if (!(await lazyScript("/js/documents-blockref.js"))) return toast("The block references could not be loaded.", true, { action: ["Try again", () => docRevealBlock(blockId)] });
  return docBlockrefPiece.docRevealBlock(blockId);
}

//: **True only while a print is being prepared** (`exportDocumentPdf`), which
//: is the one moment the rendered pane carries the remarks rather than hiding
//: them: a PDF handed to somebody should carry them as footnotes, and Read view
//: should not, and both are drawn by `renderDocPreview` from one place. A flag
//: rather than an argument because the render is also reached from the debounce
//: and from `setDocView`, neither of which knows anything about printing.
let docPrintComments = false;




//: The compartment decision 3 names: Live is this editor with the markdown
//: decorations on, Source is the same editor with them off. Nothing else
//: differs between the two views, which is the whole point.
//: **A reconfigure that changes nothing is skipped** (DOCUMENTS 25 row 7).
//: Each one is a view update that reads the DOM selection and lays the page
//: out: measured on a 241-line file, the open spent 103ms here and 75ms in the
//: gutter's twin below re-saying what `docCmExtensions` had just built. The
//: live set is cached instances (`docLivePlugin`, the two fields), so on or
//: off is the whole of its state, as the line numbers' preference is the
//: gutter's.
function docCmPartIs(part, on) {
  const current = part.get(docCmView.state);
  return Boolean(current && current.length) === Boolean(on);
}

function docSetLiveDecorations(on) {
  const CM = window.CM6;
  if (!docCmView || !CM || !docCmParts.live) return;
  if (docCmPartIs(docCmParts.live, on)) return;
  docCmView.dispatch({
    effects: docCmParts.live.reconfigure(on ? docLiveExtensions(CM) : []),
  });
}

//: **A span's marks show while a selection is in it or touching it**
//: (INBOX 1473 b, the owner: "like obsidian where it does it per phrase,
//: word, or whatever text string is formatted when clicked inside or next
//: to"). Every range counts, not only the main one, so each cursor of a
//: multi-cursor edit and every span a selection crosses reveal. Ends are
//: inclusive: a caret just after the closing `**` is "next to" the span.
function docLiveSpanTouched(ranges, from, to) {
  for (const range of ranges) {
    if (range.from <= to && range.to >= from) return true;
  }
  return false;
}

//: Whether a new selection reveals exactly what the last build revealed.
//: `probes` is the flat `[from, to, revealed, ...]` list a build records for
//: every reveal it decided; when none flips, a caret move changes no
//: decoration and the plugin keeps the set it has.
function docLiveRevealSame(probes, ranges) {
  for (let i = 0; i < probes.length; i += 3) {
    const v = probes[i + 2];
    if ((v & 2 ? docLiveSpanTouched.anchorIn : docLiveSpanTouched)(ranges, probes[i], probes[i + 1]) !== Boolean(v & 1)) return false;
  }
  return true;
}
//: A rendered widget turns to source only while a selection starts in it (INBOX 1547): a caret
//: there, or a drag begun there; a selection that crosses it leaves it drawn, height and all.
//: A property, not a name: the shared scope is at its cap (test_global_scope_ratchet).
//: **A caret shows it only from strictly inside** (audit 1102 DX5): Up or Down lands a caret on a
//: widget's edge (it has no inside to land in), and the edge revealing it moved the page 235px at
//: `[TOC]`; Left or Right from the edge steps in. A drag begun at the edge still shows it.
docLiveSpanTouched.anchorIn = (ranges, from, to) => ranges.some((range) => range.anchor >= from && range.anchor <= to && (!range.empty || (range.anchor > from && range.anchor < to)));


//: Live is three extensions rather than one now, and all three go in the same
//: compartment, so a view switch turns them on and off together: the block
//: widget and the arrow keys that step into it belong to Live exactly as the
//: markdown decorations do.
function docLiveExtensions(CM) {
  return [docLivePlugin(CM), docTableGripsPlugin(CM), docColumnsField(CM), docColumnsArrowKeymap(CM), docMermaidField(CM), docMathRender.graphField(CM), docMathRender.baseField(CM), docMathRender.queryField(CM), docLiveExtensions.dragHandle(CM)];
}

//: **A drag handle for a Live block** (audit 1102 DX29; Notion's grip). Beside
//: the block under the pointer a grip appears in the page margin; dragging it
//: and letting go moves the whole block (a paragraph, a list item with what is
//: nested under it, a fence, a heading's section) to the drop point.
//:
//: It is the keyboard move repeated, not a second model: `docBlockMoveEdit`
//: (Alt+Up and Alt+Down) is applied to a copy of the text once per neighbour the
//: drop is past, and the difference between the copy and the document is
//: dispatched as ONE transaction, so one Undo puts the block back. The keyboard
//: path already meets WCAG 2.5.7, so the grip is `aria-hidden` and its title
//: names the keys. Pointer only: a phone has no hover (the stylesheet hides it
//: too) and a code file keeps the editor's own line move.
docLiveExtensions.dragHandle = (CM) => {
  if (docViewState.blockHandle) return docViewState.blockHandle;
  const { ViewPlugin } = CM.view;
  docViewState.blockHandle = ViewPlugin.fromClass(
    class {
      constructor(view) {
        this.view = view;
        this.press = null;
        this.plan = null;
        this.unit = null;
        this.seen = -1;
        this.el = document.createElement("div");
        this.el.className = "doc-block-handle hidden";
        this.el.title = "Drag to move this block. Alt+Up and Alt+Down move it from the keyboard";
        this.el.setAttribute("aria-hidden", "true");
        const icon = document.createElement("i");
        icon.className = "ph ph-dots-six-vertical";
        this.el.appendChild(icon);
        this.mark = document.createElement("div");
        this.mark.className = "doc-block-drop hidden";
        view.scrollDOM.append(this.el, this.mark);
        this.on = {
          hover: (event) => this.hover(event),
          leave: () => this.press || this.hide(),
          down: (event) => this.down(event),
          move: (event) => this.drag(event),
          up: (event) => this.drop(event),
          cancel: () => this.end(),
        };
        view.contentDOM.addEventListener("pointermove", this.on.hover);
        view.scrollDOM.addEventListener("pointerleave", this.on.leave);
        this.el.addEventListener("pointerdown", this.on.down);
        this.el.addEventListener("pointermove", this.on.move);
        this.el.addEventListener("pointerup", this.on.up);
        this.el.addEventListener("pointercancel", this.on.cancel);
      }
      update(update) {
        if (!update.docChanged) return;
        this.end();
        this.hide();
      }
      destroy() {
        this.view.contentDOM.removeEventListener("pointermove", this.on.hover);
        this.view.scrollDOM.removeEventListener("pointerleave", this.on.leave);
        this.el.remove();
        this.mark.remove();
      }

      hide() {
        this.unit = null;
        this.seen = -1;
        this.el.classList.add("hidden");
      }

      //: The block under the pointer. Recomputed only when the pointer changes
      //: line (the block model reads the whole text), and a blank line between
      //: two blocks leaves the grip where it was so the pointer can reach it.
      hover(event) {
        if (this.press || event.pointerType !== "mouse" || window.matchMedia("(hover: none)").matches) return;
        if (!docFileType().previewable) return this.hide();
        const view = this.view;
        const pos = view.posAtCoords({ x: event.clientX, y: event.clientY }, false);
        if (pos == null) return;
        const doc = view.state.doc;
        const line = doc.lineAt(pos);
        if (line.from === this.seen) return;
        if (!line.text.trim()) return;
        this.seen = line.from;
        const text = docStr(doc);
        let edit = docBlockMoveEdit(text, line.from, 1);
        if (!edit || edit.noop) edit = docBlockMoveEdit(text, line.from, -1);
        if (!edit || edit.noop || !edit.unit) return this.hide();
        const box = view.coordsAtPos(edit.unit.from);
        if (!box) return this.hide();
        const scroller = view.scrollDOM;
        const sr = scroller.getBoundingClientRect();
        this.unit = edit.unit;
        this.el.classList.remove("hidden");
        this.el.style.top = `${Math.round(box.top - sr.top - scroller.clientTop + scroller.scrollTop)}px`;
        this.el.style.height = `${Math.round(box.bottom - box.top)}px`;
        this.el.style.left = `${Math.max(0, Math.round(box.left - sr.left - scroller.clientLeft + scroller.scrollLeft))}px`;
      }

      down(event) {
        if (event.button !== 0 || !this.unit) return;
        //: Not a text press: the editor keeps its focus and its caret.
        event.preventDefault();
        this.press = { id: event.pointerId, x: event.clientX, y: event.clientY, drag: false, unit: this.unit, text: docStr(this.view.state.doc) };
        this.plan = null;
        try {
          this.el.setPointerCapture(event.pointerId);
        } catch {
          /* a pointer that is already gone: the release will not come, and the press is dropped */
        }
      }

      //: Where a drop at this height lands: the nearest line edge, then as many
      //: neighbours as that edge is past, each one the keyboard move.
      planFor(drop) {
        const press = this.press;
        let text = press.text;
        let at = press.unit.from;
        let edge = null;
        let steps = 0;
        const delta = drop > at ? 1 : -1;
        while (steps < 500) {
          const edit = docBlockMoveEdit(text, at, delta);
          if (!edit || edit.noop) break;
          if (delta > 0 ? drop < edit.hopTo : drop > edit.hopFrom) break;
          text = text.slice(0, edit.from) + edit.insert + text.slice(edit.to);
          if (delta > 0 && drop >= edit.to) drop += edit.insert.length - (edit.to - edit.from);
          at = edit.caret;
          edge = delta > 0 ? edit.hopTo : edit.hopFrom;
          steps += 1;
        }
        return { text, at, edge, steps };
      }

      drag(event) {
        const press = this.press;
        if (!press || event.pointerId !== press.id) return;
        if (!press.drag && Math.hypot(event.clientX - press.x, event.clientY - press.y) >= DOC_GRIP_DRAG_PX) {
          press.drag = true;
          this.el.classList.add("is-dragging");
        }
        if (!press.drag) return;
        const view = this.view;
        const scroller = view.scrollDOM;
        const sr = scroller.getBoundingClientRect();
        if (event.clientY < sr.top + 24) scroller.scrollTop -= 12;
        else if (event.clientY > sr.bottom - 24) scroller.scrollTop += 12;
        const doc = view.state.doc;
        const block = view.lineBlockAtHeight(event.clientY - view.documentTop);
        const line = doc.lineAt(block.from);
        const upper = event.clientY - view.documentTop < (block.top + block.bottom) / 2;
        const drop = upper ? line.from : Math.min(line.to + 1, doc.length);
        if (!this.plan || this.plan.drop !== drop) this.plan = { ...this.planFor(drop), drop };
        const edge = this.plan.steps ? view.lineBlockAt(this.plan.edge) : null;
        this.mark.classList.toggle("hidden", !edge);
        if (!edge) return;
        const cr = view.contentDOM.getBoundingClientRect();
        const y = this.plan.edge >= doc.length ? edge.bottom : edge.top;
        this.mark.style.top = `${Math.round(view.documentTop + y - sr.top - scroller.clientTop + scroller.scrollTop)}px`;
        this.mark.style.left = `${Math.round(cr.left - sr.left - scroller.clientLeft + scroller.scrollLeft)}px`;
        this.mark.style.width = `${Math.round(cr.width)}px`;
      }

      drop(event) {
        const press = this.press;
        const plan = this.plan;
        if (!press || event.pointerId !== press.id) return;
        const view = this.view;
        this.end();
        if (!press.drag || !plan || !plan.steps || view.state.doc.length !== press.text.length) return;
        //: The move is a swap of text the document already has, so the change is
        //: the stretch that differs: one edit, one transaction, one Undo.
        const old = press.text;
        const next = plan.text;
        const room = Math.min(old.length, next.length);
        let from = 0;
        while (from < room && old.charCodeAt(from) === next.charCodeAt(from)) from += 1;
        let tail = 0;
        while (tail < room - from && old.charCodeAt(old.length - 1 - tail) === next.charCodeAt(next.length - 1 - tail)) tail += 1;
        view.dispatch({
          changes: { from, to: old.length - tail, insert: next.slice(from, next.length - tail) },
          selection: { anchor: plan.at },
          userEvent: "move.line",
        });
      }

      end() {
        this.press = null;
        this.plan = null;
        this.el.classList.remove("is-dragging");
        this.mark.classList.add("hidden");
      }
    },
  );
  return docViewState.blockHandle;
};

//: State the Phase 2 pieces share: the pending Mermaid pictures and its Live field (documents-mermaid.js), the image refocus and the print sheet.
const docPhase2State = { mermaidDrawn: Promise.resolve(), mermaidReady: false, mermaidFieldCache: null, imageRefocus: null, printSheet: null };




// --- keeping the two panes looking at the same place --------------------------
//
// Side by side is only half of a split view. Without this, scrolling the
// editor leaves the preview showing paragraph one, so the rendered half is
// useful for the first screen of a document and decorative after that, which
// is most of what "the panes get squished together and it feels annoying to
// use" is about once they are actually side by side.
//
// **This used to be a scroll fraction, and the fraction is what was wrong.**
// The owner, 2026-09-20: "the scrolling is off in the split document view
// because of the md rendering", which names the cause exactly. A fraction
// assumes the two panes are the same document at two scales, and they are not:
// a picture is one line of source and four hundred pixels of preview, a table
// is six lines and one box, a code fence is twenty lines in both but with a
// header strip and a different line height in one of them. Every such block
// shifts everything below it in one pane and not the other, and the error is
// cumulative, so the top of a document lines up, the bottom lines up (both
// ends are exact by construction), and the middle, which is where anybody
// actually reads, is off by however much furniture is above it.
//
// So the map is line to block. `renderMarkdown` (navigation.js) stamps every block it
// draws with the source line it came from, which is the one place that can
// know; `docScrollAnchors` turns those stamps into pairs of offsets, one in
// each pane, and the sync interpolates between the two nearest. The old
// fraction is still here and still used, for the case where there is nothing
// to interpolate between: fewer than two anchors, or a textarea fallback with
// no line-to-pixel map of its own.

//: Which pane the user is actually scrolling. Without this the two feed each
//: other: A scrolls B, B's scroll event scrolls A, and the pair juddate to a
//: stop somewhere neither of them was asked to go.
let docScrollDriver = null;

//: The anchor table, rebuilt only when something that could move an anchor has
//: changed. Building it walks every block in the preview and asks the editor
//: where each one's line sits, which is far too much to do on every frame of a
//: scroll; the token below is two layout reads and changes whenever the
//: rendering, the text or either pane's size has.
let docScrollAnchorCache = { token: "", anchors: [] };

//: Where a source line starts, in the editor's own scrolled coordinates.
//:
//: CodeMirror is asked through `lineBlockAt`, not through `coordsAtPos`, and
//: the difference matters here more than anywhere else in this file: the view
//: only renders the lines near the viewport, so `coordsAtPos` answers null for
//: exactly the anchors this table is built for, the ones off screen.
//: `lineBlockAt` answers from the height map, which covers the whole document.
//:
//: A textarea has no line map at all, and rather than guess, this returns null
//: and the caller falls back to the fraction. An estimate here would be a
//: worse fraction wearing the word "anchor".
function docSourceLineTop(surface, line) {
  if (!surface || surface.kind !== "codemirror") return null;
  const view = surface.view;
  const doc = view.state.doc;
  const number = Math.max(1, Math.min(line + 1, doc.lines));
  return view.lineBlockAt(doc.line(number).from).top;
}

//: One pair of offsets per rendered block that says where it came from: the
//: top of its source line in the editor, and the top of the block itself in
//: the preview, both in their own pane's scrolled coordinates.
//:
//: Monotonic by construction, and checked anyway: a block whose stamp is not
//: past the previous one's is dropped rather than allowed to fold the map back
//: on itself, which would make the interpolation jump backwards. Two anchors
//: are the minimum worth having, since one line and one slope is what
//: interpolation needs.
function docScrollAnchors(editor, preview) {
  //: The widths are in the token, not decoration: a pane that changes width
  //: rewraps every paragraph in it, which moves every anchor below the first
  //: one that rewrapped. The sidebar collapsing is the case that found this,
  //: and it can change a width without changing either scroll height, so the
  //: four numbers that were here could all stay the same across it.
  const token = [
    preview.childElementCount,
    preview.scrollHeight,
    preview.clientWidth,
    editor.scrollHeight,
    editor.scrollEl?.clientWidth || 0,
    editor.kind === "codemirror" ? editor.view.state.doc.length : -1,
  ].join(":");
  if (docScrollAnchorCache.token === token) return docScrollAnchorCache.anchors;
  const anchors = [];
  let lastLine = -1;
  //: **Rects, corrected by the pane's own, never `offsetTop`.** This is the
  //: rule `setDocPage` (app.js) already states for the same reason, and
  //: ignoring it is what INBOX 278 turned out to be: `offsetTop` is measured
  //: against the nearest **positioned** ancestor, and the preview is not
  //: positioned. Measured on the probe document at 1440: every block's
  //: `offsetTop` ran 218px past its true offset in the pane with the sidebar
  //: open, and 146px with it collapsed, because collapsing it puts a
  //: positioned `#doc-layout` between the block and the body.
  //:
  //: A constant bias is not a harmless one here. Every anchor carries it, the
  //: interpolation hands it straight through, and `syncDocScroll` then parks
  //: the preview that far past the line the source is showing, at every
  //: position in the document: which is exactly the shape of the report, "the
  //: documents split view scrolling is broken and misaligned", with no
  //: pattern to it because the error does not grow, it just sits there.
  //:
  //: It also defeated the probe that closed the first report, because that
  //: probe read `offsetTop` too: the same bias on both sides of the
  //: subtraction cancels, and the answer comes back 0 from a pane that is a
  //: paragraph and a half out. `scratchpad/ui-sweeps/docsplit.js` measures
  //: through rects now for that reason.
  const previewTop = preview.getBoundingClientRect().top;
  for (const block of preview.children) {
    //: The stamp is a line in the string the preview rendered; the editor
    //: counts from a different zero (`docPreviewLineShift`).
    const line = Number(block.dataset.srcLine) - docPreviewLineShift;
    if (!Number.isFinite(line) || line <= lastLine) continue;
    const srcTop = docSourceLineTop(editor, line);
    if (srcTop === null) {
      docScrollAnchorCache = { token, anchors: [] };
      return docScrollAnchorCache.anchors;
    }
    anchors.push({
      srcTop,
      prevTop: block.getBoundingClientRect().top - previewTop + preview.scrollTop,
    });
    lastLine = line;
  }
  docScrollAnchorCache = { token, anchors: anchors.length >= 2 ? anchors : [] };
  return docScrollAnchorCache.anchors;
}

//: Piecewise-linear, with the end segments' own slopes carried outwards.
//:
//: The alternative at the ends is to clamp, and clamping is visibly wrong in
//: the one place it would apply: the space above the first block and below the
//: last, where a clamped map pins the other pane while this one keeps moving.
//: Carrying the slope keeps both moving at the rate the nearest real pair of
//: anchors says they should.
function docMapThroughAnchors(value, anchors, forward) {
  const key = forward ? "srcTop" : "prevTop";
  const other = forward ? "prevTop" : "srcTop";
  let index = 0;
  while (index < anchors.length - 2 && anchors[index + 1][key] <= value) index += 1;
  const low = anchors[index];
  const high = anchors[index + 1];
  const span = high[key] - low[key];
  //: Two anchors at the same offset in one pane (an empty block, a heading
  //: immediately followed by another) would divide by zero; the lower one's
  //: partner is the honest answer.
  if (span <= 0) return low[other];
  const ratio = (value - low[key]) / span;
  return low[other] + ratio * (high[other] - low[other]);
}

function syncDocScroll(from) {
  const editor = docSurface();
  const preview = $("doc-preview");
  if (!editor || !preview || preview.classList.contains("hidden")) return;
  //: Compared against the *preview*, not against the editor. The editor half
  //: of this pair is a surface whose identity is stable but whose scrolling
  //: element changes when CodeMirror takes over, so "is this the preview"
  //: is the question with one answer.
  const to = from === preview ? editor : preview;
  // A pane with nothing to scroll has a zero range; dividing by it gives NaN,
  // and assigning NaN to scrollTop silently jumps the other pane to 0.
  const fromRange = from.scrollHeight - from.clientHeight;
  const toRange = to.scrollHeight - to.clientHeight;
  if (fromRange <= 0 || toRange <= 0) return;
  const anchors = docScrollAnchors(editor, preview);
  let next;
  if (anchors.length >= 2) {
    next = docMapThroughAnchors(from.scrollTop, anchors, from !== preview);
  } else {
    //: No map to read: the fraction, which is what this always was.
    next = (from.scrollTop / fromRange) * toRange;
  }
  docScrollDriver = from;
  to.scrollTop = Math.max(0, Math.min(Math.round(next), toRange));
  // Cleared on a timer rather than immediately: the assignment above fires the
  // other pane's own scroll event asynchronously, so clearing on this tick
  // lets that event through and starts the feedback loop this exists to stop.
  clearTimeout(syncDocScroll._release);
  syncDocScroll._release = setTimeout(() => { docScrollDriver = null; }, 120);
}

//: Idempotent per scrolling element, because the editor's scroller is
//: replaced when CodeMirror mounts and the pair has to be re-wired then.
//: `dataset` rather than a set, so a scroller that is thrown away takes its
//: mark with it (tests/test_frontend_handlers.py exists because of exactly
//: the duplicate-listener shape this avoids).
function wireDocSurfaceScroll(surface) {
  const el = surface?.scrollEl;
  if (!el || el.dataset.docScrollSync === "1") return;
  el.dataset.docScrollSync = "1";
  el.addEventListener("scroll", () => {
    //: Before the driver guard below, not after it: the outline follows the
    //: editor whichever pane started the scroll, and when the preview is
    //: driving, this listener's own surface is the one being moved.
    scheduleDocOutlineSpy();
    docRememberPosition();
    if (docScrollDriver && docScrollDriver !== surface) return;
    syncDocScroll(surface);
  });
}

function wireDocScrollSync() {
  wireDocSurfaceScroll(docSurface());
  const preview = $("doc-preview");
  if (!preview) return;
  preview.addEventListener("scroll", () => {
    if (docScrollDriver && docScrollDriver !== preview) return;
    syncDocScroll(preview);
  });
}

// Markdown formatting from a toolbar, so you don't have to remember the
// syntax. Everything it inserts is plain markdown, the file stays portable
// and the source stays readable, which is the point of using markdown at all.
const MD_ACTIONS = {
  h1: { line: "# " },
  h2: { line: "## " },
  h3: { line: "### " },
  bold: { wrap: MD_INLINE_MARKS.bold, placeholder: "bold text" },
  italic: { wrap: MD_INLINE_MARKS.italic, placeholder: "italic text" },
  strike: { wrap: MD_INLINE_MARKS.strike, placeholder: "struck through" },
  code: { wrap: MD_INLINE_MARKS.code, placeholder: "code" },
  highlight: { wrap: MD_INLINE_MARKS.highlight, placeholder: "highlighted" },
  clearformat: { custom: "clearformat" },
  //: Opens the "/" menu (editor.js), the one insert catalogue (DX6).
  insert: { custom: "insert" },
  //: The one icon and emoji picker (MINDMAP_PLAN decision 46).
  emoji: { custom: "emoji" },
  //: The picker's other two tabs and the calculator, each its own door (INBOX 1544).
  icon: { custom: "icon" },
  symbol: { custom: "symbol" },
  equation: { custom: "equation" },
  calculator: { custom: "calculator" },
  ul: { line: "- " },
  ol: { line: "1. " },
  task: { line: "- [ ] " },
  quote: { line: "> " },
  link: { custom: "link" },
  codeblock: { block: "```\n", suffix: "\n```", placeholder: "your code" },
  //: **Three columns, and the caret in the first header cell.** The "/" menu
  //: has always said "3 columns" and this table had two, which is the kind of
  //: disagreement nobody reports and everybody notices. `custom`, because the
  //: `insert` shape leaves the caret after the whole block: a table you have
  //: to arrow back into is a table you retype.
  table: { custom: "table" },
  hr: { insert: "\n---\n" },

  //: **The rest of the Obsidian editing-toolbar's command set**, asked for by
  //: name: *"I want you to make the toolbar in the notes and documents
  //: exactly like this but also with the application specific functions, both
  //: in what tools are there, and how they function"*, PKM-er's
  //: obsidian-editing-toolbar.
  //:
  //: Added to this table rather than to a second one, because this table is
  //: already the single place that decides what `**` means in this app (see
  //: its own comment, and editor.js's "/" menu, which reads the same
  //: dialect). A command that lives anywhere else is a third opinion waiting
  //: to disagree.
  h4: { line: "#### " },
  h5: { line: "##### " },
  h6: { line: "###### " },
  //: A callout, not a bare blockquote. `> [!note]` is the syntax Obsidian,
  //: GitHub and Typora all already render, which is the same portability
  //: argument editor.js makes for using it in the "/" menu.
  callout: { block: "> [!note] ", suffix: "\n> ", placeholder: "Title" },
  //: Asymmetric wrappers: HTML, because markdown has no superscript and
  //: Obsidian's own toolbar inserts exactly these tags.
  sup: { pre: "<sup>", post: "</sup>", placeholder: "sup" },
  sub: { pre: "<sub>", post: "</sub>", placeholder: "sub" },
  underline: { pre: "<u>", post: "</u>", placeholder: "underlined" },
  //: `$…$` is the syntax every markdown editor with math uses, and the
  //: renderer for it is in this file (`docMathTree`). Symmetric, so pressing
  //: it twice takes it off again, which is what `wrap` gives.
  math: { wrap: "$", placeholder: "x^2" },
  //: `%%…%%` is Obsidian's comment: kept in the file, never rendered.
  comment: { pre: "%%", post: "%%", placeholder: "note to self" },
  //: A remark *on* something, which is the comment the panel lists (Phase 5
  //: item 1). `custom`, because a `pre`/`post` pair cannot do it: what it
  //: inserts depends on whether anything is selected, and the caret has to
  //: land between the two `%%` pairs rather than after the whole insertion.
  annotate: { custom: "annotate" },
  image: { custom: "image" },
  //: Properties (DOCUMENTS_PLAN Phase 3 item 4). `custom`, because the block
  //: goes at the top of the document rather than at the caret: it is the one
  //: markdown construct whose position is fixed by what it means.
  properties: { custom: "properties" },
  //: A block reference (DOCUMENTS_PLAN Phase 4 item 2). `custom`, because it
  //: inserts nothing at the caret: it gives the block the caret is in an id
  //: and puts the link to it on the clipboard.
  blockref: { custom: "blockref" },
  //: A synced block (DOCUMENTS_PLAN 26): the same block reference as an embed, copied now and inserted in another document later.
  syncedcopy: { custom: "syncedcopy" },
  syncedpaste: { custom: "syncedpaste" },
  //: Two columns, with the caret in the first one. The `block`/`suffix` shape
  //: rather than `insert`, so the selection lands on the placeholder and the
  //: first thing typed replaces it, which is what the table and the code
  //: block already do.
  columns: {
    block: "\n:::columns\n",
    suffix: "\n:::column\n\n:::\n",
    placeholder: "Left column",
  },
  //: This app's own link syntax, which is the "application specific
  //: functions" half of the request, a toolbar for *this* notebook has to
  //: offer the link that resolves inside it, not only the markdown one.
  wikilink: { pre: "[[", post: "]]", placeholder: "note name" },
  footnote: { custom: "footnote" },
  cite: { custom: "cite" },
  indent: { custom: "indent" },
  outdent: { custom: "outdent" },
  undo: { custom: "undo" },
  redo: { custom: "redo" },
};

// `boxId` is what lets the Notes composer reuse this whole table. It used to
// be hardcoded to the document editor, and duplicating the logic for notes
// would have been the third place in this app to independently decide what
// `**` means: see MD_ACTIONS' own comment and editor.js's "/" menu, which
// are already deliberately kept to one dialect.
//: **A line prefix is a switch, not a stack.** The heading, list, task and
//: quote buttons used to put their marker in front of whatever the line
//: already began with, so H2 on a heading did nothing,
//: Numbered on a bullet gave `1. - x` and H1 on `## x` gave `# ## x`. A
//: second press on the same kind takes it off (every other editor's toggle);
//: a different kind of the same family (heading, list) replaces it; a quote
//: marker is its own layer and stays put under either. Blank lines in a
//: multi-line selection are left blank; a numbered list counts 1, 2, 3.
const MD_LINE_KINDS = {
  h1: ["heading", "# "], h2: ["heading", "## "], h3: ["heading", "### "],
  h4: ["heading", "#### "], h5: ["heading", "##### "], h6: ["heading", "###### "],
  ul: ["list", "- "], ol: ["list", "1. "], task: ["list", "- [ ] "], quote: ["quote", "> "],
};
const MD_LINE_QUOTE = /^(?:>[ \t]?)+/;
const MD_LINE_HEAD = /^( *)(#{1,6}[ \t]+)?(?:(?:([-*+])|(\d+[.)]))[ \t]+(\[[ xX]\][ \t]+)?)?/;

//: What a line (past any quote marker) already is: "h1".."h6", "ul", "ol",
//: "task" or "".
function mdLineKind(rest) {
  const m = MD_LINE_HEAD.exec(rest);
  if (m[2]) return `h${m[2].trim().length}`;
  if (m[4]) return "ol";
  if (m[3]) return m[5] ? "task" : "ul";
  return "";
}

function mdLinePrefixEdit(block, kind) {
  const [family, marker] = MD_LINE_KINDS[kind];
  const lines = block.split("\n");
  const live = lines.filter((line) => line.trim());
  const one = lines.length === 1;
  const split = (line) => {
    const lead = MD_LINE_QUOTE.exec(line)?.[0] || "";
    return [lead, line.slice(lead.length)];
  };
  const has = (line) => {
    const [lead, rest] = split(line);
    return family === "quote" ? Boolean(lead) : mdLineKind(rest) === kind;
  };
  const off = (live.length > 0 || one) && (live.length ? live : lines).every(has);
  let count = 0;
  return lines.map((line) => {
    if (!line.trim() && !one) return line;
    const [lead, rest] = split(line);
    if (family === "quote") return off ? rest : lead ? line : marker + line;
    const head = MD_LINE_HEAD.exec(rest)[0];
    const body = rest.slice(head.length);
    if (off) return lead + body;
    count += 1;
    const indent = family === "list" ? /^ */.exec(rest)[0] : "";
    return `${lead}${indent}${kind === "ol" ? `${count}. ` : marker}${body}`;
  }).join("\n");
}

//: **Image opens a picker** (audit 1028 U10; it used to drop a bare
//: `![image](https://)` and leave the person to find a URL). The file goes to
//: the media store as a pasted or imported picture does (`/media/upload`) and
//: the embed is written where the caret was. The old stub is the fallback when
//: the upload fails, so the button never ends in nothing.
function docImagePick(box, boxId) {
  const input = document.createElement("input");
  input.type = "file";
  input.accept = "image/*,video/mp4,video/webm,.mp4,.webm";
  input.addEventListener("change", () => {
    const file = input.files && input.files[0];
    if (file) docImageUpload(box, boxId, file);
  });
  input.click();
}

async function docImageUpload(box, boxId, file, said = "") {
  const { selectionStart: start, selectionEnd: end, value } = box;
  const alt = said || value.slice(start, end) || file.name.replace(/\.[^.]+$/, "") || "image";
  try {
    const form = new FormData();
    form.append("file", file);
    const uploaded = await apiJson("/media/upload", { method: "POST", headers: authHeaders(), body: form });
    if (!uploaded || !uploaded.url) throw new Error("no address");
    docUndoBreak();
    const at = Math.min(start, box.value.length);
    const embed = `![${alt}](${uploaded.url})`;
    box.value = `${box.value.slice(0, at)}${embed}${box.value.slice(Math.min(end, box.value.length))}`;
    box.setSelectionRange(at + embed.length, at + embed.length);
    finishMarkdownEdit(box, boxId);
  } catch {
    const before = box.value;
    docImageStub(box, boxId, start, end);
    const stubbed = box.value;
    //: Try again takes the stub back out first (if it is untouched), so the
    //: picture lands where the first try would have.
    const retry = () => {
      if (box.value === stubbed) {
        box.value = before;
        box.setSelectionRange(start, end);
      }
      docImageUpload(box, boxId, file, said);
    };
    toast("Couldn't upload that picture. Add its address by hand.", true, { action: ["Try again", retry] });
  }
}

//: **A picture pasted into a markdown document asks what it shows** (audit
//: 1028 D27). The upload and the embed were already there (settings-wiring.js'
//: paste handler), with the file's own name for alt text, "image.png". On
//: `window` in the capture phase so it runs ahead of that one, and only for a
//: clipboard that is a picture and nothing else; a copy with words in it is
//: the words' paste. An empty answer or Escape still adds the picture.
window.addEventListener("paste", (event) => {
  const view = docCmView;
  if (!view || !view.dom.contains(event.target) || view.dom.classList.contains("doc-content-code") || view.state.readOnly) return;
  const data = event.clipboardData;
  if (!data || data.getData("text/plain")) return;
  const file = [...data.files].find((f) => f.type.startsWith("image/"));
  if (!file) return;
  event.preventDefault();
  event.stopPropagation();
  docImagePasteAsk(file);
}, true);

async function docImagePasteAsk(file) {
  const said = await promptDialog("Describe this picture (optional)", "", { confirmLabel: "Add picture" });
  await docImageUpload(docSurface(), "doc-content", file, said);
}

//: The address-by-hand form: the selection becomes the *alt text* and the
//: caret lands on the URL, the same split `link` makes. (The first version
//: passed the alt text as the body between the two markers and produced
//: `![cat](cat)`: a picture whose address was its own caption.)
function docImageStub(box, boxId, start, end) {
  const alt = box.value.slice(start, end) || "image";
  const url = "https://";
  box.value = `${box.value.slice(0, start)}![${alt}](${url})${box.value.slice(end)}`;
  const at = start + alt.length + 4;
  box.setSelectionRange(at, at + url.length);
  finishMarkdownEdit(box, boxId);
}

function applyMarkdown(kind, boxId = "doc-content") {
  const action = MD_ACTIONS[kind];
  const box = docSurfaceById(boxId);
  if (!action || !box) return;
  //: A toolbar press is its own undo step, never part of the typing burst it
  //: happened to follow. Set *before* the edit, because the recording happens
  //: inside it (`finishMarkdownEdit` -> `markDocDirty`).
  docUndoBreak();
  const { selectionStart: start, selectionEnd: end, value } = box;
  const selected = value.slice(start, end);

  if (action.wrap) {
    wrapDocSelection(action.wrap, action.placeholder, boxId);
    return;
  }
  if (action.custom === "clearformat") {
    clearInlineFormatting(box);
    finishMarkdownEdit(box, boxId);
    return;
  }
  if (action.custom === "insert") {
    box.focus();
    editorOpenMenuByShortcut();
    return;
  }
  if (["emoji", "icon", "symbol"].includes(action.custom)) {
    //: Hung from the button that asked, in whichever strip it is (a strip
    //: without that tab's button hangs it from the emoji one); a button inside
    //: a closed Insert menu has no place, so the picker centres.
    const near = `:is([data-md="${action.custom}"], [data-md="emoji"])`;
    const anchor = document.querySelector(`[data-md-target="${boxId}"] ${near}`)
      || (boxId === "doc-content" ? document.querySelector(`#doc-toolbar ${near}`) : null);
    editorPickGlyph(box, anchor, action.custom);
    return;
  }
  if (action.custom === "calculator") {
    //: Over this box, so its Insert writes here; the same entry the palette's row uses.
    POPUP_TOOLS.find((tool) => tool.id === "calculator").open(box);
    return;
  }
  if (action.custom === "equation") {
    //: The guided equation editor (math-editor.js, DOCUMENTS_PLAN 16); from a
    //: closed Insert menu it centres, as the picker above does.
    openMathEditor({ target: box });
    return;
  }
  //: **Undo and redo go through the browser's own history, deliberately.**
  //: A textarea already has one, built from the user's typing *and* from
  //: `execCommand("insertText")`, and reimplementing it here would give the
  //: editor a second history that disagrees with Ctrl+Z, the one thing a
  //: user is certain about in any text box.
  if (action.custom === "undo" || action.custom === "redo") {
    box.focus();
    //: **The document editor has its own history now, and these buttons use
    //: it.** The paragraph above is still true everywhere else, the notes
    //: composer and the note edit form are one textarea each, so the browser's
    //: own stack is the right one and a second would only disagree with
    //: Ctrl+Z. The document editor is the case that broke the assumption, and
    //: it now has a real history of its own: CodeMirror's, where the engine is
    //: mounted, and the D3 snapshot stack at the end of this file where it is
    //: not. `docUndo` picks between them; this button must not reach past it
    //: to `execCommand`, which knows about neither.
    if (docToolsBoxFor(box)) {
      if (action.custom === "undo") docUndo();
      else docRedo();
      return;
    }
    document.execCommand(action.custom);
    finishMarkdownEdit(box, boxId);
    return;
  }
  if (action.custom === "indent" || action.custom === "outdent") {
    shiftDocIndent(box, action.custom === "indent" ? 1 : -1);
    finishMarkdownEdit(box, boxId);
    return;
  }
  if (action.custom === "image") {
    docImagePick(box, boxId);
    return;
  }
  if (action.custom === "properties") {
    docInsertProperties();
    return;
  }
  if (action.custom === "blockref" || action.custom === "syncedcopy" || action.custom === "syncedpaste") {
    docCopyBlockRef(action.custom === "blockref" ? "link" : action.custom === "syncedcopy" ? "copy" : "paste");
    return;
  }
  if (action.custom === "table") {
    //: Blank cells with their outer pipes, so every one of them is a cell GFM
    //: can see (`docTableFillRowEdits` carries the reason a blank last cell
    //: without a trailing pipe is not a cell at all).
    const table = "\n| Column | Column | Column |\n| --- | --- | --- |\n|  |  |  |\n|  |  |  |\n";
    box.value = value.slice(0, start) + table + value.slice(end);
    const at = start + table.indexOf("Column");
    box.setSelectionRange(at, at + "Column".length);
    finishMarkdownEdit(box, boxId);
    return;
  }
  if (action.custom === "annotate") {
    docAnnotateSelection(box, boxId);
    return;
  }
  if (action.custom === "cite") {
    //: A citation: the reference at the caret and the source at the foot (`docPairInput.citeInsert`).
    //: A note is picked and written as `[[title]]`; an address or words typed in the same box stay as typed.
    docPairInput.citePick().then((source) => {
      if (!source || !source.trim()) return;
      const done = docPairInput.citeInsert(box.value, end, end, source);
      box.value = done.value;
      box.setSelectionRange(done.caret, done.caret);
      finishMarkdownEdit(box, boxId);
    });
    return;
  }
  if (action.custom === "footnote") {
    //: A reference *and* its definition, because a footnote marker with
    //: nothing to point at renders as literal text and reads as a bug.
    const marker = `[^${docNextFootnote(value)}]`;
    box.value = `${value.slice(0, start)}${marker}${value.slice(end)}\n\n${marker}: `;
    const at = box.value.length;
    box.setSelectionRange(at, at);
    finishMarkdownEdit(box, boxId);
    return;
  }
  if (action.pre) {
    //: A second press takes the pair off, as Bold does: the selection sits
    //: inside the pair, or is the pair with its words.
    const post = action.post || "";
    if (selected && value.slice(start - action.pre.length, start) === action.pre && value.slice(end, end + post.length) === post) {
      box.value = value.slice(0, start - action.pre.length) + selected + value.slice(end + post.length);
      box.setSelectionRange(start - action.pre.length, end - action.pre.length);
      finishMarkdownEdit(box, boxId);
      return;
    }
    if (selected.length > action.pre.length + post.length && selected.startsWith(action.pre) && selected.endsWith(post)) {
      const bare = selected.slice(action.pre.length, selected.length - post.length);
      box.value = value.slice(0, start) + bare + value.slice(end);
      box.setSelectionRange(start, start + bare.length);
      finishMarkdownEdit(box, boxId);
      return;
    }
    const body = selected || action.placeholder || "";
    insertAround(box, start, end, action.pre, action.post || "", body, action.pre.length);
    finishMarkdownEdit(box, boxId);
    return;
  }
  if (action.line) {
    // Every selected line, or the current one when nothing is selected.
    const lineStart = value.lastIndexOf("\n", start - 1) + 1;
    const lineEnd = end + (value.slice(end).indexOf("\n") === -1 ? 0 : value.slice(end).indexOf("\n"));
    const to = Math.max(lineEnd, end);
    const prefixed = mdLinePrefixEdit(value.slice(lineStart, to), kind);
    box.value = value.slice(0, lineStart) + prefixed + value.slice(to);
    box.setSelectionRange(lineStart, lineStart + prefixed.length);
  } else if (action.custom === "link") {
    const label = selected || "link text";
    const inserted = `[${label}](https://)`;
    box.value = value.slice(0, start) + inserted + value.slice(end);
    // Land the caret in the URL, which is the part you still have to type.
    const at = start + label.length + 3;
    box.setSelectionRange(at, at + 8);
  } else if (action.block) {
    const body = selected || action.placeholder;
    const inserted = action.block + body + action.suffix;
    box.value = value.slice(0, start) + inserted + value.slice(end);
    const at = start + action.block.length;
    box.setSelectionRange(at, at + body.length);
  } else if (action.insert) {
    box.value = value.slice(0, start) + action.insert + value.slice(end);
    const at = start + action.insert.length;
    box.setSelectionRange(at, at);
  }
  finishMarkdownEdit(box, boxId);
}

//: Wrap a selection in two different markers, leaving the body selected so
//: the next keystroke replaces a placeholder. `wrapDocSelection` above is the
//: symmetric case and carries the toggle-off logic that only makes sense when
//: both ends are the same string.
function insertAround(box, start, end, pre, post, body, caretOffset) {
  const value = box.value;
  box.value = value.slice(0, start) + pre + body + post + value.slice(end);
  const at = start + caretOffset;
  box.setSelectionRange(at, at + body.length);
}

//: Two spaces per level, matching what this app's own markdown renderer and
//: every list in it already use. Whole lines, so a selection spanning three
//: bullets indents all three, the behaviour Tab has in Obsidian's editor.
function shiftDocIndent(box, direction) {
  const { selectionStart: start, selectionEnd: end, value } = box;
  const lineStart = value.lastIndexOf("\n", start - 1) + 1;
  const tail = value.slice(end).indexOf("\n");
  const lineEnd = tail === -1 ? value.length : end + tail;
  const block = value.slice(lineStart, lineEnd);
  const shifted = block
    .split("\n")
    .map((line) =>
      direction > 0 ? `  ${line}` : line.replace(/^ {1,2}/, ""),
    )
    .join("\n");
  box.value = value.slice(0, lineStart) + shifted + value.slice(lineEnd);
  box.setSelectionRange(lineStart, lineStart + shifted.length);
}

//: The next free footnote number in this document. Counting the definitions
//: rather than the references: a reference can appear twice and share one
//: definition, which is what a footnote is for.
function docNextFootnote(text) {
  const used = [...String(text || "").matchAll(/^\[\^(\d+)\]:/gm)].map((m) => Number(m[1]));
  return used.length ? Math.max(...used) + 1 : 1;
}

// The bookkeeping every toolbar edit ends with. The document editor has a
// dirty flag and a live preview to refresh; the notes composer has neither,
// but everything downstream of typing there (autogrow, the character count,
// draft autosave) listens for `input`, which a programmatic value change does
// not fire on its own.
function finishMarkdownEdit(box, boxId) {
  box.focus();
  if (boxId === "doc-content") {
    markDocDirty();
    renderDocPreview();
  } else {
    box.dispatchEvent(new Event("input", { bubbles: true }));
  }
}

// Strip a highlight or a text colour from the selection. The counterpart to
// the two colour pickers - asked for directly ("change the colour, or remove
// the highlight"), and without it the only way back out of a colour was to
// hand-delete the markers.
function clearInlineFormatting(box) {
  const { selectionStart: start, selectionEnd: end, value } = box;
  const selected = value.slice(start, end);
  if (!selected) return;
  const cleaned = selected
    .replace(/==(?:[a-z]+\|)?([^=\n]+?)==/g, "$1")
    .replace(/\+\+[a-z]+\|([^+\n]+?)\+\+/g, "$1");
  if (cleaned === selected) return;
  box.value = value.slice(0, start) + cleaned + value.slice(end);
  box.setSelectionRange(start, start + cleaned.length);
}

// Wrap the selection in markdown syntax (Ctrl+B / Ctrl+I).
function wrapDocSelection(marker, placeholder = "", boxId = "doc-content") {
  //: Reached both from `applyMarkdown` (which has already broken the burst)
  //: and directly from Ctrl+B / Ctrl+I / Ctrl+E, which have not. Idempotent, so
  //: setting it twice costs nothing and missing it would silently fold a Bold
  //: into the word you had just typed.
  docUndoBreak();
  const box = docSurfaceById(boxId);
  if (!box) return;
  const { selectionStart: start, selectionEnd: end, value } = box;

  // Toggle off, case 1: the selection sits *inside* an existing pair of
  // markers ("**|bold text|**", caret positions marked). Reported directly:
  // applying Bold to an already-bold selection didn't remove it the way
  // every other rich-text editor's toggle does: this was a one-way
  // "apply", never a toggle.
  const before = value.slice(Math.max(0, start - marker.length), start);
  const after = value.slice(end, end + marker.length);
  if (marker && before === marker && after === marker) {
    box.value =
      value.slice(0, start - marker.length) + value.slice(start, end) + value.slice(end + marker.length);
    box.selectionStart = start - marker.length;
    box.selectionEnd = end - marker.length;
    box.focus();
    finishMarkdownEdit(box, boxId);
    return;
  }
  // Toggle off, case 2: the markers themselves are part of the selection
  // ("|**bold text**|"), selecting the whole formatted span, not just its
  // inner text, is just as natural a way to select it for un-formatting.
  if (
    marker &&
    end - start >= marker.length * 2 &&
    value.slice(start, start + marker.length) === marker &&
    value.slice(end - marker.length, end) === marker
  ) {
    const inner = value.slice(start + marker.length, end - marker.length);
    box.value = value.slice(0, start) + inner + value.slice(end);
    box.selectionStart = start;
    box.selectionEnd = start + inner.length;
    box.focus();
    finishMarkdownEdit(box, boxId);
    return;
  }

  // With nothing selected, insert the placeholder and select it, so the next
  // keystroke replaces it: pressing Bold on an empty line should give you
  // somewhere to type, not two markers and a caret between them.
  const selected = value.slice(start, end) || placeholder;
  box.value = value.slice(0, start) + marker + selected + marker + value.slice(end);
  // Keep the same text selected, so the shortcut can be toggled or stacked.
  box.selectionStart = start + marker.length;
  box.selectionEnd = start + marker.length + selected.length;
  box.focus();
  //: **`finishMarkdownEdit`, not `markDocDirty()` + `renderDocPreview()`.**
  //: Both toggle-off branches above already end this way; this branch: the
  //: one that actually *applies* formatting, and so the one that runs almost
  //: every time: did the doc-content half inline instead, which quietly did
  //: the wrong thing for every other box: it marked the *document* dirty and
  //: never told the box's own listeners anything had changed.
  //:
  //: Found when the selection bar started appearing over live-view
  //: paragraphs. Bold visibly wrapped the words in the block and the document
  //: underneath never received them, measured, `input` fired 0 times, and
  //: dispatching one by hand synced it immediately. The same call was wrong
  //: for the note edit box for exactly as long, where it marked a document
  //: dirty that the user was not editing.
  finishMarkdownEdit(box, boxId);
}

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
async function deleteDocumentWithUndo(doc) {
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

// --- AI editing ---
let docAiController = null;

//: The Atlas panel's code is documents-ai.js, fetched on the first press of any
//: of its controls (audit 1031 DC13): `docAiLazy` loads it, then calls the
//: function of that name the file defines.
async function docAiLazy(name, ...args) {
  //: With the diff library beside it: the panel draws its proposal with `docRenderDiff`.
  if (!(await Promise.all([lazyScript("/js/documents-ai.js"), lazyScript("/js/documents-history.js")])).every(Boolean)) return toast("The Atlas panel could not be loaded.", true, { action: ["Try again", () => docAiLazy(name, ...args)] });
  return window[name](...args);
}

function closeDocAiPanel() {
  $("doc-ai-panel").classList.add("hidden");
}

// Extract notes (BACKLOG.md §62): the same selection-or-whole-document scope
// AI edit above already uses, select a passage first to extract from just
// that, or leave nothing selected to extract from the whole document.
function openDocExtractPreview() {
  if (!currentDoc) return;
  const box = docSurface();
  const { from, to } = box.selection();
  const selection = box.text.slice(from, to).trim();
  openExtractPreview(selection || box.text, { sourceDocumentId: currentDoc.id });
}

// --- AI edit history (the changelog) ---------------------------------------

function docAiVerbIcon(verb) {
  return { edit: "ph-pencil-simple", write: "ph-plus-circle", remove: "ph-x-circle", revert: "ph-arrow-counter-clockwise" }[verb] || "ph-pencil-simple";
}

async function openDocAiHistory() {
  if (!currentDoc) return;
  const dialog = $("doc-ai-history-dialog");
  const list = $("doc-ai-history-list");
  const empty = $("doc-ai-history-empty");
  list.replaceChildren();
  empty.classList.add("hidden");
  dialog.showModal();
  const li = document.createElement("li");
  li.className = "muted";
  li.textContent = "Loading…";
  list.appendChild(li);
  try {
    const entries = await apiJson(`/documents/${currentDoc.id}/ai-edit-log`);
    list.replaceChildren();
    if (!entries.length) {
      empty.classList.remove("hidden");
      return;
    }
    for (const entry of entries) {
      const row = document.createElement("li");
      row.className = "doc-ai-history-entry";
      const icon = document.createElement("i");
      icon.className = `ph ${docAiVerbIcon(entry.verb)}`;
      icon.setAttribute("aria-hidden", "true");
      const text = document.createElement("div");
      text.className = "doc-ai-history-text";
      const line = document.createElement("p");
      line.textContent = entry.instruction || (entry.verb === "remove" ? "Removed a selection" : "AI edit");
      const meta = document.createElement("p");
      meta.className = "muted text-sm";
      const when = whenText(entry.created_at);
      meta.textContent = entry.selection_excerpt
        ? `${when} · “${entry.selection_excerpt}”`
        : when;
      text.append(line, meta);
      const revertBtn = document.createElement("button");
      revertBtn.type = "button";
      revertBtn.className = "ghost small";
      revertBtn.textContent = "Revert";
      revertBtn.addEventListener("click", async () => {
        revertBtn.disabled = true;
        try {
          const saved = await apiJson(
            `/documents/${currentDoc.id}/ai-edit-log/${entry.id}/revert`,
            { method: "POST" }
          );
          if (currentDoc && currentDoc.id === saved.id) {
            currentDoc = saved;
            docSurface().text = saved.content;
            $("doc-title").value = saved.title;
            renderDocPreview();
            docDirty = false;
            $("doc-saved").textContent = "Saved";
          }
          docs = docs.map((d) => (d.id === saved.id ? { ...d, ...saved } : d));
          renderDocList();
          toast("Reverted.");
          dialog.close();
        } catch (error) {
          toast(error.message || "Couldn't revert that.", true);
        } finally {
          revertBtn.disabled = false;
        }
      });
      row.append(icon, text, revertBtn);
      list.appendChild(row);
    }
  } catch (error) {
    list.replaceChildren();
    const errLi = document.createElement("li");
    errLi.className = "muted";
    errLi.textContent = error.message || "Couldn't load the history.";
    list.appendChild(errLi);
  }
}

//: The version history dialog and the line diff are documents-history.js,
//: fetched on the first press of the dock's History or Name this version
//: (audit 1031 DC13). The AI edit panel, the code assistant and the edit-conflict
//: prompt wait on the same `lazyScript` before they draw a diff, so none of them
//: can run ahead of `docRenderDiff`.
for (const [id, name] of [["doc-history", "openDocHistory"], ["doc-history-name", "docNameCurrentVersion"]]) {
  $(id)?.addEventListener("click", async () => {
    if (!(await lazyScript("/js/documents-history.js"))) return toast("The history could not be loaded.", true, { action: ["Try again", () => $(id).click()] });
    return window[name]();
  });
}
//: The AI assistant's own model. `openFeatureModelSheet` lives in app.js,
//: which loads first, and is the same sheet the Chat tab and the writing desk
//: open: one picker, three ways in.
$("doc-ai-model")?.addEventListener("click", () => window.openFeatureModelSheet?.("documents"));

const DOC_SIDEBAR_SECTIONS = ["list", "outline"];
const DOC_SIDEBAR_STORE = "docSidebarSection";

function showDocSidebarSection(name) {
  const wanted = DOC_SIDEBAR_SECTIONS.includes(name) ? name : "list";
  for (const section of DOC_SIDEBAR_SECTIONS) {
    $(`doc-sidebar-${section}`)?.classList.toggle("hidden", section !== wanted);
  }
  for (const button of document.querySelectorAll("#doc-sidebar-tabs button")) {
    const active = button.dataset.section === wanted;
    button.classList.toggle("active", active);
    button.setAttribute("aria-selected", String(active));
    button.tabIndex = active ? 0 : -1;
  }
  prefs.set(DOC_SIDEBAR_STORE, wanted);
  //: A hidden list has no scroll position to correct, so the mark made while
  //: the Documents tab was showing could not bring its row into view. Asked
  //: again on the way in, when the outline has a box.
  if (wanted === "outline") {
    docOutlineMarked = -1;
    markDocOutline();
    //: The comments section is in this tab and is drawn from the document's own
    //: text on every facts pass, so the same argument applies to it: a hidden
    //: list has nothing to draw into, and the pass that ran while the Documents
    //: tab was showing left it with nothing in it.
    renderDocComments();
  }
}

function initDocSidebarTabs() {
  const strip = $("doc-sidebar-tabs");
  if (!strip || strip.dataset.ready) return;
  strip.dataset.ready = "1";
  strip.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-section]");
    if (button) showDocSidebarSection(button.dataset.section);
  });
  strip.addEventListener("keydown", (event) => {
    const step = { ArrowRight: 1, ArrowLeft: -1 }[event.key];
    if (!step) return;
    event.preventDefault();
    const index = DOC_SIDEBAR_SECTIONS.indexOf(
      prefs.get(DOC_SIDEBAR_STORE, null) || "list"
    );
    const next =
      DOC_SIDEBAR_SECTIONS[
        (index + step + DOC_SIDEBAR_SECTIONS.length) % DOC_SIDEBAR_SECTIONS.length
      ];
    showDocSidebarSection(next);
    strip.querySelector(`button[data-section="${next}"]`)?.focus();
  });
  showDocSidebarSection(prefs.get(DOC_SIDEBAR_STORE, null) || "list");
}

// --- documents wiring ---
//: The code panel's ways in (INBOX 788), each fetching documents-codekit.js
//: on its first press. `keep` reopens a tab without toggling it shut.
async function docCodeSideFrom(tab, keep = false) {
  if (!(await lazyScript("/js/documents-codekit.js"))) return toast("The code panel could not be loaded.", true, { action: ["Try again", () => docCodeSideFrom(tab, keep)] });
  if (keep) docCodeSideOpen(tab, { auto: true });
  else docCodeSideToggle(tab);
}
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
//: **The document changed, whichever surface it changed in.** Bound to the
//: fallback textarea's own `input` here and called straight by CodeMirror's
//: update listener once the view is mounted, so there is one pipeline rather
//: than one per engine.
function docSurfaceInput() {
  scheduleUndoBar();
  markDocDirty();
  scheduleDocPreview();
  //: Only the fallback's own column (DX1): the engine numbers its own lines,
  //: and every note box's gutter was redrawn per key typed here.
  if (!docCmView) renderDocGutter(docBoxEl());
}
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
// Both formatting toolbars, wired the same way. `data-md-target` on the
// toolbar names the textarea it drives, defaulting to the document editor so
// #doc-toolbar keeps working exactly as it did without carrying the
// attribute. The colour <select>s reset themselves after firing: they are
// action menus wearing a select, not a setting with a current value, so
// leaving "green" showing afterwards would claim a state that does not exist.
const MD_COLOURS = ["yellow", "green", "blue", "pink", "purple", "orange", "red", "grey"];

//: **A run** (INBOX 1403): `{{size=24 font=serif ink=red hl=yellow|words}}`, the
//: size, face, text colour and highlight of just those words, written in the
//: text itself like `==x==` so save, search, undo, export and the AI all read
//: it with no new column. The grammar is one alternative of `INLINE_MD` and
//: `INLINE_MD_LEGACY` (notes-list.js, at boot); what draws and edits it is
//: here, in the Library's scripts, out of the boot budget. Every value is
//: checked on the way out of the text (`mdRunParse`): a size is 8 to 200, a
//: face is one of `MD_RUN_FONTS` (the board's Font row builds from it), a
//: colour one of `MD_COLOURS`.
const MD_RUN = /\{\{((?:(?:size|font|ink|hl)=[a-z0-9]{1,12} ?){1,4})\|([^}\n]{1,2000}?)\}\}/;
const MD_RUN_FONTS = Object.freeze({
  serif: 'Georgia, "Iowan Old Style", "Times New Roman", serif',
  mono: 'ui-monospace, "Cascadia Code", "SF Mono", Consolas, "Liberation Mono", "DejaVu Sans Mono", monospace',
  wide: 'Verdana, "DejaVu Sans", Geneva, sans-serif',
  hand: '"Segoe Print", "Bradley Hand", "Chalkboard SE", "Comic Sans MS", cursive',
});

function mdRunParse(spec) {
  const out = {};
  for (const pair of String(spec).trim().split(/\s+/)) {
    const [key, value] = pair.split("=");
    if (key === "size" && /^\d{1,3}$/.test(value) && value >= 8 && value <= 200) out.size = Number(value);
    else if (key === "font" && Object.prototype.hasOwnProperty.call(MD_RUN_FONTS, value)) out.font = value;
    else if ((key === "ink" || key === "hl") && MD_COLOURS.includes(value)) out[key] = value;
  }
  return out;
}

//: The attributes as the text between `{{` and `|`, in one fixed order so the
//: same run is always the same characters.
function mdRunFormat(attrs) {
  return ["size", "font", "ink", "hl"].filter((key) => attrs[key] !== undefined && attrs[key] !== null).map((key) => `${key}=${attrs[key]}`).join(" ");
}

//: A run's element and the element its words go into, `[node, host]`. Classes
//: for the colours (the stylesheet has a theme-aware rule for each), CSSOM for
//: the size and face, never a `style` attribute (the CSP rejects one). A
//: highlight is a `<mark>`, whose own `color: inherit` would beat a text
//: colour on the same element, so the colour sits on a span inside it.
function mdRunNode(spec) {
  const attrs = mdRunParse(spec);
  const node = document.createElement(attrs.hl ? "mark" : "span");
  if (attrs.hl) node.classList.add("text-highlight", `text-highlight-${attrs.hl}`);
  if (attrs.size) node.style.fontSize = `${attrs.size}px`;
  if (attrs.font) node.style.fontFamily = MD_RUN_FONTS[attrs.font];
  if (!attrs.ink) return [node, node];
  const host = attrs.hl ? node.appendChild(document.createElement("span")) : node;
  host.classList.add("text-ink", `text-ink-${attrs.ink}`);
  return [node, host];
}

//: **A colour pick on text that is already coloured switches the colour.**
//: Reported: blue picked on yellow text "shows markdown" (`==blue|==x====`).
//: The mark around the selection, or the one the selection is exactly, is
//: replaced rather than wrapped again. Yellow is the highlight's default and
//: needs no prefix, so `==x==` says the same as `==yellow|x==`. Returns the
//: range to replace, its text and where the selection goes after.
function mdColourEdit(value, start, end, kind, colour) {
  const mark = kind === "ink" ? "++" : "==";
  const open = kind === "ink" ? `++${colour}|` : colour === "yellow" ? "==" : `==${colour}|`;
  const picked = value.slice(start, end);
  //: The marks on this line that the selection sits inside (or is): the whole
  //: mark takes the new colour, whatever part of its words was selected.
  const lineFrom = value.lastIndexOf("\n", start - 1) + 1;
  const lineTo = value.indexOf("\n", end) === -1 ? value.length : value.indexOf("\n", end);
  const marks = kind === "ink" ? /\+\+[a-z]+\|((?:(?!\+\+).)+)\+\+/g : /==(?:[a-z]+\|)?((?:(?!==).)+)==/g;
  const line = value.slice(lineFrom, lineTo);
  let hit;
  while ((hit = marks.exec(line)) !== null) {
    const from = lineFrom + hit.index;
    const to = from + hit[0].length;
    if (from <= start && end <= to) {
      return { from, to, insert: open + hit[1] + mark, selFrom: from + open.length, selTo: from + open.length + hit[1].length };
    }
  }
  const text = picked || (kind === "ink" ? "coloured text" : "highlighted");
  return { from: start, to: end, insert: open + text + mark, selFrom: start + open.length, selTo: start + open.length + text.length };
}

//: **The rest of the Obsidian toolbar, built once and mounted into both
//: editors.** Asked for by name (PKM-er/obsidian-editing-toolbar), for the
//: notes composer *and* the documents editor, "both in what tools are there,
//: and how they function".
//:
//: Rendered from a table rather than written into index.html twice, and that
//: is the whole point: the two toolbars were already hand-written markup that
//: happened to agree, and the note one was the shorter of the two by
//: accident of when it was added. One table means a command added here
//: appears in both, at the same size, in the same group, with the same
//: tooltip: which is the thing that actually stops them drifting.
//:
//: One `<details>` menu is left ("More": the three inline styles with no
//: row in the "/" catalogue), worded like the Highlight menu beside it. Headings
//: 4 to 6, quotes, code, tables, callouts, links, images, footnotes and
//: comments are the "Insert" button's, which opens the "/" menu (DX6): one
//: catalogue, `editorBlockRows`, instead of a menu of this table's own for each.
const EDITOR_TOOLBAR_MENUS = [
  {
    id: "inline",
    icon: "ph:text-underline",
    label: "More",
    title: "Underline, superscript and subscript",
    items: [
      ["underline", "Underline"],
      ["sup", "Superscript"],
      ["sub", "Subscript"],
    ],
  },
];

//: The buttons that stay on the row, because they are reached mid-sentence
//: and a menu costs a click every time. Obsidian's own default set makes the
//: same split.
const EDITOR_TOOLBAR_BUTTONS = [
  { md: "outdent", icon: "ph:text-outdent", title: "Outdent" },
  { md: "indent", icon: "ph:text-indent", title: "Indent" },
  { md: "undo", icon: "ph:arrow-counter-clockwise", title: "Undo (Ctrl+Z)" },
  { md: "redo", icon: "ph:arrow-clockwise", title: "Redo (Ctrl+Shift+Z)" },
];

function mountEditorToolbarExtras(bar) {
  //: Idempotent: `initMarkdownToolbars` can run again (the note edit form
  //: builds its own bar per edit), and a second mount would double every
  //: control. Marked on the element rather than tracked in a set, so a bar
  //: that is rebuilt from scratch is correctly treated as new.
  if (bar.dataset.mdExtras === "1") return;
  bar.dataset.mdExtras = "1";
  const sep = () => {
    const el = document.createElement("span");
    el.className = "doc-toolbar-sep";
    el.dataset.mdExtra = "1";
    el.setAttribute("aria-hidden", "true");
    return el;
  };
  bar.appendChild(sep());
  //: **A pair is one flex item.** Undo and redo (and outdent and indent) are
  //: one decision; the strip wraps between items, and at 1440 it wrapped
  //: between Undo and Redo, leaving Redo alone at the start of row two.
  let pair = null;
  for (const spec of EDITOR_TOOLBAR_BUTTONS) {
    if (!pair || pair.children.length > 1) {
      pair = document.createElement("span");
      pair.className = "doc-toolbar-pair";
      pair.setAttribute("role", "group");
      pair.dataset.mdExtra = "1";
      bar.appendChild(pair);
    }
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.md = spec.md;
    button.dataset.mdExtra = "1";
    button.title = spec.title;
    button.setAttribute("aria-label", spec.title);
    setLabel(button, spec.icon);
    pair.appendChild(button);
  }
  //: A strip without its own Insert (the notes' two) gets the same button.
  if (!bar.querySelector('[data-md="insert"]')) {
    const insert = document.createElement("button");
    insert.type = "button";
    insert.dataset.md = "insert";
    insert.dataset.mdExtra = "1";
    insert.title = "Insert a block, image, link, table, diagram, emoji or equation (or press /)";
    setLabel(insert, "ph:plus Insert");
    bar.appendChild(insert);
  }
  for (const menu of EDITOR_TOOLBAR_MENUS) {
    //: The document strip carries these rows in its Style menu already.
    if (bar.querySelector(`[data-md="${menu.items[0][0]}"]`)) continue;
    const details = document.createElement("details");
    details.className = "doc-dock-menu doc-toolbar-menu";
    details.dataset.mdExtra = "1";
    //: **Drawn exactly like the two menus written in the markup.** These were
    //: built with different classes and an icon *plus a word*, "Heading",
    //: "Block", "More", "Insert", sitting in a row where every other control
    //: is a glyph. Four labelled chips among twenty icons is what makes a
    //: toolbar read as assembled rather than designed, and it is the same
    //: "two implementations of one control" shape this project keeps paying
    //: for. The name lives in the tooltip and the ARIA label, where the
    //: markup's own menus already keep theirs.
    const summary = document.createElement("summary");
    summary.className = "doc-dock-menu-btn doc-toolbar-menu-btn";
    summary.title = menu.title;
    summary.setAttribute("aria-label", `${menu.label}: ${menu.title}`);
    setLabel(summary, `${menu.icon} ${menu.label}`);
    const caret = document.createElement("i");
    caret.className = "ph ph-caret-down doc-toolbar-menu-caret";
    caret.setAttribute("aria-hidden", "true");
    summary.appendChild(caret);
    const body = document.createElement("div");
    body.className = "doc-dock-menu-list";
    for (const [md, label] of menu.items) {
      const button = document.createElement("button");
      button.type = "button";
      //: The one menu-row recipe, shared with the chat's kebab (`.menu-item`,
      //: 02-chat-graph.css) -- see the comment on `.doc-dock-menu-list`.
      button.className = "menu-item doc-dock-menu-item";
      button.dataset.md = md;
      button.textContent = label;
      body.appendChild(button);
    }
    details.append(summary, body);
    bar.appendChild(details);
  }
}

//: Wire one formatting strip to its textarea: mount the shared extras
//: (Block menu, colours, …), then every `button[data-md]` and colour
//: select. Split out of `initMarkdownToolbars` so the note edit form can
//: clone the capture strip and wire the clone (app.js `noteEditToolbar`).
//: Everything the mount appends is marked `data-md-extra` so a clone can
//: drop the stale copies and mount fresh ones with live listeners.
function wireMarkdownToolbar(bar) {
  const boxId = bar.dataset.mdTarget || "doc-content";
  mountEditorToolbarExtras(bar);
  wireToolbarRoving(bar);
  //: **Delegated, not one listener per button.** The dropdown menus are
  //: built by the mount above and, in the note edit form, the whole strip
  //: is a *clone*: so per-button listeners covered whatever existed at
  //: wiring time and silently missed anything a menu created later
  //: (reported: "none of the toolbar dropdowns work" in the edit form; a
  //: browser check confirmed a Block-menu item changed nothing). One
  //: listener on the bar cannot miss a descendant.
  bar.addEventListener("mousedown", (event) => {
    // Keeps the caret in the textarea: a click moves focus first and the
    // selection the action is about to act on is already gone.
    if (event.target.closest("button[data-md]")) event.preventDefault();
  });
  bar.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-md]");
    if (!button || !bar.contains(button)) return;
    applyMarkdown(button.dataset.md, boxId);
    //: A menu row is finished once chosen (dogfood item 15).
    const menu = button.closest("details.doc-toolbar-menu");
    if (menu) menu.open = false;
  });
  for (const select of bar.querySelectorAll("select[data-md-colour]")) {
    const kind = select.dataset.mdColour;
    //: A cloned strip (the note edit form) brings the source's options along.
    for (const old of [...select.options]) if (old.value) old.remove();
    for (const colour of MD_COLOURS) {
      const option = document.createElement("option");
      option.value = colour;
      option.textContent = colour[0].toUpperCase() + colour.slice(1);
      select.appendChild(option);
    }
    select.addEventListener("change", () => {
      const colour = select.value;
      select.value = "";
      if (!colour) return;
      const box = docSurfaceById(boxId);
      if (!box) return;
      const edit = mdColourEdit(box.value, box.selectionStart, box.selectionEnd, kind, colour);
      if (typeof box.replaceRange === "function") box.replaceRange(edit.from, edit.to, edit.insert);
      else box.value = box.value.slice(0, edit.from) + edit.insert + box.value.slice(edit.to);
      box.setSelectionRange(edit.selFrom, edit.selTo);
      finishMarkdownEdit(box, boxId);
    });
  }
}

//: **Ctrl+B / Ctrl+I / Ctrl+Shift+S, in the two note editors too.**
//:
//: Reported alongside the missing strikethrough chord itself: both toolbar
//: buttons have carried "Bold (Ctrl+B)"/"Italic (Ctrl+I)" tooltips since
//: `noteEditToolbar` cloned this strip's markup for the note editors, but
//: neither note editor ever actually wired the keys, the tooltip named a
//: shortcut only `#doc-content`'s own handler (above this function) had.
//:
//: Not folded into that handler and shared: it also owns Tab-indent,
//: Ctrl+/ comments, Ctrl+1..3 headings and Ctrl+F find, none of which a
//: three-row note field has any use for, and giving it a second caller
//: would mean guarding every one of those behind a "is this really
//: #doc-content" check. This is the three chords the note editors and the
//: document editor genuinely share, kept as one small function so the
//: shifted-S-before-plain-S ordering (see that handler's own comment)
//: exists in exactly one place rather than two copies that could drift.
//:
//: Idempotent via `dataset.mdFormatShortcuts`: `#entry-content` is wired
//: once, at page load, but the note edit form's textarea is a fresh
//: element every time a note is opened for editing, and calling this again
//: on the *same* element (a note re-opened for editing without a full
//: reload) must not stack a second listener that fires the same keydown
//: twice.
//: Takes the element itself, not only its id: `renderEditForm` (note-edit-panels.js)
//: builds the note edit form's textarea and wires this before appending it
//: to the document, where `$(id)` (`document.getElementById`) would find
//: nothing yet. `#entry-content` is already in the page at boot, so the
//: capture box still just passes its id string.
function wireMdFormatShortcuts(boxOrId) {
  const box = typeof boxOrId === "string" ? $(boxOrId) : boxOrId;
  if (!box || box.dataset.mdFormatShortcuts) return;
  const boxId = box.id;
  box.dataset.mdFormatShortcuts = "1";
  box.addEventListener("keydown", (event) => {
    if (!(event.ctrlKey || event.metaKey)) return;
    const key = event.key.toLowerCase();
    if (key === "s" && event.shiftKey) {
      event.preventDefault();
      wrapDocSelection("~~", "struck through", boxId);
    } else if (key === "b") {
      event.preventDefault();
      wrapDocSelection("**", "bold text", boxId);
    } else if (key === "i") {
      event.preventDefault();
      wrapDocSelection("*", "italic text", boxId);
    }
  });
}
window.wireMdFormatShortcuts = wireMdFormatShortcuts;

//: **The phone bar's "/" button** (DOCUMENTS_PLAN Phase 6 item 1). The six
//: buttons beside it are `data-md` and need no code at all; this one has to
//: type the character, because the slash menu is `editor.js`'s and it opens
//: off what the writer typed rather than off a call: `editorTokenAt` wants a
//: "/" with whitespace or a line start in front of it, and every other way in
//: (calling `editorOpenMenu` directly) would leave the menu open over a
//: document with no "/" in it to remove when an item runs.
//:
//: Through `docReplaceRange`, which is the engine's own transaction, so the
//: update listener calls `editorHandleInput` exactly as it does for a typed
//: character; on the fallback textarea the same helper goes through
//: `execCommand` and `finishMarkdownEdit` raises the `input` event editor.js
//: listens for.
function openDocPhoneInsert() {
  const box = docSurfaceById("doc-content");
  if (!box) return;
  box.focus();
  const { selectionStart: start, selectionEnd: end, value } = box;
  const before = start === 0 ? "\n" : value[start - 1];
  const insert = /\s/.test(before) ? "/" : " /";
  docReplaceRange(box, start, end, insert);
  box.setSelectionRange(start + insert.length, start + insert.length);
  finishMarkdownEdit(box, "doc-content");
  //: And then again, by hand, because of *when* the engine reports a change.
  //: `docCmUpdate` calls `editorHandleInput` while the transaction that
  //: inserted the "/" is still the current update, and the caret is then
  //: still in front of it: `editorTokenAt` looks only at the text before the
  //: selection, finds no slash, and the menu never opens. Measured: the
  //: character landed and nothing happened. The caret is set above, so this
  //: second call is the one that has a token to find.
  if (typeof editorHandleInput === "function") editorHandleInput(box);
}

$("doc-phone-insert").addEventListener("click", openDocPhoneInsert);
$("doc-phone-turn").addEventListener("click", (event) => docTurnIntoMenu("doc-content", event.currentTarget));

// NOTE-SURFACE-BEGIN
//: =========================================================================
//: One editor everywhere (DOCUMENTS_PLAN Phase 8)
//: =========================================================================
//:
//: The owner: "anywhere there is a note related capture, edit or view area
//: with a text box to integrate features similar to the documents upgrade.
//: The editors need to be consistent in form and function." Before this, five
//: note editors had five feature sets, and only the document had the engine.
//:
//: **The textarea stays.** It is the form's value carrier, the thing every
//: existing handler, save path and test holds, and the fallback if the bundle
//: never loads. What changes is that a CodeMirror view is mounted beside it
//: and the two are kept in step in both directions: the view's text is
//: mirrored into the textarea (with an `input` event, because the draft save,
//: the character count and the autosize all hang off one), and a script that
//: writes `box.value` is pushed back into the view through an own-property
//: setter on that one element. Without that second direction a note saved
//: from the capture box would clear the textarea and leave the words on
//: screen.
//:
//: **The textarea is not hidden, it is laid over the view at zero opacity.**
//: `display: none` would have been simpler and wrong in two ways that only a
//: browser shows: `setSelectionRange` on an unrendered textarea is a no-op in
//: some engines, and every popup that positions itself off the textarea's own
//: rectangle (app.js's `[[` suggest is the one that matters) would open at
//: 0,0. Laid over the view, its rectangle is the editor's rectangle and its
//: selection is real.
//:
//: **Mounted on the first focus**, once per element: a capture box that
//: nobody clicks costs nothing, and the bundle is fetched once per page
//: whichever surface asks for it first.
const NOTE_SURFACE_DEFAULTS = { size: "box", live: true };

//: The note editors, by the id of their textarea. A table rather than a call
//: at each site, because three of these boxes are built in script in another
//: file and a delegated focus listener reaches those the same way it reaches
//: the ones in the page. `tests/test_note_surface.py` is the lint that a note
//: textarea is in here.
const NOTE_SURFACES = {
  //: Capture, the most used text box in the app.
  "entry-content": { size: "box", live: true },
  //: The note edit form (`renderEditForm`), rebuilt per edit, which is why
  //: the listener is delegated rather than bound at boot.
  "entry-edit-content": { size: "inline", live: true },
  //: The graph's own two note boxes (Phase 8b): the node popup's editor and
  //: the new-note box beside it. Both are note text, and both had a bare
  //: textarea.
  "graph-popup-content": { size: "box", live: true },
  "graph-new-content": { size: "box", live: true },
  //: Write with the AI (Phase 8b). The draft is note text and gets Live; the
  //: thoughts pane above it is a scratch pad for what you want to say, so it
  //: gets the engine (undo, the "/" menu, one behaviour) without the
  //: rendering, which is the plan's own split.
  "draft-text": { size: "box", live: true },
  "draft-thoughts": { size: "box", live: false },
  //: A concept map card's text (Phase 8c, the board half), opened by
  //: `wbEditNodeText` in whiteboard.js. It is a single idea, so Enter
  //: commits and Escape abandons: the card hands those in as
  //: `host.noteSurfaceKeys`, which go ahead of every other chord here.
  "wb-card-editor": { size: "inline", live: true },
};

//: element -> view. Weak, because the edit form's textarea is thrown away and
//: rebuilt on every edit and a strong map would hold every one of them.
const noteSurfaceViews = new WeakMap();
let noteSurfaceMirroring = false;

//: The surface for a note editor, given its textarea or any node inside its
//: view. Null for anything that has not mounted, which is what keeps
//: `asSurface` falling back to the textarea adapter.
function noteSurfaceFor(box) {
  if (!box) return null;
  if (box instanceof HTMLTextAreaElement) {
    const view = noteSurfaceViews.get(box);
    return view ? cmSurface(view, noteSurfaceMeta(box)) : null;
  }
  if (box instanceof Node && box.nodeType === 1 && box.closest) {
    const wrap = box.closest(".note-surface");
    if (wrap && wrap.noteSurfaceHost) return noteSurfaceFor(wrap.noteSurfaceHost);
  }
  return null;
}

//: Built once per host and kept on the element, so `cmSurface`'s own cache
//: (keyed by the view) never sees two different identities for one view.
function noteSurfaceMeta(host) {
  if (!host.noteSurfaceMeta) {
    host.noteSurfaceMeta = { id: host.id, changeHandlers: [] };
  }
  return host.noteSurfaceMeta;
}

//: What the engine gives a note box. Deliberately smaller than the document's
//: set: no gutter, no folding, no find panel, no autosave, no typewriter.
//: What it shares is everything the owner's "consistent in form and function"
//: is about, the Live decorations, the markdown grammar, undo, the selection,
//: and this app's own theme and chords.
function noteSurfaceExtensions(CM, host, options) {
  //: **Live or Source, one box** (INBOX 430, the owner: "note forms use the
  //: live view with a source toggle, no Preview"). The rendering and the
  //: grammar sit in a compartment of their own, so the strip's Source button
  //: swaps them out for the plain markdown and back without a remount, the
  //: text and the caret untouched (`setNoteSurfaceSource`).
  const live = options.live ? [docLiveExtensions(CM), noteGrammarPlugin(CM)] : [];
  host.noteLiveSlot = new CM.state.Compartment();
  host.noteLiveExtensions = live;
  //: **`box.readOnly = true` from script has to reach the editor** (the Write
  //: with AI desk sets it while a pass streams into the draft; measured, a
  //: person could type into the mounted editor throughout, because the flag
  //: only ever lived on the hidden textarea). A compartment of its own, driven
  //: by the own `readOnly` accessor `noteSurfaceOwnValue` installs. Script
  //: writes (`box.value = ...`, the stream itself) still go through: a view's
  //: `readOnly` only refuses the person's input.
  host.noteReadOnlyExtensions = (on) => (on ? [CM.state.EditorState.readOnly.of(true), CM.view.EditorView.editable.of(false)] : []);
  host.noteReadOnlySlot = new CM.state.Compartment();
  return [
    host.noteReadOnlySlot.of(host.noteReadOnlyExtensions(host.readOnly)),
    //: The same whole-line copy and cut the document has (INBOX 652).
    CM.state.Prec.high(docLineClipboardExtension(CM)),
    //: Bullets that do not nest when retyped, fences that close at their own
    //: indent, Enter on an empty item ending the list (dogfood round 1).
    docListFenceExtensions(CM, false),
    //: Grammar rides with the rendering: the note's own list (PROSE-TOOLS,
    //: `noteGrammarPlugin`).
    host.noteLiveSlot.of(noteSourceWanted() && NOTE_SOURCE_HOSTS.has(host.id) ? [] : live),
    (host.noteGutterSlot = new CM.state.Compartment()).of(noteSurfaceGutter(CM, host)),
    //: **No findings plugin here, and that is the option the plan names
    //: rather than an omission.** `docProseFound` is the *document's* list of
    //: prose findings, at the document's offsets; drawn over a note it would
    //: underline whatever words happened to sit at those positions. The
    //: checker for note text is its own piece of work (Phase 8's `findings`
    //: option), not a plugin reused at the wrong offsets.
    CM.view.EditorView.lineWrapping,
    //: The GitHub dialect, the same call the document makes: `markdown()`
    //: alone is commonmark and every tree-based decoration (bold, headings,
    //: task boxes) would silently draw nothing.
    docCmLanguageFor(CM, "md"),
    CM.view.highlightSpecialChars(),
    CM.commands.history(),
    CM.view.drawSelection(),
    CM.view.dropCursor(),
    CM.language.indentOnInput(),
    CM.language.syntaxHighlighting(CM.language.defaultHighlightStyle, { fallback: true }),
    CM.language.bracketMatching(),
    docCmTheme(CM),
    docCmHighlight(CM),
    CM.view.placeholder(host.placeholder || ""),
    //: This app's chords first, so Ctrl+B is bold in a note for the same
    //: reason it is bold in a document.
    docRedoChord(CM),
    CM.view.keymap.of([
      //: The host's own keys first (Phase 8c): a box whose Enter means "done"
      //: says so on the element, and a table row cannot carry a closure over
      //: the one card being edited.
      ...(Array.isArray(host.noteSurfaceKeys) ? host.noteSurfaceKeys : []),
      ...noteSurfaceKeymap(host),
      ...CM.commands.historyKeymap,
      ...CM.commands.defaultKeymap,
    ]),
    CM.view.EditorView.updateListener.of((update) => noteSurfaceUpdate(host, update)),
    CM.view.EditorView.contentAttributes.of({ "aria-label": noteSurfaceName(host) }),
  ];
}

//: **The box keeps its name** (WCAG 4.1.2, INBOX 433). The view is mounted
//: over a labelled textarea and hides it, and the editable it puts in its
//: place had no name: a screen reader said "edit text" in Capture, the edit
//: form and every other note box. The name is the textarea's own, in the
//: order a browser would compute it.
function noteSurfaceName(host) {
  const labelled = host.getAttribute("aria-labelledby");
  const byId = labelled ? labelled.split(/\s+/).map((id) => document.getElementById(id)?.textContent.trim()).filter(Boolean).join(" ") : "";
  const forLabel = host.id ? document.querySelector(`label[for="${CSS.escape(host.id)}"]`)?.textContent.trim() : "";
  //: A placeholder is the last resort, and only its first line: Capture's runs
  //: to three lines of tips, which is not a name.
  return byId || host.getAttribute("aria-label") || forLabel || host.title || (host.placeholder || "").split("\n")[0].trim() || "Note text";
}

//: **The document's chords, aimed at this box.** `docCmKeymap` cannot be
//: reused as it is: every one of its entries is written against
//: `doc-content`, so Ctrl+B in a note would have emboldened a word in
//: whatever document was last open, and Ctrl+S would have saved it. The
//: helpers underneath all take a box id or a surface already, so this is the
//: same four actions with this box named. Ctrl+S and Ctrl+F are deliberately
//: absent: a note has no find panel and saving one is the form's business,
//: which the app's own global chord already handles.
function noteSurfaceKeymap(host) {
  const surface = () => noteSurfaceFor(host) || textareaSurface(host);
  return [
    //: **Ctrl+/ is the blocks menu in a note** (INBOX 402 kept it that way:
    //: only the document editor answers it with the comment toggle). The
    //: engine's `defaultKeymap` binds it to its own comment toggle, which in
    //: a markdown note wrote `<!--  -->` where the menu should have opened
    //: (measured, `slashicons.js`). Answered here, before that keymap, by
    //: the same function the app's shortcut runs.
    {
      key: "Mod-/",
      run: () => (typeof editorOpenMenuByShortcut === "function" ? editorOpenMenuByShortcut() : false),
    },
    {
      key: "Tab",
      run: () => {
        indentDocSelection(surface(), false);
        return true;
      },
    },
    {
      key: "Shift-Tab",
      run: () => {
        if (!docCanOutdent(surface())) return false;
        indentDocSelection(surface(), true);
        return true;
      },
    },
    //: **Ctrl+Enter is the box's own "done"** (INBOX 432). Every note box
    //: that has one (capture saves, the thoughts pane drafts, the edit form
    //: saves) listens for it on its textarea, and the textarea stops
    //: hearing keys the moment this view is mounted over it: measured in
    //: Chromium, Ctrl+Enter in the capture box saved nothing and the
    //: engine's own binding inserted a blank line. So the chord is handed
    //: back to the textarea as the same event, and answered here only when a
    //: listener there took it.
    {
      key: "Mod-Enter",
      run: () => {
        const mac = /Mac|iP(hone|ad)/.test(navigator.platform || "");
        const forwarded = new KeyboardEvent("keydown", {
          key: "Enter",
          ctrlKey: !mac,
          metaKey: mac,
          bubbles: true,
          cancelable: true,
        });
        host.dispatchEvent(forwarded);
        return forwarded.defaultPrevented;
      },
    },
    { key: "Mod-b", run: () => { wrapDocSelection("**", "bold text", host.id); return true; } },
    { key: "Mod-i", run: () => { wrapDocSelection("*", "italic text", host.id); return true; } },
    { key: "Mod-e", run: () => { wrapDocSelection("`", "", host.id); return true; } },
    { key: "Mod-Shift-s", run: () => { wrapDocSelection("~~", "struck through", host.id); return true; } },
    { key: "Mod-1", run: () => { applyMarkdown("h1", host.id); return true; } },
    { key: "Mod-2", run: () => { applyMarkdown("h2", host.id); return true; } },
    { key: "Mod-3", run: () => { applyMarkdown("h3", host.id); return true; } },
    ...docCmKeymap.insert((kind) => { applyMarkdown(kind, host.id); return true; }),
    //: No Ctrl+/ here: in a note it is the blocks menu (the registry's
    //: `editorMenu`), and a comment toggle bound here as well wrapped the
    //: line in the *document's* comment marker before the menu wrote "/"
    //: over it (INBOX 402).
  ];
}

//: The Source choice is one for every note box, remembered: a person who
//: writes in raw markdown wants it in the edit form as much as in Capture.
const NOTE_SOURCE_KEY = "note-source-view";
//: **Only the boxes that carry the Source toggle** (INBOX 447, the owner:
//: "i dont think the md is rendered at all in the graph popups"). Source
//: pressed once in Capture was remembered for every note box, so the graph
//: popup, which has no toggle to press back, showed raw `**` and
//: `![...](...)` for good. A box without the toggle always renders.
const NOTE_SOURCE_HOSTS = new Set(["entry-content", "entry-edit-content"]);

function noteSourceWanted() {
  try {
    return prefs.get(NOTE_SOURCE_KEY, null) === "1";
  } catch {
    return false;
  }
}

//: Swap one mounted box between Live and Source. Answers whether it could.
function setNoteSurfaceSource(host, source) {
  const view = noteSurfaceViews.get(host);
  if (!view || !host.noteLiveSlot) return false;
  view.dispatch({ effects: host.noteLiveSlot.reconfigure(source ? [] : host.noteLiveExtensions || []) });
  return true;
}

//: The view changed: mirror it out, and run the pipelines a typed character
//: would have run in the textarea.
function noteSurfaceUpdate(host, update) {
  const view = update.view;
  if (update.docChanged || update.selectionSet) noteSurfaceMirror(host, view, update.docChanged);
  if (!update.docChanged) return;
  const surface = noteSurfaceFor(host);
  const meta = noteSurfaceMeta(host);
  for (const fn of meta.changeHandlers) fn();
  //: editor.js hangs "/" and `[[` off a DOM `input` event, which the engine
  //: never raises for a typed character (the same call `docCmUpdate` makes
  //: for the document, and for the same reason).
  if (typeof editorHandleInput === "function") editorHandleInput(surface);
  //: Autocorrect (autocorrect.js, Brief 94) hears a typed change as an event,
  //: a microtask later: it may dispatch, which an update in progress refuses.
  if (update.transactions.some((tr) => tr.isUserEvent("input.type"))) {
    queueMicrotask(() => host.dispatchEvent(new CustomEvent("note-typed", { bubbles: true, detail: surface })));
  }
}

//: **The hidden textarea is written once typing pauses, not on every key**
//: (the owner, 2026-10-12: backspace and delete lag in a long note). Writing a
//: textarea's value makes the browser rebuild its inner text, a text node and a
//: <br> per line, and restyle them: 10,962 <br> insertions and 141 restyles of
//: 1,764 elements in 25 Backspaces of a 1500-word note, every stack ending in
//: that write. Reads of `value` and the selection come live from the view
//: (`noteSurfaceOwnValue`), so the `input` event below sees the same text; the
//: textarea itself is brought level `NOTE_MIRROR_MS` after the last change, or
//: at once if something calls into it (`noteMirrorFlush`).
const NOTE_MIRROR_MS = 250;
function noteSurfaceMirror(host, view, docChanged) {
  host.noteMirrorStale = true;
  clearTimeout(host.noteMirrorTimer);
  host.noteMirrorTimer = setTimeout(() => host.noteMirrorFlush?.(), NOTE_MIRROR_MS);
  //: A script's own `box.value = ...` already told everyone; only a change
  //: made in the view raises the event.
  if (!docChanged || host.noteSettingValue) return;
  noteSurfaceMirroring = true;
  try {
    host.dispatchEvent(new Event("input", { bubbles: true }));
  } finally {
    noteSurfaceMirroring = false;
  }
}

//: What brings the textarea level with the view, and keeps anything that
//: reaches into the textarea itself from finding it behind.
function noteSurfaceMirrorTools(host, view, valueProto) {
  const nativeRange = HTMLTextAreaElement.prototype.setSelectionRange;
  host.noteMirrorStale = false;
  host.noteMirrorFlush = () => {
    clearTimeout(host.noteMirrorTimer);
    if (!host.noteMirrorStale) return;
    host.noteMirrorStale = false;
    const text = docStr(view.state.doc);
    const range = view.state.selection.main;
    noteSurfaceMirroring = true;
    try {
      valueProto.set.call(host, text);
      //: Some engines refuse a selection on a box that is not rendered, and a
      //: refusal is not a reason to drop the text.
      nativeRange.call(host, Math.min(range.from, text.length), Math.min(range.to, text.length));
    } catch (error) {
      // The text is in; the caret there is the view's to keep.
    } finally {
      noteSurfaceMirroring = false;
    }
  };
  for (const name of ["setRangeText", "select"]) {
    const native = HTMLTextAreaElement.prototype[name];
    host[name] = function mirrored(...args) {
      host.noteMirrorFlush();
      return native.apply(this, args);
    };
  }
}

//: The other direction: `box.value = ""` from script (a note saved, a draft
//: loaded, a template applied) has to reach the view, and assigning to
//: `.value` raises no event anyone can listen for. An own property on this
//: one element, wrapping the prototype's own accessors, is the only hook the
//: platform offers; it is installed at mount and leaves every other textarea
//: in the app untouched.
function noteSurfaceOwnValue(host, view) {
  const proto = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value");
  if (!proto || !proto.set) return;
  noteSurfaceMirrorTools(host, view, proto);
  Object.defineProperty(host, "value", {
    configurable: true,
    //: Live: the textarea behind it is only brought level once typing pauses.
    get() {
      return docStr(view.state.doc);
    },
    set(next) {
      proto.set.call(this, next);
      host.noteMirrorStale = false;
      if (noteSurfaceMirroring) return;
      const current = docStr(view.state.doc);
      if (next === current) return;
      host.noteSettingValue = true;
      try {
        view.dispatch({ changes: { from: 0, to: current.length, insert: String(next) } });
      } finally {
        host.noteSettingValue = false;
      }
    },
  });
  //: **And the selection, which is the half that looks like it works.**
  //: `box.setSelectionRange(6, 11)` then "make that bold" is how several
  //: callers here select a word before acting on it (the shared toolbar
  //: table, "improve this", the note sweeps). Written on the textarea alone
  //: it moves a selection nobody can see, and the action then runs against
  //: whatever the *view's* caret happened to be: measured, bold arrived at
  //: position 0 with its placeholder text instead of around the word.
  const setRange = host.setSelectionRange.bind(host);
  host.setSelectionRange = (from, to, direction) => {
    host.noteMirrorFlush();
    setRange(from, to, direction);
    if (noteSurfaceMirroring) return;
    const length = view.state.doc.length;
    const anchor = Math.max(0, Math.min(Number(from) || 0, length));
    const head = Math.max(0, Math.min(Number(to == null ? from : to) || 0, length));
    view.dispatch({ selection: { anchor, head } });
  };
  for (const name of ["selectionStart", "selectionEnd"]) {
    const own = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, name);
    if (!own || !own.set) continue;
    const native = (key) => Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, key).get.call(host);
    Object.defineProperty(host, name, {
      configurable: true,
      //: Live from the view's caret, as the value is.
      get() {
        const range = view.state.selection.main;
        return name === "selectionStart" ? range.from : range.to;
      },
      set(at) {
        host.noteMirrorFlush();
        own.set.call(this, at);
        if (noteSurfaceMirroring) return;
        host.setSelectionRange(native("selectionStart"), native("selectionEnd"));
      },
    });
  }
  //: And `box.readOnly`, for the same reason as `value`: the flag is the
  //: textarea's, the person types into the view.
  const readOnlyProto = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "readOnly");
  if (readOnlyProto && readOnlyProto.set && host.noteReadOnlySlot) {
    Object.defineProperty(host, "readOnly", {
      configurable: true,
      get() {
        return readOnlyProto.get.call(this);
      },
      set(on) {
        readOnlyProto.set.call(this, on);
        view.dispatch({ effects: host.noteReadOnlySlot.reconfigure(host.noteReadOnlyExtensions(Boolean(on))) });
      },
    });
  }
  //: And `box.focus()`, which a dozen call sites use to put the caret in a
  //: note box: the textarea is invisible and would take the keystrokes.
  const focus = host.focus.bind(host);
  host.focus = (...args) => {
    if (noteSurfaceViews.has(host)) view.focus();
    else focus(...args);
  };
}

//: Mount the engine for one note textarea. Returns the surface, or the
//: textarea's own surface if the bundle is not available: every caller can
//: carry on either way, which is the whole point of the adapter.
async function mountNoteSurface(host, options = {}) {
  if (!host || noteSurfaceViews.has(host)) return noteSurfaceFor(host) || textareaSurface(host);
  if (docCmBroken) return textareaSurface(host);
  const settings = { ...NOTE_SURFACE_DEFAULTS, ...options };
  let CM = null;
  try {
    CM = await loadCodeMirror();
  } catch (error) {
    return textareaSurface(host);
  }
  if (!CM || noteSurfaceViews.has(host)) return noteSurfaceFor(host) || textareaSurface(host);
  //: **The box can be gone by the time the editor has loaded.** A board
  //: card's editor closed with Escape while CodeMirror was still loading
  //: (measured at 390 under load, cardarrows sweep) left `host.parentNode`
  //: null and threw at the `insertBefore` below.
  if (!host.parentNode) return textareaSurface(host);
  //: Read before the wrapper below moves the textarea: moving a focused
  //: element in the DOM blurs it, so by the time the view exists the answer
  //: is always "no".
  const hadFocus = document.activeElement === host;
  //: **A box its own layout was stretching has to go on being stretched, and
  //: the wrapper is what the layout can see now** (INBOX 240, the owner: "when
  //: I clicked on the 'your thoughts' text box in the write with ai notes
  //: subtab, the box instantly shortened in height from what it was. same with
  //: the 'the draft' textbox as well").
  //:
  //: Measured on :8802 with `scratchpad/ui-sweeps/draftboxes.js`: both Writing
  //: Room boxes were 330.3px tall and came back 146px on the first focus, a
  //: loss of 184.3px each. Nothing shrank them. `.draft-column` is a flex
  //: column and `.draft-column textarea` is `flex: 1 1 auto`, so the box was
  //: taking the column's slack; one line below, the textarea is no longer a
  //: child of the column at all, this wrapper is, and a `div` with no flex
  //: declaration is `flex: 0 1 auto`, i.e. as tall as its content, which is
  //: `.note-surface-box`'s own `min-height: 9rem` (144px) plus the padding.
  //:
  //: So the wrapper takes the role rather than the number: a host that was a
  //: growing item of a flex parent hands that over, and the stretch rules in
  //: 09-editor.css let the editor fill the height instead of capping it. Read
  //: before the move, because one line later the parent is this wrapper.
  //: General rather than a `#draft-thoughts` rule: every note box in
  //: `NOTE_SURFACES` is somewhere a layout may stretch, and the next one added
  //: would hit this the same way with nothing to warn it.
  const hostStyle = getComputedStyle(host);
  const parent = host.parentNode;
  const parentStyle = parent instanceof Element ? getComputedStyle(parent) : null;
  const stretched =
    !!parentStyle &&
    (parentStyle.display === "flex" || parentStyle.display === "inline-flex") &&
    Number(hostStyle.flexGrow) > 0;
  const wrap = document.createElement("div");
  wrap.className = `note-surface note-surface-${settings.size}${stretched ? " note-surface-stretch" : ""}`;
  //: **And the floor moves with it.** A stretching item is only as tall as the
  //: row lets it be, and what stops the row itself collapsing is the box's own
  //: `min-height` (`.draft-column textarea` declares 11rem, "the floor is four
  //: lines"). Left behind on the invisible mirror, the stretch rules made
  //: things worse rather than better: measured with the class and without this
  //: line, the draft column fell from 477.8px to 179.9 and its box to 42,
  //: because nothing in the column had an intrinsic height any more. Carried
  //: as an inline length because it is this box's number, not a rule anything
  //: else should inherit.
  //:
  //: **And the height it was already drawn at is the basis, not a fresh
  //: guess.** `flex: 1 1 auto` sizes an item from its content, and a textarea's
  //: content height is its `rows` attribute (7 and 14 here, 189.2px and
  //: 330.3px measured); an editor view has no such thing, so the row it is in
  //: has nothing to be tall for. With the class and the floor alone the draft
  //: column still fell from 477.8px to 314 and its box to 176, the floor
  //: exactly. Handing the wrapper the host's own measured height as its
  //: `flex-basis` is what carries the `rows` across: the item asks the row for
  //: the height it already had, and grows or shrinks from there like any other.
  if (stretched) {
    const drawn = host.getBoundingClientRect().height;
    if (drawn > 0) wrap.style.flexBasis = `${Math.round(drawn)}px`;
    const floor = Number.parseFloat(hostStyle.minHeight);
    if (Number.isFinite(floor) && floor > 0) wrap.style.minHeight = `${floor}px`;
  }
  wrap.noteSurfaceHost = host;
  host.parentNode.insertBefore(wrap, host);
  wrap.appendChild(host);
  host.classList.add("note-surface-mirror");
  //: The stylesheet sizes the mirror to the view; a height `autoGrow` wrote
  //: before the mount would override it, and `autoGrow` leaves a mirror alone
  //: from now on (INBOX 424i), so the old one would otherwise stay for good.
  host.style.height = "";
  host.setAttribute("tabindex", "-1");
  host.setAttribute("aria-hidden", "true");
  //: **Seeded here, not at the focus that asked for the mount.** The bundle
  //: takes a moment on the first box of a page, and a person who clicks a
  //: capture box types into it immediately: those characters go into the
  //: textarea, and both the text *and* the caret have moved by the time this
  //: runs. Reading them now is what keeps them. Measured with the caret taken
  //: at focus time instead: typing "hello world" straight after the click
  //: left "worldhello " in the box, because the caret was put back to 0 after
  //: the first characters had already landed.
  //: Both ends of it, not just the caret: a caller that selected a word and
  //: then acted on it (the shared toolbar does exactly that) would otherwise
  //: have its selection collapsed to the start by the mount, and the action
  //: would insert a placeholder where the word was.
  const length = host.value.length;
  const from = Math.min(host.selectionStart ?? length, length);
  const to = Math.min(host.selectionEnd ?? from, length);
  const state = CM.state.EditorState.create({
    doc: host.value,
    selection: { anchor: from, head: to },
    extensions: noteSurfaceExtensions(CM, host, settings),
  });
  const view = new CM.view.EditorView({ state, parent: wrap });
  //: The same guard the document's own host carries: the app binds single
  //: characters as global shortcuts ("/" focuses search), and a
  //: contenteditable is not a textarea, so nothing else stops them. Measured
  //: without it: typing "/" in a note put no slash in the note.
  docGuardGlobalShortcuts(view.contentDOM);
  noteSurfaceViews.set(host, view);
  noteSurfaceOwnValue(host, view);
  //: A box that had the focus keeps it through its own upgrade. The editor
  //: mounts over the textarea the first time the section shows, and the
  //: textarea then loses focus to nothing (measured in Chromium: focus in
  //: on the textarea at 537ms after the phone's + was pressed, focus out
  //: with no related target at 679ms, the body active at 1200ms). The
  //: caret a person just asked for is the one thing the upgrade must not
  //: drop, so it goes where the words now go.
  if (hadFocus) view.focus();
  //: The "/" menu's table is keyed by surface id, and these boxes are in it
  //: already or are added here: one line rather than a wiring change, which
  //: is the shape editor.js's own comment asks for.
  if (typeof EDITOR_SURFACES === "object" && EDITOR_SURFACES && !(host.id in EDITOR_SURFACES)) {
    EDITOR_SURFACES[host.id] = "note";
  }
  return cmSurface(view, noteSurfaceMeta(host));
}

//: One delegated listener for every note box in the app, including the three
//: that are built in script when a card opens. `focusin` rather than `focus`
//: because it bubbles, and the focus is handed to the view the moment it
//: exists so the keystroke that opened the box is not lost.
document.addEventListener("focusin", (event) => {
  const host = event.target;
  const options = host instanceof HTMLTextAreaElement && NOTE_SURFACES[host.id];
  if (!options || noteSurfaceViews.has(host)) return;
  mountNoteSurface(host, options).then((s) => {
    //: Only while this box is still the focused one. A mount that already had
    //: the caret keeps it itself (`hadFocus`), so this is for the fallback box;
    //: and a person who left the box while the bundle loaded must not be pulled
    //: back into it (Save, a blur, then Ctrl+Shift+Z met the editor and Redo
    //: never ran: e2e capture-filing under load, 400 ms after the blur).
    if (document.activeElement !== host) return;
    return !activeOverlay() && s?.focus();
  });
});
// NOTE-SURFACE-END

function initMarkdownToolbars() {
  for (const bar of document.querySelectorAll("[data-md-target], #doc-toolbar")) {
    wireMarkdownToolbar(bar);
  }
  wireMdFormatShortcuts("entry-content");
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

//: **The reading measure, opted out of.** Reported: "idk why the document
//: rendered views are so thin??", measured at 736px inside a 1132px pane,
//: which is the 72ch cap in the CSS doing exactly what it was written to do.
//: A measure is right for reading a finished page and wrong for a wide table,
//: a code-heavy file, or simply wanting the window you have. The cap stays the
//: default; this is the way out of it.
//:
//: The class goes on the tab rather than on each pane so Split's two halves
//: can never disagree, and it is remembered because it is a preference about
//: how you read, not a place you are.
//: A toggle shows its state in its glyph, not only in a fill (INBOX 904 B58:
//: "clicking an icon button to toggle smth doesn't change the icon's" look).
//: Keeps `ph-lead` on a menu row's icon.
function docToggleIcon(button, on, onIcon, offIcon) {
  const icon = button?.querySelector("i.ph");
  if (!icon) return;
  const lead = icon.classList.contains("ph-lead") ? " ph-lead" : "";
  icon.className = `ph ${on ? onIcon : offIcon}${lead}`;
}

const DOC_WIDTH_KEY = "doc-full-width";

function applyDocWidth(wide) {
  const tab = $("tab-documents");
  tab?.classList.toggle("doc-wide", wide);
  const title = wide ? "Back to a comfortable reading width" : "Use the full width of the pane";
  //: **Both views of one setting, painted together.** The toolbar's icon and
  //: the ⋯ menu's worded row are the same control, and the app's own rule (see
  //: `applyDocToolbarMode`) is that painting one without the other is how they
  //: drift. The menu row exists because the icon alone was not findable, 
  //: reported as "is there a way to make it wider if the user chooses??" about
  //: a control that was already there.
  for (const button of [$("doc-width-toggle"), $("doc-width-menu")]) {
    if (!button) continue;
    button.setAttribute("aria-pressed", String(wide));
    docToggleIcon(button, wide, "ph-arrows-in-line-horizontal", "ph-arrows-out-line-horizontal");
    button.title = title;
    button.setAttribute("aria-label", title);
  }
  //: The label names what pressing it *does*, not the state it is in, the
  //: state is `aria-pressed` for a screen reader and the pane's own width for
  //: everyone else. Same rule the toolbar-mode row follows.
  const label = $("doc-width-menu-label");
  if (label) label.textContent = wide ? "Comfortable reading width" : "Use the full width";
}

function setDocWidth(wide) {
  try {
    prefs.set(DOC_WIDTH_KEY, wide ? "wide" : "measure");
  } catch {
    // A private window can refuse storage; the mode still applies for now.
  }
  applyDocWidth(wide);
}

const toggleDocWidth = () => setDocWidth(!$("tab-documents")?.classList.contains("doc-wide"));
$("doc-width-toggle")?.addEventListener("click", toggleDocWidth);
$("doc-width-menu")?.addEventListener("click", toggleDocWidth);

try {
  applyDocWidth(prefs.get(DOC_WIDTH_KEY, null) === "wide");
} catch {
  applyDocWidth(false);
}

//: **Reading and focus: three preferences about the act of writing**
//: (DOCUMENTS_PLAN Phase 5 item 4, PLAN D9). They are one block because they
//: answer one question, "what should be in front of me while I write this",
//: and because two of them are the same mistake apart: a mode that changes
//: what the editor *shows* and one that changes where it *puts* the line you
//: are on.
//:
//: Named apart from `toggleDocFocus`, which hides the app's chrome and is a
//: mode for right now. These three are remembered, because they are the shape
//: of somebody's writing habit rather than a thing they did once, and none of
//: them can leave the document unreachable: the caret's own paragraph is never
//: dimmed, the centred line is still the line you are typing on, and the serif
//: is a face, not a layout.
const DOC_DIM_KEY = "doc-dim-others";
const DOC_TYPEWRITER_KEY = "doc-typewriter";
const DOC_SERIF_KEY = "doc-serif";

const docReadingModes = { dimOthers: false, typewriter: false };
let docReadingPluginCache = null;

//: The block, by the same rule the rest of this file uses: the run of
//: non-blank lines around the caret. A heading with a paragraph under it is
//: two blocks, which is what a person means by "the paragraph I am in", and a
//: list is dimmed item by item for the same reason.
function docReadingPlugin(CM) {
  if (docReadingPluginCache) return docReadingPluginCache;
  const { Decoration, ViewPlugin } = CM.view;

  function build(view) {
    if (!docReadingModes.dimOthers) return Decoration.none;
    const doc = view.state.doc;
    let first = doc.lineAt(view.state.selection.main.head).number;
    let last = first;
    while (first > 1 && doc.line(first - 1).text.trim() !== "") first--;
    while (last < doc.lines && doc.line(last + 1).text.trim() !== "") last++;
    const ranges = [];
    //: Only what is on screen, like the findings plugin beside it: a 20,000
    //: word document would otherwise build a decoration per line on every
    //: arrow key.
    for (const range of view.visibleRanges) {
      const from = doc.lineAt(range.from).number;
      const to = doc.lineAt(range.to).number;
      for (let n = from; n <= to; n++) {
        if (n >= first && n <= last) continue;
        ranges.push(Decoration.line({ class: "cm-doc-dimmed" }).range(doc.line(n).from));
      }
    }
    return Decoration.set(ranges, true);
  }

  docReadingPluginCache = ViewPlugin.fromClass(
    class {
      constructor(view) {
        this.decorations = build(view);
      }
      update(update) {
        if (update.docChanged || update.selectionSet || update.viewportChanged) {
          this.decorations = build(update.view);
        }
      }
    },
    { decorations: (plugin) => plugin.decorations }
  );
  return docReadingPluginCache;
}

//: **Typewriter scrolling**, as an update listener rather than a second
//: plugin: it changes no decoration, it moves the viewport. The frame's delay
//: is not a nicety, a dispatch from inside an update is re-entrant and
//: CodeMirror refuses it; by the next frame the update has finished and the
//: measurement the scroll needs is the one that is actually on screen.
function docTypewriterExtension(CM) {
  const { EditorView } = CM.view;
  return EditorView.updateListener.of((update) => {
    if (!docReadingModes.typewriter) return;
    if (!update.selectionSet && !update.docChanged) return;
    const view = update.view;
    requestAnimationFrame(() => {
      if (!docReadingModes.typewriter || view !== docCmView) return;
      view.dispatch({
        effects: EditorView.scrollIntoView(view.state.selection.main.head, { y: "center" }),
      });
    });
  });
}

function applyDocDim(on) {
  docReadingModes.dimOthers = on;
  const button = $("doc-dim-others");
  if (button) {
    button.setAttribute("aria-pressed", String(on));
    docToggleIcon(button, on, "ph-drop-half-bottom", "ph-drop-half");
    button.title = on
      ? "Show the whole document again"
      : "Fade everything except the paragraph the caret is in";
  }
  const CM = window.CM6;
  if (docCmView && CM && docCmParts.reading) {
    docCmView.dispatch({
      effects: docCmParts.reading.reconfigure(on ? docReadingPlugin(CM) : []),
    });
  }
}

function applyDocTypewriter(on) {
  docReadingModes.typewriter = on;
  const button = $("doc-typewriter");
  if (button) {
    button.setAttribute("aria-pressed", String(on));
    docToggleIcon(button, on, "ph-arrows-in-line-vertical", "ph-arrows-down-up");
    button.title = on
      ? "Let the page scroll the way it normally does"
      : "Keep the line you are typing on in the middle of the pane";
  }
  if (on && docCmView && window.CM6) {
    const { EditorView } = window.CM6.view;
    docCmView.dispatch({
      effects: EditorView.scrollIntoView(docCmView.state.selection.main.head, { y: "center" }),
    });
  }
}

//: The rendered pane only. A serif is for reading a finished page; the editor
//: is where markers, code fences and tables live, and those are the one place
//: a monospaced or neutral face is doing real work.
function applyDocSerif(on) {
  $("tab-documents")?.classList.toggle("doc-serif", on);
  const button = $("doc-serif");
  if (button) {
    button.setAttribute("aria-pressed", String(on));
    button.title = on ? "Back to the app's own face" : "Read the rendered page in a serif";
  }
}

function docRememberReading(key, on, apply) {
  try {
    prefs.set(key, on ? "1" : "0");
  } catch {
    // A private window can refuse storage; the mode still applies for now.
  }
  apply(on);
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

function docRestoreReading() {
  let dim = false;
  let typewriter = false;
  let serif = false;
  try {
    dim = prefs.get(DOC_DIM_KEY, null) === "1";
    typewriter = prefs.get(DOC_TYPEWRITER_KEY, null) === "1";
    serif = (prefs.get(DOC_SERIF_KEY, null) ?? (prefsCache?.writing_style === "documents" ? "1" : "")) === "1";
  } catch {
    // Nothing stored, nothing remembered: the defaults below are all off.
  }
  applyDocDim(dim);
  applyDocTypewriter(typewriter);
  applyDocSerif(serif);
}

docRestoreReading();

//: **Text size and line spacing for prose** (docs3-1026). Word and Google
//: Docs both have them; here they are two cycling rows in the menu, set once
//: and remembered, because the same window is a half-screen beside a lecture
//: one day and a full screen the next. Classes on the tab, drawn by
//: library-lazy.css for prose only: a code file keeps its own metrics, which
//: the gutter arithmetic depends on.
const DOC_TEXT_SIZES = ["small", "medium", "large", "xlarge", "xxlarge"];
const DOC_LINE_SPACINGS = ["compact", "comfortable", "relaxed"];

function docCycleChoice(list, current) {
  return list[(list.indexOf(current) + 1) % list.length];
}

function applyDocTypography(size, spacing) {
  const tab = $("tab-documents");
  for (const name of DOC_TEXT_SIZES) tab?.classList.toggle(`doc-size-${name}`, name === size);
  for (const name of DOC_LINE_SPACINGS) tab?.classList.toggle(`doc-spacing-${name}`, name === spacing);
  const sizeLabel = $("doc-text-size-label");
  if (sizeLabel) sizeLabel.textContent = `Text size: ${{ xlarge: "extra large", xxlarge: "huge" }[size] || size}`;
  const spacingLabel = $("doc-line-spacing-label");
  if (spacingLabel) spacingLabel.textContent = `Line spacing: ${spacing}`;
}

function docTypographyNow() {
  const tab = $("tab-documents");
  return {
    size: DOC_TEXT_SIZES.find((n) => tab?.classList.contains(`doc-size-${n}`)) || "medium",
    spacing: DOC_LINE_SPACINGS.find((n) => tab?.classList.contains(`doc-spacing-${n}`)) || "comfortable",
  };
}

function docStepTypography(which) {
  const now = docTypographyNow();
  const size = which === "size" ? docCycleChoice(DOC_TEXT_SIZES, now.size) : now.size;
  const spacing = which === "spacing" ? docCycleChoice(DOC_LINE_SPACINGS, now.spacing) : now.spacing;
  try {
    prefs.set("doc-text-size", size);
    prefs.set("doc-line-spacing", spacing);
  } catch {
    // A private window can refuse storage; the choice still applies for now.
  }
  applyDocTypography(size, spacing);
}

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

function docRestoreTypography() {
  let size = "medium";
  let spacing = "comfortable";
  try {
    const savedSize = prefs.get("doc-text-size", null);
    const savedSpacing = prefs.get("doc-line-spacing", null);
    if (DOC_TEXT_SIZES.includes(savedSize)) size = savedSize;
    if (DOC_LINE_SPACINGS.includes(savedSpacing)) spacing = savedSpacing;
  } catch {
    // Nothing stored: the defaults are the app's own.
  }
  applyDocTypography(size, spacing);
}

docRestoreTypography();


//: **Focus mode.** Asked for as part of "the ultimate editor", and again by
//: the owner as "a document full screen mode so there is more space"
//: (INBOX 425 i), which is how it was found to have had no visible way in:
//: its button sat in the formatting strip, and that strip is hidden until
//: asked for. Measured before this pass at 1440x900 with the mode off: 228px
//: of chrome above the first line and a writing area 520px tall.
//:
//: The mode hides everything that is not the page: the app's top bar and tab
//: strip (the tab page covers them, `position: fixed`, the same overlay the
//: whiteboard's and graph's full-screen toggles use), the document sidebar,
//: the dock, the formatting strip, the breadcrumbs and the status bar. What is
//: left is the column at `--doc-measure`, centred in the window, and one small
//: floating dock (`#doc-focus-bar`) with the title, the word count, the save
//: state and the way out, which fades after `DOC_FOCUS_IDLE_MS` without the
//: pointer moving and comes back on a move, a hover or a keyboard focus.
//:
//: **Remembered for the session, not for good.** `sessionStorage`, so a
//: reload in the middle of writing comes back as it was, and a fresh launch
//: always opens into the normal page: an app that starts with no chrome and
//: its only exit faded out is its own bug. The earlier version remembered
//: nothing, which made a reload throw the mode away mid-sentence.
const DOC_FOCUS_KEY = "doc-focus";
const DOC_FOCUS_IDLE_MS = 2500;
let docFocusIdleTimer = 0;
let docFocusLastWake = 0;
let docFocusSavedWatch = null;
//: Whether this mode asked for the browser's full screen, so leaving the mode
//: only undoes what the mode did: a person who was already in the browser's
//: own full screen before opening focus mode stays in it after.
let docFocusOwnsFullscreen = false;

function docFocusOn() {
  return !!$("tab-documents")?.classList.contains("doc-focus");
}

//: **Tools, inside the mode** (INBOX 426 a). Brings the dock and the
//: formatting strip back without leaving focus mode; remembered for the
//: session with the mode itself, so a reload that restores the mode restores
//: what it was showing. Showing the tools expands a collapsed strip, because
//: the press asked to see the tools and a collapsed strip in focus mode is a
//: bar with nothing on it but the way to open it.
const DOC_FOCUS_TOOLS_KEY = "doc-focus-tools";

function setDocFocusTools(on) {
  const tab = $("tab-documents");
  if (!tab) return;
  tab.classList.toggle("doc-focus-tools", on);
  const button = $("doc-focus-tools");
  if (button) {
    button.setAttribute("aria-pressed", String(on));
    button.title = on ? "Hide the dock and the formatting tools" : "Show the dock and the formatting tools";
    button.setAttribute("aria-label", button.title);
  }
  if (on && docToolbarCollapsed()) setDocToolbarCollapsed(false);
  try {
    if (on) sessionStorage.setItem(DOC_FOCUS_TOOLS_KEY, "1");
    else sessionStorage.removeItem(DOC_FOCUS_TOOLS_KEY);
  } catch {
    // Storage refused: the tools show for now and are not brought back.
  }
}

//: **The sidebar, inside the mode** (INBOX 453 (1): "there should be a way to
//: open and close the documents editor sidebar when in full screen mode").
//: The list and the outline come back as a panel fixed to the window's left
//: edge while the page gives up that room, the mirror of Suggestions on the
//: right; remembered for the session with the mode, like Tools. On a phone
//: the two side panels would be two full-width sheets, so opening one closes
//: the other. The editor has no key for its sidebar outside the mode (only
//: the rail's own toggle), so there is none to reuse; Escape closes it.
const DOC_FOCUS_SIDEBAR_KEY = "doc-focus-sidebar";
const DOC_FOCUS_NARROW = "(max-width: 720px)";

function setDocFocusSidebar(on) {
  const tab = $("tab-documents");
  if (!tab) return;
  tab.classList.toggle("doc-focus-sidebar", on);
  const button = $("doc-focus-sidebar");
  if (button) {
    button.setAttribute("aria-pressed", String(on));
    button.title = on ? "Hide the documents sidebar (Esc)" : "Show the documents sidebar";
    button.setAttribute("aria-label", button.title);
  }
  if (on && window.matchMedia(DOC_FOCUS_NARROW).matches && !$("doc-prose-panel")?.classList.contains("hidden")) {
    $("doc-prose-panel").classList.add("hidden");
    $("doc-prose")?.setAttribute("aria-expanded", "false");
    docFocusSyncProse();
  }
  try {
    if (on) sessionStorage.setItem(DOC_FOCUS_SIDEBAR_KEY, "1");
    else sessionStorage.removeItem(DOC_FOCUS_SIDEBAR_KEY);
  } catch {
    // Storage refused: the sidebar shows for now and is not brought back.
  }
}

function toggleDocFocus(force) {
  const tab = $("tab-documents");
  if (!tab) return;
  const on = typeof force === "boolean" ? force : !tab.classList.contains("doc-focus");
  tab.classList.toggle("doc-focus", on);
  tab.classList.remove("doc-focus-idle");
  //: The suggestions panel's grip is offered in the mode as well (INBOX 1408).
  applyDocProseDock();
  try {
    if (on) sessionStorage.setItem(DOC_FOCUS_KEY, "1");
    else sessionStorage.removeItem(DOC_FOCUS_KEY);
  } catch {
    // Storage refused (a private window): the mode still works, it just is
    // not brought back by a reload.
  }
  const button = $("doc-focus-toggle");
  if (button) {
    button.setAttribute("aria-pressed", String(on));
    button.title = on
      ? "Leave focus mode (Esc or F11)"
      : "Focus mode: hide everything but the page (F11)";
    button.setAttribute("aria-label", button.title);
    const icon = button.querySelector("i");
    if (icon) icon.className = on ? "ph ph-corners-in" : "ph ph-corners-out";
  }
  if (on) {
    docFocusFill();
    docFocusWatch(true);
    docFocusWake(true);
    let tools = false;
    try {
      tools = sessionStorage.getItem(DOC_FOCUS_TOOLS_KEY) === "1";
    } catch {
      // No storage: the mode opens with the page alone, as it always has.
    }
    setDocFocusTools(tools);
    let sidebar = false;
    try {
      sidebar = sessionStorage.getItem(DOC_FOCUS_SIDEBAR_KEY) === "1";
    } catch {
      // No storage: the mode opens with the page alone.
    }
    setDocFocusSidebar(sidebar);
  } else {
    docFocusWatch(false);
    clearTimeout(docFocusIdleTimer);
    if (docFocusOwnsFullscreen && docDesktopFs().full) {
      docDesktopFullscreenToggle().then(docFocusSyncFullscreen);
    } else if (docFocusOwnsFullscreen && document.fullscreenElement) {
      document.exitFullscreen?.().catch(() => {});
    }
    docFocusOwnsFullscreen = false;
  }
  //: The caret goes back to the page either way: entering, so the next key
  //: is writing; leaving, because the control that was pressed (the floating
  //: Exit) has just stopped being drawn and would otherwise take the focus
  //: with it to <body>.
  if (tab.classList.contains("hidden")) return;
  docSurface()?.focus();
}

//: The floating dock's words. The title and the count are written from
//: `renderDocCounts` while the mode is on (it runs after every edit and every
//: open, so a document switched from the palette relabels the dock too); the
//: save state is watched, because it is written from a dozen places and none
//: of them should have to know this dock exists.
function docFocusFill() {
  docSetStatusText($("doc-focus-title"), $("doc-title")?.value.trim() || "Untitled");
  docSetStatusText($("doc-focus-saved"), $("doc-saved")?.textContent || "");
  renderDocCounts();
  const full = $("doc-focus-fullscreen");
  if (full) full.hidden = !document.fullscreenEnabled && !docDesktopFs().available;
  docFocusSyncFullscreen();
  //: Asked once, then kept: whether this page is in the desktop window,
  //: whose own full screen is the one that fills the monitor.
  if (!docDesktopFs().asked) {
    docDesktopFs().asked = true;
    apiJson("/desktop/fullscreen")
      .then((state) => {
        docDesktopFs().available = !!state?.available;
        docDesktopFs().full = !!state?.fullscreen;
        if (full) full.hidden = !document.fullscreenEnabled && !docDesktopFs().available;
        docFocusSyncFullscreen();
      })
      .catch(() => {});
  }
}

function docFocusWatch(on) {
  docFocusSavedWatch?.disconnect();
  docFocusSavedWatch = null;
  const listen = on ? "addEventListener" : "removeEventListener";
  document[listen]("pointermove", docFocusPointer, { passive: true });
  document[listen]("pointerdown", docFocusPointer, { passive: true });
  document[listen]("keydown", docFocusKey, true);
  if (!on) return;
  const saved = $("doc-saved");
  if (saved && typeof MutationObserver === "function") {
    docFocusSavedWatch = new MutationObserver(() =>
      docSetStatusText($("doc-focus-saved"), saved.textContent || "")
    );
    docFocusSavedWatch.observe(saved, { childList: true, characterData: true, subtree: true });
  }
}

//: The dock comes back and the idle clock restarts. Throttled to one restart
//: per quarter second, because `pointermove` fires at the display's rate and
//: a timer cleared and set sixty times a second is work a poor laptop can
//: feel for no change on screen.
function docFocusWake(force = false) {
  const tab = $("tab-documents");
  if (!tab?.classList.contains("doc-focus")) return;
  const now = performance.now();
  const idle = tab.classList.contains("doc-focus-idle");
  if (!force && !idle && now - docFocusLastWake < 250) return;
  if (idle) tab.classList.remove("doc-focus-idle");
  docFocusLastWake = now;
  clearTimeout(docFocusIdleTimer);
  docFocusIdleTimer = setTimeout(docFocusRest, DOC_FOCUS_IDLE_MS);
}

function docFocusRest() {
  const tab = $("tab-documents");
  if (!tab?.classList.contains("doc-focus")) return;
  //: Never out from under the hand or the keyboard: a pointer resting on the
  //: dock or a focus inside it keeps it, and the clock is asked again later.
  if ($("doc-focus-bar")?.matches(":hover, :focus-within")) {
    docFocusIdleTimer = setTimeout(docFocusRest, DOC_FOCUS_IDLE_MS);
    return;
  }
  tab.classList.add("doc-focus-idle");
}

function docFocusPointer() {
  docFocusWake();
}

//: A key pressed while writing is writing, so it sends the dock away at
//: once rather than after the idle wait; a key pressed anywhere else (the
//: focus on the page itself, Tab walking into the dock) brings it back.
function docFocusKey(event) {
  const target = event.target;
  const writing = target instanceof Element &&
    !!target.closest('[contenteditable="true"], textarea, input:not([type="checkbox"]):not([type="radio"])') &&
    !target.closest("#doc-focus-bar");
  if (!writing) {
    docFocusWake(true);
    return;
  }
  if (event.key === "Escape" || event.ctrlKey || event.metaKey || event.altKey) return;
  clearTimeout(docFocusIdleTimer);
  docFocusRest();
}

//: The browser's own full screen, offered only where it exists and only as
//: an extra: the in-app mode is the whole feature, and this takes away the
//: browser's or the desktop window's frame as well. A refusal (an iframe
//: without permission, a webview that does not implement it) changes
//: nothing but a toast.
//:
//: **In the desktop window it is the window that fills the screen** (INBOX
//: 426 z, images 93 and 94: "Fill the whole screen" did nothing there). The
//: web view granted the page its full screen, the button turned to "Leave
//: full screen", and the window did not move: a web view's full screen fills
//: the web view, and resizing the window around it is the host's job, which
//: pywebview does not do. So where the server says there is a window
//: (`GET /desktop/fullscreen`, core/window_hook.py) the window is asked, and
//: the browser's API is used everywhere else. The state hangs off a hoisted
//: function rather than a `let`: `docFocusFill` can run before this part of
//: the file has, and a `let` would be in its temporal dead zone then.
function docDesktopFs() {
  docDesktopFs.state ||= { asked: false, available: false, full: false };
  return docDesktopFs.state;
}

async function docDesktopFullscreenToggle() {
  try {
    const state = await apiJson("/desktop/fullscreen", { method: "POST" });
    docDesktopFs().available = !!state?.available;
    docDesktopFs().full = !!state?.fullscreen;
    return docDesktopFs().available;
  } catch {
    return false;
  }
}

function docFocusSyncFullscreen() {
  const button = $("doc-focus-fullscreen");
  if (!button) return;
  const full = docDesktopFs().available ? docDesktopFs().full : !!document.fullscreenElement;
  button.setAttribute("aria-pressed", String(full));
  button.title = full ? "Leave full screen" : "Fill the whole screen";
  button.setAttribute("aria-label", button.title);
  const icon = button.querySelector("i");
  if (icon) icon.className = full ? "ph ph-arrows-in" : "ph ph-arrows-out";
}

async function docFocusToggleFullscreen() {
  if (docDesktopFs().available) {
    if (await docDesktopFullscreenToggle()) {
      docFocusOwnsFullscreen = docDesktopFs().full;
    } else {
      toast("Full screen is not available in this window.", "info");
    }
    docFocusSyncFullscreen();
    docSurface()?.focus();
    return;
  }
  try {
    if (document.fullscreenElement) {
      await document.exitFullscreen();
      docFocusOwnsFullscreen = false;
    } else {
      await document.documentElement.requestFullscreen();
      docFocusOwnsFullscreen = true;
    }
  } catch {
    toast("Full screen is not available in this window.", "info");
  }
  docFocusSyncFullscreen();
  docSurface()?.focus();
}

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

//: Leaving with unsaved edits would lose them; autosave hasn't fired yet.
//: The `beforeunload` guard for this is centralised in navigation.js
//: (`hasUnsavedWork`/its listener) now, alongside the note edit form and the
//: Capture box, rather than kept here as a second `docDirty`-only listener:
//: one browser event, one place that reads every surface's own flag.

initDocSidebarTabs();


// --- Toolbar shape: expanded, or one scrolling row --------------------------
//
// Asked for directly: *"there should be the option to have the tool bar as a
// horizontal scroll or expanded."* Expanded (wrapping) is the default, and not
// only as a preference: a wrapping toolbar is not a scroll container, so it
// cannot clip the `<details>` menus inside it: which was the other half of
// the same report. See `.doc-toolbar`'s own comment for the `overflow-y:
// visible` trap that caused both.

const DOC_TOOLBAR_MODE_KEY = "doc-toolbar-mode";
//: The default flipped from "row" to "wrap" on 2026-09-09 (see `.doc-toolbar`
//: in 05-sidebars-themes.css), but a value saved before that still reads
//: "row" from storage and renders the crushed single-line strip forever,
//: which is exactly the "still gets clipped" report repeating on a build
//: that already carries the fix. Migrated once: a bare stored "row" with no
//: migration flag is the pre-2026-09-09 default, not a deliberate choice,
//: so it is cleared back to the new default rather than honoured.
const DOC_TOOLBAR_MODE_MIGRATED_KEY = "doc-toolbar-mode-migrated-2026-09-09";

function docToolbarMode() {
  try {
    const stored = prefs.get(DOC_TOOLBAR_MODE_KEY, null);
    if (stored === "row" && !prefs.get(DOC_TOOLBAR_MODE_MIGRATED_KEY, null)) {
      prefs.remove(DOC_TOOLBAR_MODE_KEY);
      prefs.set(DOC_TOOLBAR_MODE_MIGRATED_KEY, "1");
      return "wrap";
    }
    if (stored === "row" || stored === "wrap") return stored;
    //: No stored choice and a narrow window: one row (143 px wrapped, 59 px
    //: here at 700 px wide; dogfood item 10). The toggle always wins.
    return window.matchMedia?.(DOC_TOOLBAR_NARROW)?.matches ? "row" : "wrap";
  } catch {
    return "wrap"; // private mode: the safe shape, since it never clips
  }
}

const DOC_TOOLBAR_NARROW = "(max-width: 760px)";
window.matchMedia?.(DOC_TOOLBAR_NARROW)?.addEventListener?.("change", () => applyDocToolbarMode(docToolbarMode()));

function applyDocToolbarMode(mode) {
  const row = mode === "row";
  for (const bar of document.querySelectorAll(".doc-toolbar")) {
    //: An attribute rather than a class: the CSS keys off
    //: `[data-toolbar-mode="row"]`, and the default (wrap) is the bare rule,
    //: so an unset attribute is the safe shape rather than an unstyled one.
    if (row) bar.dataset.toolbarMode = "row";
    else delete bar.dataset.toolbarMode;
  }
  const button = document.getElementById("doc-toolbar-mode");
  const label = document.getElementById("doc-toolbar-mode-label");
  if (button) button.setAttribute("aria-pressed", row ? "true" : "false");
  //: The label names what pressing it *does*, not the state it is in, the
  //: state is carried by `aria-pressed` for a screen reader and by the
  //: toolbar's own shape for everyone else.
  if (label) label.textContent = row ? "Expand the toolbar" : "Use one row";
  //: The strip's own layout button and this menu entry are two views of one
  //: setting, so painting one without the other is how they drift.
  applyDocToolbarLayoutButtons();
  //: Refit now: the mode change alone does not resize the bar, so the width observer never fired and the
  //: note editor's "fit on one row" button looked like it did nothing (reported at release). Once, after
  //: the layout button moved, not once per strip before it as well.
  fitDocToolbars();
}

function setDocToolbarMode(mode) {
  try {
    prefs.set(DOC_TOOLBAR_MODE_KEY, mode);
    //: A choice made now is never the pre-2026-09-09 default the migration
    //: in `docToolbarMode` clears. Without the flag, the first read after
    //: choosing "row" cleared it back to "wrap": the next press chose "row"
    //: again (the toggle could not go back) and a reload lost it.
    prefs.set(DOC_TOOLBAR_MODE_MIGRATED_KEY, "1");
  } catch {
    /* private mode: it just won't be remembered */
  }
  applyDocToolbarMode(mode);
}

document.getElementById("doc-toolbar-mode")?.addEventListener("click", () => {
  setDocToolbarMode(docToolbarMode() === "row" ? "wrap" : "row");
});

//: **The two controls that were asked for, on the toolbar itself.**
//:
//: Reported: *"cant collapse and make horizontally scrollable the tools bar in
//: the notes capture subtab and documents editor."* Half of that was already
//: built and unfindable: the wrap/scroll switch existed, buried in the
//: document dock's ⋯ menu, four clicks from the strip it changes, and the note
//: composer's toolbar had no way to reach it at all. The other half, collapse,
//: did not exist: on a laptop the expanded strip is two rows of chrome above a
//: three-row note box.
//:
//: Built in script rather than written into the markup twice, because there
//: are two toolbars and a third would silently miss out. Pinned to the right
//: edge with `position: sticky` so that in scroll mode the controls do not
//: scroll away with the buttons they control.
//: **Line numbers are a choice, not a file-type consequence.** Asked for
//: directly: "line numbers should be togglable in the documents". They used to
//: appear for code files and for nothing else, so a long markdown note -- the
//: thing most likely to need "the paragraph around line 240" -- could not have
//: them, and a .py file could not be rid of them.
//:
//: Default follows the old behaviour (on for code, off for prose), so nothing
//: moves for anyone who never touches the control; once touched, the choice is
//: remembered and wins for every file.
const DOC_GUTTER_KEY = "doc-gutter";

function docGutterPref() {
  try {
    return prefs.get(DOC_GUTTER_KEY, null); // "1", "0", or null for "follow the file type"
  } catch {
    return null;
  }
}

function docGutterWanted(isCode) {
  const pref = docGutterPref();
  if (pref === "1") return true;
  if (pref === "0") return false;
  //: Plain numbers itself, like a code file does. Asked for directly:
  //: "on the plain txt editor, they should show by default but be togglable
  //: in the toolbar." Only the *default* moves: an explicit "0" above still
  //: wins, so turning them off in Plain turns them off and stays off. Plain
  //: is the view with no grammar and no decorations (docCmViewLanguage), so
  //: the numbers are the only structure left to navigate by, which is why
  //: this is the one view whose default differs from prose's.
  if (typeof docView !== "undefined" && docView === "plain") return true;
  return Boolean(isCode);
}

function setDocGutter(on) {
  try {
    prefs.set(DOC_GUTTER_KEY, on ? "1" : "0");
  } catch {
    /* private mode: the choice holds for this session only */
  }
  document.documentElement.dataset.noteGutter = on ? "on" : "off";
  applyDocGutter();
}

//: Reads the *current* file's type rather than taking it as an argument, so
//: the toggle and the file-open path cannot disagree about what "code" means.
function applyDocGutter() {
  // One remembered choice for every editor. The documents editor keeps its
  // "follow the file type" default (code files number themselves); a note
  // box has no file type, so there the choice alone decides.
  let anyOn = false;
  for (const { gutter, box } of docGutters()) {
    const isDoc = box.id === "doc-content";
    const on = isDoc
      ? docGutterWanted(box.classList.contains("doc-content-code"))
      : docGutterPref() === "1";
    gutter.classList.toggle("hidden", !on);
    //: Numbers only line up against hard lines, so a numbered box stops
    //: soft-wrapping, which is the same rule `.doc-content-code` already
    //: applies.
    //:
    //: **The documents editor used to be excluded from this**, on the
    //: assumption that a numbered document is always a code file and so
    //: already has `.doc-content-code`. It is not: `docGutterWanted` honours a
    //: remembered "1", so anyone who turned line numbers on sees them on a
    //: markdown document too, where the textarea soft-wraps and the column
    //: does not. That is one number lost per wrapped line, accumulating down
    //: the file, which is exactly the "line numbers drift out of sync with the
    //: text" that was reported.
    box.classList.toggle("has-gutter", on);
    anyOn = anyOn || on;
  }
  syncDocGutterMetrics();
  watchDocGutter(docBoxEl());
  //: The document's own numbers come from the engine once it is mounted, so
  //: the preference has to reach it as well as the two note columns.
  docCmSyncGutter();
  for (const { box } of docGutters()) {
    const view = noteSurfaceViews.get(box);
    if (view && box.noteGutterSlot && window.CM6) view.dispatch({ effects: box.noteGutterSlot.reconfigure(noteSurfaceGutter(window.CM6, box)) });
  }
  for (const button of document.querySelectorAll(".doc-toolbar-gutter")) {
    const bar = button.closest(".doc-toolbar");
    const own = bar?.id === "doc-toolbar"
      ? docCmView
        ? docGutterWanted(!docFileType().previewable)
        : !$("doc-gutter")?.classList.contains("hidden")
      : docGutterPref() === "1";
    button.setAttribute("aria-pressed", own ? "true" : "false");
    button.title = own ? "Hide line numbers" : "Show line numbers";
    button.setAttribute("aria-label", button.title);
  }
  renderDocGutter();
}

const DOC_TOOLBAR_COLLAPSED_KEY = "doc-toolbar-collapsed";

function docToolbarCollapsed() {
  try {
    // Collapsed until you ask for it (PLAN.md D1): Typora, iA Writer and
    // Notion all start with no formatting strip on screen, the strip is a
    // 30-control, three-row block that pushed the first line of text to
    // y=284 at 1440px. The collapsed strip keeps its own name and the
    // chevron that brings it back, and a choice either way is remembered.
    return (prefs.get(DOC_TOOLBAR_COLLAPSED_KEY, null) ?? "1") === "1";
  } catch {
    return false; // private mode: the expanded shape is the safe default
  }
}

//: `only`: one strip, which may not be in the document yet. Both appliers are
//: what actually draw the wrap and collapse glyphs (`setLabel` lives here, not
//: at the buttons' creation), and both used to walk the document -- so a bar
//: mounted before insertion, which is exactly what the note edit form's cloned
//: strip is, ended up with two blank buttons.
function applyDocToolbarCollapsed(collapsed, only = null) {
  // The documents dock's own strip has a toggle in the header row (PLAN.md
  // D1); the strip itself hides entirely while collapsed, so the header
  // button is the way back and must say which state it is in.
  const headerToggle = $("doc-format-toggle");
  if (headerToggle && (!only || only.id === "doc-toolbar")) {
    headerToggle.setAttribute("aria-pressed", collapsed ? "false" : "true");
    headerToggle.title = collapsed
      ? "Show the formatting toolbar above the editor (Ctrl+Shift+X)"
      : "Hide the formatting toolbar (Ctrl+Shift+X)";
    headerToggle.setAttribute("aria-label", headerToggle.title);
    const label = $("doc-format-toggle-label");
    if (label) label.textContent = collapsed ? "Show formatting toolbar" : "Hide formatting toolbar";
    docSyncFormatShow();
  }
  for (const bar of only ? [only] : document.querySelectorAll(".doc-toolbar")) {
    //: **A note's strip never folds** (INBOX 616, the owner: "the formatting
    //: toolbar looks really awkward when collapsed", an empty band with three
    //: icons and a caret). It is one slim row of icons with the rest behind
    //: More, in Capture and the edit form alike; the folded state and its
    //: button are the document editor's, which has a dock to bring it back.
    bar.classList.toggle("is-collapsed", collapsed && !bar.classList.contains("note-toolbar"));
    const button = bar.querySelector(".doc-toolbar-collapse");
    if (!button) continue;
    button.setAttribute("aria-pressed", collapsed ? "true" : "false");
    button.title = collapsed ? "Show the formatting tools" : "Hide the formatting tools";
    button.setAttribute("aria-label", button.title);
    setLabel(button, collapsed ? "ph:caret-down" : "ph:caret-up");
  }
  for (const bar of only ? [only] : document.querySelectorAll(".doc-toolbar")) fitDocToolbarRow(bar);
}

function setDocToolbarCollapsed(collapsed) {
  try {
    prefs.set(DOC_TOOLBAR_COLLAPSED_KEY, collapsed ? "1" : "0");
  } catch {
    /* private mode: it just won't be remembered */
  }
  applyDocToolbarCollapsed(collapsed);
  //: **Said once, the first time it is hidden** (INBOX 574): where it went
  //: and the two ways back, so a strip closed by accident is not lost.
  if (collapsed) {
    let told = false;
    try {
      told = prefs.get(DOC_TOOLBAR_HINT_KEY, null) === "1";
      prefs.set(DOC_TOOLBAR_HINT_KEY, "1");
    } catch {
      /* private mode: said every time, which is the safe side */
    }
    if (!told) toast("Formatting hidden. Bring it back from the Formatting button or Ctrl+Shift+X.");
  }
}

const DOC_TOOLBAR_HINT_KEY = "doc-toolbar-hidden-hint";

//: The dock's Formatting button (INBOX 574): there while the strip is hidden
//: on a document that has one (a code file has no markdown strip at all, so
//: no way back to it either).
function docSyncFormatShow() {
  const show = $("doc-format-show");
  if (!show) return;
  const strip = $("doc-toolbar");
  const stripless = !strip || strip.classList.contains("hidden");
  show.classList.toggle("hidden", !docToolbarCollapsed() || stripless || !currentDoc);
}

function toggleDocToolbar() {
  const collapsed = !docToolbarCollapsed();
  setDocToolbarCollapsed(collapsed);
  if (!collapsed) $("doc-toolbar")?.querySelector("button:not([hidden])")?.focus({ preventScroll: true });
  //: Hiding it from inside it must not strand the keyboard on <body>: the
  //: focused button just vanished, and the next keystroke went nowhere.
  else if (!document.activeElement || document.activeElement === document.body) docSurface()?.focus();
}

//: One strip's wrap/collapse group. Split out of the loop below so a bar that
//: is *not* in the document yet can get one: the note edit form clones the
//: capture strip, and a clone carries a copy of this group whose listeners did
//: not survive cloning -- two dead arrow buttons, sitting mid-strip instead of
//: at the end, because the loop's own `continue` then decided the bar already
//: had its controls. Counted in the browser: the clone's group sat between the
//: Preview button and the indent separator, where the capture strip's is last.
function mountDocToolbarControlsFor(bar) {
  {
    if (bar.querySelector(".doc-toolbar-tools")) return;
    const tools = document.createElement("span");
    tools.className = "doc-toolbar-tools";

    //: Shown only while collapsed, so the strip still says what it is rather
    //: than becoming an unexplained bar with two arrows in it.
    const name = document.createElement("span");
    name.className = "doc-toolbar-collapsed-name";
    name.textContent = "Formatting";
    tools.appendChild(name);

    //: **More, for a strip on one row** (INBOX 426 a). Hidden until
    //: `fitDocToolbarRow` finds tools that do not fit; pressing it lets the
    //: strip wrap to show them, and pressing it again folds them back.
    const more = document.createElement("button");
    more.type = "button";
    more.className = "ghost small icon-only doc-toolbar-more";
    more.hidden = true;
    setLabel(more, "ph:dots-three");
    more.addEventListener("click", () => {
      bar.classList.toggle("is-more-open");
      syncDocToolbarMore(bar);
    });
    tools.appendChild(more);

    const layout = document.createElement("button");
    layout.type = "button";
    layout.className = "ghost small icon-only doc-toolbar-layout";
    layout.addEventListener("click", () => {
      setDocToolbarMode(docToolbarMode() === "row" ? "wrap" : "row");
      applyDocToolbarLayoutButtons();
    });
    tools.appendChild(layout);

    const gutter = document.createElement("button");
    gutter.type = "button";
    gutter.className = "ghost small icon-only doc-toolbar-gutter";
    setLabel(gutter, "ph:list-numbers");
    gutter.addEventListener("click", () => {
      // The strip's own button reads its own gutter: the documents strip
      // asks #doc-gutter, a note strip asks the remembered choice.
      const own = bar.id === "doc-toolbar"
        ? docCmView
          ? !docGutterWanted(!docFileType().previewable)
          : $("doc-gutter")?.classList.contains("hidden")
        : docGutterPref() !== "1";
      setDocGutter(own);
    });
    tools.appendChild(gutter);

    const collapse = document.createElement("button");
    collapse.type = "button";
    collapse.className = "ghost small icon-only doc-toolbar-collapse";
    collapse.addEventListener("click", () => setDocToolbarCollapsed(!docToolbarCollapsed()));
    tools.appendChild(collapse);

    bar.appendChild(tools);
  }
  //: **Both buttons are drawn here, not by the caller.** Reported with a
  //: screenshot: "the note edit toolbar buttons on the bottom right dont
  //: render and show as black boxes". Neither button is given an icon when it
  //: is created -- `applyDocToolbarLayoutButtons` and `applyDocToolbarCollapsed`
  //: are what call `setLabel` on them, and both used to run once at the end of
  //: the document-wide loop below. A bar mounted on its own (the note edit
  //: form's cloned strip) therefore got two empty buttons: correct size,
  //: correct background, no glyph and no text.
  applyDocToolbarLayoutButtons(bar);
  applyDocToolbarCollapsed(docToolbarCollapsed(), bar);
  applyDocGutter();
  watchDocToolbarWidth(bar);
}

function mountDocToolbarControls() {
  $("doc-format-toggle")?.addEventListener("click", () =>
    setDocToolbarCollapsed(!docToolbarCollapsed())
  );
  $("doc-format-show")?.addEventListener("click", () => toggleDocToolbar());
  //: Ctrl+Shift+X anywhere on the Documents tab, not only inside the text
  //: (the editor's own keymap has it too): with the strip hidden, the focus
  //: is as likely to be on the dock as in the page.
  document.addEventListener("keydown", (event) => {
    if (!(event.ctrlKey || event.metaKey) || !event.shiftKey || event.altKey || event.key.toLowerCase() !== "x") return;
    if (event.defaultPrevented || $("tab-documents")?.classList.contains("hidden") || !currentDoc) return;
    event.preventDefault();
    toggleDocToolbar();
  });
  // The capture box gets its gutter here, once, with the strip that toggles it.
  mountGutterFor($("entry-content"));
  for (const bar of document.querySelectorAll(".doc-toolbar")) mountDocToolbarControlsFor(bar);
  applyDocToolbarLayoutButtons();
  applyDocToolbarCollapsed(docToolbarCollapsed());
}

function applyDocToolbarLayoutButtons(only = null) {
  const row = docToolbarMode() === "row";
  const scope = only || document;
  for (const button of scope.querySelectorAll(".doc-toolbar-layout")) {
    button.setAttribute("aria-pressed", row ? "true" : "false");
    //: The tooltip names what pressing it *does*; `aria-pressed` carries the
    //: state. Same rule the dock menu's own label follows.
    button.title = row ? "Expand the toolbar over several rows" : "Fit the toolbar on one row, the rest behind More";
    button.setAttribute("aria-label", button.title);
    setLabel(button, row ? "ph:rows" : "ph:arrows-left-right");
  }
}

//: **One row means one row, and what does not fit is behind More** (INBOX 426
//: a). The owner, with a screenshot of this strip at about 1000px: "in the
//: documents full screen mode, I cant access the formatting toolbar or any of
//: the other key tools or controls". The one-row mode was a sideways scroller
//: with the strip's own three buttons pinned over its right end
//: (`position: sticky` on an opaque ground), so the pinned group sat on top
//: of Insert, cut it in half, and every tool past it was behind a scrollbar
//: that looks like decoration. The phone band (720px and under) made every
//: strip that scroller, whatever the mode, with its scrollbar hidden.
//:
//: Now a strip that does not wrap is measured: its tools are laid out whole,
//: and while the strip's own group runs past the strip's inner edge the last
//: tool is folded away (`.doc-toolbar-over`, `display: none`), so the row
//: ends where the strip does and nothing is drawn over anything. More (the
//: first button of the group) says how many are folded; pressing it lets the
//: strip wrap and shows them in place, the real controls with their own
//: menus and handlers rather than copies in a list, so a `<details>` menu and
//: a colour picker behave exactly as they do on the row. A group rule left at
//: the end of the row with nothing after it is folded with its group.
//:
//: A wrapping strip (the default, and the note edit form's always) is left
//: alone: it has nothing to fold.
//: The index the fold starts from, worked out from positions read once: every item from it to the end
//: folds. `lefts[i]` is item i's left edge, or null when it takes no room (hidden). Folding items i..end
//: leaves the group (`toolsLeft`) where the first of them with room stood, so the row fits when the
//: group's right edge, moved left by that much, is inside `edge`. A margin between items is not in
//: `lefts` (measured: three of 94 widths folded one tool too many without it), so the start is one item
//: short of what the positions say, and the caller folds one at a time from there to exactly the old row.
//: `lefts.length` means nothing folds.
//: A property of `fitDocToolbarRow`, its only caller (one global name fewer).
fitDocToolbarRow.foldFrom = function (lefts, toolsLeft, toolsRight, edge) {
  if (toolsRight <= edge + 0.5) return lefts.length;
  let next = null;
  for (let i = lefts.length - 1; i >= 0; i--) {
    if (lefts[i] !== null) next = lefts[i];
    if (next !== null && toolsRight - (toolsLeft - next) <= edge + 0.5) return Math.min(i + 1, lefts.length);
  }
  return 0;
};

function fitDocToolbarRow(bar) {
  const tools = bar.querySelector(":scope > .doc-toolbar-tools");
  const more = tools?.querySelector(".doc-toolbar-more");
  if (!tools || !more) return;
  //: **A strip nobody can see is fitted when it is shown** (INBOX 1716 lag log, 489 ms): fitting writes
  //: classes and then reads, a style pass and a layout of the page, 120 ms a strip with the Library Images
  //: tab drawn at 4x. The width observer sees a hidden strip go from 0 to its width and fits it then.
  //: Read before any write, so it costs nothing when the page is clean.
  if (!bar.getClientRects().length) return;
  const items = [...bar.children].filter((el) => el !== tools);
  const open = bar.classList.contains("is-more-open");
  //: Measured as the closed row, whatever the reader has open: what fits is
  //: a fact about the row, and the open state is put back afterwards.
  bar.classList.remove("is-more-open", "is-layout-folded");
  for (const el of items) el.classList.remove("doc-toolbar-over");
  more.hidden = true;
  const style = getComputedStyle(bar);
  const measurable = bar.getClientRects().length > 0 &&
    !bar.classList.contains("is-collapsed") &&
    style.flexWrap === "nowrap";
  if (measurable) {
    const box = bar.getBoundingClientRect();
    const edge = box.right -
      parseFloat(style.paddingRight) - parseFloat(style.borderRightWidth);
    const fits = () => tools.getBoundingClientRect().right <= edge + 0.5;
    if (!fits()) {
      more.hidden = false;
      //: **On a narrow strip the layout toggle is the first thing folded**
      //: (INBOX 426 a, round 2). At 360 the strip's own group (More,
      //: layout, line numbers, collapse) took 176 of a 300px row and left
      //: room for two tools. The layout toggle is the one of the four a
      //: reader sets once, so under 600px it goes behind More with the
      //: tools, and comes back on the open strip's last row. Only when
      //: something is folded anyway: a strip whose tools all fit keeps it,
      //: so it is never out of reach.
      //: A note strip has no layout toggle to fold (INBOX 616).
      if (box.width < 600 && !bar.classList.contains("note-toolbar")) bar.classList.add("is-layout-folded");
      //: **Folded in one batch, then checked** (INBOX 1716 lag log, 489 ms): a class and a
      //: width read per item is a style pass and a layout each, 2 to 10 ms a pass with the
      //: Library Images tab drawn. The positions are read once and the batch is what they say
      //: must fold; any item still over after it folds one at a time, as before.
      const fold = (el) => {
        el.classList.add("doc-toolbar-over");
        //: A menu folded while open would stay open with nothing to anchor
        //: it: closed with its button.
        if (el.tagName === "DETAILS" && !open) el.open = false;
      };
      const lefts = items.map((el) => (el.getClientRects().length ? el.getBoundingClientRect().left : null));
      const row = tools.getBoundingClientRect();
      const from = fitDocToolbarRow.foldFrom(lefts, row.left, row.right, edge);
      for (let i = items.length - 1; i >= from; i--) fold(items[i]);
      for (let i = from - 1; i >= 0 && !fits(); i--) fold(items[i]);
      const shown = items.filter((el) => !el.classList.contains("doc-toolbar-over"));
      for (let i = shown.length - 1; i >= 0 && shown[i].classList.contains("doc-toolbar-sep"); i--) {
        shown[i].classList.add("doc-toolbar-over");
      }
    }
  }
  if (open && !more.hidden) bar.classList.add("is-more-open");
  syncDocToolbarMore(bar);
  trimDocToolbarGroup(bar, style);
}

//: **The strip's own group never takes a row to itself** (INBOX 426, round 4,
//: A3). Expanded at 1024, the document strip's two rows of tools filled to
//: 657 and 685 of 726px and its own three buttons (layout, line numbers,
//: collapse) went down to a third row alone: a row of chrome under the tools
//: it is chrome for. Two of the three have a row of their own in the
//: document's ⋯ menu ("Use one row", "Always show formatting"), so on the
//: document strip, when the group would be alone, those two are left to the
//: menu and line numbers stays, which fits the second row's tail. Only the
//: document strip: a note's strip has no menu holding the other two. Put
//: back first and measured again on every fit, so a wider window gets them
//: back.
//:
//: Where it goes then: the end of the first row, if that row has the room
//: (the window-controls corner, and measured at 1024 the first row had 69px
//: free where the trimmed group needs 48), else the end of the last. The
//: group is put back at the end of the strip before every fit, so the
//: one-row mode, which measures it there, always finds it there.
function trimDocToolbarGroup(bar, style = getComputedStyle(bar)) {
  const tools = bar.querySelector(":scope > .doc-toolbar-tools");
  if (!tools) return;
  bar.classList.remove("is-group-trimmed");
  if (bar.lastElementChild !== tools) bar.appendChild(tools);
  if (bar.id !== "doc-toolbar" || style.flexWrap === "nowrap") return;
  if (!bar.getClientRects().length || bar.classList.contains("is-collapsed")) return;
  const shown = () => [...bar.children].filter((el) => el !== tools && el.getClientRects().length);
  //: Rows counted by the bottom of each item's line: the tallest item sets
  //: it, and items centred on one row share it to within a pixel or two.
  const rowTops = () => {
    const bottoms = [...bar.children].filter((el) => el.getClientRects().length)
      .map((el) => el.getBoundingClientRect().bottom).sort((a, b) => a - b);
    let count = 0;
    let edge = -Infinity;
    for (const bottom of bottoms) if (bottom > edge + 12) { count += 1; edge = bottom; }
    return { size: count };
  };
  const alone = () => {
    const items = shown();
    const last = items[items.length - 1];
    return Boolean(last) && tools.getBoundingClientRect().top >= last.getBoundingClientRect().bottom - 1;
  };
  if (!alone()) return;
  const rowsBefore = rowTops().size;
  bar.classList.add("is-group-trimmed");
  //: Rows are told apart by where an item's middle falls, not by its top:
  //: the strip centres items of different heights, so two on one row can
  //: have tops a few pixels apart.
  const items = shown();
  const first = items[0]?.getBoundingClientRect();
  if (!first) return;
  const middle = (el) => { const r = el.getBoundingClientRect(); return (r.top + r.bottom) / 2; };
  const secondRow = items.find((el) => middle(el) > first.bottom);
  if (!secondRow) return;
  bar.insertBefore(tools, secondRow);
  const onFirst = middle(tools) < first.bottom;
  if (!onFirst || rowTops().size >= rowsBefore) bar.appendChild(tools);
}

//: More says what pressing it does and how many tools it holds, and carries
//: its state on `aria-expanded`, the disclosure's own attribute.
function syncDocToolbarMore(bar) {
  const more = bar.querySelector(".doc-toolbar-more");
  if (!more) return;
  const open = bar.classList.contains("is-more-open");
  const count = bar.querySelectorAll(".doc-toolbar-over:not(.doc-toolbar-sep)").length +
    (bar.classList.contains("is-layout-folded") ? 1 : 0);
  more.setAttribute("aria-expanded", String(open));
  more.setAttribute("aria-pressed", String(open));
  more.title = open
    ? "Fold the extra tools away again"
    : `${count} more tool${count === 1 ? "" : "s"}`;
  more.setAttribute("aria-label", more.title);
  markDocToolbarSepEdges(bar);
}

//: **A group rule never starts or ends a row** (the owner at release: "there
//: is a vertical divider line at the start of the second row"). A wrapped
//: strip breaks wherever the width runs out, which is often right after a
//: rule, so the next row opened with one. Hidden rather than removed
//: (visibility, not display): taking its width away could pull the next
//: tool back up a row and move the break it was marking. All writes first,
//: then all reads, then the writes they decide, so one pass lays out once.
function markDocToolbarSepEdges(bar) {
  const kids = [...bar.children];
  for (const el of kids) el.classList.remove("doc-toolbar-sep-edge");
  const shown = kids.filter((el) => el.getClientRects().length > 0);
  const mids = shown.map((el) => {
    const box = el.getBoundingClientRect();
    return box.top + box.height / 2;
  });
  const newRow = (i) => i === 0 || Math.abs(mids[i] - mids[i - 1]) > 12;
  const edges = shown.filter((el, i) => el.classList.contains("doc-toolbar-sep") &&
    (newRow(i) || i === shown.length - 1 || newRow(i + 1)));
  for (const el of edges) el.classList.add("doc-toolbar-sep-edge");
}

//: Refitted whenever a strip's width changes, and only then: the observer
//: also fires when More makes the strip taller, and that is not a reason to
//: measure again. A strip that was hidden and is shown (the tab, focus mode's
//: Tools, the collapse) goes from 0 to its width, which counts. The width is
//: kept on the strip itself and cleared here, because the note edit form's
//: strip is a clone of the capture strip and would otherwise arrive carrying
//: the width it was cloned at, and never be measured. Hoisted state only (a
//: property of this function, a data attribute): the appliers above can run
//: before this part of the file has, and a `let` here would be in its
//: temporal dead zone for them.
function watchDocToolbarWidth(bar) {
  if (typeof ResizeObserver !== "function") return;
  watchDocToolbarWidth.observer ||= new ResizeObserver((entries) => {
    for (const entry of entries) {
      const width = String(Math.round(entry.contentRect.width));
      if (entry.target.dataset.fitWidth === width) continue;
      entry.target.dataset.fitWidth = width;
      fitDocToolbarRow(entry.target);
    }
  });
  delete bar.dataset.fitWidth;
  watchDocToolbarWidth.observer.observe(bar);
  watchDocToolbarContents(bar);
}

//: **Refitted when the row's contents change, too** (INBOX 426 a, round 2).
//: A width is not the only thing that decides what fits: the extras
//: (`mountEditorToolbarExtras`) are appended after the strip is first
//: measured, and a control shown or hidden at a constant width (by file
//: type, by a setting) moves the end of the row without resizing the strip,
//: so the row stayed folded for tools that had gone, or ran under the end
//: group for tools that had come, until the next resize.
//:
//: The observer sees every attribute change in the strip, and most of them
//: are no reason to measure: the bold button gains `active` on every cursor
//: move, and the fit itself folds tools with a class. So each change is
//: reduced to a signature of what the row lays out (which direct children
//: exist and whether each is hidden by the page, not by the fit) and the
//: strip is refitted only when that signature moved, once per frame at most.
function docToolbarLayoutSignature(bar) {
  let sig = "";
  for (const el of bar.children) {
    if (el.classList.contains("doc-toolbar-tools")) continue;
    const gone = el.hidden || el.classList.contains("hidden") || el.style.display === "none";
    sig += `${el.tagName[0]}${gone ? 0 : 1}${el.textContent.length},`;
  }
  return sig;
}

function watchDocToolbarContents(bar) {
  if (typeof MutationObserver !== "function") return;
  //: Kept in a set, not marked on the element: the note edit form's strip is
  //: a clone of the capture strip and a data attribute would arrive with it,
  //: so the clone would think it was already watched. A property of this
  //: function, for the same hoisting reason as the width observer's.
  //: A map from the strip to its observer (audit 1028 D37): the handle is kept, not dropped.
  watchDocToolbarContents.seen ||= new WeakMap();
  if (watchDocToolbarContents.seen.has(bar)) return;
  let sig = docToolbarLayoutSignature(bar);
  let queued = false;
  const observer = new MutationObserver(() => {
    if (queued) return;
    queued = true;
    requestAnimationFrame(() => {
      queued = false;
      const next = docToolbarLayoutSignature(bar);
      if (next === sig) return;
      sig = next;
      fitDocToolbarRow(bar);
    });
  });
  watchDocToolbarContents.seen.set(bar, observer);
  observer.observe(bar, {
    childList: true,
    subtree: true,
    characterData: true,
    attributes: true,
    attributeFilter: ["hidden", "class", "style"],
  });
}

function fitDocToolbars() {
  //: The reads first: a strip's fit writes classes, and the next strip's visibility read would pay for them.
  const shown = [...document.querySelectorAll(".doc-toolbar")].filter((bar) => bar.getClientRects().length);
  for (const bar of shown) fitDocToolbarRow(bar);
}

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

// --- the status bar -----------------------------------------------------------


//: Line and column are 1-based, because that is what every editor and every
//: error message in the world means by them.
//: **Asked of the surface, not counted from the start of the document.**
//: This used to slice the text up to the caret and split it on newlines,
//: which is a whole-document pass on every keystroke *and* on every caret
//: move. CodeMirror keeps a line index and answers in O(log n); the fallback
//: textarea's own `lineAt` does the same slice it always did, on the only
//: surface that has no better answer. Measured on the plan's 20k-word
//: document: this and the two passes below were what stood between the
//: engine and the 30 ms gate once the block renderer was gone.
function docCaretStats(box) {
  const range = box.selection();
  const line = box.lineAt(range.from);
  const selected = range.to - range.from;
  //: **Words in the selection, not just characters.** Asked for: "I want
  //: more utility in the documents editor like being able to highlight a
  //: paragraph or set of text and see the amount of words". It belongs on
  //: this line rather than beside the document's own totals, because this
  //: is the half of the status bar that reruns on every selection change;
  //: `renderDocCounts` is deliberately debounced behind `scheduleDocFacts`
  //: and a selection count that lagged the selection would be worse than
  //: none. Counted only when there is a selection to count, so the common
  //: case (a caret, no range) still does no work at all.
  const words = selected ? docPlainText.counts(docCommentStrip(box.text.slice(range.from, range.to))).words : 0;
  //: **How far through** (L-documents-67, DOCUMENTS_PLAN 17d): the caret's line of the last line, said only from 200 lines up, where a
  //: document scrolls for a while and a page or two of prose is not worth a figure. The last line is asked of the surface
  //: (`lineAt` clamps), so it costs the line index and no more.
  const last = box.lineAt(Infinity).number;
  return {
    line: line.number,
    column: range.from - line.from + 1,
    selected,
    selectedWords: words,
    through: last >= 200 ? Math.round((line.number / last) * 100) : -1,
  };
}

//: **A status line's words are changed in place, never replaced.** Traced
//: while typing into a 400-word document (scratchpad/ui-sweeps/scrolltrace.js,
//: SCENE=typing-doc): every keystroke restyled the whole editor, 220 elements
//: at 6 to 9ms a time, and the invalidation tracking named the cause as the
//: caret readout's `textContent` write. Setting `textContent` removes the
//: text node and inserts a new one, and an inserted node is a structural
//: change that every `:has()` rule over an ancestor has to re-check (the
//: editor sits inside `.card`, which `.card:has(details.dock-menu[open])`
//: watches), so the check invalidated the `.doc-layout` subtree each time.
//: Rewriting the existing text node's `data` is not a structural change, and
//: nothing re-checks.
function docSetStatusText(el, text) {
  if (!el) return;
  const node = el.firstChild;
  if (node && node.nodeType === Node.TEXT_NODE && !node.nextSibling) {
    if (node.data !== text) node.data = text;
  } else if (el.textContent !== text) {
    el.textContent = text;
  }
}

//: The caret half of the status bar: cheap, and so run on every keystroke and
//: every selection change.
function renderDocCaret() {
  const box = docActiveBox();
  const caret = $("doc-caret");
  if (!box || !caret) return;
  //: **One set of coordinates now.** This used to have a second branch that
  //: translated a live-view paragraph's own offsets into the document's,
  //: because Live gave every paragraph its own box and a line number counted
  //: inside one of them was a lie about the document. With Live and Source as
  //: one editor there is nothing to translate, and the bar can no longer say
  //: "In a paragraph" because there is no paragraph to be lost in.
  const stats = docCaretStats(box);
  //: Words first: selecting a paragraph is almost always a question about
  //: its length, and the character count is the supporting detail. A
  //: selection inside one word has no word count worth printing, so it
  //: falls back to characters alone.
  const selection = !stats.selected
    ? ""
    : stats.selectedWords
      ? ` · ${stats.selectedWords.toLocaleString()} word${
          stats.selectedWords === 1 ? "" : "s"
        } selected (${stats.selected.toLocaleString()} char${stats.selected === 1 ? "" : "s"})`
      : ` · ${stats.selected.toLocaleString()} char${stats.selected === 1 ? "" : "s"} selected`;
  const through = stats.through >= 0 ? ` · ${stats.through}%` : "";
  docSetStatusText(caret, `Ln ${stats.line}, Col ${stats.column}${through}${selection}`);
  //: The breadcrumb follows the caret, so it is drawn from the same stats
  //: rather than from a listener of its own: two things that answer "where am
  //: I" and update on different events are two things that disagree.
  renderDocCrumbs(stats.line - 1);
  docRememberPosition();
  renderDocToolbarState();
}

//: **Which formatting buttons are on for the caret** (DOCUMENTS_PLAN Phase 2,
//: the third of the three things the engine phase deliberately left out:
//: "which buttons are 'on' for the caret's position is not driven from the
//: syntax tree, which the tree now makes cheap").
//:
//: It was never built because before the engine there was no tree to ask: a
//: textarea's value is a string, and deciding whether the caret is inside
//: `**bold**` meant counting asterisks from the top of the document on every
//: keystroke. The tree already exists for the decorations, and this walks one
//: node's ancestors, so the cost is the depth of the markdown at the caret and
//: not the length of the document.
//:
//: A lezer node name to the `data-md` of the button that writes it. Only the
//: marks a caret can be *inside*: Link is here because a caret in `[text](x)`
//: is inside a Link node, while the buttons that always insert something new
//: (a divider, a table, a colour) have no state to be in and are left alone,
//: which is also why `aria-pressed` is set on these and on nothing else. A
//: button that is not a toggle must not claim to be one to a screen reader.
const DOC_TOOLBAR_MARKS = {
  StrongEmphasis: "bold",
  Emphasis: "italic",
  Strikethrough: "strike",
  InlineCode: "code",
  FencedCode: "code",
  ATXHeading1: "h1",
  ATXHeading2: "h2",
  ATXHeading3: "h3",
  BulletList: "ul",
  OrderedList: "ol",
  Blockquote: "quote",
  Link: "link",
  Task: "task",
};

//: The `data-md` values this can answer for, so a button outside the set is
//: never touched rather than being told it is off.
const DOC_TOOLBAR_STATEFUL = new Set(Object.values(DOC_TOOLBAR_MARKS));

function docToolbarMarksAt(CM, state) {
  const marks = new Set();
  const { syntaxTree } = CM.language;
  //: **`-1`, the side the caret came from.** With `1`, a caret just past the
  //: final `d` of `**bold**` resolves to whatever follows the emphasis and
  //: Bold reads as off at the exact moment a writer is still typing the word.
  //: Asking for the node on the left is what makes "keep typing in bold" and
  //: "the button says bold" the same answer.
  const head = state.selection.main.head;
  //: A blank line is inside nothing: resolving left of it lands in the item above.
  if (!state.doc.lineAt(head).text.trim()) return marks;
  let node = syntaxTree(state).resolveInner(head, -1);
  while (node) {
    const mark = DOC_TOOLBAR_MARKS[node.name];
    if (mark) marks.add(mark);
    node = node.parent;
  }
  //: A task list *is* a bullet list in the grammar, so both would light and
  //: the bar would claim two list kinds at once. The more specific one wins,
  //: which is also the one pressing the button again would turn off.
  if (marks.has("task")) marks.delete("ul");
  return marks;
}

function renderDocToolbarState() {
  const bar = $("doc-toolbar");
  //: Only the document's own strip. The capture composer's clone carries the
  //: same `data-md` buttons and a different caret, and lighting it from this
  //: view would be a bar describing a document nobody is looking at.
  if (!bar || !docCmView || !window.CM6) return;
  let marks;
  try {
    marks = docToolbarMarksAt(window.CM6, docCmView.state);
  } catch {
    //: A tree that is not ready yet answers nothing rather than throwing on
    //: the beat of every arrow key. The next selection change asks again.
    return;
  }
  for (const button of bar.querySelectorAll("button[data-md]")) {
    if (!DOC_TOOLBAR_STATEFUL.has(button.dataset.md)) continue;
    const on = marks.has(button.dataset.md) ? "true" : "false";
    //: Only on a change: this runs on every keystroke, over 51 buttons (the
    //: strip and its menus), and an attribute set to the value it already
    //: had is still a mutation the style engine has to look at.
    if (button.getAttribute("aria-pressed") !== on) button.setAttribute("aria-pressed", on);
  }
}

//: The lines a reader sees: `textCounts(...).lines` is `wc -l` (newlines), so a
//: last line with no newline after it is one more, and an empty text has none.
function docLineCount(text) {
  const value = String(text || "");
  if (!value) return 0;
  return textCounts(value).lines + (value.endsWith("\n") ? 0 : 1);
}

//: What a code file's status bar says: the lines, the characters and the
//: language, in that order. Words and a reading time are about prose; a
//: `.py` file has neither a reader nor a word count worth a bar's room. The
//: same two counters as the prose line (`docLineCount`, `textCounts`).
function docCodeCountsText(text, label) {
  const lines = docLineCount(text);
  const { chars } = textCounts(String(text || ""));
  return [`${lines.toLocaleString()} line${lines === 1 ? "" : "s"}`, `${chars.toLocaleString()} char${chars === 1 ? "" : "s"}`, label]
    .filter(Boolean)
    .join(" · ");
}

const DOC_COUNTS_TITLE_PROSE = "Characters, words, lines and roughly how long this takes to read. Press for the full statistics";
const DOC_COUNTS_TITLE_CODE = "Lines, characters and the language. Press for the full statistics";

//: A code file's counts, drawn. Decided the way `docProseChord` decides: by the
//: file type's own `previewable`, through `docIsCodeFile`, so a `.txt` or a
//: `.csv` keeps the prose line it is read as.
function renderDocCodeCounts(counts) {
  const text = docText();
  counts.textContent = docCodeCountsText(text, docFileType().label);
  counts.title = DOC_COUNTS_TITLE_CODE;
  if (docFocusOn()) {
    const lines = docLineCount(text);
    docSetStatusText($("doc-focus-words"), lines ? `${lines.toLocaleString()} line${lines === 1 ? "" : "s"}` : "");
    docSetStatusText($("doc-focus-title"), $("doc-title")?.value.trim() || "Untitled");
  }
}

//: The counts. A whole-document pass, which is why it is scheduled rather
//: than run on the keystroke (see `scheduleDocFacts`).
function renderDocCounts() {
  const counts = $("doc-counts");
  if (!counts) return;
  if (docIsCodeFile()) return renderDocCodeCounts(counts);
  counts.title = DOC_COUNTS_TITLE_PROSE;
  //: **A remark is not prose you wrote for a reader**, so it is not in the
  //: count, the character total or the reading time. Measured on a 128-word
  //: document with two comments in it: 134 words counted before this, 128
  //: after, which is the number the same document's Read view shows.
  //: Counted by `textCounts` (settings-wiring.js), the one count the
  //: composer, this bar and the server share: characters are code points, as
  //: `wc -m` counts them, so an emoji is one, not two.
  const stripped = docCommentStrip(docText());
  const { words, read } = docPlainText.counts(stripped);
  const { chars } = textCounts(stripped);
  const lines = docLineCount(stripped);
  //: Characters first, because that is the one the existing header line never
  //: showed and the one that was asked for by name. Lines (OPEN ledger 299)
  //: come before the reading time, which is what a phone's ellipsis drops
  //: first.
  counts.textContent = [
    `${chars.toLocaleString()} char${chars === 1 ? "" : "s"}`,
    `${words.toLocaleString()} word${words === 1 ? "" : "s"}`,
    lines ? `${lines.toLocaleString()} line${lines === 1 ? "" : "s"}` : "",
    read,
  ]
    .filter(Boolean)
    .join(" · ");
  //: The day's tally and streak read the same count (the writing-streak block above).
  counts.dispatchEvent(new CustomEvent("doc:counted", { detail: { id: currentDoc?.id ?? null, words } }));
  //: Focus mode's floating dock carries the count too, since the status bar
  //: is hidden while it is on; and the title, which is how a document opened
  //: from the palette while the mode is on relabels the dock.
  if (docFocusOn()) {
    docSetStatusText($("doc-focus-words"), words ? `${words.toLocaleString()} word${words === 1 ? "" : "s"}` : "");
    docSetStatusText($("doc-focus-title"), $("doc-title")?.value.trim() || "Untitled");
  }
}

function renderDocStatusBar() {
  renderDocCaret();
  renderDocCounts();
}

//: **The facts about the whole document, on a pause rather than on a
//: keystroke.**
//:
//: The word goal, the outline and the status bar's counts each walk the
//: entire text. On the plan's 20k-word document that is three passes over
//: 130,000 characters per character typed, and it is most of what was left
//: between the editor and PLAN P4's 30 ms gate once the Live view stopped
//: rebuilding a thousand blocks. None of the three is *state*: they are
//: readouts, and a readout that lands 120 ms after you stop typing is a
//: readout nobody notices arriving late. Exactly the argument
//: `scheduleDocPreview` already makes a few storeys up, and the same shape:
//: a trailing debounce, then an idle callback with a ceiling so a busy tab
//: still repaints within a third of a second.
//:
//: Anything that needs them *now* (opening a document, a restore, a view
//: switch) still calls the three directly.
let docFactsTimer = null;
//: Set when a pass was due while the Documents tab was hidden; the next visit
//: runs it (`loadDocuments`), so nothing is out of date when it is seen again.
let docFactsStale = false;
let docFactsIdle = 0;

//: `typed`: the pause after typing, which skips the outline while every edit
//: since the last pass left the heading, fence and task lines alone
//: (`runDocFacts.outlineSame`, kept by `docCmUpdate`; DX1). Any other caller
//: draws everything.
function runDocFacts(typed = false) {
  docFactsStale = false;
  const outlineSame = typed && runDocFacts.outlineSame === true;
  runDocFacts.outlineSame = undefined;
  renderDocStats();
  if (!outlineSame) renderDocOutline();
  renderDocCounts();
  renderDocComments();
  //: The properties panel is drawn from the frontmatter's own text and
  //: redraws only when that text moves, so it costs one parse of the top
  //: of the document per pause in the typing.
  renderDocProperties();
}

//: **A big document waits longer for its facts** (audit 1031 row 23 CE3, audit
//: 1028 D20). The outline, counts and word goal are whole-document passes: at
//: 120 ms a pause they ran between nearly every burst of keys in a 7,000-line
//: file, and in a 20,000-word document (130,000 characters) one pass is about
//: 17 ms, so a steady typist paid it on every key. The wait grows with the
//: text, so the cost lands once after a burst; a short document keeps 120.
function docFactsDelay() {
  const len = docCmView ? docCmView.state.doc.length : 0;
  return len > 120000 ? 600 : len > 40000 ? 300 : 120;
}

function scheduleDocFacts() {
  clearTimeout(docFactsTimer);
  //: **A key cancels a pass still waiting** (DX1): the idle callback had a
  //: 300 ms ceiling, so on a slow machine it ran between two keys of the same
  //: burst, which is exactly when it was meant not to. Now it waits for a
  //: real pause and for an idle moment, and the next key withdraws it.
  if (docFactsIdle) {
    cancelIdleCallback(docFactsIdle);
    docFactsIdle = 0;
  }
  //: And never sooner than one and a half of this typist's own gap between
  //: keys (`gap`, kept by `docToolsOnInput`), so a slow machine's long keys
  //: are not pauses.
  const gap = scheduleDocFacts.gap || 0;
  docFactsTimer = setTimeout(() => {
    docFactsTimer = null;
    const run = () => {
      //: **Not while nobody can see it** (audit 1028 D20). A change that lands
      //: with another tab in front (a sync, a restore, the AI's edit arriving)
      //: used to rebuild the stats, outline, counts, comments and properties
      //: for a hidden page: measured 65 ms of work on a 20k-word document per
      //: change. Marked stale instead, and run once on the way back in.
      if ($("tab-documents")?.classList.contains("hidden")) {
        docFactsStale = true;
        return;
      }
      runDocFacts(true);
    };
    //: One queued pass at most: a second pause that arrives before the idle
    //: callback has run replaces it, so a busy tab does not stack two.
    if (typeof requestIdleCallback === "function") {
      if (docFactsIdle) cancelIdleCallback(docFactsIdle);
      docFactsIdle = requestIdleCallback(() => {
        docFactsIdle = 0;
        run();
      });
    } else requestAnimationFrame(run);
  }, Math.max(docFactsDelay(), Math.min(600, 1.5 * gap)));
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

//: **"whats" is "what's" with the apostrophe left out** (the owner,
//: 2026-10-19: "this should have been picked up as what's"). The word list
//: keeps "what" and drops the "'s" (`docWordKnown`), so no edit of "whats"
//: reaches it. Offered first in the menu only, never as the sure answer:
//: an apostrophe is a style choice (`DOC_AUTOCORRECT`), so typing never
//: rewrites it on its own.
const DOC_CONTRACTION_BASES = {
  re: new Set(["you", "we", "they", "who", "what", "there"]),
  ll: new Set(["i", "you", "we", "they", "he", "she", "it", "that", "there", "who", "what"]),
  ve: new Set(["i", "you", "we", "they", "who", "would", "could", "should", "might", "must"]),
  d: new Set(["i", "you", "we", "they", "he", "she", "it", "that", "there", "who"]),
  m: new Set(["i"]),
};

function docSpellContraction(lower) {
  if (/['\u2019]/.test(lower)) return null;
  if (lower.endsWith("nt") && docWordlist.has(`${lower.slice(0, -2)}n't`)) return `${lower.slice(0, -2)}n't`;
  for (const [tail, bases] of Object.entries(DOC_CONTRACTION_BASES)) {
    if (lower.endsWith(tail) && bases.has(lower.slice(0, -tail.length))) return `${lower.slice(0, -tail.length)}'${tail}`;
  }
  if (lower.length > 3 && lower.endsWith("s") && docWordlist.has(lower.slice(0, -1)) && /^(?:what|that|there|here|who|where|when|how|it|he|she|let)$/.test(lower.slice(0, -1))) {
    return `${lower.slice(0, -1)}'s`;
  }
  return null;
}

//: **The one answer, or none.** A correction this app is willing to make
//: without being asked, or to put behind a single check button, has to be the
//: only candidate of its kind: exactly one real word reachable by a swap of
//: two letters or by dropping one, and nothing else that close. "tets" has
//: exactly one ("test"); "tho" has several and gets a menu instead. Short
//: words are refused outright because almost every three-letter string is one
//: edit from several real words.
const DOC_CONFIDENT_MIN = 4;

function docSpellConfident(word) {
  if (!docWordlist) return null;
  const lower = docSpellRoot(word);
  if (lower.length < DOC_CONFIDENT_MIN) return null;
  const swaps = [];
  const drops = [];
  for (const [candidate, rank] of docEditsOnce(lower)) {
    if (rank > DOC_EDIT_DROP) continue;
    if (!docWordlist.has(candidate)) continue;
    (rank === DOC_EDIT_SWAP ? swaps : drops).push(candidate);
  }
  //: A swap outranks a dropped letter rather than competing with it. "tets"
  //: has one of each ("test" and "tet", the Vietnamese new year), and
  //: treating those as a tie left the app with no opinion about the most
  //: ordinary typo there is.
  if (swaps.length === 1) return swaps[0];
  if (!swaps.length && drops.length === 1) return drops[0];
  return null;
}

//: Is this word one swap of two letters from exactly one real word? The test a
//: capitalised word in mid-sentence has to pass to be called a typo and not a
//: name (`docSpellNameKind`).
function docSpellTransposed(word) {
  if (!docWordlist) return false;
  const lower = docSpellRoot(word);
  if (lower.length < DOC_CONFIDENT_MIN) return false;
  let swaps = 0;
  for (const [candidate, rank] of docEditsOnce(lower)) {
    if (rank === DOC_EDIT_SWAP && docWordlist.has(candidate)) swaps += 1;
  }
  return swaps === 1;
}

//: One answer per word rather than per occurrence. A document says the same
//: word many times, the answers cannot change between two of them inside one
//: pass, and the generation above is the most expensive thing the checker
//: does. Cleared when the dictionary changes, which is the only thing that
//: can change an answer.
let docSpellCache = new Map();

function docSpellLookup(word) {
  const key = docSpellRoot(word);
  let answer = docSpellCache.get(key);
  if (answer === undefined) {
    answer = { known: docWordKnown(word), sure: null };
    //: **The second opinion** (INBOX 1731): a word this list does not know is
    //: put to the worker's Hunspell dictionary and to the person's own words.
    //: Until it answers the word is not called a typo, and that answer is not
    //: kept, so the next pass asks again.
    if (!answer.known) {
      const second = docSpell.answer(key);
      if (second) answer.known = second.known;
      else if (docSpell.want(key)) return { known: true, sure: null };
    }
    if (!answer.known) answer.sure = docSpellConfident(word);
    //: Bounded, because a pathological document must not grow this without
    //: limit: cleared wholesale rather than evicted one at a time, which
    //: costs one rebuild on a document with more than 5,000 distinct words.
    if (docSpellCache.size > 5000) docSpellCache.clear();
    docSpellCache.set(key, answer);
  }
  return answer;
}

//: Spans of the document the prose rules do not read. A fenced block is code,
//: an inline span in backticks is code, a URL is an address and a markdown
//: link's destination is a path: none of them is prose, and every one of them
//: is full of things that look like misspellings and missing spaces. Without
//: this a real dictionary would put a red underline under every identifier in
//: a code sample, which is the single fastest way to make a writer turn the
//: whole check off.
//:
//: A byte mask rather than a list of ranges because the test is asked once
//: per finding and once per word: a linear scan of ranges per word is the
//: shape that makes a long document slow.
const DOC_PROSE_SKIP = [
  /(^|\n)[ \t]*(```|~~~)[^\n]*\n[\s\S]*?(\n[ \t]*\2[^\n]*|$)/g, // fenced code
  /`[^`\n]+`/g, // inline code
  /\b(?:https?:\/\/|ftp:\/\/|mailto:|www\.)\S+/g, // addresses
  /\]\([^)\n]*\)/g, // a markdown link's destination
  /^\[[^\]\n]+\]:\s*\S+/gm, // a reference link's definition
  /<\/?[A-Za-z][^>\n]*>/g, // an html tag
  /\[\[[^\]\n]*\]\]/g, // a note link: the title is a name, not prose
  //: A callout's own marker. `> [!note]` is syntax, and the space before its
  //: "!" was being reported as a space before punctuation on every callout in
  //: every document.
  /^[ \t]*>[ \t]*\[![A-Za-z]+\]/gm,
  /^---\n[\s\S]*?\n---/g, // frontmatter
  //: Suggestion mode's marks (PROSE-TOOLS): a word proposed for deletion is
  //: on its way out and not worth a finding, and the markers are syntax.
  /\{--[\s\S]*?--\}/g,
  /\{\+\+|\+\+\}/g,
  //: **Things that are not prose** (INBOX 1357, K11; measured on
  //: `tests/grammar_fixture_1026.json`): an email address, a file path and a
  //: file name, and a unit written after a number. Harper read `/etc/nginx/
  //: conf.d` as "config" and `uni` as a negative prefix, and called "min" and
  //: "mL" words to fix; the dictionary read the host of an address.
  /(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)+/g, // an email address
  /(?<![\w/.:])(?:~|\.{1,2})?(?:\/[\w.\-@+~%]+)+\/?/g, // /etc/hosts, ~/notes/a.md
  /(?<![\w/.-])[\w.-]+(?:\/[\w.-]+){2,}\/?/g, // src/app/main.py
  /(?<![\w/-])[\w-]+\/[\w-]+\.[A-Za-z0-9]{1,5}\b/g, // docs/readme.md
  /\b[A-Za-z]:\\[^\s"'<>|]*/g, // C:\Users\me\notes.txt
  /(?<![\w-])[\w-]+\.(?:md|txt|pdf|png|jpe?g|gif|svg|csv|docx?|xlsx?|pptx?|html?|css|js|ts|py|json|ya?ml|toml|sh|zip)\b/gi, // a file name
  //: A unit straight after a number is a unit and not a word: 10 min, 2 h,
  //: 250 ms, 15 mL, 5 km, 3 x 4, 10am, 3rd, 90%, 37 °C. The number is not
  //: masked, the unit is; a unit with no number before it is prose.
  /(?<=\d)[ \u00a0]?(?:min|mins|h|hr|hrs|sec|secs|s|ms|ns|kg|g|mg|km|m|cm|mm|ml|l|kb|mb|gb|tb|khz|mhz|ghz|hz|kw|w|v|mv|ma|px|pt|dpi|fps|rpm|mph|lb|lbs|oz|ft|kcal|cal|kj|mol|db|x|am|pm|st|nd|rd|th)\b/gi,
  /(?<=\d)[ \u00a0]?(?:%|°[CFKcfk]?|℃|℉)/g,
];

//: **The words of a link** are the writer's label for an address, a name or a
//: phrase pasted from somewhere ("something" in the owner's capture, K11), not
//: a sentence of theirs, so they are skipped like the address beside them.
//: `[text](address)`, `[text][ref]` and `![alt](source)`; not a `[[wiki link]]`
//: (masked above) and not a `[ ]` checkbox, which no `(` or `[` follows.
//: Settings, Writing, "Check link text" turns the check back on.
const DOC_PROSE_SKIP_LINK_TEXT = [/!?\[(?!\[)[^\][\n]*\](?=\([^)\n]*\)|\[[^\]\n]*\])/g];

//: **One mask per text** (prose-1101): the rule pass, the extras' filter and the
//: grammar answer each asked for the mask of the same string, three regex walks
//: for one result. `docProseSkipMask.memo` holds the last one, keyed by the
//: string and the link-text setting; a reader only reads it. The keystroke path
//: (`docProse.near`) stores the mask it assembled for the new text here too.
function docProseSkipMask(text) {
  const link = docCheckLinkText();
  const memo = docProseSkipMask.memo;
  if (memo && memo.link === link && memo.text === text) return memo.mask;
  const mask = new Uint8Array(text.length);
  docProseSkipMask.memo = { text, link, mask };
  const sources = link ? DOC_PROSE_SKIP : DOC_PROSE_SKIP.concat(DOC_PROSE_SKIP_LINK_TEXT);
  for (const source of sources) {
    //: A fresh regex per pass, for the reason the rules' own loop gives:
    //: `lastIndex` survives on a shared object and silently skips half the
    //: document on every second call.
    const pattern = new RegExp(source.source, source.flags);
    let match;
    while ((match = pattern.exec(text)) !== null) {
      if (!match[0].length) {
        pattern.lastIndex += 1;
        continue;
      }
      mask.fill(1, match.index, match.index + match[0].length);
    }
  }
  return mask;
}

//: Findings, in document order, each with the exact span it is about so the
//: panel can jump to it and the fix can replace it without searching for the
//: text again (which would find the wrong occurrence in a document that says
//: the same thing twice).
//: `lang` is the document's, read from its frontmatter; a paragraph passed alone (`docProse.near`)
//: has none, so the caller says it.
function docProseFindings(text, lang = docProse.langOf(text)) {
  const found = [];
  //: Kicked off here rather than at load: this is the first moment anything
  //: wants to know whether a word is a word. It returns immediately, and the
  //: pass that arrives with it re-runs this one. Not for an empty editor
  //: (audit 2026-10-05, FE-03): this file's last line paints the tools once
  //: at load, when no document is open, and that pass fetched the 871 KB
  //: word list on every first Library visit with nothing to check.
  if (text.trim()) docLoadWordlist();
  const skip = docProseSkipMask(text);
  //: A span is skipped when it starts inside code or an address. Its start
  //: rather than every character of it: a rule whose match straddles the end
  //: of a code fence is about the code, not the prose after it.
  const skipped = (at) => skip[at] === 1;
  const english = lang === "en";
  for (const rule of DOC_PROSE_RULES) {
    if (!rule.test) continue;
    //: English word lists (repeat, confusion) would misfire on another language.
    if (rule.english && !english) continue;
    //: A fresh regex per pass: these carry `g`, and `lastIndex` survives
    //: between calls on a shared object, which silently skips half the
    //: document on every second run.
    const pattern = new RegExp(rule.test.source, rule.test.flags);
    let match;
    while ((match = pattern.exec(text)) !== null) {
      if (!match[0].length) break; // a zero-width match would loop forever
      if (skipped(match.index)) continue;
      found.push({
        rule: rule.id,
        message: rule.message,
        start: match.index,
        end: match.index + match[0].length,
        text: match[0],
        replacement: rule.fix ? rule.fix(match[0]) : null,
        ...(rule.alternatives ? { alternatives: rule.alternatives(match[0]) } : {}),
      });
    }
  }
  //: Spelling, word by word, so the span is the word and not a substring of a
  //: longer one: a regex over the whole list would flag "ot" inside "not".
  const word = /[A-Za-z']+/g;
  const dictionary = docDictionary();
  const variants = docVariantLookup();
  //: Off for a document whose `lang` is not English (`docProse.langOf`): see `docProse.langNote`.
  const checkWords = english;
  let hit;
  while (checkWords && (hit = word.exec(text)) !== null) {
    if (skipped(hit.index)) continue;
    const lower = hit[0].toLowerCase();
    //: A word in the dictionary is a word. This is the whole point of having
    //: one: the third time a checker flags your project's name, a checker you
    //: cannot answer is a checker you turn off.
    if (dictionary.has(lower)) continue;
    const variant = variants.get(lower);
    if (variant) {
      found.push({
        rule: "variant",
        message: `${DOC_VARIANT_LABEL[docSpellingVariant()] || "US"} spelling: “${variant}”`,
        start: hit.index,
        end: hit.index + hit[0].length,
        text: hit[0],
        replacement:
          hit[0][0] === hit[0][0].toUpperCase()
            ? variant[0].toUpperCase() + variant.slice(1)
            : variant,
      });
      continue;
    }
    const better = DOC_AUTOCORRECT[lower];
    if (better) {
      found.push({
        rule: "spelling",
        message: `“${hit[0]}” is probably “${better}”`,
        start: hit.index,
        end: hit.index + hit[0].length,
        text: hit[0],
        //: Keeps the writer's capitalisation: a typo at the start of a
        //: sentence must not be corrected into a lowercase word.
        replacement: docMatchCase(hit[0], better),
      });
      continue;
    }
    //: A contraction that is also a word ("I cant go", "ill be there"): the
    //: neighbours decide (`autocorrectState.contextual`), and the word is
    //: known to the dictionary, so it is asked before the dictionary is.
    const said = autocorrectState.inText(text, hit.index, hit[0]);
    if (said) {
      found.push({
        rule: "spelling",
        message: `“${hit[0]}” is probably “${said}”`,
        start: hit.index,
        end: hit.index + hit[0].length,
        text: hit[0],
        replacement: said,
      });
      continue;
    }
    //: **Everything else, against the dictionary.** The table above is 42
    //: entries and keeps its place only because it carries the one certain
    //: answer for each of them; this is the check that makes the other
    //: several hundred thousand typos visible. Silent until the word list has
    //: loaded, because a checker that flags every word for a second and then
    //: takes it back is worse than one that waits.
    if (!docWordlistReady()) continue;
    if (!docSpellable(text, hit[0], hit.index, hit.index + hit[0].length)) continue;
    const nameKind = docSpellNameKind(text, hit[0], hit.index);
    if (nameKind === "name" && (docWordKnown(hit[0]) || !docSpellTransposed(hit[0]))) continue;
    const looked = docSpellLookup(hit[0]);
    if (looked.known) continue;
    if (nameKind === "initial" && !looked.sure) continue;
    //: The candidate list is *not* computed here. It costs the square of the
    //: work of one edit when one edit finds nothing, and computing it for
    //: every unknown word on every pass put `docProseFindings` at 29ms over a
    //: 276-character document (measured, 2026-09-12) when the whole pass has
    //: a 300ms budget from keystroke to underline. The menu computes it for
    //: the one word it is about, when it opens.
    //:
    //: The row claims an answer only when there is one to claim
    //: (`docSpellConfident`); otherwise it says what it knows, which is that
    //: the word is not in the dictionary, and the menu offers the candidates.
    //: Saying "probably" about the first of five would be picking one at
    //: random on the writer's behalf.
    const sure = looked.sure;
    found.push({
      rule: "spelling",
      message: sure
        ? `“${hit[0]}” is probably “${sure}”`
        : `“${hit[0]}” is not in the dictionary`,
      start: hit.index,
      end: hit.index + hit[0].length,
      text: hit[0],
      //: `replacement` is what "Fix all" applies without asking, so it is set
      //: only when there is nothing to choose between.
      replacement: sure ? docMatchCase(hit[0], sure) : null,
    });
  }
  //: Another language: its installed spelling pack answers in the worker (documents-spell.js, D30)
  //: and finds nothing until it has, or when no pack is installed.
  if (!english) found.push(...docSpell.packFindings(text, lang, skipped));
  //: Long sentences, measured over the prose only. Code fences and headings
  //: are skipped: a fenced block has no sentences, and a heading that runs
  //: long is a heading, not a run-on.
  //: Headings, list items and table rows are blanked first (same length, so
  //: every offset holds): "- a, b and c" run together over a pasted list was
  //: one 90-word sentence, and a list item is not a sentence anyway (K4b).
  const sentences = docStructuralBlank(text);
  const paragraphBreak = /\n[ \t]*\n/g;
  const chunks = [];
  let last = 0;
  let split;
  while ((split = paragraphBreak.exec(sentences)) !== null) {
    chunks.push([last, split.index]);
    last = split.index + split[0].length;
  }
  chunks.push([last, sentences.length]);
  for (const [at, to] of chunks) {
    const chunk = sentences.slice(at, to);
    if (/^\s*(?:```|~~~|#|\||>)/.test(chunk)) continue;
    let cursor = 0;
    for (const sentence of chunk.split(/(?<=[.!?])\s+/)) {
      const words = (sentence.match(/\S+/g) || []).length;
      if (words > DOC_LONG_SENTENCE_WORDS) {
        found.push({
          rule: "long-sentence",
          message: `${nounCount(words, "word")} in one sentence`,
          start: at + cursor,
          end: at + cursor + sentence.length,
          text: text.slice(at + cursor, at + cursor + sentence.length),
          replacement: null,
        });
      }
      cursor += sentence.length + 1;
    }
  }
  return found
    .filter((finding) => !docProseIgnored.has(docProseKey(finding)))
    .sort((a, b) => a.start - b.start);
}

//: **Spelling in a code file: comments and the words inside strings, never
//: code** (the owner, 2026-10-11: `is_leap`, `urFucked` and the `f"The` of an
//: f-string were underlined). The squiggles were the browser's own, on because
//: the word list loads only on a prose pass and a code file never made one.
//: Now the browser's checker is off in a code file (`docCmSpellcheck`) and
//: this draws the app's own marks, which open the same suggestion popover as
//: prose. The text is masked to the comment and string nodes of the syntax
//: tree, everything else blanked at the same length so every offset still
//: names the document's characters: a string's prefix (f, r, b, u) and quotes
//: and a comment's marker are blanked too, and so is an f-string's `{expr}`.
//: `win`, past DOC_PROSE_WINDOW_CHARS, is the window the pass reads (audit 1031
//: CE3: the whole-file mask was 517 ms of a 20-key run in a 7,000-line file at
//: 4x): only the tree and the text inside it, and the mask returned is that
//: window's.
function docCodeProseMask(text, win = null) {
  const CM = window.CM6;
  if (!CM || !docCmView || docCmView.state.doc.length !== text.length) return "";
  const state = docCmView.state;
  const tree = win ? CM.language.syntaxTree(state) : CM.language.ensureSyntaxTree(state, state.doc.length, 50) || CM.language.syntaxTree(state);
  const keep = new Uint8Array(text.length);
  const blank = (from, length) => keep.fill(0, from, from + length);
  tree.iterate({
    ...(win ? { from: win.from, to: win.to } : {}),
    enter(node) {
      if (/Interpolation|Escape|FormatReplacement/i.test(node.name)) {
        blank(node.from, node.to - node.from);
        return false;
      }
      const string = /string|template/i.test(node.name);
      const comment = /comment/i.test(node.name);
      if (!string && !comment) return undefined;
      keep.fill(1, node.from, node.to);
      if (string) {
        const head = /^[rRbBuUfF]{0,3}(?:"""|'''|"|'|`)/.exec(text.slice(node.from, node.from + 6));
        if (head) blank(node.from, head[0].length);
        const tail = /(?:"""|'''|"|'|`)$/.exec(text.slice(Math.max(node.from, node.to - 3), node.to));
        if (tail) blank(node.to - tail[0].length, tail[0].length);
      } else {
        const head = /^(?:\/\/+|\/\*+|#+|--|<!--|;+|%+)/.exec(text.slice(node.from, node.from + 5));
        if (head) blank(node.from, head[0].length);
        const tail = /(?:\*+\/|-->)$/.exec(text.slice(Math.max(node.from, node.to - 4), node.to));
        if (tail) blank(node.to - tail[0].length, tail[0].length);
      }
      return undefined;
    },
  });
  const parts = [];
  for (let i = win ? win.from : 0, end = win ? win.to : text.length; i < end; i += 1) parts.push(keep[i] || text[i] === "\n" ? text[i] : " ");
  return parts.join("");
}

function docCodeSpellFindings(text, win = null) {
  if (!text.trim()) return [];
  docLoadWordlist();
  if (!docWordlistReady()) return [];
  const masked = docCodeProseMask(text, win);
  if (!masked.trim()) return [];
  const shift = win ? win.from : 0;
  const found = [];
  const dictionary = docDictionary();
  const word = /[A-Za-z']+/g;
  let hit;
  while ((hit = word.exec(masked)) !== null) {
    const lower = hit[0].toLowerCase();
    if (dictionary.has(lower)) continue;
    const at = hit.index;
    const base = { start: at + shift, end: at + shift + hit[0].length, text: hit[0], rule: "spelling" };
    const better = DOC_AUTOCORRECT[lower] || autocorrectState.inText(masked, at, hit[0]);
    if (better) {
      found.push({ ...base, message: `“${hit[0]}” is probably “${better}”`, replacement: docMatchCase(hit[0], better) });
      continue;
    }
    if (!docSpellable(masked, hit[0], at, at + hit[0].length)) continue;
    const nameKind = docSpellNameKind(masked, hit[0], at);
    if (nameKind === "name" && (docWordKnown(hit[0]) || !docSpellTransposed(hit[0]))) continue;
    const looked = docSpellLookup(hit[0]);
    if (looked.known) continue;
    if (nameKind === "initial" && !looked.sure) continue;
    found.push({
      ...base,
      message: looked.sure ? `“${hit[0]}” is probably “${looked.sure}”` : `“${hit[0]}” is not in the dictionary`,
      replacement: looked.sure ? docMatchCase(hit[0], looked.sure) : null,
    });
  }
  return found.filter((finding) => !docProseIgnored.has(docProseKey(finding)));
}

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
const docProse = {
  //: **The document's language** (audit 1028 D30). The `lang` (or `language`) key of a
  //: leading frontmatter block, reduced to its primary subtag: "en-GB" is "en". Absent
  //: means English, the one list this app ships. Pure, so it is tested alone. A method
  //: here rather than a global (the scope ratchet).
  langOf(text) {
    const block = /^---\r?\n([\s\S]*?)\r?\n---/.exec(text || "");
    if (!block) return "en";
    const key = /^lang(?:uage)?:[ \t]*["']?([A-Za-z]{2,3})/m.exec(block[1]);
    return key ? key[1].toLowerCase() : "en";
  },
  //: Why the checker is quiet for a non-English document: the English list would
  //: flag every word, and no pack for its language is installed (a30h-1102 step 4). With a
  //: pack (D30, documents-spell.js) spelling is checked and the note says so.
  langNote(text) {
    const lang = this.langOf(text);
    if (lang === "en") return "";
    return docSpell.packNote(lang) || `Spelling and grammar are off for this document: its language is set to ${docSpell.langName(lang)}, and only the English checks are installed.`;
  },
  hidden: false,
  panelView: "list",
  win: null,
  timer: null,
  memo: null,
  //: **A key reads the paragraph it edited, not the window** (prose-1101). A
  //: pass made for a keystroke (`typing`) or for an answer to one (`again`)
  //: whose text differs from the last pass's by one small edit inside a
  //: paragraph keeps every finding outside that paragraph (moved by the length
  //: difference) and runs the rules on the paragraph alone; the mask is made
  //: the same way. Typing at 4x in a 5,000-line document read 14,000
  //: characters per key for the rules and the mask, now about 300. What it
  //: does not see (a finding that crosses a paragraph, the sentence before a
  //: blank line) is made good by `settle`: a full pass once the writer pauses,
  //: so the settled findings are the full pass's (`tests/test_prose_near_1101.py`).
  //: Anything that could change a paragraph's neighbours (a new line, a fence,
  //: frontmatter or a suggestion mark's characters, a paste) takes the full pass.
  typing: false,
  dirty: false,
  nearMin: 8000,
  rules(part, again) {
    const key = [docProseIgnored.size, docWordlist ? docWordlist.size : -1, docDictionary().size, docSpellingVariant(), docCheckLinkText(), docSpell.packKey()].join("|");
    const memo = this.memo;
    if (!((again || this.typing) && memo && memo.part === part && memo.key === key)) {
      const near = (this.typing || again) && memo && memo.key === key && part.length >= this.nearMin && memo.part !== part ? this.near(memo, part) : null;
      if (near) {
        this.memo = { part, key, found: near.found, mask: near.mask };
        this.dirty = true;
        this.settle();
      } else {
        const found = docProseFindings(part, docProse.langOf(part));
        //: Kept here, not read back from `docProseSkipMask.memo`: a grammar
        //: answer for an older text replaces that one between two keys.
        this.memo = { part, key, found, mask: part.length >= this.nearMin ? docProseSkipMask(part) : null };
        this.dirty = false;
      }
    }
    return this.memo.found.map((finding) => ({ ...finding }));
  },
  //: The findings and mask of `part` made from the last pass's (`last`), or
  //: null when the edit is not one a paragraph can hold.
  near(last, part) {
    const { part: old, found, mask: before } = last;
    if (!before || before.length !== old.length) return null;
    const limit = Math.min(old.length, part.length);
    let head = 0;
    while (head < limit && old.charCodeAt(head) === part.charCodeAt(head)) head += 1;
    let tail = 0;
    while (tail < limit - head && old.charCodeAt(old.length - 1 - tail) === part.charCodeAt(part.length - 1 - tail)) tail += 1;
    const gone = old.slice(head, old.length - tail);
    const put = part.slice(head, part.length - tail);
    if (gone.length > 200 || put.length > 200 || /[\n`~{}+-]/.test(gone + put)) return null;
    let from = part.lastIndexOf("\n\n", head);
    from = from < 0 ? 0 : from + 2;
    let to = part.indexOf("\n\n", head + put.length);
    if (to < 0) to = part.length;
    if (to - from > 4000) {
      //: A paragraph that long (notes with no blank lines) is read three lines at a time.
      const first = from;
      from = part.lastIndexOf("\n", Math.max(0, head - 1)) + 1;
      if (from > first) from = part.lastIndexOf("\n", from - 2) + 1;
      const next = part.indexOf("\n", head + put.length);
      const after = next < 0 ? -1 : part.indexOf("\n", next + 1);
      to = after < 0 ? to : Math.min(to, after);
    }
    const zone = part.slice(from, to);
    if (/```|~~~/.test(zone)) return null;
    let fences = 0;
    for (const _ of part.slice(0, from).matchAll(/^(?:```|~~~)/gm)) fences += 1;
    if (fences % 2 === 1) return null;
    const shift = part.length - old.length;
    const stop = to - shift;
    const inside = docProseFindings(zone, docProse.langOf(part));
    const mask = new Uint8Array(part.length);
    mask.set(before.subarray(0, from), 0);
    mask.set(docProseSkipMask(zone), from);
    mask.set(before.subarray(stop), to);
    docProseSkipMask.memo = { text: part, link: docCheckLinkText(), mask };
    const out = [];
    for (const finding of found) {
      if (finding.end <= from) out.push(finding);
      else if (finding.start >= stop) out.push(shift ? { ...finding, start: finding.start + shift, end: finding.end + shift } : finding);
    }
    for (const finding of inside) out.push({ ...finding, start: finding.start + from, end: finding.end + from });
    return { found: out.sort((a, b) => a.start - b.start), mask };
  },
  //: **The findings move with the text** (INBOX 1526). `docProseFound` is made
  //: for one text and the pass for the next one is a pause away, so between a
  //: key and that pass every offset past the caret was stale and the plugin
  //: drew none of them: the underlines below the line being typed on went out
  //: and came back 150 ms later. Moved here through the edit's changes instead
  //: (a copy per finding: the grammar cache's own objects are shared with the
  //: list). A finding the edit went into no longer reads its text and is not
  //: drawn; the start moves right of an insertion at it and the end stays left.
  remap(changes) {
    docProseFound = docProseFound.map((finding) => ({
      ...finding,
      start: changes.mapPos(finding.start, 1),
      end: changes.mapPos(finding.end, -1),
    }));
  },
  //: What the marks say, to know whether a repaint would draw anything new.
  sig() {
    return docProseFound.map((f) => `${f.rule}:${f.start}:${f.end}:${f.text}:${f.message}`).join("|");
  },
  painted: null,
  frame: 0,
  //: The full pass, once the writer has paused: when the browser is idle, at
  //: the latest 1.5 s after.
  settle() {
    clearTimeout(this.settleTimer);
    this.settleTimer = setTimeout(() => {
      const run = () => {
        if (this.dirty) renderDocProse();
      };
      if (typeof requestIdleCallback === "function") requestIdleCallback(run, { timeout: 1500 });
      else run();
    }, 700);
  },
};
//: "list" is the suggestions, "dismissed" is the ones put away in this document.

//: **Past this many characters the prose pass reads a window** (audit 1028
//: D7), centred on what is on screen and cut at blank lines, so the cost of a
//: pause is the window and not the document. Measured at 100,800 characters:
//: see docs/roadmap/agent-remaining/docux-1028.md.
const DOC_PROSE_WINDOW_CHARS = 30000;

//: A code file's window (CE3): the same centre as the prose one and the
//: whole 30,000, cut at line ends (a blank line or a fence means nothing in code).
function docCodeWindow(text) {
  if (text.length <= DOC_PROSE_WINDOW_CHARS) return null;
  const ranges = docCmView ? docCmView.visibleRanges : [];
  const mid = ranges.length ? (ranges[0].from + ranges[ranges.length - 1].to) >> 1 : 0;
  const to = Math.min(text.length, Math.max(0, mid - DOC_PROSE_WINDOW_CHARS / 2) + DOC_PROSE_WINDOW_CHARS);
  const start = Math.max(0, to - DOC_PROSE_WINDOW_CHARS);
  const end = to < text.length ? text.indexOf("\n", to) : -1;
  return { from: start ? text.lastIndexOf("\n", start) + 1 : 0, to: end < 0 ? text.length : end };
}

//: **A prose window is the screen and a margin, not the whole 30,000** (audit
//: 1028 D18 to D20): a prose pass is paid on every pause, and a screen of text
//: is about 3,000 characters, so 14,000 keeps about two screens either side of
//: the view checked while the pass costs under half of what 30,000 did.
//: Scrolling out of it re-runs the pass (`docProseScrolled`).
function docProseWindow(text) {
  if (text.length <= DOC_PROSE_WINDOW_CHARS) return null;
  const view = 14000;
  let mid = 0;
  try {
    const ranges = docCmView ? docCmView.visibleRanges : [];
    mid = ranges.length ? (ranges[0].from + ranges[ranges.length - 1].to) >> 1 : docCmView ? docCmView.state.selection.main.head : 0;
  } catch {
    mid = 0;
  }
  let to = Math.min(text.length, Math.max(0, mid - view / 2) + view);
  let from = Math.max(0, to - view);
  if (from > 0) {
    //: Cut at a blank line, and never inside a fence: a window that began in
    //: the middle of a code block would read its code as prose. A blank line
    //: more than a view away (a long list, notes with no blank lines at all)
    //: is no cut: the window was then the whole document, 391,000 characters
    //: read on every key, so the cut is the nearest line end instead.
    const cut = text.lastIndexOf("\n\n", from);
    from = cut >= 0 && from - cut < view ? cut + 2 : text.lastIndexOf("\n", from) + 1;
    let open = -1;
    for (const fence of text.slice(0, from).matchAll(/^(?:```|~~~)/gm)) open = open < 0 ? fence.index : -1;
    if (open >= 0) from = open;
  }
  if (to < text.length) {
    const cut = text.indexOf("\n\n", to);
    const line = text.indexOf("\n", to);
    to = cut >= 0 && cut - to < view ? cut : line < 0 ? text.length : line;
  }
  return { from, to };
}

//: Scrolling out of the window re-runs the pass once the view settles.
function docProseScrolled() {
  if (!docProse.win) return;
  clearTimeout(docProse.timer);
  docProse.timer = setTimeout(() => {
    const ranges = docCmView ? docCmView.visibleRanges : [];
    if (!ranges.length || !docProse.win) return;
    const seen = ranges[0].from < docProse.win.from || ranges[ranges.length - 1].to > docProse.win.to;
    if (seen) renderDocProse();
  }, 250);
}

function renderDocProse(again = false) {
  again = again === true;
  const chip = $("doc-prose");
  const count = $("doc-prose-count");
  const panel = $("doc-prose-panel");
  if (!chip || !count || !panel) return;
  //: A code file has no prose. Running these rules over one would flag `==`,
  //: `;;` and every long line, which is noise a programmer cannot turn off
  //: fast enough.
  const isCode = !docFileType().previewable;
  //: The rule findings, then the ones from the prose tools below (grammar,
  //: accessibility), which never claim a span a rule already holds.
  const text = docText();
  //: And Check with AI's findings (`docAiFindings`), located afresh in the
  //: text as it is now, so an applied or edited-away one simply goes.
  //: A long document is checked a window at a time (audit 1028 D7): the pass
  //: walks every rule and word, and at 100k characters that was a visible
  //: pause on each 150ms stop. The window follows the view (`docProseScrolled`).
  const win = isCode ? docCodeWindow(text) : docProseWindow(text);
  docProse.win = win;
  if (isCode) docProseFound = docCodeSpellFindings(text, win);
  else if (win) {
    const part = text.slice(win.from, win.to);
    const near = docProseExtras(part, docProse.rules(part, again));
    for (const finding of near) {
      finding.start += win.from;
      finding.end += win.from;
    }
    docProseFound = near.concat(docAiFindings(text)).sort((a, b) => a.start - b.start);
  } else {
    docProseFound = docProseExtras(text, docProse.rules(text, again)).concat(docAiFindings(text)).sort((a, b) => a.start - b.start);
  }
  if (docProse.hidden) docProseFound = [];
  chip.hidden = isCode;
  count.textContent = docProse.hidden
    ? "Suggestions hidden"
    : docProseFound.length
      ? `${docProseFound.length.toLocaleString("en")} ${docProseFound.length === 1 ? "suggestion" : "suggestions"}${win ? " in view" : ""}`
      : win
        ? "No suggestions in view"
        : "No suggestions";
  chip.classList.toggle("has-findings", docProseFound.length > 0);
  docFocusSyncProse();
  //: A fresh set of findings means a fresh set of marks. The engine is told
  //: through an effect rather than by rebuilding anything: the decorations are
  //: computed from `docProseFound` over the visible lines, so the repaint is a
  //: screenful whatever the document's length.
  docCmRepaintFindings(again);
  renderDocSuggestState();
  if (!panel.classList.contains("hidden")) docProsePanelSoon();
}

//: **While the writer types, the open panel is redrawn at most every 400 ms**
//: (perf 1031 row 23, DC3: a 58,000-character document with the panel open,
//: 36 keys at 4x: 26 redraws of the rows, 95 long tasks, 15 s of them). The
//: first redraw is at once and the last one always lands; a click in the panel
//: (Fix, Dismiss) is not typing and redraws at once.
const DOC_PROSE_PANEL_GAP_MS = 400;
function docProsePanelSoon() {
  const soon = docProsePanelSoon;
  clearTimeout(soon.timer);
  const wait = docCmView?.hasFocus ? (soon.at || 0) + DOC_PROSE_PANEL_GAP_MS - performance.now() : 0;
  if (!(wait > 0)) {
    soon.at = performance.now();
    renderDocProsePanel();
    return;
  }
  soon.timer = setTimeout(() => {
    soon.at = performance.now();
    renderDocProsePanel();
  }, wait);
}

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

//: A long sentence is the one finding that must not be underlined: the span
//: is a whole paragraph, and a wavy line under all of it says "everything
//: here is wrong", which is the opposite of what that finding means.
const DOC_FINDING_SKIP = new Set(["long-sentence"]);

//: Findings "Fix all" never applies: a model's reading and an offer to link a
//: note are judgements for the writer, whatever replacement they carry.
const DOC_FIX_ALL_NEVER = new Set(["ai", "link-offer"]);

//: Three kinds, because three is what a reader can decode at a glance from
//: the shape of a line. The rules are more numerous than that (there are
//: eight), but "a spacing slip" and "a UK/US spelling" are the same *kind* of
//: note as far as the eye is concerned, and both are answered the same way.
function docFindingKind(finding) {
  if (finding.rule === "spelling") return "spelling";
  if (finding.rule === "grammar" || finding.rule === "confusion") return "grammar";
  //: A claim check's verdict (MINDMAP_PLAN Phase G) rides the same finding: marked
  //: when no note backs it or one says otherwise, quiet when a note supports it.
  if (finding.rule === "ai") {
    const claim = finding.aiItem?.claim;
    if (!claim) return "ai";
    if (claim.verdict === "supported") return "backed";
    return "claim";
  }
  if (DOC_ACCESS_RULES.has(finding.rule)) return "access";
  if (finding.rule === "repeat") return "repeat";
  if (finding.rule === "link-offer") return "link";
  return "style";
}


//: **One head for both states of the panel** (INBOX 549 and 552, the
//: panel-head recipe): the name and its count as quiet text, then one row of
//: quiet icon buttons of one size, the X last, never wrapping: the panel is
//: 240px at its narrowest. Fix N is the one worded tool (its number is what
//: it says) and drops its words in a narrow panel; the Dictionary and the
//: dock side are in the ⋯, which also holds Check with AI for the width
//: where its own icon gives way.
function docProseHeader() {
  const head = document.createElement("div");
  head.className = "row doc-prose-head";
  const title = document.createElement("span");
  title.className = "doc-prose-title";
  //: The name gives way (an ellipsis); the count beside it never does.
  const name = document.createElement("span");
  name.className = "doc-prose-name";
  name.textContent = "Suggestions";
  title.appendChild(name);
  const n = docProseFound.length;
  const count = document.createElement("span");
  count.className = "doc-prose-count";
  count.textContent = n ? String(n) : "";
  count.title = `${nounCount(n, "suggestion")} in this document`;
  title.appendChild(count);
  head.appendChild(title);

  const tools = document.createElement("span");
  tools.className = "row doc-prose-tools";
  const tool = (label, title, run, extra) => {
    const button = smallButton(label, title, run);
    button.classList.add("doc-prose-tool", ...extra.split(" "));
    button.setAttribute("aria-label", title);
    return button;
  };
  //: A model's fix is a judgement to read, never one of "every suggestion that
  //: has one clear answer", so Fix all leaves the `ai` kind alone, and an
  //: offer to link a note (`DOC_FIX_ALL_NEVER`).
  const fixable = docProseFound.filter((f) => f.replacement !== null && !DOC_FIX_ALL_NEVER.has(f.rule));
  if (fixable.length) {
    const all = tool(`ph:magic-wand Fix all ${fixable.length.toLocaleString("en")}`, `Fix all ${fixable.length.toLocaleString("en")}: apply every suggestion that has one clear answer`, () => docProseFixAll(), "doc-prose-fix-all");
    tools.appendChild(all);
  }
  //: **Meaning needs a model** (ROADMAP: its/it's, agreement, tense), and
  //: judging it takes seconds, so it is a button rather than a pass on every
  //: keystroke: it costs nothing until asked for.
  const running = docAiCheck.state === "running";
  tools.appendChild(tool(
    running ? "ph:stop" : "ph:sparkle",
    running
      ? "Stop checking; what it found so far stays"
      : "Check with AI: read for what spelling and grammar rules can't catch (its/it's, agreement, tense, tone, clarity)",
    () => docAiReview(),
    "icon-only doc-prose-ai-run"
  ));
  const right = docProseDockSide() === "right";
  const more = kebabMenu([
    makeMenuItem("ph:sparkle Check with AI", "Read for what the rules can't catch", () => docAiReview()),
    makeMenuItem("ph:seal-check Check claims against my notes", "Mark each sentence supported, contradicted or not found in your notes", () => docAiCheck.claims()),
    makeMenuItem(
      docProse.hidden ? "ph:eye Show suggestions" : "ph:eye-slash Hide all suggestions",
      docProse.hidden ? "Underline and list suggestions again" : "Hide every underline and the list until you show them again",
      () => docProseSetHidden(!docProse.hidden)
    ),
    makeMenuItem(
      `ph:arrow-counter-clockwise Dismissed (${docProseDismissed().length})`,
      "The suggestions you put away in this document, to bring back",
      () => {
        docProse.panelView = "dismissed";
        renderDocProsePanel();
      }
    ),
    makeMenuItem("ph:book-open-text Dictionary", "The words you have told this to accept", () => openDocDictionary()),
    //: Where the panel sits (`applyDocProseDock`); not offered where there is
    //: no choice (a narrow window, focus mode's side panel).
    ...(window.matchMedia(DOC_PROSE_NARROW).matches || docFocusOn() ? [] : [
      makeMenuItem(
        right ? "ph:square-split-vertical Dock at the bottom" : "ph:square-split-horizontal Dock on the right",
        right ? "Dock the suggestions at the bottom" : "Dock the suggestions on the right",
        () => toggleDocProseDock()
      ),
    ]),
  ], "More for the suggestions");
  more.classList.add("doc-prose-more");
  const opener = more.querySelector("button");
  opener.classList.add("doc-prose-tool");
  opener.setAttribute("aria-label", "More for the suggestions");
  tools.appendChild(more);
  tools.appendChild(tool("ph:x", "Close the suggestions", () => closeDocProsePanel(), "icon-only doc-prose-close"));
  head.appendChild(tools);
  return head;
}

function docProseSetHidden(hidden) {
  docProse.hidden = hidden;
  docProse.panelView = "list";
  renderDocProse();
  renderDocProsePanel();
}

//: The keys in `docProseIgnored` that belong to this document, as rows.
//: A key is `<doc>:<rule>:<text>`; the first two parts hold no colon.
function docProseDismissed() {
  const scope = `${currentDoc && currentDoc.id ? currentDoc.id : "unsaved"}:`;
  const rows = [];
  for (const key of docProseIgnored) {
    if (!key.startsWith(scope)) continue;
    const rest = key.slice(scope.length);
    const cut = rest.indexOf(":");
    if (cut < 0) continue;
    rows.push({ key, rule: rest.slice(0, cut), text: rest.slice(cut + 1) });
  }
  return rows;
}

//: What the panel shows instead of the list: the hidden notice, or the
//: dismissed list with a Restore on each row.
function docProseSideView() {
  const wrap = document.createElement("div");
  wrap.className = "doc-prose-side";
  const line = document.createElement("p");
  line.className = "muted doc-prose-side-line";
  wrap.appendChild(line);
  if (docProse.panelView === "dismissed") {
    const rows = docProseDismissed();
    line.textContent = rows.length
      ? "Put away in this document. Restore one to see it again."
      : "Nothing dismissed in this document.";
    const back = smallButton("ph:arrow-left Back", "Back to the suggestions", () => {
      docProse.panelView = "list";
      renderDocProsePanel();
    });
    back.classList.add("ghost");
    const list = document.createElement("ul");
    list.className = "doc-prose-dismissed";
    for (const row of rows) {
      const item = document.createElement("li");
      item.className = "row doc-prose-dismissed-row";
      const word = document.createElement("span");
      word.className = "doc-prose-dismissed-text";
      word.textContent = row.text;
      word.title = `${row.rule}: ${row.text}`;
      const restore = smallButton("ph:arrow-counter-clockwise Restore", `Show “${row.text}” again`, () => {
        docProseIgnored.delete(row.key);
        if (docProseDismissed().length === 0) docProse.panelView = "list";
        renderDocProse();
        renderDocProsePanel();
      });
      restore.classList.add("ghost");
      item.append(word, restore);
      list.appendChild(item);
    }
    wrap.append(back, list);
    if (rows.length > 1) {
      const all = smallButton("ph:arrow-counter-clockwise Restore all", "Show every dismissed suggestion again", () => {
        for (const row of rows) docProseIgnored.delete(row.key);
        renderDocProse();
        renderDocProsePanel();
      });
      all.classList.add("ghost");
      wrap.appendChild(all);
    }
    return wrap;
  }
  line.textContent = "Suggestions are hidden. The underlines and this list are off until you show them.";
  const show = smallButton("ph:eye Show suggestions", "Underline and list suggestions again", () => docProseSetHidden(false));
  wrap.appendChild(show);
  return wrap;
}

function closeDocProsePanel() {
  $("doc-prose-panel")?.classList.add("hidden");
  $("doc-prose")?.setAttribute("aria-expanded", "false");
  docFocusSyncProse();
  //: Focus goes back to the control that opened it, or it lands on the body
  //: and the next Tab starts from the top of the page. In focus mode the
  //: status bar is gone, so that is the floating dock's own button.
  (docFocusOn() ? $("doc-focus-prose") : $("doc-prose"))?.focus();
}

//: The floating dock's Suggestions says what the chip says: how many, and
//: whether the panel is open. Hidden for a code file, as the chip is.
function docFocusSyncProse() {
  const button = $("doc-focus-prose");
  if (!button) return;
  const n = docProseFound.length;
  const words = n ? nounCount(n, "suggestion") : "Suggestions";
  const label = $("doc-focus-prose-count");
  if (label) label.textContent = words;
  button.hidden = Boolean($("doc-prose")?.hidden);
  const open = !$("doc-prose-panel")?.classList.contains("hidden");
  button.setAttribute("aria-expanded", String(open));
  button.title = open ? "Close the writing suggestions" : n ? `Writing suggestions: ${words}` : "Writing suggestions";
  button.setAttribute("aria-label", button.title);
}

function renderDocProsePanel() {
  const panel = $("doc-prose-panel");
  if (!panel) return;
  panel.replaceChildren();
  //: The header first, always, including on the empty state. Reported:
  //: "there's no close x button." A panel whose only exit is the control that
  //: opened it is a panel you have to remember how to leave, and the empty
  //: state was the one view where that was most likely.
  if (docProse.hidden || docProse.panelView === "dismissed") {
    panel.appendChild(docProseHeader());
    panel.appendChild(docProseSideView());
    return;
  }
  const aiStatus = docAiCheckStatus();
  if (!docProseFound.length) {
    panel.appendChild(docProseHeader());
    if (aiStatus) panel.appendChild(aiStatus);
    //: Quiet: a mark, one line, and what was checked under it.
    const empty = document.createElement("div");
    empty.className = "doc-prose-empty";
    const mark = document.createElement("i");
    mark.className = "ph ph-check-circle doc-prose-empty-mark";
    mark.setAttribute("aria-hidden", "true");
    const said = document.createElement("p");
    said.textContent = "Nothing to flag.";
    const what = document.createElement("p");
    what.className = "muted";
    what.textContent = `Checked for spelling, ${docGrammarEnabled() ? "grammar, " : ""}spacing, sentence length and accessibility; these read the text, not its meaning.`;
    empty.append(mark, said, what);
    const langRow = docSpell.langRow(docText());
    if (langRow) empty.appendChild(langRow);
    panel.appendChild(empty);
    return;
  }
  panel.appendChild(docProseHeader());
  if (aiStatus) panel.appendChild(aiStatus);
  const langRow = docSpell.langRow(docText());
  if (langRow) panel.appendChild(langRow);

  //: **Grouped by kind, with a count on each group** (DOCUMENTS_PLAN Phase 0
  //: item 3). A flat list of twenty rows is twenty separate decisions in
  //: whatever order the document happens to put them; "Spelling 3 / Style 11 /
  //: Repeated words 2" is one look that tells you what kind of pass this
  //: document needs, and it lets you do all of one kind at a time, which is
  //: how anyone actually edits. The order is fixed rather than by size, so the
  //: strongest claim is always at the top and the panel does not reshuffle
  //: itself between two openings.
  for (const [kind, label] of DOC_FINDING_GROUPS) {
    const group = docProseFound.filter((finding) => docFindingKind(finding) === kind);
    if (!group.length) continue;
    const heading = document.createElement("p");
    heading.className = "doc-prose-group";
    const name = document.createElement("span");
    name.textContent = label;
    const count = document.createElement("span");
    count.className = "doc-prose-group-count";
    count.textContent = String(group.length);
    heading.append(name, count);
    panel.appendChild(heading);
    panel.appendChild(docProseGroupList(group));
  }
  if (!panel.dataset.keys) {
    panel.dataset.keys = "1";
    panel.addEventListener("keydown", docProseRowKeys);
  }
  if (docProseFocusAt >= 0) {
    const jumps = panel.querySelectorAll(".doc-prose-jump");
    (jumps[Math.min(docProseFocusAt, jumps.length - 1)] || panel.querySelector(".doc-prose-close"))?.focus({ preventScroll: true });
    docProseFocusAt = -1;
  }
}

//: The three kinds the underlines already draw, in the order of how strong a
//: claim each one is. Named here rather than in the panel so the group title
//: and the squiggle can never drift apart.
const DOC_FINDING_GROUPS = [
  ["spelling", "Spelling"],
  ["grammar", "Grammar"],
  ["repeat", "Repeated words"],
  ["style", "Style and spacing"],
  ["access", "Accessibility"],
  ["link", "Links to your notes"],
  //: Claim check (Phase G): what the notebook does not back, then what it does.
  ["claim", "Checked against your notes"],
  ["backed", "Supported by your notes"],
  //: Last: a model's reading is the weakest claim in the panel, and it says
  //: so by where it sits.
  ["ai", "Checked with AI"],
];

//: Sixty rows, over all the groups rather than per group: the cap is there so
//: a pathological document cannot build ten thousand elements, and a cap that
//: applied per group would let three kinds multiply it by three.
const DOC_PROSE_ROWS = 60;

//: **The row of the panel, and the answers under it** (DOCUMENTS_PLAN 12 D3).
//:
//: Reported: "when I click on the issue from the suggestions thing, the box
//: just appears right there in my face." The row used to open the floating
//: menu, first at the row (which is at the foot of the window, under the
//: pointer) and then at the word, and both readings of "where" were answers to
//: the wrong question: a list at the foot of the window had no answers of its
//: own, so acting on any row meant drawing a 335px popup over the text being
//: discussed, on top of the 297px panel that asked. Measured: 70% of the
//: window's height spent on one misspelled word.
//:
//: So the row expands under itself, inside the panel, with the same answers the
//: menu offers (`docSuggestAnswers`), and the document scrolls the word to the
//: middle of the editor so the sentence is readable while its row is open. One
//: surface at a time, which is DESIGN.md's popover rule: a panel that has to
//: open a popover to be useful was breaking it structurally.
//: **Closing a row, once.** Three things close one (the second press on the
//: row, Escape inside the answers, and pressing an answer), and each of them
//: used to write the same four lines. They also have to agree about focus: a
//: row opened from the keyboard has the focus ring somewhere inside the block
//: that is about to be emptied, and an element removed while it has focus
//: hands it to `<body>`, which is the end of keyboard navigation for that
//: panel. So the row takes it back, but only when the row is where it came
//: from: a pointer press left focus in the editor on purpose (that is what
//: "show me this in the document" means) and stealing it here would move the
//: caret out of the sentence the reader was just shown.
function docProseRowCollapse(row, control, answers) {
  control.setAttribute("aria-expanded", "false");
  row.removeAttribute("aria-current");
  answers.classList.add("hidden");
  answers.replaceChildren();
  if (row.dataset.keyOpened === "1") control.focus();
  delete row.dataset.keyOpened;
}

async function docProseRowAnswers(row, control, finding, opts = {}) {
  const panel = $("doc-prose-panel");
  const answers = row.querySelector(".doc-prose-answers");
  if (!panel || !answers) return;
  //: **Keyboard or pointer, decided by `event.detail`.** A click raised by
  //: Enter or Space on a button reports `detail === 0`; a real press reports
  //: the click count. It is the only signal that separates the two here, and
  //: the whole behaviour below hangs off it, so the caller passes it in rather
  //: than this function reaching for a global event.
  const byKeyboard = opts.keyboard === true;
  const wasOpen = control.getAttribute("aria-expanded") === "true";
  //: One open row, like one open popover. Two sets of answers in one list is
  //: two places the next press could mean something.
  for (const other of panel.querySelectorAll('.doc-prose-jump[aria-expanded="true"]')) {
    //: **Not this row.** The selector matches the row being pressed too when
    //: it is already open, and collapsing it here rather than in the `wasOpen`
    //: branch below meant the branch ran against a row that was already closed
    //: and had already given its focus away: measured as the editor keeping
    //: the ring after Enter closed a row from the keyboard.
    if (other === control) continue;
    const li = other.closest(".doc-prose-row");
    const box = li?.querySelector(".doc-prose-answers");
    //: Another row's answers, so its focus is not this row's business: the
    //: flag goes first, and the collapse leaves focus where it found it.
    if (li) delete li.dataset.keyOpened;
    if (li && box) docProseRowCollapse(li, other, box);
    else other.setAttribute("aria-expanded", "false");
  }
  //: Pressing the row always takes you to the word, open or closing: that is
  //: what the row is for, and it is the half of this the owner asked for
  //: ("it should auto scroll to the issue and temporarily highlight it").
  docProseJump(finding);
  //: **The press that closes decides where focus goes**, not the press that
  //: opened: closing with Enter from the row means the reader is on the row
  //: and wants to stay there, whichever way it was opened. Set before either
  //: branch because the `close` handed to the answers below reads it too, and
  //: that is what a candidate pressed with Enter calls.
  if (byKeyboard) row.dataset.keyOpened = "1";
  else delete row.dataset.keyOpened;
  if (wasOpen) {
    docProseRowCollapse(row, control, answers);
    return;
  }
  control.setAttribute("aria-expanded", "true");
  //: The open row is where you are in the document, so it says so with
  //: `aria-current` and is painted from that attribute (DESIGN.md's recipe for
  //: a list that says where you are), not with a class a screen reader cannot
  //: see.
  row.setAttribute("aria-current", "location");
  const drawn = await docSuggestAnswers(finding, {
    inline: true,
    close: () => docProseRowCollapse(row, control, answers),
    current: () => control.getAttribute("aria-expanded") === "true",
  });
  //: The piece may have been fetched meanwhile: a row closed or replaced by then is left alone.
  if (control.getAttribute("aria-expanded") !== "true") return;
  answers.replaceChildren(drawn);
  answers.classList.remove("hidden");
  //: Brought into view by the panel's own `scrollTop`, never `scrollIntoView`,
  //: which walks every scrolling ancestor including the page (DESIGN.md).
  const box = row.getBoundingClientRect();
  const frame = panel.getBoundingClientRect();
  if (box.bottom > frame.bottom) panel.scrollTop += box.bottom - frame.bottom + 8;
  else if (box.top < frame.top) panel.scrollTop -= frame.top - box.top + 8;
  //: **Focus follows the keyboard into the answers, and only the keyboard.**
  //: Reported (OPEN.md, prose-intelligence.md): "Enter opens the row, focus
  //: stays on the control, the candidates are a Tab away with nothing saying
  //: so." Measured before this: after Enter, `document.activeElement` was the
  //: editor's own `cm-content` (`docProseJump` focuses the surface to show the
  //: word), so the candidates were not one Tab away, they were behind the
  //: whole editor's tab order. The first candidate is the one the panel says
  //: is the best answer, so it is the one that takes the ring.
  if (!byKeyboard) return;
  const first = answers.querySelector("button:not([disabled])");
  if (first) first.focus();
}

//: What Ignore says: a link offer is put away by name everywhere, anything else
//: for this document until a restart.
function docIgnoreLabel(finding) {
  return finding.rule === "link-offer" ? "Never offer a link to this name" : "Ignore in this document";
}

//: Stop flagging this wording in this document (until a restart).
function docProseIgnore(finding) {
  //: A link offer is put away by its name, for every document (the switch and
  //: the list of kept names are in Settings, Writing).
  if (finding.rule === "link-offer" && finding.name) {
    docLinkOfferIgnore(finding.name);
    return;
  }
  docProseIgnored.add(docProseKey(finding));
  renderDocProse();
  renderDocProsePanel();
}

//: **Next, without a key for it**: after a row's Accept or Ignore the focus
//: lands on the row that took its place, so the keyboard walks the list
//: answer by answer. Set by the row's action, spent by the next paint.
let docProseFocusAt = -1;

//: Up and Down walk the rows across the groups, Home and End the ends.
function docProseRowKeys(event) {
  const jump = event.target.closest?.(".doc-prose-jump");
  const moves = { ArrowDown: 1, ArrowUp: -1, Home: -Infinity, End: Infinity };
  if (!jump || !(event.key in moves)) return;
  event.preventDefault();
  const all = [...event.currentTarget.querySelectorAll(".doc-prose-jump")];
  const to = Math.max(0, Math.min(all.length - 1, all.indexOf(jump) + moves[event.key]));
  all[to]?.focus();
}

function docProseGroupList(findings) {
  const list = document.createElement("ul");
  list.className = "doc-prose-list";
  for (const finding of findings.slice(0, DOC_PROSE_ROWS)) {
    const li = document.createElement("li");
    li.className = "doc-prose-row";
    const head = document.createElement("div");
    head.className = "row doc-prose-rowhead";
    const jump = document.createElement("button");
    jump.type = "button";
    jump.className = "doc-prose-jump";
    jump.setAttribute("aria-expanded", "false");
    //: The words, then why: one drawing of a finding, shared with the menu's
    //: own head (`docFindingLine`).
    jump.appendChild(docFindingLine(finding, "row"));
    jump.title = "Show me this in the document, and what can be done about it";
    //: `event.detail === 0` is a press that came from Enter or Space rather
    //: than from a pointer: see `docProseRowAnswers` for what hangs off it.
    jump.addEventListener("click", (event) =>
      docProseRowAnswers(li, jump, finding, { keyboard: event.detail === 0 }));
    head.appendChild(jump);
    //: **One action cell per row** (INBOX 549): accept when there is one clear
    //: answer, then the way to put it away, last on every row: Ignore, or for
    //: a model's finding, Dismiss. Quiet icons of one size, centred on the row.
    const acts = document.createElement("span");
    acts.className = "doc-prose-acts";
    const act = (icon, title, run, extra = "") => {
      const button = smallButton(icon, title, () => {
        docProseFocusAt = [...$("doc-prose-panel").querySelectorAll(".doc-prose-jump")].indexOf(jump);
        run();
      });
      button.classList.add("icon-only", "doc-prose-act", ...extra.split(" ").filter(Boolean));
      button.setAttribute("aria-label", title);
      return button;
    };
    if (finding.aiItem?.claim?.note) {
      const note = finding.aiItem.claim.note;
      acts.appendChild(act("ph:note", `Open the note \u201c${note.title}\u201d`, () => openNoteEditor(note.id), "doc-prose-open-note"));
    }
    if (finding.replacement !== null) {
      acts.appendChild(act("ph:check", `Change it to \u201c${finding.replacement}\u201d`, () => docProseFix(finding), "doc-prose-fix"));
    }
    acts.appendChild(finding.rule === "ai"
      ? act("ph:x", "Dismiss this finding", () => docAiDismiss(finding), "doc-prose-fix doc-prose-dismiss")
      : act("ph:eye-slash", docIgnoreLabel(finding), () => docProseIgnore(finding), "doc-prose-ignore"));
    head.appendChild(acts);
    li.appendChild(head);
    const answers = document.createElement("div");
    answers.className = "doc-prose-answers hidden";
    //: **Escape leaves the answers the way it leaves every other surface in
    //: this app**, and it is wired here, once per row, rather than inside the
    //: open: the block is reused across opens, so a listener added there would
    //: multiply by one per press (the shape `tests/test_frontend_handlers.py`
    //: exists to catch). Stopped from bubbling because the app's own Escape
    //: chain would otherwise close the whole panel from underneath a reader
    //: who only meant to close one row.
    answers.addEventListener("keydown", (event) => {
      if (event.key !== "Escape") return;
      if (jump.getAttribute("aria-expanded") !== "true") return;
      event.stopPropagation();
      event.preventDefault();
      li.dataset.keyOpened = "1";
      docProseRowCollapse(li, jump, answers);
    });
    li.appendChild(answers);
    list.appendChild(li);
  }
  return list;
}

//: **Show me where: and make it obvious for a moment.**
//:
//: Asked for directly: "if I click on an issue flagged in the document
//: suggestions, it should auto scroll to the issue and temporarily highlight
//: the offending area." The scrolling half was here already; the highlight was
//: a text selection, which is the quietest mark a screen has, the same grey
//: as any other selection, in a box the pointer has just left, several
//: paragraphs from where the eye was. Landing in roughly the right place with
//: nothing saying "here" is what makes a jump feel like it did not happen.
//:
//: One way to say it now, because there is one editor. The selection is put
//: on the flagged span and the surface scrolls it into view: CodeMirror does
//: that itself as part of the transaction, and the underline is already there
//: to say which words are meant. The fallback textarea still needs the
//: `blur`+`focus` trick and the accent `::selection` flash, which is the only
//: mark a textarea can draw on a range it already holds.
const DOC_FLASH_MS = 1600;

function docProseJump(finding) {
  //: **No view switch.** This used to drop anyone in Live back into Source to
  //: find the word, which throws away the view they were reading in. Live can
  //: show the underline where it is now, so there is nothing to switch to.
  if (docView === "rendered") setDocView(lastEditView);
  const box = docSurface();
  if (!box) return;
  box.focus();
  box.setSelection(finding.start, finding.end);
  if (box.kind === "codemirror") {
    //: **To the middle, not just inside the edge** (DOCUMENTS_PLAN 12 D3).
    //: `setSelection` scrolls the minimum that reveals the range, which puts a
    //: word reached from the panel hard against the bottom of the editor, the
    //: one place where everything that follows (the row's own answers, a menu)
    //: has to be drawn over the text being discussed. Measured before this:
    //: the word at `564..583` in an editor ending at `588`.
    const CM = window.CM6;
    if (CM) {
      docCmView.dispatch({
        effects: CM.view.EditorView.scrollIntoView(finding.start, { y: "center" }),
      });
    }
    return;
  }
  box.blur();
  box.focus();
  box.classList.remove("doc-selection-flash");
  void box.offsetWidth;
  box.classList.add("doc-selection-flash");
  setTimeout(() => box.classList.remove("doc-selection-flash"), DOC_FLASH_MS);
}

function docProseApply(text, finding) {
  return text.slice(0, finding.start) + finding.replacement + text.slice(finding.end);
}

function docProseFix(finding) {
  const box = docSurface();
  if (!box || finding.replacement === null) return;
  //: Checked against the document as it is *now*, not as it was when the panel
  //: was drawn. Editing while the panel is open moves every span after the
  //: edit, and applying a stale offset would corrupt the document silently, 
  //: which is the one failure a writing aid must never have.
  if (box.value.slice(finding.start, finding.end) !== finding.text) {
    renderDocProse();
    return toast("That text has changed, the list is refreshed.", "info");
  }
  //: Its own step in the editor's history (Ctrl+Z, rule 1.8), never folded
  //: into the typing before it.
  docUndoBreak();
  box.value = docProseApply(box.value, finding);
  markDocDirty();
  box.dispatchEvent(new Event("input", { bubbles: true }));
  renderDocProse();
}

function docProseFixAll() {
  const box = docSurface();
  if (!box) return;
  //: Back to front, so each replacement cannot move the offsets of the ones
  //: still to be applied.
  const fixable = docProseFound
    .filter((f) => f.replacement !== null && !DOC_FIX_ALL_NEVER.has(f.rule))
    .sort((a, b) => b.start - a.start);
  let text = box.value;
  let applied = 0;
  for (const finding of fixable) {
    if (text.slice(finding.start, finding.end) !== finding.text) continue;
    text = docProseApply(text, finding);
    applied += 1;
  }
  if (!applied) return toast("Nothing left to fix.", "info");
  docUndoBreak();
  box.value = text;
  markDocDirty();
  box.dispatchEvent(new Event("input", { bubbles: true }));
  renderDocProse();
  toast(`Fixed ${applied}. Ctrl+Z undoes it.`);
}

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

const DOC_COMPLETE_MIN = 3; //: Below three characters almost anything matches.
const DOC_COMPLETE_MAX = 6;

let docCompleteWords = null;
let docCompleteMatches = [];
let docCompleteIndex = 0;
let docCompleteBox = null;

function docCompleteEnabled() {
  return $("doc-complete")?.checked !== false;
}

//: Rebuilt when the document changes rather than on every keystroke: a
//: 50,000-word document is a real thing to have here, and splitting it on each
//: character typed is the shape that makes an editor feel heavy.
function docBuildVocabulary() {
  const counts = new Map();
  const add = (word, weight) => {
    if (word.length < DOC_COMPLETE_MIN + 1) return;
    counts.set(word, (counts.get(word) || 0) + weight);
  };
  for (const word of docText().match(/[A-Za-z][A-Za-z'-]{2,}/g) || []) {
    //: Weighted above the notebook's words: while writing *this* document, the
    //: word you used two paragraphs ago is far likelier than one from a note
    //: last March.
    add(word, 3);
  }
  const entries = typeof allEntries !== "undefined" ? allEntries : [];
  for (const entry of entries.slice(0, 400)) {
    for (const word of String(entry.content || "").slice(0, 400).match(/[A-Za-z][A-Za-z'-]{2,}/g) || []) {
      add(word, 1);
    }
  }
  for (const doc of typeof docList !== "undefined" && Array.isArray(docList) ? docList : []) {
    for (const word of String(doc.title || "").match(/[A-Za-z][A-Za-z'-]{2,}/g) || []) add(word, 2);
  }
  docCompleteWords = [...counts.entries()].sort((a, b) => b[1] - a[1]);
}

//: The half-typed word immediately before the caret, or null. Deliberately not
//: offered mid-word: a caret inside "compl|etion" is someone fixing a letter,
//: and a popup there is in the way.
//:
//: **Read from the caret's line, not from the start of the document.** This
//: ran on every keystroke and asked the surface for its whole text to slice
//: two short strings out of it, which on a 20k-word document is 130,000
//: characters materialised per character typed: measured, it was the single
//: biggest thing left between the engine and PLAN P4's 30 ms gate. A word
//: fragment cannot span a line break, so the line is all this ever needed.
function docWordFragment(box) {
  const at = box.selection().from;
  const line = box.lineAt(at);
  const column = at - line.from;
  const upto = line.text.slice(0, column);
  const after = line.text.slice(column, column + 1);
  if (after && /[A-Za-z]/.test(after)) return null;
  const match = /[A-Za-z][A-Za-z'-]*$/.exec(upto);
  if (!match || match[0].length < DOC_COMPLETE_MIN) return null;
  //: Never inside a wiki link, that autocomplete owns those keystrokes, and
  //: two popups over one caret is worse than either alone.
  if (/\[\[[^\]]*$/.test(upto)) return null;
  return { start: line.from + match.index, fragment: match[0] };
}

function hideDocComplete() {
  const list = $("doc-complete-list");
  list?.classList.add("hidden");
  docReturnFromViewport(list);
  docCompleteMatches = [];
  docCompleteBox = null;
  if (typeof docProseGhostSet === "function") docProseGhostSet(null, "");
}

//: **The autofill rows for the caret, if it is at a trigger** (the owner,
//: 2026-09-24: "if I type lorem and press enter ... it will autofill the lorem
//: ipsum filler text"). The token and the rows are documents-prose.js's pure
//: `PROSE-FILL` region; this is the part that knows the editor: the caret's
//: line, the name in Settings, the renderer's heading ids. Prose only: a code
//: file has its own list (`docCodeTools`), and two lists at one caret is the
//: thing this file keeps refusing.
function docFillAt(box) {
  if (typeof docFillToken !== "function" || !docProseFillOn()) return null;
  const range = box.selection();
  if (range.from !== range.to) return null;
  const line = box.lineAt(range.from);
  const column = range.from - line.from;
  const tok = docFillToken(line.text.slice(0, column), line.text.slice(column));
  if (!tok) return null;
  //: The "/" menu and the `[[` menu own their keystrokes while open.
  if (typeof editorMenuState === "object" && editorMenuState?.open) return null;
  const options = docFillOptions(tok, {
    now: new Date(),
    locale: undefined,
    name: (typeof prefsCache === "object" && prefsCache?.display_name) || "",
    doc: tok.kind === "toc" ? docText() : "",
    slug: mdHeadingId,
  });
  if (!options.length) return null;
  return { start: line.from + tok.start, options };
}

function renderDocComplete(box) {
  const list = $("doc-complete-list");
  if (!list) return hideDocComplete();
  //: **One popup at the caret.** While the "/" menu is open, what is typed
  //: after the slash is its query, not a word to complete: measured, "/warn"
  //: drew the word list's "warning" over the top of the block menu's first
  //: group (INBOX 421 b's screenshot pass).
  if (typeof editorMenuState === "object" && editorMenuState?.open) return hideDocComplete();
  //: The expansions first, and whatever the word switch says: they answer a
  //: trigger the writer typed on purpose, where word suggestions are a guess.
  const fill = docFillAt(box);
  const at = docCompleteEnabled() ? docWordFragment(box) : null;
  let words = [];
  if (at) {
    if (!docCompleteWords) docBuildVocabulary();
    const needle = at.fragment.toLowerCase();
    words = docCompleteWords
      .filter(([word]) => word.toLowerCase().startsWith(needle) && word.toLowerCase() !== needle)
      .slice(0, DOC_COMPLETE_MAX)
      .map(([word]) => ({ word, typed: at.fragment.length }));
  }
  //: A row is `{word, typed}` (the rest of a word) or `{fill, start}` (an
  //: expansion that replaces from `start` to the caret).
  docCompleteMatches = [
    ...(fill ? fill.options.map((option) => ({ fill: option, start: fill.start })) : []),
    ...words,
  ];
  if (!docCompleteMatches.length) return hideDocComplete();

  docCompleteBox = box;
  docCompleteIndex = Math.min(docCompleteIndex, docCompleteMatches.length - 1);
  list.replaceChildren();
  docCompleteMatches.forEach((match, index) => {
    const li = document.createElement("li");
    li.setAttribute("role", "option");
    li.setAttribute("aria-selected", String(index === docCompleteIndex));
    li.classList.toggle("active", index === docCompleteIndex);
    if (match.fill) {
      //: The trigger in full strength, what it writes quieter: the same two
      //: inks a word row uses for typed and suggested. A shortcode leads with
      //: its glyph, which is the picker.
      li.classList.add("doc-complete-fill");
      if (match.fill.glyph) {
        const glyph = document.createElement("span");
        glyph.className = "doc-complete-glyph";
        glyph.textContent = match.fill.glyph;
        li.appendChild(glyph);
      }
      const head = document.createElement("b");
      head.textContent = match.fill.label;
      li.appendChild(head);
      if (match.fill.detail) {
        const detail = document.createElement("span");
        detail.className = "doc-complete-detail";
        detail.textContent = match.fill.detail;
        li.appendChild(detail);
      }
    } else {
      const head = document.createElement("b");
      head.textContent = match.word.slice(0, match.typed);
      const rest = document.createElement("span");
      rest.textContent = match.word.slice(match.typed);
      li.append(head, rest);
    }
    li.addEventListener("mousedown", (event) => {
      //: mousedown, not click: the textarea must not lose focus first, or the
      //: selection this writes into is gone by the time it runs.
      event.preventDefault();
      applyDocComplete(box, match);
    });
    list.appendChild(li);
  });
  //: The ghost after the caret, on the engine only: the chosen row's rest, as
  //: the code side draws it (`.cm-ghostText`).
  if (box.kind === "codemirror" && typeof docProseGhostSet === "function") {
    const chosen = docCompleteMatches[docCompleteIndex];
    const caret = box.selection().from;
    const ghost = chosen.fill ? docFillGhost(chosen.fill) : chosen.word.slice(chosen.typed);
    docProseGhostSet(caret, ghost);
  }
  const point = docCaretPoint(box);
  //: Kept on screen: a popup at the caret near the right edge or the bottom of
  //: the window would otherwise open off it, which is the app-wide rule for
  //: every menu here. Out of the card first, for the reason `docLiftToViewport`
  //: gives: this list is placed in viewport coordinates too, so a blurred
  //: ancestor moves it exactly as it moved the word menu.
  docLiftToViewport(list);
  list.classList.remove("hidden");
  const width = list.offsetWidth;
  const height = list.offsetHeight;
  const left = Math.min(point.left, window.innerWidth - width - 8);
  const below = point.bottom + 4;
  const flipped = below + height > window.innerHeight - 8 ? point.top - height - 4 : below;
  //: Clamped at both ends, not just at the top. A caret low in a short window
  //: flips the list above itself, and a list taller than the space above lands
  //: at a negative top, is pulled back to 8, and then draws its last rows off
  //: the bottom of the screen: the bug `placeDocSuggest` already records
  //: fixing on the word menu, in the one other popup that never got it.
  const top = Math.min(
    Math.max(8, flipped),
    Math.max(8, window.innerHeight - 8 - height)
  );
  docPlaceFixed(list, Math.max(8, left), top);
}

function applyDocComplete(box, match) {
  if (!match) return hideDocComplete();
  //: A range edit rather than a whole-value rewrite: on the engine that keeps
  //: the completion as one undo step over the fragment it replaced, and it
  //: costs the length of the word rather than the length of the document.
  const caret = box.selection().from;
  if (match.fill) {
    //: Read again at the moment of taking it, the rule `docProseFix` keeps: the
    //: row was drawn a keystroke ago, and a trigger that is no longer before
    //: the caret is not one to replace.
    const now = docFillAt(box);
    if (!now || now.start !== match.start) return hideDocComplete();
    const text = match.fill.text;
    box.replaceRange(match.start, caret, text);
    if (match.fill.select) {
      box.setSelection(match.start + match.fill.select[0], match.start + match.fill.select[1]);
    } else {
      box.setSelection(match.start + text.length);
    }
  } else {
    const at = docWordFragment(box);
    if (!at) return hideDocComplete();
    box.replaceRange(at.start, caret, match.word);
    box.setSelection(at.start + match.word.length);
  }
  hideDocComplete();
  box.focus();
  box.dispatchEvent(new Event("input", { bubbles: true }));
}

//: Returns true when it handled the key, so the caller knows not to let the
//: editor's own bindings see it, the same contract the editor menu's keys use.
function docCompleteKeydown(event, box) {
  const list = $("doc-complete-list");
  if (!list || list.classList.contains("hidden")) return false;
  if (event.key === "ArrowDown" || event.key === "ArrowUp") {
    event.preventDefault();
    const step = event.key === "ArrowDown" ? 1 : -1;
    docCompleteIndex =
      (docCompleteIndex + step + docCompleteMatches.length) % docCompleteMatches.length;
    renderDocComplete(box);
    return true;
  }
  //: **Tab for a word, and Enter only for an expansion.** Enter in a document
  //: is a new line, and stealing it for a guessed word is how an autocomplete
  //: becomes the thing you fight. An expansion is different: it answers a
  //: trigger typed on purpose (`lorem`, `today` on its own line, `:smile`),
  //: and "type lorem and press enter" is the ask it exists for. Escape, then
  //: Enter, is still a plain new line.
  const chosen = docCompleteMatches[docCompleteIndex];
  //: In a table cell Tab moves cells and never takes a word (dogfood item 8).
  if (event.key === "Tab" && docTableContext(box)) {
    hideDocComplete();
    return false;
  }
  if (event.key === "Tab" || (event.key === "Enter" && chosen?.fill && !event.shiftKey && !event.ctrlKey && !event.metaKey && !event.altKey)) {
    event.preventDefault();
    applyDocComplete(box, chosen);
    return true;
  }
  if (event.key === "Escape") {
    event.preventDefault();
    hideDocComplete();
    return true;
  }
  return false;
}

// --- autocorrect --------------------------------------------------------------

function docAutocorrectEnabled() {
  //: Never in a code file: `teh` may be a variable, and an editor that rewrote
  //: an identifier as you typed it would be unusable.
  return $("doc-autocorrect")?.checked === true && docFileType().previewable;
}

//: Fires on the keystroke that *finishes* a word, a space, a newline or
//: punctuation: which is the only moment a correction is unambiguous. Mid-word
//: it would rewrite "teh" while you were on your way to typing "tehran".
function docAutocorrectAt(box) {
  if (!docAutocorrectEnabled()) return false;
  const caret = box.selection().from;
  //: The caret's line, for the same reason `docWordFragment` reads one: this
  //: runs on every inserted character, and the word it is looking at cannot
  //: begin on a previous line.
  const line = box.lineAt(caret);
  const upto = line.text.slice(0, caret - line.from);
  const match = /([A-Za-z']+)([\s.,;:!?)\]]+)$/.exec(upto);
  if (!match) return false;
  //: Never the tail of a word with an accented letter ("ve" of naïve; D8).
  if (/\p{L}/u.test(upto[match.index - 1] || "")) return false;
  const lower = match[1].toLowerCase();
  //: A word the reader has accepted is never rewritten, whatever the typo list
  //: says. The dictionary is the reader's answer to this feature, and an
  //: autocorrect that ignored it would be the app overruling them mid-sentence.
  if (docDictionary().has(lower)) return false;
  //: And a word put back from the underline's menu (autocorrect.js) is not
  //: rewritten again this session, the same promise the note boxes keep.
  if (typeof autocorrectRefused !== "undefined" && autocorrectRefused.has(lower)) return false;
  let better = DOC_AUTOCORRECT[lower] || docVariantLookup().get(lower);
  //: **The dictionary's own unambiguous answers, on the same terms as the
  //: table's.** The table is 42 strings that are not words in any English
  //: text, which is the bar an automatic replacement has to clear because the
  //: cost of being wrong is that the app silently changed something the
  //: writer meant. `docSpellConfident` holds the same bar against 93,000
  //: words rather than 42: the word is not in any dictionary, and there is
  //: exactly one real word a swap of two letters away (or exactly one a
  //: dropped letter away, when no swap reaches one at all), and it is at
  //: least four letters long because almost every three-letter string is one
  //: edit from several real words. Anything with a choice in it stays a menu.
  if (!better) {
    //: The same refusals the check itself makes: an acronym, an identifier,
    //: a word touching a digit or a path is not prose and must never be
    //: rewritten. The line is the text these offsets are in.
    const at = caret - line.from - match[0].length;
    if (!docSpellable(line.text, match[1], at, at + match[1].length)) return false;
    const looked = docSpellLookup(match[1]);
    if (looked.known) return false;
    better = looked.sure;
  }
  if (!better) return false;
  const replacement = match[1][0] === match[1][0].toUpperCase()
    ? better[0].toUpperCase() + better.slice(1)
    : better;
  const start = caret - match[0].length;
  //: **Its own step in the history, or the toast below is a lie.** Typing is
  //: grouped into one undo entry per burst, so a correction folded into that
  //: burst means Ctrl+Z takes back the whole sentence rather than the
  //: correction. Measured 2026-09-12: one Ctrl+Z after "I ran a tets " left
  //: an empty document. Isolating before the replacement makes the first
  //: Ctrl+Z give back exactly what was typed, which is what the toast says
  //: and the only thing that makes an automatic rewrite acceptable.
  docUndoBreak();
  box.replaceRange(start, caret, replacement + match[2]);
  const next = start + replacement.length + match[2].length;
  box.setSelection(next);
  //: Announced, quietly and once. Software that changes what you typed and
  //: says nothing is the reason people turn autocorrect off, and this one
  //: names both words so a wrong correction is visible rather than found
  //: later.
  toast(`“${match[1]}” → “${replacement}”. Ctrl+Z undoes it.`);
  //: **Highlighted, with a menu on hover or click** (INBOX 904 B04), the same
  //: underline the note boxes get. autocorrect.js is lazy: the first
  //: correction of a visit fetches it (cached, so a promise already settled).
  const typedWord = match[1];
  lazyScript("/js/autocorrect.js").then(() => autocorrectShow(box, start, typedWord, replacement));
  return true;
}

// --- wiring -------------------------------------------------------------------
//
// One delegated pair on `document` rather than listeners per box: the live
// view replaces its textareas on every render, and per-box listeners are the
// shape that silently accumulates duplicates (tests/test_frontend_handlers.py
// exists because of exactly that).

const DOC_TOOL_KEYS = {
  autocorrect: "doc-autocorrect",
  complete: "doc-complete",
  //: INBOX 402: VS Code's Alt+Z and "render whitespace", for a code file.
  codeWrap: "doc-code-wrap",
  whitespace: "doc-whitespace",
  //: Brief 42: a name missing here was stored under the key "undefined".
  codeMinimap: "doc-minimap",
  //: L-documents-41: the opt-in Vim keymap, off by default.
  vimKeys: "doc-vim",
  //: Brief 69 (D6): Preview live in the run panel.
  runLive: "doc-run-live",
};

function docToolPref(name, fallback) {
  try {
    const stored = prefs.get(DOC_TOOL_KEYS[name], null);
    return stored === null ? fallback : stored === "1";
  } catch {
    return fallback; // private mode: the default shape
  }
}

function docSaveToolPref(name, on) {
  try {
    prefs.set(DOC_TOOL_KEYS[name], on ? "1" : "0");
  } catch {
    /* private mode: it just won't be remembered */
  }
}

const DOC_PROSE_DEBOUNCE_MS = 150;

let docProseTimer = null;
let docVocabTimer = null;

function docToolsOnInput(box) {
  renderDocCaret();
  renderDocComplete(box);
  //: Debounced, both of them: the prose pass walks the whole document and the
  //: vocabulary re-splits it, and neither is worth doing between two
  //: keystrokes.
  //:
  //: **150ms, down from 400.** The pause is no longer only about when the
  //: *panel* is current. Since Phase 0 it is also when the squiggle appears
  //: under the word you just misspelt, and DOCUMENTS_PLAN's acceptance for
  //: that is 300ms from the keystroke. At 400 the underline could not make it
  //: even with a free pass.
  //:
  //: The work itself is cheap, measured on a 2,629-character document in the
  //: sandbox Chromium: 0.82ms to find the findings and 6.3ms for the whole
  //: `renderDocProse`, which repaints the chip and asks the engine for a
  //: decoration pass over the visible lines. So the number here is almost the
  //: whole
  //: latency, and it is set for headroom rather than for the average: at 200
  //: the sweep measured 284ms end to end against a 300ms bound, which is a
  //: check that would fail on a slower machine while nothing was wrong.
  //: Still well over the gap between two keystrokes of ordinary typing, so
  //: this does not run mid-word.
  //:
  //: **Then an idle moment the next key withdraws** (DX1). On a slow machine
  //: one key's own work outlasted the 150 ms, so the timer fired between two
  //: keys of one burst, the pass (23 ms at 4x CPU in a 3,120-line document)
  //: made the next gap longer still, and it ran on 29 of 60 keys. So the
  //: pause is also counted in this typist's own rhythm: one and a half times
  //: the recent gap between keys (`gap`, under a second), never less than 150.
  const now = performance.now();
  const gap = now - (docToolsOnInput.at || -1e9);
  docToolsOnInput.gap = gap < 1000 ? (docToolsOnInput.gap ? docToolsOnInput.gap * 0.6 + gap * 0.4 : gap) : 0;
  docToolsOnInput.at = now;
  //: Shared with the facts pass and the grammar answer, which read them there.
  scheduleDocFacts.gap = docToolsOnInput.gap;
  docProse.typedAt = now;
  clearTimeout(docProseTimer);
  if (docToolsOnInput.idle) cancelIdleCallback(docToolsOnInput.idle);
  docToolsOnInput.idle = 0;
  const check = () => {
    docToolsOnInput.idle = 0;
    docProse.typing = true;
    try {
      renderDocProse();
    } finally {
      docProse.typing = false;
    }
  };
  docProseTimer = setTimeout(() => {
    if (window.requestIdleCallback) docToolsOnInput.idle = requestIdleCallback(check);
    else check();
  }, Math.max(DOC_PROSE_DEBOUNCE_MS, Math.min(600, 1.5 * docToolsOnInput.gap)));
  clearTimeout(docVocabTimer);
  docVocabTimer = setTimeout(() => {
    docCompleteWords = null;
  }, 1200);
}

//: **The editing box an event landed in, as a surface.** Three shapes reach
//: this: the fallback textarea, a live-view paragraph, and any node inside
//: CodeMirror's editable, which is a `div` and so matches none of the
//: textarea checks that used to be the whole of this function. Returning null
//: for anything else is what keeps the instruments off the note composer.
function docToolsBoxFor(target) {
  //: A surface as well as a node, because half the callers now hold one
  //: already (`applyMarkdown`'s Undo branch is the one that caught this: with
  //: a surface passed to the old element-only check it returned null and the
  //: toolbar's Undo silently fell through to `execCommand`).
  if (target && (target.kind === "textarea" || target.kind === "codemirror")) {
    return target.isDocument ? target : null;
  }
  if (target instanceof HTMLTextAreaElement) {
    return target.id === "doc-content" ? textareaSurface(target) : null;
  }
  return docEventFromCm(target) ? docSurface() : null;
}

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
    document.body.classList.add("resizing-sidebar");
    //: Dragging left (a negative delta) widens it: the mirror of a sidebar.
    const move = (e) => docProseApplyWidth(startWidth - (e.clientX - startX));
    const stop = () => {
      document.body.classList.remove("resizing-sidebar");
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", stop);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", stop);
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

//: Painted once on load so the bar is not blank before the first keystroke,
//: and again whenever a document is opened, `openDocument` calls this.
//:
//: **The call that runs it at load time is the last line of this file**, not
//: this one. `const`/`let` at module scope are hoisted into a temporal dead
//: zone, so calling this here threw `Cannot access 'docDictionarySet' before
//: initialization` the moment the dictionary and the spelling tables were
//: added below: a real crash, caught in the browser, that no amount of
//: reading the function would have shown.
function renderDocTools() {
  docCompleteWords = null;
  renderDocStatusBar();
  renderDocProse();
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

//: **US and UK, as an explicit list rather than a rule.** The rules everyone
//: reaches for are wrong often enough to be useless: `-ise/-ize` turns "size"
//: into "sise", `-our/-or` turns "four" into "for". Every pair here is a word
//: whose two spellings are both real and mean the same thing, which is the only
//: case where suggesting the other one is safe.
//:
//: UK on the left, US on the right, and the direction is chosen by the setting
//:, the checker never has an opinion about which is correct, only about which
//: one this notebook was told to use.
const DOC_SPELLING_PAIRS = [
  ["colour", "color"], ["colours", "colors"], ["coloured", "colored"],
  ["favourite", "favorite"], ["favourites", "favorites"], ["favour", "favor"],
  ["behaviour", "behavior"], ["behaviours", "behaviors"],
  ["honour", "honor"], ["labour", "labor"], ["neighbour", "neighbor"],
  ["humour", "humor"], ["rumour", "rumor"], ["flavour", "flavor"],
  ["harbour", "harbor"], ["endeavour", "endeavor"], ["armour", "armor"],
  ["centre", "center"], ["centres", "centers"], ["metre", "meter"],
  ["metres", "meters"], ["litre", "liter"], ["litres", "liters"],
  ["theatre", "theater"], ["fibre", "fiber"], ["calibre", "caliber"],
  ["organise", "organize"], ["organised", "organized"], ["organising", "organizing"],
  ["organisation", "organization"], ["organisations", "organizations"],
  ["recognise", "recognize"], ["recognised", "recognized"],
  ["realise", "realize"], ["realised", "realized"],
  ["apologise", "apologize"], ["analyse", "analyze"], ["analysed", "analyzed"],
  ["prioritise", "prioritize"], ["summarise", "summarize"],
  ["specialise", "specialize"], ["categorise", "categorize"],
  ["catalogue", "catalog"], ["dialogue", "dialog"], ["programme", "program"],
  ["licence", "license"], ["defence", "defense"], ["offence", "offense"],
  ["practise", "practice"], ["grey", "gray"], ["cheque", "check"],
  ["travelling", "traveling"], ["travelled", "traveled"], ["traveller", "traveler"],
  ["cancelled", "canceled"], ["cancelling", "canceling"], ["modelling", "modeling"],
  ["labelled", "labeled"], ["fulfil", "fulfill"], ["enrol", "enroll"],
  ["storey", "story"], ["tyre", "tire"], ["kerb", "curb"], ["plough", "plow"],
  ["aluminium", "aluminum"], ["sceptical", "skeptical"], ["moustache", "mustache"],
  ["draught", "draft"], ["pyjamas", "pajamas"], ["jewellery", "jewelry"],
  ["marvellous", "marvelous"], ["towards", "toward"],
];

//: The setting's five values (VC6) read the one table: Australian and Indian
//: spell as the British column does for every pair here; Canadian is the
//: mixed one (`DOC_CA_KEEPS_UK`). The label is what a finding says.
const DOC_VARIANT_FAMILY = { us: "us", uk: "uk", au: "uk", in: "uk", ca: "ca" };
const DOC_VARIANT_LABEL = { us: "US", uk: "UK", au: "Australian", ca: "Canadian", in: "Indian" };
//: Canada spells -our, -re, -ce, grey, cheque and the doubled l the British
//: way and -ize and the rest the American way ("tyre" is "tire" there).
const DOC_CA_KEEPS_UK =
  /^(?!tyre$)([a-z]*(our(s|ed|ite|ites)?|re|res|ce|ces|ll(ed|ing|er))|grey|cheque|jewellery|marvellous|catalogue)$/;

//: Built once from the pairs above, in whichever direction the setting names.
//: A map rather than a scan, because this runs per word of the document.
let docVariantMap = null;
let docVariantFor = null;

//: **"auto" is the default** (INBOX 1731): the dialect of the computer's own
//: language, so an Australian notebook is checked as Australian without the
//: owner finding the select first. Anything not English, or a tag with no
//: dialect of its own, is "off" (no preference); the rest of the English-
//: speaking world that spells the British way reads as British.
function docSpellingVariant() {
  const set = (prefsCache && prefsCache.spelling_variant) || "auto";
  if (set !== "auto") return set;
  const tag = String((typeof navigator === "object" && navigator && navigator.language) || "").toLowerCase();
  const byTag = { "en-au": "au", "en-nz": "au", "en-gb": "uk", "en-us": "us", "en-ca": "ca", "en-in": "in" };
  return byTag[tag] || (/^en-(ie|za|sg|my)$/.test(tag) ? "uk" : "off");
}

function docVariantLookup() {
  const variant = docSpellingVariant();
  if (docVariantFor === variant && docVariantMap) return docVariantMap;
  docVariantFor = variant;
  docVariantMap = new Map();
  const family = DOC_VARIANT_FAMILY[variant];
  if (!family) return docVariantMap;
  for (const [uk, us] of DOC_SPELLING_PAIRS) {
    //: Canada keeps some of each side: -our, -re, -ce and the doubled l from
    //: the left, -ize and the rest from the right.
    const british = family === "uk" || (family === "ca" && DOC_CA_KEEPS_UK.test(uk));
    if (british) docVariantMap.set(us, uk);
    else docVariantMap.set(uk, us);
  }
  return docVariantMap;
}

//: The words the reader has told this to accept. A Set, lowercased, because a
//: word added at the start of a sentence must not have to be added again in
//: the middle of one.
let docDictionarySet = null;

//: **The array the set was last built from, compared by identity.** This pair
//: is the fix for a report that was worse than it read: *"I swear I added
//: 'idk' to the dictionary last night, make sure it is persistent."*
//:
//: The set used to be memoised with `if (!docDictionarySet)`, and an empty
//: `Set` is truthy, so the first call won for the rest of the session. The
//: first call happens at the bottom of this file, which runs `renderDocTools`
//: at parse time; `prefsCache` is filled by an async fetch in app.js that has
//: not resolved yet. So the dictionary was built empty, every saved word was
//: unknown for the whole session, and, worse, `docDictionaryWrite` below sends
//: `[...docDictionary(), newWord]`: the first word you added after a reload
//: replaced your entire saved dictionary with that one word. Silent data loss,
//: and it is why a word added last night was being offered again today.
//:
//: Identity rather than a dirty flag, because `apiJson` returns a fresh object
//: on every read and `prefsCache` is reassigned in a dozen places across
//: app.js. Anything that reloads preferences therefore rebuilds this set
//: without having to know it exists, which is the property that stops the same
//: bug coming back through a new caller.
let docDictionarySource = null;

function docDictionary() {
  const source = (prefsCache && prefsCache.writing_dictionary) || null;
  if (!docDictionarySet || docDictionarySource !== source) {
    docDictionarySource = source;
    docDictionarySet = new Set((source || []).map((word) => String(word).toLowerCase()));
    //: A rebuilt dictionary means every cached per-word answer was answered
    //: against the old one, including the "not a word" answers that put the
    //: underlines on screen.
    docKnownWordsCache = null;
    docSpellCache = new Map();
  }
  return docDictionarySet;
}

async function docDictionaryWrite(words) {
  docDictionarySet = new Set(words.map((word) => word.toLowerCase()));
  //: Pinned to the preferences this set now speaks for, so the optimistic add
  //: above survives any read between here and the response: without it, the
  //: next `docDictionary()` would see the old array still on `prefsCache`,
  //: decide the set was stale and rebuild it without the word just added. When
  //: the PUT below replaces `prefsCache`, the identity changes and the set is
  //: rebuilt from what the server actually stored, which is the right answer.
  docDictionarySource = (prefsCache && prefsCache.writing_dictionary) || null;
  //: The ranked suggestions are drawn from this list, so a word added here has
  //: to be offerable on the very next menu rather than after a reload, and
  //: the per-word answers have to forget the word that has just been accepted.
  docKnownWordsCache = null;
  docSpellCache = new Map();
  prefsCache = await apiJson("/preferences", {
    method: "PUT",
    body: JSON.stringify({ writing_dictionary: [...docDictionarySet].sort() }),
  }).catch(() => prefsCache);
  docSpell.ownWordsSend();
  renderDocProse();
}

async function docDictionaryAdd(word) {
  const clean = String(word || "").trim();
  if (!clean) return;
  const lower = clean.toLowerCase();
  const without = () => docDictionaryWrite([...docDictionary()].filter((other) => other !== lower));
  const add = () => docDictionaryWrite([...docDictionary(), lower]);
  await add();
  offerUndo(`Added “${clean}” to the dictionary`, `“${clean}” added to your dictionary.`, without, add);
}

//: Findings dismissed for this sitting only. Not persisted, deliberately:
//: "not this time" is a statement about one sentence, and remembering it
//: forever would quietly turn a check off with no way to see that it is off.
const docProseIgnored = new Set();

function docProseKey(finding) {
  //: Scoped to the document, because the row says "in this document" and a
  //: dismissal that silently applied to the next document you opened would be
  //: the checker turning itself off with no way to see that it had.
  const scope = currentDoc && currentDoc.id ? currentDoc.id : "unsaved";
  return `${scope}:${finding.rule}:${finding.text.toLowerCase()}`;
}

//: **The popup, and the four answers a person actually has.** Fix it, this is
//: a word, not this time, and, for a spelling, always correct it. Anchored
//: at the thing it is about, because a menu that opens somewhere else makes
//: you re-find the word you were looking at.
let docSuggestOpenFor = null;

function closeDocSuggest() {
  const menu = $("doc-suggest-menu");
  menu?.classList.add("hidden");
  docReturnFromViewport(menu);
  docSuggestOpenFor = null;
}

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

const DOC_SUGGEST_MAX = 5;

//: Two edits. Three matches almost anything at these word lengths, and the
//: third suggestion for a five-letter word is noise a reader has to read
//: before dismissing.
const DOC_SUGGEST_DISTANCE = 2;

//: The vocabulary of a big notebook is tens of thousands of words and this
//: runs while a menu is opening, so the scan is bounded. `docCompleteWords`
//: is sorted by how often you use a word, so the cap keeps the words most
//: likely to be the one you meant.
const DOC_SUGGEST_CANDIDATES = 3000;

//: **Optimal string alignment**, which is Damerau-Levenshtein restricted to
//: adjacent transpositions. The restriction is the right one here: the typos
//: this is for are a swapped pair (`teh`), a doubled or dropped letter, or a
//: neighbouring key, and full Damerau's extra bookkeeping buys nothing for
//: those while costing more per candidate on a list scanned thousands of
//: times.
//:
//: `cap` is not an optimisation detail, it is what keeps the answer sensible:
//: a row whose minimum is already past the cap cannot produce a distance
//: under it, so the rest of the matrix is not computed, and any word more
//: than `cap` edits away is not a suggestion at all.
function docEditDistance(a, b, cap) {
  if (Math.abs(a.length - b.length) > cap) return cap + 1;
  if (a === b) return 0;
  let previous = Array.from({ length: b.length + 1 }, (_, i) => i);
  let beforePrevious = null;
  for (let i = 1; i <= a.length; i += 1) {
    const row = new Array(b.length + 1);
    row[0] = i;
    let best = row[0];
    for (let j = 1; j <= b.length; j += 1) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1;
      let value = Math.min(row[j - 1] + 1, previous[j] + 1, previous[j - 1] + cost);
      if (i > 1 && j > 1 && a[i - 1] === b[j - 2] && a[i - 2] === b[j - 1]) {
        value = Math.min(value, beforePrevious[j - 2] + 1);
      }
      row[j] = value;
      if (value < best) best = value;
    }
    if (best > cap) return cap + 1;
    beforePrevious = previous;
    previous = row;
  }
  return previous[b.length];
}

//: The words this app can say it knows, as opposed to the words it has seen.
//: Rebuilt when the dictionary changes, which is the only thing that can add
//: to it.
let docKnownWordsCache = null;

function docKnownWords() {
  if (docKnownWordsCache) return docKnownWordsCache;
  const pool = new Set(docDictionary());
  for (const correction of Object.values(DOC_AUTOCORRECT)) pool.add(correction.toLowerCase());
  for (const [uk, us] of DOC_SPELLING_PAIRS) {
    pool.add(uk);
    pool.add(us);
  }
  docKnownWordsCache = [...pool];
  return docKnownWordsCache;
}

//: A typo at the start of a sentence must not be corrected into a lowercase
//: word, and a suggestion for `Recieve` that comes back as `receive` reads as
//: a second mistake. The same rule the built-in fixes already follow, pulled
//: out so every source of a suggestion follows it too.
function docMatchCase(sample, word) {
  if (!sample || !word) return word;
  if (sample[0] !== sample[0].toUpperCase()) return word;
  return word[0].toUpperCase() + word.slice(1);
}

//: `skip` is read, never written. It held the words already offered, and an
//: earlier draft also *added* each result to it as a way of not repeating
//: itself between the two candidate lists. That silently returned nothing at
//: all: the caller's own de-duplicating `push` reads the same set, so every
//: word this function found had already been marked as seen by the time it
//: was offered. Measured, not reasoned: the ranked list came back empty for a
//: word one edit from `environment` while `docNearestWords` on its own
//: returned it.
function docNearestWords(word, candidates, limit, skip) {
  const lower = word.toLowerCase();
  const scored = [];
  let scanned = 0;
  for (const candidate of candidates) {
    if (scanned >= DOC_SUGGEST_CANDIDATES) break;
    scanned += 1;
    const clean = String(candidate).toLowerCase();
    if (clean === lower || skip.has(clean)) continue;
    if (Math.abs(clean.length - lower.length) > DOC_SUGGEST_DISTANCE) continue;
    const distance = docEditDistance(lower, clean, DOC_SUGGEST_DISTANCE);
    if (distance <= DOC_SUGGEST_DISTANCE) scored.push([clean, distance]);
  }
  //: Distance first, then alphabetically, so the same word always sorts to
  //: the same place. A menu whose rows move between two openings of the same
  //: word is one nobody learns the shape of.
  scored.sort((a, b) => a[1] - b[1] || (a[0] < b[0] ? -1 : 1));
  return scored.slice(0, limit).map(([candidate]) => candidate);
}

//: Word-level rules only. "The nearest word to `,,` by edit distance" is not
//: a question with an answer, and the punctuation rules already carry the one
//: correct fix in `replacement`.
const DOC_WORD_RULES = new Set(["spelling", "variant"]);

//: What the menu calls the thing it is about. Visible text wherever there is
//: any, and a description of the whitespace wherever there is not.
function docFindingLabel(finding) {
  const text = finding.text || "";
  if (text.trim()) return text.replace(/\s+/g, " ").slice(0, 48);
  if (/^\n+$/.test(text)) return `${text.length} blank line${text.length === 1 ? "" : "s"}`;
  return nounCount(text.length, "space");
}

function docSuggestAlternatives(finding) {
  //: More than one plausible answer, where there is one. A single suggestion
  //: presented as *the* answer is how a checker quietly rewrites someone's
  //: voice; two or three make it a choice.
  const out = [];
  const seen = new Set();
  const push = (word) => {
    const clean = String(word);
    const key = clean.toLowerCase();
    if (!clean || seen.has(key) || key === finding.text.toLowerCase()) return;
    seen.add(key);
    out.push(clean);
  };
  if (finding.replacement !== null && finding.replacement !== undefined) {
    push(finding.replacement);
  }
  //: A grammar finding carries its checker's own answers, in its order. An
  //: empty one means "remove it", which `push` would drop as blank.
  if (Array.isArray(finding.alternatives)) {
    for (const option of finding.alternatives) {
      if (out.length >= DOC_SUGGEST_MAX) break;
      if (option === "") {
        if (!out.includes("")) out.push("");
      } else {
        push(option);
      }
    }
  }
  if (DOC_WORD_RULES.has(finding.rule)) {
    const lower = finding.text.toLowerCase();
    //: The other direction of the variant table, so a document set to UK still
    //: offers the US spelling as the second option rather than pretending it
    //: does not exist.
    for (const [uk, us] of DOC_SPELLING_PAIRS) {
      if (uk === lower) push(docMatchCase(finding.text, us));
      if (us === lower) push(docMatchCase(finding.text, uk));
    }
    //: **The dictionary's own answer, first.** These are real words one or
    //: two edits from what was typed, which is what a person means by "what
    //: did I mean to write". The two pools below stay underneath it because
    //: they still answer the cases it cannot: a word the reader added, and a
    //: word that appears in their own notes and in no dictionary.
    //: **The dictionary's answers, most common first** (INBOX 1731): the
    //: worker's, already ranked by how common the word is. Every pool here
    //: drops a suggestion that changes more than a third of a short word.
    const second = docSpell.answer(docSpellRoot(finding.text));
    for (const word of second ? second.suggestions : []) push(docMatchCase(finding.text, word));
    const near = (word) => docEditDistance(docSpellRoot(finding.text), word.toLowerCase(), 99) <= Math.max(1, Math.floor(finding.text.length / 3));
    if (out.length < DOC_SUGGEST_MAX) {
      const guesses = finding.guesses || docSpellGuesses(finding.text, DOC_SUGGEST_MAX);
      for (const word of guesses) {
        if (out.length >= DOC_SUGGEST_MAX) break;
        if (near(word)) push(docMatchCase(finding.text, word));
      }
    }
    if (out.length < DOC_SUGGEST_MAX) {
      for (const word of docNearestWords(finding.text, docKnownWords(), DOC_SUGGEST_MAX - out.length, seen)) {
        if (near(word)) push(docMatchCase(finding.text, word));
      }
    }
    if (out.length < DOC_SUGGEST_MAX) {
      //: Built on demand rather than kept warm: this is the only caller that
      //: needs it before the first completion popup, and building it walks the
      //: document and four hundred notes.
      if (!docCompleteWords) docBuildVocabulary();
      const vocabulary = (docCompleteWords || []).map(([word]) => word);
      for (const word of docNearestWords(finding.text, vocabulary, DOC_SUGGEST_MAX - out.length, seen)) {
        if (near(word)) push(docMatchCase(finding.text, word));
      }
    }
  }
  return out.slice(0, DOC_SUGGEST_MAX);
}

//: **One drawing of a finding, wherever one is drawn** (DOCUMENTS_PLAN 12 D1).
//: The panel row said the reason and then the words, the menu's head said the
//: words and then the reason, and the underline said neither, so one object was
//: described three ways and a reader had to re-read the list to match a row to
//: the word it was about. Here it is one line in one order: a dot in the same
//: colour as that kind's underline, the words, the reason. The dot is the link
//: back to the text, and it is the one mark the three surfaces share.
function docFindingLine(finding, variant = "row") {
  const line = document.createElement("span");
  line.className = `doc-finding-line doc-finding-line-${variant}`;
  const dot = document.createElement("span");
  dot.className = `doc-finding-dot doc-finding-dot-${docFindingKind(finding)}`;
  dot.setAttribute("aria-hidden", "true");
  const words = document.createElement("span");
  words.className = "doc-finding-words";
  //: A spacing finding's text *is* whitespace, so a heading built from it
  //: rendered as an empty bold nothing. Said in words instead: "three spaces"
  //: is a thing you can look for in the line, an empty heading is not.
  words.textContent = docFindingLabel(finding);
  const why = document.createElement("span");
  why.className = "doc-finding-why";
  const hint = variant === "row" ? docSpellGuesses.hint(finding) : "";
  why.textContent = hint ? `Did you mean \u201c${hint}\u201d?` : finding.message;
  //: Both halves ellipsise in a narrow panel (INBOX 426 b), so each carries
  //: its whole text as a title: the nearest title is the one the pointer
  //: shows, so these win over the row button's "show me this" hint only
  //: where the words themselves are under it.
  words.title = words.textContent;
  why.title = why.textContent;
  line.append(dot, words, why);
  return line;
}

//: **Is this finding a passage or a word?** (DOCUMENTS_PLAN 12 D2.) A
//: misspelling's other wordings *are* the candidate list above it, and
//: "translate this passage" over one word is a dictionary lookup wearing the
//: wrong label: both rows belong to a finding that is a run of words (a
//: repeat, a long sentence), and offering them on every spelling made the
//: common menu nine rows deep. Whitespace-only findings (a double space) are
//: not passages either: there is nothing in them to rephrase.
function docFindingIsPassage(finding) {
  //: A link offer's answer is the link; asking a model to reword a title
  //: would be a different question.
  return finding.rule !== "link-offer" && /\s/.test(String(finding.text || "").trim());
}

//: The answers to a finding (rows as data, and the buttons drawn from them): documents-suggest.js, fetched on first
//: use. Each is a stand-in the piece's function of the same name replaces on load, so a caller awaits it.
async function docFindingAnswerRows(...args) {
  if (!(await lazyScript("/js/documents-suggest.js"))) return toast("The suggestions could not be loaded.", true, { action: ["Try again", () => docFindingAnswerRows(...args)] }), [];
  return docSuggestPiece.docFindingAnswerRows(...args);
}

async function docSuggestAnswers(...args) {
  if (!(await lazyScript("/js/documents-suggest.js"))) return toast("The suggestions could not be loaded.", true, { action: ["Try again", () => docSuggestAnswers(...args)] }), document.createDocumentFragment();
  return docSuggestPiece.docSuggestAnswers(...args);
}

//: **The popup, the translate hand-off, Discuss in chat and the AI review** are
//: documents-suggest.js, fetched on first use. Each name here is a stand-in: the
//: piece's own function of the same name replaces it on load, so calling the name
//: again after the fetch reaches the real one. Nothing reads their return.
async function openDocSuggest(...args) {
  if (!(await lazyScript("/js/documents-suggest.js"))) return toast("The suggestions could not be loaded.", true, { action: ["Try again", () => openDocSuggest(...args)] });
  return docSuggestPiece.openDocSuggest(...args);
}

async function docTranslatePassage(...args) {
  if (!(await lazyScript("/js/documents-suggest.js"))) return toast("The suggestions could not be loaded.", true, { action: ["Try again", () => docTranslatePassage(...args)] });
  return docSuggestPiece.docTranslatePassage(...args);
}

async function docAiDiscussInChat(...args) {
  if (!(await lazyScript("/js/documents-suggest.js"))) return toast("The suggestions could not be loaded.", true, { action: ["Try again", () => docAiDiscussInChat(...args)] });
  return docSuggestPiece.docAiDiscussInChat(...args);
}

async function docAiReview(...args) {
  if (!(await lazyScript("/js/documents-suggest.js"))) return toast("The suggestions could not be loaded.", true, { action: ["Try again", () => docAiReview(...args)] });
  return docSuggestPiece.docAiReview(...args);
}

//: **A popup placed in viewport coordinates has to live in the viewport's own
//: frame, and inside this tab it did not.** INBOX 168, with a screenshot: the
//: word menu for "tets" drawn at the right edge of the window with its column
//: cut off past it and its list under the bottom bar. Every clamp in
//: `placeDocSuggest` is unconditional, so the menu cannot leave the viewport
//: by arithmetic; what it can do is be laid out against something that is not
//: the viewport. A `position: fixed` element is laid out against the nearest
//: ancestor carrying a `filter`, `transform` or `backdrop-filter`, and
//: `.card.doc-main` is exactly that whenever the background art is on
//: (`:root[data-bg-art="on"]:not([data-glass="off"]) .card`, which is the
//: default pair of settings the moment someone turns the art on). Measured at
//: 1440x900 with the art on, before this: the menu asked for `left 952, top
//: 322` and rendered at `1245..1485, 399`, 45px past the right edge of the
//: window and 53px away from the word it belongs to, which is also INBOX 128's
//: "wide gap". The same blur makes the card a stacking context, so no z-index
//: could lift the menu over the bars outside it either.
//:
//: So the popup leaves the card while it is open and goes back on a comment
//: placeholder on the way out, the same move `buildTableBlock`'s full view
//: makes for the same reason. It has to be a move rather than a stylesheet
//: change: the card's blur is a deliberate part of the background-art look,
//: and a viewport popup has no business being a descendant of a surface that
//: can be blurred, transformed or scaled at any time.
const docLiftedHome = new WeakMap();

function docLiftToViewport(el) {
  if (!el || el.parentElement === document.body) return el;
  const home = document.createComment(`${el.id || "popup"} while it is open`);
  el.replaceWith(home);
  docLiftedHome.set(el, home);
  document.body.appendChild(el);
  return el;
}

function docReturnFromViewport(el) {
  const home = el && docLiftedHome.get(el);
  if (!home || !home.parentNode) return;
  home.replaceWith(el);
  docLiftedHome.delete(el);
}

//: **Ask for a viewport position, then check the popup landed there.** The
//: belt to the braces above: body itself can carry a transform (a page
//: animation, a future shell), and one ancestor with a filter anywhere in the
//: chain silently turns every number here into an offset from somewhere else.
//: Measuring what was drawn and correcting by the difference costs one rect
//: read and is exact for any containing block that only translates the frame,
//: which is what a filter, a backdrop-filter and a translate all do. It is a
//: no-op, and reads as one, when the frame is the viewport.
function docPlaceFixed(el, left, top) {
  el.style.left = `${Math.round(left)}px`;
  el.style.top = `${Math.round(top)}px`;
  const at = el.getBoundingClientRect();
  const dx = left - at.left;
  const dy = top - at.top;
  if (Math.abs(dx) > 0.5 || Math.abs(dy) > 0.5) {
    el.style.left = `${Math.round(left + dx)}px`;
    el.style.top = `${Math.round(top + dy)}px`;
  }
}

//: Kept so the menu can be re-placed after it changes size, the AI wordings
//: arrive seconds after it opens and make it taller, and a menu that grew
//: downwards off the bottom of the window is a menu whose best suggestion is
//: unreachable.
let docSuggestAnchor = null;

//: The gap the menu keeps from the word, and from every edge it is clamped to.
const DOC_SUGGEST_GAP = 4;
const DOC_SUGGEST_EDGE = 8;

//: **The band the menu is allowed to occupy: the editor's own box first, the
//: window second** (DOCUMENTS_PLAN 12 D4).
//:
//: Reported as "the popup edit suggestions menu screws upn the screen and make
//: sit go out of bounds", and measured: a flagged word at the end of a long
//: line sits at `left 1161` in a card whose right edge is `1255`, and clamping
//: to the *window* put the menu at `1161..1401`, so 146 of its 240px hung past
//: the card into the window's own gutter, pointing at a document it was no
//: longer over. The window is not the frame this menu belongs to; the text is.
//:
//: Only when the card is actually wide enough to hold it: below that the band
//: would be narrower than the menu and every placement inside it would be a
//: lie, so a narrow window falls back to the viewport, which is the one frame
//: that always exists.
function docSuggestBand(width) {
  const band = {
    min: DOC_SUGGEST_EDGE,
    max: window.innerWidth - DOC_SUGGEST_EDGE,
  };
  const host = docCmView ? docCmView.dom.getBoundingClientRect() : docSurface()?.rect?.();
  if (host && host.right - host.left >= width + 2) {
    band.min = Math.max(band.min, host.left);
    band.max = Math.min(band.max, host.right);
  }
  return band;
}

function placeDocSuggest() {
  const menu = $("doc-suggest-menu");
  if (!menu || !docSuggestAnchor || menu.classList.contains("hidden")) return;
  //: Measured after it is visible, because a hidden element measures zero and
  //: a menu positioned against zero opens in the corner. And measured parked
  //: at the window's left edge, not wherever the last open left it: a fixed
  //: box with `left` and no `right` is shrink-to-fit against the room to its
  //: right, so a short menu left near the right edge and then filled with a
  //: long candidate measured 256px of its 316 at 390 wide and was placed
  //: from that, its right edge on the window's (`wordmenuwidth.js`).
  docPlaceFixed(menu, DOC_SUGGEST_EDGE, DOC_SUGGEST_EDGE);
  const width = menu.offsetWidth;
  const height = menu.offsetHeight;
  const band = docSuggestBand(width);

  //: Left edge against the word's left edge, which is where a menu about a word
  //: reads from. When that would cross the band's right edge the menu is
  //: *right-aligned to the word* instead of slid back along it: the two boxes
  //: then share an edge, which still reads as "this belongs to that word", and
  //: the menu ends up beside the word rather than hanging off the card.
  let left = docSuggestAnchor.left;
  if (left + width > band.max) left = (docSuggestAnchor.right ?? docSuggestAnchor.left) - width;
  left = Math.max(band.min, Math.min(left, band.max - width));

  //: Below the word, above it when there is no room below, and clamped to the
  //: window in both directions. The old version clamped the *top* only, so an
  //: anchor low in a short window flipped to a negative top, was pulled back to
  //: 8, and drew its bottom rows off the end of the screen.
  let top = docSuggestAnchor.bottom + DOC_SUGGEST_GAP;
  if (top + height > window.innerHeight - DOC_SUGGEST_EDGE) {
    const above = docSuggestAnchor.top - height - DOC_SUGGEST_GAP;
    top = above >= DOC_SUGGEST_EDGE ? above : top;
  }
  top = Math.max(
    DOC_SUGGEST_EDGE,
    Math.min(top, window.innerHeight - DOC_SUGGEST_EDGE - height)
  );

  docPlaceFixed(menu, left, top);
}

//: **A menu about a word goes where the word goes, or it goes away.** The
//: anchor is copied at open time, so anything that moves the text under an
//: open menu leaves it pointing at whatever has scrolled into that spot: the
//: editor scrolled with the wheel, the window resized, the sidebar or the chat
//: dock opened beside it. None of those reach the mousedown and input
//: listeners that close this menu, which is why it could be left stranded.
//:
//: Re-measured rather than re-clamped: the stored rect is the stale thing, so
//: placing it again would only move a wrong answer. The mark is found again
//: from the finding the menu is open on, and when it has left the editor's
//: visible box, or is no longer drawn at all, the menu closes, which is
//: DOCUMENTS_PLAN 12 D4's rule ("a menu that points at a word that is off
//: screen is a menu pointing at nothing") applied after the open rather than
//: only during it.
function docSuggestFollowAnchor(event) {
  const menu = $("doc-suggest-menu");
  if (!menu || menu.classList.contains("hidden") || !docSuggestOpenFor) return;
  //: The menu scrolls its own overflow, and that scroll reaches this listener
  //: in the capture phase like any other. Following the word because someone
  //: is reading the last row of the menu would be absurd.
  if (event && event.target instanceof Node && menu.contains(event.target)) return;
  const rect = docFindingAnchor(docSuggestOpenFor, null);
  const host = docCmView ? docCmView.dom.getBoundingClientRect() : docSurface()?.rect?.();
  if (!rect || (host && (rect.bottom <= host.top + 1 || rect.top >= host.bottom - 1))) {
    return closeDocSuggest();
  }
  docSuggestAnchor = {
    left: rect.left,
    right: rect.right ?? rect.left,
    top: rect.top,
    bottom: rect.bottom,
  };
  placeDocSuggest();
}

let docSuggestFollowFrame = 0;
function docScheduleSuggestFollow() {
  if (docSuggestFollowFrame) return;
  docSuggestFollowFrame = requestAnimationFrame(() => {
    docSuggestFollowFrame = 0;
    docSuggestFollowAnchor(null);
  });
}

window.addEventListener("resize", docSuggestFollowAnchor);
//: Capture, because the scroll that matters is the editor's own and a scroll
//: event does not bubble.
window.addEventListener("scroll", docSuggestFollowAnchor, true);


let docLastTranslateLanguage = "";

// --- Check with AI, in place (INBOX 410) -----------------------------------
//
// The owner, 2026-09-24: "improve how the 'check with ai' feature works in the
// documents editor." It used to leave the editor for the Chat tab, answer in a
// bubble with nothing to apply, and raise a skill suggestion that did not fit
// (INBOX 413). Now it stays: `POST /documents/{id}/ai-check` streams findings
// (the exact words, a one-line reason, a one-line fix) and each becomes a
// finding of kind `ai`, so it is underlined in the text, listed in the panel
// under its own group, and answered by the same row and the same answers every
// other finding has (`docFindingLine`, `docSuggestAnswers`), with Apply (the
// row's check) and Dismiss. Stop is the button that started it. The model is
// the documents feature's (Settings, Models, per feature).

//: `state` is idle, running, done, stopped, offline or failed; `items` are
//: `{text, message, replacement, near}` as they arrived, located afresh on every
//: pass (`docAiFindings`) because the writer may keep typing while it runs.
//: `mode` is "ai" or "claims" (Check claims against my notes, Phase G): the claim
//: check puts its verdicts in the same `items`, each with a `claim` `{verdict, note}`.
const docAiCheck = {
  state: "idle", items: [], message: "", controller: null, docId: null, mode: "ai",
  //: One request, no stream: the server writes nothing and answers every sentence.
  async claims() {
    if (docAiCheck.state === "running") return;
    const box = docSurface();
    const full = box?.text || "";
    if (!full.trim()) return toast("Nothing to check yet.", "info");
    const doc = currentDoc || (await ensureDocumentExists().catch(() => null));
    if (!doc) return toast("Nothing to check yet.", "info");
    Object.assign(docAiCheck, { state: "running", items: [], message: "", controller: null, docId: doc.id, mode: "claims" });
    $("doc-prose-panel")?.classList.remove("hidden");
    $("doc-prose")?.setAttribute("aria-expanded", "true");
    renderDocProse();
    try {
      const got = await apiJson(`/documents/${doc.id}/claim-check`, { method: "POST", body: JSON.stringify({ text: full }), readOnly: true });
      docAiCheck.items = got.claims.map((c) => ({
        text: c.text, message: c.message, replacement: "", near: c.start, claim: { verdict: c.verdict, note: c.note },
      }));
      docAiCheck.state = "done";
      docAiCheck.message = got.source === "words" ? "No AI model ran, so sentences were matched to notes by their words." : "";
    } catch (error) {
      docAiCheck.state = "failed";
      docAiCheck.message = error.message || "The check did not finish.";
    }
    renderDocProse();
  },
};

//: The streamed items as findings against the text as it is now. An item whose
//: words are gone (applied, or edited away) is simply not drawn; one dismissed
//: is gone from `items` itself.
function docAiFindings(text) {
  if (!docAiCheck.items.length || docAiCheck.docId !== (currentDoc?.id ?? null)) return [];
  const out = [];
  for (const item of docAiCheck.items) {
    let start = text.indexOf(item.text, Math.max(0, item.near - 200));
    if (start === -1) start = text.indexOf(item.text);
    if (start === -1) continue;
    const finding = {
      rule: "ai",
      start,
      end: start + item.text.length,
      text: item.text,
      message: item.message,
      replacement: item.replacement || null,
      aiItem: item,
    };
    if (docProseIgnored.has(docProseKey(finding))) continue;
    out.push(finding);
  }
  return out;
}

function docAiDismiss(finding) {
  docAiCheck.items = docAiCheck.items.filter((item) => item !== finding.aiItem);
  renderDocProse();
}


//: **The check's own line in the panel**: what it is doing or did, and the
//: two ways on (again, or Discuss in chat). No model is a `.notice-warn` with
//: the way to connect one, rather than a toast that is gone before it is read.
function docAiCheckStatus() {
  if (docAiCheck.state === "idle" || docAiCheck.docId !== (currentDoc?.id ?? null)) return null;
  const wrap = document.createElement("div");
  wrap.className = "doc-prose-ai";
  wrap.setAttribute("role", "status");
  const n = docAiCheck.items.length;
  const found = nounCount(n, "finding");
  if (docAiCheck.state === "offline") {
    const notice = document.createElement("p");
    notice.className = "notice notice-warn doc-prose-ai-notice";
    const icon = document.createElement("i");
    icon.className = "ph ph-plug";
    icon.setAttribute("aria-hidden", "true");
    const words = document.createElement("span");
    words.textContent = "No AI model is connected, so Check with AI cannot read this yet.";
    notice.append(icon, words);
    const open = smallButton("ph:gear Open Settings, Models", "Connect or choose the model documents use", () => {
      if (typeof openSettingsModal === "function") openSettingsModal("models");
    });
    open.classList.add("doc-prose-ai-settings");
    wrap.append(notice, open);
  } else {
    const line = document.createElement("span");
    line.className = "doc-prose-ai-line";
    if (docAiCheck.mode === "claims") {
      const marked = docAiCheck.items.filter((item) => item.claim.verdict !== "supported").length;
      line.textContent = docAiCheck.state === "running"
        ? "Checking sentences against your notes…"
        : docAiCheck.state === "failed"
          ? docAiCheck.message || "The check did not finish."
          : `${nounCount(n, "sentence")} checked, ${marked} not backed by a note.${docAiCheck.message ? ` ${docAiCheck.message}` : ""}`;
      if (docAiCheck.state === "failed") line.classList.add("error");
    } else if (docAiCheck.state === "running") {
      line.textContent = n ? `Checking with AI, ${found} so far…` : "Checking with AI…";
    } else if (docAiCheck.state === "stopped") {
      line.textContent = `Stopped. ${n ? `${found} before it stopped.` : "Nothing found before it stopped."}`;
    } else if (docAiCheck.state === "failed") {
      line.textContent = docAiCheck.message || "The check did not finish.";
      line.classList.add("error");
    } else {
      line.textContent = n ? `Checked with AI: ${found}.` : "Checked with AI: nothing to flag.";
    }
    wrap.appendChild(line);
  }
  const chat = smallButton("ph:chat-circle Discuss in chat", "Open this document in a chat, to ask about it in your own words", () => docAiDiscussInChat());
  chat.classList.add("doc-prose-ai-chat");
  wrap.appendChild(chat);
  return wrap;
}


//: **Managing the dictionary** (asked for by name): the sheet is documents-dictionary.js,
//: fetched on the first press; the word list's reads stay here (`docDictionary`).
async function openDocDictionary() {
  if (!(await lazyScript("/js/documents-dictionary.js"))) return toast("The dictionary could not be loaded.", true, { action: ["Try again", openDocDictionary] });
  return docDictionaryOpen();
}

//: Last line, deliberately: everything above has to exist before the first
//: paint. See `renderDocTools`.
renderDocTools();

// =============================================================================
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

function docRedo() {
  const CM = window.CM6;
  if (docCmView && CM) return CM.commands.redo(docCmView) && (toast("Redone: last change on this document", "info"), true);
  docSurface()?.focus();
  return document.execCommand("redo");
}

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

const DOC_CM_BUNDLE = "/vendor/codemirror/codemirror.min.js";

//: **Warm on idle** (perf-1026): the Documents list is the signal that a
//: document is about to open, so the editor bundle (about 140 ms to evaluate)
//: is loaded in a spare moment and the checker's files are fetched into the
//: HTTP cache, rather than both on the first open. Phones too (L-documents-47:
//: the cold open there is the one a person waits on), but never on a metered
//: connection or a device with 2 GB or less, where the bytes cost more than the wait.
let docWarmed = false;
function warmDocumentEngine() {
  const link = navigator.connection || {};
  if (docWarmed || link.saveData || (navigator.deviceMemory || 8) <= 2) return;
  docWarmed = true;
  const idle = window.requestIdleCallback || ((fn) => setTimeout(fn, 400));
  idle(() => {
    loadCodeMirror();
    for (const href of DOC_GRAMMAR_FILES.slice(1)) {
      const el = Object.assign(document.createElement("link"), { rel: "prefetch", href });
      document.head.appendChild(el);
    }
  }, { timeout: 2000 });
}

//: The in-flight load, so two documents opened quickly do not inject two
//: script tags. Reset to null on failure, so a later attempt can retry after
//: whatever went wrong (a dropped connection on first paint, most likely).
let docCmLoad = null;

//: True once loading or mounting has failed. Checked before every attempt, so
//: a broken bundle costs one request rather than one per document opened.
let docCmBroken = false;

function loadCodeMirror() {
  if (window.CM6) return Promise.resolve(window.CM6);
  if (docCmBroken) return Promise.resolve(null);
  if (docCmLoad) return docCmLoad;
  docCmLoad = new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = DOC_CM_BUNDLE;
    script.async = true;
    script.addEventListener("load", () => {
      if (window.CM6) resolve(window.CM6);
      //: Loaded but exporting nothing is a broken build, not a missing file,
      //: and the two want different messages in the console.
      else reject(new Error("the editor bundle loaded but defined no CM6"));
    });
    script.addEventListener("error", () =>
      reject(new Error("the editor bundle could not be loaded"))
    );
    document.head.appendChild(script);
  }).catch((error) => {
    docCmLoad = null;
    docCmBroken = true;
    //: Said out loud once. Silence here would be the "policy silently
    //: refusing the work" shape: the editor would quietly stay a textarea and
    //: nobody would know why the new features were missing.
    console.warn(`Tessellate: ${error.message}. The plain editor is still available.`);
    return null;
  });
  return docCmLoad;
}

//: The parts of the configuration that are swapped without rebuilding the
//: state: the language (a file's type can change while it is open), the theme
//: (light and dark), the gutter (a remembered preference), and line wrapping
//: (prose wraps, code does not).
const docCmParts = {
  language: null,
  theme: null,
  gutter: null,
  wrap: null,
  //: Live is this compartment holding the markdown decorations; Source is the
  //: same compartment holding nothing (decision 3).
  live: null,
  //: Whether the *browser's* checker draws squiggles, which is a question with
  //: two answers over the life of one editor: see `docCmSpellcheck`.
  spell: null,
  //: A code file's diagnostics and completions (`docCodeTools`); empty for
  //: prose and in Plain.
  code: null,
  //: The empty page's words, which follow the file type (`docPlaceholderFor`).
  placeholder: null,
  //: **PHP is its own file, fetched on the first .php open** (L-documents-63): the grammar is 28 KB gzipped and
  //: only this one file type wants it, so `php.min.js` extends the bundle's `CM6` the way `vim.min.js` does
  //: (called from `docCmViewLanguage`). Until it lands the file is plain text; then the memo is cleared and the
  //: language compartment reconfigured. A failed fetch leaves it plain, with a toast whose "Try again" asks
  //: once more (`lazyScript` forgets a failed load).
  phpLoading: false,
  async loadPhp() {
    if (this.phpLoading) return;
    this.phpLoading = true;
    const ok = await lazyScript("/vendor/codemirror/php.min.js");
    this.phpLoading = false;
    if (!ok || !window.CM6?.php) return toast("The PHP highlighter could not be loaded.", true, { action: ["Try again", () => this.loadPhp()] });
    docCmApplied.delete("language");
    docCmSyncLanguage();
  },
};

//: How the prose findings tell the view to repaint. A `StateEffect` rather
//: than a bare `dispatch({})`, so the plugin can rebuild for exactly this and
//: ignore every other transaction that does not move the document or the
//: viewport. Created with the first view, because it needs `CM.state`.
let docFindingsEffect = null;

//: The vendored modes, by the extension `GET /documents/file-types` uses.
//: Anything not here is plain text, which is the honest answer: several of
//: the file types this editor opens (csv) have no mode, and a wrong
//: highlighter is worse than none.
function docCmLanguageFor(CM, ext) {
  const stream = (mode) => (mode ? CM.language.StreamLanguage.define(mode) : []);
  switch (ext) {
    //: **`base: markdownLanguage`, and it is not a detail.** `markdown()` on
    //: its own parses *commonmark*, which has no strikethrough and no task
    //: lists, so `~~struck~~` and `- [ ] a task` produce no syntax nodes at
    //: all and the Live decorations that read them silently draw nothing.
    //: Caught by measuring (`scratchpad/ui-sweeps/cm-live.js`), not by
    //: reading: everything else on the page rendered, so the two missing
    //: features looked like a bug in this file rather than a parser that had
    //: never been told about them. `markdownLanguage` is the GitHub dialect,
    //: which is the one this app's own renderer and its toolbar both speak.
    case "md": return CM.markdown.markdown({ base: CM.markdown.markdownLanguage, codeLanguages: (info) => docPairInput.fenceLanguage(CM, info) });
    //: `jsx: true` because a React file is a `.js` file as often as not,
    //: and without it every `<div>` in one was an error node, underlined as
    //: a syntax error in code that runs. TypeScript stays without it: TSX
    //: reads `<T>(x) => x` as a tag, which would break valid `.ts`.
    case "js": return CM.javascript.javascript({ jsx: true });
    case "ts": return CM.javascript.javascript({ typescript: true });
    case "py": return CM.python.python();
    case "css": return CM.css.css();
    case "html": return CM.html.html();
    case "json": return CM.json.json();
    case "yaml": return CM.yaml.yaml();
    case "bash": return stream(CM.shell);
    //: `standardSQL`, the mode: `sql` is the factory that makes one, and
    //: mounting it threw "i is not a function" from the parser, so opening a
    //: .sql document failed outright (found by tests/test_code_vscode.py).
    case "sql": return stream(CM.standardSQL);
    case "toml": return stream(CM.toml);
    case "go": return stream(CM.go);
    case "rs": return stream(CM.rust);
    case "c": return stream(CM.c);
    case "cpp": return stream(CM.cpp);
    case "cs": return stream(CM.csharp);
    case "java": return stream(CM.java);
    case "kt": return stream(CM.kotlin);
    case "rb": return stream(CM.ruby);
    case "xml": return stream(CM.xml);
    case "svg": return stream(CM.xml);
    //: Added with the modes themselves (2026-09-09). `ini` is CodeMirror's
    //: `properties` mode, which is what that format is called there.
    case "swift": return stream(CM.swift);
    case "r": return stream(CM.r);
    case "ini": return stream(CM.properties);
    //: Bundled with the editor already (entry.js), so 0 bytes more.
    case "diff": return stream(CM.diff);
    case "dockerfile": return stream(CM.dockerFile);
    case "vb": return stream(CM.vb);
    case "vbs": return stream(CM.vbScript);
    //: `php` is a separate lazy file (php.min.js, `docCmParts.loadPhp`), so until it is
    //: loaded this is plain text. **`csv` stays plain on purpose**: a CSV has no syntax to colour, a highlighter
    //: would draw attention to its commas and nothing else, and what it wants is a table view (DOCUMENTS_PLAN).
    case "php": return CM.php ? CM.php.php() : [];
    default: return [];
  }
}

//: **The editor's ink, from the app's own tokens.**
//:
//: A theme object rather than a stylesheet, and the reason is mechanical:
//: CodeMirror styles itself through `document.adoptedStyleSheets`, and
//: adopted sheets sort *after* every document stylesheet, so a rule in
//: 09-editor.css would lose to the library's own base rule at equal
//: specificity and nothing would say so. Layout lives in the file; colour,
//: type and the caret live here.
//:
//: `var(--…)` all the way through, so the density slider, a custom accent and
//: a theme change move the editor with the rest of the app rather than
//: leaving it as the one panel that did not follow.
//: The Live table's placement rules, one pair per column count.
//:
//: A CodeMirror line is the grid, and its children are whatever the
//: decorations left there: the cell marks, and behind every hidden pipe two
//: `cm-widgetBuffer` images and an empty `contenteditable=false` span. Those
//: three are zero-width and were still taking a `1fr` track each under
//: `grid-auto-flow: column`, which is why a table drew its cells 51.6px wide
//: with three empty columns of gap between them and wrapped every word.
//: Placing the cells by index and pinning everything else into the first
//: track at zero width is the only arrangement that stays right whatever the
//: decorations do: a mark the table does not know about (a spelling
//: underline, a search match) can be added tomorrow without taking a column.
function docTableGridRules() {
  const rules = {};
  for (let n = 1; n <= DOC_TABLE_GRID_MAX; n += 1) {
    rules[`.cm-md-cols-${n}`] = {
      //: **A column has a floor** (audit 1102 DX2): a zero minimum let 14
      //: columns share 594px as 42px tracks and stack "Column 0" one letter a
      //: line. The floor is `--doc-table-col-min` (6em, a word and its inset;
      //: 5em broke "Column" mid-word when measured) and the line is as wide as
      //: its columns need, so a wide table scrolls the editor sideways as the
      //: Read view does, every row the same width. The floor is a fixed
      //: minimum, not `auto`, so a long unbroken word still wraps inside its
      //: track instead of widening the table.
      gridTemplateColumns: `repeat(${n}, minmax(var(--doc-table-col-min), 1fr))`,
      minWidth: `calc(${n} * var(--doc-table-col-min))`,
      //: **An implicit row gets no height** (the owner, twice: "when I click
      //: on a header row in a table on the live view, another row appears
      //: below it until I click off"). Measured with the caret in the header
      //: at 1440: `grid-template-rows` reads "28.19px 25.59px" and the line
      //: grows from 29.2px to 54.8px. The second row holds one child, the
      //: trailing `<br>` CodeMirror appends to every line, which sits at
      //: top+32.2 while every other child sits at top+1.
      //:
      //: The rule below already assigns it `grid-area: 1 / 1` and its computed
      //: `grid-row-start` reads 1, so pinning it harder is not the answer, and
      //: pinning the menu instead was measured and changed nothing. What is
      //: certain is that the row is implicit, and an implicit row here is
      //: always wrong: every cell of a table row is placed explicitly by
      //: `.cm-md-c*`, so anything auto-placed is furniture, not content, and
      //: furniture must not add height to the line.
      //: One explicit row, then implicit ones with no height. Both halves are
      //: needed and `grid-auto-rows` alone was measured collapsing the line to
      //: 1px: with no `grid-template-rows` every row here is implicit,
      //: including the one the cells are in, so zeroing implicit rows zeroed
      //: the table.
      gridTemplateRows: "auto",
      gridAutoRows: "0",
    };
    //: The menu is excluded because it is absolutely positioned against the
    //: header line and is not in the grid's flow at all; giving it `width: 0`
    //: would take its buttons away.
    rules[`.cm-md-cols-${n} > *:not(.cm-md-td):not(.cm-md-table-menu)`] = {
      gridArea: "1 / 1",
      justifySelf: "start",
      width: "0",
      overflow: "hidden",
    };
    rules[`.cm-md-c${n}`] = { gridColumn: String(n), gridRow: "1" };
  }
  return rules;
}

//: **Indent guides under a nested list** (INBOX 392). A nested item was
//: told apart from its parent by its indent alone, and three levels deep a
//: reader was counting em widths to know which item a line belonged to. One
//: hairline per ancestor, down the column of that ancestor's own marker, is
//: what every outliner draws; it is a background rather than a border or a
//: widget because a line decoration can carry it without adding a node, and
//: it cannot move the text. The marker of level `k` sits at `k * 1.6em` (the
//: hanging indent in the theme), so the guide for level `j` is at that plus
//: 0.3em, under the bullet's middle.
function docListGuides(depth) {
  const tone = "color-mix(in srgb, var(--muted) 35%, transparent)";
  const ink = `linear-gradient(${tone}, ${tone})`;
  const layers = [];
  const places = [];
  for (let j = 0; j < depth; j += 1) {
    layers.push(ink);
    places.push(`${(j * 1.6 + 0.3).toFixed(2)}em 0`);
  }
  return {
    backgroundImage: layers.join(", "),
    backgroundPosition: places.join(", "),
    backgroundSize: "1px 100%",
    backgroundRepeat: "no-repeat",
  };
}

//: How many matches the find panel's query has, said in the panel (audit
//: 1028 U9): the library's panel finds without ever saying how many. Counted
//: only while the panel is open and only when the text or the query changed,
//: and stopped at 1,000 so a one-letter query in a long file stays cheap.
const DOC_SEARCH_COUNT_CAP = 1000;
function docSearchCountText(state, CM) {
  const query = CM.search.getSearchQuery(state);
  if (!query.search || !query.valid) return "";
  let n = 0;
  for (const cursor = query.getCursor(state); n < DOC_SEARCH_COUNT_CAP && !cursor.next().done;) n += 1;
  if (!n) return "No matches";
  return n >= DOC_SEARCH_COUNT_CAP ? "1,000+ matches" : `${n} match${n === 1 ? "" : "es"}`;
}

function docCmSearchCount(CM) {
  return CM.view.ViewPlugin.fromClass(class {
    constructor(view) { this.query = null; this.update({ view, docChanged: true, state: view.state }); }
    update(update) {
      const { view } = update;
      if (!CM.search.searchPanelOpen(view.state)) return void (this.query = null);
      const query = CM.search.getSearchQuery(view.state);
      if (!update.docChanged && this.query?.eq(query)) return;
      const panel = view.dom.querySelector(".cm-search");
      if (!panel) return;
      this.query = query;
      let out = panel.querySelector(".cm-search-count");
      if (!out) {
        out = Object.assign(document.createElement("span"), { className: "cm-search-count muted text-sm" });
        out.setAttribute("role", "status");
        //: **One find panel for this document and for all of them** (audit 1028 D33): the same words and options carry to the
        //: every-document find and replace, which used to start empty from a different place.
        const all = Object.assign(document.createElement("span"), { className: "cm-search-all" });
        const asked = () => CM.search.getSearchQuery(view.state);
        const find = Object.assign(document.createElement("button"), { type: "button", className: "cm-button", name: "all-documents", textContent: "All documents", title: "Find this in every document (Ctrl+Shift+F)" });
        find.addEventListener("click", () => docFindInDocuments(asked().search));
        const swap = Object.assign(document.createElement("button"), { type: "button", className: "cm-button", name: "replace-in-all", textContent: "Replace in all", title: "Replace this in every document" });
        swap.addEventListener("click", () => {
          const q = asked();
          openDocReplace({ find: q.search, replace: q.replace, caseSensitive: q.caseSensitive, regexp: q.regexp, wholeWord: q.wholeWord });
        });
        all.append(find, swap);
        const lineBreak = panel.querySelector("br");
        if (lineBreak) lineBreak.before(out, all);
        else panel.append(out, all);
      }
      out.textContent = docSearchCountText(view.state, CM);
    }
  });
}


//: **Code colours from the app's own palette, and the reason this is not
//: optional.** The owner: "for code files, include code syntax and make it a
//: proper code editor like vs code."
//:
//: Without this the bundle falls back to CodeMirror's `defaultHighlightStyle`,
//: which is a fixed light-page palette: a keyword is `#770088`, a variable
//: name is `#0000ff`, a string `#aa1111`. Measured against this app's dark
//: ground, sampled off a screenshot at `rgb(27, 31, 44)`: the keyword reads
//: **1.76:1** and the variable name **1.91:1**, against WCAG AA's 4.5. Every
//: token was byte-identical in light and dark, because that style has no dark
//: variant to switch to. Nothing logged it, and a reader with the theme on
//: light would never see it, which is the shape this file keeps recording.
//:
//: Built here rather than in a stylesheet for the same reason the theme
//: itself is: adopted sheets sort after every document stylesheet, so a rule
//: in 09-editor.css would lose to the library's at equal specificity. The
//: roles are mapped onto tokens the app already defines for both themes, so
//: the density slider, a custom accent and a theme change move the code with
//: the rest of the app.
//: Built once, and **deliberately not inside the theme compartment.** Every
//: colour below is a `var(--…)`, so light and dark are already handled by the
//: cascade; rebuilding it on each mode change would define a fresh
//: `StyleModule` and adopt another stylesheet every time the theme was
//: toggled, which is a leak that only shows up after a few switches.
let docCmHighlightCache = null;

function docCmHighlight(CM) {
  if (docCmHighlightCache) return docCmHighlightCache;
  const { HighlightStyle } = CM.language;
  const t = CM.highlight.tags;
  //: One colour per role, and the roles are the six a reader actually
  //: separates at a glance: what the language says (keyword), what the writer
  //: named (variable, and the function or type it is), literal data, prose the
  //: compiler ignores (comment), and punctuation. More than that and a file
  //: reads as confetti, which is the failure mode of a highlighter that maps
  //: every lezer tag it can find.
  const keyword = { color: "var(--accent-text)", fontWeight: "600" };
  const name = { color: "var(--ink)" };
  const literal = { color: "var(--ok)" };
  const string = { color: "var(--warn)" };
  const comment = { color: "var(--muted)", fontStyle: "italic" };
  const punctuation = { color: "var(--muted)" };
  docCmHighlightCache = CM.language.syntaxHighlighting(
    HighlightStyle.define([
      { tag: [t.keyword, t.modifier, t.controlKeyword, t.operatorKeyword, t.self, t.null], ...keyword },
      { tag: [t.atom, t.bool, t.number, t.integer, t.float], ...literal },
      { tag: [t.string, t.special(t.string), t.regexp, t.character], ...string },
      { tag: [t.comment, t.lineComment, t.blockComment, t.docComment], ...comment },
      //: A definition is bolder than a use: in a file you are reading rather
      //: than writing, "where is this declared" is the question the eye is
      //: actually asking.
      { tag: [t.definition(t.variableName), t.definition(t.propertyName)], color: "var(--ink)", fontWeight: "600" },
      { tag: [t.function(t.variableName), t.function(t.propertyName), t.macroName], color: "var(--accent-text)" },
      { tag: [t.typeName, t.className, t.namespace, t.standard(t.typeName)], color: "var(--accent-text)", fontWeight: "600" },
      { tag: [t.variableName, t.propertyName, t.attributeName], ...name },
      { tag: [t.punctuation, t.separator, t.bracket, t.operator], ...punctuation },
      { tag: [t.meta, t.processingInstruction], color: "var(--muted)" },
      { tag: t.invalid, color: "var(--error)" },
      //: A patch's added and removed lines (the diff mode's only tokens
      //: besides `@@`): without these a `.diff` drew in one colour.
      { tag: t.inserted, color: "var(--ok)" },
      { tag: t.deleted, color: "var(--error)" },
      { tag: t.link, color: "var(--accent-text)", textDecoration: "underline" },
      //: Markdown's own tags, so Source view on a `.md` file is not the one
      //: file type in the editor with no highlighting at all. Live view draws
      //: these itself, from the tree, with its markers hidden; this is what
      //: Source and Plain fall back to.
      { tag: t.heading, fontWeight: "700", color: "var(--ink)" },
      { tag: t.emphasis, fontStyle: "italic" },
      { tag: t.strong, fontWeight: "700" },
      { tag: t.strikethrough, textDecoration: "line-through" },
      { tag: [t.monospace], color: "var(--accent-text)" },
    ])
  );
  return docCmHighlightCache;
}

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
const docHistories = new Map();
let docHistoryOwner = null;

//: `repaint: false` when the caller repaints the findings itself a frame
//: later (`openDocument`, through `renderDocTools`): the findings plugin is
//: rebuilt by `setState` from the same list, and the extra dispatch was a
//: second layout of the page (138ms of a 573ms open at 390).
function docResetDocument(text, id = null, { repaint = true } = {}) {
  const CM = window.CM6;
  if (!docCmView || !CM) {
    const surface = docSurface();
    if (surface) surface.text = text;
    return;
  }
  const field = CM.commands.historyField;
  if (docHistoryOwner != null && field) {
    try {
      docHistories.set(docHistoryOwner, docCmView.state.toJSON({ history: field }));
    } catch { /* nothing to keep */ }
  }
  const kept = id != null ? docHistories.get(id) : null;
  //: Not kept this session: the stored one, once it is read (INBOX 553(b)).
  if (id != null && !kept) docHistoryRestore(id, text);
  let state = null;
  if (kept && kept.doc === text && field) {
    try {
      state = CM.state.EditorState.fromJSON(kept, { extensions: docCmExtensions(CM) }, { history: field });
    } catch { state = null; }
  }
  docHistoryOwner = id;
  docCmView.setState(state || CM.state.EditorState.create({ doc: text, extensions: docCmExtensions(CM) }));
  //: `docCmExtensions` builds *new* compartments, so everything held in one
  //: has to be said again. Missing this is the "a value that is invalid where
  //: it is used" shape: the view would come back in Source's configuration
  //: while the view control still said Live, and nothing would log a thing.
  docSetLiveDecorations(docView === "live");
  if (repaint) docCmRepaintFindings();
  //: The `[!kind]-` callouts, folded as their markers ask, on the one event
  //: that means "a different document is on screen now".
  docFoldMarkedCallouts();
}

//: **A document's history survives a reload** (INBOX 553(b), the owner's
//: decision; WHITEBOARD_PLAN decision 17 as amended). Written a moment after
//: each edit (`docHistoryPersist`, from `docCmUpdate`), read back when the
//: document opens and nothing was kept this session, and given back only
//: over the very text it was taken against and only if no edit has been made
//: since the open. CodeMirror's history holds its last hundred events
//: (its own `minDepth`), which is the owner's "~100 steps".
function docHistoryRestore(id, text) {
  if (typeof undoStoreGet !== "function") return;
  undoStoreGet(`doc:${id}`).then((stored) => {
    const CM = window.CM6;
    const field = CM?.commands?.historyField;
    if (!stored || !field || !docCmView || docHistoryOwner !== id || stored.doc !== text) return;
    if (docStr(docCmView.state.doc) !== text) return;
    try {
      docCmView.setState(CM.state.EditorState.fromJSON(stored, { extensions: docCmExtensions(CM) }, { history: field }));
      docSetLiveDecorations(docView === "live");
      docCmRepaintFindings();
    } catch {
      /* a history this version cannot read is no history */
    }
  });
}

function docHistoryPersist() {
  const CM = window.CM6;
  const field = CM?.commands?.historyField;
  if (typeof undoStorePut !== "function" || !field || !docCmView || docHistoryOwner == null) return;
  try {
    //: Serialised at the store's pause, not per keystroke (audit 1028 D6).
    const state = docCmView.state;
    undoStorePut(`doc:${docHistoryOwner}`, () => state.toJSON({ history: field }));
  } catch {
    /* nothing to keep */
  }
}

//: **Source view has to be measured after it is shown.** CodeMirror caches
//: the geometry it lays out with, and a view inside a `display: none` wrapper
//: measures as zero: switching back from Live or Read would leave every line
//: positioned against that zero until something else forced a reflow.
function docCmViewShown() {
  if (!docCmView) return;
  docCmView.requestMeasure();
}

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
function docWatchLock() {
  const overlay = document.getElementById("lock-overlay");
  if (!overlay || typeof MutationObserver !== "function") return;
  //: A password prompt borrows the overlay (`askPasswordPrompt`, app.js) and
  //: is not a lock, so it leaves the open document alone. `data-mode` is
  //: watched too, so a prompt that turns into a real lock still purges.
  //: Kept (audit 1028 D37), and let go before a second one is made.
  docWatchLock.observer?.disconnect();
  docWatchLock.observer = new MutationObserver(() => {
    if (overlay.classList.contains("hidden")) return;
    if (overlay.dataset.mode === "prompt") return;
    if (!docCmView) return;
    //: `setState`, not a change transaction: the history is part of the
    //: state, and an undo that could bring the document back after a lock
    //: would make this purge decorative. The kept histories go with it.
    docHistoryOwner = null;
    docHistories.clear();
    //: The stored ones too (undo-store.js): a document's history holds its
    //: text, and so does a board step's payload.
    if (typeof undoStoreClear === "function") undoStoreClear();
    docResetDocument("");
  });
  docWatchLock.observer.observe(overlay, { attributes: true, attributeFilter: ["class", "data-mode"] });
}
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

