"""Sync with another computer (WORLD_CLASS_PLAN B6): the segment it reads, and Sync now.

Behind the unlock gate like every route (decision 4): the other computer
reads `GET /sync/segment` as a signed-in, allowed LAN device of this one,
under the LAN rules unchanged. The work is in `entry/sync_segments.py` and
`entry/sync_pull.py`; this module only routes.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from tessellate.core import deps, sync_state
from tessellate.core.deps import get_session
from tessellate.entry import sync_pull, sync_segments

router = APIRouter(tags=["sync"])


@router.get("/sync/status")
def sync_status() -> dict:
    """Settings, Import & export, Sync: the last sync, its counts and its failure sentence."""
    return sync_pull.status(deps.get_config().data_dir)


@router.get("/sync/segment")
def sync_segment(
    since: int = Query(default=0, ge=0),
    peer: str = Query(min_length=1, max_length=40),
    session: Session = Depends(get_session),
) -> dict:
    """This notebook's notes changed after `since`, for the computer named `peer`."""
    device = sync_state.device_id(deps.get_config().data_dir)
    return sync_segments.export_segment(session, device, since, peer)


@router.post("/sync/now")
def sync_now(session: Session = Depends(get_session)) -> dict:
    """Pull the paired computer's changes into this notebook."""
    return sync_pull.pull(session, deps.get_config().data_dir)
