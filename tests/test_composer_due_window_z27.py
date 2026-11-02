"""Audit 1030 Z27: "what's due soon" said two weeks and "coming up" seven
days, over different items (3, 5 and 3 for one meaning). One default window,
today to two weeks on, and one reader of the items, whatever the phrasing.

The audit-1030 notebook (`tests/_seed_1030.py`), fixed clock Friday 30
October 2026.
"""

from __future__ import annotations

import pytest

from tessellate.ai import composer_plan
from tests import _seed_1030 as seed

AHEAD = ["31 October", "1 November", "4 November", "6 November", "10 November"]
BEYOND = ["14 November", "15 November", "20 November"]
BARE = ["what's due soon", "what is due soon", "coming up", "what's coming up", "anything due soon",
        "what's on my plate"]


@pytest.fixture
def ask(client, session, monkeypatch):
    seed.seed(session)
    go = seed.asker(client, monkeypatch)
    return lambda q: go(q)[0]


@pytest.mark.parametrize("question", BARE)
def test_one_window_and_one_set_for_every_phrasing(ask, question):
    said = ask(question)
    assert composer_plan.AHEAD_SAID in said, said
    for day in AHEAD:
        assert day in said, (day, said)
    for day in BEYOND:
        assert day not in said, (day, said)


def test_the_default_window_is_two_weeks_from_today():
    from datetime import date

    assert composer_plan.ahead_default(date(2026, 10, 30)) == (date(2026, 10, 30), date(2026, 11, 12), "the next two weeks")
