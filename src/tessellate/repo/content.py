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

An adapter is small on purpose: how to find a row with the bin included,
whether that row is binned, and how to take it out of the bin. `KINDS` is the
table a verb across kinds reads (**the undo table**: `restore(session, kind,
id)` is the one way back out of the bin for every kind, and every restore
route goes through it), so a new kind is one adapter row. See
`repo/__init__.py` for the rules every repository keeps (flush, never commit).

A binned OCR reading is not here on purpose: it is a former value of a file's
text kept in `core/reading_bin.py`, not a row with a bin mark, and putting it
back rewrites the file's reading, its region cache and its index, which its
own route does.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import Protocol, runtime_checkable

from sqlalchemy import select
from sqlalchemy.orm import Session

from tessellate.core.database import Attachment, Document, Entry, Recording, Reminder
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

    def restore(self, session: Session, row: object) -> None:
        """Out of the bin, logged; flushes, never commits. Only called on a
        binned row."""


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

    def restore(self, session: Session, row: Entry) -> None:
        from tessellate.entry import manager

        manager.restore_entry(session, row)


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

    def restore(self, session: Session, row: Document) -> None:
        """With the sub-pages binned in the same moment as it (D14), and not
        one binned on its own before: that one stays in the bin."""
        from tessellate.entry.manager import log_action
        from tessellate.repo.documents import subtree

        binned_at, row.deleted_at = row.deleted_at, None
        for child in subtree(session, row.id):
            if binned_at is not None and child.deleted_at == binned_at:
                child.deleted_at = None
        log_action(session, "restored", "document", row.id, row.title[:80])
        session.flush()


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

    def restore(self, session: Session, row: Attachment) -> None:
        """A file is in its note's bin, so its way back is its note's."""
        NOTES.restore(session, session.get(Entry, row.entry_id))


class _Reminders(_Documents):
    """A reminder's bin mark is `deleted_at`, like a document's."""

    kind = noun = "reminder"

    def find_any(self, session: Session, row_id: int) -> Reminder | None:
        from tessellate.entry.bin import including_binned

        with including_binned(session):
            return session.get(Reminder, row_id)

    def restore(self, session: Session, row: Reminder) -> None:
        from tessellate.repo import reminders

        reminders.restore(session, row)


class _Recordings(_Documents):
    kind = noun = "recording"

    def find_any(self, session: Session, row_id: int) -> Recording | None:
        from tessellate.entry.bin import including_binned

        with including_binned(session):
            return session.get(Recording, row_id)

    def restore(self, session: Session, row: Recording) -> None:
        from tessellate.entry.manager import log_action

        row.deleted_at = None
        log_action(session, "restored", "recording", row.id)
        session.flush()


NOTES = _Notes()
BOARDS = _Boards()
DOCUMENTS = _Documents()
FILES = _Files()
REMINDERS = _Reminders()
RECORDINGS = _Recordings()

#: Every content type by its kind name: the undo table, and the table any
#: other verb across kinds reads.
KINDS: dict[str, Content] = {a.kind: a for a in (NOTES, BOARDS, DOCUMENTS, FILES, REMINDERS, RECORDINGS)}

#: The answer for a kind the table does not name.
NO_KIND = "Nothing of that kind goes in the bin."


def restore(session: Session, kind: str, row_id: int) -> tuple[object, bool]:
    """The one way out of the bin: the row and whether it was binned. A live
    row is left as it is (a second press of Restore changes nothing). Flushes,
    never commits: the route owns the transaction."""
    adapter = KINDS.get(kind)
    if adapter is None:
        raise NotFound(NO_KIND)
    row = adapter.find_any(session, row_id)
    if row is None:
        raise NotFound(f"That {adapter.noun} could not be found.")
    binned = adapter.is_binned(session, row)
    if binned:
        adapter.restore(session, row)
    return row, binned


#: The walk's order: notes and boards share one pass over their table, in id
#: order, so an export writes them as it always has; then documents, files,
#: reminders and recordings.
_TABLES = ((Entry, (NOTES, BOARDS)), (Document, (DOCUMENTS,)), (Attachment, (FILES,)),
           (Reminder, (REMINDERS,)), (Recording, (RECORDINGS,)))


def walk(session: Session, kinds: Iterable[str] | None = None) -> Iterator[tuple[Content, object]]:
    """Every row of every kind (or of `kinds`), each with its adapter, in one
    order: **the one export walker** (audit 1031 row 2a). A binned note and
    a binned document are both walked (the exports keep the bin, under
    `_recycle-bin`; decided in content3-1101, so an export never drops what
    the bin still holds); a binned reminder or recording stays under the bin
    floor (`core/database._hide_binned`) as it always has."""
    from tessellate.entry.bin import including_binned

    wanted = set(KINDS) if kinds is None else set(kinds)
    for model, adapters in _TABLES:
        if not wanted & {a.kind for a in adapters}:
            continue
        if model is Document:
            with including_binned(session):
                rows = list(session.scalars(select(model).order_by(model.id)))
        else:
            rows = session.scalars(select(model).order_by(model.id))
        for row in rows:
            adapter = adapters[-1] if model is Entry and row.is_board else adapters[0]
            if adapter.kind in wanted:
                yield adapter, row


def unshelved(document: Document, *, unarchive: bool) -> Document:
    """A document's own rule on top of the bin: an archived one is taken off
    the shelf only when the caller asks, else 409 (DC8)."""
    if document.archived_at is not None:
        if not unarchive:
            raise Conflict(ARCHIVED.format(noun="document"))
        document.archived_at = None
    return document


def anything_kept(session: Session) -> bool:
    """Whether the notebook holds a note or a document outside the bin. A
    private note counts (it is counted, never read), and a board does not:
    the chat's empty-notebook line reads this (`api/chat_pool.py`)."""
    note = select(Entry.id).where(Entry.is_deleted == False, Entry.is_board == False).limit(1)  # noqa: E712
    document = select(Document.id).where(Document.deleted_at.is_(None)).limit(1)
    return session.scalar(note) is not None or session.scalar(document) is not None
