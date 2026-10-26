"""Composer classes, second pass (INBOX 1357/1400, composer9-1026 work list).

Same notebook and fixed clock as `test_composer_classes_1357.py` (Wednesday
21 October 2026, 10:00); each class has several phrasings the owner did not
report. A failing case is a strict xfail in `OPEN`. No model runs."""

from __future__ import annotations

import re

import datetime as dt

import pytest

from tessellate.ai import notebook_stats
from tests.test_composer_classes_1357 import NOT_FOUND, NOW, ask  # noqa: F401


@pytest.fixture(autouse=True)
def _stats_clock(monkeypatch):
    """The counts read their windows from the same fixed day."""
    monkeypatch.setattr(notebook_stats, "utcnow", lambda: NOW.replace(tzinfo=dt.timezone.utc))

_KIND_MAP = r"(map|Cloud computing)"

#: Class M, a map or board's words are found without naming it, and the answer
#: says the source kind (work list 1: "tell me about IaaS" found nothing).
M_SOURCES = [
    ("tell me about IaaS", r"(?=.*IaaS)(?=.*Cloud computing map)"),
    ("what is PaaS", rf"(?=.*PaaS)(?=.*{_KIND_MAP})"),
    ("define SaaS", rf"(?=.*SaaS)(?=.*{_KIND_MAP})"),
    ("anything on SaaS?", rf"(?=.*SaaS)(?=.*{_KIND_MAP})"),
    ("what do I have on service models", rf"(?=.*Service models)(?=.*{_KIND_MAP})"),
    ("what do my notes say about iaas", rf"(?=.*IaaS)(?=.*{_KIND_MAP})"),
    ("what do I have on the exam cards", r"(?=.*operating systems exam)(?=.*(board|Revision))"),
    ("anything about scheduling cards?", r"(?=.*Scheduling)(?=.*(board|Revision))"),
    ("what do I know about the ghost", r"(?=.*ghost)(?=.*(Essay draft|document))"),
]

_HIER = r"Service models\W+(?:[a-z ]*:)?\s*(?:IaaS|PaaS)"
_FLAT = r"lists four|Service models, IaaS"

#: Class N, a map or an outline is read as a hierarchy (work list 2): the
#: parent leads and its children follow it, never four siblings.
N_HIERARCHY = [
    "what does my cloud computing map say",
    "what's on my cloud computing map",
    "tell me about the cloud computing map",
    "what are the service models",
    "summarise my cloud computing map",
]

#: Class O, "tell me more" does not tell again what an earlier answer drew on,
#: however that answer worded it (work list 4: tracking by source, not by
#: wording). (first question, never)
O_TOLD = [
    ("when are my uni days?", r"Tuesday and Thursday"),
    ("what have I saved about uni?", r"Tuesday and Thursday|student card"),
    ("summarise my uni notes", r"student card|Tuesday|Hamlet|round robin"),
    ("what's in my uni timetable", r"Tuesday|student card"),
    ("tell me about my hobbies", r"brown sugar|Squats"),
    ("what do I know about bubble tea", r"brown sugar|taro"),
    ("what did I write about the essay?", r"Hamlet's delay|due 30 October"),
]

#: Class P, a board's card never outranks the note that holds the answer.
P_SOURCE_RANK = [
    ("what's my exam about", r"12 November"),
    ("when is my exam?", r"12 November"),
    ("what do I have on round robin", r"time slice"),
]

#: Class Q, a count narrowed by any filter says the filtered number, and a
#: filter value the notebook lacks says so (work list 3). (question, must)
Q_COUNTS = [
    ("how many notes are not linked", r"\b7 unlinked notes"),
    ("how many notes are unlinked", r"\b7 unlinked notes"),
    ("how many notes have no links", r"\b7 unlinked notes"),
    ("how many orphan notes do I have", r"\b7 unlinked notes"),
    ("how many notes aren't linked to anything", r"\b7 unlinked notes"),
    ("how many notes are tagged work", r"no tag called work"),
    ("how many notes have the tag work", r"no tag called work"),
    ("how many notes tagged work", r"no tag called work"),
    ("how many notes are in Work", r"no category called Work.*Hobbies"),
    ("how many notes are in Hobbies", r"\b2 notes in Hobbies"),
    ("how many uni notes are not linked", r"\b3 unlinked notes in Uni"),
    ("how many notes have a tag", r"no notes with a tag"),
    ("how many boards do I have", r"\b1 board\b"),
    ("how many maps do I have", r"\b1 mind map"),
    ("how many notes did I write in the last 3 days", r"\b2 notes"),
    ("how many notes did I write in October", r"\b5 notes"),
]

#: Class R, time windows said as a range, a span or a default (work list 5,
#: through `ai/recognise.py` only). (question, must, never)
R_WINDOWS = [
    ("what did I do from Monday to Wednesday", r"(?=.*Gym routine)(?=.*Lecture 5)", r"Errands|Essay draft"),
    ("what did I make from monday to wednesday", r"(?=.*Gym routine)(?=.*Lecture 5)", r"Errands"),
    ("what did I write between 1 and 5 October", r"(?=.*Shakespeare essay)(?=.*Bubble tea)", r"Gym routine|Lecture 5"),
    ("what did I do between 2 and 5 October?", r"(?=.*Shakespeare essay)(?=.*Bubble tea)", r"Gym routine"),
    ("what did I do between March and May", r"March", r"Gym routine|Lecture 5"),
    ("what did I do from March to May", r"March", r"Gym routine|Lecture 5"),
    ("what did I do recently", r"(?=.*Lecture 5)(?=.*Errands)(?=.*7 to 21 October)", r"Bubble tea"),
    ("what have I been up to lately", r"(?=.*Lecture 5)(?=.*Errands)(?=.*7 to 21 October)", r"Bubble tea"),
    ("what did I do this weekend", r"Essay draft", r"Gym routine|Lecture 5"),
]

OPEN: set[str] = set()


def _cases():
    for q, must in M_SOURCES:
        yield ("M", q, must, NOT_FOUND)
    for q in N_HIERARCHY:
        yield ("N", q, _HIER, _FLAT + "|" + NOT_FOUND)
    for q, must in P_SOURCE_RANK:
        yield ("P", q, must, NOT_FOUND)
    for q, must, never in R_WINDOWS:
        yield ("R", q, must, never + "|" + NOT_FOUND)
    for q, must in Q_COUNTS:
        yield ("Q", q, must, NOT_FOUND + r"|^The number you saved")


CASES = [
    pytest.param(c, q, m, n, id=f"{c}-{q}", marks=([pytest.mark.xfail(strict=True)] if f"{c}-{q}" in OPEN else []))
    for c, q, m, n in _cases()
]


@pytest.mark.parametrize("cls,q,must,never", CASES)
def test_the_class_holds(ask, cls, q, must, never):  # noqa: F811
    said = ask(q)
    ok = bool(re.search(must, said, re.I | re.S)) and not (never and re.search(never, said, re.I | re.S))
    assert ok, f"[{cls}] {q!r} -> {said[:500]!r}"


@pytest.mark.parametrize("first,never", O_TOLD, ids=[f"O-{f}" for f, _ in O_TOLD])
def test_tell_me_more_is_new(ask, first, never):  # noqa: F811
    said = ask(first)
    more = ask("tell me more", [{"question": first, "answer": said}])
    assert not re.search(never, more, re.I), f"[O] {first!r} -> {more[:400]!r}"
