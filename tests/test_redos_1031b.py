"""CodeQL 1889, 1890, 1894 and the personal.py rstrip: the patterns that read a
typed question must be linear on a long run of one character.

Each public pass takes 50,000 characters of the run that made the old pattern
backtrack polynomially, inside a bound the old patterns took far longer to meet;
a second case pins that the readings did not change.
"""

from __future__ import annotations

import time

import pytest

from tessellate.ai import composer_digest, composer_money, personal, question_noise

N = 50_000
BOUND_S = 2.0

ADVERSARIAL = {
    "spaces after total time": "total time" + " " * N + "x",
    "spaces then bang": "total time" + " " * N + "!",
    "as": "A" * N,
    "as then digit": "A" * N + "1",
    "bangs": "x" + "!" * N + "x",
    "bangs only": "!" * N,
    "dots after word": "hmmm" + "." * N + "a",
    "gerund run": "a " * (N // 2) + "x",
}


@pytest.mark.parametrize("name", ADVERSARIAL)
def test_each_reader_is_linear_on_a_long_run(name):
    text = ADVERSARIAL[name]
    for label, fn in (
        ("drop_filler", question_noise.drop_filler),
        ("_totalled", composer_money._totalled),
        ("_clean", personal._clean),
    ):
        started = time.perf_counter()
        fn(text)
        assert time.perf_counter() - started < BOUND_S, label


def test_a_bare_total_still_reads_with_its_tail_and_trailing_marks():
    assert composer_money._totalled("what") == "what"
    assert composer_money._totalled("Total time?") == "what is my total time"
    assert composer_money._totalled("my total distance this month!!") == "what is my total distance this month"
    assert composer_money._totalled("how much time in total?") == "what is my total time"
    assert composer_money._totalled("total time? and more") == "total time? and more"


def test_filler_goes_and_words_stay():
    assert question_noise.drop_filler("errrmmm. hi test test") == "hi test test"
    assert question_noise.drop_filler("hmm") == "hmm"
    assert question_noise.drop_filler("hum along, um, now") == "hum along, now"


def test_a_fragment_rides_on_the_sentence_before():
    assert composer_digest._is_fragment("slicing everything but it was fun")
    assert composer_digest._is_fragment("straighter this time")
    assert not composer_digest._is_fragment("you did it again")
    assert not composer_digest._is_fragment("one two three four")
