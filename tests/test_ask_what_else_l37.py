"""'What else do my notes say about university?' answers from the records (L-chat-37).

The owner, 2026-11-13 (two screenshots of Ask with no model, through the hub):
five records matched, and the answer was two sentences, both from the first
one: a mid-argument "however" line about what the notes leave out, then an
"Also" from the same note. The four concrete facts in the other records (uni
days, the subjects, the assignments, the friend) were ignored, the first
record's reason was the question's own word "notes", and a "Remind me the day
before" chip sat under a summary.
"""

from __future__ import annotations

import re

import pytest

from tessellate.core import deps
from tessellate.entry import manager
from tests.test_composer_route_688 import _ask

NOTES = (
    "# Core Concepts\n\nThis note pulls together the main ideas from my university study so far. "
    "What my notes currently leave out, however, is the complete overarching structure of your double "
    "degree and how the subjects fit together. It paints a picture of the subjects you are engaging with "
    "this semester and the skills each one builds.",
    "My uni days this week are tuesday and thursday, so I can work the other days.",
    "I'm taking one IT subject and three Design subjects - Tangible Interaction Design, Cloud Computing, "
    "Visual Communication and Design Futures.",
    "got sent home after 1h33 at work today, so I need to lock-in for my assignments at uni this week.",
    "missed the bus to uni this morning but ran into a uni friend at the stop and we caught the next one.",
)

QUESTION = "What else do my notes say about university?"
STOPWORDS = ("notes", "my", "say", "else", "what", "do", "about")


@pytest.fixture()
def client(app_state):
    """Model off, meaning search on: the owner's Ask found the five records by meaning."""
    from fastapi.testclient import TestClient

    from tessellate.api.app import create_app
    from tests.fakes import FakeEmbeddingService, FakeOllama

    deps.override_ai(ollama=FakeOllama(running=False), embeddings=FakeEmbeddingService(available=True))
    return TestClient(create_app())


def _seed(session):
    entries = [manager.create_entry(session, text) for text in NOTES]
    for entry in entries:
        deps.store_quietly(session, entry)
    session.commit()
    return [e.id for e in entries]


def _answer(client, session):
    _seed(session)
    out = _ask(client, QUESTION, notes_only=True, use_tools=False)
    final = out.get("answer_final")
    text = final[-1]["text"] if final and "text" in final[-1] else out["text"]
    return out, text


def _sentences(text):
    return [s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s]


def test_the_answer_draws_on_at_least_three_records(client, session):
    out, text = _answer(client, session)
    cited = {row["note_id"] for row in out["grounding"][-1]["sentences"]}
    assert len(cited) >= 3, text
    #: One line per record at most, plus the opening and one closing.
    assert 3 <= len(_sentences(text)) <= len(NOTES) + 2, text


def test_the_concrete_facts_are_in_the_answer(client, session):
    _, text = _answer(client, session)
    low = text.lower()
    assert "tuesday" in low and "thursday" in low, text
    assert "design" in low or "cloud computing" in low, text


def test_no_sentence_leads_with_a_connective(client, session):
    _, text = _answer(client, session)
    for sentence in _sentences(text):
        first = re.sub(r"^\W+", "", sentence).split(" ", 1)[0].lower().strip(",:")
        assert first not in {"however", "also", "but", "so"}, sentence
    assert "however" not in _sentences(text)[0].lower(), text


def test_no_reason_is_a_question_word(client, session):
    out, _ = _answer(client, session)
    blob = repr(out.get("sources", [])) + repr(out.get("meta", []))
    for word in STOPWORDS:
        assert f'word "{word}"' not in blob and f"word “{word}”" not in blob, word


def test_a_summary_offers_no_reminder(client, session):
    out, _ = _answer(client, session)
    assert "Remind me" not in repr({k: v for k, v in out.items() if k not in ("text",)})
