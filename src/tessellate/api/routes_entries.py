"""Capture, read, edit, soft-delete, restore, and link entries.

Handlers are plain `def` (not async) on purpose: FastAPI then runs them
in a threadpool, which keeps the server responsive while blocking AI
calls run (plan §4).
"""

from __future__ import annotations

import contextlib
import json
import logging
import re
from datetime import date
from types import SimpleNamespace

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from sqlalchemy.orm import Session

from tessellate.ai import (
    extractor,
    janitor,
    librarian,
)
from tessellate.ai.ollama_client import OllamaError
from tessellate.api import paging
from tessellate.api.downloads import attachment_headers, safe_filename
from tessellate.api.edit_conflicts import (
    content_hash,
    entity_tag,
    refuse_if_stale,
    refuse_if_tags_stale,
    refuse_unless_match,
)
from tessellate.api import entry_out
from tessellate.api.routes_entries_refs import _reference_rows_batch
from tessellate.api.schemas import (
    ContextBody,
    EntryCreate,
    EntryOut,
    EntryUpdate,
)
from tessellate.core import companion_events, deps, events, vault
from tessellate.core.database import (
    EmbeddingRecord,
    Entry,
    utcnow,
)
from tessellate.core.deps import get_session
from tessellate.core.events import ACTOR_USER_AND_AI
from tessellate.core.validation_copy import Said
from tessellate.entry import manager, private_space
from tessellate.entry import capture, filing_background, listing, manager_wiki, tag_reasons, tag_suggestions
from tessellate.entry import manager_text
from tessellate.entry import manager_purge
from tessellate.entry import service as entry_service
from tessellate.repo import content as content_repo
from tessellate.repo.content import NOTES

router = APIRouter(prefix="/entries", tags=["entries"])

#: Read by tests/test_connection_labels_1442.py, which names the label by its
#: old home; the one definition is `entry_service.connection_label`.
_connection_label = entry_service.connection_label

logger = logging.getLogger("tessellate.api.entries")
















#: A note longer than this, opened, is the in-app companion's reading glasses (`avatars.js` `nameMarkBuddyNoteOpened`).
LONG_NOTE_CHARS = 1200


def _kept_private(session: Session, entry) -> bool:  # noqa: ANN001
    """A private note, or one in a private space: the desk companion hears only the generic kind for these."""
    return bool(entry.is_private) or private_space.is_private_space(session, entry.workspace_id)




















def _existing_entry(session: Session, entry_id: int):  # noqa: ANN202
    # `manager.get_entry` is `session.get(Entry, entry_id)` under the hood
    # (memorymap/entry/manager.py); going through `deps.get_or_404` directly
    # is equivalent and consolidates the 404.
    return deps.get_or_404(session, Entry, entry_id, "That note could not be found.")








































def _apply_flags(session: Session, entry, body) -> None:  # noqa: ANN001
    """Colour (null clears it) and draft from an edit, each saved when it moves."""
    if "colour" in body.model_fields_set and body.colour != entry.colour:
        entry.colour = body.colour
        session.commit()
    if body.is_draft is not None and body.is_draft != entry.is_draft:
        entry.is_draft = body.is_draft
        session.commit()

















@router.post("", response_model=EntryOut, status_code=201)
def create_entry(body: EntryCreate, session: Session = Depends(get_session)) -> EntryOut:
    """Save a new note (`capture.create`); the filing thread starts after the answer is shaped."""
    try:
        made = capture.create(session, body)
    except private_space.NeedsKey as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    out = entry_out.to_out(session, made.entry, filed_by=made.filed_by, similar=entry_out.similar_out(made.similar))
    capture.start_background(made)
    return out


# --- D6: the journal's daily note. What makes a note one, and why the date is
# the caller's, is in `entry/service.py`; these routes parse and shape.


class DailyDayOut(BaseModel):
    date: str
    written: bool


class DailyJournalOut(BaseModel):
    #: The caller's today, echoed, so a client that let the server default it
    #: can see which day the answer is about.
    through: str
    #: Oldest first, one entry per day in the window.
    days: list[DailyDayOut]
    #: Days written in a row, counting back from `through`.
    streak: int


def _daily_date(raw: str) -> date:
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise HTTPException(
            status_code=422, detail="Write a journal date as year-month-day, like 2026-10-04."
        ) from exc


@router.get("/daily", response_model=DailyJournalOut)
def daily_journal(
    through: str | None = None,
    days: int = Query(default=entry_service.DAILY_WINDOW_DAYS, ge=1, le=entry_service.DAILY_WINDOW_MAX),
    session: Session = Depends(get_session),
) -> DailyJournalOut:
    """Which of the last `days` days have a journal entry, and the streak
    (`entry_service.journal`, which lets today be empty).

    Declared before `/{entry_id}` so FastAPI does not match "daily" as an
    entry id and answer 422 instead (the ordering trap `/media/orphans` in
    routes_files.py carries the same comment about).
    """
    #: Today on the user's clock (audit 1028 K22): a LAN phone in another zone
    #: saw its streak break at the server's midnight.
    from tessellate.core.config import user_now

    last = _daily_date(through) if through else user_now(deps.get_config()).date()
    window, streak = entry_service.journal(session, last, days)
    return DailyJournalOut(
        through=last.isoformat(),
        days=[DailyDayOut(date=day.isoformat(), written=written) for day, written in window],
        streak=streak,
    )


@router.get("/daily/{day}", response_model=EntryOut)
def daily_note(day: str, session: Session = Depends(get_session)) -> EntryOut:
    """One day's journal entry, or 404 if nothing was written that day.

    Read-only, and the writing half is the POST below. The obvious shape for
    D6 is one GET that creates when it has to, and it was written that way
    first: a GET that writes is the shape a reviewer is right to stop, because
    the CSRF defence in `core/security.py` judges *methods*, and an endpoint
    that makes a row on a GET is outside it by construction.
    """
    found = entry_service.daily_note(session, _daily_date(day))
    if found is None:
        raise HTTPException(status_code=404, detail="Nothing is written on that day yet.")
    return entry_out.to_out(session, found)


@router.post("/daily/{day}", response_model=EntryOut)
def open_daily_note(day: str, session: Session = Depends(get_session)) -> EntryOut:
    """One day's journal entry, made if it is not there yet.

    "Creates or returns", which is what makes the key safe to press from
    anywhere: splitting it into a lookup plus a conditional create puts the
    race between two windows of the same app (or two presses of the key) back
    exactly where this endpoint exists to remove it. 200 rather than 201 for
    the same reason: whether this call made the note is not the caller's
    business and is not stable between two presses a second apart.
    """
    return entry_out.to_out(session, entry_service.open_daily_note(session, _daily_date(day)))


class FilingStopBody(BaseModel):
    action: str = "keep"


