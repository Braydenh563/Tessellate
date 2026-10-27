"""What one background filing costs, counted rather than timed (INBOX 434).

The wall-clock figures (1.2 to 4 s for "filed") came from one encode on
torch's default thread pool (`tests/test_embedding_threads.py`); what is left
is structure, and structure can be counted: how many times the model is
asked, and how many statements the job issues however big the notebook is.
Neither depends on the machine, so a regression shows up as a failed
assertion rather than as a slow afternoon.
"""

from __future__ import annotations

import types

import numpy as np
import pytest
from sqlalchemy import event

from tessellate.ai.embeddings import EmbeddingService
from tessellate.api import routes_entries
from tessellate.core import deps
from tessellate.core.database import Entry

_WORDS = ("garden", "tomato", "budget", "gym", "flight", "bread", "meeting", "hike")


class _CountingEmbeddings(EmbeddingService):
    """The real service (its cache, its `store_for_entry`) over a model that
    only counts, so "how many encodes" is the real code's answer."""

    def __init__(self) -> None:
        super().__init__(
            model_manager=types.SimpleNamespace(embedding_backend=lambda: "fastembed"),
            ollama_client=None,
        )
        self.encodes: list[str] = []

    def backend_id(self) -> str:
        return "counting:v1"

    def active_model(self) -> str:
        return "counting"

    def is_ready(self) -> bool:
        return True

    def loads_cold(self) -> bool:
        #: Its "model" is loaded from the start: a cold one sends the search
        #: to words and queues a "warm up" encode (6cf293e43), not a filing's cost.
        return False

    def _embed_uncached(self, text):  # noqa: ANN001
        self.encodes.append(text)
        vector = np.zeros(len(_WORDS) + 1, dtype="float32")
        for i, word in enumerate(_WORDS):
            if word in text.lower():
                vector[i] = 1.0
        if not vector.any():
            vector[-1] = 1.0
        return vector


@pytest.fixture()
def counting(app_state):
    from tests.fakes import FakeOllama

    service = _CountingEmbeddings()
    deps.override_ai(ollama=FakeOllama(running=False), embeddings=service)
    return service


def _seed(client, count: int) -> None:
    for i in range(count):
        word = _WORDS[i % len(_WORDS)]
        client.post(
            "/entries",
            json={"content": f"{word} plan number {i} for the week", "category": word.title(), "tags": [word]},
        )


def _file_one(client, session, text: str) -> list[str]:
    """Save one deferred note and run its filing job inline; returns the
    the SQL statements the job issued."""

    routes_entries._queue_filing, original = (lambda entry: None), routes_entries._queue_filing
    try:
        created = client.post("/entries", json={"content": text, "defer_filing": True}).json()
    finally:
        routes_entries._queue_filing = original
    statements = []
    engine = deps.get_db().engine

    def count(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", count)
    try:
        routes_entries._file_entry_in_background(created["id"], "default")
    finally:
        event.remove(engine, "before_cursor_execute", count)
    session.expire_all()
    entry = session.get(Entry, created["id"])
    assert entry.filing_state != "pending"
    return statements


def test_a_filing_asks_the_model_at_most_twice(client, session, counting):
    _seed(client, 6)
    counting.encodes.clear()
    counting.clear_embed_cache()

    _file_one(client, session, "garden bed of tomato plants to water")

    # Once for the note's words (filing, then the duplicate check from the
    # cache) and once for what is stored (the words plus where it was filed).
    assert len(counting.encodes) <= 2, counting.encodes


def test_the_job_issues_no_more_statements_in_a_big_notebook(client, session, counting):
    _seed(client, 4)
    small = _file_one(client, session, "garden bed of tomato plants to water")
    _seed(client, 36)
    large = _file_one(client, session, "garden bed of tomato plants to weed")

    # A per-note query anywhere in the job (an N+1 over the notebook) would
    # make the second figure grow with the forty notes added between them,
    # by forty or more. The few it does gain are the near-duplicate the
    # larger notebook finds (one update and its re-index), not its size.
    assert len(large) <= len(small) + 6, (len(small), len(large), [" ".join(q.split())[:70] for q in large])
