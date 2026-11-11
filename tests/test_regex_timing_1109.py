"""Two composer regexes retried a line-long scan at every word: seconds on a long line (review 1109).

Measured before the fix, on the regexes alone: `_AFTER` 0.8 s at 20,000 characters and 5.3 s at 50,000
("for" then "w to w to ..." and a newline); `_PLANNED_FOR` 0.07 s and 0.44 s ("a planned for " repeated,
then a newline).
"""

from __future__ import annotations

import time

import pytest

from tessellate.ai import composer_money
from tessellate.ai import composer_digest_lines

LIMIT = 0.2


@pytest.mark.parametrize("size", [20_000, 50_000])
def test_a_long_clause_after_an_amount_is_read_in_linear_time(size):
    rest = " for " + "w to " * (size // 5) + "\nx"
    started = time.perf_counter()
    composer_money._after_what(rest)
    assert time.perf_counter() - started < LIMIT


@pytest.mark.parametrize("size", [20_000, 50_000])
def test_a_long_planned_line_is_read_in_linear_time(size):
    body = "a planned for " * (size // 14) + "\nx"
    started = time.perf_counter()
    composer_digest_lines._day_clause(body)
    assert time.perf_counter() - started < LIMIT


def test_ordinary_clauses_still_read():
    assert composer_money._after_what(" for groceries this week").group("what")
    assert composer_digest_lines._day_clause("Lisbon trip planned for May")
