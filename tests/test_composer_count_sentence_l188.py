"""L188 (C6): the count sentence counts the notes the answer then says. Measured on the
207-note notebook (seed filler 150): the number in "You have N notes about X" equals the
number of distinct notes the answer cites, for every phrasing, so two answers never
disagree with themselves (the owner's "three notes" then eight)."""

from __future__ import annotations

import re

import pytest

from tests import _seed_1031c as seed_c

_NUMBERS = {w: n for n, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve".split())}


@pytest.fixture
def big(client, session, monkeypatch):
    seed_c.seed(session, filler=150)
    return seed_c.asker(client, monkeypatch)


def _cited(said, events) -> set[int]:
    grounded = {int(r["note_id"]) for e in events if e.get("type") == "grounding" for r in e.get("sentences") or [] if r.get("note_id") is not None}
    return grounded or {int(i) for i in re.findall(r"#/notes/(\d+)", said)}


@pytest.mark.parametrize(
    "question",
    [
        "what have I written about uni",
        "what about uni",
        "what do I know about cloud",
        "what do I know about the passport",
        "summarize my running notes",
    ],
)
def test_the_count_is_the_number_of_notes_the_answer_cites(big, question):
    said, events = big(question)
    first = said.split("\n", 1)[0]
    counted = re.search(r"\b(?:You have |Your notes on \w+: )?(\w+) notes?\b", first)
    assert counted, first
    word = counted.group(1).lower()
    n = _NUMBERS.get(word, int(word) if word.isdigit() else None)
    assert n is not None, first
    assert n == len(_cited(said, events)), (first, _cited(said, events))


# L156: "what else ... about X" lists what the matching notes say, as the plain ask does.
@pytest.mark.parametrize(
    ("question", "plain", "at_least"),
    [
        ("what else do I know about cloud", "what do I know about cloud", 5),
        ("what else is there about the passport", "what is there about the passport", 3),
        ("what else do my notes say about uni", "what do my notes say about uni", 4),
    ],
)
def test_what_else_lists_every_matching_note_not_one_fact(big, question, plain, at_least):
    said, events = big(question)
    assert len(_cited(said, events)) >= at_least, said
    assert "Also:" not in said, said
