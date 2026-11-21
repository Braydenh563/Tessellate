"""2026-10-30 composer sweep (composer-subject-1029.md item 2): "what is the
plan for December" was answered "two notes about December", losing the plan,
and two notes written close together were "All two came within a day"."""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from tessellate.api import routes_chat
from tessellate.core import config
from tessellate.entry import manager

NOW = datetime(2026, 10, 29, 12, 0)
NOTES = [
    "# Running plan\n\nBuild to 10 km by December, three runs a week.",
    "# December plan\n\nVisit Mum on the 20th. Finish the quilt. Book the car service.",
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


@pytest.mark.parametrize(("question", "topic"), [
    ("what is the plan for December", "about the plan for December"),
    ("what's my plan for december", "about your plan for December"),
])
def test_a_thing_for_something_keeps_both_halves(ask, question, topic):
    said = ask(question)
    assert topic in said.split("\n")[0], said


def test_two_notes_are_both_never_all_two(ask):
    said = ask("what is the plan for December")
    assert "All two" not in said and "Both came within" in said, said


def test_a_purchase_for_someone_is_still_about_them(ask):
    """No determiner before the thing: "what did I buy for Mum" stays about Mum."""
    assert "buy for" not in ask("what did I buy for Mum").split("\n")[0]
