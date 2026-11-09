// diagram-complete.js: the Mermaid completion list in the Source pane (DD-5, owner 2026-11-09). Lazy:
// `LAZY_MODULES.diagramComplete`, registered at the foot of documents-mermaid.js and asked for by diagram-embed.js's `open`.
// A `.doc-complete-list` under the caret (the documents' completion recipe: the field keeps focus, Up and Down light a row,
// Enter or Tab takes it, Escape closes the list before anything else). The pure half (`DGC-BEGIN` to `-END`) runs in node
// (tests/test_diagram_complete.py): the keyword table, what the caret is on, and the rows it earns.
(() => {
  // DGC-BEGIN
  const FLOW = "flow";
  const SEQ = "seq";
  //: [word, what it is, kind it belongs to (none: every kind), text added after it].
  const KEYWORDS = [
    ["flowchart", "Start a flowchart", FLOW, " "], ["graph", "Start a flowchart (older word)", FLOW, " "], ["sequenceDiagram", "Start a sequence diagram", SEQ, ""],
    ["subgraph", "A group of blocks, closed by end", FLOW, " "], ["end", "Closes a subgraph", FLOW, ""], ["direction", "Direction inside a subgraph", FLOW, " "],
    ["classDef", "Name a look for blocks", FLOW, " "], ["class", "Give blocks a look", FLOW, " "], ["style", "Colour one block", FLOW, " "], ["linkStyle", "Colour an arrow by its number", FLOW, " "],
    ["click", "Make a block a link", FLOW, " "],
    ["participant", "Name someone in the exchange", SEQ, " "], ["actor", "Someone drawn as a person", SEQ, " "], ["autonumber", "Number the messages", SEQ, ""],
    ["activate", "Show someone busy", SEQ, " "], ["deactivate", "Show someone free again", SEQ, " "], ["Note", "A note beside or over someone", SEQ, " "],
    ["loop", "Repeat, closed by end", SEQ, " "], ["alt", "Either or, closed by end", SEQ, " "], ["opt", "Maybe, closed by end", SEQ, " "], ["else", "The other branch of alt", SEQ, ""], ["end", "Closes loop, alt or opt", SEQ, ""],
  ];
  const DIRECTIONS = [["TD", "Top down"], ["TB", "Top to bottom"], ["LR", "Left to right"], ["RL", "Right to left"], ["BT", "Bottom up"]];
  const ARROWS = {
    [FLOW]: [["-->", "Arrow"], ["---", "Line"], ["-.->", "Dotted arrow"], ["-.-", "Dotted line"], ["==>", "Thick arrow"], ["===", "Thick line"], ["<-->", "Both ways"], ["--x", "Ends in a cross"], ["--o", "Ends in a circle"]],
    [SEQ]: [["->>", "Message"], ["-->>", "Dashed message"], ["->", "Line"], ["-->", "Dashed line"], ["-x", "Lost message"], ["--)", "Async message"], ["-)", "Async, solid"]],
  };
  const MAX_ROWS = 8;
  //: The tile of each row by where it came from.
  const ICONS = { key: "ph:text-aa", arrow: "ph:arrow-right", dir: "ph:compass", id: "ph:square" };

  //: The diagram's kind from its first statement: "flow", "seq" or null (nothing yet, or one the list does not know).
  function dgcKind(lines) {
    let front = false;
    for (const [i, raw] of lines.entries()) {
      const line = raw.trim();
      if (i === 0 && line === "---") { front = true; continue; }
      if (front) { if (line === "---") front = false; continue; }
      if (!line || line.startsWith("%%")) continue;
      if (/^(flowchart|graph)\b/.test(line)) return FLOW;
      if (/^sequenceDiagram\b/.test(line)) return SEQ;
      return null;
    }
    return null;
  }

  //: True inside the front matter block (`---` ... `---`) or a `%%` comment line: nothing is offered there.
  function dgcQuiet(lines, row) {
    if (lines[row].trim().startsWith("%%")) return true;
    if (lines[0].trim() !== "---" || row === 0) return false;
    const close = lines.findIndex((l, i) => i > 0 && l.trim() === "---");
    return close === -1 || row <= close;
  }

  //: Ids already in the text: a block's id and a group's (flowchart), or each name in a sequence (`participant X`, `X->>Y`).
  function dgcIds(source, kind, model) {
    if (kind === FLOW && model) return [...model.nodes.map((n) => [n.id, n.text]), ...(model.subgraphs || []).map((g) => [g.id, g.title])];
    const seen = new Map();
    const words = KEYWORDS.map((k) => k[0]);
    for (const m of source.matchAll(/(?:^|\s)(?:participant|actor)\s+([\p{L}\p{N}_]+)(?:\s+as\s+([^\n]+))?|([\p{L}\p{N}_]+)\s*-?-?[>x)]+>?\s*[+-]?([\p{L}\p{N}_]+)/gu)) {
      for (const [id, text] of [[m[1], m[2]], [m[3], ""], [m[4], ""]]) if (id && !words.includes(id) && !seen.has(id)) seen.set(id, (text || "").trim());
    }
    return [...seen];
  }

  //: What the caret is on: the word (or arrow) before it, and the text before that on its line. `null` where nothing is offered.
  function dgcAt(line, col) {
    const before = line.slice(0, col);
    const word = /[\p{L}\p{N}_]+$/u.exec(before);
    const arrow = /[-=.<>ox)]+$/.exec(before);
    const hit = arrow && /^[-=<]/.test(arrow[0]) && (!word || arrow.index > word.index) ? arrow : word;
    if (!hit) return /\s$/.test(before) || before === "" ? { start: col, text: "", head: before } : null;
    //: A word right after a letter or a digit is not a fresh token (`A1x`): the fragment stands only after a space, a bracket or a bar.
    return { start: hit.index, text: hit[0], head: before.slice(0, hit.index) };
  }

  //: The rows for the caret: `{ word, detail, add }`, the part typed already being `text`. `force` (Ctrl+Space) also answers an empty fragment.
  function dgcRows(source, row, col, model, force) {
    const lines = source.split("\n");
    if (!lines[row] || dgcQuiet(lines, row)) return null;
    const at = dgcAt(lines[row], col);
    if (!at) return null;
    const kind = dgcKind(lines);
    const arrowText = /^[-=<]/.test(at.text);
    const turning = /^\s*(?:graph|flowchart|direction)\s+$/.test(at.head);
    if (!arrowText && !turning && at.text.length < 2 && !(force && at.text.length <= 1)) return null;
    //: A new fragment, not the tail of a word: the char before it is a space, nothing, or a bracket. An arrow needs a block before it
    //: and a space or a closing bracket between (so the hyphen in `my-id` offers nothing).
    if (arrowText ? !/\S[\s\])}"]$|\S\s+$/.test(at.head) : !/(^|[\s(\[{|;])$/.test(at.head)) return null;
    const needle = at.text.toLowerCase();
    const first = !at.head.trim();
    let pool = [];
    if (turning) pool = DIRECTIONS.map(([w, d]) => [w, d, "", "dir"]);
    else if (arrowText) pool = ARROWS[kind || FLOW].map(([w, d]) => [w, d, "", "arrow"]);
    else {
      //: Before the diagram has a header only its first words are offered; after it, the statements of its kind.
      const starter = /^(flowchart|graph|sequenceDiagram)$/;
      if (first) pool = KEYWORDS.filter(([w, , k]) => (kind ? k === kind && !starter.test(w) : starter.test(w))).map(([w, d, , add]) => [w, d, add, "key"]);
      if (kind) pool.push(...dgcIds(source, kind, model).filter(([id]) => id.toLowerCase() !== needle).map(([id, text]) => [id, text, "", "id"]));
    }
    const seen = new Set();
    const rows = pool.filter(([w]) => (needle ? w.toLowerCase().startsWith(needle) : true) && w.toLowerCase() !== needle && !seen.has(w) && seen.add(w));
    return rows.length ? { start: at.start, text: at.text, rows: rows.slice(0, MAX_ROWS).map(([word, detail, add, from]) => ({ word, detail, add, from })) } : null;
  }
  // DGC-END

  //: Caret position inside the wrap, from the field's own metrics (it does not wrap, and indents with spaces, so a line is a row and a column a character).
  function point(field, wrap, row, col) {
    const css = getComputedStyle(field);
    const canvas = (point.canvas ||= document.createElement("canvas")).getContext("2d");
    canvas.font = `${css.fontSize} ${css.fontFamily}`;
    const lh = parseFloat(css.lineHeight) || parseFloat(css.fontSize) * 1.5;
    const left = field.offsetLeft + parseFloat(css.borderLeftWidth) + parseFloat(css.paddingLeft) + col * canvas.measureText("0").width - field.scrollLeft;
    const top = field.offsetTop + parseFloat(css.borderTopWidth) + parseFloat(css.paddingTop) + (row + 1) * lh - field.scrollTop;
    return { left: Math.max(0, Math.min(left, wrap.clientWidth - 8)), top, lh };
  }

  function wire(field, wrap, modelOf) {
    const list = document.createElement("ul");
    list.className = "rich-picker-list dgm-complete hidden";
    list.id = `dgm-complete-${Math.random().toString(36).slice(2, 8)}`;
    list.setAttribute("role", "listbox");
    list.setAttribute("aria-label", "Mermaid suggestions");
    wrap.append(list);
    field.setAttribute("role", "combobox");
    field.setAttribute("aria-autocomplete", "list");
    field.setAttribute("aria-controls", list.id);
    field.setAttribute("aria-expanded", "false");
    let at = null;
    let index = 0;
    const isOpen = () => !list.classList.contains("hidden");
    const close = () => {
      list.classList.add("hidden");
      field.setAttribute("aria-expanded", "false");
      field.removeAttribute("aria-activedescendant");
      at = null;
    };
    const mark = () => {
      [...list.children].forEach((li, i) => {
        li.classList.toggle("active", i === index);
        li.setAttribute("aria-selected", String(i === index));
        if (i === index) field.setAttribute("aria-activedescendant", li.id);
      });
      list.children[index]?.scrollIntoView?.({ block: "nearest" });
    };
    const take = (row) => {
      const caret = field.selectionStart;
      field.setRangeText(row.word + row.add, at.start + at.lineStart, caret, "end");
      close();
      field.dispatchEvent(new Event("input"));
    };
    function refresh(force = false) {
      const caret = field.selectionStart;
      if (caret !== field.selectionEnd) return close();
      const upto = field.value.slice(0, caret).split("\n");
      const row = upto.length - 1;
      const found = dgcRows(field.value, row, upto[row].length, modelOf(field.value), force);
      if (!found) return close();
      at = { ...found, lineStart: caret - upto[row].length };
      index = 0;
      list.replaceChildren(...found.rows.map((r, i) => {
        //: The rich picker's row (rich-picker.js): the typed letters marked, what the word is as its second line.
        const li = richPickerRow({ icon: ICONS[r.from], label: r.word, about: r.detail, query: found.text, id: `${list.id}-${i}` });
        //: mousedown, not click: the field keeps its focus and its caret.
        li.addEventListener("mousedown", (event) => (event.preventDefault(), take(r)));
        return li;
      }));
      list.classList.remove("hidden");
      field.setAttribute("aria-expanded", "true");
      const p = point(field, wrap, row, upto[row].length - found.text.length);
      list.style.left = `${p.left}px`;
      //: Under the line, or over it when the list would run past the wrap's foot.
      const room = wrap.clientHeight - p.top;
      list.style.top = `${list.offsetHeight > room && p.top - p.lh > list.offsetHeight ? p.top - p.lh - list.offsetHeight : p.top}px`;
      mark();
    }
    field.addEventListener("input", (event) => (event.inputType ? refresh() : close()));
    field.addEventListener("keydown", (event) => {
      if (event.key === " " && event.ctrlKey) return event.preventDefault(), refresh(true);
      if (!isOpen()) return;
      const rows = list.children.length;
      if (event.key === "ArrowDown" || event.key === "ArrowUp") index = (index + (event.key === "ArrowDown" ? 1 : rows - 1)) % rows, mark();
      else if (event.key === "Enter" || (event.key === "Tab" && !event.shiftKey)) take(at.rows[index]);
      else if (event.key === "Escape") close();
      else if (["ArrowLeft", "ArrowRight", "Home", "End", "PageUp", "PageDown"].includes(event.key)) return close();
      else return;
      event.preventDefault();
      event.stopImmediatePropagation();
    });
    field.addEventListener("blur", close);
    field.addEventListener("pointerdown", close);
    field.addEventListener("scroll", close);
    return { open: isOpen, close };
  }

  diagramModel.complete = { wire, rows: dgcRows, kind: dgcKind };
})();
