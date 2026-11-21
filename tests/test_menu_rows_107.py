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
