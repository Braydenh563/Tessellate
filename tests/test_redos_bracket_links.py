"""The Python bracket-link scanners cannot be frozen by a long unclosed run (L-world-class-53).

`[^\\]]*` before a literal `]` (and `[^)]*` before `)`) rescans to the end of the
text from every `[`, so a run of `[`, `![` or `[a](` costs the square of its length
(measured at 20,000 characters: 5 to 11 s in `study._LINK`, `composer_extra._LINKED`).
Each scanner now bounds its text at 300 and its address at 1000 characters. The JS
side is `test_js_link_regex_redos.py`.
"""

from __future__ import annotations

import time

import pytest

from tessellate.ai import (
    composer_chat,
    composer_extra,
    composer_frame,
    composer_threads,
    page_analysis,
    study,
    task_acts,
)
from tessellate.entry import link_offers

N = 30_000
BOUND_S = 2.0

SHAPES = {
    "[": "[" * N,
    "![": "![" * (N // 2),
    "[[": "[[" * (N // 2),
    "[^": "[^" * (N // 2),
    "[**": "[**" * (N // 3),
    "[a](": "[a](" * (N // 4),
    "![a](b": "![a](b" * (N // 6),
    "[a](#/notes/1": "[a](#/notes/1" * (N // 13),
    "<a": "<a" * (N // 2),
}


def _each(pattern):
    return lambda text: sum(1 for _ in pattern.finditer(text))


SCANNERS = {
    "composer_extra._LINKED": _each(composer_extra._LINKED),
    "study._FOOTNOTE": _each(study._FOOTNOTE),
    "study._FOOTNOTE_LINE": lambda t: study._FOOTNOTE_LINE.match(t),
    "study._LINK": _each(study._LINK),
    "composer_chat._LINK": _each(composer_chat._LINK),
    "composer_chat._plain": composer_chat._plain,
    "page_analysis._plain": page_analysis._plain,
    "task_acts.items_in": lambda t: task_acts.items_in("- " + t),
    "composer_frame._ONLY_PICTURES": lambda t: composer_frame._ONLY_PICTURES.fullmatch(t),
    "composer_frame._MEDIA": _each(composer_frame._MEDIA),
    "composer_threads._MARK_CHARS": _each(composer_threads._MARK_CHARS),
    "link_offers._BLOCKED": link_offers._blocked_spans,
}


@pytest.mark.parametrize("name", SCANNERS)
def test_scanner_is_linear_on_an_unclosed_run(name):
    scan = SCANNERS[name]
    for shape, text in SHAPES.items():
        started = time.perf_counter()
        scan(text)
        assert time.perf_counter() - started < BOUND_S, f"{name} on a run of {shape!r}"


def test_normal_links_still_read_the_same():
    assert composer_chat._plain("see [the plan](#/notes/4) and [**x**] now") == "see the plan and [x] now"
    assert page_analysis._plain("a [b c](http://x.y/z) `d`") == "a b c d"
    assert composer_extra._LINKED.search("[**Plan**](#/notes/12)").groups() == ("Plan", "12")
    assert study._LINK.search("[[Note|alias]] and [t](u)").group(1) == "Note"
    assert link_offers._blocked_spans("a [b](c) `d` <e>") == [(2, 8), (9, 12), (13, 16)]
