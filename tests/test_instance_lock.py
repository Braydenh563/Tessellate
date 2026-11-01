"""Single instance by default (the owner's decision B).

Launching the desktop app while it is already running on the same data
directory must bring the running window forward rather than start a second
server on the same SQLite file. The mechanism is a lock file in the data
directory naming the running server's port, pid and a token, plus a health
check of that port; a lock whose server does not answer and whose process is
gone (or whose boot grace has run out) is stale and is taken over.

Everything that decides is a pure function here, tested without a server,
a window or a launcher script. Nothing in this file runs `start.sh`,
`start.bat` or `python -m tessellate` (CLAUDE.md's trap about scripts that can
delete things).
"""

from __future__ import annotations

import json
import os
import sys
import pytest

from fastapi.testclient import TestClient

from tessellate.core import instance_lock as il



@pytest.fixture(autouse=True)
def _no_reminder_notifier(monkeypatch):
    """`_run_desktop` starts the reminder notifier; a test of the window must
    not post a real notification or leave a thread polling another test's
    database."""
    from tessellate.core import reminder_notifier

    monkeypatch.setattr(reminder_notifier, "pick_backend", lambda: None)

def test_the_lock_lives_in_the_data_dir(tmp_path):
    assert il.lock_path(tmp_path) == tmp_path / "instance.lock"


def test_a_written_lock_reads_back(tmp_path):
    info = il.new_lock(8123, pid=4242, now=1000.0)
    il.write_lock(il.lock_path(tmp_path), info)
    read = il.read_lock(il.lock_path(tmp_path))
    assert read == info
    assert read.port == 8123 and read.pid == 4242 and read.started == 1000.0
    assert len(read.token) >= 16


def test_two_locks_never_share_a_token():
    assert il.new_lock(8000).token != il.new_lock(8000).token


def test_a_missing_or_junk_lock_reads_as_none(tmp_path):
    path = il.lock_path(tmp_path)
    assert il.read_lock(path) is None
    path.write_text("not json", encoding="utf-8")
    assert il.read_lock(path) is None
    path.write_text(json.dumps({"pid": "x", "port": 8000}), encoding="utf-8")
    assert il.read_lock(path) is None
    path.write_text(json.dumps({"pid": 1, "port": 99999, "token": "t", "started": 0}), encoding="utf-8")
    assert il.read_lock(path) is None


def test_classify_no_lock():
    assert il.classify(None, answering=False, pid_alive=False, now=0) == "none"


def test_classify_a_lock_whose_server_answers_is_live():
    lock = il.new_lock(8000, pid=1, now=0)
    assert il.classify(lock, answering=True, pid_alive=False, now=10_000) == "live"


def test_classify_a_lock_still_booting_is_starting():
    lock = il.new_lock(8000, pid=1, now=100.0)
    now = 100.0 + il.BOOT_GRACE_SECONDS - 1
    assert il.classify(lock, answering=False, pid_alive=True, now=now) == "starting"


def test_classify_a_dead_process_is_stale():
    lock = il.new_lock(8000, pid=1, now=100.0)
    assert il.classify(lock, answering=False, pid_alive=False, now=101.0) == "stale"


def test_classify_a_live_pid_past_its_boot_grace_is_stale():
    """A pid reused by some other program after a crash must not hold the
    notebook shut forever: past the grace, a silent port means stale."""
    lock = il.new_lock(8000, pid=1, now=100.0)
    now = 100.0 + il.BOOT_GRACE_SECONDS + 1
    assert il.classify(lock, answering=False, pid_alive=True, now=now) == "stale"


def test_decide_starts_a_server_only_when_nothing_is_running():
    assert il.decide("none", new_window=False) == "start"
    assert il.decide("stale", new_window=False) == "start"
    assert il.decide("stale", new_window=True) == "start"


def test_decide_focuses_by_default_and_opens_a_window_when_asked():
    assert il.decide("live", new_window=False) == "focus"
    assert il.decide("starting", new_window=False) == "focus"
    assert il.decide("live", new_window=True) == "new_window"
    assert il.decide("starting", new_window=True) == "new_window"


def test_a_stale_lock_is_taken_over(tmp_path):
    path = il.lock_path(tmp_path)
    old = il.new_lock(8000, pid=999_999, now=0.0)
    il.write_lock(path, old)
    mine = il.claim(tmp_path, 8001)
    try:
        assert il.read_lock(path) == mine
        assert mine.pid == os.getpid() and mine.port == 8001
        assert il.current_token() == mine.token
    finally:
        il.release()
    assert il.read_lock(path) is None


