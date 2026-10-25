"""Dogfood round 1 (2026-10-25) whiteboard and mind map fixes, fixer B.

Source-level checks the suite can see; the browser numbers are in the
commit messages and `docs/roadmap/agent-remaining/fixb-1025.md`.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WB = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")


def test_new_map_toast_says_what_enter_does_while_typing():
    # Enter in a topic's editor is a line break (the owner, 2026-10-10), so the
    # creation toast must name the key that adds a sibling while typing.
    assert "While typing a name, Ctrl+Enter adds the sibling." in WB


def _function(name: str) -> str:
    start = WB.index(f"function {name}(")
    return WB[start : WB.index("\n}\n", start) + 3]


def _node(expr: str):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    script = (
        "".join(_function(n) for n in ("wbShapeDims", "wbEllipseDrawD"))
        + f"console.log(JSON.stringify({expr}));"
    )
    return json.loads(
        subprocess.run([node, "-e", script], capture_output=True, text=True, check=True).stdout
    )


def _bbox(d: str):
    # M left top+ry, then two arcs of width w: the box is left..left+w, top..top+2ry.
    parts = d.replace("a", " a ").split()
    left, mid = float(parts[1]), float(parts[2])
    rx, ry, w = float(parts[4]), float(parts[5]), float(parts[9])
    return left, mid - ry, w, 2 * ry, rx


def test_ellipse_is_drawn_corner_to_corner_like_the_rectangle():
    # Press at (100, 100), drag to (200, 160): the rectangle's box is x 100..200,
    # y 100..160, and the ellipse must fill the same box (it used to centre on
    # the press and reach 200 wide, 120 tall, 100 left and 40 above it).
    left, top, w, h, rx = _bbox(_node("wbEllipseDrawD(100, 100, 200, 160, false)"))
    assert (left, top, w, h) == (100, 100, 100, 60) and rx == 50


def test_ellipse_dragged_up_left_stays_in_the_dragged_box():
    left, top, w, h, _ = _bbox(_node("wbEllipseDrawD(200, 160, 100, 100, false)"))
    assert (left, top, w, h) == (100, 100, 100, 60)


def test_ellipse_with_shift_is_a_circle_away_from_the_press():
    left, top, w, h, _ = _bbox(_node("wbEllipseDrawD(200, 160, 100, 100, true)"))
    assert (left, top, w, h) == (100, 60, 100, 100)


def test_draw_out_snap_has_no_centred_mode():
    assert "centred = false" not in _function("wbDrawOutSnap").split("{")[0]
