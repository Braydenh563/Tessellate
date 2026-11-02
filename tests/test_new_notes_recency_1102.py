"""INBOX 1532: in Ask with no model, "new notes" answered the create prompt. A
plural "notes" with new, newest, latest or recent is a recency ask (the newest
notes listed); a singular "new note" with words is the create act, and a bare
"new note" offers both."""

from __future__ import annotations

import json

import pytest

from tessellate.ai import composer_suggest
from tessellate.entry import manager

RECENCY = [
    "new notes",
    "New notes",
    "my newest notes",
    "newest notes",
    "latest notes",
    "my latest notes",
    "recent notes please",
    "recent notes",
    "show new notes",
    "show me my newest notes",
    "list the latest notes",
    "any new notes",
    "see new notes",
]


@pytest.mark.parametrize("ask", RECENCY)
def test_a_plural_recency_ask_is_not_open_ended(ask):
    assert composer_suggest.open_ended(ask) == "", ask


@pytest.mark.parametrize("ask", ["new note", "New note"])
def test_a_bare_singular_new_note_still_offers_both(ask):
    assert composer_suggest.open_ended(ask) == "new", ask
    shown = composer_suggest.reply(ask, ["Dentist", "Harbor launch plan"])
    assert "What should the note say" in shown["text"]
    assert any("newest" in a.lower() or "latest" in a.lower() or "recent" in a.lower() for a in shown["asks"]), shown["asks"]


def _ask(client, question: str) -> str:
    with client.stream("POST", "/chat/stream", json={"question": question, "use_tools": False}) as response:
        assert response.status_code == 200
        events = [json.loads(line) for line in response.iter_lines() if line.strip()]
    return "".join(e.get("delta", "") for e in events if e["type"] == "answer")


@pytest.mark.parametrize("ask", RECENCY)
def test_through_the_route_the_newest_notes_are_listed(client, session, ask):
    manager.create_entry(session, "# Dentist\n\nCheck-up booked for the 21st.")
    manager.create_entry(session, "# Harbor launch plan\n\nShip the app.")
    session.commit()
    said = _ask(client, ask)
    assert "What should the note say" not in said and "note:" not in said, said
    assert "Dentist" in said or "Harbor" in said, said


@pytest.mark.parametrize(
    ("said", "read"),
    [
        ("new notes", "newest notes"),
        ("Show me my new notes please", "Show me my newest notes please"),
        ("any new notes?", "any newest notes"),
        ("new notes about uni", "newest notes about uni"),
        ("see new entries", "see newest entries"),
    ],
)
def test_new_notes_is_read_as_newest_notes(said, read):
    from tessellate.ai import question_noise

    assert question_noise.new_notes_as_newest(said) == read


@pytest.mark.parametrize("said", ["new note", "new note: buy milk", "I made new notes today", "what is new in my notes", "make a new note called Gym"])
def test_nothing_else_is_reworded(said):
    from tessellate.ai import question_noise

    assert question_noise.new_notes_as_newest(said) == said