@router.post("/{entry_id}/filing/stop")
def stop_filing_one(
    entry_id: int, body: FilingStopBody, session: Session = Depends(get_session)
) -> dict:
    """Stop filing one note by hand (`entry_service.stop_filing`)."""
    if body.action not in entry_service.FILING_STOP_ACTIONS:
        raise HTTPException(status_code=422, detail="Pick keep or fallback.")
    entry = _existing_entry(session, entry_id)
    stopped, category = entry_service.stop_filing_one(session, entry, body.action)
    return {"id": entry.id, "stopped": stopped, "category": category}


class FilingDecisionBody(BaseModel):
    #: True: the person keeps the janitor's category, so the note leaves the
    #: review queue and re-evaluate leaves it alone. False is Accept's Undo.
    accepted: bool = True


@router.post("/{entry_id}/filing", response_model=EntryOut)
def decide_filing(
    entry_id: int, body: FilingDecisionBody, session: Session = Depends(get_session)
) -> EntryOut:
    """The review queue's Accept (`entry_service.accept_filing`)."""
    entry = NOTES.writable(session, entry_id)
    entry_service.accept_filing(session, entry, body.accepted)
    return entry_out.to_out(session, entry)


@router.get("/{entry_id}/filing")
def filing_status(entry_id: int, session: Session = Depends(get_session)) -> dict:
    """Where a note filed in the background ended up, the one thing the composer polls.

    Deliberately not `GET /entries/{id}`: that serialises links, documents,
    dates and attachments through four more queries, and a poller running
    every second while a note settles would pay all of it to read three
    fields. This is the whole of what the "Filed under X" notification
    needs.
    """
    entry = _existing_entry(session, entry_id)
    # **A note is never pending with nothing working on it.** The filing job
    # lives in this process's queue, so a note saved moments before the app
    # closed came back "pending" on the next launch with no job behind it,
    # and its card said "Filing…" forever (owner, 0.3.31: "it still looks
    # like it is endlessly filing"). Asking here re-queues it; the dedupe
    # key makes that a no-op while a job for it is already queued or running.
    if (getattr(entry, "filing_state", "") or "") == "pending":
        filing_background._queue_filing(entry)
    return entry_service.filing_status(session, entry)




class SuggestTagsBody(BaseModel):
    content: str
    tags: list[str] = Field(default_factory=list)
    #: Capture's title field: a note's title says what it is, so it counts
    #: with its first line (`ai/tagging.lead`).
    title: str = Field(default="", max_length=300)

#: Said once per process, not once per keystroke pause.
_SAID_ONCE: set[str] = set()


@router.post("/suggest-tags")
def suggest_tags_for_draft(
    body: SuggestTagsBody, session: Session = Depends(get_session)
) -> dict:
    """Tag suggestions for a note that doesn't exist yet: the other half of
    a report that `/{entry_id}/reevaluate` only ever covered post-save:
    "the ai and application doesnt suggest tags either before creating a
    new note or after." "After" already had a path (buried in a kebab
    menu action, easy to never find); "before" had none at all. Reuses
    `librarian.suggest_tags` directly on the draft's own text: it only
    ever needed a string and the tags already on it, never a saved
    `Entry`, so the Capture form can offer suggestions while the user is
    still typing, before Save exists to be clicked.
    """
    content = body.content.strip()
    if body.title.strip() and content:
        content = f"# {body.title.strip()}\n\n{content}"
    if not content:
        return {"suggested_tags": [], "suggested_tag_reasons": {}}
    #: **No model, no model call** (measured on the running app: with none
    #: running, every pause in Capture asked the client for a completion from
    #: model "" and logged a WARNING with its traceback, three per note typed,
    #: and offered nothing). Then, and when the model fails, the notebook's own
    #: tags answer, the fallback filing already uses (`_suggest_after_filing`).
    model_manager, ollama = deps.get_model_manager(), deps.get_ollama()
    suggested: list[str] = []
    if model_manager.utility_model() and ollama.is_running():
        try:
            suggested = librarian.suggest_tags(
                content, body.tags, model_manager, ollama, vocabulary=tag_suggestions.tag_vocabulary(session)
            )
        except Exception:
            logger.info("tag suggestions from the model failed; using the notebook's own", exc_info=True)
    else:
        if "no-model-tags" not in _SAID_ONCE:
            _SAID_ONCE.add("no-model-tags")
            logger.info("no model running: tag suggestions come from the notebook's own tags")
    offered = tag_suggestions.engine_tags(session, content, body.tags, suggested, None)
    return {"suggested_tags": offered, "suggested_tag_reasons": tag_reasons.reasons(content, offered)}


class SuggestedTagsBody(BaseModel):
    take: list[str] = Field(default_factory=list, max_length=20)
    discard: list[str] = Field(default_factory=list, max_length=20)
    #: Turned down before, offered again (the owner, 2026-10-10: "is there a
    #: way to undo it or see the list"): off `discarded_tags`, back into the
    #: suggestions.
    restore: list[str] = Field(default_factory=list, max_length=20)
    #: True stops suggesting tags for this note, False starts again (brief 89).
    mute: bool | None = None


def _discard_tags(entry, body) -> dict[str, str]:  # noqa: ANN001
    """Remember the tags turned down on this note (the last 200), and return the
    ones taken back, keyed by their folded form."""
    gone = tag_suggestions.json_tags(entry.discarded_tags)
    gone_folded = {tag.casefold() for tag in gone}
    gone += [tag.strip() for tag in body.discard if tag.strip() and tag.strip().casefold() not in gone_folded]
    restored = {tag.strip().casefold(): tag.strip() for tag in body.restore if tag.strip()}
    gone = [tag for tag in gone if tag.casefold() not in restored]
    entry.discarded_tags = json.dumps(gone[-200:])
    return restored


@router.post("/{entry_id}/suggested-tags", response_model=EntryOut)
def answer_suggested_tags(
    entry_id: int, body: SuggestedTagsBody, session: Session = Depends(get_session)
) -> EntryOut:
    """Take or discard the tags filing suggested (INBOX 440). A taken tag is
    added like one typed by hand; a discarded one is remembered so no later
    filing pass offers it on this note again."""
    entry = NOTES.writable(session, entry_id)
    if body.mute is not None:
        entry.tag_suggest_off = body.mute
    offered = {tag.casefold(): tag for tag in tag_suggestions.json_tags(entry.suggested_tags)}
    take = [offered.get(tag.casefold(), tag.strip()) for tag in body.take if tag.strip()]
    if take:
        have = manager.entry_tags(entry)
        folded = {tag.casefold() for tag in have}
        manager.update_entry(session, entry, tags=have + [tag for tag in take if tag.casefold() not in folded])
    restored = _discard_tags(entry, body)
    answered = {tag.casefold() for tag in [*take, *body.discard]}
    kept = [tag for tag in tag_suggestions.json_tags(entry.suggested_tags) if tag.casefold() not in answered]
    kept_folded = {tag.casefold() for tag in kept}
    entry.suggested_tags = json.dumps(kept + [tag for key, tag in restored.items() if key not in kept_folded])
    session.commit()
    return entry_out.to_out(session, entry)


