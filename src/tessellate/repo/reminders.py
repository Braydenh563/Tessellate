"""Reminders: the one place the `reminders` table is read and written (INBOX
1499, row 3a's third resource). A binned reminder is out of every read by the
session's bin floor (`core/database.py`); `get_any` is the bin's own read.
See `repo/__init__.py` for the rules every repository keeps.
"""

from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta, timezone
from typing import Callable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tessellate.ai import recognise_reminders
from tessellate.core.database import Reminder, utcnow
from tessellate.entry.manager import log_action
from tessellate.repo import Conflict, NotFound

MISSING = "That reminder could not be found."

#: The order every list of reminders is read in: soonest first, the id the
#: tiebreaker so two due in the same minute never swap between pages.
ORDER = (Reminder.due_at, Reminder.id)


def find(session: Session, reminder_id: int) -> Reminder | None:
    return session.get(Reminder, reminder_id)


def get(session: Session, reminder_id: int) -> Reminder:
    reminder = find(session, reminder_id)
    if reminder is None:
        raise NotFound(MISSING)
    return reminder


def get_any(session: Session, reminder_id: int) -> Reminder:
    """The reminder, binned or not: the bin's restore and purge read this."""
    from tessellate.entry.bin import including_binned

    with including_binned(session):
        reminder = session.get(Reminder, reminder_id)
    if reminder is None:
        raise NotFound(MISSING)
    return reminder


def page(
    session: Session,
    *,
    limit: int,
    offset: int,
    entry_id: int | None = None,
    document_id: int | None = None,
    include_done: bool = True,
    only_done: bool = False,
    due_before: datetime | None = None,
) -> tuple[list[Reminder], int]:
    """A page soonest first and the total of the same filtered set: a total
    that answers a different question from the rows is worse than none."""
    filters = []
    if entry_id is not None:
        filters.append(Reminder.entry_id == entry_id)
    if document_id is not None:
        filters.append(Reminder.document_id == document_id)
    if only_done:
        filters.append(Reminder.done.is_(True))
    elif not include_done:
        filters.append(Reminder.done.is_(False))
    if due_before is not None:
        filters.append(Reminder.due_at <= due_before)
    total = session.scalar(select(func.count(Reminder.id)).where(*filters)) or 0
    rows = session.scalars(select(Reminder).where(*filters).order_by(*ORDER).limit(limit).offset(offset))
    return list(rows), total


def every(session: Session, *, include_done: bool = False, limit: int | None = None) -> list[Reminder]:
    """Every reminder soonest first, the ticked-off ones only when asked."""
    statement = select(Reminder).order_by(*ORDER)
    if not include_done:
        statement = statement.where(Reminder.done.is_(False))
    if limit is not None:
        statement = statement.limit(limit)
    return list(session.scalars(statement))


def open_stamp(session: Session, limit: int) -> dict:
    """What the page's once-a-minute look needs to know whether its list is
    still true (audit 1028 K32): how many are open, the soonest, and a stamp
    over the same first `limit` open rows `page` would answer, with the columns
    the badge, the title count, the due timer and an announcement read. Columns
    only, no row objects: this is the cheap question that spares the dear one."""
    rows = session.execute(
        select(
            Reminder.id, Reminder.due_at, Reminder.text, Reminder.alert_minutes, Reminder.priority,
            Reminder.recurring, Reminder.entry_id, Reminder.document_id,
        )
        .where(Reminder.done.is_(False))
        .order_by(*ORDER)
        .limit(limit)
    ).all()
    total = session.scalar(select(func.count(Reminder.id)).where(Reminder.done.is_(False))) or 0
    digest = hashlib.sha1(usedforsecurity=False)
    for row in rows:
        digest.update(repr(tuple(row)).encode("utf-8"))
    return {"open": total, "next_due_at": rows[0].due_at.isoformat() if rows else None, "stamp": digest.hexdigest()[:16]}


def count(session: Session) -> int:
    return session.scalar(select(func.count(Reminder.id))) or 0


def counts_for_notes(session: Session, entry_ids: list[int], *, include_done: bool) -> dict[int, int]:
    """How many reminders each of these notes has, in one query."""
    filters = [Reminder.entry_id.in_(entry_ids)]
    if not include_done:
        filters.append(Reminder.done.is_(False))
    rows = session.execute(
        select(Reminder.entry_id, func.count(Reminder.id)).where(*filters).group_by(Reminder.entry_id)
    ).all()
    return {entry_id: int(n) for entry_id, n in rows if entry_id is not None}


def on_note(session: Session, entry_id: int) -> list[Reminder]:
    return list(session.scalars(select(Reminder).where(Reminder.entry_id == entry_id, Reminder.deleted_at.is_(None))))


def matching(session: Session, clause: Callable, limit: int) -> list[Reminder]:
    """Reminders whose text the caller's clause matches, latest due first;
    `clause` is given the text column (the chat's word match builds it)."""
    return list(session.scalars(select(Reminder).where(clause(Reminder.text)).order_by(Reminder.due_at.desc()).limit(limit)))


