"""The phone top bar's controls sit on the right edge, not packed left (WORLD_CLASS 430).

Driven at 390: the controls ended at x=318 of 390 (72px empty on the right, 10px
on the left) because the desktop rule that zeroes their auto margin for the tab
strip's sake also matched on a phone, where the strip is not in the bar."""

from __future__ import annotations

import re
from pathlib import Path

CSS = (Path(__file__).resolve().parent.parent / "frontend" / "css" / "07-whiteboard-misc.css").read_text(encoding="utf-8")
SELECTOR = "header#top-bar:not(.tabs-wrapped):not(.tabs-centred) > .header-controls"


def test_the_desktop_rule_that_zeroes_the_auto_margin_has_a_phone_counterpart():
    zero = CSS.index(SELECTOR + " {\n  margin-left: 0;")
    phone = re.search(r"@media \(max-width: 599\.98px\) \{\s*" + re.escape(SELECTOR) + r" \{\s*margin-left: auto;", CSS[zero:])
    assert phone, "below 600 the controls must take the free space (margin-left: auto) after the rule that zeroes it"
