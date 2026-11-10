"""One-shot carry-over of the app's saved browser settings from the
`http://127.0.0.1:PORT` origin to `http://localhost:PORT`.

The owner, 2026-11-10 (HANDOVER "Hello origin"): the desktop window opens
`localhost` so Windows Hello works (WebAuthn refuses an IP address as an RP
id), and nothing may reset. `localStorage` belongs to one origin, so the old
origin's page (`origin-bridge.html`, opened once by the desktop shell) posts
its keys here and the new origin's copy of the same page takes them.

Both routes are this computer only (a tunnel included), single use, short
lived and bounded; the session token is never carried (the new origin signs
in on its own). Nothing is written to disk. `tests/test_origin_handoff.py`.
"""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from tessellate.api import routes_auth
from tessellate.api.this_computer import REFUSAL

router = APIRouter(prefix="/origin-handoff", tags=["auth"])

TTL_SECONDS = 120.0
MAX_KEYS = 400
MAX_KEY_CHARS = 128
MAX_VALUE_CHARS = 262_144
MAX_TOTAL_CHARS = 1_048_576
#: Never carried: a bearer token for the old origin's session.
NEVER = frozenset({"token"})

_held: dict[str, object] = {}


def _now() -> float:  # a seam: tests give it a fixed clock
    return time.monotonic()


def _here(request: Request) -> None:
    if not routes_auth._from_this_computer(request):
        raise HTTPException(status_code=403, detail=REFUSAL)


class HandoffIn(BaseModel):
    items: dict[str, str] = Field(default_factory=dict)


@router.post("/put", dependencies=[Depends(_here)])
def put(body: HandoffIn) -> dict:
    items = {k: v for k, v in body.items.items() if k not in NEVER}
    if len(items) > MAX_KEYS or any(len(k) > MAX_KEY_CHARS or len(v) > MAX_VALUE_CHARS for k, v in items.items()):
        raise HTTPException(status_code=413, detail="Too much to carry over.")
    if sum(len(k) + len(v) for k, v in items.items()) > MAX_TOTAL_CHARS:
        raise HTTPException(status_code=413, detail="Too much to carry over.")
    #: A second, empty put (the bridge opened twice, a reload) does not wipe a set still held (review 5850946759).
    held = _held.get("items")
    if not items and isinstance(held, dict) and held and _now() <= float(_held.get("expires", 0.0)):  # type: ignore[arg-type]
        return {"ok": True, "count": 0, "kept": len(held)}
    _held.clear()
    _held.update(items=items, expires=_now() + TTL_SECONDS)
    return {"ok": True, "count": len(items)}


@router.post("/take", dependencies=[Depends(_here)])
def take() -> dict:
    """The held keys once, then nothing: a second call, or one after the
    window of two minutes, gets an empty set."""
    items = _held.get("items")
    expires = float(_held.get("expires", 0.0))  # type: ignore[arg-type]
    _held.clear()
    if not isinstance(items, dict) or _now() > expires:
        return {"items": {}}
    return {"items": items}
