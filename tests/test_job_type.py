"""One `Job` type with lane, owner, cancel token and run record (INBOX 1502, audit AR6).

Jobs had six homes; `core/jobs.Job` is the one record every seat (the pool,
a reading on the request's thread, a watcher thread) shares, so the panel and
a shutdown ask one object the same four questions.
"""

from __future__ import annotations

import threading

from tessellate.core import jobruns, jobs, origin


def test_a_pool_job_is_background_and_owned_by_whoever_started_it():
    with jobruns.started_by("you"):
        job = jobs.Job(1, "ocr", print, (), {}, "scan.png")
    #: `ocr` is a person's own run as a history kind; the pool's `job-ocr` is not.
    assert (job.row_kind, job.lane, job.owner) == ("job-ocr", "background", "you")
    assert jobs.Job(2, "ocr", print).owner == "app"


def test_a_job_queued_for_another_device_says_so():
    with origin.acting_for(True):
        job = jobs.Job(1, "embed-entry", print)
    assert job.owner == jobs.ANOTHER_DEVICE and job.another_device


def test_stop_sets_the_token_and_asks_the_stopper():
    asked = threading.Event()
    job = jobs.Job(1, "watch", None, seat="thread", stopper=asked.set)
    assert job.stoppable and not job.cancel.is_set()
    assert job.stop() is True
    assert job.cancel.is_set() and asked.is_set()


def test_a_job_with_no_stopper_still_carries_the_token():
    job = jobs.Job(1, "probe", None, seat="thread")
    assert job.stop() is False and job.cancel.is_set() and not job.stoppable


def test_the_run_record_is_kept_on_the_job():
    job = jobs.Job(1, "caption", print, (), {}, "cat.png")
    run = job.open_run()
    try:
        assert job.run is run and run.title == "Describing an image: cat.png"
    finally:
        run.finish()
    assert jobs.Job(2, "pass", print).open_run() is None


def test_a_pending_row_carries_lane_and_owner():
    pool = jobs.Pool(widths={"cpu": 1})
    release = threading.Event()
    try:
        pool.enqueue("document", release.wait, 5, name="a.pdf")
        pool.enqueue("document", release.wait, 5, name="b.pdf")
        rows = pool.pending()
        assert rows and all(row["lane"] == "background" and row["owner"] for row in rows)
        assert {row["kind"] for row in rows} == {"job-document"}
    finally:
        release.set()
        pool.shutdown(deadline=2)


def test_a_reading_is_a_job_on_the_callers_thread():
    with jobs.reading("describe", 7, "", "fake-utility") as job:
        assert (job.seat, job.row_kind, job.lane) == ("here", "file-describe", "background")
        [row] = [row for row in jobs.readings() if row["kind"] == "file-describe"]
        assert row["name"] == "file 7" and row["detail"] == "file 7 (fake-utility)"
    assert not [row for row in jobs.readings() if row["name"] == "file 7"]
