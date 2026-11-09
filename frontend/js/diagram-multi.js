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
    //: Icon-only ghost buttons (1708), each named by its aria-label and its tooltip; the words are in the title.
    const tool = (icon, name, title, run) => {
      const button = smallButton(`ph:${icon}`, title, run);
      button.setAttribute("aria-label", name);
      return button;
    };
    const shapeBtn = tool("diamond", "Shape", "Give every selected box one shape", () => {
      const r = shapeBtn.getBoundingClientRect();
      openMenuAtPoint(ops.SHAPES.map((shape) => ({ label: ops.LABEL[shape], run: () => shapeAll(shape) })), "Shape of the selected blocks", r.left, r.bottom, shapeBtn);
    });
    shapeBtn.setAttribute("aria-haspopup", "menu");
    //: Colour (K) is the lazy style sheet over the picked boxes; Connect joins the first picked to the second (1679 slice 10).
    const colourBtn = tool("palette", "Colour", "Colour the selected boxes (K)", async () => (await ensureModule("diagramStyle")) ? diagramModel.style.colour(S, h) : say("That did not load."));
    const connectBtn = tool("arrow-bend-down-right", "Connect", "Draw an arrow from the first selected block to the second", () => connectTwo());
    //: The head line: the count, then Select all and Clear as text buttons (Undo and Done are the toolbar's and Clear's).
    const selectAll = smallButton("Select all", "Pick every block (Ctrl+A on the picture)", () => pickAll());
    const clearBtn = smallButton("Clear", "Drop the pick", () => show([], S.sel));
    end.append(selectAll, clearBtn);
    const head = h.el("div", "dgm-selecthead");
    head.append(count, end);
    const tools = h.el("div", "dgm-selecttools");
    tools.append(
      tool("copy", "Duplicate", "Copy the selected blocks, keeping the connectors between them", () => copyAll()),
      shapeBtn,
      colourBtn,
      connectBtn,
      tool("stack", "Box them", "Draw a labelled box around the selected blocks (a group)", () => wrapAll()),
      Object.assign(tool("trash", "Delete", "Delete the selected blocks", () => removeAll()), { className: "ghost small icon-only danger" })
    );
    bar.append(head, tools);
    S.pane.prepend(bar);

    // --- the pick -----------------------------------------------------------------
    function refresh() {
      if (S.picked.size < 2) S.picked.clear();
      bar.classList.toggle("hidden", !S.picked.size);
      count.textContent = `${S.picked.size} selected`;
      selectAll.disabled = S.picked.size >= keys().length;
      //: The List head's own Select all (diagram-split.js) shows only while nothing is picked; the bar has its own.
      S.pane.querySelector(".dgm-head-all")?.classList.toggle("hidden", S.picked.size > 0);
    }
    const pickAll = () => keys().length && show(keys(), S.sel || keys()[0]);
    S.pickAll = pickAll;
    //: Makes `list` the pick (fewer than two is no pick) with `primary` as `S.sel`.
    function show(list, primary) {
      S.picked.clear();
      if (list.length > 1) list.forEach((k) => S.picked.add(k));
      S.sel = primary;
      S.fresh = null; //: a pick made by hand, so Branch nests under it (diagram-kinds.js addTile)
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
      const gone = base().filter((k) => k[0] !== "k" && ops.remove(S.m, k)).length;
      S.picked.clear();
      S.sel = null;
      if (gone) h.commit(S, `Deleted ${gone} blocks.`);
    }
    function copyAll() {
      const list = base().filter((k) => k[0] !== "k");
      if (!list.length) return say("Pick a block to duplicate.");
      const made = ops.duplicate(S.m, list);
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
      if (n) h.commit(S, `${n} blocks are now ${ops.LABEL[shape].toLowerCase()}.`);
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
    diagramModel.quick.wire(S, h, { show, keys, base, copyAll, removeAll });
  }

  diagramModel.multi = { wire };
})();

