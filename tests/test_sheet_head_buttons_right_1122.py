"""A sheet head's Minimise and Close sit at its right edge (the owner, 2026-11-22).

Source text: "Timeline 'Add to <date>' panel: the minimise and close buttons sit right after the
title instead of right-aligned in the header." `.inbox-card` shrank every sheet title to its
words so a head select's auto margin could push the buttons; a sheet with no select (the
Timeline adder) kept them beside the title. Measured (scratchpad/ui-sweeps/tladdhead1122.js):
Close's right edge 726 against the head's 1083 at 1440, now 1083 and 1083 (373 and 373 at 390).
"""

from __future__ import annotations

import re

from tests._css_paths import css_text


def test_the_inbox_card_title_shrinks_only_beside_a_select():
    css = css_text()
    rules = re.findall(r"([^{}]*\.inbox-card[^{}]*\.sheet-title[^{}]*)\{([^}]*)\}", css)
    shrinking = [sel.strip() for sel, body in rules if re.search(r"flex:\s*0 1 auto", body)]
    assert shrinking, "the shrink rule moved: find where the inbox-card title is sized"
    assert all(":has(> .select-shell)" in sel for sel in shrinking), shrinking
