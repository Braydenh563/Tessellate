"""INBOX 1672, the owner at 680 wide: "it looks like it is faded out on the
right but it isnt scrollable". Below 820 every status item is a 44px target,
so the bar needed 649px with nothing optional showing and about 750 with the
clock, with `overflow: visible`: Redo ran past the edge and the edge fade said
"scroll" over it. Measured after, 600 to 820 with and without the clock
(scratchpad probe statusfade5.js): Redo ends 8px inside the bar, no fade."""

from __future__ import annotations

import re
from pathlib import Path

from tests._app_js import app_js_text

ROOT = Path(__file__).resolve().parents[1]


def _fn(name: str) -> str:
    js = app_js_text()
    start = js.index(f"function {name}(")
    return js[start : js.index("\n}\n", start)]


def test_only_a_strip_that_scrolls_is_faded() -> None:
    body = _fn("syncEdgeFade")
    assert "getComputedStyle(bar).overflowX" in body
    assert re.search(r'overflow === "auto" \|\| overflow === "scroll" \? bar\.scrollWidth - bar\.clientWidth : 0', body)


def test_the_status_bar_sheds_optional_items_in_order() -> None:
    body = _fn("syncEdgeFade")
    assert '["status-clock", "status-lan", "status-tray"]' in body
    # every pass starts from all shown, then sheds in order while it overflows
    assert "item.hidden = false" in body
    assert "bar.scrollWidth > bar.clientWidth" in body
    assert "item.hidden = true" in body
    # an item already hidden frees nothing, so it is not counted as shed
    assert '!item.classList.contains("hidden")' in body
    # a bar that scrolls (under 400) sheds nothing
    # and one that started scrolling gets back what it shed at a wider size
    assert re.search(r'item\.hidden = false;\s*if \(overflow === "visible"\)', body)


def test_the_fit_is_told_by_an_observer_not_a_timer() -> None:
    # the edge-fade observer the bar already has, also watching its zones
    # (an item showing changes a zone's width, not the bar's)
    body = _fn("edgeFadeWire")
    assert 'bar.querySelectorAll("[data-status-zone]")' in body
    assert "seen.observe(box)" in body


def test_a_shed_item_is_not_drawn() -> None:
    # the hidden attribute, which `[hidden] { display: none !important; }` covers
    css = (ROOT / "frontend/css/02-chat-graph.css").read_text(encoding="utf-8")
    assert re.search(r"\[hidden\] \{\s*display: none !important;", css)
