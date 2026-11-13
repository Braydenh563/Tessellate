"""L124: every confirm card that rewrites a note's text is locked to the text it
read (`base_hash`), not only add-to-today, so a note edited after the card was
made is refused, never overwritten."""

from __future__ import annotations

import json

import pytest


def _card(client, said):
    with client.stream("POST", "/chat/stream", json={"question": said, "use_tools": True}) as r:
        events = [json.loads(line) for line in r.iter_lines() if line.strip()]
    return next((e for e in events if e.get("type") == "act"), None)


def _seed(client):
    client.post("/entries", json={"content": "# Gym log\n\nSquats on Monday."})
    client.post("/entries", json={"content": "# Todo\n\n- [ ] buy milk\n- [ ] call the bank"})


@pytest.mark.parametrize("said", [
    "rename the gym log note to Strength plan",
    "add buy chalk to the gym log note",
    "add pay rent to my todo list",
    "tick off buy milk",
])
def test_a_text_edit_card_carries_the_hash_it_read(client, said):
    _seed(client)
    card = _card(client, said)
    assert card, said
    edits = [s for s in card["steps"] if s["name"] == "edit_note" and "content" in s["arguments"]]
    assert edits and all(s["arguments"].get("base_hash") for s in edits), card["steps"]


def test_a_note_edited_after_the_card_is_not_overwritten(client):
    _seed(client)
    card = _card(client, "add buy chalk to the gym log note")
    note = card["steps"][0]["arguments"]["note_id"]
    client.put(f"/entries/{note}", json={"content": "# Gym log\n\nSquats on Monday.\n- written meanwhile"})
    done = client.post("/chat/command/run", json={"steps": card["steps"], "skipped": []}).json()
    assert not done["ok"]
    assert client.get(f"/entries/{note}").json()["content"].endswith("- written meanwhile")
