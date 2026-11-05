"""A throw never scrolls the page, and its landing reads before it writes (INBOX 1634).

The owner: "also when I try to throw the companion, the page scrolls", with a
lag log whose landing (`spotNow`) paid 9576ms of forced layout. Measured with
a 4,000-paragraph dashboard at 4x CPU (scratchpad, throw trace): a landing
forced three whole-page layouts (the placement's own read, then the ride
band's `clientLeft`/`clientWidth` and `Put`'s `scrollTop` after the ride's
writes), one after `nmb.place.client`.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AV = (ROOT / "frontend" / "js" / "avatars.js").read_text()
DRAG_EDGE = (ROOT / "frontend" / "js" / "drag-edge.js").read_text()


def _fn(name: str) -> str:
    start = AV.index(f"function {name}(")
    return AV[start : AV.index("\n}\n", start)]


def test_the_placement_reads_a_scrollers_client_box_with_its_rect() -> None:
    read = AV[AV.index("  read(spot) {") : AV.index("\n  },\n};", AV.index("  read(spot) {"))]
    assert "scroller.clientLeft" in read and "scroller.clientWidth" in read and "scroller.scrollTop" in read
    # The ride band and Put answer from it, never from the element after a write.
    assert "r.el.scrollTop" not in _fn("nameMarkBuddyPut") and "r.el.clientLeft" not in _fn("nameMarkBuddyRideBox")
    assert "r.el.scrollTop" not in _fn("nameMarkBuddyRideBox")
    assert "nmb.place.client(r.el)" in _fn("nameMarkBuddyPut")


def test_a_keyboard_on_the_figure_never_scrolls_the_page() -> None:
    assert "Page(Up|Down)|Home|End" in AV
    assert "if (step && plain) event.preventDefault();" in AV


def test_a_wheel_over_it_while_carried_or_flying_scrolls_nothing() -> None:
    assert "if (nmb.grabbed || nmb.flight) return event.preventDefault();" in AV


def test_the_edge_scroll_stays_off_the_companions_drag() -> None:
    assert re.search(r'closest\?\.\("#nm-buddy"\)', DRAG_EDGE)
