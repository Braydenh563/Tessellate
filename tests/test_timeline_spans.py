"""Date ranges as spans (TIMELINE_PLAN decision 13, L-timeline-4).

A note that names a range ("the conference, 3 to 7 March 2031") stores the
range's last day beside its first, its feed row still sits on the first day
(decision 3: a row is one moment) and carries `until`, and the calendar's
window for any day inside the range holds it, so the span can be drawn across
those days rather than on the first alone.
"""

from __future__ import annotations

from datetime import date, datetime

import pytest

from tessellate.core.database import Entry, EntryDate
from tessellate.entry import timewords

NOW = datetime(2026, 7, 28, 10, 30)


@pytest.mark.parametrize(
    ("text", "start", "end"),
    [
        ("Conference 3 to 7 March 2031", date(2031, 3, 3), date(2031, 3, 7)),
        ("Conference 3-7 March 2031", date(2031, 3, 3), date(2031, 3, 7)),
        ("Conference 3rd – 7th of March 2031", date(2031, 3, 3), date(2031, 3, 7)),
        ("Conference March 3 to 7, 2031", date(2031, 3, 3), date(2031, 3, 7)),
        ("Away 28 July until 2 August", date(2026, 7, 28), date(2026, 8, 2)),
        ("Away from 30 December 2030 to 2 January 2031", date(2030, 12, 30), date(2031, 1, 2)),
    ],
)
def test_a_written_range_is_one_mention_with_its_last_day(text, start, end):
    found = timewords.find(text, NOW)
    assert len(found) == 1, found
    assert (found[0].at, found[0].until, found[0].precision) == (start, end, timewords.RANGE)


@pytest.mark.parametrize("text", ["Conference 7 to 3 March 2031", "3 to 45 March", "2 to 3 days from now"])
def test_a_backwards_or_impossible_range_is_not_a_span(text):
    assert all(m.precision != timewords.RANGE for m in timewords.find(text, NOW))


def test_a_single_date_stays_a_day():
    (only,) = timewords.find("Dentist on 3 March 2031", NOW)
    assert only.precision == timewords.DAY and only.until is None


def _save(client, content: str) -> dict:
    response = client.post("/entries", json={"content": content, "category": "Journal"})
    assert response.status_code == 201
    return response.json()


def _rows(client, start: str, end: str) -> list[dict]:
    query = f"/timeline?kind=note&start={start}&end={end}&tz=0&limit=1000&also=true"
    return client.get(query).json()["rows"]


def test_the_range_is_stored_and_served_as_a_span(client, session):
    made = _save(client, "Conference 3 to 7 March 2031, book the train.")
    session.get(Entry, made["id"]).created_at = datetime(2024, 3, 2, 10, 0)
    session.commit()
    stored = session.query(EntryDate).filter(EntryDate.entry_id == made["id"]).one()
    assert (stored.at.date(), stored.until.date(), stored.precision) == (date(2031, 3, 3), date(2031, 3, 7), "range")
    row = next(r for r in _rows(client, "2031-03-01T00:00:00", "2031-03-31T23:59:59") if r["id"] == made["id"])
    assert (row["date"], row["until"], row["placed_by"]) == ("2031-03-03", "2031-03-07", "mentioned")


def test_a_window_inside_the_span_holds_the_note(client):
    made = _save(client, "Conference 3 to 7 March 2031.")
    plain = _save(client, "Dentist on 3 March 2031.")
    middle = {r["id"] for r in _rows(client, "2031-03-05T00:00:00", "2031-03-05T23:59:59")}
    after = {r["id"] for r in _rows(client, "2031-03-08T00:00:00", "2031-03-08T23:59:59")}
    assert made["id"] in middle and plain["id"] not in middle
    assert made["id"] not in after


def test_a_day_row_carries_no_until(client):
    made = _save(client, "Dentist on 3 March 2031.")
    row = next(r for r in _rows(client, "2031-03-03T00:00:00", "2031-03-03T23:59:59") if r["id"] == made["id"])
    assert row.get("until") is None
