"""INBOX 1492, the frontend half (a tab click at 4x CPU, 500 notes: Notes 544
to 720ms, Dashboard 392 to 424ms). Source-shape pins for each cause found; the
numbers are in docs/roadmap/agent-remaining/tabspeed-1031.md."""

from __future__ import annotations

import re
from pathlib import Path

from tests._app_js import frontend_text

ROOT = Path(__file__).resolve().parents[1]


def _body(js: str, head: str) -> str:
    start = js.index(head)
    return js[start : js.index("\n}\n", start)]


def _css(name: str) -> str:
    return (ROOT / "frontend" / "css" / name).read_text(encoding="utf-8")


def test_a_custom_property_on_a_page_is_written_only_when_it_changes():
    """`--notes-sticky-top` is inherited, so a write restyles the whole Notes
    page (1,794 elements, 100 to 230ms at 4x). The hidden strip still reads its
    10px margin, so the sum wrote `10px` on every hide and `46px` on every show:
    two changes a tab visit. The box decides, and an equal value is not written."""
    body = _body(frontend_text("phone-shell.js"), "function initNotesSubtabHeightToken(")
    assert "if (!(box > 0)) return;" in body
    assert 'getPropertyValue("--notes-sticky-top") !== h' in body
    assert "if (h > 0)" not in body


def test_an_empty_row_shell_is_not_matched_by_the_row_rules_that_use_has():
    """A shell is an empty `li` and a long list is hundreds of them: every rule
    that lets `:has()` or `content-visibility` run on `li` runs on each, on every
    restyle of the page (`#entry-list li:is(:focus-visible, :has(:focus-visible))`
    3.1ms and the content-visibility rule 2.6ms at 515 `li`), and
    `content-visibility: auto` on a shell rebuilt its layout object (977 layout
    additions for 488 shells). `:where(:not(.row-shell))` keeps the specificity."""
    cv = _css("07-whiteboard-misc.css")
    assert "#entry-list > li:not(.row-shell, .list-window-sentinel, :focus-within)" in cv
    assert "#entry-list li:where(:not(.row-shell)):is(:focus-visible, :has(:focus-visible))" in _css("03-dashboard-widgets.css")
    consistency = _css("08-consistency.css")
    assert ".entry-list > li:has(> :is(.skill-row, .persona-row))" not in consistency
    assert consistency.count(".entry-list > li:where(:not(.row-shell)):has(> :is(.skill-row, .persona-row))") == 2


def test_the_tab_scroller_search_does_not_visit_every_element_of_the_page():
    """`tabPageScroller` read `scrollHeight` of all of a page's elements (Notes
    3,528, Library 6,122: 14 to 140ms at 4x) two frames after every tab press.
    The scrolling region is a few levels down on every page."""
    body = _body(frontend_text("phone-shell.js"), "function tabPageScroller(")
    assert not re.search(r'querySelectorAll\(\s*"\*"\s*\)', body)
