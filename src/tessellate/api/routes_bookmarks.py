"""Bookmarks: saved links to somewhere outside the notebook, create, list,
update, delete. The routes read the request and shape the answer; every
query is `repo/bookmarks.py`'s (INBOX 1499). Nothing here needs the AI.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response

from tessellate.api import paging
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from tessellate.core.deps import get_session
from tessellate.repo import bookmarks, bookmarks_html

router = APIRouter(prefix="/bookmarks", tags=["bookmarks"])


class BookmarkCreate(BaseModel):
    url: str = Field(min_length=1, max_length=2000)
    title: str = Field(default="", max_length=200)
    note: str = Field(default="", max_length=2000)
    group_name: str = Field(default="", max_length=120)
    tags: list[str] = Field(default_factory=list, max_length=40)
    #: Carried on create so an Undo of a delete can put a link back exactly as
    #: it was, pin and read state included.
    pinned: bool = False
    is_read: bool = False


class BookmarkUpdate(BaseModel):
    url: str | None = Field(default=None, min_length=1, max_length=2000)
    title: str | None = Field(default=None, max_length=200)
    note: str | None = Field(default=None, max_length=2000)
    pinned: bool | None = None
    is_read: bool | None = None
    group_name: str | None = Field(default=None, max_length=120)
    tags: list[str] | None = Field(default=None, max_length=40)


def _to_out(bookmark, duplicate_of: int | None = None) -> dict:
    out = {
        "id": bookmark.id,
        "url": bookmark.url,
        "title": bookmark.title,
        "note": bookmark.note,
        "pinned": bookmark.pinned,
        "is_read": bool(bookmark.is_read),
        "group_name": bookmark.group_name,
        "tags": bookmarks.tag_list(bookmark.tags),
        "created_at": bookmark.created_at.isoformat(),
    }
    if duplicate_of is not None:
        # Warn, don't block (asked for directly): re-saving a link you
        # already have is a normal thing to do by accident, not a mistake
        # worth refusing outright: so this still creates the row and just
        # tells the frontend which earlier bookmark shares its URL, for a
        # toast rather than a hard stop.
        out["duplicate_of"] = duplicate_of
    return out


#: One page of saved links. A notebook's bookmarks grow with use and nothing
#: ever trimmed this list, so the response grew with the table for ever.
BOOKMARKS_PAGE_SIZE = 200


@router.get("")
def list_bookmarks(
    response: Response,
    limit: int = Query(default=BOOKMARKS_PAGE_SIZE, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    cursor: str | None = paging.cursor_param(),
    session: Session = Depends(get_session),
) -> list[dict]:
    """Pinned first, then newest first within each group, one page at a time."""
    offset = paging.start(cursor, offset)
    rows, total = bookmarks.page(session, limit=limit, offset=offset)
    response.headers["X-Total-Count"] = str(total)
    paging.finish(response, offset, limit, total)
    return [_to_out(b) for b in rows]


class BookmarksImport(BaseModel):
    #: The text of a browser's exported bookmarks file (Netscape format; every browser writes it).
    html: str = Field(min_length=1, max_length=bookmarks_html.MAX_CHARS)


@router.get("/export")
def export_bookmarks(session: Session = Depends(get_session)) -> Response:
    """Every bookmark as the bookmarks file a browser imports."""
    rows = [
        {"url": b.url, "title": b.title, "group_name": b.group_name, "tags": bookmarks.tag_list(b.tags), "created_at": b.created_at}
        for b in bookmarks.everything(session)
    ]
    return Response(
        content=bookmarks_html.render(rows),
        media_type="text/html; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="tessellate-bookmarks.html"'},
    )


@router.post("/import")
def import_bookmarks(body: BookmarksImport, session: Session = Depends(get_session)) -> dict:
    """Save the links of a browser's bookmarks file; ones already saved (by address) are skipped.

    The ids come back so the caller's Undo can take exactly these away.
    """
    rows, skipped = bookmarks_html.parse(body.html)
    made, twins = bookmarks.import_rows(session, rows)
    session.commit()
    return {"added": len(made), "ids": [b.id for b in made], "duplicates": twins, "skipped": skipped, "found": len(rows)}


@router.post("", status_code=201)
def create_bookmark(body: BookmarkCreate, session: Session = Depends(get_session)) -> dict:
    bookmark, twin = bookmarks.create(session, **body.model_dump())
    session.commit()
    return _to_out(bookmark, duplicate_of=twin)


@router.put("/{bookmark_id}")
def update_bookmark(
    bookmark_id: int, body: BookmarkUpdate, session: Session = Depends(get_session)
) -> dict:
    bookmark = bookmarks.update(session, bookmark_id, **body.model_dump())
    session.commit()
    return _to_out(bookmark)


@router.delete("/{bookmark_id}")
def delete_bookmark(bookmark_id: int, session: Session = Depends(get_session)) -> dict:
    """Delete a saved link and what attaches it (`bookmarks.delete` says why)."""
    bookmarks.delete(session, bookmark_id)
    session.commit()
    return {"deleted": True}
