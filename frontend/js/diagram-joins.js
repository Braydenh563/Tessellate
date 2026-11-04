// diagram-joins.js: a flowchart's connectors, in the block pane (1546 P2 built them, P4 moved them out so
// diagram-builder.js, which every diagram opens, stays small). Lazy: `LAZY_MODULES.diagramJoins`,
// registered at the foot of documents-mermaid.js and fetched by the builder on the first press of a
// connector row or of Connect to. Two things: the menu a connector row opens (its line, its label, remove) and the
// picker that connects one block to another, which can also make the other block (1594). R6: the menu hangs from its row,
// each line kind has its own drawn glyph, the picker shows each block's shape, and a second branch off a decision asks for its words.
//
// One closure, one export: `diagramModel.joins`. `h` is the builder's helpers (`say`, `commit`, `ops`, `blockEl`).
(() => {
  //: The six link kinds, as the connector row's menu words them.
  const LINKS = [
    ["solid", true, "Arrow"], ["solid", false, "Line"], ["dotted", true, "Dotted arrow"],
    ["dotted", false, "Dotted line"], ["thick", true, "Thick arrow"], ["thick", false, "Thick line"],
  ];
  //: A shape's icon and word in the picker (R6.9): every block was one square and "Block".
  const SHAPES = { rect: ["ph:square", "Box"], round: ["ph:rectangle", "Rounded"], stadium: ["ph:pill", "Pill"], circle: ["ph:circle", "Circle"], diamond: ["ph:diamond", "Decision"], hexagon: ["ph:hexagon", "Hexagon"] };
  //: The picker's value for "a new block"; a block id never holds a plus.
  const NEW = "+";
  const titleOf = (h, S, id) => h.ops.node(S.m, id)?.text ?? h.ops.group(S.m, id)?.title ?? id;
  const nameOf = (h, S, key) => titleOf(h, S, h.ops.split(key)[1]);

  function items(S, edge, h) {
    const to = titleOf(h, S, edge.to);
    const links = LINKS.map(([style, arrow, name]) => ({
      label: `${edge.style === style && edge.arrow === arrow ? "ph:check" : "ph:arrow-right"} ${name}`,
      run: () => {
        Object.assign(edge, { style, arrow });
        h.commit(S, `The connector to ${to} is now a ${name.toLowerCase()}.`);
      },
      group: "kind",
    }));
    return [
      ...links,
      {
        label: "ph:text-t Label",
        run: async () => {
          const text = await promptDialog(`Label for the connector to ${to}`, edge.label, { confirmLabel: "Save" });
          if (text === null) return;
          edge.label = text.trim();
          h.commit(S, edge.label ? `Labelled the connector ${edge.label}.` : "Cleared the connector label.");
        },
        group: "edit",
      },
      { label: "ph:trash Remove connector", danger: true, run: () => (h.ops.unjoin(S.m, edge), h.commit(S, `Removed the connector to ${to}.`)), group: "edit" },
    ];
  }

  //: The connector row's menu (R6.4). It hangs from the row's right edge, as every menu does, so it opens under its row and
  //: not at the window's left; the six line kinds are drawn (`dgm-link`), where one arrow icon stood for four of them.
  function menu(S, { edge, chip }, h) {
    const r = chip.getBoundingClientRect();
    const rows = items(S, edge, h);
    openMenuAtPoint(rows, "This connector", r.right, r.bottom, chip);
    const open = document.querySelector(".action-menu:not(.hidden):not(.submenu)");
    open?.querySelectorAll(":scope > .menu-item").forEach((row, i) => {
      if (i >= LINKS.length) return;
      const [style, arrow, name] = LINKS[i];
      const made = document.createElement("button");
      made.type = "button";
      made.className = "menu-item dgm-shape-row";
      made.setAttribute("role", "menuitem");
      const glyph = document.createElement("span");
      glyph.className = "dgm-link";
      glyph.dataset.style = style;
      glyph.dataset.arrow = String(arrow);
      glyph.setAttribute("aria-hidden", "true");
      made.append(glyph, Object.assign(document.createElement("span"), { className: "menu-item-words", textContent: name }));
      if (edge.style === style && edge.arrow === arrow) {
        made.setAttribute("aria-current", "true");
        made.append(Object.assign(document.createElement("i"), { className: "ph ph-check dgm-shape-check" }));
      }
      made.addEventListener("click", (event) => {
        event.stopPropagation();
        closeActionMenus();
        rows[i].run();
      });
      row.replaceWith(made);
    });
    open?.querySelector(".menu-item")?.focus({ preventScroll: true });
  }

  //: The words for a decision's arrow, in one dialog: the field holds the offer (yes, then no) and a yes | no pair fills it, so one press answers. "" when cancelled.
  async function words(h, m, edge, message) {
    const word = h.ops.branchWord(m, edge);
    const options = ["yes", "no"].map((value) => ({ value, label: value }));
    const asked = promptDialog(message, word, { confirmLabel: "Save", segment: { label: "Quick answer", options, value: word } });
    //: The dialog's pair only picks; here a press is also the answer, so it is written into the field too.
    const card = document.querySelector(".prompt-card");
    card?.querySelectorAll(".seg button").forEach((b) => b.addEventListener("click", () => (card.querySelector("input").value = b.dataset.value)));
    return (await asked)?.text?.trim() || "";
  }

  //: Every arrow off a decision with no words on it is asked for them (R6.3, the first one too since INBOX 1679). Cancel keeps the arrow as it is.
  async function ask(S, edge, h) {
    if (!h.ops.needsLabel(S.m, edge)) return;
    const text = await words(h, S.m, edge, `Words for the arrow to ${titleOf(h, S, edge.to)}`);
    if (!text) return;
    edge.label = text;
    h.commit(S, `Labelled the connector ${edge.label}.`);
  }

  function pick(S, key, h) {
    const from = h.ops.split(key)[1];
    const shell = pickerDialog({ title: `Connect ${nameOf(h, S, key)} to`, placeholder: "Search the blocks…", searchLabel: "Search the blocks" });
    const box = pickerListbox(shell, "Blocks");
    //: What was typed, for the block that Add makes: typing a name that is not there yet is the quickest way to the next block.
    let typed = "";
    const paint = () => {
      typed = shell.search.value.trim();
      const needle = typed.toLowerCase();
      const fresh = { icon: "ph:plus", label: typed ? `Add “${typed}” as a new block` : "A new block", about: "Added after this one and connected", value: NEW };
      const rows = [
        ...(needle ? [] : [fresh]),
        ...S.m.nodes.filter((n) => n.id !== from).map((n) => ({ icon: (SHAPES[n.shape] || SHAPES.rect)[0], label: n.text, about: (SHAPES[n.shape] || SHAPES.rect)[1], value: n.id })),
        ...S.m.subgraphs.filter((g) => g.id !== from).map((g) => ({ icon: "ph:stack", label: g.title, about: "Group", value: g.id })),
      ].filter((item) => !needle || item.label.toLowerCase().includes(needle));
      if (needle) rows.push(fresh);
      box.fill(rows, needle, { icon: "ph:squares-four", title: "No block matches", text: "Try other words." });
    };
    shell.search.addEventListener("input", paint);
    paint();
    new Promise((resolve) => shell.open(resolve)).then(async (to) => {
      if (!to) return h.blockEl(S, key)?.focus();
      if (to === NEW) {
        //: Asked before the block is made, so the arrow's words and then the block's name are two steps, not two fields at once.
        const probe = { from, label: "" };
        const ahead = { ...S.m, edges: [...S.m.edges, probe] };
        const said = h.ops.needsLabel(ahead, probe) ? await words(h, ahead, probe, "Words for the new arrow") : "";
        //: A box, not the shape in hand: from a decision the next block was a decision too.
        return h.add(S, { after: key, from, shape: "rect", text: typed || undefined, label: said, edit: !typed });
      }
      const edge = h.ops.join(S.m, from, to);
      const name = titleOf(h, S, to);
      if (!edge) return h.say(S, `${nameOf(h, S, key)} is already connected to ${name}.`);
      S.sel = key;
      h.commit(S, `Connected ${nameOf(h, S, key)} to ${name}.`);
      h.blockEl(S, key)?.focus();
      ask(S, edge, h);
    });
    //: A phone does not get its keyboard over the list at once (R6.9): focus rests on the dialog, the field is a tap away.
    if (matchMedia("(pointer: coarse)").matches) {
      shell.card.tabIndex = -1;
      shell.card.focus({ preventScroll: true });
    }
  }

  diagramModel.joins = { items, menu, pick };
})();
