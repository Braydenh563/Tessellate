"""The phone's More sheet groups the Arrange rows like the desktop menu (L-whiteboard-30).

`WB_MORE_ARRANGE_GROUPS` (whiteboard-commands.js) names the submenus; this holds it to
the desktop Arrange menu's own `data-wb-submenu` sections, so the two cannot drift.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMMANDS = (ROOT / "frontend" / "js" / "whiteboard-commands.js").read_text(encoding="utf-8")
INDEX = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")


def _js_groups() -> list[tuple[str, list[str]]]:
    start = COMMANDS.index("const WB_MORE_ARRANGE_GROUPS = [")
    block = COMMANDS[start : COMMANDS.index("\n  ];\n", start)]
    return [
        (m.group(1), re.findall(r'"([\w-]+)"', m.group(2)))
        for m in re.finditer(r'label: "([^"]+)", ids: \[([^\]]*)\]', block)
    ]


def _desktop_groups() -> list[tuple[str, list[str]]]:
    start = INDEX.index('id="wb-arrange-menu"')
    end = INDEX.index('id="wb-view-menu"', start)
    out = []
    for m in re.finditer(r'data-wb-submenu="([^"]+)".*?\n(.*?)\n\s*</div>', INDEX[start:end], re.S):
        out.append((m.group(1), re.findall(r'data-wb-cmd="([\w-]+)"', m.group(2))))
    return out


def test_phone_groups_mirror_the_desktop_submenus() -> None:
    js = _js_groups()
    desktop = _desktop_groups()
    assert len(desktop) >= 5
    assert [label for label, _ in js] == [label for label, _ in desktop]
    for (label, ids), (_, want) in zip(js, desktop):
        assert set(want) <= set(ids), f"{label}: the desktop's rows are missing from the phone group"


def test_every_grouped_id_is_a_board_command() -> None:
    for _, ids in _js_groups():
        for cid in ids:
            assert f'{{ id: "{cid}"' in COMMANDS, cid


def test_the_sheet_folds_them_and_hides_empty_groups() -> None:
    assert "foldArrange(menu);" in COMMANDS
    assert "buildMenuGroupButton" in COMMANDS[COMMANDS.index("function foldArrange") :]
    assert ".menu-group" in COMMANDS[COMMANDS.index("function wbSyncMoreMenu") :]
