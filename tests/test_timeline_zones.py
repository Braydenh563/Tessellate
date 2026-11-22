"""A reader outside UTC sees a typed day on the day it names (LEDGER L914, part a).

Measured in Chromium with `timezoneId` America/Los_Angeles and Asia/Kolkata:
"Dentist 2026-11-20 at 3pm" plus a reminder due 15:00 local land in the 20 Nov
calendar cell at "3:00 PM", in the feed's 2026-11-20 bucket at "3:00 PM", and
the reminders tab says "Fri, Nov 20, 3:00 PM"; the app sent `tz=-480` and
`tz=330`. A mentioned time is the writer's wall clock with no zone, so it must
come back as written and sit inside the reader's own day window in both zones.
"""

from __future__ import annotations

import pytest

ZONES = [("America/Los_Angeles", -480), ("Asia/Kolkata", 330)]


def _ids(client, start: str, end: str, tz: int) -> set[int]:
    body = client.get(f"/timeline?kind=note&start={start}&end={end}&tz={tz}&limit=1000").json()
    return {row["id"] for row in body["rows"]}


def _utc(day: str, tz: int, end: bool = False) -> tuple[str, str]:
    from datetime import datetime, timedelta

    start = datetime.fromisoformat(f"{day}T00:00:00") - timedelta(minutes=tz)
    stop = start + timedelta(days=1, seconds=-1)
    return start.isoformat(), stop.isoformat()


@pytest.mark.parametrize(("zone", "tz"), ZONES)
def test_the_note_keeps_its_wall_clock_and_sits_in_the_readers_own_day(client, zone, tz):
    made = client.post("/entries", json={"content": "Dentist 2026-11-20 at 3pm"})
    assert made.status_code == 201
    note = made.json()["id"]
    rows = client.get(f"/timeline?kind=note&days=0&tz={tz}&limit=1000").json()["rows"]
    row = next(r for r in rows if r["id"] == note)
    assert row["placed_by"] == "mentioned"
    assert (row["date"], row["time"], row["at"]) == ("2026-11-20", "15:00", "2026-11-20T15:00:00"), zone
    assert note in _ids(client, *_utc("2026-11-20", tz), tz)
    assert note not in _ids(client, *_utc("2026-11-19", tz), tz)
    assert note not in _ids(client, *_utc("2026-11-21", tz), tz)
