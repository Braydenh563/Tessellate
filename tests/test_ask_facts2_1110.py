"""Composer audit 2 (fable-composer2-1110.md) G1, the three left over, no model, clock fixed at
Tuesday 10 November 2026, 09:00: "last" reads the past visit, a goal line is not a distance run,
and "has X changed" says what it was and what it is now."""

from __future__ import annotations

import pytest

from tessellate.entry import manager
from tests.test_ask_facts_1110 import NOTES, _fixed_now, ask  # noqa: F401 - the clock fixture

DENTIST = "# Dentist\n\nCheck-up booked for 21 November.\n\nLast visit 20 May: a filling on the left."


@pytest.fixture
def notebook(session):
    from datetime import datetime

    for content, cat, when in [*NOTES, (DENTIST, "Health", "2026-05-20T10:00:00")]:
        entry = manager.create_entry(session, content, category_name=cat)
        entry.created_at = entry.updated_at = datetime.fromisoformat(when)
    session.commit()
    return session


@pytest.mark.parametrize("question", ["when did I last see the dentist", "when was my last dentist visit"])
def test_last_is_the_past_visit_not_the_next_booking(client, notebook, question):
    said = ask(client, question)
    assert "20 May" in said.split("21 November")[0], said


def test_when_is_my_next_dentist_visit_still_reads_the_booking(client, notebook):
    said = ask(client, "when is my next dentist appointment")
    assert "21 November" in said.split("20 May")[0], said


def test_how_far_did_i_run_leaves_out_the_goal(client, notebook):
    said = ask(client, "how far did I run")
    assert "10 km" in said and "20 km" not in said and "15 km" not in said, said


def test_has_the_launch_date_changed_says_from_and_to(client, notebook):
    said = ask(client, "has the launch date changed")
    assert said.startswith("Yes") and "14 December" in said and "11 January" in said, said
    assert said.index("14 December") < said.index("11 January") or "to 11 January" in said, said


def test_has_something_changed_with_one_note_says_so_plainly(client, notebook):
    said = ask(client, "has the dentist date changed")
    assert not said.startswith("Yes"), said
