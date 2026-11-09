"""How far off a date in a fact is (R9-17): "Mum's birthday is 2 December" is said "in 23 days", not "written on
11 August, about three months ago". Only a day and a month said in the fact, and only one still ahead."""

from __future__ import annotations

import re
from datetime import date

_MONTHS = ("january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december")
_NAMES = "|".join(_MONTHS)
_DAY_FIRST = re.compile(rf"\b(?P<d>\d{{1,2}})(?:st|nd|rd|th)?(?: of)? (?P<m>{_NAMES})\b(?:,? (?P<y>\d{{4}}))?", re.IGNORECASE)
_MONTH_FIRST = re.compile(rf"\b(?P<m>{_NAMES}) (?P<d>\d{{1,2}})(?:st|nd|rd|th)?\b(?:,? (?P<y>\d{{4}}))?", re.IGNORECASE)


def date_in(fact: str, today: date) -> date | None:
    found = _DAY_FIRST.search(fact) or _MONTH_FIRST.search(fact)
    if not found:
        return None
    try:
        return date(int(found.group("y") or today.year), _MONTHS.index(found.group("m").lower()) + 1, int(found.group("d")))
    except ValueError:
        return None


def distance(fact: str, today: date) -> str:
    """"in 23 days" for a fact whose day is still ahead, else ""."""
    day = date_in(fact, today)
    if day is None or day < today:
        return ""
    days = (day - today).days
    if days == 0:
        return "today"
    if days == 1:
        return "tomorrow"
    return f"in {days} days" if days <= 60 else f"in about {round(days / 30)} months"
