"""The Notes list's Select tick sits in the card's left gutter (INBOX 851: "the
selection boxes on notes are weirdly positioned above the note content").

Measured in Chromium before (scratchpad: the Notes tab, Select pressed): in card
view the tick was a flow child, so every card grew 28px (90 to 118, 93 to 121,
149 to 177) and the title sat under the box; in rows view (the default) the tick
took a grid row of its own and 45px rows became 73px. After: card heights and
row heights are unchanged in Select mode, the tick is 20x20 (`--space-7`) and its centre is
within 1px of the first line's centre, at 1440 and 390. The numbers are the
proof; this pins the shape so a refactor cannot put the tick back in the flow.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests._css_paths import css_text


def _rule(css: str, selector: str) -> str:
    match = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", css)
    assert match, selector
    return match.group(1)


def test_the_tick_is_out_of_the_flow_and_twenty_pixels():
    body = _rule(css_text(), '#entry-list > li.selectable > input[type="checkbox"].select-check')
    for decl in ("position: absolute", "width: var(--space-7)", "height: var(--space-7)",
                 "min-width: var(--space-7)", "min-height: var(--space-7)",
                 "border-radius: var(--radius-sm)"):
        assert decl in body, decl


def test_each_view_reserves_a_gutter_for_it():
    css = css_text()
    cards = _rule(css, "#entry-list:not(.is-rows) > li.selectable")
    assert "padding-left: calc(var(--space-3) + var(--space-7) + var(--space-3))" in cards
    rows = _rule(css, "#entry-list.is-rows > li.selectable > .select-check")
    assert "grid-column: auto" in rows and "top: var(--row-anchor)" in rows


# Select shrinks to a square icon button when its word is hidden (INBOX 803).


def _front_css(name: str) -> str:
    return (Path(__file__).resolve().parents[1] / "frontend" / "css" / name).read_text(encoding="utf-8")


def test_notes_select_is_square_when_its_word_is_hidden():
    css = _front_css("07-whiteboard-misc.css")
    rule = '[data-dock-name="notes"] .dock-actions > button:has(> .ph-lead + .dock-word)'
    assert rule in css
    block = css[css.index(rule):].split("}", 1)[0]
    assert "width: var(--control-h)" in block and "padding-inline: 0" in block
