// documents-callouts.js: callout folds, the block bar and the heading fold
// (split out of documents.js, audit 1031 DC13 remainder).
//
// What is here: the fold services (`docHeadingFold`, `docCalloutFold`), the
// preview's hover bar that moves, edits or deletes a top-level block
// (`docBlockBar*`, `docBlockEdit`, `docBlockDelete`), the callout kind menu and
// fold toggles, the table-of-contents jump and the footnote jump. What stayed
// in documents.js: `docCmExtensions`, which names the two fold services from
// inside a function, and `docResetDocument`.
//
// **Loaded in the Library bundle, right after documents.js**, not before it
// like the other pieces: this file's top level registers the preview's
// `mouseover` listener through `docListen` and reads `$("doc-preview")`, both
// of which documents.js defines. documents.js reads nothing from here at load
// (every call is inside a function). One closure; what other files call is the
// `Object.assign` at the foot.
(() => {
  //: **Folding on headings.** The markdown parser gives fold ranges for fenced
  //: code and lists; a *section* is the unit anyone actually wants to collapse
  //: in a long document, and nothing in the grammar calls it one. So this is a
  //: fold service rather than a syntax property: from the end of a heading line
  //: to just before the next heading at the same level or above, which is what
  //: every outliner means by folding a section.
  //:
  //: Only for markdown. In a `.py` file a `#` line is a comment, and folding
  //: from one comment to the next would be nonsense.
  //: **A callout is foldable when its marker says so**, `> [!note]-` (start
  //: folded) or `> [!note]+` (start open), which is the syntax Obsidian uses and
  //: the one GitHub and Typora also read. The range folded is everything after
  //: the first line to the end of the blockquote, so the kind's own label stays
  //: on screen as the thing you click to get the rest back.
  //:
  //: Written against the document rather than the syntax tree for the same
  //: reason the renderer's callout branch is: `[!note]` is not markdown, it is a
  //: convention inside a blockquote, and the tree has no node for it.
  function docCalloutFoldRange(state, line) {
    if (!/^\s*>\s*\[![A-Za-z]+\][-+]/.test(line.text)) return null;
    let last = line.number;
    for (let number = line.number + 1; number <= state.doc.lines; number += 1) {
      if (!/^\s*>/.test(state.doc.line(number).text)) break;
      last = number;
    }
    if (last === line.number) return null;
    return { from: line.to, to: state.doc.line(last).to };
  }

  function docCalloutFold(CM) {
    return CM.language.foldService.of((state, lineStart) => {
      if (!docFileType().previewable) return null;
      return docCalloutFoldRange(state, state.doc.lineAt(lineStart));
    });
  }

  //: Whether this callout is folded *now*, which is what decides which way its
  //: chevron points. The marker in the text says where it started, not where it
  //: is.
  function docCalloutFolded(state, line) {
    const CM = window.CM6;
    if (!CM || typeof CM.language.foldedRanges !== "function") return false;
    const range = docCalloutFoldRange(state, line);
    if (!range) return false;
    let folded = false;
    CM.language.foldedRanges(state).between(range.from, range.to, () => {
      folded = true;
      return false;
    });
    return folded;
  }

  //: The click on a callout's label. Dispatches the fold itself rather than
  //: calling `toggleFold`, whose job is the *cursor's* fold: a click on a
  //: callout three screens from the caret would otherwise fold whatever the
  //: caret happened to be inside.
  //: A contents entry's jump: the n-th heading with this text and level, as
  //: `mdTocEntries` counted them, gets the caret and the top of the view.
  function docTocJump(view, entry) {
    const CM = window.CM6;
    if (!CM || !view) return;
    const doc = view.state.doc;
    let fenced = false;
    for (let n = 1; n <= doc.lines; n += 1) {
      const line = doc.line(n);
      if (/^[ \t]*(?:```|~~~)/.test(line.text)) fenced = !fenced;
      if (fenced) continue;
      const heading = /^(#{1,6})\s+(.*\S)\s*$/.exec(line.text);
      if (!heading || heading[1].length !== entry.level) continue;
      if (heading[2].replace(/\s+#+$/, "") !== entry.text) continue;
      view.dispatch({
        selection: { anchor: line.to },
        effects: CM.view.EditorView.scrollIntoView(line.from, { y: "start", yMargin: 24 }),
      });
      view.focus();
      return;
    }
  }

  //: **Change a callout's kind or folding from the block itself** (INBOX 421
  //: b). `at` is any position on the callout's first line; the rewrite touches
  //: only the `[!kind]` marker (`calloutRewriteHead`), through the surface, so
  //: it is one undo step and the autosave sees it like a keystroke.
  function docSetCalloutHead(at, kind, fold) {
    const box = docSurface();
    if (!box || typeof calloutRewriteHead !== "function") return;
    const line = box.lineAt(Math.max(0, at));
    const next = calloutRewriteHead(line.text, kind, fold);
    if (next === line.text) return;
    box.replaceRange(line.from, line.to, next);
    if (!box.isDocument) return;
    markDocDirty();
    renderDocPreview();
  }

  //: **The block bar: act on a block from where it is drawn** (INBOX 421 b:
  //: "a block hover toolbar (change kind, fold, delete)"). In the Read and
  //: Split views, the rendered block under the pointer gets a small bar at its
  //: top right: the kind (a callout's, as its own icon tile, opening the kinds
  //: and folding menu), Edit (the block's first line, in the editor), Copy (its
  //: markdown) and Delete (with Undo). Everything it does is written to the
  //: text through the surface, so it is the editor's own undo step as well.
  //:
  //: Found from the block's `data-src-line` (a line of the rendered string,
  //: `docRenderFlow`) less `docPreviewLineShift` (the title and properties the
  //: preview adds or leaves out), and **checked against the text before
  //: anything is written**: a callout's first line has to be a callout head.
  //: The preview has no drag handle: reordering by drag needs a drop model for
  //: it, which is not cheap. Live has one (`docLiveExtensions.dragHandle`).
  //: Pointer only: a phone has no hover, and its Live view carries the kind
  //: button on the callout itself.
  let docBlockBarFor = null;
  let docBlockBarHide = 0;

  function docBlockBarEl() {
    let bar = document.getElementById("doc-block-bar");
    if (bar) return bar;
    bar = document.createElement("div");
    bar.id = "doc-block-bar";
    bar.className = "doc-block-bar hidden";
    bar.setAttribute("role", "toolbar");
    bar.setAttribute("aria-label", "This block");
    bar.addEventListener("mouseenter", () => clearTimeout(docBlockBarHide));
    bar.addEventListener("mouseleave", () => docBlockBarSoon());
    document.body.appendChild(bar);
    return bar;
  }

  function docBlockBarSoon() {
    clearTimeout(docBlockBarHide);
    docBlockBarHide = setTimeout(docBlockBarClose, 250);
  }

  function docBlockBarClose() {
    clearTimeout(docBlockBarHide);
    docBlockBarFor = null;
    document.getElementById("doc-block-bar")?.classList.add("hidden");
  }

  //: The source lines a rendered block came from, as [first, last] (0-based
  //: lines of `docText()`), trailing blank lines left out.
  function docBlockLines(block) {
    const preview = $("doc-preview");
    const stamp = Number(block.dataset.srcLine);
    if (!preview || !Number.isFinite(stamp)) return null;
    const lines = docText().split("\n");
    const first = stamp - docPreviewLineShift;
    if (first < 0 || first >= lines.length) return null;
    const blocks = [...preview.children].filter((b) => b.dataset.srcLine !== undefined);
    const next = blocks[blocks.indexOf(block) + 1];
    let last = next ? Number(next.dataset.srcLine) - docPreviewLineShift - 1 : lines.length - 1;
    last = Math.min(Math.max(first, last), lines.length - 1);
    while (last > first && !lines[last].trim()) last -= 1;
    return { first, last, lines };
  }

  function docLineOffset(lines, index) {
    let at = 0;
    for (let i = 0; i < index; i += 1) at += lines[i].length + 1;
    return at;
  }

  function docBlockBarShow(block) {
    if (docBlockBarFor === block) return;
    const span = docBlockLines(block);
    if (!span) return;
    const bar = docBlockBarEl();
    docBlockBarFor = block;
    bar.replaceChildren();
    const isCallout = block.classList.contains("callout");
    const head = isCallout && typeof mdCalloutHead === "function"
      ? mdCalloutHead(span.lines[span.first].replace(/^\s*>\s?/, ""))
      : null;
    if (head) {
      const meta = CALLOUT_KINDS[head.kind] || CALLOUT_KINDS.note;
      const kind = smallButton(meta.icon, `Change the kind: ${meta.label}`, (event) => {
        const box = event.currentTarget.getBoundingClientRect();
        const lineStart = docLineOffset(span.lines, span.first);
        openMenuAtPoint(
          calloutMenuItems(head.kind, head.fold, (k, fold) => docSetCalloutHead(lineStart, k, fold)),
          "Callout kind",
          box.left,
          box.bottom + 4
        );
      });
      kind.classList.add("doc-block-kind", `doc-block-kind-${head.kind}`);
      bar.appendChild(kind);
    }
    bar.appendChild(smallButton("ph:pencil-simple", "Edit this block", () => docBlockEdit(span)));
    bar.appendChild(smallButton("ph:copy", "Copy this block's markdown", (event) => {
      copyToClipboard(span.lines.slice(span.first, span.last + 1).join("\n"), event.currentTarget);
    }));
    bar.appendChild(smallButton("ph:trash", "Delete this block", () => docBlockDelete(span)));
    bar.classList.remove("hidden");
    const rect = block.getBoundingClientRect();
    const host = $("doc-preview").getBoundingClientRect();
    const width = bar.offsetWidth;
    const left = Math.min(rect.right, host.right) - width;
    const top = Math.max(host.top, rect.top) - bar.offsetHeight / 2;
    docPlaceFixed(bar, Math.max(host.left, left), Math.max(4, top));
  }

  function docBlockEdit(span) {
    docBlockBarClose();
    if (docView === "rendered") setDocView("live");
    const box = docSurface();
    if (!box) return;
    const at = docLineOffset(docText().split("\n"), span.first);
    requestAnimationFrame(() => {
      box.focus();
      box.setSelectionRange(at, at);
      if (typeof box.scrollIntoView === "function") box.scrollIntoView(at);
    });
  }

  function docBlockDelete(span) {
    docBlockBarClose();
    const box = docSurface();
    if (!box) return;
    const lines = docText().split("\n");
    //: The block and the blank line after it, so the paragraphs either side do
    //: not end up glued together or two blank lines apart.
    let last = span.last;
    if (last + 1 < lines.length && !lines[last + 1].trim()) last += 1;
    const from = docLineOffset(lines, span.first);
    const to = Math.min(docText().length, docLineOffset(lines, last) + lines[last].length + 1);
    const removed = docText().slice(from, to);
    box.replaceRange(from, to, "");
    markDocDirty();
    renderDocPreview();
    toastAction("Block deleted.", "Undo", () => {
      const now = docSurface();
      if (!now) return;
      now.replaceRange(from, from, removed);
      markDocDirty();
      renderDocPreview();
    });
  }

  //: The top-level block under the pointer, in the preview only.
  docListen("mouseover", (event) => {
    const preview = $("doc-preview");
    if (!preview || preview.classList.contains("hidden")) return;
    if (!(event.target instanceof Element)) return;
    if (event.target.closest("#doc-block-bar")) return;
    if (!preview.contains(event.target)) {
      if (docBlockBarFor) docBlockBarSoon();
      return;
    }
    if (window.matchMedia("(hover: none)").matches) return;
    let block = event.target;
    while (block && block.parentElement !== preview) block = block.parentElement;
    if (!block || block.dataset.srcLine === undefined) return;
    clearTimeout(docBlockBarHide);
    docBlockBarShow(block);
  });
  $("doc-preview")?.addEventListener("scroll", docBlockBarClose);

  function docCalloutKindMenu(at, x, y) {
    const box = docSurface();
    if (!box || typeof openMenuAtPoint !== "function") return;
    const head = typeof mdCalloutHead === "function"
      ? mdCalloutHead(box.lineAt(Math.max(0, at)).text.replace(/^\s*>\s?/, ""))
      : null;
    if (!head) return;
    openMenuAtPoint(
      calloutMenuItems(head.kind, head.fold, (kind, fold) => docSetCalloutHead(at, kind, fold)),
      "Callout kind",
      x,
      y
    );
  }

  function docToggleCalloutFold(at) {
    const CM = window.CM6;
    const view = docCmView;
    if (!CM || !view) return;
    const line = view.state.doc.lineAt(Math.max(0, Math.min(at, view.state.doc.length)));
    const range = docCalloutFoldRange(view.state, line);
    if (!range) return;
    let folded = null;
    CM.language.foldedRanges(view.state).between(range.from, range.to, (from, to) => {
      if (!folded) folded = { from, to };
      return false;
    });
    view.dispatch({
      effects: folded ? CM.language.unfoldEffect.of(folded) : CM.language.foldEffect.of(range),
    });
  }

  //: **Every `[!kind]-` callout in the document, folded, once.** The marker is a
  //: statement about how the document opens, so it is applied when the document
  //: opens and never again: re-applying it on every repaint would make a
  //: callout somebody opened close itself under their hands.
  function docFoldMarkedCallouts() {
    const CM = window.CM6;
    const view = docCmView;
    if (!CM || !view || !docFileType().previewable) return;
    const effects = [];
    for (let number = 1; number <= view.state.doc.lines; number += 1) {
      const line = view.state.doc.line(number);
      if (!/^\s*>\s*\[![A-Za-z][\w-]*\]-/.test(line.text)) continue;
      const range = docCalloutFoldRange(view.state, line);
      if (range) effects.push(CM.language.foldEffect.of(range));
    }
    if (effects.length) view.dispatch({ effects });
  }

  //: A footnote reference goes to its definition, which is the whole point of
  //: the raised number: in a long document the text it refers to is hundreds of
  //: lines away and scrolling for it is what stops people using footnotes.
  function docGoToFootnote(id) {
    const surface = docSurface();
    if (!surface) return;
    const text = surface.text;
    const marker = `\n[^${id}]:`;
    let at = text.startsWith(`[^${id}]:`) ? 0 : text.indexOf(marker);
    if (at > 0) at += 1;
    if (at < 0) {
      toast(`Footnote ${id} has no text yet`);
      return;
    }
    surface.focus();
    surface.setSelectionRange(at, at);
  }

  function docHeadingFold(CM) {
    return CM.language.foldService.of((state, lineStart, lineEnd) => {
      if (!docFileType().previewable) return null;
      const line = state.doc.lineAt(lineStart);
      const here = /^(#{1,6})\s/.exec(line.text);
      if (!here) return null;
      const level = here[1].length;
      for (let number = line.number + 1; number <= state.doc.lines; number += 1) {
        const next = state.doc.line(number);
        const found = /^(#{1,6})\s/.exec(next.text);
        //: The same level or shallower ends the section. A deeper heading is
        //: part of it, which is why this is not simply "the next heading".
        if (found && found[1].length <= level) {
          return next.from - 1 > lineEnd ? { from: lineEnd, to: next.from - 1 } : null;
        }
      }
      return state.doc.length > lineEnd ? { from: lineEnd, to: state.doc.length } : null;
    });
  }

  //: The file's whole surface: what documents.js and documents-cm.js call.
  Object.assign(window, { docCalloutFold, docCalloutFolded, docTocJump, docBlockBarClose, docCalloutKindMenu, docToggleCalloutFold, docFoldMarkedCallouts, docGoToFootnote, docHeadingFold });
})();
