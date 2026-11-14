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

from tessellate.ai import recognise_questions
from tessellate.core import clock
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
    #: What the newer note says of the subject (the contradiction answer, L-chat-8).
    now: str = ""


def _state(sentence: str) -> tuple[frozenset, str] | None:
    """A state sentence's subject words and its value, or None."""
    m = _COLON.match(sentence) or _COPULA.match(sentence)
    if not m:
        return None
    words = frozenset(w for w in query_understanding.search_terms(m.group(1)) if w not in _VALIDITY)
    return (words, m.group(2).strip()) if words else None


def _sentences(text: str) -> list[str]:
    return [s.strip().rstrip(".!?") for s in _SENTENCE.split(text or "")]


_RELATION = re.compile(r"^(?:my|our|his|her|their|your)\s+\w+$", re.I)
_DAYS = re.compile(r"\b(?:mon|tues|wednes|thurs|fri|satur|sun)day\b|\b(?:january|february|march|april|may|june|july|august|september|october|november|december)\b", re.I)


def _kind(value: str) -> str:
    """What sort of thing a value is: a relation ("my sister") never
    changes into a price, and a price is not a person."""
    if _RELATION.match(value.strip()):
        return "relation"
    if re.search(r"\d", value):
        return "number"
    return "day" if _DAYS.search(value) else "text"


def _form(sentence: str) -> str:
    return "colon" if _COLON.match(sentence) else "copula"


def _subjects(text: str) -> list[tuple[frozenset, str, str]]:
    """Each state sentence's subject words, its value and its clause form."""
    rows = [(_state(s), _form(s)) for s in _sentences(text)]
    return [(state[0], state[1], form) for state, form in rows if state]


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
    if recognise_questions.says_past(question) or len(notes) < 2:
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
    return [(n, [row for row in _subjects(str(n.get("content") or "")) if row[0] & asked], _day(n)) for n in notes]


def _replaced_by(row: tuple, read: list[tuple]) -> Replaced | None:
    """The first newer note that says something else of a subject `row`'s
    note names, or None."""
    older, old_subjects, old_day = row
    for newer, new_subjects, new_day in read:
        if newer is older or not old_day or not new_day or new_day <= old_day:
            continue
        for words, value, form in old_subjects:
            match = next((v for w, v, f in new_subjects if _same(words, w) and _alike(value, form, v, f)), None)
            if match is not None and match.lower() != value.lower():
                return Replaced(older, newer, value, old_day, match)
    return None


#: The newest notes `changes` reads: every pair is two notes' subjects, so the
#: cost grows with the square, and an old change of mind is the least asked for.
_CHANGES_NOTES = 400


def changes(notes: list[dict]) -> list[Replaced]:
    """Every subject a newer note says something else of, over the whole
    notebook (no question to narrow it): "do my notes contradict each other"
    (L-chat-8). Oldest first; each older note once, with the next note that
    replaced it."""
    dated = sorted((n for n in notes if _day(n)), key=_day)[-_CHANGES_NOTES:]
    read = [(n, _subjects(str(n.get("content") or "")), _day(n)) for n in dated]
    return [r for r in (_replaced_by(row, read) for row in read if row[1]) if r and _one_thing(r)]


def _one_thing(found: Replaced) -> bool:
    """Two notes about one thing: a note that is the state itself ("My
    address is now 4 Birch Road"), or two whose first lines match. Two
    recipes each with "Ingredients:" are two things, not a change of mind."""
    firsts = [_sentences(str(n.get("content") or ""))[0] for n in (found.older, found.newer)]
    if all(_state(first) for first in firsts):
        return True
    a, b = (frozenset(query_understanding.search_terms(first)) for first in firsts)
    return bool(a | b) and _same(a, b)


