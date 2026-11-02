"""The dashboard greeting without a model: the time of day, the day of the
week and the notebook itself (INBOX 876, the owner 2026-10-11: "can you add
more deterministic welcome messages?? mroe variety and ones for each time of
the day?? maybe the composer can spin something up based on usage patterns,
note content, and more??").

Every phrase is name-free and takes ", Name" after it ("Day 4 of your
streak" + ", Sam" + "."), as the model's do; the frontend adds the name.
The pick is seeded by the day and the hour, so a reload shows the same line
and the next hour a new one (the frontend caches it per hour).
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

#: Seven slots, not four: "Good evening" at 22:40 and "Still up" at 01:00
#: are different moments, and so are 06:00 and 10:30.
SLOTS = (
    (5, "small hours"),
    (8, "early morning"),
    (12, "morning"),
    (14, "midday"),
    (18, "afternoon"),
    (21, "evening"),
    (24, "late evening"),
)

PHRASES: dict[str, tuple[str, ...]] = {
    "small hours": ("Still up", "Working late", "Burning the midnight oil", "The quiet hours",
                    "A late one tonight", "Up past midnight", "Night owl hours", "While the world sleeps"),
    "early morning": ("Early start", "Up with the sun", "First light", "Before the rush",
                      "A fresh start", "An early one", "Good early morning", "The day is all yours"),
    "morning": ("Good morning", "Morning", "Rise and shine", "A fresh page",
                "Welcome back", "Ready for the day", "Hello again", "Bright and early"),
    "midday": ("Good afternoon", "Lunchtime already", "Halfway through the day", "A midday pause",
               "Hello there", "Midday check-in", "Taking a break"),
    "afternoon": ("Good afternoon", "Afternoon", "Hope today's going well", "Afternoon check-in",
                  "Still going strong", "The afternoon stretch", "Welcome back", "Good to see you"),
    "evening": ("Good evening", "Evening", "Winding down", "End of the day",
                "Evening check-in", "The day's nearly done", "Settling in for the evening", "Nice to see you"),
    "late evening": ("Getting late", "Late evening", "Before bed", "One more thought before bed",
                     "Nearly time to rest", "A quiet evening", "Last thoughts of the day"),
}

#: By weekday (Monday 0), and only in the slots where they read true.
WEEKDAY_PHRASES: dict[int, tuple[str, ...]] = {
    0: ("New week", "A fresh week ahead", "Monday again"),
    4: ("Nearly the weekend", "Friday at last", "Happy Friday"),
    5: ("Happy Saturday", "A slow Saturday", "Weekend thinking"),
    6: ("Happy Sunday", "A quiet Sunday", "Sunday thoughts"),
}
_WEEKDAY_SLOTS = {
    0: {"early morning", "morning", "midday"},
    4: {"afternoon", "evening"},
    5: {"early morning", "morning", "midday", "afternoon"},
    6: {"early morning", "morning", "midday", "afternoon"},
}

#: Categories too generic to greet anyone with.
_PLAIN_CATEGORIES = {"", "general", "inbox", "uncategorised", "uncategorized", "misc", "other", "notes"}


@dataclass(frozen=True)
class NotebookFacts:
    total: int = 0
    today: int = 0
    this_week: int = 0
    days_since_last: int | None = None
    streak: int = 0
    recent_category: str = ""


def slot_for(hour: int) -> str:
    for end, name in SLOTS:
        if hour < end:
            return name
    return SLOTS[-1][1]


def _context_phrases(facts: NotebookFacts, slot: str) -> list[tuple[str, str]]:
    """(phrase, mark) pairs the notebook makes true right now."""
    out: list[tuple[str, str]] = []
    if facts.total == 0:
        return [("A blank page awaits", "."), ("Your first note is waiting", ".")]
    if facts.days_since_last is not None and facts.days_since_last >= 3:
        out.append((f"It has been {facts.days_since_last} days since your last note", "."))
        out.append(("Good to have you back", "."))
    if facts.streak >= 3:
        out.append((f"Day {facts.streak} of your writing streak", "."))
    if facts.today >= 3:
        out.append(("Busy day so far", "."))
        #: The sub line under the greeting says how many; the headline must not.
        out.append(("A full page today", "."))
    elif facts.today >= 1:
        out.append(("Back for more", "."))
    #: A week is said of notes from more than today: a notebook made seconds
    #: ago with fourteen notes was "A productive week" (audit 1030 Y18).
    if facts.this_week >= 10 and facts.this_week - facts.today >= 3:
        out.append(("A productive week", "."))
    if facts.recent_category:
        out.append((f"{facts.recent_category} on your mind lately", "?"))
    if slot in {"small hours", "late evening"} and facts.today >= 1:
        out.append(("Burning the midnight oil again", "?") if slot == "small hours" else ("Still writing tonight", "?"))
    return out


def compose(now: datetime, facts: NotebookFacts) -> tuple[str, str]:
    """A greeting phrase (no name, no final mark) and its mark."""
    slot = slot_for(now.hour)
    rng = random.Random(f"{now.date().isoformat()}|{now.hour}")
    plain = [(p, ".") for p in PHRASES[slot]]
    weekday = now.weekday()
    if slot in _WEEKDAY_SLOTS.get(weekday, set()):
        plain += [(p, ".") for p in WEEKDAY_PHRASES[weekday]]
    context = _context_phrases(facts, slot)
    #: About half the time the notebook speaks, when it has something to say.
    if context and rng.random() < 0.5:
        return rng.choice(context)
    return rng.choice(plain)


def _naive(value):  # noqa: ANN001, ANN202
    """A stored instant as naive UTC, whichever way the column hands it back."""
    if value is None or value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _streak(days: set[int]) -> int:
    """Consecutive days with a note, counting back from today (or yesterday)."""
    streak = 0
    day = 0 if 0 in days else -1
    while day in days:
        streak += 1
        day -= 1
    return streak


def _recent_category(session, live, midnight: datetime) -> str:  # noqa: ANN001
    """The category written in most of the last fortnight, if it is a real topic."""
    from sqlalchemy import func, select

    from tessellate.core.database import Category, Entry

    recent = session.execute(
        select(Category.name, func.count(Entry.id))
        .join(Entry, Entry.category_id == Category.id)
        .where(*live, Entry.created_at >= midnight - timedelta(days=13))
        .group_by(Category.name)
        .order_by(func.count(Entry.id).desc())
        .limit(1)
    ).first()
    if not (recent and recent[1] >= 3 and str(recent[0]).strip().lower() not in _PLAIN_CATEGORIES):
        return ""
    name = str(recent[0]).strip()
    return name[:1].upper() + name[1:] if len(name.split()) <= 3 else ""


def gather(session, now: datetime) -> NotebookFacts:  # noqa: ANN001  # a Session
    """The few numbers `compose` reads, from the notes themselves (drafts and
    boards left out, as the dashboard's count does)."""
    from sqlalchemy import func, select

    from tessellate.core.database import Entry

    live = (Entry.is_deleted == False, Entry.is_draft == False, Entry.is_board == False)  # noqa: E712
    total = session.scalar(select(func.count(Entry.id)).where(*live)) or 0
    if not total:
        return NotebookFacts()
    #: Local midnight, as a naive UTC instant like the stored columns.
    offset = now.utcoffset() or timedelta(0)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0).replace(tzinfo=None) - offset
    since = midnight - timedelta(days=60)
    stamps = [_naive(s) for s in session.scalars(select(Entry.created_at).where(*live, Entry.created_at >= since)).all()]
    days = {(s - midnight).days for s in stamps if s is not None}
    today = sum(1 for s in stamps if s is not None and s >= midnight)
    week = sum(1 for s in stamps if s is not None and s >= midnight - timedelta(days=6))
    last = _naive(session.scalar(select(func.max(Entry.created_at)).where(*live)))
    days_since = None if last is None else max(0, (midnight - last).days + (0 if last >= midnight else 1))
    streak = _streak(days)
    category = _recent_category(session, live, midnight)
    return NotebookFacts(total=total, today=today, this_week=week, days_since_last=days_since,
                         streak=streak, recent_category=category)