@router.post("/{entry_id}/context", response_model=EntryOut)
def add_context(
    entry_id: int, body: ContextBody, session: Session = Depends(get_session)
) -> EntryOut:
    """Append context to an existing note and let the janitor rethink the
    category with the fuller picture. If the user filed this
    entry themselves, the category is left alone, their call stands."""
    entry = NOTES.writable(session, entry_id)
    # Appending to the ciphertext made the note unreadable for good, and the
    # filing below would read its text: a private note is edited in its own
    # editor (same refusal as generate-title and remove-title).
    if entry.is_private:
        raise HTTPException(
            status_code=400, detail="Make this note readable first: private notes can't be edited here."
        )
    entry.content = f"{entry.content}\n\n--- added context ---\n{body.text.strip()}"
    manager.mark_edited(entry)
    manager.log_action(session, "edited", "entry", entry.id, "context added")
    session.commit()

    # The old vector describes the old text, refresh it, best effort.
    try:
        session.execute(
            sa_delete(EmbeddingRecord).where(EmbeddingRecord.entry_id == entry.id)
        )
        session.commit()
    except Exception:  # noqa: BLE001  # never fail the edit over the index
        logging.getLogger("tessellate.embeddings").warning(
            "couldn't clear the stale vector for entry %s", entry.id, exc_info=True
        )
        session.rollback()
    else:
        deps.store_quietly(session, entry)

    filed_by = None
    if not entry.user_filed:
        try:
            category, confidence, filed_by = janitor.categorise(
                session,
                entry.content,
                deps.get_embeddings(),
                deps.get_model_manager(),
                deps.get_ollama(),
                exclude_entry_id=entry.id,  # don't let it anchor to itself
            )
            if filed_by != "none":
                manager.record_filing(
                    session, entry, category,
                    by=janitor.filed_by_label(
                        filed_by, confidence, deps.get_model_manager(), deps.get_embeddings()
                    ),
                )
                entry.ai_confidence = confidence
                # The same two lines as the create paths: a category the AI
                # chose here is one a later move by hand corrects, and without
                # the flag that correction went unrecorded (Brief 13).
                if janitor.settled_state(filed_by) != "done":
                    entry.filing_state = janitor.settled_state(filed_by)
                session.commit()
        except Exception:
            logger.warning("re-filing after new context failed", exc_info=True)
            filed_by = None  # AI down, the note keeps its old category

    return entry_out.to_out(session, entry, filed_by=filed_by)


class ImproveBody(BaseModel):
    text: str
    mode: str = "proofread"  # proofread | rewrite | concise | custom
    # Only read when mode == "custom", the user's own instruction, in their
    # own words, instead of picking from the three presets. Length-capped to
    # match the input's own maxlength; this is one line of steering, not a
    # second prompt.
    custom_instruction: str | None = Field(default=None, max_length=200)


@router.post("/improve")
def improve_writing(body: ImproveBody) -> dict:
    """Return an AI-polished version of some note text without saving it, 
    the UI shows a before/after and the user decides. Never
    touches the note itself; the AI is a servant, not a gatekeeper."""
    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="There's no text to improve.")
    custom_instruction = (body.custom_instruction or "").strip()
    if body.mode == "custom" and not custom_instruction:
        raise HTTPException(
            status_code=400, detail="Say what you want changed, then try again."
        )
    if not deps.get_ollama().is_running():
        #: O7 (INBOX 904 B33): proofreading is the app's own with no model;
        #: rewording is writing, and says so.
        if body.mode != "proofread":
            raise HTTPException(
                status_code=503,
                detail="Rewording needs a model (Settings, Models). Proofread works without one.",
            )
        from tessellate.ai import proofread

        improved, changes = proofread.proofread(text)
        return {
            "original": text, "improved": improved, "mode": body.mode, "by": "composer",
            "said": proofread.said(changes, text), "truncated": proofread.covered(text) < len(text),
        }
    try:
        improved = librarian.improve_writing(
            text,
            body.mode,
            deps.get_model_manager(),
            deps.get_ollama(),
            custom_instruction=custom_instruction,
        )
    except OllamaError as exc:
        # The provider's own text names the model and carries the transport's
        # error; it belongs in the log, not in the toast.
        logger.warning("improve writing failed", exc_info=True)
        raise HTTPException(status_code=502, detail=librarian.AI_FAILED_MESSAGE) from exc
    return {"original": text, "improved": improved, "mode": body.mode}








#: A page of the plain list, not a hard ceiling on notebook size, the
#: frontend fetches pages in a loop until X-Total-Count says it has
#: everything (loadEntries in app.js). Bounds each individual request so a
#: notebook that has grown for years can't make one response unbounded; the
#: max just stops a client from asking for one absurdly large page.
ENTRIES_PAGE_SIZE = 1000
ENTRIES_PAGE_SIZE_MAX = 5000
#: How many notes one `?ids=` read may name: more than any one change touches
#: (a bulk action over more falls back to the paged list on the client).
ENTRIES_BY_IDS_MAX = 200


#: The most characters `?preview=` may ask for: past it a caller wants the text.
ENTRIES_PREVIEW_MAX = 2000












def _note_ids(ids: str, aside: bool) -> list[int]:
    """`?ids=` as numbers (FE-05): at most ENTRIES_BY_IDS_MAX, and only from the notes list."""
    parts = [part.strip() for part in ids.split(",") if part.strip()]
    if not all(part.isdigit() for part in parts) or len(parts) > ENTRIES_BY_IDS_MAX:
        raise HTTPException(
            status_code=422,
            detail=f"Ask for up to {ENTRIES_BY_IDS_MAX} note ids, as numbers.",
        )
    if aside:
        raise HTTPException(status_code=422, detail="Note ids are read from the notes list only.")
    return [int(part) for part in parts]


