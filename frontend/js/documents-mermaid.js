// documents-mermaid.js: Mermaid fences, the flowchart model and the Live
// figure widget (split out of documents.js, audit 1031 DC13 remainder).
//
// What is here: the pure flowchart model (`diagramModel`: parse and print,
// bracketed by `DIAGRAM-MODEL-BEGIN`/`END` for `tests/test_diagram_model.py`;
// 1546 D1 to D4), the hand-over of a fence to the lazy `mermaid`
// module (`docRenderMermaidIn`, `docMermaidWhenDrawn`) and the Live state field
// that draws a fence as its figure (`docMermaidField`). What stayed in
// documents.js: `docPhase2State` (shared with the embeds and the print sheet)
// and the editor extension list that calls `docMermaidField`.
//
// **Loaded in the Library bundle, before documents.js**, the way
// documents-props.js is: documents.js and documents-export.js call in here only
// from inside functions, while this file's own top level declares and reads
// nothing from either (`docPhase2State`, `docStr`, `ensureModule` are read when
// a function runs). One closure; what other files call is the `Object.assign`
// at the foot.
(() => {
  // -----------------------------------------------------------------------------
  // Mermaid fences (DOCUMENTS_PLAN decisions 3 and 6, BACKLOG steps 8 and 12b)
  // -----------------------------------------------------------------------------
  //
  //: **Every ```mermaid fence is drawn by Mermaid itself**, in Read (so in a print
  //: and the HTML export) and in Live while the caret is outside the fence. The
  //: library is vendored (`frontend/vendor/mermaid/`) and lives in a hidden
  //: same-origin frame that the lazy `mermaid` module (mermaid-draw.js) creates
  //: on the first fence; nothing of it is in the boot scripts. This file only
  //: hands a fence over (`docRenderMermaidIn`, the Live widget below) and waits
  //: for the picture when a page is printed or saved.
  //:
  //: What stays here is the flowchart model below (1546), pure and node-tested.
  // DIAGRAM-MODEL-BEGIN
  //: **1546 D1, D2 and D4: the one flowchart grammar.** `parse(source)` reads a
  //: flowchart fence into `{kind, dir, nodes: [{id, text, shape, group}], edges:
  //: [{from, to, label, style, arrow}], subgraphs: [{id, title, parent}], kept:
  //: [{at, line}], front}` and `print(model)` writes the whole source back in
  //: one canonical order (the header, subgraphs with their nodes, loose nodes,
  //: edges), so the source is the only state. No coordinates: Mermaid source has
  //: none. A line this reader cannot place whole (`style`, `classDef`, `click`,
  //: `%%` comments, `@{ }` shapes, markdown-string labels, a shape it has no name
  //: for) is a `kept` line, printed verbatim where it stood (`at` counts the
  //: nodes, edges and subgraphs written before it), never dropped. `front` holds
  //: the lines ahead of the header (frontmatter, `%%{init}%%`). Labels are
  //: quoted and `#`, `"`, `<`, `>` (and `|` in an edge label) written as
  //: Mermaid's entity codes, as the composer does (composer_mermaid.py).
  //: Pure and node-tested (tests/test_diagram_model.py). A text that is another
  //: kind of diagram is null.
  const DGM_MAX_NODES = 120;
  const DGM_SHAPES = [
    ["([", "])", "stadium"], ["((", "))", "circle"], ["{{", "}}", "hexagon"], ["[(", ")]", "cylinder"], ["[/", "/]", "parallelogram"],
    ["[", "]", "rect"], ["(", ")", "round"], ["{", "}", "diamond"],
  ];
  const DGM_UNREAD_SHAPE = /^(?:\[\[|\[[\\|]|\(\(\(|>|@\{|:::|\{\{\{)/;
  const DGM_KEPT = /^(?:%%|(?:style|classDef|class|linkStyle|click|direction|default)\s|acc(?:Title|Descr)\b)/;
  const DGM_OTHER = /^(?:sequenceDiagram|classDiagram|stateDiagram|erDiagram|journey|gantt|pie|mindmap|timeline|gitGraph|C4\w+|quadrantChart|requirementDiagram|sankey|xychart|block|packet|kanban|architecture|zenuml)\b/i;
  //: Longest first, so `-.->` is not read as `-.-` and a stray `>`.
  const DGM_LINKS = [
    ["-.->", "dotted", true], ["==>", "thick", true], ["-->", "solid", true],
    ["-.-", "dotted", false], ["===", "thick", false], ["---", "solid", false],
    //: Both ways (R14, 1679 slice 10): the fourth field. No other token starts with `<`, so its place in the list is free.
    ["<-.->", "dotted", true, true], ["<==>", "thick", true, true], ["<-->", "solid", true, true],
  ];
  const DGM_WORDED = /^(--|-\.|==)\s*("[^"]*"|[^-.=|>"\s][^|>]*?)\s*(-->|\.->|==>|---|-\.-|===)/;
  const DGM_ENTITY = { quot: '"', lt: "<", gt: ">", amp: "&" };
  const DGM_CODE = { '"': "#quot;", "<": "#lt;", ">": "#gt;", "#": "#35;", "|": "#124;" };

  function dgmDecode(text) {
    return text.replace(/#(quot|lt|gt|amp|\d{1,7});/g, (all, k) => DGM_ENTITY[k] ?? (Number(k) <= 0x10ffff ? String.fromCodePoint(Number(k)) : all));
  }

  //: A line break in a label stays the `<br/>` Mermaid reads (a newline written is one); every other `<` is a code.
  function dgmEscape(text, inBars = false) {
    return String(text ?? "").replace(/\s*\n\s*/g, "<br/>").replace(/<br\s*\/?>|[#"<>|]/gi, (c) => (c.length > 1 || (c === "|" && !inBars) ? c : DGM_CODE[c]));
  }

  function dgmUnquote(text) {
    const t = text.trim();
    return t.length >= 2 && t[0] === '"' && t[t.length - 1] === '"' ? t.slice(1, -1) : t;
  }

  //: Lines and `;` statements. A `;` ends one only outside a quote and not as the
  //: end of an entity code; a comment line is whole.
  function dgmStatements(text) {
    const out = [];
    for (const line of text.split("\n")) {
      const comment = line.trimStart().startsWith("%%");
      let from = 0;
      let quoted = false;
      for (let i = 0; i < line.length && !comment; i++) {
        if (line[i] === '"') quoted = !quoted;
        else if (line[i] === ";" && !quoted && !/#\w{1,7}$/.test(line.slice(from, i))) {
          out.push(line.slice(from, i));
          from = i + 1;
        }
      }
      out.push(line.slice(from));
    }
    return out.map((s) => s.trim()).filter(Boolean);
  }

  //: The text of a shape from after its opening mark: quoted (a backtick right
  //: after the quote is a markdown string, `md`, its text kept raw) or up to the
  //: closing mark. Null when it is not whole.
  function dgmShapeText(rest, close) {
    const lead = rest.length - rest.trimStart().length;
    if (rest[lead] !== '"') {
      const end = rest.indexOf(close);
      return end === -1 ? null : { text: dgmDecode(rest.slice(0, end).trim()), used: end + close.length };
    }
    const md = rest[lead + 1] === "`";
    const end = md ? rest.indexOf('`"', lead + 2) + 1 || -1 : rest.indexOf('"', lead + 1);
    if (end === -1) return null;
    const after = rest.slice(end + 1);
    const gap = after.length - after.trimStart().length;
    if (!after.startsWith(close, gap)) return null;
    return md ? { text: rest.slice(lead + 2, end - 1), md: true, used: end + 1 + gap + close.length } : { text: dgmDecode(rest.slice(lead + 1, end)), used: end + 1 + gap + close.length };
  }

  //: One node reference: an id and, optionally, its shape and text.
  function dgmRef(src, at) {
    //: A hyphen only between word characters: `a-->b` is a, a link and b.
    const id = /^[\p{L}\p{N}_]+(?:-[\p{L}\p{N}_]+)*/u.exec(src.slice(at));
    if (!id) return null;
    const i = at + id[0].length;
    const tail = src.slice(i);
    if (DGM_UNREAD_SHAPE.test(tail)) return null;
    for (const [open, close, shape] of DGM_SHAPES) {
      if (!tail.startsWith(open)) continue;
      const body = dgmShapeText(tail.slice(open.length), close);
      return body && { id: id[0], shape, text: body.text, ...(body.md ? { md: true } : {}), end: i + open.length + body.used };
    }
    return { id: id[0], shape: null, text: null, end: i };
  }

  //: A link: `-->`, `-.->`, `==>` and their open forms, a label in bars after it
  //: or written inside it (`-- yes -->`).
  function dgmLink(src, at) {
    const rest = src.slice(at);
    const worded = DGM_WORDED.exec(rest);
    if (worded) {
      const style = worded[1] === "-." ? "dotted" : worded[1] === "==" ? "thick" : "solid";
      const arrow = worded[3] === "-->" || worded[3] === ".->" || worded[3] === "==>";
      return { style, arrow, label: dgmDecode(dgmUnquote(worded[2])), end: at + worded[0].length };
    }
    const hit = DGM_LINKS.find(([token]) => rest.startsWith(token));
    if (!hit) return null;
    const piped = /^\s*\|("[^"]*"|[^|]*)\|/.exec(src.slice(at + hit[0].length));
    return { style: hit[1], arrow: hit[2], ...(hit[3] ? { both: true } : {}), label: piped ? dgmDecode(dgmUnquote(piped[1])) : "", end: at + hit[0].length + (piped ? piped[0].length : 0) };
  }

  //: A node-and-link statement (chains `a --> b --> c`, fans `a & b --> c`) as
  //: its references and links, or null when any part is not read whole.
  function dgmChain(src) {
    const refs = [];
    const links = [];
    let at = 0;
    let group = [];
    let pending = null;
    const skip = () => {
      while (at < src.length && /\s/.test(src[at])) at++;
    };
    for (;;) {
      skip();
      const ref = dgmRef(src, at);
      if (!ref) return null;
      refs.push(ref);
      group.push(ref.id);
      at = ref.end;
      skip();
      if (src[at] === "&") {
        at++;
        continue;
      }
      if (pending) for (const from of pending.from) for (const to of group) links.push({ from, to, label: pending.label, style: pending.style, arrow: pending.arrow, ...(pending.both ? { both: true } : {}) });
      if (at >= src.length) return { refs, links };
      const link = dgmLink(src, at);
      if (!link) return null;
      pending = { ...link, from: group };
      group = [];
      at = link.end;
    }
  }

  //: `subgraph id [Title]`, `subgraph id["Title"]` or `subgraph Some title`.
  function dgmSubgraph(rest, parent) {
    const named = /^([A-Za-z0-9_][\w-]*)\s*\[\s*(.*?)\s*\]$/.exec(rest);
    const id = named ? named[1] : dgmDecode(dgmUnquote(rest));
    return { id, title: named ? dgmDecode(dgmUnquote(named[2])) || id : id, parent };
  }

  //: The canonical rows of a model, each `{depth, line, unit}` (`unit` null for an
  //: `end`): subgraphs with their members first, then the loose nodes, then the
  //: edges. Print writes them and parse counts them to place a kept line.
  function dgmRows(m) {
    const rows = [];
    const ids = new Set(m.subgraphs.map((g) => g.id));
    //: A parent that is missing or is itself leaves the subgraph at the top.
    const parentOf = (g) => (ids.has(g.parent) && g.parent !== g.id ? g.parent : null);
    const done = new Set();
    const emit = (group, depth) => {
      m.subgraphs.forEach((g, i) => {
        if (parentOf(g) !== group || done.has(i)) return;
        done.add(i);
        const plain = /^[A-Za-z0-9_][\w-]*$/.test(g.id);
        const line = plain && g.title !== g.id ? `subgraph ${g.id} ["${dgmEscape(g.title)}"]` : `subgraph ${g.id}`;
        rows.push({ depth, line, unit: { t: "s", i } });
        emit(g.id, depth + 1);
        rows.push({ depth, line: "end", unit: null });
      });
      m.nodes.forEach((n, i) => {
        if ((ids.has(n.group) ? n.group : null) !== group) return;
        const [open, close] = DGM_SHAPES.find((s) => s[2] === n.shape) || ["[", "]"];
        //: A markdown string is written raw on one line; a text with a quote, a backtick or a `<br>` is plain.
        const md = n.md && !/["`\n]|<br/i.test(n.text);
        rows.push({ depth, line: md ? `${n.id}${open}"\`${n.text}\`"${close}` : `${n.id}${open}"${dgmEscape(n.text)}"${close}`, unit: { t: "n", i } });
      });
    };
    emit(null, 0);
    m.edges.forEach((e, i) => {
      const token = (DGM_LINKS.find(([, style, arrow, both]) => style === e.style && arrow === e.arrow && Boolean(both) === Boolean(e.both)) || DGM_LINKS[2])[0];
      const label = e.label ? `|"${dgmEscape(e.label, true)}"|` : "";
      rows.push({ depth: 0, line: `${e.from} ${token}${label} ${e.to}`, unit: { t: "e", i } });
    });
    return rows;
  }

  //: 1661 B: a block's colour is `n.fill`, a hex hue. It is written as the one `style` line below (the hue mixed
  //: a quarter with white, so the dark text reads on both themes), and only that exact line is lifted back; any
  //: other `style` stays a kept line, byte for byte.
  const dgmTint = (hue) => "#" + [1, 3, 5].map((i) => Math.round(parseInt(hue.slice(i, i + 2), 16) * 0.25 + 191.25).toString(16).padStart(2, "0")).join("");
  const DGM_STYLE = /^style\s+([\w-]+)\s+fill:(#[0-9a-f]{6}),stroke:(#[0-9a-f]{6}),color:#1a1a1a$/;

  const DGM_LINKSTYLE = /^linkStyle\s+(\d+)\s+stroke:(#[0-9a-f]{6}),stroke-width:2px$/;

  function dgmPrint(m) {
    const kept = (m.kept || []).map((k, i) => ({ ...k, i })).sort((a, b) => a.at - b.at || a.i - b.i);
    const out = [...(m.front || []), `flowchart ${m.dir || "TD"}`];
    const indent = (depth) => "  ".repeat(depth + 1);
    let units = 0;
    let next = 0;
    const flush = (limit, depth) => {
      while (next < kept.length && kept[next].at <= limit) out.push(indent(depth) + kept[next++].line);
    };
    for (const row of dgmRows(m)) {
      if (row.unit) flush(units++, row.depth);
      out.push(indent(row.depth) + row.line);
    }
    flush(Infinity, 0);
    for (const n of m.nodes) if (/^#[0-9a-f]{6}$/.test(n.fill || "")) out.push(`${indent(0)}style ${n.id} fill:${dgmTint(n.fill)},stroke:${n.fill},color:#1a1a1a`);
    //: An arrow's colour (1679 slice 10): `linkStyle N`, N the edge's place in the canonical order, which is `m.edges`' own.
    m.edges.forEach((e, i) => /^#[0-9a-f]{6}$/.test(e.colour || "") && out.push(`${indent(0)}linkStyle ${i} stroke:${e.colour},stroke-width:2px`));
    return out.join("\n") + "\n";
  }

  //: The lines of the text before its header: frontmatter and leading comments.
  function dgmFront(text) {
    const front = [];
    const fm = /^---[ \t]*\n[\s\S]*?\n---[ \t]*(?:\n|$)/.exec(text);
    if (fm) front.push(...fm[0].replace(/\n$/, "").split("\n"));
    return { front, rest: fm ? text.slice(fm[0].length) : text };
  }

  function dgmParse(source) {
    const { front, rest } = dgmFront(String(source ?? "").replace(/\r/g, ""));
    const statements = dgmStatements(rest);
    let at = 0;
    while (at < statements.length && statements[at].startsWith("%%")) front.push(statements[at++]);
    const head = /^(flowchart|graph)(?:\s+(TD|TB|BT|LR|RL))?$/i.exec(statements[at] || "");
    if (!head && DGM_OTHER.test(statements[at] || "")) return null;
    if (head) at++;
    const m = { kind: "flowchart", dir: (head?.[2] || "TD").toUpperCase().replace("TB", "TD"), nodes: [], edges: [], subgraphs: [], kept: [], front };
    const byId = new Map();
    const born = new Map();
    const open = [];
    const snaps = [];
    const touch = (ref) => {
      let n = byId.get(ref.id);
      if (!n) {
        n = { id: ref.id, text: ref.text ?? ref.id, shape: ref.shape || "rect", group: null, ...(ref.md ? { md: true } : {}) };
        byId.set(ref.id, n);
        born.set(ref.id, born.size);
        m.nodes.push(n);
      } else if (ref.shape) Object.assign(n, { shape: ref.shape, text: ref.text ?? n.text, md: ref.md });
      if (n.md === undefined || n.md === false) delete n.md;
      //: A node belongs to the first subgraph it is named inside.
      if (n.group == null && open.length) n.group = open[open.length - 1];
    };
    const keep = (line) => {
      m.kept.push({ at: 0, line });
      snaps.push({ n: born.size, e: m.edges.length, s: m.subgraphs.length });
    };
    for (const s of statements.slice(at)) {
      const sub = /^subgraph\s+(.+)$/.exec(s);
      if (DGM_KEPT.test(s)) keep(s);
      else if (sub) {
        const g = dgmSubgraph(sub[1].trim(), open.length ? open[open.length - 1] : null);
        if (!m.subgraphs.some((o) => o.id === g.id)) m.subgraphs.push(g);
        open.push(g.id);
      } else if (s === "end" && open.length) open.pop();
      else {
        const chain = s === "end" ? null : dgmChain(s);
        if (!chain) keep(s);
        else {
          chain.refs.forEach(touch);
          m.edges.push(...chain.links);
        }
      }
    }
    //: A subgraph named in an edge is the group, not a node of its own.
    const groups = new Set(m.subgraphs.map((g) => g.id));
    m.nodes = m.nodes.filter((n) => !groups.has(n.id));
    const rows = dgmRows(m).filter((r) => r.unit);
    const seen = (u, snap) => (u.t === "n" ? born.get(m.nodes[u.i].id) < snap.n : u.t === "e" ? u.i < snap.e : u.i < snap.s);
    snaps.forEach((snap, k) => {
      m.kept[k].at = rows.filter((r) => seen(r.unit, snap)).length;
    });
    dgmLift(m);
    return m;
  }

  //: The builder's own `style` and `linkStyle` lines become `fill` and `colour`; every other one stays a kept line.
  function dgmLift(m) {
    m.kept = m.kept.filter((k) => {
      const hit = DGM_STYLE.exec(k.line);
      const node = hit && dgmTint(hit[3]) === hit[2] && m.nodes.find((n) => n.id === hit[1]);
      if (node) node.fill = hit[3];
      const arrow = DGM_LINKSTYLE.exec(k.line);
      const edge = arrow && m.edges[Number(arrow[1])];
      if (edge) edge.colour = arrow[2];
      return !node && !edge;
    });
  }

  //: The source range of the ```mermaid fence in `text` whose source is `source` (the one nearest `near`
  //: when several repeat): `{from, to}`, the lines between the fences, so a replace keeps both fences
  //: and everything around them byte for byte. Null when no fence holds it any more.
  function dgmFence(text, source, near = 0) {
    let best = null;
    const re = /^```[ \t]*mermaid[^\n]*\n([\s\S]*?)\n```[ \t]*$/gm;
    for (let m = re.exec(text); m; m = re.exec(text)) {
      if (m[1] !== source) continue;
      const from = m.index + m[0].indexOf("\n") + 1;
      if (!best || Math.abs(m.index - near) < Math.abs(best.at - near)) best = { at: m.index, from, to: from + source.length };
    }
    return best && { from: best.from, to: best.to };
  }

  //: `decode`, `front` and `statements` are the readers the other kinds share (diagram-kinds.js).
  const diagramModel = { MAX_NODES: DGM_MAX_NODES, parse: dgmParse, print: dgmPrint, decode: dgmDecode, front: dgmFront, statements: dgmStatements, fence: dgmFence };
  // DIAGRAM-MODEL-END

  //: Read (and so the print and the HTML export, which are drawn from it): each
  //: mermaid fence is handed to the lazy `mermaid` module (mermaid-draw.js), which
  //: asks the diagram frame and swaps the fence for its picture; one the parser
  //: refuses stays the code block with the reason under it. The promise is kept
  //: so an export or a print can wait for the pictures before it saves the page.
  function docRenderMermaidIn(container) {
    if (!container.querySelector('.code-block code[data-lang="mermaid"]')) return;
    docPhase2State.mermaidDrawn = ensureModule("mermaid")
      .then((ok) => (ok ? mermaidDrawIn(container) : null))
      .catch(() => null);
  }

  //: Resolves when the pictures of the page being saved or printed are in.
  async function docMermaidWhenDrawn() {
    await docPhase2State.mermaidDrawn;
    //: Only a page that loaded the module has pictures to wait for.
    if (await lazyModuleLoads.get("mermaid")) await mermaidSettled();
  }

  //: Live: a mermaid fence the caret is outside of is its figure, through a
  //: state field for the reason the columns block gives (a replace that spans
  //: line breaks may not come from a plugin). Pressing the figure puts the
  //: caret on the fence's first line, which shows the text to edit.
  function docMermaidBlocks(text) {
    const blocks = [];
    const re = /^```[ \t]*mermaid[^\n]*\n([\s\S]*?)\n```[ \t]*$/gm;
    for (let m = re.exec(text); m; m = re.exec(text)) {
      blocks.push({ from: m.index, to: m.index + m[0].length, source: m[1] });
    }
    return blocks;
  }

  function docMermaidField(CM) {
    if (docPhase2State.mermaidFieldCache) return docPhase2State.mermaidFieldCache;
    const { StateField, StateEffect } = CM.state;
    const { Decoration, EditorView, WidgetType } = CM.view;
    //: Sent when a fence the frame refused is known, so the field draws it as the
    //: code it is (with the reason) instead of leaving a figure that never fills.
    const recheck = StateEffect.define();
    class DocMermaidWidget extends WidgetType {
      constructor(source, from) {
        super();
        this.source = source;
        this.from = from;
      }
      //: The source alone (DX1): with the start in it, a key typed above a diagram
      //: moved every one below and each was drawn again, blob and image, per key.
      eq(other) {
        return other.source === this.source;
      }
      //: What CodeMirror assumes for a widget it has not measured; the figure's
      //: placeholder is about this tall (mermaid-lazy.css), so the page does not jump.
      get estimatedHeight() {
        return 160;
      }
      ignoreEvent(event) {
        return event.type !== "mousedown";
      }
      toDOM(view) {
        //: The figure and its tool in one box: a redraw (a theme change) replaces the figure's children, not the button.
        const wrap = document.createElement("div");
        wrap.className = "cm-md-mermaid-wrap";
        const figure = document.createElement("figure");
        figure.className = "md-mermaid cm-md-mermaid md-mermaid-pending";
        figure.title = "Press to edit the diagram's text";
        //: Async: the placeholder holds the room, then the picture replaces it
        //: and the editor measures the widget again.
        ensureModule("mermaid").then((ok) => {
          if (!ok) return;
          docPhase2State.mermaidReady = true;
          mermaidFill(figure, this.source, (result) => {
            if (result.svg) view.requestMeasure();
            else view.dispatch({ effects: recheck.of(this.source) });
          });
        });
        figure.addEventListener("mousedown", (event) => {
          event.preventDefault();
          const at = Math.min(view.posAtDOM(figure) + 4, view.state.doc.length);
          view.dispatch({ selection: { anchor: at } });
          view.focus();
        });
        //: Edit as blocks (1546 D6): the same builder a diagram document opens in, in a dialog; Done replaces this fence's lines only.
        const edit = smallButton("ph:squares-four", "Edit as blocks", () => {
          const near = Math.min(view.posAtDOM(figure), view.state.doc.length);
          openDiagramBuilder({
            source: this.source,
            title: "Edit diagram",
            draft: `doc:${currentDoc?.id ?? ""}`,
            offer: { fence: [view, this.source, near] },
            onDone: (next, changed) => {
              if (!changed) return;
              const at = diagramModel.fence(docStr(view.state.doc), this.source, near);
              //: The printer ends its source with a line break; the fence's closing line has its own.
              if (at) view.dispatch({ changes: { from: at.from, to: at.to, insert: next.replace(/\n+$/, "") }, userEvent: "input.diagram" });
              else toast("That diagram is no longer in the document.", "info");
            },
          });
        });
        //: Save to Library (R9c), beside Edit.
        const keep = smallButton("ph:books", "Save to Library", async () => (await ensureModule("diagramEmbed")) && diagramModel.embed.save(this.source, { fence: [view, this.source, view.posAtDOM(figure)] }));
        for (const b of [edit, keep]) (b.classList.add("md-mermaid-edit", "icon-only"), b.addEventListener("mousedown", (event) => event.stopPropagation()));
        wrap.append(figure, edit, keep);
        return wrap;
      }
    }
    class DocMermaidReason extends WidgetType {
      constructor(reason, source) {
        super();
        this.reason = reason;
        this.source = source;
      }
      eq(other) {
        return other.reason === this.reason && other.source === this.source;
      }
      toDOM() {
        return mermaidFailure.note(this.reason, this.source);
      }
    }
    //: The fences once per text (DX1): a caret move rescanned the whole document.
    const blocksOf = new WeakMap();
    const build = (state) => {
      let blocks = blocksOf.get(state.doc);
      if (!blocks) {
        const text = docStr(state.doc);
        blocks = text.includes("```mermaid") || /```[ \t]+mermaid/.test(text) ? docMermaidBlocks(text) : [];
        blocksOf.set(state.doc, blocks);
      }
      if (!blocks.length) return Decoration.none;
      const ranges = [];
      for (const block of blocks) {
        //: A reason exists only once the module drew here (the widget above).
        const reason = docPhase2State.mermaidReady ? mermaidFailure(block.source) : "";
        //: A fence the frame refused stays the code it is, with its reason under it.
        if (reason) {
          ranges.push(Decoration.widget({ widget: new DocMermaidReason(reason, block.source), block: true, side: 1 }).range(block.to));
          continue;
        }
        if (docLiveSpanTouched.anchorIn(state.selection.ranges, block.from, block.to)) continue;
        ranges.push(Decoration.replace({ widget: new DocMermaidWidget(block.source, block.from), block: true }).range(block.from, block.to));
      }
      return Decoration.set(ranges, true);
    };
    docPhase2State.mermaidFieldCache = StateField.define({
      create: (state) => build(state),
      update: (value, tr) => (tr.docChanged || tr.selection || tr.effects.some((e) => e.is(recheck)) ? build(tr.state) : value),
      provide: (field) => EditorView.decorations.from(field),
    });
    return docPhase2State.mermaidFieldCache;
  }

  //: The builder in a dialog (1546 D6) for every place that draws Mermaid from a source it can hand back
  //: (a Live figure, a board's diagram): `{source, kind, title, onDone(source)}`. The code is the lazy
  //: diagram-embed.js; this is its stand-in, because the callers are in this bundle.
  async function openDiagramBuilder(options) {
    if (await ensureModule("diagramEmbed")) return diagramModel.embed.open(options);
    toast("The diagram editor did not load. Try again.", "info");
    return null;
  }

  //: The sheet of existing diagrams and "New diagram" (diagram-suggest.js `choose`): a row, `true` for New, or null.
  async function chooseDiagram(options) {
    return (await ensureModule("diagramSuggest")) ? diagramModel.suggest.choose(options) : null;
  }

  //: **The one door to the Diagram builder** (INBOX 1588). Every list that offers it (the palette, Find anything, Tools and
  //: features, Quick access, both "/" menus, Chat, the Library's Create, the board's Insert) ends here, through the `diagram`
  //: row of `POPUP_TOOLS`. Over a board or a mind map it is the board's own `wbEditDiagram` (a diagram object lands on Done);
  //: over a text box it opens the builder on the starter and makes a .mmd document and writes `![[Title]]` at the caret on Done (1621 D5); anywhere else (or `doc`) it
  //: opens the builder and saves a new .mmd document on Done. Cancel changes nothing; Done keeps what the dialog shows.
  //: A diagram made from the builder is a document the lists do not know yet: the Library's `docs` (the sidebar, the Live view's link
  //: resolver) and the `[[` picker's cache are given the row, so `![[Title]]` draws in Read view at once and not after a reload.
  function diagramMadeKnown(made) {
    const other = (list) => [made, ...(Array.isArray(list) ? list : []).filter((d) => d.id !== made.id)];
    if (typeof docs !== "undefined") docs = other(docs);
    if (typeof editorDocumentCache !== "undefined" && editorDocumentCache?.length) editorDocumentCache = other(editorDocumentCache);
    if ($("doc-list")) renderDocList();
  }

  async function diagramDoor({ target = null, doc = false } = {}) {
    //: `window.`: no Library bundle means no board; `typeof` because the boards bundle may not have loaded.
    const onBoard = !doc && Boolean(window.wbCommandsLive?.()) && (!target || Boolean(target.closest?.("#library-view-whiteboard")));
    if (onBoard && typeof wbEditDiagram === "function") return wbEditDiagram();
    //: The text box as a surface (the adapter `editorBlock` writes through), whether it was handed a surface, a textarea or an editable inside one.
    const box = !doc && target && target.isConnected !== false && (target.id === "question" || target.id in EDITOR_SURFACES || editorSurfaceKind(target)) ? editorSurfaceFor(target) : null;
    //: A text box asks first (R12, owner 2026-11-12): a diagram already made is embedded at once, "New diagram" opens the empty builder.
    const pick = box ? await chooseDiagram({ verb: "Embed" }) : null;
    if (box && !pick) return null;
    if (box && pick !== true) {
      box.focus?.();
      return editorBlock(box, `![[${pick.title}]]`, "", "");
    }
    //: **Anywhere else, the builder itself, then a .mmd document on Done** (the owner: "searching up and clicking
    //: the diagram builder in the find anything search took me to the documents editor and did nothing else, it
    //: didnt even show the panel"). A blank .mmd page is made by its first keystroke, so the door used to show
    //: the last document and no builder. Cancel makes nothing.
    if (!box) {
      return openDiagramBuilder({
        //: A drawn three-box starter, its first box selected (DD-3b, 1107; it was empty so the walkthrough showed, R6.8): the
        //: first connected diagram is names typed over boxes that exist. Clear in the ... menu empties it.
        source: diagramModel.starter,
        title: "Diagram builder",
        named: true,
        draft: "new",
        existing: { pick: () => chooseDiagram({ fresh: false }), open: async (row) => (await ensureModule("library"), switchTab("documents"), loadDocuments(row.id)) },
        //: The window's title names the document and the exports; blank is dated, so two Done presses are two names (DD-12, 1107).
        onDone: async (next, _changed, name) => {
          const made = await apiJson("/documents", { method: "POST", body: JSON.stringify({ title: name || `Diagram ${new Date().toISOString().slice(0, 16).replace("T", " ")}`, content: next, file_type: "mmd" }) }).catch(() => (toast("The diagram was not saved. Try Done again.", "info"), null));
          if (!made) return;
          if (!(await ensureModule("library"))) return toast("The diagram was saved. Open the Library to see it.", "info");
          switchTab("documents");
          await loadDocuments(made.id);
          offerCreateUndo(made);
        },
      });
    }
    return openDiagramBuilder({
      source: "",
      title: "Diagram builder",
      named: true,
      draft: "new-embed",
      //: Done makes the `.mmd` row and writes a live reference to it (1621 D5), so the diagram has one home and a page of its own.
      //: The window hands back a clean, unused title, so `![[Title]]` finds this row.
      onDone: async (next, _changed, name) => {
        if (!String(next).trim()) return toast("Add a block first, or Cancel.", "info");
        const title = name || `Diagram ${new Date().toISOString().slice(0, 16).replace("T", " ")}`;
        const made = await apiJson("/documents", { method: "POST", body: JSON.stringify({ title, content: next, file_type: "mmd" }) }).catch(() => (toast("The diagram was not saved. Try Done again.", "info"), null));
        if (!made) return;
        offerCreateUndo(made);
        diagramMadeKnown(made);
        box.focus?.();
        editorBlock(box, `![[${made.title || title}]]`, "", "");
      },
    });
  }
  //: What a new diagram opens on, so the blocks and the picture show at once (the board's Insert used the same lines).
  diagramModel.starter = "flowchart TD\n  A[Start] --> B{Ready?}\n  B -->|yes| C[Ship it]";
  //: Exported on `diagramModel`, not as a global name of its own: callers ask for the library bundle first, or this file alone.
  diagramModel.door = diagramDoor;
  diagramModel.madeKnown = diagramMadeKnown;

  //: A toolbar is one Tab stop; Left and Right move between its visible controls. Here because the builder opens without the Library bundle.
  function wireToolbarRoving(bar) {
    const all = () => [...bar.querySelectorAll("button, select, summary")];
    const rove = (to) => all().forEach((el) => { el.tabIndex = el === to ? 0 : -1; });
    rove(bar.querySelector("button"));
    bar.addEventListener("focusin", (event) => {
      if (all().includes(event.target)) rove(event.target);
    });
    bar.addEventListener("keydown", (event) => {
      const step = { ArrowRight: 1, ArrowLeft: -1 }[event.key];
      if (!step || event.target.tagName === "SELECT") return;
      const shown = all().filter((el) => !el.disabled && el.getClientRects().length);
      const next = shown[shown.indexOf(event.target) + step];
      if (!next) return;
      event.preventDefault();
      next.focus();
    });
  }

  //: The file's whole surface: what documents.js and documents-export.js call.
  Object.assign(window, { wireToolbarRoving, docRenderMermaidIn, docMermaidWhenDrawn, docMermaidField, diagramModel, openDiagramBuilder, chooseDiagram });
  //: The block pane (1546 P2) is a bundle of its own, fetched when a diagram is first shown (the kinds, 1546 P4, when a mind map, timeline or sequence diagram is):
  //: every caller is in this bundle or opens a document first, so no stand-in is needed, and
  //: neither app.js nor lazy-entries.js (both at their caps) carries the row.
  Object.assign(LAZY_MODULES, { diagramBuilder: ["/css/diagram-lazy.css", "/js/diagram-builder.js"], diagramEmbed: ["/js/diagram-embed.js"], diagramTouch: ["/js/diagram-touch.js"], diagramView: ["/css/value-field.css", "/js/value-field.js", "/js/diagram-view.js"], diagramOverlay: ["/js/diagram-overlay.js"], diagramCanvas: ["/js/diagram-canvas.js"], diagramEdges: ["/js/diagram-edges.js"], diagramEdgePick: ["/js/diagram-edge-pick.js"], diagramSplit: ["/js/diagram-split.js"], diagramLetGo: ["/js/diagram-letgo.js"], diagramComplete: ["/js/diagram-complete.js"], diagramMulti: ["/js/diagram-multi.js"], diagramBar: ["/js/diagram-bar.js"], diagramKindbar: ["/js/diagram-kindbar.js"], diagramSteps: ["/js/diagram-steps.js"], diagramOutline: ["/js/diagram-outline.js"], diagramSuggest: ["/js/diagram-suggest.js"], diagramKinds: ["/js/diagram-kinds.js"], diagramJoins: ["/js/diagram-joins.js"], diagramStyle: ["/js/diagram-style.js"], diagramAi: ["/js/diagram-ai.js"], diagramAiKinds: ["/js/diagram-ai-kinds.js"] });
})();
