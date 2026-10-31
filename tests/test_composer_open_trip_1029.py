"""Audit 1029 C33 residue: "what do I need to do before the Lisbon trip" and
"what is left for the Lisbon trip" said no checklist had anything left,
though "Lisbon packing list" held two open items: the trip note named every
word and held no tasks. When the named notes hold nothing to tick, the notes
titled with every name the subject carries are asked too; the name keeps the
Tokyo trip off the Lisbon list."""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from tessellate.api import routes_chat
from tessellate.core import config
from tessellate.entry import manager

NOW = datetime(2026, 10, 29, 12, 0)
NOTES = [
    "# Lisbon trip\n\nFlying out on 14 November, back on the 21st. Staying in Alfama, near the castle.",
    "# Atlas kickoff attendees\n\n- [ ] Sara\n- [ ] Tom\n- [ ] Priya",
    "# Lisbon packing list\n\n- [ ] passport\n- [x] charger\n- [ ] walking shoes",
    "# Tokyo trip\n\nThe flight is in March.",
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


@pytest.mark.parametrize("question", ["what do I need to do before the Lisbon trip", "what is left for the Lisbon trip"])
def test_the_trip_is_answered_with_its_packing_list(ask, question):
    said = ask(question)
    assert "Lisbon packing list" in said and "Passport" in said and "Walking shoes" in said, said
    assert "Sara" not in said and "Charger" not in said, said


def test_another_trip_does_not_take_the_lisbon_list(ask):
    said = ask("what is left for the Tokyo trip")
    assert "Passport" not in said and "Sara" not in said, said
