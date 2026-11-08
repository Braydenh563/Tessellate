"""Batch B of small-rows-1108, row A22. Answers are composed with no model (CHAT_PLAN decision 75: a running model leads) on a fixed clock."""

from __future__ import annotations

from datetime import date, datetime

import pytest

from tessellate.ai import composer, composer_small
from tessellate.entry import manager
from tests.test_composer_route_688 import _ask

TODAY = date(2026, 11, 8)
NOW = datetime(2026, 11, 8, 12, 0)

NOTES = [
    {"id": 1, "content": "# Lisbon\n\nI want to live near the river in Lisbon. Rent there is about 1200 a month.",
     "created_at": "2026-09-01", "written": "Tuesday 1 September 2026, 09:00"},
    {"id": 2, "content": "# Gym plan\n\nThe weekly split.\n\n## Leg day\n\nSquats on Monday and deadlifts on Friday.",
     "created_at": "2026-11-01", "category": "Fitness",
     "written": "Sunday 1 November 2026, 09:00, edited Thursday 5 November 2026, 10:00"},
    {"id": 3, "content": "# Old trip\n\nWe walked the coast path in 2022.", "created_at": "2022-06-01", "category": "Travel",
     "written": "Wednesday 1 June 2022, 09:00"},
]


def _say(question: str, notes=NOTES, **kw) -> dict:
    return composer.compose(question, notes, today=TODAY, now=NOW, **kw)


# --- A22: where did I write X ----------------------------------------------------------

def test_where_did_i_write_names_the_note_its_section_its_category_and_its_age():
    out = _say("where did I write about squats")
    assert out["text"] == ("It is in **Gym plan**, under Leg day, in Fitness, last edited three days ago. "
                           "It reads: Squats on Monday and deadlifts on Friday.")
    assert out["shape"] == "where" and [row["note_id"] for row in out["grounding"]] == [2]


def test_where_did_i_write_a_note_never_edited_says_when_it_was_written():
    assert _say("where did I write down the coast path?")["text"] == (
        "It is in **Old trip**, in Travel, written four years ago. It reads: We walked the coast path in 2022.")


def test_where_did_i_write_something_no_note_holds_is_left_to_the_ordinary_answer():
    assert composer_small.where_written("where did I write about kayaks", NOTES, today=TODAY) is None


@pytest.mark.parametrize(
    ("days", "said"),
    [(0, "today"), (1, "yesterday"), (3, "three days ago"), (20, "three weeks ago"), (100, "three months ago"), (1500, "four years ago")],
)
def test_ago_is_said_the_way_a_person_says_it(days, said):
    assert composer_small.ago(days) == said


def test_where_did_i_write_over_the_route_with_no_model(client, session):
    manager.create_entry(session, "# Gym plan\n\nSquats on Monday.\n\n## Leg day\n\nDeadlifts on Friday.", category_name="Fitness")
    session.commit()
    text = _ask(client, "where did I write about deadlifts", notes_only=True, use_tools=False)["text"]
    assert text.startswith("It is in **Gym plan**, under Leg day, in Fitness, ")
