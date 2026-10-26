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
    assert "Call the landlord" in said and "(" in said, said


@pytest.mark.parametrize("q", ["the next 7 days", "what is the next 7 days"])
def test_a_bare_span_is_a_due_question(ask, q):  # noqa: F811
    said = ask(q, notes_only=False)
    assert "Call the landlord" in said or "Nothing" in said or "dated" in said, said
    assert "newest notes" not in said, said


def test_summarise_done_takes_a_voice():
    from tessellate.ai import commands

    assert commands.summarise_done(["Moved note 3"], []) == "Done: Moved note 3."
    assert commands.summarise_done(["Moved note 3"], [], lambda w: f"All set, {w}.") == "All set, Moved note 3."
    assert commands.summarise_done([], []) == "Nothing was changed."


#: composer8: the rest of small talk, and the no-answer, composed.
_KINDS = ["insult", "emotion", "who", "about_app", "joke", "unclear", "test", "nothing"]
_VOICES = ["natural", "professional", "playful", "plain"]


@pytest.mark.parametrize("kind", _KINDS)
@pytest.mark.parametrize("voice", _VOICES)
def test_the_rest_of_small_talk_has_sixteen_surfaces_a_voice(kind, voice):
    from tessellate.ai import composer_compose as cc

    mood = cc.mood_of("hello", voice=voice, seed="x")
    assert len(set(cc.eligible(f"social_{kind}", mood))) >= 16, (kind, voice)


@pytest.mark.parametrize("kind", ["who", "about_app"])
@pytest.mark.parametrize("voice", _VOICES)
def test_identity_kinds_name_the_assistant(kind, voice):
    from tessellate.ai import composer_compose as cc

    for line in cc.eligible(f"social_{kind}", cc.mood_of("hello", voice=voice, seed="x")):
        assert "Atlas" in line.split(".")[0] or "Atlas" in line, line


@pytest.mark.parametrize(("message", "kind", "intent"), [
    ("you're useless", "insult", "smalltalk"), ("i feel sad", "emotion", "smalltalk"), ("tell me a joke", "joke", "smalltalk"), ("asdfgh", "unclear", "smalltalk"),
    ("are you an ai", "who", "smalltalk"), ("what can you do", "about_app", "about_app"), ("test", "test", "smalltalk"),
])
@pytest.mark.parametrize("voice", _VOICES)
def test_stored_kinds_are_composed_and_vary(message, kind, intent, voice):
    from tessellate.ai import composer, phrasing

    said: list[str] = []
    for n in range(24):
        said.append(composer.social(message, intent, said[-1] if said else "", "", voice=voice, recent=said, seed=f"s{n}"))
    assert phrasing.repeats(said) == 0, (kind, voice)
    built = set(composer.social_surfaces(kind)) | set(composer.social_surfaces(kind, True))
    assert all(x in built for x in said), (kind, voice, [x for x in said if x not in built][:2])


@pytest.mark.parametrize("voice", _VOICES)
def test_the_nothing_found_line_is_composed_in_the_chat_voice(voice):
    from tessellate.ai import composer

    texts = set()
    for n in range(40):
        got = composer.compose("what is the zorblax code", [], voice="natural", register=voice, salt=f"s{n}", turn=n)
        assert got["missed"] and got["text"].strip(), got
        texts.add(got["text"])
    assert len(texts) >= 8, (voice, len(texts))


def test_the_nothing_found_line_follows_the_register():
    from tessellate.ai import composer

    terse = {composer.compose("zorblax", [], register="plain", salt=str(n), turn=n)["text"] for n in range(20)}
    formal = {composer.compose("zorblax", [], register="professional", salt=str(n), turn=n)["text"] for n in range(20)}
    assert not terse & formal


def test_composing_the_rest_is_cheap():
    import time

    from tessellate.ai import composer

    for msg in ("tell me a joke", "asdfgh", "test", "you're useless"):
        composer.social(msg, voice="playful", seed="warm")
        began = time.perf_counter()
        for n in range(20):
            composer.social(msg, voice="playful", seed=str(n))
        assert (time.perf_counter() - began) / 20 < 0.005, msg


@pytest.mark.parametrize("register", ["natural", "professional", "playful", "plain"])
def test_an_empty_window_is_said_in_the_chat_voice(register):
    from datetime import date

    from tessellate.ai import composer

    said = {composer.empty_window("last month", date(2026, 9, 1), date(2026, 10, 20), seed=str(n), register=register) for n in range(60)}
    assert len(said) >= 8, (register, len(said))
    assert all("!" not in s and chr(0x2014) not in s and s[0].isupper() for s in said), said
    one = composer.empty_window("last month", date(2026, 9, 1), date(2026, 9, 1), register=register)
    assert "1 September" in one, one


def test_the_ask_controls_are_one_group_after_the_field():
    from pathlib import Path

    html = (Path(__file__).resolve().parents[1] / "frontend" / "index.html").read_text(encoding="utf-8")
    row = html.split("ask-query-row ask-composer", 1)[1].split("ask-offline", 1)[0]
    group = row.split("ask-controls", 1)[1]
    assert row.index("id=\"question\"") < row.index("ask-controls")
    assert all(i in group for i in ("ask-mode-select", "ask-time-travel", "ask-search-tune", "id=\"ask-btn\"", "stop-btn"))
