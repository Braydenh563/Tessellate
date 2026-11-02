"""A toolbar or dock rule states its control's height and corners as tokens
(audit 1028 S44).

The audit found "mixed button heights and radii between toolbars". Measured at
1280 and at 390 (every `.dock` control on the seven tabs): 30 controls are 28px
with a 4.8px radius at 1280 and 26 are 44px with the same radius at 390, the
search fields 32px; the view segments are the one small well (24px, 2.4px). The
cause of that agreement is that every rule for those controls reads
`--control-h`-style tokens, so this holds it: a rule whose selector names a
dock or a toolbar and sets `height`, `min-height` or `border-radius` takes a
`var(...)`, or is one of the short list below, each with its reason.
"""

from __future__ import annotations

import re

from tests._css_paths import css_text

#: (selector fragment, property, value): the few raw sizes that are not a
#: control's size at all.
ALLOWED = {
    # The visually-hidden pattern for a word kept for screen readers.
    (".toolbar-word", "height", "1px"),
    (".dock-word", "height", "1px"),
    (".dock-native-hidden", "height", "1px !important"),
    # A hairline between toolbar groups, not a control.
    (".doc-toolbar-sep", "height", "1.1rem"),
    # A menu's own scroll cap, in viewport units.
    (".ocr-reader-menu > .dock-menu-list", "height", "70dvh"),
}

TARGET = re.compile(r"(^|[\s,>])\.(dock|dock-actions|dock-group|dock-find|dock-arrange|dock-menu|doc-toolbar|doc-dock-menu-btn|doc-toolbar-menu|toolbar)\b")
SIZED = re.compile(r"(border-radius|height|min-height)\s*:\s*([^;]+);")
EXEMPT_VALUES = {"0", "auto", "none", "100%", "inherit", "unset", "50%", "initial"}


def test_a_toolbar_rule_sizes_its_controls_by_token():
    css = re.sub(r"/\*.*?\*/", "", css_text(), flags=re.S)
    loose = []
    for rule in re.finditer(r"([^{}]+)\{([^{}]*)\}", css):
        selector, body = " ".join(rule.group(1).split()), rule.group(2)
        if not TARGET.search(selector):
            continue
        for prop, value in SIZED.findall(body):
            value = value.strip()
            if "var(" in value or value in EXEMPT_VALUES:
                continue
            if any(frag in selector and (prop == p and value == v) for frag, p, v in ALLOWED):
                continue
            loose.append(f"{selector[:90]} {{ {prop}: {value} }}")
    assert not loose, "a toolbar control sized by a raw value, not a token:\n" + "\n".join(loose)
