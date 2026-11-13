"""Audit rows closed on 2026-11-11: 1030 Z7 (the stale-plan line quotes no verb phrase)."""

from __future__ import annotations

from datetime import date

import pytest

from tessellate.ai import insights

TODAY = date(2026, 11, 11)


def _text(content: str) -> str:
    note = {"id": 1, "content": content, "created_at": "2026-09-20T10:00:00", "tags": []}
    return insights.drift([note], TODAY)[0].text


@pytest.mark.parametrize("content, said", [
    ("Tokyo trip\nWant to see Kyoto and Nara.", "your plan to see Kyoto and Nara"),
    ("I plan to book the flights.", "your plan to book the flights"),
])
def test_a_stale_plan_is_said_as_a_noun_phrase(content, said):
    text = _text(content)
    assert f"no later note picks up {said}. It may still be open." in text, text
    assert "picks up want" not in text and "may be still" not in text


@pytest.mark.parametrize("content, said", [
    ("Need to lock-in for my assignments.", "your plan to lock-in for my assignments"),
    ("I need to lock in for my assignments", "your plan to lock in for my assignments"),
    ("I should call the bank about the mortgage", "your plan to call the bank about the mortgage"),
    ("Planning to visit Lisbon in spring", "your plan to visit Lisbon in spring"),
])
def test_l186_a_need_or_should_is_said_as_a_plan_not_a_quoted_fragment(content, said):
    """L186 (Z7): the verb-led fragment was quoted after "this plan:" with its own mood and word order."""
    text = _text(content)
    assert f"no later note picks up {said}. It may still be open." in text, text
    assert "this plan:" not in text
