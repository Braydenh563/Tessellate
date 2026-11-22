"""Menu keys the menus.js sweep found broken (L-world-class-875).

Each was measured in the running app (scratchpad/ui-sweeps/menus.js at 1440,
light): these pin the shape of each fix so it cannot quietly come back.
"""

from __future__ import annotations

import re

from tests._app_js import app_js_text


def _body(name: str) -> str:
    text = app_js_text()
    at = text.index(name)
    return text[at : at + 4000]


def test_a_submenu_row_is_not_taken_for_a_closed_menu_button():
    """↓ on a submenu's row walks on: the opener rule used to click it open and refocus it."""
    text = app_js_text()
    m = re.search(r'const opener = target\.closest\("([^"]+)"\);', text)
    assert m, "navigation.js's arrow-key opener rule is gone"
    assert "[role='menuitem']" in m.group(1), "a role=menuitem row with aria-haspopup must not count as an opener"


def test_a_select_row_in_an_open_menu_leaves_the_arrows_to_the_menu():
    """↓ on Sort and view's sort select walks the menu; it used to open the list too, orphaned by Escape."""
    body = _body("APG select-only combobox")
    guard = body.index('opener.closest(".doc-dock-menu-list, [role=\'menu\']")')
    assert guard < body.index("opener.click();"), "the menu-row guard must come before the select opens"


def test_both_answer_length_pickers_are_painted_when_their_surface_is_built():
    """Ask's picker is on the Notes surface: painted only with Chat's, it opened with no rows."""
    body = _body("const loadResponseModes")
    assert re.search(r'for \(const surface of \["chat", "notes"\]\) onSurface\(surface, paint\)', body)
