"""A reminder said against a time already in the notebook: "remind me an hour before the dentist" (L-chat-28).

There is no calendar model: a time a note holds is an `EntryDate` row at minute precision (what
"tomorrow at 3pm" meant on the day it was typed, `entry/timewords.py`). The reader keeps the offset and
the name; `settle` finds the note's time, takes the offset off it and hands `_plan_reminder` a due time
like any other, or says what is missing. Nothing here writes.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

_LEAD = r"^(?:(?:please|pls|can you|could you|would you)\s+)*(?:remind me|set a reminder|add a reminder)\s+"
_AMOUNT = r"(?P<n>an?|one|half an?|\d+(?:\.\d+)?)\s*(?P<unit>hours?|hrs?|h|minutes?|mins?|m|days?)"
_AFTER = r"\s+before\s+(?:the |my |our )?(?P<what>[\w' -]+?)(?:\s+(?:appointment|meeting|call|session))?$"
_TASK_FIRST = re.compile(rf"{_LEAD}to\s+(?P<task>.+?)\s+{_AMOUNT}{_AFTER}", re.I)
_PLAIN = re.compile(rf"{_LEAD}(?:to\s+(?P<task>.+?)\s+)?{_AMOUNT}{_AFTER}", re.I)
_NO_WHAT = frozenset({"it", "that", "this", "then", "now", "bed", "work", "lunch", "dinner", "midnight", "noon"})


def _minutes(amount: str, unit: str) -> int:
    word = amount.lower()
    n = 0.5 if word.startswith("half") else 1.0 if word in ("a", "an", "one") else float(word)
    per = 1440 if unit.lower().startswith("d") else 60 if unit.lower().startswith("h") else 1
    return round(n * per)


def read(text: str) -> dict | None:
    """The reminder `text` asks for against a named time, or None. `due_at` stays empty until `settle`."""
    found = _TASK_FIRST.match(text) or _PLAIN.match(text)
    if not found:
        return None
    what = " ".join(found.group("what").split())
    if not what or what.lower() in _NO_WHAT or re.search(r"\d", what):
        return None
    minutes = _minutes(found.group("n"), found.group("unit"))
    task = " ".join((found.group("task") or "").split())
    phrase = f"{found.group('n')} {found.group('unit')} before the {what}"
    return {
        "intent": "reminder", "text": (task[:1].upper() + task[1:]) if task else what[:1].upper() + what[1:], "said": task or phrase,
        "due_at": None, "time_given": True, "clock_unsaid": False, "anchor": {"minutes": minutes, "what": what, "phrase": phrase},
    }


def settle(session: Session, parsed: dict, now: datetime) -> dict:
    """`parsed` with `due_at` set from the note's own time, or `ask` saying why it cannot be."""
    from tessellate.core.database import Entry, EntryDate

    anchor = parsed["anchor"]
    what = anchor["what"].casefold()
    offset = timedelta(minutes=anchor["minutes"])
    rows = session.execute(
        select(EntryDate.at, Entry.content).join(Entry, Entry.id == EntryDate.entry_id)
        .where(EntryDate.precision == "minute", Entry.deleted_at.is_(None)).order_by(EntryDate.at)
    ).all()
    #: Wall-clock times, as the person typed them: the stored zone is not part of "3pm".
    ahead = [at.replace(tzinfo=None) for at, content in rows if at.replace(tzinfo=None) - offset > now and what in (content or "").casefold()]
    if not ahead:
        return {**parsed, "ask": f"I found no time for “{anchor['what']}” in your notes. When is it, so I can set the reminder against it?"}
    clock = ahead[0].strftime("%-I:%M %p").lower()
    return {**parsed, "due_at": ahead[0] - offset, "said": f"{parsed['said']} ({anchor['phrase']}, at {clock})" if parsed["said"] != anchor["phrase"] else f"{anchor['phrase']} (at {clock})"}
