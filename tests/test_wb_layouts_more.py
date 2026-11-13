"""Draw.io's Arrange > Layout for a board (flow, radial tree, organic, circle, org chart) and the stack layout on lanes.

`whiteboard-layouts-more.js` is run in node: the layout functions are pure (boxes and pairs of keys in, top-left
corners out), so overlaps, rank order, crossings and repeatability are read back as numbers from fixed inputs."""

from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from tests._app_js import frontend_text

#: Twelve boxes of four sizes scattered over the board, joined by fourteen connectors (a layered graph with two long edges).
GRAPH = r"""
const wbFmtState = {}, wbBoardState = {};
const sizes = [[120, 60], [160, 80], [100, 50], [140, 70]];
const nodes = [];
for (let i = 0; i < 12; i++) nodes.push({ key: "node:" + (i + 1), x: (i * 37) % 300, y: (i * 91) % 260, w: sizes[i % 4][0], h: sizes[i % 4][1] });
const edges = [[1, 2], [1, 3], [1, 4], [2, 5], [2, 6], [3, 6], [3, 7], [4, 8], [5, 9], [6, 9], [6, 10], [7, 11], [8, 12], [2, 12]].map(([a, b]) => ["node:" + a, "node:" + b]);
const boxesOf = (pos, list = nodes) => list.map((n) => ({ x: pos.get(n.key).x, y: pos.get(n.key).y, w: n.w, h: n.h }));
"""

KINDS = ["flow-h", "flow-v", "radial", "org", "organic", "circle"]


def _run(body: str):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    script = GRAPH + frontend_text("whiteboard-layouts-more.js") + "\nconst L = wbFmtState.layoutMore;\n" + body
    return json.loads(subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=30, check=True).stdout)


@pytest.mark.parametrize("kind", KINDS)
def test_no_two_boxes_overlap(kind):
    got = _run(f'const pos = L.arrange("{kind}", nodes, edges); console.log(JSON.stringify(L.overlapCount(boxesOf(pos))));')
    assert got == 0


@pytest.mark.parametrize("kind", ["flow-h", "flow-v"])
def test_flow_puts_every_connector_forward_by_at_least_the_box(kind):
    axis = "x" if kind == "flow-h" else "y"
    size = "w" if kind == "flow-h" else "h"
    got = _run(
        f'const pos = L.arrange("{kind}", nodes, edges); const by = new Map(nodes.map((n) => [n.key, n]));'
        f"console.log(JSON.stringify(edges.map(([a, b]) => pos.get(b).{axis} - (pos.get(a).{axis} + by.get(a).{size}))));"
    )
    assert all(gap > 0 for gap in got), got


@pytest.mark.parametrize("kind", ["flow-h", "flow-v", "radial", "org", "organic"])
def test_crossings_do_not_go_up(kind):
    got = _run(f'const pos = L.arrange("{kind}", nodes, edges); console.log(JSON.stringify([L.crossingCount(nodes, pos, edges), L.crossingCount(nodes, new Map(), edges)]));')
    after, before = got
    assert before > 0 and after <= before, got


def test_flow_cuts_crossings_on_a_woven_pair_of_chains():
    # Two chains drawn criss-cross: a1-a2-a3 and b1-b2-b3, with the columns swapped half way down the board.
    got = _run(
        'const w = [["a1", 0, 0], ["b1", 100, 0], ["b2", 0, 150], ["a2", 100, 150], ["a3", 0, 300], ["b3", 100, 300]].map(([key, x, y]) => ({ key, x, y, w: 60, h: 40 }));'
        'const e = [["a1", "a2"], ["a2", "a3"], ["b1", "b2"], ["b2", "b3"]];'
        'const pos = L.arrange("flow-v", w, e); console.log(JSON.stringify([L.crossingCount(w, new Map(), e), L.crossingCount(w, pos, e)]));'
    )
    assert got == [2, 0]


def test_circle_keeps_neighbours_together_on_a_path():
    got = _run(
        'const w = Array.from({ length: 8 }, (_, i) => ({ key: "p" + i, x: ((i * 5) % 8) * 90, y: ((i * 3) % 8) * 70, w: 80, h: 40 }));'
        "const e = w.slice(1).map((n, i) => [w[i].key, n.key]);"
        'const pos = L.arrange("circle", w, e); console.log(JSON.stringify([L.crossingCount(w, new Map(), e), L.crossingCount(w, pos, e), L.overlapCount(boxesOf(pos, w))]));'
    )
    assert got[1] <= got[0] and got[2] == 0, got


@pytest.mark.parametrize("kind", KINDS)
def test_the_same_input_gives_the_same_output(kind):
    got = _run(
        f'const one = [...L.arrange("{kind}", nodes, edges)]; const two = [...L.arrange("{kind}", nodes.map((n) => ({{ ...n }})), edges.map((e) => [...e]))];'
        "console.log(JSON.stringify(JSON.stringify(one) === JSON.stringify(two)));"
    )
    assert got is True


