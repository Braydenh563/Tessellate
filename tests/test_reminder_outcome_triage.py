"""Reminder outcome (L-general-10) and overdue triage (L-general-12).

The append is client side (`reminderOutcomePrompt`, reminder-triage.js): it reads the source note,
writes `content + blank line + "Outcome (day): line"` with the note's own `PUT /entries/{id}`, and
Undo writes the old text back. The route test below drives exactly those two calls against the real
app, so the outcome reaching the note's text is held at the route; the source pins hold that the
client makes those calls, asks only for a reminder with a note, and treats an empty answer as nothing.
The running app was driven too (the numbers are in the commit message and CHANGELOG)."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from tests._clock import SUITE_NOW, pin_clock

JS = Path(__file__).resolve().parents[1] / "frontend" / "js"
TRIAGE = (JS / "reminder-triage.js").read_text(encoding="utf-8")
REMINDERS = (JS / "shell-reminders.js").read_text(encoding="utf-8")


def test_the_outcome_reaches_the_source_note_and_undo_puts_it_back(client, monkeypatch) -> None:
    pin_clock(monkeypatch, SUITE_NOW)
    note = client.post("/entries", json={"content": "Plan the launch with Sam"}).json()
    due = (SUITE_NOW + timedelta(hours=1)).isoformat()
    reminder = client.post("/reminders", json={"text": "Call Sam", "due_at": due, "entry_id": note["id"]}).json()
    assert reminder.get("id")
    done = client.put(f"/reminders/{reminder['id']}", json={"done": True}).json()
    assert done["done"] is True

    before = client.get(f"/entries/{note['id']}").json()["content"]
    line = "Outcome (21 Nov 2026): Agreed to ship on Friday"
    saved = client.put(f"/entries/{note['id']}", json={"content": f"{before.rstrip()}\n\n{line}"})
    assert saved.status_code == 200
    appended = client.get(f"/entries/{note['id']}").json()["content"]
    assert appended.endswith(line)

    client.put(f"/entries/{note['id']}", json={"content": before})  # Undo
    restored = client.get(f"/entries/{note['id']}").json()["content"]
    assert restored == "Plan the launch with Sam"


def test_the_client_asks_only_for_a_reminder_with_a_note_and_empty_does_nothing() -> None:
    assert "if (!reminder?.entry_id) return false;" in TRIAGE
    assert 'cancelLabel: "Skip"' in TRIAGE
    assert "if (!line) return false;" in TRIAGE  # Skip, Escape or Enter on nothing
    assert '`/entries/${id}`, { method: "PUT", body: JSON.stringify({ content })' in TRIAGE
    assert "pushUndo(\"Added an outcome to a note\"" in TRIAGE
    #: both completion paths ask: a plain tick and a repeating reminder rolling on
    assert REMINDERS.count('reminder.entry_id && loadReminders.act("outcome", reminder);') == 2


def test_overdue_has_a_triage_with_keep_drop_move_and_bulk() -> None:
    assert 'if (label === "Overdue")' in REMINDERS and 'loadReminders.act("triage", items)' in REMINDERS
    for word in ("Still matters", '"Drop"', '"Reschedule"', "Reschedule all", "Drop all"):
        assert word in TRIAGE, word
    #: drop is the bin (restorable), never a purge; a move keeps the due time inside the future
    assert 'method: "DELETE"' in TRIAGE and "/restore" in TRIAGE and "purge" not in TRIAGE
    assert "triageDueFor" in TRIAGE


def test_the_triage_review_of_pr_222_holds() -> None:
    """Review of PR 222: a part-failed bulk act keeps an Undo for the rows done;
    a cleared date field cannot move anything; focus and the count survive a
    repaint; Undo of an outcome takes off only its line, so later edits stay."""
    assert "done = todo.filter((r) => r.gone);" in TRIAGE and "if (done.length) undoFor(done, when, back, apply);" in TRIAGE
    assert 'if (kind === "move" && !value) return;' in TRIAGE and "move.disabled = !dateInput.value;" in TRIAGE
    assert "bulk[0].disabled = !todo.length || !dateInput.value;" in TRIAGE
    assert 'note.setAttribute("role", "status");' in TRIAGE and '(row?.querySelector("button:not(:disabled)") || note).focus();' in TRIAGE
    assert "if (!now.endsWith(added)) throw" in TRIAGE and 'pushUndo("Added an outcome to a note", takeOff, putBack)' in TRIAGE
    assert "put(before.content)" not in TRIAGE
