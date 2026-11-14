"""Numbers spoken in words are read by the dates utility ("twenty-one days" is 21)."""

from datetime import datetime

import pytest

from tessellate.ai import number_words, utilities

NOW = datetime(2026, 11, 10, 9, 0)


@pytest.mark.parametrize(("said", "number"), [("one", 1), ("nineteen", 19), ("twenty", 20), ("twenty-one", 21), ("forty two", 42), ("ninety-nine", 99)])
def test_number_words_are_read(said, number):
    assert number_words.value(said) == number


@pytest.mark.parametrize("said", ["", "hundred", "twenty-twenty", "five one", "banana"])
def test_not_a_number(said):
    assert number_words.value(said) is None


@pytest.mark.parametrize("ask", ["what day is it gonna be in twenty-one days", "what day is it in 21 days"])
def test_offset_in_words_matches_digits(ask):
    assert utilities.answer(ask, NOW)[0][1] == "21 days from today is Tuesday 1 December 2026."


def test_thirty_five_days_ago():
    assert "35 days ago is Tuesday 6 October 2026" in utilities.answer("what day was it thirty five days ago", NOW)[0][1]


def test_calender_slip_is_read():
    assert "Wednesday 11 November 2026" in utilities.answer("calender says tomorrow is", NOW)[0][1]
