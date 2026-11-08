"""INBOX 1570: "Pin a note" -> "Which note do you want pinned?" -> "erm, the interesting bean
one" was not understood. (a) the reply fills the act's slot before any routing, (b) a reference
like "the X one" with filler words resolves to a note by title, (c) an exact title proceeds
with the act and its Undo."""

from __future__ import annotations

import json
from datetime import date

import pytest

from tessellate.ai import composer_suggest
from tessellate.core import clock
from tessellate.entry import manager

NOTES = ["# Interesting bean\n\nAn interesting bean from the market.", "# Conversation starters\n\nAsk something interesting.", "# Lisbon trip\n\nFlights."]

REPLIES = [
    "erm, the interesting bean one", "um interesting bean", "uh, that interesting bean one", "like the interesting bean note",
    "so the one about the interesting bean", "Interesting bean", "the Interesting bean one please", "hmm the one called interesting bean",
]


def _run(client, body):
    events = []
    with client.stream("POST", "/chat/stream", json=body) as response:
        for line in response.iter_lines():
            if line.strip():
                events.append(json.loads(line))
    return events


def _said(events):
    return "".join(e.get("delta", "") for e in events if e["type"] == "answer")


@pytest.fixture
def notebook(client, session, monkeypatch):
    #: A fixed day: the reply seed reads it (`chat_said._reply_seed`), so the confirmation's phrasing moved with the real date.
    monkeypatch.setattr(clock, "today", lambda: date(2026, 11, 7))
    for content in NOTES:
        manager.create_entry(session, content)
    session.commit()

    def converse(first: str, reply: str):
        asked = _said(_run(client, {"question": first, "answer_from": "notes", "use_tools": False}))
        events = _run(client, {"question": reply, "answer_from": "notes", "use_tools": False, "history": [{"question": first, "answer": asked}]})
        return asked, events

    return converse


# (b) A reference to a note, with or without filler.

@pytest.mark.parametrize("reply", REPLIES)
def test_a_reference_names_the_note(reply):
    assert composer_suggest.reference(reply).lower().replace("the ", "") == "interesting bean", composer_suggest.reference(reply)


@pytest.mark.parametrize("reply", ["erm", "um, that one", "it", "the one", "uh, this note", "so"])
def test_filler_and_pointers_name_nothing(reply):
    assert composer_suggest.reference(reply) == ""


# (a) and (c) The reply to "which note?" runs the act, with its Undo, for every act that asks.

@pytest.mark.parametrize("reply", REPLIES)
def test_the_reply_to_pin_a_note_pins_it_with_undo(notebook, reply):
    asked, events = notebook("Pin a note", reply)
    assert "Which note" in asked
    said = _said(events)
    assert "Interesting bean" in said and "did not catch" not in said, said
    assert said.startswith("Done") and any(e["type"] == "act" for e in events), (said, [e["type"] for e in events])


@pytest.mark.parametrize("first, done", [
    ("Pin a note", "Added to Favourites"), ("Unpin a note", "Removed from Favourites"),
])
@pytest.mark.parametrize("reply", REPLIES[:4])
def test_every_pin_act_fills_its_slot(notebook, first, done, reply):
    _asked, events = notebook(first, reply)
    #: Any case: the confirmation's phrasing (`act_done`) is picked per reply, and
    #: "Done: {what}." or "I have {what}." carries the label lower-cased.
    assert done.lower() in _said(events).lower(), _said(events)


@pytest.mark.parametrize("reply", REPLIES[:4])
def test_a_delete_asks_to_confirm_the_note_it_was_given(notebook, reply):
    _asked, events = notebook("Delete a note", reply)
    said = _said(events)
    assert "Interesting bean" in said and "bin" in said, said


@pytest.mark.parametrize("first", ["Open a note", "Find a note", "Summarise a note"])
@pytest.mark.parametrize("reply", REPLIES[:4])
def test_open_find_and_summarise_take_the_named_note(notebook, first, reply):
    _asked, events = notebook(first, reply)
    said = _said(events)
    assert "Interesting bean" in said and "did not catch" not in said, said
    assert "Lisbon" not in said and "Conversation starters" not in said, said


def test_a_reply_that_is_its_own_request_is_routed_as_one(notebook):
    _asked, events = notebook("Pin a note", "pin the lisbon trip note")
    assert "Lisbon trip" in _said(events), _said(events)


def test_a_new_question_after_the_clarifying_one_is_not_a_title(notebook):
    _asked, events = notebook("Pin a note", "what did I write about lisbon?")
    assert "Favourites" not in _said(events), _said(events)
