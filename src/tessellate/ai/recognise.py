"""The one reader of numbers, dates, times, durations, units and contacts
(CHAT_PLAN "The deterministic foundation", module 1; decisions 46 and 56).

Before this, five readers each read time words their own way and disagreed
("last friday" was next Friday in one, "every morning at 7" was 19:00 in
another), and nothing read a unit at all. Now there is one:

- `recognise(text, *, now, locale)` returns every `Span` it reads, in order:
  number, ordinal, date, time, datetime, duration, recurrence, range, money,
  quantity (the unit table below, 150 units and more), temperature, email,
  url, phone, person, place, tag. Past and future both resolve; the tense is
  read from the sentence ("what did I do on Friday" is the Friday before). An
  ambiguous phrase ("2/11", "5 pounds", a month with no tense) gives both
  readings at the same offsets, the likelier with `rank` 0.
- The date reading `ai/when.py` used to hold lives here unchanged in shape:
  `resolve`, `parse_reminder_text`, `days_since`, `span`, `find` and `window`
  keep their signatures, and `when` re-exports them.
- The "in 20 minutes" offsets `ai/reminder_parser.py` read (`relative_delta`)
  and the unit and currency names `ai/utilities.py` converts with live here;
  both modules import them back.

No network and no app imports (decision 56; `tests/test_recognise.py` checks
the imports): currency rates stay in `utilities` with their date. The rule
`tests/test_one_reader.py` holds: no other file compiles a date-word or unit
pattern, except `entry/timewords.py`, which reads a saved note's own words.
"""

from __future__ import annotations

import re
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any

# --- "in 20 minutes": an offset, not a wall-clock target (from reminder_parser) ----
#
# Reported: "play league of legends in half an hour" was scheduled for 10am the
# next day. A 3B model was doing arithmetic a regex does perfectly, so these
# shapes are read here first and the model is the fallback.

_UNIT_SECONDS = {
    "min": 60, "mins": 60, "minute": 60, "minutes": 60,
    "hr": 3600, "hrs": 3600, "hour": 3600, "hours": 3600,
    "day": 86400, "days": 86400,
    "week": 604800, "weeks": 604800,
}

_WORD_COUNTS = {
    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
    "twelve": 12, "fifteen": 15, "twenty": 20, "thirty": 30, "forty": 40,
    "forty-five": 45, "fortyfive": 45, "sixty": 60, "ninety": 90,
    # Spelled out rather than an optional `(?:a\s+)?` prefix: sorted longest
    # first, "a couple of" is tried before the bare "a".
    "couple of": 2, "couple": 2, "few": 3,
    "a couple of": 2, "a couple": 2, "a few": 3,
}

_FRACTIONS: list[tuple[str, timedelta]] = [
    (r"in\s+(?:half\s+an\s+hour|a\s+half\s+hour|30\s*mins?)\b", timedelta(minutes=30)),
    (r"in\s+(?:an?\s+)?hour\s+and\s+a\s+half\b", timedelta(minutes=90)),
    (r"in\s+(?:a\s+)?quarter\s+of\s+an\s+hour\b", timedelta(minutes=15)),
    (r"in\s+a\s+(?:little\s+)?while\b", timedelta(minutes=30)),
]

_COUNT_WORDS = "|".join(sorted((re.escape(w) for w in _WORD_COUNTS), key=len, reverse=True))
_IN_PATTERN = re.compile(
    rf"in\s+(\d{{1,4}}(?:\.\d{{1,2}})?|{_COUNT_WORDS})\s*({'|'.join(sorted(_UNIT_SECONDS, key=len, reverse=True))})\b",
    re.IGNORECASE,
)
_FRACTION_PATTERNS = [(re.compile(p, re.IGNORECASE), d) for p, d in _FRACTIONS]
#: "in 1h30", "in 2h", "in 1.5h", "in 1h30m", "in 1 hour 30 minutes", "in an hour
#: and 20 minutes": hours, then optionally the minutes beside them. "in 2
#: hours" alone is the same offset the unit table reads; the point is that the
#: minutes after the hours are never dropped. Bare "1h30" (no "in") stays a
#: duration the recogniser reports, not a time to come.
_IN_HOURS_MINUTES_SRC = (
    rf"\bin\s+(\d{{1,3}}(?:\.\d{{1,2}})?|{_COUNT_WORDS})\s?(?:hours?|hrs?|h)"
    rf"(?:(?:\s+and\s+|\s+|,\s?)(\d{{1,3}}|{_COUNT_WORDS})\s?(?:minutes?|mins?|m)\b|(\d{{2}})(?:m(?:ins?)?)?\b|\b(?!\s+and\s+a\s+half))"
)
_IN_HOURS_MINUTES = re.compile(_IN_HOURS_MINUTES_SRC, re.IGNORECASE)
_IN_MONTHS = re.compile(rf"\bin\s+(\d{{1,2}}|{_COUNT_WORDS})\s+(months?|years?)\b", re.IGNORECASE)


_FROM_NOW = re.compile(
    rf"\b(half\s+an\s+hour|an?\s+hour\s+and\s+a\s+half|(?:a\s+)?quarter\s+of\s+an\s+hour|"
    rf"(?:\d{{1,4}}(?:\.\d{{1,2}})?|{_COUNT_WORDS})\s*(?:{'|'.join(sorted(_UNIT_SECONDS, key=len, reverse=True))}))\s+from\s+now\b",
    re.IGNORECASE,
)


def relative_delta(text: str) -> tuple[timedelta, str] | None:
    """(how far ahead, the phrase that said so), or None.

    Only offsets: "in 20 minutes", "30 minutes from now". "At 8pm" and
    "tomorrow morning" name a wall-clock target, which `resolve` reads
    against the user's date.
    """
    if _rx("weeks_on").search(text):
        return None  # "in two weeks on wednesday" is a day, read by `_weeks_on_day`
    from_now = _FROM_NOW.search(text)
    if from_now:
        inner = relative_delta("in " + from_now.group(1))
        return (inner[0], from_now.group(0)) if inner else None
    for pattern, delta in _FRACTION_PATTERNS:
        found = pattern.search(text)
        if found:
            return delta, found.group(0)
    compound = _in_hours_minutes(text)
    if compound is not None:
        return compound
    found = _IN_PATTERN.search(text)
    if not found:
        return None
    raw_count, unit = found.group(1).lower(), found.group(2).lower()
    count = _WORD_COUNTS.get(raw_count)
    if count is None:
        try:
            count = float(raw_count)
        except ValueError:
            return None
    if count <= 0:
        return None
    seconds = count * _UNIT_SECONDS[unit]
    # A year out is not a reminder, it is a typo with consequences.
    if seconds > 366 * 86400:
        return None
    return timedelta(seconds=round(seconds)), found.group(0)


def _in_hours_minutes(text: str) -> tuple[timedelta, str] | None:
    """(offset, phrase) of "in 1h30" or "in 1 hour and 30 minutes", else None."""
    found = _IN_HOURS_MINUTES.search(text)
    if not found:
        return None
    hours = _WORD_COUNTS.get(found.group(1).lower())
    hours = float(found.group(1)) if hours is None and found.group(1)[0].isdigit() else hours
    said = (found.group(2) or found.group(3) or "0").lower()
    minutes = _WORD_COUNTS.get(said, float(said) if said.isdigit() else None)
    if hours is None or minutes is None or minutes >= 60 and found.group(3):
        return None
    return timedelta(minutes=round(hours * 60 + minutes)), found.group(0)


def relative_months(text: str, now: datetime) -> tuple[datetime, str] | None:
    """"in 6 months", "in a year": the same day that many calendar months on,
    at the same clock (engine probe: both were None). At most two years out,
    the same guard as `relative_delta`'s."""
    found = _IN_MONTHS.search(text)
    if not found:
        return None
    raw = found.group(1).lower()
    count = int(raw) if raw.isdigit() else _WORD_COUNTS.get(raw)
    if not count:
        return None
    months = count * (12 if found.group(2).lower().startswith("y") else 1)
    if months > 24:
        return None
    first = _shift_months(now.date().replace(day=1), months)
    day = first.replace(day=min(now.day, _month_end(first).day))
    return datetime.combine(day, now.time(), now.tzinfo), found.group(0)


def strip_lead(text: str) -> str:
    """A reminder's words without "remind me (to|about|that)" or a leading
    "to", which the time phrase left stranded ("remind me in 20 minutes to
    check the oven" is "Check the oven")."""
    rest = re.sub(r"^\s*(?:please\s+)?remind me\b", " ", text, flags=re.IGNORECASE).strip(" ,.;:-")
    head, _, tail = rest.partition(" ")
    if head.lower() in {"to", "about", "that"} and tail:
        rest = tail
    return rest

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
WEEKDAY_WORD = re.compile(r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)s?\b", re.I)
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
_ANCHORED = re.compile(
    r"^(\d{1,3}|half an|a couple of|a few|[a-z-]+) (minutes?|mins?|hours?|hrs?) (before|after) (.+)$"
)
_CLOCK = re.compile(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm|a\.m\.|p\.m\.)?(?=\s|$)")
_ISO_DATE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_DAY_MONTH = re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?([a-z]+)\b")
_MONTH_DAY = re.compile(r"\b([a-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?\b")
_WEEKDAY = re.compile(r"\b(?:(this|on|next|coming)\s+)?(" + "|".join(_WEEKDAYS) + r")\b")


#: A question whose answer the app works out (a span, a countdown, a weekday):
#: the figures in such a reply are computed, not quoted from a note.
_COMPUTED = re.compile(
    r"\b(?:how (?:long|many (?:days?|weeks?|months?|years?|hours?|minutes?)|far|soon)|ago|until|till|since|countdown|"
    r"what (?:day|date) (?:is|was|will)|days? (?:between|from|after|before))\b",
    re.IGNORECASE,
)


def asks_computed(question: str) -> bool:
    return bool(_COMPUTED.search(question))


#: A question about time (INBOX 1441): only then does an answer say a date.
_ASKS_TIME = re.compile(
    r"\b(?:when|what time|dates?|dated|days?|weeks?|weekend|months?|years?|yesterday|today|tonight|tomorrow|"
    r"recent(?:ly)?|latest|newest|oldest|earliest|last|first|since|ago|before|after|until|timeline|history|"
    r"how long|how often|going|progress\w*|improv\w*|chang\w*|monday|tuesday|wednesday|thursday|friday|saturday|sunday|january|february|march|"
    r"april|may|june|july|august|september|october|november|december|\d{1,2}(?:st|nd|rd|th)?)\b", re.I)


def asks_time(question: str) -> bool:
    """Whether a question's words are about time: a when, a day, a week or
    a month, a change over time (composer.asks_time adds "when did I write")."""
    return bool(_ASKS_TIME.search(question))


_WD_WORD = "|".join(sorted(_WEEKDAYS, key=len, reverse=True))
_MO_WORD = "|".join(sorted(_MONTHS, key=len, reverse=True))
_WD_PREFIX = rf"(?:\b({_WD_WORD})\.?,?\s+)?"
_YEAR_SUFFIX = r"(?:,?\s+((?:19|20)\d\d)\b)?"
_MENTION_DM = re.compile(rf"{_WD_PREFIX}\b(\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?({_MO_WORD})\b{_YEAR_SUFFIX}")
_MENTION_MD = re.compile(rf"{_WD_PREFIX}\b({_MO_WORD})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?\b(?![\d:])(?!\s*(?:am|pm)\b){_YEAR_SUFFIX}")
_MENTION_ISO = re.compile(rf"{_WD_PREFIX}\b(\d{{4}})-(\d\d)-(\d\d)(?=\b|t\d)")
#: "Thursday 29": a weekday and a day number, no month, not a clock time
#: or a count ("friday 2 notes").
_MENTION_WD_DAY = re.compile(
    rf"\b({_WD_WORD})\.?,?\s+(\d{{1,2}})(?:st|nd|rd|th)?\b(?![\d:])(?!\s*(?:am|pm)\b)(?!\s+(?!at\b|by\b|for\b|and\b|is\b|to\b|the\b)[a-z])"
)
#: (year or None, month or None, day, weekday or None)
DateMention = tuple[int | None, int | None, int, int | None]


def date_mentions(text: str) -> list[DateMention]:
    """The calendar dates a text states: a day with a month ("28 Oct",
    "October 28, 2026"), an ISO date, or a weekday with a day number
    ("Thursday 29"). Clock times and spans are no dates; a day that no month
    has (31 Feb) is skipped. The caller decides what they must match."""
    low = (text or "").lower()
    found: list[DateMention] = []

    def add(year: str | None, month: int | None, day: str, weekday: str | None) -> None:
        number = int(day)
        if 1 <= number <= 31:
            found.append((int(year) if year else None, month, number, _WEEKDAYS[weekday] if weekday else None))

    for m in _MENTION_ISO.finditer(low):
        if 1 <= int(m[3]) <= 12 and 1 <= int(m[4]) <= 31:
            add(m[2], int(m[3]), m[4], m[1])
    for m in _MENTION_DM.finditer(low):
        add(m[4], _MONTHS[m[3]], m[2], m[1])
    for m in _MENTION_MD.finditer(low):
        add(m[4], _MONTHS[m[2]], m[3], m[1])
    for m in _MENTION_WD_DAY.finditer(low):
        add(None, None, m[2], m[1])
    return found


def _nearest_year(month: int, day: int, now: datetime) -> date | None:
    """The date a year-less "28 Oct" is: the year that puts it nearest `now`."""
    tries = []
    for year in (now.year - 1, now.year, now.year + 1):
        try:
            tries.append(date(year, month, day))
        except ValueError:
            continue
    return min(tries, key=lambda d: abs((d - now.date()).days)) if tries else None


_RELATIVE_DAYS = (("day after tomorrow", 2), ("tomorrow", 1), ("today", 0), ("tonight", 0), ("yesterday", -1))


def days_named(text: str, now: datetime) -> set[date]:
    """The days a text names: its stated dates (a year-less one in the year
    nearest `now`), "today", "tomorrow", "yesterday", and each weekday word
    as its next and its last occurrence."""
    low = (text or "").lower()
    today = now.date()
    days: set[date] = {today}
    for year, month, day, _weekday in date_mentions(low):
        if month is None:
            continue
        try:
            named = date(year, month, day) if year else _nearest_year(month, day, now)
        except ValueError:
            continue
        if named:
            days.add(named)
    days.update(today + timedelta(days=offset) for word, offset in _RELATIVE_DAYS if word in low)
    for word in set(re.findall(rf"\b(?:{_WD_WORD})\b", low)):
        ahead = (_WEEKDAYS[word] - today.weekday()) % 7
        days.update((today + timedelta(days=ahead), today + timedelta(days=ahead - 7)))
    return days


#: A stamp as a tool result prints it, "2026-10-30T17:00:00".
_ISO_STAMP = re.compile(r"(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2})(?::(\d{2}))?)?")


def iso_figures(text: str) -> list[str]:
    """Every figure inside the ISO stamps of `text`: "2026-10-30T17:00" holds
    2026, 10, 30, 17 and 00, which the source check counts as said."""
    return [part for found in _ISO_STAMP.finditer(text) for part in found.groups() if part]


def _iso(text: str, now: datetime) -> datetime | None:
    if _ISO_DATE.fullmatch(text):
        return None  # a date alone is a day, read by `_day` with its 9:00
    try:
        parsed = datetime.fromisoformat(text.strip().upper().replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=now.tzinfo) if parsed.tzinfo is None else parsed


def _day(text: str, now: datetime) -> tuple[date | None, str]:
    """The day the phrase names, if it names one, and the text left over."""
    today = now.date()
    for pattern, offset in (
        (r"\bthe day after tomorrow\b", 2),
        (r"\btomorrow\b", 1),
        (r"\b(?:today|tonight)\b", 0),
    ):
        if re.search(pattern, text):
            return today + timedelta(days=offset), text
    if re.search(r"\bnext week\b", text):
        return today + timedelta(days=7 - today.weekday()), text
    found = _ISO_DATE.search(text)
    if found:
        try:
            return date(*(int(g) for g in found.groups())), text.replace(found.group(0), " ")
        except ValueError:
            return None, text
    for pattern, day_group, month_group in ((_DAY_MONTH, 1, 2), (_MONTH_DAY, 2, 1)):
        for found in pattern.finditer(text):
            month = _MONTHS.get(found.group(month_group))
            if month is None:
                continue
            try:
                day = date(today.year, month, int(found.group(day_group)))
            except ValueError:
                continue
            if day < today:
                day = day.replace(year=today.year + 1)
            return day, text.replace(found.group(0), " ")
    found = _WEEKDAY.search(text)
    if found:
        target = _WEEKDAYS[found.group(2)]
        if found.group(1) == "next":
            return today + timedelta(days=7 - today.weekday() + target), text
        return today + timedelta(days=(target - today.weekday()) % 7), text
    return None, text


