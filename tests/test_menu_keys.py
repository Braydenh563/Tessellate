"""Menu keys the menus.js sweep found broken (L-world-class-875).

Each was measured in the running app (scratchpad/ui-sweeps/menus.js at 1440,
light): these pin the shape of each fix so it cannot quietly come back. The submenu-row
and Answer length fixes landed on the base as well and are pinned by
tests/test_menu_keys_1440.py.
"""

from __future__ import annotations

from tests._app_js import app_js_text


def _body(name: str) -> str:
    text = app_js_text()
    at = text.index(name)
    return text[at : at + 4000]


def test_a_select_row_in_an_open_menu_leaves_the_arrows_to_the_menu():
    """↓ on Sort and view's sort select walks the menu; it used to open the list too, orphaned by Escape."""
    body = _body("APG select-only combobox")
    guard = body.index('opener.closest(".doc-dock-menu-list, [role=\'menu\']")')
    assert guard < body.index("opener.click();"), "the menu-row guard must come before the select opens"
