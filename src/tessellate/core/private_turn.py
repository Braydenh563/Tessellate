"""Whether the turn running right now is a private chat (INBOX 1481, BACKLOG 1481).

A private chat answers from the notes and keeps nothing: no audit row, no
use count, no learned thing read or written, no question or tool argument in
the log or the process ledger. That used to be a `private` parameter handed
down every call, and each new write path that was not handed it leaked (a
skill run, a tool call's audit row, the narrator's log lines, the rows cache).

It is one fact now, set once where a turn starts (`scope`, `stepped`, `route`)
and read at the write itself, so a new write path asks the same question
instead of needing the flag passed to it. The reads are `events.record` (the
only writer of audit rows), `memory.persona_with_memory`, the tool that saves
a preference, the stream narrator, the rows cache and the question log.

A context variable, so it follows the request through the agent, skill and
plan code without a parameter. It does not follow a raw thread, so a worker
that must honour it is started with `contextvars.copy_context().run`.
"""

from __future__ import annotations

import contextlib
import functools
from collections.abc import Callable, Iterator
from contextvars import ContextVar

_private: ContextVar[bool] = ContextVar("tessellate_private_turn", default=False)


def active() -> bool:
    """True while a private chat's turn is running on this context."""
    return _private.get()


@contextlib.contextmanager
def scope(private: bool):
    """Mark everything inside the block as one private turn.

    Never clears an outer private scope: `scope(False)` inside `scope(True)`
    is still private, so a helper cannot un-private its caller."""
    if not private:
        yield
        return
    token = _private.set(True)
    try:
        yield
    finally:
        _private.reset(token)


def stepped(lines: Iterator, private: bool) -> Iterator:
    """`lines`, with the scope entered around each step.

    A streamed turn is advanced one `next()` at a time, each in a copy of the
    caller's context (Starlette's threadpool, `_stop_when_gone`), so a flag set
    once inside the generator is gone on the second step. Entering the scope
    around every step is what makes the turn private to its last line."""
    if not private:
        yield from lines
        return
    source = iter(lines)
    try:
        while True:
            with scope(True):
                try:
                    line = next(source)
                except StopIteration:
                    return
            yield line
    finally:
        close = getattr(source, "close", None)
        if close is not None:
            with scope(True):
                close()


def route(handler: Callable) -> Callable:
    """A chat endpoint whose request body carries `private`: the whole handler
    runs inside the scope. The body is read by name, as FastAPI passes it."""

    @functools.wraps(handler)
    def wrapped(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        body = kwargs.get("body")
        with scope(bool(getattr(body, "private", False))):
            return handler(*args, **kwargs)

    return wrapped
