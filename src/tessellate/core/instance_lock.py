"""One running server per data directory (the owner's decision: single
instance by default).

**Why.** A second double-click on the desktop app used to start a second
process on the same data directory: `create_app()` ran its migrations, its
singletons and its background work against the SQLite file the first copy
already had open, and only then did uvicorn fail to bind the port. Two
servers on one SQLite file is the exact shape `scratchpad/ui-sweeps/serve.sh`
records as producing `no such table` and `Could not refresh instance` 500s
hours later.

**The mechanism**, kept simple on purpose:

- A server that starts writes `instance.lock` into its data directory: its
  port, its pid, when it started, and a random token.
- A launch reads that file first. If the port answers `/health` as Tessellate,
  the notebook is already open: the launch asks the running server to bring
  its window forward (`POST /instance/focus`, carrying the token, which only
  someone who can read the data directory has), or, with the Advanced
  setting "Open a new window on each launch" on, opens a second window onto
  that same server. Never a second server.
- A lock whose port is silent is **stale** unless its process is still alive
  and inside its boot grace (a first launch still running its migrations),
  and a stale lock is simply taken over. A crash therefore costs nothing but
  one silent port check on the next launch.

Everything that decides is a pure function (`classify`, `decide`,
`find_running` with its probes passed in), so the rules are tested without a
server, a window or a launcher script (`tests/test_instance_lock.py`).

This module imports nothing heavy: `__main__` reads it before the window
opens, and the import cost there is measured (see `_run_server`'s docstring).
"""

from __future__ import annotations

import json
import logging
import os
import secrets
import sys
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

LOCK_NAME = "instance.lock"

#: How long a lock whose port does not answer yet still counts as a server
#: that is starting, while its process lives. A cold first start (migrations,
#: an embeddings warm-up) was measured in the tens of seconds; the desktop
#: window's own wait is 45s (`_wait_for_server_with_progress`). Past this, a
#: live pid with a silent port is taken to be a pid reused by something else.
BOOT_GRACE_SECONDS = 90.0


@dataclass(frozen=True)
class LockInfo:
    pid: int
    port: int
    token: str
    started: float


def lock_path(data_dir: str | os.PathLike[str]) -> Path:
    return Path(data_dir) / LOCK_NAME


def new_lock(port: int, *, pid: int | None = None, now: float | None = None) -> LockInfo:
    return LockInfo(
        pid=os.getpid() if pid is None else int(pid),
        port=int(port),
        token=secrets.token_urlsafe(24),
        started=time.time() if now is None else float(now),
    )


def read_lock(path: str | os.PathLike[str]) -> LockInfo | None:
    """The lock at `path`, or None when it is missing or not one of ours.

    Junk reads as no lock rather than raising: a half-written file from a
    crash, or anything else, must never stop the notebook opening.
    """
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        info = LockInfo(
            pid=int(raw["pid"]),
            port=int(raw["port"]),
            token=str(raw["token"]),
            started=float(raw["started"]),
        )
    except (OSError, ValueError, TypeError, KeyError):
        return None
    if not 1 <= info.port <= 65535 or not info.token:
        return None
    return info


def write_lock(path: str | os.PathLike[str], info: LockInfo) -> None:
    from tessellate.core.atomic_io import atomic_write_text

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(target, json.dumps(asdict(info)))


def classify(lock: LockInfo | None, *, answering: bool, pid_alive: bool, now: float) -> str:
    """"none", "live", "starting" or "stale"."""
    if lock is None:
        return "none"
    if answering:
        return "live"
    if pid_alive and now - lock.started < BOOT_GRACE_SECONDS:
        return "starting"
    return "stale"


def decide(state: str, *, new_window: bool) -> str:
    """What a launch does: "start" a server, "focus" the running window, or
    open a "new_window" onto the running server. Never a second server while
    one is live or starting."""
    if state in ("live", "starting"):
        return "new_window" if new_window else "focus"
    return "start"


def pid_alive(pid: int) -> bool:
    """Whether a process with this pid exists.

    **Not `os.kill(pid, 0)` on Windows**: there, `os.kill` with any signal
    other than the two console events calls `TerminateProcess`, so the probe
    would end the very process it asked about. `OpenProcess` plus
    `GetExitCodeProcess` asks without touching it.
    """
    if pid <= 0:
        return False
    if sys.platform == "win32":
        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(0x1000, False, pid)  # QUERY_LIMITED_INFORMATION
            if not handle:
                return False
            try:
                code = ctypes.c_ulong()
                if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                    return False
                return code.value == 259  # STILL_ACTIVE
            finally:
                kernel32.CloseHandle(handle)
        except Exception:  # noqa: BLE001 - a failed probe reads as "not alive"
            return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # it exists; it is simply not ours to signal
    except OSError:
        return False
    return True


