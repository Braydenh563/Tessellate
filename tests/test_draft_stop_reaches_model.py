"""L889: Stop in the writing room reaches the model.

The browser's Stop only aborted the HTTP response. The route kept reading the
model's stream to the end (measured with a delayed OpenAI-compatible backend:
a Stop 1 s and 6 s in left the backend generating for 15.7 s), the same gap
audit 1028 E3 closed for chat. A cancelled body now sets the pass's stop flag,
which cuts the upstream request (`activity.stop_aware`) and closes the stream.
"""

from __future__ import annotations

import asyncio
import gc
import threading

from tessellate.api import routes_drafts
from tessellate.core import activity


class _SlowModel:
    """Streams a word every `pause` seconds until it is cut; records how it ended."""

    def __init__(self, pause: float = 0.01) -> None:
        self.closed = threading.Event()
        self.chunks = 0
        self.pause = pause

    def is_running(self) -> bool:
        return True

    def chat_stream(self, model, messages, **kwargs):  # noqa: ANN001, ANN201
        import time

        try:
            for i in range(500):
                self.chunks += 1
                yield {"content_delta": f"w{i} "}
                time.sleep(self.pause)
        finally:
            self.closed.set()


def _stream(monkeypatch, model):  # noqa: ANN001, ANN202
    monkeypatch.setattr(routes_drafts.deps, "get_ollama", lambda: model)
    monkeypatch.setattr(
        routes_drafts.deps, "get_model_manager",
        type("M", (), {"for_feature": lambda self, f: self, "chat_model": lambda self: "m"}),  # the class: calling it makes the manager
    )
    response = routes_drafts.compose_draft_stream(routes_drafts.ComposeBody(thoughts="bread"), session=None)
    #: Measured with a bare Starlette 1.10 + uvicorn 0.54 app: a sync generator body is never
    #: closed when the client goes (30 s later still suspended), an async generator's `finally`
    #: runs within a second. Only the async wrapper reaches the model.
    assert response.body_iterator.ag_code.co_name == "stop_when_gone"
    return response.body_iterator.__aiter__()


async def _until_closed(model) -> None:  # noqa: ANN001
    for _ in range(40):
        if model.closed.is_set():
            return
        await asyncio.sleep(0.05)


def _run(go) -> None:  # noqa: ANN001
    #: The server's generators sit in reference cycles (the job, its hooks), which only the
    #: cyclic collector frees, minutes later; the test must not lean on it. Nor on the loop's
    #: shutdown, which closes every async generator left: each test checks inside the loop.
    gc.disable()
    try:
        asyncio.run(go())
    finally:
        gc.enable()


def _ended(model, seen) -> None:  # noqa: ANN001
    assert seen["closed"], "the model's stream was left running after Stop"
    assert model.chunks < 100, f"the model wrote {model.chunks} pieces after Stop"
    assert not [j for j in activity.snapshot() if j.get("label") == "Drafting"]


def test_a_stop_while_the_model_is_writing_stops_it(monkeypatch):
    """The cancel lands while a step waits on the model in the worker thread."""
    model = _SlowModel(pause=0.3)
    seen = {}

    async def go() -> None:
        agen = _stream(monkeypatch, model)
        await agen.__anext__()
        task = asyncio.ensure_future(agen.__anext__())
        await asyncio.sleep(0.05)
        assert not task.done(), "the step must still be waiting on the model"
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass  # the cancel is the point
        await _until_closed(model)
        seen["closed"] = model.closed.is_set()

    _run(go)
    _ended(model, seen)


def test_a_stream_dropped_between_lines_stops_the_model(monkeypatch):
    """The cancel lands in the server's own send: Starlette 1.10 drops the body without aclose,
    so the stream is finalized at `yield`, between two of the model's lines (leg 1 on 38c73e48d:
    the model kept writing until the loop shut down)."""
    model = _SlowModel()
    seen = {}

    async def go() -> None:
        agen = _stream(monkeypatch, model)
        await agen.__anext__()
        #: In the server the job and its hooks hold the sync stream in a cycle, so dropping the
        #: body does not free it by refcount; hold it here the same way.
        seen["held"] = agen.ag_frame.f_locals["source"]
        del agen
        await _until_closed(model)
        seen["closed"] = model.closed.is_set()

    _run(go)
    _ended(model, seen)
