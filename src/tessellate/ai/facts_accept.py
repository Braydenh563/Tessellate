"""Accepting a fact the night pass read by rule (L-world-class-27).

A date a note names becomes a reminder on that day; a note that says what an earlier one
does is merged into it by Tidy's own merge. Neither asks a model, and each returns what
the caller needs to undo it (a reminder id, a Tidy undo id). Entities and the judged
kinds have no accept: they are read, not acted on."""

from __future__ import annotations

import re
from datetime import date, datetime, time, timezone

from sqlalchemy.orm import Session

from tessellate.core.database import DerivedFact, Entry
from tessellate.repo import reminders as reminder_repo

ACCEPTABLE = ("date", "duplicate")
#: A reminder is a day, not an hour: the morning, the same default the composer's chips use.
REMINDER_HOUR = 9
_SAID_BY = re.compile(r"note (\d+)$")


def accept(session: Session, fact: DerivedFact, now: datetime) -> dict:
    """Do what the fact proposes. `now` is the caller's clock (aware UTC); ValueError says why not."""
    entry = session.get(Entry, fact.entry_id)
    if entry is None or entry.is_deleted or entry.is_private:
        raise ValueError("That note is gone.")
    if fact.kind == "date":
        return _remind(session, fact, entry, now)
    if fact.kind == "duplicate":
        return _merge(session, fact)
    raise ValueError("Only a date or a duplicate can be accepted.")


def _day(fact: DerivedFact, entry: Entry) -> date | None:
    """The calendar day the fact's span names, read again as the pass read it."""
    from tessellate.ai import recognise

    for span in recognise.recognise(entry.content or "", now=entry.created_at or datetime(2000, 1, 1, 12)):
        if span.kind == "date" and span.rank == 0 and span.start == fact.span_start and isinstance(span.value, date):
            return span.value.date() if isinstance(span.value, datetime) else span.value
    return None


def _remind(session: Session, fact: DerivedFact, entry: Entry, now: datetime) -> dict:
    day = _day(fact, entry)
    if day is None:
        raise ValueError("I could not read that date again.")
    due = datetime.combine(day, time(REMINDER_HOUR), tzinfo=timezone.utc)
    if due <= now:
        raise ValueError("That date has already passed.")
    content = entry.content or ""
    start = content.rfind("\n", 0, fact.span_start) + 1
    end = content.find("\n", fact.span_end)
    line = content[start: len(content) if end == -1 else end].strip().lstrip("-*+ ").strip()[:200] or fact.text
    twin = reminder_repo.twin(session, line, due)
    if twin is not None:
        return {"kind": "reminder", "reminder_id": twin, "due_at": due.isoformat(), "existing": True}
    made = reminder_repo.create(session, text=line, due_at=due, entry_id=entry.id)
    return {"kind": "reminder", "reminder_id": made.id, "due_at": due.isoformat(), "existing": False}


def _merge(session: Session, fact: DerivedFact) -> dict:
    from tessellate.entry import tidy

    said = _SAID_BY.search(fact.text or "")
    if said is None:
        raise ValueError("I could not tell which note this repeats.")
    return {"kind": "merge", **tidy.merge_pair(session, int(said.group(1)), fact.entry_id)}
