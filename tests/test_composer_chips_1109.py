"""A follow-on chip asks about a subject, never the question's own tail (R3-36, D19):
"What else have I saved about book am I reading?" was a button that asked the garbage
back. A subject that carries the question's verb makes no topic chip; the note chip stays.
Seed: `tests/_seed_1031c.py`."""

from __future__ import annotations

import pytest

import tests._seed_1031c as seed_c


@pytest.fixture
def chips(client, session, monkeypatch):
    seed_c.seed(session)
    go = seed_c.asker(client, monkeypatch)

    def asks(question):
        _text, events = go(question)
        offered = [a for e in events if e.get("type") == "offer" for a in (e.get("offer") or {}).get("asks", [])]
        return offered + [a for e in events if e.get("type") == "grounding" for a in (e.get("asks") or e.get("next") or [])]

    return asks


@pytest.mark.parametrize("question", ["what book am I reading", "how many times did I run", "does Sara like jazz"])
def test_no_chip_asks_about_the_questions_own_verb(chips, question):
    for ask in chips(question):
        assert not any(w in ask.lower().split() for w in ("am", "did", "like")), ask
    assert not any(ask.startswith(("What else have I saved about", "When did I last write about")) for ask in chips(question))


@pytest.mark.parametrize("question, subject", [("what time did I run", "run"), ("what is Anna's birthday", "Anna's birthday"), ("what is the latest on code", "code")])
def test_a_real_subject_still_gets_its_chips(chips, question, subject):
    assert any(f"about {subject}?" in ask for ask in chips(question)), chips(question)