@router.get("", response_model=list[EntryOut])
def list_entries(
    response: Response,
    deleted: bool = False,
    archived: bool = False,
    semantic: bool = False,
    q: str = "",
    limit: int = Query(default=ENTRIES_PAGE_SIZE, ge=1, le=ENTRIES_PAGE_SIZE_MAX),
    offset: int = Query(default=0, ge=0),
    cursor: str | None = paging.cursor_param(),
    #: `after` is the same cursor under the name ARCH-04's first cut gave
    #: it; one keyset, read by `paging` either way.
    after: str = Query(default="", max_length=512),
    # **This list is the notes list, so boards are not in it by default.**
    #
    # Reported: "I made a mindmap naming it test and I think it came up as a
    # new note??", it did, on every surface built on this response. A board
    # (and a mind map, which is a board with `type: "map"`) is an `Entry`, so
    # it came back here with everything else; measured on a notebook with
    # nine maps, ten of the Notes list's twelve rows were maps.
    #
    # The default is the fix, rather than a filter in each of the four
    # surfaces that draw notes, because "the same object drawn five ways" is
    # this app's recurring failure and four client-side filters is that shape
    # exactly. `boards=only` is how the two callers that genuinely want boards
    # (the `[[wiki]]` resolver and the editor's `@` picker) ask for them, and
    # `boards=include` restores the old response for anything wanting both.
    boards: str = Query(default=manager.BOARDS_EXCLUDE),
    # **Just these notes, of the same list** (audit 2026-10-05, FE-05). Every
    # save used to re-read the whole notebook (27 requests and 5.3 MB at
    # 5,010 notes); the client now asks for the notes a change touched and
    # patches them in. An id outside the view (binned, archived, a board) is
    # simply absent, which is how the client learns to drop it, and
    # `X-Total-Count` stays the whole list's size so it can check its patched
    # list against this one. No side effect: unlike `GET /entries/{id}`,
    # this is not opening the note.
    ids: str = Query(default="", description="Comma-separated note ids"),
    #: **Each note's first characters, not all of it** (audit 1031 BK10): 0
    #: keeps the whole text, which every caller in the app that holds the list
    #: for search and the card body still asks for. `content_truncated` marks
    #: a clipped row; `content_hash` stays the whole text's.
    preview: int = Query(default=0, ge=0, le=ENTRIES_PREVIEW_MAX),
    session: Session = Depends(get_session),
) -> list[EntryOut]:
    """Normal list, the recycle bin when ?deleted=true, the archive when
    ?archived=true, or a concept search. `deleted` and `archived` are
    mutually exclusive views (each its own held-back set), not filters
    that combine: same as `deleted` already worked before `archived`
    existed.

    `?semantic=true&q=…` is the one case the browser cannot do for itself: the
    notes list is filtered client-side by keyword, but cosine distance needs
    the vectors, which only live here.

    `limit`/`offset` page the plain list; `X-Total-Count` on the response
    says the real size regardless of the page, so a caller knows when it has
    everything. Was genuinely unbounded before, every note, every load, no
    matter the notebook's size: which is real risk for a "just works" local
    app that's supposed to degrade gracefully rather than time out or OOM.
    """
    cursor = cursor or after or None
    if boards not in manager.BOARD_MODES:
        raise HTTPException(
            status_code=422,
            detail=f"Pick one of these board options: {', '.join(manager.BOARD_MODES)}.",
        )
    if semantic and q:
        try:
            matched = listing.semantic(session, q, deleted=deleted, archived=archived, boards=boards)
        except listing.SemanticNotReady as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        response.headers["X-Total-Count"] = str(len(matched))
        return entry_out.previewed(entry_out.to_out_bulk(session, matched), preview)

    if ids:
        entries, total = listing.by_ids(session, _note_ids(ids, deleted or archived), boards=boards)
    elif q and not (deleted or archived) and (found_text := listing.text_match(session, q, boards=boards, offset=offset, limit=limit)) is not None:
        #: The filter box's literal match over whole bodies, in list order and paged (L810).
        entries, total = found_text
    elif deleted or archived:
        page = paging.resolve(response, offset=offset, limit=limit, cursor=cursor)
        entries, total = listing.bin_page(session, deleted=deleted, limit=limit, offset=page.offset)
        page.finish(len(entries), total)
    else:
        after_key = paging.read_keyset(cursor, 3) if cursor else None
        found = listing.notes_page(session, limit=limit, offset=offset, boards=boards, after=after_key)
        entries, total = found.entries, found.total
        if found.next_key is not None:
            response.headers[paging.NEXT_CURSOR] = paging.keyset_cursor(found.next_key)
    response.headers["X-Total-Count"] = str(total)
    return entry_out.previewed(entry_out.to_out_bulk(session, entries), preview)


@router.get("/query")
def query_entries(q: str = "", session: Session = Depends(get_session)) -> dict:
    """The notes a live query matches, with the table view's columns (`listing.query`)."""
    return listing.query(session, q)


@router.get("/changes")
def entry_changes(
    since: str = Query(default="", max_length=40),
    session: Session = Depends(get_session),
) -> dict:
    """Which notes changed since `since`, for another device's live update (`listing.changes`)."""
    try:
        return listing.changes(session, since)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


# Declared before /{entry_id} so "most-accessed" isn't parsed as an id.
@router.get("/most-accessed", response_model=list[EntryOut])
def most_accessed(session: Session = Depends(get_session)) -> list[EntryOut]:
    """Top entries by how often they've been opened or matched a
    question: the quick-access dashboard."""
    entries = manager.most_accessed_entries(session, limit=5)
    return entry_out.to_out_bulk(session, entries)


# Onboarding's own "is this notebook empty" check: deliberately just a
# number (never the full /entries payload) so the first-run tour can decide
# whether to offer example notes without pulling a real notebook's worth of
# content over the wire just to find out it isn't empty.
@router.get("/count")
def count_entries(session: Session = Depends(get_session)) -> dict:
    return {"count": manager.count_notes(session)}






@router.post("/seed-examples")
def seed_example_entries(session: Session = Depends(get_session)) -> dict:
    """The onboarding tour's "add example notes" offer (ROADMAP.md's
    onboarding item). Refuses on any notebook that already has a note, 
    see `manager.seed_example_notes`'s own guard."""
    created = manager_wiki.seed_example_notes(session)
    return {"created": created}


#: How many notes one counts call may cover. A page of the list is at most
#: `ENTRIES_PAGE_SIZE` on the client (50); anything past that is a caller
#: asking for a report, not a chip row.
REFERENCE_COUNT_IDS_MAX = 60


@router.get("/reference-counts")
def entry_reference_counts(
    ids: str = Query(default="", description="Comma-separated note ids"),
    session: Session = Depends(get_session),
) -> dict:
    """Per note, how many things point at it, by kind, for one page at once.

    INBOX 246's third gap. A card showed nothing until Connections was opened,
    so a note on two boards and in three documents looked exactly like a note
    nothing had ever touched. The row on the card needs a number per kind and
    nothing else, and it needs it for every note on screen in one round trip:
    fifty cards asking `/references` each would be fifty scans per render.

    One reader. The numbers come from the same `_reference_rows` the
    Referenced-by row draws, so the chip and the row cannot disagree about
    what counts as a reference (the LIKE-then-verify rule, the deleted-note
    rule, the board-versus-map rule all live there once).

    A static path before the `/{entry_id}/...` routes on purpose: FastAPI
    matches in declaration order, and `{entry_id}` is typed `int`, so
    "reference-counts" would 422 rather than fall through if it came second.
    """
    wanted: list[int] = []
    for part in ids.split(","):
        part = part.strip()
        if part.isdigit():
            wanted.append(int(part))
    wanted = wanted[:REFERENCE_COUNT_IDS_MAX]
    if not wanted:
        return {"counts": {}}
    #: One query for the page's rows, then the reader per note. Rows that do
    #: not exist or are deleted are simply absent from the answer, so a stale
    #: id on the client is a missing key rather than a 404 that fails the
    #: whole page's chips.
    entries = session.scalars(
        select(Entry).where(Entry.id.in_(wanted), Entry.is_deleted.is_(False))
    ).all()
    counts: dict[str, dict[str, int]] = {}
    #: The whole page in one go (`_reference_rows_batch`): the per-note reader
    #: this called was four statements a card, and sixty cards at every unlock.
    page = _reference_rows_batch(session, list(entries))
    for entry in entries:
        by_kind: dict[str, int] = {}
        for row in page[entry.id]:
            by_kind[row["kind"]] = by_kind.get(row["kind"], 0) + 1
        by_kind["total"] = sum(by_kind.values())
        counts[str(entry.id)] = by_kind
    return {"counts": counts}


