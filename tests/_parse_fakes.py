"""Crafted-file stand-ins for `tests/test_parse_guard.py`: parsers that loop,
allocate without end, crash the interpreter or fail, run through
`parse_guard.isolated` the way the real readers are. Module-level, so the
child process imports them by name."""

from __future__ import annotations

import os
import signal

from tessellate.core import parse_guard


@parse_guard.isolated("test", timeout=20)
def whose_process(value: str) -> tuple[int, str]:
    return os.getpid(), value


@parse_guard.isolated("test", timeout=1.5)
def loops_forever(path: str) -> str:
    while True:
        pass


@parse_guard.isolated("test", timeout=20)
def allocates(size: int) -> int:
    return len(bytearray(size))


@parse_guard.isolated("test", timeout=20)
def crashes() -> None:
    os.kill(os.getpid(), signal.SIGSEGV)


@parse_guard.isolated("test", timeout=20)
def fails() -> None:
    raise ValueError("not a real document")


@parse_guard.isolated("test", timeout=1.5, on_stop=list)
def pages_forever(path: str) -> list[bytes]:
    while True:
        pass


@parse_guard.isolated("document", timeout=1.5)
def convert_forever(path) -> str:  # noqa: ANN001
    while True:
        pass
