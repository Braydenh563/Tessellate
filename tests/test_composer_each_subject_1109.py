"""Two things asked about at once are answered one at a time (composer-r6 E10):
"what do I know about Tom and Sara" was one pooled search that dropped Tom. It is
read as the comparison's sides, so the answer is a block per subject, and each
subject is searched on its own. Seed: `tests/_seed_1031c.py`."""

from __future__ import annotations

import pytest

import tests._seed_1031c as seed_c
from tessellate.ai import composer_ask


@pytest.fixture
def go(client, session, monkeypatch):
    seed_c.seed(session)
    return seed_c.asker(client, monkeypatch)


@pytest.mark.parametrize("said, sides", [
    ("what do I know about Tom and Sara", ("Tom", "Sara")),
    ("what do I know about tom and sara", ("tom", "sara")),
    ("tell me about Tom and Sara", ("Tom", "Sara")),
    ("what have I written about Tom and Sara", ("Tom", "Sara")),
    ("what do my notes say about Tom and Sara", ("Tom", "Sara")),
    ("anything about Lisbon and Tokyo", ("Lisbon", "Tokyo")),
    ("what do I know about Tom, Sara and Anna", ("Tom", "Sara", "Anna")),
    ("Tom and Sara", ("Tom", "Sara")),
])
def test_two_subjects_are_two_sides(said, sides):
    assert composer_ask.compare_sides(said) == sides
    assert composer_ask.classify(said) == "compare"


@pytest.mark.parametrize("said", [
    "what do I know about the trip and what to pack", "what do I know about Tom", "salt and pepper", "what do I know about my trip and I",
])
def test_one_subject_or_a_clause_is_not_split(said):
    assert composer_ask.compare_sides(said) is None


@pytest.mark.parametrize("said", ["what do I know about Tom and Sara", "tell me about Tom and Sara", "what do my notes say about Tom and Sara"])
def test_the_answer_has_a_block_for_each(go, said):
    text, _ = go(said)
    assert "**Tom**" in text and "**Sara**" in text, text
    assert "conference in June" in text and "Sara is your sister" in text, text


def test_a_second_subject_the_notes_never_name_is_said(go):
    text, _ = go("what do I know about Anna and José")
    assert "José" in text and "Anna" in text, text
