"""The obstacle-avoiding elbow router (WHITEBOARD_PLAN step 6): grid A* over item boxes.

`wbFmtState.router.find` is pure; run in node against the source with fixed boxes. The browser half
(timing on 200 items, square end legs, drawn shapes) is `scratchpad/ui-sweeps/wbconnectors3.js`.
"""

import json
import shutil
import subprocess

import pytest

from tests._app_js import frontend_text


def _node(body: str):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    script = "const wbFmtState = {};\nconst onSurface = () => {};\n" + frontend_text("whiteboard-draw-more.js") + "\n" + body
    return json.loads(subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=30, check=True).stdout)


def _box(x, y, w=100, h=60):
    return {"minX": x, "minY": y, "maxX": x + w, "maxY": y + h}


def _find(s, t, boxes):
    return _node(f"console.log(JSON.stringify(wbFmtState.router.find({json.dumps(s)}, {json.dumps(t)}, {json.dumps(boxes)})));")


def _crosses(a, b, box) -> bool:
    lo_x, hi_x = sorted((a["x"], b["x"]))
    lo_y, hi_y = sorted((a["y"], b["y"]))
    return lo_x < box["maxX"] - 0.5 and hi_x > box["minX"] + 0.5 and lo_y < box["maxY"] - 0.5 and hi_y > box["minY"] + 0.5


def _ends(src, dst):
    """Right side of `src`, left side of `dst`, each leaving square to its side."""
    s = {"x": src["maxX"], "y": (src["minY"] + src["maxY"]) / 2, "dir": {"x": 1, "y": 0}, "box": src}
    t = {"x": dst["minX"], "y": (dst["minY"] + dst["maxY"]) / 2, "dir": {"x": -1, "y": 0}, "box": dst}
    return s, t


def test_the_route_misses_every_box_and_turns_only_at_right_angles():
    a, b = _box(0, 100), _box(400, 100)
    wall = {"minX": 200, "minY": -200, "maxX": 240, "maxY": 400}
    s, t = _ends(a, b)
    pts = _find(s, t, [a, b, wall])
    assert pts and pts[0]["x"] == s["x"] and pts[-1]["x"] == t["x"]
    for p, q in zip(pts, pts[1:]):
        assert abs(p["x"] - q["x"]) < 0.5 or abs(p["y"] - q["y"]) < 0.5
        for box in (a, b, wall):
            assert not _crosses(p, q, box), (p, q, box)


def test_an_open_field_takes_the_fewest_bends():
    a, b = _box(0, 0), _box(400, 200)
    s, t = _ends(a, b)
    pts = _find(s, t, [a, b])
    assert len(pts) - 2 == 2, pts  # out, one run across, in: two corners (a Z)
    box_a, box_b = _box(0, 0), _box(400, 0)
    straight = _find(*_ends(box_a, box_b), [box_a, box_b])
    assert len(straight) == 2


def test_a_box_in_the_way_costs_a_detour_not_a_crossing():
    a, b, mid = _box(0, 0), _box(400, 0), _box(180, -20, 60, 100)
    s, t = _ends(a, b)
    pts = _find(s, t, [a, b, mid])
    assert pts and all(not _crosses(p, q, mid) for p, q in zip(pts, pts[1:]))
    assert len(pts) >= 4


def test_it_is_deterministic():
    boxes = [_box(0, 0), _box(400, 150), _box(180, 20, 60, 90), _box(250, -80, 40, 60)]
    s, t = _ends(boxes[0], boxes[1])
    assert _find(s, t, boxes) == _find(s, t, boxes)


def test_the_last_leg_is_square_to_the_side_it_enters():
    a, b = _box(0, 0), _box(300, 300)
    s = {"x": 50, "y": 60, "dir": {"x": 0, "y": 1}, "box": a}
    t = {"x": 350, "y": 300, "dir": {"x": 0, "y": -1}, "box": b}
    pts = _find(s, t, [a, b])
    assert abs(pts[-1]["x"] - pts[-2]["x"]) < 0.5 and pts[-1]["y"] > pts[-2]["y"]
    assert abs(pts[0]["x"] - pts[1]["x"]) < 0.5 and pts[1]["y"] > pts[0]["y"]


def test_a_missing_direction_is_taken_from_the_nearest_side():
    got = _node("console.log(JSON.stringify(wbFmtState.router.squareDir({x: 100, y: 30, box: {minX: 0, minY: 0, maxX: 100, maxY: 60}}, {x: 0, y: 0})));")
    assert got == {"x": 1, "y": 0}


def test_no_path_or_too_large_a_grid_answers_null():
    a, b = _box(0, 0), _box(400, 0)
    s, t = _ends(a, b)
    buried = _find(s, t, [a, b, {"minX": 105, "minY": -20, "maxX": 140, "maxY": 80}])
    assert buried is None  # the stub out of the source starts inside another box
    many = [_box(130 + (i % 40) * 3.1, -100 + (i // 40) * 7.3, 2, 2) for i in range(800)]
    assert _find(s, t, [a, b, *many]) is None  # past the cell cap: the caller draws the classic route


def test_wblinkpathd_uses_the_router_and_keeps_the_classic_route_as_fallback():
    src = frontend_text("whiteboard.js")
    body = src[src.index('if (shape?.route === "elbow") {') :][:1100]
    assert "wbFmtState.router?.route" in body and "wbElbowRoute(" in body
