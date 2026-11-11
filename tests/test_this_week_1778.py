"""INBOX 1778 (b): "What did I write this week?" answered "You have no notes
that fit yet." though the owner had written a gym note that week."""

from __future__ import annotations

from datetime import datetime

import pytest

from tessellate.api import routes_chat
from tessellate.core import config
from tessellate.entry import manager
from tests.test_composer_route_688 import _ask

#: Wednesday 11 November 2026; the week (Monday start) began on the 9th.
NOW = datetime(2026, 11, 11, 15, 0)


@pytest.fixture()
def clock(monkeypatch):
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)


def _note(session, when: datetime, text: str) -> None:
    entry = manager.create_entry(session, f"# {text}\n\nBody of {text}.")
    entry.created_at = entry.updated_at = when
    session.commit()


@pytest.fixture()
def week(session):
    _note(session, datetime(2026, 11, 10, 18), "Gym session")
    _note(session, datetime(2026, 11, 3, 9), "Old budget")
    _note(session, datetime(2026, 10, 1, 9), "Autumn plans")


def test_probe(client, clock, week):
    out = _ask(client, "What did I write this week?", use_tools=False)
    print(out["text"])
    out = _ask(client, "What did I write this week?")
    print({k: v for k, v in out.items() if k != "answer"})
    assert 0
