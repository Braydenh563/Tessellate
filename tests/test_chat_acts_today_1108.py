"""Add to today's note by chat (CHAT_PLAN X10, acts-1108): "add buy milk to
today's note" is a confirm card that appends a bullet to the daily note, locked
to the text it read (`edit_conflicts.content_hash`), so a note edited in between
is refused rather than overwritten. A question about the daily note is never the
act. Every provider runs against a fake transport (CLAUDE.md section 4)."""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from tessellate.ai import starter_acts

NOW = datetime(2026, 11, 8, 10, 0)
HEADING = "# 2026-11-08"


@pytest.fixture(autouse=True)
def _clock(monkeypatch):
    from tessellate.api import routes_chat

    monkeypatch.setattr("tessellate.core.config.user_now", lambda _config: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _config: NOW)


def _events(client, question, **body):
    with client.stream("POST", "/chat/stream", json={"question": question, "use_tools": True, **body}) as r:
        assert r.status_code == 200
        return [json.loads(line) for line in r.iter_lines() if line.strip()]


def _card(client, said):
    return next((e for e in _events(client, said) if e.get("type") == "act"), None)


def _confirm(client, card):
    return client.post("/chat/command/run", json={"steps": card["steps"], "skipped": card.get("skipped", [])}).json()


def _today(client, body="- call the bank"):
    return client.post("/entries", json={"content": f"{HEADING}\n\n{body}"}).json()["id"]


@pytest.mark.parametrize("said, words", [
    ("add buy milk to today's note", "buy milk"),
    ("Add buy milk to today's note.", "buy milk"),
    ("put call the bank in my daily note", "call the bank"),
    ("please add pay rent to the daily note", "pay rent"),
    ("add to today's note: call the bank", "call the bank"),
])
def test_it_is_read_with_the_words_kept(said, words):
    kind, slots = starter_acts.read(said)
    assert kind == "append_today" and slots["words"] == words


@pytest.mark.parametrize("said", [
    "what did I add to today's note", "how do I add to today's note", "add to today's note", "what is in today's note",
    "show me today's note", "can I add things to today's note",
])
def test_a_question_or_a_gap_is_not_the_act(said):
    assert starter_acts.read(said) is None or starter_acts.read(said)[0] != "append_today"


def test_it_appends_a_bullet_after_confirm_and_undo_puts_it_back(client):
    note = _today(client)
    card = _card(client, "add buy milk to today's note")
    assert card and not card.get("done") and card["label"] == "Add “Buy milk” to the end of today's note"
    assert client.get(f"/entries/{note}").json()["content"].endswith("- call the bank"), "nothing writes on read"
    outcome = _confirm(client, card)
    assert outcome["ok"]
    assert client.get(f"/entries/{note}").json()["content"] == f"{HEADING}\n\n- call the bank\n- Buy milk"
    client.post("/chat/command/run", json={"steps": outcome["undo"]})
    assert client.get(f"/entries/{note}").json()["content"] == f"{HEADING}\n\n- call the bank"


def test_no_daily_note_yet_starts_one(client):
    card = _card(client, "add buy milk to today's note")
    assert card and card["label"] == "Start today's note with “Buy milk”" and card["steps"][0]["name"] == "create_note"


def test_a_note_edited_since_the_card_was_made_is_not_overwritten(client):
    note = _today(client)
    card = _card(client, "add buy milk to today's note")
    client.put(f"/entries/{note}", json={"content": f"{HEADING}\n\n- call the bank\n- written meanwhile"})
    outcome = _confirm(client, card)
    assert not outcome["ok"] and "changed since the card was made" in outcome["summary"]
    assert client.get(f"/entries/{note}").json()["content"].endswith("- written meanwhile")


def test_a_private_daily_note_is_not_written(client, session):
    from tessellate.core.database import Entry

    note = _today(client)
    session.get(Entry, note).is_private = True
    session.commit()
    card = _card(client, "add buy milk to today's note")
    assert card is None, "nothing is offered for a private note"
