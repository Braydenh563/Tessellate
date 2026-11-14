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

The month and weekday tables and the span-of-days reading (`span`, `find`,
`window`) live in `ai/recognise_windows.py` (audit-1028 K24) and are imported
back here, so `recognise.span` and the rest keep working.

No network and no app imports (decision 56; `tests/test_recognise.py` checks
the imports): currency rates stay in `utilities` with their date. The rule
`tests/test_one_reader.py` holds: no other file compiles a date-word or unit
pattern, except `entry/timewords.py`, which reads a saved note's own words.
"""

from __future__ import annotations

import re

from tessellate.core.lazyre import lazy_compile
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from tessellate.ai.recognise_units import GLUED_ONLY, NOT_IN_TEXT, SPACED_CAPITALS, CURRENCY_NAMES, UNITS
from tessellate.ai.recognise_windows import (
    _ANCHORED,
    _CALL_LOCALE,
    _CLOCK,
    _COMPUTED,
    _DATE_ORDER,
    _DAY_MONTH,
    _HEMISPHERE,
    _ISO_DATE,
    _MONTHS,
    _MONTH_DAY,
    _MONTH_RE,
    _NTH_IN_MONTH,
    _NUMBERS,
    _ORDINAL_N,
    _PARTS,
    _SEASON_START,
    _WEEKDAY,
    _WEEKDAYS,
    _WEEKDAY_CODES,
    _YEAR_AFTER_MONTH,
    _amount,
    _in_locale,
    _month_end,
    _month_span,
    _nearest,
    _nth_in_month,
    _shift_months,
    find,
    span,
)

#: Names other modules read from here; they live in `recognise_windows` now.
from tessellate.ai.recognise_windows import (
    AHEAD_DAY_WORDS,
    LATELY_DAYS,
    MONTH_NAMES,
    PHRASE_FILLER,
    SPAN_MINUTES,
    WEEKDAY_NAMES,
    WEEKDAY_WORD,
    a_topic_phrase,
    adverbial,
    ahead_window,
    configure_date_order,
    configure_hemisphere,
    count_of,
    hemisphere_of,
    looks_dated,
    mid_sentence,
    names_a_day,
    note_locale,
    proper_days,
    says_a_recent_day,
    window,
    without_ahead_words,
    without_windows,
)

#: Re-exported for callers that read these as `recognise.NAME`.
__all__ = [
    "AHEAD_DAY_WORDS",
    "LATELY_DAYS",
    "MONTH_NAMES",
    "PHRASE_FILLER",
    "SPAN_MINUTES",
    "WEEKDAY_NAMES",
    "WEEKDAY_WORD",
    "YEAR_SHIFT",
    "a_topic_phrase",
    "adverbial",
    "ahead_window",
    "configure_date_order",
    "configure_hemisphere",
    "count_of",
    "hemisphere_of",
    "looks_dated",
    "mid_sentence",
    "names_a_day",
    "note_locale",
    "proper_days",
    "says_a_recent_day",
    "window",
    "without_ahead_words",
    "without_windows",
]

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
_IN_PATTERN = lazy_compile(
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
_IN_HOURS_MINUTES = lazy_compile(_IN_HOURS_MINUTES_SRC, re.IGNORECASE)
_IN_MONTHS = lazy_compile(rf"\bin\s+(\d{{1,2}}|{_COUNT_WORDS})\s+(months?|years?)\b", re.IGNORECASE)


_FROM_NOW = lazy_compile(
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


def asks_computed(question: str) -> bool:
    return bool(_COMPUTED.search(question))


#: A question about time (INBOX 1441): only then does an answer say a date.
_ASKS_TIME = lazy_compile(
    r"\b(?:when|what time|dates?|dated|days?|weeks?|weekend|months?|years?|yesterday|today|tonight|tomorrow|"
    r"recent(?:ly)?|latest|newest|oldest|earliest|last|first|since|ago|before|after|until|timeline|history|"
    r"how long|how often|going|progress\w*|improv\w*|chang\w*|monday|tuesday|wednesday|thursday|friday|saturday|sunday|january|february|march|"
    r"april|may|june|july|august|september|october|november|december|\d{1,2}(?:st|nd|rd|th)?)\b", re.I)


def asks_time(question: str) -> bool:
    """Whether a question's words are about time: a when, a day, a week or
    a month, a change over time (composer.asks_time adds "when did I write")."""
    return bool(_ASKS_TIME.search(question))


#: "What is tomorrow's date", "what is the date yesterday", and the CLINC150
#: phrasings ("what will the date be tomorrow", "tomorrow, what will the date
#: be", "day is it gonna be tomorrow"): which neighbouring day is asked about.
_NEIGHBOUR_DAY = lazy_compile(
    r"^(?:(?:what|when) (?:is|was) )?(?:the )?(?P<d>tomorrow|yesterday)(?:'s|s)? date$|^what (?:is|was) the date (?P<e>tomorrow|yesterday)$"
    r"|^(?:what(?:'s| is| will| would)?\s+)?(?:the\s+)?(?:date\s+(?:will\s+)?(?:be\s+)?(?:for\s+)?(?P<f>tomorrow|yesterday)|(?P<g>tomorrow|yesterday)'?s?\s+date"
    r"|(?:(?:what\s+)?(?:will\s+)?the\s+)?date\s+(?:will\s+)?be\s+(?P<h>tomorrow|yesterday)|(?P<i>tomorrow|yesterday),?\s+what\s+(?:will\s+)?the\s+date\s+(?:be|was)"
    r"|day\s+(?:is\s+it\s+)?(?:gonna\s+be\s+)?(?P<j>tomorrow|yesterday))$",
    re.I,
)


def neighbour_day(question: str) -> str | None:
    """"tomorrow" or "yesterday" when the whole question asks for that day's date."""
    found = _NEIGHBOUR_DAY.match(question)
    return next(word for word in found.groups() if word).lower() if found else None


