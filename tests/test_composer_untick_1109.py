"""Untick by chat, no model (composer-r6 E7): untick X, mark X undone and
"undo that" after a tick reopen a ticked reminder or checklist line at once,
with Undo. Fake transport throughout."""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from tessellate.ai import commands
from tests._consent import confirmed

NOW = datetime(2026, 11, 9, 10, 0)
LIST = "# Packing\n\n- [x] charger\n- [ ] passport\n- [x] socks"


@pytest.mark.parametrize("said, about", [
    ("untick charger", "charger"), ("Untick the charger.", "charger"), ("un-tick charger", "charger"), ("uncheck the charger", "charger"),
    ("please untick charger", "charger"), ("untick charger off the list", "charger"), ("mark charger as not done", "charger"),
    ("mark the charger not done", "charger"), ("mark charger incomplete", "charger"), ("mark charger as open", "charger"),
    ("reopen the charger task", "charger"), ("uncomplete charger", "charger"),
])
def test_an_untick_is_read_in_its_phrasings(said, about):
    got = commands.read(said, NOW)
    assert got and got["intent"] == "uncomplete" and got["about"] == about, got


@pytest.mark.parametrize("said", ["mark charger done", "tick off charger", "untick", "mark the report as done"])
def test_a_tick_is_not_an_untick(said):
    got = commands.read(said, NOW)
    assert (got or {}).get("intent") != "uncomplete", got


def _ask(client, question, **body):
    with client.stream("POST", "/chat/stream", json={"question": question, "use_tools": True, **body}) as r:
        return [json.loads(line) for line in r.iter_lines() if line.strip()]


def _text(client, note):
    return client.get(f"/entries/{note}").json()["content"]


def test_a_checklist_line_is_reopened_and_undo_ticks_it_again(client):
    note = client.post("/entries", json={"content": LIST}).json()["id"]
    events = _ask(client, "untick charger")
    card = next(e for e in events if e.get("type") == "act")
    assert card["label"].startswith("Mark “charger” not done")
    assert _text(client, note) == LIST, "waits for Confirm (owner, 2026-11-10)"
    confirmed(client, events)
    assert _text(client, note) == LIST.replace("[x] charger", "[ ] charger")
    assert "[x] socks" in _text(client, note), "only the one line"


def test_a_ticked_reminder_is_reopened(client, session):
    from tessellate.core.database import Reminder

    session.add(Reminder(text="Call the dentist", due_at=datetime(2030, 1, 1, 9), done=True))
    session.commit()
    events = _ask(client, "mark the dentist task as not done")
    session.expire_all()
    assert session.query(Reminder).one().done is True, "waits for Confirm"
    confirmed(client, events)
    session.expire_all()
    assert session.query(Reminder).one().done is False


def test_an_item_that_is_not_ticked_says_so(client):
    client.post("/entries", json={"content": LIST})
    said = "".join(e.get("delta", "") for e in _ask(client, "untick passport") if e.get("type") == "answer")
    assert "not ticked off" in said and "passport" in said


def test_an_item_that_is_nowhere_says_so(client):
    client.post("/entries", json={"content": LIST})
    said = "".join(e.get("delta", "") for e in _ask(client, "untick bread") if e.get("type") == "answer")
    assert "I found no ticked task or reminder named “bread”" in said


def test_undo_that_after_a_tick_unticks_it(client):
    note = client.post("/entries", json={"content": LIST}).json()["id"]
    confirmed(client, _ask(client, "tick off passport"))
    assert "[x] passport" in _text(client, note)
    history = [{"question": "tick off passport", "answer": "Mark “passport” done (in Packing)."}]
    for said in ("undo that", "undo", "Undo it."):
        confirmed(client, _ask(client, "tick off passport"))
        confirmed(client, _ask(client, said, history=history))
        assert "[ ] passport" in _text(client, note), said


def test_undo_after_something_else_unticks_nothing(client):
    note = client.post("/entries", json={"content": LIST}).json()["id"]
    _ask(client, "undo", history=[{"question": "pin the gym note", "answer": "Pinned."}])
    assert _text(client, note) == LIST
