"""The JavaScript debugger (DOCUMENTS_PLAN 23, D3; Brief 70), run in node.

The lowering pass (`run-debug.js`, over the vendored CodeMirror's own
JavaScript parser) and the stepping worker (`run_sandbox._JS_DEBUG_WORKER`
after the vendored JS-Interpreter) are the same text the browser runs: here
the worker's `postMessage` and `onmessage` are a script of the panel's
actions. The browser half is measured by `scratchpad/ui-sweeps/code-debug.js`.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tessellate.api import run_sandbox

ROOT = Path(__file__).resolve().parents[1]
CM_JS = ROOT / "frontend" / "vendor" / "codemirror" / "codemirror.min.js"
INTERP_JS = ROOT / "frontend" / "vendor" / "js-interpreter" / "js-interpreter.min.js"
LOWER_JS = ROOT / "frontend" / "js" / "run-debug.js"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")

_HARNESS = """
const window = globalThis;
const vm = require("vm");
//: `node -` puts CommonJS names on the global, which would send the
//: interpreter's Acorn down its module path; a worker has none of them.
delete globalThis.exports;
delete globalThis.module;
globalThis.navigator = globalThis.navigator || { userAgent: "node", platform: "" };
%(cm)s
%(lower)s
const lowerOnly = (src) => { try { const r = runDebugLower(src); return { code: r.code, dom: r.dom }; } catch (e) { return { error: e.message, line: e.line }; } };
const sessions = [];
async function session(src, breaks, watches, actions) {
  const lowered = runDebugLower(src);
  const got = [];
  return await new Promise((resolve) => {
    const self = {};
    const postMessage = (m) => {
      got.push(m);
      if (m.t === "stop") setTimeout(() => self.onmessage({ data: { reply: actions.shift() || { cmd: "stop" } } }), 0);
      if (m.t === "done") resolve(got);
    };
    //: A worker's globals, as the browser gives them: the interpreter's
    //: text at the top level (fresh per session), then the driver.
    globalThis.self = self;
    globalThis.postMessage = postMessage;
    vm.runInThisContext(%(interp)s + "\\n;" + %(worker)s);
    self.onmessage({ data: { source: lowered.code, breaks, watches, dom: lowered.dom } });
    setTimeout(() => resolve(got), 4000);
  });
}
(async () => {
  const out = {};
  for (const [key, call] of Object.entries(CALLS)) out[key] = call[0] === "lower" ? lowerOnly(call[1]) : await session(...call.slice(1));
  console.log(JSON.stringify(out));
})();
"""


def _node(calls: dict) -> dict:
    script = "const CALLS = " + json.dumps(calls) + ";\n" + _HARNESS % {
        "cm": CM_JS.read_text(encoding="utf-8"),
        "lower": LOWER_JS.read_text(encoding="utf-8"),
        "interp": json.dumps(INTERP_JS.read_text(encoding="utf-8")),
        "worker": json.dumps(run_sandbox._JS_DEBUG_WORKER),
    }
    done = subprocess.run(["node", "-"], input=script, capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr[-2000:]
    return json.loads(done.stdout)


PROGRAM = (
    "function double(n) {\n  const m = n * 2;\n  return m;\n}\nlet total = 0;\n"
    "for (let i = 0; i < 3; i++) {\n  total += double(i);\n}\nconsole.log(`total ${total}`);\nnull.boom();\n"
)


def test_the_pass_lowers_es2015_and_keeps_every_line():
    out = _node({
        "a": ["lower", "const xs = [1, 2];\nlet f = (a, b) => a + b;\nconst g = x => {\n  return x;\n};\nvar o = {xs, m() { return 1; }};\nconsole.log(`a ${f(1, 2)}\nb`);\n"],
        "this": ["lower", "function T() { this.f = () => this.n; }"],
    })
    code = out["a"]["code"]
    assert code.count("\n") == 8
    assert "const" not in code and "let " not in code and "=>" not in code and "`" not in code
    assert "var f = function (a, b)  { return (a + b); };" in code
    assert "var g = function (x)  {" in code
    assert "{xs: xs, m: function() { return 1; }}" in code
    assert ".bind(this)" in out["this"]["code"]


def test_what_the_pass_cannot_lower_is_named_with_its_line():
    out = _node({
        "getter": ["lower", "var a = 1;\nclass A {\n  get x() { return 1; }\n}\n"],
        "private": ["lower", "class A {\n  #x = 1;\n}"],
        "computed": ["lower", "class A { [k]() {} }"],
        "newspread": ["lower", "\n\nnew A(...b);"],
        "callspread": ["lower", "f()(...b);"],
        "default": ["lower", "function f(a = g()) {}"],
        "async": ["lower", "async function f() { await 1; }"],
        "optional": ["lower", "var a = b?.c;"],
        "gen": ["lower", "function* g() { yield 1; }"],
        "arrowpattern": ["lower", "var h = ([a] = [1]) => a;"],
    })
    assert out["getter"] == {"error": "Debug cannot step getters and setters yet (line 3): Run runs this file as it is.", "line": 3}
    assert "private class members" in out["private"]["error"]
    assert "computed or quoted names" in out["computed"]["error"]
    assert out["newspread"]["line"] == 3 and "spread and rest" in out["newspread"]["error"]
    assert "spread in a call to something other" in out["callspread"]["error"]
    assert "default parameter values other than a plain value" in out["default"]["error"]
    assert "async functions" in out["async"]["error"]
    assert "optional chaining" in out["optional"]["error"]
    assert "generators" in out["gen"]["error"]
    assert "parser could not read" in out["arrowpattern"]["error"]


_MODERN = (
    "class Animal {\n  constructor(name) { this.name = name; }\n  speak() { return this.name + ' makes a sound'; }\n"
    "  static kind() { return 'animal'; }\n}\n"
    "class Dog extends Animal {\n  constructor(name) { super(name); this.tricks = 0; }\n"
    "  speak() { return super.speak() + ', woof'; }\n  static kind() { return super.kind() + '/dog'; }\n}\n"
    "class Cat extends Animal {}\n"
    "function greet(who, punct = '!', times = 1) { return who + punct + times; }\n"
    "let seen = [];\n"
    "for (const n of [1, 2, 3]) seen.push(n ** 2);\n"
    "for (const ch of 'ab') { seen.push(ch); }\n"
    "const none = null;\n"
    "console.log(new Dog('Rex').speak(), Dog.kind(), new Cat('Tom').speak());\n"
    "console.log(greet('hi'), greet('hi', '?', 2), none ?? 'fallback', 0 ?? 'zero', 2 ** 3 ** 2);\n"
    "console.log(seen.join(','), new Dog('a') instanceof Animal);\n"
)


def test_classes_defaults_for_of_power_and_nullish_are_lowered_and_keep_every_line():
    lowered = _node({"m": ["lower", _MODERN]})["m"]
    assert "error" not in lowered, lowered
    assert lowered["code"].count("\n") == _MODERN.count("\n")
    for gone in ("class ", "extends", "super", "**", "??", " of "):
        assert gone not in lowered["code"].replace("Animal", "").replace("Dog", ""), gone


def test_the_lowered_program_stepped_by_the_interpreter_says_what_node_says():
    out = _node({"s": ["session", _MODERN, [], [], []]})["s"]
    logs = [m["text"] for m in out if m["t"] == "log"]
    assert logs == [
        "Rex makes a sound, woof animal/dog Tom makes a sound",
        "hi!1 hi?2 fallback 0 512",
        "1,4,9,a,b true",
    ], logs
    assert out[-1] == {"t": "done", "ended": "finished"} or out[-1]["t"] == "done"


def test_for_of_over_something_that_is_not_an_array_stops_and_says_so():
    out = _node({"s": ["session", "for (const x of 5) {}\n", [], [], []]})["s"]
    assert any("array or a string only" in m.get("text", "") for m in out), out


def test_a_breakpoint_inside_a_lowered_method_lands_on_its_own_line():
    src = "class A {\n  go(n) {\n    const m = n * 2;\n    return m;\n  }\n}\nconsole.log(new A().go(4));\n"
    out = _node({"s": ["session", src, [{"line": 3}], [], [{"cmd": "continue"}]]})["s"]
    stops = [m for m in out if m["t"] == "stop"]
    assert stops and stops[0]["line"] == 3 and {"name": "n", "value": "4", "type": "number"} in stops[0]["locals"]


def test_a_session_breaks_steps_watches_and_stops_on_the_throw():
    out = _node({
        "s": ["session", PROGRAM, [{"line": 7}], ["total * 10"],
              [{"cmd": "in"}, {"cmd": "over"}, {"cmd": "over"}, {"cmd": "continue"}, {"cmd": "continue"}, {"cmd": "continue"}]],
    })["s"]
    stops = [m for m in out if m["t"] == "stop"]
    assert [s["line"] for s in stops] == [7, 2, 3, 7, 7, 10]
    assert stops[0]["reason"] == "breakpoint" and stops[1]["reason"] == "step"
    assert [f["name"] for f in stops[1]["stack"]] == ["double", "(top level)"]
    assert {"name": "n", "value": "0", "type": "number"} in stops[1]["locals"]
    assert stops[0]["watches"] == [{"expr": "total * 10", "value": "0"}]
    last = stops[-1]
    assert last["reason"] == "exception" and last["watches"] == [{"expr": "total * 10", "value": "60"}]
    assert last["text"].startswith("Uncaught TypeError: Cannot read")
    logs = [m for m in out if m["t"] == "log"]
    assert logs[0] == {"t": "log", "level": "log", "text": "total 6", "line": 9}
    assert logs[-1]["uncaught"] and logs[-1]["line"] == 10
    assert out[-1] == {"t": "done", "ended": "error"}


def test_a_condition_and_step_out_and_stop():
    out = _node({
        "cond": ["session", PROGRAM, [{"line": 2, "cond": "n === 2"}], [], [{"cmd": "out"}, {"cmd": "stop"}]],
    })["cond"]
    stops = [m for m in out if m["t"] == "stop"]
    assert stops[0]["line"] == 2 and {"name": "n", "value": "2", "type": "number"} in stops[0]["locals"]
    assert len(stops[1]["stack"]) == 1
    assert out[-1] == {"t": "done", "ended": "stopped"}
    assert not any(m["t"] == "log" and m["text"] == "total 6" for m in out)


def test_a_dom_script_debugs_against_a_stand_in():
    out = _node({
        "dom": ["session", "var el = document.getElementById('out');\nel.textContent = 'hi';\nconsole.log(el.id, el.textContent);\n", [], [], []],
    })["dom"]
    assert {"t": "log", "level": "log", "text": "out hi", "line": 3} in out
    assert out[-1] == {"t": "done", "ended": "done"}


def test_a_list_or_an_object_opens_into_its_children():
    """OPEN row 1058: Variables showed one level, a repr, as the only view."""
    src = "var xs = [1, 'a'];\nvar o = {k: 2, f: function () {}};\nvar n = 3;\nn;\n"
    out = _node({"s": ["session", src, [{"line": 4}], [], [{"cmd": "stop"}]]})["s"]
    stop = next(m for m in out if m["t"] == "stop")
    by = {row["name"]: row for row in stop["locals"]}
    assert by["n"] == {"name": "n", "value": "3", "type": "number"}
    assert by["xs"]["children"] == [
        {"name": "[0]", "value": "1", "type": "number"},
        {"name": "[1]", "value": '"a"', "type": "string"},
    ]
    assert [c["name"] for c in by["o"]["children"]] == ["k", "f"]


def test_a_nested_list_or_object_opens_down_to_three_levels_and_a_watch_opens_too():
    """L312: Variables opened one level; each child that is a list or object opens in turn."""
    src = "var o = {a: [1, {b: 2}], c: 3};\nvar x = 1;\nx;\n"
    out = _node({"s": ["session", src, [{"line": 3}], ["o.a"], [{"cmd": "stop"}]]})["s"]
    stop = next(m for m in out if m["t"] == "stop")
    by = {row["name"]: row for row in stop["locals"]}
    a = next(c for c in by["o"]["children"] if c["name"] == "a")
    assert [c["name"] for c in a["children"]] == ["[0]", "[1]"]
    assert a["children"][1]["children"] == [{"name": "b", "value": "2", "type": "number"}]
    assert [c["name"] for c in stop["watches"][0]["children"]] == ["[0]", "[1]"]


#: One program per construct (L334): the lowered text stepped by the interpreter
#: must say what node says about the original, and keep every line.
_CONSTRUCTS = {
    "fields": (
        "class P {\n  a = 1;\n  b = this.a + 1;\n  c;\n  static s = 5;\n  static { P.t = P.s * 2; }\n"
        "  show() { return [this.a, this.b, this.c, P.s, P.t].join('/'); }\n}\n"
        "class Q extends P {\n  d = this.b * 10;\n  constructor() { super(); this.e = this.d + 1; }\n"
        "  show() { return super.show() + '/' + this.d + '/' + this.e; }\n}\n"
        "class R extends P { f = () => this.a; }\n"
        "console.log(new P().show(), new Q().show(), new R().f());\n"
        "console.log(Object.keys(new P()).join(','));\n"
    ),
    "destructure": (
        "const { a, b: [c, d = 4], e = 5, ...rest } = { a: 1, b: [2], x: 7, y: 8 };\n"
        "let [p, , q = 9, ...tail] = [1, 2, undefined, 4, 5];\n"
        "const [[m], { n }] = [[6], { n: 7 }];\n"
        "console.log(a, c, d, e, Object.keys(rest).join(','), p, q, tail.join(','), m, n);\n"
        "const [h0, ...t0] = [];\nconsole.log(h0, t0.length);\n"
        "let x = 1, y = 2;\n[x, y] = [y, x];\n"
        "console.log(x, y);\n"
        "for (const [k, v] of [['a', 1], ['b', 2]]) console.log(k + v);\n"
        "for (const { id, tag = 't' } of [{ id: 1 }, { id: 2, tag: 'u' }]) { console.log(id + tag); }\n"
    ),
    "params": (
        "function f({ a, b = 2 }, [c, d], e = 5, ...more) { return [a, b, c, d, e, more.join('+')].join(','); }\n"
        "const g = ({ a }, ...r) => a + r.length;\n"
        "function h([a, b] = [3, 4]) { return a * b; }\n"
        "function k(...all) { return all.length; }\n"
        "console.log(f({ a: 1 }, [3, 4]), f({ a: 1, b: 9 }, [3, 4], 6, 7, 8), g({ a: 10 }, 1, 2), h(), h([2, 5]), k(), k(1, 2, 3));\n"
    ),
    "spread": (
        "const xs = [1, 2], ys = [3];\n"
        "const all = [0, ...xs, ...ys, 9,];\n"
        "function add(a, b, c) { return a + b + c; }\n"
        "const o = { base: 10, sum(a, b) { return this.base + a + b; } };\n"
        "const merged = { ...{ p: 1, q: 2 }, q: 3, ...null, r: 4 };\n"
        "console.log(all.join(','), add(...xs, 5), add(1, ...xs), o.sum(...xs), Math.max(...all), 'hi'.length);\n"
        "console.log(Object.keys(merged).join(','), merged.q, [...'ab'].join('-'));\n"
    ),
}


@pytest.mark.parametrize("name", sorted(_CONSTRUCTS))
def test_each_lowered_construct_steps_to_what_node_prints(name):
    src = _CONSTRUCTS[name]
    lowered = _node({"m": ["lower", src]})["m"]
    assert "error" not in lowered, lowered
    assert lowered["code"].count("\n") == src.count("\n")
    stepped = [m["text"] for m in _node({"s": ["session", src, [], [], []]})["s"] if m["t"] == "log"]
    real = subprocess.run(["node", "-e", src], capture_output=True, text=True, timeout=30)
    assert real.returncode == 0, real.stderr
    assert stepped == real.stdout.splitlines(), (stepped, real.stdout)


def test_a_breakpoint_inside_a_field_initializer_and_a_destructured_body_keeps_its_line():
    src = "class A {\n  n = 2;\n  m = this.n * 3;\n}\nfunction f({ a }) {\n  const s = a + 1;\n  return s;\n}\nconsole.log(new A().m, f({ a: 1 }));\n"
    out = _node({"s": ["session", src, [{"line": 3}, {"line": 7}], [], [{"cmd": "continue"}, {"cmd": "stop"}]]})["s"]
    stops = [m for m in out if m["t"] == "stop"]
    assert [s["line"] for s in stops] == [3, 7]
    assert {"name": "a", "value": "1", "type": "number"} in stops[1]["locals"]


def test_spread_and_array_patterns_over_something_else_stop_and_say_so():
    for src in ("const [a] = 5;\n", "function f() {}\nf(...5);\n"):
        out = _node({"s": ["session", src, [], [], []]})["s"]
        assert any("array or a string only" in m.get("text", "") for m in out), out
