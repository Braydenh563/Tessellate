"""Composer classes, sixth pass (the date-phrase class): a day, a season, a part
of a month or year, or a range, said with "last year", "this year" or "next
year", and every one of them after "since", "before", "until" or "after".
Round 5 gave a month a year word; its siblings had none. One table of phrasings
(the owner's eight and their kin) is read three ways: by `recognise.span` (the
first and last day), by `find` and `without_windows` (one whole phrase, no date
word left behind for the subject), and by a question to the composer (a list
and a count over a small notebook). The fix is to the reader in
`ai/recognise.py`, so every surface that reads a date gets it.

The clock is Wednesday 21 October 2026, 10:00. A season is meteorological and
northern (winter is December to February and is named for the year it starts
in); the hemisphere is an open owner decision, not changed here. No model
runs."""

from __future__ import annotations

import datetime as dt
import re

import pytest

from tessellate.ai import recognise as rec
from tessellate.entry import manager
from tests.test_composer_classes_1026c import _asker
from tests.test_composer_classes_1357 import NOT_FOUND

D = dt.datetime
d = dt.date
TODAY = d(2026, 10, 21)
#: "Before X" and "until X" begin where the notebook could: no note is older.
EPOCH = d(1970, 1, 1)

#: (phrase, first day, last day). Read against TODAY as a note about the past.
READ_DAY_YEAR = [
    ("20 March this year", d(2026, 3, 20), d(2026, 3, 20)),
    ("20th of March last year", d(2025, 3, 20), d(2025, 3, 20)),
    ("the 20th of March this year", d(2026, 3, 20), d(2026, 3, 20)),
    ("march 20th last year", d(2025, 3, 20), d(2025, 3, 20)),
    ("March 20 last year", d(2025, 3, 20), d(2025, 3, 20)),
    ("March the 20th of last year", d(2025, 3, 20), d(2025, 3, 20)),
    ("1 May of last year", d(2025, 5, 1), d(2025, 5, 1)),
    ("20 March next year", d(2027, 3, 20), d(2027, 3, 20)),
    ("on 20 March last year", d(2025, 3, 20), d(2025, 3, 20)),
    ("the 3rd of next month", d(2026, 11, 3), d(2026, 11, 3)),
    ("the 3rd of last month", d(2026, 9, 3), d(2026, 9, 3)),
    ("next month on the 3rd", d(2026, 11, 3), d(2026, 11, 3)),
]
READ_SEASON_YEAR = [
    ("last summer", d(2026, 6, 1), d(2026, 8, 31)),
    ("this spring", d(2026, 3, 1), d(2026, 5, 31)),
    ("last winter", d(2025, 12, 1), d(2026, 2, 28)),
    ("last autumn", d(2025, 9, 1), d(2025, 11, 30)),
    ("summer last year", d(2025, 6, 1), d(2025, 8, 31)),
    ("spring this year", d(2026, 3, 1), d(2026, 5, 31)),
    ("autumn next year", d(2027, 9, 1), d(2027, 11, 30)),
    ("fall last year", d(2025, 9, 1), d(2025, 11, 30)),
    ("winter last year", d(2025, 12, 1), d(2026, 2, 28)),
    ("winter this year", d(2026, 12, 1), d(2027, 2, 28)),
    ("the summer of last year", d(2025, 6, 1), d(2025, 8, 31)),
    ("in summer of last year", d(2025, 6, 1), d(2025, 8, 31)),
    ("summer of 2025", d(2025, 6, 1), d(2025, 8, 31)),
    ("the winter of 2025", d(2025, 12, 1), d(2026, 2, 28)),
]
READ_PART_YEAR = [
    ("early March last year", d(2025, 3, 1), d(2025, 3, 10)),
    ("mid June last year", d(2025, 6, 15), d(2025, 6, 15)),
    ("late May this year", d(2026, 5, 21), d(2026, 5, 31)),
    ("end of March last year", d(2025, 3, 31), d(2025, 3, 31)),
    ("early March of last year", d(2025, 3, 1), d(2025, 3, 10)),
    ("early March 2025", d(2025, 3, 1), d(2025, 3, 10)),
    ("early next year", d(2027, 1, 1), d(2027, 4, 30)),
    ("early this year", d(2026, 1, 1), d(2026, 4, 30)),
    ("mid last year", d(2025, 5, 1), d(2025, 8, 31)),
    ("late last year", d(2025, 9, 1), d(2025, 12, 31)),
    ("end of last year", d(2025, 12, 31), d(2025, 12, 31)),
    ("early 2025", d(2025, 1, 1), d(2025, 4, 30)),
    ("early next month", d(2026, 11, 1), d(2026, 11, 10)),
    ("mid next month", d(2026, 11, 15), d(2026, 11, 15)),
    ("late last month", d(2026, 9, 21), d(2026, 9, 30)),
    ("end of last month", d(2026, 9, 30), d(2026, 9, 30)),
    ("the first week of March last year", d(2025, 3, 1), d(2025, 3, 7)),
    ("the last week of May last year", d(2025, 5, 25), d(2025, 5, 31)),
    ("the second half of June this year", d(2026, 6, 16), d(2026, 6, 30)),
    ("the first half of last year", d(2025, 1, 1), d(2025, 6, 30)),
    ("the second half of this year", d(2026, 7, 1), d(2026, 12, 31)),
    ("the last week of last year", d(2025, 12, 25), d(2025, 12, 31)),
]
READ_RANGE_YEAR = [
    ("1-10 March last year", d(2025, 3, 1), d(2025, 3, 10)),
    ("from 1 to 10 March this year", d(2026, 3, 1), d(2026, 3, 10)),
    ("between 1 and 10 March this year", d(2026, 3, 1), d(2026, 3, 10)),
    ("March 1-10 this year", d(2026, 3, 1), d(2026, 3, 10)),
    ("March 1 to 10 last year", d(2025, 3, 1), d(2025, 3, 10)),
    ("between the 3rd and the 9th of May last year", d(2025, 5, 3), d(2025, 5, 9)),
    ("from 1 March to 10 April this year", d(2026, 3, 1), d(2026, 4, 10)),
    ("between 1 March and 10 April last year", d(2025, 3, 1), d(2025, 4, 10)),
    ("between March 3 and April 9 last year", d(2025, 3, 3), d(2025, 4, 9)),
    ("from 1 March to 10 April 2025", d(2025, 3, 1), d(2025, 4, 10)),
    ("from March to May last year", d(2025, 3, 1), d(2025, 5, 31)),
    ("between March and May this year", d(2026, 3, 1), d(2026, 5, 31)),
    ("from November to February", d(2025, 11, 1), d(2026, 2, 28)),
]
READ_EDGES = [
    ("since last spring", d(2026, 3, 1), TODAY),
    ("since spring last year", d(2025, 3, 1), TODAY),
    ("since last summer", d(2026, 6, 1), TODAY),
    ("since summer this year", d(2026, 6, 1), TODAY),
    ("since March last year", d(2025, 3, 1), TODAY),
    ("since 20 March last year", d(2025, 3, 20), TODAY),
    ("since March 20th last year", d(2025, 3, 20), TODAY),
    ("since early March this year", d(2026, 3, 1), TODAY),
    ("since the first week of March last year", d(2025, 3, 1), TODAY),
    ("since the 3rd of last month", d(2026, 9, 3), TODAY),
    ("before March last year", EPOCH, d(2025, 2, 28)),
    ("before 20 March last year", EPOCH, d(2025, 3, 19)),
    ("before last summer", EPOCH, d(2026, 5, 31)),
    ("before the summer of last year", EPOCH, d(2025, 5, 31)),
    ("before early March last year", EPOCH, d(2025, 2, 28)),
    ("until June this year", EPOCH, d(2026, 6, 30)),
    ("until 20 March this year", EPOCH, d(2026, 3, 20)),
    ("until last spring", EPOCH, d(2026, 5, 31)),
    ("till the end of March last year", EPOCH, d(2025, 3, 31)),
    ("after March last year", d(2025, 4, 1), TODAY),
    ("after 20 March this year", d(2026, 3, 21), TODAY),
    ("after last summer", d(2026, 9, 1), TODAY),
    ("after summer last year", d(2025, 9, 1), TODAY),
]
READ_ALL = READ_DAY_YEAR + READ_SEASON_YEAR + READ_PART_YEAR + READ_RANGE_YEAR + READ_EDGES

