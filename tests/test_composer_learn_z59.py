"""Audit 1030 Z59: "what am I learning" said nothing beside "Learning Spanish
with Duolingo"; "what is my streak" gave the app's writing streak unlabelled
beside the Spanish note's own 42-day streak.

The audit-1030 notebook (`tests/_seed_1030.py`), fixed clock 30 October 2026.
"""

from __future__ import annotations

import pytest

from tests import _seed_1030 as seed


@pytest.fixture
def ask(client, session, monkeypatch):
    seed.seed(session)
    go = seed.asker(client, monkeypatch)
    return lambda q: go(q)[0]


@pytest.mark.parametrize("question", ["what am I learning", "what am I studying", "what have I been learning",
                                      "what do I want to learn", "what have I been studying lately"])
def test_every_learn_question_finds_the_note_that_says_it(ask, question):
    said = ask(question)
    assert "Spanish" in said, said
    assert "don't say you're learning" not in said, said


@pytest.mark.parametrize("question", ["what is my streak", "what's my longest streak", "how long is my streak"])
def test_the_apps_streak_is_labelled_as_writing(ask, question):
    said = ask(question)
    assert "writing streak" in said, said