// Quick ways to build (INBOX 1661 j), in the same lazy file because they act on the pick: Ctrl+D copies it, Ctrl+A picks every
// block from the picture, Delete removes it from the picture, Shift+Enter adds a joined box after it and Alt+Enter a
// sister joined to the same parent, a double press on empty picture adds a box, and Find (Ctrl+F or /) rings the boxes
// whose words match. Tab chains stay as diagram-bar.js has them (no trap).
(() => {
  const typing = (t) => t.isContentEditable || t.closest?.("input, textarea, select, .menu-wrap");

  function wire(S, h, { show, keys, base, copyAll, removeAll }) {
    const { ops } = h;
    const say = (text) => h.say(S, text);
    const img = () => S.fig.querySelector(".md-mermaid-img");
    const nodeKey = () => (S.sel && S.sel[0] === "n" ? ops.split(S.sel)[1] : null);

    // --- find ---------------------------------------------------------------------
    const bar = h.el("div", "dock dgm-find hidden");
    bar.setAttribute("role", "search");
    const field = h.el("input", "search-field");
    field.type = "search";
    field.placeholder = "Find a block";
    field.setAttribute("aria-label", "Find a block");
    const count = h.el("span", "muted dgm-find-count");
    count.setAttribute("aria-hidden", "true");
    const shut = smallButton("ph:x", "Close find, Escape", () => close());
    shut.setAttribute("aria-label", "Close find");
    bar.append(field, count, shut);
    (S.fig.parentElement || S.fig).append(bar);
    let hits = [];
    let at = -1;
    const ring = () => {
      const ids = new Set(hits.map((k) => ops.split(k)[1]));
      for (const box of S.fig.querySelectorAll(".dgm-overlay .dgm-box")) box.classList.toggle("found", ids.has(box.dataset.node || box.dataset.group));
    };
    (S.fig.onpaint ||= []).push(ring);
    const scan = () => {
      const needle = field.value.trim().toLowerCase();
      hits = needle ? keys().filter((k) => (ops.node(S.m, ops.split(k)[1])?.text ?? ops.group(S.m, ops.split(k)[1])?.title ?? "").toLowerCase().includes(needle)) : [];
      at = -1;
      count.textContent = needle ? `${hits.length} found` : "";
      ring();
      if (needle) say(hits.length ? `${hits.length} ${hits.length === 1 ? "block matches" : "blocks match"}.` : "No block matches.");
    };
    function go(step) {
      if (!hits.length) return;
      at = (at + step + hits.length) % hits.length;
      count.textContent = `${at + 1} of ${hits.length}`;
      S.sel = hits[at];
      h.select(S, hits[at], false);
      S.fig.querySelector(`.dgm-overlay .dgm-box[data-node="${ops.split(hits[at])[1]}"]`)?.scrollIntoView({ block: "center", inline: "center", behavior: "auto" });
      say(`${h.name(S, hits[at])}, ${at + 1} of ${hits.length}.`);
    }
    function open() {
      bar.classList.remove("hidden");
      field.focus();
      field.select();
      scan();
    }
    function close() {
      bar.classList.add("hidden");
      hits = [];
      ring();
      (S.sel ? h.blockEl(S, S.sel) : null)?.focus?.() || S.fig.focus();
    }
    field.addEventListener("input", scan);
    field.addEventListener("keydown", (event) => {
      if (event.key === "Enter") (event.preventDefault(), go(event.shiftKey ? -1 : 1));
      else if (event.key === "Escape") (event.preventDefault(), event.stopPropagation(), close());
    });

    // --- build ----------------------------------------------------------------------
    const child = () => h.add(S, nodeKey() ? { after: S.sel, from: nodeKey() } : { after: S.sel });
    const sister = () => {
      const id = nodeKey();
      const parent = id && S.m.edges.find((e) => e.to === id)?.from;
      return h.add(S, parent ? { after: S.sel, from: parent } : { after: S.sel });
    };
    S.root.addEventListener("keydown", (event) => {
      if (event.defaultPrevented || typing(event.target)) return;
      const mod = event.ctrlKey || event.metaKey;
      const low = event.key.toLowerCase();
      const inTree = S.tree.contains(event.target);
      let run = null;
      if (mod && !event.shiftKey && !event.altKey && low === "d") run = copyAll;
      else if (mod && !event.shiftKey && !event.altKey && low === "f") run = open;
      else if (mod && !event.altKey && low === "a" && event.target === S.fig && keys().length) run = S.pickAll;
      else if (!mod && !event.altKey && event.key === "/") run = open;
      else if (!mod && event.key === "Enter" && event.shiftKey && !event.altKey && (inTree || event.target === S.fig)) run = child;
      else if (!mod && event.key === "Enter" && event.altKey && !event.shiftKey && (inTree || event.target === S.fig)) run = sister;
      else if (!mod && !event.altKey && /^(Delete|Backspace)$/.test(event.key) && event.target === S.fig && base().length) run = removeAll;
      if (!run) return;
      event.preventDefault();
      event.stopPropagation();
      run();
    });

    //: A double press on empty picture adds a box (a node, an arrow or a group's title strip renames, in diagram-edges.js).
    S.fig.addEventListener("dblclick", (event) => {
      const image = img();
      if (!image || !S.hit || event.target.closest(".dock, .dgm-overlay > *, .dgm-zoom")) return;
      const rect = image.getBoundingClientRect();
      const canvas = diagramModel.canvas.math;
      if (canvas.nodeAt(S.hit, rect, event.clientX, event.clientY) || canvas.groupAt(S.hit, rect, event.clientX, event.clientY) || diagramModel.edges?.math.edgeAt(S.hit, rect, event.clientX, event.clientY)) return;
      event.preventDefault();
      h.add(S, { after: null });
    });
  }

  diagramModel.quick = { wire };
})();
