"""Drag to reschedule a reminder on the calendar (TIMELINE_PLAN section 9,
decision 16, step 3).

The calendar moves a reminder with the reminders' own `PUT` (`due_at`), and
undoes it with the same `PUT` and `restore`, which the past-date rule lets
through because the time an undo goes back to may already be gone. What has
to hold: the move keeps everything but the time, a move into the past is
refused with words, and the undo puts back the exact time.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone


def _iso(moment: datetime) -> str:
    return moment.replace(microsecond=0).isoformat()


def _make(client, **extra) -> dict:
    due = datetime.now(timezone.utc) + timedelta(days=1)
    body = {"text": "Water the plants", "due_at": _iso(due), "priority": "high", "recurring": "weekly", **extra}
    response = client.post("/reminders", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def test_a_drop_moves_the_due_time_and_nothing_else(client):
    made = _make(client, alert_minutes=30)
    old = datetime.fromisoformat(made["due_at"])
    new = old + timedelta(days=3)
    response = client.put(f"/reminders/{made['id']}", json={"due_at": _iso(new.replace(tzinfo=timezone.utc))})
    assert response.status_code == 200, response.text
    moved = response.json()
    assert datetime.fromisoformat(moved["due_at"]).replace(tzinfo=None) == new.replace(tzinfo=None, microsecond=0)
    for key in ("text", "priority", "recurring", "alert_minutes", "done"):
        assert moved[key] == made[key], key


def test_a_drop_into_the_past_is_refused_with_words(client):
    made = _make(client)
    past = datetime.now(timezone.utc) - timedelta(days=2)
    response = client.put(f"/reminders/{made['id']}", json={"due_at": _iso(past)})
    assert response.status_code == 422
    assert "past" in response.json()["detail"]
    kept = client.get("/reminders").json()
    assert kept[0]["due_at"] == made["due_at"]


def test_the_undo_puts_back_the_exact_time_even_once_it_is_past(client):
    made = _make(client)
    client.put(f"/reminders/{made['id']}", json={"due_at": _iso(datetime.now(timezone.utc) + timedelta(days=5))})
    # The undo of a drag made on an overdue reminder sends a time already gone.
    gone = datetime.now(timezone.utc) - timedelta(hours=3)
    response = client.put(f"/reminders/{made['id']}", json={"due_at": _iso(gone), "restore": True})
    assert response.status_code == 200
    back = client.put(f"/reminders/{made['id']}", json={"due_at": made["due_at"], "restore": True}).json()
    assert back["due_at"] == made["due_at"]


def test_the_timeline_row_follows_the_move(client):
    made = _make(client)
    new = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(days=9)
    client.put(f"/reminders/{made['id']}", json={"due_at": _iso(new)})
    start = (new - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S")
    end = (new + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S")
    rows = client.get(f"/timeline?kind=reminder&start={start}&end={end}&limit=1000").json()["rows"]
    assert [row["id"] for row in rows] == [made["id"]]
    assert rows[0]["at"].startswith(new.strftime("%Y-%m-%dT%H:%M"))


def test_the_edit_forms_alert_is_set_and_cleared_through_the_same_put(client):
    """OPEN.md: the reminder edit form could not change an alert. The form's
    select sends `alert_minutes` (0 clears it); the reminder keeps the rest."""
    from pathlib import Path

    made = _make(client, alert_minutes=15)
    changed = client.put(f"/reminders/{made['id']}", json={"alert_minutes": 60})
    assert changed.status_code == 200 and changed.json()["alert_minutes"] == 60
    cleared = client.put(f"/reminders/{made['id']}", json={"alert_minutes": 0})
    assert cleared.json()["alert_minutes"] is None and cleared.json()["priority"] == "high"
    form = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "shell-reminders.js").read_text(encoding="utf-8")
    body = form[form.index("function reminderEditForm("):form.index("async function reminderPutUndoably(")]
    assert "alert_minutes: Number(alertSelect.value)" in body and "alert_minutes: alertNow" in body
    assert "recurringSelect, alertSelect]" in body and "wrap.append(textInput, fields, row)" in body
