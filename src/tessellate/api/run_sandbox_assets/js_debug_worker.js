
(function () {
  "use strict";
  var I = Interpreter, interp = null, breaks = {}, watches = [], seen = new WeakSet();
  var mode = "continue", base = 0, last = null, paused = null, finished = false, thrown = null, builtins = null;
  var STEP_BUDGET = 4000, REPR = 200, NAMES = 200;
  //: A statement is where a line stops, as a line is where VS Code stops.
  var SKIP = { BlockStatement: 1, FunctionDeclaration: 1, EmptyStatement: 1 };
  function isStatement(node) {
    return /(?:Statement|Declaration)$/.test(node.type) && !SKIP[node.type];
  }
  function own(o, k) { return Object.prototype.hasOwnProperty.call(o, k); }
  //: A value as the panel shows it: short, never the interpreter's insides.
  function show(v, depth) {
    depth = depth || 0;
    if (v === undefined) return "undefined";
    if (v === null) return "null";
    if (typeof v === "string") return depth ? JSON.stringify(v) : JSON.stringify(v);
    if (typeof v !== "object") return String(v);
    if (!(v instanceof I.Object)) return String(v);
    var p = v.properties || {};
    if (v.class === "Function") {
      var n = v.node && v.node.id ? v.node.id.name : "";
      return "function " + n + "()";
    }
    if (v.class === "Error") return String(interp.getProperty(v, "name") || "Error") + ": " + String(interp.getProperty(v, "message") || "");
    if (v.class === "RegExp" || v.class === "Date") return String(v.data);
    if (v.gs) return "Generator {}";
    if (p.__st !== undefined) return "Promise { " + (p.__st === 0 ? "<pending>" : (p.__st === 2 ? "<rejected> " : "") + show(p.__v, depth + 1)) + " }";
    if (depth > 1) return v.class === "Array" ? "[...]" : "{...}";
    var parts = [];
    if (v.class === "Array") {
      var len = Number(p.length) || 0;
      for (var i = 0; i < Math.min(len, 50); i++) parts.push(show(p[i], depth + 1));
      if (len > 50) parts.push("...");
      return clip("[" + parts.join(", ") + "]");
    }
    for (var k in p) {
      if (!own(p, k)) continue;
      parts.push(k + ": " + show(p[k], depth + 1));
      if (parts.length >= 30) { parts.push("..."); break; }
    }
    return clip("{" + parts.join(", ") + "}");
  }
  function clip(t) { t = String(t); return t.length <= REPR ? t : t.slice(0, REPR - 3) + "..."; }
  function kind(v) {
    if (v === null) return "null";
    if (v instanceof I.Object) return v.class === "Function" ? "function" : v.class === "Array" ? "array" : "object";
    return typeof v;
  }
  //: A list or an object opens into its children (OPEN row 1058), CHILDREN at
  //: most, and a child that is one opens in turn, DEPTH levels down with
  //: DEEPER rows each level (L312). A value already on the way down (an
  //: object holding itself) keeps its short form, so the walk ends.
  var CHILDREN = 50, DEEPER = 20, DEPTH = 3;
  function children(v, depth, path) {
    depth = depth || 1; path = path || [];
    if (!(v instanceof I.Object) || (v.class !== "Array" && v.class !== "Object")) return null;
    var p = v.properties || {}, rows = [], total = 0, limit = depth === 1 ? CHILDREN : DEEPER, way = path.concat([v]);
    function row(name, item) {
      var r = { name: name, value: clip(show(item, 1)), type: kind(item) };
      var kids = depth < DEPTH && way.indexOf(item) < 0 ? children(item, depth + 1, way) : null;
      if (kids) r.children = kids;
      return r;
    }
    if (v.class === "Array") {
      total = Number(p.length) || 0;
      for (var i = 0; i < Math.min(total, limit); i++) rows.push(row("[" + i + "]", p[i]));
    } else {
      if (v.gs) return null;
      for (var k in p) {
        if (!own(p, k) || (p.__st !== undefined && k.indexOf("__") === 0)) continue;
        total++;
        if (rows.length < limit) rows.push(row(k, p[k]));
      }
    }
    if (total > limit) rows.push({ name: "...", value: (total - limit) + " more", type: "" });
    return rows.length ? rows : null;
  }
  function names(props, skip) {
    var rows = [];
    for (var k in props) {
      if (!own(props, k) || (skip && skip[k]) || k.indexOf("__") === 0) continue;
      var row = { name: k, value: clip(show(props[k])), type: kind(props[k]) };
      var kids = children(props[k]);
      if (kids) row.children = kids;
      rows.push(row);
      if (rows.length >= NAMES) break;
    }
    return rows;
  }
  //: The call stack from the interpreter's own state stack: a call whose body
  //: is running opens a frame; every state with a location moves its frame's
  //: line, so a caller's line is its call and the top frame's is the stop.
  function frames(stack) {
    var out = [{ name: "(top level)", line: null, scope: interp.getGlobalScope() }];
    for (var i = 0; i < stack.length; i++) {
      var s = stack[i], n = s.node, top = out[out.length - 1];
      if (n.loc && n.end) {
        top.line = n.loc.start.line;
        if (s.scope) top.scope = s.scope;
      }
      //: The helpers below (promises, generators, spread) are the debugger's:
      //: their calls are not frames of the program.
      if ((n.type === "CallExpression" || n.type === "NewExpression") && s.doneExec_ && s.func_ && s.func_.node && s.func_.node.end) {
        var fn = s.func_.node;
        out.push({ name: (fn.id && fn.id.name) || "(anonymous)", line: top.line, scope: s.scope });
      }
    }
    return out.reverse();
  }
  //: A watch, or a breakpoint's condition, evaluated against the stopped
  //: frame's variables: a name resolves through the frame's scopes to the
  //: interpreter's value, made native; anything else is this worker's own
  //: global (Math, JSON). Read-only by intent: it runs natively, not stepped.
  function evaluate(expr, scope) {
    function find(k) {
      for (var s = scope; s; s = s.parentScope) if (own(s.object.properties, k)) return s;
      return null;
    }
    var view = new Proxy({}, {
      has: function (t, k) { return typeof k === "string" && !!find(k); },
      get: function (t, k) {
        if (typeof k !== "string") return undefined;
        var s = find(k);
        if (!s) return undefined;
        var v = s.object.properties[k];
        try { return interp.pseudoToNative(v); } catch (e) { return v; }
      },
    });
    return Function("__mmScope", "with (__mmScope) { return (" + expr + "\n); }")(view);
  }
  //: A watch's value is a native value (the proxy hands code real objects), so
  //: it opens by the same rule over plain arrays and objects.
  function nativeChildren(v, depth, path) {
    depth = depth || 1; path = path || [];
    if (!v || typeof v !== "object" || (!Array.isArray(v) && Object.getPrototypeOf(v) !== Object.prototype)) return null;
    var keys = Object.keys(v), limit = depth === 1 ? CHILDREN : DEEPER, way = path.concat([v]), rows = [];
    keys.slice(0, limit).forEach(function (k) {
      var item = v[k], r = { name: Array.isArray(v) ? "[" + k + "]" : k, value: showNative(item), type: item === null ? "null" : Array.isArray(item) ? "array" : typeof item };
      var kids = depth < DEPTH && way.indexOf(item) < 0 ? nativeChildren(item, depth + 1, way) : null;
      if (kids) r.children = kids;
      rows.push(r);
    });
    if (keys.length > limit) rows.push({ name: "...", value: (keys.length - limit) + " more", type: "" });
    return rows.length ? rows : null;
  }
  function showNative(r) {
    if (typeof r === "string") return clip(JSON.stringify(r));
    if (r && typeof r === "object") { try { return clip(JSON.stringify(r)); } catch (e) { return clip(String(r)); } }
    return clip(String(r));
  }
  function snapshot(reason, fr, line, text) {
    var top = fr[0], locals = [], globals = [];
    var global = interp.getGlobalScope();
    if (fr.length > 1) {
      for (var s = top.scope; s && s !== global; s = s.parentScope) locals = locals.concat(names(s.object.properties, { "this": 1, arguments: 1 }));
      globals = names(global.object.properties, builtins);
    } else {
      locals = names(global.object.properties, builtins);
    }
    var w = [];
    for (var i = 0; i < watches.length; i++) {
      try {
        var got = evaluate(watches[i], top.scope), entry = { expr: watches[i], value: showNative(got) };
        var kids = nativeChildren(got);
        if (kids) entry.children = kids;
        w.push(entry);
      }
      catch (e) { w.push({ expr: watches[i], error: String(e && e.name || "Error") + ": " + String(e && e.message || e) }); }
    }
    return {
      t: "stop", reason: reason, line: line, text: text || "",
      locals: locals, globals: globals, watches: w,
      stack: fr.map(function (f) { return { name: f.name, line: f.line }; }),
    };
  }
  function lineNow() {
    var stack = interp.getStateStack();
    for (var i = stack.length - 1; i >= 0; i--) if (stack[i].node.loc && stack[i].node.end) return stack[i].node.loc.start.line;
    return null;
  }
  //: Console rows, with the line that called them.
  function fmt(v) { return typeof v === "string" ? v : show(v); }
  //: Ordinary ES5, read by the interpreter itself ahead of the program: the
  //: helpers the lowering pass calls (spread, rest, for...of, `new` with a
  //: spread, tagged templates), a Promise, and the drivers of an async
  //: function and `yield*`. Its nodes carry no `end`, so the interpreter runs
  //: through it in one go, the stepper never stops in it and its calls are not frames of the program.
  function POLY() {
    var g = this;
    function drain(v, what) {
      if (v == null) throw new TypeError("Debug steps " + what + " over an array or a string only, or a generator");
      if (typeof v.length === "number") return v;
      if (typeof v.next !== "function") throw new TypeError("Debug steps " + what + " over an array or a string only, or a generator");
      var out = [], r;
      while (!(r = v.next()).done) out.push(r.value);
      return out;
    }
    g.__spr = function (v) { return Array.prototype.slice.call(drain(v, "spread")); };
    g.__forOf = function (v) { return drain(v, "destructuring"); };
    g.__iter = function (v) {
      if (v != null && typeof v.length !== "number" && typeof v.next === "function") return v;
      if (v == null || typeof v.length !== "number") throw new TypeError("Debug steps for...of over an array or a string only, or a generator");
      var i = 0;
      return { next: function () { return i < v.length ? { value: v[i++], done: false } : { value: undefined, done: true }; } };
    };
    g.__rest = function (o, ks) { var r = {}; for (var k in o) { if (Object.prototype.hasOwnProperty.call(o, k) && ks.indexOf(k) < 0) r[k] = o[k]; } return r; };
    g.__ospr = function (t) { for (var i = 1; i < arguments.length; i++) { var s = arguments[i]; if (s != null) { for (var k in s) { if (Object.prototype.hasOwnProperty.call(s, k)) t[k] = s[k]; } } } return t; };
    g.__tt = function (c, r) { c.raw = r; return c; };
    g.__new = function (F, a) {
      switch (a.length) {
        case 0: return new F();
        case 1: return new F(a[0]);
        case 2: return new F(a[0], a[1]);
        case 3: return new F(a[0], a[1], a[2]);
        case 4: return new F(a[0], a[1], a[2], a[3]);
        case 5: return new F(a[0], a[1], a[2], a[3], a[4]);
        case 6: return new F(a[0], a[1], a[2], a[3], a[4], a[5]);
        case 7: return new F(a[0], a[1], a[2], a[3], a[4], a[5], a[6]);
      }
      var o = Object.create(F.prototype), r = F.apply(o, a);
      return r !== null && typeof r === "object" ? r : o;
    };
    g.__yieldStar = function (it) {
      it = g.__iter(it);
      var r, sent;
      while (!(r = it.next(sent)).done) sent = g.__yield(r.value);
      return r.value;
    };
    g.String.raw = function (s) {
      var out = s.raw[0];
      for (var i = 1; i < s.raw.length; i++) out += (i < arguments.length ? String(arguments[i]) : "") + s.raw[i];
      return out;
    };
    function settle(p, st, v) {
      p.__st = st; p.__v = v;
      var q = p.__q;
      p.__q = [];
      if (st === 2 && !q.length) g.__unhandled(p);
      for (var i = 0; i < q.length; i++) react(p, q[i]);
    }
    function react(p, h) {
      g.__micro(function () {
        var cb = p.__st === 1 ? h.ok : h.no, out;
        if (typeof cb !== "function") { if (p.__st === 1) adopt(h.p, p.__v); else settle(h.p, 2, p.__v); return; }
        try { out = cb(p.__v); } catch (e) { settle(h.p, 2, e); return; }
        adopt(h.p, out);
      });
    }
    function adopt(p, v) {
      if (v === p) { settle(p, 2, new TypeError("Chaining cycle detected for promise")); return; }
      if (v !== null && (typeof v === "object" || typeof v === "function")) {
        var then;
        try { then = v.then; } catch (e) { settle(p, 2, e); return; }
        if (typeof then === "function") {
          g.__micro(function () {
            var once = false;
            try {
              then.call(v, function (x) { if (!once) { once = true; adopt(p, x); } }, function (e) { if (!once) { once = true; settle(p, 2, e); } });
            } catch (e) { if (!once) { once = true; settle(p, 2, e); } }
          });
          return;
        }
      }
      settle(p, 1, v);
    }
    function Promise(executor) {
      if (!(this instanceof Promise)) throw new TypeError("Promise constructor cannot be invoked without 'new'");
      if (typeof executor !== "function") throw new TypeError("Promise resolver " + executor + " is not a function");
      this.__st = 0; this.__v = undefined; this.__q = [];
      var self = this, once = false;
      try {
        executor(function (v) { if (!once) { once = true; adopt(self, v); } }, function (e) { if (!once) { once = true; settle(self, 2, e); } });
      } catch (e) { if (!once) { once = true; settle(self, 2, e); } }
    }
    Promise.prototype.then = function (ok, no) {
      var child = new Promise(function () {}), h = { ok: ok, no: no, p: child };
      if (this.__st === 0) this.__q.push(h);
      else { if (this.__st === 2) g.__handled(this); react(this, h); }
      return child;
    };
    Promise.prototype["catch"] = function (no) { return this.then(undefined, no); };
    Promise.prototype["finally"] = function (f) {
      return this.then(function (v) { return Promise.resolve(f()).then(function () { return v; }); },
        function (e) { return Promise.resolve(f()).then(function () { throw e; }); });
    };
    Promise.resolve = function (v) { return v instanceof Promise ? v : new Promise(function (res) { res(v); }); };
    Promise.reject = function (e) { return new Promise(function (res, rej) { rej(e); }); };
    function each(xs, fn) {
      var list = Array.prototype.slice.call(drain(xs, "Promise combinators")), out = new Array(list.length), left = list.length;
      return { list: list, out: out, left: left };
    }
    Promise.all = function (xs) {
      return new Promise(function (res, rej) {
        var e = each(xs), n = e.left;
        if (!n) return res([]);
        e.list.forEach(function (x, i) { Promise.resolve(x).then(function (v) { e.out[i] = v; if (--n === 0) res(e.out); }, rej); });
      });
    };
    Promise.allSettled = function (xs) {
      return new Promise(function (res) {
        var e = each(xs), n = e.left;
        if (!n) return res([]);
        e.list.forEach(function (x, i) {
          Promise.resolve(x).then(function (v) { e.out[i] = { status: "fulfilled", value: v }; if (--n === 0) res(e.out); },
            function (r) { e.out[i] = { status: "rejected", reason: r }; if (--n === 0) res(e.out); });
        });
      });
    };
    Promise.race = function (xs) {
      return new Promise(function (res, rej) { each(xs).list.forEach(function (x) { Promise.resolve(x).then(res, rej); }); });
    };
    Promise.any = function (xs) {
      return new Promise(function (res, rej) {
        var e = each(xs), n = e.left;
        if (!n) return rej(new Error("All promises were rejected"));
        e.list.forEach(function (x, i) {
          Promise.resolve(x).then(res, function (r) { e.out[i] = r; if (--n === 0) { var err = new Error("All promises were rejected"); err.errors = e.out; rej(err); } });
        });
      });
    };
    g.Promise = Promise;
    g.__async = function (self, fn) {
      var gen = g.__gen(self, fn);
      return new Promise(function (res, rej) {
        function step(how, arg) {
          var r;
          try { r = gen[how](arg); } catch (e) { rej(e); return; }
          if (r.done) { res(r.value); return; }
          Promise.resolve(r.value).then(function (v) { step("next", v); }, function (e) { step("throw", e); });
        }
        step("next");
      });
    };
  }

  //: Generators (and async functions, which are generators a promise drives).
  //: The interpreter keeps its call stack as data, so a generator is a slice
  //: of it: `next` pushes the slice back above the call, `yield` takes it off
  //: again and hands the call its value. A marker state sits under the slice
  //: so a body that returns is told from one that yields.
  var unhandled = [];
  function coroutines(it, g) {
    function result(v, done) {
      var o = it.createObjectProto(it.OBJECT_PROTO);
      it.setProperty(o, "value", v);
      it.setProperty(o, "done", done);
      return o;
    }
    it.stepFunctions_.GenFrame_ = function (stack, state) {
      var st = state.gen;
      stack.pop();
      st.done = true; st.running = false; st.frames = null;
      stack[stack.length - 1].value = result(state.value, true);
    };
    function resume(gen, how, v) {
      var st = gen && gen.gs, stack = it.getStateStack(), call = stack[stack.length - 1];
      if (!st) it.throwException(it.TYPE_ERROR, how + " method called on incompatible receiver");
      if (st.running) it.throwException(it.TYPE_ERROR, "Generator is already running");
      if (st.done || (!st.started && how !== "next")) {
        st.done = true;
        if (how === "throw") it.throwException(v);
        return result(how === "return" ? v : undefined, true);
      }
      if (how === "return") { st.done = true; st.frames = null; return result(v, true); }
      st.running = true;
      if (!st.started) {
        st.started = true;
        var mark = new I.State({ type: "GenFrame_", end: 1 }, call.scope), node = it.newNode(), at = new I.State(node, call.scope);
        mark.gen = st;
        node.type = "CallExpression";
        at.doneCallee_ = 2; at.funcThis_ = st.self; at.func_ = st.fn; at.doneArgs_ = true; at.arguments_ = [];
        stack.push(mark, at);
        return undefined;
      }
      var frames = st.frames;
      st.frames = null;
      for (var i = 0; i < frames.length; i++) stack.push(frames[i]);
      if (how === "throw") it.throwException(v);
      frames[frames.length - 1].value = v;
      return undefined;
    }
    var proto = it.createObjectProto(it.OBJECT_PROTO);
    ["next", "return", "throw"].forEach(function (how) {
      it.setProperty(proto, how, it.createNativeFunction(function (v) { return resume(this, how, v); }), I.NONENUMERABLE_DESCRIPTOR);
    });
    it.setProperty(g, "__gen", it.createNativeFunction(function (self, fn) {
      var gen = it.createObjectProto(proto);
      gen.gs = { self: self, fn: fn, started: false, done: false, running: false, frames: null };
      return gen;
    }));
    it.setProperty(g, "__yield", it.createNativeFunction(function (v) {
      var stack = it.getStateStack(), m = stack.length - 1;
      while (m >= 0 && stack[m].node.type !== "GenFrame_") m--;
      if (m < 1) it.throwException(it.SYNTAX_ERROR, "yield or await outside a generator or an async function");
      var st = stack[m].gen;
      st.frames = stack.splice(m);
      st.running = false;
      stack[stack.length - 1].value = result(v, false);
    }));
    //: A reaction runs before any timer: a task due since the start of time,
    //: queued behind the ones already waiting.
    it.setProperty(g, "__micro", it.createNativeFunction(function (fn) {
      var node = it.newNode(), task = new I.Task(fn, [], it.globalScope, node, -1), at = 0;
      node.type = "CallExpression";
      task.time = 0;
      while (at < it.tasks.length && it.tasks[at].time === 0) at++;
      it.tasks.splice(at, 0, task);
    }));
    //: A rejection nothing has caught by the time the program is idle is
    //: reported, as node does.
    it.setProperty(g, "__unhandled", it.createNativeFunction(function (p) { unhandled.push(p); }));
    it.setProperty(g, "__handled", it.createNativeFunction(function (p) {
      var at = unhandled.indexOf(p);
      if (at >= 0) unhandled.splice(at, 1);
    }));
    it.polyfills_.push("(" + POLY + ").call(this);");
  }

  function init(it, g) {
    var con = it.nativeToPseudo({});
    ["log", "info", "warn", "error", "debug"].forEach(function (k) {
      it.setProperty(con, k, it.createNativeFunction(function () {
        var parts = [];
        for (var i = 0; i < arguments.length; i++) parts.push(fmt(arguments[i]));
        postMessage({ t: "log", level: k, text: parts.join(" "), line: lineNow() });
      }));
    });
    it.setProperty(g, "console", con);
    coroutines(it, g);
    if (DOM) stubDocument(it, g);
  }
  //: Scripts that use the DOM debug against a stand-in: every element is a
  //: plain object whose methods do nothing and whose finders hand back
  //: another stand-in, so the script's own logic can be stepped. The app
  //: says so in a row; nothing is drawn.
  function stubDocument(it, g) {
    function noop() { return undefined; }
    function element(tag) {
      var el = it.nativeToPseudo({ tagName: String(tag || "div").toUpperCase(), id: "", className: "", textContent: "", innerHTML: "", value: "", checked: false, style: {}, dataset: {} });
      var cls = it.nativeToPseudo({});
      ["add", "remove", "toggle"].forEach(function (k) { it.setProperty(cls, k, it.createNativeFunction(noop)); });
      it.setProperty(cls, "contains", it.createNativeFunction(function () { return false; }));
      it.setProperty(el, "classList", cls);
      ["addEventListener", "removeEventListener", "setAttribute", "removeAttribute", "remove", "focus", "blur", "click"].forEach(function (k) {
        it.setProperty(el, k, it.createNativeFunction(noop));
      });
      it.setProperty(el, "getAttribute", it.createNativeFunction(function () { return null; }));
      ["appendChild", "append", "prepend", "insertBefore", "replaceChildren"].forEach(function (k) {
        it.setProperty(el, k, it.createNativeFunction(function (child) { return child; }));
      });
      it.setProperty(el, "querySelector", it.createNativeFunction(function () { return element("div"); }));
      it.setProperty(el, "querySelectorAll", it.createNativeFunction(function () { return it.nativeToPseudo([]); }));
      return el;
    }
    var doc = element("#document");
    it.setProperty(doc, "body", element("body"));
    it.setProperty(doc, "documentElement", element("html"));
    it.setProperty(doc, "getElementById", it.createNativeFunction(function (id) { var el = element("div"); it.setProperty(el, "id", String(id)); return el; }));
    it.setProperty(doc, "createElement", it.createNativeFunction(function (tag) { return element(tag); }));
    it.setProperty(doc, "createTextNode", it.createNativeFunction(function (text) { var el = element("#text"); it.setProperty(el, "textContent", String(text)); return el; }));
    it.setProperty(g, "document", doc);
    it.setProperty(g, "window", g);
    it.setProperty(g, "addEventListener", it.createNativeFunction(noop));
  }
  //: An exception nothing catches: seen in `unwind` before the stack is
  //: unwound, so the stop has the frame it was raised in and its variables.
  var unwind = I.prototype.unwind;
  I.prototype.unwind = function (type, value, label) {
    if (type === I.Completion.THROW) {
      var live = this.getStateStack();
      for (var j = live.length - 1; j >= 0 && live[j].node.type !== "TryStatement"; j--) {
        if (live[j].node.type === "GenFrame_") { live[j].gen.done = true; live[j].gen.running = false; }
      }
    }
    if (type === I.Completion.THROW && !thrown) {
      var stack = this.getStateStack(), caught = false;
      for (var i = 0; i < stack.length; i++) if (stack[i].node.type === "TryStatement") caught = true;
      if (!caught) {
        var fr = frames(stack);
        var text = "Uncaught " + show(value).replace(/^"|"$/g, "");
        var trace = fr.map(function (f) { return "    at " + f.name + (f.line ? " (line " + f.line + ")" : ""); }).join("\n");
        thrown = { frames: fr, line: fr[0].line, text: text, trace: text + "\n" + trace };
      }
    }
    return unwind.call(this, type, value, label);
  };
  function condition(line, scope) {
    var cond = breaks[line];
    if (cond === undefined) return false;
    if (!cond) return true;
    try { return Boolean(evaluate(cond, scope)); } catch (e) { return true; }
  }
  function within(node, outer) {
    return outer && node !== outer && node.start >= outer.start && node.end <= outer.end;
  }
  //: Decide, at a statement about to run, whether this is a stop.
  function decide(state) {
    var node = state.node, line = node.loc.start.line;
    if (last && line === last.loc.start.line && within(node, last)) return null;
    //: Continuing past a line with no breakpoint is the common case, and it
    //: needs no stack walk.
    if (mode === "continue" && !own(breaks, line)) return null;
    var fr = frames(interp.getStateStack()), depth = fr.length - 1;
    if (condition(line, fr[0].scope)) return { reason: "breakpoint", frames: fr, line: line };
    if (mode === "in" || (mode === "over" && depth <= base) || (mode === "out" && depth < base)) return { reason: "step", frames: fr, line: line };
    return null;
  }
  function pause(stop) {
    paused = stop;
    if (stop.node) last = stop.node;
    postMessage(snapshot(stop.reason, stop.frames, stop.line, stop.text));
  }
  function finish(ended) {
    finished = true;
    postMessage({ t: "done", ended: ended || "done" });
  }
  function go() {
    if (paused || finished) return;
    var budget = STEP_BUDGET;
    try {
      while (budget-- > 0) {
        var more = interp.step();
        if (!more) {
          for (var u = 0; u < unhandled.length; u++) {
            postMessage({ t: "log", level: "error", text: "Uncaught (in promise) " + show(unhandled[u].properties.__v).replace(/^"|"$/g, ""), line: null, uncaught: true });
          }
          return finish(unhandled.length ? "error" : "done");
        }
        var stack = interp.getStateStack(), top = stack[stack.length - 1];
        if (top && top.node.loc && top.node.end && !seen.has(top)) {
          seen.add(top);
          if (isStatement(top.node)) {
            var stop = decide(top);
            if (stop) { stop.node = top.node; return pause(stop); }
          }
        }
        if (interp.getStatus() === I.Status.TASK) {
          var due = interp.tasks.length ? interp.tasks[0].time - Date.now() : 0;
          setTimeout(go, Math.max(0, Math.min(due, 1000)));
          return;
        }
      }
    } catch (e) {
      if (thrown) {
        var t = thrown;
        return pause({ reason: "exception", frames: t.frames, line: t.line, text: t.trace, uncaught: t.text });
      }
      postMessage({ t: "log", level: "error", text: "Uncaught " + String(e && e.message || e), line: lineNow(), uncaught: true });
      return finish("error");
    }
    setTimeout(go, 0);
  }
  var DOM = false;
  self.onmessage = function (e) {
    var d = e.data || {};
    if (d.reply) {
      var r = d.reply;
      if (Array.isArray(r.breaks)) setBreaks(r.breaks);
      if (Array.isArray(r.watches)) watches = r.watches.map(String).slice(0, 50);
      if (!paused) return;
      if (r.cmd === "eval") { postMessage(snapshot(paused.reason, paused.frames, paused.line, paused.text)); return; }
      if (paused.reason === "exception") {
        postMessage({ t: "log", level: "error", text: paused.uncaught, line: paused.line, uncaught: true });
        paused = null;
        return finish("error");
      }
      if (r.cmd === "stop") { paused = null; return finish("stopped"); }
      mode = r.cmd === "in" || r.cmd === "over" || r.cmd === "out" ? r.cmd : "continue";
      base = paused.frames.length - 1;
      paused = null;
      go();
      return;
    }
    if (typeof d.source !== "string") return;
    setBreaks(d.breaks || []);
    watches = (d.watches || []).map(String).slice(0, 50);
    DOM = Boolean(d.dom);
    unhandled = [];
    builtins = {};
    var bare = new I("", function (it, g) { init(it, g); });
    for (var k in bare.getGlobalScope().object.properties) builtins[k] = 1;
    try {
      interp = new I(d.source, init);
    } catch (err) {
      var at = err && err.loc ? err.loc.line : null;
      postMessage({ t: "log", level: "error", text: "Debug could not read this: " + String(err && err.message || err).replace(/\s*\(\d+:\d+\)$/, ""), line: at, uncaught: true });
      return finish("error");
    }
    postMessage({ t: "started" });
    go();
  };
  function setBreaks(list) {
    breaks = {};
    for (var i = 0; i < list.length; i++) {
      var line = Number(list[i] && list[i].line) || 0;
      if (line > 0) breaks[line] = String(list[i].cond || "").trim();
    }
  }
})();
