"""Untrusted files are parsed in a child process with a time and memory limit.

SECURITY.md threat T19 (L-world-class-321): a crafted PDF, Word file or
picture was parsed inside the server process by pypdfium2, markitdown, Pillow
and the OCR readers, guarded by size caps only. A parser bug then ran with the
notebook's rights, and an endless loop or a runaway allocation in a C library
hung or killed the server for every tab.

`isolated(lane, timeout=...)` wraps a parse function so that a call from the
server runs it in a long-lived child process for that lane ("pdf",
"document", "ocr"), one call at a time:

* **Time**: a call that does not answer within its timeout has its child
  killed; the next call starts a fresh one. `ParseStopped` says so plainly.
* **Memory**: on POSIX the child caps its own address space
  (`RLIMIT_AS`, `MEMORY_BYTES`), so a huge allocation fails in the child,
  not in the server. Windows has the time limit only (L-world-class-690).
* **Crash**: a segfault or abort ends the child, never the server; the call
  raises `ParseStopped` and the next call starts a new child.

The child is spawned, not forked (a fork of a threaded server copies its
locks mid-use), and kept between calls so a page view does not pay a start-up
each time. The frozen Windows build starts it through
`multiprocessing.freeze_support()` in `__main__`.

`TESSELLATE_PARSE_INLINE=1` runs every call in-process: the test suite sets
it (its fake parsers live in `sys.modules`, which a child cannot see), and
`tests/test_parse_guard.py` clears it to prove the child does its job.
"""

from __future__ import annotations

import atexit
import functools
import importlib
import logging
import multiprocessing
import os
import pickle
import sys
import threading
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)

#: The child's address-space cap. Generous: RapidOCR's ONNX runtime and a
#: large scan's bitmap together reserve well over a gigabyte of address space,
#: and a cap that refuses honest files is worse than none.
MEMORY_BYTES = 4 * 1024**3

TIMED_OUT = "That file took too long to read, so reading it was stopped."
CRASHED = "That file stopped the reader. It may be damaged or made to break readers."
TOO_BIG = "That file needed more memory to read than is allowed, so reading it was stopped."

#: True inside a parse child: a wrapped function called there runs in place.
_in_child = False


class ParseStopped(RuntimeError):
    """The child timed out, ran out of memory or died. `sentence` is one of
    the three fixed sentences above, for a person."""

    def __init__(self, sentence: str) -> None:
        super().__init__(sentence)
        self.sentence = sentence


def enabled() -> bool:
    """Whether a wrapped call goes to a child process."""
    if _in_child:
        return False
    return os.environ.get("TESSELLATE_PARSE_INLINE", "").strip().lower() not in ("1", "true", "yes")


#: Win32: `LimitFlags` bit for a per-process commit cap, and the
#: `SetInformationJobObject` class that carries it.
JOB_OBJECT_LIMIT_PROCESS_MEMORY = 0x100
JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9

#: Kept for the life of the child: the cap belongs to the job object.
_job_handle: Any = None


def _limit_memory(limit: int) -> None:
    if sys.platform == "win32":
        _limit_memory_windows(limit)
        return
    try:
        import resource  # noqa: PLC0415  # POSIX only
    except ImportError:
        return
    try:
        resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
    except (ValueError, OSError):
        logger.info("couldn't cap the parse child's memory", exc_info=True)


