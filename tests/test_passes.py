"""INBOX 713: every scheduled pass, with its schedule, Run now and Stop.

The owner: "for a bunch of the background processes like the night shift and
stuff, is it possible to manually run them as well as manually stop or cancel
them when they are running??" Decision taken: Background tasks lists every
scheduled pass with its schedule and last run, a Run now on each (through the
job pool, deduped), and a running pass's row carries Stop (`/tasks/cancel`),
which ends it at its next step.
"""

from __future__ import annotations

import threading
import time

import pytest

from tessellate.core import jobs, passes


@pytest.fixture(autouse=True)
def _clean():
    passes.reset_for_tests()
    yield
    passes.reset_for_tests()


def _wait(check, seconds=10):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if check():
            return
        time.sleep(0.02)
    raise AssertionError("timed out")


def test_the_overview_names_every_scheduled_pass_with_its_schedule(client):
    runs = {run["kind"]: run for run in client.get("/jobs/last-runs").json()["jobs"]}
    for kind in ("autonomous", "night-shift", "learned-audit", "backup", "resurface", "embeddings-backfill", "maintenance"):
        assert kind in runs, kind
        assert runs[kind]["schedule"], kind
        assert runs[kind]["can_run"] is True, kind
    # A job a person starts by hand is not a scheduled pass.
    assert runs["import"].get("can_run") is not True


def test_run_now_goes_through_the_pool_and_is_deduped(client, monkeypatch):
    gate = threading.Event()
    calls = []

    def slow():
        calls.append(1)
        assert gate.wait(10)

    monkeypatch.setitem(passes.RUNNERS, "resurface", slow)
    first = client.post("/jobs/passes/resurface/run").json()
    assert first["started"] is True
    _wait(lambda: calls)
    second = client.post("/jobs/passes/resurface/run").json()
    assert second["started"] is False and "already" in second["message"]
    rows = [t for t in client.get("/tasks").json()["tasks"] if t["kind"] == "job-pass"]
    assert rows and rows[0]["name"] == "Resurfacing"
    gate.set()
    _wait(lambda: not passes.running("resurface"))
    assert calls == [1]


def test_an_unknown_pass_is_refused(client):
    response = client.post("/jobs/passes/no-such-pass/run")
    assert response.status_code == 404


def test_stop_ends_a_pass_at_its_next_step(client, monkeypatch):
    reached = []
    entered = threading.Event()
    gate = threading.Event()

    def first():
        reached.append("first")
        entered.set()
        assert gate.wait(10)

    def second():
        reached.append("second")

    monkeypatch.setattr(passes, "MAINTENANCE_STEPS", (first, second))
    started = client.post("/jobs/passes/maintenance/run").json()
    assert started["started"] is True
    assert entered.wait(5)
    row = next(t for t in client.get("/tasks").json()["tasks"] if t["kind"] == "job-pass")
    assert row["cancellable"] is True
    stopped = client.post("/tasks/cancel", json={"kind": "job-pass", "name": row["name"]}).json()
    assert stopped["stopped"] is True
    gate.set()
    _wait(lambda: not passes.running("maintenance"))
    assert reached == ["first"]


def test_a_pass_with_no_step_to_stop_at_says_so(client, monkeypatch):
    gate = threading.Event()
    monkeypatch.setitem(passes.RUNNERS, "learned-audit", lambda: gate.wait(10))
    client.post("/jobs/passes/learned-audit/run")
    _wait(lambda: passes.running("learned-audit"))
    # The learned audit's own row: another test's pass can still be listed in this worker (CI 31bac2a took a stoppable one).
    row = next(t for t in client.get("/tasks").json()["tasks"] if t["kind"] == "job-pass" and passes.kind_for_label(t["name"]) == "learned-audit")
    assert row["cancellable"] is False
    gate.set()


def test_the_autonomous_pass_keeps_its_own_switch(client):
    """Run now on the librarian still respects its master toggle (the
    reported "completed" notification for a pass that was switched off)."""
    body = client.post("/jobs/passes/autonomous/run").json()
    assert body["started"] is False
    assert "switched off" in body["message"]


def test_pass_jobs_have_a_lane():
    assert jobs.KIND_LANES["pass"] == "batch"
