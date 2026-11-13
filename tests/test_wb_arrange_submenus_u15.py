"""The board's Arrange menu is five submenus, not 25 rows (INBOX 1564, U15).

The owner, 2026-11-03: "I think it is a good idea to make it subsectioned
yeah". The rows stay in the markup under `data-wb-submenu` sections (every
`data-wb-cmd` row and its shortcut keycap, so `WB_COMMANDS` and the lints that
read index.html see what they always saw); `wbFoldArrangeMenu` moves each
section's rows into the menu recipe's own `buildMenuGroupButton` at boot.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests._help_text import help_core_text

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
BOARD = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")
HELP = help_core_text()
DESIGN = (ROOT / "docs" / "DESIGN.md").read_text(encoding="utf-8")


def _arrange() -> str:
    block = INDEX[INDEX.index('id="wb-arrange-menu"') :]
    return block[: block.index('<div class="wb-board-menu-wrap">')]


def test_arrange_is_five_named_submenus_holding_every_row() -> None:
    block = _arrange()
    sections = re.findall(r'<div class="wb-menu-section" data-wb-submenu="ph:([a-z-]+) ([^"]+)"', block)
    assert [name for _, name in sections] == ["Order", "Align", "Distribute, size and flip", "Tidy and connect", "Group and lock"]
    assert len(re.findall(r'data-wb-cmd="', block)) == 29  # 28 + Loop on the shape (L439: the Guide names it under Arrange)
    assert "wb-panel-group-label" not in block, "the trigger names the group; a label over it says it twice"


def test_the_arrange_row_the_guide_names_is_in_the_menu() -> None:
    """Source text: the Guide and the Format panel's help say "Arrange, Loop on the shape"; the sweep that presses the
    menu (scratchpad/ui-sweeps/helpaudit.js, L439) found no such row, only the Ctrl+K command. The row is in the
    "Tidy and connect" flyout, named as the command's own `menu` word."""
    block = _arrange()
    assert re.search(r'data-wb-cmd="loop"[^>]*>.*?<span>Loop on the shape</span>', block)
    assert block.index('data-wb-cmd="loop"') > block.index("Tidy and connect")
    assert block.index('data-wb-cmd="loop"') < block.index("Group and lock")


def test_every_arrange_row_keeps_its_keycap() -> None:
    block = _arrange()
    for keys in ("]", "[", "Ctrl+]", "Ctrl+[", "Ctrl+G", "Ctrl+Shift+G", "Ctrl+Shift+L", "Shift+H", "Shift+V"):
        assert f"<kbd>{keys}</kbd>" in block, keys


def test_the_board_folds_them_with_the_menu_recipe_and_not_a_second_builder() -> None:
    fold = BOARD[BOARD.index("function wbFoldMenuSubmenus(") :]
    fold = fold[: fold.index("\n}\n")]
    assert "buildMenuGroupButton(" in fold
    assert "[data-wb-submenu]" in fold
    #: A flyout is a `.wb-board-menu` too, so the delegated row click, the
    #: outside-click test and the menu looks all find its rows.
    assert '"wb-board-menu"' in fold
    assert "wbFoldMenuSubmenus(menu)" in BOARD


def test_closing_the_menu_closes_its_flyouts_and_a_nested_level() -> None:
    close = BOARD[BOARD.index("const closeAllWbMenus = () => {") :]
    close = close[: close.index("\n  };")]
    assert "menu-group-open" in close
    assert ".submenu" in close


def test_escape_in_a_flyout_closes_the_flyout_first() -> None:
    handler = BOARD[BOARD.index("In a flyout (or a nested level) Escape") :][:400]
    assert 'closest(".submenu.wb-board-menu:not(.hidden)")' in handler


def test_a_nested_level_hides_the_boards_other_rows() -> None:
    css = "".join(p.read_text(encoding="utf-8") for p in (ROOT / "frontend" / "css").glob("*.css"))
    #: 2026-11-03: menus.js marks the open group's own menu `.menu-nested`, a board menu too, so the
    #: rule needs no `:has()` anchor with a universal child (test_tab_entry_cost). Same intent.
    assert ".wb-board-menu.menu-nested > :not(.menu-group-open)" in css
    assert 'parentElement.classList.add("menu-nested")' in (ROOT / "frontend" / "js" / "menus.js").read_text(encoding="utf-8")


def test_help_and_the_recipe_say_so() -> None:
    assert "Arrange opens as submenus" in HELP
    assert "Arrange menu" in DESIGN and "wbFoldMenuSubmenus" in DESIGN