def _limit_memory_windows(limit: int) -> None:
    """Windows has no RLIMIT_AS: the child puts itself in a job object with a
    per-process memory limit, so an allocation past it fails as a
    MemoryError, as on POSIX. Best effort, like the POSIX cap."""
    global _job_handle
    try:
        import ctypes  # noqa: PLC0415  # the Windows build only

        class BasicLimits(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", ctypes.c_int64),
                ("PerJobUserTimeLimit", ctypes.c_int64),
                ("LimitFlags", ctypes.c_uint32),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", ctypes.c_uint32),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", ctypes.c_uint32),
                ("SchedulingClass", ctypes.c_uint32),
            ]

        class IoCounters(ctypes.Structure):
            _fields_ = [(name, ctypes.c_uint64) for name in (
                "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                "ReadTransferCount", "WriteTransferCount", "OtherTransferCount",
            )]

        class ExtendedLimits(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", BasicLimits),
                ("IoInfo", IoCounters),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateJobObjectW.restype = ctypes.c_void_p
        kernel32.GetCurrentProcess.restype = ctypes.c_void_p
        job = kernel32.CreateJobObjectW(None, None)
        if not job:
            raise OSError("CreateJobObjectW failed")
        info = ExtendedLimits()
        info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_PROCESS_MEMORY
        info.ProcessMemoryLimit = limit
        if not kernel32.SetInformationJobObject(
            ctypes.c_void_p(job), JOB_OBJECT_EXTENDED_LIMIT_INFORMATION, ctypes.byref(info), ctypes.sizeof(info)
        ):
            raise OSError("SetInformationJobObject failed")
        if not kernel32.AssignProcessToJobObject(ctypes.c_void_p(job), ctypes.c_void_p(kernel32.GetCurrentProcess())):
            raise OSError("AssignProcessToJobObject failed")
        _job_handle = job
    except Exception:  # noqa: BLE001  # a missing cap must not stop the reader
        logger.info("couldn't cap the parse child's memory", exc_info=True)


def _serve(conn, memory: int) -> None:  # noqa: ANN001  # a multiprocessing Connection
    """The child's loop: one call in, one answer out, until the pipe closes."""
    global _in_child
    _in_child = True
    _limit_memory(memory)
    while True:
        try:
            module, name, args, kwargs = conn.recv()
        except (EOFError, OSError):
            return
        try:
            answer: tuple[str, Any] = ("ok", getattr(importlib.import_module(module), name)(*args, **kwargs))
        except MemoryError:
            answer = ("memory", None)
        except Exception as exc:  # noqa: BLE001  # handed back to the caller to raise
            try:
                pickle.dumps(exc)
                answer = ("error", exc)
            except Exception:  # noqa: BLE001  # an exception that will not travel
                answer = ("error", RuntimeError(f"{type(exc).__name__}: {exc}"))
        try:
            conn.send(answer)
        except Exception as exc:  # noqa: BLE001  # a result that will not pickle
            conn.send(("error", RuntimeError(f"the reader's answer could not be sent back: {exc}")))
        if answer[0] == "memory":
            return  # a process that hit its cap is not trusted with the next file


class _Worker:
    """One lane's child process, one call at a time."""

    def __init__(self, lane: str) -> None:
        self.lane = lane
        self.lock = threading.Lock()
        self.process = None
        self.conn = None

    def _start(self) -> None:
        ctx = multiprocessing.get_context("spawn")
        parent, child = ctx.Pipe()
        process = ctx.Process(target=_serve, args=(child, MEMORY_BYTES), daemon=True, name=f"tessellate-parse-{self.lane}")
        process.start()
        child.close()
        self.process, self.conn = process, parent

    def stop(self) -> None:
        process, conn = self.process, self.conn
        self.process = self.conn = None
        if conn is not None:
            conn.close()
        if process is not None:
            if process.is_alive():
                process.kill()
            process.join(5)

    def call(self, module: str, name: str, args: tuple, kwargs: dict, timeout: float) -> Any:
        with self.lock:
            if self.process is None or not self.process.is_alive():
                self.stop()
                self._start()
            try:
                self.conn.send((module, name, args, kwargs))
                if not self.conn.poll(timeout):
                    logger.warning("%s.%s ran past %.0f s: its reader was stopped", module, name, timeout)
                    self.stop()
                    raise ParseStopped(TIMED_OUT)
                status, payload = self.conn.recv()
            except (EOFError, OSError):
                code = self.process.exitcode if self.process is not None else None
                logger.warning("the %s reader died on %s.%s (exit %s)", self.lane, module, name, code)
                self.stop()
                raise ParseStopped(CRASHED) from None
        if status == "memory":
            with self.lock:
                self.stop()
            logger.warning("%s.%s hit the reader's memory cap", module, name)
            raise ParseStopped(TOO_BIG)
        if status == "error":
            raise payload
        return payload


_workers: dict[str, _Worker] = {}
_workers_lock = threading.Lock()


def _worker(lane: str) -> _Worker:
    with _workers_lock:
        if lane not in _workers:
            _workers[lane] = _Worker(lane)
        return _workers[lane]


def run(lane: str, fn: Callable, args: tuple = (), kwargs: dict | None = None, *, timeout: float) -> Any:
    """`fn(*args, **kwargs)` in `lane`'s child; `fn` must be importable by
    its module and name (a module-level function)."""
    return _worker(lane).call(fn.__module__, fn.__name__, tuple(args), dict(kwargs or {}), timeout)


def stop_all() -> None:
    """End every child (at exit, and between tests)."""
    with _workers_lock:
        workers = list(_workers.values())
        _workers.clear()
    for worker in workers:
        with worker.lock:
            worker.stop()


atexit.register(stop_all)


def isolated(
    lane: str, *, timeout: float, on_stop: Callable[[], Any] | None = None
) -> Callable[[Callable], Callable]:
    """Run the wrapped module-level function in `lane`'s child when
    `enabled()`, in place otherwise (and always inside the child itself).

    `on_stop` is for a function whose contract is "never raises" (a page
    count, an OCR reading): a stopped reader returns `on_stop()` instead of
    raising, logged above, the same answer the function gives a file it
    cannot read."""

    def wrap(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def inner(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
            if not enabled():
                return fn(*args, **kwargs)
            try:
                return _worker(lane).call(fn.__module__, fn.__name__, args, kwargs, timeout)
            except ParseStopped:
                if on_stop is None:
                    raise
                return on_stop()

        return inner

    return wrap
