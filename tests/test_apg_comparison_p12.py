"""Sh1 P12: the Radix, shadcn and WAI-ARIA APG comparison, held as tests.

Brief 92 (b) asked for an element-by-element comparison of menu, select,
dialog, tabs, switch, slider, tooltip, popover and toast against the free
reference libraries (keyboard, focus, ARIA, states), each gap a fix with a
test. The record is HISTORY.md, "Radix, shadcn and APG comparison"; the gaps
it closed are held here. The DOM code cannot run in the suite, so this holds
the shape each fix took; the numbers behind them are from a driven server.
"""

from __future__ import annotations

import re

from tests._app_js import FRONTEND_DIR, JS_DIR

CSS_DIR = FRONTEND_DIR / "css"


def _js(name: str) -> str:
    return (JS_DIR / name).read_text(encoding="utf-8")


def test_a_menu_and_a_listbox_are_named():
    selects = _js("sheets-selects.js")
    assert 'if (ariaLabel) menu.setAttribute("aria-label", ariaLabel)' in selects
    assert 'menu.setAttribute("aria-label", label); // the listbox is named like its button' in selects


def test_arrow_keys_open_a_closed_menu_button_and_a_closed_select():
    nav = _js("navigation.js")
    assert 'opener.getAttribute("aria-haspopup") === "menu" && opener.getAttribute("aria-expanded") === "false"' in nav
    assert "openRows[openRows.length - 1]" in nav, "ArrowUp opens on the last row"
    selects = _js("sheets-selects.js")
    assert 'opener.addEventListener("keydown"' in selects
    assert '(event.key !== "ArrowDown" && event.key !== "ArrowUp")' in selects


def test_tab_closes_an_open_menu_and_letters_find_a_row():
    menus = _js("menus.js")
    keyboard = menus[menus.index("function wireMenuKeyboard") :]
    assert 'event.key === "Tab"' in keyboard and "closeActionMenus()" in keyboard
    assert "wireMenuKeyboard.typeahead(menu, menuItems, current, event)" in keyboard
    helper = menus[menus.index("wireMenuKeyboard.typeahead = ") :]
    assert "setTimeout(() => (menu._typed" in helper, "the prefix resets"
    assert "startsWith(menu._typed)" in helper


def test_the_confirm_and_prompt_dialogs_are_named_and_described():
    app = _js("app.js")
    confirm = app[app.index("function confirmDialog") : app.index("function promptDialog")]
    assert 'overlay.setAttribute("aria-labelledby"' in confirm
    assert 'overlay.setAttribute("aria-describedby", text.id)' in confirm
    prompt = app[app.index("function promptDialog") :]
    assert 'overlay.setAttribute("aria-labelledby", text.id)' in prompt[:6000]


def _css_switch_selectors() -> set[str]:
    css = re.sub(r"/\*.*?\*/", "", (CSS_DIR / "06-timeline-dialogs.css").read_text(encoding="utf-8"), flags=re.S)
    rule = re.search(r"(?:(?<=[{}])|\A)([^{}]+)\{\s*appearance: none;\s*-webkit-appearance: none;\s*width: 2rem;", css)
    assert rule, "the switch rule moved"
    return {re.sub(r"\s+", "", part).replace('"', "") for part in rule.group(1).split(",") if part.strip()}


def test_the_switch_role_list_is_the_switch_rule_selector_list():
    source = _js("sheets-selects.js")
    block = source[source.index("const SWITCH_BOXES = [") :]
    block = block[: block.index("].join")]
    ours = {re.sub(r"\s+", "", s) for s in re.findall(r'"([^"]+)"', block)}
    assert ours == _css_switch_selectors()
    assert 'box.setAttribute("role", "switch")' in source
    assert "enhanceAllSelects.stampSwitches?.(root || document)" in source


def test_a_slider_with_a_value_field_says_its_unit():
    field = _js("value-field.js")
    assert 'slider.setAttribute("aria-valuetext"' in field
    assert "valueTextOwn" in field, "a surface's own words are kept"


def test_an_error_toast_is_an_alert():
    """Source text: a failure toast takes `role="alert"` (Radix's foreground
    toast, the app's own load-failed.js), a plain one stays in #toast-box's
    polite region (L440)."""
    status = _js("status.js")
    body = status[status.index("function toast(message") :]
    assert 'if (isError) note.setAttribute("role", "alert");' in body[:3000]
