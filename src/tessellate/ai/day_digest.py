"""The day's digest the dashboard opens with (CHAT_PLAN section 2, the
dashboard row): what is due, the open questions, what changed since
yesterday and the topics gone quiet, composed by the engine with no model,
in the realiser's voice.

Every line is one of two kinds, and says which: a `count` (a number the
notebook's rows give, each listed in `counts`, and no other number) or a `quote` (words copied from one
note or one reminder, with where they came from). Nothing is summarised,
inferred or paraphrased, so a line can always be checked against its
source; `tests/test_day_digest.py` checks every one.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tessellate.ai import questions, realise
from tessellate.core.database import Category, Entry, Reminder

#: A topic is quiet when its newest note is older than this.
QUIET_DAYS = 30
#: A topic with fewer notes than this is not one anybody keeps up.
QUIET_MIN_NOTES = 3
#: Quoted lines per part, so the digest stays a glance.
QUOTES = 2
QUOTE_CHARS = 90


def _naive(moment: datetime) -> datetime:
    return moment.astimezone(timezone.utc).replace(tzinfo=None) if moment.tzinfo else moment


def _first_line(text: str) -> str:
    for line in (text or "").splitlines():
        line = line.strip().lstrip("#").strip()
        if line:
            return line
    return ""


def _cut(text: str) -> str:
    return realise.cut_title(text, QUOTE_CHARS)


_LISTED = (
    Entry.is_deleted == False,  # noqa: E712
    Entry.is_draft == False,  # noqa: E712
    Entry.is_board == False,  # noqa: E712
    Entry.is_private == False,  # noqa: E712
)


def _notes():
    return select(Entry).where(*_LISTED)


def _due(session: Session, now: datetime) -> list[dict]:
    end = _naive(datetime.combine(now.date(), time.max, tzinfo=now.tzinfo))
    start = _naive(datetime.combine(now.date(), time.min, tzinfo=now.tzinfo))
    rows = session.scalars(
        select(Reminder)
        .where(Reminder.done == False, Reminder.deleted_at.is_(None), Reminder.due_at <= end)  # noqa: E712
        .order_by(Reminder.due_at)
    ).all()
    if not rows:
        return []
    late = sum(1 for r in rows if _naive(r.due_at) < start)
    today = len(rows) - late
    parts = []
    if today:
        parts.append(f"{realise.count_noun(today, 'reminder')} due today")
    if late:
        parts.append(f"{realise.count_word(late)} overdue")
    lines = [{"part": "due", "kind": "count", "text": " and ".join(parts).capitalize() + ".",
              "counts": [n for n in (today, late) if n]}]
    lines.extend({"part": "due", "kind": "quote", "quote": _cut(row.text), "source": {"reminder_id": row.id},
                  "text": f"“{_cut(row.text)}”"} for row in rows[:QUOTES])
    return lines


def _questions(session: Session) -> list[dict]:
    page = questions.listing(session, state="open", limit=QUOTES)
    total = page["counts"]["open"]
    if not total:
        return []
    verb = "is" if total == 1 else "are"
    lines = [{"part": "questions", "kind": "count", "counts": [total],
              "text": f"{realise.count_noun(total, 'question').capitalize()} in your notes {verb} still open."}]
    for item in page["items"]:
        said = _cut(item["display"] or item["text"])
        lines.append({"part": "questions", "kind": "quote", "quote": said,
                      "source": {"entry_id": item["entry_id"], "question_id": item["id"]}, "text": f"“{said}”"})
    return lines


def _changed(session: Session, now: datetime) -> list[dict]:
    since = _naive(now) - timedelta(days=1)
    made = session.scalars(_notes().where(Entry.created_at >= since).order_by(Entry.created_at.desc())).all()
    edited = session.scalars(
        _notes().where(Entry.created_at < since, Entry.updated_at >= since).order_by(Entry.updated_at.desc())
    ).all()
    if not made and not edited:
        return []
    said = []
    if made:
        said.append(f"{realise.count_noun(len(made), 'note')} written")
    if edited:
        said.append(f"{realise.count_noun(len(edited), 'note')} edited")
    lines = [{"part": "changed", "kind": "count", "counts": [n for n in (len(made), len(edited)) if n],
              "text": (" and ".join(said) + " since this time yesterday.").capitalize()}]
    for entry in (made + edited)[:QUOTES]:
        head = _cut(_first_line(entry.content))
        if head:
            lines.append({"part": "changed", "kind": "quote", "quote": head, "source": {"entry_id": entry.id},
                          "text": f"“{head}”"})
    return lines


def _quiet(session: Session, now: datetime) -> list[dict]:
    newest = func.max(Entry.created_at)
    rows = session.execute(
        select(Category.name, func.count(Entry.id), newest)
        .select_from(Entry)
        .join(Category, Category.id == Entry.category_id)
        .where(*_LISTED)
        .group_by(Category.name)
        .having(func.count(Entry.id) >= QUIET_MIN_NOTES)
        .order_by(newest)
    ).all()
    lines = []
    for name, count, last in rows:
        days = (_naive(now).date() - _naive(last).date()).days
        if days < QUIET_DAYS:
            continue
        lines.append({"part": "quiet", "kind": "count", "counts": [days, count], "category": name,
                      "text": f"{name}: no new note in {realise.count_noun(days, 'day')} ({count} notes in all)."})
        if len(lines) >= QUOTES:
            break
    return lines


def compose(session: Session, now: datetime) -> dict:
    """The digest's lines in the order the widget shows them, and an
    empty-day line when there is nothing to say."""
    lines = _due(session, now) + _questions(session) + _changed(session, now) + _quiet(session, now)
    return {"lines": lines, "empty": "Nothing is due and nothing changed since yesterday." if not lines else ""}
