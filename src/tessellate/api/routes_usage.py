"""`/usage`: the local usage ledger's door (WORLD_CLASS_PLAN H9, row 27).

The ledger is `core/usage.py`. The page batches its counts and sends them
here; Settings reads them back. Behind the sign-in like every other route.
"""

from __future__ import annotations

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from tessellate.core import deps, usage

router = APIRouter(prefix="/usage", tags=["usage"])
#: Quick capture from anywhere (H9): the command this install's own
#: interpreter or executable runs for `--capture`, for Settings to show.
capture_router = APIRouter(prefix="/capture", tags=["usage"])


class UsageIn(BaseModel):
    features: list[str] = Field(default_factory=list, max_length=200)


class KnownIn(BaseModel):
    #: The features the page offers (its palette commands, its tabs), so the
    #: answer can name the ones never used at all.
    known: list[str] = Field(default_factory=list, max_length=2000)


@router.post("")
def count(body: UsageIn) -> dict:
    return {"counted": usage.record(deps.get_config().data_dir, body.features)}


@router.post("/summary")
def summary(body: KnownIn) -> dict:
    return usage.summary(deps.get_config().data_dir, body.known)


@router.get("/offer")
def offer(known: list[str] = Query(default_factory=list, max_length=2000)) -> dict:
    """The one feature to try this week, or none (`usage.weekly_offer`). A GET
    because it only notes which name it said (names, never user data), so the
    page asks again without a body and nothing a person made is written."""
    return {"name": usage.weekly_offer(deps.get_config().data_dir, known)}


@router.delete("")
def clear() -> dict:
    usage.clear(deps.get_config().data_dir)
    return {"cleared": True}


@capture_router.get("/command")
def capture_command() -> dict:
    """The exact command line for `--capture` on this install: the frozen
    build's executable, or this interpreter with `-m tessellate`. Quoted, so
    a path with spaces (Program Files) pastes as one argument."""
    import sys

    exe = sys.executable
    if getattr(sys, "frozen", False):
        return {"command": f'"{exe}" --capture'}
    return {"command": f'"{exe}" -m tessellate --capture'}
