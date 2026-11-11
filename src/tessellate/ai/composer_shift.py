"""A window moved off the one the turn before named (F13 h, fable-composer-1110).

"and the week before?" after "what did I write last week" is that question over the
week earlier; "what else is on that week?" after an answer about a dated thing asks for
the agenda of that thing's week. Both are rewritten to a plain question the ordinary
readers already answer ("... from 26 October to 1 November", "what is due between
16 November and 22 November"); nothing here searches or writes. None when the turn is neither, or the
turn before named no window and no day.
"""

from __future__ import annotations

import calendar
import re
from datetime import date, timedelta

from tessellate.ai import recognise as rec

_NUMBERS = {"a": 1, "one": 1, "two": 2, "three": 3, "four": 4}
_LEAD = r"^\s*(?:(?:and|but|so|ok)[, ]+)*(?:what about\s+)?"
_SHIFT = re.compile(
    _LEAD + r"(?:the\s+)?(?:(?P<n>\d+|a|one|two|three|four)\s+)?(?P<unit>day|week|month)s?\s+(?P<dir>before|after|earlier|later|prior)"
    r"(?:\s+(?:that|it|then))?\s*[?.!]*$",
    re.I,
)
_STEP = re.compile(_LEAD + r"(?:the\s+)?(?P<dir>previous|next|following|preceding)\s+(?P<unit>day|week|month)\s*[?.!]*$", re.I)
_THAT = re.compile(_LEAD + r"what else (?:is|was|'s) (?:on|happening|going on) (?:that|the same) (?P<unit>day|week)\s*[?.!]*$", re.I)
#: "any other notes around that time", "what else around then", "near then" (INBOX 1739):
#: the notes a few days either side of the day the turn before named.
_NEAR = re.compile(
    _LEAD + r"(?:(?:are there |is there |do i have |did i write |what )?(?:any|anything|something)?\s*(?:(?:other|more|else)\s+)*(?:notes?|stuff|things?|entries)?\s*)"
    r"(?:and\s+)?(?:(?:what about|how about)\s+)?(?:(?:around|near|nearby|close to|within a few days of|about)\s+)"
    r"(?:that\s+(?:time|day|date|week)|then|the same (?:time|day|week))\s*[?.!]*$",
    re.I,
)
_BACK = {"before", "earlier", "prior", "previous", "preceding"}


def _said(day: date, today: date) -> str:
    return f"{day.day} {calendar.month_name[day.month]}" + ("" if day.year == today.year else f" {day.year}")


def _months(day: date, count: int) -> date:
    index = day.year * 12 + day.month - 1 + count
    year, month = divmod(index, 12)
    return date(year, month + 1, min(day.day, calendar.monthrange(year, month + 1)[1]))


def _moved(first: date, last: date, unit: str, count: int) -> tuple[date, date]:
    if unit == "month":
        whole = first.day == 1 and last.day == calendar.monthrange(last.year, last.month)[1]
        moved_first = _months(first, count)
        return (moved_first, date(moved_first.year, moved_first.month, calendar.monthrange(moved_first.year, moved_first.month)[1])) if whole else (moved_first, _months(last, count))
    days = timedelta(days=count * (7 if unit == "week" else 1))
    return first + days, last + days


def _shifted(text: str, previous: str, today: date) -> str | None:
    found = _SHIFT.match(text) or _STEP.match(text)
    window = rec.question_day(previous, today) if found else None
    if not found or window is None:
        return None
    first, last, _phrase, start, end = window
    raw = (found.groupdict().get("n") or "1").lower()
    count = int(raw) if raw.isdigit() else _NUMBERS.get(raw, 1)
    unit = found.group("unit").lower()
    first, last = _moved(first, last, unit, -count if found.group("dir").lower() in _BACK else count)
    base = " ".join(f"{previous[:start]} {previous[end:]}".split()).rstrip(" ?.!")
    return f"{base} on {_said(first, today)}?" if first == last else f"{base} from {_said(first, today)} to {_said(last, today)}?"


def _around(text: str, previous: str, today: date) -> str | None:
    if not _NEAR.match(text):
        return None
    window = rec.question_day(previous, today)
    if window is None:
        return None
    first, last = window[0], window[1]
    return f"what else did I write around {_said(first + (last - first) / 2, today)}?"


def _that_week(text: str, last: dict, today: date) -> str | None:
    found = _THAT.match(text)
    days = [d for d in ((last or {}).get("frame") or {}).get("dates") or [] if isinstance(d, str)]
    if not found or not days:
        return None
    try:
        day = date.fromisoformat(days[0])
    except ValueError:
        return None
    if found.group("unit").lower() != "week":
        return f"what's on {_said(day, today)}?"
    monday = day - timedelta(days=day.weekday())
    return f"what is due between {_said(monday, today)} and {_said(monday + timedelta(days=6), today)}?"


def follow(text: str, previous: str, last: dict, today: date) -> str | None:
    """The plain question `text` stands for after `previous`, or None."""
    return _shifted(text, previous, today) or _that_week(text, last, today) or _around(text, previous, today)
