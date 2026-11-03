// diagram-ops.js: the pure half of the block pane, the changes a gesture makes to a flowchart's model (1546 P2; moved out
// of diagram-builder.js by 1594, which was over its size target). A plain lazy file, fetched by the builder's `show`
// with the drag code. Nothing here reaches the DOM: tests/test_diagram_builder.py runs the region between
// `DIAGRAM-OPS-BEGIN` and `-END` in node.
//
// One closure, one export: `diagramModel.ops`.
(() => {
  // DIAGRAM-OPS-BEGIN
  //: **Keys name blocks**: `n:<id>` a node, `g:<id>` a subgraph, `k:<n>` a kept
  //: line. Every function here changes the model in place and answers whether
  //: it did; none draws. Kept lines hold their place by the unit they stood
  //: before (`dgbEdit` anchors them first and re-anchors after), so a
  //: `direction` line inside a group is still inside it once a group is added above.
  const DGB_SHAPES = ["rect", "round", "stadium", "circle", "diamond", "hexagon"];
  const DGB_MAX = 120;
  //: The kinds a person meets that the blocks do not draw (D3): named in the one line that sends them to Source.
  const DGB_PLAIN = [[/^stateDiagram/i, "state diagrams"], [/^classDiagram/i, "class diagrams"], [/^pie$/i, "pie charts"], [/^gantt$/i, "Gantt charts"], [/^journey$/i, "user journeys"], [/^erDiagram/i, "ER diagrams"], [/^C4/i, "C4 diagrams"]];

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
    relabel: dgbRelabel, step: dgbStep, nest: dgbNest, lift: dgbLift, inside: dgbInside, SHAPES: DGB_SHAPES, MAX: DGB_MAX, PLAIN: DGB_PLAIN,
  };
  // DIAGRAM-OPS-END

  diagramModel.ops = diagramOps;
})();
