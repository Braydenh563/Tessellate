"""The model is told what day it is, and does not have to work it out.

The owner's transcript, 2026-09-21. He had a note saying an assignment was
due "Friday", asked for a reminder two hours before midnight, and got one for
the wrong night. The model's own reasoning shows both faults:

    "The current date and time is 2026-09-21T15:55:00+10:00 (AEST).
     Midnight for today, September 21st, is 2026-09-22T00:00.
     2 hours before midnight is 2026-09-22T22:00."

Two hours before that midnight is the 21st at 22:00, not the 22nd. And
"Friday" was never resolvable at all: an ISO timestamp does not say what
weekday it is, so a small model has to derive one, which is the arithmetic
these models are worst at.

Both are the prompt's fault rather than the model's, because both facts were
cheap to state and were not stated. These tests hold them stated.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

import pytest

WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


@pytest.fixture()
def system_prompt(client):
    """The assembled system prompt, reached the way the app reaches it."""
    from tessellate.ai import agent_turn

    return agent_turn.build_agent_messages("what is due?", [])[0]["content"]


def test_the_prompt_names_the_weekday(system_prompt):
    assert any(day in system_prompt for day in WEEKDAYS), (
        "the prompt gives a date with no weekday, so 'due Friday' cannot be "
        "placed without the model counting days"
    )


def test_the_prompt_names_the_week_ahead(system_prompt):
    """Seven short dates, so any weekday the user names is a lookup."""
    found = re.findall(r"\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun) \d{1,2} \w{3}\b", system_prompt)
    assert len(found) >= 7, f"only {len(found)} of the coming days are named: {found}"


def test_the_slip_in_his_transcript_is_the_app_s_arithmetic_now(system_prompt, session):
    """INBOX 527: the "still today" sentence taught the model arithmetic; the
    tool now takes his words and the app resolves them, so the prompt no
    longer teaches it and the reminder lands on the right night."""
    from zoneinfo import ZoneInfo

    from tessellate.ai import when

    assert "still today's date" not in system_prompt
    assert "compute" not in system_prompt.split("set_reminder", 1)[1][:120]
    now = datetime(2026, 9, 21, 15, 55, tzinfo=ZoneInfo("Australia/Brisbane"))
    assert when.resolve("two hours before midnight", now).strftime("%d %H:%M") == "21 22:00"


def test_the_clock_is_still_the_last_thing(system_prompt):
    """The daily part changes once a day and the timestamp every minute, so
    the timestamp goes last or the prefix cache is invalidated by the part
    that did not change. `test_prompt_prefix_stability.py` holds the rule for
    the whole prompt; this holds it inside the clock sentence, which is where
    it was got wrong first."""
    clock = system_prompt.rindex("The current date and time is")
    weekday = system_prompt.rindex("Today is")
    assert weekday < clock, "the weekday must come before the minute, not after"


def test_the_week_is_computed_from_the_user_s_own_clock():
    """Not the server's. The days after a local Monday evening are a Tuesday,
    and in UTC that same instant may already be Tuesday, which would name the
    wrong seven days."""
    local = datetime(2026, 9, 21, 15, 55, tzinfo=timezone(timedelta(hours=10)))
    week = [(local + timedelta(days=n)).strftime("%a") for n in range(1, 8)]
    assert week[0] == "Tue", week
    assert week[3] == "Fri", "the Friday he was asking about is four days on"
