"""The question readers over the recogniser: a window in the past, a stretch ending now, date questions, the event window (audit K24, BK11).

Moved whole out of `ai/recognise.py`. It sits above the recogniser (it reads a
question with `recognise.recognise` and `recognise.resolve`), so `recognise`
never imports it. `recognise.recurring_schedule` stayed in the base because the
recogniser itself reads it.
"""

from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta

from tessellate.ai.recognise import recognise, resolve
from tessellate.ai.recognise_windows import (
    _DAY_MONTH,
    _ISO_DATE,
    _LATELY,
    _MONTH_DAY,
    _MONTHS,
    _NUMBERS,
    _WEEKDAYS,
    _amount,
)
from tessellate.core.lazyre import lazy_compile

# --- a window in the past (AGENT_SKILLS_REFORM, the audit of computed arguments) ---
#
# `resolve` reads a time to come. The list tools' `since` asks the other way,
# "notes from this week", and used to take only a number of days or an ISO
# date, so a model asked about "this week" had to work out which date that
# was: the arithmetic the 2026-09-21 decision took away from it everywhere.

_SPAN = lazy_compile(
    r"^(?:the\s+)?(?:last|past|previous)\s+(?:(\d{1,3}|[a-z-]+)\s+)?(days?|weeks?|months?|years?)$"
)
_AGO = lazy_compile(r"^(\d{1,3}|[a-z-]+)\s+(days?|weeks?|months?|years?)\s+ago$")


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
        #: Monday of the week before (Q24: "last week" is Monday to Sunday everywhere; "past week" rolls).
        "last week": today.weekday() + 7,
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
    #: The first or last seven days of a month ("the start of the month", "the end of last month").
    (r"\b(?:at\s+)?the\s+(?:start|beginning)\s+of\s+(?:the|this)\s+month\b", "month_start"),
    (r"\b(?:at\s+)?the\s+end\s+of\s+last\s+month\b", "last_month_end"),
    #: "last week" is the week before this one, Monday to Sunday, as everywhere else (the owner's Q24); "past week" rolls.
    (r"(?:in|over|during)?\s*(?:the\s+)?last\s+week\b(?!\s+of\b)", "last_week"),
    (r"(?:in|over|during)?\s*(?:the\s+)?past\s+(week)\b", "back"),
    (r"(?:in|over|during)?\s*(?:the\s+)?(?:last|past)\s+(month)\b", "back"),
    (r"(?:in|over|during)?\s*(?:the\s+)?(?:last|past)\s+(year)\b", "back"),
    (r"\btoday\b", "today"),
    (r"(?<!before )\byesterday\b", "yesterday"),
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
    if kind == "last_week":
        monday = today - timedelta(days=today.weekday() + 7)
        return monday, monday + timedelta(days=6)
    if kind == "this_month":
        return today.replace(day=1), today
    if kind == "month_start":
        first = today.replace(day=1)
        return first, first + timedelta(days=6)
    if kind == "last_month_end":
        last = today.replace(day=1) - timedelta(days=1)
        return last - timedelta(days=6), last
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


_AHEAD = lazy_compile(r"\b(?:next (?:week|month|year|fortnight)|coming fortnight)\b|\btomorrow\b", re.IGNORECASE)


def says_ahead(text: str) -> bool:
    """True when a sentence points to time to come ("next week", "tomorrow"):
    the fact graph's cue for a plan rather than a record."""
    return bool(_AHEAD.search(text or ""))


#: A question about the change or the past ("what did I use to...", "a year
#: ago"): `supersede.current` keeps every note for one. Read here, with the
#: other date words (decision 46).
_PAST = lazy_compile(
    r"\b(?:changed?|changes|used to|before|previous(?:ly)?|last (?:semester|term|year|time)|old|older|history|over time|"
    r"compare|comparison|difference|ago|in the past|originally|first)\b",
    re.I,
)


#: A question about how something has gone is about the run of notes, not the
#: latest one: "how's the gym going" reads 80 kg and then 90 kg (INBOX 812).
_PROGRESS = lazy_compile(
    r"\bprogress\b|\bhow(?:'s|s| is| are| has| have|'ve)\b[^?.!]{0,40}?\b(?:going|been|coming along|progressing)\b",
    re.I,
)


def says_past(text: str) -> bool:
    return bool(_PAST.search(text or "") or _PROGRESS.search(text or ""))


