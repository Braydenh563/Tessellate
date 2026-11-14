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
