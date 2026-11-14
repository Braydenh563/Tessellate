"""L-chat-234, the open tails of the quantity engine: a difference between two doings ("how much more did I walk than
run") is two sums and a subtraction over the same notes, citing both; a goal that names its own doing ("Run a 10k")
is counted in that doing, not in every distance written."""

from __future__ import annotations

import pytest

from tests.test_composer_quantity_1030 import RUNS, WALKS, ask  # noqa: F401


@pytest.mark.parametrize("question", ["how much more did I walk than run", "how much more have I walked than run"])
def test_the_difference_between_two_doings(ask, question):  # noqa: F811
    said = ask(question, WALKS + RUNS)
    assert said.startswith("You walked 21.5 km more than you ran."), said
    assert "30 km walked" in said and "8.5 km run" in said and "Walking log" in said and "Running log" in said, said


def test_the_other_way_round_says_less(ask):  # noqa: F811
    said = ask("how much less did I run than walk", WALKS + RUNS)
    assert said.startswith("You ran 21.5 km less than you walked."), said


def test_a_goal_names_its_own_doing(ask):  # noqa: F811
    said = ask("how close am I to my 10k goal", WALKS + RUNS)
    assert said.startswith("You are 1.5 km short of your 10 km goal."), said
