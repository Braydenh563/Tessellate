// diagram-joins.js: a flowchart's joins, in the block pane (1546 P2 built them, P4 moved them out so
// diagram-builder.js, which every diagram opens, stays small). Lazy: `LAZY_MODULES.diagramJoins`,
// registered at the foot of documents-mermaid.js and fetched by the builder on the first press of a
// join chip or of Join to. Two things: the menu a join chip opens (its kind, its label, remove) and the
// picker that joins one block to another.
//
// One closure, one export: `diagramModel.joins`. `h` is the builder's helpers (`say`, `commit`, `ops`, `blockEl`).
(() => {
  //: The six link kinds, as the join chip's menu words them.
  const LINKS = [
    ["solid", true, "Arrow"], ["solid", false, "Line"], ["dotted", true, "Dotted arrow"],
    ["dotted", false, "Dotted line"], ["thick", true, "Thick arrow"], ["thick", false, "Thick line"],
  ];
  const titleOf = (h, S, id) => h.ops.node(S.m, id)?.text ?? h.ops.group(S.m, id)?.title ?? id;
  const nameOf = (h, S, key) => titleOf(h, S, h.ops.split(key)[1]);

  function items(S, edge, h) {
    const to = titleOf(h, S, edge.to);
    const links = LINKS.map(([style, arrow, name]) => ({
      label: `${edge.style === style && edge.arrow === arrow ? "ph:check" : "ph:arrow-right"} ${name}`,
      run: () => {
        Object.assign(edge, { style, arrow });
        h.commit(S, `Join to ${to} is now a ${name.toLowerCase()}.`);
      },
      group: "kind",
    }));
    return [
      ...links,
      {
        label: "ph:text-t Label",
        run: async () => {
          const text = await promptDialog(`Label for the join to ${to}`, edge.label, { confirmLabel: "Save" });
          if (text === null) return;
          edge.label = text.trim();
          h.commit(S, edge.label ? `Labelled the join ${edge.label}.` : "Cleared the join label.");
        },
        group: "edit",
      },
      { label: "ph:trash Remove join", danger: true, run: () => (h.ops.unjoin(S.m, edge), h.commit(S, `Removed the join to ${to}.`)), group: "edit" },
    ];
  }

  function pick(S, key, h) {
    const from = h.ops.split(key)[1];
    const shell = pickerDialog({ title: `Join ${nameOf(h, S, key)} to`, placeholder: "Search the blocks…", searchLabel: "Search the blocks" });
    const box = pickerListbox(shell, "Blocks");
    const paint = () => {
      const needle = shell.search.value.trim().toLowerCase();
      const rows = [
        ...S.m.nodes.filter((n) => n.id !== from).map((n) => ({ icon: "ph:square", label: n.text, about: "Block", value: n.id })),
        ...S.m.subgraphs.filter((g) => g.id !== from).map((g) => ({ icon: "ph:stack", label: g.title, about: "Group", value: g.id })),
      ].filter((item) => !needle || item.label.toLowerCase().includes(needle));
      box.fill(rows, needle, { icon: "ph:squares-four", title: needle ? "No block matches" : "No other block yet", text: needle ? "Try other words." : "Add a block to join to." });
    };
    shell.search.addEventListener("input", paint);
    paint();
    new Promise((resolve) => shell.open(resolve)).then((to) => {
      if (!to) return h.blockEl(S, key)?.focus();
      const edge = h.ops.join(S.m, from, to);
      const name = titleOf(h, S, to);
      if (!edge) return h.say(S, `${nameOf(h, S, key)} is already joined to ${name}.`);
      S.sel = key;
      h.commit(S, `Joined ${nameOf(h, S, key)} to ${name}.`);
      h.blockEl(S, key)?.focus();
    });
  }

  diagramModel.joins = { items, pick };
})();
