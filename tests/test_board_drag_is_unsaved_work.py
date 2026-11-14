"""A board mid-drag is unsaved work (L-world-class-97, WORLD_CLASS_PLAN 22.1.4).

A card, box or shape held in the pointer is only written when it is released, so
a reload or a closed window in that moment loses the move. The board asks the
browser to confirm the leave from the gesture it already tracks (`wbGesture`,
the one Escape puts back). Source-reading: a drag needs a pointer.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _guard():
    js = (ROOT / "frontend/js/whiteboard.js").read_text(encoding="utf-8")
    start = js.index('window.addEventListener("beforeunload"')
    return js[start : js.index("\n", start)]


def test_leaving_the_page_mid_drag_asks_first():
    guard = _guard()
    assert "event.preventDefault()" in guard


def test_only_an_item_in_the_pointer_counts_and_not_one_escape_took_back():
    guard = _guard()
    assert "wbGesture?.move" in guard and "wbGesture.cancelled" in guard
