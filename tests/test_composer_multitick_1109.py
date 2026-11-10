"""Tick, untick or cancel several tasks in one sentence (composer-r6 D10):
"tick email landlord and call plumber". One card, one step per reminder, one edit
per note (two lines on one note must not undo each other). A name that is one
task's whole name ("salt and pepper") stays one task. Fake transport."""

from __future__ import annotations

import json
from datetime import datetime

import pytest
from tests._consent import confirmed

NOW = datetime(2026, 11, 9, 10, 0)
HOME = "# Home\n\n- [ ] email landlord\n- [ ] call plumber\n- [ ] water plants"


def _ask(client, question):
    with client.stream("POST", "/chat/stream", json={"question": question, "use_tools": True}) as r:
        events = confirmed(client, [json.loads(line) for line in r.iter_lines() if line.strip()])
    return next((e for e in events if e.get("type") == "act"), None), "".join(e.get("delta", "") for e in events if e.get("type") == "answer")


def _text(client, note):
    return client.get(f"/entries/{note}").json()["content"]


@pytest.mark.parametrize("said", [
    "tick email landlord and call plumber", "tick off email landlord and call plumber", "tick off email landlord, call plumber",
    "mark email landlord and call plumber as done", "tick off the email landlord and the call plumber tasks",
    "tick email landlord & call plumber off", "tick off email landlord then call plumber",
])
def test_two_ticks_on_one_note_both_land(client, said):
    note = client.post("/entries", json={"content": HOME}).json()["id"]
    card, line = _ask(client, said)
    assert card and len(card["steps"]) == 1, (said, line)
    assert _text(client, note) == "# Home\n\n- [x] email landlord\n- [x] call plumber\n- [ ] water plants"
    assert "“email landlord” and “call plumber” done" in card["label"]


def test_undo_puts_both_back(client):
    note = client.post("/entries", json={"content": HOME}).json()["id"]
    card, _ = _ask(client, "tick email landlord and call plumber")
    done = client.post("/chat/command/run", json={"steps": card["steps"]}).json()
    client.post("/chat/command/run", json={"steps": done["undo"]}) if done.get("undo") else None
    assert _text(client, note).count("[ ]") >= 1


def test_a_list_of_three_with_a_comma_and_an_and(client):
    note = client.post("/entries", json={"content": HOME}).json()["id"]
    card, _ = _ask(client, "tick off email landlord, call plumber and water plants")
    assert card and _text(client, note).count("[x]") == 3


def test_a_reminder_and_a_checklist_line_in_one_sentence(client, session):
    from tessellate.core.database import Reminder

    note = client.post("/entries", json={"content": HOME}).json()["id"]
    session.add(Reminder(text="Renew passport", due_at=datetime(2030, 1, 1, 9)))
    session.commit()
    card, _ = _ask(client, "tick off renew passport and email landlord")
    assert card and len(card["steps"]) == 2
    session.expire_all()
    assert session.query(Reminder).one().done is True and "[x] email landlord" in _text(client, note)


def test_a_name_with_and_in_it_is_one_task(client):
    note = client.post("/entries", json={"content": "# Shop\n\n- [ ] salt and pepper\n- [ ] bread"}).json()["id"]
    card, _ = _ask(client, "tick off salt and pepper")
    assert card and card["label"].startswith("Mark “salt and pepper” done")
    assert _text(client, note) == "# Shop\n\n- [x] salt and pepper\n- [ ] bread"


def test_one_found_and_one_missing_does_the_one_and_says_the_other(client):
    note = client.post("/entries", json={"content": HOME}).json()["id"]
    card, line = _ask(client, "tick email landlord and book flights")
    assert card and "email landlord" in card["label"]
    assert "[x] email landlord" in _text(client, note) and "Not done: “book flights”" in line


def test_none_found_says_so_and_changes_nothing(client):
    note = client.post("/entries", json={"content": HOME}).json()["id"]
    card, line = _ask(client, "tick book flights and buy stamps")
    assert card is None and "book flights" in line
    assert _text(client, note) == HOME


def test_untick_and_cancel_take_a_list_too(client):
    note = client.post("/entries", json={"content": "# Home\n\n- [x] email landlord\n- [x] call plumber\n- [ ] water plants"}).json()["id"]
    _ask(client, "untick email landlord and call plumber")
    assert _text(client, note) == HOME
    _ask(client, "cancel email landlord and call plumber from my tasks")
    assert _text(client, note) == "# Home\n\n- [ ] water plants"
