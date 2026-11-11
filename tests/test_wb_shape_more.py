"""F2, draw.io's ports and points: a table's row ports (`portConstraint=eastwest`) and, below, a shape's own points.

`whiteboard-shape-more.js` is run in node against a small stand-in for the board, so what it writes is read back as numbers."""

from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from pathlib import Path

from tests._app_js import frontend_text

ROOT = Path(__file__).resolve().parents[1]

STAND_INS = r"""
const wbFmtState = {};
const onSurface = () => {};
const saved = [];
const wbState = { sketches: [] };
const wbIsLinkSketch = (s) => /"type"\s*:\s*"link-/.test(s.data || "");
const wbSketchData = (s) => JSON.parse(s.data);
const wbSaveSketchProps = async (sketch, patch) => { saved.push({ id: sketch.id, patch }); };
const link = (id, data) => ({ id, data: JSON.stringify({ type: "link-straight", sourceKind: "node", targetKind: "node", ...data }) });
"""


def _run(body: str):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    script = STAND_INS + frontend_text("whiteboard-shape-more.js") + "\n(async () => {" + body + "})();"
    return json.loads(subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=30, check=True).stdout)


def test_a_table_has_the_two_ends_of_every_row_and_the_middles_of_its_top_and_bottom():
    got = _run("console.log(JSON.stringify(wbFmtState.shapeMore.tableRowPorts(3)));")
    assert got == [
        {"x": 0, "y": 0.1667}, {"x": 1, "y": 0.1667}, {"x": 0, "y": 0.5}, {"x": 1, "y": 0.5},
        {"x": 0, "y": 0.8333}, {"x": 1, "y": 0.8333}, {"x": 0.5, "y": 0}, {"x": 0.5, "y": 1},
    ]
    assert _run("console.log(JSON.stringify(wbFmtState.shapeMore.tableRowPorts(0).length));") == 4


def test_an_anchor_is_on_a_row_only_at_the_side_and_at_the_middle_of_the_row():
    got = _run(
        "const m = wbFmtState.shapeMore;"
        "console.log(JSON.stringify([m.rowOf({ x: 0, y: 0.5 }, 3), m.rowOf({ x: 1, y: 0.8333 }, 3), m.rowOf({ x: 0.5, y: 0 }, 3),"
        " m.rowOf({ x: 0, y: 0.5 }, 2), m.rowOf({ x: 0.3, y: 0.5 }, 3), m.rowOf(null, 3)]));"
    )
    assert got == [1, 2, -1, -1, -1, -1]


def test_adding_or_removing_a_row_moves_the_rows_after_it_and_lets_go_of_the_removed_one():
    got = _run(
        "const m = wbFmtState.shapeMore; console.log(JSON.stringify([m.rowAfter(0, 1, false), m.rowAfter(1, 1, false), m.rowAfter(2, 1, false),"
        " m.rowAfter(0, 1, true), m.rowAfter(1, 1, true), m.rowAfter(2, 1, true)]));"
    )
    assert got == [0, 2, 3, 0, -1, 1]


def test_a_connector_on_a_row_follows_its_row_when_a_row_is_added_above_it():
    got = _run(
        "const m = wbFmtState.shapeMore;"
        "wbState.sketches = [link(1, { sourceId: 7, sourceKind: 'object', targetId: 2, sourceAnchor: { x: 1, y: 0.5 } }),"
        " link(2, { sourceId: 8, sourceKind: 'object', targetId: 7, targetKind: 'object', targetAnchor: { x: 0, y: 0.1667 } }),"
        " link(3, { sourceId: 7, sourceKind: 'object', targetId: 2, sourceAnchor: { x: 0.5, y: 0 } })];"
        "const run = m.carryRowPorts({ id: 7 }, 1, false, 3); await run(); console.log(JSON.stringify(saved));"
    )
    #: Three rows become four: row 1 (y 0.5) is now row 2 (y 0.625); row 0 stays row 0 (y 0.125); the top edge's middle is not a row.
    assert got == [
        {"id": 1, "patch": {"sourceAnchor": {"x": 1, "y": 0.625}}},
        {"id": 2, "patch": {"targetAnchor": {"x": 0, "y": 0.125}}},
    ]


