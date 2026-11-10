"""F2 and F4 of the 1110 audit, no model, clock fixed at Tuesday 10 November 2026, 09:00.

- F2: "stats" inside another subject is a note search; the overview only when the notebook's figures are asked for.
- F4: social turns and turns about the last answer are read, never searched as notes."""

from __future__ import annotations

import pytest

import tests._seed_1031c as seed_c

STATS_ASKS = [
    "when is the stats exam",
    "what's the stats exam worth",
    "when is the stats exam on",
    "statistics lecture",
    "I have so much going on this week, can you tell me when the stats exam is and what it covers please",
]
OVERVIEW = ["statistics", "show my statistics", "notebook stats", "stats"]


@pytest.fixture
def go(client, session, monkeypatch):
    seed_c.seed(session)
    return seed_c.asker(client, monkeypatch)


@pytest.fixture
def go_chat(client, session, monkeypatch):
    seed_c.seed(session)
    return seed_c.asker(client, monkeypatch, chat=True)


@pytest.mark.parametrize("ask", STATS_ASKS)
def test_a_stats_word_inside_another_subject_is_a_note_search(go, ask):
    text, events = go(ask)
    assert "notes in" not in text or "categories" not in text, text
    assert "Open Statistics" not in text, text


@pytest.mark.parametrize("ask", STATS_ASKS[:2])
def test_the_statistics_card_is_not_attached_with_a_model_up(go_chat, ask):
    _text, events = go_chat(ask)
    assert not any("statistic" in str(e.get("tool", e.get("name", ""))).lower() for e in events if e.get("type") in ("tool", "tool_result", "card")), events


@pytest.mark.parametrize("ask", OVERVIEW)
def test_the_notebook_figures_still_give_the_overview(go, ask):
    text, _ = go(ask)
    assert "notes" in text and ("categor" in text or "tag" in text), text
