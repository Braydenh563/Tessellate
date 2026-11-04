// diagram-bar.js: the flowchart pane's toolbar (INBOX 1661 D2). Lazy: `LAZY_MODULES.diagramBar`, fetched by
// diagram-builder.js's `show` before the pane is mounted. ONE row at every width: Add (the last-used shape is the
// button, a caret lists every shape with its key), Direction (one button that turns the diagram), Suggest, Undo, Redo
// and the ... menu. The eight Add tiles and the four direction buttons that wrapped it to two to four rows are gone.
//
// `diagramModel.keys` is the one table of shape keys: the Add menu's hints and the pane's key handler both read it.
(() => {
  const LAST = "diagram.lastShape";
  //: key -> what it adds. N (a Box) and G (a group) were there before; 1 to 7 are the Add menu's order.
  const KEYS = { 1: "rect", 2: "round", 3: "stadium", 4: "circle", 5: "diamond", 6: "hexagon", 7: "note", n: "rect", g: "group" };
  const ORDER = ["rect", "round", "stadium", "circle", "diamond", "hexagon", "note", "group"];
  //: A short word for the Direction button; the full names stay on its tooltip and the live line.
  const WORD = { TD: "Down", LR: "Right", BT: "Up", RL: "Left" };
  diagramModel.keys = KEYS;

  //: A Box answers to N as well as 1, so both show.
  const hintOf = (shape) => (shape === "group" ? "G" : shape === "rect" ? "N or 1" : Object.keys(KEYS).find((k) => /\d/.test(k) && KEYS[k] === shape));
  const last = () => {
    const saved = prefs.get(LAST, "rect");
    return ORDER.includes(saved) ? saved : "rect";
  };
  const optionsOf = (shape) => (shape === "group" ? { group: true } : shape === "note" ? { shape: "round", text: "Note" } : { shape });
  const nameOf = (shape, h) => (shape === "group" ? "Group" : shape === "note" ? "Note" : h.label[shape]);

  const OUTLINE = "diagram.outline";
  function paintOutline(S, button) {
    const on = prefs.get(OUTLINE) !== "0";
    S.root.classList.toggle("dgm-no-outline", !on);
    button.setAttribute("aria-pressed", String(on));
  }

  //: Refreshes what depends on the model: the Direction button's arrow and word.
  function sync(S) {
    const [dir, arrow, name] = S.bar.dirs.find(([d]) => d === S.m?.dir) || S.bar.dirs[0];
    const icon = document.createElement("i");
    icon.className = `ph ${arrow.replace(":", "-")}`;
    icon.setAttribute("aria-hidden", "true");
    const word = document.createElement("span");
    word.className = "dgm-dirword";
    word.textContent = WORD[dir];
    S.dirs.dataset.dir = dir;
    S.dirs.replaceChildren(icon, word);
    S.dirs.setAttribute("aria-label", `Direction: ${WORD[dir]}. Press to turn it.`);
    S.dirs.title = `${name}. Press to turn it, Shift to turn it back.`;
  }

  function build(S, h) {
    const { el, DIRS } = h;
    const bar = el("div", "dock dgm-dock");
    bar.dataset.dockName = "diagram";
    bar.setAttribute("role", "toolbar");
    bar.setAttribute("aria-label", "Diagram blocks");
    S.bar = { dirs: DIRS };
    const hints = new Map(diagramModel.library.flow(h).map((t) => [t.name, t.hint]));

    //: Add: the main half repeats the last shape, the caret lists them all.
    const split = el("span", "dgm-addsplit");
    const main = el("button", "ghost small dgm-addmain");
    main.type = "button";
    const paint = () => {
      const shape = last();
      const name = nameOf(shape, h);
      main.replaceChildren(shape === "group" ? h.groupGlyph() : h.glyph(shape === "note" ? "round" : shape), el("span", "dgm-addname", `Add ${name.toLowerCase()}`));
      main.title = `Add a ${name.toLowerCase()} (${hintOf(shape)})`;
    };
    const add = (shape) => {
      prefs.set(LAST, shape);
      paint();
      h.add(S, optionsOf(shape));
    };
    main.addEventListener("click", () => add(last()));
    const caret = h.smallButton("ph:caret-down", "Choose a shape to add", () => {
      //: A pointer menu lines its right edge up with the point, so the point is the caret's right edge (it opened at the window's left edge from the split's left).
      const r = caret.getBoundingClientRect();
      const rows = ORDER.map((shape) => ({ label: nameOf(shape, h), keys: hintOf(shape), title: hints.get(nameOf(shape, h)) || "", run: () => add(shape) }));
      openMenuAtPoint(rows, "Add to the diagram", r.right, r.bottom, caret);
    });
    caret.classList.add("dgm-addcaret");
    caret.setAttribute("aria-haspopup", "menu");
    paint();
    split.append(main, caret);

    //: Direction: one button that turns the diagram Down, Right, Up, Left; Shift turns it back.
    S.dirs = el("button", "ghost small dgm-dirs");
    S.dirs.type = "button";
    S.dirs.addEventListener("click", (event) => {
      const at = DIRS.findIndex(([d]) => d === S.m.dir);
      const to = DIRS[(at + (event.shiftKey ? DIRS.length - 1 : 1)) % DIRS.length];
      S.m.dir = to[0];
      h.commit(S, `${to[2]}.`);
    });

    const suggest = h.smallButton("ph:sparkle Suggest", "Start from a template, your notes or a description", () => h.suggestMenu(S, suggest));
    suggest.classList.add("dgm-suggest");
    suggest.setAttribute("aria-haspopup", "menu");
    S.suggestBtn = suggest;
    const hist = [["ph:arrow-counter-clockwise", "Undo", "Undo, Ctrl+Z", () => S.io.undo()], ["ph:arrow-clockwise", "Redo", "Redo, Ctrl+Y", () => S.io.redo()]].map(([icon, label, tip, run]) => {
      const b = h.smallButton(icon, tip, run);
      b.setAttribute("aria-label", label);
      b.classList.add("dgm-hist");
      return b;
    });
    //: The outline (the blocks list) can be hidden, leaving the picture and the toolbar; the choice is kept.
    const outline = h.smallButton("ph:sidebar-simple", "Show or hide the list of blocks", () => {
      prefs.set(OUTLINE, prefs.get(OUTLINE) === "0" ? "1" : "0");
      paintOutline(S, outline);
    });
    outline.setAttribute("aria-label", "Blocks list");
    outline.classList.add("dgm-outline-toggle");
    paintOutline(S, outline);
    const actions = el("div", "dock-actions");
    actions.append(suggest, ...hist, outline, h.more(S));
    bar.append(split, S.dirs, actions);
    sync(S);
    //: One Tab stop for the whole toolbar, Left and Right between its buttons (documents.js; 17 stops to the first block before).
    wireToolbarRoving(bar);
    return bar;
  }

  //: The keys that add a shape (1 to 7) and Shift+N (the last one used). Returns true when it took the key.
  function key(event) {
    if (event.altKey || event.ctrlKey || event.metaKey) return null;
    const shape = event.shiftKey ? (event.key === "N" ? last() : null) : /^[1-7]$/.test(event.key) ? KEYS[event.key] : null;
    if (!shape) return null;
    prefs.set(LAST, shape);
    return optionsOf(shape);
  }

  //: The same keys from the picture, the toolbar or the outline's edge (the block handler only hears a focused block):
  //: 1 to 7, N, Shift+N, G add after the selected block, K colours, ? opens the sheet. Typing in a field is left alone.
  function rootKey(S, event, h) {
    const t = event.target;
    if (event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey || t.isContentEditable || t.closest?.(".dgm-tree, .menu-wrap, input, textarea, select")) return;
    const low = event.key.toLowerCase();
    const picked = key(event) || (low === "n" && !event.shiftKey ? { shape: "rect" } : low === "g" ? { group: true } : null);
    const run = picked ? () => h.add(S, { after: S.sel, ...picked }) : low === "k" ? () => h.style(S, "colour", S.sel) : event.key === "?" ? () => h.style(S, "shortcuts") : null;
    if (!run) return;
    event.preventDefault();
    run();
  }

  diagramModel.bar = { build, sync, key, last, rootKey };
})();
