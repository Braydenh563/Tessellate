"""The lag log (core/lagwatch.py): the browser posts; GET and DELETE read and clear
the file (`<data dir>/logs/lag.log`) for whoever is asked to look at it.

Behind the unlock gate like every route but `/logs/client`: a lag report is
written after the app is open, never on the loading screen, and from a phone
on the network as well as this computer, because a phone's lag is as much the
app's as the desktop's.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from tessellate.core import deps, lagwatch, maintenance

logger = logging.getLogger("tessellate.lag")
router = APIRouter(tags=["logs"])


class LagBatch(BaseModel):
    #: At most 20 reports a post; the watcher sends a batch every 10 seconds.
    events: list[dict] = Field(max_length=20)


def _logs_dir():  # noqa: ANN202
    return maintenance.logs_dir(deps.get_config().data_dir)


@router.post("/logs/lag", status_code=201)
def record_lag(body: LagBatch) -> dict:
    """Keep the reports on disk and put a one-line summary of each in the log."""
    events = [lagwatch.clean(e) for e in body.events]
    for e in events:
        # The fields come from the browser: a line break in one could forge a
        # log record (CodeQL py/log-injection), so each is one line here.
        kind, ms, view, cause = (
            str(e.get(key, "?")).replace("\r", " ").replace("\n", " ") for key in ("kind", "ms", "view", "cause")
        )
        logger.warning("[lag] %s %sms on %s: %s", kind, ms, view, cause)
    return {"kept": lagwatch.append(_logs_dir(), events)}


@router.get("/logs/lag")
def lag_reports(limit: int = Query(default=200, ge=1, le=2000)) -> list[dict]:
    return lagwatch.recent(_logs_dir(), limit)


@router.delete("/logs/lag")
def clear_lag_reports() -> dict:
    lagwatch.clear(_logs_dir())
    return {"cleared": True}
