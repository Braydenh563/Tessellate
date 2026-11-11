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


#: Tests that post to a chat endpoint and read the real calendar to build their data (a note "three days ago",
#: a reminder "now") without asserting composed wording; the list may shrink, never grow (INBOX 1693 a, lint half).
CHAT_POSTERS_ON_REAL_DAY = {
    "test_agent_tools_api.py",
    "test_composer_route_688.py",
    "test_dialogue_b8.py",
    "test_output_forms.py",
    "test_records_a3.py",
    "test_related_elsewhere.py",
    "test_starter_acts.py",
}


def test_a_test_that_posts_to_chat_does_not_read_the_real_day():
    """The reply seed carries `clock.today()`, so any test that reaches a chat endpoint is day-dependent
    when it reads the real date for its data; a new one pins the day (conftest `_fixed_day`) or builds its
    dates from `SUITE_DAY`. Beyond the composer and chat files the first lint covers."""
    reads = re.compile(r"\b(?:date\.today|datetime\.now|datetime\.today|datetime\.utcnow)\(")
    posts = re.compile(r"""post\(\s*f?["']/(?:chat|ask|composer|act)\b|["']/chat["']|/chat/""")
    offenders = sorted(
        path.name
        for path in TESTS.glob("test_*.py")
        if path.name != Path(__file__).name
        and path.name not in CHAT_POSTERS_ON_REAL_DAY
        and not path.name.startswith(("test_composer", "test_chat"))
        and reads.search(text := path.read_text(encoding="utf-8"))
        and posts.search(text)
    )
    assert not offenders, f"pin the day or build dates from SUITE_DAY: {offenders}"
    stale = sorted(
        name
        for name in CHAT_POSTERS_ON_REAL_DAY
        if not reads.search(text := (TESTS / name).read_text(encoding="utf-8")) or not posts.search(text)
    )
    assert not stale, f"no longer reads the real day or posts to chat, drop it from the list: {stale}"
