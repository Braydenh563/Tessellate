// diagram-ai-kinds.js: the Ask box for a mind map, a timeline and a sequence diagram (L-documents-35). Lazy:
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
  const DAK_TYPES = { mindmap: "rb", timeline: "spe", sequence: "am" };
  const dakSlug = (text) => String(text).replace(/[^\p{L}\p{N}_]+/gu, "_").slice(0, 30) || "P";

  //: The kind's blocks as the flat list the backend reads. Notes, boxes and dividers are not asked about.
  function dakFlatten(A, ko, m) {
    const nodes = [];
    ko.walk(A, m, (n, level, parent) => {
      if (!DAK_TYPES[A.name].includes(n.type) || nodes.length >= 120) return;
      const row = { uid: n.uid, type: n.type, text: String(A.text(n) ?? "").slice(0, 200) };
      if (parent && DAK_TYPES[A.name].includes(parent.type)) row.parent = parent.uid;
      if (n.type === "a") row.id = n.id;
      if (n.type === "m") (row.from = n.from, row.to = n.to);
      nodes.push(row);
    });
    return nodes;
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
        const fields = { mindmap: { text }, timeline: { s: { title: text }, p: { when: text }, e: { text } }[op.type], sequence: op.type === "a" ? { label: text } : { text, from: ids.get(op.from) || op.from, to: ids.get(op.to) || op.to } }[A.name];
        const node = text && fields && (!op.parent || parent) && ko.add(A, m, op.type, { parent, fields });
        if (node) {
          named.set(name, node);
          if (op.type === "a") ids.set(dakSlug(text), node.id);
          ok = true;
          lines.push(op.type === "m" ? `Add the message ${text}` : `Add ${text}`);
        }
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
