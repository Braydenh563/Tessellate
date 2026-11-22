"""Alt resizes a board item from its centre (row 1600, the audit's C3).

`wbResizeBox` is the one frame maths the card and object handles share, and
`wbSketchResizeTransform` reads it back as a scale about the middle for a
drawn shape and for a group. Run in node against the real functions.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess

import pytest

from tests._app_js import frontend_text

WB = frontend_text("whiteboard.js")


def _fn(name: str) -> str:
    match = re.search(rf"^function {name}\(.*?^\}}", WB, re.S | re.M)
    assert match, f"{name} is gone from whiteboard.js"
    return match.group(0)


def _run(expr: str):
    script = "\n".join([
        "const WB_SKETCH_MIN_SIZE = 10;",
        _fn("wbKeepAspect"), _fn("wbResizeBox"), _fn("wbSketchResizeTransform"),
        f"process.stdout.write(JSON.stringify({expr}));",
    ])
    return json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)


pytestmark = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def test_alt_on_the_east_edge_grows_both_sides_and_keeps_the_centre():
    box = _run("wbResizeBox({x: 100, y: 50, w: 200, h: 80}, 'e', 30, 0, false, true, 10)")
    assert box == {"x": 70, "y": 50, "w": 260, "h": 80}
    assert box["x"] + box["w"] / 2 == 200


def test_without_alt_the_opposite_side_stays_put():
    assert _run("wbResizeBox({x: 100, y: 50, w: 200, h: 80}, 'w', 30, 0, false, false, 10)") == {
        "x": 130, "y": 50, "w": 170, "h": 80,
    }


def test_alt_and_shift_on_a_corner_keep_the_proportions_about_the_middle():
    box = _run("wbResizeBox({x: 0, y: 0, w: 200, h: 100}, 'se', 50, 0, true, true, 10)")
    assert box["w"] / box["h"] == 2
    assert (box["x"] + box["w"] / 2, box["y"] + box["h"] / 2) == (100, 50)


def test_a_drawn_shape_scales_about_its_centre_with_alt():
    t = _run("wbSketchResizeTransform({minX: 0, minY: 0, maxX: 100, maxY: 40}, 'n', 0, -10, false, true)")
    assert (t["anchorX"], t["anchorY"]) == (50, 20)
    assert t["sx"] == 1 and t["sy"] == 1.5
    plain = _run("wbSketchResizeTransform({minX: 0, minY: 0, maxX: 100, maxY: 40}, 'n', 0, -10, false, false)")
    assert plain["anchorY"] == 40


def test_every_resize_handle_passes_alt_through():
    assert WB.count("event.sourceEvent.altKey") >= 4
    for name in ("nodeResizeDrag", "resizeDrag"):
        start = WB.index(f"function {name}(handle)")
        assert "wbResizeBox(" in WB[start : start + 3000], f"{name} has its own resize maths again"
