"""Sums and countdowns the utilities eval (L-chat-22) found unread: comma
grouped numbers, mod, factorial, word numbers, and weeks until a day."""

from datetime import datetime

import pytest

from tessellate.ai import utilities

NOW = datetime(2026, 11, 14, 10, 0)


def _said(question: str) -> str:
    parts = utilities.answer(question, now=NOW)
    assert parts, f"{question!r} was not answered"
    return "".join(p[1] for p in parts)


@pytest.mark.parametrize(("question", "value"), [
    ("1,000 + 250", "1,250"),
    ("what is 2,500 * 2", "5,000"),
    ("what is 1,000,000 / 4", "250,000"),
])
def test_comma_grouped_numbers_are_read(question, value):
    assert f" is {value}." in _said(question)


def test_a_comma_grouped_sum_is_its_own_reading():
    assert "Read as" not in _said("1,000 + 250")


@pytest.mark.parametrize(("question", "value"), [("what is 10 mod 3", "1"), ("17 modulo 5", "2")])
def test_mod_is_the_remainder(question, value):
    said = _said(question)
    assert f" is {value}." in said and "Read as" in said and "mod" in said.split("Read as")[1]


@pytest.mark.parametrize(("question", "value"), [("what is 7!", "5,040"), ("factorial of 5", "120"), ("what's 0!", "1")])
def test_factorial(question, value):
    said = _said(question)
    assert f" is {value}." in said and "factorial" in said


def test_a_factorial_past_the_range_is_not_computed():
    assert utilities.answer("what is 40!", now=NOW) is None


@pytest.mark.parametrize(("question", "value"), [
    ("what is twelve plus thirty", "42"),
    ("five times seven", "35"),
    ("what is one hundred and five minus five", "100"),
    ("twenty one divided by three", "7"),
])
def test_word_numbers_are_read(question, value):
    said = _said(question)
    assert f" is {value}." in said and "Read as" in said


def test_weeks_until_a_day_are_said_in_weeks():
    said = _said("how many weeks until 1 December")
    assert "2 weeks and 3 days away" in said, said


def test_weeks_until_a_day_a_whole_number_of_weeks_away():
    assert "3 weeks away" in _said("how many weeks until 5 December")


def test_days_until_stays_in_days():
    assert "17 days away" in _said("how many days until 1 December")


@pytest.mark.parametrize("question", ["10 ton to kg", "convert 3 tons to pounds", "2 kg in tons"])
def test_a_bare_ton_asks_which_ton_it_is(question):
    """L-chat-118 (T2): ton, tons are metric, short or long, so the answer asks."""
    said = _said(question)
    assert "Which one do you mean" in said and "short tons" in said and "gon" not in said


@pytest.mark.parametrize(("question", "value"), [("2 short tons to kg", "1,814.4"), ("1 tonne to kg", "1,000")])
def test_a_named_ton_still_converts(question, value):
    assert value in _said(question)


@pytest.mark.parametrize(
    ("question", "said"),
    [
        ("how old is 3 March 1990", "3 March 1990 is 36 years, 8 months and 11 days ago."),
        ("how long ago was 14 November 2025", "1 year ago"),
        ("how old is 14 October 2026", "1 month"),
    ],
)
def test_how_old_is_a_date(question, said):
    """L-chat-120 (T4): the age of a dated day, in years, months and days."""
    assert said in _said(question) and "Read as the time from" in _said(question)
