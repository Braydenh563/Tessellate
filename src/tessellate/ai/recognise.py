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
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

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


def resolve(phrase: str, now: datetime, *, locale: str | None = None) -> datetime | None:
    """The instant `phrase` means, on `now`'s clock, or None. `locale` orders
    a numeric date ("2/11"): day first unless it is a month-first locale."""
    text = " ".join(str(phrase or "").lower().replace(",", " ").split()).strip(" .")
    if not text:
        return None
    iso = _iso(text, now)
    if iso is not None:
        return iso
    shifted = _offset_from(text, now)
    if shifted is not None:
        return shifted
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
            day, rest = found[0], text[:start] + " " + text[end:]
            break
    clock = _clock(rest)
    part = next((p for p in _PARTS if re.search(rf"\b{p}\b", text)), None)
    if day is None and clock is None and part is None:
        #: What the phrase reads as to the recogniser and not to the rules
        #: above ("march" alone, "q4"): its first day, at 9:00.
        for found in recognise(text, now=now, locale=locale, tense="future"):
            if found.rank == 0 and found.kind in ("date", "range") and isinstance(found.value[0] if found.kind == "range" else found.value, date):
                first = found.value[0] if found.kind == "range" else found.value
                return datetime.combine(first, time(9), now.tzinfo)
        return None
    evening = part in ("evening", "night", "tonight")
    if clock is not None:
        hour, minute, meridiem = clock
        if hour == 24:
            return _midnight(day or now.date(), text, now)
        hour = _hour24(hour, meridiem, evening)
        if day is None and meridiem is None and hour < 12:
            # "at 9" with no day: the next 9 o'clock, morning or evening.
            #: "every morning at 7" is seven in the morning, never 19:00.
            for candidate in (hour,) if part == "morning" else (hour, hour + 12):
                at = datetime.combine(now.date(), time(candidate, minute), now.tzinfo)
                if at > now:
                    return at
    else:
        hour, minute = (_PARTS[part] if part else 9), 0
    at = _still_tonight(datetime.combine(day or now.date(), time(hour, minute), now.tzinfo), now, part if clock is None else None)
    if at <= now and day is None:
        at += timedelta(days=1)
    elif at <= now and day == now.date() and _WEEKDAY.search(text):
        at += timedelta(days=7)  # "Monday 9am", said on a Monday afternoon
    return at


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
    #: The past (a timeline entry, "on 3 october") is the recogniser's
    #: reading; `resolve` reads only time to come.
    at = resolve(text, now, locale=locale) if tense == "future" else None
    instant = next((s.value for s in spans if s.kind == "datetime"), None)
    if instant is not None and (at is None or at.date() == instant.date()):
        at = instant
    at = _still_tonight(at, now, _part_alone(text))
    if at is None:
        #: A day `resolve` cannot know but the caller does ("on my birthday").
        day = next((s.value for s in spans if s.kind == "date"), None)
        at = datetime.combine(day, time(9), now.tzinfo) if day else None
    if repeat is not None and (at is None or "BYHOUR" in repeat.value or "BYMONTHDAY" in repeat.value):
        at = first_of(repeat.value, now) or at
    if at is None:
        return None
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
    if not rest:
        rest = text.strip() or "Reminder"
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
#: "the first monday of november", "the last friday of next month": groups
#: are the place, the weekday, this/next/last month, the month's name, a year.
_NTH_IN_MONTH = (
    r"(?:the )?(first|second|third|fourth|last|1st|2nd|3rd|4th) " + _WEEKDAY_RE
    + r" (?:of|in) (?:(this|next|last) month|" + _MONTH_RE + r"(?: (\d{4}))?)"
)
_UNIT_RE = r"(days?|weeks?|fortnights?|months?|years?)"
_AMOUNT_RE = r"(\d{1,3}|a|an|one|two|three|four|five|six|seven|eight|nine|ten|twelve|a couple of|a few)"

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
            _NTH_IN_MONTH,
            r"(?:next|this|last) month,? (?:on )?(?:the )?\d{1,2}(?:st|nd|rd|th)",
            r"(?:the )?(?:first|last) day of (?:(?:this|next|last) month|the month|" + _MONTH_RE + r")",
            r"since (?:the )?(?:\d{1,2}(?:st|nd|rd|th)? (?:of )?" + _MONTH_RE + r"|" + _MONTH_RE + r"(?: \d{1,2}(?:st|nd|rd|th)?)?|"
            + _WEEKDAY_RE + r"|last (?:week|month|year)|yesterday|\d{4}-\d{2}-\d{2})",
            r"(?:the )?week before last",
            r"(?:the )?day (?:after tomorrow|before yesterday)",
            _AMOUNT_RE + r" " + _UNIT_RE + r" ago",
            r"in (?:a fortnight|" + _AMOUNT_RE + r" " + _UNIT_RE + r")",
            r"(?:the )?(?:last|past|previous) (?:(?:\d{1,3}|few|couple of|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve) )?(?:days|weeks|months|years)",
            r"(?:last|this|next|past|coming) (?:week|weekend|month|year)",
            r"(?:last|this|next|coming|on) " + _WEEKDAY_RE + r"(?: (?:morning|afternoon|evening|night))?",
            r"\d{4}-\d{2}-\d{2}",
            r"(?:on )?(?:the )?" + _ORD + r" of (?:next|this|last) month",
            #: "on the 14th of November" whole, never "on the 14th" of this
            #: month (ledger row 441); "November the 14th" too.
            r"(?:on (?=the ))?(?:the )?\d{1,2}(?:st|nd|rd|th)? (?:of )?" + _MONTH_RE + r"(?: \d{4})?",
            _MONTH_RE + r" (?:the )?\d{1,2}(?:st|nd|rd|th)?(?:,? \d{4})?",
            r"(?:on )?the " + _ORD,
            #: "dentist 21st 9am": a bare ordinal is a day of the month only
            #: with a clock right after it (engine probe: it was tomorrow).
            r"\d{1,2}(?:st|nd|rd|th)(?= (?:at \d|\d{1,2}(?::\d{2})? ?(?:am|pm|a\.m\.|p\.m\.)))",
            r"(?:mid|early|late|end of) " + _MONTH_RE,
            r"(?:the )?end of (?:the )?(?:day|week|month|year)|eod",
            r"(?:in|during|from|by) " + _MONTH_RE + r"(?: \d{4})?",
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
    step = {"last": -1, "past": -1, "this": 0, "next": 1, "coming": 1}[which]
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
_MONTH_EDGE = r"(?:the )?(?P<edge>first|last) day of (?:(?P<which>this|next|last) month|(?P<the>the) month|(?P<month>" + "|".join(sorted(_MONTHS, key=len, reverse=True)) + r"))"


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
        first = _month_span(_MONTHS[found.group("month")], a, tense or "future")[0]
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


