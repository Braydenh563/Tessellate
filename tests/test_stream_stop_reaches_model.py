"""L-documents-96: every model-backed streaming route stops the model when the client goes.

L889 fixed the drafts and the Guide; the document check and the weekly digest were still sync
generators, which Starlette 1.10 never closes on disconnect (the model kept writing to the end).
One test per route, in the style of `test_draft_stop_reaches_model.py`: a slow stub backend,
cancel the body after the first line, and the stub's stream must be closed well before its end.
"""

from __future__ import annotations

import asyncio
import gc
import threading
import time
from types import SimpleNamespace

from tessellate.api import routes_documents, routes_insights
from tessellate.core import activity


class _SlowModel:
    #: What each piece carries; the document check sends thinking pieces, which it relays as events.
    piece = "content_delta"

    def __init__(self) -> None:
        self.closed = threading.Event()
        self.chunks = 0

    def is_running(self) -> bool:
        return True

    def chat_stream(self, model, messages, **kwargs):  # noqa: ANN001, ANN201
        try:
            for i in range(500):
                self.chunks += 1
                yield {self.piece: f"w{i} "}
                time.sleep(0.01)
        finally:
            self.closed.set()


_MANAGER = type("M", (), {
    "for_feature": lambda self, f: self,
    "chat_model": lambda self: "m",
    "utility_model": lambda self: "m",
})()


def _cancel_after_first(response) -> None:  # noqa: ANN001
    async def go() -> None:
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

    gc.disable()  # the server's generators sit in cycles only the collector frees
    try:
        asyncio.run(go())
    finally:
        gc.enable()


def _assert_stopped(model: _SlowModel, label: str) -> None:
    assert model.closed.is_set(), "the model's stream was left running after Stop"
    assert model.chunks < 100, f"the model wrote {model.chunks} pieces after Stop"
    assert not [j for j in activity.snapshot() if j.get("label") == label]


def test_a_cancelled_document_check_stops_the_model(monkeypatch):
    model = _SlowModel()
    model.piece = "thinking_delta"
    monkeypatch.setattr(routes_documents.deps, "get_ollama", lambda: model)
    monkeypatch.setattr(routes_documents.deps, "get_model_manager", lambda: _MANAGER)
    monkeypatch.setattr(routes_documents, "_existing", lambda session, i: SimpleNamespace(content="Some text to check."))
    response = routes_documents.ai_check(1, routes_documents.AiCheckBody(), session=None)
    _cancel_after_first(response)
    _assert_stopped(model, "Reviewing a document")


def test_a_cancelled_weekly_digest_stops_the_model(monkeypatch):
    model = _SlowModel()
    monkeypatch.setattr(routes_insights.deps, "get_ollama", lambda: model)
    monkeypatch.setattr(routes_insights.deps, "get_model_manager", lambda: _MANAGER)
    monkeypatch.setattr(routes_insights.deps, "get_config", lambda: SimpleNamespace(get_preference=lambda k, d=None: d))
    monkeypatch.setattr(routes_insights, "_digest_notes", lambda session: [{"title": "a"}])
    monkeypatch.setattr(routes_insights, "digest_question", lambda session: "q")
    monkeypatch.setattr(routes_insights.librarian, "resolve_persona_prompt", lambda *a, **k: "")
    monkeypatch.setattr(routes_insights.librarian, "plan_budget", lambda *a, **k: None)
    monkeypatch.setattr(routes_insights.librarian, "build_messages", lambda *a, **k: [])
    response = routes_insights.weekly_digest_stream(session=None)
    _cancel_after_first(response)
    _assert_stopped(model, "Writing the weekly digest")


def test_format_declines_before_producing_a_file_the_save_would_refuse():
    """L-documents-96: a file over `MAX_CONTENT` is refused on save (422). Format must say so and
    leave the text as written, not hand over output that is then silently lost."""
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "frontend/js/documents-code-format.js").read_text(encoding="utf-8")
    assert f"grown > {routes_documents.MAX_CONTENT}" in source
    assert "Your text is unchanged." in source
    assert source.index("grown > 500000") < source.index("view.dispatch({\n      changes,")
