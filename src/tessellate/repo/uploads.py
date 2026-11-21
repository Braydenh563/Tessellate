"""Library uploads (`MediaUpload` rows): the reads the chat's attach paths share, so routers stay ORM-free."""
from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from tessellate.core.database import Attachment, Entry, MediaUpload


def get(session: Session, upload_id: int) -> MediaUpload | None:
    return session.get(MediaUpload, upload_id)


def by_ids(session: Session, ids: Iterable[int]) -> list[MediaUpload]:
    ids = list(ids)
    return session.query(MediaUpload).filter(MediaUpload.id.in_(ids)).all() if ids else []


def library_page(session: Session, limit: int, offset: int) -> tuple[int, list[MediaUpload]]:
    """The Library's count and one page, newest first. A picture that lives only on a board (K18) is not listed;
    the id breaks a tie on `created_at` so a page boundary never hides a row."""
    total = session.scalar(select(func.count(MediaUpload.id)).where(MediaUpload.board_only.is_(False))) or 0
    rows = (
        session.query(MediaUpload)
        .filter(MediaUpload.board_only.is_(False))
        .order_by(MediaUpload.created_at.desc(), MediaUpload.id.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )
    return total, rows


def by_filename(session: Session, filename: str) -> MediaUpload | None:
    return session.query(MediaUpload).filter(MediaUpload.filename == filename).first()


def is_listed(session: Session, filename: str) -> bool:
    """True when an upload row carries this stored filename in the request's reads."""
    return session.scalar(select(MediaUpload.id).where(MediaUpload.filename == filename)) is not None


def notes_embedding(session: Session, url: str) -> list[Entry]:
    """Live, non-private notes whose text contains `url`; the caller's regex decides.

    A private note is encrypted at rest and its content is not readable
    here, which is also why one cannot embed a Library image into one.
    """
    return list(
        session.scalars(
            select(Entry).where(
                Entry.is_deleted.is_(False),
                Entry.is_private.is_(False),
                Entry.content.contains(url),
            )
        ).all()
    )


def attachment_gallery_page(session: Session, limit: int, offset: int) -> tuple[int, list[tuple[Attachment, Entry]]]:
    """(the total, one page of (file, note) newest first) over the files whose note is neither binned nor private.

    The id breaks a tie on `created_at` so two files attached in the same
    second cannot swap places between pages and hide a row.
    """
    visible = (
        select(Attachment, Entry)
        .join(Entry, Attachment.entry_id == Entry.id)
        .where(
            Entry.is_deleted == False,  # noqa: E712
            Entry.is_private == False,  # noqa: E712
        )
    )
    total = session.scalar(select(func.count()).select_from(visible.subquery())) or 0
    rows = session.execute(
        visible.order_by(Attachment.created_at.desc(), Attachment.id.desc()).limit(limit).offset(offset)
    ).all()
    return total, [(a, e) for a, e in rows]


def readings(session: Session, source: str, source_id: int) -> list[tuple]:
    """(kind, page, text, model, ts) of each stored reading of one file, by page then kind."""
    return list(
        session.execute(
            text("SELECT kind, page, text, model, ts FROM readings WHERE source = :s AND source_id = :i ORDER BY page, kind"),
            {"s": source, "i": source_id},
        ).all()
    )
