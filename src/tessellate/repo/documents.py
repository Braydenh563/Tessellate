"""Documents: the rows, their history (`DocumentRevision`) and the log of
accepted AI edits (`DocumentAiEdit`). The resource behind `api/routes_documents.py`
(INBOX 1499, row 3a); see `repo/__init__.py` for the rules every repository
keeps (flush, never commit).

The bin and shelf guards are `repo/content.py`'s (`DOCUMENTS.writable`,
`unshelved`); this module is the reads and the plain writes. A policy number
(how long a sitting lasts, how many entries a history keeps) is the route's to
name and is passed in, so it is defined where it is read.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy import delete as sa_delete
from sqlalchemy.orm import Session

from tessellate.core.database import (
    LIKE_ESCAPE,
    Document,
    DocumentAiEdit,
    DocumentLink,
    DocumentRevision,
    like_escape,
    utcnow,
)
from tessellate.repo import NotFound

logger = logging.getLogger(__name__)

MISSING = "That document could not be found."
NO_REVISION = "That revision could not be found."
NO_AI_EDIT = "That AI edit could not be found."

#: Newest first: how every document list is read.
_NEWEST = (Document.updated_at.desc(), Document.id.desc())


# --- documents -----------------------------------------------------------------


def find(session: Session, document_id: int) -> Document | None:
    return session.get(Document, document_id)


def get(session: Session, document_id: int) -> Document:
    document = find(session, document_id)
    if document is None:
        raise NotFound(MISSING)
    return document


def get_any(session: Session, document_id: int) -> Document:
    """The document, binned or not: the bin's purge reads this."""
    from tessellate.entry.bin import including_binned

    with including_binned(session):
        document = session.get(Document, document_id)
    if document is None:
        raise NotFound(MISSING)
    return document


def create(session: Session, *, title: str, content: str, file_type: str) -> Document:
    """A new document with its id; the route logs and commits."""
    document = Document(title=title, content=content, file_type=file_type)
    session.add(document)
    session.flush()
    return document


def page(
    session: Session, *, term: str, since: datetime | None, until: datetime | None, limit: int, offset: int
) -> tuple[list[Document], int]:
    """A page of the live (unshelved) documents, newest edit first, and how
    many match in all. `term` is a case-insensitive substring of the title or
    the text; `since` and `until` bound the last edit (until exclusive). The
    count reads the same filters as the page, so a caller paging a search
    never loops past the end of its own results."""
    filters = [Document.archived_at.is_(None)]
    if since is not None:
        filters.append(Document.updated_at >= since)
        if until is not None:
            filters.append(Document.updated_at < until)
    if term:
        like = f"%{like_escape(term)}%"
        filters.append(Document.title.ilike(like, escape=LIKE_ESCAPE) | Document.content.ilike(like, escape=LIKE_ESCAPE))
    total = session.scalar(select(func.count(Document.id)).where(*filters)) or 0
    rows = session.scalars(select(Document).where(*filters).order_by(*_NEWEST).limit(limit).offset(offset))
    return list(rows), total


def live(session: Session, *, limit: int, file_type: str | None = None) -> list[Document]:
    """The unshelved documents, newest edit first, of one file type when
    given: the Contents index and the replace-everywhere scan read this."""
    query = select(Document).where(Document.archived_at.is_(None))
    if file_type:
        query = query.where(Document.file_type == file_type)
    return list(session.scalars(query.order_by(*_NEWEST).limit(limit)))


def made_between(session: Session, since, until, limit: int) -> list[Document]:  # noqa: ANN001
    """The documents made on the days `since` to `until` (both kept), not in
    the bin or on the shelf, newest first: a date answer counts them with the
    notes of the days (INBOX 1739)."""
    from datetime import time, timedelta

    start, end = datetime.combine(since, time(0)), datetime.combine(until + timedelta(days=1), time(0))
    return list(session.scalars(
        select(Document)
        .where(Document.deleted_at.is_(None), Document.archived_at.is_(None), Document.created_at >= start, Document.created_at < end)
        .order_by(Document.created_at.desc(), Document.id.desc())
        .limit(limit)
    ))


