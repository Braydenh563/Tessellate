"""The suite pins `clock.today()` (INBOX 1693 a): the chat reply seed carries
the day, so a composed wording asserted without a pinned day passed on some
days and failed on others."""

from __future__ import annotations

from datetime import date

from tessellate.core import clock

from tests.conftest import SUITE_DAY



def test_no_test_reads_the_day_through_clock_unpinned():
    # SUITE_DAY is a fixed past day, so equal to it is pinned (no real read).
    assert clock.today() == SUITE_DAY == date(2026, 8, 1)


def test_a_test_that_sets_its_own_day_wins(monkeypatch):
    monkeypatch.setattr(clock, "today", lambda: date(2026, 11, 4))
    assert clock.today() == date(2026, 11, 4)


# The lints that once listed files reading the real day are replaced by
# tests/test_fixed_clock_lint.py, which allows none.
