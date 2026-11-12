"""Route wrappers for the chat sends: once per turn id (L682, E70) and a signed
tool call checked before it runs (L566). Kept out of `routes_chat.py`, which is at its line cap."""

from __future__ import annotations

import functools
from collections.abc import Callable

from fastapi import HTTPException
from starlette.responses import StreamingResponse

from tessellate.ai import consent_store, turn_once
from tessellate.core import private_turn

_NDJSON = "application/x-ndjson"
_HEADERS = {"X-Accel-Buffering": "no", "Cache-Control": "no-cache"}


def _tracked(body: object) -> bool:
    """A send is deduplicated only when it has an id and is not a private or peek turn."""
    return (
        bool(getattr(body, "turn_id", None))
        and not getattr(body, "private", False)
        and not getattr(body, "peek", False)
    )


def json_route(handler: Callable) -> Callable:
    """`POST /chat`: a repeat of the same `turn_id`, even while the first still runs, waits and gets its result."""

    @functools.wraps(handler)
    def wrapped(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        body = kwargs.get("body")
        if not _tracked(body):
            return handler(*args, **kwargs)
        held = turn_once.slot(body.turn_id)
        with held.lock:
            if held.value is None:
                held.value = handler(*args, **kwargs)
            return held.value

    return private_turn.route(wrapped)


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
        turn_once.end_stream(held, got if whole else None)


def stream_route(handler: Callable) -> Callable:
    """`POST /chat/stream`: the first run's lines again for a repeated `turn_id`; 409 while it is still running."""

    @functools.wraps(handler)
    def wrapped(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        body = kwargs.get("body")
        if not _tracked(body):
            return handler(*args, **kwargs)
        held = turn_once.slot(body.turn_id)
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

    return private_turn.route(wrapped)


def check_tag(body: object) -> None:
    """A tool call runs only as the server offered it: a card press is bound by its id (E43), anything
    else (an Undo, a redo) must carry the tag it was handed out with, unchanged (L566)."""
    if not body.sig and not body.consent_id:
        raise HTTPException(
            status_code=400, detail="That action was not offered by this app, so it was not run."
        )
    if body.sig and not consent_store.tag_matches(body.name, body.arguments, body.steps, body.sig):
        raise HTTPException(
            status_code=400,
            detail="That action was changed after it was offered, so it was not run.",
        )
