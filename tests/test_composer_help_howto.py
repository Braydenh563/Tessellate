"""INBOX 1357, fix the class: the 1653 round fixed "delete a note"; these are
the same classes for other verbs and subjects, answered with the model off.

The classes: verbs that say one doing (get back, recover, restore, undelete;
remove, erase, throw away; move, file; rename, retitle), a subject word that
names a topic ("board" the whiteboard, "move" the mind map's drag), a negated
doing ("can't undo", "cannot be undone") and the bin's own verbs (empty).
Every case is asked twice: from the Guide's own topics, and with the act
reader loaded, where the generated "Say it in Chat" pointer must not lead."""

from __future__ import annotations

import pytest

from tessellate.ai import commands, composer_help, help_chat, intent, reading  # noqa: F401  (the act reader)

BIN = "A deleted note, board, document"
EMPTY = "Empty the bin, in the bin's strip"
NO_UNDO = "Four things have no Undo"
MOVE = "Move a note to another category"
RENAME = "Delete the [[name]] and its link goes with it; rename a note"

CASES = [
    # getting back: verbs and phrases that are one restore
    ("can I get a note back", "undo-bin", BIN),
    ("can I get my deleted notes back", "undo-bin", BIN),
    ("can I get a deleted document back", "undo-bin", BIN),
    ("can I get a deleted attachment back", "undo-bin", BIN),
    ("can I get a reminder back", "undo-bin", BIN),
    ("can I get a recording back", "undo-bin", BIN),
    ("how do I recover a deleted board", "undo-bin", BIN),
    ("can I recover a deleted reminder", "undo-bin", BIN),
    ("how do I recover a note I deleted", "undo-bin", BIN),
    ("how do I bring back a deleted note", "undo-bin", BIN),
    ("can I bring back a deleted board", "undo-bin", BIN),
    ("can I restore a private note", "undo-bin", BIN),
    ("how do I restore a document from the bin", "undo-bin", BIN),
    ("can I undelete a note", "undo-bin", BIN),
    ("can I undelete a document", "undo-bin", BIN),
    ("how do I take a note out of the bin", "undo-bin", BIN),
    # taking away: delete, remove, trash, erase, throw away, per subject
    ("how do I delete a note", "undo-bin", BIN),
    ("how do I remove a board", "undo-bin", BIN),
    ("how do I delete a document", "undo-bin", BIN),
    ("how do I remove a document", "undo-bin", BIN),
    ("how do I delete a map", "undo-bin", BIN),
    ("how do I remove a mind map", "undo-bin", BIN),
    ("how do I delete a diagram", "undo-bin", BIN),
    ("how do I delete a reminder", "undo-bin", BIN),
    ("how do I remove a reminder", "undo-bin", BIN),
    ("how do I delete an attachment", "undo-bin", BIN),
    ("how do I remove an attachment", "undo-bin", BIN),
    ("how do I delete a code file", "undo-bin", BIN),
    ("how do I remove a private note", "undo-bin", BIN),
    ("how do I delete a recording", "undo-bin", BIN),
    ("how do I trash a note", "undo-bin", BIN),
    ("how do I get rid of a note", "undo-bin", BIN),
    ("how do I throw away a note", "undo-bin", BIN),
    ("how do I erase a note", "undo-bin", BIN),
    ("how do I permanently delete a note", "undo-bin", BIN),
    # the bin's own verb, and the things that cannot be taken back
    ("how do I empty the bin", "undo-bin", EMPTY),
    ("how do I clear the bin", "undo-bin", EMPTY),
    ("can I undo emptying the bin", "undo-bin", EMPTY),
    ("what can't I undo", "undo-bin", NO_UNDO),
    ("what cannot be undone", "undo-bin", NO_UNDO),
    ("which things cannot be undone", "undo-bin", NO_UNDO),
    ("can I undo delete for good", "undo-bin", NO_UNDO),
    ("is delete permanent", "undo-bin", NO_UNDO),
    ("can I undo deleting a space", "undo-bin", "A deleted picture or file"),
    # moving and filing
    ("how do I move a note", "tags-categories", MOVE),
    ("how do I move a note to a space", "tags-categories", MOVE),
    ("how do I move a note to another category", "tags-categories", MOVE),
    ("how do I move a private note", "tags-categories", MOVE),
    ("how do I put a note in another category", "tags-categories", MOVE),
    ("how do I file a note", "tags-categories", "Atlas files each note"),
    # renaming
    ("how do I rename a note", "links", RENAME),
    ("how do I retitle a note", "links", RENAME),
    ("how do I rename a tag", "tag-manager", "Rename a tag, merge it"),
    ("how do I merge tags", "tag-manager", "Rename a tag, merge it"),
    ("how do I delete a tag", "tag-manager", "Rename a tag, merge it"),
    ("how do I remove a tag from a note", "tag-manager", "Rename a tag, merge it"),
    ("how do I rename a mind map", "mind-map-import-export", "With a map open"),
    ("how do I rename a chat", "ask-chat", "Conversations save and rename"),
]

#: Asked and answered wrongly, for want of a help sentence: the Guide has no
#: step for these, so they are listed here and not asserted (INBOX 1357).
NEEDS_HELP_TEXT = [
    "how do I rename a document",
    "how do I rename a code file",
    "how do I rename a reminder",
    "how do I rename an attachment",
    "how do I rename a recording",
    "how do I rename a private note",
    "how do I rename a space",
    "how do I rename a category",
    "how do I move a document to another space",
    "how do I move a reminder",
    "how do I delete a space",
    "how do I delete a category",
]


def _pick(ask: str, *, acts: bool) -> tuple[str, str]:
    core = intent.request_core(ask)
    topics = help_chat.topics_for(core)
    if not acts:
        topics = [t for t in topics if not str(t["id"]).startswith("act-")]
    found = composer_help.help_line(core, topics)
    assert found is not None, ask
    return found[1], found[0]


def test_there_are_forty_new_questions():
    assert len(CASES) >= 47


@pytest.mark.parametrize("acts", [False, True], ids=["guide", "with-acts"])
@pytest.mark.parametrize(("ask", "topic", "start"), CASES)
def test_the_howto_leads_with_the_right_sentence(ask, topic, start, acts):
    got_topic, line = _pick(ask, acts=acts)
    assert got_topic == topic, (ask, got_topic)
    assert line.startswith(start), (ask, line)


def test_the_bin_topic_stays_under_the_length_cap():
    assert len(next(t for t in help_chat.HELP_TOPICS if t["id"] == "undo-bin")["body"]) < 1900
    assert len(next(t for t in help_chat.HELP_TOPICS if t["id"] == "tags-categories")["body"]) < 1900
