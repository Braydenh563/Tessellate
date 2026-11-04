"""INBOX 1668 (a), the owner, 2026-11-04: "help me set a reminder" was answered
with the assistant's self-introduction. Any ask to set, make, add or help with a
reminder, with or without what and when, starts the reminder act: both present
sets it (Undo is the confirm, CHAT_PLAN decision 38); one missing asks for that
one in a sentence; never the introduction, never a note's "What should the note
say?". Fixed by class (1357), model off and on alike (decision 75)."""

from __future__ import annotations

from datetime import datetime

import pytest

from tessellate.ai import reminder_parser
from tessellate.api import routes_chat
from tessellate.core import config
from tessellate.entry import manager
from tests.test_composer_route_688 import _ask

NOW = datetime(2026, 11, 4, 10, 5)

#: Nothing said: both the what and the when are asked for.
NEITHER = [
    "help me set a reminder", "set a reminder", "can you help me make a reminder", "add a reminder", "I want to set a reminder",
    "help with a reminder", "remind me", "make me a reminder", "create a reminder", "i need a reminder", "help me set reminder",
    "can u help me set a remindr", "could you help me add a reminder please", "please make a new reminder", "i'd like to create a reminder",
    "Help me set a reminder?", "hey, help me add a reminder", "pls set a reminder", "can you set me a reminder", "help me with a reminder",
    "help me make a remnder",
]
#: Both said: set, with Undo.
BOTH = [
    "help me set a reminder for friday at 3pm to ring the vet", "set a reminder to call mum tomorrow at 5pm",
    "can you help me make a reminder to call mum tomorrow at 5pm", "add a reminder to pay rent on Friday at 9am",
    "I want to set a reminder to water the plants tomorrow at 7am", "create a reminder for tomorrow at 8am to take the bins out",
]
#: One missing: that one is asked.
NO_TIME = ["help me make a reminder for the dentist", "make a reminder for the dentist", "can you help me set a reminder to call mum"]
NO_WHAT = ["help me set a reminder for 5pm", "add a reminder for tomorrow", "set a reminder for 5pm"]
INTRO = ("Atlas's assistant", "I read your notes", "I answer from your notes", "What should the note say")


@pytest.fixture
def notebook(session, monkeypatch):
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)
    manager.create_entry(session, "# Dentist\n\nCheck-up booked for the 21st.")
    session.commit()


@pytest.mark.parametrize("said", NEITHER)
def test_an_ask_for_a_reminder_asks_what_and_when(client, notebook, said):
    text = _ask(client, said)["text"]
    assert not any(w in text for w in INTRO), text
    assert "remind you about, and when" in text, text


@pytest.mark.parametrize("said", BOTH)
def test_an_ask_with_what_and_when_sets_it(client, notebook, said):
    out = _ask(client, said)
    assert out["text"].startswith("Done. I will remind you"), out["text"]


@pytest.mark.parametrize("said", NO_TIME)
def test_an_ask_with_no_time_asks_the_time(client, notebook, said):
    text = _ask(client, said)["text"]
    assert not any(w in text for w in INTRO) and ("dentist" in text or "call mum" in text) and text.rstrip().endswith("?"), text


@pytest.mark.parametrize("said", NO_WHAT)
def test_an_ask_with_no_what_asks_the_what(client, notebook, said):
    text = _ask(client, said)["text"]
    assert not any(w in text for w in INTRO) and "What should I remind you about" in text, text


@pytest.mark.parametrize("said", ["help me set a reminder", "make me a reminder", "add a reminder", "help with a reminder"])
def test_the_same_with_a_model_running(ai_client, fake_ollama, notebook, said):
    """With a model running a notes-only turn is still composed (decision 70):
    the reminder act is named, never the introduction; the model is not asked."""
    before = len(fake_ollama.chat_models)
    text = _ask(ai_client, said, notes_only=True, use_tools=False)["text"]
    assert not any(w in text for w in INTRO), text
    assert "set a reminder" in text, text
    assert len(fake_ollama.chat_models) == before


@pytest.mark.parametrize(
    "said",
    ["what reminders do I have", "help me find my reminders", "show my reminders", "when is the dentist reminder", "I set a reminder yesterday", "reminder"],
)
def test_a_question_about_reminders_is_not_the_ask(said):
    assert reminder_parser.canonical_ask(said) == said


@pytest.mark.parametrize("said", [w for w in NEITHER + BOTH if w != "remind me"])
def test_the_ask_reads_as_set_a_reminder(said):
    assert reminder_parser.canonical_ask(said).lower().startswith("set a reminder"), said
