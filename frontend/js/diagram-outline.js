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
      //: A lone target stays flush; only a branch indents.
      const targets = [...new Set(next.get(item.id) || [])];
      for (const to of targets) walk(by.get(to), targets.length > 1 ? depth + 1 : depth);
    };
    run.filter((item) => !into.has(item.id)).forEach((item) => walk(item, 0));
    run.forEach((item) => walk(item, 0));
    return out;
  }

  //: `items` is `diagramModel.ops.layout(m)` or a group's `kids`; the result has the same shape, reordered.
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

  //: True when Alt+Up or Down would move the source but leave the drawn list as it is (an invisible move).
  function stuck(m, key, dir) {
    const ids = (items) => items.flatMap((x) => [x.type + x.id, ...(x.kids ? ids(x.kids) : [])]).join();
    const trial = structuredClone(m);
    return diagramModel.ops.step(trial, key, dir) && ids(order(trial, diagramModel.ops.layout(trial))) === ids(order(m, diagramModel.ops.layout(m)));
  }

  //: A box (a Mermaid subgraph) around one block, from its menu (1679 m); around several is the selection bar's "Box them". `h` is the builder's helpers.
  function box(S, h, key) {
    const id = diagramModel.ops.wrap(S.m, [key]);
    if (!id) return h.say(S, "That block could not be boxed.");
    S.sel = diagramModel.ops.key("g", id);
    h.commit(S, `Boxed ${h.name(S, key)}. Rename the box to say what it holds.`);
  }

  diagramModel.outline = { order, offer, stuck, box };
})();
