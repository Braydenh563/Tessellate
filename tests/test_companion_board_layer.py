"""The companion over a board's canvas: in the board's layer, sized to its zoom.

INBOX 1300 C19, the owner: "Atlas and the companion can perch on objects on
the whiteboard even when they are behind the panel, if it is perched on them
then it should be on the same leayer or x-index as them as well". C20: "the
companion jumping arounf my whiteboard a lot was a little annoying and it
took up quit a bit of the screen when I zoomed out ... if it is on an
element not part of the actual canvas like the panels or outer part of the
app like the bottom or top bar then it can be its regular size."

Measured in a browser by `scratchpad/ui-sweeps/canvas1300.js` (an
elementFromPoint pair per case: over the Format panel the panel wins, over an
object the companion does, on the top bar it is z 44 at its own size).
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
AV = (ROOT / "frontend" / "js" / "avatars.js").read_text(encoding="utf-8")
WB = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "css" / "08-consistency.css").read_text(encoding="utf-8")


def _fn(src: str, name: str) -> str:
    start = src.index(f"function {name}(")
    return src[start : src.index("\n}\n", start) + 2]


@pytest.mark.skipif(not shutil.which("node"), reason="node not installed")
def test_size_follows_zoom_never_above_its_own():
    js = _fn(AV, "nameMarkBuddyCanvasScale") + (
        "console.log(JSON.stringify([0.5, 2, 0.1, undefined, 1].map(nameMarkBuddyCanvasScale)));"
    )
    out = subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True).stdout
    assert json.loads(out) == [0.5, 1, 0.4, 1, 1]
    # Smaller than the menu's smallest size only for a fit, never kept.
    assert "Math.max(keep ? 0.7 : 0.4," in _fn(AV, "nameMarkBuddySetSize")


def test_over_the_canvas_it_takes_the_boards_layer_and_zoom():
    move = _fn(AV, "nameMarkBuddyMoveTo")
    assert "nameMarkBuddyCanvasAt(spot, x, y)" in move
    assert 'classList.toggle("nmb-canvas", nmb.canvas)' in move
    assert "nameMarkBuddyCanvasScale(board.__zoom?.k)" in move
    # On a panel (an edge outside the board) it is not on the canvas.
    assert "spot.edge?.el && !board?.contains(spot.edge.el)" in _fn(AV, "nameMarkBuddyCanvasAt")
    # The board tells it each zoom, in the frame the zoom is drawn.
    assert "nameMarkBuddyCanvasZoom(t.k)" in _fn(WB, "wbZoomFrameWork")
    # Under the rail (10), the top bar (20) and the Format panel (25).
    z = int(re.search(r"#nm-buddy-band\.nmb-canvas \{\s*z-index: (\d+);", CSS).group(1))
    assert z == 2  # the raised step: no new literal layer (test_style_scale)


def test_out_of_the_way_of_the_boards_panels_and_calmer_there():
    popups = re.search(r'^const NMB_POPUPS = "(.*)";$', AV, re.M).group(1)
    assert "#wb-format:not(.hidden)" in popups and "#wb-sidebar-panel:not(.hidden)" in popups
    board = float(re.search(r"^const NMB_BOARD_WANDER = ([\d.]+);$", AV, re.M).group(1))
    assert board < 0.35 / 2
    assert "nmb.onBoard ? NMB_BOARD_WANDER : 0.35" in _fn(AV, "nameMarkBuddyWander")
    assert 'act === "hop" && nmb.onBoard' in _fn(AV, "nameMarkBuddyDecide")
    assert "nmb.onBoard = nameMarkBuddyOnBoard();" in _fn(AV, "nameMarkBuddyTick")
