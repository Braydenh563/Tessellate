"""The Timeline's "On this day" range (TIMELINE_PLAN section 8: Day One's
"On this day", the cheap Phase 4 addition).

`GET /timeline?on=MM-DD&tz=<minutes east of UTC>` keeps what was written on
that calendar day in an earlier month or year, in the reader's own day, and
leaves today out: the same rule as the Dashboard's On this day widget, so the
two can never disagree. Server side, because a client-side filter over a paged
feed would only find last year's page once someone had scrolled to it.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from tessellate.core.database import Entry
from tests._app_js import frontend_text


def _at(session, client, text, when):
    made = client.post("/entries", json={"content": text}).json()
    session.get(Entry, made["id"]).created_at = when
    session.commit()
    return made["id"]


def _ids(client, **params):
    body = client.get("/timeline", params={"days": 0, **params}).json()
    return {row["id"] for row in body["rows"] if row["kind"] == "note"}


def test_the_same_day_in_earlier_years_and_months(client, session):
    now = datetime.now(timezone.utc)
    year_ago = _at(session, client, "a year ago", now.replace(year=now.year - 1))
    two_years = _at(session, client, "two years ago", now.replace(year=now.year - 2))
    other_day = _at(session, client, "another day", now - timedelta(days=3))
    today = _at(session, client, "today", now)
    on = f"{now.month:02d}-{now.day:02d}"
    got = _ids(client, on=on, tz=0)
    assert {year_ago, two_years} <= got
    assert other_day not in got and today not in got


def test_a_month_ago_on_the_same_date_counts(client, session):
    # The widget's other half: an earlier month this year, same date.
    note = _at(session, client, "February", datetime(2026, 2, 14, 12, tzinfo=timezone.utc))
    assert note in _ids(client, on="02-14", tz=0)
    assert note not in _ids(client, on="02-15", tz=0)


def test_the_readers_own_day_not_utcs(client, session):
    # 23:30 UTC on 4 March is already 5 March for a reader at UTC+10.
    late = _at(session, client, "late", datetime(2024, 3, 4, 23, 30, tzinfo=timezone.utc))
    assert late in _ids(client, on="03-05", tz=600)
    assert late not in _ids(client, on="03-05", tz=0)
    assert late in _ids(client, on="03-04", tz=0)


def test_a_bad_day_is_refused(client):
    assert client.get("/timeline", params={"on": "13-45"}).status_code == 422
    assert client.get("/timeline", params={"on": "3-5"}).status_code == 422


def test_the_years_are_one_select_in_the_strip_head_not_a_row_of_chips():
    """"that year button in the timeline takes up a whole row on its own"
    (INBOX 842). The year filter is `#timeline-year` in the day strip's head,
    beside the month picker; `renderTimelineRecall` no longer builds a chip per
    year, so the recall row holds only On this day chips and is hidden
    without them."""
    from pathlib import Path

    
    html = (Path(__file__).resolve().parents[1] / "frontend" / "index.html").read_text(encoding="utf-8")
    head = html[html.index('class="timeline-daystrip-head"') :]
    head = head[: head.index('id="timeline-daystrip-days"')]
    assert 'id="timeline-year"' in head and 'id="timeline-month-btn"' in head
    js = frontend_text("timeline.js")
    assert "function syncTimelineYears(" in js
    assert 'button(`${year} (${count})`' not in js
