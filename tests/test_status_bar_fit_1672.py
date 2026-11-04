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
    js = app_js_text()
    assert 'const STATUS_SHED = ["status-clock", "status-lan", "status-tray"];' in js
    body = _fn("fitStatusBar")
    assert 'classList.remove("status-shed")' in body
    assert "bar.scrollWidth <= bar.clientWidth" in body
    # an item already hidden frees nothing, so it is not counted as shed
    assert '!item.classList.contains("hidden")' in body
    # a bar that scrolls (under 400) sheds nothing
    assert 'overflowX !== "visible"' in body


def test_the_fit_is_told_by_an_observer_not_a_timer() -> None:
    js = app_js_text()
    assert "new ResizeObserver(fitStatusBar)" in js
    assert 'querySelectorAll("[data-status-zone]")) fit.observe(zone)' in js


def test_a_shed_item_is_not_drawn() -> None:
    css = (ROOT / "frontend/css/10-responsive.css").read_text(encoding="utf-8")
    assert re.search(r"#status-bar \.status-item\.status-shed \{\s*display: none;", css)
