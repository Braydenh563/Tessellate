"""How far off a date in a fact is (R9-17): "Mum's birthday is 2 December" is said "in 23 days", not "written on
11 August, about three months ago". Only a day and a month said in the fact, and only one still ahead."""

from __future__ import annotations

import calendar

import re
from datetime import date

_MONTHS = ("january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december")
_NAMES = "|".join(_MONTHS)
_DAY_FIRST = re.compile(rf"\b(?P<d>\d{{1,2}})(?:st|nd|rd|th)?(?: of)? (?P<m>{_NAMES})\b(?:,? (?P<y>\d{{4}}))?", re.IGNORECASE)
_MONTH_FIRST = re.compile(rf"\b(?P<m>{_NAMES}) (?P<d>\d{{1,2}})(?:st|nd|rd|th)?\b(?:,? (?P<y>\d{{4}}))?", re.IGNORECASE)


def date_in(fact: str, today: date) -> date | None:
    found = _DAY_FIRST.search(fact) or _MONTH_FIRST.search(fact)
    if not found:
        return _abbreviated(fact, today)
    try:
        return date(int(found.group("y") or today.year), _MONTHS.index(found.group("m").lower()) + 1, int(found.group("d")))
    except ValueError:
        return None


def _abbreviated(fact: str, today: date) -> date | None:
    """"Thu 12 Nov 9:30": the day the one reader finds when the month is not spelled out (bt-compcomp-1109 item 3)."""
    from tessellate.ai import recognise

    for start, end, phrase in recognise.find(fact):
        found = recognise.span(phrase, today, "future") if phrase[:1].isdigit() else None
        if found and found[0] == found[1] and found[2] == "day":
            return found[0]
    return None


def distance(fact: str, today: date) -> str:
    """"in 23 days" for a fact whose day is still ahead, else ""."""
    day = date_in(fact, today)
    if day is None or day < today:
        return ""
    days = (day - today).days
    if days == 0:
        return "today"
    if days == 1:
        return "tomorrow"
    return f"in {days} days" if days <= 60 else f"in about {round(days / 30)} months"


def _clock_word(text: str) -> str:
    """The clock the date's own words carry ("9:30", "8am"), as written; "" when it names none. The recogniser read
    the date; this only carries its words over."""
    for token in text.split():
        word = token.rstrip(",.")
        if any(c.isdigit() for c in word) and (":" in word or word.lower().endswith(("am", "pm"))):
            return word
    return ""


def _first_date(fact: str, today: date):  # noqa: ANN202
    """(where it starts, its last span) for the first single date in `fact`, or None. A weekday span ("Thu")
    beside the span after it ("12 Nov 9:30") is one date; the reader's weekday span can take the word before it
    ("coming Wed"), so the start is the weekday word itself."""
    from datetime import datetime, time

    from tessellate.ai import recognise

    spans = [x for x in recognise.recognise(fact, now=datetime.combine(today, time(12)), tense="future") if not x.rank and x.kind in ("date", "datetime")]
    for i, span in enumerate(spans):
        if any(c.isdigit() for c in span.text):
            return span.start, span
        after = spans[i + 1] if i + 1 < len(spans) else None
        if after is not None and 0 <= after.start - span.end <= 2:
            return span.start + len(span.text) - len(span.text.split()[-1]), after
    return None


def long_form(fact: str, today: date) -> str:
    """`fact` with its first date written long: "Thu 12 Nov 9:30" as "Thursday 12 November, 9:30", "on 11 November"
    as "on Wednesday 11 November" (W8 B20, the owner's Q8: a verdict names the day in full). Left as it is when it
    names no single day."""
    from datetime import datetime

    found = _first_date(fact, today)
    if found is None:
        return fact
    start, last = found
    day = last.value.date() if isinstance(last.value, datetime) else last.value
    if not isinstance(day, date):
        return fact
    clock = _clock_word(last.text)
    said = f"{calendar.day_name[day.weekday()]} {day.day} {_MONTHS[day.month - 1].title()}" + (f" {day.year}" if day.year != today.year else "")
    joiner = " at " if clock and f"at {clock.lower()}" in last.text.lower() else ", "
    return f"{fact[:start]}{said}{joiner + clock if clock else ''}{fact[last.end:]}"
