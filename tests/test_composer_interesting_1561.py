"""INBOX 1561: "anything interesting you can do??" with no model. A question about
the assistant is answered about the assistant; an adjective is never the subject of
a search; the count agrees with the sources; a quote is a whole sentence."""

from __future__ import annotations

import json

import pytest

from tessellate.entry import manager

NOTES = [
    "# Follow- Up Questions:\n\nAfter making an initial connection.\n\n- Ask something interesting about their week.\n- Keep it light.\n",
    "# Interesting bean\n\nAn interesting bean from the market, roasted dark.",
    "# Lisbon trip\n\nFlights booked for May, hotel near the river.",
]


@pytest.fixture
def ask(client, session):
    for content in NOTES:
        manager.create_entry(session, content)
    session.commit()

    def go(question: str):
        body = {"question": question, "answer_from": "notes", "notes_only": True, "use_tools": False}
        text, sources, nxt = "", [], []
        with client.stream("POST", "/chat/stream", json=body) as response:
            for line in response.iter_lines():
                if line.strip():
                    event = json.loads(line)
                    if event["type"] == "answer":
                        text += event["delta"]
                    elif event["type"] == "sources":
                        sources = event.get("sources") or event.get("entries") or []
                    elif event["type"] in ("follow_ups", "next"):
                        nxt = event.get("items") or event.get("suggestions") or []
        return text, sources, nxt

    return go


SELF = [
    "what can you do", "anything interesting you can do??", "what are you able to do", "can you do anything fun",
    "what are your features", "anything cool you can do", "is there anything cool you can do",
    "what interesting things can you do", "something interesting you can do", "what cool stuff can you do",
    "tell me something interesting you can do", "do you have any cool features", "what are your best features",
]


@pytest.mark.parametrize("question", SELF)
def test_a_question_about_the_assistant_gets_the_capabilities_answer(ask, question):
    """Class (a): the same answer as "what can you do", never a search of the notes."""
    said, _sources, _next = ask(question)
    reference, _s, _n = ask("what can you do")
    assert said == reference, said
    assert "interesting bean" not in said.lower(), said


@pytest.mark.parametrize("question", [
    "what can you do about my interesting bean note", "tell me something interesting about lisbon",
    "anything interesting in my notes about the bean",
])
def test_a_question_with_its_own_object_is_still_a_search(ask, question):
    said, _sources, _next = ask(question)
    reference, _s, _n = ask("what can you do")
    assert said != reference, said

