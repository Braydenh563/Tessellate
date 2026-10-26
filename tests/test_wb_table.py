"""A table on the board (INBOX 797, canvasdepth2; WHITEBOARD_PLAN section 12
and "canvasdepth, ranked" row 8, draw.io's). An object of kind `table`:
`data.cells`, a rectangle of text, and `data.header`. The browser half
(typing, Tab, rows and columns at the pressed cell, resize, reopen, Undo) is
`scratchpad/ui-sweeps/wbdepth2.js wbtable`."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FMT = (ROOT / "frontend" / "js" / "whiteboard-format.js").read_text(encoding="utf-8")
WB = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")


def _body(src: str, name: str) -> str:
    start = src.index(name)
    return src[start : src.index("\n}\n", start)]


def _post(client, cells, **extra):
    return client.post("/whiteboard/objects", json={"kind": "table", "data": {"cells": cells, **extra}, "x": 0, "y": 0, "width": 360, "height": 120})


def test_a_table_is_a_rectangle_of_cells(ai_client):
    made = _post(ai_client, [["Name", "Owner"], ["Plan", "Ann"]], header=True)
    assert made.status_code in (200, 201), made.text
    assert made.json()["data"]["cells"] == [["Name", "Owner"], ["Plan", "Ann"]] and made.json()["data"]["header"] is True
    for bad in ([], [["a", "b"], ["c"]], [["x"] * 21], [["x"]] * 51, [["y" * 501]]):
        refused = _post(ai_client, bad)
        assert refused.status_code == 422, bad
    obj = made.json()
    moved = ai_client.put(f"/whiteboard/objects/{obj['id']}", json={"kind": "table", "data": {**obj["data"], "cells": [["a", "b", "c"]]}, "x": 0, "y": 0, "width": 360, "height": 40})
    assert moved.status_code == 200 and moved.json()["data"]["cells"] == [["a", "b", "c"]]
    ragged = ai_client.put(f"/whiteboard/objects/{obj['id']}", json={"kind": "table", "data": {"cells": [["a"], ["b", "c"]]}, "x": 0, "y": 0, "width": 360, "height": 40})
    assert ragged.status_code == 422


def test_the_grid_is_built_painted_and_edited_in_place():
    assert "wbBuildTable(el, d);" in WB and "wbPaintTable(this, d);" in WB
    paint = _body(FMT, "function wbPaintTable(")
    assert "[contenteditable='true']" in paint, "a cell being typed in is never redrawn under it"
    assert "grid.dataset.key === key" in paint
    edit = _body(FMT, "function wbEditTableCell(")
    for key in ('"Escape"', '"Enter"', '"Tab"'):
        assert key in edit
    #: The next cell takes the keyboard before this one is saved.
    done = edit[edit.index("const done = ") :]
    assert done.index("wbEditTableCell(id, moveTo[0], moveTo[1])") < done.index("wbSetTable(d, cells)")


def test_rows_and_columns_go_in_at_the_pressed_cell_and_the_box_follows():
    reshape = _body(FMT, "function wbTableReshape(")
    assert "d.height / rows" in reshape and "d.width / cols" in reshape
    rows = _body(FMT, "function wbTableMenuRows(")
    for words in ("Add a row below", "Add a column to the right", "Delete this row", "First row as a header"):
        assert words in rows
    assert "wbTableMenuRows(table)" in WB
    assert 'data-wb-cmd="insert-table"' in HTML


# --- column widths (wb5) ------------------------------------------------------


def _node(expr: str):
    import json
    import shutil
    import subprocess

    import pytest

    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    start = FMT.index("const WB_TABLE_WEIGHT_MIN")
    code = (
        "const wbTableCells = (d) => d.data.cells;"
        + FMT[start : FMT.index("//: **A text box, a sticky or a table, as the export draws it.**")]
        + f"console.log(JSON.stringify({expr}));"
    )
    return json.loads(subprocess.run([node, "-e", code], capture_output=True, text=True, check=True).stdout)


def test_a_table_with_no_widths_is_equal_and_a_bad_list_reads_as_equal():
    table = '{ data: { cells: [["a", "b", "c"]] } }'
    assert _node(f"wbTableWeights({table})") == [1, 1, 1]
    assert _node('wbTableWeights({ data: { cells: [["a", "b"]], col_widths: [1, 2, 3] } })') == [1, 1]
    assert _node('wbTableWeights({ data: { cells: [["a", "b"]], col_widths: [0, 2] } })') == [1, 1]
    assert _node('wbTableWeights({ data: { cells: [["a", "b"]], col_widths: [3, 1] } })') == [3, 1]


def test_widening_a_column_makes_the_others_give_way_and_keeps_the_mean():
    out = _node("wbTableResizeColumn([1, 1, 1], 0, 1.25)")
    assert out[0] > out[1] == out[2] and abs(sum(out) / 3 - 1) < 0.002
    narrow = _node("wbTableResizeColumn([1, 1, 1], 1, 0.8)")
    assert narrow[1] < narrow[0] == narrow[2]


def test_a_column_stops_at_the_least_and_the_most_it_may_take():
    least = _node("wbTableResizeColumn([0.25, 3], 0, 0.8)")
    assert least is None or least[0] / least[1] >= 0.25 / 3 - 0.001
    assert _node("wbTableResizeColumn([1, 1], 0, 1)") is None


def test_the_edges_are_shares_of_the_width():
    assert _node("wbTableColumnEdges([2, 1, 1])") == [0, 0.5, 0.75, 1]


def test_the_grid_the_menu_the_export_and_a_reshape_read_the_widths():
    assert "wbTableWeights(d)" in _body(FMT, "function wbPaintTable(")
    assert "minmax(0, ${n}fr)" in _body(FMT, "function wbPaintTable(")
    assert "wbTableColumnEdges(" in _body(FMT, "function wbSvgTable(")
    rows = _body(FMT, "function wbTableMenuRows(") + _body(FMT, "function wbTableWidthRows(")
    for words in ("Widen this column", "Narrow this column", "Equal column widths"):
        assert words in rows
    assert "col_widths" in _body(FMT, "function wbTableReshape(")


def test_widths_are_stored_one_per_column_or_refused(ai_client):
    made = _post(ai_client, [["a", "b"], ["c", "d"]], col_widths=[2, 0.5])
    assert made.status_code in (200, 201), made.text
    assert made.json()["data"]["col_widths"] == [2, 0.5]
    for bad in ([1], [1, 1, 1], [0, 1], [1, 99]):
        refused = _post(ai_client, [["a", "b"]], col_widths=bad)
        assert refused.status_code == 422, bad
