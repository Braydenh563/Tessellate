"""Template variables, filled by rule and never by a model (CHAT_PLAN X13): `{date}`, `{weekday}`,
`{week}`, `{title}` and `{n}` become the day's own words; any other `{slot}` is left for the person
to fill, which is what a saved phrasing chip ("Log a workout: {what}") asks for."""

from __future__ import annotations

import re
from datetime import datetime

_SLOT = re.compile(r"\{(\w+)\}")
_KNOWN = ("date", "weekday", "week", "title", "n", "time", "cursor", "clipboard")


def fill(template: str, now: datetime, title: str = "", n: int = 1) -> str:
    """The template with its known variables written out; unknown ones stay as they are."""
    values = {
        "date": f"{now.day} {now.strftime('%B %Y')}",
        "weekday": now.strftime("%A"),
        "week": str(now.isocalendar()[1]),
        "title": title,
        "n": str(n),
    }
    return _SLOT.sub(lambda m: values.get(m.group(1), m.group(0)), template)


def slots(template: str) -> list[str]:
    """The variables a person must still fill (those `fill` does not know), in order, once each."""
    seen: list[str] = []
    for name in _SLOT.findall(template):
        if name not in _KNOWN and name not in seen:
            seen.append(name)
    return seen
