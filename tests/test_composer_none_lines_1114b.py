"""L-chat-270: the remaining fixed "none" and "did you mean" lines (no more charts, notes or the web, no notes in a
language, a card no longer open, nothing saved in the week) are composed in the chat's voice, each still saying the plain fact."""

from __future__ import annotations

import pytest

from tessellate.ai import composer_compose as cc
from tessellate.ai import composer_lines

#: ability, facts, words of which every surface keeps one.
CASES = {
    "none_charts": ({}, ("chart", "statistics")),
    "torn_ask": ({}, ("notes", "web")),
    "none_language": ({"label": "Japanese"}, ("japanese",)),
    "card_gone": ({}, ("card", "ask")),
    "none_week": ({}, ("7 days", "week", "seven days")),
}


def _texts(ability: str, voice: str) -> set[str]:
    return {c.text for c in composer_lines.FRAMES[ability] if voice in c.voices}


@pytest.mark.parametrize("ability", sorted(CASES))
def test_the_line_is_composed_and_keeps_its_fact(ability):
    facts, stems = CASES[ability]
    seen = {cc.said_plain(ability, "what" + suffix, voice, **facts) for voice in ("natural", "professional", "plain", "playful") for suffix in ("", "?", "??", " now", " please")}
    assert len(seen) >= 4, seen
    assert all(any(w in s.lower() for w in stems) for s in seen), seen
    assert not any("!" in s or chr(0x2014) in s for s in seen)
    assert len(composer_lines.FRAMES[ability]) >= 10


def test_the_same_ask_is_said_the_same_way():
    assert cc.said_plain("card_gone", "yes", "natural") == cc.said_plain("card_gone", "yes", "natural")


def test_the_settings_voice_is_read_when_none_is_given(session):
    from tessellate.core import deps

    deps.get_config().set_preference("composer_voice", "plain")
    assert cc.said_plain("none_week") in _texts("none_week", "terse")
