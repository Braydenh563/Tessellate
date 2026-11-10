"""Windows Hello unlock on this computer (INBOX 1727; core/hellostore.py).

Enrolment, behind the password like the PIN: `/auth/hello/enrol/begin` hands
out two single-use challenges (one to create the platform credential, one
to read its PRF output with a first assertion) and the PRF salt;
`/auth/hello/enrol/finish` checks both against core/webauthn.py and wraps
the vault key under the PRF output.

Unlock: `/auth/hello/begin` gives a challenge for the stored credential, and
`/auth/hello/unlock` (the lock screen) or `/private-spaces/unlock-hello`
(the private spaces) take the assertion. The signature is verified before
the unwrap is even tried; a wrong one is a wrong guess for the address's
waits, like a wrong password. Every route is this computer only, a tunnel
included (`routes_auth._from_this_computer`), and the password is always
the way back.
"""

from __future__ import annotations

import base64
import ipaddress
import logging
import secrets

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from tessellate.api import routes_auth
from tessellate.api.this_computer import REFUSAL, this_computer_only
from tessellate.core import hellostore, pinstore, vault, webauthn
from tessellate.core.config import ConfigManager
from tessellate.core.database import User
from tessellate.core.deps import get_config, get_session
from tessellate.entry.manager import log_action

router = APIRouter(prefix="/auth/hello", tags=["auth"])
log = logging.getLogger("tessellate.hello")

#: The one refusal for any assertion that does not open the vault, so a
#: caller learns nothing about which check failed.
NOT_UNLOCKED = "Windows Hello did not unlock it. Use your password."
NO_LOCALHOST = "Windows Hello works when the app is opened at localhost."

_B64 = 65536  # a generous bound on any one base64url field


def _here(request: Request) -> None:
    if not routes_auth._from_this_computer(request):
        raise HTTPException(status_code=403, detail=REFUSAL)


def _rp_id(request: Request) -> str:
    """The page's own host name: browsers refuse an IP address as an RP id."""
    host = request.url.hostname or ""
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return host
    raise HTTPException(status_code=409, detail=NO_LOCALHOST)


def _origin(request: Request) -> str:
    return str(request.base_url).rstrip("/")


class PasswordIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=routes_auth.MAX_PASSWORD_CHARS)


class AssertionIn(BaseModel):
    ticket: str = Field(min_length=1, max_length=64)
    credential_id: str = Field(min_length=1, max_length=2048)
    client_data_json: str = Field(min_length=1, max_length=_B64)
    authenticator_data: str = Field(min_length=1, max_length=_B64)
    signature: str = Field(min_length=1, max_length=_B64)
    prf: str = Field(min_length=1, max_length=128)


class EnrolIn(BaseModel):
    ticket: str = Field(min_length=1, max_length=64)
    credential_id: str = Field(min_length=1, max_length=2048)
    client_data_json: str = Field(min_length=1, max_length=_B64)
    attestation_object: str = Field(min_length=1, max_length=_B64)
    #: The first assertion, when the PRF output came from it rather than
    #: from the create call (Windows Hello returns it only on a get).
    assertion: AssertionIn | None = None
    prf: str = Field(min_length=1, max_length=128)


@router.post("/enrol/begin", dependencies=[Depends(routes_auth.require_unlock), Depends(this_computer_only)])
def enrol_begin(
    body: PasswordIn,
    request: Request,
    session: Session = Depends(get_session),
    config: ConfigManager = Depends(get_config),
    x_auth_token: str | None = Header(default=None),
) -> dict:
    """Behind the password, as setting up a PIN is."""
    _here(request)
    rp_id = _rp_id(request)
    user = routes_auth._check_current_password(request, session, body.current_password)
    if not hellostore.available(config.data_dir):
        raise HTTPException(
            status_code=409,
            detail="This computer has no protected store for Windows Hello, so the password is the only way in here.",
        )
    if vault.key() is None:
        vault.open_with(session, body.current_password)
        session.commit()  # the vault row, when open_with had to create one
        vault.grant(x_auth_token)
    get_ticket, get_challenge = hellostore.issue("enrol-get")
    salt = secrets.token_bytes(32)
    ticket, challenge = hellostore.issue("enrol", {"get": get_ticket, "salt": salt})
    return {
        "ticket": ticket,
        "get_ticket": get_ticket,
        "rp_id": rp_id,
        "user_id": webauthn.b64url(pinstore.account_for(config.data_dir).encode()[:32]),
        "user_name": user.username or "Tessellate",
        "create_challenge": webauthn.b64url(challenge),
        "get_challenge": webauthn.b64url(get_challenge),
        "prf_salt": webauthn.b64url(salt),
    }


