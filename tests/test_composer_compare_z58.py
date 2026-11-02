"""A comparison sets like against like (audit 1030 Z58): "Lisbon vs Tokyo"
compared the Lisbon packing list's checklist with the Tokyo trip. When a side
has several notes named for it, the one of the other side's kind is read
("Lisbon trip" against "Tokyo trip"); "Lisbon or Tokyo, which is cheaper" is
a comparison too, asked the other way round.

Phrasings on the audit-1030 notebook (fixed clock: Friday 30 October 2026).
"""

from __future__ import annotations

import pytest

import tests._seed_1030 as seed_1030
from tessellate.ai import composer


@pytest.fixture
def ask(client, session, monkeypatch):
    seed_1030.seed(session)
    go = seed_1030.asker(client, monkeypatch)
    return lambda q: go(q)[0]


@pytest.mark.parametrize("question", ["Lisbon vs Tokyo", "compare Lisbon and Tokyo", "which is cheaper, Lisbon or Tokyo",
                                      "Lisbon or Tokyo, which is cheaper", "differences between Lisbon and Tokyo"])
def test_each_side_is_its_trip(ask, question):
    said = ask(question)
    assert "[**Lisbon trip**]" in said and "[**Tokyo trip**]" in said, said
    assert "Lisbon packing list" not in said and "Passport" not in said, said


@pytest.mark.parametrize("question", ["Lisbon or Tokyo, which is cheaper", "lisbon or tokyo which one is bigger?",
                                      "Porto or Lisbon, which was better"])
def test_which_asked_last_names_both_sides(question):
    assert composer.compare_sides(question) is not None


@pytest.mark.parametrize("question", ["running log vs running plan", "compare the running log and the running plan"])
def test_a_side_named_whole_keeps_its_note(ask, question):
    said = ask(question)
    assert "[**Running log**]" in said and "[**Running plan**]" in said, said
