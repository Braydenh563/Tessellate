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
// and `super.m(...)`) as a constructor function with its prototype. Also lowered
// (L334): class fields (instance ones as hidden methods the constructor calls;
// static ones and static blocks in place), destructuring in declarations,
// parameters, `for (const [k, v] of xs)` and `[a, b] = [b, a]`, rest parameters,
// and spread in a list, a call and an object. Patterns and spreads read an
// array or a string only (the stepper has no iterators), defaults must be
// plain values, and async, await, generators, private members and getters stay
// named. TypeScript reaches here after sucrase has taken its types.

//: The constructs the pass does not lower, by the parse tree's node name,
//: as the panel names them. A pattern or a spread in a place the pass has no
//: lowering for is refused by name too (`runDebugLower` keeps the places it
//: lowered in `ctx.handled`).
(() => {
  const RUN_DEBUG_REFUSED = {
    PrivatePropertyDefinition: "private class members",
    get: "getters and setters",
    set: "getters and setters",
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
    if (node.name === "ArrayExpression") return runDebugKids(node).every((c) => /^[\[\],]$/.test(c.name) || runDebugPlainDefault(c, source));
    if (node.name === "ObjectExpression") return runDebugKids(node).every((c) => /^[{}]$/.test(source.slice(c.from, c.to)));
    return false;
  }

  //: A pattern or a spread the pass lowered, and the temporaries it makes.
  function runDebugMark(ctx, node) {
    if (node.name === "ObjectPattern" || node.name === "ArrayPattern" || node.name === "Spread") ctx.handled.add(node.from);
    for (let c = node.firstChild; c; c = c.nextSibling) runDebugMark(ctx, c);
  }

  //: A pattern as `name = access` declarators. Returns `{ t, array, list }`:
  //: `t` is the temporary the caller binds to the value (through `__forOf`
  //: when `array`, which only reads an array or a string), `list` what follows.
  //: Defaults must be plain (they are copied, not lowered).
  function runDebugBind(ctx, pat) {
    const { source, refuse } = ctx;
    const text = (n) => source.slice(n.from, n.to);
    const list = [];
    const temp = () => `__d${++ctx.temps}`;
    const t0 = temp();
    const leaf = (node, access) => {
      if (node.name === "VariableDefinition") list.push(`${text(node)} = ${access}`);
      else if (node.name === "ObjectPattern" || node.name === "ArrayPattern") {
        const t = temp();
        list.push(`${t} = ${node.name === "ArrayPattern" ? `__forOf(${(ctx.need.forOf = true, access)})` : access}`);
        fill(node, t);
      } else refuse("destructuring into something other than names", node.from);
    };
    const pick = (parts, i, access) => {
      const eq = parts[i + 1];
      if (!eq || eq.name !== "Equals") return leaf(parts[i], access);
      const value = parts[i + 2];
      if (!value || !runDebugPlainDefault(value, source)) refuse("destructuring defaults other than a plain value (a number, string, name, {} or a list of those)", eq.from);
      const t = temp();
      list.push(`${t} = ${access}`);
      leaf(parts[i], `${t} === undefined ? ${text(value)} : ${t}`);
    };
    const fill = (node, base) => {
      const kids = runDebugKids(node).filter((c) => !/^[\[\]{},]$/.test(c.name));
      if (node.name === "ObjectPattern") {
        const keys = [];
        let computed = false;
        for (const pp of kids) {
          const parts = runDebugKids(pp);
          if (parts[0]?.name === "Spread") {
            if (parts[1]?.name !== "VariableDefinition" || computed) refuse("an object rest in this pattern", pp.from);
            ctx.need.rest = true;
            list.push(`${text(parts[1])} = __rest(${base}, [${keys.join(", ")}])`);
            continue;
          }
          const colon = parts.findIndex((c) => c.name === ":");
          if (colon < 0) {
            keys.push(JSON.stringify(text(parts[0])));
            pick(parts, 0, `${base}.${text(parts[0])}`);
            continue;
          }
          const key = parts[0];
          if (key.name === "[") {
            const k = parts[1];
            if (!k || !/^(?:VariableName|String|Number)$/.test(k.name)) refuse("computed keys other than a name, string or number", k ? k.from : pp.from);
            computed = true;
            pick(parts, colon + 1, `${base}[${text(k)}]`);
          } else if (key.name === "PropertyName") {
            keys.push(JSON.stringify(text(key)));
            pick(parts, colon + 1, `${base}.${text(key)}`);
          } else {
            keys.push(JSON.stringify(String(key.name === "String" ? text(key).slice(1, -1) : text(key))));
            pick(parts, colon + 1, `${base}[${text(key)}]`);
          }
        }
        return;
      }
      //: An array pattern reads by position; a comma with no element is a hole.
      const all = runDebugKids(node).filter((c) => c.name !== "[" && c.name !== "]");
      let idx = 0;
      for (let i = 0; i < all.length; i++) {
        const c = all[i];
        if (c.name === ",") {
          idx += 1;
          continue;
        }
        if (c.name === "Spread") {
          if (all[i + 1]?.name !== "VariableDefinition") refuse("an array rest in this pattern", c.from);
          list.push(`${text(all[i + 1])} = Array.prototype.slice.call(${base}, Math.min(${idx}, ${base}.length))`);
          i += 1;
          continue;
        }
        const next = all[i + 1];
        const span = next && next.name === "Equals" ? 3 : 1;
        pick(all, i, `${base}[${idx}]`);
        i += span - 1;
      }
    };
    fill(pat, t0);
    return { t: t0, array: pat.name === "ArrayPattern", list };
  }

  //: `[k, v] = x` declarators for a bound pattern: its own temporary first.
  function runDebugHead(ctx, b, root) {
    if (b.array) ctx.need.forOf = true;
    return `${b.t} = ${b.array ? `__forOf(${root})` : root}`;
  }

  //: `var {a, b} = o` / `var [a, b] = xs`: the pattern becomes its temporary
  //: and the names follow the initializer as more declarators, on its line.
  function runDebugDeclaration(ctx, node, depth) {
    const kids = runDebugKids(node);
    for (let i = 0; i < kids.length; i++) {
      const p = kids[i];
      if (p.name !== "ObjectPattern" && p.name !== "ArrayPattern") continue;
      const eq = kids[i + 1];
      const init = kids[i + 2];
      if (!eq || eq.name !== "Equals" || !init) ctx.refuse("destructuring with no value", p.from);
      const b = runDebugBind(ctx, p);
      runDebugMark(ctx, p);
      runDebugEdit(ctx.edits, p.from, p.to, b.t, 0);
      if (b.array) {
        ctx.need.forOf = true;
        runDebugEdit(ctx.edits, init.from, init.from, "__forOf(", depth + 1);
        runDebugEdit(ctx.edits, init.to, init.to, ")", -(depth + 1));
      }
      if (b.list.length) runDebugEdit(ctx.edits, init.to, init.to, `, ${b.list.join(", ")}`, 0);
    }
  }

  //: `[a, b] = [b, a]` as a sequence: `(__d1 = __forOf(rhs), a = __d1[0], ...)`.
  //: Its temporaries are declared on line 1.
  function runDebugAssign(ctx, node, depth) {
    const kids = runDebugKids(node);
    const p = kids[0];
    const eq = kids[1];
    const rhs = kids[2];
    if (!p || (p.name !== "ObjectPattern" && p.name !== "ArrayPattern") || !eq || eq.name !== "Equals" || !rhs) return;
    const first = ctx.temps;
    const b = runDebugBind(ctx, p);
    runDebugMark(ctx, p);
    for (let n = first + 1; n <= ctx.temps; n++) ctx.assignTemps.push(`__d${n}`);
    runDebugEdit(ctx.edits, p.from, eq.to, `(${b.t} =${b.array ? " __forOf(" : ""}`, depth);
    if (b.array) ctx.need.forOf = true;
    runDebugEdit(ctx.edits, rhs.to, rhs.to, `${b.array ? ")" : ""}${b.list.map((x) => `, ${x}`).join("")}, ${b.t})`, -depth);
  }

  //: Parameters: `function f(a, b = 2, {c}, ...rest) {` becomes
  //: `function f(a, b, __p1) { if (b === undefined) b = 2; var c = __p1.c; var rest = ...slice.call(arguments, 3);`
  //: on the same line, so every line stays where it was. Returns that text
  //: (the caller puts it at the top of the body).
  function runDebugParams(ctx, params) {
    const { source, edits, refuse } = ctx;
    const text = (n) => source.slice(n.from, n.to);
    const slots = [[]];
    const commas = [];
    for (const c of runDebugKids(params)) {
      if (c.name === "(" || c.name === ")") continue;
      if (c.name === ",") {
        commas.push(c);
        slots.push([]);
      } else slots[slots.length - 1].push(c);
    }
    const lines = [];
    slots.forEach((slot, n) => {
      const first = slot[0];
      if (!first) return;
      if (first.name === "Spread") {
        if (slot[1]?.name !== "VariableDefinition" || n !== slots.length - 1) refuse("rest parameters other than a last plain name", first.from);
        ctx.handled.add(first.from);
        runDebugEdit(edits, n > 0 ? commas[n - 1].from : first.from, slot[1].to, "", 0);
        lines.push(`var ${text(slot[1])} = Array.prototype.slice.call(arguments, Math.min(${n}, arguments.length));`);
        return;
      }
      const isPattern = first.name === "ObjectPattern" || first.name === "ArrayPattern";
      if (first.name !== "VariableDefinition" && !isPattern) refuse("this parameter", first.from);
      const eq = slot[1];
      const value = slot[2];
      if (eq && (eq.name !== "Equals" || !value)) refuse("this parameter", eq.from);
      if (value && !runDebugPlainDefault(value, source)) refuse("default parameter values other than a plain value (a number, string, name, {} or a list of those)", eq.from);
      const name = isPattern ? `__p${++ctx.paramNames}` : text(first);
      if (isPattern) runDebugEdit(edits, first.from, first.to, name, 0);
      if (value) {
        runDebugEdit(edits, isPattern ? first.to : first.to, value.to, "", 0);
        lines.push(`if (${name} === undefined) ${name} = ${text(value)};`);
      }
      if (isPattern) {
        const b = runDebugBind(ctx, first);
        runDebugMark(ctx, first);
        lines.push(`var ${[runDebugHead(ctx, b, name), ...b.list].join(", ")};`);
      }
    });
    return lines.join(" ");
  }

  //: `[a, ...xs, b]` as `[].concat([a], __spr(xs), [b])` and `f(a, ...xs)` as
  //: `f.apply(undefined, [].concat([a], __spr(xs)))`; `recv` is the receiver
  //: a call passes ("this" is the object of `o.m(...xs)`).
  function runDebugSpreadList(ctx, node, open, close, openText, closeText, depth) {
    const { edits, refuse } = ctx;
    const inner = runDebugKids(node).filter((c) => c.from !== open.from && c.from !== close.from);
    const slots = [[]];
    const commas = [];
    for (const c of inner) {
      if (c.name === ",") {
        commas.push(c);
        slots.push([]);
      } else slots[slots.length - 1].push(c);
    }
    if (slots.length > 1 && !slots[slots.length - 1].length) {
      const last = commas.pop();
      slots.pop();
      runDebugEdit(edits, last.from, last.to, "", 0);
    }
    if (slots.some((s) => !s.length)) refuse("spread in a list with holes", node.from);
    runDebugEdit(edits, open.from, open.to, openText, depth);
    runDebugEdit(edits, close.from, close.to, closeText, -depth);
    let run = [];
    const flush = () => {
      if (!run.length) return;
      runDebugEdit(edits, run[0][0].from, run[0][0].from, "[", depth + 1);
      const tail = run[run.length - 1];
      runDebugEdit(edits, tail[tail.length - 1].to, tail[tail.length - 1].to, "]", -(depth + 1));
      run = [];
    };
    for (const slot of slots) {
      if (slot[0].name !== "Spread") {
        run.push(slot);
        continue;
      }
      flush();
      if (slot.length !== 2) refuse("this spread", slot[0].from);
      ctx.need.spr = true;
      ctx.handled.add(slot[0].from);
      runDebugEdit(edits, slot[0].from, slot[0].to, "__spr(", depth + 1);
      runDebugEdit(edits, slot[1].to, slot[1].to, ")", -(depth + 1));
    }
    flush();
  }

  //: `{...a, b: 1}` as `__ospr({}, a, {b: 1})`.
  function runDebugObjectSpread(ctx, node, depth) {
    const { edits } = ctx;
    const open = node.firstChild;
    const close = node.lastChild;
    const props = runDebugKids(node).filter((c) => c.name === "Property");
    if (!props.some((p) => p.firstChild?.name === "Spread")) return;
    const commas = runDebugKids(node).filter((c) => c.name === ",");
    if (commas.length >= props.length && commas.length) {
      const last = commas[commas.length - 1];
      runDebugEdit(edits, last.from, last.to, "", 0);
    }
    ctx.need.ospr = true;
    runDebugEdit(edits, open.from, open.to, "__ospr({}, ", depth);
    runDebugEdit(edits, close.from, close.to, ")", -depth);
    let run = [];
    const flush = () => {
      if (!run.length) return;
      runDebugEdit(edits, run[0].from, run[0].from, "{", depth + 1);
      runDebugEdit(edits, run[run.length - 1].to, run[run.length - 1].to, "}", -(depth + 1));
      run = [];
    };
    for (const p of props) {
      const kid = runDebugKids(p);
      if (kid[0].name !== "Spread") {
        run.push(p);
        continue;
      }
      flush();
      ctx.handled.add(kid[0].from);
      runDebugEdit(edits, kid[0].from, kid[0].to, "", 0);
    }
    flush();
  }

  //: A call whose arguments spread: `f.apply(undefined, [...])`, `o.m.apply(o, [...])`.
  function runDebugSpreadCall(ctx, call, depth) {
    const kids = runDebugKids(call);
    const callee = kids[0];
    const args = kids.find((c) => c.name === "ArgList");
    if (!callee || !args || !runDebugKids(args).some((c) => c.name === "Spread")) return;
    const { source, refuse } = ctx;
    let recv = "undefined";
    if (callee.name === "MemberExpression") {
      const obj = runDebugKids(callee)[0];
      recv = source.slice(obj.from, obj.to);
      if (!/^(?:this|[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*)$/.test(recv)) refuse("spread in a call on something other than a name path (a.b.m(...xs))", callee.from);
    } else if (callee.name !== "VariableName") refuse("spread in a call to something other than a name or a.b.m", callee.from);
    runDebugEdit(ctx.edits, callee.to, callee.to, ".apply", 0);
    const parts = runDebugKids(args);
    runDebugSpreadList(ctx, args, parts[0], parts[parts.length - 1], `(${recv}, [].concat(`, "))", depth + 1);
  }

  //: A class as a constructor function, its methods on the prototype:
  //:   var A = (function () { A.prototype = Object.create(B.prototype); ...
  //:   function A(x) { B.call(this, x); ... }  A.prototype.m = function (q) { ... };
  //:   A.s = function () { ... };  return A; })();
  //: Every edit keeps the line count. Returns what `super` needs to know.
  function runDebugClass(ctx, node, isDeclaration) {
    const { source, edits, refuse } = ctx;
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
    //: Instance fields run as hidden methods (`__f1`, in the class's body, so
    //: the initializer stays where it is and is lowered in place), called from
    //: the constructor: at the top, or after `super(...)` in a derived class.
    const fields = members.filter((m) => m.name === "PropertyDeclaration" && !runDebugKids(m).some((c) => c.name === "static")).map((m) => ({ m, id: ++ctx.fieldIds }));
    const calls = fields.map((f) => `this.__f${f.id}();`).join(" ");
    const header = source.slice(node.from, body.from + 1);
    let open = `${isDeclaration ? `var ${name} = ` : ""}(function () { `;
    if (superName) open += `${name}.prototype = Object.create(${superName}.prototype); ${name}.prototype.constructor = ${name}; `;
    if (!hasCtor) open += `function ${name}() {${superName ? ` ${superName}.apply(this, arguments);` : ""}${calls ? ` ${calls}` : ""} } `;
    runDebugEdit(edits, node.from, body.from + 1, open + "\n".repeat((header.match(/\n/g) || []).length), 0);
    runDebugEdit(edits, body.to - 1, body.to, `return ${name}; })()${isDeclaration ? ";" : ""}`, 0);
    for (const member of members) {
      if (member.name === "StaticBlock") {
        const parts = runDebugKids(member);
        runDebugEdit(edits, parts[0].from, parts[0].to, "(function ()", 0);
        runDebugEdit(edits, member.to, member.to, `).call(${name});`, -1);
        continue;
      }
      if (member.name === "PropertyDeclaration") {
        const parts = runDebugKids(member);
        const def = parts.find((c) => c.name === "PropertyDefinition");
        if (!def) refuse("private class members", member.from);
        const field = source.slice(def.from, def.to);
        if (!/^[A-Za-z_$][\w$]*$/.test(field)) refuse("class members with computed or quoted names", member.from);
        const eq = parts.find((c) => c.name === "Equals");
        const value = eq ? parts[parts.indexOf(eq) + 1] : null;
        const hasValue = value && value.name !== ";";
        const end = hasValue ? value.to : def.to;
        if (parts[0].name === "static") {
          if (hasValue && /\bthis\b/.test(source.slice(value.from, value.to))) refuse("static fields that use this", value.from);
          runDebugEdit(edits, parts[0].from, hasValue ? eq.to : def.to, `${name}.${field} =${hasValue ? "" : " void 0"}`, 0);
        } else {
          const id = fields.find((f) => f.m === member).id;
          runDebugEdit(edits, def.from, hasValue ? eq.to : def.to, `Object.defineProperty(${name}.prototype, "__f${id}", { value: function () { this.${field} =${hasValue ? "" : " void 0"}`, 0);
          runDebugEdit(edits, end, end, "; } });", -1);
        }
        continue;
      }
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
    if (calls) {
      const ctor = members.find((m) => m.name === "MethodDeclaration" && !runDebugKids(m).some((c) => c.name === "static")
        && source.slice(runDebugKids(m).find((c) => c.name === "PropertyDefinition")?.from ?? 0, runDebugKids(m).find((c) => c.name === "PropertyDefinition")?.to ?? 0) === "constructor");
      if (ctor) {
        const block = runDebugKids(ctor).slice(-1)[0];
        if (!superName) runDebugEdit(edits, block.from + 1, block.from + 1, ` ${calls}`, 0);
        else {
          const sup = runDebugKids(block).find((st) => st.name === "ExpressionStatement" && runDebugKids(st)[0]?.name === "CallExpression" && runDebugKids(runDebugKids(st)[0])[0]?.name === "super");
          if (!sup) refuse("class fields in a derived class whose constructor does not call super(...) as a statement", ctor.from);
          runDebugEdit(edits, sup.to, sup.to, ` ${calls}`, 0);
        }
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
    //: What the pass shares with its helpers: patterns and spreads it lowered,
    //: temporaries, and the line-1 helpers a lowering needs.
    const ctx = { source, edits, refuse, handled: new Set(), temps: 0, paramNames: 0, fieldIds: 0, assignTemps: [], need: {}, done: new Set() };
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
        //: The parser recovers from what it cannot read (an arrow whose parameter
        //: is a pattern with a default); lowering that tree would write garbage.
        if (ref.type.isError) refuse("syntax the editor's parser could not read here (an arrow parameter that is a pattern with a default value?)", ref.from);
        if (Object.prototype.hasOwnProperty.call(RUN_DEBUG_REFUSED, name)) refuse(RUN_DEBUG_REFUSED[name], ref.from);
        if (name === "Spread" && !ctx.handled.has(ref.from)) refuse("spread and rest (...) here", ref.from);
        if ((name === "ObjectPattern" || name === "ArrayPattern") && !ctx.handled.has(ref.from)) refuse("destructuring here", ref.from);
        if (name === "VariableDeclaration") runDebugDeclaration(ctx, ref.node, depth);
        if (name === "AssignmentExpression") runDebugAssign(ctx, ref.node, depth);
        if (name === "ObjectExpression") runDebugObjectSpread(ctx, ref.node, depth);
        if (name === "ArrayExpression") {
          const parts = runDebugKids(ref.node);
          if (parts.some((c) => c.name === "Spread")) runDebugSpreadList(ctx, ref.node, parts[0], parts[parts.length - 1], "[].concat(", ")", depth);
        }
        if (name === "CallExpression") runDebugSpreadCall(ctx, ref.node, depth);
        if (name === "UpdateOp" && /^(?:\?\?|&&|\|\|)=$/.test(text())) refuse("logical assignment", ref.from);
        if (name === "UpdateOp" && text() === "**=") refuse("the ** operator", ref.from);
        if (name === "Number" && /[n_]/i.test(text()) && !/^0x/i.test(text())) refuse("BigInt and numeric separators", ref.from);
        if (name === "VariableName" && /^(?:document|window)$/.test(text())) dom = true;
        if (name === "let" || name === "const") runDebugEdit(edits, ref.from, ref.to, "var", 0);
        if (name === "ParamList" && !ctx.done.has(ref.from)) {
          const pre = runDebugParams(ctx, ref.node);
          const fn = ref.node.parent;
          const block = fn ? runDebugKids(fn).slice(-1)[0] : null;
          if (pre && (!block || block.name !== "Block")) refuse("parameter patterns or defaults in an arrow function with no braces", ref.from);
          if (pre) runDebugEdit(edits, block.from + 1, block.from + 1, ` ${pre}`, 0);
        }
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
          let prelude = "";
          if (body.name !== "Block" && params.name === "ParamList") {
            ctx.done.add(params.from);
            prelude = runDebugParams(ctx, params);
          }
          const usesThis = /\bthis\b/.test(source.slice(body.from, body.to));
          if (body.name === "Block") {
            if (usesThis) runDebugEdit(edits, ref.to, ref.to, ".bind(this)", -depth);
          } else {
            runDebugEdit(edits, body.from, body.from, `{ ${prelude ? `${prelude} ` : ""}return (`, depth);
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
          const pattern = kids.find((c) => c.name === "ArrayPattern" || c.name === "ObjectPattern");
          const of = kids.find((c) => c.name === "of");
          const iterable = of ? kids[kids.indexOf(of) + 1] : null;
          const loop = ref.node.parent;
          const body = loop ? runDebugKids(loop).slice(-1)[0] : null;
          if ((!target && !pattern) || !iterable || !body || body === ref.node) refuse("this for...of loop", ref.from);
          needForOf = true;
          loops += 1;
          const i = `__i${loops}`;
          const a = `__a${loops}`;
          let pick = target ? `var ${source.slice(target.from, target.to)} = ${a}[${i}];` : "";
          if (pattern) {
            const b = runDebugBind(ctx, pattern);
            runDebugMark(ctx, pattern);
            pick = `var ${[runDebugHead(ctx, b, `${a}[${i}]`), ...b.list].join(", ")};`;
          }
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
          classes.push(runDebugClass(ctx, ref.node, name === "ClassDeclaration"));
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
    if (ctx.assignTemps.length) runDebugEdit(edits, 0, 0, `var ${ctx.assignTemps.join(", ")}; `, -1e9 + 2);
    if (ctx.need.spr) runDebugEdit(edits, 0, 0, 'function __spr(v) { if (v == null || typeof v.length !== "number") throw new TypeError("Debug steps spread over an array or a string only"); return Array.prototype.slice.call(v); } ', -1e9 + 3);
    if (ctx.need.rest) runDebugEdit(edits, 0, 0, "function __rest(o, ks) { var r = {}; for (var k in o) { if (Object.prototype.hasOwnProperty.call(o, k) && ks.indexOf(k) < 0) r[k] = o[k]; } return r; } ", -1e9 + 4);
    if (ctx.need.ospr) runDebugEdit(edits, 0, 0, "function __ospr(t) { for (var i = 1; i < arguments.length; i++) { var s = arguments[i]; if (s != null) { for (var k in s) { if (Object.prototype.hasOwnProperty.call(s, k)) t[k] = s[k]; } } } return t; } ", -1e9 + 5);
    if (needForOf || ctx.need.forOf) {
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
