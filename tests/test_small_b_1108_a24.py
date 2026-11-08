"""Batch B of small-rows-1108, row A24. Answers are composed with no model (CHAT_PLAN decision 75: a running model leads) on a fixed clock."""

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


# --- A24: show me something old --------------------------------------------------------

def test_something_old_picks_one_note_and_says_how_old_it_is():
    out = _say("show me something old", salt="b", turn=1)
    assert out["text"] == "Here is one from a while back: **Old trip**, written four years ago. It begins: We walked the coast path in 2022."
    assert [row["note_id"] for row in out["grounding"]] == [3]


def test_the_pick_follows_the_salt_and_holds_for_the_same_one():
    picks = {_say("show me something old", salt=s, turn=1)["text"] for s in "abcdefgh"}
    assert len(picks) > 1
    assert _say("show me something old", salt="a", turn=1)["text"] == _say("show me something old", salt="a", turn=1)["text"]


@pytest.mark.parametrize("ask", ["show me an old note", "give me something forgotten", "show me something from a while back", "dig up something old"])
def test_other_ways_of_asking_for_something_old(ask):
    assert _say(ask, salt="b", turn=1)["text"].startswith("Here is one from a while back:")


@pytest.mark.parametrize("ask", ["show me something", "show me my old car notes", "what is old"])
def test_a_question_that_is_not_the_ask_is_not_read_as_one(ask):
    assert not composer_small.asks_old(ask)


def test_something_old_over_the_route_draws_from_the_faded_notes(client, session):
    for i in range(3):
        manager.create_entry(session, f"# Note {i}\n\nA sentence about thing {i}.")
    session.commit()
    text = _ask(client, "show me something old", notes_only=True, use_tools=False)["text"]
    assert text.startswith("Here is one from a while back: ")
