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


@pytest.mark.parametrize("question", [
    "which note is longer, budget or Lisbon trip",
    "which one is longer: the budget or the Lisbon trip?",
    "which of the two is longer, budget or the Lisbon trip",
])
def test_which_note_is_longer_is_the_same_ask(ask, question):
    """A noun after "which" ("which note", "which one") is still the
    comparison (composer-ranker-1029.md item 5)."""
    assert ask(question).startswith("**Lisbon trip** is the longer note: 26 words against 11 in **Budget**."), question


def test_a_side_named_in_full_is_that_note_alone(client, session, monkeypatch):
    """"running log" is the Running log, not also the Running plan that
    shares a word, so the lengths are said (2026-10-30 sweep)."""
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)
    for content in ("# Running log\n\nRan 5 km on Sunday along the river. Knee felt fine.",
                    "# Running plan\n\nBuild to 10 km by December, three runs a week.",
                    "# Baking\n\nSourdough loaf at 230C for 40 minutes. Try rye next."):
        manager.create_entry(session, content)
    session.commit()
    body = {"question": "which note is longer, running log or baking", "answer_from": "notes", "notes_only": True, "use_tools": False}
    said = ""
    with client.stream("POST", "/chat/stream", json=body) as response:
        for line in response.iter_lines():
            if line.strip() and (event := json.loads(line))["type"] == "answer":
                said += event["delta"]
    assert said.startswith("**Running log** is the longer note"), said
    assert "Running plan" not in said, said
