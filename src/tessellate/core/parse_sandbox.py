"""Parse untrusted files in a child process with a time and memory limit
(L-world-class-321, SECURITY.md T19).

A crafted PDF, Word file or picture is the one input this app reads with
native code it did not write (pypdfium2's PDFium, markitdown's converters),
so a parser bug there used to run inside the server, beside the decrypted
notes and the session tokens. `call` runs the parser in a child instead: the
answer comes back as plain data (`core/parse_child.py`'s wire, never pickle),
a hang is killed at the deadline, a memory blow-up is refused by the child's
own ``RLIMIT_AS``, and a crash is a `ParseRefused` rather than the server's
death.

**One reused child, not one per call.** A cold child is ~25 ms of interpreter
plus the parser's import, and the rail draws a page thumbnail in ~7 ms, so a
child per call would have made 24 thumbnails cost seconds; one child serves
every call, one at a time (PDFium is not thread-safe, which is why
`core/pdfpages.py` held a lock before this existed: the lock here is that
lock). The child is replaced after a timeout, a crash, a memory refusal and
every `RECYCLE_AFTER` jobs, so one file's leftovers do not live for long.

**What this is not.** The child is the same user as the server, so it is
crash, hang and memory isolation, not a privilege boundary: it can still read
what the user can. Windows has no ``setrlimit``; there the wall-clock timeout
is the only limit (no job object, on purpose: one more native API to get
right for a limit the timeout already bounds in time).
"""

from __future__ import annotations

import logging
import os
import queue
import signal
import subprocess
import sys
import threading
from pathlib import Path

from tessellate.core import jobs, parse_child
from tessellate.core.subproc import NO_WINDOW

logger = logging.getLogger(__name__)

#: Address space for the child, in MB: a page at `pdfpages.MAX_PIXELS` is
#: 160 MB of bitmap before PNG, and markitdown with magika's model loaded
#: measured about 700 MB of address space reserved on Linux.
DEFAULT_MEMORY_MB = 2048
#: Seconds a job may take before its child is killed, when the caller does
#: not say. `core/pdfpages.py` and `entry/importer.py` pass their own.
DEFAULT_TIMEOUT = 60.0
#: A cold start reads the parser's own imports; a frozen build starts its
#: whole bundle first.
START_TIMEOUT = 30.0
RECYCLE_AFTER = 500

#: What a person reads. Sentence case, one line, whole on its own
#: (checked in tests/test_core_message_wording.py's SOURCES).
TOO_LONG = "That file took too long to read, so it was stopped."
TOO_BIG = "That file needed more memory than is allowed, so it was stopped."
CRASHED = "The reader stopped unexpectedly on that file."
UNREADABLE = "That file may be damaged or in a format that can't be read."
MESSAGES = {"timeout": TOO_LONG, "memory": TOO_BIG, "crashed": CRASHED, "failed": UNREADABLE}


class ParseRefused(RuntimeError):
    """A parse that did not produce an answer. `str()` is the sentence for a
    person; `kind` is one of `MESSAGES`; `detail` is the library's own words,
    for the log only."""

    def __init__(self, kind: str, detail: str = "") -> None:
        super().__init__(MESSAGES[kind])
        self.kind = kind
        self.detail = detail


_EOF = object()


def _command() -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, "--parse-child"]  # dispatched first thing in `__main__.main`
    return [sys.executable, "-m", "tessellate.core.parse_child"]


def _env() -> dict[str, str]:
    env = dict(os.environ)
    package_root = str(Path(__file__).resolve().parents[2])
    env["PYTHONPATH"] = os.pathsep.join(filter(None, [package_root, env.get("PYTHONPATH", "")]))
    # glibc gives every thread a 64 MB arena of address space: with a model's
    # thread pool that alone can pass RLIMIT_AS before a byte of the file is read.
    env.setdefault("MALLOC_ARENA_MAX", "2")
    return env


