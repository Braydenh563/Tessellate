// diagram-ai.js: the AI in the diagram builder (dgai-1110; the owner, 2026-11-10: "the ai should be able to help you
// make it and make changes and suggest edits and stuff. it should ahve versioning"). Lazy: `LAZY_MODULES.diagramAi`,
// registered at the foot of documents-mermaid.js and asked for by diagram-builder.js's `show` for every pane.
//
// Three parts, one format (docs/roadmap/agent-remaining/dgai-1110.md F1 to F8): the Ask box sends the words and the
// model to `POST /drafts/diagram-ask` and gets operations back (by rule with no model, from the model when it runs);
// Suggestions are the same operations found by a lint here; each is previewed on a copy (the picture of both with what
// is added, removed and changed marked), then Apply (one commit, one undo step, and on a Documents page a named
// version) or Discard. Versions in the builder menu list the document's versions, compare two and restore one.
// Operations come from outside: they reach the model only through `diagramOps`, which refuses what does not apply,
// and their words only through `textContent`. Pure region `DIAGRAM-AI-BEGIN` to `-END` runs in node (tests).
//
// One closure, one export: `diagramModel.ai`.
(() => {
  // DIAGRAM-AI-BEGIN
  const DGA_MAX_OPS = 12;
  const dgaFold = (text) => String(text ?? "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
  const dgaText = (value, cap) => (typeof value === "string" || typeof value === "number" ? String(value).replace(/\s+/g, " ").trim().slice(0, cap) : "");

  //: F2: the block a name means, as a key: its id first, then its words folded, and only when one block answers.
  function dgaFind(m, ref, only = "") {
    const name = dgaText(ref, 120);
    if (!name) return null;
    const pool = [...(only === "g" ? [] : m.nodes.map((n) => ["n", n.id, n.text])), ...(only === "n" ? [] : m.subgraphs.map((g) => ["g", g.id, g.title]))];
    const byId = pool.find((p) => p[1] === name);
    if (byId) return `${byId[0]}:${byId[1]}`;
    const hits = pool.filter((p) => dgaFold(p[2]) && dgaFold(p[2]) === dgaFold(name));
    return hits.length === 1 ? `${hits[0][0]}:${hits[0][1]}` : null;
  }

  const dgaArrow = (m, a, b) => (a && b ? m.edges.find((e) => e.from === a.slice(2) && e.to === b.slice(2)) : null);

  //: A new block never takes an id the diagram had before the ops (a removed C then an added C would read as one
  //: block changed, in the preview and in a compare): it moves to the next id neither model holds.
  function dgaUnused(m, taken, id, group) {
    if (!taken.has(id)) return id;
    const used = new Set([...taken, ...m.nodes.map((n) => n.id), ...m.subgraphs.map((g) => g.id)]);
    let next = "";
    for (let c = 65; c < 91 && !next; c++) if (!group && !used.has(String.fromCharCode(c))) next = String.fromCharCode(c);
    for (let i = group ? 1 : 27; !next; i++) if (!used.has(`${group ? "G" : "N"}${i}`)) next = `${group ? "G" : "N"}${i}`;
    (group ? m.subgraphs : m.nodes).find((x) => x.id === id).id = next;
    return next;
  }

  function dgaAdd(m, op, o, taken) {
    const text = dgaText(op.text, 120);
    const after = op.after ? dgaFind(m, op.after) : null;
    const group = op.group ? dgaFind(m, op.group, "g") : null;
    if (!text || (op.after && !after) || (op.group && !group)) return false;
    if (op.shape === "group") {
      const gid = o.addGroup(m, { title: text, parent: group ? group.slice(2) : null });
      return Boolean(gid && dgaUnused(m, taken, gid, true));
    }
    const home = group ? group.slice(2) : after && after[0] === "n" ? o.node(m, after.slice(2)).group : null;
    const made = o.addNode(m, { shape: o.SHAPES.includes(op.shape) ? op.shape : "rect", text, group: home && o.group(m, home) ? home : null });
    const id = made && dgaUnused(m, taken, made, false);
    if (!id) return false;
    const label = dgaText(op.label, 40);
    if (after) o.join(m, after.slice(2), id, label ? { label } : {});
    return true;
  }

  //: One op through the pane's own functions; false when it does not apply.
  function dgaOne(m, op, o, taken) {
    if (!op || typeof op !== "object") return false;
    const arrow = "from" in op || "to" in op ? dgaArrow(m, dgaFind(m, op.from), dgaFind(m, op.to)) : null;
    const target = op.target ? dgaFind(m, op.target) : null;
    switch (op.op) {
      case "add":
        return dgaAdd(m, op, o, taken);
      case "rename":
        if (arrow) return (arrow.label = dgaText(op.text, 40)), true;
        return Boolean(target) && o.relabel(m, target, dgaText(op.text, 120));
      case "join": {
        const a = dgaFind(m, op.from);
        const b = dgaFind(m, op.to);
        const label = dgaText(op.label, 40);
        return Boolean(a && b && a !== b && o.join(m, a.slice(2), b.slice(2), label ? { label } : {}));
      }
      case "nest": {
        const group = op.group ? dgaFind(m, op.group, "g") : null;
        return Boolean(target && (!op.group || group) && o.move(m, target, group ? group.slice(2) : null, null));
      }
      case "delete":
        if (arrow) return Boolean(o.unjoin(m, arrow));
        return Boolean(target && o.remove(m, target));
      default:
        return false;
    }
  }

  //: The ops played in order on `m`, at most twelve: how many applied and how many were refused.
  function dgaApply(m, list, o) {
    const ops = Array.isArray(list) ? list.slice(0, DGA_MAX_OPS) : [];
    const taken = new Set([...m.nodes.map((n) => n.id), ...m.subgraphs.map((g) => g.id)]);
    let done = 0;
    for (const op of ops) if (dgaOne(m, op, o, taken)) done++;
    return { done, refused: (Array.isArray(list) ? list.length : 0) - done };
  }

  //: What changed between two models: block keys added, removed and changed, and the arrows.
  function dgaDiff(a, b) {
    const out = { added: [], removed: [], changed: [], arrowsAdded: [], arrowsRemoved: [], arrowsChanged: [] };
    const same = { n: (x, y) => x.text === y.text && x.shape === y.shape && (x.group ?? null) === (y.group ?? null), g: (x, y) => x.title === y.title && (x.parent ?? null) === (y.parent ?? null) };
    for (const [type, list] of [["n", "nodes"], ["g", "subgraphs"]]) {
      const before = new Map(a[list].map((x) => [x.id, x]));
      const after = new Map(b[list].map((x) => [x.id, x]));
      for (const [id, x] of after) if (!before.has(id)) out.added.push(`${type}:${id}`);
      else if (!same[type](before.get(id), x)) out.changed.push(`${type}:${id}`);
      for (const id of before.keys()) if (!after.has(id)) out.removed.push(`${type}:${id}`);
    }
    const key = (e) => `${e.from}>${e.to}`;
    const before = new Map(a.edges.map((e) => [key(e), e]));
    const after = new Map(b.edges.map((e) => [key(e), e]));
    for (const [k, e] of after) if (!before.has(k)) out.arrowsAdded.push(e);
    else if ((before.get(k).label || "") !== (e.label || "")) out.arrowsChanged.push(e);
    for (const [k, e] of before) if (!after.has(k)) out.arrowsRemoved.push(e);
    return out;
  }

  //: F7: one picture of both: the newer model with what the older had put back, each mark a colour from `hue`
  //: (`{add, del, chg}`, hex): added green, removed red and dotted, changed amber. The printer writes the fills.
  function dgaMarked(a, b, print, hue) {
    const d = dgaDiff(a, b);
    const u = JSON.parse(JSON.stringify(b));
    u.nodes.forEach((n) => delete n.fill);
    u.edges.forEach((e) => delete e.colour);
    const has = (id) => u.nodes.some((n) => n.id === id) || u.subgraphs.some((g) => g.id === id);
    for (const key of d.removed) {
      const id = key.slice(2);
      if (key[0] === "g") u.subgraphs.push({ ...a.subgraphs.find((g) => g.id === id), parent: null });
    }
    for (const key of d.removed) {
      const n = key[0] === "n" && a.nodes.find((x) => x.id === key.slice(2));
      if (n) u.nodes.push({ ...n, group: has(n.group) ? n.group : null, fill: hue.del });
    }
    for (const e of d.arrowsRemoved) if (has(e.from) && has(e.to)) u.edges.push({ ...e, style: "dotted", colour: hue.del });
    const paint = (key, colour) => {
      const n = key[0] === "n" && u.nodes.find((x) => x.id === key.slice(2));
      if (n) n.fill = colour;
    };
    d.added.forEach((k) => paint(k, hue.add));
    d.changed.forEach((k) => paint(k, hue.chg));
    const arrowKey = (e) => `${e.from}>${e.to}`;
    const marks = new Map([...d.arrowsAdded.map((e) => [arrowKey(e), hue.add]), ...d.arrowsChanged.map((e) => [arrowKey(e), hue.chg])]);
    u.edges.forEach((e) => marks.has(arrowKey(e)) && e.style !== "dotted" && (e.colour = marks.get(arrowKey(e))));
    const groupLines = [...d.added.map((k) => [k, hue.add]), ...d.removed.map((k) => [k, hue.del]), ...d.changed.map((k) => [k, hue.chg])].filter(([k]) => k[0] === "g").map(([k, c]) => `  style ${k.slice(2)} stroke:${c},stroke-width:2px`);
    return { source: print(u) + groupLines.map((l) => `${l}\n`).join(""), diff: d };
  }

  //: A block's words for a sentence: the model's words for an id, else the name as given.
  const dgaWords = (m, ref) => {
    const key = dgaFind(m, ref);
    const id = key ? key.slice(2) : "";
    return m.nodes.find((n) => n.id === id)?.text ?? m.subgraphs.find((g) => g.id === id)?.title ?? dgaText(ref, 60);
  };

  //: One line per op, in the words of the model before it ran: "Add Refund after In stock? (No)".
  function dgaSay(m, op) {
    const w = (ref) => dgaWords(m, ref);
    if (op.op === "add") return op.shape === "group" ? `Add the group ${dgaText(op.text, 60)}` : `Add ${dgaText(op.text, 60)}${op.after ? ` after ${w(op.after)}` : ""}${op.label ? ` (${dgaText(op.label, 40)})` : ""}`;
    if (op.op === "rename") return op.target ? `Rename ${w(op.target)} to ${dgaText(op.text, 60)}` : `Label the arrow from ${w(op.from)} to ${w(op.to)} ${dgaText(op.text, 40)}`;
    if (op.op === "join") return `Join ${w(op.from)} to ${w(op.to)}${op.label ? ` (${dgaText(op.label, 40)})` : ""}`;
    if (op.op === "nest") return op.group ? `Move ${w(op.target)} into ${w(op.group)}` : `Take ${w(op.target)} out of its group`;
    if (op.op === "delete") return op.target ? `Remove ${w(op.target)}` : `Remove the arrow from ${w(op.from)} to ${w(op.to)}`;
    return "";
  }

  //: The version's name (F7): "AI: added Refund", and how many more changes came with it.
  function dgaName(m, list) {
    const first = dgaSay(m, list[0] || {});
    if (!first) return "AI: changed the diagram";
    const past = first.replace(/^Add /, "added ").replace(/^Rename /, "renamed ").replace(/^Label /, "labelled ").replace(/^Join /, "joined ").replace(/^Move /, "moved ").replace(/^Take /, "took ").replace(/^Remove /, "removed ");
    const more = list.length - 1;
    return `AI: ${past}${more ? ` and ${more} more change${more === 1 ? "" : "s"}` : ""}`.slice(0, 120);
  }

  //: F6: what the lint finds, each with the ops its Apply runs: `{key, text, act, ops}`, twenty at most.
  function dgaLint(m, o) {
    const out = [];
    const outs = (id) => m.edges.filter((e) => e.from === id);
    const ins = (id) => m.edges.filter((e) => e.to === id);
    const ending = (n) => ["stadium", "circle"].includes(n.shape) || /^(end|done|finish|finished|stop|complete|completed)$/.test(dgaFold(n.text));
    for (const e of m.edges) {
      if (!o.needsLabel(m, e)) continue;
      const word = o.branchWord(m, e);
      out.push({ key: `n:${e.from}`, text: `An arrow out of ${dgaWords(m, e.from)} has no words.`, act: `Label it ${word}`, ops: [{ op: "rename", from: e.from, to: e.to, text: word }] });
    }
    m.nodes.forEach((n, i) => {
      const away = outs(n.id);
      if (n.shape === "diamond" && away.length === 1) {
        const word = /^no$/i.test(away[0].label || "") ? "yes" : "no";
        out.push({ key: `n:${n.id}`, text: `${n.text} has one way out; its ${word} branch leads off the diagram.`, act: `Add the ${word} step`, ops: [{ op: "add", text: "End", shape: "stadium", after: n.id, label: word }] });
      } else if (!away.length && ins(n.id).length && n.shape !== "diamond" && !ending(n)) {
        out.push({ key: `n:${n.id}`, text: `${n.text} has no way out.`, act: "Add an end after it", ops: [{ op: "add", text: "End", shape: "stadium", after: n.id, label: "" }] });
      } else if (!away.length && !ins(n.id).length && m.nodes.length > 1) {
        const near = m.nodes[i - 1] || m.nodes[i + 1];
        out.push({ key: `n:${n.id}`, text: `${n.text} is not joined to anything.`, act: `Join it from ${near.text}`, ops: [{ op: "join", from: near.id, to: n.id, label: "" }] });
      }
    });
    //: One row for a name used again, with one action that numbers them all (INBOX 1771: four identical "Two blocks say Step." rows).
    //: The numbers skip a name another block already has, so the rename never makes a new pair.
    const same = new Map();
    for (const n of m.nodes) {
      const f = dgaFold(n.text);
      if (f && !ending(n)) same.set(f, [...(same.get(f) || []), n]);
    }
    const WORDS = ["", "", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten"];
    for (const group of same.values()) {
      if (group.length < 2) continue;
      const mine = new Set(group);
      const taken = new Set(m.nodes.filter((x) => !mine.has(x)).map((x) => dgaFold(x.text)));
      let k = 0;
      const ops = group.slice(0, DGA_MAX_OPS).map((n) => {
        let name;
        do name = `${group[0].text} ${++k}`;
        while (taken.has(dgaFold(name)));
        return { op: "rename", target: n.id, text: name };
      });
      const count = WORDS[group.length] || String(group.length);
      out.push({ key: `n:${group[0].id}`, text: `${count} blocks say ${group[0].text}.`, act: `Number them ${group[0].text} 1 to ${k}`, ops });
    }
    for (const g of m.subgraphs) {
      const held = m.nodes.filter((n) => n.group === g.id).length + m.subgraphs.filter((x) => x.parent === g.id).length;
      if (held === 1) out.push({ key: `g:${g.id}`, text: `The group ${g.title} holds one block.`, act: "Remove the group", ops: [{ op: "delete", target: g.id }] });
    }
    return out.slice(0, 20);
  }

  //: Suggestions for the other kinds (L-documents-21): the same `{key, text, act}` rows, each with the `drop` (a block's uid) its Apply
  //: removes. A mind map holds `children`, a sequence `steps` and a timeline `periods` then `events`; the kind's own printer writes the result.
  const dgaKids = (n) => n.children || n.steps || n.periods || n.events || [];
  function dgaKindLint(kind, m) {
    const out = [];
    const row = (drop, text, act) => out.push({ key: drop, text, act, drop });
    const walk = (list, fn) => list.forEach((n) => (fn(n), walk(dgaKids(n), fn)));
    if (kind === "mindmap") {
      walk(m.root ? [m.root] : [], (n) => {
        const seen = new Set();
        for (const c of n.children || []) {
          const f = dgaFold(c.text);
          if (!f && !c.children.length) row(c.uid, `${n.text} has a branch with no words.`, "Remove the empty branch");
          else if (seen.has(f) && !c.children.length) row(c.uid, `${n.text} has ${c.text} twice.`, "Remove the second");
          seen.add(f);
        }
      });
    } else if (kind === "timeline") {
      const periods = (list) => list.forEach((p) => p.events.length || row(p.uid, `${dgaText(p.when, 60) || "A period"} has no events.`, "Remove the period"));
      periods(m.free);
      for (const s of m.sections) s.periods.length ? periods(s.periods) : row(s.uid, `The section ${dgaText(s.title, 60)} has no periods.`, "Remove the section");
    } else if (kind === "sequence") {
      const used = new Set();
      walk(m.steps, (s) => {
        if (s.type === "m") used.add(s.from).add(s.to);
        else if (s.type === "t") s.who.forEach((w) => used.add(w));
        else if (s.type === "b" && !s.steps.length) row(s.uid, `The ${s.kw} block holds no steps.`, "Remove the block");
      });
      for (const p of m.participants) used.has(p.id) || row(p.uid, `${dgaText(p.label, 60)} never sends or receives a message.`, "Remove the participant");
    }
    return out.slice(0, 20);
  }

  //: The model without the block `uid`, on a copy.
  function dgaKindDrop(m, uid) {
    const next = JSON.parse(JSON.stringify(m));
    const cut = (list) => {
      const at = list.findIndex((n) => n.uid === uid);
      return at >= 0 ? !!list.splice(at, 1) : list.some((n) => cut(dgaKids(n)));
    };
    [next.participants, next.free, next.sections, next.steps, next.root ? [next.root] : null].some((list) => list && cut(list));
    return next;
  }

  const diagramAiPure = { find: dgaFind, apply: dgaApply, diff: dgaDiff, marked: dgaMarked, say: dgaSay, name: dgaName, lint: dgaLint, kindLint: dgaKindLint, kindDrop: dgaKindDrop, MAX_OPS: DGA_MAX_OPS };
  // DIAGRAM-AI-END

  const copyOf = (m) => JSON.parse(JSON.stringify(m));
  const hues = () => ({ add: CATEGORY_PALETTE.green, del: CATEGORY_PALETTE.red, chg: CATEGORY_PALETTE.amber });
  const VERSIONS = "ph:clock-counter-clockwise Versions…";

  function el(tag, cls, text) {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text != null) node.textContent = text;
    return node;
  }

  //: The page this pane is a document on, or null in a dialog (a Live figure, a board): versions are the document's.
  const docOf = (S) => (S.io.key && typeof currentDoc !== "undefined" && currentDoc?.id === S.io.key ? currentDoc.id : null);

  function draw(fig, source) {
    fig.replaceChildren();
    return ensureModule("mermaid").then((ok) => ok && mermaidFill(fig, source));
  }

  //: The counts line under a compare or a preview: "1 block and 1 arrow added, 1 block changed".
  function counts(d) {
    const some = (n, word) => (n ? `${n} ${word}${n === 1 ? "" : "s"}` : "");
    const parts = [[d.added, d.arrowsAdded, "added"], [d.removed, d.arrowsRemoved, "removed"], [d.changed, d.arrowsChanged, "changed"]]
      .map(([blocks, arrows, verb]) => [some(blocks.length, "block"), some(arrows.length, "arrow")].filter(Boolean).join(" and ") + ` ${verb}`)
      .filter((part) => /^\d/.test(part));
    return parts.length ? parts.join(", ") : "No change";
  }

  // --- the Ask box, the preview and Suggestions -------------------------------------------------------
  function build(S, h) {
    const A = { S, h, ops: null, next: null };
    const box = el("section", "dgm-ai");
    box.setAttribute("aria-label", "Ask and suggestions");
    const form = el("form", "search-field dgm-ai-form");
    const icon = el("i", "ph ph-sparkle search-field-icon");
    icon.setAttribute("aria-hidden", "true");
    A.input = el("input", "search-field-input");
    //: The pane is narrow beside the picture (224 px at 1440): the example is the title, the placeholder two words.
    Object.assign(A.input, { type: "text", maxLength: 300, autocomplete: "off", placeholder: "Ask for a change", title: `For example: ${{ mindmap: "add Rent under Budget, or rename Hiring to Recruiting", timeline: "add event Launch under 2024, or add section Plans", sequence: "add participant Bank, or add message Pay from Shop to Bank" }[S.k?.name] || "add Refund after In stock? No, or rename Warehouse to Fulfilment"}` });
    A.input.setAttribute("aria-label", "Ask for a change to the diagram");
    const send = A.send = smallButton("ph:paper-plane-right", "Ask (Enter)", () => {}, false);
    send.type = "submit";
    send.classList.add("accent", "dgm-ai-send");
    form.append(icon, A.input, send);
    form.addEventListener("submit", (event) => (event.preventDefault(), ask(A)));
    A.preview = el("div", "dgm-ai-preview hidden");
    A.preview.setAttribute("role", "group");
    A.preview.setAttribute("aria-label", "Proposed change");
    A.said = el("p", "dgm-ai-said text-sm");
    A.list = el("ul", "dgm-ai-changes");
    A.fig = el("figure", "dgm-ai-fig");
    const foot = el("div", "dgm-ai-foot");
    const apply = smallButton("ph:check Apply", "Apply this change (one undo step)", () => applyPreview(A), false);
    apply.classList.add("accent");
    foot.append(apply, smallButton("ph:x Discard", "Leave the diagram as it is", () => discard(A)));
    A.preview.append(A.said, A.list, A.fig, foot);
    A.toggle = el("button", "ghost disclosure-row dgm-ai-lints-head");
    A.toggle.type = "button";
    //: The disclosure recipe (DESIGN.md): the caret is `.contents-caret` and turns with `aria-expanded`, as Recent runs and History do.
    A.words = el("span", "dgm-ai-lints-words", "Suggestions");
    const caret = el("i", "ph ph-caret-down contents-caret");
    caret.setAttribute("aria-hidden", "true");
    A.toggle.append(caret, A.words);
    A.toggle.setAttribute("aria-expanded", "false");
    A.lints = el("ul", "dgm-ai-lints hidden");
    A.lints.id = `dgm-ai-lints-${Math.random().toString(36).slice(2, 8)}`;
    A.toggle.setAttribute("aria-controls", A.lints.id);
    A.toggle.addEventListener("click", () => {
      const open = A.toggle.getAttribute("aria-expanded") !== "true";
      A.toggle.setAttribute("aria-expanded", String(open));
      A.lints.classList.toggle("hidden", !open);
    });
    box.append(form, A.preview, A.toggle, A.lints);
    S.pane.prepend(box);
    (S.fig.onpaint ||= []).push(() => lint(A));
    lint(A);
    return A;
  }

  async function ask(A) {
    const { S } = A;
    const words = A.input.value.trim();
    if (!words) return A.h.say(S, "Write what to change first.");
    if (S.k) return askKind(A, words);
    const model = { nodes: S.m.nodes.map((n) => ({ id: n.id, text: String(n.text).slice(0, 200), shape: n.shape, group: n.group ?? null })), edges: S.m.edges.map((e) => ({ from: e.from, to: e.to, label: String(e.label || "").slice(0, 200) })), subgraphs: S.m.subgraphs.map((g) => ({ id: g.id, title: String(g.title || "").slice(0, 200), parent: g.parent ?? null })) };
    setBusy(A.send, true);
    let reply;
    try {
      reply = await apiJson("/drafts/diagram-ask", { method: "POST", body: JSON.stringify({ ask: words, model }) });
    } catch (error) {
      return A.h.say(S, error.message || "That did not reach the app.");
    } finally {
      setBusy(A.send, false);
    }
    const by = reply.by === "model" ? "Written by the model." : "Read by rule, no model needed.";
    show(A, reply.ops || [], [reply.said, by].filter(Boolean).join(" "));
  }

  //: A mind map, timeline or sequence (L-documents-35): the lazy sibling flattens the blocks, asks, and plays the ops on a copy.
  async function askKind(A, words) {
    const { S } = A;
    setBusy(A.send, true);
    try {
      if (!(await ensureModule("diagramAiKinds"))) return A.h.say(S, "The ask for this kind did not load.");
      const got = await diagramModel.aiKinds.ask(S, words);
      if (got.say) return A.h.say(S, got.say);
      showKind(A, got.next, got.lines, got.said, `AI: ${got.lines[0]}`.slice(0, 120));
    } finally {
      setBusy(A.send, false);
    }
  }

  //: The preview (F7): the ops on a copy, the picture of both, the lines, Apply or Discard.
  function show(A, ops, said) {
    const { S } = A;
    const next = copyOf(S.m);
    const run = diagramAiPure.apply(next, ops, A.h.ops);
    if (!run.done) {
      A.preview.classList.add("hidden");
      return A.h.say(S, said && !ops.length ? said : "Nothing in that could be applied to this diagram.");
    }
    A.ops = ops;
    A.next = next;
    A.list.replaceChildren(...ops.slice(0, diagramAiPure.MAX_OPS).map((op) => el("li", "", diagramAiPure.say(S.m, op))).filter((li) => li.textContent));
    const marked = diagramAiPure.marked(S.m, next, diagramModel.print, hues());
    A.said.textContent = `${counts(marked.diff)}. ${said || ""}`.trim();
    A.preview.classList.remove("hidden");
    draw(A.fig, marked.source);
    A.h.say(S, `Proposed: ${A.list.textContent ? [...A.list.children].map((li) => li.textContent).join("; ") : counts(marked.diff)}. Apply or Discard.`);
    A.preview.querySelector(".dgm-ai-foot button")?.focus();
  }

  function discard(A) {
    A.ops = A.next = A.name = null;
    A.preview.classList.add("hidden");
    A.h.say(A.S, "Discarded. The diagram is as it was.");
    A.input.focus();
  }

  async function applyPreview(A) {
    const { S, h } = A;
    if (!A.next) return;
    const name = A.name || diagramAiPure.name(S.m, A.ops);
    S.m = A.next;
    A.ops = A.next = A.name = null;
    A.preview.classList.add("hidden");
    A.input.value = "";
    h.commit(S, `${name.replace(/^AI: /, "Applied: ")}. Undo puts it back.`);
    const doc = docOf(S);
    if (!doc) return;
    try {
      if (docDirty) await saveDocument({ silent: true });
      await apiJson(`/documents/${doc}/revisions`, { method: "POST", body: JSON.stringify({ name }) });
    } catch (error) {
      toast(error.message || "The change is in, but the version was not named.", true);
    }
  }

  //: A suggestion on another kind: the removal on a copy, the kind's own printer for the picture, then Apply or Discard as for a flowchart.
  function showKind(A, next, lines, said, name) {
    const { S } = A;
    A.ops = [];
    A.next = next;
    A.name = name;
    A.list.replaceChildren(...lines.map((line) => el("li", "", line)));
    A.said.textContent = said;
    A.preview.classList.remove("hidden");
    draw(A.fig, S.k.print(next));
    A.h.say(S, `Proposed: ${lines.join("; ").toLowerCase()}. Apply or Discard.`);
    A.preview.querySelector(".dgm-ai-foot button")?.focus();
  }

  function lint(A) {
    const { S } = A;
    if (!S.m || S.plain) return A.toggle.classList.add("hidden");
    const found = S.k ? diagramAiPure.kindLint(S.k.name, S.m) : diagramAiPure.lint(S.m, A.h.ops);
    A.toggle.classList.toggle("hidden", !found.length);
    A.words.textContent = `Suggestions (${found.length})`;
    A.lints.replaceChildren(...found.map((f) => {
      const li = el("li", "dgm-ai-lint");
      const words = el("span", "dgm-ai-lint-text", f.text);
      li.append(words, rowActions([{ label: f.act, title: `${f.act}: preview the change`, run: () => (S.k ? showKind(A, diagramAiPure.kindDrop(S.m, f.drop), [f.act], "1 block removed.", `AI: ${f.act.charAt(0).toLowerCase()}${f.act.slice(1)}`.slice(0, 120)) : show(A, f.ops, "A suggestion, by rule.")) }], "Suggestion"));
      return li;
    }));
  }

  // --- versions -----------------------------------------------------------------------------------------
  async function versions(S) {
    const doc = docOf(S);
    if (!doc) return;
    if (docDirty) await saveDocument({ silent: true });
    let rows;
    try {
      rows = await apiJson(`/documents/${doc}/revisions`);
    } catch (error) {
      return toast(error.message || "The versions did not load.", true);
    }
    openSheet({
      label: "Versions of this diagram",
      name: "diagram-versions",
      build: (card, close) => {
        card.classList.add("dgm-versions");
        const lead = el("p", "muted text-sm", rows.length ? "Tick two to compare them, or one to compare it with the diagram now." : "No versions yet. Each Apply from Ask or Suggestions names one.");
        const list = el("ul", "dgm-versions-list");
        const picked = [];
        const compare = smallButton("ph:git-diff Compare", "Compare the ticked versions", () => compareThem(S, doc, picked, view), false);
        compare.disabled = true;
        const view = el("div", "dgm-versions-view hidden");
        //: The named versions (an Apply) first, the ordinary saves under their own line, so the few that mean something are not lost among the many (dgai-1110 left).
        const ordered = [...rows.filter((r) => r.name), ...rows.filter((r) => !r.name)];
        for (const row of ordered) {
          if (!row.name && rows.some((r) => r.name) && row === ordered.find((r) => !r.name)) list.append(el("li", "dgm-versions-head muted text-sm", "Saves"));
          const li = el("li", row.name ? "dgm-versions-row" : "dgm-versions-row dgm-versions-save");
          const label = el("label", "dgm-versions-pick");
          const tick = el("input");
          tick.type = "checkbox";
          tick.addEventListener("change", () => {
            if (tick.checked) picked.push(row);
            else picked.splice(picked.indexOf(row), 1);
            while (picked.length > 2) picked.shift().tick.checked = false;
            compare.disabled = !picked.length;
          });
          row.tick = tick;
          label.append(tick, el("span", "dgm-versions-name", row.name || "Saved"), el("span", "muted text-sm", whenText(row.created_at)));
          li.append(label, rowActions([{ label: "Restore", title: "Put the diagram back to this version (Undo takes it back)", run: () => (close(), restoreDocVersionWithUndo(row)) }], "Version"));
          list.append(li);
        }
        //: Named only (L321, as the document history has): shown only when the list holds both kinds. A save that was ticked and is now hidden is unticked, so Compare never uses a row that is not shown.
        const mixed = rows.some((r) => r.name) && rows.some((r) => !r.name);
        const only = el("input");
        only.type = "checkbox";
        only.addEventListener("change", () => {
          list.classList.toggle("dgm-versions-named", only.checked);
          if (only.checked) {
            for (const row of rows.filter((r) => !r.name && r.tick?.checked)) {
              row.tick.checked = false;
              picked.splice(picked.indexOf(row), 1);
            }
            compare.disabled = !picked.length;
          }
        });
        const filter = el("label", "dgm-versions-only text-sm");
        filter.append(only, el("span", "", "Named only"));
        card.append(lead, ...(mixed ? [filter] : []), list, view, compare);
      },
    });
  }

  async function compareThem(S, doc, picked, view) {
    const load = (row) => apiJson(`/documents/${doc}/revisions/${row.id}`).then((full) => full.content || "");
    const older = picked.length === 2 ? [...picked].sort((a, b) => String(a.created_at).localeCompare(String(b.created_at))) : [picked[0], null];
    let texts;
    try {
      texts = await Promise.all(older.map((row) => (row ? load(row) : S.source)));
    } catch (error) {
      return toast(error.message || "That version did not load.", true);
    }
    const [a, b] = texts.map((t) => diagramModel.parse(t));
    view.classList.remove("hidden");
    if (!a || !b) return view.replaceChildren(el("p", "muted", "Compare draws flowcharts; one of these is another kind or cannot be read."));
    const marked = diagramAiPure.marked(a, b, diagramModel.print, hues());
    const legend = el("p", "dgm-versions-legend text-sm");
    legend.append(el("span", "dgm-mark-add", "Added"), el("span", "dgm-mark-del", "Removed"), el("span", "dgm-mark-chg", "Changed"));
    const fig = el("figure", "dgm-ai-fig");
    view.replaceChildren(el("p", "text-sm", `${older[0].name || whenText(older[0].created_at)} to ${older[1] ? older[1].name || whenText(older[1].created_at) : "now"}: ${counts(marked.diff)}.`), legend, fig);
    draw(fig, marked.source);
  }

  //: Every show: the Versions row in the ... menu on a Documents page (the builder rebuilds the menu after), and on a
  //: pane Suggestions, and on a flowchart the Ask box too, built once per pane.
  function wire(S, h) {
    if (docOf(S)) S.io.menu = [...(S.io.menu || []).filter((row) => row.label !== VERSIONS), { label: VERSIONS, run: () => versions(S) }];
    if (S.ai) return;
    S.ai = build(S, h);
  }

  diagramModel.ai = { wire, versions, pure: diagramAiPure };
})();
