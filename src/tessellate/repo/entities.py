"""Entities: the reads behind an entity's page and list (`api/routes_entities.py`,
WORLD_CLASS B4). See `repo/__init__.py` for the rules every repository keeps.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tessellate.core.database import Entity, EntityMention, Entry, EntryDate


def visible_note_ids(session: Session) -> set[int]:
    return set(session.scalars(select(Entry.id).where(Entry.is_deleted.is_(False), Entry.is_private.is_(False))))


def find(session: Session, entity_id: int) -> Entity | None:
    return session.get(Entity, entity_id)


def named_with_counts(session: Session) -> list[tuple[Entity, int]]:
    """Every unmerged entity some visible note names, with how many notes
    name it, counted in SQL (audit 1028 K31)."""
    notes = func.count(func.distinct(EntityMention.entry_id))
    named = (
        select(Entity, notes)
        .join(EntityMention, EntityMention.entity_id == Entity.id)
        .join(Entry, Entry.id == EntityMention.entry_id)
        .where(Entity.merged_into.is_(None), Entry.is_deleted.is_(False), Entry.is_private.is_(False))
        .group_by(Entity.id)
    )
    return [(entity, count) for entity, count in session.execute(named)]


def note_ids_naming(session: Session, entity_id: int) -> list[int]:
    return list(session.scalars(select(EntityMention.entry_id).where(EntityMention.entity_id == entity_id)))


def entity_ids_in_note(session: Session, entry_id: int) -> set[int]:
    return set(session.scalars(select(EntityMention.entity_id).where(EntityMention.entry_id == entry_id)))


def mention_pairs(session: Session, note_ids: list[int]) -> list[tuple[int, int]]:
    """(entity id, note id) of every mention in these notes."""
    return [
        (a, b)
        for a, b in session.execute(
            select(EntityMention.entity_id, EntityMention.entry_id).where(EntityMention.entry_id.in_(note_ids))
        )
    ]


def by_ids(session: Session, ids: list[int]) -> dict[int, Entity]:
    return {e.id: e for e in session.scalars(select(Entity).where(Entity.id.in_(ids)))} if ids else {}


def notes_by_ids(session: Session, ids: list[int]) -> dict[int, Entry]:
    return {e.id: e for e in session.scalars(select(Entry).where(Entry.id.in_(ids)))} if ids else {}


def dates_in(session: Session, note_ids: list[int], limit: int) -> list[EntryDate]:
    if not note_ids:
        return []
    return list(
        session.scalars(select(EntryDate).where(EntryDate.entry_id.in_(note_ids)).order_by(EntryDate.at).limit(limit))
    )