def mentioning(session: Session, document_id: int, like: str, limit: int) -> list[Document]:
    """Other unshelved documents whose text matches the LIKE pattern, for
    backlinks."""
    return list(session.scalars(
        select(Document)
        .where(Document.id != document_id, Document.archived_at.is_(None), Document.content.ilike(like, escape=LIKE_ESCAPE))
        .order_by(*_NEWEST)
        .limit(limit)
    ))


def recent(session: Session, limit: int) -> list[Document]:
    """The documents not in the bin, newest edit first, shelved ones too: the
    chat's title match reads this."""
    return list(session.scalars(
        select(Document).where(Document.deleted_at.is_(None)).order_by(Document.updated_at.desc()).limit(limit)
    ))


def title_of(session: Session, document_id: int) -> str | None:
    """A document's title, or None when it is gone or binned."""
    return session.scalar(select(Document.title).where(Document.id == document_id, Document.deleted_at.is_(None)))


def mentioning_any(session: Session, words: list[str], limit: int) -> list[Document]:
    """Documents whose title or text holds any of the words, newest edit first:
    one OR across the words, not one scan per word (the chat's related panel)."""
    return list(session.scalars(
        select(Document)
        .where(or_(*(
            col.ilike(f"%{like_escape(word)}%", escape=LIKE_ESCAPE)
            for col in (Document.title, Document.content)
            for word in words
        )))
        .order_by(Document.updated_at.desc())
        .limit(limit)
    ))


def by_ids(session: Session, ids: set[int] | list[int]) -> list[Document]:
    """The documents with these ids (none for an empty set, with no query)."""
    if not ids:
        return []
    return list(session.scalars(select(Document).where(Document.id.in_(ids))))


def largest_id(session: Session) -> int | None:
    """The id of the document with the most text: the bench opens it."""
    return session.scalar(select(Document.id).order_by(func.length(Document.content).desc()).limit(1))


def mentioning_names(session: Session, likes: list[str], limit: int) -> list[Document]:
    """Unshelved documents whose text matches any of the LIKE patterns, newest
    edit first: a note's backlinks from documents, under every name it has."""
    return list(session.scalars(
        select(Document)
        .where(Document.archived_at.is_(None), or_(*[Document.content.ilike(like, escape=LIKE_ESCAPE) for like in likes]))
        .order_by(*_NEWEST)
        .limit(limit)
    ))


def mention_rows(session: Session, likes: list[str]):  # noqa: ANN201
    """Per unshelved document whose text matches any LIKE pattern, newest edit
    first: (id, title, content, then one flag per pattern, in order), so one scan
    answers every label. `like`, not `ilike`: SQLite folds ASCII case already and
    `ilike` copies every row's text once per pattern (74 ms against 35 ms over 60
    labels on 500 notes, same answers)."""
    flags = [Document.content.like(like, escape=LIKE_ESCAPE) for like in likes]
    return session.execute(
        select(Document.id, Document.title, Document.content, *[f.label(f"m{i}") for i, f in enumerate(flags)])
        .where(Document.archived_at.is_(None), or_(*flags))
        .order_by(*_NEWEST)
    )


def attached_to_entry(session: Session, entry_id: int) -> list[Document]:
    """The documents a note is attached to, by title."""
    return list(session.scalars(
        select(Document)
        .join(DocumentLink, DocumentLink.document_id == Document.id)
        .where(DocumentLink.entry_id == entry_id)
        .order_by(Document.title)
    ))

def link_pairs(session: Session, entry_ids) -> list:  # noqa: ANN001
    """Every (document_id, entry_id) saved link to one of these notes: the
    graph's document edges."""
    return list(session.execute(
        select(DocumentLink.document_id, DocumentLink.entry_id).where(DocumentLink.entry_id.in_(entry_ids))
    ))


def unshelved(session: Session, limit: int) -> list[Document]:
    """The unshelved documents, newest edit first, up to `limit`: the graph's
    document nodes."""
    return list(session.scalars(
        select(Document).where(Document.archived_at.is_(None)).order_by(Document.updated_at.desc()).limit(limit)
    ))


def held(session: Session, ids) -> list[Document]:  # noqa: ANN001
    """These documents that are not in the bin."""
    return list(session.scalars(select(Document).where(Document.id.in_(ids), Document.deleted_at.is_(None))))


