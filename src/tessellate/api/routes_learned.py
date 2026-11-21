"""What the notebook learned, over HTTP (WORLD_CLASS_PLAN 15, I7).

One writer and one reader over `ai/learning.py`. The write exists because
three of the four correction kinds happen in the browser and nowhere else: a
dismissed link suggestion, a result opened after a question, a resurfacing
card sent away. The fourth, a re-file, is already recorded server-side by
`entry/manager.update_entry_with_correction`, which is why there is no
"refile" caller here.

I9, the derived facts and their lifecycle, is the second half of this module
(below the corrections routes). It needs a view of what the app worked out
rather than of the corrections themselves, which is why it has its own store
(`ai/facts.py`) and why the two halves sit under one prefix: from the outside
they are one answer to "what has this app decided about my notes".
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, Query, Response

from tessellate.api import paging
from sqlalchemy import select
from sqlalchemy.orm import Session

from tessellate.ai import facts, learning
from tessellate.core import deps, undo_bin
from tessellate.core.database import utcnow
from tessellate.core.deps import get_session
from tessellate.repo import visible_notes

router = APIRouter(prefix="/learned", tags=["learned"])


class CorrectionBody(BaseModel):
    #: One of `learning.KINDS`. Validated in the route rather than as an enum
    #: here so the error names the kinds that do exist, which is the thing a
    #: caller with a typo needs to read.
    kind: str
    #: What the correction is about: `{"entry_id": 1}` for a resurfacing
    #: dismissal, `{"a": 1, "b": 2}` for a link pair, `{"question": "...",
    #: "entry_id": 1}` for a result opened after a question. Free-form
    #: because the four kinds genuinely point at different things, and a
    #: column per kind would be four columns three of which are always null.
    subject: dict = Field(default_factory=dict)
    from_value: str | None = None
    to_value: str | None = None
    #: The subject's own words, so a filing prompt can say what kind of note a
    #: rule is about. Clipped by `learning.record`.
    excerpt: str = ""


@router.post("/corrections", status_code=201)
def add_correction(body: CorrectionBody, session: Session = Depends(get_session)) -> dict:
    """Record one correction."""
    try:
        item = learning.record(
            session,
            kind=body.kind,
            subject=body.subject,
            from_value=body.from_value,
            to_value=body.to_value,
            excerpt=body.excerpt,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    session.commit()
    return {"id": item.id, "kind": item.kind, "subject": item.subject}


#: One page of corrections. This table only ever grows: every refile, every
#: dismissed suggestion and every card sent away adds a row, for the life of
#: the notebook, so "every correction" is the one answer this route must not
#: keep giving.
CORRECTIONS_PAGE_SIZE = 200


class VerdictBody(BaseModel):
    """A cited line's verdict (CHAT_PLAN B31, B32): the note's own sentence
    the line was made from, where it is, and the line as the answer said it."""

    verdict: Literal["wrong", "pinned"]
    note_id: int
    sentence: str = Field(min_length=1, max_length=2000)
    start: int = Field(default=0, ge=0)
    end: int = Field(default=0, ge=0)
    line: str = Field(default="", max_length=2000)


@router.post("/verdict", status_code=201)
def mark_verdict(body: VerdictBody, session: Session = Depends(get_session)) -> dict:
    """Wrong fact, or Pin as true, from the next turn on. The row's Delete
    (`DELETE /learned/{id}`) is the undo."""
    from tessellate.ai import verdicts

    try:
        done = verdicts.mark(session, body.verdict, body.note_id, body.sentence, body.start, body.end, body.line)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    session.commit()
    return done


class AnswerVerdictBody(BaseModel):
    """A whole answer marked not right (audit 1028 E59): the question as asked
    and the notes the answer cited."""

    question: str = Field(min_length=1, max_length=2000)
    entry_ids: list[int] = Field(min_length=1, max_length=12)
    line: str = Field(default="", max_length=2000)


@router.post("/answer-verdict", status_code=201)
def mark_answer_wrong(body: AnswerVerdictBody, session: Session = Depends(get_session)) -> dict:
    """Not right on an answer: one `wrong_answer` correction per cited note
    (`search_manager._learned_down` reads them). `ids` are the corrections, whose
    Delete (`DELETE /learned/corrections/{id}`) is the undo."""
    ids: list[int] = []
    visible = {row.id for row in visible_notes.by_ids(session, body.entry_ids)}
    for note_id in dict.fromkeys(body.entry_ids):
        if note_id not in visible:
            continue
        item = learning.record(
            session, kind="wrong_answer", subject={"question": " ".join(body.question.split())[:300], "entry_id": note_id}, excerpt=body.line
        )
        ids.append(item.id)
    if not ids:
        raise HTTPException(status_code=422, detail="None of those notes could be found.")
    session.commit()
    return {"ids": ids, "count": len(ids)}


@router.get("/answer-verdicts")
def count_answer_verdicts(session: Session = Depends(get_session)) -> dict:
    """How many answers-marked-not-right corrections this device holds (L225)."""
    return {"count": len(learning.corrections(session, kind="wrong_answer"))}


@router.delete("/answer-verdicts")
def clear_answer_verdicts(session: Session = Depends(get_session)) -> dict:
    """Settings' "Clear answers marked not right": every `wrong_answer` correction, no other kind (L225)."""
    from tessellate.core.database import AuditLog

    ids = [row.id for row in learning.corrections(session, kind="wrong_answer")]
    for row in session.scalars(select(AuditLog).where(AuditLog.id.in_(ids), AuditLog.action == "correction")):
        session.delete(row)
    session.commit()
    return {"removed": len(ids)}