def span(phrase: str, anchor: date, tense: str | None = None) -> tuple[date, date, str] | None:
    """(first day, last day, grain) the phrase names, read against `anchor`,
    or None. `tense` ("past", "future" or None) picks between the Friday
    before and the Friday after: "I met Sam on Friday" in a note is the one
    before, "I will see Sam on Friday" the one after. Grain is "day",
    "week", "month" or "year"."""
    text = " ".join(str(phrase or "").lower().replace(",", " ").split()).strip(" .")
    text = re.sub(r"^(?:on|by|for|at|from) ", "", text)
    if not text:
        return None
    a = anchor
    found = re.fullmatch(r"since (?:the )?(.+)", text)
    if found:
        start = span(found.group(1), a, "past")
        return (start[0], a, start[2]) if start and start[0] <= a else None
    fixed = {
        "today": (a, a), "tonight": (a, a), "later today": (a, a), "yesterday": (a - timedelta(days=1),) * 2,
        "tomorrow": (a + timedelta(days=1),) * 2, "the day after tomorrow": (a + timedelta(days=2),) * 2,
        "day after tomorrow": (a + timedelta(days=2),) * 2, "the day before yesterday": (a - timedelta(days=2),) * 2,
        "day before yesterday": (a - timedelta(days=2),) * 2, "end of day": (a, a), "the end of the day": (a, a),
        "end of the day": (a, a), "eod": (a, a),
    }
    if text in fixed:
        return (*fixed[text], "day")
    if re.fullmatch(r"(?:the )?week before last", text):
        first, last = _week_of(a - timedelta(days=14))
        return first, last, "week"
    found = re.fullmatch(r"(last|this|next|past|coming) (week|weekend|month|year)", text)
    if found:
        return _calendar_unit_span(*found.groups(), a)
    found = re.fullmatch(r"(?:the )?(?:last|past|previous) (?:(\d{1,3}|few|couple of|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve) )?(days|weeks|months|years)", text)
    if found:
        amount = _amount(found.group(1) or "one") or {"few": 3, "couple of": 2}.get(found.group(1) or "", 1)
        return _back(a, amount, found.group(2)), a, "day"
    found = re.fullmatch(_AMOUNT_RE + r" " + _UNIT_RE + r" ago", text)
    if found:
        amount = _amount(found.group(1))
        if amount is None:
            return None
        day = _back(a, amount, found.group(2))
        return day, day, "day"
    found = re.fullmatch(r"in (?:a fortnight|" + _AMOUNT_RE + r" " + _UNIT_RE + r")", text)
    if found:
        if text == "in a fortnight":
            day = a + timedelta(days=14)
        else:
            amount, unit = _amount(found.group(1)), found.group(2).rstrip("s")
            if amount is None:
                return None
            if unit in ("month", "year"):
                months = amount * (12 if unit == "year" else 1)
                first = _shift_months(a.replace(day=1), months)
                day = first.replace(day=min(a.day, _month_end(first).day))
            else:
                day = a + timedelta(days=amount * {"day": 1, "week": 7, "fortnight": 14}[unit])
        return day, day, "day"
    found = re.fullmatch(_NTH_IN_MONTH, text)
    if found:
        day = _nth_in_month(found, a, tense)
        return (day, day, "day") if day else None
    found = re.fullmatch(r"(?:(last|this|next|coming|on) )?" + _WEEKDAY_RE + r"(?: (?:morning|afternoon|evening|night))?", text)
    if found:
        which, target = found.group(1), _WEEKDAYS[found.group(2)]
        if which == "last":
            back = (a.weekday() - target) % 7 or 7
            day = a - timedelta(days=back)
        elif which == "next":
            day = a + timedelta(days=7 - a.weekday() + target)
        elif which == "this":
            day = _week_of(a)[0] + timedelta(days=target)
        elif which == "coming":
            day = a + timedelta(days=(target - a.weekday()) % 7 or 7)
        else:
            day = _nearest([a + timedelta(days=(target - a.weekday()) % 7), a - timedelta(days=(a.weekday() - target) % 7)], a, tense)
        return day, day, "day"
    found = _ISO_DATE.fullmatch(text)
    if found:
        try:
            day = date(*(int(g) for g in found.groups()))
        except ValueError:
            return None
        return day, day, "day"
    found = _month_day_span(text, a, tense)
    if found:
        return found
    found = re.fullmatch(r"(?:the )?(\d{1,2})(?:st|nd|rd|th)? (?:of )?" + _MONTH_RE + r"(?: (\d{4}))?", text) or re.fullmatch(
        _MONTH_RE + r" (?:the )?(\d{1,2})(?:st|nd|rd|th)?(?:,? (\d{4}))?", text
    )
    if found:
        groups = found.groups()
        day_word, month_word = (groups[0], groups[1]) if groups[0].isdigit() else (groups[1], groups[0])
        year = int(groups[2]) if groups[2] else None
        month = _MONTHS[month_word]
        try:
            if year:
                day = date(year, month, int(day_word))
            else:
                day = _nearest([date(a.year + k, month, int(day_word)) for k in (-1, 0, 1)], a, tense)
        except ValueError:
            return None
        return day, day, "day"
    found = re.fullmatch(r"(?:the )?" + _ORD, text)
    if found:
        day = _day_of_month(int(found.group(1)), a, tense)
        return (day, day, "day") if day else None
    found = re.fullmatch(r"(mid|early|late|end of) " + _MONTH_RE, text)
    if found:
        first, last, _grain = _month_span(_MONTHS[found.group(2)], a, tense or "future")
        part = found.group(1)
        if part == "mid":
            return first.replace(day=15), first.replace(day=15), "day"
        if part == "early":
            return first, first.replace(day=10), "day"
        if part == "late":
            return first.replace(day=21), last, "day"
        return last, last, "day"
    found = re.fullmatch(r"(?:the )?end of (?:the )?(week|month|year)", text)
    if found:
        last = {"week": _week_of(a)[1], "month": _month_end(a), "year": date(a.year, 12, 31)}[found.group(1)]
        return last, last, "day"
    found = re.fullmatch(r"(?:in |during )?" + _MONTH_RE + r"(?: (\d{4}))?", text)
    if found and (found.group(1) not in ("may", "mar", "sat", "sun", "wed") or text.startswith(("in ", "during ")) or found.group(2)):
        return _month_span(_MONTHS[found.group(1)], a, tense, int(found.group(2)) if found.group(2) else None)
    holidays = {"christmas": (12, 25), "christmas day": (12, 25), "christmas eve": (12, 24), "new year": (1, 1),
                "new year's day": (1, 1), "new years day": (1, 1), "new year day": (1, 1), "new year's eve": (12, 31), "new years eve": (12, 31)}
    if text in holidays:
        month, day_n = holidays[text]
        day = _nearest([date(a.year + k, month, day_n) for k in (-1, 0, 1)], a, tense or "future")
        if tense != "past" and day == a and text.startswith("new year") and month == 1:
            day = date(a.year + 1, 1, 1)
        return day, day, "day"
    return None


