"""Spans of days and the vocabulary they read with, split out of
`ai/recognise.py` (audit-1028 K24, dec-1111-k2.md): the month and weekday
tables, and `span`, `find` and `window`, which read a phrase as the days it
names ("last week", "in March", "the weekend before last") against an anchor
and a tense. Moved whole and unchanged; `recognise` imports these names back
and stays the one public reader (`tests/test_one_reader.py` allows both files).
This module imports nothing from `recognise`, so the pair is acyclic.
"""

from __future__ import annotations

import re
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import date, datetime, time, timedelta
from typing import Any

from tessellate.core.lazyre import lazy_compile


# --- the date reading (was ai/when.py; its docstring keeps the rules) -----------

_WEEKDAYS = {
    "monday": 0, "mon": 0, "tuesday": 1, "tue": 1, "tues": 1, "wednesday": 2,
    "wed": 2, "thursday": 3, "thu": 3, "thurs": 3, "friday": 4, "fri": 4,
    "saturday": 5, "sat": 5, "sunday": 6, "sun": 6,
}
_MONTHS = {
    name: number
    for number, names in enumerate(
        (
            ("january", "jan"), ("february", "feb"), ("march", "mar"), ("april", "apr"),
            ("may",), ("june", "jun"), ("july", "jul"), ("august", "aug"),
            ("september", "sep", "sept"), ("october", "oct"), ("november", "nov"),
            ("december", "dec"),
        ),
        start=1,
    )
    for name in names
}
#: The names alone, for a reader that only asks whether a word is a month
#: or a weekday (`ai/fact_check.py`), so no second table of them exists.
MONTH_NAMES = frozenset(_MONTHS)
WEEKDAY_NAMES = frozenset(_WEEKDAYS) | {"thur"}
#: A weekday named in full, plural too ("Mondays"), for the readers that
#: find a day a note says (`composer`, `search_manager`).
WEEKDAY_WORD = lazy_compile(r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)s?\b", re.I)
#: A span's unit in minutes, for checking a stated span against the facts
#: (`ai/fact_check.py`): kept here as the one table of time units.
SPAN_MINUTES = {
    **dict.fromkeys(("second", "seconds", "sec", "secs"), 1 / 60),
    **dict.fromkeys(("minute", "minutes", "min", "mins"), 1),
    **dict.fromkeys(("hour", "hours", "hr", "hrs"), 60),
    **dict.fromkeys(("day", "days"), 1440),
    **dict.fromkeys(("week", "weeks"), 10080),
    **dict.fromkeys(("fortnight", "fortnights"), 20160),
    **dict.fromkeys(("month", "months"), 43830),
    **dict.fromkeys(("year", "years"), 525960),
}

_PARTS = {"morning": 9, "afternoon": 15, "evening": 18, "night": 20, "tonight": 20}
_NUMBERS = {
    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "twelve": 12,
    "fifteen": 15, "twenty": 20, "thirty": 30, "forty": 40, "forty-five": 45,
    "half an": 0.5, "a half": 0.5, "a couple of": 2, "a few": 3,
}

