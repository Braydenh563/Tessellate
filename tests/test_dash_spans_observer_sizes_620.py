"""L-world-class-620: the dashboard's spans come from the ResizeObserver's own sizes.

Before: `sizeDashWidgets` read every card's rect after the widget fills had dirtied the layout
(49 to 307ms at 4x, 500 notes). The observer already measured each card in the frame's layout.
"""

from __future__ import annotations

from tests._app_js import frontend_text


def _body(name: str) -> str:
    text = frontend_text("dashboard.js")
    start = text.index(f"function {name}(")
    return text[start:text.index("\n}\n", start)]


def test_the_observer_records_each_cards_border_box():
    body = _body("watchDashWidgets")
    assert "new ResizeObserver((entries) => {" in body
    assert "sizeDashWidgets.heights.set(entry.target, entry.borderBoxSize?.[0]?.blockSize" in body


def test_the_sizing_reads_the_recorded_height_before_any_rect():
    body = _body("sizeDashWidgets")
    assert "sizeDashWidgets.heights.get(card) || card.getBoundingClientRect().height" in body
    #: The reads still all go before the first write (INBOX 400, 1591).
    assert body.index("sizeDashWidgets.heights.get(card)") < body.index("card.style.gridRowEnd")


def test_the_grid_metrics_are_read_in_the_observer_where_style_is_clean():
    watch = _body("watchDashWidgets")
    callback = watch[watch.index("new ResizeObserver((entries) => {"):]
    assert callback.index("sizeDashWidgets.metrics = sizeDashWidgets.read(grid);") < callback.index("dashResizeObserver.follow?.();")
    size = _body("sizeDashWidgets")
    assert "sizeDashWidgets.metrics || sizeDashWidgets.read(grid)" in size
    assert "getComputedStyle(" not in size
