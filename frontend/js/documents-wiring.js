// documents-wiring.js: the editor's wiring: back link, change pipeline, the formatting toolbar and the note surfaces.
// Moved out of documents.js whole (L-documents-117) and wrapped: only what other files call goes on `window`.
(() => {
  // --- documents wiring ---
  //: The code panel's ways in (INBOX 788), each fetching documents-codekit.js
  //: on its first press. `keep` reopens a tab without toggling it shut.
  async function docCodeSideFrom(tab, keep = false) {
    if (!(await lazyScript("/js/documents-codekit.js"))) return toast("The code panel could not be loaded.", true, { action: ["Try again", () => docCodeSideFrom(tab, keep)] });
    if (keep) docCodeSideOpen(tab, { auto: true });
    else docCodeSideToggle(tab);
  }
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
    //: A strip without its own Insert (the notes' two) gets the same button, ahead of the pairs: the row
    //: folds from its end (`fitDocToolbarRow`), so Insert, a thing reached for, outlasts Undo and Indent
    //: (Capture at 1280: Insert was the first thing behind More, with 55px of the row empty).
    if (!bar.querySelector('[data-md="insert"]')) {
      const insert = document.createElement("button");
      insert.type = "button";
      insert.dataset.md = "insert";
      insert.dataset.mdExtra = "1";
      insert.title = "Insert a block, image, link, table, diagram, emoji or equation (or press /)";
      setLabel(insert, "ph:plus Insert");
      bar.appendChild(insert);
    }
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

  let noteSurfaceMirroring = false;

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
    //: Note find and replace (L-world-class-127); a capture box keeps the page find.
    const finds = host.id === "entry-edit-content" || host.id === "graph-popup-content";
    const findKeys = finds
      ? [
          {
            key: "Mod-h",
            run: (view) => {
              CM.search.openSearchPanel(view);
              view.dom.querySelector(".cm-search input[name=replace]")?.focus();
              return true;
            },
          },
          ...CM.search.searchKeymap,
        ]
      : [];
    return [
      ...(finds ? [CM.search.search({ top: true })] : []),
      host.noteReadOnlySlot.of(host.noteReadOnlyExtensions(host.readOnly)),
      //: The same whole-line copy and cut the document has (INBOX 652).
      CM.state.Prec.high(docLineClipboardExtension(CM)),
      //: Pasted HTML becomes Markdown here as in a document (L-world-class-50): the same
      //: `docRichPasteEvent`, and Ctrl+Shift+V the same plain paste.
      CM.state.Prec.high(CM.view.EditorView.domEventHandlers({
        keydown: (event) => {
          docPastePlain = (event.ctrlKey || event.metaKey) && event.shiftKey && event.key.toLowerCase() === "v";
          return false;
        },
        paste: (event, view) => docRichPasteEvent(event, view),
      })),
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
      //: The native caret unless several ranges or an unfocused selection (L342).
      ...docCmParts.drawSelectionWhenNeeded(CM, new CM.state.Compartment()),
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
        ...findKeys,
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
  //: same four actions with this box named. Ctrl+S is deliberately absent:
  //: saving a note is the form's business, which the app's own global chord
  //: already handles.
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
    //: Views whose editor left the page are destroyed first (see `noteSurfaceViews.live`).
    for (const gone of noteSurfaceViews.live) {
      if (gone.dom.isConnected) continue;
      noteSurfaceViews.live.delete(gone);
      try {
        gone.destroy();
      } catch (error) {
        //: A view that cannot be torn down is no worse off than before.
      }
    }
    const view = new CM.view.EditorView({ state, parent: wrap });
    noteSurfaceViews.live.add(view);
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

  //: The file's surface: what other files call (L-documents-117).
  Object.assign(window, { docCodeSideFrom, docSurfaceInput, MD_RUN, MD_RUN_FONTS, mdRunParse, mdRunFormat, mdRunNode, wireMarkdownToolbar, wireMdFormatShortcuts, NOTE_SURFACES, setNoteSurfaceSource, mountNoteSurface });

  $("doc-code-snippets-open")?.addEventListener("click", () => docCodeSideFrom("snippets"));

  $("doc-code-assist-open")?.addEventListener("click", () => docCodeSideFrom("assist"));

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

  wireDocScrollSync();

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
})();
