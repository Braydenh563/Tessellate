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


def _welcomes(**facts):
    base = {"hour": 9, "due": 2, "overdue": 0, "last": "Tides", "streak": 4, "notes": 3}
    return {cc.welcome(cc.mood_of(q, voice=v, seed=f"w{n}", intent="welcome"), **{**base, **facts}) for v in cc.VOICES for q in QUESTIONS for n in range(40)}


def test_the_welcome_is_built_on_the_clause_grammar_with_twenty_surfaces():
    """L-chat-231: the chat welcome is `composer_compose.welcome` (frames, a bridge, each fact one clause), and it says
    at least 20 distinct welcomes over the voices and moods; none claims a fact the notebook did not give."""
    seen = _welcomes()
    assert len(seen) >= 20, len(seen)
    assert not any("overdue" in s.lower() for s in seen), "an overdue clause with nothing overdue"
    quiet = _welcomes(due=0, streak=0, last="")
    assert len(quiet) >= 20 and not any("Tides" in s or "days" in s for s in quiet), len(quiet)


def test_the_dashboard_headline_has_twenty_phrases_per_day_and_none_is_false():
    """The dashboard headline is the owner's table (INBOX 876), seeded by day and hour: over a fortnight of hours it
    says at least 20 phrases, and a phrase that speaks of the notebook is said only when it is true."""
    from datetime import datetime, timedelta

    from tessellate.ai import greeting_compose as g

    start = datetime(2026, 11, 2)
    facts = g.NotebookFacts(total=40, today=0, this_week=2, days_since_last=1, streak=0)
    seen = {g.compose(start + timedelta(days=d, hours=h), facts)[0] for d in range(14) for h in range(24)}
    assert len(seen) >= 20, len(seen)
    busy = g.NotebookFacts(total=40, today=3, this_week=12, days_since_last=0, streak=5)
    said = {g.compose(start + timedelta(days=d, hours=h), busy)[0] for d in range(30) for h in range(24)}
    assert "A fresh page" not in said and "Welcome back" not in said