def pinned(session: Session) -> list[Document]:
    """The documents not in the bin that hold a graph position."""
    return list(session.scalars(
        select(Document).where(Document.deleted_at.is_(None), Document.graph_pin_x.is_not(None))
    ))

def listing(session: Session, like: str | None, limit: int) -> list[Document]:
    """Every document not on the shelf, newest edit first (a shelved one is
    listed by `shelved`, once); `like` (an escaped LIKE pattern) narrows to a
    title or text match: the Library's document rows."""
    stmt = select(Document).where(Document.archived_at.is_(None))
    if like:
        stmt = stmt.where(or_(Document.title.ilike(like, escape=LIKE_ESCAPE), Document.content.ilike(like, escape=LIKE_ESCAPE)))
    return list(session.scalars(stmt.order_by(Document.updated_at.desc()).limit(limit)))


def shelved(session: Session, limit: int) -> list[Document]:
    """The shelved (archived) documents, most recently shelved first."""
    return list(session.scalars(
        select(Document).where(Document.archived_at.is_not(None)).order_by(Document.archived_at.desc()).limit(limit)
    ))


def count(session: Session, file_type: str | None = None) -> int:
    """How many documents there are, or how many of one file type."""
    stmt = select(func.count(Document.id))
    if file_type:
        stmt = stmt.where(Document.file_type == file_type)
    return session.scalar(stmt) or 0


def count_unbinned(session: Session) -> int:
    """How many documents are not in the bin."""
    return session.scalar(select(func.count(Document.id)).where(Document.deleted_at.is_(None))) or 0

#: How the timeline pages documents: placed by when they were created, id as the tiebreak.
CREATED = (Document.created_at, Document.id)


def created_in(in_range: Callable):  # noqa: ANN201
    """The statement for live documents placed by creation, for the timeline's
    paged merge (`in_range` adds its window). An archived document is "kept, out
    of the way", the one thing a journal of what you were doing should not put
    back in front of you."""
    return in_range(select(Document).where(Document.archived_at.is_(None)), Document.created_at)


def created_days(session: Session, in_range: Callable) -> list[datetime]:
    """When each live document in the window was created, for the timeline's density."""
    return [created for (created,) in session.execute(
        in_range(select(Document.created_at).where(Document.archived_at.is_(None)), Document.created_at)
    ).all()]

# --- history ---------------------------------------------------------------------


def record_revision(
    session: Session, document: Document, source: str, *, quiet_seconds: int, keep: int
) -> None:
    """Snapshot the document as it is *now*, before the caller changes it.

    Coalesced: an edit within `quiet_seconds` of the last unnamed snapshot
    replaces it, so the history reads as sittings rather than keystrokes; the
    oldest entries past `keep` are dropped. Never raises: a history that
    fails to record must not fail the save it was recording.
    """
    try:
        latest = session.scalars(
            select(DocumentRevision).where(DocumentRevision.document_id == document.id)
            .order_by(DocumentRevision.id.desc()).limit(1)
        ).first()
        now = utcnow()
        if latest is not None:
            #: Both sides made naive-UTC before comparing: a value read back
            #: from SQLite is naive, but a future backend could hand back an
            #: aware one and a mixed comparison raises rather than being wrong.
            previous = latest.created_at
            if previous.tzinfo is not None:
                previous = previous.replace(tzinfo=None)
            reference = now.replace(tzinfo=None) if now.tzinfo is not None else now
            if not latest.name and (reference - previous).total_seconds() < quiet_seconds:
                latest.title = document.title
                latest.content = document.content
                latest.source = source
                latest.created_at = now
                return
        session.add(DocumentRevision(document_id=document.id, title=document.title, content=document.content, source=source))
        session.flush()
        stale = session.scalars(
            select(DocumentRevision).where(DocumentRevision.document_id == document.id)
            .order_by(DocumentRevision.id.desc()).offset(keep)
        ).all()
        for row in stale:
            session.delete(row)
    except Exception:  # noqa: BLE001 - a history must never block a save
        logger.debug("could not record a document revision", exc_info=True)


