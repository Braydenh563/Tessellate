"""The server log viewer and the browser's own crash reports.

Split out of routes_settings.py (K24); mounted in app.py beside that module's router.
`open_router` carries the client-error sink, which has to work before unlock.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator

from fastapi import APIRouter, Query, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from tessellate.core import logbuffer

router = APIRouter(tags=["settings"])

#: Routes in this module that must work **before** the notebook is unlocked.
#: Included in `app.py` without the `locked` dependency, deliberately and
#: only for the client-error sink below, see its docstring.
open_router = APIRouter(tags=["settings"])


@router.get("/logs")
def server_logs(limit: int = Query(default=200, ge=1, le=logbuffer.MAX_RECORDS)) -> list[dict]:
    """Recent server-side log records for the Settings, Logs viewer."""
    return logbuffer.recent(limit=limit)


class ClientError(BaseModel):
    """One thing that went wrong in the browser, on its way to the terminal."""

    message: str = Field(max_length=2000)
    #: Where it happened, when the browser knows: "app.js:6088:12". Free text
    #: because a stack frame's shape differs per engine and none of it is
    #: parsed: it is read by a person.
    source: str = Field(default="", max_length=500)
    #: "error" | "unhandledrejection" | "csp", what kind of failure this was,
    #: since the three need different first questions asked about them.
    kind: str = Field(default="error", max_length=40)


#: Lines one client may log per minute (audit 1028 K10): open to the LAN in
#: LAN mode, so a flood must not push real warnings out of the ring buffer.
CLIENT_LOG_PER_MINUTE = 30
_client_log_times: dict[str, list[float]] = {}
_client_log_clock = time.monotonic


def _client_log_allowed(client: str) -> bool:
    now = _client_log_clock()
    recent = [t for t in _client_log_times.get(client, ()) if now - t < 60]
    if len(_client_log_times) > 256:
        _client_log_times.clear()
    allowed = len(recent) < CLIENT_LOG_PER_MINUTE
    _client_log_times[client] = recent + [now] if allowed else recent
    return allowed


@open_router.post("/logs/client", status_code=204)
def record_client_error(body: ClientError, request: Request, response: Response) -> None:
    """Put a browser-side failure into the same log everything else uses.

    Asked for directly: *"can you make any other erros like what aoppeared on
    the loading screen appear in the logs as well?? the terminal and logs need
    to capture everything."*

    The gap was real and had just cost a session. A JavaScript error aborts
    the rest of the file it is in, so the app can hang on its loading screen
    with **nothing** in the terminal, nothing in Settings, Logs, and the only
    record sitting in a browser console nobody opens, least of all in the
    desktop shell, which has no obvious way to open one. The crash that
    prompted this (`Cannot access 'captureStagedFiles' before initialization`)
    was invisible to every log this app keeps.

    Deliberately `logger.error`, not a new channel: `logbuffer`'s handler is
    already attached to the root logger, so this reaches the terminal, the
    Settings, Logs viewer and `/logs/stream` at once, with no new plumbing to
    keep in step. The `[browser]` prefix is what tells a reader the failure
    happened on the other side of the wire, which changes what they should
    look at next.

    **On `open_router`, outside the unlock gate, on purpose.** This has to
    work *before* unlock: the loading-screen hang it exists for happens with
    the lock overlay still up, and a crash report that needs a token cannot
    describe the failure that stopped the token from ever being used. Every
    other route in this module stays behind `locked`.

    What it accepts is bounded instead of authenticated: three short strings,
    length-capped by the schema, appended to a ring buffer that already caps
    itself at `MAX_RECORDS`, reachable only from an origin the CSP pins to
    `'self'`, and rate-limited per client (LAN mode reaches it too). The worst an abuser of it
    can do is push older lines out of a 500-record buffer on their own
    machine.
    """
    # **Through `safe_value`, not raw.** Everything in this payload is
    # attacker-shaped by construction: it is text the browser was handed by
    # whatever failed, and a message containing a newline would draw a forged
    # second row in the Settings, Logs viewer while control characters can
    # rewrite what a terminal shows. `logbuffer.sanitise` runs at the ring
    # buffer and so protects the viewer only; the terminal sees the raw
    # record, which is exactly why this module's own helper exists and says
    # to clean at the call site.
    response.status_code = 204
    if not _client_log_allowed(request.client.host if request.client else ""):
        return
    logger = logging.getLogger("tessellate.browser")
    kind = logbuffer.safe_value(body.kind, limit=40)
    message = logbuffer.safe_value(body.message, limit=logbuffer.MAX_MESSAGE_CHARS)
    where = f" ({logbuffer.safe_value(body.source, limit=200)})" if body.source else ""
    logger.error("[browser/%s] %s%s", kind, message, where)
    response.status_code = 204


@router.get("/logs/stats")
def server_log_stats(
    limit: int = Query(default=200, ge=1, le=logbuffer.MAX_RECORDS),
) -> dict:
    """How complete the log above actually is.

    A separate call rather than a wrapper around the records, so the shape of
    /logs stays a plain list for everything already reading it.
    """
    return logbuffer.stats(limit=limit)


@router.delete("/logs")
def clear_server_logs() -> dict:
    logbuffer.clear()
    return {"cleared": True}


# How long a single stream lives before it hands over to the browser's own
# reconnect, and how often it looks for new records. The cap is not a
# limitation to work around, EventSource reconnects on its own and resends
# Last-Event-ID, so the handover is seamless, and a stream that lives forever
# is a resource nothing ever reclaims when a tab stays up for a week.
LOG_STREAM_SECONDS = 10 * 60
LOG_STREAM_POLL = 0.7
LOG_STREAM_HEARTBEAT = 15


@router.get("/logs/stream")
async def stream_server_logs(request: Request, after: int = 0) -> StreamingResponse:
    """A live log feed, so the Logs screen reads like a terminal.

    Asked for directly: the screen should behave "like the terminal running in
    the background", not a list you refresh by hand.

    **NDJSON over fetch rather than the EventSource the roadmap suggested.**
    EventSource cannot set request headers, and this app authenticates with
    `X-Auth-Token`, so an EventSource here would simply 401. The usual way
    round that is to put the token in the query string, which is a bad trade
    anywhere and a farcical one on the endpoint that serves the log: the token
    would be written into the very records it is protecting. `fetch` carries
    the header, and NDJSON matches the chat and digest streams the app already
    has, so the browser-side reader is the one that already exists.

    Polling the ring buffer rather than registering a subscriber on it. That
    sounds like the lazier choice and is the more robust one: a subscriber
    registry means the logging handler pushes into per-connection queues, so a
    slow or dead reader can block or grow unboundedly *inside logging itself*, 
    and a logging path that can stall is a far worse failure than a console
    running 700ms behind. One reader, one process, one deque.
    """

    async def lines() -> AsyncIterator[str]:
        cursor = after
        loop = asyncio.get_running_loop()
        started = loop.time()
        last_sent = started
        # An immediate first line, so the reader knows the stream is live
        # before anything has been logged, and learns where it is starting
        # from, which is what makes "dropped" meaningful on the client.
        yield json.dumps(
            {"type": "open", "cursor": cursor, "latest": logbuffer.latest_seq()}
        ) + "\n"
        while True:
            if await request.is_disconnected():
                return
            now = loop.time()
            # Drain BEFORE checking the deadline. The other order loses every
            # record that arrived in the last poll interval of the connection:
            # the client reconnects from its cursor and those records are
            # inside the buffer but behind it, so they are never sent at all.
            for record in logbuffer.since(cursor):
                cursor = record.get("seq", cursor)
                yield json.dumps({"type": "record", "record": record}) + "\n"
                last_sent = now
            if now - started > LOG_STREAM_SECONDS:
                # Hand back to the client's own reconnect rather than holding a
                # connection open forever for a tab that stays up all week.
                yield json.dumps({"type": "reconnect", "cursor": cursor}) + "\n"
                return
            if now - last_sent > LOG_STREAM_HEARTBEAT:
                # Keeps the connection from being reaped as idle, and doubles
                # as the client's proof that the server is still there rather
                # than merely quiet.
                yield json.dumps({"type": "ping", "cursor": cursor}) + "\n"
                last_sent = now
            await asyncio.sleep(LOG_STREAM_POLL)

    return StreamingResponse(
        lines(),
        media_type="application/x-ndjson",
        headers={
            # Same reasoning as the chat stream: stop a reverse proxy buffering
            # a stream whose whole value is arriving promptly.
            "X-Accel-Buffering": "no",
            "Cache-Control": "no-cache",
        },
    )
