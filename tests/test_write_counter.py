"""Caches keyed on `max(updated_at)` also carry `database.writes(model)`: two
writes in one clock tick (a pinned clock always) share every stamp, and the
tag counts served the name the first write left (`rename_tag` in test_acts)."""

from datetime import datetime, timezone

from tessellate.core.database import Entry, writes
from tessellate.entry import manager
from tessellate.repo import tags as tags_repo
from tests._clock import pin_clock


def test_two_writes_in_one_tick_both_reach_the_tag_counts(monkeypatch, session):
    pin_clock(monkeypatch, datetime(2026, 8, 1, 9, 0, tzinfo=timezone.utc))
    entry = manager.create_entry(session, "# Gym log\n\nSquats.")
    entry.tags = '["gym"]'
    session.commit()
    assert "gym" in tags_repo.counts(session)
    before = writes(Entry)
    entry.tags = '["fitness"]'
    session.commit()
    assert writes(Entry) == before + 1
    counts = tags_repo.counts(session)
    assert "fitness" in counts and "gym" not in counts
