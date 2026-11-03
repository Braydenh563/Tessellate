"""INBOX 1569: "What changed in my notebook today?" said 25 notes were edited when the
owner edited none. Background work moves `updated_at`; only a person's edit counts."""

from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest

from tessellate.api import routes_chat
from tessellate.core import config
from tessellate.entry import manager

NOW = datetime(2026, 11, 3, 12, 0)


def _seed(session, background: int, edited: int, written: int = 0):
    for k in range(background + edited):
        note = manager.create_entry(session, f"# Old note {k}\n\nSomething written long ago number {k}.")
        note.created_at = NOW - timedelta(days=40 + k)
        note.updated_at = NOW - timedelta(hours=2)
        note.edited_at = (NOW - timedelta(hours=3)) if k < edited else None
    for k in range(written):
        note = manager.create_entry(session, f"# New note {k}\n\nWritten this morning number {k}.")
        note.created_at = NOW - timedelta(hours=1 + k)
        note.updated_at = note.created_at
    session.commit()


@pytest.fixture
def ask(client, session, monkeypatch):
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)

    def go(question: str = "What changed in my notebook today?") -> str:
        text = ""
        body = {"question": question, "answer_from": "notes", "use_tools": False}
        with client.stream("POST", "/chat/stream", json=body) as response:
            for line in response.iter_lines():
                if line.strip():
                    event = json.loads(line)
                    if event["type"] == "answer":
                        text += event["delta"]
        return text

    return go


PHRASES = [
    "What changed in my notebook today?", "what changed in my notebook since yesterday", "what has changed today", "what changed in the notebook today",
]


@pytest.mark.parametrize("question", PHRASES)
def test_background_work_is_not_an_edit(ask, session, question):
    """Class (a): 25 notes touched by date reading, filing or embeddings, none edited by a person."""
    _seed(session, background=25, edited=0)
    said = ask(question)
    assert said.lower().startswith("nothing was written or edited"), said
    assert "25" not in said and "twenty" not in said.lower(), said


@pytest.mark.parametrize("question", PHRASES)
def test_only_a_persons_edits_are_counted(ask, session, question):
    _seed(session, background=25, edited=2, written=1)
    said = ask(question)
    assert "two notes edited" in said.lower() and "one note written" in said.lower(), said
    assert "27" not in said and "twenty" not in said.lower(), said


@pytest.mark.parametrize("edited", [3, 5, 9])
def test_the_list_agrees_with_its_count(ask, session, edited):
    """Class (b): the count names more than the two quotes, and the line after them says how many are left."""
    from tessellate.ai import realise

    _seed(session, background=10, edited=edited, written=0)
    said = ask()
    assert said.count("- “") == 2, said
    assert f"And {realise.count_word(edited - 2)} more." in said, said


def test_one_or_two_notes_need_no_and_more(ask, session):
    _seed(session, background=4, edited=2, written=0)
    said = ask()
    assert "more" not in said and said.count("- “") == 2, said
