"""The rules a new reminder is held to: its time read against the person's clock,
and the same words at the same minute being one reminder, not two (audit 1028 E29)."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from tessellate.ai.tools._common import ToolError
from tessellate.core.database import Reminder


def _minute(when: datetime | None) -> datetime | None:
    return when.replace(second=0, microsecond=0, tzinfo=None) if when else None


def _open_reminders(session: Session, text: str) -> list[Reminder]:
    """The reminders still waiting that say `text` (case and spacing aside)."""
    wanted = " ".join(text.split()).casefold()
    rows = session.scalars(select(Reminder).where(Reminder.done.is_(False), Reminder.deleted_at.is_(None))).all()
    return [r for r in rows if " ".join((r.text or "").split()).casefold() == wanted]


def held_reminder(session: Session, text: str, due_at: datetime) -> dict | None:
    """The result for a waiting reminder with these words at this minute, marked
    `existing`, else None."""
    for held in _open_reminders(session, text):
        if _minute(held.due_at) == _minute(due_at):
            return {
                "id": held.id, "text": held.text, "due_at": held.due_at.isoformat(), "existing": True,
                "due": held.due_at.strftime("%A %d %B %Y, %H:%M"),
                "label": f"⏰ Already set for {held.due_at.strftime('%a %d %b %Y %H:%M')}",
            }
    return None


def reminder_time(args: dict, now: datetime) -> datetime:
    """The time a reminder is for, read against `now`, or a ToolError saying what to give."""
    from tessellate.ai import when as when_words

    said = str(args.get("when") or "").strip()
    exact = str(args.get("due_at") or "").strip()
    due_at = when_words.resolve(said, now) if said else None
    if due_at is None and exact:
        due_at = when_words.resolve(exact, now)
    if due_at is None:
        raise ToolError(
            f"Couldn't read '{said or exact}' as a time. Put the user's own "
            "words in `when`, like 'tomorrow at 9am', 'in 20 minutes' or "
            "'Friday evening'."
            if said or exact
            else "Say when in `when`, in the user's words, like 'tomorrow at 9am'."
        )
    if due_at < now - timedelta(minutes=1):
        raise ToolError(
            f"{due_at.strftime('%A %d %B %H:%M')} has already passed. Ask the "
            "user for a time that has not happened yet."
        )
    return due_at
