"""Composer audit 2026-10-30 (Z rows): each test pins a class, asked several
ways. The fake transport stands in for a model; real inference is unverified."""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from tessellate.api import routes_chat
from tessellate.core import config
from tessellate.entry import manager

NOW = datetime(2026, 10, 30, 12, 0)


def _post(client, question: str, **body) -> str:
    text = ""
    with client.stream("POST", "/chat/stream", json={"question": question, "use_tools": False, **body}) as response:
        for line in response.iter_lines():
            if line.strip():
                event = json.loads(line)
                if event["type"] == "answer":
                    text += event["delta"]
    return text


@pytest.fixture
def clock(monkeypatch):
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)


@pytest.mark.parametrize("question", ["undo", "redo", "undo that", "undo the last change"])
def test_z64_an_app_tool_answer_carries_no_search_footer(client, session, clock, monkeypatch, question):
    from tessellate.ai import composer_digest

    monkeypatch.setattr(routes_chat, "_meaning_off", lambda: True)
    entry = manager.create_entry(session, "# Chess ideas\n\nTry the Sicilian.", category_name="Journal")
    assert entry.id

    said = _post(client, question)
    assert said.strip(), question
    assert composer_digest.PHRASES["meaning_off"] not in said, said
    assert composer_digest.PHRASES["meaning_loading"] not in said, said


@pytest.mark.parametrize("ask", [False, True])
@pytest.mark.parametrize("question", ["hello", "thanks", "ok", "hi there"])
def test_z71_a_model_that_says_nothing_to_a_greeting_still_gets_an_answer(ai_client, fake_ollama, session, clock, question, ask):
    fake_ollama.librarian_reply = ""
    assert _post(ai_client, question, notes_only=ask).strip(), (question, ask)


@pytest.mark.parametrize("reply, question", [
    ("Your dentist appointment is on Wednesday 4 November, in 5 days.", "when is my dentist appointment"),
    ("The dentist is in 5 days.", "how long until the dentist"),
    ("It is 5 days away, at 9:30.", "how far off is my dentist appointment"),
])
def test_z69_figures_the_prompt_worked_out_for_a_note_are_not_flagged(ai_client, fake_ollama, session, clock, reply, question):
    entry = manager.create_entry(session, "# Dentist\n\nDentist appointment on 4 November 2026 at 9:30.", category_name="Journal")
    entry.created_at = entry.updated_at = datetime(2026, 10, 20, 9, 0)
    session.commit()
    fake_ollama.librarian_reply = reply
    said = _post(ai_client, question)
    assert "Heads up" not in said, said
