"""The graph's derived layers: stored note vectors, entity mentions and the
live note ids the similarity lines and the trace path are built over. Moved
out of `api/routes_graph.py` (router ORM cap, `tests/test_repo_boundaries.py`);
reads only, no flush."""

from __future__ import annotations

import json

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tessellate.core.database import EmbeddingRecord, Entity, EntityMention, Entry, NoteType, WhiteboardObject
from tessellate.repo import properties as properties_repo


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


def maps_of(session: Session) -> dict[int, list[int]]:
    # GRAPH_PLAN Phase 5: which mind maps a note is on, from the map nodes'
    # own data (a note node stores `ref_id`), one query for the whole
    # payload. `map_ids` is what "has a map" colours by and what the local
    # pane will list; it is here whether or not maps are drawn as nodes.
    maps_of: dict[int, list[int]] = {}
    for board_id, raw in session.execute(
        select(WhiteboardObject.board_id, WhiteboardObject.data).where(
            WhiteboardObject.kind == "note", WhiteboardObject.board_id.is_not(None)
        )
    ):
        try:
            ref_id = (json.loads(raw or "{}") or {}).get("ref_id")
        except (TypeError, ValueError):
            continue
        if isinstance(ref_id, int) and board_id is not None:
            maps_of.setdefault(ref_id, []).append(board_id)
    return maps_of


def note_types_of(session: Session, node_ids: set[int]) -> dict[int, str]:
    #: WORLD_CLASS_PLAN row 10 (D5): a note's type, for the "Note type" colour
    #: rule, read from the properties index KG4 keeps (one query, the `type`
    #: key's first value per note), never by parsing every note's block. A
    #: private note has no index rows, so it carries none.
    #: A note may spell its type in its own case ("type: book"); the node
    #: carries the type's own name when Note types has it, so "book" and
    #: "Book" are one colour and one legend row, not two.
    canonical: dict[str, str] = {}
    for name in session.scalars(select(NoteType.name)):
        canonical[name.casefold()] = name
    type_of: dict[int, str] = {}
    for entry_id, value in properties_repo.types(session):
        if entry_id in node_ids and value:
            type_of.setdefault(entry_id, canonical.get(value.casefold(), value))
    return type_of
