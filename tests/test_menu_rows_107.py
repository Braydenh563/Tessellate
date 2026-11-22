"""Menu rows and the connection pill's menu button (WORLD_CLASS_PLAN 403,
L-world-class-107). Measured by scratchpad/ui-sweeps/menu-rows.js at 1440x900.

With a mouse the pill's button is the pill's inner height, so any end margin
puts its round fill off the cap's curve: 0px above and below and 2px to the
right with `margin-inline-end: 2px`. The owner named that gap twice. A
submenu row's words sat 0.9px left of every plain row's (37.8 against 38.7).
"""

import re
from pathlib import Path

CSS = (Path(__file__).resolve().parents[1] / "frontend" / "css" / "08-consistency.css").read_text(encoding="utf-8")


def _rule(selector: str, text: str = CSS) -> str:
    match = re.search(re.escape(selector) + r" \{([^}]*)\}", text)
    assert match, f"{selector} moved"
    return match.group(1)


def test_the_pill_menu_button_has_no_end_margin_with_a_mouse():
    block = re.search(r"@media \(pointer: fine\) \{\s*#entry-list \.link-connection > \.menu-wrap \{.*?\n\}", CSS, re.S)
    assert block, "the pointer-fine pill menu block moved"
    rule = _rule("#entry-list .link-connection > .menu-wrap > button", block.group(0))
    assert re.search(r"height:\s*1\.5rem", rule), "the button is the pill's inner height"
    assert re.search(r"margin-inline-end:\s*0;", rule), "an end margin puts the round fill off the pill's end"


def test_a_submenu_row_spaces_its_icon_and_words_as_every_other_row():
    # The wrapper span had no gap and its icon kept the 0.35em lead margin.
    words = [m.group(1) for m in re.finditer(r"\n\.menu-item > \.menu-item-words \{([^}]*)\}", CSS)]
    assert any(re.search(r"gap:\s*var\(--space-2\)", w) for w in words), "the words span carries the row's gap"
    assert re.search(r"margin-inline-end:\s*0;", _rule(".menu-item > .menu-item-words > .ph-lead"))


SETTINGS = (Path(__file__).resolve().parents[1] / "frontend" / "css" / "01-forms-settings.css").read_text(encoding="utf-8")


def test_a_dock_menu_switch_row_is_a_menu_row():
    # world-class menus.js at 1440: Logs' switch rows 34.9px with an 8px inset
    # against 32px and 12.8px for its buttons; the Timeline's Options switch
    # 33.2px against "Review some days" at 34.5. Measured after: every row in
    # both menus 34.5px, inset 12.8px (padding --space-2 --space-5, the recipe).
    # The recipe is one selector per row class since L342 (a list :is() at the
    # right is a universal-bucket rule), so the row list is read off the
    # selector group rather than off one :is().
    recipe = re.search(r"\n(:is\(\n  \.action-menu,[^{]*)\{([^}]*)\}", CSS)
    assert recipe, "the menu row recipe moved"
    assert ") .dock-menu-check {" in recipe.group(0), "a switch row takes the recipe's height and inset"
    assert "padding: var(--space-2) var(--space-5);" in recipe.group(2)
    assert "min-height: var(--control-h-lg);" in recipe.group(2)
    touch = re.search(r"@media \(max-width: 819\.98px\), \(pointer: coarse\) \{\n  (:is\(\n    \.action-menu,[^{]*)\{\s*min-height: var\(--target-min\);", CSS)
    assert touch and ") .dock-menu-check" in touch.group(1), "and the finger's floor"


def test_settings_does_not_pin_a_menu_row_to_its_strip_height():
    # The id-weight pin (height --settings-control-h, padding-block 0) held the
    # Logs menu's buttons at 32px; a menu row is excluded inside the same
    # `:not()` so the rule's weight on strip controls does not change.
    pin = re.search(r"\n(#settings-modal \.settings-section button:not[^\n]*),\n#settings-modal \.settings-section select,", SETTINGS)
    assert pin, "the settings control pin moved"
    assert ':not([class*="tile"], .tour-row, .doc-dock-menu-item)' in pin.group(1)


def test_a_switch_row_keeps_its_switch_at_the_end_so_its_icon_is_on_the_column():
    # Led by the switch, Logs' labels began 34.5px into the row against the
    # buttons' 21.7px; with it last, every icon is at 12.8px and every switch
    # ends 12.8px from the row's end (measured at 1440, Logs and Timeline).
    rule = _rule(':is(.doc-dock-menu-list, .action-menu) .dock-menu-check > input[type="checkbox"]')
    assert "order: 1;" in rule and "margin-inline-start: auto;" in rule


def test_a_switch_rows_icon_takes_the_menu_icon_width():
    # Not a first child (its input is), so it kept its own 15.6px against the
    # buttons' 19.5 and its words began 3.9px left of theirs.
    assert re.search(r":is\(\.action-menu, \.doc-dock-menu-list\) \.dock-menu-check > \.ph-lead \{[^}]*width: 1\.25em;", CSS)
