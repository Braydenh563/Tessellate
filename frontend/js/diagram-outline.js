// diagram-outline.js: reading a flowchart (INBOX 1679, slices 6 and 7): the block list in flow order with depth, and the sideways offer. Lazy: `LAZY_MODULES.diagramOutline`,
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

  //: "Turn it sideways", one line under the toolbar, once per diagram (1679, slice 7): `want` is diagram-view.js's `math.sideways`.
  //: A press turns it (one change); Keep ends the offer. Kept on S so a redraw does not ask again.
  function offer(S, want) {
    const show = want && !S.sidewaysAsked && Boolean(S.turn);
    if (!show) return S.sideways?.classList.add("hidden");
    if (!S.sideways) {
      const line = document.createElement("div");
      line.className = "dgm-sideways muted";
      const words = document.createElement("span");
      words.textContent = "This chart is tall for this pane.";
      const turn = smallButton("ph:arrow-right Turn it sideways", "Draw it left to right", () => ((S.sidewaysAsked = true), S.turn("LR")), false);
      const keep = smallButton("Keep", "Leave it top to bottom", () => ((S.sidewaysAsked = true), line.classList.add("hidden")));
      line.append(words, turn, keep);
      S.note.after(line);
      S.sideways = line;
    }
    S.sideways.classList.remove("hidden");
  }

  diagramModel.outline = { order, offer };
})();
