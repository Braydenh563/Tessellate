"""The fortnight ahead and the weekends (owner brief, 2026-10-27: "next
fortnight" and "last weekend" were not read as time windows).

Fixed clock: Wednesday 21 October 2026 (this week Mon 19 to Sun 25 October,
the weekend just gone Sat 17 and Sun 18, the coming one Sat 24 and Sun 25).
`last weekend` already read; it is held here with the weekends beside it."""

from __future__ import annotations

from datetime import date, datetime

import pytest

from tessellate.ai import recognise

NOW = datetime(2026, 10, 21, 10, 0)
TODAY = NOW.date()


def d(month: int, day: int) -> date:
    return date(2026, month, day)


#: (phrase, tense, first day, last day)
SPANS = [
    ("next fortnight", None, d(10, 22), d(11, 4)),
    ("the next fortnight", None, d(10, 22), d(11, 4)),
    ("in the next fortnight", None, d(10, 22), d(11, 4)),
    ("over the coming fortnight", None, d(10, 22), d(11, 4)),
    ("coming fortnight", "future", d(10, 22), d(11, 4)),
    ("last weekend", "past", d(10, 17), d(10, 18)),
    ("last weekend", None, d(10, 17), d(10, 18)),
    ("this weekend", "past", d(10, 17), d(10, 18)),
    ("this weekend", None, d(10, 24), d(10, 25)),
    ("next weekend", None, d(10, 31), d(11, 1)),
]


@pytest.mark.parametrize(("phrase", "tense", "first", "last"), SPANS, ids=[f"{s[0]}-{s[1]}" for s in SPANS])
def test_a_phrase_is_read_alone(phrase, tense, first, last):
    got = recognise.span(phrase, TODAY, tense)
    assert got is not None, phrase
    assert (got[0], got[1]) == (first, last)


@pytest.mark.parametrize(
    ("question", "said"),
    [
        ("what is due next fortnight", "next fortnight"),
        ("what is on in the next fortnight", "in the next fortnight"),
        ("what did I do last weekend", "last weekend"),
        ("what did I write this weekend", "this weekend"),
    ],
)
def test_a_phrase_is_found_in_a_question(question, said):
    assert [p for _s, _e, p in recognise.find(question)] == [said]
    assert said not in recognise.without_windows(question)
    assert recognise.looks_dated(question)


def test_a_window_never_ends_after_now():
    #: The fortnight ahead is no question's past window: None, never a guess.
    assert recognise.window("next fortnight", NOW) is None
    got = recognise.window("last weekend", NOW)
    assert got == (datetime(2026, 10, 17, 0, 0), datetime(2026, 10, 18, 23, 59, 59))


def test_the_fortnight_behind_still_reads():
    assert recognise.span("last fortnight", TODAY, "past")[:2] == (d(10, 7), d(10, 21))


#: Mon 19 to Sun 25 October 2026: whichever day it is asked, "last weekend" is
#: the Saturday and Sunday before the current week's end, never the one under way.
@pytest.mark.parametrize("day", range(19, 26))
def test_the_weekends_are_the_right_ones_on_every_weekday(day):
    today = date(2026, 10, day)
    last = recognise.span("last weekend", today, None)
    assert (last[0], last[1]) == (d(10, 17), d(10, 18))
    assert last[0].weekday() == 5 and (last[1] - last[0]).days == 1
    this = recognise.span("this weekend", today, None)
    assert (this[0], this[1]) == ((d(10, 24), d(10, 25)))
    following = recognise.span("next weekend", today, None)
    assert (following[0], following[1]) == (d(10, 31), d(11, 1))
