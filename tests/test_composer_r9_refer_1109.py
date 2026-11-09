"""R9-6 rest and R9-11 apples (composer audit round 9, c12): a line that says "it" names what it was, a second line
of a note names the note, apples are not the Apple watch. Seed: `tests/_seed_r9_1109.py`."""

from __future__ import annotations

import pytest

import tests._seed_r9_1109 as sd


@pytest.fixture
def ask(client, session, monkeypatch):
    sd.seed(session)
    go = sd.asker(client, monkeypatch)
    return lambda question: go(question)[0]


def test_a_line_that_says_it_names_what_it_was(ask):  # R9-6
    text = ask("who is Hannah")
    assert "Hannah loved Klara and the Sun" in text and "loved it" not in text, text


def test_a_second_line_of_a_note_names_the_note_not_it(ask):  # R9-6
    text = ask("what do I know about book club")
    assert "It also has" not in text and "Next book: The Remains of the Day" in text, text


def test_apples_are_not_the_apple_watch(ask):  # R9-11
    text = ask("what do I know about apples")
    assert "Battery" not in text and "4 apples" in text, text


def test_the_brand_is_still_found_by_its_own_name(ask):  # R9-11
    assert "Battery dies by 6pm" in ask("what do I know about the Apple watch")