def data_dir_id(path: str | os.PathLike[str]) -> str:
    """A short, stable name for one data directory, the same on both sides of
    a `/instance` comparison.

    The path is resolved first, so a symlink or a `..` cannot make one
    notebook look like two, and lower-cased on Windows, where `C:\\Notes` and
    `c:\\notes` are one folder. It is hashed so the open `GET /instance`
    route tells a caller whether it is the same notebook without handing
    anyone on the machine the folder's path (which carries the user name).
    """
    import hashlib

    key = str(Path(path).resolve())
    if sys.platform == "win32":
        key = key.casefold()
    return hashlib.sha256(key.encode("utf-8", "replace")).hexdigest()[:32]


def served_data_dir_id(port: int, host: str = "127.0.0.1", timeout: float = 2.0) -> str | None:
    """The data-directory id the server on `port` reports at `GET /instance`,
    or None when it does not say (an older build without the route, or a
    reply that is not the expected shape)."""
    try:
        with _opener().open(f"http://{host}:{port}/instance", timeout=timeout) as response:
            body = json.loads(response.read(4096).decode("utf-8", "replace"))
    except (OSError, ValueError):
        return None
    if isinstance(body, dict) and isinstance(body.get("data_dir_id"), str):
        return body["data_dir_id"]
    return None


def _opener():
    import urllib.request

    # No proxy: a system proxy setting must never be asked about loopback.
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


#: What `/health` and `/instance` call the app: the current name first, then
#: the name a server started before the rename to Tessellate still answers
#: with, so a launch after an update recognises the copy already running.
APP_NAMES = ("Tessellate", "MemoryMap AI")  # brand: keep


def instance_id(token: str) -> str:
    """A name for one running copy that is safe to say aloud: a hash of its
    private token, so `/health` can tell a caller *which* copy answered
    without ever handing out the token that `/instance/shutdown` takes."""
    import hashlib

    return hashlib.sha256(b"instance:" + token.encode("utf-8", "replace")).hexdigest()[:16]


def served_instance(port: int, host: str = "127.0.0.1", timeout: float = 1.5) -> str | None:
    """What answers `/health` on this port: None when nothing Tessellate does,
    "" when a copy does but names no instance (a build from before the id),
    otherwise the instance id it reports."""
    try:
        with _opener().open(f"http://{host}:{port}/health", timeout=timeout) as response:
            body = json.loads(response.read(4096).decode("utf-8", "replace"))
    except (OSError, ValueError):
        return None
    if not isinstance(body, dict) or body.get("app") not in APP_NAMES:
        return None
    named = body.get("instance")
    return named if isinstance(named, str) else ""


def answers(port: int, host: str = "127.0.0.1", timeout: float = 1.5) -> bool:
    """Whether Tessellate answers `/health` on this port."""
    return served_instance(port, host, timeout) is not None


def process_started(pid: int) -> float | None:
    """When the process `pid` began (epoch seconds), or None when it is gone or
    this platform will not say. Windows reuses a dead copy's pid for the next
    program that starts, so "a process with this pid exists" does not mean the
    copy that wrote the record is still there: its start time does."""
    if pid <= 0:
        return None
    try:
        if sys.platform == "win32":
            import ctypes
            import ctypes.wintypes

            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(0x1000, False, pid)  # QUERY_LIMITED_INFORMATION
            if not handle:
                return None
            try:
                created, ended, kernel, user = (ctypes.wintypes.FILETIME() for _ in range(4))
                if not kernel32.GetProcessTimes(handle, *(ctypes.byref(t) for t in (created, ended, kernel, user))):
                    return None
                ticks = (created.dwHighDateTime << 32) | created.dwLowDateTime  # 100 ns since 1601
                return ticks / 10_000_000 - 11_644_473_600
            finally:
                kernel32.CloseHandle(handle)
        if sys.platform.startswith("linux"):
            stat = Path(f"/proc/{int(pid)}/stat").read_text(encoding="utf-8", errors="replace")
            after_name = stat[stat.rindex(")") + 2 :].split()
            ticks = int(after_name[19])  # field 22, starttime, in clock ticks since boot
            boot = next(
                int(line.split()[1]) for line in Path("/proc/stat").read_text().splitlines() if line.startswith("btime ")
            )
            return boot + ticks / os.sysconf("SC_CLK_TCK")
    except Exception as exc:  # noqa: BLE001 - a probe that cannot tell reads as "unknown", never as "gone"
        logging.getLogger(__name__).debug("process start time unknown for pid %s: %s", pid, exc)
        return None
    return None


