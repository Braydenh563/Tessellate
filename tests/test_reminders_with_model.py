"""Reminder, task and due questions answer from the reminders themselves even
with a model up (CHAT_PLAN decision 75: the model must not do worse than the
composer). Measured 2026-10-12 against Qwen2.5-1.5B: "What reminders do I
have?" was answered from the notes as "two reminders" when there were three;
the no-model path lists the real ones.

Changed 2026-10-27 (the owner: "why is it responding as the composer when my
ai is in use??"): the model now writes the words from the real list
(`_fact_events`), and a reply that miscounts, like the one faked here, is
refused for the engine's own, with a second `meta` naming no model. The
intent is unchanged: the miscount never reaches the reader. The model-written
case is `tests/test_model_writes_facts_1027.py`.
"""

from __future__ import annotations

import json

import pytest

from tessellate.ai import reading, tools


def _seed(session):
    tools.execute_tool(session, "create_note", {"content": "Reminders: I have two reminders this week", "tags": ["home"]})
    for text, when in (("call mum", "tomorrow at 9"), ("pay rent", "in 3 days at 10am"), ("book dentist", "in 5 days at 11am")):
        tools.execute_tool(session, "set_reminder", {"text": text, "when": when})
    session.commit()


def _answer(client, question, use_tools):
    events = []
    with client.stream("POST", "/chat/stream", json={"question": question, "use_tools": use_tools}) as response:
        for line in response.iter_lines():
            if line.strip():
                events.append(json.loads(line))
    return events, "".join(e.get("delta", "") for e in events if e["type"] == "answer")


@pytest.mark.parametrize("use_tools", [False, True])
@pytest.mark.parametrize(
    "question",
    ["What reminders do I have?", "what tasks do I have", "whats due this week", "what is overdue", "list my to-dos"],
)
def test_a_reminder_question_lists_the_real_reminders_with_a_model_up(ai_client, fake_ollama, session, question, use_tools):
    _seed(session)
    fake_ollama.librarian_reply = "You have two reminders."
    events, answer = _answer(ai_client, question, use_tools)
    assert "two reminders" not in answer, answer
    for text in ("call mum", "pay rent", "book dentist"):
        assert text in answer, (question, answer)
    #: The latest `meta` is the one every client reads (`_fact_events`).
    meta = [e for e in events if e["type"] == "meta"][-1]
    assert meta["raw_results"] == [] and meta["answered_by"] is None


@pytest.mark.parametrize(
    "question",
    ["what is still open on the harbor launch", "what do I need to do for the garden", "remind me to call mum at 5", "summarise my reminders note", "what is due diligence"],
)
def test_a_checklist_or_an_act_is_not_taken_for_the_reminder_list(question):
    from datetime import datetime

    assert reading.read(question, now=datetime(2026, 10, 12, 9)).tool != "list_reminders"
