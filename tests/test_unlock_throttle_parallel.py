"""Guesses in flight count against the unlock throttle (audit 1028 K3).

The check ran before bcrypt and the failure was counted after, so a guesser
that sent forty passwords at once had all forty pass a check that allows
five. An attempt let through is now held as pending until answered.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from tessellate.api import routes_auth


@pytest.fixture(autouse=True)
def _clean():
    routes_auth._clear_unlock_failures()
    yield
    routes_auth._clear_unlock_failures()


def test_parallel_attempts_past_the_allowance_are_refused_before_any_answer():
    allowed = 0
    for _ in range(40):
        try:
            routes_auth._refuse_if_throttled("10.0.0.9")
        except HTTPException as error:
            assert error.status_code == 429
            continue
        allowed += 1
    assert allowed == routes_auth._FAILURE_ALLOWANCE


def test_an_answered_attempt_frees_its_slot():
    for _ in range(3):
        routes_auth._refuse_if_throttled("10.0.0.9")
        routes_auth._unlock_succeeded("10.0.0.9")
    assert not routes_auth._pending_unlocks


def test_an_unanswered_attempt_expires(monkeypatch):
    routes_auth._refuse_if_throttled("10.0.0.9")
    later = routes_auth.time.time() + routes_auth._PENDING_TTL + 1
    monkeypatch.setattr(routes_auth.time, "time", lambda: later)
    routes_auth._refuse_if_throttled("10.0.0.8")
    assert "10.0.0.9" not in routes_auth._pending_unlocks
