"""Board tables: merged cells, stripes, row heights and a line dragged to size one
(LEDGER L273; WHITEBOARD_PLAN section 12). The pure half (`table-core` in
whiteboard-format.js) runs under node; the server keeps `merges`, `row_heights`
and `stripes` and refuses a merge that does not fit. The browser half (spans,
heights and a real drag, measured) is `scratchpad/ui-sweeps/wbtablemerge.js`."""

from __future__ import annotations

from tests._app_js import frontend_text
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FMT = (ROOT / "frontend" / "js" / "whiteboard-format.js").read_text(encoding="utf-8")
WB = frontend_text("whiteboard.js")
INTERCHANGE = (ROOT / "frontend" / "js" / "whiteboard-interchange.js").read_text(encoding="utf-8")
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "css" / "library-lazy.css").read_text(encoding="utf-8")
CORE_SRC = FMT[FMT.index("//: table-core-begin") : FMT.index("//: table-core-end")]
#: The rules live in one object (`wbTableRules`, a single name in the shared scope); node gets them as bare names.
CORE = CORE_SRC + "\nObject.assign(globalThis, wbTableRules);\n"


def _body(src: str, name: str) -> str:
    start = src.index(name)
    return src[start : src.index("\n}\n", start)]


def _js(expr: str, prelude: str = CORE):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    out = subprocess.run([node, "-e", prelude + f"\nconsole.log(JSON.stringify({expr}));"], capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip())


def _table(cells, **data):
    return {"cells": cells, **data}


GRID3 = [["a", "b", "c"], ["d", "e", "f"], ["g", "h", "i"]]


# --- the server -------------------------------------------------------------


def _post(client, cells, **extra):
    return client.post("/whiteboard/objects", json={"kind": "table", "data": {"cells": cells, **extra}, "x": 0, "y": 0, "width": 360, "height": 120})


def test_the_server_keeps_merges_stripes_and_row_heights(ai_client):
    merges = [{"r": 0, "c": 0, "rs": 2, "cs": 2}, {"r": 2, "c": 1, "rs": 1, "cs": 2}]
    made = _post(ai_client, GRID3, merges=merges, stripes=True, row_heights=[1, 1.5, 0.5])
    assert made.status_code in (200, 201), made.text
    data = made.json()["data"]
    assert data["merges"] == merges and data["stripes"] is True and data["row_heights"] == [1, 1.5, 0.5]
    obj = made.json()
    cleared = ai_client.put(f"/whiteboard/objects/{obj['id']}", json={"kind": "table", "data": {"cells": GRID3}, "x": 0, "y": 0, "width": 360, "height": 120})
    assert cleared.status_code == 200 and not cleared.json()["data"].get("merges")


@pytest.mark.parametrize(
    "extra",
    [
        {"merges": [{"r": 0, "c": 0, "rs": 1, "cs": 1}]},
        {"merges": [{"r": 2, "c": 2, "rs": 2, "cs": 1}]},
        {"merges": [{"r": 0, "c": 0, "rs": 2, "cs": 2}, {"r": 1, "c": 1, "rs": 2, "cs": 1}]},
        {"merges": [{"r": -1, "c": 0, "rs": 2, "cs": 1}]},
        {"row_heights": [1, 1]},
    ],
)
def test_the_server_refuses_a_merge_that_does_not_fit(ai_client, extra):
    assert _post(ai_client, GRID3, **extra).status_code == 422


# --- the pure rules ---------------------------------------------------------


def test_a_range_merges_into_its_top_left_cell_with_the_words_joined():
    out = _js(f"wbTableMergeRect({json.dumps(GRID3)}, [], {{r0: 0, c0: 0, r1: 1, c1: 1}})")
    assert out["merges"] == [{"r": 0, "c": 0, "rs": 2, "cs": 2}]
    assert out["cells"] == [["a b d e", "", "c"], ["", "", "f"], ["g", "h", "i"]]
    assert _js(f"wbTableMergeRect({json.dumps(GRID3)}, [], {{r0: 1, c0: 1, r1: 1, c1: 1}})") is None


