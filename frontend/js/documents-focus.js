// documents-focus.js: block references, the reading modes, focus mode and the markdown toolbars' own commands.
// Moved out of documents.js whole (L-documents-117) and wrapped: only what other files call goes on `window`.
(() => {
  //: State that moved here from documents.js (L-documents-118).
  let docFocusOwnsFullscreen = false;
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

  //: What an id may be. Deliberately narrower than Obsidian's (which allows any
  //: non-space run): an id is generated here, so the only reason to accept more
  //: is to read somebody else's file, and a `^` followed by punctuation is far
  //: more likely to be a caret in prose ("2^31", "x ^ y") than a block id.
  //: The trailing `^id` on a line, with the space before it, so removing the id
  //: does not leave a space behind.


  // --- block references in the running editor ----------------------------------


  //: Copy a link to the block at the caret, and put the caret on a block a link led to: documents-blockref.js,
  //: fetched on first use. Each name is a stand-in that the piece's function of the same name replaces on load.
  //: `mode`: "link" copies `[[Title#^id]]`; "copy" copies the embed `![[Title#^id]]` (a synced block); "paste" inserts the last one copied.


  //: **True only while a print is being prepared** (`exportDocumentPdf`), which
  //: is the one moment the rendered pane carries the remarks rather than hiding
  //: them: a PDF handed to somebody should carry them as footnotes, and Read view
  //: should not, and both are drawn by `renderDocPreview` from one place. A flag
  //: rather than an argument because the render is also reached from the debounce
  //: and from `setDocView`, neither of which knows anything about printing.






  // --- AI editing ---
  //: The running edit's abort; documents-ai.js assigns it, so it stays a shared `let` here. The panel's doors are documents-ai-edit.js.


  function initMarkdownToolbars() {
    for (const bar of document.querySelectorAll("[data-md-target]:not(#tab-notes *), #doc-toolbar")) {
      wireMarkdownToolbar(bar);
    }
    onSurface("notes", () => {
      for (const bar of document.querySelectorAll("#tab-notes [data-md-target]")) wireMarkdownToolbar(bar);
      wireMdFormatShortcuts("entry-content");
    });
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







  //: Leaving with unsaved edits would lose them; autosave hasn't fired yet.
  //: The `beforeunload` guard for this is centralised in navigation.js
  //: (`hasUnsavedWork`/its listener) now, alongside the note edit form and the
  //: Capture box, rather than kept here as a second `docDirty`-only listener:
  //: one browser event, one place that reads every surface's own flag.



  function mountDocToolbarControls() {
    $("doc-format-toggle")?.addEventListener("click", () =>
      setDocToolbarCollapsed(!docToolbarCollapsed())
    );
    $("doc-format-show")?.addEventListener("click", () => toggleDocToolbar());
    // The capture box gets its gutter here, once, with the strip that toggles it.
    //: The Notes strips are wired when that page is built, not before: a bare `$` here built it (1,092 elements) in a Documents open.
    onSurface("notes", () => {
      mountGutterFor($("entry-content"));
      for (const bar of document.querySelectorAll("#tab-notes .doc-toolbar")) {
        mountDocToolbarControlsFor(bar);
        applyDocToolbarLayoutButtons(bar);
        applyDocToolbarCollapsed(docToolbarCollapsed(), bar);
      }
    });
    for (const bar of document.querySelectorAll(".doc-toolbar:not(#tab-notes *)")) mountDocToolbarControlsFor(bar);
    applyDocToolbarLayoutButtons();
    applyDocToolbarCollapsed(docToolbarCollapsed());
  }



  //: The file's surface: what other files call (L-documents-117).
  Object.assign(window, { docReadingModes, docReadingPlugin, docTypewriterExtension, docFocusOn, DOC_FOCUS_NARROW, setDocFocusSidebar, toggleDocFocus });

  //: These lets keep their bare names for the other files as window accessors, so one store answers every reader and writer (L-documents-118).
  for (const [name, get, set] of [
    ["docFocusOwnsFullscreen", () => docFocusOwnsFullscreen, (value) => { docFocusOwnsFullscreen = value; }],
  ]) Object.defineProperty(window, name, { get, set, configurable: true });

  initMarkdownToolbars();

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

  mountDocToolbarControls();
  //: Ctrl+Shift+X anywhere on the Documents tab, not only inside the text
  //: (the editor's own keymap has it too): with the strip hidden, the focus
  //: is as likely to be on the dock as in the page. Module level, beside the
  //: mount, so no render adds a page listener (tests/test_perf_1031.py).
  document.addEventListener("keydown", (event) => {
    if (!(event.ctrlKey || event.metaKey) || !event.shiftKey || event.altKey || event.key.toLowerCase() !== "x") return;
    if (event.defaultPrevented || $("tab-documents")?.classList.contains("hidden") || !currentDoc) return;
    event.preventDefault();
    toggleDocToolbar();
  });
})();
