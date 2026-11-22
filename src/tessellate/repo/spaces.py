"""Spaces: the one place the `spaces` table is read, and the per-space counts
(row 3a). The wholesale delete, move and restore walk every model here. See
`repo/__init__.py` for the rules every repository keeps.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete as sa_delete
from sqlalchemy import func
from sqlalchemy import select as sa_select
from sqlalchemy import update as sa_update
from sqlalchemy.orm import Session

from tessellate.core.database import Base, Category, Document, Entry, Space, workspace_scoped_models
from tessellate.core.database import impersonate_workspace


def ids(session: Session) -> set[str]:
    return {row[0] for row in session.query(Space.id).all()}


def all_spaces(session: Session) -> list[Space]:
    return session.query(Space).all()


def find(session: Session, space_id: str) -> Space | None:
    return session.get(Space, space_id)


def counts(session: Session, space_id: str) -> dict[str, int]:
    """What deleting the space would take with it; read across every workspace."""
    with impersonate_workspace(session, "all"):
        notes = session.query(func.count(Entry.id)).filter(Entry.workspace_id == space_id).scalar() or 0
        documents = session.query(func.count(Document.id)).filter(Document.workspace_id == space_id).scalar() or 0
    return {"notes": notes, "documents": documents}


def shown(session: Session, space_id: str) -> dict[str, int]:
    """What the space shows, for the dashboard's own line: saved notes, documents and
    boards, none of them counting the bin (`counts` is what a delete would take, the
    bin and the boards' companion notes included)."""
    with impersonate_workspace(session, "all"):
        def entries(board: bool) -> int:
            return session.query(func.count(Entry.id)).filter(
                Entry.workspace_id == space_id, Entry.is_board.is_(board), Entry.is_deleted.is_(False)
            ).scalar() or 0

        documents = session.query(func.count(Document.id)).filter(Document.workspace_id == space_id).scalar() or 0
        return {"notes": entries(False), "documents": documents, "boards": entries(True)}
def detach_references(session: Session, table, ids: list, depth: int = 0) -> None:  # noqa: ANN001
    """Clear every foreign key that points at `ids` in `table`: set a nullable
    one to NULL, delete the row holding a required one (and, for that row,
    whatever points at it in turn, a few levels deep)."""
    if not ids or depth > 4:
        return
    for other in Base.metadata.sorted_tables:
        for fk in other.foreign_keys:
            if fk.column.table is not table:
                continue
            column = fk.parent
            for start in range(0, len(ids), 500):
                chunk = ids[start:start + 500]
                if column.nullable:
                    session.execute(
                        sa_update(other).where(column.in_(chunk)).values({column.name: None})
                    )
                else:
                    if "id" in other.c and other is not table:
                        child_ids = [
                            row_id
                            for (row_id,) in session.execute(
                                sa_select(other.c.id).where(column.in_(chunk))
                            )
                        ]
                        detach_references(session, other, child_ids, depth + 1)
                    if other is not table:
                        session.execute(sa_delete(other).where(column.in_(chunk)))


def space_rows(session: Session, model, space_id: str):  # noqa: ANN001
    return session.query(model).filter_by(workspace_id=space_id)


def purge_ids(session: Session, model, column, ids: list) -> None:  # noqa: ANN001
    if ids:
        session.query(model).filter(column.in_(ids)).delete(synchronize_session=False)


def purge_side_tables(session: Session, ids: dict[str, list]) -> None:
    """The unscoped side tables: no workspace column of their own, only a
    foreign key into a row that is about to go. Each is the table a plain
    DELETE of its parent tripped over (real FKs, enforced)."""
    from tessellate.core.database import (
        DocumentAiEdit, DocumentBookmark, DocumentLink, DocumentRevision, EmbeddingRecord,
        EntityMention, EntryBookmark, EntryDate, EntryOpen, EntryProperty, EntryRevision, PageRead,
    )

    for model, column in (
        (EntityMention, EntityMention.entry_id),
        (EmbeddingRecord, EmbeddingRecord.entry_id),
        (EntryRevision, EntryRevision.entry_id),
        (EntryDate, EntryDate.entry_id),
        (EntryProperty, EntryProperty.entry_id),
        (EntryOpen, EntryOpen.entry_id),
        (EntryBookmark, EntryBookmark.entry_id),
        (DocumentLink, DocumentLink.entry_id),
    ):
        purge_ids(session, model, column, ids["entry"])
    for model, column in (
        (DocumentBookmark, DocumentBookmark.document_id),
        (DocumentLink, DocumentLink.document_id),
        (DocumentAiEdit, DocumentAiEdit.document_id),
        (DocumentRevision, DocumentRevision.document_id),
    ):
        purge_ids(session, model, column, ids["document"])
    purge_ids(session, EntryBookmark, EntryBookmark.bookmark_id, ids["bookmark"])
    purge_ids(session, DocumentBookmark, DocumentBookmark.bookmark_id, ids["bookmark"])
    for kind, key in (("attachment", "attachment"), ("media", "upload")):
        if ids[key]:
            session.query(PageRead).filter(
                PageRead.kind == kind, PageRead.source_id.in_(ids[key])
            ).delete(synchronize_session=False)


def purge_rows(session: Session, space_id: str, category_ids: list) -> None:
    """The space's own rows, parents after dependents.

    A note in *another* space can point at one of this space's categories
    (the reason the old reassign code merged categories by name). Those notes
    are not ours to delete; they just lose the pointer, the same as if the
    category had been deleted on its own.

    **Every reference into a doomed row is found from the schema, not a
    list.** The owner's delete of a space still failed on `DELETE FROM
    entries` with "FOREIGN KEY constraint failed" (0.3.31), from a table that
    points at notes and was on no list. Whatever the schema says points at a
    row about to go is cleared first: a nullable pointer is emptied, a
    required one takes its row with it."""
    from tessellate.core.database import (
        Attachment, AskTurn, Bookmark, Conversation, Document, EntryLink, MediaUpload,
        Reminder, WhiteboardNode, WhiteboardObject, WhiteboardSketch,
    )

    if category_ids:
        session.query(Entry).filter(Entry.category_id.in_(category_ids)).update(
            {"category_id": None}, synchronize_session=False
        )
    doomed_models = (
        EntryLink, Attachment, AskTurn, Conversation, Reminder, Bookmark,
        WhiteboardSketch, WhiteboardObject, WhiteboardNode, Document,
        Entry, Category, MediaUpload,
    )
    for model in (*doomed_models, *workspace_scoped_models()):
        rows = space_rows(session, model, space_id)
        ids = [row_id for (row_id,) in rows.with_entities(model.id).all()] if hasattr(model, "id") else []
        detach_references(session, model.__table__, ids)
    for model in doomed_models:
        space_rows(session, model, space_id).delete(synchronize_session=False)
    # Anything with WorkspaceMixin that the ordered list above does not name:
    # a model added later must not survive its space.
    for model in workspace_scoped_models():
        space_rows(session, model, space_id).delete(synchronize_session=False)


def has_rows(session: Session, space_id: str) -> bool:
    """Whether any workspace-scoped table holds a row of the space."""
    for model in workspace_scoped_models():
        table = model.__table__
        if session.execute(sa_select(table.c.id).where(table.c.workspace_id == space_id).limit(1)).first():
            return True
    return False


def purge_sources(session: Session, space_id: str) -> tuple[list, list, dict[str, list]]:
    """The space's attachments and uploads, and the ids of every kind a purge
    takes. Read with the space's bin included by the caller."""
    from tessellate.core.database import Bookmark, Document, MediaUpload, Reminder, Attachment

    attachments = space_rows(session, Attachment, space_id).all()
    uploads = space_rows(session, MediaUpload, space_id).all()

    def ids_of(model):  # noqa: ANN001
        return [row.id for row in space_rows(session, model, space_id).all()]

    return attachments, uploads, {
        "attachment": [a.id for a in attachments],
        "upload": [u.id for u in uploads],
        "document": ids_of(Document),
        "entry": ids_of(Entry),
        "bookmark": ids_of(Bookmark),
        "reminder": ids_of(Reminder),
        "category": ids_of(Category),
    }


def move_contents(session: Session, source: str, target: str) -> dict:
    """Every row of `source` becomes `target`'s. Categories are the one
    per-space unique name: a category the target already has is merged
    into it (its notes re-pointed, the duplicate dropped); the rest move.

    Answers with what it did, row by row, for Undo (undo-1005): the ids it
    moved per table, and each merged category as it was with the notes that
    pointed at it. Afterwards the moved rows cannot be told from the
    target's own, so this list is the only way back. The caller forgets the
    filing corpus: statements move notes round the ORM."""
    with impersonate_workspace(session, source):
        doomed = session.query(Category).filter(Category.workspace_id == source).all()
    with impersonate_workspace(session, target):
        existing = {
            c.name: c.id
            for c in session.query(Category).filter(Category.workspace_id == target).all()
        }
    entries = Entry.__table__
    merged: list[dict] = []
    for category in doomed:
        if category.name in existing:
            pointing = [
                row_id
                for (row_id,) in session.execute(
                    sa_select(entries.c.id).where(entries.c.category_id == category.id)
                )
            ]
            merged.append({
                "id": category.id, "name": category.name, "description": category.description,
                "colour": category.colour,
                "created_at": category.created_at.isoformat() if category.created_at else None,
                "into": existing[category.name], "entry_ids": pointing,
            })
            session.execute(
                sa_update(entries)
                .where(entries.c.category_id == category.id)
                .values(category_id=existing[category.name])
            )
            detach_references(session, Category.__table__, [category.id])
            session.execute(sa_delete(Category.__table__).where(Category.__table__.c.id == category.id))
    moved: dict[str, list[int]] = {}
    for model in workspace_scoped_models():
        table = model.__table__
        ids = [row_id for (row_id,) in session.execute(sa_select(table.c.id).where(table.c.workspace_id == source))]
        if ids:
            moved[table.name] = ids
        session.execute(
            sa_update(table).where(table.c.workspace_id == source).values(workspace_id=target)
        )
    return {"moved": moved, "merged": merged}


def move_back(session: Session, merged: list[dict], moved: dict[str, list[int]], move_to: str, sid: str) -> None:
    """Every row the delete moved out, moved back, and each merged category made again."""
    tables = {model.__table__.name: model.__table__ for model in workspace_scoped_models()}
    categories, entries = Category.__table__, Entry.__table__
    for item in merged:
        cid = int(item["id"])
        if session.execute(sa_select(categories.c.id).where(categories.c.id == cid)).first():
            continue
        created = item.get("created_at")
        session.execute(categories.insert().values(
            id=cid, name=str(item["name"])[:100], description=item.get("description"),
            colour=item.get("colour"), workspace_id=sid,
            **({"created_at": datetime.fromisoformat(created)} if created else {}),
        ))
        ids = [int(i) for i in item.get("entry_ids") or []]
        for start in range(0, len(ids), 500):
            session.execute(
                sa_update(entries)
                .where(entries.c.id.in_(ids[start:start + 500]), entries.c.category_id == int(item["into"]))
                .values(category_id=cid)
            )
    for name_, ids in moved.items():
        table = tables.get(name_)
        if table is None:
            continue
        for start in range(0, len(ids), 500):
            session.execute(
                sa_update(table)
                .where(table.c.id.in_(ids[start:start + 500]), table.c.workspace_id == move_to)
                .values(workspace_id=sid)
            )
