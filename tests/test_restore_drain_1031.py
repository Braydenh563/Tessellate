"""A restore waits for the requests in flight (audit 1031 BK5; 1028 K19).

Restore paused the job runner (1028 K19) but disposed the engine while other
requests could still be mid-transaction on it. `get_session` now counts the
requests holding a session, a restore stops new ones and waits for the count
to reach zero, and one that cannot drain in time is refused (409) with the
notebook untouched."""

from __future__ import annotations

import threading
import time

from tessellate.api import routes_backups
from tessellate.core import deps
from tests._pool_wait import pool_idle


def _save(client, text):
    return client.post("/entries", json={"content": text}).json()


def test_a_session_is_counted_while_a_request_holds_it(app_state):
    assert deps.requests_in_flight() == 0
    gen = deps.get_session()
    next(gen)
    assert deps.requests_in_flight() == 1
    gen.close()
    assert deps.requests_in_flight() == 0


def test_draining_waits_for_the_request_to_finish(app_state):
    gen = deps.get_session()
    next(gen)
    threading.Timer(0.15, gen.close).start()
    started = time.monotonic()
    with deps.drained(deadline=5.0) as idle:
        assert idle is True
        assert deps.requests_in_flight() == 0
    assert time.monotonic() - started >= 0.1


def test_draining_gives_up_at_the_deadline_and_says_so(app_state):
    gen = deps.get_session()
    next(gen)
    try:
        with deps.drained(deadline=0.1) as idle:
            assert idle is False
    finally:
        gen.close()


def test_a_request_that_arrives_mid_restore_waits_for_it(app_state):
    order: list[str] = []
    ready = threading.Event()

    def late():
        ready.wait(5)
        gen = deps.get_session()
        next(gen)
        order.append("request")
        gen.close()

    thread = threading.Thread(target=late)
    thread.start()
    with deps.drained(deadline=1.0):
        ready.set()
        time.sleep(0.2)
        order.append("restore")
    thread.join(5)
    assert order == ["restore", "request"]


def test_a_restore_with_a_request_in_flight_is_refused_and_touches_nothing(client, monkeypatch):
    monkeypatch.setattr(routes_backups, "RESTORE_JOB_WAIT_SECONDS", 0.2)
    _save(client, "kept")
    name = client.post("/backups").json()["name"]
    _save(client, "after")
    disposed = []
    engine = deps.get_db().engine
    real = engine.dispose
    monkeypatch.setattr(engine, "dispose", lambda *a, **k: (disposed.append(1), real(*a, **k))[1], raising=False)
    holder = deps.get_session()
    next(holder)  # a request still mid-flight
    try:
        refused = client.post("/backups/restore", json={"name": name})
    finally:
        holder.close()
    assert refused.status_code == 409, refused.text
    assert "request" in refused.json()["detail"]
    assert disposed == []
    entries = client.get("/entries").json()
    assert sorted(e["content"] for e in entries) == ["after", "kept"]
    restored = client.post("/backups/restore", json={"name": name})
    assert restored.status_code == 200


def test_an_open_stream_that_holds_no_session_does_not_hold_a_restore(client, monkeypatch):
    """The unlock check's session closes when the handler returns, so a
    stream (the Tasks panel keeps `/jobs/stream` open a minute) is not a
    request in flight, and a restore under it goes ahead at once (E2E
    first-run restore sat at "Restoring…" for the whole wait, then 409)."""
    _save(client, "kept")
    name = client.post("/backups").json()["name"]
    # The note's filing and the backup run on the pool; a slow runner can still be at them, and a restore
    # rightly waits for the pool (CI, Python 3.13: 3.5 s). What is checked here is the stream alone.
    assert pool_idle()
    # No wait at all: a request still holding a session would refuse the restore (409), so a 200 proves the
    # stream did not hold it, whatever the runner's speed (a wall-clock bound flaked: 2.24 s, L-world-class-38).
    monkeypatch.setattr(routes_backups, "RESTORE_JOB_WAIT_SECONDS", 0.0)
    with client.stream("GET", "/jobs/stream?seconds=5") as stream:
        next(stream.iter_lines())
        assert deps.requests_in_flight() == 0
        restored = client.post("/backups/restore", json={"name": name})
        assert restored.status_code == 200, restored.text


def test_a_long_poll_behind_the_unlock_check_does_not_hold_a_restore(client, monkeypatch):
    """`/auth/lan-watch` waits half a minute in its handler; the unlock check
    in front of it read the password table and let go, so the restore does
    not wait it out (it sat at "Restoring…" and was refused, E2E first-run)."""
    from tessellate.api import routes_auth

    monkeypatch.setattr(routes_auth, "WATCH_SECONDS", 4.0)
    monkeypatch.setattr(routes_auth, "_require_this_computer", lambda request: None)
    _save(client, "kept")
    name = client.post("/backups").json()["name"]
    # As in the stream test above: the filing and backup may still be on the pool (CI, Python 3.11: 3.5 s),
    # and a restore rightly waits for it. What is checked here is the long poll alone.
    assert pool_idle()
    monkeypatch.setattr(routes_backups, "RESTORE_JOB_WAIT_SECONDS", 0.0)  # no wait: a held session would 409
    polled: list[int] = []
    poll = threading.Thread(target=lambda: polled.append(client.get("/auth/lan-watch?since=0").status_code))
    poll.start()
    time.sleep(0.5)
    restored = client.post("/backups/restore", json={"name": name})
    poll.join(10)
    assert polled == [200]
    assert restored.status_code == 200, restored.text
