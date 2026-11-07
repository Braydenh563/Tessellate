"""Composer round 1, 2026-11-07, D1: the note a question names by its title
leads ("what is Project Atlas", "the Sara note", "show me the Dentist note",
"compare Gym and Gym plan"). Driven through the chat route with no model (fake
transport); the clock is `_seed_1031c.NOW`."""

from __future__ import annotations

import pytest

import tests._seed_1031c as seed_c
from tessellate.entry import manager

NOTES = (
    "# Project Atlas\n\nGroup project for cloud computing. Deadline 20 November. Priya does the slides, I do the report.",
    "# Meeting with Priya\n\nAgreed to split Project Atlas. Next meeting Friday 13 November at 10am.",
    "# Lisbon trip\n\nFlights cost $420 return, leaving 12 May. Staying at Hotel Alfama near the river. Day trip to Sintra on the Thursday.",
    "# Hotel Alfama\n\nBooking reference HA-77421. Late check-out requested. Breakfast included.",
    "# Sara\n\nSara is my sister. She lives in Leeds and works as a nurse. Her birthday is on 14 March.",
    "# Sara birthday ideas\n\nA jazz record, lilies, or tickets to the theatre. Do not buy perfume again.",
    "# Gift ideas\n\nTom wants a lens cap. Sara wants a jazz record for her birthday. Mum would like a scarf.",
    "Sara said she likes lilies and hates carnations",
    "# Dentist\n\nDr Patel at Kings Road practice. Phone 020 7946 0011. Next check-up Wednesday 11 November at 3pm.",
    "Dentist said to floss more and use the soft brush",
    "# Dentist bill\n\nPaid £85 for the check-up on 3 October.",
    "# Gym\n\nGym three times a week, Monday, Wednesday, Friday. Squat 80 kg, bench 60 kg.",
    "# Gym plan\n\nWarm up for ten minutes. Then squats, bench, rows. Cool down.",
)


def _id_of(heading: str) -> int:
    """The id the fixture gave the note whose first line is `heading` (ids run from 1 in a fresh notebook)."""
    return 1 + next(i for i, note in enumerate(NOTES) if note.split("\n", 1)[0] == heading)


@pytest.fixture
def go(client, session, monkeypatch):
    for content in NOTES:
        entry = manager.create_entry(session, content)
        entry.created_at = entry.updated_at = seed_c.NOW
    session.commit()
    return seed_c.asker(client, monkeypatch)


def test_d1_what_is_a_title_answers_from_the_note_with_that_title(go):
    said, _ = go("what is Project Atlas")
    assert "Group project for cloud computing" in said, said
    said, _ = go("what is Hotel Alfama")
    assert "HA-77421" in said or "Booking reference" in said, said


def test_d1_the_x_note_is_the_note_titled_x(go):
    said, _ = go("the Sara note")
    assert f"[**Sara**](#/notes/{_id_of('# Sara')})" in said and "notes about Sara" not in said, said


def test_d1_show_me_the_dentist_note_picks_the_titled_note(go):
    said, _ = go("show me the Dentist note")
    assert "Pick one" not in said, said
    #: The note titled Dentist, not "Dentist bill" or the loose "Dentist said ..." line.
    assert f"[**Dentist**](#/notes/{_id_of('# Dentist')})" in said, said


def test_d1_compare_names_both_sides(go):
    said, _ = go("compare Gym and Gym plan")
    assert "no mention" not in said.lower(), said
    assert "squat" in said.lower() and "warm up" in said.lower(), said


# --- Review 1: the title outranks the lines only for "what is X" ---------------------------

@pytest.mark.parametrize(("question", "names"), [("what is Project Atlas", True), ("what's the budget", True), ("who is Sara", True),
                                                 ("how much is rent", False), ("when is the beta", False), ("when did I last see the dentist", False)])
def test_review1_only_a_what_or_who_ask_ranks_a_titled_note_first(question, names):
    from tessellate.ai import composer_digest

    assert bool(composer_digest._NAMES_A_THING.match(question)) is names  # noqa: SLF001


@pytest.mark.parametrize("question", ["how much is rent", "what is the budget"])
def test_review1_every_also_item_starts_with_a_capital(client, session, monkeypatch, question):
    import tests._seed_1030 as seed_1030

    seed_1030.seed(session)
    said = seed_1030.asker(client, monkeypatch)(question)[0]
    line = next((x for x in said.splitlines() if x.startswith("**Also:**")), "")
    items = [x.strip() for x in line.removeprefix("**Also:**").split(";") if x.strip()]
    assert not line or all(x[:1].isupper() for x in items), said
