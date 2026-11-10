"""W7 (2026-11-10): which note leads and what it is called. One test per audit row, probed first and
fixed as a class (B9 one-note notebook and time travel here; B1 to B8 and B10 below). Clock fixed."""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from tessellate.api import routes_chat
from tessellate.core import config
from tessellate.entry import manager

NOW = datetime(2026, 10, 30, 2, 50)


def _stream(client, body: dict) -> str:
    out = ""
    with client.stream("POST", "/chat/stream", json=body) as response:
        for line in response.iter_lines():
            if line.strip():
                event = json.loads(line)
                if event.get("type") == "answer":
                    out += event["delta"]
    return out


@pytest.fixture
def one_note(client, session, monkeypatch):
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)
    entry = manager.create_entry(session, "# Lisbon trip\nFlying 14 November. Descale the kettle on Sunday.", category_name="Uncategorised")
    entry.created_at = entry.updated_at = datetime(2026, 10, 30, 1, 0)
    session.commit()
    return lambda q, **extra: _stream(client, {"question": q, "use_tools": False, **extra})


# --- B9 one-note notebook and time travel (R3-31, R3-32) --------------------------------

@pytest.mark.parametrize("question", ["what do I know about Lisbon", "what is in the Lisbon trip note", "tell me about Lisbon"])
def test_a_one_note_notebook_does_not_promise_other_notes(one_note, question):
    text = one_note(question)
    assert "Lisbon" in text and "search by meaning" not in text, text


@pytest.mark.parametrize("question", ["what is in my notebook", "what's in my notebook", "what did I write"])
def test_as_of_gives_the_notebook_as_it_stood(one_note, question):
    text = one_note(question, as_of="2026-10-31")
    assert text.startswith("On 31 October 2026 you had 1 note"), text
    assert "I found no mention" not in text


def test_as_of_before_any_note_says_none(one_note):
    assert "no notes from on or before 1 October 2026" in one_note("what is in my notebook", as_of="2026-10-01")
