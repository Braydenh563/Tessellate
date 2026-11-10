"""Review 5850946759 (PR 216, automated): two lock tables that a caller without a session could disturb."""

from __future__ import annotations

import pytest

from tessellate.core import hellostore, spacelock


@pytest.fixture
def clock(monkeypatch):
    now = {"t": 1000.0}
    monkeypatch.setattr(spacelock, "_now", lambda: now["t"])
    monkeypatch.setattr(hellostore, "_now", lambda: now["t"])
    spacelock._opened.clear()
    hellostore._pending.clear()
    yield now
    spacelock._opened.clear()
    hellostore._pending.clear()


def test_a_request_without_a_token_never_opens_the_private_spaces(clock):
    spacelock.open_for(None)
    spacelock.open_for("")
    assert not spacelock.is_open(None) and not spacelock.is_open("")
    assert spacelock._opened == {}
    spacelock.open_for("tok-a")
    assert spacelock.is_open("tok-a") and not spacelock.is_open(None)


def test_stale_sessions_are_dropped_when_another_opens(clock):
    spacelock.open_for("old")
    clock["t"] += spacelock.idle_minutes() * 60 + 1
    spacelock.open_for("new")
    assert set(spacelock._opened) == {"new"}


def test_a_full_challenge_table_refuses_instead_of_evicting_a_live_ceremony(clock):
    first, _ = hellostore.issue("get")
    for _ in range(hellostore._MAX_PENDING - 1):
        hellostore.issue("get")
    with pytest.raises(hellostore.Busy):
        hellostore.issue("get")
    assert first in hellostore._pending  # the ceremony in progress keeps its challenge
    clock["t"] += hellostore.CHALLENGE_SECONDS + 1
    hellostore.issue("get")  # expired ones make room again
    assert first not in hellostore._pending
