"""The owner's review 5899348594 on PR 230. Clock: Tuesday 10 November 2026, 09:00."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from tessellate.ai import anchor_acts
from tessellate.core.database import Entry, EntryDate
from tessellate.entry import manager

from tests.test_chat_acts_2_1112_c import _fixed_now  # noqa: F401  (autouse clock)

NOW = datetime(2026, 11, 10, 9, 0)


def _settle(session, sentence, now=NOW):
    return anchor_acts.settle(session, anchor_acts.read(sentence), now)


# --- 1. the name is matched before the row cap, not after ---------------------------------------


def test_a_named_time_past_five_hundred_other_timed_notes_still_anchors(session):
    for n in range(520):
        entry = Entry(content=f"Standup {n}", category_id=None)
        session.add(entry)
        session.flush()
        session.add(EntryDate(entry_id=entry.id, phrase="soon", at=NOW + timedelta(hours=2, minutes=n), precision="minute"))
    entry = Entry(content="Dentist check-up", category_id=None)
    session.add(entry)
    session.flush()
    session.add(EntryDate(entry_id=entry.id, phrase="later", at=datetime(2026, 11, 30, 15, 0), precision="minute"))
    session.commit()
    assert _settle(session, "remind me an hour before the dentist")["due_at"] == datetime(2026, 11, 30, 14, 0)


def test_a_percent_or_underscore_in_the_name_is_literal(session):
    entry = Entry(content="Gym class", category_id=None)
    session.add(entry)
    session.flush()
    session.add(EntryDate(entry_id=entry.id, phrase="later", at=datetime(2026, 11, 11, 15, 0), precision="minute"))
    session.commit()
    assert "ask" in _settle(session, "remind me an hour before the g_m")


# --- 2. one convention for times: the writer's wall clock, with no zone ----------------------------


def test_a_zoned_clock_in_brisbane_reads_the_same_wall_clock(session):
    manager.create_entry(session, "# Gym\n\nSession tomorrow at 3pm.", category_name="Life")
    session.commit()
    brisbane = NOW.replace(tzinfo=timezone(timedelta(hours=10)))
    assert _settle(session, "remind me an hour before the gym", brisbane)["due_at"] == datetime(2026, 11, 11, 14, 0)
    assert _settle(session, "remind me an hour before the gym")["due_at"] == datetime(2026, 11, 11, 14, 0)
