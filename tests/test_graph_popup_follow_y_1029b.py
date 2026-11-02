"""Audit 1029 rank 58 (G25): the graph popup followed a dragged node in x only.

Reproduced at 1280x640 (`/tmp/claude-0/graphb/p58c.js`, session scratch) with a
long note open: the popup took the map's whole height less 16 (517 of 533), so
its room to slide was 16px; the node was dragged 280px down and the popup moved
0. An undragged popup is now capped to 60% of the room (never under 280px, the
body scrolls inside it and the dock stays pinned), so it has a range to follow
in. One that the head has moved keeps the full room, as it stays where put.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
GRAPH = (ROOT / "frontend" / "js" / "graph.js").read_text(encoding="utf-8")


def _fn(name: str) -> str:
    start = GRAPH.index(f"function {name}(")
    return GRAPH[start : GRAPH.index("\n}\n", start) + 2]


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_an_undragged_popup_leaves_room_to_follow_its_node_and_a_dragged_one_does_not() -> None:
    script = (
        _fn("graphPopupCap")
        + """
        console.log(JSON.stringify({
          tall: graphPopupCap(533, false), taller: graphPopupCap(785, false), small: graphPopupCap(300, false),
          tiny: graphPopupCap(120, false), dragged: graphPopupCap(533, true),
        }));
        """
    )
    run = subprocess.run([shutil.which("node"), "-e", script], capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stderr
    out = json.loads(run.stdout)
    assert out["tall"] == 320 and out["taller"] == 471, out
    assert out["small"] == 280 and out["tiny"] == 120, "never under 280, never over the room"
    assert out["dragged"] == 517, "a popup the head has moved keeps the whole room"
    # The range it can slide in is what is left: 533 - 320 - 16 = 197 at the worst window measured.
    assert 533 - out["tall"] - 16 >= 150


def test_the_placement_uses_the_cap_for_the_desktop_popup_only() -> None:
    body = _fn("placeGraphPopup")
    assert "popup.style.maxHeight = `${graphPopupCap(room, graphLate.popupDragged)}px`;" in body
    sheet = body[: body.index('popup.classList.remove("graph-popup-sheet");')]
    assert "graphPopupCap" not in sheet, "the phone sheet keeps its three quarters"
    assert re.search(r"function graphPopupCap\(room, dragged\)", GRAPH)
