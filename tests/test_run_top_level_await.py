"""L-documents-108: Run steps a `.js` document with top-level await, as Debug does.

The sandbox page's own script runs in node with a stub `Worker` that keeps the
source it is handed; that source then runs in a fresh context standing in for
the worker. A script with top-level await used to stop on "await is only valid
in async functions"; it now runs as an async body on the code's own first line,
so a reported line is still the document's, and a plain script keeps its
global names for the console.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess

import pytest

from tessellate.api import run_sandbox

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")

_HARNESS = r"""
const vm = require("vm");
const PAGE = %(page)s;
function runOnce(code, opts) {
  return new Promise((resolve) => {
    const out = [];
    let made = null;
    const parent = { postMessage: (m) => out.push(m) };
    const page = {
      parent, document: { createElement: () => ({}) }, URL: { createObjectURL: (b) => b.text },
      Blob: function (parts) { this.text = parts.join(""); },
      Worker: function (src) { made = src; this.postMessage = () => {}; this.terminate = () => {}; },
    };
    page.window = page;
    vm.createContext(page);
    vm.runInContext(PAGE, page);
    page.onmessage({ source: parent, data: Object.assign({ mmRun: 1, type: "run", kind: "js", source: code }, opts || {}) });
    const logs = [];
    const self = {
      listeners: {},
      addEventListener(k, f) { (this.listeners[k] = this.listeners[k] || []).push(f); },
    };
    const ctx = { self, console: {}, setTimeout, clearTimeout, setInterval, clearInterval, Promise, Error, JSON };
    ctx.postMessage = (m) => { logs.push(m); if (m.t === "done") setTimeout(() => resolve({ logs, src: made, globals: ctx }), 20); };
    self.postMessage = ctx.postMessage;
    vm.createContext(ctx);
    ctx.self = ctx; Object.assign(ctx, { addEventListener: self.addEventListener.bind(self), listeners: self.listeners });
    process.removeAllListeners("unhandledRejection");
    process.on("unhandledRejection", (r) => { for (const f of self.listeners.unhandledrejection || []) f({ reason: r }); });
    try { vm.runInContext(made, ctx, { filename: "blob:sandbox/1" }); } catch (e) { logs.push({ t: "thrown", text: e.message }); resolve({ logs, src: made, globals: ctx }); }
    setTimeout(() => resolve({ logs, src: made, globals: ctx, timeout: true }), 3000);
  });
}
(async () => {
  const CASES = %(cases)s;
  const res = {};
  for (const [k, c] of Object.entries(CASES)) {
    const r = await runOnce(c[0], c[1]);
    res[k] = { logs: r.logs.map((m) => ({ t: m.t, text: m.text, line: m.line, level: m.level })), timeout: !!r.timeout, hasX: "x" in r.globals };
  }
  console.log(JSON.stringify(res));
})();
"""

_PAGE = re.search(r"<script>\n(.*?)</script>", run_sandbox.RUN_SANDBOX_HTML, re.S).group(1)


def _run(cases: dict) -> dict:
    src = _HARNESS % {"page": json.dumps(_PAGE), "cases": json.dumps(cases)}
    done = subprocess.run(["node", "-"], input=src, capture_output=True, text=True, timeout=60, check=False)
    assert done.returncode == 0, done.stderr[-2000:]
    return json.loads(done.stdout.strip().splitlines()[-1])


CASES = {
    "tla": ["const wait = (v) => new Promise((r) => setTimeout(() => r(v), 5));\nconsole.log('start');\nconst v = await wait(10);\nconsole.log('got', v);\n", None],
    "tla_throw": ["console.log('a');\nawait null;\nthrow new Error('late');\n", None],
    "plain": ["var x = 1;\nconsole.log('x', x);\n", None],
    "offset": ["await null;\nconsole.log('here');\n", {"lineOffset": 4}],
    "awaitname": ["var await = 3;\nconsole.log(await);\n", None],
}


def test_top_level_await_runs_and_reports_document_lines():
    out = _run(CASES)
    tla = [m for m in out["tla"]["logs"] if m["t"] == "log"]
    assert [(m["text"], m["line"]) for m in tla] == [("start", 2), ("got 10", 4)], out["tla"]
    assert any(m["t"] == "done" for m in out["tla"]["logs"])
    late = [m for m in out["tla_throw"]["logs"] if m["t"] == "log" and m["level"] == "error"]
    assert late and "late" in late[0]["text"] and late[0]["line"] == 3, out["tla_throw"]
    assert any(m["t"] == "done" for m in out["tla_throw"]["logs"]), "the top level must still report it ended"
    off = [m for m in out["offset"]["logs"] if m["t"] == "log"]
    assert [(m["text"], m["line"]) for m in off] == [("here", 6)], out["offset"]


def test_a_plain_script_keeps_its_global_names_and_await_as_a_name():
    out = _run({k: CASES[k] for k in ("plain", "awaitname")})
    assert out["plain"]["hasX"], "a plain script's var stays global for the console"
    assert [m["text"] for m in out["plain"]["logs"] if m["t"] == "log"] == ["x 1"]
    assert [m["text"] for m in out["awaitname"]["logs"] if m["t"] == "log"] == ["3"]
