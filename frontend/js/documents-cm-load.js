// documents-cm-load.js: fetching the editor engine, its language and search helpers, and the history per document.
// Moved out of documents.js whole (L335) and wrapped: only what other files call goes on `window`; nothing here runs at load.
(() => {
  //: State that moved here from documents.js (L-documents-118).
  //: True once loading or mounting has failed. Checked before every attempt, so
  //: a broken bundle costs one request rather than one per document opened.
  let docCmBroken = false;
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
  function docRedo() {
    const CM = window.CM6;
    if (docCmView && CM) return CM.commands.redo(docCmView) && (toast("Redone: last change on this document", "info"), true);
    docSurface()?.focus();
    return document.execCommand("redo");
  }
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
    //: Returns whether the engine is warming, so a caller outside this closure can chain on it.
    if (docWarmed || link.saveData || (navigator.deviceMemory || 8) <= 2) return docWarmed;
    docWarmed = true;
    const idle = window.requestIdleCallback || ((fn) => setTimeout(fn, 400));
    idle(() => {
      loadCodeMirror();
      for (const href of DOC_GRAMMAR_FILES.slice(1)) {
        const el = Object.assign(document.createElement("link"), { rel: "prefetch", href });
        document.head.appendChild(el);
      }
    }, { timeout: 2000 });
    return true;
  }
  //: The in-flight load, so two documents opened quickly do not inject two
  //: script tags. Reset to null on failure, so a later attempt can retry after
  //: whatever went wrong (a dropped connection on first paint, most likely).
  let docCmLoad = null;
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
    //: `drawSelection`, held only for several ranges or an unfocused selection (L342).
    select: null,
    //: Drawn only while the browser cannot draw it (L342): several ranges, or a
    //: selection kept while the focus is elsewhere (the find bar's match).
    //: Otherwise the native caret and selection, in the same colours. `part` is
    //: the view's own compartment: the document's, a note box's, the split view's.
    drawSelectionWhenNeeded(CM, part) {
      const drawn = CM.view.drawSelection();
      const drawWanted = (sel, focused) => sel.ranges.length > 1 || (!focused && !sel.main.empty);
      let drawFocused = false;
      const drawSwap = (state, sel, focused) => {
        const want = drawWanted(sel, focused);
        return want === (part.get(state) === drawn) ? null : part.reconfigure(want ? drawn : []);
      };
      return [
        part.of([]),
        CM.state.EditorState.transactionExtender.of((tr) => {
          if (!tr.selection) return null;
          const effect = drawSwap(tr.startState, tr.newSelection, drawFocused);
          return effect ? { effects: effect } : null;
        }),
        CM.view.EditorView.focusChangeEffect.of((state, focusing) => {
          drawFocused = focusing;
          return drawSwap(state, state.selection, focusing);
        }),
      ];
    },
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
  const docHistories = new Map();
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

  //: The file's surface: what other files call (L335).
  Object.assign(window, { docRedo, warmDocumentEngine, loadCodeMirror, docCmParts, docCmLanguageFor, docTableGridRules, docListGuides, docCmSearchCount, docCmHighlight, docHistories, docResetDocument, docHistoryPersist, docCmViewShown });

  //: These lets keep their bare names for the other files as window accessors, so one store answers every reader and writer (L-documents-118).
  for (const [name, get, set] of [
    ["docCmBroken", () => docCmBroken, (value) => { docCmBroken = value; }],
    ["docHistoryOwner", () => docHistoryOwner, (value) => { docHistoryOwner = value; }],
  ]) Object.defineProperty(window, name, { get, set, configurable: true });

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
})();