def test_a_range_grows_to_hold_a_merge_it_cuts():
    merges = [{"r": 0, "c": 1, "rs": 1, "cs": 2}]
    out = _js(f"wbTableMergeRect({json.dumps(GRID3)}, {json.dumps(merges)}, {{r0: 0, c0: 0, r1: 1, c1: 1}})")
    assert out["merges"] == [{"r": 0, "c": 0, "rs": 2, "cs": 3}] and out["rect"] == {"r0": 0, "c0": 0, "r1": 1, "c1": 2}


def test_split_frees_the_merges_the_range_touches():
    merges = [{"r": 0, "c": 0, "rs": 2, "cs": 2}, {"r": 2, "c": 1, "rs": 1, "cs": 2}]
    assert _js(f"wbTableSplitRect({json.dumps(merges)}, {{r0: 1, c0: 1, r1: 1, c1: 1}})") == [merges[1]]


def test_a_bad_merge_list_cannot_break_the_grid():
    bad = [{"r": 0, "c": 0, "rs": 1, "cs": 1}, {"r": 2, "c": 2, "rs": 3, "cs": 1}, {"r": 0, "c": 0, "rs": 1, "cs": 2}, {"r": 0, "c": 1, "rs": 2, "cs": 1}, "x", None]
    assert _js(f"wbTableCleanMerges({json.dumps(bad)}, 3, 3)") == [{"r": 0, "c": 0, "rs": 1, "cs": 2}]


def test_rows_and_columns_going_in_or_out_move_shrink_and_grow_merges():
    m = [{"r": 1, "c": 0, "rs": 2, "cs": 2}]
    reshape = lambda axis, at, remove: _js(f"wbTableReshapeMerges({json.dumps(m)}, {json.dumps(axis)}, {at}, {json.dumps(remove)})")  # noqa: E731
    assert reshape("row", 0, False) == [{"r": 2, "c": 0, "rs": 2, "cs": 2}], "a row above moves it down"
    assert reshape("row", 2, False) == [{"r": 1, "c": 0, "rs": 3, "cs": 2}], "a row inside it grows it"
    assert reshape("row", 3, False) == m, "a row after it leaves it"
    assert reshape("row", 2, True) == [{"r": 1, "c": 0, "rs": 1, "cs": 2}], "a row out of it shrinks it"
    assert reshape("row", 0, True) == [{"r": 0, "c": 0, "rs": 2, "cs": 2}]
    assert reshape("col", 1, True) == [{"r": 1, "c": 0, "rs": 2, "cs": 1}]
    one = [{"r": 0, "c": 0, "rs": 1, "cs": 2}]
    assert _js(f"wbTableReshapeMerges({json.dumps(one)}, 'col', 1, true)") == [], "a merge left covering one cell is dropped"


def test_stripes_tint_every_other_body_row_and_never_the_header():
    on = {"data": {"stripes": True, "header": True}}
    assert _js(f"[0, 1, 2, 3, 4].map((r) => wbTableStripe({json.dumps(on)}, r))") == [False, False, True, False, True]
    plain = {"data": {"stripes": True}}
    assert _js(f"[0, 1, 2, 3].map((r) => wbTableStripe({json.dumps(plain)}, r))") == [False, True, False, True]
    assert _js("wbTableStripe({data: {header: true}}, 2)") is False


def test_row_heights_read_as_equal_unless_one_per_row():
    assert _js(f"wbTableRowWeights({{data: {json.dumps(_table(GRID3, row_heights=[2, 0.5, 0.5]))}}})") == [2, 0.5, 0.5]
    assert _js(f"wbTableRowWeights({{data: {json.dumps(_table(GRID3, row_heights=[2, 1]))}}})") == [1, 1, 1]


