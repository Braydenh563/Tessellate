"""Counts of things still to do (composer work list, INBOX 1026c).

"How many reminders do I have", "how many reminders this week", "how many open
tasks", "how many unticked items": the notebook's own figures, never a search
for the word "reminders". An open item is an unticked checklist box in a live
note; an open reminder is one not yet done. The time word ("this week") is
read by `ai/recognise.py` (`ahead_window`); this module reads no date."""

from __future__ import annotations

import re
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from tessellate.core.database import Entry, Reminder

_REMINDERS = re.compile(r"\breminders?\b")
_THINGS = r"(?:tasks?|items?|to-?dos?|boxes|checkboxes|tick ?boxes)"
_OPEN_WORD = r"(?:unticked|unchecked|open|outstanding|incomplete|remaining|left|still to do|to do)"
_OPEN_ITEMS = re.compile(rf"\b{_OPEN_WORD}\b.*\b{_THINGS}\b|\b{_THINGS}\b.*\b{_OPEN_WORD}\b")
_BOX = re.compile(r"^[ \t]*(?:[-*+]|\d{1,3}[.)])[ \t]+\[([ xX])\]", re.M)


def open_items(contents: list[str]) -> tuple[int, int]:
    """(unticked boxes, notes holding any box) over these notes' text."""
    unticked = holders = 0
    for text in contents:
        boxes = _BOX.findall(text or "")
        holders += bool(boxes)
        unticked += sum(1 for mark in boxes if mark == " ")
    return unticked, holders


def _open_items_answer(session: Session, visible) -> tuple[str, str, list[dict]]:  # noqa: ANN001
    contents = list(session.scalars(visible(select(Entry.content)).where(Entry.archived_at.is_(None))))
    unticked, holders = open_items(contents)
    if not unticked:
        return "open-items", "You have no unticked checklist items.", [{"label": "open items", "count": 0}]
    item = "open item" if unticked == 1 else "open items"
    where = "1 checklist" if holders == 1 else f"{holders} checklists"
    return "open-items", f"You have {unticked} {item} across {where}.", [{"label": "open items", "count": unticked}]


def _ahead_end(moment: datetime, days: int) -> datetime:
    """Where a window of `days` ahead ends: the end of today for 0, the end of
    the month for a negative figure (`recognise.ahead_window`'s "this month")."""
    if days < 0:
        first = (moment.replace(day=28) + timedelta(days=4)).replace(day=1)
        return first - timedelta(seconds=1)
    return moment.replace(hour=23, minute=59, second=59) + timedelta(days=days)


def _reminders_answer(session: Session, now: datetime, ahead: tuple[str, int] | None) -> tuple[str, str, list[dict]]:
    moment = now.replace(tzinfo=None)
    due = [at.replace(tzinfo=None) for at in session.scalars(select(Reminder.due_at).where(Reminder.done.is_(False)))]
    if ahead is not None:
        said, days = ahead
        end = _ahead_end(moment, days)
        count = sum(1 for at in due if moment <= at <= end)
        noun = "reminder" if count == 1 else "reminders"
        return "reminder-count", f"You have {count or 'no'} {noun} due {said}.", [{"label": "reminders", "count": count}]
    late = sum(1 for at in due if at < moment)
    noun = "open reminder" if len(due) == 1 else "open reminders"
    tail = f", {late} of them overdue" if late and len(due) > 1 else ", and it is overdue" if late else ""
    return "reminder-count", f"You have {len(due) or 'no'} {noun}{tail}.", [{"label": "reminders", "count": len(due)}]


def answer(text: str, session: Session, now: datetime, visible, ahead: tuple[str, int] | None):  # noqa: ANN001, ANN201
    """(kind, sentence, facts) for a count of reminders or open items, or None."""
    if _REMINDERS.search(text):
        return _reminders_answer(session, now, ahead)
    if _OPEN_ITEMS.search(text):
        return _open_items_answer(session, visible)
    return None
