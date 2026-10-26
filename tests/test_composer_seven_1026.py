"""composer7: leftovers from composer5/6 and dog2, asked with no model."""

from __future__ import annotations

import pytest

from tests.test_composer_five_1025 import ask  # noqa: F401


def test_definition_does_not_volunteer_tasks(ask):  # noqa: F811
    said = ask("what is the Krebs cycle")
    assert "revise the krebs cycle diagram" not in said.lower(), said
    assert "read chapter 4" not in said.lower(), said


@pytest.mark.parametrize("q", ["what's my next exam", "exam date", "when is my next exam"])
def test_next_exam_uses_reminder(ask, q):  # noqa: F811
    said = ask(q)
    assert "12 Nov" in said or "November" in said or "Nov 12" in said, said
    assert "09:00" in said, said


@pytest.mark.parametrize("kind", ["how", "sorry", "laugh", "reaction", "confused", "ack", "compliment"])
@pytest.mark.parametrize("voice", ["natural", "professional", "playful", "plain"])
def test_small_talk_has_twenty_surfaces_a_voice(kind, voice):
    from tessellate.ai import composer_compose as cc

    mood = cc.mood_of("hello", voice=voice, seed="x")
    assert len(set(cc.eligible(f"social_{kind}", mood))) >= 16, (kind, voice)


def test_small_talk_follows_the_voice_and_the_emotion():
    from tessellate.ai import composer

    calm = {composer.social("sorry", voice="plain", seed=str(n)) for n in range(40)}
    formal = {composer.social("sorry", voice="professional", seed=str(n)) for n in range(40)}
    assert not calm & formal
    stressed = {composer.social("sorry i am so stressed about the deadline", voice="natural", seed=str(n)) for n in range(40)}
    assert any("one thing at a time" in x or "plate" in x or "pressing" in x or "juggling" in x or "stress" in x.lower() for x in stressed)


@pytest.mark.parametrize("q", ["due friday", "what's due friday", "what's on friday"])
def test_an_empty_weekday_says_nothing_is_dated(ask, q):  # noqa: F811
    said = ask(q, notes_only=False)
    assert "Friday" in said or "friday" in said, said
    assert "couldn't find" not in said, said
    assert "Next up: Call the landlord" in said, said


@pytest.mark.parametrize("q", ["the next 7 days", "what is the next 7 days"])
def test_a_bare_span_is_a_due_question(ask, q):  # noqa: F811
    said = ask(q, notes_only=False)
    assert "Call the landlord" in said or "Nothing" in said or "dated" in said, said
    assert "newest notes" not in said, said