def revisions(session: Session, document_id: int) -> list[DocumentRevision]:
    """This document's history, newest first."""
    return list(session.scalars(
        select(DocumentRevision).where(DocumentRevision.document_id == document_id).order_by(DocumentRevision.id.desc())
    ))


def revision(session: Session, document_id: int, revision_id: int) -> DocumentRevision:
    row = session.get(DocumentRevision, revision_id)
    if row is None or row.document_id != document_id:
        raise NotFound(NO_REVISION)
    return row


def name_version(session: Session, document: Document, name: str) -> DocumentRevision:
    """A revision holding the document as it stands, which no later edit
    coalesces into."""
    row = DocumentRevision(
        document_id=document.id, title=document.title, content=document.content, source="edit", name=name
    )
    session.add(row)
    session.flush()
    return row


# --- the AI edit log ---------------------------------------------------------------


def log_ai_edit(
    session: Session, document_id: int, *, verb: str, instruction: str, excerpt: str,
    before: str, after: str, keep: int,
) -> DocumentAiEdit:
    """One accepted AI edit; the entries past `keep` newest are pruned, so a
    heavily edited document does not hold an unbounded pile of snapshots."""
    row = DocumentAiEdit(
        document_id=document_id, verb=verb, instruction=instruction, selection_excerpt=excerpt,
        before_content=before, after_content=after,
    )
    session.add(row)
    session.flush()
    ids = session.scalars(
        select(DocumentAiEdit.id).where(DocumentAiEdit.document_id == document_id).order_by(DocumentAiEdit.created_at.desc())
    ).all()
    stale = ids[keep:]
    if stale:
        session.execute(sa_delete(DocumentAiEdit).where(DocumentAiEdit.id.in_(stale)).execution_options(synchronize_session=False))
    return row


def ai_edits(session: Session, document_id: int) -> list[DocumentAiEdit]:
    """The changelog, newest first."""
    return list(session.scalars(
        select(DocumentAiEdit).where(DocumentAiEdit.document_id == document_id).order_by(DocumentAiEdit.created_at.desc())
    ))


def ai_edit(session: Session, document_id: int, entry_id: int) -> DocumentAiEdit:
    row = session.get(DocumentAiEdit, entry_id)
    if row is None or row.document_id != document_id:
        raise NotFound(NO_AI_EDIT)
    return row


def revert_ai_edit(session: Session, document: Document, entry: DocumentAiEdit) -> None:
    """Put the text from before `entry` back, and record the revert as an
    entry of its own, so the changelog stays a truthful record and a revert
    can itself be reverted."""
    session.add(DocumentAiEdit(
        document_id=document.id,
        verb="revert",
        instruction=f"Reverted: {entry.instruction}" if entry.instruction else "Reverted an AI edit",
        selection_excerpt=entry.selection_excerpt,
        before_content=document.content,
        after_content=entry.before_content,
    ))
    document.content = entry.before_content
    document.updated_at = utcnow()


def open_link_pairs(session: Session) -> list[tuple[int, int]]:
    """(document id, note id) for every attachment of a live, non-private
    document: what a graph `document:N` node is made of. A private document
    is sealed, so it never lends the map its notes."""
    query = (
        select(DocumentLink.document_id, DocumentLink.entry_id)
        .join(Document, Document.id == DocumentLink.document_id)
        .where(Document.archived_at.is_(None), Document.deleted_at.is_(None), Document.is_private == False)  # noqa: E712
    )
    return list(session.execute(query))


def link_fingerprint(session: Session) -> tuple:
    """What moves when a document is attached, detached, archived or edited:
    the graph's document layer keys its cache on it."""
    return (
        session.scalar(select(func.count(DocumentLink.id))) or 0,
        session.scalar(select(func.max(DocumentLink.created_at))),
        session.scalar(select(func.count(Document.id)).where(Document.archived_at.is_(None), Document.deleted_at.is_(None)))
        or 0,
        session.scalar(select(func.max(Document.updated_at))),
    )


def any_title(session: Session, document_id: int) -> str | None:
    """A document's title whatever its state, for a stop on a graph route."""
    row = session.get(Document, document_id)
    return row.title if row is not None else None
