"""B29 (INBOX 904): the whiteboard's group and format controls say what is true.

The owner: "the ungroup button on the popup tools doesn't change, I cant widen
objects on one axis when grouped, resizing or moving objects doesn't update
their xywh values in the format panel in real time".

Measured by `scratchpad/ui-sweeps/wb1017-b29.js` on two grouped text boxes:

- Group and Ungroup both stayed on the bar before and after grouping;
- the panel's W and H were disabled for any selection of more than one item;
- x/y/w/h read 200/200/410/140 in the middle of a move and of a resize and
  caught up only on release.

The browser half is the sweep; this pins the pure state function and the
three wiring points.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BOARD = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")
FORMAT = (ROOT / "frontend" / "js" / "whiteboard-format.js").read_text(encoding="utf-8")


def _function(source: str, name: str) -> str:
    start = source.index(f"function {name}(")
    return source[start : source.index("\n}\n", start) + 3]


@pytest.mark.parametrize(
    ("groups", "can_group", "can_ungroup"),
    [
        ([None, None], True, False),
        (["g1", "g1"], False, True),
        (["g1", None], True, True),
        (["g1", "g2"], True, True),
        ([None], False, False),
    ],
)
def test_group_buttons_follow_the_selection(groups: list, can_group: bool, can_ungroup: bool) -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    items = [{"group_id": g} for g in groups]
    script = _function(BOARD, "wbGroupButtonState") + f"\nconsole.log(JSON.stringify(wbGroupButtonState({json.dumps(items)})));\n"
    out = subprocess.run([node, "-e", script], capture_output=True, text=True, check=True)
    assert json.loads(out.stdout.strip()) == {"canGroup": can_group, "canUngroup": can_ungroup}


def test_the_bar_applies_the_state_and_group_commands_refresh_it() -> None:
    fill = _function(BOARD, "wbFillContextBar")
    assert "wbSyncGroupButtons()" in fill, "the multi-selection bar must set the two buttons from the selection"
    for name in ("wbGroupSelection", "wbUngroupSelection"):
        assert "wbUpdateContextBar()" in _function(BOARD, name), f"{name} must refresh the bar it just made stale"


def test_a_selection_of_several_can_be_sized_on_one_axis_from_the_panel() -> None:
    sync = _function(FORMAT, "wbFormatSync")
    assert "entries.length !== 1" not in sync, "W and H were disabled for every multi-selection"
    geometry = _function(FORMAT, "wbFmtGeometry")
    assert "entries.length !== 1) return" not in geometry
    assert "wbFmtScaleSelection" in geometry


def test_the_panel_numbers_follow_a_drag_while_it_is_held() -> None:
    assert "function wbFormatLiveSoon(" in FORMAT
    assert 'addEventListener("pointermove", wbFormatLiveSoon' in FORMAT, "a held move or resize must refresh x/y/w/h"
    # A group's live sketch path is part of its box mid-resize.
    assert "_liveD" in _function(BOARD, "wbItemBBox")
