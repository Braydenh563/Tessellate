"""Time words, the class (INBOX 1357 "fix the class"; composer9-1026 Remaining:
"over the weekend", "last fortnight" and the rest of that class).

Fixed clock: Wednesday 21 October 2026 (this week is Mon 19 to Sun 25 October,
last week 12 to 18, the weekend just gone Sat 17 and Sun 18). Every phrase is
read three ways: alone (`when.span`), inside a question (`when.find` returns the
whole phrase, preposition and all) and as a window (`when.window`, ending now at
the latest)."""

from __future__ import annotations

from datetime import date, datetime

import pytest

from tessellate.ai import when

NOW = datetime(2026, 10, 21, 10, 0)
TODAY = NOW.date()


def d(month: int, day: int, year: int = 2026) -> date:
    return date(year, month, day)


#: (phrase, first day, last day)
WINDOWS = [
    # The weekend just gone, said any way round.
    ("over the weekend", d(10, 17), d(10, 18)),
    ("the weekend", d(10, 17), d(10, 18)),
    ("at the weekend", d(10, 17), d(10, 18)),
    ("on the weekend", d(10, 17), d(10, 18)),
    ("during the weekend", d(10, 17), d(10, 18)),
    ("over the week-end", d(10, 17), d(10, 18)),
    ("this past weekend", d(10, 17), d(10, 18)),
    ("the past weekend", d(10, 17), d(10, 18)),
    ("the weekend just gone", d(10, 17), d(10, 18)),
    ("last weekend", d(10, 17), d(10, 18)),
    # A fortnight is fourteen days, like "last two weeks".
    ("last fortnight", d(10, 7), d(10, 21)),
    ("the last fortnight", d(10, 7), d(10, 21)),
    ("the past fortnight", d(10, 7), d(10, 21)),
    ("over the last fortnight", d(10, 7), d(10, 21)),
    ("the previous fortnight", d(10, 7), d(10, 21)),
    ("the last two weeks", d(10, 7), d(10, 21)),
    ("a fortnight ago", d(10, 7), d(10, 7)),
    # This, last, past N days, weeks, months, with or without a preposition.
    ("in the last week", d(10, 14), d(10, 21)),
    ("over the last week", d(10, 14), d(10, 21)),
    ("within the last week", d(10, 14), d(10, 21)),
    ("during the past week", d(10, 14), d(10, 21)),
    ("the last week", d(10, 14), d(10, 21)),
    ("this past week", d(10, 14), d(10, 21)),
    ("in the last 3 days", d(10, 18), d(10, 21)),
    ("over the last three days", d(10, 18), d(10, 21)),
    ("these last few days", d(10, 18), d(10, 21)),
    ("these past few days", d(10, 18), d(10, 21)),
    ("the last few days", d(10, 18), d(10, 21)),
    ("the last couple of days", d(10, 19), d(10, 21)),
    ("the past 7 days", d(10, 14), d(10, 21)),
    ("in the past 3 weeks", d(9, 30), d(10, 21)),
    ("over the past month", d(9, 21), d(10, 21)),
    ("in the last month", d(9, 21), d(10, 21)),
    ("this past month", d(9, 21), d(10, 21)),
    ("within the last 2 months", d(8, 21), d(10, 21)),
    ("over the last couple of months", d(8, 21), d(10, 21)),
    ("in the past year", date(2025, 10, 21), d(10, 21)),
    ("in the last 24 hours", d(10, 20), d(10, 21)),
    ("in the past 48 hours", d(10, 19), d(10, 21)),
    ("in the last few hours", d(10, 21), d(10, 21)),
    # Since a day, or a part of one.
    ("since monday", d(10, 19), d(10, 21)),
    ("since friday", d(10, 16), d(10, 21)),
    ("since yesterday", d(10, 20), d(10, 21)),
    ("since the weekend", d(10, 17), d(10, 21)),
    ("since last week", d(10, 12), d(10, 21)),
    ("since this morning", d(10, 21), d(10, 21)),
    ("since last night", d(10, 20), d(10, 21)),
    ("since the 15th", d(10, 15), d(10, 21)),
    ("since october", d(10, 1), d(10, 21)),
    # Earlier, so far, to date.
    ("earlier this week", d(10, 19), d(10, 21)),
    ("earlier this month", d(10, 1), d(10, 21)),
    ("earlier this year", d(1, 1), d(10, 21)),
    ("earlier today", d(10, 21), d(10, 21)),
    ("so far this week", d(10, 19), d(10, 21)),
    ("so far this month", d(10, 1), d(10, 21)),
    ("this week so far", d(10, 19), d(10, 21)),
    ("this month so far", d(10, 1), d(10, 21)),
    ("so far this year", d(1, 1), d(10, 21)),
    ("year to date", d(1, 1), d(10, 21)),
    ("month to date", d(10, 1), d(10, 21)),
    ("week to date", d(10, 19), d(10, 21)),
    # Part of a day, and the vague recent past.
    ("last night", d(10, 20), d(10, 20)),
    ("yesterday morning", d(10, 20), d(10, 20)),
    ("yesterday afternoon", d(10, 20), d(10, 20)),
    ("yesterday evening", d(10, 20), d(10, 20)),
    ("this morning", d(10, 21), d(10, 21)),
    ("this afternoon", d(10, 21), d(10, 21)),
    ("this evening", d(10, 21), d(10, 21)),
    ("the other day", d(10, 17), d(10, 19)),
    ("this time last week", d(10, 14), d(10, 14)),
    ("this time last month", d(9, 21), d(9, 21)),
    ("this time last year", date(2025, 10, 21), date(2025, 10, 21)),
    # The units before this one.
    ("the previous week", d(10, 12), d(10, 18)),
    ("the previous month", d(9, 1), d(9, 30)),
    ("the month before last", d(8, 1), d(8, 31)),
    ("the year before last", date(2024, 1, 1), date(2024, 12, 31)),
    ("last quarter", d(7, 1), d(9, 30)),
    ("this quarter", d(10, 1), d(12, 31)),
    ("the previous quarter", d(7, 1), d(9, 30)),
    # Held: the forms that already read.
    ("last week", d(10, 12), d(10, 18)),
    ("this week", d(10, 19), d(10, 25)),
    ("yesterday", d(10, 20), d(10, 20)),
    ("3 days ago", d(10, 18), d(10, 18)),
    ("the past 3 days", d(10, 18), d(10, 21)),
    ("last month", d(9, 1), d(9, 30)),
    ("in august", d(8, 1), d(8, 31)),
    ("last friday", d(10, 16), d(10, 16)),
]


