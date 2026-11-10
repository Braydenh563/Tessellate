"""Private spaces: membership is the privacy (INBOX 1727).

Everything in a private space is sealed as a private note is: a note or a
board through `manager.set_private`, the one crypto path, and a document
through the same key by `database.SealedText`, whose hook encrypts every
write to a private row. `sealed_by_space` records that the space did it, so
"Make it ordinary" on the way out unseals only those; a note private before
it came in stays private.

Every function here needs the vault key (the caller has unlocked the private
spaces); with no key `seal_member` refuses rather than leave a row readable.
"""

from __future__ import annotations

import importlib

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from tessellate.core.database import (
    AuditLog,
    Document,
    DocumentAiEdit,
    DocumentRevision,
    Entry,
    Space,
    WhiteboardObject,
    WhiteboardSketch,
    seal_row,
    unseal_row,
)

#: The note's Private switch, locked on inside a private space.
MOVE_OUT_TO_SHARE = "Move it out of this space to share it."

#: What the activity log says for a private document instead of its title.
PRIVATE_DOCUMENT_LABEL = "a private document"


class VaultLocked(RuntimeError):
    """Sealing needs the key, and none is loaded for this caller."""


def private_space_ids(session: Session) -> set[str]:
    return set(session.scalars(select(Space.id).where(Space.is_private.is_(True))))


def is_private_space(session: Session, space_id: str | None) -> bool:
    return bool(space_id) and space_id in private_space_ids(session)


def audit_title(session: Session, document: Document) -> str:
    """The activity log's words for a document: never a private one's title,
    nor one about to be sealed by the space it is made in."""
    space = document.workspace_id or session.info.get("workspace_id")
    if document.is_private or is_private_space(session, space):
        return PRIVATE_DOCUMENT_LABEL
    return (document.title or "")[:80]


def _key() -> bytes:
    from tessellate.core import vault

    key = vault.key()
    if key is None:
        raise VaultLocked("unlock the private spaces first")
    return key


def _board_items(session: Session, board_id: int) -> list:
    rows: list = list(session.scalars(select(WhiteboardSketch).where(WhiteboardSketch.board_id == board_id)))
    rows += list(session.scalars(select(WhiteboardObject).where(WhiteboardObject.board_id == board_id)))
    return rows


def _forget_thumb(board_id: int) -> None:
    """A board's cached picture is the board in the clear."""
    from tessellate.core import board_thumbs, deps

    board_thumbs.forget(deps.get_config().data_dir, [board_id])


def seal_entry(session: Session, entry: Entry) -> bool:
    """A note or board joins a private space. True when this sealed it."""
    _key()
    sealed = False
    if not entry.is_private:
        manager = importlib.import_module("tessellate.entry.manager")
        if not manager.set_private(session, entry, True):
            raise VaultLocked("unlock the private spaces first")
        entry.sealed_by_space = True
        sealed = True
    if entry.is_board:
        session.flush()
        for item in _board_items(session, entry.id):
            seal_row(item, every_column=True)
        _seal_board_log(session, entry.id, key=_key())
        _forget_thumb(entry.id)
    return sealed


def _seal_board_log(session: Session, board_id: int, *, key: bytes) -> None:
    """The board's items' logged states carry their text: sealed with it, and
    its own lines stop naming it."""
    from tessellate.core import crypto

    session.execute(
        update(AuditLog)
        .where(AuditLog.entity_type == "board", AuditLog.entity_id == board_id)
        .values(detail="a private board", payload=None)
    )
    rows = session.scalars(
        select(AuditLog).where(
            AuditLog.entity_type.in_(("whiteboard_sketch", "whiteboard_object")), AuditLog.payload.is_not(None)
        )
    )
    for row in rows:
        payload = row.payload if isinstance(row.payload, dict) else None
        if not payload:
            continue
        changed = {}
        for side in ("before", "after"):
            state = payload.get(side)
            if isinstance(state, dict) and state.get("board_id") == board_id and isinstance(state.get("data"), str):
                if not crypto.is_encrypted(state["data"]):
                    changed[side] = {**state, "data": crypto.encrypt(key, state["data"])}
        if changed:
            row.payload = {**payload, **changed}


def unseal_entry(session: Session, entry: Entry) -> bool:
    """"Make it ordinary": only what the space sealed. True when unsealed."""
    if not (entry.is_private and entry.sealed_by_space):
        return False
    _key()
    manager = importlib.import_module("tessellate.entry.manager")
    if not manager.set_private(session, entry, False):
        raise VaultLocked("unlock the private spaces first")
    entry.sealed_by_space = False
    if entry.is_board:
        session.flush()
        for item in _board_items(session, entry.id):
            unseal_row(item)
    return True