def test_release_never_removes_another_instances_lock(tmp_path):
    il.claim(tmp_path, 8000)
    theirs = il.new_lock(8002, pid=1, now=0.0)
    il.write_lock(il.lock_path(tmp_path), theirs)
    il.release()
    assert il.read_lock(il.lock_path(tmp_path)) == theirs


def test_find_running_reports_a_live_lock(tmp_path):
    lock = il.new_lock(8000, pid=1, now=0.0)
    il.write_lock(il.lock_path(tmp_path), lock)
    state, found = il.find_running(tmp_path, answers_fn=lambda port: port == 8000, alive_fn=lambda pid: False)
    assert state == "live" and found == lock


def test_find_running_treats_a_silent_dead_lock_as_stale(tmp_path):
    il.write_lock(il.lock_path(tmp_path), il.new_lock(8000, pid=1, now=0.0))
    state, _ = il.find_running(tmp_path, answers_fn=lambda port: False, alive_fn=lambda pid: False)
    assert state == "stale"


def test_our_own_pid_is_alive_and_a_nonsense_one_is_not():
    assert il.pid_alive(os.getpid()) is True
    assert il.pid_alive(0) is False
    assert il.pid_alive(-5) is False


def test_the_new_window_setting_defaults_to_off(client):
    assert client.get("/preferences").json()["new_window_on_launch"] is False
    client.put("/preferences", json={"new_window_on_launch": True})
    assert client.get("/preferences").json()["new_window_on_launch"] is True


def test_the_focus_route_needs_the_lock_token(app_state, tmp_path):
    from tessellate.api.app import create_app

    focused = []
    il.claim(tmp_path, 8000)
    il.set_focus_handler(lambda: focused.append(True))
    try:
        client = TestClient(create_app())
        assert client.post("/instance/focus").status_code == 403
        assert client.post("/instance/focus", headers={"X-Instance-Token": "wrong"}).status_code == 403
        assert focused == []
        response = client.post("/instance/focus", headers={"X-Instance-Token": il.current_token()})
        assert response.status_code == 200 and response.json() == {"focused": True}
        assert focused == [True]
    finally:
        il.set_focus_handler(None)
        il.release()


def test_the_focus_route_says_when_there_is_no_window(app_state, tmp_path):
    """A server started in browser mode has no window to bring forward; the
    second launch is then told so and opens a window onto it instead."""
    from tessellate.api.app import create_app

    il.claim(tmp_path, 8000)
    try:
        client = TestClient(create_app())
        response = client.post("/instance/focus", headers={"X-Instance-Token": il.current_token()})
        assert response.status_code == 200 and response.json() == {"focused": False}
    finally:
        il.release()


def test_the_focus_route_refuses_when_nothing_was_claimed(app_state):
    from tessellate.api.app import create_app

    il.release()
    client = TestClient(create_app())
    assert client.post("/instance/focus", headers={"X-Instance-Token": ""}).status_code == 403


# --- The desktop launcher, wired to the lock ----------------------------------
#
# `_run_desktop` is driven with the same fake pywebview the launcher's own
# tests use, and with the probes replaced, so nothing here opens a socket to a
# real server or starts one.

import tessellate.__main__ as launcher  # noqa: E402
from tests.test_desktop_launcher import _fake_webview  # noqa: E402


def _running_lock(tmp_path, monkeypatch, port=8765):
    monkeypatch.setenv("TESSELLATE_DATA_DIR", str(tmp_path))
    lock = il.new_lock(port, pid=1, now=0.0)
    il.write_lock(il.lock_path(tmp_path), lock)
    monkeypatch.setattr(il, "answers", lambda p, host="127.0.0.1", timeout=1.5: p == port)
    monkeypatch.setattr(il, "pid_alive", lambda pid: False)
    started = []
    monkeypatch.setattr(launcher, "_run_server", lambda: started.append(True))
    return lock, started


def test_a_second_launch_focuses_the_running_window(monkeypatch, tmp_path):
    lock, started = _running_lock(tmp_path, monkeypatch)
    asked = []
    monkeypatch.setattr(il, "request_focus", lambda found, **k: asked.append(found) or True)
    calls = _fake_webview(monkeypatch)

    launcher._run_desktop()

    assert asked == [lock]
    assert calls["create_window"] is None, "a second window opened although the first was focused"
    assert started == [], "a second server started on the same data directory"


def test_a_second_launch_opens_a_window_onto_a_windowless_server(monkeypatch, tmp_path):
    """A server started in browser mode has no window to bring forward."""
    lock, started = _running_lock(tmp_path, monkeypatch)
    monkeypatch.setattr(il, "request_focus", lambda found, **k: False)
    calls = _fake_webview(monkeypatch, run_start_func=True)

    launcher._run_desktop()

    assert calls["create_window"]["url"] == f"http://{launcher.HOST}:{lock.port}"
    assert started == []


