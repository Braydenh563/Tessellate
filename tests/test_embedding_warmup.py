"""The embedding warm-up thread, and the two things it must not do.

It must not start the model load before the first page has loaded, and it must
not load a model for a notebook with nothing in it. Both came from the same
CI failure (run 34734999382): with sentence-transformers installed, the torch
import the warm-up triggered stalled the event loop past the shell's 8s
`/auth/status` probe on a fresh data dir, and the lock screen never appeared.
"""

from __future__ import annotations

import threading
import time

import pytest

from tessellate.ai import embeddings
from tessellate.ai.embeddings import EmbeddingService
from tessellate.core import jobs
from tessellate.entry import manager
from tessellate.search import search_manager


class _Service:
    def __init__(self):
        self.calls = 0
        self.done = threading.Event()

    def embed_text(self, _text):
        self.calls += 1
        self.done.set()


@pytest.fixture
def fresh_warmup(monkeypatch, app_state):
    """Each test starts from a process that has not warmed yet, with no pause.

    `app_state` because the warm-up thread reads the settings: without it the
    thread starts the app in the repo's data folder."""
    monkeypatch.setattr(embeddings, "_warmup", {"running": False, "started": False, "error": False})
    monkeypatch.setattr(embeddings, "WARMUP_DELAY_SECONDS", 0)
    monkeypatch.setattr(embeddings, "_pulse", {"at": 0.0})
    # Nothing to backfill and no matrix to warm: not what is under test.
    monkeypatch.setattr(embeddings, "backfill_missing", lambda *_a, **_k: None)


def test_an_empty_notebook_loads_no_model(fresh_warmup, monkeypatch):
    monkeypatch.setattr(embeddings, "_notebook_has_notes", lambda _f: False)
    service = _Service()
    embeddings.start_warmup(service, session_factory=lambda: None)
    assert not service.done.wait(0.5)
    assert service.calls == 0


def test_a_notebook_with_notes_warms_the_model(fresh_warmup, monkeypatch):
    monkeypatch.setattr(embeddings, "_notebook_has_notes", lambda _f: True)
    service = _Service()
    embeddings.start_warmup(service, session_factory=lambda: None)
    assert service.done.wait(2)
    assert service.calls == 1


def test_no_session_factory_still_warms(fresh_warmup):
    """Callers that pass no factory (older wiring, tests) keep the old
    behaviour: there is no notebook to ask, so the model loads."""
    service = _Service()
    embeddings.start_warmup(service)
    assert service.done.wait(2)


def test_the_pause_comes_before_the_load(fresh_warmup, monkeypatch):
    """The delay is what lets the first page load through; it has to sit in
    front of the model load, not after it."""
    order = []
    monkeypatch.setattr(embeddings, "_notebook_has_notes", lambda _f: True)
    monkeypatch.setattr(embeddings.time, "sleep", lambda _s: order.append("pause"))

    class Recording(_Service):
        def embed_text(self, text):
            order.append("load")
            super().embed_text(text)

    service = Recording()
    embeddings.start_warmup(service, session_factory=lambda: None)
    assert service.done.wait(2)
    assert order == ["pause", "load"]


def test_an_unreadable_database_does_not_stop_the_warm_up():
    """A wrong True costs one model load; a wrong False costs a cold first
    search. The helper errs on the side of warming."""

    def broken_factory():
        raise RuntimeError("no database")

    assert embeddings._notebook_has_notes(broken_factory) is True


def test_the_helper_reads_the_real_table(tmp_path):
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(f"sqlite:///{tmp_path / 'n.db'}")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE entries (id INTEGER PRIMARY KEY)"))
    factory = sessionmaker(bind=engine)
    assert embeddings._notebook_has_notes(factory) is False
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO entries (id) VALUES (1)"))
    assert embeddings._notebook_has_notes(factory) is True


def test_the_load_waits_for_the_app_to_go_quiet(fresh_warmup, monkeypatch):
    """A dashboard loading right after login must not share the CPU with the
    torch import: while requests keep arriving the warm-up holds off, and it
    goes once the app has been quiet for the idle window."""

    monkeypatch.setattr(embeddings, "_notebook_has_notes", lambda _f: True)
    monkeypatch.setattr(embeddings, "WARMUP_IDLE_SECONDS", 0.3)
    monkeypatch.setattr(embeddings, "WARMUP_MAX_WAIT_SECONDS", 10)
    service = _Service()
    embeddings.note_request()
    started = time.monotonic()
    embeddings.start_warmup(service, session_factory=lambda: None)
    for _ in range(4):
        time.sleep(0.1)
        embeddings.note_request()
    assert service.calls == 0, "the model loaded while requests were still arriving"
    assert service.done.wait(3)
    assert time.monotonic() - started >= 0.6


