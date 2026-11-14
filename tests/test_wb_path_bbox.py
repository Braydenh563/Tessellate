"""`wbPathBBox` bounds every path the shape tools write.

The circle tool writes absolute arcs (`A`); the parser handled the relative
spelling only, so a circle's box collapsed to its first point and a marquee
over it selected nothing (INBOX 252). Run in node against the function's own
source, the way the other whiteboard geometry tests do.
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


def _function(name: str) -> str:
    start = SOURCE.index(f"function {name}(")
    end = SOURCE.index("\n}\n", start) + 3
    return SOURCE[start:end]


def _run(expression: str) -> object:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    script = _function("wbPathBBox") + _function("wbTransformPathD") + f"\nconsole.log(JSON.stringify({expression}));"
    out = subprocess.run([node, "-e", script], capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip())


def _bbox(d: str) -> dict:
    return _run(f"wbPathBBox({json.dumps(d)})")


def _moved(d: str, **transform) -> str:
    return _run(f"wbTransformPathD({json.dumps(d)}, {json.dumps(transform)})")


def test_a_circle_written_with_absolute_arcs_has_its_full_box():
    box = _bbox("M 90 100 A 10 10 0 1 0 110 100 A 10 10 0 1 0 90 100 Z")
    assert (box["minX"], box["minY"], box["maxX"], box["maxY"]) == (90, 90, 110, 110)


def test_relative_arcs_still_bound_the_same_circle():
    box = _bbox("M 90 100 a 10 10 0 1 0 20 0 a 10 10 0 1 0 -20 0 Z")
    assert (box["minX"], box["minY"], box["maxX"], box["maxY"]) == (90, 90, 110, 110)


def test_absolute_h_and_v_move_the_pen():
    box = _bbox("M 0 0 H 40 V 30 H 0 Z")
    assert (box["width"], box["height"]) == (40, 30)


def test_the_source_still_has_the_function():
    assert re.search(r"^function wbPathBBox\(d\) \{", SOURCE, re.M)


CIRCLE = "M 90 100 A 10 10 0 1 0 110 100 A 10 10 0 1 0 90 100 Z"


def test_a_circle_moves_when_dragged():
    """The transform walk knew relative arcs only, so a circle (absolute
    arcs) came back unchanged from every move, resize and rotation: it could
    be selected and never dragged (the owner, 2026-09-14)."""
    moved = _moved(CIRCLE, dx=100, dy=50)
    assert moved != CIRCLE
    box = _bbox(moved)
    assert (box["minX"], box["minY"], box["maxX"], box["maxY"]) == (190, 140, 210, 160)


def test_a_circle_scales_about_its_anchor():
    box = _bbox(_moved(CIRCLE, sx=2, sy=2, anchorX=90, anchorY=90))
    assert (box["minX"], box["minY"], box["maxX"], box["maxY"]) == (90, 90, 130, 130)


def test_absolute_h_and_v_move_with_the_path():
    box = _bbox(_moved("M 0 0 H 40 V 30 H 0 Z", dx=5, dy=5))
    assert (box["minX"], box["minY"], box["maxX"], box["maxY"]) == (5, 5, 45, 35)
