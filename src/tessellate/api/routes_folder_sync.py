"""Sync without a server (WORLD_CLASS_PLAN row 36, Q34): `entry/folder_sync.py` behind two routes.

The person points this install at a folder (a USB stick, a Syncthing or cloud-drive folder) and types a sync
passphrase, the same on every computer; one press reads the other computers' files there and writes this one's.
The passphrase is used for that run and never stored. The folder and the time are remembered so the sheet can
offer them next time.
"""

from __future__ import annotations

import threading

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from tessellate.api.this_computer import this_computer_only
from tessellate.core import deps
from tessellate.core.deps import get_session
from tessellate.entry import folder_sync

router = APIRouter(prefix="/sync", tags=["sync"])
_busy = threading.Lock()


class FolderIn(BaseModel):
    folder: str = Field(max_length=1000)
    passphrase: str = Field(max_length=200)


def _state_path():  # noqa: ANN202
    return deps.get_config().data_dir / "folder_sync_state.json"


@router.get("/folder")
def folder_status() -> dict:
    state = folder_sync.load_state(_state_path())
    return {"folder": state.folder, "last": state.last, "device": state.device, "min_passphrase": folder_sync.MIN_PASSPHRASE}


#: This computer only: the folder is a path on the server's own disk, so only the person at this
#: computer, who can already reach every folder on it, may choose one (a phone on the LAN may not).
@router.post("/folder", dependencies=[Depends(this_computer_only)])
def sync_folder(body: FolderIn, session: Session = Depends(get_session)) -> dict:
    if not _busy.acquire(blocking=False):
        raise HTTPException(409, "A sync is already running.")
    try:
        state = folder_sync.load_state(_state_path())
        try:
            counts = folder_sync.run(session, state, body.folder, body.passphrase, notebook=deps.get_config().data_dir)
        except folder_sync.SyncError as exc:
            raise HTTPException(400, str(exc)) from exc
        folder_sync.save_state(_state_path(), state)
        return counts
    finally:
        _busy.release()
