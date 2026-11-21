"""Connection points on shapes (wb-phase2 step 5; draw.io's fixed ports).

Every item had the same eight anchors, its box's corners and side middles,
so a diamond's and an ellipse's corner anchors floated off the shape. A drawn
polygon now has its own corners and side middles, a curved outline its eight
compass points, each as a fraction of the box (how a link stores it); a link
anchored before keeps its end (read from the fraction, not looked up); and
with Select, pointing at an item shows its points and dragging from one draws
a connector. The browser half is `scratchpad/ui-sweeps/wbports.js`.
"""

from tests._app_js import frontend_text
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = frontend_text("whiteboard.js")


def _function(name: str) -> str:
    start = SOURCE.index(f"function {name}(")
    return SOURCE[start : SOURCE.index("\n}\n", start) + 3]


def _ports(d, shaped=False):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    script = "".join(_function(n) for n in ("wbPathBBox", "wbPathPolyline", "wbPortsForPath")) + (
        f"console.log(JSON.stringify(wbPortsForPath({json.dumps(d)}, {json.dumps(shaped)})));"
    )
    out = subprocess.run([node, "-e", script], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def _set(points):
    return {(round(p["x"], 3), round(p["y"], 3)) for p in points}


def test_a_rectangle_keeps_the_eight() -> None:
    assert _set(_ports("M 0 0 h 100 v 60 h -100 Z", True)) == {
        (0, 0), (0.5, 0), (1, 0), (1, 0.5), (1, 1), (0.5, 1), (0, 1), (0, 0.5),
    }


def test_a_diamond_has_its_tips_and_side_middles() -> None:
    got = _set(_ports("M 50 0 L 100 30 L 50 60 L 0 30 Z", True))
    assert got == {(0.5, 0), (1, 0.5), (0.5, 1), (0, 0.5), (0.75, 0.25), (0.75, 0.75), (0.25, 0.75), (0.25, 0.25)}
    assert (0, 0) not in got  # a box corner is off the shape


def test_a_triangle_has_three_corners_and_three_middles() -> None:
    got = _set(_ports("M 50 0 L 100 80 L 0 80 Z", True))
    assert got == {(0.5, 0), (1, 1), (0, 1), (0.75, 0.5), (0.5, 1), (0.25, 0.5)}


def test_an_ellipse_has_its_compass_points_on_the_curve() -> None:
    got = _ports("M 0 30 a 50 30 0 1 0 100 0 a 50 30 0 1 0 -100 0", True)
    assert len(got) == 8
    for p in got:
        # On the unit ellipse of its box.
        assert abs(((p["x"] - 0.5) / 0.5) ** 2 + ((p["y"] - 0.5) / 0.5) ** 2 - 1) < 1e-3


def test_an_open_stroke_has_none_of_its_own() -> None:
    assert _ports("M 0 0 L 100 40") is None


def test_a_stored_anchor_is_read_from_its_fraction() -> None:
    body = _function("wbAnchorPoint")
    assert "anchor.x * (box.maxX - box.minX)" in body and ".find(" not in body
    assert "wbPortFractions(kind, item).map(" in _function("wbAnchorPositions")


def test_select_shows_the_points_and_a_drag_from_one_connects() -> None:
    assert 'if (window.currentTool === "select" && !e.buttons) {\n      portHover(e);' in SOURCE
    block = SOURCE[SOURCE.index("// --- Connection points with Select") :]
    block = block[: block.index("\n  });\n", block.index('containerEl.addEventListener("pointerup"')) + 6]
    for needle in ('route: "elbow"', 'endCap: "arrow"', "sourceAnchor: drag.anchor", "targetPoint", "wbPushUndo({ action: \"create\"", "e.preventDefault();", "wbSelectedKeys().has("):
        assert needle in block, needle
