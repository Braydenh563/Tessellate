"""A note added after the list is drawn fades in (ledger 1538)."""

from __future__ import annotations

from pathlib import Path

from tests._app_js import app_js_text

CSS = (Path(__file__).resolve().parent.parent / "frontend" / "css" / "08-consistency.css").read_text(encoding="utf-8")


def test_the_list_remembers_what_was_on_screen_and_marks_new_cards():
    code = app_js_text()
    render = code[code.index("function resetNoteList("):]
    render = render[: render.index("list.replaceChildren();")]
    assert "rowEnterIds = new Set(" in render and "rowEnterTimer" in render
    card = code[code.index("function entryItem("):]
    card = card[:600]
    assert "rowEnterIds" in card and '"row-enter"' in card


def test_the_fade_uses_the_motion_token_so_reduced_motion_removes_it():
    rule = CSS[CSS.index("#entry-list li.row-enter"):]
    rule = rule[: rule.index("}")]
    assert "var(--ui-slow)" in rule and "animation: row-enter" in rule
    assert "@keyframes row-enter" in CSS


def test_an_opened_row_with_no_title_gives_its_first_line_a_title_lines_height():
    """Ledger 1548: measured 19.4 against the chevron's 22 before, 22 and 22 after
    (scratchpad/ui-sweeps/house1-chevron.js, 1440)."""
    rule = CSS[CSS.index("#entry-list.is-rows > li.row-expanded > .entry-content::first-line"):]
    rule = rule[: rule.index("}")]
    assert "line-height: var(--target-min)" in rule
    # A title gives the height back by sibling, not `:not(:has())`: that anchor restyled a
    # whole card on every insert (tests/test_tab_entry_cost.py).
    titled = CSS[CSS.index("li.row-expanded > .entry-title ~ .entry-content::first-line"):]
    assert "line-height: inherit" in titled[: titled.index("}")]
