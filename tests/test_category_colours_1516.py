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
