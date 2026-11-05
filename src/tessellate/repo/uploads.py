"""Library uploads (`MediaUpload` rows): the reads the chat's attach paths share, so routers stay ORM-free."""
from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy.orm import Session

from tessellate.core.database import MediaUpload


def get(session: Session, upload_id: int) -> MediaUpload | None:
    return session.get(MediaUpload, upload_id)


def by_ids(session: Session, ids: Iterable[int]) -> list[MediaUpload]:
    ids = list(ids)
    return session.query(MediaUpload).filter(MediaUpload.id.in_(ids)).all() if ids else []
