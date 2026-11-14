"""The compact rows view's line, chevron and motion (INBOX 676).

The owner, 2026-10-06: "hovering over collapsed notes on the compact rows
view the popup hover buttons arent correctly positioned, the metadata isnt
centred. when expanded the dropdown arrow is different and bordered, it isnt
clean, the arrow should smoothly change, the dropdown and collapse should be
a smooth animation adn not sudden and janky."

Measured before (scratchpad/ui-sweeps/rows676.js, 1440x900): the hover
cluster 32.8 to 62px in a 49.6px row (half below it), the metadata's centre
4.8px under the title's (INBOX 505's card step, `margin-top: var(--space-4)`,
reached the rows too), the expanded chevron a different glyph in a filled,
bordered square (`aria-expanded="true"` is the icon button's "on" recipe),
and the toggle a full list redraw: one frame from 49.6 to 237.8px.

These are the source halves; the numbers are the sweep's.
"""

from __future__ import annotations

import re

from tests._app_js import app_js_text
from tests._css_paths import CSS_DIR


def _css(name: str) -> str:
    return (CSS_DIR / name).read_text(encoding="utf-8")


def _function(js: str, name: str) -> str:
    start = js.index(f"function {name}(")
    end = js.index("\n}\n", start)
    return js[start:end]


def test_a_collapsed_row_puts_its_metadata_on_the_title_line():
    css = "\n".join(_css(n) for n in ("01-forms-settings.css", "04-chat-dock-appearance.css", "06-timeline-dialogs.css", "07-whiteboard-misc.css"))
    assert (
        "#entry-list.is-rows > li:not(.row-expanded):not(.list-window-sentinel) > .entry-meta.entry-meta {\n"
        "  margin-top: 0;\n}"
    ) in css


def test_the_chevron_and_the_cluster_share_one_anchor_in_both_states():
    css = "\n".join(_css(n) for n in ("01-forms-settings.css", "04-chat-dock-appearance.css", "06-timeline-dialogs.css", "07-whiteboard-misc.css"))
    assert "--row-anchor: calc(var(--space-3) + var(--target-min) / 2);" in css
    assert "grid-template-rows: minmax(var(--target-min), auto);" in css
    # The anchor, not the row's middle: a row growing through its animation
    # must not carry the chevron or the cluster down with it.
    block = css.split("--row-anchor: calc(", 1)[1]
    assert "top: var(--row-anchor);" in block
    assert "transform: translateY(-50%);" in block


def test_the_chevron_is_one_ghost_whose_glyph_turns():
    js = app_js_text()
    item = _function(js, "entryItem")
    assert "ph:caret-up" not in item, "one glyph; the turn is CSS"
    css = "\n".join(_css(n) for n in ("01-forms-settings.css", "04-chat-dock-appearance.css", "06-timeline-dialogs.css", "07-whiteboard-misc.css"))
    assert "#entry-list li > .row-expand.ghost.ghost" in css
    assert re.search(
        r"#entry-list li > \.row-expand > \.ph \{\n  transition: transform var\(--ui-base\) var\(--ease-out\);",
        css,
    )
    assert "#entry-list li.row-expanded > .row-expand > .ph {\n  transform: rotate(180deg);" in css


def test_a_toggle_animates_the_row_in_place():
    js = app_js_text()
    toggle = _function(js, "toggleRowExpanded")
    # In place: the same row and the same button, so the glyph's transition
    # runs and a second press can turn back from wherever the first got to.
    assert ".animate(" in toggle
    assert "getBoundingClientRect().height" in toggle
    assert "--ui-slow" in toggle, "the interface motion token, so the switch turns it off"
    assert "renderEntries()" in toggle  # only when the row is not on screen
    assert toggle.count("renderEntries()") == 1


def test_show_more_is_measured_whenever_the_text_has_a_size():
    """INBOX 678: "this note has show more but it doesnt have any text cut
    off". Measured before (scratchpad/ui-sweeps/rows678.js, 1440): two notes
    of four lines kept the toggle with scrollHeight 77 = clientHeight 77,
    and the lines were 19.1px clamped and 22.8px opened."""
    js = app_js_text()
    assert "const noteClampFit = new ResizeObserver(" in js
    assert "noteClampFit.observe(content);" in _function(js, "entryItem")
    assert "settleNoteClamps" not in js, "one measurement, not three partial ones"
    css = _css("03-dashboard-widgets.css")
    rule = css[css.index("#entry-list:not(.is-rows) .entry-content.entry-clamped {"):]
    assert "line-height" not in rule[: rule.index("}")]


def test_a_notes_buttons_stay_while_its_menu_is_open():
    """INBOX 679: the strip faded under its own open menu once the menu had
    moved to <body> (rows view: opacity 1 pressed, 0 on the menu)."""
    css = "\n".join(_css(n) for n in ("01-forms-settings.css", "04-chat-dock-appearance.css", "06-timeline-dialogs.css", "07-whiteboard-misc.css"))
    assert "#entry-list > li .entry-actions.menu-open {\n  opacity: 1;\n}" in css
    assert 'menu.closest(".entry-actions, .library-card")?.classList.add("menu-open");' in app_js_text()
