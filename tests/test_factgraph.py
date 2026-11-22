"""The fact layer (CHAT_PLAN Phase 6 step 1, decision 30): the exact facts of
ten notes of the Phase 6 seed, the modes, the dates read against the note's
own day, and the cache by revision.

Topic facts are left out of the exact lists: they are the taxonomy map's vote
(`ai/taxonomy.py`), which Brief 39b replaces; one test below holds their
shape.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from tessellate.ai import factgraph

SEED = json.loads((Path(__file__).parent / "fixtures" / "composer" / "phase6_seed.json").read_text(encoding="utf-8"))
NOTES = {n["id"]: n for n in SEED["notes"]}

#: (kind, text, mode, first day of `when`), in text order, read by hand
#: against each note: the date a note's "on Monday" means is the Monday on or
#: before the day it was written; "for the 21st" and "next week" look ahead.
EXPECTED = {
    1: [
        ("event", 'went to the gym', "asserted", "2026-09-28"),
        ("date", 'on Monday', "asserted", "2026-09-28"),
        ("event", 'did squats', "asserted", "2026-09-28"),
        ("count", '5 sets', "asserted", "2026-09-28"),
        ("quantity", '80 kg', "asserted", "2026-09-28"),
        ("preference", 'I like the morning sessions best', "asserted", "2026-10-04"),
    ],
    2: [
        ("plan", 'plan to go three times a week', "asserted", "2026-09-27"),
        ("count", 'three times', "asserted", "2026-09-27"),
        ("event", 'Decided to go', "asserted", "2026-09-27"),
        ("decision", 'Decided to go with the strength programme', "asserted", "2026-09-27"),
    ],
    3: [
        ("event", 'played golf', "asserted", "2026-09-05"),
        ("entity", 'Lakeside', "asserted", "2026-09-05"),
        ("event", 'Shot 94', "asserted", "2026-09-05"),
    ],
    6: [
        ("entity", 'Golf', "asserted", "2026-09-27"),
        ("date", 'on Sunday morning', "asserted", "2026-09-27"),
        ("event", 'am going again next week', "asserted", "2026-10-05"),
        ("date", 'next week', "asserted", "2026-10-05"),
    ],
    7: [
        ("entity", 'Harbor', "asserted", "2026-10-14"),
        ("date", 'on the 14th of next month', "asserted", "2026-10-14"),
        ("money", '$1,200', "asserted", "2026-09-06"),
    ],
    9: [
        ("event", 'booked', "asserted", "2026-10-21"),
        ("date", 'the 21st', "asserted", "2026-10-21"),
    ],
    10: [
        ("entity", 'Sam', "asserted", "2026-10-02"),
        ("event", 'met', "asserted", "2026-10-02"),
        ("date", 'on Friday', "asserted", "2026-10-02"),
    ],
    12: [
        ("check_item", 'Milk', "asserted", "2026-10-01"),
        ("check_item", 'Rice', "asserted", "2026-10-01"),
        ("check_item", 'Eggs', "asserted", "2026-10-01"),
        ("check_item", 'Coffee', "asserted", "2026-10-01"),
    ],
    13: [
        ("entity", 'Sam', "asserted", "2026-09-30"),
        ("event", 'wrote', "asserted", "2026-09-30"),
        ("quote", 'I am not sure we should ship it.', "quoted", "2026-09-30"),
        ("event", 'moved', "asserted", "2026-09-30"),
    ],
    18: [
        ("event", 'ran 5 km', "asserted", "2026-10-03"),
        ("quantity", '5 km', "asserted", "2026-10-03"),
        ("date", 'on Saturday', "asserted", "2026-10-03"),
        ("duration", '28 minutes', "asserted", "2026-10-03"),
    ],
}


@pytest.mark.parametrize("note_id", sorted(EXPECTED))
def test_the_exact_facts_of_ten_seed_notes(note_id):
    got = [(f.kind, f.text, f.mode, f.when[0].isoformat()) for f in factgraph.facts(NOTES[note_id]) if f.kind != "topic"]
    assert got == EXPECTED[note_id]


@pytest.mark.parametrize("note_id", sorted(NOTES))
def test_every_fact_is_its_own_span_of_the_note(note_id):
    content = NOTES[note_id]["content"]
    for f in factgraph.facts(NOTES[note_id]):
        assert content[f.start:f.end] == f.text, f
        assert f.kind in factgraph.KINDS and f.mode in factgraph.MODES


def _one(content: str, kind: str, created: str = "2026-10-06"):
    facts = factgraph.of_kind({"id": 1, "content": content, "created_at": created}, kind)
    assert facts, (content, kind)
    return facts[0]


@pytest.mark.parametrize(
    ("content", "kind", "mode"),
    [
        ("# N\n\nI did not finish the report.", "event", "negated"),
        ("# N\n\nMaybe we should move the launch.", "plan", "hypothetical"),
        ("# N\n\nIf it rains we will cancel the hike.", "event", "conditional"),
        ("# N\n\nShould we ship on Friday?", "question", "question"),
        ("# N\n\nPriya said: \"we booked the venue\".", "quote", "quoted"),
        ("# N\n\nI booked the venue.", "event", "asserted"),
    ],
)
def test_the_assertion_mode(content, kind, mode):
    assert _one(content, kind).mode == mode


def test_nothing_the_person_did_is_read_from_someone_elses_words():
    facts = factgraph.facts({"id": 1, "content": "# N\n\nPriya said: \"we booked the venue and decided to go with Lisbon\".", "created_at": "2026-10-06"})
    assert not [f for f in facts if f.kind in ("event", "decision", "plan", "preference") and "venue" in f.text]


@pytest.mark.parametrize(
    ("content", "kind", "attrs"),
    [
        ("# N\n\nThe flat costs €950 a month.", "money", {"value": 950, "currency": "EUR"}),
        ("# N\n\nThe quote was 2,400 dollars.", "money", {"value": 2400, "currency": "USD"}),
        ("# N\n\nRested for 90 minutes after.", "duration", {"seconds": 5400}),
        ("# N\n\nRead it at https://example.com/a for the details.", "link", {"target": "https://example.com/a"}),
        ("# N\n\nSee [[Gym plan]] for the split.", "link", {"target": "Gym plan"}),
        ("# N\n\nI need to call the plumber about the boiler.", "plan", {"object": "call the plumber about the boiler"}),
        ("# N\n\n- Passport\n- Charger", "list_item", {"index": 0}),
        ("# N\n\nI hate early meetings.", "preference", {"polarity": -1}),
        ("# N\n\nI don't like the new layout.", "preference", {"polarity": -1}),
        ("# N\n\nWe settled on the blue tiles.", "decision", {"choice": "the blue tiles"}),
        ("# N\n\nWe drove 300 miles to the coast.", "quantity", {"value": 300, "unit": "miles"}),
    ],
)
def test_each_kind_and_its_attributes(content, kind, attrs):
    fact = _one(content, kind)
    assert {k: fact.attrs.get(k) for k in attrs} == attrs, fact


def test_a_sentence_with_no_time_word_inherits_the_note_day_and_says_so():
    plain = _one("# N\n\nI booked the venue.", "event", "2026-09-30")
    dated = _one("# N\n\nI booked the venue on Monday.", "event", "2026-09-30")
    assert plain.inherited and plain.when == (plain.when[0], plain.when[0], "day") and plain.when[0].isoformat() == "2026-09-30"
    assert not dated.inherited and dated.when[0].isoformat() == "2026-09-28"


def test_three_times_a_week_is_how_often_not_how_long():
    assert not factgraph.of_kind(NOTES[2], "duration")


def test_a_joke_setup_is_not_a_question_on_the_list():
    note = {"id": 1, "content": "# Jokes\n\nA joke for Sam. Why did the scarecrow win a prize? Because he was outstanding.", "created_at": "2026-10-06"}
    assert not factgraph.of_kind(note, "question")


def test_topics_come_from_the_taxonomy_map():
    fact = _one("# N\n\nLeg day at the gym, squats and deadlifts.", "topic")
    assert "Fitness" in fact.attrs["labels"]


def test_the_cache_is_by_revision():
    note = {"id": 77, "content": "# N\n\nI booked the venue.", "created_at": "2026-10-06", "entry_edited_at": "2026-10-06T10:00"}
    first = factgraph.facts(note)
    assert factgraph.facts(dict(note)) is first
    edited = {**note, "content": "# N\n\nI cancelled the venue.", "entry_edited_at": "2026-10-06T11:00"}
    assert factgraph.facts(edited) is not first
    assert factgraph.of_kind(edited, "event")[0].attrs["lemma"] == "cancel"


def test_twenty_notes_are_read_in_under_fifty_milliseconds():
    #: The patterns compile once per process (`core/lazyre.py`), on the first
    #: note read: about 100 ms on a loaded machine when this test runs first.
    #: That is start-up, not reading, so it is paid before the clock starts.
    factgraph.facts(SEED["notes"][0])
    factgraph._CACHE.clear()
    started = time.perf_counter()
    for note in SEED["notes"]:
        factgraph.facts(note)
    assert time.perf_counter() - started < 0.05
