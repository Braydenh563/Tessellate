"""CHAT_PLAN T13: the calendar read off the clock, no model, no note.
Fixed clock: Sunday 8 November 2026, 10:00."""

from __future__ import annotations

import datetime as dt
import time

import pytest

from tessellate.ai import composer_clock, composer_extra, composer_study

NOW = dt.datetime(2026, 11, 8, 10, 0, 0)


def ctx(q: str, **extra) -> composer_study.Ctx:
    return composer_study.Ctx(question=q, notes=extra.pop("notes", []), now=extra.pop("now", NOW), seed="s", asked=q, **extra)


def said(q: str, **extra) -> str:
    reply = composer_extra.answer(ctx(q, **extra))
    return reply.text if reply else ""


@pytest.mark.parametrize("q", ["what week is it", "What week is it?", "what's the week number", "which week are we in", "what week of the year is it", "week number"])
def test_the_week(q):
    assert said(q) == "It is week 45 of 2026.\n\n_Read as the ISO week number of Sunday 8 November 2026 (weeks start on Monday)._"


def test_the_week_follows_the_iso_year():
    assert said("what week is it", now=dt.datetime(2027, 1, 1, 9)).startswith("It is week 53 of 2026.")


@pytest.mark.parametrize("q", ["what quarter is it", "which quarter are we in", "what's the current quarter"])
def test_the_quarter(q):
    assert said(q) == "It is quarter 4 of 2026, October to December.\n\n_Read as the calendar quarter of Sunday 8 November 2026._"


def test_the_day_of_the_year():
    assert said("what day of the year is it") == "Today is day 312 of 2026, and 53 days remain.\n\n_Read as day 312 of 365 for Sunday 8 November 2026._"
    assert said("what day of the year is it", now=dt.datetime(2026, 12, 30)).startswith("Today is day 364 of 2026, and 1 day remain")


def test_leap_year_totals():
    assert said("what day of the year is it", now=dt.datetime(2028, 12, 31)).startswith("Today is day 366 of 2028, and 0 days remain.")


def test_tomorrow_and_yesterday():
    assert said("what's tomorrow's date") == "Tomorrow is Monday 9 November 2026.\n\n_Read as the day after today._"
    assert said("what was yesterday's date") == "Yesterday was Saturday 7 November 2026.\n\n_Read as the day before today._"
    assert said("what was the date yesterday").startswith("Yesterday was Saturday 7 November 2026.")


def test_the_month_end_rolls_over():
    assert said("what's tomorrow's date", now=dt.datetime(2026, 12, 31)).startswith("Tomorrow is Friday 1 January 2027.")


@pytest.mark.parametrize("q", ["what week did I write the passport note", "what is the week plan", "what quarter did sales drop", "tomorrow's meeting", "what day of the year was the trip"])
def test_other_questions_are_left_alone(q):
    assert composer_clock.answer(ctx(q)) is None


def test_the_answer_ignores_the_model_voice_and_notes():
    private = [{"id": 1, "content": "Private: week 45 surprise.", "created_at": "2026-11-01", "private": True}]
    plain = said("what week is it")
    assert said("what week is it", voice="formal", notes=private, history=[{"role": "user", "content": "hi"}]) == plain
    assert "surprise" not in plain


@pytest.mark.parametrize("text", ["what week" + " " * 20000 + "x", "what " * 4000, "tomorrow" + " " * 20000 + "date", "what day of the year" + " is" * 7000])
def test_a_20k_text_is_linear(text):
    start = time.perf_counter()
    composer_clock.answer(ctx(text))
    assert time.perf_counter() - start < 0.5


WEEK_LEAP_LEFT = [
    ("what week is 3 march", "Tuesday 3 March 2026 was in week 10 of 2026.\n\n_Read as the ISO week number of Tuesday 3 March 2026 (weeks start on Monday)._"),
    ("what week number is christmas", "Friday 25 December 2026 is in week 52 of 2026.\n\n_Read as the ISO week number of Friday 25 December 2026 (weeks start on Monday)._"),
    ("week number of 1 january 2027", "Friday 1 January 2027 is in week 53 of 2026.\n\n_Read as the ISO week number of Friday 1 January 2027 (weeks start on Monday)._"),
    ("is 2028 a leap year", "2028 is a leap year: it has 366 days, and February has 29.\n\n_Read as the leap year rule: every fourth year, except centuries not divisible by 400._"),
    ("Is it a leap year?", "2026 is not a leap year: it has 365 days, and February has 28.\n\n_Read as the leap year rule: every fourth year, except centuries not divisible by 400._"),
    ("was 1900 a leap year", "1900 was not a leap year: it has 365 days, and February has 28.\n\n_Read as the leap year rule: every fourth year, except centuries not divisible by 400._"),
    ("was 2000 a leap year", "2000 was a leap year: it has 366 days, and February has 29.\n\n_Read as the leap year rule: every fourth year, except centuries not divisible by 400._"),
    ("is next year a leap year", "2027 is not a leap year: it has 365 days, and February has 28.\n\n_Read as the leap year rule: every fourth year, except centuries not divisible by 400._"),
    ("how many days are left in the year", "There are 53 days left in 2026, after today.\n\n_Read as the days from tomorrow to Thursday 31 December 2026._"),
    ("how many weeks left in the year", "There are 7.6 weeks (53 days) left in 2026, after today.\n\n_Read as the days from tomorrow to Thursday 31 December 2026._"),
    ("days remaining in this year", "There are 53 days left in 2026, after today.\n\n_Read as the days from tomorrow to Thursday 31 December 2026._"),
]


@pytest.mark.parametrize(("q", "text"), WEEK_LEAP_LEFT)
def test_week_of_a_date_leap_years_and_days_left(q, text):
    assert said(q) == text


def test_one_day_left_is_singular():
    assert said("how many days are left in the year", now=dt.datetime(2026, 12, 30)).startswith("There is 1 day left in 2026")


@pytest.mark.parametrize("q", ["what week is it", "what week is the exam", "is the leap year note done", "how many days are left in the project", "what week is xyz"])
def test_week_of_edge_cases_are_left_alone_or_current(q):
    got = said(q)
    assert got == "" or got.startswith("It is week 45")


@pytest.mark.parametrize("text", ["what week is" + " " * 20000 + "x", "is " + "a " * 9000 + "leap year", "how many days " * 2000, "week number of " + "3 " * 9000])
def test_a_20k_text_is_linear_for_the_date_readers(text):
    start = time.perf_counter()
    composer_clock.answer(ctx(text))
    assert time.perf_counter() - start < 0.5


def test_a_read_as_line_never_repeats_the_answer_it_follows():
    """L89 (Z49): the line says how the question was read, not the answer again.
    Decision 54 keeps the line; these two only echoed their own sentence."""
    from tessellate.ai import utilities

    assert "Monday 9 November 2026" not in said("what's tomorrow's date").split("_Read as")[1]
    assert "Saturday 7 November 2026" not in said("what was yesterday's date").split("_Read as")[1]
    assert utilities._CLOCK_READ[1] == "\nRead as this computer's clock."
