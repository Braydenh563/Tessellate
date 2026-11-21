"""Source text: the behaviour is CSS and front-end script that only a browser renders, and pytest has none, so these pin the rules' text.

L303 and L326: the Writing Room's two boxes end on one line.

Measured at 1440x900 with both boxes mounted: the thoughts box was 326.8px and the draft box 294.8px
(32px apart). The draft side's footer is two `.ask-composer` rows and the actions row; the thoughts side
wraps its footer in `.draft-foot`, held to the same height. After the fix both boxes are 294.8px at
1440, 1280 and 1160. The graph's two note boxes (`graph-popup-content`, `graph-new-content`) were
measured too: 146px empty, 352px (the `min(22rem, 45vh)` cap) with 60 lines, and the popup ends at
y=838.5 in a 900px window with no scroll.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_thoughts_footer_is_one_wrapper_held_to_the_drafts_footer_height():
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    start = html.index('<div class="draft-foot">')
    wrapped = html[start : html.index('<div class="draft-column">', start)]
    for marker in ("draft-desk-controls", 'id="draft-sources"', 'id="draft-rule-line"', 'id="draft-status"'):
        assert marker in wrapped, marker
    css = (ROOT / "frontend" / "css" / "04-chat-dock-appearance.css").read_text(encoding="utf-8")
    rule = re.search(r"\n\.draft-foot \{([^}]*)\}", css)
    assert rule, "the .draft-foot rule is missing"
    assert "min-height: calc(3 * var(--control-h) + 2 * (2 * var(--space-2) + 2px) + 2 * 0.4rem)" in rule.group(1)
