// diagram-builder.js: the block pane of a diagram (1546 P2, DOCUMENTS_PLAN "1546 design" D5 to D10). Lazy:
// `LAZY_MODULES.diagramBuilder` (documents-mermaid.js). Blocks, connector rows and the live picture; each gesture is one
// model change printed to the source (`io.set`), so the source is the only state and its history the undo. Pure half:
// diagram-ops.js; Add library: diagram-library.js; drag: diagram-pointer.js. Held to 12 KB gzipped: new behaviour goes
// in lazy files. One closure, one export: `diagramModel.builder`.
(() => {
  //: The pure half (diagram-ops.js, fetched with this file): keys name blocks, every change is one call, none draws.
  let diagramOps;

  // ---------------------------------------------------------------------------
  // The pane
  // ---------------------------------------------------------------------------
  //: Filled from `diagramOps.LABEL` and `.TEXT` when the pane opens (the tables live in diagram-ops.js).
  const SHAPE_LABEL = {};
  const SHAPE_TEXT = {};
  //: A narrow window or a touch screen: the phone's palette sheet and pinch.
  const COMPACT = "(max-width: 599.98px), (pointer: coarse)";
  //: Whole icon names, so tests/test_icon_names.py can check each is in the font.
  const DIRS = [["TD", "ph:arrow-down", "Top to bottom"], ["LR", "ph:arrow-right", "Left to right"], ["BT", "ph:arrow-up", "Bottom to top"], ["RL", "ph:arrow-left", "Right to left"]];
  //: The instance of a mounted pane, by its root element.
  const panes = new WeakMap();

  function el(tag, cls, text) {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text != null) node.textContent = text;
    return node;
  }

  const say = (S, text) => {
    S.live.textContent = "";
    //: A second message in the same turn still reads: the region is emptied, then filled a tick later.
    setTimeout(() => (S.live.textContent = text), 20);
  };

  const titleOf = (S, id) => diagramOps.node(S.m, id)?.text ?? diagramOps.group(S.m, id)?.title ?? id;
  const nameOf = (S, key) => titleOf(S, diagramOps.split(key)[1]);

  const blockEl = (S, key) => (key ? S.tree.querySelector(`.dgm-block[data-key="${key.replace(/["\\]/g, "\\$&")}"]`) : null);

  //: One change printed: the whole source goes out when it differs, the pane is
  //: drawn again and `said` is announced. The first change to a source the
  //: printer would have written differently says so once.
  function commit(S, said) {
    const src = (S.k || diagramModel).print(S.m);
    if (src !== S.source) {
      const tidy = S.tidy;
      S.tidy = false;
      S.source = src;
      S.io.set(src);
      if (tidy) said = `${said} Tidied the source.`;
    }
    say(S, said);
    (S.k ? S.k.render : render)(S);
    drawPicture(S);
  }

  // --- the picture ----------------------------------------------------------------
  function drawPicture(S) {
    clearTimeout(S.drawTimer);
    S.drawing = true; //: edges.js `ask` waits for the draw (1661)
    S.drawTimer = setTimeout(() => {
      const source = S.source;
      const stamp = ++S.drawn;
      //: Empty: no block and only a header; a kept line is still drawn, so the picture says why.
      const blank = S.k ? S.k.blank(S.m) : S.m && !S.m.nodes.length;
      const bare = diagramModel.front(source.replace(/\r/g, "")).rest.split("\n").every((l) => !l.trim() || /^\s*(%%|flowchart\b|graph\b|mindmap\b|timeline\b|sequenceDiagram\b)/i.test(l));
      const empty = !source.trim() || (!S.plain && blank && bare);
      S.fig.classList.toggle("dgm-picture-empty", empty);
      //: The phone layout keys on the window body; a class, not `.dgm-body:has()` (test_css_body_has).
      S.fig.closest(".dgm-body")?.classList.toggle("dgm-body-empty", empty);
      if (empty) return (S.drawing = false), S.fig.replaceChildren(el("p", "muted dgm-hint", "Press Add above to start the diagram."));
      //: The hint goes now, or it and the pending line show together (1679 m).
      S.fig.querySelector(":scope > .dgm-hint")?.remove();
      Promise.all([ensureModule("mermaid"), diagramModel.picture.idle(S)]).then(([ok]) => {
        if (!ok) S.drawing = false;
        if (!ok || stamp !== S.drawn) return;
        const began = performance.now();
        mermaidFill(S.fig, source, (result) => {
          //: A big diagram waits half its draw time for the next change.
          S.drawWait = Math.min(600, Math.max(120, (performance.now() - began) / 2));
          if (stamp !== S.drawn) return;
          S.drawing = false;
          S.hit = result.svg ? diagramModel.picture.boxes(result.svg) : null;
          for (const paint of S.fig.onpaint || []) paint();
          diagramModel.picture.failure(S, result, source, smallButton);
        });
      });
    }, S.drawWait || 120);
  }

  // --- the tree -------------------------------------------------------------------
  function render(S) {
    const had = S.tree.contains(document.activeElement);
    const layout = diagramModel.outline ? diagramModel.outline.order(S.m, diagramOps.layout(S.m)) : diagramOps.layout(S.m);
    const edgesFrom = new Map();
    S.m.edges.forEach((e, i) => edgesFrom.set(e.from, [...(edgesFrom.get(e.from) || []), { e, i }]));
    const live = blockKeys(layout);
    if (S.sel && !live.includes(S.sel)) S.sel = null;
    S.rendered?.(live);
    //: An unchanged block keeps its element and place.
    const fresh = new Map();
    S.cache ||= new Map();
    const rows = layout.map((item) => buildBlock(S, item, 1, edgesFrom, fresh));
    S.cache = fresh;
    S.tree.querySelectorAll(".dgm-target, .dgm-connecting, .dgm-lifted").forEach((b) => b.classList.remove("dgm-target", "dgm-connecting", "dgm-lifted"));
    reconcile(S.tree, rows);
    diagramModel.steps.sync(S, layout.length);
    S.next.classList.toggle("hidden", !layout.length);
    const next = diagramModel.steps.next(S);
    if (S.next.textContent !== next) S.next.textContent = next;
    //: An empty pane is the one stop, so N and G work before there is a block to focus.
    S.pane.tabIndex = layout.length ? -1 : 0;
    const stop = blockEl(S, S.sel) || S.tree.querySelector(".dgm-block");
    stops(S, stop);
    if (had && document.activeElement !== stop) stop?.focus();
    diagramModel.bar.sync(S);
  }

  //: The one tab stop and the selected row; an attribute is written only where it differs.
  function stops(S, stop) {
    for (const b of S.tree.querySelectorAll(".dgm-block")) {
      const index = b === stop ? "0" : "-1";
      if (b.getAttribute("tabindex") !== index) b.tabIndex = Number(index);
      //: Only the picked row's buttons are Tab stops (DD-8).
      for (const c of b.querySelectorAll(":scope > .dgm-card button, :scope > .dgm-joins button")) if (c.getAttribute("tabindex") !== index) c.setAttribute("tabindex", index);
      const on = String(b.dataset.key === S.sel || S.picked?.has(b.dataset.key) === true);
      if (b.getAttribute("aria-selected") !== on) b.setAttribute("aria-selected", on);
    }
  }

  //: Puts `rows` in `parent` in order, moving only what is out of place and removing what is gone.
  function reconcile(parent, rows) {
    const want = new Set(rows);
    for (const child of [...parent.children]) if (!want.has(child)) child.remove();
    rows.forEach((row, i) => {
      if (parent.children[i] !== row) parent.insertBefore(row, parent.children[i] || null);
    });
  }

  const blockKeys = (items) => items.flatMap((x) => (x.type === "k" ? [] : [diagramOps.key(x.type, x.id), ...blockKeys(x.kids || [])]));

  const icon = (cls) => {
    const i = el("i", `ph ${cls}`);
    i.setAttribute("aria-hidden", "true");
    return i;
  };

  function shapeGlyph(shape) {
    const glyph = el("span", "dgm-shape");
    glyph.dataset.shape = shape;
    glyph.setAttribute("aria-hidden", "true");
    return glyph;
  }

  //: The shapes a block can take; `shapeRow` draws each (`setLabel` takes only `ph:` icons).
  function shapeItems(S, key) {
    const id = diagramOps.split(key)[1];
    return diagramOps.SHAPES.map((shape) => ({
      shape,
      on: diagramOps.node(S.m, id).shape === shape,
      run: () => {
        diagramOps.node(S.m, id).shape = shape;
        commit(S, `${nameOf(S, key)} is now a ${SHAPE_LABEL[shape].toLowerCase()}.`);
      },
    }));
  }

  //: One row of the shape menu: the shape drawn where an icon goes.
  function shapeRow({ shape, on, run }) {
    const row = el("button", "menu-item dgm-shape-row");
    row.type = "button";
    row.setAttribute("role", "menuitem");
    if (on) row.setAttribute("aria-current", "true");
    row.append(shapeGlyph(shape), el("span", "menu-item-words", SHAPE_LABEL[shape]));
    if (on) {
      row.append(icon("ph-check dgm-shape-check"));
    }
    row.addEventListener("click", (event) => {
      event.stopPropagation();
      closeActionMenus();
      run();
    });
    return row;
  }

  //: The row's swatch: the shape itself, and a button that opens the shape menu (1613).
  function shapeButton(S, key, shape, text) {
    const button = el("button", "dgm-swatch");
    button.type = "button";
    button.setAttribute("aria-label", `Shape: ${SHAPE_LABEL[shape]}`);
    button.title = `Shape: ${SHAPE_LABEL[shape]}. Press to change it.`;
    button.setAttribute("aria-haspopup", "menu");
    button.append(shapeGlyph(shape));
    button.addEventListener("click", () => {
      select(S, key);
      const r = button.getBoundingClientRect();
      const items = shapeItems(S, key);
      openMenuAtPoint(items.map((item) => ({ label: SHAPE_LABEL[item.shape], run: item.run })), `Shape of ${text}`, r.left, r.bottom, button);
      //: Plain rows, each swapped for the drawn one.
      const menu = document.querySelector(".action-menu:not(.hidden):not(.submenu)");
      menu?.querySelectorAll(":scope > .menu-item").forEach((row, i) => row.replaceWith(shapeRow(items[i])));
      menu?.querySelector(".menu-item")?.focus({ preventScroll: true });
    });
    return button;
  }

  //: A row is rebuilt only when its `sig` changed.
  function buildBlock(S, item, base, edgesFrom, fresh) {
    //: The flow depth (diagram-outline.js) is the level.
    const level = base + (item.depth || 0);
    const id = item.type === "k" ? `k:${item.index}` : diagramOps.key(item.type, item.id);
    const kids = (item.kids || []).map((k) => buildBlock(S, k, level + 1, edgesFrom, fresh));
    const own = item.type === "k" ? item.line : [item.type === "g" ? diagramOps.group(S.m, item.id).title : `${diagramOps.node(S.m, item.id).text}\n${diagramOps.node(S.m, item.id).shape}`, ...(edgesFrom.get(item.id) || []).map(({ e, i }) => `${i}:${titleOf(S, e.from)}>${titleOf(S, e.to)}:${e.label || ""}:${e.style}:${e.arrow}`)].join("\n");
    const sig = `${level}\n${own}\n${kids.map((k) => fresh.get(k.dataset.key).sig).join("|")}`;
    const hit = S.cache.get(id);
    const made = hit && hit.sig === sig ? hit.el : buildRow(S, item, level, edgesFrom, kids);
    fresh.set(id, { sig, el: made });
    return made;
  }

  function buildRow(S, item, level, edgesFrom, built) {
    const block = el("div", "dgm-block");
    if (item.type === "k") {
      block.classList.add("dgm-kept");
      block.dataset.key = `k:${item.index}`;
      block.setAttribute("role", "treeitem");
      block.setAttribute("aria-level", String(level));
      block.setAttribute("aria-label", `Kept line: ${item.line}`);
      block.title = "Blocks cannot edit this line. It stays in the source where it is.";
      const lock = icon("ph-lock-simple dgm-kept-icon");
      block.append(el("div", "dgm-card"));
      block.firstChild.append(lock, el("code", "dgm-label", item.line));
      return block;
    }
    const key = diagramOps.key(item.type, item.id);
    const isGroup = item.type === "g";
    const data = isGroup ? diagramOps.group(S.m, item.id) : diagramOps.node(S.m, item.id);
    const text = isGroup ? data.title : data.text;
    block.dataset.key = key;
    block.setAttribute("role", "treeitem");
    block.setAttribute("aria-level", String(level));
    const joins = edgesFrom.get(item.id) || [];
    if (item.depth) block.dataset.depth = String(item.depth);
    block.setAttribute("aria-label", `${text}, ${isGroup ? "group" : SHAPE_LABEL[data.shape].toLowerCase()}${joins.length ? `, ${joins.length} ${joins.length === 1 ? "connector" : "connectors"}` : ""}`);
    if (isGroup) {
      block.classList.add("dgm-group");
      block.setAttribute("aria-expanded", "true");
    }
    const card = el("div", "dgm-card");
    const grip = el("span", "dgm-grip");
    grip.dataset.objGrip = "";
    grip.title = "Drag to move it, or onto another block to connect it";
    grip.append(icon("ph-dots-six-vertical"));
    const label = el("span", "dgm-label", text);
    label.title = text;
    card.append(grip, isGroup ? groupGlyph() : shapeButton(S, key, data.shape, text), label);
    //: The arrow is on every row, its words on the chosen one.
    const connect = smallButton("ph:arrow-bend-down-right Connect to…", "Draw an arrow from this block to another", (event) => ((S.tapped = event.detail > 0), joinPick(S, key)));
    connect.classList.add("dgm-connect");
    connect.setAttribute("aria-label", `Connect to…, from ${text}`);
    card.append(connect);
    card.append(diagramModel.library.lazyKebab(() => blockItems(S, key), `Menu for ${text}`));
    block.append(card);
    if (joins.length) {
      const row = el("div", "dgm-joins");
      for (const { e, i } of joins) row.append(joinChip(S, e, i));
      block.append(row);
    }
    if (isGroup) {
      const kids = el("div", "dgm-kids");
      kids.setAttribute("role", "group");
      if (built.length) kids.append(...built);
      else kids.append(el("p", "dgm-hole muted", "Drop blocks here"));
      block.append(kids);
    }
    return block;
  }

  function groupGlyph() {
    return icon("ph-stack dgm-group-icon");
  }

  //: A connector row: the words go to the block they point at (joins `go`).
  function joinChip(S, edge, index) {
    const line = el("div", "dgm-joinline");
    const chip = el("button", "dgm-join");
    chip.type = "button";
    const [from, to] = [titleOf(S, edge.from), titleOf(S, edge.to)];
    chip.dataset.style = edge.style;
    chip.append(icon(edge.arrow ? "ph-arrow-right" : "ph-minus"), el("span", "dgm-join-to", to));
    if (edge.label) chip.append(el("span", "dgm-join-label muted", edge.label));
    chip.title = `Go to ${to}`;
    chip.setAttribute("aria-label", `Go to ${to}. Connector from ${from} to ${to}${edge.label ? `, labelled ${edge.label}` : ""}.`);
    chip.addEventListener("click", () => joins(S, "go", { edge: S.m.edges[index] || edge, end: "to" }));
    const more = diagramModel.library.lazyKebab(() => joins(S, "items", S.m.edges[index] || edge), "Change this connector", { anchor: line });
    line.append(chip, more);
    return line;
  }

  // --- menus ----------------------------------------------------------------------
  function blockItems(S, key) {
    const [type] = diagramOps.split(key);
    const isNode = type === "n";
    const items = [
      { label: "ph:pencil-simple Rename", run: () => relabel(S, key), group: "edit" },
      { label: "ph:arrow-bend-down-right Connect to…", run: () => joinPick(S, key), group: "edit" },
      ...(isNode ? [{ label: "ph:palette Colour…", run: () => styleDo(S, "colour", key), group: "edit" }, { label: "ph:stack Box this block", run: () => diagramModel.outline.box(S, helpers, key), group: "edit" }] : []),
      { label: isNode ? "ph:plus Add block after" : "ph:plus Add block inside", run: () => addBlock(S, { after: isNode ? key : null, into: isNode ? null : key }), group: "edit" },
    ];
    if (isNode) {
      const n = diagramOps.node(S.m, diagramOps.split(key)[1]);
      items.push({ label: n.md ? "ph:text-aa Plain text" : "ph:text-b Markdown text", run: () => ((n.md = !n.md), n.md || delete n.md, commit(S, `${n.text} is now ${n.md ? "markdown text: **bold**, *italic*" : "plain text"}.`)), group: "edit" });
      items.push({
        label: "ph:diamond Shape",
        items: shapeItems(S, key).map(shapeRow),
        group: "edit",
      });
    }
    if (!isNode) {
      const g = diagramOps.group(S.m, diagramOps.split(key)[1]);
      const turn = (dir) => () => (dir ? (g.dir = dir) : delete g.dir, commit(S, dir ? `${g.title} flows ${DIRS.find(([d]) => d === dir)[2].toLowerCase()}.` : `${g.title} follows the diagram's direction.`));
      items.push({ label: "ph:arrows-out-line-horizontal Direction", items: [...DIRS.map(([d, icon, name]) => ({ label: `${icon} ${name}`, run: turn(d) })), { label: "Same as the diagram", run: turn("") }], group: "edit" });
    }
    items.push(
      { label: "ph:arrow-up Move up", run: () => stepBlock(S, key, -1), group: "move" },
      { label: "ph:arrow-down Move down", run: () => stepBlock(S, key, 1), group: "move" },
      { label: "ph:arrow-line-right Nest into the group above", run: () => nestBlock(S, key, true), group: "move" },
      { label: "ph:arrow-line-left Lift out of its group", run: () => nestBlock(S, key, false), group: "move" },
      { label: isNode ? "ph:trash Delete" : "ph:trash Delete group", danger: true, run: () => removeBlock(S, key), group: "end" }
    );
    return items;
  }

  // --- gestures -------------------------------------------------------------------
  function select(S, key, focus = false) {
    S.sel = key;
    S.picked?.clear();
    stops(S, blockEl(S, key));
    if (focus) {
      const b = blockEl(S, key);
      b?.focus();
      b?.scrollIntoView({ block: "nearest" });
    }
  }

  //: A shape, or a group, added after the block `after`, inside the group `into`,
  //: or (neither) after the selection. `edit` opens its label for typing.
  //: `from` is a block id to connect to the new one, in the same change.
  function addBlock(S, { shape = S.shape, group = false, after = S.sel, into = null, before = undefined, edit = true, text = SHAPE_TEXT[shape], from = undefined, label = "" } = {}) {
    const m = S.m;
    const sel = after && !into ? after : null;
    const parent = into ? diagramOps.split(into)[1] : sel ? diagramOps.parentOf(m, sel) : null;
    const next = sel ? diagramOps.sisters(m, sel) : null;
    const sisters = next ? next.keys.filter((k) => k[0] === (group ? "g" : "n")) : [];
    const ahead = before !== undefined ? before : sel && sisters.includes(sel) ? sisters[sisters.indexOf(sel) + 1] || null : null;
    //: Joined after the picked (or last) block; a drop, a group or an explicit `from` is left as it is.
    if (from === undefined) from = !group && !into && before === undefined ? diagramModel.outline.tail(m, sel) : null;
    const id = group ? diagramOps.addGroup(m, { parent, before: ahead }) : diagramOps.addNode(m, { shape, text, group: parent, before: ahead });
    if (!id) return say(S, group ? "That group cannot be added." : `A diagram holds at most ${diagramOps.MAX} blocks.`);
    if (!group) S.shape = shape;
    const key = diagramOps.key(group ? "g" : "n", id);
    S.sel = key;
    if (from) diagramOps.join(m, from, id, { label });
    commit(S, `Added ${group ? "a group" : `a ${SHAPE_LABEL[shape].toLowerCase()}`}${sel ? ` after ${nameOf(S, sel)}` : ""}${from ? ` and connected ${titleOf(S, from)} to it` : ""}.`);
    //: List folded: named over the picture (1661 m, edges.js `askNode`).
    const name = () => edit && (!group && S.pane.offsetParent === null ? nameOnPicture(S, id) : relabel(S, key));
    //: After a decision the arrow's words are asked first (R12), then the name.
    const edge = from && !group && edit && m.edges.find((e) => e.from === from && e.to === id);
    edge && diagramOps.needsLabel(m, edge) ? joins(S, "ask", edge).then(name) : name();
    return key;
  }

  function nameOnPicture(S, id) {
    S.askNode?.(id);
  }

  function relabel(S, key) {
    const b = blockEl(S, key);
    if (!b || key[0] === "k") return;
    const label = b.querySelector(":scope > .dgm-card > .dgm-label");
    beginEdit(S, label, nameOf(S, key), (text, was) => {
      //: An empty name is refused; an unchanged row gets the old name back by hand.
      if (!diagramOps.relabel(S.m, key, text)) return (label.textContent = nameOf(S, key)), render(S);
      if (text === nameOf(S, key) && S.source === diagramModel.print(S.m)) return render(S);
      commit(S, `Renamed to ${text}.`);
      diagramModel.picture.patch(S, key, was, text);
    }, key);
  }

  //: A label in place (the `wbBeginTextEdit` pattern): Enter commits, Escape puts it back.
  function beginEdit(S, target, was, done, key = null) {
    if (!target || target.isContentEditable) return;
    target.setAttribute("contenteditable", "plaintext-only");
    target.classList.add("dgm-editing");
    target.focus();
    const range = document.createRange();
    range.selectNodeContents(target);
    const sel = window.getSelection();
    sel.removeAllRanges();
    sel.addRange(range);
    let over = false;
    const end = (keep, to) => {
      if (over) return;
      over = true;
      target.removeEventListener("keydown", onKey);
      target.removeEventListener("blur", onBlur);
      const text = target.textContent.trim();
      target.removeAttribute("contenteditable");
      target.classList.remove("dgm-editing");
      if (keep && text !== was) done(text, was);
      else target.textContent = was;
      //: Not when the render put focus there or the press went to another field.
      const block = key && blockEl(S, key);
      if (block && !to && document.activeElement !== block) block.focus();
    };
    const onKey = (event) => {
      if (event.key !== "Enter" && event.key !== "Escape") return;
      event.preventDefault();
      event.stopPropagation();
      end(event.key === "Enter");
    };
    const onBlur = (event) => end(true, event.relatedTarget);
    target.addEventListener("keydown", onKey);
    target.addEventListener("blur", onBlur);
  }

  const stepBlock = (S, key, dir) => key[0] !== "k" && diagramModel.outline.move(S, helpers, key, dir);

  function nestBlock(S, key, into) {
    if (key[0] === "k") return;
    const ok = into ? diagramOps.nest(S.m, key) : diagramOps.lift(S.m, key);
    if (!ok) return say(S, into ? "There is no group just above to nest into." : `${nameOf(S, key)} is not inside a group.`);
    const parent = diagramOps.parentOf(S.m, key);
    commit(S, into ? `Nested ${nameOf(S, key)} into ${nameOf(S, diagramOps.key("g", parent))}.` : `Lifted ${nameOf(S, key)} out.`);
  }

  function removeBlock(S, key) {
    if (key[0] === "k") return;
    const sis = diagramOps.sisters(S.m, key);
    const near = sis && (sis.keys[sis.keys.indexOf(key) + 1] || sis.keys[sis.keys.indexOf(key) - 1] || (sis.parent ? diagramOps.key("g", sis.parent) : null));
    const name = nameOf(S, key);
    const gone = diagramOps.remove(S.m, key);
    if (!gone) return;
    S.sel = near && near !== key ? near : null;
    const extra = [gone.joins ? `${gone.joins} ${gone.joins === 1 ? "join" : "joins"}` : "", gone.lifted ? `${gone.lifted} ${gone.lifted === 1 ? "block" : "blocks"} stayed` : ""].filter(Boolean);
    commit(S, `Deleted ${name}${extra.length ? ` with ${extra.join(", ")}` : ""}.`);
  }


  // --- keyboard -------------------------------------------------------------------
  function onKey(S, event) {
    const block = event.target.closest?.(".dgm-block");
    if (event.target.isContentEditable || !block || event.target.closest(".menu-wrap, .dgm-join, .dgm-connect, .dgm-swatch")) return;
    const key = block.dataset.key;
    const all = [...S.tree.querySelectorAll(".dgm-block")];
    const at = all.indexOf(block);
    const go = (target) => target && select(S, target.dataset.key, true);
    const mod = event.ctrlKey || event.metaKey;
    if (mod && !event.altKey && /^[zy]$/i.test(event.key)) {
      event.preventDefault();
      //: Not passed on: the app's Ctrl+Z would undo a second step.
      event.stopPropagation();
      return event.shiftKey || /y/i.test(event.key) ? S.io.redo() : S.io.undo();
    }
    if (event.altKey && !mod) {
      const act = { ArrowUp: () => stepBlock(S, key, -1), ArrowDown: () => stepBlock(S, key, 1), ArrowRight: () => nestBlock(S, key, true), ArrowLeft: () => nestBlock(S, key, false) }[event.key];
      if (!act) return;
      event.preventDefault();
      event.stopPropagation();
      return act();
    }
    if (mod) return;
    if (diagramModel.bar.chain(event, S, key, block, addBlock)) return;
    const low = event.key.length === 1 ? event.key.toLowerCase() : event.key;
    //: 1 to 9 add a shape, Shift+N the last one used (diagram-bar.js, 1661 D2).
    const picked = diagramModel.bar.key(event);
    if (picked && event.key !== "N") {
      event.preventDefault();
      return addBlock(S, { after: key, ...picked });
    }
    const plain = {
      ArrowDown: () => go(all[at + 1]), ArrowUp: () => go(all[at - 1]), Home: () => go(all[0]), End: () => go(all.at(-1)),
      ArrowLeft: () => go(block.parentElement.closest(".dgm-block")), ArrowRight: () => go(block.querySelector(".dgm-block")),
      Enter: () => relabel(S, key), F2: () => relabel(S, key),
      Insert: () => addBlock(S, { after: key, shape: "rect" }), n: () => addBlock(S, { after: key, ...(diagramModel.bar.key(event) || { shape: "rect" }) }),
      g: () => addBlock(S, { after: key, group: true }),
      k: () => key[0] === "n" && styleDo(S, "colour", key), "?": () => styleDo(S, "shortcuts"),
      c: () => key[0] !== "k" && joinPick(S, key), j: () => key[0] !== "k" && joinPick(S, key),
      Delete: () => removeBlock(S, key), Backspace: () => removeBlock(S, key),
      ContextMenu: () => menuAt(S, block), F10: () => event.shiftKey && menuAt(S, block),
    }[low];
    if (!plain || (event.shiftKey && event.key.length > 1 && event.key !== "F10")) return;
    event.preventDefault();
    plain();
  }

  function menuAt(S, block) {
    if (block.dataset.key[0] === "k") return;
    const r = block.querySelector(".dgm-card").getBoundingClientRect();
    openMenuAtPoint(blockItems(S, block.dataset.key), "Block menu", r.left + r.width / 2, r.bottom, block);
  }

  // --- suggestions (diagram-suggest.js, lazy) ---------------------------------------
  //: Templates, From my notes and Describe it. What comes back lands as blocks (D8): on an
  //: empty diagram it becomes the diagram, otherwise it arrives as ghosts to take or drop.
  const helpers = { label: SHAPE_LABEL, el, say, commit, blockEl, stops, suggest, add: addBlock, panes, name: nameOf, items: blockItems, select };
  async function suggest(S, how) {
    if (!(await ensureModule("diagramSuggest"))) return say(S, "The suggestions did not load.");
    return diagramModel.suggest[how](S, helpers);
  }

  //: The connector menu and the connect picker (diagram-joins.js, lazy).
  async function joins(S, how, arg) {
    if (!(await ensureModule("diagramJoins"))) return void say(S, "Connectors did not load.");
    return diagramModel.joins[how](S, arg, helpers);
  }
  const joinPick = (S, key) => joins(S, "pick", key);
  //: Colour and the shortcuts sheet (diagram-style.js, lazy, 1661 B).
  async function styleDo(S, how, key) {
    if (!(await ensureModule("diagramStyle"))) return void say(S, "That did not load.");
    return diagramModel.style[how](S, helpers, key);
  }

  //: The Suggest button's menu is made by the lazy file, so it is fetched on the press.
  async function suggestMenu(S, button) {
    if (!(await ensureModule("diagramSuggest"))) return say(S, "The suggestions did not load.");
    const r = button.getBoundingClientRect();
    openMenuAtPoint(diagramModel.suggest.items(S, helpers), "Suggest a diagram", r.left, r.bottom, button);
  }

  // --- building the pane ----------------------------------------------------------
  //: The ... menu (1546 D7): what the host adds (`io.menu`, the dialog's Turn into shapes), then the
  //: exports. They run from diagram-embed.js, fetched on the first press.
  function more(S) {
    const rows = [["ph:file-svg Save as SVG", "svg"], ["ph:file-png Save as PNG", "png"], ["ph:image Copy as picture", "picture"], ["ph:copy Copy as Mermaid", "mermaid"], ["ph:code Copy as SVG", "svgtext"]];
    //: Suggest folds in here on a phone; at 480 px or less Direction, Redo and Ask too (diagram-kindbar.js, L-documents-7).
    const { rows: fold, key } = diagramModel.kindbar.fold(S, DIRS, suggestMenu);
    const mine = S.io.menu || [];
    const menu = kebabMenu([...mine, ...fold, makeMenuItem("ph:keyboard Keyboard shortcuts", "", () => styleDo(S, "shortcuts")), ...rows.map(([label, how]) => makeMenuItem(label, "", () => ensureModule("diagramEmbed").then((ok) => ok && diagramModel.embed.out(how, S.source, S.io.name))))], "More for this diagram");
    menu.classList.add("dgm-more");
    menu.dataset.rows = key;
    return menu;
  }

  //: The host's rows can depend on the diagram: after a redraw that changes them the menu is rebuilt.
  function refreshMore(S) {
    const old = S.root.querySelector(".dgm-more");
    if (!old || old.dataset.rows === diagramModel.kindbar.fold(S, DIRS).key) return;
    const next = more(S);
    next.querySelector("button").tabIndex = old.querySelector("button").tabIndex;
    old.replaceWith(next);
  }

  //: The toolbar is diagram-bar.js (lazy, 1661 D2): one row, built from these.
  const buildPalette = (S) => diagramModel.bar.build(S, { ...helpers, DIRS, label: SHAPE_LABEL, glyph: shapeGlyph, groupGlyph, smallButton, more, commit, suggestMenu });

  function mount(host, io, text) {
    host.replaceChildren();
    const root = el("div", "dgm");
    const S = { host, root, io, source: text, m: null, sel: null, shape: "rect", drawn: 0, hit: null, tidy: false };
    S.live = el("p", "visually-hidden dgm-live");
    S.live.setAttribute("role", "status");
    S.live.setAttribute("aria-live", "polite");
    S.tree = el("div", "dgm-tree");
    S.tree.setAttribute("role", "tree");
    S.tree.setAttribute("aria-label", "Diagram blocks");
    //: The empty state recipe: one sentence and one action, the filled button.
    S.empty = el("div", "empty-state dgm-empty");
    const start = smallButton("ph:layout Start from a template", "Pick a starting flowchart", () => suggest(S, "templates"), false);
    start.classList.add("accent");
    //: The walkthrough (diagram-steps.js).
    S.empty.append(diagramModel.steps.build(S, { el, commit, add: addBlock, rename: relabel, connect: joinPick }), start);
    S.ghosts = el("div", "dgm-ghosts hidden");
    S.drop = el("div", "dgm-drop hidden");
    S.pane = el("div", "dgm-pane");
    S.pane.setAttribute("aria-label", "Diagram blocks. Press N for a block or G for a group.");
    S.pane.setAttribute("role", "region");
    //: The next step, one line under the list.
    S.next = el("p", "muted dgm-next");
    S.pane.append(S.tree, S.next, S.empty, S.ghosts, S.drop);
    diagramModel.steps.frame(S, { add: addBlock, connect: joinPick });
    S.fig = el("figure", "dgm-picture");
    const body = el("div", "dgm-body");
    body.append(S.pane, S.fig);
    S.note = el("p", "muted dgm-hint hidden", "");
    root.append(buildPalette(S), S.note, body, S.live);
    host.append(root);
    panes.set(root, S);
    S.tree.addEventListener("keydown", (event) => onKey(S, event));
    root.addEventListener("keydown", (event) => diagramModel.kindbar.historyKey(S, event));
    root.addEventListener("keydown", (event) => diagramModel.bar.rootKey(S, event, { add: addBlock, style: styleDo }));
    S.tree.addEventListener("click", (event) => {
      const block = event.target.closest(".dgm-block");
      if (block && !event.target.closest(".menu-wrap, .dgm-join, .dgm-connect, .dgm-swatch")) select(S, block.dataset.key);
    });
    S.tree.addEventListener("dblclick", (event) => {
      const label = event.target.closest(".dgm-label");
      const block = label?.closest(".dgm-block");
      if (block && block.dataset.key[0] !== "k") relabel(S, block.dataset.key);
    });
    S.tree.addEventListener("contextmenu", (event) => {
      const block = event.target.closest(".dgm-block");
      if (!block || block.dataset.key[0] === "k") return;
      event.preventDefault();
      openMenuAtPoint(blockItems(S, block.dataset.key), "Block menu", event.clientX, event.clientY, block);
    });
    wireLongPress(S.tree, (event, point) => {
      const block = event.target.closest?.(".dgm-block");
      if (block && block.dataset.key[0] !== "k") openMenuAtPoint(blockItems(S, block.dataset.key), "Block menu", point.x, point.y, block);
    });
    S.fig.addEventListener("click", (event) => {
      const id = diagramModel.picture.pick(S, event);
      if (!id || !diagramOps.node(S.m, id)) return;
      const key = diagramOps.key("n", id);
      if ((event.shiftKey || event.ctrlKey || event.metaKey) && S.pickAt) return S.pickAt(key);
      select(S, key, true);
    });
    S.pane.addEventListener("keydown", (event) => {
      if (event.target !== S.pane || !/^[nNgG]$|^Insert$/.test(event.key)) return;
      event.preventDefault();
      addBlock(S, { after: null, group: /^[gG]$/.test(event.key), shape: "rect" });
    });
    sync(host, text, S);
    return S;
  }

  //: Reads the source into the model. Another kind of diagram, or a source the
  //: reader cannot take, is shown as its picture alone with one line saying why.
  function sync(host, text, S = panes.get(host.querySelector(".dgm"))) {
    if (!S) return null;
    S.source = text;
    //: More than `diagramOps.MAX` blocks: the picture and a line.
    const read = diagramModel.parse(text);
    const big = Boolean(read && read.nodes.length > diagramOps.MAX);
    const parsed = big ? null : read;
    S.tidy = Boolean(parsed && text.trim() && diagramModel.print(parsed) !== text);
    S.plain = !parsed;
    S.root.classList.toggle("dgm-plain", !parsed);
    S.note.classList.toggle("hidden", Boolean(parsed));
    const named = diagramOps.PLAIN.find(([re]) => re.test(diagramModel.front(text.replace(/\r/g, "")).rest.trim().split(/\s/, 1)[0] || ""));
    S.note.textContent = parsed ? "" : big ? `This diagram has more than ${diagramOps.MAX} blocks, so it opens in Source with its picture.` : named ? `Blocks do not draw ${named[1]} yet, so it opens in Source with its picture.` : "Blocks draw flowcharts, mind maps, timelines and sequence diagrams, so this one opens in Source with its picture.";
    S.m = parsed || { kind: "flowchart", dir: "TD", nodes: [], edges: [], subgraphs: [], kept: [], front: [] };
    if (!parsed) S.ghosts.replaceChildren(), S.ghosts.classList.add("hidden");
    S.pane.classList.toggle("hidden", !parsed);
    render(S);
    drawPicture(S);
    return S;
  }

  //: What documents.js calls: the pane in `host` for this source, mounted once,
  //: then only told the source when it changed from outside (a typed edit, an undo).
  //: A mind map, a timeline or a sequence diagram is the lazy diagram-kinds.js's pane (1546 P4); the
  //: flowchart path above never reads it. Any other text is a flowchart's, or a picture alone.
  function kindOf(text) {
    const first = diagramModel.front(String(text || "").replace(/\r/g, "")).rest.split("\n").map((l) => l.trim()).find((l) => l && !l.startsWith("%%"));
    const hit = /^(mindmap|timeline|sequenceDiagram)\b/i.exec(first || "");
    return hit ? hit[1].toLowerCase().replace("diagram", "") : "flowchart";
  }
  //: What the kinds' panes borrow: the same DOM helpers, so the two read as one pane.
  const kit = { el, more, say, commit, drawPicture, beginEdit, blockEl, select, suggest, suggestMenu, reconcile, stops };
  //: A line a suggestion left for the pane that opens next (the kind changed under it).
  let told = "";

  async function show(host, io, text) {
    //: The renderer and the toolbar fetch with the first batch.
    const kind = kindOf(text);
    ensureModule("mermaid");
    const early = Promise.all([ensureModule("diagramKindbar"), ...(kind === "flowchart" ? [ensureModule("diagramBar"), ensureModule("diagramSteps"), ensureModule("diagramOutline")] : [])]);
    await Promise.all(["/css/objmove-lazy.css", "/js/obj-ref.js", "/js/obj-drag.js", "/js/diagram-picture.js", "/js/diagram-library.js", "/js/diagram-pointer.js", "/js/diagram-ops.js"].map((file) => lazyScript(file)));
    diagramOps = helpers.ops = diagramModel.ops;
    Object.assign(SHAPE_LABEL, diagramOps.LABEL);
    Object.assign(SHAPE_TEXT, diagramOps.TEXT);
    if (typeof OBJ_MODES === "object" && !OBJ_MODES.diagram) OBJ_MODES.diagram = diagramModel.pointer.make(helpers);
    kit.dropMark ||= diagramModel.pointer.dropMark;
    if (!(await early).every(Boolean) && kind === "flowchart") return host.replaceChildren(el("p", "muted", "The block editor did not load. Source still works."));
    let S;
    if (kind !== "flowchart") {
      if (!(await ensureModule("diagramKinds"))) return host.replaceChildren(el("p", "muted", "The block editor for this kind did not load. Source still works."));
      S = diagramModel.kinds.show(host, io, text, kind, kit);
    } else {
      S = panes.get(host.querySelector(":scope > .dgm"));
      if (!S) S = mount(host, io, text);
      else {
        S.io = io;
        if (text !== S.source) sync(host, text, S);
      }
    }
    if (S && (await ensureModule("diagramAi"))) diagramModel.ai.wire(S, helpers);
    if (S) refreshMore(S);
    //: A diagram page (its io has a key; the dialog's has none) gets Export in its head.
    if (S && io.key && (await ensureModule("diagramEmbed"))) diagramModel.embed.headExport();
    //: The phone's palette sheet and pinch (diagram-touch.js).
    if (S && (S.k || matchMedia(COMPACT).matches) && (await ensureModule("diagramTouch"))) diagramModel.touch.wire(S);
    //: Zoom, pan and fit for the picture, in every window (diagram-view.js, 1614).
    if (S && ((await ensureModule("vf")) && (await ensureModule("diagramView")))) diagramModel.view.wire(S);
    //: The shelf of blocks on the picture, once it has its stage (diagram-library.js).
    if (S && S.fig.parentElement?.classList.contains("dgm-stage")) diagramModel.library.shelf(S, { ...helpers, glyph: shapeGlyph, groupGlyph });
    //: The other kinds are edited on their picture too (1661 l): their parts become the overlay's boxes first.
    if (S?.k && (await lazyScript("/js/diagram-seq-canvas.js"))) await diagramModel.seqCanvas?.wire(S);
    if (S && (!S.k || S.hitAt) && (await ensureModule("diagramOverlay"))) diagramModel.overlay.wire(S);
    if (S && !S.k && (await ensureModule("diagramMulti"))) diagramModel.multi.wire(S, helpers);
    if (S && !S.k && (await ensureModule("diagramCanvas"))) diagramModel.canvas.wire(S, helpers);
    if (S && !S.k && (await ensureModule("diagramEdges"))) diagramModel.edges.wire(S, helpers);
    if (S && !S.k && (await ensureModule("diagramEdgePick"))) diagramModel.edgepick.wire(S, helpers);
    //: The divider between the blocks and the picture (diagram-split.js, 1615 e).
    if (S && (await ensureModule("diagramSplit"))) diagramModel.split.wire(S);
    if (S && (await ensureModule("diagramLetGo"))) diagramModel.letgo.wire(S, helpers);
    if (told && S) say(S, told);
    told = "";
    return S;
  }

  diagramModel.builder = { show, kindOf, select, styleDo, tell: (text) => (told = text) };
})();
