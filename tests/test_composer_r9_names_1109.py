"""R9-15 and R9-16 (composer audit round 9): one name for a note on every surface, no raw checklist markdown in a
day list. Seed: `tests/_seed_r9_1109.py`."""

from __future__ import annotations

import pytest

import tests._seed_r9_1109 as sd


@pytest.fixture
def say(client, session, monkeypatch):
    sd.seed(session)
    go = sd.asker(client, monkeypatch)
    return lambda q: go(q)[0]


def test_whats_new_names_a_title_less_note_in_quotes_not_bold(say):
    text = say("what's new")
    assert "[“planted the garlic today, three rows…”](#/notes/20)" in text
    assert "[**Running log**](#/notes/29)" in text
    assert "**planted the garlic" not in text


@pytest.mark.parametrize("ask", ["what did I do last week", "what happened on 7 November", "summarise last week"])
def test_a_day_list_says_a_checklist_in_words(say, ask):
    text = say(ask)
    assert "[ ]" not in text and "[x]" not in text and " - [" not in text
    assert "oat milk, garlic and lemons" in text


def test_a_date_still_ahead_is_said_by_its_distance_not_the_write_date(say):
    text = say("when is mum's birthday")
    assert text.startswith("Mum's birthday is 2 December")
    assert "in 23 days" in text
    assert "written on 11 August" not in text


@pytest.mark.parametrize(("fact", "today", "want"), [
    ("Mum's birthday is 2 December", sd.TODAY, "in 23 days"),
    ("Meet on 10 November", sd.TODAY, "tomorrow"),
    ("Dentist 9 November", sd.TODAY, "today"),
    ("Ran 10 km on 1 November", sd.TODAY, ""),
    ("Holiday on 15 March", sd.TODAY, ""),
    ("No date here", sd.TODAY, ""),
])
def test_distance_reads_only_a_day_still_ahead(fact, today, want):
    from tessellate.ai import composer_ahead

    assert composer_ahead.distance(fact, today) == want
