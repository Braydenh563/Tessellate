"""W9 B29: the tick-off phrasings each reach a confirm card for the named task
(consent for every act), and the loose "I finished X" without a kind word stays
a question (audit 1030 A15 guard, tests/test_audit_1030_ai_acts.py)."""

from __future__ import annotations

import pytest

import tests._seed_r9_1109 as sd

FORMS = ["tick off oat milk", "mark oat milk as done", "mark the task oat milk done", "complete oat milk", "cross off oat milk", "check off oat milk"]


@pytest.mark.parametrize("message", FORMS)
def test_each_tick_off_form_asks_before_ticking(client, session, monkeypatch, message):
    sd.seed(session)
    said, events = sd.asker(client, monkeypatch, chat=True)(message)
    assert "oat milk" in said.lower() and "Confirm" in said, said
    assert any(e.get("type") == "act" for e in events), message


def test_the_add_form_answers_with_the_default_time(client, session, monkeypatch):
    sd.seed(session)
    said, _events = sd.asker(client, monkeypatch, chat=True)("add a task to read chapter 5 tomorrow")
    assert "due tomorrow at 9am (the default)" in said and "read chapter 5" in said, said


def test_a_follow_on_with_it_reads_the_note_the_answer_cited(client, session, monkeypatch):
    """B21: "tell me more about it" is scoped to the cited note, as "tell me more about the Plumber note" is."""
    sd.seed(session)
    go = sd.asker(client, monkeypatch, chat=False)
    question = "what did I write about the plumber"
    history = [{"question": question, "answer": go(question)[0], "objects": ["Plumber", "Call plumber"]}]
    said = go("tell me more about it", history=history)[0]
    assert "Dave" in said and "olive oil" not in said, said


def test_and_the_other_one_asks_about_the_other_cited_note(client, session, monkeypatch):
    """B21: not the notes nearest the bare words."""
    sd.seed(session)
    go = sd.asker(client, monkeypatch, chat=False)
    question = "what did I write about the plumber"
    history = [{"question": question, "answer": go(question)[0], "objects": ["Plumber", "Todo"]}]
    said = go("and the other one?", history=history)[0]
    assert "Ran 10 km" not in said and "**Todo**" in said, said
