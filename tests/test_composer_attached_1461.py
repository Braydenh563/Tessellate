"""INBOX 1461 (was 1455; the owner, Chat, no model): a note attached to the message and
"when did I make this note?" got the note quoted, then "Oldest first:" with two
unrelated notes and a stray "[Current Commitments]". A question about the
attached note answers about that note alone; "this note", "this" and "it"
with an attachment mean the attachment.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from tessellate.entry import manager
from tests.test_composer_route_688 import _ask

BUS = (
    "I just missed the bus to uni today, but I ran into a uni friend at the stop and we got coffee "
    "instead. Turned out to be a good morning after all."
)


def _seed(session) -> int:
    bus = manager.create_entry(session, BUS)
    bus.created_at = datetime(2026, 10, 8, 8, 30)
    bus.edited_at = datetime(2026, 10, 9, 18, 0)
    manager.create_entry(session, "# Girl with bell\n\nA painting of a girl with a bell, seen at the gallery.")
    manager.create_entry(session, "# Current Commitments\n\n- Gym on Mondays\n- Uni project due 12 November")
    session.commit()
    return bus.id


def _clean(text: str) -> None:
    assert "Oldest first" not in text and "Girl with bell" not in text and "Current Commitments" not in text, text
    assert "[" not in text and "]" not in text, text


@pytest.mark.parametrize(
    "question",
    ["when did I make this note?", "when did I write this", "when was this written?", "when did I create it?", "when was this note made"],
)
def test_when_made_answers_the_attachment_alone(client, session, question):
    bus = _seed(session)
    out = _ask(client, question, use_tools=False, note_ids=[bus])
    _clean(out["text"])
    assert "8 October" in out["text"], out["text"]


@pytest.mark.parametrize("question", ["when did I last edit this?", "when was this note changed", "when did I update it"])
def test_when_edited_answers_the_attachment_alone(client, session, question):
    bus = _seed(session)
    out = _ask(client, question, use_tools=False, note_ids=[bus])
    _clean(out["text"])
    assert "9 October" in out["text"], out["text"]


@pytest.mark.parametrize("question", ["how long is this note?", "how many words is this", "how long is it"])
def test_how_long_answers_the_attachment_alone(client, session, question):
    bus = _seed(session)
    out = _ask(client, question, use_tools=False, note_ids=[bus])
    _clean(out["text"])
    assert "words" in out["text"], out["text"]


@pytest.mark.parametrize("question", ["what is this note about?", "summarise this", "what's it about"])
def test_what_about_answers_the_attachment_alone(client, session, question):
    bus = _seed(session)
    out = _ask(client, question, use_tools=False, note_ids=[bus])
    _clean(out["text"])
    assert "bus" in out["text"].lower(), out["text"]


def test_this_note_with_nothing_attached_is_asked_about(client, session):
    _seed(session)
    out = _ask(client, "when did I make this note?", use_tools=False)
    assert "Which note do you mean" in out["text"] and "notes:" not in out["text"], out["text"]


def test_a_question_about_a_subject_is_not_taken(client, session):
    bus = _seed(session)
    from tessellate.ai import composer_this

    for question in ("when is the dentist", "when did I write about uni", "how long is the gym session", "what did I write last week"):
        assert composer_this.kind(question) == "", question
    out = _ask(client, "when did I last edit this?", use_tools=False, note_ids=[bus, bus + 1])
    assert "You last changed" not in out["text"]
