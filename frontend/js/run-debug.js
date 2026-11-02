// run-debug.js: JavaScript for the debugger (DOCUMENTS_PLAN 23, D3).
//
// Lazy, in the `run` bundle (`LAZY_MODULES.run` in app.js) with run-core.js.
//
// **Why a pass at all.** Debug steps a script with JS-Interpreter, which reads
// ES5. Run keeps the worker's native engine, so a script that runs may still
// use syntax the stepper cannot read. The commonest of it is lowered here,
// on CodeMirror's own JavaScript parse tree (`CM6.javascript`), with every
// line kept where it was so a stop's line is the document's: `let` and
// `const` become `var`, an arrow function a function expression (bound to
// `this` when its body says `this`), a template string a concatenation, a
// shorthand property or method its long form. What is left that ES5 cannot
// say is named, with its line, and Debug does not start: Run still runs the
// file as it is. Also lowered (data-1011): `**` as Math.pow, `??` through one
// temporary, `for (x of array)` as an indexed loop (an array or a string; the
// stepper has no iterators), a simple default parameter as a first line of
// the body, and a class (methods, static methods, `extends`, `super(...)`
// and `super.m(...)`) as a constructor function with its prototype. TypeScript reaches here after sucrase has taken its types.

//: The constructs the pass does not lower, by the parse tree's node name,
//: as the panel names them.
(() => {
  const RUN_DEBUG_REFUSED = {
    PropertyDeclaration: "class fields",
    StaticBlock: "class static blocks",
    PrivatePropertyDefinition: "private class members",
    get: "getters and setters",
    set: "getters and setters",
    Spread: "spread and rest (...)",
    ObjectPattern: "destructuring",
    ArrayPattern: "destructuring",
    AwaitExpression: "async functions and await",
    async: "async functions and await",
    YieldExpression: "generators",
    Star: "generators",
    TaggedTemplateExpression: "tagged templates",
    ImportDeclaration: "import and export",
    ExportDeclaration: "import and export",
    NewTarget: "new.target",
    "?.": "optional chaining (?.)",
  };

  //: An edit of the pass: replace `from` to `to` with `text`. `rank` orders
  //: two edits at one place: an outer construct opens before an inner one and
  //: closes after it.
  function runDebugEdit(edits, from, to, text, rank) {
    edits.push({ from, to, text, rank });
  }

  //: The text of a template string's literal part as a quoted string, its
  //: line breaks kept as line breaks (a closing quote, a plus, the break, an
  //: opening quote) so every line after it keeps its number.
  function runDebugQuote(raw) {
    const cooked = raw.replace(/\\`/g, "`").replace(/\\\$/g, "$");
    return cooked.split("\n").map((part) => part.replace(/"/g, '\\"').replace(/\r$/, "")).join('\\n" +\n"');
  }

  function runDebugKids(node) {
    const kids = [];
    for (let c = node.firstChild; c; c = c.nextSibling) kids.push(c);
    return kids;
  }

  //: A default value moved to the body must be one that needs no lowering of
  //: its own, since the pass edits text where it stands.
  const RUN_DEBUG_PLAIN_DEFAULT = new Set(["Number", "String", "Boolean", "null", "VariableName", "this"]);

  function runDebugPlainDefault(node, source) {
    if (RUN_DEBUG_PLAIN_DEFAULT.has(node.name)) return true;
    if (node.name === "UnaryExpression") return runDebugKids(node).every((c) => c.name === "ArithOp" || c.name === "Number");
    if (node.name === "ArrayExpression" || node.name === "ObjectExpression") return runDebugKids(node).every((c) => /^[\[\]{}]$/.test(source.slice(c.from, c.to)));
    return false;
  }

  //: `function f(a, b = 2) {` becomes `function f(a, b) { if (b === undefined) b = 2;`
  //: on the same line, so every line stays where it was.
  function runDebugDefaults(params, source, edits, refuse, depth) {
    const kids = runDebugKids(params);
    const defaults = [];
    for (let i = 0; i < kids.length; i++) {
      if (kids[i].name !== "Equals") continue;
      const target = kids[i - 1];
      const value = kids[i + 1];
      if (!target || target.name !== "VariableDefinition" || !value) refuse("default parameter values", kids[i].from);
      if (!runDebugPlainDefault(value, source)) refuse("default parameter values other than a plain value (a number, string, name, [] or {})", kids[i].from);
      defaults.push({ name: source.slice(target.from, target.to), value: source.slice(value.from, value.to), cut: [target.to, value.to] });
    }
    if (!defaults.length) return;
    const fn = params.parent;
    const body = fn ? runDebugKids(fn).slice(-1)[0] : null;
    if (!body || body.name !== "Block") refuse("default parameter values in an arrow function with no braces", params.from);
    for (const d of defaults) runDebugEdit(edits, d.cut[0], d.cut[1], "", 0);
    const lines = defaults.map((d) => `if (${d.name} === undefined) ${d.name} = ${d.value};`).join(" ");
    runDebugEdit(edits, body.from + 1, body.from + 1, ` ${lines}`, 0);
  }

  //: A class as a constructor function, its methods on the prototype:
  //:   var A = (function () { A.prototype = Object.create(B.prototype); ...
  //:   function A(x) { B.call(this, x); ... }  A.prototype.m = function (q) { ... };
  //:   A.s = function () { ... };  return A; })();
  //: Every edit keeps the line count. Returns what `super` needs to know.
  function runDebugClass(node, source, edits, refuse, isDeclaration) {
    const kids = runDebugKids(node);
    const nameNode = kids.find((c) => c.name === "VariableDefinition");
    const name = nameNode ? source.slice(nameNode.from, nameNode.to) : "__Class";
    const ext = kids.find((c) => c.name === "extends");
    const superNode = ext ? kids[kids.indexOf(ext) + 1] : null;
    if (superNode && !/^[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*$/.test(source.slice(superNode.from, superNode.to))) {
      refuse("a class that extends something other than a name", superNode.from);
    }
    const superName = superNode ? source.slice(superNode.from, superNode.to) : "";
    const body = kids.find((c) => c.name === "ClassBody");
    if (!body) refuse("this class", node.from);
    const members = runDebugKids(body).filter((c) => c.name !== "{" && c.name !== "}" && c.name !== ";");
    const hasCtor = members.some((m) => m.name === "MethodDeclaration" && !runDebugKids(m).some((c) => c.name === "static")
      && source.slice(runDebugKids(m).find((c) => c.name === "PropertyDefinition")?.from ?? 0, runDebugKids(m).find((c) => c.name === "PropertyDefinition")?.to ?? 0) === "constructor");
    const header = source.slice(node.from, body.from + 1);
    let open = `${isDeclaration ? `var ${name} = ` : ""}(function () { `;
    if (superName) open += `${name}.prototype = Object.create(${superName}.prototype); ${name}.prototype.constructor = ${name}; `;
    if (!hasCtor) open += `function ${name}() {${superName ? ` ${superName}.apply(this, arguments);` : ""} } `;
    runDebugEdit(edits, node.from, body.from + 1, open + "\n".repeat((header.match(/\n/g) || []).length), 0);
    runDebugEdit(edits, body.to - 1, body.to, `return ${name}; })()${isDeclaration ? ";" : ""}`, 0);
    for (const member of members) {
      if (member.name !== "MethodDeclaration") refuse(RUN_DEBUG_REFUSED[member.name] || "this class member", member.from);
      const parts = runDebugKids(member);
      const def = parts.find((c) => c.name === "PropertyDefinition");
      const isStatic = parts.some((c) => c.name === "static");
      const block = parts[parts.length - 1];
      const first = parts[0];
      if (!def || !/^[A-Za-z_$][\w$]*$/.test(source.slice(def.from, def.to)) || parts.some((c) => c.name === "[")) {
        refuse("class members with computed or quoted names", member.from);
      }
      const method = source.slice(def.from, def.to);
      if (method === "constructor" && !isStatic) {
        runDebugEdit(edits, def.from, def.to, `function ${name}`, 0);
      } else {
        const start = isStatic ? first.from : def.from;
        runDebugEdit(edits, start, def.to, `${name}${isStatic ? "" : ".prototype"}.${method} = function`, 0);
        runDebugEdit(edits, block.to, block.to, ";", 0);
      }
    }
    return { name, superName };
  }

  //: `super(a)` is `B.call(this, a)`; `super.m(a)` is `B.prototype.m.call(this, a)`
  //: (`B.m.call` in a static method).
  function runDebugSuperCall(call, source, edits, refuse, cls) {
    const kids = runDebugKids(call);
    const head = kids[0];
    const args = kids.find((c) => c.name === "ArgList");
    if (!head || !args) return;
    const empty = runDebugKids(args).every((c) => c.name === "(" || c.name === ")");
    const lead = empty ? "this" : "this, ";
    if (head.name === "super") {
      if (!cls.superName) refuse("super() in a class with no extends", head.from);
      runDebugEdit(edits, head.from, head.to, `${cls.superName}.call`, 0);
      runDebugEdit(edits, args.from + 1, args.from + 1, lead, 0);
    } else if (head.name === "MemberExpression" && runDebugKids(head)[0]?.name === "super") {
      if (!cls.superName) refuse("super.method() in a class with no extends", head.from);
      let inStatic = false;
      for (let p = call.parent; p; p = p.parent) {
        if (p.name === "MethodDeclaration") { inStatic = runDebugKids(p).some((c) => c.name === "static"); break; }
      }
      const sup = runDebugKids(head)[0];
      runDebugEdit(edits, sup.from, sup.to, inStatic ? cls.superName : `${cls.superName}.prototype`, 0);
      runDebugEdit(edits, head.to, head.to, ".call", 0);
      runDebugEdit(edits, args.from + 1, args.from + 1, lead, 0);
    }
  }

  //: Lower `source` for JS-Interpreter. Returns `{ code, dom }` (`dom`: the
  //: script reaches for `document` or `window`); throws an Error with `line`
  //: naming the first construct it cannot lower.
  function runDebugLower(source) {
    const CM = window.CM6;
    if (!CM?.javascript) throw new Error("The editor's JavaScript parser is not loaded.");
    const tree = CM.javascript.javascriptLanguage.parser.parse(source);
    const lineAt = (pos) => source.slice(0, pos).split("\n").length;
    const refuse = (what, pos) => {
      const error = new Error(`Debug cannot step ${what} yet (line ${lineAt(pos)}): Run runs this file as it is.`);
      error.line = lineAt(pos);
      throw error;
    };
    const edits = [];
    let depth = 0;
    let dom = false;
    //: The classes being lowered, innermost last; helpers a lowering needs on
    //: line 1 (`var __nc` for `??`, `__forOf` for `for...of`) and a loop count.
    const classes = [];
    const powDone = new Set();
    let needNc = false;
    let needForOf = false;
    let loops = 0;
    tree.iterate({
      enter(ref) {
        depth += 1;
        const name = ref.name;
        const text = () => source.slice(ref.from, ref.to);
        if (Object.prototype.hasOwnProperty.call(RUN_DEBUG_REFUSED, name)) refuse(RUN_DEBUG_REFUSED[name], ref.from);
        if (name === "UpdateOp" && /^(?:\?\?|&&|\|\|)=$/.test(text())) refuse("logical assignment", ref.from);
        if (name === "UpdateOp" && text() === "**=") refuse("the ** operator", ref.from);
        if (name === "Number" && /[n_]/i.test(text()) && !/^0x/i.test(text())) refuse("BigInt and numeric separators", ref.from);
        if (name === "VariableName" && /^(?:document|window)$/.test(text())) dom = true;
        if (name === "let" || name === "const") runDebugEdit(edits, ref.from, ref.to, "var", 0);
        if (name === "ParamList") runDebugDefaults(ref.node, source, edits, refuse, depth);
        if (name === "Property") {
          const kids = [];
          for (let c = ref.node.firstChild; c; c = c.nextSibling) kids.push(c);
          if (kids[0]?.name === "[") refuse("computed property names", ref.from);
          const def = kids[0]?.name === "PropertyDefinition" ? kids[0] : null;
          if (def && kids.length === 1) runDebugEdit(edits, def.to, def.to, `: ${source.slice(def.from, def.to)}`, 0);
          if (def && kids[1]?.name === "ParamList") runDebugEdit(edits, def.to, def.to, ": function", 0);
        }
        if (name === "ArrowFunction") {
          const kids = [];
          for (let c = ref.node.firstChild; c; c = c.nextSibling) kids.push(c);
          const arrow = kids.find((c) => c.name === "Arrow");
          const params = kids[0];
          const body = kids[kids.length - 1];
          if (!arrow || !params || !body || body === arrow) refuse("this arrow function", ref.from);
          //: `x => ...` is a ParamList too, without its brackets.
          if (params.name === "ParamList" && source[params.from] === "(") {
            runDebugEdit(edits, params.from, params.from, "function ", depth);
          } else {
            runDebugEdit(edits, params.from, params.from, "function (", depth);
            runDebugEdit(edits, params.to, params.to, ")", -depth);
          }
          runDebugEdit(edits, arrow.from, arrow.to, "", 0);
          const usesThis = /\bthis\b/.test(source.slice(body.from, body.to));
          if (body.name === "Block") {
            if (usesThis) runDebugEdit(edits, ref.to, ref.to, ".bind(this)", -depth);
          } else {
            runDebugEdit(edits, body.from, body.from, "{ return (", depth);
            runDebugEdit(edits, body.to, body.to, `); }${usesThis ? ".bind(this)" : ""}`, -depth);
          }
        }
        if (name === "BinaryExpression") {
          const kids = runDebugKids(ref.node);
          const op = kids[1];
          if (op && op.name === "ArithOp" && source.slice(op.from, op.to) === "**" && !powDone.has(`${ref.from}:${ref.to}`)) {
            //: The parse tree groups a chain to the left; `**` groups to the
            //: right (2 ** 3 ** 2 is 2 ** 9), so the whole chain is read flat
            //: and written as nested Math.pow calls, once, from its outer node.
            const operands = [];
            const ops = [];
            let at = ref.node;
            for (;;) {
              const parts = runDebugKids(at);
              powDone.add(`${at.from}:${at.to}`);
              operands.unshift(parts[2]);
              ops.unshift(parts[1]);
              const left = parts[0];
              const lp = left.name === "BinaryExpression" ? runDebugKids(left) : null;
              if (lp && lp[1] && lp[1].name === "ArithOp" && source.slice(lp[1].from, lp[1].to) === "**") at = left;
              else {
                operands.unshift(left);
                break;
              }
            }
            for (let i = 0; i < ops.length; i++) {
              runDebugEdit(edits, operands[i].from, operands[i].from, "Math.pow(", depth);
              runDebugEdit(edits, ops[i].from, ops[i].to, ",", 0);
            }
            runDebugEdit(edits, ref.to, ref.to, ")".repeat(ops.length), -depth);
          }
          if (op && op.name === "LogicOp" && source.slice(op.from, op.to) === "??") {
            needNc = true;
            runDebugEdit(edits, ref.from, ref.from, "((__nc = ", depth);
            runDebugEdit(edits, op.from, op.to, ") != null ? __nc : ", 0);
            runDebugEdit(edits, ref.to, ref.to, ")", -depth);
          }
        }
        if (name === "ForOfSpec") {
          const kids = runDebugKids(ref.node);
          const target = kids.find((c) => c.name === "VariableDefinition");
          if (!target && kids.some((c) => c.name === "ArrayPattern" || c.name === "ObjectPattern")) refuse("destructuring", ref.from);
          const of = kids.find((c) => c.name === "of");
          const iterable = of ? kids[kids.indexOf(of) + 1] : null;
          const loop = ref.node.parent;
          const body = loop ? runDebugKids(loop).slice(-1)[0] : null;
          if (!target || !iterable || !body || body === ref.node) refuse("this for...of loop", ref.from);
          needForOf = true;
          loops += 1;
          const i = `__i${loops}`;
          const a = `__a${loops}`;
          const pick = `var ${source.slice(target.from, target.to)} = ${a}[${i}];`;
          runDebugEdit(edits, ref.from, iterable.from, `(var ${i} = 0, ${a} = __forOf(`, 0);
          runDebugEdit(edits, iterable.to, ref.to, `); ${i} < ${a}.length; ${i}++)`, 0);
          if (body.name === "Block") {
            runDebugEdit(edits, body.from + 1, body.from + 1, ` ${pick}`, 0);
          } else {
            runDebugEdit(edits, body.from, body.from, `{ ${pick} `, depth);
            runDebugEdit(edits, body.to, body.to, " }", -depth);
          }
        }
        if (name === "ClassDeclaration" || name === "ClassExpression") {
          classes.push(runDebugClass(ref.node, source, edits, refuse, name === "ClassDeclaration"));
        }
        if (name === "CallExpression" && classes.length) runDebugSuperCall(ref.node, source, edits, refuse, classes[classes.length - 1]);
        if (name === "MemberExpression" && classes.length && ref.node.firstChild?.name === "super") {
          const parentName = ref.node.parent?.name;
          if (parentName !== "CallExpression") refuse("super property access", ref.from);
        }
        if (name === "TemplateString") {
          let at = ref.from + 1;
          runDebugEdit(edits, ref.from, ref.from + 1, '("', depth);
          for (let c = ref.node.firstChild; c; c = c.nextSibling) {
            if (c.name === "Interpolation") {
              runDebugEdit(edits, at, c.from, runDebugQuote(source.slice(at, c.from)), 0);
              const start = c.firstChild;
              const end = c.lastChild;
              if (start?.name === "InterpolationStart") runDebugEdit(edits, start.from, start.to, '" + (', depth);
              if (end?.name === "InterpolationEnd") runDebugEdit(edits, end.from, end.to, ') + "', -depth);
              at = c.to;
            }
          }
          runDebugEdit(edits, at, ref.to - 1, runDebugQuote(source.slice(at, ref.to - 1)), 0);
          runDebugEdit(edits, ref.to - 1, ref.to, '")', -depth);
        }
      },
      leave(ref) {
        depth -= 1;
        if (ref.name === "ClassDeclaration" || ref.name === "ClassExpression") classes.pop();
      },
    });
    if (needNc) runDebugEdit(edits, 0, 0, "var __nc; ", -1e9);
    if (needForOf) {
      runDebugEdit(edits, 0, 0, 'function __forOf(v) { if (v == null || typeof v.length !== "number") throw new TypeError("Debug steps for...of over an array or a string only"); return v; } ', -1e9 + 1);
    }
    //: Applied in one pass, front to back. At one place the ranks order them:
    //: an inner construct's closing (most negative) first, then an outer one's,
    //: then a plain replacement (0), then the openings, outer before inner.
    edits.sort((a, b) => a.from - b.from || a.rank - b.rank);
    let out = "";
    let pos = 0;
    for (const edit of edits) {
      if (edit.from < pos) continue;
      out += source.slice(pos, edit.from) + edit.text;
      pos = edit.to;
    }
    return { code: out + source.slice(pos), dom };
  }

  //: The file's whole surface: what other files and the stand-ins call (ranked row 37a).
  Object.assign(window, { runDebugLower });
})();
