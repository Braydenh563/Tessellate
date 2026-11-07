"""BACKLOG 1678 / INBOX 1683 l review (2026-11-07): the desk figure's screen reads follow the
"Roam over windows" switch, never block the frame thread on a folder, and say nothing for what
happened while the figure was away."""

from __future__ import annotations

from pathlib import Path

from tessellate.core.overlay import screenwatch

RUNNER = (Path(__file__).resolve().parents[1] / "src/tessellate/core/overlay/runner.py").read_text(encoding="utf-8")


def _watch(run=None):
    fg, files, reads = [10], [3], {"fg": 0, "files": 0}

    def foreground():
        reads["fg"] += 1
        return fg[0]

    def downloads():
        reads["files"] += 1
        return files[0]

    kw = {"run": run} if run is not None else {}
    return screenwatch.ScreenWatch(foreground=foreground, battery=lambda: (80, True), downloads=downloads, **kw), fg, files, reads


def test_with_roaming_off_neither_the_foreground_nor_the_folder_is_read_but_the_hour_still_is() -> None:
    w, _fg, _files, reads = _watch()
    assert w.poll(0.0, 9, 59, screen=False) == []
    assert w.poll(2.0, 10, 0, screen=False) == ["hour_chime"]
    assert reads == {"fg": 0, "files": 0}


def test_turning_roaming_back_on_says_nothing_for_what_changed_while_it_was_off() -> None:
    w, fg, files, _reads = _watch()
    w.poll(0.0, 9, 30)
    fg[0], files[0] = 11, 9
    w.poll(2.0, 9, 30, screen=False)
    assert w.poll(12.0, 9, 30) == [], "the first read after the switch is only remembered"
    fg[0], files[0] = 12, 10
    assert sorted(w.poll(24.0, 9, 30)) == ["app_switched", "download_done"]


def test_after_a_stall_the_first_poll_only_remembers() -> None:
    w, fg, files, _reads = _watch()
    w.poll(0.0, 9, 30)
    assert w.windows_seen([1, 2]) == []
    w.forget()
    fg[0], files[0] = 11, 9
    assert w.poll(12.0, 9, 30) == [] and w.windows_seen([1, 2, 3]) == []


def test_the_folder_is_counted_off_the_calling_thread_and_answered_on_a_later_poll() -> None:
    queued = []
    w, _fg, files, reads = _watch(run=queued.append)
    w.poll(0.0, 9, 30)
    assert reads["files"] == 0 and len(queued) == 1, "the count is handed to a worker, not run in the poll"
    queued.pop()()
    files[0] = 4
    w.poll(12.0, 9, 30)
    assert w.poll(14.0, 9, 30) == [], "a count still running is not started twice nor answered"
    assert len(queued) == 1
    queued.pop()()
    assert w.poll(16.0, 9, 30) == ["download_done"]


def test_the_runner_passes_the_switch_counts_on_a_worker_and_forgets_on_every_resume() -> None:
    assert "screen=self.roam_windows" in RUNNER
    assert 'jobs.thread("overlay-downloads"' in RUNNER
    assert RUNNER.count(".resume(now)") == 1, "every resume goes through the one helper"
    body = RUNNER.split("def _resume_engine", 1)[1].split("\n    def ", 1)[0]
    assert "self._watch.forget()" in body and ".resume(now)" in body
