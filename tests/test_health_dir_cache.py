"""INBOX 1426 L1: `/debug/health` took 10.9s the moment Settings opened. The
data folder's size walks every file under it; on a big folder that is seconds,
so the figure is cached, measured again off the request, and a first count
that runs long answers with what it has (`data_dir_bytes_partial`)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tessellate.api import routes_debug


class _Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def monotonic(self) -> float:
        return self.now


@pytest.fixture
def walk(monkeypatch):
    clock = _Clock()
    monkeypatch.setattr(routes_debug, "time", clock)
    monkeypatch.setitem(routes_debug._dir_cache, "bytes", None)
    monkeypatch.setitem(routes_debug._dir_cache, "walking", False)
    monkeypatch.setitem(routes_debug._dir_cache, "partial", False)
    monkeypatch.setitem(routes_debug._dir_cache, "path", "")
    monkeypatch.setitem(routes_debug._dir_cache, "at", 0.0)
    queued: list = []
    monkeypatch.setattr(routes_debug.jobs, "enqueue", lambda kind, func, *a, **k: queued.append((func, a)))
    state = {"calls": [], "size": 100, "slow": False}

    def fake(path, deadline=None):
        state["calls"].append(deadline)
        if state["slow"] and deadline is not None:
            return 7, False
        return state["size"], True

    monkeypatch.setattr(routes_debug, "_dir_bytes", fake)
    return clock, queued, state


def test_a_figure_under_the_ttl_is_not_measured_again(walk):
    clock, queued, state = walk
    folder = Path("/data")
    assert routes_debug._data_dir_size(folder) == (100, False)
    clock.now += routes_debug.DIR_BYTES_TTL - 1
    state["size"] = 999
    assert routes_debug._data_dir_size(folder) == (100, False)
    assert len(state["calls"]) == 1 and not queued


def test_a_stale_figure_is_served_and_measured_again_off_the_request(walk):
    clock, queued, state = walk
    folder = Path("/data")
    routes_debug._data_dir_size(folder)
    clock.now += routes_debug.DIR_BYTES_TTL + 1
    state["size"] = 250
    assert routes_debug._data_dir_size(folder) == (100, False)  # the old figure, at once
    assert len(state["calls"]) == 1 and len(queued) == 1
    # a second ask while that walk is out does not start another
    routes_debug._data_dir_size(folder)
    assert len(queued) == 1
    func, args = queued[0]
    func(*args)
    assert routes_debug._data_dir_size(folder) == (250, False)


def test_a_first_count_that_runs_long_answers_partial_and_finishes_behind(walk):
    clock, queued, state = walk
    state["slow"] = True
    folder = Path("/data")
    assert routes_debug._data_dir_size(folder) == (7, True)
    assert state["calls"][0] == clock.now + routes_debug.DIR_BYTES_FIRST_BUDGET
    assert len(queued) == 1
    assert routes_debug._data_dir_size(folder) == (7, True)  # still the partial one, no second inline walk
    assert len(state["calls"]) == 1
    func, args = queued[0]
    func(*args)
    assert routes_debug._data_dir_size(folder) == (100, False)
