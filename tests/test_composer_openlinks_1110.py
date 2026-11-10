"""F13 j of the composer audit: "what links to it", "what's related" and "why are they linked"
after opening a note are about that note's links, not the word "links". Asked with a model up
or not (the exact-events hook runs first for both)."""

from __future__ import annotations

import json

import pytest

from tessellate.core import clock
from tessellate.core.database import EntryLink
from tessellate.api import chat_said, chat_turn, routes_chat
import tests._seed_composer_1110 as seed

NOW = seed.NOW


@pytest.fixture(autouse=True)
def _fixed_now(monkeypatch):
    for module in (routes_chat, chat_said, chat_turn):
        monkeypatch.setattr(module, "user_now", lambda _config: NOW)
    monkeypatch.setattr(clock, "today", lambda: NOW.date())


def _post(client, question, **extra):
    body = {"question": question, "history": [], "use_tools": False, **extra}
    with client.stream("POST", "/chat/stream", json=body) as response:
        events = [json.loads(line) for line in response.iter_lines() if line.strip()]
    return "".join(e.get("delta", "") for e in events if e.get("type") == "answer")


def _linked(session):
    seed.seed(session)
    session.add(EntryLink(source_entry_id=6, target_entry_id=7, reason="same clinic"))
    session.commit()


@pytest.mark.parametrize("question", ["what links to it", "what's related", "what is related to it", "which notes link to this note"])
def test_the_links_of_the_open_note_are_listed_with_their_reason(client, session, question):
    _linked(session)
    said = _post(client, question, open_note_id=6)
    assert "linked to [**Dentist**]" in said and "(#/notes/7)" in said and "same clinic" in said, said


def test_why_are_they_linked_names_the_reason_for_the_notes_just_shown(client, session):
    _linked(session)
    frame = {"note_ids": [6, 7], "subject": "dentist", "person": "", "ask": "dentist", "dates": [], "items": []}
    said = _post(client, "why are they linked", history=[{"question": "dentist", "answer": "Two notes.", "frame": frame}])
    assert "You linked" in said and "same clinic" in said, said


def test_a_note_with_no_links_says_so(client, session):
    seed.seed(session)
    assert "Nothing is linked to [**Dentist**]" in _post(client, "what links to it", open_note_id=6)


def test_no_open_note_leaves_the_question_to_the_other_readers(client, session):
    _linked(session)
    assert "linked to [**Dentist**]" not in _post(client, "what links to it")


def test_the_same_links_with_a_model_up(ai_client, fake_ollama, session):
    _linked(session)
    said = _post(ai_client, "what links to it", open_note_id=6)
    assert "same clinic" in said, said
