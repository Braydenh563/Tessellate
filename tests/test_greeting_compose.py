"""The dashboard greeting without a model (INBOX 876, the owner 2026-10-11:
"can you add more deterministic welcome messages?? mroe variety and ones for
each time of the day?? maybe the composer can spin something up based on
usage patterns, note content, and more??")."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from tessellate.ai import greeting_compose as gc
from tessellate.ai.greeting_compose import NotebookFacts
import pytest
from tests._clock import SUITE_NOW, pin_clock


@pytest.fixture(autouse=True)
def _suite_clock(monkeypatch):
    """Data here is built from SUITE_NOW, and the app reads the same pinned clock."""
    pin_clock(monkeypatch, SUITE_NOW)

ZONE = timezone(timedelta(hours=8))


def _at(day: int, hour: int) -> datetime:
    return datetime(2026, 10, day, hour, 15, tzinfo=ZONE)


def test_seven_times_of_day_each_with_variety():
    assert [gc.slot_for(h) for h in (1, 6, 10, 13, 16, 19, 22)] == [
        "small hours", "early morning", "morning", "midday", "afternoon", "evening", "late evening"]
    assert all(len(set(p)) >= 7 for p in gc.PHRASES.values())


def test_same_hour_same_line_next_hour_new_choices():
    facts = NotebookFacts(total=30)
    assert gc.compose(_at(14, 19), facts) == gc.compose(_at(14, 19), facts)
    seen = {gc.compose(_at(d, 19), facts)[0] for d in range(1, 29)}
    assert len(seen) >= 5, seen


def test_lines_are_name_ready_and_plain():
    facts = NotebookFacts(total=40, today=4, this_week=12, days_since_last=0, streak=5, recent_category="University")
    for day in range(1, 29):
        for hour in range(24):
            phrase, mark = gc.compose(_at(day, hour), facts)
            assert phrase and phrase[0].isupper() and phrase[-1] not in ".!?" and mark in {".", "?"}
            assert "!" not in phrase and chr(0x2014) not in phrase


def test_the_notebook_speaks_when_it_has_something_to_say():
    facts = NotebookFacts(total=40, today=0, days_since_last=6, recent_category="University")
    said = {gc.compose(_at(d, h), facts)[0] for d in range(1, 29) for h in (9, 15)}
    assert "It has been 6 days since your last note" in said
    assert "University on your mind lately" in said
    assert "A blank page awaits" in {gc.compose(_at(d, 9), NotebookFacts())[0] for d in range(1, 29)}


def test_facts_come_from_the_notes(session):
    from tessellate.core.database import Category, Entry

    uni = Category(name="university")
    session.add(uni)
    session.flush()
    now = SUITE_NOW.astimezone(ZONE).replace(hour=20)
    base = now.astimezone(timezone.utc).replace(tzinfo=None)
    for back in (0, 0, 1, 2):
        session.add(Entry(content=f"note {back}", category_id=uni.id, created_at=base - timedelta(days=back)))
    session.commit()
    facts = gc.gather(session, now)
    assert facts.total == 4 and facts.today == 2 and facts.streak == 3
    assert facts.recent_category == "University" and facts.days_since_last == 0
