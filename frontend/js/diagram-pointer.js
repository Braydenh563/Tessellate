// diagram-pointer.js: the block pane's pointer mode (1546 P2; moved out of diagram-builder.js by 1594 to keep the
// builder under its size target). A plain lazy file, fetched by the builder's `show` with the drag code: a first drag
// is never waiting on it.
//
// A block (or a Add library tile) is grabbed by `seed`, ahead of the app's object cards; the drop is one change to the model.
// Over a block's top or bottom edge the drop is before or after it; over a group's head, into it; over the middle of
// another block, a connector. `make(h)` is the mode (`h` is the builder's helpers); `dropMark` is shared with the
// other kinds' panes, which draw the same line and the same target.
(() => {
  //: The caption that says what a drop will do (1679 slice 12): one element for the page, fixed under the target, moved with it.
  let tag = null;
  function word(text, r, host, frame) {
    if (!text || !r) return tag?.classList.add("hidden");
    if (!tag) {
      tag = document.createElement("span");
      tag.className = "dgm-drop-word hidden";
      tag.setAttribute("aria-hidden", "true");
    }
    //: Inside the open dialog's overlay when the drag is in one (that overlay is a z-index 1010 layer, so a caption on the body is under it); last child paints over the dialog.
    const home = host?.closest?.(".modal-overlay") || document.body;
    if (tag.parentElement !== home || tag !== home.lastElementChild) home.append(tag);
    tag.textContent = text;
    tag.classList.remove("hidden");
    const below = r.bottom + 28 < innerHeight;
    let top = below ? r.bottom + 4 : Math.max(4, r.top - 28);
    let left = Math.max(8, Math.min(r.left, innerWidth - 168));
    //: Over the picture the caption stays inside its frame (blind test 1108: it sat at y=749, under the pane).
    if (frame) {
      top = Math.max(frame.top + 4, Math.min(top, frame.bottom - 28));
      left = Math.max(frame.left + 4, Math.min(left, frame.right - 168));
    }
    tag.style.top = `${top}px`;
    tag.style.left = `${left}px`;
  }

  //: The rectangle is read before the marks change, so the caption costs no layout after a write.
  function dropMark(g, target) {
    const r = target?.word && target.card ? target.card.getBoundingClientRect() : null;
    mark(g, target);
    word(target?.word, r, target?.card, target?.canvas ? g.S.fig.getBoundingClientRect() : null);
  }

  function mark(g, target) {
    const { S } = g;
    S.hot?.classList.remove("dgm-target", "dgm-connecting");
    S.hot = null;
    const line = S.drop;
    line.classList.add("hidden");
    if (!target) return;
    //: Over the picture the target is a box (or the whole overlay) the canvas draws; nothing is redrawn until the drop.
    if (target.canvas) return target.card?.classList.add("dgm-target"), (S.hot = target.card);
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
      //: A press on a drawn node takes it, as the grip of its row does (a finger holds first).
      const drawn = !tile && !block && diagramModel.canvas?.node(event, h);
      if (drawn) {
        const at = `n:${drawn.id}`;
        const many = carried(drawn.S, at)?.length;
        return { card: drawn.box, ref: { kind: "block", id: at, title: many ? `${many} blocks` : h.name(drawn.S, at) }, grip: event.pointerType !== "touch", S: drawn.S, key: at, tile: null };
      }
      const root = (tile || block)?.closest(".dgm");
      const S = root && h.panes.get(root);
      if (!S || target.closest(".menu-wrap, .dgm-join, .dgm-connect, [contenteditable]") || (block?.classList.contains("dgm-kept") && !tile)) return null;
      const key = tile ? null : block.dataset.key;
      const title = tile ? tile.dataset.title : h.name(S, key);
      const many = carried(S, key)?.length;
      return { card: tile || block.querySelector(":scope > .dgm-card"), ref: { kind: "block", id: key || tile.dataset.shape, title: many ? `${many} blocks` : title }, grip: Boolean(target.closest("[data-obj-grip]")), S, key, tile };
    }

    //: Whether the block `k` is the dragged group or sits inside it.
    const within = (m, k, group) => h.ops.inside(m, k[0] === "g" ? k.slice(2) : h.ops.node(m, k.slice(2))?.group, group);

    //: The picked keys when the grabbed one is among them (R5): the grip of any picked row carries all of them.
    const carried = (S, key) => (key && S.picked?.size > 1 && S.picked.has(key) ? [...S.picked] : null);

    function dropAt(g) {
      const { S, key } = g;
      const set = carried(S, key);
      const at = document.elementFromPoint(g.x, g.y);
      if (!at || !S.pane.contains(at)) return diagramModel.canvas?.over(g, h) || null;
      const block = at.closest(".dgm-block");
      if (!block) return { op: "into", group: null, before: null };
      const over = block.dataset.key;
      if (over[0] === "k" || (key && (over === key || (key[0] === "g" && within(S.m, over, key.slice(2))))) || set?.some((p) => p === over || (p[0] === "g" && within(S.m, over, p.slice(2))))) return null;
      const card = block.querySelector(":scope > .dgm-card");
      const r = card.getBoundingClientRect();
      const f = (g.y - r.top) / r.height;
      const sis = h.ops.sisters(S.m, over);
      const said = h.name(S, over);
      if (over[0] === "g") return f < 0.25 ? { op: "before", key: over, group: sis.parent, before: over, card, word: `Before ${said}` } : { op: "into", key: over, group: over.slice(2), before: null, card, word: `Into ${said}` };
      const nextKey = sis.keys.slice(sis.keys.indexOf(over) + 1).find((k) => k[0] !== "k") || null;
      //: A palette tile has no join to make: its top half is before, its bottom half after.
      const [lo, hi] = key ? [0.3, 0.7] : [0.5, 0.5];
      if (f <= lo) return { op: "before", key: over, group: sis.parent, before: over, card, word: `Before ${said}` };
      if (f >= hi) return { op: "after", key: over, group: sis.parent, before: nextKey, card, below: true, word: `After ${said}` };
      //: A drop on the middle of an earlier block draws an arrow that runs back up the list; the card says so (W17 C2).
      const own = key && h.ops.sisters(S.m, key).keys;
      const back = own && own.includes(over) && own.indexOf(over) < own.indexOf(key);
      return { op: "join", key: over, card, word: back ? `Connect back to ${said}` : `Connect to ${said}` };
    }

    function dropApply(g, target) {
      const { S } = g;
      const m = S.m;
      if (g.tile) {
        const group = g.tile.dataset.shape === "group";
        if (target.op === "join") return;
        return h.add(S, { shape: group ? S.shape : g.tile.dataset.shape, text: g.tile.dataset.text, group, after: null, into: null, before: target.before ?? null, edit: false, ...(target.group ? { into: h.ops.key("g", target.group) } : {}), ...(target.from ? { from: target.from } : {}) });
      }
      const set = carried(S, g.key);
      if (set) {
        if (target.op === "join") return h.say(S, "Drop between blocks to move them together.");
        if (!h.ops.moveMany(m, set, target.group, target.before)) return h.say(S, "A group cannot go inside itself.");
        return h.commit(S, `Moved ${set.length} blocks.`);
      }
      S.picked?.clear();
      if (target.op === "join") {
        const from = g.key.slice(2);
        const edge = h.ops.join(m, from, target.key.slice(2));
        if (!edge) return h.say(S, `${h.name(S, g.key)} is already connected to ${h.name(S, target.key)}.`);
        return h.commit(S, `Connected ${h.name(S, g.key)} to ${h.name(S, target.key)}.`);
      }
      if (target.op !== "into" && diagramModel.outline.drop(m, g.key, target)) return h.commit(S, `Moved ${h.name(S, g.key)}.`);
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
        g.dragEls = g.tile ? [] : (carried(g.S, g.key) || [g.key]).map((k) => h.blockEl(g.S, k));
        g.dragEls.forEach((b) => b?.classList.add("dgm-lifted"));
        if (g.card.classList.contains("dgm-box")) g.card.classList.add("dgm-lifted");
      },
      update(g) {
        g.target = dropAt(g);
        dropMark(g, g.target);
      },
      drop(g) {
        dropMark(g, null);
        g.dragEls?.forEach((b) => b?.classList.remove("dgm-lifted"));
        g.card.classList.remove("dgm-lifted");
        if (g.target) dropApply(g, g.target);
      },
      cancel(g) {
        dropMark(g, null);
        g.dragEls?.forEach((b) => b?.classList.remove("dgm-lifted"));
        g.card.classList.remove("dgm-lifted");
      },
    };
    return mode;
  }

  diagramModel.pointer = { make, dropMark };
})();
