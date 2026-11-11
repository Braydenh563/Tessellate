// diagram-joins.js: a flowchart's connectors, in the block pane (1546 P2 built them, P4 moved them out so
// diagram-builder.js, which every diagram opens, stays small). Lazy: `LAZY_MODULES.diagramJoins`,
// registered at the foot of documents-mermaid.js and fetched by the builder on the first press of a
// connector row or of Connect to. Two things: the menu a connector row opens (its line, its label, remove) and the
// picker that connects one block to another, which can also make the other block (1594). R6: the menu hangs from its row,
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
    const links = LINKS.map((kind) => ({
      label: `${isKind(edge, kind) ? "ph:check" : kind[3] ? "ph:arrows-left-right" : "ph:arrow-right"} ${kind[2]}`,
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

  //: The menu off the row that opened it (INBOX 1771, the owner: "appears on top of it and not next to it"). `openMenuAtPoint` hangs a menu
  //: from a one-pixel point, so a menu taller than the room below flipped up from that point and lay across the row (measured at 1440x900:
  //: the row at 475 to 499, the menu 101 to 505). Placed here against the row's whole box instead: below, above, then to the right or the left,
  //: the first that fits the window; none fitting, the larger of below and above with the menu scrolling inside it.
  function beside(menu, row, opener) {
    if (!menu) return;
    const [margin, gap] = [8, 4];
    escapeMenuToBody(menu, opener);
    menu.style.visibility = "hidden";
    menu.style.maxHeight = "";
    menu.style.left = "0px";
    menu.style.top = "0px";
    const [vw, vh] = [window.innerWidth, window.innerHeight];
    const box = menu.getBoundingClientRect();
    const clamp = (n, size, room) => Math.max(margin, Math.min(n, room - margin - size));
    const fits = (top) => top >= margin && top + box.height <= vh - margin;
    let [left, top] = [clamp(row.right - box.width, box.width, vw), 0];
    if (fits(row.bottom + gap)) top = row.bottom + gap;
    else if (fits(row.top - gap - box.height)) top = row.top - gap - box.height;
    else if (row.right + gap + box.width <= vw - margin) [left, top] = [row.right + gap, clamp(row.top, box.height, vh)];
    else if (row.left - gap - box.width >= margin) [left, top] = [row.left - gap - box.width, clamp(row.top, box.height, vh)];
    else {
      const room = [vh - margin - (row.bottom + gap), row.top - gap - margin];
      const below = room[0] >= room[1];
      menu.style.maxHeight = `${Math.max(120, Math.floor(room[below ? 0 : 1]))}px`;
      top = below ? row.bottom + gap : Math.max(margin, row.top - gap - menu.getBoundingClientRect().height);
    }
    menu.style.left = `${Math.round(left)}px`;
    menu.style.top = `${Math.round(top)}px`;
    menu.style.visibility = "";
  }

  //: The connector row's menu (R6.4). It hangs from the row's right edge, as every menu does, so it opens under its row and
  //: not at the window's left; the six line kinds are drawn (`dgm-link`), where one arrow icon stood for four of them.
  function menu(S, { edge, chip }, h) {
    //: The whole row, not its ⋯: the menu stays off the words it belongs to.
    const r = (chip.closest(".dgm-joinline") || chip).getBoundingClientRect();
    const rows = items(S, edge, h);
    const open = openMenuAtPoint(rows, "This connector", r.right, r.bottom, chip);
    beside(open, r, chip);
    open?.querySelectorAll(":scope > .menu-item").forEach((row, i) => {
      if (i >= LINKS.length) return;
      const [style, arrow, name, both] = LINKS[i];
      const made = document.createElement("button");
      made.type = "button";
      made.className = "menu-item dgm-shape-row";
      made.setAttribute("role", "menuitem");
      const glyph = document.createElement("span");
      glyph.className = "dgm-link";
      glyph.dataset.style = style;
      glyph.dataset.arrow = both ? "both" : String(arrow);
      glyph.setAttribute("aria-hidden", "true");
      made.append(glyph, Object.assign(document.createElement("span"), { className: "menu-item-words", textContent: name }));
      if (isKind(edge, LINKS[i])) {
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

  diagramModel.joins = { items, menu, pick, ask, go };
})();
