"""INBOX 1468: an overdue or repeating-overdue reminder could not be saved.

The edit form sent `due_at` on every Save, so an overdue reminder's own past
time (cut to the minute by the datetime field) hit the past-date rule and came
back 422, and nothing on the page said so. The route accepts the time a
reminder already has, the form leaves an unchanged time out, a refusal is a
toast with the reason (the form stays open), and Save sits one gap under the
fields.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from tests._app_js import JS_DIR


def _iso(moment: datetime) -> str:
    return moment.isoformat()


def _overdue(client, **extra) -> dict:
    due = datetime.now(timezone.utc) - timedelta(days=11)
    body = {"text": "Do my tax return", "due_at": _iso(due), "restore": True, **extra}
    response = client.post("/reminders", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def test_an_overdue_reminder_saves_with_its_own_past_time(client):
    made = _overdue(client)
    #: The form's field is cut to the minute, so the time sent is not the stored one to the second.
    own = datetime.fromisoformat(made["due_at"]).replace(second=0, microsecond=0)
    response = client.put(f"/reminders/{made['id']}", json={"text": "Do my tax return today", "due_at": _iso(own)})
    assert response.status_code == 200, response.text
    assert response.json()["text"] == "Do my tax return today"


def test_a_repeating_overdue_reminder_saves_with_its_own_past_time(client):
    made = _overdue(client, recurring="weekly")
    own = datetime.fromisoformat(made["due_at"]).replace(second=0, microsecond=0)
    response = client.put(
        f"/reminders/{made['id']}",
        json={"text": "Weekly review", "due_at": _iso(own), "recurring": "weekly", "priority": "high", "alert_minutes": 0},
    )
    assert response.status_code == 200, response.text
    assert response.json()["recurring"] == "weekly"


def test_an_overdue_reminder_saves_with_a_new_future_time(client):
    made = _overdue(client)
    new = datetime.now(timezone.utc) + timedelta(days=4)
    response = client.put(f"/reminders/{made['id']}", json={"due_at": _iso(new)})
    assert response.status_code == 200
    assert datetime.fromisoformat(response.json()["due_at"]) > datetime.now(timezone.utc)


def test_a_different_past_time_is_still_refused_with_the_reason(client):
    made = _overdue(client)
    other = datetime.fromisoformat(made["due_at"]) - timedelta(days=3)
    response = client.put(f"/reminders/{made['id']}", json={"due_at": _iso(other)})
    assert response.status_code == 422
    assert "in the past" in response.json()["detail"]


def _form() -> str:
    source = (JS_DIR / "reminder-edit.js").read_text(encoding="utf-8")
    match = re.search(r"^function reminderEditForm\(reminder\) \{.*?^\}", source, re.S | re.M)
    assert match, "reminderEditForm is gone"
    return match.group(0)


def test_save_leaves_an_unchanged_time_out_of_the_request():
    form = _form()
    assert "toLocalInputValue(reminder.due_at)" in form and "dueInput.value !== " in form
    assert "due_at: new Date(dueInput.value).toISOString()," not in form, "due_at must be sent only when the time changed"


def test_a_refused_save_says_why_and_keeps_the_form_open():
    form = _form()
    save = form[form.index('smallButton("Save"'):form.index('smallButton("Cancel"')]
    assert "catch (error)" in save
    assert "toast(error.message" in save and "true)" in save
    assert "editingReminderId = reminder.id" in save, "a refused save must not drop the form on the next refresh"


def test_the_action_row_sits_one_gap_under_the_fields():
    form = _form()
    assert 'row.style.marginTop = "var(--space-2)"' in form
