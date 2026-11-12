"""The everyday vocabulary beside the pack (INBOX 1297, decision 8).

`memorymap_everyday.json` adds general words the pack's formal phrases miss
("boiler", "payslip", "parents evening") to the pack's own topics, merged in
`taxonomy._data()`. The pack file is never edited.

Measured with no model on `tests/fixtures/filing/notes.json` (120 notes,
leave one out) and on `notes_b.json`, 48 notes written before this file and
never used to choose a word in it, filed against the first set's notebook:

| | filed top-1 | filed wrong | suggested top-1 (sensitive notes included) |
| --- | --- | --- | --- |
| 120 notes, before | 0.417 | 15 | 0.533 |
| 120 notes, after | 0.617 | 11 | 0.792 |
| 48 held-out notes, before | 0.458 | 6 | not measured |
| 48 held-out notes, after | 0.667 | 3 | 0.833 |
| 60 frozen notes (`tests/test_filing_held_out_c.py`), Q29 | 0.633 | 5 | 0.817 |

The held-out set is the evidence: its notes were not read for a word, only
scored. The 120 are partly the evidence this was written beside. Words that
filed one of those wrong were taken out, not tuned around (essay, booked,
renewal, service, bulbs, stock)..
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tessellate.ai import lexical_filing, taxonomy
from tessellate.entry import manager
from tests.test_filing_accuracy import NOTES, _seed

DATA = Path(__file__).resolve().parents[1] / "src" / "tessellate" / "ai" / "data" / "taxonomy"
HELD_OUT = json.loads(
    (Path(__file__).parent / "fixtures" / "filing" / "notes_b.json").read_text(encoding="utf-8")
)
EXTRA = json.loads((DATA / "memorymap_everyday.json").read_text(encoding="utf-8"))


def test_every_topic_it_extends_is_a_pack_topic() -> None:
    pack = json.loads((DATA / "memorymap_taxonomy.json").read_text(encoding="utf-8"))["taxonomy"]
    assert set(EXTRA["terms"]) <= set(pack), set(EXTRA["terms"]) - set(pack)


def test_the_terms_are_clean_words_not_sentences() -> None:
    for topic, terms in EXTRA["terms"].items():
        assert terms == list(dict.fromkeys(terms)), f"{topic} repeats a term"
        for term in terms:
            assert term == term.strip().lower() and term, (topic, term)
            assert len(term.split()) <= 3, f"{topic}: {term!r} reads as a clause, not a phrase"
            assert len(term) <= 24, (topic, term)


def test_the_merge_reaches_the_matchers_and_leaves_the_pack_file_alone() -> None:
    assert "boiler" in taxonomy.taxonomy_map()["Home"]
    assert "boiler" in taxonomy.topic_hits("The boiler pressure dropped again")["Home"]
    pack = json.loads((DATA / "memorymap_taxonomy.json").read_text(encoding="utf-8"))
    assert "boiler" not in pack["taxonomy"]["Home"]


def test_a_weak_word_needs_company() -> None:
    assert set(EXTRA["weak"]) & {"season"}
    assert "Entertainment" not in taxonomy.strong_topics("Pumpkins are best in season")


def _held_out_score(session) -> tuple[int, int, int]:
    """(filed right, filed wrong, right when a held sensitive note's best guess counts)."""
    right = wrong = suggested = 0
    for note in HELD_OUT:
        decision = lexical_filing.decide(session, note["content"])
        filed = decision.filed.name if decision.filed else None
        pick = filed or (decision.ranked[0].name if decision.held and decision.ranked else None)
        right += filed == note["category"]
        wrong += filed is not None and filed != note["category"]
        suggested += pick == note["category"]
    return right, wrong, suggested


@pytest.mark.parametrize("held_out", [True])
def test_the_held_out_notes_keep_what_the_vocabulary_won(session, held_out) -> None:
    _seed(session)
    right, wrong, suggested = _held_out_score(session)
    assert right / len(HELD_OUT) >= 0.64, right
    assert wrong <= 4, wrong
    assert suggested / len(HELD_OUT) >= 0.8, suggested


def test_the_first_set_with_its_sensitive_notes_suggested(session) -> None:
    ids = _seed(session)
    suggested = 0
    for entry_id, note in zip(ids, NOTES):
        decision = lexical_filing.decide(session, note["content"], exclude_entry_id=entry_id)
        pick = decision.filed or (decision.ranked[0] if decision.held and decision.ranked else None)
        suggested += bool(pick) and pick.name == note["category"]
    assert suggested / len(NOTES) >= 0.77, suggested
    assert manager  # the fixture's notebook is real notes, filed by hand
