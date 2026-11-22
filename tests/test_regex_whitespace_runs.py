"""A pattern that was quadratic in a long run of whitespace.

`followups._INLINE_SPLIT` (model output, split per line) let the regex engine
try every split of a whitespace run between adjacent `\\s` quantifiers or from
every position inside the run. (The second, `docexport._TABLE_RULE`, went with
the python-docx writer, Brief 42.) Measured before the rewrite, on 20,000
characters: see the numbers in the CHANGELOG line. The rewrites are linear and
must keep splitting and matching exactly as before.
"""

from __future__ import annotations

import time

import pytest

from tessellate.ai import followups

N = 20_000
BUDGET = 0.02  # seconds; the quadratic forms took 0.5 to 10 s


def _timed(fn):
    started = time.process_time()
    fn()
    return time.process_time() - started


@pytest.mark.parametrize(
    "text",
    [
        " " * N + "x",
        "a?" + " " * N,
        "What now?" + " " * N + "\t",
        "a" + (" " * 50 + "1") * (N // 51),
        "a" + " " * N + "12",
        "a" + (" " * 3 + "-") * (N // 4),
    ],
    ids=["spaces-then-x", "question-then-spaces", "tab-after-run", "digit-after-runs", "digits-no-marker", "many-dashes"],
)
def test_inline_split_is_linear_on_whitespace_runs(text):
    assert _timed(lambda: followups._INLINE_SPLIT.split(text)) < BUDGET


@pytest.mark.parametrize(
    ("line", "pieces"),
    [
        ("What did I note? When is it due?", ["What did I note?", "When is it due?"]),
        ("What did I note? 2) When is it due?", ["What did I note?", "2)", "When is it due?"]),
        ("a  1. b", ["a", "b"]),
        ("a - b * c • d", ["a", "b", "c", "d"]),
        ("ends with a question?   ", ["ends with a question?   "]),
        ("no split here", ["no split here"]),
        ("1) first 2. second", ["1) first", "second"]),
    ],
)
def test_inline_split_still_splits_the_same_lines(line, pieces):
    got = followups._INLINE_SPLIT.split(line)
    # The first case of the old behaviour is the reference; compare against the
    # unrewritten pattern so this pins "unchanged", not a guess at it.
    import re

    old = re.compile(r"(?<=\?)\s+(?=\S)|\s+(?:\d+[.)]|[-*•])\s+")
    assert got == old.split(line)


def test_the_rewrite_agrees_with_the_old_pattern_on_random_text():
    """A differential check over the characters that matter to each pattern."""
    import random
    import re

    old_split = re.compile(r"(?<=\?)\s+(?=\S)|\s+(?:\d+[.)]|[-*•])\s+")
    rng = random.Random(3)
    for _ in range(4000):
        text = "".join(rng.choice(" ?1.)-*•a\t|:\n") for _ in range(rng.randint(0, 24)))
        assert followups._INLINE_SPLIT.split(text) == old_split.split(text), repr(text)