#: Whole-year words and how far each is from this year.
YEAR_SHIFT = {"it": 0, "this year": 0, "next year": 1, "last year": -1}
_LEAP_QUESTION = lazy_compile(r"^(?:is|was|will) (?P<y>\d{4}|it|this year|next year|last year)(?: be)? a leap year$")


def leap_year_asked(question: str) -> str | None:
    """The year a leap-year question names: four digits, or a key of YEAR_SHIFT."""
    found = _LEAP_QUESTION.match(question)
    return found["y"] if found else None


_WD_WORD = "|".join(sorted(_WEEKDAYS, key=len, reverse=True))
_MO_WORD = "|".join(sorted(_MONTHS, key=len, reverse=True))
_WD_PREFIX = rf"(?:\b({_WD_WORD})\.?,?\s+)?"
_YEAR_SUFFIX = r"(?:,?\s+((?:19|20)\d\d)\b)?"
_MENTION_DM = lazy_compile(rf"{_WD_PREFIX}\b(\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?({_MO_WORD})\b{_YEAR_SUFFIX}")
_MENTION_MD = lazy_compile(rf"{_WD_PREFIX}\b({_MO_WORD})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?\b(?![\d:])(?!\s*(?:am|pm)\b){_YEAR_SUFFIX}")
_MENTION_ISO = lazy_compile(rf"{_WD_PREFIX}\b(\d{{4}})-(\d\d)-(\d\d)(?=\b|t\d)")
#: "Thursday 29": a weekday and a day number, no month, not a clock time
#: or a count ("friday 2 notes").
_MENTION_WD_DAY = lazy_compile(
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
_ISO_STAMP = lazy_compile(r"(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2})(?::(\d{2}))?)?")


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


_FROM_DAY = lazy_compile(
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


_SCHEDULE_DAY = lazy_compile(r"\b(?:mon|tues|wednes|thurs|fri|satur|sun)day", re.I)
_SCHEDULE_EVERY = lazy_compile(r"\bevery (?:other )?(?:week|day|month|(?:mon|tues|wednes|thurs|fri|satur|sun)day)|\b(?:mon|tues|wednes|thurs|fri|satur|sun)days\b", re.I)


def recurring_schedule(sentence: str) -> bool:
    """Whether a sentence is a habit, not a day that falls due: "Gym on Monday, Wednesday and Friday at 7am",
    "every Tuesday", "Mondays" (bt-compcomp-1109 item 8). Only a bounded slice is read."""
    text = (sentence or "")[:2000]
    return len(_SCHEDULE_DAY.findall(text)) > 1 or bool(_SCHEDULE_EVERY.search(text))


# --- the part of the day a note was about ------------------------------------------

#: A "now" scope on the end of an ask ("what is most important today"), as regex source for the composer's
#: plan asks (composer_plan `_PLAN`), so the day words stay in this file (tests/test_one_reader.py).
_NOW_SCOPE = r"right now|now|today|at the moment|at present|this morning|this afternoon|tonight"
_NOW_SCOPE_SHORT = r"right now|now|today"


def now_scope(short: bool = False) -> str:
    """The "now" scope words as regex source (`short`: only "right now", "now", "today")."""
    return _NOW_SCOPE_SHORT if short else _NOW_SCOPE
_EVENING_SAID = lazy_compile(r"\b(?:after work|in the evening|this evening|tonight|after dinner)\b", re.IGNORECASE)
_MORNING_SAID = lazy_compile(r"\b(?:before work|in the morning|this morning|early morning|at dawn)\b", re.IGNORECASE)


def part_of_day(text: str) -> str | None:
    """"evening" when a text says it was after work or in the evening (the
    insights' "after work" count reads this), "morning" when it says the
    morning and not the evening, else None."""
    if _EVENING_SAID.search(text or ""):
        return "evening"
    return "morning" if _MORNING_SAID.search(text or "") else None


# --- the recogniser: every span a text reads as ----------------------------------------

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


_PAST_CUE = lazy_compile(r"\b(?:did|was|were|wrote|written|had|went|met|saw|ran|made|said|happened|spent|paid|bought|"
                       r"finished|started|ago|earlier|previously|used to)\b")
_FUTURE_CUE = lazy_compile(r"\b(?:will|remind|due|until|till|going to|need to|have to|should|plan to|book|schedule|"
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


def _reads_month_first(locale: str | None) -> bool:
    """A reader that takes no locale (a plan's window, a day list) follows the one the request reported
    (`note_locale`): Chat and Ask carry it, so "3/4" is 4 March in en-US wherever it is read (W8 B18)."""
    if _DATE_ORDER["setting"] != "auto":
        return _DATE_ORDER["setting"] == "month"
    return (locale or _CALL_LOCALE.get() or _HEMISPHERE["reported"] or "").lower() in _MONTH_FIRST


def _numeric_readings(a: int, b: int, year: int | None, month_first: bool, today: date, tense: str | None) -> list:
    """The dates "a/b" can be, the locale's order first; a pair that is no date drops out."""
    readings: list = []
    day_first, other = (b, a, "day first"), (a, b, "month first")
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
    return readings


def _numeric_dates(low: str, today: date, locale: str | None, tense: str | None) -> list[tuple[int, int, list]]:
    """"2/11", "25/12/2026", "3.11.2026": (start, end, [(day, read_as), ...])
    with the locale's reading first and the other second when both are
    dates. "1/2 cup" is a fraction, not a date."""
    month_first = _reads_month_first(locale)
    out = []
    for found in _rx("numeric").finditer(low):
        a, b, year_s = (found.group(1), found.group(2), found.group(3)) if found.group(1) else (found.group(4), found.group(5), found.group(6))
        after = low[found.end():found.end() + 12].lstrip()
        if not year_s and after and re.match(_unit_names(), after) and after.split(" ")[0].strip(".,") in UNITS:
            continue
        year = None if not year_s else int(year_s) + (2000 if len(year_s) == 2 else 0)
        readings = _numeric_readings(int(a), int(b), year, month_first, today, tense)
        if readings:
            out.append((found.start(), found.end(), readings))
    return out


_DAY_PREP = lazy_compile(r"\b(?:on|for|by|before|after|since|until|till|from|at|around|about|during|between|and|to)\s+$", re.I)


_ASKING = lazy_compile(r"\W*(?:what|when|which|who|how|do|does|did|is|are|was|were|have|has|any|anything|show|list|tell)\b", re.I)
_WAS_ASKED = lazy_compile(r"\b(?:did|was|were|wrote|written|made|happened|had|done|went)\b", re.I)


def spell_asked_days(question: str, today: date, locale: str | None, plain: bool = True) -> str:
    """`spell_numeric_days` for a message that is a question only: a note or a command keeps the person's own
    characters (`plain` is False for a skill's text)."""
    if not plain or not _ASKING.match(question):
        return question
    return spell_numeric_days(question, today, locale, "past" if _WAS_ASKED.search(question) else "future")


def spell_numeric_days(text: str, today: date, locale: str | None, tense: str | None = None) -> str:
    """"what's due on 3/4" as "what's due on 4 March" (en-US) or "3 April" (elsewhere): a bare day and month
    is ordered once, by the locale the request carried, before any reader sees it, so Chat and Ask read it the
    same way everywhere (W8 B18). A fraction ("1/2 cup") and a figure that is no date are left as typed."""
    if "/" not in text and "." not in text and "-" not in text:
        return text
    low = text.lower()
    out, last = [], 0
    for start, end, readings in _numeric_dates(low, today, locale, tense):
        #: Only after a word that puts a day there ("on 3/4", "by 12/11"): "what is 1/2 of 10" is a fraction.
        if not _DAY_PREP.search(low[:start]):
            continue
        day = readings[0][0]
        said = f"{day.day} {day:%B}" + (f" {day.year}" if day.year != today.year else "")
        out += [text[last:start], said]
        last = end
    return "".join([*out, text[last:]]) if out else text


_MONTH_ONLY = lazy_compile(r"(?:in |during )?" + _MONTH_RE + _YEAR_AFTER_MONTH)
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
    if after[:1] in ("%", "°") or (word in UNITS and word not in GLUED_ONLY):
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
        if name in NOT_IN_TEXT or (name in GLUED_ONLY and not glued and written not in SPACED_CAPITALS):
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


_MONTH_TO_MONTH = lazy_compile(
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


_DAY_OF_MONTH = lazy_compile(r"(?:on )?(?:the )?(\d{1,2})(?:st|nd|rd|th)")


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


def _settle_overlaps(cands: list[tuple]) -> tuple[list[tuple], list[tuple]]:
    """Candidates longest first: those that clash with none taken are kept (a rank-0 reading), and a ranked reading of a taken phrase's exact span is an alternative."""
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
    return taken, alts


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
    taken, alts = _settle_overlaps(cands)
    spans = [
        Span(c[2], raw[c[0]:c[1]], c[0], c[1], c[3], _read_as(c[2], c[3], c[4]), c[5]) for c in taken + alts
    ]
    return sorted(spans, key=lambda s: (s.start, s.rank))


#: A day named in a dated note is that week's, not this one's (the owner,
#: 2026-10-26: "it was due that friday, not this friday").
_DAY_SHIFT = (
    (lazy_compile(r"\b(?:on |this )?(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b"), r"that \1"),
    (lazy_compile(r"\btonight\b"), "that night"), (lazy_compile(r"\btoday\b"), "that day"),
    (lazy_compile(r"\btomorrow\b"), "the next day"), (lazy_compile(r"\bnext week\b"), "the week after"),
    (lazy_compile(r"\bis due\b"), "was due"),
)


def as_of_then(text: str) -> str:
    """`text`, a dated note's words, with its days said as of that note's
    day ("due on Friday" to "due that Friday", "tonight" to "that night")."""
    for pattern, repl in _DAY_SHIFT:
        text = pattern.sub(repl, text)
    return text


#: Money and scores, for an answer that sums amounts or finds a word a note
#: says by its shape ("money" by "$40", "rate" by "8/10"; 2026-10-30 sweep).
_AMOUNT = lazy_compile(r"([$£€¥])\s?(\d[\d,]*(?:\.\d{1,2})?)(k\b)?")
_MONEY = lazy_compile(r"[$£€¥]\s?\d|\b\d[\d,.]*\s?(?:dollars|pounds|euros|quid|bucks|usd|gbp|eur)\b", re.I)
_SCORE = lazy_compile(r"\b\d+(?:\.\d+)?\s?(?:/\s?(?:5|10|20|100)\b|out of \d+|stars?\b)", re.I)


_DEGREES = lazy_compile(r"\b\d+(?:\.\d+)?\s?(?:°\s?[CF]?|degrees|deg)\b|\b\d+(?:\.\d+)?\s?[CF]\b", re.I)


def says_shape(shape: str, text: str) -> bool:
    """Whether `text` holds a "money" amount, a "score" ("8/10", "4 stars"), a "temperature" ("175C") or a "schedule" (a recurring habit)."""
    if shape == "schedule":
        return recurring_schedule(text)  # "Gym on Monday, Wednesday and Friday at 7am" is a schedule (bt-compcomp-1109 item 11)
    pattern = {"money": _MONEY, "score": _SCORE, "temperature": _DEGREES}.get(shape)
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
    found = [Measure("money", float(m.group(2).replace(",", "")) * (1000 if m.group(3) else 1), m.group(1), m.start(), m.end()) for m in _AMOUNT.finditer(raw)]
    for m in _rx("quantity").finditer(raw.lower()):
        name, glued, written = m.group(3), not m.group(2), raw[m.start(3):m.end(3)]
        if name in NOT_IN_TEXT or name in CURRENCY_NAMES or (name in GLUED_ONLY and not glued and written not in SPACED_CAPITALS):
            continue
        dimension, size, _said = UNITS[name]
        if dimension != "temperature" and raw[m.start() - 1:m.start()] not in ("$", "£", "€", "¥"):
            found.append(Measure(dimension, _figure(m.group(1)) * size, name, m.start(), m.end()))
    return sorted(found, key=lambda x: x[3])


# --- readers lent to the act modules (decision 46: one reader of date words and units) ---

#: "an hour", "half an hour", "30 mins", "2 days": an amount of time before
#: something (anchor_acts' "remind me an hour before the dentist").
_AMOUNT_BEFORE = r"(?P<n>an?|one|half an?|\d+(?:\.\d+)?)\s*(?P<unit>hours?|hrs?|h|minutes?|mins?|m|days?)"


def amount_before() -> str:
    """The source of `_AMOUNT_BEFORE`, for a pattern built around it (groups `n` and `unit`)."""
    return _AMOUNT_BEFORE


def amount_minutes(amount: str, unit: str) -> int:
    """The minutes `_AMOUNT_BEFORE`'s two groups say ("half an", "hour": 30)."""
    word = amount.lower()
    n = 0.5 if word.startswith("half") else 1.0 if word in ("a", "an", "one") else float(word)
    per = 1440 if unit.lower().startswith("d") else 60 if unit.lower().startswith("h") else 1
    return round(n * per)


_NAMES_A_TIME = lazy_compile(r"\b(?:week|day|today|tomorrow|weekend|month|morning|afternoon|evening|tonight|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", re.I)


def names_a_time(text: str) -> bool:
    """True when `text` names a day, a part of one, a week or a month."""
    return bool(_NAMES_A_TIME.search(text or ""))
