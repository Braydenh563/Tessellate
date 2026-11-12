"""Composed lines read as English (owner, 2026-11-10): "You have four notes last weekend:"
put a count and a time side by side after a verb that takes neither."""

from __future__ import annotations

import pytest

from tessellate.ai import composer_compose


@pytest.mark.parametrize("voice", ["natural", "professional", "playful", "plain"])
def test_a_recent_list_lead_never_has_the_count_and_the_window_side_by_side_after_have(voice):
    for seed in range(60):
        mood = composer_compose.mood_of("what did I write last weekend", voice=voice, seed=f"s{seed}")
        line = composer_compose.frame("recent_any", mood, count="four notes", span="last weekend")
        assert not any(bad in line for bad in ("have four notes last weekend", "are four notes last weekend")), line
        assert "four notes" in line and "ast weekend" in line, line
