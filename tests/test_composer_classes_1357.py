"""Composer failure classes (INBOX 1357: "each time I show an issue for the
composer, I think you are only fixing for that specific case scenario").

Every owner report about the composer, clustered into classes; each class is
tested here with sibling phrasings the owner did not report (other wording,
typos, casual forms, other content kinds), so a fix has to hold for the class.
The reports behind each class are listed in
`docs/roadmap/agent-remaining/composer9-1026.md`.

Fixed clock: Wednesday 21 October 2026, 10:00. "Last week" is 12 to 18
October; "this week" is 19 to 21 October. No model runs."""

from __future__ import annotations

import datetime as dt
import json
import os
import re

import pytest

from tessellate.api import routes_chat
from tessellate.core import config
from tessellate.core.database import Document, Reminder, WhiteboardObject
from tessellate.entry import manager
from tests.test_composer_route_688 import _ask

NOW = dt.datetime(2026, 10, 21, 10, 0, 0)

#: (content, category, written, extra fields)
NOTES = [
    ("# Hello\n\nFirst note in Tessellate. Planning to use it for uni and the gym.", "Personal", dt.datetime(2026, 7, 1, 9), {}),
    ("# Uni timetable\n\nMy uni days this week are Tuesday and Thursday. Tomorrow I pick up my student card.", "Uni", dt.datetime(2026, 7, 17, 9), {}),
    ("# Shakespeare essay\n\nHamlet's delay is the theme of the essay. The essay is due 30 October.", "Uni", dt.datetime(2026, 10, 2, 9), {}),
    ("# Bubble tea\n\nTried the brown sugar one at Chatime; too sweet. Next time the taro one.", "Hobbies", dt.datetime(2026, 10, 5, 18), {}),
    ("# Lecture 5: Operating systems\n\nA process is a program in execution. Round robin gives each process a fixed time slice. Exam on 12 November.", "Uni", dt.datetime(2026, 10, 20, 9), {}),
    ("# Gym routine\n\nPull, push, legs, then a rest day. Squats on Monday, deadlifts on Thursday.", "Hobbies", dt.datetime(2026, 10, 19, 8), {}),
    ("# Errands\n\n- [ ] Book the tram pass\n- [ ] Buy a notebook\n- [x] Pay rent", "Personal", dt.datetime(2026, 10, 14, 9), {}),
    ("# Revision board", "Uni", dt.datetime(2026, 10, 16, 15), {"is_board": True, "board_settings": json.dumps({"type": "board"})}),
    ("# Cloud computing map", "Uni", dt.datetime(2026, 10, 13, 11), {"is_board": True, "board_settings": json.dumps({"type": "map"})}),
    ("# Old shopping list\n\nMilk, eggs, bread.", "Personal", dt.datetime(2026, 10, 12, 9), {"is_deleted": True, "deleted_at": dt.datetime(2026, 10, 15, 12)}),
]
#: A board's and a map's words live on their objects, not in the entry:
#: (board title, [(text, parent index or None)]).
OBJECTS = {
    "# Revision board": [("Cards for the operating systems exam", None), ("Scheduling: round robin", None)],
    "# Cloud computing map": [("Service models", None), ("IaaS", 0), ("PaaS", 0), ("SaaS", 0)],
}
DOCUMENTS = [
    ("Essay draft", "Hamlet delays because he doubts the ghost.", dt.datetime(2026, 10, 15, 14), dt.datetime(2026, 10, 17, 16)),
]
REMINDERS = [
    ("Pay the phone bill", dt.datetime(2026, 10, 16, 9), True, dt.datetime(2026, 10, 16, 10)),
    ("Hand in the essay", dt.datetime(2026, 10, 30, 17), False, None),
]

_DUMP = os.environ.get("COMPOSER_1357_DUMP")


@pytest.fixture
def ask(client, session, monkeypatch):
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)
    for text, category, when, extra in NOTES:
        entry = manager.create_entry(session, text, category)
        entry.created_at = entry.updated_at = when
        for key, value in extra.items():
            setattr(entry, key, value)
        made: list = []
        for words, parent in OBJECTS.get(text, []):
            obj = WhiteboardObject(board_id=entry.id, kind="text", data=json.dumps({"content": words}),
                                   parent_id=made[parent].id if parent is not None else None)
            session.add(obj)
            session.flush()
            made.append(obj)
    for title, content, made, edited in DOCUMENTS:
        session.add(Document(title=title, content=content, created_at=made, updated_at=edited))
    for text, due, done, done_at in REMINDERS:
        session.add(Reminder(text=text, due_at=due, done=done, done_at=done_at, created_at=due - dt.timedelta(days=3)))
    session.commit()

    def go(question: str, history: list | None = None) -> str:
        text = _ask(client, question, notes_only=True, answer_from="notes", history=history or [])["text"]
        if _DUMP:
            with open(_DUMP, "a", encoding="utf-8") as fh:
                fh.write(f"### {question}\n{text}\n\n")
        return text

    return go


