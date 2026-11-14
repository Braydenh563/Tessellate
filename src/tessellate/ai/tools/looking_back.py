"""Three reading tools the looking-back skills stand on (L-chat-51 to 53): `find_stale_notes`, `count_month_figures`
and `get_person_page`. Each reads only and hands the model numbers and note ids the app counted, so a skill
cites figures it did not work out itself. Private notes and binned notes are never counted or listed."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tessellate.ai.tools._common import ToolError, ToolSpec
from tessellate.ai.tools.tool_read import _named
from tessellate.core import config as core_config
from tessellate.core import deps
from tessellate.core.database import Entity, EntityMention, Entry, EntryLink, Reminder

MAX_ROWS = 40


def _visible():  # noqa: ANN202
    return (Entry.is_deleted.is_(False), Entry.is_private.is_(False), Entry.is_board.is_(False))


def _today() -> date:
    return core_config.user_now(deps.get_config()).date()


def _last_touched(entry: Entry) -> datetime:
    """The latest of written, edited and opened: a note read last week is not stale."""
    return max(t for t in (entry.created_at, entry.edited_at, entry.last_opened_at) if t is not None)


def _stale_notes(session: Session, args: dict) -> dict:
    try:
        days = int(args.get("days"))
    except (TypeError, ValueError) as exc:
        raise ToolError("Give days as a number, for example 90") from exc
    if days < 1:
        raise ToolError("Give days as a number of at least 1")
    cutoff = datetime.combine(_today(), datetime.min.time()) - timedelta(days=days)
    rows = [e for e in session.scalars(select(Entry).where(*_visible(), Entry.archived_at.is_(None), Entry.pinned.is_(False))) if _last_touched(e).replace(tzinfo=None) < cutoff]
    rows.sort(key=_last_touched)
    shown = rows[: int(args.get("limit") or MAX_ROWS)]
    notes = [{"id": e.id, "title": _named(e).strip("“”"), "last_touched": _last_touched(e).date().isoformat()} for e in shown]
    return {
        "days": days, "total_stale": len(rows), "returned": len(notes), "notes": notes,
        "note_to_model": "Favourites are left out. Archive only the notes the person ticks.",
        "label": f"ph:archive Found {len(rows)} note{'' if len(rows) == 1 else 's'} untouched for {days} days",
    }


def _month_window(said: str, today: date) -> tuple[date, date, str]:
    from tessellate.ai import library_acts

    got = library_acts.span(said or "last month", today)
    if got is None:
        raise ToolError(f"I could not read “{said}” as a month. Try: March, last month, this month.")
    return got


def _spent(session: Session, said: str, today: date) -> dict:
    """What the notes record as spent in the window, from the composer's own sum, with the notes it came from."""
    from tessellate.ai import composer

    notes = [{"id": e.id, "content": e.content or "", "created_at": e.created_at} for e in session.scalars(select(Entry).where(*_visible(), Entry.archived_at.is_(None)))]
    got = composer.compose(f"how much have I spent {said}", notes, today=today)
    cited = sorted({int(g["note_id"]) for g in got.get("grounding") or [] if isinstance(g, dict) and g.get("note_id")})
    return {"text": str(got.get("text") or "") if cited else "", "source_notes": cited}


def _month_figures(session: Session, args: dict) -> dict:
    today = _today()
    start, end, said = _month_window(str(args.get("month") or ""), today)
    lo, hi = datetime.combine(start, datetime.min.time()), datetime.combine(end, datetime.min.time())
    written = list(session.scalars(select(Entry).where(*_visible(), Entry.created_at >= lo, Entry.created_at < hi)))
    done = list(session.scalars(select(Reminder).where(Reminder.done.is_(True), Reminder.done_at >= lo, Reminder.done_at < hi, Reminder.deleted_at.is_(None))))
    open_due = session.scalar(select(func.count(Reminder.id)).where(Reminder.done.is_(False), Reminder.deleted_at.is_(None), Reminder.due_at >= lo, Reminder.due_at < hi)) or 0
    spent = _spent(session, f"in {said}" if not said.startswith(("this", "last", "the")) else said, today)
    return {
        "period": said, "from": start.isoformat(), "to": (end - timedelta(days=1)).isoformat(),
        "notes_written": len(written), "written_ids": [e.id for e in written[:MAX_ROWS]],
        "reminders_finished": len(done), "finished": [{"id": r.id, "text": r.text} for r in done[:MAX_ROWS]],
        "reminders_still_open_from_then": open_due,
        "spent": spent,
        "note_to_model": "Cite each number as it is here, with the note ids. Say plainly when spent is empty: no spending was recorded.",
        "label": f"ph:calendar Counted {said}: {len(written)} written, {len(done)} finished",
    }


