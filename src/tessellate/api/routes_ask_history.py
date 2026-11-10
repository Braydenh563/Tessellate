"""Browsing back through the Ask box (Notes tab): every notes-only question
it has answered, not just the last five as a chip row.

Turns are written by routes_chat.py's `chat_stream` (the only caller of the
Ask box) once a real answer has landed; nothing here writes a turn. This
file is read, search, pin and delete only (a delete or a clear also
marks the audit log, so the Ask again row forgets it).
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, Field

from tessellate.api import paging
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tessellate.core import deps, undo_bin
from tessellate.core.database import LIKE_ESCAPE, AskTurn, Entry, like_escape
from tessellate.core.deps import get_session
from tessellate.ai.grounding import composed_support, support as grounding_support
from tessellate.entry import manager

router = APIRouter(prefix="/ask-history", tags=["ask-history"])

#: A row's answer, cut to a preview length for the list view, the full text
#: is only fetched when a turn is actually opened (GET /{turn_id}).
PREVIEW_CHARS = 220


def _summary(turn: AskTurn) -> dict:
    answer = turn.answer or ""
    return {
        "id": turn.id,
        "question": turn.question,
        "answer_preview": answer[:PREVIEW_CHARS] + ("…" if len(answer) > PREVIEW_CHARS else ""),
        "search_mode": turn.search_mode,
        "when_phrase": turn.when_phrase,
        "result_count": len(json.loads(turn.raw_result_ids or "[]")),
        "pinned": bool(turn.pinned),
        "created_at": turn.created_at.isoformat(),
    }


@router.get("")
def list_ask_history(
    response: Response,
    q: str = "",
    pinned_only: bool = False,
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    cursor: str | None = paging.cursor_param(),
    session: Session = Depends(get_session),
) -> dict:
    """Newest first, pinned first among ties, same ordering Conversation
    uses for the Chat tab's own saved list, for the same reason: the thread
    you keep coming back to shouldn't sink under a week of one-offs."""
    offset = paging.start(cursor, offset)
    query = select(AskTurn)
    if pinned_only:
        query = query.where(AskTurn.pinned == True)  # noqa: E712
    term = q.strip()
    if term:
        like = f"%{like_escape(term)}%"
        query = query.where(
            AskTurn.question.ilike(like, escape=LIKE_ESCAPE)
            | AskTurn.answer.ilike(like, escape=LIKE_ESCAPE)
        )
    ordered = query.order_by(AskTurn.pinned.desc(), AskTurn.created_at.desc())
    total = session.scalar(select(func.count()).select_from(ordered.subquery()))
    rows = session.scalars(ordered.limit(limit).offset(offset)).all()
    paging.finish(response, offset, limit, total or 0)
    return {
        "turns": [_summary(t) for t in rows],
        "total": total or 0,
        "offset": offset,
        "limit": limit,
    }


@router.get("/stats")
def ask_history_stats(session: Session = Depends(get_session)) -> dict:
    """A one-line header for the panel: how much is here to browse."""
    total = session.scalar(select(func.count(AskTurn.id))) or 0
    pinned = session.scalar(select(func.count(AskTurn.id)).where(AskTurn.pinned == True)) or 0  # noqa: E712
    return {"total": total, "pinned": pinned}


@router.get("/{turn_id}")
def get_ask_turn(turn_id: int, session: Session = Depends(get_session)) -> dict:
    """The full turn, with its notes hydrated to their current state.

    A note deleted or made private since this question was asked is dropped
    rather than shown: same rule `_attached_notes` (routes_chat.py) applies
    when a note is attached live, kept here for the same reason: a browsed-
    back turn should not resurrect binned content or leak a note that has
    since been marked private.
    """
    from tessellate.api.routes_entries import _to_out_bulk  # avoids a route-module cycle

    turn = deps.get_or_404(session, AskTurn, turn_id, "That question is not in your history.")
    ids = json.loads(turn.raw_result_ids or "[]")
    entries = []
    if ids:
        found = {
            e.id: e
            for e in session.scalars(select(Entry).where(Entry.id.in_(ids)))
            if not e.is_deleted and not e.is_private
        }
        # Preserve the order the answer originally showed them in.
        entries = [found[i] for i in ids if i in found]
    return {
        **_summary(turn),
        "answer": turn.answer,
        "raw_results": [r.model_dump(mode="json") for r in _to_out_bulk(session, entries)],
        "omitted_results": len(ids) - len(entries),
        # Same badge data the live answer had, older rows saved before this
        # field existed fall back to "no explanation" rather than an error.
        "match_info": json.loads(turn.match_info or "{}"),
        "connected_ids": json.loads(turn.connected_ids or "[]"),
        #: The sentence-level citations, so a reopened turn draws the same
        #: numbered markers and the same "grounded in" strip the live answer
        #: had (INBOX 241).
        "grounding": _live_grounding(session, turn),
        #: The low-support notice's numbers, from the stored answer and the
        #: marks as they were written (not the live-filtered ones above: a note
        #: deleted since does not make the answer any better or worse backed
        #: than it was). Same counter as the live stream, so a reopened turn
        #: shows the notice the live one did.
        "support": _saved_support(turn),
    }