@pytest.mark.parametrize("kind", KINDS)
def test_the_group_stays_where_it_was(kind):
    got = _run(
        f'const pos = L.arrange("{kind}", nodes, edges); const b = boxesOf(pos);'
        "const mid = (xs) => (Math.min(...xs) + Math.max(...xs)) / 2;"
        "const was = nodes.map((n) => ({ x: n.x, y: n.y, w: n.w, h: n.h }));"
        "console.log(JSON.stringify([Math.min(...b.map((o) => o.x)) - Math.min(...was.map((o) => o.x)), Math.min(...b.map((o) => o.y)) - Math.min(...was.map((o) => o.y)),"
        " mid(b.flatMap((o) => [o.x, o.x + o.w])) - mid(was.flatMap((o) => [o.x, o.x + o.w])), mid(b.flatMap((o) => [o.y, o.y + o.h])) - mid(was.flatMap((o) => [o.y, o.y + o.h]))]));"
    )
    left, top, cx, cy = got
    if kind in ("flow-h", "flow-v", "org"):
        assert abs(left) <= 1 and abs(top) <= 1, got
    else:
        assert abs(cx) <= 1 and abs(cy) <= 1, got


def test_a_loop_of_connectors_still_lays_out():
    got = _run(
        'const w = ["a", "b", "c"].map((key, i) => ({ key, x: i * 10, y: 0, w: 50, h: 30 })); const e = [["a", "b"], ["b", "c"], ["c", "a"]];'
        'const out = {}; for (const k of ["flow-h", "flow-v", "radial", "org", "organic", "circle"]) { const p = L.arrange(k, w, e); out[k] = L.overlapCount(boxesOf(p, w)); }'
        "console.log(JSON.stringify(out));"
    )
    assert set(got.values()) == {0}, got


def test_an_org_chart_stacks_leaves_under_their_manager():
    got = _run(
        'const w = [["boss", 0, 0], ["l1", 0, 0], ["l2", 5, 5], ["l3", 9, 9], ["vp", 40, 0], ["x1", 0, 0], ["x2", 0, 0]].map(([key, x, y]) => ({ key, x, y, w: 80, h: 40 }));'
        'const e = [["boss", "l1"], ["boss", "l2"], ["boss", "l3"], ["boss", "vp"], ["vp", "x1"], ["vp", "x2"]];'
        "const p = L.arrange(\"org\", w, e); console.log(JSON.stringify(Object.fromEntries([...p].map(([k, v]) => [k, [v.x, v.y]]))));"
    )
    leaves = [got["l1"], got["l2"], got["l3"]]
    assert len({x for x, _ in leaves}) == 1, "the leaves share a column"
    ys = [y for _, y in leaves]
    assert ys == sorted(ys) and all(b - a >= 40 for a, b in zip(ys, ys[1:])), ys
    assert all(y > got["boss"][1] + 40 for y in ys), "under the manager"


def test_the_lane_stack_leaves_equal_gaps_and_grows_the_lane():
    got = _run(
        'const kids = [{ key: "a", minX: 40, minY: 70, maxX: 100, maxY: 110 }, { key: "b", minX: 10, minY: 130, maxX: 160, maxY: 150 }, { key: "c", minX: 60, minY: 20, maxX: 90, maxY: 60 }];'
        "console.log(JSON.stringify(L.stackColumn({ x: 0, y: 0, width: 120, height: 100 }, kids, { gap: 16, pad: 16 })));"
    )
    moves = {m["key"]: m for m in got["moves"]}
    # c (top) then a then b: each 16 in from the lane's left edge and 16 below the one before.
    assert moves["c"]["dy"] + 20 == 16 and moves["c"]["dx"] + 60 == 16
    assert moves["a"]["dy"] + 70 == 16 + 40 + 16 and moves["b"]["dy"] + 130 == 16 + 40 + 16 + 40 + 16
    assert got["width"] == 150 + 32 and got["height"] == 16 + 40 + 16 + 40 + 16 + 20 + 16


def test_the_lane_stack_never_shrinks_a_lane():
    got = _run('console.log(JSON.stringify(L.stackColumn({ x: 0, y: 0, width: 500, height: 900 }, [{ key: "a", minX: 0, minY: 0, maxX: 50, maxY: 50 }])));')
    assert got["width"] == 500 and got["height"] == 900


# --- wiring ---------------------------------------------------------------------------------------------------


def test_the_file_is_in_the_boards_bundle_and_the_commands_reach_it():
    assert "/js/whiteboard-layouts-more.js" in frontend_text("lazy-entries.js")
    cmds = frontend_text("whiteboard-commands.js")
    for kind in KINDS:
        row = next(line for line in cmds.splitlines() if f'id: "layout-{kind}"' in line)
        assert f'apply("{kind}")' in row and 'needs: "layout"' in row
    assert "layout: () => Boolean(wbFmtState.layoutMore?.canLayout())" in cmds


def test_a_change_to_a_lane_and_its_stacking_are_one_undo_step():
    src = frontend_text("whiteboard.js")
    push = src[src.index("function wbPushUndo(entry)") :].split("\n}\n")[0]
    assert "wbBoardState.lane?.settle(entry)" in push and "wbRecordDepth === 0" in push
    gesture = src[src.index("async function wbRecordGesture") :].split("\n}\n")[0]
    assert "wbBoardState.lane?.settleNow()" in gesture
    fmt = frontend_text("whiteboard-format.js")
    assert 'frame: ["pad", "stack", "collapse", "geometry", "props", "tags"]' in fmt and 'on("wb-fmt-stack", "change"' in fmt


def test_the_guide_names_the_layouts() -> None:
    """Standing order 13: the Layout menu's six layouts are in the Guide's diagram tools topic."""
    from tessellate.ai import help_chat

    body = next(t["body"] for t in help_chat.HELP_TOPICS if t["id"] == "board-diagram-tools")
    assert "a flow, a radial tree, an org chart, an organic network or a circle" in body and len(body) < 1900
