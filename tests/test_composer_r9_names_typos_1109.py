"""R9-14 (composer audit round 9): a name typed one slip off ("hanna") is read as the note's name, and the
answer says so. Seed: `tests/_seed_r9_1109.py`."""

from __future__ import annotations

import pytest

import tests._seed_r9_1109 as sd
from tessellate.ai import composer_names


@pytest.fixture
def say(client, session, monkeypatch):
    sd.seed(session)
    go = sd.asker(client, monkeypatch)
    return lambda q: go(q)[0]


@pytest.mark.parametrize("ask", ["what do i know about hanna", "who is hanna"])
def test_hanna_is_hannah(say, ask):
    text = say(ask)
    assert "Hannah is your friend from uni" in text
    assert "None of your notes mention" not in text and "I found no mention" not in text


def test_the_answer_says_how_it_was_read(say):
    assert "hannah" in say("what do i know about hanna").split("\n", 1)[0].lower()


@pytest.mark.parametrize("ask", ["what do I know about hannover", "tell me about paris"])
def test_a_word_far_from_every_name_is_left_alone(say, ask):
    assert "hannah" not in say(ask).lower().split("\n", 1)[0]


def test_only_names_are_the_vocabulary():
    notes = [{"title": "Hannah", "content": "Hannah hosts the book club. the club meets monthly"}]
    names = composer_names.names_of(notes)
    assert "hannah" in names and "club" not in names
    assert composer_names.respell("what about pairs", names) == "what about pairs"
    assert composer_names.respell("what about hanna", names) == "what about hannah"
