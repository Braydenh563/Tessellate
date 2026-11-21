"""An explicit window holds the notes that sit in it (TIMELINE_PLAN section 9).

The calendar asks `/timeline` for one month, week or day with `start` and
`end`. A note sits on the date it mentions where it has one, so a window is
answered by that placement, not by when the note was typed: the calendar
sweep found a day page written in March and titled for today on the feed's
today and missing from the calendar's.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from tessellate.core.database import Entry
import pytest
from tests._clock import SUITE_LOCAL, SUITE_NOW, pin_clock


@pytest.fixture(autouse=True)
def _suite_clock(monkeypatch):
    """Data here is built from SUITE_NOW, and the app reads the same pinned clock."""
    pin_clock(monkeypatch, SUITE_NOW)


def _save(client, content: str) -> dict:
    response = client.post("/entries", json={"content": content, "category": "Journal"})
    assert response.status_code == 201
    return response.json()


def _ids(client, start: str, end: str, tz: int = 0) -> set[int]:
    body = client.get(f"/timeline?kind=note&start={start}&end={end}&tz={tz}&limit=1000").json()
    return {row["id"] for row in body["rows"]}


def _day(client, note_id: int) -> str:
    rows = client.get("/timeline?kind=note&days=0&limit=1000").json()["rows"]
    return next(row["date"] for row in rows if row["id"] == note_id)


def test_a_note_sits_in_the_window_of_the_day_it_mentions(client, session):
    page = _save(client, "Dentist tomorrow, bring the forms.")
    plain = _save(client, "Written today, about nothing in particular.")
    session.get(Entry, page["id"]).created_at = datetime(2024, 3, 2, 10, 0)
    session.commit()
    day = _day(client, page["id"])
    on_it = _ids(client, f"{day}T00:00:00", f"{day}T23:59:59")
    written = _ids(client, "2024-03-01T00:00:00", "2024-03-31T23:59:59")
    assert page["id"] in on_it and page["id"] not in written
    assert plain["id"] not in on_it


def test_a_mentioned_day_is_matched_on_the_readers_clock(client):
    page = _save(client, "Dentist tomorrow, bring the forms.")
    day = date.fromisoformat(_day(client, page["id"]))
    before = day - timedelta(days=1)
    after = day + timedelta(days=1)
    # Five hours west of UTC a local day runs 05:00 to 04:59 UTC: the day the
    # writer named is in its own day's window, not the one before.
    own = _ids(client, f"{day}T05:00:00", f"{after}T04:59:59", tz=-300)
    previous = _ids(client, f"{before}T05:00:00", f"{day}T04:59:59", tz=-300)
    assert page["id"] in own and page["id"] not in previous


def test_a_meeting_sits_in_the_window_of_its_own_date(client, session):
    made = client.post("/meetings", json={"title": "Planning", "when": "2031-02-03T14:00", "category": "Work"})
    assert made.status_code == 201
    meeting = made.json()
    session.get(Entry, meeting["id"]).created_at = datetime(2024, 3, 2, 10, 0)
    session.commit()
    assert meeting["id"] in _ids(client, "2031-02-03T00:00:00", "2031-02-03T23:59:59")
    assert meeting["id"] not in _ids(client, "2024-03-01T00:00:00", "2024-03-31T23:59:59")


def test_a_note_with_a_written_out_date_sits_on_that_date(client, session):
    """The owner, 2026-10-11: "things written on specific dates dont show".
    A note saying "2031-02-03 at 3pm" was placed by when it was typed, since
    only relative phrases were read; now the calendar's window for that day
    holds it, with the clock, and the day it was written does not."""
    made = _save(client, "Dentist appointment on 2031-02-03 at 3pm, bring forms")
    session.get(Entry, made["id"]).created_at = datetime(2024, 3, 2, 10, 0)
    session.commit()
    assert made["id"] in _ids(client, "2031-02-03T00:00:00", "2031-02-03T23:59:59")
    assert made["id"] not in _ids(client, "2024-03-01T00:00:00", "2024-03-31T23:59:59")
    body = client.get("/timeline?kind=note&start=2031-02-03T00:00:00&end=2031-02-03T23:59:59&limit=1000").json()
    row = next(r for r in body["rows"] if r["id"] == made["id"])
    assert row["placed_by"] == "mentioned" and row["date"] == "2031-02-03" and row["time"] == "15:00"


def test_the_feeds_last_year_range_holds_a_note_by_where_it_sits_like_the_calendar(client, session):
    """OPEN.md: the feed's Last-year range filtered by when a note was written,
    so a note about a day this month written over a year ago showed in the
    calendar and not the feed (TIMELINE_PLAN decision 24)."""
    soon = (SUITE_LOCAL.date() + timedelta(days=3)).isoformat()
    old = _save(client, f"Renew the licence on {soon}.")
    session.get(Entry, old["id"]).created_at = datetime(2023, 1, 5, 10, 0)
    recent = _save(client, "Written today about nothing in particular.")
    session.commit()
    feed = {row["id"] for row in client.get("/timeline?kind=note&days=365&limit=1000").json()["rows"]}
    assert old["id"] in feed and recent["id"] in feed
    recent_90 = {row["id"] for row in client.get("/timeline?kind=note&days=90&limit=1000").json()["rows"]}
    assert old["id"] in recent_90  # it sits three days ahead: inside a range with no end


def test_a_note_written_this_year_about_a_day_long_ago_sits_there_not_in_the_recent_feed(client):
    made = _save(client, "I was born on 1999-03-04.")
    recent = {row["id"] for row in client.get("/timeline?kind=note&days=90&limit=1000").json()["rows"]}
    assert made["id"] not in recent
    everything = {row["id"] for row in client.get("/timeline?kind=note&days=0&limit=1000").json()["rows"]}
    assert made["id"] in everything


def test_a_note_naming_two_dates_sits_on_the_first_and_lists_the_other_as_also_on(client):
    made = _save(client, "Pay the deposit on 2031-02-03 and the balance on 2031-03-05.")
    window = "kind=note&start={}T00:00:00&end={}T23:59:59&limit=1000"
    first = client.get("/timeline?" + window.format("2031-02-03", "2031-02-03")).json()["rows"]
    row = next(r for r in first if r["id"] == made["id"])
    assert row["date"] == "2031-02-03" and row["also_on"] == ["2031-03-05"]
    # The second date's window holds it only when the calendar asks for the also-on notes.
    plain = client.get("/timeline?" + window.format("2031-03-05", "2031-03-05")).json()["rows"]
    assert made["id"] not in {r["id"] for r in plain}
    asked = client.get("/timeline?" + window.format("2031-03-05", "2031-03-05") + "&also=true").json()["rows"]
    assert made["id"] in {r["id"] for r in asked}
