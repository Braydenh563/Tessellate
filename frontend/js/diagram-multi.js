// diagram-multi.js: several blocks picked at once (INBOX 1615 a, b; DOCUMENTS_PLAN 22.4 R5). Lazy:
// `LAZY_MODULES.diagramMulti`, registered at the foot of documents-mermaid.js and asked for by diagram-builder.js's
// `show` for a flowchart. `S.sel` stays the one primary key, because the kinds' panes, the suggestions, the joins and the
// pointer read it; `S.picked` is an ordered Set of every picked key, empty unless two or more are picked, and the
// builder's own `select` empties it. The pure changes are `diagramOps.roots`, `moveMany`, `duplicate` and `wrap`
// (diagram-ops.js); the grip drag that carries the picked rows is in diagram-pointer.js.
//
// Keys: Shift+click a range, Ctrl or Cmd+click one more, Ctrl+A all, Shift+Up or Down to extend, Escape to drop the pick.
// The bar is the Library's selection bar (DESIGN.md, "A list you manage").
(() => {
  const SHAPES = { rect: "Box", round: "Rounded", stadium: "Pill", circle: "Circle", diamond: "Decision", hexagon: "Hexagon" };
  const skip = ".menu-wrap, .dgm-join, .dgm-connect, .dgm-swatch, [contenteditable]";

  function wire(S, h) {
    if (S.picked || S.k) return;
    S.picked = new Set();
    const { ops } = h;
    S.tree.setAttribute("aria-multiselectable", "true");
    const keys = () => [...S.tree.querySelectorAll(".dgm-block")].map((b) => b.dataset.key).filter((k) => k[0] !== "k");
    const say = (text) => h.say(S, text);

    // --- the bar ----------------------------------------------------------------
    const bar = h.el("div", "library-contextbar selectbar dgm-selectbar hidden");
    bar.setAttribute("role", "group");
    bar.setAttribute("aria-label", "Actions for the selected blocks");
    const count = h.el("span", "library-selected-count");
    const end = h.el("span", "library-contextbar-end");
    //: The words fold away where the bar is tight (diagram-lazy.css), so each button is named for a reader.
    const tool = (label, title, run) => {
      const button = smallButton(label, title, run);
      button.setAttribute("aria-label", label.replace(/^ph:\S+ /, ""));
      return button;
    };
    const shapeBtn = tool("ph:diamond Shape", "Give every selected box one shape", () => {
      const r = shapeBtn.getBoundingClientRect();
      openMenuAtPoint(ops.SHAPES.map((shape) => ({ label: SHAPES[shape], run: () => shapeAll(shape) })), "Shape of the selected blocks", r.left, r.bottom, shapeBtn);
    });
    shapeBtn.setAttribute("aria-haspopup", "menu");
    //: Colour (K) is the lazy style sheet over the picked boxes; Connect joins the first picked to the second (1679 slice 10).
    const colourBtn = tool("ph:palette Colour", "Colour the selected boxes (K)", async () => (await ensureModule("diagramStyle")) ? diagramModel.style.colour(S, h) : say("That did not load."));
    const connectBtn = tool("ph:arrow-bend-down-right Connect", "Draw an arrow from the first selected block to the second", () => connectTwo());
    end.append(tool("ph:arrow-counter-clockwise Undo", "Undo", () => S.io.undo()), tool("Done", "Stop selecting", () => show([], S.sel)));
    bar.append(
      count,
      tool("ph:trash Delete", "Delete the selected blocks", () => removeAll()),
      tool("ph:copy Duplicate", "Copy the selected blocks, keeping the connectors between them", () => copyAll()),
      shapeBtn,
      colourBtn,
      connectBtn,
      tool("ph:stack Box them", "Draw a labelled box around the selected blocks (a group)", () => wrapAll()),
      end
    );
    S.pane.prepend(bar);

    // --- the pick -----------------------------------------------------------------
    function refresh() {
      if (S.picked.size < 2) S.picked.clear();
      bar.classList.toggle("hidden", !S.picked.size);
      count.textContent = `${S.picked.size} selected`;
    }
    //: Makes `list` the pick (fewer than two is no pick) with `primary` as `S.sel`.
    function show(list, primary) {
      S.picked.clear();
      if (list.length > 1) list.forEach((k) => S.picked.add(k));
      S.sel = primary;
      refresh();
      h.stops(S, h.blockEl(S, primary));
      if (list.length > 1) say(`${list.length} blocks selected.`);
    }
    S.pick = show;
    //: A modified click on a drawn block (the picture, as the list does): Shift a range from the anchor, Ctrl or Cmd one more.
    S.pickAt = (key, shift) => {
      if (!shift) return toggle(key);
      S.anchor = base().includes(S.anchor) ? S.anchor : S.sel || key;
      show(range(S.anchor, key), key);
    };
    //: A render prunes the pick to the blocks that are still there.
    S.rendered = (live) => {
      for (const k of S.picked) if (!live.includes(k)) S.picked.delete(k);
      refresh();
    };
    const range = (from, to) => {
      const all = keys();
      const [a, b] = [all.indexOf(from), all.indexOf(to)];
      return a < 0 || b < 0 ? [to] : all.slice(Math.min(a, b), Math.max(a, b) + 1);
    };
    const base = () => (S.picked.size ? [...S.picked] : S.sel ? [S.sel] : []);
    function toggle(key) {
      const have = base();
      S.anchor = key;
      if (!have.includes(key)) return show([...have, key], key);
      const rest = have.filter((k) => k !== key);
      show(rest, rest.at(-1) ?? null);
    }

    // --- the actions ----------------------------------------------------------------
    function removeAll() {
      const gone = [...S.picked].filter((k) => ops.remove(S.m, k)).length;
      S.picked.clear();
      S.sel = null;
      if (gone) h.commit(S, `Deleted ${gone} blocks.`);
    }
    function copyAll() {
      const made = ops.duplicate(S.m, [...S.picked]);
      if (!made) return say(`A diagram holds at most ${ops.MAX} blocks.`);
      S.picked.clear();
      made.keys.forEach((k) => S.picked.add(k));
      S.sel = made.keys[0];
      h.commit(S, `Duplicated ${made.keys.length === 1 ? "1 block" : `${made.keys.length} blocks`}.`);
    }
    function shapeAll(shape) {
      let n = 0;
      for (const k of S.picked) {
        const node = k[0] === "n" && ops.node(S.m, k.slice(2));
        if (node) (node.shape = shape), n++;
      }
      if (n) h.commit(S, `${n} blocks are now ${SHAPES[shape].toLowerCase()}.`);
      else say("Only boxes take a shape.");
    }
    async function connectTwo() {
      const [from, to] = [...S.picked].map((k) => ops.split(k)[1]);
      const edge = ops.join(S.m, from, to);
      if (!edge) return say("Those two are already connected.");
      const title = (id) => ops.node(S.m, id)?.text ?? ops.group(S.m, id)?.title ?? id;
      h.commit(S, `Connected ${title(from)} to ${title(to)}.`);
      if (await ensureModule("diagramJoins")) diagramModel.joins.ask(S, edge, h);
    }
    function wrapAll() {
      const id = ops.wrap(S.m, [...S.picked]);
      if (!id) return say("Those blocks could not be grouped.");
      const n = S.picked.size;
      S.picked.clear();
      S.sel = ops.key("g", id);
      h.commit(S, `Grouped ${n} blocks into a box.`);
    }

    // --- the gestures ---------------------------------------------------------------
    const rowOf = (event) => {
      const row = event.target.closest?.(".dgm-block");
      return row && row.dataset.key[0] !== "k" && !event.target.closest(skip) ? row.dataset.key : null;
    };
    //: A modified press must not start a text selection.
    S.tree.addEventListener("mousedown", (event) => {
      if ((event.shiftKey || event.ctrlKey || event.metaKey) && rowOf(event)) event.preventDefault();
    }, true);
    //: In the capture phase and before the builder's own click, which would make this row the only one.
    S.tree.addEventListener("click", (event) => {
      const key = rowOf(event);
      if (!key || !(event.shiftKey || event.ctrlKey || event.metaKey)) return;
      event.stopPropagation();
      if (!event.shiftKey) return toggle(key);
      S.anchor = base().includes(S.anchor) ? S.anchor : S.sel || key;
      show(range(S.anchor, key), key);
      h.blockEl(S, key)?.focus();
    }, true);
    S.tree.addEventListener("keydown", (event) => {
      if (event.target.isContentEditable || event.target.closest(skip) || event.altKey) return;
      const mod = event.ctrlKey || event.metaKey;
      const all = keys();
      let done = true;
      if (mod && /^a$/i.test(event.key) && all.length) show(all, S.sel || all[0]);
      else if (!mod && event.shiftKey && /^Arrow(Up|Down)$/.test(event.key) && S.sel) {
        const next = all[all.indexOf(S.sel) + (event.key === "ArrowUp" ? -1 : 1)];
        S.anchor = base().includes(S.anchor) ? S.anchor : S.sel;
        if (next) (show(range(S.anchor, next), next), h.blockEl(S, next)?.focus());
      } else if (S.picked.size && !mod && event.key === "Escape") show([], S.sel);
      else if (S.picked.size && !mod && /^(Delete|Backspace)$/.test(event.key)) removeAll();
      else done = false;
      if (done) (event.preventDefault(), event.stopPropagation());
    }, true);
  }

  diagramModel.multi = { wire };
})();
