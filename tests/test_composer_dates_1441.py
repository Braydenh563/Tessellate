"""A date is said only when the question is about time (INBOX 1441, the
owner: "I dont like how it refers to dates").

The answer to "What have I saved about hobbies?" opened "You have ten notes
about hobbies, 17 July to 4 October.", then "On 4 September, you saved ...",
"Your note of 27 July has ...", "A week on, by 3 August, ..." and closed
"You last wrote about it about a month ago, which is a while". The rule, for
the class: a sentence carries the fact and the record card carries the date;
a date (or a day word: "yesterday", "last Friday") is said only when the
question asks about time; a note is named by its title or clipped clause,
never "your note of <date>"; the staleness footer only when the question is
about how current something is.

Three notebooks of different subjects, several phrasings each, in Ask
(`notes_only`) and in Chat, with no model. Note text holds no dates of its
own, so any date in an answer is the composer's.

Fixed clock: Thursday 29 October 2026, 10:00."""

from __future__ import annotations

import datetime as dt
import re

import pytest

from tessellate.api import routes_chat
from tessellate.core import config
from tessellate.entry import manager
from tests.test_composer_route_688 import _ask

NOW = dt.datetime(2026, 10, 29, 10, 0, 0)
D = dt.datetime

#: (category, a word for it, notes as (text, written)).
BOOKS = [
    ("Hobbies", "my hobbies", [
        ("# Girl with bell\n\nA painting idea: a girl ringing a bell in the snow, soft blues.", D(2026, 9, 4, 9)),
        ("Go to the gym at 9pm for legs.", D(2026, 7, 27, 9)),
        ("# Workout split\n\nPull, Push, Legs, Rest Day, Pull, Push, Rest Day", D(2026, 7, 27, 18)),
        ("Started learning guitar, practising chords for ten minutes a day.", D(2026, 8, 3, 9)),
        ("# Chess\n\nPlaying the Sicilian defence online in the evenings.", D(2026, 10, 4, 9)),
        ("Thinking of buying a better sketchbook for watercolours.", D(2026, 7, 17, 9)),
    ]),
    ("Cooking", "cooking", [
        ("# Sourdough starter\n\nA sourdough starter is flour and water left to ferment with wild yeast.", D(2026, 8, 2, 9)),
        ("Baked a sourdough loaf with a darker crust.", D(2026, 8, 14, 9)),
        ("# Ramen\n\nTonkotsu broth needs twelve hours; try a pressure cooker.", D(2026, 9, 1, 9)),
        ("Want to learn knife skills, maybe a weekend class.", D(2026, 9, 20, 9)),
        ("# Pantry\n\nmiso, rice vinegar, chilli crisp", D(2026, 10, 2, 9)),
    ]),
    ("Study", "uni", [
        ("# Psych lecture 1\n\nMemory is reconstructive rather than a recording.", D(2026, 7, 20, 9)),
        ("Read chapters 1 to 3 of the Myers textbook.", D(2026, 7, 27, 9)),
        ("# Stats\n\nStill shaky on confidence intervals; redo the practice set.", D(2026, 8, 10, 9)),
        ("Study group meets in the library after the lab.", D(2026, 8, 31, 9)),
        ("# Essay plan\n\nIntro, two case studies, counterargument, conclusion.", D(2026, 9, 28, 9)),
    ]),
]


def _plain(cat: str, word: str) -> list[str]:
    low = cat.lower()
    return [f"What have I saved about {low}?", f"tell me about {word}", f"what about {low}",
            f"what do I know about {low}", f"{low}", f"what are my notes on {word}"]


def _timed(cat: str, word: str) -> list[str]:
    low = cat.lower()
    return [f"when did I last write about {low}", f"what did I write about {word} in July",
            f"what's the latest on {low}", f"what did I write about {low} last month"]


@pytest.fixture
def answers(client, session, monkeypatch):
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)

    def build(book, questions, chat: bool) -> list[tuple[str, str]]:  # noqa: ANN001
        cat, word, notes = book
        for text, when in notes:
            entry = manager.create_entry(session, text, cat)
            entry.created_at = entry.updated_at = when
        session.commit()
        kw = {} if chat else {"notes_only": True, "answer_from": "notes"}
        return [(q, _ask(client, q, **kw)["text"]) for q in questions(cat, word)]

    return build


MODES = pytest.mark.parametrize("chat", [False, True], ids=["ask", "chat"])
BOOK = pytest.mark.parametrize("book", BOOKS, ids=[b[0] for b in BOOKS])

_MONTH = "January|February|March|April|May|June|July|August|September|October|November|December"
_WEEKDAY = "Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday"
#: A date, or a day said as a time word, anywhere in an answer.
_DATE = re.compile(
    rf"\b\d{{1,2}} (?:{_MONTH})\b|\b(?:{_MONTH}) \d{{1,2}}\b|\b(?:yesterday|today|a week ago|earlier this month)\b"
    rf"|\b(?:[Oo]n|[Ll]ast) (?:{_WEEKDAY})\b|\b(?:a|two|three|four|\w+) (?:weeks?|days?|months?) (?:on|later)\b", re.I)