@router.get("/{entry_id}", response_model=EntryOut)
def get_entry(
    entry_id: int,
    response: Response,
    deleted: bool = False,
    open: bool = False,  # noqa: A002 - the query word is the contract
    session: Session = Depends(get_session),
) -> EntryOut:
    """One entry. `?deleted=true` also reaches into the bin.

    **Only `?open=1` counts as an open** (audit 1031 N5). The graph hover card,
    the swipe sheet, the chat agent and the image layout all read a note this
    way without a person reading it, and each bumped "Views", the "most used"
    sort and the Continue pill; a read is not an open unless the caller says
    a person is looking at the note.

    The bin used to be a panel that listed every deleted note with its full
    text, so "read a binned note before deciding whether to restore it" came
    free. The Library shows a preview instead, which is right for a grid of
    mixed things and wrong as the *only* way to see a note you are about to
    delete for good: so the reader needs a way to fetch one binned note.

    Two things stay different from a live read, and both are deliberate:
    a deleted note is only reachable when the caller says so (a stale link to
    a binned note should still 404 rather than quietly resurrect it), and
    reading one does **not** count as using it. `access_count` feeds
    "most accessed", and a note in the bin climbing that list because you
    looked at it on the way to deleting it is the counter lying.
    """
    entry = _existing_entry(session, entry_id)
    if entry.is_deleted and not deleted:
        raise HTTPException(status_code=404, detail="That note could not be found.")
    if open and not entry.is_deleted:
        entry.access_count += 1  # opening an entry counts as using it
        #: And on which day (WORLD_CLASS_PLAN section 17 row 5): "most opened
        #: this month" cannot be read off an all-time count.
        from tessellate.entry import opens

        opens.record_open(session, entry.id)
        # And *when*, which is the half the dashboard's Continue pill needs:
        # a count cannot answer "the note I was last in", and `updated_at`
        # only moves when the text changes, so reading an old note left the
        # pill pointing at whatever was newest. Same guard as the count: a
        # note read on its way out of the bin has not been come back to.
        entry.last_opened_at = utcnow()
        #: The in-app companion's reading glasses and covered eyes, for the desk one (W31): a kind and a time. A private
        #: note is only ever the generic kind (not its length, not which note).
        if _kept_private(session, entry):
            companion_events.record("private_note")
        elif len(entry.content or "") > LONG_NOTE_CHARS:
            companion_events.record("long_note")
    if not entry.is_deleted:
        # A private note has no audit trail at all otherwise, encrypted at
        # rest and invisible to the AI is the whole promise, but nothing
        # recorded *when* one was actually opened and decrypted for
        # reading, which is the one thing that would tell you if that
        # promise had ever been tested. Scoped to private notes only: every
        # other note already has plenty of activity logged elsewhere (see
        # the Library's own "activity is 93%+ of a real notebook" note) and
        # doesn't need a second entry for the same open.
        # Only when the vault is actually open, readable_content() returns
        # a placeholder ("Private note: unlock to read it.") rather than
        # the real text when it's locked, and logging "decrypted" for a
        # request that decrypted nothing is worse than not logging at all:
        # a trail meant to build confidence that lies about what happened
        # is the one bug this feature cannot afford.
        if bool(getattr(entry, "is_private", False)) and vault.key() is not None:
            manager.log_action(session, "decrypted", "entry", entry.id)
        session.commit()
    out = entry_out.to_out(session, entry)
    #: B7: the note's version as an HTTP entity tag, the same text hash the
    #: editor already sends back as `base_hash`, so a client that never reads
    #: the body's fields can still say "only if it is still this version" with
    #: `If-Match` on its write (`refuse_unless_match`).
    response.headers["ETag"] = entity_tag(out.content_hash)
    return out


def _refuse_while_sealed(entry) -> None:  # noqa: ANN001
    """Export and history hand out a note's text, so a locked private note
    answers 409 rather than a placeholder that looks like the note (INBOX
    1437). The same gate as writes: the person unlocks, then asks again."""
    if manager.note_is_sealed(entry.is_private):
        raise HTTPException(status_code=409, detail="Unlock first.")


@router.get("/{entry_id}/export.md")
def export_entry(entry_id: int, session: Session = Depends(get_session)) -> Response:
    """One note's own text, as a download, BACKLOG.md §95 item D.14: "Full
    export exists. There is no way to hand one note to someone."

    Mirrors `routes_documents.py`'s `export_markdown` (same route shape,
    same `Content-Disposition` filename sanitising) rather than reusing it
    directly: a note has no `file_type` the way a document does, so there
    is no second branch to share, and the two routes would only be coupled
    by the part that's already this short.

    A locked private note answers 409 "Unlock first." (`_refuse_while_sealed`):
    a download named like the note and holding a placeholder is a file that
    looks like the note and is not.
    """
    entry = _existing_entry(session, entry_id)
    if entry.is_deleted:
        raise HTTPException(status_code=404, detail="That note could not be found.")
    _refuse_while_sealed(entry)
    content = manager_text.readable_content(entry)
    title = manager_text.extract_title(content) or content.strip()[:60] or "Untitled note"
    body = content if manager_text.extract_title(content) else f"# {title}\n\n{content}"
    return Response(
        content=body,
        media_type="text/markdown; charset=utf-8",
        headers=attachment_headers(safe_filename(title, "md")),
    )


def _content_change(entry, body: EntryUpdate) -> tuple[bool, str | None]:  # noqa: ANN001
    """`(changed, text to store)`; the text is None when nothing is written."""
    new_content = body.content
    if entry.is_private and body.content is not None:
        #: A private note's column holds ciphertext, so "changed" is judged on
        #: the text the editor saw, and the new text is stored encrypted: it
        #: was written plain, with the note still flagged private, and sat in
        #: `entries.content` and the full-text index in the clear (found
        #: 2026-10-04 by scanning a data dir for a private note's words).
        content_changed = body.content != manager_text.readable_content(entry)
        new_content = _stored_form(entry, body.content) if content_changed else None
    else:
        content_changed = body.content is not None and body.content != entry.content
    return content_changed, new_content


