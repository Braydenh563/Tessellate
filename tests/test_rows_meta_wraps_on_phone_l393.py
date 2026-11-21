"""Source text: under 600px a list-view row puts its facts on a line of their own (L393).

Measured at 320, 360 and 390 with ten seeded notes: before, the facts sat
beside the title in a `fit-content(26rem)` track that took the whole row and
left the title about 10px wide; after, the title track is 190px at 320, the
facts span the row on line 2, and no row's actions run past the viewport.
"""

from __future__ import annotations

import re

from tests._css_paths import CSS_DIR

CSS = (CSS_DIR / "01-forms-settings.css").read_text(encoding="utf-8")


def test_the_facts_take_their_own_line_under_600():
    block = re.search(r"@media \(max-width: 599\.98px\) \{\s*\.entry-list\.is-rows li:not\(:has\(textarea\)\) > \.entry-meta \{(.*?)\}", CSS, re.S)
    assert block, "the narrow rows rule is missing"
    assert "grid-column: 1 / -1" in block.group(1)
    assert "grid-row: 2" in block.group(1)