#: Day and month names that are always names. "march" and "may" are left out:
#: they are as often a verb as a date.
_CAPITAL_NAMES = lazy_compile(
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
_DAYS_UNTIL = lazy_compile(_HOW_MANY + r"\s*(?:is it |are there |left )?(?:until|till|til|to|before)\s+(?P<what>.+)$", re.I)
_DAYS_SINCE = lazy_compile(_HOW_MANY + r"\s*(?:has it been |is it |ago was |have passed |)?(?:since)\s+(?P<what>.+)$", re.I)
_N_UNIT = r"(\d{1,3}|a|an|one|two|three|four|five|six|seven|eight|nine|ten)\s+(days?|weeks?|months?|years?)"
#: "what date is it in 3 weeks" and "what is the date in 10 days" (the prefix, the suffix optional), or the bare
#: "10 days from today" (no prefix, so the suffix is required); a real model run found both read as other questions.
_DATE_FROM_NOW = lazy_compile(
    r"^(?:what (?:(?:day|date)(?: of the week)? (?:is|will it be|was|is it (?:gonna|going to) be)\s+(?:it\s+)?|(?:is|was) the (?:day|date)\s+)(?:in\s+)?" + _N_UNIT
    + r"(?:\s+(from now|from today|ago))?|" + _N_UNIT + r"\s+(from now|from today|ago))$",
    re.I,
)


#: What may follow a bare "how long to": a name for a day or event, never a doing.
_EVENT_START = lazy_compile(r"^(?:the|my|our|his|her|their|your|this|next|\d|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b|(?:mon|tues?|wed(?:nes)?|thu(?:rs?)?|fri|sat(?:ur)?|sun)(?:day)?\b)", re.I)


_HOW_LONG_TO = lazy_compile(r"\bhow long to\s+(?P<what>.+?)\W*$", re.I)


def is_duration_of_doing(text: str) -> bool:
    """"how long to prove sourdough" asks a duration: a bare "to" with a several-word
    object that does not open like a day or an event (INBOX 1739 row)."""
    found = _HOW_LONG_TO.search(text)
    return bool(found) and " " in found.group("what") and not _EVENT_START.match(found.group("what"))


def days_question(text: str) -> tuple[str, str] | None:
    """("future", what) for "how many days until what", ("past", what) for
    "how long since what", else None."""
    for pattern, tense in ((_DAYS_UNTIL, "future"), (_DAYS_SINCE, "past")):
        found = pattern.match(text)
        if found and not is_duration_of_doing(text):
            return tense, found.group("what")
    return None


def offset_question(text: str) -> tuple[str, str, bool] | None:
    """(amount, unit, ago) for "what date is it in 3 weeks" or "what day was
    it 10 days ago", else None."""
    found = _DATE_FROM_NOW.match(text)
    if not found:
        return None
    amount, unit, tail = (found.group(1), found.group(2), found.group(3)) if found.group(1) else (found.group(4), found.group(5), found.group(6))
    return amount, unit, not (tail or "from").startswith("from")

#: Any sentence that may carry a day, wider than `looks_dated`: abbreviated
#: months and weekdays, "21st", "3/11", "due". A cheap test before the
#: recogniser runs on it (notes are read by the hundred).
_DATED_WIDE = lazy_compile(
    r"\b(?:today|tomorrow|tonight|yesterday|next (?:week|month|year|[a-z]+day)|this (?:week|month|weekend)|weekend|"
    r"(?:mon|tues?|wed(?:nes)?|thu(?:rs?)?|fri|sat(?:ur)?|sun)(?:day)?|\d{1,2}(?:st|nd|rd|th)\b(?: of)?(?: (?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*)?|"
    r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.? \d{1,2}|\d{1,2} (?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*|"
    r"\d{1,2}[/.-]\d{1,2}(?:[/.-]\d{2,4})?|\d{4}-\d{2}-\d{2}|by (?:the )?end of|before (?:we|i) (?:go|leave)|deadline|due)\b", re.I)


#: A verb that says a thing happened: an irregular past, or a regular one.
_PAST_VERB = lazy_compile(
    r"\b(?:was|were|had|did|went|slept|ate|felt|saw|met|ran|got|came|left|took|made|spent|lost|won|"
    r"[a-z]{3,}ed)\b", re.I)
#: Words that set a thing up for later, so the day they name is ahead:
#: "booked for", "moved to", "due", "will", "next".
_ARRANGED = lazy_compile(
    r"\b(?:booked|scheduled|planned|moved|arranged|organised|organized|confirmed|registered|signed up|set|"
    r"rescheduled|postponed|pushed|due|will|going to|gonna|next|upcoming|deadline|need|needs|have to|has to)\b", re.I)


def set_for_later(sentence: str) -> bool:
    """Whether a sentence sets a thing up for its day ("Booked for 14
    November", "moved to Friday", "due Friday"): the day it names is ahead of
    the note, and it is not a thing that happened. A day must be named:
    "I've just booked flights" is the booking itself, done that day."""
    return bool(_ARRANGED.search(sentence or "")) and dated_sentence(sentence)


def told_as_past(sentence: str) -> bool:
    """Whether a sentence tells of something that happened ("Slept badly on
    Tuesday.", "Went to the gym on Monday"), not a thing set for its day
    ("Dentist booked for Thursday", "The essay is due Friday"): its day is
    behind the writer, never one ahead (audit 1030 Z26)."""
    return bool(_PAST_VERB.search(sentence or "")) and not _ARRANGED.search(sentence or "")


#: A day the writer only counts by its weekday, and a line that records a
#: measured result on it, are a log of a day gone ("Wednesday bench 60kg."),
#: not a thing due on the next one (audit 1028 E20).
_LOG_TITLE = lazy_compile(r"\b(?:log|logs|diary|journal|tracker|record|records|history|workout|workouts)\b", re.I)
_PLAN_TITLE = lazy_compile(r"\b(?:plan|plans|schedule|programme|program|routine|timetable|agenda|to-?do|goals?|calendar|itinerary)\b", re.I)
_MEASURE = lazy_compile(r"\b\d+(?:\.\d+)?\s?(?:kg|kgs|lbs?|reps?|sets?|km|kms|miles?|mi|kcal|steps|bpm)\b|\b\d+\s?[x\u00d7]\s?\d+\b", re.I)
_WEEKDAY_WORD = lazy_compile(r"\b(?:mon|tues?|wed(?:nes)?|thu(?:rs?)?|fri|sat(?:ur)?|sun)(?:day)?\b", re.I)
#: A day named some other way than by its weekday, or a cue that the line looks ahead.
_CONCRETE_DAY = lazy_compile(
    r"\b(?:today|tomorrow|tonight|yesterday|next|this|due|deadline|(?:by|before|until|till) (?:the |end of |mon|tue|wed|thu|fri|sat|sun)|"
    r"\d{1,2}(?:st|nd|rd|th)\b|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.? \d{1,2}|"
    r"\d{1,2} (?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*|\d{1,2}[/.-]\d{1,2}|\d{4}-\d{2}-\d{2})\b", re.I)


def logged_day(sentence: str, title: str = "") -> bool:
    """Whether a line names its day by a bare weekday and records what was
    done on it: a measured result ("Wednesday bench 60kg for 5 reps"), or
    any line of a log, diary or tracker note. Its weekday is behind the
    writer; a plan, schedule or routine note is the other way round."""
    text = sentence or ""
    if not _WEEKDAY_WORD.search(text) or _ARRANGED.search(text) or _CONCRETE_DAY.search(text):
        return False
    if _PLAN_TITLE.search(title or ""):
        return False
    return bool(_LOG_TITLE.search(title or "") or _MEASURE.search(text))


def dated_sentence(text: str) -> bool:
    """Whether a sentence may name a day or a deadline at all."""
    return bool(_DATED_WIDE.search(text or ""))


_SINCE_Q = lazy_compile(
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
    for read in recognise(text, now=now, tense="future"):
        if read.rank == 0 and read.kind in ("date", "datetime"):
            low = read.text.lower()
            return bool(re.search(r"\d{4}-\d{2}-\d{2}|\d{1,2}[/.]\d{1,2}[/.]\d{2,4}", low)) or any(
                m in low for m in _MONTHS if len(m) > 2
            )
    return False


_DAY_OFFSET = lazy_compile(
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


# --- round 9 readers (c11): the event window at the end of a question, and a distance --------------------------------

_WINDOW_DAYS = frozenset({"monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"})
_WEEKDAY_WINDOW = r"(?:(?:on|this) )?(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
_EVENT_WINDOW_WORDS = rf"this week|next week|this weekend|next weekend|this month|next month|today|tomorrow|tonight|{_WEEKDAY_WINDOW}"
#: Both read text whose whitespace is already one space each (the callers join `split()`), so every gap is a single
#: literal space: no quantified whitespace for a long run to backtrack through (CodeQL polynomial regex).
_EVENT_TAIL = lazy_compile(rf" (?:this|next) (?:week|month|weekend) ?[?.!]*$| (?:today|tomorrow|tonight|{_WEEKDAY_WINDOW}) ?[?.!]*$", re.I)
#: "are we meeting on Tuesday", "is there a team sync on Wednesday": a meeting word stands where "the plumber" does.
EVENT_LEAD = (r"(?:(?:is|are|will) (?:the|my|our|a)\b|(?:are we|am i|will we|will i|do we have|do i have|is there|will there be) (?:an? |the |any )?"
               r"(?:[a-z]+ ){0,2}(?:meeting|meet\w*|call|sync|lunch|dinner|appointment|session|class|visit|interview|catch-?up)\b)")
_EVENT_ASK = lazy_compile(rf"^\W*{EVENT_LEAD}.*? (?P<window>{_EVENT_WINDOW_WORDS}) ?[?.!]*$", re.I)
_DISTANCE = lazy_compile(r"(?<![\d.,])(\d[\d.,]{0,15})\s{0,3}(km|kilometres|kilometers|miles|mi)\b", re.I)


def without_event_window_tail(question: str) -> str:
    """`question` without a window ("this week", "tomorrow") at its end. Only the last 60 characters are read, so a
    long run never meets the pattern (polynomial regex, CodeQL)."""
    question = " ".join((question or "").split())
    return question[:-60] + _EVENT_TAIL.sub("", question[-60:])


def event_window_asked(question: str) -> str:
    """The window ("next week", "today") a yes/no question about a thing ends with, or ""."""
    text = " ".join((question or "").split())
    found = _EVENT_ASK.match(text) if text and len(text) < 300 else None
    if not found:
        return ""
    said = found.group("window").lower()
    #: A weekday keeps its capital in the verdict ("No, not on Wednesday"), as it does everywhere else in an answer.
    *lead, last = said.split()
    return " ".join([*lead, last.title()]) if last in _WINDOW_DAYS else said


def distances(text: str) -> list[tuple[int, int, str, str]]:
    """Each distance said in `text`: (start, end, figure as written, unit as written)."""
    return [(m.start(), m.end(), m.group(1), m.group(2)) for m in _DISTANCE.finditer(text or "")]


def months_named(text: str) -> list[int]:
    """The months `text` names, in order, as 1 to 12 ("best in April" is [4]). "may" counts only
    capitalised, so the verb is not a month. Only the first 2,000 characters are read."""
    found = []
    for word in re.findall(r"[A-Za-z]+", (text or "")[:2000]):
        low = word.lower()
        if low in _MONTHS and (low != "may" or word[:1] == "M"):
            found.append(_MONTHS[low])
    return found


_APART = lazy_compile(
    r"\b(?:(?P<n>\d{1,3}|a|an|one|two|three|four|five|six|seven|eight|nine|ten|twelve|a couple of|a few)|the)\s+"
    r"(?P<u>days?|weeks?|fortnights?)\s+(?P<d>before|earlier|prior to|after|later)\b",
    re.IGNORECASE,
)


def days_apart(text: str) -> int | None:
    """How many days "the day before", "a week before that", "two days later" sit
    from the day they are counted from: negative for before, positive for after;
    None when the text says no such span. "The week before" is seven days."""
    found = _APART.search(text or "")
    if not found:
        return None
    amount = 1 if found["n"] is None else _amount(found["n"])
    if not amount:
        return None
    unit = {"d": 1, "w": 7, "f": 14}[found["u"][0].lower()]
    return amount * unit * (-1 if found["d"].lower() in ("before", "earlier", "prior to") else 1)


#: Time words true of the day a note was written, read against the note's date by
#: `composer_stale` (one reader of date words, tests/test_one_reader.py).
STALE_TIME_WORD = lazy_compile(
    r"\b(?:now|today|tonight|right now|at the moment|currently|these days|"
    r"this (?:morning|afternoon|evening|weekend|week|month))\b", re.I)
THAT_TIME_WORD = lazy_compile(r"\b(?:tonight|this (?:morning|afternoon|evening|weekend|week|month))\b", re.I)
AT_THE_TIME_WORD = lazy_compile(r"\b(?:right now|at the moment|these days)\b", re.I)
DROPPED_NOW_WORD = lazy_compile(r"^(?:now|today)\b,?\s+|\s+\b(?:today|currently)\b(?=\W|$)|^currently\s+", re.I)
