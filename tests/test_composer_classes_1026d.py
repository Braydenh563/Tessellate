"""Composer classes, fourth pass (the leftovers of round 3): archived notes stay
out of every count, "how many work notes" with no tag or folder of that name
counts the notes that mention it, a day range inside one month, a season or
month with a year and no lead word, and a note that is one short label line
still listed by its date. Each class is at least four phrasings the owner did
not report; the fix is to the class (`ai/recognise.py` for every date word,
`ai/notebook_stats.py` and `ai/notebook_filters.py` for the counts,
`ai/composer.py` for the listing). The clock is Wednesday 21 October 2026,
10:00. No model runs."""

from __future__ import annotations

import datetime as dt
import re

import pytest

from tests.test_composer_classes_1026c import _asker
from tests.test_composer_classes_1357 import NOT_FOUND
from tessellate.core.database import Entry
from tessellate.entry import manager
from sqlalchemy import select

D = dt.datetime

#: (content, category, written, extra entry fields, tags)
EXTRA = [
    ("# Old standup\n\nStuck on work review.", "Personal", D(2026, 9, 26, 9), {"archived_at": D(2026, 10, 2, 9)}, ["work"]),
    ("Blockers: none.", "Personal", D(2025, 11, 4, 9), {}, []),
    ("# Daily check\n\nMood: fine.", "Personal", D(2025, 11, 18, 9), {}, []),
    ("# Surf lesson\n\nFirst wave stood up.", "Hobbies", D(2025, 7, 12, 10), {}, []),
    ("# Festival\n\nThe mud was deep.", "Hobbies", D(2025, 6, 20, 19), {}, []),
    ("# Camp week\n\nLearned to tie knots.", "Hobbies", D(2024, 8, 5, 9), {}, []),
    ("# Work week\n\nPlanning the week ahead.", "Misc", D(2026, 10, 1, 9), {}, []),
    ("# Meeting\n\nRemember to finish the work before Friday.", "Misc", D(2026, 10, 2, 9), {}, []),
    ("# Chores\n\nDo some work around the house.", "Misc", D(2026, 10, 3, 9), {}, []),
    ("# Homework\n\nMaths sheet, page four.", "Misc", D(2026, 10, 4, 9), {}, []),
    ("# Network map\n\nThe router sits by the door.", "Misc", D(2026, 10, 5, 9), {}, []),
]


def _extras(session, untagged: bool) -> None:  # noqa: ANN001
    for text, category, when, extra, tags in EXTRA:
        entry = manager.create_entry(session, text, category, tags=tags or None)
        entry.created_at = entry.updated_at = when
        for key, value in extra.items():
            setattr(entry, key, value)
    if untagged:
        for entry in session.scalars(select(Entry)):
            entry.tags = "[]"
    session.commit()


@pytest.fixture
def ask(client, session, monkeypatch):
    said = _asker(client, session, monkeypatch, False)
    _extras(session, False)
    return said


@pytest.fixture
def ask_untagged(client, session, monkeypatch):
    """The same notebook with no tag called work: only notes that say the word."""
    said = _asker(client, session, monkeypatch, False)
    _extras(session, True)
    return said


#: Live notes: the base 1026c notebook has 20 with its archived one, this
#: pass adds 11 of which 1 is archived: 29 not archived.
#: Class A, an archived note is in no count unless the question asks for
#: archived. (question, must)
A_TOTALS = [
    ("how many notes do I have", r"\b29 notes\b"),
    ("how many notes are there", r"\b29 notes\b"),
    ("what is the total number of notes", r"\b29 notes\b"),
    ("how many notes do I have in total", r"\b29 notes\b"),
    ("number of notes", r"\b29 notes\b"),
    ("count my notes", r"\b29 notes\b"),
    ("how many notes in September", r"\b3 notes\b"),
    ("how many notes did I write in September", r"\b3 notes\b"),
    ("number of notes written in September", r"\b3 notes\b"),
    ("how many notes from September", r"\b3 notes\b"),
    ("how many notes in Personal", r"\b12 notes in Personal"),
    ("how many personal notes", r"\b12 notes in Personal"),
    ("number of notes in Personal", r"\b12 notes in Personal"),
    ("how many notes are in Personal", r"\b12 notes in Personal"),
    ("how many work notes", r"\b2 notes are tagged work"),
    ("number of work notes", r"\b2 notes are tagged work"),
    ("count my work notes", r"\b2 notes are tagged work"),
    ("how many notes are tagged work", r"\b2 notes tagged work"),
    ("how many archived notes", r"\b2 archived notes"),
    ("how many archived notes do I have", r"\b2 archived notes"),
    ("how many notes are archived", r"\b2 archived notes"),
    ("number of archived notes", r"\b2 archived notes"),
]

