// markdown.js: the markdown renderer and the block vocabulary. Moved out of
// app.js on 2026-09-26 as one contiguous range (INBOX 426 cc,
// docs/roadmap/agent-remaining/appjs-split.md). A classic script sharing
// app.js's globals, loaded in app.js's old order; nothing in an earlier file
// calls into it while the page loads (scratchpad/appjs-map.js --check).

// --- tiny markdown renderer (Round 1) -------------------------------------------
// Safe by construction: builds DOM with createElement/textContent, never
// innerHTML, so note/answer text can never inject markup. Supports the
// subset small local models actually emit: headings, bullet/numbered
// lists, fenced code, and inline **bold**/*italic*/`code`/[links].

// True when `line` looks like a GFM table separator row, e.g.
// "| --- | :---: |", the row that turns the line above it into a header.
function isTableSeparator(line) {
  const trimmed = line.trim();
  if (!trimmed.includes("-") || !/\|/.test(trimmed)) return false;
  const cells = splitTableRow(trimmed);
  return cells.length > 0 && cells.every((c) => /^:?-{1,}:?$/.test(c.trim()));
}

// Split one "| a | b |" row into its cell strings, tolerating (and
// stripping) the optional leading/trailing pipes. Escaped \| stays literal.
function splitTableRow(line) {
  const cells = [];
  let current = "";
  for (let k = 0; k < line.length; k++) {
    const ch = line[k];
    if (ch === "\\" && line[k + 1] === "|") {
      current += "|";
      k++;
    } else if (ch === "|") {
      cells.push(current);
      current = "";
    } else {
      current += ch;
    }
  }
  cells.push(current);
  // Drop the empty cells created by leading/trailing pipes.
  if (cells.length && cells[0].trim() === "") cells.shift();
  if (cells.length && cells[cells.length - 1].trim() === "") cells.pop();
  return cells;
}

// Column alignment from the separator row: ":--" left, "--:" right,
// ":-:" centre, else none.
function columnAlign(spec) {
  const s = spec.trim();
  const left = s.startsWith(":");
  const right = s.endsWith(":");
  if (left && right) return "center";
  if (right) return "right";
  if (left) return "left";
  return "";
}

