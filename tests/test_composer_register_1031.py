"""A day a note named, said in the register of the question (the owner,
2026-10-31, verbatim: "or the dates as they are referred could be changed in
how they are referred based on context or percieved user speech patterns or
emotion etc.").

One rule table (`composer_digest._SAY_WHEN`), each row by several phrasings:
the base form leads with how far back (INBOX 1483: "three weeks ago, on 8
October", never "on 8 October (three weeks ago)"); "when did I" and "what
date" get the date first ("on 8 October, about three weeks ago"); "how long
ago" the distance first; a casual question the relative form; the person's own time words said back ("last week" for
"last week"); today and yesterday relative only; a distant day by its month.

Fixed clock: Friday 30 October 2026 (weeks start on Monday).
"""

from __future__ import annotations

import contextvars
import re
from datetime import date

import pytest

from tessellate.ai import composer_digest

TODAY = date(2026, 10, 30)


@pytest.fixture(autouse=True)
def _monday_first(monkeypatch):
    monkeypatch.setattr(composer_digest, "_week_first", lambda: 0)


def _said(question: str, text: str, written: date) -> str:
    #: In a copy of the context: the timing set here never reaches the
    #: next test in this worker (`test_gold_answers` pins against its own day).
    def run() -> str:
        composer_digest._TODAY.set(TODAY)
        composer_digest._set_timing(question)
        return composer_digest._pin(text, written)

    return contextvars.copy_context().run(run)


EVERY = ["tell me about the bus", "yooo what's up with the bus", "when did I miss the bus",
         "how long ago did I miss the bus", "what date did I miss the bus"]


@pytest.mark.parametrize("question", EVERY)
def test_yesterday_is_said_relatively_only(question):
    assert _said(question, "I missed the bus today", date(2026, 10, 29)) == "I missed the bus yesterday"


@pytest.mark.parametrize("question", ["what did I do last week", "anything happen last week?",
                                      "yo what went on last week", "what did I get up to last week lol"])
def test_their_last_week_is_said_back(question):
    assert _said(question, "I missed the bus today", date(2026, 10, 20)) == "I missed the bus last week"
    #: A day outside their words is said by the table as usual.
    assert _said(question, "I missed the bus today", date(2026, 10, 8)) == "I missed the bus three weeks ago"


@pytest.mark.parametrize("question", ["what did I do this month", "what happened this month",
                                      "how's this month been going"])
def test_their_this_month_is_said_back(question):
    assert _said(question, "I missed the bus today", date(2026, 10, 8)) == "I missed the bus this month"


@pytest.mark.parametrize("question", ["when did I miss the bus last week", "what day last week did I miss the bus",
                                      "which day did I miss the bus last week"])
def test_when_with_their_words_gives_the_date_then_their_words(question):
    #: INBOX 1483: their words after the date, not in brackets.
    assert _said(question, "I missed the bus today", date(2026, 10, 20)) == "I missed the bus on 20 October, last week"


@pytest.mark.parametrize("question", ["how long ago did I miss the bus", "how long since I missed the bus",
                                      "how long has it been since the bus thing"])
def test_how_long_ago_gives_the_distance_first(question):
    assert _said(question, "I missed the bus today", date(2026, 10, 8)) == "I missed the bus three weeks ago, on 8 October"
    assert _said(question, "I missed the bus today", date(2026, 7, 20)) == "I missed the bus three months ago, on 20 July"


@pytest.mark.parametrize("question", ["tell me about the bus", "what have I saved about the bus",
                                      "yooo what's been going on with the bus", "anything new recently"])
def test_a_distant_day_is_said_by_its_month(question):
    assert _said(question, "I missed the bus today", date(2026, 3, 10)) == "I missed the bus back in March"
    assert _said(question, "I missed the bus today", date(2025, 11, 3)) == "I missed the bus back in November 2025"


@pytest.mark.parametrize("question", ["when did I miss the bus", "what date did I miss the bus"])
def test_a_distant_day_still_has_its_date_when_asked_when(question):
    #: INBOX 1483: "about eight months ago" (234 days, rounded), not "(seven months ago)".
    assert _said(question, "I missed the bus today", date(2026, 3, 10)) == "I missed the bus on 10 March, about eight months ago"


@pytest.mark.parametrize("question", ["tell me about uni", "what have I saved about uni", "uni"])
def test_a_distant_week_is_said_by_its_month_in_the_past(question):
    said = _said(question, "my uni days this week are tuesday and thursday", date(2026, 3, 11))
    assert said == "my uni days back in March were tuesday and thursday", said


# A weekday in a note is pinned to the note's own week (item 4).

THURSDAY = date(2026, 9, 10)


@pytest.mark.parametrize(("text", "said"), [
    ("Group project meeting moved to Friday", "Group project meeting moved to Friday 11 September"),
    ("Tutorial changed to Thursday", "Tutorial changed to Thursday 10 September"),
    ("The exam is on Monday", "The exam was on Monday 14 September"),
    ("Lab report handed in on Monday", "Lab report handed in on Monday 7 September"),
    ("Slept badly on Tuesday", "Slept badly on Tuesday 8 September"),
    ("Dentist moved to next Tuesday", "Dentist moved to Tuesday 15 September"),
])
def test_a_weekday_is_its_weeks_day_and_past_once_gone(text, said):
    assert _said("tell me about uni", text, THURSDAY) == said


@pytest.mark.parametrize("text", ["Tutorial changed to Thursday next week", "Quiz on Friday 11 September",
                                  "Quiz on Friday, 11 Sep"])
def test_a_weekday_with_its_week_or_date_is_not_pinned_twice(text):
    said = _said("tell me about uni", text, THURSDAY)
    assert said.count("September") <= 1 and not re.search(r"\d+ September \d", said), said


@pytest.mark.parametrize("text", ["see Sam on friday", "gym on Monday"])
def test_a_note_of_today_keeps_its_weekday(text):
    assert _said("tell me about uni", text, TODAY) == text


@pytest.mark.parametrize("text", ["my uni days are tuesday and thursday", "Gym on Monday, Wednesday and Friday",
                                  "I swim on Tuesdays and Saturdays"])
def test_a_weekly_schedule_keeps_its_weekdays(text):
    said = _said("tell me about uni", text, THURSDAY)
    assert "September" not in said, said
