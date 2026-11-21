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


def _titles(result: dict) -> list[str]:
    return sorted(n["content"].splitlines()[0].lstrip("# ") for n in result["notes"])


def test_the_composer_names_this_week_and_the_note(client, clock, week):
    text = _ask(client, "What did I write this week?", use_tools=False)["text"]
    assert "Gym session" in text and "no notes" not in text.lower()
    assert "Old budget" not in text


@pytest.mark.parametrize("phrase, expected", [
    ("this week", ["Gym session"]),
    ("last week", ["Old budget"]),
    ("yesterday", ["Gym session"]),
    ("today", []),
    ("since Monday", ["Gym session"]),
    ("this month", ["Gym session", "Old budget"]),
])
def test_a_span_in_since_or_category_filters_by_date(session, clock, week, phrase, expected):
    from tessellate.ai.tools import _list_notes

    by_since = _list_notes(session, {"since": phrase})
    by_category = _list_notes(session, {"category": phrase})
    assert _titles(by_since) == expected
    assert _titles(by_category) == expected
    assert by_category["total_matching"] == len(expected)


def test_an_edit_inside_the_window_counts(session, clock, week):
    from tessellate.ai.tools import _list_notes

    entry = manager.create_entry(session, "# Autumn plans two\n\nBody.")
    entry.created_at = datetime(2026, 10, 1, 9)
    entry.updated_at = datetime(2026, 11, 9, 8)
    session.commit()
    assert "Autumn plans two" in _titles(_list_notes(session, {"since": "this week"}))


def test_count_notes_reads_the_same_span(session, clock, week):
    from tessellate.ai.tools import _count_notes

    assert _count_notes(session, {"category": "this week"})["count"] == 1
    assert _count_notes(session, {"since": "last week"})["count"] == 1


def test_a_real_category_is_still_a_category(session, clock, week):
    from tessellate.ai.tools import _list_notes

    assert _list_notes(session, {"category": "Recipes"})["total_matching"] == 0
