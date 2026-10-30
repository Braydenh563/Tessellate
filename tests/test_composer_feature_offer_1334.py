"""INBOX 1334, the open half: a one- to three-word message naming an app
feature ("timer") when a note DOES mention the word answers with the note, and
one closing line offers the tool from the same Guide line `_feature_instead`
says when no note mentions it."""

from __future__ import annotations

import pytest

from tessellate.entry import manager
from tests.test_composer_route_688 import _ask

OFFER = "The app has a tool by that name too."


@pytest.fixture
def notes(session):
    manager.create_entry(session, "# Kitchen timer\n\nThe oven timer broke last week; buy a new one.")
    manager.create_entry(session, "# Maths revision\n\nThe calculator I borrowed needs batteries before the exam.")
    session.commit()


@pytest.mark.parametrize(("question", "note", "tool"), [
    ("timer", "oven timer broke", r"timer"),
    ("timer?", "oven timer broke", r"timer"),
    ("Timer", "oven timer broke", r"timer"),
    ("calculator", "calculator you borrowed", r"calculator"),
])
def test_a_feature_word_a_note_mentions_answers_with_the_note_and_offers_the_tool(client, notes, question, note, tool):
    text = _ask(client, question, use_tools=False)["text"]
    assert note in text
    assert OFFER in text
    assert text.index(note) < text.index(OFFER)
    assert text.lower().count(tool) >= 2


@pytest.mark.parametrize("question", ["oven timer", "kitchen timer", "what did I write about the oven timer"])
def test_a_phrase_that_is_not_the_feature_gets_no_offer(client, notes, question):
    text = _ask(client, question, use_tools=False)["text"]
    assert "oven timer broke" in text
    assert OFFER not in text


def test_a_feature_word_no_note_mentions_is_still_the_tool_alone(client, session):
    manager.create_entry(session, "# Dentist\n\nCheck-up booked for the 21st.")
    session.commit()
    text = _ask(client, "timer", use_tools=False)["text"]
    assert "one of the app's own tools" in text
    assert OFFER not in text
