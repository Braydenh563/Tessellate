"""A typed entry lands on the day it names (TIMELINE_PLAN 10 row 5).

Twenty phrases typed as plain notes, read against a fixed Sunday, each have to
come back from `/timeline` on the day the words name, placed "mentioned" and
carrying the phrase. The reading is `entry/timewords.py` (the one reader a note
is read by); this holds the whole path, save to row, so a change to either end
cannot move a note off its day without a failure. A bare weekday after a past
verb ("called mum on friday") is left out on purpose: it is an owner decision
in docs/roadmap/archive/agent-remaining/timeline-1018.md, not a measured gap.
"""

from __future__ import annotations

from datetime import datetime

import pytest

#: Sunday, so "next tuesday" and "last friday" cross a week boundary.
NOW = datetime(2026, 10, 18, 12, 0)

PHRASES = [
    ("yesterday lunch with Sam", "2026-10-17"),
    ("dentist appointment tomorrow", "2026-10-19"),
    ("last monday standup notes", "2026-10-12"),
    ("the day before yesterday I fixed the bike", "2026-10-16"),
    ("meeting on october 3", "2026-10-03"),
    ("went hiking on 2026-10-04", "2026-10-04"),
    ("two days ago passport photos", "2026-10-16"),
    ("budget review next tuesday", "2026-10-20"),
    ("dinner at 7pm yesterday", "2026-10-17"),
    ("flight on oct 25", "2026-10-25"),
    ("last friday retro", "2026-10-16"),
    ("today I started the garden plan", "2026-10-18"),
    ("3 days ago call with landlord", "2026-10-15"),
    ("tomorrow morning gym", "2026-10-19"),
    ("on 5 october painted the hall", "2026-10-05"),
    ("yesterday evening piano", "2026-10-17"),
    ("the deadline is in 2 weeks", "2026-11-01"),
    ("three weeks ago we moved house", "2026-09-27"),
    ("Friday 23 October dentist", "2026-10-23"),
    ("in 5 days renew the passport", "2026-10-23"),
]


@pytest.fixture
def fixed_clock(monkeypatch):
    monkeypatch.setattr("tessellate.core.config.user_now", lambda *_a, **_k: NOW)


def test_twenty_typed_phrases_land_on_the_day_they_name(client, fixed_clock):
    saved = {}
    for text, _ in PHRASES:
        response = client.post("/entries", json={"content": text})
        assert response.status_code == 201
        saved[text] = response.json()["id"]
    rows = {row["id"]: row for row in client.get("/timeline?kind=note&scale=day&limit=200").json()["rows"]}
    wrong = []
    for text, day in PHRASES:
        row = rows[saved[text]]
        if row["placed_by"] != "mentioned" or row["date"][:10] != day or not row["phrase"]:
            wrong.append((text, day, row["date"], row["placed_by"]))
    assert wrong == [], f"{len(PHRASES) - len(wrong)} of {len(PHRASES)} landed on their day: {wrong}"
