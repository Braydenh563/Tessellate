"""One `Content` protocol across notes, boards, documents and files, with one
bin guard (audit 1031 row 2a: BK2, DC8, AR7).

Each content type had written its own bin, so each answered a write to a
binned thing differently: a note took the PUT and was rewritten (BK2), a
document and a board said 404 as if gone, and a file on a binned note was
renamed and rewritten under a note nobody could see. The rule lives here:
**a thing in the bin is restored before it is written**, answered 409 with
one sentence per noun, and every write route of the four families fetches
its row through its adapter's `writable`. A read keeps its 404: the bin floor
is a read rule (`core/database.py`, `entry/bin.py`).

An adapter is small on purpose: how to find a row with the bin included and
whether that row is binned. `KINDS` is the table a new verb (restore by kind,
the export walk) reads, so a new verb lands once for every kind. See
`repo/__init__.py` for the rules every repository keeps (flush, never commit).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from sqlalchemy.orm import Session

from tessellate.core.database import Attachment, Document, Entry
from tessellate.repo import Conflict, NotFound

#: One sentence per noun, so the answer reads the same from every route.
BINNED = "This {noun} is in the bin. Restore it first."
ARCHIVED = "This {noun} is archived. Unarchive it first."


@runtime_checkable
class Content(Protocol):
    """What every content type answers; `writable` is the one bin guard."""

    kind: str
    noun: str

    def find_any(self, session: Session, row_id: int) -> object | None:
        """The row, binned or not, or None if there is none to this caller."""

    def is_binned(self, session: Session, row: object) -> bool:
        """Whether the row sits in the bin."""

    def writable(self, session: Session, row_id: int) -> object:
        """The live row, or a 404 for none and a 409 for one in the bin."""


class _Adapter:
    kind = ""
    noun = ""

    def writable(self, session: Session, row_id: int):  # noqa: ANN201
        """The row, or `NotFound` (404) if there is none, or `Conflict` (409)
        if it is in the bin."""
        row = self.find_any(session, row_id)
        if row is None:
            raise NotFound(f"That {self.noun} could not be found.")
        if self.is_binned(session, row):
            raise Conflict(BINNED.format(noun=self.noun))
        return row


class _Notes(_Adapter):
    kind = noun = "note"

    def find_any(self, session: Session, row_id: int) -> Entry | None:
        return session.get(Entry, row_id)

    def is_binned(self, session: Session, row: Entry) -> bool:
        return bool(row.is_deleted)


class _Boards(_Notes):
    """A board is a note with a canvas; ids at or below 0 name none (0 is the
    unnamed scratch board, which has no note and no bin)."""

    kind = noun = "board"

    def find_any(self, session: Session, row_id: int) -> Entry | None:
        return session.get(Entry, row_id) if row_id > 0 else None


class _Documents(_Adapter):
    kind = noun = "document"

    def find_any(self, session: Session, row_id: int) -> Document | None:
        from tessellate.entry.bin import including_binned

        with including_binned(session):
            return session.get(Document, row_id)

    def is_binned(self, session: Session, row: Document) -> bool:
        return row.deleted_at is not None


class _Files(_Adapter):
    """An attachment is in the bin when its note is: binning a note carries its
    files with it, and restoring the note brings them back. The note is also
    the file's workspace (an attachment has no column of its own), so a file
    whose note this request cannot see is none."""

    kind = noun = "file"

    def find_any(self, session: Session, row_id: int) -> Attachment | None:
        row = session.get(Attachment, row_id)
        if row is None or session.get(Entry, row.entry_id) is None:
            return None
        return row

    def is_binned(self, session: Session, row: Attachment) -> bool:
        return bool(session.get(Entry, row.entry_id).is_deleted)


NOTES = _Notes()
BOARDS = _Boards()
DOCUMENTS = _Documents()
FILES = _Files()

#: Every content type by its kind name: the table a verb across kinds reads.
KINDS: dict[str, Content] = {a.kind: a for a in (NOTES, BOARDS, DOCUMENTS, FILES)}


def unshelved(document: Document, *, unarchive: bool) -> Document:
    """A document's own rule on top of the bin: an archived one is taken off
    the shelf only when the caller asks, else 409 (DC8)."""
    if document.archived_at is not None:
        if not unarchive:
            raise Conflict(ARCHIVED.format(noun="document"))
        document.archived_at = None
    return document
