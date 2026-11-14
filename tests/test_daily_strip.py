"""WORLD_CLASS_PLAN D6: the calendar strip and the day pair in a daily note's head.

The backend (`/entries/daily`, `/entries/daily/{day}`) and Ctrl+D were built
first; what was left was the two surfaces this file holds in place. The suite
cannot open a browser, so the shapes that would silently break are pinned
statically and `scratchpad/ui-sweeps/daystrip.js` drives the real thing.
"""

from __future__ import annotations

from tests._help_text import help_chat_text

import re
from pathlib import Path

from tests._app_js import frontend_text

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
TIMELINE = frontend_text("timeline.js")


def _function(source: str, signature: str) -> str:
    start = source.index(signature)
    return source[start : source.index("\n}\n", start)]


def test_the_strip_lives_in_the_tab_not_in_the_dock():
    # Seven buttons in the dock would spend its whole seven-control ceiling.
    assert 'id="timeline-daystrip"' in HTML
    dock_start = HTML.index('data-dock-name="timeline"')
    dock_end = HTML.index('id="timeline-intro"', dock_start)
    assert 'id="timeline-daystrip"' not in HTML[dock_start:dock_end]


def test_a_press_never_writes_a_note():
    """The owner's rule for Start today's note ("it shouldnt make the note yet")
    holds for every day: opening or starting a day reads, and the composer is
    the only way a note comes into being."""
    for signature in ("async function openDayPage(", "function startDayNote(", "async function renderTimelineDayStrip("):
        body = _function(TIMELINE, signature)
        assert "POST" not in body, signature
        assert 'method:' not in body, signature
    assert 'showNotesSection("capture")' in _function(TIMELINE, "function startDayNote(")


def test_a_day_is_asked_about_before_it_is_read():
    """A day with no page is an answer, not a 404 in the console (errors.js
    counts those): `openDayPage` asks `GET /entries/daily` first."""
    body = _function(TIMELINE, "async function openDayPage(")
    assert body.index("/entries/daily?through=") < body.index("/entries/daily/${key}")


def test_the_strip_reads_the_endpoint_written_for_it():
    body = _function(TIMELINE, "async function renderTimelineDayStrip(")
    # One helper answers both the strip and the month popover.
    assert "timelineDayPages(first, end)" in body
    assert "/entries/daily?through=${end}&days=${span}" in _function(TIMELINE, "async function timelineDayPages(")
    assert "TIMELINE_STRIP_DAYS = 7" in TIMELINE
    # The window never passes today, and Today brings it home.
    assert '$("timeline-days-later").disabled = end >= today' in body
    assert "timelineStripEnd = null" in TIMELINE[TIMELINE.index('$("timeline-jump-today")') :]


def test_the_day_pair_is_offered_for_a_note_titled_with_its_date():
    cards = frontend_text("note-cards.js")
    assert re.search(r"\^\\d\{4\}-\\d\{2\}-\\d\{2\}\$/\.test\(entry\.title\)", cards)
    assert "dailyNotePair(entry.title)" in cards
    pair = _function(TIMELINE, "function dailyNotePair(")
    assert "openDayPage(other)" in pair
    # One day before, one day after.
    assert "side(-1" in pair and "side(1" in pair


def test_the_strip_has_its_styles_and_stays_flat():
    css = (ROOT / "frontend" / "css" / "06-timeline-dialogs.css").read_text(encoding="utf-8")
    assert "grid-template-columns: repeat(7, minmax(0, 1fr))" in css
    # Flat on the page: no card or glass around the strip (surface budget).
    assert not re.search(r'id="timeline-daystrip"[^>]*class="[^"]*(card|glass)', HTML)


def test_the_guide_and_the_timeline_help_name_the_strip():
    guide = help_chat_text()
    assert "the calendar strip shows the last seven days" in guide
    assert "The strip below shows the last seven days" in HTML


def test_the_month_popover_is_the_popover_shell_with_a_roving_grid():
    """D6's overflow: the month label opens a calendar on the popover shell
    (`wireHelpPopover`), days after today are not offered, a picked day moves
    the strip and writes nothing, and the arrow keys walk the grid."""
    assert 'id="timeline-month-btn"' in HTML and 'aria-haspopup="dialog"' in HTML
    assert 'id="timeline-month-pop"' in HTML
    assert "wireHelpPopover(button, pop)" in TIMELINE
    day = _function(TIMELINE, "function renderTimelineMonthPop(")
    assert "button.disabled = key > today" in day
    assert "POST" not in day and "method:" not in day
    jump = _function(TIMELINE, "function timelineJumpToDay(")
    assert "openDayPage" not in jump and "closeHelpPopovers()" in jump
    keys = _function(TIMELINE, "function timelineMonthKeys(")
    for name in ("ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "Home", "End", "PageUp", "PageDown", "Escape"):
        assert name in keys, name


def test_the_strip_is_one_header_with_the_arrows_by_the_month():
    """INBOX 543: the month sits between its arrows in one group, the days are
    one well spanning the row, and the seven are one Tab stop the arrow keys
    walk (the sweep measures the layout; this pins the shape)."""
    head = HTML[HTML.index('class="timeline-daystrip-head"') : HTML.index('id="timeline-daystrip-days"')]
    assert head.index('id="timeline-days-earlier"') < head.index('id="timeline-month-btn"') < head.index('id="timeline-days-later"')
    css = (ROOT / "frontend" / "css" / "06-timeline-dialogs.css").read_text(encoding="utf-8")
    days = css[css.index(".timeline-days {") : css.index("}", css.index(".timeline-days {"))]
    assert "background: var(--chip-bg)" in days and "max-width" not in days
    assert ".timeline-day.is-today .timeline-day-num" in css
    body = _function(TIMELINE, "async function renderTimelineDayStrip(")
    assert "button.tabIndex = key === stop ? 0 : -1" in body
    keys = _function(TIMELINE, "function timelineDayKeys(")
    for name in ("ArrowLeft", "ArrowRight", "Home", "End"):
        assert name in keys, name
    assert 'addEventListener("keydown", timelineDayKeys)' in TIMELINE


def test_the_strip_says_the_journal_streak():
    """L495 (D6's "a streak that counts days with a daily note"), reopened
    2026-11-14: decision 22 had only a session reason. The streak is a quiet
    line in the strip's head, not a dock control, asked over the endpoint's
    full window so a long run is not capped at the strip's seven days, and
    hidden under two days (one day is not a run)."""
    head = HTML[HTML.index('class="timeline-daystrip-head"') : HTML.index('id="timeline-daystrip-days"')]
    assert re.search(r'<span id="timeline-streak" class="[^"]*\bhidden\b[^"]*"', head)
    body = _function(TIMELINE, "async function renderTimelineDayStrip(")
    assert "/entries/daily?through=${today}&days=366" in body
    assert "timelineStreakLine(" in body
    line = _function(TIMELINE, "function timelineStreakLine(")
    assert "days in a row" in line and "< 2" in line
