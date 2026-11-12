"""CodeQL 2086, 2087, 2088 (PR 216): the readers the composer rounds added
must be linear on the runs CodeQL named, and still read the asks they were
built for (the same shape as tests/test_redos_1031b.py)."""

from __future__ import annotations

import time

import pytest

from tessellate.ai import composer_lists, composer_slots, notebook_stats

N = 50_000
BOUND_S = 2.0

RUNS = {
    "tabs": "\t" * N,
    "tabs then bang": "notes about x" + "\t" * N + "!",
    "and not bangs": "notes\tnot\t!" + "\tand\tnot\t!" * (N // 10),
    "undone in tabs": "what\tundone\tin\t" + "\t\t" * (N // 2) + "\n",
    "spaces and marks": "how many notes have the word x" + " ?" * (N // 2) + "x",
}


def _timed(fn, text):
    started = time.perf_counter()
    fn(text)
    return time.perf_counter() - started


@pytest.mark.parametrize("name", RUNS)
def test_each_reader_is_linear_on_the_runs_codeql_named(name):
    text = RUNS[name]
    for label, fn in (
        ("without_ask", composer_lists.without_ask),
        ("kind", composer_lists.kind),
        ("asks_state", composer_slots.asks_state),
        ("_held_word", lambda t: notebook_stats._held_word(t, t)),  # noqa: SLF001
    ):
        assert _timed(fn, text) < BOUND_S, label


def test_the_readings_did_not_change():
    assert composer_lists.without_ask("notes about Tokyo but not Lisbon") == ("Tokyo", "Lisbon")
    assert composer_lists.without_ask("which notes are not about Lisbon") == ("", "Lisbon")
    assert composer_lists.without_ask("nothing about the word Lisbon") == ("", "Lisbon")
    assert composer_lists.without_ask("what is not done") is None
    assert composer_lists.without_ask("notes without tags") is None
    assert composer_lists.kind("notes about Tokyo but not Lisbon") == "without"
    assert composer_slots.asks_state("what's unpacked in my Tokyo list")
    assert composer_slots.asks_state("what is not ticked yet")
    assert not composer_slots.asks_state("what is the weather")
    assert notebook_stats._held_word("how many notes have the word lisbon?", "How many notes have the word Lisbon?") == "Lisbon"  # noqa: SLF001
