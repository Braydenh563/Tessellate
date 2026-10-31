"""Threads and the connection pool are sized together (audit 1031 BK1, AR11).

24 parallel `POST /entries` gave 19 x 201 and 5 x 500 after 30 s: sync routes run
on a 40-thread pool while the engine kept SQLAlchemy's default pool (5 plus 10)
with a 30 s wait, so the 16th request waited out the default and died as a bare
500. `core/concurrency.py` owns the numbers; a pool that cannot give every worker
thread a connection is a test failure, and a pool that is still exhausted after
`POOL_TIMEOUT` answers 503 busy with `Retry-After`, never a 500."""

from __future__ import annotations

import threading

from fastapi.testclient import TestClient
from sqlalchemy.exc import TimeoutError as PoolTimeout

from tessellate.core import concurrency, deps


def test_the_pool_holds_a_connection_for_every_worker_thread():
    assert concurrency.POOL_SIZE + concurrency.POOL_OVERFLOW >= concurrency.WORKER_THREADS
    assert concurrency.POOL_TIMEOUT <= 10


def test_the_engine_uses_the_sizing(app_state):
    pool = deps.get_db().engine.pool
    assert pool.size() == concurrency.POOL_SIZE
    assert pool._max_overflow == concurrency.POOL_OVERFLOW  # noqa: SLF001  # no public getter
    assert pool.timeout() == concurrency.POOL_TIMEOUT


def test_the_worker_thread_limit_is_the_one_the_pool_was_sized_for():
    import anyio
    import anyio.to_thread

    async def limit() -> int:
        concurrency.apply_worker_limit()
        return anyio.to_thread.current_default_thread_limiter().total_tokens

    assert anyio.run(limit) == concurrency.WORKER_THREADS


def test_the_app_applies_it_at_startup():
    from pathlib import Path

    app = (Path(__file__).resolve().parent.parent / "src" / "tessellate" / "api" / "app.py").read_text(encoding="utf-8")
    assert "concurrency.apply_worker_limit()" in app


def test_24_parallel_note_creations_all_succeed(client):
    results: list[int] = []
    lock = threading.Lock()

    def make(i: int) -> None:
        r = client.post("/entries", json={"content": f"parallel note {i}"})
        with lock:
            results.append(r.status_code)

    threads = [threading.Thread(target=make, args=(i,)) for i in range(24)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(60)
    assert sorted(results) == [201] * 24


def test_an_exhausted_pool_answers_503_busy_with_retry_after(app_state, monkeypatch):
    from tessellate.api.app import create_app

    def starved(*_a, **_k):
        raise PoolTimeout("QueuePool limit of size 40 overflow 20 reached, connection timed out")

    monkeypatch.setattr(deps, "get_or_404", starved)
    api = TestClient(create_app(), raise_server_exceptions=False)
    r = api.get("/entries/1")
    assert r.status_code == 503
    assert r.json()["code"] == "busy"
    assert r.headers["Retry-After"]
