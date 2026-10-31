"""Planning the week spreads open tasks by note over the days left (audit 1030
Z57): "A way to spread them over the lighter days: Friday: milk, eggs, oat
milk, tomatoes, Renew passport, ..." put ten items on one day and split a
shopping list across days.

The class, by five phrasings on the audit-1030 notebook (fixed clock: Friday
30 October 2026, so "this week" is Friday to Sunday):

- a note's open items stay together on one day (a shopping list is one trip);
- with two or more notes and two or more days, they go on different days, and
  only then is it called a spread;
- "Busiest day ... with 1" is not said (one item is not busy);
- the opening line's second sentence starts with a capital.
"""

from __future__ import annotations

import re

import pytest

import tests._seed_1030 as seed_1030

QUESTIONS = ["plan my week", "help me plan my week", "what should I do this weekend",
             "spread these over the week", "how should I spread my tasks this week"]
TITLES = ("Shopping list", "Todo this week", "Lisbon packing list")


@pytest.fixture
def ask(client, session, monkeypatch):
    seed_1030.seed(session)
    go = seed_1030.asker(client, monkeypatch)
    return lambda q: go(q)[0]


def _spread(text: str) -> str:
    line = next((p for p in text.split("\n\n") if p.startswith(("A way to spread", "One way to spread")) or " is the lightest day" in p), "")
    assert line, text
    return line


@pytest.mark.parametrize("question", QUESTIONS)
def test_a_notes_tasks_stay_together_on_one_day(ask, question):
    line = _spread(ask(question))
    days = dict(re.findall(r"(Friday|Saturday|Sunday|Monday|Tuesday|Wednesday|Thursday|Today|Tomorrow): ([^;]+)", line))
    for title in TITLES:
        assert sum(title in held for held in days.values()) == 1, line
    for item in ("milk", "eggs", "tomatoes", "Renew passport", "charger"):
        assert item not in line, line
    assert len(days) >= 2 and len(days) == len(set(days)), line


@pytest.mark.parametrize("question", QUESTIONS)
def test_one_item_is_not_a_busy_day_and_the_opening_is_cased(ask, question):
    text = ask(question)
    assert not re.search(r"Busiest day: [^.]+ with 1\.", text), text
    first = text.split("\n", 1)[0]
    assert not re.search(r"[.!?] [a-z]", first), first
