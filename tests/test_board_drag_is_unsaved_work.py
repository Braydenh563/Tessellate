"""A board mid-drag is unsaved work (L-world-class-97, WORLD_CLASS_PLAN 22.1.4).

A card, box or shape held in the pointer is only written when it is released, so
a reload or a closed window in that moment loses the move. The board answers
`window.wbMidDrag()` from the gesture it already tracks (`wbGesture`, the one
Escape puts back); navigation.js asks it in the one `beforeunload` guard, the way
it asks for a live recording. Source-reading: a drag needs a pointer.
"""
import re
from pathlib import Path

from tests._app_js import app_js_text

ROOT = Path(__file__).resolve().parents[1]


def test_the_board_answers_whether_an_item_is_in_the_pointer():
    js = (ROOT / "frontend/js/whiteboard.js").read_text(encoding="utf-8")
    helper = js[js.index("window.wbMidDrag"):]
    helper = helper[: helper.index("\n")]
    # only the three item drags, and not one Escape already took back
    assert "wbGesture" in helper and ".move" in helper and "cancelled" in helper


def test_leaving_the_page_mid_drag_asks_first():
    js = app_js_text()
    guard = js[js.index('window.addEventListener("beforeunload"'):]
    guard = guard[: guard.index("});")]
    assert "window.wbMidDrag?.() !== true" in guard


def test_the_helper_adds_no_typeof_guard_and_no_global_name():
    # the ratchets (tests/test_global_scope_ratchet.py) stay where they are:
    # a window property is not a top-level name and needs no typeof test
    js = app_js_text()
    assert not re.search(r"typeof wbMidDrag", js)
