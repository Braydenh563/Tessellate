"""F2, draw.io's two line shapes the board did not have: Entity relation (`route: "er"`) and Isometric (`route: "iso"`).

The stops come from `whiteboard-draw-more.js`, run in node; the board's own `wbLinkPathD` is cut out of whiteboard.js, so
the path the board paints is the one checked."""

from __future__ import annotations

import json
import math
import shutil
import subprocess
from pathlib import Path

import pytest

from tests import _js_scope
from tests._app_js import frontend_text, script_file_text

ROOT = Path(__file__).resolve().parents[1]
WB = frontend_text("whiteboard.js")


def _function(name: str) -> str:
    start = WB.index(f"function {name}(")
    return WB[start : WB.index("\n}\n", start) + 3]


def _stops(route: str, s: dict, t: dict) -> list[dict]:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    script = (
        "const wbFmtState = {};\nconst onSurface = () => {};\n" + frontend_text("whiteboard-draw-more.js")
        + f"\nconsole.log(JSON.stringify(wbFmtState.drawMore.routeStops({json.dumps(route)}, {json.dumps(s)}, {json.dumps(t)})));"
    )
    return json.loads(subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=30, check=True).stdout)


RIGHT, LEFT = {"x": 1, "y": 0}, {"x": -1, "y": 0}


def _right_angles(stops):
    return all(a["x"] == b["x"] or a["y"] == b["y"] for a, b in zip(stops, stops[1:]))


def test_entity_relation_meets_halfway_between_facing_ends():
    got = _stops("er", {"x": 0, "y": 0, "dir": RIGHT}, {"x": 200, "y": 100, "dir": LEFT})
    assert got == [{"x": 0, "y": 0}, {"x": 100, "y": 0}, {"x": 100, "y": 100}, {"x": 200, "y": 100}]


def test_entity_relation_steps_round_when_there_is_no_room():
    #: 40 apart: the two 30 stubs would cross, so it goes out, across the middle row and in.
    got = _stops("er", {"x": 0, "y": 0, "dir": RIGHT}, {"x": 40, "y": 100, "dir": LEFT})
    assert got == [
        {"x": 0, "y": 0}, {"x": 30, "y": 0}, {"x": 30, "y": 50}, {"x": 10, "y": 50}, {"x": 10, "y": 100}, {"x": 40, "y": 100},
    ]
    assert _right_angles(got)


def test_entity_relation_with_both_ends_on_one_side_goes_out_past_both_stubs():
    got = _stops("er", {"x": 0, "y": 0, "dir": RIGHT}, {"x": 100, "y": 80, "dir": RIGHT})
    assert got == [{"x": 0, "y": 0}, {"x": 130, "y": 0}, {"x": 130, "y": 80}, {"x": 100, "y": 80}]


def test_entity_relation_with_free_ends_leaves_toward_the_other_end():
    got = _stops("er", {"x": 300, "y": 0}, {"x": 0, "y": 60})
    assert got[1]["x"] < 300 and got[0] == {"x": 300, "y": 0} and got[-1] == {"x": 0, "y": 60}
    assert _right_angles(got)


def test_entity_relation_on_one_row_is_a_single_run_without_empty_segments():
    got = _stops("er", {"x": 0, "y": 50, "dir": RIGHT}, {"x": 200, "y": 50, "dir": LEFT})
    assert got == [{"x": 0, "y": 50}, {"x": 200, "y": 50}]


def test_isometric_runs_along_the_thirty_degree_axes_and_never_doubles_back():
    for target in ({"x": 300, "y": 80}, {"x": 300, "y": -120}, {"x": -250, "y": 40}, {"x": 90, "y": 400}, {"x": -60, "y": -300}):
        got = _stops("iso", {"x": 0, "y": 0}, target)
        assert got[0] == {"x": 0, "y": 0} and got[-1] == target
        for a, b in zip(got, got[1:]):
            #: Every run is at 30 degrees, or (past the cone, for the last run) straight up or down.
            vertical = math.isclose(a["x"], b["x"], abs_tol=1e-6)
            assert vertical or math.isclose(abs((b["y"] - a["y"]) / (b["x"] - a["x"])), math.tan(math.pi / 6), rel_tol=1e-6), (target, got)
        xs = [p["x"] for p in got]
        assert xs == sorted(xs) or xs == sorted(xs, reverse=True), ("doubles back", got)


def test_isometric_on_an_axis_is_one_run():
    got = _stops("iso", {"x": 0, "y": 0}, {"x": 173.20508075688772, "y": 100})
    assert len(got) == 2


def test_the_board_draws_and_names_the_new_shapes():
    path = _function("wbLinkPathD")
    assert 'shape?.route === "er" || shape?.route === "iso"' in path and "wbFmtState.drawMore.routeStops(" in path
    shape = _function("wbLinkShape")
    assert 'parsed?.route === "er" || parsed?.route === "iso"' in shape and "points: []" in shape
    assert '["elbow", "er", "iso"].includes(parsed?.route)' in _function("wbLinkRouteName")
    #: No bend grips, no add-a-bend spots and no bend by double-click: the shape ignores them, so none are offered.
    assert '["er", "iso", "loop"].includes(wbLinkShape(parsed)?.route)' in _function("wbRenderWaypointHandles")
    assert '["er", "iso", "loop"].includes(shape?.route)' in _function("wbWaypointAddSpots")
    assert "drawn from its two ends" in WB


def test_the_selects_the_setter_and_the_drawio_round_trip_agree():
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    for select in ("wb-prop-route", "wb-fmt-route"):
        block = html[html.index(f'id="{select}"') :]
        block = block[: block.index("</select>")]
        assert 'value="er">Entity relation' in block and 'value="iso">Isometric' in block
    fmt = script_file_text("whiteboard-format.js")
    assert '["elbow", "er", "iso"].includes(value) ? value : undefined' in fmt
    xchg = script_file_text("whiteboard-interchange.js")
    assert 'data.route = "er"' in xchg and 'data.route = "iso"' in xchg
    assert "edgeStyle=entityRelationEdgeStyle;" in xchg and "edgeStyle=isometricEdgeStyle;" in xchg
    src = script_file_text("whiteboard-draw-more.js")
    assert _js_scope.is_wrapped(src) and _js_scope.global_names(src) == set()
    assert "/js/whiteboard-draw-more.js" in script_file_text("lazy-entries.js")