def test_the_new_window_setting_opens_another_window_onto_the_same_server(monkeypatch, tmp_path):
    from tessellate.core.config import ConfigManager

    lock, started = _running_lock(tmp_path, monkeypatch)
    ConfigManager(str(tmp_path)).set_preference("new_window_on_launch", True)
    asked = []
    monkeypatch.setattr(il, "request_focus", lambda found, **k: asked.append(found) or True)
    calls = _fake_webview(monkeypatch, run_start_func=True)

    launcher._run_desktop()

    assert asked == [], "the running window was focused although a new window was asked for"
    assert calls["create_window"]["url"] == f"http://{launcher.HOST}:{lock.port}"
    assert started == [], "the new window started a server of its own"


def test_a_stale_lock_launches_normally_and_is_replaced(monkeypatch, tmp_path):
    monkeypatch.setenv("TESSELLATE_DATA_DIR", str(tmp_path))
    il.write_lock(il.lock_path(tmp_path), il.new_lock(8765, pid=1, now=0.0))
    monkeypatch.setattr(il, "answers", lambda p, host="127.0.0.1", timeout=1.5: False)
    monkeypatch.setattr(il, "pid_alive", lambda pid: False)
    started = []
    monkeypatch.setattr(launcher, "_run_server", lambda: started.append(True))
    monkeypatch.setattr(launcher, "_wait_for_server_with_progress", lambda window, timeout=45.0: True)
    monkeypatch.setattr(launcher, "_desktop_port", lambda: launcher.PORT)
    seen = {}

    def _record_claim(*args, **kwargs):
        seen["lock"] = il.read_lock(il.lock_path(tmp_path))
        return None

    calls = _fake_webview(monkeypatch, run_start_func=True)
    original_start = sys.modules["webview"].start

    def start(func=None, args=None, **kwargs):
        original_start(func, args, **kwargs)
        _record_claim()

    sys.modules["webview"].start = start

    launcher._run_desktop()

    assert calls["create_window"]["html"], "the normal launch opens on the loading page"
    assert seen["lock"] is not None and seen["lock"].pid == os.getpid(), "the stale lock was not taken over"
    assert seen["lock"].port == launcher.PORT
    # Released when the window closed.
    assert il.read_lock(il.lock_path(tmp_path)) is None


def test_every_abrupt_exit_lets_go_of_the_lock(tmp_path, monkeypatch):
    """Quit, Restart and the console-mode switch end the process with
    `os._exit` or an exec, which skip `_run_desktop`'s `finally`; each calls
    `_stop_background_work` first, so that is where the lock goes. Left
    behind, it named a dead pid that Windows soon reuses, and a restart's
    new process could read the dying server as live."""
    from tessellate import __main__ as launcher
    from tessellate.core import jobs

    monkeypatch.setattr(jobs, "stop_all", lambda *a, **k: None)
    il.claim(tmp_path, 8123)
    try:
        launcher._stop_background_work()
        left = il.lock_path(tmp_path).exists()
        assert left is False
    finally:
        il.release()



def test_the_lock_is_claimed_before_the_window_shows(monkeypatch, tmp_path):
    """Two quick double-clicks: the second must find the first's lock. The
    claim used to happen in `_boot_and_swap`, after the window was on screen
    and a second of imports later, so both launches read "none" and both
    started a server on one data directory. It now happens before the
    window exists."""
    monkeypatch.setenv("TESSELLATE_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(launcher, "_run_server", lambda: None)
    monkeypatch.setattr(launcher, "_desktop_port", lambda: 8765)
    monkeypatch.setattr(launcher, "PORT", 8000)
    seen = {}
    calls = _fake_webview(monkeypatch)
    real_create = sys.modules["webview"].create_window

    def create_window(*args, **kwargs):
        seen["lock"] = il.read_lock(il.lock_path(tmp_path))
        return real_create(*args, **kwargs)

    sys.modules["webview"].create_window = create_window

    launcher._run_desktop()

    assert calls["create_window"] is not None
    assert seen["lock"] is not None, "no lock existed when the window opened"
    assert seen["lock"].pid == os.getpid() and seen["lock"].port == 8765
    assert launcher.PORT == 8765, "the lock names a port the server does not use"
    assert os.environ["TESSELLATE_PORT"] == "8765"
    assert il.read_lock(il.lock_path(tmp_path)) is None, "released when the window closed"


def test_boot_and_swap_no_longer_claims_the_lock():
    import inspect

    body = inspect.getsource(launcher._boot_and_swap)
    assert "instance_lock.claim" not in body and "_desktop_port()" not in body
