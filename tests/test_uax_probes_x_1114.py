"""CHAT_PLAN Acting rows X2 to X17 (LEDGER L-chat-100 to 107): the plan line's own phrasing asked of the
audit-1031 notebook with tools on and no model; the confirm card is read, nothing is confirmed here."""

from __future__ import annotations

import pytest

from tests import _seed_1031c as seed


@pytest.fixture
def act(client, session, monkeypatch):
    seed.seed(session)
    go = seed.asker(client, monkeypatch, chat=True)
    return lambda question, history=None: go(question, history=history)


def test_x2_tag_my_gym_notes_with_a_hash_resolves_the_notes_and_shows_the_card(act):
    text, events = act("tag my gym notes #fitness")
    assert "#fitness" in text and "Confirm" in text, text


def test_x11_the_summary_just_given_is_saved_as_a_note_on_confirm(act):
    said, _ = act("summarise the Tokyo trip")
    text, _ = act("save the summary as a note", history=[{"question": "summarise the Tokyo trip", "answer": said}])
    assert "Confirm" in text and "Tokyo trip" in text, text
