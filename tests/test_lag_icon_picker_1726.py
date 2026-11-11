"""The icon picker draws a screenful of tiles in the open and the rest in slices (INBOX 1726).

The owner's log: `input 736ms on documents: pointerup on button in #doc-toolbar` with
`frame 727ms ... icon-picker.js`. On the first open every one of the 429 emoji tiles was made and
laid out in one task (forced layout 139 to 256ms, median 183, after 4x CPU; the after-frame style
and paint another 79ms). Now 72 tiles are drawn at once (forced layout 34 to 60ms, median 39; after
frame 40 to 69ms) and the other 357 follow in idle slices of 48; the count is 429 again within
about a second. `iconPickerState.slices` is the plan, run in node here; the glue is read as source.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from tests import _js_scope

ROOT = Path(__file__).resolve().parents[1]
JS = _js_scope.unwrapped((ROOT / "frontend" / "js" / "icon-picker.js").read_text(encoding="utf-8"))

needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def _slices(counts: list[int], first: int, slice_: int) -> dict:
    block = re.search(r"^iconPickerState\.slices = .*?^\};", JS, re.S | re.M)
    assert block, "iconPickerState.slices must stay a field of the state object (no new global name)"
    script = (
        "const iconPickerState = {};\n"
        f"{block.group(0)}\n"
        f"console.log(JSON.stringify(iconPickerState.slices({json.dumps(counts)}, {first}, {slice_})));"
    )
    return json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)


@needs_node
def test_the_first_screenful_is_drawn_at_once_and_the_rest_follows_in_order() -> None:
    plan = _slices([48, 48, 48, 48], 72, 48)
    assert plan["now"] == [48, 24, 0, 0]
    assert plan["later"] == [[1, 24, 48], [2, 0, 48], [3, 0, 48]]


@needs_node
def test_every_tile_is_drawn_exactly_once_and_no_slice_crosses_a_group() -> None:
    counts = [20, 48, 7, 240, 0, 33]
    plan = _slices(counts, 72, 48)
    drawn = [0] * len(counts)
    for g, n in enumerate(plan["now"]):
        drawn[g] += n
    prev = (-1, -1)
    for g, start, end in plan["later"]:
        assert drawn[g] == start, "a slice begins where the group's drawn tiles end"
        assert 0 < end - start <= 48 and end <= counts[g]
        assert (g, start) > prev, "slices run in document order"
        prev = (g, start)
        drawn[g] = end
    assert drawn == counts
    assert sum(plan["now"]) == 72


@needs_node
def test_a_short_list_has_nothing_left_for_later() -> None:
    plan = _slices([5, 9], 72, 48)
    assert plan == {"now": [5, 9], "later": []}


def test_draw_fills_from_the_plan_and_a_redraw_drops_what_is_pending() -> None:
    draw = JS[JS.index("  const draw = () => {") : JS.index("  //: The number of tiles in one row")]
    assert "iconPickerState.slices(specs.map((x) => x.shown.length))" in draw
    assert "drawn += 1;" in draw.split("for (const b of tabs.children)")[0], "a redraw drops the old slices"
    assert "if (pending.length) fillSoon(drawn);" in draw
    # The search is drawn the same way, so a keystroke does not lay out 240 tiles at once.
    assert 'addGroup(`${found.length} found`, found.slice(0, 240), "found")' in draw


def test_the_slices_run_when_idle_and_stop_with_the_panel_or_a_redraw() -> None:
    soon = JS[JS.index("  const fillSoon = (turn) => {") : JS.index("  const finishDraw")]
    assert "window.requestIdleCallback" in soon and "if (turn !== drawn || !panel.isConnected) return;" in soon
    assert "pending.shift()?.();" in soon and "fillSoon(turn)" in soon


def test_a_key_that_walks_the_tiles_draws_the_rest_first() -> None:
    keys = JS[JS.index('  list.addEventListener("keydown"') :]
    keys = keys[: keys.index("  list.addEventListener(\"click\"")]
    guard = 'if (pending.length && ["ArrowRight", "ArrowLeft", "ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) finishDraw();'
    assert guard in keys
    assert keys.index(guard) < keys.index("rowLength()"), "End and the arrows see every tile"
    assert "while (pending.length) pending.shift()();" in JS


def test_the_defaults_are_about_nine_rows_and_one_group_page() -> None:
    head = re.search(r"^iconPickerState\.slices = \(counts, first = (\d+), slice = (\d+)\) => \{", JS, re.M)
    assert head, "the plan carries its own defaults, so no new name enters the shared scope"
    first, slice_ = int(head.group(1)), int(head.group(2))
    assert 48 <= first <= 96, "about nine rows: what shows before a scroll"
    assert slice_ <= 48, "a slice is one group page at most: a few ms of layout each"
