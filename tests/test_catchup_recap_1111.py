"""A catch-up question ("hey what's been happening?", "what's new", "catch me
up") is the activity recap's, never "Nothing is dated for the next two weeks".
Fixed clock: Wednesday 11 November 2026, 10:00. No model runs."""

from __future__ import annotations

import datetime as dt

import pytest

from tessellate.api import routes_chat
from tessellate.core import config
from tessellate.entry import manager
from tests.test_composer_route_688 import _ask

NOW = dt.datetime(2026, 11, 11, 10, 0, 0)

RECAP = [
    "what's been happening",
    "hey what's been happening?",
    "Hey, what has been happening",
    "what have I been up to",
    "what's new",
    "catch me up",
    "what did I miss",
    "hey what's new",
    "hey, catch me up",
    "anything new?",
    "what's going on lately",
]


@pytest.fixture
def ask(client, session, monkeypatch):
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)
    for text, day in (("# Gym routine\n\nPush, pull, legs.", 9), ("# Lecture 5\n\nProcesses and threads.", 10), ("# Errands\n\nBuy a notebook.", 11)):
        entry = manager.create_entry(session, text, "Personal")
        entry.created_at = entry.updated_at = dt.datetime(2026, 11, day, 9)
    session.commit()
    return lambda q: _ask(client, q, notes_only=True, answer_from="notes", history=[])["text"]


@pytest.mark.parametrize("question", RECAP)
def test_a_catch_up_is_the_recap(ask, question):
    said = ask(question)
    assert "Nothing is dated" not in said, said
    assert all(t in said for t in ("Gym routine", "Lecture 5", "Errands")), said


@pytest.mark.parametrize("question", ["what's happening this week", "what's coming up"])
def test_the_future_stays_the_agenda(ask, question):
    said = ask(question)
    assert "last 7 days" not in said.lower(), said


def test_catch_me_up_on_a_topic_is_a_recall(ask):
    assert "Lecture 5" in ask("catch me up on lecture 5")


def test_whats_happening_alone_is_small_talk(ask):
    assert "Gym routine" not in ask("whats happening")


# --- parity: a model up is handed the same recap -------------------------------------


@pytest.mark.parametrize("question", ["hey what's been happening?", "catch me up", "what did I miss", "what's new"])
def test_a_model_is_handed_the_same_recap(ai_client, fake_ollama, session, monkeypatch, question):
    from tests.test_parity_1110 import prompt_of, stream

    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)
    for text, day in (("# Gym routine\n\nPush, pull, legs.", 9), ("# Errands\n\nBuy a notebook.", 11)):
        entry = manager.create_entry(session, text, "Personal")
        entry.created_at = entry.updated_at = dt.datetime(2026, 11, day, 9)
    session.commit()
    stream(ai_client, question)
    sent = prompt_of(fake_ollama)
    assert "Gym routine" in sent and "Errands" in sent and "nothing dated" not in sent.lower(), sent[-900:]