def _after_content_edit(session: Session, entry, body: EntryUpdate) -> None:  # noqa: ANN001
    """What an edited text sets going: the stale vector goes, links resolve, media settles."""
    # The old vector describes the old text, refresh it, best effort.
    try:
        session.execute(
            sa_delete(EmbeddingRecord).where(EmbeddingRecord.entry_id == entry.id)
        )
        session.commit()
    except Exception:  # noqa: BLE001  # never fail the edit over the index
        logging.getLogger("tessellate.embeddings").warning(
            "couldn't clear the stale vector for entry %s", entry.id, exc_info=True
        )
        session.rollback()
    else:
        #: Off the request (audit 2026-10-05, ARCH-02 step 5): an edit
        #: used to embed here, a model call of 200 to 400 ms on a real
        #: embedder before the editor's save returned. The stale vector
        #: is already gone, so until the job runs the note is found by
        #: its words, as a note saved with the embedder off is.
        filing_background._queue_embedding(entry)
    # Editing a note can introduce new [[links]]; resolve those too.
    try:
        manager_wiki.sync_wiki_links(session, entry)
        manager_wiki.resolve_links_to(session, entry)
        session.commit()
    except Exception:
        session.rollback()
        logger.warning("couldn't sync wiki links for entry %s", entry.id, exc_info=True)
    # Same "committed" trigger point as create_entry, an edit can be
    # the first time an image the note already referenced actually
    # gets saved (a staged upload attached, then the note edited to
    # include it, rather than created with it already there).
    capture.process_committed_media(session, body.content)


def _wiki_rename(session: Session, entry, old_name: str) -> dict | None:  # noqa: ANN001
    """Set when the opening line changed and other notes link to the old name."""
    if not old_name or manager_wiki.wiki_opening(entry.content) == old_name:
        return None
    # Spelt as the holders wrote it, the opening line as the note does.
    first = (entry.content or "").strip().split("\n", 1)[0]
    new_name = re.sub(r"^\s{0,3}#{1,6}\s+", "", first).strip()
    holders = manager_wiki.wiki_holders(session, entry, old_name)
    if not holders or not new_name:
        return None
    spelt = re.search(r"\[\[\s*(" + re.escape(old_name) + r")", holders[0].content, re.IGNORECASE)
    return {"old": spelt.group(1) if spelt else old_name, "new": new_name, "notes": len(holders)}


@router.put("/{entry_id}", response_model=EntryOut)
def update_entry(
    entry_id: int,
    body: EntryUpdate,
    response: Response,
    session: Session = Depends(get_session),
    if_match: str | None = Header(default=None),
) -> EntryOut:
    """Manual override: the user can correct anything the AI decided
    (plan §4: the AI is a servant, not a gatekeeper).

    `If-Match` (B7) is the HTTP spelling of `base_hash`: a write that names
    the version it was made from is refused with 412 when the note is no
    longer that version, whatever the body changes, so an outside client
    cannot clobber a background AI edit it never saw."""
    entry = NOTES.writable(session, entry_id)
    refuse_unless_match(
        if_match,
        current_hash=content_hash(manager_text.readable_content(entry)),
        current=lambda: entry_out.to_out(session, entry),
        noun="note",
    )
    #: Two windows, one note (WORLD_CLASS_PLAN 22.1 item 5): a save that
    #: started from text another window has since replaced is refused, with
    #: that text, before anything is written. Compared as the reader sees it
    #: (decrypted), which is what the editor's hash was taken from.
    if body.base_hash and body.content is not None:
        refuse_if_stale(
            base_hash=body.base_hash,
            current_text=manager_text.readable_content(entry),
            new_text=body.content,
            current=lambda: entry_out.to_out(session, entry),
            noun="note",
        )
    refuse_if_tags_stale(
        base_tags=body.base_tags,
        current_tags=manager.entry_tags(entry),
        new_tags=body.tags,
        current=lambda: entry_out.to_out(session, entry),
        noun="note",
    )
    content_changed, new_content = _content_change(entry, body)
    tags_changed = body.tags is not None and body.tags != manager.entry_tags(entry)
    #: The note's [[name]] before the edit (a private note is never a target).
    old_name = (
        manager_wiki.wiki_opening(entry.content) if content_changed and not entry.is_private else ""
    )
    #: A save that carries an applied Atlas suggestion is both of theirs.
    with events.acting_as(ACTOR_USER_AND_AI) if body.ai_assisted else contextlib.nullcontext():
        # Snapshot BEFORE the change, so the newest revision is always the
        # version being replaced rather than the one replacing it.
        if content_changed or tags_changed:
            manager.record_revision(session, entry)
        manager.update_entry(
            session,
            entry,
            content=new_content,
            category_name=body.category,
            tags=body.tags,
        )
    if body.pinned is not None and body.pinned != entry.pinned:
        entry.pinned = body.pinned
        manager.log_action(
            session, "edited", "entry", entry.id, "pinned" if body.pinned else "unpinned"
        )
        session.commit()
    _apply_flags(session, entry, body)
    if content_changed:
        _after_content_edit(session, entry, body)
    out = entry_out.to_out(session, entry)
    out.wiki_rename = _wiki_rename(session, entry, old_name)
    response.headers["ETag"] = entity_tag(out.content_hash)
    return out


class WikiRenameIn(BaseModel):
    old: str = Field(min_length=1, max_length=120)


@router.post("/{entry_id}/wiki-rename")
def wiki_rename(entry_id: int, body: WikiRenameIn, session: Session = Depends(get_session)) -> dict:
    """Rewrite `[[old]]` as this note's current name in every note that still
    writes the old one (GRAPH_PLAN 518; offered by the edit that renamed it)."""
    entry = NOTES.writable(session, entry_id)
    first = (manager_text.readable_content(entry) or "").strip().split("\n", 1)[0]
    new_name = re.sub(r"^\s{0,3}#{1,6}\s+", "", first).strip()
    if not new_name or len(new_name) > 120 or "]" in new_name or "[" in new_name:
        raise HTTPException(status_code=422, detail="This note's first line can't be a [[name]].")
    notes: list[dict] = []
    rewritten = manager_wiki.rewrite_wiki_name(session, entry, body.old, new_name, notes)
    return {"rewritten": rewritten, "notes": notes}


@router.delete("/{entry_id}", response_model=EntryOut)
def delete_entry(
    entry_id: int,
    session: Session = Depends(get_session),
    if_match: str | None = Header(default=None),
) -> EntryOut:
    """Soft delete → recycle bin. Restorable until purged. `If-Match` as on
    the edit: a client binning the version it read does not bin a newer one."""
    entry = _existing_entry(session, entry_id)
    refuse_unless_match(
        if_match,
        current_hash=content_hash(manager_text.readable_content(entry)),
        current=lambda: entry_out.to_out(session, entry),
        noun="note",
    )
    if not entry.is_deleted:
        manager.soft_delete_entry(session, entry)
        companion_events.record("private_note" if _kept_private(session, entry) else "note_binned")  # kind and time only (W31)
    return entry_out.to_out(session, entry)


