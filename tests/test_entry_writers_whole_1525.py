"""Every writer of a note's text reads the whole note first (INBOX 1525).

The Notes list asks for `preview=300`, so a row in `allEntries` can hold only
a note's first 300 characters (`content_truncated`). A PUT of that text would
cut the note. A file that sends a note's text to `PUT /entries/{id}` must say
which way it gets the whole text: `fullEntry(id)` (fills the row in place) or a
`GET /entries/{id}` of its own. A new writer fails here until it is listed.
"""

from __future__ import annotations

import re

from pathlib import Path

#: Sends the text of a note it holds as a row; the row is made whole by `fullEntry` first.
FULL_ENTRY = {
    "entry-card.js", "lightbox-actions.js", "note-history.js", "note-properties.js",
    "documents.js", "selection.js", "settings-controls.js", "whiteboard.js", "note-edit-panels.js", "writing-desk.js",
}
#: Reads the note by id (`GET /entries/{id}`) in the same function, so it never holds a clipped row.
BY_ID = {"graph.js", "image-layout.js", "meetings.js", "timeline-calendar.js"}

PUT = re.compile(r"`/entries/\$\{[^}]+\}`,\s*\{\s*method:\s*\"PUT\"(.{0,240}?)\}\)", re.S)
GET = re.compile(r"apiJson\(`/entries/\$\{[^}]+\}(?:\?[^`]*)?`(?:,\s*\{[^}]*\})?\)")


def _files():
    root = Path(__file__).resolve().parent.parent / "frontend" / "js"
    return {path.name: path.read_text(encoding="utf-8") for path in root.glob("*.js")}


def test_every_file_that_puts_a_notes_text_is_listed():
    writers = {name for name, text in _files().items() if any("content" in m.group(1) for m in PUT.finditer(text))}
    unlisted = writers - FULL_ENTRY - BY_ID
    assert not unlisted, f"{sorted(unlisted)} PUT a note's text: read the whole note first (`fullEntry`) and list the file"


def test_the_listed_files_really_read_the_whole_note():
    files = _files()
    for name in sorted(FULL_ENTRY):
        assert "fullEntry(" in files[name], f"{name} is listed as reading through fullEntry but never calls it"
    for name in sorted(BY_ID):
        assert GET.search(files[name]), f"{name} is listed as reading the note by id but has no GET /entries/{{id}}"


def test_the_list_asks_for_the_preview_and_the_screens_read_the_flag_and_the_server_numbers():
    files = _files()
    assert files["notes-list.js"].count("preview=300") >= 2  # the page read and the by-id refresh
    assert "preview=300" in files["notes-lazy.js"]  # the Semantic list
    #: The clamp: a clipped row is long whatever its 300 characters look like.
    assert "entry.content_truncated" in files["entry-card.js"]
    #: The dashboard counts words and open tasks on the server, over the whole text.
    dash = files["dashboard.js"]
    assert "entry.word_count ??" in dash and "entry.tasks_open ??" in dash and "entry.tasks_done ??" in dash
