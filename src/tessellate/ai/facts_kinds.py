"""The fact kinds a rule reads exactly (L657): dates a note names, the entities it
mentions, and a note that says what another says word for word.

Claims and questions are guesses a model may narrow; these are not, so the night
pass stores them as read (`facts._derive_note`) and the learned-store check leaves
them alone (`facts.JUDGED_KINDS`). Each returns `(kind, text, start, end, confidence)`
so `facts.Candidate` stays in one place."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from tessellate.core.database import Entity, EntityMention, Entry

#: The kinds stored as read, never narrowed by a model.
EXACT_KINDS = ("date", "entity", "duplicate")
#: Per note: a long list of dates is a calendar, not a fact worth a row each.
MAX_PER_KIND = 4

Found = tuple[str, str, int, int, float]


def dates_in(content: str, written: datetime | None) -> list[Found]:
    """The calendar dates the note states, as written ("12 March", "2026-03-12")."""
    from tessellate.ai import recognise

    spans = recognise.recognise(content, now=written or datetime(2000, 1, 1, 12))
    out: list[Found] = [
        ("date", span.text.strip(), span.start, span.end, 0.8)
        for span in spans
        if span.kind == "date" and span.rank == 0 and isinstance(span.value, date) and span.text.strip()
    ]
    return out[:MAX_PER_KIND]


def entities_in(session: Session, entry_id: int, content: str) -> list[Found]:
    """The entities this note is a mention of, placed where the note names them."""
    low = content.casefold()
    out: list[Found] = []
    for name, aliases in session.execute(
        select(Entity.name, Entity.aliases).join(EntityMention, EntityMention.entity_id == Entity.id).where(EntityMention.entry_id == entry_id)
    ):
        for word in [name, *(aliases or [])]:
            at = low.find(str(word).casefold()) if word else -1
            if at >= 0:
                out.append(("entity", content[at:at + len(word)], at, at + len(word), 0.8))
                break
    return out[:MAX_PER_KIND]


def duplicate_of(session: Session, entry: Entry, content: str) -> list[Found]:
    """A note whose words are another live, non-private note's exactly: the
    later one says so, naming the earlier (the earlier is the original)."""
    if len(" ".join(content.split())) < 20:
        return []
    other = session.scalars(
        select(Entry.id).where(Entry.id < entry.id, Entry.is_deleted.is_(False), Entry.is_private.is_(False), Entry.content == entry.content).limit(1)
    ).first()
    return [("duplicate", f"Says the same as note {other}", 0, len(content), 0.95)] if other else []


def exact(session: Session, entry: Entry, content: str) -> list[Found]:
    """Everything above for one note."""
    return dates_in(content, entry.created_at) + entities_in(session, entry.id, content) + duplicate_of(session, entry, content)
