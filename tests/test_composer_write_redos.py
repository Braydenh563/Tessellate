"""CodeQL 1880 to 1883: the Writing room's line patterns on user text must be linear.

A run of tabs after a bullet or heading marker made the old `(.*\\S)\\s*$` tail
backtrack polynomially; each public pass now takes 50,000 characters of it
inside a bound that the old patterns took minutes to meet.
"""

from __future__ import annotations

import time

import pytest

from tessellate.ai import composer_write as cw

N = 50_000
BOUND_S = 2.0

ADVERSARIAL = {
    "tabs": "\t\t" * (N // 2),
    "bullet then tabs": "*\t" * (N // 2),
    "bullet, tabs, text, tabs": "*" + "\t" * N + "x" + "\t" * N,
    "heading then tabs": "#" + "\t" * N + "\x0b",
    "numbered checkbox": "1." + "\t" * N + "[ ]" + "\t" * N,
    "spaced words": "a" + " \t" * (N // 2) + "b",
}
PASSES = [cw.sentences, cw.trim, cw.concise, cw.plain, cw.to_bullets, cw.to_prose, cw.plainly, cw.shorter, cw.summary_of, cw.with_summary]


@pytest.mark.parametrize("name", ADVERSARIAL)
def test_every_pass_is_linear_on_a_long_run_of_tabs(name):
    text = ADVERSARIAL[name]
    for fn in PASSES:
        started = time.perf_counter()
        fn(text)
        assert time.perf_counter() - started < BOUND_S, fn.__name__


def test_the_line_patterns_still_read_headings_bullets_and_checkboxes():
    assert cw._HEADING.match("  ## Plan  ").group(2) == "Plan"
    assert cw._HEADING.match("####### seven") is None
    found = cw._ITEM.match("  - [x] Buy milk \t")
    assert (found.group(1), found.group(2), found.group(4)) == ("  ", "-", "Buy milk")
    assert cw._ITEM.match("12) Call Sam").group(4) == "Call Sam"
    assert cw._ITEM.match("-") is None and cw._ITEM.match("- \t") is None
    assert cw._relist("  * keep  ", str.upper) == "  * KEEP"


def test_blank_text_has_no_sentences():
    assert cw.sentences("") == cw.sentences(" \t ") == []
