"""INBOX 1653: a how-to about doing something to a thing leads with the
sentence whose subject is that thing ("A deleted note ... goes to the bin"),
not a list of exceptions that shares the verb ("Four things have no Undo")."""

from __future__ import annotations

import pytest

from tessellate.ai import composer_help, help_chat, intent

BIN = ("undo-bin", "A deleted note, board, document")
FRAMES = ["how do I {}", "I need to {}", "can I {}"]


def _pick(ask: str) -> tuple[str, str]:
    core = intent.request_core(ask)
    #: The generated "Say it in Chat" topics lead by design once the reader is
    #: loaded (other tests load it); this is the Guide's own topics.
    topics = [t for t in help_chat.topics_for(core) if not str(t["id"]).startswith("act-")]
    found = composer_help.help_line(core, topics)
    assert found is not None, ask
    return found[1], found[0]


@pytest.mark.parametrize("frame", FRAMES)
@pytest.mark.parametrize("thing", ["delete a note", "remove a note", "restore a deleted note", "undo a delete"])
def test_deleting_leads_with_the_bin_sentence(frame, thing):
    topic, line = _pick(frame.format(thing))
    assert topic == BIN[0], thing
    assert line.startswith(BIN[1]), (thing, line)


@pytest.mark.parametrize("ask", ["why is there no undo for delete for good", "which things have no undo"])
def test_an_ask_about_the_exception_still_gets_it(ask):
    assert _pick(ask)[1].startswith("Four things have no Undo")


@pytest.mark.parametrize(
    ("ask", "topic", "start"),
    [
        ("pin a note", "favourites", "Starring (pinning)"),
        ("export my notes", "import-export", "Export your data"),
        ("share a note", "share-note", "Three ways"),
        ("lock the app", "security", "The lock button"),
        ("hide a note", "archive", "Archiving keeps"),
        ("archive a note", "archive", "Archiving keeps"),
        ("tag a note", "tags-categories", "Atlas files each note"),
        ("link two notes", "links", "Link one note to another"),
        ("search my notes", "search", "Find anything"),
        ("import notes", "import-export", "Import markdown files"),
        ("back up my notes", "import-export", "Backups:"),
    ],
)
@pytest.mark.parametrize("frame", FRAMES)
def test_the_right_picks_stay_right(frame, ask, topic, start):
    got_topic, line = _pick(frame.format(ask))
    assert got_topic == topic, ask
    assert line.startswith(start), (ask, line)
