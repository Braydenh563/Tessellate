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
    assert said("what's tomorrow's date") == "Tomorrow is Monday 9 November 2026.\n\n_Read as tomorrow as Monday 9 November 2026._"
    assert said("what was yesterday's date") == "Yesterday was Saturday 7 November 2026.\n\n_Read as yesterday as Saturday 7 November 2026._"
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
