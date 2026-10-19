"""Notes by the order they were made (INBOX 1345 b, the owner, Chat with no model):
"what was the first note I ever wrote?" answered "Your notes don't mention
"first"", "the 5th note" answered the tag table after a search for
"doesn't have count_notes".

The reader is `ai/note_order.py`; the Chat composer, the Agent popup (both
through `/chat/stream`) and the Statistics Ask box share it.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from tessellate.ai import needle_provider, note_order, stats_ask
from tessellate.core.database import Entry
from tessellate.entry import manager
from tests.test_needle_provider import _install_fake_needle

_NOW = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)


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


def _seed(session, count: int = 8) -> list[int]:
    ids = []
    for i in range(count):
        entry = manager.create_entry(session, f"# Note {i}\n\nBody {i}.")
        entry.created_at = _NOW - timedelta(days=100 - i * 10)
        ids.append(entry.id)
    session.commit()
    return ids


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("what was the first note I ever wrote?", (1, False)),
        ("what's my oldest note", (1, False)),
        ("my newest note", (1, True)),
        ("the latest note I made", (1, True)),
        ("what was the last note I made", (1, True)),
        ("the 5th note I wrote", (5, False)),
        ("my 3rd most recent note", (3, True)),
        ("the second note", (2, False)),
        ("what did I write first", (1, False)),
        ("what did I write last?", (1, True)),
        ("the 500th note", (500, False)),
    ],
)
def test_the_reader(question, expected):
    assert tuple(note_order.read(question)) == expected


@pytest.mark.parametrize(
    "question",
    ["my first note about Harbor", "notes from last week", "What did I write last month?", "the last note on dentist", "what is in my notes", "how many notes do I have"],
)
def test_other_questions_are_left_alone(question):
    assert note_order.read(question) is None


def test_it_names_the_note_and_the_date(session):
    ids = _seed(session)
    first, _ = note_order.say(session, note_order.Ask(1, False), _NOW.tzinfo)
    assert first == f"Your first note is from 11 July 2026: [Note 0](#/notes/{ids[0]})"
    fifth, _ = note_order.say(session, note_order.Ask(5, False), _NOW.tzinfo)
    assert "Your 5th note" in fifth and f"(#/notes/{ids[4]})" in fifth
    third_back, _ = note_order.say(session, note_order.Ask(3, True), _NOW.tzinfo)
    assert "Your 3rd most recent note" in third_back and f"(#/notes/{ids[5]})" in third_back


def test_out_of_range_says_how_many(session):
    _seed(session, 40)
    text, found = note_order.say(session, note_order.Ask(500, False))
    assert text == "You have 40 notes, so there is no 500th one." and found is None


def test_deleted_drafts_private_and_boards_are_not_counted(session):
    ids = _seed(session, 5)
    for flag, at in (("is_deleted", 0), ("is_draft", 1), ("is_private", 2), ("is_board", 3)):
        setattr(session.get(Entry, ids[at]), flag, True)
    session.commit()
    assert note_order.count(session) == 1
    assert note_order.nth(session, note_order.Ask(1, False)).id == ids[4]
    assert note_order.nth(session, note_order.Ask(2, False)) is None


def test_the_chat_answers_it_with_no_model(client, session):
    ids = _seed(session)
    first = _ask(client, "what was the first note I ever wrote?")
    assert first.startswith("Your first note is from") and f"(#/notes/{ids[0]})" in first
    assert "don't mention" not in first
    assert f"(#/notes/{ids[4]})" in _ask(client, "what was the 5th note I ever wrote?")
    assert "You have 8 notes" in _ask(client, "the 500th note I wrote")


def test_the_agent_answers_it_and_never_reaches_for_a_tool(client, session, monkeypatch):
    ids = _seed(session)
    needle_provider.reset_for_tests()
    _install_fake_needle()
    asked: list[str] = []

    class _Engine:
        def complete(self, system, tools_json, text):
            asked.append(text)
            return {"function_calls": [{"name": "list_tags", "arguments": {}}]}

    monkeypatch.setattr(needle_provider, "_get_engine", lambda: _Engine())
    try:
        answer = _ask(client, "what was the 5th note I ever wrote?", use_tools=True)
    finally:
        needle_provider.reset_for_tests()
    assert f"(#/notes/{ids[4]})" in answer and "tags" not in answer.lower()
    assert asked == []


def test_the_statistics_ask_uses_the_same_reader(session):
    _seed(session)
    done = stats_ask.ask("when did I write my 3rd note", session, _NOW, {})
    assert done.kind == "note-order" and "Your 3rd note is from 31 July 2026: Note 2" in done.text
    assert stats_ask.ask("when did I write my first note", session, _NOW, {}).text.startswith("Your first note is from 11 July 2026")


# --- the Needle query (item 2) ------------------------------------------------------------


def test_needle_is_given_the_request_not_the_apps_lines_about_tools():
    turn = (
        "(No notes matched these words. That says nothing about how many I have: count_notes and search_notes do.)\n\n"
        "My request: what was the 5th note I ever wrote?"
    )
    assert needle_provider.request_of(turn) == "what was the 5th note I ever wrote?"
    assert needle_provider.request_of("plain words") == "plain words"


def test_a_tool_name_is_never_a_query():
    schemas = [
        {"name": "search_notes", "parameters": {"properties": {"query": {}}, "required": ["query"]}},
        {"name": "count_notes", "parameters": {"properties": {}}},
    ]
    calls = [{"name": "search_notes", "arguments": {"query": "doesn't have count_notes"}}]
    assert needle_provider._cleaned_calls(calls, schemas, "5th note") == []
    ok = [{"name": "search_notes", "arguments": {"query": "dentist"}}]
    assert len(needle_provider._cleaned_calls(ok, schemas, "dentist")) == 1


def test_a_needle_call_is_logged_under_needles_name():
    from tessellate.core import jobruns

    assert jobruns._named(type("P", (), {"name": "needle"})(), "gemma-big") == "needle"
    assert jobruns._named(type("P", (), {"name": "ollama"})(), "gemma-big") == "gemma-big"


@pytest.mark.parametrize(
    "question",
    ["what was the first note I ever wrote?", "what was the 5th note I ever wrote?", "what did I write in my notes about harbor"],
)
def test_a_question_about_your_own_notes_never_goes_to_the_web(question):
    from tessellate.ai import personal

    assert personal.about_own_notes(question)
    assert not personal.about_own_notes("what's the capital of France")
