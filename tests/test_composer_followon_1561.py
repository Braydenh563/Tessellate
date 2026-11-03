"""INBOX 1561 (e): a follow-on never repeats a subject the answer rejected. A praise
word is not a subject, so no chip asks "When did I write about interesting?"."""

from __future__ import annotations

import json

import pytest

from tessellate.entry import manager

PRAISE = ("interesting", "cool", "fun", "neat", "awesome", "amazing")


@pytest.fixture
def ask(client, session):
    for k in range(3):
        manager.create_entry(session, f"# Starters {k}\n\nAfter making an initial connection.\n\n- Ask something interesting and cool about their week {k}.\n")
    manager.create_entry(session, "# Interesting bean\n\nAn interesting bean from the market, roasted dark.")
    session.commit()

    def go(question: str) -> list[str]:
        chips: list[str] = []
        with client.stream("POST", "/chat/stream", json={"question": question, "answer_from": "notes", "notes_only": True, "use_tools": False}) as response:
            for line in response.iter_lines():
                if line.strip():
                    event = json.loads(line)
                    chips += [c for c in event.get("next") or [] if isinstance(c, str)]
        return chips

    return go


@pytest.mark.parametrize("word", PRAISE)
@pytest.mark.parametrize("shape", ["what do I have about {w}", "tell me about {w}", "summarise my {w} notes", "what is the latest on {w}", "how many notes about {w}"])
def test_no_follow_on_asks_about_a_praise_word(ask, word, shape):
    for chip in ask(shape.format(w=word)):
        low = chip.lower()
        assert not any(f"{p} {word}" in low or f"{p} {word}?" in low for p in ("about", "on", "in")), chip
        assert not low.rstrip("?").endswith(f"about {word}") and not low.rstrip("?").endswith(f"on {word}"), chip


def test_a_praise_word_beside_a_noun_still_makes_a_follow_on(ask):
    chips = ask("tell me about the interesting bean")
    assert chips, chips
