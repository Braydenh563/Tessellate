"""F2, draw.io's layout menu: "Space parallel connectors" (`mxParallelEdgeLayout`) and "Flip the layout" (a layout's `direction`).

`whiteboard-arrange-more.js` is run in node against a small stand-in for the board, so the bends it writes and the
places it moves shapes to are read back as numbers."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tests._app_js import frontend_text

ROOT = Path(__file__).resolve().parents[1]

#: A board of three shapes in a row (centres at x 50, 250, 450, y 50) and the stand-ins the file reads at run time.
STAND_INS = r"""
const SIDES = { top: { start: { x: 0.3, y: 0 }, end: { x: 0.7, y: 0 } }, right: { start: { x: 1, y: 0.3 }, end: { x: 1, y: 0.7 } },
  bottom: { start: { x: 0.7, y: 1 }, end: { x: 0.3, y: 1 } }, left: { start: { x: 0, y: 0.7 }, end: { x: 0, y: 0.3 } } };
const wbFmtState = { drawMore: { SIDES } };
const saved = [], moved = [], said = [];
let picked = new Set();
const boxes = { "node:1": { minX: 0, minY: 0, maxX: 100, maxY: 100 }, "node:2": { minX: 200, minY: 0, maxX: 300, maxY: 100 }, "node:3": { minX: 400, minY: 0, maxX: 500, maxY: 100 } };
const items = { "node:1": { id: 1 }, "node:2": { id: 2 }, "node:3": { id: 3 } };
const wbState = { sketches: [] };
const wbIsLinkSketch = (s) => /"type"\s*:\s*"link-/.test(s.data || "");
const wbIsLocked = () => false, wbItemHidden = () => false;
const wbSketchData = (s) => JSON.parse(s.data);
const wbFindItem = (kind, id) => items[`${kind}:${id}`];
const wbItemBBox = (kind, item) => boxes[`${kind}:${item.id}`];
const wbBoxCenter = (b) => ({ x: (b.minX + b.maxX) / 2, y: (b.minY + b.maxY) / 2 });
const wbSelectedKeys = () => picked;
const wbRecordGesture = async (run) => run();
const wbSaveSketchProps = async (sketch, patch) => { saved.push({ id: sketch.id, patch }); };
const wbSelectionEntries = () => [...picked].filter((k) => boxes[k]).map((k) => { const [kind, id] = k.split(":"); return { kind, id: Number(id), item: items[k], bbox: boxes[k] }; });
const wbMoveItemBy = (kind, id, item, dx, dy, rows) => { moved.push({ key: `${kind}:${id}`, dx, dy }); rows.push({ kind, item }); };
const wbSaveMany = async () => true;
const wbScheduleRender = () => {}, wbAnnounce = (s) => said.push(s), toast = (s) => said.push(s);
const nounCount = (n, one) => `${n} ${one}${n === 1 ? "" : "s"}`;
const link = (id, data) => ({ id, data: JSON.stringify({ type: "link-curved", sourceKind: "node", targetKind: "node", ...data }) });
"""


def _run(body: str):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    script = STAND_INS + frontend_text("whiteboard-arrange-more.js") + "\n(async () => {" + body + "})();"
    return json.loads(subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=30, check=True).stdout)


def test_the_offsets_fan_about_the_middle_line():
    got = _run("const m = wbFmtState.arrangeMore; console.log(JSON.stringify([m.offsets(1), m.offsets(2), m.offsets(3), m.offsets(4)]));")
    assert got == [[0], [-14, 14], [-28, 0, 28], [-42, -14, 14, 42]]


def test_two_connectors_between_the_same_shapes_bow_to_opposite_sides_whichever_way_they_point():
    got = _run(
        "wbState.sketches = [link(10, { sourceId: 1, targetId: 2 }), link(11, { sourceId: 2, targetId: 1 }), link(12, { sourceId: 1, targetId: 3 })];"
        "await wbFmtState.arrangeMore.spread(); console.log(JSON.stringify(saved));"
    )
    #: Shapes 1 and 2 lie along x, so the normal is vertical; the bend is twice the offset (a curve peaks at half its bend).
    assert got == [{"id": 10, "patch": {"bend": {"x": 0, "y": -28}}}, {"id": 11, "patch": {"bend": {"x": 0, "y": 28}}}]


def test_three_between_a_pair_keep_the_middle_one_unbent_and_a_pair_alone_is_left_be():
    got = _run(
        "wbState.sketches = [link(1, { sourceId: 1, targetId: 3 }), link(2, { sourceId: 3, targetId: 1 }), link(3, { sourceId: 1, targetId: 3 }), link(4, { sourceId: 1, targetId: 2 })];"
        "await wbFmtState.arrangeMore.spread(); console.log(JSON.stringify(saved));"
    )
    assert [(s["id"], s["patch"].get("bend")) for s in got] == [(1, {"x": 0, "y": -56}), (2, None), (3, {"x": 0, "y": 56})]


def test_a_connector_with_bends_of_its_own_or_a_route_drawn_from_its_ends_is_not_touched():
    got = _run(
        "wbState.sketches = [link(1, { sourceId: 1, targetId: 2, points: [{ x: 150, y: 10 }] }), link(2, { sourceId: 1, targetId: 2, route: 'elbow' }),"
        " link(3, { sourceId: 1, targetId: 2 }), link(4, { sourceId: 1, targetId: 1, loop: 'top' }), link(5, { sourceId: 1, sourceKind: 'node', targetId: null })];"
        "const m = wbFmtState.arrangeMore; await m.spread(); console.log(JSON.stringify([saved, m.canSpread(), said]));"
    )
    saved, can, said = got
    assert saved == [] and can is False
    assert "bends of their own" in said[0]


def test_only_the_picked_pairs_are_spread_and_it_is_one_undo_step():
    source = frontend_text("whiteboard-arrange-more.js")
    assert source.count("wbRecordGesture(") == 2  # the spread and the flip, one gesture each
    got = _run(
        "wbState.sketches = [link(1, { sourceId: 1, targetId: 2 }), link(2, { sourceId: 1, targetId: 2 }), link(3, { sourceId: 2, targetId: 3 }), link(4, { sourceId: 2, targetId: 3 })];"
        "picked = new Set(['node:2', 'node:3']); await wbFmtState.arrangeMore.spread(); console.log(JSON.stringify(saved.map((s) => s.id)));"
    )
    assert got == [3, 4]
    got = _run(
        "wbState.sketches = [link(1, { sourceId: 1, targetId: 2 }), link(2, { sourceId: 1, targetId: 2 }), link(3, { sourceId: 2, targetId: 3 }), link(4, { sourceId: 2, targetId: 3 })];"
        "picked = new Set(['sketch:1']); await wbFmtState.arrangeMore.spread(); console.log(JSON.stringify(saved.map((s) => s.id)));"
    )
    assert got == [1, 2]


def test_flipping_the_layout_left_to_right_swaps_the_shapes_about_the_middle_of_the_group():
    got = _run(
        "picked = new Set(['node:1', 'node:2', 'node:3']); await wbFmtState.arrangeMore.flipLayout('h'); console.log(JSON.stringify(moved));"
    )
    #: The group spans x 0 to 500, so a shape's centre c goes to 500 - c: 1 from 50 to 450, 3 from 450 to 50, 2 stays.
    assert got == [{"key": "node:1", "dx": 400, "dy": 0}, {"key": "node:3", "dx": -400, "dy": 0}]


def test_flipping_top_to_bottom_moves_along_y_only():
    got = _run(
        "boxes['node:2'] = { minX: 200, minY: 300, maxX: 300, maxY: 400 };"
        "picked = new Set(['node:1', 'node:2']); await wbFmtState.arrangeMore.flipLayout('v'); console.log(JSON.stringify(moved));"
    )
    assert got == [{"key": "node:1", "dx": 0, "dy": 300}, {"key": "node:2", "dx": 0, "dy": -300}]


def test_one_shape_is_not_a_layout():
    got = _run("picked = new Set(['node:1']); const n = await wbFmtState.arrangeMore.flipLayout('h'); console.log(JSON.stringify([n, moved.length, said]));")
    assert got[0] == 0 and got[1] == 0 and "two or more" in got[2][0]


def test_a_flip_mirrors_the_bends_the_anchors_and_the_loop_of_the_connectors_that_went_with_the_shapes():
    got = _run(
        "const m = wbFmtState.arrangeMore, both = new Set(['node:1', 'node:2']);"
        "const data = { sourceKind: 'node', targetKind: 'node', sourceId: 1, targetId: 2, sourceAnchor: { x: 1, y: 0.5 }, targetAnchor: { x: 0, y: 0.5, dx: 4 },"
        " points: [{ x: 120, y: 30 }, { x: 180, y: 70 }], bend: { x: 10, y: -6 } };"
        "const whole = m.mirrored(data, 'h', 500, both, false), half = m.mirrored(data, 'h', 500, new Set(['node:1']), false);"
        "const loop = m.mirrored({ sourceKind: 'node', targetKind: 'node', sourceId: 1, targetId: 1, loop: 'left' }, 'h', 500, new Set(['node:1']), false);"
        "const free = m.mirrored({ sourceKind: 'node', sourceId: 1, targetPoint: { x: 40, y: 10 }, targetId: null }, 'v', 100, new Set(['node:1']), false);"
        "console.log(JSON.stringify({ whole, half, loop, free }));"
    )
    #: Both ends went: anchors turn to the other side, the bends and the bow are mirrored about x = 250.
    assert got["whole"]["sourceAnchor"] == {"x": 0, "y": 0.5} and got["whole"]["targetAnchor"] == {"x": 1, "y": 0.5, "dx": -4}
    assert got["whole"]["points"] == [{"x": 380, "y": 30}, {"x": 320, "y": 70}] and got["whole"]["bend"] == {"x": -10, "y": -6}
    #: One end went: its anchor flips, the line's own path (bends, bow) is left as the person had it.
    assert list(got["half"]) == ["sourceAnchor"]
    assert got["loop"]["loop"] == "right" and got["loop"]["sourceAnchor"] == {"x": 1, "y": 0.3}
    #: A connector whose only attached end went is mirrored whole, its free end too (it is part of the layout).
    assert got["free"] == {"targetPoint": {"x": 40, "y": 90}}


def test_the_commands_are_in_the_table_the_menus_and_the_lazy_board_bundle():
    cmds = frontend_text("whiteboard-commands.js")
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    for cmd, needs in (("flip-layout-h", "two"), ("flip-layout-v", "two"), ("parallel-edges", "parallel")):
        row = cmds.split(f'id: "{cmd}"')[1].split("\n")[0]
        assert f'needs: "{needs}"' in row and 'surface: "board"' in row
        assert html.count(f'data-wb-cmd="{cmd}"') == 1
    assert "parallel: () => Boolean(wbFmtState.arrangeMore?.canSpread())" in cmds
    assert "/js/whiteboard-arrange-more.js" in frontend_text("lazy-entries.js")
    assert '"parallel-edges"' in frontend_text("whiteboard.js")  # also in the context menu's Arrange list
