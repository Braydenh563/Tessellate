"""How often and how many times a person did a thing count the doings, not the
notes (audit 1030 Z23): "how often do I run" counted three notes filed under
running; "how many times did I run" quoted the plan ("Tuesday 5 km easy");
"how much did I run in October" did the same, not 19 km over three runs.

The class, by phrasings on the audit-1030 notebook (fixed clock: Friday 30
October 2026): a doing is a past line that names the verb, on its own day (a
log line "Ran 8 km on 17 October" in a note begun on 3 October is this
October's); a plan line is not one; distances are summed; a habit line with
its weekdays says how often when nothing is logged; "write about" still
counts notes.
"""

from __future__ import annotations

import pytest

import tests._seed_1030 as seed_1030
from tessellate.ai import composer_doings


@pytest.fixture
def ask(client, session, monkeypatch):
    seed_1030.seed(session)
    go = seed_1030.asker(client, monkeypatch)
    return lambda q: go(q)[0]


RUNS = "3 October (5 km), 17 October (8 km) and 25 October (6 km)"


@pytest.mark.parametrize("question", ["how many times did I run", "how many runs did I do", "how many times have I run?",
                                      "How often do I run", "how often did I run"])
def test_the_runs_are_counted_from_the_lines_that_say_them(ask, question):
    said = ask(question)
    assert said.startswith("You ran three times, on " + RUNS), said
    assert "Tuesday 5 km easy" not in said and "titled or tagged" not in said, said


@pytest.mark.parametrize("question", ["how often do I run", "how often did I run"])
def test_how_often_gives_the_gap(ask, question):
    assert "about every 11 days" in ask(question)


@pytest.mark.parametrize("question", ["how much did I run in October", "how much have I run this October", "how much did I run"])
def test_how_much_sums_the_distance(ask, question):
    said = ask(question)
    assert said.startswith("You ran 19 km in all"), said
    assert "over three days: " + RUNS in said, said


@pytest.mark.parametrize("question", ["how often do I go to the gym", "how often do I go to gym", "how often did I go to the gym"])
def test_a_habit_line_says_how_often(ask, question):
    assert ask(question).startswith("Three times a week: Monday, Wednesday and Friday, going by your Gym note."), ask(question)


@pytest.mark.parametrize("question", ["how often do I write about running", "how many times did I mention running"])
def test_writing_about_is_not_a_doing(question):
    assert composer_doings.asked(question) is None
