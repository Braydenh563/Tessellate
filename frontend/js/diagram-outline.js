// diagram-outline.js: the block list in flow order with depth (INBOX 1679, slice 6). Lazy: `LAZY_MODULES.diagramOutline`,
// asked for by diagram-builder.js's `show`. The printed source order is the truth (D1); this is only the order the list is
// drawn in: each run of nodes under one parent is walked from the nodes nothing points at, a node's targets right under it
// (the order the arrows were added), `depth` the steps from the root. A node reached twice keeps its first place, so a
// cycle is cut at the first repeat. A group and a kept line stay where the source has them and split a run.
(() => {
  const MAX_DEPTH = 6;

  function flow(edges, run) {
    if (run.length < 2) return run;
    const by = new Map(run.map((item) => [item.id, item]));
    const into = new Set();
    const next = new Map();
    for (const e of edges) {
      if (e.from === e.to || !by.has(e.from) || !by.has(e.to)) continue;
      into.add(e.to);
      next.set(e.from, [...(next.get(e.from) || []), e.to]);
    }
    const seen = new Set();
    const out = [];
    const walk = (item, depth) => {
      if (seen.has(item.id)) return;
      seen.add(item.id);
      out.push(depth ? { ...item, depth: Math.min(depth, MAX_DEPTH) } : item);
      for (const to of next.get(item.id) || []) walk(by.get(to), depth + 1);
    };
    run.filter((item) => !into.has(item.id)).forEach((item) => walk(item, 0));
    run.forEach((item) => walk(item, 0));
    return out;
  }

  //: `items` is `diagramOps.layout(m)` or a group's `kids`; the result has the same shape, reordered.
  function order(m, items) {
    const out = [];
    let run = [];
    const close = () => {
      out.push(...flow(m.edges, run));
      run = [];
    };
    for (const item of items) {
      if (item.type === "n") run.push(item);
      else {
        close();
        out.push(item.kids ? { ...item, kids: order(m, item.kids) } : item);
      }
    }
    close();
    return out;
  }

  diagramModel.outline = { order };
})();