def test_a_connector_on_a_removed_row_floats_and_nothing_to_carry_gives_no_job():
    got = _run(
        "const m = wbFmtState.shapeMore;"
        "wbState.sketches = [link(1, { sourceId: 7, sourceKind: 'object', targetId: 2, sourceAnchor: { x: 1, y: 0.5, dx: 3 } })];"
        "const run = m.carryRowPorts({ id: 7 }, 1, true, 3); await run();"
        "console.log(JSON.stringify([saved, JSON.stringify(saved[0].patch), m.carryRowPorts({ id: 9 }, 0, false, 3)]));"
    )
    assert got[0] == [{"id": 1, "patch": {}}]  # the anchor key is undefined, which JSON drops: the end floats
    assert got[1] == "{}"
    assert got[2] is None


def test_the_table_ports_are_wired_into_the_port_lookup_the_reshape_and_the_lazy_board_bundle():
    assert 'item.kind === "table"' in frontend_text("whiteboard.js")
    assert "shapeMore?.carryRowPorts" in frontend_text("whiteboard-format.js")
    assert "/js/whiteboard-shape-more.js" in frontend_text("lazy-entries.js")


def test_a_closed_shape_of_straight_sides_gives_its_corners_and_nothing_else_does():
    got = _run(
        "const m = wbFmtState.shapeMore, P = m.polygonPoints;"
        "console.log(JSON.stringify([P('M 0 0 L 120 0 L 120 70 L 0 70 Z'), P('M 10 10 H 50 V 40 H 10 Z').length, P('m 10 10 l 40 0 l 0 30 z').length,"
        " P('M 0 0 L 10 0 L 10 10 L 0 0 Z').length, P('M 0 0 L 10 0 L 10 10'), P('M 0 0 C 1 1 2 2 3 3 L 5 5 Z'), P('M 0 0 L 10 0 L 10 10 Z M 20 20 L 30 20 L 30 30 Z'),"
        " P('M 0 0 L 10 0 Z'), P('')]));"
    )
    assert got[0] == [{"x": 0, "y": 0}, {"x": 120, "y": 0}, {"x": 120, "y": 70}, {"x": 0, "y": 70}]
    #: H and V, and relative moves, give the same corners; a path that returns to its start does not repeat it.
    assert got[1:4] == [4, 3, 3]
    #: Open, curved, two outlines, two corners, empty: not editable.
    assert got[4:] == [None, None, None, None, None]


def test_the_path_written_back_is_a_closed_run_of_straight_sides_to_two_places():
    got = _run(
        "const m = wbFmtState.shapeMore; const d = m.polygonD([{ x: 0, y: 0 }, { x: 10.126, y: 0 }, { x: 5, y: 7.5 }]);"
        "console.log(JSON.stringify([d, m.polygonPoints(d)]));"
    )
    assert got[0] == "M 0 0 L 10.13 0 L 5 7.5 Z"
    assert got[1] == [{"x": 0, "y": 0}, {"x": 10.13, "y": 0}, {"x": 5, "y": 7.5}]


def test_a_press_takes_the_nearest_corner_within_reach_else_the_nearest_side_is_found_for_a_new_one():
    got = _run(
        "const m = wbFmtState.shapeMore, sq = m.polygonPoints('M 0 0 L 100 0 L 100 100 L 0 100 Z');"
        "console.log(JSON.stringify([m.nearestCorner(sq, 97, 4, 8), m.nearestCorner(sq, 50, 50, 8), m.nearestOnSide(sq, 60, -3), m.nearestOnSide(sq, 104, 30), m.nearestOnSide(sq, 10, 99)]));"
    )
    assert got[0] == 1 and got[1] == -1
    #: A corner added on the top side goes after corner 0 (index 1); on the right after corner 1 (index 2); on the bottom after corner 2... the bottom runs corner 2 to 3, so index 3.
    assert [(side["index"], side["x"], side["y"]) for side in got[2:4]] == [(1, 60, 0), (2, 100, 30)]
    assert got[4]["index"] == 3 and got[4]["x"] == 10 and got[4]["y"] == 100 and abs(got[4]["dist"] - 1) < 1e-9


def test_the_points_editor_is_a_command_in_the_menus_and_it_saves_one_undo_step_per_change():
    cmds = frontend_text("whiteboard-commands.js")
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    row = cmds.split('id: "edit-points"')[1].split("\n")[0]
    assert 'needs: "polygon"' in row and 'surface: "board"' in row
    assert html.count('data-wb-cmd="edit-points"') == 1
    assert "polygon: () => Boolean(wbFmtState.shapeMore?.pointsTarget())" in cmds
    assert '"edit-points"' in frontend_text("whiteboard.js")  # also in the context menu's Arrange list
    source = frontend_text("whiteboard-shape-more.js")
    assert source.count('wbPushUndo({ action: "move"') == 1  # one place saves, so a move, an addition and a removal are each one step
