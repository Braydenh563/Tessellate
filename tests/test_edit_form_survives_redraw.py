"""An open edit form is carried through a list redraw, never rebuilt.

A redraw (filing event, change poll, late refresh) used to build the form
again: a bare textarea whose editor mounts only on a focus nobody gave it.
The E2E spec notes.spec.js "the edit form saves a new title, body and tag"
failed under load because of it.
"""

from __future__ import annotations

from _app_js import app_js_text


def test_entry_item_hands_back_the_open_edit_row():
    js = app_js_text()
    start = js.index("function entryItem(")
    body = js[start : start + 1500]
    assert "return entryItem.live" in body
    # A fresh open (a focus request pending) still builds the form.
    assert "focusBodyAfterRender !== entry.id" in body
    assert "focusTagsAfterRender !== entry.id" in body
    # A closed form is forgotten, so a later open builds a new one.
    assert "if (editingId !== entry.id) entryItem.live = null" in body
    assert "entryItem.live = li;" in js