@router.post("/{entry_id}/restore", response_model=EntryOut)
def restore_entry(entry_id: int, session: Session = Depends(get_session)) -> EntryOut:
    entry, _was_binned = content_repo.restore(session, "note", entry_id)
    session.commit()
    return entry_out.to_out(session, entry)


@router.post("/{entry_id}/archive", response_model=EntryOut)
def archive_entry(entry_id: int, session: Session = Depends(get_session)) -> EntryOut:
    """Kept, but out of the way (BACKLOG §30b): distinct from the recycle
    bin: never auto-cleared, never purgeable, no confirmation needed since
    nothing is at risk of being lost."""
    entry = NOTES.writable(session, entry_id)
    if not entry.archived_at:
        manager.archive_entry(session, entry)
    return entry_out.to_out(session, entry)


@router.post("/{entry_id}/unarchive", response_model=EntryOut)
def unarchive_entry(entry_id: int, session: Session = Depends(get_session)) -> EntryOut:
    entry = NOTES.writable(session, entry_id)
    if entry.archived_at:
        manager.unarchive_entry(session, entry)
    return entry_out.to_out(session, entry)


@router.delete("/{entry_id}/purge")
def purge_entry(entry_id: int, session: Session = Depends(get_session)) -> dict:
    """Permanently delete ONE note from the recycle bin. Asked for directly.

    Emptying the whole bin was all-or-nothing, so getting rid of a single note
    for good meant destroying everything else in there too, which is why
    people leave the bin full instead, and then the bin is not a bin.

    **Only a binned note can be purged.** A note still in the notebook has to
    go through `DELETE /entries/{id}` first, so there is always the soft-delete
    step between an ordinary click and permanent loss. Enforced here rather
    than trusted to the UI: this is the one route in the app that destroys
    something with no undo.
    """
    entry = _existing_entry(session, entry_id)
    if not entry.is_deleted:
        raise HTTPException(
            status_code=400,
            detail="Only notes in the recycle bin can be permanently deleted.",
        )
    removed = manager_purge.purge_entries(
        session, [entry], uploads_dir=deps.get_config().uploads_dir
    )
    return {"purged": removed, "id": entry_id}


class LinkBody(BaseModel):
    target_id: int
    # Optional: "why are these connected?" A shared tag or a reply thread
    # says why on its own; a manual link often doesn't.
    reason: str | None = Field(default=None, max_length=200)
    # What kind of connection, from core.database.LINK_TYPES. Optional, and an
    # unrecognised value is stored as null rather than rejected, see
    # manager.create_link on why a typo should not cost you the link.
    link_type: str | None = Field(default=None, max_length=24)
    #: How sure the suggestion was, kept with a `reason` its signals wrote
    #: (GRAPH_PLAN KG9). Ignored without a reason.
    reason_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    #: GRAPH_PLAN KG3: the link's own properties.
    props: dict | None = None

    @field_validator("props")
    @classmethod
    def _props_shape(cls, value: dict | None) -> dict | None:
        return check_link_props(value)


#: A link's properties: a few short scalar values, never a document.
LINK_PROPS_MAX = 20


def check_link_props(value: dict | None) -> dict | None:
    if value is None:
        return None
    if len(value) > LINK_PROPS_MAX:
        raise Said(f"A link holds {LINK_PROPS_MAX} properties at most.")
    out = {}
    for key, item in value.items():
        key = " ".join(str(key).split())[:40]
        if not key:
            raise ValueError("A property needs a name.")
        if item is not None and not isinstance(item, (str, int, float, bool)):
            raise ValueError("A property is a word, a number or yes/no, not a list or a group.")
        out[key] = item[:200] if isinstance(item, str) else item
    return out


class LinkPatchBody(BaseModel):
    #: A kind (built-in or custom), or null for none. Unlike creation, a bad
    #: name here is refused: changing a link's type is the whole request.
    #: Only the fields sent change.
    link_type: str | None = Field(default=None, max_length=24)
    props: dict | None = None
    #: INBOX 693: true for a link that runs both ways, false for one way,
    #: null to let its type decide (`manager.is_two_way_link`).
    two_way: bool | None = None

    @field_validator("props")
    @classmethod
    def _props_shape(cls, value: dict | None) -> dict | None:
        return check_link_props(value)


class LinkReasonBody(BaseModel):
    # None (or omitted/blank) clears the reason, this is also how a link
    # that got an auto-deduced reason it disagrees with is corrected back
    # to nothing, same as it would have started with.
    reason: str | None = Field(default=None, max_length=200)


class PrivacyBody(BaseModel):
    private: bool


#: How many events one request of a note's history returns. A note edited
#: every day for a year has a history worth paging through rather than
#: sending whole to a sheet that shows a dozen rows at a time.
HISTORY_PAGE = 50


def _stored_form(entry, text: str, session: Session | None = None) -> str:  # noqa: ANN001
    """A past version's text, in the form this note stores it in now.

    A private note's restored text marks the pictures it embeds, as an edit
    does (SEC-A2): a picture only an older version used was served locked."""
    stored = manager_text.content_for_entry(entry, text or "")
    if stored is None:
        raise HTTPException(status_code=409, detail="Unlock the app first: this version needs the encryption key.")
    if session is not None and entry.is_private:
        manager_text.flag_private_media(session, _readable(stored))
    return stored


def _readable(content: str) -> str:
    """Decrypt stored content for display, the same way a note itself is.

    `manager.readable_content` reads one attribute, so an event's stored
    content can borrow it without a row to hang it on.
    """
    return manager_text.readable_content(SimpleNamespace(content=content or ""))


class MakeAllPrivateBody(BaseModel):
    confirm: bool


@router.post("/make-all-private")
def make_all_private(body: MakeAllPrivateBody, session: Session = Depends(get_session)) -> dict:
    """Seal every ordinary note (INBOX 1695 d). The client asks first; the
    server refuses without `confirm` so a stray call cannot do it."""
    if not body.confirm:
        raise HTTPException(status_code=400, detail="Confirm first: this locks every note.")
    sealed = entry_service.make_all_private(session)
    if sealed is None:
        raise HTTPException(status_code=409, detail="Unlock the app first: the encryption key isn't loaded.")
    return {"sealed": len(sealed), "ids": sealed}


@router.post("/{entry_id}/privacy", response_model=EntryOut)
def set_entry_privacy(
    entry_id: int, body: PrivacyBody, session: Session = Depends(get_session)
) -> EntryOut:
    """Encrypt this note at rest, or decrypt it again.

    Needs the vault open, which means the app must be unlocked, the data key
    only exists in memory while it is.
    """
    entry = NOTES.writable(session, entry_id)
    if not body.private and private_space.is_private_space(session, entry.workspace_id):
        # INBOX 1727: no per-note opt-out inside a private space.
        raise HTTPException(status_code=409, detail=private_space.MOVE_OUT_TO_SHARE)
    if not entry_service.set_privacy(session, entry, body.private):
        raise HTTPException(
            status_code=409,
            detail="Unlock the app first: the encryption key isn't loaded.",
        )
    return entry_out.to_out(session, entry)


