// diagram-joins.js: a flowchart's connectors, in the block pane (1546 P2 built them, P4 moved them out so
// diagram-builder.js, which every diagram opens, stays small). Lazy: `LAZY_MODULES.diagramJoins`,
// registered at the foot of documents-mermaid.js and fetched by the builder on the first press of a
// connector row or of Connect to. Two things: the menu a connector row opens (its line, its label, remove) and the
// picker that connects one block to another, which can also make the other block (1594).
//
// One closure, one export: `diagramModel.joins`. `h` is the builder's helpers (`say`, `commit`, `ops`, `blockEl`).
(() => {
  //: The six link kinds, as the connector row's menu words them.
  const LINKS = [
    ["solid", true, "Arrow"], ["solid", false, "Line"], ["dotted", true, "Dotted arrow"],
    ["dotted", false, "Dotted line"], ["thick", true, "Thick arrow"], ["thick", false, "Thick line"],
  ];
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
        ...S.m.nodes.filter((n) => n.id !== from).map((n) => ({ icon: "ph:square", label: n.text, about: "Block", value: n.id })),
        ...S.m.subgraphs.filter((g) => g.id !== from).map((g) => ({ icon: "ph:stack", label: g.title, about: "Group", value: g.id })),
      ].filter((item) => !needle || item.label.toLowerCase().includes(needle));
      if (needle) rows.push(fresh);
      box.fill(rows, needle, { icon: "ph:squares-four", title: "No block matches", text: "Try other words." });
    };
    shell.search.addEventListener("input", paint);
    paint();
    new Promise((resolve) => shell.open(resolve)).then((to) => {
      if (!to) return h.blockEl(S, key)?.focus();
      if (to === NEW) return h.add(S, { after: key, from, text: typed || undefined, edit: !typed });
      const edge = h.ops.join(S.m, from, to);
      const name = titleOf(h, S, to);
      if (!edge) return h.say(S, `${nameOf(h, S, key)} is already connected to ${name}.`);
      S.sel = key;
      h.commit(S, `Connected ${nameOf(h, S, key)} to ${name}.`);
      h.blockEl(S, key)?.focus();
    });
  }

  diagramModel.joins = { items, pick };
})();