#: "contradict each other about the passport", "the passport contradiction", "inconsistencies on my passport".
_ASK_TAIL = re.compile(r"\b(?:about|on|over|regarding|concerning|around|with)\s+(?:(?:my|the|our)\s+)?(?P<s>[^?.!,]+?)\W*$", re.I)
_ASK_HEAD = re.compile(r"\b(?:the|my|our)\s+(?P<s>[\w'-]+(?:\s+[\w'-]+){0,2}?)\s+(?:contradictions?|inconsistenc(?:y|ies)|conflicts?|disagreements?)\b", re.I)
_ASK_NOISE = frozenset({"note", "each", "other", "one", "another", "contradict", "contradiction", "inconsist", "conflict", "disagre", "chang", "mind"})


def ask_subject(question: str) -> str:
    """The words of the subject a contradiction ask names, or "" for the whole
    notebook ("do my notes contradict each other" names none; L-chat-245)."""
    from tessellate.ai import study

    found = _ASK_TAIL.search(" ".join(question.split())) or _ASK_HEAD.search(" ".join(question.split()))
    words = re.findall(r"[\w'-]+", found.group("s")) if found else []
    return " ".join(w for w in words if study.content_stems(w) and not set(study.content_stems(w)) <= _ASK_NOISE)


def about(subject: str, *texts: str) -> bool:
    """Whether every word of `subject` (stemmed) is in the texts."""
    from tessellate.ai import study

    return set(study.content_stems(subject)) <= set(study.content_stems(" ".join(texts)))


def changes_line(found: Replaced, today: date) -> str:
    """One change said with both days and both values, newest first."""
    newer = _day(found.newer)
    new_day = _said_day(newer, today) if newer else "a later day"
    old_day = _said_day(found.written, today) if found.written else "an earlier day"
    said = f"your note of {new_day} says {_you(found.now)}, and an older one, from {old_day}, said {_you(found.value)}."
    subject = _subject_of(found)
    return f"{subject}: {said}" if subject else said[0].upper() + said[1:]


def _subject_of(found: Replaced) -> str:
    """The words the older note says its changed value of ("Uni days this semester")."""
    for sentence in _sentences(str(found.older.get("content") or "")):
        m = _COLON.match(sentence) or _COPULA.match(sentence)
        if m and m.group(2).strip() == found.value:
            words = _you(re.sub(r"^(My|Our|Mine)\b", lambda w: w.group(1).lower(), m.group(1).strip()))
            return words[0].upper() + words[1:]
    return ""


def _alike(old: str, old_form: str, new: str, new_form: str) -> bool:
    """A value replaces another only as the same sort of thing (audit 1031
    C2: a gift list's "Sara: a jazz record" is no new value of "Sara is my
    sister"): the same kind (a price for a price, days for days), or the same
    clause form when neither is a relation."""
    a, b = _kind(old), _kind(new)
    if "relation" in (a, b):
        return a == b
    return a == b != "text" or old_form == new_form


_WHEN_ASK = re.compile(r"^\W*(?:when|what\s+(?:day|date))\b", re.I)


def _dated_sentences(notes: list[dict], asked: frozenset, today: date) -> list[tuple[date, dict, date]]:
    """(the day a sentence names, its note, the day the note was written) for each
    sentence of `notes` that holds every word asked (its note's title counts)."""
    from tessellate.ai import composer_ahead

    held = []
    for note in notes:
        written = _day(note)
        title = str(note.get("content") or "").lstrip().split("\n", 1)[0].lstrip("# ")
        for sentence in _sentences(str(note.get("content") or "")) if written else []:
            day = composer_ahead.date_in(sentence, today)
            if day is not None and asked <= set(query_understanding.search_terms(f"{title} {sentence}")):
                held.append((day, note, written))
    return held


def _asks_when(question: str, text: str, notes: list[dict], today: date) -> tuple[frozenset, date] | None:
    """(the words asked, the date the answer gave) for a when-question over several notes, else None."""
    from tessellate.ai import composer_ahead

    asked = frozenset(w for w in query_understanding.search_terms(question or "") if w not in _VALIDITY)
    said = composer_ahead.date_in(text.split("\n", 1)[0], today)
    ok = _WHEN_ASK.match(question or "") and asked and said and len(notes) > 1 and not recognise_questions.says_past(question)
    return (asked, said) if ok else None


