"""Where a note belongs besides its one category (L-world-class-172, 173).

`EntryCategory` (a note's further categories, set by hand) and `NoteGroup`
with its members (sets of notes a person gathered, apart from every sort).
Nothing here is written by the filer or any model, so the single-category
rule the janitor keeps is untouched: `entries.category_id` stays the one it
decides, and a row naming that same category is simply never read.
A repository flushes and never commits (`repo/__init__.py`).
"""

from __future__ import annotations

from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.orm import Session

from tessellate.core.database import Category, Entry, EntryCategory, NoteGroup, NoteGroupMember
from tessellate.repo import Conflict, Invalid, NotFound

NAME_MAX = 100


def in_category(category_id: int):
    """The where-clause for "this note is in this category": filed there, or
    also put there. One definition for every filter that selects by category."""
    return or_(
        Entry.category_id == category_id,
        Entry.id.in_(select(EntryCategory.entry_id).where(EntryCategory.category_id == category_id)),
    )


def in_any_category(category_ids):  # noqa: ANN001
    """`in_category` for a list or a subquery of category ids."""
    return or_(
        Entry.category_id.in_(category_ids),
        Entry.id.in_(select(EntryCategory.entry_id).where(EntryCategory.category_id.in_(category_ids))),
    )


def also_ids(session: Session, category_id: int) -> set[int]:
    """The notes also put in this category (not those filed there)."""
    return set(session.scalars(select(EntryCategory.entry_id).where(EntryCategory.category_id == category_id)))


def folded_names(session: Session, ids: list[int]) -> dict[int, set[str]]:
    """Every category name a note is in, filed or also, case-folded: what the
    search filters `in:`, `cat:` and `-cat:` compare."""
    found: dict[int, set[str]] = {}
    if not ids:
        return found
    for entry_id, name in session.execute(
        select(Entry.id, Category.name).join(Category, Category.id == Entry.category_id).where(Entry.id.in_(ids))
    ):
        found.setdefault(entry_id, set()).add(str(name).casefold())
    for entry_id, name in session.execute(
        select(EntryCategory.entry_id, Category.name)
        .join(Category, Category.id == EntryCategory.category_id)
        .where(EntryCategory.entry_id.in_(ids))
    ):
        found.setdefault(entry_id, set()).add(str(name).casefold())
    return found


def also_in_bulk(session: Session, entries: list[Entry]) -> dict[int, list[str]]:
    """Each note's further category names, in name order, never its own primary."""
    ids = [e.id for e in entries if e.id]
    if not ids:
        return {}
    primary = {e.id: e.category_id for e in entries}
    found: dict[int, list[str]] = {}
    rows = session.execute(
        select(EntryCategory.entry_id, Category.id, Category.name)
        .join(Category, Category.id == EntryCategory.category_id)
        .where(EntryCategory.entry_id.in_(ids))
        .order_by(Category.name)
    )
    for entry_id, category_id, name in rows:
        if category_id != primary.get(entry_id):
            found.setdefault(entry_id, []).append(name)
    return found


def groups_bulk(session: Session, ids: list[int]) -> dict[int, list[str]]:
    """The names of the groups each note is in, in name order."""
    if not ids:
        return {}
    found: dict[int, list[str]] = {}
    rows = session.execute(
        select(NoteGroupMember.entry_id, NoteGroup.name)
        .join(NoteGroup, NoteGroup.id == NoteGroupMember.group_id)
        .where(NoteGroupMember.entry_id.in_(ids))
        .order_by(NoteGroup.name)
    )
    for entry_id, name in rows:
        found.setdefault(entry_id, []).append(name)
    return found


def for_one(session: Session, entry: Entry) -> tuple[list[str], list[str]]:
    """`(also_in, groups)` of one note, for the routes that return a single one."""
    return also_in_bulk(session, [entry]).get(entry.id, []), groups_bulk(session, [entry.id]).get(entry.id, [])


