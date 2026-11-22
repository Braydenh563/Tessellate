"""An elbow connector turns at right angles and goes round its shapes (Phase B, W4).

The features audit: the board had straight and curved connectors only, one
bend each; draw.io's orthogonal edge, the one every flowchart uses, was
missing, and so were its waypoints, its sliding label and its ER line ends.
`wbElbowRoute` is the pure part: the two ends with the direction they leave
their shapes, the two boxes, and any waypoints, to a polyline. Run in node
against the source; the browser half is `scratchpad/ui-sweeps/wb1005-elbow.js`.
"""

from tests._app_js import frontend_text
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = frontend_text("whiteboard.js")
INDEX = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
ROUTE_FUNCTIONS = ("wbElbowSide", "wbElbowCrosses", "wbElbowLeg", "wbElbowDetour", "wbElbowRoute", "wbElbowFloat", "wbElbowEnds", "wbPolylineAt")


def _function(name: str) -> str:
    start = SOURCE.index(f"function {name}(")
    return SOURCE[start : SOURCE.index("\n}\n", start) + 3]


def _node(expr: str):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    pad = SOURCE[SOURCE.index("const WB_ELBOW_PAD") :].split("\n", 1)[0]
    script = pad + "\n" + "".join(_function(n) for n in ROUTE_FUNCTIONS) + f"\nconsole.log(JSON.stringify({expr}));\n"
    out = subprocess.run([node, "-e", script], capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip())


def _route(s, t, s_box, t_box, points=()):
    return _node(f"wbElbowRoute({json.dumps(s)}, {json.dumps(t)}, {json.dumps(s_box)}, {json.dumps(t_box)}, {json.dumps(list(points))})")


def _box(x, y, w=100, h=60):
    return {"minX": x, "minY": y, "maxX": x + w, "maxY": y + h}


def _crosses(a, b, box) -> bool:
    """Whether the axis-aligned segment a-b passes through the box's inside."""
    lo_x, hi_x = sorted((a["x"], b["x"]))
    lo_y, hi_y = sorted((a["y"], b["y"]))
    return lo_x < box["maxX"] - 1 and hi_x > box["minX"] + 1 and lo_y < box["maxY"] - 1 and hi_y > box["minY"] + 1


def _check(pts, s_box, t_box, s, t):
    assert pts[0] == {"x": s["x"], "y": s["y"]} and pts[-1] == {"x": t["x"], "y": t["y"]}
    for a, b in zip(pts, pts[1:]):
        assert abs(a["x"] - b["x"]) < 0.5 or abs(a["y"] - b["y"]) < 0.5, f"a slanted segment {a} {b}"
        assert not _crosses(a, b, s_box), f"through the source: {a} {b}"
        assert not _crosses(a, b, t_box), f"through the target: {a} {b}"


def test_side_to_side_forward_is_three_segments_round_nothing() -> None:
    a, b = _box(0, 0), _box(300, 120)
    s = {"x": 100, "y": 30, "dir": {"x": 1, "y": 0}}
    t = {"x": 300, "y": 150, "dir": {"x": -1, "y": 0}}
    pts = _route(s, t, a, b)
    _check(pts, a, b, s, t)
    assert len(pts) <= 6


def test_backwards_goes_round_both_boxes() -> None:
    a, b = _box(0, 0), _box(-400, 20)
    s = {"x": 100, "y": 30, "dir": {"x": 1, "y": 0}}
    t = {"x": -400, "y": 50, "dir": {"x": -1, "y": 0}}
    _check(_route(s, t, a, b), a, b, s, t)


def test_top_to_bottom_and_back() -> None:
    a, b = _box(0, 0), _box(150, 200)
    s = {"x": 50, "y": 60, "dir": {"x": 0, "y": 1}}
    t = {"x": 200, "y": 200, "dir": {"x": 0, "y": -1}}
    _check(_route(s, t, a, b), a, b, s, t)
    s2 = {"x": 50, "y": 0, "dir": {"x": 0, "y": -1}}
    t2 = {"x": 200, "y": 260, "dir": {"x": 0, "y": 1}}
    _check(_route(s2, t2, a, b), a, b, s2, t2)


def test_side_to_top_is_one_corner() -> None:
    a, b = _box(0, 0), _box(300, 200)
    s = {"x": 100, "y": 30, "dir": {"x": 1, "y": 0}}
    t = {"x": 350, "y": 200, "dir": {"x": 0, "y": -1}}
    pts = _route(s, t, a, b)
    _check(pts, a, b, s, t)
    assert len(pts) == 3


def test_a_top_beside_the_source_is_entered_from_above() -> None:
    """The case the first draft drew through the target: the target's top is
    level with the source's side, so carrying on along the side runs inside
    the target box before it turns."""
    a, b = _box(0, 0), _box(300, 0)
    s = {"x": 100, "y": 30, "dir": {"x": 1, "y": 0}}
    t = {"x": 350, "y": 0, "dir": {"x": 0, "y": -1}}
    _check(_route(s, t, a, b), a, b, s, t)
    below = _box(0, 200)
    t2 = {"x": 50, "y": 200, "dir": {"x": 0, "y": -1}}
    _check(_route(s, t2, a, below), a, below, s, t2)


def test_waypoints_are_on_the_route() -> None:
    a, b = _box(0, 0), _box(400, 0)
    s = {"x": 100, "y": 30, "dir": {"x": 1, "y": 0}}
    t = {"x": 400, "y": 30, "dir": {"x": -1, "y": 0}}
    pts = _route(s, t, a, b, [{"x": 250, "y": 200}])
    _check(pts, a, b, s, t)
    assert {"x": 250, "y": 200} in pts


