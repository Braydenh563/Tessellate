"""What the composer's voice may read, for the dashboard's line and the
companion's remarks (INBOX 743): notes that are not private, drafts, boards
or binned, as the plain dicts `composer_voice` takes, and the reminders due.
Read only; see `repo/__init__.py` for the rules every repository keeps.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tessellate.core.database import Category, Entry, Reminder
from tessellate.entry import manager

#: No private note, draft, board or bin.
SHOWN = (Entry.is_deleted == False, Entry.is_private == False, Entry.is_draft == False, Entry.is_board == False)  # noqa: E712


def as_notes(session: Session, rows: list[Entry]) -> list[dict]:
    """Notes as `composer_voice` reads them (id, content, day, tags, category)."""
    cats = {c.id: c.name for c in session.scalars(select(Category)).all()}
    return [
        {
            "id": e.id,
            "content": e.content or "",
            "created_at": e.created_at.date().isoformat() if e.created_at else "",
            "tags": manager.shown_tags(e),
            "category": "" if cats.get(e.category_id, "").lower().startswith("uncategori") else cats.get(e.category_id, ""),
        }
        for e in rows
    ]


def recent(session: Session, limit: int = 120) -> list[Entry]:
    return list(session.scalars(select(Entry).where(*SHOWN).order_by(Entry.created_at.desc()).limit(limit)).all())


def this_day_before(session: Session, today: date, limit: int = 10) -> list[Entry]:
    """Notes written on today's month and day in an earlier year."""
    return list(session.scalars(
        select(Entry)
        .where(*SHOWN, Entry.created_at < datetime(today.year, 1, 1), func.strftime("%m-%d", Entry.created_at) == today.strftime("%m-%d"))
        .order_by(Entry.created_at.desc())
        .limit(limit)
    ).all())


def due_by(session: Session, today: date, limit: int = 10) -> list[dict]:
    """Open reminders due by the end of tomorrow, soonest first."""
    due = session.scalars(
        select(Reminder).where(Reminder.done == False, Reminder.due_at <= datetime.combine(today + timedelta(days=1), datetime.max.time()))  # noqa: E712
        .order_by(Reminder.due_at).limit(limit)
    ).all()
    return [{"id": r.id, "text": r.text, "due_at": r.due_at.date().isoformat(), "done": False, "entry_id": r.entry_id} for r in due]
