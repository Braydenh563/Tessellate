// diagram-builder.js: the block pane of a diagram (1546 P2, DOCUMENTS_PLAN
// "1546 design" D5 to D10). Lazy: `LAZY_MODULES.diagramBuilder`, registered at
// the foot of documents-mermaid.js, so nothing of it is in the boot scripts.
//
// A diagram is edited as blocks, never as text first: an Add library of shapes and a
// group, a tree of cards (a node is a card, a group is a card holding cards),
// the connectors as rows under the card they leave, and the live picture beside
// it. Every gesture is one change to the model (`diagramModel`, documents-
// mermaid.js) printed to the whole source and handed to `io.set`, so the
// source is the only state and the document's own history is the undo.
// The pure part is diagram-ops.js (node-tested, tests/test_diagram_builder.py),
// the Add library is diagram-library.js and the drag mode diagram-pointer.js
// (1594: all three come with `show`, so this file stays under its size target);
// the rest is the DOM, made with createElement and textContent.
//
// One closure, one export: `diagramModel.builder` (no new global name).
(() => {
  //: The pure half (diagram-ops.js, fetched with this file): keys name blocks, every change is one call, none draws.
  let diagramOps;

  // ---------------------------------------------------------------------------
  // The pane
  // ---------------------------------------------------------------------------
  const SHAPE_LABEL = { rect: "Box", round: "Rounded", stadium: "Pill", circle: "Circle", diamond: "Decision", hexagon: "Hexagon" };
  const SHAPE_TEXT = { rect: "Step", round: "Step", stadium: "Start", circle: "Event", diamond: "Question?", hexagon: "Prepare" };
  //: A narrow window or a touch screen: the phone's palette sheet, direction in the ... menu and the picture's pinch.
  const COMPACT = "(max-width: 599.98px), (pointer: coarse)";
  const DIRS = [["TD", "down", "Top to bottom"], ["LR", "right", "Left to right"], ["BT", "up", "Bottom to top"], ["RL", "left", "Right to left"]];
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
    S.drawTimer = setTimeout(() => {
      const source = S.source;
      const stamp = ++S.drawn;
      //: A kind the blocks cannot read (S.plain) still has its picture. Empty is a source with no block and nothing but
      //: its header: a kept line the reader could not place is still drawn, so the picture says why it cannot (INBOX 1596 b).
      const blank = S.k ? S.k.blank(S.m) : S.m && !S.m.nodes.length;
      const bare = diagramModel.front(source.replace(/\r/g, "")).rest.split("\n").every((l) => !l.trim() || /^\s*(%%|flowchart\b|graph\b|mindmap\b|timeline\b|sequenceDiagram\b)/i.test(l));
      const empty = !source.trim() || (!S.plain && blank && bare);
      S.fig.classList.toggle("dgm-picture-empty", empty);
      if (empty) return S.fig.replaceChildren(el("p", "muted dgm-hint", "The picture appears here as you add blocks."));
      ensureModule("mermaid").then((ok) => {
        if (!ok || stamp !== S.drawn) return;
        const began = performance.now();
        mermaidFill(S.fig, source, (result) => {
          //: A big diagram takes long to draw, so the next change waits half that long: edits in a row draw once.
          S.drawWait = Math.min(600, Math.max(120, (performance.now() - began) / 2));
          if (stamp !== S.drawn) return;
          S.hit = result.svg ? diagramModel.picture.boxes(result.svg) : null;
          S.fig.onpaint?.();
          if (result.svg) return;
          S.fig.classList.remove("md-mermaid-pending");
          S.fig.replaceChildren(mermaidFailure.note(result.error, source));
        });
      });
    }, S.drawWait || 120);
  }

  // --- the tree -------------------------------------------------------------------
  function render(S) {
    const had = S.tree.contains(document.activeElement);
    const layout = diagramOps.layout(S.m);
    const edgesFrom = new Map();
    S.m.edges.forEach((e, i) => edgesFrom.set(e.from, [...(edgesFrom.get(e.from) || []), { e, i }]));
    if (S.sel && !blockKeys(layout).includes(S.sel)) S.sel = null;
    //: A block whose words, shape and connectors are unchanged keeps its element, and the tree keeps what it already
    //: holds in place (`reconcile`), so a change lays out only the rows it touched.
    const fresh = new Map();
    S.cache ||= new Map();
    const rows = layout.map((item) => buildBlock(S, item, 1, edgesFrom, fresh));
    S.cache = fresh;
    S.tree.querySelectorAll(".dgm-target, .dgm-connecting, .dgm-lifted").forEach((b) => b.classList.remove("dgm-target", "dgm-connecting", "dgm-lifted"));
    reconcile(S.tree, rows);
    S.empty.classList.toggle("hidden", Boolean(layout.length));
    S.next.classList.toggle("hidden", !layout.length);
    const next = S.m.nodes.length < 2 ? "Add a second block, then press Connect to… on one to draw an arrow." : S.m.edges.length ? "Drag a grip to move or nest a block. Double-click a name to rename it." : "Press Connect to… on a block, or drag its grip onto another block, to draw an arrow.";
    if (S.next.textContent !== next) S.next.textContent = next;
    //: An empty pane is the one stop, so N and G work before there is a block to focus.
    S.pane.tabIndex = layout.length ? -1 : 0;
    const stop = blockEl(S, S.sel) || S.tree.querySelector(".dgm-block");
    stops(S, stop);
    if (had && document.activeElement !== stop) stop?.focus();
    for (const b of S.dirs.querySelectorAll("button")) {
      b.classList.toggle("active", b.dataset.dir === S.m.dir);
      b.setAttribute("aria-pressed", String(b.dataset.dir === S.m.dir));
    }
  }

  //: The one tab stop and the selected row: an attribute is written only where it differs, so a long list is not restyled.
  function stops(S, stop) {
    for (const b of S.tree.querySelectorAll(".dgm-block")) {
      const index = b === stop ? "0" : "-1";
      if (b.getAttribute("tabindex") !== index) b.tabIndex = Number(index);
      const on = String(b.dataset.key === S.sel);
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

  function shapeGlyph(shape) {
    const glyph = el("span", "dgm-shape");
    glyph.dataset.shape = shape;
    glyph.setAttribute("aria-hidden", "true");
    return glyph;
  }

  //: A row is rebuilt only when its `sig` (everything below that it reads) changed since the last render.
  function buildBlock(S, item, level, edgesFrom, fresh) {
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
      const lock = el("i", "ph ph-lock-simple dgm-kept-icon");
      lock.setAttribute("aria-hidden", "true");
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
    block.setAttribute("aria-label", `${text}, ${isGroup ? "group" : SHAPE_LABEL[data.shape].toLowerCase()}${joins.length ? `, ${joins.length} ${joins.length === 1 ? "connector" : "connectors"}` : ""}`);
    if (isGroup) {
      block.classList.add("dgm-group");
      block.setAttribute("aria-expanded", "true");
    }
    const card = el("div", "dgm-card");
    const grip = el("span", "dgm-grip");
    grip.dataset.objGrip = "";
    grip.title = "Drag to move it, or onto another block to connect it";
    const dots = el("i", "ph ph-dots-six-vertical");
    dots.setAttribute("aria-hidden", "true");
    grip.append(dots);
    const label = el("span", "dgm-label", text);
    card.append(grip, isGroup ? groupGlyph() : shapeGlyph(data.shape), label);
    //: Connecting is one act on every row; the words show on the chosen row, the arrow is always there.
    const connect = smallButton("ph:arrow-bend-down-right Connect to…", "Draw an arrow from this block to another", () => joinPick(S, key));
    connect.classList.add("dgm-connect");
    connect.setAttribute("aria-label", `Connect to…, from ${text}`);
    card.append(connect);
    const menu = kebabMenu(blockItems(S, key), `Menu for ${text}`);
    menu.classList.add("dgm-menu");
    card.append(menu);
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
    const icon = el("i", "ph ph-stack dgm-group-icon");
    icon.setAttribute("aria-hidden", "true");
    return icon;
  }

  //: A connector reads as what it is, "Start to Next" and its label, in a row that hangs off the block it leaves.
  function joinChip(S, edge, index) {
    const chip = el("button", "dgm-join");
    chip.type = "button";
    const [from, to] = [titleOf(S, edge.from), titleOf(S, edge.to)];
    const arrow = el("i", `ph ${edge.arrow ? "ph-arrow-right" : "ph-minus"}`);
    arrow.setAttribute("aria-hidden", "true");
    chip.dataset.style = edge.style;
    chip.append(arrow, el("span", "dgm-join-to", `${from} to ${to}`));
    if (edge.label) chip.append(el("span", "dgm-join-label muted", edge.label));
    chip.title = "Change this connector: its line, its label, or remove it";
    chip.setAttribute("aria-label", `Connector from ${from} to ${to}${edge.label ? `, labelled ${edge.label}` : ""}. Opens its menu.`);
    chip.addEventListener("click", async () => {
      const r = chip.getBoundingClientRect();
      //: The row is kept across changes, so the connector is read from the model when pressed, not when drawn.
      const rows = await joins(S, "items", S.m.edges[index] || edge);
      if (rows) openMenuAtPoint(rows, "This connector", r.left, r.bottom, chip);
    });
    return chip;
  }

  // --- menus ----------------------------------------------------------------------
  function blockItems(S, key) {
    const [type] = diagramOps.split(key);
    const isNode = type === "n";
    const items = [
      { label: "ph:pencil-simple Rename", run: () => relabel(S, key), group: "edit" },
      { label: "ph:arrow-bend-down-right Connect to…", run: () => joinPick(S, key), group: "edit" },
      { label: isNode ? "ph:plus Add block after" : "ph:plus Add block inside", run: () => addBlock(S, { after: isNode ? key : null, into: isNode ? null : key }), group: "edit" },
    ];
    if (isNode) {
      items.push({
        label: "ph:diamond Shape",
        items: diagramOps.SHAPES.map((shape) => ({
          label: `${diagramOps.node(S.m, diagramOps.split(key)[1]).shape === shape ? "ph:check" : "ph:square"} ${SHAPE_LABEL[shape]}`,
          run: () => {
            diagramOps.node(S.m, diagramOps.split(key)[1]).shape = shape;
            commit(S, `${nameOf(S, key)} is now a ${SHAPE_LABEL[shape].toLowerCase()}.`);
          },
        })),
        group: "edit",
      });
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
    stops(S, blockEl(S, key));
    if (focus) {
      const b = blockEl(S, key);
      b?.focus();
      b?.scrollIntoView({ block: "nearest" });
    }
  }

  //: A shape, or a group, added after the block `after`, inside the group `into`,
  //: or (neither) after the selection. `edit` opens its label for typing.
  //: `from` is a block id to connect to the new one, in the same change (Connect to…, A new block).
  function addBlock(S, { shape = S.shape, group = false, after = S.sel, into = null, before = undefined, edit = true, text = SHAPE_TEXT[shape], from = null } = {}) {
    const m = S.m;
    const sel = after && !into ? after : null;
    const parent = into ? diagramOps.split(into)[1] : sel ? diagramOps.parentOf(m, sel) : null;
    const next = sel ? diagramOps.sisters(m, sel) : null;
    const sisters = next ? next.keys.filter((k) => k[0] === (group ? "g" : "n")) : [];
    const ahead = before !== undefined ? before : sel && sisters.includes(sel) ? sisters[sisters.indexOf(sel) + 1] || null : null;
    const id = group ? diagramOps.addGroup(m, { parent, before: ahead }) : diagramOps.addNode(m, { shape, text, group: parent, before: ahead });
    if (!id) return say(S, group ? "That group cannot be added." : `A diagram holds at most ${diagramOps.MAX} blocks.`);
    if (!group) S.shape = shape;
    const key = diagramOps.key(group ? "g" : "n", id);
    S.sel = key;
    if (from) diagramOps.join(m, from, id);
    commit(S, `Added ${group ? "a group" : `a ${SHAPE_LABEL[shape].toLowerCase()}`}${sel ? ` after ${nameOf(S, sel)}` : ""}${from ? ` and connected ${titleOf(S, from)} to it` : ""}.`);
    if (edit) relabel(S, key);
    return key;
  }

  function relabel(S, key) {
    const b = blockEl(S, key);
    if (!b || key[0] === "k") return;
    const label = b.querySelector(":scope > .dgm-card > .dgm-label");
    beginEdit(S, label, nameOf(S, key), (text) => {
      if (!diagramOps.relabel(S.m, key, text)) return;
      if (text === nameOf(S, key) && S.source === diagramModel.print(S.m)) return render(S);
      commit(S, `Renamed to ${text}.`);
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
    const end = (keep) => {
      if (over) return;
      over = true;
      target.removeEventListener("keydown", onKey);
      target.removeEventListener("blur", onBlur);
      const text = target.textContent.trim();
      target.removeAttribute("contenteditable");
      target.classList.remove("dgm-editing");
      if (keep && text !== was) done(text);
      else target.textContent = was;
      //: Not when the render that `done` made has already put focus there: a focus() after a change forces its layout.
      const block = key && blockEl(S, key);
      if (block && document.activeElement !== block) block.focus();
    };
    const onKey = (event) => {
      if (event.key !== "Enter" && event.key !== "Escape") return;
      event.preventDefault();
      event.stopPropagation();
      end(event.key === "Enter");
    };
    const onBlur = () => end(true);
    target.addEventListener("keydown", onKey);
    target.addEventListener("blur", onBlur);
  }

  function stepBlock(S, key, dir) {
    if (key[0] === "k") return;
    if (!diagramOps.step(S.m, key, dir)) return say(S, `${nameOf(S, key)} is already ${dir < 0 ? "first" : "last"}.`);
    commit(S, `Moved ${nameOf(S, key)} ${dir < 0 ? "up" : "down"}.`);
  }

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
    if (event.target.isContentEditable || !block || event.target.closest(".menu-wrap, .dgm-join, .dgm-connect")) return;
    const key = block.dataset.key;
    const all = [...S.tree.querySelectorAll(".dgm-block")];
    const at = all.indexOf(block);
    const go = (target) => target && select(S, target.dataset.key, true);
    const mod = event.ctrlKey || event.metaKey;
    if (mod && !event.altKey && /^[zy]$/i.test(event.key)) {
      event.preventDefault();
      //: Not passed on: the app's own Ctrl+Z would undo a second step (measured: one press took a merge and the template before it).
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
    const plain = {
      ArrowDown: () => go(all[at + 1]), ArrowUp: () => go(all[at - 1]), Home: () => go(all[0]), End: () => go(all.at(-1)),
      ArrowLeft: () => go(block.parentElement.closest(".dgm-block")), ArrowRight: () => go(block.querySelector(".dgm-block")),
      Enter: () => relabel(S, key), F2: () => relabel(S, key),
      Insert: () => addBlock(S, { after: key }), n: () => addBlock(S, { after: key }), N: () => addBlock(S, { after: key }),
      g: () => addBlock(S, { after: key, group: true }), G: () => addBlock(S, { after: key, group: true }),
      c: () => key[0] !== "k" && joinPick(S, key), C: () => key[0] !== "k" && joinPick(S, key),
      j: () => key[0] !== "k" && joinPick(S, key), J: () => key[0] !== "k" && joinPick(S, key),
      Delete: () => removeBlock(S, key), Backspace: () => removeBlock(S, key),
      ContextMenu: () => menuAt(S, block), F10: () => event.shiftKey && menuAt(S, block),
    }[event.key];
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
  const helpers = { el, say, commit, blockEl, suggest, add: addBlock, panes, name: nameOf };
  async function suggest(S, how) {
    if (!(await ensureModule("diagramSuggest"))) return say(S, "The suggestions did not load.");
    return diagramModel.suggest[how](S, helpers);
  }

  //: The connector row's menu and the picker that connects two blocks (diagram-joins.js, lazy): fetched on first use.
  async function joins(S, how, arg) {
    if (!(await ensureModule("diagramJoins"))) return void say(S, "Connectors did not load.");
    return diagramModel.joins[how](S, arg, helpers);
  }
  const joinPick = (S, key) => joins(S, "pick", key);

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
    const rows = [["ph:file-svg Save as SVG", "svg"], ["ph:file-png Save as PNG", "png"], ["ph:copy Copy as Mermaid", "mermaid"], ["ph:code Copy as SVG", "svgtext"]];
    //: Where the four direction buttons do not fit (a phone, a touch screen) they fold into this menu: a dock folds by width.
    const fold = S.dirs && matchMedia(COMPACT).matches ? [{ label: "ph:compass Direction", items: DIRS.map(([dir, arrow, name]) => ({ label: `ph:arrow-${arrow} ${name}`, run: () => S.dirs.querySelector(`[data-dir="${dir}"]`).click() })), group: "view" }] : [];
    //: With the direction, Suggest folds in here too: Add, Undo, Redo and this menu are one row at 320 (INBOX 1596 d).
    if (S.suggestBtn && matchMedia(COMPACT).matches) fold.push({ label: "ph:sparkle Suggest…", group: "edit", run: () => suggestMenu(S, S.root.querySelector(".dgm-more button") || S.suggestBtn) });
    const menu = kebabMenu([...(S.io.menu || []), ...fold, ...rows.map(([label, how]) => makeMenuItem(label, "", () => ensureModule("diagramEmbed").then((ok) => ok && diagramModel.embed.out(how, S.source, S.io.name))))], "More for this diagram");
    menu.classList.add("dgm-more");
    return menu;
  }

  function buildPalette(S) {
    const bar = el("div", "dock dgm-dock");
    bar.dataset.dockName = "diagram";
    bar.setAttribute("role", "toolbar");
    bar.setAttribute("aria-label", "Diagram blocks");
    //: The Add library (diagram-library.js): the shapes grouped by meaning, each with its hint.
    const library = diagramModel.library;
    const shapes = library.build(library.flow({ glyph: shapeGlyph, groupGlyph, label: SHAPE_LABEL, add: (options) => addBlock(S, options) }));
    S.dirs = el("div", "seg dgm-dirs");
    S.dirs.setAttribute("role", "group");
    S.dirs.setAttribute("aria-label", "Direction of the diagram");
    for (const [dir, arrow, name] of DIRS) {
      const b = el("button");
      b.type = "button";
      b.dataset.dir = dir;
      b.title = name;
      b.setAttribute("aria-label", name);
      const icon = el("i", `ph ph-arrow-${arrow}`);
      icon.setAttribute("aria-hidden", "true");
      b.append(icon);
      b.addEventListener("click", () => {
        S.m.dir = dir;
        commit(S, `${name}.`);
      });
      S.dirs.append(b);
    }
    const actions = el("div", "dock-actions");
    S.suggestBtn = smallButton("ph:sparkle Suggest", "Start from a template, your notes or a description", () => suggestMenu(S, S.suggestBtn));
    S.suggestBtn.classList.add("dgm-suggest");
    S.suggestBtn.setAttribute("aria-haspopup", "menu");
    actions.append(S.suggestBtn);
    for (const [icon, label, run] of [["ph:arrow-counter-clockwise", "Undo", () => S.io.undo()], ["ph:arrow-clockwise", "Redo", () => S.io.redo()]]) {
      const b = smallButton(icon, label, run);
      b.classList.add("icon-only");
      b.setAttribute("aria-label", label);
      actions.append(b);
    }
    actions.append(more(S));
    bar.append(shapes, el("div", "dock-group"), actions, shapes.hint);
    bar.children[1].append(S.dirs);
    return bar;
  }

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
    S.empty.append(el("p", "empty-title", "Start a diagram"), el("p", "", "Press a shape in Add, or press N, to add the first block. Then press Connect to… on a block to draw an arrow to the next."), start);
    S.ghosts = el("div", "dgm-ghosts hidden");
    S.drop = el("div", "dgm-drop hidden");
    S.pane = el("div", "dgm-pane");
    S.pane.setAttribute("aria-label", "Diagram blocks. Press N for a block or G for a group.");
    S.pane.setAttribute("role", "region");
    //: The next step, one line under the list (and the space under it): it follows what the diagram has so far.
    S.next = el("p", "muted dgm-next");
    S.pane.append(S.tree, S.next, S.empty, S.ghosts, S.drop);
    S.fig = el("figure", "dgm-picture");
    const body = el("div", "dgm-body");
    body.append(S.pane, S.fig);
    S.note = el("p", "muted dgm-hint hidden", "");
    root.append(buildPalette(S), S.note, body, S.live);
    host.append(root);
    panes.set(root, S);
    S.tree.addEventListener("keydown", (event) => onKey(S, event));
    S.tree.addEventListener("click", (event) => {
      const block = event.target.closest(".dgm-block");
      if (block && !event.target.closest(".menu-wrap, .dgm-join, .dgm-connect")) select(S, block.dataset.key);
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
      if (id && diagramOps.node(S.m, id)) select(S, diagramOps.key("n", id), true);
    });
    S.pane.addEventListener("keydown", (event) => {
      if (event.target !== S.pane || !/^[nNgG]$|^Insert$/.test(event.key)) return;
      event.preventDefault();
      addBlock(S, { after: null, group: /^[gG]$/.test(event.key) });
    });
    sync(host, text, S);
    return S;
  }

  //: Reads the source into the model. Another kind of diagram, or a source the
  //: reader cannot take, is shown as its picture alone with one line saying why.
  function sync(host, text, S = panes.get(host.querySelector(".dgm"))) {
    if (!S) return null;
    S.source = text;
    //: More blocks than the pane holds (`diagramOps.MAX`) is the same answer as another kind: the picture and a line.
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
    await Promise.all(["/css/objmove-lazy.css", "/js/obj-ref.js", "/js/obj-drag.js", "/js/diagram-picture.js", "/js/diagram-library.js", "/js/diagram-pointer.js", "/js/diagram-ops.js"].map((file) => lazyScript(file)));
    diagramOps = helpers.ops = diagramModel.ops;
    if (typeof OBJ_MODES === "object" && !OBJ_MODES.diagram) OBJ_MODES.diagram = diagramModel.pointer.make(helpers);
    kit.dropMark ||= diagramModel.pointer.dropMark;
    const kind = kindOf(text);
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
    //: A narrow window or a touch screen gets the phone's palette sheet and the picture's pinch (diagram-touch.js).
    if (S && matchMedia(COMPACT).matches && (await ensureModule("diagramTouch"))) diagramModel.touch.wire(S);
    if (told && S) say(S, told);
    told = "";
    return S;
  }

  diagramModel.builder = { show, kindOf, tell: (text) => (told = text) };
})();
