"""WORLD_CLASS_PLAN D8 (section 8, row 34): snooze 10m, 1h and tomorrow, and the
reminder row on the notes' row recipe."""

from __future__ import annotations

from pathlib import Path

JS = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "shell-reminders.js").read_text(encoding="utf-8")


def test_a_reminder_snoozes_ten_minutes_an_hour_and_to_tomorrow():
    row = JS[JS.index("function reminderItem(") : JS.index("function reminderTarget(")]
    assert "Snooze 10 minutes" in row and "10 * 60 * 1000" in row
    assert '"Snooze one hour"' in row and 'presetDate("tomorrow")' in row


def test_the_reminder_row_is_the_notes_row_recipe():
    groups = JS[JS.index('const groupsBox = $("reminder-groups");') :]
    assert 'ul.className = "entry-list";' in groups
    row = JS[JS.index("function reminderItem(") :]
    assert 'row.className = "entry-meta";' in row


def test_a_snooze_has_an_undo_that_may_restore_a_past_time(client):
    """Undo of a snooze puts back the old time, usually already past (an
    overdue reminder is the one snoozed), so `restore` skips the past-date rule."""
    from datetime import datetime, timedelta, timezone

    soon = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    made = client.post("/reminders", json={"text": "x", "due_at": soon}).json()
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    assert client.put(f"/reminders/{made['id']}", json={"due_at": past}).status_code == 422
    restored = client.put(f"/reminders/{made['id']}", json={"due_at": past, "restore": True})
    assert restored.status_code == 200
    assert restored.json()["due_at"][:10] == past[:10]


def test_the_snooze_function_pushes_an_undo():
    # Moved to the lazy reminder-edit.js (the boot gzip budget, INBOX 1578); the rule is the same.
    lazy = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "reminder-edit.js").read_text(encoding="utf-8")
    assert 'lazyScript("/js/reminder-edit.js").then(() => snoozeReminderTo(' in JS
    body = lazy.split("async function snoozeReminderTo(", 1)[1].split("\n}\n", 1)[0]
    assert "pushUndo(" in body and "restore: true" in body and '"Undo"' in body
