"""A note's references, then-and-now and history routes (list, restore an event, restore a revision).

Split out of routes_entries.py (K24); mounted in app.py beside that module's router. The helpers these
routes read (`_existing_entry`, `_to_out`, `_stored_form`, ...) stay in routes_entries, and the
reference-row scan lives in routes_entries_refs.
"""

from __future__ import annotations

import json
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from tessellate.api.routes_entries import (
    HISTORY_PAGE,
    _existing_entry,
    _readable,
    _refuse_while_sealed,
    _stored_form,
    _to_out,
)
from tessellate.api.routes_entries_refs import _reference_rows
from tessellate.api.schemas import EntryOut
from tessellate.core import deps, events
from tessellate.core.database import AuditLog, EntryRevision
from tessellate.core.deps import get_session
from tessellate.entry import manager
from tessellate.entry import manager_text
from tessellate.repo.content import NOTES

router = APIRouter(tags=["entries"], prefix="/entries")


@router.get("/{entry_id}/references")
def entry_references(entry_id: int, session: Session = Depends(get_session)) -> dict:
    """What points at this note, from anywhere in the notebook."""
    entry = _existing_entry(session, entry_id)
    items = _reference_rows(session, entry)
    return {"items": items, "total": len(items)}


@router.get("/{entry_id}/then-and-now")
def then_and_now(entry_id: int, as_of: date = Query(...), session: Session = Depends(get_session)) -> dict:
    """This note's claims as they stood at the end of `as_of` against its
    claims now (WORLD_CLASS_PLAN I5, row 23; `ai/timetravel.py`): `then` and
    `now` are its sentences, `changed` pairs them as revised, dropped or new."""
    from tessellate.ai import timetravel
    from tessellate.core.config import user_now

    entry = _existing_entry(session, entry_id)
    if entry.is_private:
        raise HTTPException(status_code=403, detail="This note is private, so its history is not compared.")
    zone = user_now(deps.get_config()).tzinfo
    then = timetravel.text_as_of(session, entry, timetravel.end_of_day(as_of, zone))
    if then is None:
        raise HTTPException(status_code=404, detail=f"This note did not exist on {timetravel.day_words(as_of)}.")
    out = timetravel.then_and_now(then.text, entry.content or "")
    out.update({"as_of": as_of.isoformat(), "revision_id": then.revision_id, "exact": then.exact})
    return out


@router.get("/{entry_id}/claims")
def claims_as_of(entry_id: int, as_of: date | None = Query(default=None), session: Session = Depends(get_session)) -> dict:
    """This note's claims as they stood at the end of `as_of`, or now (I5).
    The revision is resolved at the date, as then-and-now resolves it; a
    claim the night shift stored for the note is named by its fact id, and
    one the person marked wrong (I7) says so."""
    from sqlalchemy import select

    from tessellate.ai import timetravel, verdicts
    from tessellate.core.config import user_now
    from tessellate.core.database import DerivedFact

    entry = _existing_entry(session, entry_id)
    if entry.is_private:
        raise HTTPException(status_code=403, detail="This note is private, so its claims are not listed.")
    text, revision_id, exact = entry.content or "", None, True
    if as_of is not None:
        zone = user_now(deps.get_config()).tzinfo
        then = timetravel.text_as_of(session, entry, timetravel.end_of_day(as_of, zone))
        if then is None:
            raise HTTPException(status_code=404, detail=f"This note did not exist on {timetravel.day_words(as_of)}.")
        text, revision_id, exact = then.text, then.revision_id, then.exact
    stored = {
        verdicts.norm(row.text): row.id
        for row in session.scalars(select(DerivedFact).where(DerivedFact.entry_id == entry.id, DerivedFact.kind == "claim"))
    }
    known = verdicts.known(session)
    claims = [
        {"text": c, "fact_id": stored.get(verdicts.norm(c)), "wrong": known.is_wrong(entry.id, c)}
        for c in timetravel.claims(text)
    ]
    return {"as_of": as_of.isoformat() if as_of else None, "revision_id": revision_id, "exact": exact, "claims": claims}


class ThenTextBody(BaseModel):
    #: A version of the note the reader is looking at (a History row's text).
    then: str = Field(max_length=200_000)


@router.post("/{entry_id}/then-and-now")
def then_and_now_of_text(entry_id: int, body: ThenTextBody, session: Session = Depends(get_session)) -> dict:
    """The same comparison for one version the reader already has on screen,
    a History row: by its text rather than by a day, so two edits made the
    same day are still two versions. Reads nothing but the note now."""
    from tessellate.ai import timetravel

    entry = _existing_entry(session, entry_id)
    if entry.is_private:
        raise HTTPException(status_code=403, detail="This note is private, so its history is not compared.")
    return timetravel.then_and_now(body.then, entry.content or "")


