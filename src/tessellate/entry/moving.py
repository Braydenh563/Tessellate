"""Moving notes: into a category, or into another space.

Lifted out of the two routes that had the only copies (`POST /categories/move`
and `POST /spaces/{id}/move-notes`) so the agent's `move_notes` tool and the
screens do the same thing by the same code (OPEN row 1374, BACKLOG 14). The
routes keep their request and response shapes; nothing here knows about HTTP.
"""

from __future__ import annotations

from sqlalchemy import select
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
    """What hangs off the moved notes follows: files, reminders, fade scores, and links with both ends moved."""
    with impersonate_workspace(session, "all"):
        for model in (Attachment, Reminder, NoteScore):
            for row in session.scalars(select(model).where(model.entry_id.in_(moved_ids))):
                row.workspace_id = space_id
        for link in session.scalars(
            select(EntryLink).where(
                EntryLink.source_entry_id.in_(moved_ids), EntryLink.target_entry_id.in_(moved_ids)
            )
        ):
            link.workspace_id = space_id


def to_space(session: Session, space_id: str, ids: list[int]) -> dict:
    """Move these notes into one space and return `{"moved": n, "from": {id: old
    space}}`. Only notes the session can see move (the ambient space filter
    reads them), a note keeps its category's name (made in the target when it
    has none), and what hangs off a note comes with it: its files, reminders
    and fade score, and links whose both ends moved. A link to a note left
    behind stays where it was."""
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
        return {"moved": 0, "from": {}}
    before = {str(e.id): e.workspace_id or "default" for e in entries}
    _move_entries(session, entries, space_id)
    _move_dependents(session, [e.id for e in entries], space_id)
    manager.log_action(session, "moved", "entry", None, f"{len(entries)} note(s) to the space {space_id}")
    session.commit()
    return {"moved": len(entries), "from": before}
