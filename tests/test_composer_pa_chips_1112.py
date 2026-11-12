"""Composer ledger 1112, composer-chips (F5): an empty count goes on to the weeks ahead, not to the statistics chips. No model."""

from __future__ import annotations

import pytest

import tests._seed_1031c as seed_c
from tessellate.ai import composer_chips


@pytest.fixture
def go(client, session, monkeypatch):
    seed_c.seed(session)
    return seed_c.asker(client, monkeypatch)


def _asks(events):
    return [a for e in events if e.get("type") == "offer" for a in (e.get("offer") or {}).get("asks", [])]


@pytest.mark.parametrize("question", ["what's overdue", "do I have any reminders overdue", "is anything overdue"])
def test_f5_nothing_overdue_offers_the_weeks_ahead(go, question):
    text, events = go(question)
    assert text.startswith("Nothing is overdue"), text
    asks = _asks(events)
    assert asks == ["What's due this week?", "What's due next week?"], asks
    assert not set(a.lower() for a in asks) & composer_chips.GENERIC


def test_f5_the_chips_nothing_overdue_offers_are_themselves_answered(go):
    for chip in ("What's due this week?", "What's due next week?"):
        text, _events = go(chip)
        assert "dated item" in text or "Nothing is due" in text, text


def test_f5_a_thanks_after_it_offers_the_same_chips_again(go):
    _text, first = go("what's overdue")
    text, events = go("thanks", history=[{"question": "what's overdue", "answer": "Nothing is overdue."}])
    assert _asks(first)
    assert not set(a.lower() for a in _asks(events)) & composer_chips.GENERIC, text
