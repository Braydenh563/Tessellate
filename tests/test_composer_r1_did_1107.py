"""Composer round 1, 2026-11-07, D4: a "did I" answer needs a note that says it
was done, and a count with a subject counts the subject. Driven through the
chat route with no model (fake transport); the clock is `_seed_1031c.NOW`."""

from __future__ import annotations

import pytest

import tests._seed_1031c as seed_c
from tessellate.entry import manager


@pytest.fixture
def notebook(client, session, monkeypatch):
    def make(*contents):
        for content in contents:
            entry = manager.create_entry(session, content)
            entry.created_at = entry.updated_at = seed_c.NOW
        session.commit()
        return seed_c.asker(client, monkeypatch)

    return make


def test_d4_a_to_do_line_is_not_a_record_that_it_was_done(notebook):
    go = notebook("Pay rent, due 10 November", "# Budget\n\nRent £950 a month. Phone £12.")
    said, _ = go("did I pay the rent")
    assert not said.startswith("Yes"), said


def test_d4_a_past_tense_line_still_answers_yes(notebook):
    go = notebook("Paid rent on 3 November", "# Budget\n\nRent £950 a month. Phone £12.")
    said, _ = go("did I pay the rent")
    assert said.startswith("Yes"), said


def test_review2_a_record_that_says_it_was_due_is_still_a_record(notebook):
    go = notebook("Paid rent on 1 November, it was due on the 1st.", "# Budget\n\nRent £950 a month. Phone £12.")
    said, _ = go("did I pay the rent")
    assert said.startswith("Yes"), said


@pytest.mark.parametrize(("line", "plans"), [("Pay rent, due 10 November", True), ("- Send the report, deadline Friday", True),
                                            ("Paid rent on 1 November, it was due on the 1st.", False), ("Sent the report; the deadline was Friday", False),
                                            ("Remember to pay rent", True), ("Paid rent", False)])
def test_review2_planned_tells_a_to_do_from_a_record(line, plans):
    from tessellate.ai import composer_done

    assert composer_done.planned(line) is plans


def test_d4_a_booking_note_answers_did_i_book(notebook):
    go = notebook(
        "# Lisbon trip\n\nFlights cost $420 return, leaving 12 May. Staying at Hotel Alfama near the river.",
        "# Hotel Alfama\n\nBooking reference HA-77421. Late check-out requested. Breakfast included.",
    )
    said, _ = go("did I book the hotel")
    assert "found nothing" not in said and "HA-77421" in said, said


def test_review4_a_titled_note_with_no_line_on_the_verb_is_not_offered_as_the_doing(notebook):
    go = notebook(
        "# Lisbon trip\n\nFlights cost $420 return, leaving 12 May.",
        "# Hotel Alfama\n\nLate check-out requested. Breakfast included.",
    )
    said, _ = go("did I book the hotel")
    assert "does not say it outright" not in said and "Breakfast" not in said.split("closest")[0], said


def test_review4_the_line_offered_is_the_one_on_the_verb_not_the_first(notebook):
    go = notebook(
        "# Lisbon trip\n\nFlights cost $420 return, leaving 12 May.",
        "# Hotel Alfama\n\nLate check-out requested. Booking reference HA-77421. Breakfast included.",
    )
    said, _ = go("did I book the hotel")
    assert "HA-77421" in said and "Late check-out" not in said, said


@pytest.mark.parametrize("question", ["how many notes have the word Lisbon", "how many notes contain Lisbon", "how many notes mention Lisbon",
                                      "how many notes have the word Lisbon?", "How many notes contain Lisbon?", "how many notes have the phrase Lisbon."])
def test_d4_a_count_with_a_subject_counts_the_subject(notebook, question):
    go = notebook(
        "# Lisbon trip\n\nFlights cost $420 return.",
        "# Hotel Alfama\n\nA hotel in Lisbon. Breakfast included.",
        "# Banana bread\n\n3 ripe bananas, 100 g butter.",
        "# Gym plan\n\nSquats, bench, rows.",
        "# Dentist\n\nDr Patel at Kings Road practice.",
    )
    said, _ = go(question)
    assert "five notes" not in said and "You have 5 notes" not in said, said
    assert "two notes" in said.lower() or "2 notes" in said, said


COUNT_NOTES = (
    "# Lisbon trip\n\nFlights cost $420 return.",
    "# Hotel Alfama\n\nA hotel in Lisbon. Breakfast included.",
    "# Banana bread\n\n3 ripe bananas, 100 g butter.",
)


def test_review3_the_word_keeps_the_casing_the_person_typed(notebook):
    said, _ = notebook(*COUNT_NOTES)("how many notes have the word Lisbon?")
    assert "mention Lisbon" in said and "lisbon" not in said, said


@pytest.mark.parametrize("question", ["how many notes do I have today", "how many notes did I have yesterday", "how many notes have I got this week",
                                      "how many notes have reminders", "how many notes have photos", "how many notes have tags", "how many notes have links?"])
def test_review3_a_day_or_a_kind_after_have_is_not_a_word_to_find(question, client, session):
    from tessellate.ai import notebook_stats
    from tessellate.entry import manager

    for content in COUNT_NOTES:
        manager.create_entry(session, content)
    session.commit()
    got = notebook_stats.answer(question, session)
    assert got is None or got.kind != "mention-count", (question, got)
