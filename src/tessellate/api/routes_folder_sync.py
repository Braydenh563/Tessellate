"""Sync through a folder (WORLD_CLASS_PLAN B6 decision 14, row 36): `entry/folder_sync.py` behind two routes.

The person points this install at a folder (a USB stick, a Syncthing or cloud-drive folder) and types a sync
passphrase, the same on every computer; one press reads the other computers' files there and writes this one's.
The passphrase is used for that run and never stored. The folder and the time are remembered so the sheet can
offer them next time. The shared last-synced line is `GET /sync/status` (`api/routes_sync.py`), which a run
through the folder updates like a pull over the home network.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from tessellate.api.this_computer import this_computer_only
from tessellate.core import deps, sync_state
from tessellate.core.deps import get_session
from tessellate.entry import folder_sync, sync_pull

router = APIRouter(prefix="/sync", tags=["sync"])


class FolderIn(BaseModel):
    folder: str = Field(max_length=1000)
    passphrase: str = Field(max_length=200)


@router.get("/folder")
def folder_status() -> dict:
    data_dir = deps.get_config().data_dir
    state = folder_sync.load_state(data_dir)
    return {**state, "device": sync_state.device_id(data_dir), "min_passphrase": folder_sync.MIN_PASSPHRASE}


#: This computer only: the folder is a path on the server's own disk, so only the person at this
#: computer, who can already reach every folder on it, may choose one (a phone on the LAN may not).
@router.post("/folder", dependencies=[Depends(this_computer_only)])
def sync_folder(body: FolderIn, session: Session = Depends(get_session)) -> dict:
    if not sync_pull.RUNNING.acquire(blocking=False):
        raise HTTPException(409, sync_pull.BUSY)
    try:
        try:
            return folder_sync.run(session, deps.get_config().data_dir, body.folder, body.passphrase)
        except folder_sync.SyncError:
            raise HTTPException(400, folder_sync.last_problem()) from None
    finally:
        sync_pull.RUNNING.release()
