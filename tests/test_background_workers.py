"""`core/background.py`: one registry of named workers with start, stop and status (decision 58)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tessellate.core import background


@pytest.fixture(autouse=True)
def _clean():
    background._workers.clear()
    yield
    background._workers.clear()


def test_register_lists_and_stop_all_signals_without_waiting():
    log = []
    background.register("a", stop=lambda: log.append("a"))
    background.register("b", stop=lambda: log.append("b"))
    assert {r["name"] for r in background.status() if r["running"]} == {"a", "b"}
    assert sorted(background.stop_all()) == ["a", "b"] and sorted(log) == ["a", "b"]
    assert background.stop_all() == []  # already stopped: not asked twice


def test_a_failing_stop_does_not_keep_the_others_from_stopping():
    log = []

    def boom():
        raise RuntimeError("stuck")

    background.register("bad", stop=boom)
    background.register("good", stop=lambda: log.append("good"))
    background.stop_all()
    assert log == ["good"]


def test_start_runs_only_a_stopped_worker_that_has_a_start():
    log = []
    background.register("w", stop=lambda: log.append("stop"), start=lambda: log.append("start"), running=False)
    assert background.start("w") is True and background.start("w") is False
    assert background.stop("w") is True and log == ["start", "stop"]
    assert background.start("missing") is False


def test_the_reminder_notifier_registers_and_stops_with_the_registry(monkeypatch, tmp_path):
    from tessellate.core import reminder_notifier

    monkeypatch.setattr(reminder_notifier, "pick_backend", lambda: "notify-send")
    monkeypatch.setattr(reminder_notifier.ReminderNotifier, "start", lambda self: self)
    notifier = reminder_notifier.start(Path(tmp_path))
    try:
        assert "reminder-notifier" in [r["name"] for r in background.status()]
        background.stop_all()
        assert notifier.stopped.is_set() and not reminder_notifier.active()
    finally:
        notifier.stop()

