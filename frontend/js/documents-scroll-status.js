// documents-scroll-status.js: the split view's scroll sync, and the status bar (caret, counts, reading time) with the facts pass behind it.
// Moved out of documents.js whole and wrapped: only what other files call goes on `window`; nothing here runs at load beyond declaring.
(() => {
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

  //: A getter, because an exported `let` would be copied at load and never change after it.
  const docFactsPending = () => docFactsStale;

  //: The file's surface: what other files call.
  Object.assign(window, { syncDocScroll, wireDocSurfaceScroll, wireDocScrollSync, docFactsPending, docSetStatusText, renderDocCaret, DOC_COUNTS_TITLE_PROSE, renderDocCounts, renderDocStatusBar, runDocFacts, scheduleDocFacts });
})();
