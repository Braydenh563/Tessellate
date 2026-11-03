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
  const SHAPE_NAME = { rect: "box", round: "rounded box", stadium: "pill", circle: "circle", diamond: "decision", hexagon: "hexagon" };

  //: Whether the diagram has nothing in it a suggestion could clash with.
  const isEmpty = (m) => !m.nodes.length && !m.subgraphs.length && !m.edges.length && !(m.kept || []).length;

  // --- a source arrives ------------------------------------------------------------
  //: `source` is Mermaid from a template, the composer or a model; `said` the one line
  //: that goes with it. Answers once it has landed or been refused.
  async function receive(S, h, source, said) {
    S.note.classList.toggle("hidden", !S.plain);
    const inc = diagramModel.parse(source);
    //: Blank: nothing in the diagram a suggestion could clash with, so it becomes the diagram.
    const blank = !S.source.trim() || (!S.plain && isEmpty(S.m));
    if (inc && blank) {
      const keep = S.m.front || [];
      S.m = inc;
      if (!inc.front.length && keep.length) inc.front = keep;
      S.sel = inc.nodes.length ? h.ops.key("n", inc.nodes[0].id) : null;
      h.commit(S, said);
      h.blockEl(S, S.sel)?.focus();
      return true;
    }
    if (inc && S.plain) return reason(S, h, "This diagram is another kind, so blocks cannot add to it. Source still works."), false;
    if (inc) {
      if (!inc.nodes.length && !inc.subgraphs.length) return h.say(S, "There was nothing in it to add."), false;
      ghosts(S, h, inc, said);
      return true;
    }
    //: Another kind of diagram (a mind map, a timeline): the pane draws flowcharts for now.
    const kind = /^\s*(?:%%.*\n\s*)*([A-Za-z][\w-]*)/.exec(source)?.[1] || "diagram";
    if (!blank) return reason(S, h, `That came back as a ${kind}, and blocks join flowcharts only for now. It was left out.`), false;
    //: On a blank diagram the other kind is drawn first: one the frame refuses shows its reason
    //: and opens in Source so it can be mended there; one it draws becomes the source.
    const ok = await ensureModule("mermaid");
    const result = ok ? await mermaidRequest(source) : { error: "The diagram renderer did not load." };
    S.io.set(source);
    if (result.svg) {
      h.say(S, `${said} Blocks draw flowcharts for now, so it stays in Source with its picture.`);
      return true;
    }
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
  //: The Ghost topics recipe, in the tree's own place: a `role="group"` under the blocks
  //: holding one toggle (`aria-pressed`, faded and dashed until taken) per incoming block.
  function ghosts(S, h, inc, said) {
    const layer = S.ghosts;
    const flat = [];
    const walk = (items, level) => {
      for (const item of items) {
        if (item.type === "k") continue;
        flat.push({ ...item, level, key: `${item.type}:${item.id}` });
        if (item.kids) walk(item.kids, level + 1);
      }
    };
    walk(h.ops.layout({ ...inc, kept: [] }), 0);
    const taken = new Set();
    const buttons = [];
    layer.replaceChildren();
    layer.classList.remove("hidden");
    layer.setAttribute("role", "group");
    layer.setAttribute("aria-label", "Suggested blocks");

    const head = h.el("div", "dgm-ghost-head");
    const title = h.el("strong", "", count(inc.nodes.length + inc.subgraphs.length, "suggested block", "suggested blocks"));
    const line = h.el("p", "muted", `${said || "Suggested by the composer."} Tab takes a block, Enter adds, Escape drops them.`);
    head.append(title, line);

    const list = h.el("div", "dgm-ghost-list");
    for (const row of flat) {
      const isGroup = row.type === "g";
      const data = isGroup ? inc.subgraphs.find((g) => g.id === row.id) : inc.nodes.find((n) => n.id === row.id);
      const name = isGroup ? data.title : data.text;
      const ghost = h.el("button", "dgm-ghost");
      ghost.type = "button";
      ghost.dataset.key = row.key;
      ghost.dataset.level = String(Math.min(row.level, 4));
      ghost.setAttribute("aria-pressed", "false");
      const glyph = isGroup ? h.el("i", "ph ph-stack dgm-group-icon") : h.el("span", "dgm-shape");
      if (!isGroup) glyph.dataset.shape = data.shape;
      glyph.setAttribute("aria-hidden", "true");
      const outs = inc.edges.filter((e) => e.from === row.id).map((e) => inc.nodes.find((n) => n.id === e.to)?.text || inc.subgraphs.find((g) => g.id === e.to)?.title || e.to);
      const words = h.el("span", "dgm-ghost-words");
      words.append(h.el("span", "dgm-ghost-text", name), ...(outs.length ? [h.el("span", "dgm-ghost-joins muted", `to ${outs.join(", ")}`)] : []));
      ghost.append(glyph, words);
      ghost.setAttribute("aria-label", `${name}, ${isGroup ? "group" : SHAPE_NAME[data.shape]}${outs.length ? `, joins to ${outs.join(", ")}` : ""}`);
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
      for (const key of dgsSubtree(inc, ghost.dataset.key)) {
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
      const set = taken.size ? taken : focused ? new Set(dgsSubtree(inc, focused.dataset.key)) : null;
      const done = dgsMerge(h.ops, S.m, inc, set);
      if (!done.nodes && !done.groups) return h.say(S, `A diagram holds at most ${h.ops.MAX} blocks, so nothing was added.`);
      const lead = inc.nodes.find((n) => done.map.has(n.id));
      S.sel = lead ? h.ops.key("n", done.map.get(lead.id)) : h.ops.key("g", [...done.map.values()][0]);
      const parts = [done.nodes ? count(done.nodes, "block", "blocks") : "", done.groups ? count(done.groups, "group", "groups") : "", done.edges ? count(done.edges, "join", "joins") : ""].filter(Boolean);
      end(true);
      h.commit(S, `Added ${parts.join(", ")}.${done.skipped ? ` ${count(done.skipped, "block did", "blocks did")} not fit.` : ""} Undo takes them back.`);
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
    const rows = await loadTemplates().catch(() => []);
    if (!rows.length) return reason(S, h, "The templates did not load. Try again in a moment.");
    const fill = !isEmpty(S.m) || S.plain;
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
      if (!diagramModel.parse(t.source)?.nodes.length) return figure.append(h.el("p", "muted dgm-hint", "An empty flowchart."));
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
    const use = async () => {
      if (made || !chosen) return;
      made = true;
      dialog.close();
      await receive(S, h, chosen.source, `Started from the ${chosen.name.toLowerCase()} template.`);
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
    body.append(list, preview);
    const foot = h.el("div", "row right space-dialog-actions");
    const cancel = smallButton("Cancel", "Close without starting", () => dialog.close());
    const go = smallButton(fill ? "Add its blocks" : "Use this template", "Start from the chosen template", use, false);
    go.classList.add("accent");
    foot.append(cancel, go);
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
      const flow = isEmpty(S.m) && !S.plain ? "" : "flowchart";
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
      ? compose(S, h, { draft: heads.join("\n").slice(0, 20000), instruction: isEmpty(S.m) && !S.plain ? "mind map" : "flowchart" }, `Reading the headings of ${pick.label}.`)
      : compose(S, h, { draft: String(doc.content).slice(0, 20000) }, `Reading ${pick.label}.`);
  }

  async function describe(S, h) {
    const text = await promptDialog("Describe the diagram", "", { confirmLabel: "Draw it" });
    if (!text) return null;
    return compose(S, h, { thoughts: text.slice(0, 8000) }, "Drafting from your description.");
  }

  diagramModel.suggest = { templates, notes, describe };
})();
