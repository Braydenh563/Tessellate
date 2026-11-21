"""L-chat-157 (F8): an answer does not parse a note it has already read.

Measured before (400 notes, the route's NOTE_LIMIT; `composer.compose`, no model):
400 `read_note` parses per answer, 40 ms of a 100 to 150 ms answer. After: the
second and later answers over an unchanged notebook parse 0 notes.
"""

from __future__ import annotations

import dataclasses
from datetime import date, datetime

from tessellate.ai import composer, composer_read

NOTES = [
    {"id": i, "created_at": f"2026-10-{1 + i % 28:02d}", "category": "Work", "tags": ["a"], "content": f"# Note {i}\n\nThe dentist is on Friday {i}. Plus costs $6 a month."}
    for i in range(1, 41)
]


def _ask(notes, question="when is the dentist"):
    return composer.compose(question, notes, today=date(2026, 11, 14), now=datetime(2026, 11, 14, 10))


def _count(monkeypatch) -> list[int]:
    seen: list[int] = []
    fresh = composer_read._read_note_fresh

    def counting(note, rank):
        seen.append(note["id"])
        return fresh(note, rank)

    monkeypatch.setattr(composer_read, "_read_note_fresh", counting)
    return seen


def test_an_unchanged_note_is_parsed_once_across_answers(monkeypatch):
    composer_read.forget_reads()
    seen = _count(monkeypatch)
    first = _ask(NOTES)["text"]
    parsed_first = len(seen)
    assert parsed_first == len(NOTES), parsed_first
    seen.clear()
    assert _ask(NOTES)["text"] == first
    assert seen == [], f"re-parsed {len(seen)} notes"


def test_an_edited_note_is_parsed_again_and_the_rest_are_not(monkeypatch):
    composer_read.forget_reads()
    _ask(NOTES)
    seen = _count(monkeypatch)
    edited = [dict(n, content=n["content"] + " Moved to Monday.") if n["id"] == 3 else n for n in NOTES]
    _ask(edited)
    assert seen == [3], seen


def test_a_cached_read_equals_a_fresh_one_and_is_not_shared(monkeypatch):
    composer_read.forget_reads()
    note = NOTES[0]
    fresh = composer_read._read_note_fresh(note, 4)
    composer_read.read_note(note, 0)
    again = composer_read.read_note(note, 4)
    assert dataclasses.asdict(again) == dataclasses.asdict(fresh)
    again.sentences[0].score = 99.0
    again.sentences[0].echoes.append("x")
    again.words.add("zzz")
    third = composer_read.read_note(note, 7)
    assert third.sentences[0].score == 0.0 and third.sentences[0].echoes == [] and "zzz" not in third.words
    assert {s.rank for s in third.sentences} == {7} and third.rank == 7


def test_the_view_keeps_the_callers_own_note_dict():
    composer_read.forget_reads()
    composer_read.read_note(NOTES[0], 0)
    mine = dict(NOTES[0], connected=True)
    assert composer_read.read_note(mine, 0).note is mine


def test_the_cache_is_bounded(monkeypatch):
    composer_read.forget_reads()
    for i in range(composer_read.READ_CACHE_MAX + 50):
        composer_read.read_note({"id": i + 1, "content": f"# T\n\nBody {i}."}, 0)
    assert composer_read.cached_reads() <= composer_read.READ_CACHE_MAX
