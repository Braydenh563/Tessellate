"""L563: every place an answer words a day follows the person's date order (en-US
"September 11", elsewhere "11 September"), not just the composer's tagged parts."""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from tessellate.ai import activity, composer_stale, note_order, realise, recognise, records, timetravel, tool_say, verdicts

DAY = date(2025, 9, 11)
TODAY = date(2026, 6, 1)
CASES = {
    "activity._day_words": lambda: activity._day_words(DAY, TODAY),
    "activity._say_day": lambda: activity._say_day(DAY, TODAY),
    "records._day_words": lambda: records._day_words(DAY, TODAY),
    "tool_say._when": lambda: tool_say._when("2025-09-11T09:00:00"),
    "verdicts.day_words": lambda: verdicts.day_words(DAY),
    "timetravel.day_words": lambda: timetravel.day_words(DAY),
    "note_order.date_in_words": lambda: note_order.date_in_words(datetime(2025, 9, 11, tzinfo=timezone.utc), timezone.utc),
    "composer_stale._day_said": lambda: composer_stale._day_said(DAY, TODAY),
}


@pytest.fixture(autouse=True)
def _reset():
    before = dict(recognise._HEMISPHERE)
    yield
    recognise._HEMISPHERE.update(before)
    recognise.configure_date_order("auto")


@pytest.mark.parametrize("name", sorted(CASES))
def test_a_day_follows_the_locale(name):
    recognise.note_locale("en-GB")
    gb = CASES[name]()
    recognise.note_locale("en-US")
    us = CASES[name]()
    assert "11 Sep" in gb, gb
    assert "Sep" in us and "11 Sep" not in us, us
    assert us.index("11") > us.index("Sep"), us


def test_before_and_after_counts(monkeypatch, capsys):
    recognise.note_locale("en-US")
    after = sum("11 Sep" not in CASES[name]() for name in CASES)
    monkeypatch.setattr(realise, "localised_days", lambda text: text)
    before = sum("11 Sep" not in CASES[name]() for name in CASES)
    print(f"MONTHFIRST before {before}/{len(CASES)} after {after}/{len(CASES)}")
    assert after == len(CASES) and before == 0


def test_month_first_reads_abbreviated_months():
    assert realise.month_first_days("Thu 11 Sep, 3 October 2025") == "Thu Sep 11, October 3, 2025"