#: A question's time window, taken off whole before its subject is read
#: ("last week", "3 days ago", "this month"), so "week 4" stays a subject
#: and "last week" is not one. Moved from the composer (ledger row 453).
_WINDOW_WORDS = re.compile(
    r"\b(?:(?:the\s+)?(?:last|this|next|past|previous|coming)\s+(?:few\s+|couple\s+of\s+|\d{1,3}\s+|two\s+|three\s+|four\s+|five\s+|six\s+|seven\s+|eight\s+|nine\s+|ten\s+|eleven\s+|twelve\s+)?"
    r"(?:days?|weeks?|weekend|months?|years?|night|morning|evening|monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
    r"|(?:the\s+)?week\s+before\s+last|(?:\d{1,3}|a|an|one|two|three|four|five|six)\s+(?:days?|weeks?|months?|years?)\s+ago"
    r"|(?:since|in|during)\s+(?:january|february|march|april|may|june|july|august|september|october|november|december))\b",
    re.I,
)
#: A sentence that looks dated: the composer's score for a "when" answer,
#: never turned into a value (that is `find` and `span`).
_DATED = re.compile(
    r"\b(\d{1,2}(st|nd|rd|th)|\d{4}|today|tomorrow|tonight|yesterday|next (week|month|year)|"
    r"last (week|month|year)|this (week|month|year)|weekend|january|february|march|april|may|june|july|"
    r"august|september|october|november|december|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
    re.I,
)


