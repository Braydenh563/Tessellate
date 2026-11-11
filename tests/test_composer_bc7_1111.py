"""Batch BC7 (audit 1107 composer rows R3-32 to F1, rechecked 2026-11-11).
D7: "what does Tom want" is answered by the sentence that says what Tom
wants, not by the line that says who Tom is."""

from __future__ import annotations

import pytest

from tests.test_composer_bc6_1111 import say

GIFT = "# Gift ideas\n\nTom wants a book. Sara likes jazz records."
TOM = "# Tom\n\nTom is my friend."


@pytest.mark.parametrize("question", ["what does Tom want", "what does Tom want for his birthday", "what does tom want"])
def test_d7_what_a_person_wants_is_the_sentence_that_says_it(question):
    said = say(question, TOM, GIFT)
    assert "Tom wants a book" in said, said
    assert not said.startswith("Tom is my friend") and not said.startswith("Tom is your friend"), said


def test_d7_a_person_with_no_wanting_sentence_is_not_answered_with_the_wrong_line():
    said = say("what does Tom want", TOM)
    assert "wants" not in said or "not" in said.lower() or "friend" not in said.split(".")[0], said
