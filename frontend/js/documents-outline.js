// documents-outline.js: the breadcrumb row and the outline's folding and
// filter model (split out of documents.js, audit 1031 DC13 remainder).
//
// What is here: the trail of headings a line sits under (`docHeadingTrail`,
// bracketed by `DOC-CRUMBS-BEGIN`/`END`), the row that draws it
// (`renderDocCrumbs`), the folds and filter the outline keeps
// (`docOutlineFolds`, `docOutlineVisibility`) and the heading scan and section
// range both read (`docScanHeadings`, `docSectionRange`). What stayed in
// documents.js: the outline's own rebuild and its list, and `docOutlineState`,
// the two values the rebuild and the trail share.
//
// **Loaded in the Library bundle, before documents.js**, the way
// documents-props.js is: this file's own top level declares functions and
// constants and reads nothing from documents.js. One closure; what other files
// call is the `Object.assign` at the foot.
(() => {
  // A table of contents built from the document's own headings. Past a couple
  // of screens the scrollbar stops being a way to navigate a document.
  // =============================================================================
  // Breadcrumbs: where the caret is, in the document's own structure
  // =============================================================================
  //
  // DOCUMENTS_PLAN Phase 4 item 3. The outline answers "what is in this
  // document"; this answers "where am I in it", which is the question a reader
  // two screens into a section cannot answer from the text in front of them.
  // Obsidian has neither; VS Code, IntelliJ and Word all do, and all three put
  // it in the same place: one line above the writing, not in the chrome.
  //
  // It is a trail rather than a label because the useful part is the *ancestry*:
  // "Sampling" on its own says nothing, and "Method > Sampling" says which of
  // the three sections called Sampling you are in.

  // DOC-CRUMBS-BEGIN

  //: The headings a line sits under, as indexes into `headings`, outermost
  //: first. `[]` for a line above the first heading, which is a real position in
  //: most documents (the paragraph before the first `#`) rather than an error.
  //:
  //: Walked forward with a stack rather than searched backwards per level: a
  //: backwards search has to ask "is there a level 2 between here and the level
  //: 1" for every level, which is the shape that gets the skipped-level case
  //: wrong. A document that goes `#` then `###` has a two-deep trail, not a
  //: three-deep one with a hole in it, and the stack gives that for free.
  function docHeadingTrail(headings, line) {
    const trail = [];
    const list = headings || [];
    const at = Number.isFinite(line) ? line : 0;
    for (let index = 0; index < list.length; index += 1) {
      const heading = list[index];
      //: `>` rather than `>=`: the caret *on* a heading's own line is inside
      //: that heading, which is what a writer editing the heading means.
      if (heading.line > at) break;
      while (trail.length && list[trail[trail.length - 1]].level >= heading.level) trail.pop();
      trail.push(index);
    }
    return trail;
  }

  // DOC-CRUMBS-END

  //: The row, and its one-time wiring. It is in index.html (see the markup
  //: there for why), so this is a lookup rather than a build; what is done once
  //: here is the edge-fade, whose listeners app.js only attaches to the strips
  //: that exist when it boots, before this tab has ever been opened.
  let docCrumbsWired = false;

  function docCrumbsEl() {
    const nav = $("doc-crumbs");
    if (!nav || docCrumbsWired) return nav;
    docCrumbsWired = true;
    nav.addEventListener("scroll", () => window.syncEdgeFade?.(nav), { passive: true });
    if (typeof ResizeObserver !== "undefined") {
      //: The half that actually matters here: a trail's width changes when the
      //: caret moves into a deeper section, with no window resize to hang a
      //: recalculation off, and a strip whose fade is only recomputed on resize
      //: keeps whichever mask it had when it was last measured.
      //: Kept (audit 1028 D37), and let go before a second one is made, so wiring the
      //: strip again (a rebuilt nav) cannot leave two watching it.
      docCrumbsEl.resize?.disconnect();
      docCrumbsEl.resize = new ResizeObserver(() => window.syncEdgeFade?.(nav));
      docCrumbsEl.resize.observe(nav);
    }
    return nav;
  }

  function renderDocCrumbs(line) {
    const nav = docCrumbsEl();
    if (!nav) return;
    const list = nav.firstElementChild;
    const headings = docOutlineState.headings;
    //: A document with no headings has nothing to say here, and a row that is
    //: present and empty is a strip of blank space above the writing.
    nav.classList.toggle("hidden", !headings.length);
    if (!headings.length) {
      list.replaceChildren();
      docOutlineState.crumbsKey = "";
      return;
    }
    //: The document itself is the first crumb, and it jumps to the top. Phase
    //: 1's own sketch of the header reads `Documents > Design system notes`, so
    //: the trail starting at the document is the shape this plan already chose;
    //: it also keeps the row the same height whether or not the caret is under
    //: a heading yet, which is what stops it from jumping as you write.
    //: Drawn as a "Top" mark, not the title: the title sits in the dock just
    //: above, and the same words twice in 40px read as a stutter (the density
    //: pass, 2026-10-03).
    const crumbs = [{ text: "Top", line: 0 }];
    for (const index of docHeadingTrail(headings, line)) crumbs.push(headings[index]);
    const key = crumbs.map((crumb) => `${crumb.line}:${crumb.text}`).join("\u0000");
    if (key === docOutlineState.crumbsKey) return;
    docOutlineState.crumbsKey = key;
    list.replaceChildren();
    crumbs.forEach((crumb, index) => {
      const li = document.createElement("li");
      const button = document.createElement("button");
      button.type = "button";
      button.className = "linklike doc-crumb";
      if (index) button.textContent = crumb.text;
      else {
        const icon = document.createElement("i");
        icon.className = "ph ph-arrow-line-up ph-lead";
        icon.setAttribute("aria-hidden", "true");
        button.append(icon, "Top");
      }
      button.title = index ? `Jump to \u201c${crumb.text}\u201d` : "Jump to the top of the document";
      //: The last crumb is where you are, and `aria-current="location"` is how
      //: the recipe index says a row says so: the weight it is drawn in hangs
      //: off this attribute in CSS, so the mark and its announcement are one
      //: thing and cannot drift apart.
      if (index === crumbs.length - 1) button.setAttribute("aria-current", "location");
      button.addEventListener("click", () => jumpToDocLine(crumb.line));
      li.appendChild(button);
      list.appendChild(li);
    });
    //: After the row is built, not before: the fade is a measurement of
    //: `scrollWidth` against `clientWidth`, and both are the previous trail's
    //: until the new buttons are in the document. After the frame's layout,
    //: too (INBOX 1530 c): measured at once it forced the outline's rows,
    //: written a moment before, to be laid out inside the open (2 to 10 ms).
    if (renderDocCrumbs.fading) return;
    renderDocCrumbs.fading = true;
    afterFrames(() => setTimeout(() => {
      renderDocCrumbs.fading = false;
      window.syncEdgeFade?.(nav);
    }), 1);
  }

  //: The caret's line, 0-based, for the callers that want the trail but do not
  //: already hold a set of caret stats.
  function docCaretLine() {
    const box = docActiveBox();
    if (!box) return 0;
    try {
      return box.lineAt(box.selection().from).number - 1;
    } catch {
      //: A surface mid-teardown (the engine swapping in under the textarea) can
      //: answer neither, and a breadcrumb is not worth an exception in the
      //: middle of a document open.
      return 0;
    }
  }

  //: **Folding, and the filter box** (DOCUMENTS_PLAN Phase 4 item 3, and
  //: OPEN.md's "The outline is headings only, and it does not fold").
  //:
  //: **Folds are kept per document, by heading rather than by line.** A line
  //: number is the obvious key and the wrong one: it changes every time a
  //: paragraph is added above, so a folded section would unfold itself, or
  //: worse, some other section would be folded in its place, the moment anybody
  //: wrote anything. The heading's own level and text survive an edit anywhere
  //: else in the document, which is what a remembered fold has to survive to be
  //: worth remembering. Two headings with the same words at the same level fold
  //: together, which is a fair reading of "the same section" and the only
  //: ambiguity this key has.
  //:
  //: In `localStorage` because it is a per-viewer convenience about how a panel
  //: is drawn, not something about the document: a fold written into the file
  //: would travel to everyone who opens it and would show up in its diff.
  const DOC_OUTLINE_FOLD_KEY = "doc-outline-folds";

  //: Ten. Below it the whole outline is on screen and a filter box is a control
  //: that costs a row and saves nothing; past it the list is longer than the
  //: panel and hunting starts. OPEN.md puts the line at "two screens of
  //: headings", which in this sidebar's own measurement (`#doc-outline-wrap` at
  //: 85px with the list scrolling inside it) arrives well before twenty.
  const DOC_OUTLINE_FILTER_FROM = 10;

  function docOutlineFoldStore() {
    //: Keyed by document, so folding one document's sections says nothing about
    //: another's. A document with no id yet (never saved) gets no store rather
    //: than a shared one.
    const id = typeof currentDoc !== "undefined" && currentDoc ? currentDoc.id : null;
    return id ? `${DOC_OUTLINE_FOLD_KEY}:${id}` : "";
  }

  function docOutlineFolds() {
    const store = docOutlineFoldStore();
    if (!store) return new Set();
    try {
      const raw = prefs.json(store, []);
      return new Set(Array.isArray(raw) ? raw.filter((k) => typeof k === "string") : []);
    } catch {
      //: Private mode, or a value written by an older shape. An outline that
      //: draws unfolded is right; one that throws on open is not.
      return new Set();
    }
  }

  function docOutlineSetFolds(folds) {
    const store = docOutlineFoldStore();
    if (!store) return;
    try {
      prefs.set(store, JSON.stringify([...folds]));
    } catch {
      //: Nothing to do and nothing worth saying: the fold still applies to the
      //: outline on screen, it just will not survive a reload.
    }
  }

  function docOutlineFoldKey(heading) {
    return `${heading.level}:${heading.text}`;
  }

  function docOutlineFilterText() {
    return ($("doc-outline-filter")?.value || "").trim().toLowerCase();
  }

  //: Which rows are drawn, as one pass over the headings, because folding and
  //: filtering are two answers to the same question and a row cannot be given
  //: to both. **Filtering wins outright**: a search that hides its own matches
  //: inside a folded section is a search that reports nothing and is right about
  //: nothing, so while there is a needle the folds are ignored entirely.
  //:
  //: Returns, per heading: whether it is drawn, and whether it can fold (which
  //: is a fact about the document, not about the filter, so it is the same
  //: either way and the caret does not appear and disappear as you type).
  function docOutlineVisibility(headings, needle, folds) {
    const rows = headings.map((heading, index) => {
      const next = headings[index + 1];
      return { shown: true, foldable: Boolean(next && next.level > heading.level) };
    });
    if (needle) {
      headings.forEach((heading, index) => {
        rows[index].shown = heading.text.toLowerCase().includes(needle);
      });
      return rows;
    }
    //: A fold hides the run of deeper headings under it, and a fold inside a
    //: folded section needs no second pass: the outer one already covers every
    //: row the inner one would.
    let hideUnder = -1;
    headings.forEach((heading, index) => {
      if (hideUnder >= 0 && heading.level > hideUnder) {
        rows[index].shown = false;
        return;
      }
      hideUnder = -1;
      if (rows[index].foldable && folds.has(docOutlineFoldKey(heading))) hideUnder = heading.level;
    });
    return rows;
  }

  //: **The headings in a piece of markdown**, pulled out of `renderDocOutline`
  //: so the reorder (Phase 4 item 3) can ask the *current* text where a section
  //: starts and ends. The outline's own list is rebuilt on a pause in typing, so
  //: acting on its line numbers a keystroke later would move the wrong run of
  //: lines; scanning again costs one pass and cannot be stale.
  function docScanHeadings(text) {
    const headings = [];
    let inFence = false;
    const lines = String(text == null ? "" : text).split("\n");
    lines.forEach((line, index) => {
      // A "# " inside a code fence is code, not a heading.
      if (/^(```|~~~)/.test(line.trim())) inFence = !inFence;
      if (inFence) return;
      const match = /^(#{1,4})\s+(.*\S)\s*$/.exec(line);
      if (match) {
        headings.push({ level: match[1].length, text: match[2], line: index });
        return;
      }
      //: **The setext form too**, `Title` on one line with `=====` or `-----`
      //: under it. The editor renders these as headings (`docLivePlugin`'s
      //: heading branch matches `SetextHeading1` and `2`), so an outline that
      //: skipped them showed "2" over a document with three headings in it, one
      //: of them the largest thing on the page. Recognised on the *underline*,
      //: because that is the line that decides: `Title` on its own is a
      //: paragraph until the row of `=` arrives.
      //:
      //: Guards, and each one is a real document: the line above has to have
      //: text in it (a rule with a blank line above it is a `<hr>`, not a
      //: heading), it must not already be an ATX heading or a list item or a
      //: quote (all of which a `---` under them would not turn into a heading),
      //: and the previous line must not itself have been consumed as one.
      const underline = /^\s*(=+|-{2,})\s*$/.exec(line);
      if (!underline || index === 0) return;
      const above = lines[index - 1];
      if (!above || !above.trim()) return;
      if (/^\s*(#{1,6}\s|[-*+]\s|\d+[.)]\s|>|\|)/.test(above)) return;
      if (headings.length && headings[headings.length - 1].line === index - 1) return;
      headings.push({
        level: underline[1][0] === "=" ? 1 : 2,
        text: above.trim(),
        line: index - 1,
      });
    });
    return headings;
  }

  //: **A section is its heading and everything under it**, down to the next
  //: heading at the same level or shallower: the run of lines a reader means
  //: when they drag "Results" somewhere else. `lineCount` rather than the text
  //: again, because every caller has already split it.
  function docSectionRange(headings, index, lineCount) {
    const heading = headings[index];
    let end = lineCount;
    for (let next = index + 1; next < headings.length; next += 1) {
      if (headings[next].level <= heading.level) {
        end = headings[next].line;
        break;
      }
    }
    return { from: heading.line, to: end };
  }

  //: The file's whole surface: what documents.js and documents-cm.js call.
  Object.assign(window, { renderDocCrumbs, docCaretLine, DOC_OUTLINE_FILTER_FROM, docOutlineFolds, docOutlineSetFolds, docOutlineFoldKey, docOutlineFilterText, docOutlineVisibility, docScanHeadings, docSectionRange });
})();
