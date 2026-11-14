"""Composer round 5, 2026-11-08 (compare): rows of audits 1107 (D, E, R3) that round 4 left unfixed. Every
question runs through `/chat/stream` with no model and a fixed clock, because the seams these
rows share (the pool the route builds, the act cues, the history) sit in front of the composer."""

from __future__ import annotations

import time

import pytest

from tests import _r5_1108 as r5



@pytest.fixture
def ask(client, session, monkeypatch):
    return r5.driver(client, session, monkeypatch)


@pytest.mark.parametrize("question", ["Lisbon vs Atlas", "Lisbon versus Atlas", "Lisbon vs. Atlas", "Lisbon or Atlas which", "Lisbon or Atlas, which one", "Lisbon or Atlas, which is better"])
def test_d3_two_names_with_a_versus_cue_are_a_compare(ask, question):
    said = ask(question)["text"]
    assert "mention Lisbon" in said and "mentions Atlas" in said, said
    assert "You have four notes about Lisbon" not in said, said


def test_d3_the_versus_cues_are_linear():
    from tessellate.ai import composer_ask, composer_tables

    mine = [p for p in composer_tables.EXTRA_COMPARE_SIDES if "of them" in p.pattern and "{1,40}" in p.pattern]
    assert len(mine) == 1
    for run in ("a or " * 3000 + "b, which", "x " * 6000 + "or y which", "a" * 10_000 + " or b which one", "a or b " + " " * 10_000 + "which"):
        t0 = time.perf_counter()
        mine[0].match(run)
        assert time.perf_counter() - t0 < 0.5, run[:20]
    for run in ("x " * 6000 + "or y which", "a" * 10_000 + " or b which one"):
        t0 = time.perf_counter()
        composer_ask.classify(run)
        assert time.perf_counter() - t0 < 2.0, run[:20]
