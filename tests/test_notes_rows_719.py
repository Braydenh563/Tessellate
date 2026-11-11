"""Compact rows and cards in Notes: the lane, the cursor, the date (INBOX 719).

The owner, with screenshots: "blank space on right of compact rows view and
when hovering over the rows, the cursor is the text type cursor, not pointer",
and of the card view: "the last created or edited date changes position each
note, I think it should be consistent in the corner".

Measured in Chromium at 1440, before:

- rows: the metadata lane ended 104px short of the row's right edge on every
  row. `padding-inline-end: 6.5rem` held the width at rest for the hover
  actions, which are `position: absolute` and cost no width at all;
- rows: `cursor: auto` on the row, though a click on it opens or closes it;
- cards: a title-only note's date sat 104px left of every other card's. The
  actions' float (`.entry-content::before`, 6.5rem wide, 1em tall) lives in
  the body paragraph, which a title-only note leaves empty, so the float had
  no line to sit in, escaped the paragraph and narrowed the flex meta line
  below it (a flex container avoids floats);
- cards: on a one-line note the hover strip's bottom was 6px below the date's
  top, so the strip sat over the date.

The numbers are from that measurement; these pins hold the causes, so a later cleanup
of "redundant" rules fails here and not in the next screenshot.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests._css_paths import css_text

ROOT = Path(__file__).resolve().parents[1]


def _css() -> str:
    return css_text()


def _block(css: str, selector: str) -> str:
    """The declarations of the first rule whose selector is exactly `selector`."""
    match = re.search(re.escape(selector) + r"\s*(?:,[^{}]*)?\{([^}]*)\}", css)
    assert match, selector
    return match.group(1)


def test_rows_reserve_no_width_for_the_hover_actions():
    css = _css()
    assert "padding-inline-end: 6.5rem" not in css
    # Their strip overlays the end of the row; it does not take width.
    strip = _block(css, "#entry-list>li .entry-actions")
    assert "position: absolute" in strip


def test_a_collapsed_row_keeps_no_float_for_the_actions_in_its_preview():
    css = _css()
    block = _block(css, "#entry-list.is-rows > li:not(.row-expanded) > .entry-content::before")
    assert "display: none" in block


def test_an_opened_row_keeps_its_title_clear_of_the_actions():
    css = _css()
    block = _block(css, "#entry-list.is-rows > li.row-expanded > .entry-title")
    assert "padding-inline-end: 6.5rem" not in block
    assert "padding-inline-end:" in block


def test_a_row_is_a_pointer_target_where_a_click_opens_it():
    css = _css()
    block = _block(css, "#entry-list.is-rows > li:not(:has(textarea))")
    assert "cursor: pointer" in block
    # The opened row's own text is real, selectable text: it keeps its cursor.
    body = _block(css, "#entry-list.is-rows > li.row-expanded > .entry-content")
    assert "cursor: auto" in body


def test_cards_keep_the_text_cursor_and_select_mode_keeps_the_pointer():
    css = _css()
    assert re.search(r"\.entry-list li\.selectable\s*\{[^}]*cursor:\s*pointer", css)
    assert not re.search(r"#entry-list:not\(\.is-rows\)\s*>\s*li\s*\{[^}]*cursor:\s*pointer", css)


def test_the_hover_strip_ends_inside_the_time_it_covers():
    css = _css()
    block = _block(css, "#entry-list.is-rows > li .entry-meta-end > .entry-actions")
    assert "right: var(--space-1)" in block


def test_an_empty_body_leaves_no_float_to_narrow_the_meta_line():
    css = _css()
    block = _block(css, "#entry-list > li > .entry-content:empty::before")
    assert "display: none" in block


def test_the_card_strip_sits_in_the_corner_not_a_second_offset_below_it():
    css = _css()
    block = _block(css, "#entry-list:not(.is-rows) > li .entry-meta-end > .entry-actions")
    # Not a second offset below the corner; since the wrapzoom sweep it rises
    # by `--space-1` into the card's padding so it ends with the first line.
    assert "top: calc(var(--space-1) * -1)" in block


def test_the_cards_float_keeps_the_strips_own_width_clear():
    """wrapzoom sweep: a 6.5rem (104px) float against a 131px strip left the
    strip over the first line's end, 11x6 at 1280. The float is the strip's
    width in targets and gaps, a draft's five as well as four."""
    css = _css()
    four = _block(css, "#entry-list > li > .entry-content::before")
    assert "width: calc(4 * var(--target-min) + 3 * 0.4rem + var(--space-2))" in four
    assert "6.5rem" not in four
    five = _block(css, "#entry-list > li.has-wide-strip > .entry-content::before")
    assert "5 * var(--target-min)" in five
    card = (ROOT / "frontend" / "js" / "entry-card.js").read_text(encoding="utf-8")
    assert 'li.classList.toggle("has-wide-strip", actions.childElementCount > 4)' in card


def test_a_pointed_at_row_makes_room_for_its_strip_in_the_lane():
    """wrapzoom sweep, every width: the 131px strip lay over the time and the
    chips before it ("Linked by 1 note" half shown). On hover the time leaves
    and the lane's end keeps the strip's width."""
    css = _css()
    hover = "#entry-list.is-rows > li:not(:has(textarea)):is(:hover, :focus-within) > .entry-meta"
    assert "padding-inline-end: calc(4 * var(--target-min) + 3 * 0.4rem + var(--space-2))" in _block(css, hover)
    assert "display: none" in _block(css, hover + " > .entry-date")
