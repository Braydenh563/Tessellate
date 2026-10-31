"""INBOX 1428: a board opened from elsewhere fits its content.

The owner opened "Sequence diagram" from the timeline and it kept a view
showing only its top-left corner: any overlap with the content counted as
"shows the board", and with no view of its own the last board's camera was
kept. These run the real `wbViewShowsContent` under node.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

WB = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")


def _function(name: str) -> str:
    start = WB.index(f"function {name}(")
    return WB[start : WB.index("\n}\n", start) + 3]


def _shows(view: dict, bounds: dict) -> bool:
    free = {"left": 0, "top": 0, "right": 1600, "bottom": 900}
    script = _function("wbViewShowsContent") + f"\nconsole.log(JSON.stringify(wbViewShowsContent({json.dumps(view)}, {json.dumps(bounds)}, {json.dumps(free)})));"
    return json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True, timeout=30).stdout)


needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
BOARD = {"minX": 0, "minY": 0, "maxX": 2000, "maxY": 1200}


@needs_node
def test_a_view_showing_only_a_corner_is_not_kept():
    # At 0.52 the board is 1040 x 624 on screen; shifted so 160 x 120 of it shows.
    assert _shows({"x": -880, "y": -504, "k": 0.52}, BOARD) is False


@needs_node
def test_a_view_showing_most_of_the_board_is_kept():
    assert _shows({"x": 100, "y": 50, "k": 0.52}, BOARD) is True


@needs_node
def test_a_big_board_zoomed_in_on_one_part_is_kept():
    # 2 x zoom: the board is 4000 x 2400, the canvas wholly covered by it.
    assert _shows({"x": -1000, "y": -600, "k": 2}, BOARD) is True


@needs_node
def test_a_view_off_the_content_is_not_kept():
    assert _shows({"x": 5000, "y": 5000, "k": 1}, BOARD) is False


def test_a_board_without_its_own_view_is_framed():
    restore = _function("wbRestoreOrFrameBoard")
    assert "if (bounds) wbZoomToFit({ animate: false });" in restore
    assert "d3.zoomTransform(container)" not in restore
