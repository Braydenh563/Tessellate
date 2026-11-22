"""The recycle bin for documents and reminders (WORLD_CLASS_PLAN 5 item 10).

Notes, boards and maps are `Entry` rows with `is_deleted`, binned and restored
by `entry/manager.py`. A document and a reminder were deleted outright, and
their Undo made a new copy with a new id: a document came back without its
history, its notes and its reminders. Now each has `deleted_at`: set, it is
in the bin; cleared, it is back with everything that pointed at it.

**Hidden everywhere by one rule, not thirty-six filters.** A binned document
must not show in the Documents list, the Library, the timeline, the graph,
search, a mention scan or the agent's tools, and those read `Document` from
fourteen modules. `core/database.py` adds `deleted_at IS NULL` to every ORM
select of the two models (the same mechanism as the space filter) unless the
session says otherwise with `including_binned`, which the bin's own routes,
a space's delete and the media sweep use: those are the readers that must
see a binned document, so that restoring one brings back its pictures and a
deleted space takes its bin with it.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import timedelta
from typing import Iterator

from sqlalchemy import update
from sqlalchemy.orm import Session

from tessellate.core.database import (
    INCLUDE_BINNED,
    Document,
    DocumentAiEdit,
    DocumentBookmark,
    DocumentLink,
    DocumentRevision,
    Reminder,
    utcnow,
)
from tessellate.core import events, reading_bin, recordings


@contextmanager
def including_binned(session: Session) -> Iterator[Session]:
    """Read binned documents and reminders too, for the length of a block."""
    old = session.info.get(INCLUDE_BINNED)
    session.info[INCLUDE_BINNED] = True
    try:
        yield session
    finally:
        if old is None:
            session.info.pop(INCLUDE_BINNED, None)
        else:
            session.info[INCLUDE_BINNED] = old


def purge_document(session: Session, document: Document) -> None:
    """Delete a document for good, with every row that points at it.

    **All four tables that point at a document**, the whole of
    `grep 'ForeignKey("documents.id")'` in `core/database.py`: a revision, an
    AI edit, a note attached to it and a saved link each hold a real foreign
    key with no cascade, and a document with any of them could not be deleted
    at all before this list was written (the comment history is in
    `routes_documents.delete_document`'s git log). A reminder about it is the
    person's, not the document's: it stays, about nothing.
    """
    for model, column in (
        (DocumentRevision, DocumentRevision.document_id),
        (DocumentAiEdit, DocumentAiEdit.document_id),
        (DocumentLink, DocumentLink.document_id),
        (DocumentBookmark, DocumentBookmark.document_id),
    ):
        session.query(model).filter(column == document.id).delete(synchronize_session=False)
    session.execute(update(Reminder).where(Reminder.document_id == document.id).values(document_id=None))
    #: Its sub-pages are lifted to the top level, not taken with it (D14).
    session.execute(update(Document).where(Document.parent_id == document.id).values(parent_id=None))
    session.delete(document)


def binned(session: Session) -> tuple[list[Document], list[Reminder]]:
    """What is in the bin of these two kinds, newest first."""
    with including_binned(session):
        documents = (
            session.query(Document)
            .filter(Document.deleted_at.is_not(None))
            .order_by(Document.deleted_at.desc())
            .all()
        )
        reminders = (
            session.query(Reminder)
            .filter(Reminder.deleted_at.is_not(None))
            .order_by(Reminder.deleted_at.desc())
            .all()
        )
    return documents, reminders


def _purge(session: Session, documents: list[Document], reminders: list[Reminder]) -> int:
    for document in documents:
        purge_document(session, document)
    for reminder in reminders:
        session.delete(reminder)
    return len(documents) + len(reminders)


def empty(session: Session) -> int:
    """Empty the bin's documents, reminders, OCR readings and recordings. Commits."""
    documents, reminders = binned(session)
    with including_binned(session):
        count = (
            _purge(session, documents, reminders)
            + reading_bin.empty(session)
            + recordings.empty(session)
        )
        if count:
            events.record(session, "purged", "recycle_bin", None, f"{count} documents and reminders")
        session.commit()
    return count


def purge_expired(session: Session, days: int) -> int:
    """Drop documents and reminders binned more than `days` ago, the rule the
    bin's notes follow (`manager_purge.purge_expired_deleted`). Commits."""
    cutoff = utcnow() - timedelta(days=days)
    documents, reminders = binned(session)
    documents = [d for d in documents if d.deleted_at < cutoff]
    reminders = [r for r in reminders if r.deleted_at < cutoff]
    with including_binned(session):
        count = (
            _purge(session, documents, reminders)
            + reading_bin.purge_expired(session, days)
            + recordings.purge_expired(session, days)
        )
        if count:
            events.record(
                session, "purged", "recycle_bin", None, f"{count} expired documents and reminders"
            )
        session.commit()
    return count
