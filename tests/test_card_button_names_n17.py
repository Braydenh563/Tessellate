"""Audit 1029 N17: a note card's icon buttons carry the note's name.

A screen-reader list of buttons read "Edit this entry" once per card, so the
cards could not be told apart. The actions row (entry-card.js) appends the
note's plain name to each icon button's accessible name; the `title` stays as
it was, because notes-list.js finds the Edit button by it.
"""

from __future__ import annotations

from tests._app_js import app_js_text

JS = app_js_text()


def test_card_actions_are_named_after_their_note():
    at = JS.index("Wave L rework: two everyday actions stay visible")
    row = JS[at : at + 4000]
    assert "const cardName = " in row
    assert "noteNamePlain(entry.content" in row
    assert 'setAttribute("aria-label", `${verb}: ${cardName}`)' in row


def test_the_edit_button_keeps_its_title():
    assert 'smallButton("ph:pencil-simple", "Edit this entry"' in JS
    assert "[title='Edit this entry']" in JS
