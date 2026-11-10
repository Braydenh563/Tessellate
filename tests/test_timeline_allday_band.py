"""INBOX 1733: the Week and Day views' all-day band is as tall as its notes.

It was a fixed 5rem (week) and 9rem (day): two notes in the Day view left
68 px empty under them (144 px band, content 76), an empty day 144 px.
TIMELINE_PLAN decision 15/21 hold: plain notes are all-day chips, only a note
that names a clock (and reminders, meetings) sits on its hour, so the band is
sized, not the placement changed. Measured at 1440: two notes 144 to 80 px
(4 px empty), no notes 144 to 40, nine notes 128 with "+6 more"; the Week
band is unchanged at 80 for two notes.
"""

import re
from pathlib import Path

CSS = (Path(__file__).resolve().parent.parent / "frontend/css/timeline-calendar-lazy.css").read_text()


def _rule(selector: str) -> str:
    start = CSS.index(selector + " {", CSS.index("The all-day row is as tall"))
    return CSS[start : CSS.index("}", start)]


def test_the_all_day_band_sizes_to_its_content_under_a_cap() -> None:
    band = _rule(".timeline-cal-alldaycell")
    assert "height: auto;" in band and "min-height:" in band
    assert "max-height: var(--cal-allday);" in band
    assert not re.search(r"(?<![-\w])height: var\(--cal-allday\)", band)


def test_the_day_view_keeps_its_taller_cap() -> None:
    day = _rule(".timeline-cal-weekwrap.is-day .timeline-cal-alldaycell")
    assert "max-height: calc(var(--cal-allday) * 1.8);" in day
