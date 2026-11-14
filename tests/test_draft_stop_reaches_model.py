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
    """Streams a word every 10 ms until it is cut; records how it ended."""

    def __init__(self) -> None:
        self.closed = threading.Event()
        self.chunks = 0

    def is_running(self) -> bool:
        return True

    def chat_stream(self, model, messages, **kwargs):  # noqa: ANN001, ANN201
        import time

        try:
            for i in range(500):
                self.chunks += 1
                yield {"content_delta": f"w{i} "}
                time.sleep(0.01)
        finally:
            self.closed.set()


def test_a_cancelled_draft_stream_stops_the_model(monkeypatch):
    model = _SlowModel()
    monkeypatch.setattr(routes_drafts.deps, "get_ollama", lambda: model)
    monkeypatch.setattr(
        routes_drafts.deps, "get_model_manager",
        lambda: type("M", (), {"for_feature": lambda self, f: self, "chat_model": lambda self: "m"})(),
    )
    body = routes_drafts.ComposeBody(thoughts="bread")

    async def go() -> None:
        response = routes_drafts.compose_draft_stream(body, session=None)
        #: Measured with a bare Starlette 1.10 + uvicorn 0.54 app: a sync generator body is never
        #: closed when the client goes (30 s later still suspended), an async generator's `finally`
        #: runs within a second. Only the async wrapper reaches the model.
        assert response.body_iterator.ag_code.co_name == "stop_when_gone"
        agen = response.body_iterator.__aiter__()
        await agen.__anext__()
        task = asyncio.ensure_future(agen.__anext__())
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass  # the cancel is the point
        await asyncio.sleep(0.5)

    #: The server's generators sit in reference cycles (the job, its hooks), which only the
    #: cyclic collector frees, minutes later; the test must not lean on it.
    gc.disable()
    try:
        asyncio.run(go())
    finally:
        gc.enable()
    assert model.closed.is_set(), "the model's stream was left running after Stop"
    assert model.chunks < 100, f"the model wrote {model.chunks} pieces after Stop"
    assert not [j for j in activity.snapshot() if j.get("label") == "Drafting"]
