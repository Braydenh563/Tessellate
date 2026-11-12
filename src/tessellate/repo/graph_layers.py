"""The graph's derived layers: stored note vectors, entity mentions and the
live note ids the similarity lines and the trace path are built over. Moved
out of `api/routes_graph.py` (router ORM cap, `tests/test_repo_boundaries.py`);
reads only, no flush."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tessellate.core.database import EmbeddingRecord, Entity, EntityMention, Entry


def live_note_ids(session: Session) -> set[int]:
    """Every note not in the bin."""
    return set(session.scalars(select(Entry.id).where(Entry.is_deleted == False)))  # noqa: E712


def vector_note_ids(session: Session) -> set[int]:
    """The notes a similarity line means something for: live, not a draft,
    not a board, not private."""
    return set(
        session.scalars(
            select(Entry.id).where(
                Entry.is_deleted == False,  # noqa: E712
                Entry.is_draft == False,  # noqa: E712
                Entry.is_board == False,  # noqa: E712
                Entry.is_private == False,  # noqa: E712
            )
        )
    )


def vectors_for(session: Session, backend: str) -> list[EmbeddingRecord]:
    """The stored vectors made by one embedding backend."""
    return list(session.scalars(select(EmbeddingRecord).where(EmbeddingRecord.model_version == backend)))


def mention_pairs(session: Session) -> list[tuple[int, int]]:
    """(entity id, note id) for every mention."""
    return list(session.execute(select(EntityMention.entity_id, EntityMention.entry_id)))


def mention_fingerprint(session: Session) -> tuple:
    """What moves when a mention is added or removed."""
    return (
        session.scalar(select(func.count(EntityMention.id))) or 0,
        session.scalar(select(func.max(EntityMention.id))),
        session.scalar(select(func.sum(EntityMention.id))),
    )


def entity_name(session: Session, entity_id: int) -> str | None:
    """An entity's name, for a stop on a graph route."""
    row = session.get(Entity, entity_id)
    return row.name if row is not None else None
