"""L155: "what is most important right now" and its kin ask for the day's plan from the
notebook's own dates and open tasks, not for general knowledge."""

from __future__ import annotations

import json

import pytest

from tessellate.api import chat_said, chat_turn, routes_chat
from tessellate.core import clock
import tests._seed_composer_1110 as seed

NOW = seed.NOW


@pytest.fixture(autouse=True)
def _fixed_now(monkeypatch):
    for module in (routes_chat, chat_said, chat_turn):
        monkeypatch.setattr(module, "user_now", lambda _config: NOW)
    monkeypatch.setattr(clock, "today", lambda: NOW.date())


def _post(client, question):
    body = {"question": question, "history": [], "use_tools": False}
    with client.stream("POST", "/chat/stream", json=body) as response:
        events = [json.loads(line) for line in response.iter_lines() if line.strip()]
    return "".join(e.get("delta", "") for e in events if e.get("type") == "answer")


@pytest.mark.parametrize(
    "question",
    [
        "what is most important right now",
        "what's most important right now",
        "what is the most important thing to do",
        "what's most urgent",
        "what is urgent",
        "what's the top priority",
        "what are my priorities",
        "what matters most right now",
        "what's my most important task today",
    ],
)
def test_most_important_is_answered_from_the_notebooks_plan(client, session, question):
    seed.seed(session)
    said = _post(client, question)
    assert "general knowledge" not in said, said
    assert "Today, Tuesday 10 November" in said and "email landlord about the leak" in said, said


def test_a_general_question_about_importance_is_not_taken(client, session):
    seed.seed(session)
    assert "Open tasks" not in _post(client, "what is the most important invention in history")
