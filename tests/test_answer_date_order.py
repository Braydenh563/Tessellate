"""Answers say a day the way the person's locale reads it (CHAT_PLAN decision 43,
L563): en-US "April 3, 2025", elsewhere "3 April 2025". Quotes stay the note's own words."""

from __future__ import annotations

from datetime import date

import pytest

from tessellate.ai import realise, recognise
from tessellate.ai.composer_answer import _Answer


@pytest.fixture(autouse=True)
def _reset():
    before = dict(recognise._HEMISPHERE)
    yield
    recognise._HEMISPHERE.update(before)
    recognise.configure_date_order("auto")


@pytest.mark.parametrize(
    ("text", "said"),
    [
        ("written 3 April", "written April 3"),
        ("written 3 April 2025, about Friday 28 February", "written April 3, 2025, about Friday February 28"),
        ("on 1 October.", "on October 1."),
        ("the 3 April 2025 trip", "the April 3, 2025 trip"),
        ("it costs 3 apples", "it costs 3 apples"),
        ("May 3 stays", "May 3 stays"),
    ],
)
def test_month_first_says_the_day_month_first(text, said):
    assert realise.month_first_days(text) == said


def test_answer_measured_day_follows_the_request_locale():
    answer = _Answer({}, date(2026, 6, 1))
    answer.t("written_on").m(answer.day(date(2025, 4, 3)))
    recognise.note_locale("en-GB")
    assert "3 April 2025" in answer.text
    recognise.note_locale("en-US")
    assert "April 3, 2025" in answer.text
    assert "3 April" not in answer.text


def test_a_quote_is_never_reordered():
    answer = _Answer({}, date(2026, 6, 1))
    answer.parts.append(("quote", "Flight lands 3 April.", 1))
    recognise.note_locale("en-US")
    assert answer.text == "Flight lands 3 April."


def test_date_order_setting_wins_over_the_locale():
    answer = _Answer({}, date(2026, 6, 1))
    answer.m("3 April")
    recognise.note_locale("en-GB")
    recognise.configure_date_order("month")
    assert answer.text == "April 3"
    recognise.note_locale("en-US")
    recognise.configure_date_order("day")
    assert answer.text == "3 April"


@pytest.mark.parametrize("question", ["when did I write the harbor launch plan", "when was Lisbon, where to stay written"])
def test_a_composed_when_answer_says_the_day_by_locale(question):
    from tessellate.ai import composer
    from tests.test_composer_688 import NOTES, TODAY

    recognise.note_locale("en-GB")
    gb = composer.compose(question, NOTES, today=TODAY)["text"]
    recognise.note_locale("en-US")
    us = composer.compose(question, NOTES, today=TODAY)["text"]
    assert " 6 September" in gb or " 11 September" in gb
    assert "September 6" in us or "September 11" in us
    assert " 6 September" not in us and " 11 September" not in us
