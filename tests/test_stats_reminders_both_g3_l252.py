"""L252 G3 (recovered from the deleted g13-1110 note): "how many open reminders and how
many are overdue" is one count with both numbers, not the overdue count alone."""

from __future__ import annotations

from datetime import datetime

from tessellate.ai import notebook_tasks
from tessellate.repo import reminders as reminder_repo

NOW = datetime(2026, 11, 10, 9, 0)


def _seed(session):
    for text, due in (("a", datetime(2026, 11, 9, 9)), ("b", datetime(2026, 11, 8, 9)), ("c", datetime(2026, 11, 12, 9))):
        reminder_repo.create(session, text=text, due_at=due, done=False)
    session.commit()


def _say(session, question):
    return notebook_tasks.answer(question, session, NOW, lambda q: q, None)[1]


def test_open_and_overdue_asked_together_give_both_counts(session):
    _seed(session)
    said = _say(session, "how many open reminders and how many are overdue")
    assert said == "You have 3 open reminders, 2 of them overdue."


def test_overdue_alone_is_still_the_overdue_count(session):
    _seed(session)
    assert _say(session, "how many reminders are overdue") == "You have 2 overdue reminders."
