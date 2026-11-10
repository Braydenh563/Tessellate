"""One count of the reminders that are due, for every surface that says it
(audit 2 G3: the chat greeting, the dashboard digest, the dashboard's line and
its tile gave four counts for the same reminders).

**The rule.** An open reminder is *due today* when its day is today (a time
earlier today is still today), *overdue* when its day is before today, and
*later* otherwise. A done reminder counts as none of them. The dashboard
(`dashboard.js`, `dashDueSummary`) reads the same rule.

**The wording.** "One due today, two overdue"; either half is left out when it
is zero. Nothing due and nothing overdue is "" (the caller says what it says).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone

from tessellate.ai import realise


@dataclass(frozen=True)
class Due:
    today: int = 0
    overdue: int = 0
    later: int = 0

    @property
    def now(self) -> int:
        """Reminders that want attention now: today's and the overdue."""
        return self.today + self.overdue


def _naive(moment: datetime) -> datetime:
    return moment.astimezone(timezone.utc).replace(tzinfo=None) if moment.tzinfo else moment


def _get(row, key: str):  # noqa: ANN001, ANN202
    return row.get(key) if isinstance(row, dict) else getattr(row, key, None)


def day_of(row) -> date | None:  # noqa: ANN001
    """The day an open reminder is due, or None for a done one or one with no time."""
    due = _get(row, "due_at")
    if _get(row, "done") or not isinstance(due, datetime):
        return None
    return _naive(due).date()


def of(rows, now: datetime) -> Due:  # noqa: ANN001
    """The counts for `rows` (reminder objects or dicts) at `now`."""
    today = _naive(now).date()
    days = [d for r in rows if (d := day_of(r)) is not None]
    return Due(today=sum(d == today for d in days), overdue=sum(d < today for d in days), later=sum(d > today for d in days))


def say(due: Due) -> str:
    """"One due today, two overdue", or "" when neither."""
    parts = [f"{realise.count_word(n)} {what}" for n, what in ((due.today, "due today"), (due.overdue, "overdue")) if n]
    return ", ".join(parts).capitalize()