def older_dates(question: str, text: str, notes: list[dict], today: date) -> list[Replaced]:
    """The older date of the same event, for a when-question: the answer's
    date is one a note says, and an earlier note names another date for the
    same subject ("the launch is 14 December", then "slips to 11 January").
    The newest dated fact leads (audit 2 G1); the older is said once."""
    asks = _asks_when(question, text, notes, today)
    held = _dated_sentences(notes, asks[0], today) if asks else []
    newest = max((h for h in held if h[0] == asks[1]), key=lambda h: h[2], default=None) if asks else None
    older = [h for h in held if newest and h[0] != asks[1] and h[2] < newest[2]]
    if not older:
        return []
    day, note, written = max(older, key=lambda h: h[2])
    return [Replaced(note, newest[1], f"{day.day} {_MONTHS[day.month - 1]}", written)]


#: "has the launch date changed", "did the meeting move": the subject is what comes between the verb and the change.
_CHANGED_ASK = re.compile(
    r"^\W*(?:has|have|did|is|was|will)\s+(?:the\s+|my\s+|our\s+)?(?P<subject>.+?)\s+(?:been\s+)?"
    r"(?:changed|change|moved|move|slipped|slip|shifted|shift|pushed(?:\s+back)?|delayed|rescheduled|postponed)(?:\s+again)?\W*$",
    re.I,
)
_DATE_WORDS = frozenset({"date", "time", "day"})


def _said_day(day: date, today: date) -> str:
    return f"{day.day} {_MONTHS[day.month - 1]}" + ("" if day.year == today.year else f" {day.year}")


def changed(question: str, notes: list[dict], today: date) -> str:
    """The answer to "has the launch date changed": yes, with the day it was and the day it is, when two
    notes written on different days give different days for the subject; no, when every note that gives
    one gives the same; "" when the notes cannot tell (one note, or no day). The newest note leads."""
    found = _CHANGED_ASK.match(question or "")
    asked = frozenset(w for w in query_understanding.search_terms(found["subject"]) if w not in _VALIDITY | _DATE_WORDS) if found else frozenset()
    held = _dated_sentences(notes, asked, today) if asked else []
    if len({id(h[1]) for h in held}) < 2:
        return ""
    newest = max(held, key=lambda h: h[2])
    older = [h for h in held if h[2] < newest[2] and h[0] != newest[0]]
    if not older:
        return f"No, your notes give the same day: {_said_day(newest[0], today)}." if len({h[0] for h in held}) == 1 else ""
    before = max(older, key=lambda h: h[2])
    return f"Yes, from {_said_day(before[0], today)} to {_said_day(newest[0], today)}. Your note of {_said_day(newest[2], today)} has the new day; your note of {_said_day(before[2], today)} had the old one."


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


def _you(value: str) -> str:
    """A note's first-person value said to the person who wrote it ("my
    sister" is "your sister"), never spliced in as written."""
    for first, second in ((r"\bI am\b", "you are"), (r"\bI'm\b", "you are"), (r"\bI\b", "you"), (r"\bmy\b", "your"), (r"\bmine\b", "yours"), (r"\bme\b", "you")):
        value = re.sub(first, second, value)
    return value


def older_line(replaced: list[Replaced], *, voice: str = "natural", today: date | None = None, seed: int = 0) -> str:
    """One line for the first note left out: what it said, and when."""
    if not replaced:
        return ""
    first = replaced[0]
    today = today or clock.today()
    when = ""
    if first.written:
        when = f"{first.written.day} {first.written:%B}" + ("" if first.written.year == today.year else f" {first.written.year}")
    lines = _PROFESSIONAL if voice == "professional" else _NATURAL
    line = lines[seed % len(lines)]
    return line.format(when=when or "an earlier day", value=_you(first.value.rstrip(".")))


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
    if recognise_questions.says_past(question):
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
