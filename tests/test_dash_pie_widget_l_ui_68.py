"""Source text: the dashboard's pie widget draws in a browser; the source pins
its registry entry, its data and its accessible name (L-ui-modernisation-68).

Notes by category as a donut: the five biggest categories and Other, each
slice in the category's own dot colour, a share bar per slice under it that
opens that category's notes.
"""

from __future__ import annotations

from tests._app_js import frontend_text


def _render() -> str:
    source = frontend_text("dashboard.js")
    start = source.index("renderCategoriesWidget.pie = async function (body)")
    return source[start : source.index("\n};\n", start)]


def test_the_pie_is_a_dashboard_widget():
    source = frontend_text("dashboard.js")
    assert 'pie: { title: "ph:chart-pie Notes by category"' in source


def test_slices_use_the_category_colour_and_name_their_shares():
    body = _render()
    assert "fetchDashStats()" in body and "categoryDotColour(" in body
    assert 'setAttribute("role", "img")' in body and "aria-label" in body
    assert '"Other"' in body and "stroke-dasharray" in body
    assert "showCategoryNotes(" in body