class _Child:
    def __init__(self, memory_mb: int) -> None:
        self.path = tuple(sys.path)
        self.jobs = 0
        self.proc = subprocess.Popen(  # noqa: S603  # our own interpreter and module
            _command(),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=_env(),
            creationflags=NO_WINDOW,
        )
        self.replies: queue.Queue = queue.Queue()
        jobs.thread("parse-sandbox-reader", self._pump, stop=self.kill)
        self.send({"path": list(self.path), "memory_mb": memory_mb})
        reply = self.wait(START_TIMEOUT)
        if not isinstance(reply, dict) or not reply.get("ok"):
            self.kill()
            raise ParseRefused("crashed", "the parser child did not start")

    def _pump(self) -> None:
        read = parse_child.reader(self.proc.stdout)
        while True:
            try:
                self.replies.put(parse_child.decode(read))
            except (EOFError, OSError, ValueError, UnicodeDecodeError):
                # EOF is the child gone; anything else is a frame that was not
                # one, which only a broken or compromised child sends.
                self.replies.put(_EOF)
                return

    def send(self, message: dict) -> None:
        self.proc.stdin.write(parse_child.encode(message))  # type: ignore[union-attr]
        self.proc.stdin.flush()  # type: ignore[union-attr]

    def wait(self, timeout: float):  # noqa: ANN201  # a reply dict, _EOF, or None on timeout
        try:
            return self.replies.get(timeout=timeout)
        except queue.Empty:
            return None

    def alive(self) -> bool:
        return self.proc.poll() is None

    def kill(self) -> None:
        if self.proc.poll() is None:
            self.proc.kill()
        try:
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            logger.warning("the parser child did not exit after being killed")
        for pipe in (self.proc.stdin, self.proc.stdout):
            try:
                pipe.close()  # type: ignore[union-attr]
            except OSError:
                pass  # already closed by the child's death


class Sandbox:
    """One child, reused, one job at a time. `default()` is the app's."""

    def __init__(self, memory_mb: int = DEFAULT_MEMORY_MB) -> None:
        self.memory_mb = memory_mb
        self._lock = threading.Lock()
        self._child: _Child | None = None

    def _ready(self) -> _Child:
        child = self._child
        if child is not None and (not child.alive() or child.path != tuple(sys.path) or child.jobs >= RECYCLE_AFTER):
            # An extra installed since the start changes `sys.path`; the child
            # must see what the server sees.
            child.kill()
            child = None
        if child is None:
            child = self._child = _Child(self.memory_mb)
        return child

    def _drop(self) -> None:
        if self._child is not None:
            self._child.kill()
            self._child = None

    def call(self, job: str, *args, timeout: float = DEFAULT_TIMEOUT, cpu_seconds: float | None = None):  # noqa: ANN002, ANN201
        """`module:function(*args)` in the child; its return value, or
        `ParseRefused`. `cpu_seconds` defaults to `timeout`."""
        with self._lock:
            child = self._ready()
            child.jobs += 1
            try:
                child.send({"job": job, "args": list(args), "cpu": cpu_seconds or timeout})
            except OSError:
                self._drop()
                raise ParseRefused("crashed", "the parser child had gone") from None
            reply = child.wait(timeout)
            if reply is None:
                self._drop()
                raise ParseRefused("timeout", f"{job} passed {timeout} s")
            if reply is _EOF:
                code = child.proc.wait(timeout=5) if child.alive() else child.proc.returncode
                self._drop()
                # SIGXCPU is the processor-time limit, which is a timeout to a person.
                kind = "timeout" if code == -getattr(signal, "SIGXCPU", 0) and code else "crashed"
                raise ParseRefused(kind, f"{job} ended the child with {code}")
            if not reply.get("ok"):
                kind = reply.get("kind") if reply.get("kind") in MESSAGES else "failed"
                if kind == "memory":
                    self._drop()
                raise ParseRefused(kind, str(reply.get("detail", ""))[:500])
            return reply.get("value")

    def close(self) -> None:
        with self._lock:
            self._drop()


_default: Sandbox | None = None
_default_lock = threading.Lock()


def default() -> Sandbox:
    global _default
    with _default_lock:
        if _default is None:
            _default = Sandbox()
        return _default


def call(job: str, *args, timeout: float = DEFAULT_TIMEOUT, cpu_seconds: float | None = None):  # noqa: ANN002, ANN201
    return default().call(job, *args, timeout=timeout, cpu_seconds=cpu_seconds)
