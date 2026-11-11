"""The offline studio (WORLD_CLASS_PLAN row 35, Q34): an audio overview, or a brief before a
meeting, made from the person's notes and read in the natural voice on this computer.

The script is `ai/studio.py` (their own sentences under a fixed frame, no model), the voice
`ai/natural_voice.py`, and the result a saved recording with its timed lines
(`core/recording_make.py`). It runs as a Job in the Activity panel with Stop; the page polls
`GET /studio/runs/{id}` and then opens the recording from the Library, Recordings.
"""

from __future__ import annotations

import logging
import threading
from collections import OrderedDict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from tessellate.ai import natural_voice, studio
from tessellate.core import activity, jobs, recording_make
from tessellate.core.deps import get_session
from tessellate.repo import visible_notes

router = APIRouter(prefix="/studio", tags=["studio"])
logger = logging.getLogger("tessellate.studio")

#: Finished runs kept for the page to read once more.
KEEP_RUNS = 20
_lock = threading.Lock()
_runs: OrderedDict[str, dict] = OrderedDict()


class OverviewIn(BaseModel):
    #: What the overview is about: notes holding these words. Empty means the newest notes.
    topic: str = Field(default="", max_length=200)
    #: Or exactly these notes, in this order (a note that is private or binned is skipped).
    entry_ids: list[int] = Field(default_factory=list, max_length=studio.MAX_NOTES)
    minutes: int = Field(default=studio.DEFAULT_MINUTES, ge=1, le=max(studio.LENGTHS))
    #: A brief before a meeting: the same builder with a different frame.
    brief: bool = False


def _notes(session: Session, body: OverviewIn) -> list[dict]:
    if body.entry_ids:
        found = {row[0]: row[1] for row in visible_notes.by_ids(session, body.entry_ids)}
        rows = [(i, found[i]) for i in body.entry_ids if i in found]
    elif body.topic.strip():
        rows = visible_notes.holding(session, body.topic.strip(), limit=studio.MAX_NOTES)
    else:
        rows = visible_notes.recent(session, limit=studio.MAX_NOTES)
    return [{"id": row[0], "text": row[1]} for row in rows]


def _title(body: OverviewIn) -> str:
    topic = " ".join(body.topic.split())[:80]
    if body.brief:
        return f"Brief about {topic or 'recent notes'}"
    return f"Overview of {topic or 'recent notes'}"


def _set(job_id: str, **fields: object) -> None:
    with _lock:
        _runs.setdefault(job_id, {}).update(fields)
        while len(_runs) > KEEP_RUNS:
            _runs.popitem(last=False)


def _make(job: activity.Job, lines: list[str], title: str, derived: str, workspace: str | None) -> None:
    state, error, recording_id = "done", "", None
    try:
        wav, segments = natural_voice.render(
            lines,
            should_stop=lambda: job.stopped,
            progress=lambda done, total: (
                job.update(done=done, total=total, detail=f"{done} of {total} sentences"),
                _set(job.id, progress=round(done / total, 3)),
            ),
        )
        recording_id = recording_make.save_generated(title, wav, segments, derived=derived, workspace=workspace)
        job.result = "saved a recording"
    except natural_voice.Stopped:
        state = "stopped"
    except Exception:  # noqa: BLE001  # a bad voice is a run that says so, never a dead thread
        logger.warning("studio overview failed", exc_info=True)
        state, error = "failed", "Couldn't make that overview. Check the Natural voice package in Settings, Packages."
        if job.run is not None:
            job.run.fail(error)
    finally:
        _set(job.id, state=state, error=error, recording_id=recording_id)
        activity.finish(job)


@router.post("/overview", status_code=202)
def make_overview(body: OverviewIn, session: Session = Depends(get_session)) -> dict:
    if not natural_voice.available():
        raise HTTPException(status_code=503, detail=natural_voice.INSTALL_HINT)
    lines = studio.script(_notes(session, body), topic=body.topic, minutes=body.minutes, brief=body.brief)
    if not lines:
        raise HTTPException(status_code=422, detail="There is nothing in those notes to read aloud.")
    title = _title(body)
    job = activity.start("studio", f"Making “{title}”", stoppable=True)
    _set(job.id, state="running", progress=0.0, error="", recording_id=None, title=title, script=lines)
    work = (job, lines, title, "brief" if body.brief else "overview", session.info.get("workspace_id"))
    jobs.thread(f"studio-{job.id}", lambda: _make(*work))
    return {"id": job.id, "title": title, "script": lines}


@router.get("/runs/{run_id}")
def run_state(run_id: str) -> dict:
    with _lock:
        run = _runs.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="No such run.")
    return {"id": run_id, **run}


@router.post("/runs/{run_id}/stop")
def stop_run(run_id: str) -> dict:
    stopped, detail = activity.stop(run_id)
    return {"stopped": stopped, "detail": detail}