def without_windows(text: str) -> str:
    """`text` with its time windows blanked out."""
    return _WINDOW_WORDS.sub(" ", text or "")


def looks_dated(text: str) -> bool:
    return bool(_DATED.search(text or ""))


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


def question_day(text: str, today: date) -> tuple[date, date, str, int, int] | None:
    """(since, until, phrase, start, end) for the first day or span a search
    question names that is not a stretch ending now ("on tuesday", "in
    March", "two weeks ago"), read in the past tense. A day said in weeks or
    months is widened around it: nobody remembers which day they wrote
    something two weeks ago."""
    anchor = datetime.combine(today, time(12))
    for found in recognise(text, now=anchor, tense="past"):
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


_AHEAD = re.compile(r"\bnext (?:week|month|year)\b|\btomorrow\b", re.IGNORECASE)


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


def says_past(text: str) -> bool:
    return bool(_PAST.search(text or ""))


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


def _date_cands(raw: str, low: str, now: datetime, locale: str | None, tense: str | None, bare_hours: bool = False) -> list[tuple]:
    today = now.date()
    point = tense or "future"
    out: list[tuple] = []
    bases: list[tuple] = []  # (start, end, day, read_as, rank, evening-said)
    month_only = re.compile(r"(?:in |during )?" + _MONTH_RE + r"(?: (\d{4}))?")
    whole = low.strip(" .?!")
    phrases = list(find(low))
    if whole in _MONTHS and len(whole) > 3 and not phrases:
        at = low.index(whole)
        phrases = [(at, at + len(whole), whole)]
    for start, end, phrase in phrases:
        words = phrase.lower()
        if words in ("later today",):
            out.append((start, end, "datetime", resolve("later today", now), "", 0))
            continue
        if words in ("end of day", "end of the day", "the end of the day", "eod"):
            out.append((start, end, "datetime", datetime.combine(today, time(17), now.tzinfo), "", 0))
            continue
        monthly = month_only.fullmatch(words)
        found = span(phrase, today, tense if monthly and not monthly.group(2) else point)
        if found is None:
            continue
        first, last, grain = found
        part = next((p for p in _PARTS if re.search(rf"\b{p}\b", words)), None)
        if first == last and grain == "day":
            bases.append((start, end, first, 0, part))
        else:
            out.append((start, end, "range", found, "", 0))
            if monthly and not monthly.group(2) and tense is None:
                other = _month_span(_MONTHS[monthly.group(1)], today, "future")
                if other[0] != first:
                    out.append((start, end, "range", other, "", 1))
    for start, end, readings in _numeric_dates(low, today, locale, tense):
        for rank, (day, said) in enumerate(readings):
            bases.append((start, end, day, rank, None, said))
    for found in _rx("quarter").finditer(low):
        q, year = int(found.group(1)), int(found.group(2) or today.year)
        first = date(year, 3 * q - 2, 1)
        out.append((found.start(), found.end(), "range", (first, _month_end(date(year, 3 * q, 1)), "quarter"), "", 0))
    for found in _rx("year").finditer(low):
        year = int(found.group(2))
        first, last = date(year, 1, 1), date(year, 12, 31)
        if found.group(1) == "since":
            last = today
        out.append((found.start(), found.end(), "range", (first, last, "year"), "", 0))
    for found in _rx("iso_dt").finditer(low):
        at = _iso(found.group(0), now)
        if at is not None:
            out.append((found.start(), found.end(), "datetime", at, "", 0))
    for found in _rx("this_part").finditer(low):
        at = datetime.combine(today, time(_PARTS[found.group(1)]), now.tzinfo)
        out.append((found.start(), found.end(), "datetime", at, "", 0))
    for base in bases:
        start, end, day, rank, part = base[:5]
        said = base[5] if len(base) > 5 else ""
        evening = part in ("evening", "night", "tonight")
        at: time | None = time(_PARTS[part]) if part else None
        after = _rx("part_after").match(low[end:end + 12])
        if at is None and after:
            part, at, end = after.group(1), time(_PARTS[after.group(1)]), end + after.end()
            evening = part in ("evening", "night")
        clock = _rx("clock_after").match(low[end:end + 24])
        if clock and clock.group(0).strip(" ,"):
            read = _clock_match(clock, evening, bare_ok=bare_hours and _bare_hour(clock, low, end))
            if read is not None:
                at, end = read, end + len(clock.group(0))
        tail = low[max(0, start - 24):start]
        if tail.endswith("first thing "):
            at, start = time(9), start - len("first thing ")
        elif at is None:
            before = _rx("clock_before").search(tail)
            if before and before.group(0).strip():
                read = _clock_match(before, evening)
                if read is not None:
                    at, start = read, start - len(before.group(0))
        if at is None:
            out.append((start, end, "date", day, said, rank))
        elif at == time(0) and "midnight" in low[start:end]:
            out.append((start, end, "datetime", datetime.combine(day + timedelta(days=1), at, now.tzinfo), said, rank))
        else:
            out.append((start, end, "datetime", datetime.combine(day, at, now.tzinfo), said, rank))
    return out


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


