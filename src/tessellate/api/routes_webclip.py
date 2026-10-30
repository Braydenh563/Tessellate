"""`POST /links/clip`: keep a web page as a note (WORLD_CLASS_PLAN D9).

The fetch, the address checks and the extraction are `core/webclip.py`; this
is the door, and the one rule that belongs at the door: **nothing goes online
unless the person has said the web may be used.** The clipper shares the web
reader's opt-in (`web_search_enabled`, Settings, Web search) rather than
having a switch of its own, because "may this app reach the web when I ask"
is one question, and two switches that answer it differently would be a
promise kept in one place and broken in the other.

The note goes through the same path as one typed into Capture
(`routes_entries.create_entry`), so it is filed, embedded and indexed like
any other, and a clipped page is found by search by its words.
"""

from __future__ import annotations

from urllib.parse import urlparse, urlunparse

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from tessellate.api import routes_entries
from tessellate.api.schemas import EntryCreate, EntryOut
from tessellate.core import deps, webclip
from tessellate.core.database import Entry
from tessellate.core.deps import get_session
from tessellate.entry import manager

router = APIRouter(prefix="/links", tags=["links"])

WEB_OFF = (
    "Clipping a page needs the web, and the web is turned off. Allow it in "
    "Settings, Web search, then clip the page again."
)


class ClipIn(BaseModel):
    url: str = Field(min_length=1, max_length=2000)


@router.post("/clip", response_model=EntryOut, status_code=201)
def clip(body: ClipIn, session: Session = Depends(get_session)) -> EntryOut:
    if not deps.get_config().get_preference("web_search_enabled", False):
        raise HTTPException(status_code=403, detail=WEB_OFF)
    try:
        fetched = webclip.fetch_page(body.url)
    except webclip.ClipRefused as exc:
        raise HTTPException(status_code=exc.status, detail=str(exc)) from exc
    url = fetched["url"]
    extracted = webclip.extract(fetched["html"], url)
    note = routes_entries.create_entry(
        EntryCreate(
            content=webclip.note_content(extracted, url),
            source_url=url,
            source_title=extracted["title"],
            defer_filing=True,
        ),
        session,
    )
    manager.log_action(session, "web_clipped", "entry", note.id, detail=url[:120])
    session.commit()
    return note


# --- the page the browser sends (row 24, fully local) ------------------------
#
# The bookmarklet in Settings, Import & export opens `clip.html` beside the
# page being read and hands it that page: its address, its title, its HTML as
# the browser has it (pages behind a sign-in the person can see included),
# and any text they had selected. Nothing is fetched, so the web switch above
# does not apply: the page is already on this computer.
#
# The text is somebody else's. It is stored with its `source_url`, which is
# what `manager.came_from_outside` reads, so the agent treats a turn that
# reads it as tainted and the prompt fences it as a note from outside.

CLIP_PAGE_MAX_SELECTION = 200_000
NOT_A_PAGE = "Only a web page's address (http or https) can be clipped."


class ClipPageIn(BaseModel):
    url: str = Field(min_length=1, max_length=2000)
    title: str = Field(default="", max_length=1000)
    html: str = Field(default="", max_length=webclip.CLIP_MAX_BYTES)
    selection: str = Field(default="", max_length=CLIP_PAGE_MAX_SELECTION)


class ClipPageOut(BaseModel):
    entry: EntryOut
    #: The page was clipped before: this is the note it made then.
    existing: bool


def _page_address(raw: str) -> str:
    url = webclip.clean_url(raw)
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise HTTPException(status_code=400, detail=NOT_A_PAGE)
    # The fragment names a place on the page, not a different page.
    return urlunparse(parsed._replace(fragment=""))


def _plain_title(raw: str, url: str) -> str:
    return " ".join(raw.split())[:300] or urlparse(url).hostname or "Clipped page"


@router.post("/clip-page", response_model=ClipPageOut, status_code=201)
def clip_page(body: ClipPageIn, response: Response, session: Session = Depends(get_session)) -> ClipPageOut:
    url = _page_address(body.url)
    already = session.scalar(
        select(Entry).where(Entry.source_url == url, Entry.is_deleted.is_(False)).order_by(Entry.id).limit(1)
    )
    if already is not None:
        response.status_code = 200
        return ClipPageOut(entry=routes_entries._to_out(session, already), existing=True)
    selection = body.selection.strip()
    if selection:
        extracted = {"title": _plain_title(body.title, url), "markdown": selection, "words": len(selection.split())}
    elif body.html.strip():
        extracted = webclip.extract(body.html, url)
    else:
        #: Nothing sent but the address: a bookmarklet fired on a blank page
        #: filled the notebook with hollow notes (audit 1030 Y12).
        raise HTTPException(status_code=422, detail="This page sent no text to clip. Reload it and clip again.")
    note = routes_entries.create_entry(
        EntryCreate(
            content=webclip.note_content(extracted, url),
            source_url=url,
            source_title=extracted["title"],
            defer_filing=True,
        ),
        session,
    )
    manager.log_action(session, "web_clipped", "entry", note.id, detail=f"from the browser: {url[:100]}")
    session.commit()
    return ClipPageOut(entry=note, existing=False)
