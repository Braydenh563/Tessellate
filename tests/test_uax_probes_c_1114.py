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


def test_c9_a_finished_list_is_remarked_on_and_an_unfinished_one_is_counted(say, session):
    from datetime import datetime

    from tessellate.entry import manager

    said = say("I finished everything on my list")
    assert "4 of the 5 items on the **Todo** list are still open" in said, said
    made = manager.create_entry(session, "# Garden jobs\n\n- [x] Mow\n- [X] Water\n- [x] Prune", category_name="Garden", tags=[])
    made.created_at = made.updated_at = datetime(2026, 10, 31, 9, 0)
    session.commit()
    assert "All 3 items on the **Garden jobs** list are ticked." in say("I finished everything on my list")
    assert "All 3 items on the **Garden jobs** list" in say("I've done all the items on the garden jobs list")


def test_c9_the_tick_that_finishes_a_list_is_remarked_on(client, session, monkeypatch):
    seed.seed(session)
    go = seed.asker(client, monkeypatch, chat=True)
    for item in ("sunscreen", "walking shoes", "power adapter", "charger"):
        _, events = go(f"tick off {item}")
        card = next(e for e in events if e.get("type") == "act")
        done = client.post("/chat/command/run", json={"steps": card["steps"], "skipped": [], "consent_id": card["consent_id"]}).json()
        assert done["ok"], done
    assert "All 5 items on **Lisbon packing list** are ticked." in done["summary"], done["summary"]
