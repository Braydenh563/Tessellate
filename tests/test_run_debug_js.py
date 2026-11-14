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
async function session(src, breaks, watches, actions, tests) {
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
    self.onmessage({ data: { source: lowered.code, breaks, watches, dom: lowered.dom, tests: Boolean(tests) } });
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
        "getter": ["lower", "var a = 1;\nvar o = {\n  get x() { return 1; }\n};\n"],
        "private": ["lower", "class A {\n  #x = 1;\n  has(o) { return #x in o; }\n}"],
        "undeclared": ["lower", "class A {\n  m() { return this.#y; }\n}"],
        "computed": ["lower", "class A { [k]() {} }"],
        "callspread": ["lower", "f()(...b);"],
        "default": ["lower", "function f(a = g()) {}"],
        "asyncgen": ["lower", "async function* f() { yield 1; }"],
        "forawait": ["lower", "async function f(xs) {\n  for await (const x of xs) {}\n}"],
        "topawait": ["lower", "\nawait 1;"],
        "plainawait": ["lower", "async function f() { return () => await 1; }"],
        "args": ["lower", "async function f() { return arguments.length; }"],
        "optional": ["lower", "var a = b?.c;"],
        "yieldin": ["lower", "function g() { var x = yield 1; }"],
        "arrowpattern": ["lower", "var h = ([a] = g()) => a;"],
        "broken": ["lower", "var x = ;\n"],
    })
    assert out["getter"] == {"error": "Debug cannot step getters and setters yet (line 3): Run runs this file as it is.", "line": 3}
    # Class accessors and private members are lowered (L-documents-37); an
    # object literal's accessor and a brand check are still named.
    assert out["private"] == {"error": "Debug cannot step private brand checks (#x in o) yet (line 3): Run runs this file as it is.", "line": 3}
    assert "private name no enclosing class declares" in out["undeclared"]["error"]
    assert "computed or quoted names" in out["computed"]["error"]
    assert "spread in a call to something other" in out["callspread"]["error"]
    assert "default parameter values other than a plain value" in out["default"]["error"]
    assert "async generators" in out["asyncgen"]["error"]
    assert out["forawait"]["line"] == 2 and "for await" in out["forawait"]["error"]
    assert out["topawait"]["line"] == 2 and "top level" in out["topawait"]["error"]
    assert "await outside an async function" in out["plainawait"]["error"]
    assert "arguments inside an async function" in out["args"]["error"]
    assert "optional chaining" in out["optional"]["error"]
    assert "yield outside a generator" in out["yieldin"]["error"]
    assert "default parameter values other than a plain value" in out["arrowpattern"]["error"]
    assert "parser could not read" in out["broken"]["error"]


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
    "accessors": (
        "class T {\n  constructor() { this.c = 20; }\n  get f() { return this.c * 9 / 5 + 32; }\n"
        "  set f(v) { this.c = (v - 32) * 5 / 9; }\n  static get unit() { return 'C'; }\n}\n"
        "class U extends T { get label() { return this.f + 'F'; } }\n"
        "const t = new T();\nconsole.log(t.f, T.unit);\nt.f = 212;\nconsole.log(t.c, new U().label);\n"
        "console.log(Object.keys(t).join(','), Object.keys(T.prototype).length);\n"
    ),
    "private": (
        "class Counter {\n  #n = 0;\n  static #made = 0;\n  constructor() { Counter.#made++; }\n"
        "  #step() { return 2; }\n  get #twice() { return this.#n * 2; }\n"
        "  bump() { this.#n += this.#step(); return this.#twice; }\n  static made() { return Counter.#made; }\n}\n"
        "class Sub extends Counter {\n  #n = 100;\n  own() { return this.#n; }\n}\n"
        "const c = new Counter();\nc.bump();\nconsole.log(c.bump(), new Sub().own(), new Sub().bump(), Counter.made());\n"
        "console.log(Object.keys(c).length, JSON.stringify(c));\n"
    ),
    "arrowpattern": (
        "const f = ([a, b] = [1, 2]) => a + b;\n"
        "const g = ({ x = 4, y = 3 } = {}) => {\n  return x * y;\n};\n"
        "const h = ([p] = [5], q = 6) => p + q;\n"
        "const k = (\n  [m, n] = [1, 2],\n  z = 3\n) => m + n + z;\n"
        "console.log(f(), f([10, 20]), g(), g({ x: 1, y: 2 }), h(), h([1], 1), k(), k([5, 5], 0));\n"
    ),
    "newspread": (
        "class A { constructor(a, b, c) { this.s = a + b + c; } }\n"
        "const xs = [1, 2];\nconst a = new A(...xs, 3);\nconst d = new Date(...[2020, 0, 15]);\n"
        "const ns = { A };\nconst b = new ns.A(0, ...xs);\nconst e = new Error(...['boom']);\n"
        "console.log(a.s, a instanceof A, d.getFullYear(), d.getMonth(), b.s, new Array(...[1, 2, 3]).length, e.message);\n"
    ),
    "generators": (
        "function* count(n) {\n  for (let i = 1; i <= n; i++) {\n    const got = yield i * 10;\n    if (got) console.log('sent', got);\n  }\n  return 'end';\n}\n"
        "const g = count(3);\nconsole.log(JSON.stringify([g.next(), g.next('a'), g.next(), g.next(), g.next()]));\n"
        "function* inner() { yield 'a'; yield 'b'; return 'r'; }\nfunction* outer() { const r = yield* inner(); yield r; yield* [1, 2]; }\n"
        "console.log([...outer()].join(','));\n"
        "const out = [];\nfor (const v of count(2)) out.push(v);\nconsole.log(out.join(','));\n"
        "function* nat() { let n = 0; while (true) yield n++; }\nfor (const v of nat()) { if (v > 3) break; out.push(v); }\nconsole.log(out.join(','));\n"
        "const [p, q, ...rest] = count(4);\nconsole.log(p, q, rest.join('/'));\n"
        "function* boom() { try { yield 1; yield 2; } catch (e) { yield 'caught ' + e; } finally { console.log('fin'); } }\n"
        "const b = boom();\nconsole.log(b.next().value, b.throw('x').value, b.next().done, b.next().done);\n"
        "function* fail() { yield 1; throw new Error('bad'); }\nconst f = fail();\nf.next();\n"
        "try { f.next(); } catch (e) { console.log(e.message, f.next().done); }\n"
        "class Tree { constructor() { this.items = [3, 4]; }\n  *walk() { for (const x of this.items) yield x * 2; }\n  static *range(a, b) { for (let i = a; i < b; i++) yield i; } }\n"
        "console.log([...new Tree().walk()].join(','), [...Tree.range(1, 4)].join(','));\n"
        "const ob = { *g() { yield this.v; }, v: 7 };\nconsole.log(ob.g().next().value, g.return(5).value, g.next().done);\n"
    ),
    "async": (
        "const log = (...a) => console.log(...a);\n"
        "const wait = (ms, v) => new Promise((res) => setTimeout(() => res(v), ms));\n"
        "async function one(x) {\n  log('one start', x);\n  const y = await x;\n  log('one got', y);\n  return y + 1;\n}\n"
        "async function main() {\n  const a = await one(1);\n  const b = await wait(5, a * 10);\n  try {\n    await Promise.reject(new Error('no'));\n  } catch (e) {\n    log('caught', e.message);\n  }\n"
        "  const all = await Promise.all([one(5), wait(1, 'w'), 3]);\n  log(all.join('|'));\n  return b;\n}\n"
        "log('before');\nmain().then((v) => log('main', v));\nlog('after');\n"
        "setTimeout(() => log('timer'), 0);\nPromise.resolve().then(() => log('micro'));\n"
        "const arrow = async (n) => n * 2;\nconst arrow2 = async n => { await null; return n + 1; };\n"
        "class K { constructor() { this.v = 3; } async m(d) { await wait(1); return this.v + d; } static async s() { return 's'; }\n  fn() { return async () => { await 0; return this.v; }; } }\n"
        "const o = { async am() { return 'am'; } };\n"
        "Promise.all([arrow(4), arrow2(4), new K().m(1), K.s(), o.am(), new K().fn()()]).then((r) => log(r.join(',')));\n"
        "Promise.allSettled([Promise.reject('r'), 1]).then((r) => log(r.map((x) => x.status).join(',')));\n"
        "Promise.race([wait(20, 'slow'), wait(2, 'fast')]).then((v) => log(v));\n"
        "Promise.any([Promise.reject(1), wait(3, 'any')]).then((v) => log(v));\n"
        "new Promise((_, rej) => rej('x')).catch((e) => log('c', e)).finally(() => log('f'));\n"
    ),
    "tagged": (
        "function tag(s, ...v) { return s.join('|') + '#' + v.join(',') + '#' + s.raw.join('|'); }\n"
        "const n = 3;\n"
        "console.log(tag`a${n}b${n + 1}c`, tag`x`, tag`\\n${1}\\t`, String.raw`a\\nb${n}`);\n"
        "const o = { p: '>', t(s, v) { return this.p + s[0] + v; } };\n"
        "console.log(o.t`k${9}`, tag`multi\nline ${1}\nend`, tag`${1}${2}`);\n"
        "console.log(tag`q${tag`in${2}ner`}r`);\n"
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
    assert "\n".join(stepped) == real.stdout.rstrip("\n"), (stepped, real.stdout)


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


_CORO = (
    "function* g() {\n  const a = 1;\n  yield a;\n  const b = a + 1;\n  yield b;\n}\n"
    "async function f() {\n  const x = await 5;\n  const y = x + 1;\n  return y;\n}\n"
    "for (const v of g()) console.log(v);\nf().then((r) => console.log('r', r));\n"
)


def test_a_breakpoint_after_a_yield_and_after_an_await_stops_on_its_own_line_with_its_variables():
    out = _node({"s": ["session", _CORO, [{"line": 4}, {"line": 9}], [], [{"cmd": "continue"}, {"cmd": "continue"}]]})["s"]
    stops = [m for m in out if m["t"] == "stop"]
    assert [s["line"] for s in stops] == [4, 9]
    assert {"name": "a", "value": "1", "type": "number"} in stops[0]["locals"]
    assert {"name": "x", "value": "5", "type": "number"} in stops[1]["locals"]
    #: The debugger's own helpers (the promise, the driver) are not frames of the program.
    assert all(f["name"] != "step" for s in stops for f in s["stack"]), [s["stack"] for s in stops]
    assert [m["text"] for m in out if m["t"] == "log"] == ["1", "2", "r 6"]


def test_step_over_an_await_lands_on_the_next_line_of_the_same_function():
    out = _node({"s": ["session", _CORO, [{"line": 8}], [], [{"cmd": "over"}, {"cmd": "over"}, {"cmd": "stop"}]]})["s"]
    assert [m["line"] for m in out if m["t"] == "stop"] == [8, 9, 10]


def test_a_rejection_nothing_catches_is_reported_when_the_program_is_idle():
    out = _node({"s": ["session", "Promise.reject(new Error('lost'));\nconsole.log('ran');\n", [], [], []]})["s"]
    errors = [m["text"] for m in out if m["t"] == "log" and m.get("level") == "error"]
    assert errors == ["Uncaught (in promise) Error: lost"], errors
    assert out[-1] == {"t": "done", "ended": "error"}
    handled = _node({"s": ["session", "var p = Promise.reject(1);\np.catch(function () {});\nasync function f() { throw 2; }\nf().catch(function (e) { console.log('got', e); });\n", [], [], []]})["s"]
    assert [m["text"] for m in handled if m["t"] == "log"] == ["got 2"] and handled[-1]["ended"] == "done"


_TESTS = (
    "function add(a, b) {\n  return a + b;\n}\n"
    "describe('add', () => {\n"
    "  let base = 0;\n"
    "  beforeEach(() => { base = 10; });\n"
    "  it('adds', () => {\n"
    "    const s = add(base, 2);\n"
    "    expect(s).toBe(12);\n"
    "  });\n"
    "  it('fails', () => {\n"
    "    expect(add(1, 1)).toEqual(3);\n"
    "  });\n"
    "  it('waits', async () => {\n"
    "    const v = await Promise.resolve(4);\n"
    "    expect([v]).toContain(4);\n"
    "  });\n"
    "  it.skip('later', () => {});\n"
    "  it('throws', () => {\n"
    "    expect(() => { null.x; }).not.toThrow();\n"
    "  });\n"
    "});\n"
)


def test_a_file_of_tests_debugs_through_the_harness_and_lists_each_test():
    out = _node({"s": ["session", _TESTS, [], [], [], True]})["s"]
    rows = [(m["name"], m["state"], m["line"]) for m in out if m["t"] == "test"]
    assert rows == [("add > adds", "pass", 7), ("add > fails", "fail", 12), ("add > waits", "pass", 14), ("add > later", "skip", 18), ("add > throws", "fail", 20)], rows
    fail = next(m for m in out if m["t"] == "test" and m["name"] == "add > fails")
    assert "Expected: 3" in fail["text"] and "Received: 2" in fail["text"]
    #: The failure's line is the line of the expect, not of the test's start.
    assert fail["line"] == 12
    assert next(m for m in out if m["t"] == "tests-done")["failed"] == 2
    assert out[-1]["t"] == "done"


def test_a_breakpoint_in_a_test_body_stops_there_with_its_locals_and_the_harness_is_no_frame():
    out = _node({"s": ["session", _TESTS, [{"line": 9}], [], [{"cmd": "continue"}], True]})["s"]
    stops = [m for m in out if m["t"] == "stop"]
    assert [s["line"] for s in stops] == [9]
    assert {"name": "s", "value": "12", "type": "number"} in stops[0]["locals"]
    assert all(f["name"] not in ("run", "series", "call") for f in stops[0]["stack"]), stops[0]["stack"]
    #: The harness's own names are not the program's variables.
    assert not any(v["name"] in ("describe", "expect", "it") for v in stops[0]["locals"] + stops[0].get("globals", []))
