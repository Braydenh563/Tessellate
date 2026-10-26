"""Composer classes, fifth pass (the leftovers of round 4): a list of notes by
date leaves archived notes out like every count does, a month with "last
year", "this year" or "next year" is that month of that year, and a note whose
first line is a label ("Blockers: none.") is listed by its title or by its
date, never by the label. Each class is at least four phrasings the owner did
not report; the fix is to the class (`ai/recognise.py` for every date word,
`search_manager.entries_between` for the archived rule, `ai/composer.py` for
the listing name). The clock is Wednesday 21 October 2026, 10:00. No model
runs."""

from __future__ import annotations

import datetime as dt
import re

import pytest

from tests.test_composer_classes_1026c import _asker
from tests.test_composer_classes_1357 import NOT_FOUND
from tessellate.entry import manager

D = dt.datetime

#: (content, category, written, extra entry fields)
EXTRA = [
    ("# Old standup\n\nStuck on the review.", "Personal", D(2026, 9, 26, 9), {"archived_at": D(2026, 10, 2, 9)}),
    ("# Stale idea\n\nA scrapped plan for the shed.", "Personal", D(2026, 10, 14, 9), {"archived_at": D(2026, 10, 15, 9)}),
    ("# Fresh idea\n\nA kept plan for the shed.", "Personal", D(2026, 10, 15, 9), {}),
    ("# Standup\n\nThe build was quiet.", "Personal", D(2026, 9, 29, 9), {}),
    ("# Blossom walk\n\nThe park was pink.", "Hobbies", D(2026, 3, 14, 10), {}),
    ("# Midsummer\n\nA bonfire by the lake.", "Hobbies", D(2025, 6, 21, 21), {}),
    ("# Frost\n\nThe first frost of the year.", "Personal", D(2025, 11, 9, 8), {}),
    ("Blockers: none.", "Personal", D(2025, 11, 4, 9), {}),
    ("Mood: fine.", "Personal", D(2025, 11, 18, 9), {}),
    ("Status: done", "Personal", D(2026, 10, 16, 9), {}),
    ("# Scope\n\nBlockers: none.", "Personal", D(2026, 10, 17, 9), {}),
]


@pytest.fixture
def ask(client, session, monkeypatch):
    said = _asker(client, session, monkeypatch, False)
    for text, category, when, extra in EXTRA:
        entry = manager.create_entry(session, text, category)
        entry.created_at = entry.updated_at = when
        for key, value in extra.items():
            setattr(entry, key, value)
    session.commit()
    return said


_SEP = (r"(?=.*Standup)", r"Old standup")
_LAST_WEEK = (r"(?=.*Fresh idea)", r"Stale idea")
#: Class A, a list by date leaves archived notes out, as a count does.
#: (question, must, never)
A_ARCHIVED = [
    ("notes from 24 to 30 September", *_SEP),
    ("what did I write from 24 to 30 September", *_SEP),
    ("notes from September 24 to 30", *_SEP),
    ("what did I write between the 24th and the 30th of September", *_SEP),
    ("show me notes from 24-30 September", *_SEP),
    ("what did I write last week", *_LAST_WEEK),
    ("notes from last week", *_LAST_WEEK),
    ("show me what I wrote last week", *_LAST_WEEK),
    ("what did I jot down last week", *_LAST_WEEK),
    ("list my notes from last week", *_LAST_WEEK),
]
#: Asked for, an archived note comes back. (question, must, never)
A_ASKED = [
    ("archived notes from 24 to 30 September", r"Old standup", NOT_FOUND),
    ("what archived notes did I write from 24 to 30 September", r"Old standup", NOT_FOUND),
    ("archived notes from last week", r"Stale idea", NOT_FOUND),
    ("what archived notes did I write last week", r"Stale idea", NOT_FOUND),
]

def _check(said: str, must: str, never: str | None, q: str, cls: str) -> None:
    ok = bool(re.search(must, said, re.I | re.S)) and not (never and re.search(never, said, re.I | re.S))
    assert ok, f"[{cls}] {q!r} -> {said[:600]!r}"


@pytest.mark.parametrize("q,must,never", A_ARCHIVED, ids=[r[0] for r in A_ARCHIVED])
def test_a_list_by_date_leaves_archived_notes_out(ask, q, must, never):
    _check(ask(q), must, never + "|" + NOT_FOUND, q, "A")


@pytest.mark.parametrize("q,must,never", A_ASKED, ids=[r[0] for r in A_ASKED])
def test_a_list_by_date_keeps_archived_notes_when_asked(ask, q, must, never):
    _check(ask(q), must, never, q, "A")
