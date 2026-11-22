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
    assert writes(Entry) == before + 2  # the flush and the commit (review of PR 222)
    counts = tags_repo.counts(session)
    assert "fitness" in counts and "gym" not in counts


def test_a_reader_between_the_flush_and_the_commit_is_retired_by_the_commit(session):
    """Review of PR 222: another session that fingerprints after the flush but
    before the commit sees the old rows under the new count; the commit moves
    the count again, so that cached pass is never served."""
    entry = manager.create_entry(session, "First draft.")
    session.commit()
    entry.content = "Second draft."
    session.flush()
    between = writes(Entry)
    session.commit()
    assert writes(Entry) > between


def test_a_rolled_back_flush_is_not_counted_at_the_next_commit(session):
    entry = manager.create_entry(session, "Kept.")
    session.commit()
    entry.content = "Dropped."
    session.flush()
    session.rollback()
    before = writes(Entry)
    session.commit()
    assert writes(Entry) == before
