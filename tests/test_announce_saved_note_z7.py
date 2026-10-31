"""audit-1031 Z7: every "saved to your notebook" toast has an Open action.

The sketch pad closed, toasted "Sketch saved to your notebook." and left focus
on `body` with nothing that led to the note. `announceSavedNote`
(quick-note.js) is the one announcement for a note that reached the server: the
toast with its way to the note, the list refreshed, the Undo entry, and focus
back where the person was.
"""

from __future__ import annotations

import re
from pathlib import Path

JS = Path(__file__).resolve().parents[1] / "frontend" / "js"


def _src(name: str) -> str:
    return (JS / name).read_text(encoding="utf-8")


def _body(source: str, name: str) -> str:
    start = source.index(f"function {name}(")
    nxt = re.search(r"\n(?:async )?function \w+\(", source[start + 10 :])
    return source[start : start + 10 + nxt.start()] if nxt else source[start:]


def test_one_announcement_with_an_open_action_and_the_openers_focus():
    quick = _src("quick-note.js")
    assert quick.count("function announceSavedNote(") == 1
    body = _body(quick, "announceSavedNote")
    assert '"Open"' in body and "flashEntry(saved.id)" in body
    assert "pushEntryCreateUndo(" in body
    assert "focusOpener(" in body
    assert "function focusOpener(" in quick


def test_the_save_as_note_paths_use_it_instead_of_a_bare_toast():
    sketch = _body(_src("media.js"), "saveSketch")
    assert "announceSavedNote(entry" in sketch
    assert "Sketch saved to your notebook" in sketch
    assert "toast(" not in sketch
    assert "announceSavedNote(made" in _body(_src("web-clip.js"), "saveWebPageAsNote")
    assert "announceSavedNote(created" in _src("library.js")


def test_the_opener_is_kept_from_the_moment_the_sketch_opened():
    media = _src("media.js")
    assert "sketchOpener" in _body(media, "openSketch")
    assert "sketchOpener" in _body(media, "saveSketch")
