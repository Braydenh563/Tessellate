"""Other copies of Tessellate running on this computer (INBOX 1641).

The owner, after "Port 8000 is already in use by another program": "the user
should be able to shutdown running instances from the settings".

`instance.lock` (core/instance_lock.py) is per data folder, so it cannot show a
copy that serves a different notebook. This is the per-user side of it: each
server that claims its lock also writes one small record, `<pid>.json`, into a
folder only this user can read (`%LOCALAPPDATA%\\Tessellate\\run` on Windows,
`$XDG_STATE_HOME/tessellate/run` elsewhere; `TESSELLATE_RUN_DIR` overrides it,
which the tests use). The record holds the pid, port, data folder, start time
and the same random token the copy's `/instance/focus` already takes.

- **Listing** prunes as it reads: a record whose pid is gone, or whose port no
  longer answers `/health` as Tessellate once the boot grace has passed, is
  deleted. A crash costs one stale file that the next list removes.
- **Shut down** asks the other copy over its own loopback route
  (`POST /instance/shutdown`, carrying the token). Nothing a web page can send
  carries the token, and the folder is private to this user, so another user's
  copy is never reachable. Only if that route does not answer (a build from
  before it existed, a hung server) is the pid ended, and only once it is
  verified to be this app: the port answers as Tessellate and the process's
  command line names it.

Pure functions with the probes passed in, so the rules are tested without a
second server (`tests/test_running_copies_1641.py`). Light imports only.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

from tessellate.core import instance_lock


@dataclass(frozen=True)
class Record:
    pid: int
    port: int
    token: str
    started: float
    data_dir: str = ""


@dataclass(frozen=True)
class Copy:
    pid: int
    port: int
    started: float
    data_dir: str
    this_copy: bool

    def public(self) -> dict:
        """What Settings sees. The token never leaves this module."""
        return asdict(self)


def run_dir() -> Path:
    override = os.environ.get("TESSELLATE_RUN_DIR")
    if override:
        return Path(override)
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "Tessellate" / "run"
    state = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return Path(state) / "tessellate" / "run"


def _path(pid: int) -> Path:
    return run_dir() / f"{int(pid)}.json"


def register(record: Record) -> None:
    from tessellate.core.atomic_io import atomic_write_text

    folder = run_dir()
    folder.mkdir(parents=True, exist_ok=True)
    if sys.platform != "win32":
        os.chmod(folder, 0o700)  # the files are 0600 already; the listing is private too
    atomic_write_text(_path(record.pid), json.dumps(asdict(record)))


def unregister(pid: int, token: str) -> None:
    """Remove a record, and only if it is still the one with this token."""
    current = _read(_path(pid))
    if current is not None and current.token == token:
        try:
            _path(pid).unlink()
        except OSError:
            pass


def _read(path: Path) -> Record | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        rec = Record(
            pid=int(raw["pid"]),
            port=int(raw["port"]),
            token=str(raw["token"]),
            started=float(raw["started"]),
            data_dir=str(raw.get("data_dir", "")),
        )
    except (OSError, ValueError, TypeError, KeyError):
        return None
    if not 1 <= rec.port <= 65535 or not rec.token or rec.pid <= 0:
        return None
    return rec


def _records(
    *,
    answers_fn: Callable[[int], bool] | None = None,
    alive_fn: Callable[[int], bool] | None = None,
    now: float | None = None,
) -> list[Record]:
    """The live records, with the stale ones deleted on the way."""
    answers_fn = answers_fn or instance_lock.answers
    alive_fn = alive_fn or instance_lock.pid_alive
    when = time.time() if now is None else now
    kept: list[Record] = []
    try:
        files = sorted(run_dir().glob("*.json"))
    except OSError:
        return kept
    for path in files:
        rec = _read(path)
        if rec is None:
            continue  # not ours to delete: junk reads as no record
        state = instance_lock.classify(
            instance_lock.LockInfo(rec.pid, rec.port, rec.token, rec.started),
            answering=answers_fn(rec.port),
            pid_alive=alive_fn(rec.pid),
            now=when,
        )
        if state == "stale":
            try:
                path.unlink()
            except OSError:
                pass
            continue
        kept.append(rec)
    return kept


def list_copies(
    *,
    own_pid: int | None = None,
    answers_fn: Callable[[int], bool] | None = None,
    alive_fn: Callable[[int], bool] | None = None,
    now: float | None = None,
) -> list[Copy]:
    me = os.getpid() if own_pid is None else own_pid
    return [
        Copy(r.pid, r.port, r.started, r.data_dir, r.pid == me)
        for r in _records(answers_fn=answers_fn, alive_fn=alive_fn, now=now)
    ]


def ask_to_stop(port: int, token: str) -> bool:
    """Ask the copy on `port` to quit. True only when it said it is stopping."""
    return instance_lock.request_shutdown(port, token)


def _command_line(pid: int) -> str:
    try:
        if sys.platform == "win32":
            out = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 f"(Get-CimInstance Win32_Process -Filter ProcessId={int(pid)}).CommandLine"],
                capture_output=True, text=True, timeout=10, check=False,
            ).stdout
            return out
        proc = Path(f"/proc/{int(pid)}/cmdline")
        if proc.exists():
            return proc.read_bytes().replace(b"\0", b" ").decode("utf-8", "replace")
        return subprocess.run(
            ["ps", "-p", str(int(pid)), "-o", "command="],
            capture_output=True, text=True, timeout=5, check=False,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def verify_is_this_app(pid: int, port: int) -> bool:
    """The pid is Tessellate: its port answers as Tessellate and its command
    line names the app. Either alone is not enough (a pid can be reused; a
    port can be anything)."""
    if not instance_lock.answers(port):
        return False
    line = _command_line(pid).lower()
    return "tessellate" in line or "memorymap" in line  # brand: keep


def terminate(pid: int) -> None:
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/PID", str(int(pid)), "/T", "/F"], capture_output=True, check=False)
        return
    import signal

    os.kill(int(pid), signal.SIGTERM)


def shutdown(
    pid: int,
    *,
    own_pid: int | None = None,
    ask_fn: Callable[[int, str], bool] | None = None,
    verify_fn: Callable[[int, int], bool] | None = None,
    kill_fn: Callable[[int], None] | None = None,
) -> str:
    """"stopping", "this-copy", "unknown" or "failed"."""
    me = os.getpid() if own_pid is None else own_pid
    if pid == me:
        return "this-copy"
    rec = _read(_path(pid))
    if rec is None:
        return "unknown"
    if (ask_fn or ask_to_stop)(rec.port, rec.token):
        return "stopping"
    if (verify_fn or verify_is_this_app)(rec.pid, rec.port):
        try:
            (kill_fn or terminate)(rec.pid)
        except OSError:
            return "failed"
        return "stopping"
    return "failed"