#: Class B, a word before "notes" that is no tag and no folder: the notes that
#: say it, and the answer says so. (question, must)
B_MENTION = [
    ("how many work notes", r"\b3 notes mention work"),
    ("how many work notes do I have", r"\b3 notes mention work"),
    ("number of work notes", r"\b3 notes mention work"),
    ("count my work notes", r"\b3 notes mention work"),
    ("how many work notes are there", r"\b3 notes mention work"),
    ("how many zebra notes", r"none of your notes mention zebra"),
    ("how many quokka notes do I have", r"none of your notes mention quokka"),
    ("number of volcano notes", r"none of your notes mention volcano"),
    ("count my lantern notes", r"none of your notes mention lantern"),
]
#: A word that says what kind of notes, not what they say, stays a total.
B_NOT_A_WORD = [
    ("how many new notes", r"\b29 notes"),
    ("how many total notes", r"\b29 notes"),
    ("how many recent notes", r"\b29 notes"),
    ("how many old notes do I have", r"\b29 notes"),
    ("how many of my notes", r"\b29 notes"),
]

_SEP_END = (r"Standup notes", r"Packing list|Quarterly report|Gym routine|Errands")
_SEP_MID = (r"(?=.*Quarterly report)(?=.*Packing list)", r"Standup notes|Gym routine|Errands")
_MAY = (r"Pancakes", r"Pasta bake|Lentil curry|Gym routine|Errands")
#: Class C, a run of days inside one month, said six ways. (question, must, never)
C_DAY_RANGES = [
    ("notes from 24 to 30 September", *_SEP_END),
    ("what did I write from 24 to 30 September", *_SEP_END),
    ("notes from 24-30 September", *_SEP_END),
    ("what did I write between the 24th and the 30th of September", *_SEP_END),
    ("notes from September 24 to 30", *_SEP_END),
    ("anything I wrote from 24 to 30 Sept?", *_SEP_END),
    ("notes from 10 to 12 September", *_SEP_MID),
    ("what did I write 10-12 September", *_SEP_MID),
    ("notes between the 10th and the 12th of September", *_SEP_MID),
    ("what did I write from September 10 to 12", *_SEP_MID),
    ("notes between 10 and 12 September", *_SEP_MID),
    ("what did I write between the 3rd and the 9th of May", *_MAY),
    ("notes between 3 and 9 May", *_MAY),
    ("what did I write May 3 to 9", *_MAY),
    ("notes from the 3rd to the 9th of May", *_MAY),
    ("what did I write 3rd to 9th May", *_MAY),
]
C_DAY_RANGE_COUNTS = [
    ("how many notes did I write from 24 to 30 September", r"\b1 note\b"),
    ("how many notes from 24-30 September", r"\b1 note\b"),
    ("how many notes did I write between the 24th and the 30th of September", r"\b1 note\b"),
    ("number of notes September 24 to 30", r"\b1 note\b"),
    ("how many notes between 10 and 12 September", r"\b2 notes\b"),
    ("how many notes did I write between the 3rd and the 9th of May", r"\b1 note\b"),
]

_WINTER = (r"(?=.*Ski trip)(?=.*Snow day)(?=.*New year plans)", r"Gym routine|Lecture 5|Beach day|Hello|Spring clean")
_SUMMER_25 = (r"(?=.*Surf lesson)(?=.*Festival)", r"Camp week|Beach day|Hello|Gym routine|Ski trip")
_SUMMER_24 = (r"Camp week", r"Surf lesson|Festival|Beach day|Hello|Gym routine")
_SPRING_26 = (r"(?=.*Spring clean)(?=.*Taxes)(?=.*Pasta bake)(?=.*Pancakes)", r"Ski trip|Beach day|Gym routine|Lecture 5")
_MARCH_26 = (r"(?=.*Spring clean)(?=.*Taxes)", r"Ski trip|Beach day|Pasta bake|Gym routine")
_AUG_26 = (r"Beach day", r"Spring clean|Gym routine|Hello|Uni timetable")
#: Class D, a season or a month with a year and no lead word. (question, must, never)
D_YEAR = [
    ("winter 2025", *_WINTER),
    ("winter 2025 notes", *_WINTER),
    ("notes winter 2025", *_WINTER),
    ("what did I write winter 2025", *_WINTER),
    ("summer 2025", *_SUMMER_25),
    ("notes summer 2025", *_SUMMER_25),
    ("summer 2025 notes", *_SUMMER_25),
    ("summer 2024 notes", *_SUMMER_24),
    ("notes summer 2024", *_SUMMER_24),
    ("spring 2026 notes", *_SPRING_26),
    ("notes spring 2026", *_SPRING_26),
    ("March 2026 notes", *_MARCH_26),
    ("notes March 2026", *_MARCH_26),
    ("what did I write March 2026", *_MARCH_26),
    ("August 2026 notes", *_AUG_26),
    ("notes august 2026", *_AUG_26),
]
D_YEAR_COUNTS = [
    ("how many notes summer 2025", r"\b2 notes\b"),
    ("how many summer 2025 notes", r"\b2 notes\b"),
    ("how many notes did I write winter 2025", r"\b3 notes\b"),
    ("number of notes March 2026", r"\b2 notes\b"),
]
#: A season word with no year stays a subject ("winter tyres").
D_STILL_A_SUBJECT = [
    ("notes about winter tyres", r"winter tyres"),
    ("my summer reading list", r"summer reading"),
]

