"""The rest of the slash commands (O6 rest; BACKLOG "Slash commands in Chat
and the composer": `/today`, `/due`, `/calc`, `/find`, `/stats`, `/orphans`,
`/random`, `/tags`, `/categories`, `/pinned`, `/oldest`, `/todo`).

Read by `slash.COMMANDS`, which pairs each function in `RUN` with its words
in `slash_table.TABLE`, so a command here reaches the route,
`GET /chat/commands`, `/help` and the "/" menu. Each answers with no model,
as a sentence and the rows `tool_say` draws for a tool's notes. The row
helpers (`_rows`, `_notes`, `_more`, `_tags_of`) live here, below `slash`, so
neither module imports the other.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import date, datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tessellate.ai import arithmetic, realise
from tessellate.ai.composer_frame import note_title

#: How many rows a command shows; the sentence says how many there are.
SHOWN = 8


def _rows(session: Session, entries: list) -> str:
    """The notes as `tool_say` draws a tool's notes: title linked, first
    line, category and tags."""
    from tessellate.ai import tool_say
    from tessellate.core.database import Category

    shown = entries[:SHOWN]
    ids = {e.category_id for e in shown if e.category_id}
    names = dict(session.execute(select(Category.id, Category.name).where(Category.id.in_(ids))).all()) if ids else {}
    return "\n".join(
        tool_say._note_row({"id": e.id, "content": e.content or "", "category": names.get(e.category_id), "tags": _tags_of(e.tags)})
        for e in shown
    )


def _notes():  # noqa: ANN202
    from tessellate.ai.tools._common import _visible
    from tessellate.core.database import Entry

    return Entry, _visible()


def _more(total: int) -> str:
    return f"\n\n{realise.count_word(total - SHOWN).capitalize()} more in Notes." if total > SHOWN else ""


def _tags_of(raw: str) -> list[str]:
    try:
        parsed = json.loads(raw or "[]")
    except (TypeError, ValueError):
        return []
    return [str(t).strip().lower() for t in parsed if str(t).strip()] if isinstance(parsed, list) else []


def count_arg(arg: str, default: int = 5, most: int = 20) -> int:
    """How many rows `arg` asks for, kept between 1 and `most`. ASCII digits
    only: `str.isdigit` is true for "²", which `int` refuses, and a number of
    thousands of digits is refused too."""
    typed = arg.strip()
    if not (typed.isascii() and typed.isdigit()):
        return default
    return max(1, min(int(typed) if len(typed) <= 6 else most, most))


#: Words `/find` reads; every one is a condition in the query, and SQLite
#: refuses an expression tree over 1,000 deep.
FIND_WORDS = 8


def _day(moment: datetime) -> str:
    """A day as "17 October", with no platform-only strftime flag."""
    return f"{moment.day} {moment:%B}"


#: An open checkbox line: "- [ ] call the dentist". Spaces and tabs only, never
#: `\s`: with `re.M` a `\s*` at each line start would read on through every
#: blank line below it, quadratic in a note of many (CodeQL py/polynomial-redos).
_OPEN_BOX = re.compile(r"^[ \t]*[-*][ \t]+\[ \][ \t]+(\S.*)$", re.M)


def _newest(session: Session, *conditions, order=None, limit: int = 200) -> list:  # noqa: ANN001
    entry, visible = _notes()
    ordered = order if order is not None else entry.created_at.desc()
    return list(session.scalars(select(entry).where(*visible, *conditions).order_by(ordered, entry.id.desc()).limit(limit)))


def _listed(session: Session, rows: list, one: str, many: str) -> str:
    """`rows` under a lead line: `one` for a single note, `many` (with its
    `{n}` as "Three notes") otherwise."""
    lead = one if len(rows) == 1 else many.format(n=realise.count_noun(len(rows), "note").capitalize())
    return f"{lead}\n\n{_rows(session, rows)}{_more(len(rows))}"


def _find(session: Session, arg: str, now: datetime) -> str:
    words = [w for w in re.findall(r"[\w'-]+", arg.lower()) if len(w) > 1 or w.isdigit()][:FIND_WORDS]
    if not words:
        return "Say what to find: /find golf, or /find dentist tuesday for notes that hold both words."
    entry, _ = _notes()
    said = " ".join(words)
    rows = _newest(session, *(func.lower(entry.content).contains(w, autoescape=True) for w in words))
    if not rows:
        return f"No note holds {'both ' if len(words) > 1 else ''}“{said}”."
    return _listed(session, rows, f"One note mentions “{said}”:", f"{{n}} mention “{said}”:")


def _pinned(session: Session, arg: str, now: datetime) -> str:
    entry, _ = _notes()
    rows = _newest(session, entry.pinned.is_(True))
    if not rows:
        return "No note is pinned. Say “pin the … note” to pin one."
    return _listed(session, rows, "One note is pinned:", "{n} are pinned:")


def _oldest(session: Session, arg: str, now: datetime) -> str:
    entry, _ = _notes()
    n = count_arg(arg)
    rows = _newest(session, order=entry.created_at.asc(), limit=n)
    if not rows:
        return "You have no notes yet."
    lead = "Your oldest note:" if len(rows) == 1 else f"Your {realise.count_word(len(rows))} oldest notes:"
    return f"{lead}\n\n{_rows(session, rows)}"


def _random(session: Session, arg: str, now: datetime) -> str:
    rows = _newest(session, limit=2000)
    if not rows:
        return "You have no notes yet."
    pick = rows[int(now.timestamp() * 1000) % len(rows)]
    return f"Here is one of your {len(rows)} notes, picked at random:\n\n{_rows(session, [pick])}"


#: The most points a strip carries, and the longest span it draws by the day
#: and by the week: past them it counts in months.
_STRIP_MOST, _STRIP_DAYS, _STRIP_WEEKS = 60, 31, 182


def _strip_day(d: date, today: date) -> str:
    return "Today" if d == today else f"{d.day} {d:%b}" + (f" {d.year}" if d.year != today.year else "")


def timeline_panel(session: Session, start: date, end: date, today: date) -> dict | None:
    """The small timeline strip a time answer carries (INBOX 1333 b): notes
    counted over `start` to `end`, a point a day, a week or a month by how
    long that is (one day: a point an hour), for the lazy reply kit's spark
    line (`replyTimelinePanel`). None when nothing was written in it or it is
    one point."""
    entry, visible = _notes()
    end = min(end, today)
    if start > end:
        return None
    stamps = [d for d in session.scalars(select(entry.created_at).where(
        *visible, entry.created_at >= datetime.combine(start, time.min), entry.created_at < datetime.combine(end + timedelta(days=1), time.min))) if d]
    if not stamps:
        return None
    span, first = (end - start).days + 1, start
    if span == 1:
        by, size, slot, labels = "hour", 24, (lambda d: d.hour), ("00:00", "23:00")
    elif span <= _STRIP_DAYS:
        by, size, slot = "day", span, (lambda d: (d.date() - start).days)
    elif span <= _STRIP_WEEKS:
        by, size, slot = "week", -(-span // 7), (lambda d: (d.date() - start).days // 7)
    else:
        month = lambda d: d.year * 12 + d.month - 1  # noqa: E731
        base = max(month(start), month(end) - _STRIP_MOST + 1)
        by, size, slot = "month", month(end) - base + 1, (lambda d: month(d) - base)
        first = start if base == month(start) else date(base // 12, base % 12 + 1, 1)
    points = [0] * size
    for stamp in stamps:
        if 0 <= slot(stamp) < size:
            points[slot(stamp)] += 1
    ends = labels if by == "hour" else (_strip_day(first, today), _strip_day(end, today))
    return {"type": "panel", "panel": "timeline", "by": by, "title": f"Notes per {by}", "points": points, "from": ends[0], "to": ends[1]}


def empty_timeline(session: Session, today: date) -> dict | None:
    """Where the notes run, for an answer that found none in the day or span
    asked: the strip from the first note to today."""
    entry, visible = _notes()
    first = session.scalar(select(func.min(entry.created_at)).where(*visible))
    return timeline_panel(session, first.date(), today, today) if first else None


def tag_counts(session: Session) -> Counter:
    """How many visible notes carry each tag."""
    entry, visible = _notes()
    return Counter(t for raw in session.scalars(select(entry.tags).where(*visible)) for t in _tags_of(raw))


def category_counts(session: Session) -> tuple[list, int]:
    """((name, notes) per category, most first; the notes filed nowhere)."""
    from tessellate.core.database import Category

    entry, visible = _notes()
    count = func.count(entry.id)
    rows = session.execute(
        select(Category.name, count).join(entry, entry.category_id == Category.id).where(*visible).group_by(Category.id).order_by(count.desc(), Category.name)
    ).all()
    return rows, session.scalar(select(count).where(*visible, entry.category_id.is_(None))) or 0


def _tags(session: Session, arg: str, now: datetime) -> str:
    counts = tag_counts(session)
    if not counts:
        return "No note has a tag yet."
    top = counts.most_common(15)
    said = ", ".join(f"#{tag} ({n})" for tag, n in top)
    more = f" and {len(counts) - len(top)} more" if len(counts) > len(top) else ""
    return f"You use {realise.count_noun(len(counts), 'tag')}, most used first: {said}{more}."


def _categories(session: Session, arg: str, now: datetime) -> str:
    rows, unfiled = category_counts(session)
    parts = [f"{name} ({n})" for name, n in rows] + ([f"not filed ({unfiled})"] if unfiled else [])
    if not parts:
        return "You have no notes yet."
    return f"Your notes sit in {realise.count_noun(len(rows), 'category')}: {', '.join(parts)}."


def _todo(session: Session, arg: str, now: datetime) -> str:
    from tessellate.ai import tool_say

    entry, _ = _notes()
    notes = _newest(session, entry.content.contains("[ ]"))
    found = [(e, m.group(1).strip()) for e in notes for m in _OPEN_BOX.finditer(e.content or "")]
    if not found:
        return "No note has an open checkbox."
    lines = [f"- {text} in {tool_say.link((note_title(e.content, size=60) or 'Untitled'), tool_say.note_at(e.id))}" for e, text in found[: SHOWN]]
    lead = "One open checkbox:" if len(found) == 1 else f"{realise.count_word(len(found)).capitalize()} open checkboxes:"
    return f"{lead}\n\n" + "\n".join(lines) + _more(len(found))


def _when(reminder, today) -> str:  # noqa: ANN001
    due = reminder.due_at
    if due.date() < today:
        return f"overdue since {_day(due)}"
    return f"{due:%A} {_day(due)}, {due:%H:%M}"


def _due(session: Session, arg: str, now: datetime) -> str:
    from tessellate.core.database import Reminder

    week = arg.strip().lower() in ("week", "this week", "7")
    end = datetime.combine(now.date() + timedelta(days=7 if week else 0), time.max)
    rows = list(session.scalars(select(Reminder).where(Reminder.done.is_(False), Reminder.due_at <= end).order_by(Reminder.due_at).limit(40)))
    span = "this week" if week else "today"
    if not rows:
        return f"No reminder is due {span} or overdue."
    lines = "\n".join(f"- {r.text} ({_when(r, now.date())})" for r in rows[: SHOWN])
    lead = f"One reminder is due {span} or overdue:" if len(rows) == 1 else f"{realise.count_noun(len(rows), 'reminder').capitalize()} are due {span} or overdue:"
    return f"{lead}\n\n{lines}{_more(len(rows))}"


def _calc(session: Session, arg: str, now: datetime) -> str:
    expression = arg.strip().rstrip("=?")
    if not expression:
        return "Give me a sum: /calc 12 * (3 + 4)."
    try:
        value = arithmetic.evaluate(expression)
    except arithmetic.NotArithmetic:
        #: What the Calculator dialog reads ("12% of 340", a unit, a currency):
        #: the one reader, so the chat does not refuse what the dialog does
        #: (audit 1030 A28).
        from tessellate.ai import tools

        got = tools.execute_tool(session, "calculate", {"question": expression[:300]})
        if got.get("answer"):
            return f"{expression} = {got['answer']}"
        return f"I can only work out sums with numbers, + - * / % ^ and brackets, so not “{expression}”."
    return f"{expression} = {arithmetic.spoken(value)}"


def _streak(days: set, today) -> int:  # noqa: ANN001
    """Days in a row up to today, or up to yesterday while today is empty."""
    day, run = (today if today in days else today - timedelta(days=1)), 0
    while day in days:
        run, day = run + 1, day - timedelta(days=1)
    return run


def _stats(session: Session, arg: str, now: datetime) -> str:
    entry, visible = _notes()
    rows = session.execute(select(entry.content, entry.created_at, entry.tags).where(*visible)).all()
    if not rows:
        return "You have no notes yet."
    words = sum(len((c or "").split()) for c, _, _ in rows)
    days = {d.date() for _, d, _ in rows}
    tags = {t for _, _, raw in rows for t in _tags_of(raw)}
    newest = max(d for _, d, _ in rows)
    run = _streak(days, now.date())
    said = f"You have {realise.count_noun(len(rows), 'note')} and {words:,} words, {realise.count_noun(len(tags), 'tag')}, written on {realise.count_noun(len(days), 'day')}. Your newest note is from {_day(newest)} {newest.year}"
    return said + (f", and you have written {realise.count_noun(run, 'day', article=True)} running." if run > 1 else ".")


def _orphans(session: Session, arg: str, now: datetime) -> str:
    from tessellate.core.database import EntryLink

    entry, _ = _notes()
    linked = set(session.scalars(select(EntryLink.source_entry_id))) | set(session.scalars(select(EntryLink.target_entry_id)))
    rows = _newest(session, entry.id.not_in(linked)) if linked else _newest(session)
    if not rows:
        return "Every note is linked to another."
    return _listed(session, rows, "One note links to nothing:", "{n} link to nothing:")


#: The functions that run each command here, by name (the words are in
#: `slash_table.TABLE`; `today` and `yesterday` are `slash`'s, which owns `made`).
RUN = {
    "find": _find,
    "pinned": _pinned,
    "oldest": _oldest,
    "random": _random,
    "tags": _tags,
    "categories": _categories,
    "todo": _todo,
    "due": _due,
    "calc": _calc,
    "stats": _stats,
    "orphans": _orphans,
}
