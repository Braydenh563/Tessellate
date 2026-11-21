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

  // DOC-THREADS-BEGIN

  //: **A thread is a sidecar record, never text in the file** (DOCUMENTS_PLAN
  //: DX24t; audit 1102 DX24, audit 1028 D26). The remark stays the inline
  //: `%%remark%%` above, so a document still opens in Obsidian and an export
  //: still carries it as a footnote; what the file cannot say (who wrote it,
  //: when, what was answered, that it is settled) is a record in
  //: `documents.threads` (core/docthreads.py). Everything between these
  //: markers is pure (no DOM, no globals) and runs in node in
  //: tests/test_document_thread_model.py.
  //:
  //: **The key** is the remark's text hash plus its place among remarks that
  //: say the same thing (`2f9a41c3.1`), so a rename of the words around a
  //: remark, or a move of the paragraph, changes nothing. FNV-1a, because it
  //: is ten lines and a collision costs two threads swapping places.
  const DOC_THREAD_UNDO_MS = 10 * 60 * 1000;

  function docThreadHash(body) {
    let hash = 0x811c9dc5;
    for (let index = 0; index < body.length; index += 1) {
      hash ^= body.charCodeAt(index);
      hash = Math.imul(hash, 0x01000193) >>> 0;
    }
    return hash.toString(16).padStart(8, "0");
  }

  function docThreadKeys(comments) {
    const seen = new Map();
    return comments.map((comment) => {
      const hash = docThreadHash(comment.body);
      const nth = seen.get(hash) || 0;
      seen.set(hash, nth + 1);
      return `${hash}.${nth}`;
    });
  }

  //: Match records to the remarks now in the text, in four passes, each only
  //: over what the one before left: the key; the same words (a reopened thread
  //: comes back with no key, and deleting one of two identical remarks shifts
  //: the other's place); the one remark and the one open record left over (the
  //: remark was edited, and a thread must follow its remark through the typing,
  //: each keystroke being a new hash); then the rest. A remark with no record is
  //: new and is stamped (`stamp.author`, `stamp.at`; both empty on the pass that
  //: opens a document, so a remark written before threads existed claims no
  //: author or time it does not have). A record whose remark is gone is dropped
  //: if nobody answered it, and kept as resolved if they did: replies are never
  //: lost to a deleted line. Returns the new list, the record of each remark by
  //: comment id, and whether anything changed.
  function docThreadsReconcile(threads, comments, stamp = {}) {
    const keys = docThreadKeys(comments);
    const open = (threads || []).filter((thread) => !thread.resolved);
    const kept = (threads || []).filter((thread) => thread.resolved);
    const made = stamp.id || (() => `t${Math.random().toString(36).slice(2, 10)}`);
    const owner = new Array(comments.length).fill(null);
    const used = new Set();
    let changed = false;
    const claim = (index, thread, patch = null) => {
      owner[index] = patch ? { ...thread, ...patch } : thread;
      used.add(thread);
      if (patch) changed = true;
    };

    const byKey = new Map();
    for (const thread of open) if (!byKey.has(thread.key)) byKey.set(thread.key, thread);
    comments.forEach((comment, index) => {
      const thread = byKey.get(keys[index]);
      if (thread && !used.has(thread)) claim(index, thread);
    });
    comments.forEach((comment, index) => {
      if (owner[index]) return;
      const thread = open.find((candidate) => !used.has(candidate) && candidate.text === comment.body);
      if (thread) claim(index, thread, { key: keys[index] });
    });
    const freeComments = comments.map((c, index) => index).filter((index) => !owner[index]);
    const freeThreads = open.filter((thread) => !used.has(thread));
    const reclaimed = new Set();
    if (freeComments.length === 1 && freeThreads.length === 1) {
      const index = freeComments[0];
      claim(index, freeThreads[0], { key: keys[index], text: comments[index].body });
    } else {
      const now = Date.parse(stamp.at || "");
      for (const index of freeComments) {
        //: **Ctrl+Z after Resolve puts the remark back, and its thread with it.**
        //: A remark that returns with the words of one resolved a moment ago is
        //: that thread reopened, not a stranger: replies and all. Only a recent
        //: one (`DOC_THREAD_UNDO_MS`), or writing the same words again next month
        //: would resurrect a settled thread.
        const back = Number.isNaN(now)
          ? null
          : (threads || [])
              .filter((t) => t.resolved && !reclaimed.has(t) && t.text === comments[index].body && now - Date.parse(t.resolved_at || "") <= DOC_THREAD_UNDO_MS)
              .sort((a, b) => Date.parse(b.resolved_at) - Date.parse(a.resolved_at))[0];
        if (back) {
          reclaimed.add(back);
          owner[index] = { ...back, resolved: false, resolved_at: "", key: keys[index] };
        } else {
          owner[index] = {
            id: made(),
            key: keys[index],
            author: stamp.author || "",
            at: stamp.at || "",
            text: comments[index].body,
            replies: [],
            resolved: false,
            resolved_at: "",
            target: "",
            line: 1,
            own: false,
          };
        }
        changed = true;
      }
    }
    const orphans = open.filter((thread) => !used.has(thread) && !owner.includes(thread));
    const fallen = [];
    for (const thread of orphans) {
      changed = true;
      if (thread.replies && thread.replies.length) fallen.push({ ...thread, resolved: true, resolved_at: thread.resolved_at || stamp.at || "" });
    }
    const byComment = {};
    comments.forEach((comment, index) => {
      byComment[comment.id] = owner[index];
    });
    //: Resolved records first, then the open ones in the order of the text: the
    //: stored order is stable, which keeps a save from rewriting an unchanged list.
    const next = [...kept.filter((thread) => !reclaimed.has(thread)), ...fallen, ...owner];
    return { threads: next, byComment, changed };
  }

  function docThreadReply(threads, id, author, at, text) {
    const said = String(text || "").trim();
    if (!said || !threads.some((thread) => thread.id === id)) return threads;
    return threads.map((thread) => (thread.id === id ? { ...thread, replies: [...thread.replies, { author: author || "", at: at || "", text: said }] } : thread));
  }

  //: A reply's words changed (the stamp stays: it says when it was first said), or the reply taken
  //: away. Empty words and a place that is not there change nothing, and hand back the same list.
  function docThreadEditReply(threads, id, index, text) {
    const said = String(text || "").trim();
    const thread = threads.find((one) => one.id === id);
    if (!said || !thread || !thread.replies[index]) return threads;
    const replies = thread.replies.map((reply, at) => (at === index ? { ...reply, text: said } : reply));
    return threads.map((one) => (one === thread ? { ...one, replies } : one));
  }

  function docThreadDeleteReply(threads, id, index) {
    const thread = threads.find((one) => one.id === id);
    if (!thread || !thread.replies[index]) return threads;
    const replies = thread.replies.filter((reply, at) => at !== index);
    return threads.map((one) => (one === thread ? { ...one, replies } : one));
  }

  //: What Reopen needs is kept on the record at the moment of resolving, when
  //: the remark is still in the text: the words it was about, the line, and
  //: whether it was alone on its line (`own`, which `docCommentResolveEdit`
  //: removed whole).
  function docThreadResolve(threads, id, comment, text, at) {
    const edit = docCommentResolveEdit(text, comment);
    const own = Boolean(edit) && text.slice(edit.from, edit.to).replace(/\n$/, "") === text.slice(comment.from, comment.to);
    return threads.map((thread) =>
      thread.id === id
        ? { ...thread, resolved: true, resolved_at: at || "", text: comment.body, target: comment.target || "", line: comment.line || 1, own }
        : thread
    );
  }

  //: Reopened with no key, so the reconcile after the edit below finds the
  //: remark by its words and the thread (replies and all) is back.
  function docThreadReopen(threads, id) {
    return threads.map((thread) => (thread.id === id ? { ...thread, resolved: false, resolved_at: "", key: "" } : thread));
  }

  //: The edit that puts a resolved remark back. Its words are looked for in the
  //: text as it is now (the first place outside code and frontmatter) and
  //: highlighted again; failing that, a standing remark goes where it was (its
  //: own line, or the end of its line), and one in a place that is code now goes
  //: to the end of the document. Nothing is lost if the words changed: the
  //: remark comes back, attached to the line rather than the words.
  function docThreadReopenEdit(text, thread) {
    const body = typeof text === "string" ? text : "";
    const remark = `%%${thread.text}%%`;
    const skip = docCommentSkipMask(body);
    if (thread.target) {
      let at = body.indexOf(thread.target);
      while (at !== -1 && skip[at] === 1) at = body.indexOf(thread.target, at + 1);
      if (at !== -1) return { from: at, to: at + thread.target.length, insert: `==${thread.target}== ${remark}` };
    }
    const starts = [0];
    for (let index = 0; index < body.length; index += 1) if (body[index] === "\n") starts.push(index + 1);
    const line = Math.min(Math.max(1, thread.line || 1), starts.length);
    const lineStart = starts[line - 1];
    const lineEnd = line < starts.length ? starts[line] - 1 : body.length;
    const end = { from: body.length, to: body.length, insert: `${body && !body.endsWith("\n") ? "\n" : ""}${remark}` };
    if (skip[lineStart] === 1 || skip[Math.max(0, lineEnd - 1)] === 1) return end;
    if (thread.own) return { from: lineStart, to: lineStart, insert: `${remark}\n` };
    const lineText = body.slice(lineStart, lineEnd);
    return { from: lineEnd, to: lineEnd, insert: lineText.trim() ? ` ${remark}` : remark };
  }

  // DOC-THREADS-END

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

  // --- the threads behind the remarks (DOCUMENTS_PLAN DX24t) ----------------
  //
  // **Where the records live while a document is open.** In this closure, keyed
  // by the document they belong to, loaded from `currentDoc.threads` on the
  // first pass after an open and sent back by every save (`docThreadsForSave`,
  // read by `docSaveOnce`). The first pass stamps nothing (a remark written
  // before threads existed has no author or time and claims none); a remark
  // that appears after it is stamped with the account's name (the display name
  // in Settings, "You" until there is one) and the moment. Single user,
  // local-first: the name is for reading a thread back, not for access.
  let docThreads = [];
  let docThreadsDoc = null;
  let docThreadMap = {};
  let docThreadsResolvedOpen = false;
  let docCommentReplying = null;
  //: The reply being reworded: `thread.id:index`, or null.
  let docCommentEditing = null;

  function docThreadAuthor() {
    return ((typeof prefsCache === "object" && prefsCache?.display_name) || "").trim() || "You";
  }

  function docThreadWho(author, at) {
    const when = at ? relativeTime(at) : "";
    return [author, when].filter(Boolean).join(" \u00b7 ");
  }

  //: Reconcile the records with the remarks in the text now. Called by every
  //: draw of the panel, so the records follow the text through typing, undo and
  //: a restored revision with no hook of their own.
  function docThreadsSync(comments) {
    if (!currentDoc) {
      docThreads = [];
      docThreadsDoc = null;
      docThreadMap = {};
      return;
    }
    const opening = docThreadsDoc !== currentDoc.id;
    if (opening) {
      docThreads = Array.isArray(currentDoc.threads) ? currentDoc.threads : [];
      docThreadsDoc = currentDoc.id;
      docCommentReplying = null;
      docCommentEditing = null;
    }
    const stamp = opening ? { author: "", at: "" } : { author: docThreadAuthor(), at: new Date().toISOString() };
    const result = docThreadsReconcile(docThreads, comments, stamp);
    docThreads = result.threads;
    docThreadMap = result.byComment;
    //: Threads made or dropped by the reconcile are a change to save even when
    //: the text did not move (a remark that came back with a revision, one
    //: whose words were edited away); the opening pass is not, or every open
    //: would be an unsaved document.
    if (!opening && result.changed) markDocDirty();
  }

  //: What a save sends: undefined (so JSON leaves it out and the server keeps
  //: what it has) until this document's records have been read.
  function docThreadsForSave() {
    return currentDoc && docThreadsDoc === currentDoc.id ? docThreads : undefined;
  }

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

  //: Who and when, then the replies under a remark, the same in an open row and
  //: a resolved one.
  function docThreadReplies(thread) {
    const list = document.createElement("ol");
    list.className = "doc-comment-replies";
    thread.replies.forEach((reply, index) => {
      const item = document.createElement("li");
      item.className = "doc-comment-reply";
      const who = document.createElement("span");
      who.className = "doc-comment-who";
      who.textContent = docThreadWho(reply.author, reply.at);
      if (docCommentEditing === `${thread.id}:${index}`) {
        item.append(who, docCommentReplyForm(thread, index));
        list.appendChild(item);
        return;
      }
      const said = document.createElement("p");
      said.className = "doc-comment-body";
      //: A reply may carry an attached link or `[[note]]`, so it is drawn as markdown.
      renderMarkdown(said, reply.text);
      //: Edit and Delete sit on the byline, icon only, like the head row's actions.
      const edit = smallButton("ph:pencil-simple", "Edit this reply", () => {
        docCommentEditing = `${thread.id}:${index}`;
        renderDocComments();
        document.querySelector("#doc-comments .doc-comment-reply-input")?.focus();
      });
      const drop = smallButton("ph:trash", "Delete this reply", () => docDeleteReply(thread, index));
      for (const button of [edit, drop]) button.classList.add("doc-comment-action", "doc-comment-reply-action");
      who.append(edit, drop);
      item.append(who, said);
      list.appendChild(item);
    });
    return list;
  }

  //: One line and Enter to post, Escape to cancel: a reply is a sentence. The
  //: field is the app's plain text input, not a second editor.
  //: With an `index` it rewords that reply instead of adding one.
  //: What the picker handed back, as the markdown a reply draws: a link as `[label](url)`, a note
  //: or document as `[[title]]`, a board as `[[board:id|title]]` (the board's own shapes).
  function docReplyAttachMarkdown(chosen) {
    const row = chosen.row || {};
    const label = String(chosen.label || row.title || "").replace(/[[\]|]/g, " ").replace(/\s+/g, " ").trim().slice(0, 120);
    if (chosen.kind === "link") {
      const url = String(row.url || "").replace(/ /g, "%20").replace(/\)/g, "%29");
      return url ? `[${label || url}](${url})` : "";
    }
    if (chosen.kind === "board") return `[[${row.type === "board" ? "board" : "map"}:${chosen.id ?? row.id}|${label || "Board"}]]`;
    return label ? `[[${label}]]` : "";
  }

  function docCommentReplyForm(thread, index = -1) {
    const editing = index >= 0;
    const form = document.createElement("form");
    form.className = "doc-comment-reply-form";
    const input = document.createElement("input");
    input.type = "text";
    input.className = "doc-comment-reply-input";
    input.maxLength = 2000;
    input.placeholder = "Write a reply";
    input.setAttribute("aria-label", editing ? "Edit this reply" : "Reply to this comment");
    if (editing) input.value = thread.replies[index].text;
    input.addEventListener("keydown", (event) => {
      if (event.key !== "Escape") return;
      event.preventDefault();
      docCommentReplying = null;
      docCommentEditing = null;
      renderDocComments();
    });
    const post = smallButton(editing ? "Save" : "Post", editing ? "Save the reply" : "Post the reply", () => {}, false);
    post.type = "submit";
    //: Attach, as on the board's comments: the app's one-thing picker, written into the field as markdown.
    const attach = smallButton("ph:paperclip", "Attach a bookmark, note, document or board", async () => {
      const chosen = await pickLibraryItemDialog("Attach to this reply", { sources: ["link", "note", "document", "board"] });
      const piece = chosen ? docReplyAttachMarkdown(chosen) : "";
      if (!piece) return;
      const at = input.selectionStart ?? input.value.length;
      const before = input.value.slice(0, at);
      const lead = before && !/\s$/.test(before) ? " " : "";
      input.value = `${before}${lead}${piece} ${input.value.slice(input.selectionEnd ?? at)}`.slice(0, input.maxLength);
      input.focus({ preventScroll: true });
    });
    attach.classList.add("doc-comment-action");
    form.append(input, attach, post);
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      if (editing) docEditReply(thread, index, input.value);
      else docReplyToComment(thread, input.value);
    });
    return form;
  }

  function docCommentRow(comment) {
    const thread = docThreadMap[comment.id] || null;
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
    resolve.classList.add("doc-comment-resolve");
    //: Reply is the head row's second icon, beside Resolve, for the same reason
    //: Resolve is there: a row that grows a line for it is a panel that shows two
    //: remarks instead of four (a remark with no thread, one written before
    //: threads, has no Reply and is unchanged).
    if (thread && docCommentReplying !== thread.id) {
      const reply = smallButton("ph:arrow-bend-up-left", "Reply to this comment", () => {
        docCommentReplying = thread.id;
        renderDocComments();
        document.querySelector("#doc-comments .doc-comment-reply-input")?.focus();
      });
      reply.classList.add("doc-outline-row-action", "doc-comment-action", "doc-comment-reply-open");
      head.append(open, reply, resolve);
    } else head.append(open, resolve);

    item.append(head);
    const who = thread ? docThreadWho(thread.author, thread.at) : "";
    if (who) {
      const byline = document.createElement("span");
      byline.className = "doc-comment-who";
      byline.textContent = who;
      item.append(byline);
    }
    item.append(body);
    if (thread?.replies.length) item.append(docThreadReplies(thread));
    if (thread && docCommentReplying === thread.id) item.append(docCommentReplyForm(thread));
    return item;
  }

  //: A resolved thread: the words it was about, who said what, and Reopen. Its
  //: remark is not in the text (resolving removes it, undoably); Reopen puts it
  //: back where the words are (`docThreadReopenEdit`).
  function docResolvedRow(thread) {
    const item = document.createElement("li");
    item.className = "doc-comment-item doc-comment-resolved";
    item.dataset.thread = thread.id;
    const head = document.createElement("div");
    head.className = "doc-outline-row doc-comment-head";
    const context = document.createElement("span");
    context.className = "outline-link doc-comment-open doc-comment-context";
    context.textContent = thread.target || `Line ${thread.line}`;
    const reopen = smallButton("ph:arrow-counter-clockwise", "Reopen: put the remark back in the document", () => docReopenComment(thread));
    reopen.classList.add("doc-outline-row-action", "doc-comment-action");
    //: A resolved thread can still be answered: the reply stays on it, and it stays resolved.
    const answer = smallButton("ph:arrow-bend-up-left", "Reply to this comment", () => {
      docCommentReplying = thread.id;
      renderDocComments();
      document.querySelector("#doc-comments .doc-comment-reply-input")?.focus();
    });
    answer.classList.add("doc-outline-row-action", "doc-comment-action", "doc-comment-reply-open");
    head.append(context, ...(docCommentReplying === thread.id ? [] : [answer]), reopen);
    const meta = document.createElement("span");
    meta.className = "doc-comment-who";
    meta.textContent = [docThreadWho(thread.author, thread.at), thread.resolved_at ? `resolved ${relativeTime(thread.resolved_at)}` : "resolved"].filter(Boolean).join(" \u00b7 ");
    const body = document.createElement("p");
    body.className = "doc-comment-body";
    body.textContent = thread.text;
    body.title = thread.text;
    item.append(head, meta, body);
    if (thread.replies.length) item.append(docThreadReplies(thread));
    if (docCommentReplying === thread.id) item.append(docCommentReplyForm(thread));
    return item;
  }

  //: The panel's parts are made on the first draw, not shipped in the page (the boot element cap).
  function docCommentsShell(wrap) {
    if (wrap.firstElementChild) return;
    const heading = document.createElement("h3");
    const count = document.createElement("span");
    count.className = "doc-outline-count";
    count.id = "doc-comments-count";
    heading.append("Comments ", count);
    const list = document.createElement("ul");
    list.id = "doc-comments";
    list.className = "doc-outline doc-comments";
    const toggle = document.createElement("button");
    toggle.type = "button";
    toggle.id = "doc-comments-resolved-toggle";
    toggle.className = "ghost small doc-comments-resolved-toggle hidden";
    toggle.setAttribute("aria-expanded", "false");
    toggle.setAttribute("aria-controls", "doc-comments-resolved");
    const shelf = document.createElement("ul");
    shelf.id = "doc-comments-resolved";
    shelf.className = "doc-outline doc-comments hidden";
    wrap.append(heading, list, toggle, shelf);
  }

  //: Drawn from the document's own text on every facts pass, like the outline:
  //: there is no comment store and there must not be one, or a document copied
  //: into this app from anywhere else would arrive with its remarks invisible.
  function renderDocComments() {
    const wrap = $("doc-comments-wrap");
    if (wrap) docCommentsShell(wrap);
    const list = $("doc-comments");
    const count = $("doc-comments-count");
    if (!wrap || !list) return;
    //: A reply being typed is not redrawn under the person typing it: the facts
    //: pass runs on every edit and would swap the field out from under the caret.
    if (docCommentReplying && list.contains(document.activeElement) && document.activeElement.matches?.(".doc-comment-reply-input")) return;
    if (docCommentEditing && list.contains(document.activeElement) && document.activeElement.matches?.(".doc-comment-reply-input")) return;
    const comments = currentDoc ? docComments() : [];
    docThreadsSync(comments);
    if (docCommentCurrent && !comments.some((c) => c.id === docCommentCurrent)) {
      docCommentCurrent = null;
    }
    list.replaceChildren();
    for (const comment of comments) list.appendChild(docCommentRow(comment));
    const resolved = docThreads.filter((thread) => thread.resolved);
    const toggle = $("doc-comments-resolved-toggle");
    const shelf = $("doc-comments-resolved");
    if (toggle && shelf) {
      toggle.classList.toggle("hidden", !resolved.length);
      if (!resolved.length) docThreadsResolvedOpen = false;
      toggle.setAttribute("aria-expanded", String(docThreadsResolvedOpen));
      toggle.textContent = `${docThreadsResolvedOpen ? "Hide" : "Show"} ${resolved.length} resolved`;
      shelf.classList.toggle("hidden", !docThreadsResolvedOpen || !resolved.length);
      shelf.replaceChildren();
      if (docThreadsResolvedOpen) for (const thread of resolved) shelf.appendChild(docResolvedRow(thread));
    }
    //: The whole section goes when there is nothing in it, which is what the two
    //: sections under it already do (`renderDocBacklinks`, `renderDocNotes`) and
    //: what this panel's own stylesheet measured the cost of not doing: 69px of
    //: column for an eyebrow over nothing. A sentence explaining what a comment
    //: is would be the right answer for a tab that carries the word in its name;
    //: a section is allowed to be absent. Resolved threads keep it, so they can
    //: be reopened from a document with no open remark left in it.
    wrap.classList.toggle("hidden", !comments.length && !resolved.length);
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
    const thread = docThreadMap[comment.id];
    //: The record first, from the text as it is before the edit: the words, the
    //: line and whether the remark had its line to itself are what Reopen needs.
    if (thread) docThreads = docThreadResolve(docThreads, thread.id, comment, surface.text, new Date().toISOString());
    docReplaceRange(surface, edit.from, edit.to, edit.insert);
    if (docCommentReplying === thread?.id) docCommentReplying = null;
    if (docCommentCurrent === comment.id) docCommentCurrent = null;
    markDocDirty();
    renderDocComments();
    scheduleDocPreview();
    renderDocCounts();
    //: Says where it went rather than only that it happened: the remark is gone
    //: from the text and the undo that brings it back is the ordinary one.
    toast("Resolved. Ctrl+Z puts it back, or Show resolved lists it.");
  }

  //: The remark goes back into the text and the thread with it; the
  //: reconcile after the edit finds it by its words.
  function docReopenComment(thread) {
    const surface = docSurface();
    if (!surface) return;
    const edit = docThreadReopenEdit(surface.text, thread);
    docThreads = docThreadReopen(docThreads, thread.id);
    docReplaceRange(surface, edit.from, edit.to, edit.insert);
    markDocDirty();
    renderDocComments();
    scheduleDocPreview();
    renderDocCounts();
    toast("Reopened. Ctrl+Z puts it back.");
  }

  function docEditReply(thread, index, text) {
    docCommentEditing = null;
    const next = docThreadEditReply(docThreads, thread.id, index, text);
    if (next !== docThreads) {
      docThreads = next;
      markDocDirty();
    }
    renderDocComments();
  }

  function docDeleteReply(thread, index) {
    const before = docThreads;
    const next = docThreadDeleteReply(before, thread.id, index);
    if (next === before) return;
    const apply = (list) => {
      docThreads = list;
      markDocDirty();
      renderDocComments();
    };
    apply(next);
    offerUndo("Deleted a reply", "Reply deleted.", () => apply(before), () => apply(next));
  }

  function docReplyToComment(thread, text) {
    const next = docThreadReply(docThreads, thread.id, docThreadAuthor(), new Date().toISOString(), text);
    if (next === docThreads) return;
    docThreads = next;
    docCommentReplying = null;
    //: Saved with the document: a reply is a change like any other.
    markDocDirty();
    renderDocComments();
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

  //: One listener on the wrap, since the toggle inside it is made on the first draw.
  $("doc-comments-wrap")?.addEventListener("click", (event) => {
    if (!event.target.closest?.("#doc-comments-resolved-toggle")) return;
    docThreadsResolvedOpen = !docThreadsResolvedOpen;
    renderDocComments();
  });

  //: The file's whole surface: what documents.js, documents-cm.js and documents-prose.js call.
  Object.assign(window, { docCommentStrip, docCommentFootnotes, renderDocComments, docShowComment, docAnnotateSelection });
  //: What a save sends beside the text; a property of the panel's own entry point so it takes no name in the shared scope (tests/test_global_scope_ratchet.py).
  renderDocComments.threads = docThreadsForSave;
  //: The next draw reads the records from `currentDoc` again ("Take theirs" replaced them).
  renderDocComments.reload = () => {
    docThreadsDoc = null;
  };
})();
