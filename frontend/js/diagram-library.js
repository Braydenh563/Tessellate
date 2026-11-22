// diagram-library.js: the Add library of a block pane (INBOX 1594). A plain lazy file, fetched by diagram-builder.js's
// `show` with the drag code, so the flowchart's tiles and the other kinds' are drawn by one piece of code.
//
// The strip was a row of bare shapes. It is a labelled "Add" library: the tiles grouped by what they mean, each with a
// one-line hint. The hint of the tile under the pointer or focus shows in a line under the strip, it is part of the tile's
// name for a screen reader, and the phone's Add sheet (diagram-touch.js) lists the same groups with the hint on every row.
//
// A tile is `{ group, name, hint, glyph, label, data, press, keys? }`. `flow` is the flowchart's own list; the other kinds
// give theirs to `build` from diagram-kinds.js. One closure, one export: `diagramModel.library`.
(() => {
  const IDLE = "Press a shape to add it, or drag it into the blocks or onto the picture.";
  //: A phone or touch screen has no shelf to drag from (diagram-lazy.css hides it): the words say tap and Add, not drag.
  const compact = () => matchMedia("(max-width: 599.98px), (pointer: coarse)").matches;
  const idleLine = () => (compact() ? "Tap a shape to add it." : IDLE);

  //: The flowchart's tiles by meaning: [group, [[shape, hint], ...]]. A note is a rounded block that says "Note".
  const FLOW = [
    ["Steps", [["rect", "A step or an action."], ["round", "A softer step, for a state or a result."], ["hexagon", "A set-up or preparation step."], ["cylinder", "Stored data, like a database."], ["parallelogram", "Something coming in or going out."]]],
    ["Decisions", [["diamond", "A question that leads to a yes or a no."]]],
    ["Start and end", [["stadium", "Where a flow starts or stops."], ["circle", "Something that happens, like a message arriving."]]],
    ["Notes and groups", [["note", "A remark; connect it to what it is about."], ["group", "A frame round blocks that belong together."]]],
  ];

  function make(tag, cls, text) {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text != null) node.textContent = text;
    return node;
  }

  //: `h` is the builder's: `glyph(shape)`, `groupGlyph()`, `label` (a shape's name) and `add(options)`.
  function flow(h) {
    return FLOW.flatMap(([group, list]) =>
      list.map(([shape, hint]) => {
        const note = shape === "note";
        const isGroup = shape === "group";
        const name = note ? "Note" : isGroup ? "Group" : h.label[shape];
        return {
          group, name, hint,
          glyph: isGroup ? h.groupGlyph() : h.glyph(note ? "round" : shape),
          label: `Add a ${name.toLowerCase()}. ${hint}`,
          data: { shape: note ? "round" : shape, title: name, ...(note ? { text: "Note" } : {}) },
          press: () => h.add(isGroup ? { group: true } : note ? { shape: "round", text: "Note" } : { shape }),
        };
      })
    );
  }

  //: One tile: a button that is pressed to add and grabbed (`data-obj-grip`) to drag, so the strip and the shelf share it.
  function tileOf(t) {
    const tile = make("button", "dgm-tile");
    tile.type = "button";
    tile.dataset.objGrip = "";
    Object.assign(tile.dataset, t.data, { hint: t.hint });
    tile.title = compact() ? `${t.name}. ${t.hint} Tap to add it.` : `${t.name}. ${t.hint} Press to add it, or drag it into the blocks or onto the picture.`;
    tile.setAttribute("aria-label", t.label);
    if (t.keys) tile.setAttribute("aria-keyshortcuts", t.keys);
    //: A clone: a spec is drawn twice (the Add library and the shelf) and a node sits in one place only. The second tile took the first's glyph, so the phone's Add sheet printed the name where the glyph should be (blind test 1108).
    tile.append(t.glyph.cloneNode(true), make("span", "dgm-tile-name", t.name));
    tile.addEventListener("click", t.press);
    return tile;
  }

  function build(tiles, idle = idleLine()) {
    const strip = make("div", "dock-group dgm-palette dgm-library");
    strip.setAttribute("role", "group");
    strip.setAttribute("aria-label", "Add to the diagram");
    const hint = make("p", "dgm-lib-hint muted", idle);
    //: The same words are in every tile's name, so the line is for sighted eyes only.
    hint.setAttribute("aria-hidden", "true");
    const groups = new Map();
    for (const t of tiles) groups.set(t.group, [...(groups.get(t.group) || []), t]);
    strip.append(make("span", "dgm-lib-title", "Add"));
    for (const [name, list] of groups) {
      const box = make("div", "dgm-lib-group");
      box.setAttribute("role", "group");
      box.setAttribute("aria-label", name);
      const row = make("div", "dgm-lib-tiles");
      for (const t of list) row.append(tileOf(t));
      box.append(make("span", "dgm-lib-head", name), row);
      strip.append(box);
    }
    const say = (event) => {
      hint.textContent = event.target.closest?.(".dgm-tile")?.dataset.hint || idle;
    };
    strip.addEventListener("pointerover", say);
    strip.addEventListener("focusin", say);
    strip.addEventListener("pointerleave", () => (hint.textContent = idle));
    strip.addEventListener("focusout", () => (hint.textContent = idle));
    //: The line goes last in the dock, on a row of its own (the caller appends it).
    strip.hint = hint;
    return strip;
  }

  //: The shelf (INBOX 1661 l): six tiles of the kind on the picture's top left, and a caret for the rest as the grouped Add menu.
  //: A flowchart's are picked by name, the other kinds' by tile id (a mind map has two, a timeline three).
  const SIX = {
    flowchart: ["Box", "Rounded", "Decision", "Pill", "Note", "Group"],
    sequence: ["participant", "message", "reply", "note", "loop", "alt"],
    mindmap: ["branch", "leaf"],
    timeline: ["section", "period", "event"],
    gantt: ["section", "task", "milestone"],
    pie: ["slice"],
    state: ["state", "group", "transition"],
    class: ["class", "member", "relation"],
    er: ["entity", "attribute", "relationship"],
  };

  const SHELF = "diagram.shelf";

  function shelf(S, h) {
    const stage = S?.fig?.parentElement;
    const kind = S?.k ? S.k.name : "flowchart";
    if (!stage?.classList.contains("dgm-stage") || stage.querySelector(".dgm-shelf") || !SIX[kind]) return;
    const specs = S.k ? S.specs : flow({ ...h, add: (options) => h.add(S, options) });
    if (!specs) return;
    const bar = make("div", "dock dgm-shelf");
    bar.setAttribute("role", "group");
    bar.setAttribute("aria-label", "Add to the picture");
    //: The shelf folds to one button (the owner 2026-11-09: it covered the drawing and could not be put away), the choice kept
    //: in prefs; open or folded, the picture starts below it (`dgm-shelved`, always on), so neither lies over the drawing (a folded
    //: button covered a box at 1440, dgmseq-1109).
    const fold = make("button", "ghost small icon-only dgm-shelf-toggle");
    fold.type = "button";
    fold.append(make("i", "ph"));
    fold.firstChild.setAttribute("aria-hidden", "true");
    stage.classList.add("dgm-shelved");
    const paint = () => {
      const off = prefs.get(SHELF, "") === "off";
      bar.classList.toggle("dgm-shelf-off", off);
      fold.setAttribute("aria-expanded", String(!off));
      fold.firstChild.className = `ph ph-${off ? "plus" : "caret-left"}`;
      const say = off ? "Open the add shelf" : "Fold the add shelf";
      fold.title = say;
      fold.setAttribute("aria-label", say);
    };
    fold.addEventListener("click", () => {
      prefs.set(SHELF, prefs.get(SHELF, "") === "off" ? "" : "off");
      paint();
    });
    bar.append(fold);
    for (const id of SIX[kind]) {
      const t = specs.find((x) => (x.data.tile || x.name) === id);
      if (t) bar.append(tileOf(t));
    }
    const more = make("button", "ghost small icon-only dgm-shelf-more");
    more.type = "button";
    more.title = "Every block you can add";
    more.setAttribute("aria-label", "Every block you can add");
    more.setAttribute("aria-haspopup", "menu");
    more.append(make("i", "ph ph-caret-down"));
    more.firstChild.setAttribute("aria-hidden", "true");
    more.setAttribute("aria-expanded", "false");
    more.addEventListener("click", () => {
      //: A second press closes the menu (the owner 2026-11-09), as the Add caret does (diagram-bar.js): while it is open the caret says `aria-expanded`, so the outside-press closer leaves the press to this click.
      if (more.getAttribute("aria-expanded") === "true") {
        closeActionMenus();
        return;
      }
      const r = more.getBoundingClientRect();
      //: Each row wears its tile's glyph through the item's own `lead` (the menu has no icon field for a drawn shape), so a menu that regroups or reorders its rows cannot put a glyph on another row.
      //: Found by the shape's id, not by the row's place.
      const glyphOf = new Map(specs.map((t) => [t.data.tile || t.name, t.glyph]));
      const lead = (t) => () => {
        const id = t.data.tile || t.name;
        const slot = make("span", "dgm-menu-glyph");
        slot.dataset.tile = id;
        slot.append(glyphOf.get(id).cloneNode(true));
        return slot;
      };
      const menu = openMenuAtPoint(specs.map((t) => ({ label: t.name, group: t.group, title: t.hint, run: t.press, lead: lead(t) })), "Add to the diagram", r.right, r.bottom, more);
      if (menu) {
        menu._escapedOpener = more;
        more.setAttribute("aria-expanded", "true");
      }
    });
    bar.append(more);
    //: First in the stage, so Tab meets it before the picture as the eye does (it sat after the zoom bar, tab stop 18 of 26), and one stop with Left and Right between the tiles (the toolbar's own roving).
    stage.prepend(bar);
    wireToolbarRoving(bar);
    paint();
  }

  //: `anchor` (INBOX 1771; here, not in sheets-selects.js, as only these menus pass one): the menu keeps off a whole row, not a point. Below, else above, the first that fits the window; neither, the larger of the two, scrolling.
  kebabMenu.beside = (menu, row, opener) => {
    const [margin, gap] = [8, 4];
    escapeMenuToBody(menu, opener);
    menu.style.visibility = "hidden";
    menu.style.maxHeight = "";
    menu.style.left = menu.style.top = "0px";
    const box = menu.getBoundingClientRect();
    const [down, up] = [innerHeight - margin - row.bottom - gap, row.top - gap - margin];
    const below = box.height <= down || (box.height > up && down >= up);
    menu.style.maxHeight = `${Math.max(120, Math.floor(below ? down : up))}px`;
    const left = Math.max(margin, Math.min(row.right - box.width, innerWidth - margin - box.width));
    const top = below ? row.bottom + gap : Math.max(margin, row.top - gap - menu.getBoundingClientRect().height);
    menu.style.left = `${Math.round(left)}px`;
    menu.style.top = `${Math.round(top)}px`;
    menu.style.visibility = "";
    menu.querySelector(".menu-item")?.focus({ preventScroll: true });
  };

  //: A row's ⋯ before it is pressed: an empty `kebabMenu` (1108 P2). The press is caught on the way down, and the
  //: real menu, with its rows and the shape submenu, is built then and swapped in; 41 blocks no longer carry 41
  //: full menus nobody opened. `items` is called on that press (it may be async, a connector's rows come from a lazy file; null opens
  //: nothing), and `opts` are `kebabMenu`'s (a connector's `anchor` is its whole row).
  function lazyKebab(items, label, opts) {
    const stub = kebabMenu([], label, opts);
    stub.classList.add("dgm-menu");
    let busy = false;
    const swap = (rows) => {
      busy = false;
      if (!rows) return;
      const real = kebabMenu(rows, label, opts);
      real.classList.add("dgm-menu");
      const [old, again] = [stub, real].map((wrap) => wrap.querySelector(".kebab-opener"));
      const tab = old.getAttribute("tabindex");
      if (tab != null) again.setAttribute("tabindex", tab);
      const focused = document.activeElement === old;
      stub.replaceWith(real);
      if (focused) again.focus({ preventScroll: true });
      again.click();
    };
    stub.addEventListener("click", (event) => {
      event.stopPropagation();
      if (busy) return;
      const rows = items();
      busy = Boolean(rows?.then);
      if (busy) rows.then(swap);
      else swap(rows);
    }, true);
    return stub;
  }

  //: Undo and Redo are dimmed while there is nothing to go back or forward to (dgpolish-1109: both always looked live). An `io` that
  //: does not say (`canUndo` unset) keeps them live.
  function hist(S) {
    const [undo, redo] = S.root?.querySelectorAll(".dgm-hist") || [];
    if (!undo) return;
    const held = document.activeElement;
    undo.disabled = S.io?.canUndo === false;
    redo.disabled = S.io?.canRedo === false;
    //: A button that dims under the finger takes the focus with it, so the other one (or the picture) keeps it.
    if ((held === undo && undo.disabled) || (held === redo && redo.disabled)) (held === undo && !redo.disabled ? redo : S.fig)?.focus?.({ preventScroll: true });
  }

  diagramModel.library = { build, flow, shelf, lazyKebab, hist };
})();
