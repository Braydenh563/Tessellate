"""A sheet head's Minimise and Close sit at its right edge (the owner, 2026-11-22).

Source text: "Timeline 'Add to <date>' panel: the minimise and close buttons sit right after the
title instead of right-aligned in the header." `.inbox-card` shrank every sheet title to its
words so a head select's auto margin could push the buttons; a sheet with no select (the
Timeline adder) kept them beside the title. Measured (scratchpad/ui-sweeps/tladdhead1122.js):
Close's right edge 726 against the head's 1083 at 1440, now 1083 and 1083 (373 and 373 at 390).
"""

from __future__ import annotations

import re

from tests._css_paths import css_glob_text, css_text


def test_the_inbox_card_title_shrinks_only_beside_a_select():
    css = css_text()
    rules = re.findall(r"(?:(?<=[{}])|\A)([^{}]*\.inbox-card[^{}]*\.sheet-title[^{}]*)\{([^}]*)\}", css)
    shrinking = [sel.strip() for sel, body in rules if re.search(r"flex:\s*0 1 auto", body)]
    assert shrinking, "the shrink rule moved: find where the inbox-card title is sized"
    assert all(":has(> .select-shell)" in sel for sel in shrinking), shrinking


#: The compound just before the title names its parent; any of these is a popup head.
_HEAD = re.compile(r"\.(?:dialog-head|sheet-head|panel-head)\b[^\s>]*\s*>?\s*$")


def test_no_popup_head_title_gives_up_its_room_unless_a_select_takes_it():
    """Widened from the Timeline adder (the hub's 2026-11-22 brief: every floating panel's actions
    right-aligned, timeline add, new meeting, voice recorder, dictionary and the rest). The shared
    head recipe puts Minimise and Close at the right edge because the title grows (`flex: 1 1 auto`,
    10-responsive.css and 08-consistency.css). A title set not to grow, directly in a head, left them
    beside it. Only a head select's auto margin may take the room instead. A title wrapped in a
    group of its own (the OCR headline, whose head is `space-between`) is not the head's child.
    Measured on every popup that opens bare (scratchpad/ui-sweeps/allheads1122.js, about 40 heads):
    the last control's right edge against the head's content edge, 0px at 390, 900 and 1440."""
    css = re.sub(r"/\*.*?\*/", "", css_glob_text(), flags=re.S)
    bad = []
    for group, body in re.findall(r"(?:(?<=[{}])|\A)([^{}]*)\{([^{}]*)\}", css):
        if not re.search(r"(?:^|;)\s*(?:flex:\s*(?:0|none)\b|flex-grow:\s*0\b)", body):
            continue
        for sel in group.split(","):
            sel = sel.strip()
            m = re.search(r"\.(?:sheet-title|dialog-head-title)\b[^\s>]*$", sel)
            if not m or ":has(> .select-shell)" in sel:
                continue
            before = sel[: m.start()]
            if not before.strip() or _HEAD.search(before) or re.search(r"\.(?:[\w-]*card|[\w-]*dialog)\b[^\s>]*\s*$", before):
                bad.append(sel)
    assert not bad, f"a popup title stops growing, so its head's buttons leave the right edge: {bad}"