_LABELS = (r"(?=.*Blockers)(?=.*Daily check)", r"Gym routine|Lecture 5|Ski trip|Surf lesson|New year plans")
#: Class E, a note that is one short label line is listed by its date.
#: (question, must, never)
E_LABELS = [
    ("notes from November 2025", *_LABELS),
    ("what did I write in November 2025", *_LABELS),
    ("show me notes from November last year", *_LABELS),
    ("list my notes from November 2025", *_LABELS),
    ("what did I write in November last year", *_LABELS),
    ("what did I write on 4 November 2025", r"Blockers", r"Daily check|Gym routine"),
    ("notes from 4 November 2025", r"Blockers", r"Daily check|Gym routine"),
    ("what did I write on 18 November 2025", r"Daily check", r"Blockers|Gym routine"),
]
E_COUNTS = [
    ("how many notes did I write in November 2025", r"\b2 notes\b"),
    ("how many notes in November last year", r"\b2 notes\b"),
]


#: Classes still failing, each case a strict xfail until its fix lands (take
#: the letter out when the class passes).
OPEN: set[str] = {"C", "D", "E"}
#: Phrasings of an open class that already worked before its fix.
WORKED = {
    "notes between 10 and 12 September", "notes between 3 and 9 May", "what did I write May 3 to 9",
    "how many notes between 10 and 12 September", "how many notes did I write between the 3rd and the 9th of May",
    "how many notes did I write from 24 to 30 September", "how many notes did I write between the 24th and the 30th of September",
    "what did I write in November 2025", "how many notes did I write in November 2025", "how many notes in November last year",
}


def _cases(cls: str, rows: list):  # noqa: ANN202
    def mark(q: str) -> list:
        return [pytest.mark.xfail(strict=True, reason="open")] if cls in OPEN and q not in WORKED else []

    return [pytest.param(*row, id=row[0], marks=mark(row[0])) for row in rows]


def _check(said: str, must: str, never: str | None, q: str, cls: str) -> None:
    ok = bool(re.search(must, said, re.I | re.S)) and not (never and re.search(never, said, re.I | re.S))
    assert ok, f"[{cls}] {q!r} -> {said[:500]!r}"


@pytest.mark.parametrize("q,must", A_TOTALS, ids=[q for q, _ in A_TOTALS])
def test_archived_notes_are_in_no_count(ask, q, must):
    _check(ask(q), must, NOT_FOUND, q, "A")


@pytest.mark.parametrize("q,must", _cases("B", B_MENTION))
def test_a_word_that_is_no_tag_counts_the_notes_that_say_it(ask_untagged, q, must):
    said = ask_untagged(q)
    _check(said, must, NOT_FOUND + r"|You have \d", q, "B")


@pytest.mark.parametrize("q,must", _cases("A", B_NOT_A_WORD))
def test_a_kind_word_is_not_a_word_to_find(ask_untagged, q, must):
    _check(ask_untagged(q), must, r"mention", q, "B")


@pytest.mark.parametrize("q,must,never", _cases("C", C_DAY_RANGES))
def test_a_run_of_days_in_a_month(ask, q, must, never):
    _check(ask(q), must, never + "|" + NOT_FOUND, q, "C")


@pytest.mark.parametrize("q,must", _cases("C", C_DAY_RANGE_COUNTS))
def test_a_run_of_days_is_counted(ask, q, must):
    _check(ask(q), must, NOT_FOUND, q, "C")


@pytest.mark.parametrize("q,must,never", _cases("D", D_YEAR))
def test_a_season_or_month_with_a_year(ask, q, must, never):
    _check(ask(q), must, never + "|" + NOT_FOUND, q, "D")


@pytest.mark.parametrize("q,must", _cases("D", D_YEAR_COUNTS))
def test_a_season_or_month_with_a_year_is_counted(ask, q, must):
    _check(ask(q), must, NOT_FOUND, q, "D")


@pytest.mark.parametrize("q,word", D_STILL_A_SUBJECT, ids=[q for q, _ in D_STILL_A_SUBJECT])
def test_a_season_without_a_year_is_still_a_subject(ask, q, word):
    from tessellate.ai import recognise

    assert not recognise.find(q), q


@pytest.mark.parametrize("q,must,never", _cases("E", E_LABELS))
def test_a_label_line_note_is_listed_by_its_date(ask, q, must, never):
    _check(ask(q), must, never + "|" + NOT_FOUND, q, "E")


@pytest.mark.parametrize("q,must", _cases("E", E_COUNTS))
def test_a_label_line_note_is_counted(ask, q, must):
    _check(ask(q), must, NOT_FOUND, q, "E")
