"""INBOX 1445: "I cant left click drag to pan on the mind map".

The 2026-10-19 reversal (MINDMAP_PLAN decision 48) gave the left drag on empty
canvas back to the box select for boards and maps alike, so a map had no
left-drag pan. On a map a left drag on bare canvas pans and Shift draws the box;
a press on a topic still moves the topic. The filter and the box select share
`wbPansOnLeftDrag`, so they cannot disagree about who owns the gesture. Since
INBOX 1450 a board follows the same rule.
Browser half, measured with a Playwright drag on an imported map: view
(489,329) to (369,259) on a (-120,-70) drag, Shift draws the box, a topic drag
leaves the view alone.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")


def _function(name: str) -> str:
    start = SOURCE.index(f"function {name}(")
    return SOURCE[start : SOURCE.index("\n}\n", start) + 3]


def _filter(*, is_map: bool, tool: str = "select", shift: bool = False, bare: bool = True) -> bool:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    event = {"type": "mousedown", "button": 0, "buttons": 1, "shiftKey": shift, "target": None}
    script = (
        "const nmb = { grabbed: false }; let wbSpaceHeld = false; let wbMidPanHeld = false;"
        " const wbBoardState = { wheel: { at: -1e9, pad: false } };"
        f" globalThis.window = {{ currentTool: {json.dumps(tool)} }};\n"
        f"function wbIsBareCanvas() {{ return {json.dumps(bare)}; }}\n"
        f"function wbIsMap() {{ return {json.dumps(is_map)}; }}\n"
        + _function("wbPansOnLeftDrag")
        + _function("wbTrackpadPan")
        + _function("wbCompanionHeld")
        + _function("wbZoomFilter")
        + f"\nconsole.log(JSON.stringify(Boolean(wbZoomFilter({json.dumps(event)}))));\n"
    )
    out = subprocess.run([node, "-e", script], capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip())


def test_a_left_drag_on_empty_map_canvas_pans() -> None:
    assert _filter(is_map=True) is True


def test_a_left_drag_on_empty_board_canvas_pans_too() -> None:
    """INBOX 1450, the owner: "cant left click drag to pan now on whiteboard".
    Until then a board's plain left drag stayed the box select (this file
    pinned that); the board takes the map's rule, Shift-drag boxes."""
    assert _filter(is_map=False) is True


@pytest.mark.parametrize(
    ("kwargs", "why"),
    [
        ({"is_map": True, "bare": False}, "a press on a topic moves the topic"),
        ({"is_map": True, "shift": True}, "Shift draws the box"),
        ({"is_map": True, "tool": "text"}, "a drawing tool keeps the drag"),
        ({"is_map": False, "shift": True}, "Shift draws the box on a board too"),
    ],
)
def test_everything_else_keeps_its_gesture(kwargs: dict, why: str) -> None:
    assert _filter(**kwargs) is False, why


def test_the_box_select_stands_aside_for_the_map_pan() -> None:
    start = SOURCE.index('if (!place && e.pointerType === "touch") return;')
    assert "wbPansOnLeftDrag(e)" in SOURCE[start : start + 300]
