"""Unix time, both ways, off the clock (the Time and date row): "what is
1700000000 as a date", "unix time now", "unix time of 1 January 2024".

The clock is the turn's own (`ctx.now`), so a test with a fixed clock gets a
fixed answer. A date has no clock time in these questions, so it is read as
midnight UTC and the answer says so. No note is read. Questions are read
lower case with blanks collapsed, and no group starts at a blank.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone

from tessellate.ai import composer_clock
from tessellate.ai.composer_clock import computed
from tessellate.ai.composer_study import Ctx, Reply

_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
#: Seconds up to year 5138 (11 digits); milliseconds are 12 to 14 digits.
_MAX_DIGITS = 14
_WORD = r"(?:unix|epoch)(?: time| timestamp)"
#: With a number or a date straight after, the bare word is enough ("epoch 1700000000 to date", "epoch for 25 december").
_LOOSE = r"(?:unix|epoch)(?: time| timestamp)?"
_NOW = re.compile(rf"^(?:what is |what's |tell me )?(?:the )?(?:current |present )?{_WORD}(?: now| right now| today)?$")
_TO_DATE = re.compile(
    rf"^(?:what(?: is|'s)? |convert |turn |what date is )?(?:(?:the )?{_LOOSE} |timestamp )?(?P<n>-?\d{{1,{_MAX_DIGITS}}})(?: as| to| in)? (?:a )?(?:human )?(?:date|time|readable date)$"
    rf"|^(?:convert |what date is |what is |what's )?(?:the )?(?:{_LOOSE}|timestamp) (?P<m>-?\d{{1,{_MAX_DIGITS}}})(?: as| to| in)?(?: a)?(?: human)?(?: date| time)?$"
)
_OF_DATE = re.compile(
    rf"^(?:what is |what's |convert )?(?:the )?{_LOOSE} (?:of|for) (?P<d>\S.*)$|^(?:what is |what's |convert )?(?P<e>\S.*) (?:in|as|to) {_LOOSE}$"
)


def _when(n: int) -> tuple[datetime, str] | None:
    """The UTC instant of a count of seconds, or of milliseconds when it has 12 digits or more."""
    ms = len(str(abs(n))) >= 12
    try:
        return _EPOCH + timedelta(seconds=n / 1000 if ms else n), "milliseconds" if ms else "seconds"
    except OverflowError:
        return None


def _to_date(raw: str) -> Reply | None:
    got = _when(int(raw))
    if got is None:
        return None
    at, unit = got
    return computed(f"{raw} is {composer_clock.long_day(at.date())}, {at:%H:%M:%S} UTC.", f"{unit} since 1 January 1970 UTC")


def _of_date(phrase: str, today: date) -> Reply | None:
    day = composer_clock.on(phrase, today)
    if day is None:
        return None
    n = int((datetime(day.year, day.month, day.day, tzinfo=timezone.utc) - _EPOCH).total_seconds())
    return computed(f"{day.day} {day:%B %Y} is {n} in Unix time (midnight UTC).", f"seconds from 1 January 1970 UTC to the start of {composer_clock.long_day(day)}")


def answer(ctx: Ctx) -> Reply | None:
    text = composer_clock.clean(ctx.question)
    if not text or len(text) > 100:
        return None
    if _NOW.match(text):
        n = int(ctx.now.timestamp())
        return computed(f"The Unix time is {n}.", f"the seconds since 1 January 1970 UTC at {ctx.now:%H:%M} on {composer_clock.long_day(ctx.now.date())} by your clock")
    found = _TO_DATE.match(text)
    if found:
        raw = found["n"] or found["m"]
        if "unix" in text or "epoch" in text or "timestamp" in text or len(raw.lstrip("-")) >= 9:
            return _to_date(raw)
        return None
    found = _OF_DATE.match(text)
    return _of_date(found["d"] or found["e"], ctx.now.date()) if found else None
