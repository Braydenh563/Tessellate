"""A "cheaper" or "sooner" comparison leads with the two figures or days
(audit 1030 Z58, composer-1031), also with no sides named ("which trip is
sooner") and for the oldest or newest note on a subject, with the days.

Several phrasings of each, on the audit-1030 notebook (fixed clock: Friday
30 October 2026, `tests/_seed_1030.py`).
"""

from __future__ import annotations

import pytest

import tests._seed_1030 as seed_1030


@pytest.fixture
def ask(client, session, monkeypatch):
    seed_1030.seed(session)
    go = seed_1030.asker(client, monkeypatch)
    return lambda q: go(q)[0]


def _lead(said: str) -> str:
    return said.split("\n")[0]


@pytest.mark.parametrize("question", [
    "which is cheaper, Lisbon or Tokyo", "Lisbon or Tokyo, which is cheaper", "is Lisbon cheaper than Tokyo",
    "which is cheaper: Lisbon or Tokyo?", "which is the cheaper, Lisbon or Tokyo",
])
def test_cheaper_leads_with_both_figures(ask, question):
    lead = _lead(ask(question))
    assert "$420" in lead and "$3,000" in lead, lead
    assert lead.index("$420") < lead.index("$3,000"), lead
    assert "cheaper" in lead and lead.index("Lisbon") < lead.index("Tokyo"), lead


@pytest.mark.parametrize("question", ["which is more expensive, Lisbon or Tokyo", "which is pricier, Lisbon or Tokyo",
                                      "is Tokyo pricier than Lisbon"])
def test_dearer_leads_with_the_dearer_one(ask, question):
    lead = _lead(ask(question))
    assert lead.index("Tokyo") < lead.index("Lisbon") and "$3,000" in lead and "$420" in lead, lead


@pytest.mark.parametrize("question", [
    "which is sooner, the dentist or the Lisbon trip", "the dentist or the Lisbon trip, which is sooner",
    "which comes first, the dentist or the Lisbon trip", "which is earlier, the dentist or the Lisbon trip",
])
def test_sooner_leads_with_both_days(ask, question):
    lead = _lead(ask(question))
    assert "4 November" in lead and "14 November" in lead, lead
    assert lead.index("Dentist") < lead.index("Lisbon"), lead


@pytest.mark.parametrize("question", [
    "which trip is sooner", "which of my trips is sooner", "which trip comes first", "which trip is earlier",
    "which trip is next",
])
def test_which_trip_is_sooner_names_the_sides_itself(ask, question):
    lead = _lead(ask(question))
    assert "Lisbon trip" in lead and "Tokyo trip" in lead and "14 November" in lead and "April 2027" in lead, lead
    assert lead.index("Lisbon trip") < lead.index("Tokyo trip"), lead


@pytest.mark.parametrize("question", ["which trip is later", "which trip is further away", "which trip is the last"])
def test_which_trip_is_later(ask, question):
    lead = _lead(ask(question))
    assert lead.index("Tokyo trip") < lead.index("Lisbon trip") and "April 2027" in lead, lead


@pytest.mark.parametrize("question", [
    "which note is the oldest about baking", "which is the oldest baking note", "what is my oldest baking note",
    "which baking note is the oldest", "which note was written first about baking",
])
def test_the_oldest_note_on_a_subject_comes_with_the_days(ask, question):
    lead = _lead(ask(question))
    assert "Sourdough starter" in lead and "oldest" in lead, lead
    assert lead.index("30 September") < lead.index("5 October") < lead.index("12 October"), lead


@pytest.mark.parametrize("question", [
    "which note is the newest about baking", "which is the most recent baking note", "what is my newest baking note",
    "what is my latest note about baking",
])
def test_the_newest_note_on_a_subject_comes_with_the_days(ask, question):
    lead = _lead(ask(question))
    assert "Sourdough loaf" in lead and "newest" in lead, lead
    assert lead.index("12 October") < lead.index("5 October") < lead.index("30 September"), lead


def test_a_comparison_with_no_figure_still_counts_both_sides(ask):
    said = ask("which is cheaper, Sara or Tom")
    assert "$" not in _lead(said), said
    assert "Sara" in said and "Tom" in said


def test_a_question_that_names_no_subject_is_left_to_the_note_order_reader(ask):
    said = ask("what is my oldest note")
    assert " against " not in said, said
