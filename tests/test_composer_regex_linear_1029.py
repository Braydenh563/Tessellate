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


def test_define_and_command_readings_are_linear_and_hold():
    from tessellate.ai import composer, composer_digest

    for text in ("define " + "a " * 40000, "define" + " " * 50000 + "x", "the meaning of " + " " * 50000):
        start = time.perf_counter()
        composer.what_is(text)
        assert time.perf_counter() - start < 0.2
    start = time.perf_counter()
    composer._without_command("please " * 30000 + "move " + "to the " * 20000)
    composer_digest._one_name("tell me about " + " " * 50000 + "x", {"x"})
    assert time.perf_counter() - start < 0.5
    assert composer.what_is("Define sourdough  starter") == "what is sourdough starter"
    assert composer.what_is("the meaning of kombucha") == "what is kombucha"
    assert composer.what_is("define") == "define"