#: Words a window leaves behind when the reader took only part of it.
_LEFT = re.compile(
    r"\b(?:year|month|january|february|march|april|may|june|july|august|september|october|november|december|"
    r"spring|summer|autumn|fall|winter|early|late|mid|since|before|until|till|after|between|half|week|\d+)\b", re.I
)


@pytest.mark.parametrize("phrase,first,last", READ_ALL, ids=[r[0] for r in READ_ALL])
def test_span_reads_the_phrase(phrase, first, last):
    got = rec.span(phrase, TODAY, "past")
    assert got is not None and (got[0], got[1]) == (first, last), f"{phrase!r} -> {got}"


@pytest.mark.parametrize("phrase", [r[0] for r in READ_ALL if r[0] != "from November to February"], ids=[r[0] for r in READ_ALL if r[0] != "from November to February"])
def test_find_takes_the_whole_phrase_once(phrase):
    """One phrase, not a month and a stray "last year": the composer reads the first."""
    found = rec.find("what did I write " + phrase)
    assert len(found) == 1, f"{phrase!r} -> {[f[2] for f in found]}"
    assert found[0][2].lower().endswith(phrase.lower()) or phrase.lower().startswith("on ") and found[0][2].lower() == phrase.lower()[3:], found


@pytest.mark.parametrize("phrase", [r[0] for r in READ_ALL], ids=[r[0] for r in READ_ALL])
def test_without_windows_leaves_no_date_word(phrase):
    """The subject is read from what is left: a stray "last year" would be one."""
    left = rec.without_windows("notes from " + phrase)
    assert not _LEFT.search(left.replace("notes from", "")), f"{phrase!r} -> {left!r}"


