// diagram-builder.js: the block pane of a diagram (1546 P2, DOCUMENTS_PLAN
// "1546 design" D5 to D10). Lazy: `LAZY_MODULES.diagramBuilder`, registered at
// the foot of documents-mermaid.js, so nothing of it is in the boot scripts.
//
// A diagram is edited as blocks, never as text first: a palette of shapes and a
// group, a tree of cards (a node is a card, a group is a card holding cards),
// the joins as chips under the card they leave, and the live picture beside
// it. Every gesture is one change to the model (`diagramModel`, documents-
// mermaid.js) printed to the whole source and handed to `io.set`, so the
// source is the only state and the document's own history is the undo.
// `DIAGRAM-OPS-BEGIN`/`END` is the pure part (node-tested, tests/test_diagram_
// builder.py); the rest is the DOM, made with createElement and textContent.
//
// One closure, one export: `diagramModel.builder` (no new global name).
(() => {
  // DIAGRAM-OPS-BEGIN
  //: **Keys name blocks**: `n:<id>` a node, `g:<id>` a subgraph, `k:<n>` a kept
  //: line. Every function here changes the model in place and answers whether
  //: it did; none draws. Kept lines hold their place by the unit they stood
  //: before (`dgbEdit` anchors them first and re-anchors after), so a
  //: `direction` line inside a group is still inside it once a group is added above.
  const DGB_SHAPES = ["rect", "round", "stadium", "circle", "diamond", "hexagon"];
  const DGB_MAX = 120;

  const dgbKey = (type, id) => `${type}:${id}`;
  const dgbSplit = (key) => [key.slice(0, 1), key.slice(2)];
  const dgbIds = (m) => new Set([...m.nodes.map((n) => n.id), ...m.subgraphs.map((g) => g.id)]);
  const dgbNode = (m, id) => m.nodes.find((n) => n.id === id);
  const dgbGroup = (m, id) => m.subgraphs.find((g) => g.id === id);

  //: A first free id: A to Z, then N27 and on for a node; G1 and on for a group.
  function dgbFreshId(m, group) {
    const used = dgbIds(m);
    if (!group) for (let c = 65; c < 91; c++) if (!used.has(String.fromCharCode(c))) return String.fromCharCode(c);
    for (let i = group ? 1 : 27; ; i++) if (!used.has(`${group ? "G" : "N"}${i}`)) return `${group ? "G" : "N"}${i}`;
  }

  //: The blocks as a nested list in the order the source prints them (groups
  //: first, then nodes; `diagramModel.print`), each kept line where it stood:
  //: `{type: "g", id, kids}`, `{type: "n", id}`, `{type: "k", index, line}`.
  function dgbLayout(m) {
    const kept = (m.kept || []).map((k, index) => ({ ...k, index })).sort((a, b) => a.at - b.at || a.index - b.index);
    const groups = new Set(m.subgraphs.map((g) => g.id));
    const parentOf = (g) => (groups.has(g.parent) && g.parent !== g.id ? g.parent : null);
    const done = new Set();
    let units = 0;
    let next = 0;
    const put = (into, limit) => {
      while (next < kept.length && kept[next].at <= limit) into.push({ type: "k", index: kept[next].index, line: kept[next++].line });
    };
    const emit = (group, into) => {
      m.subgraphs.forEach((g, i) => {
        if (parentOf(g) !== group || done.has(i)) return;
        done.add(i);
        put(into, units++);
        const item = { type: "g", id: g.id, kids: [] };
        into.push(item);
        emit(g.id, item.kids);
      });
      m.nodes.forEach((n) => {
        if ((groups.has(n.group) ? n.group : null) !== group) return;
        put(into, units++);
        into.push({ type: "n", id: n.id });
      });
    };
    const top = [];
    emit(null, top);
    put(top, Infinity);
    return top;
  }

  //: The units in the order a kept line's `at` counts them: groups and nodes as
  //: the layout walks them, then the edges.
  function dgbUnits(m) {
    const out = [];
    const walk = (items) => {
      for (const item of items) {
        if (item.type === "k") continue;
        out.push(item.type === "g" ? dgbGroup(m, item.id) : dgbNode(m, item.id));
        if (item.kids) walk(item.kids);
      }
    };
    walk(dgbLayout({ ...m, kept: [] }));
    return [...out, ...m.edges];
  }

  //: Runs a change with the kept lines held where they stood; false when it refused.
  function dgbEdit(m, change) {
    const before = dgbUnits(m);
    const anchors = (m.kept || []).map((k) => before[k.at] || null);
    const result = change();
    if (!result) return result;
    const units = dgbUnits(m);
    (m.kept || []).forEach((k, i) => {
      const at = anchors[i] ? units.indexOf(anchors[i]) : -1;
      k.at = at >= 0 ? at : anchors[i] ? Math.min(k.at, units.length) : units.length;
    });
    return result;
  }

  //: The group a block sits in (null at the top), or undefined for no such block.
  function dgbParentOf(m, key) {
    const [type, id] = dgbSplit(key);
    const item = type === "n" ? dgbNode(m, id) : type === "g" ? dgbGroup(m, id) : null;
    return item ? (type === "n" ? item.group : item.parent) ?? null : undefined;
  }

  //: Whether `id` is `group` or sits anywhere inside it.
  function dgbInside(m, id, group) {
    for (let at = id, hops = 0; at && hops < 200; hops++) {
      if (at === group) return true;
      at = dgbGroup(m, at)?.parent;
    }
    return false;
  }

  //: Moves a block into `group` (null: the top) before the block `before` (null:
  //: last). A node dropped before a group goes first among that group's nodes
  //: and a group dropped before a node goes last among its sisters, because the
  //: source prints groups ahead of nodes. A group cannot go inside itself.
  function dgbMove(m, key, group = null, before = null) {
    const [type, id] = dgbSplit(key);
    const item = type === "n" ? dgbNode(m, id) : type === "g" ? dgbGroup(m, id) : null;
    if (!item || before === key || (group && !dgbGroup(m, group)) || (type === "g" && group && dgbInside(m, group, id))) return false;
    return dgbEdit(m, () => {
      const list = type === "n" ? m.nodes : m.subgraphs;
      list.splice(list.indexOf(item), 1);
      if (type === "n") item.group = group;
      else item.parent = group;
      const same = (x) => ((type === "n" ? x.group : x.parent) ?? null) === group;
      const [bt, bid] = before ? dgbSplit(before) : [];
      //: The id this one goes in front of, among the same kind.
      const ahead = bt === type ? bid : type === "n" && bt === "g" ? list.find(same)?.id : null;
      let at = ahead ? list.findIndex((x) => x.id === ahead) : -1;
      if (at < 0) {
        const last = list.reduce((hit, x, i) => (same(x) ? i : hit), -1);
        at = last >= 0 ? last + 1 : list.length;
      }
      list.splice(at, 0, item);
      return true;
    });
  }

  function dgbAddNode(m, { shape = "rect", text = "Step", group = null, before = null } = {}) {
    if (m.nodes.length >= DGB_MAX || (group && !dgbGroup(m, group))) return null;
    const node = { id: dgbFreshId(m, false), text, shape: DGB_SHAPES.includes(shape) ? shape : "rect", group };
    const added = dgbEdit(m, () => m.nodes.push(node));
    if (added && before) dgbMove(m, dgbKey("n", node.id), group, before);
    return added ? node.id : null;
  }

  function dgbAddGroup(m, { title = "Group", parent = null, before = null } = {}) {
    if (parent && !dgbGroup(m, parent)) return null;
    const g = { id: dgbFreshId(m, true), title, parent };
    const added = dgbEdit(m, () => m.subgraphs.push(g));
    if (added && before) dgbMove(m, dgbKey("g", g.id), parent, before);
    return added ? g.id : null;
  }

  //: Removes a block with the joins that touch it. A group lifts its blocks out
  //: to its own parent. `{joins, lifted}` counts what went with it or moved.
  function dgbRemove(m, key) {
    const [type, id] = dgbSplit(key);
    const item = type === "n" ? dgbNode(m, id) : type === "g" ? dgbGroup(m, id) : null;
    if (!item) return null;
    return dgbEdit(m, () => {
      const was = m.edges.length;
      m.edges = m.edges.filter((e) => e.from !== id && e.to !== id);
      let lifted = 0;
      if (type === "n") m.nodes.splice(m.nodes.indexOf(item), 1);
      else {
        for (const n of m.nodes) if (n.group === id) Object.assign(n, { group: item.parent ?? null }), lifted++;
        for (const g of m.subgraphs) if (g.parent === id) Object.assign(g, { parent: item.parent ?? null }), lifted++;
        m.subgraphs.splice(m.subgraphs.indexOf(item), 1);
      }
      return { joins: was - m.edges.length, lifted };
    });
  }

  //: Joins two blocks (a node or a group each); null when one is missing or the
  //: same join is already there.
  function dgbJoin(m, from, to, extra = {}) {
    const ids = dgbIds(m);
    const edge = { from, to, label: "", style: "solid", arrow: true, ...extra };
    if (!ids.has(from) || !ids.has(to)) return null;
    if (m.edges.some((e) => e.from === from && e.to === to && e.label === edge.label && e.style === edge.style && e.arrow === edge.arrow)) return null;
    return dgbEdit(m, () => m.edges.push(edge)) ? edge : null;
  }

  function dgbUnjoin(m, edge) {
    return dgbEdit(m, () => {
      const at = m.edges.indexOf(edge);
      return at >= 0 && m.edges.splice(at, 1);
    });
  }

  //: A label, in place. An empty one is refused (Mermaid draws an empty box as nothing).
  function dgbRelabel(m, key, text) {
    const [type, id] = dgbSplit(key);
    const clean = String(text ?? "").replace(/\s*\n\s*/g, " ").trim();
    const item = type === "n" ? dgbNode(m, id) : type === "g" ? dgbGroup(m, id) : null;
    if (!item || !clean) return false;
    if (type === "n") item.text = clean;
    else item.title = clean;
    return true;
  }

  //: The blocks sharing a parent with `key`, in the order the tree shows them.
  function dgbSisters(m, key) {
    const parent = dgbParentOf(m, key);
    if (parent === undefined) return null;
    let list = dgbLayout({ ...m, kept: [] });
    const find = (items) => items.reduce((hit, x) => hit || (x.type === "g" ? (x.id === parent ? x.kids : find(x.kids)) : null), null);
    if (parent) list = find(list) || [];
    return { parent, keys: list.map((x) => dgbKey(x.type, x.id)) };
  }

  //: One place up (-1) or down (1) among its sisters; nodes and groups keep their
  //: own order, so a node steps over the nodes only.
  function dgbStep(m, key, dir) {
    const sis = dgbSisters(m, key);
    if (!sis) return false;
    const same = sis.keys.filter((k) => k[0] === key[0]);
    const to = same.indexOf(key) + dir;
    if (to < 0 || to >= same.length) return false;
    return dgbMove(m, key, sis.parent, dir < 0 ? same[to] : same[to + 1] || null);
  }

  //: Alt+Right: into the nearest group above it among its sisters (the source prints
  //: groups ahead of nodes, so every group of a level is above its nodes).
  function dgbNest(m, key) {
    const sis = dgbSisters(m, key);
    const above = sis && sis.keys.slice(0, sis.keys.indexOf(key)).reverse().find((k) => k[0] === "g");
    return Boolean(above && dgbMove(m, key, above.slice(2)));
  }

  //: Alt+Left: out of its group, to just after it.
  function dgbLift(m, key) {
    const parent = dgbParentOf(m, key);
    if (!parent) return false;
    const groups = dgbSisters(m, dgbKey("g", parent)).keys.filter((k) => k[0] === "g");
    const after = groups[groups.indexOf(dgbKey("g", parent)) + 1] || null;
    return dgbMove(m, key, dgbGroup(m, parent).parent ?? null, key[0] === "g" ? after : null);
  }

  const diagramOps = {
    layout: dgbLayout, key: dgbKey, split: dgbSplit, node: dgbNode, group: dgbGroup, sisters: dgbSisters, parentOf: dgbParentOf,
    addNode: dgbAddNode, addGroup: dgbAddGroup, move: dgbMove, remove: dgbRemove, join: dgbJoin, unjoin: dgbUnjoin,
    relabel: dgbRelabel, step: dgbStep, nest: dgbNest, lift: dgbLift, inside: dgbInside, SHAPES: DGB_SHAPES, MAX: DGB_MAX,
  };
  // DIAGRAM-OPS-END

  // ---------------------------------------------------------------------------
  // The pane
  // ---------------------------------------------------------------------------
  const SHAPE_LABEL = { rect: "Box", round: "Rounded", stadium: "Pill", circle: "Circle", diamond: "Decision", hexagon: "Hexagon" };
  const SHAPE_TEXT = { rect: "Step", round: "Step", stadium: "Start", circle: "Event", diamond: "Question?", hexagon: "Prepare" };
  //: The six link kinds, as the join chip's menu words them.
  const LINKS = [
    ["solid", true, "Arrow"], ["solid", false, "Line"], ["dotted", true, "Dotted arrow"],
    ["dotted", false, "Dotted line"], ["thick", true, "Thick arrow"], ["thick", false, "Thick line"],
  ];
  const DIRS = [["TD", "down", "Top to bottom"], ["LR", "right", "Left to right"], ["BT", "up", "Bottom to top"], ["RL", "left", "Right to left"]];
  //: The instance of a mounted pane, by its root element.
  const panes = new WeakMap();

  function el(tag, cls, text) {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text != null) node.textContent = text;
    return node;
  }

  const say = (S, text) => {
    S.live.textContent = "";
    //: A second message in the same turn still reads: the region is emptied, then filled a tick later.
    setTimeout(() => (S.live.textContent = text), 20);
  };

  const titleOf = (S, id) => diagramOps.node(S.m, id)?.text ?? diagramOps.group(S.m, id)?.title ?? id;
  const nameOf = (S, key) => titleOf(S, diagramOps.split(key)[1]);

  const blockEl = (S, key) => (key ? [...S.tree.querySelectorAll(".dgm-block")].find((b) => b.dataset.key === key) : null);

  //: One change printed: the whole source goes out when it differs, the pane is
  //: drawn again and `said` is announced. The first change to a source the
  //: printer would have written differently says so once.
  function commit(S, said) {
    const src = diagramModel.print(S.m);
    if (src !== S.source) {
      const tidy = S.tidy;
      S.tidy = false;
      S.source = src;
      S.io.set(src);
      if (tidy) said = `${said} Tidied the source.`;
    }
    say(S, said);
    render(S);
    drawPicture(S);
  }

  // --- the picture ----------------------------------------------------------------
  //: The nodes' boxes, read off the SVG text with patterns: `{id, x, y, w, h}` in the
  //: picture's own units, from Mermaid's `flowchart-<id>-<n>` groups. Not through
  //: DOMParser: a parsed document keeps the page's policy, and Mermaid's `style=`
  //: attributes were refused one by one (measured: 19 console errors on a 3-node
  //: diagram). Null when the picture has none.
  function boxesOf(svg) {
    const vb = /<svg\b[^>]*\bviewBox="([^"]+)"/.exec(svg)?.[1].trim().split(/[ ,]+/).map(Number);
    if (!vb || vb.length !== 4 || vb.some(Number.isNaN)) return null;
    const num = (tag, name) => Number(new RegExp("\\b" + name + '="(-?[\\d.]+)"').exec(tag)?.[1]) || 0;
    const boxes = [];
    for (const g of svg.matchAll(/<g\b[^>]*\bid="flowchart-([^"]+?)-\d+"[^>]*>/g)) {
      const at = /transform="translate\(\s*(-?[\d.]+)[ ,]+(-?[\d.]+)/.exec(g[0]);
      if (!at) continue;
      const tail = svg.slice(g.index + g[0].length, g.index + g[0].length + 900);
      const rect = /<rect\b[^>]*>/.exec(tail)?.[0] || "";
      const poly = /<polygon\b[^>]*\bpoints="([^"]+)"/.exec(tail)?.[1].trim().split(/[ ,]+/).map(Number) || [];
      const xs = poly.filter((_, i) => i % 2 === 0);
      const ys = poly.filter((_, i) => i % 2 === 1);
      const r = num(/<circle\b[^>]*>/.exec(tail)?.[0] || "", "r") * 2;
      boxes.push({
        id: g[1], x: Number(at[1]), y: Number(at[2]),
        w: num(rect, "width") || (xs.length ? Math.max(...xs) - Math.min(...xs) : 0) || r || 80,
        h: num(rect, "height") || (ys.length ? Math.max(...ys) - Math.min(...ys) : 0) || r || 40,
      });
    }
    return boxes.length ? { vb, boxes } : null;
  }

  function drawPicture(S) {
    clearTimeout(S.drawTimer);
    S.drawTimer = setTimeout(() => {
      const source = S.source;
      const stamp = ++S.drawn;
      //: A kind the blocks cannot read (S.plain) still has its picture; only a flowchart with no block yet is empty.
      const empty = !source.trim() || (!S.plain && S.m && !S.m.nodes.length);
      S.fig.classList.toggle("dgm-picture-empty", empty);
      if (empty) return S.fig.replaceChildren(el("p", "muted dgm-hint", "The picture appears here as you add blocks."));
      ensureModule("mermaid").then((ok) => {
        if (!ok || stamp !== S.drawn) return;
        mermaidFill(S.fig, source, (result) => {
          if (stamp !== S.drawn) return;
          S.hit = result.svg ? boxesOf(result.svg) : null;
          if (result.svg) return;
          S.fig.classList.remove("md-mermaid-pending");
          S.fig.replaceChildren(mermaidFailure.note(result.error, source));
        });
      });
    }, 120);
  }

  //: A press on a drawn node selects its block. Not a drag: the picture is not a handle.
  function pictureClick(S, event) {
    const img = event.target.closest?.("img");
    if (!img || !S.hit || !S.m) return;
    const r = img.getBoundingClientRect();
    const [vx, vy, vw, vh] = S.hit.vb;
    const x = vx + ((event.clientX - r.left) / r.width) * vw;
    const y = vy + ((event.clientY - r.top) / r.height) * vh;
    const box = S.hit.boxes.find((b) => Math.abs(x - b.x) <= b.w / 2 && Math.abs(y - b.y) <= b.h / 2);
    if (!box || !diagramOps.node(S.m, box.id)) return;
    select(S, diagramOps.key("n", box.id), true);
  }

  // --- the tree -------------------------------------------------------------------
  function render(S) {
    const had = S.tree.contains(document.activeElement);
    const layout = diagramOps.layout(S.m);
    const edgesFrom = new Map();
    S.m.edges.forEach((e) => edgesFrom.set(e.from, [...(edgesFrom.get(e.from) || []), e]));
    if (S.sel && !blockKeys(layout).includes(S.sel)) S.sel = null;
    S.tree.replaceChildren(...layout.map((item) => buildBlock(S, item, 1, edgesFrom)));
    S.empty.classList.toggle("hidden", Boolean(layout.length));
    //: An empty pane is the one stop, so N and G work before there is a block to focus.
    S.pane.tabIndex = layout.length ? -1 : 0;
    const stop = blockEl(S, S.sel) || S.tree.querySelector(".dgm-block");
    for (const b of S.tree.querySelectorAll(".dgm-block")) {
      b.tabIndex = b === stop ? 0 : -1;
      b.setAttribute("aria-selected", String(b.dataset.key === S.sel));
    }
    if (had) stop?.focus();
    for (const b of S.dirs.querySelectorAll("button")) {
      b.classList.toggle("active", b.dataset.dir === S.m.dir);
      b.setAttribute("aria-pressed", String(b.dataset.dir === S.m.dir));
    }
  }

  const blockKeys = (items) => items.flatMap((x) => (x.type === "k" ? [] : [diagramOps.key(x.type, x.id), ...blockKeys(x.kids || [])]));

  function shapeGlyph(shape) {
    const glyph = el("span", "dgm-shape");
    glyph.dataset.shape = shape;
    glyph.setAttribute("aria-hidden", "true");
    return glyph;
  }

  function buildBlock(S, item, level, edgesFrom) {
    const block = el("div", "dgm-block");
    if (item.type === "k") {
      block.classList.add("dgm-kept");
      block.dataset.key = `k:${item.index}`;
      block.setAttribute("role", "treeitem");
      block.setAttribute("aria-level", String(level));
      block.setAttribute("aria-label", `Kept line: ${item.line}`);
      block.title = "Blocks cannot edit this line. It stays in the source where it is.";
      const lock = el("i", "ph ph-lock-simple dgm-kept-icon");
      lock.setAttribute("aria-hidden", "true");
      block.append(el("div", "dgm-card"));
      block.firstChild.append(lock, el("code", "dgm-label", item.line));
      return block;
    }
    const key = diagramOps.key(item.type, item.id);
    const isGroup = item.type === "g";
    const data = isGroup ? diagramOps.group(S.m, item.id) : diagramOps.node(S.m, item.id);
    const text = isGroup ? data.title : data.text;
    block.dataset.key = key;
    block.setAttribute("role", "treeitem");
    block.setAttribute("aria-level", String(level));
    const joins = edgesFrom.get(item.id) || [];
    block.setAttribute("aria-label", `${text}, ${isGroup ? "group" : SHAPE_LABEL[data.shape].toLowerCase()}${joins.length ? `, ${joins.length} ${joins.length === 1 ? "join" : "joins"}` : ""}`);
    if (isGroup) {
      block.classList.add("dgm-group");
      block.setAttribute("aria-expanded", "true");
    }
    const card = el("div", "dgm-card");
    const grip = el("span", "dgm-grip");
    grip.dataset.objGrip = "";
    grip.title = "Drag to move";
    const dots = el("i", "ph ph-dots-six-vertical");
    dots.setAttribute("aria-hidden", "true");
    grip.append(dots);
    const label = el("span", "dgm-label", text);
    card.append(grip, isGroup ? groupGlyph() : shapeGlyph(data.shape), label);
    const menu = kebabMenu(blockItems(S, key), `Menu for ${text}`);
    menu.classList.add("dgm-menu");
    card.append(menu);
    block.append(card);
    if (joins.length) {
      const row = el("div", "dgm-joins");
      for (const edge of joins) row.append(joinChip(S, edge));
      block.append(row);
    }
    if (isGroup) {
      const kids = el("div", "dgm-kids");
      kids.setAttribute("role", "group");
      if (item.kids.length) kids.append(...item.kids.map((k) => buildBlock(S, k, level + 1, edgesFrom)));
      else kids.append(el("p", "dgm-hole muted", "Drop blocks here"));
      block.append(kids);
    }
    return block;
  }

  function groupGlyph() {
    const icon = el("i", "ph ph-stack dgm-group-icon");
    icon.setAttribute("aria-hidden", "true");
    return icon;
  }

  function joinChip(S, edge) {
    const chip = el("button", "dgm-join");
    chip.type = "button";
    const to = titleOf(S, edge.to);
    const arrow = el("i", `ph ${edge.arrow ? "ph-arrow-right" : "ph-minus"}`);
    arrow.setAttribute("aria-hidden", "true");
    chip.dataset.style = edge.style;
    chip.append(arrow, el("span", "dgm-join-to", to));
    if (edge.label) chip.append(el("span", "dgm-join-label muted", edge.label));
    chip.title = "Change this join";
    chip.setAttribute("aria-label", `Join to ${to}${edge.label ? `, ${edge.label}` : ""}. Opens its menu.`);
    chip.addEventListener("click", () => {
      const r = chip.getBoundingClientRect();
      openMenuAtPoint(joinItems(S, edge), "This join", r.left, r.bottom, chip);
    });
    return chip;
  }

  // --- menus ----------------------------------------------------------------------
  function joinItems(S, edge) {
    const to = titleOf(S, edge.to);
    const links = LINKS.map(([style, arrow, name]) => ({
      label: `${edge.style === style && edge.arrow === arrow ? "ph:check" : "ph:arrow-right"} ${name}`,
      run: () => {
        Object.assign(edge, { style, arrow });
        commit(S, `Join to ${to} is now a ${name.toLowerCase()}.`);
      },
      group: "kind",
    }));
    return [
      ...links,
      {
        label: "ph:text-t Label",
        run: async () => {
          const text = await promptDialog(`Label for the join to ${to}`, edge.label, { confirmLabel: "Save" });
          if (text === null) return;
          edge.label = text.trim();
          commit(S, edge.label ? `Labelled the join ${edge.label}.` : "Cleared the join label.");
        },
        group: "edit",
      },
      { label: "ph:trash Remove join", danger: true, run: () => (diagramOps.unjoin(S.m, edge), commit(S, `Removed the join to ${to}.`)), group: "edit" },
    ];
  }

  function blockItems(S, key) {
    const [type] = diagramOps.split(key);
    const isNode = type === "n";
    const items = [
      { label: "ph:pencil-simple Rename", run: () => relabel(S, key), group: "edit" },
      { label: "ph:arrow-bend-down-right Join to…", run: () => joinPick(S, key), group: "edit" },
      { label: isNode ? "ph:plus Add block after" : "ph:plus Add block inside", run: () => addBlock(S, { after: isNode ? key : null, into: isNode ? null : key }), group: "edit" },
    ];
    if (isNode) {
      items.push({
        label: "ph:diamond Shape",
        items: diagramOps.SHAPES.map((shape) => ({
          label: `${diagramOps.node(S.m, diagramOps.split(key)[1]).shape === shape ? "ph:check" : "ph:square"} ${SHAPE_LABEL[shape]}`,
          run: () => {
            diagramOps.node(S.m, diagramOps.split(key)[1]).shape = shape;
            commit(S, `${nameOf(S, key)} is now a ${SHAPE_LABEL[shape].toLowerCase()}.`);
          },
        })),
        group: "edit",
      });
    }
    items.push(
      { label: "ph:arrow-up Move up", run: () => stepBlock(S, key, -1), group: "move" },
      { label: "ph:arrow-down Move down", run: () => stepBlock(S, key, 1), group: "move" },
      { label: "ph:arrow-line-right Nest into the group above", run: () => nestBlock(S, key, true), group: "move" },
      { label: "ph:arrow-line-left Lift out of its group", run: () => nestBlock(S, key, false), group: "move" },
      { label: isNode ? "ph:trash Delete" : "ph:trash Delete group", danger: true, run: () => removeBlock(S, key), group: "end" }
    );
    return items;
  }

  // --- gestures -------------------------------------------------------------------
  function select(S, key, focus = false) {
    S.sel = key;
    for (const b of S.tree.querySelectorAll(".dgm-block")) {
      b.tabIndex = b.dataset.key === key ? 0 : -1;
      b.setAttribute("aria-selected", String(b.dataset.key === key));
    }
    if (focus) {
      const b = blockEl(S, key);
      b?.focus();
      b?.scrollIntoView({ block: "nearest" });
    }
  }

  //: A shape, or a group, added after the block `after`, inside the group `into`,
  //: or (neither) after the selection. `edit` opens its label for typing.
  function addBlock(S, { shape = S.shape, group = false, after = S.sel, into = null, before = undefined, edit = true } = {}) {
    const m = S.m;
    const sel = after && !into ? after : null;
    const parent = into ? diagramOps.split(into)[1] : sel ? diagramOps.parentOf(m, sel) : null;
    const next = sel ? diagramOps.sisters(m, sel) : null;
    const sisters = next ? next.keys.filter((k) => k[0] === (group ? "g" : "n")) : [];
    const ahead = before !== undefined ? before : sel && sisters.includes(sel) ? sisters[sisters.indexOf(sel) + 1] || null : null;
    const id = group ? diagramOps.addGroup(m, { parent, before: ahead }) : diagramOps.addNode(m, { shape, text: SHAPE_TEXT[shape], group: parent, before: ahead });
    if (!id) return say(S, group ? "That group cannot be added." : `A diagram holds at most ${diagramOps.MAX} blocks.`);
    if (!group) S.shape = shape;
    const key = diagramOps.key(group ? "g" : "n", id);
    S.sel = key;
    commit(S, `Added ${group ? "a group" : `a ${SHAPE_LABEL[shape].toLowerCase()}`}${sel ? ` after ${nameOf(S, sel)}` : ""}.`);
    if (edit) relabel(S, key);
    return key;
  }

  function relabel(S, key) {
    const b = blockEl(S, key);
    if (!b || key[0] === "k") return;
    const label = b.querySelector(":scope > .dgm-card > .dgm-label");
    beginEdit(S, label, nameOf(S, key), (text) => {
      if (!diagramOps.relabel(S.m, key, text)) return;
      if (text === nameOf(S, key) && S.source === diagramModel.print(S.m)) return render(S);
      commit(S, `Renamed to ${text}.`);
    }, key);
  }

  //: A label in place (the `wbBeginTextEdit` pattern): Enter commits, Escape puts it back.
  function beginEdit(S, target, was, done, key = null) {
    if (!target || target.isContentEditable) return;
    target.setAttribute("contenteditable", "plaintext-only");
    target.classList.add("dgm-editing");
    target.focus();
    const range = document.createRange();
    range.selectNodeContents(target);
    const sel = window.getSelection();
    sel.removeAllRanges();
    sel.addRange(range);
    let over = false;
    const end = (keep) => {
      if (over) return;
      over = true;
      target.removeEventListener("keydown", onKey);
      target.removeEventListener("blur", onBlur);
      const text = target.textContent.trim();
      target.removeAttribute("contenteditable");
      target.classList.remove("dgm-editing");
      if (keep && text !== was) done(text);
      else target.textContent = was;
      if (key) blockEl(S, key)?.focus();
    };
    const onKey = (event) => {
      if (event.key !== "Enter" && event.key !== "Escape") return;
      event.preventDefault();
      event.stopPropagation();
      end(event.key === "Enter");
    };
    const onBlur = () => end(true);
    target.addEventListener("keydown", onKey);
    target.addEventListener("blur", onBlur);
  }

  function stepBlock(S, key, dir) {
    if (key[0] === "k") return;
    if (!diagramOps.step(S.m, key, dir)) return say(S, `${nameOf(S, key)} is already ${dir < 0 ? "first" : "last"}.`);
    commit(S, `Moved ${nameOf(S, key)} ${dir < 0 ? "up" : "down"}.`);
  }

  function nestBlock(S, key, into) {
    if (key[0] === "k") return;
    const ok = into ? diagramOps.nest(S.m, key) : diagramOps.lift(S.m, key);
    if (!ok) return say(S, into ? "There is no group just above to nest into." : `${nameOf(S, key)} is not inside a group.`);
    const parent = diagramOps.parentOf(S.m, key);
    commit(S, into ? `Nested ${nameOf(S, key)} into ${nameOf(S, diagramOps.key("g", parent))}.` : `Lifted ${nameOf(S, key)} out.`);
  }

  function removeBlock(S, key) {
    if (key[0] === "k") return;
    const sis = diagramOps.sisters(S.m, key);
    const near = sis && (sis.keys[sis.keys.indexOf(key) + 1] || sis.keys[sis.keys.indexOf(key) - 1] || (sis.parent ? diagramOps.key("g", sis.parent) : null));
    const name = nameOf(S, key);
    const gone = diagramOps.remove(S.m, key);
    if (!gone) return;
    S.sel = near && near !== key ? near : null;
    const extra = [gone.joins ? `${gone.joins} ${gone.joins === 1 ? "join" : "joins"}` : "", gone.lifted ? `${gone.lifted} ${gone.lifted === 1 ? "block" : "blocks"} stayed` : ""].filter(Boolean);
    commit(S, `Deleted ${name}${extra.length ? ` with ${extra.join(", ")}` : ""}.`);
  }

  function joinPick(S, key) {
    const from = diagramOps.split(key)[1];
    const shell = pickerDialog({ title: `Join ${nameOf(S, key)} to`, placeholder: "Search the blocks…", searchLabel: "Search the blocks" });
    const box = pickerListbox(shell, "Blocks");
    const paint = () => {
      const needle = shell.search.value.trim().toLowerCase();
      const items = [
        ...S.m.nodes.filter((n) => n.id !== from).map((n) => ({ icon: "ph:square", label: n.text, about: "Block", value: n.id })),
        ...S.m.subgraphs.filter((g) => g.id !== from).map((g) => ({ icon: "ph:stack", label: g.title, about: "Group", value: g.id })),
      ].filter((item) => !needle || item.label.toLowerCase().includes(needle));
      box.fill(items, needle, { icon: "ph:squares-four", title: needle ? "No block matches" : "No other block yet", text: needle ? "Try other words." : "Add a block to join to." });
    };
    shell.search.addEventListener("input", paint);
    paint();
    new Promise((resolve) => shell.open(resolve)).then((to) => {
      if (!to) return blockEl(S, key)?.focus();
      const edge = diagramOps.join(S.m, from, to);
      const name = titleOf(S, to);
      if (!edge) return say(S, `${nameOf(S, key)} is already joined to ${name}.`);
      S.sel = key;
      commit(S, `Joined ${nameOf(S, key)} to ${name}.`);
      blockEl(S, key)?.focus();
    });
  }

  // --- keyboard -------------------------------------------------------------------
  function onKey(S, event) {
    const block = event.target.closest?.(".dgm-block");
    if (event.target.isContentEditable || !block || event.target.closest(".menu-wrap, .dgm-join")) return;
    const key = block.dataset.key;
    const all = [...S.tree.querySelectorAll(".dgm-block")];
    const at = all.indexOf(block);
    const go = (target) => target && select(S, target.dataset.key, true);
    const mod = event.ctrlKey || event.metaKey;
    if (mod && !event.altKey && /^[zy]$/i.test(event.key)) {
      event.preventDefault();
      return event.shiftKey || /y/i.test(event.key) ? S.io.redo() : S.io.undo();
    }
    if (event.altKey && !mod) {
      const act = { ArrowUp: () => stepBlock(S, key, -1), ArrowDown: () => stepBlock(S, key, 1), ArrowRight: () => nestBlock(S, key, true), ArrowLeft: () => nestBlock(S, key, false) }[event.key];
      if (!act) return;
      event.preventDefault();
      event.stopPropagation();
      return act();
    }
    if (mod) return;
    const plain = {
      ArrowDown: () => go(all[at + 1]), ArrowUp: () => go(all[at - 1]), Home: () => go(all[0]), End: () => go(all.at(-1)),
      ArrowLeft: () => go(block.parentElement.closest(".dgm-block")), ArrowRight: () => go(block.querySelector(".dgm-block")),
      Enter: () => relabel(S, key), F2: () => relabel(S, key),
      Insert: () => addBlock(S, { after: key }), n: () => addBlock(S, { after: key }), N: () => addBlock(S, { after: key }),
      g: () => addBlock(S, { after: key, group: true }), G: () => addBlock(S, { after: key, group: true }),
      j: () => key[0] !== "k" && joinPick(S, key), J: () => key[0] !== "k" && joinPick(S, key),
      Delete: () => removeBlock(S, key), Backspace: () => removeBlock(S, key),
      ContextMenu: () => menuAt(S, block), F10: () => event.shiftKey && menuAt(S, block),
    }[event.key];
    if (!plain || (event.shiftKey && event.key.length > 1 && event.key !== "F10")) return;
    event.preventDefault();
    plain();
  }

  function menuAt(S, block) {
    if (block.dataset.key[0] === "k") return;
    const r = block.querySelector(".dgm-card").getBoundingClientRect();
    openMenuAtPoint(blockItems(S, block.dataset.key), "Block menu", r.left + r.width / 2, r.bottom, block);
  }

  // --- the pointer mode: obj-drag.js's one gesture, with a mode of its own ---------
  //: A block (or a palette tile) is grabbed by `seed`, ahead of the app's object
  //: cards; the drop is one change to the model. Over a block's top or bottom
  //: edge the drop is before or after it; over a group's head, into it; over the
  //: middle of another block, a join.
  function seedBlock(event) {
    const target = event.target;
    const tile = target.closest?.(".dgm-tile");
    const block = target.closest?.(".dgm-card")?.closest(".dgm-block");
    const root = (tile || block)?.closest(".dgm");
    const S = root && panes.get(root);
    if (!S || target.closest(".menu-wrap, .dgm-join, [contenteditable]") || (block?.classList.contains("dgm-kept") && !tile)) return null;
    const key = tile ? null : block.dataset.key;
    const title = tile ? tile.dataset.title : nameOf(S, key);
    return { card: tile || block.querySelector(":scope > .dgm-card"), ref: { kind: "block", id: key || tile.dataset.shape, title }, grip: Boolean(target.closest("[data-obj-grip]")), S, key, tile };
  }

  //: Whether the block `k` is the dragged group or sits inside it.
  const within = (m, k, group) => diagramOps.inside(m, k[0] === "g" ? k.slice(2) : diagramOps.node(m, k.slice(2))?.group, group);

  function dropAt(g) {
    const { S, key } = g;
    const at = document.elementFromPoint(g.x, g.y);
    if (!at || !S.pane.contains(at)) return null;
    const block = at.closest(".dgm-block");
    if (!block) return { op: "into", group: null, before: null };
    const over = block.dataset.key;
    if (over[0] === "k" || (key && (over === key || (key[0] === "g" && within(S.m, over, key.slice(2)))))) return null;
    const card = block.querySelector(":scope > .dgm-card");
    const r = card.getBoundingClientRect();
    const f = (g.y - r.top) / r.height;
    const sis = diagramOps.sisters(S.m, over);
    if (over[0] === "g") return f < 0.25 ? { op: "before", key: over, group: sis.parent, before: over, card } : { op: "into", key: over, group: over.slice(2), before: null, card };
    const nextKey = sis.keys.slice(sis.keys.indexOf(over) + 1).find((k) => k[0] !== "k") || null;
    //: A palette tile has no join to make: its top half is before, its bottom half after.
    const [lo, hi] = key ? [0.3, 0.7] : [0.5, 0.5];
    if (f <= lo) return { op: "before", key: over, group: sis.parent, before: over, card };
    if (f >= hi) return { op: "after", key: over, group: sis.parent, before: nextKey, card, below: true };
    return { op: "join", key: over, card };
  }

  function dropMark(g, target) {
    const { S } = g;
    S.hot?.classList.remove("dgm-target");
    S.hot = null;
    const line = S.drop;
    line.classList.add("hidden");
    if (!target) return;
    if (target.card && (target.op === "into" || target.op === "join")) {
      S.hot = target.card;
      return target.card.classList.add("dgm-target");
    }
    if (target.card) {
      const pane = S.pane.getBoundingClientRect();
      const r = target.card.getBoundingClientRect();
      line.classList.remove("hidden");
      line.style.top = `${(target.below ? r.bottom : r.top) - pane.top + S.pane.scrollTop - 1}px`;
      line.style.left = `${r.left - pane.left + S.pane.scrollLeft}px`;
      line.style.width = `${r.width}px`;
    }
  }

  function dropApply(g, target) {
    const { S } = g;
    const m = S.m;
    if (g.tile) {
      const group = g.tile.dataset.shape === "group";
      if (target.op === "join") return;
      return addBlock(S, { shape: group ? S.shape : g.tile.dataset.shape, group, after: null, into: null, before: target.before ?? null, edit: false, ...(target.group ? { into: diagramOps.key("g", target.group) } : {}) });
    }
    if (target.op === "join") {
      const from = g.key.slice(2);
      const edge = diagramOps.join(m, from, target.key.slice(2));
      if (!edge) return say(S, `${nameOf(S, g.key)} is already joined to ${nameOf(S, target.key)}.`);
      return commit(S, `Joined ${nameOf(S, g.key)} to ${nameOf(S, target.key)}.`);
    }
    if (!diagramOps.move(m, g.key, target.group, target.before)) return;
    S.sel = g.key;
    commit(S, target.op === "into" && target.group ? `Nested ${nameOf(S, g.key)} into ${nameOf(S, diagramOps.key("g", target.group))}.` : `Moved ${nameOf(S, g.key)}.`);
  }

  const DIAGRAM_MODE = {
    seed: seedBlock,
    grab: () => ({}),
    begin(g) {
      g.scroller = g.S.pane;
      g.dragEl = g.tile ? null : blockEl(g.S, g.key);
      g.dragEl?.classList.add("dgm-lifted");
    },
    update(g) {
      g.target = dropAt(g);
      dropMark(g, g.target);
    },
    drop(g) {
      dropMark(g, null);
      g.dragEl?.classList.remove("dgm-lifted");
      if (g.target) dropApply(g, g.target);
    },
    cancel(g) {
      dropMark(g, null);
      g.dragEl?.classList.remove("dgm-lifted");
    },
  };

  // --- building the pane ----------------------------------------------------------
  function buildPalette(S) {
    const bar = el("div", "dock dgm-dock");
    bar.dataset.dockName = "diagram";
    bar.setAttribute("role", "toolbar");
    bar.setAttribute("aria-label", "Diagram blocks");
    const shapes = el("div", "dock-group dgm-palette");
    for (const shape of [...diagramOps.SHAPES, "group"]) {
      const tile = el("button", "dgm-tile");
      tile.type = "button";
      tile.dataset.shape = shape;
      tile.dataset.objGrip = "";
      tile.dataset.title = shape === "group" ? "Group" : SHAPE_LABEL[shape];
      tile.title = `Add a ${tile.dataset.title.toLowerCase()}: press, or drag it into the blocks`;
      tile.setAttribute("aria-label", `Add a ${tile.dataset.title.toLowerCase()}`);
      tile.append(shape === "group" ? groupGlyph() : shapeGlyph(shape), el("span", "dgm-tile-name", tile.dataset.title));
      tile.addEventListener("click", () => addBlock(S, { shape: shape === "group" ? S.shape : shape, group: shape === "group" }));
      shapes.append(tile);
    }
    S.dirs = el("div", "seg dgm-dirs");
    S.dirs.setAttribute("role", "group");
    S.dirs.setAttribute("aria-label", "Direction of the diagram");
    for (const [dir, arrow, name] of DIRS) {
      const b = el("button");
      b.type = "button";
      b.dataset.dir = dir;
      b.title = name;
      b.setAttribute("aria-label", name);
      const icon = el("i", `ph ph-arrow-${arrow}`);
      icon.setAttribute("aria-hidden", "true");
      b.append(icon);
      b.addEventListener("click", () => {
        S.m.dir = dir;
        commit(S, `${name}.`);
      });
      S.dirs.append(b);
    }
    const actions = el("div", "dock-actions");
    for (const [icon, label, run] of [["ph:arrow-counter-clockwise", "Undo", () => S.io.undo()], ["ph:arrow-clockwise", "Redo", () => S.io.redo()]]) {
      const b = smallButton(icon, label, run);
      b.classList.add("icon-only");
      b.setAttribute("aria-label", label);
      actions.append(b);
    }
    bar.append(shapes, el("div", "dock-group"), actions);
    bar.children[1].append(S.dirs);
    return bar;
  }

  function mount(host, io, text) {
    host.replaceChildren();
    const root = el("div", "dgm");
    const S = { host, root, io, source: text, m: null, sel: null, shape: "rect", drawn: 0, hit: null, tidy: false };
    S.live = el("p", "visually-hidden dgm-live");
    S.live.setAttribute("role", "status");
    S.live.setAttribute("aria-live", "polite");
    S.tree = el("div", "dgm-tree");
    S.tree.setAttribute("role", "tree");
    S.tree.setAttribute("aria-label", "Diagram blocks");
    S.empty = el("p", "muted dgm-hint", "Press a shape above, or press N, to add the first block. Drag blocks to move, nest or join them.");
    S.drop = el("div", "dgm-drop hidden");
    S.pane = el("div", "dgm-pane");
    S.pane.setAttribute("aria-label", "Diagram blocks. Press N for a block or G for a group.");
    S.pane.setAttribute("role", "region");
    S.pane.append(S.tree, S.empty, S.drop);
    S.fig = el("figure", "dgm-picture");
    const body = el("div", "dgm-body");
    body.append(S.pane, S.fig);
    S.note = el("p", "muted dgm-hint hidden", "");
    root.append(buildPalette(S), S.note, body, S.live);
    host.append(root);
    panes.set(root, S);
    S.tree.addEventListener("keydown", (event) => onKey(S, event));
    S.tree.addEventListener("click", (event) => {
      const block = event.target.closest(".dgm-block");
      if (block && !event.target.closest(".menu-wrap, .dgm-join")) select(S, block.dataset.key);
    });
    S.tree.addEventListener("dblclick", (event) => {
      const label = event.target.closest(".dgm-label");
      const block = label?.closest(".dgm-block");
      if (block && block.dataset.key[0] !== "k") relabel(S, block.dataset.key);
    });
    S.tree.addEventListener("contextmenu", (event) => {
      const block = event.target.closest(".dgm-block");
      if (!block || block.dataset.key[0] === "k") return;
      event.preventDefault();
      openMenuAtPoint(blockItems(S, block.dataset.key), "Block menu", event.clientX, event.clientY, block);
    });
    wireLongPress(S.tree, (event, point) => {
      const block = event.target.closest?.(".dgm-block");
      if (block && block.dataset.key[0] !== "k") openMenuAtPoint(blockItems(S, block.dataset.key), "Block menu", point.x, point.y, block);
    });
    S.fig.addEventListener("click", (event) => pictureClick(S, event));
    S.pane.addEventListener("keydown", (event) => {
      if (event.target === S.pane && /^[nNgG]$|^Insert$/.test(event.key)) addBlock(S, { after: null, group: /^[gG]$/.test(event.key) });
    });
    sync(host, text, S);
    return S;
  }

  //: Reads the source into the model. Another kind of diagram, or a source the
  //: reader cannot take, is shown as its picture alone with one line saying why.
  function sync(host, text, S = panes.get(host.querySelector(".dgm"))) {
    if (!S) return null;
    S.source = text;
    //: More blocks than the pane holds (`DGB_MAX`) is the same answer as another kind: the picture and a line.
    const read = diagramModel.parse(text);
    const big = Boolean(read && read.nodes.length > DGB_MAX);
    const parsed = big ? null : read;
    S.tidy = Boolean(parsed && text.trim() && diagramModel.print(parsed) !== text);
    S.plain = !parsed;
    S.root.classList.toggle("dgm-plain", !parsed);
    S.note.classList.toggle("hidden", Boolean(parsed));
    S.note.textContent = parsed ? "" : big ? `This diagram has more than ${DGB_MAX} blocks. It stays in Source, and its picture is drawn here.` : "Blocks draw flowcharts for now. This diagram stays in Source, and its picture is drawn here.";
    S.m = parsed || { kind: "flowchart", dir: "TD", nodes: [], edges: [], subgraphs: [], kept: [], front: [] };
    S.root.querySelector(".dgm-dock").classList.toggle("hidden", !parsed);
    S.pane.classList.toggle("hidden", !parsed);
    render(S);
    drawPicture(S);
    return S;
  }

  //: What documents.js calls: the pane in `host` for this source, mounted once,
  //: then only told the source when it changed from outside (a typed edit, an undo).
  async function show(host, io, text) {
    await Promise.all(["/css/objmove-lazy.css", "/js/obj-ref.js", "/js/obj-drag.js"].map((file) => lazyScript(file)));
    if (typeof OBJ_MODES === "object" && !OBJ_MODES.diagram) OBJ_MODES.diagram = DIAGRAM_MODE;
    const S = panes.get(host.querySelector(":scope > .dgm"));
    if (!S) return mount(host, io, text);
    S.io = io;
    return text === S.source ? S : sync(host, text, S);
  }

  diagramModel.builder = { show, ops: diagramOps };
})();
