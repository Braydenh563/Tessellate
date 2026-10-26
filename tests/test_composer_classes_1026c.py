"""Composer classes, third pass (INBOX 1026c): counts by state, counts by a tag
or folder word, seasons, a week or half of a named month, and a window phrase
said twice. Each class is five phrasings the owner did not report; the fix is
to the class (`ai/recognise.py` for every date word, `ai/notebook_stats.py` for
the counts). The clock is Wednesday 21 October 2026, 10:00. No model runs."""

from __future__ import annotations

import datetime as dt
import json
import re

import pytest

from tessellate.ai import notebook_stats
from tessellate.api import routes_chat
from tessellate.core import config
from tessellate.core.database import Document, Reminder, WhiteboardObject
from tessellate.entry import manager
from tests.test_composer_classes_1357 import DOCUMENTS, NOTES, NOT_FOUND, NOW, OBJECTS
from tests.test_composer_route_688 import _ask

D = dt.datetime

#: Marks on notes the base notebook already has: pinned titles.
PINNED = ("# Gym routine", "# Shakespeare essay")

#: (content, category, written, extra entry fields, tags)
MORE = [
    ("# Old receipts\n\nBin the 2025 receipts.", "Personal", D(2026, 9, 3, 9), {"archived_at": D(2026, 10, 1, 9)}, []),
    ("# Packing list\n\n- [ ] Passport\n- [ ] Charger\n- [x] Tickets", "Personal", D(2026, 9, 12, 9), {}, []),
    ("# Standup notes\n\nBlockers: none.", "Personal", D(2026, 9, 28, 9), {}, ["work"]),
    ("# Quarterly report\n\nNumbers due Friday.", "Personal", D(2026, 9, 10, 9), {}, ["work"]),
    ("# Pasta bake\n\nTomato, cheese, thirty minutes.", "Recipes", D(2026, 4, 2, 18), {}, []),
    ("# Lentil curry\n\nOnions first, then the spices.", "Recipes", D(2026, 4, 10, 18), {}, []),
    ("# Pancakes\n\nOne cup of flour per egg.", "Recipes", D(2026, 5, 3, 9), {}, []),
    ("# Ski trip\n\nThe lift queue was an hour.", "Personal", D(2026, 1, 15, 9), {}, []),
    ("# Snow day\n\nSchool shut, so we built a fort.", "Personal", D(2026, 2, 10, 9), {}, []),
    ("# New year plans\n\nLess sugar, more sleep.", "Personal", D(2025, 12, 31, 9), {}, []),
    ("# Beach day\n\nSunscreen twice, the water was cold.", "Hobbies", D(2026, 8, 9, 11), {}, []),
    ("# Spring clean\n\nGarage shelves first.", "Personal", D(2026, 3, 20, 9), {}, []),
    ("# Taxes\n\nGather the payslips.", "Personal", D(2026, 3, 5, 9), {}, []),
]
REMINDERS = [
    ("Pay the phone bill", D(2026, 10, 16, 9), True, D(2026, 10, 16, 10)),
    ("Hand in the essay", D(2026, 10, 30, 17), False, None),
    ("Call the dentist", D(2026, 10, 22, 9), False, None),
    ("Book the flights", D(2026, 11, 3, 9), False, None),
]


def _fill(session, work_folder: bool) -> None:
    for text, category, when, extra, tags in [(*n[:4], []) for n in NOTES] + MORE:
        if work_folder and tags == ["work"]:
            category, tags = "Work", []
        entry = manager.create_entry(session, text, category, tags=tags or None)
        entry.created_at = entry.updated_at = when
        entry.pinned = text.split("\n")[0] in PINNED
        for key, value in extra.items():
            setattr(entry, key, value)
        made: list = []
        for words, parent in OBJECTS.get(text, []):
            obj = WhiteboardObject(board_id=entry.id, kind="text", data=json.dumps({"content": words}),
                                   parent_id=made[parent].id if parent is not None else None)
            session.add(obj)
            session.flush()
            made.append(obj)
    for title, content, made_at, edited in DOCUMENTS:
        session.add(Document(title=title, content=content, created_at=made_at, updated_at=edited))
    for text, due, done, done_at in REMINDERS:
        session.add(Reminder(text=text, due_at=due, done=done, done_at=done_at, created_at=due - dt.timedelta(days=3)))
    session.commit()


def _asker(client, session, monkeypatch, work_folder: bool):  # noqa: ANN001, ANN202
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)
    monkeypatch.setattr(notebook_stats, "utcnow", lambda: NOW.replace(tzinfo=dt.timezone.utc))
    _fill(session, work_folder)
    return lambda q: _ask(client, q, notes_only=True, answer_from="notes", history=[])["text"]


