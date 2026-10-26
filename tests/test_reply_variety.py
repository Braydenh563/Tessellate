"""Varied replies (the owner, 2026-10-11: "can it have more varied
responses??"; `ai/phrasing.py`, `ai/composer_replies.py`).

Every reply family holds eight phrasings or more in both voices, a reply
never says a line one of the last three said nor opens like one, and it is
shaped unlike the one before. Measured over 50 consecutive replies a family,
from the prompts in `fixtures/reply_variety_prompts.json`:

| | before | after |
| --- | --- | --- |
| distinct openers in every four replies (mean) | 0.82 | 1.00 |
| replies shaped unlike the last (mean) | 0.60 | 1.00 |
| replies repeating one of the last three (of 950) | 250 | 0 |
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tessellate.ai import composer, composer_replies, phrasing, vocative

PROMPTS = json.loads((Path(__file__).parent / "fixtures" / "reply_variety_prompts.json").read_text(encoding="utf-8"))
OPENER_FLOOR = 0.95
SHAPE_FLOOR = 0.8
TURNS = 50


def _session(kind: str, seed: str = "s") -> list[str]:
    replies: list[str] = []
    prompts = PROMPTS[kind]
    for turn in range(TURNS):
        message = prompts[(turn * 3) % len(prompts)]
        if kind == "call":
            reply = composer.call(vocative.split(message).names, recent=replies, seed=seed)
        else:
            intent = "about_app" if kind == "about_app" else "smalltalk"
            reply = composer.social(message, intent, replies[-1] if replies else "", "", recent=replies, seed=seed)
        replies.append(reply)
    return replies


def test_every_family_has_eight_phrasings_in_both_voices():
    for kind in composer.SOCIAL:
        assert len(composer.SOCIAL[kind]) >= 8, kind
        assert len(composer.SOCIAL_PROFESSIONAL[kind]) >= 8, kind
    for voice, lines in composer_replies.CALL.items():
        assert len(lines) >= 8, voice


def test_every_family_is_measured():
    assert set(PROMPTS) == set(composer.SOCIAL) | {"call"}
    assert all(len(prompts) >= 8 for prompts in PROMPTS.values())


@pytest.mark.parametrize("kind", [k for k in PROMPTS if k != "call"])
def test_the_prompts_read_as_their_family(kind):
    intent = "about_app" if kind == "about_app" else "smalltalk"
    wrong = [(m, composer.social_kind(m, intent)) for m in PROMPTS[kind] if composer.social_kind(m, intent) != kind]
    assert not wrong, wrong


@pytest.mark.parametrize("kind", list(PROMPTS))
def test_fifty_replies_vary(kind):
    replies = _session(kind)
    assert phrasing.repeats(replies) == 0, kind
    assert phrasing.opener_ratio(replies) >= OPENER_FLOOR, kind
    assert phrasing.shape_variety(replies) >= SHAPE_FLOOR, kind


def test_the_same_seed_gives_the_same_words():
    assert _session("greeting", "a") == _session("greeting", "a")
    assert _session("greeting", "a") != _session("greeting", "b")


def test_a_family_holds_more_than_one_shape():
    for table in (composer.SOCIAL, composer.SOCIAL_PROFESSIONAL, composer_replies.CALL):
        for kind, lines in table.items():
            assert len({phrasing.shape(line) for line in lines}) >= 3, kind


@pytest.mark.parametrize(
    "line",
    [line for table in (composer_replies.SOCIAL_NATURAL, composer_replies.SOCIAL_PROFESSIONAL, composer_replies.CALL) for lines in table.values() for line in lines],
)
def test_house_style(line):
    assert "!" not in line and chr(0x2014) not in line and "Oops" not in line
    assert line[0].isupper() or line.startswith("{name}"), line


def test_a_nickname_is_said_back_now_and_then():
    """Some call lines say the name; most do not, and none laughs at "Atlas"."""
    said = [composer.call(["brotato"], seed=str(i)) for i in range(40)]
    named = sum("Brotato" in line for line in said)
    assert 0 < named < len(said) / 2
    assert not any(line.startswith("Ha") for line in (composer.call(["Atlas"], seed=str(i)) for i in range(40)))
    assert len(composer.call_asks("x")) == 3


#: Nothing found, 50 turns of one conversation asking what no note holds.
#: Measured 2026-10-11: openers 0.25 to 1.00 (natural) and 0.25 to 0.96
#: (professional); every one stays a question, so its shape varies less.
NOTHING_FLOOR = 0.9


@pytest.mark.parametrize("voice", ["natural", "professional"])
def test_nothing_found_varies_across_a_conversation(voice):
    notes = [{"id": 1, "content": "# Boiler\n\nDue in March.", "created_at": "2026-09-01"}]
    asked = ["What is the capital of Peru?", "who won the cup in 1966", "what is the speed of light", "where is the eiffel tower", "how tall is everest"]
    history: list[dict] = []
    replies: list[str] = []
    for turn in range(TURNS):
        question = asked[turn % len(asked)]
        out = composer.compose(question, notes, voice=voice, dialogue=composer.Dialogue.from_history(history, salt="s"))
        replies.append(out["text"])
        history.append({"question": question, "answer": out["text"]})
    assert phrasing.repeats(replies) == 0
    assert phrasing.opener_ratio(replies) >= NOTHING_FLOOR
    assert all(reply.endswith("?") for reply in replies)


@pytest.mark.parametrize("key", ["nothing", "none_found", "nothing_ask"])
def test_nothing_found_has_eight_wordings_a_voice(key):
    from tessellate.ai import composer_tables

    for voice in composer_tables.VOICES:
        assert len(composer_tables.VOICE_VARIANTS[voice][key]) >= 8, (key, voice)


@pytest.mark.parametrize("family", ["CONFIRM", "WHICH_NOTE"])
def test_clarifying_and_confirming_vary(family, app_state):
    """An act's Confirm line and its "which note?" were one sentence each:
    eight a voice now, and fifty acts in a row open differently."""
    from tessellate.ai import commands

    table = getattr(composer_replies, family)
    assert all(len(table[voice]) >= 8 for voice in ("natural", "professional"))
    assert all(len({phrasing.shape(line.format(label="Pin note 4", change="pin note 4", about="x")) for line in table[v]}) >= 2 for v in table)
    say = commands._confirm if family == "CONFIRM" else commands._which_note
    replies = [say(f"Move note {n} to Work" if family == "CONFIRM" else f"topic {n}") for n in range(TURNS)]
    assert phrasing.repeats(replies) == 0
    assert phrasing.opener_ratio(replies) >= OPENER_FLOOR, replies[:8]
    if family == "CONFIRM":
        assert all("Confirm" in r or "confirm" in r for r in replies)
