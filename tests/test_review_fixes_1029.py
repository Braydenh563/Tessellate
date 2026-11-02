"""Review of the audit 1029 round: new input rules apply to what a person
sends, never to data coming back (a restore, an undo, a background write),
and a note-to-self stays a task in the digest."""

from __future__ import annotations

import json

import pytest

from tessellate.ai import composer_digest
from tessellate.entry import manager

#: Fixed clock for any date a test names; no test here reads the real one.
PAST = "2020-03-10T09:00:00+00:00"


def test_a_legacy_comma_tag_survives_create_and_update(session):
    entry = manager.create_entry(session, "x", tags=["work, home", "x"])
    assert json.loads(entry.tags) == ["work, home", "x"]
    manager.update_entry(session, entry, tags=[*json.loads(entry.tags), "stale"])
    assert json.loads(entry.tags) == ["work, home", "x", "stale"]


def test_a_typed_comma_tag_is_still_split(client):
    note = client.post("/entries", json={"content": "x", "tags": ["a, b"]}).json()
    assert note["tags"] == ["a", "b"]


def test_undo_brings_back_a_blank_reminder_but_a_new_one_is_refused(client):
    response = client.post("/reminders", json={"text": "  ", "due_at": PAST, "restore": True})
    assert response.status_code in (200, 201)
    response = client.post("/reminders", json={"text": "  ", "due_at": "2099-03-10T09:00:00+00:00"})
    assert response.status_code == 422


def test_undo_of_a_space_delete_keeps_its_name_as_it_was(client):
    made = client.post("/spaces", json={"name": "Garden"}).json()
    space = {"id": made["id"], "name": "Gar\u200bden", "icon": made.get("icon"), "hidden_from_all": False}
    client.delete(f"/spaces/{made['id']}")
    response = client.post("/spaces/restore", json={"space": space})
    assert response.status_code == 200, response.text
    assert response.json()["name"] == "Gar\u200bden"


@pytest.mark.parametrize("body", ["Remember to call mum", "Try to sleep earlier"])
def test_a_note_to_self_is_not_retold_as_a_fact(body):
    clause = composer_digest._clause(body, "noted", 0, True)
    assert not clause.lower().startswith("you " + body.split()[0].lower()), clause


def test_a_need_is_still_its_own_clause():
    assert composer_digest._clause("Need to cut eating out", "noted", 0, True) == "you need to cut eating out"
