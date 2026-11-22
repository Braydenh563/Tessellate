"""Settings' Restart works in every way the app runs (INBOX 872).

The owner, 2026-10-11: "can you make sure the application restart works
both normally and on the windows application??", then "I restarted the app
with the button and it didnt restart??" and "or it took like 3 minutes?".
It worked only in the desktop app on Windows, and there it raced: the new
copy started while the old one still answered, read the notebook as open,
handed off to it and closed. Now every relaunch carries `--restart-after
<pid>` and the new copy waits for the old one to be gone first.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

import tessellate.__main__ as entry

ROOT = Path(__file__).resolve().parent.parent


def test_the_relaunch_carries_this_launch_but_not_repair_or_an_old_pid(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["memorymap", "--desktop", "--reinstall", "--restart-after", "12"])
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    argv = entry._relaunch_argv()
    assert argv[:3] == [sys.executable, "-m", "tessellate"]
    assert argv[3:] == ["--desktop", "--restart-after", str(os.getpid())]


def test_the_packaged_app_relaunches_itself_without_python_flags(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["Tessellate.exe", "--desktop"])
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert entry._relaunch_argv() == [sys.executable, "--desktop", "--restart-after", str(os.getpid())]


def test_every_windows_desktop_relaunch_waits_for_the_old_copy(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    calls = []

    class _Popen:
        def __init__(self, argv, **kwargs):
            calls.append(argv)

    monkeypatch.setattr(subprocess, "Popen", _Popen)
    assert entry._spawn_desktop(False, restart_after=4242) is not None
    assert calls == [[sys.executable, "--desktop", "--restart-after", "4242"]]


def test_waiting_ends_when_the_old_copy_is_gone(monkeypatch):
    gone = subprocess.Popen([sys.executable, "-c", "pass"])
    gone.wait()
    naps = []
    real_sleep = time.sleep
    monkeypatch.setattr(entry.time, "sleep", lambda s: (naps.append(s), real_sleep(s)))
    assert entry._wait_for_exit(gone.pid, timeout=5) is True
    assert naps == []  # counted (L-general-70): a copy already gone is not polled for


def test_the_route_restarts_any_launch_the_launcher_made(client, monkeypatch):
    import tessellate.__main__  # noqa: F401

    monkeypatch.setenv("TESSELLATE_LAUNCHED", "1")
    monkeypatch.delenv("TESSELLATE_DESKTOP", raising=False)
    calls = []
    monkeypatch.setattr("tessellate.__main__.restart_app", lambda: calls.append(True))
    restarted = client.post("/system/restart")
    assert restarted.json() == {"restarting": True}
    assert calls == [True]


def test_the_page_waits_for_the_new_copy_and_reloads():
    from tests._app_js import app_js_text

    app = app_js_text()
    body = app.split("async function waitForRestart()", 1)[1].split("\n}\n", 1)[0]
    assert "window.location.reload()" in body and "wentAway" in body
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert 'id="account-lan-restart"' in html


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _get(port, path):
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=3) as r:  # noqa: S310
        return json.loads(r.read() or b"null")


@pytest.mark.skipif(sys.platform == "win32", reason="the POSIX relaunch path; Windows' is the spawn tests above")
def test_a_browser_launch_restarts_for_real(tmp_path):
    """The real launcher, started as `start.sh` starts it: Restart ends that
    process and a new one answers on the same port, with the same notebook."""
    port = _free_port()
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src"), "TESSELLATE_DATA_DIR": str(tmp_path / "data"),
           "TESSELLATE_PORT": str(port), "NO_PROXY": "*"}
    env.pop("TESSELLATE_DESKTOP", None)
    first = subprocess.Popen([sys.executable, "-m", "tessellate"], env=env, cwd=ROOT,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    new_pid = None
    try:
        deadline = time.monotonic() + 60
        while True:
            try:
                _get(port, "/auth/status")
                break
            except OSError:
                assert time.monotonic() < deadline, "the first copy never answered"
                time.sleep(0.3)
        request = urllib.request.Request(f"http://127.0.0.1:{port}/system/restart", method="POST", data=b"")
        with urllib.request.urlopen(request, timeout=5) as r:  # noqa: S310
            assert json.loads(r.read()) == {"restarting": True}
        first.wait(timeout=20)
        deadline = time.monotonic() + 60
        while True:
            try:
                _get(port, "/auth/status")
                break
            except OSError:
                assert time.monotonic() < deadline, "the restarted copy never answered"
                time.sleep(0.3)
        from tessellate.core import instance_lock

        lock = instance_lock.read_lock(instance_lock.lock_path(tmp_path / "data"))
        new_pid = lock.pid if lock else None
        assert new_pid and new_pid != first.pid
    finally:
        if first.poll() is None:
            first.kill()
        if new_pid:
            try:
                os.kill(new_pid, 15)
            except OSError:
                pass  # already gone: nothing to stop
