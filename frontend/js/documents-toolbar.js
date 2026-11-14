// documents-toolbar.js: the format strip's shape (wrap or one row, collapsed or shown), the line-number toggle and the row fit.
// Moved out of documents.js and wrapped (L-documents-116): only what other files call goes on `window`. Two listeners bind at load;
// everything else only declares. `mountDocToolbarControls` stays in documents.js and runs at its load.
(() => {
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

  //: The file's surface: what other files call.
  Object.assign(window, { docToolbarMode, applyDocToolbarMode, docGutterPref, docGutterWanted, applyDocGutter, docToolbarCollapsed, applyDocToolbarCollapsed, setDocToolbarCollapsed, docSyncFormatShow, toggleDocToolbar, mountDocToolbarControlsFor, applyDocToolbarLayoutButtons });
})();
