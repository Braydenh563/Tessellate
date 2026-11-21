"""An edit's new vector is made after the PUT returns (audit 2026-10-05, ARCH-02 step 5).

`PUT /entries/{id}` with new text called the embedder on the request: on a
real model that is 200 to 400 ms before the editor's autosave came back,
growing with the model rather than the note. The stale vector is still
dropped on the request (a search must not find the old meaning), and the
new one is made on the model lane, newest text last.
"""

from __future__ import annotations

import threading
import time

import pytest
from fastapi.testclient import TestClient

from tessellate.core import deps, jobs
from tessellate.core.database import EmbeddingRecord
from tests.fakes import FakeEmbeddingService, FakeOllama


class GatedEmbeddings(FakeEmbeddingService):
    """Records each embed's text and thread, and can hold one."""

    def __init__(self) -> None:
        super().__init__(available=True)
        self.texts: list[str] = []
        self.threads: list[str] = []
        self.gate = threading.Event()
        self.gate.set()
        #: Embeds that got past the gate: one that finished before the gate
        #: opened timed out on it, which only a caller that waited could see.
        self.done = 0

    def embed_text(self, text):  # noqa: ANN001, ANN201
        self.texts.append(text)
        self.threads.append(threading.current_thread().name)
        #: Held until the test releases it, not for a fixed few seconds: a gate
        #: that lets itself go after N s is a wall-clock promise that the test
        #: thread gets to its next line inside N s, which a loaded machine breaks.
        self.gate.wait(120)
        self.done += 1
        return super().embed_text(text)


def _embed_jobs_in_flight() -> bool:
    """Is a note's embed job still queued or running in the process-global pool?

    The pool outlives every test and dedupes by `("embed-entry", note id)`, and
    every test here edits note 1 of a fresh database. A job left over from an
    earlier test (its last assertion passes once the vector row exists, a few
    statements before the job returns) is therefore still "the job in flight"
    for the next test's edit, which then folds into it and is never embedded:
    the wait for its vector times out. Draining before and after each test
    keeps the pool's state the test's own."""
    pool = jobs.pool()
    with pool._lock:
        return any(
            isinstance(job.dedupe_key, tuple) and job.dedupe_key[:1] == ("embed-entry",)
            for job in (*pool._running.values(), *pool._queued.values())
        )


@pytest.fixture()
def gated(app_state):
    from tessellate.api.app import create_app

    assert _wait(lambda: not _embed_jobs_in_flight(), 60), "an earlier embed job never finished"
    fake = GatedEmbeddings()
    deps.override_ai(ollama=FakeOllama(running=False), embeddings=fake)
    yield TestClient(create_app()), fake
    fake.gate.set()  # never leave a job parked on the gate for the next test
    _wait(lambda: not _embed_jobs_in_flight(), 60)


def _vector_count(entry_id: int) -> int:
    with deps.get_db().session() as session:
        return session.query(EmbeddingRecord).filter(EmbeddingRecord.entry_id == entry_id).count()


def _wait(predicate, timeout: float = 60.0) -> bool:  # noqa: ANN001
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return False


def _note(client) -> dict:
    note = client.post("/entries", json={"content": "the garden plan", "category": "Home"}).json()
    assert _wait(lambda: _vector_count(note["id"]) == 1)
    return note


def test_an_edit_returns_before_its_text_is_embedded(gated):
    client, fake = gated
    note = _note(client)
    fake.gate.clear()  # the next embed waits until released
    fake.texts.clear()
    fake.threads.clear()
    done = fake.done
    response = client.put(f"/entries/{note['id']}", json={"content": "the work budget for spring"})
    assert response.status_code == 200
    #: The gate is shut until the test opens it, so a PUT that embedded on the
    #: request returns only after its embed timed out on the gate (L-general-70).
    assert fake.done == done, "the PUT waited for the embedder"
    # The old meaning is gone at once; the new one arrives from the job.
    assert _vector_count(note["id"]) == 0
    fake.gate.set()
    assert _wait(lambda: _vector_count(note["id"]) == 1)
    assert any("work budget" in text for text in fake.texts)
    assert fake.threads and all(name.startswith("mm-job-") for name in fake.threads)


def test_an_unchanged_text_is_not_embedded_again(gated):
    client, fake = gated
    note = _note(client)
    fake.texts.clear()
    client.put(f"/entries/{note['id']}", json={"content": "the garden plan", "tags": ["x"]})
    time.sleep(0.2)
    assert fake.texts == []
    assert _vector_count(note["id"]) == 1


def test_an_edit_made_while_the_job_embeds_is_the_text_left_embedded(gated):
    client, fake = gated
    note = _note(client)
    fake.gate.clear()
    fake.texts.clear()
    client.put(f"/entries/{note['id']}", json={"content": "first edit about work"})
    assert _wait(lambda: len(fake.texts) >= 1)  # the job is holding the first text
    client.put(f"/entries/{note['id']}", json={"content": "second edit about health"})
    fake.gate.set()
    assert _wait(lambda: any("second edit" in text for text in fake.texts))
    assert _wait(lambda: _vector_count(note["id"]) == 1)
