"""The server-mode process used to sit for 5 to 9 seconds after uvicorn had
already logged "Finished server process" (INBOX 423i).

**The thread.** Almost every route in this app is a plain `def`, not an
`async def`, so Starlette runs each one through `anyio.to_thread.run_sync`,
which is backed by a small pool of "AnyIO worker thread" objects. Each one is
supposed to stop itself once the server's own root asyncio task finishes, but
that stop is scheduled as a callback for the event loop's *next* iteration,
and `uvicorn.run()` can tear the loop down before that iteration happens. A
worker left over that way is not a daemon thread, so Python's own interpreter
shutdown, which joins every non-daemon thread with no timeout before the
process can exit, sits waiting on it.

Measured directly (`scratchpad/` is not the place for a one-off repro, so the
numbers are recorded here instead): a real `uvicorn.Server` handling one sync
request and then shutting down consistently leaves an "AnyIO worker thread"
alive and `daemon=False` at the moment `Server.run()` returns, and Python's
own process took an extra 1.8 to 4.6 seconds to actually disappear because of
it, on top of whatever else interpreter teardown costs on this machine. The
worst case is unbounded: nothing tells that thread to stop, so how long it
survives is a race with anyio's own `MAX_IDLE_TIME` (10 seconds), not a
guarantee.

`_stop_lingering_worker_threads` (`__main__.py`, called right after
`uvicorn.run()` returns in `_run_server`) asks any thread of exactly that
class to stop, the same way anyio's own done-callback would have, and bounds
the wait rather than trusting it to be instant. This test reproduces the
leftover thread with a real `uvicorn.Server` running this app's own
`create_app()` and checks the fix actually clears it inside the 1 second
budget. A bare FastAPI app with one throwaway route did not reproduce this
reliably: the leftover thread comes from a race (anyio's done-callback for
the *next* event loop iteration against `uvicorn.run()` tearing the loop
down), and it is this app's own startup work, the embeddings warmup thread,
the autonomous scheduler, that is enough concurrent activity to make that
race land the same way it does for a real launch.
"""

from __future__ import annotations

import socket
import threading
import time

import pytest

from tessellate.__main__ import _stop_lingering_worker_threads


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _anyio_worker_threads() -> list[threading.Thread]:
    return [
        thread
        for thread in threading.enumerate()
        if type(thread).__module__ == "anyio._backends._asyncio"
        and type(thread).__name__ == "WorkerThread"
    ]


def _serve_one_sync_request_then_shut_down(app) -> None:
    """Runs `app` through a real `uvicorn.Server`: one request against a
    plain `def` route (`/health`, this app's own, not a stand-in), then shut
    down exactly as Ctrl+C would ask for (`should_exit`, not `os.kill`, so
    this has no signal-handling side effects the rest of the suite could
    see). Returns once `Server.run()` itself has returned, i.e. the exact
    moment `_run_server` calls `_stop_lingering_worker_threads`.

    **The real app, not a minimal stand-in.** A bare FastAPI app with one
    route did not reproduce this reliably in trial runs: the leftover thread
    comes from a race (anyio's done-callback for the *next* event loop
    iteration against `uvicorn.run()` tearing the loop down), and this app's
    own startup work (the embeddings warmup thread, the autonomous scheduler)
    is enough concurrent activity to make that race land the same way it
    does for a real launch. A smaller repro is a different, easier race.
    """
    import uvicorn

    port = _free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)

    def hit_then_stop() -> None:
        import urllib.request

        for _ in range(200):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1)
                break
            except OSError:  # not listening yet (URLError is an OSError)
                time.sleep(0.05)
        time.sleep(0.3)
        server.should_exit = True

    threading.Thread(target=hit_then_stop, daemon=True).start()
    server.run()


#: **What this race actually is.** anyio schedules a worker's own cleanup as
#: a callback for the event loop's *next* iteration
#: (`root_task.add_done_callback`), and whether `uvicorn.run()` tears the
#: loop down before that iteration runs depends on exact scheduling, not on
#: anything this test controls. It used to be asserted here that a real
#: server reproduces it within eight attempts; on CI (2026-09-24, a docs-only
#: commit) it did not, because the odds move with how much else the app does
#: at startup. So the real server is still run, and any leftover it does
#: produce is still checked, but the fix is proven against a leftover built
#: directly (`_leftover_worker`): the exact state the race leaves, an alive
#: non-daemon `WorkerThread` whose event loop is already closed and whose
#: done-callback never ran. That half is deterministic.
_REPRODUCE_ATTEMPTS = 3


