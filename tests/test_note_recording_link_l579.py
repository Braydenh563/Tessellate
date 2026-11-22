"""A note can embed and link a recording by its name (L579).

`![[Sync call]]` in a note played nothing unless the documents bundle had
happened to load ("Nothing called ... yet", measured on :8798), and
`[[Sync call]]` offered to create a note. Both now ask the recorder's lazy
file, which knows the Library's recordings; the boot files only name it.
Search already finds a recording by its name and its words
(`tests/test_search_recordings.py`).
"""

from __future__ import annotations

import re
from pathlib import Path

from tests._app_js import frontend_text

ROOT = Path(__file__).resolve().parent.parent


def test_a_note_embed_that_names_nothing_else_asks_the_recorder_file():
    md = frontend_text("markdown.js")
    assert "(window.docEmbedFill || noteRecording)(body, name" in md


def test_an_unresolved_link_tries_a_recording_before_offering_a_note():
    editor = frontend_text("editor.js")
    offer = editor[editor.index("async function offerToCreateWikiTarget") :][:900]
    assert "await noteRecording(0, wanted)" in offer


def test_the_recorder_file_owns_it_and_the_stand_in_names_it():
    meetings = frontend_text("meetings.js")
    assert "async function noteRecording(host, name)" in meetings
    raw = (ROOT / "frontend/js/meetings.js").read_text()
    assert re.search(r"Object\.assign\(window, \{[^}]*\bnoteRecording,", raw)
    assert '"noteRecording"' in frontend_text("app.js")


def test_the_name_is_matched_the_way_the_library_shows_it():
    meetings = frontend_text("meetings.js")
    body = meetings[meetings.index("function noteRecordingByName") :][:700]
    assert "toLowerCase()" in body and "/recordings?q=" in body
