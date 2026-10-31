"""The dashboard's masonry spans are never measured while the tab is hidden (dashcls-1031).

A ResizeObserver also fires when the grid goes `display: none` (a tab switch):
every card measured 0px, was given `span 1`, and the next visit painted the
cards stacked on 8px rows before the spans were put right a frame or two
later. Layout shift on a revisit, measured by a PerformanceObserver over five
revisits: 0.34 before.
"""

from tests._app_js import frontend_text


def _fn(text: str, name: str) -> str:
    start = text.index(f"function {name}(")
    return text[start : text.index("\n}\n", start)]


def test_sizing_waits_for_a_visible_grid():
    body = _fn(frontend_text("dashboard.js"), "sizeDashWidgets")
    guard = body.index("checkVisibility")
    assert guard < body.index("getBoundingClientRect"), "measure only a laid-out grid"
    assert guard < body.index('style.gridRowEnd = "span 1"'), "never release spans of a hidden grid"


def test_the_digest_widget_is_drawn_only_when_its_day_lines_are():
    text = frontend_text("dashboard.js")
    start = text.index("async function renderDigestWidget(")
    body = text[start : text.index("\n}\n", start)]
    assert "const dayDrawn = renderDayDigest(dayBox);" in body
    assert body.rstrip().endswith("await dayDrawn;"), "resolving early left a short card that grew a fetch later"
