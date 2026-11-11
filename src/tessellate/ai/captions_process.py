"""Run the live-captions helper as a local child process (Brief 82b, INBOX 1777).

The two Packages rows (`captions`, the pywhispercpp engine, and `captionmodel`,
the pinned model file) put the pieces on disk; this module starts
`ai/captions_helper.py` from them and nobody else does. It follows
`search/searxng_process.py`: a log file, `NO_WINDOW`, terminate on stop.

**Lazy.** Nothing starts at boot or from a status poll. The first
`captions.begin()` calls `ensure_started()`, which spawns the child, reads the
port it printed as its first stdout line (it binds port 0, so there is no
race), then polls `GET /` every 100 ms for up to `START_TIMEOUT` seconds (the
model loads in about 0.1 s for tiny.en, caption82-1010.md). Meanwhile the page
says "Starting captions…" (`starts_on_first_use` in the status).

**Crashes.** A child found dead is restarted on the next `ensure_started()`,
at most `MAX_RESTARTS` times in `RESTART_WINDOW` seconds; after that
`gave_up()` is true and the hint tells the person to reinstall.

**Stop.** `IDLE_STOP_SECONDS` after the last session ends, and at app
shutdown (the lifespan and `atexit`). The child also exits when its stdin
closes, so a hard-killed app does not leave it behind.

`TESSELLATE_CAPTIONS_URL` still wins: with it set nothing here runs.
"""

from __future__ import annotations

import atexit
import logging
import os
import queue
import subprocess  # noqa: S404  # fixed args, no shell
import sys
import threading
import time
from pathlib import Path

import requests

from tessellate.core import egress, extras, jobs
from tessellate.core.subproc import NO_WINDOW

logger = logging.getLogger("tessellate.captions")

#: Seconds, all of them. `clock` is replaced in the tests.
START_TIMEOUT = 15.0
POLL_SECONDS = 0.1
IDLE_STOP_SECONDS = 300.0
RESTART_WINDOW = 600.0
MAX_RESTARTS = 3

ENGINE_ID = "captions"
MODEL_ID = "captionmodel"

STOPPED_HINT = "The captions helper stopped. Reinstall Live captions in Settings, Packages."
NOT_STARTED_HINT = "The captions helper didn't start. Reinstall Live captions in Settings, Packages."

clock = time.monotonic
sleep = time.sleep


class HelperError(RuntimeError):
    """The helper could not be started; the message is a sentence for the person."""


_lock = threading.RLock()
_proc: subprocess.Popen | None = None
_port = 0
#: When the child was found dead or failed to start, newest last.
_crashes: list[float] = []
_idle_since: float | None = None
_timer: threading.Timer | None = None
#: True while a start is in progress, so the status can say "starting".
starting = False


def model_path() -> Path | None:
    """The installed model file, or None."""
    folder = extras.download_ready(MODEL_ID)
    return folder / extras.CAPTIONS_MODEL_FILE if folder else None


def installed() -> bool:
    """Both rows are there: the engine importable, the model on disk."""
    engine = extras.EXTRAS_BY_ID[ENGINE_ID]
    return extras.is_installed(engine) and model_path() is not None


def _alive() -> bool:
    return _proc is not None and _proc.poll() is None


def url() -> str:
    """The running helper's address, or "". Never starts anything, and never
    waits for `_lock`: a start holds it for seconds, and the status poll that
    asks this must still answer while the dock says "Starting captions"."""
    proc, port = _proc, _port
    return f"http://127.0.0.1:{port}" if proc is not None and proc.poll() is None and port else ""


def gave_up() -> bool:
    """Too many crashes in the window: stop trying until it passes or the
    person reinstalls. Lock-free for the same reason as `url`."""
    now = clock()
    return sum(1 for t in list(_crashes) if now - t < RESTART_WINDOW) > MAX_RESTARTS


def _note_crash() -> None:
    """Record a crash, forgetting the ones that aged out of the window."""
    now = clock()
    _crashes[:] = [t for t in _crashes if now - t < RESTART_WINDOW] + [now]


