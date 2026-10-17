"""A newer note on the same thing is the current one (O11; BACKLOG "Facts
change over time", the owner, 2026-10-12: "a newer note about the same thing
supersedes an older one instead of confusing the answer").

Measured 2026-10-17 with the composer and no model: "what are my uni days"
over a February note ("Uni days this semester: Tuesday and Thursday") and a
July one ("Uni days this semester are Monday and Wednesday") answered from
February; "what is my address" over "My address is 12 Oak Street" (2025)
and "My address is now 4 Birch Road" (2026) quoted the old address.

**Same thing, by its subject.** A state sentence names what it is about
before its value: the words before a colon ("Uni days this semester:
Tuesday and Thursday") or before "is" or "are" ("My address is now ...").
Two notes whose subjects share most of their words, and whose values
differ, are one thing at two times; the newer is current. Validity words
("this semester", "now", "currently") are not part of a subject.

**Never silently dropped.** The answer is the current note's, and one line
says what the older one said and when ("An older note, from 20 February,
said Tuesday and Thursday"). A question about the change or the past
("what changed", "last semester", "used to", "before") keeps both.

**A window that has closed.** A state sentence that says how long it holds
("Parking permit: bay 14 until June", "valid through March", "by the end of
September") with nothing newer on the subject is read for its end; once
that day is behind today, the answer adds one line saying so and that the
note may be out of date, instead of quoting it as current.
"""

from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import date

from tessellate.ai import recognise
from tessellate.search import query as query_understanding

#: Words that say when a value holds, not what it is about.
_VALIDITY = frozenset(
    "this that current currently now new latest semester term year week month today these days anymore still my our".split()
)
_SENTENCE = re.compile(r"(?<=[.!?])\s+|\n+")
_COLON = re.compile(r"^([^:]{3,60}):\s*(\S.*)$")
_COPULA = re.compile(r"^(.{3,60}?)\s+(?:is|are|was|were)\s+(?:now\s+|still\s+)?(\S.*)$", re.I)


@dataclass(frozen=True)
class Replaced:
    older: dict
    newer: dict
    value: str
    written: date | None


def _state(sentence: str) -> tuple[frozenset, str] | None:
    """A state sentence's subject words and its value, or None."""
    m = _COLON.match(sentence) or _COPULA.match(sentence)
    if not m:
        return None
    words = frozenset(w for w in query_understanding.search_terms(m.group(1)) if w not in _VALIDITY)
    return (words, m.group(2).strip()) if words else None


def _sentences(text: str) -> list[str]:
    return [s.strip().rstrip(".!?") for s in _SENTENCE.split(text or "")]


def _subjects(text: str) -> list[tuple[frozenset, str]]:
    """Each state sentence's subject words and its value."""
    return [state for state in (_state(s) for s in _sentences(text)) if state]


_SPELLED = re.compile(r"\b(\d{1,2}) (January|February|March|April|May|June|July|August|September|October|November|December) (\d{4})\b")
_MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")


def _day(note: dict) -> date | None:
    """The day a note was written: its ISO `created_at`, or the route's
    spelled-out `written` ("Friday 20 February 2026, 10:00")."""
    try:
        return date.fromisoformat(str(note.get("created_at") or "")[:10])
    except ValueError:
        pass
    spelled = _SPELLED.search(str(note.get("written") or ""))
    if spelled:
        return date(int(spelled.group(3)), _MONTHS.index(spelled.group(2)) + 1, int(spelled.group(1)))
    return None


def _same(a: frozenset, b: frozenset) -> bool:
    return len(a & b) / len(a | b) >= 0.6


def current(question: str, notes: list[dict]) -> tuple[list[dict], list[Replaced]]:
    """`notes` with each note a newer one supersedes left out, and what was
    left out; unchanged for a question about the change or the past."""
    if recognise.says_past(question) or len(notes) < 2:
        return notes, []
    #: Only the subject asked about: an older note says other things too, and
    #: "what are my uni days" is no reason to set aside an old note on golf.
    read = _read(question, notes)
    replaced = [r for r in (_replaced_by(row, read) for row in read) if r]
    gone = {id(r.older) for r in replaced}
    return [n for n in notes if id(n) not in gone], replaced


def _read(question: str, notes: list[dict]) -> list[tuple]:
    """Each note with its subjects that the question names, and its day."""
    asked = frozenset(w for w in query_understanding.search_terms(question or "") if w not in _VALIDITY)
    return [(n, [(w, v) for w, v in _subjects(str(n.get("content") or "")) if w & asked], _day(n)) for n in notes]


def _replaced_by(row: tuple, read: list[tuple]) -> Replaced | None:
    """The first newer note that says something else of a subject `row`'s
    note names, or None."""
    older, old_subjects, old_day = row
    for newer, new_subjects, new_day in read:
        if newer is older or not old_day or not new_day or new_day <= old_day:
            continue
        for words, value in old_subjects:
            match = next((v for w, v in new_subjects if _same(words, w)), None)
            if match is not None and match.lower() != value.lower():
                return Replaced(older, newer, value, old_day)
    return None


