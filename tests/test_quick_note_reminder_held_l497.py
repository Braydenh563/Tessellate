"""L497: a quick note held in the outbox (server gone) keeps its reminder
chip: the reminder is held with the note, never sent as part of it, and set
when the outbox delivers the note and it has an id."""

from __future__ import annotations

from pathlib import Path

from tests._js_scope import unwrapped

JS = Path(__file__).resolve().parents[1] / "frontend" / "js" / "quick-note.js"


def _quick_note() -> str:
    return unwrapped(JS.read_text(encoding="utf-8"))


def test_the_reminder_is_held_with_the_note_not_dropped():
    js = _quick_note()
    assert "Its reminder was not set" not in js
    assert "held_reminder: heldReminder } : payload" in js
    assert "{ heldReminder });" in js


def test_the_flush_strips_it_from_the_note_and_sets_it_after_the_save():
    js = _quick_note()
    flush = js[js.index("function flushNoteOutbox()") :]
    flush = flush[: flush.index("function returnNoteToCapture")]
    assert "held_reminder: heldReminder, ...payload } = item;" in flush
    after = flush[flush.index('apiJson("/entries", { method: "POST"') :]
    assert after.index("quickNoteReminder(saved.id") > 0
