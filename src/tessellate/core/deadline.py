"""No route waits on the model for ever (audit 1029 H3, H4).

One table of deadlines for the routes that ask the model for a small job.
`guard` is a dependency on every unlocked router: for a route in the table it
binds a stop flag that fires when the deadline passes or the browser goes
away. The provider calls (`ai/provider_http.py`) read that flag, cut their
connection to the model the moment it fires and fail like any other model
failure, so each route's own notes-only fallback runs; a route with none
answers 504 (`api/app.py`). A route not in the table is not touched: chat,
imports and pulls legitimately run long.
"""

from __future__ import annotations

import asyncio
import contextvars
import logging
import threading

from fastapi import Request

from tessellate.core.activity import StopEvent

#: Seconds, by (method, route template). A title or a tag list is short work;
#: a digest or a summary reads more, so it gets longer. Add a route here, not
#: a number in the route.
DEADLINES: dict[tuple[str, str], float] = {
    ("POST", "/drafts/title"): 15.0,
    ("POST", "/entries/suggest-tags"): 15.0,
    ("POST", "/entries/{entry_id}/reevaluate"): 30.0,
    ("POST", "/chat/followups"): 15.0,
    ("POST", "/voice/summarize"): 30.0,
    ("POST", "/help/ask"): 30.0,
    ("POST", "/insights/digest"): 30.0,
    #: Decorations: a banner or a note beside a pair never waits for a model.
    ("GET", "/insights/greeting"): 4.0,
    ("GET", "/entries/tensions"): 10.0,
}

#: How often a waiting route looks for a browser that has gone.
WATCH_SECONDS = 0.5

_current: contextvars.ContextVar[StopEvent | None] = contextvars.ContextVar("model_deadline", default=None)
_log = logging.getLogger("tessellate.deadline")


def current() -> StopEvent | None:
    """The flag for the route this thread is serving, or None outside one."""
    return _current.get()


def seconds_for(method: str, template: str) -> float | None:
    return DEADLINES.get((method.upper(), template))


async def _watch(request: Request, event: StopEvent) -> None:
    while not event.is_set():
        await asyncio.sleep(WATCH_SECONDS)
        if await request.is_disconnected():
            event.set()


async def guard(request: Request):  # noqa: ANN201
    route = request.scope.get("route")
    seconds = seconds_for(request.method, getattr(route, "path", ""))
    if seconds is None:
        yield
        return
    event = StopEvent()

    def expire() -> None:
        request.state.deadline_expired = True
        _log.info("%s %s passed its %s s deadline", request.method, request.url.path, seconds)
        event.set()

    timer = threading.Timer(seconds, expire)
    timer.daemon = True
    timer.start()
    watcher = asyncio.ensure_future(_watch(request, event))
    _current.set(event)
    try:
        yield
    finally:
        timer.cancel()
        watcher.cancel()