_NOTE_OF = re.compile(r"\bnote of\b", re.I)
_STALE = re.compile(r"fresh note|may have moved on|where it stood then|Nothing new on it|which is a while")


def _bad(found: list[str]) -> None:
    assert not found, "\n\n".join(found)


@MODES
@BOOK
def test_a_question_not_about_time_says_no_date(answers, book, chat):
    _bad([f"{q!r}: {m.group(0)!r} in\n{t}" for q, t in answers(book, _plain, chat) for m in [_DATE.search(t)] if m])


@MODES
@BOOK
def test_a_note_is_never_named_by_its_date(answers, book, chat):
    found = answers(book, lambda c, w: _plain(c, w) + _timed(c, w), chat)
    _bad([f"{q!r}:\n{t}" for q, t in found if _NOTE_OF.search(t)])


@MODES
@BOOK
def test_the_staleness_footer_only_for_a_currency_question(answers, book, chat):
    _bad([f"{q!r}:\n{t}" for q, t in answers(book, _plain, chat) if _STALE.search(t)])


@MODES
@BOOK
def test_a_question_about_time_still_says_when(answers, book, chat):
    found = answers(book, _timed, chat)
    #: "Nothing in July touches hobbies" says the asked time too.
    when = re.compile(rf"\bago\b|\b(?:in|of|since) (?:{_MONTH})\b|\blast (?:week|month)\b", re.I)
    _bad([f"{q!r}:\n{t}" for q, t in found if not _DATE.search(t) and not when.search(t)])


class _Slots(dict):
    def __missing__(self, key: str) -> str:
        return "Thing" if key[:1].isupper() else "thing"


def _every_phrase() -> list[tuple[str, str]]:
    from tessellate.ai import composer_digest

    said = []
    for table in [composer_digest._BASE, *composer_digest.VOICES.values()]:
        for key, phrases in table.items():
            for phrase in phrases if isinstance(phrases, tuple) else (phrases,):
                #: A lead ("a week on, ") opens a clause; it is not one.
                if isinstance(phrase, str) and "{" in phrase and not phrase.endswith(", "):
                    said.append((key, phrase))
    return said


def test_a_dropped_date_never_leaves_its_clause_behind():
    """The coordinator, 2026-10-29: "You use HCI in two notes, the last." A
    phrase's date goes with its whole clause, in every phrase of every voice."""
    from tessellate.ai import composer_digest

    token = composer_digest._TIMED.set(False)
    try:
        bad = []
        for key, phrase in _every_phrase():
            text = composer_digest._Capitals(phrase).format(**_Slots({k: "thing" for k in re.findall(r"\{(\w+)\}", phrase)}))
            if re.search(r"\b(?:the last|on|of|from|by|at|written|dated|spanning)\s*[.,:;)]|,\s*[.,:;)]|\s{2}", text):
                bad.append(f"{key}: {text}")
    finally:
        composer_digest._TIMED.reset(token)
    _bad(bad)


def test_a_glossary_answer_names_its_note_and_ends_whole():
    from datetime import date

    from tessellate.ai import composer_digest

    notes = [{"id": i, "content": c, "created_at": f"2026-09-0{i}T10:00:00", "tags": [], "category": "Uni"}
             for i, c in ((1, "# HCI lecture\n\nHuman Computer Interaction (HCI) lecture 2."), (2, "HCI quiz Friday."))]
    text = composer_digest.answer("what does HCI stand for?", notes, today=date(2026, 10, 11))["text"]
    assert text.startswith("HCI is short for Human Computer Interaction, from your HCI lecture note."), text
    assert "You use HCI in two notes." in text and "September" not in text, text
    #: Asked about time, the clause comes back whole.
    from tessellate.ai import composer

    composer_digest._set_timing("when did I write down what HCI is?")
    out = composer_digest._Out()
    views = [composer.read_note(n, i) for i, n in enumerate(notes)]
    assert composer_digest._stands_for(out, "HCI", views, date(2026, 10, 11))
    timed = " ".join(out.lines + out.closing)
    assert "written on 1 September" in timed and "the last on 2 September" in timed and "note of" not in timed, timed


@pytest.mark.parametrize(("content", "named"), [
    ("Intro to Cloud Computing starts Monday.", "the note that starts “Intro to Cloud Computing starts Monday”"),
    ("Annual Leave starts 2 December.", "the note that starts “Annual Leave starts 2 December”"),
    ("Project Management Office sent the forms.", "the note that starts “Project Management Office sent the forms”"),
    ("Atlas retro meeting", "the Atlas retro meeting"),
    ("HCI quiz Friday.", "the HCI quiz Friday"),
])
def test_a_one_line_sentence_is_quoted_never_worn_as_a_name(content, named):
    """The coordinator, 2026-10-29: "Intro to Cloud Computing starts Monday
    names it in full". A short line that says something is a sentence."""
    from tessellate.ai import composer_frame

    assert composer_frame.short_name({"content": content, "category": "Uni"}) == named
