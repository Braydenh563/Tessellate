"""Route wrappers for the chat sends: once per turn id (L682, E70) and a signed
tool call checked before it runs (L566). Kept out of `routes_chat.py`, which is at its line cap."""

from __future__ import annotations

import functools
import hashlib
import inspect
from collections.abc import Callable

from fastapi import HTTPException, Request
from starlette.responses import StreamingResponse

from tessellate.ai import consent_store, turn_once
from tessellate.core import private_turn

_NDJSON = "application/x-ndjson"
_REQ = "once_request"
_HEADERS = {"X-Accel-Buffering": "no", "Cache-Control": "no-cache"}


def _tracked(body: object) -> bool:
    """A send is deduplicated only when it has an id and is not a private or peek turn."""
    return (
        bool(getattr(body, "turn_id", None))
        and not getattr(body, "private", False)
        and not getattr(body, "peek", False)
    )


def _takes_request(handler: Callable, wrapped: Callable) -> Callable:
    """Add the request to the signature FastAPI reads, so the wrapper knows who sent the turn."""
    sig = inspect.signature(handler)
    extra = inspect.Parameter(_REQ, inspect.Parameter.KEYWORD_ONLY, annotation=Request)
    wrapped.__signature__ = sig.replace(parameters=[*sig.parameters.values(), extra])
    return wrapped


def _caller(request: Request) -> str:
    """One sign-in's slots are its own: two devices that pick the same turn id never share an answer.

    With no password there is no token, so every caller hashes the empty string and shares one
    key. That is intended: such a notebook has one person, and a repeat of a turn id from a second
    tab of theirs should get the first answer rather than run the turn twice."""
    token = request.headers.get("x-auth-token") or ""
    return hashlib.sha256(token.encode()).hexdigest()[:16]


def json_route(handler: Callable) -> Callable:
    """`POST /chat`: a repeat of the same `turn_id`, even while the first still runs, waits and gets its result."""

    @functools.wraps(handler)
    def wrapped(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        body = kwargs.get("body")
        request = kwargs.pop(_REQ)
        if not _tracked(body):
            return handler(*args, **kwargs)
        held = turn_once.slot(body.turn_id, _caller(request))
        with held.lock:
            if held.value is None:
                held.value = handler(*args, **kwargs)
            return held.value

    return private_turn.route(_takes_request(handler, wrapped))


async def _remember(held: turn_once.Slot, lines):  # noqa: ANN001, ANN202
    """The lines as they go out, kept when the stream ends whole."""
    got: list = []
    whole = False
    try:
        async for line in lines:
            got.append(line)
            yield line
        whole = True
    finally:
        turn_once.end_stream(held, got if whole else None, partial=bool(got) and not whole)


def stream_route(handler: Callable) -> Callable:
    """`POST /chat/stream`: the first run's lines again for a repeated `turn_id`; 409 while it is still running."""

    @functools.wraps(handler)
    def wrapped(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        body = kwargs.get("body")
        request = kwargs.pop(_REQ)
        if not _tracked(body):
            return handler(*args, **kwargs)
        held = turn_once.slot(body.turn_id, _caller(request))
        if held.partial:
            raise HTTPException(status_code=409, detail="That answer stopped partway, so it was not run again.")
        if held.value is not None:
            return StreamingResponse(iter(held.value), media_type=_NDJSON, headers=_HEADERS)
        if not turn_once.begin_stream(held):
            raise HTTPException(status_code=409, detail="That question is already being answered.")
        try:
            response = handler(*args, **kwargs)
        except BaseException:
            turn_once.end_stream(held, None)
            raise
        response.body_iterator = _remember(held, response.body_iterator)
        return response

    return private_turn.route(_takes_request(handler, wrapped))


def check_tag(body: object) -> None:
    """A tool call runs only as the server offered it: a card press is bound by its id (E43), anything
    else (an Undo, a redo) must carry the tag it was handed out with, unchanged (L566)."""
    #: An id alone counts only while its card is waiting (parked, not spent):
    #: a batch never reaches the card check, so a made-up id ran its steps.
    if not body.sig and not body.consent_id:
        raise HTTPException(
            status_code=400, detail="That action was not offered by this app, so it was not run."
        )
    if not body.sig and consent_store.peek(body.consent_id) is None:
        raise HTTPException(status_code=409, detail="That card is no longer waiting. Ask for it again.")
    if body.sig and not consent_store.tag_matches(body.name, body.arguments, body.steps, body.sig):
        raise HTTPException(
            status_code=400,
            detail="That action was changed after it was offered, so it was not run.",
        )