#: A small notebook over the base one (its clock, `_asker`). Written dates are
#: the point: a window is right when exactly its notes come back.
EXTRA = [
    ("# Old ledger\n\nClosed the year-end books.", "Personal", D(2024, 11, 2, 9)),
    ("# Early tulips\n\nThe first shoots by the gate.", "Hobbies", D(2025, 3, 6, 9)),
    ("# Seed order\n\nSweet peas and beans.", "Hobbies", D(2025, 3, 20, 9)),
    ("# Tulip day\n\nThe whole border was out.", "Hobbies", D(2025, 3, 26, 9)),
    ("# Lent plans\n\nGive up biscuits.", "Personal", D(2025, 4, 12, 9)),
    ("# Solstice picnic\n\nStrawberries on the hill.", "Hobbies", D(2025, 6, 21, 13)),
    ("# Autumn leaves\n\nRaked the front path.", "Hobbies", D(2025, 10, 12, 9)),
    ("# Frost walk\n\nThe canal had iced over.", "Hobbies", D(2025, 12, 20, 9)),
]


@pytest.fixture
def ask(client, session, monkeypatch):
    said = _asker(client, session, monkeypatch, False)
    for text, category, when in EXTRA:
        entry = manager.create_entry(session, text, category)
        entry.created_at = entry.updated_at = when
    session.commit()
    return said


def _t(*names: str) -> str:
    return "".join(f"(?=.*{n})" for n in names)


