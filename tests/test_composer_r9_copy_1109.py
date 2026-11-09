"""R9-15 and R9-17 (composer audit round 9, c12): a title-only note is said to be that, no filler opener, who-once and the
busiest day in words. Seed: `tests/_seed_r9_1109.py`."""

from __future__ import annotations

import pytest

import tests._seed_r9_1109 as sd


@pytest.fixture
def ask(client, session, monkeypatch):
    sd.seed(session)
    go = sd.asker(client, monkeypatch)
    return lambda question: go(question)[0]


def test_a_note_with_only_its_title_is_said_to_be_that(ask):  # R9-15
    text = ask("what's the recipe for thai green curry")
    assert "Thai green curry" in text and "only a title" in text, text
    assert "None of these notes" not in text, text


def test_no_right_away_filler_opens_an_answer():  # R9-17
    from tessellate.ai import composer_lines

    assert "Right away." not in [cand.text for cand in composer_lines.OPENERS]


def test_who_once_says_the_role_with_the_number(ask):  # R9-17
    text = ask("who is Dave")
    assert text.startswith("Dave is your plumber: 07700 900789"), text
    assert "only note that names" not in text, text


def test_the_busiest_day_counts_in_words(ask):  # R9-17
    text = ask("organise my week")
    assert "Busiest day: Friday 13 November, with two items." in text and " with 2." not in text, text
