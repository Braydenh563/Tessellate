"""INBOX 1569 (c), (d), (e): the starter reading's figures are the app's own, its Why trail
names the step that found the notes, and the trail's time says what it times."""

from __future__ import annotations

import json

import pytest

from tests.test_changed_today_1569 import NOW, _seed
from tessellate.api import routes_chat
from tessellate.core import config


@pytest.fixture
def ask(client, monkeypatch):
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)

    def go(question: str = "What changed in my notebook today?") -> str:
        text = ""
        with client.stream("POST", "/chat/stream", json={"question": question, "answer_from": "notes", "use_tools": False}) as response:
            for line in response.iter_lines():
                if line.strip() and json.loads(line)["type"] == "answer":
                    text += json.loads(line)["delta"]
        return text

    return go


def test_a_starter_reading_is_exempt_from_the_number_check(ask, session):
    from tessellate.api import chat_turn

    _seed(session, background=2, edited=25, written=0)
    said = ask()
    assert "heads up" not in said.lower(), said
    assert not chat_turn._checks_grounding({"stats": None, "app_first": True}, False, False, False)


# (d) The Why trail names the step that found the notes, (e) and says what its time is.

def test_the_why_trail_names_the_reading_and_what_its_time_measures(client, session, monkeypatch):
    _seed(session, background=3, edited=3, written=1)
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)
    lines = []
    body = {"question": "What changed in my notebook today?", "answer_from": "notes", "use_tools": False}
    with client.stream("POST", "/chat/stream", json=body) as response:
        for line in response.iter_lines():
            if line.strip():
                event = json.loads(line)
                if event["type"] == "why":
                    lines = [row["text"] for row in event["lines"]]
    assert lines, lines
    assert not any("nothing matched" in t for t in lines), lines
    assert any("written and edited" in t for t in lines), lines
    assert lines[-1].startswith("Done in") and "whole wait" in lines[-1], lines
