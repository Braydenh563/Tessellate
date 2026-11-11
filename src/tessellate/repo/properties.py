"""Note properties: the index of each note's `---` block (GRAPH_PLAN KG4).

The fifth resource behind a repository (INBOX 1499); the rules every
repository keeps are in `repo/__init__.py`. The note's text is the truth and
`manager.reindex_properties` rebuilds these rows on every save, so this module
only reads: a row per value, `number` and `date` being the value read as one
when it reads. A private note has no rows at all.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, aliased

from tessellate.core.database import Entry, EntryProperty
from tessellate.repo import NotFound

MISSING = "That note has no such property."


def find(session: Session, entry_id: int, key: str) -> EntryProperty | None:
    """The note's first row for `key` (lowest id), or None."""
    return session.scalars(
        select(EntryProperty)
        .where(EntryProperty.entry_id == entry_id, EntryProperty.key == key)
        .order_by(EntryProperty.id)
        .limit(1)
    ).first()


def get(session: Session, entry_id: int, key: str) -> EntryProperty:
    row = find(session, entry_id, key)
    if row is None:
        raise NotFound(MISSING)
    return row


def page(session: Session, entry_id: int, *, limit: int, offset: int = 0) -> tuple[list[EntryProperty], int]:
    """One note's rows in the order they sit in its block, and how many it has."""
    total = session.scalar(select(func.count(EntryProperty.id)).where(EntryProperty.entry_id == entry_id)) or 0
    rows = session.scalars(
        select(EntryProperty)
        .where(EntryProperty.entry_id == entry_id)
        .order_by(EntryProperty.id)
        .limit(limit)
        .offset(offset)
    )
    return list(rows), total


def types(session: Session) -> list[tuple[int, str]]:
    """Every note's `type` values as (note id, value), oldest row first, so a
    caller keeping the first per note keeps the one written first."""
    return [(i, v) for i, v in session.execute(
        select(EntryProperty.entry_id, EntryProperty.value)
        .where(EntryProperty.key == "type")
        .order_by(EntryProperty.id)
    )]


def meeting_dates(session: Session, entry_ids: list[int]) -> dict[int, tuple[datetime, str]]:
    """Each meeting's own date among `entry_ids` as (date, the value as
    written): a note typed Meeting whose `date:` reads as one. Two queries for
    the page; the first date row per note wins."""
    if not entry_ids:
        return {}
    typed = set(
        session.scalars(
            select(EntryProperty.entry_id).where(
                EntryProperty.entry_id.in_(entry_ids),
                EntryProperty.key == "type",
                func.lower(EntryProperty.value) == "meeting",
            )
        )
    )
    if not typed:
        return {}
    found: dict[int, tuple[datetime, str]] = {}
    for row in session.scalars(
        select(EntryProperty).where(
            EntryProperty.entry_id.in_(typed),
            EntryProperty.key == "date",
            EntryProperty.date.is_not(None),
        )
    ):
        found.setdefault(row.entry_id, (row.date, row.value))
    return found


def join_meeting_date(query: Select, entry_id) -> tuple[Select, object]:
    """`query` with each meeting's own `date:` joined on, and that column.

    The lowest-id date row of a note typed Meeting, found once for the whole
    notebook as a grouped subquery and joined on `entry_id` (a note's id
    column), so a window, a density and a page read a plain column instead of
    a correlated subquery per note.
    """
    meetings = select(EntryProperty.entry_id).where(
        EntryProperty.key == "type", func.lower(EntryProperty.value) == "meeting"
    )
    own_pick = (
        select(EntryProperty.entry_id.label("entry_id"), func.min(EntryProperty.id).label("pick"))
        .where(EntryProperty.key == "date", EntryProperty.date.is_not(None), EntryProperty.entry_id.in_(meetings))
        .group_by(EntryProperty.entry_id)
        .subquery("own_date")
    )
    own = aliased(EntryProperty)
    joined = query.outerjoin(own_pick, own_pick.c.entry_id == entry_id).outerjoin(own, own.id == own_pick.c.pick)
    return joined, own.date


#: A table of notes is a view, not an export: this many rows at most.
TABLE_ROWS = 300


