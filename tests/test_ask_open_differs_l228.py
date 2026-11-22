"""L228: the same question asked with different notes open gives different,
note-specific replies (22-10 bug doc: "Ask tab replies are identical across
notes"). Three fixture notes, each opened in turn, through /chat/stream."""

from __future__ import annotations

import json

import pytest

from tessellate.entry import manager

NOTES = {
    "plan": "# Harbor launch plan\n\nShip the mobile app on the 14th of next month. Three gates come first: beta feedback, onboarding, pricing.\n\n- [x] Beta invite list\n- [ ] Store listing copy",
    "trip": "# Lisbon trip\n\nTen days in May with Ana and Rui. The flight leaves on 3 May. Book the tram pass before we go.",
    "hire": "# Hiring a designer\n\nPortfolio review on Tuesday with Maria Costa. Looking for someone who has shipped a product end to end.",
}
#: One word only that note holds, so a reply that has it is about that note.
OWN = {"plan": "harbor", "trip": "lisbon", "hire": "designer"}

QUESTIONS = [
    "What's left to do?",
    "When is the deadline?",
    "Who is involved?",
    "What's the main point?",
    "What should I know?",
    "Is there anything important?",
    "Anything I am forgetting?",
]


def _ask(client, question: str, **body) -> str:
    text = []
    with client.stream("POST", "/chat/stream", json={"question": question, **body}) as response:
        assert response.status_code == 200
        for line in response.iter_lines():
            if line.strip():
                event = json.loads(line)
                if event["type"] == "answer":
                    text.append(event["delta"])
    return "".join(text)


@pytest.fixture
def ids(session):
    made = {k: manager.create_entry(session, v).id for k, v in NOTES.items()}
    session.commit()
    return made


@pytest.mark.parametrize("question", QUESTIONS)
def test_every_open_note_gets_its_own_reply(ai_client, ids, question):
    replies = {k: _ask(ai_client, question, open_note_id=i, notes_only=True, answer_from="notes") for k, i in ids.items()}
    assert len(set(replies.values())) == 3, "\n---\n".join(f"{k}: {v}" for k, v in replies.items())