def test_dragging_a_line_trades_width_between_the_two_tracks_and_keeps_the_mean():
    assert _js("wbTableDragWeights([1, 1, 1], 0, 0.5)") == [1.5, 0.5, 1]
    assert _js("wbTableDragWeights([1, 1, 1], 1, -0.5)") == [1, 0.5, 1.5]
    #: Held to the least a track may take (a quarter of the mean) and the most (six).
    assert _js("wbTableDragWeights([1, 1, 1], 0, 5)") == [1.75, 0.25, 1]
    assert _js("wbTableDragWeights([1, 1, 1], 0, -5)") == [0.25, 1.75, 1]
    assert _js("wbTableDragWeights([1, 1], 0, 0)") is None
    assert _js("wbTableDragWeights([1, 1], 1, 1)") is None


def test_axis_weights_follow_a_new_or_removed_track():
    assert _js("wbTableAxisWeights([2, 1, 1], 1, false)") == [1.5, 1, 0.75, 0.75]
    assert _js("wbTableAxisWeights([2, 1, 1], 0, true)") == [1, 1]


def test_cell_boxes_span_merged_cells_and_follow_the_weights():
    d = {"data": _table(GRID3, merges=[{"r": 0, "c": 0, "rs": 2, "cs": 2}], col_widths=[2, 0.5, 0.5], row_heights=[1, 1, 1], stripes=True, header=True)}
    boxes = _js(f"wbTableCellBoxes({json.dumps(d)}, 300, 90)")
    by = {(b["r"], b["c"]): b for b in boxes}
    assert len(boxes) == 9 - 3, "the three cells under the merge are not drawn"
    assert (0, 1) not in by and (1, 0) not in by and (1, 1) not in by
    first = by[(0, 0)]
    assert (first["x"], first["y"], round(first["w"]), round(first["h"])) == (0, 0, 250, 60), "two columns of three-quarters of the width"
    assert by[(0, 0)]["head"] is True and by[(2, 0)]["stripe"] is True and by[(2, 1)]["stripe"] is True
    assert round(by[(2, 2)]["x"]) == 250 and round(by[(2, 2)]["w"]) == 50


# --- the board --------------------------------------------------------------


def test_the_grid_paints_spans_stripes_and_grips_from_the_data():
    paint = _body(FMT, "function wbPaintTable(")
    assert "wbTableCovered(merges, r, c)" in paint, "a covered cell is not drawn"
    assert "cell.style.gridRow" in paint and "cell.style.gridColumn" in paint and "span ${" in paint
    assert "dataset.stripe" in paint and "dataset.head" in paint
    assert "d.data?.stripes" in paint and "heights, merges" in paint, "the redraw key holds stripes, heights and merges"
    assert 'grip("col", c, from, to)' in paint and 'grip("row", r, from, to)' in paint and "wbTableGripRuns(" in paint
    assert "gridTemplateRows" in _body(FMT, "function wbTableTracks(")


def test_a_dragged_line_is_one_undo_step_written_on_release():
    drag = _body(FMT, "function wbTableGripDrag(")
    assert "wbTableDragWeights(" in drag and "wbSetTable(" in drag
    assert drag.count("wbSetTable(") == 1, "one write, on release, so one Undo step"
    assert "pointercancel" in drag and "stopPropagation" in drag
    set_table = _body(FMT, "async function wbSetTable(")
    assert set_table.count("wbPushUndo(") == 1
    #: The object's own drag listens for mouse and touch events, so the grip stops those too.
    assert "mousedown" in _body(FMT, "function wbPaintTable(") and "touchstart" in _body(FMT, "function wbPaintTable(")
    assert ".wb-selected .wb-table-grip" in CSS and "cursor: col-resize" in CSS and "cursor: row-resize" in CSS


def test_merge_and_split_are_item_menu_rows_and_one_undo_step_each():
    rows = _body(FMT, "function wbTableMergeRows(")
    for words in ("Merge cells", "Split cell", "Merge with the cell on the right", "Merge with the cell below"):
        assert words in rows
    assert rows.count("wbSetTable(") == 2, "a merge and a split are each one write"
    menu = _body(FMT, "function wbTableMenuRows(")
    assert "...wbTableRules.wbTableMergeRows(" in menu and "...wbTableRules.wbTableSizeRows(" in menu and "Striped rows" in menu
    sizes = _body(FMT, "function wbTableSizeRows(")
    for words in ("Taller row", "Shorter row", "Equal row heights", "Widen this column"):
        assert words in sizes, "the menu keeps a keyboard way to size a row or a column"
    assert "wbTableMenuRows(table)" in WB


