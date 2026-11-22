"""What the suggestions inbox reads and clears on notes (L-world-class-820).

See `repo/__init__.py` for the rules every repository keeps.
"""

from __future__ import annotations

from sqlalchemy import bindparam, select, text
from sqlalchemy.orm import Session

from tessellate.core.database import Entry


def turned_down_tag_rows(session: Session) -> list[tuple[int, str]]:
    """(note id, the JSON of its "Not suggested" tags) for every live note that has any."""
    return [
        (entry_id, raw)
        for entry_id, raw in session.execute(
            text("SELECT id, discarded_tags FROM entries WHERE is_deleted = 0 AND discarded_tags NOT IN ('', '[]')")
        ).all()
    ]


def forget_turned_down_tags(session: Session, ids: list[int]) -> None:
    """Raw SQL: forgetting a verdict is not an edit, so no note's updated_at moves."""
    clear = text("UPDATE entries SET discarded_tags = '[]' WHERE id IN :ids").bindparams(bindparam("ids", expanding=True))
    session.execute(clear, {"ids": ids})


def content_of(session: Session, entry_id: int) -> str | None:
    return session.scalar(select(Entry.content).where(Entry.id == entry_id))