def test_a_floating_end_starts_in_the_middle_of_the_facing_side() -> None:
    ends = _node(
        'wbElbowEnds({x: 100, y: 10, floating: true, box: {minX: 0, minY: 0, maxX: 100, maxY: 60}},'
        ' {x: 300, y: 170, floating: true, box: {minX: 300, minY: 120, maxX: 400, maxY: 180}}, [])'
    )
    assert ends["source"]["x"] == 100 and ends["source"]["y"] == 30 and ends["source"]["dir"] == {"x": 1, "y": 0}
    assert ends["target"]["x"] == 300 and ends["target"]["y"] == 150 and ends["target"]["dir"] == {"x": -1, "y": 0}


def test_a_new_bend_takes_its_place_along_the_line() -> None:
    line = [{"x": 0, "y": 0}, {"x": 100, "y": 0}, {"x": 100, "y": 100}]
    assert _node(f"wbPolylineAt({json.dumps(line)}, {{x: 50, y: 5}})") == 50
    assert _node(f"wbPolylineAt({json.dumps(line)}, {{x: 95, y: 60}})") == 160


def test_an_elbow_is_a_straight_link_with_a_route() -> None:
    """Every reader that only knows the two old types still draws it."""
    assert 'route: ["elbow", "er", "iso"].includes(value) ? value : undefined' in (ROOT / "frontend" / "js" / "whiteboard-format.js").read_text(encoding="utf-8")
    assert 'type: value === "curved" ? "link-curved" : "link-straight"' in (ROOT / "frontend" / "js" / "whiteboard-format.js").read_text(encoding="utf-8")
    #: Every place a link's path is drawn passes its shape.
    calls = re.findall(r"wbLinkPathD\(parsed\.type, [^;]*\);", SOURCE)
    assert calls and all("wbLinkShape(parsed)" in c or "{ route: \"elbow\", points }" in c or "bendLive" in c for c in calls), calls
    for value in ("curved", "straight", "elbow"):
        assert f'<option value="{value}">' in INDEX[INDEX.index('id="wb-prop-route"') :]


def test_the_er_line_ends_are_offered_on_both_ends() -> None:
    kinds = re.search(r"const WB_CAP_KINDS = \[([^\]]*)\]", SOURCE).group(1)
    for kind in ("er-one", "er-one-only", "er-zero-one", "er-many", "er-one-many", "er-zero-many"):
        assert f'"{kind}"' in kinds
        for which in ("startcap", "endcap"):
            select = INDEX[INDEX.index(f'id="wb-prop-{which}"') :]
            select = select[: select.index("</select>")]
            assert f'value="{kind}"' in select, (which, kind)


def test_an_er_end_is_drawn_and_differs_from_its_neighbours() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    start = SOURCE.index("const WB_CAP_KINDS")
    head = SOURCE[start : SOURCE.index("function wbCapPath(", start)]
    script = (
        _function("wbArrowHeadPath") + head + _function("wbFilledTriangle") + _function("wbCapPathMore") + _function("wbCapPath")
        + "console.log(JSON.stringify(WB_CAP_KINDS.map((k) => wbCapPath(k, 100, 0, 0, 18))));"
    )
    out = subprocess.run([node, "-e", script], capture_output=True, text=True, check=True)
    paths = json.loads(out.stdout.strip())
    assert paths[0] == ""
    assert all(p.startswith("M ") for p in paths[1:])
    assert len(set(paths)) == len(paths), "two ends draw the same mark"


def test_the_label_slides_and_defaults_to_the_middle() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    script = _function("wbLinkLabelT") + "console.log(JSON.stringify([wbLinkLabelT({}), wbLinkLabelT({label_t: 0.2}), wbLinkLabelT({label_t: 7})]));"
    out = subprocess.run([node, "-e", script], capture_output=True, text=True, check=True)
    assert json.loads(out.stdout.strip()) == [0.5, 0.2, 0.5]
    assert "getPointAtLength(length * t)" in SOURCE


def test_placed_bends_keep_their_place(ai_client):
    """A saved elbow's bends are kept from the box's corner and placed with it."""
    board = ai_client.post("/whiteboard/boards", json={"name": "Elbows", "type": "board"}).json()
    rect = "M 0 0 L 100 0 L 100 60 L 0 60 Z"
    payload = {
        "box": {"w": 400, "h": 200},
        "items": [
            {"key": "a", "kind": "sketch", "data": {"d": rect, "shape": "rect"}, "z": 1},
            {"key": "b", "kind": "sketch", "data": {"d": "M 300 140 L 400 140 L 400 200 L 300 200 Z", "shape": "rect"}, "z": 1},
        ],
        "links": [{"from": "a", "to": "b", "data": {"type": "link-straight", "route": "elbow", "points": [{"x": 200, "y": 100}]}}],
    }
    item = ai_client.post("/board-library", json={"kind": "element", "name": "Elbow", "payload": payload}).json()
    out = ai_client.post(f"/whiteboard/boards/{board['id']}/place", json={"item_id": item["id"], "x": 1200, "y": 100})
    assert out.status_code == 201, out.text
    link = next(json.loads(s["data"]) for s in out.json()["sketches"] if json.loads(s["data"]).get("route") == "elbow")
    assert link["points"] == [{"x": 1200.0, "y": 100.0}]
