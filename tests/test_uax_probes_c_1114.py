"""CHAT_PLAN Conversing rows C1 to C9 (LEDGER L-chat-108 to 112): the plan line's own phrasing asked of the
audit-1031 notebook (clock fixed at Saturday 31 October 2026, 11:30) with tools on and no model."""

from __future__ import annotations

import pytest

from tests import _seed_1031c as seed


@pytest.fixture
def say(client, session, monkeypatch):
    seed.seed(session)
    go = seed.asker(client, monkeypatch, chat=True)
    history: list[dict] = []

    def turn(question: str) -> str:
        text = go(question, history=list(history))[0]
        history.append({"question": question, "answer": text})
        return text

    return turn


def test_c1_a_greeting_follows_the_hour_and_the_return_and_never_runs_twice(say):
    first, second, third = say("hello"), say("hello"), say("hello")
    assert first.startswith("Good morning") and "welcome back" in first.lower()
    assert len({first, second, third}) == 3


def test_c3_a_feeling_word_is_named_back_and_no_advice_is_given(say):
    said = say("I am feeling anxious")
    assert "anxious" in said and "should" not in said.lower()


def test_c4_small_talk_does_not_repeat_a_reply_across_the_session(say):
    replies = [say("how are you") for _ in range(3)]
    assert len(set(replies)) == 3
