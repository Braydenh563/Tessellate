"""Ctrl+S saves the edit form that is open (L-world-class-102).

Audit, driven 2026-11-14 at 1440 on Dashboard, Chat, Graph, Reminders, Timeline,
Notes and Boards: Ctrl+S is always taken (default prevented, so the browser's
save-page never opens) but in an open note edit form, with a change typed, it
answered "Nothing to save yet." and wrote nothing (the server kept the old
text). The two lazy forms now take the chord themselves, as Ctrl+Enter does,
and stop it before the global handler.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _text(name):
    return (ROOT / "frontend/js" / name).read_text(encoding="utf-8")


def test_the_note_edit_form_saves_on_ctrl_s_and_keeps_it_from_the_global_chord():
    src = _text("note-edit-panels.js")
    block = src[src.index("L-world-class-102"):][:500]
    assert '"s"' in block and "saveButton.click()" in block
    assert "stopPropagation" in block
    # capture phase, because the page's own handler is a bubbling one on document
    assert 'document.addEventListener("keydown", escapeFromBody, true)' in src


def test_the_reminder_edit_form_saves_on_ctrl_s_too():
    src = _text("reminder-edit.js")
    block = src[src.index('event.key.toLowerCase() === "s"'):][:500]
    assert "stopPropagation" in block and 'row.querySelector("button")' in block
    assert re.search(r"ctrlKey \|\| event\.metaKey", src)
