// diagram-suggest.js: what the block pane is offered (1546 P3, DOCUMENTS_PLAN
// "1546 design" D8). Lazy: `LAZY_MODULES.diagramSuggest`, registered at the foot of
// documents-mermaid.js and fetched by the builder on the first press of Suggest.
//
// Three ways in, one way out. Templates (`board-library/diagram-templates.json`,
// picked in the dialog-of-choices recipe with each preview drawn by the frame),
// From my notes (the Library picker, then `POST /drafts/compose` with `kind:
// "diagram"`: the composer by rule, no model needed) and Describe it (the same
// route with the model on). Each yields a Mermaid source, and `receive` lands it
// as blocks: on an empty diagram it becomes the diagram; otherwise its blocks
// arrive as ghosts (the Ghost topics recipe: Tab takes, Shift+Tab lets go, Enter
// adds, Escape drops), ids renumbered past the diagram's own, one undo step.
// Text nodes only: nothing a model wrote is ever inserted as markup.
//
// One closure, one export: `diagramModel.suggest`.
(() => {
  // DIAGRAM-GHOST-BEGIN
  //: **The merge** (D8): the blocks of `inc` (a parsed model) added to `m` through the
  //: builder's own ops (`ops` is `diagramOps`), so ids are renumbered past the diagram's
  //: own (A and B taken means the newcomers are C, D, E), a group goes in before what it
  //: holds, and the limit of blocks is the pane's. `take` is a Set of the incoming keys
  //: (`n:<id>`, `g:<id>`) to bring, or null for all. A join comes only when both ends do;
  //: a block whose group stayed behind goes to the top. Kept lines are not merged.
  //: Answers `{nodes, groups, edges, skipped, map}` (`map`: incoming id to new id).
  function dgsMerge(ops, m, inc, take = null) {
    const want = (type, id) => !take || take.has(`${type}:${id}`);
    const map = new Map();
    const out = { nodes: 0, groups: 0, edges: 0, skipped: 0, map };
    const known = new Set(inc.subgraphs.map((g) => g.id));
    const walk = (parent, into) => {
      for (const g of inc.subgraphs) {
        if ((known.has(g.parent) && g.parent !== g.id ? g.parent : null) !== parent) continue;
        let here = into;
        if (want("g", g.id)) {
          const id = ops.addGroup(m, { title: g.title, parent: into });
          if (id) {
            map.set(g.id, id);
            here = id;
            out.groups++;
          } else out.skipped++;
        }
        walk(g.id, here);
      }
    };
    walk(null, null);
    for (const n of inc.nodes) {
      if (!want("n", n.id)) continue;
      const id = ops.addNode(m, { shape: n.shape, text: n.text, group: map.get(n.group) ?? null });
      if (id) {
        map.set(n.id, id);
        out.nodes++;
      } else out.skipped++;
    }
    for (const e of inc.edges) {
      if (!map.has(e.from) || !map.has(e.to)) continue;
      if (ops.join(m, map.get(e.from), map.get(e.to), { label: e.label, style: e.style, arrow: e.arrow })) out.edges++;
    }
    return out;
  }

  //: A block and everything inside it (a group's whole subtree), as incoming keys.
  function dgsSubtree(inc, key) {
    const keys = [key];
    if (key[0] !== "g") return keys;
    const id = key.slice(2);
    for (const g of inc.subgraphs) if (g.parent === id && g.id !== id) keys.push(...dgsSubtree(inc, `g:${g.id}`));
    for (const n of inc.nodes) if (n.group === id) keys.push(`n:${n.id}`);
    return keys;
  }
  // DIAGRAM-GHOST-END

  const count = (n, one, many) => `${n} ${n === 1 ? one : many}`;
  const SHAPE_NAME = { rect: "box", round: "rounded box", stadium: "pill", circle: "circle", diamond: "decision", hexagon: "hexagon", cylinder: "database", parallelogram: "input or output" };
  const NOUN = { flowchart: "flowchart", mindmap: "mind map", timeline: "timeline", sequence: "sequence diagram", gantt: "Gantt chart", pie: "pie chart", state: "state diagram", class: "class diagram", er: "ER diagram" };

  //: Whether the diagram has nothing in it a suggestion could clash with.
  const isEmpty = (m) => !m.nodes.length && !m.subgraphs.length && !m.edges.length && !(m.kept || []).length;
  //: The same for the pane's own kind (a flowchart's model, or a mind map's, a timeline's, a sequence diagram's).
  const paneBlank = (S) => (S.k ? S.k.blank(S.m) : isEmpty(S.m));

  //: The key of the first block of a kind's model (where the focus goes after a suggestion lands).
  function firstKey(A, inc) {
    const ops = diagramModel.kinds.ops;
    let first = null;
    ops.walk(A, inc, (n) => {
      if (!first && n.type !== "k") first = ops.key(n);
    });
    return first;
  }

  // --- a source arrives ------------------------------------------------------------
  //: `source` is Mermaid from a template, the composer or a model; `said` the one line
  //: that goes with it. Answers once it has landed or been refused. A suggestion of the
  //: pane's own kind lands as blocks (D8; 1546 P4 gave the other kinds the same): on a blank
  //: diagram it becomes the diagram, otherwise its blocks arrive as ghosts. Another kind is
  //: refused when the diagram has blocks, and replaces a blank one. `replace` (the template dialog's
  //: Replace the diagram) treats the pane as blank, so the template becomes the diagram in one undoable commit.
  async function receive(S, h, source, said, replace = false) {
    S.note.classList.toggle("hidden", !S.plain);
    const kind = diagramModel.builder.kindOf(source);
    const mine = S.k ? S.k.name : "flowchart";
    if (kind !== "flowchart" && !(await ensureModule("diagramKinds"))) return reason(S, h, "The block editor did not load."), false;
    if (kind !== "flowchart" && !(await diagramModel.kinds.load(kind))) return reason(S, h, "The block editor did not load."), false;
    const A = kind === "flowchart" ? null : diagramModel.kinds[kind];
    const inc = A ? A.parse(source) : diagramModel.parse(source);
    //: Blank: nothing in the diagram a suggestion could clash with, so it becomes the diagram.
    const blank = replace || !S.source.trim() || (!S.plain && paneBlank(S));
    if (inc && kind === mine && !S.plain) {
      if (blank) {
        const keep = S.m.front || [];
        S.m = inc;
        if (inc.front && !inc.front.length && keep.length) inc.front = keep;
        S.sel = A ? firstKey(A, inc) : inc.nodes.length ? h.ops.key("n", inc.nodes[0].id) : null;
        h.commit(S, said);
        h.blockEl(S, S.sel)?.focus();
        return true;
      }
      const spec = A ? diagramModel.kinds.ghostSpec(S, inc) : flowSpec(S, h, inc);
      if (!spec.rows.length) return h.say(S, "There was nothing in it to add."), false;
      ghosts(S, h, spec, said);
      return true;
    }
    if (inc && S.plain) return reason(S, h, "This diagram is another kind, so blocks cannot add to it. Source still works."), false;
    //: Another kind, or a source the reader cannot take.
    const word = kind !== "flowchart" ? NOUN[kind] : /^\s*(?:%%.*\n\s*)*([A-Za-z][\w-]*)/.exec(source)?.[1] || "diagram";
    if (!blank) return reason(S, h, kind === mine ? "Blocks cannot read what came back, so it was left out." : `That came back as a ${word}, and this is a ${NOUN[mine]}, so blocks cannot add to it. It was left out.`), false;
    //: On a blank diagram the other kind is drawn first: one the frame refuses shows its reason
    //: and opens in Source so it can be mended there; one it draws becomes the source, and the
    //: pane of its kind opens in place of this one.
    const ok = await ensureModule("mermaid");
    const result = ok ? await mermaidRequest(source) : { error: "The diagram renderer did not load." };
    if (result.svg) {
      diagramModel.builder.tell(said);
      S.io.set(source);
      return true;
    }
    S.io.set(source);
    setDocView("source", { persist: false });
    const first = String(result.error || "").split("\n").find((line) => line.trim()) || "It could not be drawn.";
    reason(S, h, `The picture could not be drawn: ${first.trim().slice(0, 140)}`);
    return false;
  }

  //: One plain line for why nothing arrived (the pane's own note line, and said aloud).
  function reason(S, h, text) {
    S.note.textContent = text;
    S.note.classList.remove("hidden");
    h.say(S, text);
  }

  // --- ghosts ----------------------------------------------------------------------
  //: A flowchart's suggestion as the ghosts layer reads it: `rows` (key, level, glyph, text, meta,
  //: aria), `subtree(key)` (the keys that go with a block) and `merge(take)`. A kind's comes from
  //: diagram-kinds.js (`ghostSpec`) in the same shape.
  function flowSpec(S, h, inc) {
    const flat = [];
    const walk = (items, level) => {
      for (const item of items) {
        if (item.type === "k") continue;
        flat.push({ ...item, level, key: `${item.type}:${item.id}` });
        if (item.kids) walk(item.kids, level + 1);
      }
    };
    walk(h.ops.layout({ ...inc, kept: [] }), 0);
    return {
      rows: flat.map((row) => {
        const isGroup = row.type === "g";
        const data = isGroup ? inc.subgraphs.find((g) => g.id === row.id) : inc.nodes.find((n) => n.id === row.id);
        const name = isGroup ? data.title : data.text;
        const glyph = isGroup ? h.el("i", "ph ph-stack dgm-group-icon") : h.el("span", "dgm-shape");
        if (!isGroup) glyph.dataset.shape = data.shape;
        glyph.setAttribute("aria-hidden", "true");
        const outs = inc.edges.filter((e) => e.from === row.id).map((e) => inc.nodes.find((n) => n.id === e.to)?.text || inc.subgraphs.find((g) => g.id === e.to)?.title || e.to);
        return { key: row.key, level: row.level, glyph, text: name, meta: outs.length ? `to ${outs.join(", ")}` : "", aria: `${name}, ${isGroup ? "group" : SHAPE_NAME[data.shape]}${outs.length ? `, joins to ${outs.join(", ")}` : ""}` };
      }),
      subtree: (key) => dgsSubtree(inc, key),
      merge(take) {
        const done = dgsMerge(h.ops, S.m, inc, take);
        const lead = inc.nodes.find((n) => done.map.has(n.id));
        const parts = [done.nodes ? count(done.nodes, "block", "blocks") : "", done.groups ? count(done.groups, "group", "groups") : "", done.edges ? count(done.edges, "join", "joins") : ""].filter(Boolean);
        return { count: done.nodes + done.groups, skipped: done.skipped, parts: parts.join(", "), sel: lead ? h.ops.key("n", done.map.get(lead.id)) : h.ops.key("g", [...done.map.values()][0]) };
      },
    };
  }

  //: The Ghost topics recipe, in the tree's own place: a `role="group"` under the blocks
  //: holding one toggle (`aria-pressed`, faded and dashed until taken) per incoming block.
  function ghosts(S, h, spec, said) {
    const layer = S.ghosts;
    const taken = new Set();
    const buttons = [];
    layer.replaceChildren();
    layer.classList.remove("hidden");
    layer.setAttribute("role", "group");
    layer.setAttribute("aria-label", "Suggested blocks");

    const head = h.el("div", "dgm-ghost-head");
    const title = h.el("strong", "", count(spec.rows.length, "suggested block", "suggested blocks"));
    const line = h.el("p", "muted", `${said || "Suggested by the composer."} Tab takes a block, Enter adds, Escape drops them.`);
    head.append(title, line);

    const list = h.el("div", "dgm-ghost-list");
    for (const row of spec.rows) {
      const ghost = h.el("button", "dgm-ghost");
      ghost.type = "button";
      ghost.dataset.key = row.key;
      ghost.dataset.level = String(Math.min(row.level, 4));
      ghost.setAttribute("aria-pressed", "false");
      const words = h.el("span", "dgm-ghost-words");
      words.append(h.el("span", "dgm-ghost-text", row.text), ...(row.meta ? [h.el("span", "dgm-ghost-joins muted", row.meta)] : []));
      ghost.append(row.glyph, words);
      ghost.setAttribute("aria-label", row.aria);
      ghost.addEventListener("click", () => toggle(ghost, !taken.has(row.key)));
      list.append(ghost);
      buttons.push(ghost);
    }

    const foot = h.el("div", "dgm-ghost-foot row right");
    const drop = smallButton("Drop", "Drop the suggestions (Escape)", () => end(false));
    const add = smallButton("Add", "Add the blocks you took, or all of them", () => finish(), false);
    add.classList.add("accent");
    foot.append(drop, add);
    layer.append(head, list, foot);

    const toggle = (ghost, on) => {
      for (const key of spec.subtree(ghost.dataset.key)) {
        if (on) taken.add(key);
        else taken.delete(key);
        const b = buttons.find((x) => x.dataset.key === key);
        b?.classList.toggle("is-taken", on);
        b?.setAttribute("aria-pressed", String(on));
      }
      label();
    };
    const label = () => {
      const n = taken.size;
      setLabel(add, n ? `Add ${count(n, "block", "blocks")}` : "Add all");
    };
    label();

    const end = (added) => {
      layer.replaceChildren();
      layer.classList.add("hidden");
      (h.blockEl(S, S.sel) || S.tree.querySelector(".dgm-block") || S.pane).focus?.();
      if (!added) h.say(S, "Suggestions dropped.");
    };
    //: Enter and the button: the taken blocks, else (the recipe) the one in focus, else all of them from the button.
    const finish = (focused = null) => {
      const done = spec.merge(taken.size ? taken : focused ? new Set(spec.subtree(focused.dataset.key)) : null);
      if (!done.count) return h.say(S, `A diagram holds at most ${h.ops.MAX} blocks, so nothing was added.`);
      S.sel = done.sel;
      end(true);
      h.commit(S, `Added ${done.parts || count(done.count, "block", "blocks")}.${done.skipped ? ` ${count(done.skipped, "block did", "blocks did")} not fit.` : ""} Undo takes them back.`);
    };

    layer.onkeydown = (event) => {
      const at = buttons.indexOf(document.activeElement);
      if (event.target.closest(".dgm-ghost-foot")) {
        if (event.key === "Escape") {
          event.preventDefault();
          event.stopPropagation();
          end(false);
        }
        return;
      }
      if (at < 0) return;
      const used = { Escape: 1, Tab: 1, Enter: 1, ArrowDown: 1, ArrowUp: 1 };
      if (!used[event.key]) return;
      //: Taken here, not passed on: the pane's own Enter relabels a block and Tab leaves it.
      event.stopPropagation();
      event.preventDefault();
      if (event.key === "Escape") end(false);
      else if (event.key === "Tab") {
        //: Tab takes, Shift+Tab lets go; the walk is the arrows'. Past the last one, Tab leaves the layer.
        toggle(buttons[at], !event.shiftKey);
        const next = at + (event.shiftKey ? 0 : 1);
        if (next >= buttons.length) foot.querySelector(".accent").focus();
        else buttons[Math.max(0, next)].focus();
      } else if (event.key === "Enter") finish(buttons[at]);
      else buttons[(at + (event.key === "ArrowDown" ? 1 : -1) + buttons.length) % buttons.length].focus();
    };
    buttons[0]?.focus();
    h.say(S, `${count(buttons.length, "suggested block", "suggested blocks")}. ${said || ""} Tab takes one, Enter adds, Escape drops them.`);
  }

  // --- the Suggest menu ---------------------------------------------------------------
  //: The rows under the palette's Suggest button, made here so the builder does not carry them.
  function items(S, h) {
    const off = aiIsOff();
    return [
      { label: "ph:layout Templates", run: () => h.suggest(S, "templates"), group: "start" },
      { label: "ph:note-pencil From my notes", run: () => h.suggest(S, "notes"), group: "start" },
      {
        label: "ph:sparkle Describe it",
        disabled: off,
        title: off ? "Describing a diagram needs a model. Connect a model in Settings." : "Say what the diagram is, and the model drafts it",
        //: A dimmed row still answers: it says why, on the pane's own line (and aloud).
        run: () => {
          if (!off) return h.suggest(S, "describe");
          reason(S, h, "Describing a diagram needs a model. Connect a model in Settings. Templates and From my notes work without one.");
        },
        group: "start",
      },
    ];
  }

  // --- Templates ---------------------------------------------------------------------
  let cache = null;
  async function loadTemplates() {
    if (cache) return cache;
    const res = await api(`/board-library/diagram-templates.json${lazyAssetStamp()}`, { silent: true });
    const body = await res.json();
    cache = (body.templates || []).filter((t) => t && typeof t.source === "string" && t.name);
    return cache;
  }

  //: The dialog of choices (DESIGN.md: rows that each make something, beside a picture of
  //: what the chosen row makes): a click chooses, Enter, a double click or the one filled
  //: button makes it, the arrows walk the rows, and the first row is chosen on open.
  async function templates(S, h) {
    //: A failed read says so; an empty list is not dressed up as one (test_load_failed_1028b).
    const all = await loadTemplates().catch(() => null);
    if (!all) return reason(S, h, "The templates did not load. Try again in a moment.");
    if (!all.length) return reason(S, h, "There are no templates yet.");
    const fill = S.plain || !paneBlank(S);
    //: A diagram with blocks takes only blocks of its own kind, so only its kind's templates are offered.
    const mine = S.k ? S.k.name : "flowchart";
    const rows = fill && !S.plain ? all.filter((t) => (t.kind || "flowchart") === mine) : all;
    const dialog = h.el("dialog", "card space-dialog doc-ai-history-dialog doc-template-dialog dgm-template-dialog");
    dialog.setAttribute("aria-label", "Start from a template");
    const returnFocus = document.activeElement;
    const list = h.el("ul", "doc-ai-history-list");
    list.setAttribute("role", "radiogroup");
    list.setAttribute("aria-label", "Templates");
    const preview = h.el("div", "doc-template-preview dgm-template-preview");
    preview.setAttribute("aria-hidden", "true");
    preview.inert = true;
    const figure = h.el("figure", "dgm-template-figure");
    preview.append(figure);
    let chosen = null;
    let made = false;
    let stamp = 0;
    const paint = (t) => {
      const mine = ++stamp;
      figure.replaceChildren();
      figure.classList.remove("md-mermaid", "md-mermaid-pending");
      if (!t.kind && !diagramModel.parse(t.source)?.nodes.length) return figure.append(h.el("p", "muted dgm-hint", "An empty flowchart."));
      ensureModule("mermaid").then((ok) => {
        if (ok && mine === stamp) mermaidFill(figure, t.source);
      });
    };
    const choose = (t, focus = false) => {
      chosen = t;
      for (const row of list.querySelectorAll(".doc-template-choice")) {
        const on = row.dataset.template === t.id;
        row.setAttribute("aria-checked", String(on));
        row.tabIndex = on ? 0 : -1;
        if (on && focus) row.focus();
      }
      paint(t);
    };
    const use = async (replace = false) => {
      if (made || !chosen) return;
      made = true;
      dialog.close();
      if (replace === true) await receive(S, h, chosen.source, `Replaced the diagram with the ${chosen.name.toLowerCase()} template.`, true);
      else await receive(S, h, chosen.source, `Started from the ${chosen.name.toLowerCase()} template.`);
    };
    for (const t of rows) {
      const li = h.el("li");
      li.setAttribute("role", "presentation");
      const button = h.el("button", "ghost doc-template-choice");
      button.type = "button";
      button.setAttribute("role", "radio");
      button.setAttribute("aria-checked", "false");
      button.dataset.template = t.id;
      const check = h.el("i", "ph ph-check doc-template-check");
      check.setAttribute("aria-hidden", "true");
      button.append(h.el("strong", "", t.name), h.el("span", "muted text-sm", t.hint || ""), check);
      button.addEventListener("click", () => choose(t));
      button.addEventListener("dblclick", use);
      li.append(button);
      list.append(li);
    }
    list.addEventListener("keydown", (event) => {
      const buttons = [...list.querySelectorAll(".doc-template-choice")];
      const at = buttons.findIndex((b) => b.getAttribute("aria-checked") === "true");
      const step = { ArrowDown: 1, ArrowRight: 1, ArrowUp: -1, ArrowLeft: -1 }[event.key];
      const next = step ? buttons[(at + step + buttons.length) % buttons.length] : event.key === "Home" ? buttons[0] : event.key === "End" ? buttons.at(-1) : null;
      if (next) {
        event.preventDefault();
        choose(rows.find((t) => t.id === next.dataset.template), true);
      } else if (event.key === "Enter") {
        event.preventDefault();
        use();
      }
    });
    const body = h.el("div", "doc-template-body");
    //: Fourteen rows are typed to (DESIGN.md row 714); Escape clears the field before it closes the dialog.
    const column = h.el("div", "dgm-template-column");
    column.append(list);
    body.append(column, preview);
    listFilter(list, { label: "Search the templates" });
    const foot = h.el("div", "row right space-dialog-actions");
    const cancel = smallButton("Cancel", "Close without starting", () => dialog.close());
    const go = smallButton(fill ? "Add its blocks" : "Use this template", "Start from the chosen template", use, false);
    go.classList.add("accent");
    foot.append(cancel);
    //: A diagram with blocks can also be swapped for the template; Undo (Ctrl+Z) brings the old one back.
    if (fill && !S.plain) foot.append(smallButton("Replace the diagram", "Swap the diagram for the chosen template; Undo brings it back", () => use(true)));
    foot.append(go);
    dialog.append(
      dialogHead("Start from a template", () => dialog.close()),
      h.el("p", "muted", fill ? "Your diagram has blocks, so the template's blocks arrive as suggestions to take." : "A starting shape, not a form: every block is yours to change."),
      body,
      foot,
    );
    dialog.addEventListener("close", () => {
      dialog.remove();
      //: A template that was used hands the focus to what it made (the first block, or the ghosts).
      if (!made && returnFocus?.isConnected) returnFocus.focus?.();
    });
    document.body.append(dialog);
    dialog.showModal();
    choose(rows[0], true);
    return null;
  }

  // --- From my notes and Describe it ----------------------------------------------------
  //: The headings of a document, outside its code fences: two or more make an outline.
  function outlineOf(text) {
    let fenced = false;
    const heads = [];
    for (const line of String(text || "").split("\n")) {
      if (/^\s*```/.test(line)) fenced = !fenced;
      else if (!fenced && /^\s{0,3}#{1,6}\s+\S/.test(line)) heads.push(line.trim());
    }
    return heads;
  }

  //: Asks `/drafts/compose` for a diagram and hands what came back to `receive`. The
  //: server reads the reply (`diagram`, or `diagram_error`, one sentence of why not).
  async function compose(S, h, body, working) {
    S.root.classList.add("dgm-busy");
    h.say(S, working);
    try {
      const flow = !S.plain && paneBlank(S) ? "" : S.k ? S.k.want || "" : "flowchart";
      const res = await apiJson("/drafts/compose", { method: "POST", body: JSON.stringify({ kind: "diagram", instruction: flow, ...body }), silent: true });
      if (!res.diagram) return reason(S, h, res.diagram_error || res.message || "Nothing came back to draw.");
      return await receive(S, h, res.diagram, res.said || (res.by === "composer" ? "Drawn by plain rule, with no model." : "Drafted by the model."));
    } catch (err) {
      return reason(S, h, err?.message || "The diagram could not be drafted.");
    } finally {
      S.root.classList.remove("dgm-busy");
    }
  }

  async function notes(S, h) {
    const pick = await pickLibraryItemDialog("Draw a diagram from", { sources: ["note", "document"] });
    if (!pick) return null;
    if (pick.kind === "note") return compose(S, h, { source_ids: [pick.id] }, `Reading ${pick.label}.`);
    const doc = await apiJson(`/documents/${pick.id}`, { silent: true }).catch(() => null);
    if (!doc || !String(doc.content || "").trim()) return reason(S, h, `${pick.label} has nothing in it to draw.`);
    const heads = outlineOf(doc.content);
    //: A document with sections is drawn from its headings (a mind map); otherwise from its text.
    return heads.length >= 2
      ? compose(S, h, { draft: heads.join("\n").slice(0, 20000), instruction: !S.plain && paneBlank(S) ? "mind map" : S.k ? S.k.want || "" : "flowchart" }, `Reading the headings of ${pick.label}.`)
      : compose(S, h, { draft: String(doc.content).slice(0, 20000) }, `Reading ${pick.label}.`);
  }

  async function describe(S, h) {
    const text = await promptDialog("Describe the diagram", "", { confirmLabel: "Draw it" });
    if (!text) return null;
    return compose(S, h, { thoughts: text.slice(0, 8000) }, "Drafting from your description.");
  }

  const el = (tag, cls, text) => {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text != null) node.textContent = text;
    return node;
  };

  // --- the sheet (R12, owner 2026-11-12) -------------------------------------------------
  //: `/diagram`, the board's Insert and the builder's "Open an existing diagram" ask here first: the diagrams already made
  //: (documents of type mmd) and, when `fresh`, "New diagram" first. Answers the document row, `true` for New, or null. The
  //: dialog of choices (DESIGN.md): a click chooses, Enter, a double click or the one filled button takes it.
  async function choose({ fresh = true, verb = "Open" } = {}) {
    let all = typeof docs !== "undefined" && Array.isArray(docs) && docs.length ? docs : null;
    //: A list that failed to load says so; it is never shown as "No diagrams yet" (test_load_failed_1028b).
    if (!all) all = await apiPagedList("/documents", 200).catch((error) => (toast(`Couldn't load your diagrams: ${error?.message || error}`, "info"), null));
    if (!all) return null;
    const rows = [...(fresh ? [{ id: "new", title: "New diagram", hint: "Start with an empty builder", pick: true }] : []), ...all.filter((d) => d.file_type === "mmd").map((d) => ({ id: String(d.id), title: d.title || "Untitled", hint: d.updated_at ? `Changed ${relativeTime(d.updated_at)}` : "", pick: d }))];
    if (!rows.length) return toast("No diagrams yet. Make one with the blocks and it will be listed here.", "info");
    return new Promise((resolve) => {
      const dialog = el("dialog", "card space-dialog doc-ai-history-dialog doc-template-dialog dgm-choose-dialog");
      dialog.setAttribute("aria-label", "Choose a diagram");
      const returnFocus = document.activeElement;
      const list = el("ul", "doc-ai-history-list");
      list.setAttribute("role", "radiogroup");
      list.setAttribute("aria-label", "Diagrams");
      let chosen = null;
      let answer = null;
      const mark = (row, focus = false) => {
        chosen = row;
        for (const b of list.querySelectorAll(".doc-template-choice")) {
          const on = b.dataset.id === row.id;
          b.setAttribute("aria-checked", String(on));
          b.tabIndex = on ? 0 : -1;
          if (on && focus) b.focus();
        }
      };
      const use = () => {
        answer = chosen?.pick ?? null;
        dialog.close();
      };
      for (const row of rows) {
        const li = el("li");
        li.setAttribute("role", "presentation");
        const button = el("button", "ghost doc-template-choice");
        button.type = "button";
        button.setAttribute("role", "radio");
        button.setAttribute("aria-checked", "false");
        button.dataset.id = row.id;
        const check = el("i", "ph ph-check doc-template-check");
        check.setAttribute("aria-hidden", "true");
        button.append(el("strong", "", row.title), el("span", "muted text-sm", row.hint), check);
        button.addEventListener("click", () => mark(row));
        button.addEventListener("dblclick", use);
        li.append(button);
        list.append(li);
      }
      list.addEventListener("keydown", (event) => {
        const buttons = [...list.querySelectorAll(".doc-template-choice")];
        const at = buttons.findIndex((b) => b.getAttribute("aria-checked") === "true");
        const step = { ArrowDown: 1, ArrowRight: 1, ArrowUp: -1, ArrowLeft: -1 }[event.key];
        const next = step ? buttons[(at + step + buttons.length) % buttons.length] : event.key === "Home" ? buttons[0] : event.key === "End" ? buttons.at(-1) : null;
        if (next) {
          event.preventDefault();
          mark(rows.find((r) => r.id === next.dataset.id), true);
        } else if (event.key === "Enter") {
          event.preventDefault();
          use();
        }
      });
      const foot = el("div", "row right space-dialog-actions");
      const go = smallButton(verb, "Use the chosen diagram", use, false);
      go.classList.add("accent");
      foot.append(smallButton("Cancel", "Close without choosing", () => dialog.close()), go);
      dialog.append(dialogHead("Choose a diagram", () => dialog.close()), el("p", "muted", fresh ? "Pick one you made, or start a new one." : "Pick the diagram to open."), list, foot);
      listFilter(list, { label: "Search your diagrams" });
      dialog.addEventListener("close", () => {
        dialog.remove();
        if (!answer && returnFocus?.isConnected) returnFocus.focus?.();
        resolve(answer);
      });
      document.body.append(dialog);
      dialog.showModal();
      mark(rows[0], true);
    });
  }

  diagramModel.suggest = { templates, notes, describe, items, choose };
})();