@router.get("/corrections")
def list_corrections(
    response: Response,
    kind: str | None = None,
    limit: int = Query(default=CORRECTIONS_PAGE_SIZE, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    cursor: str | None = paging.cursor_param(),
    session: Session = Depends(get_session),
) -> list[dict]:
    """One page of corrections, oldest first, optionally of one kind."""
    offset = paging.start(cursor, offset)
    rows = learning.corrections(session, kind=kind)
    response.headers["X-Total-Count"] = str(len(rows))
    paging.finish(response, offset, limit, len(rows))
    return [
        {
            "id": item.id,
            "kind": item.kind,
            "subject": item.subject,
            "from": item.from_value,
            "to": item.to_value,
            "excerpt": item.excerpt,
        }
        for item in rows[offset : offset + limit]
    ]


# --- I9: the derived facts, their lifecycle and their switches ----------------
#
# The routes above are I7's corrections store. Everything below is I9: the
# table of what the app worked out for itself, and the contract every
# invention in WORLD_CLASS_PLAN 15 ships under. `ai/facts.py` holds the
# reasoning; these routes are the thin HTTP shell over it.


class FactPatch(BaseModel):
    #: The only editable field today. `payload` and `status` in the plan
    #: belong to kinds this pass does not derive yet (a tension's verdict, a
    #: duplicate's pair), and a field that nothing can set is a field that
    #: goes stale before its first caller.
    text: str = Field(min_length=1, max_length=2000)


class SwitchBody(BaseModel):
    #: Any subset of `facts.SWITCHES` plus `paused`. Free-form rather than a
    #: field per switch so a switch added by a later invention needs no change
    #: here, and validated in `facts.set_switches`, which owns the list.
    model_config = {"extra": "allow"}


class ForgetBody(BaseModel):
    confirm: bool = False


@router.get("")
def list_facts(
    response: Response,
    kind: str | None = None,
    q: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    cursor: str | None = paging.cursor_param(),
    session: Session = Depends(get_session),
) -> dict:
    """One page of what the notebook learned."""
    offset = paging.start(cursor, offset)
    rows, total = facts.listing(session, kind=kind, q=q, limit=limit, offset=offset)
    response.headers["X-Total-Count"] = str(total)
    paging.finish(response, offset, limit, total)
    return {"items": [facts.as_json(row) for row in rows], "total": total}


@router.get("/export")
def export_learned(session: Session = Depends(get_session)) -> dict:
    """Everything learned, as one JSON document the person can read outside
    the app. Declared before `/{fact_id}` so that path does not swallow it.

    Assembled here rather than in either store because it is the one answer
    that needs both, and `ai/learning.py` already asks `ai/facts.py` whether
    its runner is on: a reader in `facts` that named `learning` would close
    that loop. Read-only and complete on purpose, with no import beside it:
    a file the person can open in any editor is the point, and an import path
    would be a second way for rows to appear that nothing in the app derived.
    """
    rows, _total = facts.listing(session, limit=10_000)
    boosts: dict[str, list[dict]] = {}
    for family in learning.FAMILIES:
        for key, weight in learning.boosts(session, family).items():
            boosts.setdefault(family, []).append(
                {"key": [str(part) for part in key], "weight": weight}
            )
    return {
        "exported_at": utcnow().isoformat(),
        "switches": facts.switches(deps.get_config()),
        "facts": [facts.as_json(row) for row in rows],
        "corrections": [
            {
                "id": item.id,
                "kind": item.kind,
                "subject": item.subject,
                "from": item.from_value,
                "to": item.to_value,
                "excerpt": item.excerpt,
                "at": item.at.isoformat() if item.at else None,
            }
            for item in learning.corrections(session)
        ],
        "boosts": boosts,
    }


@router.get("/summary")
def learned_summary(session: Session = Depends(get_session)) -> dict:
    """The "Learned from you" line (WORLD_CLASS_PLAN row 20, I7): how many
    corrections, and filing accuracy over the notes the AI filed last
    (`learning.filing_accuracy`). Declared before `/{fact_id}`."""
    return learning.filing_accuracy(session)


@router.get("/switches")
def get_switches() -> dict:
    """Every switch, as the runners see it (the master wins)."""
    return facts.switches(deps.get_config())


@router.put("/switches")
def put_switches(body: SwitchBody) -> dict:
    """Set any subset of the switches."""
    try:
        return facts.set_switches(deps.get_config(), body.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("")
def forget_everything(body: ForgetBody, session: Session = Depends(get_session)) -> dict:
    """Forget everything learned. Notes and revisions are not touched.

    `confirm` is required rather than implied by the verb: this is the one
    button in the app that throws away work nobody can get back, and a
    mis-routed DELETE with no body should do nothing at all.

    Nobody can get it back *from the notebook*: what went is kept in the undo
    bin (`core/undo_bin.py`) and the answer carries the token that
    `POST /learned/unforget` takes (INBOX 898).
    """
    if not body.confirm:
        raise HTTPException(
            status_code=400, detail="Confirm that you want to forget everything learned, then try again."
        )
    token = undo_bin.stash(deps.get_config().data_dir, "learned", facts.snapshot(session))
    facts.forget(session)
    session.commit()
    return {"forgotten": True, "undo_token": token}


class UnforgetBody(BaseModel):
    token: str = Field(min_length=1, max_length=64)


@router.post("/unforget")
def unforget_everything(body: UnforgetBody, session: Session = Depends(get_session)) -> dict:
    """Undo of `DELETE /learned` (INBOX 898)."""
    config = deps.get_config()
    saved, _ = undo_bin.take(config.data_dir, "learned", body.token)
    put = facts.unforget(session, saved)
    session.commit()
    undo_bin.finish(config.data_dir, body.token)
    return {"restored": put}


class BulkBody(BaseModel):
    #: At most one page of the table and a bit: the Settings list shows fifty
    #: rows, and a request for thousands is not a selection anyone made.
    ids: list[int] = Field(min_length=1, max_length=500)
    action: Literal["delete", "reset", "restore"]


@router.post("/bulk")
def bulk_action(body: BulkBody, session: Session = Depends(get_session)) -> dict:
    """Delete or reset several facts in one request (the plan's `{ids, action}`).

    The reason this is a route and not a loop in the browser is written at the
    top of the Settings section that calls it: N requests can half fail, and a
    selection that half happened is worse than one that did not. So every row
    is changed in one transaction, and each one exactly as its single-row
    route changes it, correction included, because a bulk delete that the
    learning loop could not see would teach it nothing.

    Declared before `/{fact_id}`, or that path would swallow "bulk". A reset
    of a row nobody edited is a no-op and is not counted; an id that is gone
    or not visible (a private note's fact) comes back in `missing`, so the
    Settings list can say what it could not do rather than claim it all.
    """
    done = 0
    missing: list[int] = []
    for fact_id in dict.fromkeys(body.ids):
        if body.action == "restore":
            #: Undo of a bulk delete (INBOX 898).
            gone = facts.tombstoned(session, fact_id)
            if gone is None:
                missing.append(fact_id)
                continue
            _unlearn_deletion(session, gone)
            facts.restore(session, gone)
            done += 1
            continue
        row = facts.visible(session, fact_id)
        if row is None:
            missing.append(fact_id)
            continue
        if body.action == "delete":
            learning.record(
                session,
                kind="delete_fact",
                subject={"entry_id": row.entry_id, "fact_id": row.id, "kind": row.kind},
                excerpt=row.original_text or row.text,
            )
            facts.remove(session, row)
            done += 1
        elif row.edited_by_user:
            facts.reset(session, row)
            done += 1
    session.commit()
    return {"action": body.action, "done": done, "missing": missing}


def _unlearn_deletion(session: Session, row) -> None:  # noqa: ANN001
    """Drop the `delete_fact` correction that deleting `row` taught the loop.

    Restoring a fact says the deletion was a slip; leaving the lesson behind
    would have the notebook learn from a mistake the person took back.
    """
    from sqlalchemy import select

    from tessellate.core.database import AuditLog

    rows = session.scalars(
        select(AuditLog)
        .where(AuditLog.action == "correction", AuditLog.detail.like("delete_fact:%"))
        .order_by(AuditLog.id.desc())
    ).all()
    for item in rows:
        subject = (item.payload or {}).get("subject") or {}
        if subject.get("fact_id") == row.id:
            session.delete(item)
            break


@router.get("/{fact_id}")
def get_fact(fact_id: int, session: Session = Depends(get_session)) -> dict:
    row = facts.visible(session, fact_id)
    if row is None:
        raise HTTPException(status_code=404, detail="That learned fact could not be found.")
    return facts.as_json(row)


@router.patch("/{fact_id}")
def patch_fact(fact_id: int, body: FactPatch, session: Session = Depends(get_session)) -> dict:
    """Correct what a fact says. No later run overwrites it."""
    row = facts.visible(session, fact_id)
    if row is None:
        raise HTTPException(status_code=404, detail="That learned fact could not be found.")
    before = row.text
    facts.edit(session, row, body.text)
    learning.record(
        session,
        kind="edit_fact",
        subject={"entry_id": row.entry_id, "fact_id": row.id, "kind": row.kind},
        from_value=before[:200],
        to_value=body.text[:200],
    )
    session.commit()
    return facts.as_json(row)


@router.post("/{fact_id}/reset")
def reset_fact(fact_id: int, session: Session = Depends(get_session)) -> dict:
    """Put the model's own words back."""
    row = facts.visible(session, fact_id)
    if row is None:
        raise HTTPException(status_code=404, detail="That learned fact could not be found.")
    facts.reset(session, row)
    session.commit()
    return facts.as_json(row)


@router.delete("/{fact_id}", status_code=204)
def delete_fact(fact_id: int, session: Session = Depends(get_session)) -> Response:
    """Delete a fact, and remember that it was deleted.

    Two writes, deliberately: the tombstone stops the next run re-deriving
    it, and the correction is what the loop learns from. Either alone is a
    half measure, and it was the half measure that made "I keep telling it
    no" a recurring report elsewhere in this app.
    """
    row = facts.visible(session, fact_id)
    if row is None:
        raise HTTPException(status_code=404, detail="That learned fact could not be found.")
    learning.record(
        session,
        kind="delete_fact",
        subject={"entry_id": row.entry_id, "fact_id": row.id, "kind": row.kind},
        excerpt=row.original_text or row.text,
    )
    facts.remove(session, row)
    session.commit()
    return Response(status_code=204)


@router.post("/{fact_id}/restore")
def restore_fact(fact_id: int, session: Session = Depends(get_session)) -> dict:
    """Undo of `DELETE /learned/{id}`: the fact is back, and the deletion is forgotten (INBOX 898)."""
    row = facts.tombstoned(session, fact_id)
    if row is None:
        raise HTTPException(status_code=404, detail="That learned fact is not deleted.")
    _unlearn_deletion(session, row)
    facts.restore(session, row)
    session.commit()
    return facts.as_json(row)


@router.delete("/corrections/{correction_id}")
def remove_correction(correction_id: int, session: Session = Depends(get_session)) -> dict:
    """Undo of `POST /learned/corrections`: take that one correction back (INBOX 898).

    Only a correction row, and only by the id the POST returned, so an Undo
    cannot reach any other event in the log.
    """
    from tessellate.core.database import AuditLog

    row = session.get(AuditLog, correction_id)
    if row is None or row.action != "correction":
        raise HTTPException(status_code=404, detail="That correction could not be found.")
    session.delete(row)
    session.commit()
    return {"removed": correction_id}
