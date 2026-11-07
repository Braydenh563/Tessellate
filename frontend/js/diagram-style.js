// diagram-style.js: block colour and the shortcuts sheet (INBOX 1661 step B). Lazy: `LAZY_MODULES.diagramStyle`,
// fetched on the first press of Colour (K, the block menu) or `?` / the ... menu's Keyboard shortcuts, so the builder
// carries two call sites and no more.
//
// Colour is `n.fill`, one hex hue per block, written by `diagramModel.print` as the one `style` line it also reads
// back (documents-mermaid.js); every other style line in a source stays a kept line. The picker is the swatch picker
// (categories-panel.js) with the same twelve hues as the categories, so a colour means the same thing everywhere.
// The shortcuts sheet reads `diagramModel.keys` for the shape keys, so it cannot drift from the handler.
(() => {
  //: Keys that are not in the shape table: [keys, what it does].
  const OTHER = [
    ["Tab", "Add a box after the selected one, joined to it"], ["Shift + Tab", "Select the box that points at this one"], ["F6", "Leave the blocks for the picture"],
    ["Enter, F2", "Name the selected block"], ["Delete", "Remove the selected block"], ["C", "Connect the selected block to another"],
    ["K", "Colour the selected blocks"], ["Alt + arrows", "Move or nest the selected block"], ["Ctrl + Z, Ctrl + Y", "Undo, redo"],
    ["Shift + F10", "Open the block menu"], ["?", "Show this sheet"],
  ];

  //: The keys the shape table holds, each with the word the Add menu uses.
  function shapeRows(h) {
    const label = { ...h.label, group: "Group", note: "Note" };
    return Object.entries(diagramModel.keys).map(([key, shape]) => [key.toUpperCase(), `Add ${shape === "group" ? "a group" : `a ${label[shape].toLowerCase()}`}`]);
  }

  //: The blocks a colour applies to: the picked set, else the selection; nodes only (a group has no fill).
  const targets = (S, key, ops) => [...(S.picked?.size ? S.picked : [key || S.sel])].filter((k) => k && k[0] === "n").map((k) => ops.node(S.m, ops.split(k)[1]));

  function colour(S, h, key) {
    const nodes = targets(S, key, h.ops);
    if (!nodes.length) return h.say(S, "Select a box to colour it.");
    const named = nodes.length === 1 ? nodes[0].text : `${nodes.length} blocks`;
    const keyOf = (hue) => Object.keys(CATEGORY_PALETTE).find((k) => CATEGORY_PALETTE[k] === hue) || null;
    const apply = (key) => {
      for (const n of nodes) {
        if (key) n.fill = CATEGORY_PALETTE[key];
        else delete n.fill;
      }
      h.commit(S, key ? `Coloured ${named} ${key}.` : `Cleared the colour of ${named}.`);
    };
    openSheet({
      label: `Colour for ${named}`,
      sub: "Fills the box on the picture. Automatic clears it.",
      name: "diagram-colour",
      build: (card, close) => {
        card.classList.add("swatch-card");
        card.append(swatchPicker({ label: "Colour", value: keyOf(nodes[0].fill), onChange: () => {}, onChoose: (key) => (close(), apply(key)), none: "Automatic" }));
      },
    });
  }

  //: An arrow's colour (1679 slice 10): `link.colour`, one hex hue written as a `linkStyle` line (documents-mermaid.js).
  function edge(S, h, link) {
    const to = h.ops.node(S.m, link.to)?.text ?? h.ops.group(S.m, link.to)?.title ?? link.to;
    const keyOf = (hue) => Object.keys(CATEGORY_PALETTE).find((k) => CATEGORY_PALETTE[k] === hue) || null;
    const apply = (key) => {
      if (key) link.colour = CATEGORY_PALETTE[key];
      else delete link.colour;
      h.commit(S, key ? `Coloured the arrow to ${to} ${key}.` : `Cleared the colour of the arrow to ${to}.`);
    };
    openSheet({
      label: `Colour for the arrow to ${to}`,
      sub: "Draws the arrow on the picture. Automatic clears it.",
      name: "diagram-colour",
      build: (card, close) => {
        card.classList.add("swatch-card");
        card.append(swatchPicker({ label: "Colour", value: keyOf(link.colour), onChange: () => {}, onChoose: (key) => (close(), apply(key)), none: "Automatic" }));
      },
    });
  }

  function shortcuts(S, h) {
    const rows = [...shapeRows(h), ...OTHER];
    openSheet({
      label: "Keyboard shortcuts",
      sub: "With the picture or the blocks focused.",
      name: "diagram-shortcuts",
      build: (card) => {
        const field = document.createElement("input");
        field.type = "search";
        field.className = "search-field";
        field.setAttribute("aria-label", "Find a shortcut");
        field.placeholder = "Find a shortcut";
        const list = document.createElement("ul");
        list.className = "wb-help-list dgm-keys";
        const items = rows.map(([keys, what]) => {
          const li = document.createElement("li");
          li.className = "wb-help-row";
          const icon = document.createElement("i");
          icon.className = "ph ph-keyboard wb-help-row-icon";
          icon.setAttribute("aria-hidden", "true");
          const label = document.createElement("span");
          label.textContent = what;
          const hint = document.createElement("span");
          hint.className = "wb-help-row-keys";
          const kbd = document.createElement("kbd");
          kbd.textContent = keys;
          hint.append(kbd);
          li.append(icon, label, hint);
          list.append(li);
          return li;
        });
        field.addEventListener("input", () => {
          const q = field.value.trim().toLowerCase();
          rows.forEach(([keys, what], i) => items[i].classList.toggle("hidden", Boolean(q) && !`${keys} ${what}`.toLowerCase().includes(q)));
        });
        card.append(field, list);
        field.focus();
      },
    });
  }

  diagramModel.style = { colour, edge, shortcuts };
})();
