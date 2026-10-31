"""What "yesterday" meant, on the day it was written (roadmap §10A).

Notes are full of relative time, "tomorrow", "last week", "in three days" , 
and every one of those phrases is correct when it is typed and misleading
forever afterwards. Nothing recorded what they resolved to, so a note saying
"the deadline is next Friday" is unanswerable a month later, and the AI
answering questions about it can only guess.

This resolves them at capture and stores the answer alongside the note.

**Deliberately deterministic.** `ai/reminder_parser.py` asks the model to do
the same job for a reminder, and that is the right trade there: one reminder,
typed on purpose, worth a model call. This runs on *every* note that is saved,
including when Ollama is off, the app's second design principle, so it is
regular expressions and arithmetic, and nothing here can make a save fail or
slow.

The reference clock is the user's, not the server's. "Tonight" resolved
against UTC on a machine in Brisbane is the wrong night, which is exactly the
bug the reminder columns were fixed for.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

# How exact the phrase was. A note saying "last week" did not mean a day, and
# showing it as one would be inventing precision the writer did not use.
DAY = "day"
WEEK = "week"
MONTH = "month"
YEAR = "year"
# A day with a clock said beside it: "on Friday at 3pm" (audit 2026-10-05,
# UX-02). Before, the 3pm was dropped and the day stored as a midnight that a
# browser west of UTC then drew on the evening before.
MINUTE = "minute"

MAX_MENTIONS = 8  # a note is not a calendar; this only guards runaway text

_WEEKDAYS = {
    "monday": 0, "mon": 0,
    "tuesday": 1, "tue": 1, "tues": 1,
    "wednesday": 2, "wed": 2,
    "thursday": 3, "thu": 3, "thurs": 3,
    "friday": 4, "fri": 4,
    "saturday": 5, "sat": 5,
    "sunday": 6, "sun": 6,
}

_NUMBER_WORDS = {
    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
    "twelve": 12, "couple of": 2, "few": 3,
}

_UNIT_DAYS = {"day": 1, "week": 7, "fortnight": 14}


@dataclass(frozen=True)
class Mention:
    """One phrase, and the date it meant when it was written."""

    phrase: str
    at: date
    precision: str
    #: The clock said beside a day phrase, as written (the writer's own wall
    #: clock, no zone): set only with precision MINUTE.
    time: time | None = None


def _monday(day: date) -> date:
    return day - timedelta(days=day.weekday())


def _add_months(day: date, months: int) -> date:
    """Month arithmetic without a dependency. The 31st of a short month lands
    on its last day rather than overflowing into the next one."""
    total = day.month - 1 + months
    year = day.year + total // 12
    month = total % 12 + 1
    last = [31, 29 if year % 4 == 0 and (year % 100 or year % 400 == 0) else 28,
            31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1]
    return date(year, month, min(day.day, last))


def _count(word: str) -> int | None:
    word = word.strip().lower()
    if word.isdigit():
        return int(word)
    return _NUMBER_WORDS.get(word)


_MONTHS = {
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3,
    "april": 4, "apr": 4, "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7,
    "august": 8, "aug": 8, "september": 9, "sept": 9, "sep": 9, "october": 10,
    "oct": 10, "november": 11, "nov": 11, "december": 12, "dec": 12,
}
_MONTH_PATTERN = "|".join(sorted(_MONTHS, key=len, reverse=True))
#: A weekday said before a date ("Friday 16 October") is part of the phrase,
#: so the date, not "on friday", is what the note is about.
_WEEKDAY_BEFORE = r"(?:(?:" + "|".join(sorted(_WEEKDAYS, key=len, reverse=True)) + r")\.?,?\s+)?"


def _written_date(year: str | None, month: int, day: int, today: date):
    """A date the note spells out. Without a year it is the occurrence
    nearest the day it was written: "3 March" typed in July is next March."""
    if year:
        return date(int(year), month, day), DAY
    nearest = min(
        (date(today.year + shift, month, day) for shift in (-1, 0, 1)),
        key=lambda candidate: abs((candidate - today).days),
    )
    return nearest, DAY


def _day_of_month(m, t):
    shift = {"last": -1, "next": 1, "this": 0}[m.group(2).lower()]
    month = _add_months(t.replace(day=1), shift)
    return date(month.year, month.month, int(m.group(1))), DAY


def _weekday_late(m, t):
    return _weekday(m, t)


# Every pattern gets the match and "today" and returns (date, precision).
# Order matters: the longer phrase has to be tried before the shorter one it
# contains, or "the day after tomorrow" resolves as "tomorrow".
_RULES: list[tuple[str, object]] = [
    # A date written out ("2026-10-25", "Friday 16 October 2026", "Oct 3rd"):
    # first, so the weekday inside it is never read as "on friday".
    (r"(?<![\d-])(\d{4})-(\d{2})-(\d{2})(?![\d-])",
     lambda m, t: (date(int(m.group(1)), int(m.group(2)), int(m.group(3))), DAY)),
    (_WEEKDAY_BEFORE + r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?(" + _MONTH_PATTERN + r")\b\.?(?:,?\s+(\d{4})\b)?",
     lambda m, t: _written_date(m.group(3), _MONTHS[m.group(2).lower()], int(m.group(1)), t)),
    (_WEEKDAY_BEFORE + r"\b(" + _MONTH_PATTERN + r")\b\.?\s+(\d{1,2})(?:st|nd|rd|th)?\b(?!:)(?:,?\s+(\d{4})\b)?",
     lambda m, t: _written_date(m.group(3), _MONTHS[m.group(1).lower()], int(m.group(2)), t)),
    (r"the day after tomorrow", lambda m, t: (t + timedelta(days=2), DAY)),
    (r"the day before yesterday", lambda m, t: (t - timedelta(days=2), DAY)),
    (r"tomorrow(?: morning| afternoon| evening| night)?",
     lambda m, t: (t + timedelta(days=1), DAY)),
    (r"yesterday(?: morning| afternoon| evening)?",
     lambda m, t: (t - timedelta(days=1), DAY)),
    (r"last night", lambda m, t: (t - timedelta(days=1), DAY)),
    (r"(?:today|tonight|this (?:morning|afternoon|evening))",
     lambda m, t: (t, DAY)),
    (r"last week", lambda m, t: (_monday(t) - timedelta(days=7), WEEK)),
    (r"next week", lambda m, t: (_monday(t) + timedelta(days=7), WEEK)),
    (r"this week", lambda m, t: (_monday(t), WEEK)),
    #: "the 14th of next month": that day, not the month (audit 1031 N8).
    (r"the (\d{1,2})(?:st|nd|rd|th)(?: day)? of (last|next|this) month",
     lambda m, t: _day_of_month(m, t)),
    (r"last month", lambda m, t: (_add_months(t, -1), MONTH)),
    (r"next month", lambda m, t: (_add_months(t, 1), MONTH)),
    (r"this month", lambda m, t: (t, MONTH)),
    (r"last year", lambda m, t: (date(t.year - 1, t.month, 1), YEAR)),
    (r"next year", lambda m, t: (date(t.year + 1, t.month, 1), YEAR)),
    # "in three days", "in 2 weeks", "in a fortnight"
    (r"in (\d{1,3}|a|an|one|two|three|four|five|six|seven|eight|nine|ten|"
     r"eleven|twelve|few|couple of) (day|week|fortnight)s?",
     lambda m, t: _offset(m, t, forward=True)),
    (r"in (\d{1,3}|a|an|one|two|three|four|five|six|seven|eight|nine|ten|"
     r"eleven|twelve|few|couple of) months?",
     lambda m, t: (_add_months(t, _count(m.group(1)) or 0), MONTH)),
    # "three days ago", "a week ago"
    (r"(\d{1,3}|a|an|one|two|three|four|five|six|seven|eight|nine|ten|eleven|"
     r"twelve|few|couple of) (day|week|fortnight)s? ago",
     lambda m, t: _offset(m, t, forward=False)),
    (r"(\d{1,3}|a|an|one|two|three|four|five|six|seven|eight|nine|ten|eleven|"
     r"twelve|few|couple of) months? ago",
     lambda m, t: (_add_months(t, -(_count(m.group(1)) or 0)), MONTH)),
    # "last friday", "next tues", "this monday", "on wednesday"
    # The lambda is NOT redundant, though CodeQL's `py/unnecessary-lambda`
    # says so (#47) and the suggested `_weekday` is a NameError: this table is
    # built at import time and `_weekday` is defined below it. The wrapper
    # defers the lookup to call time, which is the only reason the module
    # imports at all. Checked by replacing it and watching the suite fail.
    (r"(last|next|this|on) (" + "|".join(_WEEKDAYS) + r")\b", _weekday_late),
]

_COMPILED = [(re.compile(pattern, re.IGNORECASE), resolve) for pattern, resolve in _RULES]


def _offset(match: re.Match, today: date, forward: bool):
    count = _count(match.group(1))
    if count is None:
        return None
    days = count * _UNIT_DAYS[match.group(2).lower()]
    return (today + timedelta(days=days if forward else -days), DAY)


def _weekday(match: re.Match, today: date):
    """"Next Friday" is the Friday of next week; "on Friday" is the coming one.

    Both readings exist in ordinary speech and neither is wrong. The rule is
    written down here so the answer is at least consistent, and the phrase is
    always shown next to the date so a reader can disagree with it.
    """
    which, name = match.group(1).lower(), match.group(2).lower()
    target = _WEEKDAYS[name]
    ahead = (target - today.weekday()) % 7
    if which == "last":
        behind = (today.weekday() - target) % 7 or 7
        return (today - timedelta(days=behind), DAY)
    if which == "next":
        return (_monday(today) + timedelta(days=7 + target), DAY)
    return (today + timedelta(days=ahead), DAY)  # "this"/"on": the coming one


# A clock beside a day phrase. A bare number counts only with "at" before it or
# a colon or am/pm in it, the rule `ai/when._clock` uses, so "on Friday we had 3
# meetings" and "tomorrow, 4 people" keep their day alone.
_MERIDIEM = r"(?:am|pm|a\.m\.|p\.m\.)"
_CLOCK_WORDS = r"(?:noon|midday|midnight)"
_CLOCK_AFTER = re.compile(
    rf"^,?\s*(?:(?:at|@|by|around|from)\s*)?(?:{_CLOCK_WORDS}\b|"
    rf"(?P<h>\d{{1,2}})(?::(?P<m>\d{{2}}))?\s*(?P<ap>{_MERIDIEM})?(?![\w:]))",
    re.IGNORECASE,
)
_CLOCK_BEFORE = re.compile(
    rf"(?:\b(?:at|by|around|from)\s*|@\s*)?(?:\b{_CLOCK_WORDS}|\b"
    rf"(?P<h>\d{{1,2}})(?::(?P<m>\d{{2}}))?\s*(?P<ap>{_MERIDIEM})?)\s+$",
    re.IGNORECASE,
)


def _clock(found: re.Match, evening: bool) -> time | None:
    """The time a `_CLOCK_*` match says, or None if it is not one."""
    said = found.group(0).strip(" ,").lower()
    if found.group("h") is None:
        if "midnight" in said:
            return time(0, 0)
        return time(12, 0)  # noon, midday
    hour, minute = int(found.group("h")), int(found.group("m") or 0)
    meridiem = (found.group("ap") or "").replace(".", "").lower()
    leading = said.split()[0] if said.split() else ""
    if not meridiem and found.group("m") is None and leading not in ("at", "@", "by", "around", "from"):
        return None  # a bare number with nothing saying it is a time
    if hour > 23 or minute > 59 or (meridiem and not 1 <= hour <= 12):
        return None
    if meridiem == "am":
        hour = 0 if hour == 12 else hour
    elif meridiem == "pm":
        hour = hour if hour == 12 else hour + 12
    elif 1 <= hour <= 11 and (evening or hour <= 6):
        # The rule `ai/when` writes down: a bare 1 to 6 is afternoon, 7 to 11
        # morning, unless the phrase says evening or tonight.
        hour += 12
    return time(hour, minute)


def _with_clock(text: str, span: tuple[int, int], mention: Mention) -> tuple[tuple[int, int], Mention]:
    """The mention widened to a clock said right after or right before it."""
    if mention.precision != DAY:
        return span, mention
    evening = bool(re.search(r"evening|night|tonight", mention.phrase, re.IGNORECASE))
    start, end = span
    after = _CLOCK_AFTER.match(text[end:])
    if after and after.group(0).strip(" ,"):
        at = _clock(after, evening)
        if at is not None:
            end += len(after.group(0).rstrip())
            return (start, end), Mention(text[start:end].strip(), mention.at, MINUTE, at)
    before = _CLOCK_BEFORE.search(text[max(0, start - 16):start])
    if before and before.group(0).strip():
        at = _clock(before, evening)
        if at is not None:
            start -= len(before.group(0))
            return (start, end), Mention(text[start:end].strip(), mention.at, MINUTE, at)
    return span, mention


def find(text: str, now: datetime | date) -> list[Mention]:
    """Every temporal phrase in `text`, resolved against `now`.

    Overlapping matches are resolved in favour of the earliest, longest one,
    so "the day after tomorrow" is never also counted as "tomorrow".
    """
    today = now.date() if isinstance(now, datetime) else now
    claimed: list[tuple[int, int]] = []
    found: list[tuple[int, Mention]] = []
    for pattern, resolve in _COMPILED:
        for match in pattern.finditer(text or ""):
            span = match.span()
            if any(span[0] < end and start < span[1] for start, end in claimed):
                continue
            try:
                answer = resolve(match, today)
            except (ValueError, KeyError, TypeError):
                continue  # a phrase we thought we understood and didn't
            if answer is None:
                continue
            at, precision = answer
            span, mention = _with_clock(text or "", span, Mention(match.group(0), at, precision))
            claimed.append(span)
            found.append((span[0], mention))
    found.sort(key=lambda pair: pair[0])
    return [mention for _, mention in found[:MAX_MENTIONS]]
