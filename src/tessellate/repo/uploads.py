"""Library uploads (`MediaUpload` rows): the reads the chat's attach paths share, so routers stay ORM-free."""
from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tessellate.core.database import MediaUpload


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
