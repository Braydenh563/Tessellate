"""The graph's derived layers: stored note vectors, entity mentions and the
live note ids the similarity lines and the trace path are built over. Moved
out of `api/routes_graph.py` (router ORM cap, `tests/test_repo_boundaries.py`);
reads only, no flush."""

from __future__ import annotations

import json

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tessellate.core.database import (
    Attachment,
    EmbeddingRecord,
    Entity,
    EntityMention,
    Entry,
    NoteType,
    WhiteboardObject,
)
from tessellate.entry import manager
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


def embedding_fingerprint(session: Session, backend: str) -> tuple:
    """What moves when a stored vector changes (review 5883476033): a note's
    vector is rewritten as a new row (`_write_vector` deletes, then inserts),
    so a re-embed moves the newest id even when no note was edited."""
    mine = EmbeddingRecord.model_version == backend
    return (
        session.scalar(select(func.count(EmbeddingRecord.id)).where(mine)) or 0,
        session.scalar(select(func.max(EmbeddingRecord.id)).where(mine)),
        session.scalar(select(func.max(EmbeddingRecord.created_at)).where(mine)),
    )


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


def embedding_coverage(session: Session) -> tuple[int, int]:
    """(live notes with a stored vector, live notes): how many search by
    meaning can find. Drafts and binned notes count in neither."""
    live = (Entry.is_deleted == False) & (Entry.is_draft == False)  # noqa: E712
    total = session.scalar(select(func.count(Entry.id)).where(live)) or 0
    indexed = session.scalar(
        select(func.count(EmbeddingRecord.id)).join(Entry, Entry.id == EmbeddingRecord.entry_id).where(live)
    ) or 0
    return int(indexed), int(total)


#: What `/graph` reads of a note: the node's fields, the label's text, and what
#: the opt-in layers need (a board's settings, a vault file's path).
GRAPH_COLUMNS = (
    Entry.id,
    Entry.content,
    Entry.tags,
    Entry.workspace_id,
    Entry.category_id,
    Entry.created_at,
    Entry.updated_at,
    Entry.edited_at,
    Entry.access_count,
    Entry.pinned,
    Entry.graph_pin_x,
    Entry.graph_pin_y,
    Entry.parent_id,
    Entry.is_board,
    Entry.is_private,
    Entry.board_settings,
    Entry.source_path,
)

_FINGERPRINT_COLUMNS = (
    Entry.id, Entry.updated_at, Entry.access_count, Entry.pinned, Entry.graph_pin_x,
    Entry.graph_pin_y, Entry.category_id, Entry.tags, Entry.is_private, Entry.workspace_id,
    Entry.parent_id, Entry.is_board, Entry.board_settings, Entry.source_path, Entry.created_at,
)


def live_count_and_newest(session: Session) -> tuple[int, object]:
    """(how many notes are not in the bin, the newest edit among them)."""
    live = Entry.is_deleted == False  # noqa: E712
    return (
        session.scalar(select(func.count(Entry.id)).where(live)) or 0,
        session.scalar(select(func.max(Entry.updated_at)).where(live)),
    )


def similarity_note_ids(session: Session, boards: bool) -> set[int]:
    """Live, non-draft notes; boards too when `boards`."""
    return set(
        session.scalars(
            select(Entry.id).where(
                Entry.is_deleted == False,  # noqa: E712
                Entry.is_draft == False,  # noqa: E712
                *(() if boards else (Entry.is_board == False,)),  # noqa: E712
            )
        )
    )


def mentions_in(session: Session, node_ids) -> list:  # noqa: ANN001
    """(entity_id, entry_id) rows for mentions inside these notes."""
    return list(
        session.execute(
            select(EntityMention.entity_id, EntityMention.entry_id).where(EntityMention.entry_id.in_(node_ids))
        )
    )


def entities_by_id(session: Session, entity_ids) -> dict[int, Entity]:  # noqa: ANN001
    return {e.id: e for e in session.scalars(select(Entity).where(Entity.id.in_(entity_ids)))}


def map_note_rows(session: Session, maps) -> list:  # noqa: ANN001
    """(board_id, data) for the note objects on these maps."""
    return list(
        session.execute(
            select(WhiteboardObject.board_id, WhiteboardObject.data).where(
                WhiteboardObject.board_id.in_(maps),
                WhiteboardObject.kind == "note",
            )
        )
    )


