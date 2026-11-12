"""Batch B of small-rows-1108, row U17. Answers are composed with no model (CHAT_PLAN decision 75: a running model leads) on a fixed clock."""

from __future__ import annotations

from datetime import date

import pytest

from tessellate.ai import composer_numbers
from tessellate.ai.composer import plan

TODAY = date(2026, 11, 8)


# --- U17: spelled numbers --------------------------------------------------------------

@pytest.mark.parametrize(
    ("said", "read"),
    [
        ("list the twenty notes", "list the 20 notes"),
        ("show me the last two notes", "show me the last 2 notes"),
        ("twenty-five notes", "25 notes"),
        ("thirty two days", "32 days"),
        ("I have one note and three tags", "I have 1 note and three tags"),
        ("the last two weeks", "the last 2 weeks"),
        ("the past three months", "the past 3 months"),
        ("Five notes about the garden", "5 notes about the garden"),
        #: Names and sayings stay as typed (review of batch B): only a count of units is a digit.
        ("the seven habits", "the seven habits"),
        ("twenty-one pilots", "twenty-one pilots"),
        ("Ocean's eleven", "Ocean's eleven"),
        ("the one thing", "the one thing"),
        ("fifty fifty", "fifty fifty"),
        ("Five Guys menu", "Five Guys menu"),
        ("which one is it", "which one is it"),
        ("no one knows", "no one knows"),
        ("the Five Guys menu", "the Five Guys menu"),
        ('find "two of us" please', 'find "two of us" please'),
        ("three hundred notes", "three hundred notes"),
        ("the second note", "the second note"),
    ],
)
def test_number_words_become_digits_ahead_of_the_rules(said, read):
    assert composer_numbers.normalise(said) == read


def test_the_plan_sees_the_digit_a_spelled_number_stands_for():
    assert plan("what did I write in the last fifteen days", TODAY).window == (date(2026, 10, 24), TODAY)


def test_a_spelled_count_is_not_a_subject_to_search_for():
    assert "twenty" not in plan("list the twenty notes", TODAY).terms
    assert "20" in plan("list the twenty notes", TODAY).terms


def test_two_weeks_ago_reads_the_same_before_and_after_normalising():
    from tessellate.entry import timewords

    def read(text):
        return [(m.at, m.precision) for m in timewords.find(text, TODAY)]

    assert read(composer_numbers.normalise("two weeks ago")) == read("two weeks ago") == [(date(2026, 10, 25), "day")]
