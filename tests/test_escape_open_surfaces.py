"""Escape on the surfaces the 2026-10-18 audit listed as open (L-world-class-94).

Driven in the app (2026-11-14): the image lightbox, the graph node popup and
the reminders add form closed or cleared on Escape; the note edit form closed
only while the caret was inside it, and did nothing once focus had fallen to
<body> (a click on the blank page, a closed popover). These checks keep the
three listeners that make each of them close.
"""

import re
from pathlib import Path

JS = Path(__file__).resolve().parents[1] / "frontend" / "js"


def _src(name):
    return (JS / name).read_text(encoding="utf-8")


def test_the_note_edit_form_takes_escape_when_focus_is_on_the_page():
    text = _src("note-edit-panels.js")
    assert "const escapeFromBody = (event) =>" in text
    block = text[text.index("const escapeFromBody"):]
    block = block[:block.index("renderEditForm.bodyKeys = escapeFromBody")]
    # only a key with no caret anywhere, and never over an open dialog
    assert "event.target === document.body" in block
    assert "dialog[open]" in block and ".modal-overlay:not(.hidden)" in block
    # and it lets go of the listener once the form is gone
    #: Letting go is unpointing the one page listener (test_perf_1031), not removing a per-render one.
    assert "!li.isConnected" in block and "renderEditForm.bodyKeys = null" in block


def test_the_body_fallback_does_not_see_the_hidden_lock_card():
    # The lock card is role=dialog and lives under a hidden overlay all session:
    # a `[role=dialog]` test saw it as an open dialog and the key never closed
    # the form (measured 2026-11-14).
    assert "[role=dialog]" not in _src("note-edit-panels.js")


def test_the_lightbox_closes_on_escape_in_capture():
    text = _src("lightbox-view.js")
    assert 'document.addEventListener("keydown", onKey, true)' in text
    assert re.search(r'if \(e\.key === "Escape"\) \{[^}]*close\(\)', text, re.S)


def test_the_graph_popup_closes_on_escape_from_the_page_handler():
    text = _src("settings-wiring.js")
    assert re.search(r'"Escape" && document\.getElementById\("graph-popup"\)[^\n]*\n\s*closeGraphPopup\(true\)', text)
