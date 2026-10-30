"""INBOX 1452, the owner 2026-10-30: "i think left click drag select instead
of pan on the whiteboard and mindmap is the way to go, that way right click hold
can be pan and trackpad users two finger pan or zoom".

This file pinned INBOX 1445 and 1450 (a plain left drag on empty canvas panned,
Shift drew the box); the owner reversed that, so its intent moved with them. A
left drag on empty canvas with Select is the selection box on a map and a board
alike; the right button, Space, the middle button and the Pan tool pan, and a
two-finger trackpad scroll pans (`wbTrackpadPan`).
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


def _filter(*, is_map: bool, tool: str = "select", shift: bool = False, bare: bool = True, button: int = 0, space: bool = False) -> bool:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    event = {"type": "mousedown", "button": button, "buttons": 1 << [0, 2, 1][button], "shiftKey": shift, "target": None}
    script = (
        f"const nmb = {{ grabbed: false }}; let wbSpaceHeld = {json.dumps(space)}; let wbMidPanHeld = false;"
        " const wbBoardState = { wheel: { at: -1e9, pad: false } };"
        f" globalThis.window = {{ currentTool: {json.dumps(tool)} }};\n"
        f"function wbIsBareCanvas() {{ return {json.dumps(bare)}; }}\n"
        f"function wbIsMap() {{ return {json.dumps(is_map)}; }}\n"
        + _function("wbTrackpadPan")
        + _function("wbCompanionHeld")
        + _function("wbZoomFilter")
        + f"\nconsole.log(JSON.stringify(Boolean(wbZoomFilter({json.dumps(event)}))));\n"
    )
    out = subprocess.run([node, "-e", script], capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip())


@pytest.mark.parametrize("is_map", [True, False])
@pytest.mark.parametrize("shift", [False, True])
def test_a_left_drag_on_empty_canvas_selects_not_pans(is_map: bool, shift: bool) -> None:
    assert _filter(is_map=is_map, shift=shift) is False


@pytest.mark.parametrize(
    ("kwargs", "why"),
    [
        ({"is_map": True, "button": 2}, "a right drag on an empty map pans"),
        ({"is_map": False, "button": 2}, "a right drag on an empty board pans"),
        ({"is_map": False, "space": True}, "Space and drag pans"),
        ({"is_map": False, "tool": "pan"}, "the Pan tool pans"),
        ({"is_map": True, "button": 1, "bare": False}, "the middle button pans from anywhere"),
    ],
)
def test_the_other_buttons_pan(kwargs: dict, why: str) -> None:
    assert _filter(**kwargs) is True, why


def test_a_right_press_on_a_card_keeps_its_menu() -> None:
    assert _filter(is_map=False, button=2, bare=False) is False


def test_the_box_select_takes_the_plain_drag() -> None:
    start = SOURCE.index('if (!place && e.pointerType === "touch") return;')
    assert "function wbPansOnLeftDrag(" not in SOURCE
    assert "if (e.button !== 0 || !e.isPrimary) return;" in SOURCE[start : start + 500]
    assert "wbSelectFrameAt(...getLogicalMouse(e)" in SOURCE