#: Single spaces, not `\s+`: `resolve` has already folded every run of
#: whitespace to one space, and a literal space leaves the engine nothing to
#: backtrack over (CodeQL, polynomial regular expression).
_ANCHORED = lazy_compile(
    r"^(\d{1,3}|half an|a couple of|a few|[a-z-]+) (minutes?|mins?|hours?|hrs?) (before|after) (.+)$"
)
_CLOCK = lazy_compile(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm|a\.m\.|p\.m\.)?(?=\s|$)")
_ISO_DATE = lazy_compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_DAY_MONTH = lazy_compile(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?([a-z]+)\b")
_MONTH_DAY = lazy_compile(r"\b([a-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?\b")
_WEEKDAY = lazy_compile(r"\b(?:(this|on|next|coming)\s+)?(" + "|".join(_WEEKDAYS) + r")\b")


#: A question whose answer the app works out (a span, a countdown, a weekday):
#: the figures in such a reply are computed, not quoted from a note.
_COMPUTED = lazy_compile(
    r"\b(?:how (?:long|many (?:days?|weeks?|months?|years?|hours?|minutes?)|far|soon)|ago|until|till|since|countdown|"
    r"what (?:day|date) (?:is|was|will)|days? (?:between|from|after|before))\b",
    re.IGNORECASE,
)


_WEEKDAY_CODES = ("MO", "TU", "WE", "TH", "FR", "SA", "SU")


_ORDINAL_N = {"first": 1, "1st": 1, "second": 2, "2nd": 2, "third": 3, "3rd": 3, "fourth": 4, "4th": 4, "last": -1}


def _nth_of_month(year: int, month: int, code: str) -> date | None:
    """The day a BYDAY like "-1FR" (last Friday) or "2MO" names in a month."""
    found = re.fullmatch(r"(-1|[1-4])([A-Z]{2})", code)
    if not found:
        return None
    weekday = _WEEKDAY_CODES.index(found.group(2))
    days = [d for d in range(1, 32) if _valid_day(year, month, d) and date(year, month, d).weekday() == weekday]
    n = int(found.group(1))
    return date(year, month, days[n if n < 0 else n - 1])


def _valid_day(year: int, month: int, day: int) -> bool:
    try:
        date(year, month, day)
    except ValueError:
        return False
    return True


# --- a span of days, past or to come (CHAT_PLAN Phase 6, decisions 30 and 31) ---
#
# `resolve` reads one instant to come; `days_since` one start in the past. A
# question ("what did I do last week") and a note's own time words ("I met
# Sam on Friday", read against the day the note was written) name a span of
# days with a grain: a day, a week, a month, a year. `span` reads one such
# phrase against an anchor day and a tense; `find` finds the phrases in a
# text; `window` is a question's span as two instants on the person's clock.
# Every rule is a row of `tests/test_when_windows.py`.

_ORD = r"(\d{1,2})(?:st|nd|rd|th)"
_MONTH_RE = r"(" + "|".join(sorted(_MONTHS, key=len, reverse=True)) + r")"
_WEEKDAY_RE = r"(" + "|".join(sorted(_WEEKDAYS, key=len, reverse=True)) + r")"
#: The year after a month: "November last year", "June of last year", "May
#: next year", "March this year". One capture group where a reader needs it.
_YEAR_WORD = r"(?:of )?(?:last|this|next) year"
_YEAR_AFTER_MONTH = r"(?: (\d{4}|" + _YEAR_WORD + r"))?"
#: The same, non-capturing, for the readers and `find`: a four-digit year or a
#: year word after a day, a season, a part of a month, a range. `span` turns
#: the year word into the year first (`_numbered_year`), so a reader needs only
#: the digits. One space between the parts, so nothing backtracks (CodeQL).
_YEAR_NAMED = r"(?: (?:of )?(?:\d{4}|(?:last|this|next) year))?"
_YEAR_COMMA = r"(?:,? (?:\d{4}|" + _YEAR_WORD + r"))?"
#: "the first monday of november", "the last friday of next month": groups
#: are the place, the weekday, this/next/last month, the month's name, a year.
_NTH_IN_MONTH = (
    r"(?:the )?(first|second|third|fourth|last|1st|2nd|3rd|4th) " + _WEEKDAY_RE
    + r" (?:of|in) (?:(this|next|last) month|" + _MONTH_RE + r"(?: (\d{4}))?)"
)
_UNIT_RE = r"(days?|weeks?|fortnights?|months?|years?)"
#: The recent past, said any way round (composer9-1026, "over the weekend",
#: "last fortnight", "in the past 3 weeks"): one set of fragments for `span`
#: (`_span_recent`, `_span_weekend`), `find` and `without_windows`, so the
#: three cannot drift apart.
_PRE = r"(?:in|over|during|within|throughout|across|through|for) "
_COUNT = r"(?:\d{1,3}|few|couple of|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)"
_RECENT_UNIT = r"(?:hours?|days?|weeks?|fortnights?|months?|years?)"
_ROLLING = (
    #: A count makes it a run of days back from today, with any lead-in.
    rf"(?:{_PRE})?(?:(?:the|these|this) )?(?:last|past|previous) {_COUNT} {_RECENT_UNIT}",
    #: No count: only after a lead-in or "the"; bare "last week" is the calendar week.
    #: Not "the last day of this month" or "the last week of the term": a
    #: "last" with an "of" after it names a place in something, not a run back.
    rf"(?:(?:{_PRE})(?:the |these |this )?|the |these |this )(?:last|past) {_RECENT_UNIT}(?! of\b)",
    r"(?:the |this |these )?(?:last|past|previous) fortnight",
)
#: The fortnight ahead, the mirror of "the last fortnight": fourteen days
#: from today. ("next week" is the calendar week; a fortnight has none.)
_FORTNIGHT_AHEAD = rf"(?:{_PRE})?(?:the )?(?:next|coming) fortnight"
#: The weekend just gone ("last weekend" stays the calendar reading).
_WEEKEND = r"(?:(?:in|over|during|throughout|across|through|for|at|on) the|the|this past|this last|the past) week[- ]?end(?: just (?:gone|past))?"
_TO_DATE = (
    r"(?:earlier|so far) this (?:week|month|year)",
    r"this (?:week|month|year) so far",
    r"(?:week|month|year)[ -]to[ -]date",
    r"earlier today",
)
_PART_OF_DAY = (
    r"last night",
    r"yesterday (?:morning|afternoon|evening|night)",
    r"this (?:morning|afternoon|evening)",
    r"the other day",
    r"(?:this time|the same day|same day) last (?:week|month|year)",
)
#: "Recently" and "lately" name no span; asked of the past they mean this many
#: days back from today, and the answer says so (`LATELY_DAYS`).
LATELY_DAYS = 14
_LATELY = r"(?:very )?(?:recently|lately|of late)"
_BEFORE_LAST = r"(?:the )?(?:week|weekend|month|year) before last"
_QUARTER = r"(?:the )?(?:last|this|next|previous|coming) quarter"
_PREVIOUS_UNIT = r"the previous (?:week|weekend|month|year|quarter)"
#: "Tuesday last week", "the Monday of the week before last": a day inside a named week (CHAT_PLAN U9).
_DAY_IN_WEEK = r"(?:the )?(?:" + "|".join(sorted(_WEEKDAYS, key=len, reverse=True)) + r") (?:of |in )?(?:the )?(last week|this week|previous week|week before last)"
#: "from Monday to Wednesday", "between March and May", "between 1 and 5
#: October": two days or months, joined. A bare number is only the first end,
#: and only before a day and month ("from 9 to 5" is a clock).
_END_DAY = rf"(?:{_WEEKDAY_RE}|{_MONTH_RE}(?: \d{{1,2}}(?:st|nd|rd|th)?)?|\d{{1,2}}(?:st|nd|rd|th)? (?:of )?{_MONTH_RE})"
_JOIN = r" (?:to|and|until|till|through) "
_BETWEEN = rf"(?:(?:between|from) {_END_DAY}{_JOIN}{_END_DAY}|between \d{{1,2}}(?:st|nd|rd|th)?{_JOIN}\d{{1,2}}(?:st|nd|rd|th)? (?:of )?{_MONTH_RE}){_YEAR_NAMED}"
#: A run of days inside one month, said four ways: "24-30 September", "from
#: 24 to 30 September", "between the 3rd and the 9th of May", "September 24 to
#: 30". Single spaces only and the parts disjoint, so nothing backtracks over
#: a run of spaces (CodeQL).
_DAY_NO = r"\d{1,2}(?:st|nd|rd|th)?"
_DAY_TO = r"(?: (?:to|through|until|till|and) (?:the )?|-|–)"
_DAY_RUNS = (
    rf"(?:(?:between|from) )?(?:the )?{_DAY_NO}{_DAY_TO}{_DAY_NO} (?:of )?{_MONTH_RE}{_YEAR_NAMED}",
    rf"(?:(?:between|from) )?{_MONTH_RE} (?:the )?{_DAY_NO}{_DAY_TO}{_DAY_NO}{_YEAR_COMMA}",
)
_SINCE_PART = r"(?:the weekend|this morning|last night|the \d{1,2}(?:st|nd|rd|th))"
_AMOUNT_RE = r"(\d{1,3}|a|an|one|two|three|four|five|six|seven|eight|nine|ten|twelve|a couple of|a few)"

#: A week or half of a named month ("the first week of October", "the last
#: week of September", "the second half of March") and a season ("last
#: summer", "in winter"): a bare season word is a phrase only after a lead-in
#: or a this/last/next, since "winter tyres" is a subject.
_LEAD_IN = r"(?:(?:in|during|over|throughout|through) )?"
_PART_OF_MONTH = (
    r"(?:the )?(?:first|second|third|fourth|1st|2nd|3rd|4th|last|final|latter|back) (?:week|half) of "
    r"(?:(?:this|next|last) (?:month|year)|" + _MONTH_RE + _YEAR_NAMED + r")"
)
_SEASON_RE = r"(spring|summer|autumn|fall|winter)"
_SEASON_FIND = (
    r"(?:in|during|over|throughout|through|from|for) (?:the )?(?:(?:last|this|next|previous|coming) )?"
    + _SEASON_RE + _YEAR_NAMED,
    r"(?:the )?(?:last|this|next|previous|coming) " + _SEASON_RE + _YEAR_NAMED,
    #: With a year a season needs no lead word ("winter 2025", "summer last
    #: year"); without one it stays a subject ("winter tyres").
    r"(?:the )?" + _SEASON_RE + r" (?:of )?(?:(?:19|20)\d{2}|(?:last|this|next) year)",
)
#: A month with a year and no lead word ("March 2026 notes"); a day follows a
#: month in "March 20 2026", which the day readers take first.
_MONTH_YEAR = _MONTH_RE + r" (?:(?:19|20)\d{2}|" + _YEAR_WORD + r")"
_PERIODS = (_LEAD_IN + _PART_OF_MONTH, *_SEASON_FIND)
#: "early March last year", "late last year", "end of next month", "mid 2025".
_PART_WORD = r"(?:mid|early|late|end of) (?:" + _MONTH_RE + _YEAR_NAMED + r"|(?:this|next|last) (?:month|year)|(?:19|20)\d{2})"
#: A day and its month, either way round, with a year or a year word.
_DAY_FORMS = (
    #: "on the 14th of November" whole, never "on the 14th" of this month
    #: (ledger row 441); "November the 14th" too.
    r"(?:on (?=the ))?(?:the )?\d{1,2}(?:st|nd|rd|th)? (?:of )?" + _MONTH_RE + _YEAR_NAMED,
    _MONTH_RE + r" (?:the )?\d{1,2}(?:st|nd|rd|th)?" + _YEAR_COMMA,
)
#: What "since", "before", "until", "till" and "after" take: any dated phrase
#: above, so each of them reads like the phrase alone ("since last spring",
#: "before 20 March last year", "until June this year").
_EDGE_INNER = (*_SEASON_FIND[1:], r"(?:the )?" + _SEASON_RE, _PART_OF_MONTH, _PART_WORD, *_DAY_FORMS, _MONTH_YEAR, _MONTH_RE,
               r"(?:last|this|next) (?:week|month|year)", r"\d{1,2}(?:st|nd|rd|th) of (?:next|this|last) month")
#: "from March 20th": the month is the day's, not a window of its own.
_NOT_A_DAY = r"(?! (?:the )?\d{1,2}(?:st|nd|rd|th)?\b)"
_EDGES = (
    r"(?:before|until|till|after) (?:the )?(?:" + "|".join(_EDGE_INNER) + r")",
    r"since (?:the )?(?:" + "|".join((*_EDGE_INNER, _WEEKDAY_RE, r"yesterday", r"\d{4}-\d{2}-\d{2}", _SINCE_PART)) + r")",
)

#: Every phrase `span` reads, longest forms first, as one pattern for `find`
#: (`_date_phrase`).
#: Word boundaries on both sides; nothing here backtracks over a run of
#: spaces (the text is searched as written, so `\s` is a single space class
#: bounded by words).
def _date_phrase() -> re.Pattern[str]:
    """The time-phrase pattern, compiled on first use: one long alternation, the
    slowest part of importing this module otherwise."""
    global _DATE_PHRASE
    if _DATE_PHRASE is None:
        _DATE_PHRASE = re.compile(_DATE_PHRASE_SOURCE, re.IGNORECASE)
    return _DATE_PHRASE


_DATE_PHRASE: re.Pattern[str] | None = None
_DATE_PHRASE_SOURCE = (
    r"\b(?:"
    + "|".join(
        (
            "(?:on )?" + _DAY_IN_WEEK,
            *_EDGES,
            *_PERIODS,
            _WEEKEND,
            *_ROLLING,
            _FORTNIGHT_AHEAD,
            *_TO_DATE,
            *_PART_OF_DAY,
            _BETWEEN,
            *_DAY_RUNS,
            _MONTH_YEAR,
            _LATELY,
            _BEFORE_LAST,
            _QUARTER,
            _PREVIOUS_UNIT,
            _NTH_IN_MONTH,
            r"(?:next|this|last) month,? (?:on )?(?:the )?\d{1,2}(?:st|nd|rd|th)",
            r"(?:the )?(?:first|last) day of (?:(?:this|next|last) month|the month|" + _MONTH_RE + _YEAR_NAMED + r")",
            r"(?:the )?day (?:after tomorrow|before yesterday)",
            _AMOUNT_RE + r" " + _UNIT_RE + r" ago",
            r"in (?:a fortnight|" + _AMOUNT_RE + r" " + _UNIT_RE + r")",
            r"(?:the )?(?:last|past|previous) (?:(?:\d{1,3}|few|couple of|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve) )?(?:days|weeks|months|years)",
            r"(?:last|this|next|past|coming) (?:week|weekend|month|year)(?! of\b)",
            r"(?:last|this|next|coming|on) " + _WEEKDAY_RE + r"(?: (?:morning|afternoon|evening|night))?",
            r"\d{4}-\d{2}-\d{2}",
            r"(?:on )?(?:the )?" + _ORD + r" of (?:next|this|last) month",
            *_DAY_FORMS,
            r"(?:on )?the " + _ORD,
            #: "dentist 21st 9am": a bare ordinal is a day of the month only
            #: with a clock right after it (engine probe: it was tomorrow).
            r"\d{1,2}(?:st|nd|rd|th)(?= (?:at \d|\d{1,2}(?::\d{2})? ?(?:am|pm|a\.m\.|p\.m\.)))",
            _PART_WORD,
            r"(?:the )?end of (?:the )?(?:day|week|month|year)|eod",
            r"(?:in|during|from|by) " + _MONTH_RE + _NOT_A_DAY + r"(?: (?:\d{4}|" + _YEAR_WORD + r"))?",
            r"(?:in|during) (?:19|20)\d{2}(?![\d:.-])",
            r"(?:(?:last|next|this) )?(?:christmas(?: day| eve)?|new year'?s? (?:day|eve)|new year)",
            r"later today|today|tonight|yesterday|tomorrow",
            _WEEKDAY_RE,
        )
    )
    + r")\b"
)

_AMOUNTS = {**{k: v for k, v in _NUMBERS.items() if isinstance(v, int)}, "a couple of": 2, "couple of": 2, "few": 3, "a few": 3, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12}


def _amount(word: str) -> int | None:
    word = word.lower()
    if word.isdigit():
        return int(word)
    return _AMOUNTS.get(word)


def count_of(word: str) -> int | None:
    """A whole count said as digits or a word ("3", "three", "a few"), or
    None: for a surface that needs a small number from a command ("a grid of
    three") and must not read it itself."""
    value = _amount(str(word or "").strip())
    return value if isinstance(value, int) else None


def _month_end(day: date) -> date:
    after = day.replace(day=28) + timedelta(days=4)
    return after - timedelta(days=after.day)


def _shift_months(day: date, months: int) -> date:
    index = day.year * 12 + day.month - 1 + months
    return date(index // 12, index % 12 + 1, 1)


def _week_of(day: date) -> tuple[date, date]:
    monday = day - timedelta(days=day.weekday())
    return monday, monday + timedelta(days=6)


def _nearest(candidates: list[date], anchor: date, tense: str | None) -> date:
    """The one of `candidates` the tense points at: the latest on or before
    the anchor for the past (and with no tense: notes mostly say what
    happened), the earliest on or after it for the future."""
    if tense == "future":
        ahead = [d for d in candidates if d >= anchor]
        return min(ahead) if ahead else max(candidates)
    behind = [d for d in candidates if d <= anchor]
    return max(behind) if behind else min(candidates)


def _day_of_month(day: int, anchor: date, tense: str | None) -> date | None:
    options = []
    for months in (-1, 0, 1):
        first = _shift_months(anchor.replace(day=1), months)
        try:
            options.append(first.replace(day=day))
        except ValueError:
            continue
    return _nearest(options, anchor, tense) if options else None


def _named_year(said: str | None, anchor: date) -> int | None:
    """The year a month is said with: 2025, "last year", "of next year"; None
    when it names none."""
    if not said:
        return None
    if said[0].isdigit():
        return int(said)
    return anchor.year + {"last": -1, "this": 0, "next": 1}[said.split()[-2]]


def _month_span(month: int, anchor: date, tense: str | None, year: int | None = None) -> tuple[date, date, str]:
    if year is None:
        options = [date(anchor.year + k, month, 1) for k in (-1, 0, 1)]
        if tense == "future":
            first = min(d for d in options if _month_end(d) >= anchor)
        else:
            first = max(d for d in options if d <= anchor)
    else:
        first = date(year, month, 1)
    return first, _month_end(first), "month"


def _back(anchor: date, amount: int, unit: str) -> date:
    unit = unit.rstrip("s")
    if unit == "day":
        return anchor - timedelta(days=amount)
    if unit in ("week", "fortnight"):
        return anchor - timedelta(days=7 * amount * (2 if unit == "fortnight" else 1))
    if unit == "month":
        first = _shift_months(anchor.replace(day=1), -amount)
        return first.replace(day=min(anchor.day, _month_end(first).day))
    try:
        return anchor.replace(year=anchor.year - amount)
    except ValueError:
        return anchor.replace(year=anchor.year - amount, day=28)


def _calendar_unit_span(which: str, unit: str, a: date) -> tuple[date, date, str]:
    """"last week", "next month", "this year", "past week": a whole calendar unit."""
    step = {"last": -1, "past": -1, "previous": -1, "this": 0, "next": 1, "coming": 1}[which]
    if unit == "quarter":
        index = a.year * 4 + (a.month - 1) // 3 + step
        first = date(index // 4, index % 4 * 3 + 1, 1)
        return first, _month_end(_shift_months(first, 2)), "month"
    if which == "past" and unit == "weekend":
        which = "last"
    if unit == "week":
        if which == "past":
            return a - timedelta(days=7), a, "week"
        first, last = _week_of(a + timedelta(days=7 * step))
        return first, last, "week"
    if unit == "weekend":
        saturday = a + timedelta(days=(5 - a.weekday()) % 7) if a.weekday() != 6 else a - timedelta(days=1)
        saturday += timedelta(days=7 * step)
        return saturday, saturday + timedelta(days=1), "week"
    if unit == "month":
        if which == "past":
            return _back(a, 1, "month"), a, "month"
        first = _shift_months(a.replace(day=1), step)
        return first, _month_end(first), "month"
    if which == "past":
        return _back(a, 1, "year"), a, "year"
    return date(a.year + step, 1, 1), date(a.year + step, 12, 31), "year"


_SHIFT = {"next": 1, "this": 0, "last": -1}
_MONTH_DAY_FORMS = (
    r"(?:the )?(?P<ord>\d{1,2})(?:st|nd|rd|th) of (?P<which>next|this|last) month",
    r"(?P<which>next|this|last) month,? (?:on )?(?:the )?(?P<ord>\d{1,2})(?:st|nd|rd|th)",
)
#: "the last day of this month", "first day of march": the month's edges.
_MONTH_EDGE = r"(?:the )?(?P<edge>first|last) day of (?:(?P<which>this|next|last) month|(?P<the>the) month|(?P<month>" + "|".join(sorted(_MONTHS, key=len, reverse=True)) + r")(?: (?P<year>\d{4}))?)"


def _month_day_span(text: str, a: date, tense: str | None) -> tuple[date, date, str] | None:
    """A day named by its month: "the 3rd of next month", "next month on the
    3rd", "the last day of this month", "first day of march"."""
    for form in _MONTH_DAY_FORMS:
        found = re.fullmatch(form, text)
        if found:
            first = _shift_months(a.replace(day=1), _SHIFT[found.group("which")])
            number = int(found.group("ord"))
            day = first.replace(day=number) if 1 <= number <= _month_end(first).day else None
            return (day, day, "day") if day else None
    found = re.fullmatch(_MONTH_EDGE, text)
    if not found:
        return None
    if found.group("which") or found.group("the"):
        first = _shift_months(a.replace(day=1), _SHIFT.get(found.group("which") or "this"))
    else:
        year = found.group("year")
        first = _month_span(_MONTHS[found.group("month")], a, tense or "future", int(year) if year else None)[0]
    day = first if found.group("edge") == "first" else _month_end(first)
    return day, day, "day"


def _nth_in_month(found: re.Match, anchor: date, tense: str | None) -> date | None:
    """The day an `_NTH_IN_MONTH` match names: a named month with no year is
    the next one to come (the last one gone, for a note about the past)."""
    nth, name, which, month_name, year = found.groups()
    code = f"{_ORDINAL_N[nth]}{_WEEKDAY_CODES[_WEEKDAYS[name]]}"
    if which:
        first = _shift_months(anchor.replace(day=1), {"last": -1, "this": 0, "next": 1}[which])
        return _nth_of_month(first.year, first.month, code)
    month = _MONTHS[month_name]
    if year:
        return _nth_of_month(int(year), month, code)
    days = [d for d in (_nth_of_month(anchor.year + k, month, code) for k in (-1, 0, 1)) if d]
    gone = [d for d in days if d < anchor]
    return max(gone, default=None) if tense == "past" else min((d for d in days if d >= anchor), default=None)


#: Time words that bound "what is coming up": (pattern, how it is said, days ahead).
#: -1 runs to the month's end.
_AHEAD_WORDS = (
    (lazy_compile(r"\btoday\b"), "today", 0),
    (lazy_compile(r"\btomorrow\b"), "tomorrow", 1),
    (lazy_compile(r"\bnext week\b"), "next week", 14),
    (lazy_compile(r"\b(?:next|coming) fortnight\b"), "in the next fortnight", 14),
    (lazy_compile(r"\bthis week\b"), "in the next seven days", 7),
    (lazy_compile(r"\bthis month\b"), "this month", -1),
    (lazy_compile(r"\bsoon\b"), "in the next two weeks", 14),
)


def ahead_window(question: str) -> tuple[str, int] | None:
    """`(how it is said, days ahead)` for the time word in a question about
    what is due or coming up, or None when it names none."""
    low = str(question or "").lower()
    return next(((said, days) for pattern, said, days in _AHEAD_WORDS if pattern.search(low)), None)


def without_ahead_words(text: str) -> str:
    """`text` with the time words `ahead_window` reads taken out: what is left
    of "what is due this week" past "this week" is the subject, if any."""
    low = str(text or "").lower()
    for pattern, _said, _days in _AHEAD_WORDS:
        low = pattern.sub(" ", low)
    return " ".join(low.split())


#: A reader that does not recognise the phrase returns this, so the next one
#: is tried; None means "recognised, but not a real date", which ends the read.
_MISS: Any = object()

#: Phrases that are one fixed day, as a day offset from the anchor.
_FIXED_DAYS = {
    "today": 0, "tonight": 0, "later today": 0, "yesterday": -1, "tomorrow": 1, "the day after tomorrow": 2,
    "day after tomorrow": 2, "the day before yesterday": -2, "day before yesterday": -2, "end of day": 0,
    "the end of the day": 0, "end of the day": 0, "eod": 0,
    "last night": -1, "yesterday morning": -1, "yesterday afternoon": -1, "yesterday evening": -1, "yesterday night": -1,
    "this morning": 0, "this afternoon": 0, "this evening": 0, "earlier today": 0,
}

_HOLIDAYS = {
    "christmas": (12, 25), "christmas day": (12, 25), "christmas eve": (12, 24), "new year": (1, 1),
    "new year's day": (1, 1), "new years day": (1, 1), "new year day": (1, 1), "new year's eve": (12, 31), "new years eve": (12, 31),
}


def _one_day(day: date) -> tuple[date, date, str]:
    return day, day, "day"


#: Before any notebook: "before March last year" runs from here.
_EPOCH_DAY = date(1970, 1, 1)
_EDGE_WORDS = lazy_compile(r"(since|before|until|till|after) (.+)")


def _span_edge(text: str, a: date, tense: str | None) -> Any:
    """"since last spring" runs from the start of the phrase to today, "after
    X" from the day after it, "before X" up to the day before it and "until X"
    or "till X" through its last day. The phrase after the word is read as it
    would be alone, so each date phrase gets all five."""
    found = _EDGE_WORDS.fullmatch(text)
    if not found:
        return _MISS
    word, rest = found.groups()
    #: "since the weekend" keeps its "the"; "since the 15th" and "since the
    #: first of march" read without it.
    inner = span(rest, a, "past") or span(re.sub(r"^the ", "", rest), a, "past")
    if inner is None:
        return None
    first, last, grain = inner
    if word == "since":
        return (first, a, grain) if first <= a else None
    if word == "after":
        return (last + timedelta(days=1), a, "day") if last < a else None
    if word == "before":
        return (_EPOCH_DAY, first - timedelta(days=1), "day") if first > _EPOCH_DAY else None
    return _EPOCH_DAY, last, "day"


def _span_fixed(text: str, a: date, tense: str | None) -> Any:
    if text not in _FIXED_DAYS:
        return _MISS
    return _one_day(a + timedelta(days=_FIXED_DAYS[text]))


def _span_week_before_last(text: str, a: date, tense: str | None) -> Any:
    found = re.fullmatch(_BEFORE_LAST, text)
    if not found:
        return _MISS
    unit = text.split()[-3]
    if unit == "week":
        first, last = _week_of(a - timedelta(days=14))
        return first, last, "week"
    if unit == "weekend":
        #: The weekend just gone, one week earlier (the same weekday a week back has the same "last weekend").
        return _calendar_unit_span("last", "weekend", a - timedelta(days=7))
    if unit == "month":
        first = _shift_months(a.replace(day=1), -2)
        return first, _month_end(first), "month"
    return date(a.year - 2, 1, 1), date(a.year - 2, 12, 31), "year"


_BARE_YEAR = lazy_compile(r"(?:in |during |of |for )?((?:19|20)\d{2})")


def _span_year(text: str, a: date, tense: str | None) -> Any:
    """A year by its number ("2025", "in 2025"): the whole of that year."""
    found = _BARE_YEAR.fullmatch(text)
    if not found:
        return _MISS
    year = int(found.group(1))
    return date(year, 1, 1), date(year, 12, 31), "year"


def _span_lately(text: str, a: date, tense: str | None) -> Any:
    return (a - timedelta(days=LATELY_DAYS), a, "day") if re.fullmatch(_LATELY, text) else _MISS


def _end_of_range(side: str, a: date, tense: str | None, other: tuple | None = None) -> tuple[date, date, str] | None:
    """One end of "from X to Y": a day or a month, "may" taken as the month,
    a bare number as that day of the other end's month."""
    got = span(side, a, tense) or span("in " + side, a, tense)
    if got is None and side.isdigit() and other is not None and 1 <= int(side) <= other[1].day:
        day = other[1].replace(day=int(side))
        return day, day, "day"
    return got


_DAY_RUN_DAY_FIRST = lazy_compile(rf"(?:between )?(?:the )?({_DAY_NO}){_DAY_TO}({_DAY_NO}) (?:of )?{_MONTH_RE}(?: (\d{{4}}))?")
_DAY_RUN_MONTH_FIRST = lazy_compile(rf"(?:between )?{_MONTH_RE} (?:the )?({_DAY_NO}){_DAY_TO}({_DAY_NO})(?:,? (\d{{4}}))?")


def _span_day_run(text: str, a: date, tense: str | None) -> Any:
    """"24-30 September", "between the 3rd and the 9th of May": the days from
    the first to the second in one month. The year is the one the first day
    falls in when the month is read as any day of it is (latest past for a
    note about the past), so both ends are always in the same year."""
    found = _DAY_RUN_DAY_FIRST.fullmatch(text)
    if found:
        first_day, last_day, month, year = found.groups()
    else:
        found = _DAY_RUN_MONTH_FIRST.fullmatch(text)
        if not found:
            return _MISS
        month, first_day, last_day, year = found.groups()
    first_n, last_n = (int(re.sub(r"\D", "", day)) for day in (first_day, last_day))
    anchor = span(f"{first_n} {month}" + (f" {year}" if year else ""), a, tense)
    try:
        first, last = (anchor[0], date(anchor[0].year, anchor[0].month, last_n)) if anchor else (None, None)
    except ValueError:
        return None
    return (first, last, "day") if first and last >= first else None


def _shared_year(first: str, second: str) -> str:
    """"from 1 March to 10 April 2025": the year belongs to both ends."""
    year = re.search(r" (\d{4})$", second)
    if year and not re.search(r"\d{4}$", first) and any(word in _MONTHS for word in first.split(" ")):
        return first + " " + year.group(1)
    return first


def _span_between(text: str, a: date, tense: str | None) -> Any:
    found = re.fullmatch(r"(?:between )?(.+?)" + _JOIN.replace("(?:", "(?:") + r"(.+)", text) if re.search(_JOIN, text) else None
    if not found or " to " in found.group(2) or " and " in found.group(2):
        return _MISS
    second = found.group(2)
    first_said = _shared_year(found.group(1), second)
    last = _end_of_range(re.sub(r"(?:st|nd|rd|th)$", "", second) if second[:1].isdigit() else second, a, tense)
    first = _end_of_range(re.sub(r"(?:st|nd|rd|th)$", "", first_said), a, tense, last)
    if first is None or last is None:
        return _MISS
    end = last[1]
    while end < first[0] and last[2] == "day":
        end += timedelta(days=7)
    #: "from November to February": the February after the November.
    if end < first[0] and last[2] == "month" and not re.search(r"\d{4}$", second):
        end = _month_end(_shift_months(last[0], 12))
    return first[0], end, ("month" if first[2] == last[2] == "month" else "day")


def _span_calendar_unit(text: str, a: date, tense: str | None) -> Any:
    #: "What did I do this weekend?" asked on a Wednesday is the weekend just
    #: gone, and on a Saturday or Sunday the one under way.
    if tense == "past" and text == "this weekend":
        saturday = a - timedelta(days=(a.weekday() - 5) % 7)
        return saturday, saturday + timedelta(days=1), "week"
    found = re.fullmatch(r"(last|this|next|past|coming|previous) (week|weekend|month|year|quarter)", re.sub(r"^the previous ", "previous ", text))
    return _calendar_unit_span(*found.groups(), a) if found else _MISS


_RECENT = lazy_compile(rf"(?:({_PRE.strip()}) )?(?:(the|these|this) )?(last|past|previous) (?:({_COUNT}) )?({_RECENT_UNIT})")


def _span_recent(text: str, a: date, tense: str | None) -> Any:
    """A run of days back from today: "the last 3 days", "in the past
    fortnight", "over the last week". A count always makes it one; without a
    count it takes a lead-in or "the" ("last week" alone is the calendar week,
    read before this)."""
    found = _RECENT.fullmatch(text)
    if not found:
        return _MISS
    lead, det, word, count, unit = found.groups()
    unit = unit.rstrip("s")
    if not (count or unit == "fortnight" or ((lead or det) and word in ("last", "past"))):
        return _MISS
    amount = _amount(count) if count else 1
    if unit == "hour":
        start = a - timedelta(days=-(-amount // 24) if amount >= 24 else 0)
    else:
        start = _back(a, amount, unit)
    return start, a, "day"


def _span_ahead(text: str, a: date, tense: str | None) -> Any:
    """"the next fortnight": the fourteen days after today (so no question's past window)."""
    if not re.fullmatch(_FORTNIGHT_AHEAD, text):
        return _MISS
    return a + timedelta(days=1), a + timedelta(days=14), "day"


def _span_weekend(text: str, a: date, tense: str | None) -> Any:
    """The weekend just gone ("over the weekend", "the weekend"); the coming
    one for a note about the future. "last weekend" is the calendar reading."""
    if not re.fullmatch(_WEEKEND, text):
        return _MISS
    if tense == "future":
        saturday = a - timedelta(days=1) if a.weekday() == 6 else a + timedelta(days=(5 - a.weekday()) % 7)
    else:
        saturday = a - timedelta(days=(a.weekday() - 5) % 7)
    return saturday, saturday + timedelta(days=1), "week"


def _span_to_date(text: str, a: date, tense: str | None) -> Any:
    """From the start of this week, month or year up to today."""
    found = re.fullmatch(r"(?:(?:earlier|so far) this (week|month|year)|this (week|month|year) so far|(week|month|year)[ -]to[ -]date)", text)
    if not found:
        return _MISS
    unit = next(g for g in found.groups() if g)
    start = {"week": _week_of(a)[0], "month": a.replace(day=1), "year": date(a.year, 1, 1)}[unit]
    return start, a, unit


def _span_other_day(text: str, a: date, tense: str | None) -> Any:
    """"The other day": a few days back, two to four."""
    if text != "the other day":
        return _MISS
    return a - timedelta(days=4), a - timedelta(days=2), "day"


def _span_same_day(text: str, a: date, tense: str | None) -> Any:
    found = re.fullmatch(r"(?:this time|the same day|same day) last (week|month|year)", text)
    return _one_day(_back(a, 1, found.group(1))) if found else _MISS


def _span_ago(text: str, a: date, tense: str | None) -> Any:
    found = re.fullmatch(_AMOUNT_RE + r" " + _UNIT_RE + r" ago", text)
    if not found:
        return _MISS
    amount = _amount(found.group(1))
    return None if amount is None else _one_day(_back(a, amount, found.group(2)))


def _span_in(text: str, a: date, tense: str | None) -> Any:
    found = re.fullmatch(r"in (?:a fortnight|" + _AMOUNT_RE + r" " + _UNIT_RE + r")", text)
    if not found:
        return _MISS
    if text == "in a fortnight":
        return _one_day(a + timedelta(days=14))
    amount, unit = _amount(found.group(1)), found.group(2).rstrip("s")
    if amount is None:
        return None
    if unit in ("month", "year"):
        first = _shift_months(a.replace(day=1), amount * (12 if unit == "year" else 1))
        return _one_day(first.replace(day=min(a.day, _month_end(first).day)))
    return _one_day(a + timedelta(days=amount * {"day": 1, "week": 7, "fortnight": 14}[unit]))


def _span_nth(text: str, a: date, tense: str | None) -> Any:
    found = re.fullmatch(_NTH_IN_MONTH, text)
    if not found:
        return _MISS
    day = _nth_in_month(found, a, tense)
    return _one_day(day) if day else None


def _weekday_named(which: str | None, target: int, a: date, tense: str | None) -> date:
    if which == "last":
        return a - timedelta(days=(a.weekday() - target) % 7 or 7)
    if which == "next":
        return a + timedelta(days=7 - a.weekday() + target)
    if which == "this":
        return _week_of(a)[0] + timedelta(days=target)
    if which == "coming":
        return a + timedelta(days=(target - a.weekday()) % 7 or 7)
    return _nearest([a + timedelta(days=(target - a.weekday()) % 7), a - timedelta(days=(a.weekday() - target) % 7)], a, tense)


def _span_weekday(text: str, a: date, tense: str | None) -> Any:
    found = re.fullmatch(r"(?:(last|this|next|coming|on) )?" + _WEEKDAY_RE + r"(?: (?:morning|afternoon|evening|night))?", text)
    if not found:
        return _MISS
    return _one_day(_weekday_named(found.group(1), _WEEKDAYS[found.group(2)], a, tense))


def _span_day_in_week(text: str, a: date, tense: str | None) -> Any:
    found = re.fullmatch(_DAY_IN_WEEK, text)
    if not found:
        return _MISS
    week = span(found.group(1), a, tense)
    day = _WEEKDAYS[text.removeprefix("the ").split()[0]]
    return _one_day(week[0] + timedelta(days=day)) if week else None


def _span_iso(text: str, a: date, tense: str | None) -> Any:
    found = _ISO_DATE.fullmatch(text)
    if not found:
        return _MISS
    try:
        return _one_day(date(*(int(g) for g in found.groups())))
    except ValueError:
        return None


def _span_month_day(text: str, a: date, tense: str | None) -> Any:
    return _month_day_span(text, a, tense) or _MISS


def _span_day_and_month(text: str, a: date, tense: str | None) -> Any:
    found = re.fullmatch(r"(?:the )?(\d{1,2})(?:st|nd|rd|th)? (?:of )?" + _MONTH_RE + r"(?: (\d{4}))?", text) or re.fullmatch(
        _MONTH_RE + r" (?:the )?(\d{1,2})(?:st|nd|rd|th)?(?:,? (\d{4}))?", text
    )
    if not found:
        return _MISS
    groups = found.groups()
    day_word, month_word = (groups[0], groups[1]) if groups[0].isdigit() else (groups[1], groups[0])
    year = int(groups[2]) if groups[2] else None
    month = _MONTHS[month_word]
    try:
        if year:
            return _one_day(date(year, month, int(day_word)))
        options = [date(a.year + k, month, int(day_word)) for k in (-1, 0, 1)]
        #: With no tense the nearer year by days wins, a tie going to the past
        #: (notes mostly say what happened): "Flight on 20 October", written on
        #: 2 October, is 18 days on, not 347 days back (INBOX 1518).
        if tense is None:
            return _one_day(min(options, key=lambda d: (abs((d - a).days), d > a)))
        return _one_day(_nearest(options, a, tense))
    except ValueError:
        return None


def _span_ordinal(text: str, a: date, tense: str | None) -> Any:
    found = re.fullmatch(r"(?:the )?" + _ORD, text)
    if not found:
        return _MISS
    day = _day_of_month(int(found.group(1)), a, tense)
    return _one_day(day) if day else None


_PART_OF_WORD_RX = lazy_compile(r"(mid|early|late|end of) (?:(this|next|last) (month|year)|(?P<year>\d{4})|" + _MONTH_RE + r"(?: (\d{4}))?)")


def _span_part_of_month(text: str, a: date, tense: str | None) -> Any:
    """"early March", "mid June last year", "late last month", "early next
    year": a third of a month or of a year (early the first ten days or four
    months, late the last ten days or four months), the middle one day (a
    middle third of a year), the end the last day."""
    found = _PART_OF_WORD_RX.fullmatch(text)
    if not found:
        return _MISS
    part, which, unit, year_n, month, month_year = found.groups()
    if year_n or unit == "year":
        year = int(year_n) if year_n else a.year + _SHIFT[which]
        first, last = date(year, 1, 1), date(year, 12, 31)
        if part == "early":
            return first, date(year, 4, 30), "day"
        if part == "mid":
            return date(year, 5, 1), date(year, 8, 31), "day"
        return (date(year, 9, 1), last, "day") if part == "late" else _one_day(last)
    if which:
        first = _shift_months(a.replace(day=1), _SHIFT[which])
        last = _month_end(first)
    else:
        first, last, _grain = _month_span(_MONTHS[month], a, tense or "future", int(month_year) if month_year else None)
    if part == "mid":
        return _one_day(first.replace(day=15))
    if part == "early":
        return first, first.replace(day=10), "day"
    if part == "late":
        return first.replace(day=21), last, "day"
    return _one_day(last)


def _span_end_of(text: str, a: date, tense: str | None) -> Any:
    found = re.fullmatch(r"(?:the )?end of (?:the )?(week|month|year)", text)
    if not found:
        return _MISS
    return _one_day({"week": _week_of(a)[1], "month": _month_end(a), "year": date(a.year, 12, 31)}[found.group(1)])


def _span_month(text: str, a: date, tense: str | None) -> Any:
    found = re.fullmatch(r"(?:in |during )?" + _MONTH_RE + _YEAR_AFTER_MONTH, text)
    # Three-letter month words that are also weekdays or "may" need a cue.
    if not found or not (found.group(1) not in ("may", "mar", "sat", "sun", "wed") or text.startswith(("in ", "during ")) or found.group(2)):
        return _MISS
    return _month_span(_MONTHS[found.group(1)], a, tense, _named_year(found.group(2), a))


def _span_holiday(text: str, a: date, tense: str | None) -> Any:
    #: "last Christmas" is the latest one gone, "next Christmas" the next to come, "this Christmas" the one of this
    #: year (W8B 1111: it read as no date, so its window carried no year).
    pointer, _, bare = text.partition(" ")
    if pointer in ("last", "next", "this") and bare in _HOLIDAYS:
        text, tense = bare, {"last": "past", "next": "future", "this": tense}[pointer]
        if pointer == "this":
            month, day_n = _HOLIDAYS[text]
            return _one_day(date(a.year, month, day_n))
    if text not in _HOLIDAYS:
        return _MISS
    month, day_n = _HOLIDAYS[text]
    day = _nearest([date(a.year + k, month, day_n) for k in (-1, 0, 1)], a, tense or "future")
    if tense != "past" and day == a and text.startswith("new year") and month == 1:
        day = date(a.year + 1, 1, 1)
    return _one_day(day)


_WEEK_NUMBER = {"first": 1, "1st": 1, "second": 2, "2nd": 2, "third": 3, "3rd": 3, "fourth": 4, "4th": 4}
_PART_OF_MONTH_RX = lazy_compile(
    r"(?:the )?(first|second|third|fourth|1st|2nd|3rd|4th|last|final|latter|back) (week|half) of "
    r"(?:(this|next|last) (month|year)|" + _MONTH_RE + r"(?: (\d{4}))?)"
)


def _part_in(first: date, nth: str, unit: str) -> tuple[date, date] | None:
    """The days a week or half of the month starting `first` covers: a week
    is a run of seven days from the 1st, the last week the month's final
    seven, the second half the 16th to the end."""
    end = _month_end(first)
    if unit == "half":
        if nth in ("first", "1st"):
            return first, first.replace(day=15)
        return (first.replace(day=16), end) if nth in ("second", "2nd", "last", "final", "latter", "back") else None
    if nth in ("last", "final"):
        return end - timedelta(days=6), end
    number = _WEEK_NUMBER.get(nth)
    if number is None:
        return None
    start = first + timedelta(days=7 * (number - 1))
    return (start, min(start + timedelta(days=6), end)) if start <= end else None


def _part_of_year(year: int, nth: str, unit: str) -> tuple[date, date] | None:
    """The first or second half of a year, or its first or last week."""
    if unit == "half":
        if nth in ("first", "1st"):
            return date(year, 1, 1), date(year, 6, 30)
        return (date(year, 7, 1), date(year, 12, 31)) if nth in ("second", "2nd", "last", "final", "latter", "back") else None
    if nth in ("first", "1st"):
        return date(year, 1, 1), date(year, 1, 7)
    return (date(year, 12, 25), date(year, 12, 31)) if nth in ("last", "final") else None


def _span_part_of_period(text: str, a: date, tense: str | None) -> Any:
    found = _PART_OF_MONTH_RX.fullmatch(re.sub(r"^(?:in|during|over|throughout|through) ", "", text))
    if not found:
        return _MISS
    nth, unit, which, whole, month, year = found.groups()
    if whole == "year":
        part = _part_of_year(a.year + _SHIFT[which], nth, unit)
        return None if part is None else (part[0], part[1], unit)
    named = which is None and year is None
    first = _shift_months(a.replace(day=1), _SHIFT[which]) if which else _month_span(_MONTHS[month], a, tense, int(year) if year else None)[0]
    part = _part_in(first, nth, unit)
    if part and named and tense == "past" and part[0] > a:
        part = _part_in(first.replace(year=first.year - 1), nth, unit)
    return None if part is None else (part[0], part[1], unit)


#: Meteorological seasons by the first month of each. The southern half is
#: the northern one six months on (the owner, 2026-10-27: summer is December
#: to February in Sydney, Auckland and Johannesburg).
_SEASON_START_NORTH = {"spring": 3, "summer": 6, "autumn": 9, "fall": 9, "winter": 12}
_SEASON_START_SOUTH = {"spring": 9, "summer": 12, "autumn": 3, "fall": 3, "winter": 6}
_SEASON_START = _SEASON_START_NORTH  # the words a season can be said with, for membership

#: Regions whose people live mostly in the southern hemisphere. Read off the
#: locale's region ("en-AU", "es_AR"); a bare "af" (Afrikaans) is southern too.
_SOUTHERN_REGIONS = frozenset(
    {"au", "nz", "za", "zw", "bw", "na", "ls", "sz", "mz", "zm", "ao", "mg", "ar", "cl", "uy", "py", "bo", "pe", "br", "fj"}
)
_SOUTHERN_LANGUAGES = frozenset({"af"})


def hemisphere_of(locale: str | None) -> str:
    """"south" for a locale of a southern region (en-AU, en-NZ, en-ZA ...),
    "north" for every other and for none."""
    parts = re.split(r"[-_]", str(locale or "").strip().lower())
    if parts and parts[0] in _SOUTHERN_LANGUAGES:
        return "south"
    return "south" if any(len(p) == 2 and p in _SOUTHERN_REGIONS for p in parts[1:]) else "north"


#: The person's season setting ("auto", "north", "south") and the locale the
#: browser last reported, kept as process state because most callers of the
#: reader carry no locale (`configure_hemisphere`, from Settings and at start).
_HEMISPHERE: dict[str, str | None] = {"setting": "auto", "reported": None}
#: The locale of the call in progress, so the readers below (which take no
#: locale) see it; none outside a call.
_CALL_LOCALE: ContextVar[str | None] = ContextVar("recognise_locale", default=None)


def configure_hemisphere(setting: str | None, reported_locale: str | None) -> None:
    """Settings, Calendar, Seasons ("auto", "north", "south") and the locale
    the browser reported; "auto" follows the call's own locale, then the
    reported one, then the north."""
    _HEMISPHERE["setting"] = setting if setting in ("north", "south") else "auto"
    _HEMISPHERE["reported"] = str(reported_locale) if reported_locale else None


#: "3/4" in a search or a question: the person's own choice (Settings, General,
#: Calendar, Date order) over the browser's language and region. "auto" follows them.
_DATE_ORDER = {"setting": "auto"}


def configure_date_order(setting: str | None) -> None:
    _DATE_ORDER["setting"] = setting if setting in ("day", "month") else "auto"


def note_locale(locale: str | None) -> None:
    """The locale a request carried is the freshest report of the person's
    place (kept in memory only; Settings holds the saved one)."""
    if locale:
        _HEMISPHERE["reported"] = str(locale)


def _hemisphere() -> str:
    if _HEMISPHERE["setting"] != "auto":
        return str(_HEMISPHERE["setting"])
    return hemisphere_of(_CALL_LOCALE.get() or _HEMISPHERE["reported"])


@contextmanager
def _in_locale(locale: str | None):  # noqa: ANN202
    """`locale` is the call's own while the block runs (an outer call's stays
    when this one carries none)."""
    token = _CALL_LOCALE.set(locale or _CALL_LOCALE.get())
    try:
        yield
    finally:
        _CALL_LOCALE.reset(token)


def _season_first_months() -> dict[str, int]:
    return _SEASON_START_SOUTH if _hemisphere() == "south" else _SEASON_START_NORTH

_SEASON_RX = lazy_compile(r"(?:(?:in|during|over|throughout|through) )?(?:the )?(?:(last|this|next|previous|coming|past) )?" + _SEASON_RE + r"(?: (?:of )?(\d{4}))?")


def _season_cycles(name: str, a: date) -> list[tuple[date, date]]:
    """Every run of the season near `a`, oldest first (meteorological seasons:
    winter is December to February, starting in the year it is named for)."""
    firsts = [date(y, _season_first_months()[name], 1) for y in range(a.year - 2, a.year + 2)]
    return [(f, _month_end(_shift_months(f, 2))) for f in firsts]


def _season_pick(which: str | None, tense: str | None, a: date, cycles: list[tuple[date, date]]) -> tuple[date, date]:
    """The run a this/last/next or a bare season names: the one in progress if
    there is one (a bare season, or "this"), else the one gone for the past
    and the one to come for the future; "this" and no tense pick the nearer."""
    now = next((c for c in cycles if c[0] <= a <= c[1]), None)
    gone = [c for c in cycles if c[1] < a][-1]
    coming = next(c for c in cycles if c[0] > a)
    if which in ("last", "previous", "past"):
        return gone
    if which in ("next", "coming"):
        return coming
    if now:
        return now
    if tense == "future":
        return coming
    if tense == "past":
        return gone
    return gone if (a - gone[1]) <= (coming[0] - a) else coming


def _span_season(text: str, a: date, tense: str | None) -> Any:
    found = _SEASON_RX.fullmatch(text)
    if not found:
        return _MISS
    which, name, year = found.groups()
    if year:
        first = date(int(year), _season_first_months()[name], 1)
        return first, _month_end(_shift_months(first, 2)), "season"
    cycles = _season_cycles(name, a)
    first, last = _season_pick(which, tense, a, cycles)
    return first, last, "season"


#: Tried in this order: an earlier reader's pattern can be a prefix of a later one's.
_SPAN_READERS = (
    _span_edge, _span_fixed, _span_day_run, _span_between, _span_week_before_last, _span_calendar_unit, _span_weekend, _span_ahead, _span_recent, _span_lately, _span_to_date,
    _span_other_day, _span_same_day, _span_ago, _span_in,
    _span_nth, _span_day_in_week, _span_weekday, _span_year, _span_iso, _span_month_day, _span_day_and_month, _span_ordinal,
    _span_part_of_period, _span_season, _span_part_of_month, _span_end_of, _span_month, _span_holiday,
)


_YEAR_TAIL = lazy_compile(r"(?: of)? (last|this|next) year$")
_DAY_WORD = lazy_compile(r"\d{1,2}(?:st|nd|rd|th)?(?:-\d{1,2}(?:st|nd|rd|th)?)?|the|to|through|until|till|and")


def _numbered_year(text: str, a: date) -> str:
    """"20 March last year" as "20 March 2025": a year word right after a month
    or a season is the year, so every reader below needs only the digits. A
    year word after anything else ("early next year", "since last year") is
    not touched."""
    found = _YEAR_TAIL.search(text)
    if not found:
        return text
    head = text[: found.start()]
    words = head.split(" ")
    #: Past the days after the month: "March 20", "March the 20th", "March 1-10",
    #: "March 1 to 10".
    while len(words) > 1 and _DAY_WORD.fullmatch(words[-1]):
        words.pop()
    if words[-1] not in _MONTHS and words[-1] not in _SEASON_START:
        return text
    return f"{head} {a.year + _SHIFT[found.group(1)]}"


def span(phrase: str, anchor: date, tense: str | None = None, locale: str | None = None) -> tuple[date, date, str] | None:
    """(first day, last day, grain) the phrase names, read against `anchor`,
    or None. `tense` ("past", "future" or None) picks between the Friday
    before and the Friday after: "I met Sam on Friday" in a note is the one
    before, "I will see Sam on Friday" the one after. Grain is "day",
    "week", "month" or "year"."""
    text = " ".join(str(phrase or "").lower().replace(",", " ").split()).strip(" .")
    text = re.sub(r"^(?:on|by|for|at|from) ", "", text)
    if not text:
        return None
    text = _numbered_year(text, anchor)
    with _in_locale(locale):
        for reader in _SPAN_READERS:
            got = reader(text, anchor, tense)
            if got is not _MISS:
                return got
    return None


#: A question's time window, taken off whole before its subject is read
#: ("last week", "3 days ago", "this month"), so "week 4" stays a subject
#: and "last week" is not one. Moved from the composer (ledger row 453).
#: Compiled on first use: this alternation was 15 ms of the composer's cold
#: import, whose budget is 0.2 s (tests/test_engine_budgets.py).
_WINDOW_WORDS: re.Pattern[str] | None = None


def _window_words() -> re.Pattern[str]:
    global _WINDOW_WORDS
    if _WINDOW_WORDS is None:
        _WINDOW_WORDS = re.compile(
            r"\b(?:" + "|".join((*_EDGES, *_PERIODS, _WEEKEND, *_ROLLING, _FORTNIGHT_AHEAD, *_TO_DATE, *_PART_OF_DAY, _BETWEEN, *_DAY_RUNS, *_DAY_FORMS, _PART_WORD, _MONTH_YEAR, _LATELY, _BEFORE_LAST,
                                 _QUARTER, _PREVIOUS_UNIT)) + r"|(?:the\s+)?(?:last|this|next|past|previous|coming)\s+(?:few\s+|couple\s+of\s+|\d{1,3}\s+|two\s+|three\s+|four\s+|five\s+|six\s+|seven\s+|eight\s+|nine\s+|ten\s+|eleven\s+|twelve\s+)?"
            r"(?:days?|weeks?|weekend|months?|years?|night|morning|evening|monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
            r"|(?:the\s+)?week\s+before\s+last|(?:\d{1,3}|a|an|one|two|three|four|five|six)\s+(?:days?|weeks?|months?|years?)\s+ago"
            r"|(?:in|during|of)\s+(?:19|20)\d{2}\b|(?:since|in|during|from)\s+(?:january|february|march|april|may|june|july|august|september|october|november|december)" + _NOT_A_DAY + r"(?: (?:of )?(?:last|this|next) year)?)\b",
            re.I,
        )
    return _WINDOW_WORDS


#: A sentence that looks dated: the composer's score for a "when" answer,
#: never turned into a value (that is `find` and `span`).
_DATED = lazy_compile(
    r"\b(\d{1,2}(st|nd|rd|th)|\d{4}|today|tomorrow|tonight|yesterday|next (week|month|year|fortnight)|coming fortnight|"
    r"last (week|month|year)|this (week|month|year)|weekend|january|february|march|april|may|june|july|"
    r"august|september|october|november|december|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
    re.I,
)


def without_windows(text: str) -> str:
    """`text` with its time windows blanked out."""
    return _window_words().sub(" ", text or "")


def looks_dated(text: str) -> bool:
    return bool(_DATED.search(text or ""))


#: A time phrase that names a day or a month by name ("3 March", "Friday",
#: "tomorrow", "in June"); a bare "May" is the verb as often as the month.
_NAMES_DAY = lazy_compile(r"\d|january|february|march|april|june|july|august|september|october|november|december|monday|tuesday|wednesday|thursday|friday|saturday|sunday|tomorrow|today", re.I)


def names_a_day(phrase: str) -> bool:
    """Whether a phrase `find` returned names a day: what a when-slot answer
    can say (composer_slots, audit 1029 C21), not "next week" or "lately"."""
    return bool(_NAMES_DAY.search(phrase or ""))


#: A day or span named relative to now that has not come ("tomorrow", "next
#: week", "this coming friday"), as a pattern for a question's own shape
#: (`composer_plan._KNOW_AHEAD`): the reader stays here, the shape stays there.
AHEAD_DAY_WORDS = (
    r"(?:tomorrow|tonight|day after tomorrow|"
    r"(?:next|this coming|this) (?:week|month|weekend|(?:mon|tues|wednes|thurs|fri|satur|sun)day))"
)
_SAID_RECENT_DAY = lazy_compile(r"\b(?:today|yesterday|tonight|this morning)\b", re.I)


def says_a_recent_day(text: str) -> bool:
    """Whether a sentence says the day it was written about itself ("ran 5 km
    today"): a flag for the composer, no word becomes a date here."""
    return bool(_SAID_RECENT_DAY.search(text or ""))


#: A time phrase that already carries its preposition, or needs none
#: ("since 3 October", "last week", "today", "3 days ago").
_ADVERB_LEAD = lazy_compile(r"^(?:in|on|at|since|during|between|from|before|after|by|until|till|over|within|for)\b", re.I)
_ADVERB_BARE = lazy_compile(
    r"^(?:today|tonight|yesterday|tomorrow|this|last|next|previous|coming|recently|lately|"
    r"the (?:day|week|weekend|rest|next|last|past|previous|first|end)\b)|\bago\b", re.I)
#: "the last 7 days", "past week": a rolling window is "in" it; "last week" and
#: "last month" are calendar spans and read without.
_ROLLING_SAID = lazy_compile(r"^(?P<the>the )?(?P<which>past|last|previous) (?P<n>(?:[\w-]+(?: of)? )?)?(?:days?|weeks?|months?|years?)$", re.I)


def _rolling_said(text: str) -> str:
    """"in the last 7 days" for a rolling window, "" for anything else."""
    rolling = _ROLLING_SAID.match(text)
    if rolling and (rolling.group("n") or rolling.group("the") or rolling.group("which").lower() == "past"):
        return f"in {text if rolling.group('the') else 'the ' + text}"
    return ""


def _dated_said(text: str, low: str) -> str:
    """The preposition a named day, month or year takes, "" when none."""
    month = re.search(r"\b" + _MONTH_RE + r"\b", low)
    if re.fullmatch(_WEEKDAY_RE + "s?", low) or re.fullmatch(r"(?:the )?\d{1,2}(?:st|nd|rd|th)", low):
        return "on " + text
    if month and re.search(r"\b\d{1,2}(?:st|nd|rd|th)?\b(?!\s*\d{2}\b)", re.sub(r"\b(?:19|20)\d{2}\b", "", low)):
        return ("from " if re.search(r"\bto\b|\d\s*-\s*\d", low) else "on ") + text
    if month or re.fullmatch(r"(?:19|20)\d{2}", low):
        return "in " + text
    return ""


#: A time phrase that points at "now" or counts back from it: a window of
#: when notes were written. Any other ("Christmas", "October", "the weekend")
#: is a thing the notes may talk about.
_DEICTIC_PHRASE = lazy_compile(
    r"^(?:in |on |from |during |for )?(?:today|yesterday|tomorrow|tonight|now|(?:this|last|next|past|previous|coming)\b.*|(?:\d+|a|an|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|a couple of|a few) (?:days?|weeks?|fortnights?|months?|years?) ago)$",
    re.I,
)
#: "which holiday is better in April" (R9-10): the month is the subject of the ask, not when it was written.
_ABOUT_PHRASE = r"\b(?:about|regarding|concerning|(?:best|better|nicest|ideal|great) (?:in|for))\s+(?:the |my |our )?{}\s*[?.!]*$"
PHRASE_FILLER = frozenset("in on at from during for the a an of".split())
_TOPIC_HOLIDAYS = frozenset(
    "christmas xmas easter halloween thanksgiving diwali eid ramadan hanukkah passover valentines boxing new year new years".split()
)
#: A question that asks what was done or written is about when.
_WHEN_ASK = lazy_compile(r"\b(?:did|have|had|was) (?:i|we)\b|\bwhat happened\b|\b(?:wrote|written|made|jotted|noted|added|captured)\b", re.I)


def a_topic_phrase(question: str, phrase: str, *, holiday: bool = True) -> bool:
    """Whether the time phrase is what the question is about, not when notes
    were written (audit 1031 C3): "what do I know about Christmas", "who is
    coming for Christmas". A holiday needs a "what did I do" to be a window;
    a holiday, month or weekend after "about" is searched for. The search
    (`search/query.py`) and the composer's plan both read it."""
    bare = re.sub(r"^(?:in|on|from|during|for|at|the)\s+", "", phrase.strip(), flags=re.I)
    if not bare or _DEICTIC_PHRASE.match(phrase.strip()):
        return False
    if re.search(_ABOUT_PHRASE.format(re.escape(bare)), question or "", re.I):
        return True
    #: "the Q4 report": a quarter with a noun after it names the thing, it does not date the note (R9-3).
    if re.fullmatch(r"q[1-4]", bare.lower()) and re.search(rf"\b{re.escape(bare)} [a-z]", (question or "")[:500], re.I):
        return True
    return holiday and bare.lower().replace("'", "") in _TOPIC_HOLIDAYS and not _WHEN_ASK.search(question or "")


#: The preposition a holiday or a bare weekend takes (audit 1031 C3: "nothing
#: went into your notes Christmas" had none).
_HOLIDAY_PREP = {
    "christmas": "at Christmas", "xmas": "at Christmas", "easter": "at Easter", "new year": "at New Year",
    "new year's": "at New Year", "halloween": "on Halloween", "thanksgiving": "at Thanksgiving",
    "boxing day": "on Boxing Day", "valentine's day": "on Valentine's Day", "new year's day": "on New Year's Day",
    "new year's eve": "on New Year's Eve", "christmas eve": "on Christmas Eve", "christmas day": "on Christmas Day",
    "the weekend": "over the weekend", "weekend": "over the weekend",
}


def _holiday_said(low: str) -> str:
    return _HOLIDAY_PREP.get(low.removeprefix("on ").removeprefix("at ").removeprefix("for ").strip(), "")


_POINTED_HOLIDAY = lazy_compile(r"(?:last|next|this) (?:christmas(?: day| eve)?|new year'?s? (?:day|eve)|new year)", re.I)


def with_holiday_year(phrase: str, day: date | None) -> str:
    """"last Christmas" as "last Christmas (2025)": a holiday asked by pointer names its year, so the answer says which one
    it read (W8B 1111). Any other phrase, or no day, is left as it is."""
    return f"{phrase} ({day.year})" if day is not None and _POINTED_HOLIDAY.fullmatch(" ".join(phrase.split())) else phrase


def adverbial(phrase: str) -> str:
    """A time phrase as it follows a verb or a count, carrying the
    preposition it needs (audit 1029 C10): "20 October" is "on 20 October",
    "friday" is "on friday", "october" and "2025" are "in" them, a rolling
    window is "in the last 7 days"; "last week", "today", "3 days ago" and
    "since 3 October" stand as they are. A range of days is "from" the first."""
    text = " ".join(str(phrase or "").split())
    low = text.lower()
    if text and (said := _holiday_said(low)):
        return said
    if _POINTED_HOLIDAY.fullmatch(low):
        return text
    if not text or _ADVERB_LEAD.match(low):
        return text
    if said := _rolling_said(text):
        return said
    if _ADVERB_BARE.search(low):
        return text
    return _dated_said(text, low) or (f"in {text}" if low.startswith(("a ", "an ")) else text)


def proper_days(text: str) -> str:
    """A month or a weekday typed small is said with its capital: "in
    october" is "in October" in an answer (audit 1030 Z45)."""
    return re.sub(r"\b[a-z]+\b", lambda m: m.group(0).capitalize() if m.group(0) in MONTH_NAMES or m.group(0) in WEEKDAY_NAMES else m.group(0), text)


_DEICTIC_LEAD = lazy_compile(r"^(?:Today|Tomorrow|Yesterday|Tonight)\b")


def mid_sentence(span: str) -> str:
    """A span that opens with a day word ("Tomorrow, Friday 30 October") with
    that word lowered, for a frame that puts it mid-sentence."""
    return span[0].lower() + span[1:] if _DEICTIC_LEAD.match(span) else span


def find(text: str) -> list[tuple[int, int, str]]:
    """Every time phrase in `text`: (start, end, phrase), left to right, none
    overlapping. A bare month that is also a word ("may", "march" as a verb)
    is found only with "in" or a day beside it (`span` holds the same rule)."""
    out = []
    for match in _date_phrase().finditer(text or ""):
        phrase = match.group(0)
        if phrase.lower() in ("may", "march", "sat", "sun", "wed", "mar") and not re.search(r"\d", phrase):
            continue
        out.append((match.start(), match.end(), phrase))
    return out


def window(phrase: str, now: datetime) -> tuple[datetime, datetime] | None:
    """A question's time phrase as (start, end) instants on `now`'s clock,
    the end never after `now`: "last week" is Monday 00:00 to Sunday 23:59
    of the week before this one; "since March" is 1 March to now. None for a
    phrase that names no past span, never a guess."""
    found = span(phrase, now.date(), "past")
    if found is None:
        return None
    first, last, _grain = found
    start = datetime.combine(first, time(0), now.tzinfo)
    end = min(datetime.combine(last, time(23, 59, 59), now.tzinfo), now)
    return (start, end) if start < end else None


#: Read by `recognise` (imported there); listed so the split's one-way use is explicit.
__all__ = [
    "AHEAD_DAY_WORDS",
    "PHRASE_FILLER",
    "SPAN_MINUTES",
    "WEEKDAY_WORD",
    "_PARTS",
    "_ANCHORED",
    "_CLOCK",
    "_DAY_MONTH",
    "_MONTH_DAY",
    "_WEEKDAY",
    "_COMPUTED",
]
