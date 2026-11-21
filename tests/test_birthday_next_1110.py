"""compleft2: "whose birthday is next" is the dated-people reader. One birthday still answers, the
asking varies ("who has the next birthday"), both date orders are read, and a model up gets the
same answer (CHAT_PLAN decision 75: the model reads the note and its distance in the prompt; the figures reader is not a facts turn, `chat_turn._facts_turn`). Clock: Tuesday
10 November 2026, 09:00."""

from __future__ import annotations

from datetime import datetime

import pytest

from tessellate.api import chat_said, chat_turn, routes_chat
from tessellate.entry import manager
from tests.test_parity_1110 import prompt_of, stream

NOW = datetime(2026, 11, 10, 9, 0)
ASKS = ["whose birthday is next", "who has the next birthday", "when is the next birthday"]


@pytest.fixture(autouse=True)
def _fixed_now(monkeypatch):
    for module in (routes_chat, chat_said, chat_turn):
        monkeypatch.setattr(module, "user_now", lambda _config: NOW)


def _notes(session, *contents: str) -> None:
    for content in contents:
        manager.create_entry(session, content, category_name="People")
    session.commit()


@pytest.mark.parametrize("question", ASKS)
def test_one_birthday_is_the_next(client, session, question):
    _notes(session, "# Anna\n\nAnna's birthday is 3 December.", "# Plumber\n\nCall on Tuesday.")
    said = stream(client, question)["text"]
    assert "Anna" in said and "3 December" in said and "23 days" in said, said


def test_the_month_first_order_is_read(client, session):
    _notes(session, "# Anna\n\nBirthday: December 3.", "# Mia\n\nMia's birthday is on the 9th of February.")
    said = stream(client, "whose birthday is next")["text"]
    assert "Anna" in said and "3 December" in said and "Mia" in said and "9 February" in said, said


def test_the_nearest_wraps_into_next_year(client, session):
    _notes(session, "# Mia\n\nMia's birthday is 9 February.")
    said = stream(client, "whose birthday is next")["text"]
    assert "Mia" in said and "9 February 2027" in said, said


def test_no_birthday_in_the_notes_is_not_invented(client, session):
    _notes(session, "# Plumber\n\nCall on Tuesday.")
    said = stream(client, "whose birthday is next")["text"]
    assert "3 December" not in said and "Anna" not in said, said


def test_a_model_up_is_handed_the_birthday_and_its_distance(ai_client, fake_ollama, session):
    _notes(session, "# Anna\n\nAnna's birthday is 3 December.")
    stream(ai_client, "whose birthday is next", use_tools=True)
    sent = prompt_of(fake_ollama)
    assert "Anna's birthday is 3 December" in sent and "in 23 days" in sent, sent[-700:]
