"""INBOX 1649: "I want to edit a note" is a request to do something in the app,
answered with the way to do it, never a retrieval of notes sharing its words."""

from __future__ import annotations

import pytest

from tessellate.ai import intent

FRAMES = [
    "I want to {}", "i need to {}", "I would like to {}", "I'd like to {}", "can I {}", "could i {}",
    "how do I {}", "how can I {}", "how would I {}", "help me {}", "is it possible to {}", "let me {}",
    "show me how to {}", "I wanna {}",
]
THINGS = [
    "edit a note", "make a mind map", "delete a note", "pin a note", "open a note", "change a note",
    "write a note", "move a note", "share a note", "export a note", "copy a note", "duplicate a note",
    "format a note", "lock a note", "hide a note", "archive a note", "sort my notes", "add a reminder",
    "create a tag", "use the whiteboard", "edit a document", "merge two notes", "restore a note",
]


@pytest.mark.parametrize("frame", FRAMES)
@pytest.mark.parametrize("thing", THINGS)
def test_a_request_for_the_app_is_the_guides(frame, thing):
    text = frame.format(thing)
    assert intent.classify(text) == intent.ABOUT_APP, text


@pytest.mark.parametrize(
    "text",
    [
        "I want to edit my pasta note", "open my pasta note", "delete the note about pasta",
        "I need to delete the note about pasta", "can I see my pasta note", "I want to read the note on pasta",
        "how do I find the note about pasta", "I would like to edit the note called pasta",
    ],
)
def test_a_specific_note_stays_with_the_notes(text):
    assert intent.classify(text) != intent.ABOUT_APP, text


def test_the_edit_answer_names_the_way_to_edit():
    from tessellate.ai import composer_help

    got = composer_help._help_answer("I want to edit a note")
    assert got, "no guide answer for edit"
    text = " ".join(str(p[1]) for p in got["parts"] if p[0] == "help").lower()
    assert "edit" in text or "open" in text, text


def test_a_quoted_line_never_ends_on_a_dangling_word():
    from tessellate.ai import composer_digest as d

    cut = "Open the hub-finish-ui page and check the header, the dock and the footer all render and"
    assert d.whole_clause(cut) == "Open the hub-finish-ui page and check the header, the dock and the footer all render"
    assert d.whole_clause("Check the hub-finish-ui and") == "Check the hub-finish-ui"
    assert d.whole_clause("Fix it and") == ""
    assert d.whole_clause("Press Edit, then Save.") == "Press Edit, then Save."
    assert d.whole_clause("Row More button. Expect: menu with Use, Copy, Edit") == "Row More button. Expect: menu with Use, Copy, Edit"


def test_only_note_is_said_for_a_topic_never_for_a_request():
    from tessellate.ai import composer_digest as d

    assert d.asks_for_a_topic("what do I know about pasta")
    assert d.asks_for_a_topic("pasta")
    for q in ("I want to edit my pasta note", "can I open the pasta note", "help me edit the pasta note"):
        assert not d.asks_for_a_topic(q), q


def test_a_request_answer_has_no_only_note_claim():
    from tessellate.ai import composer, composer_digest

    notes = [{"id": 1, "title": "pasta", "content": "# pasta\n\nBoil the pasta for ten minutes with salt.", "tags": [],
              "category": "Food", "created_at": "2026-10-02T10:00:00"}]
    text = composer.compose("I want to edit my pasta note", notes)["text"]
    assert not any(composer_digest.is_only_claim(line) for line in text.splitlines()), text
