"""Moving notes: into a category, or into another space.

Lifted out of the two routes that had the only copies (`POST /categories/move`
and `POST /spaces/{id}/move-notes`) so the agent's `move_notes` tool and the
screens do the same thing by the same code (OPEN row 1374, BACKLOG 14). The
routes keep their request and response shapes; nothing here knows about HTTP.
"""

from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from tessellate.core.database import Attachment, Entry, EntryLink, NoteScore, Reminder, Space, impersonate_workspace
from tessellate.entry import manager


def to_category(session: Session, entries: list, name: str, user_filed: bool | None = None) -> list[dict]:
    """Move notes into a category by name (made if new). Returns each moved
    note's old category and whether a person had filed it, which is what an
    Undo sends back."""
    previous = []
    for entry in entries:
        before = manager.category_name_for(session, entry)
        if before != name:
            previous.append({"id": entry.id, "category": before, "user_filed": bool(entry.user_filed)})
            manager.update_entry(session, entry, category_name=name)
        if user_filed is not None:
            entry.user_filed = user_filed
    session.commit()
    return previous


def _move_entries(session: Session, entries: list, space_id: str) -> None:
    """Put the notes in the space; a category goes by name, made in the target when it has none."""
    names = manager.bulk_category_names(session, entries)
    with impersonate_workspace(session, space_id):
        for entry in entries:
            name = names.get(entry.category_id)
            if entry.category_id is not None and name:
                entry.category_id = manager.get_or_create_category(session, name, space_id).id
            entry.workspace_id = space_id


def _move_dependents(session: Session, moved_ids: list[int], space_id: str) -> None:
    """What hangs off the moved notes follows: files, reminders, fade scores, and links with both ends now in the space."""
    with impersonate_workspace(session, "all"):
        for model in (Attachment, Reminder, NoteScore):
            for row in session.scalars(select(model).where(model.entry_id.in_(moved_ids))):
                row.workspace_id = space_id
        links = list(session.scalars(select(EntryLink).where(
            or_(EntryLink.source_entry_id.in_(moved_ids), EntryLink.target_entry_id.in_(moved_ids))
        )))
        #: Both ends in the target now: moved together, or one of them already
        #: there (the linked notes brought along by a second move).
        ends = {e for link in links for e in (link.source_entry_id, link.target_entry_id)}
        there = set(session.scalars(select(Entry.id).where(Entry.id.in_(ends), Entry.workspace_id == space_id)))
        for link in links:
            if {link.source_entry_id, link.target_entry_id} <= there:
                link.workspace_id = space_id


def _left_linked(session: Session, moved_ids: list[int], space_id: str) -> list[int]:
    """The notes a moved note is linked to, either way, that stayed behind:
    such a link keeps its old space, so it drops out of view in both spaces
    (All spaces still shows it). Read under the request's own space filter,
    so only notes the person could have selected are named, for the screens'
    "Bring them too" (WORLD_CLASS_PLAN 27.1, Spaces). Wiki links are text and
    resolve by title in whichever space the note is read."""
    moved = set(moved_ids)
    ends = session.execute(
        select(EntryLink.source_entry_id, EntryLink.target_entry_id).where(
            or_(EntryLink.source_entry_id.in_(moved_ids), EntryLink.target_entry_id.in_(moved_ids))
        )
    ).all()
    others = {end for pair in ends for end in pair if end not in moved}
    if not others:
        return []
    return sorted(session.scalars(
        select(Entry.id).where(Entry.id.in_(others), Entry.is_deleted == False, Entry.workspace_id != space_id)  # noqa: E712
    ))


def to_space(session: Session, space_id: str, ids: list[int]) -> dict:
    """Move these notes into one space and return `{"moved": n, "from": {id: old
    space}}`. Only notes the session can see move (the ambient space filter
    reads them), a note keeps its category's name (made in the target when it
    has none), and what hangs off a note comes with it: its files, reminders
    and fade score, and links whose both ends moved. A link to a note left
    behind stays where it was, and `linked` names those notes."""
    if space_id == "all":
        raise ValueError("Pick one space to move them to.")
    if session.get(Space, space_id) is None:
        raise LookupError("That space could not be found.")
    wanted = list(dict.fromkeys(ids))
    entries = [
        e for e in session.scalars(select(Entry).where(Entry.id.in_(wanted)))
        if (e.workspace_id or "default") != space_id
    ]
    if not entries:
        return {"moved": 0, "from": {}, "linked": []}
    before = {str(e.id): e.workspace_id or "default" for e in entries}
    moved_ids = [e.id for e in entries]
    linked = _left_linked(session, moved_ids, space_id)
    _move_entries(session, entries, space_id)
    _move_dependents(session, moved_ids, space_id)
    manager.log_action(session, "moved", "entry", None, f"{len(entries)} note(s) to the space {space_id}")
    session.commit()
    return {"moved": len(entries), "from": before, "linked": linked}