@router.post("/{entry_id}/generate-title", response_model=EntryOut)
def generate_entry_title(
    entry_id: int, session: Session = Depends(get_session)
) -> EntryOut:
    """Write a title for this note with AI, on request.

    Recognising a title the user already wrote (`manager.extract_title`) is
    free; writing one is a real model call, so this is its own opt-in
    action rather than something that runs on every save. Replaces an
    existing title rather than stacking a second heading on top of it.
    """
    entry = NOTES.writable(session, entry_id)
    # `readable_content` decrypts a private note for reading; writing that
    # decrypted text straight back to `entry.content` (below) would silently
    # replace the ciphertext with plaintext, the note would stop being
    # private as a side effect of titling it. Refused outright rather than
    # risked: unlike a plain edit, there's no form here the user reviewed
    # before it reached the server.
    if entry.is_private:
        raise HTTPException(
            status_code=400, detail="Make this note readable first: private notes can't be re-titled here."
        )
    content = manager_text.readable_content(entry)
    if not content.strip():
        raise HTTPException(status_code=400, detail="There's no text to title yet.")
    if not deps.get_ollama().is_running():
        return _composed_title(session, entry, content)
    try:
        title = librarian.generate_title(content, deps.get_model_manager(), deps.get_ollama())
    except OllamaError as exc:
        logger.warning("title generation failed", exc_info=True)
        raise HTTPException(status_code=502, detail=librarian.AI_FAILED_MESSAGE) from exc
    if not title:
        raise HTTPException(status_code=502, detail="The AI didn't return a usable title.")
    entry_service.retitle(session, entry, content, title, f"generated title: {title}")
    return entry_out.to_out(session, entry)


def _composed_title(session: Session, entry, content: str) -> EntryOut:  # noqa: ANN001
    """**A title with no model** (O7; INBOX 904 B33: "they arent ai actions
    if the composer does them"): the note's own words, its first sentence cut
    at seven words (`composer_voice.title_for`), never a word it does not
    hold. The client says it was taken, not written."""
    from tessellate.ai import composer_voice

    title = composer_voice.title_for(manager_text.remove_title(content) or content)
    if not title:
        raise HTTPException(status_code=422, detail="There's no sentence here to take a title from yet.")
    entry_service.retitle(session, entry, content, title, f"title from its own words: {title}")
    return entry_out.to_out(session, entry)


@router.post("/{entry_id}/remove-title", response_model=EntryOut)
def remove_entry_title(entry_id: int, session: Session = Depends(get_session)) -> EntryOut:
    """Take a note's title back out, asked for directly. Just the leading
    heading line; a note with no title is returned unchanged rather than
    treated as an error, since the client only offers this action when
    `entry.title` is already set and a stale menu shouldn't 400."""
    entry = NOTES.writable(session, entry_id)
    # Same reason as generate-title: writing decrypted text back to
    # `entry.content` would un-encrypt the note as a side effect.
    if entry.is_private:
        raise HTTPException(
            status_code=400, detail="Make this note readable first: private notes can't be edited here."
        )
    entry_service.remove_title(session, entry)
    return entry_out.to_out(session, entry)



# --- extract notes (BACKLOG.md §62) ------------------------------------------
# Select a block of writing, the Writing Room's draft, a Document's body, or
# several notes' content selected on the whiteboard, and turn it into one or
# several AI-drafted notes, auto-linked with real reasons. Preview first,
# matching `generate_diagram`'s own preview-before-commit convention (see
# `ai.extractor`'s module docstring): nothing is written here until
# `/extract/commit` is called with what the preview actually showed.


class ExtractPreviewBody(BaseModel):
    text: str = Field(min_length=1, max_length=extractor.EXTRACT_MAX_CHARS)
    # A Graph/whiteboard selection's notes-in-context: existing notes this
    # extraction should try to link every new note back to, regardless of
    # how similar the wording is, the user already said they're connected
    # by selecting them together.
    source_entry_ids: list[int] = Field(default_factory=list)


@router.post("/extract/preview")
def extract_preview(body: ExtractPreviewBody, session: Session = Depends(get_session)) -> dict:
    """Propose one or more notes from `body.text`, with the links they'd get
    and why: nothing saved yet. See `ai.extractor.build_extraction`."""
    try:
        return extractor.build_extraction(
            session,
            body.text,
            deps.get_embeddings(),
            deps.get_model_manager(),
            deps.get_ollama(),
            source_entry_ids=body.source_entry_ids,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None


class ExtractNoteIn(BaseModel):
    """One note from a preview, as the user reviewed it, possibly edited,
    possibly dropped (the caller just omits it) before commit."""

    ref: str = Field(min_length=1, max_length=40)
    title: str = Field(default="", max_length=200)
    content: str = Field(min_length=1, max_length=extractor.EXTRACT_MAX_CHARS)
    category: str = Field(default=manager.UNCATEGORISED, max_length=100)
    tags: list[str] = Field(default_factory=list)


class ExtractLinkIn(BaseModel):
    """One proposed link, as shown in the preview. `source_ref`/`target_ref`
    are either `nN` (one of this batch's own notes) or `existing:<id>` (a
    note already in the notebook)."""

    source_ref: str = Field(min_length=1, max_length=48)
    target_ref: str = Field(min_length=1, max_length=48)
    reason: str = Field(min_length=1, max_length=200)


class ExtractCommitBody(BaseModel):
    notes: list[ExtractNoteIn] = Field(min_length=1, max_length=extractor.MAX_EXTRACT_NOTES)
    links: list[ExtractLinkIn] = Field(default_factory=list)
    # When extracting from a Document's body, attach every note created here
    # to it: the same connection `POST /documents/{id}/notes` makes by hand.
    source_document_id: int | None = None


@router.post("/extract/commit", status_code=201)
def extract_commit(body: ExtractCommitBody, session: Session = Depends(get_session)) -> dict:
    """Write exactly what a preview showed (possibly edited, possibly
    trimmed) to the notebook: the notes, then the links between them
    (`entry_service.commit_extraction`)."""
    refs = [note.ref for note in body.notes]
    for ref in refs:
        if refs.count(ref) > 1:
            raise HTTPException(status_code=400, detail=f"Each note needs its own reference, and '{ref}' is used by more than one.")
    created, links_created = entry_service.commit_extraction(
        session,
        [(note.ref, note.content, note.category, note.tags) for note in body.notes],
        [(link.source_ref, link.target_ref, link.reason) for link in body.links],
        body.source_document_id,
    )
    return {
        "notes": entry_out.to_out_bulk(session, created),
        "links_created": links_created,
    }