#: The notebook's true newest note. A closing line that calls any other note
#: "your newest" or "your latest" states a wrong fact (class K, found while
#: measuring this set: "Your latest note is Hello" under a gym answer).
NEWEST = "Lecture 5: Operating systems"
_RECENCY = re.compile(
    r"(?:your newest note|newest page|is your newest|latest note is|latest note:|most recent note is|latest entry is|"
    r"most recently you wrote|lately|where you left off|fresh off your keyboard)",
    re.I,
)


def _false_recency(said: str) -> bool:
    for line in said.splitlines():
        if _RECENCY.search(line):
            titles = re.findall(r"“([^”]+)”", line)
            if titles and any(t != NEWEST for t in titles):
                return True
    return False


def _ok(said: str, must: str | None, never: str | None) -> bool:
    if _false_recency(said):
        return False
    return (not must or bool(re.search(must, said, re.I | re.S))) and (not never or not re.search(never, said, re.I | re.S))


NOT_FOUND = r"could you put it another way|different word|don't mention|do not mention|nothing (here|in your notes)|no notes? (about|on|mention)|which note (would|might) it be|how else might you have put|couldn't find"

#: Class A, the capability question in any wording (1300 "Wat cna u do??",
#: K20 "whaty can u do??"): the capability reply, never a note search.
CAPABILITY = r"Atlas's assistant|I answer from your notes"
A_CAPABILITY = [
    "whaty can u do??",
    "wat can u do",
    "what can you even do",
    "what r u able to do",
    "how can you help me",
    "what are you capable of?",
    "waht can you do",
    "what do u do",
    "what can atlas do",
    "what kind of stuff can you help with",
]

#: Class B, a bare tool or command word (1334 "timer\\"): run it or offer the
#: choice; never "your notes don't mention" with "which note".
B_COMMAND = [
    ("timer\\", r"timer"),
    ("timer", r"timer"),
    ("set a timer", r"timer"),
    ("reminder", r"Hand in the essay"),
    ("reminders", r"Hand in the essay"),
    ("stats", r"notes"),
    ("statistics", r"notes"),
    ("categories", r"Uni.*Hobbies.*Personal"),
    ("tags", r"tag"),
    ("countdown", r"countdown|until|days"),
]

#: Class C, the activity recap by window (K20, K20a, 1333 /today, 441): every
#: kind, made vs edited vs binned, and a named empty window with the nearest
#: active one. (question, must, never)
C_RECAP = [
    ("what did I do last week?", r"(?=.*Revision board)(?=.*Cloud computing map)(?=.*Essay draft)(?=.*Old shopping list)(?=.*phone bill)", None),
    ("what did i get up to last week", r"(?=.*Revision board)(?=.*Essay draft)", NOT_FOUND),
    ("wat did i do last wk", r"(?=.*Revision board)(?=.*Essay draft)", NOT_FOUND + r"|five newest"),
    ("what did I make last week?", r"(?=.*Revision board)(?=.*Cloud computing map)(?=.*Essay draft)", r"\[ \]"),
    ("what did I work on last week", r"Essay draft", None),
    ("what did I delete last week?", r"Old shopping list", None),
    ("what did I edit last week", r"Essay draft", None),
    ("show my activity this week", r"Gym routine|Lecture 5", None),
    ("what did I do in August?", r"August.*(17 July|2 October)", None),
    ("what did I do yesterday", r"Lecture 5", None),
    ("what have I been up to this week", r"Gym routine|Lecture 5", NOT_FOUND),
]

#: Class D, a note's relative time words said as dates when the note is not
#: from now (1339 "it is not this week anymore"). (question, never)
D_TIME = [
    ("what are my uni days?", r"this week are|\btomorrow\b"),
    ("what have I saved about uni?", r"this week are|\btomorrow\b"),
    ("tell me about my uni timetable", r"this week are|\btomorrow\b"),
    ("when do I pick up my student card?", r"\btomorrow\b"),
    ("summarise my uni notes", r"this week are|\btomorrow\b"),
    ("what's in my uni timetable note", r"this week are|\btomorrow\b"),
]

#: Class E, the first, oldest, latest note (1345 "what was the first note I
#: ever wrote?"). (question, must)
E_EXTREME = [
    ("what was the first note I ever wrote?", r"Hello|1 July"),
    ("whats my oldest note", r"^(?!.*five oldest).*Hello"),
    ("my first ever note?", r"Hello|1 July"),
    ("what was the last note I wrote", r"Lecture 5|20 October|yesterday"),
    ("most recent note?", r"Lecture 5|20 October|yesterday"),
    ("what's my newest note", r"Lecture 5|20 October|yesterday"),
    ("what did I write first", r"Hello|1 July"),
]

