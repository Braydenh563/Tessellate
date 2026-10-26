"""A coloured text box, a sticky and a table export as themselves (wbdog-1026).

Measured before the fix: a sticky with a yellow paper and a table of four cells
exported as bare words (SVG, PNG and PDF all read the same SVG): the board's
background rect was the only `<rect>`, and the table was not in the file at all.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WB = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")
FMT = (ROOT / "frontend" / "js" / "whiteboard-format.js").read_text(encoding="utf-8")


def _slice(src: str, start: str, end: str) -> str:
    return src[src.index(start) : src.index(end)]


def _run(expr: str, prelude: str = ""):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    code = (
        "const wbSvgEscape = (s) => String(s).replace(/&/g, '&amp;').replace(/\"/g, '&quot;').replace(/</g, '&lt;');"
        "const wbSvgText = (lines, x, y, o = {}) => `<text x=\"${x}\" y=\"${y}\" fill=\"${o.fill}\">${lines.join('|')}</text>`;"
        "const wbSvgWrapLines = (t) => [String(t)];"
        "const wbTableCells = (d) => d.data.cells;"
        + prelude
        + _slice(FMT, "//: **A text box, a sticky or a table, as the export draws it.**", "function wbBuildTable(")
        + f"console.log(JSON.stringify({expr}));"
    )
    return json.loads(subprocess.run([node, "-e", code], capture_output=True, text=True, check=True).stdout)


def test_one_radius_per_corner_makes_one_path():
    path = _run("wbSvgRoundedPath(100, 50, [24, 0, 24, 0])")
    assert path.startswith("M24 0H100A0 0")
    assert "A24 24 0 0 1 24 0Z" in path


def test_a_radius_cannot_pass_half_the_short_side():
    assert "A25 25" in _run("wbSvgRoundedPath(100, 50, [999, 0, 0, 0])")


def test_a_filled_box_with_no_element_draws_its_data_paper():
    out = _run('wbSvgBoxBackdrop(null, { bg: "#fde68a", radii: [8, 8, 8, 8] }, 200, 100)')
    assert 'fill="#fde68a"' in out and "<path" in out


def test_a_box_with_no_fill_and_no_edge_draws_nothing():
    assert _run("wbSvgBoxBackdrop(null, {}, 200, 100)") == ""
    assert _run('wbSvgBoxBackdrop(null, { bg: "transparent" }, 200, 100)') == ""


def test_a_table_draws_a_rect_and_the_words_for_every_cell():
    out = _run('wbSvgTable(null, { width: 200, height: 100, data: { header: true, cells: [["a", "b"], ["c", "d"]] } })')
    assert out.count("<rect") == 4
    assert all(f">{w}</text>" in out for w in "abcd")


def test_the_export_calls_both_for_the_object_kinds():
    assert "wbSvgBoxBackdrop(" in WB and "wbSvgTable(" in WB