def _matching_ids(session: Session, conditions: list[tuple[str, str]], columns: list[str]) -> set[int]:
    """Ids of the notes meeting every condition, or, with none, the notes that have any of `columns`."""
    ids: set[int] | None = None
    for key, value in conditions:
        found = set(
            session.scalars(
                select(EntryProperty.entry_id).where(
                    func.lower(EntryProperty.key) == key.strip().lower(),
                    func.lower(EntryProperty.value) == value.strip().lower(),
                )
            )
        )
        ids = found if ids is None else ids & found
    if ids is None:
        wanted = [c.lower() for c in columns]
        ids = set(session.scalars(select(EntryProperty.entry_id).where(func.lower(EntryProperty.key).in_(wanted))))
    return ids


def _cells(session: Session, ids: set[int], wanted: set[str]) -> dict[int, dict[str, list[EntryProperty]]]:
    """The property rows of those notes under those (lower-cased) keys, in the order they were written."""
    by_note: dict[int, dict[str, list[EntryProperty]]] = {}
    if not ids or not wanted:
        return by_note
    for row in session.scalars(
        select(EntryProperty)
        .where(EntryProperty.entry_id.in_(ids), func.lower(EntryProperty.key).in_(wanted))
        .order_by(EntryProperty.id)
    ):
        by_note.setdefault(row.entry_id, {}).setdefault(row.key.lower(), []).append(row)
    return by_note


def _sort_key(rows: list[EntryProperty]) -> tuple:
    """Numbers first, then dates, then text, by the property's first value."""
    first = rows[0]
    if first.number is not None:
        return (0, first.number, "")
    if first.date is not None:
        return (0, first.date.timestamp(), "")
    return (1, 0, first.value.lower())


def _ordered(ids: set[int], by_note: dict[int, dict[str, list[EntryProperty]]], sort: str, descending: bool) -> list[int]:
    """Ids by the sort property; a note without it goes last either way."""
    ordered = sorted(ids)
    key = sort.strip().lower()
    if not key:
        return ordered
    has = [i for i in ordered if by_note.get(i, {}).get(key)]
    seen = set(has)
    has.sort(key=lambda i: _sort_key(by_note[i][key]), reverse=descending)
    return has + [i for i in ordered if i not in seen]


def _rows(session: Session, page_ids: list[int], by_note: dict[int, dict[str, list[EntryProperty]]], columns: list[str]) -> list[dict]:
    """The page of notes as rows; a note deleted since the index was read is left out."""
    entries = {e.id: e for e in session.scalars(select(Entry).where(Entry.id.in_(page_ids)))} if page_ids else {}
    out = []
    for note_id in page_ids:
        entry = entries.get(note_id)
        if entry is None or entry.is_deleted:
            continue
        cells = by_note.get(note_id, {})
        values = {c: [r.value for r in cells.get(c.lower(), [])] for c in columns}
        out.append({"id": note_id, "content": entry.content or "", "values": values})
    return out


def table(
    session: Session,
    *,
    kind: str = "",
    where: list[tuple[str, str]] | None = None,
    columns: list[str] | None = None,
    sort: str = "",
    descending: bool = False,
    limit: int = TABLE_ROWS,
) -> tuple[list[dict], int]:
    """Notes matching every condition, with the values of `columns`, and how many matched.

    A condition is a property and a value, compared without regard to case; a
    list property matches when any of its values does. `kind` is the condition
    `type = kind`. With no condition at all, the notes that have any of
    `columns`. A private note has no rows, so it never appears. `sort` orders by
    that property's first value, as a number or a date when it reads as one,
    else as text; a note without it goes last either way.
    """
    conditions = ([("type", kind)] if kind.strip() else []) + [(k, v) for k, v in (where or []) if k.strip()]
    columns = [c for c in (columns or []) if c.strip()]
    ids = _matching_ids(session, conditions, columns)
    wanted = {c.lower() for c in columns} | {sort.strip().lower()}
    by_note = _cells(session, ids, wanted - {""})
    ordered = _ordered(ids, by_note, sort, descending)
    return _rows(session, ordered[: max(1, min(limit, TABLE_ROWS))], by_note, columns), len(ordered)
