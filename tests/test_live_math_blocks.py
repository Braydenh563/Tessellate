"""Live draws a display formula written over several lines, and `\\ref{` completes.

A replace decoration from a view plugin may not hold a line break, so the
formula is drawn over the opening line and the lines under it are folded by a
line class (`cm-md-math-fold`); the caret in any of them shows the source.
`\\ref{` and `\\eqref{` list the page's equation labels with their numbers.
Driven in Chromium (CHANGELOG): the heights, the folded lines and the list.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"

node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def _read(name: str) -> str:
    return (JS / name).read_text(encoding="utf-8")


@node
def test_a_label_key_is_the_typed_word_after_ref_or_eqref() -> None:
    text = _read("documents-prose.js")
    start = text.index("docPairInput.refTyped = ")
    code = text[start : text.index("\n};\n", start) + 4]
    script = (
        "function docPairInput() {}\n"
        + code
        + "\nconsole.log(JSON.stringify(['See \\\\ref{', 'see \\\\eqref{eq:o', '\\\\ref{a}', '\\\\label{x', 'ref{a'].map(docPairInput.refTyped)));"
    )
    out = subprocess.run(["node", "-"], input=script, capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr[-400:]
    assert json.loads(out.stdout.strip()) == ["", "eq:o", None, None, None]


def test_the_completion_is_wired_into_the_markdown_sources() -> None:
    assert "docPairInput.refSource(CM)" in _read("documents-code.js")
    assert "labels.index(docStr(context.state.doc))" in _read("documents-prose.js")


def test_a_multi_line_formula_is_drawn_over_its_first_line_and_folds_the_rest() -> None:
    cm = _read("documents-cm.js")
    assert "mdMathBlockFrom(blockLines, at)" in cm
    assert 'class: "cm-md-math-fold"' in cm
    assert '".cm-md-math-fold": { display: "none" }' in _read("documents-cm-theme.js")
    # the one-line rule still says why a replace may not span lines
    assert "[^$\\n]{1,400}" in cm
