"""The fact kinds a rule reads exactly (L657): dates a note names, the entities it
mentions, and a note that says what another says word for word.

Claims and questions are guesses a model may narrow; these are not, so the night
pass stores them as read (`facts._derive_note`) and the learned-store check leaves
them alone (`facts.JUDGED_KINDS`). Each returns `(kind, text, start, end, confidence)`
so `facts.Candidate` stays in one place."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

from sqlalchemy import func, select
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


@dataclass
class Lookups:
    """What `entities_in` and `duplicate_of` read, fetched once for a whole pass:
    two queries per note was 107 statements over 45 notes (tests/test_derived_facts.py)."""

    #: entry id -> the (name, aliases) of every entity it mentions.
    mentions: dict[int, list[tuple[str, list[str]]]] = field(default_factory=dict)
    #: note text -> the first live, non-private note with exactly that text (only texts said twice).
    first_with: dict[str, int] = field(default_factory=dict)


#: Ids per IN (...) query, well under SQLite's bound-parameter limit.
_CHUNK = 500


def lookups(session: Session, entries: list[Entry]) -> Lookups:
    """Both reads for every note the pass will reach: one mention query per 500 notes, one duplicate query."""
    out = Lookups()
    entry_ids = [entry.id for entry in entries]
    for at in range(0, len(entry_ids), _CHUNK):
        chunk = entry_ids[at:at + _CHUNK]
        for entry_id, name, aliases in session.execute(
            select(EntityMention.entry_id, Entity.name, Entity.aliases)
            .join(Entity, EntityMention.entity_id == Entity.id)
            .where(EntityMention.entry_id.in_(chunk))
        ):
            out.mentions.setdefault(entry_id, []).append((name, aliases or []))
    live = (Entry.is_deleted.is_(False), Entry.is_private.is_(False))
    for first, content in session.execute(
        select(func.min(Entry.id), Entry.content).where(*live).group_by(Entry.content).having(func.count() > 1)
    ):
        out.first_with[content] = first
    return out


def entities_in(found: Lookups, entry_id: int, content: str) -> list[Found]:
    """The entities this note is a mention of, placed where the note names them."""
    low = content.casefold()
    out: list[Found] = []
    for name, aliases in found.mentions.get(entry_id, []):
        for word in [name, *aliases]:
            at = low.find(str(word).casefold()) if word else -1
            if at >= 0:
                out.append(("entity", content[at:at + len(word)], at, at + len(word), 0.8))
                break
    return out[:MAX_PER_KIND]


def duplicate_of(found: Lookups, entry: Entry, content: str) -> list[Found]:
    """A note whose words are another live, non-private note's exactly: the
    later one says so, naming the earlier (the earlier is the original)."""
    if len(" ".join(content.split())) < 20:
        return []
    other = found.first_with.get(entry.content or "")
    return [("duplicate", f"Says the same as note {other}", 0, len(content), 0.95)] if other and other < entry.id else []


def exact(found: Lookups, entry: Entry, content: str) -> list[Found]:
    """Everything above for one note."""
    return dates_in(content, entry.created_at) + entities_in(found, entry.id, content) + duplicate_of(found, entry, content)