def due_in(in_range: Callable):  # noqa: ANN201
    """The statement for reminders placed by their due time, for the
    timeline's paged merge (`in_range` adds its window to a statement)."""
    return in_range(select(Reminder), Reminder.due_at)


def due_days(session: Session, in_range: Callable) -> list[date]:
    """The day each reminder in the window is due, for the timeline's density."""
    return [due.date() for (due,) in session.execute(in_range(select(Reminder.due_at), Reminder.due_at)).all()]


def due_by(session: Session, today: date, limit: int = 10) -> list[dict]:
    """Open reminders due by the end of tomorrow, soonest first, as the
    composer's voice reads them (the dashboard's line, the companion)."""
    due = session.scalars(
        select(Reminder)
        .where(Reminder.done.is_(False), Reminder.due_at <= datetime.combine(today + timedelta(days=1), datetime.max.time()))
        .order_by(Reminder.due_at)
        .limit(limit)
    ).all()
    return [{"id": r.id, "text": r.text, "due_at": r.due_at.date().isoformat(), "done": False, "entry_id": r.entry_id} for r in due]


def twin(session: Session, text: str, due_at: datetime) -> int | None:
    """An open reminder with the same words at the same time, for the
    "you already have this" warning (made anyway: warn, don't block)."""
    return session.scalar(
        select(Reminder.id)
        .where(
            func.lower(func.trim(Reminder.text)) == text.strip().lower(),
            Reminder.due_at == due_at,
            Reminder.done.is_(False),
        )
        .limit(1)
    )


def create(session: Session, **fields) -> Reminder:
    reminder = Reminder(**fields)
    session.add(reminder)
    session.flush()
    log_action(session, "created", "reminder", reminder.id, (reminder.text or "")[:80])
    return reminder


def import_event(session: Session, event) -> tuple[str, Reminder]:  # noqa: ANN001
    """A calendar event as a reminder: the one this app wrote (its UID names
    it) is updated, so importing the same file twice doubles nothing."""
    reminder = session.get(Reminder, event.own_id) if event.own_id else None
    verb = "updated"
    if reminder is None or reminder.deleted_at is not None:
        reminder, verb = Reminder(), "added"
        session.add(reminder)
    reminder.text = event.text
    reminder.due_at = event.due_at.replace(tzinfo=timezone.utc)
    reminder.priority = event.priority
    reminder.recurring = event.recurring
    reminder.alert_minutes = event.alert_minutes
    reminder.done = event.done
    session.flush()
    return verb, reminder


def complete(session: Session, reminder: Reminder, tz_offset_minutes: int) -> None:
    """Done, or for a repeating reminder its next time: the rule is rolled on
    from the due time (`recognise.next_occurrence`) until it is ahead of now,
    in the person's days (`tz_offset_minutes`, minutes east of UTC)."""
    if reminder.recurring and reminder.recurring != "none":
        shift = timedelta(minutes=tz_offset_minutes)
        due = reminder.due_at.replace(tzinfo=None) + shift
        now = utcnow().replace(tzinfo=None) + shift
        # A 31st clamped to the 28th remembers it was a 31st (Brief 101b).
        anchor = reminder.repeat_day or due.day
        for _ in range(1000):
            due = recognise_reminders.next_occurrence(reminder.recurring, due, anchor)
            if due > now:
                break
        reminder.repeat_day = anchor if anchor > 28 else None
        reminder.due_at = due - shift
        reminder.done = False
        log_action(session, "edited", "reminder", reminder.id, "rolled on")
    else:
        reminder.done = True
        log_action(session, "edited", "reminder", reminder.id, "done")


def snooze(session: Session, reminder: Reminder, by: timedelta) -> None:
    """Later by `by`. A done reminder stays done: a notification left on screen after the tick
    must not open it again (INBOX 1747, row 5)."""
    if reminder.done:
        return
    reminder.due_at = utcnow() + by
    reminder.done = False
    log_action(session, "edited", "reminder", reminder.id, "snoozed")


def move_to_bin(session: Session, reminder: Reminder) -> None:
    """To the recycle bin: hidden, not fired, restorable with its id."""
    log_action(session, "deleted", "reminder", reminder.id)
    reminder.deleted_at = utcnow()
    session.flush()


def restore(session: Session, reminder: Reminder) -> None:
    if reminder.deleted_at is not None:
        reminder.deleted_at = None
        log_action(session, "restored", "reminder", reminder.id)
        session.flush()


def purge(session: Session, reminder: Reminder) -> None:
    """For good; only a binned reminder (a live one goes to the bin first)."""
    if reminder.deleted_at is None:
        raise Conflict("Only a reminder in the bin can be deleted for good.")
    log_action(session, "purged", "reminder", reminder.id)
    session.delete(reminder)
    session.flush()


def open_on_notes(session: Session, entry_ids: list[int]) -> list[Reminder]:
    """The reminders on these notes still pending, soonest first."""
    if not entry_ids:
        return []
    return list(
        session.scalars(
            select(Reminder)
            .where(Reminder.entry_id.in_(entry_ids), Reminder.done.is_(False), Reminder.deleted_at.is_(None))
            .order_by(*ORDER)
        )
    )
