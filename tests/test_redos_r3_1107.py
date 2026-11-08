"""Composer round 3 (2026-11-07): the readers the round added are linear on
50,000-character runs (CodeQL polynomial ReDoS; same shape as test_redos_1107.py)."""

from __future__ import annotations

import time

import pytest

from tessellate.ai import composer_ask, composer_body, composer_digest, composer_property, question_noise

N = 50_000
BOUND_S = 2.0

RUNS = {
    "letters": "a" * N,
    "spaces": " " * N,
    "possessives": "x's " * (N // 4),
    "number of": "number of " * (N // 10),
    "number for": "number for the " * (N // 14),
    "apostrophes": "'" * N,
    "number then spaces": "what is the number" + " " * N + "!",
    "sentence breaks": ". A" * (N // 3),
    "labelled": "Wedding table: " + "A b " * (N // 4),
    "colons": ":" * N,
    "when words": "when is " * (N // 8),
    "first notes": "first note " * (N // 11),
    "she he": "she he " * (N // 7),
}

READERS = {
    "composer_property.asked": composer_property.asked,
    "composer_property.subject": composer_property.subject,
    "question_noise.slips_only": question_noise.slips_only,
}


@pytest.mark.parametrize("run", RUNS)
@pytest.mark.parametrize("reader", READERS)
def test_each_reader_is_linear(reader, run):
    started = time.perf_counter()
    READERS[reader](RUNS[run])
    assert time.perf_counter() - started < BOUND_S, (reader, run)


REGEXES = {
    "digest._SENTENCE_BREAK": composer_digest._SENTENCE_BREAK,
    "digest._LABELLED": composer_digest._LABELLED,
    "digest._OWN_DATE": composer_digest._OWN_DATE,
    "digest._WHEN_NOW": composer_digest._WHEN_NOW,
    "body._OWN_DATE": composer_body._OWN_DATE,
    "digest._PRONOUN_START": composer_digest._PRONOUN_START,
    "digest._PERSON_TITLE": composer_digest._PERSON_TITLE,
    "digest._FIRST_PERSON": composer_digest._FIRST_PERSON,
    "body._DAYISH": composer_body._DAYISH,
    "ask._ORDINAL_NOTE": composer_ask._ORDINAL_NOTE,
    "ask._DATE_ASK": composer_ask._DATE_ASK,
}


@pytest.mark.parametrize("run", RUNS)
@pytest.mark.parametrize("name", REGEXES)
def test_each_new_pattern_is_linear(name, run):
    started = time.perf_counter()
    REGEXES[name].search(RUNS[run])
    REGEXES[name].match(RUNS[run])
    assert time.perf_counter() - started < BOUND_S, (name, run)
