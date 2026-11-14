"""The map topic menu opens beside the ring's More sector, never over it.

INBOX 421 a, reported a third time from the desktop window: the topic menu
at the top-left of the window. The placement knew two spots (left or right
of the sector) and a clamp; in a page made narrow by Windows' display scale
(a 1256px window at 200% is a 628px page) neither side had room and the clamp
put the menu over More itself (mapmorezoom.js: menu 8,199 to 318,675, More
243,411 to 385,560). `wbMenuSpotBeside` tries the sides, then below and
above, then the roomier of those two with the height capped; `wbSetMenuSpot`
refuses a set-measure-correct step that would move the menu out of the
window. Run in node against the source with stand-in elements; the browser
half is `scratchpad/ui-sweeps/mapmorezoom.js`.
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


def _run(body: str, w: int, h: int) -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    script = (
        f"globalThis.window = {{ innerWidth: {w}, innerHeight: {h} }};\n"
        f"globalThis.document = {{ documentElement: {{ clientWidth: {w}, clientHeight: {h} }} }};\n"
        "const warned = []; console.warn = (...a) => warned.push(a[0]);\n"
        + _function("wbMenuSpotBeside")
        + _function("wbSetMenuSpot")
        + body
    )
    out = subprocess.run([node, "-e", script], capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip())


def _spot(anchor: dict, size: dict, w: int, h: int) -> dict:
    return _run(
        f"console.log(JSON.stringify(wbMenuSpotBeside({json.dumps(anchor)}, {json.dumps(size)})));",
        w,
        h,
    )


def _covers(spot: dict, size: dict, anchor: dict) -> bool:
    h = spot["maxHeight"] or size["height"]
    across = min(spot["left"] + size["width"], anchor["right"]) - max(spot["left"], anchor["left"])
    down = min(spot["top"] + h, anchor["bottom"]) - max(spot["top"], anchor["top"])
    return across > 0 and down > 0


def _inside(spot: dict, size: dict, w: int, h: int) -> bool:
    height = spot["maxHeight"] or size["height"]
    return spot["left"] >= 8 and spot["top"] >= 8 and spot["left"] + size["width"] <= w - 8 and spot["top"] + height <= h - 8


MORE_LEFT = {"left": 24, "top": 330, "right": 161, "bottom": 489, "width": 137, "height": 159, "outward": "left"}


def test_room_on_the_side_the_sector_faces_puts_the_menu_there_level_with_it():
    anchor = dict(MORE_LEFT, left=538, right=675)
    size = {"width": 239, "height": 303}
    spot = _spot(anchor, size, 1440, 900)
    assert spot["side"] == "left" and spot["left"] + 239 + 4 == 538, spot
    assert spot["top"] == 330 and spot["maxHeight"] is None, spot


def test_no_room_on_the_left_takes_the_right():
    size = {"width": 239, "height": 303}
    spot = _spot(MORE_LEFT, size, 1440, 900)
    assert spot["side"] == "right" and spot["left"] == 161 + 4, spot


def test_a_narrow_page_with_no_room_either_side_never_covers_more():
    # 1256x1366 at 200% with the app at 130%: the measured case.
    anchor = {"left": 243, "top": 411, "right": 385, "bottom": 560, "width": 142, "height": 149, "outward": "left"}
    size = {"width": 310, "height": 476}
    spot = _spot(anchor, size, 628, 683)
    assert not _covers(spot, size, anchor), spot
    assert _inside(spot, size, 628, 683), spot
    # Hung from the edge the sector faces, and touching it on the other axis.
    assert spot["side"] == "above" and spot["top"] + spot["maxHeight"] + 4 == 411, spot


def test_a_short_menu_goes_below_when_the_sides_are_full():
    anchor = {"left": 243, "top": 200, "right": 385, "bottom": 349, "width": 142, "height": 149, "outward": "left"}
    size = {"width": 310, "height": 240}
    spot = _spot(anchor, size, 628, 683)
    assert spot["side"] == "below" and spot["top"] == 353 and spot["maxHeight"] is None, spot
    assert not _covers(spot, size, anchor)


def _set(read_dx: int, read_dy: int, w: int = 1440, h: int = 900) -> dict:
    return _run(
        f"""
const menu = {{
  style: {{}},
  getBoundingClientRect() {{
    const left = parseFloat(this.style.left) + {read_dx};
    const top = parseFloat(this.style.top) + {read_dy};
    return {{ left, top, width: 240, height: 300, right: left + 240, bottom: top + 300 }};
  }},
}};
wbSetMenuSpot(menu, {{ left: 200, top: 300, maxHeight: null }}, "topic menu");
console.log(JSON.stringify({{ left: menu.style.left, top: menu.style.top, warned }}));
""",
        w,
        h,
    )


def test_a_steady_offset_is_corrected_by_the_difference():
    got = _set(0, 12)
    assert got["top"] == "288px" and got["left"] == "200px" and not got["warned"], got


def test_a_correction_that_would_leave_the_window_is_refused_and_logged():
    # A read with the menu somewhere other than where it was put: undoing it
    # would write top -200, the menu above the window's own top.
    got = _set(0, 500)
    assert got["top"] == "300px", got
    assert got["warned"] and "outside the window" in got["warned"][0], got


def test_the_node_menu_and_the_corner_guard_both_place_through_it():
    opener = _function("wbOpenMapNodeMenu")
    assert "wbMenuSpotBeside(anchor, size)" in opener
    assert 'wbSetMenuSpot(menu, spot, "topic menu")' in opener
    assert "wbSetMenuSpot(menu, wbMenuSpotBeside(box" in _function("wbGuardMenuCorner")
