// documents-threads.js: the document comment threads' pure model (moved out of documents-comments.js, L624).
// Loaded after it; the panel calls these as `renderDocComments.model.*` (a property, so no new shared name).
(() => {
  const docCommentResolveEdit = (...args) => renderDocComments.edit(...args);

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

  renderDocComments.model = {
    docThreadsReconcile, docThreadReply, docThreadEditReply, docThreadDeleteReply, docThreadResolve, docThreadReopen, docThreadReopenEdit,
  };
})();
