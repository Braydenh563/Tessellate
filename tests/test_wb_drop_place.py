"""Where a thing put on a board lands (INBOX 664).

The owner, 2026-10-06: "Placing coordinates of templates on the mindmap and
whiteboard could be improved (little off from the cursor)." Measured before
(scratchpad/ui-sweeps/dropplace.js): a click from the Library landed 165px
left of the open canvas, a drag ignored where the tile was held (291px for
the Kanban template held by its corner at 100%), a note card sat 25px high, a
map template 237px off. The rule now: the point of the thing held stays under
the pointer; a click puts its middle in the middle of the canvas you can see.

The pure halves run in node against the functions' own source; the browser
half is the sweep.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WB = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")
LIB = (ROOT / "frontend" / "js" / "whiteboard-library.js").read_text(encoding="utf-8")


def _function(source: str, name: str) -> str:
    start = source.index(f"function {name}(")
    return source[start : source.index("\n}\n", start) + 3]


def _run(expr: str):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    script = "".join(_function(WB, n) for n in ("wbScreenToBoard", "wbAnchorDelta", "wbFreeCanvasRect"))
    out = subprocess.run([node, "-e", script + f"\nconsole.log(JSON.stringify({expr}));"], capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip())


# --- the one conversion -------------------------------------------------------


def test_a_point_on_screen_is_read_through_the_pan_and_the_zoom() -> None:
    at = _run("wbScreenToBoard(516, 380, { left: 16, top: 80, scale: 1 }, { x: 137, y: -83, k: 2 })")
    assert at == [(500 - 137) / 2, (300 + 83) / 2]


def test_a_scaled_canvas_is_read_back_to_its_own_pixels() -> None:
    """An ancestor's CSS transform scales the drawn canvas; the layers inside
    it are laid out in unscaled pixels."""
    at = _run("wbScreenToBoard(116, 80, { left: 16, top: 30, scale: 0.5 }, { x: 0, y: 0, k: 1 })")
    assert at == [200, 100]


def test_every_screen_to_board_conversion_goes_through_the_one_function() -> None:
    """Nine places wrote `(clientX - rect.left - t.x) / t.k` by hand. A tenth
    would be a tenth place to get the origin wrong."""
    for name, source in (("whiteboard.js", WB), ("whiteboard-library.js", LIB)):
        hand = re.findall(r"\(\w+\.clientX - \w+\.left - \w+\.x\) / \w+\.k", source)
        assert hand == [], f"{name}: {hand}"
    assert "wbClientToBoard(e.clientX, e.clientY)" in _function(WB, "wbBoardPointOf")


# --- the anchor -----------------------------------------------------------------


def test_the_middle_goes_to_the_point() -> None:
    dx, dy = _run("wbAnchorDelta({ minX: 0, minY: 0, maxX: 160, maxY: 100 }, [500, 300])")
    assert (dx, dy) == (420, 250)


def test_a_grabbed_corner_quarter_goes_to_the_point() -> None:
    dx, dy = _run("wbAnchorDelta({ minX: 10, minY: 20, maxX: 1050, maxY: 540 }, [0, 0], [0.25, 0.25])")
    assert (dx, dy) == (-(10 + 260), -(20 + 130))


def test_snap_puts_the_corner_on_the_grid_afterwards() -> None:
    """The one allowed difference from the pointer: the grid's own step."""
    dx, dy = _run("wbAnchorDelta({ minX: 0, minY: 0, maxX: 160, maxY: 100 }, [503, 307], [0.5, 0.5], 24)")
    assert ((0 + dx) % 24, (0 + dy) % 24) == (0, 0)
    assert abs(80 + dx - 503) <= 12 and abs(50 + dy - 307) <= 12


# --- the middle of the canvas you can see ----------------------------------------

BOX = "{ left: 16, top: 80, right: 1424, bottom: 847 }"


def test_the_chrome_docked_over_the_canvas_is_left_out() -> None:
    """Measured at 1440x900 with the Library open: the top bar, the side rail
    with its panel, the tool dock at the bottom."""
    covers = "[{ left: 24, top: 88, right: 1416, bottom: 130 }, { left: 24, top: 138, right: 346, bottom: 787 }, { left: 351, top: 795, right: 1089, bottom: 841 }]"
    free = _run(f"wbFreeCanvasRect({BOX}, {covers})")
    assert free == {"left": 346, "top": 130, "right": 1424, "bottom": 795}


def test_a_cover_over_most_of_the_canvas_is_not_an_edge() -> None:
    """A phone's sheet, a panel opened wide: the middle stays the canvas's."""
    free = _run(f"wbFreeCanvasRect({BOX}, [{{ left: 16, top: 200, right: 1424, bottom: 847 }}])")
    assert free == {"left": 16, "top": 80, "right": 1424, "bottom": 847}


def test_a_hidden_or_empty_cover_changes_nothing() -> None:
    free = _run(f"wbFreeCanvasRect({BOX}, [null, {{ left: 0, top: 0, right: 0, bottom: 0 }}])")
    assert free == {"left": 16, "top": 80, "right": 1424, "bottom": 847}


# --- the wiring ---------------------------------------------------------------------


def test_a_tile_drag_carries_its_picture_held_where_it_was_pressed() -> None:
    assert "e.dataTransfer.setDragImage(svg, grab.offset[0], grab.offset[1])" in LIB
    assert "wbLibState.libPress?.tile === tile" in LIB
    assert "{ onto, grab: wbLibState.libGrab" in LIB  # intoLink joined the call (drop on a line)


def test_a_placement_is_anchored_inside_its_own_undo_step() -> None:
    """The move that anchors what was drawn is made inside the same
    `wbRecordGesture` as the placement, so one Ctrl+Z takes both."""
    place = _function(LIB, "wbLibPlace")
    gesture = place[place.index("await wbRecordGesture(") : place.index("if (!made) return;")]
    assert "await wbAnchorPlaced(rows, point, frac);" in gesture
    assert "wbAnchorDelta(drawn, point, frac" in place


def test_a_dropped_note_is_one_undo_step_and_anchored() -> None:
    start = WB.index("const at = wbClientToBoard(e.clientX, e.clientY);")
    body = WB[start : WB.index("} catch (err) {", start)]
    assert "await wbRecordGesture(async () => {" in body
    assert 'await wbAnchorPlaced([{ kind: "node", item: res }], at);' in body


def test_a_click_steps_off_the_last_click_rather_than_a_timer() -> None:
    centre = _function(LIB, "wbLibCentre")
    assert "wbViewCentre()" in centre
    assert "Date.now()" not in centre
