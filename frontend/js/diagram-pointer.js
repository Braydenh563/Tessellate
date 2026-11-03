// diagram-pointer.js: the block pane's pointer mode (1546 P2; moved out of diagram-builder.js by 1594 to keep the
// builder under its size target). A plain lazy file, fetched by the builder's `show` with the drag code: a first drag
// is never waiting on it.
//
// A block (or a Add library tile) is grabbed by `seed`, ahead of the app's object cards; the drop is one change to the model.
// Over a block's top or bottom edge the drop is before or after it; over a group's head, into it; over the middle of
// another block, a connector. `make(h)` is the mode (`h` is the builder's helpers); `dropMark` is shared with the
// other kinds' panes, which draw the same line and the same target.
(() => {
  function dropMark(g, target) {
    const { S } = g;
    S.hot?.classList.remove("dgm-target", "dgm-connecting");
    S.hot = null;
    const line = S.drop;
    line.classList.add("hidden");
    if (!target) return;
    if (target.card && (target.op === "into" || target.op === "join")) {
      S.hot = target.card;
      //: Over a block's middle the drop connects, and the card says so.
      target.card.classList.toggle("dgm-connecting", target.op === "join");
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

  function make(h) {
    //: A block (or a palette tile) is grabbed by `seed`, ahead of the app's object
    //: cards; the drop is one change to the model. Over a block's top or bottom
    //: edge the drop is before or after it; over a group's head, into it; over the
    //: middle of another block, a join.
    function seedBlock(event) {
      const target = event.target;
      const tile = target.closest?.(".dgm-tile");
      const block = target.closest?.(".dgm-card")?.closest(".dgm-block");
      const root = (tile || block)?.closest(".dgm");
      const S = root && h.panes.get(root);
      if (!S || target.closest(".menu-wrap, .dgm-join, .dgm-connect, [contenteditable]") || (block?.classList.contains("dgm-kept") && !tile)) return null;
      const key = tile ? null : block.dataset.key;
      const title = tile ? tile.dataset.title : h.name(S, key);
      return { card: tile || block.querySelector(":scope > .dgm-card"), ref: { kind: "block", id: key || tile.dataset.shape, title }, grip: Boolean(target.closest("[data-obj-grip]")), S, key, tile };
    }

    //: Whether the block `k` is the dragged group or sits inside it.
    const within = (m, k, group) => h.ops.inside(m, k[0] === "g" ? k.slice(2) : h.ops.node(m, k.slice(2))?.group, group);

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
      const sis = h.ops.sisters(S.m, over);
      if (over[0] === "g") return f < 0.25 ? { op: "before", key: over, group: sis.parent, before: over, card } : { op: "into", key: over, group: over.slice(2), before: null, card };
      const nextKey = sis.keys.slice(sis.keys.indexOf(over) + 1).find((k) => k[0] !== "k") || null;
      //: A palette tile has no join to make: its top half is before, its bottom half after.
      const [lo, hi] = key ? [0.3, 0.7] : [0.5, 0.5];
      if (f <= lo) return { op: "before", key: over, group: sis.parent, before: over, card };
      if (f >= hi) return { op: "after", key: over, group: sis.parent, before: nextKey, card, below: true };
      return { op: "join", key: over, card };
    }

    function dropApply(g, target) {
      const { S } = g;
      const m = S.m;
      if (g.tile) {
        const group = g.tile.dataset.shape === "group";
        if (target.op === "join") return;
        return h.add(S, { shape: group ? S.shape : g.tile.dataset.shape, text: g.tile.dataset.text, group, after: null, into: null, before: target.before ?? null, edit: false, ...(target.group ? { into: h.ops.key("g", target.group) } : {}) });
      }
      if (target.op === "join") {
        const from = g.key.slice(2);
        const edge = h.ops.join(m, from, target.key.slice(2));
        if (!edge) return h.say(S, `${h.name(S, g.key)} is already connected to ${h.name(S, target.key)}.`);
        return h.commit(S, `Connected ${h.name(S, g.key)} to ${h.name(S, target.key)}.`);
      }
      if (!h.ops.move(m, g.key, target.group, target.before)) return;
      S.sel = g.key;
      h.commit(S, target.op === "into" && target.group ? `Nested ${h.name(S, g.key)} into ${h.name(S, h.ops.key("g", target.group))}.` : `Moved ${h.name(S, g.key)}.`);
    }

    const mode = {
      ancestors: true,
      seed: seedBlock,
      grab: () => ({}),
      begin(g) {
        g.scroller = g.S.pane;
        g.dragEl = g.tile ? null : h.blockEl(g.S, g.key);
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
    return mode;
  }

  diagramModel.pointer = { make, dropMark };
})();
