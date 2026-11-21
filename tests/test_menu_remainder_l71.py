"""L-general-71: what scratchpad/ui-sweeps/menus.js left on the 5k showcase after the keyboard pass.

The sweep needs a browser; these are the source-level ratchets on each cause (numbers are the sweep's, 1440 unless
said): a switch row in a dock menu stood 34.5px against the buttons' 32 and drew its icon 34px right of theirs; a
board submenu row's icon box was 15.6px against 19.5; Escape with a select's list open closed the menu and left the
list at <body>; Answer length was empty until the Chat pane had been built; the zoom list was 200px for 80px of
content; the sheet's long rows ended in an ellipsis at 390."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS = ROOT / "frontend" / "css"
JS = ROOT / "frontend" / "js"


def _rule(text: str, selector: str) -> str:
    return re.search(re.escape(selector) + r"\s*\{([^}]*)\}", text).group(1)


def test_a_switch_row_in_a_dock_menu_is_a_menu_row() -> None:
    css = (CSS / "08-consistency.css").read_text(encoding="utf-8")
    row = _rule(css, ".doc-dock-menu-list .dock-menu-check")
    assert "min-height: var(--control-h-lg)" in row
    assert "padding-block: 0" in _rule(css, "#settings-modal .settings-section .doc-dock-menu-list .dock-menu-check")
    assert "width: 1.25em" in _rule(css, ".doc-dock-menu-list .dock-menu-check > .ph-lead")
    assert "order: 1" in _rule(css, ".doc-dock-menu-list .dock-menu-check > input")
    # the menu-item recipe (padding, flex, floor) names the switch row beside the button row
    assert css.count("  .dock-menu-check,\n") >= 2


def test_a_board_submenu_row_has_the_command_rows_icon_box() -> None:
    css = (CSS / "08-consistency.css").read_text(encoding="utf-8")
    assert ":is(.action-menu, .doc-dock-menu-list, .wb-board-menu)\n  .menu-item > span:first-child > .ph:first-child" in css


def test_escape_leaves_a_selects_open_list_to_close_first() -> None:
    nav = (JS / "navigation.js").read_text(encoding="utf-8")
    body = nav[nav.index("const DETAILS_MENU_OPEN"):]
    body = body[: body.index("true\n);")]
    assert 'document.querySelector(".action-menu:not(.hidden)")' in body
    assert body.index("closeActionMenus()") < body.index("open.open = false")


def test_answer_length_is_filled_when_notes_is_built() -> None:
    chat = (JS / "chat.js").read_text(encoding="utf-8")
    assert 'onSurface("notes", paint);' in chat and 'onSurface("chat", paint);' in chat


def test_the_zoom_list_is_as_wide_as_its_numbers() -> None:
    js = (JS / "value-field.js").read_text(encoding="utf-8")
    assert '.classList.add("value-field-list")' in js
    assert 'group: p.run ? "run" : "value"' in js
    assert "min-width: 0" in _rule((CSS / "value-field.css").read_text(encoding="utf-8"), ".action-menu.value-field-list")


def test_a_sheet_row_wraps_instead_of_ending_in_an_ellipsis() -> None:
    css = (CSS / "10-responsive.css").read_text(encoding="utf-8")
    rule = _rule(css, ".action-menu-card .action-menu .menu-item .ph-text")
    assert "white-space: normal" in rule and "text-overflow: clip" in rule


def test_the_sweep_does_not_call_a_dialog_opener_or_a_lifted_list_a_finding() -> None:
    sweep = (ROOT / "scratchpad" / "ui-sweeps" / "menus.js").read_text(encoding="utf-8")
    assert "select-opener:not([aria-haspopup=\"dialog\"])" in sweep
    assert "wbLiftMenuOffOptionsBar" in sweep
    assert "Math.max(m.natural, m.op.r - m.op.l)" in sweep