def _document_history(session: Session, document_id: int) -> list:
    rows: list = list(session.scalars(select(DocumentRevision).where(DocumentRevision.document_id == document_id)))
    rows += list(session.scalars(select(DocumentAiEdit).where(DocumentAiEdit.document_id == document_id)))
    return rows


def seal_document(session: Session, document: Document) -> bool:
    """A document joins a private space: its text, title, comments, history
    and AI edits are encrypted, its search row goes, its activity lines
    stop naming it."""
    _key()
    if document.is_private:
        return False
    document.is_private = True
    document.sealed_by_space = True
    seal_row(document, every_column=True)
    session.flush()
    for row in _document_history(session, document.id):
        seal_row(row, every_column=True)
    session.execute(
        update(AuditLog)
        .where(AuditLog.entity_type == "document", AuditLog.entity_id == document.id)
        .values(detail=PRIVATE_DOCUMENT_LABEL)
    )
    importlib.import_module("tessellate.search.index").touch(session, "documents", document.id)
    return True


def unseal_document(session: Session, document: Document) -> bool:
    if not (document.is_private and document.sealed_by_space):
        return False
    _key()
    document.is_private = False
    document.sealed_by_space = False
    unseal_row(document)
    session.flush()
    for row in _document_history(session, document.id):
        unseal_row(row)
    importlib.import_module("tessellate.search.index").touch(session, "documents", document.id)
    return True


def _members(session: Session, space_id: str) -> tuple[list[Entry], list[Document]]:
    from tessellate.core.deps import impersonate_workspace
    from tessellate.entry.bin import including_binned

    # Every row of the space, whatever space the request names ("" is no
    # space filter; "all" would still drop a space hidden from All spaces).
    with including_binned(session), impersonate_workspace(session, ""):
        entries = list(session.scalars(select(Entry).where(Entry.workspace_id == space_id)))
        documents = list(session.scalars(select(Document).where(Document.workspace_id == space_id)))
    return entries, documents


def member_count(session: Session, space_id: str) -> int:
    entries, documents = _members(session, space_id)
    return len(entries) + len(documents)


def seal_space_members(session: Session, space_id: str) -> int:
    """Seal everything in a private space that is not sealed yet. Idempotent,
    so a run cut short finishes on the next call. Returns how many it sealed."""
    entries, documents = _members(session, space_id)
    count = 0
    for entry in entries:
        if not entry.is_private:
            count += int(seal_entry(session, entry))
    for document in documents:
        count += int(seal_document(session, document))
    return count


def unseal_space_members(session: Session, space_id: str) -> int:
    """"Make them ordinary": everything the space sealed, nothing else."""
    entries, documents = _members(session, space_id)
    count = sum(int(unseal_entry(session, entry)) for entry in entries)
    return count + sum(int(unseal_document(session, document)) for document in documents)


def keep_members_private(session: Session, space_id: str) -> None:
    """A space turned ordinary with "Keep it private": each note becomes an
    ordinary private note, its own switch again. A document stays sealed."""
    entries, _documents = _members(session, space_id)
    for entry in entries:
        entry.sealed_by_space = False


def seal_if_private_space(session: Session, obj: Entry | Document) -> bool:
    """For a row just created in, or moved into, some space."""
    if not is_private_space(session, getattr(obj, "workspace_id", None)):
        return False
    session.flush()
    return seal_document(session, obj) if isinstance(obj, Document) else seal_entry(session, obj)


def leaving_ids(session: Session, target: str, ids: list[int]) -> list[int]:
    """Which of these notes sit in a private space other than `target`."""
    private = private_space_ids(session) - {target}
    if not private or not ids:
        return []
    return list(session.scalars(select(Entry.id).where(Entry.id.in_(ids), Entry.workspace_id.in_(private))))


def after_leaving(session: Session, ids: list[int], *, keep_private: bool) -> int:
    """The two-way answer for notes just moved out of a private space."""
    from tessellate.core.deps import impersonate_workspace

    with impersonate_workspace(session, ""):  # they are in their new space now
        entries = session.scalars(select(Entry).where(Entry.id.in_(ids))).all()
    return sum(int(leave_private_space(session, entry, keep_private=keep_private)) for entry in entries)


def leave_private_space(session: Session, obj: Entry | Document, *, keep_private: bool) -> bool:
    """A row moved out of a private space: the two-way question's answer."""
    if keep_private:
        if isinstance(obj, Entry):
            obj.sealed_by_space = False  # now its own: a later move in or out keeps it
        return False
    return unseal_document(session, obj) if isinstance(obj, Document) else unseal_entry(session, obj)
