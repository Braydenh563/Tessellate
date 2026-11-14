// documents-code-lint.js: lint for .js, .ts and .py documents (DOCUMENTS_PLAN 25 row 4, L-documents-50).
//
// **Loaded on the first check of such a file**, by `lazyScript` in documents-code.js, which then calls
// `DOC_LINT_CONFIG.codeLint` (a field of an existing const, so the shared scope gains no name and the boot
// bundle gains no bytes).
//
// **JavaScript and TypeScript: a small in-house pass over CodeMirror's own parse tree**, run only on text the
// tree already calls valid, so it never underlines a half-typed line. No eslint: it is MIT but 3 MB of rules
// and a parser that CodeMirror already has. The rules are the ones that are nearly always a mistake: a
// duplicate key in an object, an assignment where a condition goes, code after a return, a duplicate `case`,
// a comparison with NaN (never true), and a `typeof` compared with a word it never gives.
//
// **Python: Ruff** (`@astral-sh/ruff-wasm-web`, MIT), the optional "Python lint (Ruff)" extra. Its 10 MB wasm is
// over the 5 MB line for vendoring, so it is downloaded on an Install click and served from the data folder
// (`/documents/ruff/`), then imported here on the first Python check. The rules E4, E7, E9 and F (syntax, imports,
// undefined names) run; its own fix is offered where it has one. Not installed: no underlines and no request
// more than once in half a minute.
(() => {
  const LEVELS = { warning: "warning", error: "error" };
  const TYPEOF = new Set(["undefined", "object", "boolean", "number", "bigint", "string", "symbol", "function"]);
  const NEVER_RETURNS = new Set(["ReturnStatement", "ThrowStatement", "BreakStatement", "ContinueStatement"]);
  const TEST_PARENT = new Set(["IfStatement", "WhileStatement", "DoStatement"]);

  const found = (out, from, to, message, key) => out.push({ from, to: Math.max(to, from + 1), severity: LEVELS.warning, source: "Lint", message, key });

  function js(CM, state) {
    const tree = CM.language.syntaxTree(state);
    const out = [];
    const text = (n) => state.sliceDoc(n.from, n.to);
    const keyOf = (prop) => {
      const first = prop.firstChild;
      if (!first || first.name === "[" || first.name === "Spread") return null;
      if (first.name === "PropertyDefinition") return text(first);
      if (first.name === "String") return text(first).slice(1, -1);
      return null;
    };
    const isNumberOrString = (n) => n && (n.name === "Number" || n.name === "String");
    tree.iterate({
      enter(ref) {
        const name = ref.name;
        if (name === "ObjectExpression") {
          const seen = new Map();
          for (let c = ref.node.firstChild; c; c = c.nextSibling) {
            if (c.name !== "Property") continue;
            const key = keyOf(c);
            if (key === null) continue;
            //: A getter and a setter share a name on purpose; the word before the name says which.
            const kind = /^\s*(get|set)\s/.exec(state.sliceDoc(c.from, c.to).slice(0, 5))?.[1] || "";
            const id = `${kind}:${key}`;
            if (seen.has(id)) found(out, c.from, c.from + (c.firstChild ? c.firstChild.to - c.from : 1), `Duplicate key “${key}”: the later value replaces the earlier one`, "dup-key");
            else seen.set(id, true);
          }
        } else if (TEST_PARENT.has(ref.node.parent?.name) && name === "ParenthesizedExpression") {
          //: `if (a = b)`; one more pair of parentheses, `if ((a = b))`, is the usual way to say it is meant.
          const inner = ref.node.firstChild?.nextSibling;
          if (inner && inner.name === "AssignmentExpression" && inner.getChild("Equals")) {
            found(out, inner.from, inner.to, "An assignment where a condition goes: did you mean ===? Wrap it in another pair of parentheses if it is meant", "assign-in-test");
          }
        } else if (name === "Block" || name === "SwitchBody") {
          let dead = false;
          for (let c = ref.node.firstChild; c; c = c.nextSibling) {
            if (c.name === "{" || c.name === "}" || c.name === "CaseLabel" || c.name === "DefaultLabel" || c.name === "LineComment" || c.name === "BlockComment") {
              //: A label starts reachable code again.
              if (c.name === "CaseLabel" || c.name === "DefaultLabel") dead = false;
              continue;
            }
            if (dead && c.name !== "FunctionDeclaration" && c.name !== "ClassDeclaration" && c.name !== "EmptyStatement") {
              found(out, c.from, c.to, "This code can never run: the statement above it leaves the block", "unreachable");
              dead = false;
            }
            if (NEVER_RETURNS.has(c.name)) dead = true;
          }
          if (name === "SwitchBody") {
            const seen = new Set();
            for (let c = ref.node.firstChild; c; c = c.nextSibling) {
              if (c.name !== "CaseLabel") continue;
              const label = state.sliceDoc(c.from, c.to).replace(/^case\s*/, "").replace(/\s*:$/, "");
              if (seen.has(label)) found(out, c.from, c.to, `Duplicate case ${label}: the earlier one runs`, "dup-case");
              else seen.add(label);
            }
          }
        } else if (name === "BinaryExpression") {
          const op = ref.node.getChild("CompareOp");
          if (!op || !/^[!=]=/.test(text(op))) return;
          const left = ref.node.firstChild;
          const right = op.nextSibling;
          if (!left || !right) return;
          const isNaN = (n) => n.name === "VariableName" && text(n) === "NaN";
          if (isNaN(left) || isNaN(right)) found(out, ref.from, ref.to, "Nothing equals NaN, not even NaN: use Number.isNaN(x)", "nan-compare");
          const typeofSide = left.name === "UnaryExpression" && /^typeof\b/.test(text(left)) ? right : right.name === "UnaryExpression" && /^typeof\b/.test(text(right)) ? left : null;
          if (typeofSide && typeofSide.name === "String" && !TYPEOF.has(text(typeofSide).slice(1, -1))) {
            found(out, typeofSide.from, typeofSide.to, `typeof never gives ${text(typeofSide)}: it gives one of ${[...TYPEOF].join(", ")}`, "typeof-word");
          }
          if (isNumberOrString(left) && isNumberOrString(right) && text(left) === text(right)) found(out, ref.from, ref.to, "Both sides are the same value, so this is always the same answer", "self-compare");
        }
      },
    });
    return out;
  }

  //: Ruff, loaded once. `ready` is whether the extra is installed: a yes is kept, a no is asked again after half a minute.
  const RUFF = { workspace: null, loading: null, asked: 0, ready: false };

  async function ruffReady() {
    if (RUFF.workspace) return true;
    if (!RUFF.ready) {
      if (Date.now() - RUFF.asked < 30000) return false;
      RUFF.asked = Date.now();
      const body = await apiJson("/extras", { silent: true }).catch(() => null);
      RUFF.ready = Boolean(body?.extras?.find((e) => e.id === "ruff")?.installed);
      if (!RUFF.ready) return false;
    }
    RUFF.loading = RUFF.loading || (async () => {
      const mod = await DOC_LINT_CONFIG.codeLint.load();
      RUFF.workspace = new mod.Workspace({ lint: { select: ["E4", "E7", "E9", "F"] } }, mod.PositionEncoding.Utf16);
    })().catch(() => {
      //: A load that failed is forgotten so the next check tries again, a half minute on.
      RUFF.loading = null;
      RUFF.ready = false;
    });
    await RUFF.loading;
    return Boolean(RUFF.workspace);
  }

  async function py(CM, state) {
    if (!(await ruffReady())) return [];
    let rows;
    try {
      rows = RUFF.workspace.check(docStr(state.doc));
    } catch {
      return [];
    }
    const doc = state.doc;
    const at = (loc) => {
      const row = Math.min(Math.max(loc.row, 1), doc.lines);
      const line = doc.line(row);
      return Math.min(line.from + Math.max(loc.column - 1, 0), line.to);
    };
    return rows.slice(0, 100).map((r) => {
      const from = at(r.start_location);
      const to = Math.max(at(r.end_location), from + 1);
      const edits = r.fix ? r.fix.edits.map((e) => ({ from: at(e.location), to: at(e.end_location), insert: e.content || "" })) : [];
      const label = r.fix && r.fix.message ? r.fix.message : "Apply Ruff's fix";
      return {
        from,
        to: Math.min(to, doc.length),
        severity: r.code && /^(E9|F82|F63|F7)/.test(r.code) ? "error" : "warning",
        source: r.code ? `Ruff ${r.code}` : "Ruff",
        message: r.message,
        key: `ruff:${r.code}`,
        actions: edits.length
          ? [{ name: label, apply: (view, start) => view.dispatch({ changes: edits.map((e) => ({ from: e.from + (start - from), to: e.to + (start - from), insert: e.insert })) }) }]
          : [],
      };
    });
  }

  //: A dynamic import is the one way a classic script reaches a module; the path is this server's own. A field
  //: so a test can hand over a stand-in for the 10 MB wasm.
  async function load() {
    const mod = await import("/documents/ruff/ruff_wasm.js");
    await mod.default({ module_or_path: "/documents/ruff/ruff_wasm_bg.wasm" });
    return mod;
  }

  DOC_LINT_CONFIG.codeLint = { js, py, load };
})();
