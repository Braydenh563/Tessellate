"""The 1029 composer patterns stay linear on long runs of blanks (CodeQL,
polynomial regex on user input): `.+?\\s+` gave a run of n spaces n ways to
split, so 5,000 spaces took about half a second and 50,000 over a minute.
They now read single-spaced text with words joined by one space."""

import time

import pytest

from tessellate.ai.commands import _TO_THE_BIN
from tessellate.ai.task_acts import _ON_NOTE


@pytest.mark.parametrize(
    ("pattern", "text"),
    [
        (_ON_NOTE, "a" + " " * 50000 + "x"),
        (_ON_NOTE, "a on" * 20000),
        (_TO_THE_BIN, "move a" + " " * 50000 + "x"),
        (_TO_THE_BIN, "move " + "a to " * 20000),
    ],
)
def test_no_quadratic_match(pattern, text):
    start = time.perf_counter()
    pattern.match(text)
    assert time.perf_counter() - start < 0.2


def test_the_readings_still_hold():
    assert _ON_NOTE.match("charger on the Lisbon packing list").group("item") == "charger"
    assert _TO_THE_BIN.match("move the lentil soup note to the bin").group(1) == "the lentil soup note"
