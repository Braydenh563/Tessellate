"""INBOX 1561: "anything interesting you can do??" with no model. A question about
the assistant is answered about the assistant; an adjective is never the subject of
a search; the count agrees with the sources; a quote is a whole sentence. Class (b), the praise word, is here."""

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


# (b) A praise or filler word is never the subject.

@pytest.mark.parametrize("question", [
    "show me something interesting", "anything interesting", "tell me about the cool stuff", "what is good", "any fun stuff",
    "anything neat in here", "show me the interesting ones",
])
def test_an_adjective_alone_is_not_a_subject(question):
    from tessellate.ai import composer

    assert composer.subject_terms(question) == [], composer.subject_terms(question)


@pytest.mark.parametrize("question, kept", [
    ("what is the interesting bean", "bean"), ("anything cool about lisbon", "lisbon"), ("tell me about the good recipes", "recipes"),
])
def test_an_adjective_beside_a_noun_stays(question, kept):
    from tessellate.ai import composer

    assert kept in composer.subject_terms(question)


@pytest.mark.parametrize("question", ["show me something interesting", "tell me about the interesting stuff", "any cool stuff", "anything fun"])
def test_the_answer_never_says_notes_about_an_adjective(ask, question):
    said, _sources, nxt = ask(question)
    assert "about interesting" not in said.lower() and "about cool" not in said.lower() and "about fun" not in said.lower(), said
    assert not any(w in " ".join(map(str, nxt)).lower() for w in ("about interesting", "on interesting", "about cool", "about fun")), nxt
