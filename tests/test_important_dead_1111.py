"""Two `!important` groups went in the F6 pass (OPEN.md F6, 96 to 87), and these hold why.

`.dock-native-hidden` was a rule of seven `!important` declarations for a class
nothing applies: no markup, no script adds it (two scripts only test for it), so
the rule could not match an element. And the ai-mark's emblem is drawn by
`EMBLEM_SLOTS` at 24px inline, so its stylesheet size needs no `!important`
to say the same thing. Computed styles of the emblem measured identical before
and after at 820, 1440 and 2560 wide (24px by 24px).
"""

from __future__ import annotations

import re

from pathlib import Path

from tests._css_paths import css_text

JS = Path(__file__).resolve().parents[1] / "frontend" / "js"


def app_js_text() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in sorted(JS.glob("*.js")))


def _css() -> str:
    return re.sub(r"/\*.*?\*/", "", css_text(), flags=re.S)


def test_dock_native_hidden_has_no_rule_while_nothing_applies_the_class():
    html = (JS.parent / "index.html").read_text(encoding="utf-8")
    # A script that adds the class: classList.add/toggle or className / class="" text.
    adds = re.findall(r"(?:classList\.(?:add|toggle|replace)|className\s*[+]?=|setAttribute\(\s*\"class\")[^;\n]*dock-native-hidden", app_js_text())
    assert "dock-native-hidden" not in html
    assert not adds, "a script applies .dock-native-hidden: the rule is live, put it back with its reason"
    assert ".dock-native-hidden {" not in _css(), "a rule for a class nothing applies is dead code (and seven !important)"


def test_the_emblem_mark_has_no_size_rule_of_its_own_beside_its_slot():
    css = _css()
    assert not re.search(r"\.emblem-mark \.emblem-art\s*\{", css), "the art's size is the slot's, drawn inline"
    box = re.search(r"(?m)^\.emblem-mark\s*\{([^}]*)\}", css)
    assert box and "width: 24px" in box.group(1) and "height: 24px" in box.group(1), "the row keeps a 24px box"
    assert '["ai-mark", 24, true]' in app_js_text(), "the slot's drawn size moved: the box must follow it"
