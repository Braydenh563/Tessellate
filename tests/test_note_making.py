"""Making a note: every way in, measured (INBOX 434).

* Ctrl+Shift+N, the dashboard's actions and the empty states focused the
  capture box without showing Capture: with Notes last on Browse the focus
  fell to <body> and the next keys went nowhere (measured in Chromium).
"""

from __future__ import annotations

import re

from tests._app_js import app_js_text


def test_every_new_note_entry_point_goes_through_one_function():
    code = app_js_text()
    start = code[code.index("function startNewNote("):]
    start = start[: start.index("\n}\n")]
    assert 'showNotesSection("capture")' in start
    assert "mountNoteSurfaceNow(box)" in start
    assert ".catch(() => {})" in start, "a failed editor bundle fetch must not be an unhandled rejection"
    #: The Notes tab's own New makes a note whatever the writing style (L-documents-48).
    assert '$("notes-new-note").addEventListener("click", () => startNewNote(1));' in code
    assert "newNote: () => startNewNote()," in code
    # Nothing else focuses the capture box directly: it is hidden whenever
    # Capture is not the section showing.
    direct = re.findall(r'\$\("entry-content"\)\??\.focus\(\)', code)
    assert not direct, direct
