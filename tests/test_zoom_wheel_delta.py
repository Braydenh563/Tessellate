"""A ctrl+wheel notch of a mouse zooms by a notch, not by five times.

d3-zoom multiplies a wheel delta by ten while ctrl is held, because a browser
reports a trackpad pinch as ctrl+wheel with deltas of a few pixels. A mouse
wheel notch with ctrl held is 100 to 120 pixels of the same event, so the
default turned one notch into 2^2.4 = 5.3x and two notches took a map from 1x
to its 4x ceiling (`maprender.md`). `zoomWheelDelta` (navigation.js) clamps the
delta while ctrl is held and otherwise scales as d3's own default does. The
board and the graph both hand it to `d3.zoom().wheelDelta`. Measured in
Chromium by `scratchpad/ui-sweeps/ctrlwheelzoom.js`: one notch x1.39, a pinch
step x1.06.
"""

from tests._app_js import frontend_text
import json
import math
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
APP = (JS / "navigation.js").read_text(encoding="utf-8")  # moved from app.js (its gzip cap)


def _delta(event: dict) -> float:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    start = APP.index("function zoomWheelDelta(")
    body = APP[start : APP.index("\n}\n", start) + 3]
    script = body + f"\nconsole.log(JSON.stringify(zoomWheelDelta({json.dumps(event)})));\n"
    out = subprocess.run([node, "-e", script], capture_output=True, text=True, check=True)
    return float(json.loads(out.stdout.strip()))


def _d3_default(event: dict) -> float:
    """d3-zoom v3's own wheelDelta, for the cases that must not change."""
    mode = event["deltaMode"]
    return -event["deltaY"] * (0.05 if mode == 1 else 1 if mode else 0.002) * (10 if event["ctrlKey"] else 1)


def test_a_mouse_notch_with_ctrl_is_about_a_notch() -> None:
    factor = 2 ** _delta({"deltaY": -120, "deltaMode": 0, "ctrlKey": True})
    assert 1.2 < factor < 1.6, f"one ctrl+wheel notch zoomed by x{factor:.2f}"
    # And the opposite notch undoes it exactly.
    assert math.isclose(_delta({"deltaY": 120, "deltaMode": 0, "ctrlKey": True}), -_delta({"deltaY": -120, "deltaMode": 0, "ctrlKey": True}))


@pytest.mark.parametrize(
    "event",
    [
        {"deltaY": -4, "deltaMode": 0, "ctrlKey": True},  # a trackpad pinch step
        {"deltaY": 9, "deltaMode": 0, "ctrlKey": True},
        {"deltaY": -100, "deltaMode": 0, "ctrlKey": False},  # a plain wheel (the graph zooms on it)
        {"deltaY": 3, "deltaMode": 1, "ctrlKey": False},
    ],
)
def test_a_pinch_and_a_plain_wheel_zoom_as_they_did(event: dict) -> None:
    assert math.isclose(_delta(event), _d3_default(event))


def test_the_board_and_the_graph_use_it() -> None:
    assert ".wheelDelta(zoomWheelDelta)" in frontend_text("whiteboard.js")
    assert ".wheelDelta(zoomWheelDelta)" in (JS / "graph-canvas.js").read_text(encoding="utf-8")
