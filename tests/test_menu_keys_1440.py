"""Menu keys found by scratchpad/ui-sweeps/menus.js at 1440 (the hub's order on PR 223).

Escape in Logs' More, with its "Which log" list open inside it, closed the dock menu and left
the list on screen; the next Escape closed Settings. ArrowDown on the dashboard Customise's
View row opened its flyout instead of moving on. The board's two-column View menu walked no
rows and returned before its Escape. The board's zoom list was 200px wide for 80px of values,
and the Ask box's Answer length list was empty until Chat had been opened.
"""

import re
from pathlib import Path

from tests._app_js import app_js_text
from tests._css_paths import FORMER_08, sheets

ROOT = Path(__file__).resolve().parents[1]
JS = app_js_text()
CSS = sheets(*FORMER_08)


def _body(head: str, length: int = 3000) -> str:
    at = JS.find(head)
    assert at >= 0, f"{head} moved"
    return JS[at : at + length]


def test_escape_closes_the_innermost_popup_first_and_focus_returns_to_its_opener():
    block = _body("const open = document.querySelector(DETAILS_MENU_OPEN);", 1200)
    inner = block.find('.action-menu:not(.hidden)')
    close = block.find("open.open = false")
    assert 0 <= inner < close, "a popup opened inside the dock menu is closed before the dock menu"
    assert "closeActionMenus()" in block[inner:close], "the inner popup closes, focus back on its opener"
    assert "event.stopPropagation()" in block[:close], "one Escape does one thing: Settings stays open"
    assert 'open.querySelector("summary")?.focus()' in block, "closing the dock menu focuses its button"


def test_a_flyout_row_and_a_nested_kebab_are_walked_not_opened_by_arrow_down():
    assert re.search(r'opener === target && opener\.getAttribute\("role"\) !== "menuitem"', JS), (
        "a row that opens a flyout is walked by its menu (APG: ArrowRight opens it)"
    )
    assert re.search(r'aria-expanded"\) === "false" && !opener\.parentElement\?\.closest\(\'\[role="menu"\]\'\)', JS), (
        "a closed ⋯ standing as a row of an open menu is walked past"
    )


def test_a_column_menu_walks_every_control_it_shows():
    block = _body("function wireMenuKeyboard(menu, opener)", 1500)
    assert re.search(r'menu\.querySelector\(":scope > \.wb-menu-col"\) \? menuRowsOf\(menu\)', block), (
        "the board's View menu, in columns, walks its switches, selects and rows"
    )


def test_the_zoom_list_parts_its_command_and_sizes_to_its_values():
    block = _body("const rows = presets.map((p) => ({", 600)
    assert 'group: p.run ? "act" : "value"' in block, "the values and the Fit command are two groups"
    assert 'classList.add("value-field-list")' in JS
    rule = re.search(r"\.action-menu\.value-field-list \{([^}]*)\}", CSS)
    assert rule and re.search(r"min-width:\s*0;", rule.group(1)), "no 12.5rem floor under a list of values"


def test_the_ask_box_answer_length_list_is_painted_with_the_notes_surface():
    block = _body("const loadResponseModes = (() => {", 1400)
    assert 'onSurface("chat", paint)' in block and 'onSurface("notes", paint)' in block
