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
    # The offer is at boot; the prompt and the POST load on the press (boot scripts' cap).
    assert "Add outcome" in frontend_text("shell-reminders.js")
    assert "loadReminders.outcomeAsk(reminder)" in frontend_text("shell-reminders.js")
    assert "/outcome`" in frontend_text("reminder-edit.js")


def test_two_outcomes_at_once_both_land(client, monkeypatch):
    """Source text: review (reminder_outcome): the note was read, then written
    through `update_entry`; two outcomes at once both read the old text and the
    second save dropped the first's line. Outcomes now append under one lock
    from a fresh read."""
    import threading
    import time

    from fastapi.testclient import TestClient

    from tessellate.api import routes_entries

    entry = client.post("/entries", json={"content": "Kitchen sink leaks"}).json()
    first = _reminder(client, entry_id=entry["id"])
    second = client.post(
        "/reminders",
        json={"text": "buy a washer", "due_at": (FIXED_NOW + timedelta(days=2)).isoformat(), "entry_id": entry["id"]},
    ).json()
    real = routes_entries.update_entry

    def slow(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        time.sleep(0.3)
        return real(*args, **kwargs)

    monkeypatch.setattr(routes_entries, "update_entry", slow)
    codes = []

    def post(rid, text):  # noqa: ANN001, ANN202
        other = TestClient(client.app)
        other.headers.update(client.headers)
        codes.append(other.post(f"/reminders/{rid}/outcome", json={"text": text}).status_code)

    runs = [threading.Thread(target=post, args=a) for a in ((first["id"], "Booked"), (second["id"], "Bought"))]
    for run in runs:
        run.start()
    for run in runs:
        run.join(10)
    content = client.get(f"/entries/{entry['id']}").json()["content"]
    assert codes == [200, 200]
    assert "Outcome of call the plumber: Booked" in content and "Outcome of buy a washer: Bought" in content
