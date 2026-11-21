"""L-chat-24: the phone's More sheet groups the arrange commands like the desktop menu.

The Arrange menu is five submenus (CHAT_PLAN U15: Order, Align, Distribute,
size and flip, Tidy and connect, Group and lock). The sheet used to list the
same commands flat; it now builds the same five groups, in the same order,
through `kebabMenu`'s `items` rows (`buildMenuGroupButton`).
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMMANDS = (ROOT / "frontend" / "js" / "whiteboard-commands.js").read_text(encoding="utf-8")
INDEX = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")


def _desktop() -> list[tuple[str, list[str]]]:
    menu = INDEX[INDEX.index('id="wb-arrange-menu"') :]
    menu = menu[: menu.index("</div>\n        </div>")]
    out = []
    for section in re.split(r'<div class="wb-menu-section" data-wb-submenu="', menu)[1:]:
        label = section[: section.index('"')]
        out.append((label, re.findall(r'data-wb-cmd="([\w-]+)"', section)))
    return out


def _sheet() -> list[tuple[str, list[str]]]:
    block = COMMANDS[COMMANDS.index("const WB_ARRANGE_GROUPS = [") :]
    block = block[: block.index("\n];\n")]
    return [
        (m.group(1), re.findall(r'"([\w-]+)"', m.group(2)))
        for m in re.finditer(r'\{ label: "([^"]+)", ids: \[([^\]]*)\] \}', block)
    ]


def test_the_sheet_has_the_desktops_five_groups_in_its_order() -> None:
    desktop = _desktop()
    assert [name for name, _ in desktop] == [
        "ph:stack Order",
        "ph:align-left Align",
        "ph:columns Distribute, size and flip",
        "ph:tree-structure Tidy and connect",
        "ph:link Group and lock",
    ]
    assert _sheet() == desktop


def test_every_grouped_command_is_in_the_table_and_the_sheet_builds_groups() -> None:
    table = set(re.findall(r'\{ id: "([\w-]+)"', COMMANDS))
    for _, ids in _sheet():
        assert set(ids) <= table
    body = COMMANDS[COMMANDS.index("function wbMoreMenuItems(") :]
    body = body[: body.index("\n}\n")]
    assert "items: group.ids.map(" in body
    assert "wbMoreMenuItems()" in COMMANDS[COMMANDS.index("function wbInitMoreMenu(") :]