def _time_cands(low: str) -> list[tuple]:
    out = []
    for found in _rx("clock").finditer(low):
        if found.group(1):
            at = time(0) if found.group(1) == "midnight" else time(12)
        elif found.group(2):
            at = _hour_from(int(found.group(2)), int(found.group(3)), (found.group(4) or "").replace(".", "") or None)
        elif found.group(5):
            at = _hour_from(int(found.group(5)), 0, found.group(6).replace(".", ""))
        else:
            after = low[found.end():found.end() + 14].lstrip()
            word = after.split(" ")[0].strip(".,") if after else ""
            if after[:1] in ("%", "°") or (word in UNITS and word not in _GLUED_ONLY):
                continue
            at = _hour_from(int(found.group(7)), 0, None)
        if at is not None:
            at, end = _with_part_said(low, at, found.end(), bool(found.group(4) or found.group(6)))
            out.append((found.start(), end, "time", at, "", 0))
    out += _spoken_cands(low) + _word_cands(low)
    for found in _rx("time_range").finditer(low):
        h1, m1, ap1, h2, m2, ap2 = found.groups()
        first = _hour_from(int(h1), int(m1 or 0), ap1 or (ap2 if int(h1) <= int(h2) else None))
        last = _hour_from(int(h2), int(m2 or 0), ap2)
        if first and last and first < last:
            out.append((found.start(), found.end(), "range", (first, last, "time"), "", 0))
    return out


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
    for found in _rx("hm").finditer(low):
        out.append((found.start(), found.end(), "duration", timedelta(hours=int(found.group(1)), minutes=int(found.group(2))), "", 0))
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
    for found in _rx("money_code").finditer(low):
        out.append((found.start(), found.end(), "money", (_figure(found.group(2)), CURRENCY_NAMES[found.group(1)]), "", 0))
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
    for found in _rx("tag").finditer(low):
        out.append((found.start(), found.end(), "tag", raw[found.start(1):found.end(1)].lower(), "", 0))
    for found in _rx("at_person").finditer(low):
        out.append((found.start(), found.end(), "person", raw[found.start(1):found.end(1)], "", 0))
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
    out = []
    for found in _rx("number").finditer(low):
        out.append((found.start(), found.end(), "number", _figure(found.group(1)), "", 0))
    for found in _rx("ordinal").finditer(low):
        out.append((found.start(), found.end(), "ordinal", int(found.group(1)), "", 0))
    for found in _rx("ordinal_word").finditer(low):
        out.append((found.start(1), found.end(1), "ordinal", _ORDINAL_WORDS[found.group(1)], "", 0))
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


def _date_range_cands(low: str, cands: list[tuple]) -> list[tuple]:
    """"from monday to friday": the second end read on or after the first."""
    out = []
    days = {c[0]: c for c in cands if c[2] == "date" and c[5] == 0}
    for found in _rx("date_range").finditer(low):
        first = days.get(found.end())
        if first is None:
            continue
        joint = re.match(r" (?:to|and|until|till|through) ", low[first[1]:first[1] + 10])
        last = days.get(first[1] + len(joint.group(0))) if joint else None
        if last is None:
            continue
        end_day = last[3]
        while end_day < first[3]:
            end_day += timedelta(days=7)
        out.append((found.start(), last[1], "range", (first[3], end_day, "day"), "", 0))
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


def recognise(
    text: str, *, now: datetime, locale: str | None = "en-GB", tense: str | None = None, known: dict | None = None,
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
    tense = tense or tense_of(low)
    cands = _date_cands(raw, low, now, locale, tense, bare_hours)
    cands += _time_cands(low)
    cands += _anchored_cands(low, now, cands) + _date_range_cands(low, cands)
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
