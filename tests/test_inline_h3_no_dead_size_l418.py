"""Source text: no heading class sets a size that the card's `h3` eyebrow
outranks and so never draws (L418, the `.tidy-title` clash swept wider).

The sweep read every `.card h3[class]` on the eight tabs, every Settings
section, Tidy and Activity, and listed each own-class rule that loses a
property to `.card h3` with a different value. One class lost: `.inline-h3`
(`font-size: var(--text-base)`), 25 headings, all inside a card, drawn at the
eyebrow's size. The dead size is gone; `.timeline-bucket-head` also overlaps
but sets the same weight (600).
"""

from __future__ import annotations

import re

from tests._css_paths import CSS_DIR

CSS = (CSS_DIR / "01-forms-settings.css").read_text(encoding="utf-8")


def test_inline_h3_keeps_only_its_display():
    rule = re.search(r"\n\.inline-h3 \{([^}]*)\}", CSS)
    assert rule and rule.group(1).strip() == "display: inline;"