@pytest.mark.parametrize(("phrase", "first", "last"), WINDOWS, ids=[w[0] for w in WINDOWS])
def test_a_phrase_is_read_alone(phrase, first, last):
    got = when.span(phrase, TODAY, "past")
    assert got is not None, phrase
    assert (got[0], got[1]) == (first, last)


@pytest.mark.parametrize(("phrase", "first", "last"), WINDOWS, ids=[w[0] for w in WINDOWS])
def test_a_phrase_is_found_whole_inside_a_question(phrase, first, last):
    question = f"what did I do {phrase}?"
    found = when.find(question)
    assert found, question
    start, end, said = found[0]
    #: The whole phrase, so the words around it are the question's own and
    #: nothing of the phrase is left behind as a subject.
    assert question[start:end].lower() == phrase, (question, said)
    got = when.span(said, TODAY, "past")
    assert got is not None and (got[0], got[1]) == (first, last)


@pytest.mark.parametrize(
    ("phrase", "first"),
    [("over the weekend", d(10, 17)), ("earlier this week", d(10, 19)), ("since monday", d(10, 19)), ("the other day", d(10, 17))],
)
def test_a_window_ends_now_and_starts_on_the_first_day(phrase, first):
    start, end = when.window(phrase, NOW)
    assert start.date() == first and end <= NOW


def test_a_weekend_is_the_one_just_gone_whatever_the_day():
    saturday = date(2026, 10, 24)
    sunday = date(2026, 10, 25)
    monday = date(2026, 10, 26)
    assert when.span("over the weekend", saturday, "past")[:2] == (saturday, saturday + (sunday - saturday))
    assert when.span("over the weekend", sunday, "past")[:2] == (saturday, sunday)
    assert when.span("over the weekend", monday, "past")[:2] == (saturday, sunday)


def test_a_coming_weekend_is_the_next_one():
    assert when.span("over the weekend", TODAY, "future")[:2] == (d(10, 24), d(10, 25))


@pytest.mark.parametrize("phrase", ["over the", "the last", "in the", "fortnight", "earlier", "this past", "so far"])
def test_half_a_phrase_is_not_a_window(phrase):
    assert when.span(phrase, TODAY, "past") is None


@pytest.mark.parametrize(
    "question",
    [
        "the last day of this month",
        "on the last day of the month",
        "the last week of the term",
        "the last month of the year",
        "the last day of october",
        "the last hour of the shift",
    ],
)
def test_a_last_unit_of_something_is_a_place_not_a_run_of_days(question):
    """"The last day of this month" must stay the month's last day: the run of
    days the new singular forms read ("the last week") stops at an "of"."""
    found = when.find(question)
    for _start, _end, phrase in found:
        assert " of" in phrase or phrase.split()[-1] not in {"day", "week", "month", "hour"}, (question, phrase)
