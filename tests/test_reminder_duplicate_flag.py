"""dog2 item 7: creating a reminder that repeats an open one says so.

The reminder is still made (two exams on one day are legitimate); the answer
carries `duplicate` so the Reminders box can tell the person.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from tests._frozen_clock import FIXED_NOW, freeze_reminder_clock


@pytest.fixture(autouse=True)
def _fixed_now(monkeypatch):
    freeze_reminder_clock(monkeypatch)


def test_second_identical_reminder_is_flagged_but_made(client):
    due = (FIXED_NOW + timedelta(days=2)).isoformat()
    first = client.post("/reminders", json={"text": "Exam", "due_at": due}).json()
    assert first["duplicate"] is False
    again = client.post("/reminders", json={"text": " exam ", "due_at": due})
    assert again.status_code == 201
    assert again.json()["duplicate"] is True
    listed = client.get("/reminders").json()
    assert len(listed) == 2


def test_a_different_time_or_a_done_twin_is_not_a_duplicate(client):
    due = (FIXED_NOW + timedelta(days=2)).isoformat()
    later = (FIXED_NOW + timedelta(days=3)).isoformat()
    made = client.post("/reminders", json={"text": "Exam", "due_at": due}).json()
    other_time = client.post("/reminders", json={"text": "Exam", "due_at": later}).json()
    assert other_time["duplicate"] is False
    client.put(f"/reminders/{made['id']}", json={"done": True})
    after_done = client.post("/reminders", json={"text": "Exam", "due_at": due}).json()
    assert after_done["duplicate"] is False