_NATURAL = (
    "An older note, from {when}, said {value}.",
    "Before that, on {when}, you had written {value}.",
    "Your earlier note, from {when}, said {value}.",
    "That replaces what you wrote on {when}: {value}.",
    "On {when} it was {value}.",
    "Back on {when}, your note said {value}.",
    "Earlier, on {when}, you noted {value}.",
    "It used to be {value}, going by your note from {when}.",
)
_PROFESSIONAL = (
    "An earlier note, dated {when}, recorded {value}.",
    "This supersedes the entry of {when}, which recorded {value}.",
    "The previous entry, from {when}, stated {value}.",
    "On {when} the notes recorded {value}.",
    "An older entry, dated {when}, gave {value}.",
    "Previously, as of {when}: {value}.",
    "The entry of {when} recorded {value}, since replaced.",
    "The record of {when}, {value}, has since been replaced.",
)


def older_line(replaced: list[Replaced], *, voice: str = "natural", today: date | None = None, seed: int = 0) -> str:
    """One line for the first note left out: what it said, and when."""
    if not replaced:
        return ""
    first = replaced[0]
    today = today or date.today()
    when = ""
    if first.written:
        when = f"{first.written.day} {first.written:%B}" + ("" if first.written.year == today.year else f" {first.written.year}")
    lines = _PROFESSIONAL if voice == "professional" else _NATURAL
    line = lines[seed % len(lines)]
    return line.format(when=when or "an earlier day", value=first.value.rstrip("."))


# --- a window that has closed ---------------------------------------------------------

_WINDOW = re.compile(
    r"\b(?:until|till|through|thru|by the end of|up to)\s+(?:(\d{1,2})(?:st|nd|rd|th)?\s+)?"
    r"(January|February|March|April|May|June|July|August|September|October|November|December)(?:\s+(\d{4}))?\b",
    re.I,
)


@dataclass(frozen=True)
class Lapsed:
    note: dict
    ended: date
    said: str


def window_end(sentence: str, written: date) -> date | None:
    """The last day a sentence says its value holds ("until June" is the end
    of June, "until 12 June" that day), a month before the note's own read as
    the next year; None when it names none."""
    m = _WINDOW.search(sentence or "")
    if not m:
        return None
    month = [name.lower() for name in _MONTHS].index(m.group(2).lower()) + 1
    year = int(m.group(3)) if m.group(3) else written.year + (1 if month < written.month else 0)
    day = int(m.group(1)) if m.group(1) else calendar.monthrange(year, month)[1]
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _lapsed_in(note: dict, written: date | None, asked: frozenset, today: date) -> Lapsed | None:
    for sentence in _sentences(str(note.get("content") or "")) if written else []:
        state, window = _state(sentence), _WINDOW.search(sentence)
        ended = window_end(sentence, written) if window else None
        if state and ended and ended < today and state[0] & asked:
            return Lapsed(note, ended, window.group(0))
    return None


def lapsed(question: str, notes: list[dict], today: date) -> Lapsed | None:
    """The first of `notes` (already the current ones) the question names
    whose own window has closed; None for a question about the past."""
    if recognise.says_past(question):
        return None
    asked = frozenset(w for w in query_understanding.search_terms(question or "") if w not in _VALIDITY)
    return next((found for n in notes if (found := _lapsed_in(n, _day(n), asked, today))), None)


_LAPSED_NATURAL = (
    "That note said it held {said}, which has passed, so it may be out of date.",
    "The note says {said}, and that time has gone, so this may be out of date.",
    "It runs {said} in your note, and that has passed, so it may be out of date.",
    "Your note gives {said}; that has gone by, so it may be out of date.",
    "Worth checking: the note says {said}, which is behind you now, so it may be out of date.",
    "The note gives {said}. That has passed, so what it says may be out of date.",
    "This may be out of date, since the note says {said} and that has passed.",
    "Going by the note it held {said}, which has gone by, so it may be out of date.",
)
_LAPSED_PROFESSIONAL = (
    "The entry states that it holds {said}; that date has passed, so it may be out of date.",
    "The entry gives {said}. That date has passed and the entry may be out of date.",
    "Per the entry, validity runs {said}; that has elapsed, so it may be out of date.",
    "The period given, {said}, has elapsed, so the entry may be out of date.",
    "Note that the entry says {said}, which has passed; it may be out of date.",
    "The entry was valid {said}; that has elapsed and it may be out of date.",
    "As recorded, the entry holds {said}; that date is past, so it may be out of date.",
    "Its stated period, {said}, is over, so the entry may be out of date.",
)


def lapsed_line(found: Lapsed, *, voice: str = "natural", today: date | None = None, seed: int = 0) -> str:
    """One line: the note's own window has closed, so it may be out of date."""
    lines = _LAPSED_PROFESSIONAL if voice == "professional" else _LAPSED_NATURAL
    return lines[seed % len(lines)].format(said=found.said[0].lower() + found.said[1:])
