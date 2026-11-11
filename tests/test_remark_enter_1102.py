"""Enter ends a remark (audit 1102 DX24, the Enter half).

A `%%remark%%` is inline text. Enter at the end of what was typed in one put a
newline into the file (`%%Check this word\\n%%`), so a one-line note became a
broken two-line one. `docAnnotateSelection.end` is the rule, run by node on a
stub of the editor's state: the caret straight before a closing `%%` that this
line opened moves past it, and nothing else changes.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
COMMENTS = (ROOT / "frontend" / "js" / "documents-comments.js").read_text(encoding="utf-8")
DOCUMENTS = (ROOT / "frontend" / "js" / "documents.js").read_text(encoding="utf-8") + (ROOT / "frontend" / "js" / "documents-view.js").read_text(encoding="utf-8")

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node is not available")


def _rule_source() -> str:
    start = COMMENTS.index("// DOC-REMARK-END-BEGIN")
    end = COMMENTS.index("// DOC-REMARK-END-END")
    return COMMENTS[start:end]


def _run(line: str, caret: int, anywhere: bool) -> dict:
    """The rule on one line of text with the caret at `caret`; returns the
    moved-to offset (or None) and whether the key was handled."""
    script = f"""
const docAnnotateSelection = () => {{}};
{_rule_source()}
const line = {json.dumps(line)};
let moved = null;
const view = {{
  state: {{ selection: {{ main: {{ empty: true, head: {caret} + 7 }} }}, doc: {{ lineAt: () => ({{ from: 7, text: line }}) }} }},
  dispatch: (tr) => {{ moved = tr.selection.anchor - 7; }},
}};
const handled = docAnnotateSelection.end(view, {json.dumps(anywhere)});
console.log(JSON.stringify({{ handled, moved }}));
"""
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30, check=False)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def test_enter_at_the_end_of_a_fresh_remark_moves_past_it() -> None:
    line = "==a word== %%Check this word%%"
    assert _run(line, len("==a word== %%Check this word"), False) == {"handled": True, "moved": len(line)}


def test_enter_in_an_empty_fresh_remark_moves_past_it() -> None:
    assert _run("%%%%", 2, False) == {"handled": True, "moved": 4}


def test_enter_with_text_after_the_remark_keeps_that_text_after_the_caret() -> None:
    line = "==a word== %%Check%% and then more"
    assert _run(line, len("==a word== %%Check"), False) == {"handled": True, "moved": len("==a word== %%Check%%")}


def test_enter_in_the_middle_of_a_remark_is_left_to_the_editor() -> None:
    assert _run("%%Check this word%%", 7, False) == {"handled": False, "moved": None}


def test_enter_outside_a_remark_is_left_to_the_editor() -> None:
    assert _run("Plain text %%a remark%% after", 3, False) == {"handled": False, "moved": None}
    assert _run("Plain text %%a remark%% after", len("Plain text %%a remark%% "), False) == {"handled": False, "moved": None}


def test_a_remark_that_never_closes_on_this_line_is_left_alone() -> None:
    assert _run("%%a remark that goes on", 5, True) == {"handled": False, "moved": None}


def test_escape_leaves_a_remark_from_anywhere_inside_it() -> None:
    line = "%%Check this word%% after"
    assert _run(line, 7, True) == {"handled": True, "moved": len("%%Check this word%%")}


def test_the_editor_asks_the_rule_on_enter_and_on_escape() -> None:
    keymap = DOCUMENTS[DOCUMENTS.index("function docCmKeymap("):]
    keymap = keymap[: keymap.index("\n}\n")]
    assert "docAnnotateSelection.end(view)" in keymap
    assert "docAnnotateSelection.end(view, true)" in keymap
