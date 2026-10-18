"""Bends on every connector style, and line jumps (wb-phase2 step 1).

Only an elbow took waypoints; a straight or curved connector had one `bend`
(a quadratic through one point). draw.io bends every edge style, and where
two edges cross the upper one hops over the other ("line jumps"). The pure
parts run in node against the source; the browser half is
`scratchpad/ui-sweeps/wbwaypoints.js`.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")
FORMAT = (ROOT / "frontend" / "js" / "whiteboard-format.js").read_text(encoding="utf-8")
INDEX = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
FUNCTIONS = (
    "wbArrowHeadPath", "wbHollowInset", "wbShaftEnd", "wbCapPath", "wbElbowSide", "wbElbowCrosses", "wbElbowLeg", "wbElbowDetour",
    "wbElbowRoute", "wbElbowFloat", "wbElbowEnds", "wbElbowPathD", "wbPolylineAt", "wbLinkPathD",
    "wbLinkShape", "wbCurveThroughSegs", "wbCubicAt", "wbCurvePathD", "wbWaypointInsert",
    "wbLinkWaypoints", "wbLinkGap", "wbLinkDrawnLine", "wbSegmentCross", "wbLineJumpsD", "wbShaftPoints",
)


def _function(name: str) -> str:
    start = SOURCE.index(f"function {name}(")
    return SOURCE[start : SOURCE.index("\n}\n", start) + 3]


def _const(name: str) -> str:
    start = SOURCE.index(f"const {name} =")
    end = SOURCE.index(";\n", start) + 2
    return SOURCE[start:end]


def _cap_scale() -> str:
    start = SOURCE.index("const WB_CAP_SIZE_SCALE")
    return SOURCE[start : SOURCE.index("function wbCapSizeFields(", start)]


def _node(expr: str):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    head = "".join(_const(n) for n in ("WB_ELBOW_PAD", "WB_CAP_KINDS", "WB_ER_CAPS", "WB_JUMP_STYLES", "WB_HOLLOW_INSET"))
    script = head + _cap_scale() + "".join(_function(n) for n in FUNCTIONS) + f"\nconsole.log(JSON.stringify({expr}));\n"
    out = subprocess.run([node, "-e", script], capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip())


S = {"x": 0, "y": 0, "dir": {"x": 1, "y": 0}}
T = {"x": 300, "y": 0, "dir": {"x": -1, "y": 0}}


def _path(type_, points, s=S, t=T, caps=None):
    data = {"type": type_, "points": points}
    return _node(f"wbLinkPathD({json.dumps(type_)}, {json.dumps(s)}, {json.dumps(t)}, {json.dumps(caps)}, 3, null, wbLinkShape({json.dumps(data)}))")


def test_a_straight_link_runs_through_its_waypoints_in_turn() -> None:
    d = _path("link-straight", [{"x": 100, "y": 80}, {"x": 200, "y": -40}])
    assert d == "M 0 0 L 100 80 L 200 -40 L 300 0"


def test_a_curved_link_is_one_smooth_curve_through_every_waypoint() -> None:
    d = _path("link-curved", [{"x": 150, "y": 100}])
    assert d.count(" C ") == 2 and d.startswith("M 0 0 C")
    # The curve passes through the waypoint: the first segment ends there.
    assert re.search(r"C [^C]*, 150 100 C", d), d
    # It leaves along the source's edge normal (the first control point is
    # straight out to the right of the source).
    first_ctrl = re.search(r"C (-?[\d.]+) (-?[\d.]+),", d)
    assert float(first_ctrl.group(2)) == 0 and float(first_ctrl.group(1)) > 0
    # Smooth at the waypoint: the two control points either side are in line.
    segs = _node(f"wbCurveThroughSegs({json.dumps([S, {'x': 150, 'y': 100}, T])}, {json.dumps(S['dir'])}, {json.dumps(T['dir'])})")
    c2, p, c1 = segs[0]["c2"], segs[1]["a"], segs[1]["c1"]
    cross = (p["x"] - c2["x"]) * (c1["y"] - p["y"]) - (p["y"] - c2["y"]) * (c1["x"] - p["x"])
    assert abs(cross) < 1e-6


def test_caps_follow_the_last_run_of_a_bent_line() -> None:
    d = _path("link-straight", [{"x": 300, "y": 200}], t={"x": 300, "y": 0}, caps={"startCap": "none", "endCap": "arrow"})
    # The last run goes straight up into the target, so the arrow's two
    # barbs sit below the tip, one either side.
    head = d.split(" M ")[1]
    nums = [float(n) for n in re.findall(r"-?[\d.]+", head)]
    assert nums[3] > 0 and nums[-1] > 0, d


def test_a_line_without_waypoints_draws_as_it_always_did() -> None:
    assert _node('wbLinkShape({type: "link-curved"})') is None
    assert _node('wbLinkShape({type: "link-straight", points: []})') is None
    assert _node('wbLinkShape({type: "link-straight", route: "elbow"})') == {"route": "elbow", "points": [], "gap": None}
    assert _path("link-straight", []) == "M 0 0 L 300 0"


def test_an_old_single_bend_reads_as_one_waypoint_on_the_curve() -> None:
    ends = {"source": {"x": 0, "y": 0}, "target": {"x": 200, "y": 0}}
    # A quadratic with control (100, 80) passes through (100, 40).
    got = _node(f"wbLinkWaypoints({{type: 'link-curved', bend: {{x: 0, y: 80}}}}, {json.dumps(ends)})")
    assert got == [{"x": 100, "y": 40}]
    assert _node(f"wbLinkWaypoints({{type: 'link-curved', route: 'elbow', bend: {{x: 0, y: 80}}}}, {json.dumps(ends)})") == []


def test_a_new_waypoint_lands_between_the_ones_it_falls_between() -> None:
    line = [{"x": 0, "y": 0}, {"x": 100, "y": 0}, {"x": 200, "y": 0}, {"x": 300, "y": 0}]
    pts = [{"x": 100, "y": 0}, {"x": 200, "y": 0}]
    got = _node(f"wbWaypointInsert({json.dumps(pts)}, {json.dumps(line)}, {{x: 150, y: 10}})")
    assert got == [{"x": 100, "y": 0}, {"x": 150, "y": 10}, {"x": 200, "y": 0}]
    got = _node(f"wbWaypointInsert({json.dumps(pts)}, {json.dumps(line)}, {{x: 280, y: 5}})")
    assert got[-1] == {"x": 280, "y": 5}


def test_every_route_keeps_its_bends_when_its_shape_changes() -> None:
    """draw.io keeps an edge's waypoints across styles; this dropped them."""
    body = FORMAT[FORMAT.index("async function wbSetLinkRoute(") :]
    body = body[: body.index("\n}\n")]
    assert "points: undefined," not in body
    assert "wbLinkWaypoints(parsed" in body


