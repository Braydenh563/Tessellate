"""Model-call tracing: every provider call lands in the process ledger
(INBOX 805, B77). Split from `jobruns` so that module stays under its size
cap; the thread's bound run and the request scope stay there, shared state
imported here rather than copied."""

from __future__ import annotations

import time
from contextlib import contextmanager

from tessellate.core.jobruns import Run, _bound, _clip, _request_scope, active, bound, failure_reason


def _purpose() -> str:
    """What the request is for, in words, from its endpoint's name."""
    scope = _request_scope.get()
    if not scope:
        return ""
    name = getattr(scope.get("endpoint"), "__name__", "") or ""
    if name:
        return name.replace("_", " ").strip().capitalize()
    path = str(scope.get("path") or "")
    return f"AI request for {path}" if path else ""


def _seconds(t0: float) -> str:
    took = time.monotonic() - t0
    if took < 1:
        return f"{max(1, round(took * 1000))} ms"
    return f"{took:.1f} s" if took < 60 else f"{int(took // 60)} min {int(took % 60)} s"


@contextmanager
def _calling():  # noqa: ANN202
    before = getattr(_bound, "calling", False)
    _bound.calling = True
    try:
        yield
    finally:
        _bound.calling = before


def _named(provider, model: str) -> str:  # noqa: ANN001
    """What a call is logged under. Needle ignores the configured chat model
    (it picks tools in process), so the ledger said "Asked <that model> with
    tools" for a call it never made (INBOX 1345 b)."""
    return "needle" if getattr(provider, "name", "") == "needle" else model


def _open_call(model: str, tools: bool) -> tuple["Run", "Run | None", str]:
    name = _clip(model) or "the model"
    parent = active()
    own = None
    if parent is None:
        scope = _request_scope.get()
        own = Run("ai-call", None, title=_purpose() or f"AI request to {name}", origin="you" if scope else "app", why="Your request needed the model." if scope else "")
        own.start()
    run = parent or own
    run.say(f"Asked {name}{' with tools' if tools else ''}.")
    return run, own, name


def model_call(method):  # noqa: ANN001, ANN201
    """Wrap a provider's `chat` or `chat_tools`: every model call is in the
    ledger. Inside a run (a pool job, a chat answer) it adds two timed lines
    to that run; outside one it is a run of its own, named for the request
    that made it, so no AI work happens unseen."""
    tools = "tools" in method.__name__

    def call(self, model, *args, **kwargs):  # noqa: ANN001, ANN202
        if getattr(_bound, "calling", False):
            return method(self, model, *args, **kwargs)
        run, own, name = _open_call(_named(self, model), tools)
        t0 = time.monotonic()
        try:
            with _calling(), bound(own or run):
                reply = method(self, model, *args, **kwargs)
        except BaseException as exc:
            run.say(f"{name} did not answer ({_seconds(t0)}).")
            if own is not None:
                own.fail(failure_reason(exc))
            raise
        else:
            run.say(f"{name} answered in {_seconds(t0)}.")
            if own is not None:
                own.result = f"answered in {_seconds(t0)}"
        finally:
            if own is not None:
                own.finish()
        return reply

    call.__name__ = method.__name__
    call.__qualname__ = getattr(method, "__qualname__", method.__name__)
    call.__doc__ = method.__doc__
    call.__wrapped__ = method
    call.ledgered = True
    return call


def model_stream(method):  # noqa: ANN001, ANN201
    """`model_call` for a streamed reply: the run opens at the first chunk
    and ends however the stream does (finished, closed by the reader, or
    raised), so nothing stays "running"."""
    tools = "tools" in method.__name__

    def stream(self, model, *args, **kwargs):  # noqa: ANN001, ANN202
        if getattr(_bound, "calling", False):
            yield from method(self, model, *args, **kwargs)
            return
        run, own, name = _open_call(_named(self, model), tools)
        t0 = time.monotonic()
        source = None
        try:
            with _calling():
                source = iter(method(self, model, *args, **kwargs))
            while True:
                with _calling(), bound(own or run):
                    try:
                        chunk = next(source)
                    except StopIteration:
                        break
                yield chunk
        except GeneratorExit:
            run.say(f"Stopped reading {name} after {_seconds(t0)}.")
            if own is not None:
                own.cancel("closed before it finished")
            raise
        except BaseException as exc:
            run.say(f"{name} did not answer ({_seconds(t0)}).")
            if own is not None:
                own.fail(failure_reason(exc))
            raise
        else:
            run.say(f"{name} answered in {_seconds(t0)}.")
            if own is not None:
                own.result = f"answered in {_seconds(t0)}"
        finally:
            close = getattr(source, "close", None)
            if close is not None:
                close()
            if own is not None:
                own.finish()

    stream.__name__ = method.__name__
    stream.__qualname__ = getattr(method, "__qualname__", method.__name__)
    stream.__doc__ = method.__doc__
    stream.__wrapped__ = method
    stream.ledgered = True
    return stream
