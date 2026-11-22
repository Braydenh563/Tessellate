"""The chats' rows: the sidebar list, the search scan and the quiet writes (L-world-class-820).

`api/routes_conversations.py` shapes these into summaries and turns. See
`repo/__init__.py` for the rules every repository keeps.
"""

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from tessellate.core.database import LIKE_ESCAPE, Attachment, Conversation, Entry

#: Newest first, pinned on top; the id breaks ties so two chats sharing an
#: `updated_at` cannot swap places between two pages.
ORDER = (
    Conversation.pinned.desc(),
    Conversation.updated_at.desc(),
    Conversation.id.desc(),
)

#: Archived chats are kept but out of the way (the Library's Shelved filter reads them).
LIVE = Conversation.archived_at.is_(None)


def live_page(session: Session, limit: int, offset: int) -> tuple[int, list[Conversation]]:
    total = session.scalar(select(func.count(Conversation.id)).where(LIVE)) or 0
    rows = list(session.scalars(select(Conversation).where(LIVE).order_by(*ORDER).limit(limit).offset(offset)))
    return total, rows


def search_candidates(session: Session, like: str, scan_cap: int) -> list[Conversation]:
    """A cheap prefilter that over-matches (JSON keys count as text); the caller checks properly."""
    return list(
        session.scalars(
            select(Conversation)
            .where(
                LIVE,
                Conversation.title.ilike(like, escape=LIKE_ESCAPE) | Conversation.messages.ilike(like, escape=LIKE_ESCAPE),
            )
            .order_by(*ORDER)
            .limit(scan_cap)
        )
    )


def set_quietly(session: Session, conversation: Conversation, **values) -> None:  # noqa: ANN003
    """A Core UPDATE that names `updated_at` itself, so `onupdate` does not fire.

    Pinning, archiving and a saved follow-up are organising, not using: an
    explicit value beats `onupdate`, which assigning the same value back
    through the ORM does not (an unchanged column is left out of the SET).
    """
    session.execute(
        update(Conversation)
        .where(Conversation.id == conversation.id)
        .values(**values, updated_at=conversation.updated_at)
    )


def exists(session: Session, conversation_id: int) -> bool:
    table = Conversation.__table__
    return bool(session.execute(select(table.c.id).where(table.c.id == conversation_id)).first())


def attachments_by_ids(session: Session, ids: Iterable[int]) -> list[Attachment]:
    ids = list(ids)
    return session.query(Attachment).filter(Attachment.id.in_(ids)).all() if ids else []


def entries_by_ids(session: Session, ids: Iterable[int]) -> list[Entry]:
    ids = list(ids)
    return session.query(Entry).filter(Entry.id.in_(ids)).all() if ids else []
