"""The per-page readings cache: what the optical reader saw and what a page was described as (L-world-class-820).

`api/routes_files_ocr.py` owns the sessions it opens (a cache write must
never fail a read), so these take the session it hands them. See
`repo/__init__.py` for the rules every repository keeps.
"""

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy.orm import Session

from tessellate.core.database import PageRead


def find(session: Session, kind: str, source_id: int, page: int) -> PageRead | None:
    return (
        session.query(PageRead)
        .filter(PageRead.kind == kind, PageRead.source_id == source_id, PageRead.page == int(page))
        .one_or_none()
    )


def regions_blob(session: Session, kind: str, source_id: int, page: int) -> str:
    """The stored rectangles' JSON for this page, or an empty string."""
    row = (
        session.query(PageRead.regions)
        .filter(PageRead.kind == kind, PageRead.source_id == source_id, PageRead.page == int(page))
        .one_or_none()
    )
    return (row[0] if row else "") or ""


def find_or_add(session: Session, kind: str, source_id: int, page: int) -> PageRead:
    """The page's row, made (and added) when there is none.

    A page looked at or described but never read is a real state: the row
    carries the regions or the caption and an empty `text`, which is what
    keeps "N pages read" honest. See `PageRead.regions`.
    """
    row = find(session, kind, source_id, page)
    if row is None:
        row = PageRead(kind=kind, source_id=source_id, page=int(page))
        session.add(row)
    return row


def for_sources(session: Session, kind: str, ids: Iterable[int]) -> list[PageRead]:
    return (
        session.query(PageRead)
        .filter(PageRead.kind == kind, PageRead.source_id.in_(list(ids)))
        .order_by(PageRead.source_id.asc(), PageRead.page.asc())
        .all()
    )


def source_and_texts(session: Session, kind: str, ids: Iterable[int]) -> list[tuple[int, str]]:
    return [
        (source_id, text)
        for source_id, text in session.query(PageRead.source_id, PageRead.text)
        .filter(PageRead.kind == kind, PageRead.source_id.in_(list(ids)))
        .all()
    ]


def for_source(session: Session, kind: str, source_id: int) -> list[PageRead]:
    return (
        session.query(PageRead)
        .filter(PageRead.kind == kind, PageRead.source_id == source_id)
        .order_by(PageRead.page.asc())
        .all()
    )