def _leftover_worker() -> threading.Thread:
    """An anyio `WorkerThread` in the state the race leaves behind: started,
    waiting on its queue, `daemon=False`, its loop closed before anything told
    it to stop. Built from anyio's own class so the fix is exercised against
    the real type and its real `stop()`, not a stand-in."""
    import asyncio
    from collections import deque

    from anyio._backends._asyncio import WorkerThread

    #: Built inside a running loop (its constructor reads the loop's clock),
    #: then the loop is closed with nothing ever calling `stop()`.
    async def build() -> threading.Thread:
        worker = WorkerThread(asyncio.current_task(), set(), deque())
        worker.start()
        return worker

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(build())
    finally:
        loop.close()


@pytest.fixture()
def joins_offered(monkeypatch):
    """Every `Thread.join` timeout asked for while the fixture is live (L-general-70):
    a shutdown's budget is the waits it allows itself, not a loaded runner's clock."""
    import threading

    offered: list = []
    real = threading.Thread.join

    def join(self, timeout=None):  # noqa: ANN001, ANN202
        offered.append(timeout)
        return real(self, timeout)

    monkeypatch.setattr(threading.Thread, "join", join)
    return offered


def test_a_leftover_non_daemon_worker_thread_is_cleared_by_the_fix(app_state, joins_offered) -> None:
    """The fix, proven against a leftover worker: first any the real server
    left (the race, when it lands), then one built in exactly that state, so
    the proof never depends on scheduling luck. If this fails,
    `_stop_lingering_worker_threads` (called from `_run_server`) has become a
    no-op, not a broken test."""
    from tessellate.api.app import create_app

    for _ in range(_REPRODUCE_ATTEMPTS):
        before = _anyio_worker_threads()
        _serve_one_sync_request_then_shut_down(create_app())
        if [t for t in _anyio_worker_threads() if t not in before]:
            break

    worker = _leftover_worker()
    assert worker.is_alive() and not worker.daemon, "the built leftover should match the race's state"

    before = len(joins_offered)
    _stop_lingering_worker_threads(timeout=1.0)
    offered = joins_offered[before:]

    # The waits it allowed itself, not the runner's clock (L-general-70).
    # One deadline shared by every join: each wait is what is left of it, so none
    # passes the budget and each is no longer than the one before.
    assert offered and None not in offered and max(offered) <= 1.0, offered
    assert offered == sorted(offered, reverse=True), offered
    assert not _anyio_worker_threads(), "a worker thread is still alive after being asked to stop"


def test_stop_lingering_worker_threads_is_a_quiet_no_op_with_nothing_to_stop(joins_offered) -> None:
    """Called on every server-mode exit, whether or not any sync route was
    ever actually hit: must never raise or hang when there is nothing to do."""
    _stop_lingering_worker_threads(timeout=1.0)
    assert joins_offered == []  # nothing to stop, nothing waited on (L-general-70)


def test_only_the_named_anyio_class_is_touched() -> None:
    """A thread this function does not recognise must be left alone: calling
    an arbitrary object's `.stop()` because it happens to have one is how a
    shutdown handler breaks something it was never meant to touch."""

    class _NotAnyio(threading.Thread):
        def __init__(self) -> None:
            super().__init__(daemon=False, name="not-anyio")
            self.stopped = False
            self._ready = threading.Event()
            self._go = threading.Event()

        def stop(self) -> None:
            self.stopped = True
            self._go.set()

        def run(self) -> None:
            self._ready.set()
            self._go.wait(timeout=5)

    thread = _NotAnyio()
    thread.start()
    thread._ready.wait(timeout=5)
    try:
        _stop_lingering_worker_threads(timeout=0.2)
        assert not thread.stopped, "a thread outside anyio's own class must not be told to stop"
    finally:
        thread.stop()
        thread.join(timeout=5)
