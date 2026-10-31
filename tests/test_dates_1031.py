"""Audit 1031 N8: "the 14th of next month" is that day, and a month-only
mention is shown as the month."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from tessellate.entry import timewords

TODAY = date(2026, 10, 31)  # a fixed clock, never the real one


@pytest.mark.parametrize(
    "text, day",
    [
        ("Pay rent on the 14th of next month", date(2026, 11, 14)),
        ("the 2nd of last month", date(2026, 9, 2)),
        ("the 1st of this month", date(2026, 10, 1)),
        ("the 3rd day of next month", date(2026, 11, 3)),
        ("the 5th of next month", date(2026, 11, 5)),
    ],
)
def test_an_ordinal_with_a_relative_month_is_a_day(text, day):
    (mention,) = timewords.find(text, TODAY)
    assert (mention.at, mention.precision) == (day, "day")


def test_a_month_that_has_no_such_day_is_not_invented():
    # The 31st of next month (November has 30): the month it names, not a day.
    (mention,) = timewords.find("the 31st of next month", TODAY)
    assert mention.precision == "month"


def test_next_month_alone_is_still_a_month():
    (mention,) = timewords.find("next month", TODAY)
    assert mention.precision == "month"


def test_the_chip_shows_a_month_as_the_month():
    cards = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "note-cards.js").read_text()
    assert '`${when.precision} of ${dayLabel}`' not in cards
    assert 'when.precision === "month"' in cards
