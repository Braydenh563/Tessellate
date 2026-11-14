"""`archive_note`: keep notes, out of the way, and bring them back (L-chat-46, the acts archive and unarchive).

Archiving is not deleting (BACKLOG 30b: never auto-cleared, never purged), so the tool adds, like `pin_note`,
and its result carries the Undo: one `archive_note` call the other way over exactly the notes it changed.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from tessellate.ai.tools._common import ToolError, ToolSpec, _require_note
from tessellate.ai.tools.tool_read import _named
from tessellate.entry import manager


def _requested(args: dict) -> list[int]:
    raw = [*(args.get("note_ids") or []), args.get("note_id")]
    if not isinstance(args.get("note_ids") or [], list):
        raise ToolError("note_ids must be a list of note ids")
    wanted: list[int] = []
    for value in raw:
        if value is None:
            continue
        try:
            note_id = int(value)
        except (TypeError, ValueError) as exc:
            raise ToolError(f"{value!r} is not a note id") from exc
        if note_id not in wanted:
            wanted.append(note_id)
    return wanted


def _archive_note(session: Session, args: dict) -> dict:
    wanted = _requested(args)
    if not wanted:
        raise ToolError("Must provide at least one note_id")
    archive = bool(args.get("archived", True))
    changed = []
    for note_id in wanted:
        entry = _require_note(session, {"note_id": note_id})
        if bool(entry.archived_at) == archive:
            continue
        (manager.archive_entry if archive else manager.unarchive_entry)(session, entry)
        changed.append(entry)
    if not changed:
        said = "already in the Archive" if archive else "not in the Archive"
        raise ToolError(f"Nothing to do: {'that note is' if len(wanted) == 1 else 'those notes are'} {said}")
    names = ", ".join(_named(e) for e in changed[:3]) + (f" and {len(changed) - 3} more" if len(changed) > 3 else "")
    verb = "Archived" if archive else "Brought back from the Archive"
    return {
        #: The ids the call touched either way (the change list reads this one field), and which way.
        "archived": [e.id for e in changed],
        "now_archived": archive,
        "label": f"ph:archive {verb}: {names}",
        "undo": {"tool": "archive_note", "arguments": {"note_ids": [e.id for e in changed], "archived": not archive}},
    }


ARCHIVE_SPEC = ToolSpec(
    "archive_note",
    "Archive notes, or bring them back (archived false). Archived notes are kept, never deleted.",
    {
        "type": "object",
        "properties": {
            "note_id": {"type": "integer", "description": "The note's id number"},
            "note_ids": {"type": "array", "items": {"type": "integer"}, "description": "IDs of several notes (optional)"},
            "archived": {"type": "boolean", "description": "Leave out to archive; false to bring back"},
        },
        "required": [],
    },
    _archive_note,
)
