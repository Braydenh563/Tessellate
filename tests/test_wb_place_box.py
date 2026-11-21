"""A text or sticky drag makes a box of the dragged size.

The owner (2026-09-24): "I cant drag to create a custom sized textbox on the
whiteboard when selected on the textbox tool", "same with the sticky notes".
A click still drops the default size; a press that travels draws the box.
`wbPlaceBox` turns the press and the pointer into that box (with a minimum
per kind) and `wbSquareCorner` is what Shift does. Run in node against the
source; the browser half is `scratchpad/ui-sweeps/wbplacedrag.js`.
"""

from tests._app_js import frontend_text
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = frontend_text("whiteboard.js")


def _function(name: str) -> str:
    start = SOURCE.index(f"function {name}(")
    return SOURCE[start : SOURCE.index("\n}\n", start) + 3]


def _run(expr: str):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    minimum = SOURCE[SOURCE.index("const WB_PLACE_MIN") :].split("\n", 1)[0]
    script = minimum + "\n" + _function("wbPlaceBox") + _function("wbSquareCorner") + f"\nconsole.log(JSON.stringify({expr}));\n"
    out = subprocess.run([node, "-e", script], capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip())


def test_a_drag_down_and_right_starts_at_the_press() -> None:
    box = _run('wbPlaceBox({ x: 100, y: 50, place: "text" }, 340, 180)')
    assert box == {"x": 100, "y": 50, "w": 240, "h": 130}


def test_a_drag_up_and_left_lies_on_that_side_of_the_press() -> None:
    box = _run('wbPlaceBox({ x: 100, y: 50, place: "sticky" }, -100, -50)')
    assert box == {"x": -100, "y": -50, "w": 200, "h": 100}


@pytest.mark.parametrize(("kind", "size"), [("text", (60, 32)), ("sticky", (80, 60))])
def test_a_short_drag_is_held_to_the_minimum(kind: str, size: tuple) -> None:
    box = _run(f'wbPlaceBox({{ x: 0, y: 0, place: "{kind}" }}, 10, 6)')
    assert (box["w"], box["h"]) == size


def test_shift_takes_the_longer_travel_both_ways() -> None:
    assert _run("wbSquareCorner({ x: 0, y: 0 }, 220, 120)") == [220, 220]
    assert _run("wbSquareCorner({ x: 0, y: 0 }, -90, 150)") == [-150, 150]


def test_the_click_after_a_drawn_box_is_spent() -> None:
    """The release of a drag also clicks the canvas; that click must not drop a second box."""
    click = SOURCE[SOURCE.index('containerEl.addEventListener("click", (e) => {') :]
    click = click[: click.index("\n  });\n")]
    spent = click.index("if (wbPlaceJustDrawn)")
    assert spent < click.index("wbCreateTextBox(x, y)") and spent < click.index("wbCreateSticky(x, y)")
