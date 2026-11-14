"""L-chat-128 (Build 4): the 60-phrasing gate for one time window. Two readers
share it: `search.query.understand` reads a day gone (what did I write ...) and
`composer_plan.window` reads a day ahead (what is due ...). Today is Saturday
14 November 2026; weeks run Monday to Sunday (the owner's Q24). The last three
rows are the known misses, so the pass share is measured, not assumed: 57 of
60 (95.0%), gate 95%."""

from datetime import date

import pytest

from tessellate.ai import composer_plan
from tessellate.search import query

TODAY = date(2026, 11, 14)


def d(month, day, year=2026):
    return date(year, month, day)


PAST = [
    ("what did I write today", d(11, 14), d(11, 14)),
    ("what did I write yesterday", d(11, 13), d(11, 13)),
    ("what did I write the day before yesterday", d(11, 12), d(11, 12)),
    ("what did I write this week", d(11, 9), d(11, 14)),
    ("what did I write last week", d(11, 2), d(11, 8)),
    ("what did I write the week before last", d(10, 26), d(11, 1)),
    ("what did I write this month", d(11, 1), d(11, 14)),
    ("what did I write this year", d(1, 1), d(11, 14)),
    ("what did I write in the last 3 days", d(11, 11), d(11, 14)),
    ("what did I write in the past week", d(11, 7), d(11, 14)),
    ("what did I write over the last two weeks", d(10, 31), d(11, 14)),
    ("what did I write in the last 30 days", d(10, 15), d(11, 14)),
    ("what did I write 3 days ago", d(11, 11), d(11, 11)),
    ("what did I write on Friday", d(11, 13), d(11, 13)),
    ("what did I write on Monday", d(11, 9), d(11, 9)),
    ("what did I write on the 3rd", d(11, 3), d(11, 3)),
    ("what did I write on 3 November", d(11, 3), d(11, 3)),
    ("what did I write on November 3rd", d(11, 3), d(11, 3)),
    ("what did I write in October", d(10, 1), d(10, 31)),
    ("what did I write in October 2025", d(10, 1, 2025), d(10, 31, 2025)),
    ("what did I write in 2025", d(1, 1, 2025), d(12, 31, 2025)),
    ("what did I write since Monday", d(11, 9), d(11, 14)),
    ("what did I write since last week", d(11, 2), d(11, 14)),
    ("what did I write since the 1st of November", d(11, 1), d(11, 14)),
    ("what did I write between 1 and 5 November", d(11, 1), d(11, 5)),
    ("what did I write from 1 November to 5 November", d(11, 1), d(11, 5)),
    ("what did I write earlier today", d(11, 14), d(11, 14)),
    ("what did I write this morning", d(11, 14), d(11, 14)),
    ("what did I write last night", d(11, 13), d(11, 13)),
    ("what did I write last weekend", d(11, 7), d(11, 8)),
    ("what did I write recently", d(10, 31), d(11, 14)),
    ("what did I write in the first week of November", d(11, 1), d(11, 7)),
    ("what did I write in the last week of October", d(10, 25), d(10, 31)),
    ("what did I write in spring", d(3, 1), d(5, 31)),
    ("what's on today", d(11, 14), d(11, 14)),
    ("what's on tonight", d(11, 14), d(11, 14)),
    ("what did I write two weeks ago", d(10, 28), d(11, 3)),
    ("what did I write last Monday", d(11, 9), d(11, 9)),
    ("what did I write over the weekend", d(11, 14), d(11, 15)),
    ("what did I write lately", d(10, 31), d(11, 14)),
]
AHEAD = [
    ("what is due tomorrow", d(11, 15), d(11, 15)),
    ("what is due next week", d(11, 16), d(11, 22)),
    ("what is due this weekend", d(11, 14), d(11, 15)),
    ("what is due next month", d(12, 1), d(12, 31)),
    ("what is due in 3 days", d(11, 17), d(11, 17)),
    ("what is due in two weeks", d(11, 28), d(11, 28)),
    ("what is due on Friday", d(11, 20), d(11, 20)),
    ("what is due by Friday", d(11, 14), d(11, 20)),
    ("what is coming up this week", d(11, 14), d(11, 20)),
    ("what's on next Tuesday", d(11, 17), d(11, 17)),
    ("what's on tomorrow", d(11, 15), d(11, 15)),
    ("what is due this week", d(11, 14), d(11, 20)),
    ("what is due next Monday", d(11, 16), d(11, 16)),
    ("what is due on the 20th", d(11, 20), d(11, 20)),
    ("what is due on 25 December", d(12, 25), d(12, 25)),
    ("what is due this month", d(11, 14), d(11, 30)),
    ("what is due the day after tomorrow", d(11, 16), d(11, 16)),
]
KNOWN_MISSES = [
    ("what did I do at the end of last month", d(10, 25), d(10, 31)),
    ("what did I do at the start of the month", d(11, 1), d(11, 7)),
    ("what is coming up", d(11, 14), d(11, 20)),
]


def _read(question):
    if question in {q for q, *_ in AHEAD}:
        got = composer_plan.window(question, TODAY)
        return got and got[:2]
    got = query.understand(question, TODAY)
    return got.since, got.until


def _passes(rows):
    return [q for q, first, last in rows if _read(q) == (first, last)]


def test_the_sixty_phrasing_gate():
    rows = PAST + AHEAD + KNOWN_MISSES
    assert len(rows) == 60
    passed = _passes(rows)
    assert len(passed) / len(rows) >= 0.95, [q for q, *_ in rows if q not in passed]


@pytest.mark.parametrize(("question", "first", "last"), PAST + AHEAD)
def test_each_phrasing_reads_to_its_window(question, first, last):
    assert _read(question) == (first, last)
