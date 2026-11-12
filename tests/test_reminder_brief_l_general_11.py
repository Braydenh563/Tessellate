"""A reminder that names a person or topic brings its last related notes when it fires (L-general-11).

`GET /reminders/{id}/brief` finds the notes the reminder's words point at,
newest first, without the reminder's own note or a private one; the fire
toast offers to open them.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from tests._app_js import frontend_text
from tests._frozen_clock import FIXED_NOW, freeze_reminder_clock


@pytest.fixture(autouse=True)
def _fixed_now(monkeypatch):
    freeze_reminder_clock(monkeypatch)


def _reminder(client, text, **extra):
    due = (FIXED_NOW + timedelta(days=1)).isoformat()
    response = client.post("/reminders", json={"text": text, "due_at": due, **extra})
    assert response.status_code in (200, 201)
    return response.json()


def test_brief_lists_related_notes_without_its_own(client):
    own = client.post("/entries", json={"content": "Agenda for Priya Raman catch up"}).json()
    one = client.post("/entries", json={"content": "Priya Raman wants the budget figures"}).json()
    two = client.post("/entries", json={"content": "Lunch with Priya Raman went well"}).json()
    client.post("/entries", json={"content": "Bread proving times"})
    reminder = _reminder(client, "Meet Priya Raman", entry_id=own["id"])
    response = client.get(f"/reminders/{reminder['id']}/brief")
    assert response.status_code == 200
    ids = [note["id"] for note in response.json()["notes"]]
    assert set(ids) == {one["id"], two["id"]}
    assert all(note["title"] for note in response.json()["notes"])


def test_brief_is_at_most_three_and_empty_without_a_match(client):
    for n in range(5):
        client.post("/entries", json={"content": f"Quarterly budget review note {n}"})
    full = client.get(f"/reminders/{_reminder(client, 'budget review')['id']}/brief")
    empty = client.get(f"/reminders/{_reminder(client, 'zebra xylophone')['id']}/brief")
    assert (full.status_code, len(full.json()["notes"])) == (200, 3)
    assert empty.json()["notes"] == []


def test_fire_toast_offers_the_brief():
    text = frontend_text("reminder-notify.js")
    assert "/brief" in text
    assert "openNoteEditor" in text