#: Class F, boards, maps and documents are sources like notes (744 "a board
#: must say board"). (question, must)
F_KINDS = [
    ("what's on my revision board?", r"operating systems exam"),
    ("what does my cloud computing map say", r"IaaS|PaaS|SaaS"),
    ("what's in my essay draft", r"doubts the ghost"),
    ("whats on the revision board", r"operating systems exam"),
    ("what did I write in my essay draft document?", r"doubts the ghost"),
    ("why does hamlet delay?", r"doubts the ghost|delay"),
    ("show me my boards", r"Revision board"),
    ("what maps do I have", r"Cloud computing map"),
]

#: Class G, a topic answer picks the note that is about it (724, 112, 1310,
#: 1301, K30). (question, must, never)
G_TOPIC = [
    ("what have I saved about the gym?", r"Gym routine|Pull, push|squats|deadlifts", r"Bubble tea"),
    ("anything about bubble tea?", r"brown sugar|Chatime|taro", None),
    ("gym?", r"Pull|Squats|deadlifts|Gym routine", None),
    ("tell me about my hobbies", r"Gym|Bubble tea", None),
    ("notes about my workout", r"Gym routine|Pull|Squats|deadlifts", None),
    ("what do I have on operating systems", r"process|Round robin|Lecture 5", None),
    ("when is my exam?", r"12 November", None),
    ("when's the essay due", r"30 October", None),
]

#: Class H, nothing found: name the thing, never an empty shrug, and a bare
#: tool word is not treated as a topic (1334, decision 24). (question, must)
H_EMPTY = [
    ("what did I write about quantum chromodynamics?", r"quantum chromodynamics"),
    ("anything on sourdough", r"sourdough"),
    ("notes about my cat", r"cat"),
    ("what did I say about the dentist", r"dentist"),
    ("hmm what about knitting", r"knitting"),
    ("do I have notes on tax returns", r"tax"),
]

#: Class I, lists of the notebook's own shape (1333 categories as one prose
#: line, 1324 "five notes" showing one). (question, must)
I_LISTS = [
    ("/categories", r"Uni.*Hobbies|Hobbies.*Uni"),
    ("list my categories", r"Uni.*Hobbies.*Personal"),
    ("what categories do I have", r"Uni.*Hobbies.*Personal"),
    ("how many notes per category", r"Uni.*Hobbies.*Personal"),
    ("what's still to do", r"^(?!.*newest notes).*tram pass.*notebook"),
    ("what's due", r"essay"),
    ("list my reminders", r"Hand in the essay"),
]

#: Class J, follow-ups carry the topic or window (741, dog2). (first, then, must, never)
J_FOLLOW = [
    ("what did I do last week?", "and this week?", r"Gym routine|Lecture 5", r"Cloud computing map"),
    ("what did I do this week?", "what about last week", r"board|map|Errands", None),
    ("when is my exam?", "what's it on", r"operating systems|process", None),
    ("what have I saved about the gym?", "tell me more", r"squats|deadlifts|Pull|rest day", None),
]


#: Cases still failing, each a strict xfail: a fix that makes one pass fails
#: the run until its id is taken out of this set (INBOX 1357 baseline: 35 of
#: 77 passing before any fix).
OPEN = {
    'J-what have I saved about the gym?->tell me more',
}


def _p(cls: str, turns: tuple, must, never, ident: str):  # noqa: ANN001, ANN202
    marks = [pytest.mark.xfail(strict=True, reason="INBOX 1357 open")] if ident in OPEN else []
    return pytest.param(cls, turns, must, never, id=ident, marks=marks)


def _cases():
    for q in A_CAPABILITY:
        yield _p("A", (q,), CAPABILITY, NOT_FOUND, f"A-{q}")
    for q, must in B_COMMAND:
        yield _p("B", (q,), must, NOT_FOUND, f"B-{q}")
    for q, must, never in C_RECAP:
        yield _p("C", (q,), must, never, f"C-{q}")
    for q, never in D_TIME:
        yield _p("D", (q,), None, never, f"D-{q}")
    for q, must in E_EXTREME:
        yield _p("E", (q,), must, None, f"E-{q}")
    for q, must in F_KINDS:
        yield _p("F", (q,), must, NOT_FOUND, f"F-{q}")
    for q, must, never in G_TOPIC:
        yield _p("G", (q,), must, never, f"G-{q}")
    for q, must in H_EMPTY:
        yield _p("H", (q,), must, None, f"H-{q}")
    for q, must in I_LISTS:
        yield _p("I", (q,), must, NOT_FOUND, f"I-{q}")
    for first, then, must, never in J_FOLLOW:
        yield _p("J", (first, then), must, never, f"J-{first}->{then}")


CASES = list(_cases())


@pytest.mark.parametrize("cls,turns,must,never", CASES)
def test_the_class_holds(ask, cls, turns, must, never):
    history: list = []
    said = ""
    for q in turns:
        said = ask(q, history)
        history.append({"question": q, "answer": said})
    assert _ok(said, must, never), f"[{cls}] {turns[-1]!r} -> {said[:400]!r}"
