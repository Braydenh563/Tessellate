"""The front-matter keys this app's Markdown export writes and its import
reads back (moved out of routes_settings_transfer.py to keep that route file
under its size cap; L-world-class-172, 173)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from tessellate.entry import manager
from tessellate.repo import memberships

#: The keys the app reads into its own fields (and writes on export); every
#: other key stays in the note's text as a property (GRAPH_PLAN KG4).
_APP_KEYS = {"category", "tags", "created", "updated", "pinned", "also-in", "note-groups"}


def keep_exported_state(session: Session, entry, meta: dict) -> bool:
    """Put back the date, pin, extra categories and groups an exported note
    carried; True when anything changed (the caller commits)."""
    if meta.get("created"):
        entry.created_at = meta["created"]
    if meta.get("pinned"):
        entry.pinned = True
    if meta.get("also_in"):
        space = manager.entry_space(entry)
        memberships.set_also_in(
            session, entry, [manager.get_or_create_category(session, n, workspace_id=space) for n in meta["also_in"]]
        )
    for name in meta.get("groups") or []:
        memberships.add_notes(session, memberships.ensure_group(session, name).id, [entry.id])
    return bool(meta.get("created") or meta.get("pinned") or meta.get("also_in") or meta.get("groups"))


def exported_memberships(found: dict) -> dict:
    """The export's `also-in` and `note-groups` lists, as the note's fields."""
    keys = (("also-in", "also_in"), ("note-groups", "groups"))
    return {name: [v for v in found[key] if v] for key, name in keys if found.get(key)}


def unexported_lines(block: str) -> list[str]:
    """The front matter's lines without the keys this app's export wrote."""
    kept: list[str] = []
    skipping = False
    for line in block.rstrip("\n").split("\n")[1:-1]:
        head = line.partition(":")[0].strip().lower()
        if line[:1] not in (" ", "\t", "-") and ":" in line:
            skipping = head in _APP_KEYS
        if not skipping:
            kept.append(line)
    return kept
