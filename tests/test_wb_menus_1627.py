"""INBOX 1627, the owner: "should you turn some of the things in the other whiteboard top bar
menus into sub menus like you did for the arrange one?? like paste should probably be grouped or
the special pastes". The U15 pattern (`data-wb-submenu` sections folded by `wbFoldMenuSubmenus`).
Measured at 1440x900: Edit 785px with a scrollbar to 707px without, Board 785px with a scrollbar
to 576px, Insert 631px to 551px; View unchanged (427px, no scroll, so no Zoom submenu)."""
from tests._app_js import frontend_text
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
WB = frontend_text("whiteboard.js")


def _menu(menu_id: str) -> str:
    start = HTML.index(f'<div id="{menu_id}"')
    return HTML[start : HTML.index('<div class="wb-board-menu-wrap">', start) if '<div class="wb-board-menu-wrap">' in HTML[start:] else len(HTML)]


def _submenu(menu_id: str, name: str) -> str:
    menu = _menu(menu_id)
    start = menu.index(f'data-wb-submenu="{name}"')
    return menu[start : menu.index("</div>", start)]


def test_the_menus_that_scrolled_have_submenus():
    paste = _submenu("wb-edit-menu", "ph:clipboard-text Paste in other ways")
    for cmd in ("paste-special", "paste-into-shape", "paste-no-comments"):
        assert f'data-wb-cmd="{cmd}"' in paste
    assert 'data-wb-cmd="paste" ' in _menu("wb-edit-menu").split("Paste in other ways")[0]
    diagram = _submenu("wb-insert-menu", "ph:flow-arrow Diagram")
    assert 'data-wb-cmd="insert-diagram"' in diagram and 'data-wb-cmd="import-diagram"' in diagram
    shapes = _submenu("wb-insert-menu", "ph:shapes Shapes and icons")
    assert 'data-wb-cmd="open-library"' in shapes and 'data-wb-cmd="insert-sticker"' in shapes
    workshop = _submenu("wb-board-menu", "ph:users-three Workshop")
    assert all(f'data-wb-cmd="{c}"' in workshop for c in ("vote", "clear-votes", "timer"))
    share = _submenu("wb-board-menu", "ph:share-network Share and save")
    for row in ('id="wb-export"', 'id="wb-add-to-note"', 'id="wb-map-to-doc"', 'id="wb-copy-link"', 'data-wb-cmd="save-template"'):
        assert row in share, row


def test_a_board_only_submenu_hides_on_a_map_like_its_section():
    fold = WB[WB.index("function wbFoldMenuSubmenus(menu)") :]
    fold = fold[: fold.index("\n}\n")]
    assert "group.dataset.wbSurface = section.dataset.wbSurface" in fold
    assert 'data-wb-submenu="ph:users-three Workshop" data-wb-submenu-title="Vote dots and a timer" data-wb-surface="board"' in HTML
