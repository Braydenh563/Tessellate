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


def _digest(question):
    from datetime import date, datetime, timedelta

    from tessellate.ai import composer_digest

    notes = [
        {"id": i + 1, "content": c, "tags": t, "category": "", "created_at": datetime(2026, 10, 30, 9) - timedelta(days=d)}
        for i, (c, t, d) in enumerate(seed_1030.NOTES)
    ]
    return composer_digest.answer(question, notes, today=date(2026, 10, 30))["text"]


@pytest.mark.parametrize("question", ["how long since I called Sara", "how long since I last called Sara"])
def test_z22_how_long_since_finds_a_line_whose_object_is_the_note_title(question):
    said = _digest(question)
    assert "do not say" not in said and "ago" in said, said


def test_z22_how_long_since_takes_a_verb_alone():
    said = _digest("how long since I last ran")
    assert "do not say" not in said and ("today" in said or "ago" in said), said


@pytest.mark.parametrize("question", ["how much are the flights", "what is the budget", "when is the beta"])
def test_z15_also_is_three_facts_at_most_and_starts_with_a_capital(ask, question):
    said = ask(question)[0]
    also = next((line for line in said.splitlines() if line.startswith("**Also:**")), "")
    assert also.count(";") <= 2, said
    assert not also or also.removeprefix("**Also:** ")[:1].isupper(), said


@pytest.mark.parametrize("question", ["summarise my notebook", "what is my notebook about", "what are my main themes"])
def test_z17_the_notebook_itself_is_a_subject_not_a_word_to_find(ask, question):
    said = ask(question)[0]
    assert "mention" not in said and "43 notes" in said, said


@pytest.mark.parametrize("question", ["how do I feel about running", "how did I feel about the run"])
def test_z20_a_feeling_question_leads_with_the_sentence_that_says_a_feeling(ask, question):
    said = ask(question)[0]
    assert "Felt really good" in said.split("\n")[0], said
