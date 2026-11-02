"""Documents audit 1102, the quick wins (DX2, DX8, DX17, DX18, DX20, DX21, DX22).

Each test pins the cause the audit measured in a browser, so the fix cannot
quietly go back. The numbers are in CHANGELOG.md and the agent's remaining list.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from tests._app_js import documents_text

ROOT = Path(__file__).resolve().parents[1]
CSS = "".join(p.read_text(encoding="utf-8") for p in sorted((ROOT / "frontend/css").glob("*.css")))


def _fn_body(js: str, name: str) -> str:
    return js.split(f"function {name}(")[1].split("\n}\n")[0]


def _node_region(path: Path, begin: str, end: str, body: str):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    text = path.read_text(encoding="utf-8")
    region = text[text.index(begin) : text.index(end)]
    assert "document." not in region
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as handle:
        handle.write(region + "\n" + body)
    try:
        out = subprocess.run([node, handle.name], capture_output=True, text=True, timeout=30, check=True)
    finally:
        Path(handle.name).unlink(missing_ok=True)
    return json.loads(out.stdout)


def test_dx2_live_table_columns_have_a_floor():
    """A zero minimum shared 14 columns 594px (42px each) and wrapped a word
    one letter per line. A column has a floor and the line is as wide as its
    columns, so the editor scrolls sideways as the Read view does."""
    js = documents_text()
    body = _fn_body(js, "docTableGridRules")
    assert "minmax(0, 1fr)" not in body
    assert "minmax(var(--doc-table-col-min), 1fr)" in body
    assert "minWidth" in body and "--doc-table-col-min" in body.split("minWidth")[1]
    assert re.search(r'"--doc-table-col-min":\s*"6em"', js)
    assert '"minmax(0, 1fr)"' not in js.split('".cm-md-table-wide"')[1].split("}")[0]


def test_dx17_a_diagram_error_is_said_in_plain_words():
    """The parser's token list ("Expecting 'AMP', 'COLON' ...") told a writer
    nothing. The plain reason names the line and what is wrong with it, and
    the raw message is kept behind a disclosure (`mermaidFailure.note`)."""
    body = """
const mermaidState = { bad: new Map() };
const raw = "Parse error on line 3. Expecting 'AMP', 'COLON', 'PIPE'";
const two = "Parse error on line 2. Expecting 'X'";
console.log(JSON.stringify({
  arrow: mermaidFailure.plain(raw, "flowchart TD\\n  A -->\\n"),
  arrowSemi: mermaidFailure.plain(two, "flowchart TD\\n  A --> ;"),
  bracket: mermaidFailure.plain(two, "flowchart TD\\n  A[Start --> B"),
  quote: mermaidFailure.plain(two, 'flowchart TD\\n  A["Start --> B'),
  other: mermaidFailure.plain(two, "flowchart TD\\n  A B C D"),
  kind: mermaidFailure.plain("No diagram type detected matching given configuration for text: hello", "hello"),
  sentence: mermaidFailure.plain("The diagram is empty.", ""),
}));
"""
    out = _node_region(ROOT / "frontend/js/mermaid-draw.js", "// MERMAID-PLAIN-BEGIN", "// MERMAID-PLAIN-END", body)
    assert out["arrow"] == "Line 2: an arrow needs a box after it."
    assert out["arrowSemi"] == "Line 2: an arrow needs a box after it."
    assert out["bracket"] == "Line 2: a bracket is not closed."
    assert out["quote"] == "Line 2: a quote is not closed."
    assert out["other"].startswith("Line 2: this line is not valid here")
    assert out["kind"].startswith("The first line should name a diagram")
    assert out["sentence"] == "The diagram is empty."
    for text in out.values():
        assert "Expecting" not in text and "!" not in text and chr(8212) not in text


def test_dx17_both_views_build_the_note_in_one_place():
    js = (ROOT / "frontend/js/mermaid-draw.js").read_text(encoding="utf-8")
    live = (ROOT / "frontend/js/documents-mermaid.js").read_text(encoding="utf-8")
    assert "mermaidFailure.note(result.error, code.textContent)" in js
    assert "mermaidFailure.note(this.reason, this.source)" in live
    assert "Could not draw this diagram:" not in js + live
    assert ".md-mermaid-raw" in (ROOT / "frontend/css/mermaid-lazy.css").read_text(encoding="utf-8")


def test_dx18_a_formula_that_failed_to_parse_carries_a_problem():
    """`$\\frac{a}{$` drew a lone "a" and `$$\\begin{bad}x$$` drew "x", with no
    mark that anything was wrong. The parser stays total, and now says so."""
    body = r"""
const probe = (tex) => docMathTree(tex).problem;
console.log(JSON.stringify({
  open: probe("\\frac{a}{"),
  missing: probe("\\frac{a}"),
  env: probe("\\begin{bad}x"),
  noEnd: probe("\\begin{matrix} a & b"),
  stray: probe("a } b"),
  command: probe("\\mathbb{R}"),
  fine: [
    "x^2", "\\frac{a}{b}", "\\sqrt[3]{x}", "\\begin{pmatrix} a & b \\\\ c & d \\end{pmatrix}",
    "\\left(x\\right)", "a\\,b", "\\sum_{n=1}^{10} n", "\\text{one two}", "\\vec{v}", "a \\\\ b",
  ].map(probe),
}));
"""
    out = _node_region(ROOT / "frontend/js/documents-math.js", "// DOC-MATH-BEGIN", "// DOC-MATH-END", body)
    for key in ("open", "missing", "env", "noEnd", "stray", "command"):
        assert out[key], key
    assert out["fine"] == [""] * 10


def test_dx18_the_error_is_tinted_in_one_wrapper_for_live_and_read():
    js = (ROOT / "frontend/js/documents-math.js").read_text(encoding="utf-8")
    assert 'mark.className = "md-math-error"' in js and "mark.title" in js
    rule = CSS.split(".md-math-error {")[1].split("}")[0]
    assert "var(--error)" in rule and "var(--error-soft)" in rule
