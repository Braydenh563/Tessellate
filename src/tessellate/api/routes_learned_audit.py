"""Check what it learned, over HTTP (CHAT_PLAN decision 68).

The pass itself is `ai/learned_audit.py` (the rules) and
`ai/learned_audit_run.py` (the reads and writes); this is the thin shell the
What it learned panel calls. Its own file, with its own prefix, because
`routes_learned.py` ends in `/{fact_id}` routes and the order of the two
would matter for no reason.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from tessellate.ai import learned_audit_run
from tessellate.core import jobruns
from tessellate.core.deps import get_session

router = APIRouter(prefix="/learned/audit", tags=["learned"])


@router.post("/run")
def run_check(session: Session = Depends(get_session)) -> dict:
    """Check now. The run is a job with lines (Settings, Background jobs); the
    answer says what went and why, and carries the stamp `/undo` takes."""
    with jobruns.job_run("learned-audit", origin="you") as run:
        run.say("Re-reading what it learned against its notes.")
        done = learned_audit_run.run_check(session)
        session.commit()
        learned_audit_run.say_lines(run, done)
        run.result = learned_audit_run.summary_words(done)
    return {**done, "summary": run.result}


@router.get("/last")
def last(session: Session = Depends(get_session)) -> dict:
    """What the latest check retired (still undoable) and what is flagged."""
    return learned_audit_run.last_run(session)


@router.get("/flags")
def flags(session: Session = Depends(get_session)) -> dict:
    """fact id -> the reason of its flag, for the list's rows."""
    return {"flags": {str(fact_id): reason for fact_id, reason in learned_audit_run.flags(session).items()}}


class UndoBody(BaseModel):
    run: str = Field(min_length=1, max_length=40)


@router.post("/undo")
def undo(body: UndoBody, session: Session = Depends(get_session)) -> dict:
    """Undo of `/run`: put back what that check retired."""
    lifted = learned_audit_run.undo(session, body.run)
    session.commit()
    return {"restored": lifted}


class KeepBody(BaseModel):
    fact_id: int


@router.post("/keep")
def keep(body: KeepBody, session: Session = Depends(get_session)) -> dict:
    """Keep it on one flagged row: the flag goes and later checks leave it be."""
    if not learned_audit_run.keep(session, body.fact_id):
        raise HTTPException(status_code=404, detail="That is not a flagged item.")
    session.commit()
    return {"kept": True}


@router.post("/unkeep")
def unkeep(body: KeepBody, session: Session = Depends(get_session)) -> dict:
    """Undo of `/keep`: the flag is raised again."""
    if not learned_audit_run.unkeep(session, body.fact_id):
        raise HTTPException(status_code=404, detail="That is not a kept flag.")
    session.commit()
    return {"flagged": True}


@router.post("/redo")
def redo(body: UndoBody, session: Session = Depends(get_session)) -> dict:
    """Redo of `/undo`: that check's retirements again."""
    taken = learned_audit_run.redo(session, body.run)
    session.commit()
    return {"retired": taken}
