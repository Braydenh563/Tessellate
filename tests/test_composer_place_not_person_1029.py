"""Audit 1029 C15 residue (composer-subject-1029.md item 1): "tell me about
Lisbon" took the who shape ("Lisbon comes up in ...") because any single name
the notebook writes was read as a person. A name the notes travel to, stay in
or fly from, and never speak with, is a place: answered as a topic. A person
the notes meet or call keeps the who shape."""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from tessellate.api import routes_chat
from tessellate.core import config
from tessellate.entry import manager

NOW = datetime(2026, 10, 29, 12, 0)
NOTES = [
    "Flying to Lisbon on 14 November with Sara, staying in Alfama.",
    "The train from Lisbon to Porto takes under three hours.",
    "Met Sara for coffee; she said the Lisbon flat is booked.",
    "Called Sara about the tickets.",
]


@pytest.fixture
def ask(client, session, monkeypatch):
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)
    for content in NOTES:
        manager.create_entry(session, content)
    session.commit()

    def go(question: str) -> str:
        body = {"question": question, "answer_from": "notes", "notes_only": True, "use_tools": False}
        text = ""
        with client.stream("POST", "/chat/stream", json=body) as response:
            for line in response.iter_lines():
                if line.strip():
                    event = json.loads(line)
                    if event["type"] == "answer":
                        text += event["delta"]
        return text

    return go


def test_a_place_is_not_answered_as_a_person(ask):
    said = ask("tell me about Lisbon")
    assert "Lisbon comes up" not in said, said
    assert "Lisbon" in said, said


def test_a_person_keeps_the_who_shape(ask):
    assert "Sara comes up" in ask("tell me about Sara")