// A heading's anchor id: lowercase, spaces to dashes, punctuation dropped.
//
// The document outline could already jump to a heading, but it did it by
// moving the caret in the textarea (jumpToDocLine): which works only inside
// the editor, and not at all for a link written into the text. Real ids mean a
// heading is addressable the way every other markdown tool assumes.
function mdHeadingId(text, taken) {
  const base =
    String(text)
      .toLowerCase()
      .replace(/[`*_~\[\]()]/g, "")
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "")
      .slice(0, 60) || "section";
  // Two headings can share a name ("Notes" under three chapters), and a
  // duplicate id makes every link to it resolve to the first one.
  if (!taken) return base;
  let id = base;
  let n = 2;
  while (taken.has(id)) id = `${base}-${n++}`;
  taken.add(id);
  return id;
}

// === The block vocabulary, as spellings ======================================
//
// INBOX 421 b: the "/" blocks had to become "an actual proper thing the
// user's can use to properly structure out their documents and notes". The
// storage format stays markdown, so every block below is a spelling in the
// text that any other markdown reader shows as something legible: a fenced
// div (`:::columns`, Pandoc's and markdown-it-container's), a rule, a quote,
// `[TOC]` (Typora's and Python-Markdown's), `$$` (every maths extension's).
// The parsing is pure string work in this marked region, so
// `tests/test_md_blocks.py` runs it in node, and every renderer (the note
// card, `renderMarkdown`, the document's Live view) asks the same functions
// rather than growing a dialect of its own.
//
// `docColumnsBlocks` in documents.js is the offset-keeping twin of
// `mdColumnsFrom` that the Live view needs (it maps columns back onto the
// editor's positions); both accept exactly the same three fence lines, which
// `tests/test_doc_columns.py` and this region's test each pin.

// MD-BLOCKS-BEGIN
const MD_COLS_OPEN = /^[ \t]*:::[ \t]*columns\b[ \t]*\d*[ \t]*$/i;
const MD_COLS_BREAK = /^[ \t]*:::[ \t]*column[ \t]*$/i;
const MD_COLS_CLOSE = /^[ \t]*:::[ \t]*$/;
const MD_CODE_FENCE = /^[ \t]*(?:```|~~~)/;
//: `[TOC]` alone on its line, any case. Not `[[toc]]`, which is a wiki link
//: to a note called "toc" and has to stay one.
const MD_TOC_LINE = /^[ \t]*\[toc\][ \t]*$/i;
const MD_RULE_LINE = /^\s*([-*_])(\s*\1){2,}\s*$/;
//: A quote's attribution is its last line, opened by `--`, an en dash or an
//: em dash (the last two written as escapes: the copy lint reads this file).
const MD_QUOTE_CITE = /^\s*(?:--|\u2014|\u2013)\s*(\S.*)$/;

//: The columns block that opens on `lines[start]`, or null. `columns` holds
//: each column's own text, `end` the index after the closing `:::`. An
//: unclosed block is somebody halfway through typing one and is not a block,
//: and a code fence wins: a `:::` inside one is an example of the syntax.
function mdColumnsFrom(lines, start) {
  if (!MD_COLS_OPEN.test(lines[start] || "")) return null;
  const columns = [[]];
  let fenced = false;
  for (let i = start + 1; i < lines.length; i += 1) {
    const line = lines[i];
    if (MD_CODE_FENCE.test(line)) fenced = !fenced;
    else if (!fenced && MD_COLS_BREAK.test(line)) {
      columns.push([]);
      continue;
    } else if (!fenced && MD_COLS_CLOSE.test(line)) {
      return { columns: columns.map((col) => col.join("\n")), end: i + 1 };
    } else if (!fenced && MD_COLS_OPEN.test(line)) {
      return null;
    }
    columns[columns.length - 1].push(line);
  }
  return null;
}

//: Which rule a divider line is: `---` a hairline, `***` (or `* * *`) the
//: three-dot section break, `___` the strong rule. All three are the one
//: `<hr>` everywhere else, so the variant costs nothing to take away.
function mdDividerKind(line) {
  const match = MD_RULE_LINE.exec(String(line || ""));
  if (!match) return null;
  return match[1] === "*" ? "dots" : match[1] === "_" ? "thick" : "line";
}

//: A quote's words and the name it is attributed to, when its last line is
//: `-- Name` and there is something before it to attribute.
function mdQuoteAttribution(quoted) {
  const lines = [...quoted];
  while (lines.length && !lines[lines.length - 1].trim()) lines.pop();
  const last = lines.length > 1 ? MD_QUOTE_CITE.exec(lines[lines.length - 1]) : null;
  if (!last) return { body: quoted, cite: null };
  return { body: lines.slice(0, -1), cite: last[1].trim() };
}

//: The headings a `[TOC]` lists, outside code fences, as level and text.
function mdTocEntries(text) {
  const entries = [];
  let fenced = false;
  for (const line of String(text || "").split("\n")) {
    if (MD_CODE_FENCE.test(line)) {
      fenced = !fenced;
      continue;
    }
    if (fenced) continue;
    const heading = /^(#{1,6})\s+(.*\S)\s*$/.exec(line);
    if (heading) entries.push({ level: heading[1].length, text: heading[2].replace(/\s+#+$/, "") });
  }
  return entries;
}

//: A display maths block opening on `lines[start]`: `$$` alone on its line
//: down to the next `$$`, or `$$ ... $$` on one line. Prices (`$5 and $10`)
//: never open one: the opener is two dollars, alone or around the whole line.
function mdMathBlockFrom(lines, start) {
  const line = String(lines[start] || "").trim();
  const single = /^\$\$(.+)\$\$$/.exec(line);
  if (single && single[1].trim()) return { tex: single[1].trim(), end: start + 1 };
  if (line !== "$$") return null;
  const body = [];
  for (let i = start + 1; i < lines.length; i += 1) {
    if (lines[i].trim() === "$$") return { tex: body.join("\n").trim(), end: i + 1 };
    body.push(lines[i]);
  }
  return null;
}

//: A callout's first quoted line, `[!kind]` with its fold flag and title, or
//: null. The kind is resolved through `calloutKindOf` (editor.js), so
//: Obsidian's aliases (`caution`, `tldr`, `done`) land on their kind; an
//: unknown kind is still a box, drawn as a note, because a typo should look
//: slightly wrong rather than broken.
function mdCalloutHead(line) {
  const match = /^\s*\[!([\w-]+)\]([-+])?\s*(.*)$/.exec(String(line || ""));
  if (!match) return null;
  const known = typeof calloutKindOf === "function" ? calloutKindOf(match[1]) : null;
  return { kind: known || "note", raw: match[1], fold: match[2] || "", title: match[3].trim() };
}
// MD-BLOCKS-END

// The two block-level constructs the "/" menu inserts, built once and shared.
//
// They live outside renderMarkdown because **notes do not go through
// renderMarkdown at all**: a note card is rendered by renderNoteText, which
// is an inline pass (wiki links + emphasis + search-term highlighting). That
// asymmetry is easy to miss and was: the first live check of this feature
// found callouts and embeds rendering perfectly in a document and not at all
// in a note, which is half the feature missing in the surface people use most.

// A `.callout` element for a run of blockquote lines, or null when the quote
// is an ordinary one (no `[!kind]` marker) or nesting is already too deep.
function mdCalloutElement(quoted, depth) {
  // **The `-`/`+` after the marker is the fold flag**, REDESIGN.md §R7.3
  // item 3, Kortex's "typed collapsible blocks", asked for again directly:
  // "I want the structured note features and elements from kortex with the
  // slash commands to be rendered and easier for the user to use."
  //
  // It is deliberately Obsidian's own spelling rather than a new one: people
  // who want this feature have almost certainly met it there, and it is a
  // *marker*, so §R7.3's constraint holds exactly, storage and export do not
  // change, and a plain `> [!note]` in a note written last year still renders
  // as the same open box it always did.
  //
  //     > [!note]-  collapsed, click to open
  //     > [!note]+  a real fold, but open to begin with
  //     > [!note]   not foldable at all, unchanged
  const callout = quoted.length ? mdCalloutHead(quoted[0]) : null;
  if (!callout || depth >= MD_MAX_DEPTH) return null;

  const kind = callout.kind;
  //: A toggle is a fold by definition: written without a flag it starts
  //: closed, the way Notion's does.
  const fold = callout.fold || (kind === "toggle" ? "-" : "");
  const meta = (typeof CALLOUT_KINDS !== "undefined" && CALLOUT_KINDS[kind]) || null;
  // `<details>`/`<summary>` rather than a div and a click handler: the
  // browser gives the open/close, the keyboard operation and the ARIA for
  // free, which is the same reason every other disclosure in this app is one.
  const box = document.createElement(fold ? "details" : "div");
  if (fold === "+") box.open = true;
  // An unrecognised kind still renders as a box rather than as literal
  // "[!whatever]" text: a typo should look slightly wrong, not broken.
  box.className = `callout callout-${kind}${fold ? " callout-foldable" : ""}`;
  //: What the block toolbar reads to change the kind or the fold in place
  //: (`docBlockBar`, documents.js): the kind as the text spells it is not
  //: needed, only what it resolved to.
  box.dataset.calloutKind = kind;
  box.dataset.calloutFold = callout.fold;

  const head = document.createElement(fold ? "summary" : "p");
  head.className = "callout-head";
  //: The kind's icon, drawn from the vendored set like every other icon in
  //: the app, in a tile of the kind's own tint so the head reads as the
  //: block's badge rather than as a glyph in the sentence.
  const icon = document.createElement("span");
  icon.className = "callout-icon";
  icon.setAttribute("aria-hidden", "true");
  const glyph = document.createElement("i");
  glyph.className = `ph ph-${String(meta ? meta.icon : "ph:note").replace(/^ph:/, "")}`;
  icon.appendChild(glyph);
  head.appendChild(icon);
  const title = document.createElement("span");
  title.className = "callout-title";
  // The title after the marker wins; failing that, the kind's own name.
  appendInline(title, callout.title || (meta ? meta.label : kind));
  head.appendChild(title);
  box.appendChild(head);

  const body = document.createElement("div");
  body.className = "callout-body";
  // Rendered rather than inlined, so a callout can hold a list, a code block
  // or a link: which is most of why it beats a bold paragraph.
  renderMarkdown(body, quoted.slice(1).join("\n"), depth + 1);
  box.appendChild(body);
  return box;
}

//: **The other blocks, one builder each, shared by every renderer.** The note
//: card (`renderNoteText`), `renderMarkdown` and the document's Read view all
//: call these, each passing the function that renders a piece of text *its*
//: way (the note card keeps its search highlighting, the page renderer its
//: full grammar), so a block cannot look one way in a note and another in a
//: document.

//: Columns: the same `.doc-cols` grid the document editor's Live view draws
//: (09-editor.css), so all three places agree about what a column is.
function mdColumnsElement(columns, renderInto) {
  const box = document.createElement("div");
  //: The count as a class as well as the variable: an exported file loses
  //: every style attribute (`docExportClean`), and its stylesheet reads this.
  box.className = `doc-cols md-cols md-cols-${columns.length}`;
  box.style.setProperty("--doc-cols", String(Math.max(1, columns.length)));
  for (const text of columns) {
    const col = document.createElement("div");
    col.className = "doc-col";
    renderInto(col, text);
    box.appendChild(col);
  }
  return box;
}

//: `\newpage`, a page break (DOCUMENTS_PLAN decision 20.5).
const MD_PAGE_BREAK = /^[ \t]*\\newpage[ \t]*$/;

function mdPageBreakElement() {
  const el = document.createElement("div");
  el.className = "md-page-break";
  el.setAttribute("role", "separator");
  el.setAttribute("aria-label", "Page break");
  const label = document.createElement("span");
  label.textContent = "Page break";
  el.appendChild(label);
  return el;
}

//: A rule of the kind `mdDividerKind` read.
function mdRuleElement(kind) {
  const hr = document.createElement("hr");
  hr.className = `md-rule md-rule-${kind}`;
  return hr;
}

//: A quote, or a figure of a quote and its attribution.
function mdQuoteElement(quoted, fillBody) {
  const cited = mdQuoteAttribution(quoted);
  const bq = document.createElement("blockquote");
  fillBody(bq, cited.body);
  if (!cited.cite) return bq;
  const figure = document.createElement("figure");
  figure.className = "md-quote";
  const caption = document.createElement("figcaption");
  caption.className = "md-quote-cite";
  appendInline(caption, cited.cite);
  figure.append(bq, caption);
  return figure;
}

//: Maths, display or inline. The TeX goes to `docMathRender` when the
//: documents bundle is loaded; otherwise the source is shown, set as
//: maths, and the bundle is asked for so the next render draws it.
function mdMathBox(tag, className, tex, display) {
  const box = document.createElement(tag);
  box.className = className;
  box.dataset.tex = tex;
  if (typeof docMathRender === "function") {
    try {
      box.appendChild(docMathRender(tex, display));
      return box;
    } catch {
      // A formula the renderer cannot parse shows as its source below.
    }
  }
  const source = document.createElement("code");
  source.className = "md-math-source";
  source.textContent = tex;
  box.appendChild(source);
  //: Not a silent guard: the bundle that draws maths is asked for, and the
  //: box redraws itself in place once it lands (a note card or a chat
  //: answer can be the first thing on screen with a formula in it).
  if (typeof ensureModule === "function") {
    ensureModule("library")
      .then(() => {
        if (!box.isConnected || typeof docMathRender !== "function") return;
        try {
          box.replaceChildren(docMathRender(tex, display));
        } catch {
          // The source stays.
        }
      })
      .catch(() => {});
  }
  return box;
}

//: Display maths, `$$…$$`.
function mdMathElement(tex) {
  return mdMathBox("div", "md-math-block", tex, true);
}

//: Inline maths, `$x$` (INBOX 423c): the same renderer as `mdMathElement`,
//: a `span` instead of a `div` so it sits in a run of prose rather than
//: breaking it onto its own line.
function mdInlineMathElement(tex) {
  return mdMathBox("span", "md-math-inline", tex, false);
}

//: `[TOC]`, drawn empty and filled by `mdFillTocs` once the headings exist.
function mdTocElement() {
  const nav = document.createElement("nav");
  nav.className = "md-toc";
  nav.setAttribute("aria-label", "Contents");
  const head = document.createElement("p");
  head.className = "md-toc-head";
  setLabel(head, "ph:list-dashes Contents");
  nav.appendChild(head);
  const list = document.createElement("ol");
  list.className = "md-toc-list";
  nav.appendChild(list);
  return nav;
}

//: **Fill every contents block from the headings actually rendered around
//: it.** Read from the page rather than from the text, because the page is
//: what the links have to land on: the ids are the ones `mdHeadingId` gave,
//: including the `-2` a second "Notes" heading gets. A link is a real
//: `#id` (so it still works in an exported file) that scrolls its heading
//: into view here rather than changing the address the app runs at.
function mdFillTocs(container) {
  const tocs = container.querySelectorAll(".md-toc");
  if (!tocs.length) return;
  const headings = [...container.querySelectorAll("h3, h4, h5, h6")].filter(
    (h) => h.id && !h.closest(".md-toc, .note-embed, .callout")
  );
  const levelOf = (h) => {
    const typed = /md-h(\d)/.exec(h.className);
    return typed ? Number(typed[1]) : Number(h.tagName[1]) - 2;
  };
  const top = headings.length ? Math.min(...headings.map(levelOf)) : 1;
  for (const toc of tocs) {
    const list = toc.querySelector(".md-toc-list");
    if (!list) continue;
    list.replaceChildren();
    for (const heading of headings) {
      const item = document.createElement("li");
      item.className = `md-toc-item md-toc-depth-${Math.min(3, levelOf(heading) - top)}`;
      const link = document.createElement("a");
      link.href = `#${heading.id}`;
      link.textContent = heading.textContent;
      link.addEventListener("click", (event) => {
        event.preventDefault();
        const target = container.querySelector(`#${CSS.escape(heading.id)}`) || heading;
        target.scrollIntoView({ block: "start", behavior: reducedMotionWanted() ? "auto" : "smooth" });
      });
      item.appendChild(link);
      list.appendChild(item);
    }
    if (!headings.length) {
      const empty = document.createElement("li");
      empty.className = "md-toc-empty";
      empty.textContent = "Headings you add appear here.";
      list.appendChild(empty);
    }
  }
}

// MD-FOOTNOTE-BEGIN
//: Footnotes (audit FEAT-03, DOCUMENTS_PLAN decision 20.1): definitions
//: blanked out, cited references made placeholders; tests/test_md_footnotes.py.
const MD_FN_DEF = /^\[\^([^\]\s]{1,40})\]:[ \t]?(.*)$/;
const MD_FN_REF = /\[\^([^\]\s]{1,40})\]/g;
const MD_FN_FENCE = /^\s*(?:```|~~~)/;

function mdFootnotePrepare(lines) {
  const defs = new Map();
  const out = lines.slice();
  const each = (fn) => {
    let fenced = false;
    for (let i = 0; i < out.length; i++) {
      if (MD_FN_FENCE.test(out[i])) fenced = !fenced;
      else if (!fenced) i = fn(i) ?? i;
    }
  };
  each((i) => {
    const def = MD_FN_DEF.exec(out[i]);
    if (!def || defs.has(def[1])) return;
    const body = [def[2]];
    out[i] = "";
    while (/^(?: {2,}|\t)\S/.test(out[i + 1] || "")) {
      body.push(out[++i].trim());
      out[i] = "";
    }
    defs.set(def[1], body.join(" ").trim());
    return i;
  });
  if (!defs.size) return { lines, notes: [] };
  const order = [];
  each((i) => {
    out[i] = out[i].replace(MD_FN_REF, (whole, id) => {
      if (!defs.has(id)) return whole;
      if (!order.includes(id)) order.push(id);
      return `${id}`;
    });
  });
  for (const id of defs.keys()) if (!order.includes(id)) order.push(id);
  return { lines: out, notes: order.map((id, k) => ({ id, n: k + 1, text: defs.get(id) })) };
}
// MD-FOOTNOTE-END

//: A prefix per render, so two documents on one page share no id.
let mdFootnoteRuns = 0;

function mdFootnotesFinish(container, notes) {
  if (!notes.length) return;
  const run = ++mdFootnoteRuns;
  const byId = new Map(notes.map((note) => [note.id, note]));
  const anchor = (kind, id) => `fn${kind}-${run}-${id.replace(/[^\w-]/g, "_")}`;
  const marker = /([^]+)/g;
  const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);
  const hits = [];
  while (walker.nextNode()) if (walker.currentNode.nodeValue.includes("")) hits.push(walker.currentNode);
  const cited = new Set();
  for (const node of hits) {
    const value = node.nodeValue;
    if (node.parentElement?.closest("code, pre")) {
      node.nodeValue = value.replace(marker, "[^$1]");
      continue;
    }
    const frag = document.createDocumentFragment();
    let last = 0;
    for (const m of value.matchAll(marker)) {
      const n = byId.get(m[1])?.n ?? m[1];
      const sup = document.createElement("sup");
      sup.className = "md-fn-ref";
      const link = document.createElement("a");
      link.href = `#${anchor("", m[1])}`;
      link.textContent = n;
      link.setAttribute("aria-label", `Footnote ${n}`);
      if (!cited.has(m[1])) link.id = anchor("ref", m[1]);
      cited.add(m[1]);
      sup.appendChild(link);
      frag.append(value.slice(last, m.index), sup);
      last = m.index + m[0].length;
    }
    frag.append(value.slice(last));
    node.replaceWith(frag);
  }
  const section = document.createElement("section");
  section.className = "md-footnotes";
  section.setAttribute("aria-label", "Footnotes");
  const list = document.createElement("ol");
  for (const note of notes) {
    const item = document.createElement("li");
    item.id = anchor("", note.id);
    appendInline(item, note.text);
    if (cited.has(note.id)) {
      const back = document.createElement("a");
      back.className = "md-fn-back";
      back.href = `#${anchor("ref", note.id)}`;
      back.textContent = "Back";
      back.setAttribute("aria-label", `Back to reference ${note.n}`);
      item.append(" ", back);
    }
    list.appendChild(item);
  }
  section.appendChild(list);
  container.appendChild(section);
  //: Jump in place (`mdFillTocs`'s rule); an exported file uses the `#id`.
  if (container.mdFnJump) return;
  container.mdFnJump = true;
  container.addEventListener("click", (event) => {
    const link = event.target.closest?.("a[href^='#fn']");
    const target = link && container.querySelector(`#${CSS.escape(link.getAttribute("href").slice(1))}`);
    if (!target) return;
    event.preventDefault();
    target.scrollIntoView({ block: "center", behavior: reducedMotionWanted() ? "auto" : "smooth" });
  });
}

//: **An embedded document is a card, not a link** (INBOX 421 b: "embed of a
//: note/document/board by link (renders a card)"). It was one underlined
//: title. Now: the document's tile, its title, one facts line (words, when it
//: was last edited) and the first words of it, from the list payload the app
//: already holds (`_summary` carries `preview`), so drawing it costs no
//: request. The whole card is one button, the board embed's rule: the card is
//: what the eye and the finger both go for. The Live view draws the same card
//: (`docEmbedNode`, documents.js).
function mdDocumentCard(doc, name = "") {
  const card = document.createElement("button");
  card.type = "button";
  card.className = "embed-card";
  card.title = "Open this document";
  const tile = document.createElement("span");
  tile.className = "embed-card-tile";
  tile.setAttribute("aria-hidden", "true");
  const glyph = document.createElement("i");
  glyph.className = "ph ph-file-text";
  tile.appendChild(glyph);
  const text = document.createElement("span");
  text.className = "embed-card-text";
  const title = document.createElement("span");
  title.className = "embed-card-title";
  title.textContent = (doc && doc.title) || wikiLinkLabel(name) || "Untitled";
  const facts = document.createElement("span");
  facts.className = "embed-card-meta";
  const bits = ["Document"];
  if (doc && Number.isFinite(doc.words)) bits.push(nounCount(doc.words, "word"));
  if (doc && doc.updated_at) {
    const when = new Date(doc.updated_at);
    if (!Number.isNaN(when.getTime())) bits.push(`edited ${when.toLocaleDateString()}`);
  }
  facts.textContent = bits.join(" · ");
  text.append(title, facts);
  if (doc && doc.preview) {
    const preview = document.createElement("span");
    preview.className = "embed-card-preview";
    preview.textContent = clipText(String(doc.preview).replace(/[#>*_`[\]]/g, ""), 180);
    text.appendChild(preview);
  }
  const go = document.createElement("i");
  go.className = "ph ph-arrow-square-out embed-card-go";
  go.setAttribute("aria-hidden", "true");
  card.append(tile, text, go);
  card.addEventListener("click", (event) => {
    event.stopPropagation();
    if (doc && doc.id != null) openDocument(doc.id);
  });
  return card;
}

// A `.note-embed` element for `![[name]]`.
function mdEmbedElement(name, depth) {
  //: **A board or a map is not text to transclude, it is a picture** (INBOX
  //: 309). Everything else a note can embed is words, and the card below
  //: renders those words inline; a whiteboard has no words to inline, so
  //: this branch draws the same miniature the Library and the dashboard
  //: draw and makes it the way in.
  //:
  //: Both spellings land here, because both already exist in real notes:
  //: `![[board:12|House jobs]]`, which the "/" menu writes, and a plain
  //: `![[House jobs]]` that happens to name a board, which `resolveWikiTarget`
  //: has resolved to a board since the map chips were built and which this
  //: function then rendered as "Nothing called House jobs yet" (measured on
  //: 8793 before this change: the embed of a live board claimed it did not
  //: exist).
  const ref = boardEmbedRef(name);
  const named = ref ? null : resolveWikiTarget(name);
  if (ref) return boardEmbedElement(ref);
  if (named && named.kind === "board") {
    return boardEmbedElement({
      id: named.entry.id,
      title: named.entry.title || String(name || "").trim(),
      map: named.entry.type !== "board",
    });
  }

  const box = document.createElement("div");
  box.className = "note-embed";

  const head = document.createElement("p");
  head.className = "note-embed-head";
  const marker = document.createElement("i");
  marker.className = "ph ph-paperclip";
  marker.setAttribute("aria-hidden", "true");
  head.append(marker, document.createTextNode(` Embedded: ${name}`));
  box.appendChild(head);

  const body = document.createElement("div");
  body.className = "note-embed-body";
  const target = named;
  if (depth >= MD_MAX_DEPTH) {
    // A embeds B embeds A. The cap is what stops that hanging the tab, and
    // saying so beats rendering nothing and looking like a bug.
    body.textContent = "…(embedded too deep to show)";
  } else if (target && target.kind === "note") {
    renderMarkdown(body, target.entry.content || "", depth + 1);
  } else if (target && target.kind === "document") {
    // Documents have no content in the list payload (routes_documents._summary),
    // so this is a way in rather than an inline copy. See renderMarkdown's own
    // note on why a fetch does not belong in this path.
    body.appendChild(mdDocumentCard(target.doc, name));
  } else {
    body.textContent = `Nothing called \u{201C}${name}\u{201D} yet.`;
  }
  box.appendChild(body);
  return box;
}

//: **A whiteboard or a mind map, living in a note as an object** (INBOX 309).
//:
//: One card, drawn from the one preview renderer this app has
//: (`mapPreview`), so a board looks the same in a note as it does in the
//: Library and on the dashboard. MINDMAP_PLAN §5 item 12's rule, which this
//: is the fourth surface to keep: "One `mapChip()` and one `mapPreview()`,
//: used by all of them: the app's recurring failure is the same object drawn
//: five ways."
//:
//: The whole card is one `<button>`. A picture with a separate "open" link
//: beside it is two tab stops for one action, and the picture is the thing
//: the eye and the finger both go for; making the card itself the control is
//: what `mapChip` already does for the chip-sized version of this.
//:
//: **The card is filled twice when the index is not loaded yet.** `mapPreview`
//: draws from `/whiteboard/boards` (`loadMapBoardIndex`), which a document or
//: a chat transcript has usually never asked for, and this function is
//: synchronous because it runs inside a render pass. So an unloaded index
//: draws the resting card, asks for the index, and fills in place. It cannot
//: loop: `loadMapBoardIndex` de-duplicates and caches for eight seconds.
//: The board ids a forced index refresh has been asked about: a promise while
//: that walk is in flight, `true` once it answered without finding the board.
//: See `fill` below: this is what keeps a dead reference from costing a
//: request per render, and what lets a second render of the same note wait on
//: the walk the first one started instead of calling its card a tombstone.
const boardEmbedForced = new Map();

function boardEmbedElement(ref) {
  const box = document.createElement("div");
  box.className = "note-embed board-embed";
  //: The id this card points at, so a sweep (and a reader with the inspector
  //: open) can tell which board a preview claims to be without reading the
  //: note's source.
  box.dataset.boardRef = String(ref.id || "");
  //: **A miss is not a tombstone until the index has been asked again.**
  //: `mapBoardIndexCache` is eight seconds old at most but is only *rebuilt*
  //: when something asks for it, so a board made after this session's index
  //: was built is missing from it: drawing "this board is no longer in your
  //: notebook" over a board somebody created a minute ago is the worst thing
  //: this card could say. So a miss asks once more, with the index refreshed,
  //: and only then writes the tombstone. `final` is what tells the two apart,
  //: and it cannot loop: the retry always passes true.
  const fill = (final) => {
    const found = boardEmbedFill(box, ref, final);
    if (found) {
      //: It is here after all, so a later deletion gets its own forced look
      //: rather than inheriting this one's answer.
      boardEmbedForced.delete(ref.id);
      return;
    }
    if (final) return;
    //: A reference a forced refresh has already failed to find is not asked
    //: about again: without this, every re-render of a note holding a dead
    //: object would walk `/whiteboard/boards` from the top.
    if (typeof loadMapBoardIndex !== "function") {
      fill(true);
      return;
    }
    let walk = boardEmbedForced.get(ref.id);
    if (walk === true) {
      fill(true);
      return;
    }
    //: **A walk still in flight is waited on, not read as an answer.** The
    //: list re-renders a note a few milliseconds after drawing it (a second
    //: `loadEntries`, a poll), and that second card used to find the id
    //: already marked, skip the wait and write the tombstone while the
    //: walk that would have found the board was still on the wire; the first
    //: card, the one that was waiting, had already left the page. Measured
    //: (`noteobject.js`): a board made a second earlier drawn as "no longer
    //: in your notebook" in the note that holds it, every run.
    if (!walk) {
      walk = loadMapBoardIndex(true)
        .catch(() => null)
        .then(() => {
          boardEmbedForced.set(ref.id, true);
        });
      boardEmbedForced.set(ref.id, walk);
    }
    walk.then(() => fill(true));
  };
  fill(false);
  return box;
}

function boardEmbedFill(box, ref, final) {
  const board = boardEmbedTarget(ref);
  box.replaceChildren();
  box.classList.toggle("board-embed-gone", !board && final);

  if (!board && !final) {
    //: **Not the tombstone.** "We have not looked yet" and "it is gone" are
    //: different facts, and printing the second while the first is true is
    //: how a working board gets reported as deleted.
    const waiting = document.createElement("p");
    waiting.className = "note-embed-head";
    setLabel(waiting, `${ref.map ? "ph:tree-structure" : "ph:squares-four"} ${ref.title || "Loading\u2026"}`);
    box.appendChild(waiting);
    return null;
  }

  if (!board) {
    //: **A tombstone, not a disappearance** (the decision recorded in
    //: DOCUMENTS_PLAN's "Decisions made"). A board deleted after it was put
    //: in a note would otherwise take a paragraph of that note with it, and
    //: the reader would never learn that anything had been there: content
    //: that vanishes silently is worse than content that says it is gone.
    //: The title the reference carries is exactly what makes this sentence
    //: worth reading.
    const head = document.createElement("p");
    head.className = "note-embed-head";
    setLabel(head, "ph:trash Removed");
    const what = document.createElement("p");
    what.className = "board-embed-title";
    what.textContent = ref.title || (ref.map ? "A mind map" : "A whiteboard");
    const why = document.createElement("p");
    why.className = "library-file-meta board-embed-meta";
    why.textContent = "This board is no longer in your notebook.";
    box.append(head, what, why);
    return null;
  }

  const isMap = board.type !== "board";
  const title = board.title || ref.title || (isMap ? "Untitled map" : "Untitled board");
  const open = document.createElement("button");
  open.type = "button";
  open.className = "board-embed-open";
  open.title = `Open \u201c${title}\u201d`;

  const head = document.createElement("span");
  head.className = "note-embed-head";
  setLabel(head, `${isMap ? "ph:tree-structure" : "ph:squares-four"} ${isMap ? "Mind map" : "Whiteboard"}`);

  const body = document.createElement("span");
  body.className = "board-embed-body";
  const picture = mapPreview(board, { size: "card" });
  picture.classList.add("board-embed-picture");
  const text = document.createElement("span");
  text.className = "board-embed-text";
  const name = document.createElement("span");
  name.className = "board-embed-title";
  name.textContent = title;
  //: The facts line recipe (DESIGN.md), the same sentence the Library card
  //: and the dashboard row carry under the same picture.
  const meta = document.createElement("span");
  meta.className = "library-file-meta board-embed-meta";
  meta.textContent = mapCountLabel(board);
  text.append(name, meta);
  body.append(picture, text);
  open.append(head, body);
  open.addEventListener("click", (event) => {
    //: The note card underneath is itself clickable (it expands), so a press
    //: meant for the board must not also open the note.
    event.stopPropagation();
    openWhiteboardBoard(board.id);
  });
  box.appendChild(open);
  return board;
}

//: The reference a note carries for one board, the one place the text form is
//: written. Read by the "/" menu and by the board's own "Add to a note", so
//: the two cannot write two different spellings of the same object.
function boardEmbedMarkdown(board) {
  const isMap = board?.type !== "board";
  const title = String(board?.title || (isMap ? "Untitled map" : "Untitled board"))
    .replace(/[[\]|]/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 80);
  return `![[${isMap ? "map" : "board"}:${board?.id}|${title}]]`;
}

//: How deep a callout or an embed may nest before rendering stops.
//
// Both recurse into renderMarkdown, so both can loop: a callout containing a
// callout is legitimate and useful, but note A embedding note B embedding note
// A is an infinite regress that would hang the tab. The cap is generous enough
// that no honest document reaches it and low enough that a cycle costs
// nothing.
const MD_MAX_DEPTH = 4;

//: **Wrap or scroll, per card** (the owner, 2026-10-27: "can you add a button
//: to toggle wrap text in tables or code blocks??"). A wide table or a long
//: code line scrolls sideways in a reply, which is right for code you mean to
//: paste and wrong for prose in a cell, and only the reader knows which this
//: is. So the head of a code or table card holds one icon toggle beside Copy
//: (the card head's recipe, DESIGN.md), `aria-pressed` while wrapping, and a
//: press is remembered per kind (`wrap-code`, `wrap-table`) for the cards
//: drawn afterwards. Scrolling is the default. `paint` is the only writer of
//: the button's state, so the pressed look and its title cannot disagree;
//: `keep()` lets a surface that starts somewhere else (a table's full view,
//: which starts fitted) press without changing what the next card starts as.
function wrapToggle(kind, apply, keep = () => true) {
  const key = `wrap-${kind}`;
  const button = document.createElement("button");
  button.type = "button";
  button.className = "ghost small icon-only code-copy wrap-toggle";
  setLabel(button, "ph:text-align-left");
  //: A toggle keeps one name and says its state in `aria-pressed`; the title
  //: is the sighted reader's hint of what a press does.
  button.setAttribute("aria-label", "Wrap lines");
  const paint = (on) => {
    button.setAttribute("aria-pressed", String(on));
    button.title = on ? "Don't wrap" : "Wrap lines";
  };
  button.addEventListener("click", () => {
    const on = button.getAttribute("aria-pressed") !== "true";
    paint(on);
    apply(on);
    if (keep()) prefs.set(key, on ? "1" : "0");
  });
  return { button, paint, remembered: () => prefs.bool(key, false) };
}

//: **A table the model wrote is something you can take away** (INBOX 172:
//: "export, copy, or save etc things such as tables, code blocks etc that
//: the ai generates ... scrollable tables in responses are good but
//: sometimes hard or annoying to read, maybe the user can toggle how to
//: view the table"). The same bar the code blocks wear: Copy puts
//: tab-separated cells on the clipboard (what a spreadsheet pastes), Markdown
//: copies the table as written, CSV saves it through the exports route, and
//: Full view lifts the block into a viewport-sized panel (Escape or the same
//: button puts it back) so a wide table reads without the bubble's scroll.
function buildTableBlock(scroller, headers, bodyRows, rawTable) {
  const block = document.createElement("div");
  block.className = "code-block md-table-block";
  const bar = document.createElement("div");
  bar.className = "code-bar";
  const label = document.createElement("span");
  label.className = "code-lang";
  label.textContent = bodyRows.length ? `table · header and ${nounCount(bodyRows.length, "row")}` : "table · header only";
  const cells = (row) => headers.map((_, c) => (row[c] || "").trim());
  const rows = [cells(headers), ...bodyRows.map(cells)];
  const tsv = rows.map((row) => row.map((v) => v.replace(/\t/g, " ")).join("\t")).join("\n");
  const csv = rows.map((row) => row.map((v) => `"${v.replace(/"/g, '""')}"`).join(",")).join("\n");
  const button = (text, title, onClick) => {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "ghost small code-copy";
    //: `setLabel`, not `textContent`: the Copy button here said "⧉ Copy", a
    //: typed glyph standing where an icon belongs while the app ships
    //: `ph:copy` and uses it in five other places
    //: (`tests/test_no_glyph_icons.py` names the fault and now names this
    //: glyph). A label with no `ph:` marker comes through unchanged, so the
    //: bar's other buttons are untouched.
    setLabel(b, text);
    b.title = title;
    if (onClick) b.addEventListener("click", onClick);
    return b;
  };
  //: **Fit, or actual size** (INBOX 179: "I want the full view tables to not
  //: be scrollable and to instead adjust the size to fit the panel and for
  //: the full size scrollable view to be togglable"). Fit is the default:
  //: `table-layout: fixed` with wrapped cells, so every column is on screen
  //: and nothing scrolls sideways. The toggle puts the table back at its
  //: natural width, where the panel scrolls as before.
  //: **The reader sets the column widths and the row heights** (INBOX 181,
  //: the owner: "I want the table row and column widths and heights to be
  //: adjustable by the user in the full view"). A grip on every header cell's
  //: right edge and on every body row's bottom edge, in full view only: in a
  //: bubble the table is a few hundred pixels wide and there is nothing to
  //: apportion, and grips on a block that scrolls with the conversation would
  //: be six pixels of drag target next to a wheel.
  //:
  //: The sizes live on this closure, so they last as long as the answer does:
  //: leaving full view puts the table back to the surface's own default and
  //: returning restores what was dragged, which is what "for the session"
  //: means for a block that is rebuilt whenever its answer is re-rendered.
  const tableEl = scroller.querySelector("table");
  const headCells = () => [...tableEl.querySelectorAll("thead th")];
  const bodyRowEls = () => [...tableEl.querySelectorAll("tbody tr")];
  //: A column narrower than this cannot show a word and a row shorter than
  //: this cannot show a line, so neither is a size anybody meant to choose.
  const MIN_COL = 56;
  const MIN_ROW = 28;
  let colSizes = null;
  let rowSizes = null;

  const applyTableSizes = () => {
    if (!colSizes && !rowSizes) return;
    //: `table-layout: fixed` is what makes an explicit width authoritative:
    //: under `auto` the browser treats a width as a suggestion and widens a
    //: column whose content does not fit, which is exactly the drag not
    //: appearing to work.
    if (colSizes) {
      tableEl.style.tableLayout = "fixed";
      tableEl.style.width = `${colSizes.reduce((sum, n) => sum + n, 0)}px`;
      tableEl.style.minWidth = "0";
      headCells().forEach((th, i) => {
        th.style.width = `${colSizes[i]}px`;
      });
    }
    if (rowSizes) {
      bodyRowEls().forEach((tr, i) => {
        tr.style.height = `${rowSizes[i]}px`;
      });
    }
    //: The row grip lives in its row's first cell, because a `<span>` made a
    //: child of a `<tr>` gets wrapped in an anonymous table cell and shows up
    //: as a phantom column. It is given the table's width so the whole row's
    //: bottom edge is draggable rather than only the first column's.
    const width = tableEl.getBoundingClientRect().width;
    for (const grip of block.querySelectorAll(".md-grip-row")) {
      grip.style.width = `${width}px`;
    }
  };

  const stripTableSizes = () => {
    tableEl.style.tableLayout = "";
    tableEl.style.width = "";
    tableEl.style.minWidth = "";
    for (const th of headCells()) th.style.width = "";
    for (const tr of bodyRowEls()) tr.style.height = "";
  };

  const clearTableSizes = () => {
    colSizes = null;
    rowSizes = null;
    stripTableSizes();
  };

  const startGripDrag = (event, axis, index, grip) => {
    event.preventDefault();
    event.stopPropagation();
    //: Both axes are measured on the first drag of either, from what is on
    //: screen: half-measured sizes are how a table jumps on the second drag.
    if (!colSizes) colSizes = headCells().map((th) => th.getBoundingClientRect().width);
    if (!rowSizes) rowSizes = bodyRowEls().map((tr) => tr.getBoundingClientRect().height);
    block.dataset.tableView = "sized";
    applyTableSizes();
    const startX = event.clientX;
    const startY = event.clientY;
    const startW = colSizes[index];
    const startH = rowSizes[index];
    try {
      grip.setPointerCapture(event.pointerId);
    } catch {
      //: A synthetic pointer event has no capture to take; the listeners below
      //: still see the move because they are on the grip itself.
    }
    const move = (e) => {
      if (axis === "col") colSizes[index] = Math.max(MIN_COL, startW + (e.clientX - startX));
      else rowSizes[index] = Math.max(MIN_ROW, startH + (e.clientY - startY));
      applyTableSizes();
    };
    const end = () => {
      grip.removeEventListener("pointermove", move);
      grip.removeEventListener("pointerup", end);
      grip.removeEventListener("pointercancel", end);
    };
    grip.addEventListener("pointermove", move);
    grip.addEventListener("pointerup", end);
    grip.addEventListener("pointercancel", end);
  };

  const gripFor = (axis, index, host) => {
    const grip = document.createElement("span");
    grip.className = `md-grip md-grip-${axis}`;
    grip.setAttribute("role", "separator");
    grip.setAttribute("aria-orientation", axis === "col" ? "vertical" : "horizontal");
    grip.title = axis === "col" ? "Drag to set this column's width" : "Drag to set this row's height";
    grip.addEventListener("pointerdown", (event) => startGripDrag(event, axis, index, grip));
    host.appendChild(grip);
  };

  const addGrips = () => {
    if (block.querySelector(".md-grip")) return;
    headCells().forEach((th, i) => gripFor("col", i, th));
    bodyRowEls().forEach((tr, i) => {
      if (tr.firstElementChild) gripFor("row", i, tr.firstElementChild);
    });
    applyTableSizes();
  };

  const removeGrips = () => {
    for (const grip of block.querySelectorAll(".md-grip")) grip.remove();
  };

  //: **And it has to do something in the bubble too** (INBOX 181, the owner:
  //: "the actual size/fit to panel button in ai written tables doesnt work
  //: when not in the full view"). It did not, and the cause was that every
  //: rule the toggle drove was written `.md-table-block.is-full:not(.is-actual)
  //: …`: pressing it in a bubble added a class nothing was listening for.
  //: Measured before the fix, inline: `table-layout: auto` and
  //: `overflow-x: auto` before the press and `table-layout: auto`,
  //: `overflow-x: auto` after it.
  //:
  //: The class became `data-table-view`, which is the state itself rather than
  //: "not the default", because the two surfaces have opposite defaults: a
  //: table in a bubble is at its natural width and scrolls sideways, and one
  //: in full view fits the panel (INBOX 179's decision, unchanged). One
  //: attribute with the same two values in both places is what makes the
  //: toggle mean the same thing wherever it is pressed.
  //: The wrap toggle is this attribute's switch (the old "Fit to panel" row
  //: of the ⋯, now an icon in the head): pressed is `fit`. A press in the
  //: bubble is remembered for the next table; one in full view is not, since
  //: full view starts fitted whatever the bubble was.
  const wrap = wrapToggle(
    "table",
    (on) => {
      //: A table the reader has dragged columns on is in neither state, so the
      //: toggle takes it back to one, dropping the sizes: the alternative is a
      //: button that appears to do nothing because the explicit widths win.
      clearTableSizes();
      block.dataset.tableView = on ? "fit" : "actual";
    },
    () => !block.classList.contains("is-full")
  );
  const setTableView = (view) => {
    block.dataset.tableView = view;
    wrap.paint(view === "fit");
  };
  const full = button("Full view", "Show this table on its own, at the window's width");
  //: The bubble's own start, said out loud rather than left as the absence of
  //: a class: a table in an answer is at its natural width and scrolls
  //: sideways unless the reader last chose to wrap.
  const bubbleView = () => (wrap.remembered() ? "fit" : "actual");
  setTableView(bubbleView());
  //: **The panel leaves the bubble to be full screen** (reported on the first
  //: cut, with a screenshot: "the table full view is behind a lot of stuff").
  //: A `position: fixed` element is laid out against the nearest ancestor
  //: with a filter, transform or backdrop-filter rather than against the
  //: viewport, and the chat card is a blurred surface: the panel was
  //: therefore trapped inside the card, under its own header, and no
  //: z-index could lift it out of that stacking context. So the block is
  //: moved to `document.body` while it is open and put back exactly where
  //: it was on the way out; `placeholder` is what keeps its place in the
  //: answer, since the surrounding prose has no other mark for it.
  let placeholder = null;
  //: **A panel with no visible way out is a panel people hard-refresh out of**
  //: (INBOX 239, the owner: "I opened up the table full view but there was no
  //: way to close it so I had to hard refresh the app"). Two things were true
  //: at once, and only the second one is a stylesheet's fault:
  //:
  //: - The only route out that was *drawn* was the ⋯ menu's last row, and in
  //:   full view it does not work. `kebabMenu` reparents its dropdown to
  //:   `<body>` to escape clipping ancestors (`wireEscapedActionMenu`), where
  //:   it is `position: fixed; z-index: 1020`, and this panel is a sibling of
  //:   it at `z-index: 2400`. Measured on :8802 in the documents tab: the Back
  //:   row drew at 1166,248 and `elementFromPoint` at its centre returned
  //:   `DIV.md-table-wrap`, so the click landed on the table and the panel
  //:   stayed open. Fixed at the source in `wireEscapedActionMenu`, which now
  //:   lifts an escaped menu above whatever surface its opener sits in.
  //: - Escape worked the whole time, and nothing said so. A keystroke nobody
  //:   is told about is not an affordance, so the panel gets the X every other
  //:   dismissable surface in this app has (`.sheet-close`'s shape, in the
  //:   bar that is already this panel's head) and it names the key in its
  //:   own tooltip.
  const close = smallButton("ph:x", "Close full view (Escape)", () => leave());
  //: `code-copy` is the bar's own segmented grammar, not a copy affordance:
  //: `.code-actions > .code-copy` is what strips a button's border and ground
  //: so it reads as one item of the shell rather than a chip dropped on it
  //: (the rule's own comment, in 05-sidebars-themes.css). Without it this X
  //: arrives as a bordered pill inside a tinted pill, which is the exact
  //: shape INBOX 188 was raised about.
  close.classList.add("code-copy", "md-table-close");
  close.hidden = true;
  //: Where the focus was when the panel opened, so leaving puts it back there
  //: rather than on `<body>`, which is where a removed button leaves it and
  //: from which the next Tab starts the page again.
  let returnFocusTo = null;
  const leave = () => {
    block.classList.remove("is-full");
    //: The dragged sizes stay in `colSizes`/`rowSizes` and come off the DOM:
    //: a bubble is not where a 900px-wide table belongs, and re-entering full
    //: view puts them straight back.
    removeGrips();
    stripTableSizes();
    setTableView(bubbleView());
    if (placeholder && placeholder.parentNode) {
      placeholder.replaceWith(block);
      placeholder = null;
    }
    full.textContent = "Full view";
    close.hidden = true;
    //: The menu is built below and reads these two labels; leaving full view
    //: by Escape has to put its rows back the way pressing Back would.
    syncMenuLabels();
    document.removeEventListener("keydown", onKey, true);
    //: Only when it is still on the page and still focusable: the block is
    //: re-parented on the way out, and an answer that re-rendered underneath
    //: the panel has taken its opener with it.
    if (returnFocusTo && returnFocusTo.isConnected) returnFocusTo.focus();
    returnFocusTo = null;
  };
  const onKey = (event) => {
    if (event.key === "Escape") {
      event.preventDefault();
      leave();
    }
  };
  full.addEventListener("click", () => {
    if (block.classList.contains("is-full")) return leave();
    //: Read before the move: `document.activeElement` is the ⋯ opener the row
    //: was chosen from, and one line later that button is inside a panel that
    //: has left its bubble.
    returnFocusTo = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    placeholder = document.createComment("table in full view");
    block.replaceWith(placeholder);
    document.body.appendChild(block);
    block.classList.add("is-full");
    //: Fit is full view's default (INBOX 179) and actual size is the bubble's,
    //: so the state is set on the way in rather than carried across.
    setTableView(colSizes || rowSizes ? "sized" : "fit");
    addGrips();
    full.textContent = "Back";
    close.hidden = false;
    //: The panel's own dismissal takes the focus, so Escape and Tab both act
    //: on the panel rather than on the page it covered, and a keyboard reader
    //: lands on the way out first.
    close.focus();
    document.addEventListener("keydown", onKey, true);
  });
  //: **One Copy button and a ⋯ for the rest** (INBOX 188, the owner: "the
  //: table button option rendering needs to be fixed or refined, especially
  //: in the popup agent, maybe just make it a copy button with an
  //: ellipse/kebab dropdown menu button next to it for the other options").
  //: Five labelled buttons in a row is a bar wider than most of the tables it
  //: sits on, and in the popup agent, which is a 293px card, it wrapped onto
  //: two lines above a three-column table. Copy is the one thing wanted often
  //: enough to cost a click; everything else is a `kebabMenu`, which is the
  //: recipe DESIGN.md's index gives for exactly this (standing order 11)
  //: rather than a second menu shape invented for one bar.
  //:
  //: `full` keeps its own element and its own handler and its row is a press
  //: on it, so the two places that rewrite its label (its own click, and
  //: `leave()`) go on working against the same node. Wrapping left the menu
  //: for the head (a ⋯ row hides a switch the reader wants to see the state of).
  const actions = document.createElement("span");
  actions.className = "code-actions";
  const menu = kebabMenu(
    [
      {
        label: "ph:markdown-logo Copy as markdown",
        title: "Copy the table as markdown",
        run: () => copyToClipboard(rawTable.join("\n")),
      },
      {
        label: "ph:note-pencil Save as a note",
        title: "File this table in your notebook as a new note",
        run: () => saveSelectionAsNote(rawTable.join("\n")),
      },
      {
        label: "ph:file-csv Save as CSV",
        title: "Save this table as a CSV file in the exports folder",
        run: () => saveFile(`table-${Date.now()}.csv`, new Blob([csv], { type: "text/csv" })),
      },
      { label: "ph:frame-corners", title: full.title, run: () => full.click() },
    ],
    "More table actions"
  );
  //: The two toggles' rows are found once and relabelled by the handlers that
  //: already own their wording, so the menu never says "Full view" for a table
  //: that is in full view.
  const menuRows = [...menu.querySelectorAll(".menu-item")];
  const fullRow = menuRows[3];
  const syncMenuLabels = () => {
    setLabel(fullRow, `ph:frame-corners ${full.textContent}`);
  };
  syncMenuLabels();
  full.addEventListener("click", syncMenuLabels);
  //: The button still exists, still carries the state, and is simply not in
  //: the bar: `leave()` writes to it on Escape, and the menu reads it back on
  //: the next open.
  full.hidden = true;
  actions.append(
    wrap.button,
    button("ph:copy Copy", "Copy the cells, tab-separated, for a spreadsheet", (event) => copyToClipboard(tsv, event.currentTarget)),
    menu,
    //: Last in the bar, which puts it at the panel's top-right corner, where
    //: every other X in this app is. Hidden in a bubble: there is nothing to
    //: close there.
    close,
    full
  );
  bar.append(label, actions);
  block.append(bar, scroller);
  return block;
}

//: One link and nothing else on the line, as a markdown link, an
//: angle-bracket autolink or a bare address. Bounded lengths throughout: this
//: runs over model output, and an unbounded `[^\]]*` against a paragraph that
//: opens a bracket and never closes it is a scan of the whole answer per line.
const LONE_LINK =
  /^\s*(?:\[([^\]]{1,300})\]\((https?:\/\/[^\s)]{1,500})\)|<?(https?:\/\/[^\s<>]{1,500})>?)\s*$/;

//: The path of an address, as words, for a card whose host is already on its
//: own line: "articles / s41586-024-07123-4". The query string and fragment
//: are dropped (tracking and position, not identity), and an address with no
//: path at all falls back to the host, because a card with an empty title is
//: worse than one that repeats itself.
function linkCardPath(url) {
  let parsed;
  try {
    parsed = new URL(url);
  } catch {
    return url;
  }
  const segments = parsed.pathname.split("/").filter(Boolean).map((piece) => {
    let decoded = piece;
    try {
      decoded = decodeURIComponent(piece);
    } catch {
      //: A stray percent in a path is not a reason to show nothing.
    }
    return decoded;
  });
  if (!segments.length) return parsed.hostname.replace(/^www\./i, "");
  const last = segments[segments.length - 1];
  const shown =
    last.length > READABLE_URL_SEGMENT ? `${last.slice(0, READABLE_URL_SEGMENT - 1)}\u2026` : last;
  return segments.length > 1 ? `${segments[0]} / ${shown}` : shown;
}

//: The card itself. **No favicon, and that is a decision rather than an
//: omission** (CHAT_PLAN decision 12): fetching one would be the first time
//: this app asked the web for anything nobody had asked it to, on an app whose
//: first line of description is that it is offline. So the host is written in
//: words, which is the half of a favicon that carries the meaning anyway.
//:
//: `target="_blank"` with `rel="noopener noreferrer"`, the same pair the
//: source cards use: without `noopener` the opened page gets a handle on this
//: window and can navigate it.
function linkCard(url, text) {
  const card = document.createElement("a");
  card.className = "link-card";
  card.href = safeHref(url);
  card.target = "_blank";
  card.rel = "noopener noreferrer";
  card.title = url;
  const title = document.createElement("span");
  title.className = "link-card-title";
  //: The link's own words when it has any; otherwise the address without its
  //: host, because the host is written on the line directly below. Using
  //: `readableUrl` here (the inline form) printed "arxiv.org / … / 2401.12345"
  //: over "arxiv.org", which is the card saying the same thing twice in the
  //: two lines it has.
  title.textContent = text || linkCardPath(url);
  const host = document.createElement("span");
  host.className = "link-card-host";
  setLabel(host, `ph:globe ${sourceHost(url) || url}`);
  card.append(title, host);
  return card;
}

//: **A menu where the pointer is** (INBOX 182, the owner: "I want to be able
//: to right click or hold with a touch on a link and have a popup show to let
//: me copy the link address").
//:
//: `kebabMenu` is the app's one menu recipe and every part of it is wanted
//: here, the row markup, the keyboard wiring, `escapeMenuIfClipped`, closing
//: with every other menu. What it does not have is an anchor: it opens under
//: a button you pressed, and a context menu opens where a pointer is. So the
//: recipe is given one: a one-pixel, transparent, unclickable opener inside a
//: `position: fixed` host parked at the pointer. Nothing about the menu itself
//: is re-implemented, which is the whole point of a recipe index (standing
//: order 11); DESIGN.md carries the row, `tests/test_ui_recipes.py` the
//: ratchet that keeps the next one from being hand-built.
let pointerMenuHost = null;

function openMenuAtPoint(items, ariaLabel, x, y, returnFocus = null) {
  closeActionMenus();
  if (!pointerMenuHost) {
    pointerMenuHost = document.createElement("div");
    pointerMenuHost.className = "pointer-menu-host";
    document.body.appendChild(pointerMenuHost);
  }
  pointerMenuHost.replaceChildren();
  //: Parked inside the window before the menu is measured, so the clamp that
  //: `openActionMenu` runs has a sane starting rect even at the last pixel of
  //: the viewport.
  const margin = 8;
  pointerMenuHost.style.left = `${Math.max(margin, Math.min(x, window.innerWidth - margin))}px`;
  pointerMenuHost.style.top = `${Math.max(margin, Math.min(y, window.innerHeight - margin))}px`;
  const wrap = kebabMenu(items, ariaLabel);
  const opener = wrap.querySelector("[aria-haspopup]");
  opener.classList.add("pointer-menu-anchor");
  if (returnFocus) opener._returnFocusTo = returnFocus;
  //: Not `hidden` and not `display: none`: `openActionMenu` measures the
  //: opener to decide whether to flip or to escape its container, and an
  //: element with no box measures at 0,0, which is the top left corner this
  //: app has had reported to it more than once.
  opener.setAttribute("tabindex", "-1");
  pointerMenuHost.appendChild(wrap);
  const menu = wrap.querySelector(".action-menu");
  openActionMenu(menu, opener);
  //: **The focus is asked for again on the next frame**, and only when it did
  //: not stay. Measured on the graph at 390 with a real hold (CDP touch,
  //: `scratchpad/ui-sweeps/graphphone.js`): `openActionMenu` focuses the
  //: first row, and while a touch gesture is still in flight Chromium takes
  //: it straight back out again (a `focusin` on the row followed immediately
  //: by a `focusout` to nothing, with the menu still open and visible). The
  //: cost is not cosmetic: Escape is bound on the menu, so a menu opened by a
  //: hold could not be closed by the keyboard, and the same press with the
  //: finger lifted first focuses perfectly. A frame later the same call
  //: sticks. Nothing happens when the focus is already inside, so a menu
  //: opened by a right-click is untouched.
  requestAnimationFrame(() => {
    if (!menu || menu.classList.contains("hidden")) return;
    if (menu.contains(document.activeElement)) return;
    menu.querySelector("button")?.focus({ preventScroll: true });
  });
}

//: What a right-click on a link offers, by what the link is. An address can be
//: copied and opened in a new tab; a `[[link]]` has no address to copy, so it
//: offers its title and its own click, which is what opens a note, a board or
//: a document (`resolveWikiTarget`). Returns null for anything that is not a
//: link, which is how the delegated listener below decides whether to take
//: the event away from the browser's own menu.
function linkMenuItems(el) {
  if (el.classList.contains("wiki-link")) {
    const title = el.textContent.trim();
    return [
      {
        label: "ph:copy Copy title",
        title: "Copy the name this link points at",
        run: () => copyToClipboard(title),
      },
      {
        label: "ph:arrow-square-out Open",
        title: "Open what this link points at",
        run: () => el.click(),
      },
    ];
  }
  const href = el.getAttribute("href") || "";
  //: Only the schemes the markdown renderer can produce
  //: (`tests/test_markdown_link_schemes.py`). A `#anchor`, a `blob:` download
  //: and the app's own internal anchors are not addresses anybody wants on a
  //: clipboard, and taking the browser's menu away from them would remove
  //: more than this adds.
  if (!/^(https?:|mailto:)/i.test(href) && !appAddressHash(href)) return null;
  return [
    {
      label: "ph:link Copy link address",
      title: "Copy this address to the clipboard",
      run: () => copyToClipboard(el.href),
    },
    {
      label: "ph:arrow-square-out Open in new tab",
      title: "Open this address in a new browser tab",
      run: () => window.open(el.href, "_blank", "noopener,noreferrer"),
    },
  ];
}

//: **One listener on the document, not one per surface.** The link this is
//: about is drawn by the chat, the popup agent, a note preview, a document
//: preview, the dashboard digest and the sources panel, and every one of them
//: re-renders its own contents; a listener per surface is a listener that
//: three of them forget. Delegation also means a link rendered by something
//: written next year is covered without anybody remembering this.
function linkAtEvent(event) {
  if (!(event.target instanceof Element)) return null;
  const el = event.target.closest("a[href], .wiki-link");
  if (!el || el.hasAttribute("download")) return null;
  const items = linkMenuItems(el);
  return items ? { el, items } : null;
}

document.addEventListener("contextmenu", (event) => {
  const found = linkAtEvent(event);
  if (!found) return;
  event.preventDefault();
  openMenuAtPoint(found.items, "Link actions", event.clientX, event.clientY);
});