def _decode(text: str) -> bytes:
    try:
        return webauthn.unb64url(text)
    except webauthn.WebAuthnError:
        raise HTTPException(status_code=400, detail="That Windows Hello answer could not be read.") from None


@router.post("/enrol/finish", dependencies=[Depends(routes_auth.require_unlock), Depends(this_computer_only)])
def enrol_finish(
    body: EnrolIn,
    request: Request,
    session: Session = Depends(get_session),
    config: ConfigManager = Depends(get_config),
) -> dict:
    _here(request)
    rp_id, origin = _rp_id(request), _origin(request)
    taken = hellostore.take(body.ticket, "enrol")
    if taken is None:
        raise HTTPException(status_code=409, detail="That took too long. Turn Windows Hello on again.")
    challenge, extra = taken
    get_taken = hellostore.take(extra["get"], "enrol-get")
    user = routes_auth._get_user(session)
    dek = vault.key()
    bound = routes_auth._pin_binding(session, user) if user else None
    if dek is None or bound is None:
        raise HTTPException(status_code=409, detail="Unlock your private notes before turning on Windows Hello.")
    cred_id = _decode(body.credential_id)
    prf = _decode(body.prf)
    try:
        made = webauthn.verify_registration(
            client_data_json=_decode(body.client_data_json),
            attestation_object=_decode(body.attestation_object),
            credential_id=cred_id, challenge=challenge, origin=origin, rp_id=rp_id,
        )
        count = made.sign_count
        if body.assertion is not None:
            if get_taken is None or not secrets.compare_digest(_decode(body.assertion.credential_id), cred_id):
                raise webauthn.WebAuthnError("first assertion is not for this credential")
            count = webauthn.verify_assertion(
                client_data_json=_decode(body.assertion.client_data_json),
                authenticator_data=_decode(body.assertion.authenticator_data),
                signature=_decode(body.assertion.signature),
                challenge=get_taken[0], origin=origin, rp_id=rp_id,
                alg=made.alg, spki=made.spki, sign_count=made.sign_count,
            )
        if len(prf) != hellostore.PRF_BYTES:
            raise webauthn.WebAuthnError("no PRF output")
    except webauthn.WebAuthnError as exc:
        log.info("Windows Hello enrolment refused: %s", exc)
        raise HTTPException(status_code=400, detail="Windows Hello did not confirm it. Try again.") from None
    try:
        hellostore.save(
            config.data_dir, credential_id=cred_id, rp_id=rp_id, alg=made.alg, spki=made.spki,
            sign_count=count, prf_salt=extra["salt"], prf=prf, dek=dek, bound_to=bound,
        )
    except pinstore.StoreError:
        raise HTTPException(
            status_code=409,
            detail="This computer's protected store did not keep Windows Hello. The password still works.",
        ) from None
    log_action(session, "edited", "user", user.id, "Windows Hello unlock set up on this computer")
    session.commit()
    return {"set": True}


@router.post("/forget", dependencies=[Depends(routes_auth.require_unlock), Depends(this_computer_only)])
def forget(
    request: Request,
    session: Session = Depends(get_session),
    config: ConfigManager = Depends(get_config),
) -> dict:
    """Settings, the switch off. Removing a way in needs no password."""
    _here(request)
    forgotten = hellostore.forget(config.data_dir)
    user = routes_auth._get_user(session)
    if forgotten and user is not None:
        log_action(session, "edited", "user", user.id, "Windows Hello unlock removed from this computer")
        session.commit()
    return {"forgotten": forgotten}


