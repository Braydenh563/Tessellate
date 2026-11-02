"""Five classes the third composer agent left open (composer4-1031, the
owner's INBOX 1357: fix the class, each tested several ways, on a fixed clock).

1. A bare total ("what is my total time") asks what it is the total of, never
   adds every duration in the notebook together; with a subject it is a sum.
2. "Show me all of my university notes", "pull up my uni notes": the notes on
   a subject said whole (the overview), not links to pick from or one fact.
3. A comparative is said of two, a superlative of three or more (or when the
   question asked with one): "is cheaper", "is the cheapest".
4. A count at one end of the order, with a subject ("my 2 latest baking notes",
   "my first two baking notes", "the 3 oldest notes"): that many, in that order.
5. A side's name at the start of a heading loses its "the".

Fixed clock: Friday 30 October 2026 (`tests/_seed_1030.py`).
"""

from __future__ import annotations

import re

import pytest

import tests._seed_1030 as seed_1030
from tessellate.ai import composer, composer_versus, note_recency
from tessellate.entry import manager
from tests.test_composer_class_1031 import uni  # noqa: F401  (a fixture)


@pytest.fixture
def ask(client, session, monkeypatch):
    seed_1030.seed(session)
    go = seed_1030.asker(client, monkeypatch)
    return lambda q: go(q)[0]


@pytest.fixture
def ask_three_trips(client, session, monkeypatch):
    seed_1030.seed(session)
    entry = manager.create_entry(session, "# Porto trip\nWeekend in Porto in January 2027. Budget $900 all in.", tags=["travel"])
    entry.created_at = entry.updated_at = seed_1030.NOW.replace(hour=10, minute=0)
    session.commit()
    go = seed_1030.asker(client, monkeypatch)
    return lambda q: go(q)[0]


def _lead(said: str) -> str:
    return said.split("\n")[0]


# 1. A bare total asks what it is the total of.

@pytest.mark.parametrize("question", [
    "what is my total time", "what is the total time", "what's my total time", "total time", "my total time",
    "how much time in total", "how long in total", "how long altogether",
])
def test_a_bare_total_time_asks_what_it_is_for(ask, question):
    said = ask(question)
    assert re.match(r"Total time of what\?", said), said
    assert "85" not in said and "days:" not in said, said
    assert "Spanish" in said and "my total time on" in said, said


@pytest.mark.parametrize("question", ["what is my total distance", "total distance", "what's my total weight"])
def test_a_bare_total_of_another_measure_is_not_asked_about(ask, question):
    # Only a time is asked about: unlike durations are the ones that mislead
    # (tests/test_composer_measures_1030.py keeps a distance summing every note).
    assert not re.match(r"Total (?:distance|weight) of what\?", ask(question))


@pytest.mark.parametrize("question", [
    "what is my total time on baking", "what is my total time spent on baking", "how long did I spend on baking",
    "how much time did I spend on baking", "my total time on baking",
])
def test_a_total_with_a_subject_is_that_sum(ask, question):
    said = ask(question)
    assert re.search(r"Your notes record 25\.25 hours on baking: Sourdough loaf", said), said
    assert "spent on" not in said.split(":")[0], said


# 2. The notes on a subject, said whole.

@pytest.mark.parametrize("question", [
    "show me all of my university notes", "show me all my university notes", "pull up my uni notes", "bring up my uni notes",
    "pull up all of my university notes",
])
def test_a_show_ask_on_a_subject_is_the_overview(ask, question):
    said = ask(question)
    assert re.search(r"\b(?:three|four) notes (?:about|on) (?:uni|university)\b", said), said
    assert "Pick one" not in said and "only note" not in said and "bring up" not in said and "pull up" not in said, said


@pytest.mark.parametrize("question", ["pull up my uni notes", "bring up my uni notes", "pull up all of my university notes", "get my university notes"])
def test_the_same_in_a_notebook_filed_under_university(uni, question):  # noqa: F811
    said = uni(question)
    assert re.search(r"\bten notes (?:about|on) (?:uni|university)\b", said), said
    assert "Pick one" not in said, said


def test_opening_a_note_by_name_still_points_at_it(ask):
    said = ask("open my cloud computing note")
    assert "Cloud computing" in said and "three notes about" not in said, said


# 3. Comparative of two, superlative of three or more.

@pytest.mark.parametrize("question", ["which trip is cheaper", "which of my trips is cheaper", "which is cheaper, Lisbon or Tokyo"])
def test_two_sides_are_a_comparative(ask, question):
    lead = _lead(ask(question))
    assert " is cheaper:" in lead and "cheapest" not in lead, lead


@pytest.mark.parametrize("question", ["which is the cheapest trip", "which trip is the cheapest", "which of my trips is the cheapest", "which is the cheapest of my trips"])
def test_a_superlative_asked_of_two_is_said_as_one(ask, question):
    lead = _lead(ask(question))
    assert "is the cheapest:" in lead and "Lisbon" in lead.split("is the cheapest")[0], lead


@pytest.mark.parametrize("question", [
    "which is the cheapest trip", "which trip is the cheapest", "which trip is cheaper", "which of my trips is cheaper",
])
def test_three_sides_are_a_superlative(ask_three_trips, question):
    lead = _lead(ask_three_trips(question))
    assert "Lisbon trip" in lead.split("is the cheapest")[0] and "is the cheapest:" in lead, lead
    assert lead.count("$") == 3 and "$420" in lead and "$3,000" in lead, lead


@pytest.mark.parametrize("question", ["which is the most expensive trip", "which trip is the most expensive", "which trip is more expensive"])
def test_the_dearest_of_three_costs_the_most(ask_three_trips, question):
    lead = _lead(ask_three_trips(question))
    assert re.search(r"Tokyo trip.* costs the most: \$3,000", lead), lead


