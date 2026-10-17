"""A day or a time written in a note is offered as a reminder that lands on the
timeline and the calendar (INBOX 904 B72, the owner: "I want the app to be able
to recognise future date and time mentions and suggest to use magic add to add
it to the timeline, calendar and as a reminder").

The note editor's offers already read a future day (`ai/offers.py`); a reminder
is a row on the timeline's feed and a chip on its calendar. What was missing is
the saying so: the chip's reason names both, and taking it ends on a notice
with "Show on calendar", which opens the calendar on the reminder's day.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from tessellate.ai import offers
from tests._app_js import JS_DIR

NOW = datetime(2026, 10, 10, 14, 0, tzinfo=timezone.utc)
QUICK = (JS_DIR / "quickadd.js").read_text(encoding="utf-8")
CAL = (JS_DIR / "timeline-calendar.js").read_text(encoding="utf-8")


def _fn(name: str, text: str) -> str:
    match = re.search(rf"^(?:async )?function {name}\(.*?^\}}", text, re.S | re.M)
    assert match, f"{name} is gone"
    return match.group(0)


def test_the_offer_says_where_the_reminder_goes(session):
    found = offers.offers(session, "Dinner with Sam on Friday at 7pm.", now=NOW)
    assert [o["kind"] for o in found] == ["reminder"]
    assert found[0]["reason"].endswith("on the timeline and the calendar")
    assert found[0]["label"].startswith("Remind me Friday 16 October 2026")


def test_taking_it_offers_the_calendar_on_that_day():
    take = _fn("noteOfferTake", QUICK)
    assert 'toastAction(' in take and '"Show on calendar"' in take
    assert "on the timeline and the calendar" in take
    show = _fn("noteOfferCalendar", QUICK)
    assert 'switchTab("timeline")' in show
    assert 'timelineCalendarCall("timelineCalendarOn", timelineBucketKey(new Date(dueAt), "day"))' in show


def test_the_calendar_opens_on_a_day_with_everything_shown():
    body = _fn("timelineCalendarOn", CAL)
    assert "timelineCal.focus = key" in body
    # Measured: a month read before the reminder was made left it off the agenda.
    assert 'timelineCal.url = ""' in body
    assert "timelineCal.only = null" in body
    assert 'prefs.set("timeline-view", "calendar")' in body
