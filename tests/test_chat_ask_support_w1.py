"""A reopened Ask turn counts its support as the live answer did (W1 A5, chatfoot L6).

`get_ask_turn` recounted every stored turn with the model counter, so a
composed answer (no model wrote a word of it) could reopen under the
model-draft warning it never had live. The turn now keeps who wrote it.
"""

from __future__ import annotations

import json

from tessellate.core.database import AskTurn
from tessellate.entry import manager


def _ask(client, question):
    events = []
    with client.stream("POST", "/chat/stream", json={"question": question, "notes_only": True}) as r:
        for line in r.iter_lines():
            if line.strip():
                events.append(json.loads(line))
    return events


def test_a_composed_ask_turn_reopens_with_the_composed_count(ai_client, fake_ollama, session):
    manager.create_entry(session, "The beans need netting next week. The netting is in the shed.")
    session.commit()
    fake_ollama.running = False
    events = _ask(ai_client, "what did I write about beans")
    live = next(e["support"] for e in events if e.get("type") == "grounding" and e.get("exact"))
    assert live["by_model"] is False
    turn = ai_client.get("/ask-history").json()["turns"][0]
    reopened = ai_client.get(f"/ask-history/{turn['id']}").json()["support"]
    assert reopened["by_model"] is False
    assert reopened["low"] == live["low"]


def test_a_model_ask_turn_keeps_the_model_counter(ai_client, fake_ollama, session):
    manager.create_entry(session, "The beans need netting next week")
    session.commit()
    fake_ollama.librarian_reply = "You wrote about netting the beans."
    _ask(ai_client, "what did I write about beans")
    row = session.query(AskTurn).one()
    assert row.composed is False
    reopened = ai_client.get(f"/ask-history/{row.id}").json()["support"]
    assert reopened.get("by_model", True) is not False
