"""LanguageTool as a second grammar opinion (INBOX 1731 (f)).

The program is an optional download (`extras.py`, id `languagetool`) that the
person installs from Settings, Packages; nothing here downloads. Once it is
installed, the first grammar check starts it as a child process listening on
127.0.0.1 only (its default: it is never started with `--public`), on a port
this app picked, and asks it over loopback. It is stopped after a quiet
spell and when the app exits. LGPL-2.1: it is run as a separate program,
never linked.

Spelling stays with the dictionary (the TYPOS category is switched off), so
this adds grammar and style findings only; the page merges them with
Harper's and drops a finding on a span Harper already has
(`frontend/js/documents-languagetool.js`).
"""

from __future__ import annotations

import atexit
import json
import logging
import os
import socket
import subprocess  # noqa: S404  # fixed args, no shell; see _start
import threading
import time
import urllib.parse
import urllib.request

from tessellate.core import egress, extras, jobs
from tessellate.core.languagetool_files import java_path
from tessellate.core.subproc import NO_WINDOW

log = logging.getLogger(__name__)

#: The English varieties the dictionary dialects name; anything else asks for en-US.
LANGUAGES = frozenset({"en-US", "en-GB", "en-AU", "en-CA", "en-NZ", "en-ZA"})
MAX_CHARS = 100_000
#: Seconds of quiet after which the program is stopped to give its memory back.
IDLE_STOP = 600.0
START_TIMEOUT = 60.0

_lock = threading.Lock()
_proc: subprocess.Popen | None = None
_port = 0
_timer: threading.Event | None = None  # set to cancel the idle countdown


def installed_folder():
    return extras.download_ready("languagetool")


def available() -> bool:
    return installed_folder() is not None and java_path() is not None


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _opener() -> urllib.request.OpenerDirector:
    """No proxy: this is loopback, and a system proxy must not see the text."""
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


@egress.labelled("Waiting for LanguageTool on this computer to start")
def _ready(port: int) -> bool:
    try:
        with _opener().open(f"http://127.0.0.1:{port}/v2/languages", timeout=2) as reply:
            return reply.status == 200
    except OSError:
        return False


def _start() -> int:
    """Start the program and wait until it answers; the port, or 0."""
    global _proc, _port
    folder, java = installed_folder(), java_path()
    if folder is None or java is None:
        return 0
    port = _free_port()
    command = [
        java, "-Xmx768m", "-cp", str(folder / "*") + os.pathsep + str(folder),
        "org.languagetool.server.HTTPServer", "--port", str(port),
    ]  # fmt: skip
    _proc = subprocess.Popen(  # noqa: S603  # fixed args, java found above
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=NO_WINDOW,
    )
    deadline = time.monotonic() + START_TIMEOUT
    while time.monotonic() < deadline:
        if _proc.poll() is not None:
            break
        if _ready(port):
            _port = port
            atexit.register(stop)
            return port
        time.sleep(0.3)
    stop()
    return 0


def stop() -> None:
    global _proc, _port, _timer
    with_lock = _lock.acquire(blocking=False)
    try:
        if _timer is not None:
            _timer.set()
            _timer = None
        if _proc is not None:
            _proc.terminate()
            try:
                _proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                _proc.kill()
        _proc, _port = None, 0
    finally:
        if with_lock:
            _lock.release()


def _arm_idle_stop() -> None:
    """Stop the checker after IDLE_STOP seconds unused, as a listed thread Job
    (`jobs.thread`) so the Tasks panel and a shutdown see it; each use re-arms."""
    global _timer
    if _timer is not None:
        _timer.set()
    cancelled = _timer = threading.Event()

    def wait_then_stop() -> None:
        if not cancelled.wait(IDLE_STOP):
            stop()

    jobs.thread("languagetool-idle", wait_then_stop, stop=cancelled.set)


def _running_port() -> int:
    if _proc is not None and _proc.poll() is None and _port:
        return _port
    return _start()


def _shape(match: dict, text: str) -> dict | None:
    start, length = match.get("offset"), match.get("length")
    if (
        not isinstance(start, int)
        or not isinstance(length, int)
        or length <= 0
        or start + length > len(text)
    ):
        return None
    rule = (match.get("rule") or {}).get("id") or ""
    suggestions = [
        r["value"] for r in (match.get("replacements") or [])[:5] if isinstance(r.get("value"), str)
    ]
    return {
        "start": start,
        "end": start + length,
        "message": str(match.get("message") or ""),
        "rule": str(rule),
        "suggestions": suggestions,
    }


@egress.labelled("Checking grammar with LanguageTool on this computer")
def check(text: str, language: str = "en-US") -> list[dict] | None:
    """Matches for the text, or None when it is not installed, will not
    start, or did not answer. Never raises: a missing second opinion is not
    an error."""
    if not text or len(text) > MAX_CHARS or not available():
        return None
    language = language if language in LANGUAGES else "en-US"
    body = urllib.parse.urlencode(
        {"language": language, "text": text, "disabledCategories": "TYPOS", "level": "default"}
    ).encode()
    try:
        with _lock:
            port = _running_port()
            if not port:
                return None
            _arm_idle_stop()
        request = urllib.request.Request(
            f"http://127.0.0.1:{port}/v2/check", data=body, method="POST"
        )  # noqa: S310  # loopback http
        with _opener().open(request, timeout=20) as reply:
            data = json.loads(reply.read().decode("utf-8"))
    except (OSError, ValueError) as exc:
        log.info("LanguageTool did not answer: %s", exc)
        return None
    shaped = (_shape(m, text) for m in data.get("matches") or [])
    return [m for m in shaped if m]
