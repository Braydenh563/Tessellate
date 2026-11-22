"""Restart now goes through start.bat on a Windows source install (L968)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import tessellate.__main__ as entry

ROOT = Path(__file__).resolve().parent.parent


def _win_source(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    calls = []

    class _Popen:
        def __init__(self, argv, **kwargs):
            calls.append((argv, kwargs))

    monkeypatch.setattr(subprocess, "Popen", _Popen)
    return calls


def test_a_desktop_restart_spawns_start_bat_with_the_pid(monkeypatch):
    calls = _win_source(monkeypatch)
    assert entry._spawn_desktop(False, restart_after=77) is not None
    argv, kwargs = calls[0]
    assert argv[:2] == ["cmd", "/c"] and argv[2].endswith("start.bat")
    assert argv[3:] == ["--desktop", "--restart-after", "77"]
    assert kwargs["creationflags"] == 0x00000010
    assert "-m" not in argv


def test_a_hidden_restart_has_no_console_window(monkeypatch):
    calls = _win_source(monkeypatch)
    entry._spawn_desktop(True, restart_after=5)
    assert calls[0][1]["creationflags"] == 0x08000000


def test_the_relaunch_argv_goes_through_start_bat_and_drops_unknown_flags(monkeypatch):
    _win_source(monkeypatch)
    monkeypatch.setattr(sys, "argv", ["x", "--desktop", "--hidden-relaunch", "--reinstall", "--odd"])
    argv = entry._relaunch_argv()
    assert argv[:2] == ["cmd", "/c"] and argv[2].endswith("start.bat")
    assert argv[3:] == ["--desktop", "--restart-after", str(os.getpid())]


def test_the_packaged_exe_and_other_systems_do_not_use_a_bat(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert entry._launcher_bat() is None
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    assert entry._launcher_bat() is None


def test_start_bat_forwards_the_restart_pid_to_the_app():
    text = (ROOT / "start.bat").read_text(encoding="utf-8")
    assert 'if /i "%~1"=="--restart-after"' in text
    assert text.count("!MM_RESTART_ARG!") == 2
    assert "-m tessellate --desktop !MM_RESTART_ARG!" in text
