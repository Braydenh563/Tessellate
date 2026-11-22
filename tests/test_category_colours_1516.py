"""INBOX 1516 (a): a category colour chosen redraws the dashboard and the map
without asking the layout engine whether they are showing.

`categoryColoursChanged` (notes-list.js) dispatches synchronously inside the
categories fetch's continuation; the listeners asked `checkVisibility()`, which
flushes layout the sidebar rewrite had just dirtied: 10 to 28 ms on the
dashboard at 1x (measured with a dirtied layout, 6 runs), 0.02 ms by the page's
`hidden` class. The redraw itself waits two frames (`afterFrames`).
"""

from tests._app_js import frontend_text


def _listener(js: str) -> str:
    start = js.index('document.addEventListener("categorycolours"')
    return js[start : js.index("});", start)]


def test_the_dashboard_asks_its_page_class_and_redraws_after_the_frames():
    body = _listener(frontend_text("dashboard.js"))
    assert 'classList.contains("hidden")' in body and "afterFrames(renderDashboard)" in body
    assert "checkVisibility" not in body


def test_the_graph_asks_its_page_class_and_redraws_after_the_frames():
    body = _listener(frontend_text("graph.js"))
    assert 'getElementById("tab-graph")' in body and "afterFrames(renderGraph)" in body
    assert "checkVisibility" not in body


def test_the_dashboard_waits_for_its_first_draw_before_a_colour_redraws_it():
    """L603: categories load while the opening render is on its way, and a second
    full render 80 ms later threw the first away (every widget fetched and built
    twice at boot). Counted by its guard; the boot sweep measured the renders."""
    body = _listener(frontend_text("dashboard.js"))
    assert body.index("window.dashSettled") < body.index("afterFrames(renderDashboard)")
