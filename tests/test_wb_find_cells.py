"""Find and Replace read a table's cells (wbdog-1026: a table holding the word was "0 matches")."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WB = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")


def _run(expr: str):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    a = WB.index("function wbReplaceText(")
    b = WB.index("function wbReplaceInProps(")
    c = WB.index("function wbCellsText(")
    d = WB.index("//: Find reads an item's data values too")
    script = (
        "const wbBoardSearch = {};"
        "function wbSearchPattern(q) { const re = new RegExp(q.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\\\$&'), 'gim'); return { re, has: (t) => { re.lastIndex = 0; return re.test(t); } }; }"
        + WB[a:b] + WB[c:d] + f"console.log(JSON.stringify({expr}));"
    )
    return json.loads(subprocess.run([node, "-e", script], capture_output=True, text=True, check=True).stdout)


def test_cells_are_one_searchable_string():
    assert "zebra" in _run('wbCellsText([["a", "zebra"], ["", null]])')
    assert _run("wbCellsText(undefined)") == ""


def test_replace_rewrites_every_cell_and_counts_them():
    out = _run('wbReplaceInCells([["zebra a", "b"], ["c", "Zebra"]], "zebra", "okapi")')
    assert out["count"] == 2
    assert out["cells"] == [["okapi a", "b"], ["c", "okapi"]]


def test_search_and_replace_both_use_the_cells():
    assert "wbCellsText(data.cells)" in WB
    assert "wbReplaceInCells(own?.cells" in WB
