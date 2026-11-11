"""F2, draw.io's ports and points: a table's row ports (`portConstraint=eastwest`) and, below, a shape's own points.

`whiteboard-shape-more.js` is run in node against a small stand-in for the board, so what it writes is read back as numbers."""

from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from tests._app_js import frontend_text

STAND_INS = r"""
const wbFmtState = {};
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
