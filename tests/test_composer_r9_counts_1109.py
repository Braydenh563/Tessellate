"""R9-10 (composer audit round 9): a superlative over a table row, a count of the lines that say a doing, a
distance on a named day, and a yearly total are worked out, not dumped. Seed: `tests/_seed_r9_1109.py`."""

from __future__ import annotations

import pytest

import tests._seed_r9_1109 as sd


@pytest.fixture
def say(client, session, monkeypatch):
    sd.seed(session)
    go = sd.asker(client, monkeypatch)
    return lambda q: go(q)[0]


def test_the_cheapest_builder_is_the_smallest_quote(say):
    text = say("which builder was cheapest")
    assert text.startswith("Marek, at £7,200")
    assert "BuildRight £9,100" in text and "Kowalski & Sons £8,400" in text


@pytest.mark.parametrize(("question", "lead"), [
    ("how many runs have I logged", "You ran twice"),
    ("how many quotes did I get", "Three quotes"),
    ("how many books do I want to read", "Three books"),
])
def test_a_count_of_what_the_lines_list(say, question, lead):
    assert say(question).startswith(lead)


def test_how_far_on_a_named_day_is_that_days_run(say):
    text = say("how far did I run on 8 November")
    assert text.startswith("12 km") and "10 km" not in text


def test_what_i_spend_on_insurance_adds_the_yearly_amounts(say):
    text = say("what do I spend on insurance")
    assert "£592" in text and "£412" in text and "£180" in text
