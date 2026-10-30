"""Composer audit 2026-10-30, Z66: a three-letter word of the language is not
read as a typo of a shorter one ("oat milk" was searched as "at milk")."""

from __future__ import annotations

import pytest

from tessellate.ai import question_noise, spelling
from tests import _seed_1030 as seed_1030


@pytest.mark.parametrize("word", ["oat", "gin", "yam", "fog", "cab", "bat", "fin"])
def test_z66_a_three_letter_word_is_left_alone(word):
    assert spelling.fix(word, after="milk", before="for") is None
    assert question_noise.repair(f"search for {word} milk") == f"search for {word} milk"


@pytest.mark.parametrize(("typed", "chosen"), [("teh", "the"), ("adn", "and")])
def test_z66_a_real_slip_is_still_put_right(typed, chosen):
    assert chosen in question_noise.repair(f"what is in {typed} note").split() + question_noise.repair(f"milk {typed} eggs").split()


@pytest.mark.parametrize("question", ["search for oat milk", "find oat milk"])
def test_z66_a_search_keeps_the_words_typed(client, session, monkeypatch, question):
    seed_1030.seed(session)
    said = seed_1030.asker(client, monkeypatch, chat=True)(question)[0]
    assert "oat milk" in said and "at milk" not in said.replace("oat milk", ""), said
