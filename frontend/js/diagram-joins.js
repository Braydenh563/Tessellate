// diagram-joins.js: a flowchart's connectors, in the block pane (1546 P2 built them, P4 moved them out so
// diagram-builder.js, which every diagram opens, stays small). Lazy: `LAZY_MODULES.diagramJoins`,
// registered at the foot of documents-mermaid.js and fetched by the builder on the first press of a
// connector row or of Connect to. Two things: the items of the menu a connector row opens (its line, its label, remove) and the
// picker that connects one block to another, which can also make the other block (1594). R6: the menu hangs from its row (the builder's kebabMenu, `anchor`),
// each line kind has its own drawn glyph, the picker shows each block's shape, and a second branch off a decision asks for its words.
//
// One closure, one export: `diagramModel.joins`. `h` is the builder's helpers (`say`, `commit`, `ops`, `blockEl`).
(() => {
  //: The block after the source's run of targets, so a new target lands under its siblings (the order they were added), not above them (1679, slice 6).
  function lastTarget(h, S, key, from) {
    const keys = h.ops.sisters(S.m, key)?.keys || [];
    let at = keys.indexOf(key) + 1;
    while (at < keys.length && S.m.edges.some((e) => e.from === from && e.to === keys[at].slice(2))) at++;
    return keys[at] ?? null;
  }

  //: The link kinds, as the connector row's menu words them; the fourth field is Both ways (`<-->`, 1679 slice 10).
  const LINKS = [
    ["solid", true, "Arrow"], ["solid", false, "Line"], ["dotted", true, "Dotted arrow"],
    ["dotted", false, "Dotted line"], ["thick", true, "Thick arrow"], ["thick", false, "Thick line"],
    ["solid", true, "Both ways", true],
  ];
  const isKind = (edge, [style, arrow, , both]) => edge.style === style && edge.arrow === arrow && Boolean(edge.both) === Boolean(both);
  //: A shape's icon and word in the picker (R6.9): every block was one square and "Block".
  const SHAPES = { rect: ["ph:square", "Box"], round: ["ph:rectangle", "Rounded"], stadium: ["ph:pill", "Pill"], circle: ["ph:circle", "Circle"], diamond: ["ph:diamond", "Decision"], hexagon: ["ph:hexagon", "Hexagon"], cylinder: ["ph:database", "Database"], parallelogram: ["ph:parallelogram", "Input or output"] };
  //: The picker's value for "a new block"; a block id never holds a plus.
  const NEW = "+";
  const titleOf = (h, S, id) => h.ops.node(S.m, id)?.text ?? h.ops.group(S.m, id)?.title ?? id;
  const nameOf = (h, S, key) => titleOf(h, S, h.ops.split(key)[1]);

  function items(S, edge, h) {
    const to = titleOf(h, S, edge.to);
    //: The six line kinds are drawn (`dgm-link` through the item's `lead`), where one arrow icon stood for four of them; the kind the connector is wears `current`.
    const links = LINKS.map((kind) => ({
      label: kind[2],
      lead: () => {
        const slot = Object.assign(document.createElement("span"), { className: "dgm-menu-glyph" });
        const glyph = Object.assign(document.createElement("span"), { className: "dgm-link" });
        glyph.dataset.style = kind[0];
        glyph.dataset.arrow = kind[3] ? "both" : String(kind[1]);
        slot.setAttribute("aria-hidden", "true");
        slot.append(glyph);
        return slot;
      },
      current: isKind(edge, kind),
      run: () => {
        const [style, arrow, name, both] = kind;
        Object.assign(edge, { style, arrow });
        if (both) edge.both = true;
        else delete edge.both;
        h.commit(S, `The connector to ${to} is now a ${name.toLowerCase()}.`);
      },
      group: "kind",
    }));
    return [
      ...links,
      {
        label: "ph:palette Colour…",
        run: async () => (await ensureModule("diagramStyle")) && diagramModel.style.edge(S, h, edge),
        group: "edit",
      },
      {
        label: "ph:fast-forward Animation…",
        run: async () => (await ensureModule("diagramStyle")) && diagramModel.style.animate(S, h, edge),
        group: "edit",
      },
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
      {
        label: "ph:swap Reverse direction",
        run: () => {
          if (S.m.edges.some((e) => e !== edge && e.from === edge.to && e.to === edge.from && e.label === edge.label)) return h.say(S, "A connector already points that way.");
          [edge.from, edge.to] = [edge.to, edge.from];
          h.commit(S, `The connector now runs from ${titleOf(h, S, edge.from)} to ${titleOf(h, S, edge.to)}.`);
        },
        group: "edit",
      },
      { label: `ph:arrow-elbow-down-right Go to ${to}`, title: "Pick this connector and the block it points at", run: () => go(S, { edge, end: "to" }, h), group: "go" },
      { label: `ph:arrow-elbow-up-left Go to ${titleOf(h, S, edge.from)}`, title: "Pick this connector and the block it leaves", run: () => go(S, { edge, end: "from" }, h), group: "go" },
      { label: "ph:trash Remove connector", danger: true, run: () => (h.ops.unjoin(S.m, edge), h.commit(S, `Removed the connector to ${to}.`)), group: "edit" },
    ];
  }

  //: A connector row's press: picks the arrow in the picture and puts the list on the block at one end ("to", or "from" for the source). The
  //: block row is the list's own selection, so the picture's box and the row agree; the focus stays on the row that was pressed.
  function go(S, { edge, end = "to" }, h) {
    const id = edge[end];
    const key = h.ops.node(S.m, id) ? h.ops.key("n", id) : h.ops.key("g", id);
    S.pickEdge?.(edge);
    h.select(S, key);
    h.blockEl(S, key)?.scrollIntoView({ block: "nearest" });
    h.say(S, `Went to ${titleOf(h, S, id)}, where the connector ${end === "to" ? `from ${titleOf(h, S, edge.from)} ends` : `to ${titleOf(h, S, edge.to)} starts`}.`);
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
        return h.add(S, { after: key, from, shape: "rect", text: typed || undefined, label: said, edit: !typed, before: lastTarget(h, S, key, from) });
      }
      const edge = h.ops.join(S.m, from, to);
      const name = titleOf(h, S, to);
      if (!edge) return h.say(S, `${nameOf(h, S, key)} is already connected to ${name}.`);
      S.sel = key;
      h.commit(S, `Connected ${nameOf(h, S, key)} to ${name}.`);
      h.blockEl(S, key)?.focus();
      ask(S, edge, h);
    });
    //: A tap on Connect to… wants the keyboard (1679, slice 11: typing a name needed a second tap); a key press or the menu keeps R6.9's choice,
    //: that a phone does not get its keyboard over the list at once, so focus rests on the dialog and the field is a tap away.
    const tapped = S.tapped;
    S.tapped = false;
    if (tapped) shell.search.focus();
    else if (matchMedia("(pointer: coarse)").matches) {
      shell.card.tabIndex = -1;
      shell.card.focus({ preventScroll: true });
    }
  }

  diagramModel.joins = { items, pick, ask, go };
})();
