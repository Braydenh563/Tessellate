"""A question about the one note attached or open, answered from that note's
own record (INBOX 1461, the owner: "when did I make this note?" with a note
attached got the note quoted, then "Oldest first:" with two unrelated notes).

"This note", "this" and "it" with one note attached mean that note. When it
was written, when it was last changed and how long it is are facts the app
holds for the note, so they are said from its record before any search: no
other note is read for them. What it is about and "summarise this" stay the
digest's (`composer_digest.about_this`), read from the attachment alone.
"""

from __future__ import annotations

import re
from datetime import date, datetime

from tessellate.ai import realise, study

#: A question about the note itself, not a subject in it: the asking words,
#: then "this", "it" or "this note" ("when did I make this note", "when was
#: it last edited", "how long is this").
_THIS = r"(?:this|it|that|the) ?(?:note|one|entry|page)?"
_KINDS: tuple[tuple[str, re.Pattern], ...] = (
    ("edited", re.compile(
        rf"^when (?:did i|was|have i|has) (?:last )?(?:{_THIS} )?(?:last )?(?:edit|edited|change|changed|update|updated|modified|modify)\b"
        rf"(?: {_THIS})?(?: last)?$", re.I)),
    ("made", re.compile(
        rf"^when (?:did i|was|have i) (?:{_THIS} )?(?:make|made|write|written|wrote|create|created|start|started|save|saved|add|added)\b"
        rf"(?: {_THIS})?$|^what (?:day|date) (?:did i|was) (?:{_THIS} )?(?:write|written|make|made)(?: {_THIS})?$|^how old is {_THIS}$", re.I)),
    ("length", re.compile(
        rf"^how (?:long|big) is {_THIS}$|^how many words (?:is|are in|does) {_THIS}(?: have)?$|^what(?:'s| is) the word count(?: of {_THIS})?$", re.I)),
)


NOTHING_ATTACHED = "Which note do you mean? Open it, or attach it to your message, and ask again."


def kind(question: str) -> str:
    """"made", "edited" or "length" for a question about the note itself, else ""."""
    asked = " ".join(re.sub(r"[?.!]+", " ", question or "").split()).lower()
    return next((name for name, pattern in _KINDS if pattern.match(asked)), "")


def _day(moment: datetime | None, today: date) -> str:
    if moment is None:
        return ""
    day = moment.date()
    said = f"{day.day} {realise._MONTHS[day.month - 1]}" + ("" if day.year == today.year else f" {day.year}")
    near = realise.relative_day(day, today)
    #: "today" and "yesterday" say more than the date; a date says it exactly.
    return near if near in ("today", "yesterday") else f"on {said}"


def _which(content: str) -> str:
    """The note named the way the person would know it: its heading, or the
    words it starts with."""
    from tessellate.entry import manager

    heading = manager.extract_title(content)
    if heading:
        return f"“{realise.cut_title(heading, 60)}”"
    start = study.title_of(content, size=60)
    #: Its first clause when that says enough: "I just missed the bus to uni today".
    clause = re.split(r",\s", start, maxsplit=1)[0].rstrip("…")
    return f"the note that starts “{clause if len(clause.split()) >= 4 else start}”"


def _words(content: str) -> int:
    return len(re.findall(r"[\w'’-]+", study.clean(content)))


def answer(question: str, content: str, created: datetime | None, edited: datetime | None, today: date) -> str | None:
    """The sentence that answers `question` about one note, or None when the
    question is not one of `kind`'s. `edited` is when a person last changed
    it (`Entry.edited_at`, None when never), in the person's own time."""
    asked = kind(question)
    if not asked or not content:
        return None
    which = _which(content)
    made = _day(created, today)
    if asked == "made":
        return f"You wrote it {made}: {which}." if made else None
    if asked == "edited":
        same = created is None or edited is None or abs((edited - created).total_seconds()) < 60
        changed = _day(edited, today)
        if same or not changed:
            return f"You haven't changed it since you wrote it {made}: {which}." if made else None
        return f"You last changed it {changed}, and wrote it {made}."
    words = _words(content)
    minutes = round(words / 230)
    read = "about a minute" if minutes <= 1 else f"about {realise.count_noun(minutes, 'minute')}"
    return f"It is {realise.count_noun(words, 'word')}, {read} to read: {which}."
