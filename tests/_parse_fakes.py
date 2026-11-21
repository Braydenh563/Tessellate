"""Fake parsers for `tests/test_parse_sandbox.py`, run inside the sandbox's
child process (imported there by name, so they live in a module of their own,
not in the test file)."""

from __future__ import annotations

import os
import time


def echo(*args):  # noqa: ANN002, ANN201  # whatever the wire carries comes back
    return list(args)


def hang() -> None:
    time.sleep(3600)


def spin() -> None:
    while True:
        pass


def blow_up() -> bytes:
    return bytes(8 * 1024 * 1024 * 1024)


def crash() -> None:
    os.abort()


def fail() -> None:
    raise ValueError("not a PDF at all")


def chatter() -> str:
    print("a parser that prints to stdout")
    return "still read"


def pid() -> int:
    return os.getpid()
