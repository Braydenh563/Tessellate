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

  //: "Turn it sideways", one line in the picture pane, once per diagram (1679, slice 7): `want` is diagram-view.js's `math.sideways`
  //: on a drawing that is shrunk to fit. A press turns it (one change); Keep ends the offer for that diagram for good: the host is
  //: kept in `answered`, so a redraw or a rebuilt pane after an edit does not ask again. Keyed by the diagram (`io.key`, the
  //: document's id) and not by the host: documents draw every diagram into the one #doc-preview, so a host key turned the offer
  //: off for all of them (review 1108). A dialog has no id and its own host, so the host stays its key.
  const answered = new Set();
  const whose = (S) => S.io?.key ?? S.host;
  function offer(S, want) {
    const show = want && !answered.has(whose(S)) && Boolean(S.turn);
    //: The overview (diagram-minimap.js) shares the stage's bottom-left corner with this row: while the row shows, the
    //: overview rises by its height (INBOX 1737, it lay over the words). On a phone the row is at the top (absolute), so not.
    const lift = (on) => {
      const map = S.sideways?.parentElement?.querySelector(":scope > .dgm-minimap");
      const below = on && globalThis.getComputedStyle?.(S.sideways).position !== "absolute";
      if (map) map.style.insetBlockEnd = below ? `calc(var(--space-5) + ${S.sideways.offsetHeight + 8}px)` : "";
    };
    if (!show) return S.sideways?.classList.add("hidden"), lift(false);
    if (!S.sideways) {
      const line = document.createElement("div");
      //: A `.notice` (DESIGN.md): the mark, the words, then the two actions; the words wrap before the buttons do.
      line.className = "notice dgm-sideways";
      const mark = document.createElement("i");
      mark.className = "ph ph-arrows-left-right";
      mark.setAttribute("aria-hidden", "true");
      const words = document.createElement("span");
      words.textContent = "This chart is tall for this pane.";
      const done = () => answered.add(whose(S));
      const turn = smallButton("ph:arrow-right Turn it sideways", "Draw it left to right", () => (done(), S.turn("LR")), false);
      const keep = smallButton("Keep", "Leave it top to bottom", () => (done(), line.classList.add("hidden"), lift(false)));
      line.append(mark, words, turn, keep);
      //: In the picture's stage, not the whole builder: it straddled the list and the picture (blind test 1108).
      (S.fig.parentElement || S.note.parentElement).append(line);
      S.sideways = line;
    }
    S.sideways.classList.remove("hidden");
    lift(true);
  }

  //: True when Alt+Up or Down would move the source but leave the drawn list as it is (an invisible move).
  function stuck(m, key, dir) {
    const ids = (items) => items.flatMap((x) => [x.type + x.id, ...(x.kids ? ids(x.kids) : [])]).join();
    const trial = structuredClone(m);
    return diagramModel.ops.step(trial, key, dir) && ids(order(trial, diagramModel.ops.layout(trial))) === ids(order(m, diagramModel.ops.layout(m)));
  }

  //: Alt+Up or Down, and a drop before or after a neighbour, on blocks the arrows order (dgbt-1109 1): two blocks in a chain swap by
  //: rewiring, so the drawn order really changes (the source order alone leaves the list as it is). A branch refuses: `false`.
  function swap(m, key, dir) {
    if (key[0] !== "n") return false;
    const id = key.slice(2);
    const into = (x) => m.edges.filter((e) => e.to === x && e.from !== x);
    const out = (x) => m.edges.filter((e) => e.from === x && e.to !== x);
    const link = dir < 0 ? into(id) : out(id);
    if (link.length !== 1) return false;
    const [mid] = link;
    const [up, down] = dir < 0 ? [mid.from, id] : [id, mid.to];
    if (out(up).length !== 1 || into(down).length !== 1) return false;
    into(up).forEach((e) => (e.to = down));
    out(down).forEach((e) => (e.from = up));
    [mid.from, mid.to] = [down, up];
    return true;
  }

  //: Alt+Up or Down and the row menu: a block the arrows order swaps by rewiring them, the rest move in the source; a branch says to drag.
  function move(S, h, key, dir) {
    const fixed = stuck(S.m, key, dir);
    const name = h.name(S, key);
    if (fixed ? !swap(S.m, key, dir) : !diagramModel.ops.step(S.m, key, dir)) return h.say(S, `${name} ${fixed ? "is part of a branch. Drag its grip" : `is already ${dir < 0 ? "first" : "last"}`}.`);
    h.commit(S, `Moved ${name} ${dir < 0 ? "up" : "down"}.`);
  }

  //: A grip dropped before or after the block the arrows put right next to it: the same swap, since moving it in the source alone changes nothing drawn.
  function drop(m, key, { op, key: over }) {
    const [from, to] = op === "before" ? [over.slice(2), key.slice(2)] : [key.slice(2), over.slice(2)];
    return key[0] === "n" && over[0] === "n" && m.edges.some((e) => e.from === from && e.to === to) && swap(m, key, op === "before" ? -1 : 1);
  }

  //: The block a new one is joined to (dgbt-1109 6): the picked block, or with nothing picked the last one; a picked group is nothing to join.
  const tail = (m, sel) => (sel ? (sel[0] === "n" ? sel.slice(2) : null) : m.nodes.at(-1)?.id ?? null);

  //: A box (a Mermaid subgraph) around one block, from its menu (1679 m); around several is the selection bar's "Box them". `h` is the builder's helpers.
  function box(S, h, key) {
    const id = diagramModel.ops.wrap(S.m, [key]);
    if (!id) return h.say(S, "That block could not be boxed.");
    S.sel = diagramModel.ops.key("g", id);
    h.commit(S, `Boxed ${h.name(S, key)}. Rename the box to say what it holds.`);
  }

  diagramModel.outline = { order, offer, stuck, swap, move, drop, tail, box };
})();
