"""The week's and the day's review, said once (composer audit 2, G4).

"Weekly review", "how was my week", "summarise my week", "daily review" and
the dashboard's Digest with no model are one writer: `composer_voice.week_review`
for what was written (by subject, not by event), then the reminders. Reminders
made are a count, never a list; overdue and next are titles with their days.
Every clause is a count or a title, so it can be checked by opening it."""

from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from tessellate.ai import activity, composer_voice, notebook_stats, realise
from tessellate.ai.review_words import kind  # noqa: F401  (the review words live in a leaf the Guide also reads)

def _notes(session: Session, start: date, zone) -> list[dict]:  # noqa: ANN001
    """Notes made from `start` on the person's clock; no private note, board,
    map topic or draft."""
    from tessellate.core.database import Category, Entry

    lo = datetime.combine(start, time(0))
    rows = session.execute(
        select(Entry.id, Entry.content, Entry.created_at, Category.name)
        .select_from(Entry)
        .outerjoin(Category, Category.id == Entry.category_id)
        .where(Entry.is_deleted == False, Entry.is_private == False, Entry.is_board == False,  # noqa: E712
               Entry.map_topic == False, Entry.is_draft == False,  # noqa: E712
               Entry.created_at >= lo - timedelta(days=1))
        .order_by(Entry.created_at)
    ).all()
    out = []
    for ident, content, made, category in rows:
        local = activity._local(made, zone)
        if local is not None and local >= lo:
            out.append({"id": ident, "content": content or "", "created_at": local.isoformat(), "category": category or ""})
    return out


#: What a reminder's words keep when the parser lifts its date out ("when I get
#: home , probably around"): words that only lead into a date.
_DATE_STUB = re.compile(r"(?<![\s,;:])(?:[\s,;:]+(?:probably|maybe|perhaps|around|about|at|on|by|before|for|until|till))+[\s,;:.]*$", re.I)


def _reminder_words(text: str) -> str:
    """A reminder's text as the digest says it: no space before a comma and no
    dangling lead-in to a date that is said beside it."""
    words = re.sub(r"\s+([,.;:!?])", r"\1", realise.cut_title(text or "", 80))
    return _DATE_STUB.sub("", words).rstrip(" ,;:") or words


#: Titles named in one line before "and N more".
_NAMED = 3


def _listed(names: list[str]) -> str:
    more = len(names) - _NAMED
    return ", ".join(names[:_NAMED]) + (f" and {activity._n(more)} more" if more > 0 else "")


def _named(rows: list, today: date, zone) -> str:  # noqa: ANN001
    """Reminder titles with the day each falls on, "today" and "tomorrow" said so."""
    said = []
    for r in rows[:_NAMED]:
        due = activity._local(r.due_at, zone).date()
        when = "today" if due == today else "tomorrow" if due == today + timedelta(days=1) else activity._say_day(due, today)
        said.append(f"{_reminder_words(r.text)} (due {when})")
    more = len(rows) - len(said)
    return "; ".join(said) + (f"; and {activity._n(more)} more" if more > 0 else "") + "."


def _reminders(session: Session) -> list:
    from tessellate.core.database import Reminder

    return list(session.scalars(select(Reminder).where(Reminder.deleted_at.is_(None)).order_by(Reminder.due_at)))


def _unlinked(session: Session) -> set[int]:
    from tessellate.entry import paths

    try:
        return set(paths.orphans(paths.build(session, include_private=False)))
    except Exception:  # noqa: BLE001  # the review stays, without the loose-notes line
        return set()


def _counts(rows: list, start: date, today: date, zone) -> str:  # noqa: ANN001
    """"Reminders: 4 made, 1 done." as counts, or "" when neither."""
    local = activity._local
    made = sum(1 for r in rows if (m := local(r.created_at, zone)) and start <= m.date() <= today)
    done = sum(1 for r in rows if r.done and (d := local(r.done_at, zone)) and start <= d.date() <= today)
    bits = ([f"{made} made"] if made else []) + ([f"{done} done"] if done else [])
    return "Reminders: " + ", ".join(bits) + "." if bits else ""


