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

from tessellate.ai import recognise
from tessellate.core.database import LIKE_ESCAPE, like_escape

_LEAD = r"^(?:(?:please|pls|can you|could you|would you)\s+)*(?:remind me|set a reminder|add a reminder)\s+"
_AMOUNT = recognise.amount_before()
_AFTER = r"\s+before\s+(?:the |my |our )?(?P<what>[\w' -]+?)(?:\s+(?:appointment|meeting|call|session))?$"
_TASK_FIRST = re.compile(rf"{_LEAD}to\s+(?P<task>.+?)\s+{_AMOUNT}{_AFTER}", re.I)
_PLAIN = re.compile(rf"{_LEAD}(?:to\s+(?P<task>.+?)\s+)?{_AMOUNT}{_AFTER}", re.I)
_LOOKED_AT = 500
_NO_WHAT = frozenset({"it", "that", "this", "then", "now", "bed", "work", "lunch", "dinner", "midnight", "noon"})


def _minutes(amount: str, unit: str) -> int:
    return recognise.amount_minutes(amount, unit)


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
    #: One convention: `EntryDate.at` is the writer's wall clock with no zone
    #: (`entry/manager.py`), so `now` and each row are read that way before they meet.
    now = now.replace(tzinfo=None)
    #: The name narrows in SQL before the cap (a coarse substring, `like_escape` guarding
    #: `%` and `_`); the word-boundary check below then reads what is left.
    like = "%" + like_escape(what) + "%"
    #: A private note and a board never anchor a reminder (Chat does not read them), and only a time still ahead is read.
    rows = session.execute(
        select(EntryDate.at, Entry.content).join(Entry, Entry.id == EntryDate.entry_id)
        .where(EntryDate.precision == "minute", Entry.deleted_at.is_(None), Entry.is_private.is_(False), Entry.is_board.is_(False), EntryDate.at > now + offset, Entry.content.ilike(like, escape=LIKE_ESCAPE))
        .order_by(EntryDate.at).limit(_LOOKED_AT)
    ).all()
    named = re.compile(rf"(?<!\w){re.escape(what)}(?!\w)")
    #: The column type hands rows back tagged UTC; the clock is still the writer's wall clock.
    ahead = [at.replace(tzinfo=None) for at, content in rows if at.replace(tzinfo=None) - offset > now and named.search((content or "").casefold())]
    if not ahead:
        return {**parsed, "ask": f"I found no time for “{anchor['what']}” in your notes. When is it, so I can set the reminder against it?"}
    clock = f"{ahead[0].hour % 12 or 12}:{ahead[0].minute:02d} {'pm' if ahead[0].hour >= 12 else 'am'}"  # "%-I" is glibc-only
    return {**parsed, "due_at": ahead[0] - offset, "said": f"{parsed['said']} ({anchor['phrase']}, at {clock})" if parsed["said"] != anchor["phrase"] else f"{anchor['phrase']} (at {clock})"}
