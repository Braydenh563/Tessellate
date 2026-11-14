// documents-sections.js: labelled and linked sections, and the ```sections block (L-documents-49; DOCUMENTS_PLAN 24 row
// 10; the owner: "you can visually connect ideas across the current document and link them, with reasons, you can have a
// local graph of linked ideas available for the current document and can even embed and render the graph in the document").
//
// A label is a block id (`^name`, documents-block-ids.js) at the end of a heading or a paragraph. A link is
// `[[#^name|reason]]` written inside another labelled section: the existing block reference to this document, the alias
// being the reason, so it resolves and reveals through `docResolveWikiTarget` and `docRevealBlock` like any other. This file
// reads both (`parse`), lists the links in the Outline tab (`renderLinks`, "Section links") and draws a ```sections fence
// as a small SVG graph of them (`fill`). Not the Graph tab's canvas renderer: that one draws notes from `/graph/local`
// through a worker onto one canvas, with no edge labels and no DOM to count; a dozen sections want a dozen elements.
//
// Lazy: `LAZY_MODULES.docSections`, registered in documents-math.js, which draws Read and Live and calls
// `docMathRender.sections.*`. Everything is a property of `docMathRender.sections`, so the file adds no global name.
(() => {
  // DOC-SECTIONS-BEGIN (tests/test_doc_section_links.py runs this region in node)
  //: The block id's grammar is documents-block-ids.js's `DOC_BLOCK_ID`; written again here so this region runs alone.
  const ID = "[A-Za-z0-9][A-Za-z0-9-]{0,31}";
  const AT_END = new RegExp(`(?:^|[ \\t])\\^(${ID})[ \\t]*$`);
  const LINK = new RegExp(`\\[\\[#\\^(${ID})(?:\\|([^\\[\\]|\\n]{0,120}))?\\]\\]`, "g");
  const HEADING = /^(#{1,6})[ \t]+(.*)$/;
  const FENCE = /^\s*(?:```|~~~)/;
  const MAX_NODES = 40;

  //: What a section is called: a heading's words, or a paragraph's first few, without the marks.
  function labelOf(text) {
    const plain = String(text)
      .replace(AT_END, "")
      .replace(/\[\[#\^[A-Za-z0-9-]{1,32}(?:\|([^\]]{0,120}))?\]\]/g, "$1")
      .replace(/[*_`~=]+/g, "")
      .replace(/\s+/g, " ")
      .trim();
    return plain.length > 48 ? `${plain.slice(0, 47).trimEnd()}…` : plain;
  }

  //: **`parse(text)`**: `{ sections: [{ id, label, kind, line, from, to, start, end }], links: [{ from, to, reason, line, at,
  //: missing }] }`. `from`/`to` on a section are the offsets of its own block (the heading line, or the paragraph), what is
  //: selected to show it; `start`/`end` are the lines it spans (a heading's run down to the next heading as deep or less),
  //: which is what decides which section a link is written in. Code fences and inline code are not read.
  function parse(text) {
    const lines = String(text == null ? "" : text).split("\n");
    const offsets = [];
    let at = 0;
    for (const line of lines) {
      offsets.push(at);
      at += line.length + 1;
    }
    const fenced = [];
    let open = false;
    for (const line of lines) {
      if (FENCE.test(line)) {
        fenced.push(true);
        open = !open;
      } else fenced.push(open);
    }
    const headings = [];
    lines.forEach((line, index) => {
      const h = !fenced[index] && HEADING.exec(line);
      if (h) headings.push({ line: index, level: h[1].length });
    });
    const sections = [];
    const seen = new Set();
    lines.forEach((line, index) => {
      if (fenced[index]) return;
      const mark = AT_END.exec(line);
      if (!mark || seen.has(mark[1])) return;
      seen.add(mark[1]);
      const h = HEADING.exec(line);
      if (h) {
        const level = h[1].length;
        const next = headings.find((other) => other.line > index && other.level <= level);
        sections.push({ id: mark[1], label: labelOf(h[2]), kind: "heading", line: index, start: index, end: next ? next.line : lines.length, from: offsets[index], to: offsets[index] + line.length });
        return;
      }
      let first = index;
      while (first > 0 && lines[first - 1].trim() && !fenced[first - 1] && !HEADING.test(lines[first - 1])) first--;
      const words = lines.slice(first, index + 1).join(" ");
      sections.push({ id: mark[1], label: labelOf(words), kind: "paragraph", line: index, start: first, end: index + 1, from: offsets[first], to: offsets[index] + line.length });
    });
    const ids = new Set(sections.map((s) => s.id));
    //: The innermost labelled section holding a line: the one that starts last (a paragraph inside a heading's run).
    const holder = (index) => {
      let best = null;
      for (const s of sections) if (s.start <= index && index < s.end && (!best || s.start > best.start || (s.start === best.start && s.end < best.end))) best = s;
      return best;
    };
    const links = [];
    lines.forEach((line, index) => {
      if (fenced[index] || !line.includes("[[#^")) return;
      //: Inline code is blanked to the same length, so offsets still point into the text.
      const readable = line.replace(/`[^`]*`/g, (code) => " ".repeat(code.length));
      for (const m of readable.matchAll(LINK)) {
        links.push({ from: holder(index)?.id || null, to: m[1], reason: (m[2] || "").trim(), line: index, at: offsets[index] + m.index, missing: !ids.has(m[1]) });
      }
    });
    return { sections, links };
  }

  //: **`graph(model)`**: the nodes are the labelled sections, the edges the links from one of them to another.
  //: A link to a label that is not there, from outside every section or to its own section draws no edge.
  function graph(model) {
    const nodes = model.sections.slice(0, MAX_NODES).map((s) => ({ id: s.id, label: s.label || s.id, kind: s.kind }));
    const shown = new Set(nodes.map((n) => n.id));
    const edges = model.links
      .filter((l) => l.from && l.from !== l.to && shown.has(l.from) && shown.has(l.to))
      .map((l) => ({ from: l.from, to: l.to, reason: l.reason }));
    return { nodes, edges, cut: model.sections.length - nodes.length };
  }

  //: **`layout(count, width, height)`**: the nodes round an ellipse, in the document's order from the top, so the first
  //: section is at twelve o'clock and reading clockwise is reading down the page. Two sit side by side, one in the middle.
  function layout(count, width, height) {
    const cx = width / 2;
    const cy = height / 2;
    if (count === 1) return [{ x: cx, y: cy }];
    if (count === 2) return [{ x: width * 0.25, y: cy }, { x: width * 0.75, y: cy }];
    const rx = width / 2 - 80;
    const ry = height / 2 - 30;
    return Array.from({ length: count }, (_, i) => {
      const angle = -Math.PI / 2 + (2 * Math.PI * i) / count;
      return { x: cx + rx * Math.cos(angle), y: cy + ry * Math.sin(angle) };
    });
  }

  //: **`pickBlock(stamps, shift, line)`**: which Read block a section is. `stamps` are the rendered blocks' `data-src-line`
  //: in order; the block holding a line is the last one stamped at or before it (the title and properties the preview
  //: prepends or removes are `shift`). -1 when there is none.
  function pickBlock(stamps, shift, line) {
    let hit = -1;
    for (let i = 0; i < stamps.length; i++) {
      const at = Number(stamps[i]) - shift;
      if (!Number.isFinite(at)) continue;
      if (at > line) break;
      hit = i;
    }
    return hit;
  }
  // DOC-SECTIONS-END

  const SVG = "http://www.w3.org/2000/svg";
  const svgEl = (name, attrs = {}, parent = null) => {
    const el = document.createElementNS(SVG, name);
    for (const [key, value] of Object.entries(attrs)) el.setAttribute(key, value);
    parent?.append(el);
    return el;
  };
  const cut = (text, n) => (text.length > n ? `${text.slice(0, n - 1).trimEnd()}…` : text);
  const currentText = () => docText();

  //: Read has no caret to put on a block, so Read stays Read: the rendered block is scrolled into view and ringed with the
  //: jump-to ring (`flashRevealed`, which respects reduced motion). Live and the source keep `docRevealBlock`'s selection.
  function readBlock(section) {
    const preview = document.getElementById("doc-preview");
    if (!preview || !section) return null;
    const kids = [...preview.children];
    const at = pickBlock(kids.map((el) => el.dataset.srcLine), docPreviewLineShift, section.start);
    return at < 0 ? null : kids[at];
  }

  const inRead = () => typeof docView !== "undefined" && docView === "rendered";

  //: Go to a section. A node, a row in the outline and a link all land the same way: in Read, the block ringed where it
  //: stands; elsewhere through the block reference's own reveal (the block selected, scrolled to).
  function reveal(id) {
    if (inRead()) {
      const section = parse(currentText()).sections.find((s) => s.id === id);
      const el = readBlock(section);
      if (el) {
        flashRevealed(el);
        return true;
      }
    }
    return docRevealBlock(id);
  }

  //: **Peek** (L-documents-115): the sections a row or an edge joins, marked while the pointer or focus is on it, and
  //: nothing moves: not the caret, the selection or the scroll. Read marks the rendered blocks (`.dsec-peek`); Live and the
  //: source mark the lines, through one state field added to the view the first time it is asked.
  let peekEffect = null;
  let peekField = null;
  const wired = new WeakSet();
  function peekExtension(CM) {
    if (peekField) return peekField;
    const { StateField, StateEffect } = CM.state;
    const { Decoration, EditorView } = CM.view;
    peekEffect = StateEffect.define();
    peekField = StateField.define({
      create: () => Decoration.none,
      update(value, tr) {
        for (const effect of tr.effects) {
          if (!effect.is(peekEffect)) continue;
          const doc = tr.state.doc;
          const lines = new Set();
          for (const range of effect.value) {
            const to = Math.min(range.to, doc.length);
            for (let n = doc.lineAt(Math.min(range.from, doc.length)).number; n <= doc.lineAt(to).number; n++) lines.add(doc.line(n).from);
          }
          return Decoration.set([...lines].sort((a, b) => a - b).map((from) => Decoration.line({ class: "dsec-peek" }).range(from)));
        }
        return tr.docChanged ? Decoration.none : value;
      },
      provide: (field) => EditorView.decorations.from(field),
    });
    return peekField;
  }

  function peek(ids) {
    const model = parse(currentText());
    const sections = ids.map((id) => model.sections.find((s) => s.id === id)).filter(Boolean);
    const preview = document.getElementById("doc-preview");
    for (const el of preview?.querySelectorAll(".dsec-peek") || []) el.classList.remove("dsec-peek");
    const view = typeof docCmView !== "undefined" ? docCmView : null;
    const CM = window.CM6;
    if (view && CM) {
      const field = peekExtension(CM);
      if (!wired.has(view)) {
        wired.add(view);
        view.dispatch({ effects: CM.state.StateEffect.appendConfig.of(field) });
      }
      view.dispatch({ effects: peekEffect.of(sections.map((s) => ({ from: s.from, to: s.to }))) });
    }
    if (inRead()) for (const s of sections) readBlock(s)?.classList.add("dsec-peek");
  }

  //: Hover and focus on one element peek the sections it joins; leaving clears it.
  function peekOn(el, ids) {
    const on = () => peek(ids);
    const off = () => peek([]);
    el.addEventListener("mouseenter", on);
    el.addEventListener("mouseleave", off);
    el.addEventListener("focusin", on);
    el.addEventListener("focusout", off);
  }

  //: **`fill(figure, source)`**: the graph of this document's labelled sections. `title: ...` in the fence is its caption.
  function fill(figure, source) {
    const title = /^\s*title:\s*(.+)$/im.exec(source || "")?.[1]?.trim() || "";
    const model = graph(parse(currentText()));
    figure.replaceChildren();
    if (title) figure.append(Object.assign(document.createElement("div"), { className: "dg-title", textContent: title }));
    if (!model.nodes.length) {
      const empty = document.createElement("p");
      empty.className = "dg-empty";
      empty.textContent = "No labelled sections yet. End a heading or a paragraph with ^name, then link to it from another with [[#^name|why]].";
      figure.append(empty);
      return true;
    }
    const W = 560;
    const H = Math.max(220, Math.min(420, 120 + model.nodes.length * 26));
    const points = layout(model.nodes.length, W, H);
    const at = new Map(model.nodes.map((n, i) => [n.id, points[i]]));
    const svg = svgEl("svg", { class: "dsec-svg", viewBox: `0 0 ${W} ${H}`, role: "group" });
    svg.setAttribute("aria-label", `${nounCount(model.nodes.length, "section")}, ${nounCount(model.edges.length, "link")}`);
    const markerId = `dsec-arrow-${Math.random().toString(36).slice(2, 8)}`;
    svgEl("path", { d: "M0,0 L8,4 L0,8 z", class: "dsec-head" }, svgEl("marker", { id: markerId, viewBox: "0 0 8 8", refX: 8, refY: 4, markerWidth: 8, markerHeight: 8, orient: "auto-start-reverse" }, svgEl("defs", {}, svg)));
    const edgeLayer = svgEl("g", { class: "dsec-edges" }, svg);
    const nodeLayer = svgEl("g", { class: "dsec-nodes" }, svg);
    //: A second link between the same two sections puts its reason a line lower, so two reasons never sit on each other.
    const pairs = new Map();
    for (const edge of model.edges) {
      const a = at.get(edge.from);
      const b = at.get(edge.to);
      const pair = [edge.from, edge.to].sort().join(" ");
      const nth = pairs.get(pair) || 0;
      pairs.set(pair, nth + 1);
      const g = svgEl("g", { class: "dsec-edge" }, edgeLayer);
      const dx = b.x - a.x;
      const dy = b.y - a.y;
      const len = Math.hypot(dx, dy) || 1;
      //: Stops short of the node's box, so the arrow head is seen.
      const trim = Math.min(len / 3, 22 + Math.abs(dx / len) * 34);
      svgEl("line", { x1: a.x, y1: a.y, x2: b.x - (dx / len) * trim, y2: b.y - (dy / len) * trim, "marker-end": `url(#${markerId})` }, g);
      peekOn(g, [edge.from, edge.to]);
      const label = svgEl("title", {}, g);
      label.textContent = `${edge.from} to ${edge.to}${edge.reason ? `: ${edge.reason}` : ""}`;
      if (edge.reason) {
        const text = svgEl("text", { class: "dsec-reason", x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 - 4 + nth * 14, "text-anchor": "middle" }, g);
        text.textContent = cut(edge.reason, 34);
      }
    }
    for (const node of model.nodes) {
      const p = at.get(node.id);
      const name = cut(node.label, 22);
      const width = Math.max(48, Math.min(160, name.length * 7 + 20));
      const g = svgEl("g", { class: node.kind === "paragraph" ? "dsec-node dsec-paragraph" : "dsec-node", tabindex: 0, role: "button", "data-section": node.id }, nodeLayer);
      g.setAttribute("aria-label", `Go to ${node.label}`);
      svgEl("rect", { x: p.x - width / 2, y: p.y - 14, width, height: 28, rx: 8 }, g);
      const text = svgEl("text", { x: p.x, y: p.y + 4, "text-anchor": "middle" }, g);
      text.textContent = name;
      const go = () => reveal(node.id);
      peekOn(g, [node.id]);
      g.addEventListener("click", go);
      g.addEventListener("keydown", (event) => {
        if (event.key !== "Enter" && event.key !== " ") return;
        event.preventDefault();
        go();
      });
    }
    figure.append(svg);
    const notes = [];
    if (model.cut > 0) notes.push(`The first ${model.nodes.length} sections are drawn; ${model.cut} more are not.`);
    if (!model.edges.length) notes.push("No links between them yet. Write [[#^name|why]] inside one section to link it to another.");
    for (const line of notes) figure.append(Object.assign(document.createElement("p"), { className: "dg-empty", textContent: line }));
    return true;
  }

  //: **The Outline tab's Section links** (after Comments): each link, from which section to which, with its reason.
  //: A row selects both sections, the one it goes to as the main selection, and scrolls to it.
  function wrapEl() {
    let wrap = document.getElementById("doc-sectionlinks-wrap");
    if (wrap) return wrap;
    const after = document.getElementById("doc-comments-wrap");
    if (!after) return null;
    wrap = document.createElement("div");
    wrap.id = "doc-sectionlinks-wrap";
    wrap.className = "doc-outline-wrap hidden";
    const heading = document.createElement("h3");
    const count = Object.assign(document.createElement("span"), { className: "doc-outline-count", id: "doc-sectionlinks-count" });
    heading.append("Section links ", count);
    const list = Object.assign(document.createElement("ul"), { className: "doc-outline doc-sectionlinks", id: "doc-sectionlinks" });
    wrap.append(heading, list);
    after.after(wrap);
    return wrap;
  }

  function showLink(link) {
    const model = parse(currentText());
    const byId = new Map(model.sections.map((s) => [s.id, s]));
    const target = byId.get(link.to);
    const source = byId.get(link.from);
    if (!target) return reveal(link.to);
    if (inRead()) {
      //: Read stays Read: the target is scrolled to and ringed; the section it is written in stays marked by the row's peek.
      const el = readBlock(target);
      if (!el) return reveal(link.to);
      flashRevealed(el);
      return true;
    }
    const view = typeof docCmView !== "undefined" ? docCmView : null;
    const CM = window.CM6;
    if (!view || !CM || !source || source === target) return reveal(link.to);
    const { EditorSelection } = CM.state;
    const ranges = [EditorSelection.range(source.from, source.to), EditorSelection.range(target.from, target.to)];
    view.dispatch({ selection: EditorSelection.create(ranges, 1), effects: CM.view.EditorView.scrollIntoView(target.from, { y: "center" }) });
    view.focus();
    return true;
  }

  function renderLinks(text) {
    const wrap = wrapEl();
    if (!wrap) return;
    const model = parse(text);
    const names = new Map(model.sections.map((s) => [s.id, s.label || s.id]));
    const list = document.getElementById("doc-sectionlinks");
    const count = document.getElementById("doc-sectionlinks-count");
    const key = JSON.stringify(model.links.map((l) => [l.from, l.to, l.reason, names.get(l.from), names.get(l.to)]));
    wrap.classList.toggle("hidden", !model.links.length);
    if (count) count.textContent = model.links.length ? String(model.links.length) : "";
    if (key === renderLinks.key && list.childElementCount === model.links.length) return;
    renderLinks.key = key;
    list.replaceChildren();
    for (const link of model.links) {
      const li = document.createElement("li");
      li.className = "outline-row doc-sectionlink";
      const button = document.createElement("button");
      button.type = "button";
      button.className = "outline-link";
      const from = link.from ? names.get(link.from) : "Before any label";
      const to = link.missing ? `^${link.to} (not in this document)` : names.get(link.to);
      const words = Object.assign(document.createElement("span"), { className: "outline-text", textContent: `${from} → ${to}` });
      button.append(words);
      if (link.reason) button.append(Object.assign(document.createElement("span"), { className: "doc-sectionlink-why", textContent: link.reason }));
      button.title = link.reason ? `${from} to ${to}: ${link.reason}` : `${from} to ${to}`;
      peekOn(button, [link.from, link.to].filter(Boolean));
      button.addEventListener("click", () => showLink(link));
      li.append(button);
      list.append(li);
    }
  }

  Object.assign(docMathRender.sections, { parse, graph, layout, pickBlock, fill, renderLinks, showLink, peek });
})();
