"""VC8: the question-noise real-word check reads the shipped English list, so a
correctly spelt word is never bent into a vocabulary word."""

from __future__ import annotations

import pytest

from tessellate.ai import question_noise


@pytest.mark.parametrize("word", ["abbott", "acre", "arid", "babe", "behind", "arbour"])
def test_a_real_word_is_not_corrected(word):
    assert question_noise.is_real_word(word)
    assert question_noise.nearest(word, question_noise.VOCABULARY) is None


def test_a_typo_is_still_corrected():
    assert question_noise.repair("when is the dentst") == "when is the dentist"
    assert not question_noise.is_real_word("dentst")
