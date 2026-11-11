"""Sync with another computer (WORLD_CLASS_PLAN B6): the segment it reads, pairing, and Sync now.

The other computer signs in here as an allowed LAN device of this one,
under the LAN rules unchanged (decision 4), and trades that sign-in for a
sync pass (decision 11) that `GET /sync/segment` takes in place of a
session. The work is in `entry/sync_segments.py`, `entry/sync_pull.py` and
`entry/sync_link.py`; this module only routes and gates.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from tessellate.api.routes_auth import require_unlock
from tessellate.api.this_computer import is_another_device, this_computer_only
from tessellate.core import deps, lantrust, sync_state
from tessellate.core.config import ConfigManager
from tessellate.core.deps import get_config, get_session
from tessellate.entry import sync_extras, sync_keys, sync_link, sync_pull, sync_segments

router = APIRouter(tags=["sync"])
#: Registered open in `app.ROUTERS`: its own gate takes a session or a sync pass.
open_router = APIRouter(tags=["sync"])

NO_DEVICE = "Allow this computer in Other devices on the other computer first."


def require_unlock_or_pass(
    request: Request,
    config: ConfigManager = Depends(get_config),
    x_auth_token: str | None = Header(default=None),
    x_sync_pass: str | None = Header(default=None),
) -> None:
    """A signed-in session, or a pass whose device is still in Other devices.

    Remove in Other devices ends the pass with the device: the pass names
    the device it was issued to, and an unlisted device's pass is refused."""
    device = sync_state.pass_device(config.data_dir, x_sync_pass)
    if device and any(d["id"] == device for d in lantrust.devices(config.data_dir)):
        return
    require_unlock(request, config, x_auth_token)


@open_router.get("/sync/segment", dependencies=[Depends(require_unlock_or_pass)])
def sync_segment(
    since: int = Query(default=0, ge=0),
    peer: str = Query(min_length=1, max_length=40),
    session: Session = Depends(get_session),
) -> dict:
    """This notebook's notes changed after `since`, for the computer named `peer`."""
    device = sync_state.device_id(deps.get_config().data_dir)
    return sync_segments.export_segment(session, device, since, peer)


@open_router.get("/sync/manifest", dependencies=[Depends(require_unlock_or_pass)])
def sync_manifest(peer: str = Query(min_length=1, max_length=40), session: Session = Depends(get_session)) -> dict:
    """One line per document, board and file with the hash of its state (decision 13)."""
    data_dir = deps.get_config().data_dir
    return sync_extras.manifest(session, data_dir, sync_state.device_id(data_dir))


@open_router.get("/sync/items", dependencies=[Depends(require_unlock_or_pass)])
def sync_items(
    kind: str = Query(pattern="^(document|board|file)$"),
    sid: list[str] = Query(default=[], max_length=sync_extras.MAX_ITEMS),
    peer: str = Query(min_length=1, max_length=40),
    session: Session = Depends(get_session),
) -> dict:
    """The whole state of each asked document, board or file."""
    data_dir = deps.get_config().data_dir
    return {"items": sync_extras.items(session, data_dir, sync_state.device_id(data_dir), kind, sid)}


@open_router.get("/sync/file", dependencies=[Depends(require_unlock_or_pass)])
def sync_file(
    sid: str = Query(min_length=3, max_length=80),
    peer: str = Query(min_length=1, max_length=40),
    session: Session = Depends(get_session),
) -> Response:
    """An attached file's bytes, for the paired computer to keep."""
    data_dir = deps.get_config().data_dir
    found = sync_extras.file_bytes(session, data_dir, sync_state.device_id(data_dir), sid)
    if found is None:
        raise HTTPException(status_code=404, detail="That file is not here.")
    return Response(content=found[0], media_type="application/octet-stream")


@router.get("/sync/status")
def sync_status() -> dict:
    """Settings, Import & export, Sync: the paired computer, the last sync, its counts and failure sentence."""
    return sync_pull.status(deps.get_config().data_dir)


class PassBody(BaseModel):
    peer: str = Field(min_length=1, max_length=40)


@router.post("/sync/pass")
def sync_pass(body: PassBody, request: Request) -> dict:
    """The other computer, signed in, asks for its pass (decision 11).

    It must carry a device cookie. A device from the network that had to wait
    for Allow is listed already; one that did not have to (asking off, or
    this computer itself) is listed now, so Remove can always end the pass."""
    data_dir = deps.get_config().data_dir
    raw = request.cookies.get(lantrust.DEVICE_COOKIE, "")
    if not 20 <= len(raw) <= 100:
        raise HTTPException(status_code=403, detail=NO_DEVICE)
    must_wait = is_another_device(request) and lantrust.load(data_dir)["ask_new_devices"]
    if must_wait and not lantrust.device_known(data_dir, raw):
        raise HTTPException(status_code=403, detail=NO_DEVICE)
    address = request.client.host if request.client else ""
    name = f"Paired notebook, {lantrust.device_name(request.headers.get('user-agent'))}"
    device = lantrust.remember_device(data_dir, raw, name, address)
    return {
        "pass": sync_state.issue_pass(data_dir, device),
        "device": sync_state.device_id(data_dir),
        # Decision 12: this notebook's data key, to a session its password opened.
        "key": sync_keys.own_key_for_peer(),
    }


class PairBody(BaseModel):
    address: str = Field(min_length=3, max_length=200)
    password: str = Field(min_length=1, max_length=1024)


@router.post("/sync/pair", dependencies=[Depends(this_computer_only)])
def sync_pair(body: PairBody) -> dict:
    """Pair with the computer at `address`, signing in with its password (decision 10).

    From this computer only: it makes this computer connect somewhere."""
    data_dir = deps.get_config().data_dir
    try:
        sync_link.pair(data_dir, body.address, body.password)
    except sync_link.PairError as exc:
        return {**sync_pull.status(data_dir), "error": str(exc)}
    return {**sync_pull.status(data_dir), "error": ""}


@router.delete("/sync/pair", dependencies=[Depends(this_computer_only)])
def sync_unpair() -> dict:
    """Forget the paired computer here; Remove it in Other devices there to end its pass."""
    data_dir = deps.get_config().data_dir
    sync_state.forget_link(data_dir)
    return sync_pull.status(data_dir)


@router.post("/sync/now")
def sync_now(session: Session = Depends(get_session)) -> dict:
    """Pull the paired computer's changes into this notebook."""
    return sync_pull.pull(session, deps.get_config().data_dir)
