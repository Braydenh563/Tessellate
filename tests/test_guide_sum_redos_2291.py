"""CodeQL 2291: `worked_sum`'s pattern had overlapping `\\W*`/`\\s*` runs at both
ends, so a long run of tabs backtracked polynomially. The answers stay the same."""

from __future__ import annotations

import time

import pytest

from tessellate.ai.guide_outside import worked_sum


@pytest.mark.parametrize("pad", ["\t", " ", "\t?", "?\t"])
def test_a_long_run_of_tabs_or_spaces_returns_at_once(pad):
    for text in (pad * 20000 + "x", "1+" + pad * 20000 + "x", "what is 1+1" + pad * 20000 + "x"):
        start = time.perf_counter()
        assert worked_sum(text) is None
        assert time.perf_counter() - start < 0.5


@pytest.mark.parametrize(
    "question, said",
    [
        ("what is 2+2", "2 + 2 is 4."),
        ("what's 12 x 3?", "12 × 3 is 36."),
        ("10/4", "10 ÷ 4 is 2.5."),
        ("  -5 + 2 ?! ", "-5 + 2 is -3."),
        ("\t¿calculate 3*4 =", "3 × 4 is 12."),
    ],
)
def test_sums_are_still_worked_out(question, said):
    assert worked_sum(question) == said


def test_a_division_by_zero_is_not_answered():
    assert worked_sum("4/0") is None
