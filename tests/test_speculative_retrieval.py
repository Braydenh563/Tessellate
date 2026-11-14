"""Speculative retrieval (WORLD_CLASS_PLAN H9, row 27): a typing pause in Ask
or chat warms the question's vector, so Enter does not wait for the
embedding model."""

from __future__ import annotations

import threading
import time
from pathlib import Path

from tessellate.core import deps
from tessellate.search import search_manager

ROOT = Path(__file__).resolve().parents[1]


class SlowCountingEmbeddings:
    """The test fakes' keyword vectors, slowed to a real model's pace and counted."""

    def __init__(self, inner, delay: float = 0.2):
        self.inner = inner
        self.delay = delay
        self.calls: list[str] = []

    def __getattr__(self, name):
        return getattr(self.inner, name)

    def embed_text(self, text):
        self.calls.append(text)
        time.sleep(self.delay)
        return self.inner.embed_text(text)


def test_a_warmed_question_is_not_embedded_again(ai_client, session, fake_embeddings):
    slow = SlowCountingEmbeddings(fake_embeddings)
    assert search_manager.warm(session, "what did I buy at the shopping trip", slow) is True
    assert len(slow.calls) == 1
    began = time.perf_counter()
    search_manager.retrieve(session, "what did I buy at the shopping trip", slow)
    elapsed = time.perf_counter() - began
    assert len(slow.calls) == 1, slow.calls
    # The 200 ms the model would have taken is not spent after Enter.
    assert elapsed < slow.delay


def test_the_route_warms_and_never_fails(ai_client, monkeypatch):
    warm_1 = ai_client.post("/search/warm", json={"q": "groceries for the week ahead"}).json()
    assert warm_1 == {"warmed": True}
    warm_2 = ai_client.post("/search/warm", json={"q": "hi"}).json()
    assert warm_2 == {"warmed": False}

    def broken():
        raise RuntimeError("no embeddings")

    monkeypatch.setattr(deps, "get_embeddings", broken)
    warm_3 = ai_client.post("/search/warm", json={"q": "groceries for the week ahead"}).json()
    assert warm_3 == {"warmed": False}


def test_the_boxes_send_their_words_on_a_pause():
    js = (ROOT / "frontend" / "js" / "navigation.js").read_text(encoding="utf-8")
    assert '"/search/warm"' in js
    assert 'box?.id !== "question" && box?.id !== "chat-input"' in js


def test_a_model_not_yet_loaded_starts_loading_in_the_background(session, monkeypatch):
    """Measured on a fresh install: the first question paid the embedding
    model's cold load. Focus in the box now starts it, without waiting.

    INBOX 1508: the load itself waits for the requests that came with the
    focus to stop (`wait_for_quiet`), so the engine's import does not run
    inside the burst; the request still returns at once. The wait is stubbed
    here (the process-wide request pulse is whatever earlier tests left)."""
    from tessellate.ai import embeddings as embedding_service

    order: list[str] = []
    monkeypatch.setattr(embedding_service, "wait_for_quiet", lambda max_wait: order.append(f"quiet {max_wait}"))

    release = threading.Event()
    started = threading.Event()

    class Cold:
        """Blocks inside the load until the test releases it: if `warm` ran the
        load on the caller's thread it could not return while this is held."""

        def __init__(self):
            self.calls = []
            self.thread = None

        def is_ready(self):
            return False

        def backend_id(self):
            return "cold"

        def embed_text(self, text):
            order.append("embed")
            self.calls.append(text)
            self.thread = threading.get_ident()
            started.set()
            release.wait(30)
            return None

    cold = Cold()
    try:
        assert search_manager.warm(session, "", cold) is False
        # Returned with the load not yet finished (release is still unset), and
        # the load is running elsewhere, not on this thread.
        assert not release.is_set()
        assert started.wait(30), "the background load never started"
        assert cold.thread != threading.get_ident()
    finally:
        release.set()
    assert cold.calls == ["warm up"]
    assert order == [f"quiet {search_manager.LOAD_LATER_MAX_WAIT_SECONDS}", "embed"]


def test_the_focus_call_with_no_words_does_not_touch_the_database(session, fake_embeddings):
    """INBOX 1508: `q: ""` has nothing to embed, so a ready model returns
    before the user's "today" is read."""

    touched: list[str] = []

    class NoSession:
        #: Records, then refuses, every attribute read; the list catches a
        #: read that a `getattr(..., default)` would otherwise swallow.
        def __getattr__(self, name):
            touched.append(name)
            raise AttributeError(name)

    assert search_manager.warm(NoSession(), "", fake_embeddings) is False
    assert not touched, f"the database was read for an empty question: {touched}"


def test_a_load_asked_twice_queues_once_and_a_finished_one_can_queue_again(monkeypatch):
    """L-chat-242: the flag is the only guard, set under a lock. A job
    `dedupe_key` that matched a load just finishing dropped the new one while
    the flag stayed set, so the model never loaded later."""
    from tessellate.ai import embeddings as embedding_service
    from tessellate.core import jobs

    monkeypatch.setattr(embedding_service, "warmup_running", lambda: False)
    monkeypatch.setattr(embedding_service, "wait_for_quiet", lambda max_wait: None)
    queued: list = []
    monkeypatch.setattr(jobs, "enqueue", lambda kind, func, *a, **k: queued.append((func, k)))

    class Svc:
        def embed_text(self, text):
            return None

    svc = Svc()
    search_manager._load_later(svc)
    search_manager._load_later(svc)
    assert len(queued) == 1
    assert "dedupe_key" not in queued[0][1]
    queued[0][0]()  # the load runs and finishes
    assert svc._warm_loading is False
    search_manager._load_later(svc)
    assert len(queued) == 2
