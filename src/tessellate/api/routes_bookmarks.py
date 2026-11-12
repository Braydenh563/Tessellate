"""Bookmarks: saved links to somewhere outside the notebook, create, list,
update, delete. The routes read the request and shape the answer; every
query is `repo/bookmarks.py`'s (INBOX 1499). Nothing here needs the AI.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response

from tessellate.api import paging
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from tessellate.core import deps, jobs, webclip
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
    icon: str = Field(default="", max_length=80)
    color: str = Field(default="", max_length=20)
    #: Fetch the page's icon and text after the save. Only the app's own Save sends it (the person pressed
    #: it with the web on); an agent, the MCP server or a script saving a link never goes online by itself.
    fetch: bool = False


class BookmarkUpdate(BaseModel):
    url: str | None = Field(default=None, min_length=1, max_length=2000)
    title: str | None = Field(default=None, max_length=200)
    note: str | None = Field(default=None, max_length=2000)
    pinned: bool | None = None
    is_read: bool | None = None
    group_name: str | None = Field(default=None, max_length=120)
    tags: list[str] | None = Field(default=None, max_length=40)
    icon: str | None = Field(default=None, max_length=80)
    color: str | None = Field(default=None, max_length=20)
    #: As on create: a new address is fetched only when the app's own edit asks.
    fetch: bool = False


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
        "icon": bookmark.icon or "",
        "color": bookmark.color or "",
        #: An address, not the bytes (PR 226 review): the list stays light and the icon is cached apart.
        "favicon": f"/bookmarks/{bookmark.id}/icon" if bookmark.has_icon else "",
        "excerpt": bookmark.excerpt or "",
        "has_text": bool(bookmark.has_text),
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


def _web_on() -> bool:
    return bool(deps.get_config().get_preference("web_search_enabled", False))


def _fetch(url: str) -> dict:
    """Fetch the page and return what to keep: its title, excerpt, text and icon (raises `webclip.ClipRefused`)."""
    fetched = webclip.fetch_page(url)
    extracted = webclip.extract(fetched["html"], fetched["url"])
    text = extracted["markdown"]
    favicon = ""
    href = webclip.page_icon_href(fetched["html"], fetched["url"])
    if href:
        try:
            favicon = webclip.fetch_icon(href)
        except webclip.ClipRefused:
            favicon = ""
    return {"title": extracted["title"], "excerpt": bookmarks.excerpt_of(text), "text": text, "favicon": favicon}


def _fetch_for(session: Session, bookmark) -> bool:
    """Fetch the link's page and keep what it found, unless its address changed meanwhile.

    The read transaction ends before the fetch (nothing is pending), so the row read after it is the
    current one: a fetch that took seconds never writes an old page's icon onto a link moved since.
    """
    url = bookmark.url
    session.commit()
    found = _fetch(url)
    session.refresh(bookmark)
    if bookmark.url != url:
        return False
    bookmarks.apply_fetch(bookmark, **found)
    session.commit()
    return True


def _refresh_after_save(bookmark_id: int) -> None:
    """Best effort, after the save has answered: a page that will not load leaves the link as it was.

    Runs on its own session (the request's is closed by now). Only when the web is on, so an offline
    notebook never makes a request it was not asked to."""
    session = deps.get_db().session()
    try:
        bookmark = session.get(bookmarks.Bookmark, bookmark_id)
        if bookmark is None or urlparse(bookmark.url).scheme not in ("http", "https"):
            return
        _fetch_for(session, bookmark)
    except Exception:  # noqa: BLE001 - a background refresh must never surface; the card keeps its glyph
        session.rollback()
    finally:
        session.close()


def _refresh_later(bookmark_id: int) -> None:
    #: On a listed jobs thread (the background registry), so the save answers at once and the icon follows.
    jobs.thread(f"bookmark-icon-{bookmark_id}", lambda: _refresh_after_save(bookmark_id))


@router.post("", status_code=201)
def create_bookmark(
    body: BookmarkCreate, session: Session = Depends(get_session)
) -> dict:
    fields = body.model_dump()
    fetch = fields.pop("fetch")
    bookmark, twin = bookmarks.create(session, **fields)
    session.commit()
    if fetch and twin is None and _web_on():
        _refresh_later(bookmark.id)
    return _to_out(bookmark, duplicate_of=twin)


@router.put("/{bookmark_id}")
def update_bookmark(
    bookmark_id: int, body: BookmarkUpdate, session: Session = Depends(get_session)
) -> dict:
    before = bookmarks.get(session, bookmark_id).url
    fields = body.model_dump()
    fetch = fields.pop("fetch")
    bookmark = bookmarks.update(session, bookmark_id, **fields)
    session.commit()
    if fetch and bookmark.url != before and _web_on():
        _refresh_later(bookmark.id)
    return _to_out(bookmark)


MOVED = "The link's address changed while its page was being fetched, so nothing was kept. Fetch it again."
WEB_OFF = "Fetching a page needs the web, and the web is turned off. Allow it in Settings, Web search."


@router.post("/{bookmark_id}/refresh")
def refresh_bookmark(bookmark_id: int, session: Session = Depends(get_session)) -> dict:
    """Fetch the page again and keep its icon, a short excerpt and its text (the link card, L3).

    The only thing here that goes online, so it asks the same switch the clipper does
    (`web_search_enabled`); with the web off nothing is requested and the card keeps the glyph of its kind.
    A page that will not answer leaves the link as it was and says why.
    """
    bookmark = bookmarks.get(session, bookmark_id)
    if not _web_on():
        raise HTTPException(status_code=403, detail=WEB_OFF)
    if urlparse(bookmark.url).scheme not in ("http", "https"):
        raise HTTPException(status_code=400, detail="Only a web page can be fetched.")
    try:
        kept = _fetch_for(session, bookmark)
    except webclip.ClipRefused as exc:
        raise HTTPException(status_code=exc.status, detail=str(exc)) from exc
    if not kept:
        raise HTTPException(status_code=409, detail=MOVED)
    return _to_out(bookmark)


@router.get("/{bookmark_id}/icon")
def bookmark_icon(
    bookmark_id: int, if_none_match: str | None = Header(default=None), session: Session = Depends(get_session)
) -> Response:
    """The site's icon the last fetch kept, as an image of its own (the list carries only this address).

    An ETag over the bytes, so a card asks again cheaply and a changed icon shows; `nosniff` and a
    CSP that runs nothing, since an SVG opened from here would otherwise be a page of this origin.
    """
    data = bookmarks.get(session, bookmark_id).favicon or ""
    head, _, payload = data.partition(",")
    kind = head.removeprefix("data:").removesuffix(";base64")
    try:
        body = base64.b64decode(payload, validate=True) if head.endswith(";base64") else b""
    except (binascii.Error, ValueError):
        body = b""
    if not body or not kind.startswith("image/"):
        raise HTTPException(status_code=404, detail="This link has no icon.")
    etag = '"' + hashlib.sha256(body).hexdigest()[:16] + '"'
    headers = {
        "ETag": etag,
        "Cache-Control": "private, max-age=3600, must-revalidate",
        "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; sandbox",
    }
    if if_none_match == etag:
        return Response(status_code=304, headers=headers)
    return Response(content=body, media_type=kind, headers=headers)


@router.get("/{bookmark_id}/text")
def bookmark_text(bookmark_id: int, session: Session = Depends(get_session)) -> dict:
    """The page text the last fetch kept, apart from the list so a long shelf stays light."""
    return {"text": bookmarks.get(session, bookmark_id).page_text or ""}


@router.delete("/{bookmark_id}")
def delete_bookmark(bookmark_id: int, session: Session = Depends(get_session)) -> dict:
    """Delete a saved link and what attaches it (`bookmarks.delete` says why)."""
    bookmarks.delete(session, bookmark_id)
    session.commit()
    return {"deleted": True}