def find_running(
    data_dir: str | os.PathLike[str],
    *,
    answers_fn: Callable[[int], bool] | None = None,
    alive_fn: Callable[[int], bool] | None = None,
    now: float | None = None,
) -> tuple[str, LockInfo | None]:
    """The state of this data directory's lock, and the lock itself. The
    probes default to the real ones, looked up at call time so a test can
    replace either on the module."""
    lock = read_lock(lock_path(data_dir))
    if lock is None:
        return "none", None
    state = classify(
        lock,
        answering=(answers_fn or answers)(lock.port),
        pid_alive=(alive_fn or pid_alive)(lock.pid),
        now=time.time() if now is None else now,
    )
    return state, lock


def wait_until_answering(port: int, timeout: float = BOOT_GRACE_SECONDS) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if answers(port, timeout=1.0):
            return True
        time.sleep(0.5)
    return False


def request_focus(lock: LockInfo, host: str = "127.0.0.1", timeout: float = 3.0) -> bool:
    """Ask the running server to bring its window forward. True only when it
    did: a server started in browser mode has no window, and says so."""
    import urllib.request

    request = urllib.request.Request(
        f"http://{host}:{lock.port}/instance/focus",
        data=b"",
        method="POST",
        headers={"X-Instance-Token": lock.token},
    )
    try:
        with _opener().open(request, timeout=timeout) as response:
            body = json.loads(response.read(4096).decode("utf-8", "replace"))
    except (OSError, ValueError):
        return False
    return isinstance(body, dict) and body.get("focused") is True


def request_shutdown(port: int, token: str, host: str = "127.0.0.1", timeout: float = 3.0) -> bool:
    """Ask the copy on `port` to quit (`POST /instance/shutdown`, with that
    copy's token). True only when it said it is stopping."""
    import urllib.request

    request = urllib.request.Request(
        f"http://{host}:{port}/instance/shutdown",
        data=b"",
        method="POST",
        headers={"X-Instance-Token": token},
    )
    try:
        with _opener().open(request, timeout=timeout) as response:
            body = json.loads(response.read(4096).decode("utf-8", "replace"))
    except (OSError, ValueError):
        return False
    return isinstance(body, dict) and body.get("stopping") is True


# --- This process's own claim ------------------------------------------------
#
# The server that runs in this process needs the token (to check a focus
# request) and, on the desktop, a way to reach its window. Both are process
# state, set by `__main__` and read by the `/instance/focus` route.

_claimed: tuple[Path, LockInfo] | None = None
_focus_handler: Callable[[], None] | None = None


def claim(data_dir: str | os.PathLike[str], port: int) -> LockInfo:
    """Write this process's lock, replacing whatever was there. Called only
    once `find_running` said nothing live holds the directory, so what it
    replaces is a stale lock or none."""
    global _claimed
    info = new_lock(port)
    path = lock_path(data_dir)
    write_lock(path, info)
    _claimed = (path, info)
    _register_copy(info, data_dir)
    return info


def _register_copy(info: LockInfo, data_dir: str | os.PathLike[str]) -> None:
    """Also list this server for Settings, Running copies (core/
    run_records.py). A failure there never stops the notebook opening."""
    try:
        from tessellate.core import run_records

        run_records.register(
            run_records.Record(info.pid, info.port, info.token, info.started, str(data_dir))
        )
    except Exception as exc:  # noqa: BLE001 - the list is a convenience
        logging.getLogger(__name__).info(
            "running copies: this copy is not listed in Settings (%s); restart to try again", exc
        )


def release() -> None:
    """Remove this process's lock, and only if it is still ours: a later
    launch that took a stale-looking lock over owns the file now."""
    global _claimed
    if _claimed is None:
        return
    path, info = _claimed
    _claimed = None
    try:
        from tessellate.core import run_records

        run_records.unregister(info.pid, info.token)
    except Exception as exc:  # noqa: BLE001
        logging.getLogger(__name__).info(
            "running copies: record not removed (%s); the next listing prunes it", exc
        )
    current = read_lock(path)
    if current is not None and current.token == info.token:
        try:
            path.unlink()
        except OSError:
            pass  # gone already, or unwritable: the next launch finds it stale


def current_token() -> str | None:
    return _claimed[1].token if _claimed is not None else None


def current_instance_id() -> str:
    """This process's `instance_id`, or "" before it has claimed a lock."""
    return instance_id(_claimed[1].token) if _claimed is not None else ""


def set_focus_handler(handler: Callable[[], None] | None) -> None:
    global _focus_handler
    _focus_handler = handler


def focus() -> bool:
    """Bring this process's window forward, if it has one."""
    if _focus_handler is None:
        return False
    try:
        _focus_handler()
    except Exception:  # noqa: BLE001 - a failed focus must not fail the request
        return False
    return True
