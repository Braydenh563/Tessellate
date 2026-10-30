"""Composer audit 2026-10-30, class 3: a question about a person or a thing
that a note answers is never refused first (Z14,
docs/roadmap/agent-remaining/audit-1030-composer.md)."""

from __future__ import annotations

import pytest

from tests import _seed_1030 as seed_1030


@pytest.fixture
def ask(client, session, monkeypatch):
    seed_1030.seed(session)
    return seed_1030.asker(client, monkeypatch)


@pytest.mark.parametrize("question", ["who is my sister", "what's my sister's name", "what is my sister called"])
def test_z14_a_relation_a_note_states_in_either_order_is_answered(ask, question):
    said = ask(question)[0]
    assert "Sara" in said and "don't name" not in said, said


@pytest.mark.parametrize("question", ["what should I watch next", "what should I watch"])
def test_z14_advice_with_no_favourite_falls_back_to_the_notes(ask, question):
    said = ask(question)[0]
    assert "That's your call" not in said and "Past Lives" in said, said


@pytest.mark.parametrize("question", ["who is Dr Patel", "who is Patel", "which note mentions Dr Patel"])
def test_z13_a_name_in_a_line_too_short_for_a_sentence_still_gets_a_sentence(ask, question):
    said = ask(question)[0]
    assert "Patel" in said.split("\n")[0] and "[**" not in said, said
    assert "Dentist appointment" in said, said


@pytest.mark.parametrize("question", ["what do I know about uni", "tell me about uni", "what do I know about the cloud"])
def test_z3_two_sentences_of_a_note_are_never_joined_by_a_comma(ask, question):
    said = ask(question)[0]
    assert "kernel, Autoscaling" not in said and "kernel, autoscaling" not in said, said


@pytest.mark.parametrize("question", ["when did I run 8 km", "when was my 8 km run", "what day did I run 8 km"])
def test_z4_the_amount_asked_about_picks_the_sentence_and_the_rewrite_keeps_its_words(ask, question):
    said = ask(question)[0]
    assert "8 km" in said and "6 km" not in said, said


@pytest.mark.parametrize("question", ["when did I run 5 km", "what date did I run 5 km", "when did I last run 5 km"])
def test_z4_a_day_moved_to_the_front_takes_its_preposition_with_it(ask, question):
    said = ask(question)[0]
    assert " on in " not in said and " on," not in said.split("\n")[0], said
