"""What the Library lists: the reads behind each kind's page (L-world-class-790).

Every function answers the rows `api/routes_library.py` turns into cards; the
route keeps the card shapes and the previews. See `repo/__init__.py` for the
rules every repository keeps.
"""

from __future__ import annotations

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from tessellate.core import events
from tessellate.core.database import (
    LIKE_ESCAPE,
    Attachment,
    AuditLog,
    Category,
    Conversation,
    Entry,
    like_escape,
)

#: The rows the notes list holds, as a where-clause, so its page and its total
#: can never disagree about what counts as a live note.
LIVE_NOTE = (
    Entry.is_deleted == False,  # noqa: E712
    Entry.archived_at.is_(None),
    Entry.is_draft == False,  # noqa: E712
)


def chats(session: Session, pattern: str | None, limit: int) -> list[Conversation]:
    stmt = select(Conversation)
    if pattern:
        # `messages` is the turns' JSON, so this also matches a key name like
        # "role"; harmless, since every chat has one and a person searching for
        # "role" among their chats gets them all, which is what they asked.
        stmt = stmt.where(
            or_(
                Conversation.title.ilike(pattern, escape=LIKE_ESCAPE),
                Conversation.messages.ilike(pattern, escape=LIKE_ESCAPE),
            )
        )
    return list(
        session.scalars(
            stmt.order_by(Conversation.pinned.desc(), Conversation.updated_at.desc()).limit(limit)
        )
    )


def shelved_chats(session: Session, limit: int) -> list[Conversation]:
    return session.scalars(
        select(Conversation)
        .where(Conversation.archived_at.is_not(None))
        .order_by(Conversation.archived_at.desc())
        .limit(limit)
    ).all()


def chat_count(session: Session) -> int:
    return int(session.scalar(select(func.count(Conversation.id))) or 0)


def attached_files(session: Session, limit: int) -> list:
    """Each attachment with its note; never a deleted or private note's."""
    return session.execute(
        select(Attachment, Entry)
        .join(Entry, Attachment.entry_id == Entry.id)
        .where(
            Entry.is_deleted == False,  # noqa: E712
            # An attachment on a private note is as private as the note. The
            # Library is a browsing surface and would otherwise be the one
            # place a locked-away note's contents show up in plain sight.
            Entry.is_private == False,  # noqa: E712
        )
        .order_by(Attachment.created_at.desc())
        .limit(limit)
    ).all()


def binned_notes(session: Session, limit: int) -> list[Entry]:
    return session.scalars(
        select(Entry)
        .where(
            Entry.is_deleted == True,  # noqa: E712
            Entry.is_private == False,  # noqa: E712
        )
        .order_by(Entry.created_at.desc())
        .limit(limit)
    ).all()


def first_images(session: Session, entry_ids: list[int]) -> list:
    """`(entry_id, attachment_id)` of every image attachment of these notes, oldest first."""
    return session.execute(
        select(Attachment.entry_id, Attachment.id)
        .where(Attachment.entry_id.in_(entry_ids), Attachment.mime.like("image/%"))
        .order_by(Attachment.created_at.asc())
    ).all()


def shelved_notes(session: Session, limit: int) -> list[Entry]:
    return session.scalars(
        select(Entry)
        .where(
            Entry.archived_at.is_not(None),
            Entry.is_deleted == False,  # noqa: E712
            Entry.is_private == False,  # noqa: E712
        )
        .order_by(Entry.archived_at.desc())
        .limit(limit)
    ).all()


def notes(session: Session, pattern: str | None, limit: int) -> list:
    """`(entry, category name)`, pinned first. A search matches before the page
    is cut, so it reaches a note older than the newest `limit` (INBOX 424).
    Never a private note: its content is ciphertext, and a match on it would
    say something about what the encryption is hiding."""
    return session.execute(
        select(Entry, Category.name)
        .outerjoin(Category, Entry.category_id == Category.id)
        # A draft is unfinished by definition: the Notes tab's own browse list
        # keeps every draft out of "All notes" and every category filter, and
        # so must this one.
        .where(*LIVE_NOTE)
        .where(
            *(
                (Entry.is_private == False, Entry.content.ilike(pattern, escape=LIKE_ESCAPE))  # noqa: E712
                if pattern
                else ()
            )
        )
        .order_by(Entry.pinned.desc(), Entry.created_at.desc())
        .limit(limit)
    ).all()


def notes_with_marks(session: Session, limit: int) -> list[Entry]:
    """Live, public notes whose text holds a `==mark==`, newest first."""
    return session.execute(
        select(Entry)
        .where(
            *LIVE_NOTE,
            Entry.is_board == False,  # noqa: E712
            Entry.is_private == False,  # noqa: E712
            Entry.content.contains("=="),
        )
        .order_by(Entry.created_at.desc())
        .limit(limit)
    ).scalars()


def drafts(session: Session, limit: int) -> list:
    """`(entry, category name)` of every unarchived draft."""
    return session.execute(
        select(Entry, Category.name)
        .outerjoin(Category, Entry.category_id == Category.id)
        .where(
            Entry.is_deleted == False,  # noqa: E712
            Entry.archived_at.is_(None),
            Entry.is_draft == True,  # noqa: E712
        )
        .order_by(Entry.created_at.desc())
        .limit(limit)
    ).all()


def live_note_count(session: Session) -> int:
    return int(
        session.scalar(select(func.count(Entry.id)).where(*LIVE_NOTE, Entry.is_board == False))  # noqa: E712
        or 0
    )


def activity(session: Session, q: str, limit: int) -> list:
    """The audit log's rows, columns only, narrowed to the session's space.

    A row about a note follows that note's space, the way the space hook
    narrows every other read; a row about anything else is the notebook's and
    shows in every space."""
    query = (
        select(
            AuditLog.id,
            AuditLog.action,
            AuditLog.entity_type,
            AuditLog.entity_id,
            AuditLog.detail,
            AuditLog.created_at,
        )
        # The bookkeeping events (a version snapshotted before an edit, the
        # dates re-resolved because the text changed) always accompany the
        # edit that caused them, so a feed that shows both says everything
        # twice and buries the half a person recognises.
        .where(AuditLog.action.notin_(sorted(events.QUIET_ACTIONS)))
    )
    workspace = session.info.get("workspace_id")
    scoped = bool((workspace and workspace != "all") or session.info.get("hidden_workspaces"))
    if q or scoped:
        query = query.outerjoin(
            Entry, and_(AuditLog.entity_type == "entry", Entry.id == AuditLog.entity_id)
        )
    if scoped:
        query = query.where(or_(AuditLog.entity_type != "entry", Entry.id.is_not(None)))
    if q:
        # A note's own events carry no sentence (its words are the note), so
        # a row about a note matches on the note's text as well.
        pattern = f"%{like_escape(q)}%"
        query = query.where(
            or_(
                AuditLog.detail.ilike(pattern, escape=LIKE_ESCAPE),
                Entry.content.ilike(pattern, escape=LIKE_ESCAPE),
            )
        )
    return session.execute(
        query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(limit)
    ).all()
