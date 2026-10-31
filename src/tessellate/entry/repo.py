"""Who may write what: the one guard every content type's write route asks.

A note in the bin answers 404 to a read but used to take a `PUT`, so the client
never learned it was rewriting something it could not see (audit 1031 BK2); an
archived document took one too (DC8). Each content type had written its own bin
check, so the one that forgot was a route-by-route bug (AR7). The rule lives
here: **a thing in the bin or on the shelf is restored before it is edited**,
and a route that writes a note or a document fetches it through
`writable_entry` or `writable_document`, never a bare `session.get`.

This is the first verb of a repository per content type (`readable`,
`writable`, create, update, bin). The routes still hold most of their own ORM
calls (AR1); the rest of the protocol lands one verb at a time, each behind a
test, rather than as one rewrite of 359 call sites.
"""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from tessellate.core.database import Document, Entry

#: One sentence per kind, so the answer reads the same from every route.
BINNED = "This {noun} is in the bin. Restore it first."
ARCHIVED = "This {noun} is archived. Unarchive it first."


def writable_entry(session: Session, entry_id: int, *, noun: str = "note") -> Entry:
    """The note, or 404 if there is none, or 409 if it is in the bin."""
    entry = session.get(Entry, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"That {noun} could not be found.")
    if entry.is_deleted:
        raise HTTPException(status_code=409, detail=BINNED.format(noun=noun))
    return entry


def writable_document(session: Session, document_id: int, *, unarchive: bool = False) -> Document:
    """The document, or 404 if there is none (a binned one reads as none), or 409
    if it is archived and the caller did not ask to take it off the shelf."""
    document = session.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="That document could not be found.")
    if document.archived_at is not None:
        if not unarchive:
            raise HTTPException(status_code=409, detail=ARCHIVED.format(noun="document"))
        document.archived_at = None
    return document
