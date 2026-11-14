"""L-chat-132 (Build 9): the recall kinds over real turns, no model: by time,
due, open and change of mind. Each states its count."""

import pytest

import tests._seed_r9_1109 as sd


@pytest.fixture
def ask(client, session, monkeypatch):
    sd.seed(session)
    sd.fix_clock(monkeypatch)
    return lambda q: sd.ask(client, q, notes_only=False)["text"]


@pytest.mark.parametrize("question, expect", [
    ("what did I write yesterday", "three notes yesterday"),
    ("what is due this week", "four dated items"),
    ("what tasks are still open", "Six items still open"),
    ("which of my to-dos are open", "Six unticked checklist items are still open"),
    ("what did I write about running last week", "one note"),
    ("how many notes did I write this month", "17 notes"),
    ("what notes contradict each other", "no change of mind"),
])
def test_each_recall_kind_answers_with_its_count(ask, question, expect):
    assert expect in ask(question)
