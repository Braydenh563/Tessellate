"""Lint for .js, .ts and .py documents (L-documents-50), run in node.

`documents-code-lint.js` is the browser's text over the vendored CodeMirror's JavaScript parser. The Ruff half is
checked with a stand-in workspace (the real wasm is 10 MB and an optional download), so the mapping from Ruff's
rows and columns to offsets, the fix and the not-installed path are covered; the real Ruff is measured by the
agent sweep named in the ledger row.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CM_JS = ROOT / "frontend" / "vendor" / "codemirror" / "codemirror.min.js"
PIECE = ROOT / "frontend" / "js" / "documents-code-lint.js"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")

_HARNESS = """
const window = globalThis;
globalThis.navigator = globalThis.navigator || { userAgent: "node", platform: "" };
%(cm)s
const DOC_LINT_CONFIG = {};
let installed = INSTALLED;
let asked = 0;
const apiJson = async () => { asked += 1; return { extras: [{ id: "ruff", installed }] }; };
%(piece)s
const CM = window.CM6;
const L = DOC_LINT_CONFIG.codeLint;
const state = (doc) => CM.state.EditorState.create({ doc, extensions: [CM.javascript.javascript()] });
L.load = async () => ({
  PositionEncoding: { Utf16: 1 },
  Workspace: class { check(text) { return ROWS; } },
});
(async () => {
  const out = {};
  for (const [key, call] of Object.entries(CALLS)) {
    const st = state(call.text);
    const found = call.op === "js" ? L.js(CM, st) : await L.py(CM, st);
    out[key] = found.map((d) => ({ at: call.text.slice(d.from, d.to), severity: d.severity, message: d.message, source: d.source, fixes: (d.actions || []).map((a) => a.name) }));
    if (call.apply && found[0] && found[0].actions[0]) {
      const view = { state: st, dispatch(tr) { out[key + "-fixed"] = st.update(tr).state.doc.toString(); } };
      found[0].actions[0].apply(view, found[0].from, found[0].to);
    }
  }
  out.asked = asked;
  console.log(JSON.stringify(out));
})();
"""


def _node(calls: dict, rows: list | None = None, installed: bool = True) -> dict:
    script = f"const CALLS = {json.dumps(calls)};\nconst ROWS = {json.dumps(rows or [])};\nconst INSTALLED = {json.dumps(installed)};\n" + _HARNESS % {
        "cm": CM_JS.read_text(encoding="utf-8"),
        "piece": PIECE.read_text(encoding="utf-8"),
    }
    done = subprocess.run(["node", "-"], input=script, capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr[-2000:]
    return json.loads(done.stdout)


def _js(text: str) -> dict:
    return _node({"t": {"op": "js", "text": text}})["t"]


def test_a_duplicate_object_key_is_named_and_a_getter_with_its_setter_is_not():
    assert [d["at"] for d in _js("const o = { a: 1, b: 2, a: 3 };\n")] == ["a"]
    assert _js("const o = { get a() { return 1; }, set a(v) {} };\n") == []
    assert [d["at"] for d in _js('const o = { "k": 1, k: 2 };\n')] == ["k"]


def test_an_assignment_in_a_condition_is_flagged_and_double_parentheses_say_it_is_meant():
    found = _js("let a;\nif (a = 1) { a++; }\nwhile ((a = next())) {}\nfunction next() { return 0; }\n")
    assert [d["at"] for d in found] == ["a = 1"]
    assert "===" in found[0]["message"]


def test_code_after_a_return_throw_break_or_continue_is_unreachable_but_a_function_below_is_hoisted():
    found = _js("function f() {\n  return 1;\n  log();\n  function g() {}\n}\nfunction log() {}\n")
    assert [d["at"] for d in found] == ["log();"]
    switch = _js("switch (1) {\n  case 1:\n    break;\n  case 2:\n    break;\n}\n")
    assert switch == []


def test_a_duplicate_case_a_nan_comparison_and_a_misspelt_typeof_word():
    found = _js("switch (x) {\n  case 1: break;\n  case 1: break;\n}\n")
    assert [d["at"] for d in found] == ["case 1:"]
    assert [d["at"] for d in _js("if (x === NaN) {}\n")] == ["x === NaN"]
    found = _js('if (typeof x === "strng") {}\nif (typeof x === "string") {}\n')
    assert [d["at"] for d in found] == ['"strng"']


def test_a_clean_file_has_no_findings_and_they_are_warnings():
    assert _js("const a = [1, 2].map((n) => n * 2);\nconsole.log(a);\n") == []
    assert {d["severity"] for d in _js("const o = { a: 1, a: 2 };\n")} == {"warning"}


ROWS = [
    {"code": "F401", "message": "`os` imported but unused", "start_location": {"row": 1, "column": 8}, "end_location": {"row": 1, "column": 10},
     "fix": {"message": "Remove unused import: `os`", "edits": [{"content": "", "location": {"row": 1, "column": 1}, "end_location": {"row": 2, "column": 1}}]}},
    {"code": "F821", "message": "Undefined name `zzz`", "start_location": {"row": 2, "column": 7}, "end_location": {"row": 2, "column": 10}, "fix": None},
]


def test_ruffs_rows_become_underlines_with_its_fix_and_the_fix_applies():
    text = "import os\nprint(zzz)\n"
    out = _node({"t": {"op": "py", "text": text, "apply": True}}, ROWS)
    found = out["t"]
    assert [(d["at"], d["source"], d["severity"]) for d in found] == [("os", "Ruff F401", "warning"), ("zzz", "Ruff F821", "error")]
    assert found[0]["fixes"] == ["Remove unused import: `os`"] and found[1]["fixes"] == []
    assert out["t-fixed"] == "print(zzz)\n"


def test_without_the_extra_there_are_no_underlines_and_the_question_is_asked_once_in_half_a_minute():
    out = _node({"a": {"op": "py", "text": "import os\n"}, "b": {"op": "py", "text": "import os\n"}}, ROWS, installed=False)
    assert out["a"] == [] and out["b"] == []
    assert out["asked"] == 1
