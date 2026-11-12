
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
      for (var k in p) {
        if (!own(p, k)) continue;
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
      if (!own(props, k) || (skip && skip[k])) continue;
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
      if (n.loc) top.line = n.loc.start.line;
      if (s.scope) top.scope = s.scope;
      if ((n.type === "CallExpression" || n.type === "NewExpression") && s.doneExec_ && s.func_ && s.func_.node) {
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
    for (var i = stack.length - 1; i >= 0; i--) if (stack[i].node.loc) return stack[i].node.loc.start.line;
    return null;
  }
  //: Console rows, with the line that called them.
  function fmt(v) { return typeof v === "string" ? v : show(v); }
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
        if (!more) return finish("done");
        var stack = interp.getStateStack(), top = stack[stack.length - 1];
        if (top && top.node.loc && !seen.has(top)) {
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
