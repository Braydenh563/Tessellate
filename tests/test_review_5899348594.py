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


# --- 3. a rejected answer says why, not that the model stopped ------------------------------------


def test_an_unbacked_answer_gets_its_own_note_and_a_stopped_one_keeps_its_own():
    from tessellate.api import chat_degrade
    from tessellate.api.chat_said import MODEL_STOPPED_NOTE, MODEL_UNBACKED_NOTE

    prepared = {"preview": {"text": "Composed."}}
    rejected = list(chat_degrade.fallback_events(prepared, None, {}, True, "Harbor ships on the 28th."))
    stopped = list(chat_degrade.fallback_events(prepared, None, {}, True))
    assert rejected[0]["text"].endswith(MODEL_UNBACKED_NOTE) and MODEL_STOPPED_NOTE not in rejected[0]["text"]
    assert stopped[0]["text"].endswith(MODEL_STOPPED_NOTE)
    assert MODEL_UNBACKED_NOTE != MODEL_STOPPED_NOTE and "\u2014" not in MODEL_UNBACKED_NOTE


# --- 4. a question that matches no tool group is never told its tools are off ---------------------


def test_a_question_no_group_matches_gets_no_switched_off_line(ai_client):
    from tessellate.ai.tools import tool_off
    from tessellate.ai.tools.tool_off import TOOL_GROUPS

    every = sorted({name for group, *_ in TOOL_GROUPS for name in group})
    ai_client.put("/preferences", json={"disabled_tools": every})
    assert tool_off._top_groups("good morning to you") == []
    assert tool_off.switched_off_line("good morning to you") is None