@router.get("/{entry_id}/history")
def entry_history(
    entry_id: int,
    before: int | None = Query(default=None, ge=1),
    session: Session = Depends(get_session),
) -> dict:
    """This note's history, as events and as past versions.

    Two lists because they answer two questions and Brief 7 deliberately
    kept both. `items` is the event log (Brief 7, WORLD_CLASS_PLAN B1):
    everything that ever happened to this note, who did it, and the state
    it left the note in, which is what the History sheet renders and what
    `POST /entries/{id}/restore/{event_id}` replays. `revisions` is the
    older per-edit snapshot list (`EntryRevision`, capped at
    `manager.MAX_REVISIONS`), still written, still restorable through its
    own route, and still the only thing that holds a version of a note
    whose events predate the log.

    `before` pages backwards through the events by id, newest first.
    """
    entry = _existing_entry(session, entry_id)
    _refuse_while_sealed(entry)

    rows = events.events_for(
        session,
        "entry",
        entry.id,
        newest_first=True,
        limit=HISTORY_PAGE + 1,
        before_id=before,
        # The bookkeeping events (a version snapshotted, the dates
        # re-resolved) always accompany the edit that caused them and say the
        # same thing twice in a list a person reads. They are still in the
        # log, still in /audit, and still replayed: hidden here, not dropped.
        skip_actions=events.QUIET_ACTIONS,
    )
    more = len(rows) > HISTORY_PAGE
    rows = rows[:HISTORY_PAGE]
    # What the note said after each row on *this page*, folded in one
    # ascending pass (`events.states_at`). It was every event of the note
    # hydrated into an ORM object with a whole copy of the note's text kept
    # for each, whichever page was asked for. Measured on this sandbox, on a
    # note with 4,000 events: the newest page 109 ms before against 36 ms
    # after, the oldest page 104 ms against 2.9 ms.
    rebuilt = events.states_at(session, "entry", entry.id, [row.id for row in rows])
    items = []
    for row in rows:
        at_the_time = rebuilt.get(row.id, {})
        items.append(
            {
                "id": row.id,
                "action": row.action,
                "actor": row.actor or events.ACTOR_USER,
                "detail": row.detail,
                "created_at": row.created_at.isoformat(),
                # Decrypted for display exactly like the note itself, so a
                # private note's history is readable while unlocked and not
                # otherwise.
                "content": _readable(at_the_time.get("content") or ""),
                "tags": at_the_time.get("tags") or [],
                # Whether this event's values were dropped by the compactor
                # (`events.compact`), so the sheet can say "the text from this
                # change is no longer kept" rather than render a row with no
                # text and no reason for it.
                "compacted": events.is_compacted(row),
            }
        )

    return {
        "items": items,
        "next_cursor": rows[-1].id if (more and rows) else None,
        "revisions": [
            {
                "id": revision.id,
                "content": manager_text.readable_content(revision),
                "tags": json.loads(revision.tags or "[]"),
                "created_at": revision.created_at.isoformat(),
            }
            for revision in manager.revisions_for(session, entry)
        ],
    }


@router.post("/{entry_id}/restore/{event_id}", response_model=EntryOut)
def restore_event(
    entry_id: int, event_id: int, session: Session = Depends(get_session)
) -> EntryOut:
    """Put this note back the way one of its events left it.

    Replay rather than a stored copy: the state after an event is every
    `after` payload up to and including it, applied in order, which is the
    same definition the History sheet shows and the same one a note rebuilt
    from scratch would get. Restoring is itself an edit, so the current text
    is snapshotted first and the restore records its own event: undoing an
    undo has to work, or this is a trap rather than a safety net.
    """
    entry = NOTES.writable(session, entry_id)
    row = session.get(AuditLog, event_id)
    if row is None or row.entity_type != "entry" or row.entity_id != entry.id:
        raise HTTPException(status_code=404, detail="That version no longer exists.")

    if events.is_compacted(row):
        # Not "did not change the note" and not "does not exist": this event
        # happened, and its text was deliberately dropped to stop the log
        # growing by a copy of the note on every edit (`events.compact`).
        # Gone rather than a bad request, which is what 410 is for.
        raise HTTPException(
            status_code=410,
            detail=(
                "That version is no longer kept: changes older than the "
                "history window keep the record of what happened, not the text."
            ),
        )

    state = events.replay(session, "entry", entry.id, upto_event_id=event_id)
    if "content" not in state and "tags" not in state:
        raise HTTPException(
            status_code=400, detail="That event did not change the note's text."
        )

    if "content" in state:
        restored = _stored_form(entry, state["content"], session)
    manager.record_revision(session, entry)
    if "content" in state:
        entry.content = restored
    if "tags" in state:
        entry.tags = json.dumps(state["tags"])
    manager.mark_edited(entry)
    manager.log_action(
        session,
        "restored",
        "entry",
        entry.id,
        f"back to event {event_id}",
        payload={
            "from_event": event_id,
            "after": {
                "content": entry.content,
                "tags": manager.tags_from_json(entry.tags),
            },
        },
    )
    session.commit()
    session.refresh(entry)
    return _to_out(session, entry)


@router.post("/{entry_id}/history/{revision_id}/restore", response_model=EntryOut)
def restore_revision(
    entry_id: int, revision_id: int, session: Session = Depends(get_session)
) -> EntryOut:
    """Put a past version back.

    Restoring is itself an edit, so the current text is saved first, undoing
    an undo has to work, or this is a trap rather than a safety net.
    """
    entry = NOTES.writable(session, entry_id)
    revision = session.get(EntryRevision, revision_id)
    if revision is None or revision.entry_id != entry.id:
        raise HTTPException(status_code=404, detail="That version no longer exists.")

    restored = _stored_form(entry, revision.content, session)
    manager.record_revision(session, entry)
    entry.content = restored
    entry.tags = revision.tags
    manager.mark_edited(entry)
    manager.log_action(session, "edited", "entry", entry.id, "restored an earlier version")
    session.commit()
    session.refresh(entry)
    return _to_out(session, entry)
