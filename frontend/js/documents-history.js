// documents-history.js: the version history dialog and the line diff (split
// out of documents.js, audit 1031 DC13).
//
// What is here: the line-diff model (`docDiffLines`, `docDiffHunks`,
// `docDiffApply`, `docDiffStat`), the one drawing of it (`docRenderDiff`, in
// one column or side by side), and the dialog behind the dock's Version
// history: the list with its filter, naming a version, the diff under a row.
// The AI edit panel, the code assistant's proposal and the edit-conflict
// prompt draw their changes with the same model, so they wait for this file.
//
// **Loaded on the first press**, by `lazyScript` in documents.js (the way
// documents-replace.js is): the dock's History and Name this version buttons
// are wired there and fetch it, `docAiLazy` and the code assistant's reply
// fetch it before they draw a diff, and edit-conflict.js fetches it for its
// Compare. Its top level declares, and wires the dialog's close.
(() => {
  // DOC-DIFF-BEGIN
  //: **What changed between two versions of the same text.** Two surfaces ask
  //: that question and they have to be asking it of the same object: the history
  //: dialog ("what did this version say that the next one does not") and the AI
  //: edit panel ("what is the model actually proposing"). A second diff written
  //: for the second surface is exactly how the two would come to disagree about
  //: what a change is, so there is one model here and both draw from it.
  //:
  //: **Lines, not words or characters.** A markdown document's unit of change is
  //: a line: a paragraph is one line in this app's own documents, a list item is
  //: one line, a table row is one line. A word-level diff inside a changed line
  //: reads better and is deliberately not here: it needs a second model with its
  //: own tokenisation and its own rendering, and the value of it is small next to
  //: a first version that says which paragraphs moved.
  //:
  //: **No dependency, and none is needed.** The common prefix and suffix are
  //: trimmed first, which is what makes the classic LCS table affordable: the
  //: middle of a real edit is a few lines even in a long document. The cap below
  //: is what stops the table being the size of two documents multiplied together
  //: in the one case trimming does not help (a rewrite that shares no line with
  //: what it replaced), and past it the honest answer is "this was replaced".
  const DOC_DIFF_MAX_CELLS = 4000000;

  //: The table is built from the end backwards so the walk that reads it can run
  //: forwards, which is the order the rows are drawn in. `Uint32Array` rather
  //: than nested arrays: one allocation, and a 2000x2000 middle is 16MB rather
  //: than four million boxed numbers.
  function docDiffLcs(a, b) {
    const n = a.length;
    const m = b.length;
    const width = m + 1;
    const table = new Uint32Array((n + 1) * width);
    for (let i = n - 1; i >= 0; i--) {
      for (let j = m - 1; j >= 0; j--) {
        table[i * width + j] =
          a[i] === b[j]
            ? table[(i + 1) * width + j + 1] + 1
            : Math.max(table[(i + 1) * width + j], table[i * width + j + 1]);
      }
    }
    const ops = [];
    let i = 0;
    let j = 0;
    while (i < n && j < m) {
      if (a[i] === b[j]) {
        ops.push({ op: " ", text: a[i] });
        i++;
        j++;
      } else if (table[(i + 1) * width + j] >= table[i * width + j + 1]) {
        //: A removal before an addition whenever the table is indifferent, so a
        //: replaced line always reads as "- the old, + the new" rather than the
        //: two orders alternating down the same diff.
        ops.push({ op: "-", text: a[i] });
        i++;
      } else {
        ops.push({ op: "+", text: b[j] });
        j++;
      }
    }
    while (i < n) ops.push({ op: "-", text: a[i++] });
    while (j < m) ops.push({ op: "+", text: b[j++] });
    return ops;
  }

  //: `{op, text}` for every line of both texts, in reading order: `" "` unchanged,
  //: `"-"` only in the older text, `"+"` only in the newer one.
  function docDiffLines(before, after) {
    //: An empty text has no lines, not one empty line. `"".split("\n")` says
    //: `[""]`, which would draw the first version of a document as "one line
    //: removed, everything added": the removal is of a line that was never there.
    const a = docDiffSplit(before);
    const b = docDiffSplit(after);
    let start = 0;
    while (start < a.length && start < b.length && a[start] === b[start]) start++;
    let endA = a.length;
    let endB = b.length;
    while (endA > start && endB > start && a[endA - 1] === b[endB - 1]) {
      endA--;
      endB--;
    }
    const midA = a.slice(start, endA);
    const midB = b.slice(start, endB);
    let middle;
    if (!midA.length && !midB.length) middle = [];
    else if (!midA.length) middle = midB.map((text) => ({ op: "+", text }));
    else if (!midB.length) middle = midA.map((text) => ({ op: "-", text }));
    else if (midA.length * midB.length > DOC_DIFF_MAX_CELLS)
      middle = midA
        .map((text) => ({ op: "-", text }))
        .concat(midB.map((text) => ({ op: "+", text })));
    else middle = docDiffLcs(midA, midB);
    return a
      .slice(0, start)
      .map((text) => ({ op: " ", text }))
      .concat(middle, a.slice(endA).map((text) => ({ op: " ", text })));
  }

  function docDiffSplit(text) {
    const value = String(text == null ? "" : text);
    return value === "" ? [] : value.split("\n");
  }

  function docDiffStat(ops) {
    let added = 0;
    let removed = 0;
    for (const entry of ops) {
      if (entry.op === "+") added++;
      else if (entry.op === "-") removed++;
    }
    return { added, removed };
  }

  //: **A change and the lines around it, with the rest counted rather than
  //: printed.** A diff of a long document that prints every unchanged line is a
  //: copy of the document with some colour in it: the reader has to find the
  //: change themselves, which is the work a diff exists to save. Two lines of
  //: context either side is enough to say where a change is; everything else
  //: becomes one `gap` row saying how many lines were skipped.
  function docDiffRows(ops, context) {
    const pad = Number.isFinite(context) ? context : 2;
    //: Nothing changed is no rows at all, so "these two versions say the same
    //: thing" is a sentence the caller writes rather than a page of context with
    //: no change anywhere in it.
    if (!ops.some((entry) => entry.op !== " ")) return [];
    const keep = new Array(ops.length).fill(false);
    for (let i = 0; i < ops.length; i++) {
      if (ops[i].op === " ") continue;
      for (let k = Math.max(0, i - pad); k <= Math.min(ops.length - 1, i + pad); k++) keep[k] = true;
    }
    const rows = [];
    let skipped = 0;
    for (let i = 0; i < ops.length; i++) {
      if (!keep[i]) {
        skipped++;
        continue;
      }
      if (skipped) {
        rows.push({ op: "gap", skipped });
        skipped = 0;
      }
      rows.push(ops[i]);
    }
    if (skipped) rows.push({ op: "gap", skipped });
    return rows;
  }

  //: **Changes grouped the way a person accepts them**: one hunk is a run of
  //: `+`/`-` lines with no unchanged line inside it. `docDiffApply` then rebuilds
  //: the text with only the hunks it is given applied, which is what "accept or
  //: reject per hunk" means in DOCUMENTS_PLAN Phase 5 item 3: a rejected hunk
  //: leaves the *old* lines in place, it does not drop them.
  function docDiffHunks(ops) {
    const hunks = [];
    let current = null;
    ops.forEach((entry, index) => {
      if (entry.op === " ") {
        current = null;
        return;
      }
      if (!current) {
        current = { from: index, to: index, added: 0, removed: 0 };
        hunks.push(current);
      }
      current.to = index;
      if (entry.op === "+") current.added++;
      else current.removed++;
    });
    return hunks;
  }

  function docDiffApply(ops, hunks, skipped) {
    const skip = skipped instanceof Set ? skipped : new Set(skipped || []);
    const rejected = new Set();
    hunks.forEach((hunk, index) => {
      if (!skip.has(index)) return;
      for (let i = hunk.from; i <= hunk.to; i++) rejected.add(i);
    });
    const out = [];
    ops.forEach((entry, index) => {
      const isRejected = rejected.has(index);
      if (entry.op === " ") out.push(entry.text);
      else if (entry.op === "+" && !isRejected) out.push(entry.text);
      else if (entry.op === "-" && isRejected) out.push(entry.text);
    });
    return out.join("\n");
  }
  // DOC-DIFF-END

  //: **The one drawing of a diff in this app** (DESIGN.md's recipe index, "two
  //: versions of the same text"). Both surfaces call this, and a second builder
  //: is what `tests/test_document_diff.py` fails on: the history's diff and the
  //: AI panel's proposal are the same object seen at two moments, and a reader
  //: who has learned one has learned the other.
  //:
  //: The colour vocabulary is the app's existing `.diff-added` / `.diff-removed`
  //: pair rather than a new one, so green-is-new and red-is-gone means the same
  //: thing here as it does in the chat's before/after card. The layout is this
  //: file's, because a diff of forty lines is a different shape from a
  //: two-line preview.
  function docRenderDiff(host, ops, options) {
    const opts = options || {};
    host.replaceChildren();
    host.classList.add("doc-diff", "diff-viewer");
    const rows = docDiffRows(ops, opts.context);
    if (!rows.length) {
      const same = document.createElement("p");
      same.className = "muted doc-diff-empty";
      same.textContent = opts.emptyText || "No change in the text.";
      host.appendChild(same);
      return host;
    }
    const hunks = opts.hunks || [];
    const skipped = opts.skipped instanceof Set ? opts.skipped : new Set();
    //: Which hunk an op belongs to, so a header can be drawn in front of its
    //: first line without the row loop having to search the hunk list per row.
    const hunkAt = new Map();
    hunks.forEach((hunk, index) => {
      for (let i = hunk.from; i <= hunk.to; i++) hunkAt.set(i, index);
    });
    let index = -1;
    let drawnHunk = -1;
    for (const row of rows) {
      if (row.op === "gap") {
        index += row.skipped;
        const gap = document.createElement("div");
        gap.className = "doc-diff-gap";
        gap.textContent =
          row.skipped === 1 ? "1 unchanged line" : `${row.skipped} unchanged lines`;
        host.appendChild(gap);
        continue;
      }
      index++;
      const hunkIndex = hunkAt.has(index) ? hunkAt.get(index) : -1;
      if (opts.onToggleHunk && hunkIndex !== -1 && hunkIndex !== drawnHunk) {
        drawnHunk = hunkIndex;
        host.appendChild(docDiffHunkHead(hunks[hunkIndex], hunkIndex, hunks.length, skipped, opts.onToggleHunk));
      }
      const line = document.createElement("div");
      line.className = "doc-diff-line";
      if (row.op === "+") line.classList.add("diff-added");
      else if (row.op === "-") line.classList.add("diff-removed");
      if (hunkIndex !== -1 && skipped.has(hunkIndex)) line.classList.add("is-skipped");
      const mark = document.createElement("span");
      mark.className = "doc-diff-mark";
      mark.setAttribute("aria-hidden", "true");
      mark.textContent = row.op === " " ? " " : row.op;
      const text = document.createElement("span");
      text.className = "doc-diff-text";
      //: An empty line is still a line: without the space it draws at zero
      //: height and a blank line added between two paragraphs is invisible in
      //: the one view whose job is to show exactly that.
      text.textContent = row.text === "" ? " " : row.text;
      line.append(mark, text);
      host.appendChild(line);
    }
    if (opts.split) docDiffSplitLayout(host, opts.split);
    return host;
  }

  //: **Side by side** (DOCUMENTS 24 row 4, Google Docs and every code review
  //: tool): the same rows `docRenderDiff` drew, placed on a two-column grid
  //: rather than drawn a second way. A removed run sits on the left against the
  //: added run that replaced it on the right, line for line; an unchanged line
  //: shows on both sides; a gap or a hunk head spans the two. `labels` names
  //: the columns.
  function docDiffSplitLayout(host, labels) {
    host.classList.add("doc-diff-split");
    const heads = labels.map((words) => {
      const head = document.createElement("div");
      head.className = "doc-diff-gap doc-diff-split-head";
      head.textContent = words;
      return head;
    });
    const items = [...host.children];
    host.prepend(...heads);
    heads.forEach((head, i) => {
      head.style.gridRow = "1";
      head.style.gridColumn = String(i + 1);
    });
    let row = 2;
    let run = { left: 0, right: 0 };
    const place = (el, col, at) => {
      el.style.gridRow = String(at);
      el.style.gridColumn = col;
    };
    const flush = () => {
      row += Math.max(run.left, run.right);
      run = { left: 0, right: 0 };
    };
    for (const el of items) {
      const removed = el.classList.contains("diff-removed");
      const added = el.classList.contains("diff-added");
      if (removed && !run.right) {
        place(el, "1", row + run.left++);
        continue;
      }
      if (added) {
        place(el, "2", row + run.right++);
        continue;
      }
      flush();
      if (removed) {
        place(el, "1", row + run.left++);
        continue;
      }
      if (!el.classList.contains("doc-diff-line")) {
        place(el, "1 / -1", row++);
        continue;
      }
      const twin = el.cloneNode(true);
      place(el, "1", row);
      place(twin, "2", row++);
      el.after(twin);
    }
  }

  function docDiffHunkHead(hunk, index, total, skipped, onToggle) {
    const head = document.createElement("div");
    head.className = "doc-diff-hunk-head";
    const label = document.createElement("span");
    label.className = "muted doc-diff-hunk-label";
    const counts = [];
    if (hunk.added) counts.push(`+${hunk.added}`);
    if (hunk.removed) counts.push(`-${hunk.removed}`);
    label.textContent = `Change ${index + 1} of ${total} · ${counts.join(" ")}`;
    const toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "ghost small doc-diff-hunk-toggle";
    const kept = !skipped.has(index);
    toggle.setAttribute("aria-pressed", kept ? "true" : "false");
    setLabel(toggle, kept ? "ph:check Keeping" : "ph:x Skipped");
    toggle.title = kept ? "Leave this change out" : "Put this change back in";
    toggle.addEventListener("click", () => onToggle(index));
    head.append(label, toggle);
    return head;
  }

  //: **The document's own history**, asked for by name: "can the document have
  //: edit history like git logs??"
  //:
  //: `openDocAiHistory` above lists the edits the *model* made and can revert one
  //: of them; this lists every version the document has had, whoever wrote it.
  //: They answer different questions and both are worth having, so this is a
  //: second list rather than a rewrite of that one.
  //:
  //: What makes it read like a log rather than a pile of timestamps is the
  //: signed word delta on each row, a history where every line looks the same
  //: has to be read from the top, which is the work a history exists to save.
  const DOC_HISTORY_SOURCES = {
    edit: { icon: "ph:pencil-simple", label: "You" },
    ai: { icon: "ph:sparkle", label: "AI edit" },
    restore: { icon: "ph:clock-counter-clockwise", label: "Restored" },
  };

  function docHistoryDelta(words) {
    if (!words) return "no change in length";
    return words > 0 ? `+${nounCount(words, "word")}` : nounCount(words, "word");
  }

  async function openDocHistory() {
    if (!currentDoc) return toast("Open a document first.", "info");
    const dialog = $("doc-history-dialog");
    const list = $("doc-history-list");
    const empty = $("doc-history-empty");
    if (!dialog || !list) return;
    list.replaceChildren();
    empty.classList.add("hidden");
    dialog.showModal();
    const loading = document.createElement("li");
    loading.className = "muted";
    loading.textContent = "Loading…";
    list.appendChild(loading);
    let entries;
    try {
      entries = await apiJson(`/documents/${currentDoc.id}/revisions`);
    } catch (error) {
      list.replaceChildren();
      const failed = document.createElement("li");
      failed.className = "muted";
      failed.textContent = error.message || "Couldn't load the history.";
      list.appendChild(failed);
      return;
    }
    docHistoryEntries = entries;
    docHistoryContent.clear();
    docHistoryOpenDiff = null;
    renderDocHistoryList();
  }

  //: The list is held rather than drawn straight from the response, because the
  //: filter redraws it and the diff needs to know what came *after* a version:
  //: a revision holds the text that something else replaced, so "what
  //: changed here" is this row against the row above it, or against the document
  //: as it stands for the newest one. That is the same walk `word_delta` makes on
  //: the server, so the signed word count on a row and the diff under it can
  //: never be describing two different pairs of versions.
  let docHistoryEntries = [];
  let docHistoryFilter = "all";
  let docHistoryOpenDiff = null;
  const docHistoryContent = new Map();

  async function docRevisionText(id) {
    if (docHistoryContent.has(id)) return docHistoryContent.get(id);
    const full = await apiJson(`/documents/${currentDoc.id}/revisions/${id}`);
    const text = full.content || "";
    docHistoryContent.set(id, text);
    return text;
  }

  function renderDocHistoryList() {
    const list = $("doc-history-list");
    const empty = $("doc-history-empty");
    if (!list || !empty) return;
    docHistoryOpenDiff = null;
    const shown = docHistoryEntries.filter((entry) => {
      if (docHistoryFilter === "named") return Boolean(entry.name);
      return docHistoryFilter === "all" || (entry.source || "edit") === "ai";
    });
    list.replaceChildren();
    empty.classList.toggle("hidden", shown.length > 0);
    if (!shown.length) {
      //: The filter's empty state says which filter is on. "Nothing yet" under an
      //: AI filter on a document with forty hand edits is a lie about the
      //: document rather than a fact about the filter.
      empty.textContent = {
        ai: "No AI edits in this document's history.",
        named: "No named versions yet. Name this version keeps the text as it stands now.",
      }[docHistoryFilter] || "Nothing yet: this document has not been changed since it was made.";
      return;
    }
    for (const entry of shown) list.appendChild(docHistoryRow(entry));
  }

  for (const button of document.querySelectorAll("#doc-history-filter [data-history-filter]")) {
    button.addEventListener("click", () => {
      docHistoryFilter = button.dataset.historyFilter || "all";
      for (const other of document.querySelectorAll("#doc-history-filter [data-history-filter]")) {
        other.setAttribute("aria-pressed", other === button ? "true" : "false");
        other.classList.toggle("active", other === button);
      }
      renderDocHistoryList();
    });
  }

  function docHistoryRow(entry) {
    const shape = DOC_HISTORY_SOURCES[entry.source] || DOC_HISTORY_SOURCES.edit;
    const row = document.createElement("li");
    row.className = "doc-ai-history-entry";
    const icon = document.createElement("i");
    icon.className = `ph ${shape.icon.replace("ph:", "ph-")}`;
    icon.setAttribute("aria-hidden", "true");

    const text = document.createElement("div");
    text.className = "doc-ai-history-text";
    const line = document.createElement("p");
    line.textContent = `${shape.label} · ${docHistoryDelta(entry.word_delta)}`;
    //: A named version leads with its name, the way Google Docs lists them.
    if (entry.name) {
      const name = document.createElement("strong");
      name.className = "doc-history-name";
      name.textContent = entry.name;
      line.prepend(name, " · ");
    }
    const meta = document.createElement("p");
    meta.className = "muted text-sm";
    meta.textContent = `${whenText(entry.created_at)} · ${nounCount(entry.words, "word")}`;
    //: The opening of the version itself. A row saying only "You, 20 May,
    //: +140 words" makes you open every entry to find the one you want, which
    //: is the work this list is supposed to save.
    const preview = document.createElement("p");
    preview.className = "muted text-sm doc-history-preview";
    preview.textContent = entry.preview || "";
    //: The diff opens inside the row rather than over it, which is this app's
    //: rule for a list you can act on without leaving it (DESIGN.md's recipe
    //: index): one row open at a time, the open row marked with `aria-current`,
    //: and nothing drawn over the content it is about.
    const diffBox = document.createElement("div");
    diffBox.className = "doc-history-diff hidden";
    text.append(line, meta, preview);

    const changes = document.createElement("button");
    changes.type = "button";
    changes.className = "ghost small";
    changes.textContent = "Changes";
    changes.title = "What changed between this version and the one after it";
    changes.setAttribute("aria-expanded", "false");
    changes.addEventListener("click", () => toggleDocHistoryDiff(entry, row, changes, diffBox));

    const view = document.createElement("button");
    view.type = "button";
    view.className = "ghost small";
    view.textContent = "View";
    view.title = "Read this version without changing anything";
    view.addEventListener("click", async () => {
      const full = await apiJson(
        `/documents/${currentDoc.id}/revisions/${entry.id}`
      ).catch(() => null);
      if (!full) return toast("Couldn't open that version.", true, { action: ["Try again", () => view.click()] });
      $("doc-history-dialog").close();
      //: Through the lightbox, which is already the app's read-only viewer for
      //: a document's text: including its find bar, which is how anyone
      //: actually locates what changed in a long version.
      openLightbox(
        [
          {
            filename: `${full.title || "Untitled"}, ${whenText(full.created_at)}`,
            kind: currentDoc.file_type === "md" ? "markdown" : "code",
            text: full.content || "",
            addedAt: full.created_at || "",
          },
        ],
        0
      );
    });

    const restore = document.createElement("button");
    restore.type = "button";
    restore.className = "ghost small";
    restore.textContent = "Restore";
    restore.title = "Put the document back to this version";
    restore.addEventListener("click", async () => {
      //: At once, no confirm: the restore is one step on the undo stack and its
      //: toast says how to take it back (DOCUMENTS 24 row 4).
      restore.disabled = true;
      try {
        await restoreDocVersionWithUndo(entry);
        $("doc-history-dialog").close();
      } catch (error) {
        toast(error.message || "Couldn't restore that version.", true);
      } finally {
        restore.disabled = false;
      }
    });

    const actions = document.createElement("span");
    actions.className = "row doc-history-actions";
    actions.append(changes, view, restore, docHistoryRowMenu(entry));
    //: The diff takes the row's whole width, under all three columns, so a
    //: side-by-side pair has room for two readable columns.
    row.append(icon, text, actions, diffBox);
    return row;
  }

  //: The row's less-used acts behind its ⋯ (`kebabMenu`): name or rename the
  //: version, take the name off, and on a code document compare it in the
  //: editor (the merge view, `docIdeCompareWith`).
  function docHistoryRowMenu(entry) {
    const items = [
      makeMenuItem(
        `ph:bookmark-simple ${entry.name ? "Rename this version" : "Name this version"}`,
        "A name keeps this version easy to find, and the edits after it never fold into it",
        () => docNameVersion(entry)
      ),
    ];
    if (entry.name) {
      items.push(makeMenuItem("ph:bookmark-simple Remove the name", "Keep the version, without its name", () => docSetVersionName(entry, "")));
    }
    //: The code view, as docIdeCodeView reads it; its commands call documents-ide.js directly too.
    if (docCmView && currentDoc && !docFileType().previewable) {
      items.push(
        makeMenuItem("ph:git-diff Compare in the editor", "Show this version against the editor's text, change by change", () => {
          $("doc-history-dialog").close();
          docIdeCall("docIdeCompareWith", entry.id, whenText(entry.created_at));
        })
      );
    }
    return kebabMenu(items, "More for this version", { vertical: true });
  }

  //: **A prompt asked from inside the history dialog.** `promptDialog` mounts
  //: its overlay on `<body>`, and a `showModal()` dialog makes everything
  //: outside it inert, so the prompt opened beneath the history unreachable
  //: (measured: the click at its centre landed on the history). Moved into the
  //: open modal as soon as it is made (the executor runs synchronously), the
  //: same escape `wireHelpPopover` makes for a "?". Done here rather than in
  //: app.js, whose gzipped size is held by `test_static_compression.py`.
  function docPromptInModal(message, initial) {
    const asked = promptDialog(message, initial);
    const overlay = document.body.lastElementChild;
    const modal = document.querySelector("dialog:modal");
    if (modal && overlay?.classList.contains("confirm-overlay")) {
      modal.appendChild(overlay);
      overlay.querySelector("input")?.select();
    }
    return asked;
  }

  async function docNameVersion(entry) {
    const next = await docPromptInModal(entry.name ? "Rename this version" : "Name this version", entry.name || "");
    if (next === null || next === undefined) return;
    await docSetVersionName(entry, next);
  }

  //: Naming is an act like any other: one undo step that puts the old name back.
  async function docSetVersionName(entry, name) {
    const docId = currentDoc.id;
    const before = entry.name || "";
    const put = async (value) => {
      await apiJson(`/documents/${docId}/revisions/${entry.id}`, { method: "PUT", body: JSON.stringify({ name: value }) });
      if (currentDoc?.id === docId && $("doc-history-dialog")?.open) await openDocHistory();
    };
    try {
      await put(name);
    } catch (error) {
      return toast(error.message || "Couldn't name that version.", true);
    }
    offerUndo(name.trim() ? `Named a version “${clipText(name.trim(), 40)}”` : "Removed a version's name", name.trim() ? "Version named." : "Name removed.", () => put(before), () => put(name));
  }

  //: Google Docs's "Name current version": the text as it stands, saved first so
  //: the name holds what is on screen.
  async function docNameCurrentVersion() {
    if (!currentDoc) return;
    const name = await docPromptInModal("Name this version", "");
    if (!name || !name.trim()) return;
    if (docDirty) await saveDocument({ silent: true });
    const docId = currentDoc.id;
    let made;
    try {
      made = await apiJson(`/documents/${docId}/revisions`, { method: "POST", body: JSON.stringify({ name }) });
    } catch (error) {
      return toast(error.message || "Couldn't name this version.", true);
    }
    if ($("doc-history-dialog")?.open) await openDocHistory();
    const entry = { id: made.id, name: made.name };
    offerUndo(`Named a version “${clipText(made.name, 40)}”`, "Version named. It is under Named in the history.", () => docSetVersionName(entry, ""), () => docSetVersionName(entry, made.name));
  }

  async function toggleDocHistoryDiff(entry, row, button, box) {
    if (docHistoryOpenDiff && docHistoryOpenDiff.button !== button) {
      docHistoryOpenDiff.box.classList.add("hidden");
      docHistoryOpenDiff.box.replaceChildren();
      docHistoryOpenDiff.button.setAttribute("aria-expanded", "false");
      docHistoryOpenDiff.row.removeAttribute("aria-current");
      docHistoryOpenDiff = null;
    }
    if (button.getAttribute("aria-expanded") === "true") {
      box.classList.add("hidden");
      box.replaceChildren();
      button.setAttribute("aria-expanded", "false");
      row.removeAttribute("aria-current");
      docHistoryOpenDiff = null;
      return;
    }
    box.classList.remove("hidden");
    box.replaceChildren();
    const loading = document.createElement("p");
    loading.className = "muted";
    loading.textContent = "Loading…";
    box.appendChild(loading);
    button.setAttribute("aria-expanded", "true");
    row.setAttribute("aria-current", "location");
    docHistoryOpenDiff = { row, button, box };
    const index = docHistoryEntries.findIndex((other) => other.id === entry.id);
    const newer = index > 0 ? docHistoryEntries[index - 1] : null;
    try {
      const before = await docRevisionText(entry.id);
      //: The newest version's counterpart is the document as it stands in the
      //: editor, unsaved edits included: that is the text the reader is looking
      //: at behind this dialog, and a diff against the last *saved* text would
      //: describe a document nobody can see.
      const after = newer ? await docRevisionText(newer.id) : docSurface().text;
      const ops = docDiffLines(before, after);
      const stat = docDiffStat(ops);
      box.replaceChildren();
      const head = document.createElement("p");
      head.className = "muted text-sm doc-diff-head";
      const against = newer
        ? `the version from ${whenText(newer.created_at)}`
        : "the document as it is now";
      head.textContent = `+${stat.added} −${stat.removed} lines, against ${against}.`;
      const view = document.createElement("div");
      box.append(head, view);
      //: Side by side where the dialog has the room, one column on a phone.
      const split = box.clientWidth >= 560 ? ["This version", newer ? "The version after it" : "Now"] : null;
      docRenderDiff(view, ops, { emptyText: "The text is the same; only the title changed.", split });
    } catch (error) {
      box.replaceChildren();
      const failed = document.createElement("p");
      failed.className = "muted";
      failed.textContent = error.message || "Couldn't load that version.";
      box.appendChild(failed);
    }
  }

  //: **The history in a few sentences** (L-documents-5): the server reads the newest
  //: versions pair by pair and the local model writes the account; with no model the
  //: same counts come back as plain words, so the button always answers.
  async function docHistoryStory(event) {
    const button = event.currentTarget;
    const box = $("doc-history-story");
    if (!currentDoc || !box || button.disabled) return;
    button.disabled = true;
    box.classList.remove("hidden");
    box.textContent = "Reading the versions…";
    try {
      const got = await apiJson(`/documents/${currentDoc.id}/revisions/summary`, { method: "POST", readOnly: true });
      box.textContent = got.summary;
      box.title = got.source === "model" ? "Written by the local model from the changed lines" : "Counted from the changed lines; no model wrote this";
    } catch (error) {
      box.textContent = error.message || "Couldn't read the history.";
    } finally {
      button.disabled = false;
    }
  }
  $("doc-history-story-btn")?.addEventListener("click", docHistoryStory);

  //: **Closing the dialog lets go of what it held**: the list, every version's cached text
  //: and the open diff. A space switch (space-swap.js) used to empty them by name; a modal
  //: dialog cannot be open across one, so the close is the moment, and it also frees the
  //: texts of a long history as soon as nobody is reading them.
  $("doc-history-dialog")?.addEventListener("close", () => {
    docHistoryEntries = [];
    docHistoryContent.clear();
    docHistoryOpenDiff = null;
    $("doc-history-story")?.classList.add("hidden");
  });

  //: The file's whole surface: what other files and the stand-ins call (ranked row 37a).
  Object.assign(window, { openDocHistory, docNameCurrentVersion, docRenderDiff, docDiffLines, docDiffHunks, docDiffApply, docDiffStat });
})();