def test_double_click_adds_a_waypoint_on_every_style() -> None:
    assert "const bend = { x: (px - mid.x) * 2" not in SOURCE
    assert "wbWaypointInsert(live.points, wbLinkDrawnLine(live, endpoints)" in SOURCE
    assert "if (!look) wbRenderWaypointHandles(group, sketch, parsed, endpoints);" in SOURCE


# --- Line jumps -------------------------------------------------------------


def test_a_crossing_gets_an_arc_and_nothing_else_changes() -> None:
    pts = [{"x": 0, "y": 0}, {"x": 200, "y": 0}]
    other = [[{"x": 100, "y": -50}, {"x": 100, "y": 50}]]
    d = _node(f"wbLineJumpsD({json.dumps(pts)}, {json.dumps(other)}, 'arc', 6)")
    assert d == "M 0 0 L 94 0 A 6 6 0 0 1 106 0 L 200 0"
    assert _node(f"wbLineJumpsD({json.dumps(pts)}, [], 'arc', 6)") == "M 0 0 L 200 0"
    assert _node(f"wbLineJumpsD({json.dumps(pts)}, {json.dumps(other)}, 'none', 6)") == "M 0 0 L 200 0"


def test_gap_and_sharp() -> None:
    pts = [{"x": 0, "y": 0}, {"x": 200, "y": 0}]
    other = [[{"x": 100, "y": -50}, {"x": 100, "y": 50}]]
    assert _node(f"wbLineJumpsD({json.dumps(pts)}, {json.dumps(other)}, 'gap', 6)") == "M 0 0 L 94 0 M 106 0 L 200 0"
    assert _node(f"wbLineJumpsD({json.dumps(pts)}, {json.dumps(other)}, 'sharp', 6)") == "M 0 0 L 94 0 L 100 -6 L 106 0 L 200 0"


def test_arcs_rise_the_same_way_whichever_way_the_line_runs() -> None:
    other = [[{"x": 100, "y": -50}, {"x": 100, "y": 50}]]
    right = _node(f"wbLineJumpsD([{{x: 0, y: 0}}, {{x: 200, y: 0}}], {json.dumps(other)}, 'sharp', 6)")
    left = _node(f"wbLineJumpsD([{{x: 200, y: 0}}, {{x: 0, y: 0}}], {json.dumps(other)}, 'sharp', 6)")
    assert "100 -6" in right and "100 -6" in left


def test_close_crossings_merge_and_none_sits_on_a_corner() -> None:
    pts = [{"x": 0, "y": 0}, {"x": 200, "y": 0}]
    other = [[{"x": 100, "y": -50}, {"x": 100, "y": 50}], [{"x": 108, "y": -50}, {"x": 108, "y": 50}], [{"x": 3, "y": -50}, {"x": 3, "y": 50}]]
    d = _node(f"wbLineJumpsD({json.dumps(pts)}, {json.dumps(other)}, 'arc', 6)")
    assert d.count(" A ") == 1 and "L 94 0 A 10 10 0 0 1 114 0" in d


def test_a_curve_under_a_line_is_sampled_to_hop_over() -> None:
    pts = _node("wbShaftPoints('M 0 0 C 50 -100, 150 100, 200 0 M 1 1 L 2 2')")
    assert len(pts) == 13 and pts[-1] == {"x": 200, "y": 0}
    jumped = _node(f"wbLineJumpsD([{{x: 100, y: -80}}, {{x: 100, y: 80}}], [{json.dumps(pts)}], 'arc', 6)")
    assert jumped.count(" A ") == 1


def test_jumps_are_a_format_field_for_connectors_and_the_render_applies_them() -> None:
    assert '"jumps"' in FORMAT[FORMAT.index("const WB_FMT_FIELDS") : FORMAT.index("};", FORMAT.index("const WB_FMT_FIELDS"))]
    row = INDEX[INDEX.index('data-fmt="jumps"') :][:800]
    for value in ("none", "arc", "gap", "sharp"):
        assert f'<option value="{value}">' in row
    assert "wbApplyLineJumps(sketchUpdate.sort(" in SOURCE
    # The label and its grip measure the plain line, never a gap's cut shaft.
    layout = SOURCE[SOURCE.index("function wbLayoutLinkLabel(") :]
    assert '.sketch-hitbox")?.getAttribute("d")' in layout[: layout.index("\n}\n")]
