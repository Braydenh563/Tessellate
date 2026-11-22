"""The board library's reads and the whiteboard stacking reads behind its routes (L-world-class-820).

Every function answers the rows `api/routes_board_library.py` shapes into
cards or places on a board. See `repo/__init__.py` for the rules every
repository keeps.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tessellate.core.database import (
    BoardLibrary,
    BoardLibraryItem,
    BoardLibraryMark,
    MediaUpload,
    WhiteboardNode,
    WhiteboardObject,
    WhiteboardSketch,
)


def yours(session: Session) -> BoardLibrary | None:
    return session.scalar(select(BoardLibrary).where(BoardLibrary.kind == "yours").order_by(BoardLibrary.id))


def libraries(session: Session) -> list[BoardLibrary]:
    return list(session.scalars(select(BoardLibrary).order_by(BoardLibrary.sort, BoardLibrary.id)).all())


def next_sort(session: Session) -> int:
    return 1 + (session.scalar(select(BoardLibrary.sort).order_by(BoardLibrary.sort.desc())) or 0)


def items(
    session: Session, kind: str | None, library_id: int | None, favourites: bool, deleted: bool, snippet_kind: str
) -> list[BoardLibraryItem]:
    query = select(BoardLibraryItem)
    query = query.where(BoardLibraryItem.deleted_at.is_not(None) if deleted else BoardLibraryItem.deleted_at.is_(None))
    query = query.where(BoardLibraryItem.kind == kind if kind else BoardLibraryItem.kind != snippet_kind)
    if library_id:
        query = query.where(BoardLibraryItem.library_id == library_id)
    if favourites:
        query = query.where(BoardLibraryItem.favourite.is_(True))
    return list(session.scalars(query.order_by(BoardLibraryItem.updated_at.desc(), BoardLibraryItem.id.desc())).all())


def marks(session: Session) -> list[BoardLibraryMark]:
    return list(session.scalars(select(BoardLibraryMark)).all())


def held_items(session: Session, library_id: int) -> list[BoardLibraryItem]:
    return list(session.scalars(select(BoardLibraryItem).where(BoardLibraryItem.library_id == library_id)).all())


def live_items(session: Session, library_id: int, snippet_kind: str) -> list[BoardLibraryItem]:
    return list(
        session.scalars(
            select(BoardLibraryItem).where(
                BoardLibraryItem.library_id == library_id,
                BoardLibraryItem.deleted_at.is_(None),
                BoardLibraryItem.kind != snippet_kind,
            )
        ).all()
    )


def media_filenames(session: Session) -> list[str]:
    return list(session.scalars(select(MediaUpload.filename)).all())


def has_board_root(session: Session, board_id: int, kinds: set[str]) -> bool:
    """True when the map board holds a top-level object of one of `kinds`."""
    found = session.scalar(
        select(WhiteboardObject.id)
        .where(
            WhiteboardObject.board_id == board_id,
            WhiteboardObject.parent_id.is_(None),
            WhiteboardObject.kind.in_(kinds),
        )
        .limit(1)
    )
    return found is not None


def band_tops(session: Session, board_id: int | None, skip_sketches: set, skip_objects: set):
    """(highest sketch z, highest node z, the other objects) on the board,
    leaving out the rows just placed."""
    here = (lambda col: col.is_(None)) if board_id is None else (lambda col: col == board_id)
    sketch_top = session.scalar(
        select(func.max(WhiteboardSketch.z)).where(here(WhiteboardSketch.board_id), WhiteboardSketch.id.not_in(skip_sketches))
    )
    note_top = session.scalar(select(func.max(WhiteboardNode.z)).where(here(WhiteboardNode.board_id)))
    others = session.scalars(
        select(WhiteboardObject).where(here(WhiteboardObject.board_id), WhiteboardObject.id.not_in(skip_objects))
    ).all()
    return sketch_top, note_top, others


def snippets(session: Session, snippet_kind: str) -> list[BoardLibraryItem]:
    """The person's live code snippets, newest first."""
    return list(
        session.scalars(
            select(BoardLibraryItem)
            .where(BoardLibraryItem.kind == snippet_kind, BoardLibraryItem.deleted_at.is_(None))
            .order_by(BoardLibraryItem.updated_at.desc(), BoardLibraryItem.id.desc())
        ).all()
    )
