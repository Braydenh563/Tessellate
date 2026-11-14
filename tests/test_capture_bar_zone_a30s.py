"""INBOX 1572 (the owner, 2026-11-03): the Notes capture bar is its own zone.

1572: "the quick notes adding row at the top of the notes is a little trippy to use and i sometimes
click it instead of the top search bar or buttons by accident". Measured at 1440 before: the row sat
9.6px under the dock (18.6px under the search field), looked like a second search field, and a focus
opened the card in the flow, pushing the list down 256px. Now it is its own zone: a divider and
`--space-6` above it, one quiet row at rest (no field look), and the card opens over the list so
nothing below moves.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests import _js_scope

ROOT = Path(__file__).resolve().parent.parent
INDEX = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "css" / "07-whiteboard-misc.css").read_text(encoding="utf-8")
CARD_CSS = (ROOT / "frontend" / "css" / "capture-card-lazy.css").read_text(encoding="utf-8")
#: capture-card.js is one closure now (ranked row 37a); the tests slice or run its private functions, so they read it as it was before it was wrapped (`_js_scope.unwrapped`): same code, same assertions.
CARD = _js_scope.unwrapped((ROOT / "frontend" / "js" / "capture-card.js").read_text(encoding="utf-8"))


def _rule(sheet: str, selector: str) -> str:
    """The body of the last rule whose selector list is exactly `selector`."""
    found = [m.group(1) for m in re.finditer(r"(?:^|[}/])\s*" + re.escape(selector) + r"\s*\{([^}]*)\}", sheet)]
    assert found, f"no rule for {selector}"
    return found[-1]


def _bar() -> str:
    start = INDEX.index('id="capture-bar"')
    return INDEX[start : INDEX.index('<ul id="entry-list"', start)]


# --- 1572: the bar is its own zone ----------------------------------------------------------------


def test_the_bar_is_a_divider_and_a_gap_below_the_dock_not_a_second_search_field():
    rule = _rule(CSS, ".capture-bar")
    assert "border-top: 1px solid var(--divider)" in rule
    assert "margin: var(--space-6) 0" in rule and "padding-top: var(--space-4)" in rule


def test_the_row_at_rest_is_quiet_text_with_no_field_look():
    rule = _rule(CSS, ".capture-bar-row .capture-bar-input")
    assert "background: none" in rule or "background: transparent" in rule
    assert "border: 0" in rule and "box-shadow: none" in rule
    # it lights on the pointer and the keyboard, the way a ghost button does
    assert ".capture-bar-row .capture-bar-input:hover" in CSS


def test_the_row_controls_are_pinned_to_the_body_control_height():
    """Unslop 24: the row was 36.4 and the picture button 28. L-ui-modernisation-80 put
    the 44px touch floor under the body height, so the pin is the larger of the two."""
    rule = _rule(CSS, ".capture-bar-row .capture-bar-input,\n.capture-bar-row .capture-bar-icon")
    assert "height: max(var(--control-h-body), var(--target-min))" in rule
    assert "min-height: max(var(--control-h-body), var(--target-min))" in rule


def test_the_note_todo_seg_left_the_bar_and_to_do_is_an_icon_that_opens_the_card_in_that_mode():
    bar = _bar()
    assert "capture-bar-modes" not in bar and 'class="seg' not in bar
    todo = re.search(r"<button[^>]*id=\"capture-bar-todo\"[^>]*>", bar).group(0)
    assert 'data-mode="todo"' in todo and "capture-bar-icon" in todo and "icon-only" in todo
    assert 'aria-label="' in todo and 'title="' in todo
    assert 'id="capture-bar-picture"' in bar and "capture-bar-icon" in re.search(r"<button[^>]*id=\"capture-bar-picture\"[^>]*>", bar).group(0)
    show = CARD[CARD.index("function showCaptureCard(") :]
    assert 'from?.closest?.(".capture-bar-todo")' in show[: show.index("\nfunction ")]


def test_the_card_opens_over_the_list_so_a_focus_moves_nothing():
    bar_open = _rule(CSS, ".capture-bar.is-open .capture-bar-row")
    assert "visibility: hidden" in bar_open and "display: none" not in bar_open
    assert "position: relative" in _rule(CSS, ".capture-bar")
    card = _rule(CARD_CSS, ".capture-card")
    assert "position: absolute" in card and "z-index: 2;" in card
    assert "background: var(--modal-bg-opaque)" in card
    # a floating surface on the glass-off list takes no blur
    assert "backdrop-filter" not in card


def test_the_hit_areas_do_not_overlap_the_dock_above_or_each_other():
    """Static half of the 1440 and 390 measure (elementFromPoint): the row sits below a divider, and its
    three controls are flex siblings with a gap, none of them absolutely placed over another."""
    assert "gap: var(--space-3)" in _rule(CSS, ".capture-bar-row")
    assert "position: absolute" not in _rule(CSS, ".capture-bar-row .capture-bar-input")