@router.post("/begin")
def begin(request: Request, config: ConfigManager = Depends(get_config)) -> dict:
    """A challenge for the stored credential: the lock screen and the private
    spaces both start here. Open, like the lock screen, but this computer only."""
    _here(request)
    client = routes_auth._client_key(request)
    routes_auth._refuse_if_throttled(client)
    # Only a check: a challenge is no guess, so the attempt the throttle just
    # opened is answered at once, and pressing the button never locks out
    # the password (the assertion route counts the real attempt).
    with routes_auth._throttle_lock:
        routes_auth._answered(routes_auth._bucket(client))
    made = hellostore.record(config.data_dir)
    if made is None or made.get("rp") != _rp_id(request):
        raise HTTPException(status_code=404, detail="Windows Hello is not set up here. Use your password.")
    ticket, challenge = hellostore.issue("get")
    return {
        "ticket": ticket,
        "rp_id": made["rp"],
        "challenge": webauthn.b64url(challenge),
        "credential_id": webauthn.b64url(_b64std(made["cred"])),
        "prf_salt": webauthn.b64url(_b64std(made["salt"])),
    }


def _b64std(text: str) -> bytes:
    return base64.b64decode(text)


def dek_from_assertion(request: Request, session: Session, user: User, body: AssertionIn, config: ConfigManager) -> bytes:
    """The data key a verified assertion unwraps; 401 after counting the failure.

    The order is the guarantee: this computer, the throttle, a live single-use
    challenge, the stored credential, the signature, and only then the unwrap.
    """
    _here(request)
    client = routes_auth._client_key(request)
    routes_auth._refuse_if_throttled(client)
    taken = hellostore.take(body.ticket, "get")
    made = hellostore.record(config.data_dir)
    bound = routes_auth._pin_binding(session, user)
    dek = None
    try:
        if taken is None or made is None or bound is None:
            raise webauthn.WebAuthnError("no live challenge or no record")
        rp_id = _rp_id(request)
        if made.get("rp") != rp_id:
            raise webauthn.WebAuthnError("record is for another host name")
        if not secrets.compare_digest(_decode(body.credential_id), _b64std(made["cred"])):
            raise webauthn.WebAuthnError("another credential")
        count = webauthn.verify_assertion(
            client_data_json=_decode(body.client_data_json),
            authenticator_data=_decode(body.authenticator_data),
            signature=_decode(body.signature),
            challenge=taken[0], origin=_origin(request), rp_id=rp_id,
            alg=int(made["alg"]), spki=_b64std(made["spki"]), sign_count=int(made.get("count", 0)),
        )
        dek = hellostore.unwrap(config.data_dir, made, _decode(body.prf), bound)
        if dek is None:
            raise webauthn.WebAuthnError("the PRF output or the binding is wrong")
    except (webauthn.WebAuthnError, HTTPException, KeyError, ValueError) as exc:
        log.info("Windows Hello unlock refused: %s", getattr(exc, "detail", exc))
        routes_auth._unlock_failed(client)
        raise HTTPException(status_code=401, detail=NOT_UNLOCKED) from None
    hellostore.note_sign_count(config.data_dir, count)
    routes_auth._unlock_succeeded(client)
    return dek


@router.post("/unlock")
def unlock(
    body: AssertionIn,
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
    config: ConfigManager = Depends(get_config),
) -> dict:
    """The lock screen's Windows Hello button: the whole notebook."""
    user = routes_auth._get_user(session)
    if user is None:
        raise HTTPException(status_code=400, detail="No password is set yet. Set one up first.")
    dek = dek_from_assertion(request, session, user, body, config)
    return routes_auth._finish_unlock(request, response, session, config, user, None, dek)
