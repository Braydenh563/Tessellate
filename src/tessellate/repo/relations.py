"""Links between notes (`EntryLink`): the stored connections the graph, the
backlinks, the suggestions and the export read.

The sixth resource behind a repository (INBOX 1499); the rules every
repository keeps are in `repo/__init__.py`. These are reads, and the only
lookup by id; the verbs that make or change a link (`create_link`,
`set_link_type`, `delete_link`) stay in `entry/manager.py` with the rules that
keep both ends honest. The workspace floor is the session's, as for every
model; a caller that must leave out a binned or private end filters the ends
it reads, which a link row alone cannot say (`count_live` is the one that
does, for the diagnostics count).
"""

from __future__ import annotations

from sqlalchemy import Row, func, or_, select
from sqlalchemy.orm import Session, aliased

from tessellate.core.database import Entry, EntryLink
from tessellate.repo import NotFound

MISSING = "That link could not be found."

#: What the graph and its cache fingerprint read of a link, never the row.
_GRAPH_FIELDS = (
    EntryLink.id,
    EntryLink.source_entry_id,
    EntryLink.target_entry_id,
    EntryLink.reason,
    EntryLink.reason_confidence,
    EntryLink.link_type,
    EntryLink.two_way,
)


def find(session: Session, link_id: int) -> EntryLink | None:
    return session.get(EntryLink, link_id)


def get_for_note(session: Session, entry_id: int, link_id: int) -> EntryLink:
    """The link, only if it runs to or from this note, else `NotFound`: a link
    id from another note's card answers the same as one that never existed."""
    link = find(session, link_id)
    if link is None or entry_id not in (link.source_entry_id, link.target_entry_id):
        raise NotFound(MISSING)
    return link


def pairs(session: Session) -> list[tuple[int, int]]:
    """Every link as (source id, target id), in no promised order."""
    return [(a, b) for a, b in session.execute(select(EntryLink.source_entry_id, EntryLink.target_entry_id))]


def touching(session: Session, entry_id: int) -> list[EntryLink]:
    """The links that start or end at this note, oldest first."""
    return list(
        session.scalars(
            select(EntryLink)
            .where(or_(EntryLink.source_entry_id == entry_id, EntryLink.target_entry_id == entry_id))
            .order_by(EntryLink.id)
        )
    )


def with_type(session: Session, link_type: str) -> list[EntryLink]:
    return list(session.scalars(select(EntryLink).where(EntryLink.link_type == link_type)))


def untyped(session: Session, *, limit: int) -> list[EntryLink]:
    """The newest links nobody has given a kind, for the type suggestions."""
    return list(
        session.scalars(select(EntryLink).where(EntryLink.link_type.is_(None)).order_by(EntryLink.id.desc()).limit(limit))
    )


def among(session: Session, ids: list[int]) -> list[tuple[int, int, str | None]]:
    """(source, target, reason) of every link with both ends in `ids`."""
    if not ids:
        return []
    rows = session.query(EntryLink.source_entry_id, EntryLink.target_entry_id, EntryLink.reason).filter(
        EntryLink.source_entry_id.in_(ids), EntryLink.target_entry_id.in_(ids)
    )
    return [(a, b, reason) for a, b, reason in rows]


def touching_any(session: Session, ids: set[int]) -> list[tuple[int, int]]:
    """(source, target) of every link with an end in `ids`, newest first."""
    return [
        (a, b)
        for a, b in session.execute(
            select(EntryLink.source_entry_id, EntryLink.target_entry_id)
            .where(or_(EntryLink.source_entry_id.in_(ids), EntryLink.target_entry_id.in_(ids)))
            .order_by(EntryLink.id.desc())
        ).all()
    ]


def wiki_sources(session: Session, target_id: int) -> list[int]:
    """The notes whose stored `[[wiki]]` link lands on this one, whatever the
    link text said (a prefix of the name resolves too)."""
    return list(
        session.scalars(
            select(EntryLink.source_entry_id).where(
                EntryLink.target_entry_id == target_id, EntryLink.origin == "wiki"
            )
        )
    )


def columns(session: Session, *, ordered: bool = False) -> list[Row]:
    """The graph's fields of every link (`id`, ends, `reason`,
    `reason_confidence`, `link_type`, `two_way`); by id when `ordered`."""
    query = select(*_GRAPH_FIELDS)
    if ordered:
        query = query.order_by(EntryLink.id)
    return list(session.execute(query))


def all_rows(session: Session) -> list[EntryLink]:
    """Every link, oldest first: the export."""
    return list(session.scalars(select(EntryLink).order_by(EntryLink.id)))


def count(session: Session) -> int:
    return session.scalar(select(func.count(EntryLink.id))) or 0


def newest(session: Session):
    """When the latest link was made, or None: the graph cache's fingerprint."""
    return session.scalar(select(func.max(EntryLink.created_at)))


def count_live(session: Session) -> int:
    """Links between notes still in the notebook, the graph's own count: a
    binned note keeps its links for a restore, and counting them said 4,234
    on 37 notes."""
    live_from, live_to = aliased(Entry), aliased(Entry)
    return (
        session.scalar(
            select(func.count(EntryLink.id))
            .join(live_from, live_from.id == EntryLink.source_entry_id)
            .join(live_to, live_to.id == EntryLink.target_entry_id)
            .where(live_from.is_deleted == False, live_to.is_deleted == False)  # noqa: E712
        )
        or 0
    )
