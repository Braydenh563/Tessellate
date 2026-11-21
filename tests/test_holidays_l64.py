"""L-chat-64, the `holidays` library's first use: the holidays that move or fall on a country's own day (Easter,
Good Friday, Boxing Day, Thanksgiving) are dates the window reader knows, beside its fixed Christmas and New Year.
Every test fixes the anchor day; none reads the real clock."""

from __future__ import annotations

from datetime import date

import pytest

from tessellate.ai import recognise, recognise_windows

TODAY = date(2026, 11, 14)


@pytest.mark.parametrize(
    ("phrase", "tense", "day"),
    [
        ("last easter", "past", date(2026, 4, 5)),
        ("easter", "future", date(2027, 3, 28)),
        ("easter sunday", "past", date(2026, 4, 5)),
        ("good friday", "past", date(2026, 4, 3)),
        ("easter monday", "past", date(2026, 4, 6)),
        ("last thanksgiving", "past", date(2025, 11, 27)),
        ("thanksgiving", "future", date(2026, 11, 26)),
        ("next thanksgiving", "future", date(2026, 11, 26)),
        ("this easter", "past", date(2026, 4, 5)),
        ("last boxing day", "past", date(2025, 12, 26)),
        ("boxing day", "future", date(2026, 12, 26)),
    ],
)
def test_a_moving_holiday_is_its_day(phrase, tense, day):
    found = recognise.span(phrase, TODAY, tense)
    assert found is not None and found[0] == found[1] == day, found


def test_a_pointed_holiday_names_its_year():
    assert recognise_windows.with_holiday_year("last Easter", date(2026, 4, 5)) == "last Easter (2026)"
    assert recognise_windows.with_holiday_year("last Thanksgiving", date(2025, 11, 27)) == "last Thanksgiving (2025)"
    assert recognise_windows.with_holiday_year("last Tuesday", date(2026, 11, 10)) == "last Tuesday"


def test_christmas_stays_the_fixed_table():
    assert recognise.span("last christmas", TODAY, "past")[0] == date(2025, 12, 25)