def _command(model: Path) -> list[str]:
    threads = max(1, min(4, (os.cpu_count() or 2) // 2))
    return [
        _python(),
        "-m",
        "tessellate.ai.captions_helper",
        "--model",
        str(model),
        "--threads",
        str(threads),
        "--exit-on-stdin-close",
    ]


def _python() -> str:
    if not getattr(sys, "frozen", False):
        return sys.executable
    return extras.find_system_python() or sys.executable


def _env() -> dict[str, str]:
    env = dict(os.environ)
    # A frozen app's extras live in a folder the child must see.
    frozen = extras.frozen_extras_dir()
    if frozen is not None:
        env["PYTHONPATH"] = os.pathsep.join(filter(None, [str(frozen), env.get("PYTHONPATH", "")]))
    return env


def _log_path() -> Path:
    from tessellate.core.config import ConfigManager

    return ConfigManager().data_dir / "logs" / "captions-helper.log"


def _read_port(proc: subprocess.Popen, deadline: float) -> int:
    """The child's first stdout line, as a port. A reader thread, so a child
    that prints nothing cannot hang the start."""
    lines: queue.Queue[str] = queue.Queue()

    def pump() -> None:
        try:
            for line in proc.stdout:  # type: ignore[union-attr]
                lines.put(line)
        except (OSError, ValueError):
            pass  # the pipe closed under us (child died or was stopped); the reader times out
        lines.put("")

    jobs.thread("captions-helper-stdout", pump)
    try:
        first = lines.get(timeout=max(0.1, deadline - clock()))
    except queue.Empty:
        return 0
    try:
        port = int(first.strip())
    except ValueError:
        return 0
    return port if 0 < port < 65536 else 0


@egress.labelled("Waiting for the live captions helper on this computer to start")
def _healthy(port: int) -> bool:
    session = requests.Session()
    session.trust_env = False  # never through a proxy: this is loopback
    try:
        return session.get(f"http://127.0.0.1:{port}/", timeout=1).status_code < 500
    except requests.RequestException:
        return False


def _spawn(model: Path) -> None:
    global _proc, _port
    log = _log_path()
    log.parent.mkdir(parents=True, exist_ok=True)
    handle = log.open("w", encoding="utf-8")  # truncated per start, like searxng's
    try:
        proc = subprocess.Popen(  # noqa: S603  # fixed args, no shell
            _command(model),
            stdin=subprocess.PIPE,  # held open: its closing tells the child we are gone
            stdout=subprocess.PIPE,
            stderr=handle,
            env=_env(),
            start_new_session=True,
            creationflags=NO_WINDOW,
            text=True,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        logger.warning("Couldn't start the captions helper: %s", type(exc).__name__)
        raise HelperError(NOT_STARTED_HINT) from exc
    finally:
        handle.close()
    _proc, _port = proc, 0
    deadline = clock() + START_TIMEOUT
    port = _read_port(proc, deadline)
    while port and clock() < deadline:
        if proc.poll() is not None:
            break
        if _healthy(port):
            _port = port
            return
        sleep(POLL_SECONDS)
    _kill()
    raise HelperError(NOT_STARTED_HINT)


def _kill() -> None:
    global _proc, _port
    proc, _proc, _port = _proc, None, 0
    if proc is None:
        return
    for pipe in (proc.stdin,):
        try:
            if pipe:
                pipe.close()
        except OSError:
            pass  # already closed by a dead child; nothing left to release
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=3)
    try:
        if proc.stdout:
            proc.stdout.close()
    except OSError:
        pass  # already closed by a dead child; nothing left to release


def ensure_started() -> str:
    """The helper's address, starting it if it is not running. Raises
    `HelperError` with a sentence. Called from `captions.begin()` only."""
    global starting
    with _lock:
        if _alive() and _port:
            cancel_idle()
            return url()
        if gave_up():
            raise HelperError(STOPPED_HINT)
        model = model_path()
        if model is None or not installed():
            raise HelperError("Install Live captions in Settings, Packages.")
        if _proc is not None:  # it was running and is not now: a crash
            _note_crash()
            _kill()
            if gave_up():
                raise HelperError(STOPPED_HINT)
        starting = True
        try:
            try:
                _spawn(model)
            except HelperError:
                _note_crash()
                raise
        finally:
            starting = False
        # Unregister first so repeated starts leave one exit hook, not one per start.
        atexit.unregister(stop)
        atexit.register(stop)
        cancel_idle()
        return url()


def session_ended(remaining: int) -> None:
    """A session ended; with none left, stop the helper after the idle wait."""
    global _idle_since, _timer
    if remaining or not _alive():
        return
    with _lock:
        _idle_since = clock()
        if _timer is not None:
            _timer.cancel()
        _timer = threading.Timer(IDLE_STOP_SECONDS, idle_check)
        _timer.daemon = True
        _timer.start()


def cancel_idle() -> None:
    global _idle_since, _timer
    with _lock:
        _idle_since = None
        if _timer is not None:
            _timer.cancel()
            _timer = None


def idle_check() -> bool:
    """Stop the helper if nobody has used it for the idle wait. True if it
    stopped. The timer calls this; the tests call it with a fixed clock."""
    with _lock:
        if _idle_since is None or clock() - _idle_since < IDLE_STOP_SECONDS:
            return False
        stop()
        return True


def stop() -> None:
    """Stop the helper now (Remove, shutdown, atexit). Safe to repeat."""
    with _lock:
        cancel_idle()
        _crashes.clear()
        _kill()


def reset_for_tests() -> None:
    global starting
    stop()
    starting = False


#: A reinstall or removal of the engine or the model replaces a file this helper holds open.
extras.on_release(extras.CAPTIONS_IDS, stop)
