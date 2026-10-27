"""Every menu keeps the keyboard contract (INBOX 403, the menu pass).

Measured by `scratchpad/ui-sweeps/menus.js` at 1440, before these held: every
enhanced select and every Library card menu opened with the focus on `body`,
select lists ignored ArrowDown, Escape in a Settings select closed Settings
and left the list floating, and the twenty-odd `details` dock menus and the
board's menus had no arrow keys at all. The sweep needs a browser; these are
the source-level ratchets on each cause, so a rewrite that drops one fails
here before anyone has to open a menu to find out.
"""

from __future__ import annotations

import re
from pathlib import Path
from tests._app_js import app_js_text

ROOT = Path(__file__).resolve().parents[1]
APP = app_js_text()
SETTINGS = (ROOT / "frontend" / "js" / "settings.js").read_text(encoding="utf-8")
BOARD = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")


def _function(text: str, signature: str) -> str:
    start = text.index(signature)
    end = text.index("\n}\n", start)
    return text[start:end]


def test_a_select_list_is_walked_by_the_menu_keys() -> None:
    body = _function(APP, "function wireMenuKeyboard(")
    assert 'role="option"' in body, (
        "wireMenuKeyboard walks menuitems only again: every enhanced select "
        "(a listbox of options) loses ArrowDown and its own Escape"
    )


def test_the_menu_owns_its_escape() -> None:
    body = _function(APP, "function wireMenuKeyboard(")
    escape = body[body.index('event.key === "Escape"'):]
    assert "stopPropagation()" in escape, (
        "Escape in a menu reaches the document handler too, which closes "
        "whatever holds the menu (Settings) and leaves the list floating"
    )


def test_moving_a_menu_does_not_drop_its_focus() -> None:
    body = _function(APP, "function wireEscapedActionMenu(")
    assert "const held = menu.contains(document.activeElement)" in body, (
        "the escape-to-body move no longer holds the focus: every select and "
        "Library ⋯ opens with document.activeElement on body"
    )
    assert body.count("held") >= 4, "held on the way out and handed to the opener on the way home"


def test_closing_a_focused_menu_hands_the_focus_back() -> None:
    body = _function(APP, "function closeActionMenus(")
    # The opener, or the element a point-opened menu names (`_returnFocusTo`).
    assert "back.focus(" in body and "_returnFocusTo" in body and ": opener;" in body, "a menu closed with the focus inside it drops it to body"


def test_details_menus_and_markup_menus_answer_the_arrows() -> None:
    for name in ("function menuRowsOf(", "function menuOfOpener(", "DETAILS_MENU_OPEN"):
        assert name in APP, f"{name} is gone: dock menus lose ArrowDown, Home and End"
    assert re.search(r'DETAILS_MENU_OPEN = "details\[open\]:is\(\.dock-menu, \.doc-dock-menu\)"', APP), (
        "Escape closes only `.dock-menu`s again; the document's own ⋯ and the "
        "editor toolbars' menus are `.doc-dock-menu` without it"
    )
    assert "!insideClosedDetails(el)" in _function(APP, "function menuRowsOf("), (
        "a control inside a closed `details` keeps a layout box; without this "
        "the walk lands on it (the Graph's folded View at 1024) and stops"
    )
    assert 'menu.dataset.menuKeys = "1"' in APP, (
        "a menu wired by wireMenuKeyboard must be marked, or the delegated "
        "walker moves two rows per key in it"
    )


def test_settings_closes_its_open_menus_with_itself() -> None:
    body = _function(SETTINGS, "function closeSettingsModal(")
    assert "closeActionMenus()" in body


def test_the_board_shape_tool_opens_from_the_keyboard() -> None:
    start = BOARD.index("function wbWireToggleGestures(")
    body = BOARD[start:start + 6000]
    assert 'toggle.setAttribute("aria-controls", menu.id)' in body
    assert 'e.key !== "ArrowDown" && e.key !== "ArrowUp"' in body, (
        "the shape tool's split button has no keyboard way into its menu"
    )
    assert "wbCloseDockedMenu(menu, toggle)" in body[body.index('e.key !== "Escape"'):], (
        "Escape in the shapes must close them itself: wireMenuKeyboard closes "
        "action menus only, and it stops the key"
    )
