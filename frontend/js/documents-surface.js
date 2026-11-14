// documents-surface.js: the editing surface behind one adapter (textarea or CodeMirror), opening a document, the list, and remembering where you were.
// Moved out of documents.js whole (L-documents-117) and wrapped: only what other files call goes on `window`.
(() => {
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


  //: The fallback textarea itself. Named rather than looked up at each site
  //: because a few things genuinely are about the *element*: its placeholder,
  //: its disabled flag, the `doc-content-code` class and its line-number
  //: column. Everything about the document's *text* goes through the surface
  //: instead.
  function docBoxEl() {
    return $("doc-content");
  }


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
    if (docFactsPending() && currentDoc) runDocFacts();
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
            if ((await deleteDocumentWithUndo(doc, true).catch((e) => toast(e.message, true))) === false) return;
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

  //: The file's surface: what other files call (L-documents-117).
  Object.assign(window, { docBoxEl, docSetPlaceholder, docPlaceholderFor, textareaSurface, cmSurface, docSurfaceChanged, docSurface, docStr, docText, docSurfaceById, docEventFromCm, docListen, asSurface, setDocView, loadDocuments, renderDocList, showNoDocument, openDocument, docRememberPositionNow, docRememberPosition, keepDocEditLocally, forgetDocEditLocally });
})();
