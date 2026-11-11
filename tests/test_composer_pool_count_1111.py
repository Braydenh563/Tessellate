"""comp1743 leftover: the overview reads a pool of at most `OVERVIEW_LIMIT` notes
(24), so a 30-note topic said "You have 24 notes". The lead counts the notes
that exist and says how many it read; the cap stays. Clock: Wednesday 11
November 2026, 10:30."""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta

import pytest

from tessellate.api import chat_pool, routes_chat
from tessellate.core import config
from tessellate.entry import manager

NOW = datetime(2026, 11, 11, 10, 30)


_THINGS = ("I planted beans", "I weeded the carrots", "I watered the tomatoes", "I built a compost bin", "I pruned the roses", "I sowed lettuce", "I mulched the paths")


def _make(session, count: int) -> None:
    for n in range(count):
        entry = manager.create_entry(session, f"{_THINGS[n % len(_THINGS)]} in the garden, bed {n}", "Gardening", ["garden"])
        entry.created_at = entry.updated_at = NOW - timedelta(days=3 + n * 2)
        manager.record_dates(session, entry, now=entry.created_at)
    session.commit()


def _ask(client, question: str) -> str:
    body = {"question": question, "answer_from": "notes", "notes_only": True, "use_tools": False}
    text = ""
    with client.stream("POST", "/chat/stream", json=body) as response:
        assert response.status_code == 200
        for line in response.iter_lines():
            if line.strip():
                event = json.loads(line)
                if event["type"] == "answer":
                    text += event["delta"]
    return text


@pytest.fixture(autouse=True)
def clock(monkeypatch):
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)


def test_a_topic_over_the_pool_cap_is_counted_whole(session, client):
    _make(session, 30)
    text = _ask(client, "what have I saved about gardening")
    assert chat_pool.OVERVIEW_LIMIT == 24
    assert "30 notes" in text, text
    assert "24 notes" not in text.split("\n")[0], text


def test_a_topic_under_the_cap_says_its_own_count(session, client):
    _make(session, 12)
    text = _ask(client, "what have I saved about gardening")
    assert re.search(r"\b(?:12|twelve) notes\b", text), text
    assert "read the" not in text.lower()


def test_the_story_says_how_many_it_tells(session, client):
    _make(session, 30)
    text = _ask(client, "what have I saved about gardening")
    assert re.search(r"That tells \w+ of the 30", text), text
