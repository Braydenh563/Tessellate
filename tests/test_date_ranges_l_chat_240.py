"""L-chat-240 on the 1.5B: "Team offsite 9 to 11 December 2026" answered "December 9 to 11, 2026" was refused by the fact
check (5 of 6 date answers kept). A day range names both of its days, in either word order, with the year either end."""

from __future__ import annotations

from datetime import date, datetime

import pytest

from tessellate.ai import fact_check, recognise

NOW = datetime(2026, 11, 14, 22, 0)
FACTS = "Team offsite 9 to 11 December 2026"


@pytest.mark.parametrize(
    ("text", "days"),
    [
        ("9 to 11 December 2026", {date(2026, 12, 9), date(2026, 12, 11)}),
        ("December 9 to 11, 2026", {date(2026, 12, 9), date(2026, 12, 11)}),
        ("9-11 December 2026", {date(2026, 12, 9), date(2026, 12, 11)}),
        ("3rd until 5th March 2027", {date(2027, 3, 3), date(2027, 3, 5)}),
        ("from 12 to 14 Oct", {date(2026, 10, 12), date(2026, 10, 14)}),
    ],
)
def test_a_day_range_names_both_days(text, days):
    assert days <= recognise.days_named(text, NOW)
    assert len(recognise.date_mentions(text)) == 2


@pytest.mark.parametrize(
    "prose",
    ["The offsite is scheduled for December 9 to 11, 2026.", "The offsite is 9 to 11 December 2026.", "The offsite runs December 9 to 11."],
)
def test_a_correct_range_phrasing_is_kept(prose):
    assert fact_check.keeps(prose, FACTS, "When is the offsite?", {}, False, NOW)


@pytest.mark.parametrize("prose", ["The offsite is December 9 to 12, 2026.", "The offsite is December 10 to 11, 2026."])
def test_a_wrong_range_is_still_refused(prose):
    assert not fact_check.keeps(prose, FACTS, "When is the offsite?", {}, False, NOW)


def test_a_clock_span_is_no_date():
    assert recognise.date_mentions("open 9 to 11 pm, closed 5 to 7 on Sundays") == []
