"""The 22-10 bug doc's format bar rows (OPEN.md): a line given an End mark
stays a line or arrow to the Format panel, an end with no mark shows no size,
and a bar that wraps is a panel with no hairline at a row's start.

Measured in Chromium by scratchpad/ui-sweeps/wb1025-bar.js (line bar at 1440:
913 to 700px wide; at 720: three rows, 150px tall, to two rows, 102px).
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BOARD = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")
FORMAT = (ROOT / "frontend" / "js" / "whiteboard-format.js").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "css" / "library-lazy.css").read_text(encoding="utf-8")


def _function(source: str, name: str) -> str:
    start = source.index(f"function {name}(")
    return source[start : source.index("\n}\n", start) + 3]


@pytest.mark.parametrize(
    ("d", "kind"),
    [
        ("M 120 200 L 320 260", "arrow"),
        # An End mark: the filled triangle closes its own subpath with a Z.
        ("M 120 200 L 320 260 M 320 260 L 300.69 261.72 L 304.83 247.93 Z", "arrow"),
        # A closed outline is a shape whatever it was drawn with: no ends.
        ("M 0 0 L 100 0 L 100 50 L 0 50 Z", "shape"),
    ],
)
def test_a_line_with_an_end_mark_is_still_a_line(d: str, kind: str) -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    script = (
        "const WB_MAP_KINDS = new Set();\nconst WB_FILLABLE_SHAPES = new Set(['rect','circle','triangle','diamond']);\n"
        "function wbSketchIsArrow() { return false; }\n"
        + _function(BOARD, "wbSketchTakesCaps")
        + _function(BOARD, "wbShapeLabelKind")
        + _function(FORMAT, "wbFmtKind")
        + f"\nconsole.log(JSON.stringify(wbFmtKind({{ kind: 'sketch', item: {{ data: JSON.stringify({{ shape: 'line', d: {json.dumps(d)} }}) }} }})));\n"
    )
    out = subprocess.run([node, "-e", script], capture_output=True, text=True, check=True)
    assert json.loads(out.stdout.strip()) == kind


def test_an_end_with_no_mark_hides_its_size() -> None:
    body = _function(BOARD, "wbShowCapSizes")
    assert '.classList.toggle("hidden", none)' in body


def test_a_wrapped_bar_is_a_panel_without_a_leading_hairline() -> None:
    assert "wb-context-wrapped" in _function(BOARD, "wbUpdateSelectionBar")
    assert ".wb-context.wb-context-wrapped {" in CSS
    assert ".wb-context .wb-context-group.wb-row-start:not(.hidden) {" in CSS


def test_a_colour_tab_keeps_the_panel_where_it_is() -> None:
    """The 22-10 bug doc: the Fill tab moved the popup (310px left from the
    rail's ink to the tool's fill, or to 8,4 against a hidden well);
    scratchpad/ui-sweeps/wb1025-colourtabs.js: 0px for every pair."""
    body = _function(FORMAT, "wbOpenColourMenu")
    assert "keepAt" in body and "partner.fillEl === input || partner.borderEl === input" in body
    assert "prevOpener" not in body
