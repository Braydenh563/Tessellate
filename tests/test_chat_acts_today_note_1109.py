"""Put a note into today's note by chat (owner 2026-11-09): "put it in today's
note" appends the referenced note (its text, a link back as a heading) to the
daily note, made when missing; Undo takes the append back. "It" is the attached
note, else the note the last answer cited, else a note named ("the boiler
note"). It is never read as a move with no target. Fake transport throughout."""

from __future__ import annotations

import json
from datetime import datetime

import pytest

NOW = datetime(2026, 11, 9, 10, 0)
HEADING = "# 2026-11-09"
BODY = "# Dentist\n\nCheck-up on 11 November at 9."
BLOCK = "### [[Dentist]]\n\nCheck-up on 11 November at 9."


@pytest.fixture(autouse=True)
def _clock(monkeypatch):
    from tessellate.api import routes_chat

    monkeypatch.setattr("tessellate.core.config.user_now", lambda _config: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _config: NOW)


def _events(client, question, **body):
    with client.stream("POST", "/chat/stream", json={"question": question, "use_tools": True, **body}) as r:
        return [json.loads(line) for line in r.iter_lines() if line.strip()]


def _card(client, said, **body):
    return next((e for e in _events(client, said, **body) if e.get("type") == "act"), None)


def _run(client, card):
    return client.post("/chat/command/run", json={"steps": card["steps"], "skipped": card.get("skipped", [])}).json()


def _text(client, note):
    return client.get(f"/entries/{note}").json()["content"]


PHRASES = [
    "put it in today's note", "Put it in today's note.", "add this to the daily note", "append that to my daily note",
    "put that in today's journal", "add it to today's note", "please put it in my daily note",
]


@pytest.mark.parametrize("said", PHRASES)
def test_the_attached_note_starts_today_and_undo_removes_it(client, session, said):
    note = client.post("/entries", json={"content": BODY}).json()["id"]
    card = _card(client, said, note_ids=[note])
    assert card and card["steps"][0]["name"] == "create_note", said
    assert card["steps"][0]["arguments"]["content"] == f"{HEADING}\n\n{BLOCK}"
    assert "Dentist" in card["label"] and "today's note" in card["label"]
    assert _text(client, note) == BODY, "nothing writes on read"
    done = _run(client, card)
    assert done["ok"]
    assert len(client.get("/entries").json()) == 2
    client.post("/chat/command/run", json={"steps": done["undo"]})
    assert [e["content"] for e in client.get("/entries").json()] == [BODY]


def test_it_appends_to_the_daily_note_that_is_there_and_undo_puts_it_back(client):
    note = client.post("/entries", json={"content": BODY}).json()["id"]
    today = client.post("/entries", json={"content": f"{HEADING}\n\n- call the bank"}).json()["id"]
    card = _card(client, "put it in today's note", note_ids=[note])
    done = _run(client, card)
    assert done["ok"]
    assert _text(client, today) == f"{HEADING}\n\n- call the bank\n\n{BLOCK}"
    client.post("/chat/command/run", json={"steps": done["undo"]})
    assert _text(client, today) == f"{HEADING}\n\n- call the bank"


def test_it_with_nothing_attached_is_the_note_the_last_answer_cited(client):
    client.post("/entries", json={"content": BODY})
    history = [{"question": "tell me about the dentist", "answer": "Dentist check-up.", "objects": ["Dentist"]}]
    card = _card(client, "put it in today's note", history=history)
    assert card and card["steps"][0]["arguments"]["content"] == f"{HEADING}\n\n{BLOCK}"


def test_a_note_named_is_put_in(client):
    client.post("/entries", json={"content": BODY})
    card = _card(client, "add the dentist note to the daily note")
    assert card and card["steps"][0]["arguments"]["content"] == f"{HEADING}\n\n{BLOCK}"


def test_it_with_no_note_to_mean_asks_which_and_is_never_a_move(client):
    out = _events(client, "put it in today's note")
    assert not any(e.get("type") == "act" for e in out)
    said = "".join(e.get("delta", "") for e in out if e.get("type") == "answer")
    assert "Which note" in said and "nothing to move" not in said


def test_a_private_note_is_not_copied_into_the_daily_note(client, session):
    from tessellate.core.database import Entry

    note = client.post("/entries", json={"content": BODY}).json()["id"]
    session.get(Entry, note).is_private = True
    session.commit()
    assert _card(client, "put it in today's note", note_ids=[note]) is None
