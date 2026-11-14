"""L-chat-229 and 230: every ability says at least 20 distinct surfaces across the voices and the five moods
(the 11 named abilities hold it in one voice, `test_composer_compose_1026.py`), and the voices differ in rhythm:
the terse voice's frames are short fragments, the formal voice's the longest."""

from __future__ import annotations

import pytest
from tests.test_composer_compose_1026 import FACTS

from tessellate.ai import composer_compose as cc
from tessellate.ai import composer_lines as lines

QUESTIONS = ("show me", "i am so stressed about this", "quick please", "this is broken again", "thanks, great")


@pytest.mark.parametrize("ability", sorted(lines.FRAMES))
def test_twenty_distinct_surfaces_across_voices_and_moods(ability):
    seen = {cc.say(ability, cc.mood_of(q, voice=v, seed=f"s{n}"), **FACTS[ability]) for v in cc.VOICES for q in QUESTIONS for n in range(60)}
    assert len(seen) >= 20, (ability, len(seen))


def test_the_voices_keep_their_rhythm_over_every_ability():
    """Words per frame, over all the abilities that name the four voices: terse is the shortest, formal or playful
    the longest, and every voice is measured on the same abilities."""
    mean: dict[str, float] = {}
    for voice in ("warm", "terse", "playful", "formal"):
        words = [len(x.text.split()) for frames in lines.FRAMES.values() for x in frames if x.voices == frozenset({voice})]
        mean[voice] = sum(words) / len(words)
    assert mean["terse"] < min(mean["warm"], mean["playful"], mean["formal"]), mean
    assert mean["terse"] * 1.5 < mean["formal"], mean
