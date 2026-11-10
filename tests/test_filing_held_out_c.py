"""The third filing fixture, a gate for any later vocabulary change (Q29,
owner 2026-11-11).

`tests/fixtures/filing/notes_c.json` is 60 notes, five in each of the twelve
categories of `notes.json`, all five kinds, nine marked sensitive. It is
frozen: it was written before the related-topic table was measured and was
not read for a word. Rule for a new word or a table row: it must be general
English, owned by one topic, and must not appear in any fixture note. Never
read this set's failures to choose a word; if a change loses a note here,
the change is wrong, or the floor moves with the reason said in the commit.

Scored with no model against the notebook `notes.json` builds, as
`notes_b.json` is in `test_everyday_vocabulary.py`. Floors are the numbers
measured when it was frozen: 38 of 60 filed right, 5 wrong, 49 right by
suggestion (0.817), the same wrong count with the related-topic table and
without it.
"""

from __future__ import annotations

import json
from pathlib import Path

from tessellate.ai import lexical_filing
from tests.test_filing_accuracy import _seed

NOTES_C = json.loads((Path(__file__).parent / "fixtures" / "filing" / "notes_c.json").read_text(encoding="utf-8"))
#: Measured at freeze: filed right, filed wrong, right by suggestion.
FLOOR_FILED_RIGHT = 38
FLOOR_SUGGESTED = 49
CEILING_WRONG = 5


def test_the_fixture_is_60_notes_five_per_category() -> None:
    assert len(NOTES_C) == 60
    counts = {c: sum(1 for n in NOTES_C if n["category"] == c) for c in {n["category"] for n in NOTES_C}}
    assert len(counts) == 12 and set(counts.values()) == {5}
    assert {n["kind"] for n in NOTES_C} == {"line", "pasted", "joke", "caption", "list"}
    assert sum(1 for n in NOTES_C if n.get("sensitive")) >= 6


def test_the_held_out_set_keeps_its_floors(session) -> None:
    _seed(session)
    right = wrong = suggested = 0
    for note in NOTES_C:
        decision = lexical_filing.decide(session, note["content"])
        filed = decision.filed.name if decision.filed else None
        pick = filed or (decision.ranked[0].name if decision.held and decision.ranked else None)
        right += filed == note["category"]
        wrong += filed is not None and filed != note["category"]
        suggested += pick == note["category"]
    assert right >= FLOOR_FILED_RIGHT, right
    assert suggested >= FLOOR_SUGGESTED, suggested
    assert wrong <= CEILING_WRONG, wrong
