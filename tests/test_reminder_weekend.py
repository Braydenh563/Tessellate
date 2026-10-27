"""A reminder said for "this weekend" / "next weekend" is due on the right
Saturday at 09:00 (the app's default hour for a day with no clock), from every
weekday. Read through `commands.read`, the call Chat's act path makes
(`reading.py`). Fixed clock: Monday 19 October 2026, 08:00, plus 0..6 days, so
09:00 is still ahead on each day.

On Sunday the weekend is under way and began yesterday: "this weekend" is then
today (Sunday), never the Saturday already gone."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from tessellate.ai import commands

MONDAY = datetime(2026, 10, 19, 8, 0)
DAYS = [MONDAY + timedelta(days=i) for i in range(7)]
SAT = datetime(2026, 10, 24, 9, 0)
NEXT_SAT = datetime(2026, 10, 31, 9, 0)


def _due(phrase: str, now: datetime) -> dict:
    got = commands.read(f"remind me {phrase} to water the plants", now)
    assert got is not None and got["intent"] == "reminder", (phrase, got)
    assert got["text"] == "Water the plants"
    return got


@pytest.mark.parametrize("now", DAYS, ids=[d.strftime("%a") for d in DAYS])
def test_this_weekend_is_the_coming_saturday_or_today_on_sunday(now):
    got = _due("this weekend", now)
    expected = now.replace(hour=9) if now.weekday() == 6 else SAT
    assert got["due_at"] == expected
    assert got["time_given"] is True


@pytest.mark.parametrize("now", DAYS, ids=[d.strftime("%a") for d in DAYS])
def test_next_weekend_is_the_saturday_after_this_one(now):
    got = _due("next weekend", now)
    assert got["due_at"] == NEXT_SAT
    assert got["time_given"] is True


@pytest.mark.parametrize("now", DAYS, ids=[d.strftime("%a") for d in DAYS])
def test_last_weekend_is_never_set_in_the_future(now):
    got = _due("last weekend", now)
    assert got["due_at"] == datetime(2026, 10, 17, 9, 0)
    assert got["time_given"] is False  # gone by: Chat asks when instead of setting it
