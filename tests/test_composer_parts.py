"""A hello, a thanks and a goodbye are composed from parts (O5, INBOX 904 B07).

Measured with no model before: 300 seeds of "hi", "thanks" and "bye" gave 19,
18 and 18 distinct replies (natural) and 13, 8 and 8 (professional); composed
they give about 100 or more, and every pair reads as a sentence.
"""

from __future__ import annotations

import pytest

from tessellate.ai import composer, composer_parts, phrasing

KINDS = ("greeting", "thanks", "bye")
MESSAGE = {"greeting": "hi", "thanks": "thanks", "bye": "bye"}


@pytest.mark.parametrize("voice", ["natural", "professional"])
@pytest.mark.parametrize("kind", KINDS)
def test_the_parts_join_into_sentences(voice, kind):
    heads, tails = composer_parts.PARTS[voice][kind]
    assert len(heads) >= 8 and len(tails) >= 8
    assert all(h.endswith(".") and h[0].isupper() and "?" not in h for h in heads)
    assert all(t[0].isupper() and t[-1] in ".?" for t in tails)
    assert len(set(heads)) == len(heads) and len(set(tails)) == len(tails)
    for line in composer_parts.lines(voice)[kind]:
        assert "!" not in line and chr(0x2014) not in line and "Oops" not in line


@pytest.mark.parametrize("voice", ["natural", "professional"])
@pytest.mark.parametrize("kind", KINDS)
def test_the_family_is_the_parts(voice, kind):
    table = composer.SOCIAL_PROFESSIONAL if voice == "professional" else composer.SOCIAL
    assert table[kind] == composer_parts.lines(voice)[kind]


@pytest.mark.parametrize("voice", ["natural", "professional"])
@pytest.mark.parametrize("kind", KINDS)
def test_many_seeds_say_many_things(voice, kind):
    said = {composer.social(MESSAGE[kind], voice=voice, seed=str(i)) for i in range(300)}
    assert len(said) >= 60, (kind, voice, len(said))


@pytest.mark.parametrize("kind", KINDS)
def test_a_tail_is_not_said_twice_running(kind):
    """Fifty replies in a row: no repeat of the last three, tails included."""
    replies: list[str] = []
    for turn in range(50):
        replies.append(composer.social(MESSAGE[kind], "smalltalk", replies[-1] if replies else "", "", recent=replies, seed="s"))
    assert phrasing.repeats(replies) == 0
    tails = [r.split(". ", 1)[1] if ". " in r else "" for r in replies]
    assert all(not (a and a == b) for a, b in zip(tails, tails[1:], strict=False))
