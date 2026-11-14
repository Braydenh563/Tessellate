// documents-preview.js: the Read view's render, the line numbers gutter and the caret helpers.
// Moved out of documents.js whole (L335) and wrapped: only what other files call goes on `window`; nothing here runs at load.
(() => {
  function docCaretVisibleLine() {
    const box = docSurface();
    if (!box || box.kind !== "codemirror") {
      //: The textarea fallback has no line-to-pixel map (see `docVisibleTopLine`
      //: for the same gap), so there is no honest way to ask whether its caret
      //: is on screen. The viewport answer is the one it has always had.
      return null;
    }
    const view = box.view;
    const frame = view.scrollDOM.getBoundingClientRect();
    //: A hidden pane measures 0x0, and "top >= top and bottom <= bottom" would
    //: then be true of a coordinate that is nowhere.
    if (frame.height < 1) return null;
    let coords = null;
    try {
      coords = view.coordsAtPos(view.state.selection.main.head);
    } catch {
      //: A position mid-teardown, which CodeMirror answers for with null anyway.
      return null;
    }
    if (!coords) return null;
    if (coords.top < frame.top || coords.bottom > frame.bottom) return null;
    return view.state.doc.lineAt(view.state.selection.main.head).number - 1;
  }
  function docWhereLine() {
    const box = docSurface();
    if (!box || box.kind !== "codemirror") return docCaretLine();
    const caret = docCaretVisibleLine();
    return caret === null ? docVisibleTopLine() : caret;
  }
  function keepOutlineRowInView(el) {
    const limit = $("doc-sidebar");
    if (!limit) return;
    let box = el.parentElement;
    while (box && limit.contains(box) && box.scrollHeight <= box.clientHeight + 1) {
      box = box.parentElement;
    }
    if (!box || !limit.contains(box)) return;
    const row = el.getBoundingClientRect();
    const frame = box.getBoundingClientRect();
    if (row.top < frame.top) box.scrollTop -= frame.top - row.top + 8;
    else if (row.bottom > frame.bottom) box.scrollTop += row.bottom - frame.bottom + 8;
  }
  function markDocOutline(known) {
    if (!docOutlineRows.length) return;
    //: The caret's section while the caret is on screen, the top of the view
    //: otherwise: see `docCaretVisibleLine` for why that is the order.
    const cm = docSurface()?.kind === "codemirror";
    let top = cm && known != null ? known : null;
    if (top === null) {
      const caret = docCaretVisibleLine();
      top = caret === null ? docVisibleTopLine() : caret;
    }
    //: The trail follows the same line (see `docWhereLine`); the textarea
    //: fallback keeps the caret for it.
    renderDocCrumbs(cm ? top : docCaretLine());
    //: The last heading at or above the top of the view: the section whose text
    //: you are reading, not the next one down.
    let index = 0;
    for (let i = 0; i < docOutlineRows.length; i++) {
      if (docOutlineRows[i].line > top) break;
      index = i;
    }
    //: **Up to the nearest row that is actually drawn.** A folded section's
    //: headings are still in this list (the spy is about the document, not
    //: about the panel), so the heading the caret is in may be hidden under a
    //: fold: the mark then belongs on the fold's own row, which is the one the
    //: reader can see and the one that says "you are somewhere in here". While
    //: a filter is running there may be no such row at all, and then nothing is
    //: marked, which is honest: the rows on screen are a search result, not a
    //: place in the document.
    while (index > 0 && docOutlineRows[index].row?.classList.contains("hidden")) index -= 1;
    if (docOutlineRows[index].row?.classList.contains("hidden")) index = -1;
    if (index === docOutlineMarked) return;
    for (const row of docOutlineRows) {
      row.button.classList.remove("is-current");
      row.button.removeAttribute("aria-current");
    }
    if (index === -1) {
      docOutlineMarked = -1;
      return;
    }
    const button = docOutlineRows[index].button;
    button.classList.add("is-current");
    //: `location` rather than `true`: this is where the reader is in a
    //: document, which is exactly what the token means, and it is what makes
    //: the mark reach a screen reader instead of being a colour.
    button.setAttribute("aria-current", "location");
    docOutlineMarked = index;
    if (known === undefined) keepOutlineRowInView(button);
    else afterFrames(() => setTimeout(() => button.isConnected && keepOutlineRowInView(button)), 1);
  }
  function scheduleDocOutlineSpy() {
    //: **Read in the engine's own measure pass** (DX1): asked from a frame of
    //: its own, `coordsAtPos` laid the editor out a second time per key (357 ms
    //: over 60 keys at 4x CPU in a 3,120-line document).
    if (docCmView && docSurface()?.kind === "codemirror") {
      docCmView.requestMeasure({ key: scheduleDocOutlineSpy, read: docWhereLine, write: (line) => markDocOutline(line) });
      return;
    }
    if (docOutlineSpyFrame) return;
    docOutlineSpyFrame = requestAnimationFrame(() => {
      docOutlineSpyFrame = 0;
      markDocOutline();
    });
  }
  function jumpToDocLine(lineIndex) {
    const box = docSurface();
    if (!box) return;
    const lines = box.text.split("\n");
    const offset = lines.slice(0, lineIndex).reduce((n, l) => n + l.length + 1, 0);
    box.focus();
    box.setSelection(offset, offset + (lines[lineIndex] || "").length);
    if (box.kind === "codemirror") return; // the transaction above scrolled it
    // Approximate: scroll proportionally to where the line sits in the text.
    const ratio = lineIndex / Math.max(1, lines.length);
    box.scrollTop = Math.max(0, ratio * box.scrollHeight - box.clientHeight / 3);
  }
  let storageInfo = null;
  async function renderDocStorage() {
    const el = $("doc-storage-path");
    if (!el) return;
    if (!storageInfo) {
      storageInfo = await apiJson("/storage").catch(() => null);
    }
    el.textContent = storageInfo ? storageInfo.database : "(couldn't read the path)";
  }
  let docPreviewTimer = null;
  function scheduleDocPreview() {
    const preview = $("doc-preview");
    if (!preview || preview.classList.contains("hidden")) return;
    clearTimeout(docPreviewTimer);
    docPreviewTimer = setTimeout(() => {
      docPreviewTimer = null;
      if (typeof requestIdleCallback === "function") {
        requestIdleCallback(() => renderDocPreview(), { timeout: 300 });
      } else {
        requestAnimationFrame(() => renderDocPreview());
      }
    }, 120);
  }
  function renderDocPreview() {
    const preview = $("doc-preview");
    if (preview.classList.contains("hidden")) return;
    //: 1546 D5: a diagram's preview is the block pane with its picture beside the blocks (diagram-
    //: builder.js); it keeps its own DOM between changes, so the preview is not emptied first.
    //: Each block gesture hands its printed source to `set` (one history step each: `docUndoBreak`);
    //: a typed edit or an undo comes back through here. Inline, not a named function: one global less.
    if (docFileType().ext === "mmd") {
      preview.dataset.dgmLayout = docViewState.layout;
      const text = docText();
      const io = { key: currentDoc?.id, name: $("doc-title").value, set: (next) => (docUndoBreak(), (docSurface().text = next)), undo: () => docUndo(), redo: () => docRedo(), get canUndo() { return docCanUndo(); }, get canRedo() { return docCanRedo(); } };
      ensureModule("diagramBuilder").then((ok) => {
        //: A diagram the blocks cannot take (another kind, over 120 blocks) opens in Split, which is Source with its picture
        //: and the one line saying why; once per document, so a person who goes back to Blocks is not sent out again.
        if (ok) return diagramModel.builder.show(preview, io, text).then((S) => {
          const seen = (docViewState.plain ??= new Set());
          if (S?.plain && docView === "rendered" && !seen.has(currentDoc?.id)) (seen.add(currentDoc?.id), setDocView("split", { persist: false }));
        });
        preview.replaceChildren(Object.assign(document.createElement("p"), { className: "muted", textContent: "The block editor did not load. Source still works." }));
      });
      return;
    }
    preview.replaceChildren();
    const title = ($("doc-title").value || "").trim();
    const text = docText();
    //: **The properties are not prose.** Rendered as markdown, a frontmatter
    //: block is a horizontal rule, a paragraph of `key: value` lines and
    //: another rule, which is what the preview showed until now for every
    //: document this app's own vault import wrote. They come out of the body
    //: and go back in above it as the same rows the panel draws, read-only.
    const fm = docFrontmatterParse(text);
    //: The block markers come out here rather than in the renderer: `^abc123`
    //: is what makes a paragraph linkable and it is not what the paragraph
    //: says, and this pane is the one a person reads and prints.
    //: **The remarks come out of the rendered pane** (Phase 5 item 1): a comment
    //: is a note to the author, and Read view is the document as it reads. In a
    //: print they become footnotes instead, so a PDF handed to somebody carries
    //: them rather than dropping them silently, which is what `docPrintComments`
    //: is set for by `exportDocumentPdf`.
    const remarks = docPrintComments ? docCommentFootnotes : docCommentStrip;
    const stripped = fm ? docFrontmatterStrip(text) : text;
    //: Suggested changes are drawn as struck and highlighted words (PROSE-TOOLS).
    const body = docSuggestForRead(remarks(docBlockStripIds(stripped)));
    //: **How far the preview's line numbers are from the editor's.** Every
    //: block this renders carries the line it came from (`data-src-line`,
    //: `renderMarkdown` in navigation.js), but it came from the line in the string
    //: below, not in the document: the title is prepended as a heading and the
    //: frontmatter is taken off the front, so the two texts are the same words
    //: at different line numbers. The split view's scroll map reads the stamps
    //: and has to undo this, or it lines the panes up two lines out on every
    //: titled document (`docScrollAnchors`).
    //:
    //: Both terms are prefix changes, which is what makes one number enough.
    //: The one transformation that is not is a remark removed by
    //: `docCommentStrip`, and only when the remark spans a line break: that
    //: shortens the text somewhere in the middle and everything below it drifts
    //: by those lines. Bounded, rare, and a line or two against the hundreds of
    //: pixels this map exists to remove, so it is written down here rather than
    //: paid for with a second parse of the document on every render.
    //: **Not twice** (INBOX 437 (4)): a body that already opens on its own
    //: name as a heading (every template, and most imports) read "Meeting
    //: notes" over "Meeting notes", so the name only goes on when it is not.
    const opens = body.trimStart().split("\n", 1)[0];
    const lead = !!title && !(/^#\s/.test(opens) && opens.slice(1).trim().toLowerCase() === title.toLowerCase());
    docPreviewLineShift =
      (lead ? 2 : 0) - (text.split("\n").length - stripped.split("\n").length);
    docRenderBody(preview, lead ? `# ${title}\n\n${body}` : body);
    //: Named, so a phone can leave it to the head row that already shows it
    //: (10-responsive.css, "The first line under the chrome").
    if (lead) {
      const head = preview.querySelector(":scope > .md-h1");
      head?.classList.add("doc-preview-title");
      //: The contents list was filled while the title looked like any heading;
      //: filled again without it, it leaves the added title out (DX23).
      head?.remove();
      mdFillTocs(preview);
      if (head) preview.prepend(head);
    }
    if (fm) {
      //: After the title, which is the document's name rather than part of its
      //: text, and before the first thing its author wrote.
      preview.insertBefore(docPropsReadNode(fm), preview.children[title ? 1 : 0] || null);
    }
    layerDocWikiLinks(preview);
    imageLayoutRoot(preview);
    docRenderMermaidIn(preview);
    docMathRender.graphIn(preview);
    docMathRender.baseIn(preview);
    docMathRender.queryIn(preview);
    docEmbedFill.editButtons(preview);
    docEmbedFill.tagChips(preview);
    docWireReadTasks(preview, text);
  }
  const DOC_READ_TASK = /^(\s*[-*+]\s+)\[([ xX])\](\s)/;
  function docTaskLines(text) {
    const lines = String(text).split("\n");
    const out = [];
    let at = 0;
    let fence = null;
    let i = 0;
    const fm = docFrontmatterParse(text);
    if (fm) {
      const cut = docFrontmatterStrip(text);
      const skipped = text.length - cut.length;
      while (at < skipped && i < lines.length) {
        at += lines[i].length + 1;
        i += 1;
      }
    }
    for (; i < lines.length; i += 1) {
      const line = lines[i];
      const mark = line.match(/^\s*(```+|~~~+)/);
      if (mark) {
        if (!fence) fence = mark[1][0];
        else if (mark[1][0] === fence) fence = null;
      } else if (!fence && DOC_READ_TASK.test(line)) {
        out.push({ from: at, line });
      }
      at += line.length + 1;
    }
    return out;
  }
  function docWireReadTasks(preview, text) {
    const boxes = [...preview.querySelectorAll("li.md-task input[type=checkbox]")];
    if (!boxes.length) return;
    const tasks = docTaskLines(text);
    if (tasks.length !== boxes.length) return;
    boxes.forEach((box, n) => {
      box.disabled = false;
      //: **The Live view's task box, not a second one** (audit 1102 DX21): a
      //: native box at the text's size was 14.7px, under the 24px a pressable
      //: target needs (WCAG 2.5.8), and a native box cannot be padded out. The
      //: press strip and the drawn box are `.cm-md-task-hit` and `.cm-md-task`
      //: (09-editor.css), the same two the Live widget uses, so the views agree.
      if (!box.parentElement.classList.contains("cm-md-task-hit")) {
        const hit = document.createElement("span");
        hit.className = "cm-md-task-hit";
        box.classList.add("cm-md-task");
        box.replaceWith(hit);
        hit.append(box);
      }
      box.dataset.docTask = String(n);
      box.setAttribute("aria-label", box.checked ? "Done" : "Not done");
    });
    if (preview.dataset.taskWired === "1") return;
    preview.dataset.taskWired = "1";
    //: A press on the strip beside the box lands on the strip (a pseudo-element
    //: cannot be the target), so it is forwarded to the box it belongs to.
    preview.addEventListener("click", (event) => {
      const hit = event.target instanceof Element ? event.target.closest(".cm-md-task-hit") : null;
      const box = hit?.firstElementChild;
      if (box && event.target === hit && !box.disabled) box.click();
    });
    preview.addEventListener("change", (event) => {
      const box = event.target;
      if (!(box instanceof HTMLInputElement) || box.dataset.docTask === undefined) return;
      const surface = docSurface();
      const task = docTaskLines(surface?.text ?? "")[Number(box.dataset.docTask)];
      const match = task && task.line.match(DOC_READ_TASK);
      if (!match) {
        box.checked = !box.checked;
        return;
      }
      const at = task.from + match[1].length + 1;
      surface.replaceRange(at, at + 1, box.checked ? "x" : " ");
      box.setAttribute("aria-label", box.checked ? "Done" : "Not done");
    });
  }
  function docRenderBody(container, raw) {
    //: Footnotes over the whole document, before it is cut into pieces (audit
    //: FEAT-03): a note defined at the foot is cited from every piece above it,
    //: and each piece's own `renderMarkdown` would see only its half.
    const footnotes = mdFootnotePrepare(docPairInput.citeFootnotes(String(raw ?? "")).split("\n"));
    const text = footnotes.lines.join("\n");
    const pieces = () => {
      const blocks = docColumnsBlocks(text);
      if (!blocks.length) {
        container.replaceChildren();
        docRenderFlow(container, text);
        mdFootnotesFinish(container, footnotes.notes);
        //: Once more over the whole page: the flow is rendered in pieces (around
        //: block embeds and columns), and a `[TOC]` has to list every heading,
        //: not only the ones in its own piece.
        mdFillTocs(container);
        return;
      }
      container.replaceChildren();
      //: The line an offset is on, for the pieces' `lineBase`.
      const lineOf = (offset) => {
        let count = 0;
        for (let i = text.indexOf("\n"); i !== -1 && i < offset; i = text.indexOf("\n", i + 1)) count += 1;
        return count;
      };
      let at = 0;
      for (const block of blocks) {
        if (block.from > at) docRenderFlow(container, text.slice(at, block.from), lineOf(at));
        const box = document.createElement("div");
        box.className = `doc-cols md-cols md-cols-${block.columns.length}`;
        box.dataset.srcLine = String(block.openLine);
        box.style.setProperty("--doc-cols", String(Math.max(1, block.columns.length)));
        for (const column of block.columns) {
          const col = document.createElement("div");
          col.className = "doc-col";
          docRenderFlow(col, column.text, lineOf(column.from));
          box.appendChild(col);
        }
        container.appendChild(box);
        at = block.to;
      }
      if (at < text.length) docRenderFlow(container, text.slice(at), lineOf(at));
      mdFootnotesFinish(container, footnotes.notes);
      mdFillTocs(container);
    };
    //: Equation labels over the whole document too: `\eqref{k}` above its `\label{k}` names the number below it (OPEN F1).
    const labels = window.docMathRender?.labels;
    labels?.use(labels.index(raw));
    //: Held while the pieces render: a column's own render must not re-index its text alone, or `\eqref` to another column reads (?).
    if (labels) labels.held = true;
    try {
      pieces();
    } finally {
      if (labels) labels.held = false;
    }
  }
  const DOC_BLOCK_EMBED_LINE =
    /^[ \t]*!\[\[([^[\]\n]{1,120}#\^[A-Za-z0-9][A-Za-z0-9-]{0,31})\]\][ \t]*$/;
  function docRenderFlow(container, text, lineBase = 0) {
    const lines = String(text == null ? "" : text).split("\n");
    let buffer = [];
    let bufferStart = 0;
    const flush = () => {
      if (!buffer.length) return;
      docAppendRendered(container, buffer.join("\n"), lineBase + bufferStart);
      buffer = [];
    };
    lines.forEach((line, index) => {
      const match = DOC_BLOCK_EMBED_LINE.exec(line);
      if (!match) {
        if (!buffer.length) bufferStart = index;
        buffer.push(line);
        return;
      }
      flush();
      const host = document.createElement("div");
      host.className = "doc-embed-host";
      host.dataset.srcLine = String(lineBase + index);
      docEmbedFill(host, match[1].trim());
      container.appendChild(host);
    });
    flush();
  }
  function docAppendRendered(container, text, lineBase = 0) {
    const spare = document.createElement("div");
    renderMarkdown(spare, text);
    if (lineBase) {
      for (const block of spare.children) {
        if (block.dataset.srcLine !== undefined) block.dataset.srcLine = String(Number(block.dataset.srcLine) + lineBase);
      }
    }
    while (spare.firstChild) container.appendChild(spare.firstChild);
  }
  function docPropsReadNode(fm) {
    const box = document.createElement("div");
    box.className = "doc-props doc-props-read";
    for (const entry of fm.entries) {
      const row = document.createElement("div");
      row.className = "doc-prop-row";
      const key = document.createElement("span");
      key.className = "doc-prop-key";
      key.textContent = entry.key;
      const value = document.createElement("div");
      value.className = "doc-prop-value";
      if (entry.kind === "list") {
        for (const item of entry.items) {
          const chipEl = document.createElement("span");
          chipEl.className = "chip doc-prop-chip";
          chipWords(chipEl, item.text);
          value.appendChild(chipEl);
        }
      } else {
        value.textContent = entry.value.text;
      }
      row.append(key, value);
      box.appendChild(row);
    }
    return box;
  }
  function layerDocWikiLinks(container) {
    const targets = [];
    const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT, {
      acceptNode(node) {
        if (node.parentElement && node.parentElement.closest("code, pre")) {
          return NodeFilter.FILTER_REJECT;
        }
        return /\[\[[^[\]]{1,120}\]\]/.test(node.nodeValue)
          ? NodeFilter.FILTER_ACCEPT
          : NodeFilter.FILTER_SKIP;
      },
    });
    let node;
    while ((node = walker.nextNode())) targets.push(node);

    for (const textNode of targets) {
      const text = textNode.nodeValue;
      const pattern = /\[\[([^[\]]{1,120})\]\]/g;
      const frag = document.createDocumentFragment();
      let cursor = 0;
      let match;
      while ((match = pattern.exec(text)) !== null) {
        if (match.index > cursor) {
          frag.appendChild(document.createTextNode(text.slice(cursor, match.index)));
        }
        const name = match[1].trim();
        //: Through `docResolveWikiTarget` (above), which is the Notes tab's own
        //: resolver with documents tried first. This pane used to run its own
        //: exact-match-on-`e.title` lookup, which could not resolve the note
        //: form the `[[` picker actually inserts; see that function's comment.
        const target = docResolveWikiTarget(name);
        const label = docWikiTargetLabel(target);
        const link = document.createElement("button");
        link.type = "button";
        link.className = "wiki-link";
        //: The words, not the syntax the target happens to open with: see
        //: `wikiLinkLabel` in shell-reminders.js for why the raw `name` stays in the
        //: document and only what is drawn is cleaned.
        link.textContent = window.wikiLinkLabel ? window.wikiLinkLabel(name) : name;
        link.title = target
          ? `Open ${target.kind === "document" ? "" : `the ${target.kind} `}"${label}"`
          : `Nothing called "${name}" yet.`;
        link.addEventListener("click", (event) => {
          event.stopPropagation();
          docOpenResolvedWikiTarget(target, name);
        });
        frag.appendChild(link);
        cursor = pattern.lastIndex;
      }
      if (cursor < text.length) {
        frag.appendChild(document.createTextNode(text.slice(cursor)));
      }
      textNode.parentNode.replaceChild(frag, textNode);
    }
  }
  function withDocPreviewShown(fn) {
    const previous = docView;
    const restoring = !docPreviewShowing(previous);
    if (restoring) setDocView("rendered");
    renderDocPreview();
    fn(() => {
      if (restoring) setDocView(previous);
    });
  }
  function docGutters() {
    return [...document.querySelectorAll(".doc-gutter")]
      .map((gutter) => ({ gutter, box: gutter.dataset.for ? $(gutter.dataset.for) : docBoxEl() }))
      //: The document's own gutter is the fallback textarea's. Once CodeMirror
      //: is mounted the line numbers are `lineNumbers()` inside the view
      //: (DOCUMENTS_PLAN Phase 2 decision 7) and this column is not drawn at
      //: all, so it drops out of the list rather than numbering a hidden box.
      .filter((pair) => pair.box && !(docCmView && pair.box === docBoxEl()));
  }
  const DOC_GUTTER_PROPS = ["lineHeight", "paddingTop", "paddingBottom"];
  const DOC_GUTTER_BASELINE = 0.43;
  function syncDocGutterMetrics(only = null) {
    const jobs = [];
    const wanted = only && (Array.isArray(only) ? only : [only]);
    for (const { gutter, box } of docGutters()) {
      if (wanted && !wanted.includes(box)) continue;
      if (gutter.classList.contains("hidden")) continue;
      const metrics = getComputedStyle(box);
      jobs.push({
        gutter,
        metrics: Object.fromEntries([...DOC_GUTTER_PROPS, "fontSize"].map((prop) => [prop, metrics[prop]])),
        own: parseFloat(getComputedStyle(gutter).fontSize),
        height: box.offsetHeight,
      });
    }
    for (const { gutter, metrics, own, height } of jobs) {
      gutter.style.lineHeight = metrics.lineHeight;
      //: **On the text's baseline, not its centre** (INBOX 590). A smaller
      //: figure in the same line box is centred on the row, which puts its
      //: baseline above the text's by about 0.43 of the difference in size
      //: (measured 2.1px for 11.2px figures beside 16px text, `gutter.js`).
      //: The figures move down by that much and the bottom padding gives it
      //: back, so the column's scroll range stays the box's.
      const drop = DOC_GUTTER_BASELINE * (parseFloat(metrics.fontSize) - own);
      //: Each padding is written once, to its final value: the plain copy and
      //: then the baseline drop on top of it were two invalidations a row.
      const lowered = drop > 0;
      gutter.style.paddingTop = lowered ? `calc(${metrics.paddingTop} + ${drop.toFixed(2)}px)` : metrics.paddingTop;
      gutter.style.paddingBottom = lowered
        ? `max(0px, calc(${metrics.paddingBottom} - ${drop.toFixed(2)}px))`
        : metrics.paddingBottom;
      gutter.style.height = `${height}px`;
    }
  }
  let docGutterObserver = null;
  function watchDocGutter(box) {
    if (!box || typeof ResizeObserver !== "function") return;
    if (!docGutterObserver) {
      docGutterObserver = new ResizeObserver((entries) => {
        const boxes = [];
        for (const entry of entries) {
          //: The status bar's counts ride this one observer (the wake sources are
          //: capped): a box that has no width is not a tab stop (audit 1102 DX21).
          if (entry.target.id === "doc-counts") entry.target.tabIndex = entry.target.clientWidth >= 1 ? 0 : -1;
          else boxes.push(entry.target);
        }
        //: One pass for the whole delivery, reads before writes (see
        //: `syncDocGutterMetrics`).
        if (boxes.length) syncDocGutterMetrics(boxes);
      });
    }
    //: Observing the same element twice replaces the registration rather than
    //: adding a second one, so this is safe to call on every mount and every
    //: toggle.
    docGutterObserver.observe(box);
  }
  function renderDocGutter(only = null) {
    const pairs = docGutters().filter(({ gutter, box }) => (!only || box === only) && !gutter.classList.contains("hidden"));
    //: The layout reads first, for the reason `syncDocGutterMetrics` gives.
    const heights = pairs.map(({ box }) => box.offsetHeight);
    const tops = pairs.map(({ box }) => box.scrollTop);
    for (const [index, { gutter, box }] of pairs.entries()) {
      const lines = box.value.split("\n").length;
      // One text node of numbers, not one element per line: a 5,000-line file
      // is 5,000 elements to build and lay out on every keystroke otherwise,
      // and the gutter is doing nothing that needs per-line nodes.
      //: Three while the box has the focus: the caret's line is a span of its
      //: own (`.doc-gutter-current`, in the body ink), the editor's mark.
      const numbers = Array.from({ length: lines }, (_, i) => i + 1);
      const at = document.activeElement === box ? box.value.slice(0, box.selectionStart).split("\n").length : 0;
      if (!at) gutter.textContent = numbers.join("\n");
      else {
        const mark = document.createElement("span");
        mark.className = "doc-gutter-current";
        mark.textContent = String(at);
        const before = numbers.slice(0, at - 1).join("\n");
        const after = numbers.slice(at).join("\n");
        gutter.replaceChildren(before ? `${before}\n` : "", mark, after ? `\n${after}` : "");
      }
      //: Height on every paint, not only on mount: the textarea grows and
      //: shrinks with the pane, with the chat dock, and with its own resize
      //: handle, and none of those tells this code anything.
      gutter.style.height = `${heights[index]}px`;
      gutter.scrollTop = tops[index];
    }
  }
  function mountGutterFor(textarea) {
    if (!textarea || !textarea.id || textarea.parentElement?.classList.contains("gutter-wrap")) {
      return textarea?.previousElementSibling || null;
    }
    const wrap = document.createElement("div");
    wrap.className = "gutter-wrap";
    const gutter = document.createElement("div");
    gutter.className = "doc-gutter hidden";
    gutter.dataset.for = textarea.id;
    gutter.setAttribute("aria-hidden", "true");
    //: Moving a focused element in the DOM blurs it, and this runs the first
    //: time the capture section shows, which is exactly when the phone's + has
    //: just put the caret in the box (measured: focus in at 7598ms, this wrap
    //: at 7753, focus out to nothing at 7737). The caret goes back where it was.
    //: In a microtask, not inline: this also runs at this file's own top level
    //: (`mountGutterFor($("entry-content"))` below), and a focus event fired
    //: mid-evaluation reached `mountNoteSurface` before `docCmBroken` had been
    //: declared (a TDZ ReferenceError on boot when the box starts focused).
    const hadFocus = document.activeElement === textarea;
    textarea.parentElement.insertBefore(wrap, textarea);
    wrap.append(gutter, textarea);
    if (hadFocus) queueMicrotask(() => textarea.focus());
    // The note edit form builds its <li> detached and inserts it afterwards,
    // so at this point `applyDocGutter` (which walks the *document*) cannot
    // see this gutter and `getComputedStyle` returns empty strings. Decide the
    // initial state from the remembered choice right here, and copy the type
    // metrics on the first frame the box is in the document, measured, the
    // form's gutter stayed hidden on every open without both.
    const on = docGutterPref() === "1";
    gutter.classList.toggle("hidden", !on);
    textarea.classList.toggle("has-gutter", on);
    //: One copy routine for every gutter in the app, so the documents editor's
    //: static `#doc-gutter` and the two note boxes' mounted ones cannot disagree
    //: about which properties matter. It grew `height` and the font weight and
    //: style when the column was measured against the text it numbers.
    const copyMetrics = () => {
      syncDocGutterMetrics(textarea);
      watchDocGutter(textarea);
      renderDocGutter(textarea);
    };
    if (textarea.isConnected) copyMetrics();
    else requestAnimationFrame(copyMetrics);
    //: Hidden is checked on this gutter first: `renderDocGutter` walks every
    //: `.doc-gutter` in the page before it looks at one (394 ms over 61 keys in
    //: a 14k-node page, perf-1031 item 2), so a hidden gutter costs no key.
    const paint = () => {
      if (!gutter.classList.contains("hidden")) renderDocGutter(textarea);
    };
    textarea.addEventListener("input", paint);
    for (const type of ["focus", "blur", "keyup", "mouseup"]) textarea.addEventListener(type, paint);
    textarea.addEventListener("scroll", () => {
      if (!gutter.classList.contains("hidden")) gutter.scrollTop = textarea.scrollTop;
    });
    return gutter;
  }

  //: The file's surface: what other files call (L335).
  Object.assign(window, { docWhereLine, keepOutlineRowInView, markDocOutline, scheduleDocOutlineSpy, jumpToDocLine, renderDocStorage, scheduleDocPreview, renderDocPreview, withDocPreviewShown, docGutters, syncDocGutterMetrics, watchDocGutter, renderDocGutter, mountGutterFor });
})();
