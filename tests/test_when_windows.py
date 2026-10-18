"""Time words as spans and windows (CHAT_PLAN Phase 6, decisions 30 and 31;
the engine probe's `when.resolve` table, 2026-10-10). Now is Tuesday
2026-10-06 14:30, the probe's clock."""

from __future__ import annotations

from datetime import date, datetime

import pytest

from tessellate.ai import when

NOW = datetime(2026, 10, 6, 14, 30)
TODAY = NOW.date()


@pytest.mark.parametrize(
    ("phrase", "expected"),
    [
        ("last friday", datetime(2026, 10, 2, 9, 0)),
        ("the 21st", datetime(2026, 10, 21, 9, 0)),
        ("on the 14th", datetime(2026, 10, 14, 9, 0)),
        ("21st of next month", datetime(2026, 11, 21, 9, 0)),
        ("end of the month", datetime(2026, 10, 31, 9, 0)),
        ("next month", datetime(2026, 11, 1, 9, 0)),
        ("mid november", datetime(2026, 11, 15, 9, 0)),
        ("end of day", datetime(2026, 10, 6, 17, 0)),
        ("this weekend", datetime(2026, 10, 10, 9, 0)),
        ("next weekend", datetime(2026, 10, 17, 9, 0)),
        ("in a fortnight", datetime(2026, 10, 20, 9, 0)),
        ("christmas", datetime(2026, 12, 25, 9, 0)),
        ("new year", datetime(2027, 1, 1, 9, 0)),
        ("later today", datetime(2026, 10, 6, 17, 30)),
        # The forms that were right, held.
        ("noon", datetime(2026, 10, 7, 12, 0)),
        ("at 5", datetime(2026, 10, 6, 17, 0)),
        ("5pm", datetime(2026, 10, 6, 17, 0)),
        ("17:30", datetime(2026, 10, 6, 17, 30)),
        ("tomorrow at 9", datetime(2026, 10, 7, 9, 0)),
        ("next tuesday morning", datetime(2026, 10, 13, 9, 0)),
        ("first thing monday", datetime(2026, 10, 12, 9, 0)),
        ("in 90 minutes", datetime(2026, 10, 6, 16, 0)),
        ("nov 2", datetime(2026, 11, 2, 9, 0)),
        ("2026-11-02", datetime(2026, 11, 2, 9, 0)),
        ("the day after tomorrow", datetime(2026, 10, 8, 9, 0)),
        ("friday", datetime(2026, 10, 9, 9, 0)),
        ("next week", datetime(2026, 10, 12, 9, 0)),
    ],
)
def test_resolve(phrase, expected):
    assert when.resolve(phrase, NOW) == expected


def test_later_today_after_eight_is_three_hours_on():
    late = datetime(2026, 10, 6, 21, 0)
    assert when.resolve("later today", late) == datetime(2026, 10, 7, 0, 0)


@pytest.mark.parametrize(
    ("phrase", "first", "last", "grain"),
    [
        ("yesterday", date(2026, 10, 5), date(2026, 10, 5), "day"),
        ("a week ago", date(2026, 9, 29), date(2026, 9, 29), "day"),
        ("3 weeks ago", date(2026, 9, 15), date(2026, 9, 15), "day"),
        ("the week before last", date(2026, 9, 21), date(2026, 9, 27), "week"),
        ("last week", date(2026, 9, 28), date(2026, 10, 4), "week"),
        ("this week", date(2026, 10, 5), date(2026, 10, 11), "week"),
        ("since march", date(2026, 3, 1), TODAY, "month"),
        ("in march", date(2026, 3, 1), date(2026, 3, 31), "month"),
        ("march", date(2026, 3, 1), date(2026, 3, 31), "month"),
        ("last month", date(2026, 9, 1), date(2026, 9, 30), "month"),
        ("this year", date(2026, 1, 1), date(2026, 12, 31), "year"),
        ("the last 3 days", date(2026, 10, 3), TODAY, "day"),
        ("on Monday", date(2026, 10, 5), date(2026, 10, 5), "day"),
        ("last friday", date(2026, 10, 2), date(2026, 10, 2), "day"),
        ("on 3 March", date(2026, 3, 3), date(2026, 3, 3), "day"),
        ("since last week", date(2026, 9, 28), TODAY, "week"),
        ("last weekend", date(2026, 10, 3), date(2026, 10, 4), "week"),
    ],
)
def test_a_past_span(phrase, first, last, grain):
    assert when.span(phrase, TODAY, "past") == (first, last, grain)


@pytest.mark.parametrize(
    ("phrase", "tense", "day"),
    [
        ("on Friday", "past", date(2026, 10, 2)),
        ("on Friday", "future", date(2026, 10, 9)),
        ("the 21st", "past", date(2026, 9, 21)),
        ("the 21st", "future", date(2026, 10, 21)),
        ("14 November", "future", date(2026, 11, 14)),
        ("14 November", "past", date(2025, 11, 14)),
    ],
)
def test_the_tense_picks_the_day_before_or_after(phrase, tense, day):
    assert when.span(phrase, TODAY, tense)[0] == day


def test_a_window_ends_now_at_the_latest():
    start, end = when.window("this week", NOW)
    assert start == datetime(2026, 10, 5) and end == NOW
    assert when.window("next week", NOW) is None
    assert when.window("what is this", NOW) is None


def test_find_reads_the_phrases_in_a_sentence():
    text = "Ship it on the 14th of next month, and call Sam last Friday or 3 days ago."
    assert [p for _s, _e, p in when.find(text)] == ["on the 14th of next month", "last Friday", "3 days ago"]
    assert when.find("I may march on") == []


def test_a_numeric_day_in_a_question_follows_the_locale():
    """CHAT_PLAN open item: "3/4" is day first unless the locale writes the
    month first (`recognise._MONTH_FIRST`); no locale means day first."""
    from datetime import date

    from tessellate.search import query

    today = date(2026, 10, 18)
    first = query.understand("what did I write on 3/4", today)
    assert (first.since, first.until) == (date(2026, 4, 3), date(2026, 4, 3))
    uk = query.understand("what did I write on 3/4", today, "en-GB")
    assert uk.since == date(2026, 4, 3)
    us = query.understand("what did I write on 3/4", today, "en-US")
    assert (us.since, us.until) == (date(2026, 3, 4), date(2026, 3, 4))
