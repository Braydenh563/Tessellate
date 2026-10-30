"""Composer audit 2026-10-30, class 5 (Z29): a sum of named things, or of a
named note, is added and said once, whatever the phrasing."""

from __future__ import annotations

import pytest

from tests import _seed_1030 as seed_1030


@pytest.fixture
def ask(client, session, monkeypatch):
    seed_1030.seed(session)
    return seed_1030.asker(client, monkeypatch)


@pytest.mark.parametrize("question", [
    "sum of rent and groceries", "how much is rent plus groceries", "add up rent and groceries", "how much is rent and groceries together",
])
def test_z29_named_things_are_added(ask, question):
    said = ask(question)[0]
    assert "$1,280" in said.split("\n")[0], said
    assert "periods differ" in said, said
    assert "not mentioned" not in said and "None of these notes" not in said, said


@pytest.mark.parametrize("question", ["what's the total of my budget", "add up the budget", "total of the budget"])
def test_z29_a_named_note_adds_every_amount_it_holds(ask, question):
    said = ask(question)[0].split("\n")[0]
    assert "$1,326.99" in said and "Budget" in said, said
    assert "$500" not in said, said


@pytest.mark.parametrize("question", ["total cost of the Lisbon trip", "sum of the Lisbon trip"])
def test_z29_a_note_with_one_amount_says_so(ask, question):
    said = ask(question)[0].split("\n")[0]
    assert "$420" in said and "one amount" in said, said


def test_z29_add_up_is_not_an_add_a_line_act(ask):
    assert "which note to add" not in ask("add up the budget")[0]


@pytest.mark.parametrize("question", ["how much money did I spend in October", "how much did I spend in October", "what did I spend this October"])
def test_z30_a_plan_is_not_money_spent(ask, question):
    said = ask(question)[0].split("\n")[0]
    assert "$147" in said and "$420" not in said and "$567" not in said, said
    assert "Bought a new jacket for $129 at Uniqlo $129" not in said, said


@pytest.mark.parametrize("question", ["how much did I pay for the flights", "how much did I spend on the flights"])
def test_z30_a_priced_plan_is_said_as_a_price(ask, question):
    said = ask(question)[0].split("\n")[0]
    assert "$420" in said and "paid yet" in said, said
    assert "for Flights cost" not in said, said


@pytest.mark.parametrize("question", ["how much did I spend on the jacket and the bulbs", "sum of the jacket and the bulbs"])
def test_z30_two_named_purchases_are_added(ask, question):
    assert "$147" in ask(question)[0].split("\n")[0]


@pytest.mark.parametrize("question", ["what's the biggest expense in my budget", "what's the largest amount in the budget"])
def test_z31_a_superlative_is_taken_inside_the_named_note(ask, question):
    said = ask(question)[0].split("\n")[0]
    assert "Rent, at $1,200" in said and "Budget" in said and "Flights cost," not in said, said


@pytest.mark.parametrize("question", ["what's the cheapest thing I bought", "what is my smallest bill"])
def test_z31_the_smallest_is_ranked_not_listed(ask, question):
    said = ask(question)[0].split("\n")[0]
    assert "$18" in said and "bulbs" in said, said


@pytest.mark.parametrize("question", ["what was my biggest purchase", "what's my most expensive purchase"])
def test_z31_the_biggest_purchase_is_the_jacket(ask, question):
    said = ask(question)[0].split("\n")[0]
    assert "$129" in said and "expensive" not in said.split(",")[0], said
    assert "“expensive”" not in ask(question)[0]


@pytest.mark.parametrize("question", ["how much does the hotel cost", "what does the hotel cost", "how much is the hotel"])
def test_z32_the_amount_nearest_the_asked_noun_leads(ask, question):
    said = ask(question)[0].split("\n")[0]
    assert "85 euros" in said and "$420" not in said, said


@pytest.mark.parametrize("question", ["how much are the flights", "how much do the flights cost"])
def test_z32_a_how_much_leads_with_the_price_not_a_date(ask, question):
    said = ask(question)[0].split("\n")[0]
    assert "$420" in said and "14 November" not in said, said
