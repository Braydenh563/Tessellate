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


NUMBER_SCRIPT = """
const fs = require('fs');
const take = (src, name) => { const a = src.indexOf('function ' + name); return src.slice(a, src.indexOf('\\n}\\n', a) + 3); };
eval(take(fs.readFileSync(process.argv[1], 'utf8'), 'docOrderedNumberAt').replace('function ', 'globalThis.n = function '));
eval(take(fs.readFileSync(process.argv[2], 'utf8'), 'docListEnter').replace('function ', 'globalThis.e = function '));
const at = (v) => n(v, v.length + 1, 2);
console.log(JSON.stringify([
  n('1. a\\n', 5, 2), n('1. a\\n  1. b\\n', 13, 0), n('1. a\\n2. b\\n', 11, 0), n('- a\\n', 4, 2),
  n('1. a\\n  1. b\\n  2. c\\n', 21, 0), n('intro\\n', 6, 0), n('', 0, 0),
  e('> '), e('>'), e('> > '), e('> text'), e('- '), e('  - '),
]));
"""


def test_numbered_item_takes_its_place_when_the_level_changes():
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    out = subprocess.run(
        [node, "-e", NUMBER_SCRIPT, str(ROOT / "frontend" / "js" / "documents.js"), str(ROOT / "frontend" / "js" / "documents-prose.js")],
        capture_output=True, text=True, check=True,
    )
    # Nested under 1. a: 1; back out beside 1. a (nested children skipped): 2; a bullet parent: 1.
    assert json.loads(out.stdout) == [1, 2, 3, 1, 2, 1, 1, "", "", "> ", None, "", "- "]


def test_leaving_a_tab_bins_an_untouched_document():
    """dog3d-1026: a document made by a keystroke and emptied again stayed in the list."""
    src = (ROOT / "frontend" / "js" / "navigation.js").read_text()
    leave = src[src.index("async function confirmLeavingUnsavedWork") :][:2400]
    assert leave.count("await docDropIfUntouched();") == 2
