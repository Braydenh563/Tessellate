// diagram-ai-kinds.js: the Ask box for a mind map, a timeline, a sequence diagram (L-documents-35), a Gantt chart, a pie chart, a state, a class and an ER diagram (L-documents-86). Lazy:
// `LAZY_MODULES.diagramAiKinds`, asked for by diagram-ai.js's `ask` the first time a non-flowchart pane is asked.
// It flattens the kind's blocks (`{uid, type, text, parent, id, from, to}`), posts them with the kind to
// `POST /drafts/diagram-ask`, and plays the ops it gets back on a copy with the kind's own functions
// (`diagramModel.kinds.ops`: add, relabel, move, remove), so a block lands exactly where the block editor would put it.
// Ops come from outside: one that does not apply is dropped, never forced. The caller previews the copy and commits
// it as one Undo step. Pure region `DIAGRAM-AI-KINDS-BEGIN` to `-END` runs in node (tests).
//
// One closure, one export: `diagramModel.aiKinds`.
(() => {
  // DIAGRAM-AI-KINDS-BEGIN
  const DAK_TYPES = { mindmap: "rb", timeline: "spe", sequence: "am", gantt: "stp", pie: "sp", state: "scx", class: "cmr", er: "ear" };
  //: What each of the five other kinds tells the backend beyond its words: a number or timing, a name to refer to, a relation's two ends.
  const DAK_EXTRA = {
    pie: (n) => (n.type === "s" ? { value: n.value } : {}),
    gantt: (n) => (n.type === "t" ? { value: n.spec } : {}),
    state: (n) => (n.type === "x" ? { from: n.from, to: n.to } : { id: n.id }),
    class: (n) => (n.type === "r" ? { from: n.from, to: n.to } : n.type === "c" ? { id: n.name } : {}),
    er: (n) => (n.type === "r" ? { from: n.from, to: n.to } : n.type === "e" ? { id: n.name } : {}),
  };
  //: A name not yet in `used` (a state's id, a class's or an entity's name), as the asker's words allow.
  const dakFresh = (used, base) => {
    for (let i = 1; ; i++) if (!used.has(i === 1 ? base : `${base}_${i}`)) return i === 1 ? base : `${base}_${i}`;
  };
  const dakSlug = (text) => String(text).replace(/[^\p{L}\p{N}_]+/gu, "_").slice(0, 30) || "P";

  //: The kind's blocks as the flat list the backend reads. Notes, boxes and dividers are not asked about.
  function dakFlatten(A, ko, m) {
    const nodes = [];
    ko.walk(A, m, (n, level, parent) => {
      if (!DAK_TYPES[A.name].includes(n.type) || nodes.length >= 120) return;
      const row = { uid: n.uid, type: n.type, text: String(A.text(n) ?? "").slice(0, 200) };
      if (parent && DAK_TYPES[A.name].includes(parent.type)) row.parent = parent.uid;
      if (A.name === "sequence") {
        if (n.type === "a") row.id = n.id;
        if (n.type === "m") (row.from = n.from, row.to = n.to);
      } else if (DAK_EXTRA[A.name]) Object.assign(row, DAK_EXTRA[A.name](n));
      nodes.push(row);
    });
    return nodes;
  }

  //: The fields a block of `op.type` is made with, from the op's words (and, for a relation, its two ends as the block that holds them).
  function dakFields(A, m, op, text, get, ids) {
    const end = (ref) => (ref === "[*]" ? ref : get(ref)?.id ?? get(ref)?.name ?? null);
    const used = new Set((A.refs ? A.refs(m) : []).map((x) => x.id));
    const rel = { from: end(op.from), to: end(op.to), label: text };
    if (A.name === "mindmap") return { text };
    if (A.name === "timeline") return { s: { title: text }, p: { when: text }, e: { text } }[op.type];
    if (A.name === "sequence") return op.type === "a" ? { label: text } : { text, from: ids.get(op.from) || op.from, to: ids.get(op.to) || op.to };
    if (A.name === "pie") return op.type === "p" ? { key: "title", value: text } : { label: text, value: String(op.value || "10") };
    if (A.name === "gantt") return { s: { title: text }, t: { text, spec: String(op.value || "3d") }, p: { key: "title", value: text } }[op.type];
    if (A.name === "state") {
      const id = dakFresh(used, dakSlug(text).replace(/[^\w.-]/g, "_"));
      return op.type === "x" ? (rel.from && rel.to ? rel : null) : { id, desc: id === text ? null : text };
    }
    if (op.type === "r") return rel.from && rel.to ? (A.name === "er" ? { ...rel, label: text || "has" } : A.name === "class" ? { ...rel, arrow: "-->" } : rel) : null;
    if (A.name === "class") return op.type === "c" ? { name: dakFresh(used, text.replace(/[\s{}":]/g, "")) } : { text };
    return op.type === "e" ? { name: /^[\w-]+$/.test(text) ? dakFresh(used, text) : `"${text.replace(/"/g, "")}"` } : { text };
  }
  //: What a relation said in words for the preview: `a transition from A to B`.
  function dakEnds(A, get, op) {
    const show = (ref) => (ref === "[*]" ? "the start or end" : A.text(get(ref)) ?? "?");
    return `a ${{ state: "transition", er: "relationship" }[A.name] || "relation"} from ${show(op.from)} to ${show(op.to)}`;
  }

  //: The ops played on `m` (a copy the caller owns). Blocks an op adds are named n1, n2 ... in the order added, as the
  //: backend names them, so a later op can hang a block under an earlier one. `{done, lines}`.
  function dakApply(A, ko, m, ops) {
    const named = new Map();
    const byUid = new Map();
    const index = () => (byUid.clear(), ko.walk(A, m, (n) => byUid.set(n.uid, n)));
    const get = (uid) => named.get(uid) || byUid.get(uid);
    const ids = new Map();
    let made = 0;
    let done = 0;
    const lines = [];
        for (const op of Array.isArray(ops) ? ops : []) {
      index();
      const target = get(op.target);
      let ok = false;
      if (op.op === "add") {
        const name = `n${++made}`;
        const parent = op.parent ? get(op.parent) : null;
        const text = String(op.text || "");
        const fields = dakFields(A, m, op, text, get, ids);
        const home = !op.parent && A.name === "gantt" && op.type === "t" ? A.home(m, "t") : null;
        const node = (text || fields?.from != null) && fields && (!op.parent || parent) && ko.add(A, m, op.type, { parent: parent || home, fields });
        if (node) {
          named.set(name, node);
          if (op.type === "a") ids.set(dakSlug(text), node.id);
          ok = true;
          lines.push(fields.from != null && A.name !== "sequence" ? `Add ${text ? `${text}, ` : ""}${dakEnds(A, get, op)}` : op.type === "m" && A.name === "sequence" ? `Add the message ${text}` : `Add ${text}`);
        }
      } else if (op.op === "set" && target && ["gantt", "pie"].includes(A.name)) {
        lines.push(`Set ${A.text(target)} to ${op.value}`);
        delete target.raw;
        if (A.name === "pie") target.value = String(op.value);
        else target.spec = String(op.value);
        ok = true;
      } else if (op.op === "rename" && target) {
        lines.push(`Rename ${A.text(target)} to ${op.text}`);
        ok = ko.relabel(A, m, ko.key(target), op.text);
      } else if (op.op === "move" && target && (!op.parent || get(op.parent))) {
        lines.push(`Move ${A.text(target)}`);
        ok = ko.move(A, m, ko.key(target), op.parent ? ko.key(get(op.parent)) : null);
      } else if (op.op === "delete" && target) {
        lines.push(`Delete ${A.text(target)}`);
        ok = Boolean(ko.remove(A, m, ko.key(target)));
      }
      if (ok) done++;
      else if (lines.length > done) lines.pop();
    }
    return { done, lines };
  }

  // DIAGRAM-AI-KINDS-END

  //: The ask for pane `S`: the reply from the backend, played on a copy. `{say}` when nothing came of it, else `{next, lines, said, by}`.
  async function ask(S, words) {
    const A = S.k;
    const ko = diagramModel.kinds.ops;
    let reply;
    try {
      reply = await apiJson("/drafts/diagram-ask", { method: "POST", body: JSON.stringify({ ask: words, kind: A.name, kind_model: { nodes: dakFlatten(A, ko, S.m) } }) });
    } catch (error) {
      return { say: error.message || "That did not reach the app." };
    }
    const next = JSON.parse(JSON.stringify(S.m));
    const run = dakApply(A, ko, next, reply.ops || []);
    if (!run.done) return { say: reply.said || "Nothing in that could be applied to this diagram." };
    return { next, lines: run.lines, said: [reply.said, reply.by === "model" ? "Written by the model." : "Read by rule, no model needed."].filter(Boolean).join(" ") };
  }

  diagramModel.aiKinds = { ask, pure: { flatten: dakFlatten, apply: dakApply } };
})();
