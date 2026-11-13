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


@pytest.mark.parametrize("question", ["dig out the hotel notes", "display gym", "fetch dentist", "pull out the dentist note"])
def test_l187_a_retrieval_verb_is_not_named_as_missing(client, session, monkeypatch, question):
    """L187 (Z16): "fetch", "display", "dig out" order the answer; no note is "missing" them."""
    import tests._seed_1031c as seed_c
    from tessellate.entry import manager

    for content in ("# Gym\n\nGym membership is £35 a month.", "# Hotel\n\nBooked the hotel in Lisbon for 3 nights.", "# Dentist\n\nDentist check-up on 4 November at 9am."):
        entry = manager.create_entry(session, content)
        entry.created_at = entry.updated_at = seed_c.NOW
    session.commit()
    said, _ = seed_c.asker(client, monkeypatch)(question)
    assert "mention" not in said and "nothing in these notes" not in said and "find anything about" not in said and "say nothing about" not in said, said


def test_l189_each_line_of_a_note_is_its_own_sentence_in_a_dated_listing(client, session, monkeypatch):
    """L189 (E16): "Phone 020 7946 0011" and "Dentist check-up" ran together as one line."""
    import tests._seed_1031c as seed_c
    from tessellate.entry import manager

    entry = manager.create_entry(session, "Dentist\nPhone 020 7946 0011\nDentist check-up on 11 November.")
    entry.created_at = entry.updated_at = seed_c.NOW
    session.commit()
    said, _ = seed_c.asker(client, monkeypatch)("what did I do on " + f"{seed_c.NOW.day} {seed_c.NOW:%B}")
    assert "0011. Dentist check-up" in said, said


def test_l204_a_dated_list_does_not_restate_a_note_that_is_only_its_name(client, session, monkeypatch):
    """L204 (E18): "what did I write about in October" listed “milk” (27 October): Milk."""
    import tests._seed_1031c as seed_c
    from tessellate.entry import manager

    for content in ("milk", "Dentist check-up on 11 November."):
        entry = manager.create_entry(session, content)
        entry.created_at = entry.updated_at = seed_c.NOW
    session.commit()
    said, _ = seed_c.asker(client, monkeypatch)(f"what did I write about in {seed_c.NOW:%B}")
    assert "“milk”" in said and "Milk." not in said and "milk”: " not in said, said


def test_l205_a_compare_opens_on_its_counts_and_cites_each_note_once():
    """L205 (D20): "Of the notes found, ..." opened a comparison and a note's mark could come twice."""
    import re

    from tests import _seed_r2_1107 as seed

    text = seed.ask("compare Tokyo and Lisbon")
    assert text.startswith("Two notes mention Tokyo and three mention Lisbon."), text
    marks = re.findall(r"\(\*\*([^*]+)\*\*\)", text)
    assert marks and len(marks) == len(set(marks)), text
