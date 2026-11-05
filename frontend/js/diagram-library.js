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
  const IDLE = "Press a shape to add it, or drag it into the blocks.";

  //: The flowchart's tiles by meaning: [group, [[shape, hint], ...]]. A note is a rounded block that says "Note".
  const FLOW = [
    ["Steps", [["rect", "A step or an action."], ["round", "A softer step, for a state or a result."], ["hexagon", "A set-up or preparation step."]]],
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

  function build(tiles, idle = IDLE) {
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
      for (const t of list) {
        const tile = make("button", "dgm-tile");
        tile.type = "button";
        tile.dataset.objGrip = "";
        Object.assign(tile.dataset, t.data, { hint: t.hint });
        tile.title = `${t.hint} Press to add it, or drag it into the blocks.`;
        tile.setAttribute("aria-label", t.label);
        if (t.keys) tile.setAttribute("aria-keyshortcuts", t.keys);
        tile.append(t.glyph, make("span", "dgm-tile-name", t.name));
        tile.addEventListener("click", t.press);
        row.append(tile);
      }
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

  diagramModel.library = { build, flow };
})();
