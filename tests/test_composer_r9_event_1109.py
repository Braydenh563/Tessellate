"""R9-7 (composer audit round 9): a yes/no ask about an event in a window says Yes, or says Not and when.
Seed: `tests/_seed_r9_1109.py`."""

from __future__ import annotations

from datetime import date

import pytest

import tests._seed_r9_1109 as sd
from tessellate.ai import composer_event_verdict as ev


@pytest.fixture
def say(client, session, monkeypatch):
    sd.seed(session)
    go = sd.asker(client, monkeypatch)
    return lambda q: go(q)[0]


def test_the_plumber_this_week_is_a_yes(say):
    assert say("is the plumber coming this week").startswith("Yes, plumber is coming Wednesday 11 November at 8am")


def test_the_plumber_next_week_is_a_not(say):
    assert say("is the plumber coming next week").startswith("Not next week: Plumber is coming Wednesday 11 November")


def test_the_plumber_with_no_window_has_no_verdict(say):
    assert say("is the plumber coming").startswith("Plumber is coming")


# 2026-11-09 is a Monday: the week is 9 to 15 November.
@pytest.mark.parametrize(("today", "window", "yes"), [
    (date(2026, 11, 9), "this week", True),
    (date(2026, 11, 15), "this week", True),
    (date(2026, 11, 16), "this week", False),
    (date(2026, 11, 14), "this weekend", True),
    (date(2026, 11, 20), "next month", False),
    (date(2026, 12, 2), "next month", True),
    (date(2026, 11, 10), "tomorrow", True),
    (date(2026, 11, 11), "today", False),
])
def test_window_edges(today, window, yes):
    day = f"{today.day} {today.strftime('%B')}"
    said = ev.verdict(f"is the party {window}", f"The party is on {day}.", date(2026, 11, 9))
    assert said.startswith("Yes, ") is yes
