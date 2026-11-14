// documents-cm-theme.js: `docCmTheme`, every CodeMirror rule that dresses the
// editor from the app's own tokens (split out of documents-cm.js, audit 160 D23).
//
// The gutter, the finding underlines, the linter and completion lists, the
// search panel. **Loaded in the Library bundle, before documents.js**: the top
// level is one function declaration and reads nothing; documents.js calls it
// from `docCmExtensions` and on a theme change, after the bundle.

(() => {
  function docCmTheme(CM) {
    const dark = document.documentElement.dataset.mode === "dark";
    return CM.view.EditorView.theme(
      {
        "&": {
          color: "var(--text)",
          backgroundColor: "transparent",
          height: "100%",
        },
        "&.cm-focused": { outline: "none" },
        ".cm-scroller": {
          fontFamily: "var(--ui-font, system-ui, -apple-system, 'Segoe UI', sans-serif)",
          lineHeight: "1.6",
          overflow: "auto",
        },
        //: The tail padding is not decoration: without it the last line of a
        //: document sits against the bottom of the pane and you write the end
        //: of a chapter at the very edge of the screen. Every editor this app
        //: is compared to scrolls past the end, for that reason.
        ".cm-content": {
          caretColor: "var(--text)",
          padding: "var(--space-4) var(--space-4) 40vh",
        },
        ".cm-line": { padding: "0" },
        ".cm-cursor, .cm-dropCursor": { borderLeftColor: "var(--text)" },
        "&.cm-focused .cm-selectionBackground, .cm-selectionBackground, .cm-content ::selection": {
          backgroundColor: "var(--accent-soft)",
        },
        ".cm-gutters": {
          backgroundColor: "transparent",
          color: "var(--muted)",
          border: "none",
        },
        //: The fold lane is a line tall and centred in itself, so an arrow lines
        //: up with the number beside it and with the text it folds. Without the
        //: explicit `lineHeight` the marker inherits the gutter's own, which is
        //: not the editor's line height, and every arrow sits a little high.
        ".cm-foldGutter": { width: "1.1em" },
        ".cm-foldGutter .cm-gutterElement": {
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: "0",
          lineHeight: "inherit",
          cursor: "pointer",
        },
        ".cm-fold-caret": {
          fontSize: "0.85em",
          lineHeight: "1",
          color: "var(--muted)",
        },
        ".cm-gutterElement:hover .cm-fold-caret": { color: "var(--text)" },
        //: **The numbers** (INBOX 590, the owner: "cleaner and more modern and
        //: professional"): a size under the text's, figures of one width so 9
        //: and 10 end on the same edge, right-aligned with room either side,
        //: and the line box the text's own (`1.6em` of the text is `1.6 /
        //: 0.8 = 2em` of the smaller figure). Centred in that box a figure's
        //: baseline sits about 2.4px above the text's (the size difference plus
        //: the 0.6px the gutter's rounded offset adds, `gutter.js`), so it is
        //: drawn 0.17em lower, onto the line it counts; `top` moves the glyph
        //: and not the element, so the rows below keep their places. The line
        //: the caret is on is in the body ink while the editor has the focus,
        //: and muted like the rest when it does not.
        ".cm-lineNumbers .cm-gutterElement": {
          fontSize: "0.8em",
          lineHeight: "2em",
          position: "relative",
          top: "0.17em",
          fontVariantNumeric: "tabular-nums",
          padding: "0 var(--space-4) 0 var(--space-3)",
          minWidth: "3ch",
        },
        ".cm-activeLineGutter": { backgroundColor: "transparent", color: "var(--muted)" },
        "&.cm-focused .cm-activeLineGutter": { color: "var(--text)" },
        //: **The caret's line is washed, only while the numbers show** (INBOX
        //: 651, the owner: "subtle line highlighting in the document editor
        //: when the line numbers are showing"). `highlightActiveLine()` is
        //: added with the gutter (`docCmGutter`, `noteSurfaceGutter`), so with
        //: numbers off no line carries the class at all. The wash is DESIGN.md's
        //: `--hover-veil`, a translucent ink laid over whatever ground the line
        //: has, so it reads in light and dark and never covers the selection
        //: layer's tint; it shows only while the editor has the focus, the same
        //: rule the number beside it follows. Half the veil since INBOX 684
        //: (the owner: "the active line highlighting is a little too strong"):
        //: 0.045 white in dark, 0.035 ink in light, a place marker rather than
        //: a band.
        ".cm-activeLine": { backgroundColor: "transparent" },
        "&.cm-focused .cm-activeLine": { backgroundColor: "color-mix(in srgb, var(--hover-veil) 50%, transparent)" },
        ".cm-selectionMatch": { backgroundColor: "var(--accent-soft)" },
        ".cm-searchMatch": { backgroundColor: "var(--accent-soft)" },
        ".cm-searchMatch.cm-searchMatch-selected": { outline: "1px solid var(--accent)" },
        ".cm-placeholder": { color: "var(--muted)" },
        ".cm-tooltip": {
          backgroundColor: "var(--card)",
          border: "1px solid var(--border)",
          color: "var(--text)",
        },

        //: --- a code file's diagnostics and completions (INBOX 392) ----------
        //: CodeMirror's own lint styles are fixed colours (#d11 for an error,
        //: a red SVG squiggle, a white-on-#17c selected completion), which is
        //: the same trap the highlighter fell into (`docCmHighlight`): right on
        //: a white page, wrong on this app's dark one, and deaf to a custom
        //: accent. Every one is restated here in the app's tokens.
        //:
        //: The underline is the prose findings' own shape, a wavy line in the
        //: kind's ink (`.cm-finding-spelling`), so an error in code and a
        //: misspelling in prose are one idea drawn once. The SVG CodeMirror
        //: paints as a background is switched off rather than recoloured: its
        //: colour is baked into a data URL.
        ".cm-lintRange": {
          backgroundImage: "none",
          paddingBottom: "0",
          textDecorationSkipInk: "none",
          textUnderlineOffset: "0.18em",
        },
        ".cm-lintRange-error": {
          textDecoration: "underline wavy",
          textDecorationColor: "var(--error)",
        },
        ".cm-lintRange-warning": {
          textDecoration: "underline wavy",
          textDecorationColor: "var(--warn)",
        },
        ".cm-lintRange-info, .cm-lintRange-hint": {
          textDecoration: "underline dotted",
          textDecorationThickness: "2px",
          textDecorationColor: "var(--muted)",
        },
        ".cm-lintRange-active": { backgroundColor: "var(--accent-soft)" },
        //: The gutter mark: a dot in the kind's ink, centred on its line. The
        //: library's marker is an SVG in its own colours set as `content`, so
        //: `content: normal` takes it away and the box draws the dot.
        ".cm-gutter-lint": { width: "1em" },
        ".cm-gutter-lint .cm-gutterElement": {
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: "0",
        },
        ".cm-lint-marker": {
          content: "normal",
          width: "0.55em",
          height: "0.55em",
          borderRadius: "var(--radius-pill)",
          backgroundColor: "var(--muted)",
        },
        ".cm-lint-marker-error": { backgroundColor: "var(--error)" },
        ".cm-lint-marker-warning": { backgroundColor: "var(--warn)" },
        //: **The diagnostic card** (the owner, 2026-10-10: "this popup is poorly
        //: designed and spaced"). Measured before: the message and its fix on one
        //: line, 6.4px of padding above and 9.6 beside, a 3px coloured edge as the
        //: only sign of severity and the card with no ground of its own. Now a
        //: severity glyph (a Phosphor character, in the kind's ink: an error is
        //: never the colour alone), the message as the card's one line of ink, and
        //: the fix on its own row under the message, indented to the message's
        //: edge, as a button of the app's size. A second fix sits beside the
        //: first. The card is the opaque tooltip ground below, with an inset
        //: from the line it is about so it never touches it.
        ".cm-diagnostic": {
          display: "flex",
          flexWrap: "wrap",
          alignItems: "flex-start",
          columnGap: "var(--space-2)",
          rowGap: "var(--space-2)",
          maxWidth: "min(26rem, 80vw)",
          padding: "var(--space-3) var(--space-4)",
          marginLeft: "0",
          fontSize: "var(--text-sm)",
          lineHeight: "1.45",
          borderLeft: "none",
          "--diagnostic-ink": "var(--muted)",
        },
        ".cm-diagnostic::before": {
          content: '"\\e4f8"',
          fontFamily: "Phosphor",
          fontSize: "1rem",
          lineHeight: "1.3",
          width: "1rem",
          flex: "none",
          color: "var(--diagnostic-ink)",
        },
        ".cm-diagnostic-error": { "--diagnostic-ink": "var(--error)" },
        ".cm-diagnostic-warning": { "--diagnostic-ink": "var(--warn)" },
        ".cm-diagnostic-info, .cm-diagnostic-hint": { "--diagnostic-ink": "var(--accent-text)" },
        ".cm-diagnostic-error::before": { content: '"\\e4f8"' },
        ".cm-diagnostic-warning::before": { content: '"\\e4e0"' },
        ".cm-diagnostic-info::before, .cm-diagnostic-hint::before": { content: '"\\e2ce"' },
        ".cm-diagnosticText": { flex: "1 1 calc(100% - 1rem - var(--space-2))", minWidth: "0", color: "var(--text)", fontWeight: "500", overflowWrap: "anywhere" },
        ".cm-diagnosticText + .cm-diagnosticAction": { marginLeft: "calc(1rem + var(--space-2))" },
        ".cm-tooltip-lint": { padding: "0", borderRadius: "var(--radius-md)" },
        //: A quick fix on the hover card, the quiet tinted button on its own
        //: row under the message it answers (the library's own is white on a
        //: fixed dark grey), at the dense control height, with the accent edge
        //: on hover and on keyboard focus.
        ".cm-diagnosticAction": {
          font: "inherit",
          fontSize: "var(--text-sm)",
          color: "var(--text)",
          backgroundColor: "var(--accent-soft)",
          border: "1px solid transparent",
          borderRadius: "var(--radius-md)",
          padding: "0 var(--space-3)",
          margin: "0",
          minHeight: "var(--control-h-dense)",
          cursor: "pointer",
        },
        ".cm-diagnosticAction:hover, .cm-diagnosticAction:focus-visible": {
          borderColor: "var(--accent)",
          outline: "none",
        },
        //: **Opaque, where the tooltip above is glass.** `--card` is 55%
        //: opaque (measured through `doccode.js`), which is right for a panel
        //: over the page's own ground and wrong for a box of words laid over
        //: other words: the code under a diagnostic read through its message.
        //: The ground the selection bar uses for the same reason
        //: (DESIGN.md's recipe index, "a bar of actions").
        ".cm-tooltip.cm-tooltip-hover, .cm-tooltip.cm-tooltip-autocomplete": {
          backgroundColor: "var(--modal-bg-opaque)",
        },
        ".cm-tooltip.cm-tooltip-hover": {
          borderRadius: "var(--radius-md)",
          boxShadow: "var(--shadow-md)",
          overflow: "hidden",
        },
        //: A gap between the card and the line it is about (measured 1px before):
        //: the library sets only the card's top and left, so the gap is a shift
        //: away from the line, whichever side it chose.
        ".cm-tooltip.cm-tooltip-hover.cm-tooltip-above": { transform: "translateY(calc(-1 * var(--space-1)))" },
        ".cm-tooltip.cm-tooltip-hover.cm-tooltip-below": { transform: "translateY(var(--space-1))" },
        ".cm-tooltip.cm-tooltip-autocomplete": {
          borderRadius: "var(--radius-sm, 6px)",
          boxShadow: "var(--shadow-md)",
          overflow: "hidden",
        },
        ".cm-tooltip.cm-tooltip-autocomplete > ul": {
          fontFamily: "var(--mono, ui-monospace, monospace)",
          fontSize: "var(--text-sm)",
          maxHeight: "16em",
        },
        ".cm-tooltip.cm-tooltip-autocomplete > ul > li": {
          padding: "var(--space-1) var(--space-4)",
          lineHeight: "1.5",
        },
        ".cm-tooltip-autocomplete ul li[aria-selected]": {
          backgroundColor: "var(--accent-soft)",
          color: "var(--text)",
        },
        ".cm-completionMatchedText": {
          textDecoration: "none",
          fontWeight: "700",
          color: "var(--accent-text)",
        },
        ".cm-completionDetail": { color: "var(--muted)", fontStyle: "normal" },
        ".cm-completionIcon": { color: "var(--muted)", opacity: "1" },
        //: The detail pane beside the list (an Emmet row's expansion): the
        //: list's own opaque ground and code type, because it is code laid
        //: over code.
        ".cm-tooltip.cm-completionInfo": {
          backgroundColor: "var(--modal-bg-opaque)",
          border: "1px solid var(--border)",
          borderRadius: "var(--radius-sm, 6px)",
          boxShadow: "var(--shadow-md)",
          padding: "var(--space-2) var(--space-3)",
          maxWidth: "min(480px, 60vw)",
        },
        ".cm-emmet-preview": {
          margin: "0",
          fontFamily: "var(--mono, ui-monospace, monospace)",
          fontSize: "var(--text-sm)",
          lineHeight: "1.5",
          color: "var(--text)",
          whiteSpace: "pre",
          tabSize: "2",
        },
        //: The ghost text: the rest of the chosen row after the caret, in the
        //: muted ink the placeholder uses, so it reads as offered, not typed.
        ".cm-ghostText": { color: "var(--muted)", opacity: "0.85", pointerEvents: "none" },
        //: Run's output, under the editor: a head row of the dock's own
        //: small ghost buttons, then the page (an HTML file) above the log.
        //: The log is code type, a hairline between rows, errors and
        //: warnings in their own inks on their soft grounds.
        ".cm-run-panel": {
          display: "flex",
          flexDirection: "column",
          height: "min(40vh, 320px)",
          borderTop: "1px solid var(--border)",
          backgroundColor: "var(--modal-bg-opaque)",
        },
        ".cm-run-head": {
          display: "flex",
          alignItems: "center",
          gap: "var(--space-2)",
          padding: "var(--space-1) var(--space-2)",
          borderBottom: "1px solid var(--border)",
        },
        ".cm-run-title": { fontWeight: "600", color: "var(--text)" },
        //: The status gives way first when the head is tight (Brief 70: a
        //: Python run's head with Input shown ran 60px past at 1440).
        ".cm-run-status": { color: "var(--muted)", fontSize: "var(--text-sm)", minWidth: "0", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" },
        ".cm-run-spacer": { flex: "1" },
        ".cm-run-body": { flex: "1", minHeight: "0", display: "flex", flexDirection: "column" },
        ".cm-run-frame": { display: "none", border: "0", width: "100%", flex: "3", minHeight: "0" },
        ".cm-run-panel.is-page .cm-run-frame": { display: "block", borderBottom: "1px solid var(--border)" },
        //: A page with nothing printed gives the frame the whole body, not 60
        //: percent of it and a line saying nothing ran (1031 CE7: 166 px).
        ".cm-run-panel.is-page .cm-run-log:empty": { display: "none" },
        ".cm-run-log": {
          flex: "2",
          minHeight: "0",
          overflow: "auto",
          margin: "0",
          padding: "0",
          listStyle: "none",
          fontFamily: "var(--mono, ui-monospace, monospace)",
          fontSize: "var(--text-sm)",
        },
        ".cm-run-row": {
          display: "flex",
          alignItems: "baseline",
          gap: "var(--space-2)",
          padding: "var(--space-1) var(--space-3)",
          borderBottom: "1px solid var(--border)",
          color: "var(--text)",
        },
        ".cm-run-row.is-error": { color: "var(--error)", backgroundColor: "var(--error-soft)" },
        ".cm-run-row.is-warn": { color: "var(--warn)", backgroundColor: "var(--warn-soft)" },
        ".cm-run-row.is-info, .cm-run-row.is-debug": { color: "var(--muted)" },
        ".cm-run-text": { flex: "1", whiteSpace: "pre-wrap", overflowWrap: "anywhere" },
        ".cm-run-line": { color: "var(--muted)", fontSize: "var(--text-xs)", whiteSpace: "nowrap" },
        //: A SQL statement's result (Brief 69, D5): the count on the row's
        //: first line, the table under it at the row's full width, scrolling
        //: sideways inside the row rather than widening the panel.
        ".cm-run-row.is-table": { flexWrap: "wrap" },
        ".cm-run-table-wrap": { flexBasis: "100%", minWidth: "0", overflowX: "auto" },
        ".cm-run-table": { borderCollapse: "collapse", fontSize: "var(--text-xs)" },
        ".cm-run-table th, .cm-run-table td": {
          border: "1px solid var(--border)",
          padding: "var(--space-1) var(--space-2)",
          textAlign: "left",
          whiteSpace: "nowrap",
        },
        ".cm-run-table th": { fontWeight: "600", backgroundColor: "var(--surface-2)" },
        ".cm-run-table td.is-null": { color: "var(--muted)", fontStyle: "italic" },
        ".cm-run-more": { margin: "var(--space-1) 0 0", color: "var(--muted)" },
        //: A test (D7): its state's icon, its name, its time, its line; a
        //: failure's message under it in the row's own ink.
        ".cm-run-test": { flexWrap: "wrap" },
        ".cm-run-test.is-pass > .ph": { color: "var(--ok)" },
        ".cm-run-test .cm-run-text": { flex: "1" },
        ".cm-run-ms": { color: "var(--muted)", fontSize: "var(--text-xs)", whiteSpace: "nowrap" },
        ".cm-run-why": { flexBasis: "100%", margin: "var(--space-1) 0 0", whiteSpace: "pre-wrap", font: "inherit", overflowWrap: "anywhere" },
        ".cm-run-summary": { fontWeight: "600" },
        //: Input (D9): the lines Python's input() reads, a field under the head.
        ".cm-run-stdin-wrap": {
          display: "flex",
          flexDirection: "column",
          gap: "var(--space-1)",
          padding: "var(--space-1) var(--space-2)",
          borderBottom: "1px solid var(--border)",
        },
        ".cm-run-stdin-label": { color: "var(--muted)", fontSize: "var(--text-sm)" },
        ".cm-run-stdin": { fontFamily: "var(--mono, ui-monospace, monospace)", fontSize: "var(--text-sm)", resize: "vertical", minHeight: "0" },
        //: input() asked mid-run (Brief 70): the prompt, then the field the
        //: answer is typed in, on the row the answer will take.
        ".cm-run-ask": { flex: "1", display: "flex", alignItems: "baseline", gap: "var(--space-2)", minWidth: "0" },
        ".cm-run-ask .cm-run-text": { flex: "none" },
        ".cm-run-ask-field": { flex: "1", minWidth: "0", fontFamily: "inherit", fontSize: "inherit" },
        //: Run on a .py file before the Pyodide extra is installed: the row's
        //: one action, kept whole beside the sentence it answers.
        ".cm-run-install": { flex: "none", whiteSpace: "nowrap" },
        //: The Debug tab: the five actions and where it stopped, the exception
        //: if that is why, then Variables, Watch, Call stack and Breakpoints as
        //: columns that fold to a stack on a narrow panel.
        //: The Debug tab is one of the panel's panes (Brief 71): shown and hidden
        //: by `.hidden`, like the others.
        ".cm-debug": { display: "flex", flex: "1", minHeight: "0", overflow: "auto", flexDirection: "column" },
        ".cm-debug-bar": {
          display: "flex",
          flexWrap: "wrap",
          alignItems: "center",
          gap: "var(--space-1)",
          padding: "var(--space-1) var(--space-2)",
          borderBottom: "1px solid var(--border)",
        },
        ".cm-debug-where": { color: "var(--muted)", fontSize: "var(--text-sm)", marginInlineStart: "var(--space-2)" },
        ".cm-debug-thrown": {
          margin: "0",
          padding: "var(--space-1) var(--space-3)",
          maxHeight: "8rem",
          overflow: "auto",
          whiteSpace: "pre-wrap",
          overflowWrap: "anywhere",
          fontFamily: "var(--mono, ui-monospace, monospace)",
          fontSize: "var(--text-xs)",
          color: "var(--error)",
          backgroundColor: "var(--error-soft)",
          borderBottom: "1px solid var(--border)",
        },
        ".cm-debug-grid": { display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(13rem, 1fr))" },
        ".cm-debug-section": {
          minWidth: "0",
          padding: "var(--space-1) var(--space-2)",
          borderInlineEnd: "1px solid var(--border)",
          borderBottom: "1px solid var(--border)",
        },
        ".cm-debug-title": { margin: "0 0 var(--space-1)", fontSize: "var(--text-sm)", fontWeight: "600", color: "var(--text)" },
        ".cm-debug-list": { listStyle: "none", margin: "0", padding: "0", fontSize: "var(--text-sm)" },
        ".cm-debug-row": { display: "flex", alignItems: "baseline", gap: "var(--space-2)", minWidth: "0" },
        ".cm-debug-name, .cm-debug-value": { fontFamily: "var(--mono, ui-monospace, monospace)" },
        ".cm-debug-name": { flex: "none", maxWidth: "45%", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", color: "var(--accent-text)" },
        ".cm-debug-value": { flex: "1", minWidth: "0", whiteSpace: "pre-wrap", overflowWrap: "anywhere", color: "var(--text)" },
        ".cm-debug-row.is-error .cm-debug-value": { color: "var(--error)" },
        ".cm-debug-row.has-children": { display: "block" },
        ".cm-debug-tree > summary": { display: "flex", alignItems: "baseline", gap: "var(--space-2)", minWidth: "0", cursor: "pointer", listStyle: "none" },
        ".cm-debug-tree > summary::-webkit-details-marker": { display: "none" },
        ".cm-debug-tree > summary::before": { content: '"\\25B8"', flex: "none", color: "var(--muted)" },
        ".cm-debug-tree[open] > summary::before": { content: '"\\25BE"' },
        ".cm-debug-children": { paddingInlineStart: "var(--space-3)", borderInlineStart: "1px solid var(--border)", marginInlineStart: "var(--space-1)" },
        ".cm-debug-sub": { marginTop: "var(--space-1)", color: "var(--muted)", fontSize: "var(--text-xs)" },
        ".cm-debug-empty": { color: "var(--muted)" },
        ".cm-debug-go": { minWidth: "0", textAlign: "start", fontFamily: "var(--mono, ui-monospace, monospace)" },
        ".cm-debug-remove": { marginInlineStart: "auto", flex: "none" },
        ".cm-debug-watch-add": { width: "100%", minHeight: "var(--target-min)", marginTop: "var(--space-1)", fontFamily: "var(--mono, ui-monospace, monospace)", fontSize: "var(--text-sm)" },
        //: The breakpoint lane, left of the numbers, as VS Code's: a dot, red,
        //: amber with a condition; a faint one under the pointer says a click
        //: puts one there. The stopped line is lit across the text.
        ".cm-debug-gutter .cm-gutterElement": { display: "flex", alignItems: "center", justifyContent: "center", width: "0.875rem", cursor: "pointer" },
        ".cm-debug-bp": { display: "inline-block", width: "0.625rem", height: "0.625rem", borderRadius: "50%", backgroundColor: "var(--error)" },
        ".cm-debug-bp.is-cond": { backgroundColor: "var(--warn)" },
        ".cm-debug-gutter .cm-gutterElement:hover:not(:has(.cm-debug-bp))::before": {
          content: '""',
          width: "0.625rem",
          height: "0.625rem",
          borderRadius: "50%",
          backgroundColor: "var(--error)",
          opacity: "0.35",
        },
        ".cm-debug-here": { backgroundColor: "var(--warn-soft)" },
        //: Sticky scroll: the enclosing scopes' first lines over the top of the
        //: scroller, on the opaque ground words laid over words take, with the
        //: hairline and small shadow of a bar that sits above content.
        ".cm-sticky": {
          position: "absolute",
          zIndex: "3",
          backgroundColor: "var(--modal-bg-opaque)",
          borderBottom: "1px solid var(--border)",
          boxShadow: "var(--shadow-sm)",
        },
        ".cm-sticky.hidden": { display: "none" },
        ".cm-sticky-line": {
          paddingLeft: "var(--sticky-pad, 0px)",
          whiteSpace: "pre",
          overflow: "hidden",
          textOverflow: "ellipsis",
          cursor: "pointer",
        },
        ".cm-sticky-line:hover": { backgroundColor: "var(--accent-soft)" },
        //: Shown whitespace (Alt+Z's neighbour in the menu): a dot per space and
        //: a line through a tab, in muted ink rather than the library's grey.
        ".cm-highlightSpace": {
          backgroundImage: "radial-gradient(circle at 50% 55%, var(--muted) 14%, transparent 16%)",
        },
        ".cm-highlightTab": {
          backgroundImage: "linear-gradient(var(--muted), var(--muted))",
          backgroundSize: "70% 1px",
          backgroundPosition: "50% 55%",
          backgroundRepeat: "no-repeat",
        },
        //: Indentation guides (INBOX 402, 1562): the line draws them, a hairline
        //: in `--border` at the left edge of each step, so a guide is one rule
        //: over the whole row box (wrapped and blank rows too), not a dash per
        //: row. A step is 2em of spaces or a tab's width; the gradient repeats
        //: at the step and `.cm-indent-nN` cuts it to N steps.
        ".cm-indent-lines": {
          backgroundImage: "repeating-linear-gradient(to right, var(--border) 0 1px, transparent 1px var(--doc-indent-step))",
          backgroundRepeat: "no-repeat",
          backgroundPosition: "0 0",
        },
        ".cm-indent-spaces": { "--doc-indent-step": "2em" },
        ".cm-indent-tabs": { "--doc-indent-step": "calc(var(--doc-tabs, 2) * var(--doc-space-w, 0.25em))" },
        ...Object.fromEntries(
          Array.from({ length: docIndentGuides.levels }, (_, i) => [
            `.cm-indent-n${i + 1}`,
            { backgroundSize: `calc(${i + 1} * var(--doc-indent-step)) 100%` },
          ])
        ),
        //: Every step drawn 2em wide, whatever its number of spaces
        //: (`docIndentGuides`, which measures `--doc-space-w`).
        ".cm-indent-w1": { letterSpacing: "calc(2em / 1 - var(--doc-space-w, 0.25em))" },
        ".cm-indent-w2": { letterSpacing: "calc(2em / 2 - var(--doc-space-w, 0.25em))" },
        ".cm-indent-w3": { letterSpacing: "calc(2em / 3 - var(--doc-space-w, 0.25em))" },
        ".cm-indent-w4": { letterSpacing: "calc(2em / 4 - var(--doc-space-w, 0.25em))" },
        ".cm-indent-w5": { letterSpacing: "calc(2em / 5 - var(--doc-space-w, 0.25em))" },
        ".cm-indent-w6": { letterSpacing: "calc(2em / 6 - var(--doc-space-w, 0.25em))" },
        ".cm-indent-w7": { letterSpacing: "calc(2em / 7 - var(--doc-space-w, 0.25em))" },
        ".cm-indent-w8": { letterSpacing: "calc(2em / 8 - var(--doc-space-w, 0.25em))" },
        //: Bracket pairs by depth: three of the app's own inks, each mixed a
        //: third of the way back to the text, so the pairs are told apart
        //: without the brackets shouting over the code between them.
        ".cm-bracket-0": { color: "color-mix(in srgb, var(--accent-text) 70%, var(--text))" },
        ".cm-bracket-1": { color: "color-mix(in srgb, var(--syntax-keyword, var(--ok)) 70%, var(--text))" },
        ".cm-bracket-2": { color: "color-mix(in srgb, var(--warn) 70%, var(--text))" },
        //: A name's one line on hover: the name in code type, the line in the
        //: body's, the values it takes in muted ink under it.
        ".cm-hover-doc": {
          padding: "var(--space-2) var(--space-3)",
          maxWidth: "min(420px, 70vw)",
          fontSize: "var(--text-sm)",
          lineHeight: "1.5",
        },
        ".cm-hover-doc code": { fontFamily: "var(--mono, ui-monospace, monospace)", fontWeight: "600", color: "var(--text)" },
        ".cm-hover-doc-line": { color: "var(--text)", marginTop: "var(--space-1)" },
        ".cm-hover-doc-values": { color: "var(--muted)", marginTop: "var(--space-1)" },
        //: A colour value's swatch: the colour on a hairline in the border
        //: token, square with the inner radius, one text-height small, so it
        //: reads as a mark beside the value and not as a control of its own.
        ".cm-color-swatch": {
          display: "inline-block",
          width: "0.8em",
          height: "0.8em",
          marginRight: "var(--space-1)",
          verticalAlign: "-0.05em",
          border: "1px solid var(--border)",
          borderRadius: "var(--radius-inner)",
          cursor: "pointer",
        },

        //: --- Live preview -------------------------------------------------
        //: The rendered shapes, in the app's own type scale rather than in a
        //: second one. A heading in the editor and the same heading in the
        //: rendered preview beside it are the thing a split view is *for*, so
        //: the two have to agree.
        ".cm-md-h1": { fontSize: "1.8em", fontWeight: "700", lineHeight: "1.25" },
        ".cm-md-h2": { fontSize: "1.5em", fontWeight: "700", lineHeight: "1.3" },
        ".cm-md-h3": { fontSize: "1.25em", fontWeight: "650", lineHeight: "1.35" },
        ".cm-md-h4": { fontSize: "1.1em", fontWeight: "650" },
        ".cm-md-h5": { fontSize: "1em", fontWeight: "650" },
        ".cm-md-h6": { fontSize: "1em", fontWeight: "650", color: "var(--muted)" },
        ".cm-md-strong": { fontWeight: "700" },
        ".cm-md-em": { fontStyle: "italic" },
        ".cm-md-strike": { textDecoration: "line-through", opacity: "0.65" },
        //: **The three tinted inlines wrap as whole chips, not as a chip cut in
        //: half.** Reported (INBOX 232): "link chips wrap oddly". `box-
        //: decoration-break` defaults to `slice`, which lays the background,
        //: the rounded corners and the horizontal padding out once across the
        //: whole run and then cuts it at the line break: the fragment that ends
        //: a line has a flat right edge and no padding after its last letter,
        //: and the fragment that starts the next one is flush against the
        //: column's left margin with no padding and no rounding. Measured at
        //: 390px on a document of wiki links: three of nine chips broke that
        //: way, the second fragment starting at x=10, the column's own edge.
        //:
        //: `clone` gives every fragment the whole decoration, so a wrapped chip
        //: reads as two chips rather than as one broken one. The `-webkit-`
        //: spelling is the one Chromium still implements, so both are set and
        //: the standard name is second, to win where it is supported.
        //:
        //: All three, not just the wiki link: inline code and a highlight are
        //: the same shape (a tint with a radius and side padding) and break the
        //: same way, which is why a fix for one of them is a fix for the class.
        ".cm-md-code, .cm-md-highlight, .cm-md-wiki": {
          WebkitBoxDecorationBreak: "clone",
          boxDecorationBreak: "clone",
        },
        ".cm-md-code": {
          fontFamily: "var(--mono, ui-monospace, monospace)",
          backgroundColor: "var(--field-inset)",
          borderRadius: "3px",
          padding: "0 0.25em",
        },
        //: Yellow is the default, the same as the saved view's
        //: `mark.text-highlight-yellow`. It read `--accent-soft` here, which is
        //: the *blue* of that set, so every plain highlight in the live view came
        //: out blue and only a highlight somebody had explicitly called blue
        //: looked right. One rule per colour in the allowlist above, taking the
        //: same tokens as 05-sidebars-themes.css so the two views match in both
        //: themes.
        ".cm-md-highlight": { backgroundColor: "var(--warn-soft)", borderRadius: "3px" },
        ".cm-md-highlight-yellow": { backgroundColor: "var(--warn-soft)" },
        ".cm-md-highlight-green": { backgroundColor: "var(--ok-soft)" },
        ".cm-md-highlight-blue": { backgroundColor: "var(--accent-soft)" },
        ".cm-md-highlight-pink": { backgroundColor: "rgba(236, 72, 153, 0.22)" },
        ".cm-md-highlight-purple": { backgroundColor: "rgba(168, 85, 247, 0.22)" },
        ".cm-md-highlight-orange": { backgroundColor: "rgba(249, 115, 22, 0.22)" },
        ".cm-md-highlight-red": { backgroundColor: "rgba(239, 68, 68, 0.22)" },
        ".cm-md-highlight-grey": { backgroundColor: "rgba(148, 163, 184, 0.25)" },
        //: **A commented span, told apart from a plain highlight** (Phase 5 item
        //: 1). A hairline under the words rather than a fourth underline *shape*:
        //: the three the findings own (wavy in the error ink, wavy in the accent,
        //: dotted in the muted) are all `text-decoration`, and a fourth one would
        //: be a fourth thing for a reader to decode in the same channel. A border
        //: is a different channel, and it reads correctly against the highlight's
        //: own ground, which is doing half the work already.
        ".cm-md-commented": { borderBottom: "1px solid var(--accent)" },
        //: **The remark itself, as a pin rather than as purple text.** A comment
        //: has to be visible in the document without being read in it, which is
        //: the whole difference between a margin note and the prose, so the
        //: `%%…%%` hides like every other marker and this takes its place. Sized
        //: in `em` and aligned on the text's own middle so a line with a pin in it
        //: is the same height as a line without one: measured, 24px either way.
        //: Every longhand a bare `button` would otherwise bring (the accent fill,
        //: the shadow, the 0.5rem of padding) is turned off here rather than in
        //: the stylesheet, because this element exists only inside the view and a
        //: widget split across two files is a widget that drifts.
        ".doc-comment-pin": {
          display: "inline-flex",
          verticalAlign: "middle",
          margin: "0 0.15em",
          padding: "0 0.25em",
          border: "0",
          borderRadius: "var(--radius-pill)",
          background: "var(--accent-soft)",
          boxShadow: "none",
          color: "var(--accent-text)",
          fontSize: "0.8em",
          lineHeight: "1.6",
          cursor: "pointer",
        },
        ".doc-comment-pin:hover": { background: "var(--accent)", color: "var(--on-accent)" },
        ".cm-md-link": { color: "var(--accent-text)", textDecoration: "underline", cursor: "pointer" },
        ".cm-md-wiki": {
          color: "var(--accent-text)",
          backgroundColor: "var(--accent-soft)",
          borderRadius: "4px",
          padding: "0 0.25em",
          cursor: "pointer",
        },
        //: A block id when the caret is on its line. Muted and monospaced, so it
        //: reads as scaffolding the moment it appears rather than as a word
        //: somebody typed at the end of the sentence.
        ".cm-md-blockid": {
          color: "var(--muted)",
          fontFamily: "var(--mono, ui-monospace, monospace)",
          fontSize: "0.85em",
        },
        //: **A list item's hanging indent.** `padding-left` moves the whole
        //: line in and a matching negative `text-indent` pulls the first line
        //: back out again, so the marker sits in the margin and the words line
        //: up under each other however many times the item wraps. One rule per
        //: depth rather than a CSS variable, because a CodeMirror theme is a
        //: static stylesheet and there is nowhere to set a per-line variable
        //: without an inline style, which the app's CSP refuses.
        //:
        //: `1.6em` is the width of a marker and its space at this type size,
        //: measured rather than chosen: a `-` plus a space is 2 characters of a
        //: 0.8em-per-character face.
        ".cm-md-li": { paddingLeft: "1.6em", textIndent: "-1.6em" },
        ".cm-md-li-1": { paddingLeft: "3.2em", textIndent: "-1.6em", ...docListGuides(1) },
        ".cm-md-li-2": { paddingLeft: "4.8em", textIndent: "-1.6em", ...docListGuides(2) },
        ".cm-md-li-3": { paddingLeft: "6.4em", textIndent: "-1.6em", ...docListGuides(3) },
        ".cm-md-li-4": { paddingLeft: "8em", textIndent: "-1.6em", ...docListGuides(4) },
        ".cm-md-task-done": {
          color: "var(--muted)",
          textDecoration: "line-through",
          textDecorationColor: "color-mix(in srgb, var(--muted) 70%, transparent)",
        },
        //: The marker itself: the muted ink, so the eye reads the words rather
        //: than the punctuation, and left in the document so it can be
        //: selected, deleted and typed over like any other character.
        ".cm-md-li-mark": { color: "var(--muted)" },
        //: `textIndent: 0`: an inline-block is a block container, so it inherits
        //: the line's hanging `-1.6em` and drew its own glyph 24px left of its
        //: box (bullet 44px from the words, half outside the page at 720).
        ".cm-md-li-bullet": { display: "inline-block", width: "1.6em", textIndent: "0" },
        //: The four dot-point styles are drawn, not typed (no glyph outside Phosphor): a disc, a ring,
        //: a square and a short bar, in the marker's muted ink and centred on the line.
        ".cm-md-li-bullet::before": { content: '""', display: "inline-block", boxSizing: "border-box", width: "0.4em", height: "0.4em", background: "currentColor", verticalAlign: "middle" },
        ".cm-md-li-bullet-disc::before": { borderRadius: "50%" },
        ".cm-md-li-bullet-circle::before": { borderRadius: "50%", background: "transparent", border: "1.5px solid currentColor" },
        ".cm-md-li-bullet-dash::before": { width: "0.6em", height: "2px" },
        ".cm-md-li-num": { display: "inline-block", minWidth: "1.6em", textIndent: "0" },
        //: **A quotation's bar has to be seen to do its job** (17c). It was
        //: `--border`, a 10% ink that composites to 1.2:1 on the page, so a
        //: quotation read as a paragraph set in grey. Half the muted ink is a
        //: rule you can see without it competing with the callout's accent
        //: bar, and the rendered view's `#doc-preview blockquote` (09-editor.css)
        //: now draws the same bar, inset and ink, where before it drew the
        //: browser's own 40px indent and nothing else.
        ".cm-md-quote": {
          borderLeft: "3px solid color-mix(in srgb, var(--muted) 70%, transparent)",
          paddingLeft: "var(--space-5)",
          color: "var(--muted)",
        },
        //: The kind's own ink (`--callout-accent`, set per kind in
        //: 05-sidebars-themes.css for this class and the rendered `.callout`
        //: alike), so a warning is amber in the Live view as it is in Read.
        ".cm-md-callout": {
          borderLeft: "3px solid var(--callout-accent)",
          paddingLeft: "0.75em",
          backgroundColor: "color-mix(in srgb, var(--callout-accent) 8%, transparent)",
        },
        ".cm-md-callout-toggle": {
          borderLeftColor: "var(--border)",
          backgroundColor: "transparent",
        },
        //: A quote's attribution line, set small and muted like the rendered
        //: figure's caption.
        ".cm-md-quote-cite": { fontSize: "0.88em", fontStyle: "normal" },
        ".cm-md-rule-thick": {
          backgroundImage: "linear-gradient(color-mix(in srgb, var(--muted) 55%, transparent), color-mix(in srgb, var(--muted) 55%, transparent))",
          backgroundSize: "100% 3px",
        },
        ".cm-md-rule-dots": { backgroundImage: "none", textAlign: "center" },
        ".cm-md-rule-dots::after": {
          content: "'\\2022\\2003\\2022\\2003\\2022'",
          color: "var(--muted)",
          fontSize: "0.85em",
        },
        //: The inset is the rendered `pre`'s own (`--space-5`): without it the
        //: code's first glyph sat on the very edge of its tinted slab, 0px in,
        //: which is how a block reads as a highlighted paragraph rather than
        //: as a panel of code (17c).
        ".cm-md-fence": {
          position: "relative",
          fontFamily: "var(--mono, ui-monospace, monospace)",
          backgroundColor: "var(--field-inset)",
          paddingInline: "var(--space-5)",
        },
        //: The opening and closing fence rows. Their text is hidden (INBOX
        //: 198), so a full line-height row of it is 26px of nothing at each end
        //: of every code block; these give them the height of padding instead,
        //: and round the block's own corners so five tinted rows read as one
        //: slab. `position: relative` is the anchor for the language label
        //: below.
        ".cm-md-fence-open, .cm-md-fence-close": {
          position: "relative",
        },
        //: Only while the row has nothing on it. With the caret inside the
        //: block its `” ``` ”` is back, and half a line of height would clip it.
        //:
        //: **And only while the line numbers are off** (INBOX 262: "the page
        //: numbers and collapse arrows in the documents clash with other page
        //: numnbers"). A gutter draws one element per line at that line's own
        //: height, but the number inside it keeps the editor's line-height, so
        //: a row collapsed to half a line leaves its digit standing 26px tall
        //: in an 8px box. Measured on a fenced block with the gutter on: "6
        //: paints 18px into 7" and "8 paints 18px into 9", which is the pair in
        //: the report's screenshot exactly.
        //:
        //: Numbers win, because they are the contract: one row, one number, in
        //: line with the text it counts. The tidy block is what prose gets, and
        //: prose is where the gutter is off by default (`docGutterWanted`),
        //: which is also where a fenced block wearing two blank rows was worth
        //: fixing in the first place.
        //:
        //: The decision is made where the class is set, not here: a CodeMirror
        //: theme's rules are injected into a stylesheet this page cannot read
        //: back, and a `:has(.cm-gutters)` guard written here could not be
        //: verified in the browser, only hoped for. `docGutterWanted` already
        //: knows the answer at decoration time.
        ".cm-md-fence-quiet": {
          height: "0.5em",
        },
        ".cm-md-fence-open": {
          position: "relative",
          borderTopLeftRadius: "var(--radius-sm, 6px)",
          borderTopRightRadius: "var(--radius-sm, 6px)",
        },
        ".cm-md-fence-close": {
          borderBottomLeftRadius: "var(--radius-sm, 6px)",
          borderBottomRightRadius: "var(--radius-sm, 6px)",
        },
        //: The block's title or language, in the corner rather than on a line
        //: of its own: a label for the block, the same relationship
        //: `.cm-md-callout-label` has to a callout, and the block stops
        //: spending rows on things that are not code. A button (a widget
        //: `DocFenceLabelWidget`) that lists the language names; absolute, so
        //: it takes no row.
        ".cm-md-fence-label": {
          position: "absolute",
          right: "0.6em",
          top: "0",
          fontSize: "0.7em",
          lineHeight: "1.6",
          color: "var(--muted)",
          background: "none",
          border: "none",
          padding: "0 0.4em",
          minHeight: "0",
          cursor: "pointer",
          userSelect: "none",
        },
        ".cm-md-fence-label:hover, .cm-md-fence-label:focus-visible": { color: "var(--ink)" },
        //: Copy, over the first code line's corner (L-documents-65). Absolute, so the fence row keeps its 8px; shown while the line is hovered or the button focused, always on a touch screen, where a pseudo-element grows the hit area to 44px.
        ".cm-md-fence-copy": {
          position: "absolute",
          right: "0.6em",
          top: "0",
          fontSize: "0.85em",
          lineHeight: "1.6",
          color: "var(--muted)",
          background: "none",
          border: "none",
          padding: "0 0.3em",
          minHeight: "0",
          cursor: "pointer",
          userSelect: "none",
          opacity: "0",
        },
        ".cm-md-fence:hover .cm-md-fence-copy, .cm-md-fence-copy:focus-visible, .cm-md-fence-copy.is-touch": { opacity: "1" },
        ".cm-md-fence-copy:hover, .cm-md-fence-copy:focus-visible": { color: "var(--ink)" },
        ".cm-md-fence-copy.is-touch::after": {
          content: '""',
          position: "absolute",
          top: "-8px",
          right: "-8px",
          width: "44px",
          height: "44px",
        },
        //: A rule whose own `---` is hidden is an empty line, and an empty line
        //: with a bottom border is a hairline sitting on the baseline of nothing.
        //: The height is what makes it read as a divider between two blocks
        //: rather than as an underline belonging to the paragraph above.
        //: **A full line tall, the rule drawn in its middle** (INBOX 1300 C44).
        //: It was a 0.6em box with a bottom border and 0.4em of margin, so the
        //: line-number gutter, which gives each number the line's own height,
        //: had an 8.8px element holding a 14px figure: numbers 1 and 2 overlapped
        //: (4 overlaps in 8 lines measured, `scratchpad/ui-sweeps/c44.js`). The
        //: gutter follows the line's height, so the line is given a line's height.
        ".cm-md-rule": {
          backgroundImage: "linear-gradient(var(--border), var(--border))",
          backgroundSize: "100% 1px",
          backgroundPosition: "center",
          backgroundRepeat: "no-repeat",
        },
        //: The gaps between blocks (17b), one token each; the note beside the
        //: decoration in `docLivePlugin` says why this is `line-height` and not
        //: `height`.
        //: Read's heading margins (09-editor.css, audit 1102 DX25) are these same
        //: three: 2rem and 1.5rem before a heading, `--space-4` after it, and 1.6 leading.
        ".cm-md-gap": { lineHeight: "var(--space-6)" },
        ".cm-md-gap-major": { lineHeight: "var(--space-9)" },
        ".cm-md-gap-minor": { lineHeight: "var(--space-8)" },
        ".cm-md-gap-tight": { lineHeight: "var(--space-4)" },
        ".cm-md-gap-extra": { lineHeight: "0" },
        //: The callout's kind, in the place its `[!note]` marker was. Set in
        //: `em` so it tracks the editor's own type scale, and in the muted ink
        //: because it labels the block rather than being part of what it says.
        ".cm-md-callout-label": {
          display: "inline-flex",
          alignItems: "center",
          gap: "0.35em",
          fontSize: "0.85em",
          fontWeight: "600",
          color: "var(--ink)",
          marginRight: "0.4em",
          userSelect: "none",
          verticalAlign: "baseline",
        },
        //: The kind's badge, the rendered head's `.callout-icon` at the Live
        //: view's type size, and the one control on the chip that is a button:
        //: it opens the kinds menu.
        ".cm-md-callout-kindbtn": {
          display: "inline-grid",
          placeItems: "center",
          width: "1.5em",
          height: "1.5em",
          borderRadius: "var(--radius-sm)",
          backgroundColor: "color-mix(in srgb, var(--callout-accent) 18%, transparent)",
          color: "var(--callout-accent)",
          cursor: "pointer",
        },
        ".cm-md-callout-kindbtn:hover": {
          backgroundColor: "color-mix(in srgb, var(--callout-accent) 30%, transparent)",
        },
        //: The kind button is a tile with a caret, so it reads as a menu.
        ".cm-md-callout-kindbtn:has(.cm-md-callout-caret)": {
          display: "inline-flex",
          gap: "0.1em",
          width: "auto",
          padding: "0 0.3em",
        },
        ".cm-md-callout-caret": { fontSize: "0.7em", opacity: "0.75" },
        //: No title: the kind's name stands in for one, a step back.
        ".cm-md-callout-label .cm-md-callout-word": { color: "var(--muted)", fontWeight: "500" },
        ".cm-md-callout-head": { fontWeight: "600" },
        ".cm-md-callout-hint": { color: "var(--muted)", pointerEvents: "none", userSelect: "none" },
        //: A footnote's identifier, raised, where its brackets were. The
        //: reference is a link to the definition; the definition is the place
        //: being linked to, so only one of them is clickable.
        //: Math sits on the text's own baseline and takes the editor's ink;
        //: MathML brings its own metrics, so nothing here sets a size.
        //: An embedded card is a block of app inside a line of text, so it is
        //: given the line's width to work in and nothing else: every card in it
        //: is styled by the stylesheet that owns that card.
        ".cm-md-embed": {
          display: "inline-block",
          maxWidth: "100%",
          verticalAlign: "top",
          cursor: "pointer",
        },
        //: The cards keep their own appearance and are given a width to work
        //: in: a note card sized to its content is as wide as its longest line,
        //: and a minimap is `width: 100%` of whatever box it is handed.
        ".cm-md-embed .entry-list": { width: "min(420px, 100%)", margin: "0", padding: "0" },
        ".cm-md-embed .doc-embed-map": { display: "block", width: "min(320px, 100%)" },
        ".cm-md-embed .att-card": { width: "min(360px, 100%)" },
        ".cm-md-math": { cursor: "text" },
        //: The lines under a multi-line formula's drawn first line.
        ".cm-md-math-fold": { display: "none" },
        ".cm-md-math-block": { display: "block", textAlign: "center", margin: "0.2em 0" },
        ".cm-md-footnote": {
          verticalAlign: "super",
          fontSize: "0.72em",
          color: "var(--accent-text)",
          fontWeight: "600",
        },
        ".cm-md-footnote-ref": {
          cursor: "pointer",
          //: A target of at least 24px (44 under touch) with no change to the
          //: line: the padding is the hit area, the negative margin takes it
          //: out of the layout (audit 1102 DX21, the same pair as `.md-fn-ref a`).
          padding: "var(--space-3) var(--space-5)",
          margin: "0 calc(var(--space-5) * -1)",
        },
        //: The toggle's chevron sits with the callout's own label, in the same
        //: muted ink, because it is part of the same control.
        ".cm-md-callout-fold": { fontSize: "0.9em", opacity: "0.8" },
        ".cm-md-callout-label [data-doc-callout-fold]": { cursor: "pointer" },
        ".cm-md-task-hit": { cursor: "pointer" },
        ".cm-md-image": { maxWidth: "100%", borderRadius: "var(--radius-sm)" },
        ".cm-md-image-under": { display: "block", marginTop: "var(--space-2)" },

        //: --- tables ---------------------------------------------------------
        //: **A grid over the line, not a `<table>` widget.** Replacing the block
        //: with a rendered table is what every "table editor" in a markdown app
        //: does and it is what forces them to have a serialiser, which is what
        //: loses the author's own whitespace (PLAN D4's gate, and the long
        //: comment on the model at the top of this file). Here the pipes are
        //: hidden like every other marker in this view and each cell is a mark,
        //: so `display: grid` on the line turns those marks into the columns:
        //: the text on screen is still the text in the file, at the same
        //: offsets, and the caret walks it normally.
        //:
        //: `minmax(0, 1fr)` rather than `1fr`, because a grid column's implicit
        //: minimum is its content's min-content width, so one long unbroken word
        //: in a cell would push the table wider than the editor instead of
        //: wrapping.
        ".cm-md-table": {
          display: "grid",
          "--doc-table-col-min": "6em",
          borderLeft: "1px solid var(--border)",
          //: The cell menu is positioned against whichever row it is on.
          position: "relative",
        },
        //: Past `DOC_TABLE_GRID_MAX` columns there is no class to place the
        //: cells with, so the line falls back to what it did before them. It is
        //: the worse rendering (every zero-width child behind a hidden pipe
        //: takes a track of its own), and it is a table no editor this wide can
        //: show usefully in any case.
        ".cm-md-table-wide": {
          gridAutoFlow: "column",
          gridAutoColumns: "minmax(var(--doc-table-col-min), 1fr)",
        },
        ...docTableGridRules(),
        ".cm-md-table-head": {
          fontWeight: "650",
          backgroundColor: "var(--field-inset)",
          borderTop: "1px solid var(--border)",
          //: The cell menu is positioned against this line.
          position: "relative",
        },
        //: The rendered view's own cell inset (`.md-table td`: 0.4rem by
        //: 0.6rem), where this was 0.05em by 0.5em and a row of words sat
        //: against the rules above and below it (17c, measured in
        //: `scratchpad/ui-sweeps/docblocks17c.js`).
        ".cm-md-td": {
          padding: "var(--space-2) var(--space-4)",
          borderRight: "1px solid var(--border)",
          borderBottom: "1px solid var(--border)",
        },
        //: The cell the caret is in: a ring inside the cell, so it moves no
        //: rule and changes no column width, and a faint ground that sits
        //: under a selection rather than hiding it.
        ".cm-md-td-active": {
          boxShadow: "inset 0 0 0 2px var(--accent)",
          backgroundColor: "color-mix(in srgb, var(--accent) 6%, transparent)",
          borderRadius: "var(--radius-sm, 6px)",
        },
        ".cm-md-table .cm-md-td-last": {
          paddingRight: "calc(var(--space-4) + 1.75rem)",
        },
        //: Room for the filter chip beside the menu, so it never covers the header's last word.
        ".cm-md-table .cm-md-td-filtered": { paddingRight: "calc(var(--space-4) + 1.75rem + 9rem)" },
        ".cm-md-td-left": { textAlign: "left" },
        ".cm-md-td-center": { textAlign: "center" },
        ".cm-md-td-right": { textAlign: "right" },
        //: The delimiter row is the header's underline, and the header's cells
        //: already draw that. With its own text hidden it would otherwise leave
        //: a blank line through the middle of the table; it comes back to full
        //: height the moment the caret arrives on it, which is the rule `---`
        //: has followed here since Phase 2.
        ".cm-md-table-rule": { height: "0", overflow: "hidden" },
        //: A frontmatter line, hidden the same way and for the same reason: the
        //: properties panel above the editor is where it is read and written.
        //: `border: 0` as well as the height, and it is measured: the opening
        //: fence is also a `---`, so it carries `.cm-md-rule`'s bottom border,
        //: and a zero-high line with a border is a 1px line across the top of
        //: the document.
        ".cm-md-frontmatter": { height: "0", overflow: "hidden", border: "0" },
        //: Out of the grid's flow, or the menu would be a column of its own and
        //: every cell in the table would narrow to make room for it.
        //: Centred on its row, which is now any row (the menu follows the
        //: caret): pinned to the top it sat 5px high on a one-line row.
        ".cm-md-table-menu": {
          position: "absolute",
          right: "2px",
          top: "calc(50% - 0.875rem)",
          opacity: "0.7",
        },
        ".cm-md-table-menu:hover, .cm-md-table-menu:focus-within": { opacity: "1" },
        //: A filtered row is out of the grid, not blank. Two classes beat the
        //: line's `display: grid`.
        ".cm-md-table.cm-md-row-hidden": { display: "none" },
        //: A formula's result reads as a computed value, not typed text.
        ".cm-md-td-calc": { fontVariantNumeric: "tabular-nums", fontStyle: "italic" },
        //: The filter chip sits left of the menu on the header row, out of the
        //: grid's flow like the menu itself.
        ".cm-md-table-filter": {
          position: "absolute",
          right: "calc(1.75rem + var(--space-2))",
          top: "calc(50% - 0.75rem)",
          maxWidth: "min(18rem, 40vw)",
          height: "1.5rem",
          minHeight: "0",
          padding: "0 var(--space-2)",
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
        },

        //: --- the prose findings ---------------------------------------------
        //: Three shapes, one per kind of claim. Wavy for a spelling
        //: the checker is sure about, wavy in the accent for a style note,
        //: dotted for a repeated word: three, because three is what a reader can
        //: decode at a glance from the shape of a line.
        ".cm-finding": {
          textDecorationSkipInk: "none",
          textUnderlineOffset: "0.18em",
          cursor: "pointer",
        },
        //: **The hover, which was the one surface in this feature with none.**
        //: Four things draw a finding (the underline, the word menu, the panel,
        //: the dictionary) and three of them answered the pointer; the underline
        //: offered `cursor: pointer` and nothing else, so the only way to learn
        //: that a squiggle is pressable was to press it.
        //:
        //: A tint rather than a thicker line: the three kinds are told apart by
        //: the *shape* of their underline (wavy, wavy, dotted), and thickening
        //: one on hover moves it towards another kind's shape. A ground behind
        //: the word says "this is one object" without touching the mark that
        //: says which kind it is, and it is the same thing `.menu-item:hover`
        //: does one surface over.
        //:
        //: 12% of the kind's own colour, mixed against the page rather than
        //: stated as an alpha, so it composes on the editor's ground in either
        //: theme and follows `[data-contrast="on"]`'s redefinitions of
        //: `--error`, `--accent` and `--muted` without a branch of its own.
        //: Measured light and dark in `prosepanel.js`.
        ".cm-finding-spelling:hover": {
          backgroundColor: "color-mix(in srgb, var(--error) 12%, transparent)",
          borderRadius: "3px",
        },
        ".cm-finding-style:hover": {
          backgroundColor: "color-mix(in srgb, var(--accent) 12%, transparent)",
          borderRadius: "3px",
        },
        ".cm-finding-repeat:hover": {
          backgroundColor: "color-mix(in srgb, var(--muted) 12%, transparent)",
          borderRadius: "3px",
        },
        ".cm-finding-grammar:hover": {
          backgroundColor: "color-mix(in srgb, var(--warn) 14%, transparent)",
          borderRadius: "3px",
        },
        ".cm-finding-ai:hover": {
          backgroundColor: "color-mix(in srgb, var(--accent) 12%, transparent)",
          borderRadius: "3px",
        },
        ".cm-finding-claim:hover": {
          backgroundColor: "color-mix(in srgb, var(--warn) 14%, transparent)",
          borderRadius: "3px",
        },
        ".cm-finding-access:hover": {
          backgroundColor: "color-mix(in srgb, var(--accent) 12%, transparent)",
          borderRadius: "3px",
        },
        ".cm-finding-link:hover": {
          backgroundColor: "color-mix(in srgb, var(--accent) 12%, transparent)",
          borderRadius: "3px",
        },
        ".cm-finding-spelling": {
          textDecoration: "underline wavy",
          textDecorationColor: "color-mix(in srgb, var(--error) 80%, transparent)",
        },
        ".cm-finding-style": {
          textDecoration: "underline wavy",
          textDecorationColor: "color-mix(in srgb, var(--accent) 80%, transparent)",
        },
        ".cm-finding-repeat": {
          textDecoration: "underline dotted",
          textDecorationThickness: "2px",
          textDecorationColor: "var(--muted)",
        },
        //: Grammar (Harper, INBOX 401): a double line, the shape Word gives
        //: grammar, in the warning ink, so it reads as neither a typo (wavy
        //: red) nor a style note (wavy accent).
        ".cm-finding-grammar": {
          textDecoration: "underline double",
          textDecorationColor: "var(--warn)",
        },
        //: Accessibility (INBOX 404): dashed, the one line shape left, in the
        //: accent, because it is about structure rather than a mistake.
        //: Check with AI (INBOX 410): dotted accent, a lighter mark than the
        //: style note's wavy accent, because a model's reading is a suggestion
        //: to consider rather than a rule broken.
        ".cm-finding-ai": {
          textDecoration: "underline dotted",
          textDecorationThickness: "2px",
          textDecorationColor: "color-mix(in srgb, var(--accent) 80%, transparent)",
        },
        //: A claim no note backs (Phase G): dotted in the warning ink, the model's
        //: dotted shape but not its accent, because it is about the notebook.
        ".cm-finding-claim": {
          textDecoration: "underline dotted",
          textDecorationThickness: "2px",
          textDecorationColor: "var(--warn)",
        },
        //: A claim a note supports: a thin quiet line, marked but not a warning.
        ".cm-finding-backed": {
          textDecoration: "underline solid",
          textDecorationThickness: "1px",
          textDecorationColor: "color-mix(in srgb, var(--muted) 60%, transparent)",
        },
        ".cm-finding-access": {
          textDecoration: "underline dashed",
          textDecorationThickness: "2px",
          textDecorationColor: "color-mix(in srgb, var(--accent) 80%, transparent)",
        },
        //: A link offer (VC5): a plain thin underline in the accent, the line a
        //: link wears, because this is where one could be, not a mistake.
        ".cm-finding-link": {
          textDecoration: "underline solid",
          textDecorationThickness: "1px",
          textUnderlineOffset: "3px",
          textDecorationColor: "color-mix(in srgb, var(--accent) 80%, transparent)",
        },
      },
      { dark }
    );
  }

  Object.assign(window, { docCmTheme });
})();
