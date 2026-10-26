"""The heading, list, task and quote buttons switch a line's marker; they never stack one.

Browser check: docdog-1026, toolbar H2 then List then Numbered then Task on one line
used to give `- [ ] 1. - ## text`.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

SCRIPT = """
const src = require('fs').readFileSync(process.argv[1], 'utf8');
const a = src.indexOf('const MD_LINE_KINDS');
eval(src.slice(a, src.indexOf('\\n}\\n', src.indexOf('function mdLinePrefixEdit')) + 3).replace(/^const /gm, 'var '));
const cases = JSON.parse(process.argv[2]);
console.log(JSON.stringify(cases.map(([b, k]) => mdLinePrefixEdit(b, k))));
"""

CASES = [
    (["x", "h2"], "## x"),
    (["## x", "h2"], "x"),
    (["## x", "h1"], "# x"),
    (["- x", "ol"], "1. x"),
    (["1. x", "ul"], "- x"),
    (["- [ ] x", "ul"], "- x"),
    (["- x", "task"], "- [ ] x"),
    (["- [x] x", "task"], "x"),
    (["- x", "h1"], "# x"),
    (["# x", "ul"], "- x"),
    (["a\n\nb", "ul"], "- a\n\n- b"),
    (["a\nb\nc", "ol"], "1. a\n2. b\n3. c"),
    (["1. a\n2. b", "ol"], "a\nb"),
    (["a\n- b", "ul"], "- a\n- b"),
    (["> a\n> b", "quote"], "a\nb"),
    (["a\n> b", "quote"], "> a\n> b"),
    (["> a", "ul"], "> - a"),
    (["  - a", "ol"], "  1. a"),
    (["-5 degrees", "ul"], "- -5 degrees"),
]


def test_a_line_prefix_switches_instead_of_stacking():
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    out = subprocess.run(
        [node, "-e", SCRIPT, str(ROOT / "frontend" / "js" / "documents.js"), json.dumps([c for c, _ in CASES])],
        capture_output=True, text=True, check=True,
    )
    got = json.loads(out.stdout)
    for (case, want), have in zip(CASES, got):
        assert have == want, case


def test_underline_and_replace_have_their_word_processor_chords():
    js = (ROOT / "frontend" / "js" / "documents.js").read_text(encoding="utf-8")
    # CodeMirror's own Mod-u is "undo selection": without this binding Ctrl+U looked dead.
    assert '{ key: "Mod-u", run: () => { applyMarkdown("underline"); return true; } }' in js
    assert '{ key: "Mod-h"' in js and 'input[name=replace]' in js
    assert '{ id: "underline"' in js
    # A second press takes a pre/post pair (underline, sup, sub) off again.
    assert "A second press takes the pair off" in js
    # Hiding the toolbar from inside it hands the keyboard back to the page.
    hide = js[js.index("function toggleDocToolbar()"):]
    assert "docSurface()?.focus()" in hide[: hide.index("\n}\n")]
