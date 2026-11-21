"""L-general-10 and L-general-12: completing a reminder asks for a one-line
outcome that goes onto its note, and the Overdue group has a triage view."""

from __future__ import annotations

from pathlib import Path

FRONT = Path(__file__).resolve().parents[1] / "frontend" / "js"
SHELL = (FRONT / "shell-reminders.js").read_text(encoding="utf-8")
EDIT = (FRONT / "reminder-edit.js").read_text(encoding="utf-8")


def test_ticking_a_reminder_asks_for_an_outcome_lazily():
    row = SHELL[SHELL.index("function reminderItem(") : SHELL.index("function reminderTarget(")]
    assert row.count("snoozeReminderTo.askOutcome(reminder)") == 2  # plain and repeating
    assert "askOutcome: askReminderOutcome" in EDIT and "triage: openOverdueTriage" in EDIT


def test_the_outcome_is_optional_and_goes_through_the_entry_update_route():
    body = EDIT[EDIT.index("async function askReminderOutcome") : EDIT.index("function openOverdueTriage")]
    assert "promptDialog(" in body
    assert "if (!line) return;" in body  # Cancel and an empty line skip
    assert "`/entries/${reminder.entry_id}`" in body and 'method: "PUT"' in body
    assert "base_hash" in body and "pushUndo(" in body  # one Undo, and a retry on failure
    assert '"Try again"' in body
    assert "!\"" not in body and "!`" not in body  # no exclamation marks in copy


def test_a_note_gets_the_outcome_appended_with_its_hash(client):
    note = client.post("/entries", json={"content": "Plan the trip"}).json()
    got = client.get(f"/entries/{note['id']}").json()
    appended = got["content"] + "\n\nOutcome (2026-11-21): booked"
    put = client.put(f"/entries/{note['id']}", json={"content": appended, "base_hash": got["content_hash"]})
    assert put.status_code == 200
    assert put.json()["content"].endswith("Outcome (2026-11-21): booked")
    stale = client.put(f"/entries/{note['id']}", json={"content": "x", "base_hash": got["content_hash"]})
    assert stale.status_code in (409, 412)


def test_the_overdue_group_has_a_triage_view_with_a_bulk_action():
    loop = SHELL[SHELL.index('for (const label of ["Overdue"') :]
    assert 'label === "Overdue"' in loop and "snoozeReminderTo.triage(items)" in loop
    body = EDIT[EDIT.index("function openOverdueTriage") : EDIT.index("async function snoozeReminderTo")]
    for word in ("Still matters", "Drop", "Reschedule", "Apply to all", "openSheet("):
        assert word in body
    assert "pushUndo(" in body  # one undo for the lot
    assert 'presetDate("tomorrow")' in body


def test_help_names_both():
    from tests._help_text import help_core_text

    text = help_core_text()
    assert "outcome" in text and "triage" in text.lower()
