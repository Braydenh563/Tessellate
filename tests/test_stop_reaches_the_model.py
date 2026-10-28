"""Stop in the browser stops the model too (audit 1028 E3).

The abort used to close only the HTTP response to the page: the stream to the
model was read to its end. A closed browser now sets the turn's stop flag, and
the provider's stream is cut between chunks and while it waits for the first.
"""

from __future__ import annotations

import asyncio
import threading
import time

from tessellate.api import routes_chat
from tessellate.core import activity


class _FakeResponse:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


def _chunks(response: _FakeResponse, seen: list[int]):
    for i in range(1000):
        if response.closed:
            return
        seen.append(i)
        yield f"chunk{i}"


def test_a_stop_flag_ends_the_upstream_read_within_one_chunk():
    event = activity.StopEvent()
    job = activity.Job("generation", "t", None, True, None, event)
    response, seen = _FakeResponse(), []
    out = []
    with activity.bind(job):
        for line in activity.stop_aware(response, _chunks(response, seen)):
            out.append(line)
            if len(out) == 3:
                event.set()
    assert out == ["chunk0", "chunk1", "chunk2"]
    assert len(seen) <= 4  # at most one more chunk was pulled after the flag
    assert response.closed


def test_a_stop_while_waiting_for_the_first_chunk_closes_the_response():
    event = activity.StopEvent()
    job = activity.Job("generation", "t", None, True, None, event)
    response = _FakeResponse()

    def blocked():  # a read waiting on prefill: only the close can end it
        while not response.closed:
            time.sleep(0.005)
        raise OSError("closed under a read")
        yield  # pragma: no cover

    def run() -> None:
        with activity.bind(job):
            list(activity.stop_aware(response, blocked()))

    worker = threading.Thread(target=run)
    worker.start()
    time.sleep(0.05)
    event.set()
    worker.join(2)
    assert not worker.is_alive() and response.closed


def test_a_cancelled_stream_sets_the_stop_flag_and_closes_the_generator():
    closed = threading.Event()

    def lines():
        try:
            yield "first\n"
            time.sleep(0.3)
            yield "second\n"
        finally:
            closed.set()

    class Req:
        stop = activity.StopEvent()

    async def go() -> None:
        agen = routes_chat._stop_when_gone(Req, lines())
        assert await agen.__anext__() == "first\n"
        task = asyncio.ensure_future(agen.__anext__())
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        assert Req.stop.is_set()
        await asyncio.sleep(0.5)

    asyncio.run(go())
    assert closed.is_set()
