// diagram-bar.js: the flowchart pane's toolbar (INBOX 1661 D2). Lazy: `LAZY_MODULES.diagramBar`, fetched by
// diagram-builder.js's `show` before the pane is mounted. ONE row at every width: Add (the last-used shape is the
// button, a caret lists every shape with its key), Direction (one button that turns the diagram), Suggest, Undo, Redo
// and the ... menu. The eight Add tiles and the four direction buttons that wrapped it to two to four rows are gone.
//
// `diagramModel.keys` is the one table of shape keys: the Add menu's hints and the pane's key handler both read it.
(() => {
  const LAST = "diagram.lastShape";
  //: key -> what it adds. N (a Box) and G (a group) were there before; 1 to 9 are the Add menu's order.
  const KEYS = { 1: "rect", 2: "round", 3: "stadium", 4: "circle", 5: "diamond", 6: "hexagon", 7: "note", 8: "cylinder", 9: "parallelogram", n: "rect", g: "group" };
  const ORDER = ["rect", "round", "stadium", "circle", "diamond", "hexagon", "note", "cylinder", "parallelogram", "group"];
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

  //: Refreshes what depends on the model: the Direction button's arrow and word.
  function sync(S) {
    diagramModel.library.hist(S);
    const [dir, arrow, name] = S.bar.dirs.find(([d]) => d === S.m?.dir) || S.bar.dirs[0];
    const icon = document.createElement("i");
    icon.className = `ph ${arrow.replace(":", "-")}`;
    icon.setAttribute("aria-hidden", "true");
    const word = document.createElement("span");
    word.className = "dgm-dirword";
    word.textContent = WORD[dir];
    S.dirs.dataset.dir = dir;
    S.dirs.replaceChildren(icon, word);
    S.dirs.setAttribute("aria-label", `Direction: ${WORD[dir]}. Choose a direction.`);
    S.dirs.title = `${name}. Choose a direction, or Shift to turn it back one step.`;
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
    const caret = h.smallButton("ph:caret-down", "Choose a shape to add (1 to 9, or ? for every key)", () => {
      //: A pointer menu lines its right edge up with the point, so the point is the caret's right edge (it opened at the window's left edge from the split's left).
      //: A second press closes it (the owner 2026-11-09), as a chip's menu does (chip-menus.js `openChipMenu`): while open the caret says `aria-expanded`, so the outside-press closer leaves it to this click.
      if (caret.getAttribute("aria-expanded") === "true") {
        closeActionMenus();
        return;
      }
      const r = caret.getBoundingClientRect();
      const rows = ORDER.map((shape) => ({ label: nameOf(shape, h), keys: hintOf(shape), title: hints.get(nameOf(shape, h)) || "", run: () => add(shape) }));
      const menu = openMenuAtPoint(rows, "Add to the diagram", r.right, r.bottom, caret);
      if (menu) {
        menu._escapedOpener = caret;
        caret.setAttribute("aria-expanded", "true");
      }
    });
    caret.setAttribute("aria-expanded", "false");
    caret.classList.add("dgm-addcaret");
    caret.setAttribute("aria-haspopup", "menu");
    paint();
    split.append(main, caret);

    //: Direction: a press opens the four with their arrows; Shift turns it back one step, as the single button did.
    S.turn = (dir) => {
      S.m.dir = dir;
      h.commit(S, `${DIRS.find(([d]) => d === dir)[2]}.`);
    };
    S.dirs = el("button", "ghost small dgm-dirs");
    S.dirs.type = "button";
    S.dirs.setAttribute("aria-haspopup", "menu");
    S.dirs.addEventListener("click", (event) => {
      const at = DIRS.findIndex(([d]) => d === S.m.dir);
      if (event.shiftKey) return S.turn(DIRS[(at + DIRS.length - 1) % DIRS.length][0]);
      const r = S.dirs.getBoundingClientRect();
      openMenuAtPoint(DIRS.map(([d, icon, name]) => ({ label: `${icon} ${name}`, run: () => S.turn(d) })), "Direction", r.right, r.bottom, S.dirs);
    });

    const suggest = h.smallButton("ph:sparkle Suggest", "Start from a template, your notes or a description", () => h.suggestMenu(S, suggest));
    suggest.classList.add("dgm-suggest");
    suggest.setAttribute("aria-haspopup", "menu");
    S.suggestBtn = suggest;
    const hist = [["ph:arrow-counter-clockwise", "Undo", "Undo, Ctrl+Z", () => S.io.undo()], ["ph:arrow-clockwise", "Redo", "Redo, Ctrl+Y", () => S.io.redo()]].map(([icon, label, tip, run]) => {
      const b = h.smallButton(icon, tip, run);
      b.setAttribute("aria-label", label);
      b.classList.add("dgm-hist");
      if (label === "Redo") b.classList.add("dgm-redo");
      return b;
    });
    const actions = el("div", "dock-actions");
    actions.append(suggest, ...hist, ...[diagramModel.kindbar?.expand(S)].filter(Boolean), h.more(S));
    bar.append(split, S.dirs, actions);
    diagramModel.kindbar?.mount(S, h, bar);
    sync(S);
    //: One Tab stop for the whole toolbar, Left and Right between its buttons (documents.js; 17 stops to the first block before).
    wireToolbarRoving(bar);
    return bar;
  }

  //: The keys that add a shape (1 to 9) and Shift+N (the last one used). Returns true when it took the key.
  function key(event) {
    if (event.altKey || event.ctrlKey || event.metaKey) return null;
    const shape = event.shiftKey ? (event.key === "N" ? last() : null) : /^[1-9]$/.test(event.key) ? KEYS[event.key] : null;
    if (!shape) return null;
    prefs.set(LAST, shape);
    return optionsOf(shape);
  }

  //: The same keys from the picture, the toolbar or the outline's edge (the block handler only hears a focused block):
  //: 1 to 9, N, Shift+N, G add after the selected block, K colours, ? opens the sheet. Typing in a field is left alone.
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

  //: **Tab chains** (DD-3, 1107; Whimsical's way), and only where they cannot trap: Tab on the LAST box adds a box joined to it and
  //: opens its name; Shift+Tab on a box with a parent selects the parent. Any other Tab (and Shift+Tab on a root) is left to the
  //: browser, so the blocks can be walked out of (review 1107: Tab on every box added boxes without end). Returns true when it
  //: took the key.
  function chain(event, S, key, block, add) {
    if (event.altKey) return false;
    //: F6 leaves the blocks for the picture (Shift+F6 for the toolbar).
    if (event.key === "F6") {
      event.preventDefault();
      (event.shiftKey ? S.root.querySelector(".dgm-dock button") : S.fig)?.focus();
      return true;
    }
    if (event.key !== "Tab" || key[0] !== "n") return false;
    const ops = diagramModel.ops;
    const id = ops.split(key)[1];
    if (event.shiftKey) {
      const from = S.m.edges.find((e) => e.to === id)?.from;
      const up = (from && S.tree.querySelector(`.dgm-block[data-key="${ops.key("n", from)}"]`)) || block.parentElement.closest(".dgm-block");
      if (!up) return false;
      event.preventDefault();
      diagramModel.builder.select(S, up.dataset.key, true);
      return true;
    }
    if (block !== [...S.tree.querySelectorAll(".dgm-block")].at(-1)) return false;
    event.preventDefault();
    add(S, { after: key, from: id });
    return true;
  }

  diagramModel.bar = { build, sync, key, last, rootKey, chain };
})();