def test_a_shift_click_picks_a_range_and_does_not_toggle_the_selection():
    build = _body(FMT, "function wbBuildTable(")
    assert "event.shiftKey" in build and "wbTableRect(here" in build and "tableRange" in build
    assert '.on("click"' in build and "event.stopPropagation()" in build
    assert ".wb-table-cell.is-picked" in CSS


def test_editing_a_row_or_column_carries_merges_and_heights_and_tab_skips_covered_cells():
    reshape = _body(FMT, "function wbTableReshape(")
    assert "wbTableReshapeMerges(" in reshape and "row_heights" in reshape and "wbTableAxisWeights(" in reshape
    edit = _body(FMT, "function wbEditTableCell(")
    assert "wbTableCovered(merges" in edit


def test_stripes_are_a_format_row_and_a_menu_row():
    assert '"tableheader", "stripes"' in FMT
    for ident in ("wb-fmt-stripes", "wb-fmt-tableheader"):
        assert f'id="{ident}"' in HTML and f'on("{ident}"' in FMT
    assert 'data-fmt="stripes"' in HTML
    assert ".wb-table-cell[data-stripe]" in CSS


def test_the_svg_export_draws_spans_stripes_and_heights_from_the_same_boxes():
    svg = _body(FMT, "function wbSvgTable(")
    assert "wbTableCellBoxes(obj, obj.width, obj.height)" in svg and "cell.stripe" in svg and "cell.head" in svg


# --- the draw.io file -------------------------------------------------------


def test_the_drawio_file_carries_a_table_as_its_cells_with_spans():
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    pure = INTERCHANGE[: INTERCHANGE.index("//: The rows inside an SVG")] + CORE
    state = {
        "nodes": [],
        "sketches": [],
        "objects": [
            {
                "id": 7, "kind": "table", "x": 100, "y": 50, "width": 300, "height": 90, "z": 1,
                "data": _table(GRID3, merges=[{"r": 0, "c": 0, "rs": 2, "cs": 2}], header=True, stripes=True),
            },
            {"id": 8, "kind": "table", "x": 0, "y": 0, "width": 50, "height": 50, "z": 1, "data": {}},
        ],
    }
    script = pure + f"\nconsole.log(JSON.stringify(wbBoardToDrawio({json.dumps(state)}, {{ title: 'T' }})));"
    out = json.loads(subprocess.run([node, "-e", script], capture_output=True, text=True, check=True).stdout.strip())
    import re

    geos = re.findall(r'value="([^"]*)" style="([^"]*)" vertex="1" parent="1"><mxGeometry x="(\d+)" y="(\d+)" width="(\d+)" height="(\d+)"', out["xml"])
    assert len(geos) == 6, "nine cells less the three under the merge"
    first = geos[0]
    assert first[0] == "a" and first[2:] == ("100", "50", "200", "60"), first
    assert "fontStyle=1" in first[1] and "#eef1f6" in first[1], "the header cell is bold on its tint"
    assert out["skipped"] == {"tables": 1}, "a table with no cells is still counted as left out"


def test_the_rules_are_called_through_the_one_object_not_as_bare_globals():
    """The table's rules sit behind `wbTableRules` (one name in the shared scope, tests/test_global_scope_ratchet.py);
    a bare call from outside the block would be a ReferenceError that only a drag or a menu opening finds."""
    import re

    names = re.findall(r"^  function (wbTable\w+)\(", CORE_SRC, re.M)
    assert len(names) >= 15
    inner = FMT[FMT.index("const wbTableRules = (() => {") : FMT.index("//: table-core-end")]
    outside = FMT.replace(inner, "") + INTERCHANGE
    for name in names:
        bare = re.findall(rf"(?<![\w.]){name}\(", outside)
        assert not bare, f"{name} is called bare outside the block"
