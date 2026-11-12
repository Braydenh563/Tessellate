"""A completed reminder's one-line outcome is written into its note (L-general-10).

Ticking a reminder off offers "Add outcome"; the line lands at the end of the
note the reminder is about, so the note keeps what came of it.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from tests._app_js import frontend_text
from tests._frozen_clock import FIXED_NOW, freeze_reminder_clock


@pytest.fixture(autouse=True)
def _fixed_now(monkeypatch):
    freeze_reminder_clock(monkeypatch)


def _reminder(client, **extra):
    due = (FIXED_NOW + timedelta(days=1)).isoformat()
    response = client.post("/reminders", json={"text": "call the plumber", "due_at": due, **extra})
    assert response.status_code in (200, 201)
    return response.json()


def test_outcome_is_appended_to_the_note(client):
    entry = client.post("/entries", json={"content": "Kitchen sink leaks"}).json()
    reminder = _reminder(client, entry_id=entry["id"])
    response = client.post(f"/reminders/{reminder['id']}/outcome", json={"text": "  Booked for Tuesday  "})
    assert response.status_code == 200
    content = client.get(f"/entries/{entry['id']}").json()["content"]
    assert content.startswith("Kitchen sink leaks")
    assert content.rstrip().endswith("Outcome of call the plumber: Booked for Tuesday")


def test_outcome_needs_a_note_and_words(client):
    loose = _reminder(client)
    no_note = client.post(f"/reminders/{loose['id']}/outcome", json={"text": "done"})
    entry = client.post("/entries", json={"content": "Kitchen sink leaks"}).json()
    tied = _reminder(client, entry_id=entry["id"])
    blank = client.post(f"/reminders/{tied['id']}/outcome", json={"text": "   "})
    missing = client.post("/reminders/999999/outcome", json={"text": "x"})
    assert (no_note.status_code, blank.status_code, missing.status_code) == (400, 422, 404)

def test_ticking_off_a_reminder_with_a_note_offers_the_outcome():
    source = frontend_text("shell-reminders.js")
    assert "Add outcome" in source
    assert "/outcome`" in source
