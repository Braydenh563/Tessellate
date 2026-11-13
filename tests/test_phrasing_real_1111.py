"""Real phrasings, not ours (CHAT_PLAN "Phrasing tests from real conversations").

`fixtures/composer/phrasing_1111.json` holds single-sentence user turns from CLINC150
(CC BY 3.0; attribution in `fixtures/composer/SOURCES.md`), grouped by what the person
wanted. Each is asked through `/chat/stream` with no model over the voice notebook at
its fixed clock (Tuesday 10 November 2026, 09:00), and the answer is judged by what
the class promises, not by exact words: small talk is answered by the app and never
searches the notes, an out-of-scope question never quotes a note, an act is a card or
a plain how-to and never a notes search, and a question the notebook cannot answer is
said so rather than answered with a stray note.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

import pytest

from tessellate.api import chat_said, chat_turn, routes_chat
from tessellate.entry import manager
from tests.test_composer_route_688 import _ask

_FIXTURES = Path(__file__).parent / "fixtures" / "composer"
FIXTURE = json.loads((_FIXTURES / "phrasing_1111.json").read_text(encoding="utf-8"))
NOTEBOOK = json.loads((_FIXTURES / "voice_1110.json").read_text(encoding="utf-8"))
NOW = datetime.fromisoformat(NOTEBOOK["now"])

#: A reply that went looking in the notes: a quoted note, a citation, or a miss about the person's own words.
_NOTES_SEARCH = re.compile(r"Your notes? (?:say|have|don't)|None of (?:your|these)|couldn't find|I found no|doesn't seem to be in|isn't in your|No note|nothing in your|Here is what I found|\*\*Also", re.I)
_CITES = re.compile(r"From your \*\*|\*\*Also|Your notes? (?:say|have)|You (?:wrote|saved|noted):|Here is what I found|The nearest (?:is|note|thing|entry)|The closest (?:your notes|is|relevant)|Your best match|What your notes have", re.I)
_CARD_OR_HOWTO = re.compile(r"Confirm|Cancel|What should I|I found no (?:open task or )?reminder|Say it as|say it like this|Sure\.|which note|When do you", re.I)
_DATE = re.compile(r"\b(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b.*\b(?:November|December|October|2026)\b|\b(?:November|December|October)\b", re.I)


def _judge(kind: str, text: str) -> str | None:
    if not text.strip():
        return "empty"
    if kind == "social":
        return "went looking in the notes" if _NOTES_SEARCH.search(text) else None
    if kind == "oos":
        return "quoted a note" if _CITES.search(text) else None
    if kind == "act":
        return "searched the notes for an act" if _NOTES_SEARCH.search(text) and not _CARD_OR_HOWTO.search(text) else None
    if kind == "nothing":
        return "answered with a stray note" if _CITES.search(text) else None
    if kind == "date":
        return None if _DATE.search(text) else "no date"
    raise AssertionError(kind)


@pytest.fixture(autouse=True)
def _fixed_now(monkeypatch):
    for module in (routes_chat, chat_said, chat_turn):
        monkeypatch.setattr(module, "user_now", lambda _config: NOW)


@pytest.fixture
def notebook(session):
    for made, category, tags, content in NOTEBOOK["notes"]:
        entry = manager.create_entry(session, content, category_name=category, tags=tags)
        entry.created_at = entry.updated_at = datetime.fromisoformat(made)
    session.commit()


def test_every_class_is_a_known_kind():
    assert {c["kind"] for c in FIXTURE["classes"].values()} <= {"social", "oos", "act", "nothing", "date", "notes"}


def test_the_phrasings_name_nobody_and_carry_no_digits():
    for name, group in FIXTURE["classes"].items():
        for phrase in group["phrases"]:
            assert not re.search(r"\d|@|https?:", phrase), (name, phrase)
            assert 2 <= len(phrase.split()) <= 14 and "\n" not in phrase, (name, phrase)


JOKE_ABOUT = "A joke about a named subject cannot be made with no model: the canned jokes are not about it, and the sentence falls through to a search of the notes for the subject."
STRAY = (
    "The notebook holds nothing on this (no leave balance, no meeting schedule); the answer offers the nearest note on a shared everyday word "
    "('day', 'days', 'meeting'). A coverage gate on the nearest-note answer is open work."
)
SHARED_WORD = "An out-of-scope question that shares an everyday word with a note ('ship', 'mean', 'event', 'flight') is answered with that note: the same coverage gate."
ALARM = "The app's alarm is an ordinary reminder, but a question about alarms is not yet read as a question about reminders (tool ranking); open work."
DATE = "A number spelt in words, and the misspelt 'calender' lead-in, are not read by the dates utility."
BARE_EVENT = "A bare statement of an event has no verb to say what to do with it: it is neither a reminder nor a question."

#: Phrase (lower case) -> why the composer cannot honestly answer it yet. Strict: the marker comes off when the phrase passes.
XFAIL = {
    "tell me something funny about politics": JOKE_ABOUT,
    "tell me a joke about cows": JOKE_ABOUT,
    "tell me a joke about cats": JOKE_ABOUT,
    "tell me something funny about cats": JOKE_ABOUT,
    "who is the current captain of this ship": SHARED_WORD,
    "what does it mean to be an alpha male": SHARED_WORD,
    "how do i change my flight": SHARED_WORD,
    "i want to book tickets for an event.": SHARED_WORD,
    "what alarms do i have set.": ALARM,
    "what day is it gonna be in twenty-one days": DATE,
    "calender says tomorrow is": DATE,
    "lunch with my friend at noon today": BARE_EVENT,
    "when is the meeting with my boss scheduled for": STRAY,
    "share my meeting schedule with me": STRAY,
    "do i have any meeting to go to today": STRAY,
    "how many vacation days do i have remaining, please": STRAY,
    "how many vacation days have i accrued": STRAY,
    "hoe many vacation days are left for me": STRAY,
    "i have how many vacation days left this year": STRAY,
    "what is my remaining pto days": STRAY,
    "is my day off request approved": STRAY,
    "has my vacation time been signed off on": STRAY,
    "has my day off request been approved or denied yet": STRAY,
    "any status update on my day off request": STRAY,
    "has my day off request been looked at yet": STRAY,
}


def _cases():
    for name, group in FIXTURE["classes"].items():
        for phrase in group["phrases"]:
            why = XFAIL.get(phrase.lower())
            marks = [pytest.mark.xfail(strict=True, reason=why)] if why else []
            yield pytest.param(name, group["kind"], phrase, marks=marks, id=f"{name}: {phrase}")


def test_every_xfail_names_a_phrase_in_the_fixture():
    every = {p.lower() for g in FIXTURE["classes"].values() for p in g["phrases"]}
    assert set(XFAIL) <= every


@pytest.mark.parametrize(("name", "kind", "phrase"), list(_cases()))
def test_real_phrasing(client, notebook, name, kind, phrase):
    text = _ask(client, phrase)["text"]
    problem = _judge(kind, text) if kind != "notes" else ("empty" if not text.strip() else None)
    assert not problem, f"{name} | {phrase} | {problem} | {text[:120]!r}"
