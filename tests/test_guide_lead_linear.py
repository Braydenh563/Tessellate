"""CodeQL 2296 (PR 230): `_PLACE_LAST` in ai/guide_lead.py backtracked on runs
of tabs (`\s*\W*` overlap after a bounded `.{2,40}`). Measured as a growth
ratio, not a wall time: eight times the input must cost well under 64 times
the time a quadratic match would."""

from __future__ import annotations

import time

from tessellate.ai import guide_lead


def _cost(n: int) -> float:
    text = "where do my notes go" + "\t" * n + "a"
    best = float("inf")
    for _ in range(3):
        t = time.perf_counter()
        guide_lead.place_last(text)
        best = min(best, time.perf_counter() - t)
    return best


def test_place_last_is_linear_on_runs_of_tabs() -> None:
    small, large = _cost(2_000), _cost(16_000)
    assert large < max(small, 1e-4) * 20, (small, large)


def test_place_last_still_reads_its_questions() -> None:
    assert guide_lead.place_last("Where do my notifications go?")
    assert guide_lead.place_last("where is my data stored")
    assert not guide_lead.place_last("where is the tag manager")
