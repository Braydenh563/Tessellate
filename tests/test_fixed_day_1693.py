"""The suite pins `clock.today()` (INBOX 1693 a): the chat reply seed carries
the day, so a composed wording asserted without a pinned day passed on some
days and failed on others."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from tessellate.core import clock

from tests.conftest import SUITE_DAY

TESTS = Path(__file__).resolve().parent

#: Composer and chat tests that read the real day on purpose: they build data
#: relative to "now", and the server reads the same real clock (reminders, note
#: windows), so the wording they assert does not depend on the day.
REAL_DAY_OK = {"test_composer_1324.py", "test_composer_route_688.py"}


def test_no_test_reads_the_day_through_clock_unpinned():
    assert clock.today() == SUITE_DAY != date.today()


def test_a_test_that_sets_its_own_day_wins(monkeypatch):
    monkeypatch.setattr(clock, "today", lambda: date(2026, 11, 4))
    assert clock.today() == date(2026, 11, 4)


def test_composer_and_chat_tests_do_not_read_the_real_day():
    pattern = re.compile(r"\b(?:date\.today|datetime\.now|datetime\.today|datetime\.utcnow)\(")
    offenders = [
        path.name
        for path in sorted([*TESTS.glob("test_composer*.py"), *TESTS.glob("test_chat*.py")])
        if path.name not in REAL_DAY_OK and pattern.search(path.read_text(encoding="utf-8"))
    ]
    assert not offenders, f"pin the day with clock.today (conftest _fixed_day) or monkeypatch it: {offenders}"
