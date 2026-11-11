"""The owner's answers of 2026-11-11 on notes and lists (OPEN B26): Q5, the whole unquoted phrase after "called"
is the note's title; Q6, every list add asks first, and a list that has no note yet is offered as one."""

from __future__ import annotations

from datetime import datetime

import pytest

from tessellate.ai import commands
from tessellate.entry import manager
from tests.test_composer_route_688 import _ask

NOW = datetime(2026, 11, 11, 9, 0)


@pytest.mark.parametrize(
    ("said", "content"),
    [
        ("create a note called Shopping with milk, eggs and bread", "Shopping with milk, eggs and bread"),
        ("make a note called Lunch with Sam on Friday", "Lunch with Sam on Friday"),
        ('create a note called "Shopping" with milk, eggs and bread', "Shopping\nMilk, eggs and bread"),
        ("new note called Gym that says squats on Monday", "Gym\nSquats on Monday"),
        ("make a note titled Trip ideas: book flights", "Trip ideas\nBook flights"),
    ],
)
def test_the_whole_phrase_after_called_is_the_title_unless_quoted_or_introduced(said, content):
    assert commands.parse(said, NOW).args["content"] == content


def _act(events) -> dict:
    return events["act"][0]


def test_a_list_with_no_note_is_offered_as_a_new_note_and_waits_for_confirm(client, session):
    out = _ask(client, "add milk to my shopping list")
    card = _act(out)
    assert out["text"].startswith("You have no shopping list note yet."), out["text"]
    assert [s["name"] for s in card["steps"]] == ["create_note"]
    assert card["steps"][0]["arguments"]["content"] == "# Shopping list\n\n- [ ] Milk"
    assert "Nothing changes until you confirm" in card["notice"]


def test_a_list_add_to_a_note_that_exists_asks_first_too(client, session):
    manager.create_entry(session, "# Packing list\n\nPassport, charger")
    manager.create_entry(session, "# Shopping\n\nEggs")
    session.commit()
    for said, note in (("add socks to the packing list", "Packing list"), ("add milk to my shopping list", "Shopping")):
        card = _act(_ask(client, said))
        assert [s["name"] for s in card["steps"]] == ["edit_note"] and card["items"] == [note], said
        assert "Nothing changes until you confirm" in card["notice"]


def test_a_place_that_is_no_list_still_asks_which_note(client, session):
    out = _ask(client, "add milk to the harbour plan")
    assert "act" not in out and "note" in out["text"].lower(), out["text"]
