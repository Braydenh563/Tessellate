"""Fable eye F15, left half: a checklist line a later note records as done is not
listed as pending in the note's overview either. One item has one state: the open list,
the yes or no, the reminder offer and now the gist all ask `recorded_later`."""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from tessellate.api import routes_chat
from tessellate.core import config
from tessellate.entry import manager

NOW = datetime(2026, 10, 30, 12, 0)
NOTES = [
    ("# Admin bits\n\n- [ ] Renew library membership\n- [ ] Book the dentist\n", datetime(2026, 10, 27, 9, 0)),
    ("# Membership sorted\n\nRenewed the library membership at the front desk today.", datetime(2026, 10, 29, 9, 0)),
]


@pytest.fixture
def ask(client, session, monkeypatch):
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)
    for content, when in NOTES:
        entry = manager.create_entry(session, content)
        entry.created_at = entry.updated_at = when
    session.commit()

    def go(question: str) -> str:
        body = {"question": question, "answer_from": "notes", "notes_only": True, "use_tools": False}
        text = ""
        with client.stream("POST", "/chat/stream", json=body) as response:
            for line in response.iter_lines():
                if line.strip():
                    event = json.loads(line)
                    if event["type"] == "answer":
                        text += event["delta"]
        return text

    return go


@pytest.mark.parametrize("question", [
    #: "My X note" is a counted ask: the route keeps the notes it counted and
    #: fetches no record notes, so the overview cannot see the later note.
    #: Needs the records carried beside the pool, not in it.
    "what is in my admin bits note",
    "tell me about admin bits",
    "what do I still need to do",
    "what is still open on admin bits",
])
def test_a_task_done_in_a_later_note_is_not_still_to_do(ask, question):
    said = ask(question)
    low = said.lower()
    assert not any(p in low for p in ("still need to renew", "renew library membership is still", "still has renew", "none of its two")), said
    assert "book the dentist" in low, said
    #: Listed as open, the line names no later note; said done, it does.
    for line in low.splitlines():
        if "renew library membership" in line:
            assert "29 october" in line or "done" in line, said


@pytest.mark.parametrize("question", [
    "what is in my admin bits note",
    "what is in the admin bits note",
    "show me my admin bits note",
    "what's left in my admin bits note",
])
def test_a_named_note_keeps_its_records_beside_it(client, session, question):
    """The closed set of one named note fetches the notes that name its open
    items beside it (the model's context too), never in its place."""
    from tessellate.api import routes_chat as rc

    first = manager.create_entry(session, NOTES[0][0])
    later = manager.create_entry(session, NOTES[1][0])
    session.commit()
    found = rc._Found(detected="notes")
    rc._retrieve_for(session, question, found, [first], True, None, None, True, False)
    assert [e.id for e in found.entries] == [later.id]


@pytest.mark.parametrize("question", [
    "summarise this", "give me the gist of this", "what is in this note", "what's in this", "what is this about",
    "summarize this note",
])
def test_a_this_question_reads_the_screens_note_alone(client, session, question):
    """The records ride beside a note the question names, not beside the note on
    the screen: "summarise this" is that note as written (audit C29)."""
    from tessellate.api import routes_chat as rc

    first = manager.create_entry(session, NOTES[0][0])
    manager.create_entry(session, NOTES[1][0])
    session.commit()
    found = rc._Found(detected="notes")
    rc._retrieve_for(session, question, found, [first], True, None, None, True, False)
    assert found.entries == []
