"""Two lazy-load faults found on 2026-11-01 (INBOX 1530): a board restored with its
Library side open drew tiles before whiteboard-templates.js ran (`wbThumbSvg is not
defined`), and a card file that loaded without defining `entryItem` made the notes
list ask for its own draw forever."""

import re
from pathlib import Path

JS = Path(__file__).resolve().parents[1] / "frontend" / "js"


def test_the_board_library_waits_for_its_bundle_before_drawing_tiles():
    lib = (JS / "whiteboard-library.js").read_text(encoding="utf-8")
    body = lib[lib.index("async function wbLoadLibrary"):].split("\n}\n")[0]
    assert body.index('await ensureModule("library");') < body.index("wbRenderLibrary();")


def test_a_card_file_without_its_name_is_a_failure_not_a_redraw():
    notes = (JS / "notes-list.js").read_text(encoding="utf-8")
    waiting = notes[notes.index("renderEntries.waiting ||="):][:600]
    assert "if (!ok || !window.entryItem)" in waiting
    phone = (JS / "phone-shell.js").read_text(encoding="utf-8")
    for call in ("openNotePage(entry, returnFocus)", "refreshNotePage(ids)"):
        assert f"ok && window.entryItem ? {call}" in phone
