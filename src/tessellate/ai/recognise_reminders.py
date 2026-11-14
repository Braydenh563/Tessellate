"""Magic Add and the repeat rules: a reminder sentence with its time taken out (audit K24, BK11).

Moved whole out of `ai/recognise.py`. It sits above the recogniser: it reads a
sentence with `recognise.recognise` and resolves its day with
`recognise.resolve`, so `recognise` never imports it. Callers import from here.
"""

from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta

from tessellate.ai.recognise import (
    Span,
    _part_alone,
    _still_tonight,
    recognise,
    resolve,
    strip_lead,
)
from tessellate.ai.recognise_windows import _WEEKDAY_CODES, _nth_of_month, _valid_day
from tessellate.core.lazyre import lazy_compile

# --- Magic Add: a reminder sentence with its time taken out (UX-01) ---------
#
# `resolve` reads the whole sentence, so "call mum tomorrow at 5pm" resolves as
# it stands; what it cannot say is which words were the time. The reminder that
# fires should read "Call mum", not "Call mum tomorrow at 5pm" a day later. The
# words cut are the spans `recognise` reads as a time, so what is stripped is
# exactly what was read, by the same reader.

# "Call mum tomorrow evening, high priority": the placeholder's own example.
_PRIORITY = lazy_compile(r"\b(high|low)\s+priority\b", re.IGNORECASE)
_TIME_KINDS = frozenset({"date", "datetime", "time", "range", "recurrence", "alert"})
#: The reminder repeats the app can store (`routes_reminders.Recurring`).
_STORED_REPEATS = {"FREQ=DAILY": "daily", "FREQ=WEEKLY": "weekly", "FREQ=MONTHLY": "monthly"}
#: A rule the store keeps as itself (TIMELINE_PLAN 11 row 8): every other
#: week, weekdays, the last Friday of the month. The hour is the due time's.
STORED_RULE = lazy_compile(
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
    if _only_topics(text, spans):
        return None
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
    cuts = [(s.start, s.end) for s in spans if _is_time_words(s, text, spans)]
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
        rest = _keep_due_day(rest, [s.text for s in sorted(spans, key=lambda s: s.start) if _is_time_words(s, text, spans)])
    return (rest or text.strip() or "Reminder"), priority


_CLOCK_TAIL = lazy_compile(r"(?<!\s)\s+(?:(?:at\s+)?\d{1,2}(?::\d{2})?\s*(?:am|pm)|at\s+\d{1,2}(?::\d{2})?|\d{1,2}:\d{2})\Z", re.I)


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


#: "between 8 and 10", "from 8pm to 10pm": a window of the clock. Bare numbers
#: count only when the sentence ends there or at a day word, so "between 1 and
#: 5 October" stays a date range.
_CLOCK_WINDOW = lazy_compile(
    r"\b(?:between|from)\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\s+(?:and|to|until|till)\s+(\d{1,2})(?::\d{2})?\s*(am|pm)?\b",
    re.I,
)
_WINDOW_ENDS = lazy_compile(r"\s*(?:[,.;!?]|\Z|(?:tonight|tomorrow|today|morning|evening|night)\b)", re.I)


def window_start(text: str) -> str:
    """A clock window said as the time it opens ("plumber thursday between 8
    and 10" is "plumber thursday at 8"): a reminder is due when the window
    starts, not at the day's default (audit G10). An end with am or pm lends
    its half of the day to a bare start, unless that would put the start
    after the end ("11 to 1pm" opens at 11am)."""
    found = _CLOCK_WINDOW.search(text)
    if found is None:
        return text
    hour, minute, half, end_hour, end_half = found.group(1), found.group(2), found.group(3), found.group(4), found.group(5)
    if not (half or end_half or minute) and not _WINDOW_ENDS.match(text, found.end()):
        return text
    if not half and end_half:
        half = end_half if int(hour) <= int(end_hour) or int(hour) == 12 else ("am" if end_half.lower() == "pm" else "pm")
    start = f"{hour}:{minute}" if minute else hour
    return f"{text[:found.start()]}at {start}{half or ''}{text[found.end():]}"


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
    text = window_start(text)
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
    if repeat is None and spans and not any(s.kind in ("time", "datetime") for s in spans):
        #: A day with no clock: the time is the default, and said as that.
        parsed["clock_unsaid"] = True
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


#: What may follow a holiday word and still be its time ("christmas eve", "christmas at 5", "christmas and new year").
_TIME_CONTINUES = frozenset({"day", "eve", "morning", "evening", "night", "afternoon", "at", "on", "by", "before", "after", "and", "or", "next", "this", "every", "each", "early", "late", "tomorrow", "today", "tonight", "in", "from", "until", "till", "to"})


def _names_a_topic(before: str, after: str) -> bool:
    """"about christmas plans": a holiday word, after "about" and before a plain noun, names what the task is about, not when."""
    nxt = re.match(r"\s*([a-z]+)", after.lower())
    return before.endswith(("about ", "re ")) and bool(nxt) and nxt.group(1) not in _TIME_CONTINUES


def _only_topics(text: str, spans: list) -> bool:
    """Every time the sentence holds is a holiday word naming the task's topic ("call mum about christmas plans"): no time is said."""
    timed = [s for s in spans if s.kind in _TIME_KINDS and s.kind != "alert"]
    return bool(timed) and all(re.match(r"(?:new year|christmas)", s.text.lower()) and _names_a_topic(text[:s.start].lower(), text[s.end:]) for s in timed)


def _is_time_words(found: Span, text: str, spans: list | tuple = ()) -> bool:
    """Whether a span's words are the reminder's time and so come out of its
    text. A holiday after "the" is the thing to do ("see the new year"), not
    the time, which is still read from it; so is one after "about" or "for"
    when another span already gives the time ("call mum on sunday about
    christmas plans", G10)."""
    if found.kind == "duration":
        return found.text.lower().startswith("in ")
    holiday = re.match(r"(?:new year|christmas)", found.text.lower())
    before = text[:found.start].lower()
    timed_elsewhere = any(o is not found and o.kind in _TIME_KINDS and o.kind != "alert" for o in spans)
    thing = holiday and (before.endswith("the ") or timed_elsewhere and before.endswith(("about ", "for ", "re ")) or _names_a_topic(before, text[found.end:]))
    return found.kind in _TIME_KINDS and not thing


def _repeat_and_alert(parsed: dict, repeat: Span | None, spans: list) -> None:
    """A reminder's stored repeat and its early alert, when the words say them."""
    if repeat is not None and stored_repeat(repeat.value):
        parsed["recurring"] = stored_repeat(repeat.value)
    alert = next((s for s in spans if s.kind == "alert"), None)
    if alert is not None:
        parsed["alert_minutes"] = alert.value
