"""How many requests run at once, and how many connections they may hold.

Three settings in three files were never sized together (audit 1031 BK1, AR11):
sync routes run on anyio's worker threads (40), the engine used SQLAlchemy's
default pool (5 plus 10) and a 30 s wait, so the 16th of 24 parallel note
creations waited the full 30 s for a connection and answered a bare 500.

The rule here: **every worker thread can hold a connection**, so a request never
queues for one behind a request that is itself waiting (SQLite connections are
cheap; the file allows one writer and `busy_timeout` queues the rest). A pool
that is still exhausted after `POOL_TIMEOUT` is a busy notebook, 503 with
`Retry-After`, and `tests/test_concurrency_sizing_1031.py` holds the inequality.
"""

from __future__ import annotations

#: anyio's worker-thread limit for sync routes (its own default, now stated).
WORKER_THREADS = 40
#: Connections kept open, and more allowed for a burst (background jobs and the
#: job pool hold sessions of their own beside the request threads).
POOL_SIZE = 40
POOL_OVERFLOW = 20
#: Seconds a request waits for a connection before it answers 503.
POOL_TIMEOUT = 5
#: `Retry-After` on that 503.
RETRY_AFTER_SECONDS = 2


def apply_worker_limit() -> None:
    """Set anyio's worker-thread limit to `WORKER_THREADS` (called from the
    app's lifespan, on the running loop, so the number the pool was sized for
    is the number in force rather than a library default)."""
    import anyio.to_thread

    anyio.to_thread.current_default_thread_limiter().total_tokens = WORKER_THREADS
