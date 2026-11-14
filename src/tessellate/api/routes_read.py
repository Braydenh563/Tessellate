"""`GET /read`: the one reading of what was typed (CHAT_PLAN decision 47).

Quick add, the palette, search and chat each show what the app understood
before Enter (decision 50's chips); they ask here rather than reading the
words themselves, so a phrase means one thing everywhere. Served under the
unlock like every route, and at `/api/v1/read` for an outside client.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from tessellate.ai import offers, personal, reading
from tessellate.core.database import utcnow
from tessellate.core.deps import get_config, get_session

router = APIRouter(tags=["reading"])

#: Long enough for a sentence with a list in it; a reading is not a document.
MAX_CHARS = 2000


def _clock(tz_offset_minutes: int, now: str) -> datetime:
    clock = utcnow().astimezone(timezone(timedelta(minutes=tz_offset_minutes)))
    try:
        given = datetime.fromisoformat(now) if now else None
    except ValueError:
        given = None
    return given if given is not None and given.tzinfo is not None else clock


@router.get("/read")
def read_text(
    q: str = Query("", max_length=MAX_CHARS),
    tz_offset_minutes: int = Query(0, ge=-14 * 60, le=14 * 60),
    locale: str = Query("", max_length=16),
    surface: str = Query("", max_length=32),
    birthday: str = Query("", max_length=10),
    now: str = Query("", max_length=40),
    session: Session = Depends(get_session),
) -> dict:
    """The `Reading` of `q` on the person's own clock (`tz_offset_minutes`,
    as `/reminders/parse` takes it), as JSON. `now` (ISO 8601 with an offset)
    fixes the clock for a sweep that measures against a fixture date; one
    that does not parse, or has no offset, is ignored. "My birthday" is the
    one the notes give when none is sent."""
    clock = _clock(tz_offset_minutes, now)
    if not birthday and "birthday" in q.lower():
        birthday = str(get_config().get_preference("birthday", "") or "") or personal.birthday(personal.notes_of(session), clock.replace(tzinfo=None)) or ""
    context = {key: value for key, value in (("locale", locale), ("surface", surface), ("birthday", birthday)) if value}
    return reading.read(q, now=clock, context=context).json()


class OffersBody(BaseModel):
    #: A note, not a reading: the editor sends the whole draft.
    content: str = Field("", max_length=100_000)
    entry_id: int | None = None
    category: str | None = Field(None, max_length=200)
    tz_offset_minutes: int = Field(0, ge=-14 * 60, le=14 * 60)
    locale: str = Field("", max_length=16)
    now: str = Field("", max_length=40)
    #: The Capture title: a save files the title with the words (`withTitle`),
    #: so the filing offer reads it too (INBOX 1583). Never offered on.
    title: str = Field("", max_length=300)


@router.post("/read/offers")
def note_offers(body: OffersBody, session: Session = Depends(get_session)) -> dict:
    """What the note editor offers for the draft (`ai/offers.py`): reminder
    offers from its days, its sums checked, `[[links]]` to notes its names
    open, and the filing suggestion with its reason. A POST because a draft
    is longer than a query string should carry."""
    clock = _clock(body.tz_offset_minutes, body.now)
    found = offers.offers(session, body.content, now=clock, entry_id=body.entry_id,
                          category=body.category, locale=body.locale or None, title=body.title)
    return {"offers": found}


@router.get("/read/board")
def board_act(q: str = Query("", max_length=MAX_CHARS)) -> dict:
    """The board act `q` says (`acts.board_parse`: "arrange as a grid of
    3"), for the command palette over a board, or `{"act": null}`."""
    from tessellate.ai import acts

    return {"act": acts.board_parse(q)}


class DatesBody(BaseModel):
    texts: list[str] = Field(default_factory=list, max_length=200)
    tz_offset_minutes: int = Field(0, ge=-14 * 60, le=14 * 60)
    now: str = Field("", max_length=40)


@router.post("/read/dates")
def date_chips(body: DatesBody) -> dict:
    """The day each short text names (`offers.date_chip`), in order, null for
    one that names none: a board's stickies, read in one request."""
    clock = _clock(body.tz_offset_minutes, body.now)
    return {"dates": [offers.date_chip(text[:2000], now=clock) for text in body.texts]}


@router.get("/read/filter")
def phrase_filter(
    q: str = Query("", max_length=MAX_CHARS),
    tz_offset_minutes: int = Query(0, ge=-14 * 60, le=14 * 60),
    now: str = Query("", max_length=40),
    session: Session = Depends(get_session),
) -> dict:
    """The filters a search phrase reads as (`ai/filters.py`: "connected to
    Harbor", "untouched since June") and the notes they leave; `ids` is null
    when nothing was read, so the surface searches the words as before."""
    from tessellate.ai import filters

    clock = _clock(tz_offset_minutes, now)
    found = filters.read(q, clock)
    ids = filters.resolve(session, found["filters"], clock) if found["filters"] else None
    return {**found, "ids": ids}


@router.get("/read/words")
def setting_words() -> dict:
    """The groups of words that mean one thing ("dark", "night", "theme") and
    the words of a request that name nothing, for every search box's meaning
    layer (meaning.js, Brief 94)."""
    from tessellate.ai import meaning

    return meaning.table()


class NearRequest(BaseModel):
    q: str = Field(min_length=1, max_length=200)
    texts: list[str] = Field(max_length=600)


@router.post("/read/near")
def near_rows(req: NearRequest) -> dict:
    """Close in meaning (Brief 94): which of a search box's own rows are
    nearest the query, when an embedding model is on. Without one, says so
    (`available: false`) and the box keeps its word matches."""
    from tessellate.ai import meaning
    from tessellate.core import deps

    try:
        embeddings = deps.get_embeddings()
        ready = embeddings is not None and embeddings.is_ready()
    except Exception:  # noqa: BLE001  # no backend is a state, not an error
        ready = False
    if not ready:
        return {"available": False, "near": []}
    texts = [text[:300] for text in req.texts]
    return {"available": True, "near": meaning.near(req.q, texts, embeddings.embed_many)}


@router.get("/read/acts")
def act_rows() -> dict:
    """The act registry as the palette and Help show it (`acts.palette_rows`,
    `acts.capability_line`): one source for what the app does from a
    sentence."""
    from tessellate.ai import acts

    return {"rows": acts.palette_rows(), "capability": acts.capability_line()}


@router.get("/read/act")
def act_preview(
    q: str = Query("", max_length=MAX_CHARS),
    tz_offset_minutes: int = Query(0, ge=-14 * 60, le=14 * 60),
    now: str = Query("", max_length=40),
    session: Session = Depends(get_session),
) -> dict:
    """What a typed sentence would do as an act, written nowhere (CHAT_PLAN B24:
    "remind me Tuesday 9am lecture" in the palette shows its card before Chat
    runs it). `act` is None for a sentence that is not an act, or one that
    still lacks its time (Chat asks that, once); the line is the one Chat
    would say, the label the card's, and the steps are counted, never run."""
    from tessellate.ai import acts

    clock = _clock(tz_offset_minutes, now).replace(tzinfo=None)
    parsed = acts.parse(q, clock, [])
    if parsed is None or (parsed["intent"] == "reminder" and not parsed.get("time_given") and not parsed.get("on_list")):
        return {"act": None}
    planned = acts.preview(session, parsed, None)
    card = planned.get("card") or {}
    return {"act": {"intent": parsed["intent"], "line": planned.get("line") or "", "label": card.get("label") or "", "steps": len(card.get("steps") or [])}}
