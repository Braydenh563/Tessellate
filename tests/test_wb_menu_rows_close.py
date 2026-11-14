"""The Board menu's action rows close the menu when they are pressed.

Its `wb-menu-item` rows close it through the delegated listener in
`whiteboard.js`; the six action rows drawn as `ghost small` buttons inside a
`.wb-menu-row` (Export, Clear, Add to a note, Map to document, Copy app link,
Delete) did not, so the menu stood open over what they opened. At 390 wide the
menu (z-index 1020, fixed) covers the middle of the dialog or the note picker
(z-index 1010) the row had just opened, and the picker's first row could not be
pressed: Playwright reported the menu "intercepts pointer events"
(`scratchpad/ui-sweeps/noteobject.js`, W=390 PHONE=1). Rename and New board were
fixed the same way by taking the `wb-menu-item` class (see the listener's own
comment); these rows are a label and a button, so they carry `data-wb-closes`.
"""
import re
from pathlib import Path

from tests._css_paths import CSS_FILES

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
WHITEBOARD = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")

#: Rows that do something once and are done with the menu. A switch or a
#: stepper in the same menu (grid size, the panels) must stay open, so this is
#: a list and not "every button in a row".
ACTION_ROWS = (
    "wb-export",
    "wb-clear-board",
    "wb-add-to-note",
    "wb-map-to-doc",
    "wb-board-to-doc",
    "wb-copy-link",
    "wb-delete-board",
)


def _button(button_id: str) -> str:
    match = re.search(rf'<button[^>]*\bid="{button_id}"[^>]*>', INDEX)
    assert match, f"#{button_id} is not in index.html"
    return match.group(0)


def test_every_action_row_in_the_board_menu_says_it_closes_the_menu():
    for button_id in ACTION_ROWS:
        assert "data-wb-closes" in _button(button_id), f"#{button_id} leaves the Board menu open behind what it opens"


def test_the_delegated_listener_closes_the_menu_for_those_rows():
    listener = re.search(r'const item = e\.target\.closest\("([^"]+)"\)', WHITEBOARD)
    assert listener, "the Board menu's delegated click listener moved"
    assert ".wb-board-menu [data-wb-closes]" in listener.group(1)


# The Board and View menus: section heads, plain icon rows, delete last and red; the View menu in two columns (INBOX 793).


def _menu(html: str, menu_id: str) -> str:
    start = html.index(f'<div id="{menu_id}"')
    return html[start : html.index('<input type="file" id="wb-bg-image-input"', start) if menu_id == "wb-view-menu" else html.index('<span class="wb-topbar-divider"', start)]


def test_the_board_menu_is_section_heads_and_plain_icon_rows_with_delete_last_and_red():
    """INBOX 793: no "label ... action" rows ("This board itself ... Delete")."""
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    menu = _menu(html, "wb-board-menu")
    assert "wb-menu-row" not in menu and "wb-panel-danger" not in menu
    heads = re.findall(r'wb-panel-group-label">([^<]+)<', menu)
    assert heads == ["Boards", "This board", "Help", "Remove"]
    for button_id in ("wb-export", "wb-board-kind", "wb-add-to-note", "wb-map-to-doc",
    "wb-board-to-doc", "wb-map-study", "wb-copy-link", "wb-clear-board", "wb-delete-board"):
        assert re.search(rf'<button id="{button_id}"[^>]*class="wb-menu-item', menu), button_id
    rows = re.findall(r'<button[^>]*id="(wb-[a-z-]+)"[^>]*>', menu)
    assert rows[-1] == "wb-delete-board", "what destroys is last"
    assert menu.count("wb-menu-danger") == 2


def test_the_view_menu_is_two_columns_parted_by_hairlines():
    """The map's View menu measured 785px in one column under four printed
    heads (`mapviewmenu.js` holds it to 450): two columns, Panels and Zoom
    beside Canvas and Map, the groups parted by a hairline, not a heading."""
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    menu = _menu(html, "wb-view-menu")
    assert 'class="wb-board-menu wb-menu-two-col hidden"' in menu
    groups = re.findall(r'role="group" aria-label="([^"]+)"', menu)
    assert groups == ["Panels", "Zoom", "Canvas", "Map"]
    assert menu.count('<div class="wb-menu-col">') == 2
    assert "wb-panel-group-label" not in menu
    css = "\n".join(p.read_text(encoding="utf-8") for p in CSS_FILES)
    assert ".wb-board-menu.wb-menu-two-col {" in css and ".wb-menu-two-col > .wb-menu-col + .wb-menu-col {" in css
    lazy = (ROOT / "frontend" / "css" / "library-lazy.css").read_text(encoding="utf-8")
    assert ".wb-board-menu :is(.wb-menu-item, .wb-menu-row) {\n  min-height: max(2.25rem, var(--target-min));" in lazy
    assert ".wb-board-menu .wb-menu-item.wb-menu-danger" in lazy
