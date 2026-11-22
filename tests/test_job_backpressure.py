"""The job queue's back-pressure (WORLD_CLASS_PLAN 19.5).

Measured 2026-10-05 with a model lane held busy and 2,000 captions queued
behind it (a folder of pictures dropped at once): enqueueing never blocks,
costs 53 microseconds a job, and a queued job holds 484 bytes
(tracemalloc), so neither needs a bound. What did not hold was the panel:
`pending()` returned one row per queued job, so every `/tasks` poll (every
few seconds while anything runs) carried 2,000 rows, 347 KB of JSON,
for a panel that can show a handful. The queue is now reported as the jobs
running, the next few waiting of each kind, and one row per kind saying how
many more wait, so the poll's size is bounded by the number of kinds rather
than by how many files somebody dropped.
"""

from __future__ import annotations

import json
import threading
import time

from tessellate.core import jobs


def _wait_for(predicate, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("timed out")


def test_a_long_queue_is_reported_in_bounded_rows_with_the_true_count() -> None:
    pool = jobs.Pool({"model": 1}, kind_lanes={"caption": "model", "vision": "model"})
    release = threading.Event()
    try:
        pool.enqueue("caption", release.wait, 10, name="first.png")
        _wait_for(lambda: pool.running_count() == 1)
        started = time.process_time()
        for i in range(2000):
            pool.enqueue("caption", lambda: None, name=f"pic{i}.png")
        for i in range(30):
            pool.enqueue("vision", lambda: None, name=f"scan{i}.png")
        per_job_us = (time.process_time() - started) / 2030 * 1e6
        # Never blocks: a whole folder is queued in well under a second.
        assert per_job_us < 2000, per_job_us
        rows = pool.pending()
        assert len(rows) <= 1 + 2 * (jobs.PENDING_ROWS_PER_KIND + 1), len(rows)
        more = {row["kind"]: row for row in rows if row.get("more")}
        assert more["job-caption"]["more"] == 2000 - jobs.PENDING_ROWS_PER_KIND
        assert more["job-vision"]["more"] == 30 - jobs.PENDING_ROWS_PER_KIND
        assert "1,990 more" in more["job-caption"]["detail"]
        assert pool.queued_count() == 2030
        assert len(json.dumps(rows)) < 20_000
        # The running one is first, then the oldest waiting.
        assert rows[0]["name"] == "first.png" and not rows[0]["queued"]
        assert rows[1]["name"] == "pic0.png"
    finally:
        release.set()
        pool.shutdown(deadline=2.0)


def test_a_short_queue_is_listed_whole() -> None:
    pool = jobs.Pool({"model": 1}, kind_lanes={"caption": "model"})
    release = threading.Event()
    try:
        pool.enqueue("caption", release.wait, 10, name="first.png")
        _wait_for(lambda: pool.running_count() == 1)
        for i in range(3):
            pool.enqueue("caption", lambda: None, name=f"pic{i}.png")
        rows = pool.pending()
        assert [row["name"] for row in rows] == ["first.png", "pic0.png", "pic1.png", "pic2.png"]
        assert not any(row.get("more") for row in rows)
    finally:
        release.set()
        pool.shutdown(deadline=2.0)
