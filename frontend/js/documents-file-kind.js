// documents-file-kind.js: what kind of file a document is (code, markdown, diagram), the file-type menu and its load-time wiring.
// Moved out of documents.js whole (L-documents-117) and wrapped: only what other files call goes on `window`.
(() => {
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
      docTypeState.choose = docTypeChoose; //: what a row does, for a sweep that skips the menu (`docopen.js`).
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
  //: The card's `.card:has(details.dock-menu[open])`, as a class (07-whiteboard-misc.css says why).
  //: Both of the dock's menus (View, More): one opening as the other closes leaves the class on.
  for (const dockMenu of [document.getElementById("doc-view-menu"), document.getElementById("doc-dock-menu")]) {
    dockMenu?.addEventListener("toggle", () => {
      const card = dockMenu.closest(".card");
      card?.classList.toggle("doc-view-menu-open", Boolean(card.querySelector("details.dock-menu[open]")));
    });
  }
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

  //: The file's surface: what other files call (L-documents-117).
  Object.assign(window, { docTypeState, loadDocFileTypes, docFileType, docBlankPlaceholder, syncDocFileType });
})();
