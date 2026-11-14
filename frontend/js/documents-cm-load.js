// documents-cm-load.js: fetching the editor engine, its language and search helpers, and the history per document.
// Moved out of documents.js whole (L335) and wrapped: only what other files call goes on `window`; nothing here runs at load.
(() => {
  function docRedo() {
    const CM = window.CM6;
    if (docCmView && CM) return CM.commands.redo(docCmView) && (toast("Redone: last change on this document", "info"), true);
    docSurface()?.focus();
    return document.execCommand("redo");
  }
  const DOC_CM_BUNDLE = "/vendor/codemirror/codemirror.min.js";
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
  Object.assign(window, { docRedo, warmDocumentEngine, loadCodeMirror, docCmParts, docCmLanguageFor, docTableGridRules, docListGuides, docCmSearchCount, docCmHighlight, docHistories, docResetDocument, docHistoryPersist, docCmViewShown, docWatchLock });
})();