@pytest.fixture
def ask(client, session, monkeypatch):
    return _asker(client, session, monkeypatch, False)


@pytest.fixture
def ask_folder(client, session, monkeypatch):
    """The same notebook, the two "work" notes filed in a folder named Work."""
    return _asker(client, session, monkeypatch, True)


#: Class S, a count by state: pinned, archived, checklists, open items,
#: reminders. (question, must)
S_STATE = [
    ("how many pinned notes", r"\b2 pinned notes"),
    ("how many pinned notes do I have", r"\b2 pinned notes"),
    ("how many notes are pinned", r"\b2 pinned notes"),
    ("number of pinned notes", r"\b2 pinned notes"),
    ("count my pinned notes", r"\b2 pinned notes"),
    ("how many archived notes", r"\b1 archived note\b"),
    ("how many archived notes do I have", r"\b1 archived note\b"),
    ("how many notes are archived", r"\b1 archived note\b"),
    ("number of archived notes", r"\b1 archived note\b"),
    ("how many checklists", r"\b2 checklists"),
    ("how many checklists do I have", r"\b2 checklists"),
    ("how many notes are checklists", r"\b2 checklists"),
    ("number of checklists", r"\b2 checklists"),
    ("how many open tasks", r"\b4 open (tasks|items)"),
    ("how many open tasks do I have", r"\b4 open (tasks|items)"),
    ("how many unticked items", r"\b4 (unticked|open) (items|tasks|boxes)"),
    ("how many unticked items are there", r"\b4 (unticked|open) (items|tasks|boxes)"),
    ("how many tasks are left to do", r"\b4 (unticked|open) (items|tasks|boxes)"),
    ("how many reminders do I have", r"\b3 (open |upcoming )?reminders"),
    ("how many reminders have I got", r"\b3 (open |upcoming )?reminders"),
    ("number of reminders", r"\b3 (open |upcoming )?reminders"),
    ("how many reminders this week", r"\b1 reminder\b"),
    ("how many reminders do I have this week", r"\b1 reminder\b"),
    ("how many reminders are due this week", r"\b1 reminder\b"),
    ("number of reminders this week", r"\b1 reminder\b"),
]

#: Class T, a count by a tag or folder word (tag work, folder Recipes).
T_WORD = [
    ("how many work notes", r"\b2 (notes (are )?tagged work|work notes)"),
    ("how many work notes do I have", r"\b2 (notes (are )?tagged work|work notes)"),
    ("number of work notes", r"\b2 (notes (are )?tagged work|work notes)"),
    ("count my work notes", r"\b2 (notes (are )?tagged work|work notes)"),
    ("how many notes in Recipes", r"\b3 notes in Recipes"),
    ("how many recipes notes do I have", r"\b3 notes in Recipes"),
    ("how many notes are in Recipes", r"\b3 notes in Recipes"),
    ("number of notes in Recipes", r"\b3 notes in Recipes"),
]
T_FOLDER = [
    ("how many work notes", r"\b2 notes in Work"),
    ("how many work notes do I have", r"\b2 notes in Work"),
    ("number of work notes", r"\b2 notes in Work"),
    ("count my work notes", r"\b2 notes in Work"),
]

_SUMMER = r"(?=.*Hello)(?=.*Uni timetable)(?=.*Beach day)"
_WINTER = r"(?=.*Ski trip)(?=.*Snow day)(?=.*New year plans)"
_NOT_SUMMER = r"Gym routine|Lecture 5|Ski trip|Pasta bake"
_NOT_WINTER = r"Gym routine|Lecture 5|Beach day|Hello|Spring clean"

#: Class U, a season is a window (meteorological: summer June to August,
#: winter December to February), the latest one gone for a note about the past.
#: (question, must, never)
U_SEASONS = [
    ("notes from last summer", _SUMMER, _NOT_SUMMER),
    ("what did I write last summer", _SUMMER, _NOT_SUMMER),
    ("show me what I wrote in the summer", _SUMMER, _NOT_SUMMER),
    ("anything I saved during summer?", _SUMMER, _NOT_SUMMER),
    ("how many notes did I write last summer", r"\b3 notes", NOT_FOUND),
    ("what did I write in winter", _WINTER, _NOT_WINTER),
    ("what did I write last winter", _WINTER, _NOT_WINTER),
    ("notes from winter", _WINTER, _NOT_WINTER),
    ("what did I jot down over the winter", _WINTER, _NOT_WINTER),
    ("how many notes did I write in winter", r"\b3 notes", NOT_FOUND),
]

