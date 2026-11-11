"""Reading an `.ics` file as reminders (TIMELINE_PLAN section 9, decision 17).

The other half of `routes_reminders`' export: a calendar file from a phone or
another app becomes reminders, with a report of what was skipped and why, so
one bad event never costs the rest of the file. Only what a reminder can hold
is read: the summary, the start, a repeat the store can say, the priority,
the first alarm and a completed status. Everything else (attendees,
locations, end times) is a calendar's business and is left behind.

Times: a `Z` time is UTC; a `TZID=` time is that zone where this machine
knows it; a floating time or a date with no time is the reader's own clock
(`tz_offset_minutes`), a date alone at 09:00, the hour the reminders' quick
set uses for "tomorrow". Stored naive UTC, the way every reminder is.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from tessellate.ai import recognise_reminders

#: The hour a date-only event is due at, local time.
ALL_DAY_HOUR = 9
#: A bigger file is not a reminders export; the cap keeps a stray upload of a
#: whole calendar archive from being read into memory line by line.
MAX_BYTES = 2_000_000
#: The same cap the create route puts on a reminder's text.
MAX_TEXT = 500
MAX_ALERT_MINUTES = 43200


@dataclass
class IcsReminder:
    """One event, read as the fields a reminder has."""

    line: int
    text: str = ""
    due_at: datetime | None = None
    priority: str = "normal"
    recurring: str = "none"
    alert_minutes: int | None = None
    done: bool = False
    #: `reminder-<id>@memorymap.local`: an event this app exported, which an
    #: import updates rather than duplicates.
    own_id: int | None = None
    problem: str = ""


@dataclass
class IcsReading:
    events: list[IcsReminder] = field(default_factory=list)
    skipped: list[dict] = field(default_factory=list)


def _unfold(text: str) -> list[tuple[int, str]]:
    """Logical lines with their first physical line number (RFC 5545 3.1)."""
    out: list[tuple[int, str]] = []
    for number, raw in enumerate(text.replace("\r\n", "\n").replace("\r", "\n").split("\n"), start=1):
        if raw[:1] in (" ", "\t") and out:
            out[-1] = (out[-1][0], out[-1][1] + raw[1:])
        elif raw.strip():
            out.append((number, raw))
    return out


def _split(line: str) -> tuple[str, dict[str, str], str]:
    """`NAME;PARAM=V:value` as the name, its params and the value."""
    head, _, value = line.partition(":")
    name, *params = head.split(";")
    found = {}
    for param in params:
        key, _, val = param.partition("=")
        found[key.upper()] = val.strip('"')
    return name.upper(), found, value


def _unescape(value: str) -> str:
    out, i = [], 0
    while i < len(value):
        char = value[i]
        if char == "\\" and i + 1 < len(value):
            nxt = value[i + 1]
            out.append("\n" if nxt in "nN" else nxt)
            i += 2
            continue
        out.append(char)
        i += 1
    return "".join(out)


def _when(value: str, params: dict[str, str], local: timezone) -> datetime:
    """A DTSTART as naive UTC; ValueError for a value that is not one."""
    value = value.strip()
    if params.get("VALUE") == "DATE" or len(value) == 8:
        day = datetime.strptime(value, "%Y%m%d")
        return _to_utc(day.replace(hour=ALL_DAY_HOUR), local)
    if value.endswith("Z"):
        return datetime.strptime(value, "%Y%m%dT%H%M%SZ")
    moment = datetime.strptime(value, "%Y%m%dT%H%M%S")
    zone_name = params.get("TZID")
    zone = local
    if zone_name:
        try:
            zone = ZoneInfo(zone_name)
        except (ZoneInfoNotFoundError, ValueError):
            zone = local
    return _to_utc(moment, zone)


def _to_utc(moment: datetime, zone) -> datetime:
    return moment.replace(tzinfo=zone).astimezone(timezone.utc).replace(tzinfo=None)


def _priority(value: str) -> str:
    """RFC 5545's 1 to 9, read back the way the export writes it (1, 5, 9)."""
    try:
        number = int(value)
    except ValueError:
        return "normal"
    if 1 <= number <= 4:
        return "high"
    if number >= 6:
        return "low"
    return "normal"


def _alert(value: str) -> int | None:
    """`-PT15M`, `-PT2H`, `-P1D` (or `-P1DT2H`) as minutes before; None for
    an alarm at the time itself or after it, which a reminder already is."""
    value = value.strip().upper()
    if not value.startswith("-P"):
        return None
    days, _, clock = value[2:].partition("T")
    minutes = 0
    if days:
        weeks = days.endswith("W")
        count = int(days[:-1])
        minutes += count * (7 * 1440 if weeks else 1440)
    number = ""
    for char in clock:
        if char.isdigit():
            number += char
            continue
        minutes += int(number or 0) * {"H": 60, "M": 1, "S": 0}.get(char, 0)
        number = ""
    return min(minutes, MAX_ALERT_MINUTES) or None


def _own_id(uid: str) -> int | None:
    head, _, host = uid.partition("@")
    if host != "memorymap.local" or not head.startswith("reminder-"):
        return None
    tail = head.removeprefix("reminder-")
    return int(tail) if tail.isdigit() else None


def _apply(event: IcsReminder, name: str, params: dict[str, str], value: str, local: timezone, in_alarm: bool) -> None:
    """One property of an event onto the reminder it is becoming."""
    if in_alarm:
        if name == "TRIGGER" and event.alert_minutes is None:
            event.alert_minutes = _alert(value)
        return
    if name == "SUMMARY":
        event.text = " ".join(_unescape(value).split())[:MAX_TEXT]
    elif name == "DTSTART":
        event.due_at = _when(value, params, local)
    elif name == "PRIORITY":
        event.priority = _priority(value)
    elif name == "RRULE":
        event.recurring = recognise_reminders.stored_repeat(value.strip().upper()) or "none"
    elif name == "STATUS":
        event.done = value.strip().upper() == "COMPLETED"
    elif name == "UID":
        event.own_id = _own_id(value.strip())


def read(text: str, tz_offset_minutes: int = 0) -> IcsReading:
    """Every VEVENT in `text`, each a reminder or a line in `skipped`."""
    local = timezone(timedelta(minutes=tz_offset_minutes))
    reading = IcsReading()
    event: IcsReminder | None = None
    in_alarm = False
    for number, line in _unfold(text):
        name, params, value = _split(line)
        if name == "BEGIN" and value.upper() == "VEVENT":
            event, in_alarm = IcsReminder(line=number), False
        elif name == "BEGIN" and value.upper() == "VALARM":
            in_alarm = True
        elif name == "END" and value.upper() == "VALARM":
            in_alarm = False
        elif name == "END" and value.upper() == "VEVENT" and event is not None:
            _close(event, reading)
            event = None
        elif event is not None and not event.problem:
            try:
                _apply(event, name, params, value, local, in_alarm)
            except ValueError:
                event.problem = f"line {number}: {name} {value.strip()[:40]!r} is not a date this can read"
    return reading


def _close(event: IcsReminder, reading: IcsReading) -> None:
    problem = event.problem
    if not problem and not event.text:
        problem = f"line {event.line}: the event has no summary"
    if not problem and event.due_at is None:
        problem = f"line {event.line}: the event has no start"
    if problem:
        reading.skipped.append({"line": event.line, "text": event.text, "reason": problem})
    else:
        reading.events.append(event)
