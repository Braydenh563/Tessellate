"""A map too big to fit opens with its content on screen, not an empty corner.

Owner, 2026-10-19: "when I go onto the mindmap it doesnt focus me on the
content and puts me down and to the right where nothing is." The fallback for
a map whose fit is illegible centred the root in the canvas, which for a tree
that grows right and down leaves the top-left empty. `wbMapOpenTarget` starts
the view at the content's edge unless that hides the root. The browser half is
`scratchpad/ui-sweeps/mapopenframe.js`.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")

needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
FREE = {"left": 60, "top": 60, "right": 780, "bottom": 480}


def _function(name: str) -> str:
    start = SOURCE.index(f"function {name}(")
    return SOURCE[start : SOURCE.index("\n}\n", start) + 3]


def _target(bounds: dict, root: dict, free: dict) -> dict:
    call = f"wbMapOpenTarget({json.dumps(bounds)}, {json.dumps(root)}, {json.dumps(free)}, 1)"
    script = _function("wbMapOpenTarget") + f"console.log(JSON.stringify({call}));"
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def box(x0: float, y0: float, x1: float, y1: float) -> dict:
    return {"minX": x0, "minY": y0, "maxX": x1, "maxY": y1}


@needs_node
def test_a_ladder_from_the_top_left_opens_at_its_own_corner() -> None:
    t = _target(box(0, 0, 520, 1404), box(0, 0, 200, 44), FREE)
    assert t["k"] == 1
    assert 60 <= t["x"] <= 140 and 60 <= t["y"] <= 140


@needs_node
def test_a_central_root_is_centred_when_the_content_edge_would_hide_it() -> None:
    t = _target(box(-1500, -900, 1500, 900), box(-100, -22, 100, 22), FREE)
    assert abs(t["x"] - 420) <= 1 and abs(t["y"] - 270) <= 1


def test_the_open_fallback_is_no_longer_a_fit() -> None:
    body = _function("wbFrameMapOnOpen")
    assert "wbFit.on = false" in body, "a refit must not undo the 1:1 view"
    assert "wbMapOpenTarget(" in body