def _saved_support(turn: AskTurn) -> dict:
    """The notice's numbers for a stored turn, by the counter the live answer
    used: a composed answer's (`composed_support`, never the model-draft
    warning) when no model wrote it, else the model's (chatfoot L6, W1 A5).
    The chat's saved turns branch the same way (routes_conversations.py)."""
    rows = json.loads(turn.grounding or "[]")
    if turn.composed:
        return composed_support(None, rows)
    return grounding_support(turn.answer or "", rows)


def _live_grounding(session: Session, turn: AskTurn) -> list[dict]:
    """The turn's citations, minus any whose note is gone.

    Same rule `get_ask_turn` applies to the results themselves: a note
    deleted or made private since the answer was written is dropped rather
    than shown. A citation is a link, so a marker pointing at a note the
    reader cannot open is worse than no marker at all.

    Checked against the database rather than against `raw_results`, which
    would be the cheaper test and the wrong one: a grounding row can name a
    note the model read through a tool, and `routes_chat.py`'s own comment
    at the point these are built says so ("a touched note is not in
    `raw_results`"). Filtering by the result set would silently delete those
    citations from every agent-written turn.
    """
    rows = json.loads(turn.grounding or "[]")
    wanted = {row.get("note_id") for row in rows if isinstance(row.get("note_id"), int)}
    if not wanted:
        return []
    live = {
        e.id
        for e in session.scalars(select(Entry).where(Entry.id.in_(wanted)))
        if not e.is_deleted and not e.is_private
    }
    return [row for row in rows if row.get("note_id") in live]


@router.put("/{turn_id}/pin")
def pin_ask_turn(turn_id: int, pinned: bool, session: Session = Depends(get_session)) -> dict:
    turn = deps.get_or_404(session, AskTurn, turn_id, "That question is not in your history.")
    turn.pinned = pinned
    session.commit()
    return _summary(turn)


@router.delete("/{turn_id}")
def delete_ask_turn(turn_id: int, session: Session = Depends(get_session)) -> dict:
    turn = deps.get_or_404(session, AskTurn, turn_id, "That question is not in your history.")
    #: And off the Ask again row, as `forget_recent_question` does.
    marker = manager.log_action(session, "forgot", "chat", detail=turn.question)
    session.flush()
    #: Kept for Undo (INBOX 898): the turn and the marker that hid its chip.
    token = undo_bin.stash(
        deps.get_config().data_dir,
        "ask-turns",
        {"turns": [undo_bin.row_dict(turn)], "marker_ids": [marker.id] if marker else []},
    )
    session.delete(turn)
    session.commit()
    return {"deleted": True, "undo_token": token}


@router.delete("")
def clear_ask_history(
    keep_pinned: bool = True, session: Session = Depends(get_session)
) -> dict:
    """Wipe the browsable history. Pinned turns survive by default, the
    same asymmetry a "clear all" next to a pin button always needs, or
    pinning something means nothing the next time this button is pressed."""
    query = select(AskTurn)
    if keep_pinned:
        query = query.where(AskTurn.pinned == False)  # noqa: E712
    rows = session.scalars(query).all()
    snapshot = [undo_bin.row_dict(row) for row in rows]
    for row in rows:
        session.delete(row)
    #: The Ask again row under the box is these questions too, read from the
    #: audit log (routes_chat `_recent_questions`); a marker ends it there.
    marker = manager.log_action(session, "cleared", "chat")
    session.flush()
    token = undo_bin.stash(
        deps.get_config().data_dir,
        "ask-turns",
        {"turns": snapshot, "marker_ids": [marker.id] if marker else []},
    )
    session.commit()
    return {"deleted": len(rows), "undo_token": token}


class RestoreBody(BaseModel):
    token: str = Field(min_length=1, max_length=64)


def restore_ask_markers(session: Session, ids: list[int]) -> None:
    """Write the `remembered` row that lifts each `forgot` or `cleared` marker.

    The audit log is a history, so a marker is never edited out: a later row
    says it no longer counts (`routes_chat._recent_questions` reads these).
    """
    for marker_id in ids:
        manager.log_action(session, "remembered", "chat", detail=str(marker_id))


@router.post("/restore")
def restore_ask_turns(body: RestoreBody, session: Session = Depends(get_session)) -> dict:
    """Put back what `DELETE /ask-history[/{id}]` removed (INBOX 898)."""
    config = deps.get_config()
    payload, _ = undo_bin.take(config.data_dir, "ask-turns", body.token)
    put = 0
    for data in payload["turns"]:
        taken = session.get(AskTurn, data["id"]) is not None
        session.add(undo_bin.row_from(AskTurn, data, keep_id=not taken))
        put += 1
    session.flush()
    restore_ask_markers(session, payload.get("marker_ids", []))
    session.commit()
    undo_bin.finish(config.data_dir, body.token)
    return {"restored": put}
