"""`\\begin{equation}` numbers itself (DOCUMENTS_PLAN gap row 16, the numbering part).

LaTeX writers expect `\\begin{equation} ... \\end{equation}` to be a display
equation with the next number, `equation*` to have none, and `\\label` and
`\\tag` to work inside it as they do in `$$`. The read view takes the block
through `mdMathBlockFrom` (one door for the read view, a note card and a chat
answer), which hands the renderer the formula with a synthetic `\\label`; the
page index (`docMathIndex`) gives every such block its place in the one count
that `$$` blocks with a `\\label` share. Both run in node here.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"

node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def _driver(body: str) -> object:
    math = (JS / "documents-math.js").read_text(encoding="utf-8")
    region = math[math.index("// DOC-MATH-BEGIN") : math.index("// DOC-MATH-END")]
    md = (JS / "markdown.js").read_text(encoding="utf-8")
    start = md.index("function mdMathBlockFrom(")
    block = md[start : md.index("\n}\n", start) + 3]
    env = math[math.index("// DOC-EQUATION-BEGIN") : math.index("// DOC-EQUATION-END")]
    script = "var window = {};\n" + block + "\nwindow.mdMathBlockFrom = mdMathBlockFrom;\n" + region + "\n" + env + "\n" + body
    out = subprocess.run(["node", "-"], input=script, capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr[-500:]
    return json.loads(out.stdout.strip().splitlines()[-1])


@node
def test_an_equation_block_reads_as_display_math_with_a_hidden_label() -> None:
    got = _driver(
        "const lines = ['Intro', '\\\\begin{equation}', 'a = 1', '\\\\end{equation}', 'After'];"
        "const hit = window.mdMathBlockFrom(lines, 1);"
        "console.log(JSON.stringify({ tex: hit.tex, end: hit.end, none: window.mdMathBlockFrom(lines, 0) }));"
    )
    assert got["end"] == 4 and got["none"] is None
    assert got["tex"].startswith("a = 1") and got["tex"].endswith("\\label{eq-auto-1}")


@node
def test_a_starred_block_and_a_labelled_one_are_left_alone() -> None:
    got = _driver(
        "const star = window.mdMathBlockFrom(['\\\\begin{equation*}', 'a', '\\\\end{equation*}'], 0);"
        "const named = window.mdMathBlockFrom(['\\\\begin{equation}', 'a \\\\label{k}', '\\\\end{equation}'], 0);"
        "const tagged = window.mdMathBlockFrom(['\\\\begin{equation}', 'a \\\\tag{A}', '\\\\end{equation}'], 0);"
        "console.log(JSON.stringify([star.tex, named.tex, tagged.tex]));"
    )
    assert got == ["a", "a \\label{k}", "a \\tag{A}"]


@node
def test_one_line_form_and_the_second_block_number() -> None:
    got = _driver(
        "const lines = ['\\\\begin{equation} x \\\\end{equation}', '', '\\\\begin{equation}', 'y', '\\\\end{equation}'];"
        "console.log(JSON.stringify([window.mdMathBlockFrom(lines, 0).tex, window.mdMathBlockFrom(lines, 2).tex]));"
    )
    assert got[0] == "x \\label{eq-auto-1}" and got[1] == "y \\label{eq-auto-2}"


@node
def test_the_index_numbers_both_kinds_in_page_order() -> None:
    got = _driver(
        "const page = '$$a \\\\label{a}$$\\n\\n\\\\begin{equation}\\nb\\n\\\\end{equation}\\n\\n"
        "\\\\begin{equation*}\\nc\\n\\\\end{equation*}\\n\\n\\\\begin{equation}\\nd \\\\tag{Z}\\n\\\\end{equation}\\n\\n"
        "\\\\begin{equation}\\ne \\\\label{e}\\n\\\\end{equation}';"
        "const m = docMathIndex(page);"
        "docMathUse(m);"
        "const shown = docMathTree('b \\\\label{eq-auto-1}', true).label;"
        "console.log(JSON.stringify({ map: [...m], shown }));"
    )
    assert dict(map(tuple, got["map"])) == {"a": "1", "eq-auto-1": "2", "eq-auto-2": "Z", "eq-auto-3": "3", "e": "3"}
    assert got["shown"] == "2"


def test_a_page_with_only_an_equation_block_is_indexed() -> None:
    math = (JS / "documents-math.js").read_text(encoding="utf-8")
    page = re.search(r"page: \(text\) => [^\n]+", math)
    assert page and "begin" in page.group(0)
