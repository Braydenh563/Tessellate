// documents-comments.js: `%%remark%%` comments and the panel that lists them
// (split out of documents.js, audit 1031 DC13 remainder).
//
// What is here: the pure comment model (`docCommentsParse`, `docCommentStrip`,
// `docCommentFootnotes`, `docCommentResolveEdit`, bracketed by
// `DOC-COMMENT-BEGIN`/`END` for `tests/test_doc_comments.py`), the Outline
// tab's Comments section (`renderDocComments` and its row, jump and resolve
// actions) and `docAnnotateSelection`. What stayed in documents.js:
// `docPrintComments` (a flag documents-export.js sets while a print is being
// prepared, read by `renderDocPreview`), `docText`, `docSurface` and the
// dispatch the panel's actions write through.
//
// **Loaded in the Library bundle, before documents.js**, the way
// documents-props.js is: documents.js, documents-cm.js and documents-prose.js
// call in here only from inside functions, while this file's own top level
// declares and reads nothing from them. One closure; what other files call is
// the `Object.assign` at the foot.
(() => {
  // =============================================================================
  // Comments and annotations (DOCUMENTS_PLAN Phase 5 item 1)
  // =============================================================================
  //
  // **The syntax is two constructs this editor already wrote, joined.**
  // `==highlighted text==` has rendered as a highlight since Phase 2 and
  // `%%a note to self%%` has been in the Insert menu just as long, kept in the
  // file and never rendered. A comment is the pair: the highlight says *which
  // words* and the `%%…%%` immediately after it says *what about them*. Nothing
  // new goes into the file, so a document written here still opens in Obsidian
  // (same two constructs, same meaning) and a document written there arrives
  // with its comments already understood.
  //
  // **A bare `%%…%%` is still a comment**, on the line it sits in rather than on
  // a span of words: that is what the Insert menu has always inserted, and a
  // feature that made yesterday's notes to self invisible to the panel listing
  // comments would be a feature that lost them.
  //
  // **Resolving removes the comment from the document**, and unwraps the
  // highlight it was attached to, leaving the words themselves. The alternative
  // (a resolved marker left in the text) was considered and refused: it is a
  // second state to render, a second thing for Live and Read to agree about, and
  // a file whose `%%` spans mean two different things depending on a flag
  // somewhere else. What makes removal safe here is that this editor already
  // keeps every version of a document (`/documents/{id}/revisions`) and the
  // engine's own undo covers the keystroke, so a resolve is recoverable twice
  // over.
  //
  // **In an export, a comment becomes a footnote** (`docCommentFootnotes`), so a
  // PDF handed to somebody carries the remarks rather than dropping them. In
  // Read and Split they are hidden: the document as it reads is the document
  // without the margin notes in it.
  //
  // The model is pure string work with no DOM and no app globals, so
  // `tests/test_doc_comments.py` runs it in node, the same way the table,
  // frontmatter, columns and block-reference models are tested. The footnote
  // conversion exists twice, here and in `src/tessellate/core/docexport.py`
  // (the server exports cannot call into this file), and that test runs both
  // over one fixture and asserts the two agree byte for byte.

  // DOC-COMMENT-BEGIN

  //: Where a `%%…%%` is not a comment: inside a fence or inline code it is an
  //: example of the syntax, and in frontmatter it is a property's value. The
  //: three patterns are the subset of `DOC_PROSE_SKIP` that applies (an address
  //: or a link destination cannot contain a `%%` pair and a wiki link has its
  //: own brackets), repeated here rather than shared because everything between
  //: these markers has to run in node with nothing else loaded.
  const DOC_COMMENT_SKIP = [
    /(^|\n)[ \t]*(```|~~~)[^\n]*\n[\s\S]*?(\n[ \t]*\2[^\n]*|$)/g, // fenced code
    /`[^`\n]+`/g, // inline code
    /^---\n[\s\S]*?\n---/g, // frontmatter
  ];

  function docCommentSkipMask(text) {
    const mask = new Uint8Array(text.length);
    for (const source of DOC_COMMENT_SKIP) {
      //: A fresh regex per pass: these carry `g`, and `lastIndex` survives on a
      //: shared object, which silently skips half the document on every second
      //: call. The same note is on `docProseSkipMask`, for the same reason.
      const pattern = new RegExp(source.source, source.flags);
      let match;
      while ((match = pattern.exec(text)) !== null) {
        if (!match[0].length) {
          pattern.lastIndex += 1;
          continue;
        }
        mask.fill(1, match.index, match.index + match[0].length);
      }
    }
    return mask;
  }

  //: One line only, on purpose. A comment is a remark, Obsidian's multi-line
  //: `%%` block is a way of commenting *out* a passage, and a replace decoration
  //: that contains a line break is one CodeMirror throws on (the same constraint
  //: the math renderer records). A comment long enough to need two lines is a
  //: note, and this app has notes.
  const DOC_COMMENT_RE = /%%([^\n]*?)%%/g;

  //: The highlight a comment is attached to, matched at the end of the text in
  //: front of it. `[^=\n]` rather than `[\s\S]` so `==a== and ==b== %%note%%`
  //: attaches to `==b==` and not to the whole sentence.
  const DOC_COMMENT_TARGET_RE = /==([^=\n]{1,400})==$/;

  //: Every comment in a document, in document order, each with the span of the
  //: comment itself, the span of the words it is about, and the span a reader
  //: should be shown (`anchorFrom`..`anchorTo`, which is the pair together).
  //: The spans are what let the panel jump to a comment and resolve it without
  //: searching for its text again, which would find the wrong occurrence in a
  //: document that says the same thing twice.
  function docCommentsParse(text) {
    const body = typeof text === "string" ? text : "";
    if (!body) return [];
    const skip = docCommentSkipMask(body);
    const out = [];
    const pattern = new RegExp(DOC_COMMENT_RE.source, DOC_COMMENT_RE.flags);
    let match;
    let line = 1;
    let scanned = 0;
    while ((match = pattern.exec(body)) !== null) {
      const from = match.index;
      const to = from + match[0].length;
      if (skip[from] === 1) continue;
      const note = match[1].trim();
      //: `%%%%` is a typo, not an empty remark, and a comment with nothing in it
      //: would draw a row in the panel that says nothing at all.
      if (!note) continue;
      //: Lines counted forward from where the last match left off rather than by
      //: splitting the document per comment: a 20,000-word document with forty
      //: comments in it would otherwise walk the whole text forty times.
      for (let at = scanned; at < from; at += 1) if (body[at] === "\n") line += 1;
      scanned = from;
      const head = body.slice(0, from).replace(/[ \t]$/, "");
      const gap = from - head.length;
      const mark = DOC_COMMENT_TARGET_RE.exec(head);
      //: At most one space between the words and the remark about them. Two, or
      //: a line break, and they are two separate things that happen to be near
      //: each other, which is what the bare form is for.
      const anchored = mark && gap <= 1;
      out.push({
        id: `c${from}`,
        from,
        to,
        body: note,
        target: anchored ? mark[1] : "",
        targetFrom: anchored ? head.length - mark[0].length : from,
        targetTo: anchored ? head.length : from,
        anchorFrom: anchored ? head.length - mark[0].length : from,
        anchorTo: to,
        line,
      });
    }
    return out;
  }

  //: The one edit that resolves a comment: the remark goes, the highlight's
  //: markers go with it, and the words stay. Returned rather than applied so
  //: both surfaces can dispatch it through their own history (the engine's
  //: `replaceRange`, the fallback textarea's `docReplaceRange`) and Ctrl+Z
  //: therefore puts it back.
  function docCommentResolveEdit(text, comment) {
    const body = typeof text === "string" ? text : "";
    if (!comment) return null;
    const keep = comment.target || "";
    let from = keep ? comment.targetFrom : comment.from;
    let to = comment.to;
    //: The space the remark was written after it belongs to the remark. Left
    //: behind it reads as a typo in the sentence the comment was about, which is
    //: the one thing a resolve must not do to a finished passage.
    if (!keep && body[from - 1] === " ") from -= 1;
    else if (!keep && body[to] === " ") to += 1;
    const lineStart = body.lastIndexOf("\n", Math.max(0, from - 1)) + 1;
    const lineBreak = body.indexOf("\n", to);
    const lineEnd = lineBreak === -1 ? body.length : lineBreak;
    //: A line that was nothing but a comment goes whole, newline included:
    //: otherwise resolving the last remark in a document leaves a blank line
    //: that renders as a paragraph break nobody wrote.
    if (!keep && !body.slice(lineStart, from).trim() && !body.slice(to, lineEnd).trim()) {
      return { from: lineStart, to: Math.min(lineEnd + 1, body.length), insert: "" };
    }
    return { from, to, insert: keep };
  }

  //: The document without its remarks: what Read and Split show, and what the
  //: word count has always counted (a comment is not prose you wrote for a
  //: reader). The highlights stay, because a highlight is something the author
  //: did to their own text and renders as one.
  function docCommentStrip(text) {
    const body = typeof text === "string" ? text : "";
    if (!body) return "";
    const comments = docCommentsParse(body);
    let out = body;
    //: Backwards, so every span is still at the offset it was parsed at.
    for (let index = comments.length - 1; index >= 0; index -= 1) {
      const edit = docCommentResolveEdit(out, { ...comments[index], target: "" });
      out = out.slice(0, edit.from) + edit.insert + out.slice(edit.to);
    }
    return out;
  }

  //: The document with its remarks as footnotes: what an export carries.
  //: `[^c1]` where the remark was, the remark itself in a definition block at
  //: the foot, in the markdown every renderer this app's exports pass through
  //: already understands (`docNextFootnote` writes the same shape by hand).
  //:
  //: The prefix is a parameter because a document may already have footnotes of
  //: its own; `c1` collides with nothing a person writes, and the caller can
  //: pass something else if it ever does.
  function docCommentFootnotes(text, prefix = "c") {
    const body = typeof text === "string" ? text : "";
    if (!body) return "";
    const comments = docCommentsParse(body);
    if (!comments.length) return body;
    let out = body;
    const notes = [];
    for (let index = comments.length - 1; index >= 0; index -= 1) {
      const comment = comments[index];
      const label = `${prefix}${index + 1}`;
      notes.unshift(`[^${label}]: ${comment.body}`);
      //: The reference replaces the remark and nothing else: the highlight in
      //: front of it stays highlighted, so the footnote marker sits against the
      //: words it is about rather than at the end of the sentence.
      out = `${out.slice(0, comment.from)}[^${label}]${out.slice(comment.to)}`;
    }
    const tail = out.endsWith("\n") ? "" : "\n";
    return `${out}${tail}\n${notes.join("\n")}\n`;
  }

  // DOC-COMMENT-END

  // --- the comments panel -------------------------------------------------------
  //
  // **Where a comment is listed, and why it is not a right-hand panel.** The plan
  // asked for "a right panel"; this is a section of the document sidebar's Outline
  // tab, and the reason is the same one Phase 1 item 5 settled for the outline:
  // this editor has *one* panel width. A second vertical column at 1100px leaves
  // the measure under 500px, and the sidebar is already where every "about this
  // document" list lives (the outline, what links here, the notes it draws on).
  // Phase 6 turns that one panel into a sheet at narrow widths, so a right panel
  // would have needed a second responsive story for the same content. The phrase
  // in Phase 5 item 1 is superseded by this paragraph and nothing else about it
  // is.
  //
  // It was a third tab for one measurement's worth of time, and the measurement is
  // why it is not: "Documents", "Outline" and "Comments" want 257px of label in a
  // strip with 180px of content box, so the strip wrapped and stood 75px tall
  // against 29px. The markup for the backlinks had already written the rule down
  // ("the sidebar already has two tabs too many for the space it has"), which is
  // the kind of decision this project keeps in the file it applies to precisely so
  // that the next session does not have to rediscover it with a ruler.
  //
  // A row does its work in place, which is DOCUMENTS_PLAN 12 D3's rule for the
  // writing panel arrived at from the other end: pressing a row jumps the
  // document to the remark and marks the row as where you are
  // (`aria-current="location"`), and Resolve is a button on the row rather than a
  // popover over the sentence.

  //: The remark the reader is looking at, so the row can be painted as current
  //: without re-parsing to find out which one it was.
  let docCommentCurrent = null;

  function docComments() {
    return docCommentsParse(docText());
  }

  //: The words a comment is about, or the line it sits on when it is a standing
  //: remark: a row that showed only the note would read as a list of loose
  //: sentences with no idea what any of them is about.
  function docCommentContext(comment) {
    if (comment.target) return comment.target;
    const text = docText();
    const from = text.lastIndexOf("\n", Math.max(0, comment.from - 1)) + 1;
    const to = text.indexOf("\n", comment.to);
    const line = text.slice(from, to === -1 ? text.length : to);
    const rest = (line.slice(0, comment.from - from) + line.slice(comment.to - from)).trim();
    return rest || `Line ${comment.line}`;
  }

  function docCommentRow(comment) {
    const item = document.createElement("li");
    item.className = "doc-comment-item";
    item.dataset.comment = comment.id;
    if (comment.id === docCommentCurrent) item.setAttribute("aria-current", "location");

    const open = document.createElement("button");
    open.type = "button";
    open.className = "outline-link doc-comment-open";
    open.title = "Show this in the document";
    const context = document.createElement("span");
    context.className = "doc-comment-context";
    context.textContent = docCommentContext(comment);
    //: The kind of thing this is, in the same place the writing panel puts a
    //: finding's kind: a dot, then the words, then what was said about them.
    const mark = document.createElement("i");
    mark.className = comment.target ? "ph ph-highlighter doc-comment-kind" : "ph ph-chat-teardrop-text doc-comment-kind";
    mark.setAttribute("aria-hidden", "true");
    open.append(mark, context);
    open.addEventListener("click", () => docGoToComment(comment));

    const body = document.createElement("p");
    body.className = "doc-comment-body";
    body.textContent = comment.body;
    //: The whole remark, for the row that shows three lines of it.
    body.title = comment.body;

    //: **Resolve rides on the subject line, not on a footer of its own.** It was
    //: a footer with the word on it first, and that is the measurement that moved
    //: it: 113px per row in a 226px column, so a document with four remarks in it
    //: could show two. `.doc-outline-row` is this sidebar's own recipe for a link
    //: that shares its line with one action (References and the attach row use
    //: it), and the icon-only form is the one every other "take this off" in the
    //: panel already takes. The words are on the `title` and the `aria-label`.
    const head = document.createElement("div");
    head.className = "doc-outline-row doc-comment-head";
    const resolve = smallButton(
      "ph:check",
      comment.target
        ? "Resolve: take the remark and its highlight out, leaving the words"
        : "Resolve: take the remark out",
      () => docResolveComment(comment)
    );
    resolve.classList.add("doc-outline-row-action", "doc-comment-action");
    head.append(open, resolve);

    item.append(head, body);
    return item;
  }

  //: Drawn from the document's own text on every facts pass, like the outline:
  //: there is no comment store and there must not be one, or a document copied
  //: into this app from anywhere else would arrive with its remarks invisible.
  function renderDocComments() {
    const wrap = $("doc-comments-wrap");
    const list = $("doc-comments");
    const count = $("doc-comments-count");
    if (!wrap || !list) return;
    const comments = currentDoc ? docComments() : [];
    if (docCommentCurrent && !comments.some((c) => c.id === docCommentCurrent)) {
      docCommentCurrent = null;
    }
    list.replaceChildren();
    for (const comment of comments) list.appendChild(docCommentRow(comment));
    //: The whole section goes when there is nothing in it, which is what the two
    //: sections under it already do (`renderDocBacklinks`, `renderDocNotes`) and
    //: what this panel's own stylesheet measured the cost of not doing: 69px of
    //: column for an eyebrow over nothing. A sentence explaining what a comment
    //: is would be the right answer for a tab that carries the word in its name;
    //: a section is allowed to be absent.
    wrap.classList.toggle("hidden", !comments.length);
    if (count) count.textContent = comments.length ? String(comments.length) : "";
  }

  //: The document scrolls to the remark and selects it, which is both "here it
  //: is" and a sensible place to be left: the next thing anyone does with a
  //: comment is read the sentence around it or edit it. Same choice
  //: `docRevealBlock` made, for the same reason.
  function docGoToComment(comment) {
    const surface = docSurface();
    if (!surface) return;
    docCommentCurrent = comment.id;
    for (const row of document.querySelectorAll("#doc-comments .doc-comment-item")) {
      if (row.dataset.comment === comment.id) row.setAttribute("aria-current", "location");
      else row.removeAttribute("aria-current");
    }
    //: Read view has no editing surface, so there is nothing to put a caret in
    //: and no reason to leave the reader looking at a page with no remark on it.
    if (docView === "rendered") setDocView("live");
    surface.focus();
    surface.setSelectionRange(comment.anchorFrom, comment.anchorTo);
  }

  //: Opening the panel *at* a remark, which is what the pin in the text does.
  //: The offset rather than the id, because the widget knows where it is in the
  //: document and ids are derived from exactly that.
  function docShowComment(offset) {
    const comment = docComments().find((c) => c.from === offset) || null;
    showDocSidebarSection("outline");
    if (!comment) {
      renderDocComments();
      return;
    }
    docCommentCurrent = comment.id;
    renderDocComments();
    const row = document.querySelector(`#doc-comments [data-comment="${comment.id}"]`);
    //: The panel's own scrollTop, never `scrollIntoView`: the recipe index's
    //: rule for a list that says where you are, because `scrollIntoView` walks
    //: every scrolling ancestor and takes the page with it.
    if (row) keepOutlineRowInView(row);
  }

  function docResolveComment(comment) {
    const surface = docSurface();
    if (!surface) return;
    const edit = docCommentResolveEdit(surface.text, comment);
    if (!edit) return;
    docReplaceRange(surface, edit.from, edit.to, edit.insert);
    if (docCommentCurrent === comment.id) docCommentCurrent = null;
    markDocDirty();
    renderDocComments();
    scheduleDocPreview();
    renderDocCounts();
    //: Says where it went rather than only that it happened: the remark is gone
    //: from the text and the undo that brings it back is the ordinary one.
    toast("Resolved. Ctrl+Z puts it back.");
  }

  //: A remark on the selection, which is the way a comment is made. `custom` in
  //: `MD_ACTIONS` rather than a `pre`/`post` pair, because what it inserts
  //: depends on what is selected: words become `==words== %%|%%` with the caret
  //: in the remark, and nothing selected becomes a standing `%%|%%` on the line.
  function docAnnotateSelection(box, boxId = "doc-content") {
    const surface = asSurface(box);
    if (!surface) return;
    const { from, to } = surface.selection();
    const selected = surface.text.slice(from, to);
    const insert = selected ? `==${selected}== %%%%` : "%%%%";
    docReplaceRange(surface, from, to, insert);
    //: The caret between the two `%%` pairs, so the first thing typed is the
    //: remark itself. Counted from the end of what was inserted rather than
    //: forward from the start: the selection's own length is in the middle of it.
    const caret = from + insert.length - 2;
    surface.setSelectionRange(caret, caret);
    //: Through the same finish every other action in `MD_ACTIONS` uses, rather
    //: than `markDocDirty` by hand. Two reasons, and the first is a bug this
    //: avoids: this table is shared with the notes composer, so a remark left in
    //: a *note* would otherwise mark the open *document* unsaved and autosave it.
    //: Only `finishMarkdownEdit` knows which box the press came from. The second
    //: is that the panel needs no nudge from here: the document path ends in
    //: `markDocDirty` -> `scheduleDocFacts` -> `renderDocComments`, and an empty
    //: `%%%%` is not a comment yet anyway (`docCommentsParse` skips it), so the
    //: row is drawn by the first word typed into it rather than before it.
    finishMarkdownEdit(surface, boxId);
  }

  // DOC-REMARK-END-BEGIN
  //: **Enter ends a remark** (audit 1102 DX24). With the caret straight before
  //: the closing `%%` of a remark opened on this line, Enter moved nothing but
  //: put a newline in the file (`%%Check this word` then `%%`). It now steps
  //: past the marker instead; Escape does so from anywhere inside the remark
  //: (`anywhere`). Anywhere else, and in the middle of a remark, the key is the
  //: editor's own, so a deliberate two-line remark is still typed with Enter.
  docAnnotateSelection.end = (view, anywhere = false) => {
    const { state } = view;
    const caret = state.selection.main;
    if (!caret.empty) return false;
    const line = state.doc.lineAt(caret.head);
    const at = caret.head - line.from;
    if ((line.text.slice(0, at).match(/%%/g) || []).length % 2 === 0) return false;
    const close = anywhere ? line.text.indexOf("%%", at) : (line.text.startsWith("%%", at) ? at : -1);
    if (close < 0) return false;
    view.dispatch({ selection: { anchor: line.from + close + 2 }, scrollIntoView: true });
    return true;
  };
  // DOC-REMARK-END-END

  //: The file's whole surface: what documents.js, documents-cm.js and documents-prose.js call.
  Object.assign(window, { docCommentStrip, docCommentFootnotes, renderDocComments, docShowComment, docAnnotateSelection });
})();
