"""Source text: from 820 up a settings form row keeps its reset's slot, so a
reset appearing moves nothing (L416).

Measured on the Bin row: at 820 the reset wrapped to its own line on a change
(row 32 to 57px) and at 1440 the field moved 37px; after, 32px before and
after at 820 and no movement at 1440. The other form rows wrap as before
(11, 2 and 1 of 24 at 820, 1024 and 1440, the same as without the rule).
"""

from __future__ import annotations

import re

from tests._css_paths import CSS_DIR

CSS = (CSS_DIR / "settings-controls-lazy.css").read_text(encoding="utf-8")
ROW = r"#settings-modal \.settings-section \.row:has\(> label:first-child:not\(\.setting-check\):not\(\.check-row\):not\(\.checkbox-label\)\)"


def test_the_row_reserves_the_slot_and_the_reset_sits_in_it():
    block = CSS[CSS.index("@media (min-width: 820px) {") :]
    assert re.search(ROW + r" \{[^}]*padding-inline-end: calc\(var\(--control-h-dense\) \+ var\(--space-2\)\)", block)
    assert re.search(ROW + r" > \.setting-reset \{[^}]*position: absolute", block)
    assert "flex-basis: calc(16rem - var(--control-h-dense) - var(--space-2))" in block