def _find_person(session: Session, name: str) -> Entity:
    wanted = re.sub(r"\s+", " ", name).strip().casefold()
    if not wanted:
        raise ToolError("Say whose page to read")
    for entity in session.scalars(select(Entity).where(Entity.merged_into.is_(None))):
        if wanted in {entity.name.casefold(), *(a.casefold() for a in entity.aliases or [])}:
            return entity
    raise ToolError(f"No one called “{name}” is in the notebook yet. Search the notes instead.")


def _linked_to(session: Session, ids: set[int]) -> list[Entry]:
    """The notes joined by a link to any of `ids`, not among them."""
    if not ids:
        return []
    links = session.scalars(select(EntryLink).where(EntryLink.source_entry_id.in_(ids) | EntryLink.target_entry_id.in_(ids)))
    near = {i for link in links for i in (link.source_entry_id, link.target_entry_id)} - ids
    return list(session.scalars(select(Entry).where(Entry.id.in_(near), *_visible()))) if near else []


def _naming(session: Session, entity: Entity, note_ids: set[int]) -> list[Reminder]:
    """Open reminders attached to one of the notes or naming the person in their own words."""
    names = sorted([entity.name, *(entity.aliases or [])], key=len, reverse=True)
    pattern = re.compile("|".join(re.escape(n) for n in names), re.I)
    open_ones = session.scalars(select(Reminder).where(Reminder.done.is_(False), Reminder.deleted_at.is_(None)).order_by(Reminder.due_at))
    return [r for r in open_ones if r.entry_id in note_ids or pattern.search(r.text or "")]


def _person_page(session: Session, args: dict) -> dict:
    entity = _find_person(session, str(args.get("name") or ""))
    ids = set(session.scalars(select(EntityMention.entry_id).where(EntityMention.entity_id == entity.id)))
    mentioned = list(session.scalars(select(Entry).where(Entry.id.in_(ids), *_visible()))) if ids else []
    mentioned.sort(key=lambda e: e.created_at, reverse=True)
    linked = _linked_to(session, ids)
    reminders = _naming(session, entity, {e.id for e in mentioned})
    title = lambda e: _named(e).strip("“”")  # noqa: E731
    return {
        "name": entity.name, "kind": entity.kind, "aliases": list(entity.aliases or []),
        "mentioned_in": [{"id": e.id, "title": title(e), "written": e.created_at.date().isoformat()} for e in mentioned[:MAX_ROWS]], "mentioned_total": len(mentioned),
        "linked_notes": [{"id": e.id, "title": title(e)} for e in linked[:MAX_ROWS]],
        "open_reminders": [{"id": r.id, "text": r.text, "due_at": r.due_at.isoformat()} for r in reminders[:MAX_ROWS]],
        "label": f"ph:user Read what the notes hold about {entity.name}: {len(mentioned)} note{'' if len(mentioned) == 1 else 's'}",
    }


_DAYS = {"type": "integer", "description": "Untouched for at least this many days, e.g. 90 for three months"}
LOOKBACK_SPECS = (
    ToolSpec("find_stale_notes", "Notes not written, edited or opened for a span, oldest first. Favourites and archived notes are left out.",
             {"type": "object", "properties": {"days": _DAYS, "limit": {"type": "integer", "description": f"Most notes to list (default {MAX_ROWS})"}}, "required": ["days"]}, _stale_notes),
    ToolSpec("count_month_figures", "A month in numbers: notes written, reminders done, spending, with note ids.",
             {"type": "object", "properties": {"month": {"type": "string", "description": "March, March 2025, last month or this month (default last month)"}}, "required": []}, _month_figures),
    ToolSpec("get_person_page", "What the notes hold about one person, with linked notes and reminders.",
             {"type": "object", "properties": {"name": {"type": "string", "description": "The person's name, as in the notes"}}, "required": ["name"]}, _person_page),
)
