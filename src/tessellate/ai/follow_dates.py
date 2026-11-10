"""A day counted from, or moved off, the one the last answer showed (INBOX 1730
F3 f and g, composer audit 2026-11-10).

"remind me the day before", "and a week before that" count from the date the
answer before stated (a fact's date, or the reminder it just set); "move it to
the 16th" after a reminder moves that reminder, never the category "the 16th".
Each gives the sentence the acts already parse (`follow_items.read` swaps it in
for the question) or a line that asks, and None when the turn is neither.

Every date word is read by `ai/recognise.py`: `days_apart` for the span,
`resolve` for a day, `date_mentions` for the dates an answer states.
"""

from __future__ import annotations

import calendar
import re
from datetime import datetime, timedelta

from tessellate.ai import phrasing, recognise

Reading = tuple[str | None, str | None]

_PLAIN = re.compile(r"\[([^\]]+)\]\([^)]*\)|[*_`]+")
_FROM_NOTE = re.compile(r"\bfrom your (?P<title>.+?) note\b|\[\*\*(?P<bold>[^*\]]+)\*\*\]", re.I)
_REMIND = re.compile(r"^(?:please )?(?:and |also |plus )*(?:remind me|set (?:a|another) reminder|(?:a|another) reminder)\b(?P<rest>.*)$", re.I)
_AND_SPAN = re.compile(r"^(?:and |also |plus )+(?P<rest>.+)$", re.I)
_MOVE = re.compile(
    r"^(?:please )?(?:move|push|shift|change|reschedule|set|make)\s+(?:it|that|this)(?:\s+(?:back|forward))?(?:\s+(?:to|for|on))?\s+(?P<when>.+?)\s*[.!]?$",
    re.I,
)

_DATED_ASKS = (
    "That date is written in the note, and I do not edit a note's words from here. I can remind you on {day} instead. What should it say?",
    "I leave a note's own date as it is. A reminder on {day} works, though: what is it for?",
    "The note keeps its date. Shall I remind you on {day}? Tell me what it is about.",
)
_DATED_UNTITLED = (
    "I can remind you on {day}. What should the reminder say?",
    "{day} it is. What is the reminder for?",
)


def _day(at: datetime, now: datetime) -> str:
    return f"{at.day} {calendar.month_name[at.month]}" + ("" if at.year == now.year else f" {at.year}")


def _clock(at: datetime) -> str:
    hour = at.hour % 12 or 12
    return f"{hour}{'pm' if at.hour >= 12 else 'am'}" if not at.minute else f"{hour}:{at.minute:02d}{'pm' if at.hour >= 12 else 'am'}"


def _stated_clock(phrase: str, now: datetime) -> bool:
    """Whether `phrase` names a time of day: read from two different clocks, a day
    alone lands on the clock it was read against."""
    one = recognise.resolve(phrase, now.replace(hour=3, minute=17))
    return one is not None and (one.hour, one.minute) != (3, 17)


def _anchor(history: list[dict], last, now: datetime) -> tuple[datetime, str, str, bool] | None:  # noqa: ANN001
    """(the day counted from, what it is for, its note's title, whether it is a set reminder),
    from the answer before: a reminder just set, else the one date a fact stated."""
    if last is not None and last.kind == "reminder":
        at = recognise.resolve(last.when, now)
        return (at, last.title, "", True) if at else None
    answer = _PLAIN.sub(lambda m: m.group(1) or "", str((history or [{}])[-1].get("answer") or ""))
    frame = (history or [{}])[-1].get("frame") or {}
    #: The frame knows the answer's subject date even when the rows it lists state others.
    framed = {str(d) for d in frame.get("dates") or []}
    days = {(m, d) for _y, m, d, _w in recognise.date_mentions(answer) if m}
    if len(framed) == 1:
        _year, month, day = (int(part) for part in next(iter(framed)).split("-"))
    elif len(days) == 1:
        month, day = next(iter(days))
    else:
        return None
    at =recognise.resolve(f"{day} {calendar.month_name[month]}", now)
    named = _FROM_NOTE.search(answer)
    return (at, "", (named.group("title") or named.group("bold")) if named else "", False) if at else None


def _about(rest: str) -> tuple[str, str]:
    """("Dentist", "the day before") for "about Dentist the day before": the
    subject the person named, then the span; ("", rest) when no span follows."""
    words = rest.split()
    if not words or words[0].lower() != "about":
        return "", rest
    for cut in range(2, len(words)):
        tail = " ".join(words[cut:])
        if recognise.days_apart(tail) is not None:
            return " ".join(words[1:cut]).strip(" ,"), tail
    return "", rest


def _relative(question: str, history: list[dict], last, now: datetime) -> Reading:  # noqa: ANN001
    """"remind me the day before", "and a week before that"."""
    said = " ".join(question.split())
    found = _REMIND.match(said) or _AND_SPAN.match(said)
    rest = found.group("rest") if found else ""
    subject, rest = _about(rest)
    span = recognise.days_apart(rest) if found else None
    if span is None or len(rest.split()) > 8:
        return None, None
    anchor = _anchor(history, last, now)
    if anchor is None:
        return None, None
    at, what, title, is_reminder = anchor
    target = at + timedelta(days=span)
    if is_reminder:
        return f"remind me to {what} on {_day(target, now)} at {_clock(target)}", None
    title = title or subject
    if not title:
        return None, phrasing.choose(_DATED_UNTITLED, said, [str(t.get("answer") or "") for t in history], "span").format(day=_day(target, now))
    return f"remind me about the {title} note on {_day(target, now)} at 9am", None


def _moved(question: str, history: list[dict], last, now: datetime) -> Reading:  # noqa: ANN001
    """"move it to the 16th": the reminder just set, on that day at its own time."""
    found = _MOVE.match(" ".join(question.split()))
    if not found:
        return None, None
    to = recognise.resolve(found.group("when"), now)
    if to is None:
        return None, None
    anchor = _anchor(history, last, now)
    if anchor is None:
        return None, None
    at, what, _title, is_reminder = anchor
    if not is_reminder:
        recent = [str(t.get("answer") or "") for t in history]
        return None, phrasing.choose(_DATED_ASKS, question, recent, "move").format(day=_day(to, now))
    if not _stated_clock(found.group("when"), now):
        to = to.replace(hour=at.hour, minute=at.minute)
    return f"move the reminder {what} to {_day(to, now)} at {_clock(to)}", None


def read(question: str, history: list[dict], now: datetime, last) -> Reading:  # noqa: ANN001
    """(the sentence the question stands for, the line that asks), either or neither."""
    for reader in (_relative, _moved):
        said, ask = reader(question, history, last, now)
        if said or ask:
            return said, ask
    return None, None