@pytest.mark.parametrize("question", ["which baking note is newer", "which baking note is the newest", "which is the newest baking note"])
def test_three_notes_by_age_are_the_newest(ask, question):
    lead = _lead(ask(question))
    assert "Sourdough loaf" in lead.split("is the newest")[0] and "is the newest:" in lead, lead


@pytest.mark.parametrize("question", ["which baking note is older", "which baking note is the oldest"])
def test_three_notes_by_age_are_the_oldest(ask, question):
    lead = _lead(ask(question))
    assert "Sourdough starter" in lead.split("is the oldest")[0] and "is the oldest:" in lead, lead


@pytest.mark.parametrize("question", ["which trip is the last", "which trip is the latest", "which trip is the furthest away"])
def test_the_last_of_two_comes_last(ask, question):
    assert " comes last:" in _lead(ask(question))


def test_the_word_asked_and_the_count_say_the_right_key():
    rows = [object(), object(), object()]
    two = composer_versus._versus("is_cheaper", [composer_versus.Row(None, i, "", None) for i in (1, 2)])  # noqa: SLF001
    three = composer_versus._versus("is_cheaper", [composer_versus.Row(None, i, "", None) for i in (1, 2, 3)])  # noqa: SLF001
    assert (two.key, three.key) == ("is_cheaper", "is_cheapest") and len(rows) == 3


# 4. A count at one end of the order.

@pytest.mark.parametrize("question", [
    "what are my 2 latest baking notes", "show my 2 newest baking notes", "my latest 2 baking notes", "give me the 2 most recent baking notes",
    "list my 2 newest notes about baking", "my last two baking notes",
])
def test_a_count_of_the_latest_on_a_subject(ask, question):
    said = ask(question)
    assert said.startswith("Your two newest notes about baking:"), said
    rows = [line for line in said.split("\n") if line.startswith("- ")]
    assert len(rows) == 2 and "Sourdough loaf, 12 October" in rows[0] and "Banana bread, 5 October" in rows[1], said


@pytest.mark.parametrize("question", [
    "my 2 oldest baking notes", "what are my two earliest baking notes", "my first 2 baking notes", "show me my first two baking notes",
])
def test_a_count_of_the_oldest_on_a_subject(ask, question):
    said = ask(question)
    assert said.startswith("Your two oldest notes about baking:"), said
    rows = [line for line in said.split("\n") if line.startswith("- ")]
    assert len(rows) == 2 and "Sourdough starter, 30 September" in rows[0] and "Banana bread, 5 October" in rows[1], said


def test_more_than_there_are_says_so(ask):
    said = ask("show my 9 newest baking notes")
    assert said.startswith("Your three newest notes about baking:") and "That is all there are on that." in said, said


def test_one_latest_note_on_a_subject(ask):
    said = ask("what is my 1 latest baking note")
    assert "Sourdough loaf" in said and "Banana bread" not in said, said


def test_the_oldest_notes_of_the_notebook(ask):
    said = ask("my 3 oldest notes")
    assert said.startswith("Your three oldest notes:"), said
    assert "Apartment, 31 August" in said, said


@pytest.mark.parametrize("question", ["what is the latest note about baking", "which is the oldest baking note", "notes from last week", "what are my notes"])
def test_a_ranking_or_an_uncounted_ask_is_not_a_counted_list(ask, question):
    assert not ask(question).startswith(("Your two", "Your three", "Your five")), question


@pytest.mark.parametrize(("text", "count", "subject", "oldest"), [
    ("what are my 2 latest baking notes", 2, "baking", False),
    ("my latest 3 baking notes", 3, "baking", False),
    ("the three oldest notes about Atlas", 3, "atlas", True),
    ("my first 2 notes on running", 2, "running", True),
    ("give me the 4 most recent running notes", 4, "running", False),
])
def test_the_reader_finds_the_count_the_end_and_the_subject(text, count, subject, oldest):
    found = note_recency.recency(text)
    assert (found.count, found.subject, found.oldest, found.said_count) == (count, subject, oldest, True), text


@pytest.mark.parametrize("text", ["what was the first thing I wrote", "my last week", "notes from the last 2 weeks", "which note was written first about baking"])
def test_the_reader_leaves_other_asks_alone(text):
    found = note_recency.recency(text)
    assert found is None or not found.oldest or text.startswith("which"), text


# 5. A side's name at the start of a heading.

@pytest.mark.parametrize(("label", "said"), [
    ("the dentist", "dentist"), ("the Lisbon trip", "Lisbon trip"), ("The Overstory", "Overstory"), ("my gym notes", "gym notes"),
    ("our flat", "flat"), ("a trip", "trip"), ("Lisbon", "Lisbon"), ("theatre", "theatre"), ("the", "the"),
])
def test_heading_name_drops_a_leading_article(label, said):
    assert composer.heading_name(label) == said


@pytest.mark.parametrize("question", [
    "compare the dentist and the Lisbon trip", "the dentist versus the Lisbon trip", "what is the difference between the dentist and the Lisbon trip",
    "compare the dentist with the Lisbon trip",
])
def test_a_comparison_heads_each_side_without_its_the(ask, question):
    said = ask(question)
    heads = [line for line in said.split("\n") if re.fullmatch(r"\*\*[^*]+\*\*", line)]
    assert heads and all(not re.match(r"\*\*(?:the|The) ", h) for h in heads), said
    assert any("Lisbon trip" in h for h in heads) and any("dentist" in h.lower() for h in heads), said
    #: Mid-sentence the article stays.
    assert "mentions the dentist" in said, said