def _clock(text: str) -> tuple[int, int, str | None] | None:
    """(hour, minute, "am"/"pm"/None) from the phrase, or None."""
    if re.search(r"\b(?:noon|midday)\b", text):
        return 12, 0, "pm"
    if re.search(r"\bmidnight\b", text):
        return 24, 0, None
    eod = _end_of_day(text)
    if eod:
        return eod
    spoken = _rx("spoken_clock").search(text)
    if spoken:
        return _spoken_clock(spoken)
    worded = next((m for m in _rx("word_clock").finditer(text) if _word_clock_ok(text, m)), None)
    if worded:
        return _word_clock(worded)
    return _digit_clock(text)


def _end_of_day(text: str) -> tuple[int, int, str] | None:
    """5pm for "eod" and "end of (the) day": the hour the repo has always
    given it. On its own day, or today; once five has passed it is the next
    day's, the rule for every clock with no day."""
    return (5, 0, "pm") if re.search(r"\b(?:eod|end of (?:the )?day)\b", text) else None


def _digit_clock(text: str) -> tuple[int, int, str | None] | None:
    """The first "9", "9:30" or "9pm" in the phrase that is a time."""
    for found in _CLOCK.finditer(text):
        hour, minute = int(found.group(1)), int(found.group(2) or 0)
        meridiem = (found.group(3) or "").replace(".", "") or None
        # A bare number counts only as a time when something says it is one:
        # "at 9", "9:30", "9pm". "in 3 days" has numbers that are not hours.
        if meridiem is None and found.group(2) is None:
            before = text[: found.start()]
            #: The last word before the number, not a `\s*$` search, which
            #: backtracks over a long run of spaces (CodeQL).
            if before.rstrip().rpartition(" ")[2] not in {"at", "by", "around", "about"}:
                continue
        if hour > 23 or minute > 59 or (meridiem and not 1 <= hour <= 12):
            continue
        return hour, minute, meridiem
    return None


_SPOKEN_HOURS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
    "ten": 10, "eleven": 11, "twelve": 12,
}
_SPOKEN_MINUTES = {"half": 30, "quarter": 15, "five": 5, "ten": 10, "twenty": 20, "twenty-five": 25, "twenty five": 25}


def _spoken_clock(found: re.Match) -> tuple[int, int, str | None] | None:
    """(hour, minute, "am"/"pm"/None) of "half past 4", "a quarter to five",
    "ten past 6pm": the clock as people say it aloud. "To" counts back from
    the next hour, so "quarter to 5" is 4:45."""
    minutes, direction, said, meridiem = found.groups()
    hour = int(said) if said.isdigit() else _SPOKEN_HOURS[said]
    if not 1 <= hour <= 12:
        return None
    minute = _SPOKEN_MINUTES.get(minutes) or int(minutes)
    if direction == "to":
        minute, hour = 60 - minute, 12 if hour == 1 else hour - 1
    return hour, minute, (meridiem or "").replace(".", "") or None


_WORD_MINUTES = {
    "fifteen": 15, "twenty": 20, "twenty-five": 25, "twenty five": 25, "thirty": 30, "thirty-five": 35,
    "thirty five": 35, "forty": 40, "forty-five": 45, "forty five": 45, "fifty": 50, "fifty-five": 55,
    "fifty five": 55,
}
#: Words after a bare word hour that make it a count, not a time ("at three
#: people"); "at one" alone is never read (it is "at one point" as often).
_NOT_A_CLOCK_NEXT = frozenset({"of", "more", "x", "people", "point", "time", "with", "another"})


def _word_clock(found: re.Match) -> tuple[int, int, str | None] | None:
    """(hour, minute, "am"/"pm"/None) of "3 o'clock", "at three", "at ten
    thirty", "at 1530", "at 15h30". The figure forms are 24-hour notation, so
    their hour is stated, never guessed: 1 to 11 is am, 12 is noon, 0 and
    13 to 23 stand as written. The word and o'clock forms keep the bare-hour
    rule (`_hour24`) unless they say am or pm."""
    got = found.groupdict()
    if got["o"] or got["w"]:
        said = got["o"] or got["w"]
        hour = int(said) if said.isdigit() else _SPOKEN_HOURS[said]
        meridiem = (got["wa"] or "").replace(".", "") or None
        return (hour, _WORD_MINUTES.get(got["wm"] or "", 0), meridiem) if 1 <= hour <= 12 else None
    hour, minute = int(got["hh"] or got["h2"]), int(got["mm"] or got["m2"])
    if hour > 23:
        return None
    return hour, minute, "am" if 1 <= hour <= 11 else "pm" if hour == 12 else None


def _word_clock_ok(low: str, found: re.Match) -> bool:
    """A bare word hour ("at three") is a time unless a count follows it
    ("at three people"), and never "one" ("at one point")."""
    got = found.groupdict()
    if not got["w"] or got["wm"] or got["wa"]:
        return True
    rest = low[found.end():].split()
    return got["w"] != "one" and not (rest and (rest[0].endswith("s") or rest[0] in UNITS or rest[0] in _NOT_A_CLOCK_NEXT))


def _hour24(hour: int, meridiem: str | None, evening: bool) -> int:
    if meridiem == "am":
        return 0 if hour == 12 else hour
    if meridiem == "pm":
        return hour if hour == 12 else hour + 12
    if hour > 12 or hour == 0:
        return hour
    if evening:
        return hour if hour == 12 else hour + 12
    return hour + 12 if 1 <= hour <= 6 else hour


_FROM_DAY = re.compile(
    r"^(\d{1,3}|a|an|one|two|three|four|five|six|seven|eight|nine|ten|twelve|a couple of|a few) (days?|weeks?|fortnights?) from (.+)$"
)


def _offset_from(text: str, now: datetime) -> datetime | None:
    """A time moved off another phrase's: "2 hours before midnight", "a week
    from friday" (the Friday coming, then seven days on)."""
    anchored = _ANCHORED.match(text)
    if anchored:
        amount = _NUMBERS.get(anchored.group(1))
        amount = int(anchored.group(1)) if amount is None and anchored.group(1).isdigit() else amount
        base = resolve(anchored.group(4), now)
        unit = timedelta(hours=1) if anchored.group(2).startswith("h") else timedelta(minutes=1)
        return None if amount is None or base is None else base + unit * amount * (-1 if anchored.group(3) == "before" else 1)
    moved = _FROM_DAY.match(text)
    amount = _amount(moved.group(1)) if moved else None
    base = resolve(moved.group(3), now) if moved and amount else None
    return base + timedelta(days={"d": 1, "w": 7, "f": 14}[moved.group(2)[0]] * amount) if base else None


def _weeks_on_day(found: re.Match, today: date) -> date | None:
    """The day "in two weeks on wednesday" names. Decided to match "next
    friday" (the Friday of next week, in `_day` and `span`): weeks run Monday
    to Sunday, "in N weeks" is the week N weeks on, and the weekday is its day
    there. So "in a week on friday" is "next friday", and said on a Friday,
    "in two weeks on wednesday" is the Wednesday before the mark two weeks out
    (the 14th day on), never the one after it. Counting 14 days and then
    finding the weekday would make the same words mean a different week
    depending on the day they were said."""
    amount = 1 if found["f"] else _amount(found["n"])
    if amount is None:
        return None
    weeks = amount * (2 if found["f"] or found["u"].startswith("f") else 1)
    return today - timedelta(days=today.weekday()) + timedelta(weeks=weeks, days=_WEEKDAYS[found["d"]])


def _weeks_on_cands(low: str, now: datetime) -> list[tuple]:
    """"in two weeks on wednesday" as one day, longer than the offset inside it."""
    out = []
    for found in _rx("weeks_on").finditer(low):
        day = _weeks_on_day(found, now.date())
        if day is not None:
            out.append((found.start(), found.end(), "date", day, "", 0))
    return out


def _first_day(text: str, now: datetime) -> tuple[date | None, str]:
    """`_day`, except a weekday's place in a month ("the first monday of
    november") is that day and not the next Monday, and "in two weeks on
    wednesday" is the week's Wednesday and not a fortnight on."""
    weeks = _rx("weeks_on").search(text)
    day = _weeks_on_day(weeks, now.date()) if weeks else None
    if day:
        return day, text[: weeks.start()] + " " + text[weeks.end():]
    nth = _rx("nth_in_month").search(text)
    day = _nth_in_month(nth, now.date(), "future") if nth else None
    return (day, text[: nth.start()] + " " + text[nth.end():]) if day else _day(text, now)


def _resolve_shortcut(text: str, now: datetime) -> datetime | None:
    """The shapes that name the instant outright: an ISO stamp, an offset, a
    relative span, "later today". None when the phrase is none of them."""
    for shape in (_iso, _offset_from):
        got = shape(text, now)
        if got is not None:
            return got
    relative = relative_delta(text)
    if relative is not None:
        return _with_clock(now + relative[0], relative[1], text, now, relative[0] >= timedelta(days=1))
    months = relative_months(text, now)
    if months is not None:
        return _with_clock(months[0], months[1], text, now, True)
    if text == "later today":
        #: Three hours on, never past eight in the evening (engine probe: it
        #: was nine this morning, already gone).
        later = now + timedelta(hours=3)
        cap = datetime.combine(now.date(), time(20), now.tzinfo)
        return min(later, cap) if cap > now else later
    return None


def _resolve_day(text: str, now: datetime, locale: str | None) -> tuple:
    """The day the phrase names and the words left over for the clock."""
    day, rest = _first_day(text, now)
    if day is None:
        numeric = _numeric_dates(text, now.date(), locale, "future")
        if numeric:
            start, end, readings = numeric[0]
            day, rest = readings[0][0], text[:start] + " " + text[end:]
    #: What `_day` does not read, or reads the wrong way ("last friday" was
    #: the coming one), is read by `span`: past weekdays, "the 21st",
    #: "21st of next month", "this weekend", "in a fortnight", "christmas".
    for start, end, phrase in find(text):
        if day is not None and not phrase.lower().startswith("last "):
            break
        if _end_of_day(phrase):
            continue  # a clock (17:00), not a day: `_clock` reads it
        found = span(phrase, now.date(), "future")
        if found is not None:
            #: A weekend under way on its Sunday began yesterday: a reminder
            #: for it is today, never a Saturday already gone.
            first = now.date() if found[0] < now.date() <= found[1] else found[0]
            return first, text[:start] + " " + text[end:]
    return day, rest


def _first_reading(text: str, now: datetime, locale: str | None) -> datetime | None:
    """What the phrase reads as to the recogniser and not to the rules
    ("march" alone, "q4"): its first day, at 9:00."""
    for found in recognise(text, now=now, locale=locale, tense="future"):
        if found.rank == 0 and found.kind in ("date", "range") and isinstance(found.value[0] if found.kind == "range" else found.value, date):
            first = found.value[0] if found.kind == "range" else found.value
            return datetime.combine(first, time(9), now.tzinfo)
    return None


def _early_clock(day: date | None, clock: tuple, part: str | None, text: str, now: datetime) -> datetime | None:
    """A clock that answers by itself: midnight, or a bare hour with no day,
    which is the next such o'clock."""
    hour, minute, meridiem = clock
    if hour == 24:
        return _midnight(day or now.date(), text, now)
    hour = _hour24(hour, meridiem, part in ("evening", "night", "tonight"))
    if day is None and meridiem is None and hour < 12:
        # "at 9" with no day: the next 9 o'clock, morning or evening.
        #: "every morning at 7" is seven in the morning, never 19:00.
        for candidate in (hour,) if part == "morning" else (hour, hour + 12):
            at = datetime.combine(now.date(), time(candidate, minute), now.tzinfo)
            if at > now:
                return at
    return None


def _clock_hm(clock: tuple | None, part: str | None) -> tuple:
    if clock is None:
        return (_PARTS[part] if part else 9), 0
    hour, minute, meridiem = clock
    return _hour24(hour, meridiem, part in ("evening", "night", "tonight")), minute


def _settled(day: date | None, clock: tuple | None, part: str | None, text: str, now: datetime) -> datetime:
    """The day and clock as an instant, rolled forward when it has gone."""
    hour, minute = _clock_hm(clock, part)
    at = _still_tonight(datetime.combine(day or now.date(), time(hour, minute), now.tzinfo), now, part if clock is None else None)
    if at <= now and day is None:
        at += timedelta(days=1)
    elif at <= now and day == now.date() and _WEEKDAY.search(text):
        at += timedelta(days=7)  # "Monday 9am", said on a Monday afternoon
    return at


def resolve(phrase: str, now: datetime, *, locale: str | None = None) -> datetime | None:
    """The instant `phrase` means, on `now`'s clock, or None. `locale` orders
    a numeric date ("2/11"): day first unless it is a month-first locale."""
    text = " ".join(str(phrase or "").lower().replace(",", " ").split()).strip(" .")
    if not text:
        return None
    shortcut = _resolve_shortcut(text, now)
    if shortcut is not None:
        return shortcut
    day, rest = _resolve_day(text, now, locale)
    clock = _clock(rest)
    part = next((p for p in _PARTS if re.search(rf"\b{p}\b", text)), None)
    if day is None and clock is None and part is None:
        return _first_reading(text, now, locale)
    early = _early_clock(day, clock, part, text, now) if clock is not None else None
    if early is not None:
        return early
    return _settled(day, clock, part, text, now)

def _with_clock(target: datetime, said: str, text: str, now: datetime, day_sized: bool) -> datetime:
    """An offset of a day or more with a clock beside it ("in 2 weeks at 3pm"):
    the day the offset lands on, at that clock. An offset of hours keeps the
    instant, and a day-sized one with no clock keeps `now`'s time of day."""
    rest = " ".join(text.replace(said, " ", 1).split())
    if not day_sized or not rest or not (_clock(rest) or any(re.search(rf"\b{p}\b", rest) for p in _PARTS)):
        return target
    return resolve(f"{target.date().isoformat()} {rest}", now) or target


def _midnight(day: date, text: str, now: datetime) -> datetime:
    """The midnight a phrase means. Midnight belongs to the night of the day it
    is said with, so alone it is tonight's (the next one) and "midnight on 5
    october" is the turn into the 6th. The one exception, decided 2026-10-17:
    "new year" (not "new year's eve" or "new year's day", which name their day
    and follow the rule) is the midnight that opens the year, so "remind me at
    midnight to see the new year" is 00:00 on 1 January, not a night later."""
    opens = re.search(r"\bnew year(?!'?s? (?:eve|day)\b)", text)
    return datetime.combine(day + timedelta(days=0 if opens else 1), time(0), now.tzinfo)


def _part_alone(text: str) -> str | None:
    """"tonight" or "this evening" said with no clock time beside it."""
    found = re.search(r"\b(tonight|evening|night)\b", text, re.IGNORECASE)
    return found.group(1).lower() if found and not re.search(r"\d", text) else None


def _still_tonight(at: datetime | None, now: datetime, part: str | None) -> datetime | None:
    """"Tonight" said after eight is not eight o'clock gone by: it is the
    next whole hour, still tonight (a reminder set for a time past fails)."""
    if at is None or part not in ("tonight", "evening", "night") or at > now or at.date() != now.date():
        return at
    return now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)


# --- Magic Add: a reminder sentence with its time taken out (UX-01) ---------
#
# `resolve` reads the whole sentence, so "call mum tomorrow at 5pm" resolves as
# it stands; what it cannot say is which words were the time. The reminder that
# fires should read "Call mum", not "Call mum tomorrow at 5pm" a day later. The
# words cut are the spans `recognise` reads as a time, so what is stripped is
# exactly what was read, by the same reader.

# "Call mum tomorrow evening, high priority": the placeholder's own example.
_PRIORITY = re.compile(r"\b(high|low)\s+priority\b", re.IGNORECASE)
_TIME_KINDS = frozenset({"date", "datetime", "time", "range", "recurrence", "alert"})
#: The reminder repeats the app can store (`routes_reminders.Recurring`).
_STORED_REPEATS = {"FREQ=DAILY": "daily", "FREQ=WEEKLY": "weekly", "FREQ=MONTHLY": "monthly"}
#: A rule the store keeps as itself (TIMELINE_PLAN 11 row 8): every other
#: week, weekdays, the last Friday of the month. The hour is the due time's.
STORED_RULE = re.compile(
    r"FREQ=(?:DAILY|WEEKLY|MONTHLY|YEARLY)(?:;INTERVAL=\d{1,2})?"
    r"(?:;BYDAY=(?:-1|[1-4])?(?:MO|TU|WE|TH|FR|SA|SU)(?:,(?:MO|TU|WE|TH|FR|SA|SU)){0,6})?(?:;BYMONTHDAY=\d{1,2})?"
)


def stored_repeat(rule: str) -> str | None:
    """The reminder's `recurring` value for an RRULE: one of the three words
    when the rule is one of them (the due day carries the weekday or the
    day of the month), else the rule itself, or None when the store cannot
    say it: nothing is saved as a repeat it is not."""
    head = rule.split(";BYHOUR=")[0]
    if head in _STORED_REPEATS:
        return _STORED_REPEATS[head]
    found = re.fullmatch(r"FREQ=(WEEKLY|MONTHLY);BY(?:DAY=[A-Z]{2}|MONTHDAY=(\d{1,2}))", head)
    #: The 29th to the 31st is not in every month: "monthly" would carry
    #: February's 28th on into March (ledger row 414), so the day stays.
    if found and int(found.group(2) or 0) < 29:
        return _STORED_REPEATS["FREQ=" + found.group(1)]
    return head if STORED_RULE.fullmatch(head) else None


