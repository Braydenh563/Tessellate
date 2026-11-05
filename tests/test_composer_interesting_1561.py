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
                    elif event["type"] == "grounding":
                        sources = event.get("sentences") or []
                        nxt = event.get("next") or []
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




# (c) The count, the names and the sources are one set, and "other(s)" agrees.

def _tail(total: int):
    from datetime import date
    from types import SimpleNamespace as NS

    from tessellate.ai import composer_digest as digest

    def view(i):
        return NS(id=i, note={"source_id": i, "title": f"Note {i}", "content": f"Note {i}", "tags": []}, title=f"Note {i}", titled=True,
                  kind="note", written=None, sentences=[])

    out = digest._Out()
    out.rows.append({"note_id": 1})
    digest._overview_tail(out, "overview", [view(i) for i in range(1, total + 1)], date(2026, 1, 1), False, 1)
    return out


@pytest.mark.parametrize("total, line", [
    (2, "The other is Note 2."), (3, "The others are Note 2 and Note 3."), (4, "The others are Note 2, Note 3 and Note 4."),
])
def test_the_others_agree_in_number_and_every_note_named_is_cited(total, line):
    out = _tail(total)
    assert out.lines == [line], out.lines
    assert [r["note_id"] for r in out.rows] == list(range(1, total + 1)), out.rows