def _reminder_lines(rows: list, start: date, today: date, zone, *, ahead: int) -> list[str]:  # noqa: ANN001
    """Made and done as counts; overdue and next as titles with their days."""
    due = lambda r: activity._local(r.due_at, zone).date()  # noqa: E731
    open_ = [r for r in rows if not r.done]
    late = [r for r in open_ if due(r) < today]
    coming = [r for r in open_ if today <= due(r) <= today + timedelta(days=ahead)]
    return [
        line
        for line in (
            _counts(rows, start, today, zone),
            f"Overdue: {_named(late, today, zone)}" if late else "",
            f"Next: {_named(coming, today, zone)}" if coming else "",
        )
        if line
    ]


def week(session: Session, now: datetime) -> str:
    """The seven days to today as a review."""
    today, zone = now.date(), now.tzinfo or timezone.utc
    start = today - timedelta(days=6)
    notes = _notes(session, start, zone)
    paras = [composer_voice.week_review(notes, today=today, unlinked=_unlinked(session))["text"].strip()] if notes else []
    tail = _reminder_lines(_reminders(session), start, today, zone, ahead=7)
    if not paras and not tail:
        return "Nothing was written or finished in the last seven days."
    if not paras:
        paras.append("No notes were written in the last seven days.")
    return "\n\n".join(paras + (["\n".join(tail)] if tail else []))


def span(session: Session, start: date, end: date, now: datetime) -> tuple[str, list[dict]]:
    """The days from `start` to `end` as a review, and the notes in them,
    oldest first (L-timeline-2: a span brushed on the timeline's strip)."""
    zone = now.tzinfo or timezone.utc
    notes = [n for n in _notes(session, start, zone) if n["created_at"][:10] <= end.isoformat()]
    said = composer_voice.span_review(notes, start=start, end=end, today=now.date(), unlinked=_unlinked(session))
    return said["text"].strip(), notes


def day(session: Session, now: datetime) -> str:
    """Today: what was written, what was ticked, what is due tonight and tomorrow."""
    today, zone = now.date(), now.tzinfo or timezone.utc
    notes = _notes(session, today, zone)
    rows = _reminders(session)
    if notes:
        names = [activity._link("note", n["id"], activity._note_name(n["content"])) for n in notes]
        parts = [f"You wrote {activity._n(len(notes))} {'note' if len(notes) == 1 else 'notes'} today: {_listed(names)}."]
    else:
        parts = ["You have not written a note today."]
    done = [r for r in rows if r.done and (d := activity._local(r.done_at, zone)) and d.date() == today]
    if done:
        parts.append(f"Done today: {_listed([_reminder_words(r.text) for r in done])}.")
    tail = _reminder_lines([r for r in rows if not r.done], today, today, zone, ahead=1)
    return "\n\n".join(parts + (["\n".join(tail)] if tail else []))


def reminder_note(session: Session, now: datetime) -> str:
    """The week's reminder lines as a sentence for the model's digest prompt,
    so its prose has what the composed review says; "" when there are none."""
    today, zone = now.date(), now.tzinfo or timezone.utc
    lines = _reminder_lines(_reminders(session), today - timedelta(days=6), today, zone, ahead=7)
    return " Reminders, say the overdue ones briefly: " + " ".join(lines) if lines else ""


def answer(question: str, session: Session, now: datetime) -> notebook_stats.StatAnswer | None:
    """The review a question asks for, or None for any other question."""
    from tessellate.ai import question_noise

    asked = kind(question_noise.repair(question_noise.tidy(question or "")))
    if asked is None:
        return None
    return notebook_stats.StatAnswer(kind="activity", text=(week if asked == "week" else day)(session, now), facts=[])