def _rule_parts(rule: str) -> dict:
    """An RRULE as its parts; the three stored words as the rules they are."""
    word = {v: k for k, v in _STORED_REPEATS.items()}.get(rule)
    return dict(item.split("=", 1) for item in (word or rule).split(";") if "=" in item)


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


def _day_fits(day: date, parts: dict) -> bool:
    """Whether a day is one a rule's BYDAY and BYMONTHDAY allow."""
    codes = parts.get("BYDAY", "").split(",") if parts.get("BYDAY") else []
    if any(re.match(r"-?\d", c) for c in codes):
        return any(_nth_of_month(day.year, day.month, c) == day for c in codes)
    if codes and _WEEKDAY_CODES[day.weekday()] not in codes:
        return False
    return "BYMONTHDAY" not in parts or day.day == int(parts["BYMONTHDAY"])


def _add_months(at: datetime, months: int, parts: dict, day_of_month: int | None = None) -> datetime:
    """`at` moved on whole months, landing on the rule's day in that month.
    `day_of_month` is the day the repeat means when `at` was clamped by a
    shorter month (31 January -> 28 February -> 31 March)."""
    month0 = at.month - 1 + months
    year, month = at.year + month0 // 12, month0 % 12 + 1
    code = parts.get("BYDAY", "")
    if re.match(r"-?\d", code):
        day = _nth_of_month(year, month, code)
    else:
        want = int(parts.get("BYMONTHDAY", day_of_month or at.day))
        day = date(year, month, max(d for d in range(1, want + 1) if _valid_day(year, month, d)))
    return datetime.combine(day, at.timetz())


def next_occurrence(rule: str, after: datetime, day_of_month: int | None = None) -> datetime:
    """The next time a stored repeat ("weekly", or a rule `stored_repeat`
    keeps) falls after `after`, at `after`'s time of day: what completing a
    repeating reminder rolls it on to (`routes_reminders`). `day_of_month`
    is the anchor a monthly or yearly repeat returns to when the month
    allows (`Reminder.repeat_day`)."""
    parts = _rule_parts(rule)
    interval = int(parts.get("INTERVAL", 1))
    freq = parts.get("FREQ", "DAILY")
    if freq == "MONTHLY":
        return _add_months(after, interval, parts, day_of_month)
    if freq == "YEARLY":
        return _add_months(after, 12 * interval, parts, day_of_month)
    if freq == "WEEKLY" and "," in parts.get("BYDAY", ""):
        day = next(after.date() + timedelta(days=n) for n in range(1, 8) if _day_fits(after.date() + timedelta(days=n), parts))
        return datetime.combine(day, after.timetz())
    return after + timedelta(days=interval * (7 if freq == "WEEKLY" else 1))


def first_of(rule: str, now: datetime) -> datetime | None:
    """The first time an RRULE from `recognise` falls after `now`."""
    parts = dict(item.split("=", 1) for item in rule.split(";"))
    hour, minute = int(parts.get("BYHOUR", 9)), int(parts.get("BYMINUTE", 0))
    for ahead in range(0, 370):
        day = now.date() + timedelta(days=ahead)
        if not _day_fits(day, parts):
            continue
        at = datetime.combine(day, time(hour, minute), now.tzinfo)
        if at > now:
            return at
    return None


def _known_day(spans: list, now: datetime) -> datetime | None:
    """A day `resolve` cannot know but the caller does ("on my birthday"), at 9."""
    day = next((s.value for s in spans if s.kind == "date"), None)
    return datetime.combine(day, time(9), now.tzinfo) if day else None


def _spoken_instant(spans: list) -> datetime | None:
    """The datetime a sentence's own span names. "this evening, 6:30" and
    "tonight when I get back, say 7:30pm": a day part (no digits) and a clock
    apart from it. The clock said is the time; the day part only says which day."""
    day_span = next((s for s in spans if s.kind == "datetime"), None)
    if day_span is None:
        return None
    instant = day_span.value
    if not re.search(r"\d|noon|midnight", day_span.text):
        clock = next((s for s in spans if s.kind == "time" and isinstance(s.value, time)), None)
        if clock is not None:
            instant = datetime.combine(instant.date(), clock.value)
    return instant


def _reminder_instant(text: str, now: datetime, locale: str | None, tense: str, spans: list, repeat: Span | None) -> datetime | None:
    """When the sentence says the reminder is due, or None."""
    #: The past (a timeline entry, "on 3 october") is the recogniser's
    #: reading; `resolve` reads only time to come.
    at = resolve(text, now, locale=locale) if tense == "future" else None
    instant = _spoken_instant(spans)
    if instant is not None and (at is None or at.date() == instant.date()):
        at = instant
    at = _still_tonight(at, now, _part_alone(text)) or _known_day(spans, now)
    if repeat is not None and (at is None or "BYHOUR" in repeat.value or "BYMONTHDAY" in repeat.value):
        at = first_of(repeat.value, now) or at
    return at


def _reminder_words(text: str, spans: list) -> tuple[str, str]:
    """The reminder's own words (the time cut out) and its priority."""
    cuts = [(s.start, s.end) for s in spans if _is_time_words(s, text)]
    priority = "normal"
    said = _PRIORITY.search(text)
    if said:
        priority = said.group(1).lower()
        cuts.append(said.span())
    rest = text
    for start, end in sorted(cuts, reverse=True):
        rest = rest[:start] + " " + rest[end:]
    rest = strip_lead(re.sub(r"\s+", " ", rest).strip(" ,.;:-"))
    rest = _trim_dangling(rest)
    if not any(s.kind == "recurrence" for s in spans):
        rest = _keep_due_day(rest, [s.text for s in sorted(spans, key=lambda s: s.start) if _is_time_words(s, text)])
    return (rest or text.strip() or "Reminder"), priority


_CLOCK_TAIL = re.compile(r"(?<!\s)\s+(?:(?:at\s+)?\d{1,2}(?::\d{2})?\s*(?:am|pm)|at\s+\d{1,2}(?::\d{2})?|\d{1,2}:\d{2})\Z", re.I)


def _keep_due_day(rest: str, cut_words: list[str]) -> str:
    """"Essay due friday 5pm" is "Essay due Friday", not "Essay due": a title that
    ends on "due" has lost the day it was due when the time is cut out, so the
    day word stays and only the clock goes."""
    if not cut_words or not rest.lower().endswith(" due"):
        return rest
    day = _CLOCK_TAIL.sub("", cut_words[0].strip()).strip()
    if not day or re.fullmatch(r"(?:at\s+)?\d{1,2}(?::\d{2})?\s*(?:am|pm)?", day, re.I) or day.lower().startswith("in "):
        return rest
    return f"{rest} {day[0].upper() + day[1:]}" if day[0].isalpha() else f"{rest} {day}"


def parse_reminder_text(
    text: str, now: datetime, *, locale: str | None = None, known: dict | None = None, tense: str = "future"
) -> dict | None:
    """A reminder from a sentence `resolve` reads, with no model, or None.

    {"text", "due_at", "priority", "source"}, and "recurring" ("daily",
    "weekly", "monthly") when the sentence repeats ("water the plants every
    tuesday"): the shape of `reminder_parser.parse_relative`. The text keeps
    the sentence's own words minus the time; a sentence that was only a time
    keeps itself, since an empty reminder is worse than a redundant one.
    """
    spans = [s for s in recognise(text, now=now, locale=locale, tense=tense, known=known, bare_hours=True) if s.rank == 0]
    repeat = next((s for s in spans if s.kind == "recurrence"), None)
    at = _reminder_instant(text, now, locale, tense, spans, repeat)
    if at is None:
        return None
    rest, priority = _reminder_words(text, spans)
    parsed = {
        "text": (rest[0].upper() + rest[1:])[:500],
        "due_at": at,
        "priority": priority,
        "source": "rule",
    }
    _repeat_and_alert(parsed, repeat, spans)
    return parsed


def _trim_dangling(rest: str) -> str:
    """The words a cut time left stranded. A dangling "on" or "at", dropped by
    word rather than by a `\\s+...$` pattern, which backtracks on a long run
    of spaces; and the "to" that "remind me at midnight to lock up" has left
    in front ("To lock up") once the "at" is gone, which `strip_lead` could
    not see through it."""
    words = rest.split(" ")
    while words and words[-1].lower() in {"on", "at", "by", "for", "every", "each"}:
        words.pop()
    lead = 0
    while lead < len(words) and words[lead].lower() in {"on", "at", "by"}:
        lead += 1
    if lead and words[lead:lead + 2][:1] == ["to"] and len(words) > lead + 1:
        lead += 1
    return " ".join(words[lead:]).strip(" ,.;:-")


def _is_time_words(found: Span, text: str) -> bool:
    """Whether a span's words are the reminder's time and so come out of its
    text. A holiday after "the" is the thing to do ("see the new year"), not
    the time, which is still read from it."""
    if found.kind == "duration":
        return found.text.lower().startswith("in ")
    thing = re.match(r"(?:new year|christmas)", found.text.lower()) and text[:found.start].lower().endswith("the ")
    return found.kind in _TIME_KINDS and not thing


def _repeat_and_alert(parsed: dict, repeat: Span | None, spans: list) -> None:
    """A reminder's stored repeat and its early alert, when the words say them."""
    if repeat is not None and stored_repeat(repeat.value):
        parsed["recurring"] = stored_repeat(repeat.value)
    alert = next((s for s in spans if s.kind == "alert"), None)
    if alert is not None:
        parsed["alert_minutes"] = alert.value


# --- a window in the past (AGENT_SKILLS_REFORM, the audit of computed arguments) ---
#
# `resolve` reads a time to come. The list tools' `since` asks the other way,
# "notes from this week", and used to take only a number of days or an ISO
# date, so a model asked about "this week" had to work out which date that
# was: the arithmetic the 2026-09-21 decision took away from it everywhere.

_SPAN = re.compile(
    r"^(?:the\s+)?(?:last|past|previous)\s+(?:(\d{1,3}|[a-z-]+)\s+)?(days?|weeks?|months?|years?)$"
)
_AGO = re.compile(r"^(\d{1,3}|[a-z-]+)\s+(days?|weeks?|months?|years?)\s+ago$")


def _months_back(today: date, months: int) -> date:
    year, month = today.year, today.month - months
    while month < 1:
        month += 12
        year -= 1
    return date(year, month, min(today.day, 28))


def _count(word: str | None) -> int | None:
    if word is None:
        return 1
    if word.isdigit():
        return int(word)
    value = _NUMBERS.get(word)
    return int(value) if value and value >= 1 else None


def _span_days(amount: int, unit: str, today: date) -> int:
    unit = unit.rstrip("s")
    if unit == "day":
        return amount
    if unit == "week":
        return 7 * amount
    if unit == "month":
        return (today - _months_back(today, amount)).days
    return (today - today.replace(year=today.year - amount)).days


def days_since(phrase: str, now: datetime) -> int | None:
    """How many days back a window in the user's words starts, on `now`'s
    calendar: "this week" 0 on a Monday, "since Friday", "last month" (from
    the first of the month before), "the last 30 days", "3 days ago", "1
    September" (the last one that has passed), an ISO date, or a bare
    number of days. None for anything that names no past window, never a
    guess, so a caller can say it did not understand rather than filter on a
    wrong date."""
    text = " ".join(str(phrase or "").lower().replace(",", " ").split()).strip(" .")
    if not text:
        return None
    if text.isdigit():
        return int(text)
    today = now.date()
    text = re.sub(r"^(?:since|from|after)\s+", "", text)
    fixed = {
        "today": 0,
        "yesterday": 1,
        "this week": today.weekday(),
        "last week": 7,
        "the past week": 7,
        "past week": 7,
        "this month": today.day - 1,
        "last month": (today - _months_back(today, 1).replace(day=1)).days,
        "this year": (today - date(today.year, 1, 1)).days,
        "last year": (today - date(today.year - 1, 1, 1)).days,
    }
    if text in fixed:
        return fixed[text]
    found = _SPAN.match(text) or _AGO.match(text)
    if found:
        amount = _count(found.group(1))
        return None if amount is None else _span_days(amount, found.group(2), today)
    found = re.fullmatch(r"(?:last\s+)?(" + "|".join(_WEEKDAYS) + r")", text)
    if found:
        back = (today.weekday() - _WEEKDAYS[found.group(1)]) % 7
        return back or 7
    found = _ISO_DATE.fullmatch(text)
    if found:
        try:
            day = date(*(int(g) for g in found.groups()))
        except ValueError:
            return None
        return (today - day).days if day <= today else None
    for pattern, day_group, month_group in ((_DAY_MONTH, 1, 2), (_MONTH_DAY, 2, 1)):
        found = pattern.fullmatch(text)
        if not found or _MONTHS.get(found.group(month_group)) is None:
            continue
        try:
            day = date(today.year, _MONTHS[found.group(month_group)], int(found.group(day_group)))
        except ValueError:
            return None
        if day > today:
            day = day.replace(year=today.year - 1)
        return (today - day).days
    return None


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
_BEFORE_LAST = r"(?:the )?(?:week|month|year) before last"
_QUARTER = r"(?:the )?(?:last|this|next|previous|coming) quarter"
_PREVIOUS_UNIT = r"the previous (?:week|weekend|month|year|quarter)"
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
            r"christmas(?: day| eve)?|new year'?s? (?:day|eve)|new year",
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
    (re.compile(r"\btoday\b"), "today", 0),
    (re.compile(r"\btomorrow\b"), "tomorrow", 1),
    (re.compile(r"\bnext week\b"), "next week", 14),
    (re.compile(r"\b(?:next|coming) fortnight\b"), "in the next fortnight", 14),
    (re.compile(r"\bthis week\b"), "in the next seven days", 7),
    (re.compile(r"\bthis month\b"), "this month", -1),
    (re.compile(r"\bsoon\b"), "in the next two weeks", 14),
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
_EDGE_WORDS = re.compile(r"(since|before|until|till|after) (.+)")


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
    if unit == "month":
        first = _shift_months(a.replace(day=1), -2)
        return first, _month_end(first), "month"
    return date(a.year - 2, 1, 1), date(a.year - 2, 12, 31), "year"


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


_DAY_RUN_DAY_FIRST = re.compile(rf"(?:between )?(?:the )?({_DAY_NO}){_DAY_TO}({_DAY_NO}) (?:of )?{_MONTH_RE}(?: (\d{{4}}))?")
_DAY_RUN_MONTH_FIRST = re.compile(rf"(?:between )?{_MONTH_RE} (?:the )?({_DAY_NO}){_DAY_TO}({_DAY_NO})(?:,? (\d{{4}}))?")


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


_RECENT = re.compile(rf"(?:({_PRE.strip()}) )?(?:(the|these|this) )?(last|past|previous) (?:({_COUNT}) )?({_RECENT_UNIT})")


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
        return _one_day(_nearest([date(a.year + k, month, int(day_word)) for k in (-1, 0, 1)], a, tense))
    except ValueError:
        return None


def _span_ordinal(text: str, a: date, tense: str | None) -> Any:
    found = re.fullmatch(r"(?:the )?" + _ORD, text)
    if not found:
        return _MISS
    day = _day_of_month(int(found.group(1)), a, tense)
    return _one_day(day) if day else None


_PART_OF_WORD_RX = re.compile(r"(mid|early|late|end of) (?:(this|next|last) (month|year)|(?P<year>\d{4})|" + _MONTH_RE + r"(?: (\d{4}))?)")


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
    if text not in _HOLIDAYS:
        return _MISS
    month, day_n = _HOLIDAYS[text]
    day = _nearest([date(a.year + k, month, day_n) for k in (-1, 0, 1)], a, tense or "future")
    if tense != "past" and day == a and text.startswith("new year") and month == 1:
        day = date(a.year + 1, 1, 1)
    return _one_day(day)


_WEEK_NUMBER = {"first": 1, "1st": 1, "second": 2, "2nd": 2, "third": 3, "3rd": 3, "fourth": 4, "4th": 4}
_PART_OF_MONTH_RX = re.compile(
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

_SEASON_RX = re.compile(r"(?:(?:in|during|over|throughout|through) )?(?:the )?(?:(last|this|next|previous|coming|past) )?" + _SEASON_RE + r"(?: (?:of )?(\d{4}))?")


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
    _span_nth, _span_weekday, _span_iso, _span_month_day, _span_day_and_month, _span_ordinal,
    _span_part_of_period, _span_season, _span_part_of_month, _span_end_of, _span_month, _span_holiday,
)


