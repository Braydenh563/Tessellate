"""Audit 1029 C36 (composer-ranker-1029.md item 5): "which is longer, the
budget or the Lisbon trip" listed each side and never said which was longer.
With one note a side the answer now leads with both lengths."""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from tessellate.api import routes_chat
from tessellate.core import config
from tessellate.entry import manager

NOW = datetime(2026, 10, 29, 12, 0)
NOTES = [
    "# Budget\n\nRent 1200, food 400, transport 120. Savings goal 300 a month.",
    "# Lisbon trip\n\nFlying out on 14 November, back on the 21st. Staying in Alfama, near the castle. "
    + "Day trip to Sintra on the 17th, and a fado night.",
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


def test_which_is_longer_says_both_lengths(ask):
    said = ask("which is longer, the budget or the Lisbon trip")
    assert said.startswith("**Lisbon trip** is the longer note: 26 words against 11 in **Budget**."), said


def test_which_is_shorter_names_the_shorter(ask):
    said = ask("which is shorter, the budget or the Lisbon trip")
    assert said.startswith("**Budget** is the shorter note: 11 words against 26 in **Lisbon trip**."), said


def test_a_plain_comparison_keeps_its_count_lead(ask):
    assert "longer note" not in ask("compare the budget and the Lisbon trip")
