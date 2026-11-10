"""Tidy's routes (INBOX 691): the reviews in `entry/tidy.py` over HTTP.

`GET /tidy` is every review with its count (the Notes dock's badge reads the
total); `GET /tidy/{key}` lists one; `POST /tidy/{key}/apply` acts on the ids
ticked and answers with one `undo_id`; `POST /tidy/undo/{id}` puts a run
back; `GET /tidy/history` is the recent runs; `PUT /tidy/auto` switches a
review's automatic run; `POST /tidy/{key}/dismiss` drops rows for good and
`.../undismiss` brings them back; `POST /tidy/link-reasons/run` queues the
whole-notebook reason pass as a durable job, and `.../stop` asks it to stop.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from tessellate.core import deps, jobs, jobruns
from tessellate.core.deps import get_session
from tessellate.entry import tidy

router = APIRouter(prefix="/tidy", tags=["tidy"])


def _review(key: str) -> tidy.Review:
    review = tidy.REVIEWS.get(key)
    if review is None:
        raise HTTPException(status_code=404, detail="No such review.")
    return review


def _level(review: tidy.Review, level: str) -> str:
    return level if level in review.levels else review.level


class ApplyBody(BaseModel):
    ids: list[str] = Field(default_factory=list, max_length=2000)
    level: str = Field(default="", max_length=20)


class DismissBody(BaseModel):
    ids: list[str] = Field(default_factory=list, max_length=2000)


class AutoBody(BaseModel):
    key: str = Field(max_length=40)
    on: bool


@router.get("")
def tidy_summary(session: Session = Depends(get_session)) -> dict:
    return tidy.summary(session, deps.get_config())


@router.get("/history")
def tidy_history(limit: int = Query(default=20, ge=1, le=100), session: Session = Depends(get_session)) -> dict:
    return {"runs": tidy.history(session, limit)}


@router.put("/auto")
def tidy_auto(body: AutoBody, session: Session = Depends(get_session)) -> dict:  # noqa: ARG001
    _review(body.key)
    try:
        settings = tidy.set_auto(deps.get_config(), body.key, body.on)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"key": body.key, "auto": settings[body.key]}


@router.post("/undo/{undo_id}")
def tidy_undo(undo_id: int, session: Session = Depends(get_session)) -> dict:
    try:
        return tidy.undo(session, undo_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/link-reasons/run")
def tidy_link_reasons_run(request: Request) -> dict:
    """The whole notebook's link reasons, named in the background (a durable
    job: a quit mid-way resumes next launch, and Quit in the Tasks panel
    stops it between chunks)."""
    workspace = request.headers.get("X-Workspace-ID") or "default"
    jobs.enqueue("tidy-link-reasons", tidy.respecify_all, workspace, dedupe_key=("tidy-link-reasons", workspace))
    return {"queued": True}


@router.get("/{key}")
def tidy_rows(key: str, level: str = Query(default="", max_length=20), session: Session = Depends(get_session)) -> dict:
    review = _review(key)
    found = tidy.rows(session, key, _level(review, level))
    return {
        "key": key, "label": review.label, "about": review.about, "level": _level(review, level),
        "levels": list(review.levels), "count": len(found), "rows": found[: tidy.MAX_ROWS],
    }


@router.post("/{key}/dismiss")
def tidy_dismiss(key: str, body: DismissBody, session: Session = Depends(get_session)) -> dict:
    """Dismiss suggestions for good: the rows are not listed, counted or applied
    again. `dismissed` is how many this review has dismissed in all."""
    _review(key)
    return {"dismissed": tidy.dismiss(session, deps.get_config(), key, body.ids)}


@router.post("/{key}/undismiss")
def tidy_undismiss(key: str, body: DismissBody) -> dict:
    _review(key)
    return {"dismissed": tidy.undismiss(deps.get_config(), key, body.ids)}


@router.post("/{key}/apply")
def tidy_apply(key: str, body: ApplyBody, session: Session = Depends(get_session)) -> dict:
    review = _review(key)
    with jobruns.job_run("tidy", origin="you") as run:
        result = tidy.apply(session, key, body.ids, _level(review, body.level))
        run.result = result["message"]
    return result
