"""The shared simulated hour (W24, CI time 1109): an hour read back from the session folder is the hour a fresh run
gives, and a second asker does not simulate it again."""

from __future__ import annotations

import pytest

from tests import overlay_sim_1670 as sim


@pytest.fixture()
def folder(tmp_path, monkeypatch):
    monkeypatch.setenv(sim.CACHE_ENV, str(tmp_path))
    sim._plain_hour.cache_clear()
    yield tmp_path
    sim._plain_hour.cache_clear()


def test_a_cached_hour_equals_a_fresh_one(folder) -> None:
    fresh = sim._simulate("float", 3, 900.0, None, True, "masculine", True)
    first = sim.simulate("float", 3, 900.0)
    sim._plain_hour.cache_clear()  # a second worker: no memory, the file only
    second = sim.simulate("float", 3, 900.0)
    assert first == fresh
    assert second == fresh
    assert len(list(folder.glob("*.pkl"))) == 1


def test_the_second_asker_reads_the_file_and_does_not_compute(folder) -> None:
    calls = []

    def compute():
        calls.append(1)
        return {"a": [1, 2], "b": (3.5, "x")}

    assert sim.disk_memo(("k", 1), compute) == sim.disk_memo(("k", 1), compute)
    assert len(calls) == 1
    assert sim.disk_memo(("k", 2), compute) == {"a": [1, 2], "b": (3.5, "x")}
    assert len(calls) == 2


def test_without_the_folder_it_just_computes(monkeypatch) -> None:
    monkeypatch.delenv(sim.CACHE_ENV, raising=False)
    calls = []
    sim.disk_memo(("k",), lambda: calls.append(1))
    sim.disk_memo(("k",), lambda: calls.append(1))
    assert len(calls) == 2
