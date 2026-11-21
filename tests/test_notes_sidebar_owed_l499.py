"""The Notes tab's category list is drawn when the tab is shown (L499).

`renderSidebar` skips a hidden Notes tab and marked the debt on the list's own
`data-stale`. A page of notes arriving behind the dashboard drew the list and
cleared that flag, so the category list it skipped stayed empty when Notes was
opened by its tab (the README's palette shot, 2026-11-21: 0 rows, 13 by URL).
The sidebar now owes its own debt and both payers read it.
"""

from __future__ import annotations

import re

from tests._app_js import app_js_text


def _body(js: str, name: str) -> str:
    start = js.index(f"function {name}(")
    return js[start : js.index("\n}\n", start)]


def test_a_hidden_tab_owes_the_sidebar_and_a_draw_pays_it():
    body = _body(app_js_text(), "renderSidebar")
    hidden = body.index('classList.contains("hidden")')
    owed = body.index("window.notesSidebarOwed = true", hidden)
    assert owed < body.index("return;", hidden)
    assert "window.notesSidebarOwed = false" in body[owed + 1 :]


def test_both_payers_read_the_sidebar_debt():
    js = app_js_text()
    assert re.search(r'dataset\.stale \|\| window\.notesSidebarOwed\)\) renderSidebar\(\)', _body(js, "renderEntries"))
    assert 'name === "notes" && ($("entry-list").dataset.stale || window.notesSidebarOwed)) renderEntries()' in js