_LATE_SEP = r"(?=.*Standup notes)"
_NOT_LATE_SEP = r"Packing list|Quarterly report|Gym routine|Errands"
#: Class V, a week or a half of a named month. (question, must, never)
V_PARTS = [
    ("what did I write in the first week of October", r"(?=.*Shakespeare essay)(?=.*Bubble tea)", r"Gym routine|Lecture 5|Errands"),
    ("notes from the first week of October", r"(?=.*Shakespeare essay)(?=.*Bubble tea)", r"Gym routine|Lecture 5|Errands"),
    ("what did I do in the first week of october", r"(?=.*Shakespeare essay)(?=.*Bubble tea)", r"Gym routine|Lecture 5|Errands"),
    ("show me the first week of October", r"(?=.*Shakespeare essay)(?=.*Bubble tea)", r"Gym routine|Lecture 5|Errands"),
    ("what did I write in the second week of October", r"Errands", r"Gym routine|Lecture 5|Bubble tea"),
    ("what did I write in the last week of September", _LATE_SEP, _NOT_LATE_SEP),
    ("notes from the last week of September", _LATE_SEP, _NOT_LATE_SEP),
    ("what did I do in the last week of Sept", _LATE_SEP, _NOT_LATE_SEP),
    ("anything from the last week of september?", _LATE_SEP, _NOT_LATE_SEP),
    ("what did I write in the second half of March", r"Spring clean", r"Taxes|Gym routine"),
    ("notes from the second half of March", r"Spring clean", r"Taxes|Gym routine"),
    ("what did I do in the second half of march", r"Spring clean", r"Taxes|Gym routine"),
    ("show me the 2nd half of March", r"Spring clean", r"Taxes|Gym routine"),
    ("what did I write in the first half of March", r"Taxes", r"Spring clean|Gym routine"),
]

_THIS_WEEK = r"(?=.*Gym routine)(?=.*Lecture 5)"
_NOT_THIS_WEEK = r"Errands|Bubble tea|Shakespeare essay"
#: Class W, a window phrase said twice is applied once, never an error or an
#: empty answer. (question, must, never)
W_REPEAT = [
    ("what did I write this week and this week", _THIS_WEEK, _NOT_THIS_WEEK),
    ("this week, what did I write this week", _THIS_WEEK, _NOT_THIS_WEEK),
    ("notes from this week, what did I make this week", _THIS_WEEK, _NOT_THIS_WEEK),
    ("what have I written this week, I mean this week", _THIS_WEEK, _NOT_THIS_WEEK),
    ("how many notes did I write this week, this week only", r"\b2 notes", NOT_FOUND),
    ("notes from last month, you know, last month", r"Packing list", r"Gym routine|Lecture 5|Bubble tea"),
]


#: Classes still failing, each case a strict xfail until its fix lands (take
#: the letter out when the class passes).
OPEN = {"U", "V", "what did I write this week and this week", "what have I written this week, I mean this week"}


def _cases(cls: str, rows: list):  # noqa: ANN202
    def mark(q: str) -> list:
        return [pytest.mark.xfail(strict=True, reason="open")] if cls in OPEN or q in OPEN else []

    return [pytest.param(*row, id=row[0], marks=mark(row[0])) for row in rows]


def _check(said: str, must: str, never: str | None, q: str, cls: str) -> None:
    ok = bool(re.search(must, said, re.I | re.S)) and not (never and re.search(never, said, re.I | re.S))
    assert ok, f"[{cls}] {q!r} -> {said[:500]!r}"


@pytest.mark.parametrize("q,must", S_STATE, ids=[q for q, _ in S_STATE])
def test_counts_by_state(ask, q, must):
    _check(ask(q), must, NOT_FOUND, q, "S")


@pytest.mark.parametrize("q,must", T_WORD, ids=[q for q, _ in T_WORD])
def test_counts_by_tag_or_folder_word(ask, q, must):
    _check(ask(q), must, NOT_FOUND, q, "T")


@pytest.mark.parametrize("q,must", T_FOLDER, ids=[q for q, _ in T_FOLDER])
def test_work_word_is_a_folder_when_no_tag(ask_folder, q, must):
    _check(ask_folder(q), must, NOT_FOUND, q, "T")


@pytest.mark.parametrize("q,must,never", _cases("U", U_SEASONS))
def test_seasons(ask, q, must, never):
    _check(ask(q), must, never, q, "U")


@pytest.mark.parametrize("q,must,never", _cases("V", V_PARTS))
def test_weeks_and_halves_of_a_month(ask, q, must, never):
    _check(ask(q), must, (never + "|" + NOT_FOUND), q, "V")


@pytest.mark.parametrize("q,must,never", _cases("W", W_REPEAT))
def test_a_repeated_window_applies_once(ask, q, must, never):
    _check(ask(q), must, (never + "|" + NOT_FOUND), q, "W")
