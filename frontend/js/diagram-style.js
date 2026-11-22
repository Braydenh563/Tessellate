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
    ["Tab", "Add a box after the last one, joined to it"], ["Shift + Tab", "Select the box that points at this one"], ["F6", "Leave the blocks for the picture"], ["[ and ]", "Fold the list or the picture to a rail, or open it"], ["Ctrl + Enter", "Keep the diagram (Done)"],
    ["Enter, F2", "Name the selected block, in the list or on the picture"], ["Delete", "Remove the selected block"], ["C", "Connect the selected block to another"],
    ["K", "Colour the selected blocks"], ["Alt + arrows", "Move or nest the selected block"], ["Ctrl + Z, Ctrl + Y", "Undo, redo"],
    ["Shift + Enter", "Add a box joined to the selected one and name it"], ["Alt + Enter", "Add a box joined to the same parent (a sister)"], ["Ctrl + D", "Duplicate the selected blocks"], ["Ctrl + A", "Select every block (the List's Select all does the same)"], ["Delete on the picture", "Remove the selected blocks"], ["Ctrl + F, /", "Find a block by its words; Enter goes to the next"], ["Double press on empty picture", "Add a box"], ["Shift + F10", "Open the block menu"], ["Left, Right in the bar", "Move along its buttons; Enter on ... opens the look, Save as PNG and Save to Library"], ["Arrows on the picture", "Pick the box in that direction"], ["Shift + arrows on the picture", "Move the picture"], ["Drag on empty picture", "Pick the blocks the box touches; Shift or Ctrl adds"], ["Shift + click on a block", "Add it to the pick, or take it out"], ["Ctrl + arrows on the picture", "Add the next box that way to the pick"], ["Space + drag on the picture", "Move the picture (the middle button does too)"], ["+ on a sequence picture", "Open the Add menu for the gap after the picked step"], ["Tab, Shift + Tab in Source", "Indent, take the indent back"], ["Esc in Source", "Leave the text for the views"], ["Ctrl + Space in Source", "List Mermaid words"], ["?", "Show this sheet"],
  ];

  //: The keys the shape table holds, each with the word the Add menu uses.
  function shapeRows(h) {
    //: Each read as a thing you add (the owner's screenshot 2026-11-09 read "Add a input or output" and "Add a rounded").
    const label = { ...h.label, group: "Group", note: "Note", round: "Rounded box", parallelogram: "Input or output box" };
    const article = (word) => (/^[aeiou]/i.test(word) ? "an" : "a");
    return Object.entries(diagramModel.keys).map(([key, shape]) => {
      const word = label[shape].toLowerCase();
      return [key.toUpperCase(), `Add ${article(word)} ${word}`];
    });
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

  //: L-documents-58: an arrow's animation (`e.animate`: on, fast or slow; Mermaid's `e1@-->` and `e1@{ animate: true }`). The id is the
  //: model's to make when it prints. The picture holds still under reduced motion (mermaid-draw.js).
  function animate(S, h, link) {
    const to = h.ops.node(S.m, link.to)?.text ?? h.ops.group(S.m, link.to)?.title ?? link.to;
    const ways = [["", "Still"], ["on", "Moving"], ["slow", "Moving, slowly"], ["fast", "Moving, quickly"]];
    openSheet({
      label: `Animation for the arrow to ${to}`,
      sub: "Draws the arrow moving on the picture. It holds still when motion is reduced.",
      name: "diagram-animate",
      build: (card, close) => {
        const list = h.el("div", "dgm-animate-list");
        for (const [way, name] of ways) {
          const button = h.el("button", "ghost");
          button.type = "button";
          button.textContent = name;
          button.setAttribute("aria-pressed", String((link.animate || "") === way));
          button.addEventListener("click", () => {
            close();
            if (way) link.animate = way;
            else delete link.animate;
            h.commit(S, way ? `The arrow to ${to} is now ${name.toLowerCase()}.` : `The arrow to ${to} holds still.`);
          });
          list.append(button);
        }
        card.append(list);
      },
    });
  }

  //: L-documents-55. A block's class (`n.cls`, a `classDef` in `m.classes`, props kept raw): a new name makes the class
  //: from a pale blue and a blank takes the block out of it.
  async function cls(S, h, key) {
    const n = h.ops.node(S.m, h.ops.split(key)[1]);
    const names = (S.m.classes || []).map((c) => c.name);
    const text = await promptDialog(`Class for ${n.text}${names.length ? ` (now: ${names.join(", ")})` : ""}`, n.cls || "", { confirmLabel: "Save" });
    if (text === null) return;
    const name = text.trim();
    if (name && !/^[\w-]+$/.test(name)) return h.say(S, "A class name is letters, digits, - and _.");
    if (name && !names.includes(name)) (S.m.classes ||= []).push({ name, css: "fill:#e8f0fe,stroke:#4a6fa5,color:#1a1a1a" });
    if (name) n.cls = name;
    else delete n.cls;
    h.commit(S, name ? `${n.text} is in the class ${name}. Its look is a classDef line in Source.` : `${n.text} is out of its class.`);
  }

  //: A block's link (`n.href`): http(s) or a `[[note]]`, nothing else (no `javascript:`). Opened through the document's own
  //: link path (`docOpenLink`, `docOpenWikiTarget`), never by the picture, which is an image.
  async function link(S, h, key) {
    const n = h.ops.node(S.m, h.ops.split(key)[1]);
    const text = await promptDialog(`Link for ${n.text}: an https address or [[a note]]`, n.href || "", { confirmLabel: "Save" });
    if (text === null) return;
    const url = text.trim();
    if (url && !/^(?:https?:\/\/[^\s"]+|\[\[[^\]"\n]+\]\])$/i.test(url)) return h.say(S, "Only https addresses and [[note]] links are kept.");
    if (url) n.href = url;
    else delete n.href, delete n.tip;
    h.commit(S, url ? `${n.text} links to ${url}.` : `Removed the link from ${n.text}.`);
  }

  function follow(S, h, key) {
    const href = h.ops.node(S.m, h.ops.split(key)[1])?.href || "";
    if (href.startsWith("[[")) docOpenWikiTarget(href.slice(2, -2));
    else docOpenLink(href);
  }

  //: The block menu's own rows for a flowchart block (diagram-builder.js `blockItems` adds them once this file is loaded, which `show` asks for): a block's
  //: Markdown text, Class and Link (and Open link), a group's Direction (`g.dir`, the group's own flow, L-documents-59, 60, 55).
  function items(S, h, key) {
    const [type, id] = h.ops.split(key);
    if (type === "n") {
      const n = h.ops.node(S.m, id);
      const flip = () => ((n.md = !n.md), n.md || delete n.md, h.commit(S, `${n.text} is now ${n.md ? "markdown text: **bold**, *italic*" : "plain text"}.`));
      return [
        { label: "ph:shapes Class…", run: () => cls(S, h, key), group: "edit" },
        { label: "ph:link-simple Link…", run: () => link(S, h, key), group: "edit" },
        ...(n.href ? [{ label: "ph:arrow-square-out Open link", run: () => follow(S, h, key), group: "edit" }] : []),
        { label: n.md ? "ph:text-aa Plain text" : "ph:text-b Markdown text", run: flip, group: "edit" },
      ];
    }
    const g = h.ops.group(S.m, id);
    const turn = (dir) => () => (dir ? (g.dir = dir) : delete g.dir, h.commit(S, dir ? `${g.title} flows ${S.bar.dirs.find(([d]) => d === dir)[2].toLowerCase()}.` : `${g.title} follows the diagram's direction.`));
    return [{ label: "ph:arrows-out-line-horizontal Direction", items: [...S.bar.dirs.map(([d, icon, name]) => ({ label: `${icon} ${name}`, run: turn(d) })), { label: "Same as the diagram", run: turn("") }], group: "edit" }];
  }

  function shortcuts(S, h) {
    const rows = [...shapeRows(h), ...OTHER];
    openSheet({
      label: "Keyboard shortcuts",
      sub: "From anywhere in the editor outside a text field.",
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

  diagramModel.style = { colour, edge, animate, shortcuts, items };
})();
