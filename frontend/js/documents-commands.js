// documents-commands.js: the command list, the outline, and moving a section or block.
// Moved out of documents.js whole (L335) and wrapped: only what other files call goes on `window`; nothing here runs at load.
(() => {
  // DOC-COMMANDS-BEGIN
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
  function docOutlineDropAfter(row, clientY) {
    const box = row.getBoundingClientRect();
    return clientY > box.top + box.height / 2;
  }
  function docOutlineClearDrop() {
    for (const row of document.querySelectorAll("#doc-outline .is-drop-before, #doc-outline .is-drop-after")) {
      row.classList.remove("is-drop-before", "is-drop-after");
    }
  }
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
  let docOutlineKey = "";
  let docOutlineFocusKey = "";
  let docOutlineDragIndex = -1;
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

  //: The file's surface: what other files call (L335).
  Object.assign(window, { DOC_COMMANDS, docPaletteCommands, renderDocShortcutSheet, docBlockMoveEdit, docBlockMoveRun, renderDocOutline, docVisibleTopLine });
})();
