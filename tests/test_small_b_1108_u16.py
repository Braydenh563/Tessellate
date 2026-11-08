"""Batch B of small-rows-1108, row U16. Answers are composed with no model (CHAT_PLAN decision 75: a running model leads) on a fixed clock."""

from __future__ import annotations

from datetime import date, datetime

import pytest

from tessellate.ai import composer
from tessellate.ai.composer import plan
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


# --- U16: a what-if never states a consequence -----------------------------------------

def test_a_what_if_quotes_the_subject_and_says_the_notes_do_not_say_what_would_happen():
    out = _say("what if I move to Lisbon")
    assert out["text"] == ("Your notes say this about Lisbon: You want to live near the river in Lisbon. [**Lisbon**] "
                           "Your notes do not say what would happen.")
    assert [row["note_id"] for row in out["grounding"]] == [1]


def test_a_what_if_about_a_subject_no_note_holds_says_so():
    out = _say("What if I move to Paris?")
    assert out["text"] == "Your notes hold nothing about Paris, and they do not say what would happen."
    assert out["grounding"] == []


@pytest.mark.parametrize("ask", ["suppose I move to Lisbon", "what would happen if I move to Lisbon", "imagine I move to Lisbon"])
def test_other_ways_of_asking_a_what_if_are_the_same(ask):
    assert _say(ask)["text"].endswith("Your notes do not say what would happen.")


def test_a_what_if_never_states_a_consequence():
    text = _say("what if I move to Lisbon")["text"]
    assert "would be" not in text and "will " not in text and "you would" not in text.lower()


def test_a_what_if_is_no_longer_a_translation():
    assert plan("what if I move to Lisbon").kind != "utility"


def test_a_what_if_over_the_route_with_no_model(client, session):
    manager.create_entry(session, "# Lisbon\n\nI want to live near the river in Lisbon.")
    session.commit()
    text = _ask(client, "what if I move to Lisbon", notes_only=True, use_tools=False)["text"]
    assert text.endswith("Your notes do not say what would happen.") and "Lisbon" in text