_YEAR_TAIL = re.compile(r"(?: of)? (last|this|next) year$")
_DAY_WORD = re.compile(r"\d{1,2}(?:st|nd|rd|th)?(?:-\d{1,2}(?:st|nd|rd|th)?)?|the|to|through|until|till|and")


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
            r"|(?:since|in|during|from)\s+(?:january|february|march|april|may|june|july|august|september|october|november|december)" + _NOT_A_DAY + r"(?: (?:of )?(?:last|this|next) year)?)\b",
            re.I,
        )
    return _WINDOW_WORDS


#: A sentence that looks dated: the composer's score for a "when" answer,
#: never turned into a value (that is `find` and `span`).
_DATED = re.compile(
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
_NAMES_DAY = re.compile(r"\d|january|february|march|april|june|july|august|september|october|november|december|monday|tuesday|wednesday|thursday|friday|saturday|sunday|tomorrow|today", re.I)


def names_a_day(phrase: str) -> bool:
    """Whether a phrase `find` returned names a day: what a when-slot answer
    can say (composer_slots, audit 1029 C21), not "next week" or "lately"."""
    return bool(_NAMES_DAY.search(phrase or ""))


#: A time phrase that already carries its preposition, or needs none
#: ("since 3 October", "last week", "today", "3 days ago").
_ADVERB_LEAD = re.compile(r"^(?:in|on|at|since|during|between|from|before|after|by|until|till|over|within|for)\b", re.I)
_ADVERB_BARE = re.compile(
    r"^(?:today|tonight|yesterday|tomorrow|this|last|next|previous|coming|recently|lately|"
    r"the (?:day|week|weekend|rest|next|last|past|previous|first|end)\b)|\bago\b", re.I)
#: "the last 7 days", "past week": a rolling window is "in" it; "last week" and
#: "last month" are calendar spans and read without.
_ROLLING_SAID = re.compile(r"^(?P<the>the )?(?P<which>past|last|previous) (?P<n>(?:[\w-]+(?: of)? )?)?(?:days?|weeks?|months?|years?)$", re.I)


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


def adverbial(phrase: str) -> str:
    """A time phrase as it follows a verb or a count, carrying the
    preposition it needs (audit 1029 C10): "20 October" is "on 20 October",
    "friday" is "on friday", "october" and "2025" are "in" them, a rolling
    window is "in the last 7 days"; "last week", "today", "3 days ago" and
    "since 3 October" stand as they are. A range of days is "from" the first."""
    text = " ".join(str(phrase or "").split())
    low = text.lower()
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


_DEICTIC_LEAD = re.compile(r"^(?:Today|Tomorrow|Yesterday|Tonight)\b")


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


# --- units and currencies (the tables `ai/utilities.py` converts with) -------------

#: name -> (dimension, size in the dimension's base unit, the name said).
#: Base units: metre, kilogram, litre, second, square metre, metre per second,
#: byte, joule, watt, pascal, degree of arc, hertz, newton, volt, ampere, ohm,
#: ampere hour, percent, bit per second, lumen, lux. Temperature converts by
#: formula, not by size. Single letters and words that are also words ("in",
#: "st") are read only glued to a number ("5in", "10k"): see `_GLUED_ONLY`.
UNITS: dict[str, tuple[str, float, str]] = {}


def _unit(dimension: str, size: float, said: str, *names: str) -> None:
    for name in (said, *names):
        UNITS[name] = (dimension, size, said)


for _args in (
    ("length", 1e-9, "nanometres", "nm", "nanometre", "nanometer", "nanometers"),
    ("length", 1e-6, "micrometres", "µm", "um", "micron", "microns", "micrometre", "micrometer", "micrometers"),
    ("length", 0.001, "millimetres", "mm", "millimetre", "millimeter", "millimeters"),
    ("length", 0.01, "centimetres", "cm", "centimetre", "centimeter", "centimeters"),
    ("length", 0.1, "decimetres", "dm", "decimetre", "decimeter", "decimeters"),
    ("length", 1.0, "metres", "m", "metre", "meter", "meters"),
    ("length", 1000.0, "kilometres", "km", "kms", "kilometre", "kilometer", "kilometers", "k"),
    ("length", 0.0254, "inches", "in", "inch", '"'),
    ("length", 0.1016, "hands", "hand"),
    ("length", 0.3048, "feet", "ft", "foot"),
    ("length", 0.9144, "yards", "yd", "yds", "yard"),
    ("length", 1.8288, "fathoms", "fathom"),
    ("length", 20.1168, "chains", "chain"),
    ("length", 201.168, "furlongs", "furlong"),
    ("length", 1609.344, "miles", "mi", "mile"),
    ("length", 1852.0, "nautical miles", "nmi", "nautical mile"),
    ("length", 4828.032, "leagues", "league"),
    ("length", 1.495978707e11, "astronomical units", "au", "astronomical unit"),
    ("length", 9.4607304725808e15, "light years", "ly", "light year", "light-year", "light-years"),
    ("mass", 1e-9, "micrograms", "µg", "mcg", "ug", "microgram"),
    ("mass", 0.000001, "milligrams", "mg", "milligram"),
    ("mass", 0.0002, "carats", "ct", "carat"),
    ("mass", 0.00006479891, "grains", "grain"),
    ("mass", 0.001, "grams", "g", "gram", "gr"),
    ("mass", 1.0, "kilograms", "kg", "kgs", "kilogram", "kilo", "kilos"),
    ("mass", 1000.0, "tonnes", "t", "tonne", "metric ton", "metric tons"),
    ("mass", 907.18474, "short tons", "short ton", "us ton", "us tons"),
    ("mass", 1016.0469088, "long tons", "long ton", "uk ton", "uk tons"),
    ("mass", 50.80234544, "hundredweight", "cwt"),
    ("mass", 0.028349523125, "ounces", "oz", "ounce"),
    ("mass", 0.0311034768, "troy ounces", "ozt", "troy ounce"),
    ("mass", 0.00155517384, "pennyweights", "dwt", "pennyweight"),
    ("mass", 0.45359237, "pounds", "lb", "lbs", "pound"),
    ("mass", 6.35029318, "stone", "st", "stones"),
    ("volume", 0.001, "millilitres", "ml", "millilitre", "milliliter", "milliliters"),
    ("volume", 0.01, "centilitres", "cl", "centilitre", "centiliter", "centiliters"),
    ("volume", 0.1, "decilitres", "dl", "decilitre", "deciliter", "deciliters"),
    ("volume", 1.0, "litres", "l", "litre", "liter", "liters", "ltr"),
    ("volume", 100.0, "hectolitres", "hl", "hectolitre", "hectoliter", "hectoliters"),
    ("volume", 1000.0, "cubic metres", "m3", "m³", "cu m", "cubic metre", "cubic meter", "cubic meters"),
    ("volume", 0.001, "cubic centimetres", "cc", "cm3", "cm³", "cubic centimetre", "cubic centimeter", "cubic centimeters"),
    ("volume", 0.016387064, "cubic inches", "in3", "cu in", "cubic inch"),
    ("volume", 28.316846592, "cubic feet", "ft3", "cu ft", "cubic foot"),
    ("volume", 0.00492892159375, "teaspoons", "tsp", "teaspoon"),
    ("volume", 0.01, "dessertspoons", "dsp", "dessertspoon"),
    ("volume", 0.01478676478125, "tablespoons", "tbsp", "tablespoon"),
    ("volume", 0.2365882365, "cups", "cup"),
    ("volume", 0.0295735295625, "fluid ounces", "fl oz", "floz", "fluid ounce"),
    ("volume", 0.0284130625, "UK fluid ounces", "uk fl oz", "uk fluid ounce", "uk fluid ounces"),
    ("volume", 0.1420653125, "gills", "gill"),
    ("volume", 0.473176473, "US pints", "pint", "pints", "us pint", "us pints"),
    ("volume", 0.56826125, "UK pints", "uk pint", "uk pints", "imperial pint", "imperial pints"),
    ("volume", 0.946352946, "US quarts", "quart", "quarts", "qt", "us quart", "us quarts"),
    ("volume", 1.1365225, "UK quarts", "uk quart", "uk quarts", "imperial quart", "imperial quarts"),
    ("volume", 3.785411784, "US gallons", "gallon", "gallons", "gal", "us gallon", "us gallons"),
    ("volume", 4.54609, "UK gallons", "uk gallon", "uk gallons", "imperial gallon", "imperial gallons"),
    ("volume", 158.987294928, "barrels", "bbl", "barrel"),
    ("time", 1e-9, "nanoseconds", "ns", "nanosecond"),
    ("time", 1e-6, "microseconds", "µs", "microsecond"),
    ("time", 0.001, "milliseconds", "ms", "millisecond"),
    ("time", 1.0, "seconds", "s", "sec", "secs", "second"),
    ("time", 60.0, "minutes", "min", "mins", "minute"),
    ("time", 3600.0, "hours", "h", "hr", "hrs", "hour"),
    ("time", 86400.0, "days", "day"),
    ("time", 604800.0, "weeks", "week", "wk", "wks"),
    ("time", 1209600.0, "fortnights", "fortnight"),
    ("time", 2629800.0, "months", "month", "mo"),
    ("time", 31557600.0, "years", "year", "yr", "yrs"),
    ("time", 315576000.0, "decades", "decade"),
    ("time", 3155760000.0, "centuries", "century"),
    ("time", 31557600000.0, "millennia", "millennium"),
    ("area", 0.000001, "square millimetres", "mm2", "mm²", "sq mm", "square millimetre"),
    ("area", 0.0001, "square centimetres", "cm2", "cm²", "sq cm", "square centimetre"),
    ("area", 1.0, "square metres", "m2", "m²", "sq m", "square metre", "square meters", "square meter"),
    ("area", 1000000.0, "square kilometres", "km2", "km²", "sq km", "square kilometre"),
    ("area", 0.00064516, "square inches", "in2", "sq in", "square inch"),
    ("area", 0.09290304, "square feet", "ft2", "sq ft", "square foot"),
    ("area", 0.83612736, "square yards", "yd2", "sq yd", "square yard"),
    ("area", 2589988.110336, "square miles", "mi2", "sq mi", "square mile"),
    ("area", 10000.0, "hectares", "ha", "hectare"),
    ("area", 4046.8564224, "acres", "acre", "ac"),
    ("speed", 1 / 3.6, "kilometres an hour", "km/h", "kph", "kmh", "kilometres per hour", "kilometers per hour"),
    ("speed", 0.44704, "miles an hour", "mph", "miles per hour"),
    ("speed", 1.0, "metres a second", "m/s", "metres per second", "meters per second"),
    ("speed", 0.3048, "feet a second", "ft/s", "fps", "feet per second"),
    ("speed", 0.514444, "knots", "kn", "knot", "kt"),
    ("data", 0.125, "bits", "bit"),
    ("data", 125.0, "kilobits", "kbit", "kilobit"),
    ("data", 125000.0, "megabits", "mbit", "megabit"),
    ("data", 1.25e8, "gigabits", "gbit", "gigabit"),
    ("data", 1.0, "bytes", "b", "byte"),
    ("data", 1e3, "kilobytes", "kb", "kilobyte"),
    ("data", 1e6, "megabytes", "mb", "megabyte"),
    ("data", 1e9, "gigabytes", "gb", "gigabyte"),
    ("data", 1e12, "terabytes", "tb", "terabyte"),
    ("data", 1e15, "petabytes", "pb", "petabyte"),
    ("data", 1024.0, "kibibytes", "kib", "kibibyte"),
    ("data", 1048576.0, "mebibytes", "mib", "mebibyte"),
    ("data", 1073741824.0, "gibibytes", "gib", "gibibyte"),
    ("data", 1099511627776.0, "tebibytes", "tib", "tebibyte"),
    ("data rate", 1e3, "kilobits a second", "kbps", "kb/s", "kilobits per second"),
    ("data rate", 1e6, "megabits a second", "mbps", "mbit/s", "megabits per second"),
    ("data rate", 1e9, "gigabits a second", "gbps", "gbit/s", "gigabits per second"),
    ("energy", 1.0, "joules", "j", "joule"),
    ("energy", 1000.0, "kilojoules", "kj", "kilojoule"),
    ("energy", 1e6, "megajoules", "mj", "megajoule"),
    ("energy", 4184.0, "kilocalories", "kcal", "calories", "calorie", "cal", "kilocalorie"),
    ("energy", 3600.0, "watt hours", "wh", "watt hour", "watt-hour", "watt-hours"),
    ("energy", 3.6e6, "kilowatt hours", "kwh", "kilowatt hour", "kilowatt-hour", "kilowatt-hours"),
    ("energy", 3.6e9, "megawatt hours", "mwh", "megawatt hour"),
    ("energy", 1055.05585262, "British thermal units", "btu", "btus", "british thermal unit"),
    ("energy", 105505585.262, "therms", "therm"),
    ("energy", 1.602176634e-19, "electronvolts", "ev", "electronvolt", "electron volts"),
    ("power", 1.0, "watts", "w", "watt"),
    ("power", 1e3, "kilowatts", "kw", "kilowatt"),
    ("power", 1e6, "megawatts", "mw", "megawatt"),
    ("power", 1e9, "gigawatts", "gw", "gigawatt"),
    ("power", 745.69987158227022, "horsepower", "hp", "bhp"),
    ("pressure", 1.0, "pascals", "pa", "pascal"),
    ("pressure", 100.0, "hectopascals", "hpa", "hectopascal"),
    ("pressure", 1000.0, "kilopascals", "kpa", "kilopascal"),
    ("pressure", 1e6, "megapascals", "mpa", "megapascal"),
    ("pressure", 1e5, "bar", "bars"),
    ("pressure", 100.0, "millibars", "mbar", "millibar"),
    ("pressure", 6894.757293168, "pounds per square inch", "psi"),
    ("pressure", 101325.0, "atmospheres", "atm", "atmosphere"),
    ("pressure", 133.322387415, "millimetres of mercury", "mmhg"),
    ("pressure", 3386.389, "inches of mercury", "inhg"),
    ("pressure", 133.32236842, "torr",),
    ("angle", 1.0, "degrees", "deg", "degree"),
    ("angle", 57.29577951308232, "radians", "rad", "radian"),
    ("angle", 0.9, "gradians", "grad", "gradian", "gon"),
    ("angle", 360.0, "turns", "turn", "revolutions", "revolution"),
    ("angle", 1 / 60, "arcminutes", "arcmin", "arcminute"),
    ("angle", 1 / 3600, "arcseconds", "arcsec", "arcsecond"),
    ("frequency", 1.0, "hertz", "hz"),
    ("frequency", 1e3, "kilohertz", "khz"),
    ("frequency", 1e6, "megahertz", "mhz"),
    ("frequency", 1e9, "gigahertz", "ghz"),
    ("frequency", 1 / 60, "revolutions a minute", "rpm", "revolutions per minute"),
    ("frequency", 1 / 60, "beats a minute", "bpm", "beats per minute"),
    ("force", 1.0, "newtons", "newton"),
    ("force", 4.4482216152605, "pounds force", "lbf", "pound force", "pound-force"),
    ("force", 9.80665, "kilograms force", "kgf", "kilogram force", "kilogram-force"),
    ("voltage", 1.0, "volts", "v", "volt"),
    ("voltage", 0.001, "millivolts", "mv", "millivolt"),
    ("voltage", 1000.0, "kilovolts", "kv", "kilovolt"),
    ("current", 1.0, "amps", "amp", "ampere", "amperes"),
    ("current", 0.001, "milliamps", "ma", "milliamp", "milliampere", "milliamperes"),
    ("resistance", 1.0, "ohms", "ohm", "Ω"),
    ("resistance", 1000.0, "kilohms", "kohm", "kΩ", "kilohm"),
    ("charge", 1.0, "amp hours", "ah", "amp hour", "amp-hour", "amp-hours"),
    ("charge", 0.001, "milliamp hours", "mah", "milliamp hour", "milliamp-hours"),
    ("ratio", 1.0, "percent", "%", "per cent", "pc"),
    ("ratio", 0.1, "per mille", "‰", "permille"),
    ("ratio", 0.0001, "parts per million", "ppm"),
    ("luminous flux", 1.0, "lumens", "lm", "lumen"),
    ("illuminance", 1.0, "lux", "lx"),
    ("temperature", 1.0, "°C", "c", "celsius", "°c", "degrees c", "degrees celsius", "centigrade"),
    ("temperature", 1.0, "°F", "f", "fahrenheit", "°f", "degrees f", "degrees fahrenheit"),
    ("temperature", 1.0, "K", "kelvin"),
):
    _unit(*_args)

#: Names read only when glued to their number: "10k" is ten kilometres, "10 k"
#: is nothing; "5in" is five inches, "5 in the morning" is not.
_GLUED_ONLY = frozenset(n for n in UNITS if len(n) == 1) | {"in", "st", "ac", "kn", "kt", "gr", "pc", "mo", "ma", "ah", "lm", "ct", "rad", "turn", "turns", "grad", "gon"}
#: Names the converter reads that a sentence does not: "1990s" is a decade,
#: not 1,990 seconds.
_NOT_IN_TEXT = frozenset({"s", '"'})
#: Symbols a person writes spaced and in capitals: "a 60 W bulb", "12 V".
_SPACED_CAPITALS = frozenset({"W", "V", "J", "K"})

#: Currency names to ISO codes. Rates are not here: `utilities.RATES` holds
#: them with the date they were set (decision 43).
CURRENCY_NAMES = {
    "usd": "USD", "dollar": "USD", "dollars": "USD", "us dollars": "USD", "bucks": "USD", "$": "USD",
    "eur": "EUR", "euro": "EUR", "euros": "EUR", "€": "EUR",
    "gbp": "GBP", "pound": "GBP", "pounds": "GBP", "pounds sterling": "GBP", "quid": "GBP", "£": "GBP",
    "jpy": "JPY", "yen": "JPY", "¥": "JPY", "aud": "AUD", "australian dollars": "AUD", "cad": "CAD", "canadian dollars": "CAD",
    "nzd": "NZD", "new zealand dollars": "NZD", "chf": "CHF", "swiss francs": "CHF", "francs": "CHF", "cny": "CNY", "yuan": "CNY",
    "rmb": "CNY", "inr": "INR", "rupees": "INR", "sek": "SEK", "kronor": "SEK", "nok": "NOK", "dkk": "DKK", "sgd": "SGD",
    "hkd": "HKD", "mxn": "MXN", "pesos": "MXN", "brl": "BRL", "reais": "BRL", "zar": "ZAR", "rand": "ZAR", "krw": "KRW",
    "won": "KRW", "pln": "PLN", "zloty": "PLN",
}


# --- a question's stretch ending now (was search/query.py's `_RANGE_RULES`) -----------
#
# Phrases that mean "a stretch ending now" rather than a single day. `timewords`
# resolves "last week" to one date, the Monday of the previous week, which is
# right for a note that says "I'll do it last week" and wrong for a question,
# where the person means the whole stretch. So ranges are recognised here, and
# anything not in this list falls through to `timewords` and becomes a single
# day (widened by its own precision below).
#
# Ordered longest-first: "in the last couple of weeks" has to be tried before
# "the last week" or the shorter phrase eats the longer one's meaning.
_QUESTION_RANGES: list[tuple[str, object]] = [
    (
        r"(?:in|over|during|from|within)?\s*(?:the\s+)?(?:last|past|previous)\s+"
        r"(\d{1,3}|a|an|one|two|three|four|five|six|seven|eight|nine|ten|"
        r"eleven|twelve|few|couple of)\s+(day|week|fortnight|month|year)s?",
        "back",
    ),
    (r"(?:in|over|during)?\s*(?:the\s+)?(?:last|past)\s+(week)\b", "back"),
    (r"(?:in|over|during)?\s*(?:the\s+)?(?:last|past)\s+(month)\b", "back"),
    (r"(?:in|over|during)?\s*(?:the\s+)?(?:last|past)\s+(year)\b", "back"),
    (r"\btoday\b", "today"),
    (r"\byesterday\b", "yesterday"),
    (r"\bthis\s+week\b", "this_week"),
    (r"\bthis\s+month\b", "this_month"),
    (r"\bthis\s+year\b", "this_year"),
    (r"\brecent(?:ly)?\b", "recent"),
]

_COMPILED_QUESTION_RANGES = [(re.compile(p, re.IGNORECASE), kind) for p, kind in _QUESTION_RANGES]

_RANGE_UNIT_DAYS = {"day": 1, "week": 7, "fortnight": 14, "month": 30, "year": 365}

#: What "recently" means when nobody says. A fortnight: long enough that a
#: quiet week does not come back empty, short enough that "recently" still
#: means something.
RECENT_DAYS = 14


def _range_count(word: str) -> int:
    word = word.strip().lower()
    if word.isdigit():
        return int(word)
    return {
        "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
        "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
        "twelve": 12, "few": 3, "couple of": 2,
    }.get(word, 1)


def _range_for(kind: str, match: re.Match, today: date) -> tuple[date, date]:
    if kind == "back":
        groups = [g for g in match.groups() if g]
        if len(groups) >= 2:
            days = _range_count(groups[0]) * _RANGE_UNIT_DAYS[groups[1].lower()]
        else:
            days = _RANGE_UNIT_DAYS[groups[0].lower()] if groups else RECENT_DAYS
        return today - timedelta(days=days), today
    if kind == "today":
        return today, today
    if kind == "yesterday":
        return today - timedelta(days=1), today - timedelta(days=1)
    if kind == "this_week":
        return today - timedelta(days=today.weekday()), today
    if kind == "this_month":
        return today.replace(day=1), today
    if kind == "this_year":
        return today.replace(month=1, day=1), today
    return today - timedelta(days=RECENT_DAYS), today  # "recent"



def is_lately(phrase: str) -> bool:
    """True for a bare "recently" or "lately": a lean towards new, not a span."""
    return bool(re.fullmatch(_LATELY, (phrase or "").strip().lower()))

def question_range(text: str, today: date) -> tuple[date, date, str, int, int, bool] | None:
    """(since, until, phrase, start, end, soft) for the first stretch-ending-now
    phrase in a search question, or None. `soft` is "recently": a lean, not
    a boundary (`search.query.Understood.soft`)."""
    for pattern, kind in _COMPILED_QUESTION_RANGES:
        match = pattern.search(text)
        if match:
            since, until = _range_for(kind, match, today)
            return since, until, match.group(0).strip(), match.start(), match.end(), kind == "recent"
    return None


def question_day(text: str, today: date, locale: str | None = None) -> tuple[date, date, str, int, int] | None:
    """(since, until, phrase, start, end) for the first day or span a search
    question names that is not a stretch ending now ("on tuesday", "in
    March", "two weeks ago"), read in the past tense. A day said in weeks or
    months is widened around it: nobody remembers which day they wrote
    something two weeks ago. `locale` orders a numeric date ("3/4" is 3 April
    unless the locale writes the month first); none means day first."""
    anchor = datetime.combine(today, time(12))
    for found in recognise(text, now=anchor, tense="past", locale=locale):
        if found.rank or found.kind not in ("date", "datetime", "range"):
            continue
        if text[max(0, found.start - 1):found.start] == ":":
            continue  # "before:tuesday", an operator the search could not read: no date is made up
        if found.kind == "range":
            first, last, _grain = found.value
            if isinstance(first, time):
                continue
            return first, last, found.text, found.start, found.end
        day = found.value.date() if isinstance(found.value, datetime) else found.value
        words = found.text.lower()
        if "fortnight" in words or re.search(r"\bweeks?\b", words):
            return day - timedelta(days=3), day + timedelta(days=3), found.text, found.start, found.end
        if re.search(r"\bmonths?\b", words):
            return day - timedelta(days=15), day + timedelta(days=15), found.text, found.start, found.end
        return day, day, found.text, found.start, found.end
    return None


_AHEAD = re.compile(r"\b(?:next (?:week|month|year|fortnight)|coming fortnight)\b|\btomorrow\b", re.IGNORECASE)


def says_ahead(text: str) -> bool:
    """True when a sentence points to time to come ("next week", "tomorrow"):
    the fact graph's cue for a plan rather than a record."""
    return bool(_AHEAD.search(text or ""))


#: A question about the change or the past ("what did I use to...", "a year
#: ago"): `supersede.current` keeps every note for one. Read here, with the
#: other date words (decision 46).
_PAST = re.compile(
    r"\b(?:changed?|changes|used to|before|previous(?:ly)?|last (?:semester|term|year|time)|old|older|history|over time|"
    r"compare|comparison|difference|ago|in the past|originally|first)\b",
    re.I,
)


#: A question about how something has gone is about the run of notes, not the
#: latest one: "how's the gym going" reads 80 kg and then 90 kg (INBOX 812).
_PROGRESS = re.compile(
    r"\bprogress\b|\bhow(?:'s|s| is| are| has| have|'ve)\b[^?.!]{0,40}?\b(?:going|been|coming along|progressing)\b",
    re.I,
)


def says_past(text: str) -> bool:
    return bool(_PAST.search(text or "") or _PROGRESS.search(text or ""))


#: Day and month names that are always names. "march" and "may" are left out:
#: they are as often a verb as a date.
_CAPITAL_NAMES = re.compile(
    r"(?<![\w'])(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|january|february|april|june|july|august|"
    r"september|october|november|december)(?![\w'])"
)


def capitalise_names(text: str) -> str:
    """`text` with its weekday and month names given capitals (the
    proofreader's day names)."""
    return _CAPITAL_NAMES.sub(lambda m: m.group(0).capitalize(), text)


# --- date questions ("how many days until", "what date is it in 3 weeks") ----------
#
# The question's shape is read here, with the date words in it, so the
# utilities that answer them read no time words themselves (decision 46).

#: "how many days until X", and the short forms people type (CHAT_PLAN A1):
#: "days until 25 Dec", "number of days till christmas", "countdown to X".
_HOW_MANY = r"^(?:how (?:many|long) (?P<unit>days|weeks|months)?|(?:the )?(?:number of |count of )?(?P<bare>days|weeks|months)|countdown)"
_DAYS_UNTIL = re.compile(_HOW_MANY + r"\s*(?:is it |are there |left )?(?:until|till|til|to|before)\s+(?P<what>.+)$", re.I)
_DAYS_SINCE = re.compile(_HOW_MANY + r"\s*(?:has it been |is it |ago was |have passed |)?(?:since)\s+(?P<what>.+)$", re.I)
_DATE_FROM_NOW = re.compile(
    r"^what (?:day|date)(?: of the week)? (?:is|will it be|was)\s+(?:it\s+)?(?:in\s+)?(\d{1,3}|a|an|one|two|three|four|five|six|seven|eight|nine|ten)\s+(days?|weeks?|months?|years?)(?:\s+(from now|from today|ago))?$",
    re.I,
)


def days_question(text: str) -> tuple[str, str] | None:
    """("future", what) for "how many days until what", ("past", what) for
    "how long since what", else None."""
    for pattern, tense in ((_DAYS_UNTIL, "future"), (_DAYS_SINCE, "past")):
        found = pattern.match(text)
        if found:
            return tense, found.group("what")
    return None


def offset_question(text: str) -> tuple[str, str, bool] | None:
    """(amount, unit, ago) for "what date is it in 3 weeks" or "what day was
    it 10 days ago", else None."""
    found = _DATE_FROM_NOW.match(text)
    if not found:
        return None
    return found.group(1), found.group(2), not (found.group(3) or "from").startswith("from")

#: Any sentence that may carry a day, wider than `looks_dated`: abbreviated
#: months and weekdays, "21st", "3/11", "due". A cheap test before the
#: recogniser runs on it (notes are read by the hundred).
_DATED_WIDE = re.compile(
    r"\b(?:today|tomorrow|tonight|yesterday|next (?:week|month|year|[a-z]+day)|this (?:week|month|weekend)|weekend|"
    r"(?:mon|tues?|wed(?:nes)?|thu(?:rs?)?|fri|sat(?:ur)?|sun)(?:day)?|\d{1,2}(?:st|nd|rd|th)\b(?: of)?(?: (?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*)?|"
    r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.? \d{1,2}|\d{1,2} (?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*|"
    r"\d{1,2}[/.-]\d{1,2}(?:[/.-]\d{2,4})?|\d{4}-\d{2}-\d{2}|by (?:the )?end of|before (?:we|i) (?:go|leave)|deadline|due)\b", re.I)


def dated_sentence(text: str) -> bool:
    """Whether a sentence may name a day or a deadline at all."""
    return bool(_DATED_WIDE.search(text or ""))


_SINCE_Q = re.compile(
    r"^(?:(?:so|ok|okay|hey|please|pls|can you|could you|quick question|tell me)[, ]+)*"
    r"(?:how (?:many|much) (?P<u>days|weeks|months)(?: (?:has it been|have passed|have gone by|has passed|ago was|ago is|ago did)| ago)?\s+(?:since|was|is)"
    r"|(?P<u2>days|weeks|months) since|how long (?:has it been )?since|how long ago (?:was|is|did|were))"
    r"\s+(?P<d>.+?)\W*$", re.I)


def since_question(text: str) -> tuple[str, str] | None:
    """(unit, the day as said) for "how many days since 1 october", "weeks
    since the 3rd", "how long ago was 1 september"; None for anything else."""
    found = _SINCE_Q.match(" ".join((text or "").split()))
    if not found:
        return None
    return (found.group("u") or found.group("u2") or "days").lower(), found.group("d").strip()


def states_its_date(text: str, now: datetime) -> bool:
    """Whether the first date `text` reads as is written out (a month and a
    day, or a numeric date), rather than counted from the day it was said on
    ("Friday", "tomorrow", "the 21st"). Composer follow-ups use it to say how a
    note's day was read."""
    for span in recognise(text, now=now, tense="future"):
        if span.rank == 0 and span.kind in ("date", "datetime"):
            low = span.text.lower()
            return bool(re.search(r"\d{4}-\d{2}-\d{2}|\d{1,2}[/.]\d{1,2}[/.]\d{2,4}", low)) or any(
                m in low for m in _MONTHS if len(m) > 2
            )
    return False


_DAY_OFFSET = re.compile(
    r"^(?P<in>in\s+)?(?P<n>\d{1,4}|a|an|one|two|three|four|five|six|seven|eight|nine|ten|twelve|a couple of|couple of|a few)\s+"
    r"(?P<u>days?|weeks?|fortnights?|months?|years?)\s*(?P<d>from now|from today|from|after|before|ago|since|later|earlier|hence|prior to|away)?\s*(?P<a>.*?)\W*$",
    re.I)
_BACKWARD = ("before", "ago", "earlier", "prior to")


def shift_day(base: date, n: int, unit: str, sign: int) -> date:
    """`base` moved n days, weeks, fortnights, months or years (a month's end
    clamps: 31 January plus a month is 28 February)."""
    unit = unit.lower().rstrip("s")
    if unit in ("day", "week", "fortnight"):
        return base + timedelta(days={"day": 1, "week": 7, "fortnight": 14}[unit] * n * sign)
    index = base.year * 12 + base.month - 1 + n * (12 if unit == "year" else 1) * sign
    year, month = divmod(index, 12)
    month += 1
    nxt = date(year + (month == 12), month % 12 + 1, 1)
    return base.replace(year=year, month=month, day=min(base.day, (nxt - timedelta(days=1)).day))


def _anchor_day(anchor: str, today: date) -> date | None:
    if not anchor or anchor.lower() in ("now", "today"):
        return today
    got = resolve(anchor, datetime.combine(today, time(10)))
    return got.date() if got else None


def day_offset(text: str, today: date) -> dict | None:
    """"3 weeks from friday", "100 days ago", "in 2 months", "2 weeks after 1
    december": {"target", "base", "n", "unit", "sign", "anchor"}, else None.
    Needs a direction word or a leading "in"; the anchor is read as a day."""
    found = _DAY_OFFSET.match((text or "").strip())
    if not found or not (found["in"] or found["d"]):
        return None
    n = _amount(found["n"])
    direction = (found["d"] or "").lower()
    anchor = found["a"].strip(" ,.?")
    if n is None or (found["in"] and direction):
        return None
    base = _anchor_day(anchor, today)
    if base is None:
        return None
    sign = -1 if direction in _BACKWARD else 1
    return {"target": shift_day(base, n, found["u"], sign), "base": base, "n": n, "unit": found["u"].lower().rstrip("s"),
            "sign": sign, "anchor": anchor, "said": direction or "in"}



# --- the part of the day a note was about ------------------------------------------

_EVENING_SAID = re.compile(r"\b(?:after work|in the evening|this evening|tonight|after dinner)\b", re.IGNORECASE)
_MORNING_SAID = re.compile(r"\b(?:before work|in the morning|this morning|early morning|at dawn)\b", re.IGNORECASE)


def part_of_day(text: str) -> str | None:
    """"evening" when a text says it was after work or in the evening (the
    insights' "after work" count reads this), "morning" when it says the
    morning and not the evening, else None."""
    if _EVENING_SAID.search(text or ""):
        return "evening"
    return "morning" if _MORNING_SAID.search(text or "") else None


# --- the recogniser: every span a text reads as ----------------------------------------

_WEEKDAY_CODES = ("MO", "TU", "WE", "TH", "FR", "SA", "SU")
_WEEKDAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
_MONTH_NAMES = ("January", "February", "March", "April", "May", "June", "July", "August", "September",
                "October", "November", "December")
_ORDINAL_WORDS = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7,
                  "eighth": 8, "ninth": 9, "tenth": 10}
#: Locales that write the month first ("2/11" is 11 February in them).
_MONTH_FIRST = ("en-us", "en_us", "us", "en-ph", "en-ca")
_FAHRENHEIT = ("en-us", "en_us", "us")


@dataclass(frozen=True)
class Span:
    """One thing read in a text: its kind, the words as written and where,
    the value, how it was read in plain words, and its rank (0 the reading;
    1 and on the other readings of the same words)."""

    kind: str
    text: str
    start: int
    end: int
    value: object
    read_as: str
    rank: int = 0

    def json(self) -> dict:
        return {"kind": self.kind, "text": self.text, "start": self.start, "end": self.end,
                "value": _jsonable(self.kind, self.value), "read_as": self.read_as, "rank": self.rank}


def _jsonable(kind: str, value: object) -> object:
    if kind == "range":
        first, last, grain = value
        return {"start": _jsonable("x", first), "end": _jsonable("x", last), "grain": grain}
    if kind == "money":
        return {"amount": value[0], "currency": value[1]}
    if kind in ("quantity", "temperature"):
        return {"amount": value[0], "unit": value[1], "dimension": value[2] if len(value) > 2 else "temperature"}
    if isinstance(value, datetime):
        return value.isoformat(timespec="minutes")
    if isinstance(value, (date, time)):
        return value.isoformat() if isinstance(value, date) else value.strftime("%H:%M")
    if isinstance(value, timedelta):
        return {"seconds": int(value.total_seconds())}
    return value


def _lower(text: str) -> str:
    """Lower case that keeps every offset ("İ" lowers to two characters)."""
    return "".join(c if len(c.lower()) != 1 else c.lower() for c in text)


def _day_words(day: date) -> str:
    return f"{_WEEKDAY_NAMES[day.weekday()]} {day.day} {_MONTH_NAMES[day.month - 1]} {day.year}"


def _clock_words(at: time) -> str:
    return at.strftime("%H:%M")


def _num_words(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:g}"


def _duration_words(seconds: float) -> str:
    out, left = [], int(round(seconds))
    for size, name in ((86400, "day"), (3600, "hour"), (60, "minute"), (1, "second")):
        if left >= size:
            n, left = divmod(left, size)
            out.append(f"{n} {name}{'' if n == 1 else 's'}")
    return " ".join(out) or "0 seconds"


_PAST_CUE = re.compile(r"\b(?:did|was|were|wrote|written|had|went|met|saw|ran|made|said|happened|spent|paid|bought|"
                       r"finished|started|ago|earlier|previously|used to)\b")
_FUTURE_CUE = re.compile(r"\b(?:will|remind|due|until|till|going to|need to|have to|should|plan to|book|schedule|"
                         r"upcoming|shall)\b")


def tense_of(low: str) -> str | None:
    """"past", "future" or None, from the sentence's own verbs."""
    past, future = bool(_PAST_CUE.search(low)), bool(_FUTURE_CUE.search(low))
    return "past" if past and not future else "future" if future and not past else None


# Each collector yields candidates (start, end, kind, value, read_as, rank).
_PRIORITY_OF = {"email": 0, "url": 0, "phone": 0, "recurrence": 1, "alert": 1, "range": 2, "datetime": 3, "date": 4, "time": 5,
                "money": 6, "temperature": 7, "quantity": 8, "duration": 9, "tag": 10, "person": 10, "place": 10,
                "ordinal": 11, "number": 12}

_NUMBER = r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?"
_COMPILED: dict[str, object] = {}


def _rx(name: str) -> re.Pattern[str]:
    """Patterns compiled on first use: the unit alternation is long, and
    importing this module sits inside the composer's import budget."""
    if name not in _COMPILED:
        _COMPILED[name] = re.compile(_SOURCES[name]() if callable(_SOURCES[name]) else _SOURCES[name])
    return _COMPILED[name]


def _unit_names() -> str:
    return "|".join(sorted((re.escape(n.lower()) for n in UNITS), key=len, reverse=True))


def _money_names() -> str:
    return "|".join(sorted((re.escape(n) for n in CURRENCY_NAMES if n not in "$€£¥"), key=len, reverse=True))


_CLOCK_SRC = r"(?:noon|midday|midnight|(\d{1,2})(?::(\d{2}))?\s?(am|pm|a\.m\.|p\.m\.)?)"
_SOURCES: dict[str, object] = {
    "email": r"(?<![\w.+-])[\w.+-]+@[a-z0-9-]+(?:\.[a-z0-9-]+)+",
    "url": r"\b(?:https?://|www\.)[^\s<>\"')\]]+",
    "phone": r"(?<![\w+])(?:\+\d{1,3}[ .-]?)?(?:\(\d{2,5}\)[ .-]?)?\d{2,8}(?:[ .-]\d{2,8}){0,4}(?![\w])",
    "tag": r"(?<![\w&#/])#([a-z][\w-]{0,40})",
    "at_person": r"(?<![\w.@])@([a-z][\w-]{0,30})",
    "person": r"\b(?i:with|call|ring|meet|email|text|ask|tell|phone|message|thank)\s+([A-Z][a-z]+(?: [A-Z][a-z]+)?)\b",
    "place": r"\b(?i:in|to|at|from|near|visit|visiting)\s+(?:the\s+)?([A-Z][\w'-]+(?: [A-Z][\w'-]+){0,2})",
    "every": lambda: (
        r"\b(?:every|each)\s+(other\s+)?(?:(\d{1,2}|two|three|four|five|six)\s+)?"
        r"(day|week|month|year|fortnight|weekday|weekend|morning|afternoon|evening|night|"
        + "|".join(n for n in _WEEKDAYS if len(n) > 3) + r")s?\b"
        r"(?:\s+on\s+the\s+(\d{1,2})(?:st|nd|rd|th))?"
    ),
    "adverb": r"\b(daily|weekly|monthly|yearly|annually|fortnightly|nightly)\b",
    #: "the last friday of the month", "every first monday": a weekday's
    #: place in its month (TIMELINE_PLAN 11 row 8).
    "nth_in_month": _NTH_IN_MONTH,
    "nth_weekday": lambda: (
        r"\b(?:(every|each)\s+)?(?:the\s+)?(first|second|third|fourth|last|1st|2nd|3rd|4th)\s+("
        + "|".join(n for n in _WEEKDAYS if len(n) > 3) + r")(\s+(?:of|in)\s+(?:the|every|each)\s+month)?\b"
    ),
    #: An early alert: "1 day before", "an hour before", "the day before".
    "alert": (
        r"\b(?:(?:with\s+an?\s+)?(?:alert|warn|notify|ping|remind)(?:\s+me)?\s+)?"
        r"(\d{1,3}|an?|one|two|three|four|five|six|ten|fifteen|twenty|thirty|forty-five|the)\s+"
        r"(min(?:ute)?s?|hours?|hrs?|days?|weeks?)\s+(?:before(?:hand)?|ahead|early)\b"
    ),
    "plural_day": lambda: r"\b(" + "|".join(n + "s" for n in _WEEKDAYS if len(n) > 3) + r"|weekdays|weekends)\b",
    "clock_after": r"^,?\s?(?:(at|@|by|around)\s?)?" + _CLOCK_SRC + r"(?![\w:])",
    "part_after": r"^\s(morning|afternoon|evening|night)\b",
    "clock_before": r"(?:(at|by|around)\s)?" + _CLOCK_SRC + r"\s(?:on\s)?$",
    "quarter": r"\bq([1-4])(?:\s(\d{4}))?\b",
    "year": r"\b(in|during|since)\s((?:19|20)\d{2})\b(?![/.-]\d)",
    "numeric": r"(?<![\d/.:-])(\d{1,2})/(\d{1,2})(?:/(\d{4}|\d{2}))?(?![\d/])|(?<![\d/.:-])(\d{1,2})[.-](\d{1,2})[.-](\d{4})(?![\d.-])",
    "iso_dt": r"\b\d{4}-\d{2}-\d{2}[t ]\d{2}:\d{2}(?::\d{2})?(?:z|[+-]\d{2}:?\d{2})?\b",
    "this_part": r"\bthis (morning|afternoon|evening)\b",
    "part_said": r"^ (?:in the (morning|afternoon|evening)|at (night))\b",
    "clock": r"\b(noon|midday|midnight)\b|(?<![\d:.])\b(\d{1,2}):(\d{2})(?:\s?(am|pm|a\.m\.|p\.m\.))?(?![\w:])|"
             r"(?<![\d:.])\b(\d{1,2})\s?(am|pm|a\.m\.|p\.m\.)(?!\w)|\b(?:at|by|around|about)\s(\d{1,2})\b(?![:.,]\d)",
    #: "to" takes a word for its minutes ("the 5 to 7 train" is not a time) and
    #: never follows "from" or "between" ("open from ten to five" is a range).
    "spoken_clock": lambda: (
        r"(?:\b(?:at|by|around|about) )?(?<!from )(?<!between )\b(?:an? )?"
        r"(half|quarter|five|ten|twenty-five|twenty five|twenty|\d{1,2}(?= past)) (past|to) "
        rf"(\d{{1,2}}|{'|'.join(_SPOKEN_HOURS)})(?:\s?(am|pm|a\.m\.|p\.m\.))?(?![\w:])"
    ),
    #: Clocks said or written without a colon: "3 o'clock", "at three", "at ten
    #: thirty", "at 1530", "at 15h30". The figure forms need "at" (or the like),
    #: so "the 1530 train" and "1h30" (a duration) are not clocks.
    "word_clock": lambda: (
        rf"(?<![\w:])(?:(?:(?:at|by|around|about) )?(?P<o>\d{{1,2}}|{'|'.join(_SPOKEN_HOURS)}) ?o['’]? ?clock"
        rf"|(?:at|by|around|about) (?P<w>{'|'.join(_SPOKEN_HOURS)})(?: (?P<wm>{'|'.join(sorted(_WORD_MINUTES, key=len, reverse=True))}))?"
        r"(?: ?(?P<wa>am|pm|a\.m\.|p\.m\.))?"
        r"|(?:at|by|around|about) (?P<hh>[01]\d|2[0-3])(?P<mm>[0-5]\d)(?: ?(?:h|hrs|hours))?"
        r"|(?:at|by|around|about) (?P<h2>\d{1,2})h(?P<m2>[0-5]\d))(?![\w:/-])"
    ),
    "weeks_on": lambda: (
        r"\bin (?:(?P<f>a fortnight)|(?P<n>\d{1,2}|an?|one|two|three|four|five|six|seven|eight|nine|ten|twelve) "
        r"(?P<u>weeks?|fortnights?)),? (?:on )?(?P<d>" + "|".join(sorted(_WEEKDAYS, key=len, reverse=True)) + r")\b"
    ),
    "time_range": r"\b(?:from\s)?(\d{1,2})(?::(\d{2}))?\s?(am|pm)?\s?(?:-|–|to|until|till)\s?(\d{1,2})(?::(\d{2}))?\s?(am|pm)\b",
    "date_range": r"\b(?:from|between)\s",
    "anchored": lambda: rf"\b(\d{{1,3}}|{_COUNT_WORDS}|half an)\s(minutes?|mins?|hours?|hrs?)\s(before|after)\s",
    "from_now": lambda: _FROM_NOW.pattern,
    "relative": lambda: rf"{_IN_HOURS_MINUTES_SRC}|\bin\s(?:half an hour|a half hour|an? hour and a half|a quarter of an hour|"
                        rf"(\d{{1,4}}(?:\.\d{{1,2}})?|{_COUNT_WORDS})\s?(minutes?|mins?|hours?|hrs?))\b",
    "words_duration": lambda: (
        rf"\b(?:(an?|one|\d+) (hour|minute)s? and a half|half an hour|"
        rf"({_COUNT_WORDS}|half an) (seconds?|minutes?|hours?|days?|weeks?|fortnights?|months?|years?))\b(?! ago| before| after)"
    ),
    "hm": r"\b(\d{1,2})h(\d{2})\b",
    "money_pre": r"(?<![\w])([$€£¥])\s?(" + _NUMBER + r")(\s?(?:k|m|bn)\b)?",
    "money_code": lambda: r"\b(usd|eur|gbp|jpy|aud|cad|nzd|chf|cny|inr|sek|nok|dkk|sgd|hkd|mxn|brl|zar|krw|pln)\s?(" + _NUMBER + r")\b",
    "money_post": lambda: r"(?<![\w.,])(" + _NUMBER + r")\s?(" + _money_names() + r")\b",
    "quantity": lambda: r"(?<![\w.,])(" + _NUMBER + r")(\s?)(" + _unit_names() + r")(?![\w/²³])",
    "degrees": r"(?<![\w.,])(" + _NUMBER + r")\s?(?:degrees|deg|°)(?![\w])(?!\s?(?:c|f|celsius|fahrenheit)\b)",
    "number": r"(?<![\w.,/:])(" + _NUMBER + r")(?![\w%°]|[.,/:]\d)",
    "ordinal": r"\b(\d{1,3})(st|nd|rd|th)\b",
    "ordinal_word": r"\b(?:the|my|our|their|his|her|its|your)\s(" + "|".join(_ORDINAL_WORDS) + r")\b",
}

_NAME_STOP = frozenset(
    {"The", "A", "An", "My", "Our", "Your", "I", "Me", "Him", "Her", "Them", "Us", "It", "This", "That", "Today",
     "Tomorrow", "Tonight", "Noon", "Midnight", "Midday", "Christmas", "Easter", "Monday", "Tuesday", "Wednesday",
     "Thursday", "Friday", "Saturday", "Sunday", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun", *_MONTH_NAMES,
     "Jan", "Feb", "Mar", "Apr", "Jun", "Jul", "Aug", "Sep", "Sept", "Oct", "Nov", "Dec"}
)


def _hour_from(hour: int, minute: int, meridiem: str | None, evening: bool = False) -> time | None:
    if hour > 23 or minute > 59 or (meridiem and not 1 <= hour <= 12):
        return None
    return time(_hour24(hour, meridiem, evening) % 24, minute)


def _clock_match(found: re.Match, evening: bool = False, *, bare_ok: bool = False) -> time | None:
    """The time a `clock_after`/`clock_before` match says. A bare number
    counts only with "at" (or the like) before it, a colon or am/pm, the rule
    `_clock` keeps for `resolve`."""
    said = found.group(0).lower()
    if "midnight" in said:
        return time(0, 0)
    if "noon" in said or "midday" in said:
        return time(12, 0)
    hour, minute, meridiem = found.group(2), found.group(3), found.group(4)
    if hour is None:
        return None
    meridiem = (meridiem or "").replace(".", "") or None
    if not (found.group(1) or minute or meridiem or bare_ok):
        return None
    return _hour_from(int(hour), int(minute or 0), meridiem, evening)


def _bare_hour(clock: re.Match, low: str, end: int) -> bool:
    """"remind me friday 9 dentist": a bare 1 to 12 straight after a day is
    its hour when the next word is not something counted ("friday 3 people")
    or a unit."""
    hour = clock.group(2)
    if hour is None or clock.group(3) or not 1 <= int(hour) <= 12:
        return False
    rest = low[end + len(clock.group(0)):].split()
    return not rest or not (rest[0].endswith("s") or rest[0] in UNITS or rest[0] in ("people", "of", "more", "x"))


def _numeric_dates(low: str, today: date, locale: str | None, tense: str | None) -> list[tuple[int, int, list]]:
    """"2/11", "25/12/2026", "3.11.2026": (start, end, [(day, read_as), ...])
    with the locale's reading first and the other second when both are
    dates. "1/2 cup" is a fraction, not a date."""
    month_first = (locale or "").lower() in _MONTH_FIRST
    out = []
    for found in _rx("numeric").finditer(low):
        a, b, year_s = (found.group(1), found.group(2), found.group(3)) if found.group(1) else (found.group(4), found.group(5), found.group(6))
        after = low[found.end():found.end() + 12].lstrip()
        if not year_s and after and re.match(_unit_names(), after) and after.split(" ")[0].strip(".,") in UNITS:
            continue
        year = None if not year_s else int(year_s) + (2000 if len(year_s) == 2 else 0)
        readings = []
        day_first, other = (int(b), int(a), "day first"), (int(a), int(b), "month first")
        orders = (other, day_first) if month_first else (day_first, other)
        for month, day_n, said in orders:
            try:
                if year:
                    day = date(year, month, day_n)
                else:
                    day = _nearest([date(today.year + k, month, day_n) for k in (-1, 0, 1)], today, tense or "future")
            except ValueError:
                continue
            if all(day != r[0] for r in readings):
                readings.append((day, said))
        if readings:
            out.append((found.start(), found.end(), readings))
    return out


_MONTH_ONLY = re.compile(r"(?:in |during )?" + _MONTH_RE + _YEAR_AFTER_MONTH)
_END_OF_DAY_WORDS = ("end of day", "end of the day", "the end of the day", "eod")


def _without_edge(start: int, phrase: str, tense: str | None) -> tuple[int, str]:
    """A reminder's or an action's "before 14 November" is due that day, not
    a stretch from 1970 (`span` reads edges for questions about the past)."""
    lead, _, rest = phrase.partition(" ")
    if lead.lower() in ("before", "until", "till") and rest and tense != "past":
        return start + len(lead) + 1, rest
    return start, phrase


def _one_phrase(start: int, end: int, phrase: str, now: datetime, tense: str | None, out: list, bases: list) -> None:
    """One date phrase `find` located: a ready candidate, or a day that waits
    in `bases` for a clock beside it."""
    today = now.date()
    start, phrase = _without_edge(start, phrase, tense)
    words = phrase.lower()
    if words == "later today":
        out.append((start, end, "datetime", resolve("later today", now), "", 0))
        return
    if words in _END_OF_DAY_WORDS:
        out.append((start, end, "datetime", datetime.combine(today, time(17), now.tzinfo), "", 0))
        return
    monthly = _MONTH_ONLY.fullmatch(words)
    bare_month = bool(monthly) and not monthly.group(2)
    found = span(phrase, today, tense if bare_month else (tense or "future"))
    if found is None:
        return
    first, last, grain = found
    if first == last and grain == "day":
        part = next((p for p in _PARTS if re.search(rf"\b{p}\b", words)), None)
        bases.append((start, end, first, 0, part))
        return
    out.append((start, end, "range", found, "", 0))
    if bare_month and tense is None:
        other = _month_span(_MONTHS[monthly.group(1)], today, "future")
        if other[0] != first:
            out.append((start, end, "range", other, "", 1))


def _phrase_cands(low: str, now: datetime, tense: str | None) -> tuple:
    out: list[tuple] = []
    bases: list[tuple] = []  # (start, end, day, read_as, rank, evening-said)
    whole = low.strip(" .?!")
    phrases = list(find(low))
    if whole in _MONTHS and len(whole) > 3 and not phrases:
        at = low.index(whole)
        phrases = [(at, at + len(whole), whole)]
    for start, end, phrase in phrases:
        _one_phrase(start, end, phrase, now, tense, out, bases)
    return out, bases


def _pattern_cands(low: str, now: datetime) -> list[tuple]:
    """Quarters, years, ISO stamps and "this evening": read straight off the text."""
    today = now.date()
    out: list[tuple] = []
    for found in _rx("quarter").finditer(low):
        q, year = int(found.group(1)), int(found.group(2) or today.year)
        first = date(year, 3 * q - 2, 1)
        out.append((found.start(), found.end(), "range", (first, _month_end(date(year, 3 * q, 1)), "quarter"), "", 0))
    for found in _rx("year").finditer(low):
        year = int(found.group(2))
        last = today if found.group(1) == "since" else date(year, 12, 31)
        out.append((found.start(), found.end(), "range", (date(year, 1, 1), last, "year"), "", 0))
    for found in _rx("iso_dt").finditer(low):
        at = _iso(found.group(0), now)
        if at is not None:
            out.append((found.start(), found.end(), "datetime", at, "", 0))
    for found in _rx("this_part").finditer(low):
        at = datetime.combine(today, time(_PARTS[found.group(1)]), now.tzinfo)
        out.append((found.start(), found.end(), "datetime", at, "", 0))
    return out


def _clock_trailing(low: str, end: int, at: time | None, evening: bool, bare_hours: bool) -> tuple:
    """A clock right after the day ("monday at 5pm"): the time and where it ends."""
    clock = _rx("clock_after").match(low[end:end + 24])
    if clock and clock.group(0).strip(" ,"):
        read = _clock_match(clock, evening, bare_ok=bare_hours and _bare_hour(clock, low, end))
        if read is not None:
            return read, end + len(clock.group(0))
    return at, end


def _clock_leading(low: str, start: int, at: time | None, evening: bool) -> tuple:
    """A clock right before the day ("at 5pm on monday", "first thing monday")."""
    tail = low[max(0, start - 24):start]
    if tail.endswith("first thing "):
        return time(9), start - len("first thing ")
    if at is None:
        before = _rx("clock_before").search(tail)
        if before and before.group(0).strip():
            read = _clock_match(before, evening)
            if read is not None:
                return read, start - len(before.group(0))
    return at, start


def _base_cand(base: tuple, low: str, now: datetime, bare_hours: bool) -> tuple:
    """A day with the clock and part of day around it, as one candidate."""
    start, end, day, rank, part = base[:5]
    said = base[5] if len(base) > 5 else ""
    evening = part in ("evening", "night", "tonight")
    at: time | None = time(_PARTS[part]) if part else None
    after = _rx("part_after").match(low[end:end + 12])
    if at is None and after:
        part, at, end = after.group(1), time(_PARTS[after.group(1)]), end + after.end()
        evening = part in ("evening", "night")
    at, end = _clock_trailing(low, end, at, evening, bare_hours)
    at, start = _clock_leading(low, start, at, evening)
    if at is None:
        return (start, end, "date", day, said, rank)
    if at == time(0) and "midnight" in low[start:end]:
        return (start, end, "datetime", datetime.combine(day + timedelta(days=1), at, now.tzinfo), said, rank)
    return (start, end, "datetime", datetime.combine(day, at, now.tzinfo), said, rank)


def _date_cands(raw: str, low: str, now: datetime, locale: str | None, tense: str | None, bare_hours: bool = False) -> list[tuple]:
    out, bases = _phrase_cands(low, now, tense)
    for start, end, readings in _numeric_dates(low, now.date(), locale, tense):
        for rank, (day, said) in enumerate(readings):
            bases.append((start, end, day, rank, None, said))
    out += _pattern_cands(low, now)
    return out + [_base_cand(base, low, now, bare_hours) for base in bases]


def _spoken_cands(low: str) -> list[tuple]:
    """The clocks said aloud ("half past 4") as time spans."""
    out = []
    for found in _rx("spoken_clock").finditer(low):
        said = _spoken_clock(found)
        at = _hour_from(*said) if said else None
        if at is not None:
            out.append((found.start(), found.end(), "time", at, "", 0))
    return out


def _with_part_said(low: str, at: time, end: int, said_meridiem: bool) -> tuple[time, int]:
    """A clock followed by its part of day: "at 5 in the morning" is five, "at
    9 at night" twenty-one. The clock and where its words now end."""
    part = _rx("part_said").match(low[end:end + 20])
    if part and not said_meridiem:
        return time(at.hour % 12 + (0 if part.group(1) == "morning" else 12), at.minute), end + part.end()
    return at, end


def _word_cands(low: str) -> list[tuple]:
    """The clocks said or written without a colon ("3 o'clock", "at three",
    "at 1530", "at 15h30") as time spans."""
    out = []
    for found in _rx("word_clock").finditer(low):
        said = _word_clock(found) if _word_clock_ok(low, found) else None
        at = _hour_from(*said) if said else None
        if at is not None:
            at, end = _with_part_said(low, at, found.end(), bool(said[2]))
            out.append((found.start(), end, "time", at, "", 0))
    return out


def _clock_value(low: str, found: re.Match) -> time | None:
    """The time one `clock` match reads as, or None when it is not a clock
    (a bare number glued to a unit or a percent sign)."""
    if found.group(1):
        return time(0) if found.group(1) == "midnight" else time(12)
    if found.group(2):
        return _hour_from(int(found.group(2)), int(found.group(3)), (found.group(4) or "").replace(".", "") or None)
    if found.group(5):
        return _hour_from(int(found.group(5)), 0, found.group(6).replace(".", ""))
    after = low[found.end():found.end() + 14].lstrip()
    word = after.split(" ")[0].strip(".,") if after else ""
    if after[:1] in ("%", "°") or (word in UNITS and word not in _GLUED_ONLY):
        return None
    return _hour_from(int(found.group(7)), 0, None)


def _clock_cands(low: str) -> list[tuple]:
    out = []
    for found in _rx("clock").finditer(low):
        at = _clock_value(low, found)
        if at is not None:
            at, end = _with_part_said(low, at, found.end(), bool(found.group(4) or found.group(6)))
            out.append((found.start(), end, "time", at, "", 0))
    return out


def _time_range_cands(low: str) -> list[tuple]:
    out = []
    for found in _rx("time_range").finditer(low):
        h1, m1, ap1, h2, m2, ap2 = found.groups()
        first = _hour_from(int(h1), int(m1 or 0), ap1 or (ap2 if int(h1) <= int(h2) else None))
        last = _hour_from(int(h2), int(m2 or 0), ap2)
        if first and last and first < last:
            out.append((found.start(), found.end(), "range", (first, last, "time"), "", 0))
    return out


def _time_cands(low: str) -> list[tuple]:
    return _clock_cands(low) + _spoken_cands(low) + _word_cands(low) + _time_range_cands(low)


def _relative_cands(low: str, now: datetime, tense: str | None) -> list[tuple]:
    if tense == "past":
        return []  # "ran 10k in 52 minutes" is how long it took, not when
    out = _weeks_on_cands(low, now)
    for found in (*_rx("relative").finditer(low), *_rx("from_now").finditer(low)):
        got = relative_delta(found.group(0))
        if got is not None:
            out.append((found.start(), found.end(), "datetime", now + got[0], "", 0))
    return out


def _clock_after(low: str, end: int, evening: bool) -> tuple[time, int] | None:
    """The clock a repeat names right after its words ("every day at 7:30",
    "... at half past 7") and how much text it took."""
    tail = low[end:end + 30]
    clock = _rx("clock_after").match(tail[:24])
    if clock and clock.group(0).strip(" ,"):
        at = _clock_match(clock, evening)
        if at is not None:
            return at, len(clock.group(0))
    lead = len(tail) - len(tail.lstrip(" ,"))
    for name, read in (("spoken_clock", _spoken_clock), ("word_clock", _word_clock)):
        found = _rx(name).match(tail, lead)
        said = read(found) if found and (name == "spoken_clock" or _word_clock_ok(tail, found)) else None
        at = _hour_from(*said, evening) if said else None
        if at is not None:
            return at, found.end()
    return None


def _recurrence_cands(low: str) -> list[tuple]:
    out = []

    def add(start: int, end: int, rule: list[str], words: str) -> None:
        evening = "BYHOUR=18" in ";".join(rule) or "BYHOUR=20" in ";".join(rule)
        found = _clock_after(low, end, evening)
        if found is not None:
            at, used = found
            rule = [r for r in rule if not r.startswith(("BYHOUR", "BYMINUTE"))] + [f"BYHOUR={at.hour}", f"BYMINUTE={at.minute}"]
            end += used
            words += f" at {_clock_words(at)}"
        out.append((start, end, "recurrence", ";".join(rule), words, 0))

    for found in _rx("every").finditer(low):
        other, count, unit, monthday = found.groups()
        interval = 2 if other else (int(count) if count and count.isdigit() else _WORD_COUNTS.get(count or "", 1))
        rule, words = [], "every " + ("other " if other else f"{count} " if count else "")
        if unit in _WEEKDAYS:
            rule = ["FREQ=WEEKLY"] + ([f"INTERVAL={interval}"] if interval > 1 else []) + [f"BYDAY={_WEEKDAY_CODES[_WEEKDAYS[unit]]}"]
            words += _WEEKDAY_NAMES[_WEEKDAYS[unit]]
        elif unit in ("weekday", "weekend"):
            rule = ["FREQ=WEEKLY", "BYDAY=" + ("MO,TU,WE,TH,FR" if unit == "weekday" else "SA,SU")]
            words += unit
        elif unit in _PARTS:
            rule = ["FREQ=DAILY", f"BYHOUR={_PARTS[unit]}", "BYMINUTE=0"]
            words += unit
        else:
            freq = {"day": "DAILY", "week": "WEEKLY", "fortnight": "WEEKLY", "month": "MONTHLY", "year": "YEARLY"}[unit]
            interval *= 2 if unit == "fortnight" else 1
            rule = [f"FREQ={freq}"] + ([f"INTERVAL={interval}"] if interval > 1 else [])
            if monthday:
                rule.append(f"BYMONTHDAY={int(monthday)}")
            words += unit + ("s" if interval > 1 and not other else "")
        add(found.start(), found.end(), rule, words)
    #: "weekly review every friday": with an "every ..." said, "weekly" is
    #: the thing's name, not a second repeat (Brief 66's sweep).
    for found in () if out else _rx("adverb").finditer(low):
        freq = {"daily": "DAILY", "nightly": "DAILY", "weekly": "WEEKLY", "fortnightly": "WEEKLY", "monthly": "MONTHLY",
                "yearly": "YEARLY", "annually": "YEARLY"}[found.group(1)]
        rule = [f"FREQ={freq}"] + (["INTERVAL=2"] if found.group(1) == "fortnightly" else [])
        rule += ["BYHOUR=20", "BYMINUTE=0"] if found.group(1) == "nightly" else []
        add(found.start(), found.end(), rule, found.group(1))
    for found in _rx("plural_day").finditer(low):
        name = found.group(1)
        if name in ("weekdays", "weekends"):
            rule = ["FREQ=WEEKLY", "BYDAY=" + ("MO,TU,WE,TH,FR" if name == "weekdays" else "SA,SU")]
        else:
            rule = ["FREQ=WEEKLY", f"BYDAY={_WEEKDAY_CODES[_WEEKDAYS[name[:-1]]]}"]
        add(found.start(), found.end(), rule, "every " + name[:-1])
    _nth_weekday_cands(low, add)
    return out


_ORDINAL_N = {"first": 1, "1st": 1, "second": 2, "2nd": 2, "third": 3, "3rd": 3, "fourth": 4, "4th": 4, "last": -1}


def _nth_weekday_cands(low: str, add) -> None:  # noqa: ANN001
    """"The last friday of the month" as a monthly rule. "Last friday" alone
    is a day gone (a date's reading), so the month or an "every" must be said."""
    for found in _rx("nth_weekday").finditer(low):
        every, nth, name, month = found.groups()
        if not (every or month):
            continue
        weekday = _WEEKDAYS[name]
        n = _ORDINAL_N[nth]
        words = f"every {nth} {_WEEKDAY_NAMES[weekday]} of the month"
        add(found.start(), found.end(), ["FREQ=MONTHLY", f"BYDAY={n}{_WEEKDAY_CODES[weekday]}"], words)


def _alert_cands(low: str) -> list[tuple]:
    """An early alert, in minutes before the due time."""
    out = []
    for found in _rx("alert").finditer(low):
        count, unit = found.groups()
        n = 1 if count == "the" else int(count) if count.isdigit() else _WORD_COUNTS.get(count, 1)
        key = unit if unit in _UNIT_SECONDS else {"hrs": "hours", "hr": "hour"}.get(unit, unit)
        minutes = n * _UNIT_SECONDS[key] // 60
        if 0 < minutes <= 43200:
            out.append((found.start(), found.end(), "alert", minutes, "", 0))
    return out


def alert_words(minutes: int) -> str:
    """"1 day before", "30 minutes before": an early alert, said back."""
    for size, name in ((10080, "week"), (1440, "day"), (60, "hour"), (1, "minute")):
        if minutes % size == 0:
            n = minutes // size
            return f"{n} {name}{'' if n == 1 else 's'} before"
    return f"{minutes} minutes before"


def _duration_cands(low: str) -> list[tuple]:
    out = []
    for found in _rx("words_duration").finditer(low):
        said = found.group(0)
        if found.group(2):
            n = 1 if found.group(1) in ("a", "an", "one") else int(found.group(1))
            seconds = (n + 0.5) * (3600 if found.group(2) == "hour" else 60)
        elif said == "half an hour":
            seconds = 1800
        else:
            n = 0.5 if found.group(3) == "half an" else _WORD_COUNTS.get(found.group(3))
            before = low[:found.start()].split()
            if n is None or (found.group(3) in ("a", "an") and before and before[-1].lstrip("0123456789.,") in UNITS):
                continue  # "3 kWh a day" is a rate, not a day
            seconds = n * UNITS[found.group(4).rstrip("s") if found.group(4).rstrip("s") in UNITS else found.group(4)][1]
        out.append((found.start(), found.end(), "duration", timedelta(seconds=seconds), "", 0))
    out.extend((f.start(), f.end(), "duration", timedelta(hours=int(f.group(1)), minutes=int(f.group(2))), "", 0)
               for f in _rx("hm").finditer(low))
    return out


def _figure(raw: str) -> float:
    value = float(raw.replace(",", ""))
    return int(value) if value.is_integer() else value


def _duration_cand(start: int, end: int, seconds: float) -> list[tuple]:
    try:
        span = timedelta(seconds=seconds)
    except OverflowError:  # "last 99999999999999999999 days" is no span
        return []
    return [(start, end, "duration", span, "", 0)]


def _measure_cands(raw: str, low: str, locale: str | None) -> list[tuple]:
    out = []
    us = (locale or "").lower() in _FAHRENHEIT
    for found in _rx("money_pre").finditer(low):
        amount = _figure(found.group(2))
        scale = {"k": 1000, "m": 1_000_000, "bn": 1_000_000_000}.get((found.group(3) or "").strip(), 1)
        out.append((found.start(), found.end(), "money", (amount * scale, CURRENCY_NAMES[found.group(1)]), "", 0))
    out.extend((f.start(), f.end(), "money", (_figure(f.group(2)), CURRENCY_NAMES[f.group(1)]), "", 0)
               for f in _rx("money_code").finditer(low))
    for found in _rx("money_post").finditer(low):
        name = found.group(2)
        both = name in UNITS  # "5 pounds": money or weight, by where the person is
        out.append((found.start(), found.end(), "money", (_figure(found.group(1)), CURRENCY_NAMES[name]), "", 1 if both and us else 0))
    for found in _rx("quantity").finditer(low):
        name, glued = found.group(3), not found.group(2)
        written = raw[found.start(3):found.end(3)]
        if name in _NOT_IN_TEXT or (name in _GLUED_ONLY and not glued and written not in _SPACED_CAPITALS):
            continue
        dimension, _size, said = UNITS[name]
        amount = _figure(found.group(1))
        if dimension == "time":
            out += _duration_cand(found.start(), found.end(), amount * _size)
        elif dimension == "temperature":
            out.append((found.start(), found.end(), "temperature", (amount, said), "", 0))
        else:
            rank = (0 if us else 1) if name in CURRENCY_NAMES else 0
            out.append((found.start(), found.end(), "quantity", (amount, said, dimension), "", rank))
    for found in _rx("degrees").finditer(low):
        amount = _figure(found.group(1))
        if low[max(0, found.start() - 3):found.start()] == "at ":
            out.append((found.start(), found.end(), "quantity", (amount, "degrees", "angle"), "", 0))
        else:
            out.append((found.start(), found.end(), "temperature", (amount, "°F" if us else "°C"), "", 0))
    return out


def _contact_cands(raw: str, low: str) -> list[tuple]:
    out = []
    for found in _rx("email").finditer(low):
        text = found.group(0).rstrip(".")
        out.append((found.start(), found.start() + len(text), "email", raw[found.start():found.start() + len(text)], "", 0))
    for found in _rx("url").finditer(low):
        text = raw[found.start():found.end()].rstrip(".,;:!?")
        value = text if "://" in text else "https://" + text
        out.append((found.start(), found.start() + len(text), "url", value, "", 0))
    for found in _rx("phone").finditer(low):
        text = found.group(0)
        digits = re.sub(r"\D", "", text)
        lead = text[:1]
        if not 7 <= len(digits) <= 15 or not (lead in "+(0" or len(digits) >= 10):
            continue
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
            continue
        out.append((found.start(), found.end(), "phone", ("+" if lead == "+" else "") + digits, "", 0))
    out.extend((f.start(), f.end(), "tag", raw[f.start(1):f.end(1)].lower(), "", 0) for f in _rx("tag").finditer(low))
    out.extend((f.start(), f.end(), "person", raw[f.start(1):f.end(1)], "", 0) for f in _rx("at_person").finditer(low))
    for kind in ("person", "place"):
        for found in _rx(kind).finditer(raw):
            name = found.group(1)
            words = name.split(" ")
            while words and words[-1] in _NAME_STOP:
                words.pop()
            if not words or words[0] in _NAME_STOP:
                continue
            name = " ".join(words)
            end = found.start(1) + len(name)
            out.append((found.start(1), end, kind, name, "", 0))
            while kind == "person":
                more = re.match(r"(?:,| and| &|, and) ([A-Z][a-z]+)\b", raw[end:end + 40])
                if more is None or more.group(1) in _NAME_STOP:
                    break
                out.append((end + more.start(1), end + more.end(1), "person", more.group(1), "", 0))
                end += more.end()
    return out


def _number_cands(low: str) -> list[tuple]:
    out = [(f.start(), f.end(), "number", _figure(f.group(1)), "", 0) for f in _rx("number").finditer(low)]
    out.extend((f.start(), f.end(), "ordinal", int(f.group(1)), "", 0) for f in _rx("ordinal").finditer(low))
    out.extend((f.start(1), f.end(1), "ordinal", _ORDINAL_WORDS[f.group(1)], "", 0) for f in _rx("ordinal_word").finditer(low))
    return out


def _anchored_cands(low: str, now: datetime, cands: list[tuple]) -> list[tuple]:
    """"two hours before midnight": an offset from the time the next span reads."""
    out = []
    for found in _rx("anchored").finditer(low):
        amount = _NUMBERS.get(found.group(1)) or _WORD_COUNTS.get(found.group(1))
        if amount is None and found.group(1).isdigit():
            amount = int(found.group(1))
        nxt = [c for c in cands if c[0] == found.end() and c[2] in ("time", "datetime", "date") and c[5] == 0]
        if not amount or not nxt:
            continue
        base_c = max(nxt, key=lambda c: c[1])
        base = resolve(low[base_c[0]:base_c[1]], now)
        if base is None:
            continue
        unit = timedelta(hours=1) if found.group(2).startswith("h") else timedelta(minutes=1)
        out.append((found.start(), base_c[1], "datetime", base + unit * amount * (-1 if found.group(3) == "before" else 1), "", 0))
    return out


def _ends_of(cand: tuple) -> tuple[date, date] | None:
    """The first and last day a day or a whole month's span reads as."""
    value = cand[3]
    if cand[2] == "date" and isinstance(value, date):
        return value, value
    if cand[2] == "range" and isinstance(value[0], date) and isinstance(value[1], date):
        return value[0], value[1]
    return None


def _range_start(first: tuple, last_days: tuple[date, date]) -> date | None:
    """Where a range begins: the first end's own first day, or "1" in
    "between 1 and 5 October", the day of the month the second end names."""
    ends = _ends_of(first)
    if ends:
        return ends[0]
    if first[2] == "number" and 1 <= first[3] <= last_days[1].day:
        return last_days[1].replace(day=first[3])
    return None


def _first_end(low: str, at: int, points: dict) -> tuple | None:
    """The day or month starting at `at`, or a bare day number there."""
    if at in points:
        return points[at]
    number = re.match(r"\d{1,2}(?=\s)", low[at:])
    return (at, at + len(number.group(0)), "number", int(number.group(0)), "", 0) if number else None


def _date_range_cands(low: str, cands: list[tuple]) -> list[tuple]:
    """"from monday to friday", "between 1 and 5 October": the second end
    read on or after the first."""
    out = []
    points = {c[0]: c for c in cands if c[5] == 0 and c[2] in ("date", "range") and _ends_of(c)}
    for found in _rx("date_range").finditer(low):
        first = _first_end(low, found.end(), points)
        joint = re.match(r" (?:to|and|until|till|through) ", low[first[1]:first[1] + 10]) if first else None
        last = points.get(first[1] + len(joint.group(0))) if joint else None
        start = _range_start(first, _ends_of(last)) if last else None
        if start is None:
            continue
        end_day = _ends_of(last)[1]
        while end_day < start and last[2] == "date":
            end_day += timedelta(days=7)
        out.append((found.start(), last[1], "range", (start, end_day, "day"), "", 0))
    return out


_MONTH_TO_MONTH = re.compile(
    r"\b(?:from|between)\s+" + _MONTH_RE + r"\s+(?:to|and|until|till|through)\s+" + _MONTH_RE + r"\b"
)


def _month_range_cands(low: str, now: datetime, tense: str | None) -> list[tuple]:
    """"between March and May", "from June to August": whole months, the
    second read after the first."""
    out = []
    for found in _MONTH_TO_MONTH.finditer(low):
        first = _month_span(_MONTHS[found.group(1)], now.date(), tense or "past")
        last = _month_span(_MONTHS[found.group(2)], now.date(), tense or "past")
        if last[1] < first[0]:
            last = _month_span(_MONTHS[found.group(2)], now.date(), tense or "past", first[0].year + 1)
        out.append((found.start(), found.end(), "range", (first[0], last[1], "month"), "", 0))
    return out


def _read_as(kind: str, value: object, note: str) -> str:
    if kind == "date":
        words = _day_words(value)
    elif kind == "datetime":
        words = f"{_day_words(value.date())} at {_clock_words(value.time())}"
    elif kind == "time":
        words = _clock_words(value)
    elif kind == "range":
        first, last, grain = value
        if isinstance(first, time):
            words = f"{_clock_words(first)} to {_clock_words(last)}"
        else:
            words = f"{_day_words(first)} to {_day_words(last)}"
    elif kind == "duration":
        words = _duration_words(value.total_seconds())
    elif kind == "recurrence":
        words = note or value
        note = ""
    elif kind == "alert":
        words = "alert " + alert_words(value)
    elif kind == "money":
        words = f"{_num_words(value[0])} {value[1]}"
    elif kind in ("quantity", "temperature"):
        words = f"{_num_words(value[0])} {value[1]}"
    elif kind == "ordinal":
        words = f"number {value} in order"
    elif kind == "number":
        words = _num_words(value)
    else:
        words = f"{kind} {value}"
    return f"{words} ({note})" if note else words


_DAY_OF_MONTH = re.compile(r"(?:on )?(?:the )?(\d{1,2})(?:st|nd|rd|th)")


def day_of_month(span: Span) -> int | None:
    """The day a date span names when it named only a day of the month ("on
    the 1st"): a monthly repeat is worth offering for it."""
    found = _DAY_OF_MONTH.fullmatch(span.text.lower().strip()) if span.kind == "date" else None
    return int(found.group(1)) if found else None


_YEAR_WORDS = ("last year", "this year", "next year")
_PERIOD_LEADS = frozenset({"early", "mid", "late", "end"})


def _is_class_phrase(said: str) -> bool:
    """Whether a phrase `find` read is one the plain date readers get wrong:
    anything after since/before/until/till/after, or a year word on a month,
    season, part of one or range ("20 March last year", "summer last year",
    "early next year"), never a bare "last year" or "the last year"."""
    words = said.split(" ")
    if words[0] in ("since", "before", "until", "till", "after"):
        return True
    if not said.endswith(_YEAR_WORDS) or len(words) < 3:
        return False
    return any(w in _MONTHS or w in _SEASON_START or w in _PERIOD_LEADS or w in ("half", "week") for w in words)


def _dated_class_cands(low: str, now: datetime, asked_past: bool) -> list[tuple]:
    """The phrases of the date-phrase class, read as `span` reads them (a
    question about the past only: a reminder's "before March" is no day).
    A candidate as long as the phrase beats the pieces the other readers
    would take from it ("from March", "20th", "last year")."""
    if not asked_past:
        return []
    out = []
    for start, end, phrase in find(low):
        if not _is_class_phrase(phrase.lower()):
            continue
        got = span(phrase, now.date(), "past")
        if got is None:
            continue
        first, last, grain = got
        out.append((start, end, "date", first, "", 0) if first == last else (start, end, "range", (first, last, grain), "", 0))
    return out


def class_window(text: str, today: date) -> tuple[date, date, str, int, int] | None:
    """(since, until, phrase, start, end) for the first phrase of the
    date-phrase class a search question holds ("notes from March 20th last
    year", "since last spring", "before the summer of 2025"), read before the
    stretch-ending-now rules, which would take its "last year" alone."""
    low = _lower(text or "")
    found = find(low)
    if not found or not _is_class_phrase(found[0][2].lower()):
        return None
    start, end, phrase = found[0]
    got = span(phrase, today, "past")
    return None if got is None else (got[0], got[1], phrase, start, end)


def recognise(
    text: str, *, now: datetime, locale: str | None = None, tense: str | None = None, known: dict | None = None,
    bare_hours: bool = False,
) -> list[Span]:
    """Every span `text` reads as, left to right (`_recognise`). `locale`
    orders a numeric date, picks the temperature scale and the hemisphere a
    season is read in; none means day first, Celsius and the reported locale."""
    with _in_locale(locale):
        return _recognise(text, now=now, locale=locale, tense=tense, known=known, bare_hours=bare_hours)


def _recognise(
    text: str, *, now: datetime, locale: str | None = None, tense: str | None = None, known: dict | None = None,
    bare_hours: bool = False,
) -> list[Span]:
    """Every span `text` reads as, left to right; the readings of one
    phrase share its offsets, ranked. `tense` ("past", "future") overrides
    the one read from the sentence's verbs; with neither, a day is the next
    one and a month alone the last one ("what did I write in March").
    `known` maps phrases the caller knows to their day ({"my birthday":
    date(...)}): a stored date is read, never guessed. `bare_hours` reads
    a bare number after a day as its hour ("friday 9 dentist"), for a
    reminder's own words only."""
    raw = str(text or "")
    if not raw.strip():
        return []
    low = _lower(raw)
    tense_given = tense
    tense = tense or tense_of(low)
    cands = _date_cands(raw, low, now, locale, tense, bare_hours)
    cands += _time_cands(low)
    cands += _dated_class_cands(low, now, tense_given == "past")
    cands += _anchored_cands(low, now, cands) + _date_range_cands(low, cands) + _month_range_cands(low, now, tense)
    cands += _relative_cands(low, now, tense) + _recurrence_cands(low) + _alert_cands(low)
    cands += _duration_cands(low) + _measure_cands(raw, low, locale)
    cands += _contact_cands(raw, low) + _number_cands(low)
    for phrase, day in (known or {}).items():
        for found in re.finditer(r"(?<!\w)" + re.escape(str(phrase).lower()) + r"(?!\w)", low):
            cands.append((found.start(), found.end(), "date", day, "", 0))
    cands.sort(key=lambda c: (-(c[1] - c[0]), c[5], _PRIORITY_OF[c[2]], c[0]))
    taken: list[tuple] = []
    alts: list[tuple] = []
    for cand in cands:
        start, end = cand[0], cand[1]
        clash = [t for t in taken if start < t[1] and t[0] < end]
        if not clash:
            if cand[5] == 0:
                taken.append(cand)
            continue
        same = clash[0]
        if len(clash) == 1 and (same[0], same[1]) == (start, end) and cand[5] > 0 and (cand[2], cand[3]) != (same[2], same[3]):
            alts.append(cand)
    spans = [
        Span(c[2], raw[c[0]:c[1]], c[0], c[1], c[3], _read_as(c[2], c[3], c[4]), c[5]) for c in taken + alts
    ]
    return sorted(spans, key=lambda s: (s.start, s.rank))


#: A day named in a dated note is that week's, not this one's (the owner,
#: 2026-10-26: "it was due that friday, not this friday").
_DAY_SHIFT = (
    (re.compile(r"\b(?:on |this )?(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b"), r"that \1"),
    (re.compile(r"\btonight\b"), "that night"), (re.compile(r"\btoday\b"), "that day"),
    (re.compile(r"\btomorrow\b"), "the next day"), (re.compile(r"\bnext week\b"), "the week after"),
    (re.compile(r"\bis due\b"), "was due"),
)


def as_of_then(text: str) -> str:
    """`text`, a dated note's words, with its days said as of that note's
    day ("due on Friday" to "due that Friday", "tonight" to "that night")."""
    for pattern, repl in _DAY_SHIFT:
        text = pattern.sub(repl, text)
    return text


#: Money and scores, for an answer that sums amounts or finds a word a note
#: says by its shape ("money" by "$40", "rate" by "8/10"; 2026-10-30 sweep).
_AMOUNT = re.compile(r"([$£€¥])\s?(\d[\d,]*(?:\.\d{1,2})?)(k\b)?")
_MONEY = re.compile(r"[$£€¥]\s?\d|\b\d[\d,.]*\s?(?:dollars|pounds|euros|quid|bucks|usd|gbp|eur)\b", re.I)
_SCORE = re.compile(r"\b\d+(?:\.\d+)?\s?(?:/\s?(?:5|10|20|100)\b|out of \d+|stars?\b)", re.I)


def says_shape(shape: str, text: str) -> bool:
    """Whether `text` holds a "money" amount or a "score" ("8/10", "4 stars")."""
    pattern = {"money": _MONEY, "score": _SCORE}.get(shape)
    return bool(pattern and pattern.search(text or ""))


class Measure(tuple):
    """(dimension, value, unit, offset), and `end` (where the figure and its
    unit stop), so a caller can read the words after it."""

    end: int

    @property
    def at(self) -> int:
        return self[3]

    def __new__(cls, dimension: str, value: float, unit: str, at: int, end: int) -> "Measure":
        made = super().__new__(cls, (dimension, value, unit, at))
        made.end = end
        return made


def measures(text: str) -> list[Measure]:
    """Each measured amount, temperature aside: (dimension, value in the
    dimension's base unit, the unit as written, offset). "5 km" and "800 m"
    add up because both are metres here (CHAT_PLAN, placed 2026-10-30).
    Money is a dimension too ("money"), its base unit the currency, so "$86"
    is (money, 86.0, "$", offset) and "$1.5k" is 1500."""
    raw = text or ""
    found = []
    for m in _AMOUNT.finditer(raw):
        found.append(Measure("money", float(m.group(2).replace(",", "")) * (1000 if m.group(3) else 1), m.group(1), m.start(), m.end()))
    for m in _rx("quantity").finditer(raw.lower()):
        name, glued, written = m.group(3), not m.group(2), raw[m.start(3):m.end(3)]
        if name in _NOT_IN_TEXT or name in CURRENCY_NAMES or (name in _GLUED_ONLY and not glued and written not in _SPACED_CAPITALS):
            continue
        dimension, size, _said = UNITS[name]
        if dimension != "temperature" and raw[m.start() - 1:m.start()] not in ("$", "£", "€", "¥"):
            found.append(Measure(dimension, _figure(m.group(1)) * size, name, m.start(), m.end()))
    return sorted(found, key=lambda x: x[3])