#: Notes by window: the 2025 notes are Old ledger (Nov 2024), Early tulips,
#: Seed order, Tulip day, Lent plans, Solstice picnic, Autumn leaves, Frost walk.
#: (question, must, never)
SURFACE_LISTS = [
    ("what did I write on 20 March last year", _t("Seed order"), "Early tulips|Tulip day|Spring clean|Taxes"),
    ("notes from March 20th last year", _t("Seed order"), "Early tulips|Tulip day|Spring clean|Taxes"),
    ("what did I write on the 20th of March this year", _t("Spring clean"), "Taxes|Seed order"),
    ("notes from 20 March this year", _t("Spring clean"), "Taxes|Seed order"),
    ("what did I write summer last year", _t("Solstice picnic"), "Beach day|Autumn leaves|Early tulips"),
    ("notes from the summer of last year", _t("Solstice picnic"), "Beach day|Autumn leaves"),
    ("what did I write in summer this year", _t("Beach day"), "Solstice picnic"),
    ("what did I write autumn last year", _t("Autumn leaves"), "Solstice picnic|Frost walk"),
    ("what did I write in the winter of 2025", _t("Frost walk", "New year plans", "Ski trip", "Snow day"), "Autumn leaves|Seed order"),
    ("notes from winter last year", _t("Frost walk", "Ski trip"), "Autumn leaves|Seed order"),
    ("what did I write in early March last year", _t("Early tulips"), "Seed order|Tulip day"),
    ("what did I write in late March last year", _t("Tulip day"), "Early tulips|Seed order"),
    ("notes from the first week of March last year", _t("Early tulips"), "Seed order|Tulip day"),
    ("what did I write in the second half of March last year", _t("Seed order", "Tulip day"), "Early tulips"),
    ("notes from the first half of last year", _t("Seed order", "Solstice picnic"), "Autumn leaves|Frost walk|Old ledger"),
    ("what did I write in the second half of last year", _t("Autumn leaves", "Frost walk"), "Solstice picnic|Seed order"),
    ("notes from 1 to 10 March this year", _t("Taxes"), "Spring clean|Early tulips"),
    ("what did I write between 1 and 10 March last year", _t("Early tulips"), "Seed order|Taxes"),
    ("notes from 1-10 March last year", _t("Early tulips"), "Seed order|Taxes"),
    ("what did I write from 1 March to 10 April last year", _t("Early tulips", "Seed order", "Tulip day"), "Lent plans|Solstice picnic"),
    ("notes from March to April last year", _t("Early tulips", "Lent plans"), "Solstice picnic|Old ledger"),
    ("what did I write since last spring", _t("Spring clean", "Beach day"), "Seed order|Solstice picnic|Autumn leaves|Frost walk"),
    ("notes since March last year", _t("Seed order", "Solstice picnic", "Spring clean"), "Old ledger"),
    ("what did I write since 20 March last year", _t("Seed order", "Tulip day"), "Early tulips|Old ledger"),
    ("what did I write before March last year", _t("Old ledger"), "Early tulips|Seed order|Spring clean"),
    ("notes until May last year", _t("Old ledger", "Early tulips", "Lent plans"), "Solstice picnic|Spring clean"),
    ("notes from after summer last year", _t("Autumn leaves", "Frost walk"), "Solstice picnic|Old ledger"),
]
#: A window still ahead holds no note yet: said as that, no other window's notes.
_AHEAD = (r"nothing|no notes|none|not yet|haven't|yet to", r"Old ledger|Early tulips|Seed order|Solstice|Autumn leaves|Frost walk|Spring clean|Taxes|is not in anything")
SURFACE_AHEAD = [
    ("what did I write early next year", *_AHEAD),
    ("what did I write in winter this year", *_AHEAD),
    ("notes from 20 March next year", *_AHEAD),
]
SURFACE_COUNTS = [
    ("how many notes did I write on 20 March last year", r"\b1 note\b"),
    ("how many notes did I write on 20 March this year", r"\b1 note\b"),
    ("how many notes did I write summer last year", r"\b1 note\b"),
    ("how many notes did I write in early March last year", r"\b1 note\b"),
    ("how many notes did I write between 1 and 10 March last year", r"\b1 note\b"),
    ("how many notes did I write from 1 March to 10 April last year", r"\b3 notes\b"),
    ("how many notes did I write in the second half of March last year", r"\b2 notes\b"),
    ("how many notes did I write before March last year", r"\b1 note\b"),
]


def _check(said: str, must: str, never: str | None, q: str) -> None:
    ok = bool(re.search(must, said, re.I | re.S)) and not (never and re.search(never, said, re.I | re.S))
    assert ok, f"{q!r} -> {said[:600]!r}"


@pytest.mark.parametrize("q,must,never", SURFACE_LISTS, ids=[r[0] for r in SURFACE_LISTS])
def test_a_list_by_a_dated_phrase(ask, q, must, never):
    _check(ask(q), must, never + "|" + NOT_FOUND, q)


@pytest.mark.parametrize("q,must,never", SURFACE_AHEAD, ids=[r[0] for r in SURFACE_AHEAD])
def test_a_window_still_ahead_is_said_empty(ask, q, must, never):
    _check(ask(q), must, never, q)


@pytest.mark.parametrize("q,must", SURFACE_COUNTS, ids=[r[0] for r in SURFACE_COUNTS])
def test_a_count_by_a_dated_phrase(ask, q, must):
    _check(ask(q), must, NOT_FOUND, q)
