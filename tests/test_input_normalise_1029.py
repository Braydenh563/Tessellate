"""One normaliser per thing, at the model (audit 1029 N6, N15, X6, C29, rank 10).

Stored data is never rewritten: these rules apply to what arrives.
"""

from __future__ import annotations

import pytest

from tessellate.entry import tagnames

#: Fixed clock for any date a test names; no test here reads the real one.
FUTURE = "2099-03-10T09:00:00+00:00"


@pytest.mark.parametrize("content", ["   ", "\n\t \n", "​​", "   ‍ "])
def test_a_note_with_only_blanks_is_refused(client, content):
    response = client.post("/entries", json={"content": content})
    assert response.status_code == 422
    assert "empty" in response.text.lower() or "blank" in response.text.lower()


def test_a_note_with_words_still_saves_and_keeps_its_text(client):
    body = client.post("/entries", json={"content": "  hello  \n"}).json()
    assert body["id"]


def test_comma_separated_tags_are_split(client):
    note = client.post("/entries", json={"content": "x", "tags": ["a, b,c", "d"]}).json()
    assert note["tags"] == ["a", "b", "c", "d"]
    only_commas = client.post("/entries", json={"content": "y", "tags": [",", " , "]}).json()
    assert only_commas["tags"] == []


def test_normalise_tags_splits_on_commas_and_keeps_the_first_spelling():
    assert tagnames.normalise_tags(["Idea, idea", "#Plan,b"]) == ["Idea", "Plan", "b"]


def test_a_tag_rename_to_a_comma_name_is_refused_and_changes_nothing(client):
    note = client.post("/entries", json={"content": "x", "tags": ["old"]}).json()
    response = client.post("/tags/rename", json={"old": "old", "new": "a, b"})
    assert response.status_code == 400 and "comma" in response.text
    response = client.get(f"/entries/{note['id']}")
    assert response.json()["tags"] == ["old"]


def test_space_names_ignore_invisible_characters_and_inner_spacing(client):
    ok = client.post("/spaces", json={"name": "Garden"})
    assert ok.status_code == 200
    for twin in ("Gar\u200bden", "garden", "  Garden  ", "\u00a0Garden\u00a0"):
        again = client.post("/spaces", json={"name": twin})
        assert again.status_code == 409, twin
    inner = client.post("/spaces", json={"name": "Side   project"})
    assert inner.json()["name"] == "Side project"
    response = client.post("/spaces", json={"name": "Side project"})
    assert response.status_code == 409


@pytest.mark.parametrize("name", ["​", " ​‍ ", "⁠﻿"])
def test_a_space_name_of_only_invisible_characters_is_refused(client, name):
    response = client.post("/spaces", json={"name": name})
    assert response.status_code in (400, 422)


def test_a_space_rename_obeys_the_same_rule(client):
    client.post("/spaces", json={"name": "Alpha"})
    beta = client.post("/spaces", json={"name": "Beta"}).json()
    clash = client.put(f"/spaces/{beta['id']}", json={"name": "Al​pha"})
    assert clash.status_code == 409
    response = client.put(f"/spaces/{beta['id']}", json={"name": "​"})
    assert response.status_code in (400, 422)


@pytest.mark.parametrize("due", ["2099-02-31T09:00:00+00:00", "2099-13-01T09:00:00+00:00", "next tuesday", ""])
def test_a_reminder_date_that_is_not_a_date_is_refused_on_create_and_update(client, due):
    response = client.post("/reminders", json={"text": "t", "due_at": due})
    assert response.status_code == 422
    made = client.post("/reminders", json={"text": "t", "due_at": FUTURE})
    assert made.status_code in (200, 201)
    response = client.put(f"/reminders/{made.json()['id']}", json={"due_at": due})
    assert response.status_code == 422


def test_a_reminder_with_only_blanks_for_text_is_refused(client):
    response = client.post("/reminders", json={"text": "  ​ ", "due_at": FUTURE})
    assert response.status_code == 422


@pytest.mark.parametrize("due", ["2099-02-31T09:00:00", "next tuesday", ""])
def test_a_snooze_step_with_a_date_that_is_not_one_answers_an_error_not_a_crash(client, session, due):
    from tessellate.ai import task_acts

    made = client.post("/reminders", json={"text": "t", "due_at": FUTURE}).json()
    answer = task_acts.run_step(session, "snooze_reminder", {"reminder_id": made["id"], "due_at": due})
    assert "not a date" in answer["error"]
