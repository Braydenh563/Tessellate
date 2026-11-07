"""Composer round 3 (2026-11-07): the readers the round added are linear on
50,000-character runs (CodeQL polynomial ReDoS; same shape as test_redos_1107.py)."""

from __future__ import annotations

import time

import pytest

from tessellate.ai import composer_property

N = 50_000
BOUND_S = 2.0

RUNS = {
    "letters": "a" * N,
    "spaces": " " * N,
    "possessives": "x's " * (N // 4),
    "number of": "number of " * (N // 10),
    "number for": "number for the " * (N // 14),
    "apostrophes": "'" * N,
    "number then spaces": "what is the number" + " " * N + "!",
}

READERS = {
    "composer_property.asked": composer_property.asked,
    "composer_property.subject": composer_property.subject,
}


@pytest.mark.parametrize("run", RUNS)
@pytest.mark.parametrize("reader", READERS)
def test_each_reader_is_linear(reader, run):
    started = time.perf_counter()
    READERS[reader](RUNS[run])
    assert time.perf_counter() - started < BOUND_S, (reader, run)
