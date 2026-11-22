// documents-md-actions.js: the markdown formatting actions behind the toolbar and the keys, and image paste.
// Moved out of documents.js whole (L-documents-117) and wrapped: only what other files call goes on `window`.
(() => {
  // Markdown formatting from a toolbar, so you don't have to remember the
  // syntax. Everything it inserts is plain markdown, the file stays portable
  // and the source stays readable, which is the point of using markdown at all.
  const MD_ACTIONS = {
    h1: { line: "# " },
    h2: { line: "## " },
    h3: { line: "### " },
    bold: { wrap: MD_INLINE_MARKS.bold, placeholder: "bold text" },
    italic: { wrap: MD_INLINE_MARKS.italic, placeholder: "italic text" },
    strike: { wrap: MD_INLINE_MARKS.strike, placeholder: "struck through" },
    code: { wrap: MD_INLINE_MARKS.code, placeholder: "code" },
    highlight: { wrap: MD_INLINE_MARKS.highlight, placeholder: "highlighted" },
    clearformat: { custom: "clearformat" },
    //: Opens the "/" menu (editor.js), the one insert catalogue (DX6).
    insert: { custom: "insert" },
    //: The one icon and emoji picker (MINDMAP_PLAN decision 46).
    emoji: { custom: "emoji" },
    //: The picker's other two tabs and the calculator, each its own door (INBOX 1544).
    icon: { custom: "icon" },
    symbol: { custom: "symbol" },
    equation: { custom: "equation" },
    calculator: { custom: "calculator" },
    ul: { line: "- " },
    ol: { line: "1. " },
    task: { line: "- [ ] " },
    quote: { line: "> " },
    link: { custom: "link" },
    codeblock: { block: "```\n", suffix: "\n```", placeholder: "your code" },
    //: The graph of the document's labelled sections (documents-sections.js, L-documents-49); the one line is its caption.
    sections: { block: "```sections\ntitle: ", suffix: "\n```", placeholder: "Linked ideas" },
    //: **Three columns, and the caret in the first header cell.** The "/" menu
    //: has always said "3 columns" and this table had two, which is the kind of
    //: disagreement nobody reports and everybody notices. `custom`, because the
    //: `insert` shape leaves the caret after the whole block: a table you have
    //: to arrow back into is a table you retype.
    table: { custom: "table" },
    hr: { insert: "\n---\n" },

    //: **The rest of the Obsidian editing-toolbar's command set**, asked for by
    //: name: *"I want you to make the toolbar in the notes and documents
    //: exactly like this but also with the application specific functions, both
    //: in what tools are there, and how they function"*, PKM-er's
    //: obsidian-editing-toolbar.
    //:
    //: Added to this table rather than to a second one, because this table is
    //: already the single place that decides what `**` means in this app (see
    //: its own comment, and editor.js's "/" menu, which reads the same
    //: dialect). A command that lives anywhere else is a third opinion waiting
    //: to disagree.
    h4: { line: "#### " },
    h5: { line: "##### " },
    h6: { line: "###### " },
    //: A callout, not a bare blockquote. `> [!note]` is the syntax Obsidian,
    //: GitHub and Typora all already render, which is the same portability
    //: argument editor.js makes for using it in the "/" menu.
    callout: { block: "> [!note] ", suffix: "\n> ", placeholder: "Title" },
    //: Asymmetric wrappers: HTML, because markdown has no superscript and
    //: Obsidian's own toolbar inserts exactly these tags.
    sup: { pre: "<sup>", post: "</sup>", placeholder: "sup" },
    sub: { pre: "<sub>", post: "</sub>", placeholder: "sub" },
    underline: { pre: "<u>", post: "</u>", placeholder: "underlined" },
    //: `$…$` is the syntax every markdown editor with math uses, and the
    //: renderer for it is in this file (`docMathTree`). Symmetric, so pressing
    //: it twice takes it off again, which is what `wrap` gives.
    math: { wrap: "$", placeholder: "x^2" },
    //: `%%…%%` is Obsidian's comment: kept in the file, never rendered.
    comment: { pre: "%%", post: "%%", placeholder: "note to self" },
    //: A remark *on* something, which is the comment the panel lists (Phase 5
    //: item 1). `custom`, because a `pre`/`post` pair cannot do it: what it
    //: inserts depends on whether anything is selected, and the caret has to
    //: land between the two `%%` pairs rather than after the whole insertion.
    annotate: { custom: "annotate" },
    image: { custom: "image" },
    //: Properties (DOCUMENTS_PLAN Phase 3 item 4). `custom`, because the block
    //: goes at the top of the document rather than at the caret: it is the one
    //: markdown construct whose position is fixed by what it means.
    properties: { custom: "properties" },
    //: A block reference (DOCUMENTS_PLAN Phase 4 item 2). `custom`, because it
    //: inserts nothing at the caret: it gives the block the caret is in an id
    //: and puts the link to it on the clipboard.
    blockref: { custom: "blockref" },
    //: A synced block (DOCUMENTS_PLAN 26): the same block reference as an embed, copied now and inserted in another document later.
    syncedcopy: { custom: "syncedcopy" },
    syncedpaste: { custom: "syncedpaste" },
    //: Two columns, with the caret in the first one. The `block`/`suffix` shape
    //: rather than `insert`, so the selection lands on the placeholder and the
    //: first thing typed replaces it, which is what the table and the code
    //: block already do.
    columns: {
      block: "\n:::columns\n",
      suffix: "\n:::column\n\n:::\n",
      placeholder: "Left column",
    },
    //: This app's own link syntax, which is the "application specific
    //: functions" half of the request, a toolbar for *this* notebook has to
    //: offer the link that resolves inside it, not only the markdown one.
    wikilink: { pre: "[[", post: "]]", placeholder: "note name" },
    footnote: { custom: "footnote" },
    cite: { custom: "cite" },
    indent: { custom: "indent" },
    outdent: { custom: "outdent" },
    undo: { custom: "undo" },
    redo: { custom: "redo" },
  };

  // `boxId` is what lets the Notes composer reuse this whole table. It used to
  // be hardcoded to the document editor, and duplicating the logic for notes
  // would have been the third place in this app to independently decide what
  // `**` means: see MD_ACTIONS' own comment and editor.js's "/" menu, which
  // are already deliberately kept to one dialect.
  //: **A line prefix is a switch, not a stack.** The heading, list, task and
  //: quote buttons used to put their marker in front of whatever the line
  //: already began with, so H2 on a heading did nothing,
  //: Numbered on a bullet gave `1. - x` and H1 on `## x` gave `# ## x`. A
  //: second press on the same kind takes it off (every other editor's toggle);
  //: a different kind of the same family (heading, list) replaces it; a quote
  //: marker is its own layer and stays put under either. Blank lines in a
  //: multi-line selection are left blank; a numbered list counts 1, 2, 3.
  const MD_LINE_KINDS = {
    h1: ["heading", "# "], h2: ["heading", "## "], h3: ["heading", "### "],
    h4: ["heading", "#### "], h5: ["heading", "##### "], h6: ["heading", "###### "],
    ul: ["list", "- "], ol: ["list", "1. "], task: ["list", "- [ ] "], quote: ["quote", "> "],
  };
  const MD_LINE_QUOTE = /^(?:>[ \t]?)+/;
  const MD_LINE_HEAD = /^( *)(#{1,6}[ \t]+)?(?:(?:([-*+])|(\d+[.)]))[ \t]+(\[[ xX]\][ \t]+)?)?/;

  //: What a line (past any quote marker) already is: "h1".."h6", "ul", "ol",
  //: "task" or "".
  function mdLineKind(rest) {
    const m = MD_LINE_HEAD.exec(rest);
    if (m[2]) return `h${m[2].trim().length}`;
    if (m[4]) return "ol";
    if (m[3]) return m[5] ? "task" : "ul";
    return "";
  }

  function mdLinePrefixEdit(block, kind) {
    const [family, marker] = MD_LINE_KINDS[kind];
    const lines = block.split("\n");
    const live = lines.filter((line) => line.trim());
    const one = lines.length === 1;
    const split = (line) => {
      const lead = MD_LINE_QUOTE.exec(line)?.[0] || "";
      return [lead, line.slice(lead.length)];
    };
    const has = (line) => {
      const [lead, rest] = split(line);
      return family === "quote" ? Boolean(lead) : mdLineKind(rest) === kind;
    };
    const off = (live.length > 0 || one) && (live.length ? live : lines).every(has);
    let count = 0;
    return lines.map((line) => {
      if (!line.trim() && !one) return line;
      const [lead, rest] = split(line);
      if (family === "quote") return off ? rest : lead ? line : marker + line;
      const head = MD_LINE_HEAD.exec(rest)[0];
      const body = rest.slice(head.length);
      if (off) return lead + body;
      count += 1;
      const indent = family === "list" ? /^ */.exec(rest)[0] : "";
      return `${lead}${indent}${kind === "ol" ? `${count}. ` : marker}${body}`;
    }).join("\n");
  }

  //: **Image opens a picker** (audit 1028 U10; it used to drop a bare
  //: `![image](https://)` and leave the person to find a URL). The file goes to
  //: the media store as a pasted or imported picture does (`/media/upload`) and
  //: the embed is written where the caret was. The old stub is the fallback when
  //: the upload fails, so the button never ends in nothing.
  function docImagePick(box, boxId) {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = "image/*,video/mp4,video/webm,.mp4,.webm";
    input.addEventListener("change", () => {
      const file = input.files && input.files[0];
      if (file) docImageUpload(box, boxId, file);
    });
    input.click();
  }

  async function docImageUpload(box, boxId, file, said = "") {
    const { selectionStart: start, selectionEnd: end, value } = box;
    const alt = said || value.slice(start, end) || file.name.replace(/\.[^.]+$/, "") || "image";
    try {
      const form = new FormData();
      form.append("file", file);
      const uploaded = await apiJson("/media/upload", { method: "POST", headers: authHeaders(), body: form });
      if (!uploaded || !uploaded.url) throw new Error("no address");
      docUndoBreak();
      const at = Math.min(start, box.value.length);
      const embed = `![${alt}](${uploaded.url})`;
      box.value = `${box.value.slice(0, at)}${embed}${box.value.slice(Math.min(end, box.value.length))}`;
      box.setSelectionRange(at + embed.length, at + embed.length);
      finishMarkdownEdit(box, boxId);
    } catch {
      const before = box.value;
      docImageStub(box, boxId, start, end);
      const stubbed = box.value;
      //: Try again takes the stub back out first (if it is untouched), so the
      //: picture lands where the first try would have.
      const retry = () => {
        if (box.value === stubbed) {
          box.value = before;
          box.setSelectionRange(start, end);
        }
        docImageUpload(box, boxId, file, said);
      };
      toast(voiceLine("failed", { what: "upload that picture", why: "add its address by hand" }), true, { action: ["Try again", retry] });
    }
  }

  //: **A picture pasted into a markdown document asks what it shows** (audit
  //: 1028 D27). The upload and the embed were already there (settings-wiring.js'
  //: paste handler), with the file's own name for alt text, "image.png". On
  //: `window` in the capture phase so it runs ahead of that one, and only for a
  //: clipboard that is a picture and nothing else; a copy with words in it is
  //: the words' paste. An empty answer or Escape still adds the picture.
  window.addEventListener("paste", (event) => {
    const view = docCmView;
    if (!view || !view.dom.contains(event.target) || view.dom.classList.contains("doc-content-code") || view.state.readOnly) return;
    const data = event.clipboardData;
    if (!data || data.getData("text/plain")) return;
    const file = [...data.files].find((f) => f.type.startsWith("image/"));
    if (!file) return;
    event.preventDefault();
    event.stopPropagation();
    docImagePasteAsk(file);
  }, true);

  async function docImagePasteAsk(file) {
    const said = await promptDialog("Describe this picture (optional)", "", { confirmLabel: "Add picture" });
    await docImageUpload(docSurface(), "doc-content", file, said);
  }

  //: The address-by-hand form: the selection becomes the *alt text* and the
  //: caret lands on the URL, the same split `link` makes. (The first version
  //: passed the alt text as the body between the two markers and produced
  //: `![cat](cat)`: a picture whose address was its own caption.)
  function docImageStub(box, boxId, start, end) {
    const alt = box.value.slice(start, end) || "image";
    const url = "https://";
    box.value = `${box.value.slice(0, start)}![${alt}](${url})${box.value.slice(end)}`;
    const at = start + alt.length + 4;
    box.setSelectionRange(at, at + url.length);
    finishMarkdownEdit(box, boxId);
  }

  //: The `pre`/`post` actions (a pair around the selection): a second press takes the pair off.
  function mdApplyPair(box, boxId, action, selection) {
    const { start, end, value, selected } = selection;
    //: A second press takes the pair off, as Bold does: the selection sits
    //: inside the pair, or is the pair with its words.
    const post = action.post || "";
    if (selected && value.slice(start - action.pre.length, start) === action.pre && value.slice(end, end + post.length) === post) {
      box.value = value.slice(0, start - action.pre.length) + selected + value.slice(end + post.length);
      box.setSelectionRange(start - action.pre.length, end - action.pre.length);
      finishMarkdownEdit(box, boxId);
      return;
    }
    if (selected.length > action.pre.length + post.length && selected.startsWith(action.pre) && selected.endsWith(post)) {
      const bare = selected.slice(action.pre.length, selected.length - post.length);
      box.value = value.slice(0, start) + bare + value.slice(end);
      box.setSelectionRange(start, start + bare.length);
      finishMarkdownEdit(box, boxId);
      return;
    }
    const body = selected || action.placeholder || "";
    insertAround(box, start, end, action.pre, action.post || "", body, action.pre.length);
    finishMarkdownEdit(box, boxId);
  }

  //: The line, link, block and plain-insert actions: one edit, caret placed for the next keystroke.
  function mdApplyPlain(box, kind, action, selection) {
    const { start, end, value, selected } = selection;
    if (action.line) {
      // Every selected line, or the current one when nothing is selected.
      const lineStart = value.lastIndexOf("\n", start - 1) + 1;
      const lineEnd = end + (value.slice(end).indexOf("\n") === -1 ? 0 : value.slice(end).indexOf("\n"));
      const to = Math.max(lineEnd, end);
      const prefixed = mdLinePrefixEdit(value.slice(lineStart, to), kind);
      box.value = value.slice(0, lineStart) + prefixed + value.slice(to);
      box.setSelectionRange(lineStart, lineStart + prefixed.length);
    } else if (action.custom === "link") {
      const label = selected || "link text";
      const inserted = `[${label}](https://)`;
      box.value = value.slice(0, start) + inserted + value.slice(end);
      // Land the caret in the URL, which is the part you still have to type.
      const at = start + label.length + 3;
      box.setSelectionRange(at, at + 8);
    } else if (action.block) {
      const body = selected || action.placeholder;
      const inserted = action.block + body + action.suffix;
      box.value = value.slice(0, start) + inserted + value.slice(end);
      const at = start + action.block.length;
      box.setSelectionRange(at, at + body.length);
    } else if (action.insert) {
      box.value = value.slice(0, start) + action.insert + value.slice(end);
      const at = start + action.insert.length;
      box.setSelectionRange(at, at);
    }
  }

  function applyMarkdown(kind, boxId = "doc-content") {
    const action = MD_ACTIONS[kind];
    const box = docSurfaceById(boxId);
    if (!action || !box) return;
    //: A toolbar press is its own undo step, never part of the typing burst it
    //: happened to follow. Set *before* the edit, because the recording happens
    //: inside it (`finishMarkdownEdit` -> `markDocDirty`).
    docUndoBreak();
    const { selectionStart: start, selectionEnd: end, value } = box;
    const selected = value.slice(start, end);

    if (action.wrap) {
      wrapDocSelection(action.wrap, action.placeholder, boxId);
      return;
    }
    if (action.custom === "clearformat") {
      clearInlineFormatting(box);
      finishMarkdownEdit(box, boxId);
      return;
    }
    if (action.custom === "insert") {
      box.focus();
      editorOpenMenuByShortcut();
      return;
    }
    if (["emoji", "icon", "symbol"].includes(action.custom)) {
      //: Hung from the button that asked, in whichever strip it is (a strip
      //: without that tab's button hangs it from the emoji one); a button inside
      //: a closed Insert menu has no place, so the picker centres.
      const near = `:is([data-md="${action.custom}"], [data-md="emoji"])`;
      const anchor = document.querySelector(`[data-md-target="${boxId}"] ${near}`)
        || (boxId === "doc-content" ? document.querySelector(`#doc-toolbar ${near}`) : null);
      editorPickGlyph(box, anchor, action.custom);
      return;
    }
    if (action.custom === "calculator") {
      //: Over this box, so its Insert writes here; the same entry the palette's row uses.
      POPUP_TOOLS.find((tool) => tool.id === "calculator").open(box);
      return;
    }
    if (action.custom === "equation") {
      //: The guided equation editor (math-editor.js, DOCUMENTS_PLAN 16); from a
      //: closed Insert menu it centres, as the picker above does.
      openMathEditor({ target: box });
      return;
    }
    //: **Undo and redo go through the browser's own history, deliberately.**
    //: A textarea already has one, built from the user's typing *and* from
    //: `execCommand("insertText")`, and reimplementing it here would give the
    //: editor a second history that disagrees with Ctrl+Z, the one thing a
    //: user is certain about in any text box.
    if (action.custom === "undo" || action.custom === "redo") {
      box.focus();
      //: **The document editor has its own history now, and these buttons use
      //: it.** The paragraph above is still true everywhere else, the notes
      //: composer and the note edit form are one textarea each, so the browser's
      //: own stack is the right one and a second would only disagree with
      //: Ctrl+Z. The document editor is the case that broke the assumption, and
      //: it now has a real history of its own: CodeMirror's, where the engine is
      //: mounted, and the D3 snapshot stack at the end of this file where it is
      //: not. `docUndo` picks between them; this button must not reach past it
      //: to `execCommand`, which knows about neither.
      if (docToolsBoxFor(box)) {
        if (action.custom === "undo") docUndo();
        else docRedo();
        return;
      }
      document.execCommand(action.custom);
      finishMarkdownEdit(box, boxId);
      return;
    }
    if (action.custom === "indent" || action.custom === "outdent") {
      shiftDocIndent(box, action.custom === "indent" ? 1 : -1);
      finishMarkdownEdit(box, boxId);
      return;
    }
    if (action.custom === "image") {
      docImagePick(box, boxId);
      return;
    }
    if (action.custom === "properties") {
      docInsertProperties();
      return;
    }
    if (action.custom === "blockref" || action.custom === "syncedcopy" || action.custom === "syncedpaste") {
      docCopyBlockRef(action.custom === "blockref" ? "link" : action.custom === "syncedcopy" ? "copy" : "paste");
      return;
    }
    if (action.custom === "table") {
      //: Blank cells with their outer pipes, so every one of them is a cell GFM
      //: can see (`docTableFillRowEdits` carries the reason a blank last cell
      //: without a trailing pipe is not a cell at all).
      const table = "\n| Column | Column | Column |\n| --- | --- | --- |\n|  |  |  |\n|  |  |  |\n";
      box.value = value.slice(0, start) + table + value.slice(end);
      const at = start + table.indexOf("Column");
      box.setSelectionRange(at, at + "Column".length);
      finishMarkdownEdit(box, boxId);
      return;
    }
    if (action.custom === "annotate") {
      docAnnotateSelection(box, boxId);
      return;
    }
    if (action.custom === "cite") {
      //: A citation: the reference at the caret and the source at the foot (`docPairInput.citeInsert`).
      //: A note is picked and written as `[[title]]`; an address or words typed in the same box stay as typed.
      docPairInput.citePick().then((source) => {
        if (!source || !source.trim()) return;
        const done = docPairInput.citeInsert(box.value, end, end, source);
        box.value = done.value;
        box.setSelectionRange(done.caret, done.caret);
        finishMarkdownEdit(box, boxId);
      });
      return;
    }
    if (action.custom === "footnote") {
      //: A reference *and* its definition, because a footnote marker with
      //: nothing to point at renders as literal text and reads as a bug.
      const marker = `[^${docNextFootnote(value)}]`;
      box.value = `${value.slice(0, start)}${marker}${value.slice(end)}\n\n${marker}: `;
      const at = box.value.length;
      box.setSelectionRange(at, at);
      finishMarkdownEdit(box, boxId);
      return;
    }
    const selection = { start, end, value, selected };
    if (action.pre) {
      mdApplyPair(box, boxId, action, selection);
      return;
    }
    mdApplyPlain(box, kind, action, selection);
    finishMarkdownEdit(box, boxId);
  }

  //: Wrap a selection in two different markers, leaving the body selected so
  //: the next keystroke replaces a placeholder. `wrapDocSelection` above is the
  //: symmetric case and carries the toggle-off logic that only makes sense when
  //: both ends are the same string.
  function insertAround(box, start, end, pre, post, body, caretOffset) {
    const value = box.value;
    box.value = value.slice(0, start) + pre + body + post + value.slice(end);
    const at = start + caretOffset;
    box.setSelectionRange(at, at + body.length);
  }

  //: Two spaces per level, matching what this app's own markdown renderer and
  //: every list in it already use. Whole lines, so a selection spanning three
  //: bullets indents all three, the behaviour Tab has in Obsidian's editor.
  function shiftDocIndent(box, direction) {
    const { selectionStart: start, selectionEnd: end, value } = box;
    const lineStart = value.lastIndexOf("\n", start - 1) + 1;
    const tail = value.slice(end).indexOf("\n");
    const lineEnd = tail === -1 ? value.length : end + tail;
    const block = value.slice(lineStart, lineEnd);
    const shifted = block
      .split("\n")
      .map((line) =>
        direction > 0 ? `  ${line}` : line.replace(/^ {1,2}/, ""),
      )
      .join("\n");
    box.value = value.slice(0, lineStart) + shifted + value.slice(lineEnd);
    box.setSelectionRange(lineStart, lineStart + shifted.length);
  }

  //: The next free footnote number in this document. Counting the definitions
  //: rather than the references: a reference can appear twice and share one
  //: definition, which is what a footnote is for.
  function docNextFootnote(text) {
    const used = [...String(text || "").matchAll(/^\[\^(\d+)\]:/gm)].map((m) => Number(m[1]));
    return used.length ? Math.max(...used) + 1 : 1;
  }

  // The bookkeeping every toolbar edit ends with. The document editor has a
  // dirty flag and a live preview to refresh; the notes composer has neither,
  // but everything downstream of typing there (autogrow, the character count,
  // draft autosave) listens for `input`, which a programmatic value change does
  // not fire on its own.
  function finishMarkdownEdit(box, boxId) {
    box.focus();
    if (boxId === "doc-content") {
      markDocDirty();
      renderDocPreview();
    } else {
      box.dispatchEvent(new Event("input", { bubbles: true }));
    }
  }

  // Strip a highlight or a text colour from the selection. The counterpart to
  // the two colour pickers - asked for directly ("change the colour, or remove
  // the highlight"), and without it the only way back out of a colour was to
  // hand-delete the markers.
  function clearInlineFormatting(box) {
    const { selectionStart: start, selectionEnd: end, value } = box;
    const selected = value.slice(start, end);
    if (!selected) return;
    const cleaned = selected
      .replace(/==(?:[a-z]+\|)?([^=\n]+?)==/g, "$1")
      .replace(/\+\+[a-z]+\|([^+\n]+?)\+\+/g, "$1");
    if (cleaned === selected) return;
    box.value = value.slice(0, start) + cleaned + value.slice(end);
    box.setSelectionRange(start, start + cleaned.length);
  }

  // Wrap the selection in markdown syntax (Ctrl+B / Ctrl+I).
  function wrapDocSelection(marker, placeholder = "", boxId = "doc-content") {
    //: Reached both from `applyMarkdown` (which has already broken the burst)
    //: and directly from Ctrl+B / Ctrl+I / Ctrl+E, which have not. Idempotent, so
    //: setting it twice costs nothing and missing it would silently fold a Bold
    //: into the word you had just typed.
    docUndoBreak();
    const box = docSurfaceById(boxId);
    if (!box) return;
    const { selectionStart: start, selectionEnd: end, value } = box;

    // Toggle off, case 1: the selection sits *inside* an existing pair of
    // markers ("**|bold text|**", caret positions marked). Reported directly:
    // applying Bold to an already-bold selection didn't remove it the way
    // every other rich-text editor's toggle does: this was a one-way
    // "apply", never a toggle.
    const before = value.slice(Math.max(0, start - marker.length), start);
    const after = value.slice(end, end + marker.length);
    if (marker && before === marker && after === marker) {
      box.value =
        value.slice(0, start - marker.length) + value.slice(start, end) + value.slice(end + marker.length);
      box.selectionStart = start - marker.length;
      box.selectionEnd = end - marker.length;
      box.focus();
      finishMarkdownEdit(box, boxId);
      return;
    }
    // Toggle off, case 2: the markers themselves are part of the selection
    // ("|**bold text**|"), selecting the whole formatted span, not just its
    // inner text, is just as natural a way to select it for un-formatting.
    if (
      marker &&
      end - start >= marker.length * 2 &&
      value.slice(start, start + marker.length) === marker &&
      value.slice(end - marker.length, end) === marker
    ) {
      const inner = value.slice(start + marker.length, end - marker.length);
      box.value = value.slice(0, start) + inner + value.slice(end);
      box.selectionStart = start;
      box.selectionEnd = start + inner.length;
      box.focus();
      finishMarkdownEdit(box, boxId);
      return;
    }

    // With nothing selected, insert the placeholder and select it, so the next
    // keystroke replaces it: pressing Bold on an empty line should give you
    // somewhere to type, not two markers and a caret between them.
    const selected = value.slice(start, end) || placeholder;
    box.value = value.slice(0, start) + marker + selected + marker + value.slice(end);
    // Keep the same text selected, so the shortcut can be toggled or stacked.
    box.selectionStart = start + marker.length;
    box.selectionEnd = start + marker.length + selected.length;
    box.focus();
    //: **`finishMarkdownEdit`, not `markDocDirty()` + `renderDocPreview()`.**
    //: Both toggle-off branches above already end this way; this branch: the
    //: one that actually *applies* formatting, and so the one that runs almost
    //: every time: did the doc-content half inline instead, which quietly did
    //: the wrong thing for every other box: it marked the *document* dirty and
    //: never told the box's own listeners anything had changed.
    //:
    //: Found when the selection bar started appearing over live-view
    //: paragraphs. Bold visibly wrapped the words in the block and the document
    //: underneath never received them, measured, `input` fired 0 times, and
    //: dispatching one by hand synced it immediately. The same call was wrong
    //: for the note edit box for exactly as long, where it marked a document
    //: dirty that the user was not editing.
    finishMarkdownEdit(box, boxId);
  }

  //: The file's surface: what other files call (L-documents-117).
  Object.assign(window, { MD_ACTIONS, applyMarkdown, finishMarkdownEdit, wrapDocSelection });
})();
