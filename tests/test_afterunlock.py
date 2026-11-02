"""Launch work waits for the first unlock (INBOX 1492, the owner's lag log:
`/auth/unlock` 5072 ms, `/models/status` 3743 ms): the unlock answer goes
before the search model, the speller, the housekeeping and the resumed jobs
start, and a launch with no password runs them at once as it always did."""

from __future__ import annotations

import threading

import pytest

from tessellate.core import afterunlock


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    monkeypatch.setattr(afterunlock, "SETTLE_SECONDS", 0)
    monkeypatch.setattr(afterunlock, "_state", {"armed": False, "fired": False})
    monkeypatch.setattr(afterunlock, "_pending", [])


def test_a_launch_with_no_password_runs_the_work_at_once():
    ran = []
    afterunlock.defer("a", lambda: ran.append("a"))
    assert ran == ["a"] and not afterunlock.armed()


def test_work_is_held_until_a_token_is_issued_and_then_runs_in_order():
    afterunlock.arm()
    ran, done = [], threading.Event()
    afterunlock.defer("a", lambda: ran.append("a"))
    afterunlock.defer("b", lambda: (ran.append("b"), done.set()))
    assert ran == [] and afterunlock.armed()
    afterunlock.fire()
    assert done.wait(2) and ran == ["a", "b"] and not afterunlock.armed()
    afterunlock.fire()  # a second unlock does nothing
    assert ran == ["a", "b"]


def test_a_piece_that_fails_does_not_stop_the_next():
    afterunlock.arm()
    done = threading.Event()

    def boom():
        raise RuntimeError("no")

    afterunlock.defer("boom", boom)
    afterunlock.defer("next", done.set)
    afterunlock.fire()
    assert done.wait(2)


def test_work_deferred_after_the_unlock_runs_at_once():
    afterunlock.arm()
    afterunlock.fire()
    ran = []
    afterunlock.defer("late", lambda: ran.append(1))
    assert ran == [1]


def test_every_token_issue_releases_the_work_and_the_launch_holds_it():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "src" / "tessellate"
    auth = (root / "api" / "routes_auth.py").read_text(encoding="utf-8")
    issue = auth[auth.index("def _issue_token()") :][:400]
    assert "afterunlock.fire()" in issue
    app = (root / "api" / "app.py").read_text(encoding="utf-8")
    for held in ('afterunlock.defer("search-warmup"', 'afterunlock.defer("resume-jobs"', 'afterunlock.defer("maintenance"'):
        assert held in app, held
    assert "afterunlock.arm()" in app
