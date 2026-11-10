"""Private spaces: open, close, and turn a space private or ordinary (INBOX 1727).

One door for every private space: the vault password, or the PIN on this
computer only (never over the network), as the lock screen takes them. The
door closes after the idle minutes in Settings, on lock and when the window
closes (`core/spacelock.py`). Sealing is `entry/private_space.py`.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from tessellate.api import routes_auth
from tessellate.core import deps, pinstore, spacelock, vault
from tessellate.core.config import ConfigManager
from tessellate.core.database import Space
from tessellate.core.deps import get_config, get_session
from tessellate.entry import manager, private_space

router = APIRouter(tags=["spaces"])

#: The refusal when sealing needs the key and this session has none.
LOCKED_DETAIL = "Unlock your private spaces first."


def _is_open(token: str | None) -> bool:
    return spacelock.opened(token)


@router.get("/private-spaces/status")
def status(
    request: Request,
    config: ConfigManager = Depends(get_config),
    x_auth_token: str | None = Header(default=None),
) -> dict:
    """Whether this session has the private spaces open, and how it may open them."""
    return {
        "open": _is_open(x_auth_token),
        "idle_minutes": spacelock.idle_minutes(),
        "pin": routes_auth._from_this_computer(request) and pinstore.is_set(config.data_dir),
    }


class UnlockBody(BaseModel):
    #: The vault password, or the PIN (this computer only).
    secret: str = Field(min_length=4, max_length=routes_auth.MAX_PASSWORD_CHARS)


@router.post("/private-spaces/unlock")
def unlock(
    body: UnlockBody,
    request: Request,
    session: Session = Depends(get_session),
    config: ConfigManager = Depends(get_config),
    x_auth_token: str | None = Header(default=None),
) -> dict:
    """The lock screen's check and throttle: a wrong secret here is a wrong
    guess everywhere, so this is not a second place to guess the password."""
    client = routes_auth._client_key(request)
    routes_auth._refuse_if_throttled(client)
    user = routes_auth._get_user(session)
    if user is None:
        raise HTTPException(status_code=400, detail="No password is set yet. Set one up first.")
    if routes_auth._password_matches(body.secret, user.password_hash):
        if vault.key() is None:
            vault.open_with(session, body.secret)
            session.commit()  # the vault row, when open_with had to create one
    else:
        dek = routes_auth._unlock_with_pin(request, session, user, body.secret, config)
        if dek is None:
            raise HTTPException(status_code=401, detail="That password or PIN is wrong.")
        vault.set_key(dek)
    routes_auth._unlock_succeeded(client)
    vault.grant(x_auth_token)
    if vault.key() is None:
        raise HTTPException(status_code=409, detail="The private notes key could not be opened.")
    spacelock.open_for(x_auth_token)
    # A run cut short (a crash while a space was being sealed) finishes here.
    sealed = sum(private_space.seal_space_members(session, sid) for sid in private_space.private_space_ids(session))
    manager.log_action(session, "unlocked", "vault", detail="private spaces opened")
    session.commit()
    if sealed:
        manager.scrub_private_leftovers(session)
    return {"open": True}


@router.post("/private-spaces/touch")
def touch(x_auth_token: str | None = Header(default=None)) -> dict:
    """The person is at the keyboard (the window sends this on their own
    input, at most once a minute): the idle window starts again."""
    return {"open": vault.key() is not None and spacelock.is_open(x_auth_token)}


@router.post("/private-spaces/lock")
def lock(x_auth_token: str | None = Header(default=None)) -> dict:
    """Close the private spaces for this session (the lock button, page close)."""
    spacelock.close_for(x_auth_token)
    return {"open": False}


class PrivateBody(BaseModel):
    private: bool
    #: Turning Private off: keep every item private (default) or make the
    #: ones the space sealed ordinary.
    keep_private: bool = True


def _refuse_unless_open(token: str | None) -> None:
    if not _is_open(token):
        raise HTTPException(status_code=423, detail=LOCKED_DETAIL)


@router.put("/spaces/{space_id}/private")
def set_space_private(
    space_id: str,
    body: PrivateBody,
    session: Session = Depends(get_session),
    x_auth_token: str | None = Header(default=None),
) -> dict:
    """Turn a space private (seal everything in it, in one transaction, so it
    is never half-sealed) or ordinary (the two-way answer)."""
    space = deps.get_or_404(session, Space, space_id, "That space could not be found.")
    if space.id == "default" and body.private:
        raise HTTPException(status_code=400, detail="The default space cannot be private.")
    if body.private == bool(space.is_private):
        return {"private": space.is_private, "changed": 0}
    if body.private and vault.key() is None:
        raise HTTPException(status_code=423, detail=LOCKED_DETAIL)
    if not body.private or private_space.private_space_ids(session):
        _refuse_unless_open(x_auth_token)
    space.is_private = body.private
    session.flush()
    if body.private:
        changed = private_space.seal_space_members(session, space.id)
    else:
        changed = 0 if body.keep_private else private_space.unseal_space_members(session, space.id)
        if body.keep_private:
            private_space.keep_members_private(session, space.id)
    manager.log_action(session, "edited", "space", None, f"space {space.id} private={body.private}")
    session.commit()
    if body.private:
        manager.scrub_private_leftovers(session)
        spacelock.open_for(x_auth_token)
    return {"private": space.is_private, "changed": changed}

