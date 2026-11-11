"""Durable jobs (WORLD_CLASS_PLAN B2): a `jobs` table, leases, resume after
a kill, `/jobs` and `/jobs/stream`.

The gate the plan set is "kill the server mid-OCR, restart, the job
resumes". `test_a_job_killed_mid_run_is_resumed_by_the_next_process` does
exactly that with two real processes and a real SIGKILL, against a stand-in
handler that sleeps where Tesseract would read (the sandbox's Tesseract is
too quick to be killed mid-read on purpose). The rest pin each piece on its
own: the row's life, the lease, the resume rules, the routes.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import textwrap
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import select

from tessellate.core import deps, jobs, jobstore
from tessellate.core.database import DurableJob
from tessellate.core.database_manager import DatabaseManager

ROOT = Path(__file__).resolve().parents[1]

#: The test handlers below, by the dotted name `jobstore.HANDLERS` uses.
CALLS: list[tuple] = []


def remember_call(n, path):  # noqa: ANN001, ANN201
    CALLS.append((n, path))


def failing_call(n):  # noqa: ANN001, ANN201
    raise RuntimeError(f"no luck with {n}")


@pytest.fixture()
def db(tmp_path):
    return DatabaseManager(tmp_path / "jobs.db")


@pytest.fixture()
def kinds(monkeypatch):
    monkeypatch.setitem(jobstore.HANDLERS, "test-remember", f"{__name__}:remember_call")
    monkeypatch.setitem(jobstore.HANDLERS, "test-fail", f"{__name__}:failing_call")
    CALLS.clear()
    yield
    CALLS.clear()


def _rows(db):
    with db.session() as session:
        return list(session.scalars(select(DurableJob).order_by(DurableJob.id)))


def _wait(predicate, seconds=5.0):
    ends = time.monotonic() + seconds
    while time.monotonic() < ends:
        if predicate():
            return True
        time.sleep(0.02)
    return predicate()


def test_every_named_handler_imports():
    for kind in jobstore.HANDLERS:
        func = jobstore.resolve(kind)
        assert callable(func), kind
        assert jobstore.durable_kind(kind, func), kind


def test_payloads_round_trip_paths_and_refuse_objects():
    args, kwargs = jobstore.decode_payload(jobstore.encode_payload((3, Path("/a/b.png")), {"force": True}))
    assert args == (3, Path("/a/b.png")) and kwargs == {"force": True}
    with pytest.raises(jobstore.NotDurable):
        jobstore.encode_payload((object(),), {})


def test_a_pool_job_with_a_named_handler_is_recorded_leased_and_closed(db, kinds):
    pool = jobs.Pool(widths={"cpu": 1})
    try:
        with _patched_db(db):
            pool.enqueue("test-remember", remember_call, 4, Path("/p.png"), name="p.png", dedupe_key=("r", 4))
            assert _wait(lambda: [r.state for r in _rows(db)] == ["done"])
    finally:
        pool.shutdown(deadline=2)
    row = _rows(db)[0]
    assert CALLS == [(4, Path("/p.png"))]
    assert (row.kind, row.name, row.attempts, row.owner) == ("test-remember", "p.png", 1, jobstore.OWNER)
    assert json.loads(row.dedupe_key) == ["r", 4]
    assert row.finished_at is not None and row.lease_until is None


def test_a_failure_is_recorded_with_its_reason(db, kinds):
    pool = jobs.Pool(widths={"cpu": 1})
    try:
        with _patched_db(db):
            pool.enqueue("test-fail", failing_call, 9)
            assert _wait(lambda: [r.state for r in _rows(db)] == ["failed"])
    finally:
        pool.shutdown(deadline=2)
    assert _rows(db)[0].error == "no luck with 9"


def test_a_stand_in_function_runs_but_is_not_remembered(db, kinds):
    """A test's monkeypatched reader, or any other function than the named
    one, must not leave a row that a later launch would run as the real one."""
    pool = jobs.Pool(widths={"cpu": 1})
    ran = threading.Event()
    try:
        with _patched_db(db):
            pool.enqueue("test-remember", lambda *a: ran.set(), 1, Path("/x"))
            assert ran.wait(2)
    finally:
        pool.shutdown(deadline=2)
    assert _rows(db) == []


def test_no_database_records_nothing_and_still_runs(kinds):
    pool = jobs.Pool(widths={"cpu": 1})
    try:
        with _patched_db(None):
            pool.enqueue("test-remember", remember_call, 2, Path("/y"))
            assert _wait(lambda: CALLS == [(2, Path("/y"))])
    finally:
        pool.shutdown(deadline=2)


def test_a_lease_is_taken_once_and_renewed_by_its_owner(db, kinds):
    job_id = jobstore.record("test-remember", (1, Path("/z")), {}, db=db)
    assert jobstore.lease(job_id, db=db) is True
    assert jobstore.lease(job_id, db=db) is False  # already running
    first = _rows(db)[0].lease_until
    time.sleep(0.01)
    assert jobstore.renew([job_id], db=db) == 1
    assert _rows(db)[0].lease_until > first
    jobstore.finish(job_id, db=db)
    assert jobstore.held() == [] or job_id not in jobstore.held()


def test_a_cancelled_queued_job_is_never_run(db, kinds):
    job_id = jobstore.record("test-remember", (1, Path("/z")), {}, db=db)
    assert jobstore.cancel(job_id, db=db) == (True, "Stopped before it started.")
    assert jobstore.lease(job_id, db=db) is False
    assert _rows(db)[0].state == "cancelled"
    stopped, detail = jobstore.cancel(job_id, db=db)
    assert not stopped and "already finished" in detail


def test_a_running_job_is_not_interrupted(db, kinds):
    job_id = jobstore.record("test-remember", (1, Path("/z")), {}, db=db)
    jobstore.lease(job_id, db=db)
    stopped, detail = jobstore.cancel(job_id, db=db)
    assert not stopped and "will finish" in detail
    jobstore.finish(job_id, db=db)


def _set(db, job_id, **values):
    with db.session() as session:
        row = session.get(DurableJob, job_id)
        for key, value in values.items():
            setattr(row, key, value)
        session.commit()


def test_resume_queues_the_left_work_and_leaves_live_leases(db, kinds):
    now = datetime.now(timezone.utc)
    queued = jobstore.record("test-remember", (1, Path("/a")), {}, dedupe_key=("k", 1), db=db)
    lapsed = jobstore.record("test-remember", (2, Path("/b")), {}, db=db)
    _set(db, lapsed, state="running", owner="gone-1", attempts=1, lease_until=now - timedelta(seconds=5))
    live = jobstore.record("test-remember", (3, Path("/c")), {}, db=db)
    _set(db, live, state="running", owner="alive-2", attempts=1, lease_until=now + timedelta(seconds=600))
    poison = jobstore.record("test-remember", (4, Path("/d")), {}, db=db)
    _set(db, poison, state="running", owner="gone-1", attempts=jobstore.MAX_ATTEMPTS, lease_until=now - timedelta(seconds=5))
    retired = jobstore.record("test-retired", (5,), {}, db=db)

    submitted = []
    counts = jobstore.resume(db=db, enqueue=lambda *call: submitted.append(call))

    assert counts == {"resumed": 2, "gave_up": 1, "waiting": 1, "unknown": 1}
    assert [(c[1], c[2], c[5], c[6]) for c in submitted] == [
        (remember_call, (1, Path("/a")), ("k", 1), queued),
        (remember_call, (2, Path("/b")), None, lapsed),
    ]
    states = {row.id: row.state for row in _rows(db)}
    assert states == {queued: "queued", lapsed: "queued", live: "running", poison: "failed", retired: "failed"}
    assert "not tried again" in _rows(db)[3].error
    # The live lease is looked at again when it would run out: one timer,
    # which the pool's shutdown cancels.
    assert jobstore._timer is not None and jobstore._timer.is_alive()
    jobstore.stop()
    assert jobstore._timer is None


def test_a_resumed_row_already_in_hand_is_closed_not_left_queued(db, kinds):
    pool = jobs.Pool(widths={"cpu": 1})
    gate = threading.Event()
    try:
        with _patched_db(db):
            pool.enqueue("test-remember", lambda *a: gate.wait(2), 1, dedupe_key=("same", 1))
            old = jobstore.record("test-remember", (1, Path("/a")), {}, dedupe_key=("same", 1), db=db)
            pool.resubmit("test-remember", remember_call, (1, Path("/a")), {}, "", ("same", 1), old, db)
            gate.set()
    finally:
        pool.shutdown(deadline=2)
    assert _rows(db)[0].state == "done"


def test_prune_keeps_the_work_in_hand(db, kinds, monkeypatch):
    monkeypatch.setattr(jobstore, "KEEP_FINISHED_ROWS", 1)
    for n in range(3):
        job_id = jobstore.record("test-remember", (n, Path("/a")), {}, db=db)
        jobstore.lease(job_id, db=db)
        jobstore.finish(job_id, db=db)
    waiting = jobstore.record("test-remember", (9, Path("/a")), {}, db=db)
    assert jobstore.prune(db=db) == 2
    assert {row.id: row.state for row in _rows(db)} == {3: "done", waiting: "queued"}


# -- the routes ----------------------------------------------------------------


def test_the_routes_list_cancel_and_stream(client, kinds):
    db = deps.get_db()
    job_id = jobstore.record("ocr", (7, Path("/pic.png")), {}, name="pic.png", db=db)
    listed = client.get("/jobs", params={"limit": 5}).json()["jobs"]
    assert [(j["id"], j["state"], j["label"], j["name"]) for j in listed] == [
        (job_id, "queued", jobs.LABELS["ocr"], "pic.png")
    ]
    with client.stream("GET", "/jobs/stream", params={"seconds": 0}) as response:
        assert response.headers["content-type"].startswith("text/event-stream")
        body = "".join(response.iter_text())
    assert "event: jobs" in body
    data = json.loads(body.split("data: ", 1)[1].split("\n", 1)[0])
    assert data["jobs"][0]["id"] == job_id
    answer = client.post(f"/jobs/{job_id}/cancel").json()
    assert answer["stopped"] is True
    assert client.post(f"/jobs/{job_id}/cancel").json()["stopped"] is False
    assert client.post("/jobs/99999/cancel").json()["stopped"] is False


def test_the_panels_quit_stops_a_queued_reading(client, kinds):
    db = deps.get_db()
    jobstore.record("ocr", (7, Path("/pic.png")), {}, name="pic.png", db=db)
    answer = client.post("/tasks/cancel", json={"kind": "job-ocr", "name": "pic.png"}).json()
    assert answer == {"status": "ok", "stopped": True, "detail": "Stopped 1 waiting job."}
    assert _rows(db)[0].state == "cancelled"


def test_the_stream_sends_a_change(client, kinds, monkeypatch):
    """With a window open, a job recorded after the first snapshot arrives
    as a second `jobs` event. The record is made by the first snapshot
    itself, right after it has read its rows, so no clock is involved: a
    0.2 s timer here once fired after the 2.5 s window closed on a loaded CI
    runner (one event, "retry: 3000", py3.12, 2026-10-05)."""
    db = deps.get_db()
    seen = jobstore.version()
    original = jobstore.list_jobs
    calls: list[int] = []

    def first_then_record(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        rows = original(*args, **kwargs)
        if not calls:
            calls.append(1)
            jobstore.record("ocr", (8, Path("/late.png")), {}, name="late.png", db=db)
        return rows

    monkeypatch.setattr(jobstore, "list_jobs", first_then_record)
    with client.stream("GET", "/jobs/stream", params={"seconds": 2.5}) as response:
        body = "".join(response.iter_text())
    assert jobstore.version() > seen
    events = body.split("event: jobs")[1:]
    assert len(events) >= 2, body
    assert "late.png" not in events[0] and "late.png" in events[-1]


def test_launch_resumes_through_the_pool(app_state, kinds):
    """`create_app` runs `jobs.resume`: a row left queued is run."""
    from tessellate.api.app import create_app

    db = deps.get_db()
    jobstore.record("test-remember", (5, Path("/left.png")), {}, db=db)
    create_app()
    try:
        assert _wait(lambda: [r.state for r in _rows(db)] == ["done"])
    finally:
        jobs.shutdown(deadline=2)
    assert CALLS == [(5, Path("/left.png"))]


# -- the gate: a real process, a real kill ------------------------------------

_CHILD = textwrap.dedent(
    """
    import json, os, sys, time
    from pathlib import Path

    sys.path.insert(0, {src!r})
    from tessellate.core import jobruns, jobs, jobstore
    from tessellate.core.database_manager import DatabaseManager

    db_path, marks, mode = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
    db = DatabaseManager(db_path)
    jobruns.set_database_source(lambda: db)
    # Short leases so the second process need not wait half a minute.
    jobstore.LEASE_SECONDS = 2.0
    jobstore.HEARTBEAT_SECONDS = 0.5


    def slow_read(upload_id, path):
        (marks / f"started-{{os.getpid()}}").write_text(str(upload_id))
        if mode == "start":
            time.sleep(120)  # killed in here, mid-read
        (marks / "done").write_text(f"{{upload_id}} {{path}} {{os.getpid()}}")


    jobstore.register("test-slow", "__main__:slow_read")
    if mode == "start":
        jobs.enqueue("test-slow", slow_read, 41, Path("/pics/scan.png"), name="scan.png")
        time.sleep(120)
    else:
        print(json.dumps(jobs.resume(db=db)), flush=True)
        ends = time.monotonic() + 20
        while time.monotonic() < ends and not (marks / "done").exists():
            time.sleep(0.05)
        time.sleep(0.3)  # let the worker write the ending
        jobs.shutdown(deadline=2)
    """
)


@pytest.mark.skipif(sys.platform == "win32", reason="SIGKILL")
def test_a_job_killed_mid_run_is_resumed_by_the_next_process(tmp_path):
    script = tmp_path / "child.py"
    script.write_text(_CHILD.format(src=str(ROOT / "src")))
    marks = tmp_path / "marks"
    marks.mkdir()
    db_path = tmp_path / "notebook.db"
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}

    first = subprocess.Popen([sys.executable, str(script), str(db_path), str(marks), "start"], env=env)
    try:
        assert _wait(lambda: any(marks.glob("started-*")), seconds=30), "the first process never started the job"
        rows = _rows(DatabaseManager(db_path))
        assert [(r.state, r.attempts) for r in rows] == [("running", 1)]
    finally:
        first.send_signal(signal.SIGKILL)
        first.wait(10)
    assert first.returncode == -signal.SIGKILL
    assert not (marks / "done").exists()

    second = subprocess.run(
        [sys.executable, str(script), str(db_path), str(marks), "resume"],
        env=env, capture_output=True, text=True, timeout=60,
    )
    assert second.returncode == 0, second.stderr
    counts = json.loads(second.stdout.strip().splitlines()[0])
    # Within its lease the dead process's row waits, then is taken over;
    # past it, it is taken at once. Either way it is run exactly once more.
    assert counts["resumed"] + counts["waiting"] == 1

    done = (marks / "done").read_text().split()
    assert done[:2] == ["41", "/pics/scan.png"]
    assert int(done[2]) == second_pid(marks, exclude=first.pid)
    row = _rows(DatabaseManager(db_path))[0]
    assert (row.state, row.attempts, row.error) == ("done", 2, "")


def second_pid(marks: Path, exclude: int) -> int:
    pids = [int(p.name.split("-", 1)[1]) for p in marks.glob("started-*")]
    others = [pid for pid in pids if pid != exclude]
    assert len(others) == 1, pids
    return others[0]


# -- helpers -------------------------------------------------------------------


class _patched_db:
    """Point the job store's database source at `db` for a block."""

    def __init__(self, db) -> None:  # noqa: ANN001
        self.db = db

    def __enter__(self):  # noqa: ANN204
        from tessellate.core import jobruns

        self._before = jobruns._peek_db
        jobruns.set_database_source(lambda: self.db)
        return self

    def __exit__(self, *exc) -> None:  # noqa: ANN002
        from tessellate.core import jobruns

        jobruns.set_database_source(self._before)
