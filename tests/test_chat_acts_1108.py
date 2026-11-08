"""Chat verbs that act (CHAT_PLAN X5, X8, X10, X17, acts-1108): cancel a card
that waits, rename a tag or category, restore from the bin, add to today's
note. Every write waits for Confirm; nothing writes on read; a question about
the verb or a sentence that only shares its words is never read as the act.
Every provider runs against a fake transport (CLAUDE.md section 4)."""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from tessellate.ai import acts, commands, composer_cancel
from tessellate.ai.composer_dialogue import Dialogue

NOW = datetime(2026, 11, 8, 10, 0)


def _events(client, question, **body):
    with client.stream("POST", "/chat/stream", json={"question": question, "use_tools": True, **body}) as r:
        assert r.status_code == 200
        return [json.loads(line) for line in r.iter_lines() if line.strip()]


def _text(events) -> str:
    return " ".join(e.get("delta", "") for e in events if e.get("type") == "answer")


# --- X17: cancel -------------------------------------------------------------------------

WAITING = [{"question": "delete the boiler note", "answer": "Move the note “Boiler” to the bin. Confirm to do it.", "pending_act": "Move the note “Boiler” to the bin"}]


@pytest.mark.parametrize("said", ["cancel", "Cancel.", "never mind", "nevermind", "Never mind!", "forget it", "ok forget that", "cancel that please", "scrap it"])
def test_cancel_words_drop_the_waiting_card(said):
    events = composer_cancel.reply(said, WAITING)
    #: The reply now names the card it drops (review 1108), so the page closes that one, not every open card.
    assert events and events[1] == {"type": "act", "cancel": True, "label": "Move the note “Boiler” to the bin"}
    assert events[0]["delta"] == "Cancelled: move the note “Boiler” to the bin. Nothing was changed."


@pytest.mark.parametrize("said", ["cancel", "never mind", "forget it"])
def test_cancel_with_no_card_waiting_falls_through(said):
    assert composer_cancel.reply(said, [{"question": "hi", "answer": "Hello."}]) is None
    assert composer_cancel.reply(said, []) is None


@pytest.mark.parametrize("said", [
    "cancel my gym membership note", "cancel the dentist task", "how do I cancel a reminder", "what did I cancel", "never mind the boiler note",
    "forget it is Friday", "cancel culture essay",
])
def test_a_sentence_that_only_shares_the_words_is_not_a_cancel(said):
    assert composer_cancel.reply(said, WAITING) is None


def test_dialogue_reads_the_waiting_card_from_the_last_turn_only():
    assert Dialogue.from_history(WAITING).pending_act == "Move the note “Boiler” to the bin"
    later = [*WAITING, {"question": "thanks", "answer": "Welcome."}]
    assert Dialogue.from_history(later).pending_act == ""
    assert Dialogue.from_history(None).pending_act == ""


def test_cancel_in_the_chat_drops_the_card_and_writes_nothing(client):
    note = client.post("/entries", json={"content": "# Boiler service\n\nDue in March."}).json()["id"]
    sent = _events(client, "delete the boiler note")
    card = next(e for e in sent if e.get("type") == "act")
    assert not card.get("done") and card["steps"][0]["name"] == "delete_note"
    history = [{"question": "delete the boiler note", "answer": _text(sent), "pending_act": card["label"]}]
    events = _events(client, "never mind", history=history)
    assert [e["type"] for e in events if e["type"] in ("act", "answer")] == ["answer", "act"]
    assert next(e for e in events if e["type"] == "act")["cancel"] is True
    assert "Nothing was changed" in _text(events)
    assert client.get(f"/entries/{note}").status_code == 200


def test_cancel_in_the_chat_with_no_card_is_not_the_cancel_reply(client):
    events = _events(client, "never mind", history=[{"question": "hi", "answer": "Hello."}])
    assert "Cancelled:" not in _text(events)
    assert not any(e.get("cancel") for e in events)


def test_cancel_a_task_is_still_the_task_act():
    assert commands.read_typed("cancel the dentist task", NOW)["intent"] == "cancel"
    assert commands.read_typed("cancel my gym membership note", NOW) is None
    assert acts.parse("how do I cancel a reminder", NOW) is None