def wiki_sources(session: Session) -> list:
    """(content, source_path) of every live, non-private note."""
    return session.execute(
        select(Entry.content, Entry.source_path).where(
            Entry.is_deleted == False, Entry.is_private == False  # noqa: E712
        )
    ).all()


def attachments_on(session: Session, node_ids, limit: int) -> list[Attachment]:
    """The newest attachments on these notes, capped."""
    return list(
        session.scalars(
            select(Attachment)
            .where(Attachment.entry_id.in_(node_ids))
            .order_by(Attachment.created_at.desc())
            .limit(limit)
        )
    )


def attached_note_ids(session: Session) -> set[int]:
    """Notes that carry at least one file."""
    return set(session.scalars(select(Attachment.entry_id).distinct()))


def fingerprint_notes(session: Session):
    """The columns of every live, non-draft note the payload reads, by id."""
    return session.execute(
        select(*_FINGERPRINT_COLUMNS)
        .where(Entry.is_deleted == False, Entry.is_draft == False)  # noqa: E712
        .order_by(Entry.id)
    )


def fingerprint_attachments(session: Session):
    return session.execute(select(Attachment.entry_id).distinct().order_by(Attachment.entry_id))


def fingerprint_map_objects(session: Session):
    return session.execute(
        select(WhiteboardObject.id, WhiteboardObject.board_id, WhiteboardObject.data)
        .where(WhiteboardObject.kind == "note")
        .order_by(WhiteboardObject.id)
    )


def fingerprint_embeddings(session: Session):
    return session.execute(select(func.count(EmbeddingRecord.id), func.max(EmbeddingRecord.created_at)))


def fingerprint_note_types(session: Session):
    return session.execute(select(NoteType.id, NoteType.name, NoteType.colour).order_by(NoteType.id))


def graph_note_rows(session: Session) -> list:
    """The notes `/graph` draws, as column rows (not whole objects)."""
    return list(session.execute(manager.note_filter(select(*GRAPH_COLUMNS), boards=manager.BOARDS_INCLUDE)))


def type_colours(session: Session) -> dict[str, str]:
    """Each note type's own colour, by name, for those that have one."""
    return {row.name: row.colour for row in session.scalars(select(NoteType)) if row.colour}


def live_by_ids_chunked(session: Session, ids) -> dict[int, Entry]:  # noqa: ANN001
    """The live notes with these ids, read in chunks (SQLite's variable cap)."""
    wanted = list(ids)
    found: dict[int, Entry] = {}
    for start in range(0, len(wanted), 500):
        rows = session.scalars(
            select(Entry).where(Entry.id.in_(wanted[start : start + 500]), Entry.is_deleted == False)  # noqa: E712
        )
        found.update((e.id, e) for e in rows)
    return found


def live_entries_by_ids(session: Session, ids) -> list[Entry]:  # noqa: ANN001
    return list(session.scalars(select(Entry).where(Entry.id.in_(ids), Entry.is_deleted.is_(False))))


def entity_name_mentions(session: Session, entity_ids=None) -> list:  # noqa: ANN001
    """(entity name, entry id) per mention, all or for these entities."""
    stmt = select(Entity.name, EntityMention.entry_id).join(Entity, Entity.id == EntityMention.entity_id)
    if entity_ids is not None:
        stmt = stmt.where(EntityMention.entity_id.in_(entity_ids))
    return list(session.execute(stmt))


def entity_ids_in(session: Session, note_ids) -> set[int]:  # noqa: ANN001
    return set(session.scalars(select(EntityMention.entity_id).where(EntityMention.entry_id.in_(note_ids))))


def pin_targets(session: Session, ids) -> list[Entry]:  # noqa: ANN001
    """Live notes among these ids, whole, for a pin write."""
    return session.query(Entry).filter(Entry.id.in_(ids), Entry.is_deleted == False).all()  # noqa: E712


def pinned_notes(session: Session) -> list[Entry]:
    return session.query(Entry).filter(Entry.is_deleted == False, Entry.graph_pin_x.is_not(None)).all()  # noqa: E712


def texts_of(session: Session, ids) -> dict[int, str]:  # noqa: ANN001
    return dict(session.execute(select(Entry.id, Entry.content).where(Entry.id.in_(ids))).all())