def test_a_never_visited_app_still_warms_within_the_cap(fresh_warmup, monkeypatch):

    monkeypatch.setattr(embeddings, "_notebook_has_notes", lambda _f: True)
    monkeypatch.setattr(embeddings, "WARMUP_IDLE_SECONDS", 5)
    monkeypatch.setattr(embeddings, "WARMUP_MAX_WAIT_SECONDS", 0.4)
    service = _Service()
    stop = False

    def keep_busy():
        while not stop:
            embeddings.note_request()
            time.sleep(0.05)

    busy = threading.Thread(target=keep_busy, daemon=True)
    busy.start()
    embeddings.start_warmup(service, session_factory=lambda: None)
    assert service.done.wait(3)
    stop = True


def test_no_request_yet_means_no_wait(fresh_warmup, monkeypatch):
    monkeypatch.setattr(embeddings, "_notebook_has_notes", lambda _f: True)
    monkeypatch.setattr(embeddings, "WARMUP_IDLE_SECONDS", 5)
    service = _Service()
    embeddings.start_warmup(service, session_factory=lambda: None)
    assert service.done.wait(1)


# The first question after a restart reads by words while the search model loads (a cold load was 21.75 s), and a subject that is a category's whole name is that category

class _Models:
    def embedding_backend(self) -> str:
        return "sentence-transformers"

    def embedding_st_model(self) -> str:
        return "BAAI/bge-small-en-v1.5"


class _Cold(EmbeddingService):
    """A local model not yet loaded, whose load takes the time it took."""

    def __init__(self) -> None:
        super().__init__(_Models(), None)
        self.loads = 0

    def _load_st_model(self):  # noqa: ANN202
        self.loads += 1
        time.sleep(0.3)
        raise RuntimeError("no model in tests")


def test_a_cold_model_is_not_waited_for(monkeypatch):
    queued: list[str] = []
    monkeypatch.setattr(jobs, "enqueue", lambda kind, fn, **kw: queued.append(kw.get("dedupe_key", kind)))
    cold = _Cold()
    assert cold.loads_cold()
    started = time.perf_counter()
    assert search_manager.query_vector(cold, "courses and study") is None
    assert time.perf_counter() - started < 0.1 and cold.loads == 0
    assert queued == ["search-warm"]


def test_a_loaded_or_fake_model_is_used_as_before(fake_embeddings):
    assert not fake_embeddings.loads_cold()
    assert search_manager.query_vector(fake_embeddings, "gaming mouse") is not None


def test_with_no_meaning_search_a_category_named_whole_is_that_category(session, app_state):
    from tessellate.core import deps
    from tests.fakes import FakeEmbeddingService

    deps.override_ai(embeddings=FakeEmbeddingService(available=False))
    study = manager.create_entry(session, "Psych lecture 1: memory is reconstructive.", category_name="Courses & Study")
    manager.create_entry(session, "Bought oat milk and eggs.", category_name="Shopping")
    session.commit()
    found, mode = search_manager.retrieve(session, "what have I saved about courses & study?", FakeEmbeddingService(available=False), limit=5)
    assert mode == "category" and [e.id for e in found] == [study.id]


def test_why_says_the_search_read_words_only():
    from tessellate.ai import why

    lines = why.lines(intent="notes", mode="keyword", matched=2, used=2, composed=True, loading=True, marks={})
    assert any("the search by meaning was still loading, so it read words only" in line["text"] for line in lines)


def test_through_the_route_a_cold_model_answers_at_once_and_says_so(client, session, monkeypatch):
    import json

    from tessellate.ai import composer_digest
    from tessellate.core import deps

    manager.create_entry(session, "Went to the gym after work.", category_name="Fitness")
    session.commit()
    monkeypatch.setattr(jobs, "enqueue", lambda *a, **kw: None)
    deps.override_ai(embeddings=_Cold())
    started = time.perf_counter()
    body = {"question": "what do I need to buy?", "history": [], "notes_only": True, "use_tools": False, "answer_from": "notes"}
    with client.stream("POST", "/chat/stream", json=body) as response:
        events = [json.loads(line) for line in response.iter_lines() if line.strip()]
    assert time.perf_counter() - started < 5
    text = "".join(e.get("delta", "") for e in events if e.get("type") == "answer")
    assert composer_digest.PHRASES["meaning_loading"] in text
    why = next(e for e in events if e.get("type") == "why")
    assert any("still loading" in line["text"] for line in why["lines"])