def set_also_in(session: Session, entry: Entry, categories: list[Category]) -> list[str]:
    """Replace the note's further categories; the primary is dropped from the
    list. Returns the names kept."""
    keep = {c.id: c for c in categories if c.id != entry.category_id}
    session.execute(delete(EntryCategory).where(EntryCategory.entry_id == entry.id))
    for category in keep.values():
        session.add(EntryCategory(entry_id=entry.id, category_id=category.id))
    session.flush()
    return sorted(c.name for c in keep.values())


def move_also_in(session: Session, from_id: int, to_id: int) -> None:
    """A merge: the notes that were also in `from_id` are also in `to_id`
    (unless they are filed there, which `also_in_bulk` hides anyway)."""
    already = set(session.scalars(select(EntryCategory.entry_id).where(EntryCategory.category_id == to_id)))
    for row in list(session.scalars(select(EntryCategory).where(EntryCategory.category_id == from_id))):
        if row.entry_id in already:
            session.delete(row)
        else:
            row.category_id = to_id
    session.flush()


def _clean(name: str) -> str:
    name = " ".join((name or "").split())
    if not name:
        raise Invalid("A group needs a name.")
    if len(name) > NAME_MAX:
        raise Invalid(f"A group name is at most {NAME_MAX} characters.")
    return name


def find_group(session: Session, group_id: int) -> NoteGroup:
    group = session.get(NoteGroup, group_id)
    if group is None:
        raise NotFound("That group no longer exists.")
    return group


def list_groups(session: Session) -> list[dict]:
    """Every group with how many live notes it holds, by name."""
    counts = dict(
        session.execute(
            select(NoteGroupMember.group_id, func.count(Entry.id))
            .join(Entry, Entry.id == NoteGroupMember.entry_id)
            .where(and_(Entry.is_deleted == False, Entry.is_draft == False))  # noqa: E712
            .group_by(NoteGroupMember.group_id)
        ).all()
    )
    rows = session.scalars(select(NoteGroup).order_by(NoteGroup.name))
    return [{"id": g.id, "name": g.name, "count": counts.get(g.id, 0)} for g in rows]


def create_group(session: Session, name: str) -> NoteGroup:
    name = _clean(name)
    if session.scalar(select(NoteGroup.id).where(NoteGroup.name == name)) is not None:
        raise Conflict(f"There is already a group called {name}.")
    group = NoteGroup(name=name)
    session.add(group)
    session.flush()
    return group


def ensure_group(session: Session, name: str) -> NoteGroup:
    """The group of that name, made if it is not there (an import)."""
    name = _clean(name)
    found = session.scalar(select(NoteGroup).where(NoteGroup.name == name))
    return found if found is not None else create_group(session, name)


def rename_group(session: Session, group_id: int, name: str) -> NoteGroup:
    group = find_group(session, group_id)
    name = _clean(name)
    clash = session.scalar(select(NoteGroup.id).where(NoteGroup.name == name, NoteGroup.id != group_id))
    if clash is not None:
        raise Conflict(f"There is already a group called {name}.")
    group.name = name
    session.flush()
    return group


def delete_group(session: Session, group_id: int) -> None:
    """The group goes; its notes are untouched."""
    group = find_group(session, group_id)
    session.execute(delete(NoteGroupMember).where(NoteGroupMember.group_id == group.id))
    session.delete(group)
    session.flush()


def add_notes(session: Session, group_id: int, entry_ids: list[int]) -> int:
    find_group(session, group_id)
    have = set(session.scalars(select(NoteGroupMember.entry_id).where(NoteGroupMember.group_id == group_id)))
    live = set(session.scalars(select(Entry.id).where(Entry.id.in_(entry_ids))))
    added = [i for i in dict.fromkeys(entry_ids) if i in live and i not in have]
    for entry_id in added:
        session.add(NoteGroupMember(group_id=group_id, entry_id=entry_id))
    session.flush()
    return len(added)


def remove_notes(session: Session, group_id: int, entry_ids: list[int]) -> int:
    find_group(session, group_id)
    result = session.execute(
        delete(NoteGroupMember).where(
            NoteGroupMember.group_id == group_id, NoteGroupMember.entry_id.in_(entry_ids)
        )
    )
    session.flush()
    return result.rowcount or 0
